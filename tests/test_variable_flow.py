"""Validate workflow structural contracts and invariants.

P0 — checks that workflow files follow structural rules that prevent
runtime failures and silent data loss.
"""

import os
import re
import pytest
from conftest import load_all_workflows, flatten_steps


# Workflows that have no activation (they run in the current directory
# or are invoked differently). Add to this set if a new workflow is
# intentionally activation-less.
_NO_ACTIVATION = set()

# Workflows whose complete.yaml is allowed to skip check-config
# (they do no API calls and need no config vars).
_NO_CHECK_CONFIG_COMPLETE = {
    "create-architecture/complete.yaml",
    "create-ux-design/complete.yaml",
    "create-epics-and-stories/complete.yaml",
}

# Workflows that delegate to the sync task instead of using check-config directly.
# They INCLUDE issue-sync/sync which has its own check-config.
_SYNC_DELEGATES = {"sprint-planning/complete.yaml", "sprint-status/complete.yaml"}


class TestActivationExists:
    """P0: Every workflow with a complete.yaml must have an activation.yaml.

    Missing activations caused real runtime failures (sprint-status, edit-prd,
    correct-course, retrospective all ran BMM workflows in the wrong directory).
    """

    @pytest.mark.parametrize("rel, wf", list(load_all_workflows().items()), ids=lambda x: x[0] if isinstance(x, tuple) else str(x))
    def test_activation_exists_for_complete(self, rel, wf, all_workflows):
        """If a workflow has complete.yaml, it must also have activation.yaml (unless in _NO_ACTIVATION)."""
        if not rel.endswith("/complete.yaml"):
            return
        workflow_dir = os.path.dirname(rel)
        workflow_name = workflow_dir.replace("/", "")
        if workflow_name in _NO_ACTIVATION:
            return
        activation_path = f"{workflow_dir}/activation.yaml"
        assert activation_path in all_workflows, (
            f"{rel}: has complete.yaml but no activation.yaml. "
            f"Add activation.yaml or add '{workflow_name}' to _NO_ACTIVATION."
        )


class TestTmpFileCleanup:
    """P0: Every WRITE to /tmp/ must have a corresponding rm -f.

    Workflows create temporary description files in /tmp/ for API calls.
    Cleanup can happen either directly (rm -f in the same file) or via
    an INCLUDED sub-workflow (e.g. common/update-issue-description).
    If cleanup is missing entirely, files leak across invocations.
    """

    # Sub-workflows known to clean up {description_file} via rm -f
    _CLEANUP_INCLUDES = {"common/update-issue-description"}

    @pytest.mark.parametrize("rel, wf", list(load_all_workflows().items()), ids=lambda x: x[0] if isinstance(x, tuple) else str(x))
    def test_tmp_files_are_cleaned_up(self, rel, wf):
        """Every /tmp/ file written must be cleaned up directly or via INCLUDE."""
        written_tmp = set()
        removed_tmp = set()
        cleanup_via_include = False
        tmp_pattern = re.compile(r"/tmp/[\w.-]+")

        for step in flatten_steps(wf["steps"]):
            if step["type"] == "WRITE":
                for _, key, value in step.get("block", []):
                    if key == "file":
                        written_tmp.update(tmp_pattern.findall(value))
            elif step["type"] == "RUN":
                cmd = step["raw_value"]
                if "rm -f" in cmd or "rm -rf" in cmd:
                    removed_tmp.update(tmp_pattern.findall(cmd))
            elif step["type"] == "INCLUDE":
                target = step["raw_value"].strip()
                if target in self._CLEANUP_INCLUDES:
                    cleanup_via_include = True

        # If the file writes {description_file} and includes a cleanup sub-workflow,
        # the cleanup is delegated — skip the check for that pattern
        for f in written_tmp:
            if cleanup_via_include:
                continue
            assert f in removed_tmp, (
                f"{rel}: writes {f} but never cleans it up (missing 'rm -f {f}')"
            )


class TestSepUsageInLabels:
    """P1: Label references in RUN steps must use {sep} not hardcoded :: or :.

    Hardcoded 'status::done' works on GitLab but fails on GitHub (which uses 'status:done').
    Hardcoded 'status:done' works on GitHub but creates a wrong label on GitLab.
    The {sep} variable resolves to '::' on GitLab and ':' on GitHub.
    """

    @pytest.mark.parametrize("rel, wf", list(load_all_workflows().items()), ids=lambda x: x[0] if isinstance(x, tuple) else str(x))
    def test_no_hardcoded_separator_in_labels(self, rel, wf):
        """RUN steps must not use hardcoded '::' or ':' for label separators (use {sep})."""
        for step in flatten_steps(wf["steps"]):
            if step["type"] != "RUN":
                continue
            cmd = step["raw_value"]
            # Skip Python code blocks that construct labels programmatically
            if 'import' in cmd:
                continue
            # Skip if {sep} is already used (correct pattern)
            if '{sep}' in cmd:
                continue
            # Match word::word (GitLab separator) or word:word (GitHub separator)
            label_matches = re.findall(r'[\w][\w-]*::[\w-]+', cmd)
            single_colon = re.findall(r'[\w][\w-]*:[\w-]+', cmd)
            all_matches = label_matches + single_colon
            # Filter out URL schemes (https://, http://) from matches, not from commands
            all_matches = [m for m in all_matches if not m.endswith('://')]
            assert not all_matches, (
                f"{rel}:L{step['start_line']+1}: hardcoded separator in label reference: "
                f"{all_matches}. Use '{{sep}}' instead."
            )


class TestActivationSymmetry:
    """P1: PRD-scoped activations that need prd_key must all include find-prd.

    Activations that CD to a PRD worktree need prd_key and prd_worktree_path,
    which are set by common/find-prd. Missing find-prd means the agent operates
    in the wrong directory or without prd_key in scope.
    """

    _PRD_SCOPED_ACTIVATIONS = {
        "edit-prd", "check-implementation-readiness", "correct-course",
        "retrospective", "sprint-status", "create-architecture",
        "create-ux-design", "create-epics-and-stories", "sprint-planning",
        "create-story", "dev-story", "code-review",
    }
    # Activations that create their own PRD (no find-prd needed)
    _SELF_PRD_ACTIVATIONS = {"create-prd"}

    @pytest.mark.parametrize("rel, wf", list(load_all_workflows().items()), ids=lambda x: x[0] if isinstance(x, tuple) else str(x))
    def test_prd_scoped_activation_has_find_prd(self, rel, wf):
        """PRD-scoped activations must INCLUDE common/find-prd (unless self-PRD)."""
        if not rel.endswith("/activation.yaml"):
            return
        workflow_name = os.path.dirname(rel).replace("/", "")
        if workflow_name not in self._PRD_SCOPED_ACTIVATIONS:
            return
        if workflow_name in self._SELF_PRD_ACTIVATIONS:
            return
        includes = {step["raw_value"].strip() for step in wf["steps"] if step["type"] == "INCLUDE"}
        assert "common/find-prd" in includes, (
            f"{rel}: PRD-scoped activation but no INCLUDE common/find-prd. "
            f"prd_key and prd_worktree_path will not be set."
        )


class TestOutputVariablesUsed:
    """P1: Non-common workflow files should reference their documented output variables.

    If a workflow declares output variables in its contract header, those
    variables should be referenced somewhere in the file (by the agent or
    by subsequent steps).
    """

    def test_non_common_outputs_used(self, all_workflows):
        """Non-common workflow files should reference their INCLUDE outputs."""
        for rel, wf in all_workflows.items():
            if rel.startswith("common/"):
                continue
            contract_lines = wf["content"].split("\n")
            outputs = []
            in_output = False
            for line in contract_lines:
                stripped = line.strip().lstrip("#").strip()
                if stripped.lower().startswith("output variables"):
                    in_output = True
                    continue
                if in_output and stripped.startswith("-"):
                    var_name = stripped.lstrip("-").strip()
                    if ":" in var_name:
                        var_name = var_name.split(":")[0].strip()
                    outputs.append(var_name)
                elif in_output and stripped:
                    break
            if not outputs:
                continue
            content = wf["content"]
            for var in outputs:
                if var in ("none",):
                    continue
                pattern = re.compile(r"\{" + re.escape(var) + r"\b")
                if not pattern.search(content):
                    pytest.fail(
                        f"{rel}: output variable '{var}' not referenced in file"
                    )
