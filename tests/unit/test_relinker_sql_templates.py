"""Tests for the proximity re-linker SQL templates.

The `_relink_sql()` helper picks between primary (round_number-aware)
and fallback (no round_number) UPDATE shapes and caches the formatted
result. Pin the contract so the mismatch-detection clause stays in
both shapes — without it, a single proximity row attached to the wrong
round persists forever and silently corrupts KIS / momentum / BOX.

PR #160 added the mismatch leg (`OR round_id != $1`); these tests stop
a future "simplification" from removing it.
"""
from __future__ import annotations

import importlib

# Import via runtime to side-step the cog's discord.ext dependency at
# class definition time. The mixin module imports `discord.ext.tasks`
# which is fine at import — the helpers we need don't touch it.
relinker = importlib.import_module("bot.cogs.proximity_mixins.relinker_mixin")


def setup_function(_func):
    """Reset the module-level caches before each test."""
    relinker._relink_primary_cache.clear()
    relinker._relink_fallback_cache.clear()


def test_primary_template_includes_round_number_and_mismatch_clause():
    sql = relinker._relink_sql("proximity_kill_outcome")
    # All five primary parameters must be present
    assert "map_name = $2" in sql
    assert "round_number = $3" in sql
    assert "session_date = $4" in sql
    assert "round_start_unix = $5" in sql
    # Mismatch detection — the load-bearing fix from PR #160
    assert "(round_id IS NULL OR round_id != $1)" in sql, (
        "primary template must keep the OR-mismatch clause; without it the "
        "re-linker only repairs NULLs and leaves wrong-round links untouched"
    )


def test_fallback_template_keeps_mismatch_clause():
    sql = relinker._relink_sql("proximity_hit_region", fallback=True)
    # Fallback uses only map + round_start_unix (no round_number)
    assert "round_number" not in sql
    assert "map_name = $2" in sql
    assert "round_start_unix = $3" in sql
    assert "(round_id IS NULL OR round_id != $1)" in sql, (
        "fallback template must also detect mismatched links — tables "
        "without round_number still get used by back-to-back-match races"
    )


def test_table_name_is_substituted():
    """Each call returns SQL targeting the requested table."""
    a = relinker._relink_sql("proximity_kill_outcome")
    b = relinker._relink_sql("proximity_team_cohesion")
    assert "UPDATE proximity_kill_outcome SET" in a
    assert "UPDATE proximity_team_cohesion SET" in b
    assert a != b


def test_primary_and_fallback_caches_are_independent():
    """Same table name, different `fallback` flags → two distinct strings."""
    primary = relinker._relink_sql("proximity_carrier_event")
    fallback = relinker._relink_sql("proximity_carrier_event", fallback=True)
    assert primary != fallback
    assert "round_number" in primary
    assert "round_number" not in fallback


def test_cache_returns_same_object_on_repeat_call():
    """Hot path: the template is built once per (table, fallback) and reused."""
    a = relinker._relink_sql("proximity_combat_position")
    b = relinker._relink_sql("proximity_combat_position")
    assert a is b


def test_cache_population_isolated_to_correct_dict():
    relinker._relink_sql("proximity_focus_fire")
    relinker._relink_sql("proximity_focus_fire", fallback=True)
    assert "proximity_focus_fire" in relinker._relink_primary_cache
    assert "proximity_focus_fire" in relinker._relink_fallback_cache
    # No cross-contamination
    assert (
        relinker._relink_primary_cache["proximity_focus_fire"]
        != relinker._relink_fallback_cache["proximity_focus_fire"]
    )
