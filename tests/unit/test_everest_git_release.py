"""Test release branch isolation with temporary local Git repositories."""
import os
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Everest release launcher uses Windows locking")
LAUNCHER = Path(__file__).resolve().parents[2] / "deploy" / "everest_git_release.py"


def git(directory, *args):
    result = subprocess.run(
        ["git", "-c", "core.hooksPath=NUL", "-C", str(directory), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def test_release_uses_main_with_develop_checked_out(tmp_path):
    source = tmp_path / "source"
    runtime = tmp_path / "runtime"
    storage = tmp_path / "storage"
    state = tmp_path / "state"
    source.mkdir()
    storage.mkdir()
    state.mkdir()
    git(source, "init", "--initial-branch=main")
    git(source, "config", "user.name", "Release test")
    git(source, "config", "user.email", "release-test@example.invalid")
    git(source, "commit", "--allow-empty", "-m", "Production revision")
    main = git(source, "rev-parse", "HEAD")
    git(source, "switch", "-c", "develop")
    git(source, "commit", "--allow-empty", "-m", "Development revision")
    develop = git(source, "rev-parse", "HEAD")
    git(tmp_path, "clone", "--no-local", "--branch", "main", str(source), str(runtime))
    assert git(runtime, "rev-parse", "refs/remotes/origin/develop") == develop

    def release(action, *revision):
        return subprocess.run(
            [sys.executable, "-B", str(LAUNCHER), action, *revision,
             "--source", str(source), "--runtime", str(runtime),
             "--storage", str(storage), "--state", str(state)],
            capture_output=True,
            text=True,
        )

    initialized = release("initialize")
    assert initialized.returncode == 0, initialized.stderr
    default = release("check")
    assert default.returncode == 0, default.stderr
    assert f"Runtime commit {main}" in default.stdout
    assert git(runtime, "rev-parse", "refs/pyconlyse-release/main") == main

    denied = release("check", develop)
    assert denied.returncode == 1
    assert "The selected revision must be on main" in denied.stderr
