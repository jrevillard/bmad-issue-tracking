---
name: bmad-issue-tracking-setup
description: 'One-time setup for issue tracking integration. Use after installing the module to deploy TOML overrides and shared tasks.'
---

# Issue Tracking Setup

One-time setup for BMAD Issue Tracking integration. Deploys TOML overrides to `_bmad/custom/` and a shared task to `_bmad/_config/custom/`.

## Prerequisites

- BMAD Method module (BMM) 6.11.0+ installed
- `uv` available (required by BMM 6.11.0+ skills; the workflow YAMLs invoke Python via `uv run python`)
- This module installed via `npx bmad-method install --custom-source https://github.com/jrevillard/bmad-issue-tracking`

## Instructions

<task>
<action>IMPORTANT: When a step asks you to configure a value with a default, you MUST present the default as a suggestion and wait for the user's answer before writing anything. Never silently apply a default.</action>

<step n="1" goal="Verify BMM installation">
<action>Check that `_bmad/bmm/config.yaml` exists and contains `# Version:` header with version 6.11.0+.</action>
<check if="version < 6.11.0 or not found">
  <output>ERROR: BMM 6.11.0+ required. This module targets the 6.11.0 skill set (bmad-ux, consolidated sprint-planning, uv-based tooling).</output>
  <action>Stop here</action>
</check>
<action>Verify `uv` is available by running `uv --version`. If missing, report the BMM 6.11.0 requirement (`uv` is mandatory for BMM 6.11.0+ skills).</action>
</step>

<step n="2" goal="Remove obsolete sync task file">
<action>The sync logic has been converted to workflow YAML files. The old markdown file `bmad-bmm-issue-sync.md` is no longer needed.</action>

<action>Remove the file if it exists in the consuming project:</action>

```bash
rm -f _bmad/_config/custom/bmad-bmm-issue-sync.md
```

<action>Confirm that the file no longer exists.</action>
</step>

<step n="3" goal="Deploy TOML overrides">
<action>Locate the TOML overrides. Check these locations in order:</action>
1. `~/.bmad/cache/custom-modules/github.com/jrevillard/bmad-issue-tracking/skills/bmad-issue-tracking-setup/assets/custom/`
2. Ask the user for the path to the cloned `bmad-issue-tracking` repo

<action>IMPORTANT: Always overwrite existing TOML files — this is an update, not a first install. New versions may have changed TOML content.</action>

<action>Copy all TOML files to `_bmad/custom/`, overwriting existing files:</action>

```bash
cp -f <path>/*.toml _bmad/custom/
```

<action>Remove any `bmad-*.toml` files in `_bmad/custom/` that no longer exist in the source (files may have been renamed or removed in a new version).</action>

<action>The following TOML files should now exist in `_bmad/custom/`:</action>
- `bmad-code-review.toml` (requires BMM 6.11.0+)
- `bmad-correct-course.toml` (requires BMM 6.11.0+)
- `bmad-create-architecture.toml` (requires BMM 6.11.0+)
- `bmad-create-epics-and-stories.toml` (requires BMM 6.11.0+)
- `bmad-create-prd.toml` (requires BMM 6.11.0+, superseded by bmad-prd.toml)
- `bmad-create-story.toml` (requires BMM 6.11.0+; shim — deprecated upstream, bmad-build is the official path)
- `bmad-dev-story.toml` (requires BMM 6.11.0+; shim — deprecated upstream, bmad-build is the official path)
- `bmad-edit-prd.toml` (requires BMM 6.11.0+, superseded by bmad-prd.toml)
- `bmad-prd.toml` (requires BMM 6.11.0+; unified PRD override)
- `bmad-retrospective.toml` (requires BMM 6.11.0+)
- `bmad-sprint-planning.toml` (requires BMM 6.11.0+; owns the sprint-status artifact)
- `bmad-sprint-status.toml` (requires BMM 6.11.0+; consolidated into bmad-sprint-planning, retained as shim alias)
- `bmad-ux.toml` (requires BMM 6.11.0+; replaces bmad-create-ux-design, removed in 6.11.0)

<action>Note: All TOML files are in pointer format — they reference workflow YAML files deployed in step 3b.</action>
<action>Verify each TOML file is valid by checking it contains a `[workflow]` section and at least one hook key (`on_complete`, `activation_steps_append`, etc.).</action>
</step>

<step n="3b" goal="Deploy workflow language files">
<action>The TOML overrides reference workflow language YAML files. These are deployed separately to keep the TOML files as simple pointers.</action>

<action>Locate the workflow language files. They are siblings of the `custom/` directory (in the same `assets/` parent):</action>
1. `~/.bmad/cache/custom-modules/github.com/jrevillard/bmad-issue-tracking/skills/bmad-issue-tracking-setup/assets/`
2. Ask the user for the path to the cloned `bmad-issue-tracking` repo

<action>IMPORTANT: Always overwrite existing files — new versions may have changed workflow content.</action>

<action>Copy the workflow language specification and workflow YAML files, overwriting existing files:</action>

```bash
cp -f <path>/bmad-workflow-lang.md _bmad/_config/custom/
mkdir -p _bmad/_config/custom/workflows
cp -rf <path>/workflows/* _bmad/_config/custom/workflows/
```

<action>Remove any workflow YAML files in `_bmad/_config/custom/workflows/` that no longer exist in the source (files may have been renamed or removed in a new version).</action>

<action>Verify the following files exist:</action>
- `_bmad/_config/custom/bmad-workflow-lang.md`
- `_bmad/_config/custom/workflows/common/check-config.yaml`
- `_bmad/_config/custom/workflows/common/check-mr-ci.yaml`
- `_bmad/_config/custom/workflows/common/create-issue.yaml`
- `_bmad/_config/custom/workflows/common/create-label.yaml`
- `_bmad/_config/custom/workflows/common/ensure-board.yaml`
- `_bmad/_config/custom/workflows/common/ensure-dynamic-labels.yaml`
- `_bmad/_config/custom/workflows/common/ensure-labels.yaml`
- `_bmad/_config/custom/workflows/common/find-issue.yaml`
- `_bmad/_config/custom/workflows/common/find-prd.yaml`
- `_bmad/_config/custom/workflows/common/find-prd-key.yaml`
- `_bmad/_config/custom/workflows/common/find-stories.yaml`
- `_bmad/_config/custom/workflows/common/mark-mr-ready.yaml`
- `_bmad/_config/custom/workflows/common/set-story-status.yaml`
- `_bmad/_config/custom/workflows/common/sync-issues.yaml`
- `_bmad/_config/custom/workflows/common/update-issue-description.yaml`
- `_bmad/_config/custom/workflows/common/update-issue-status.yaml`
- `_bmad/_config/custom/workflows/common/wait-for-green-ci.yaml`
- `_bmad/_config/custom/workflows/issue-sync/prepare.yaml`
- `_bmad/_config/custom/workflows/issue-sync/sync.yaml`
- `_bmad/_config/custom/workflows/bmad-prd/activation.yaml`
- `_bmad/_config/custom/workflows/bmad-prd/complete.yaml`
- `_bmad/_config/custom/workflows/bmad-ux/activation.yaml`
- `_bmad/_config/custom/workflows/bmad-ux/complete.yaml`
- `_bmad/_config/custom/workflows/code-review/activation.yaml`
- `_bmad/_config/custom/workflows/code-review/complete.yaml`
- `_bmad/_config/custom/workflows/correct-course/activation.yaml`
- `_bmad/_config/custom/workflows/correct-course/complete.yaml`
- `_bmad/_config/custom/workflows/create-architecture/activation.yaml`
- `_bmad/_config/custom/workflows/create-architecture/complete.yaml`
- `_bmad/_config/custom/workflows/create-epics-and-stories/activation.yaml`
- `_bmad/_config/custom/workflows/create-epics-and-stories/complete.yaml`
- `_bmad/_config/custom/workflows/create-prd/activation.yaml`
- `_bmad/_config/custom/workflows/create-prd/complete.yaml`
- `_bmad/_config/custom/workflows/create-story/activation.yaml`
- `_bmad/_config/custom/workflows/create-story/complete.yaml`
- `_bmad/_config/custom/workflows/dev-story/activation.yaml`
- `_bmad/_config/custom/workflows/dev-story/complete.yaml`
- `_bmad/_config/custom/workflows/edit-prd/activation.yaml`
- `_bmad/_config/custom/workflows/edit-prd/complete.yaml`
- `_bmad/_config/custom/workflows/retrospective/activation.yaml`
- `_bmad/_config/custom/workflows/retrospective/complete.yaml`
- `_bmad/_config/custom/workflows/sprint-planning/activation.yaml`
- `_bmad/_config/custom/workflows/sprint-planning/complete.yaml`
- `_bmad/_config/custom/workflows/sprint-status/activation.yaml`
- `_bmad/_config/custom/workflows/sprint-status/complete.yaml`
</step>

<step n="3c" goal="Deploy bmad-loop CI status + story tracking (optional)">
<action>The module ships three pieces for bmad-loop, deployed only if the consuming project uses bmad-loop (has a `.bmad-loop/` directory after `bmad-loop init`):

- **`story-track-dev` plugin** — an LLM workflow session at `post_dev_phase` that pushes the code dev, waits for the CI pipeline to complete, writes the result to `ci-status.json`, and creates the trace MR. It runs for EVERY story that completes dev, regardless of whether review happens afterward.
- **`story-track-review` plugin** — an LLM workflow session at `post_review_result` that commits review modifications, pushes, waits for CI, writes `ci-status.json`, and mirrors the story to its GitLab/GitHub issue (status label, result comment, MR link). It runs ONLY when review completes.
- **`ci-status.sh`** — a `[verify]` command that reads `ci-status.json` (written by the last plugin that ran). It returns exit 0 if CI is green, exit 1 if red (with diagnostic). bmad-loop answers a red CI with a feedback-driven repair session (re-runs `bmad-build-auto` with the failing output) — the auto-fix loop.

The two-stage architecture ensures:
- Stories that complete dev (with or without review) get pushed + CI + MR
- Stories that complete review get review modifications committed + pushed + CI + issue tracking
- ci-status.sh reads the latest ci-status.json (after last push)

The scripts derive branch/host/project/platform from git and their working directory — no environment variables required.</action>

<check if=".bmad-loop/ directory exists">
  <true>
    <action>Copy `ci-status.sh` to the repo root and register it in `[verify] commands` + `[scm] worktree_seed` (verify commands run inside each story worktree, so the script must be seeded into worktrees); copy the two `story-track-*` plugins into `.bmad-loop/plugins/`:</action>
    ```bash
    mkdir -p .bmad-loop .bmad-loop/plugins
    cp -f <path>/bmad-loop/ci-gate/ci-status.sh .bmad-loop/ci-status.sh
    cp -rf <path>/bmad-loop/story-track-dev .bmad-loop/plugins/story-track-dev
    cp -rf <path>/bmad-loop/story-track-review .bmad-loop/plugins/story-track-review
    ```
    <action>Edit `.bmad-loop/policy.toml` (preserve existing keys):</action>
    ```toml
    [scm]
    worktree_seed = [".bmad-loop/ci-status.sh"]

    [verify]
    commands = ["bash .bmad-loop/ci-status.sh"]
    ```
    <action>Verify `.bmad-loop/ci-status.sh` and `.bmad-loop/plugins/story-track-*/plugin.toml` exist.</action>
    <action>Note: the `story-track-*` plugins are declarative (no `[python]` module) — they load automatically, no trust allowlist. The `ci-status.sh` script is deterministic and fast — it just reads a file. The intelligent work (polling CI, parsing logs) is done by the LLM workflows.</action>
  </true>
  <false>
    <output>Skipping ci-status + story-track — project does not use bmad-loop (no `.bmad-loop/` directory).</output>
  </false>
</check>
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
<action>Run the platform auth check (use `--hostname {host}` for self-hosted instances):</action>
- GitLab: `glab auth status --hostname {host}`
- GitHub: `gh auth status --hostname {host}`

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
