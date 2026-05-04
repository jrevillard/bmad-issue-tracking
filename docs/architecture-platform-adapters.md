# Architecture: Platform Adapters via Sub-Workflows

**Date:** 2026-04-28
**Author:** Winston (System Architect)
**Status:** Draft — for party mode debate

---

## 1. Problem Statement

The YAML workflows currently inline platform-specific logic (GitLab vs GitHub) via `PLATFORM:` annotations and `CHECK` blocks. The inventory shows:

- **66 PLATFORM-annotated RUN steps** across 13 workflow files
- **11 inline search+extract patterns** (duplicated across files)
- **3 copies of resolve_mr_repo** (~15-30 lines each, identical 4-way branching)
- **2 copies of resolve_issue_ref** (identical 4-way branching)

Adding JIRA would multiply this by 1.5x (new PLATFORM branches everywhere) and introduce fundamental differences (no MR concept, different ID format, different CLI).

## 2. Design Principles

1. **Zero PLATFORM blocks in workflow files** — platform selection happens once, via adapter resolution
2. **Primitives, not commands** — workflows call `{create_issue}`, not `glab issue create`
3. **Boring technology** — sub-workflows with shared variable scope, no DSL, no engine
4. **Backwards compatible** — same workflow language, no new step types
5. **Testable at the primitive level** — each platform primitive is an independent unit

## 3. Architecture

```
┌─────────────────────────────────────────────┐
│              Main Workflow YAML               │
│  (pure orchestration: what, not how)        │
│                                             │
│  - INCLUDE: common/resolve-platform           │
│  - INCLUDE: {find_issue}                     │
│  - INCLUDE: {create_issue}                   │
│  - INCLUDE: {create_mr}                      │
│  - INCLUDE: {resolve_mr_repo}               │
└──────────────┬──────────────────────────────┘
               │
               │ INCLUDE (variable scope shared)
               ▼
┌─────────────────────────────────────────────┐
│         common/resolve-platform.yaml          │
│                                             │
│  READ config → set {platform}              │
│  Set {sep} = "::" or ":"                   │
│  Set {find_issue} = "platforms/{p}/find"   │
│  Set {create_issue} = "platforms/{p}/..."   │
│  Set {supports_mr} = "true" / "false"     │
└─────────────────────────────────────────────┘
               │
               │ variable interpolation in INCLUDE
               ▼
┌─────────────────────────────────────────────┐
│       platforms/gitlab/                       │
│  ├── find-issue.yaml                        │
│  ├── create-issue.yaml                     │
│  ├── update-issue-description.yaml            │
│  ├── update-issue-status.yaml               │
│  ├── close-issue.yaml                       │
│  ├── reopen-issue.yaml                      │
│  ├── post-comment.yaml                      │
│  ├── create-mr.yaml                        │
│  ├── merge-mr.yaml                         │
│  ├── find-mr.yaml                         │
│  └── resolve-mr-repo.yaml                 │
│                                             │
│       platforms/github/                       │
│  ├── (same primitives, different impl)        │
│  └── ...                                   │
│                                             │
│       platforms/jira/                         │
│  ├── create-issue.yaml                     │
│  ├── update-issue-description.yaml            │
│  ├── update-issue-status.yaml               │
│  ├── find-issue.yaml                        │
│  ├── post-comment.yaml                      │
│  └── (no MR primitives)                     │
└─────────────────────────────────────────────┘
```

## 4. Component Design

### 4.1 resolve-platform.yaml

Reads config, sets platform constants, maps primitive names to platform sub-workflow paths. This is the **single dispatch point** — the rest of the workflow never mentions platform names.

```yaml
# common/resolve-platform.yaml
- READ: _bmad/custom/issue-tracking.yaml
  EXTRACT:
    platform: issue_tracking.platform
    git_platform: issue_tracking.git_platform
- CHECK: exists git_platform
  FALSE:
    - SET: { variable: git_platform, value: "{platform}" }
# Platform constants
- CHECK: platform eq "gitlab"
  TRUE:
    - SET: { variable: sep, value: "::" }
    - SET: { variable: platform_path, value: "platforms/gitlab" }
  FALSE:
    - SET: { variable: sep, value: ":" }
    - SET: { variable: platform_path, value: "platforms/github" }
# Capabilities
- SET: { variable: supports_mr, value: "true" }
# Primitive routing — each variable points to a platform sub-workflow
- SET: { variable: find_issue, value: "platforms/{platform_path}/find-issue" }
- SET: { variable: create_issue, value: "platforms/{platform_path}/create-issue" }
- SET: { variable: update_issue_description, value: "platforms/{platform_path}/update-issue-description" }
- SET: { variable: update_issue_status, value: "platforms/{platform_path}/update-issue-status" }
- SET: { variable: close_issue, value: "platforms/{platform_path}/close-issue" }
- SET: { variable: reopen_issue, value: "platforms/{platform_path}/reopen-issue" }
- SET: { variable: post_comment, value: "platforms/{platform_path}/post-comment" }
- SET: { variable: create_mr, value: "platforms/{platform_path}/create-mr" }
- SET: { variable: merge_mr, value: "platforms/{platform_path}/merge-mr" }
- SET: { variable: find_mr, value: "platforms/{platform_path}/find-mr" }
- SET: { variable: resolve_mr_repo, value: "platforms/{platform_path}/resolve-mr-repo" }
```

**Key point:** `{platform_path}` uses variable interpolation within the SET value. When the agent executes `SET: { variable: find_issue, value: "platforms/{platform_path}/find-issue" }`, it resolves `{platform_path}` to `platforms/gitlab` (or `platforms/github`), producing `"platforms/gitlab/find-issue"`. This requires that the workflow language supports `{variable}` substitution in SET values — which it already does for all string fields.

### 4.2 Platform sub-workflow (example: create-issue)

Each primitive is a self-contained YAML sub-workflow. It receives data via shared variable scope (from the calling workflow) and produces outputs via SET.

```yaml
# platforms/gitlab/create-issue.yaml
#
# Input variables (set by caller):
#   title, labels (comma-separated), description_file
# Output variables:
#   issue_id (the GitLab IID)
# Side effects: creates an issue on GitLab

- RUN: glab api --method POST "projects/$PROJECT_ID/issues" --hostname $HOST -f "title={title}" -F "description=@{description_file}" -f "labels={labels}"
  STORE: result
- FILTER:
    source: result
    select: iid
    store: issue_id
```

```yaml
# platforms/github/create-issue.yaml
#
# Input variables (set by caller):
#   title, labels (comma-separated), description_file
# Output variables:
#   issue_id (the GitHub issue number)
# Side effects: creates an issue on GitHub

- RUN: gh issue create --title "{title}" --body-file "{description_file}" --label "{labels}" -R "$HOST/$OWNER/$REPO"
  STORE: result
- FILTER:
    source: result
    select: number
    store: issue_id
```

### 4.3 Main workflow (before vs after)

**BEFORE (current create-prd/complete.yaml — MR section):**

```yaml
# 15 lines of nested cross-platform logic
- CHECK: git_platform eq "gitlab"
  TRUE:
    - CHECK: git_platform eq platform
      TRUE:
        - SET: { variable: mr_repo, value: "$HOST/$PROJECT_PATH" }
      FALSE:
        - READ: ... git_host, git_project from config
        - SET: { variable: mr_repo, value: "$git_host/$git_project" }
    - RUN: glab mr list --source-branch {prd_branch} --target-branch {default_branch} -R "{mr_repo}"
  FALSE:
    - CHECK: git_platform eq platform
      TRUE:
        - SET: { variable: mr_repo, value: "$HOST/$OWNER/$REPO" }
      FALSE:
        - READ: ... git_host, git_project from config
        - RUN: python3 ... split git_project
        - SET: { variable: mr_repo, value: "$git_host/$git_owner/$git_repo" }
    - RUN: gh pr list --head {prd_branch} --base {default_branch} ...
```

**AFTER (refactored create-prd/complete.yaml — MR section):**

```yaml
# 3 lines — platform logic is inside resolve-mr-repo primitive
- INCLUDE: {resolve_mr_repo}
- RUN: glab mr list --source-branch {prd_branch} --target-branch {default_branch} -R "{mr_repo}"
  PLATFORM: gitlab
- RUN: gh pr list --head {prd_branch} --base {default_branch} --json number -R "{mr_repo}"
  PLATFORM: github
```

Wait — we still have PLATFORM annotations here. But that's because the MR creation command itself differs between platforms (flag names, JSON output). This is acceptable: the **data resolution** is abstracted (resolve_mr_repo), while the **CLI execution** may still need platform branching for flag differences.

The key win: the 4-way branching logic (15-30 lines) is gone. Replaced by one INCLUDE + two PLATFORM-annotated RUNs (which is the existing pattern).

### 4.4 JIRA adapter — handling missing primitives

JIRA doesn't have MRs. The resolve-platform sets `{supports_mr} = "true"` for GitLab/GitHub but `"false"` for JIRA. Workflows guard MR-related steps:

```yaml
# In create-prd/complete.yaml
- CHECK: supports_mr eq "true"
  TRUE:
    - INCLUDE: {resolve_mr_repo}
    - RUN: ... create MR ...
```

For JIRA, `{supports_mr}` is `"false"`, so the MR block is skipped entirely. No JIRA-specific MR sub-workflow is needed.

Optionally, JIRA can provide a `create-mr.yaml` that creates a stub or posts a comment:

```yaml
# platforms/jira/create-mr.yaml
- OUTPUT:
    message: "JIRA does not support MRs. Skipping MR creation."
    stop: true
```

### 4.5 resolve-mr-repo — the hardest primitive

This is the most complex primitive because it has 4-way branching (gitlab/github × same-platform/cross-platform). Each platform sub-workflow encapsulates its own logic:

```yaml
# platforms/gitlab/resolve-mr-repo.yaml
# Input: git_platform, platform (from shared scope)
# Output: mr_repo
- CHECK: git_platform eq platform
  TRUE:
    - SET: { variable: mr_repo, value: "$HOST/$PROJECT_PATH" }
  FALSE:
    - READ: _bmad/custom/issue-tracking.yaml
      EXTRACT:
        git_host: issue_tracking.git_host
        git_project: issue_tracking.git_project
    - SET: { variable: mr_repo, value: "$git_host/$git_project" }
```

```yaml
# platforms/github/resolve-mr-repo.yaml
- CHECK: git_platform eq platform
  TRUE:
    - SET: { variable: mr_repo, value: "$HOST/$OWNER/$REPO" }
  FALSE:
    - READ: _bmad/custom/issue-tracking.yaml
      EXTRACT:
        git_host: issue_tracking.git_host
        git_project: issue_tracking.git_project
    - RUN: python3 -c "parts = sys.argv[1].split('/'); print(parts[0])" {git_project}
      STORE: git_owner
    - RUN: python3 -c "parts = sys.argv[1].split('/'); print(parts[1])" {git_project}
      STORE: git_repo
    - SET: { variable: mr_repo, value: "$git_host/$git_owner/$git_repo" }
```

The 15-30 line inline blocks in create-prd, create-story, and code-review are replaced by a single INCLUDE.

## 5. Complete Primitive Inventory

| Primitive | GitLab | GitHub | JIRA | Files Using |
|----------|--------|--------|------|-------------|
| find-issue | `glab api .../issues?search=` | `gh api .../issues --paginate` | `jira issue search` | 11 occurrences |
| create-issue | `glab api --method POST .../issues` | `gh issue create` | `jira issue create` | create-issue (canonical) |
| update-issue-description | `glab api ... PUT ... -F description=@` | `gh issue edit --body-file` | `jira issue edit` | 5 invocation sites |
| update-issue-status | fetch+filter+PUT labels | `--add-label` | `jira issue edit` | 5 invocation sites |
| close-issue | `glab api ... PUT -F state_event=close` | `gh issue close` | `jira issue move` | 2 occurrences |
| reopen-issue | `glab api ... PUT -F state_event=reopen` | `gh issue reopen` | `jira issue move` | 1 occurrence |
| post-comment | `glab api .../notes -F body=@` | `gh issue comment --body-file` | `jira issue comment` | 2 occurrences |
| create-mr | `glab mr create --target-branch --source-branch` | `gh pr create --base --head` | N/A (stub) | 2 occurrences |
| merge-mr | `glab mr merge --source-branch --target-branch` | `gh pr list` + `gh pr merge` | N/A | 1 occurrence |
| find-mr | `glab mr list --source-branch --target-branch` | `gh pr list --head --base` | N/A | 1 occurrence |
| resolve-mr-repo | 4-way branch | 4-way branch | N/A | 3 occurrences |
| resolve-issue-ref | 4-way branch | 4-way branch | N/A | 2 occurrences |
| find-default-branch | `git symbolic-ref ...` | same | same | 1 occurrence |

## 6. Migration Strategy

### Phase 1: Extract primitives from current workflows (mechanical)

1. Create `platforms/gitlab/` directory with all primitives extracted from current YAML files
2. Create `platforms/github/` with GitHub equivalents
3. Create `common/resolve-platform.yaml` with the dispatch logic
4. Update main workflow files to use `INCLUDE: {primitive_name}` instead of inline PLATFORM blocks
5. **No behavioral change** — same commands, same order, same variables

### Phase 2: Verify with snapshot testing

1. For each workflow, capture the exact shell commands that would be executed (on a test repo)
2. Before and after migration: same commands, same order
3. This proves the migration is safe

### Phase 3: Add JIRA adapter

1. Create `platforms/jira/` with primitives for supported operations
2. Set `{supports_mr} = "false"` in resolve-platform
3. Add stub primitives for unsupported operations (create-mr, merge-mr)
4. Test: JIRA workflows should skip MR steps, execute issue operations

## 7. What This Does NOT Solve

1. **Multi-PRD parallelism** — issue searches still collide when multiple PRDs have the same epic numbers. This is a separate concern (already tracked in memory/task_multi_prd_support.md).
2. **CLI command differences** — `glab mr create` vs `gh pr create` still have different flags. Workflows that call `{create_mr}` may still need 2 PLATFORM-annotated RUN steps (one per CLI tool). This is acceptable: the **data resolution** is fully abstracted, only the **CLI syntax** remains platform-specific.
3. **Search result parsing** — GitLab returns different JSON structures than GitHub. Each platform's `find-issue.yaml` handles its own parsing.

## 8. Alternative Considered and Rejected

### A: Full code execution engine

Rejected. Introduces a Python/Node runtime dependency, loses agent visibility for error diagnosis, breaks the "agent reads YAML and executes" model that BMAD users understand.

### B: Adapter YAML with command templates

Rejected. Requires template interpolation logic in the agent (fill in `{title}`, `{body}`, etc.) which is exactly the cognitive load we're trying to reduce. Sub-workflows receive parameters via shared variable scope — no interpolation needed.

### C: Plugin framework with dynamic loading

Rejected. Over-engineering for 2-4 platforms. Directory-based convention (file names = primitive names) is sufficient.

### D: Single adapter file per platform

Rejected. Creates 200+ line files that duplicate the same resolve-mr-repo logic. Sub-workflows per primitive enables independent testing and composition.

## 9. Questions for Party Mode Debate

1. **Should resolve-mr-repo be a platform primitive or a common sub-workflow?** It's the same logic for both platforms, only the default repo variable differs. Extracting it into `common/resolve-mr-repo.yaml` would reduce duplication further.

2. **Should we extend the workflow language to support `{variable}` interpolation in INCLUDE paths?** Currently INCLUDE paths are literal. Without this, resolve-platform must SET a full path variable for each primitive (13 SETs). With interpolation, resolve-platform just sets `{platform_path}` once and workflows use `INCLUDE: platforms/{platform_path}/create-issue`.

3. **How should JIRA's lack of MRs be handled?** Options: stub file that stops, capability flag in resolve-platform, or workflow-level CHECK.

4. **Should the SKILL.md deploy platform files?** Yes — the setup skill already deploys workflow files. Platform sub-workflows are just more files in the same structure.

5. **Naming convention: `platforms/gitlab/` vs `adapters/gitlab/`?** "platforms" is more descriptive (they're platform-specific implementations). "adapters" implies the Go/Java adapter pattern which might mislead.
