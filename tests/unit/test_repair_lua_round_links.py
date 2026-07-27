import hashlib
from types import SimpleNamespace

from scripts.repair_lua_round_links import (
    RepairAction,
    backup_manifest_problems,
    check_expectations,
    fingerprint_actions,
)


def test_action_fingerprint_is_stable_and_includes_quarantine():
    actions = [
        RepairAction(20, 2, None, 0),
        RepairAction(10, 1, 3, 1),
    ]
    assert fingerprint_actions(actions) == fingerprint_actions(list(reversed(actions)))
    assert fingerprint_actions(actions) != fingerprint_actions([
        RepairAction(10, 1, 3, 1),
    ])
    assert fingerprint_actions(actions) != fingerprint_actions([
        RepairAction(20, 2, None, 0, table="lua_spawn_stats"),
        RepairAction(10, 1, 3, 1),
    ])


def test_apply_expectations_bind_counts_fingerprint_and_database():
    stats = {
        "rebind_count": 19,
        "quarantine_count": 25,
        "current_duplicate_groups": 37,
        "projected_duplicate_groups": 0,
        "latest_date": "2026-07-18",
        "fingerprint": "abc",
        "db_identity": "localhost:5432/etlegacy",
    }
    args = SimpleNamespace(
        expect_rebind_count=19,
        expect_quarantine_count=25,
        expect_current_duplicate_groups=37,
        expect_latest_date="2026-07-18",
        expect_fingerprint="abc",
        expect_db="localhost:5432/etlegacy",
    )
    assert check_expectations(stats, args) == []

    args.expect_quarantine_count = 24
    assert check_expectations(stats, args) == [
        "--expect-quarantine-count mismatch: expected 24, measured 25"
    ]


def test_apply_refuses_a_projection_with_duplicate_links():
    stats = {
        "rebind_count": 1,
        "quarantine_count": 0,
        "current_duplicate_groups": 1,
        "projected_duplicate_groups": 1,
        "latest_date": "2026-07-18",
        "fingerprint": "abc",
        "db_identity": "localhost:5432/etlegacy",
    }
    args = SimpleNamespace(
        expect_rebind_count=1,
        expect_quarantine_count=0,
        expect_current_duplicate_groups=1,
        expect_latest_date="2026-07-18",
        expect_fingerprint="abc",
        expect_db="localhost:5432/etlegacy",
    )
    assert "repair projection retains 1 duplicate round_id group(s)" in check_expectations(
        stats, args
    )


def _write_backup_manifest(tmp_path, *, identity="localhost:5432/etlegacy"):
    dump = tmp_path / "etlegacy.sql.gz"
    dump.write_bytes(b"verified backup payload")
    manifest = tmp_path / "etlegacy.sql.gz.manifest"
    manifest.write_text(
        "\n".join([
            f"db_identity={identity}",
            f"dump_file={dump}",
            f"sha256={hashlib.sha256(dump.read_bytes()).hexdigest()}",
            "created_unix=1785177600",
        ]) + "\n",
        encoding="utf-8",
    )
    return manifest, dump


def test_backup_manifest_binds_database_and_dump_checksum(tmp_path):
    manifest, _dump = _write_backup_manifest(tmp_path)

    assert backup_manifest_problems(
        manifest, "localhost:5432/etlegacy"
    ) == []
    assert backup_manifest_problems(
        manifest, "prod.example:5432/etlegacy"
    ) == [
        "backup database mismatch: manifest localhost:5432/etlegacy, "
        "repair prod.example:5432/etlegacy"
    ]


def test_backup_manifest_rejects_a_changed_dump(tmp_path):
    manifest, dump = _write_backup_manifest(tmp_path)
    dump.write_bytes(b"changed after backup")

    assert backup_manifest_problems(
        manifest, "localhost:5432/etlegacy"
    ) == [f"backup checksum mismatch: {dump}"]
