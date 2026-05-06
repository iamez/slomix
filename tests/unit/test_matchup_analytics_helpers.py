"""Tests for MatchupAnalyticsService pure helpers + TTLCache.

The matchup analytics module decides which lineup beats which over a
season. A regression silently:

- create_lineup_hash: order-sensitive → "Alice/Bob" and "Bob/Alice" map
  to different hashes → matchup history splits artificially.
- create_matchup_id: not normalised → A-vs-B stored separately from
  B-vs-A → win-rate calc is half what it should be.
- get_confidence_level: wrong threshold → "high" tier on 1 match
  silently overstates accuracy.
- TTLCache: never expires → stale baselines linger past TTL; or
  evicts wrong entry → cache thrashing.

Pin every contract.
"""
from __future__ import annotations

import time

import pytest

from bot.services.matchup_analytics_service import (
    MatchupAnalyticsService,
    MatchupStats,
    PlayerMatchupStats,
    TTLCache,
)

# ---------------------------------------------------------------------------
# create_lineup_hash — order independence + determinism
# ---------------------------------------------------------------------------


def test_lineup_hash_deterministic_for_same_input():
    """Same GUIDs → same hash, every time."""
    h1 = MatchupAnalyticsService.create_lineup_hash(["a", "b", "c"])
    h2 = MatchupAnalyticsService.create_lineup_hash(["a", "b", "c"])
    assert h1 == h2


def test_lineup_hash_order_independent():
    """Reversed → same hash. Without sorting, Alice/Bob and Bob/Alice
    would split history. Pin the sort."""
    h1 = MatchupAnalyticsService.create_lineup_hash(["alice", "bob", "carol"])
    h2 = MatchupAnalyticsService.create_lineup_hash(["carol", "alice", "bob"])
    assert h1 == h2


def test_lineup_hash_different_for_different_players():
    """Different roster → different hash. Pin so a hash collision
    bug doesn't quietly merge two matchups."""
    h1 = MatchupAnalyticsService.create_lineup_hash(["a", "b", "c"])
    h2 = MatchupAnalyticsService.create_lineup_hash(["a", "b", "d"])
    assert h1 != h2


def test_lineup_hash_returns_12_char_string():
    """First 12 chars of SHA-256 hex — pin format so DB schema (likely
    VARCHAR(12)) doesn't truncate silently if hash format changes."""
    h = MatchupAnalyticsService.create_lineup_hash(["a", "b"])
    assert len(h) == 12
    assert all(c in "0123456789abcdef" for c in h)


def test_lineup_hash_handles_empty_list():
    """Empty lineup → still produces a hash (hash of empty string).
    Pinned observed behaviour — caller must reject empty before."""
    h = MatchupAnalyticsService.create_lineup_hash([])
    assert isinstance(h, str)
    assert len(h) == 12


def test_lineup_hash_handles_single_player():
    h = MatchupAnalyticsService.create_lineup_hash(["solo"])
    assert isinstance(h, str)
    assert len(h) == 12


# ---------------------------------------------------------------------------
# create_matchup_id — normalisation
# ---------------------------------------------------------------------------


def test_matchup_id_normalises_a_vs_b_to_canonical_form():
    """Lower hash always first, regardless of arg order."""
    out1 = MatchupAnalyticsService.create_matchup_id("aaa", "bbb")
    out2 = MatchupAnalyticsService.create_matchup_id("bbb", "aaa")
    assert out1 == out2 == "aaa:bbb"


def test_matchup_id_format_uses_colon_separator():
    """`{lower}:{higher}` — pin so SQL WHERE uses correct LIKE
    pattern."""
    out = MatchupAnalyticsService.create_matchup_id("alpha", "beta")
    assert ":" in out
    assert out.split(":") == ["alpha", "beta"]


def test_matchup_id_lexicographic_order():
    """SHA-256 hex hashes are compared lexicographically (string
    compare), not numerically. Pin the choice."""
    out = MatchupAnalyticsService.create_matchup_id("9", "10")
    # "10" < "9" lex → "10" first
    assert out == "10:9"


def test_matchup_id_with_equal_hashes_returns_self_pair():
    """Same hash on both sides (mirror match) → "X:X"."""
    out = MatchupAnalyticsService.create_matchup_id("foo", "foo")
    assert out == "foo:foo"


# ---------------------------------------------------------------------------
# get_confidence_level — sample-size → tier
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("matches, expected", [
    (0,  "low"),
    (1,  "low"),    # MIN_MATCHES_LOW_CONFIDENCE = 1, but threshold for medium is 3
    (2,  "low"),
    (3,  "medium"),  # MIN_MATCHES_MEDIUM_CONFIDENCE
    (4,  "medium"),
    (5,  "high"),    # MIN_MATCHES_HIGH_CONFIDENCE
    (10, "high"),
    (100, "high"),
])
def test_confidence_level_thresholds(matches, expected):
    """Pin the full tier ladder. A regression that bumps the high
    threshold to 10 silently downgrades existing matchups to medium."""
    assert MatchupAnalyticsService.get_confidence_level(matches) == expected


# ---------------------------------------------------------------------------
# TTLCache — TTL expiry + LRU eviction
# ---------------------------------------------------------------------------


def test_ttl_cache_returns_none_for_missing_key():
    cache = TTLCache(maxsize=10, ttl_seconds=60)
    assert cache.get("missing") is None


def test_ttl_cache_returns_value_when_present():
    cache = TTLCache(maxsize=10, ttl_seconds=60)
    cache.set("k", "v")
    assert cache.get("k") == "v"


def test_ttl_cache_expires_after_ttl(monkeypatch):
    """Time-based TTL: once `time.time() - timestamp >= ttl`, cache
    returns None. Pin so a regression that drops the comparison
    silently makes the cache eternal."""
    cache = TTLCache(maxsize=10, ttl_seconds=60)
    # Set at time t=1000
    monkeypatch.setattr(time, "time", lambda: 1000.0)
    cache.set("k", "v")
    # Read at time t=1059 → not expired
    monkeypatch.setattr(time, "time", lambda: 1059.0)
    assert cache.get("k") == "v"
    # Read at time t=1061 → expired (60s TTL elapsed)
    monkeypatch.setattr(time, "time", lambda: 1061.0)
    assert cache.get("k") is None


def test_ttl_cache_removes_expired_entry_on_get(monkeypatch):
    """Expired entry is REMOVED on get (not just hidden) — pin so
    expired entries don't bloat the dict."""
    cache = TTLCache(maxsize=10, ttl_seconds=60)
    monkeypatch.setattr(time, "time", lambda: 1000.0)
    cache.set("k", "v")
    monkeypatch.setattr(time, "time", lambda: 1100.0)
    cache.get("k")  # triggers cleanup
    assert "k" not in cache._cache


def test_ttl_cache_evicts_oldest_on_capacity(monkeypatch):
    """At maxsize, set() evicts the oldest entry. Pin so a regression
    that "just appends" silently leaks memory."""
    cache = TTLCache(maxsize=2, ttl_seconds=600)
    monkeypatch.setattr(time, "time", lambda: 1000.0)
    cache.set("first", "v1")
    monkeypatch.setattr(time, "time", lambda: 1010.0)
    cache.set("second", "v2")
    monkeypatch.setattr(time, "time", lambda: 1020.0)
    cache.set("third", "v3")  # evicts "first" (oldest)
    assert cache.get("first") is None
    assert cache.get("second") == "v2"
    assert cache.get("third") == "v3"


def test_ttl_cache_set_overwrites_existing_key(monkeypatch):
    """Re-setting a key updates its value AND timestamp."""
    cache = TTLCache(maxsize=10, ttl_seconds=60)
    monkeypatch.setattr(time, "time", lambda: 1000.0)
    cache.set("k", "v1")
    monkeypatch.setattr(time, "time", lambda: 1010.0)
    cache.set("k", "v2")
    assert cache.get("k") == "v2"


# ---------------------------------------------------------------------------
# format_matchup_summary — Discord embed text
# ---------------------------------------------------------------------------


def _make_stats(**kw) -> MatchupStats:
    """Build a MatchupStats with defaults for testing the formatter."""
    base = {
        "lineup_a_hash": "aaa", "lineup_b_hash": "bbb",
        "matchup_id": "aaa:bbb",
        "lineup_a_names": ["Alice"], "lineup_b_names": ["Bob"],
        "total_matches": 5,
        "lineup_a_wins": 3, "lineup_b_wins": 2,
        "lineup_a_winrate": 0.6, "lineup_b_winrate": 0.4,
        "confidence": "medium",
    }
    base.update(kw)
    return MatchupStats(**base)


def test_format_matchup_includes_lineup_names():
    svc = MatchupAnalyticsService(db_adapter=None)
    stats = _make_stats()
    out = svc.format_matchup_summary(stats)
    assert "Alice" in out
    assert "Bob" in out


def test_format_matchup_perspective_a_uses_a_winrate():
    svc = MatchupAnalyticsService(db_adapter=None)
    stats = _make_stats()
    out = svc.format_matchup_summary(stats, perspective="a")
    assert "60%" in out  # 0.6 * 100 = 60


def test_format_matchup_perspective_b_uses_b_winrate():
    svc = MatchupAnalyticsService(db_adapter=None)
    stats = _make_stats()
    out = svc.format_matchup_summary(stats, perspective="b")
    assert "40%" in out  # 0.4 * 100


def test_format_matchup_truncates_long_lineup_to_three_names():
    svc = MatchupAnalyticsService(db_adapter=None)
    stats = _make_stats(
        lineup_a_names=["Alice", "Bob", "Carol", "Dave", "Eve"],
    )
    out = svc.format_matchup_summary(stats)
    assert "Alice, Bob, Carol..." in out
    assert "Dave" not in out
    assert "Eve" not in out


def test_format_matchup_includes_confidence_emoji():
    """high → 🟢, medium → 🟡, low → 🔴."""
    svc = MatchupAnalyticsService(db_adapter=None)
    out_high = svc.format_matchup_summary(_make_stats(confidence="high"))
    out_med = svc.format_matchup_summary(_make_stats(confidence="medium"))
    out_low = svc.format_matchup_summary(_make_stats(confidence="low"))
    assert "🟢" in out_high
    assert "🟡" in out_med
    assert "🔴" in out_low


def test_format_matchup_unknown_confidence_uses_white_circle():
    """Unknown confidence value → ⚪ fallback (NOT crash)."""
    svc = MatchupAnalyticsService(db_adapter=None)
    out = svc.format_matchup_summary(_make_stats(confidence="???"))
    assert "⚪" in out


def test_format_matchup_top_performer_renders_with_sign():
    """Positive impact gets explicit '+' prefix; negative natural '-'."""
    svc = MatchupAnalyticsService(db_adapter=None)
    pstats = PlayerMatchupStats(player_guid="g", player_name="Star")
    pstats.impact_percent = 25.5
    stats = _make_stats(
        player_stats={"g": pstats},
        top_performer_guid="g",
        top_performer_impact=25.5,
    )
    out = svc.format_matchup_summary(stats)
    assert "+26%" in out or "+25%" in out  # rounded
    assert "Star" in out


def test_format_matchup_worst_performer_only_shown_if_below_minus_10():
    """Worst performer line only appears when impact < -10. Pin so a
    -5% blip doesn't shame players."""
    svc = MatchupAnalyticsService(db_adapter=None)
    pstats = PlayerMatchupStats(player_guid="g", player_name="OK")
    pstats.impact_percent = -5
    stats = _make_stats(
        player_stats={"g": pstats},
        worst_performer_guid="g",
        worst_performer_impact=-5,  # NOT < -10
    )
    out = svc.format_matchup_summary(stats)
    assert "OK" not in out


def test_format_matchup_loss_count_includes_ties():
    """L count = total - wins - ties."""
    svc = MatchupAnalyticsService(db_adapter=None)
    stats = _make_stats(
        total_matches=10, lineup_a_wins=4, ties=1, lineup_a_winrate=0.4,
    )
    out = svc.format_matchup_summary(stats)
    assert "4W-5L" in out  # 10 - 4 - 1 = 5


# ---------------------------------------------------------------------------
# format_synergy_summary
# ---------------------------------------------------------------------------


def test_format_synergy_includes_player_names():
    svc = MatchupAnalyticsService(db_adapter=None)
    syn = {
        "matches_together": 5,
        "avg_dpm_together": 250.0,
        "avg_dpm_baseline": 200.0,
        "synergy_percent": 25.0,
        "confidence": "medium",
    }
    out = svc.format_synergy_summary(syn, "Alice", "Bob")
    assert "Alice" in out
    assert "Bob" in out


def test_format_synergy_positive_gets_plus_sign():
    svc = MatchupAnalyticsService(db_adapter=None)
    syn = {
        "matches_together": 5, "avg_dpm_together": 250.0,
        "avg_dpm_baseline": 200.0, "synergy_percent": 25.0,
        "confidence": "high",
    }
    out = svc.format_synergy_summary(syn, "A", "B")
    assert "+25.0%" in out


def test_format_synergy_negative_keeps_natural_sign():
    svc = MatchupAnalyticsService(db_adapter=None)
    syn = {
        "matches_together": 5, "avg_dpm_together": 150.0,
        "avg_dpm_baseline": 200.0, "synergy_percent": -25.0,
        "confidence": "high",
    }
    out = svc.format_synergy_summary(syn, "A", "B")
    assert "-25.0%" in out
    assert "+-25" not in out  # no double sign
