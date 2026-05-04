"""Validate that platform-specific RUN steps have correct CLI/platform pairing.

P1 — checks that glab commands run on PLATFORM:gitlab and gh on PLATFORM:github.
Does NOT recurse into branches (same limitation as variable flow).
"""

import pytest
from conftest import load_all_workflows, get_step_field, flatten_steps


class TestPlatformCoverage:
    """P1: glab commands on PLATFORM:gitlab, gh on PLATFORM:github."""

    @pytest.mark.parametrize("rel, wf", list(load_all_workflows().items()), ids=lambda x: x[0] if isinstance(x, tuple) else str(x))
    def test_platform_runs_balanced(self, rel, wf):
        """Top-level PLATFORM-annotated RUNs must pair glab with gitlab and gh with github."""
        glab_gitlab = 0
        gh_github = 0
        glab_github = 0
        gh_gitlab = 0

        for step in flatten_steps(wf["steps"]):
            if step["type"] != "RUN":
                continue
            platform = None
            cmd = step["raw_value"]
            for _, key, value in step["block"]:
                if key == "PLATFORM":
                    platform = value
            if platform is None:
                continue
            if cmd.strip().startswith("glab ") and platform == "gitlab":
                glab_gitlab += 1
            elif cmd.strip().startswith("glab ") and platform == "github":
                glab_github += 1
            elif cmd.strip().startswith("gh ") and platform == "github":
                gh_github += 1
            elif cmd.strip().startswith("gh ") and platform == "gitlab":
                gh_gitlab += 1

        errors = []
        if glab_github:
            errors.append(f"glab on PLATFORM:github ({glab_github}x)")
        if gh_gitlab:
            errors.append(f"gh on PLATFORM:gitlab ({gh_gitlab}x)")

        if errors:
            pytest.fail(f"{rel}: {', '.join(errors)}")
