# BMAD Issue Tracking

BMAD extension module that mirrors sprint tracking to GitLab Issues or GitHub Issues. Supports both cloud and self-hosted instances via their respective CLIs (`glab` / `gh`).

Uses BMAD's native TOML customization where available and `.patch` files for workflows not yet customizable.

## Prerequisites

- BMAD Method module (BMM) 6.3+ installed in your project
- `glab` CLI (GitLab) or `gh` CLI (GitHub) installed and authenticated
- Repository with Issues enabled

## Installation

### 1. Install the module via BMAD installer

```bash
npx bmad-method install --custom-source https://github.com/jrevillard/bmad-issue-tracking
```

This registers three skills as slash commands:
- `/bmad-bmm-issue-sync` — Sync sprint status to issues
- `/bmad-bmm-issue-link` — Link merged MRs/PRs to issues
- `/bmad-issue-tracking-setup` — Apply integration patches (run once)

### 2. Run the setup skill

```
/bmad-issue-tracking-setup
```

This applies TOML overrides, patches BMM workflow files, and configures the platform. You can also run the patch script manually:

```bash
bash skills/bmad-issue-tracking-setup/assets/patches/patch-bmm.sh --force
```

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
| Link MRs/PRs | `/bmad-bmm-issue-link` | Link merged MRs/PRs to issues |
| Setup | `/bmad-issue-tracking-setup` | One-time integration setup |

### TOML overrides (via setup)

Survive BMM updates automatically.

| Override file | Target workflow | Hook | Behavior |
|---|---|---|---|
| `_bmad/custom/bmad-create-story.toml` | `create-story` | `on_complete` | Creates issue when a story is created |
| `_bmad/custom/bmad-retrospective.toml` | `retrospective` | `on_complete` | Creates issue when a retrospective is saved |

### Patch files (via setup)

4 workflows don't have `customize.toml` yet ([BMAD issue #2303](https://github.com/bmad-code-org/BMAD-METHOD/issues/2303)).

| Patch file | Target | Change |
|---|---|---|
| `config-yaml.patch` | `bmm/config.yaml` | Adds `issue_tracking` config block |
| `*-code-review-*` | `code-review/` | Syncs status after review |
| `*-dev-story-*` | `dev-story/` | Syncs in-progress and review transitions |
| `*-sprint-planning-*` | `sprint-planning/` | Adds issue sync step |
| `*-sprint-status-*` | `sprint-status/` | Adds issue reconciliation |

### Shared custom tasks (via setup)

Copied to `_bmad/_config/custom/` — referenced by TOML `on_complete` hooks.

- `bmad-bmm-issue-sync.md` — Sync `sprint-status.yaml` to issues (GitLab or GitHub)
- `bmad-bmm-issue-link.md` — Link merged MRs/PRs to issues

## Usage

### Sync sprint status to issues

```
/bmad-bmm-issue-sync
```

Creates/updates issues for all sprint entries, manages labels, reconciles statuses.

### Link merged MRs/PRs to issues

```
/bmad-bmm-issue-link
```

Three-tier matching: pattern, AI context, manual.

## Platform differences

| Aspect | GitLab | GitHub |
|---|---|---|
| CLI | `glab` | `gh` |
| Labels | `status::done` (double colon) | `status:done` (single colon) |
| Description file | `-F "description=@file"` | `--body-file "file"` |
| Boards | Created automatically | Skipped in v1 |
| Enterprise | `--hostname` on every command | `--hostname` on every command |

## After BMM updates

- **Skills** — update via `npx bmad-method install --custom-source https://github.com/jrevillard/bmad-issue-tracking`
- **TOML overrides** — no action needed
- **Shared tasks** — no action needed
- **Patches** — re-run `/bmad-issue-tracking-setup` or `patch-bmm.sh`. If a patch fails, inspect with `git apply --stat`.

## Disabling

Set `issue_tracking.enabled: false` in `_bmad/bmm/config.yaml`.

## Migration path

As BMAD extends [Workflow Customization](https://docs.bmad-method.org) to all workflows ([issue #2303](https://github.com/bmad-code-org/BMAD-METHOD/issues/2303)), patches will be replaced by TOML overrides and removed from this module.
