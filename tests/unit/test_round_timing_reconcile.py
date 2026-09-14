"""Default-OFF and schema/workflow contracts for the bounded timing journal."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from shared.round_timing_reconcile import reconcile_missing_round_timing, timing_events_enabled


@pytest.mark.parametrize("base,timing,expected", [
    (None, None, False), ("false", "true", False), ("true", "false", False),
    ("true", "true", True), ("true", " TRUE ", True), ("true", "1", False),
])
def test_requires_both_flags(monkeypatch, base, timing, expected):
    for key, value in (("EVENT_STREAM_ENABLED", base), ("ROUND_TIMING_EVENTS_ENABLED", timing)):
        monkeypatch.delenv(key, raising=False)
        if value is not None:
            monkeypatch.setenv(key, value)
    assert timing_events_enabled() is expected


async def test_disabled_needs_no_adapter():
    assert await reconcile_missing_round_timing(None, enabled=False) == 0


def test_bootstrap_mirrors_timing_migration():
    root = Path(__file__).resolve().parents[2]
    migration = (root / "migrations/084_runtime_timing_events.sql").read_text().strip()
    assert migration in (root / "tools/schema_postgresql.sql").read_text()


@pytest.mark.parametrize("enabled,fails", [(False, False), (True, False), (True, True)])
async def test_bot_routes_only_enabled_path(monkeypatch, enabled, fails):
    import shared.round_timing_reconcile as module
    from bot.ultimate_bot import UltimateETLegacyBot

    adapter = SimpleNamespace(execute=AsyncMock(return_value="UPDATE 0"))
    helper = AsyncMock(return_value=2)
    if fails:
        helper.side_effect = RuntimeError("commit outcome unavailable")
    monkeypatch.setattr(module, "timing_events_enabled", lambda: enabled)
    monkeypatch.setattr(module, "reconcile_missing_round_timing", helper)
    await UltimateETLegacyBot._reconcile_missing_round_timing(SimpleNamespace(db_adapter=adapter))  # noqa: SLF001
    if enabled:
        helper.assert_awaited_once_with(adapter, enabled=True)
        adapter.execute.assert_not_awaited()  # no fallback writes after failure
    else:
        helper.assert_not_awaited()
        adapter.execute.assert_awaited_once()
