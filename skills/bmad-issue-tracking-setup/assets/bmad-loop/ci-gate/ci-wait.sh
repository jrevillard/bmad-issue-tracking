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
# Exit 0 on green, or when no pipeline exists (CI not triggered / not
# configured). Exit non-zero on red/timeout -> bmad-loop treats it as a failed
# verify command and answers with a feedback-driven repair session (re-runs
# bmad-build-auto with the failing output) — the auto-fix loop.
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
fail() { echo "[ci-wait] FAIL: $*"; exit 1; }

# ------------------------------------------------------------------ settings

[ -n "$branch" ] || fail "not on a git branch (cwd=$worktree)"

# Resolve platform from the module config first — self-hosted instances
# (opensource.unicc.org, GHE, ...) don't betray their platform in the hostname,
# but the module records it as `git_platform` (or `platform`) in
# `_bmad/custom/issue-tracking.yaml`, which bmad-loop copies into each worktree.
cfg="$worktree/_bmad/custom/issue-tracking.yaml"
if [ -z "$platform" ] && [ -f "$cfg" ]; then
  platform="$(sed -n 's/^\s*git_platform:\s*//p' "$cfg" | head -1 | tr -d '"'"'"'[:space:]')"
  [ -z "$platform" ] && platform="$(sed -n 's/^\s*platform:\s*//p' "$cfg" | head -1 | tr -d '"'"'"'[:space:]')"
fi

# Resolve host/project/platform from the git remote when not configured.
if [ -z "$host" ] || [ -z "$project" ] || [ -z "$platform" ]; then
  remote="$(git -C "$worktree" remote get-url origin 2>/dev/null || true)"
  [ -n "$remote" ] || fail "no origin remote and host/project not configured"
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
    *) fail "unparseable origin remote: $remote" ;;
  esac
  [ -n "$rhost" ] || fail "could not resolve host from remote"
  [ -z "$host" ] && host="$rhost"
  [ -z "$project" ] && project="$rproj"
  [ -z "$platform" ] && case "$host" in
    *gitlab*) platform="gitlab" ;;
    *github*) platform="github" ;;
    *) fail "could not infer platform from host ($host) — set BMAD_LOOP_SETTING_PLATFORM" ;;
  esac
fi
[ -n "$project" ] || fail "could not resolve project from remote"
[ -n "$platform" ] || fail "platform not resolved (gitlab | github)"

# ------------------------------------------------------------------- helpers

# Latest pipeline status for the branch, or "no_pipeline".
branch_status() {
  case "$platform" in
    gitlab)
      glab api "projects/${project}/pipelines?ref=${branch}" --hostname "$host" 2>/dev/null \
        | uv run --no-project python -c 'import json,sys; d=json.load(sys.stdin); print(d[0]["status"] if d else "no_pipeline")' 2>/dev/null \
        || echo no_pipeline
      ;;
    github)
      gh run list --branch "$branch" -R "${host}/${project}" --limit 1 --json status,conclusion 2>/dev/null \
        | uv run --no-project python -c 'import json,sys; d=json.load(sys.stdin); print(d[0]["conclusion"] or d[0]["status"] if d else "no_pipeline")' 2>/dev/null \
        || echo no_pipeline
      ;;
  esac
}

# Pipeline status of the story's trace MR/PR (created by story-track), or
# "no_mr"/"no_pipeline". Aggregates ALL check states on GitHub.
mr_status() {
  case "$platform" in
    gitlab)
      iid="$(glab api "projects/${project}/merge_requests?source_branch=${branch}" --hostname "$host" 2>/dev/null \
        | uv run --no-project python -c 'import json,sys; d=json.load(sys.stdin); print(d[0]["iid"] if d else "")' 2>/dev/null || echo "")"
      [ -n "$iid" ] || { echo no_mr; return; }
      glab api "projects/${project}/merge_requests/${iid}/pipelines" --hostname "$host" 2>/dev/null \
        | uv run --no-project python -c 'import json,sys; d=json.load(sys.stdin); print(d[0]["status"] if d else "no_pipeline")' 2>/dev/null \
        || echo no_pipeline
      ;;
    github)
      num="$(gh pr list --head "$branch" -R "${host}/${project}" --json number --jq '.[0].number' 2>/dev/null || echo "")"
      [ -n "$num" ] || { echo no_mr; return; }
      gh pr checks "$num" -R "${host}/${project}" --json state 2>/dev/null \
        | uv run --no-project python -c 'import json,sys
states=[c["state"] for c in json.load(sys.stdin)]
if not states: print("no_pipeline")
elif any(s in ("FAILURE","ERROR","ACTION_REQUIRED","CANCELLED","TIMED_OUT") for s in states): print("failed")
elif all(s=="SUCCESS" for s in states): print("success")
else: print("in_progress")' 2>/dev/null \
        || echo no_pipeline
      ;;
  esac
}

# -------------------------------------------------------------------- main

# 1. Push the story branch (propagate the current code — including any
#    _fix_phase repair commits — so the remote CI runs on what we will check).
if ! git -C "$worktree" push -u origin "$branch" >/dev/null 2>&1; then
  fail "git push of $branch failed"
fi
log "pushed $branch"

# 2. Which pipeline to poll: the branch's if it has one, else the trace MR's.
bs="$(branch_status)"
mode="branch"; s="$bs"
if [ "$s" = "no_pipeline" ] || [ -z "$s" ]; then
  ms="$(mr_status)"
  if [ "$ms" = "no_mr" ] || [ "$ms" = "no_pipeline" ] || [ -z "$ms" ]; then
    log "no pipeline found for $branch — no CI gate"
    exit 0
  fi
  mode="mr"; s="$ms"
fi
log "polling $mode pipeline for $branch (timeout ${timeout_sec}s)"

# 2. Poll until green/red/timeout.
deadline=$(( $(date +%s) + timeout_sec ))
while :; do
  [ "$(date +%s)" -ge "$deadline" ] && fail "CI timeout after ${timeout_sec}s"
  if [ "$mode" = "mr" ]; then
    s="$(mr_status)"
    if [ "$s" = "no_pipeline" ]; then
      # MR pipeline not indexed yet but a branch pipeline exists — fall back.
      bs2="$(branch_status)"
      [ "$bs2" = "no_pipeline" ] || { mode="branch"; s="$bs2"; }
    fi
  else
    s="$(branch_status)"
  fi
  case "$s" in
    success|SUCCESS|completed|successful) log "CI green"; exit 0 ;;
    failed|FAILURE|failure|error|ERROR|cancelled|canceled|skipped|manual|neutral|stale|timed_out|action_required)
      fail "CI failed ($s)" ;;
    no_mr) fail "no MR available for CI" ;;
    running|pending|queued|in_progress|no_pipeline|""|null) sleep 30 ;;
    *) sleep 30 ;;
  esac
done
