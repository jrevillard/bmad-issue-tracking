# Module: issue-tracking — setup skill

Deploys the issue-tracking override assets into a consumer project's `_bmad/` tree. Run once after installing the module.

## What it copies

- TOML pointers in `assets/custom/bmad-*.toml` → `_bmad/custom/` (override bmm workflows' `on_complete` + `activation_steps_append`)
- YAML workflows in `assets/workflows/**` → `_bmad/_config/custom/workflows/` (executed by the hooks above)
- Optional: `scripts/bmad-loop/ci-gate/ci-status.sh` → consumer's `.bmad-loop/` (only when project uses bmad-loop)
- Optional: `scripts/close-trace-mr/**` → consumer's `.bmad-loop/plugins/` (only when bmad-loop + issue-tracking coexist)

## Refs the module expects at runtime (consumer side)

- `_bmad/_config/custom/issue-tracking.yaml` — sidecar config the asset workflows read (platform, host, project, worktree_base, branch_patterns)
- A working `glab` (GitLab) or `gh` (GitHub) CLI

## References to running skills in this module

- `/bmad-issue-tracking-sync` — the mirror dispatch; run via its own skill folder, not via this one.

## Sibling module doc

See `bmad-issue-tracking-sync/references/help.md` for the routing view of both skills.
