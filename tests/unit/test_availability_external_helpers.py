"""Tests for _AvailabilityExternalChannelsMixin pure helpers.

These statics handle parsing of /avail commands coming from Telegram
and Signal — single line of text → (date, operation, status). A
regression silently:

- `_normalize_status_input` drops a synonym (e.g., "L" for LOOKING) →
  user types `/avail today L` and gets a usage error.
- `_normalize_status_input` accepts a typo'd status as a real one →
  silent miscategorisation.
- `_parse_date_arg` accepts an ambiguous date format and parses
  surprisingly → wrong day's availability set.
- `_normalize_operation_input` REMOVE keyword set drift → user typing
  "DELETE" is treated as unknown status → confused user.
- `_parse_availability_operation` order swap (status-then-date) →
  date-then-status path mis-parses → silently sets wrong slot.
- `_format_external_usage` text drift → operator-facing help message
  describes commands the bot no longer supports.
- REMOVE_STATUS_KEYWORDS shared module constant: pin every entry so
  a typo'd rename in one place silently stops accepting the keyword.

Pin every static + the shared keyword set.
"""
from __future__ import annotations

from datetime import date as dt_date

import pytest

from bot.cogs.availability_mixins import REMOVE_STATUS_KEYWORDS
from bot.cogs.availability_mixins.external_channels_mixin import (
    _AvailabilityExternalChannelsMixin as Mixin,
)

# ---------------------------------------------------------------------------
# REMOVE_STATUS_KEYWORDS — shared constant
# ---------------------------------------------------------------------------


def test_remove_keywords_pinned_set():
    """Pin every accepted "remove" synonym. A drift breaks every
    /avail command that uses an alternative phrasing."""
    assert {"REMOVE", "DELETE", "CLEAR", "UNSET", "NONE"} == REMOVE_STATUS_KEYWORDS


def test_remove_keywords_is_set():
    """Set membership is O(1) — pin so a regression to list/tuple
    doesn't slow the per-message dispatch."""
    assert isinstance(REMOVE_STATUS_KEYWORDS, set)


# ---------------------------------------------------------------------------
# _normalize_status_input
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("inp, expected", [
    ("LOOKING", "LOOKING"),
    ("looking", "LOOKING"),
    ("Looking", "LOOKING"),
    ("LOOKING_TO_PLAY", "LOOKING"),
    ("L", "LOOKING"),
    ("AVAILABLE", "AVAILABLE"),
    ("A", "AVAILABLE"),
    ("MAYBE", "MAYBE"),
    ("TENTATIVE", "MAYBE"),
    ("M", "MAYBE"),
    ("NOT_PLAYING", "NOT_PLAYING"),
    ("NOTPLAYING", "NOT_PLAYING"),
    ("NO", "NOT_PLAYING"),
    ("N", "NOT_PLAYING"),
])
def test_normalize_status_known_synonyms(inp, expected):
    """Pin every (synonym → canonical) mapping. A drop here breaks
    a real user phrasing."""
    assert Mixin._normalize_status_input(inp) == expected


def test_normalize_status_strips_whitespace():
    """Leading/trailing whitespace ignored."""
    assert Mixin._normalize_status_input("  L  ") == "LOOKING"


def test_normalize_status_unknown_returns_none():
    """Unknown text → None (NOT a default — caller decides what to do)."""
    assert Mixin._normalize_status_input("PARTYING") is None
    assert Mixin._normalize_status_input("xyz") is None


def test_normalize_status_empty_returns_none():
    assert Mixin._normalize_status_input("") is None
    assert Mixin._normalize_status_input(None) is None


# ---------------------------------------------------------------------------
# _parse_date_arg
# ---------------------------------------------------------------------------


def test_parse_date_today_keyword():
    """`today` → now_date arg."""
    now = dt_date(2026, 5, 7)
    assert Mixin._parse_date_arg("today", now) == now


def test_parse_date_tomorrow_keyword():
    """`tomorrow` → now+1 day."""
    now = dt_date(2026, 5, 7)
    assert Mixin._parse_date_arg("tomorrow", now) == dt_date(2026, 5, 8)


def test_parse_date_iso_string():
    """ISO date string → date object."""
    assert Mixin._parse_date_arg("2026-12-25", dt_date(2026, 5, 7)) == dt_date(2026, 12, 25)


def test_parse_date_case_insensitive_keywords():
    """`TODAY`, `Tomorrow` accepted regardless of casing."""
    now = dt_date(2026, 5, 7)
    assert Mixin._parse_date_arg("TODAY", now) == now
    assert Mixin._parse_date_arg("Tomorrow", now) == dt_date(2026, 5, 8)


def test_parse_date_strips_whitespace_iso():
    assert Mixin._parse_date_arg("  2026-05-07  ", dt_date(2026, 5, 7)) == dt_date(2026, 5, 7)


def test_parse_date_invalid_returns_none():
    """Garbage / wrong format → None (caller decides error response)."""
    now = dt_date(2026, 5, 7)
    assert Mixin._parse_date_arg("not-a-date", now) is None
    assert Mixin._parse_date_arg("2026/05/07", now) is None
    assert Mixin._parse_date_arg("05-07-2026", now) is None


def test_parse_date_empty_returns_none():
    now = dt_date(2026, 5, 7)
    assert Mixin._parse_date_arg("", now) is None
    assert Mixin._parse_date_arg(None, now) is None


# ---------------------------------------------------------------------------
# _normalize_operation_input
# ---------------------------------------------------------------------------


def test_operation_input_status():
    """Plain status text → ("SET", canonical_status)."""
    assert Mixin._normalize_operation_input("LOOKING") == ("SET", "LOOKING")
    assert Mixin._normalize_operation_input("L") == ("SET", "LOOKING")
    assert Mixin._normalize_operation_input("MAYBE") == ("SET", "MAYBE")


def test_operation_input_remove_keywords():
    """Any REMOVE_STATUS_KEYWORDS entry → ("REMOVE", None)."""
    for kw in REMOVE_STATUS_KEYWORDS:
        out = Mixin._normalize_operation_input(kw)
        assert out == ("REMOVE", None), f"REMOVE keyword {kw} not recognised"


def test_operation_input_normalises_separators():
    """Spaces and hyphens normalised to underscores. Pin so
    `not playing` and `not-playing` both → NOT_PLAYING."""
    assert Mixin._normalize_operation_input("not playing") == ("SET", "NOT_PLAYING")
    assert Mixin._normalize_operation_input("not-playing") == ("SET", "NOT_PLAYING")


def test_operation_input_unknown_returns_double_none():
    """Unknown → (None, None) — caller's signal to show usage."""
    assert Mixin._normalize_operation_input("xyz") == (None, None)


def test_operation_input_empty_returns_double_none():
    assert Mixin._normalize_operation_input("") == (None, None)
    assert Mixin._normalize_operation_input(None) == (None, None)


# ---------------------------------------------------------------------------
# _parse_availability_operation — full command parsing
# ---------------------------------------------------------------------------


def test_parse_op_date_then_status():
    """`<date> <status>` → (date, "SET", status)."""
    now = dt_date(2026, 5, 7)
    out = Mixin._parse_availability_operation(["today", "LOOKING"], now)
    assert out == (now, "SET", "LOOKING")


def test_parse_op_date_then_remove():
    """`<date> remove` → (date, "REMOVE", None)."""
    now = dt_date(2026, 5, 7)
    out = Mixin._parse_availability_operation(["tomorrow", "remove"], now)
    assert out == (dt_date(2026, 5, 8), "REMOVE", None)


def test_parse_op_remove_then_date():
    """`<remove> <date>` (operation-first) → (date, "REMOVE", None).
    Pin so users can type either order."""
    now = dt_date(2026, 5, 7)
    out = Mixin._parse_availability_operation(["remove", "today"], now)
    assert out == (now, "REMOVE", None)


def test_parse_op_iso_date_then_multi_word_status():
    """Status that's multiple tokens (e.g., "not playing") joined by space."""
    now = dt_date(2026, 5, 7)
    out = Mixin._parse_availability_operation(
        ["2026-05-09", "not", "playing"], now
    )
    assert out == (dt_date(2026, 5, 9), "SET", "NOT_PLAYING")


def test_parse_op_too_few_args_returns_triple_none():
    """<2 args → (None, None, None)."""
    now = dt_date(2026, 5, 7)
    assert Mixin._parse_availability_operation([], now) == (None, None, None)
    assert Mixin._parse_availability_operation(["today"], now) == (None, None, None)


def test_parse_op_invalid_date_returns_triple_none():
    """First arg is unparseable as date AND not REMOVE → all None."""
    now = dt_date(2026, 5, 7)
    out = Mixin._parse_availability_operation(["garbage", "LOOKING"], now)
    assert out == (None, None, None)


def test_parse_op_invalid_status_returns_triple_none():
    """Date OK, status garbage → all None."""
    now = dt_date(2026, 5, 7)
    out = Mixin._parse_availability_operation(["today", "garbage"], now)
    assert out == (None, None, None)


def test_parse_op_remove_with_invalid_date_returns_none():
    """`remove <bad-date>` → all None (won't silently apply to today)."""
    now = dt_date(2026, 5, 7)
    out = Mixin._parse_availability_operation(["remove", "garbage"], now)
    assert out == (None, None, None)


# ---------------------------------------------------------------------------
# _format_external_usage
# ---------------------------------------------------------------------------


def test_format_usage_lists_canonical_commands():
    """The usage text is what users see when they get a parse error.
    Pin the canonical command list so a refactor that drops e.g.
    `/today` doesn't leave the docs lying."""
    out = Mixin._format_external_usage()
    # Required commands documented
    assert "/avail" in out
    assert "/today" in out
    assert "/tomorrow" in out
    assert "/avail status" in out
    assert "remove" in out


def test_format_usage_shows_supported_status_values():
    """Every canonical status mentioned so the user can copy-paste."""
    out = Mixin._format_external_usage()
    assert "LOOKING" in out
    assert "AVAILABLE" in out
    assert "MAYBE" in out
    assert "NOT_PLAYING" in out


def test_format_usage_shows_supported_date_keywords():
    """today / tomorrow / ISO date all advertised."""
    out = Mixin._format_external_usage()
    assert "today" in out
    assert "tomorrow" in out
    assert "YYYY-MM-DD" in out
