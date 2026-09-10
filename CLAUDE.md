# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

BMAD module that integrates sprint tracking with GitLab/GitHub Issues. It's not a runnable application — it's a set of TOML overrides and Skills-as-modules folders consumed by the new BMad installer (each `<skill>/module-manifest.toml` declares `module = "issue-tracking"`).

Requires BMM 6.11.0+ (uniform customize.toml support across all BMM workflows; targets the 6.11.0 skill set — `bmad-ux`, consolidated sprint-planning, `uv`-based tooling).

## Architecture

Two Skills-as-modules folders, each with its own manifest declaring the same module key:

- `skills/bmad-issue-tracking-sync/` — the user-facing `/bmad-issue-tracking-sync` command. Manifest: `module = "issue-tracking"`, `knowledge = "references/help.md in the bmad-issue-tracking-sync skill"`.
- `skills/bmad-issue-tracking-setup/` — one-time deploy. Manifest: same module key, plus `scripts = [...]` listing the bmad-loop integration Python + shell files.

Assets that get pushed into a consumer project live under `skills/bmad-issue-tracking-setup/assets/custom/` (TOML pointers), `assets/workflows/` (YAML bodies), and `assets/bmad-workflow-lang.md`. The standalone sync SKILL.md never gets copied into a consumer project — only `assets/` payloads do, via the setup skill.

### Issue sync workflow split

The sync task is split into two phases so callers can skip redundant setup:

- **`issue-sync/prepare.yaml`** (steps 1-3) — platform detection, labels, board, PRD issue creation
- **`issue-sync/sync.yaml`** (steps 4-6) — sync issues, mark MR ready, summary (includes its own `check-config` + `find-prd` since context may be compacted)

Callers:
- `sprint-planning/complete.yaml` → `INCLUDE: issue-sync/sync` (steps 4-6 only, prepare ran during sprint planning)
- `sprint-status/complete.yaml` → `INCLUDE: issue-sync/sync` (steps 4-6 only, prepare ran during sprint status)
- `/bmad-issue-tracking-sync` standalone → `INCLUDE: issue-sync/prepare` then `INCLUDE: issue-sync/sync`

## TOML override semantics

Files in `skills/bmad-issue-tracking-setup/assets/custom/` are TOML overrides for BMM workflows:
- `[workflow] activation_steps_append` — array, appends to BMM's activation steps
- `[workflow] on_complete` — scalar, replaces BMM's completion block entirely

All overrides are pure pointers — they reference workflow YAML files that handle the actual logic. The config guard (`common/check-config.yaml` validating `issue_tracking.platform`, `issue_tracking.branch_patterns`, etc.) runs inside each workflow YAML, not in the TOML.

## Key variable conventions in instructions

TOML instructions reference these placeholders — they are NOT config variables, they're resolved at runtime by the AI agent:
- `{prd_key}` — from PRD frontmatter, e.g. `mobile-oidc`
- `{story_key}` — sprint-status entry key, e.g. `1-3-login-form`
- `{epic_num}`, `{story_num}` — extracted from `story_key` (first two dash-separated numbers)
- `{prd_branch}` — `branch_patterns.prd` resolved with `{prd_key}`, e.g. `feat/mobile-oidc/prd`
- `{story_branch}` — `branch_patterns.story` resolved with `{prd_key}` and `{story_key}`
- `{sep}` — `::` for GitLab, `:` for GitHub (label separator)
- `$MR_HOST`, `$MR_PROJECT` — git remote host/project for MR operations (GitLab); same as `$HOST`/`$PROJECT_PATH` when platforms match
- `$MR_OWNER`, `$MR_REPO` — git remote owner/repo for PR operations (GitHub); same as `$OWNER`/`$REPO` when platforms match

## Issue title formats

All workflows that create issues use these title formats. They must stay consistent — `create-issue.yaml` searches by title to avoid duplicates.

| Type | Format | Set by |
|------|--------|--------|
| PRD | `PRD: {prd_key}` | `bmad-prd/complete.yaml`, `create-prd/complete.yaml`, `issue-sync/prepare.yaml` |
| Story | `Story {epic_num}.{story_num}: {title}` | `create-story/complete.yaml`, `sync-issues.yaml` |
| Epic | `Epic {n}: {title}` | `sync-issues.yaml` |
| Retrospective | `Retrospective: Epic {n}` | `retrospective/complete.yaml` |

For stories, `{title}` is extracted from the story file heading (`# Story 1.4: Login Form` → `Login Form`). During initial sync (sprint-planning), story files don't exist yet — the title is derived from the entry key (`1-4-login-form` → `Login Form`). Both paths produce the same format.

## Branch/MR flow

Branch setup happens in activation (before BMM workflow runs). The BMM workflow creates files directly in the worktree. on_complete handles commit/push/issue/MR. Never commit on PRD for story work.

| Workflow | Activation | on_complete | MR direction |
|----------|-----------|-------------|--------------|
| bmad-prd (6.11.0+) | Detect intent: create → ask key + create worktree; update/validate → find worktree | Create → issue + commit + push + draft MR; update → update description | PRD → default (draft, create only) |
| create-prd (6.11.0+ shim) | Create/switch to PRD worktree | Commit + push + issue + draft MR | PRD → default (draft) |
| create-architecture | Switch to PRD worktree | Commit + push | (PRD worktree) |
| bmad-ux | Switch to PRD worktree | Commit + push | (PRD worktree) |
| create-epics-and-stories | Switch to PRD worktree | Commit + push | (PRD worktree) |
| sprint-planning | Switch to PRD worktree | Trigger issue sync (steps 4-6) | (PRD worktree) |
| edit-prd (6.11.0+ shim) | Switch to PRD worktree | Update PRD issue description | (PRD worktree) |
| correct-course | Switch to PRD worktree | Update issue descriptions if artifacts modified | (PRD worktree) |
| retrospective | Switch to PRD worktree | Create retrospective issue + close | (PRD worktree) |
| create-story (shim) | Ask story key, create/switch to story worktree (from PRD) | Commit + push + issue + MR | story → PRD |
| dev-story (shim) | Find story with status `ready-for-dev`, switch to worktree | Commit + push + update issue | (MR from create-story) |
| code-review | Find story with status `review`, switch to worktree | Commit + push + post review + optional merge | story → PRD |
| sprint-status (shim) | Switch to PRD worktree | Trigger issue sync (steps 4-6) | (none) |

### bmad-loop flow (unattended)

Projects using [`bmad-loop`](https://github.com/bmad-code-org/bmad-loop) bypass the manual branch/MR flow: bmad-loop drives `bmad-build-auto` per story in isolated worktrees, is the single writer of `sprint-status.yaml`, and merges each story back locally (never pushes). The module's role shrinks to mirroring:

- `common/find-prd-key.yaml` — silent `prd_key` resolution (no PRD worktree, no prompt); used by `issue-sync/prepare.yaml` + `sync.yaml` so `/bmad-issue-tracking-sync` runs unattended after a bmad-loop run.
- `common/mark-mr-ready.yaml` — no-op when no MR exists (bmad-loop has none); the MR-based CI gates (`check-mr-ci`, `wait-for-green-ci`) are not used in this flow.
- `scripts/bmad-loop/ci-gate/ci-status.sh` (declared in the setup skill's `module-manifest.toml` `scripts = [...]`) — bmad-loop `[verify]` command deployed to `.bmad-loop/ci-status.sh` (setup step 3c): reads `ci-status.json` (written by the `dev-finish` / `review-finish` phases of `common/post-dev-complete.yaml` via `common/write-ci-status.yaml`) and returns exit 0 if CI is green, exit 1 if red (fixable), exit 1 if the file is missing. The intelligent work (polling CI, parsing logs) is done by the `on_complete` workflow.
- `custom/bmad-build-auto.toml` — routes the `bmad-build-auto` `on_complete` hook to `common/post-build-dispatch.yaml` (non-interactive dispatcher). The bmad-build-auto skill executes this hook at the end of EVERY session — including when bmad-loop invokes it — so issue tracking + CI write happen without any bmad-loop plugins. `bmad-build.toml` uses the interactive dispatcher (`post-build-dispatch-interactive.yaml`) with the optional MR merge prompt.
- `awaiting-operator` — bmad-loop status for a story parked on external action; mapped to `status{sep}awaiting-operator` and the issue stays open.

## Platform differences

- GitLab: `glab` CLI, labels use `::` separator, `glab api` for issue updates (labels field replaces all), `glab label create` for labels
- GitHub: `gh` CLI, labels use `:` separator, `gh issue edit --add-label`/`--remove-label` for label updates (preserves other labels)
- `glab api` uses `--hostname`; `glab mr`/`glab label` use `-R`; `gh` uses `-R` with format `[HOST/]OWNER/REPO`

**Git remote vs issue tracker:** The git remote (origin) and issue tracker can be on different platforms (e.g., code on GitLab, issues on GitHub). `issue_tracking.platform` is the issue tracker; `issue_tracking.git_platform` (set during setup) is the git remote. Issue operations (create/update/close issues, labels, comments) use `platform`. MR/PR operations (list, create, merge, mark ready) use `git_platform`. When they differ, `host`/`project` apply to the issue tracker and `git_host`/`git_project` apply to the git remote. Issue references in MR descriptions use `Closes #X` for same-platform, full URL for cross-platform.

## Files to update when adding a new BMM workflow override

1. Create `skills/bmad-issue-tracking-setup/assets/custom/bmad-{workflow}.toml` (pointer format — activation_steps_append and/or on_complete)
2. Create the corresponding workflow YAML files in `skills/bmad-issue-tracking-setup/assets/workflows/{workflow}/`
3. Add the TOML file to the list in `skills/bmad-issue-tracking-setup/SKILL.md` (step 3)
4. Add the YAML files to the list in `skills/bmad-issue-tracking-setup/SKILL.md` (step 3b)
5. Add a row to the override table in `README.md`
6. If the workflow has a standalone skill, create or update its `references/help.md` and bump `version` in `<skill>/module-manifest.toml` (manifest is now the source of truth — `module-help.csv` no longer exists)

## Python environment

Tests use `pytest` and `pyyaml`. Always use the project venv — never `pip3 install --break-system-packages`:
```bash
python3 -m venv .venv && source .venv/bin/activate && pip install pytest pyyaml
```

## Releasing

When working on a branch, add functional changes to the `[Unreleased]` section of `CHANGELOG.md` following Keep a Changelog format (Added, Changed, Fixed, etc.) — one entry per logical change, not per commit.

When cutting a release:
1. Bump `version` in every `skills/*/module-manifest.toml` so all skills declare the same release version (manifest is now the source of truth — `module.yaml` and `marketplace.json` no longer exist).
2. Update `CHANGELOG.md` — replace `[Unreleased]` with the version and date, add comparison link.
3. Create a git tag `v{version}` on the version bump commit and push it (`git push origin --tags`).
