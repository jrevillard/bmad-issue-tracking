You are the story-track-dev step of a bmad-loop run, executing after dev completes
and before review starts. Your job: push the code, wait for CI, and create the
trace MR.

**Context**: You are running in the story's worktree (current working directory). All file operations should use relative paths or `$PWD`.

## Mandatory: push + CI + MR

These must succeed — the subsequent CI check and review depend on them.

1. **Push the final code**: `git push -u origin HEAD` (the current branch is the
   story branch).

2. **Wait for CI pipeline** — poll the pipeline status until it reaches a terminal
   state (success/failed). Use the same platform detection as step 2:
   - GitLab: `glab api "projects/{project_enc}/merge_requests/{iid}/pipelines" --hostname {host}` — check the latest pipeline status
   - GitHub: `gh pr checks {num} -R "{host}/{project}"` — check the check suite status
   - Poll every 30 seconds. **No timeout** — wait until CI completes (green or red), no matter how long it takes.
   - If the pipeline has multiple jobs, aggregate: all success = green, any failure = red. Wait until ALL jobs reach terminal state (success/failed/skipped).

3. **Write ci-status.json** — after CI completes, write the result to `{worktree}/ci-status.json`:
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

4. **Ensure a trace MR/PR exists** for this branch (CI vehicle + execution trace;
   leave it open — GitLab auto-marks it merged after the merge-back is pushed to
   the target branch):
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
   - **Clean up stale MRs** (a re-driven story — e.g., after a defer — may leave a stale MR from an earlier run on another branch). The GitLab API does NOT support changing an MR's source branch, so the stale MR must be closed:
     - Find open MRs/PRs referencing this story (search by title `{title}` or key `{story_key}`)
     - If an MR exists whose source branch is NOT the current branch: close it and delete the old remote branch
   - GitLab: if `glab api "projects/{project_enc}/merge_requests?source_branch={branch}"` is empty, create
     `glab mr create --source-branch {branch} --target-branch {target} --title "{title}" --description "Trace MR created by bmad-loop story-track." --yes --no-editor -R "{host}/{project}"`.
   - GitHub: if `gh pr list --head {branch} -R "{host}/{project}"` is empty, create
     `gh pr create --base {target} --head {branch} --title "{title}" --body "Trace PR created by bmad-loop story-track." -R "{host}/{project}"`.

5. **Complete the workflow** — after writing `ci-status.json` and creating the MR,
   complete your turn. The `ci-status.sh` verify command will read the file and
   exit 0 (green) or 1 (red).

**IMPORTANT**: Do NOT track issues here. Issue tracking happens at post_review_result (story-track-review).

## Constraints

- **Do NOT modify `sprint-status.yaml`** — the orchestrator owns it.
- **Do NOT track issues** — that's story-track-review's job at post_review_result.
- Use the module's deployed workflows under `_bmad/_config/custom/workflows/common/` as the canonical logic where it helps.

Then end your turn following the Completion signal contract below.
