"""`/api/voice-activity/current` must be able to say it cannot see voice.

⛔ THREE SITUATIONS RETURNED ONE PAYLOAD. Nobody in voice, no row written by
the bot, and a row that would not parse all produced `total_count: 0` with an
empty member list — so a page had nothing to branch on and "voice is quiet"
rendered identically to "we cannot see voice". The only distinguishing field
was an `error` key that appeared ONLY in the failure cases and whose value was
`None`, which reads as "no error" (Codex on PR #806, via Fable).

The endpoint is a plain async function taking a db, so these call it directly
rather than through the app — no client, no lifespan, no event loop of its own
beyond the one pytest-asyncio provides.
"""

from __future__ import annotations

import datetime as dt
import json

import pytest

from website.backend.routers.diagnostics_router import get_current_voice_activity


class _Db:
    """Answers one query with whatever the test wants back."""

    def __init__(self, row=None, raises: Exception | None = None):
        self._row = row
        self._raises = raises

    async def fetch_one(self, _query, _params=None):
        if self._raises is not None:
            raise self._raises
        return self._row


def _status(members):
    return {"channel_name": "Gaming", "members": [{"name": n} for n in members]}


class TestAnEmptyChannelIsAnAnswer:
    @pytest.mark.asyncio
    async def test_nobody_in_voice_is_reported_as_ok(self):
        """⭐ The case the whole change turns on: zero is a MEASUREMENT here,
        and it must not wear the same clothes as a failure."""
        # ⚠️ A FRESH timestamp, computed rather than written down. A literal
        # date ages into staleness and the test starts failing on a day nobody
        # touched the code.
        fresh = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=5)
        db = _Db(row=(json.dumps(_status([])), fresh))
        payload = await get_current_voice_activity(db=db)

        assert payload["status"] == "ok"
        assert payload["total_count"] == 0
        assert payload["members"] == []
        assert payload["reason"] is None

    @pytest.mark.asyncio
    async def test_members_come_back_sanitised(self):
        fresh = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=5)
        db = _Db(row=(_status(["ciril", "jakazc"]), fresh))
        payload = await get_current_voice_activity(db=db)

        assert payload["status"] == "ok"
        assert [m["name"] for m in payload["members"]] == ["ciril", "jakazc"]
        assert all(set(m) == {"name", "channel_name"} for m in payload["members"])


class TestAFailureSaysSo:
    @pytest.mark.asyncio
    async def test_no_row_is_unavailable_not_an_empty_room(self):
        payload = await get_current_voice_activity(db=_Db(row=None))

        assert payload["status"] == "unavailable"
        assert "not published" in payload["reason"]
        assert payload["total_count"] == 0

    @pytest.mark.asyncio
    async def test_unparseable_status_is_unavailable_and_names_the_fault(self):
        db = _Db(row=("{not json", None))
        payload = await get_current_voice_activity(db=db)

        assert payload["status"] == "unavailable"
        assert "could not be read" in payload["reason"]
        assert "JSONDecodeError" in payload["reason"]

    @pytest.mark.asyncio
    async def test_the_two_failures_are_told_apart(self):
        """A missing row and a corrupt row need different fixes — one is the
        bot not writing, the other is what it wrote."""
        missing = await get_current_voice_activity(db=_Db(row=None))
        corrupt = await get_current_voice_activity(db=_Db(row=("{", None)))

        assert missing["reason"] != corrupt["reason"]


class TestTheReportCarriesItsAge:
    @pytest.mark.asyncio
    async def test_a_datetime_is_published_as_iso(self):
        stamp = dt.datetime(2026, 8, 25, 12, 34, 56)
        db = _Db(row=(_status(["ciril"]), stamp))
        payload = await get_current_voice_activity(db=db)

        assert payload["updated_at"] == stamp.isoformat()

    @pytest.mark.asyncio
    async def test_a_string_timestamp_does_not_turn_a_good_row_into_a_failure(self):
        """⚠️ PostgreSQL returns a datetime; the SQLite dev path returns a
        string. Calling `.isoformat()` on the string raises AttributeError —
        which the endpoint's own `except` catches, so a working row would have
        been reported as unavailable. A timestamp is not worth that."""
        db = _Db(row=(_status(["ciril"]), "2026-08-25 12:34:56"))
        payload = await get_current_voice_activity(db=db)

        assert payload["status"] == "ok"
        assert payload["updated_at"] == "2026-08-25 12:34:56"

    @pytest.mark.asyncio
    async def test_an_unavailable_report_has_no_age_to_give(self):
        payload = await get_current_voice_activity(db=_Db(row=None))
        assert payload["updated_at"] is None


class TestAReportThatStoppedIsNotARoomThatEmptied:
    """⛔ The bot writes every 30 s and its last row stays in the table.

    Nothing compared that row's age to anything, so when the bot stopped the
    member list was presented as current indefinitely — hours later, still
    "3 in voice" (Codex on PR #808).

    ⭐ The threshold is not chosen here. `monitor_tasks_mixin` writes on a
    `@tasks.loop(seconds=30)` and that same service refuses to act on its own
    status rows past 180 s; re-deriving a different number would give the
    system two opinions about one staleness.
    """

    def _row(self, age_s: float, tz_aware: bool = True):
        now = (dt.datetime.now(dt.timezone.utc) if tz_aware
               else dt.datetime.now(dt.timezone.utc).replace(tzinfo=None))
        return (_status(["ciril", "jakazc"]), now - dt.timedelta(seconds=age_s))

    @pytest.mark.asyncio
    async def test_a_fresh_report_is_ok(self):
        payload = await get_current_voice_activity(db=_Db(row=self._row(20)))
        assert payload["status"] == "ok"
        assert payload["total_count"] == 2
        assert payload["reason"] is None

    @pytest.mark.asyncio
    async def test_a_report_past_the_threshold_is_stale(self):
        payload = await get_current_voice_activity(db=_Db(row=self._row(3600)))

        assert payload["status"] == "stale"
        assert payload["age_seconds"] >= 3599
        assert "30 s" in payload["reason"]
        # ⭐ The members STAY. The page decides not to present them as
        # current; deleting them here would throw away the last thing we know.
        assert payload["total_count"] == 2

    @pytest.mark.asyncio
    async def test_stale_is_not_unavailable(self):
        """We read the row — that is a different fact from not reading it, and
        a different fix: the bot stopped, versus the row is unreadable."""
        stale = await get_current_voice_activity(db=_Db(row=self._row(3600)))
        gone = await get_current_voice_activity(db=_Db(row=None))

        assert stale["status"] != gone["status"]

    @pytest.mark.asyncio
    async def test_the_boundary_is_the_bots_own_number(self):
        from website.backend.routers.diagnostics_router import (
            VOICE_REPORT_STALE_AFTER_S,
        )
        assert VOICE_REPORT_STALE_AFTER_S == 180

        under = await get_current_voice_activity(
            db=_Db(row=self._row(VOICE_REPORT_STALE_AFTER_S - 10)))
        over = await get_current_voice_activity(
            db=_Db(row=self._row(VOICE_REPORT_STALE_AFTER_S + 10)))
        assert under["status"] == "ok"
        assert over["status"] == "stale"

    @pytest.mark.asyncio
    async def test_a_naive_timestamp_is_read_as_utc_not_as_an_error(self):
        """⚠️ Subtracting a naive datetime from an aware one raises
        TypeError, which the endpoint's own `except` would catch — turning a
        perfectly readable row into `unavailable`. The column the bot writes
        is UTC either way."""
        payload = await get_current_voice_activity(
            db=_Db(row=self._row(20, tz_aware=False)))

        assert payload["status"] == "ok"
        assert payload["age_seconds"] is not None

    @pytest.mark.asyncio
    async def test_an_undateable_report_is_not_presented_as_current(self):
        """⛔ TWO WAYS TO GET THIS WRONG, and the first version got the second.

        Zero would say "just written", which is the one thing an unparseable
        timestamp cannot support — so the age is None. But answering `ok`
        alongside it claims currency from a timestamp we could not read, which
        is the same failure with a different face: an undateable row could be
        from a minute ago or from March.

        `stale` here means READ BUT NOT ESTABLISHED AS CURRENT, which is what
        both the too-old case and this one have in common.
        """
        payload = await get_current_voice_activity(
            db=_Db(row=(_status(["ciril"]), "not a timestamp")))

        assert payload["age_seconds"] is None
        assert payload["status"] == "stale"
        assert "no usable timestamp" in payload["reason"]
        # The members still travel — the page decides not to present them.
        assert payload["total_count"] == 1

    @pytest.mark.asyncio
    async def test_a_missing_timestamp_is_treated_the_same_way(self):
        """`live_status.updated_at` is nullable (default `now()`, so NULL is
        unusual rather than impossible). A row with no timestamp cannot be
        dated either, and gets the same answer as one that cannot be parsed."""
        payload = await get_current_voice_activity(
            db=_Db(row=(_status(["ciril"]), None)))

        assert payload["status"] == "stale"
        assert payload["age_seconds"] is None
