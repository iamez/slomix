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


# ── Which database, and as whom, are two different questions ────────────────


def _root_env(tmp_path, **values):
    (tmp_path / ".env").write_text(
        "\n".join(f"{k}={v}" for k, v in values.items()) + "\n", encoding="utf-8")
    return tmp_path


def test_the_dump_role_prefers_an_explicit_override(tmp_path):
    from scripts.db_backup import resolve_dump_role

    conn = {"user": "website_app", "password": "svc"}
    _root_env(tmp_path, POSTGRES_USER="etlegacy_user", POSTGRES_PASSWORD="owner")
    user, password, source = resolve_dump_role(
        conn, tmp_path, {"BACKUP_DB_USER": "postgres", "BACKUP_DB_PASSWORD": "su"})
    assert (user, password) == ("postgres", "su")
    assert source == "BACKUP_DB_USER"


def test_an_override_without_a_password_keeps_the_resolved_one(tmp_path):
    from scripts.db_backup import resolve_dump_role

    user, password, _ = resolve_dump_role(
        {"user": "website_app", "password": "svc"}, tmp_path, {"BACKUP_DB_USER": "postgres"})
    assert (user, password) == ("postgres", "svc")


def test_the_root_env_wins_over_the_service_role(tmp_path):
    """The failure this exists for: website/.env shadows the root .env, so the
    dump ran as website_app -- which cannot read seven of the 103 tables, and
    pg_dump died on the first one."""
    from scripts.db_backup import resolve_dump_role

    _root_env(tmp_path, POSTGRES_USER="etlegacy_user", POSTGRES_PASSWORD="owner")
    user, password, source = resolve_dump_role(
        {"user": "website_app", "password": "svc"}, tmp_path, {})
    assert (user, password) == ("etlegacy_user", "owner")
    assert ".env" in source


def test_a_root_env_that_agrees_changes_nothing(tmp_path):
    from scripts.db_backup import resolve_dump_role

    _root_env(tmp_path, POSTGRES_USER="etlegacy_user", POSTGRES_PASSWORD="owner")
    user, password, source = resolve_dump_role(
        {"user": "etlegacy_user", "password": "owner"}, tmp_path, {})
    assert (user, password, source) == ("etlegacy_user", "owner", "resolved connection")


def test_without_a_root_env_the_old_behaviour_stands(tmp_path):
    """Anyone whose setup has neither an override nor a root .env must keep
    getting exactly what they got before."""
    from scripts.db_backup import resolve_dump_role

    user, password, source = resolve_dump_role(
        {"user": "someone", "password": "pw"}, tmp_path, {})
    assert (user, password, source) == ("someone", "pw", "resolved connection")


def test_resolving_the_role_never_touches_the_process_environment(tmp_path):
    """dotenv_values, not load_dotenv: reading the root .env here must not
    change what a later tool in the same process resolves."""
    from scripts.db_backup import resolve_dump_role

    _root_env(tmp_path, POSTGRES_USER="etlegacy_user", POSTGRES_PASSWORD="owner",
              SOME_UNRELATED_KEY="leaked")
    before = dict(os.environ)
    resolve_dump_role({"user": "website_app", "password": "svc"}, tmp_path, {})
    assert dict(os.environ) == before
    assert "SOME_UNRELATED_KEY" not in os.environ


def test_the_role_is_not_part_of_the_backup_identity():
    """The manifest binds a dump to host:port/database. Adding the role would
    refuse a perfectly good backup taken by a different admin account."""
    import inspect

    from scripts.db_backup import create_backup

    src = inspect.getsource(create_backup)
    assert 'db_identity = f"{host}:{port}/{database}"' in src
    assert "role" not in src.split("db_identity =")[1].split("\n")[0]
