# BMAD Issue Tracking

BMAD extension module that mirrors sprint tracking to GitLab Issues or GitHub Issues. Supports both cloud and self-hosted instances via their respective CLIs (`glab` / `gh`).

Uses BMAD's native TOML customization where available and `.patch` files for workflows not yet customizable.

## Prerequisites

- BMAD Method module (BMM) 6.3+ installed in your project
- `glab` CLI (GitLab) or `gh` CLI (GitHub) installed and authenticated
- Repository with Issues enabled

## Installation

### 1. Copy module identity

```bash
cp module.yaml _bmad/
```

### 2. Run the install script

```bash
./patches/patch-bmm.sh
```

Or specify the project root:

```bash
./patches/patch-bmm.sh /path/to/your/project
```

The script is **idempotent** — safe to run multiple times.

### 3. Configure platform and PRD key

Edit `_bmad/bmm/config.yaml` (injected by the install script):

```yaml
issue_tracking:
  enabled: true
  platform: gitlab  # or "github"
```

Add `prd_key` to your PRD frontmatter:

```markdown
---
prd_key: my-initiative
---
```

## What gets installed

### TOML overrides (native BMAD customization)

Survive BMM updates automatically.

| Override file | Target workflow | Hook | Behavior |
|---|---|---|---|
| `_bmad/custom/bmad-create-story.toml` | `create-story` | `on_complete` | Creates issue when a story is created |
| `_bmad/custom/bmad-retrospective.toml` | `retrospective` | `on_complete` | Creates issue when a retrospective is saved |

### Patch files (pending BMAD customization support)

4 workflows don't have `customize.toml` yet ([BMAD issue #2303](https://github.com/bmad-code-org/BMAD-METHOD/issues/2303)).

| Patch file | Target | Change |
|---|---|---|
| `config-yaml.patch` | `bmm/config.yaml` | Adds `issue_tracking` config block |
| `*-code-review-*` | `code-review/` | Syncs status after review |
| `*-dev-story-*` | `dev-story/` | Syncs in-progress and review transitions |
| `*-sprint-planning-*` | `sprint-planning/` | Adds issue sync step |
| `*-sprint-status-*` | `sprint-status/` | Adds issue reconciliation |

### Shared custom tasks

Copied to `_bmad/_config/custom/` — survive BMM updates.

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

- **TOML overrides** — no action needed
- **Shared tasks** — no action needed
- **Patches** — re-run `./patches/patch-bmm.sh`. If a patch fails, inspect with `git apply --stat`.

## Disabling

Set `issue_tracking.enabled: false` in `_bmad/bmm/config.yaml`.

## Migration path

As BMAD extends [Workflow Customization](https://docs.bmad-method.org) to all workflows ([issue #2303](https://github.com/bmad-code-org/BMAD-METHOD/issues/2303)), patches will be replaced by TOML overrides and removed from this module.
