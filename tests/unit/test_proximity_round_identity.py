"""Source start identity must not be replaced by nearest end-to-start matching."""
# ruff: noqa: SLF001 -- exercise the canonical parser's internal linkage boundary

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from proximity.parser import ProximityParserV4, round_identity

START = 1789794600
END = START + 600


async def test_exact_source_start_beats_next_round_near_end():
    async def fetch_all(query, params):
        if 'round_start_unix = ?' in query:
            assert params == ('fixture', 1, START)
            return [(101,)]
        return [(102, '2026-09-19', '052100', None, END + 60),
                (101, '2026-09-19', '051000', None, START)]
    adapter = SimpleNamespace(fetch_all=fetch_all, fetch_one=AsyncMock(return_value=None))
    parser = ProximityParserV4(db_adapter=adapter)
    parser.metadata.update(map_name='fixture', round_num=1, round_start_unix=START, round_end_unix=END)
    await parser._resolve_round_link_context(date(2026, 9, 19))
    assert parser._round_link_context['round_id'] == 101


async def test_duplicate_start_identity_is_not_guessed():
    async def fetch_all(query, params):
        if 'round_start_unix = ?' in query:
            return [(101,), (102,)]
        return [(102, '2026-09-19', '051000', None, START),
                (101, '2026-09-19', '051000', None, START)]
    adapter = SimpleNamespace(fetch_all=fetch_all, fetch_one=AsyncMock(return_value=None))
    parser = ProximityParserV4(db_adapter=adapter)
    parser.metadata.update(map_name='fixture', round_num=1, round_start_unix=START, round_end_unix=END)
    await parser._resolve_round_link_context(date(2026, 9, 19))
    assert parser._round_link_context['round_id'] is None
    assert parser._round_link_context['round_link_reason'] == 'ambiguous_source_start'


@pytest.mark.parametrize('start', [0, -1, None, True, 1, 999999999999])
async def test_missing_implausible_start_preserves_fallback(start, monkeypatch):
    fallback = AsyncMock(return_value=(44, {'reason_code': 'resolved'}))
    monkeypatch.setattr(round_identity, 'resolve_round_id_with_reason', fallback)
    adapter = SimpleNamespace(fetch_all=AsyncMock())
    options = {'round_date': '2026-09-19', 'window_minutes': 45, 'target_dt': None}
    assert await round_identity.resolve_proximity_round_id(
        adapter, 'fixture', 1, source_start_unix=start, **options,
    ) == (44, {'reason_code': 'resolved'})
    adapter.fetch_all.assert_not_awaited()
    fallback.assert_awaited_once_with(adapter, 'fixture', 1, **options)


async def test_no_exact_start_keeps_original_end_target(monkeypatch):
    fallback = AsyncMock(return_value=(55, {}))
    monkeypatch.setattr(round_identity, 'resolve_round_id_with_reason', fallback)
    adapter = SimpleNamespace(fetch_all=AsyncMock(return_value=[]))
    target = object()
    assert await round_identity.resolve_proximity_round_id(
        adapter, 'fixture', 1, source_start_unix=START, target_dt=target,
    ) == (55, {})
    fallback.assert_awaited_once_with(adapter, 'fixture', 1, target_dt=target)


async def test_identity_lookup_error_never_falls_back(monkeypatch):
    fallback = AsyncMock()
    monkeypatch.setattr(round_identity, 'resolve_round_id_with_reason', fallback)
    adapter = SimpleNamespace(fetch_all=AsyncMock(side_effect=RuntimeError('identity unavailable')))
    with pytest.raises(RuntimeError, match='identity unavailable'):
        await round_identity.resolve_proximity_round_id(adapter, 'fixture', 1, source_start_unix=START)
    fallback.assert_not_awaited()


async def test_filename_fallback_is_not_promoted_to_source_identity(monkeypatch, tmp_path):
    resolver = AsyncMock(return_value=(55, {}))
    monkeypatch.setattr(round_identity, 'resolve_proximity_round_id', resolver)
    parser = ProximityParserV4(db_adapter=object(), gametimes_dir=str(tmp_path))
    path = str(tmp_path / '2026-09-19-051000-fixture-round-1_engagements.txt')
    payload = f'# map=fixture\n# round=1\n# round_end_unix={END}\n'.encode()
    assert parser.parse_file(path, source_bytes=payload)
    assert parser.metadata['round_start_unix'] > 0
    await parser._resolve_round_link_context(date(2026, 9, 19))
    assert resolver.call_args.kwargs['source_start_unix'] == 0
    assert int(resolver.call_args.kwargs['target_dt'].timestamp()) == END
    # Reusing the canonical parser for a later real header resets provenance.
    assert parser.parse_file(path, source_bytes=payload + f'# round_start_unix={START}\n'.encode())
    await parser._resolve_round_link_context(date(2026, 9, 19))
    assert resolver.call_args.kwargs['source_start_unix'] == START
