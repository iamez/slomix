"""Regression test: STATS_READY webhook calls fetch BEFORE Lua store.

Pins the 2026-04-21 race-condition fix in bot/services/stats_ready_mixin.py.

Before the fix, `_handle_stats_ready_webhook` called
`_store_lua_round_teams` first — which internally ran
`_resolve_round_id_for_metadata`. The `rounds` row did not yet exist
(it's created as a side effect of parsing the stats file), so resolve
always failed and emitted a noisy WARN pair on every live match. The
relinker cron eventually picked up the orphaned Lua row, which was
correct but generated 2 WARNs per round during live play.

After the fix, stats fetch runs first → rounds row exists → resolve in
the subsequent Lua store succeeds. No spurious WARN.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


@pytest.mark.asyncio
async def test_worker_round_reraises_on_failure():
    """The worker handler must propagate exceptions so
    `WebhookEventQueue._worker_loop` can clear the dedup key. A
    swallowed exception would lock Lua retries out of the TTL window
    — regression pin for the Copilot/codex P1 finding on #142.
    """
    from bot.services.stats_ready_mixin import _StatsReadyMixin

    class _Bot(_StatsReadyMixin):
        def __init__(self):
            self._queue_pending_metadata = MagicMock()
            self._fetch_latest_stats_file = AsyncMock(
                side_effect=RuntimeError("SSH boom"),
            )
            self._store_lua_round_teams = AsyncMock()
            self._store_lua_spawn_stats = AsyncMock()
            self.track_error = AsyncMock()

    bot = _Bot()
    msg = MagicMock()
    msg.delete = AsyncMock()

    metadata = {
        "map_name": "te_escape2",
        "round_number": 1,
        "round_end_unix": 1772746382,
    }
    with pytest.raises(RuntimeError, match="SSH boom"):
        await bot._process_stats_ready_round(metadata, msg)

    # track_error still fires before re-raise (admin alerting preserved)
    bot.track_error.assert_awaited_once()


@pytest.mark.asyncio
async def test_stats_ready_fetches_before_storing_lua():
    """The two side effects must fire in the right order — fetch first."""
    from bot.services.stats_ready_mixin import _StatsReadyMixin

    order: list[str] = []

    def _fetch_side_effect(*_a, **_kw):
        order.append("fetch")
        return True  # success — so the handler doesn't raise

    class _Bot(_StatsReadyMixin):
        def __init__(self):
            self._queue_pending_metadata = MagicMock(side_effect=lambda *a, **kw: order.append("queue"))
            self._fetch_latest_stats_file = AsyncMock(side_effect=_fetch_side_effect)
            self._store_lua_round_teams = AsyncMock(side_effect=lambda *a, **kw: order.append("store_lua"))
            self._store_lua_spawn_stats = AsyncMock(side_effect=lambda *a, **kw: order.append("store_spawn"))
            self._parse_spawn_stats_from_metadata = MagicMock(return_value=None)
            self._fields_to_metadata_map = MagicMock(return_value={})
            self._build_round_metadata_from_map = MagicMock(return_value={
                "map_name": "te_escape2",
                "round_number": 1,
                "round_end_unix": 1772746382,
                "round_start_unix": 1772746000,
                "lua_playtime_seconds": 300,
                "lua_warmup_seconds": 0,
                "lua_pause_count": 0,
                "winner_team": 1,
                "axis_score": 1,
                "allies_score": 0,
                "surrender_team": 0,
                "axis_players": [],
                "allies_players": [],
            })
            self.track_error = AsyncMock()

    embed = MagicMock()
    embed.fields = []
    embed.footer = None
    msg = MagicMock()
    msg.embeds = [embed]
    msg.delete = AsyncMock()

    bot = _Bot()
    await bot._process_stats_ready_webhook(msg)

    # Fetch must complete before Lua teams are stored.
    assert "fetch" in order and "store_lua" in order
    fetch_idx = order.index("fetch")
    store_idx = order.index("store_lua")
    assert fetch_idx < store_idx, f"fetch must come before store_lua (got order: {order})"


@pytest.mark.asyncio
async def test_stats_ready_queues_metadata_before_fetch():
    """Pending metadata is the SSH-poll safety net — queue it before we
    kick off the immediate fetch so a fetch failure doesn't lose the
    override data."""
    from bot.services.stats_ready_mixin import _StatsReadyMixin

    order: list[str] = []

    def _fetch_side_effect(*_a, **_kw):
        order.append("fetch")
        return True

    class _Bot(_StatsReadyMixin):
        def __init__(self):
            self._queue_pending_metadata = MagicMock(side_effect=lambda *a, **kw: order.append("queue"))
            self._fetch_latest_stats_file = AsyncMock(side_effect=_fetch_side_effect)
            self._store_lua_round_teams = AsyncMock()
            self._store_lua_spawn_stats = AsyncMock()
            self._parse_spawn_stats_from_metadata = MagicMock(return_value=None)
            self._fields_to_metadata_map = MagicMock(return_value={})
            self._build_round_metadata_from_map = MagicMock(return_value={
                "map_name": "te_escape2",
                "round_number": 1,
                "round_end_unix": 1772746382,
                "round_start_unix": 1772746000,
                "lua_playtime_seconds": 300,
                "lua_warmup_seconds": 0,
                "lua_pause_count": 0,
                "winner_team": 1,
                "axis_score": 1,
                "allies_score": 0,
                "surrender_team": 0,
                "axis_players": [],
                "allies_players": [],
            })
            self.track_error = AsyncMock()

    embed = MagicMock()
    embed.fields = []
    embed.footer = None
    msg = MagicMock()
    msg.embeds = [embed]
    msg.delete = AsyncMock()

    bot = _Bot()
    await bot._process_stats_ready_webhook(msg)

    assert "queue" in order and "fetch" in order
    assert order.index("queue") < order.index("fetch")
