from types import SimpleNamespace

from scripts.repair_lua_round_links import (
    RepairAction,
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
