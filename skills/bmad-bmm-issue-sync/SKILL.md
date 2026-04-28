---
name: bmad-bmm-issue-sync
description: 'Sync sprint-status.yaml entries to GitLab/GitHub Issues. Use when the user says "sync issues" or wants to push sprint status to the issue tracker.'
---

# Sync Sprint Status to Issues (GitLab or GitHub)

> Shared custom BMAD task — syncs `sprint-status.yaml` to GitLab Issues or GitHub Issues.
> Reads `issue_tracking.platform` from `_bmad/custom/issue-tracking.yaml` to pick the CLI.
> Issue-tracker-first with automatic file-system fallback when unavailable.

## Prerequisites

- `glab` CLI (for GitLab) or `gh` CLI (for GitHub) installed and authenticated
- Repository has Issues enabled
- `sprint-status.yaml` exists at `{status_file}`
- `prd_key` in `prd.md` frontmatter (field: `prd_key`), or provided by user if absent

## Error Handling

All CLI commands may fail (network timeout, 401, 409, etc.). When a command fails:
1. Log a warning to the output (do not halt the workflow)
2. Skip the specific operation that failed
3. Continue with remaining operations

## JSON Parsing

The AI parses JSON responses natively — no `jq` dependency.

## Platform Detection

At the start of every step that runs CLI commands, determine the platform by reading `issue_tracking.platform` from `_bmad/custom/issue-tracking.yaml`. Valid values: `gitlab`, `github`.

**Label separator convention:**
- GitLab: double colon (`status::done`, `type::story`)
- GitHub: single colon (`status:done`, `type:story`)

The task below uses `{sep}` as a placeholder. Replace with `::` for GitLab, `:` for GitHub.

**CLI command patterns:**
| Operation | GitLab | GitHub |
|---|---|---|
| Auth check | `glab auth status --hostname $HOST` | `gh auth status [--hostname $HOST]` |
| Create label | `glab label create -n "..." -c "..." -d "..." -R "$HOST/$PROJECT_PATH"` | `gh label create "..." --color "..." --description "..." -R "$HOST/$OWNER/$REPO"` |
| Search issues | `glab api --paginate "projects/$PROJECT_ID/issues?search=...&labels=...&state=all&per_page=100" --hostname $HOST` | `gh api --paginate "repos/$OWNER/$REPO/issues?state=all&per_page=100&labels=..." [--hostname $HOST]` |
| Create issue | `glab api --method POST "projects/$PROJECT_ID/issues" --hostname $HOST -f "title=..." -F "description=@/tmp/desc.md" -f "labels=..."` | `gh issue create --title "..." --body-file "/tmp/desc.md" --label "..." -R "$HOST/$OWNER/$REPO"` |
| Update issue | `glab api --method PUT "projects/$PROJECT_ID/issues/$IID" --hostname $HOST -f "title=..." -f "labels=..." -f "state_event=reopen"` | `gh issue edit {number} --title "..." --add-label "..." --remove-label "..." -R "$HOST/$OWNER/$REPO"` |
| Close issue | `glab api --method PUT "projects/$PROJECT_ID/issues/$IID" --hostname $HOST -f "state_event=close"` | `gh issue close {number} -R "$HOST/$OWNER/$REPO"` |
| Reopen issue | `glab api --method PUT "projects/$PROJECT_ID/issues/$IID" --hostname $HOST -f "state_event=reopen"` | `gh issue reopen {number} -R "$HOST/$OWNER/$REPO"` |
| Add comment | `glab api --method POST "projects/$PROJECT_ID/issues/$IID/notes" --hostname $HOST -F "body=@/tmp/comment.md"` | `gh issue comment {number} --body-file "/tmp/comment.md" -R "$HOST/$OWNER/$REPO"` |

**Description file:** GitLab uses `-F "description=@/tmp/file.md"` (with `@` prefix). GitHub uses `--body-file "/tmp/file.md"` (no `@` prefix).

**IMPORTANT:** Only use the exact commands from the table above. Do NOT improvise variations — check the CLI help (`glab <cmd> --help`, `gh <cmd> --help`) if you need a command not listed here.

## Task Instructions

<task>

<step n="1" goal="Detect platform and project">
<action>Check `issue_tracking` in `_bmad/custom/issue-tracking.yaml`:
- If the section does not exist, or `platform` is not set: output "Issue tracking not configured. Open a new session and run `/bmad-issue-tracking-setup` (step 5) to configure the platform. When done, come back here and say 'done' — the configuration will be re-verified and then continue these instructions." and stop.
- If `branch_patterns` is not set: output "Branch strategy not configured. Open a new session and run `/bmad-issue-tracking-setup` (step 6b) to configure branch patterns. When done, come back here and say 'done' — the configuration will be re-verified and then continue these instructions." and stop.
</action>
<action>Read `issue_tracking.platform` from config. Valid values: `gitlab`, `github`.</action>
<action>Set `{sep}` to `::` for GitLab, `:` for GitHub.</action>

<action>Resolve connection details — config first, git remote as fallback:</action>
  1. Check if `host` and `project` are set in the `issue_tracking` block.
  2. **If both are set** — use them directly. Skip git remote detection.
  3. **If either is missing** — detect from `git remote get-url origin`:
     - **If `git_platform` is set and differs from `platform`:** output "Issue tracker host/project must be configured explicitly in `_bmad/custom/issue-tracking.yaml` when git remote and issue tracker are on different platforms. Run `/bmad-issue-tracking-setup` (step 5) to configure." and stop. Do NOT use the git remote as fallback — it points to the wrong platform.
     - **GitLab** (SSH `git@HOST:GROUP/PROJECT.git` or HTTPS `https://HOST/GROUP/PROJECT.git`):
       - Set HOST and PROJECT_PATH
       - Run `glab api "projects/$(printf '%s' "$PROJECT_PATH" | sed 's/\//%2F/g')" --hostname $HOST`
       - Extract `.id` as PROJECT_ID
     - **GitHub** (SSH `git@github.com:OWNER/REPO.git` or HTTPS `https://github.com/OWNER/REPO.git` or GHE variants):
       - Set HOST (github.com or GHE host), OWNER, REPO
       - Run `gh api "repos/$OWNER/$REPO" [--hostname $HOST]` to verify connectivity

<action>Verify CLI connectivity using the auth check command for the platform</action>
<check if="any step fails">
  <output>WARN: Issue tracker unavailable — falling back to file-system tracking.</output>
  <action>Skip remaining steps</action>
</check>
<action>Read `prd_key` from `prd.md` frontmatter (field: prd_key)</action>
<check if="prd_key not found in frontmatter">
  <ask>Ask the user for the PRD key (e.g., "mobile-oidc"). Then offer to add it to the PRD frontmatter for next time.</ask>
</check>
<action>Read `planning_artifacts` and `story_location` paths from `bmm/config.yaml` (fields: `planning_artifacts` and `implementation_artifacts`)</action>
<note>Store all detected values for use in subsequent steps. For issue-tracker operations (labels, issues, comments), use the tracker variables: `-R "$HOST/$PROJECT_PATH"` for GitLab, `-R "$HOST/$OWNER/$REPO"` for GitHub. For MR/PR operations, use the git platform variables: if `git_platform` differs from `platform`, resolve `MR_HOST`/`MR_PROJECT` (GitLab) or `MR_HOST`/`MR_OWNER`/`MR_REPO` (GitHub) from `issue_tracking.git_host`/`git_project`. If same platform, reuse the tracker variables.</note>
</step>

<step n="2" goal="Ensure labels exist">
<action>Load existing labels using the search command for the platform</action>
<action>For each label below that is NOT in the response, create it using the create-label command for the platform. Skip on any error.</action>

**Status labels:**
| Label | Color | Description |
|-------|-------|-------------|
| status{sep}backlog | E5E5E5 | Story exists in epic only |
| status{sep}ready-for-dev | FBCA04 | Story file created |
| status{sep}in-progress | FEF2C7 | Developer actively working |
| status{sep}review | FF9900 | Ready for code review |
| status{sep}done | 1D7F36 | Story completed |
| status{sep}deferred | 909090 | YAGNI - deferred |
| status{sep}closed | BFBFBF | Closed - no longer needed |
| status{sep}optional | EEEEEE | Retrospective - optional |

**Type labels:**
| Label | Color | Description |
|-------|-------|-------------|
| type{sep}prd | 1F78D1 | Product Requirements Document |
| type{sep}epic | E74C3C | Epic grouping |
| type{sep}story | 6699CC | Implementation story (includes QA work tracked as stories) |
| type{sep}retrospective | CC6699 | Epic retrospective |

**PRD label:**
| Label | Color | Description |
|-------|-------|-------------|
| prd{sep}{prd_key} | 428BCA | (empty) |

**Epic labels** (read from sprint-status.yaml, match `epic-\d+:` but NOT `epic-\d+-retrospective:`):
| Label | Color | Description |
|-------|-------|-------------|
| {prd_key}{sep}epic-N | 428BCA, 44AD8E, F0AD4E, D9534F, 6B5CE7, 1ABC9C, E74C8B, 95A5A6, 3498DB, E67E22 | Epic N |

<note>Color sequence: epic-1=#428BCA, epic-2=#44AD8E, epic-3=#F0AD4E, etc.</note>

<check if="platform is gitlab">
  <action>Ensure BMAD Sprint Board exists (one-time setup). Create board named "BMAD Sprint Board" with columns for each active status label (omit done/closed). This is GitLab-specific — skip for GitHub.</action>
</check>
</step>

<step n="3" goal="Create PRD issue (if not exists)">
<action>Search for existing PRD issue using the search command with labels `type{sep}prd` and `prd{sep}{prd_key}`</action>
<check if="no match found">
  <action>Create PRD issue. Read `{planning_artifacts}/prd.md` to extract title (first `#` heading) and brief description (first paragraph). Format title as `"PRD: {heading text}"`</action>
  <action>Labels: `type{sep}prd,prd{sep}{prd_key}`</action>
  <action>Use the create-issue command for the platform</action>
</check>
</step>

<step n="4" goal="Sync issues (create missing + reconcile statuses)">
<critical>Single pass — one API fetch, then targeted creates/updates.</critical>

<action>Fetch ALL issues for this PRD using the search command with label `prd{sep}{prd_key}`. Build an in-memory index.</action>
<action>Read sprint-status.yaml and parse ALL entries in development_status</action>

<action>Classify each entry by key pattern (matches BMM sprint-status classification):</action>
  - **Epic**: starts with `epic-` and does not end with `-retrospective` → type{sep}epic
  - **Retrospective**: ends with `-retrospective` → type{sep}retrospective
  - **Story**: everything else (e.g., `1-2-login-form`, `2-11-e2e-test-coverage`) → type{sep}story

<action>Extract epic number from each entry key:</action>
  - `epic-N` → N | `epic-N-retrospective` → N | `N-N-*` → first N

<action>For each entry, determine the title:</action>
  - **Epic**: Read `{planning_artifacts}/epics.md` and extract the section starting with `## Epic N:` up to the next `## Epic` heading (or end of file). Format: `"Epic N: {first heading after ## Epic N:}"`
  - **Story**: Read `{story_location}/{entry_key}.md`. Format: `"EPIC.STORY {title}"`. If file missing, derive from key.
  - **Retrospective**: Read `{story_location}/epic-N-retrospective.md`. Format: `"Retrospective: Epic N"`

<action>Match against the in-memory issue index:</action>
  1. Exact title match (case-sensitive)
  2. Description contains the exact sprint key string
  3. Title starts with same `EPIC.STORY ` prefix (exclude `closed_as_duplicate_of`)

<action>Based on match result:</action>

  **A) No match → CREATE:**
  - Write description to `/tmp/issue-desc-{entry_key}.md`:
    ```
    **Sprint Key:** `{entry_key}`
    **Epic:** {epic_num}
    **PRD:** {prd_key}

    ---

    {full content of story file, or the extracted epic section from epics.md, or omit if no file}
    ```
  - Create with labels: `type{sep}{TYPE},status{sep}{YAML_STATUS},prd{sep}{prd_key},{prd_key}{sep}epic-{EPIC}`
  - Use the platform-appropriate create-issue command (note the `@` prefix difference for description files)
  - If YAML status is `done` or `closed`, close the issue immediately after creation
  - Clean up temp file

  **B) Match found → UPDATE (if needed):**
  - Check title match (case-sensitive)
  - Map YAML status to label name: `drafted`→`ready-for-dev`, `contexted`→`in-progress`, all others map directly (e.g., `backlog`→`backlog`). Compare the mapped label name against the issue's current status label.
  - If both match → **SKIP**
  - If different → update using the platform-appropriate commands:
    - **GitLab**: `glab api --method PUT` with `-f "labels=..."` and `-f "state_event=..."` in a single call. **WARNING:** The `labels` field replaces ALL labels on the issue. You MUST include all existing labels (type, prd, epic labels) plus the updated status label. Fetch the issue's current labels first, remove the old status label, add the new one.
    - **GitHub**: `gh issue edit` with `--add-label "new-status"` and `--remove-label "old-status"` (targeted add/remove, preserves other labels). Then use separate `gh issue close` or `gh issue reopen` for state changes — `gh issue edit` has no `--state` flag.
    - If `done` or `closed` → close; if `in-progress`, `review`, or `ready-for-dev` → reopen; if `backlog`, `deferred`, or `optional` → do NOT change open/closed state

<note>yaml is the fallback authority during outage — auto-push to issue tracker</note>
</step>

<step n="5" goal="Mark draft PR ready when all epics are done">
<note>MR/PR operations use the **git platform** (where the code lives), not the issue tracker platform. Read `git_platform` from `issue_tracking` config. If not set, assume it equals `platform`. Resolve MR repository variables: if `git_platform` differs from `platform`, set `MR_HOST` and `MR_PROJECT` from `issue_tracking.git_host`/`git_project` (for GitLab), or `MR_HOST`, `MR_OWNER`, `MR_REPO` by parsing `git_project` as OWNER/REPO (for GitHub). If same platform, reuse the standard HOST/PROJECT_PATH/OWNER/REPO variables already resolved in Step 1.</note>
<action>Determine the default branch: `git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || git remote show origin 2>/dev/null | grep 'HEAD branch' | awk '{print $NF}'`.</action>
<action>Check if all epics in sprint-status.yaml have status `done`:</action>
<check if="all epics are done">
  <action>Find the draft PR/MR for the PRD branch (PRD branch → default branch). Use the git platform and repository variables resolved above:</action>
  - **GitLab:** `glab mr list --source-branch {prd_branch} --target-branch {default_branch} -R "$MR_HOST/$MR_PROJECT"`
  - **GitHub:** `gh pr list --head {prd_branch} --base {default_branch} --json number -R "$MR_HOST/$MR_OWNER/$MR_REPO"`
  <check if="draft PR/MR found">
    <action>Mark it as ready:</action>
    - **GitLab:** `glab mr update {mr_iid} --ready -R "$MR_HOST/$MR_PROJECT"`
    - **GitHub:** `gh pr ready {pr_number} -R "$MR_HOST/$MR_OWNER/$MR_REPO"`
    <output>All epics are done — draft PR/MR marked as ready for review.</output>
  </check>
</check>
</step>

<step n="6" goal="Report sync summary">
<action>Display:</action>

```
Issue Tracker Sync Summary
==========================
Platform:       {platform}
Host:           {resolved host}
Project:        {resolved project}
PRD:            {prd_key}
Labels synced:  {n} created/verified
Issues created: {n}
Status updated: {n}
Skipped:        {n} (already in sync)
```

</step>

</task>
