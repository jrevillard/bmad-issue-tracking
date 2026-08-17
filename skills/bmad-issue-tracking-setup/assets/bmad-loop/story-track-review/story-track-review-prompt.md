You are the story-track-review step of a bmad-loop run, executing after review
completes. Your job: commit review modifications, push, wait for CI, and mirror
the story to its issue.

**Context**: You are running in the story's worktree (current working directory). All file operations should use relative paths or `$PWD`.

## Mandatory: commit + push + CI

These must succeed — the issue tracking depends on the final CI result.

1. **Commit review modifications**:
   ```bash
   git add -A
   git commit -m "review: apply review feedback and improvements"
   ```
   If there are no changes to commit (review made no modifications), skip this step.

2. **Push the changes**: `git push` (the branch is already tracked from story-track-dev).

3. **Wait for CI pipeline** — poll the pipeline status until it reaches a terminal
   state (success/failed). Use the same platform detection as story-track-dev:
   - GitLab: `glab api "projects/{project_enc}/merge_requests/{iid}/pipelines" --hostname {host}` — check the latest pipeline status
   - GitHub: `gh pr checks {num} -R "{host}/{project}"` — check the check suite status
   - Poll every 30 seconds. **No timeout** — wait until CI completes (green or red), no matter how long it takes.
   - If the pipeline has multiple jobs, aggregate: all success = green, any failure = red. Wait until ALL jobs reach terminal state (success/failed/skipped).

4. **Write ci-status.json** — after CI completes, write the result to `{worktree}/ci-status.json`:
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
   **IMPORTANT: Validate the JSON before writing!** Use `uv run --no-project python -c "import json,sys; json.loads(sys.stdin.read())" < ci-status.json` to validate. If invalid, fix and retry. **Never write invalid JSON** — ci-status.sh will fail to parse it.

   For red CI, provide a **rich diagnostic**: pipeline URL, names of failed jobs, error messages, links to logs. This diagnostic will be passed to the repair session.

   **Note on flaky tests:** If you detect a flaky test (e.g., test passes on retry, or known flaky pattern like timeout/connection error), still write `status: "red"` — bmad-loop's repair session will handle the retry. Do not retry flaky tests yourself; let the repair loop manage it.

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
   - GitLab: `glab api "projects/{project_enc}/issues?search={story_key}&labels=prd::{prd_key}" --hostname {host}`
   - GitHub: `gh api "search/issues?q={story_key}+repo:{project}+label:prd:{prd_key}" --hostname {host}`

3. If found, read ci-status.json (just written) and update the issue:
   - Status label: `green` → `status::{sep}done` (close issue), `red` → `status::{sep}in-progress` (keep open)
     (`{sep}` is `::` on GitLab, `:` on GitHub)
   - Post a comment: the trace MR link + CI result (green/red) + brief summary.

4. If the issue is not found, skip (the post-run sync will create it).

## Constraints

- **Do NOT modify `sprint-status.yaml`** — the orchestrator owns it and
  reconciles it after you finish.
- **Do NOT rewrite code** — the module provides canonical workflows under `_bmad/_config/custom/workflows/common/` that handle platform differences, pagination, URL encoding, and API specifics. Use them (INCLUDE) instead of writing ad-hoc scripts. For issue/board/label operations, INCLUDE:
  - `update-issue-status.yaml`
  - `find-issue.yaml`
  - `create-issue.yaml` (if needed)
- Use the module's deployed workflows under
  `_bmad/_config/custom/workflows/common/` (`update-issue-status.yaml`,
  `find-issue.yaml`) as the canonical logic where it helps.

Then end your turn following the Completion signal contract below.
