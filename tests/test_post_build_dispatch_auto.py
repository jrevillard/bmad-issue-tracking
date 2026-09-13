"""The unattended dispatcher must do NOTHING when the caller owns the chain.

Covers `common/post-build-dispatch-auto.yaml`, the entry point of bmad-build-auto's
on_complete hook:

- the marker guard exists, reads `<worktree>/.bmad-ci-handled`, and comes BEFORE the
  INCLUDE that would run the post-completion chain (anything later leaves check-config,
  the spec read and the status routing running, which is not "nothing");
- the guard is conditional, never a bare STOP — this file is bmad-loop's path too, and
  bmad-loop never writes the marker, so its behaviour must be untouched;
- the earlier, narrower attempt (skipping only the two CI steps inside
  post-dev-complete.yaml) is gone, so the two files cannot disagree about how much is
  skipped.

The suite only regex-parses these YAML files (see conftest) — it cannot execute them, so
none of this proves runtime behaviour. The runtime check is a live run with the marker
present: the hook chain must produce no push, no CI wait and no issue write.
"""

from conftest import load_workflow


def test_marker_guard_exists_and_reads_the_worktree_marker():
    wf = load_workflow("common/post-build-dispatch-auto.yaml")
    content = wf["content"]
    # {worktree} is not in scope here, so the file captures it the same way
    # post-dev-complete.yaml does: pwd into a STORE.
    assert "RUN: pwd" in content, "the guard needs the worktree root; {worktree} is not in scope here"
    assert "STORE: worktree" in content
    assert 'cat "{worktree}/.bmad-ci-handled"' in content, "the guard must read the caller's marker"
    assert "STORE: ci_handled" in content
    # cat on a missing file exits non-zero; without EXPECT_EXIT the step would fail the
    # workflow for every consumer that does not write the marker.
    assert "EXPECT_EXIT: any" in content


def test_guard_precedes_the_post_completion_chain():
    content = load_workflow("common/post-build-dispatch-auto.yaml")["content"]
    guard_at = content.index("STORE: ci_handled")
    include_at = content.index("INCLUDE: common/post-build-dispatch")
    assert guard_at < include_at, (
        "the marker guard must come BEFORE the INCLUDE — placed after it, check-config, the "
        "{spec_file} read and the status routing still run, which is not 'nothing'"
    )
    assert content.index("CHECK: empty ci_handled") < include_at
    # And it must actually stop on the marker-present branch.
    stop_at = content.index("stop: true")
    assert guard_at < stop_at < include_at


def test_guard_is_conditional_not_a_bare_stop():
    content = load_workflow("common/post-build-dispatch-auto.yaml")["content"]
    assert "CHECK: empty ci_handled" in content, "the skip must be conditional on the marker"
    # A bare STOP (or an unconditional stop) would break bmad-loop, whose [verify] command
    # requires the ci-status.json only this chain writes.
    assert "CHECK: empty ci_handled" in content.split("stop: true")[0], (
        "the stop must sit inside the marker-present branch"
    )
    assert "INCLUDE: common/post-build-dispatch" in content, "the normal path must still dispatch"


def test_still_sets_review_producer_for_the_normal_path():
    """The flag post-dev-complete keys its review-section halt on."""
    content = load_workflow("common/post-build-dispatch-auto.yaml")["content"]
    assert 'review_producer, value: "bmad-build-auto"' in content


def test_narrow_ci_gates_are_gone_from_post_dev_complete():
    """One place decides the skip. Two would drift, and the narrow one lies."""
    content = load_workflow("common/post-dev-complete.yaml")["content"]
    assert "ci_handled" not in content, (
        "post-dev-complete must not carry its own copy of the marker logic — the guard lives "
        "at the entry point of the chain"
    )
    assert "bmad-ci-handled" not in content
