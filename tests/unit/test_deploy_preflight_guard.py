"""deploy_release.sh step 1b — the checkout pre-flight.

On 2026-08-19 the v1.39.0 deploy died at step 3 with exit 128:

    error: Entry 'website/data/uploads/clip/.../original.mp4' not uptodate.

Two user uploads had been committed long ago, the tag no longer tracked them,
so `git checkout` had to inspect them — and the uploads directory is
drwx------ owned by the web user, which the deploy user cannot stat. Nothing
was wrong with the release. The deploy just learned it AFTER step 2 had spent
minutes dumping the database.

The guard has to satisfy two things, and both are tested here: it must detect
that situation, and it must run before the backup. A guard that fires after
the expensive step is only a nicer error message.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

DEPLOY_SCRIPT = Path("scripts/deploy_release.sh")


def _preflight_block() -> str:
    src = DEPLOY_SCRIPT.read_text(encoding="utf-8")
    return src[src.index("1b/8 Pre-flight"):src.index("2/8  Backup DB")]


def _predicate(starts_with: str) -> str:
    """Pull a pre-flight predicate OUT of the deployed script.

    The tests used to hold their own copies of these commands, which meant
    they would happily keep passing after the real ones regressed (coderabbit,
    PR #784). Extracting them means a rename, a dropped filter or a deleted
    check breaks this file instead of going unnoticed.

    The script wraps each predicate in `$SSH "cd $VM_PATH && ... "`; only the
    part from the git command to the closing quote is runnable locally.
    """
    block = _preflight_block()
    start = block.index(starts_with)
    end = block.index('"', start)
    predicate = block[start:end].strip()
    assert predicate, f"no predicate starting with {starts_with!r} in step 1b"
    return predicate


# Run them the way the script does — see the LC_ALL rationale in the script.
TRACKED_DATA_CMD = _predicate("git ls-files -- ")
UNREADABLE_CMD = "export LC_ALL=C && " + _predicate("git ls-files -z")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    ).stdout


def _sh(repo: Path, cmd: str) -> str:
    return subprocess.run(
        ["bash", "-c", cmd], cwd=repo, capture_output=True, text=True
    ).stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.invalid")
    _git(tmp_path, "config", "user.name", "test")
    (tmp_path / "code.py").write_text("x = 1\n")
    _git(tmp_path, "add", "code.py")
    _git(tmp_path, "commit", "-qm", "initial")
    return tmp_path


# ── the guard must run before the money is spent ───────────────────────────


def test_preflight_runs_before_the_database_backup():
    """The whole point: fail in seconds, not after a 240 MB dump."""
    src = DEPLOY_SCRIPT.read_text(encoding="utf-8")
    # Anchor on the step banners, not on the commands: `git checkout -f $TAG`
    # also appears in the TAG-validation comment near the top of the file, and
    # anchoring there compares the guard against a comment (this assertion
    # caught exactly that mistake when it was first written).
    preflight = src.index("1b/8 Pre-flight")
    backup = src.index("2/8  Backup DB")
    checkout = src.index("3/8  Fetch tags")
    assert preflight < backup < checkout, (
        "the pre-flight moved after the backup or the checkout — it no longer "
        "saves anything"
    )


def test_preflight_runs_as_the_deploy_user():
    """Checking as root would prove nothing: the whole failure mode is that
    the DEPLOY user cannot stat a file the checkout must touch."""
    block = _preflight_block()
    assert "sudo_run" not in block, "pre-flight escalated — it must run as $VM_USER"
    assert "$SSH " in block


# ── the predicates actually detect what they claim ─────────────────────────


def test_tracked_runtime_data_is_detected(repo: Path):
    """The exact 2026-08-19 shape: a user upload committed under website/data."""
    upload = repo / "website" / "data" / "uploads" / "clip" / "abc"
    upload.mkdir(parents=True)
    (upload / "original.mp4").write_bytes(b"\x00\x01")
    _git(repo, "add", "-f", "website/data/uploads/clip/abc/original.mp4")
    _git(repo, "commit", "-qm", "oops")

    assert "original.mp4" in _sh(repo, TRACKED_DATA_CMD)


def test_clean_repo_reports_no_tracked_runtime_data(repo: Path):
    assert _sh(repo, TRACKED_DATA_CMD).strip() == ""


@pytest.mark.skipif(os.geteuid() == 0, reason="root can stat through mode 000")
def test_unreadable_tracked_file_is_detected(repo: Path):
    """A directory the deploy user cannot traverse — what drwx------ does to
    a user who is neither the owner nor in the group."""
    secret = repo / "website" / "data" / "uploads"
    secret.mkdir(parents=True)
    (secret / "original.cfg").write_text("seta x 1\n")
    _git(repo, "add", "-f", "website/data/uploads/original.cfg")
    _git(repo, "commit", "-qm", "tracked upload")
    secret.chmod(0o000)
    try:
        out = _sh(repo, UNREADABLE_CMD)
    finally:
        secret.chmod(0o700)  # let tmp_path cleanup succeed
    assert "ermission denied" in out


def test_absent_tracked_file_is_not_a_false_alarm(repo: Path):
    """`git ls-files` reads the INDEX, which may list paths that are absent
    from disk — a sparse checkout, or a skip-worktree entry. Those answer
    'No such file or directory'. Aborting a deploy on that would be a guard
    that cries wolf, so the predicate filters on EACCES only."""
    (repo / "gone.txt").write_text("bye\n")
    _git(repo, "add", "gone.txt")
    _git(repo, "commit", "-qm", "add file")
    (repo / "gone.txt").unlink()

    raw = _sh(repo, "git ls-files -z | xargs -0 -r stat -c '' 2>&1 >/dev/null")
    assert "o such file" in raw, "fixture did not produce the ENOENT case"
    assert _sh(repo, UNREADABLE_CMD).strip() == "", "ENOENT leaked through as a failure"


def test_readability_check_pins_the_locale():
    """`stat` translates its diagnostics and ssh forwards LC_* from the
    client, so a deploy launched from a localised desktop could turn
    "Permission denied" into a string the grep never matches — the guard
    would then pass in silence, which is worse than not having it.

    Asserted rather than exercised: proving it end-to-end needs a second
    locale installed, which neither CI nor the deploy host is guaranteed to
    have. What can be pinned is that the export is there and inside the same
    remote command as the pipeline it protects.
    """
    block = _preflight_block()
    line = next(ln for ln in block.splitlines() if "grep -i 'permission denied'" in ln)
    assert "LC_ALL=C" in line, (
        "the readability check lost its locale pin — a localised stat message "
        "would slip past the grep and the guard would pass silently"
    )

