---
name: bmad-bmm-issue-sync
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
3. Execute the sync workflow: `_bmad/_config/custom/workflows/issue-sync/sync.yaml`

## Unattended usage (after a bmad-loop run)

The sync is fully silent — no prompts, no PRD worktree required (`common/find-prd-key` resolves `prd_key` from `prd.md` on the current tree; `common/mark-mr-ready` is a no-op when no MR exists). Run it after a `bmad-loop run` to mirror the sprint status bmad-loop maintained, then `git push origin main` to publish the local merge-back. See "BMAD Loop integration" in the README.
