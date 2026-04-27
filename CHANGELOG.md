# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[1.2.0]: https://github.com/jrevillard/bmad-issue-tracking/compare/v1.1.1...v1.2.0
[1.1.1]: https://github.com/jrevillard/bmad-issue-tracking/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/jrevillard/bmad-issue-tracking/compare/v1.0.1...v1.1.0
[1.0.1]: https://github.com/jrevillard/bmad-issue-tracking/compare/v1.0.0...v1.0.1
