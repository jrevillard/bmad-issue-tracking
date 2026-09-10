"""Tests for ci-status.sh verify command.

Exit contract (after v2):
  - rc=0  -> CI green, proceed
  - rc=1  -> CI red OR ci-status.json missing/invalid, fixable: bmad-loop runs a
              repair session with the diagnostic as feedback
  - (no rc=126: missing/invalid ci-status.json is treated as fixable, NOT env-fault,
     because the bmad-build-auto on_complete hook is expected to write it)
"""

import subprocess
import tempfile
from pathlib import Path


CI_STATUS_SCRIPT = Path(__file__).parent.parent / "skills/bmad-issue-tracking-setup/scripts/bmad-loop/ci-gate/ci-status.sh"


def test_ci_status_green():
    """ci-status.sh exits 0 when CI is green."""
    with tempfile.TemporaryDirectory() as tmpdir:
        status_file = Path(tmpdir) / "ci-status.json"
        status_file.write_text('{"status": "green"}')
        result = subprocess.run(
            ["bash", str(CI_STATUS_SCRIPT)],
            cwd=tmpdir,
            capture_output=True
        )
        assert result.returncode == 0
        assert "CI green" in result.stdout.decode()


def test_ci_status_red():
    """ci-status.sh exits 1 when CI is red (with diagnostic)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        status_file = Path(tmpdir) / "ci-status.json"
        status_file.write_text('{"status": "red", "pipeline_url": "https://...", "failed_jobs": ["test"], "diagnostic": "Test failed"}')
        result = subprocess.run(
            ["bash", str(CI_STATUS_SCRIPT)],
            cwd=tmpdir,
            capture_output=True
        )
        assert result.returncode == 1
        assert "CI red" in result.stdout.decode()
        # Diagnostic should be output
        assert "red" in result.stdout.decode()


def test_ci_status_missing_file():
    """ci-status.sh exits 1 (fixable) when ci-status.json is missing — on_complete hook did not write it."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            ["bash", str(CI_STATUS_SCRIPT)],
            cwd=tmpdir,
            capture_output=True
        )
        assert result.returncode == 1
        output = (result.stderr.decode() + result.stdout.decode()).lower()
        assert "ci-status.json" in output
        assert "on_complete" in output


def test_ci_status_invalid_json():
    """ci-status.sh exits 1 (fixable) when ci-status.json is invalid JSON."""
    with tempfile.TemporaryDirectory() as tmpdir:
        status_file = Path(tmpdir) / "ci-status.json"
        status_file.write_text('not json')
        result = subprocess.run(
            ["bash", str(CI_STATUS_SCRIPT)],
            cwd=tmpdir,
            capture_output=True
        )
        assert result.returncode == 1  # fixable, NOT env-fault
        output = (result.stderr.decode() + result.stdout.decode()).lower()
        assert "invalid" in output or "parse" in output


def test_ci_status_missing_status_key():
    """ci-status.sh exits 1 (fixable) when ci-status.json lacks 'status' key."""
    with tempfile.TemporaryDirectory() as tmpdir:
        status_file = Path(tmpdir) / "ci-status.json"
        status_file.write_text('{"pipeline_url": "https://..."}')
        result = subprocess.run(
            ["bash", str(CI_STATUS_SCRIPT)],
            cwd=tmpdir,
            capture_output=True
        )
        assert result.returncode == 1


def test_ci_status_unknown_status():
    """ci-status.sh exits 1 when status is unknown."""
    with tempfile.TemporaryDirectory() as tmpdir:
        status_file = Path(tmpdir) / "ci-status.json"
        status_file.write_text('{"status": "unknown"}')
        result = subprocess.run(
            ["bash", str(CI_STATUS_SCRIPT)],
            cwd=tmpdir,
            capture_output=True
        )
        assert result.returncode == 1
        assert "unknown status" in result.stdout.decode()
