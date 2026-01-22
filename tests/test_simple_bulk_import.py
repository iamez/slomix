import glob
import sqlite3
from pathlib import Path

import pytest

from tools.simple_bulk_import import SimpleBulkImporter
from bot.community_stats_parser import C0RNP0RN3StatsParser


def _get_sample_file():
    """Get a real sample stats file from local_stats/"""
    # Try specific known file first
    preferred = Path('local_stats') / '2024-11-26-215746-supply-round-1.txt'
    if preferred.exists():
        return preferred

    # Fall back to any .txt file with actual data (>500 bytes)
    files = glob.glob('local_stats/*.txt')
    files = [Path(f) for f in files if not f.endswith('_ws.txt') and Path(f).stat().st_size > 500]
    if files:
        return files[0]

    return None


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

    sample = _get_sample_file()
    if sample is None:
        pytest.skip("No sample stats files available in local_stats/")

    importer = SimpleBulkImporter(
        db_path=str(tmp_db), file_patterns=[str(sample)], dry_run=True
    )
    # Should not raise
    importer.import_all()
    assert importer.failed == 0


def test_insert_player_stats_into_temp_db(tmp_path):
    tmp_db = tmp_path / 'test_db2.db'
    _make_db_with_schema(str(tmp_db))

    sample = _get_sample_file()
    if sample is None:
        pytest.skip("No sample stats files available in local_stats/")

    parser = C0RNP0RN3StatsParser()
    result = parser.parse_stats_file(str(sample))
    assert result.get('success'), f"Parser failed: {result.get('error')}"
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
