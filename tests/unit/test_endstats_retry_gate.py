"""All filename entry gates share the default-OFF explicit-failure contract."""

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.services.endstats_pipeline_mixin import _EndstatsPipelineMixin
from bot.services.webhook_handler_mixin import _WebhookHandlerMixin
from shared.endstats_retry import endstats_filename_gate_query


class EntryBot(_EndstatsPipelineMixin, _WebhookHandlerMixin):
    pass


@pytest.mark.parametrize("value,enabled", [(None, False), ("false", False), ("1", False), ("true", True), (" TRUE ", True)])
def test_explicit_flag(monkeypatch, value, enabled):
    monkeypatch.delenv("ENDSTATS_RETRY_ENABLED", raising=False)
    if value is not None:
        monkeypatch.setenv("ENDSTATS_RETRY_ENABLED", value)
    assert ("IS DISTINCT FROM" in endstats_filename_gate_query()) is enabled


@pytest.mark.parametrize("entry", ["polling", "webhook", "retry", "preflight"])
@pytest.mark.parametrize("enabled", [False, True])
async def test_every_entry_uses_same_gate(monkeypatch, entry, enabled):
    monkeypatch.setenv("ENDSTATS_RETRY_ENABLED", str(enabled).lower())
    bot = object.__new__(EntryBot)
    bot.config = SimpleNamespace(STARTUP_LOOKBACK_HOURS=168)
    bot.bot_startup_time = datetime(2026, 9, 15, 13)  # noqa: DTZ001 -- filename clock is local-naive
    bot.processed_endstats_files = set()
    bot.endstats_retry_counts = {}
    bot.endstats_retry_tasks = {}
    bot.endstats_retry_max_attempts = 5
    bot.db_adapter = SimpleNamespace(fetch_one=AsyncMock(return_value=(1,)))
    trigger = SimpleNamespace(delete=AsyncMock())
    if entry == "polling":
        await bot._process_endstats_file("fixture.txt", "fixture.txt")  # noqa: SLF001
    elif entry == "webhook":
        await bot._process_webhook_triggered_endstats("fixture.txt", trigger)  # noqa: SLF001
    elif entry == "retry":
        await bot._retry_webhook_endstats_link("fixture.txt", "fixture.txt", {}, trigger)  # noqa: SLF001
    else:
        bot._validate_endstats_filename = lambda name: True  # noqa: SLF001 -- reach DB gate with short fixture name
        await bot._should_process_endstats_file("fixture.txt")  # noqa: SLF001
    bot.db_adapter.fetch_one.assert_awaited_once_with(endstats_filename_gate_query(), ("fixture.txt",))


def test_template_disabled():
    root = Path(__file__).resolve().parents[2]
    assert "ENDSTATS_RETRY_ENABLED=false" in (root / ".env.example").read_text().splitlines()
