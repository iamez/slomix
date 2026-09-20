"""Execute the snapshot CLI against disposable repositories and a local remote."""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/review_snapshots.py"
HOOK = ROOT / "scripts/git-hooks/pre-push"


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.STDOUT).decode().strip()


@pytest.fixture
def repo(tmp_path):
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    git(checkout, "init", "-b", "main")
    git(checkout, "config", "user.name", "Snapshot test")
    git(checkout, "config", "user.email", "snapshot@example.invalid")
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    # Isolated fixture configuration; never changes the real repository hooks.
    git(checkout, "config", "core.hooksPath", str(hooks))
    (checkout / "baseline.txt").write_text("baseline\n")
    git(checkout, "add", "baseline.txt")
    git(checkout, "commit", "-m", "baseline")
    git(checkout, "tag", "v1.39.0")
    remote = tmp_path / "remote.git"
    git(checkout, "init", "--bare", str(remote))
    git(checkout, "remote", "add", "origin", str(remote))
    git(checkout, "push", "origin", "main")
    wrapper = hooks / "pre-push"
    wrapper.write_text(f'#!/bin/bash\nprintf "called\\n" >> "{tmp_path / "hook-calls"}"\nexec bash "{HOOK}" "$@"\n')
    wrapper.chmod(0o755)
    return checkout


def commit(repo, files):
    for name, content in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    git(repo, "add", "--", *files)
    git(repo, "commit", "-m", "source")
    # A local tracking ref gives the genuine hook its normal origin/main base.
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")


def run(repo, *args, area="area|.", check=True):
    result = subprocess.run([sys.executable, str(SCRIPT), "--source", "HEAD",
                             "--area", area, *args], cwd=repo, text=True,
                            capture_output=True)
    if check:
        assert result.returncode == 0, result.stdout + result.stderr
    return result


def snapshots(repo):
    return git(repo, "for-each-ref", "--format=%(refname) %(objectname)",
               "refs/heads/review", "refs/heads/review-base")


def test_split_pushes_use_real_hook_and_are_idempotent_without_worktree_changes(repo):
    commit(repo, {f"file-{n:02}.py": f"value = {n}\n" for n in range(26)})
    (repo / "baseline.txt").write_text("uncommitted owner edit\n")
    (repo / "untracked.txt").write_text("owner scratch\n")
    before = git(repo, "status", "--porcelain"), git(repo, "rev-parse", "HEAD")
    result = run(repo, "cut", "--push")
    assert "files=25 lines=25" in result.stdout
    assert "files=1 lines=1" in result.stdout
    refs = snapshots(repo)
    assert len(refs.splitlines()) == 4
    assert (repo.parent / "hook-calls").read_text().splitlines() == ["called", "called"]
    for line in refs.splitlines():
        ref, sha = line.split()
        assert git(repo, "ls-remote", "origin", ref).split()[0] == sha
        if ref.startswith("refs/heads/review/"):
            assert git(repo, "rev-parse", f"{sha}^{{tree}}") == git(repo, "rev-parse", "HEAD^{tree}")
            stat = git(repo, "diff", "--numstat", f"{sha}^", sha).splitlines()
            assert len(stat) <= 25
            assert sum(int(x) for row in stat for x in row.split()[:2]) <= 8000
    run(repo, "cut", "--push")
    assert snapshots(repo) == refs
    assert (repo.parent / "hook-calls").read_text().splitlines() == ["called", "called"]
    assert before == (git(repo, "status", "--porcelain"), git(repo, "rev-parse", "HEAD"))
    assert (repo / "baseline.txt").read_text() == "uncommitted owner edit\n"


def test_line_splitting_and_oversize_preflight_before_any_refs(repo):
    commit(repo, {"a.py": "a\n" * 4001, "b.py": "b\n" * 4000})
    assert run(repo, "measure").stdout.count("files=1") == 2
    commit(repo, {"z.py": "z\n" * 8001})
    result = run(repo, "cut", "--push", check=False)
    assert result.returncode != 0
    assert "single file exceeds 8000" in result.stderr
    assert snapshots(repo) == ""
    assert not (repo.parent / "hook-calls").exists()
    assert "review" not in git(repo, "ls-remote", "origin")


def test_conflicting_ref_blocks_without_rewriting_and_new_source_gets_new_refs(repo):
    commit(repo, {"a.py": "a\n"})
    run(repo, "cut")
    original = snapshots(repo)
    commit(repo, {"a.py": "b\n"})
    run(repo, "cut")
    assert set(original.splitlines()).issubset(snapshots(repo).splitlines())
    source = git(repo, "rev-parse", "HEAD")
    ref = next(row.split()[0] for row in snapshots(repo).splitlines() if source in row)
    git(repo, "update-ref", ref, "HEAD")
    before = snapshots(repo)
    result = run(repo, "cut", "--push", check=False)
    assert result.returncode != 0
    assert "immutable snapshot conflict" in result.stderr
    assert snapshots(repo) == before


def test_real_secret_scanner_refuses_pair_atomically(repo):
    # Synthetic literal assembled to avoid embedding credentials in this test.
    commit(repo, {"bad.py": "connect(" + "password=" + repr("abcdef" * 3) + ")\n"})
    git(repo, "tag", "archived-baseline")
    commit(repo, {"bad.py": "connect()\n"})
    result = run(repo, "--base", "archived-baseline", "cut", "--push", check=False)
    assert result.returncode != 0
    assert "hardcodes a credential" in result.stderr
    assert "refusing to publish" in result.stderr
    assert "review" not in git(repo, "ls-remote", "origin")
    assert (repo.parent / "hook-calls").read_text() == "called\n"


def test_deleted_files_spaces_and_binary_fail_closed(repo):
    (repo / "baseline.txt").unlink()
    git(repo, "add", "baseline.txt")
    commit(repo, {"space name.py": "print(1)\n"})
    run(repo, "cut")
    head = next(row.split()[1] for row in snapshots(repo).splitlines()
                if row.startswith("refs/heads/review/"))
    assert git(repo, "show", f"{head}^:baseline.txt") == "baseline"
    commit(repo, {"binary.py": "\0binary"})
    before = snapshots(repo)
    result = run(repo, "cut", "--push", check=False)
    assert result.returncode != 0
    assert "binary file needs separate review" in result.stderr
    assert snapshots(repo) == before


def test_remote_conflict_never_updates_existing_remote_ref(repo):
    commit(repo, {"a.py": "a\n"})
    run(repo, "cut")
    ref = snapshots(repo).splitlines()[0].split()[0]
    remote = repo.parent / "remote.git"
    git(remote, "update-ref", ref, "refs/heads/main")
    before = git(repo, "ls-remote", "origin")
    result = run(repo, "cut", "--push", check=False)
    assert result.returncode != 0
    assert "immutable snapshot conflict" in result.stderr
    assert git(repo, "ls-remote", "origin") == before
    assert not (repo.parent / "hook-calls").exists()


def test_genuine_hook_refuses_unsplit_26_file_push(repo):
    commit(repo, {f"file-{n:02}.py": f"value = {n}\n" for n in range(26)})
    git(repo, "update-ref", "refs/remotes/origin/main", "v1.39.0")
    result = subprocess.run(["git", "push", "origin", "HEAD:refs/heads/too-wide"],
                            cwd=repo, text=True, capture_output=True)
    assert result.returncode != 0
    assert "26 files (limit 25)" in result.stderr
    assert "too-wide" not in git(repo, "ls-remote", "origin")
