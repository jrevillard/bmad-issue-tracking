"""Unit tests for the close-trace-mr plugin's Python module.

The tests target the testable surface area of `close_trace_mr.py`:

  - env var extraction (`get_env_values`)
  - config parsing (`parse_issue_tracking_config`)
  - context resolution (`resolve_ctx`) including overlay precedence
  - MR list parsing (`list_open_mrs`) — empty result, multi-MR result, errors
  - close command construction (`close_one`) — glab vs gh, success, already-closed
  - marker file write (`write_marker`) — atomic, content shape, run_dir-less path

The subprocess runner is injected via the `runner` parameter — no real glab/gh
is spawned. Each test that needs subprocess control defines a tiny `_FakeProc`
that records the command and returns canned output, simulating success/failure
without touching the host.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

import pytest

# Make the plugin folder importable. The plugin ships as a folder next to this
# test file (standard layout: <plugin>/tests/ imports <plugin>/).
PLUGIN_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_DIR))

import close_trace_mr as ctm  # noqa: E402  (import after sys.path tweak)


# -----------------------------------------------------------------------------
# Test fixtures — a fake subprocess runner
# -----------------------------------------------------------------------------


class _FakeProc:
    """Stand-in for subprocess.CompletedProcess.

    The real type's fields (`returncode`, `stdout`, `stderr`) are enough for
    the module's usage; nothing reads `args` or `args_str` from the result.
    """

    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class _Recorder:
    """Callable that mimics `subprocess.run` while recording every call.

    `script` is a list of `(predicate, response)` pairs; the first predicate
    that matches the argv (compared by argv[0] + a regex on the joined string)
    returns its response. Any unmatched call returns (0, "", "") which lets
    tests focus on one CLI at a time without a sprawling conditional.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[Sequence[str], dict[str, Any]]] = []
        self.script: list[tuple[Any, _FakeProc]] = []

    def add(self, match: Any, proc: _FakeProc) -> None:
        self.script.append((match, proc))

    def __call__(self, cmd, **kwargs):
        self.calls.append((tuple(cmd), kwargs))
        for matcher, proc in self.script:
            if matcher(cmd):
                return proc
        # Default: silent success (empty body = "no MRs").
        return _FakeProc(0, "")

    @staticmethod
    def cmd_starts_with(*prefixes: str):
        def _match(cmd: Sequence[str]) -> bool:
            return all(cmd[i].startswith(p) for i, p in enumerate(prefixes))
        return _match


# -----------------------------------------------------------------------------
# env var extraction
# -----------------------------------------------------------------------------


class TestGetEnvValues:
    def test_extracts_all_known_vars(self):
        env = {
            "BMAD_LOOP_BRANCH": "feat/prd/3-1-foo",
            "BMAD_LOOP_STORY_KEY": "3-1-foo",
            "BMAD_LOOP_RUN_DIR": "/tmp/run-xyz",
            "BMAD_LOOP_STAGE": "post_merge",
            "BMAD_LOOP_REPO_ROOT": "/tmp/repo",
            "BMAD_LOOP_SETTING_CLOSE_TRACE_MR": "true",
            "BMAD_LOOP_SETTING_PLATFORM": "",
            "BMAD_LOOP_SETTING_HOST": "",
            "BMAD_LOOP_SETTING_PROJECT": "",
        }
        v = ctm.get_env_values(env)
        assert v["branch"] == "feat/prd/3-1-foo"
        assert v["story_key"] == "3-1-foo"
        assert v["run_dir"] == "/tmp/run-xyz"
        assert v["stage"] == "post_merge"
        assert v["repo_root"] == "/tmp/repo"
        assert v["enabled"] is True

    def test_defaults_when_no_bmad_loop_vars(self):
        v = ctm.get_env_values({})
        assert v["branch"] == ""
        assert v["story_key"] == ""
        assert v["run_dir"] == ""
        assert v["enabled"] is True
        assert v["platform_override"] == ""

    @pytest.mark.parametrize("raw,expected", [
        ("false", False), ("False", False), ("FALSE", False),
        ("0", False), ("no", False), ("", False),
        ("true", True), ("1", True), ("yes", True), ("anything-else", True),
    ])
    def test_setting_close_trace_mr_parsing(self, raw, expected):
        env = {"BMAD_LOOP_SETTING_CLOSE_TRACE_MR": raw}
        assert ctm.get_env_values(env)["enabled"] is expected


# -----------------------------------------------------------------------------
# config parsing
# -----------------------------------------------------------------------------


class TestParseIssueTrackingConfig:
    def test_returns_empty_when_missing(self, tmp_path: Path):
        assert ctm.parse_issue_tracking_config(tmp_path / "nope.yaml") == {}

    def test_extracts_relevant_keys(self, tmp_path: Path):
        cfg = tmp_path / "issue-tracking.yaml"
        cfg.write_text(
            "issue_tracking:\n"
            "  enabled: true\n"
            "  platform: gitlab\n"
            "  host: gitlab.example.com\n"
            "  project: my-group/my-proj\n"
            "  worktree_base: _bmad/worktrees\n",
            encoding="utf-8",
        )
        out = ctm.parse_issue_tracking_config(cfg)
        assert out == {
            "platform": "gitlab",
            "host": "gitlab.example.com",
            "project": "my-group/my-proj",
        }

    def test_handles_quoted_values(self, tmp_path: Path):
        cfg = tmp_path / "issue-tracking.yaml"
        cfg.write_text(
            "issue_tracking:\n"
            "  platform: 'github'\n"
            '  host: "github.example.com"\n',
            encoding="utf-8",
        )
        out = ctm.parse_issue_tracking_config(cfg)
        assert out["platform"] == "github"
        assert out["host"] == "github.example.com"

    def test_ignores_unrelated_keys(self, tmp_path: Path):
        cfg = tmp_path / "issue-tracking.yaml"
        cfg.write_text(
            "issue_tracking:\n"
            "  enabled: true\n"
            "  worktree_base: _bmad/worktrees\n"
            "  branch_patterns:\n"
            "    prd: feat/{prd_key}/prd\n"
            "    story: feat/{prd_key}/{story_key}\n",
            encoding="utf-8",
        )
        out = ctm.parse_issue_tracking_config(cfg)
        assert "enabled" not in out
        assert "worktree_base" not in out
        assert "branch_patterns" not in out

    def test_raises_on_garbage(self, tmp_path: Path):
        cfg = tmp_path / "issue-tracking.yaml"
        cfg.write_text("this is not a yaml file\n", encoding="utf-8")
        # Parser is lenient — unknown content returns empty, no exception.
        # Platform validation (which DOES raise) lives in resolve_ctx.
        assert ctm.parse_issue_tracking_config(cfg) == {}


# -----------------------------------------------------------------------------
# context resolution
# -----------------------------------------------------------------------------


class TestResolveCtx:
    _ENV = {
        "branch": "feat/prd/3-1-foo",
        "story_key": "3-1-foo",
        "run_dir": "/tmp/run",
        "stage": "post_merge",
        "repo_root": "/tmp/repo",
        "platform_override": "",
        "host_override": "",
        "project_override": "",
        "enabled": True,
    }

    def test_from_config_only(self):
        ctx = ctm.resolve_ctx(self._ENV, {"platform": "gitlab", "host": "gl.example", "project": "g/p"})
        assert ctx is not None
        assert ctx.platform == "gitlab"
        assert ctx.host == "gl.example"
        assert ctx.project == "g/p"
        assert ctx.branch == "feat/prd/3-1-foo"
        assert ctx.close_trace_mr is True

    def test_env_overrides_config(self):
        env = {**self._ENV, "host_override": "override.example", "platform_override": "github"}
        ctx = ctm.resolve_ctx(env, {"platform": "gitlab", "host": "config.example", "project": "g/p"})
        assert ctx.platform == "github"
        assert ctx.host == "override.example"
        assert ctx.project == "g/p"

    def test_github_no_host_required(self):
        env = {**self._ENV, "platform_override": "github", "project_override": "owner/repo"}
        ctx = ctm.resolve_ctx(env, {})
        # GitHub doesn't require a host override (api.github.com is the
        # default; gh uses -R project so the repo is named in the cmd itself).
        assert ctx is not None
        assert ctx.host == ""
        assert ctx.project == "owner/repo"

    def test_gitlab_defaults_to_gitlab_com(self):
        env = {**self._ENV, "platform_override": "gitlab"}
        ctx = ctm.resolve_ctx(env, {"project": "g/p"})
        assert ctx is not None
        assert ctx.host == "gitlab.com"

    def test_returns_none_when_platform_missing(self):
        assert ctm.resolve_ctx(self._ENV, {}) is None

    def test_returns_none_when_project_missing(self):
        env = {**self._ENV, "platform_override": "gitlab"}
        assert ctm.resolve_ctx(env, {"host": "gl.example"}) is None

    def test_rejects_unknown_platform(self):
        env = {**self._ENV, "platform_override": "bitbucket"}
        with pytest.raises(ctm.ConfigParseError):
            ctm.resolve_ctx(env, {})

    def test_close_trace_mr_setting_propagates(self):
        env = {**self._ENV, "enabled": False}
        ctx = ctm.resolve_ctx(env, {"platform": "gitlab", "project": "g/p"})
        assert ctx is not None
        assert ctx.close_trace_mr is False


# -----------------------------------------------------------------------------
# list_open_mrs
# -----------------------------------------------------------------------------


def _gitlab_ctx() -> ctm.Ctx:
    return ctm.Ctx(
        platform="gitlab",
        host="gl.example",
        project="group/sub/repo",
        branch="feat/prd/3-1-foo",
        story_key="3-1-foo",
        run_dir="/tmp/run",
        close_trace_mr=True,
    )


def _github_ctx() -> ctm.Ctx:
    return ctm.Ctx(
        platform="github",
        host="",
        project="owner/repo",
        branch="feat/prd/3-1-foo",
        story_key="3-1-foo",
        run_dir="/tmp/run",
        close_trace_mr=True,
    )


class TestListOpenMrs:
    def test_gitlab_empty_list(self):
        recorder = _Recorder()
        recorder.add(_Recorder.cmd_starts_with("glab"), _FakeProc(0, "[]"))
        assert ctm.list_open_mrs(recorder, _gitlab_ctx()) == []
        assert len(recorder.calls) == 1
        cmd, _ = recorder.calls[0]
        assert cmd[0] == "glab" and cmd[1] == "api"
        assert "projects/group/sub/repo/merge_requests" in cmd[2]
        assert "--hostname" in cmd and "gl.example" in cmd
        # branch + state filters (either as flags or -F flags depending on version)
        joined = " ".join(cmd)
        assert "feat/prd/3-1-foo" in joined
        assert "opened" in joined

    def test_gitlab_multi_mr_result(self):
        body = json.dumps([
            {"iid": 17, "title": "Story 3.1: foo"},
            {"iid": 42, "title": "Story 3.1: foo (duplicate)"},
        ])
        recorder = _Recorder()
        recorder.add(_Recorder.cmd_starts_with("glab"), _FakeProc(0, body))
        assert ctm.list_open_mrs(recorder, _gitlab_ctx()) == [17, 42]

    def test_gitlab_string_iid_is_coerced(self):
        body = json.dumps([{"iid": "99"}])
        recorder = _Recorder()
        recorder.add(_Recorder.cmd_starts_with("glab"), _FakeProc(0, body))
        assert ctm.list_open_mrs(recorder, _gitlab_ctx()) == [99]

    def test_gitlab_non_json_body_returns_empty(self):
        recorder = _Recorder()
        recorder.add(_Recorder.cmd_starts_with("glab"), _FakeProc(0, "<html>oops</html>"))
        assert ctm.list_open_mrs(recorder, _gitlab_ctx()) == []

    def test_gitlab_nonzero_exit_returns_empty(self):
        recorder = _Recorder()
        recorder.add(
            _Recorder.cmd_starts_with("glab"),
            _FakeProc(1, "", "401 Unauthorized"),
        )
        assert ctm.list_open_mrs(recorder, _gitlab_ctx()) == []

    def test_gitlab_empty_string_body_returns_empty(self):
        recorder = _Recorder()
        recorder.add(_Recorder.cmd_starts_with("glab"), _FakeProc(0, ""))
        assert ctm.list_open_mrs(recorder, _gitlab_ctx()) == []

    def test_github_empty_list(self):
        recorder = _Recorder()
        recorder.add(_Recorder.cmd_starts_with("gh"), _FakeProc(0, "[]"))
        assert ctm.list_open_mrs(recorder, _github_ctx()) == []
        cmd, _ = recorder.calls[0]
        assert cmd[0] == "gh" and cmd[1] == "api"
        joined = " ".join(cmd)
        assert "repos/owner/repo/pulls" in joined
        assert "feat/prd/3-1-foo" in joined

    def test_github_multi_pr_result(self):
        body = json.dumps([
            {"number": 11, "title": "Story 3.1: foo"},
            {"number": 22, "title": "Story 3.1: foo (dup)"},
        ])
        recorder = _Recorder()
        recorder.add(_Recorder.cmd_starts_with("gh"), _FakeProc(0, body))
        assert ctm.list_open_mrs(recorder, _github_ctx()) == [11, 22]


# -----------------------------------------------------------------------------
# close_one
# -----------------------------------------------------------------------------


class TestCloseOne:
    def test_gitlab_success(self):
        recorder = _Recorder()
        recorder.add(_Recorder.cmd_starts_with("glab"), _FakeProc(0, '{"state": "closed"}'))
        result = ctm.close_one(recorder, _gitlab_ctx(), iid=17)
        assert result.state == "closed"
        assert result.iid == 17
        cmd, _ = recorder.calls[0]
        joined = " ".join(cmd)
        assert "merge_requests/17" in joined
        assert "state_event" in joined and "close" in joined
        assert "-X" in cmd and "PUT" in cmd

    def test_gitlab_already_closed_is_success(self):
        recorder = _Recorder()
        recorder.add(
            _Recorder.cmd_starts_with("glab"),
            _FakeProc(409, stdout="{}", stderr="Merge request is already closed"),
        )
        result = ctm.close_one(recorder, _gitlab_ctx(), iid=17)
        assert result.state == "already_closed"

    def test_gitlab_unrelated_failure_is_recorded(self):
        recorder = _Recorder()
        recorder.add(
            _Recorder.cmd_starts_with("glab"),
            _FakeProc(403, stderr="403 Forbidden"),
        )
        result = ctm.close_one(recorder, _gitlab_ctx(), iid=17)
        assert result.state == "failed"
        assert "403" in result.message

    def test_github_success(self):
        recorder = _Recorder()
        recorder.add(_Recorder.cmd_starts_with("gh"), _FakeProc(0, "✓ Closed pull request #11\n"))
        result = ctm.close_one(recorder, _github_ctx(), iid=11)
        assert result.state == "closed"
        cmd, _ = recorder.calls[0]
        joined = " ".join(cmd)
        assert "pr close 11" in joined
        assert "-R owner/repo" in joined

    def test_github_already_closed_is_success(self):
        recorder = _Recorder()
        recorder.add(
            _Recorder.cmd_starts_with("gh"),
            _FakeProc(0, "pull request #11 is already closed"),
        )
        result = ctm.close_one(recorder, _github_ctx(), iid=11)
        assert result.state == "already_closed"

    def test_github_real_failure(self):
        recorder = _Recorder()
        recorder.add(
            _Recorder.cmd_starts_with("gh"),
            _FakeProc(1, stderr="gh: Not Found (HTTP 404)"),
        )
        result = ctm.close_one(recorder, _github_ctx(), iid=99)
        assert result.state == "failed"
        assert "Not Found" in result.message


# -----------------------------------------------------------------------------
# write_marker
# -----------------------------------------------------------------------------


class TestWriteMarker:
    def _ctx(self, run_dir: str = "/tmp/run") -> ctm.Ctx:
        return ctm.Ctx(
            platform="gitlab",
            host="gl.example",
            project="g/p",
            branch="feat/prd/3-1",
            story_key="3-1",
            run_dir=run_dir,
            close_trace_mr=True,
        )

    def test_writes_atomic_marker(self, tmp_path: Path):
        ctx = self._ctx(run_dir=str(tmp_path))
        results = [
            ctm.CloseResult(iid=17, state="closed"),
            ctm.CloseResult(iid=18, state="already_closed"),
        ]
        path = ctm.write_marker(str(tmp_path), ctx, results)
        assert path is not None
        assert path.name == "post-merge-3-1.md"
        assert path.parent == tmp_path
        text = path.read_text(encoding="utf-8")
        assert text.startswith("---\n")
        assert "status: done" in text
        assert "story_key: 3-1" in text
        assert "branch: feat/prd/3-1" in text
        assert "platform: gitlab" in text
        assert "closed_mrs: [17, 18]" in text
        assert "failed_mrs: []" in text
        # Atomic: no .tmp left behind
        assert not (path.with_suffix(path.suffix + ".tmp")).exists()

    def test_marker_handles_failed_results(self, tmp_path: Path):
        ctx = self._ctx(run_dir=str(tmp_path))
        results = [
            ctm.CloseResult(iid=17, state="closed"),
            ctm.CloseResult(iid=18, state="failed", message="HTTP 403"),
        ]
        path = ctm.write_marker(str(tmp_path), ctx, results)
        assert path is not None
        text = path.read_text(encoding="utf-8")
        assert "closed_mrs: [17]" in text
        assert "failed_mrs: [18]" in text
        assert "HTTP 403" in text

    def test_marker_no_results(self, tmp_path: Path):
        ctx = self._ctx(run_dir=str(tmp_path))
        path = ctm.write_marker(str(tmp_path), ctx, results=[])
        assert path is not None
        text = path.read_text(encoding="utf-8")
        assert "status: done" in text
        assert "closed_mrs: []" in text
        assert "failed_mrs: []" in text

    def test_returns_none_when_run_dir_empty(self):
        ctx = self._ctx(run_dir="")
        assert ctm.write_marker("", ctx, results=[]) is None

    def test_sanitises_story_key(self, tmp_path: Path):
        # Slashes + colons would otherwise escape the run dir; underscore them.
        ctx = self._ctx(run_dir=str(tmp_path))
        ctx = ctm.Ctx(
            platform=ctx.platform,
            host=ctx.host,
            project=ctx.project,
            branch=ctx.branch,
            story_key="epic:3/story-1",
            run_dir=ctx.run_dir,
            close_trace_mr=ctx.close_trace_mr,
        )
        path = ctm.write_marker(str(tmp_path), ctx, results=[])
        assert path is not None
        assert path.name == "post-merge-epic_3_story-1.md"

    def test_creates_run_dir_if_missing(self, tmp_path: Path):
        nested = tmp_path / "deep" / "nested"
        ctx = self._ctx(run_dir=str(nested))
        path = ctm.write_marker(str(nested), ctx, results=[])
        assert path is not None
        assert path.parent.is_dir()


# -----------------------------------------------------------------------------
# End-to-end `run()` — covers the orchestration + idempotency contract
# -----------------------------------------------------------------------------


class TestRunEndToEnd:
    _ENV = {
        "BMAD_LOOP_BRANCH": "feat/prd/3-1-foo",
        "BMAD_LOOP_STORY_KEY": "3-1-foo",
        "BMAD_LOOP_RUN_DIR": "",  # filled in per test
        "BMAD_LOOP_STAGE": "post_merge",
        "BMAD_LOOP_REPO_ROOT": "",  # filled in per test
        "BMAD_LOOP_SETTING_CLOSE_TRACE_MR": "true",
        "BMAD_LOOP_SETTING_PLATFORM": "",
        "BMAD_LOOP_SETTING_HOST": "",
        "BMAD_LOOP_SETTING_PROJECT": "",
    }

    def _run(self, env, tmp_path, *, runner_script=None, config_body=None, run_dir=None):
        repo = tmp_path / "repo"
        repo.mkdir(exist_ok=True)
        if config_body is not None:
            cfg_dir = repo / "_bmad" / "custom"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            (cfg_dir / "issue-tracking.yaml").write_text(config_body, encoding="utf-8")
        env2 = dict(env)
        env2["BMAD_LOOP_REPO_ROOT"] = str(repo)
        env2["BMAD_LOOP_RUN_DIR"] = run_dir or str(tmp_path / "run")
        recorder = _Recorder()
        if runner_script:
            for matcher, proc in runner_script:
                recorder.add(matcher, proc)
        rc = ctm.run(env=env2, runner=recorder, config_path=None)
        return rc, recorder, env2["BMAD_LOOP_RUN_DIR"]

    def test_disabled_setting_short_circuits(self, tmp_path: Path):
        env = {**self._ENV, "BMAD_LOOP_SETTING_CLOSE_TRACE_MR": "false"}
        rc, recorder, _ = self._run(env, tmp_path)
        assert rc == 0
        assert recorder.calls == []  # no subprocess fires

    def test_no_tracker_configured_is_clean_noop(self, tmp_path: Path):
        rc, recorder, _ = self._run(dict(self._ENV), tmp_path)
        assert rc == 0
        assert recorder.calls == []

    def test_garbage_platform_returns_1(self, tmp_path: Path):
        env = {**self._ENV, "BMAD_LOOP_SETTING_PLATFORM": "bitbucket"}
        rc, _, _ = self._run(env, tmp_path)
        assert rc == 1

    def test_no_open_mrs_writes_empty_marker(self, tmp_path: Path):
        cfg = (
            "issue_tracking:\n"
            "  enabled: true\n"
            "  platform: gitlab\n"
            "  host: gl.example\n"
            "  project: g/p\n"
        )
        runner_script = [(_Recorder.cmd_starts_with("glab"), _FakeProc(0, "[]"))]
        rc, _, run_dir = self._run(dict(self._ENV), tmp_path, runner_script=runner_script, config_body=cfg)
        assert rc == 0
        marker = Path(run_dir) / "post-merge-3-1-foo.md"
        assert marker.exists()
        assert "closed_mrs: []" in marker.read_text()

    def test_idempotent_close_already_closed_marker(self, tmp_path: Path):
        cfg = (
            "issue_tracking:\n"
            "  platform: gitlab\n"
            "  host: gl.example\n"
            "  project: g/p\n"
        )
        # list returns ONE open MR (rc=0); close returns the GitLab "already
        # closed" shape (HTTP 409 + body) — the catch-all would re-fire on the
        # list call too, so we discriminate by argv.
        runner_script = [
            (
                lambda cmd: cmd[0] == "glab" and cmd[1] == "api" and "merge_requests" in cmd[2] and "/17" not in cmd[2],
                _FakeProc(0, json.dumps([{"iid": 17}])),
            ),
            (
                lambda cmd: cmd[0] == "glab" and cmd[1] == "api" and "merge_requests/17" in cmd[2],
                _FakeProc(409, stdout="{}", stderr="Merge request is already closed"),
            ),
        ]
        rc, _, run_dir = self._run(dict(self._ENV), tmp_path, runner_script=runner_script, config_body=cfg)
        assert rc == 0
        text = (Path(run_dir) / "post-merge-3-1-foo.md").read_text()
        assert "closed_mrs: [17]" in text
        assert "already_closed" in text

    def test_multi_mr_defensive_sweep_closes_all(self, tmp_path: Path):
        cfg = (
            "issue_tracking:\n"
            "  platform: gitlab\n"
            "  host: gl.example\n"
            "  project: g/p\n"
        )
        # list returns TWO open MRs; each close succeeds. The list matcher
        # discriminates by argv (the list URL has no `/<iid>` segment).
        runner_script = [
            (
                lambda cmd: cmd[0] == "glab" and cmd[1] == "api"
                and "merge_requests" in cmd[2]
                and not any(f"/{iid}" in cmd[2] for iid in ("17", "42")),
                _FakeProc(0, json.dumps([{"iid": 17}, {"iid": 42}])),
            ),
            (
                lambda cmd: cmd[0] == "glab" and cmd[1] == "api",
                _FakeProc(0, '{"state": "closed"}'),
            ),
        ]
        rc, recorder, run_dir = self._run(
            dict(self._ENV), tmp_path, runner_script=runner_script, config_body=cfg,
        )
        assert rc == 0
        # list + 2 closes = 3 subprocess calls
        assert len(recorder.calls) == 3
        text = (Path(run_dir) / "post-merge-3-1-foo.md").read_text()
        assert "closed_mrs: [17, 42]" in text

    def test_partial_failure_returns_2(self, tmp_path: Path):
        cfg = (
            "issue_tracking:\n"
            "  platform: gitlab\n"
            "  host: gl.example\n"
            "  project: g/p\n"
        )
        # list returns two MRs; close 17 succeeds; close 42 fails. Three
        # matchers, one per call, each discriminates by the iid segment.
        runner_script = [
            (
                lambda cmd: cmd[0] == "glab" and cmd[1] == "api"
                and "merge_requests" in cmd[2]
                and not any(f"/{iid}" in cmd[2] for iid in ("17", "42")),
                _FakeProc(0, json.dumps([{"iid": 17}, {"iid": 42}])),
            ),
            (
                lambda cmd: cmd[0] == "glab" and cmd[1] == "api" and "merge_requests/17" in cmd[2],
                _FakeProc(0, '{"state": "closed"}'),
            ),
            (
                lambda cmd: cmd[0] == "glab" and cmd[1] == "api" and "merge_requests/42" in cmd[2],
                _FakeProc(403, stderr="403 Forbidden"),
            ),
        ]
        rc, _, run_dir = self._run(
            dict(self._ENV), tmp_path, runner_script=runner_script, config_body=cfg,
        )
        assert rc == 2
        text = (Path(run_dir) / "post-merge-3-1-foo.md").read_text()
        assert "closed_mrs: [17]" in text
        assert "failed_mrs: [42]" in text
        assert "403 Forbidden" in text

    def test_env_settings_override_config(self, tmp_path: Path):
        cfg = (
            "issue_tracking:\n"
            "  platform: gitlab\n"
            "  host: config.example\n"
            "  project: config/proj\n"
        )
        env = {
            **self._ENV,
            "BMAD_LOOP_SETTING_PLATFORM": "github",
            "BMAD_LOOP_SETTING_HOST": "env.example",
            "BMAD_LOOP_SETTING_PROJECT": "env/proj",
        }
        recorder = _Recorder()
        recorder.add(_Recorder.cmd_starts_with("gh"), _FakeProc(0, "[]"))
        repo = tmp_path / "repo"
        repo.mkdir(exist_ok=True)
        (repo / "_bmad" / "custom").mkdir(parents=True, exist_ok=True)
        (repo / "_bmad" / "custom" / "issue-tracking.yaml").write_text(cfg, encoding="utf-8")
        env["BMAD_LOOP_REPO_ROOT"] = str(repo)
        env["BMAD_LOOP_RUN_DIR"] = str(tmp_path / "run")
        rc = ctm.run(env=env, runner=recorder, config_path=None)
        assert rc == 0
        cmd, _ = recorder.calls[0]
        assert cmd[0] == "gh"
        joined = " ".join(cmd)
        # github path uses owner/repo and skips --hostname
        assert "repos/env/proj/pulls" in joined
        assert "--hostname" not in cmd


# -----------------------------------------------------------------------------
# Manifest validation — sanity check that the TOML we ship is parsable + sane
# -----------------------------------------------------------------------------


class TestManifestParses:
    def test_plugin_toml_loads(self):
        # tomllib is stdlib in 3.11+; this test guards the manifest's basic
        # shape so an editor-side typo cannot ship unnoticed.
        import tomllib
        with open(PLUGIN_DIR / "plugin.toml", "rb") as f:
            doc = tomllib.load(f)
        plugin = doc["plugin"]
        assert plugin["name"] == "close-trace-mr"
        assert plugin["api_version"] == 1
        hooks = doc["hooks"]
        assert "post_merge" in hooks
        assert "{scripts}" in hooks["post_merge"]["cmd"]
        assert hooks["post_merge"]["blocking"] is False
        assert hooks["post_merge"]["fail_closed"] is False
        # Settings surface — every key consumed by the hook must be declared.
        declared_keys = {s["key"] for s in doc["settings"]}
        assert "close_trace_mr" in declared_keys
        assert "platform" in declared_keys
        assert "host" in declared_keys
        assert "project" in declared_keys