"""Validate CLI command patterns in RUN steps.

P2 — checks glab/gh command conventions. Top-level only.
"""

import pytest
from conftest import load_all_workflows


class TestCommandPatterns:
    """P2: CLI commands follow platform conventions."""

    @pytest.mark.parametrize("rel, wf", list(load_all_workflows().items()), ids=lambda x: x[0] if isinstance(x, tuple) else str(x))
    def test_glab_api_uses_hostname(self, rel, wf):
        """glab api commands must include --hostname."""
        for step in wf["steps"]:
            if step["type"] != "RUN":
                continue
            cmd = step["raw_value"]
            if "glab api" in cmd:
                assert "--hostname" in cmd, f"{rel}:L{step['start_line']+1}: glab api without --hostname"

    @pytest.mark.parametrize("rel, wf", list(load_all_workflows().items()), ids=lambda x: x[0] if isinstance(x, tuple) else str(x))
    def test_glab_subcommands_use_r(self, rel, wf):
        """glab mr/label/issue subcommands must include -R."""
        for step in wf["steps"]:
            if step["type"] != "RUN":
                continue
            cmd = step["raw_value"]
            if "glab api" not in cmd and any(f"glab {s}" in cmd for s in ("mr ", "label ", "issue ")):
                assert "-R" in cmd, f"{rel}:L{step['start_line']+1}: glab subcommand without -R"

    @pytest.mark.parametrize("rel, wf", list(load_all_workflows().items()), ids=lambda x: x[0] if isinstance(x, tuple) else str(x))
    def test_gh_commands_use_r(self, rel, wf):
        """gh issue/pr commands that need repo context must include -R."""
        for step in wf["steps"]:
            if step["type"] != "RUN":
                continue
            cmd = step["raw_value"]
            if not cmd.strip().startswith("gh "):
                continue
            if any(f"gh {s}" in cmd for s in ("issue create", "issue edit", "issue close",
                                                     "issue reopen", "issue comment",
                                                     "pr create", "pr merge", "pr list",
                                                     "pr ready")):
                assert "-R" in cmd, f"{rel}:L{step['start_line']+1}: gh command without -R"
