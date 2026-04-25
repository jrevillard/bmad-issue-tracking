# BMAD Issue Tracking

BMAD extension module that mirrors sprint tracking to GitLab Issues or GitHub Issues. Supports both cloud and self-hosted instances via their respective CLIs (`glab` / `gh`).

Uses BMAD's native TOML customization for all workflow integrations.

## Prerequisites

- BMAD Method module (BMM) 6.4.0+ installed in your project
- `glab` CLI (GitLab) or `gh` CLI (GitHub) installed and authenticated
- Repository with Issues enabled

## Installation

### 1. Install the module via BMAD installer

```bash
npx bmad-method install --custom-source https://github.com/jrevillard/bmad-issue-tracking
```

This registers three skills as slash commands:
- `/bmad-bmm-issue-sync` — Sync sprint status to issues
- `/bmad-bmm-issue-link` — Cross-reference merged MRs/PRs to issues
- `/bmad-issue-tracking-setup` — Deploy TOML overrides and shared tasks (run once)

### 2. Run the setup skill

```
/bmad-issue-tracking-setup
```

This deploys TOML overrides to `_bmad/custom/`, shared tasks to `_bmad/_config/custom/`, and configures the platform.

### 3. Configure PRD key

Add `prd_key` to your PRD frontmatter:

```markdown
---
prd_key: my-initiative
---
```

## What gets installed

### Skills (via BMAD installer)

Registered as slash commands in your IDE.

| Skill | Command | Purpose |
|---|---|---|
| Sync Issues | `/bmad-bmm-issue-sync` | Sync `sprint-status.yaml` to issues |
| Link MRs/PRs | `/bmad-bmm-issue-link` | Cross-reference merged MRs/PRs to issues via comments |
| Setup | `/bmad-issue-tracking-setup` | One-time integration setup |

### TOML overrides (via setup)

Deployed to `_bmad/custom/`. Survive BMM updates automatically.

| Override file | Target workflow | Hook | Behavior |
|---|---|---|---|
| `bmad-check-implementation-readiness.toml` | `check-implementation-readiness` | `on_complete` | Updates issue descriptions if artifacts were modified |
| `bmad-code-review.toml` | `code-review` | `on_complete` | Posts review findings as comment, updates status |
| `bmad-correct-course.toml` | `correct-course` | `on_complete` | Updates issue descriptions for modified stories/epics/PRD |
| `bmad-create-story.toml` | `create-story` | `on_complete` | Creates issue with full story file content |
| `bmad-dev-story.toml` | `dev-story` | `on_complete` | Posts implementation summary, updates status |
| `bmad-edit-prd.toml` | `edit-prd` | `on_complete` | Updates PRD issue description |
| `bmad-retrospective.toml` | `retrospective` | `on_complete` | Creates issue with retrospective content |
| `bmad-sprint-planning.toml` | `sprint-planning` | `on_complete` | Triggers full issue sync |
| `bmad-sprint-status.toml` | `sprint-status` | `on_complete` | Triggers full issue sync |

> **Note:** All overrides require BMM 6.4.0+ (uniform customize.toml support across all BMM workflows).

### Shared custom tasks (via setup)

Copied to `_bmad/_config/custom/` — referenced by TOML `on_complete` hooks.

- `bmad-bmm-issue-sync.md` — Sync `sprint-status.yaml` to issues (GitLab or GitHub)
- `bmad-bmm-issue-link.md` — Cross-reference merged MRs/PRs to issues via comments

## Usage

### Sync sprint status to issues

```
/bmad-bmm-issue-sync
```

Creates/updates issues for all sprint entries, manages labels, reconciles statuses.

### Cross-reference merged MRs/PRs to issues

```
/bmad-bmm-issue-link
```

Two-tier matching: pattern, manual. Posts "Related to #N" comments on matched MRs/PRs.

## Platform differences

| Aspect | GitLab | GitHub |
|---|---|---|
| CLI | `glab` | `gh` |
| Labels | `status::done` (double colon) | `status:done` (single colon) |
| Description file | `-F "description=@file"` | `--body-file "file"` |
| State changes | Single `glab api` call with `state_event` | Separate `gh issue close` / `gh issue reopen` |
| Label updates | `-f "labels=..."` (replaces all) | `--add-label` / `--remove-label` (targeted) |
| Boards | Created automatically | Skipped in v1 |
| Enterprise | `--hostname` on every command | `--hostname` on every command |

## After BMM updates

- **Skills** — update via `npx bmad-method install --custom-source https://github.com/jrevillard/bmad-issue-tracking`
- **TOML overrides** — no action needed (survive BMM updates)
- **Shared tasks** — no action needed

## Disabling

Set `issue_tracking.enabled: false` in `_bmad/bmm/config.yaml`.
