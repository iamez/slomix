"""Execute the snapshot CLI against disposable repositories and a local remote."""
import os
import shutil
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


def commit(repo, files, *, published=True):
    for name, content in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    git(repo, "add", "--", *files)
    git(repo, "commit", "-m", "source")
    # A local tracking ref gives the genuine hook its normal origin/main base.
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    if published:
        # Fixture setup: source is already public on this disposable destination.
        # No production remote or hook is changed.
        git(repo.parent / "remote.git", "fetch", "--quiet", str(repo),
            "HEAD:refs/heads/main")


def test_unpublished_source_cannot_leak_excluded_history(repo):
    commit(repo, {"a.py": "selected\n", "b.txt": "private fixture\n"}, published=False)
    before = git(repo, "ls-remote", "origin")
    result = run(repo, "cut", "--push", area="safe|a.py", check=False)
    assert result.returncode != 0, "unpublished parent leaked unselected history"
    assert "source must already be advertised" in result.stderr
    assert git(repo, "ls-remote", "origin") == before
    assert snapshots(repo) == ""
    source = git(repo, "rev-parse", "HEAD")
    probe = subprocess.run(["git", "-C", str(repo.parent / "remote.git"),
                            "cat-file", "-e", source], capture_output=True)
    assert probe.returncode != 0


@pytest.mark.parametrize("raced", ["review-base", "review"])
def test_symbolic_local_review_ref_is_rejected(repo, raced):
    commit(repo, {"a.py": "selected\n"})
    run(repo, "cut")
    refs = dict(line.split() for line in snapshots(repo).splitlines())
    ref = next(ref for ref in refs if f"/{raced}/" in ref)
    git(repo, "update-ref", "refs/heads/mutable-alias", refs[ref])
    git(repo, "symbolic-ref", ref, "refs/heads/mutable-alias")
    result = run(repo, "cut", "--push", check=False)
    assert result.returncode != 0, "symbolic review ref was certified immutable"
    assert snapshots(repo.parent / "remote.git") == ""
    assert git(repo, "symbolic-ref", ref) == "refs/heads/mutable-alias"


@pytest.mark.parametrize("raced", ["review-base", "review"])
def test_symbolic_ref_race_is_rejected_in_transaction(repo, monkeypatch, raced):
    commit(repo, {"a.py": "selected\n"})
    run(repo, "cut")
    refs = dict(line.split() for line in snapshots(repo).splitlines())
    ref = next(ref for ref in refs if f"/{raced}/" in ref)
    alias = "refs/heads/mutable-alias"
    git(repo, "update-ref", alias, refs[ref])
    real_git = shutil.which("git")
    tools = repo.parent / "symbolic-race"
    tools.mkdir()
    wrapper = tools / "git"
    wrapper.write_text(
        f"#!{sys.executable}\nimport os, subprocess, sys\n"
        f"real_git = {real_git!r}\n"
        "if sys.argv[1] == 'update-ref' and '--stdin' in sys.argv:\n"
        f"    subprocess.run([real_git, 'symbolic-ref', {ref!r}, {alias!r}], check=True)\n"
        "os.execv(real_git, [real_git, *sys.argv[1:]])\n"
    )
    wrapper.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tools}{os.pathsep}{os.environ['PATH']}")
    result = run(repo, "cut", "--push", check=False)
    assert result.returncode != 0, "raced symbolic ref passed transaction verification"
    assert snapshots(repo.parent / "remote.git") == ""
    assert git(repo, "symbolic-ref", ref) == alias
    assert git(repo, "rev-parse", alias) == refs[ref]


def test_source_on_fetch_remote_only_cannot_authorize_push_destination(repo):
    commit(repo, {"a.py": "selected\n"})
    destination = repo.parent / "empty-push.git"
    git(repo, "init", "--bare", str(destination))
    git(repo, "remote", "set-url", "--push", "origin", str(destination))
    result = run(repo, "cut", "--push", check=False)
    assert result.returncode != 0
    assert "source must already be advertised" in result.stderr
    assert snapshots(repo) == snapshots(destination) == ""


@pytest.mark.parametrize("filename", ["archive\n.zip", "archive\t.zip", 'archive".zip'])
def test_unusual_raw_filename_does_not_escape_guard(repo, filename):
    commit(repo, {filename: "historical fixture\n"})
    git(repo, "tag", "archived-baseline")
    commit(repo, {filename: ""})
    result = run(repo, "--base", "archived-baseline", "cut", "--push", check=False)
    assert result.returncode != 0, "quoted filename bypassed the publication guard"
    assert "repository publication guard failed" in result.stderr
    assert snapshots(repo) == snapshots(repo.parent / "remote.git") == ""


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


@pytest.mark.parametrize("all_existing", [False, True])
@pytest.mark.parametrize("raced", ["review-base", "review"])
def test_local_existing_ref_race_is_verified_in_transaction(repo, monkeypatch, all_existing, raced):
    commit(repo, {"a.py": "value = 1\n"})
    run(repo, "cut")
    expected = dict(line.split() for line in snapshots(repo).splitlines())
    existing = next(ref for ref in expected if f"/{raced}/" in ref)
    missing = next(ref for ref in expected if ref != existing)
    if not all_existing:
        git(repo, "update-ref", "-d", missing)
    ancestor = git(repo, "rev-parse", "v1.39.0")
    real_git = shutil.which("git")
    wrapper_dir = repo.parent / "race-bin"
    wrapper_dir.mkdir()
    wrapper = wrapper_dir / "git"
    wrapper.write_text(
        f"#!{sys.executable}\nimport os, subprocess, sys\n"
        f"real_git = {real_git!r}\n"
        "if sys.argv[1:] == ['for-each-ref', '--format=%(objectname) %(refname)', 'refs/heads']:\n"
        "    result = subprocess.run([real_git, *sys.argv[1:]], capture_output=True)\n"
        f"    subprocess.run([real_git, 'update-ref', {existing!r}, {ancestor!r}], check=True)\n"
        "    sys.stdout.buffer.write(result.stdout)\n"
        "    sys.exit(result.returncode)\n"
        "os.execv(real_git, [real_git, *sys.argv[1:]])\n"
    )
    wrapper.chmod(0o755)
    monkeypatch.setenv("PATH", f"{wrapper_dir}{os.pathsep}{os.environ['PATH']}")
    result = run(repo, "cut", "--push", check=False)
    assert result.returncode != 0, "stale local refs were reported as a successful immutable cut"
    assert "cannot lock ref" in result.stderr
    actual = dict(line.split() for line in snapshots(repo).splitlines())
    assert actual[existing] == ancestor
    assert (actual.get(missing) == expected[missing]) if all_existing else missing not in actual
    assert snapshots(repo.parent / "remote.git") == ""
    assert not (repo.parent / "hook-calls").exists()


@pytest.mark.parametrize("attribute", ["diff=forced", "diff"])
@pytest.mark.parametrize("deleted", [False, True])
def test_binary_attributes_cannot_force_raw_nul_blob_into_text_review(repo, attribute, deleted):
    (repo / ".git/info/attributes").write_text(f"*.py {attribute}\n")
    git(repo, "config", "diff.forced.binary", "false")
    commit(repo, {"binary.py": "a\0b\n"})
    base = "v1.39.0"
    if deleted:
        base = git(repo, "rev-parse", "HEAD")
        (repo / "binary.py").unlink()
        git(repo, "add", "binary.py")
        git(repo, "commit", "-m", "remove binary")
    # Independent Git measurement proves the original numstat-only gate is bypassed.
    assert git(repo, "diff", "--numstat", base, "HEAD").split()[0] != "-"
    result = run(repo, "--base", base, "cut", "--push", check=False)
    assert result.returncode != 0, "attributes bypassed binary admission"
    assert "binary file needs separate review" in result.stderr
    assert snapshots(repo) == snapshots(repo.parent / "remote.git") == ""


@pytest.mark.parametrize("target", ["source", "baseline", "blob", "tree"])
def test_replace_objects_cannot_redefine_pinned_snapshot(repo, target):
    commit(repo, {"a.py": "source = 1\n"})
    source = git(repo, "rev-parse", "HEAD")
    source_tree = git(repo, "rev-parse", "HEAD^{tree}")
    baseline = git(repo, "rev-parse", "v1.39.0")
    run(repo, "cut")
    expected = snapshots(repo)
    commit(repo, {"a.py": "replacement = 9\n", "unselected.py": "must not leak\n"})
    alternate = git(repo, "rev-parse", "HEAD")
    original, replacement = {
        "source": (source, alternate), "baseline": (baseline, alternate),
        "blob": (git(repo, "rev-parse", f"{source}:a.py"), git(repo, "rev-parse", "HEAD:a.py")),
        "tree": (source_tree, git(repo, "rev-parse", "HEAD^{tree}")),
    }[target]
    git(repo, "replace", original, replacement)
    run(repo, "--source", source, "cut", "--push")
    assert snapshots(repo) == expected
    head = next(line.split()[1] for line in expected.splitlines() if "/review/" in line)
    # Read the actual objects through an independent Git path and bare remote.
    assert git(repo, "--no-replace-objects", "rev-parse", f"{head}^{{tree}}") == source_tree
    assert git(repo.parent / "remote.git", "show", f"{head}:a.py") == "source = 1"
    assert "unselected.py" not in git(repo.parent / "remote.git", "ls-tree", "-r", "--name-only", head)


def test_signed_source_ignores_log_show_signature(repo):
    key = repo.parent / "signing-key"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
    allowed = repo.parent / "allowed-signers"
    allowed.write_text("snapshot@example.invalid " + key.with_suffix(".pub").read_text())
    git(repo, "config", "gpg.format", "ssh")
    git(repo, "config", "user.signingkey", str(key))
    git(repo, "config", "gpg.ssh.allowedSignersFile", str(allowed))
    git(repo, "config", "commit.gpgsign", "true")
    commit(repo, {"a.py": "value = 1\n"})
    run(repo, "cut")
    expected = snapshots(repo)
    git(repo, "config", "log.showSignature", "true")
    assert "Good" in git(repo, "show", "-s", "--format=%cI", "HEAD")
    run(repo, "cut")
    assert snapshots(repo) == expected


def test_blob_replacement_cannot_hide_raw_binary_source(repo):
    (repo / ".git/info/attributes").write_text("*.py diff\n")
    commit(repo, {"binary.py": "raw\0binary\n", "text.py": "plain text\n"})
    blob = git(repo, "rev-parse", "HEAD:binary.py")
    replacement = git(repo, "rev-parse", "HEAD:text.py")
    git(repo, "replace", blob, replacement)
    assert git(repo, "cat-file", "blob", blob) == "plain text"
    assert "\0" in git(repo, "--no-replace-objects", "cat-file", "blob", blob)
    result = run(repo, "cut", "--push", check=False)
    assert result.returncode != 0, "replacement hid the raw binary object from admission"
    assert "binary file needs separate review" in result.stderr
    assert snapshots(repo) == snapshots(repo.parent / "remote.git") == ""


def test_detached_checkout_without_local_branches_can_cut(repo):
    commit(repo, {"a.py": "value = 1\n"})
    git(repo, "checkout", "--detach")
    git(repo, "update-ref", "-d", "refs/heads/main")
    assert git(repo, "for-each-ref", "refs/heads") == ""
    run(repo, "cut")
    assert len(snapshots(repo).splitlines()) == 2


def test_separate_push_destination_is_inspected_and_published(repo):
    commit(repo, {"a.py": "value = 1\n"})
    run(repo, "cut", "--push")  # Fetch remote already has the expected pair.
    expected = snapshots(repo)
    destination = repo.parent / "push.git"
    git(repo, "init", "--bare", str(destination))
    git(repo, "remote", "set-url", "--push", "origin", str(destination))
    git(destination, "fetch", "--quiet", str(repo), "HEAD:refs/heads/main")
    run(repo, "cut", "--push")
    assert snapshots(destination) == expected
    assert len((repo.parent / "hook-calls").read_text().splitlines()) == 2
    run(repo, "cut", "--push")
    assert len((repo.parent / "hook-calls").read_text().splitlines()) == 2


def test_multiple_push_destinations_fail_before_ref_creation(repo):
    commit(repo, {"a.py": "value = 1\n"})
    destination = repo.parent / "push.git"
    git(repo, "init", "--bare", str(destination))
    git(repo, "remote", "set-url", "--add", "--push", "origin", str(repo.parent / "remote.git"))
    git(repo, "remote", "set-url", "--add", "--push", "origin", str(destination))
    result = run(repo, "cut", "--push", check=False)
    assert result.returncode != 0
    assert "exactly one push URL" in result.stderr
    assert snapshots(repo) == snapshots(destination) == snapshots(repo.parent / "remote.git") == ""
    assert not (repo.parent / "hook-calls").exists()


def test_separate_push_conflict_blocks_before_local_refs(repo):
    commit(repo, {"a.py": "value = 1\n"})
    source, base = git(repo, "rev-parse", "HEAD"), git(repo, "rev-parse", "v1.39.0")
    destination = repo.parent / "remote.git"
    ref = f"refs/heads/review-base/v2-{source}-{base}/area-p001"
    git(destination, "update-ref", ref, base)
    fetch = repo.parent / "fetch.git"
    git(repo, "init", "--bare", str(fetch))
    git(repo, "remote", "set-url", "origin", str(fetch))
    git(repo, "remote", "set-url", "--push", "origin", str(destination))
    before = snapshots(destination)
    result = run(repo, "cut", "--push", check=False)
    assert result.returncode != 0 and "immutable snapshot conflict" in result.stderr
    assert snapshots(repo) == snapshots(fetch) == ""
    assert snapshots(destination) == before
    assert not (repo.parent / "hook-calls").exists()


def test_commit_encoding_does_not_change_immutable_snapshot(repo):
    commit(repo, {"a.py": "value = 1\n"})
    run(repo, "cut")
    expected = snapshots(repo)
    git(repo, "config", "i18n.commitEncoding", "ISO-8859-1")
    run(repo, "cut")
    assert snapshots(repo) == expected


def test_diff_algorithm_does_not_change_snapshot_partition(repo):
    old = list("aacbbbaeaedaaabbeeaebedbdecabdccbbcaadaccecadeadaececebaabcabadcdcbccbcaebebbddc")
    new = list("ebcabacdcabecbdddbcbbeecededcbbedaaabbdeaddedeceaaeccacdbdacebeaceebbcbeeaecdaac")
    old[10] = new[60] = "unique-anchor"
    commit(repo, {"z.py": "\n".join(old) + "\n"})
    base = git(repo, "rev-parse", "HEAD")
    commit(repo, {"z.py": "\n".join(new) + "\n"})
    counts = {}
    for algorithm in ("myers", "patience"):
        row = git(repo, "diff", f"--diff-algorithm={algorithm}", "--numstat", base, "HEAD")
        counts[algorithm] = sum(map(int, row.split()[:2]))
    assert counts["myers"] < counts["patience"], counts
    commit(repo, {"a.py": "filler\n" * (8000 - counts["myers"])})
    git(repo, "config", "diff.algorithm", "myers")
    first = run(repo, "--base", base, "cut")
    expected = snapshots(repo)
    assert "files=2 lines=8000" in first.stdout
    git(repo, "config", "diff.algorithm", "patience")
    second = run(repo, "--base", base, "cut")
    assert "files=2 lines=8000" in second.stdout
    assert snapshots(repo) == expected
    head = next(sha for ref, sha in (line.split() for line in expected.splitlines())
                if ref.startswith("refs/heads/review/"))
    rows = git(repo, "diff", "--diff-algorithm=myers", "--numstat", f"{head}^", head)
    assert sum(int(n) for row in rows.splitlines() for n in row.split()[:2]) == 8000


def test_diff_order_file_does_not_change_snapshot_partition(repo):
    names = [f"file-{number:02}.py" for number in range(26)]
    commit(repo, dict.fromkeys(names, "value = 1\n"))
    run(repo, "cut")
    expected = snapshots(repo)
    order = repo.parent / "reverse-order"
    order.write_text("\n".join(reversed(names)) + "\n")
    git(repo, "config", "diff.orderFile", str(order))
    # Establish that actual Git observes the ambient configuration.
    measured = git(repo, "diff", "--name-only", "v1.39.0", "HEAD").splitlines()
    assert measured == list(reversed(names))
    run(repo, "cut")
    assert snapshots(repo) == expected
    assert len(expected.splitlines()) == 4
    order.unlink()
    run(repo, "cut")
    assert snapshots(repo) == expected


@pytest.mark.parametrize("hook_mode", ["absent", "disabled", "unrelated", "missing-order"])
def test_bundled_guard_blocks_history_without_installed_guard(repo, hook_mode):
    commit(repo, {"z-archive.db": "historical forbidden data\n", "a.py": "old\n"})
    git(repo, "tag", "archived-baseline")
    commit(repo, {"z-archive.db": "", "a.py": "new\n"})
    hook = repo.parent / "hooks/pre-push"
    if hook_mode in ("absent", "missing-order"):
        hook.unlink()
    elif hook_mode == "disabled":
        hook.chmod(0o644)
    else:
        hook.write_text("#!/bin/sh\nexit 0\n")
    if hook_mode == "missing-order":
        git(repo, "config", "diff.orderFile", str(repo.parent / "missing-order"))
    result = run(repo, "--base", "archived-baseline", "--area", "bad|z-archive.db",
                 "cut", "--push", area="safe|a.py", check=False)
    assert result.returncode != 0
    assert "repository publication guard failed" in result.stderr
    assert snapshots(repo) == snapshots(repo.parent / "remote.git") == ""
    assert not (repo.parent / "hook-calls").exists()


def test_bundled_guard_allows_safe_publication_without_installed_hook(repo):
    commit(repo, {"a.py": "value = 1\n"})
    (repo.parent / "hooks/pre-push").unlink()
    run(repo, "cut", "--push")
    assert len(snapshots(repo).splitlines()) == 2
    assert snapshots(repo) == snapshots(repo.parent / "remote.git")


def test_missing_bundled_guard_fails_before_any_ref_creation(repo):
    commit(repo, {"a.py": "value = 1\n"})
    standalone = repo.parent / "review_snapshots.py"
    shutil.copyfile(SCRIPT, standalone)
    result = subprocess.run([sys.executable, str(standalone), "--source", "HEAD",
                             "--area", "safe|a.py", "cut", "--push"],
                            cwd=repo, text=True, capture_output=True)
    assert result.returncode != 0
    assert "repository publication guard failed" in result.stderr
    assert snapshots(repo) == snapshots(repo.parent / "remote.git") == ""
    assert not (repo.parent / "hook-calls").exists()


def test_missing_scanner_fails_closed(repo, monkeypatch):
    commit(repo, {"a.py": "value = 1\n"})
    tools = repo.parent / "limited-tools"
    tools.mkdir()
    for command in ("bash", "git", "head", "tr", "sort", "comm"):
        (tools / command).symlink_to(shutil.which(command))
    (repo.parent / "hooks/pre-push").unlink()
    monkeypatch.setenv("PATH", str(tools))
    result = run(repo, "cut", "--push", check=False)
    assert result.returncode != 0
    assert "requires all inspection tools" in result.stderr
    assert snapshots(repo) == snapshots(repo.parent / "remote.git") == ""


def test_failed_remote_probe_does_not_expose_destination_credentials(repo):
    commit(repo, {"a.py": "value = 1\n"})
    marker = "synthetic-marker-only"
    destination = f"file://test:{marker}@localhost/nonexistent-review-fixture"
    git(repo, "remote", "set-url", "--push", "origin", destination)
    result = run(repo, "cut", "--push", check=False)
    assert result.returncode != 0
    assert marker not in result.stdout + result.stderr
    assert destination not in result.stdout + result.stderr
    assert "ls-remote failed" in result.stderr
    assert snapshots(repo) == ""


@pytest.mark.parametrize("reject", [False, True])
def test_remote_push_diagnostics_do_not_expose_credentials(repo, reject):
    commit(repo, {"a.py": "value = 1\n"})
    marker = "synthetic-marker-only"
    remote = repo.parent / "remote.git"
    destination = f"file://test:{marker}@localhost{remote}"
    git(repo, "remote", "set-url", "--push", "origin", destination)
    hook = remote / "hooks/pre-receive"
    hook.write_text(f"#!/bin/sh\necho '{marker}' >&2\nexit {int(reject)}\n")
    hook.chmod(0o755)
    result = run(repo, "cut", "--push", check=False)
    assert bool(result.returncode) == reject
    assert marker not in result.stdout + result.stderr
    assert destination not in result.stdout + result.stderr
    assert bool(snapshots(remote)) != reject


@pytest.mark.parametrize("present", ["review-base", "review"])
@pytest.mark.parametrize("race", [False, True])
def test_partial_remote_pair_is_rejected_before_any_publication(repo, monkeypatch, present, race):
    commit(repo, {"a.py": "value = 1\n"})
    run(repo, "cut")
    expected = dict(line.split() for line in snapshots(repo).splitlines())
    ref = next(ref for ref in expected if ref.startswith(f"refs/heads/{present}/"))
    git(repo, "push", "origin", f"{expected[ref]}:{ref}")
    before = snapshots(repo.parent / "remote.git")
    for local_ref in expected:
        git(repo, "update-ref", "-d", local_ref)
    calls = (repo.parent / "hook-calls").read_text()
    if race:
        real_git = shutil.which("git")
        remote = str(repo.parent / "remote.git")
        ancestor = git(repo, "rev-parse", "v1.39.0")
        wrapper_dir = repo.parent / "race-bin"
        wrapper_dir.mkdir()
        wrapper = wrapper_dir / "git"
        wrapper.write_text(
            f"#!{sys.executable}\nimport os, subprocess, sys\n"
            f"real_git = {real_git!r}\n"
            f"if sys.argv[1:] == ['ls-remote', '--heads', '--', {remote!r}]:\n"
            "    result = subprocess.run([real_git, *sys.argv[1:]], capture_output=True)\n"
            f"    subprocess.run([real_git, '--git-dir', {remote!r}, "
            f"'update-ref', {ref!r}, {ancestor!r}], check=True)\n"
            "    sys.stdout.buffer.write(result.stdout)\n"
            "    sys.exit(result.returncode)\n"
            "os.execv(real_git, [real_git, *sys.argv[1:]])\n"
        )
        wrapper.chmod(0o755)
        monkeypatch.setenv("PATH", f"{wrapper_dir}{os.pathsep}{os.environ['PATH']}")
        before = f"{ref} {ancestor}"
    result = run(repo, "cut", "--push", check=False)
    assert result.returncode != 0, "partial pair was completed without an atomic check of its existing member"
    assert "partial remote snapshot pair" in result.stderr
    assert snapshots(repo) == ""
    assert snapshots(repo.parent / "remote.git") == before
    assert (repo.parent / "hook-calls").read_text() == calls


def test_retired_body_generator_fails_without_overwriting_historical_bodies(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    script = scripts / "review_slice_bodies.py"
    shutil.copyfile(ROOT / "scripts/review_slice_bodies.py", script)
    (scripts / "review_slices.sh").write_text(
        "#!/bin/sh\nprintf '01-proximity-spiderweb-lua-p001: files=2 lines=3\\n'\n"
    )
    output = tmp_path / "docs/review/SLICES.md"
    output.parent.mkdir(parents=True)
    output.write_text("historical body sizes must survive\n")
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    assert result.returncode != 0
    assert "review body generator retired:" in result.stderr
    assert output.read_text() == "historical body sizes must survive\n"


@pytest.mark.parametrize("raced", ["review-base", "review", "both"])
def test_remote_creation_race_cannot_overwrite_or_partially_publish(repo, monkeypatch, raced):
    commit(repo, {"a.py": "value = 1\n"})
    run(repo, "cut")
    before = snapshots(repo)
    refs = [line.split()[0] for line in before.splitlines()]
    ancestor = git(repo, "rev-parse", "v1.39.0")
    raced_refs = [ref for ref in refs if raced == "both" or ref.startswith(f"refs/heads/{raced}/")]
    real_git = shutil.which("git")
    wrapper_dir = repo.parent / "race-bin"
    wrapper_dir.mkdir()
    wrapper = wrapper_dir / "git"
    # Return the genuine preflight advertisement, then race before push starts.
    # All objects/ref transactions and the push itself use the actual Git CLI.
    wrapper.write_text(
        f"#!{sys.executable}\nimport os, subprocess, sys\n"
        f"real_git = {real_git!r}\n"
        f"if sys.argv[1:] == ['ls-remote', '--heads', '--', {str(repo.parent / 'remote.git')!r}]:\n"
        "    result = subprocess.run([real_git, *sys.argv[1:]], capture_output=True)\n"
        f"    for ref in {raced_refs!r}:\n"
        f"        subprocess.run([real_git, '--git-dir', {str(repo.parent / 'remote.git')!r}, "
        f"'update-ref', ref, {ancestor!r}], check=True)\n"
        "    sys.stdout.buffer.write(result.stdout)\n"
        "    sys.stderr.buffer.write(result.stderr)\n"
        "    sys.exit(result.returncode)\n"
        "os.execv(real_git, [real_git, *sys.argv[1:]])\n"
    )
    wrapper.chmod(0o755)
    monkeypatch.setenv("PATH", f"{wrapper_dir}{os.pathsep}{os.environ['PATH']}")
    result = run(repo, "cut", "--push", check=False)
    assert result.returncode != 0, "concurrent immutable ref was overwritten by a fast-forward"
    remote = dict(line.split()[::-1] for line in git(repo, "ls-remote", "origin").splitlines())
    for ref in refs:
        if ref in raced_refs:
            assert remote[ref] == ancestor
        else:
            assert ref not in remote, "atomic pair was partially published"
    assert snapshots(repo) == before


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
    assert "repository publication guard failed" in result.stderr
    assert "diagnostics withheld" in result.stderr
    assert "abcdef" * 3 not in result.stdout + result.stderr
    assert "review" not in git(repo, "ls-remote", "origin")
    assert not (repo.parent / "hook-calls").exists()
    assert snapshots(repo) == ""


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


@pytest.mark.parametrize("area", ["oops|", "oops|   ", "oops|:!a", "oops|:^a",
                                   "oops|:(exclude)a", "oops|:(top,exclude)a"])
def test_missing_positive_area_blocks_before_refs(repo, area):
    commit(repo, {"a.py": "a\n", "b.py": "b\n"})
    result = run(repo, "cut", "--push", area=area, check=False)
    assert result.returncode != 0
    assert "positive pathspec" in result.stderr
    assert snapshots(repo) == ""
    assert "review" not in git(repo, "ls-remote", "origin")
    assert not (repo.parent / "hook-calls").exists()


def test_duplicate_area_blocks_before_refs(repo):
    commit(repo, {"a.py": "a\n", "b.py": "b\n"})
    result = run(repo, "--area", "same|b.py", "cut", "--push",
                 area="same|a.py", check=False)
    assert result.returncode != 0
    assert "duplicate area name" in result.stderr
    assert snapshots(repo) == ""
    assert "review" not in git(repo, "ls-remote", "origin")
    assert not (repo.parent / "hook-calls").exists()


@pytest.mark.parametrize("area", ["empty|typo.py", "empty|a.py :!a.py"])
def test_empty_selected_area_blocks_all_refs(repo, area):
    commit(repo, {"a.py": "a\n", "secret.py": "synthetic data\n"})
    result = run(repo, "--area", area, "cut", "--push",
                 area="valid|a.py", check=False)
    assert result.returncode != 0
    assert "area selects no changes: empty" in result.stderr
    assert snapshots(repo) == ""
    assert "review" not in git(repo, "ls-remote", "origin")
    assert not (repo.parent / "hook-calls").exists()


@pytest.mark.parametrize("exclusion", ["secret.py", ":", ":!", ":(exclude)"])
def test_exclusion_argument_cannot_expand_scope(repo, exclusion):
    commit(repo, {"a.py": "a\n", "secret.py": "synthetic data\n"})
    result = run(repo, "--exclude", exclusion, "cut", "--push",
                 area="area|a.py", check=False)
    assert result.returncode != 0
    assert "exclude requires an exclusion pathspec" in result.stderr
    assert snapshots(repo) == ""
    assert "review" not in git(repo, "ls-remote", "origin")
    assert not (repo.parent / "hook-calls").exists()


@pytest.mark.parametrize("exclusion", [":!secret.py", ":^secret.py",
                                        ":(exclude)secret.py", ":(top,exclude)secret.py"])
def test_explicit_exclusion_preserves_only_selected_changes(repo, exclusion):
    commit(repo, {"a.py": "a\n", "secret.py": "synthetic data\n"})
    result = run(repo, "--exclude", exclusion, "cut", "--push")
    assert "files=1 lines=1" in result.stdout
    head = next(row.split()[1] for row in snapshots(repo).splitlines()
                if row.startswith("refs/heads/review/"))
    assert git(repo, "diff", "--name-only", f"{head}^", head) == "a.py"
    assert git(repo, "ls-remote", "origin", "refs/heads/review/*").split()[0] == head


@pytest.mark.parametrize("limit", ["files", "lines", "scope"])
def test_directory_file_collateral_blocks_before_refs(repo, limit):
    commit(repo, {"z": "old\n"})
    baseline = git(repo, "rev-parse", "HEAD")
    (repo / "z").unlink()
    files = {"z/child.py": "new\n" * (8000 if limit == "lines" else 1)}
    if limit == "files":
        files.update({f"a{n:02}.py": "a\n" for n in range(24)})
    commit(repo, files)
    result = run(repo, "--base", baseline, "cut", "--push",
                 area="area|z :!z/*" if limit == "scope" else "area|.", check=False)
    assert result.returncode != 0
    assert "actual snapshot" in result.stderr
    assert snapshots(repo) == ""
    assert "review" not in git(repo, "ls-remote", "origin")
    assert not (repo.parent / "hook-calls").exists()


@pytest.mark.parametrize("reverse", [False, True])
def test_complete_directory_file_pair_keeps_exact_scope(repo, reverse):
    original, replacement = ("z/child.py", "z") if reverse else ("z", "z/child.py")
    commit(repo, {original: "old\n"})
    baseline = git(repo, "rev-parse", "HEAD")
    (repo / original).unlink()
    if reverse:
        (repo / "z").rmdir()
    git(repo, "add", "--", original)
    commit(repo, {replacement: "new\n"})
    result = run(repo, "--base", baseline, "cut", "--push")
    assert "files=2 lines=2" in result.stdout
    head = next(row.split()[1] for row in snapshots(repo).splitlines()
                if row.startswith("refs/heads/review/"))
    assert set(git(repo, "diff", "--no-renames", "--name-only", f"{head}^", head).splitlines()) == {original, replacement}
    assert len(git(repo, "diff", "--no-renames", "--numstat", f"{head}^", head).splitlines()) == 2


def test_reverse_directory_file_exclusion_keeps_exact_selected_path(repo):
    commit(repo, {"z/child.py": "old\n"})
    baseline = git(repo, "rev-parse", "HEAD")
    (repo / "z/child.py").unlink()
    (repo / "z").rmdir()
    git(repo, "add", "--", "z/child.py")
    commit(repo, {"z": "new\n"})
    result = run(repo, "--base", baseline, "cut", "--push", area="area|z :!z/*")
    assert "files=1 lines=1" in result.stdout
    head = next(row.split()[1] for row in snapshots(repo).splitlines()
                if row.startswith("refs/heads/review/"))
    assert git(repo, "diff", "--no-renames", "--name-only", f"{head}^", head) == "z"
