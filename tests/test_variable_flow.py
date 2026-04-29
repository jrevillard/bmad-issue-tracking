"""Validate that INCLUDE paths and contract headers are consistent.

P0 — checks that INCLUDE references point to existing files and that
common/ sub-workflows document their contracts.
"""

import re
import pytest
from conftest import PREDEFINED_VARS, load_all_workflows, parse_contract_header


class TestIncludePaths:
    """P0: All INCLUDE paths point to existing workflow files."""

    @pytest.mark.parametrize("rel, wf", list(load_all_workflows().items()), ids=lambda x: x[0] if isinstance(x, tuple) else str(x))
    def test_include_paths_exist(self, rel, wf, all_workflows):
        """Every INCLUDE must reference an existing YAML or .md file."""
        for step in wf["steps"]:
            if step["type"] != "INCLUDE":
                continue
            path = step["raw_value"].strip()
            if path.endswith(".md"):
                continue
            assert path in all_workflows or path + ".yaml" in all_workflows, (
                f"{rel}:L{step['start_line']+1}: INCLUDE '{path}' not found"
            )

    def test_common_subworkflows_have_contracts(self, all_workflows):
        """All common/ files must document their Purpose."""
        for rel, wf in all_workflows.items():
            if not rel.startswith("common/"):
                continue
            contract = parse_contract_header(wf["content"])
            assert contract["purpose"], f"{rel}: missing Purpose in contract header"

    def test_non_common_outputs_used(self, all_workflows):
        """Non-common workflow files should reference their INCLUDE outputs.

        Top-level workflow files that INCLUDE a sub-workflow and receive
        output variables should reference at least one of them.
        """
        for rel, wf in all_workflows.items():
            if rel.startswith("common/"):
                continue  # common outputs are used by callers, not self
            contract = parse_contract_header(wf["content"])
            outputs = contract["output_variables"]
            if not outputs:
                continue
            content = wf["content"]
            for var in outputs:
                pattern = re.compile(r"\{" + re.escape(var) + r"\b")
                if not pattern.search(content):
                    pytest.fail(
                        f"{rel}: output variable '{var}' from INCLUDE not referenced in file"
                    )
