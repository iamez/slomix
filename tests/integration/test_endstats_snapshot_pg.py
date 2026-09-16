"""Persisted row comparison on the explicitly isolated PostgreSQL fixture."""

import pytest

from shared.endstats_snapshot import capture_endstats_snapshot
from tests.integration.test_runtime_events_pg import journal_db  # noqa: F401


@pytest.fixture
async def snapshot_db(journal_db):  # noqa: F811
    writer, reader = journal_db
    await writer.execute("""
        CREATE TABLE round_awards (
            id SERIAL, round_id INTEGER, round_date TEXT, map_name TEXT,
            round_number INTEGER, award_name TEXT, player_name TEXT,
            player_guid TEXT, award_value TEXT, award_value_numeric REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE round_vs_stats (
            id SERIAL, round_id INTEGER, round_date TEXT, map_name TEXT,
            round_number INTEGER, player_name TEXT, player_guid TEXT,
            kills INTEGER, deaths INTEGER, subject_name TEXT, subject_guid TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO round_awards(round_id, award_name, award_value_numeric)
            VALUES (1, 'fixture', 'NaN'), (1, 'other', 1), (2, 'excluded', 99);
        INSERT INTO round_vs_stats(round_id, player_name, kills, deaths)
            VALUES (1, 'fixture', 2, 3);
    """)
    return writer, reader


async def test_snapshot_requires_transaction(snapshot_db):
    writer, _ = snapshot_db
    with pytest.raises(RuntimeError, match="storage transaction"):
        await capture_endstats_snapshot(writer, 1)


async def test_reordered_reinsert_with_new_ids_and_clocks_is_identical(snapshot_db):
    writer, reader = snapshot_db
    async with writer.transaction():
        before = await capture_endstats_snapshot(writer, 1)
        await writer.execute("""
            DELETE FROM round_awards WHERE round_id = 1;
            INSERT INTO round_awards(round_id, award_name, award_value_numeric, created_at)
                VALUES (1, 'other', 1, '2000-01-01'), (1, 'fixture', 'NaN', '2000-01-01');
            UPDATE round_vs_stats SET id = id + 100, created_at = '2000-01-01';
        """)
        assert before == await capture_endstats_snapshot(writer, 1)
    assert await reader.fetchval("SELECT count(*) FROM round_awards WHERE round_id=1") == 2
    assert len(await reader.fetch("SELECT * FROM round_awards WHERE round_id=1")) == 2
    print("snapshot runtime: reordered persisted rows and new IDs/clocks compare equal, NaN stable")


@pytest.mark.parametrize("statement", [
    "UPDATE round_awards SET award_value_numeric=2 WHERE award_name='other'",
    "UPDATE round_awards SET player_guid='changed' WHERE award_name='other'",
    "UPDATE round_awards SET award_value='changed' WHERE award_name='other'",
    "UPDATE round_vs_stats SET subject_guid='changed' WHERE round_id=1",
    "UPDATE round_vs_stats SET deaths=4 WHERE round_id=1",
    "INSERT INTO round_vs_stats(round_id,player_name,kills,deaths) VALUES(1,'fixture',2,3)",
])
async def test_real_content_and_duplicate_multiplicity_change_snapshot(snapshot_db, statement):
    writer, _ = snapshot_db
    async with writer.transaction():
        before = await capture_endstats_snapshot(writer, 1)
        await writer.execute(statement)
        assert before != await capture_endstats_snapshot(writer, 1)


async def test_other_round_changes_are_excluded(snapshot_db):
    writer, _ = snapshot_db
    async with writer.transaction():
        before = await capture_endstats_snapshot(writer, 1)
        await writer.execute("UPDATE round_awards SET award_name='changed' WHERE round_id=2")
        assert before == await capture_endstats_snapshot(writer, 1)
