#!/usr/bin/env bash
# close-trace-mr.sh — bmad-loop post_merge declarative-hook trampoline.
#
# The manifest's `cmd` template (plugin.toml `[hooks.post_merge].cmd`) calls this
# script with `{scripts}` expanded to the plugin folder, so it sits next to the
# Python module that owns all the logic. The script's only job is to:
#
#   1. Resolve the plugin folder's own path (no hard-coded absolute paths, so
#      the plugin ships to any consumer without rewrite).
#   2. Hand off to the Python module under `uv run --no-project` — the same
#      invocation the rest of bmad-issue-tracking uses, so we add no new
#      dependency surface (no venv install, no pyyaml requirement).
#   3. Forward the script's exit code verbatim — the bus maps non-zero exits
#      to a `defer` veto only because we set `blocking = false`. With non-
#      blocking, the bus logs `plugin-hook` and continues. The marker file
#      written by the Python module is the human-observable record.
#
# Failure isolation: every error path is inside the Python module — this
# script never raises. The bus still wraps the subprocess for transport
# failures (timeout, launch error), which is logged `plugin-hook-error`.

set -u

# `BASH_SOURCE[0]` is the path the bus invoked. Resolve symlinks so a symlinked
# install (e.g. via `npx bmad-method install` -> ~/.bmad/cache/...) still finds
# close_trace_mr.py next to itself.
plugin_dir="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"

# All logic lives in the Python module — kept thin here so unit tests can
# import it directly without spawning bash. `uv run --no-project` runs against
# the active python without creating a project venv (BMM 6.11.0+ requirement;
# the SKILL.md step 1 already verifies `uv` is available).
exec uv run --no-project --directory "$plugin_dir" python "$plugin_dir/close_trace_mr.py"