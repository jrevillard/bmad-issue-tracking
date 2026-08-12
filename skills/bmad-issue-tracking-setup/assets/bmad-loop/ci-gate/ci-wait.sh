#!/usr/bin/env bash
# bmad-loop CI gate, used as a `[verify]` command.
#
# It pushes the story branch (propagating whatever code is on it — including
# bmad-loop's deterministic _fix_phase repairs) and waits for the remote pipeline
# to go green. It does NOT create MRs and does NOT fix code itself: the trace MR
# and issue tracking are the LLM `story-track` workflow's job, and a red CI is
# fixed by bmad-loop's feedback-driven repair session.
#
# Why it pushes: `_fix_phase` (the deterministic repair) commits locally but does
# not push, so the branch must be re-pushed before each CI check or the fix never
# reaches the remote pipeline.
#
# Exit contract (bmad-loop verify.py): a non-zero rc is a failed verify command.
#   - rc=1  -> fixable: a RED/timed-out CI. bmad-loop re-runs bmad-build-auto
#             with the failing output as feedback (_fix_phase, bounded by
#             max_dev_attempts).
#   - rc=126 -> ENV FAULT (bmad-loop ENV_FAULT_RCS={126,127}): a configuration /
#             environment error (platform unknown, host/project unresolved,
#             CLI/auth/network/push failure). bmad-loop ESCALATES — the run
#             pauses for an environment fix and the story's repair budget resets
#             — instead of burning the budget on a futile repair.
#
# Setup (see /bmad-issue-tracking-setup step 3c):
#   cp <assets>/bmad-loop/ci-gate/ci-wait.sh .bmad-loop/ci-wait.sh
#   # .bmad-loop/policy.toml
#   [scm]
#   worktree_seed = [".bmad-loop/ci-wait.sh"]
#   [verify]
#   commands = ["bash .bmad-loop/ci-wait.sh"]
#
# Note: bmad-loop caps each verify command at 30 minutes (COMMAND_TIMEOUT_S);
# keep TIMEOUT_SEC below that.
set -u

worktree="$(pwd)"
branch="$(git -C "$worktree" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")"
platform="${BMAD_LOOP_SETTING_PLATFORM:-}"
host="${BMAD_LOOP_SETTING_HOST:-}"
project="${BMAD_LOOP_SETTING_PROJECT:-}"
timeout_sec="${BMAD_LOOP_SETTING_TIMEOUT_SEC:-1500}"

log() { echo "[ci-wait] $*"; }
# The gate itself: red/timeout CI. rc=1 is bmad-loop's fixable class -> _fix_phase.
fail() { echo "[ci-wait] FAIL: $*"; exit 1; }
# Configuration/environment errors: rc=126 is bmad-loop's env-fault class -> the
# run ESCALATES (pauses for an environment fix, budget resets) instead of burning
# the story's repair budget on a futile repair.
env_fail() { echo "[ci-wait] ENV-FAULT: $*"; exit 126; }

# ------------------------------------------------------------------ settings

[ -n "$branch" ] || env_fail "not on a git branch (cwd=$worktree)"

# Resolve platform from the module config first — self-hosted instances
# (opensource.unicc.org, GHE, ...) don't betray their platform in the hostname,
# but the module records it as `git_platform` (or `platform`) in
# `_bmad/custom/issue-tracking.yaml`, which bmad-loop copies into each worktree.
# Strip inline YAML comments (`key: value  # comment`) so the value stays clean.
cfg="$worktree/_bmad/custom/issue-tracking.yaml"
if [ -z "$platform" ] && [ -f "$cfg" ]; then
  platform="$(sed -n 's/^[[:space:]]*git_platform:[[:space:]]*//p' "$cfg" | head -1 \
    | sed 's/[[:space:]]*#.*$//' | tr -d '"'"'"'[:space:]')"
  [ -z "$platform" ] && platform="$(sed -n 's/^[[:space:]]*platform:[[:space:]]*//p' "$cfg" | head -1 \
    | sed 's/[[:space:]]*#.*$//' | tr -d '"'"'"'[:space:]')"
fi

# Resolve host/project/platform from the git remote when not configured.
if [ -z "$host" ] || [ -z "$project" ] || [ -z "$platform" ]; then
  remote="$(git -C "$worktree" remote get-url origin 2>/dev/null || true)"
  [ -n "$remote" ] || env_fail "no origin remote and host/project not configured"
  case "$remote" in
    git@*)
      rhost="${remote#git@}"; rhost="${rhost%%:*}"
      rproj="${remote#*:}"; rproj="${rproj%.git}"
      ;;
    ssh://git@*)
      rest="${remote#ssh://git@}"
      rhost="${rest%%[:/]*}"
      rproj="${rest#*:}"; rproj="${rproj#*/}"; rproj="${rproj%.git}"
      ;;
    http*)
      rhost="$(printf '%s' "$remote" | sed -E 's#^https?://([^/]+)/.*#\1#')"
      rproj="$(printf '%s' "$remote" | sed -E 's#^https?://[^/]+/(.*)$#\1#')"
      rproj="${rproj%.git}"
      ;;
    *) env_fail "unparseable origin remote: $remote" ;;
  esac
  [ -n "$rhost" ] || env_fail "could not resolve host from remote"
  [ -z "$host" ] && host="$rhost"
  [ -z "$project" ] && project="$rproj"
  [ -z "$platform" ] && case "$host" in
    *gitlab*) platform="gitlab" ;;
    *github*) platform="github" ;;
    *) env_fail "could not infer platform from host ($host) — set git_platform in _bmad/custom/issue-tracking.yaml or BMAD_LOOP_SETTING_PLATFORM" ;;
  esac
fi
[ -n "$project" ] || env_fail "could not resolve project from remote"
[ -n "$platform" ] || env_fail "platform not resolved (gitlab | github)"

# The GitLab API requires the URL-encoded namespace path for nested groups
# (`projects/un%2Fitu%2Fgenie-ai`, not `projects/un/itu/genie-ai`).
project_enc="${project//\//%2F}"

# The CI CLI must exist — a missing glab/gh would silently read "no_pipeline"
# and pass the gate with no CI run at all.
if [ "$platform" = "gitlab" ] && ! command -v glab >/dev/null 2>&1; then
  env_fail "glab CLI not found on PATH"
fi
if [ "$platform" = "github" ] && ! command -v gh >/dev/null 2>&1; then
  env_fail "gh CLI not found on PATH"
fi

# ------------------------------------------------------------------- helpers

# Run a status function, store its output in $STATUS, and translate an
# `env_fault:` marker into an env_fail. Must be called WITHOUT command
# substitution: a bare `exit 126` inside `$(...)` would only exit the subshell
# and be lost, so the functions emit `env_fault:<reason>` and this wrapper does
# the env_fail in the caller's (main) shell.
status_get() {
  STATUS="$("$1")"
  case "$STATUS" in
    env_fault:*) env_fail "${STATUS#env_fault:}" ;;
  esac
}

# Latest pipeline status for the branch: success/failed/running/... or
# "no_pipeline". Emits "env_fault:<reason>" on an API/CLI error.
branch_status() {
  local raw rc
  case "$platform" in
    gitlab)
      raw="$(glab api "projects/${project_enc}/pipelines?ref=${branch}" --hostname "$host" 2>&1)"; rc=$?
      [ "$rc" -eq 0 ] || { echo "env_fault:glab API call failed for $host/$project — not authenticated or project not found: $(printf '%s' "$raw" | head -c 120)"; return; }
      printf '%s' "$raw" | uv run --no-project python -c 'import json,sys; d=json.load(sys.stdin); print(d[0]["status"] if d else "no_pipeline")' 2>/dev/null \
        || { echo "env_fault:uv run python failed — is uv installed on PATH?"; return; }
      ;;
    github)
      raw="$(gh run list --branch "$branch" -R "${host}/${project}" --limit 1 --json status,conclusion 2>&1)"; rc=$?
      [ "$rc" -eq 0 ] || { echo "env_fault:gh API call failed for $host/$project — not authenticated or repo not found: $(printf '%s' "$raw" | head -c 120)"; return; }
      printf '%s' "$raw" | uv run --no-project python -c 'import json,sys; d=json.load(sys.stdin); print(d[0]["conclusion"] or d[0]["status"] if d else "no_pipeline")' 2>/dev/null \
        || { echo "env_fault:uv run python failed — is uv installed on PATH?"; return; }
      ;;
  esac
}

# Pipeline status of the story's trace MR/PR, or "no_mr"/"no_pipeline".
# Aggregates ALL check states on GitHub. Emits "env_fault:" on an API error.
mr_status() {
  local raw rc
  case "$platform" in
    gitlab)
      raw="$(glab api "projects/${project_enc}/merge_requests?source_branch=${branch}" --hostname "$host" 2>&1)"; rc=$?
      [ "$rc" -eq 0 ] || { echo "env_fault:glab API call failed for $host/$project: $(printf '%s' "$raw" | head -c 120)"; return; }
      iid="$(printf '%s' "$raw" | uv run --no-project python -c 'import json,sys; d=json.load(sys.stdin); print(d[0]["iid"] if d else "")' 2>/dev/null || echo "")"
      [ -n "$iid" ] || { echo no_mr; return; }
      raw="$(glab api "projects/${project_enc}/merge_requests/${iid}/pipelines" --hostname "$host" 2>&1)"; rc=$?
      [ "$rc" -eq 0 ] || { echo "env_fault:glab API call failed for $host/$project: $(printf '%s' "$raw" | head -c 120)"; return; }
      printf '%s' "$raw" | uv run --no-project python -c 'import json,sys; d=json.load(sys.stdin); print(d[0]["status"] if d else "no_pipeline")' 2>/dev/null \
        || { echo "env_fault:uv run python failed — is uv installed on PATH?"; return; }
      ;;
    github)
      raw="$(gh pr list --head "$branch" -R "${host}/${project}" --json number --jq '.[0].number' 2>&1)"; rc=$?
      [ "$rc" -eq 0 ] || { echo "env_fault:gh API call failed for $host/$project: $(printf '%s' "$raw" | head -c 120)"; return; }
      num="$raw"
      [ -n "$num" ] || { echo no_mr; return; }
      raw="$(gh pr checks "$num" -R "${host}/${project}" --json state 2>&1)"; rc=$?
      [ "$rc" -eq 0 ] || { echo "env_fault:gh API call failed for $host/$project: $(printf '%s' "$raw" | head -c 120)"; return; }
      printf '%s' "$raw" | uv run --no-project python -c 'import json,sys
states=[c["state"] for c in json.load(sys.stdin)]
if not states: print("no_pipeline")
elif any(s in ("FAILURE","ERROR","ACTION_REQUIRED","CANCELLED","TIMED_OUT") for s in states): print("failed")
elif all(s=="SUCCESS" for s in states): print("success")
else: print("in_progress")' 2>/dev/null \
        || { echo "env_fault:uv run python failed — is uv installed on PATH?"; return; }
      ;;
  esac
}

# -------------------------------------------------------------------- main

# 1. Push the story branch (propagate the current code — including any
#    _fix_phase repair commits — so the remote CI runs on what we will check).
#    One retry for transient network failures before escalating.
if ! git -C "$worktree" push -u origin "$branch" >/dev/null 2>&1; then
  sleep 3
  git -C "$worktree" push -u origin "$branch" >/dev/null 2>&1 \
    || env_fail "git push of $branch failed (auth/network/remote state)"
fi
log "pushed $branch"

# 2. GitLab creates the ref pipeline asynchronously — wait a few seconds and
#    re-check before concluding there is no pipeline (avoids a spurious
#    post-push "no CI gate" pass on un-CI'd code).
status_get branch_status
for _ in 1 2 3; do
  [ "$STATUS" = "no_pipeline" ] || break
  sleep 5
  status_get branch_status
done

mode="branch"; s="$STATUS"
if [ "$s" = "no_pipeline" ] || [ -z "$s" ]; then
  status_get mr_status
  if [ "$STATUS" = "no_mr" ] || [ "$STATUS" = "no_pipeline" ] || [ -z "$STATUS" ]; then
    log "no pipeline found for $branch — no CI gate"
    exit 0
  fi
  mode="mr"; s="$STATUS"
fi
log "polling $mode pipeline for $branch (timeout ${timeout_sec}s)"

# 3. Poll until green/red/timeout.
deadline=$(( $(date +%s) + timeout_sec ))
while :; do
  [ "$(date +%s)" -ge "$deadline" ] && fail "CI timeout after ${timeout_sec}s"
  if [ "$mode" = "mr" ]; then
    status_get mr_status
    s="$STATUS"
    if [ "$s" = "no_pipeline" ]; then
      # MR pipeline not indexed yet but a branch pipeline exists — fall back.
      status_get branch_status
      [ "$STATUS" = "no_pipeline" ] || { mode="branch"; s="$STATUS"; }
    fi
  else
    status_get branch_status
    s="$STATUS"
  fi
  case "$s" in
    success|SUCCESS|completed|successful) log "CI green"; exit 0 ;;
    failed|FAILURE|failure|error|ERROR|cancelled|canceled|skipped|manual|neutral|stale|timed_out|action_required)
      fail "CI failed ($s)" ;;
    no_mr) env_fail "no MR available for CI (the story-track trace MR is gone — a remote-state issue, not the story's code)" ;;
    running|pending|queued|in_progress|no_pipeline|""|null) sleep 30 ;;
    *) sleep 30 ;;
  esac
done
