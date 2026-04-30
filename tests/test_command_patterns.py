"""Validate CLI command patterns in RUN steps at all nesting levels."""

import re
import pytest
from conftest import load_all_workflows, flatten_steps, build_config_requiring_subworkflows, collect_includes, references_config_vars


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
            # Match repos/{project}/issues?... pattern
            m = re.search(r'gh api "repos/\{project\}/issues\?([^"]+)"', cmd)
            if m:
                query = m.group(1)
                if "search=" in query and "prd_key" in query:
                    continue
                assert "labels=" in query and ("prd" in query or "type" in query), (
                    f"{rel}:L{step['start_line']+1}: gh issue search not scoped by prd label"
                )
                continue
            # Match search/issues?q=... pattern (used by find-issue.yaml)
            m = re.search(r'gh api "search/issues\?q=([^"]+)"', cmd)
            if m:
                query = m.group(1)
                assert "label:prd" in query, (
                    f"{rel}:L{step['start_line']+1}: gh search/issues query not scoped by prd label"
                )

    @pytest.mark.parametrize("rel, wf", list(load_all_workflows().items()), ids=lambda x: x[0] if isinstance(x, tuple) else str(x))
    def test_no_unresolved_shell_vars(self, rel, wf):
        """No step must contain unresolved shell variables ($var)."""
        shell_var_pattern = re.compile(r"""\$(?:([A-Za-z_]\w*)\b|\{([^}]+)\})""")
        allowed = {"NF"}  # awk built-in (e.g. awk '{print $NF}')
        for step in flatten_steps(wf["steps"]):
            # Scan raw_value (RUN commands, CHECK conditions, etc.)
            text = step["raw_value"]
            # Also scan SET values (stored in block as "value: ...")
            for _, key, value in step.get("block", []):
                if key == "value":
                    text += "\n" + value
            match = shell_var_pattern.search(text)
            if match:
                var = match.group(1) or match.group(2)
                if var in allowed:
                    continue
                assert not match, (
                    f"{rel}:L{step['start_line']+1}: unresolved shell variable ${'{'+var+'}' if match.group(2) else var} in {step['type']} step"
                )


class TestPythonImportCompliance:
    """P1: Python one-liners using sys.argv must import sys (prevents NameError at runtime)."""

    @pytest.mark.parametrize("rel, wf", list(load_all_workflows().items()), ids=lambda x: x[0] if isinstance(x, tuple) else str(x))
    def test_python_sys_argv_has_import(self, rel, wf):
        """python3 -c blocks that reference sys.argv must have import sys."""
        for step in flatten_steps(wf["steps"]):
            if step["type"] != "RUN":
                continue
            raw = step["raw_value"]
            if "python3 -c" not in raw:
                continue
            has_sys_argv = "sys.argv" in raw
            if not has_sys_argv:
                continue
            has_import = bool(re.search(r"(?m)^[^#]*import\s+(json,\s*)?sys", raw))
            assert has_import, (
                f"{rel}:L{step['start_line']+1}: python3 -c uses sys.argv without import sys"
            )


class TestCompleteConfigRequirements:
    """P1: complete.yaml files that depend on config variables must include check-config.

    Between activation and on_complete, the BMM workflow runs and the AI agent's
    context may be compacted, losing variables set during activation. Any complete.yaml
    that (directly or transitively via INCLUDE) depends on config variables must
    re-derive them via common/check-config.

    This test is platform-agnostic: it checks for variable references ({host},
    {project}, {platform}) rather than specific CLI tools (glab, gh, jira, ...).
    """

    _requiring = None

    @classmethod
    def setup_class(cls):
        cls._requiring = build_config_requiring_subworkflows(load_all_workflows())

    @pytest.mark.parametrize("rel, wf", list(load_all_workflows().items()), ids=lambda x: x[0] if isinstance(x, tuple) else str(x))
    def test_complete_with_config_deps_has_check_config(self, rel, wf):
        """complete.yaml files depending on config vars must INCLUDE common/check-config."""
        if not rel.endswith("/complete.yaml"):
            return
        includes = collect_includes(wf)
        needs_config = any(inc in self._requiring for inc in includes)
        if not needs_config and references_config_vars(wf):
            needs_config = True
        if not needs_config:
            return
        has_check_config = "common/check-config" in includes
        assert has_check_config, (
            f"{rel}: depends on config variables but does not INCLUDE common/check-config. "
            f"Config-requiring includes: {sorted(inc for inc in includes if inc in self._requiring)}"
        )
