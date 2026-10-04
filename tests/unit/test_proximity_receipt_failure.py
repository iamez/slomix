"""Receipt failure must leave the canonical import unacknowledged."""

from contextlib import asynccontextmanager
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from proximity.parser import ProximityParserV4


@pytest.mark.parametrize('missing_table', [False, True])
async def test_receipt_failure_escapes_transaction_and_rolls_back(monkeypatch, missing_table, tmp_path):
    stored = []
    rolled_back = []
    receipt_checks = []

    @asynccontextmanager
    async def transaction():
        before = list(stored)
        try:
            yield
        except Exception:
            stored[:] = before
            rolled_back.append(True)
            raise

    async def execute(query, params=None):
        if 'VALUES (?, FALSE)' in query:
            return  # Reservation precedes data; inject only at completion.
        assert 'INSERT INTO proximity_processed_files' in query
        assert stored == ['parsed-data'], 'The receipt failure must happen after a data write'
        raise RuntimeError('injected receipt failure')

    parser = ProximityParserV4(db_adapter=SimpleNamespace(transaction=transaction, execute=execute))
    source = tmp_path / '2026-10-03-120000-fixture-round-1_engagements.txt'
    source.write_text('# PROXIMITY_TRACKER_V4\n# map=fixture\n# round=1\n')
    monkeypatch.setattr(parser, '_resolve_round_link_context', AsyncMock())
    monkeypatch.setattr(parser, '_check_processed_file', AsyncMock(return_value=False))
    async def has_column(table, column):
        if column == 'filename':
            assert stored == ['parsed-data']
            receipt_checks.append(True)
        return not missing_table and column == 'filename'

    monkeypatch.setattr(parser, '_table_has_column', has_column)

    async def write_data(session_date):
        stored.append('parsed-data')

    monkeypatch.setattr(parser, '_import_engagements', write_data)
    for method in ('_update_player_stats', '_update_crossfire_pairs', '_import_heatmaps'):
        monkeypatch.setattr(parser, method, AsyncMock())
    result = await parser.import_file(str(source), date(2026, 10, 3))
    assert receipt_checks == [True], 'The test must reach the actual receipt path'
    assert result is False
    assert rolled_back == [True]
    assert stored == []
