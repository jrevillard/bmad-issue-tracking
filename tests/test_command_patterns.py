"""Validate CLI command patterns in RUN steps at all nesting levels."""

import re
import pytest
from conftest import load_all_workflows, flatten_steps


class TestCommandPatterns:
    """P2: CLI commands follow platform conventions."""

    @pytest.mark.parametrize("rel, wf", list(load_all_workflows().items()), ids=lambda x: x[0] if isinstance(x, tuple) else str(x))
    def test_glab_api_uses_hostname(self, rel, wf):
        """glab api commands must include --hostname."""
        for step in flatten_steps(wf["steps"]):
            if step["type"] != "RUN":
                continue
            cmd = step["raw_value"]
            if "glab api" in cmd:
                assert "--hostname" in cmd, f"{rel}:L{step['start_line']+1}: glab api without --hostname"

    @pytest.mark.parametrize("rel, wf", list(load_all_workflows().items()), ids=lambda x: x[0] if isinstance(x, tuple) else str(x))
    def test_glab_subcommands_use_r(self, rel, wf):
        """glab mr/label/issue subcommands must include -R."""
        for step in flatten_steps(wf["steps"]):
            if step["type"] != "RUN":
                continue
            cmd = step["raw_value"]
            if "glab api" not in cmd and any(f"glab {s}" in cmd for s in ("mr ", "label ", "issue ")):
                assert "-R" in cmd, f"{rel}:L{step['start_line']+1}: glab subcommand without -R"

    @pytest.mark.parametrize("rel, wf", list(load_all_workflows().items()), ids=lambda x: x[0] if isinstance(x, tuple) else str(x))
    def test_gh_commands_use_r(self, rel, wf):
        """gh issue/pr commands that need repo context must include -R."""
        for step in flatten_steps(wf["steps"]):
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


class TestIssueSearchScoping:
    """P1: Issue search API calls must be scoped by prd_key label to prevent multi-PRD collisions."""

    @pytest.mark.parametrize("rel, wf", list(load_all_workflows().items()), ids=lambda x: x[0] if isinstance(x, tuple) else str(x))
    def test_glab_issue_search_has_prd_label(self, rel, wf):
        """glab api issue search URLs must include a prd label filter (unless search already contains prd_key)."""
        for step in flatten_steps(wf["steps"]):
            if step["type"] != "RUN":
                continue
            cmd = step["raw_value"]
            m = re.search(r'glab api "projects/\{project\}/issues\?([^"]+)"', cmd)
            if not m:
                continue
            query = m.group(1)
            if "search=PRD:%20{prd_key}" in query or "search=PRD%3A%20{prd_key}" in query:
                continue
            assert "labels=" in query and "prd" in query, (
                f"{rel}:L{step['start_line']+1}: glab issue search not scoped by prd label"
            )

    @pytest.mark.parametrize("rel, wf", list(load_all_workflows().items()), ids=lambda x: x[0] if isinstance(x, tuple) else str(x))
    def test_gh_issue_search_has_prd_label(self, rel, wf):
        """gh api issue search URLs must include a prd label filter (unless search already contains prd_key)."""
        for step in flatten_steps(wf["steps"]):
            if step["type"] != "RUN":
                continue
            cmd = step["raw_value"]
            m = re.search(r'gh api "repos/\{project\}/issues\?([^"]+)"', cmd)
            if not m:
                continue
            query = m.group(1)
            if "search=" in query and "prd_key" in query:
                continue
            assert "labels=" in query and ("prd:" in query or "type:prd" in query), (
                f"{rel}:L{step['start_line']+1}: gh issue search not scoped by prd label"
            )

    @pytest.mark.parametrize("rel, wf", list(load_all_workflows().items()), ids=lambda x: x[0] if isinstance(x, tuple) else str(x))
    def test_no_unresolved_shell_vars(self, rel, wf):
        """RUN steps must not contain unresolved shell variables ($ALL_CAPS)."""
        shell_var_pattern = re.compile(r"""\$([A-Z][A-Z_0-9]+)\b""")
        allowed = {"NF"}  # awk built-in (e.g. awk '{print $NF}')
        for step in flatten_steps(wf["steps"]):
            if step["type"] != "RUN":
                continue
            cmd = step["raw_value"]
            match = shell_var_pattern.search(cmd)
            if match and match.group(1) in allowed:
                continue
            assert not match, (
                f"{rel}:L{step['start_line']+1}: unresolved shell variable ${match.group(1)} in RUN step"
            )
