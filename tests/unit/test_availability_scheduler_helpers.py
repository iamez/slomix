"""Tests for _AvailabilitySchedulerMixin pure helpers.

These statics power the daily-availability scheduler, quiet-hours gate,
and promotion-job dispatch in AvailabilityPollCog. A regression silently:

- `_decode_json_dict` returns a list when JSON parses to one → caller's
  `dict.get()` AttributeError mid-loop → reminder dispatch dies.
- `_decode_json_list` returns mixed-type entries → downstream type
  assumption (`item["guid"]`) crashes on a string sneak-through.
- `_normalize_name_for_match` ET color codes (^N) leak through →
  case/punctuation differences mean equal players don't match.
- `_is_time_in_quiet_window`: overnight wrap (23:00–08:00) inverted →
  quiet hours either always on or always off.
- `_is_time_in_quiet_window`: start==end → quiet ALWAYS (whole day),
  pin so a typo'd config doesn't silently disable mute entirely.
- `_coerce_campaign_date`: input has time component → fails to parse;
  pin SUBSTR(0:10) coercion so trailing time bits don't crash.
- `_promotion_event_key`: separator drift → ledger duplicate-event
  collisions or split-keys for the same campaign.
- `_is_reminder_due`: missing/malformed config → returns False
  (NEVER raises) — pin so a misconfig doesn't crash the scheduler loop.

Pin every static.
"""
from __future__ import annotations

from datetime import date as dt_date
from datetime import datetime, timezone
from datetime import time as dt_time

import pytest

from bot.cogs.availability_mixins.scheduler_mixin import _AvailabilitySchedulerMixin

# ---------------------------------------------------------------------------
# _decode_json_dict
# ---------------------------------------------------------------------------


def test_decode_json_dict_native_dict():
    """Native dict → returned as-is (no copy/serialize round-trip)."""
    src = {"start": "23:00", "end": "08:00"}
    assert _AvailabilitySchedulerMixin._decode_json_dict(src) is src


def test_decode_json_dict_parses_json_string():
    """JSON string → parsed dict."""
    out = _AvailabilitySchedulerMixin._decode_json_dict('{"a": 1}')
    assert out == {"a": 1}


def test_decode_json_dict_returns_empty_when_json_parses_to_list():
    """JSON parses to a list → return {} (NOT the list). Pin so caller's
    `out.get(...)` doesn't AttributeError on a list-shaped row."""
    out = _AvailabilitySchedulerMixin._decode_json_dict('[1, 2, 3]')
    assert out == {}


def test_decode_json_dict_returns_empty_for_invalid_json():
    """Malformed JSON → {} (no propagation)."""
    assert _AvailabilitySchedulerMixin._decode_json_dict("not-json") == {}


def test_decode_json_dict_returns_empty_for_none():
    """None / int / unrecognised → {} (defensive default)."""
    assert _AvailabilitySchedulerMixin._decode_json_dict(None) == {}
    assert _AvailabilitySchedulerMixin._decode_json_dict(42) == {}


# ---------------------------------------------------------------------------
# _decode_json_list — list-of-dicts contract
# ---------------------------------------------------------------------------


def test_decode_json_list_native_list_filters_non_dicts():
    """Mixed-type list → only dicts kept. Pin so a string sneak-through
    (legacy schema) doesn't crash a downstream `item["guid"]`."""
    src = [{"guid": "x"}, "garbage", 42, {"guid": "y"}]
    out = _AvailabilitySchedulerMixin._decode_json_list(src)
    assert out == [{"guid": "x"}, {"guid": "y"}]


def test_decode_json_list_parses_json_string():
    out = _AvailabilitySchedulerMixin._decode_json_list('[{"x": 1}]')
    assert out == [{"x": 1}]


def test_decode_json_list_returns_empty_when_json_is_dict():
    """JSON parses to dict (NOT list) → return []. Pin defensive default."""
    out = _AvailabilitySchedulerMixin._decode_json_list('{"a": 1}')
    assert out == []


def test_decode_json_list_invalid_json_returns_empty():
    assert _AvailabilitySchedulerMixin._decode_json_list("xyz") == []


def test_decode_json_list_none_returns_empty():
    assert _AvailabilitySchedulerMixin._decode_json_list(None) == []


# ---------------------------------------------------------------------------
# _normalize_name_for_match — case/punct/ET-color stripping
# ---------------------------------------------------------------------------


def test_normalize_name_strips_et_color_codes():
    """`^1`, `^7` etc. (ET color escapes) stripped. Pin so
    `^7Puran` and `Puran` match."""
    assert _AvailabilitySchedulerMixin._normalize_name_for_match("^7Puran") == "puran"


def test_normalize_name_lowercases():
    assert _AvailabilitySchedulerMixin._normalize_name_for_match("PURAN") == "puran"


def test_normalize_name_removes_non_alphanumeric():
    """Punctuation/spaces stripped → "p|uran" matches "p uran" matches "p_uran"."""
    assert _AvailabilitySchedulerMixin._normalize_name_for_match("p|uran") == "puran"
    assert _AvailabilitySchedulerMixin._normalize_name_for_match("p u_ran") == "puran"


def test_normalize_name_handles_none():
    """None → ''. Pin so a missing name doesn't crash regex on `None`."""
    assert _AvailabilitySchedulerMixin._normalize_name_for_match(None) == ""


def test_normalize_name_handles_empty_and_whitespace():
    assert _AvailabilitySchedulerMixin._normalize_name_for_match("") == ""
    assert _AvailabilitySchedulerMixin._normalize_name_for_match("   ") == ""


def test_normalize_name_unicode_passes_through_punct_only():
    """Unicode letters NOT in [a-z0-9] are stripped (current contract).
    Pin observed behaviour so a non-ASCII alias matching scheme is
    deliberately broken-or-fixed by caller, not silently changed here."""
    out = _AvailabilitySchedulerMixin._normalize_name_for_match("žaba")
    # `ž` and `a` are non-ASCII — stripped as non-[a-z0-9]
    assert out == "aba"  # only ASCII a/b/a survives


# ---------------------------------------------------------------------------
# _is_time_in_quiet_window — quiet hours math (incl. overnight wrap)
# ---------------------------------------------------------------------------


def test_quiet_window_start_equals_end_means_always_quiet():
    """start==end → always quiet (whole-day mute). Pin observed
    behaviour so a typo'd config doesn't silently disable mute."""
    out = _AvailabilitySchedulerMixin._is_time_in_quiet_window(
        dt_time(12, 0), dt_time(8, 0), dt_time(8, 0)
    )
    assert out is True


def test_quiet_window_normal_range_inside():
    """09:00 in [08:00, 12:00) → quiet."""
    out = _AvailabilitySchedulerMixin._is_time_in_quiet_window(
        dt_time(9, 0), dt_time(8, 0), dt_time(12, 0)
    )
    assert out is True


def test_quiet_window_normal_range_outside():
    """13:00 not in [08:00, 12:00) → not quiet."""
    out = _AvailabilitySchedulerMixin._is_time_in_quiet_window(
        dt_time(13, 0), dt_time(8, 0), dt_time(12, 0)
    )
    assert out is False


def test_quiet_window_at_start_inclusive():
    """Start boundary inclusive."""
    out = _AvailabilitySchedulerMixin._is_time_in_quiet_window(
        dt_time(8, 0), dt_time(8, 0), dt_time(12, 0)
    )
    assert out is True


def test_quiet_window_at_end_exclusive():
    """End boundary EXCLUSIVE — pin so a 12:00 reminder fires on a
    [08:00, 12:00) quiet window without being suppressed."""
    out = _AvailabilitySchedulerMixin._is_time_in_quiet_window(
        dt_time(12, 0), dt_time(8, 0), dt_time(12, 0)
    )
    assert out is False


def test_quiet_window_overnight_wraps_midnight():
    """[23:00, 08:00) → 02:00 is quiet (after midnight side)."""
    out = _AvailabilitySchedulerMixin._is_time_in_quiet_window(
        dt_time(2, 0), dt_time(23, 0), dt_time(8, 0)
    )
    assert out is True


def test_quiet_window_overnight_evening_side():
    """[23:00, 08:00) → 23:30 is quiet (evening side)."""
    out = _AvailabilitySchedulerMixin._is_time_in_quiet_window(
        dt_time(23, 30), dt_time(23, 0), dt_time(8, 0)
    )
    assert out is True


def test_quiet_window_overnight_outside():
    """[23:00, 08:00) → 12:00 is NOT quiet."""
    out = _AvailabilitySchedulerMixin._is_time_in_quiet_window(
        dt_time(12, 0), dt_time(23, 0), dt_time(8, 0)
    )
    assert out is False


# ---------------------------------------------------------------------------
# _coerce_campaign_date — DB row → date
# ---------------------------------------------------------------------------


def test_coerce_campaign_date_passes_through_date():
    d = dt_date(2026, 5, 7)
    assert _AvailabilitySchedulerMixin._coerce_campaign_date(d) is d


def test_coerce_campaign_date_parses_iso_string():
    out = _AvailabilitySchedulerMixin._coerce_campaign_date("2026-05-07")
    assert out == dt_date(2026, 5, 7)


def test_coerce_campaign_date_truncates_time_component():
    """Input with time bits (e.g., DB returns "2026-05-07T12:00:00") →
    truncated to first 10 chars and parsed. Pin so a TIMESTAMP column
    doesn't crash on conversion."""
    out = _AvailabilitySchedulerMixin._coerce_campaign_date("2026-05-07T12:00:00")
    assert out == dt_date(2026, 5, 7)


def test_coerce_campaign_date_raises_on_bad_input():
    """Garbage → ValueError (loud) — pin so a typo'd campaign row
    surfaces immediately instead of silently using today's date."""
    with pytest.raises(ValueError):
        _AvailabilitySchedulerMixin._coerce_campaign_date("not-a-date")


# ---------------------------------------------------------------------------
# _promotion_event_key
# ---------------------------------------------------------------------------


def test_promotion_event_key_format():
    """`PROMOTE:{phase}:{iso_date}` — pin format so a refactor doesn't
    split ledger entries from old vs new dispatch path."""
    out = _AvailabilitySchedulerMixin._promotion_event_key(
        campaign_date=dt_date(2026, 5, 7), phase="reminder"
    )
    assert out == "PROMOTE:reminder:2026-05-07"


def test_promotion_event_key_zero_pads_iso():
    """Single-digit month/day zero-padded (ISO 8601). Pin so
    "2026-1-5" never appears as a ledger key (would split duplicates)."""
    out = _AvailabilitySchedulerMixin._promotion_event_key(
        campaign_date=dt_date(2026, 1, 5), phase="checkin"
    )
    assert out == "PROMOTE:checkin:2026-01-05"


def test_promotion_event_key_distinguishes_phases():
    a = _AvailabilitySchedulerMixin._promotion_event_key(
        campaign_date=dt_date(2026, 5, 7), phase="phase-A"
    )
    b = _AvailabilitySchedulerMixin._promotion_event_key(
        campaign_date=dt_date(2026, 5, 7), phase="phase-B"
    )
    assert a != b


# ---------------------------------------------------------------------------
# _is_reminder_due — instance-method form (uses self.daily_reminder_time)
# ---------------------------------------------------------------------------


class _FakeMixin(_AvailabilitySchedulerMixin):
    """Just enough to invoke the instance helper."""
    def __init__(self, daily_reminder_time):
        self.daily_reminder_time = daily_reminder_time


def test_is_reminder_due_matches_exact_minute():
    """now == configured HH:MM → True."""
    m = _FakeMixin("18:30")
    out = m._is_reminder_due(datetime(2026, 5, 7, 18, 30, 15))
    assert out is True


def test_is_reminder_due_off_by_one_minute_returns_false():
    """One minute off → False (NOT a fuzzy match)."""
    m = _FakeMixin("18:30")
    assert m._is_reminder_due(datetime(2026, 5, 7, 18, 29, 0)) is False
    assert m._is_reminder_due(datetime(2026, 5, 7, 18, 31, 0)) is False


def test_is_reminder_due_returns_false_on_malformed_string_config():
    """Non-HH:MM strings → False via the (TypeError, ValueError) catch."""
    assert _FakeMixin("garbage")._is_reminder_due(datetime(2026, 5, 7, 12, 0)) is False
    assert _FakeMixin("12")._is_reminder_due(datetime(2026, 5, 7, 12, 0)) is False
    assert _FakeMixin("xx:yy")._is_reminder_due(datetime(2026, 5, 7, 12, 0)) is False


def test_is_reminder_due_none_config_raises_attribute_error():
    """OBSERVED BUG: production catches (TypeError, ValueError) but a
    `None` config calls `None.split()` first → AttributeError leaks
    out. Pin observed behaviour as a tripwire — a fix that broadens
    the except (or null-checks) would deliberately update this test.

    Real risk: a deploy that omits `daily_reminder_time` from config
    would crash the scheduler loop tick. Operators should always set
    a string value (even "00:00")."""
    with pytest.raises(AttributeError):
        _FakeMixin(None)._is_reminder_due(datetime(2026, 5, 7, 12, 0))


def test_is_reminder_due_handles_zero_padded_config():
    """`08:05` matches 08:05 (NOT requires `8:5`)."""
    m = _FakeMixin("08:05")
    assert m._is_reminder_due(datetime(2026, 5, 7, 8, 5)) is True


# ---------------------------------------------------------------------------
# _recipient_in_quiet_hours_now — integration of statics
# ---------------------------------------------------------------------------


class _Recipient(_AvailabilitySchedulerMixin):
    def __init__(self, tz_name="UTC"):
        self.promotion_timezone = tz_name
        self.timezone = None


def test_recipient_no_quiet_hours_returns_false():
    """No quiet_hours config → never quiet."""
    r = _Recipient()
    out = r._recipient_in_quiet_hours_now({})
    assert out is False


def test_recipient_invalid_time_format_returns_false():
    """Malformed HH:MM in config → not quiet (defensive). Pin so a
    bad row doesn't accidentally mute the user forever."""
    r = _Recipient()
    out = r._recipient_in_quiet_hours_now(
        {"quiet_hours": {"start": "25:00", "end": "08:00"}}
    )
    assert out is False


def test_recipient_partial_config_returns_false():
    """Only `start` set → not quiet. Pin so a half-saved profile
    doesn't accidentally enable mute."""
    r = _Recipient()
    out = r._recipient_in_quiet_hours_now(
        {"quiet_hours": {"start": "23:00"}}
    )
    assert out is False


def test_recipient_quiet_window_evaluates_in_utc_when_specified():
    """tz=UTC, quiet 23:00–08:00, now 02:00 UTC → quiet."""
    r = _Recipient(tz_name="UTC")
    out = r._recipient_in_quiet_hours_now(
        {"quiet_hours": {"start": "23:00", "end": "08:00"}, "timezone": "UTC"},
        now_utc=datetime(2026, 5, 7, 2, 0, tzinfo=timezone.utc),
    )
    assert out is True


def test_recipient_outside_quiet_window():
    """Same window but now is 12:00 → not quiet."""
    r = _Recipient(tz_name="UTC")
    out = r._recipient_in_quiet_hours_now(
        {"quiet_hours": {"start": "23:00", "end": "08:00"}, "timezone": "UTC"},
        now_utc=datetime(2026, 5, 7, 12, 0, tzinfo=timezone.utc),
    )
    assert out is False


# ---------------------------------------------------------------------------
# _run_scheduler_with_lock — advisory-lock gating (log-sweep remediation)
# ---------------------------------------------------------------------------
#
# The scheduler now runs its body inside `db_adapter.advisory_lock(...)`, an
# async CM yielding True when the lock is held. When NOT acquired (another
# instance owns it) the body must be skipped entirely; when acquired it runs.

from contextlib import asynccontextmanager  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402


def _scheduler_self(acquired: bool):
    @asynccontextmanager
    async def _lock(_key):
        yield acquired

    s = MagicMock()
    s.bot.db_adapter.advisory_lock = _lock
    s.scheduler_lock_key = 875211
    s.promotion_enabled = True
    s.last_daily_reminder_date = None
    s._is_reminder_due = MagicMock(return_value=False)
    s._send_daily_reminder = AsyncMock()
    s._check_session_ready = AsyncMock()
    s._process_promotion_jobs = AsyncMock()
    return s


@pytest.mark.asyncio
async def test_run_scheduler_skips_body_when_lock_not_acquired():
    """Lock held by another instance → body never runs (cross-instance guard)."""
    s = _scheduler_self(acquired=False)
    await _AvailabilitySchedulerMixin._run_scheduler_with_lock(
        s, datetime(2026, 5, 7, 9, 0, tzinfo=timezone.utc)
    )
    s._check_session_ready.assert_not_awaited()
    s._process_promotion_jobs.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_scheduler_runs_body_when_lock_acquired():
    """Lock acquired → session-ready check + promotion jobs run."""
    s = _scheduler_self(acquired=True)
    await _AvailabilitySchedulerMixin._run_scheduler_with_lock(
        s, datetime(2026, 5, 7, 9, 0, tzinfo=timezone.utc)
    )
    s._check_session_ready.assert_awaited_once()
    s._process_promotion_jobs.assert_awaited_once()
