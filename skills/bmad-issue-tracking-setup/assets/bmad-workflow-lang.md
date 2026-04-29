# Structured Workflow Language Specification

**Version:** 1.0

This document defines how an AI agent interprets YAML workflow files. The agent MUST read this specification before executing any workflow. Every step type, operator, variable rule, and error behavior is defined here. The agent executes mechanically based on these definitions -- no improvisation, no interpretation of intent beyond what is written.

---

## 1. File Format

Workflow files are YAML. Each file contains a top-level list of steps. A step is a single list item that begins with one of the defined step type keywords.

```yaml
- STEP_TYPE: value
  OPTIONAL_FIELD: value
```

The agent reads the YAML file and executes each step in order, from top to bottom. Steps are not skipped, reordered, or interpreted beyond their definitions.

---

## 2. Step Types

There are 11 step types:

| Type | Purpose |
|------|---------|
| `INCLUDE` | Insert a sub-workflow |
| `READ` | Read a file and extract data |
| `FILTER` | Extract a value from a variable |
| `RUN` | Execute a CLI command |
| `OUTPUT` | Display message to user |
| `WRITE` | Write content to a file |
| `CHECK` | Conditional branching |
| `LOOP` | Iterate over a collection |
| `SET` | Assign a literal value to a variable |
| `STOP` | Halt workflow execution |
| `CD` | Change agent working directory |

### 2.1 INCLUDE

Inserts all steps from the referenced sub-workflow at this position. Execution continues with the included steps and resumes in the parent file after the last included step.

**Syntax:**

```yaml
- INCLUDE: common/check-config
```

**Fields:**
- `path` (required): path to the sub-workflow file. Paths are relative to `_bmad/_config/custom/workflows/`.

**Variable scope:** Variables defined in the parent scope are accessible within the included sub-workflow. Variables defined within the sub-workflow are accessible in the parent scope after the INCLUDE returns (shared scope).

**Non-YAML includes:** If the referenced file is not a YAML workflow (e.g., a `.md` file), the agent reads the file and follows its instructions as-is. No step parsing is applied. This is the bridge to existing prose-based tasks.

**Example (from sprint-planning complete.yaml):**

```yaml
- INCLUDE: common/check-config
- INCLUDE: bmad-bmm-issue-sync
```

The first INCLUDE executes the check-config sub-workflow. The second INCLUDE reads the sync task markdown and follows its prose instructions.

### 2.2 READ

Reads a file and optionally extracts specific values using dotpath notation.

**Syntax:**

```yaml
- READ: _bmad/custom/issue-tracking.yaml
  EXTRACT:
    platform: issue_tracking.platform
    branch_patterns: issue_tracking.branch_patterns
```

**Fields:**
- `file` (required): path to the file (supports `{variable}` substitution).
- `extract` (optional): map of `{local_name}: {dotpath}`. The agent parses the file and extracts the value at the given dotpath. If omitted, the entire file content is stored as a string.

**Supported file formats and extraction rules:**

| Format | Detection | Dotpath behavior |
|--------|-----------|-----------------|
| YAML | `.yaml`, `.yml` | Standard dot-notation (e.g., `issue_tracking.platform`) |
| Markdown with frontmatter | `.md` with `---` delimiters | `frontmatter.prd_key` extracts from the YAML frontmatter block between the first pair of `---` delimiters. The `---` delimiters themselves are stripped. |
| JSON | `.json` | Standard dot-notation |

**Failure:** If the file does not exist, the workflow stops with an error including the file path. If a dotpath does not exist in the file, the workflow stops with an error including the dotpath and file path. If a dotpath resolves to a list or object, the full value is stored (not stringified).

**Example (from check-config.yaml):**

```yaml
- READ: _bmad/custom/issue-tracking.yaml
  EXTRACT:
    platform: issue_tracking.platform
    branch_patterns: issue_tracking.branch_patterns
```

### 2.3 FILTER

Extracts a value from a previously stored variable using a condition.

**Syntax:**

```yaml
- FILTER:
    source: worktree_list
    select: path
    where: branch matches "{prd_pattern}"
    store: prd_worktree_path
```

**Fields:**
- `source` (required): the variable to filter (must be a list of objects or a multi-line string).
- `select` (required): the field name to extract from matching items. Use `value` to select the raw item when the source is a list of strings.
- `where` (required): a CHECK condition expression (same operators as CHECK, see section 3). The special field `index` is available in `where` clauses and refers to the item's 0-based position in the source list.
- `store` (required): the variable name to store the result.
- `collect` (optional): if `true`, returns all matching items as a newline-separated string instead of just the first match. Default: `false` (first match only).

**Failure:** If no item matches the `where` condition, the workflow stops with an error including the filter condition.

**Example (from find-prd.yaml):**

```yaml
- FILTER:
    source: worktree_list
    select: path
    where: branch matches "{prd_pattern}"
    store: prd_worktree_path
```

**Example (collect all matching keys from a YAML map):**

```yaml
- FILTER:
    source: entries
    select: key
    where: value eq "in-progress"
    store: in_progress_keys
    collect: true
```

**Example (select by index):**

```yaml
- FILTER:
    source: in_progress_keys
    select: value
    where: index eq "0"
    store: story_key
```

### 2.4 RUN

Executes a CLI command in the shell.

**Syntax:**

```yaml
- RUN: git branch --list '{prd_pattern}'
  STORE: prd_branches
  EXPECT_EXIT: 0
  CAPTURE: stdout
  PLATFORM: gitlab
```

**Fields:**
- `command` (required): the CLI command to execute (supports `{variable}` substitution).
- `store` (optional): variable name to store the captured output. The output is stored as a raw string (multi-line output includes newlines).
- `capture` (optional): what to capture -- `stdout` (default), `stderr`.
- `expect_exit` (optional): expected exit code (default: `0`). If the command exits with a different code, the workflow stops with an error including the command and the actual exit code.
- `platform` (optional): if specified (`gitlab` or `github`), the step is executed ONLY when the `platform` variable (from `issue_tracking.platform`) matches this value. If omitted, the step is always executed. Only one platform value is allowed per step -- use two separate RUN steps for platform divergence.

**Example (from edit-prd complete.yaml):**

```yaml
- RUN: glab api --method PUT "projects/$PROJECT_ID/issues/{prd_issue_id}" --hostname $HOST -F "description=@/tmp/prd-desc.md"
  PLATFORM: gitlab
  EXPECT_EXIT: 0
- RUN: gh issue edit {prd_issue_id} --body-file "/tmp/prd-desc.md" -R "$HOST/$OWNER/$REPO"
  PLATFORM: github
  EXPECT_EXIT: 0
```

Only the step matching the configured platform is executed. The other is silently skipped.

### 2.5 OUTPUT

Displays a message to the user.

**Syntax:**

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

**Fields:**
- `message` (required): text to display to the user. This is a display string -- the agent shows it verbatim and takes no further action based on its content.
- `store` (optional): if present, the agent waits for user input and stores the response as a string in this variable.
- `stop` (optional): if `true`, the workflow halts after displaying the message.

**Example (from find-stories.yaml):**

```yaml
- OUTPUT:
    message: "Multiple stories found with status '{target_status}'. Please choose (enter the number):"
    store: selected_story_index
```

### 2.6 WRITE

Writes content to a file.

**Syntax:**

```yaml
- WRITE:
    file: /tmp/prd-desc.md
    content: "**PRD:** {prd_key}\n\n---\n\n{prd_content}"
    mode: overwrite
```

**Fields:**
- `file` (required): path to the file (supports `{variable}` substitution).
- `content` (required): text to write (supports `{variable}` substitution).
- `mode` (optional):
  - `overwrite` (default): replaces the entire file content. Creates the file if it does not exist.
  - `append`: appends to the end of the file. Creates the file if it does not exist.
  - `create`: creates a new file. If the file already exists, the workflow stops with an error.

**Failure:** If the parent directory does not exist, the workflow stops with an error including the directory path.

**Example (from edit-prd complete.yaml):**

```yaml
- WRITE:
    file: /tmp/prd-desc.md
    content: "**PRD:** {prd_key}\n\n---\n\n{prd_content}"
    mode: overwrite
```

### 2.7 CHECK

Conditional branching. Evaluates a condition and executes the corresponding branch.

**Syntax:**

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

**Fields:**
- `condition` (required): a formal expression using the operators defined in section 3. Syntax: `{left_operand} {operator} {right_operand}`. Operands are either literal values (strings in quotes, numbers unquoted) or variable references (unquoted names).
- `true` (optional): steps to execute when the condition evaluates to true.
- `false` (optional): steps to execute when the condition evaluates to false.
- If neither `true` nor `false` is provided: the check acts as an assertion -- the workflow stops with an error if the condition evaluates to false.

**Example (from check-config.yaml):**

```yaml
- CHECK: exists platform
  FALSE:
    - OUTPUT:
        message: "Issue tracking not configured. Open a new session and run /bmad-issue-tracking-setup (step 5) to configure the platform."
        stop: true
```

### 2.8 LOOP

Iterates over a collection and executes steps for each item.

**Syntax:**

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
    FILTER:
      where: entries any value eq "review"
      store: matched_stories
```

**Fields:**
- `items` (required): the collection variable to iterate over (must be a list or a multi-line string split by newline).
- `as` (required): the loop variable name for each item.
- `do` (required): steps to execute for each item.
- `filter` (optional): post-loop filter. Has a single `where` condition and a single `store` target. The agent evaluates the `where` condition against the variables set during each loop iteration. If the condition is true, the current loop item (the value of `as`) is appended to the target variable (initialized as empty string if not already defined, items separated by newlines).

**Example (from find-stories.yaml):**

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
      where: entries any value eq "{target_status}"
      store: matched_stories
```

This iterates over each story branch, pulls the worktree, reads sprint-status, and collects branches whose sprint-status entry has the target status value.

### 2.9 SET

Assigns a value to a variable. Used to pass parameters to sub-workflows before including them, or to copy a variable.

**Syntax:**

```yaml
- SET: { variable: target_status, value: "ready-for-dev" }
```

**Fields:**
- `variable` (required): the variable name to assign.
- `value` (required): the value to assign. Supports `{variable}` substitution -- if the value contains `{variable_name}`, it is replaced with the referenced variable's value at execution time. If no substitution pattern is found, the value is taken literally.

**Example (literal value, from dev-story activation.yaml):**

```yaml
- SET: { variable: target_status, value: "ready-for-dev" }
- INCLUDE: common/find-stories
```

Sets `target_status` to `"ready-for-dev"` before including find-stories, which reads `target_status` from the shared scope.

**Example (variable reference):**

```yaml
- SET: { variable: story_key, value: "{in_progress_keys}" }
```

### 2.10 STOP

Halts workflow execution immediately.

**Syntax:**

```yaml
- STOP
```

No message is displayed. To display a message before stopping, use OUTPUT with `stop: true`.

### 2.11 CD

Changes the agent's working directory. Unlike `RUN: cd <path>` (which runs in a subprocess and does not persist), `CD` instructs the agent to change its own session directory. All subsequent steps (RUN, READ, WRITE, etc.) operate relative to the new directory.

**Syntax:**

```yaml
- CD: {variable_or_path}
```

The value MUST be an absolute path or a variable reference resolving to an absolute path. The agent MUST resolve the path and change its working directory before processing the next step.

**Trace format:** `CD /path/to/directory`

The agent MUST verify that the target directory exists before changing. If it does not exist, the workflow stops with an error.

---

## 3. CHECK Operators

The following operators are available in CHECK conditions and FILTER `where` clauses.

| Operator | Meaning | Left | Right | Example |
|----------|---------|------|-------|---------|
| `eq` | equals (case-sensitive) | string, number, variable | string, number, variable | `status eq "done"` |
| `ne` | not equals | string, number, variable | string, number, variable | `prd_branches ne ""` |
| `exists` | variable is defined and not null | variable name | -- | `exists prd_key` |
| `empty` | variable is empty string, empty list, or undefined | variable name | -- | `empty prd_branches` |
| `contains` | string contains substring, or list contains value | string or list | string | `status contains "review"` |
| `any` | list/map contains an item matching a field condition | list or map | `field eq "value"` | `entries any value eq "review"` |
| `gt` | greater than (numeric, or line count on newline-separated strings) | number, variable, or newline-separated string | number | `matched_keys gt 1` |
| `lt` | less than (numeric, or line count on newline-separated strings) | number, variable, or newline-separated string | number | `matched_keys lt 1` |
| `matches` | regex match (Python `re` syntax) | string or variable | string (regex pattern) | `branch matches "feat/.+/prd"` |

**Operand rules:**
- String literals are enclosed in double quotes: `"ready-for-dev"`.
- Numbers are unquoted: `1`, `0`.
- Variable references are unquoted names: `prd_key`, `status`.
- The `exists` and `empty` operators take a single operand (the variable name).
- The `any` operator takes a list or map on the left and a field condition on the right. For maps, `key` refers to the map key and `value` refers to the map value: `entries any value eq "review"`.
- The `index` field is available in FILTER `where` clauses and refers to the item's 0-based position in the source list. It cannot be used in CHECK conditions (only in FILTER).

---

## 4. Variable System

### 4.1 Types

All variables are strings. Multi-line command output is stored as a string with newlines. Lists are stored as newline-separated strings. No implicit typing.

**YAML maps:** When READ extracts a YAML map (e.g., `development_status` from sprint-status.yaml), the map is treated as a list of `{key, value}` objects for CHECK and FILTER operations. The `key` field is the map key (string), the `value` field is the map value (string or object). This allows filtering and checking maps using the same operators as lists of objects.

Example: given `development_status: { "1-3-login-form": "done", "2-2-jwks-refresh": "ready-for-dev" }`:
- `entries any value eq "done"` → true (at least one entry has value "done")
- `entries any key matches "1-3-.*"` → true (at least one entry key matches the pattern)
- `FILTER source: entries select: value where: key eq "1-3-login-form"` → stores `"done"`

### 4.2 Scope

Variables set within an INCLUDED sub-workflow are accessible in the parent scope after the INCLUDE returns. No prefix is needed -- this is the default behavior.

### 4.3 Reference Syntax

Variables are referenced using `{variable_name}` in any string field. The agent substitutes the value at execution time.

### 4.4 Predefined Variables

These variables are resolved at workflow execution time:

| Variable | Source | Resolution |
|----------|--------|------------|
| `{planning_artifacts}` | `bmm/config.yaml` field `planning_artifacts` | Read from BMM config at workflow start |
| `{implementation_artifacts}` | `bmm/config.yaml` field `implementation_artifacts` | Read from BMM config at workflow start |
| `{project-root}` | Working directory root | Resolved from current git repo root |
| `{sep}` | Label separator | `::` if platform is `gitlab`, `:` if `github`. Resolved by reading `_bmad/custom/issue-tracking.yaml` at workflow start. |
| `{prd_key}` | PRD frontmatter | Extracted from `{planning_artifacts}/prd.md` frontmatter field `prd_key` |
| `{story_key}` | Sprint status | Resolved per-workflow by reading `{implementation_artifacts}/sprint-status.yaml` and matching the entry whose status equals the workflow's target status |
| `{epic_num}` | Derived from `story_key` | First dash-separated segment (e.g., `1` from `1-3-login-form`) |
| `{story_num}` | Derived from `story_key` | Second dash-separated segment (e.g., `3` from `1-3-login-form`) |
| `{prd_branch}` | Config pattern | `issue_tracking.branch_patterns.prd` with `{prd_key}` substituted |
| `{story_branch}` | Config pattern | `issue_tracking.branch_patterns.story` with `{prd_key}` and `{story_key}` substituted |

**Shell variables** (set by `git remote` and `glab`/`gh` CLI, resolved during sync task step 1):

| Variable | Source | Example |
|----------|--------|---------|
| `{HOST}` | Git remote URL | `gitlab.example.com` |
| `{PROJECT_ID}` | `glab api` response | `42` |
| `{PROJECT_PATH}` | Git remote path | `group/project` |
| `{OWNER}` | Git remote path | `octocat` |
| `{REPO}` | Git remote path | `my-repo` |

### 4.5 Resolution Failure

If a referenced variable is not defined at the point of reference, the workflow stops with an error naming the missing variable.

---

## 5. Error Handling

The following situations cause the workflow to stop immediately. No retry. No fallback. The agent does NOT improvise recovery -- it stops and reports the error.

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

---

## 6. Execution Trace

The agent MUST output a structured trace as it executes each step. This trace is the ONLY output the user sees during workflow execution. The agent MUST NOT output prose, commentary, or reasoning between steps — only the trace.

### Format

```
Step N: STEP_TYPE value

  ● RUN command
  ● READ file → extracting key1, key2
  ● CHECK condition → TRUE (pass) / FALSE
  ● SET variable = value
  ● INCLUDE sub-workflow → "result summary"

  Sub-workflow-name terminé. Variables en scope: key1=val1, key2=val2
```

Rules:
- **INCLUDE**: show the included sub-workflow name, then indent its trace. After the sub-workflow completes, show a one-line summary with the variables it added to scope.
- **READ**: show the file path and which keys were extracted. If the file was read for content (no EXTRACT), show `→ content loaded`.
- **CHECK**: show the condition and the result. If the branch taken matters for debugging, show it: `→ TRUE (pass)` or `→ FALSE → branch taken`.
- **SET**: show `variable = value`.
- **RUN**: show the command (truncated if long).
- **CD**: show the target path.
- **FILTER**: show `source → key = value`.
- **OUTPUT with store**: show `message → stored in variable`.
- **STOP with stop: true**: show `STOP — reason`.
- **WRITE**: show the file path and whether append/overwrite.

The trace MUST be compact — one line per step or sub-step. No prose explanations between steps.

**Object display:** When a variable is an object (dict/map), display its keys and values in compact format: `{key1=val1, key2=val2}`. Do NOT use `<object>`, `…`, or omit the value.

---

## 7. CLI Anti-Improvisation Rule

The agent MUST NOT use any CLI command that is not explicitly specified in a RUN step within the workflow file or in the sync task command table. The agent MUST NOT add diagnostic commands (e.g., `git status`, `echo`, `cat`), exploration commands, or any command not in the workflow. The only CLI commands the agent may execute are those written in RUN steps and those listed in the sync task's command table.

---

## 8. Language Version

This specification is version **1.0**. Workflow files MAY declare a minimum language version. If a workflow file declares `min_lang_version: X.Y` and the deployed language spec version is lower, the workflow stops with an error stating the version mismatch before executing any steps.

---

## 9. Sub-Workflow Contracts

Each sub-workflow file documents its contract in a YAML comment at the top:
- **Purpose:** what the sub-workflow does
- **Input variables:** variables the caller must set before INCLUDE (if any)
- **Output variables:** variables the sub-workflow defines that are available to the caller after INCLUDE
- **Side effects:** any observable effects beyond variable assignment (e.g., git pull, worktree switch)
