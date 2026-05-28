"""Validate that platform-specific RUN steps have correct CLI/platform pairing.

P1 — checks that glab commands run on PLATFORM:gitlab, gh on PLATFORM:github,
and az on PLATFORM:azure-devops.
Does NOT recurse into branches (same limitation as variable flow).
"""

import pytest
from conftest import load_all_workflows, get_step_field, flatten_steps


class TestPlatformCoverage:
    """P1: glab commands on PLATFORM:gitlab, gh on PLATFORM:github, az on PLATFORM:azure-devops."""

    @pytest.mark.parametrize("rel, wf", list(load_all_workflows().items()), ids=lambda x: x[0] if isinstance(x, tuple) else str(x))
    def test_platform_runs_balanced(self, rel, wf):
        """Top-level PLATFORM-annotated RUNs must pair CLI with correct platform."""
        glab_gitlab = 0
        gh_github = 0
        az_ado = 0
        glab_github = 0
        gh_gitlab = 0
        az_wrong = 0

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
            stripped = cmd.strip()
            if stripped.startswith("glab "):
                if platform == "gitlab":
                    glab_gitlab += 1
                else:
                    glab_github += 1
            elif stripped.startswith("gh "):
                if platform == "github":
                    gh_github += 1
                else:
                    gh_gitlab += 1
            elif stripped.startswith("az "):
                if platform == "azure-devops":
                    az_ado += 1
                else:
                    az_wrong += 1

        errors = []
        if glab_github:
            errors.append(f"glab on PLATFORM:github ({glab_github}x)")
        if gh_gitlab:
            errors.append(f"gh on PLATFORM:gitlab ({gh_gitlab}x)")
        if az_wrong:
            errors.append(f"az on wrong PLATFORM ({az_wrong}x)")

        if errors:
            pytest.fail(f"{rel}: {', '.join(errors)}")
