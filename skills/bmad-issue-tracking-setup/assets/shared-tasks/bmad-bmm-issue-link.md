---
name: bmad-bmm-issue-link
description: 'Add cross-references between merged MRs/PRs and their corresponding issues. Use when the user says "link MRs" or wants to connect merged work to issues.'
---

# Cross-Reference Merged MRs/PRs to Issues

> Shared custom BMAD task — adds comments on merged MRs/PRs referencing their corresponding issues.
> Reads `issue_tracking.platform` from config to pick the CLI.
>
> **Important:** Neither GitLab nor GitHub provides an API to programmatically link MRs/PRs to Issues.
> This task uses **comment-based cross-referencing** instead: it posts a comment on each matched MR/PR
> referencing the related issue (e.g., "Related to #42"). This creates a visible link without side effects
> (does not auto-close the issue).

## Prerequisites

- `glab` or `gh` CLI authenticated
- Issues already synced via `/bmad-bmm-issue-sync`
- `prd_key` in `prd.md` frontmatter

## Platform Detection

Read `issue_tracking.platform` from `_bmad/bmm/config.yaml`.

| Aspect | GitLab | GitHub |
|---|---|---|
| Fetch merged MRs | `glab api --paginate "projects/$PROJECT_ID/merge_requests?state=merged&per_page=100" --hostname $HOST` | `gh api --paginate "repos/$OWNER/$REPO/pulls?state=closed&per_page=100" --hostname $HOST --jq '.[] \| select(.merged_at != null)'` |
| Fetch merged PRs | (same as above) | (same as above) |
| Add comment | `glab api --method POST "projects/$PROJECT_ID/merge_requests/$IID/notes" --hostname $HOST -F "body=@/tmp/comment.md"` | `gh issue comment {number} --body-file "/tmp/comment.md" -R "$OWNER/$REPO" [--hostname $HOST]` |
| List comments | `glab api "projects/$PROJECT_ID/merge_requests/$IID/notes" --hostname $HOST --paginate` | `gh api "repos/$OWNER/$REPO/issues/{number}/comments" --hostname $HOST --paginate` |
| Search issues | `glab api --paginate "projects/$PROJECT_ID/issues?search=...&labels=...&state=all&per_page=100" --hostname $HOST` | `gh api --paginate "repos/$OWNER/$REPO/issues?state=all&per_page=100&labels=..." --hostname $HOST` |

**Note on GitHub merged PRs:** GitHub has no `state=merged` filter for the pulls API. Use `state=closed` and filter by `merged_at != null`. Use `--jq` to extract only merged PRs.

**Note on GitHub `gh api`:** Does NOT accept `-R`. Uses `{owner}/{repo}` in endpoint URL. Other `gh` subcommands (`gh issue comment`, `gh pr list`, etc.) DO accept `-R`.

## Error Handling

All commands may fail. Log a warning and continue.

## Task Instructions

<task>

<step n="1" goal="Detect platform and project">
<action>Read `issue_tracking.platform` from `_bmad/bmm/config.yaml`. If absent or unrecognized, print a warning and stop.</action>
<action>Detect project from git remote (same detection logic as sync task Step 1)</action>
<action>Verify CLI connectivity</action>
<check if="connectivity fails">
  <output>WARN: Issue tracker unavailable — skipping link.</output>
  <action>Skip remaining steps</action>
</check>
<action>Read `prd_key` from `prd.md` frontmatter</action>
</step>

<step n="2" goal="Fetch merged MRs/PRs and issues">
<action>Fetch all merged MRs/PRs using the platform-appropriate fetch command. Build an in-memory index keyed by MR/PR number.</action>
<action>Fetch all PRD issues using the platform-appropriate search with label `prd{sep}{prd_key}`. Build an in-memory index keyed by issue number.</action>
</step>

<step n="3" goal="Pattern matching">
<action>For each merged MR/PR, attempt pattern matching against issue titles:</action>

Pattern rules (in order):
1. **Story key in title**: MR/PR title contains `N-N-` pattern (e.g., `feat/1-3-login-form`). Extract the story key, convert dashes to dots (e.g., `1-3` → `1.3`), and find issue whose title starts with `N.N ` (e.g., `1.3 Login Form`)
2. **Epic reference**: Title or branch name contains `epic-N`. Find issues with label `{prd_key}{sep}epic-N`
3. **Branch name**: Parse `source_branch` (GitLab) or `head.ref` (GitHub) for story key patterns (e.g., `feature/1-3-backend-auth`)

<note>Track which MRs/PRs were matched and which remain unmatched.</note>
</step>

<step n="4" goal="Check for existing cross-references">
<action>For each matched MR/PR, check if a cross-reference comment already exists:</action>
1. List comments using the platform-appropriate list-comments command
2. Check if any comment body contains `Related to #{ISSUE_NUMBER}` or `Closes #{ISSUE_NUMBER}`
3. If already referenced → skip

<note>This ensures idempotency — re-running the task won't add duplicate comments.</note>
</step>

<step n="5" goal="Add cross-reference comments">
<action>For each matched MR/PR without an existing cross-reference, post a comment:</action>

Comment body:
```
Related to #{ISSUE_NUMBER}
```

<action>Use the platform-appropriate add-comment command.</action>
</step>

<step n="6" goal="Tier 2 — Manual resolution">
<action>Present unmatched MRs/PRs to the user for manual cross-referencing. Skip any the user wants left unlinked.</action>
</step>

<step n="7" goal="Report summary">
<action>Display:</action>

```
MR/PR-Issue Cross-Reference Summary
====================================
Platform:           {platform}
Pattern matched:    {n}
Already referenced: {n} (skipped)
Comments added:     {n}
Manually linked:    {n}
Unlinked:           {n}
```

</step>

</task>
