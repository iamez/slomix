from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from bot.automation.file_tracker import FileTracker
from bot.community_stats_parser import C0RNP0RN3StatsParser
from bot.services.endstats_aggregator import EndstatsAggregator


class _RecordingDb:
    def __init__(self, rows=None, execute_error: Exception | None = None):
        self.rows = rows or []
        self.execute_error = execute_error
        self.fetch_all_calls = []
        self.execute_calls = []

    async def fetch_all(self, query, params=None):
        self.fetch_all_calls.append((query, params))
        return self.rows

    async def fetch_one(self, query, params=None):
        return None

    async def execute(self, query, params=None):
        self.execute_calls.append((query, params))
        if self.execute_error is not None:
            raise self.execute_error


@pytest.mark.asyncio
async def test_easiest_preys_groups_by_stable_identity():
    db = _RecordingDb(rows=[("RenamedEnemy", 9, 2)])
    aggregator = EndstatsAggregator(db)

    result = await aggregator.get_easiest_preys([11, 12], "subject-guid", limit=2)

    assert result == [("RenamedEnemy", 9, 2)]
    query, params = db.fetch_all_calls[0]
    assert "GROUP BY COALESCE(player_guid, player_name)" in query
    assert "GROUP BY player_name" not in query
    assert params == ("subject-guid", 11, 12)


@pytest.mark.asyncio
async def test_worst_enemies_groups_by_stable_identity():
    db = _RecordingDb(rows=[("Enemy", 3, 7)])
    aggregator = EndstatsAggregator(db)

    result = await aggregator.get_worst_enemies([21], "subject-guid", limit=1)

    assert result == [("Enemy", 3, 7)]
    query, params = db.fetch_all_calls[0]
    assert "GROUP BY COALESCE(player_guid, player_name)" in query
    assert "ORDER BY total_deaths DESC" in query
    assert params == ("subject-guid", 21)


@pytest.mark.asyncio
async def test_mark_processed_returns_false_and_logs_error_on_persistence_failure(caplog):
    tracker = FileTracker(
        db_adapter=_RecordingDb(execute_error=RuntimeError("disk full")),
        config=SimpleNamespace(STARTUP_LOOKBACK_HOURS=168),
        bot_startup_time=datetime(2026, 3, 8, 12, 0, 0),
        processed_files=set(),
    )

    with caplog.at_level("ERROR"):
        stored = await tracker.mark_processed("2026-03-08-120000-supply-round-1.txt")

    assert stored is False
    assert "restart-time dedupe may drift" in caplog.text


def test_parse_time_to_seconds_does_not_swallow_keyboard_interrupt():
    parser = C0RNP0RN3StatsParser()

    class _InterruptingTime:
        def __str__(self):
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        parser.parse_time_to_seconds(_InterruptingTime())


def test_determine_round_outcome_does_not_swallow_keyboard_interrupt(monkeypatch):
    parser = C0RNP0RN3StatsParser()

    def raise_interrupt(_value):
        raise KeyboardInterrupt

    monkeypatch.setattr(parser, "parse_time_to_seconds", raise_interrupt)

    with pytest.raises(KeyboardInterrupt):
        parser.determine_round_outcome("20:00", "18:30", 1)
