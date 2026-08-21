---
title: 'bmad-loop issue tracking integration'
type: 'feature'
created: '2026-08-19'
status: 'in-review'
review_loop_iteration: 0
context: []
baseline_commit: 'NO_VCS'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The story-track-review plugin improvises issue tracking in its LLM prompt instead of reusing the module's established YAML workflows. This leads to inconsistency and fragility when the module's issue handling evolves.

**Approach:** Reference the module's YAML workflows from the plugin prompts so the LLM follows the exact same logic used by the module's own workflows.

## Boundaries & Constraints

**Always:**
- Reference existing YAML workflows by path, do not reimplement logic
- Support both GitLab (glab) and GitHub (gh) platforms
- Keep the plugin prompts minimal — just reference the workflows

**Ask First:**
- Whether to also add issue tracking to story-track-dev (set status to "in-progress")

**Never:**
- Duplicate the issue tracking logic in the plugin prompts
- Hardcode platform-specific API calls

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| CI green, issue exists | story key, prd_key, MR link, pipeline ID | Issue closed with status::done (close: "true"), comment posted with MR link + CI result | N/A |
| CI green, issue not found | story key, prd_key | OUTPUT message "Issue not found, post-run sync will create it", skip issue tracking | N/A |
| CI red | story key, prd_key, error details | Issue stays open (close: "false", status::in-progress), comment posted with failure details | N/A |
| Platform is GitHub | story key, prd_key | Use gh CLI commands instead of glab | N/A |
| Comment posting fails | story key, prd_key, issue found, comment API error | Skip comment (best-effort), report in OUTPUT message, continue — do not fail session | N/A |

</frozen-after-approval>

## Code Map

- `skills/bmad-issue-tracking-setup/assets/bmad-loop/story-track-review/story-track-review-prompt.md` -- Plugin prompt to update; replace ad-hoc inline glab/gh commands (lines 59-68) with INCLUDE references to the three YAML workflows. The Constraints section already references some workflows; the task is to remove the duplicated inline logic and use INCLUDE consistently
- `skills/bmad-issue-tracking-setup/assets/bmad-loop/story-track-dev/story-track-dev-prompt.md` -- Optional: add reference to update-issue-status.yaml for setting "in-progress" status. If accepted, also remove the "Do NOT track issues" constraint (lines 71, 76) to avoid contradiction
- `skills/bmad-issue-tracking-setup/assets/workflows/common/post-issue-comment.yaml` -- NEW: extracted from code-review/complete.yaml, reusable for posting comments. Input contract: issue_id, comment_file (path to temp file with body), host, project, project_enc. Platform-specific RUN steps use glab/gh with these variables. Caller must resolve host/project/project_enc before INCLUDE. (`{sep}` is not used — the workflow does not construct labels, only URLs from the caller-supplied encoded project)
- `skills/bmad-issue-tracking-setup/assets/workflows/code-review/complete.yaml:46-70` -- Source of post-comment logic (Python regex extracts review section, glab api POST notes, gh issue comment). After extraction, replace inline logic with INCLUDE: common/post-issue-comment
- `skills/bmad-issue-tracking-setup/assets/workflows/dev-story/complete.yaml` -- Has same inline post-comment pattern. After extraction, replace inline logic with INCLUDE: common/post-issue-comment (or document deferral)
- `skills/bmad-issue-tracking-setup/assets/workflows/common/find-issue.yaml` -- Existing: finds issue by story key + prd label. Requires input variables: search_text, prd_key, host, project, project_enc, sep
- `skills/bmad-issue-tracking-setup/assets/workflows/common/update-issue-status.yaml` -- Existing: updates status label and closes/reopens issue. Requires input variables: issue_id, new_status, close ("true"/"false"/"none"), host, project, project_enc, sep

## Tasks & Acceptance

**Execution:**
- [x] `common/post-issue-comment.yaml` -- Extract post-comment logic from code-review/complete.yaml:46-70 into a reusable workflow with input contract (issue_id, comment_file, host, project, project_enc) -- Avoids duplication, makes logic reusable by plugins
- [x] `code-review/complete.yaml` -- Replace inline post-comment logic (lines 46-70) with INCLUDE: common/post-issue-comment -- Eliminates duplication at source
- [x] `dev-story/complete.yaml` -- Replace inline post-comment logic with INCLUDE: common/post-issue-comment (or document explicit deferral with reason) -- Eliminates duplication at second site
- [x] `story-track-review/story-track-review-prompt.md` -- Replace ad-hoc inline glab/gh commands (lines 59-68) with INCLUDE references to find-issue.yaml, update-issue-status.yaml, and post-issue-comment.yaml. Remove the duplicated logic. Ensure host/project/project_enc/sep variables are resolved before INCLUDE -- LLM follows module's established patterns without duplication
- [x] `story-track-dev/story-track-dev-prompt.md` -- Optionally: add reference to update-issue-status.yaml for setting "in-progress" status AND remove the "Do NOT track issues" constraint (lines 71, 76) to avoid contradiction -- Keeps issue status in sync with dev progress

**Acceptance Criteria:**
- Given a story-track-review plugin run with CI green, when the plugin executes, then the issue is found via find-issue.yaml logic, closed via update-issue-status.yaml logic (close: "true"), and a comment is posted via post-issue-comment.yaml logic
- Given a story-track-review plugin run with CI red, when the plugin executes, then the issue stays open (close: "false", status::in-progress) and a comment is posted with failure details via post-issue-comment.yaml logic
- Given a story-track-review plugin run where the issue is not found, when the plugin executes, then an OUTPUT message is emitted ("Issue not found, post-run sync will create it") and issue tracking is skipped
- Given a story-track-review plugin run where comment posting fails, when the plugin executes, then the comment is skipped (best-effort), an OUTPUT message reports the failure, and the session continues without failing
- Given a story-track-review plugin run on GitHub, when the plugin executes, then gh CLI commands are used instead of glab
- Given a story-track-dev plugin run, when the plugin executes (if issue tracking added), then the issue status is set to "in-progress" and the "Do NOT track issues" constraint is removed
- Given a story-track-dev plugin run where the story is parked (`awaiting-operator`), when the plugin executes, then the issue status update is skipped (no `in-progress` overwrite)

## Spec Change Log

## Design Notes

The module's YAML workflows are interpreted by LLMs in both BMM workflows and bmad-loop plugins. By referencing the same YAML files, we ensure consistency and single-source-of-truth for issue tracking logic.

## Verification

**Commands:**
- `grep -r "INCLUDE.*find-issue.yaml\|INCLUDE.*update-issue-status.yaml\|INCLUDE.*post-issue-comment.yaml" skills/bmad-issue-tracking-setup/assets/bmad-loop/story-track-review/` -- expected: review prompt references all 3 workflows via INCLUDE
- `grep -c "glab api.*notes\|gh issue comment" skills/bmad-issue-tracking-setup/assets/bmad-loop/story-track-review/story-track-review-prompt.md` -- expected: 0 (inline logic removed)
- `grep "INCLUDE.*post-issue-comment" skills/bmad-issue-tracking-setup/assets/workflows/code-review/complete.yaml skills/bmad-issue-tracking-setup/assets/workflows/dev-story/complete.yaml` -- expected: both files INCLUDE the extracted workflow (or dev-story has documented deferral)
- `cat skills/bmad-issue-tracking-setup/assets/workflows/common/post-issue-comment.yaml` -- expected: contains both glab and gh comment posting logic with parameterized input (issue_id, comment_file, host, project, project_enc)

**Manual checks:**
- Read both plugin prompts and verify they reference the YAML workflows by path
- Verify post-issue-comment.yaml handles both GitLab and GitHub platforms

### Review Findings

**High:**
- [x] [Review][Patch] Verification grep "both prompts" but task 3 optional — contradiction if optional skipped — **FIXED: verification scoped to story-track-review only**
- [x] [Review][Patch] AC missing for CI red (issue stays open + failure comment) and CI green + issue not found (skip + report) — **FIXED: added AC for CI red, issue not found, comment posting fails**
- [x] [Review][Patch] Task 2 must say "Replace inline logic with INCLUDE references" not "Add references" — duplicated inline glab/gh logic already exists in review-prompt.md lines 59-68 — **FIXED: task reworded to "Replace ad-hoc inline glab/gh commands"**
- [x] [Review][Patch] code-review/complete.yaml + dev-story/complete.yaml must INCLUDE common/post-issue-comment after extraction, not just create it — **FIXED: added tasks for both files**

**Medium:**
- [x] [Review][Patch] Dev-prompt "Do NOT track issues" constraint must be removed if Task 3 accepted — otherwise contradictory instructions — **FIXED: task now includes removing constraint**
- [x] [Review][Patch] post-issue-comment.yaml input contract unspecified — needs issue_id, comment_body/comment_file, host, project, project_enc, sep — **FIXED: input contract defined in Code Map**
- [x] [Review][Patch] dev-story/complete.yaml has same inline post-comment logic as code-review/complete.yaml — add to spec scope or document deferral — **FIXED: added to scope**
- [x] [Review][Patch] AC don't specify close input mapping (green → close: "true", red → close: "false") — **FIXED: AC now specify close input**
- [x] [Review][Patch] Edge-case matrix missing row for "comment posting fails" — need error handling policy (skip + report vs fail) — **FIXED: added row with skip+report policy**
- [x] [Review][Patch] "Issue not found" handling underspecified — OUTPUT message vs silent return? — **FIXED: OUTPUT message specified in matrix**

**Low:**
- [x] [Review][Patch] Code Map line references vague — should cite concrete line numbers (e.g., code-review/complete.yaml:64-69) — **FIXED: line numbers added**
- [x] [Review][Patch] {sep} variable dependency not surfaced — spec should note plugins must resolve host/project/project_enc/sep before INCLUDE — **FIXED: noted in Code Map**

**Dismissed:**
- [x] [Review][Dismiss] Design Notes "single-source-of-truth" claim vs inline logic — covered by finding #3
- [x] [Review][Dismiss] Verification commands not testable in CI — improvement future, out of scope

### Review Findings (this iteration)

**Patch:**
- [x] [Review][Patch] `post-issue-comment.yaml` `EXPECT_EXIT: 0` blocks the "best-effort comment skip" AC — change to non-fatal or wrap in CHECK/caller-side error handling [common/post-issue-comment.yaml:14-19] [story-track-review-prompt.md:76-77]
- [x] [Review][Patch] Both story-track prompts drop `prd_key` from `find-issue.yaml` INCLUDE — high collision risk across parallel PRDs (see [[task_multi_prd_support]]) [story-track-dev-prompt.md:81-82] [story-track-review-prompt.md:62-64] [common/find-issue.yaml:7,12]
- [x] [Review][Patch] `common/post-issue-comment.yaml` not listed in SKILL.md step 3b deploy checklist — add to the verification list (file is deployed by `cp -rf`, but the manual checklist lags) [SKILL.md:95-113]
- [x] [Review][Patch] CHANGELOG.md `[Unreleased]` not updated for the 5 logical changes (new common file, code-review refactor, dev-story refactor, story-track-dev, story-track-review) — per CLAUDE.md "Releasing" guidance [CHANGELOG.md]
- [x] [Review][Patch] Spec Code Map mentions `sep` in `post-issue-comment.yaml` input contract but the workflow header (correctly) does not — fix the spec, not the workflow [spec Code Map line 49] [post-issue-comment.yaml:4-11]
- [x] [Review][Patch] story-track-dev sets `in-progress` even when story is parked (`awaiting-operator`) — add a check to skip when issue label is `status::awaiting-operator` [story-track-dev-prompt.md:85-86]
- [x] [Review][Patch] Spec Task 5 marked `[ ]` but the diff implements it — flip to `[x]` and add to acceptance that dev now updates issue status [spec Tasks line 62]
- [x] [Review][Patch] dev-story `test -f /tmp/dev-story-comment.md` has no FALSE branch — if user dismisses the prompt, workflow halts without cleanup [dev-story/complete.yaml:55-56]
- [x] [Review][Patch] story-track-review step 4 uses `e.g.` for the temp file path — hardcode `/tmp/story-track-review-comment.md` for caller consistency [story-track-review-prompt.md:73-77]
- [x] [Review][Patch] story-track-review step 1 instructs resolving `{sep}` but the only INCLUDE that uses it is `find-issue.yaml` — keep, but trim noise in the prompt (redundant `URL-encode` already done by the workflow) [story-track-review-prompt.md:55-60]

**Defer:**
- [x] [Review][Defer] No pytest cases for `post-issue-comment.yaml` extraction — add in a follow-up test pass [tests/]
- [x] [Review][Defer] `gh -R "{host}/{project}"` rejects `host` with scheme — convention already enforced by module's existing config validators [post-issue-comment.yaml:17]
- [x] [Review][Defer] No input validation guards in `post-issue-comment.yaml` — callers (code-review, dev-story, story-track-review) guarantee variables in scope [post-issue-comment.yaml]
- [x] [Review][Defer] No retry/backoff for transient 5xx/network errors — out of scope for refactor [post-issue-comment.yaml]
- [x] [Review][Defer] No `platform` value validation in story-track-dev step 1 — would need a CHECK before INCLUDE [story-track-dev-prompt.md:76-79]
- [x] [Review][Defer] `prd.md` missing → no fallback in story-track prompts — indicates a broken setup, deferred to a separate hardening pass [story-track-*-prompt.md]
