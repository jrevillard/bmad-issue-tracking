#!/usr/bin/env bash
# bmad-loop CI status checker, used as a `[verify]` command.
#
# Reads ci-status.json written by the story-track-dev or story-track-review workflow (LLM session).
# Returns exit 0 if CI is green, exit 1 if red (with diagnostic in output).
#
# This script is deterministic and fast — it just reads a file. The intelligent
# work (polling CI, parsing logs, distinguishing flaky vs real) is done by
# story-track-dev and story-track-review (LLM workflows).
#
# Exit contract (bmad-loop verify.py):
#   - rc=0  -> CI green, proceed
#   - rc=1  -> CI red, fixable: bmad-loop re-runs bmad-build-auto with the
#              diagnostic as feedback (_fix_phase)
#
# Setup (see /bmad-issue-tracking-setup step 3c):
#   cp <assets>/bmad-loop/ci-gate/ci-status.sh .bmad-loop/ci-status.sh
#   # .bmad-loop/policy.toml
#   [verify]
#   commands = ["bash .bmad-loop/ci-status.sh"]

set -u

worktree="$(pwd)"
ci_status_file="$worktree/ci-status.json"

log() { echo "[ci-status] $*"; }
fail() { echo "[ci-status] FAIL: $*"; exit 1; }

# Check if ci-status.json exists
if [ ! -f "$ci_status_file" ]; then
  echo "[ci-status] ENV-FAULT: ci-status.json not found — story-track-dev or story-track-review workflow did not complete"
  exit 126  # bmad-loop ENV_FAULT_RCS={126,127} -> escalate, reset budget
fi

# Read status from JSON
status="$(uv run --no-project python -c "import json,sys; print(json.load(open(sys.argv[1]))['status'])" "$ci_status_file" 2>&1)"
if [ $? -ne 0 ]; then
  echo "[ci-status] ENV-FAULT: failed to parse ci-status.json — story-track-dev or story-track-review wrote invalid JSON: $status"
  exit 126  # bmad-loop ENV_FAULT_RCS={126,127} -> escalate, reset budget
fi

case "$status" in
  green)
    log "CI green"
    exit 0
    ;;
  red)
    # Output the full diagnostic for bmad-loop to capture in feedback/
    log "CI red — diagnostic:"
    cat "$ci_status_file"
    exit 1
    ;;
  *)
    fail "unknown status in ci-status.json: $status"
    ;;
esac
