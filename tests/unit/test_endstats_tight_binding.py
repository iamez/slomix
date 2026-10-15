"""Late stats import must not redirect endstats to a previous map play."""
# ruff: noqa: SLF001 -- exercise private mixin boundaries directly
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.services.endstats_pipeline_mixin import _EndstatsPipelineMixin as M


@pytest.mark.asyncio
@pytest.mark.parametrize('rows,expected', [([], None), ([(10, '220809')], None),
    ([(10, '220809'), (20, '221505')], 20), ([(20, '221505'), (21, '221506')], None),
    ([(20, '221534')], 20), ([(20, '221535')], None)])
async def test_only_unique_tight_candidate_is_eligible(rows, expected):
    bot = M()
    bot.db_adapter = SimpleNamespace(fetch_all=AsyncMock(return_value=[(rid, '2026-10-12', time) for rid, time in rows]))
    bot._resolve_round_id_for_metadata = AsyncMock(return_value=10)
    result, _ = await bot._resolve_endstats_round_id('2026-10-12', '221504', 'fixture', 1, 'unused', {})
    assert result == expected
    bot._resolve_round_id_for_metadata.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('enabled', [False, True])
@pytest.mark.parametrize('half', [1, 2])
async def test_pending_poll_survives_budget_then_binds_new_stats(monkeypatch, enabled, half):
    monkeypatch.setenv('ENDSTATS_RETRY_ENABLED', str(enabled).lower())
    time = '221504' if half == 1 else '221816'
    old_time = '220809' if half == 1 else '221124'
    old_id, new_id = (11770, 11773) if half == 1 else (11771, 11774)
    filename = f'2026-10-12-{time}-fixture-round-{half}-endstats.txt'
    data = {'metadata': {'date': '2026-10-12', 'time': time, 'map_name': 'fixture', 'round_number': half},
            'awards': [], 'vs_stats': []}
    monkeypatch.setattr('bot.endstats_parser.parse_endstats_file', lambda path: data)
    bot = M()
    bot.processed_endstats_files = set()
    bot.endstats_retry_counts = {}
    bot.endstats_retry_max_attempts = 2
    bot.db_adapter = SimpleNamespace(fetch_one=AsyncMock(return_value=None),
        fetch_all=AsyncMock(return_value=[(old_id, '2026-10-12', old_time)]), execute=AsyncMock())
    bot._resolve_round_id_for_metadata = AsyncMock(return_value=10)
    bot._select_richest_endstats = lambda d, p, f, *args: (d, p, f)
    bot._is_endstats_round_already_processed = AsyncMock(return_value=False)
    bot._is_endstats_round_ready = AsyncMock(return_value=True)
    bot._store_endstats_and_publish = AsyncMock(return_value=True)
    bot.track_error = AsyncMock()
    for _ in range(5):
        await bot._process_endstats_file('fixture', filename)
        assert filename not in bot.processed_endstats_files
    assert bot.endstats_retry_counts[filename] == 3
    bot.db_adapter.execute.assert_not_awaited()
    bot._is_endstats_round_already_processed.assert_not_awaited()
    bot._store_endstats_and_publish.assert_not_awaited()
    bot.db_adapter.fetch_all.return_value = [(old_id, '2026-10-12', old_time), (new_id, '2026-10-12', time)]
    await bot._process_endstats_file('fixture', filename)
    assert bot._store_endstats_and_publish.await_args.args[2] == new_id
    bot.track_error.assert_not_awaited()


@pytest.mark.asyncio
async def test_webhook_retry_keeps_missing_tight_round_pending():
    bot = M()
    bot.endstats_retry_counts = {}
    bot.endstats_retry_max_attempts = 2
    bot.db_adapter = SimpleNamespace(fetch_one=AsyncMock(return_value=None),
                                    fetch_all=AsyncMock(return_value=[(11770, '2026-10-12', '220809')]))
    bot._resolve_round_id_for_metadata = AsyncMock(return_value=11770)
    bot._schedule_endstats_retry = AsyncMock()
    bot._is_endstats_round_already_processed = AsyncMock()
    bot._store_endstats_and_publish = AsyncMock()
    data = {'metadata': {'date': '2026-10-12', 'time': '221504',
                         'map_name': 'fixture', 'round_number': 1}}
    await bot._retry_webhook_endstats_link('fixture', 'path', data, None)
    bot._schedule_endstats_retry.assert_awaited_once_with('fixture', 'path', data, None)
    bot._is_endstats_round_already_processed.assert_not_awaited()
    bot._store_endstats_and_publish.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('target_date,target_time,rows,expected,dates', [
    ('2026-10-13', '000001', [(20, '2026-10-12', '235959')], 20, ('2026-10-12', '2026-10-13')),
    ('2026-10-12', '235959', [(20, '2026-10-13', '000001')], 20, ('2026-10-12', '2026-10-13')),
    ('2026-10-13', '000010', [(20, '2026-10-12', '235950')], 20, ('2026-10-12', '2026-10-13')),
    ('2026-10-12', '235950', [(20, '2026-10-13', '000010')], 20, ('2026-10-12', '2026-10-13')),
    ('2026-10-13', '000010', [(20, '2026-10-12', '235950'), (21, '2026-10-13', '000011')], None, ('2026-10-12', '2026-10-13')),
    ('2026-10-13', '000010', [(20, '2026-10-12', '235940')], 20, ('2026-10-12', '2026-10-13')),
    ('2026-10-13', '000010', [(20, '2026-10-12', '235939')], None, ('2026-10-12', '2026-10-13')),
    ('2026-10-12', '235950', [(20, '2026-10-13', '000020')], 20, ('2026-10-12', '2026-10-13')),
    ('2026-10-12', '235950', [(20, '2026-10-13', '000021')], None, ('2026-10-12', '2026-10-13')),
    ('2026-10-13', '000010', [(10, '2026-10-12', '235000'), (20, '2026-10-13', '000011')], 20, ('2026-10-12', '2026-10-13')),
    ('2026-10-13', '120000', [(20, '2026-10-12', '120000')], None, ('2026-10-13', '2026-10-13')),
])
async def test_absolute_tight_window_across_dates(target_date, target_time, rows, expected, dates):
    bot = M()
    calls = []

    async def query(sql, params):
        calls.append((sql, params))
        assert 'round_date BETWEEN ? AND ?' in sql
        assert params == (*dates, 'fixture', 1)
        # Emulate the SQL date filter as well as testing absolute-time matching.
        return [row for row in rows if params[0] <= row[1] <= params[1]]

    bot.db_adapter = SimpleNamespace(fetch_all=query)
    bot._resolve_round_id_for_metadata = AsyncMock(return_value=10)
    rid, reason = await bot._resolve_endstats_round_id(target_date, target_time, 'fixture', 1, 'unused', {})
    assert rid == expected and len(calls) == 1
    if len(rows) == 2 and expected is None:
        assert reason == 'ambiguous_narrow_time_match'
    bot._resolve_round_id_for_metadata.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('date,time', [('2026-02-30', '120000'), ('2026-10-13', '240000'),
                                      ('2026-10-13', '000060'), ('2026-10-13', '12345')])
async def test_invalid_full_timestamp_never_queries_or_falls_back(date, time):
    bot = M()
    bot.db_adapter = SimpleNamespace(fetch_all=AsyncMock())
    result = await bot._resolve_endstats_round_id(date, time, 'fixture', 1, 'unused', {})
    assert result == (None, 'invalid_endstats_time')
    bot.db_adapter.fetch_all.assert_not_awaited()
