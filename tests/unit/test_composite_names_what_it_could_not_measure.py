"""Regression: `/api/skill/composite` answered `status: "ok"` for a scope it
could not measure.

Four of the five composite metrics draw on the proximity tables, and **98 of
151 gaming sessions in this database have no proximity rows at all** —
`shot_fired` has been off on the game server since 2026-08-11, and the capture
only ever covered part of the history. For those sessions the endpoint
returned real players, real kill counts, and:

    ci   0.0 for every player      (clutch_kills / total_combat_kills, both
                                    from proximity_combat_position)
    kpi  0.0 for every player      (`else 0` when total_outcomes == 0 — the
                                    "no data" answer is literally written as
                                    a zero)
    tir  0.0 for every player      (crossfire + trades)
    sds  capped at 40.0            (avg_spawn_score is 60 % of the weight)

…under `status: "ok"`, with nothing on the wire to say which. Measured over a
random 24-session sample: proximity absent -> ci 18/18 all-zero, kpi 18/18,
tir 17/18, sds <= 40.0 for 124/124 players; proximity present -> none of the
five ever all-zero. So the zeros are the shape of a question nobody asked,
and a player who never got a clutch kill was indistinguishable from a session
nobody instrumented.

⭐ THE DESIGN POINT, and what most of this file tests: the flag is derived
from whether the SOURCE ROWS exist in scope, never from whether the scores
came out zero. Reading it off the zeros would be circular, and it would also
flag a fully measured session that genuinely had no clutch kills — which is a
real answer, not a missing one.
"""
import warnings

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

warnings.filterwarnings("ignore")

from website.backend import dependencies as deps  # noqa: E402
from website.backend.routers import skill_router  # noqa: E402

# One player row in the shape the composite query returns, 16 columns.
# Every proximity-derived input is non-zero, so the SCORES are non-zero too —
# which is what lets the tests below separate "measured" from "came out zero".
RICH_PLAYER = (
    "AAAA1111", "player", 100,   # guid, name, kills
    30, 20,                      # crossfire_kills, trade_kills
    10, 50,                      # gibbed, total_outcomes
    12, 40,                      # clutch_kills, total_combat_kills
    0.7,                         # avg_spawn_score
    60, 600,                     # denied_playtime, time_played_seconds
    0.55,                        # survival_rate
    0, 0,                        # focus_escapes, times_focused (always 0)
    0.3,                         # avg_time_dead_pct
)
# The same player with every proximity input at zero: real kills, no coverage.
POOR_PLAYER = (
    "AAAA1111", "player", 100,
    0, 0,
    0, 0,
    0, 0,
    0.0,
    60, 600,
    0.55,
    0, 0,
    0.3,
)

ALL_FOUR = ["ci", "kpi", "sds", "tir"]


class _ScriptedDb:
    """A database that answers by what the query asks for, not by call order."""

    def __init__(self, players, source_counts, latest_date="2026-08-27"):
        self.players = players
        self.source_counts = source_counts
        self.latest_date = latest_date

    async def fetch_all(self, query, params=None):
        return list(self.players)

    async def fetch_one(self, query, params=None):
        if "MAX(session_date)" in query:
            return (self.latest_date,)
        if "storytelling_kill_impact" in query:
            return tuple(self.source_counts)
        return None


def _client(db):
    app = FastAPI()
    app.include_router(skill_router.router, prefix="/api")
    app.dependency_overrides[deps.get_db] = lambda: db
    return TestClient(app, raise_server_exceptions=False)


def test_a_scope_with_no_proximity_rows_names_all_four_metrics():
    db = _ScriptedDb([POOR_PLAYER], source_counts=[0, 0, 0, 0, 0])
    body = _client(db).get("/api/skill/composite?gaming_session_id=98").json()
    assert body["coverage"]["unmeasured_metrics"] == ALL_FOUR, (
        "a session with no proximity coverage still claims to have measured "
        f"everything: {body['coverage']}")
    assert body["players"], "the players themselves must still be returned"


def test_a_fully_covered_scope_names_nothing():
    db = _ScriptedDb([RICH_PLAYER], source_counts=[1152, 163, 1182, 1182, 1182])
    body = _client(db).get("/api/skill/composite?gaming_session_id=137").json()
    assert body["coverage"]["unmeasured_metrics"] == [], (
        "a fully covered session is being reported as degraded — the flag "
        "would become noise and get ignored")


def test_zero_scores_with_sources_present_are_reported_as_measured():
    """⛔ THE ASSERTION THAT SEPARATES A REAL ZERO FROM A MISSING ONE.

    Sources produced rows; the player simply never got a clutch kill, never
    traded, never gibbed. Every score is 0.0 — and every one of them is a
    true answer. A flag read off the zeros would mislabel all four, which is
    worse than no flag: it would teach the UI to hide correct numbers.
    """
    db = _ScriptedDb([POOR_PLAYER], source_counts=[500, 500, 500, 500, 500])
    body = _client(db).get("/api/skill/composite?gaming_session_id=137").json()
    player = body["players"][0]
    assert (player["tir"], player["ci"], player["kpi"]) == (0.0, 0.0, 0.0), (
        "the fixture stopped producing the zeros this test is about")
    assert body["coverage"]["unmeasured_metrics"] == [], (
        "genuine zeros were reported as unmeasured — the flag is being read "
        f"off the scores instead of the sources: {body['coverage']}")


def test_a_metric_that_is_not_zero_is_still_flagged_when_its_source_is_empty():
    """The other direction, and the reason `sds` is in the list at all.

    SDS never reaches 0 without proximity — `avg_spawn_score * 60` drops out
    but `denied_pct * 40` survives, so it lands at or below 40.0 and looks
    like an ordinary low score. Only the source count knows that 60 % of its
    weight was never asked for.
    """
    db = _ScriptedDb([POOR_PLAYER], source_counts=[0, 0, 0, 0, 0])
    body = _client(db).get("/api/skill/composite?gaming_session_id=98").json()
    assert body["players"][0]["sds"] > 0.0, "fixture no longer exercises the case"
    assert "sds" in body["coverage"]["unmeasured_metrics"], (
        "a non-zero but half-measured metric passed as measured")


@pytest.mark.parametrize(
    ("counts", "expected"),
    [
        ([1, 0, 0, 0, 0], ["ci", "kpi", "sds"]),        # crossfire alone measures tir
        ([0, 1, 0, 0, 0], ["ci", "kpi", "sds"]),        # trades alone also measures tir
        ([0, 0, 1, 0, 0], ["kpi", "sds", "tir"]),
        ([0, 0, 0, 1, 0], ["ci", "sds", "tir"]),
        ([0, 0, 0, 0, 1], ["ci", "kpi", "tir"]),
    ],
)
def test_each_source_lifts_exactly_the_metrics_it_feeds(counts, expected):
    """Per metric, not per endpoint: partial coverage is the common case
    (9 of 151 sessions), and 'some proximity data exists' does not mean every
    metric was measured."""
    db = _ScriptedDb([POOR_PLAYER], source_counts=counts)
    body = _client(db).get("/api/skill/composite?gaming_session_id=1").json()
    assert body["coverage"]["unmeasured_metrics"] == expected, (
        f"source counts {counts} mapped to the wrong metrics")


def test_the_no_scope_answer_has_the_same_keys_as_every_other_answer():
    """⛔ Two shapes for one endpoint is the bug, restated.

    When there is no proximity data at all there is no default scope, and
    that path used to return a SHORTER object — no `coverage`, no `meta`. A
    caller reading `coverage.unmeasured_metrics` would get a KeyError on
    exactly the state where the answer matters most.
    """
    empty = _ScriptedDb([], source_counts=[0, 0, 0, 0, 0], latest_date=None)
    normal = _ScriptedDb([RICH_PLAYER], source_counts=[9, 9, 9, 9, 9])
    short = _client(empty).get("/api/skill/composite").json()
    full = _client(normal).get("/api/skill/composite").json()

    assert short["session_date"] is None, "fixture no longer takes the short path"
    assert set(short) == set(full), (
        f"the two answers differ in shape: only in short {set(short) - set(full)}, "
        f"only in full {set(full) - set(short)}")
    assert set(short["coverage"]) == set(full["coverage"])
    assert set(short["coverage"]["source_rows"]) == set(full["coverage"]["source_rows"])
    assert short["meta"]["metrics"] == full["meta"]["metrics"], (
        "the two paths carry different metric descriptions — one dict, two "
        "copies, and they will drift")
    assert short["coverage"]["unmeasured_metrics"] == ALL_FOUR


def test_cp_description_does_not_claim_a_measurement_that_is_a_constant():
    """`focus_escapes`/`times_focused` are selected as literal 0, so
    `focus_escape_rate` is 0.5 for every player in every session — a fixed 15
    of CP's 100 points. Measured: 158 of 158 sampled players carry 0/0. The
    only source in the database (`player_teamplay_stats`) is a 32-row
    LIFETIME aggregate with no round or session key, so it cannot answer a
    per-session question. The number stays; the claim about it does not.
    """
    cp = skill_router._COMPOSITE_METRIC_DESCRIPTIONS["cp"]
    assert "fixed 15 points" in cp, (
        f"CP is advertised without saying part of it is a constant: {cp!r}")


def test_the_checks_above_can_fail():
    """A control: the two fixtures must actually differ."""
    rich = _client(_ScriptedDb([RICH_PLAYER], [9, 9, 9, 9, 9])).get(
        "/api/skill/composite?gaming_session_id=1").json()["players"][0]
    poor = _client(_ScriptedDb([POOR_PLAYER], [0, 0, 0, 0, 0])).get(
        "/api/skill/composite?gaming_session_id=1").json()["players"][0]
    assert (rich["tir"], rich["ci"], rich["kpi"]) != (poor["tir"], poor["ci"], poor["kpi"]), (
        "both fixtures produce the same scores — the tests above would pass "
        "against a handler that ignores its inputs entirely")
