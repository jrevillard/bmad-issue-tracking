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
# Latest version (main branch)
npx bmad-method install --custom-source https://github.com/jrevillard/bmad-issue-tracking

# Specific version (e.g. 1.0.1)
npx bmad-method install --custom-source https://github.com/jrevillard/bmad-issue-tracking@1.0.1
```

This registers two skills as slash commands:
- `/bmad-bmm-issue-sync` — Sync sprint status to issues
- `/bmad-issue-tracking-setup` — Deploy TOML overrides and shared tasks (run once)

### 2. Run the setup skill

```
/bmad-issue-tracking-setup
```

This deploys TOML overrides to `_bmad/custom/`, shared tasks to `_bmad/_config/custom/`, and configures:
- **Platform** (GitLab or GitHub) — detected from git remote, with mismatch handling
- **Connection** (host and project) — always configured explicitly
- **Branch patterns** (PRD branch, story branches) — controls automatic branch and MR/PR creation

### 3. PRD key

`prd_key` is captured automatically when running `/bmad-create-prd` (via `activation_steps_append`). No manual configuration needed.

## What gets installed

### Skills (via BMAD installer)

Registered as slash commands in your IDE.

| Skill | Command | Purpose |
|---|---|---|
| Sync Issues | `/bmad-bmm-issue-sync` | Sync `sprint-status.yaml` to issues, mark draft PR ready |
| Setup | `/bmad-issue-tracking-setup` | One-time integration setup |

### TOML overrides (via setup)

Deployed to `_bmad/custom/`. Survive BMM updates automatically.

| Override file | Target workflow | Hook | Behavior |
|---|---|---|---|
| `bmad-create-prd.toml` | `create-prd` | `activation_steps_append`, `on_complete` | Captures `prd_key` at activation, creates PRD issue + PRD branch + draft PR/MR on completion |
| `bmad-create-architecture.toml` | `create-architecture` | `activation_steps_append`, `on_complete` | Switches to PRD worktree at activation, commits and pushes on completion |
| `bmad-create-ux-design.toml` | `create-ux-design` | `activation_steps_append`, `on_complete` | Switches to PRD worktree at activation, commits and pushes on completion |
| `bmad-create-epics-and-stories.toml` | `create-epics-and-stories` | `activation_steps_append`, `on_complete` | Switches to PRD worktree at activation, commits and pushes on completion |
| `bmad-create-story.toml` | `create-story` | `activation_steps_append`, `on_complete` | Sets up story worktree at activation, creates issue + MR on completion |
| `bmad-dev-story.toml` | `dev-story` | `activation_steps_append`, `on_complete` | Switches to story worktree at activation, posts summary, updates status |
| `bmad-code-review.toml` | `code-review` | `activation_steps_append`, `on_complete` | Switches to story worktree at activation, posts review, updates status |
| `bmad-sprint-planning.toml` | `sprint-planning` | `activation_steps_append`, `on_complete` | Switches to PRD worktree at activation, triggers full issue sync |
| `bmad-sprint-status.toml` | `sprint-status` | `activation_steps_append`, `on_complete` | Switches to PRD worktree at activation, triggers full issue sync |
| `bmad-edit-prd.toml` | `edit-prd` | `activation_steps_append`, `on_complete` | Switches to PRD worktree at activation, updates PRD issue description |
| `bmad-correct-course.toml` | `correct-course` | `activation_steps_append`, `on_complete` | Switches to PRD worktree at activation, updates issue descriptions for modified stories/epics/PRD |
| `bmad-check-implementation-readiness.toml` | `check-implementation-readiness` | `activation_steps_append`, `on_complete` | Switches to PRD worktree at activation, updates issue descriptions if artifacts were modified |
| `bmad-retrospective.toml` | `retrospective` | `activation_steps_append`, `on_complete` | Switches to PRD worktree at activation, creates issue with retrospective content |

> **Note:** All overrides require BMM 6.4.0+ (uniform customize.toml support across all BMM workflows).

### Shared custom tasks (via setup)

Copied to `_bmad/_config/custom/` — referenced by TOML `on_complete` hooks.

- `bmad-bmm-issue-sync.md` — Sync `sprint-status.yaml` to issues, manage labels, create branches and MRs

## Usage

### Sync sprint status to issues

```
/bmad-bmm-issue-sync
```

Creates/updates issues for all sprint entries, manages labels, reconciles statuses, marks draft PR ready when all epics are done.

## Branch strategy

When `branch_patterns` is configured in the setup:

| Event | Action |
|---|---|
| PRD created | PRD worktree created in activation + draft PR/MR (PRD → default branch) |
| Story created | Story worktree created in activation (from PRD) + issue + MR (story → PRD) |
| Story developed | Story worktree entered, changes committed |
| Story reviewed | Issue status updated, worktree exited (only if MR merged) |
| All epics done | Draft PR/MR marked as ready for review |

## Platform differences

| Aspect | GitLab | GitHub |
|---|---|---|
| CLI | `glab` | `gh` |
| Labels | `status::done` (double colon) | `status:done` (single colon) |
| Description file | `-F "description=@file"` | `--body-file "file"` |
| State changes | Single `glab api` call with `state_event` | Separate `gh issue close` / `gh issue reopen` |
| Label updates | `-f "labels=..."` (replaces all) | `--add-label` / `--remove-label` (targeted) |
| Boards | Created automatically | Skipped in v1 |
| Enterprise | `-R` on subcommands, `--hostname` on `glab api` only | `-R` on subcommands, `--hostname` on `gh api` only |

## After BMM updates

- **Skills** — update via `npx bmad-method install --custom-source https://github.com/jrevillard/bmad-issue-tracking`
- **TOML overrides** — no action needed (survive BMM updates)
- **Shared tasks** — no action needed

## Disabling

Set `issue_tracking.enabled: false` in `_bmad/custom/issue-tracking.yaml`.

## Configuration

The `issue_tracking` block in `_bmad/custom/issue-tracking.yaml` controls the integration:

```yaml
issue_tracking:
  enabled: true
  platform: gitlab  # or github
  host: gitlab.com  # always configured by setup
  project: group/project  # always configured by setup
  branch_patterns:
    prd: "feat/{prd_key}/prd"
    story: "feat/{prd_key}/{story_key}"
```

- **`platform`** — required. `gitlab` or `github`. Determines which CLI to use (`glab` / `gh`).
- **`host`** — required. The issue tracker host (e.g. `gitlab.com`, `github.com`, or a self-hosted instance).
- **`project`** — required. The project path (e.g. `my-org/my-repo`).
- **`branch_patterns.prd`** — required. Pattern for the PRD branch. Must contain `{prd_key}`.
- **`branch_patterns.story`** — required. Pattern for story branches. Must contain `{prd_key}` and `{story_key}`.

**Cross-platform scenario:** If your code is on GitLab but you want to track issues on GitHub (or vice versa), the setup skill detects the mismatch and asks for the issue tracker host and project explicitly.
