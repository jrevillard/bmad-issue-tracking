"""close-trace-mr: logic for the `post_merge` declarative hook.

This module is invoked by `close-trace-mr.sh` via `uv run --no-project python`,
so it must remain stdlib-only (no pyyaml, no requests). Everything is exposed
as plain functions that take their dependencies as parameters — `subprocess.run`
is injectable so unit tests do not spawn real CLI processes, and a small YAML
parser handles the few keys we read from `_bmad/custom/issue-tracking.yaml`.

Contract:
    The bus calls the script at `post_merge`. The script's exit code is the bus
    signal: `blocking = false` in the manifest means non-zero is logged and the
    run continues, so we exit non-zero only on a CONFIG error (no platform
    resolvable — the operator cannot have intended an empty config to fire
    a close). Subprocess failures (a glab call that returns non-zero) are
    reported on stderr and counted, but the script still exits 0 unless the
    WHOLE close attempt is unrecoverable.

Marker file:
    `$BMAD_LOOP_RUN_DIR/post-merge-<story_key>.md` — a small YAML front-matter
    block that records which MRs were closed (or that none were open). The
    bus does NOT read this file; it is a human-observable side effect.

Idempotency:
    Closing an already-closed MR/PR is a no-op for the script's purposes. A
    GitLab `state_event=close` on a closed MR returns 409 + a payload; we treat
    "already closed" as success. `gh pr close` returns its own already-closed
    message; same handling.

Defensive sweep:
    If 2+ open MRs exist for the same source branch (e.g. an earlier duplicate
    the operator forgot to clean up), every open MR is closed.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Mapping

# -----------------------------------------------------------------------------
# Types
# -----------------------------------------------------------------------------

# The CLI runner is injectable so tests can swap in a fake without spawning
# real processes. Signature mirrors subprocess.run(...).
Runner = Callable[..., "subprocess.CompletedProcess[str]"]


@dataclass(frozen=True)
class Ctx:
    """Resolved runtime context the hook operates in.

    Every field is required except `run_dir` (the marker location — empty
    means we still try the close but skip writing the marker file). The
    `close_trace_mr` flag is the master switch from the manifest's settings.
    """

    platform: str       # "gitlab" | "github"
    host: str           # "gitlab.example.com" | "github.com" | ""
    project: str        # "group/sub/repo" | "owner/repo"
    branch: str         # the source branch the trace MR targets
    story_key: str      # used for marker filename + log lines
    run_dir: str        # bmad-loop run dir; "" skips the marker file
    close_trace_mr: bool # operator opt-out (settings.close_trace_mr)
    stage: str = "post_merge"  # the firing stage (for the marker file)


@dataclass(frozen=True)
class CloseResult:
    """One MR/PR close outcome — what we put in the marker file + journal."""

    iid: int
    state: str  # "closed" | "already_closed" | "failed"
    message: str = ""


# -----------------------------------------------------------------------------
# Constants — surface area for tests + reader-friendly config
# -----------------------------------------------------------------------------

PLATFORMS = ("gitlab", "github")

# File name: sits at the run dir root, named after the story, parallel to the
# journal.jsonl + ATTENTION files the orchestrator already writes there.
_MARKER_PREFIX = "post-merge-"
_MARKER_SUFFIX = ".md"

# Subprocess timeout per CLI invocation. The hook timeout (manifest) is 30s;
# split it: list (5s) + close * N (5s each, max 3) + marker write (1s) + slack.
# Each subprocess call gets a slice so a single hung CLI does not eat the
# whole budget — bmad-loop will kill the hook at the manifest timeout anyway.
_SUBPROC_TIMEOUT_SEC = 10

# glab JSON for a list endpoint wraps the array under a header that we ignore
# (`X-Total`, `X-Next-Page`); the body is a JSON array. gh API returns the same.
_EMPTY_LIST_SENTINELS = ("[]", "", "null")


# -----------------------------------------------------------------------------
# Env var extraction — pure, testable
# -----------------------------------------------------------------------------

def get_env_values(env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Pull every BMAD_LOOP_* var the hook uses. Defaults to os.environ.

    Returned keys are normalised to snake_case so the rest of the module never
    reads the raw `BMAD_LOOP_*` names (keeps the call sites readable and the
    unit tests focused on shape, not casing).
    """
    src = env if env is not None else os.environ
    enabled_raw = src.get("BMAD_LOOP_SETTING_CLOSE_TRACE_MR", "true")
    return {
        "branch": src.get("BMAD_LOOP_BRANCH", ""),
        "story_key": src.get("BMAD_LOOP_STORY_KEY", ""),
        "run_dir": src.get("BMAD_LOOP_RUN_DIR", ""),
        "stage": src.get("BMAD_LOOP_STAGE", ""),
        "repo_root": src.get("BMAD_LOOP_REPO_ROOT", ""),
        "platform_override": src.get("BMAD_LOOP_SETTING_PLATFORM", ""),
        "host_override": src.get("BMAD_LOOP_SETTING_HOST", ""),
        "project_override": src.get("BMAD_LOOP_SETTING_PROJECT", ""),
        "enabled": enabled_raw.strip().lower() not in ("false", "0", "no", ""),
    }


# -----------------------------------------------------------------------------
# Minimal YAML reader for _bmad/custom/issue-tracking.yaml
# -----------------------------------------------------------------------------

# Only the keys we care about — a 4-line file format with 2-space indent. We
# do NOT pull pyyaml: uv --no-project runs against whatever python is active,
# and pyyaml is not guaranteed to be installed there. A 30-line regex-based
# reader handles this file's actual shape (the file is hand-written by the
# setup skill; it never contains nested mapping/list values for the keys we
# read). The reader is permissive about whitespace and tolerant of comments;
# it raises ConfigParseError on truly broken input so the operator gets a
# useful message rather than a silent empty result.

_CONFIG_KEYS = frozenset({"platform", "host", "project", "git_host", "git_project"})

# Captures `key: value` where key is one of the names we care about, value
# can be a bare word or a quoted string. Tolerant of trailing comments.
_LINE_RE = re.compile(
    r"^\s*(?P<key>platform|host|project|git_host|git_project)\s*:\s*"
    r"(?:\"(?P<dq>[^\"]*)\"|'(?P<sq>[^']*)'|(?P<bare>[^#\s][^#]*?))\s*(?:#.*)?$"
)


class ConfigParseError(ValueError):
    """Raised when issue-tracking.yaml exists but cannot be parsed at all."""


def parse_issue_tracking_config(path: Path) -> dict[str, str]:
    """Read the few keys we care about from `_bmad/custom/issue-tracking.yaml`.

    Lenient by design — returns an empty dict for any non-matching file. The
    file is hand-written by `bmad-issue-tracking-setup`'s step 6 and always
    carries `platform` + `host` + `project` together, but we tolerate:
      * a missing file (the project does not use bmad-issue-tracking);
      * a file with only sibling keys we don't read (`worktree_base`,
        `branch_patterns`, `enabled`, etc.);
      * a file the operator has overwritten with unrelated yaml;
      * an empty / malformed file.

    In every case the hook no-ops cleanly downstream (resolve_ctx returns
    None when no `platform` is found). The only place we raise is the
    platform-value validation in `resolve_ctx` — `bitbucket` is not a
    supported target, that is the operator's misconfiguration to fix.
    """
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8")
    out: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = _LINE_RE.match(line)
        if not m:
            continue
        value = m.group("dq") if m.group("dq") is not None else (
            m.group("sq") if m.group("sq") is not None else m.group("bare").strip()
        )
        out[m.group("key")] = value
    return out


# -----------------------------------------------------------------------------
# Context resolution — overlay order: env > config > auto
# -----------------------------------------------------------------------------

def resolve_ctx(env_values: Mapping[str, str], config: Mapping[str, str]) -> Ctx | None:
    """Build the runtime Ctx from env values and parsed config.

    Returns None when the platform is missing AND the host/project cannot be
    inferred — i.e. when there is genuinely no tracker to talk to. The caller
    must treat None as "no-op, log to stderr, exit 0".
    """
    platform = env_values.get("platform_override", "") or config.get("platform", "")
    host = env_values.get("host_override", "") or config.get("host", "")
    project = env_values.get("project_override", "") or config.get("project", "")
    if not platform:
        return None
    platform = platform.strip().lower()
    if platform not in PLATFORMS:
        # Operator put garbage in their config — fail loudly so they fix it.
        raise ConfigParseError(
            f"unsupported platform {platform!r}; expected one of {PLATFORMS}"
        )
    # GitHub uses api.github.com; host may legitimately be empty. For GitLab,
    # host is required (gitlab.com is the SaaS default).
    if platform == "gitlab" and not host:
        host = "gitlab.com"
    if not project:
        return None
    return Ctx(
        platform=platform,
        host=host,
        project=project.strip(),
        branch=env_values.get("branch", "").strip(),
        story_key=env_values.get("story_key", "").strip(),
        run_dir=env_values.get("run_dir", "").strip(),
        close_trace_mr=bool(env_values.get("enabled", True)),
        stage=env_values.get("stage", "post_merge").strip() or "post_merge",
    )


# -----------------------------------------------------------------------------
# CLI invocations — pure except for the injected Runner
# -----------------------------------------------------------------------------

def list_open_mrs(
    runner: Runner,
    ctx: Ctx,
) -> list[int]:
    """Find open MRs/PRs whose source_branch == ctx.branch. Empty list = none.

    GitLab: `glab api projects/{url-encoded project}/merge_requests?source_branch=X&state=opened`
            — the body is a JSON array of MR objects; we extract `iid`.
    GitHub: `gh api repos/{owner}/{repo}/pulls?head={owner}:{branch}&state=open`
            — body is a JSON array of PR objects; we extract `number`.

    The script treats a non-zero exit or a non-JSON body as "no MRs found"
    (logged on stderr) so a transient CLI error does NOT abort the run.
    """
    if ctx.platform == "gitlab":
        cmd = [
            "glab", "api",
            f"projects/{ctx.project}/merge_requests",
            "--hostname", ctx.host,
            "--paginate",
            "-F", "source_branch", ctx.branch,
            "-F", "state", "opened",
        ]
        iid_key = "iid"
    else:  # github
        # `head` is `owner:branch` per the GitHub REST contract; we only know
        # `branch`, so we use the search-shaped endpoint that takes branch only.
        cmd = [
            "gh", "api",
            f"repos/{ctx.project}/pulls",
            "-R", ctx.project,
            "-f", f"head={ctx.branch}",
            "-f", "state=open",
            "--paginate",
        ]
        iid_key = "number"

    proc = runner(cmd, capture_output=True, text=True, timeout=_SUBPROC_TIMEOUT_SEC)
    if proc.returncode != 0:
        print(
            f"[close-trace-mr] list failed (rc={proc.returncode}): "
            f"{proc.stderr.strip() or proc.stdout.strip()}",
            file=sys.stderr,
        )
        return []
    body = (proc.stdout or "").strip()
    if body in _EMPTY_LIST_SENTINELS:
        return []
    try:
        items = json.loads(body)
    except json.JSONDecodeError:
        print(f"[close-trace-mr] list returned non-JSON body: {body[:200]!r}", file=sys.stderr)
        return []
    if not isinstance(items, list):
        return []
    out: list[int] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        iid = item.get(iid_key)
        if isinstance(iid, int):
            out.append(iid)
        elif isinstance(iid, str) and iid.isdigit():
            out.append(int(iid))
    return out


def close_one(runner: Runner, ctx: Ctx, iid: int) -> CloseResult:
    """Close a single MR/PR. Classifies the outcome for the marker file.

    GitLab: `glab api projects/.../merge_requests/{iid} -X PUT -F state_event=close`
            — 200 OK on success, 409 with "Already closed" body when closed.
    GitHub: `gh pr close <iid> -R <project> [--delete-branch false]`
            — exit 0 even when already closed (message on stdout); non-zero
              only on real failures.

    Failure: a non-zero exit with no "already closed" signal → state="failed"
    so the marker records the miss and the operator can re-run by hand.
    """
    if ctx.platform == "gitlab":
        cmd = [
            "glab", "api",
            f"projects/{ctx.project}/merge_requests/{iid}",
            "--hostname", ctx.host,
            "-X", "PUT",
            "-F", "state_event", "close",
        ]
    else:  # github
        cmd = [
            "gh", "pr", "close", str(iid),
            "-R", ctx.project,
            "--delete-branch", "false",
        ]
    proc = runner(cmd, capture_output=True, text=True, timeout=_SUBPROC_TIMEOUT_SEC)
    combined = (proc.stdout + proc.stderr).lower()
    # Idempotency: classify the response before exit-code gating. GitLab
    # reports an already-closed MR as HTTP 409 with "already closed" in the
    # body (rc != 0); GitHub reports rc=0 with a "already closed" stdout.
    # "Closed" alone is too greedy — `gh pr close` prints "✓ Closed pull
    # request #11" on a real success, so we ONLY treat the explicit "already"
    # signal as already_closed and let the rc==0 path absorb the rest.
    if "already" in combined:
        return CloseResult(iid=iid, state="already_closed")
    if proc.returncode == 0:
        return CloseResult(iid=iid, state="closed")
    return CloseResult(
        iid=iid,
        state="failed",
        message=(proc.stderr or proc.stdout).strip()[:500],
    )


# -----------------------------------------------------------------------------
# Marker file
# -----------------------------------------------------------------------------

def write_marker(
    out_dir: str,
    ctx: Ctx,
    results: list[CloseResult],
) -> Path | None:
    """Write the post-merge marker to `$out_dir/post-merge-<story_key>.md`.

    Atomic write (temp + rename) so a concurrent reader never sees a half-
    written marker. Returns None when out_dir is empty (the hook caller can
    still proceed — the marker is observability, not a contract).
    """
    if not out_dir:
        return None
    d = Path(out_dir)
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"[close-trace-mr] cannot create run_dir {out_dir}: {e}", file=sys.stderr)
        return None
    safe_key = re.sub(r"[^A-Za-z0-9._-]", "_", ctx.story_key) or "unknown"
    final = d / f"{_MARKER_PREFIX}{safe_key}{_MARKER_SUFFIX}"
    closed = [r.iid for r in results if r.state in ("closed", "already_closed")]
    failed = [r for r in results if r.state == "failed"]
    body = (
        "---\n"
        "status: done\n"
        f"stage: {ctx.stage or 'post_merge'}\n"
        f"story_key: {ctx.story_key}\n"
        f"branch: {ctx.branch}\n"
        f"platform: {ctx.platform}\n"
        f"project: {ctx.project}\n"
        f"host: {ctx.host}\n"
        f"closed_mrs: {closed}\n"
        f"failed_mrs: {[r.iid for r in failed]}\n"
        f"results:\n"
        + "\n".join(
            f"  - iid: {r.iid}\n    state: {r.state}\n    message: {r.message!r}"
            for r in results
        )
        + "\n---\n"
    )
    tmp = final.with_suffix(final.suffix + ".tmp")
    try:
        tmp.write_text(body, encoding="utf-8")
        os.replace(tmp, final)
    except OSError as e:
        print(f"[close-trace-mr] marker write failed at {final}: {e}", file=sys.stderr)
        return None
    return final


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------

def run(
    env: Mapping[str, str] | None = None,
    *,
    runner: Runner | None = None,
    config_path: Path | None = None,
) -> int:
    """Top-level orchestrator. Returns a process exit code.

    Exit codes:
        0  — clean (no MRs to close, all closed, or operator opt-out).
        1  — fatal config error (operator must fix).
        2  — partial close (some MRs failed); the bus logs `plugin-hook rc=2`
             but the run continues (manifest `blocking = false`).
    """
    _runner = runner or subprocess.run
    env_values = get_env_values(env)

    if not env_values["enabled"]:
        print("[close-trace-mr] disabled by setting; skipping.", file=sys.stderr)
        return 0

    # Resolve config from env-provided path, else default to the conventional
    # project-relative location. Tests override this.
    cfg_path = config_path or _default_config_path(env_values.get("repo_root", ""))
    config: dict[str, str]
    try:
        config = parse_issue_tracking_config(cfg_path) if cfg_path else {}
    except ConfigParseError as e:
        print(f"[close-trace-mr] {e}", file=sys.stderr)
        return 1

    try:
        ctx = resolve_ctx(env_values, config)
    except ConfigParseError as e:
        print(f"[close-trace-mr] {e}", file=sys.stderr)
        return 1
    if ctx is None:
        print(
            "[close-trace-mr] no tracker configured "
            "(set _bmad/custom/issue-tracking.yaml or [plugins.close-trace-mr] overrides); skipping.",
            file=sys.stderr,
        )
        return 0

    if not ctx.branch:
        print("[close-trace-mr] BMAD_LOOP_BRANCH is empty; nothing to close.", file=sys.stderr)
        return 0

    iids = list_open_mrs(_runner, ctx)
    if not iids:
        print(
            f"[close-trace-mr] no open MR/PR on {ctx.platform} "
            f"with source_branch={ctx.branch}; nothing to do.",
            file=sys.stderr,
        )
        write_marker(ctx.run_dir, ctx, results=[])
        return 0

    results: list[CloseResult] = [close_one(_runner, ctx, iid) for iid in iids]
    write_marker(ctx.run_dir, ctx, results)

    failed = [r for r in results if r.state == "failed"]
    if failed:
        print(
            f"[close-trace-mr] {len(failed)}/{len(results)} MRs failed to close: "
            + ", ".join(f"#{r.iid}({r.message[:80]})" for r in failed),
            file=sys.stderr,
        )
        return 2
    print(
        f"[close-trace-mr] closed {len(results)} MR(s) for branch {ctx.branch}: "
        + ", ".join(f"#{r.iid}" for r in results),
        file=sys.stderr,
    )
    return 0


def _default_config_path(repo_root: str) -> Path | None:
    """The conventional `_bmad/custom/issue-tracking.yaml` location.

    `uv run --no-project` does NOT change cwd; the bus runs hooks with
    `cwd = ctx.worktree or ctx.repo_root`, so `repo_root` from BMAD_LOOP_REPO_ROOT
    is the right anchor. Falls back to None when no repo_root was provided
    (e.g. unit tests without env).
    """
    if not repo_root:
        return None
    return Path(repo_root) / "_bmad" / "custom" / "issue-tracking.yaml"


if __name__ == "__main__":
    sys.exit(run())