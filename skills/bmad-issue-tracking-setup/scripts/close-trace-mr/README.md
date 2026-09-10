# close-trace-mr

A `bmad-loop` plugin that auto-closes the trace MR/PR after `bmad-loop`'s
local merge. Bmad-loop opens a per-story worktree, runs dev + review, then
merges the story branch into the target branch **locally**. The trace MR/PR
that `bmad-issue-tracking`'s `common/ensure-mr.yaml` workflow opened earlier
(source_branch = story branch, target_branch = PRD branch) is now redundant —
this plugin closes it.

## Stage

`post_merge`. Fires from `bmad-loop/src/bmad_loop/worktree_flow.py:2300`,
after `journal.append("unit-merged", ...)` and before
`close_unit_workspace` tears the worktree down. The merge has already landed
on the local target branch by the time this hook runs.

The hook is **non-blocking**: a failure logs `plugin-hook` and the run
continues. The local merge is the source of truth — a missing trace-MR close
must NOT defer an already-merged unit.

## Env vars consumed

Set by `bmad-loop/src/bmad_loop/plugins/bus.py::_hook_env` (line 85):

| Var | Use |
|-----|-----|
| `BMAD_LOOP_STAGE` | Always `"post_merge"` — informational only |
| `BMAD_LOOP_BRANCH` | The story branch just merged = source branch of the trace MR |
| `BMAD_LOOP_STORY_KEY` | Used to name the marker file |
| `BMAD_LOOP_RUN_DIR` | Where the marker file is written |
| `BMAD_LOOP_REPO_ROOT` | Where `_bmad/custom/issue-tracking.yaml` lives |
| `BMAD_LOOP_PLUGIN` | Always `"close-trace-mr"` |
| `BMAD_LOOP_SETTING_CLOSE_TRACE_MR` | `"true"` \| `"false"` — master switch |
| `BMAD_LOOP_SETTING_PLATFORM` | Optional override for tracker platform |
| `BMAD_LOOP_SETTING_HOST` | Optional override for tracker host |
| `BMAD_LOOP_SETTING_PROJECT` | Optional override for tracker project path |

## Configuration resolution

`platform`, `host`, `project` resolve in this order (first hit wins):

1. `BMAD_LOOP_SETTING_*` overrides (manual operator escape hatch).
2. `_bmad/custom/issue-tracking.yaml` — keys `platform` + `host` + `project`,
   or `git_platform` + `git_host` + `git_project` when the issue tracker
   differs from the git remote.

If no `platform` is found after both passes, the hook no-ops cleanly and
writes `status: skipped` to the marker. This happens for projects that have
not configured `bmad-issue-tracking`.

## Idempotency

Re-running on an already-closed MR is safe:

- **GitLab**: `PUT .../merge_requests/{iid}?state_event=close` on a closed
  MR returns HTTP 409, which `glab` surfaces as a non-zero exit. The hook
  intercepts this and treats it as success (the MR is closed — that was the
  goal).
- **GitHub**: `gh pr close <n>` on a closed PR returns rc=0 with "already
  closed" on stdout. The hook matches that message and treats it as success.

A defensive sweep handles a degenerate multi-MR state: if the source_branch
resolves to 2+ open MRs (e.g. a prior duplicate), every open one is closed.

## Squash vs merge-commit

Independent of `bmad-loop`'s local merge strategy (`scm.merge_strategy`
in `{merge, squash, fast_forward, replay}`). The trace MR lives on the
REMOTE (GitLab/GitHub), and the local merge is a separate operation — the
MR close is always `state_event=close` (GitLab) or `gh pr close` (GitHub),
with no relation to the local commit shape. A squash-merged local branch
and a merge-commit-merged local branch both produce identical MR-closed
outcomes.

## Marker file

Written to `$BMAD_LOOP_RUN_DIR/post-merge-<safe_story_key>.md` with a YAML
front-matter:

```markdown
---
status: done
stage: post_merge
plugin: close-trace-mr
branch: feat/admin-logs-victorialogs/prd/story-1-6
platform: gitlab
host: opensource.unicc.org
project: un/itu/genie-ai
mr_iid: 17
closed_at: 2026-09-07T10:42:31Z
---

Closed MR !17 after local merge of feat/admin-logs-victorialogs/prd/story-1-6
into feat/admin-logs-victorialogs/prd.
```

The marker is **human-observable**: `bmad-loop`'s bus does not poll for it
(per `src/bmad_loop/plugins/bus.py::HookBus.emit`). The authoritative record
remains the journal line `plugin-hook plugin=close-trace-mr stage=post_merge
rc=<n>`. The marker exists so operators can see what happened without
scrolling logs.

If the hook is skipped (no platform configured, or master switch off), the
marker still lands, with `status: skipped` and an explanatory `message:`
field.

## Exit codes

| Code | Meaning |
|------|---------|
| 0    | All MRs/PRs closed (or none found — clean) |
| 1    | Configuration error (invalid platform, missing project) — logged, run continues |
| 2    | Partial failure — at least one MR/PR failed to close (logged, run continues) |

In all error cases the `blocking = false` declaration prevents the run from
being deferred. The merge has already succeeded.

## Installation

The plugin is deployed automatically by `bmad-issue-tracking-setup` step 3d.
For manual install:

```bash
mkdir -p .bmad-loop/plugins
cp -r <path>/close-trace-mr .bmad-loop/plugins/
chmod +x .bmad-loop/plugins/close-trace-mr/close-trace-mr.sh
```

bmad-loop discovers the plugin on the next run. To disable:

```toml
# .bmad-loop/policy.toml
[plugins.close-trace-mr.settings]
close_trace_mr = false
```

## Files

```
close-trace-mr/
├── plugin.toml              # manifest declaring post_merge hook
├── close-trace-mr.sh        # bash trampoline -> Python
├── close_trace_mr.py        # stdlib-only Python module (logic)
├── README.md                # this file
└── tests/
    └── test_close_trace_mr.py  # pytest unit tests
```

## Tests

```bash
uv run --no-project --directory .bmad-loop/plugins/close-trace-mr \
    python -m pytest tests/ -v
```

Covers: env extraction, config parsing (lenient), MR-list parsing (empty,
multi-MR), close command construction, atomic marker write, end-to-end
orchestration, GitLab 409 / GitHub "already closed" idempotency, and the
manifest's TOML schema (via `bmad-loop`'s `PluginManifest` parser).
