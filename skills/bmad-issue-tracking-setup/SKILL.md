---
name: bmad-issue-tracking-setup
description: 'One-time setup for issue tracking integration. Use after installing the module to apply TOML overrides and patches.'
---

# Issue Tracking Setup

One-time setup for BMAD Issue Tracking integration. Applies TOML overrides and patches to BMM workflow files.

## Prerequisites

- BMAD Method module (BMM) 6.3+ installed
- This module installed via `npx bmad-method install --custom-source https://github.com/jrevillard/bmad-issue-tracking`

## Instructions

<task>

<step n="1" goal="Verify BMM installation">
<action>Check that `_bmad/bmm/config.yaml` exists and contains `# Version:` header with version 6.3+.</action>
<check if="version < 6.3 or not found">
  <output>ERROR: BMM 6.3+ required. TOML overrides need customize.toml support.</output>
  <action>Stop here</action>
</check>
</step>

<step n="2" goal="Run the install script">
<action>Locate the patch script. Check these locations in order:</action>
1. `~/.bmad/cache/custom-modules/github.com/jrevillard/bmad-issue-tracking/skills/bmad-issue-tracking-setup/assets/patches/patch-bmm.sh`
2. Ask the user for the path to the cloned `bmad-issue-tracking` repo

<action>Run the script with `--force` to overwrite existing files:</action>

```bash
bash <path>/patch-bmm.sh --force
```

<action>Review the output. All items should show APPLIED. If any show FAILED, the BMM version may have changed — inspect with `git apply --stat <patch-file>`.</action>
</step>

<step n="3" goal="Verify configuration">
<action>Confirm `_bmad/bmm/config.yaml` now contains the `issue_tracking` block.</action>
<action>Confirm `_bmad/custom/bmad-create-story.toml` and `_bmad/custom/bmad-retrospective.toml` exist.</action>
<action>Confirm `_bmad/_config/custom/bmad-bmm-issue-sync.md` and `_bmad/_config/custom/bmad-bmm-issue-link.md` exist.</action>
</step>

<step n="4" goal="Configure platform">
<action>Ask the user which platform they use: GitLab or GitHub.</action>
<action>Edit `_bmad/bmm/config.yaml` and set `issue_tracking.platform` to the chosen value.</action>
</step>

<step n="5" goal="Verify CLI connectivity">
<action>Run the platform auth check:</action>
- GitLab: `glab auth status`
- GitHub: `gh auth status`

<check if="auth fails">
  <output>WARN: CLI not authenticated. Issue tracking will fall back to file-system until authenticated.</output>
</check>
</step>

<step n="6" goal="Remind about PRD key">
<action>Remind the user to add `prd_key` to their PRD frontmatter if not already present:</action>

```markdown
---
prd_key: my-initiative
---
```

</step>

</task>
