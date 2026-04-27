---
name: bmad-issue-tracking-setup
description: 'One-time setup for issue tracking integration. Use after installing the module to deploy TOML overrides and shared tasks.'
---

# Issue Tracking Setup

One-time setup for BMAD Issue Tracking integration. Deploys TOML overrides to `_bmad/custom/` and shared tasks to `_bmad/_config/custom/`.

## Prerequisites

- BMAD Method module (BMM) 6.4.0+ installed
- This module installed via `npx bmad-method install --custom-source https://github.com/jrevillard/bmad-issue-tracking`

## Instructions

<task>

<step n="1" goal="Verify BMM installation">
<action>Check that `_bmad/bmm/config.yaml` exists and contains `# Version:` header with version 6.4.0+.</action>
<check if="version < 6.4.0 or not found">
  <output>ERROR: BMM 6.4.0+ required. TOML overrides need customize.toml support for all 6 workflows.</output>
  <action>Stop here</action>
</check>
</step>

<step n="2" goal="Deploy shared tasks">
<action>Locate the module's shared tasks. Check these locations in order:</action>
1. `~/.bmad/cache/custom-modules/github.com/jrevillard/bmad-issue-tracking/skills/bmad-issue-tracking-setup/assets/shared-tasks/`
2. Ask the user for the path to the cloned `bmad-issue-tracking` repo

<action>Copy all files to `_bmad/_config/custom/`:</action>

```bash
cp <path>/shared-tasks/*.md _bmad/_config/custom/
```

<action>Verify that `bmad-bmm-issue-sync.md` exists in `_bmad/_config/custom/`.</action>
</step>

<step n="3" goal="Deploy TOML overrides">
<action>Copy all TOML files from the same module's `assets/custom/` directory to `_bmad/custom/`:</action>

```bash
cp <path>/custom/*.toml _bmad/custom/
```

<action>The following TOML files should now exist in `_bmad/custom/`:</action>
- `bmad-check-implementation-readiness.toml` (requires BMM 6.4.0+)
- `bmad-code-review.toml` (requires BMM 6.4.0+)
- `bmad-correct-course.toml` (requires BMM 6.4.0+)
- `bmad-create-prd.toml` (requires BMM 6.4.0+)
- `bmad-create-story.toml` (requires BMM 6.4.0+)
- `bmad-dev-story.toml` (requires BMM 6.4.0+)
- `bmad-edit-prd.toml` (requires BMM 6.4.0+)
- `bmad-retrospective.toml` (requires BMM 6.4.0+)
- `bmad-sprint-planning.toml` (requires BMM 6.4.0+)
- `bmad-sprint-status.toml` (requires BMM 6.4.0+)

<action>Verify each TOML file is valid by checking it contains a `[workflow]` section and at least one hook key (`on_complete`, `activation_steps_append`, etc.).</action>
</step>

<step n="4" goal="Configure issue_tracking in BMM config">
<action>Check if `_bmad/bmm/config.yaml` already contains an `issue_tracking` block.</action>
<check if="not found">
  <action>Append the following block to `_bmad/bmm/config.yaml`:</action>

```yaml
issue_tracking:
  enabled: true
  platform: gitlab  # or github — configure in next step
  # host and project configured in step 5
```
</check>
</step>

<step n="5" goal="Configure platform and connection">
<action>Detect the git remote by running `git remote get-url origin`.</action>
<action>Ask the user which platform they use for issue tracking: GitLab or GitHub.</action>
<action>Set `issue_tracking.platform` to the chosen value.</action>
<check if="platform differs from git remote host">
  <output>NOTE: The issue tracker ({platform}) differs from the git remote ({git_host}). This is valid — e.g. code on GitLab but issues on GitHub.</output>
</check>
<action>Ask the user for the issue tracker host and project path. Set `issue_tracking.host` and `issue_tracking.project` in `_bmad/bmm/config.yaml`.</action>
</step>

<step n="6" goal="Verify CLI connectivity">
<action>Run the platform auth check:</action>
- GitLab: `glab auth status`
- GitHub: `gh auth status`

<check if="auth fails">
  <output>WARN: CLI not authenticated. Issue tracking will fall back to file-system until authenticated.</output>
</check>
</step>

<step n="6b" goal="Configure branch patterns">
<action>Explain: "Branch patterns control automatic branch and MR/PR creation when developing PRD stories. Placeholders: `{prd_key}` (e.g. `auth-refactor`), `{story_key}` (e.g. `3-4-automatic-department-routing`)."</action>

<action>Ask the user for their PRD branch pattern. Default: `feat/{prd_key}/prd`</action>
<action>Ask the user for their story branch pattern. Default: `feat/{prd_key}/{story_key}`</action>

<check if="PRD pattern does not contain `{prd_key}`">
  <output>WARN: PRD branch pattern must contain `{prd_key}` placeholder. Using default.</output>
  <action>Set PRD pattern to `feat/{prd_key}/prd`</action>
</check>

<check if="story pattern does not contain `{prd_key}` or does not contain `{story_key}`">
  <output>WARN: Story branch pattern must contain both `{prd_key}` and `{story_key}` placeholders. Using default.</output>
  <action>Set story pattern to `feat/{prd_key}/{story_key}`</action>
</check>

<action>Write `branch_patterns` under `issue_tracking` in `_bmad/bmm/config.yaml`:</action>

```yaml
issue_tracking:
  enabled: true
  platform: <platform>
  host: <host>
  project: <project>
  branch_patterns:
    prd: "<resolved PRD pattern>"
    story: "<resolved story pattern>"
```

<action>Verify the section was written correctly by reading it back.</action>
</step>

</task>
