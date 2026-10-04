"""Unknown import receipt state must never authorize aggregate writes."""

import asyncio
from contextlib import asynccontextmanager
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from proximity.parser import ProximityParserV4


@pytest.mark.parametrize('row,expected', [(None, False), ((False,), False), ((True,), True)])
async def test_receipt_read_uses_required_table_directly(row, expected):
    fetch = AsyncMock(return_value=row)
    parser = ProximityParserV4(db_adapter=SimpleNamespace(fetch_one=fetch))
    assert await parser._check_processed_file('sealed.txt') is expected  # noqa: SLF001 - receipt contract
    fetch.assert_awaited_once_with(
        'SELECT aggregates_applied FROM proximity_processed_files WHERE filename = $1',
        ('sealed.txt',),
    )


@pytest.mark.parametrize('error', [RuntimeError('missing receipt table'), ConnectionError('receipt unavailable')])
async def test_receipt_query_error_is_not_a_negative_receipt(error):
    parser = ProximityParserV4(db_adapter=SimpleNamespace(fetch_one=AsyncMock(side_effect=error)))
    with pytest.raises(type(error), match=str(error)):
        await parser._check_processed_file('sealed.txt')  # noqa: SLF001 - receipt contract


@pytest.mark.parametrize('transactional', [True, False])
@pytest.mark.parametrize('cancelled', [True, False])
async def test_failed_receipt_read_prevents_all_import_writes(monkeypatch, tmp_path, transactional, cancelled):
    active = False
    reads = []
    rollbacks = []

    @asynccontextmanager
    async def transaction():
        nonlocal active
        active = True
        try:
            yield
        except BaseException:
            rollbacks.append(True)
            raise
        finally:
            active = False

    async def fetch_one(query, params):
        assert query.startswith('SELECT aggregates_applied')
        reads.append((active, params))
        if cancelled:
            raise asyncio.CancelledError()
        raise ConnectionError('injected receipt read outage')

    claim = AsyncMock()
    adapter = SimpleNamespace(fetch_one=fetch_one, execute=claim)
    if transactional:
        adapter.transaction = transaction
    parser = ProximityParserV4(db_adapter=adapter)
    source = tmp_path / '2026-10-04-120000-fixture-round-1_engagements.txt'
    source.write_text('# PROXIMITY_TRACKER_V4\n# map=fixture\n# round=1\n')
    monkeypatch.setattr(parser, '_resolve_round_link_context', AsyncMock())
    writes = []
    for method in ('_import_engagements', '_update_player_stats', '_update_crossfire_pairs',
                   '_import_heatmaps', '_mark_file_processed'):
        call = AsyncMock()
        monkeypatch.setattr(parser, method, call)
        writes.append(call)
    if cancelled and transactional:
        with pytest.raises(asyncio.CancelledError):
            await parser.import_file(str(source), date(2026, 10, 4))
    else:
        assert await parser.import_file(str(source), date(2026, 10, 4)) is False
    assert reads == ([(True, (source.name,))] if transactional else [])
    assert rollbacks == ([True] if transactional else [])
    assert claim.await_count == int(transactional)
    for write in writes:
        write.assert_not_awaited()
