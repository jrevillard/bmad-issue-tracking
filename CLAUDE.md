# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

BMAD extension module that integrates sprint tracking with GitLab/GitHub Issues. It's not a runnable application — it's a set of TOML overrides and skills deployed into consuming BMAD projects via the BMAD installer (`npx bmad-method install`).

Requires BMM 6.4.0+ (uniform customize.toml support across all BMM workflows).

## Architecture

Two concepts that must stay aligned:

- **Standalone skill** (`skills/bmad-bmm-issue-sync/SKILL.md`) — the user-facing slash command (`/bmad-bmm-issue-sync`) and the single source of truth for the sync task
- **Deployed copy** — during setup, this file is copied to `_bmad/_config/custom/bmad-bmm-issue-sync.md` in the consuming project. TOML `on_complete` hooks reference this deployed path.

The standalone skill IS the source. If you edit it, the deployed copy in consuming projects won't update automatically — users must re-run `/bmad-issue-tracking-setup`.

## TOML override semantics

Files in `skills/bmad-issue-tracking-setup/assets/custom/` are TOML overrides for BMM workflows:
- `[workflow] activation_steps_append` — array, appends to BMM's activation steps
- `[workflow] on_complete` — scalar, replaces BMM's completion block entirely

All overrides use the same config guard pattern: check `issue_tracking.platform` and `issue_tracking.branch_patterns` in `_bmad/bmm/config.yaml` before proceeding.

## Key variable conventions in instructions

TOML instructions reference these placeholders — they are NOT config variables, they're resolved at runtime by the AI agent:
- `{prd_key}` — from PRD frontmatter, e.g. `mobile-oidc`
- `{story_key}` — sprint-status entry key, e.g. `1-3-login-form`
- `{epic_num}`, `{story_num}` — extracted from `story_key` (first two dash-separated numbers)
- `{prd_branch}` — `branch_patterns.prd` resolved with `{prd_key}`, e.g. `feat/mobile-oidc/prd`
- `{story_branch}` — `branch_patterns.story` resolved with `{prd_key}` and `{story_key}`
- `{sep}` — `::` for GitLab, `:` for GitHub (label separator)

## Branch/MR flow

| Workflow | Branch action | MR direction |
|----------|--------------|--------------|
| create-prd | Create PRD worktree + push | PRD branch → default branch (draft) |
| create-story | Commit on PRD + create story worktree + push | story branch → PRD branch |
| dev-story | Switch to story worktree + commit + push | (MR exists from create-story) |
| code-review | Switch to story worktree + commit + push + optional merge | story branch → PRD branch |

## Platform differences

- GitLab: `glab` CLI, labels use `::` separator, `glab api` for issue updates (labels field replaces all), `glab label create` for labels
- GitHub: `gh` CLI, labels use `:` separator, `gh issue edit` with `--add-label`/`--remove-label` (targeted)
- `glab api` uses `--hostname`; `glab mr`/`glab label` use `-R`; `gh` uses `-R` with format `[HOST/]OWNER/REPO`

## Files to update when adding a new BMM workflow override

1. Create `skills/bmad-issue-tracking-setup/assets/custom/bmad-{workflow}.toml` with the config guard
2. Add it to the file list in `skills/bmad-issue-tracking-setup/SKILL.md` (step 3)
3. Add a row to the override table in `README.md`
4. Update `module-help.csv` if the workflow has a standalone skill

## Version alignment

When bumping `module.yaml` version, also update `.claude-plugin/marketplace.json` plugin version to match.
