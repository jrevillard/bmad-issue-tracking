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
   - Resolve `{host}`/`{project}` from `git remote get-url origin`, and the
     target branch from `git symbolic-ref refs/remotes/origin/HEAD`.
   - GitLab: if `glab api "projects/{project}/merge_requests?source_branch={branch}"` is empty, create
     `glab mr create --source-branch {branch} --target-branch {target} --title "CI: {branch}" --description "Trace MR created by bmad-loop story-track." --yes --no-editor -R "{host}/{project}"`.
   - GitHub: if `gh pr list --head {branch} -R "{host}/{project}"` is empty, create
     `gh pr create --base {target} --head {branch} --title "CI: {branch}" --body "Trace PR created by bmad-loop story-track." -R "{host}/{project}"`.

## Best-effort: mirror the story to its issue

Do this after the push + MR. If any step here fails, **report it and continue —
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
- Use the module's deployed workflows under
  `_bmad/_config/custom/workflows/common/` (`update-issue-status.yaml`,
  `find-issue.yaml`) as the canonical logic where it helps.

Then end your turn following the Completion signal contract below.
