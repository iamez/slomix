"""Exercise preparation without ever running PostgreSQL or systemd services."""

import json
import os
import stat
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import prepare_runtime_proof as module


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    parent, bindir = tmp_path / "proofs", tmp_path / "bin"
    parent.mkdir()
    bindir.mkdir()
    for name in ("postgres", "initdb"):
        binary = bindir / name
        binary.write_text("not an executable database; all subprocess calls are recorded")
        binary.chmod(0o700)
    original_mkdtemp = tempfile.mkdtemp

    def mkdtemp(*, prefix, dir):
        return original_mkdtemp(prefix=prefix, dir=tmp_path if str(dir) == "/tmp" else dir)

    monkeypatch.setattr(module.tempfile, "mkdtemp", mkdtemp)
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        if Path(argv[0]).name == "initdb":
            data = Path(argv[argv.index("-D") + 1])
            data.mkdir(mode=0o700)
            (data / "PG_VERSION").write_text("14\n")
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(module.subprocess, "run", run)
    return parent, bindir, calls


def test_prepare_only_creates_private_new_state_and_offline_unit(sandbox, monkeypatch):
    parent, bindir, calls = sandbox
    monkeypatch.setenv("PGDATA", "/application/database")
    monkeypatch.setenv("PGPASSWORD", "ambient-secret-not-to-be-used")
    result = module.prepare(parent, bindir)
    root, socket, unit = (Path(result[key]) for key in ("root", "socket", "unit"))
    assert result["status"] == "prepared_not_started"
    assert result["pg_major"] == "14"
    for directory in (root, socket):
        assert stat.S_IMODE(directory.stat().st_mode) == 0o700
        assert directory.stat().st_uid == os.getuid()
    assert json.loads((root / "manifest.json").read_text()) == result
    assert [Path(argv[0]).name for argv, _ in calls] == ["initdb", "systemd-analyze"]
    init, verify = calls
    assert init[0][1:] == ["-D", str(root / "data"), "--username", result["owner"],
                          "--auth-local=peer", "--auth-host=reject", "--encoding=UTF8",
                          "--locale=C", "--no-instructions", "--no-clean"]
    assert verify[0] == ["/usr/bin/systemd-analyze", "--user", "verify", str(unit)]
    for _, kwargs in calls:
        assert not any(key.startswith("PG") for key in kwargs["env"])
        assert kwargs["check"] is True
        assert kwargs["timeout"] in (30, 120)
        assert kwargs["stdin"] == subprocess.DEVNULL
    text = unit.read_text()
    for line in ("Type=exec", "Restart=no", "RuntimeMaxSec=60min", "MemoryMax=256M",
                 "KillSignal=SIGINT", "NoNewPrivileges=yes", "UMask=0077"):
        assert line in text.splitlines()
    assert "-c listen_addresses= -c port=5432" in text
    assert f"-c unix_socket_directories={socket} -c unix_socket_permissions=0700" in text
    assert f"ExecStart={bindir}/postgres -D {root}/data " in text
    assert "[Install]" not in text
    assert not (root / "data/postmaster.pid").exists()


@pytest.mark.parametrize("bad", ["relative", "/tmp/with space", "/tmp/%n", "/tmp/$x", "/tmp/a\nb"])
def test_unsafe_paths_fail_before_subprocess_or_creation(sandbox, bad):
    parent, bindir, calls = sandbox
    with pytest.raises(ValueError, match="canonical absolute"):
        module.prepare(bad, bindir)
    assert calls == []
    assert list(parent.iterdir()) == []


def test_symlink_parent_is_rejected(sandbox):
    parent, bindir, calls = sandbox
    link = parent.parent / "alias"
    link.symlink_to(parent, target_is_directory=True)
    with pytest.raises(ValueError, match="canonical absolute"):
        module.prepare(link, bindir)
    assert calls == []


def test_repository_parent_is_rejected(sandbox):
    parent, bindir, calls = sandbox
    (parent / ".git").write_text("gitdir: example")
    with pytest.raises(ValueError, match="outside a Git checkout"):
        module.prepare(parent, bindir)
    assert calls == []
    assert list(parent.iterdir()) == [parent / ".git"]


@pytest.mark.parametrize("identity", ["root", "setuid"])
def test_privileged_identity_rejected_before_writes(sandbox, monkeypatch, identity):
    parent, bindir, calls = sandbox
    if identity == "root":
        monkeypatch.setattr(module.os, "getuid", lambda: 0)
    else:
        monkeypatch.setattr(module.os, "geteuid", lambda: os.getuid() + 1)
    with pytest.raises(ValueError, match="unprivileged proof owner"):
        module.prepare(parent, bindir)
    assert calls == []
    assert list(parent.iterdir()) == []


@pytest.mark.parametrize("stage", ["initdb", "systemd-analyze"])
@pytest.mark.parametrize("failure", ["exit", "timeout"])
def test_failure_preserves_output_and_does_not_claim_ready(sandbox, monkeypatch, stage, failure):
    parent, bindir, calls = sandbox
    original = module.subprocess.run

    def fail(argv, **kwargs):
        if Path(argv[0]).name == stage:
            kwargs["stdout"].write("injected failure evidence\n")
            if failure == "exit":
                raise subprocess.CalledProcessError(9, argv)
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
        return original(argv, **kwargs)

    monkeypatch.setattr(module.subprocess, "run", fail)
    with pytest.raises(RuntimeError, match="retained files") as caught:
        module.prepare(parent, bindir)
    root, = parent.iterdir()
    assert str(root) in str(caught.value)
    assert "injected failure evidence" in (root / "prepare.log").read_text()
    assert not (root / "manifest.json").exists()
    assert len(calls) == (1 if stage == "systemd-analyze" else 0)


def test_repeat_preparation_never_overwrites_prior_proof(sandbox):
    parent, bindir, _ = sandbox
    first = module.prepare(parent, bindir)
    first_files = {path: path.read_bytes() for path in Path(first["root"]).rglob("*") if path.is_file()}
    second = module.prepare(parent, bindir)
    assert first["root"] != second["root"]
    assert first["socket"] != second["socket"]
    assert first["unit"] != second["unit"]
    assert all(path.read_bytes() == before for path, before in first_files.items())


def test_missing_explicit_prepare_is_read_only(sandbox):
    parent, bindir, calls = sandbox
    with pytest.raises(SystemExit) as exc:
        module.main(["--parent", str(parent), "--pg-bindir", str(bindir)])
    assert exc.value.code == 2
    assert calls == []
    assert list(parent.iterdir()) == []


def test_exclusive_output_creation_does_not_replace_file(tmp_path):
    path = tmp_path / "unit"
    path.write_text("original")
    with pytest.raises(FileExistsError):
        module.write_new(path, "replacement")
    assert path.read_text() == "original"


def test_foreign_parent_owner_rejected_before_writes(sandbox, monkeypatch):
    parent, bindir, calls = sandbox
    original = Path.stat

    def stat_path(path, **kwargs):
        value = original(path, **kwargs)
        if path == parent:
            return SimpleNamespace(st_mode=value.st_mode, st_uid=os.getuid() + 1)
        return value

    monkeypatch.setattr(Path, "stat", stat_path)
    with pytest.raises(ValueError, match="belong to the current user"):
        module.prepare(parent, bindir)
    assert calls == []
    assert list(parent.iterdir()) == []


@pytest.mark.parametrize("binary", ["initdb", "postgres", "systemd-analyze"])
def test_unavailable_executable_rejected_before_writes(sandbox, monkeypatch, binary):
    parent, bindir, calls = sandbox
    original = os.access
    monkeypatch.setattr(module.os, "access", lambda path, mode: Path(path).name != binary and original(path, mode))
    with pytest.raises(ValueError, match="Required executable unavailable"):
        module.prepare(parent, bindir)
    assert calls == []
    assert list(parent.iterdir()) == []
