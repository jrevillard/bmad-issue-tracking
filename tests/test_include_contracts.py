"""Validate that common/ sub-workflows have proper contract headers.

P1 — checks that common/ files document their Purpose, Input variables,
Output variables, and Side effects.
"""

import pytest
from conftest import load_all_workflows, parse_contract_header


class TestIncludeContracts:
    """P1: common/ files have complete contract headers."""

    def test_common_subworkflows_have_purpose(self, all_workflows):
        """All common/ files must document their Purpose."""
        for rel, wf in all_workflows.items():
            if not rel.startswith("common/"):
                continue
            contract = parse_contract_header(wf["content"])
            assert contract["purpose"], f"{rel}: missing Purpose in contract header"

    def test_common_subworkflows_have_input_variables(self, all_workflows):
        """All common/ files must document their Input variables (even if none)."""
        for rel, wf in all_workflows.items():
            if not rel.startswith("common/"):
                continue
            contract = parse_contract_header(wf["content"])
            # The section header should exist, even if empty
            content_lower = wf["content"].lower()
            assert "input variables" in content_lower, (
                f"{rel}: missing 'Input variables' section in contract header"
            )

    def test_common_subworkflows_have_output_variables(self, all_workflows):
        """All common/ files must document their Output variables (even if none)."""
        for rel, wf in all_workflows.items():
            if not rel.startswith("common/"):
                continue
            content_lower = wf["content"].lower()
            assert "output variables" in content_lower, (
                f"{rel}: missing 'Output variables' section in contract header"
            )

    def test_common_subworkflows_have_side_effects(self, all_workflows):
        """All common/ files must document their Side effects."""
        for rel, wf in all_workflows.items():
            if not rel.startswith("common/"):
                continue
            content_lower = wf["content"].lower()
            assert "side effects" in content_lower, (
                f"{rel}: missing 'Side effects' section in contract header"
            )
