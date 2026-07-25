"""Narrative baseline cutoff must be the narrated session (Codex DATA-01).

Behavioural, not source-text: the tests drive
`generate_player_narratives` with a fake DB and intercept the value handed
to `trailing_averages`, so a refactor that preserves behaviour keeps
passing and a regression that reintroduces a date-derived cutoff fails.

Why it matters: the cutoff excludes the narrated session from the player's
own trailing average. Deriving it as MIN(gaming_session_id) over the
calendar date widened that exclusion whenever a date held two sessions —
narrating the later one also discarded the earlier one, which by then is
legitimate history.
"""
from __future__ import annotations

import pytest

from website.backend.services.session_scope import GamingSessionScope
from website.backend.services.storytelling import baseline as baseline_mod
from website.backend.services.storytelling.service import StorytellingService


class _FakeDB:
    """Returns nothing for every query. The narrative path tolerates empty
    inputs, which is all these tests need — they assert on the cutoff, not
    on narrative content."""

    def __init__(self):
        self.queries: list[str] = []

    async def fetch_all(self, query, params=None):
        self.queries.append(" ".join(str(query).split()))
        return []

    async def fetch_one(self, query, params=None):
        self.queries.append(" ".join(str(query).split()))
        return None

    async def execute(self, query, params=None):
        return None

    async def executemany(self, query, params_list):
        return None


def _scope(gsid: int, dates: tuple[str, ...] = ("2026-03-25",)) -> GamingSessionScope:
    return GamingSessionScope(
        gaming_session_id=gsid,
        dates=dates,
        round_keys=((1_700_000_000, "supply", 1),),
        accepted_round_count=1,
        distinct_map_names=("supply",),
    )


@pytest.fixture
def captured_cutoffs(monkeypatch):
    """Record the cutoff handed to trailing_averages.

    The metric computations are stubbed to yield ONE player, because with
    an empty fake DB `all_guids` is empty and trailing_averages is never
    called at all — which would make every cutoff assertion vacuously true.
    """
    seen: list[int | None] = []

    async def _spy(db, guid, *, before_session_id=None, n=10):
        seen.append(before_session_id)
        return {}

    monkeypatch.setattr(baseline_mod, "trailing_averages", _spy)

    one_player = {"players": [{
        "guid_short": "AAAA1111", "name": "alpha",
        "gravity_score": 1.0, "space_score": 1.0,
        "enabler_score": 1.0, "solo_pct": 1.0,
    }]}

    async def _metric(self, scope):
        return dict(one_player)

    for meth in ("compute_gravity", "compute_space_created",
                 "compute_enabler", "compute_lurker_profile"):
        monkeypatch.setattr(StorytellingService, meth, _metric, raising=True)
    return seen


@pytest.mark.asyncio
@pytest.mark.parametrize("gsid", [101, 102])
async def test_cutoff_is_the_narrated_session(captured_cutoffs, gsid):
    """Both sessions on a shared date must each exclude only themselves."""
    db = _FakeDB()
    await StorytellingService(db=db).generate_player_narratives(
        _scope(gsid), ensure_kis=False,
    )
    # non-vacuous: the stubbed metrics guarantee at least one player
    assert captured_cutoffs, "trailing_averages was never called"
    assert all(c == gsid for c in captured_cutoffs), captured_cutoffs


@pytest.mark.asyncio
async def test_cutoff_is_not_re_derived_from_the_date(captured_cutoffs):
    """The old implementation asked the DB for MIN(gaming_session_id) over
    round_date. That query must no longer be issued at all."""
    db = _FakeDB()
    await StorytellingService(db=db).generate_player_narratives(
        _scope(102), ensure_kis=False,
    )
    assert not any(
        "MIN(gaming_session_id)" in q and "round_date" in q for q in db.queries
    ), "baseline cutoff still re-derived from the calendar date"


@pytest.mark.asyncio
async def test_baseline_bound_is_strictly_exclusive_and_bound_as_a_value():
    """The cutoff only works if the bound EXCLUDES the narrated session.
    Asserting the parameter name would still pass if the SQL flipped to
    `<=`, dropped the predicate, or stopped binding the value — so this
    inspects the emitted SQL and its parameters instead."""
    captured: dict = {}

    class _SpyDB:
        async def fetch_all(self, query, params=None):
            captured["sql"] = " ".join(str(query).split())
            captured["params"] = tuple(params or ())
            return []

    await baseline_mod.trailing_averages(_SpyDB(), "AAAA1111", before_session_id=137)

    sql = captured["sql"]
    assert "r.gaming_session_id <" in sql, sql
    assert "r.gaming_session_id <=" not in sql, "bound must EXCLUDE the session"
    assert 137 in captured["params"], captured["params"]


@pytest.mark.asyncio
async def test_no_bound_means_no_predicate():
    """Without a cutoff the helper must not invent one — an accidental
    always-true or always-false predicate would silently empty or widen
    every baseline."""
    captured: dict = {}

    class _SpyDB:
        async def fetch_all(self, query, params=None):
            captured["sql"] = " ".join(str(query).split())
            return []

    await baseline_mod.trailing_averages(_SpyDB(), "AAAA1111")
    assert "gaming_session_id <" not in captured["sql"]
