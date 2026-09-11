---
name: bmad-issue-tracking-sync
description: 'Sync sprint-status.yaml entries to GitLab/GitHub Issues. Use when the user says "sync issues" or wants to push sprint status to the issue tracker.'
---

# Sync Sprint Status to Issues (GitLab or GitHub)

## Prerequisites

- `glab` CLI (for GitLab) or `gh` CLI (for GitHub) installed and authenticated
- Repository has Issues enabled
- `sprint-status.yaml` exists at `{implementation_artifacts}/sprint-status.yaml`
- `prd_key` in `prd.md` frontmatter (required — the sync fails closed if absent; run `/bmad-issue-tracking-setup` if not set)
- Workflow files deployed by `/bmad-issue-tracking-setup` in `_bmad/_config/custom/workflows/`

## Instructions

1. Read `_bmad/_config/custom/bmad-workflow-lang.md` for the workflow language specification.
2. Execute the prepare workflow: `_bmad/_config/custom/workflows/issue-sync/prepare.yaml`
3. **Step 2c — scoped MR ops (preferred for orchestrator hooks):**
   a. Route on `BMAD_MR_ACTION` env var:
      - `BMAD_MR_ACTION=ensure-mr` → require env `BMAD_MR_SOURCE_BRANCH`, `BMAD_MR_TARGET_BRANCH`, `BMAD_MR_TITLE`, `BMAD_MR_DESCRIPTION_FILE`, `BMAD_MR_REPO`; then `INCLUDE: common/ensure-mr`.
      - `BMAD_MR_ACTION=find-mr` → require `BMAD_MR_SOURCE_BRANCH`, `BMAD_MR_REPO`; then `INCLUDE: common/find-mr`.
      - `BMAD_MR_ACTION=get-mr-pipeline` → require `BMAD_MR_IID`; then `INCLUDE: common/get-mr-pipeline`.
      - `BMAD_MR_ACTION=get-failed-jobs` → require `BMAD_PIPELINE_ID`; then `INCLUDE: common/get-failed-jobs`.
      - `BMAD_MR_ACTION=merge-mr` → require `BMAD_MR_IID`, `BMAD_MR_SQUASH` (default "false"); then `INCLUDE: common/merge-mr`.
   b. Same env-var-driven parallel-safe pattern as Step 2a — no platform-specific CLI.
   c. Cleanup: the Skill caller's agent does `rm -f` on `BMAD_MR_DESCRIPTION_FILE` after Skill returns (best-effort).
4. **Step 2d — scoped issue ops (preferred for orchestrator hooks):**
   a. Route on `BMAD_ISSUE_ACTION` env var (skip when env var unset — Step 5 sync.yaml runs as normal):
      - `BMAD_ISSUE_ACTION=set-status` → require env `BMAD_ISSUE_KEY` (the issue label text — works for story keys like `1-3-login-form` OR epic keys like `epic-1` / `1`), `BMAD_ISSUE_PRD_KEY`, `BMAD_ISSUE_NEW_STATUS` (e.g. `in-progress`, `review`, `done`), `BMAD_ISSUE_CLOSE` (default `false`); then `INCLUDE: common/set-story-status` (the atomic's `story_key` input accepts any issue label — the atomic sets `search_text = "{story_key}"` then INCLUDEs find-issue, so epic keys work because find-issue searches by text not by issue type).
      - `BMAD_ISSUE_ACTION=find` → require `BMAD_ISSUE_KEY`, `BMAD_ISSUE_PRD_KEY`; then `SET: { variable: search_text, value: "{BMAD_ISSUE_KEY}" }` and `INCLUDE: common/find-issue`. Output: `{ issue_id }` (the env label text maps to find-issue's `search_text` input — not to `story_key`).
   b. Same env-var-driven parallel-safe pattern as Step 2a/2c — no platform-specific CLI.
   c. Cleanup: none (no temp files for issue ops).
5. Execute the sync workflow: `_bmad/_config/custom/workflows/issue-sync/sync.yaml`

## Unattended usage (after a bmad-loop run)

The sync is fully silent — no prompts, no PRD worktree required (`common/find-prd-key` resolves `prd_key` from `prd.md` on the current tree; `common/mark-mr-ready` is a no-op when no MR exists). Run it after a `bmad-loop run` to mirror the sprint status bmad-loop maintained, then `git push origin main` to publish the local merge-back. See "BMAD Loop integration" in the README.
