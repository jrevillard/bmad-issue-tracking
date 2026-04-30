"""Validate YAML syntax and step type correctness for all workflow files.

NOTE: The workflow YAML format uses inline Python blocks that break
yaml.safe_load. We use a lightweight regex parser that captures top-level
steps and their immediate fields but does NOT recurse into CHECK/LOOP
branches. Branch-level validation requires a full YAML-aware parser.
"""

import pytest
from conftest import VALID_STEP_TYPES, ALL_VALID_FIELDS, load_all_workflows, flatten_steps


class TestYamlSyntax:
    """P0: YAML files contain recognized step types with valid fields."""

    def test_all_files_have_steps(self, all_workflows):
        """Every .yaml file must contain at least one step."""
        for rel, wf in all_workflows.items():
            assert len(wf["steps"]) > 0, f"{rel}: no steps found"

    def test_all_steps_have_valid_type(self, all_workflows):
        """Every step must use a recognized step type keyword."""
        for rel, wf in all_workflows.items():
            for step in flatten_steps(wf["steps"]):
                assert step["type"] in VALID_STEP_TYPES, (
                    f"{rel}:L{step['start_line']+1}: invalid step type '{step['type']}'"
                )

    def test_platform_values(self, all_workflows):
        """PLATFORM annotation must be 'gitlab' or 'github' only."""
        for rel, wf in all_workflows.items():
            for step in flatten_steps(wf["steps"]):
                for _, key, value in step["block"]:
                    if key == "PLATFORM":
                        assert value in ("gitlab", "github"), (
                            f"{rel}:L{step['start_line']+1}: invalid PLATFORM '{value}'"
                        )

    def test_check_has_condition(self, all_workflows):
        """CHECK steps must have a non-empty condition."""
        for rel, wf in all_workflows.items():
            for step in flatten_steps(wf["steps"]):
                if step["type"] == "CHECK":
                    assert step["raw_value"].strip(), (
                        f"{rel}:L{step['start_line']+1}: CHECK has empty condition"
                    )

    def test_set_has_variable(self, all_workflows):
        """SET steps must specify a variable name."""
        for rel, wf in all_workflows.items():
            for step in flatten_steps(wf["steps"]):
                if step["type"] == "SET":
                    import re
                    m = re.search(r"variable:\s*(\w+)", step["raw_value"])
                    assert m, f"{rel}:L{step['start_line']+1}: SET has no variable"

    def test_cd_has_path(self, all_workflows):
        """CD steps must reference a variable or contain a path."""
        for rel, wf in all_workflows.items():
            for step in flatten_steps(wf["steps"]):
                if step["type"] == "CD":
                    assert step["raw_value"].strip(), (
                        f"{rel}:L{step['start_line']+1}: CD has no path"
                    )
