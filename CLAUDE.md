# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

BMAD extension module that integrates sprint tracking with GitLab/GitHub Issues. It's not a runnable application — it's a set of TOML overrides and skills deployed into consuming BMAD projects via the BMAD installer (`npx bmad-method install`).

Requires BMM 6.11.0+ (uniform customize.toml support across all BMM workflows; targets the 6.11.0 skill set — `bmad-ux`, consolidated sprint-planning, `uv`-based tooling).

## Architecture

Two concepts that must stay aligned:

- **Standalone skill** (`skills/bmad-bmm-issue-sync/SKILL.md`) — the user-facing slash command (`/bmad-bmm-issue-sync`), delegates to `issue-sync/prepare.yaml` + `issue-sync/sync.yaml`
- **Deployed copy** — during setup, this file is copied to `_bmad/_config/custom/bmad-bmm-issue-sync.md` in the consuming project. TOML `on_complete` hooks reference this deployed path.

The standalone skill IS the source. If you edit it, the deployed copy in consuming projects won't update automatically — users must re-run `/bmad-issue-tracking-setup`.

### Issue sync workflow split

The sync task is split into two phases so callers can skip redundant setup:

- **`issue-sync/prepare.yaml`** (steps 1-3) — platform detection, labels, board, PRD issue creation
- **`issue-sync/sync.yaml`** (steps 4-6) — sync issues, mark MR ready, summary (includes its own `check-config` + `find-prd` since context may be compacted)

Callers:
- `sprint-planning/complete.yaml` → `INCLUDE: issue-sync/sync` (steps 4-6 only, prepare ran during sprint planning)
- `sprint-status/complete.yaml` → `INCLUDE: issue-sync/sync` (steps 4-6 only, prepare ran during sprint status)
- `/bmad-bmm-issue-sync` standalone → `INCLUDE: issue-sync/prepare` then `INCLUDE: issue-sync/sync`

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

- `common/find-prd-key.yaml` — silent `prd_key` resolution (no PRD worktree, no prompt); used by `issue-sync/prepare.yaml` + `sync.yaml` so `/bmad-bmm-issue-sync` runs unattended after a bmad-loop run.
- `common/mark-mr-ready.yaml` — no-op when no MR exists (bmad-loop has none); the MR-based CI gates (`check-mr-ci`, `wait-for-green-ci`) are not used in this flow.
- `assets/bmad-loop/ci-gate/ci-wait.sh` — bmad-loop `[verify]` command deployed to `.bmad-loop/ci-wait.sh` (setup step 3c): **check-only** — finds the story branch's pipeline (or its trace MR's) and waits for green. No push, no MR creation, no fix. A red CI fails the verify command → bmad-loop's feedback-driven repair session re-runs `bmad-build-auto` with the failing output (auto-fix, bounded by `max_dev_attempts`) → re-verify.
- `assets/bmad-loop/story-track/` — bmad-loop plugin (deployed to `.bmad-loop/plugins/story-track/`, setup step 3c) declaring a `[workflows.story-track]` LLM session at `post_review_result`, `blocking=true`: pushes the final story branch, ensures the trace MR exists, and mirrors the story to its GitLab/GitHub issue (status label, result comment, MR link). Runs BEFORE the `ci-wait` verify, so the branch is pushed and the pipeline exists when the CI check polls. The trace MR is left open (GitLab auto-marks it merged after the local merge-back is pushed).
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
6. Update `module-help.csv` if the workflow has a standalone skill

## Python environment

Tests use `pytest` and `pyyaml`. Always use the project venv — never `pip3 install --break-system-packages`:
```bash
python3 -m venv .venv && source .venv/bin/activate && pip install pytest pyyaml
```

## Releasing

When working on a branch, add functional changes to the `[Unreleased]` section of `CHANGELOG.md` following Keep a Changelog format (Added, Changed, Fixed, etc.) — one entry per logical change, not per commit.

When cutting a release:
1. Update version in `module.yaml` and `.claude-plugin/marketplace.json` (must match)
2. Update `CHANGELOG.md` — replace `[Unreleased]` with the version and date, add comparison link
3. Create a git tag `v{version}` on the version bump commit and push it (`git push origin --tags`)
