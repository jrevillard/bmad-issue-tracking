"""Validate CLI command patterns in RUN steps.

P2 — checks glab/gh command conventions. Top-level only.
"""

import re
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


class TestIssueSearchScoping:
    """P1: Issue search API calls must be scoped by prd_key label to prevent multi-PRD collisions."""

    @pytest.mark.parametrize("rel, wf", list(load_all_workflows().items()), ids=lambda x: x[0] if isinstance(x, tuple) else str(x))
    def test_glab_issue_search_has_prd_label(self, rel, wf):
        """glab api issue search URLs must include a prd label filter (unless search already contains prd_key)."""
        for step in wf["steps"]:
            if step["type"] != "RUN":
                continue
            cmd = step["raw_value"]
            m = re.search(r'glab api "projects/\$PROJECT_ID/issues\?([^"]+)"', cmd)
            if not m:
                continue
            query = m.group(1)
            if "search=PRD:%20{prd_key}" in query or "search=PRD%3A%20{prd_key}" in query:
                continue  # already scoped by prd_key in search term
            assert "labels=" in query and "prd" in query, (
                f"{rel}:L{step['start_line']+1}: glab issue search not scoped by prd label"
            )

    @pytest.mark.parametrize("rel, wf", list(load_all_workflows().items()), ids=lambda x: x[0] if isinstance(x, tuple) else str(x))
    def test_gh_issue_search_has_prd_label(self, rel, wf):
        """gh api issue search URLs must include a prd label filter (unless search already contains prd_key)."""
        for step in wf["steps"]:
            if step["type"] != "RUN":
                continue
            cmd = step["raw_value"]
            m = re.search(r'gh api "repos/\$OWNER/\$REPO/issues\?([^"]+)"', cmd)
            if not m:
                continue
            query = m.group(1)
            if "search=" in query and "prd_key" in query:
                continue  # already scoped by prd_key in search term
            assert "labels=" in query and ("prd:" in query or "type:prd" in query), (
                f"{rel}:L{step['start_line']+1}: gh issue search not scoped by prd label"
            )


class TestIssueSearchScopingRaw:
    """P1: Raw-content scan catches issue search URLs nested inside CHECK/LOOP branches.

    The top-level parser skips nested steps. This test uses regex on the raw file
    content to ensure ALL issue search URLs (at any nesting depth) are scoped by prd.
    """

    @pytest.mark.parametrize("rel, wf", list(load_all_workflows().items()), ids=lambda x: x[0] if isinstance(x, tuple) else str(x))
    def test_glab_issue_searches_scoped_in_raw_content(self, rel, wf):
        """All glab api issue search URLs in raw content must include prd label or prd_key in search."""
        for m in re.finditer(r'glab api[^"]*"projects/\$PROJECT_ID/issues\?([^"]+)"', wf["content"]):
            query = m.group(1)
            if "search=PRD:%20{prd_key}" in query or "search=PRD%3A%20{prd_key}" in query:
                continue
            assert "labels=" in query and "prd" in query, (
                f"{rel}: glab issue search not scoped by prd label (raw content)"
            )

    @pytest.mark.parametrize("rel, wf", list(load_all_workflows().items()), ids=lambda x: x[0] if isinstance(x, tuple) else str(x))
    def test_gh_issue_searches_scoped_in_raw_content(self, rel, wf):
        """All gh api issue search URLs in raw content must include prd label."""
        for m in re.finditer(r'gh api[^"]*"repos/\$OWNER/\$REPO/issues\?([^"]+)"', wf["content"]):
            query = m.group(1)
            if "search=" in query and "prd_key" in query:
                continue
            assert "labels=" in query and ("prd:" in query or "type:prd" in query), (
                f"{rel}: gh issue search not scoped by prd label (raw content)"
            )
