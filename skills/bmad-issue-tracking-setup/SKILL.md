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

<action>Verify that `bmad-bmm-issue-sync.md` and `bmad-bmm-issue-link.md` exist in `_bmad/_config/custom/`.</action>
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
- `bmad-create-story.toml` (requires BMM 6.4.0+)
- `bmad-dev-story.toml` (requires BMM 6.4.0+)
- `bmad-edit-prd.toml` (requires BMM 6.4.0+)
- `bmad-retrospective.toml` (requires BMM 6.4.0+)
- `bmad-sprint-planning.toml` (requires BMM 6.4.0+)
- `bmad-sprint-status.toml` (requires BMM 6.4.0+)

<action>Verify each TOML file is valid by checking it contains a `[workflow]` section and an `on_complete` key.</action>
</step>

<step n="4" goal="Configure issue_tracking in BMM config">
<action>Check if `_bmad/bmm/config.yaml` already contains an `issue_tracking` block.</action>
<check if="not found">
  <action>Append the following block to `_bmad/bmm/config.yaml`:</action>

```yaml
issue_tracking:
  enabled: true
  platform: gitlab  # or github — configure in next step
```
</check>
</step>

<step n="5" goal="Configure platform">
<action>Ask the user which platform they use: GitLab or GitHub.</action>
<action>Edit `_bmad/bmm/config.yaml` and set `issue_tracking.platform` to the chosen value.</action>
</step>

<step n="6" goal="Verify CLI connectivity">
<action>Run the platform auth check:</action>
- GitLab: `glab auth status`
- GitHub: `gh auth status`

<check if="auth fails">
  <output>WARN: CLI not authenticated. Issue tracking will fall back to file-system until authenticated.</output>
</check>
</step>

</task>
