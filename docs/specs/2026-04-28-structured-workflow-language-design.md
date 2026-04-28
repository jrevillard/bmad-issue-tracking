# Structured Workflow Language — Design Specification

**Module:** bmad-issue-tracking
**Version:** 1.0
**Date:** 2026-04-28
**Status:** Draft

## 1. Problem Statement

The issue-tracking module uses 10 TOML override files and 1 sync task (SKILL.md) — 638 lines total — to instruct AI agents on workflow execution. Instructions are written in prose and injected into the agent's prompt.

**Observed failures:**
- Agent improvises CLI commands not in the instruction set
- Agent skips steps or executes them out of order
- Agent misinterprets conditions (e.g., "if not found" treated as "if found")
- Context compaction loses variables set during activation, causing on_complete to fail

**Root cause:** Prose requires interpretation. The agent infers intent from natural language, introducing ambiguity at every step.

**Goal:** Replace prose with a structured pseudocode format (YAML) that eliminates interpretation. Each step is typed, each condition is formal, each variable is explicitly scoped. The agent executes mechanically — no room for improvisation.

---

## 2. Architecture

### 2.1 File Structure

```
_bmad/_config/custom/
  bmad-workflow-lang.md              # Language spec — how to interpret the format
  bmad-bmm-issue-sync.md             # Sync task (unchanged)
  workflows/
    common/
      check-config.yaml              # Validate platform + branch_patterns
      find-prd.yaml                  # Find PRD branch, switch worktree, pull, extract prd_key
      find-stories.yaml              # Scan story branches, pull, read sprint-status, filter by status
    create-prd/
      activation.yaml
      complete.yaml
    create-story/
      activation.yaml
      complete.yaml
    dev-story/
      activation.yaml
      complete.yaml
    code-review/
      activation.yaml
      complete.yaml
    check-implementation-readiness/
      complete.yaml
    correct-course/
      complete.yaml
    edit-prd/
      complete.yaml
    retrospective/
      complete.yaml
    sprint-planning/
      complete.yaml
    sprint-status/
      complete.yaml
```

### 2.2 TOML Simplification

Each TOML override becomes a thin pointer:

```toml
[workflow]
activation_steps_append = [
  "Read `_bmad/_config/custom/bmad-workflow-lang.md` for the workflow language specification, then execute `_bmad/_config/custom/workflows/{workflow}/activation.yaml`.",
]
on_complete = """
Read `_bmad/_config/custom/bmad-workflow-lang.md` for the workflow language specification, then execute `_bmad/_config/custom/workflows/{workflow}/complete.yaml`.
"""
```

### 2.3 Three-Layer Model

| Layer | Purpose | Consumed by |
|-------|---------|-------------|
| **Language spec** | Defines step types, operators, variable rules, error handling | Agent (read once per session) |
| **Sub-workflows** | Reusable step sequences (check-config, find-prd, find-stories) | Workflow files via INCLUDE |
| **Workflow files** | Assemble sub-workflows + specific logic per BMM workflow | Agent (per workflow execution) |

### 2.4 Language Version

The language spec MUST include a `version` field. When the language evolves, the version is incremented. Workflow files MAY declare a minimum language version. If the deployed language spec version is lower than the minimum required by a workflow file, the workflow stops with an error.

```
version: 1.0
```

---

## 3. Language Specification

### 3.1 Step Types

| Type | Purpose | Required Fields | Optional Fields |
|------|---------|-----------------|-----------------|
| `INCLUDE` | Insert a sub-workflow | `path` | — |
| `READ` | Read a file and extract data | `file` | `extract` |
| `FILTER` | Extract a value from a variable | `source`, `select`, `where` | `store` |
| `RUN` | Execute a CLI command | `command` | `store`, `expect_exit`, `capture`, `platform` |
| `OUTPUT` | Display message to user | `message` | `store`, `stop` |
| `WRITE` | Write content to a file | `file`, `content` | `mode` |
| `CHECK` | Conditional branching | `condition` | `true`, `false` |
| `LOOP` | Iterate over a collection | `items`, `as`, `do` | `filter`, `store` |
| `STOP` | Halt workflow execution | — | — |

### 3.2 Step Definitions

#### INCLUDE

```yaml
- INCLUDE: common/check-config
```

Inserts all steps from the referenced sub-workflow at this position. Paths are relative to `_bmad/_config/custom/workflows/`. Variables defined in the parent scope are accessible within the included sub-workflow. Variables defined within the sub-workflow are accessible in the parent scope after the INCLUDE (shared scope).

**Non-YAML includes:** If the referenced file is not a YAML workflow (e.g., a `.md` file like the sync task), the agent reads the file and follows its instructions as-is. No step parsing is applied — the agent executes the markdown content according to its own interpretation. This is the bridge to existing prose-based tasks that are not yet migrated to YAML.

#### READ

```yaml
- READ: _bmad/custom/issue-tracking.yaml
  EXTRACT:
    prd_pattern: issue_tracking.branch_patterns.prd
    story_pattern: issue_tracking.branch_patterns.story
```

- `file`: path to the file (supports `{variable}` substitution)
- `extract`: optional map of `{local_name}: {dotpath}` — the agent parses the file and extracts the value at the given dotpath
- If `extract` is omitted, the entire file content is stored as a string
- Supported file formats and extraction rules:

| Format | Detection | Dotpath behavior |
|--------|-----------|-----------------|
| YAML | `.yaml`, `.yml` | Standard dot-notation (`issue_tracking.platform`) |
| Markdown with frontmatter | `.md` with `---` delimiters | `frontmatter.prd_key` extracts from the YAML frontmatter block between the first pair of `---` delimiters. The `---` delimiters themselves are stripped. |
| JSON | `.json` | Standard dot-notation |

- If the file does not exist: the step fails, the workflow stops with an error including the file path
- If the dotpath does not exist in the file: the step fails, the workflow stops with an error including the dotpath
- If the dotpath resolves to a list or object: the full value is stored (not stringified)

#### FILTER

```yaml
- FILTER:
    source: worktree_list
    select: path
    where: branch eq "{prd_branch}"
    store: prd_worktree_path
```

Extracts a value from a previously stored variable. Replaces the informal `EXTRACT ... from ... where ...` pattern.

- `source`: the variable to filter (must be a list of objects or a multi-line string)
- `select`: the field name to extract from matching items
- `where`: a CHECK condition expression (same operators as CHECK, see §3.2 CHECK)
- `store`: the variable name to store the result
- If no item matches the `where` condition: the step fails, the workflow stops with an error
- If multiple items match: the first match is stored

#### RUN

```yaml
- RUN: git branch --list '{prd_pattern}'
  STORE: prd_branches
  EXPECT_EXIT: 0
  CAPTURE: stdout
```

- `command`: the CLI command to execute (supports `{variable}` substitution)
- `store`: variable name to store the result. The captured output is stored as-is (raw string). If the output is multi-line, it is stored as a string with newlines.
- `capture`: what to capture — `stdout` (default), `stderr`. When `exit_code` is captured, it is stored as the string representation of the numeric exit code (e.g., `"0"` or `"128"`).
- `expect_exit`: expected exit code (default: 0). If the command exits with a different code, the workflow stops with an error including the command and the actual exit code
- `platform`: if specified (`gitlab` or `github`), the step is executed ONLY when `issue_tracking.platform` matches this value. If omitted, the step is always executed. Only one `platform` value is allowed per step — use two separate RUN steps for platform divergence.

#### OUTPUT

```yaml
- OUTPUT:
    message: "What is the story key? (e.g. 1-3-login-form)"
    store: story_key
```

```yaml
- OUTPUT:
    message: "No PRD found. Run /bmad-create-prd first."
    stop: true
```

- `message`: text to display to the user. This is a **display string**, not an instruction — the agent shows it verbatim and takes no further action based on its content.
- `store`: if present, the agent waits for user input and stores the response as a string in this variable
- `stop`: if `true`, the workflow halts after displaying the message

#### WRITE

```yaml
- WRITE:
    file: /tmp/issue-desc.md
    content: "**Sprint Key:** {story_key}\n\n---\n\n{story_content}"
    mode: overwrite
```

- `file`: path to the file (supports `{variable}` substitution)
- `content`: text to write (supports `{variable}` substitution)
- `mode`:
  - `overwrite` (default): replaces the entire file content. Creates the file if it does not exist.
  - `append`: appends to the end of the file. Creates the file if it does not exist.
  - `create`: creates a new file. **If the file already exists, the step fails and the workflow stops with an error.**
- If the parent directory does not exist: the step fails, the workflow stops with an error

#### CHECK

```yaml
- CHECK: prd_branches ne ""
  TRUE:
    - RUN: git worktree list
      STORE: worktrees
  FALSE:
    - OUTPUT:
        message: "No PRD found. Run /bmad-create-prd first."
        stop: true
```

- `condition`: a formal expression using the operators below. Syntax: `{left_operand} {operator} {right_operand}`. Operands are either literal values (strings in quotes, numbers unquoted) or variable references (unquoted names).
- `true`: steps to execute when the condition evaluates to true (required if there is a true branch)
- `false`: steps to execute when the condition evaluates to false (required if there is a false branch)
- If neither `true` nor `false` is provided: the check acts as an assertion — the workflow stops with an error if the condition evaluates to false

**Operators:**

| Operator | Meaning | Left | Right | Example |
|----------|---------|------|-------|---------|
| `eq` | equals (case-sensitive) | string, number, variable | string, number, variable | `status eq "done"` |
| `ne` | not equals | string, number, variable | string, number, variable | `prd_branches ne ""` |
| `exists` | variable is defined and not null | variable name | — | `exists prd_key` |
| `empty` | variable is empty string, empty list, or undefined | variable name | — | `empty prd_branches` |
| `contains` | string contains substring, or list contains value | string or list | string | `status contains "review"` |
| `any` | list contains an object matching a field condition | list (of objects) | `field eq "value"` | `entries any status eq "review"` |
| `gt` | greater than (numeric) | number or variable | number | `count gt 1` |
| `lt` | less than (numeric) | number or variable | number | `count lt 1` |
| `matches` | regex match (Python `re` syntax) | string or variable | string (regex pattern) | `branch matches "feat/.+/prd"` |

#### LOOP

```yaml
- LOOP:
    items: story_branches
    as: branch
    do:
      - RUN: git worktree list
        STORE: worktrees
      - FILTER:
          source: worktrees
          select: path
          where: branch eq "{branch}"
          store: worktree_path
      - RUN: cd {worktree_path} && git pull --ff-only
        EXPECT_EXIT: 0
      - READ: {implementation_artifacts}/sprint-status.yaml
        EXTRACT:
          entries: development_status
    FILTER:
      where: entries any status eq "review"
      store: matched_stories
```

- `items`: the collection variable to iterate over (must be a list or a multi-line string split by newline)
- `as`: the loop variable name for each item
- `do`: steps to execute for each item
- `filter`: optional post-loop filter. `filter` has a single `where` condition and a single `store` target. The agent evaluates the `where` condition against the variables set during each loop iteration. If the condition is true, the current loop item (the value of `as`) is appended to the target variable (initialized as empty string if not already defined, items separated by newlines).
- The `where` condition uses the same operators as CHECK (see operator table). For checking fields within a YAML structure stored as a variable, use the `any` operator: `entries any status eq "review"` means "the `entries` list contains an object whose `status` field equals `review`".

#### STOP

```yaml
- STOP
```

Halts workflow execution immediately. No message is displayed. To display a message before stopping, use OUTPUT with `stop: true`.

### 3.3 Variable System

**Variable types:** All variables are strings. Multi-line command output is stored as a string with newlines. Lists are stored as newline-separated strings. No implicit typing — the agent treats every variable as a string and applies string operations. This keeps the spec minimal (YAGNI).

**Scopes:**
- `workflow` — local to the current workflow file (default). Not accessible from parent or sibling workflows.
- `shared` — variables set within an INCLUDED sub-workflow are accessible in the parent scope after the INCLUDE returns. No prefix needed — this is the default behavior of INCLUDE.

**Reference syntax:** `{variable_name}` in any string field. The agent substitutes the value at execution time.

**Predefined variables** (resolved at workflow execution time):

| Variable | Source | Resolution |
|----------|--------|------------|
| `{planning_artifacts}` | `bmm/config.yaml` → `planning_artifacts` | Read from BMM config at workflow start |
| `{implementation_artifacts}` | `bmm/config.yaml` → `implementation_artifacts` | Read from BMM config at workflow start |
| `{project-root}` | Working directory root | Resolved from current git repo root |
| `{sep}` | Label separator | `::` if `issue_tracking.platform` is `gitlab`, `:` if `github`. Resolved by reading `_bmad/custom/issue-tracking.yaml` → `platform` at workflow start. |
| `{prd_key}` | PRD frontmatter | Extracted from `{planning_artifacts}/prd.md` frontmatter field `prd_key` |
| `{story_key}` | Sprint status | Each workflow that needs `story_key` defines its target status explicitly (e.g., `target_status: "review"` for code-review, `target_status: "ready-for-dev"` for dev-story). The agent reads `{implementation_artifacts}/sprint-status.yaml` and matches the entry whose status equals the target status. If no entry matches, fall back to file matching `*-*.md` in `{implementation_artifacts}/`. For workflows that do not need `story_key` (e.g., sprint-planning), this variable is not used. |
| `{epic_num}` | Derived from story_key | First dash-separated segment (e.g., `1` from `1-3-login-form`) |
| `{story_num}` | Derived from story_key | Second dash-separated segment (e.g., `3` from `1-3-login-form`) |
| `{prd_branch}` | Config pattern | `issue_tracking.branch_patterns.prd` with `{prd_key}` substituted |
| `{story_branch}` | Config pattern | `issue_tracking.branch_patterns.story` with `{prd_key}` and `{story_key}` substituted |

**Variable resolution failure:** If a referenced variable is not defined at the point of reference, the workflow stops with an error naming the missing variable.

### 3.4 Error Handling

| Situation | Behavior |
|-----------|----------|
| `RUN` exits with unexpected code | Stop workflow, output error with command, expected code, and actual code |
| `READ` file not found | Stop workflow, output error with file path |
| `READ` extract dotpath not found | Stop workflow, output error with dotpath and file path |
| `FILTER` no match on `where` | Stop workflow, output error with the filter condition |
| `CHECK` references undefined variable | Stop workflow, output error with variable name |
| `INCLUDE` path not found | Stop workflow, output error with path |
| `WRITE` mode `create` but file exists | Stop workflow, output error with file path |
| `WRITE` parent directory does not exist | Stop workflow, output error with directory path |
| Variable reference undefined | Stop workflow, output error with variable name |
| Language version mismatch | Stop workflow, output error with required and actual versions |

No retry. No fallback. The agent does NOT improvise recovery — it stops and reports the error.

### 3.5 Built-In Variables Reference

All variables are strings. This section lists every variable available at workflow execution time, its source, and how it is resolved.

**BMM Config Variables** (read from `bmm/config.yaml` at workflow start):

| Variable | Config Field | Example Value |
|----------|-------------|---------------|
| `{planning_artifacts}` | `planning_artifacts` | `_bmad-output/planning-artifacts` |
| `{implementation_artifacts}` | `implementation_artifacts` | `_bmad-output/implementation-artifacts` |
| `{project-root}` | — | `/home/user/my-project` |

**Platform Variables** (read from `_bmad/custom/issue-tracking.yaml` at workflow start):

| Variable | Config Path | GitLab Example | GitHub Example |
|----------|-------------|----------------|----------------|
| `{sep}` | `issue_tracking.platform` → `::` or `:` | `::` | `:` |
| `{prd_pattern}` | `issue_tracking.branch_patterns.prd` | `feat/mobile-oidc/prd` | `feat/mobile-oidc/prd` |
| `{story_pattern}` | `issue_tracking.branch_patterns.story` | `feat/mobile-oidc/{prd_key}-{story_key}` | `feat/mobile-oidc/{prd_key}-{story_key}` |

**Derived Variables** (resolved at runtime from other variables):

| Variable | Derived From | Example |
|----------|-------------|---------|
| `{prd_key}` | `{planning_artifacts}/prd.md` frontmatter `prd_key` | `mobile-oidc` |
| `{prd_branch}` | `{prd_pattern}` with `{prd_key}` substituted | `feat/mobile-oidc/prd` |
| `{story_key}` | `{implementation_artifacts}/sprint-status.yaml` entry matching workflow context | `1-3-login-form` |
| `{story_branch}` | `{story_pattern}` with `{prd_key}` and `{story_key}` substituted | `feat/mobile-oidc/1-3-login-form` |
| `{epic_num}` | First dash-separated segment of `{story_key}` | `1` |
| `{story_num}` | Second dash-separated segment of `{story_key}` | `3` |

**Shell Variables** (set by `git remote` and `glab`/`gh` CLI, resolved during sync task step 1):

| Variable | Source | Example |
|----------|--------|---------|
| `{HOST}` | Git remote URL | `gitlab.example.com` |
| `{PROJECT_ID}` | `glab api` response | `42` |
| `{PROJECT_PATH}` | Git remote path | `group/project` |
| `{OWNER}` | Git remote path | `octocat` |
| `{REPO}` | Git remote path | `my-repo` |

---

## 4. Sub-Workflows

### 4.1 common/check-config

Validates that the issue-tracking configuration is present and complete.

```yaml
# common/check-config.yaml
- READ: _bmad/custom/issue-tracking.yaml
  EXTRACT:
    platform: issue_tracking.platform
    branch_patterns: issue_tracking.branch_patterns
- CHECK: exists platform
  FALSE:
    - OUTPUT:
        message: "Issue tracking not configured. Open a new session and run /bmad-issue-tracking-setup (step 5) to configure the platform."
        stop: true
- CHECK: exists branch_patterns
  FALSE:
    - OUTPUT:
        message: "Branch strategy not configured. Open a new session and run /bmad-issue-tracking-setup (step 6b) to configure branch patterns."
        stop: true
```

### 4.2 common/find-prd

Finds the PRD branch, switches to its worktree, pulls, and extracts prd_key.

```yaml
# common/find-prd.yaml
- READ: _bmad/custom/issue-tracking.yaml
  EXTRACT:
    prd_pattern: issue_tracking.branch_patterns.prd
- RUN: git branch --list '{prd_pattern}'
  STORE: prd_branches
- CHECK: empty prd_branches
  TRUE:
    - OUTPUT:
        message: "No PRD found. Run /bmad-create-prd first."
        stop: true
- RUN: git worktree list
  STORE: worktree_list
- FILTER:
    source: worktree_list
    select: path
    where: branch matches "{prd_pattern}"
    store: prd_worktree_path
- RUN: cd {prd_worktree_path} && git pull --ff-only
  EXPECT_EXIT: 0
- READ: {planning_artifacts}/prd.md
  EXTRACT:
    prd_key: frontmatter.prd_key
- CHECK: exists prd_key
  FALSE:
    - OUTPUT:
        message: "prd_key not found in PRD frontmatter."
        stop: true
```

### 4.3 common/find-stories

Scans story branches, pulls each, reads sprint-status, and filters by a target status.

```yaml
# common/find-stories.yaml
# Input: target_status (variable, e.g. "review" or "ready-for-dev")
# Output: selected_story (variable, the chosen story key)
- READ: _bmad/custom/issue-tracking.yaml
  EXTRACT:
    story_pattern: issue_tracking.branch_patterns.story
- RUN: git branch --list '{story_pattern}'
  STORE: story_branches
- CHECK: empty story_branches
  TRUE:
    - OUTPUT:
        message: "No story branches found. Run /bmad-create-story first."
        stop: true
- LOOP:
    items: story_branches
    as: branch
    do:
      - RUN: git worktree list
        STORE: worktrees
      - FILTER:
          source: worktrees
          select: path
          where: branch eq "{branch}"
          store: worktree_path
      - RUN: cd {worktree_path} && git pull --ff-only
        EXPECT_EXIT: 0
      - READ: {implementation_artifacts}/sprint-status.yaml
        EXTRACT:
          entries: development_status
    FILTER:
      where: entries any status eq "{target_status}"
      store: matched_stories
- CHECK: empty matched_stories
  TRUE:
    - OUTPUT:
        message: "No stories with status '{target_status}' found."
        stop: true
- CHECK: matched_stories gt 1
  TRUE:
    - OUTPUT:
        message: "Multiple stories found with status '{target_status}'. Please choose (enter the number):"
        store: selected_story_index
- FILTER:
    source: matched_stories
    select: key
    where: index eq "{selected_story_index}"
    store: selected_story
```

---

## 5. Migration Plan

### 5.1 Principles

1. **Zero functional regression** — every behavior in the current TOML must exist in the new YAML
2. **One file at a time** — migrate the simplest workflows first, validate, then move to complex ones
3. **TOML stays as pointer** — the TOML files are simplified, not removed (BMM requires them)
4. **Sync task unchanged** — `bmad-bmm-issue-sync.md` is not modified (it already works well)
5. **Lang spec is read once** — the TOML pointer tells the agent to read it; the agent caches it for the session
6. **Prototype first** — implement the language spec and migrate sprint-planning as a proof of concept before proceeding with the remaining workflows

### 5.2 Migration Order

Each workflow is migrated independently. Order from simplest to most complex:

| Step | Workflow | Complexity | Reason |
|------|----------|------------|--------|
| 0 | Language spec + common sub-workflows | Foundation | Must exist before any workflow migration |
| 1 | sprint-planning | Trivial | Just runs sync task, no activation |
| 2 | sprint-status | Trivial | Just runs sync task, no activation |
| 3 | edit-prd | Simple | Read PRD, find issue, update description |
| 4 | retrospective | Simple | Create issue with specific labels, close |
| 5 | check-implementation-readiness | Simple | Conditional issue description updates |
| 6 | correct-course | Medium | Multi-artifact conditional updates |
| 7 | create-prd | Medium | Activation + complex on_complete (issue + draft MR) |
| 8 | code-review | High | Activation with story scanning + complex on_complete |
| 9 | dev-story | High | Activation with story scanning + complex on_complete |
| 10 | create-story | High | Activation with story creation + complex on_complete |

### 5.3 Sub-Workflow Migration

Sub-workflows are extracted before workflow migration:

| Step | Sub-workflow | Extracted from |
|------|-------------|----------------|
| 1 | common/check-config | All 10 on_complete guards |
| 2 | common/find-prd | create-prd, create-story, dev-story, code-review activation |
| 3 | common/find-stories | dev-story, code-review activation |

### 5.4 Per-File Migration Checklist

For each TOML file, the migration follows these steps:

1. **Audit current behavior** — list every step, condition, and CLI command in the current TOML
2. **Map to YAML steps** — translate each prose step to the corresponding typed YAML step
3. **Verify completeness** — every step, condition, variable, and CLI command from the original must appear in the YAML
4. **Write YAML file** — create the workflow file under `workflows/`
5. **Simplify TOML** — replace prose with the pointer to the workflow file
6. **Validate** — run the workflow end-to-end and verify identical behavior

### 5.5 Current State Audit

#### 5.5.1 Sprint Planning (current TOML)

```toml
on_complete = """
Follow the shared sync task at `...bmad-bmm-issue-sync.md` (Step 1 validates config and connectivity — do NOT skip it). Only use the exact CLI commands from the sync task table — do NOT improvise.
After completing sprint planning and updating sprint-status.yaml, sync all entries to the issue tracker by following the shared sync task at `...bmad-bmm-issue-sync.md`. Run the full sync (Steps 1 through 6).
"""
```

**Behavioral audit:**
1. Validate config (sync task step 1)
2. Run sync task steps 1-6

**Target YAML (complete.yaml):**
```yaml
- INCLUDE: common/check-config
- OUTPUT:
    message: "Syncing all entries to the issue tracker..."
- INCLUDE: bmad-bmm-issue-sync
```

Note: The sync task is a markdown file, not a YAML workflow. The INCLUDE reference is handled by the lang spec — the agent reads the markdown and follows its steps.

#### 5.5.2 Sprint Status (current TOML)

Identical structure to sprint-planning. Same target YAML.

#### 5.5.3 Edit PRD (current TOML)

**Behavioral audit:**
1. Validate config (sync task step 1)
2. Read prd_key from PRD frontmatter
3. Search for PRD issue (title starts with "PRD:")
4. Read full PRD file
5. Write description to /tmp/prd-desc.md
6. Update issue description (GitLab or GitHub)
7. Clean up temp files

**Target YAML (complete.yaml):**
```yaml
- INCLUDE: common/check-config
- INCLUDE: common/find-prd
- RUN: glab api "projects/$PROJECT_ID/issues?search=PRD:%20{prd_key}&labels=type{sep}prd" --hostname $HOST --paginate
  STORE: prd_issues
  PLATFORM: gitlab
- RUN: gh api "repos/$OWNER/$REPO/issues?state=all&per_page=100&labels=type:prd" --paginate
  STORE: prd_issues
  PLATFORM: github
- CHECK: empty prd_issues
  TRUE:
    - OUTPUT:
        message: "PRD issue not found. Skipping."
        stop: true
- READ: {planning_artifacts}/prd.md
  STORE: prd_content
- WRITE:
    file: /tmp/prd-desc.md
    content: "**PRD:** {prd_key}\n\n---\n\n{prd_content}"
    mode: overwrite
- RUN: glab api --method PUT "projects/$PROJECT_ID/issues/$IID" --hostname $HOST -F "description=@/tmp/prd-desc.md"
  PLATFORM: gitlab
  EXPECT_EXIT: 0
- RUN: gh issue edit {number} --body-file "/tmp/prd-desc.md" -R "$HOST/$OWNER/$REPO"
  PLATFORM: github
  EXPECT_EXIT: 0
- RUN: rm -f /tmp/prd-desc.md
```

#### 5.5.4 Remaining Workflows

The remaining 7 workflows follow the same audit pattern. Each is documented in the migration checklist with its full behavioral audit, target YAML, and verification steps. The detailed audit for each will be produced during implementation.

---

## 6. Functional Requirements

### FR-1: Language Specification File
The module SHALL provide a language specification file (`bmad-workflow-lang.md`) that defines all step types, operators, variable rules, and error handling. The agent MUST read this file before executing any workflow.

### FR-2: Typed Steps
Every instruction MUST be expressed as one of the defined step types (INCLUDE, READ, FILTER, RUN, OUTPUT, WRITE, CHECK, LOOP, STOP). No free-form prose instructions are permitted in workflow files. OUTPUT `message` fields are display strings, not instructions — they are shown verbatim to the user and do not trigger agent action.

### FR-3: Formal Conditions
All conditional logic MUST use the defined CHECK operators (eq, ne, exists, empty, contains, gt, lt, matches). Natural language conditions (e.g., "if not found") are not permitted in CHECK steps or FILTER `where` clauses.

### FR-4: Sub-Workflow Reuse
Common step sequences MUST be defined as sub-workflows in `workflows/common/` and referenced via INCLUDE. Duplicated step sequences across workflow files are not permitted.

### FR-5: Variable System
All variables are strings. Variable references MUST use `{name}` syntax. Undefined variable references MUST cause the workflow to stop with an error. Variables set within an INCLUDED sub-workflow are accessible in the parent scope after the INCLUDE returns.

### FR-6: Platform-Conditional Execution
RUN steps MUST support the `PLATFORM:` field. The agent MUST execute the step only when `issue_tracking.platform` matches the specified value. If `PLATFORM:` is omitted, the step is always executed. Use separate RUN steps for platform divergence — no inline conditionals.

### FR-7: Error Handling
On any failure (command exit code, file not found, undefined variable, missing extract path, no filter match), the workflow MUST stop immediately with an error message. The agent MUST NOT attempt recovery or improvisation.

### FR-8: CLI Anti-Improvisation
The language spec MUST state that the agent MUST NOT use any CLI command not explicitly specified in a RUN step or in the sync task command table. The agent MUST NOT add diagnostic commands (e.g., `git status`, `echo`), exploration commands, or any command not in the workflow.

### FR-9: TOML Pointer
Each TOML override file MUST be simplified to contain only a reference to the language spec and the corresponding workflow file. No workflow logic MUST remain in TOML files.

### FR-10: Sync Task Integration
The sync task (`bmad-bmm-issue-sync.md`) MUST remain unchanged. Workflow files MUST reference it via INCLUDE or by instructing the agent to follow its steps.

### FR-11: Pull-Before-Read
Any step that reads from a worktree MUST be preceded by a `git pull --ff-only` RUN step targeting the same worktree. This is a workflow design rule — the workflow author ensures every READ from a worktree has a preceding RUN with `git pull --ff-only`.

### FR-12: Context Compaction Resilience
Workflow complete files MUST re-derive any variables needed from on_complete that were originally set during activation. Re-derivation sources:
- `prd_key`: read from `{planning_artifacts}/prd.md` frontmatter
- `story_key`: read from `{implementation_artifacts}/sprint-status.yaml` or from file matching `*-*.md` in `{implementation_artifacts}/`
- `prd_branch`: resolve from `issue_tracking.branch_patterns.prd` with `{prd_key}`
- `story_branch`: resolve from `issue_tracking.branch_patterns.story` with `{prd_key}` and `{story_key}`

### FR-13: Migration Process
The migration MUST be incremental — one workflow at a time, validated before proceeding. The setup skill MUST deploy new files without overwriting existing customizations in consuming projects. The migration order MUST follow §5.2.

### FR-14: Setup Skill Behavior
The setup skill (`/bmad-issue-tracking-setup`) MUST deploy the following files to `_bmad/_config/custom/` in the consuming project:
- `bmad-workflow-lang.md` (language spec)
- `workflows/common/check-config.yaml`
- `workflows/common/find-prd.yaml`
- `workflows/common/find-stories.yaml`
- 10 workflow YAML files (one per BMM workflow override)

Deployment rules:
- If a workflow YAML file does not exist, create it
- If a workflow YAML file already exists, overwrite it (workflow files are managed by the module, not user-customized)
- NEVER overwrite `_bmad/custom/issue-tracking.yaml` (user configuration — preserve existing values)
- NEVER overwrite `_bmad/_config/custom/bmad-bmm-issue-sync.md` (may have been customized)
- The TOML override files in `skills/bmad-issue-tracking-setup/assets/custom/` are updated to the simplified pointer format
- If `_bmad/_config/custom/workflows/` directory does not exist, create it (including `common/` subdirectory)

---

## 7. Non-Functional Requirements

### NFR-1: Readability
Workflow files MUST be readable by a human developer without tooling. The format (YAML) is chosen for this reason.

### NFR-2: Determinism
Given the same input state (config, branches, sprint-status), the agent MUST produce identical behavior across executions. No probabilistic or interpretation-dependent steps are permitted.

### NFR-3: Minimalism
The format MUST NOT introduce features not needed by the current 10 workflows. All variables are strings — no typing system. No sub-workflow parameters. No error recovery. No LOOP break/continue. No nested LOOPs (not needed by current workflows).

### NFR-4: Backward Compatibility
The migration MUST NOT break existing consuming projects. The TOML files continue to serve as BMM entry points. Projects that have already run `/bmad-issue-tracking-setup` must be able to re-run it to get the new workflow files without losing existing customizations.

### NFR-5: Setup Integration
The setup skill (`/bmad-issue-tracking-setup`) MUST be updated to deploy the new workflow files and the language spec alongside the existing TOML overrides.

### NFR-6: Single Source of Truth
Each behavior MUST be defined in exactly one place. The sync task remains the authoritative source for CLI commands and platform detection. Sub-workflows are the authoritative source for shared sequences.

### NFR-7: Language Versioning
The language spec MUST declare a version number. Workflow files MAY declare a minimum language version. If the deployed language spec version is lower than required, the workflow stops with an error.

### NFR-8: Testability
The language spec and workflow files MUST be testable by running an AI agent through each workflow with a controlled input state (mock git repo, mock issue tracker, predefined sprint-status.yaml). Test verification is based on observable agent actions (CLI commands executed, files written, API calls made) — not on agent internal reasoning.

---

## 8. Acceptance Criteria

### AC-1: Language Spec Completeness
**Given** the language spec file is deployed to a consuming project
**When** an agent reads the spec
**Then** every step type, operator, and error case defined in §3 has a complete definition with syntax, semantics, and failure behavior — no "TBD" or undefined behavior

### AC-2: Simplest Workflow (sprint-planning)
**Given** sprint-planning TOML is migrated to the new format
**When** the agent executes the sprint-planning workflow
**Then** the agent: (1) executes check-config, (2) runs sync steps 1-6, (3) produces the sync summary — executing exactly 2 INCLUDE steps and 1 OUTPUT step in sequence, with no additional commands

### AC-3: Complex Workflow (create-story)
**Given** create-story TOML is migrated (activation + complete)
**When** the agent executes create-story
**Then** the agent executes steps in this exact order: check-config → find-prd → ask story_key → create/switch story worktree → commit → push → create issue → create MR. Each step is verified by its observable side effect (file created, git push output, issue API response).

### AC-4: Story Scanning (dev-story, code-review)
**Given** dev-story and code-review are migrated
**When** the agent executes either workflow
**Then** for each story branch, the agent executes `git pull --ff-only` BEFORE reading `sprint-status.yaml` — verified by the pull output appearing before any sprint-status reference in the agent's actions

### AC-5: Platform Correctness
**Given** a consuming project is configured for GitLab (or GitHub)
**When** the agent executes any workflow with `PLATFORM:`-tagged RUN steps
**Then** only RUN steps matching the configured platform produce CLI output. Steps with a non-matching `PLATFORM:` are silently skipped.

### AC-6: Error Handling
**Given** a workflow encounters a failure (e.g., `git branch --list` returns exit code 128)
**When** the agent detects the failure
**Then** the agent outputs an error message containing the failed command and stops — with no retry attempt and no alternative command

### AC-7: No Prose Instructions in Workflow Files
**Given** all 10 workflow files are migrated
**When** any workflow YAML file is inspected
**Then** every top-level list item starts with one of the defined step type keywords (INCLUDE, READ, FILTER, RUN, OUTPUT, WRITE, CHECK, LOOP, STOP). OUTPUT `message` fields are exempt — they are display strings, not instructions.

### AC-8: Zero Duplication
**Given** all workflow files and sub-workflows are migrated
**When** the step sequences are compared across files
**Then** no identical step sequence of 3 or more consecutive steps appears in more than one file (excluding INCLUDE references)

### AC-9: Setup Deploys New Files
**Given** the setup skill is updated
**When** a user runs `/bmad-issue-tracking-setup` in a consuming project
**Then** the following files exist under `_bmad/_config/custom/`: `bmad-workflow-lang.md`, `workflows/common/check-config.yaml`, `workflows/common/find-prd.yaml`, `workflows/common/find-stories.yaml`, and 10 workflow YAML files (one per BMM workflow)

### AC-10: Context Compaction
**Given** a workflow's activation sets `prd_key` (via find-prd sub-workflow)
**When** the on_complete workflow executes in a new session (activation variables lost)
**Then** the on_complete workflow re-derives `prd_key` by including `common/find-prd` and reading the PRD frontmatter — without referencing any variable from the previous session

### AC-11: FILTER Step
**Given** the find-prd sub-workflow is executed
**When** `git worktree list` returns multiple entries
**Then** the FILTER step extracts only the `path` field from the entry whose `branch` matches the PRD branch pattern — verified by the subsequent `git pull` targeting the correct worktree path

### AC-12: Language Version Gate
**Given** a workflow file declares `min_lang_version: 2.0`
**When** the deployed language spec has `version: 1.0`
**Then** the workflow stops with an error stating the version mismatch — without executing any steps

### AC-13: Setup Preserves Customizations
**Given** a consuming project has `_bmad/custom/issue-tracking.yaml` with existing configuration (platform, branch_patterns, host, project)
**When** the user re-runs `/bmad-issue-tracking-setup`
**Then** the existing `issue-tracking.yaml` is preserved unchanged, the new workflow files are deployed, and the TOML overrides are updated to pointer format

### AC-13: Setup Preserves Customizations
**Given** a consuming project has `_bmad/custom/issue-tracking.yaml` with existing configuration (platform, branch_patterns, host, project)
**When** the user re-runs `/bmad-issue-tracking-setup`
**Then** the existing `issue-tracking.yaml` is preserved unchanged, the new workflow files are deployed, and the TOML overrides are updated to pointer format
