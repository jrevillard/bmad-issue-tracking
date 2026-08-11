#!/usr/bin/env bash
# bmad-loop CI gate (bound to `pre_ready_gate`).
#
# 1. Push the story branch (so the code is safe even if the run is interrupted).
# 2. Wait for the remote pipeline to go green:
#    - branch pipeline by default (GitLab pipelines on pushed branches; GitHub
#      Actions when configured on push);
#    - if CI only runs on merge requests (`mr_for_ci=always`, or `auto` when the
#      branch has no pipeline), create a trace MR and poll ITS pipeline. The MR
#      is left open: once the local merge-back is pushed to the target branch,
#      GitLab auto-marks it merged, leaving the story's execution trace.
# 3. Exit 0 on green (bmad-loop proceeds to merge-back); emit a JSON veto and
#    exit 1 on red/timeout (unit is DEFERRED).
set -u

branch="${BMAD_LOOP_BRANCH:-}"
repo_root="${BMAD_LOOP_REPO_ROOT:-}"
worktree="${BMAD_LOOP_WORKTREE:-}"
platform="${BMAD_LOOP_SETTING_PLATFORM:-gitlab}"
host="${BMAD_LOOP_SETTING_HOST:-}"
project="${BMAD_LOOP_SETTING_PROJECT:-}"
target="${BMAD_LOOP_SETTING_TARGET_BRANCH:-main}"
timeout_sec="${BMAD_LOOP_SETTING_TIMEOUT_SEC:-1800}"
mr_for_ci="${BMAD_LOOP_SETTING_MR_FOR_CI:-auto}"

log() { echo "[ci-gate] $*"; }

veto_defer() {
  echo "{\"veto\": {\"action\": \"defer\", \"reason\": \"$*\"}}"
  exit 1
}

# ------------------------------------------------------------------ settings

[ -n "$branch" ] || veto_defer "BMAD_LOOP_BRANCH is empty"
[ -n "$repo_root" ] || veto_defer "BMAD_LOOP_REPO_ROOT is empty"
[ -n "$worktree" ] || veto_defer "BMAD_LOOP_WORKTREE is empty"

# Resolve host/project from the git remote when not configured.
if [ -z "$host" ] || [ -z "$project" ]; then
  remote="$(git -C "$repo_root" remote get-url origin 2>/dev/null || true)"
  [ -n "$remote" ] || veto_defer "no origin remote and host/project not configured"
  case "$remote" in
    git@*)
      host="${remote#git@}"; host="${host%%:*}"
      proj="${remote#*:}"; proj="${proj%.git}"
      ;;
    ssh://git@*)
      rest="${remote#ssh://git@}"; host="${rest%%:*}"
      proj="${rest#*:}"; proj="${proj%.git}"
      ;;
    http*)
      host="$(printf '%s' "$remote" | sed -E 's#^https?://([^/]+)/.*#\1#')"
      proj="$(printf '%s' "$remote" | sed -E 's#^https?://[^/]+/(.*)$#\1#')"
      proj="${proj%.git}"
      ;;
    *) veto_defer "unparseable origin remote: $remote" ;;
  esac
  [ -n "$host" ] || veto_defer "could not resolve host from remote"
  [ -z "$project" ] && project="$proj"
fi
[ -n "$project" ] || veto_defer "could not resolve project from remote"

# ------------------------------------------------------------------- helpers

# Latest pipeline status for a branch, or "no_pipeline".
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

# Pipeline status of the trace MR/PR for the branch, or "no_mr"/"no_pipeline".
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
      gh pr checks "$num" -R "${host}/${project}" --json state --jq '.[0].state' 2>/dev/null \
        || echo no_pipeline
      ;;
  esac
}

# Create a trace MR/PR (CI vehicle + execution trace). Left open.
create_mr() {
  case "$platform" in
    gitlab)
      glab mr create --source-branch "$branch" --target-branch "$target" \
        --title "CI: $branch" --description "Trace MR created by the bmad-loop ci-gate plugin." \
        --yes --no-editor -R "${host}/${project}" >/dev/null 2>&1 \
        && log "created trace MR for $branch -> $target"
      ;;
    github)
      gh pr create --base "$target" --head "$branch" \
        --title "CI: $branch" --body "Trace PR created by the bmad-loop ci-gate plugin." \
        -R "${host}/${project}" >/dev/null 2>&1 \
        && log "created trace PR for $branch -> $target"
      ;;
  esac
}

# -------------------------------------------------------------------- main

# 1. Push the story branch.
if ! git -C "$worktree" push -u origin "$branch" >/dev/null 2>&1; then
  veto_defer "git push of $branch failed"
fi
log "pushed $branch"

# 2. Decide which pipeline to poll.
mode="branch"
if [ "$mr_for_ci" = "always" ]; then
  mode="mr"
elif [ "$mr_for_ci" = "auto" ]; then
  s="$(branch_status)"
  if [ "$s" = "no_pipeline" ] || [ -z "$s" ]; then
    mode="mr"
  fi
fi

if [ "$mode" = "mr" ]; then
  if [ "$(mr_status)" = "no_mr" ]; then
    create_mr
    sleep 5
    [ "$(mr_status)" != "no_mr" ] || veto_defer "could not create trace MR"
  fi
fi
log "polling $mode pipeline for $branch (timeout ${timeout_sec}s)"

# 3. Poll until green/red/timeout.
deadline=$(( $(date +%s) + timeout_sec ))
while :; do
  [ "$(date +%s)" -ge "$deadline" ] && veto_defer "CI timeout after ${timeout_sec}s"
  if [ "$mode" = "mr" ]; then s="$(mr_status)"; else s="$(branch_status)"; fi
  case "$s" in
    success|SUCCESS|completed|successful) log "CI green"; exit 0 ;;
    failed|FAILURE|failure|cancelled|timed_out|action_required)
      veto_defer "CI failed ($s)" ;;
    no_mr) veto_defer "no MR available for CI" ;;
    running|pending|queued|in_progress|no_pipeline|""|null) sleep 30 ;;
    *) sleep 30 ;;
  esac
done
