# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

BMAD module that integrates sprint tracking with GitLab/GitHub Issues. It's not a runnable application — it's a set of TOML overrides and Skills-as-modules folders consumed by the new BMad installer (each `<skill>/module-manifest.toml` declares `module = "issue-tracking"`).

Requires BMM 6.12.0+ (the flat per-skill install layout `_bmad/{method,toolbox,...}/` replaces the legacy `_bmad/{bmm,bmb,cis,core}/` subdirectories from 6.12.0 onward; BMad adopted the Skills-as-modules format with this version).

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

## Step-authoring rules the test suite enforces

These two are not style preferences — `tests/` fails a workflow that breaks them, and both
have caught real defects:

- **No raw shell variables in any step.** `test_command_patterns.py::test_no_unresolved_shell_vars`
  rejects `$var` and `${var}` in every step's `raw_value` (only the awk built-in `NF` is
  allowed). Variables are passed through the workflow language's `{placeholder}` scope —
  which also means **there is no supported environment-variable channel into a workflow**,
  so a caller cannot signal behaviour that way. `test_variable_flow.py` additionally flags
  a `${X:-default}` colon as a hardcoded label separator, so even the shell-default idiom
  is doubly unavailable. **If a caller must influence a workflow, use a file** (see
  "Caller negotiation" below) — never an env var.
- **Every `common/*.yaml` needs the four-line header** — Purpose, Input variables, Output
  variables, **Side effects**. `test_include_contracts.py` requires the Side effects line
  even when the answer is "none" (`check-config` and `find-issue` both say
  `Side effects: none`). Four MR atomics shipped without it and left the suite red; only
  the first was ever reported, because `assert` aborts the test on the first failure.

## Adding or removing a workflow file

`skills/bmad-issue-tracking-setup/SKILL.md` carries an explicit per-file verify list
(~lines 88-142) of every file the setup step must have copied. Adding
`common/post-build-dispatch-auto.yaml` required adding it there; forgetting leaves the
installer green while the file is missing in the consumer.

## Which producer wrote the review section (post-dev-complete review-finish)

Three producers reach `common/post-dev-complete.yaml`, and they disagree about the
`## Review Triage Log` / `### Review Findings` section:

| Producer | Section | How it is reached |
|---|---|---|
| `bmad-build-auto` | appends a `### <date> — Review pass` entry on EVERY pass | its `on_complete` hook |
| `bmad-build` | one row PER FINDING → nothing on a clean review | `post-build-dispatch-interactive.yaml` |
| `bmad-code-review` | nothing at all on a clean review | its `on_complete` hook → `post-dev-complete-review-finish.yaml` |

Only `bmad-build-auto` guarantees a section, so only there does a missing/empty section
mean "the review never ran". `common/post-build-dispatch-auto.yaml` — used solely by the
`bmad-build-auto` hook — sets `review_producer="bmad-build-auto"`, and post-dev-complete
halts on an absent/empty section **only** when that flag is present; every other flow
warns and continues to the CI gate.

Two things NOT to do here, both tried and reverted:
- **`allow_merge` cannot discriminate.** It marks the interactive merge prompt and is
  unset on BOTH the unattended and the `bmad-code-review` paths, so keying the halt on it
  blocked clean `bmad-code-review` stories.
- **Never let a sentinel reach `review_section`.** The block after the sentinels checks
  `empty review_section` and posts whatever it holds. A warn branch that does not clear
  the variable posts the literal string `SPEC_NO_REVIEW_SECTION` as the issue comment —
  while its own message claims no comment was posted.

Halt only on a missing spec FILE (`SPEC_NOT_FOUND`): that case is unambiguous and is the
one that actually killed story 2-1, whose phase read the spec from an invented path
(`{implementation_artifacts}/{story_key}.md`) with no error handling. The spec is now read
from `{spec_file}` — the path the runtime resolves, per `bmad-workflow-lang.md:443-455`
and BMAD's `tools/skill-validator.md:37` — with the legacy path kept as a second
candidate so existing consumers do not regress.

## Caller negotiation (both current channels)

A caller cannot pass a variable into a workflow (see the step-authoring rules), so when a
caller needs different behaviour it declares that through something a step CAN read:

| Channel | Set by | Read by | Effect |
|---|---|---|---|
| `review_producer="bmad-build-auto"` | `common/post-build-dispatch-auto.yaml`, used only by the bmad-build-auto hook | post-dev-complete review-finish | halt on an absent/empty review section (the only producer that guarantees one) |
| `<worktree>/.bmad-ci-handled` (file) | the caller, before dispatching | `common/post-build-dispatch-auto.yaml`, at its FIRST step | the WHOLE chain does nothing — no `check-config`, no spec read, no routing, no phase |

The marker file exists because a caller (bmad-build-converge) does the whole chain itself —
it pushes, ensures the MR, polls the pipeline and merges — so running the module's chain too
is a pure duplicate, and its CI wait re-introduces inside every build dispatch the delay the
convergence loop deliberately removed (measured 47-305 s per dispatch in the run traces).
Absent marker → unchanged behaviour, so bmad-loop is untouched and still gets the
`ci-status.json` its `[verify]` requires. The guard lives at the ENTRY POINT
(`post-build-dispatch-auto.yaml`, before the INCLUDE) precisely so nothing downstream runs;
placing it later would leave `check-config`, the spec read and the routing executing.

Convention for any future channel: a **file or a workflow variable set by a wrapper we
ship**, never a shell variable, and always with the "absent → previous behaviour"
property so consumers that know nothing about it cannot regress.
