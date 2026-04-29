"""Validate INCLUDE sub-workflow contracts.

P1 — checks that INCLUDE paths exist and common/ files have contract headers.
"""

import pytest
from conftest import load_all_workflows, parse_contract_header


class TestIncludeContracts:
    """P1: INCLUDE paths exist and common/ files have contracts."""

    def test_all_includes_point_to_existing_files(self, all_workflows):
        """Every INCLUDE must reference an existing YAML file or .md prose file."""
        for rel, wf in all_workflows.items():
            for step in wf["steps"]:
                if step["type"] != "INCLUDE":
                    continue
                path = step["raw_value"].strip()
                if path.endswith(".md"):
                    continue  # prose includes are valid
                if path not in all_workflows and path + ".yaml" not in all_workflows:
                    pytest.fail(f"{rel}:L{step['start_line']+1}: INCLUDE '{path}' not found")

    def test_common_subworkflows_have_contracts(self, all_workflows):
        """All files in common/ must document Purpose in their contract header."""
        for rel, wf in all_workflows.items():
            if not rel.startswith("common/"):
                continue
            contract = parse_contract_header(wf["content"])
            assert contract["purpose"], f"{rel}: missing Purpose in contract header"
