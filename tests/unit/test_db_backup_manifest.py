import gzip
import hashlib
import os
import subprocess
from pathlib import Path

from scripts.apply_migrations import get_target_dsn_parts


def test_db_backup_emits_a_verified_target_manifest(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_pg_dump = fake_bin / "pg_dump"
    fake_pg_dump.write_text(
        "#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$ARGS_LOG\"\n"
        "printf '%s\\n' '-- test dump'\n"
    )
    fake_pg_dump.chmod(0o755)

    backup_dir = tmp_path / "backups"
    env = os.environ.copy()
    env["BACKUP_DIR"] = str(backup_dir)
    args_log = tmp_path / "pg_dump.args"
    env["ARGS_LOG"] = str(args_log)
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    result = subprocess.run(
        ["bash", "scripts/db_backup.sh"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    manifests = list(backup_dir.glob("*.sql.gz.manifest"))
    assert len(manifests) == 1
    values = dict(
        line.split("=", 1)
        for line in manifests[0].read_text(encoding="utf-8").splitlines()
    )
    target = get_target_dsn_parts()
    assert values["db_identity"] == (
        f"{target['host']}:{target['port']}/{target['database']}"
    )

    dump = Path(values["dump_file"])
    assert gzip.decompress(dump.read_bytes()) == b"-- test dump\n"
    assert values["sha256"] == hashlib.sha256(dump.read_bytes()).hexdigest()
    assert dump.stat().st_mode & 0o077 == 0
    assert args_log.read_text(encoding="utf-8").splitlines() == [
        "--no-owner",
        "--no-privileges",
        "--clean",
        "--if-exists",
    ]


def test_db_backup_publishes_nothing_when_pg_dump_fails(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_pg_dump = fake_bin / "pg_dump"
    fake_pg_dump.write_text(
        "#!/bin/sh\nprintf '%s\\n' 'partial dump'\nprintf '%s\\n' 'dump failed' >&2\nexit 9\n"
    )
    fake_pg_dump.chmod(0o755)

    backup_dir = tmp_path / "backups"
    env = os.environ.copy()
    env["BACKUP_DIR"] = str(backup_dir)
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    result = subprocess.run(
        ["bash", "scripts/db_backup.sh"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 1
    assert "pg_dump failed with exit code 9: dump failed" in result.stderr
    assert list(backup_dir.iterdir()) == []
