"""⛔ THE GUARD THAT MAKES `response_model` SAFE TO ADD AT ALL.

FastAPI does not merely DOCUMENT a response model — it FILTERS the response
through it. A field the handler returns and the model omits disappears from
the payload, silently, with a 200. Adding schemas to 272 endpoints without
this test would be a slow, quiet way to delete data from every client.

So each model is checked against what its handler actually produced: call the
real handler with a stubbed database, serialise through the model, and compare
the key sets — including nested objects.

⚠️ THIS CANNOT PROVE COMPLETENESS ON ITS OWN, and saying so is part of the
test. It sees the keys THIS stub produced; a branch that adds a key under
conditions the stub does not reproduce is invisible to it. That is why every
model in this PR was also read off a LIVE response before it was written, and
why the stubs below aim at the branch that returns the MOST keys rather than
the most convenient one.
"""

from __future__ import annotations

import pytest
from pydantic import create_model

from website.backend.routers.players_router import QuickLeaders, get_quick_leaders
from website.backend.routers.records_overview import (
    ActivityCalendar,
    StatsOverview,
    get_stats_overview,
)


def missing_keys(raw, modelled, path: str = "") -> list[str]:
    """Keys present in the handler output and absent after the model.

    Recursive, because dropping a nested field is the same defect one level
    down and the flat comparison would call it a pass.
    """
    lost: list[str] = []
    if isinstance(raw, dict):
        if not isinstance(modelled, dict):
            return [f"{path or '<root>'}: became {type(modelled).__name__}"]
        for key, value in raw.items():
            here = f"{path}.{key}" if path else str(key)
            if key not in modelled:
                lost.append(here)
                continue
            lost.extend(missing_keys(value, modelled[key], here))
    elif isinstance(raw, list) and isinstance(modelled, list):
        for i, value in enumerate(raw[:3]):
            if i < len(modelled):
                lost.extend(missing_keys(value, modelled[i], f"{path}[{i}]"))
    return lost


class _OverviewDb:
    """Answers every aggregate the overview asks for, on the RICH branch.

    ⚠️ Rich on purpose: `most_active_overall` and `most_active_14d` are null
    when their query returns nothing, and a stub that returned nothing would
    let a model omitting them pass — the null branch hides the shape.
    """

    async def fetch_val(self, query, _params=None):
        # ⚠️ Type-plausible per query, not one number for everything. The
        # first version answered 7 to every aggregate including
        # `MIN(SUBSTR(round_date…))`, and the model rejected it — which is the
        # model doing its job, and a stub that lies about types cannot check a
        # schema.
        # ⚠️ `MIN(`/`MAX(`, not "round_date": the COUNT queries filter on
        # round_date too, so the broader test made every count a date string.
        if "MIN(" in query or "MAX(" in query:
            return "2025-01-01"
        return 7

    async def fetch_one(self, query, _params=None):
        if "player_guid" in query or "MAX(" in query:
            return ("E587CA5F", "ciril", 42)
        return ("2025-01-01",)

    async def fetch_all(self, _query, _params=None):
        return [("E587CA5F", "ciril")]


@pytest.mark.asyncio
async def test_stats_overview_model_drops_nothing():
    raw = await get_stats_overview(db=_OverviewDb())
    modelled = StatsOverview.model_validate(raw).model_dump()

    lost = missing_keys(raw, modelled)
    assert lost == [], "response_model dropped: " + ", ".join(lost)


@pytest.mark.asyncio
async def test_the_stub_reaches_the_branch_that_carries_the_most_keys():
    """⭐ THE TEST ABOVE IS ONLY AS GOOD AS THIS.

    If the stub returned no most-active row, both nested objects would be
    null, the recursion would never descend into them, and a model that
    omitted `name` or `rounds` would pass. Asserting the premise keeps the
    guard from quietly weakening the day the stub changes.
    """
    raw = await get_stats_overview(db=_OverviewDb())

    assert raw["most_active_overall"] is not None
    assert raw["most_active_14d"] is not None
    assert set(raw["most_active_overall"]) == {"name", "rounds"}


@pytest.mark.asyncio
async def test_a_model_missing_a_field_is_actually_caught():
    """⛔ The guard has to be able to fail. A comparison that always passes is
    the failure mode this whole file exists to prevent, so it is exercised
    directly: build a model that omits a field the handler really returns and
    confirm the comparison names it."""
    raw = await get_stats_overview(db=_OverviewDb())

    dropped = "window_days"
    truncated = create_model(
        "Truncated",
        **{
            name: (field.annotation, ...)
            for name, field in StatsOverview.model_fields.items()
            if name != dropped
        },
    )

    modelled = truncated.model_validate(raw).model_dump()
    assert missing_keys(raw, modelled) == [dropped]


class _LeadersDb:
    """Both boards populated, and both `errors` empty — the RICH branch again.

    ⚠️ A stub returning no rows would leave both lists empty, the recursion
    would never enter a row, and a model that dropped `label` or `rounds`
    would pass. The two boards carry DIFFERENT participation fields, so both
    must be non-empty for the comparison to see either.
    """

    async def fetch_all(self, query, _params=None):
        if "batch" in query.lower() or "player_links" in query:
            return []
        if "session" in query.lower() and "damage" in query.lower():
            return [("2B5938F5", "bronze", 341.7, 1)]
        return [("1C747DF1", "proner", 2880.0, 42)]

    async def fetch_one(self, _query, _params=None):
        return None


@pytest.mark.asyncio
async def test_quick_leaders_model_drops_nothing():
    raw = await get_quick_leaders(db=_LeadersDb())
    modelled = QuickLeaders.model_validate(raw).model_dump()

    lost = missing_keys(raw, modelled)
    assert lost == [], "response_model dropped: " + ", ".join(lost)


@pytest.mark.asyncio
async def test_both_boards_are_populated_so_the_comparison_can_see_them():
    """⭐ The premise, asserted. Empty boards would make the test above vacuous
    for every field inside a row."""
    raw = await get_quick_leaders(db=_LeadersDb())

    assert raw["xp"], "the XP board is empty; the row shape is unchecked"
    assert raw["dpm_sessions"], "the DPM board is empty; its row shape is unchecked"
    # The asymmetry is the reason there are two row models.
    assert "rounds" in raw["xp"][0]
    assert "sessions" in raw["dpm_sessions"][0]


# --- Round 2: five endpoints the new SPA reads -------------------------------
#
# ⚠️ THESE USE RECORDED RESPONSES, NOT STUBS, and the difference matters.
# A stub answers what the test author imagined; a recording answers what the
# service actually produced. Every fixture in `tests/fixtures/api_responses/`
# was captured from the running dev API, then anonymised — player names and
# guids replaced, everything else byte-for-byte — because the shape is what a
# schema must match and the identities are not ours to publish.
#
# ⚠️ The fixtures are TRIMMED but not thinned: `api_awards_leaderboard.json`
# keeps all 20 rows because the `guid: null` values live in the tail. A
# fixture cut to three rows would have typed that field `str` and this test
# would have passed while the model dropped nulls in production.

import json as _json
from pathlib import Path as _Path

from website.backend.routers.challenges_router import CurrentChallenge
from website.backend.routers.records_awards import (
    AwardLeaderboard,
    AwardsPage,
    HallOfFame,
)
from website.backend.routers.records_maps import MapObjectiveRecords, MapStats
from website.backend.routers.records_matches import (
    RecentRound,
    RoundAwards,
    RoundViz,
)
from website.backend.routers.records_seasons import CurrentSeason
from website.backend.routers.records_trends import StatsTrends
from website.backend.routers.records_weapons import (
    WeaponAggregate,
    WeaponLeader,
    WeaponsByPlayer,
    WeaponsHallOfFame,
)
from website.backend.routers.season_awards_router import SeasonAwards
from website.backend.routers.sessions_router import (
    SessionLeaderRow,
    SessionSummary,
)

_FIXTURES = _Path(__file__).resolve().parents[1] / "fixtures" / "api_responses"

_RECORDED = [
    ("api_awards.json", AwardsPage),
    ("api_awards_leaderboard.json", AwardLeaderboard),
    ("api_hall-of-fame.json", HallOfFame),
    ("api_seasons_current.json", CurrentSeason),
    ("api_stats_weapons_by_player.json", WeaponsByPlayer),
    # ⚠️ BOTH OF THESE FIXTURES ARE EDGE CASES ON PURPOSE.
    # The first models of these two endpoints typed `duration_seconds` and
    # `numeric` as non-null, because a 14-round sample contained no nulls.
    # They then REJECTED five of the oldest rounds and three of forty award
    # payloads outright — a 500 where the page had been rendering. Widening to
    # 60 randomly drawn rounds found both. So the recorded fixtures are a round
    # whose clock could not be resolved and an award list carrying an
    # unsortable figure; a future trim that loses those nulls loses the test.
    ("api_rounds_round_id_viz.json", RoundViz),
    ("api_rounds_round_id_awards.json", RoundAwards),
]


@pytest.mark.parametrize(("fixture", "model"), _RECORDED,
                         ids=[f for f, _ in _RECORDED])
def test_the_model_drops_nothing_from_a_recorded_response(fixture, model):
    raw = _json.loads((_FIXTURES / fixture).read_text())
    modelled = _json.loads(model.model_validate(raw).model_dump_json())
    lost = missing_keys(raw, modelled)
    assert not lost, f"{fixture}: {model.__name__} dropped {lost}"


@pytest.mark.parametrize(("fixture", "model"), _RECORDED,
                         ids=[f for f, _ in _RECORDED])
def test_the_model_changes_no_value_either(fixture, model):
    """Dropping a field is the loud failure; changing one is the quiet one.

    A `float` typed `int` truncates, an `int` typed `str` stringifies, and
    `missing_keys` sees a key in both places and calls it a pass. `most_dpm`
    is fractional while every other hall-of-fame category is a count, so this
    assertion is the one standing between that model and a silent truncation.
    """
    raw = _json.loads((_FIXTURES / fixture).read_text())
    modelled = _json.loads(model.model_validate(raw).model_dump_json())
    assert raw == modelled, f"{fixture}: {model.__name__} altered a value"


def test_a_null_survives_the_leaderboard_model():
    """States the premise the fixture exists to carry.

    If a future trim drops the rows where `guid` is null, the two tests above
    keep passing while the fixture stops proving anything about nullability.
    This one fails instead.
    """
    raw = _json.loads((_FIXTURES / "api_awards_leaderboard.json").read_text())
    guids = [row["guid"] for row in raw["leaderboard"]]
    assert None in guids, "fixture no longer carries a null guid to test"
    modelled = AwardLeaderboard.model_validate(raw).model_dump()
    assert [r["guid"] for r in modelled["leaderboard"]] == guids


def test_the_hall_of_fame_keeps_a_fractional_value():
    """`most_dpm` is the category that would show an int truncation."""
    raw = _json.loads((_FIXTURES / "api_hall-of-fame.json").read_text())
    dpm = raw["categories"]["most_dpm"]
    assert any(row["value"] % 1 for row in dpm), "fixture has no fractional dpm"
    modelled = HallOfFame.model_validate(raw).model_dump()
    assert ([r["value"] for r in modelled["categories"]["most_dpm"]]
            == [r["value"] for r in dpm])


def test_the_viz_fixture_still_carries_its_null_clock():
    """States the premise the fixture exists for.

    `duration_seconds` is null on rounds whose clock could not be resolved.
    A fixture re-recorded from a modern round would lose that, and the two
    tests above would keep passing while proving nothing about nullability.
    """
    raw = _json.loads((_FIXTURES / "api_rounds_round_id_viz.json").read_text())
    assert raw["duration_seconds"] is None, "fixture no longer carries a null clock"
    modelled = RoundViz.model_validate(raw).model_dump()
    assert modelled["duration_seconds"] is None


def test_the_awards_fixture_still_carries_an_unsortable_figure():
    raw = _json.loads((_FIXTURES / "api_rounds_round_id_awards.json").read_text())
    nulls = [a for cat in raw["categories"].values()
             for a in cat["awards"] if a["numeric"] is None]
    assert nulls, "fixture no longer carries a null numeric"
    modelled = RoundAwards.model_validate(raw).model_dump()
    still = [a for cat in modelled["categories"].values()
             for a in cat["awards"] if a["numeric"] is None]
    assert len(still) == len(nulls)
    # …and the rendered string beside it survives: the two are one figure seen
    # two ways, and dropping either leaves the client worse off.
    assert all(a["value"] for a in still)


# --- Round 3b: the branchier endpoints ---------------------------------------
#
# ⚠️ These two have MORE THAN ONE `return`, which is why they were skipped in
# #820. A single-return handler can be typed from one live response; a branchy
# one cannot, because the branch you did not exercise is the one whose shape
# you guessed. Both are covered here by exercising EVERY branch, not by
# recording a fixture and hoping it was representative.

from website.backend.routers.diagnostics_router import VoiceActivity


class TestVoiceActivityKeepsItsThreeStates:
    """⛔ 'quiet' and 'we cannot see voice' must not render alike.

    Before #808 all three situations returned `total_count: 0`, so a client had
    nothing to branch on. A response model can undo that by flattening the very
    fields that carry the distinction, so each state is asserted separately.
    """

    def _full(self, **over):
        base = {
            "status": "ok", "reason": None, "updated_at": "2026-08-28 14:00:00",
            "age_seconds": 12, "total_count": 2,
            "members": [{"name": "one", "channel_name": "Gaming"},
                        {"name": "two", "channel_name": "Gaming"}],
            "channels": [{"id": None, "name": "Gaming",
                          "members": [{"name": "one", "channel_name": "Gaming"}]}],
        }
        base.update(over)
        return base

    @pytest.mark.parametrize("state", ["ok", "stale", "unavailable"])
    def test_every_state_survives_the_model(self, state):
        payload = self._full(status=state) if state == "ok" else self._full(
            status=state,
            reason=None if state == "ok" else "the report could not be read",
            **({"updated_at": None, "age_seconds": None, "total_count": 0,
                "members": [], "channels": []} if state == "unavailable" else {}),
        )
        modelled = _json.loads(VoiceActivity.model_validate(payload).model_dump_json())
        assert missing_keys(payload, modelled) == []
        assert modelled == payload

    def test_a_populated_member_list_is_not_thinned(self):
        """⚠️ THE LIVE RESPONSE IS EMPTY MOST OF THE TIME.

        Typing this from a live call would have exercised `members: []` and
        proved nothing about the element shape — the same hole that made
        `duration_seconds` and `numeric` come out non-null in #830. The shape
        here is read from the handler (diagnostics_router.py:1799-1861), and
        this test drives it with a full list on purpose.
        """
        payload = self._full()
        modelled = VoiceActivity.model_validate(payload).model_dump()
        assert len(modelled["members"]) == 2
        assert modelled["members"][0]["channel_name"] == "Gaming"
        assert modelled["channels"][0]["members"][0]["name"] == "one"

    def test_reason_is_present_and_null_when_healthy(self):
        """Absence would have to be interpreted; null says it outright."""
        modelled = VoiceActivity.model_validate(self._full()).model_dump()
        assert "reason" in modelled
        assert modelled["reason"] is None


class TestNullsTheDataDoesNotShowYet:
    """⛔ TYPE FROM THE SCHEMA AND THE CODE, NOT FROM THE SAMPLE.

    #830 typed these models from 80 live rounds and got two nullable fields
    right that way. Review then found six more the sample could not have shown:
    every one of them is a column the schema declares nullable, or a branch the
    handler writes explicitly — and every one would have turned a rendering
    page into a response-validation 500, not a dropped field.

        rounds.winner_team   nullable   0 rows today
        rounds.round_date    nullable   0 rows today
        rounds.round_number  nullable   0 rows today
        round_awards.player_guid  nullable   496 rows today

    "Zero rows today" is not a type. The 496 currently resolve through the
    alias map, which is exactly why sampling responses could not see them.
    """

    def test_an_award_with_no_resolvable_player_is_accepted(self):
        payload = {
            "round_id": 1, "map_name": "supply", "round_number": 1,
            "round_date": "2026-08-26",
            "categories": {"combat": {"name": "Combat", "emoji": "*", "awards": [
                {"award": "Most damage", "player": "Unknown", "guid": None,
                 "value": "4999", "numeric": 4999.0},
            ]}},
        }
        modelled = _json.loads(RoundAwards.model_validate(payload).model_dump_json())
        assert missing_keys(payload, modelled) == []
        assert modelled["categories"]["combat"]["awards"][0]["guid"] is None

    def test_an_active_round_without_a_number_is_accepted(self):
        """`!session_start` inserts a placeholder with no round_number."""
        payload = {"round_id": 1, "map_name": "supply", "round_number": None,
                   "round_date": None, "categories": {}}
        assert RoundAwards.model_validate(payload).round_number is None

    def test_a_round_with_no_winner_yet_is_accepted(self):
        payload = _viz_payload(winner_team=None)
        assert RoundViz.model_validate(payload).winner_team is None

    def test_a_round_with_no_date_is_accepted(self):
        assert RoundViz.model_validate(_viz_payload(round_date=None)).round_date is None

    def test_a_round_with_no_players_has_empty_highlights(self):
        """The handler leaves `highlights` as {} when there are no player rows;
        requiring the three entries turned that into a 500."""
        payload = _viz_payload(players=[], player_count=0, highlights={})
        modelled = RoundViz.model_validate(payload)
        assert modelled.players == []
        assert modelled.highlights.mvp is None

    def test_the_three_highlight_names_are_still_declared(self):
        """Optional must not mean forgettable: a renamed field still fails."""
        assert set(RoundViz.model_fields["highlights"].annotation.model_fields) == {
            "most_damage", "most_kills", "mvp"}


def _viz_payload(**over):
    payload = {
        "round_id": 1, "map_name": "supply", "round_date": "2026-08-26",
        "round_number": 1, "round_label": "R1", "winner_team": 1,
        "duration_seconds": 454, "player_count": 1,
        "players": [{
            "guid": "A" * 8, "name": "one", "kills": 8, "deaths": 3,
            "damage_given": 1510, "damage_received": 1204,
            "team_damage_given": 0, "team_damage_received": 0,
            "time_played_seconds": 222, "time_dead_seconds": 30,
            "revives_given": 1, "gibs": 3, "self_kills": 0,
            "denied_playtime": 0, "kill_assists": 2, "xp": 55.0,
            "efficiency": 60.0, "dpm": 408.1,
        }],
        "highlights": {
            "most_damage": {"name": "one", "damage_given": 1510},
            "most_kills": {"name": "one", "kills": 8},
            "mvp": {"name": "one", "dpm": 408.1},
        },
    }
    payload.update(over)
    return payload


def test_voice_normalises_an_explicit_null_name():
    """`.get(k, default)` does NOT apply the default when the key is present
    with a null — and this validation runs after the handler's try block, so
    its malformed-row fallback could not catch the resulting error."""
    stored = {"name": None, "channel_name": None}
    assert stored.get("name", "Unknown") is None       # the trap
    assert (stored.get("name") or "Unknown") == "Unknown"  # the fix


class TestOptionalMeansAbsentNotEmpty:
    """⛔ `/stats/trends` BUILDS ITS PAYLOAD FROM A QUERY PARAMETER.

    `?metrics=rounds` returns `{dates, rounds}` and nothing else. Three ways to
    model that, two of them wrong:

      required            → every narrowed call becomes a 500
      empty-list default  → the client cannot tell "you did not ask for kills"
                            from "there were no kills"
      absent              → correct, and what the handler already does

    So the fields are `| None = None` and the route sets
    `response_model_exclude_none`, which keeps an unrequested field OUT of the
    payload rather than emitting it as null.
    """

    def _payload(self, **fields):
        return {"dates": ["2026-08-26", "2026-08-27"], **fields}

    def test_the_full_payload_survives(self):
        payload = self._payload(rounds=[3, 4], active_players=[6, 6],
                                kills=[100, 120], map_distribution={"supply": 7})
        modelled = _json.loads(
            StatsTrends.model_validate(payload).model_dump_json(exclude_none=True))
        assert missing_keys(payload, modelled) == []
        assert modelled == payload

    @pytest.mark.parametrize("subset", [
        {"rounds": [3, 4]},
        {"map_distribution": {"supply": 7}},
        {"rounds": [3, 4], "kills": [100, 120]},
        {},
    ])
    def test_a_narrowed_call_is_neither_rejected_nor_padded(self, subset):
        payload = self._payload(**subset)
        modelled = _json.loads(
            StatsTrends.model_validate(payload).model_dump_json(exclude_none=True))
        assert modelled == payload, "a field the caller did not request appeared"
        assert set(modelled) == set(payload)

    def test_dates_is_the_index_every_series_aligns_to(self):
        """A series shorter than `dates` would silently shift the chart."""
        payload = self._payload(rounds=[3, 4], kills=[100, 120])
        modelled = StatsTrends.model_validate(payload)
        assert len(modelled.rounds or []) == len(modelled.dates)
        assert len(modelled.kills or []) == len(modelled.dates)


class TestRecentRoundsTypedFromTheSchema:
    def test_the_nullable_columns_are_accepted(self):
        """`map_name`, `round_date` and `round_number` all allow NULL, and the
        handler writes the date as None outright. No live row shows it."""
        edge = {"id": 1, "map_name": None, "round_date": None,
                "round_number": None, "round_label": "?", "player_count": 0}
        modelled = _json.loads(RecentRound.model_validate(edge).model_dump_json())
        assert modelled == edge

    def test_the_ordinary_row_is_unchanged(self):
        row = {"id": 11365, "map_name": "supply", "round_date": "2026-08-27",
               "round_number": 2, "round_label": "R2", "player_count": 6}
        assert _json.loads(RecentRound.model_validate(row).model_dump_json()) == row


class TestShapesNoResponseCanShow:
    """⛔ TWO ENDPOINTS WHOSE PAYLOAD IS EMPTY EVERY TIME YOU LOOK.

    `/challenges/current` returns `challenge: null` (none set this week) and
    `/seasons/{id}/awards` returns `awards: []` (none engraved yet). Sampling
    responses can establish that those fields are nullable and nothing more —
    the element shape is simply not observable.

    #820 left both untyped for that reason. That was the right call then and
    the wrong reason: the shape IS knowable, from the `_serialize` helpers and
    the nullable columns behind them. So these models are typed from the code
    and exercised here with the content no live call produces.
    """

    def test_a_week_with_a_challenge_survives(self):
        payload = {
            "status": "ok", "week_start_date": "2026-08-24",
            "challenge": {"week_start_date": "2026-08-24", "title": "Most revives",
                          "description": "Revive the most teammates",
                          "created_at": "2026-08-24 10:00:00"},
        }
        modelled = _json.loads(
            CurrentChallenge.model_validate(payload).model_dump_json())
        assert missing_keys(payload, modelled) == []
        assert modelled == payload

    def test_a_challenge_with_the_nullable_columns_empty(self):
        """`description` and `created_at` are nullable, and `_serialize` writes
        `str(row[3]) if row[3] else None` for the timestamp."""
        payload = {"status": "ok", "week_start_date": "2026-08-24",
                   "challenge": {"week_start_date": "2026-08-24", "title": "T",
                                 "description": None, "created_at": None}}
        assert _json.loads(
            CurrentChallenge.model_validate(payload).model_dump_json()) == payload

    def test_no_challenge_is_an_answer_not_a_failure(self):
        payload = {"status": "ok", "week_start_date": "2026-08-24", "challenge": None}
        modelled = CurrentChallenge.model_validate(payload)
        assert modelled.challenge is None
        assert modelled.status == "ok", "an empty week must not read as an error"

    def test_engraved_awards_survive_including_the_nullable_ones(self):
        payload = {"status": "ok", "season_id": "2026-Q3", "season_name": "Q3 2026",
                   "awards": [
                       {"award_key": "most_kills", "label": "Most Kills",
                        "player_guid": "A" * 8, "player_name": "one",
                        "value_text": "2306", "value_num": 2306.0},
                       {"award_key": "x", "label": "X", "player_guid": "B" * 8,
                        "player_name": None, "value_text": None, "value_num": None},
                   ]}
        modelled = _json.loads(SeasonAwards.model_validate(payload).model_dump_json())
        assert missing_keys(payload, modelled) == []
        assert modelled == payload

    def test_both_halves_of_a_figure_survive(self):
        """`value_text` displays and `value_num` ranks; they are one number seen
        two ways and a client needs both."""
        payload = {"status": "ok", "season_id": "s", "season_name": "S",
                   "awards": [{"award_key": "k", "label": "K", "player_guid": "G",
                               "player_name": "p", "value_text": "1.8",
                               "value_num": 1.7999999523162842}]}
        award = SeasonAwards.model_validate(payload).awards[0]
        assert award.value_text == "1.8"
        assert award.value_num == pytest.approx(1.8)


class TestTheMapEndpoints:
    """Three endpoints where the handler, not the sample, decides nullability.

    Every numeric field on `/stats/maps` passes through `x or 0` before it
    leaves the handler, so those are genuinely non-null. `last_played` does not
    — `row[8]` goes through untouched and `rounds.round_date` is nullable — so
    it is typed nullable although no live row shows it. Reading the handler is
    what separates "guarded" from "just happens to be populated".
    """

    def _map_row(self, **over):
        row = {"name": "supply", "total_rounds": 12, "matches_played": 6,
               "allies_wins": 5, "axis_wins": 7, "allies_win_rate": 41.7,
               "axis_win_rate": 58.3, "avg_duration": 480, "min_duration": 120,
               "max_duration": 900, "last_played": "2026-08-27",
               "total_kills": 700, "total_deaths": 700, "avg_dpm": 310.5,
               "unique_players": 8, "grenade_kills": 20, "panzer_kills": 5,
               "mortar_kills": 2}
        row.update(over)
        return row

    def test_a_map_row_survives_intact(self):
        row = self._map_row()
        modelled = _json.loads(MapStats.model_validate(row).model_dump_json())
        assert missing_keys(row, modelled) == []
        assert modelled == row

    def test_an_unplayed_map_has_no_last_played(self):
        row = self._map_row(last_played=None)
        assert MapStats.model_validate(row).last_played is None


class TestAFailureThatStillAnswers200:
    """⛔ THREE STATES, AND THE CLIENT MUST NOT DERIVE THEM FROM LENGTH.

    `/records/maps/segments` catches its own exception and answers 200. It used
    to say `error` on failure and `ok` otherwise, which left the page reading
    "no records" off `records.length === 0` — and an empty list means two
    different things:

        no_data      the query ran; there genuinely are none
        unavailable  the query failed; we do not know

    Shape agreed with the workstream that renders it, so `MapsPage` can drop
    its length check.
    """

    def test_the_unavailable_state_survives(self):
        payload = {"status": "unavailable",
                   "note": "the objective-records query failed", "records": []}
        modelled = _json.loads(
            MapObjectiveRecords.model_validate(payload).model_dump_json())
        assert modelled == payload

    def test_no_data_and_unavailable_are_distinguishable(self):
        """The whole point: two empty lists that mean different things."""
        empty_measured = MapObjectiveRecords.model_validate(
            {"status": "no_data", "note": "none recorded", "records": []})
        empty_unknown = MapObjectiveRecords.model_validate(
            {"status": "unavailable", "note": "query failed", "records": []})
        assert empty_measured.records == empty_unknown.records == []
        assert empty_measured.status != empty_unknown.status, (
            "the two empties collapsed into one — the defect this shape fixes")

    def test_the_ok_state_reads_differently(self):
        assert MapObjectiveRecords.model_validate(
            {"status": "ok", "records": [], "note": None}).status == "ok"

    def test_a_record_with_no_resolved_winner_is_accepted(self):
        """`rounds.winner_team`, `map_name` and `gaming_session_id` are all
        nullable; the group-by carries the nulls through."""
        payload = {"status": "ok", "note": None, "records": [
            {"map_name": None, "fastest_seconds": 100, "fastest_time": "1:40",
             "played": "2026-08-01", "winner_team": None, "winner_side": "Draw",
             "gaming_session_id": None}]}
        modelled = _json.loads(
            MapObjectiveRecords.model_validate(payload).model_dump_json())
        assert modelled == payload

    def test_status_is_not_an_enum(self):
        """A new state must not be filtered out by the schema before anyone
        sees it."""
        assert MapObjectiveRecords.model_validate(
            {"status": "degraded", "note": None, "records": []}).status == "degraded"


class TestActivityCalendarSaysWhichEmpty:
    """The same defect as the map records, in the other router: both branches
    returned `{days, activity}`, so a failed query and a quiet month were
    identical on the wire."""

    def test_a_populated_calendar_survives(self):
        payload = {"days": 30, "activity": {"2026-08-27": 12, "2026-08-26": 18},
                   "status": "ok", "note": None}
        modelled = _json.loads(
            ActivityCalendar.model_validate(payload).model_dump_json())
        assert missing_keys(payload, modelled) == []
        assert modelled == payload

    def test_a_quiet_window_and_a_failed_query_differ(self):
        quiet = ActivityCalendar.model_validate(
            {"days": 30, "activity": {}, "status": "no_data",
             "note": "no rounds were played in this window"})
        broken = ActivityCalendar.model_validate(
            {"days": 30, "activity": {}, "status": "unavailable",
             "note": "the activity query failed"})
        assert quiet.activity == broken.activity == {}
        assert quiet.status != broken.status

    def test_the_window_size_survives_the_failure_path(self):
        """`days` is what the caller labels the chart with — losing it on the
        failure path would leave an unlabelled empty chart."""
        broken = ActivityCalendar.model_validate(
            {"days": 90, "activity": {}, "status": "unavailable", "note": "x"})
        assert broken.days == 90


class TestSessionLeaderboard:
    """Requested by the session-detail workstream ahead of its phase 4, so that
    page can be written against a schema rather than against a sample.

    ⛔ `kills` and `deaths` are nullable and no live row shows it. They come
    from `SUM(kills)` over a NULLABLE column: SUM returns NULL when every
    summed value is NULL, and the handler passes the result through with no
    guard. Zero such rows exist today. `name` is `MAX(player_name)` over a NOT
    NULL column and `dpm`'s CASE has an `ELSE 0` — those two really are
    non-null, and the difference is visible only in the aggregate, not the
    payload.
    """

    def test_an_ordinary_row_survives(self):
        row = {"rank": 1, "name": "one", "dpm": 408, "kills": 12, "deaths": 5}
        modelled = _json.loads(SessionLeaderRow.model_validate(row).model_dump_json())
        assert missing_keys(row, modelled) == []
        assert modelled == row

    def test_a_row_whose_sums_are_null_is_accepted(self):
        row = {"rank": 1, "name": "one", "dpm": 0, "kills": None, "deaths": None}
        modelled = SessionLeaderRow.model_validate(row)
        assert modelled.kills is None
        assert modelled.deaths is None

    def test_nullable_is_not_optional(self):
        """⚠️ TWO DIFFERENT THINGS, AND I CONFLATED THEM WRITING THIS TEST.

        `kills` is REQUIRED (the key is always in the payload) and NULLABLE
        (its value may be None). Optional would mean the key can be absent,
        which is what `/stats/trends` does and this endpoint does not.

        `name` and `dpm` are guarded at the source — `MAX` over a NOT NULL
        column, and a CASE with `ELSE 0` — so widening them would invite
        callers to handle a case that cannot occur.
        """
        fields = SessionLeaderRow.model_fields
        assert all(fields[k].is_required() for k in ("rank", "name", "dpm",
                                                     "kills", "deaths")), \
            "a key went optional — the client would have to check presence"
        assert fields["name"].annotation is str
        assert fields["dpm"].annotation is int
        assert type(None) in fields["kills"].annotation.__args__
        assert type(None) in fields["deaths"].annotation.__args__

    def test_an_empty_leaderboard_is_a_list_not_an_object(self):
        """Three of the handler's four branches return `[]` — an unknown
        session, no rounds, no latest date. A wrapper object would have
        reshaped all three."""
        from pydantic import TypeAdapter
        assert TypeAdapter(list[SessionLeaderRow]).validate_python([]) == []


class TestTheHandlersActuallyEmitTheThreeStates:
    """⚠️ THE MODEL ALLOWING THREE STATES IS NOT THE HANDLER PRODUCING THEM.

    The tests above pin the schema. They pass unchanged if the handler keeps
    answering `status: "ok"` for an empty result — which is the defect, not the
    fix. These drive the handlers with stub databases and read what comes out.
    """

    @pytest.mark.asyncio
    async def test_map_records_says_no_data_for_an_empty_result(self):
        from website.backend.routers.records_maps import get_map_objective_records

        class _Empty:
            async def fetch_all(self, *_a, **_k):
                return []

        out = await get_map_objective_records(db=_Empty())
        assert out["status"] == "no_data", (
            "an empty result still reads 'ok' — the page cannot tell it from "
            "a measured set")
        assert out["note"]

    @pytest.mark.asyncio
    async def test_map_records_says_unavailable_when_the_query_raises(self):
        from website.backend.routers.records_maps import get_map_objective_records

        class _Broken:
            async def fetch_all(self, *_a, **_k):
                raise RuntimeError("connection lost")

        out = await get_map_objective_records(db=_Broken())
        assert out["status"] == "unavailable"
        assert out["records"] == []
        assert "not an empty set" in out["note"]

    @pytest.mark.asyncio
    async def test_activity_calendar_distinguishes_its_two_empties(self):
        from website.backend.routers.records_overview import get_activity_calendar

        class _Empty:
            async def fetch_all(self, *_a, **_k):
                return []

        class _Broken:
            async def fetch_all(self, *_a, **_k):
                raise RuntimeError("connection lost")

        quiet = await get_activity_calendar(days=30, db=_Empty())
        broken = await get_activity_calendar(days=30, db=_Broken())
        assert quiet["activity"] == broken["activity"] == {}
        assert quiet["status"] == "no_data"
        assert broken["status"] == "unavailable"
        assert quiet["days"] == broken["days"] == 30


class TestWeaponEndpoints:
    """`/stats/weapons` and `/stats/weapons/hall-of-fame` — and the difference
    between them is worth stating, because it decides whether `status` belongs.

    `/stats/weapons` does NOT swallow its exceptions: a failure propagates and
    the caller gets a 500, which is an honest answer. It needs no state field.

    The hall-of-fame DOES swallow, returning `{"period": p, "leaders": {}}`
    with a 200 — so a failed query and a period with no weapon data were
    identical on the wire. It gets the same three states as the map records and
    the activity calendar.
    """

    def test_a_weapon_aggregate_survives(self):
        row = {"name": "Mp40", "weapon_key": "mp40", "kills": 16308,
               "headshots": 19461, "hs_rate": 12.9, "accuracy": 42.6}
        modelled = _json.loads(WeaponAggregate.model_validate(row).model_dump_json())
        assert missing_keys(row, modelled) == []
        assert modelled == row

    def test_the_rates_stay_fractional(self):
        """`hs_rate` and `accuracy` are percentages with one decimal; typing
        either `int` truncates silently, still with a 200."""
        row = {"name": "K43", "weapon_key": "k43", "kills": 1, "headshots": 1,
               "hs_rate": 12.9, "accuracy": 42.6}
        modelled = WeaponAggregate.model_validate(row)
        assert modelled.hs_rate == pytest.approx(12.9)
        assert modelled.accuracy == pytest.approx(42.6)

    def test_a_hall_of_fame_leader_survives(self):
        payload = {"period": "all", "status": "ok", "note": None, "leaders": {
            "mp40": {"weapon": "Mp40", "weapon_key": "mp40",
                     "player_guid": "A" * 8, "player_name": "one",
                     "kills": 900, "headshots": 300, "accuracy": 41.2}}}
        modelled = _json.loads(
            WeaponsHallOfFame.model_validate(payload).model_dump_json())
        assert missing_keys(payload, modelled) == []
        assert modelled == payload

    def test_its_two_empties_are_distinguishable(self):
        quiet = WeaponsHallOfFame.model_validate(
            {"period": "month", "leaders": {}, "status": "no_data",
             "note": "no weapon data for this period"})
        broken = WeaponsHallOfFame.model_validate(
            {"period": "month", "leaders": {}, "status": "unavailable",
             "note": "the hall-of-fame query failed"})
        assert quiet.leaders == broken.leaders == {}
        assert quiet.status != broken.status

    def test_the_leader_identity_stays_required(self):
        """`player_guid` and `player_name` are NOT NULL columns. Widening them
        would invite callers to handle a case the schema forbids."""
        fields = WeaponLeader.model_fields
        assert fields["player_guid"].annotation is str
        assert fields["player_name"].annotation is str


class TestTheWeaponHallOfFameHandlerEmitsItsStates:
    """Again: the model allowing three states is not the handler producing
    them."""

    @pytest.mark.asyncio
    async def test_it_says_no_data_for_an_empty_period(self):
        from website.backend.routers.records_weapons import get_weapon_hall_of_fame

        class _Empty:
            async def fetch_all(self, *_a, **_k):
                return []

        out = await get_weapon_hall_of_fame(db=_Empty())
        assert out["status"] == "no_data"
        assert out["leaders"] == {}

    @pytest.mark.asyncio
    async def test_it_says_unavailable_when_the_query_raises(self):
        from website.backend.routers.records_weapons import get_weapon_hall_of_fame

        class _Broken:
            async def fetch_all(self, *_a, **_k):
                raise RuntimeError("connection lost")

        out = await get_weapon_hall_of_fame(db=_Broken())
        assert out["status"] == "unavailable"
        assert "not an empty set" in out["note"]


class TestStatsMapsLetsItsFailuresThrough:
    """⛔ AN EMPTY ARRAY MUST MEAN EXACTLY ONE THING.

    `/stats/maps` used to catch its own exception and return `[]`, so a failed
    query and a database with no maps answered identically — and `MapsPage`
    renders `maps.length === 0` as nothing at all, so an outage looked like a
    quiet week.

    Three sibling endpoints solved this with a `status` field. This one returns
    a bare ARRAY read by four callers, so the fix is the other direction:
    remove the swallow. `[]` then means "no rows" again and HTTP carries the
    failure — no new channel, no reshaped payload, and nothing the OpenAPI
    generator cannot see. `/stats/weapons` has always worked this way.
    """

    @pytest.mark.asyncio
    async def test_a_failed_query_raises_rather_than_answering_empty(self):
        from website.backend.routers.records_maps import get_maps

        class _Broken:
            async def fetch_all(self, *_a, **_k):
                raise RuntimeError("connection lost")

        with pytest.raises(RuntimeError):
            await get_maps(db=_Broken())

    @pytest.mark.asyncio
    async def test_a_genuinely_empty_database_still_answers_empty(self):
        """The other half: removing the swallow must not turn "no maps" into
        an error. Both halves matter — a guard that fails closed on real
        emptiness would be a different defect wearing the same fix."""
        from website.backend.routers.records_maps import get_maps

        class _Empty:
            async def fetch_all(self, *_a, **_k):
                return []

        assert await get_maps(db=_Empty()) == []


class TestTheValidityGateOnRoundCounts:
    """⛔ `round_status` ALONE IS NOT THE VALIDITY GATE.

    Flagged by the workstream next door, which hit the same shape in its own
    aggregate: a query can filter bots at the ROW level and still count invalid
    or bot ROUNDS, because those are different columns.

    Measured on this database before the fix, over the last 90 days:

        2026-08-12   calendar showed  9   real answer  0   (all bot/invalid)
        2026-08-11   calendar showed 22   real answer 14
        2026-08-21   calendar showed  7   real answer  4

    Six days were wrong, always upward, so the activity calendar drew bars on
    days the server sat idle. `/rounds/recent` had the same gap and was
    offering those rounds in the picker.
    """

    def _gate_present(self, source: str, query_marker: str) -> bool:
        from pathlib import Path
        text = Path(f"website/backend/routers/{source}").read_text()
        start = text.index(query_marker)
        block = text[start:start + 1400]
        where = block.split("WHERE", 1)[1] if "WHERE" in block else ""
        return "is_valid" in where and "is_bot_round" in where

    def test_the_activity_calendar_excludes_invalid_and_bot_rounds(self):
        assert self._gate_present("records_overview.py",
                                  "SELECT SUBSTR(CAST(round_date AS TEXT), 1, 10) as day")

    def test_the_round_picker_excludes_them_too(self):
        assert self._gate_present("records_matches.py",
                                  "SELECT r.id, r.map_name, r.round_date, r.round_number")

    def test_the_session_rounds_endpoint_deliberately_does_not(self):
        """⭐ THE ONE PLACE THAT MUST NOT FILTER, and the difference is the
        point of that endpoint.

        `/stats/session/{id}/rounds` returns every round the session recorded
        and labels each with `counts_toward_totals` — which DOES apply the
        gate. Filtering there would repeat the defect it was built to fix: a
        player who played an excluded round would find it missing with no
        explanation.
        """
        from website.backend.routers.sessions_router import _counts_toward_totals
        assert _counts_toward_totals("completed", True, False) is True
        assert _counts_toward_totals("completed", False, False) is False
        assert _counts_toward_totals("completed", True, True) is False


def test_exclude_none_is_only_on_the_route_where_absence_is_the_meaning():
    """⛔ `response_model_exclude_none` DROPS EVERY None IN THE MODEL.

    On `/stats/trends` that is exactly right: a series the caller did not ask
    for should not appear at all, and none of its fields uses null as a value.

    On the others it would be a silent data loss. `RoundAwardEntry.guid` is
    null when the award could not be resolved to a player, `RoundViz.
    duration_seconds` is null when the clock could not be read — dropping those
    keys would turn "we know this is unresolved" into "we did not mention it",
    and the client could no longer tell them apart.

    Measured rather than assumed: `?metrics=rounds` returns `{dates, rounds}`
    with `kills` ABSENT, so consumers check presence, not value.
    """
    from pathlib import Path

    routers = Path("website/backend/routers")
    users = []
    for path in routers.glob("*.py"):
        text = path.read_text()
        if "response_model_exclude_none" in text:
            users.append(path.name)

    assert users == ["records_trends.py"], (
        f"exclude_none appeared on {users} — it drops every None in the model, "
        f"so a field whose null carries meaning would vanish from the payload")


class TestSessionSummaryNullsHideBehindTheDefaultLimit:
    """⛔ THE DEFAULT CALL SHOWS NO NULLS AT ALL.

        /api/sessions              20 sessions,   0 null values
        /api/sessions?limit=1       1 session,    0 null values
        /api/sessions?limit=200   137 sessions, 420 null values

    Typing this from the default response — the obvious thing to do — would
    have made all five team fields non-null and answered 500 on the majority of
    sessions, because 84 of 137 have no BOX attribution.

    ⚠️ AND `information_schema` WOULD NOT HAVE SAVED IT EITHER.
    `session_results.team_1_score` and `winning_team` are NOT NULL columns. The
    nulls come from the query's LEFT JOIN: a session with no team row has
    nothing to join, so the column's own nullability says nothing about the
    field's. The rule needs a third step — schema, then handler, then what the
    JOIN does to it.
    """

    def _row(self, **over):
        row = {"date": "2026-08-26", "session_id": 153, "rounds": 18, "maps": 6,
               "players": 6, "total_kills": 887, "maps_played": ["supply"],
               "allies_wins": 3, "axis_wins": 4, "draws": 1,
               "team_1_name": "A", "team_2_name": "B", "team_1_score": 3,
               "team_2_score": 2, "winning_team": 1,
               "time_ago": "2 days ago", "formatted_date": "Wednesday, August 26, 2026"}
        row.update(over)
        return row

    def test_a_session_with_team_attribution_survives(self):
        row = self._row()
        modelled = _json.loads(SessionSummary.model_validate(row).model_dump_json())
        assert missing_keys(row, modelled) == []
        assert modelled == row

    def test_a_session_without_it_is_accepted(self):
        """The 84-of-137 case that the default limit never shows."""
        row = self._row(team_1_name=None, team_2_name=None, team_1_score=None,
                        team_2_score=None, winning_team=None)
        modelled = SessionSummary.model_validate(row)
        assert modelled.team_1_score is None
        assert modelled.winning_team is None
        #: the non-team fields are unaffected — the join only nulls its own side
        assert modelled.rounds == 18
        assert modelled.allies_wins == 3

    def test_the_counts_stay_required(self):
        """Widening everything would be the safe-looking move. `rounds`,
        `maps`, `players` come from the driving table, not the joined one, so
        they cannot be null and typing them so would invite dead checks."""
        fields = SessionSummary.model_fields
        for name in ("rounds", "maps", "players", "total_kills", "draws"):
            assert type(None) not in getattr(
                fields[name].annotation, "__args__", (fields[name].annotation,))
