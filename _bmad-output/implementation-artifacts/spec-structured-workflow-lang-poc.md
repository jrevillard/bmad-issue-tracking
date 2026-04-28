---
title: 'Structured Workflow Language — Proof of Concept'
type: 'feature'
created: '2026-04-28'
status: 'done'
baseline_commit: '7d658e7'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** AI agents executing issue-tracking workflows interpret prose instructions, leading to improvisation, skipped steps, and context-compaction failures.

**Approach:** Create a YAML-based workflow language with typed steps (INCLUDE, READ, FILTER, RUN, OUTPUT, WRITE, CHECK, LOOP, STOP) and formal operators. Migrate 4 workflows as proof of concept: sprint-planning, sprint-status (trivial), edit-prd (simple), dev-story (high — covers LOOP, CHECK, activation+complete).

## Boundaries & Constraints

**Always:** Follow the language spec in `docs/specs/2026-04-28-structured-workflow-language-design.md` verbatim for step types, operators, variable rules, and error handling. All variables are strings. No prose instructions in workflow YAML files. Source YAML files live under `skills/bmad-issue-tracking-setup/assets/` alongside the existing `custom/` directory.

**Ask First:** Any deviation from the design spec's step definitions or operator semantics.

**Never:** Modify the sync task (`bmad-bmm-issue-sync.md`). Overwrite `_bmad/custom/issue-tracking.yaml` in consuming projects. Migrate workflows beyond sprint-planning, sprint-status, edit-prd, and dev-story in this scope.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| sprint-planning execution | config set, sync task deployed | check-config → sync task steps 1-6 | Config missing → stop |
| sprint-status execution | config set, sync task deployed | check-config → sync task steps 1-6 | Config missing → stop |
| edit-prd: PRD issue found | prd_key in frontmatter, issue exists | description updated via platform API | Issue not found → stop |
| edit-prd: platform divergence | GitLab config → only glab commands run | gh command silently skipped | Platform mismatch → skip |
| dev-story activation: single story | one branch with status `ready-for-dev` | auto-select, switch worktree | No branches → stop |
| dev-story activation: multiple stories | >1 branch with status `ready-for-dev` | ask user, switch worktree | No matching status → stop |
| dev-story complete: story_key lost | context compaction cleared variables | re-derive from sprint-status.yaml | No match → stop |
| INCLUDE non-YAML file | Path to `bmad-bmm-issue-sync.md` | agent reads markdown, follows as-is | File not found → error |
| check-config: platform missing | `issue_tracking.platform` not in config | stop with setup instruction | Workflow halts |

</frozen-after-approval>

## Code Map

### Source files (module — `skills/bmad-issue-tracking-setup/assets/`)

- `bmad-workflow-lang.md` -- **CREATE** language spec (agent reads once per session)
- `workflows/common/check-config.yaml` -- **CREATE** validates platform + branch_patterns
- `workflows/common/find-prd.yaml` -- **CREATE** finds PRD branch, worktree, extracts prd_key
- `workflows/common/find-stories.yaml` -- **CREATE** scans story branches, pulls, filters by target_status
- `workflows/sprint-planning/complete.yaml` -- **CREATE** check-config → sync task
- `workflows/sprint-status/complete.yaml` -- **CREATE** check-config → sync task (same structure)
- `workflows/edit-prd/complete.yaml` -- **CREATE** check-config → find-prd → find issue → update description
- `workflows/dev-story/activation.yaml` -- **CREATE** check-config → find-prd → find-stories(status=ready-for-dev) → select + switch worktree
- `workflows/dev-story/complete.yaml` -- **CREATE** re-derive story_key → find issue → update status label → optional review comment → commit → push

### Modified files

- `custom/bmad-sprint-planning.toml` -- simplify on_complete to pointer
- `custom/bmad-sprint-status.toml` -- simplify on_complete to pointer
- `custom/bmad-edit-prd.toml` -- simplify on_complete to pointer
- `custom/bmad-dev-story.toml` -- simplify activation_steps_append + on_complete to pointers
- `SKILL.md` (setup skill) -- add step to deploy lang spec + workflow YAMLs

## Tasks & Acceptance

**Execution:**

**Foundation (step 0):**
- [x] `skills/bmad-issue-tracking-setup/assets/bmad-workflow-lang.md` -- Create language spec: all step types (§3.2), operators (§3.2 CHECK), variable system (§3.3), error handling (§3.4), version: 1.0, CLI anti-improvisation rule (FR-8). Include one concrete example per step type drawn from the 4 POC workflows. -- Foundation: agent reads this before executing any workflow.
- [x] `skills/bmad-issue-tracking-setup/assets/workflows/common/check-config.yaml` -- Create per design spec §4.1. Outputs: `platform`, `branch_patterns`. -- Shared guard for all workflows.
- [x] `skills/bmad-issue-tracking-setup/assets/workflows/common/find-prd.yaml` -- Create per design spec §4.2 with addition: if prd_key not in frontmatter, OUTPUT+store to ask user, then WRITE prd_key into frontmatter. Outputs: `prd_key`, `prd_worktree_path`. -- Shared by edit-prd, dev-story, and future workflows.
- [x] `skills/bmad-issue-tracking-setup/assets/workflows/common/find-stories.yaml` -- Create per design spec §4.3. Input: `target_status`. Outputs: `matched_stories`, `selected_story`, `selected_worktree_path`. -- Shared by dev-story.

**Workflow migrations (step 1):**
- [x] `skills/bmad-issue-tracking-setup/assets/workflows/sprint-planning/complete.yaml` -- INCLUDE check-config → OUTPUT "Syncing..." → INCLUDE bmad-bmm-issue-sync (non-YAML) -- Trivial: validates INCLUDE chain works.
- [x] `skills/bmad-issue-tracking-setup/assets/workflows/sprint-status/complete.yaml` -- Same structure as sprint-planning (IDENTICAL content) -- Trivial: validates pattern reuse.
- [x] `skills/bmad-issue-tracking-setup/assets/custom/bmad-sprint-planning.toml` -- Replace on_complete prose with pointer: "Read lang spec, then execute sprint-planning/complete.yaml" -- TOML pointer pattern (FR-9).
- [x] `skills/bmad-issue-tracking-setup/assets/custom/bmad-sprint-status.toml` -- Replace on_complete prose with pointer: "Read lang spec, then execute sprint-status/complete.yaml" -- Same pointer pattern.

**Edit-prd migration (step 2):**
- [x] `skills/bmad-issue-tracking-setup/assets/workflows/edit-prd/complete.yaml` -- INCLUDE check-config → INCLUDE find-prd → RUN search PRD issue (PLATFORM: gitlab/github) → CHECK empty → READ prd.md → WRITE /tmp/prd-desc.md → RUN update description (PLATFORM) → RUN rm temp file -- Covers READ, FILTER, WRITE, CHECK, platform-conditional RUN.
- [x] `skills/bmad-issue-tracking-setup/assets/custom/bmad-edit-prd.toml` -- Replace on_complete prose with pointer -- Removes ~30 lines of prose.

**Dev-story migration (step 3):**
- [x] `skills/bmad-issue-tracking-setup/assets/workflows/dev-story/activation.yaml` -- INCLUDE check-config → INCLUDE find-prd → INCLUDE find-stories(target_status="ready-for-dev") → CHECK empty matched_stories → CHECK matched_stories gt 1 (ask user) → FILTER select worktree → OUTPUT "Switched to {selected_story}" -- Covers LOOP (inside find-stories), CHECK branches, FILTER, OUTPUT with store.
- [x] `skills/bmad-issue-tracking-setup/assets/workflows/dev-story/complete.yaml` -- INCLUDE check-config → re-derive story_key (READ sprint-status.yaml, filter by status, if multiple matches OUTPUT+store to ask user) → RUN find issue → CHECK empty → conditional status update (CHECK + platform RUN) → WRITE /tmp/dev-story-comment.md (if review) → RUN post comment (if review) → RUN git add + commit → RUN git push → OUTPUT stay in worktree -- Covers context compaction resilience (FR-12), conditional branching, WRITE, multi-step sequence.
- [x] `skills/bmad-issue-tracking-setup/assets/custom/bmad-dev-story.toml` -- Replace activation_steps_append with pointer to activation.yaml, replace on_complete with pointer to complete.yaml -- Removes ~50 lines of prose.

**Setup skill:**
- [x] `skills/bmad-issue-tracking-setup/SKILL.md` -- Add new step after step 3: create `_bmad/_config/custom/workflows/` directory (mkdir -p), copy `bmad-workflow-lang.md` to `_bmad/_config/custom/`, copy `workflows/` recursively to `_bmad/_config/custom/workflows/`. Update file list documentation. -- Deploys all 9 new files (FR-14).

**Acceptance Criteria:**
- Given the language spec is deployed, when an agent reads it, then every step type (INCLUDE, READ, FILTER, RUN, OUTPUT, WRITE, CHECK, LOOP, STOP) has a complete definition with syntax, semantics, and failure behavior
- Given sprint-planning or sprint-status TOML is simplified, when the agent executes on_complete, then it reads the lang spec, executes check-config, then runs the sync task — with no additional commands
- Given edit-prd TOML is simplified, when the agent executes on_complete, then only platform-matching RUN steps produce CLI output — GitLab steps skipped on GitHub and vice versa (AC-5)
- Given dev-story activation, when multiple stories have status `ready-for-dev`, then the agent asks the user to choose (OUTPUT with store) — not auto-selecting
- Given dev-story activation, when no stories match, then the agent stops with "No stories found" message
- Given dev-story complete after context compaction, when story_key was lost, then the agent re-derives it from sprint-status.yaml without referencing previous session variables (AC-10)
- Given the setup skill is updated, when a user runs `/bmad-issue-tracking-setup`, then `bmad-workflow-lang.md`, all 3 common sub-workflows, and 4 workflow YAMLs exist under `_bmad/_config/custom/`
- Given the setup skill is re-run, when workflow YAML files already exist, then they are overwritten but `issue-tracking.yaml` is preserved

## Spec Change Log

## Design Notes

**Language spec structure:** Markdown file the agent reads once per session. Defines execution semantics — how the agent interprets each YAML step type. The spec is NOT executable; the agent is the interpreter. Include one concrete example per step type from the POC workflows (e.g., LOOP example from find-stories, CHECK example from edit-prd).

**Source vs deployed paths:** YAML source files live in `skills/bmad-issue-tracking-setup/assets/` (alongside `custom/` TOMLs). The setup skill copies them to `_bmad/_config/custom/workflows/` in consuming projects. TOML pointers reference the deployed path.

**Non-YAML INCLUDE bridge:** When INCLUDE references a `.md` file (like the sync task), the agent reads it and follows its prose instructions as-is. Migration escape hatch — not everything needs YAML immediately.

**TOML pointer format:**
```toml
on_complete = """
Read `_bmad/_config/custom/bmad-workflow-lang.md` for the workflow language specification, then execute `_bmad/_config/custom/workflows/{workflow}/complete.yaml`.
"""
```
For activation: same pattern in `activation_steps_append` array, one entry.

**Sub-workflow contracts:** Each sub-workflow documents its input (variables it expects) and output (variables it defines) in a YAML comment at the top. Convention: no prefix for now (YAGNI per design spec NFR-3), but document the contract explicitly to catch drift.

**Dev-story context compaction:** The complete.yaml re-derives story_key from sprint-status.yaml (not from activation variables). This is FR-12. The activation.yaml sets `selected_story` which feeds into the BMM workflow — but on_complete cannot rely on it surviving compaction.

## Verification

**Manual checks:**
- Read `bmad-workflow-lang.md` and verify every step type from §3.1 has a complete definition with an example
- Read each workflow YAML and verify every top-level list item starts with a defined step type keyword (AC-7)
- Read each simplified TOML and verify no workflow logic remains — only the pointer
- Read the setup skill and verify it deploys all 9 new files with correct source→target paths
- Verify dev-story/activation.yaml and dev-story/complete.yaml have no shared variable dependencies (complete.yaml re-derives everything)

### Review Findings

- [x] [Review][Decision] Sub-workflow parameter passing undefined — RESOLVED: add SET step type to the language. SET assigns a literal value to a variable: `SET: { variable: target_status, value: "ready-for-dev" }`. Update lang spec task, design spec §3.1 step types table, and design spec §3.2 with full definition.
- [x] [Review][Decision] prd_key fallback regression — RESOLVED: find-prd includes the normal flow — if prd_key is not in frontmatter, OUTPUT+store to ask the user, then persist via python3 cross-platform script. This is not a "fallback" or "recovery" (FR-7), it is the normal flow when the PRD was created before the module. The find-prd sub-workflow handles this case directly.
- [x] [Review][Patch] Re-derivation assumes single match — RESOLVED: if multiple stories share the same status, OUTPUT+store shows the matched keys and asks the user to choose (consistent with dev-story activation pattern).
- [x] [Review][Defer] AC-12 (language version gate) missing from tasks/AC — Design spec §2.4 + NFR-7 require version checking. Will be addressed when lang spec is created (the task explicitly includes version: 1.0). — deferred, addressed by lang spec task

### Step-04 Patches

- [x] [Patch] find-prd.yaml used `sed -i` for frontmatter insertion — not cross-platform. Replaced with `python3` one-liner that reads the file, finds the closing `---`, inserts `prd_key:` line, and writes back. python3 is available on all platforms where Claude Code runs.
- [x] [Patch] edit-prd/complete.yaml used `$IID` and `{number}` without extracting from API response. Added platform-conditional FILTER (CHECK platform eq) to extract `prd_issue_id` from the correct API field (iid for GitLab, number for GitHub).
- [x] [Patch] dev-story/complete.yaml re-derivation logic had confused status checking (in-progress overwrite by both-statuses check). Rewrote: try in-progress first (collect keys, ask if multiple), then ready-for-dev (same pattern), then file-matching fallback. Added platform-conditional FILTER for `story_issue_id`. Fixed backwards `contains` in file-matching fallback (branch contains filename, not filename contains branch).
- [x] [Patch] SKILL.md verification list grouped common YAML files as "shared workflow fragments" instead of listing individually. Expanded to list all 3 common files: check-config.yaml, find-prd.yaml, find-stories.yaml.

### Step-04 Round 2 Patches

- [x] [Patch] find-prd.yaml python3 script missing `encoding='utf-8'` — not cross-platform safe. Added explicit encoding to both open() calls.
- [x] [Patch] edit-prd/complete.yaml FILTER extracted both `iid` and `number` without platform guard — GitLab responses don't have `number`, GitHub responses don't have `iid`, causing FILTER failure. Wrapped in `CHECK: platform eq "gitlab"` with TRUE/FALSE branches extracting the correct field into unified `prd_issue_id` variable.
- [x] [Patch] dev-story/complete.yaml same iid/number FILTER issue as edit-prd. Applied same pattern with `story_issue_id`. Also fixed backwards `contains` in file-matching fallback: `value contains "{current_branch}"` → `current_branch contains "{value}"` (branch name contains the filename, not the other way around).

### Step-04 Round 2 Patches (cont.)

- [x] [Patch] Language spec FILTER lacked `collect` mode — always returned first match. Added `collect: true` field to FILTER step type. When true, returns all matching items as newline-separated string. When false/omitted, returns first match only.
- [x] [Patch] Language spec SET only accepted literals — could not copy one variable to another. Changed SET `value` field to support `{variable}` substitution.
- [x] [Patch] Language spec FILTER had no documented `index` field for list indexing. Added `index` as an implicit field available in FILTER `where` clauses (0-based position in source list). Documented in FILTER fields and CHECK operand rules.
- [x] [Patch] Language spec `gt`/`lt` operators only defined for numbers. Clarified that they also work on newline-separated strings by counting lines.

### Step-04 Round 3 Patches

- [x] [Patch] find-stories.yaml `worktree_list` undefined — variable was never set. Added `RUN: git worktree list` + STORE before the worktree path FILTER. Also changed `select: key` to `select: value` in the index-based FILTER for consistency.
- [x] [Patch] dev-story/complete.yaml file-matching fallback used `find -printf` + FILTER with `.md` in filename — the `.` in the extension would never match in the branch name. Replaced entire fallback with python3 cross-platform script using `glob.glob` and `os.path.basename` to strip `.md`.
- [x] [Patch] find-prd.yaml `prd_body` extracted but never used. Removed the unused EXTRACT.
- [x] [Patch] Language spec RUN example (section 2.4) still referenced old `$IID` variable. Updated to use `{prd_issue_id}` matching the actual workflow files.

### Step-04 Round 4 Patches

- [x] [Patch] find-stories.yaml single-match crash — FILTER `index eq "{selected_story_index}"` ran unconditionally outside the TRUE branch. When only one match existed, `selected_story_index` was undefined. Moved FILTER inside TRUE branch, added FALSE branch with SET to auto-select.
- [x] [Patch] dev-story/complete.yaml re-derivation broken after status change — BMM workflow changes sprint-status before on_complete runs, so "in-progress" and "ready-for-dev" checks would fail. Replaced entire re-derivation with simple branch-name extraction: `git branch --show-current` + python3 to get last `/`-separated segment as story_key.
- [x] [Patch] edit-prd/complete.yaml double frontmatter — READ stored full file including frontmatter, WRITE prepended `---` separator. Issue description would show raw frontmatter. Replaced READ+WRITE with python3 script that strips frontmatter (skips everything before second `---`) and stores only the body as `prd_body`.

### Step-04 Round 5 Patches

- [x] [Patch] dev-story/complete.yaml `entries any status eq` scanned ALL stories, not just the current one. If Story A is "review" and Story B is "in-progress", the workflow would incorrectly update Story B's issue to "review". Added FILTER to extract only the current story's status: `FILTER source: entries select: value where: key eq "{story_key}" store: story_status`, then changed CHECKs to `story_status eq "review"` etc.
- [x] [Patch] **YAML map format mismatch** — sprint-status.yaml uses a YAML MAP (`{story_key: status_string}`), not a list of objects. All `entries` references with object field access (`status eq`, `key eq`) were wrong. Added lang spec section 4.1 rule: YAML maps treated as lists of `{key, value}` objects. Updated find-stories.yaml LOOP filter to `entries any value eq`, dev-story/complete.yaml FILTER to `select: value where: key eq`. Updated all spec examples.

### Step-04 Round 6 Patches

- [x] [Patch] find-stories.yaml LOOP false-positive collection — post-LOOP filter checked `entries any value eq "{target_status}"` which returns true if ANY story has the status, causing ALL branches to be collected. Fixed: extract story_key from branch name inside loop, look up specific entry's status via `FILTER select: value where: key eq "{story_key}"`, then filter on `story_status eq "{target_status}"`.
- [x] [Patch] dev-story/activation.yaml never switched to worktree — OUTPUT said "Switched to story" but no `cd` command was executed. Added `git worktree list` + FILTER + `RUN: cd {selected_worktree_path}` before the OUTPUT.
