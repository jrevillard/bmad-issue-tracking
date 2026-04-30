---
name: bmad-bmm-issue-sync
description: 'Sync sprint-status.yaml entries to GitLab/GitHub Issues. Use when the user says "sync issues" or wants to push sprint status to the issue tracker.'
---

# Sync Sprint Status to Issues (GitLab or GitHub)

> Delegates to the structured workflow YAML at `issue-sync/prepare.yaml` and `issue-sync/sync.yaml`.
> Run `/bmad-issue-tracking-setup` to deploy the workflow files first.

## Prerequisites

- `glab` CLI (for GitLab) or `gh` CLI (for GitHub) installed and authenticated
- Repository has Issues enabled
- `sprint-status.yaml` exists at `{implementation_artifacts}/sprint-status.yaml`
- `prd_key` in `prd.md` frontmatter, or provided by user if absent

## Instructions

1. Prepare the issue tracker: `INCLUDE: issue-sync/prepare`
2. Sync all issues: `INCLUDE: issue-sync/sync`
3. The prepare step handles Steps 1-3 automatically:
   - Step 1: Platform detection and configuration
   - Step 2: Ensure all labels exist (static + dynamic PRD/epic labels) and board
   - Step 3: Create PRD issue if not exists
4. The sync step handles Steps 4-6 automatically:
   - Step 4: Sync all issues (create missing + reconcile statuses)
   - Step 5: Mark draft MR/PR ready when all epics are done
   - Step 6: Report sync summary
