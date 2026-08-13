"""Dead-hours-aware permanent-orphan cutoff (FINDINGS_FOR_CODEX 2026-08-11 §1).

The bug being locked out
------------------------
Three constants disagreed:

* ``bot/services/monitor_tasks_mixin.py`` — the stats importer sleeps
  during dead hours (02:00-11:00 CET): no ``rounds`` row can be created
  in that window on the SSH-poll path.
* ``bot/cogs/proximity_mixins/ingestion_mixin.py`` — proximity ingestion
  is NOT dead-hours gated (deliberately: telemetry should land live), so
  proximity rows arrive all night with no ``rounds`` parent.
* ``bot/cogs/proximity_mixins/relinker_mixin.py`` —
  ``_PERMANENT_ORPHAN_AGE_HOURS = 6`` (lowered 48h->6h in PR #369,
  2026-06-09, to stop retry/log churn) is SHORTER than the 9h dead
  window.

Deterministic consequence: every round played 02:00-05:00 CET became a
permanent orphan — its proximity rows aged past 6h *wall* hours before
the importer woke at 11:00 and wrote the ``rounds`` row the relinker
needs. Measured live 2026-08-11: 5 night-test rounds -> 8,810 dev
orphans, relinker ran 5x, linked 0.

The fix preserves PR #369's actual invariant — "a stats file that hasn't
landed after 6 hours is never coming" — by counting those 6 hours in
*importer-awake* time: hours inside the dead window don't count, because
the importer could not have landed anything then. ``awake_cutoff`` in
``bot/core/dead_hours.py`` computes the cutoff instant; both the
discovery SQL bound and the defensive per-row recheck use it.
"""
from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from bot.core.dead_hours import (
    DEAD_HOURS_END,
    DEAD_HOURS_START,
    DEAD_HOURS_TZNAME,
    awake_cutoff,
    is_dead_hour,
)

# All scenario datetimes use a fixed summer date (CEST, UTC+2) far from
# any DST transition so wall-clock arithmetic is unambiguous.
TZ = ZoneInfo(DEAD_HOURS_TZNAME)


def local(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 8, day, hour, minute, tzinfo=TZ)


class TestDeadHoursWindow:
    def test_window_constants_match_monitor(self):
        """The monitor's historical hardcoded window was 02:00-11:00."""
        assert DEAD_HOURS_START == 2
        assert DEAD_HOURS_END == 11

    def test_is_dead_hour_boundaries(self):
        assert not is_dead_hour(1)
        assert is_dead_hour(2)       # inclusive start
        assert is_dead_hour(10)
        assert not is_dead_hour(11)  # exclusive end
        assert not is_dead_hour(23)


class TestReproduction:
    """The exact scenario measured live on 2026-08-11."""

    def test_round_at_0300_healable_at_1105(self):
        """A 03:00 round must still be relinkable at 11:05.

        The importer wakes at 11:00 and writes the `rounds` row; the
        relinker's next 5-min cycle (~11:05) must not have written the
        round off. Under the old wall-clock rule the round was 8h05 old
        (> 6h) and was skipped forever.
        """
        round_dt = local(11, 3, 0)
        now = local(11, 11, 5)

        # Document the old bug: plain wall-clock aging DOES write it off.
        assert (now - round_dt) > timedelta(hours=6)

        cutoff = awake_cutoff(now, 6)
        assert cutoff < round_dt, (
            "round played during dead hours must remain eligible when "
            "the importer wakes"
        )

    def test_round_at_0300_permanent_only_after_six_awake_hours(self):
        """Awake time for a 03:00 round starts at 11:00 -> permanent at 17:00."""
        round_dt = local(11, 3, 0)
        # One minute before the 6-awake-hour mark: still eligible.
        assert awake_cutoff(local(11, 16, 59), 6) < round_dt
        # One minute after: permanent orphan, retries stop.
        assert awake_cutoff(local(11, 17, 1), 6) > round_dt

    def test_worst_case_retry_horizon_far_below_48h(self):
        """PR #369 lowered 48h->6h to stop 2-day retry churn.

        The dead-hours-aware rule must not reintroduce that: even the
        worst-placed round (02:00, start of the dead window) is written
        off at 17:00 the same day — a 15h wall-clock horizon.
        """
        round_dt = local(11, 2, 0)
        assert awake_cutoff(local(11, 17, 1), 6) > round_dt
        assert (local(11, 17, 1) - round_dt) < timedelta(hours=16)


class TestAwakeCutoffArithmetic:
    def test_no_dead_overlap_is_plain_wall_cutoff(self):
        """Evening evaluation: the last 6h contain no dead window."""
        now = local(11, 22, 0)
        assert awake_cutoff(now, 6) == local(11, 16, 0)

    def test_evaluation_inside_dead_window(self):
        """At 05:00 the awake hours are [00:00-02:00) today plus the
        previous evening -> cutoff lands at 20:00 the day before."""
        assert awake_cutoff(local(11, 5, 0), 6) == local(10, 20, 0)

    def test_evaluation_at_midnight(self):
        """At 00:00 all 6 awake hours come from the previous evening."""
        assert awake_cutoff(local(11, 0, 0), 6) == local(10, 18, 0)

    def test_cutoff_spanning_two_dead_windows(self):
        """20 awake hours from 12:00 back: 1h (11-12), skip dead, 2h
        (00-02), 13h (prev 11:00-24:00), skip dead, 4h more."""
        assert awake_cutoff(local(11, 12, 0), 20) == local(9, 22, 0)

    def test_returns_utc(self):
        cutoff = awake_cutoff(datetime(2026, 8, 11, 20, 0, tzinfo=timezone.utc), 6)
        assert cutoff.tzinfo is not None
        assert cutoff.utcoffset() == timedelta(0)

    def test_zero_hours_is_now(self):
        now = local(11, 22, 0)
        assert awake_cutoff(now, 0) == now

    def test_naive_now_rejected(self):
        with pytest.raises(ValueError):
            awake_cutoff(datetime(2026, 8, 11, 22, 0), 6)  # noqa: DTZ001 — intentionally naive to assert rejection

    def test_negative_hours_rejected(self):
        """Negative awake-hours has no meaning; silently returning `now`
        (the pre-guard behavior) could hide a broken caller computation."""
        with pytest.raises(ValueError):
            awake_cutoff(local(11, 22, 0), -1)


class TestCallSitesAligned:
    """Lock the alignment: both loops must consume the shared module.

    These are source-level contract checks — the point of the fix is a
    single source of truth for the dead-hours window, so a future edit
    that reverts either call site to a local constant must fail a test.
    """

    def test_relinker_uses_awake_cutoff(self):
        from bot.cogs.proximity_mixins import relinker_mixin

        src = inspect.getsource(
            relinker_mixin._ProximityRelinkerMixin._relink_null_round_ids  # noqa: SLF001 — contract test inspects the private call site on purpose
        )
        assert "awake_cutoff(" in src, (
            "relinker must derive the permanent-orphan cutoff from "
            "bot.core.dead_hours.awake_cutoff, not wall-clock age"
        )
        assert "timedelta(hours=_PERMANENT_ORPHAN_AGE_HOURS)" not in src

    def test_monitor_uses_shared_window(self):
        from bot.services import monitor_tasks_mixin

        src = inspect.getsource(monitor_tasks_mixin)
        assert "is_dead_hour(hour)" in src, (
            "monitor dead-hours gate must use the shared window from "
            "bot.core.dead_hours"
        )
        # The log message must render the constant, not a literal hour —
        # a bare `"DEAD_HOURS_END" in src` would pass on an unused import.
        assert "until {DEAD_HOURS_END:02d}:00" in src
        assert "2 <= hour < 11" not in src
        assert "until 11:00" not in src
