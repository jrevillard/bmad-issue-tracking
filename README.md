# BMAD Issue Tracking

BMAD module that mirrors sprint tracking to GitLab Issues or GitHub Issues. Supports both cloud and self-hosted instances via their respective CLIs (`glab` / `gh`).

Uses native BMad TOML customization for workflow integrations. Ships as a Skills-as-modules module (manifest declares `module = "bmad-issue-tracking"`).

## Prerequisites

- BMAD Method module (BMM) 6.12.0+ installed in your project
- `glab` CLI (GitLab) or `gh` CLI (GitHub) installed and authenticated
- Repository with Issues enabled
- `uv` (mandatory from BMM 6.12.0+)

## Architecture

The module plugs into BMM via two TOML hooks per target workflow:

- **`activation_steps_append`** — runs *before* the BMM workflow: sets up the worktree, resolves variables (`prd_key`, `story_key`, branch patterns), captures context.
- **`on_complete`** — runs *after* the BMM workflow: commits, pushes, creates/updates issues, manages MRs, posts comments.

The TOML files in `assets/custom/` are pure pointers — they reference workflow YAML files in `assets/workflows/` (deployed to `_bmad/_config/custom/workflows/`) that carry the actual logic. No business logic lives in TOML.

For the full architecture — branch/MR direction table, platform differences, step-authoring rules, caller-negotiation channels, bmad-loop integration design — see [CLAUDE.md](./CLAUDE.md).

## CI integration

The module participates in your CI pipeline via two layers:

- **`common/wait-for-green-ci.yaml`** — the on_complete hook polls the MR/PR pipeline (via `common/get-mr-pipeline.yaml` + `common/get-failed-jobs.yaml`) and blocks until green.
- **`ci-status.sh`** — the bmad-loop `[verify]` command (deployed to `.bmad-loop/ci-status.sh` by the setup skill). Reads the latest `ci-status.json` written by the unified workflow; exits 0 (green) or 1 (red, with diagnostic). The intelligent work (polling, log parsing, distinguishing flaky from real) is done by the on_complete hook — `ci-status.sh` is a fast, deterministic file-read.

In the manual flow (`/bmad-build`), the hook blocks the workflow on CI. In the bmad-loop flow, a red CI triggers an automatic repair session (re-invoke `bmad-build-auto` with the diagnostic) up to `max_dev_attempts` before deferring the story.

## Installation

### 1. Install BMad core first (one-time per project)

The issue-tracking module extends a project that already has BMad set up:

```bash
npx skills add bmad-code-org/BMAD-METHOD
```

Then open your coding tool in the project and ask the `bmad` skill to run `bmad setup` (this materializes `_bmad/` in your project, including `bmm` ≥ 6.12.0).

### 2. Add the issue-tracking module

From the project root:

```bash
# Latest (default branch)
npx skills add jrevillard/bmad-issue-tracking
```

The installer reads each `skills/<name>/module-manifest.toml`; both declare `module = "bmad-issue-tracking"`. After install, two slash commands become available:

- `/bmad-issue-tracking-sync` — Sync sprint status to issues
- `/bmad-issue-tracking-setup` — Deploy TOML overrides and shared tasks (run once)

> **Pinning to a release:** the skills CLI treats `@<ref>` after the package name as a *skill name filter*, not a git ref — `npx skills add jrevillard/bmad-issue-tracking@v3.0.0` looks for a skill *named* `v3.0.0`. For release-tag installs, the GitHub URL form is the only reliable syntax (see [Development install](#development-install)).

### 3. Run the setup skill

```
/bmad-issue-tracking-setup
```

This deploys TOML overrides to `_bmad/custom/`, shared tasks to `_bmad/_config/custom/`, and configures:
- **Platform** (GitLab or GitHub) — detected from git remote, with mismatch handling
- **Connection** (host and project) — always configured explicitly
- **Branch patterns** (PRD branch, story branches) — controls automatic branch and MR/PR creation

### 4. PRD key

`prd_key` is captured automatically when running `/bmad-create-prd` (via `activation_steps_append`). No manual configuration needed.

## Development install

For contributors testing branches or local edits before a release is tagged. The skills CLI accepts two non-default forms in addition to `owner/repo`. Both forms ship only the skill folders — to actually deploy TOML overrides, workflow YAMLs, and the bmad-loop plugin into your project's `_bmad/`, you must still run `/bmad-issue-tracking-setup` afterwards (same as the production flow, see step 3 above).

### Install from a GitHub branch

Use the GitHub URL form with `/tree/<branch>`:

```bash
npx skills add https://github.com/jrevillard/bmad-issue-tracking/tree/skills-as-modules
```

The CLI clones the branch (not the default branch), so each `<skill>/module-manifest.toml` is read from that ref. Useful to validate a release-candidate branch before tagging.

### Install from a local clone

Point the CLI at an absolute path on disk. No commit or push required — the CLI reads whatever is currently on the filesystem:

```bash
npx skills add /absolute/path/to/bmad-issue-tracking
```

Handy when iterating on `<skill>/module-manifest.toml`, `references/help.md`, or `scripts/`. Re-run after each edit so the symlinked `.agents/skills/<skill>/` reflects the latest state.

### Caveats for both dev installs

- `npx skills update` won't roll either form forward to a tagged release — you'll need to remove the dev install (`npx skills remove`) and reinstall via the production command.
- The `bmad setup` doctor's `state: "blocked"` for the `issue-tracking` module is *expected* until you publish a tag matching the manifest's `version`. The install itself is healthy — only the release comparability check fails.

## Development setup

This repo ships **only this module's two skills** (`bmad-issue-tracking-setup`,
`bmad-issue-tracking-sync`). BMM core is NOT colocated here.

To test the install flow end-to-end, use a throwaway consumer project — never
reinstall BMM into this repo:

```bash
mkdir /tmp/bmad-issue-tracking-consumer
cd /tmp/bmad-issue-tracking-consumer
npx skills add bmad-code-org/BMAD-METHOD
npx skills add /home/jerome/git_projects/bmad-issue-tracking   # this repo
# picker lists exactly 2 skills
```

## What gets installed

### Skills (via BMAD installer)

Registered as slash commands in your IDE.

| Skill | Command | Purpose |
|---|---|---|
| Sync Issues | `/bmad-issue-tracking-sync` | Sync `sprint-status.yaml` to issues, mark draft PR ready |
| Setup | `/bmad-issue-tracking-setup` | One-time integration setup |

### TOML overrides (via setup)

Deployed to `_bmad/custom/`. Survive BMM updates automatically.

| Override file | Target workflow | Hook | Behavior |
|---|---|---|---|
| `bmad-create-prd.toml` | `create-prd` | `activation_steps_append`, `on_complete` | Captures `prd_key` at activation, creates PRD issue + PRD branch + draft PR/MR on completion. Superseded by `bmad-prd.toml` |
| `bmad-prd.toml` | `bmad-prd` | `activation_steps_append`, `on_complete` | Unified PRD override: detects create/update/validate intent, replaces `bmad-create-prd.toml` and `bmad-edit-prd.toml` |
| `bmad-create-architecture.toml` | `create-architecture` | `activation_steps_append`, `on_complete` | Switches to PRD worktree at activation, commits and pushes on completion |
| `bmad-ux.toml` | `bmad-ux` | `activation_steps_append`, `on_complete` | Switches to PRD worktree at activation, commits and pushes on completion. Replaces `bmad-create-ux-design.toml` (skill removed in BMM 6.12.0) |
| `bmad-create-epics-and-stories.toml` | `create-epics-and-stories` | `activation_steps_append`, `on_complete` | Switches to PRD worktree at activation, commits and pushes on completion |
| `bmad-create-story.toml` | `create-story` | `activation_steps_append`, `on_complete` | Sets up story worktree at activation, creates issue + MR on completion (shim — deprecated upstream, `bmad-build` is the official path) |
| `bmad-dev-story.toml` | `dev-story` | `activation_steps_append`, `on_complete` | Switches to story worktree at activation, posts summary, updates status (shim — deprecated upstream, `bmad-build` is the official path) |
| `bmad-code-review.toml` | `code-review` | `activation_steps_append`, `on_complete` | Switches to story worktree at activation, posts review, updates status |
| `bmad-sprint-planning.toml` | `sprint-planning` | `activation_steps_append`, `on_complete` | Switches to PRD worktree at activation, triggers full issue sync |
| `bmad-sprint-status.toml` | `sprint-status` | `activation_steps_append`, `on_complete` | Switches to PRD worktree at activation, triggers full issue sync (consolidated into `bmad-sprint-planning` in BMM 6.12.0, retained as shim alias) |
| `bmad-edit-prd.toml` | `edit-prd` | `activation_steps_append`, `on_complete` | Switches to PRD worktree at activation, updates PRD issue description. Superseded by `bmad-prd.toml` |
| `bmad-correct-course.toml` | `correct-course` | `activation_steps_append`, `on_complete` | Switches to PRD worktree at activation, updates issue descriptions for modified stories/epics/PRD |
| `bmad-retrospective.toml` | `retrospective` | `activation_steps_append`, `on_complete` | Switches to PRD worktree at activation, creates issue with retrospective content |

> **Note:** All overrides require BMM 6.12.0+ (uniform customize.toml support across all BMM workflows; targets the 6.12.0 skill set).

### Shared custom tasks (via setup)

Copied to `_bmad/_config/custom/` — referenced by TOML `on_complete` hooks.

- `bmad-workflow-lang.md` — the workflow language specification the TOML hooks reference
- `workflows/issue-sync/` — `prepare.yaml` (platform, labels, board, PRD issue) and `sync.yaml` (sync issues, mark MR ready, summary)

## Usage

### Sync sprint status to issues

```
/bmad-issue-tracking-sync
```

Creates/updates issues for all sprint entries, manages labels, reconciles statuses, marks draft PR ready when all epics are done.

## Issue titles

Issues created by the module follow a fixed naming convention:

| Type | Title |
|------|-------|
| PRD | `PRD: <prd-key>` |
| Story | `Story 1.4: Login Form` |
| Epic | `Epic 1: Authentication` |
| Retrospective | `Retrospective: Epic 1` |

Story and epic titles are derived from the planning artifacts created by BMM workflows.

## Branch strategy

When `branch_patterns` is configured in the setup:

| Event | Action |
|---|---|
| PRD created | PRD worktree created in activation + draft PR/MR (PRD → default branch) |
| Story created | Story worktree created in activation (from PRD) + issue + MR (story → PRD) |
| Story developed | Story worktree entered, changes committed |
| Story reviewed | Issue status updated, worktree exited (only if MR merged) |
| All epics done | Draft PR/MR marked as ready for review |

## BMAD Loop integration

The module is compatible with [`bmad-loop`](https://github.com/bmad-code-org/bmad-loop) (deterministic orchestrator that drives `bmad-build-auto` per story in isolated worktrees). bmad-loop is the single writer of `sprint-status.yaml`; the module mirrors it to issues. **Zero user interaction** during the run.

**Prerequisites:** bmad-loop ≥ 0.9.0, BMM ≥ 6.12.0, `sprint-status.yaml` from `bmad-sprint-planning`.

**Flow:**

1. `bmad-loop run` — each story is implemented/reviewed/verified in its own worktree and merged back locally. At the end of every `bmad-build-auto` session, the skill executes its `on_complete` hook (from `bmad-build-auto.toml`), which runs `common/post-build-dispatch.yaml` → `common/post-dev-complete.yaml`. This unified workflow handles the full lifecycle for the story:
   - **dev-finish phase** (spec status `in-review` / `in-progress`): pushes the code, waits for CI (`common/wait-for-green-ci.yaml`), writes `ci-status.json` (`common/write-ci-status.yaml`), ensures the issue + trace MR exist (`common/ensure-issue.yaml` / `common/ensure-mr.yaml`), and updates the issue status.
   - **review-finish phase** (spec status `done`): commits review modifications, pushes, waits for CI, writes `ci-status.json`, posts the review findings comment, and mirrors the story to its issue (status label, result comment, MR link).
   - **`ci-status.sh`** (`[verify]` command): reads `ci-status.json` written by the unified workflow. A **red CI fails the verify command** (with rich diagnostic), and bmad-loop runs a feedback-driven repair session (re-invoking `bmad-build-auto` with the diagnostic as feedback) — the story is **auto-fixed and re-verified**, up to `max_dev_attempts`, before the merge-back. A **missing `ci-status.json` also fails** (fixable) — the on_complete hook did not write it. Only a budget-exhausted CI defers the story (`bmad-loop resolve` to recover). No bmad-loop plugins are needed — the `on_complete` hook drives everything.
2. `/bmad-issue-tracking-sync` — unattended safety net: mirrors the updated `sprint-status.yaml` to issues (labels, statuses, close `done`), no worktree required, no prompts.
3. `git push origin main` — the local merge-back is never pushed by bmad-loop.

**Status mapping** (bmad-loop values → module labels):

| bmad-loop sprint-status | Issue |
|---|---|
| `backlog` | `status::backlog` |
| `ready-for-dev` | `status::ready-for-dev` |
| `in-progress` | `status::in-progress` |
| `review` | `status::review` |
| `awaiting-operator` | `status::awaiting-operator` (issue stays **open** — external action pending, confirm with `bmad-loop confirm`) |
| `done` | `status::done` + issue closed |

**Execution trace:** the unified workflow's `ensure-mr.yaml` ensures a trace MR/PR exists per story (left open) — a CI vehicle and the story's execution trace. After the local merge-back is pushed to the target branch, GitLab auto-marks it merged, keeping the story's diff and pipeline as a durable record. On GitHub there is no auto-detection of an out-of-band merge, so the trace PR stays open; close it with `gh pr close <number>` when the story is `done` if you want it tidied.

## Migration from ci-wait.sh (if upgrading)

If you're upgrading from a version that used `ci-wait.sh`:
1. Re-run `/bmad-issue-tracking-setup` — it will deploy `ci-status.sh` and update `policy.toml`
2. Delete the old `ci-wait.sh`: `rm .bmad-loop/ci-wait.sh`
3. If you previously installed the `story-track-dev` / `story-track-review` bmad-loop plugins (now removed — superseded by the `bmad-build-auto.toml` `on_complete` hook): delete them with `rm -rf .bmad-loop/plugins/story-track-dev .bmad-loop/plugins/story-track-review` and remove them from `[plugins] enabled` in `.bmad-loop/policy.toml`.

The architecture is simpler: at the end of every `bmad-build-auto` session, the skill's `on_complete` hook (from `bmad-build-auto.toml`) runs `common/post-build-dispatch.yaml` → `common/post-dev-complete.yaml` (dev-finish / review-finish), which pushes code + waits CI + writes `ci-status.json` + ensures issue/MR + tracks issue. `ci-status.sh` (verify command) reads the latest `ci-status.json`. No polling or API calls in the shell script — the workflow does the polling via `common/wait-for-green-ci.yaml`.

**Limits (by design):** no MR discussion threads (the MR is a CI vehicle + trace, not a review conversation); `mark-mr-ready` is not used in this flow.

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

- **Skills** — update with `npx skills update`, then run `bmad` skill → `bmad doctor` (verifies the runtime). Re-run `/bmad-issue-tracking-setup` to refresh the deployed TOML/YAML assets in your `_bmad/custom/` and `_bmad/_config/custom/workflows/` trees.
- **TOML overrides** — no action needed (survive BMM updates unless we rename a workflow).
- **Shared tasks** — no action needed

## Disabling

Set `issue_tracking.enabled: false` in `_bmad/custom/issue-tracking.yaml`.

## Troubleshooting

**`bmad doctor` reports `state: "blocked"` for `issue-tracking`.** Expected until a tag matching the manifest's `version` is published. The install itself is healthy — only the release comparability check fails. (Dev installs always show this.)

**`/bmad-issue-tracking-setup` says "platform mismatch".** Your git remote (origin) and issue tracker are on different platforms (e.g. code on GitLab, issues on GitHub). The setup skill detects the mismatch and asks for the issue tracker host and project explicitly. The `git_platform` is set from the remote; `platform` is set from your answer. Issue ops use `platform`; MR/PR ops use `git_platform`. See [CLAUDE.md § Platform differences](./CLAUDE.md#platform-differences).

**Stories appear in the wrong issue.** Parallel PRDs collide on story keys (`1-3-login-form` in two PRDs). `common/find-issue.yaml` is scoped by `prd_key` — pass it explicitly from the workflow (`prd_key` is captured during PRD activation and re-derived from `prd.md` in unattended flows).

**`/bmad-issue-tracking-sync` prompts for `prd_key`.** You're running it without a PRD worktree. Use `common/find-prd-key.yaml` (auto-resolves from `prd.md` at the repo root, fails closed) or pass `prd_key` via the workflow variable scope. The bmad-loop flow runs unattended — see [CLAUDE.md § bmad-loop flow](./CLAUDE.md#bmad-loop-flow-unattended).

**`ci-status.json` missing on disk.** The on_complete hook didn't run — typically because the build session was interrupted before reaching the hook. Re-run the build to regenerate. The `ci-status.sh` verify treats missing `ci-status.json` as fixable (rc=1), so bmad-loop retries via a repair session rather than escalating.

**`prd_key` is empty in `_bmad/custom/issue-tracking.yaml`.** Normal for new installs — it's captured automatically the first time `/bmad-create-prd` (or `bmad-prd` with create intent) runs via `activation_steps_append`. Not a bug.

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

**Cross-platform scenario:** If your code is on GitLab but you want to track issues on GitHub (or vice versa), the setup skill detects the mismatch and asks for the issue tracker host and project explicitly. The `git_platform` (from the remote) drives MR/PR ops; the `platform` (from your answer) drives issue ops.

## License

Released under the MIT License. A `LICENSE` file should accompany releases — if you cloned this repo and it is missing, request it from the maintainer or open an issue.
