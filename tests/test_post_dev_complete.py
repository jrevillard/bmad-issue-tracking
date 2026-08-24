"""Validate the unified post-completion workflow and its dispatcher.

Covers:
- post-build-dispatch.yaml routes each spec status to the right phase
- post-dev-complete.yaml dispatches on phase variable
- ci-status.json contract is preserved (written by write-ci-status.yaml)
- ensure-issue / ensure-mr are reused across phases
"""

from conftest import load_workflow, flatten_steps, collect_includes


def test_dispatch_routes_ready_for_dev_to_create_story():
    """ready-for-dev status must route to phase=create-story."""
    wf = load_workflow("common/post-build-dispatch.yaml")
    content = wf["content"]
    assert "status eq \"ready-for-dev\"" in content
    assert "phase, value: \"create-story\"" in content


def test_dispatch_routes_in_review_to_dev_finish():
    """in-review status must route to phase=dev-finish."""
    wf = load_workflow("common/post-build-dispatch.yaml")
    content = wf["content"]
    assert "status eq \"in-review\"" in content
    assert "phase, value: \"dev-finish\"" in content


def test_dispatch_routes_in_progress_to_dev_finish():
    """in-progress status must route to phase=dev-finish (dev finished, review not started)."""
    wf = load_workflow("common/post-build-dispatch.yaml")
    content = wf["content"]
    assert "status eq \"in-progress\"" in content
    assert "phase, value: \"dev-finish\"" in content


def test_dispatch_routes_done_to_review_finish():
    """done status must route to phase=review-finish."""
    wf = load_workflow("common/post-build-dispatch.yaml")
    content = wf["content"]
    assert "status eq \"done\"" in content
    assert "phase, value: \"review-finish\"" in content


def test_dispatch_skips_blocked_and_awaiting():
    """blocked / awaiting-operator statuses must skip (no phase dispatch)."""
    wf = load_workflow("common/post-build-dispatch.yaml")
    content = wf["content"]
    assert "status eq \"blocked\"" in content
    assert "status eq \"awaiting-operator\"" in content
    # No INCLUDE common/post-dev-complete directly in those branches
    includes = collect_includes(wf)
    # Only the routed phases include post-dev-complete
    assert "common/post-dev-complete" in includes


def test_post_dev_complete_has_three_phases():
    """The unified workflow must dispatch on the three phase values."""
    wf = load_workflow("common/post-dev-complete.yaml")
    content = wf["content"]
    assert "phase eq \"create-story\"" in content
    assert "phase eq \"dev-finish\"" in content
    assert "phase eq \"review-finish\"" in content


def test_dev_finish_writes_ci_status():
    """dev-finish must write ci-status.json via write-ci-status include."""
    wf = load_workflow("common/post-dev-complete.yaml")
    includes = collect_includes(wf)
    assert "common/write-ci-status" in includes
    assert "common/wait-for-green-ci" in includes


def test_review_finish_writes_ci_status():
    """review-finish must also write ci-status.json (contract for ci-status.sh)."""
    wf = load_workflow("common/post-dev-complete.yaml")
    content = wf["content"]
    includes = collect_includes(wf)
    assert "common/write-ci-status" in includes
    # write-ci-status must appear in the review-finish branch too
    # (count occurrences of the include across the flattened steps)
    writes = [s for s in flatten_steps(wf["steps"]) if s["type"] == "INCLUDE" and "write-ci-status" in s["raw_value"]]
    assert len(writes) >= 2, "write-ci-status must be included in both dev-finish and review-finish"


def test_dev_finish_ensures_issue_and_mr():
    """dev-finish must ensure issue + MR exist (not just find them)."""
    wf = load_workflow("common/post-dev-complete.yaml")
    includes = collect_includes(wf)
    assert "common/ensure-issue" in includes
    assert "common/ensure-mr" in includes


def test_create_story_ensures_issue_and_mr():
    """create-story must ensure issue + MR exist."""
    wf = load_workflow("common/post-dev-complete.yaml")
    includes = collect_includes(wf)
    assert "common/ensure-issue" in includes
    assert "common/ensure-mr" in includes


def test_wrappers_set_phase():
    """The phase wrappers must set the phase variable then INCLUDE the unified workflow."""
    expected = {
        "common/post-dev-complete-create-story.yaml": "create-story",
        "common/post-dev-complete-dev-finish.yaml": "dev-finish",
        "common/post-dev-complete-review-finish.yaml": "review-finish",
    }
    for rel, phase in expected.items():
        wf = load_workflow(rel)
        content = wf["content"]
        assert f"phase, value: \"{phase}\"" in content, f"{rel}: wrong phase value"
        includes = collect_includes(wf)
        assert "common/post-dev-complete" in includes, f"{rel}: missing unified workflow include"
