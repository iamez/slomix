"""Execute the real bounded scheduler, with injected DB failures and no I/O."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.services.endstats_pipeline_mixin import _EndstatsPipelineMixin
from shared.endstats_retry import claim_endstats_marker


@pytest.mark.parametrize("enabled,permanent,expected", [(False, False, 1), (True, False, 2), (True, True, 3)])
async def test_real_scheduler_retries_and_stops(monkeypatch, enabled, permanent, expected):
    monkeypatch.setenv("ENDSTATS_RETRY_ENABLED", str(enabled).lower())
    bot = object.__new__(_EndstatsPipelineMixin)
    bot.endstats_retry_counts = {}
    bot.endstats_retry_tasks = {}
    bot.endstats_retry_max_attempts = 3
    bot.endstats_retry_base_delay = 0
    bot.endstats_retry_max_delay = 0
    bot.processed_endstats_files = set()
    claim = claim_endstats_marker(bot, "fixture.txt")
    calls = []
    tasks = []

    async def fetch_one(*args):
        calls.append(args)
        if permanent or len(calls) == 1:
            raise RuntimeError("injected transient DB read failure")
        return (1,)  # A terminal marker stops this retry chain without publication.

    def create_task(coro, *, name=None):
        task = asyncio.create_task(coro, name=name)
        tasks.append(task)
        return task

    bot.db_adapter = SimpleNamespace(fetch_one=fetch_one)
    bot._safe_create_task = create_task  # noqa: SLF001
    trigger = SimpleNamespace(add_reaction=AsyncMock())
    try:
        await bot._schedule_endstats_retry("fixture.txt", "fixture.txt", {}, trigger, marker_claim=claim)  # noqa: SLF001
        index = 0
        while index < len(tasks):
            assert len(tasks) <= bot.endstats_retry_max_attempts
            await asyncio.wait_for(tasks[index], 2)
            index += 1
        assert len(calls) == expected
        assert len(tasks) == expected
        assert bot.endstats_retry_tasks == {}
        if enabled:
            assert bot.endstats_retry_counts == {}
        if permanent:
            trigger.add_reaction.assert_awaited_once_with('⚠️')
            assert "fixture.txt" not in bot.processed_endstats_files
        assert all(task.done() for task in tasks)
        print(f"R02c2 scheduler proof: {len(calls)} reads, {len(tasks)} completed tasks, no pending retry")
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def test_cancellation_is_not_retried(monkeypatch):
    monkeypatch.setenv("ENDSTATS_RETRY_ENABLED", "true")
    bot = object.__new__(_EndstatsPipelineMixin)
    bot.endstats_retry_counts = {}
    bot.endstats_retry_max_attempts = 3
    bot.db_adapter = SimpleNamespace(fetch_one=AsyncMock(side_effect=asyncio.CancelledError()))
    bot._schedule_endstats_retry = AsyncMock()  # noqa: SLF001
    with pytest.raises(asyncio.CancelledError):
        await bot._retry_webhook_endstats_link("fixture.txt", "fixture.txt", {}, None)  # noqa: SLF001
    bot._schedule_endstats_retry.assert_not_awaited()  # noqa: SLF001
