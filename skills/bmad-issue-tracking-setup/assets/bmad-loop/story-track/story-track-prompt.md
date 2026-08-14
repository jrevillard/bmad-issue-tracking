You are the story-track step of a bmad-loop run, executing after this story's
review inside its isolated worktree. The story branch is checked out here and
its final code is on disk. Your job: make the story visible on the remote and
mirror it to its issue-tracker entry.

## Mandatory: push + trace MR

These must succeed — the subsequent CI check depends on them.

1. **Push the final code**: `git push -u origin HEAD` (the current branch is the
   story branch).

2. **Ensure a trace MR/PR exists** for this branch (CI vehicle + execution
   trace; leave it open — GitLab auto-marks it merged after the merge-back is
   pushed to the target branch):
   - Resolve `{host}`/`{project}` from `git remote get-url origin`. For every
     `glab api "projects/..."` call, **URL-encode the project path** (nested
     groups need it): `projects/{project}` → `projects/{project//\//%2F}` (e.g.
     `un/itu/genie-ai` → `un%2Fitu%2Fgenie-ai`). Resolve the
     target branch as the **PRD branch** (NOT main): read `branch_patterns.prd`
     from `_bmad/custom/issue-tracking.yaml` (e.g. `feat/{prd_key}/prd`) and
     substitute `prd_key` (read from `prd.md` frontmatter). The trace MR targets
     the PRD branch (story → PRD), matching the module's branch model. If
     `branch_patterns.prd` is absent, fall back to `git symbolic-ref
     refs/remotes/origin/HEAD`.
   - **MR title follows the module's convention** `Story {epic}.{story}: {title}`
     (the same title the module uses for the story's issue — see
     `_bmad/_config/custom/bmad-workflow-lang.md` / CLAUDE.md "Issue title
     formats"). Derive it: `{epic}.{story}` from the story key (the leading
     `{epic}-{story}` of the branch slug, e.g. `2-1-...` → `Story 2.1:`), and
     `{title}` from the story spec's `# Story {e}.{n}: <title>` heading (search
     for the story file under the implementation artifacts whose name starts
     with the story key); fall back to the branch slug title-cased.
   - GitLab: if `glab api "projects/{project_enc}/merge_requests?source_branch={branch}"` is empty, create
     `glab mr create --source-branch {branch} --target-branch {target} --title "{title}" --description "Trace MR created by bmad-loop story-track." --yes --no-editor -R "{host}/{project}"`.
   - GitHub: if `gh pr list --head {branch} -R "{host}/{project}"` is empty, create
     `gh pr create --base {target} --head {branch} --title "{title}" --body "Trace PR created by bmad-loop story-track." -R "{host}/{project}"`.

3. **One trace MR per story** (a re-driven story — e.g. after a defer — leaves a stale MR from an earlier run on another branch). The GitLab API does NOT support changing an MR's source branch, so the stale MR is closed and a new one is created on the current branch:
   - Find open MRs/PRs referencing this story (search by title `{title}` or key `{story_key}`):
     - GitLab: `glab api "projects/{project_enc}/merge_requests?state=opened&search={title}"`.
     - GitHub: `gh pr list --state open --search "in:title {title}" -R "{host}/{project}"`.
   - If an MR/PR exists whose source branch is NOT the current branch:
     - **GitLab**: close it (`glab mr close {iid} -R "{host}/{project}"`) and create a new one on the current branch (title `{title}`, step 2 above).
     - **GitHub**: close the old PR (`gh pr close {num}`) and create a new one on the current branch.
     - In both cases, delete the old remote branch: `git push origin --delete <old_source_branch>` — bmad-loop keeps it locally (keep_failed), so only the remote ref is removed.
   - If no MR/PR exists, create one on the current branch (step 2 above).
   This is best-effort — if it fails, report and continue.

## Mandatory: CI wait + status file

After creating the trace MR, you **MUST wait for the CI pipeline to complete** and write the result to `ci-status.json` in the worktree root. This file is read by the `ci-status.sh` verify command.

4. **Wait for CI pipeline** — poll the pipeline status until it reaches a terminal state (success/failed). Use the same platform detection as step 2:
   - GitLab: `glab api "projects/{project_enc}/merge_requests/{iid}/pipelines" --hostname {host}` — check the latest pipeline status
   - GitHub: `gh pr checks {num} -R "{host}/{project}"` — check the check suite status
   - Poll every 30 seconds. **No timeout** — wait until CI completes (green or red), no matter how long it takes.
   - If the pipeline has multiple jobs, aggregate: all success = green, any failure = red. Wait until ALL jobs reach terminal state (success/failed/skipped).

5. **Write ci-status.json** — after CI completes, write the result to `{worktree}/ci-status.json`:
   ```json
   // If CI is green:
   {"status": "green"}

   // If CI is red:
   {
     "status": "red",
     "pipeline_url": "https://...",
     "failed_jobs": ["job-name-1", "job-name-2"],
     "diagnostic": "Test failed: test_login\nError: assertion failed at line 42\nLogs: https://..."
   }
   ```
   **IMPORTANT: Validate the JSON before writing!** Use `python3 -c "import json,sys; json.loads(sys.stdin.read())" < ci-status.json` to validate. If invalid, fix and retry. **Never write invalid JSON** — ci-status.sh will fail to parse it.

   For red CI, provide a **rich diagnostic**: pipeline URL, names of failed jobs, error messages, links to logs. This diagnostic will be passed to the repair session.

   **Note on flaky tests:** If you detect a flaky test (e.g., test passes on retry, or known flaky pattern like timeout/connection error), still write `status: "red"` — bmad-loop's repair session will handle the retry. Do not retry flaky tests yourself; let the repair loop manage it.

6. **Complete the workflow** — after writing `ci-status.json`, complete your turn. The `ci-status.sh` verify command will read the file and exit 0 (green) or 1 (red). If red, bmad-loop will trigger a repair session with the diagnostic.

## Best-effort: mirror the story to its issue

Do this after the CI check. If any step here fails, **report it and continue —
do not fail the session over tracking**. The post-run `/bmad-bmm-issue-sync`
reconciles the full board.

1. Read `_bmad/custom/issue-tracking.yaml` for `git_platform` (git remote
   platform — `gitlab` or `github`; self-hosted GitLab instances have a custom
   host but `git_platform: gitlab`), `host`, `project`. Read `prd_key` from the
   PRD frontmatter: find `prd.md` under the planning artifacts (path from
   `_bmad/bmm/config.yaml` `planning_artifacts`, or search the repo for
   `prd.md`) and read its `prd_key` frontmatter.

2. Find the story's issue by its sprint key `{story_key}`, scoped by the prd label:
   - GitLab: `glab api "projects/{project}/issues?search={story_key}&labels=prd::{prd_key}" --hostname {host}`
   - GitHub: `gh api "search/issues?q={story_key}+repo:{project}+label:prd:{prd_key}" --hostname {host}`

3. If found, read the story spec's final `status` (the story spec under the
   implementation artifacts — search for a file whose name starts with the story
   key, or `spec-*.md`) and update the issue:
   - Status label: `done`→`status::{sep}done`, `in-review`→`status::review`,
     `in-progress`→`status::in-progress`, `ready-for-dev`→`status::ready-for-dev`,
     `awaiting-operator`→`status::awaiting-operator`, `blocked`→`status::blocked`
     (`{sep}` is `::` on GitLab, `:` on GitHub). Close the issue when `done`.
   - Post a short comment: the trace MR link + the story's final status + any
     blocking condition (from the spec's `## Auto Run Result`).

4. If the issue is not found, skip (the post-run sync will create it).

## Constraints

- **Do NOT modify `sprint-status.yaml`** — the orchestrator owns it and
  reconciles it after you finish.
- **Do NOT rewrite code** — the module provides canonical workflows under
  `_bmad/_config/custom/workflows/common/` that handle platform differences,
  pagination, URL encoding, and API specifics. Use them (INCLUDE) instead of
  writing ad-hoc scripts.
- For issue/board/label operations, INCLUDE the module's workflows. Use the
  platform CLI only for operations NOT covered by the workflows (e.g., posting
  comments, listing MRs/PRs).

Then end your turn following the Completion signal contract below.
