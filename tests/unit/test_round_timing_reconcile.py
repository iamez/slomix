"""Default-OFF and schema/workflow contracts for the bounded timing journal."""

from fnmatch import fnmatchcase
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


@pytest.mark.parametrize("scope", [[], ()])
async def test_empty_scope_needs_no_adapter(scope):
    assert await reconcile_missing_round_timing(None, enabled=True, round_ids=scope) == 0


@pytest.mark.parametrize("scope", [
    "1", 1, {1}, {"id": 1}, [True], [False], [0], [-1], [1.0], ["1"],
    [None], [2_147_483_648], list(range(1, 102)), [1] * 101,
])
async def test_invalid_scope_rejected_before_database_access(scope):
    with pytest.raises(ValueError, match="Timing scope"):
        await reconcile_missing_round_timing(None, enabled=True, round_ids=scope)


async def test_scope_is_copied_deduplicated_and_bound():
    from contextlib import asynccontextmanager

    conn = SimpleNamespace(fetch=AsyncMock(return_value=[]))
    scope = [3, 1, 3]

    @asynccontextmanager
    async def transaction():
        scope.append(99)  # Caller mutation after admission cannot broaden scope.
        yield conn

    assert await reconcile_missing_round_timing(
        SimpleNamespace(transaction=transaction), enabled=True, round_ids=scope,
    ) == 0
    assert conn.fetch.await_args.args[1] == (1, 3)


def test_bootstrap_mirrors_timing_migration():
    root = Path(__file__).resolve().parents[2]
    migration = (root / "migrations/084_runtime_timing_events.sql").read_text().strip()
    assert migration in (root / "tools/schema_postgresql.sql").read_text()


def test_ci_covers_stacked_runtime_pushes_without_broadening_other_branches():
    import yaml

    root = Path(__file__).resolve().parents[2]
    workflow = yaml.safe_load((root / ".github/workflows/tests.yml").read_text())
    # PyYAML's YAML 1.1 loader interprets the GitHub key 'on' as True.
    triggers = workflow.get("on", workflow.get(True))
    branches = triggers["push"]["branches"]
    assert any(fnmatchcase("feat/db-runtime-timing-r02", p) for p in branches)
    assert not any(fnmatchcase("feat/unrelated-example", p) for p in branches)
    assert triggers["pull_request"]["branches"] == ["main", "develop"]


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
