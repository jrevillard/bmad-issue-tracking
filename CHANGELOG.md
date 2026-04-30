# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **BREAKING**: All BMM workflow overrides migrated from TOML pointers + markdown instructions to structured workflow YAML with INCLUDE sub-workflows
- `bmad-bmm-issue-sync/SKILL.md` simplified from 13KB markdown to thin pointer delegating to `issue-sync/prepare.yaml` + `issue-sync/sync.yaml`
- Issue sync split into `issue-sync/prepare.yaml` (steps 1-3) and `issue-sync/sync.yaml` (steps 4-6) — sprint-planning and sprint-status now only run steps 4-6
- `sprint-planning/complete.yaml` and `sprint-status/complete.yaml` replaced custom sync logic with `INCLUDE: issue-sync/sync`
- All `glab api --jq` replaced with `glab api | python3 -c "import json,sys; ..."` (glab has no --jq flag)
- All `| jq` removed entirely — zero jq dependency, python3 used for all JSON processing
- `gh api --paginate --jq` replaced with `gh api --paginate | python3 -c` (jq applies per-page, not concatenated)

### Added

- Structured workflow YAML language with 11 step types (SET, CHECK, RUN, WRITE, READ, LOOP, OUTPUT, INCLUDE, FILTER, STOP, CD)
- 14 new common sub-workflows: check-config, find-prd, find-issue, find-stories, create-issue, create-label, update-issue-status, update-issue-description, set-story-status, ensure-labels, ensure-dynamic-labels, ensure-board, sync-issues, mark-mr-ready
- 10 activation.yaml files — worktree setup and variable extraction before BMM runs
- 10 complete.yaml files — commit, push, issue/MR management after BMM runs
- 683 regression tests covering YAML syntax, CLI patterns, variable flow, include contracts, platform coverage, config requirements, Python compliance
- Recursive YAML parser in tests/conftest.py for parametrized test flattening

### Fixed

- `glab api --jq` flag does not exist on glab 1.53.0 — replaced with pipe to python3
- `glab mr list --json` flag does not exist — replaced with `--output json`
- `sys.stdin.read()` in ensure-dynamic-labels.yaml and mark-mr-ready.yaml — workflow variables are passed as sys.argv, not stdin
- `int(m.group(1))` crash in ensure-dynamic-labels.yaml — group(1) was `epic-3` (string), needed group(2) for the digit
- `gh issue edit --labels` does not exist on GitHub CLI — replaced with `--add-label`/`--remove-label`
- mark-mr-ready false positive when zero epic entries exist — added `epic_found` guard

## [1.3.0] - 2026-04-27

### Changed

- Story branch setup moved to activation steps (before BMM workflow) — the BMM workflow now creates story files directly in the story worktree, never on the PRD branch
- All workflows stay in their worktree after completion (instead of exiting) — the agent continues working from there; only code-review exits after MR merge

### Added

- Variable re-derivation fallback in on_complete blocks — if context is compacted between activation and on_complete, `{story_key}`, `{prd_branch}`, `{story_branch}` are re-derived from config and files
- create-story activation now asks for story key and creates/switches to story worktree before the BMM workflow runs

### Fixed

- create-story no longer commits on PRD branch — story files live only on story branches
- README override table: create-story now listed with `activation_steps_append` hook
- README branch strategy table updated to reflect new flow

## [1.2.0] - 2026-04-27

### Changed

- Config relocated from `_bmad/bmm/config.yaml` to `_bmad/custom/issue-tracking.yaml` — survives BMM updates that regenerate the BMM config
- Activation steps in create-story, dev-story, code-review now search for PRD branch via pattern matching when prd_key is not on the current branch (e.g. `git branch --list 'feat/*/prd'`)
- Setup auth check uses `--hostname $HOST` for self-hosted instances

### Fixed

- Missing `-R "$HOST/$OWNER/$REPO"` on `gh pr list` in create-prd.toml
- Missing closing backtick in sync skill config path references (2 occurrences)
- Stale `_bmad/bmm/config.yaml` reference in module-help.csv, README.md, and CLAUDE.md

### Improved

- Activation PRD branch search instruction now explicitly tells the agent to use `*` in place of `{prd_key}` when prd_key is unknown
- README Enterprise row updated to reflect actual CLI flag behavior (`-R` on subcommands, `--hostname` on api only)

## [1.1.1] - 2026-04-27

### Fixed

- `glab api` PUT requests for issue description now use `-F` (file upload) instead of `-f` (raw field) — descriptions were sent as literal file paths
- Replaced `--hostname` with `-R` on all `glab mr` subcommands (merge, create, list, update) — flag not supported outside `glab api`
- Replaced `[--hostname $HOST]` with `-R "$HOST/$OWNER/$REPO"` on all `gh` subcommands — flag only valid on `gh api` and `gh auth`
- Added missing `-R` flag on `gh pr merge`, `gh pr list`, and `gh pr ready` in sync task and code-review
- Specified exact cache path for TOML overrides in setup step 3 (was ambiguous)
- Defined `{default_branch}` resolution in sync task step 5 (was used without definition)
- Fixed misleading `--hostname` description in CLAUDE.md

## [1.1.0] - 2026-04-27

### Changed

- Standalone sync skill (`bmad-bmm-issue-sync`) is now the single source of truth — removed duplicate `shared-tasks/` directory
- Setup copies the sync skill directly to `_bmad/_config/custom/` instead of from a separate shared-tasks directory

### Fixed

- `create-story` now pushes the PRD branch after committing story file and sprint-status update
- `bmad-bmm-issue-link` removed from marketplace.json (skill was deleted in 1.0.1)
- Marketplace.json version aligned with module.yaml

### Improved

- Branch variable placeholders (`{prd_branch}`, `{story_branch}`) explicitly defined at first use in CLI commands
- MR direction (story → PRD) repeated in code-review merge step
- `story_key` to `epic_num`/`story_num` extraction clarified in create-story
- Guard messages reworded: "the workflow will resume" → "then continue these instructions"
- Removed dead `prd_parent_issue` config option from sync task (was never set or documented)
- Added CLAUDE.md with architectural guidance for future development

## [1.0.1] - 2026-04-26

### Added

- Git worktree-based branch management for all workflows (create-prd, create-story, dev-story, code-review)
- Automatic branch and MR/PR creation during PRD and story workflows
- Branch pattern configuration (`branch_patterns`) in setup (step 6b)
- `prd_key` capture during `create-prd` activation (persisted to PRD frontmatter)
- PRD issue and draft PR/MR creation on `create-prd` completion
- Story issue and MR creation on `create-story` completion
- Implementation summary comment posted on `dev-story` completion
- Code review findings posted as comment on `code-review` completion
- MR merge prompt in `code-review` (asks user, then merges if confirmed)
- Commit and push steps in `dev-story` and `code-review` workflows
- TOML overrides for `check-implementation-readiness`, `correct-course`, `edit-prd`, and `retrospective`
- Uniform `branch_patterns` config guard across all activation hooks and `on_complete` hooks
- Conditional worktree cleanup: remove after merge, keep otherwise
- Optional host/project config for cross-platform issue tracking (e.g. code on GitLab, issues on GitHub)

### Changed

- Default PRD branch pattern changed from `feat/{prd_key}` to `feat/{prd_key}/prd` to avoid git naming conflict with story branches
- Migrated from patches to TOML overrides (requires BMM 6.4.0+)
- Sync task no longer creates branches or MRs (moved to create-story workflow)
- Minimum BMM version bumped to 6.4.0

### Fixed

- `glab label create` used instead of `glab api` for label creation
- `--raw-field` flag used for `glab label create` (form-data fails on self-hosted instances)
- Setup step 5 always asks for host/project when mismatch detected
- `prd_key` captured during activation instead of `on_complete`
- Epics read from `epics.md` instead of `epic-N-*.md`

### Removed

- `bmad-bmm-issue-link` skill (obsolete, sync task handles MR creation)
- Known issue workaround for git branch naming conflict (fixed by PRD pattern change)

[Unreleased]: https://github.com/jrevillard/bmad-issue-tracking/compare/v1.3.0...HEAD
[1.3.0]: https://github.com/jrevillard/bmad-issue-tracking/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/jrevillard/bmad-issue-tracking/compare/v1.1.1...v1.2.0
[1.1.1]: https://github.com/jrevillard/bmad-issue-tracking/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/jrevillard/bmad-issue-tracking/compare/v1.0.1...v1.1.0
[1.0.1]: https://github.com/jrevillard/bmad-issue-tracking/compare/v1.0.0...v1.0.1
