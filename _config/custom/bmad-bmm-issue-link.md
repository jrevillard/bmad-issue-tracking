# Link Merged MRs/PRs to Issues

> Shared custom BMAD task — retroactively links merged Merge Requests (GitLab) or Pull Requests (GitHub) to their corresponding issues.
> Reads `issue_tracking.platform` from config to pick the CLI.

## Prerequisites

- `glab` or `gh` CLI authenticated
- Issues already synced via `/bmad-bmm-issue-sync`
- `prd_key` in `prd.md` frontmatter

## Platform Detection

Read `issue_tracking.platform` from `_bmad/bmm/config.yaml`.

| Aspect | GitLab | GitHub |
|---|---|---|
| Fetch merged | `glab api --paginate "projects/$PROJECT_ID/merge_requests?state=merged&per_page=500" --hostname $HOST` | `gh pr list --state merged --json number,title,body,headRefName,mergedAt --limit 500 -R "$OWNER/$REPO"` |
| Link command | `glab api --method POST "projects/$PROJECT_ID/merge_requests/$IID/links" --hostname $HOST -f "target_issue_iid=$ISSUE_IID"` | `gh api "repos/$OWNER/$REPO/pulls/{number}/linked_issues" -f "issue_number=$ISSUE_NUMBER" [--hostname $HOST]` |
| Reference syntax | `Closes #IID` in MR description | `Closes #NUMBER` in PR description |

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
<action>Fetch all merged MRs/PRs using the platform-appropriate fetch command. Build an in-memory index.</action>
<action>Fetch all open and closed PRD issues using the platform-appropriate search with label `prd{sep}{prd_key}`. Build an in-memory index.</action>
</step>

<step n="3" goal="Tier 1 — Pattern matching">
<action>For each merged MR/PR, attempt pattern matching against issue titles:</action>

Pattern rules (in order):
1. **Story key in title**: PR/MR title contains `N.N-` pattern. Extract story key and find issue whose title starts with `N.N `
2. **Epic reference**: Title or branch name contains `epic-N`. Find issues with label `{prd_key}{sep}epic-N`
3. **Branch name**: Parse `headRefName` for story key patterns (e.g., `feature/1-3-backend-auth`)

<action>For each match, link using the platform-appropriate link command.</action>
<note>Track which MRs/PRs were linked and which remain unmatched.</note>
</step>

<step n="4" goal="Tier 2 — AI context matching">
<action>For each unmatched MR/PR:</action>
1. Read title and body
2. Read changed files (platform-appropriate diff command)
3. Compare against unmatched issue titles and bodies
4. If confident match, link

<action>Link matched MRs/PRs.</action>
</step>

<step n="5" goal="Tier 3 — Manual resolution">
<action>Present unmatched MRs/PRs to the user for manual linking. Skip any the user wants left unlinked.</action>
</step>

<step n="6" goal="Report summary">
<action>Display:</action>

```
MR/PR-Issue Linking Summary
===========================
Platform:        {platform}
Pattern matched:  {n}
AI matched:       {n}
Manually linked:  {n}
Unlinked:         {n}
```

</step>

</task>
