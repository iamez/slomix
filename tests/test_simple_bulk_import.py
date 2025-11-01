import sqlite3
from pathlib import Path

from tools.simple_bulk_import import SimpleBulkImporter
from bot.community_stats_parser import C0RNP0RN3StatsParser


def _make_db_with_schema(tmp_db_path):
    """Create a sqlite DB file and load the schema from bot/schema.sql"""
    schema_path = Path('bot') / 'schema.sql'
    assert schema_path.exists(), "Schema file not found"
    schema_sql = schema_path.read_text()

    conn = sqlite3.connect(tmp_db_path)
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()


def test_importer_dry_run_on_sample(tmp_path):
    # prepare temporary DB file
    tmp_db = tmp_path / 'test_db.db'
    _make_db_with_schema(str(tmp_db))

    sample = Path('local_stats') / 'tmp_dry_run_1.txt'
    assert sample.exists(), f"Sample file not found: {sample}"

    importer = SimpleBulkImporter(
        db_path=str(tmp_db), file_patterns=[str(sample)], dry_run=True
    )
    # Should not raise
    importer.import_all()
    assert importer.failed == 0


def test_insert_player_stats_into_temp_db(tmp_path):
    tmp_db = tmp_path / 'test_db2.db'
    _make_db_with_schema(str(tmp_db))

    parser = C0RNP0RN3StatsParser()
    sample = str(Path('local_stats') / 'tmp_dry_run_1.txt')
    result = parser.parse_stats_file(sample)
    assert result.get('success')
    players = result.get('players', [])
    assert players

    conn = sqlite3.connect(str(tmp_db))
    try:
        importer = SimpleBulkImporter(db_path=str(tmp_db))
        session_timestamp = 'test-session-000'
        session_id = importer.insert_session(
            conn, session_timestamp, result, 'testfile'
        )

        # Insert first player (should not raise and should create a row)
        importer.insert_player_stats(
            conn, session_id, session_timestamp, result, players[0]
        )
        conn.commit()

        c = conn.cursor()
        c.execute(
            'SELECT COUNT(*) FROM player_comprehensive_stats '
            'WHERE session_id = ?',
            (session_id,)
        )
        cnt = c.fetchone()[0]
        assert cnt >= 1
    finally:
        conn.close()
