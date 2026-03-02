from __future__ import annotations

import pytest

from bot.services.round_correlation_service import RoundCorrelationService


class _FakeCorrelationDb:
    def __init__(self, *, schema_columns: list[str] | None = None, fail_execute: bool = False):
        self.schema_columns = schema_columns if schema_columns is not None else []
        self.fail_execute = fail_execute
        self.executed = []
        self.fetch_all_calls = []
        self.fetch_one_calls = []

    async def fetch_all(self, query, params=None):
        query_text = str(query)
        self.fetch_all_calls.append((query_text, params))
        if "information_schema.columns" in query_text and "round_correlations" in query_text:
            return [(col,) for col in self.schema_columns]
        if "GROUP BY status" in query_text:
            return []
        if "ORDER BY created_at DESC" in query_text:
            return []
        return []

    async def fetch_one(self, query, params=None):
        query_text = str(query)
        self.fetch_one_calls.append((query_text, params))
        if "FROM round_correlations" in query_text and "WHERE correlation_id = $1" in query_text:
            # has_r1_stats only (partial)
            return (True, False, False, False, False, False, False, False)
        return None

    async def execute(self, query, params=None, *extra):
        query_text = str(query)
        if extra:
            if params is None:
                params = extra
            elif isinstance(params, tuple):
                params = params + tuple(extra)
        self.executed.append((query_text, params))
        if self.fail_execute:
            raise RuntimeError("simulated execute failure")


@pytest.mark.asyncio
async def test_correlation_live_mode_enabled_after_schema_preflight():
    db = _FakeCorrelationDb(
        schema_columns=sorted(RoundCorrelationService.REQUIRED_COLUMNS),
        fail_execute=False,
    )
    svc = RoundCorrelationService(
        db,
        dry_run=False,
        require_schema_check=True,
        write_error_threshold=3,
    )

    await svc.initialize()

    assert svc.dry_run is False
    assert svc.preflight_checked is True
    assert svc.preflight_ok is True
    assert svc.guardrail_reason is None

    summary = await svc.get_status_summary()
    assert summary["dry_run"] is False
    assert summary["live_requested"] is True
    assert summary["preflight_ok"] is True


@pytest.mark.asyncio
async def test_correlation_preflight_failure_forces_dry_run():
    db = _FakeCorrelationDb(schema_columns=[], fail_execute=False)
    svc = RoundCorrelationService(
        db,
        dry_run=False,
        require_schema_check=True,
        write_error_threshold=3,
    )

    await svc.initialize()

    assert svc.dry_run is True
    assert svc.preflight_checked is True
    assert svc.preflight_ok is False
    assert svc.guardrail_reason is not None
    assert svc.guardrail_reason.startswith("schema_preflight_")


@pytest.mark.asyncio
async def test_correlation_auto_disables_live_mode_after_write_errors():
    db = _FakeCorrelationDb(
        schema_columns=sorted(RoundCorrelationService.REQUIRED_COLUMNS),
        fail_execute=True,
    )
    svc = RoundCorrelationService(
        db,
        dry_run=False,
        require_schema_check=True,
        write_error_threshold=2,
    )
    await svc.initialize()
    assert svc.dry_run is False

    await svc.on_round_imported(
        match_id="2026-02-26-215959",
        round_number=1,
        round_id=9001,
        map_name="supply",
    )
    assert svc.dry_run is False
    assert svc.write_error_count == 1

    await svc.on_round_imported(
        match_id="2026-02-26-215959",
        round_number=2,
        round_id=9002,
        map_name="supply",
    )
    assert svc.dry_run is True
    assert svc.write_error_count == 2
    assert svc.guardrail_reason is not None
    assert svc.guardrail_reason.startswith("write_error_threshold_reached:")

    executed_before = len(db.executed)
    await svc.on_round_imported(
        match_id="2026-02-26-220101",
        round_number=1,
        round_id=9003,
        map_name="supply",
    )
    assert len(db.executed) == executed_before
