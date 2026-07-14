"""Unit tests for betting auto-lifecycle (Faza B2).

Pure helpers plus FakeDB-driven coverage of maybe_open_market's decision logic
(live gating, existing-market no-op, two-team detection, roster vs legacy INSERT).
"""
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta

import pytest

from website.backend.routers.bets_router import SettleSkip, _roster_cols_cache
from website.backend.services.bets_lifecycle import (
    _coerce_date,
    _label_from_names,
    maybe_close_after_map1,
    maybe_open_market,
    maybe_settle_markets,
)


class FakeDB:
    """Minimal async DB stub that routes queries by content."""

    def __init__(self, *, latest_round=None, existing_market=None, teams_rows=None,
                 session_date_row=("2026-06-30",), roster_cols=2, insert_returns=(99,),
                 finalized=False, map1_round=None):
        self.latest_round = latest_round        # (gsid, round_start_unix) | None
        self.existing_market = existing_market   # (id,) | None
        self.teams_rows = teams_rows or []       # list of (team_name, guids, names)
        self.session_date_row = session_date_row
        self.roster_cols = roster_cols
        self.insert_returns = insert_returns
        self.finalized = finalized               # session_results row exists?
        self.map1_round = map1_round             # (round_start_unix, duration_s) | None
        self.inserts: list[tuple] = []

    async def fetch_one(self, query, params=()):
        q = query.lower()
        if "actual_duration_seconds" in q and "from rounds" in q:
            return self.map1_round  # _map1_closes_at probe (None -> fallback window)
        if "from rounds" in q and "order by round_start_unix" in q:
            return self.latest_round
        if "from session_results" in q:
            return (1,) if self.finalized else None
        if "select id from parimutuel_markets" in q:
            return self.existing_market
        if "max(round_date)" in q:
            return self.session_date_row
        if "information_schema.columns" in q:
            return (self.roster_cols,)
        if "insert into parimutuel_markets" in q:
            self.inserts.append((query, params))
            return self.insert_returns
        return None

    async def fetch_all(self, query, params=()):
        if "from session_teams" in query.lower():
            return self.teams_rows
        return []

    async def execute(self, query, params=()):
        return None

    @asynccontextmanager
    async def transaction(self):
        yield self


@pytest.fixture(autouse=True)
def _clear_roster_cache():
    # _has_roster_cols caches a positive result on the module; reset between tests
    # so the roster-cols vs legacy path is deterministic.
    _roster_cols_cache.clear()
    yield
    _roster_cols_cache.clear()


def _two_team_rows():
    return [
        ("Team A", '["42E142B3", "5D989160"]', '["immoo{", ".olz"]'),
        ("Team B", '["1EDBF300", "EDBB5DA9"]', '["KaNii", "vid"]'),
    ]


class TestMaybeOpenMarket:
    async def test_no_live_session(self):
        db = FakeDB(latest_round=None)
        assert await maybe_open_market(db, 5400) is None
        assert db.inserts == []

    async def test_stale_session_not_live(self):
        db = FakeDB(latest_round=(132, int(time.time()) - 10_000))
        assert await maybe_open_market(db, 5400) is None  # 10000s > 5400s window
        assert db.inserts == []

    async def test_existing_market_noop(self):
        db = FakeDB(latest_round=(132, int(time.time())), existing_market=(7,),
                    teams_rows=_two_team_rows())
        assert await maybe_open_market(db, 5400) is None
        assert db.inserts == []

    async def test_finalized_session_noop(self):
        # Result already recorded (session_results) — don't open a market nobody
        # can bet on, even if the session is still inside the live window.
        db = FakeDB(latest_round=(132, int(time.time())), existing_market=None,
                    teams_rows=_two_team_rows(), finalized=True)
        assert await maybe_open_market(db, 5400) is None
        assert db.inserts == []

    async def test_no_clean_two_teams(self):
        db = FakeDB(latest_round=(132, int(time.time())), existing_market=None,
                    teams_rows=[("Team A", "[]", "[]")])  # only one row
        assert await maybe_open_market(db, 5400) is None
        assert db.inserts == []

    async def test_happy_roster_path(self):
        db = FakeDB(latest_round=(132, int(time.time())), existing_market=None,
                    teams_rows=_two_team_rows(), roster_cols=2, insert_returns=(42,))
        mid = await maybe_open_market(db, 5400)
        assert mid == 42
        assert len(db.inserts) == 1
        sql, params = db.inserts[0]
        assert "team_a_guids" in sql and "team_b_guids" in sql
        # labels derived from player_names
        assert "immoo{, .olz" in params and "KaNii, vid" in params

    async def test_legacy_path_without_roster_cols(self):
        db = FakeDB(latest_round=(132, int(time.time())), existing_market=None,
                    teams_rows=_two_team_rows(), roster_cols=0, insert_returns=(43,))
        mid = await maybe_open_market(db, 5400)
        assert mid == 43
        assert len(db.inserts) == 1
        sql, _params = db.inserts[0]
        assert "team_a_guids" not in sql
        assert "closes_at" in sql  # cutoff set even on the legacy path

    async def test_closes_at_fallback_when_map1_incomplete(self, monkeypatch):
        # No completed map-1 R2 yet -> closes_at is a short window from now (§6.4b).
        # Clear the env override so the default (20 min) path is host-independent.
        monkeypatch.delenv("BETS_CLOSE_AFTER_MINUTES", raising=False)
        db = FakeDB(latest_round=(132, int(time.time())), existing_market=None,
                    teams_rows=_two_team_rows(), roster_cols=2, map1_round=None)
        assert await maybe_open_market(db, 5400) == 99
        sql, params = db.inserts[0]
        assert "closes_at" in sql
        closes_at = params[-2]  # ...team_b_guids, closes_at, gsid
        assert isinstance(closes_at, datetime)
        # fallback window is in the near future (default 20 min)
        assert timedelta(minutes=1) < (closes_at - datetime.now()) < timedelta(minutes=60)  # noqa: DTZ005

    async def test_skips_when_map1_cutoff_already_passed(self):
        # Map 1's R2 already finished when auto-open first sees the (still-live) session:
        # the §6.4b window has passed, so no market is opened at all — opening one with a
        # past closes_at would show as 'open' in the UIs but reject every bet (codex P2).
        start_unix = int(time.time()) - 1800  # map 1 started 30 min ago
        duration = 300                          # ...and ended 25 min ago -> cutoff passed
        db = FakeDB(latest_round=(132, int(time.time())), existing_market=None,
                    teams_rows=_two_team_rows(), roster_cols=2,
                    map1_round=(start_unix, duration))
        assert await maybe_open_market(db, 5400) is None
        assert db.inserts == []


class TestLabelFromNames:
    def test_list_of_names(self):
        assert _label_from_names(["immoo{", ".olz", "wiseBoy"], "Team A") == "immoo{, .olz, wiseBoy"

    def test_json_string_names(self):
        assert _label_from_names('["KaNii", "vid"]', "Team B") == "KaNii, vid"

    def test_empty_falls_back(self):
        assert _label_from_names([], "Team A") == "Team A"
        assert _label_from_names(None, "Team B") == "Team B"

    def test_blanks_filtered(self):
        assert _label_from_names(["  ", "vid", ""], "Team A") == "vid"

    def test_truncated_to_40(self):
        long = [f"player{i}" for i in range(20)]
        out = _label_from_names(long, "Team A")
        assert len(out) <= 40

    def test_fallback_also_truncated(self):
        assert len(_label_from_names([], "X" * 80)) == 40


class TestCoerceDate:
    def test_none(self):
        assert _coerce_date(None) is None

    def test_date_passthrough(self):
        d = date(2026, 6, 30)
        assert _coerce_date(d) is d

    def test_iso_string(self):
        assert _coerce_date("2026-06-30") == date(2026, 6, 30)

    def test_datetime_string_prefix(self):
        assert _coerce_date("2026-06-30 22:03:51") == date(2026, 6, 30)

    def test_garbage_returns_none(self):
        assert _coerce_date("not-a-date") is None


class _SettleFakeDB:
    """Stub for maybe_settle_markets: the scan returns (market_id, winning_team)
    rows. `markets` is a list of (id, winning_team) tuples; winning_team None means
    the session result isn't recorded yet."""

    def __init__(self, markets):
        self.markets = markets

    async def fetch_all(self, query, params=()):
        q = query.lower()
        if "from parimutuel_markets m" in q and "status in ('open', 'closed')" in q:
            return [(mid, wt) for (mid, wt) in self.markets]
        return []

    @asynccontextmanager
    async def transaction(self):
        yield self


class TestMaybeSettleMarkets:
    async def test_settles_each_open_finalized_market(self, monkeypatch):
        calls = []

        async def fake_settle(db, market_id, outcome_override=None):
            calls.append((market_id, outcome_override))
            return {"outcome": "team_a", "total_pool": 0, "bets": 0}

        monkeypatch.setattr(
            "website.backend.services.bets_lifecycle.settle_market_locked", fake_settle
        )
        n = await maybe_settle_markets(_SettleFakeDB([(10, 1), (11, 2)]))
        assert n == 2
        # decisive results auto-resolve (override None)
        assert calls == [(10, None), (11, None)]

    async def test_draw_settles_as_void(self, monkeypatch):
        calls = []

        async def fake_settle(db, market_id, outcome_override=None):
            calls.append((market_id, outcome_override))
            return {"outcome": "void", "total_pool": 0, "bets": 0}

        monkeypatch.setattr(
            "website.backend.services.bets_lifecycle.settle_market_locked", fake_settle
        )
        n = await maybe_settle_markets(_SettleFakeDB([(10, 0)]))
        assert n == 1
        assert calls == [(10, "void")]  # draw -> void/refund

    async def test_unrecorded_result_skipped(self):
        # winning_team None -> session result not in yet -> left open, not settled.
        assert await maybe_settle_markets(_SettleFakeDB([(10, None)])) == 0

    async def test_nothing_to_settle(self):
        assert await maybe_settle_markets(_SettleFakeDB([])) == 0

    async def test_skips_on_settleskip(self, monkeypatch):
        async def fake_settle(db, market_id, outcome_override=None):
            raise SettleSkip("already_settled", "already settled")

        monkeypatch.setattr(
            "website.backend.services.bets_lifecycle.settle_market_locked", fake_settle
        )
        # SettleSkip is swallowed per-market -> 0 settled, no raise.
        assert await maybe_settle_markets(_SettleFakeDB([(10, 1)])) == 0


class _CloseFakeDB:
    """Stub for maybe_close_after_map1: the scan returns auto-opened open markets as
    (id, gaming_session_id, closes_at); `map1_round` = (start_unix, duration) feeds
    _map1_closes_at (None = map 1 not finished). Captures the close UPDATE as
    (market_id, new_closes_at)."""

    def __init__(self, markets, map1_round=None):
        self.markets = markets
        self.map1_round = map1_round
        self.updates: list[tuple] = []

    async def fetch_all(self, query, params=()):
        q = query.lower()
        if "from parimutuel_markets" in q and "created_by_user_id is null" in q:
            return list(self.markets)
        return []

    async def fetch_one(self, query, params=()):
        q = query.lower()
        if "actual_duration_seconds" in q and "from rounds" in q:
            return self.map1_round
        return None

    async def execute(self, query, params=()):
        if "update parimutuel_markets set status = 'closed'" in query.lower():
            self.updates.append((params[1], params[0]))  # (market_id, new_closes_at)


class TestMaybeCloseAfterMap1:
    async def test_closes_market_when_map1_ended(self):
        # Fallback market still open; map 1 has since ended -> flip to closed and stamp
        # closes_at with the real end-of-map-1 (so UIs/place_bet stop treating it open).
        start_unix = int(time.time()) - 400
        duration = 300  # map-1 end = 100s ago
        future = datetime.now() + timedelta(minutes=10)  # noqa: DTZ005 - fallback still future
        db = _CloseFakeDB([(55, 132, future)], map1_round=(start_unix, duration))
        assert await maybe_close_after_map1(db) == 1
        assert db.updates == [(55, datetime.fromtimestamp(start_unix + duration))]  # noqa: DTZ006

    async def test_closes_market_when_fallback_window_elapsed(self):
        # Map 1 still unfinished (map1_round=None) but the fallback closes_at is already
        # in the past -> close so the UIs stop advertising an expired 'open' market.
        past = datetime.now() - timedelta(minutes=1)  # noqa: DTZ005 - fallback elapsed
        db = _CloseFakeDB([(55, 132, past)], map1_round=None)
        assert await maybe_close_after_map1(db) == 1
        assert db.updates == [(55, past)]  # keeps the (already-passed) fallback cutoff

    async def test_noop_when_map1_unfinished_and_window_future(self):
        # Map 1 unfinished and fallback still in the future -> leave the market open.
        future = datetime.now() + timedelta(minutes=10)  # noqa: DTZ005
        db = _CloseFakeDB([(55, 132, future)], map1_round=None)
        assert await maybe_close_after_map1(db) == 0
        assert db.updates == []

    async def test_nothing_open(self):
        assert await maybe_close_after_map1(_CloseFakeDB([])) == 0
