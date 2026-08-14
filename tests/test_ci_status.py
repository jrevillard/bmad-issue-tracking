"""Tests for ci-status.sh verify command."""

import subprocess
import json
import tempfile
from pathlib import Path


CI_STATUS_SCRIPT = Path(__file__).parent.parent / "skills/bmad-issue-tracking-setup/assets/bmad-loop/ci-gate/ci-status.sh"


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
    """ci-status.sh exits 126 (ENV_FAULT) when ci-status.json is missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            ["bash", str(CI_STATUS_SCRIPT)],
            cwd=tmpdir,
            capture_output=True
        )
        assert result.returncode == 126
        assert "ENV-FAULT" in result.stderr.decode() or "ENV-FAULT" in result.stdout.decode()


def test_ci_status_invalid_json():
    """ci-status.sh exits 1 when ci-status.json is invalid JSON."""
    with tempfile.TemporaryDirectory() as tmpdir:
        status_file = Path(tmpdir) / "ci-status.json"
        status_file.write_text('not json')
        result = subprocess.run(
            ["bash", str(CI_STATUS_SCRIPT)],
            cwd=tmpdir,
            capture_output=True
        )
        assert result.returncode == 1
        assert "failed to parse" in result.stdout.decode() or "unknown status" in result.stdout.decode()


def test_ci_status_missing_status_key():
    """ci-status.sh exits 1 when ci-status.json lacks 'status' key."""
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
