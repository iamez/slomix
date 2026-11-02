"""R1 event clocks must not inherit wide R2/import-recovery windows."""
# ruff: noqa: SLF001 -- exercise private selection while intercepting all writes.

from unittest.mock import AsyncMock

import pytest

from bot.services.round_correlation_service import RoundCorrelationService


def _service(rows):
    db = AsyncMock()
    db.fetch_all.return_value = rows
    db.fetch_one.return_value = None
    service = RoundCorrelationService(db, dry_run=False, require_schema_check=False)
    service._initialized = True
    service._upsert_correlation = AsyncMock()
    return service


@pytest.mark.asyncio
@pytest.mark.parametrize('window', [600, 1800])
@pytest.mark.parametrize('stamp,expected', [
    ('212618', 'earlier'),  # Ordinary delayed import: event clock remains 3s apart.
    ('212645', 'earlier'),  # Existing 30s inclusive boundary.
    ('212646', None),
    ('212743', None),      # Actual reset:88s after the earlier R1 stats clock.
])
async def test_wide_caller_window_cannot_expand_r1_timestamp_match(window, stamp, expected):
    service = _service([('earlier', '2026-10-26-212615', 11866)])
    result = await service._find_nearby_correlation_id(
        f'2026-10-26-{stamp}', 'supply', 1, window_seconds=window,
    )
    assert result == expected


@pytest.mark.asyncio
async def test_reset_proximity_and_retry_keep_own_correlation():
    service = _service([('2026-10-26-212615:supply', '2026-10-26-212615', 11866)])
    for _ in range(2):
        await service.on_proximity_imported('2026-10-26-212743', 1, 'supply')
    assert service._upsert_correlation.await_count == 2
    for call in service._upsert_correlation.await_args_list:
        assert call.kwargs['correlation_id'] == '2026-10-26-212743:supply'
        assert call.kwargs['match_id'] == '2026-10-26-212743'
        assert call.kwargs['updates'] == {'has_r1_proximity': True}


@pytest.mark.asyncio
async def test_exact_r1_identity_reuses_its_own_key():
    service = _service([('2026-10-26-212743:supply', '2026-10-26-212743', None)])
    await service.on_proximity_imported('2026-10-26-212743', 1, 'supply')
    assert service._upsert_correlation.await_args.kwargs['correlation_id'] == '2026-10-26-212743:supply'


@pytest.mark.asyncio
async def test_r2_retains_wide_legacy_timestamp_match():
    service = _service([('earlier', '2026-10-26-212615', 11866)])
    result = await service._find_nearby_correlation_id(
        '2026-10-26-213115', 'supply', 2, window_seconds=600,
    )
    assert result == 'earlier'
