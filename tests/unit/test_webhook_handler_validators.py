"""Tests for _WebhookHandlerMixin pure validators + mode helpers.

These methods sit on the bot's webhook ingest path. A regression in any
of them either:

- Lets a malicious filename through to file processing (path traversal,
  injection), OR
- Silently drops legitimate webhooks (a deploy-time mode change is
  enough to lose every round notification).

Pin the contract for both filename validation AND the trigger-mode
state machine.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from bot.services.webhook_handler_mixin import _WebhookHandlerMixin


class _StubBot(_WebhookHandlerMixin):
    """Minimal harness: only `self.config` is needed for the pure
    helpers under test. Avoids spinning up the full bot."""

    def __init__(self, **config_attrs):
        self.config = SimpleNamespace(**config_attrs)


# ---------------------------------------------------------------------------
# _webhook_trigger_mode — config → canonical mode string
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw, expected", [
    ("stats_ready_only", "stats_ready_only"),
    ("dual",             "dual"),
    ("filename_only",    "filename_only"),
])
def test_webhook_trigger_mode_returns_known_values(raw, expected):
    bot = _StubBot(webhook_trigger_mode=raw)
    assert bot._webhook_trigger_mode() == expected


@pytest.mark.parametrize("raw, expected", [
    ("STATS_READY_ONLY", "stats_ready_only"),
    ("DUAL",             "dual"),
    ("Filename_Only",    "filename_only"),
])
def test_webhook_trigger_mode_lowercases(raw, expected):
    """Casing must not matter — pin so future env vars set in upper case
    keep working."""
    bot = _StubBot(webhook_trigger_mode=raw)
    assert bot._webhook_trigger_mode() == expected


def test_webhook_trigger_mode_strips_whitespace():
    bot = _StubBot(webhook_trigger_mode="  dual  ")
    assert bot._webhook_trigger_mode() == "dual"


@pytest.mark.parametrize("bad", [
    "",
    "unknown",
    "off",
    "yes",
    None,
])
def test_webhook_trigger_mode_falls_back_to_stats_ready_only(bad):
    """Invalid / missing mode → safe default. Pin so a typo in .env can't
    silently turn into "filename_only" or some other surprise mode."""
    bot = _StubBot(webhook_trigger_mode=bad)
    assert bot._webhook_trigger_mode() == "stats_ready_only"


def test_webhook_trigger_mode_uses_default_when_attr_missing():
    """Bot config without `webhook_trigger_mode` attr → default."""
    bot = _StubBot()  # no webhook_trigger_mode
    assert bot._webhook_trigger_mode() == "stats_ready_only"


# ---------------------------------------------------------------------------
# Mode → capability boolean accessors
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mode, allows_stats_ready, allows_filename", [
    ("stats_ready_only", True,  False),
    ("dual",             True,  True),
    ("filename_only",    False, True),
])
def test_mode_allows_state_table(mode, allows_stats_ready, allows_filename):
    """The full truth table — every mode flips exactly the right pair.
    A regression here would either silently disable STATS_READY (no
    round notifications) or accidentally enable filename triggers
    when the operator wanted them off."""
    bot = _StubBot(webhook_trigger_mode=mode)
    assert bot._webhook_mode_allows_stats_ready() is allows_stats_ready
    assert bot._webhook_mode_allows_filename_triggers() is allows_filename


# ---------------------------------------------------------------------------
# _validate_endstats_filename — security boundary
# ---------------------------------------------------------------------------


@pytest.fixture
def bot():
    return _StubBot()


@pytest.mark.parametrize("good", [
    "2026-01-12-224606-te_escape2-round-2-endstats.txt",
    "2025-12-09-100000-supply-round-1-endstats.txt",
    "2026-04-21-235959-mp_oasis-round-10-endstats.txt",
    "2020-01-01-000000-a-round-1-endstats.txt",
    "2035-12-31-235959-radar-round-1-endstats.txt",
])
def test_validate_endstats_accepts_valid_format(bot, good):
    """Pin happy-path examples so a regex tweak that breaks them is
    immediately visible."""
    assert bot._validate_endstats_filename(good) is True


@pytest.mark.parametrize("bad", [
    "../etc/passwd",                                   # parent traversal
    "2026-01-12-224606-../te_escape2-round-2-endstats.txt",  # embedded ..
    "2026-01-12/224606-te-round-2-endstats.txt",      # slash
    "2026-01-12-224606-te-round-2-endstats.txt\0",    # null byte
    "2026-01-12-224606-te-round-2-endstats.txt\\evil", # backslash
])
def test_validate_endstats_rejects_path_injections(bot, bad):
    """Path-traversal + injection chars MUST be rejected up front so the
    filename never reaches a file-open call."""
    assert bot._validate_endstats_filename(bad) is False


def test_validate_endstats_rejects_too_long_filename(bot):
    """>255 chars → rejected (DoS prevention). Edge: exactly 256."""
    f = "a" * 256 + ".txt"
    assert bot._validate_endstats_filename(f) is False


def test_validate_endstats_rejects_filename_at_length_boundary(bot):
    """256 chars = rejected; under-256 with otherwise-invalid pattern is
    rejected on pattern, not length."""
    # 255-char filename that doesn't match pattern → rejected on pattern
    f = "a" * 255
    assert bot._validate_endstats_filename(f) is False


@pytest.mark.parametrize("bad", [
    "stats.txt",                                                 # no datetime
    "2026-01-12-te_escape2-round-2-endstats.txt",                # missing time
    "2026-01-12-224606-te_escape2-round-2.txt",                  # not -endstats
    "2026-01-12-224606-te_escape2-round-2-endstats.log",         # wrong ext
    "2026-1-12-224606-te-round-2-endstats.txt",                  # 1-digit month
    "26-01-12-224606-te-round-2-endstats.txt",                   # 2-digit year
    "2026-01-12-224606-te-round-2-endstats",                     # no .txt
])
def test_validate_endstats_rejects_pattern_violations(bot, bad):
    assert bot._validate_endstats_filename(bad) is False


@pytest.mark.parametrize("bad", [
    "2019-01-12-224606-te-round-2-endstats.txt",  # year < 2020
    "2036-01-12-224606-te-round-2-endstats.txt",  # year > 2035
    "2026-00-12-224606-te-round-2-endstats.txt",  # month=0
    "2026-13-12-224606-te-round-2-endstats.txt",  # month=13
    "2026-01-00-224606-te-round-2-endstats.txt",  # day=0
    "2026-01-32-224606-te-round-2-endstats.txt",  # day=32
])
def test_validate_endstats_rejects_invalid_date_components(bot, bad):
    """Date component bounds — pin so the regex tightening can't be
    silently relaxed (e.g., year-range bump that accidentally drops the
    upper bound)."""
    assert bot._validate_endstats_filename(bad) is False


@pytest.mark.parametrize("bad", [
    "2026-01-12-246060-te-round-2-endstats.txt",  # hour=24
    "2026-01-12-126060-te-round-2-endstats.txt",  # minute=60
    "2026-01-12-125960-te-round-2-endstats.txt",  # 12:59:60 sec=60
])
def test_validate_endstats_rejects_invalid_timestamp(bot, bad):
    assert bot._validate_endstats_filename(bad) is False


@pytest.mark.parametrize("bad_round", ["0", "11", "99", "100"])
def test_validate_endstats_rejects_round_outside_1_to_10(bot, bad_round):
    """round_num must be 1-10 inclusive."""
    f = f"2026-01-12-224606-supply-round-{bad_round}-endstats.txt"
    assert bot._validate_endstats_filename(f) is False


@pytest.mark.parametrize("good_round", ["1", "2", "5", "10"])
def test_validate_endstats_accepts_round_1_through_10(bot, good_round):
    f = f"2026-01-12-224606-supply-round-{good_round}-endstats.txt"
    assert bot._validate_endstats_filename(f) is True


def test_validate_endstats_rejects_map_name_too_long(bot):
    """map_name > 50 chars → rejected. Pinned so an enthusiastic mod with
    a 60-char custom map name doesn't quietly fail; rather, it explodes
    loudly on the validator."""
    long_map = "x" * 51
    f = f"2026-01-12-224606-{long_map}-round-1-endstats.txt"
    assert bot._validate_endstats_filename(f) is False


def test_validate_endstats_accepts_map_name_at_50_char_boundary(bot):
    map50 = "x" * 50
    f = f"2026-01-12-224606-{map50}-round-1-endstats.txt"
    assert bot._validate_endstats_filename(f) is True


@pytest.mark.parametrize("good_map", [
    "supply",
    "te_escape2",
    "mp_oasis",
    "etl_sp_delivery",
    "radar2",
    "MAP_WITH_UPPER",
    "abc-def_123",  # underscore + hyphen + digit
])
def test_validate_endstats_accepts_map_name_charset(bot, good_map):
    """Map name allowlist: alnum + hyphen + underscore. Pin so a future
    "support apostrophes too" change is visible."""
    f = f"2026-01-12-224606-{good_map}-round-1-endstats.txt"
    assert bot._validate_endstats_filename(f) is True


@pytest.mark.parametrize("bad_map", [
    "map name",       # space
    "map.name",       # dot
    "map%20name",     # percent-encoded space
    "map'name",       # quote
])
def test_validate_endstats_rejects_disallowed_map_chars(bot, bad_map):
    f = f"2026-01-12-224606-{bad_map}-round-1-endstats.txt"
    assert bot._validate_endstats_filename(f) is False
