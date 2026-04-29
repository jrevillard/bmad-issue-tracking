---
name: bmad-issue-tracking-setup
description: 'One-time setup for issue tracking integration. Use after installing the module to deploy TOML overrides and shared tasks.'
---

# Issue Tracking Setup

One-time setup for BMAD Issue Tracking integration. Deploys TOML overrides to `_bmad/custom/` and a shared task to `_bmad/_config/custom/`.

## Prerequisites

- BMAD Method module (BMM) 6.4.0+ installed
- This module installed via `npx bmad-method install --custom-source https://github.com/jrevillard/bmad-issue-tracking`

## Instructions

<task>
<action>IMPORTANT: When a step asks you to configure a value with a default, you MUST present the default as a suggestion and wait for the user's answer before writing anything. Never silently apply a default.</action>

<step n="1" goal="Verify BMM installation">
<action>Check that `_bmad/bmm/config.yaml` exists and contains `# Version:` header with version 6.4.0+.</action>
<check if="version < 6.4.0 or not found">
  <output>ERROR: BMM 6.4.0+ required. TOML overrides need customize.toml support for all 6 workflows.</output>
  <action>Stop here</action>
</check>
</step>

<step n="2" goal="Deploy shared task">
<action>Locate the sync skill. Check these locations in order:</action>
1. `~/.bmad/cache/custom-modules/github.com/jrevillard/bmad-issue-tracking/skills/bmad-bmm-issue-sync/SKILL.md`
2. Ask the user for the path to the cloned `bmad-issue-tracking` repo

<action>Copy the skill file to `_bmad/_config/custom/`:</action>

```bash
cp <path>/SKILL.md _bmad/_config/custom/bmad-bmm-issue-sync.md
```

<action>Verify that `bmad-bmm-issue-sync.md` exists in `_bmad/_config/custom/`.</action>
</step>

<step n="3" goal="Deploy TOML overrides">
<action>Locate the TOML overrides. Check these locations in order:</action>
1. `~/.bmad/cache/custom-modules/github.com/jrevillard/bmad-issue-tracking/skills/bmad-issue-tracking-setup/assets/custom/`
2. Ask the user for the path to the cloned `bmad-issue-tracking` repo

<action>Copy all TOML files to `_bmad/custom/`:</action>

```bash
cp <path>/*.toml _bmad/custom/
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

<action>Note: All TOML files are in pointer format — they reference workflow YAML files deployed in step 3b.</action>
<action>Verify each TOML file is valid by checking it contains a `[workflow]` section and at least one hook key (`on_complete`, `activation_steps_append`, etc.).</action>
</step>

<step n="3b" goal="Deploy workflow language files">
<action>The TOML overrides reference workflow language YAML files. These are deployed separately to keep the TOML files as simple pointers.</action>

<action>Locate the workflow language files. They are siblings of the `custom/` directory (in the same `assets/` parent):</action>
1. `~/.bmad/cache/custom-modules/github.com/jrevillard/bmad-issue-tracking/skills/bmad-issue-tracking-setup/assets/`
2. Ask the user for the path to the cloned `bmad-issue-tracking` repo

<action>Copy the workflow language specification and workflow YAML files:</action>

```bash
cp <path>/bmad-workflow-lang.md _bmad/_config/custom/
mkdir -p _bmad/_config/custom/workflows
cp -r <path>/workflows/* _bmad/_config/custom/workflows/
```

<action>Verify the following files exist:</action>
- `_bmad/_config/custom/bmad-workflow-lang.md`
- `_bmad/_config/custom/workflows/common/check-config.yaml`
- `_bmad/_config/custom/workflows/common/create-issue.yaml`
- `_bmad/_config/custom/workflows/common/find-prd.yaml`
- `_bmad/_config/custom/workflows/common/find-stories.yaml`
- `_bmad/_config/custom/workflows/common/update-issue-description.yaml`
- `_bmad/_config/custom/workflows/common/update-issue-status.yaml`
- `_bmad/_config/custom/workflows/check-implementation-readiness/complete.yaml`
- `_bmad/_config/custom/workflows/code-review/activation.yaml`
- `_bmad/_config/custom/workflows/code-review/complete.yaml`
- `_bmad/_config/custom/workflows/correct-course/complete.yaml`
- `_bmad/_config/custom/workflows/create-prd/activation.yaml`
- `_bmad/_config/custom/workflows/create-prd/complete.yaml`
- `_bmad/_config/custom/workflows/create-story/activation.yaml`
- `_bmad/_config/custom/workflows/create-story/complete.yaml`
- `_bmad/_config/custom/workflows/dev-story/activation.yaml`
- `_bmad/_config/custom/workflows/dev-story/complete.yaml`
- `_bmad/_config/custom/workflows/edit-prd/complete.yaml`
- `_bmad/_config/custom/workflows/retrospective/complete.yaml`
- `_bmad/_config/custom/workflows/sprint-planning/complete.yaml`
- `_bmad/_config/custom/workflows/sprint-status/complete.yaml`
</step>

<step n="4" goal="Configure issue_tracking">
<action>Check if `_bmad/custom/issue-tracking.yaml` already exists.</action>
<check if="config file exists">
  <false>
    <action>Create `_bmad/custom/issue-tracking.yaml` with the following content (this file is independent from BMM and survives BMM updates):</action>

    ```yaml
    issue_tracking:
      enabled: true
      platform: gitlab  # or github — configure in next step
      # worktree_base, host, project configured in steps 4-5
    ```
  </false>
</check>
<check if="worktree_base is already set">
  <true>
    <output>worktree_base already configured: {worktree_base}.</output>
  </true>
  <false>
    <action>Ask the user for their worktree base directory. Default: `_bmad/worktrees`</action>
    <action>Set `issue_tracking.worktree_base` to the user's answer in `_bmad/custom/issue-tracking.yaml`.</action>
  </false>
</check>
<action>Ensure the worktree base directory is in `.gitignore`. Read the configured `worktree_base` value and check if it is listed. If not, append it.</action>
</step>

<step n="5" goal="Configure platform and connection">
<action>Detect the git remote by running `git remote get-url origin`.</action>
<action>Determine the git remote platform from the remote URL (gitlab.com → gitlab, github.com → github, GHE/GitLab self-hosted → ask user).</action>
<action>Extract `git_host` (hostname) and `git_project` (group/project or owner/repo) from the remote URL.</action>
<action>Always set `issue_tracking.git_platform` to the git remote platform in `_bmad/custom/issue-tracking.yaml`.</action>
<check if="platform is already set">
  <true>
    <output>Platform already configured: {platform}.</output>
  </true>
  <false>
    <action>Ask the user which platform they use for issue tracking: GitLab or GitHub.</action>
    <action>Set `issue_tracking.platform` to the chosen value.</action>
  </false>
</check>
<check if="git_platform is already set">
  <true>
    <output>git_platform already configured: {git_platform}.</output>
  </true>
  <false>
    <action>Set `issue_tracking.git_platform` to the git remote platform in `_bmad/custom/issue-tracking.yaml`.</action>
  </false>
</check>
<check if="platform differs from git remote platform">
  <output>NOTE: The issue tracker ({platform}) differs from the git remote ({git_platform}). This is valid — e.g. code on GitLab but issues on GitHub. MRs/PRs will target the git remote, so `git_host` and `git_project` are also needed.</output>
  <check if="git_host is already set">
    <true>
      <output>git_host already configured: {git_host}.</output>
    </true>
    <false>
      <action>Set `issue_tracking.git_host` to the git remote hostname (already extracted from the remote URL above).</action>
    </false>
  </check>
  <check if="git_project is already set">
    <true>
      <output>git_project already configured: {git_project}.</output>
    </true>
    <false>
      <action>Set `issue_tracking.git_project` to the git remote project path (already extracted from the remote URL above).</action>
    </false>
  </check>
</check>
<check if="platform does NOT differ from git remote platform">
  <check if="git_host is set">
    <output>NOTE: Platform and git remote match — `git_host` is no longer needed. Removing it.</output>
    <action>Remove `issue_tracking.git_host` from `_bmad/custom/issue-tracking.yaml`.</action>
  </check>
  <check if="git_project is set">
    <output>NOTE: Platform and git remote match — `git_project` is no longer needed. Removing it.</output>
    <action>Remove `issue_tracking.git_project` from `_bmad/custom/issue-tracking.yaml`.</action>
  </check>
</check>
<check if="host is already set">
  <true>
    <output>host already configured: {host}.</output>
  </true>
  <false>
    <action>Ask the user for the issue tracker host (e.g. `gitlab.company.com` or `github.com`). Set `issue_tracking.host` in `_bmad/custom/issue-tracking.yaml`.</action>
  </false>
</check>
<check if="project is already set">
  <true>
    <output>project already configured: {project}.</output>
  </true>
  <false>
    <action>Ask the user for the issue tracker project path (e.g. `my-group/my-project`). Set `issue_tracking.project` in `_bmad/custom/issue-tracking.yaml`.</action>
  </false>
</check>
</step>

<step n="6" goal="Verify CLI connectivity">
<action>Run the platform auth check (use `--hostname $HOST` for self-hosted instances):</action>
- GitLab: `glab auth status --hostname $HOST`
- GitHub: `gh auth status --hostname $HOST`

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

<action>Write `branch_patterns` under `issue_tracking` in `_bmad/custom/issue-tracking.yaml`:</action>

```yaml
issue_tracking:
  enabled: true
  platform: <platform>
  git_platform: <git_platform>  # git remote platform (same as platform in nominal case)
  host: <host>
  project: <project>
  worktree_base: <configured_worktree_base>
  # Only present when git remote differs from issue tracker:
  # git_host: <git_hostname>
  # git_project: <git_group>/<git_project>
  branch_patterns:
    prd: "<resolved PRD pattern>"
    story: "<resolved story pattern>"
```

<action>Verify the section was written correctly by reading it back.</action>
</step>

</task>
