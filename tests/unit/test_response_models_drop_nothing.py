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

from website.backend.routers.availability import (
    AvailabilityDayAnonymous,
    AvailabilityDayViewer,
    AvailabilityDayViewerWithUsers,
    AvailabilityOverview,
    AvailabilityUser,
)
from website.backend.routers.challenges_router import CurrentChallenge
from website.backend.routers.diagnostics_router import (
    StorytellingCompleteness,
    SystemOverview,
)
from website.backend.routers.players_router import (
    LeaderboardRow,
    TonightIdle,
    TonightLive,
)
from website.backend.routers.proximity_positions import (
    PlayerAim,
    PlayerHeatmap,
    PlayerHeatmapKillsOnly,
    ProximityHitRegions,
    ProximityPlayers,
)
from website.backend.routers.proximity_scoring import (
    ProxFormula,
    ProxScores,
)
from website.backend.routers.records_awards import (
    AwardLeaderboard,
    AwardsPage,
    HallOfFame,
    StatsRecords,
)
from website.backend.routers.records_maps import MapObjectiveRecords, MapStats
from website.backend.routers.records_matches import (
    EmptyHighlights,
    RecentRound,
    RoundAwards,
    RoundViz,
    VizHighlights,
)
from website.backend.routers.records_seasons import (
    CurrentSeason,
    SeasonLeadersResponse,
    SeasonSummary,
)
from website.backend.routers.records_trends import StatsTrends
from website.backend.routers.records_weapons import (
    WeaponAggregate,
    WeaponLeader,
    WeaponsByPlayer,
    WeaponsHallOfFame,
)
from website.backend.routers.season_awards_router import SeasonAwards
from website.backend.routers.sessions_router import (
    LastSession,
    SessionLeaderRow,
    SessionSummary,
)
from website.backend.routers.uploads import (
    UploadDetail,
    UploadList,
    UploadListItem,
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

    def test_a_round_with_no_players_sends_an_empty_object(self):
        """The handler leaves `highlights` as `{}` when there are no player
        rows. Requiring the three entries turned that into a 500; making them
        OPTIONAL fixed the 500 and broke the payload instead, sending
        `{"most_damage": null, …}` where `{}` had been (Codex on #830). The
        union restores the shape, and this asserts the SERIALISED bytes rather
        than an attribute — the attribute is what hid the regression."""
        payload = _viz_payload(players=[], player_count=0, highlights={})
        modelled = RoundViz.model_validate(payload)
        assert modelled.players == []
        assert type(modelled.highlights) is EmptyHighlights
        assert _json.loads(modelled.model_dump_json())["highlights"] == {}

    def test_the_union_order_is_load_bearing_here(self):
        """⚠️ UNLIKE THE OTHER UNIONS ON THIS BRANCH, ORDER DECIDES THIS ONE.

        `VizHighlights` has three optional fields, so it also accepts `{}`;
        written first it wins and puts the three nulls back. Measured both
        ways before choosing. Pinned so a tidy-up that reorders the annotation
        fails here instead of in a payload nobody re-checks.
        """
        from pydantic import TypeAdapter

        annotation = RoundViz.model_fields["highlights"].annotation
        assert _json.loads(
            TypeAdapter(annotation).validate_python({}).model_dump_json()) == {}
        wrong_way = TypeAdapter(VizHighlights | EmptyHighlights)
        assert _json.loads(
            wrong_way.validate_python({}).model_dump_json()) != {}, (
            "VizHighlights no longer accepts {} — the ordering hazard this "
            "test guards against is gone, and so is the reason for the union")

    def test_the_three_highlight_names_are_still_declared(self):
        """Optional must not mean forgettable: a renamed field still fails."""
        assert set(VizHighlights.model_fields) == {
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

    ⛔ THIS GUARD USED TO GREP THE ROUTER FILES FOR THE STRING, AND THAT WAS
    WRONG. Deleting `response_model_exclude_none=True` from the `/stats/records`
    route left the phrase behind in the model's own docstring, so the grep still
    found the file and the guard still passed while the behaviour had changed:
    every absent category would have started arriving as `null`. A guard that
    reads PROSE can be satisfied by a comment. This one reads the ROUTE OBJECTS,
    which is the only thing FastAPI actually acts on.
    """
    import importlib
    from pathlib import Path

    from fastapi.routing import APIRoute

    users = {}
    for path in sorted(Path("website/backend/routers").glob("*.py")):
        if path.stem == "__init__":
            continue
        module = importlib.import_module(f"website.backend.routers.{path.stem}")
        router_obj = getattr(module, "router", None)
        if router_obj is None:
            continue
        for route in router_obj.routes:
            if isinstance(route, APIRoute) and route.response_model_exclude_none:
                users[route.path] = path.name

    assert sorted(users) == ["/stats/records", "/stats/trends"], (
        f"exclude_none appeared on {sorted(users)} — it drops every None in the "
        f"model, so a field whose null carries meaning would vanish from the "
        f"payload. Adding a file here means asserting that NONE of its "
        f"exclude_none model's fields uses null as a value.")

    # `records_awards.py` earns it the same way trends does, and the claim is
    # checked rather than asserted in prose: on `StatsRecords` every field is
    # `list[RecordEntry] | None`, where None means "the category key was never
    # in the dict". Nothing there uses null AS A VALUE, so dropping the Nones
    # loses no information — it is what reproduces the handler's own behaviour
    # of omitting a category that came back empty.
    from website.backend.routers.records_awards import RecordEntry, StatsRecords

    for name, field in StatsRecords.model_fields.items():
        assert field.annotation == (list[RecordEntry] | None), (
            f"StatsRecords.{name} is {field.annotation!r}, not "
            f"list[RecordEntry] | None. exclude_none is on this route: a field "
            f"whose null means anything other than 'key absent' would be "
            f"silently dropped from the response.")
        assert field.default is None, (
            f"StatsRecords.{name} must default to None so an unset category is "
            f"omitted rather than sent as null or []")

    # And the entries themselves carry no Nones at all, so exclude_none can
    # never reach inside a category and thin out a record.
    for name, field in RecordEntry.model_fields.items():
        assert type(None) not in getattr(field.annotation, "__args__", ()), (
            f"RecordEntry.{name} became nullable — under exclude_none that key "
            f"would vanish from a record instead of reading null")


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


class TestTheTwoFilteredBoards:
    """`/stats/leaderboard` and `/stats/records` — both take filters, and a
    filter is where a response_model mistake hides best.

    ⚠️ THE MUTATION THAT MOTIVATED THIS CLASS: deleting `deaths` from
    `LeaderboardRow` changed nothing anywhere in this file. 101 tests passed
    while the field silently vanished from every leaderboard payload — the
    exact failure this module is named after, on a model the module did not
    know about. Recording the fixtures is what gives it something to compare.

    Coverage of the filters is measured, not assumed: all 9 valid `stat` values
    × all 4 distinct `period` branches (`7d`, `30d`, `season`, and the
    else-branch all-time) = 635 rows, zero nulls in any field. `min_games` is
    accepted and then IGNORED — `having` is the empty string — so
    `min_games=1` and `min_games=999` return identical rows.
    """

    def _fixture(self, name):
        return _json.loads((_FIXTURES / name).read_text())

    def test_no_leaderboard_field_is_dropped_or_altered(self):
        rows = self._fixture("api_stats_leaderboard.json")
        assert len(rows) == 25, "fixture trimmed — it no longer covers a full page"
        for raw in rows:
            modelled = _json.loads(
                LeaderboardRow.model_validate(raw).model_dump_json())
            assert not missing_keys(raw, modelled), (
                f"LeaderboardRow dropped {missing_keys(raw, modelled)}")
            assert raw == modelled, "LeaderboardRow altered a value"

    def test_all_nineteen_record_categories_survive(self):
        raw = self._fixture("api_stats_records.json")
        assert len(raw) == 19, "fixture no longer holds every category"
        modelled = _json.loads(
            StatsRecords.model_validate(raw).model_dump_json(exclude_none=True))
        assert not missing_keys(raw, modelled), (
            f"StatsRecords dropped {missing_keys(raw, modelled)}")
        assert raw == modelled, "StatsRecords altered a value"

    def test_a_counting_record_stays_an_int_and_accuracy_stays_a_float(self):
        """`value: int | float`, not `float`. A bare `float` would rewrite
        `"value": 5994` as `"value": 5994.0` on every counting category —
        a wire change nobody would think to re-check."""
        raw = self._fixture("api_stats_records.json")
        modelled = StatsRecords.model_validate(raw)
        assert isinstance(modelled.damage[0].value, int)
        assert isinstance(modelled.accuracy[0].value, float)
        assert not isinstance(modelled.damage[0].value, bool)

    def test_a_map_with_no_records_is_an_empty_object_not_a_500(self):
        """⛔ THE REASON EVERY CATEGORY IS OPTIONAL.

        `?map_name=goldrush` — a real ET map this server has never recorded —
        answers `{}` with HTTP 200 and all 19 keys absent. One required field
        would turn that into a 500 on a filtered view, which is the hardest
        kind to notice. Recorded from the live endpoint, not constructed.
        """
        raw = self._fixture("api_stats_records_map_with_no_records.json")
        assert raw == {}
        modelled = _json.loads(
            StatsRecords.model_validate(raw).model_dump_json(exclude_none=True))
        assert modelled == {}, (
            f"an empty result grew keys: {modelled} — exclude_none is what "
            f"keeps 'category absent' distinguishable from 'category failed'")

    def test_the_records_route_still_carries_exclude_none(self):
        """The class above proves `{}` survives the MODEL. This proves the
        ROUTE still asks for it — without `exclude_none` the same response
        leaves as 19 nulls, and the absent/failed distinction is gone."""
        from fastapi.routing import APIRoute

        from website.backend.routers import records_awards

        route = next(r for r in records_awards.router.routes
                     if isinstance(r, APIRoute) and r.path == "/stats/records")
        assert route.response_model is StatsRecords
        assert route.response_model_exclude_none is True


class TestTheEndpointsWithoutFilters:
    """Three endpoints that take NO query parameters — and therefore look like
    they have only one shape. All three have several.

    ⭐ AN ENDPOINT WITHOUT FILTERS STILL HAS STATES; THEY LIVE IN THE DATA.
    You cannot reach them by varying a URL, so they were reached by pointing
    the season at a range with no rounds, and by making the session's team
    lookup come back empty. Both are recorded here as fixtures.
    """

    def _f(self, name):
        return _json.loads((_FIXTURES / name).read_text())

    def _roundtrip(self, model, raw, **dump):
        modelled = _json.loads(model.model_validate(raw).model_dump_json(**dump))
        assert not missing_keys(raw, modelled), (
            f"{model.__name__} dropped {missing_keys(raw, modelled)}")
        assert raw == modelled, f"{model.__name__} altered a value"
        return modelled

    def test_season_summary_survives_a_populated_season(self):
        self._roundtrip(SeasonSummary, self._f("api_seasons_current_summary.json"))

    def test_an_empty_season_keeps_its_null_map_and_its_integer_zero(self):
        """⛔ THE BRANCH NO URL CAN REACH. `top_map.name` is null and
        `avg_rounds_per_day` is the INT 0, not 0.0 — the handler's
        `if active_days else 0`. Typing that field `float` passes every test
        written against a populated season and rewrites the number on the one
        day of the year a season is empty."""
        raw = self._f("api_seasons_current_summary_empty.json")
        assert raw["top_map"]["name"] is None
        assert isinstance(raw["totals"]["avg_rounds_per_day"], int)
        modelled = SeasonSummary.model_validate(raw)
        assert modelled.top_map.name is None
        assert isinstance(modelled.totals.avg_rounds_per_day, int)
        self._roundtrip(SeasonSummary, raw)

    def test_season_leaders_survive_both_states(self):
        for name in ("api_seasons_current_leaders.json",
                     "api_seasons_current_leaders_empty.json"):
            self._roundtrip(SeasonLeadersResponse, self._f(name))

    def test_every_leader_key_is_present_even_when_every_value_is_null(self):
        """⭐ THE OPPOSITE OF StatsRecords, IN THE SAME RELEASE.

        `/stats/records` omits a category that has nothing; this endpoint keeps
        the key and nulls the value. A consumer cannot carry one habit across:
        here you check the VALUE, there you check PRESENCE. Pinned so that
        adding exclude_none to this route — which would look like tidying —
        fails loudly instead of erasing the distinction.
        """
        full = self._f("api_seasons_current_leaders.json")["leaders"]
        empty = self._f("api_seasons_current_leaders_empty.json")["leaders"]
        assert set(full) == set(empty), "the two states disagree on the key set"
        assert len(empty) == 13
        assert all(v is None for v in empty.values())
        assert all(v is not None for v in full.values()), (
            "the populated fixture lost a leader — it no longer proves the "
            "keys carry values in the other state")

    def test_last_session_survives_the_rich_scoring_shape(self):
        self._roundtrip(LastSession, self._f("api_stats_last-session.json"))

    def test_last_session_survives_the_two_key_scoring_shape(self):
        """⛔ ALL EIGHT SESSIONS IN THE CORPUS RETURN THE OTHER SHAPE.

        `scoring` is `{available, reason}` — two keys — whenever
        `build_session_scoring` takes one of its four early returns. No session
        day in the database does, so a model built from measurement alone makes
        `maps` and `team_a_name` required and answers 500 the first time one
        does. Typed as a UNION rather than one model with optional fields,
        because optional fields would put `"maps": null` on the wire for the
        common shape and `"reason": null` on the other — a payload change in
        both directions, verified byte-for-byte to be absent.
        """
        raw = self._f("api_stats_last-session_scoring_unavailable.json")
        assert set(raw["scoring"]) == {"available", "reason"}
        assert raw["scoring"]["available"] is False
        modelled = self._roundtrip(LastSession, raw)
        assert set(modelled["scoring"]) == {"available", "reason"}, (
            "the union leaked the other shape's fields onto the wire")
        assert raw["unassigned_players"], (
            "the fixture no longer carries unplaced players — it was the only "
            "recorded proof that unassigned_players and teams[].players share "
            "a shape")

    def test_unassigned_players_and_team_players_are_one_shape(self):
        """The handler appends the SAME dict to either list. One model serves
        both, and this is the evidence: same keys, same types."""
        short = self._f("api_stats_last-session_scoring_unavailable.json")
        rich = self._f("api_stats_last-session.json")
        unassigned = short["unassigned_players"][0]
        team_player = rich["teams"][0]["players"][0]
        assert set(unassigned) == set(team_player)
        assert len(unassigned) == 25
        assert {k: type(v).__name__ for k, v in unassigned.items()} == \
               {k: type(v).__name__ for k, v in team_player.items()}

    def test_the_three_lists_that_were_empty_in_every_sample(self):
        """`warnings`, `stats_checks` and `unassigned_players` are empty in all
        eight sampled sessions. An empty list tells you a field's NAME and
        nothing about its contents — these types came from the handler."""
        rich = self._f("api_stats_last-session.json")
        assert rich["warnings"] == []
        assert rich["stats_checks"] == []
        assert rich["unassigned_players"] == []
        modelled = LastSession.model_validate(rich)
        assert modelled.warnings == []
        assert modelled.unassigned_players == []


class TestTheStatesNoUrlCanReach:
    """`/stats/tonight`, `/system/overview` and
    `/diagnostics/storytelling-completeness` — three endpoints whose degraded
    and empty states are the ones worth typing for, and two of the three cannot
    be reached by varying a URL at all.
    """

    def _f(self, name):
        return _json.loads((_FIXTURES / name).read_text())

    def _roundtrip(self, model, raw):
        modelled = _json.loads(model.model_validate(raw).model_dump_json())
        assert not missing_keys(raw, modelled), (
            f"{model.__name__} dropped {missing_keys(raw, modelled)}")
        assert raw == modelled, f"{model.__name__} altered a value"
        return modelled

    # ---- /stats/tonight -------------------------------------------------

    def test_tonight_live_shape_survives(self):
        raw = self._f("api_stats_tonight_live.json")
        assert len(raw) == 12
        self._roundtrip(TonightLive, raw)

    def test_tonight_idle_shape_survives(self):
        raw = self._f("api_stats_tonight_idle.json")
        assert len(raw) == 9
        self._roundtrip(TonightIdle, raw)

    def test_sampling_tonight_today_returns_the_wrong_shape(self):
        """⛔ THE REVERSE OF THE last-session TRAP.

        The query is `WHERE captured_at::date = CURRENT_DATE`. On any day
        without a session — which is most days — the live response is the
        NINE-key idle shape, and the twelve-key one is the branch you cannot
        reach. Whichever shape you can see is not evidence about the other.
        """
        idle = self._f("api_stats_tonight_idle.json")
        live = self._f("api_stats_tonight_live.json")
        only_live = set(live) - set(idle)
        assert only_live == {"current_map", "last_update_unix", "age_seconds"}
        # …and the keys they SHARE do not share a type.
        assert idle["teams"] == {} and live["teams"] != {}
        assert idle["score"] == {} and live["score"] != {}
        assert idle["current"] is None and live["current"] is not None

    def test_the_union_picks_each_shape_without_padding_the_other(self):
        """A union rather than one model with optional fields: optional fields
        would put `"current_map": null` on the idle payload.

        ⛔ THIS TEST USED TO HAND-PICK THE MODEL and therefore never exercised
        the union at all. Loosening `TonightIdle.current` from `None` to
        `Any` — which destroys the discriminator, so an idle payload and a live
        payload both match the idle member — changed nothing and 108 tests
        passed. It must go through the SAME TypeAdapter FastAPI builds from the
        annotation, and it must assert WHICH member was chosen.
        """
        from pydantic import TypeAdapter

        adapter = TypeAdapter(TonightLive | TonightIdle)
        for fixture, expected_model, expected_keys in (
            ("api_stats_tonight_idle.json", TonightIdle, 9),
            ("api_stats_tonight_live.json", TonightLive, 12),
        ):
            raw = self._f(fixture)
            chosen = adapter.validate_python(raw)
            assert type(chosen) is expected_model, (
                f"{fixture} was matched by {type(chosen).__name__}, not "
                f"{expected_model.__name__} — the union no longer discriminates")
            out = _json.loads(chosen.model_dump_json())
            assert len(out) == expected_keys, f"{fixture} came back {len(out)} keys"
            assert out == raw, f"{fixture} changed passing through the union"

    def test_a_night_with_no_hold_curve_and_nothing_to_say_is_accepted(self):
        """⚠️ TYPED FROM THE CODE, UNPINNED BY ANY SAMPLE — so pinned here.

        `hold_probability` is `{…} if hold else None` and `director` is
        annotated `str | None` ("returns None before there is anything to
        say"). All four sampled nights had both, so no fixture carries the
        null. Making either field required passed every test that existed
        until this one: the fixtures cannot fail on a value they do not
        contain. This builds the case the corpus lacks instead.
        """
        raw = dict(self._f("api_stats_tonight_live.json"))
        raw["hold_probability"] = None
        raw["director"] = None
        out = _json.loads(TonightLive.model_validate(raw).model_dump_json())
        assert out["hold_probability"] is None
        assert out["director"] is None
        assert out == raw

    # ---- /system/overview -----------------------------------------------

    def test_system_overview_healthy_survives(self):
        self._roundtrip(SystemOverview, self._f("api_system_overview.json"))

    def test_linkage_unavailable_stays_a_single_key(self):
        """⛔ `{"available": false}` is ONE key. Typed as its own member of a
        union so the model cannot pad it with `"metrics": null`."""
        raw = self._f("api_system_overview_linkage_unavailable.json")
        assert raw["linkage"] == {"available": False}
        out = self._roundtrip(SystemOverview, raw)
        assert out["linkage"] == {"available": False}

    def test_partial_metrics_are_accepted_rather_than_rejected(self):
        """⚠️ THE STATE THAT ONLY HAPPENS WHEN THINGS ARE ALREADY BROKEN.

        The assessor fills `metrics` per query, so a failed subquery returns
        FEWER keys with `status: "error"`. The healthy path returns eleven.
        A model that pinned those eleven would answer 500 precisely when the
        page is needed most, which is why `metrics` is an open dict.
        """
        raw = self._f("api_system_overview_linkage_partial.json")
        assert raw["linkage"]["status"] == "error"
        assert len(raw["linkage"]["metrics"]) == 1
        healthy = self._f("api_system_overview.json")
        assert len(healthy["linkage"]["metrics"]) == 11
        self._roundtrip(SystemOverview, raw)

    # ---- /diagnostics/storytelling-completeness --------------------------

    @pytest.mark.parametrize("fixture", [
        "api_diagnostics_storytelling_completeness.json",
        "api_diagnostics_storytelling_completeness_no_data.json",
        "api_diagnostics_storytelling_completeness_degraded.json",
    ])
    def test_all_three_status_values_survive(self, fixture):
        raw = self._f(fixture)
        assert len(raw) == 20
        self._roundtrip(StorytellingCompleteness, raw)

    def test_the_three_states_are_actually_three(self):
        seen = {self._f(f)["status"] for f in (
            "api_diagnostics_storytelling_completeness.json",
            "api_diagnostics_storytelling_completeness_no_data.json",
            "api_diagnostics_storytelling_completeness_degraded.json")}
        assert seen == {"ok", "no_data", "degraded"}, (
            f"the fixtures no longer cover all three states: {seen}")

    def test_gaming_session_id_is_null_when_scoped_by_date(self):
        """The field a date-scoped sample would have typed `int`."""
        by_date = self._f("api_diagnostics_storytelling_completeness.json")
        by_gsid = self._f("api_diagnostics_storytelling_completeness_degraded.json")
        assert by_date["scope"] == "date"
        assert by_date["gaming_session_id"] is None
        assert by_gsid["scope"] == "gaming_session"
        assert by_gsid["gaming_session_id"] is not None

    def test_a_warning_here_is_an_object_not_a_string(self):
        """⚠️ `/stats/last-session` also has `warnings` and it is `list[str]`.
        Same field name, same site, different element type."""
        raw = self._f("api_diagnostics_storytelling_completeness_no_data.json")
        assert raw["warnings"], "the no_data fixture lost its warning"
        assert all(isinstance(w, dict) for w in raw["warnings"])
        assert set(raw["warnings"][0]) == {"level", "message"}
        last_session = _json.loads(
            (_FIXTURES / "api_stats_last-session.json").read_text())
        assert all(isinstance(w, str) for w in last_session["warnings"])

    def test_the_ratios_stay_float_on_the_empty_path(self):
        """`else 0.0`, not `else 0` — one character away from
        `SeasonTotals.avg_rounds_per_day`, which IS `int | float`."""
        raw = self._f("api_diagnostics_storytelling_completeness_no_data.json")
        for field in ("completeness_ratio", "linkage_ratio", "correlation_ratio"):
            assert raw[field] == 0.0
            assert isinstance(raw[field], float), f"{field} arrived as an int"
        empty_season = _json.loads(
            (_FIXTURES / "api_seasons_current_summary_empty.json").read_text())
        assert isinstance(empty_season["totals"]["avg_rounds_per_day"], int)


class TestAvailabilityWhereAbsentAndNullBothMeanSomething:
    """`/api/availability` — the one endpoint so far where NEITHER a nullable
    field nor `exclude_none` can express the contract, because absence and null
    are two different answers and both are given.

        anonymous          `my_status` ABSENT     — nobody asked the question
        logged in, unset   `my_status` null       — asked, and you set nothing
        logged in, set     `my_status` "LOOKING"  — asked, and here it is

    Measured over one range: 5 days carry a status, 50 are null, and all 55
    days of the anonymous response omit the key.
    """

    def _f(self, name):
        return _json.loads((_FIXTURES / name).read_text())

    def _roundtrip(self, raw):
        modelled = _json.loads(
            AvailabilityOverview.model_validate(raw).model_dump_json(by_alias=True))
        assert not missing_keys(raw, modelled), (
            f"AvailabilityOverview dropped {missing_keys(raw, modelled)}")
        assert raw == modelled, "AvailabilityOverview altered a value"
        return modelled

    @pytest.mark.parametrize("fixture", [
        "api_availability_anonymous.json",
        "api_availability_viewer.json",
        "api_availability_viewer_with_users.json",
    ])
    def test_every_viewer_state_survives(self, fixture):
        self._roundtrip(self._f(fixture))

    def test_the_three_states_of_my_status(self):
        anon = self._f("api_availability_anonymous.json")
        viewer = self._f("api_availability_viewer.json")
        assert all("my_status" not in d for d in anon["days"]), (
            "the anonymous fixture grew my_status — it no longer proves "
            "absence is a state")
        nulls = [d for d in viewer["days"] if d.get("my_status") is None]
        values = [d for d in viewer["days"] if d.get("my_status")]
        assert all("my_status" in d for d in viewer["days"])
        assert len(nulls) == 50 and len(values) == 5, (
            f"the viewer fixture no longer covers both: {len(nulls)} null, "
            f"{len(values)} set")

    def test_the_union_keeps_each_day_shape_exactly(self):
        """Each day payload comes back as its own shape, with every key.

        ⚠️ NOT because of the ordering, and not because of `extra="forbid"` —
        both of those were claimed as the mechanism and mutation refuted both:
        reversing the union, removing `forbid` from every member, and doing
        both at once all leave this test green. Pydantic's smart union picks
        the most specific member that validates. The next test pins that,
        because it is the thing the contract actually rests on.
        """
        from pydantic import TypeAdapter

        adapter = TypeAdapter(
            AvailabilityDayViewerWithUsers | AvailabilityDayViewer
            | AvailabilityDayAnonymous)
        cases = [
            ("api_availability_anonymous.json", AvailabilityDayAnonymous, 3),
            ("api_availability_viewer.json", AvailabilityDayViewer, 4),
            ("api_availability_viewer_with_users.json",
             AvailabilityDayViewerWithUsers, 5),
        ]
        for fixture, expected_model, keys in cases:
            day = self._f(fixture)["days"][0]
            chosen = adapter.validate_python(day)
            assert type(chosen) is expected_model, (
                f"{fixture} day matched {type(chosen).__name__}, not "
                f"{expected_model.__name__}")
            out = _json.loads(chosen.model_dump_json())
            assert len(out) == keys and out == day

    def test_include_users_is_silently_ignored_without_a_session(self):
        """⚠️ The API accepts `include_users=true` from an anonymous caller,
        answers 200, and omits the field — the handler gates it on
        `include_users and user_id is not None`. Recorded because a caller
        cannot tell "there were no users" from "you were not allowed to ask"."""
        anon = self._f("api_availability_anonymous.json")
        assert all("users_by_status" not in d for d in anon["days"])
        with_users = self._f("api_availability_viewer_with_users.json")
        populated = [d for d in with_users["days"]
                     if any(v for v in d["users_by_status"].values())]
        assert populated, "the fixture no longer carries a populated day"
        assert set(populated[0]["users_by_status"]) == {
            "LOOKING", "AVAILABLE", "MAYBE", "NOT_PLAYING"}
        # …and the users inside keep their shape. Without this the element
        # type could be widened to `Any` and nothing would notice.
        someone = next(u for v in populated[0]["users_by_status"].values()
                       for u in v)
        assert set(someone) == {"user_id", "display_name"}
        modelled = AvailabilityOverview.model_validate(with_users)
        day = next(d for d in modelled.days
                   if any(v for v in getattr(d, "users_by_status", {}).values()))
        entry = next(u for v in day.users_by_status.values() for u in v)
        assert isinstance(entry, AvailabilityUser)
        assert isinstance(entry.user_id, int)
        assert isinstance(entry.display_name, str)

    def test_what_the_day_union_actually_rests_on(self):
        """⭐ MEASURED, BECAUSE THE OBVIOUS EXPLANATIONS WERE BOTH WRONG.

        Smart-union selection is by specificity, not by declaration order, so
        the contract survives a reorder. Pinned so that a future switch to
        `Union[...]` in left-to-right mode — which WOULD make order matter —
        fails here instead of silently thinning a payload.
        """
        from pydantic import TypeAdapter

        reversed_order = TypeAdapter(
            AvailabilityDayAnonymous | AvailabilityDayViewer
            | AvailabilityDayViewerWithUsers)
        day = self._f("api_availability_viewer_with_users.json")["days"][0]
        chosen = reversed_order.validate_python(day)
        assert type(chosen) is AvailabilityDayViewerWithUsers, (
            "most-specific selection no longer holds: the union now depends on "
            "declaration order, and the members must be reordered to match")
        assert _json.loads(chosen.model_dump_json()) == day

    def test_the_from_alias_survives_the_model(self):
        """`from` is a Python keyword, so the field is `from_` with an alias.
        A model that forgot `by_alias` would rename the key in the payload."""
        raw = self._f("api_availability_anonymous.json")
        assert "from" in raw and "from_" not in raw
        assert "from" in self._roundtrip(raw)


def test_availability_viewer_authenticated_is_the_include_users_gate():
    """⭐ THE AMBIGUITY IS RESOLVABLE WITHOUT ADDING A FIELD, and this pins why.

    `users_by_status` is gated on `include_users and user_id is not None`, and
    `viewer.authenticated` is literally `user_id is not None` — the SAME
    expression. So a caller who sent the flag and did not get the field can
    read `viewer.authenticated` to learn which of the two reasons applies:
    "nobody was on any status" (true) or "you were not allowed to ask" (false).

    ⛔ This is a source-level assertion on purpose. The equivalence lives in
    two places in one handler, and a fixture cannot notice them drifting
    apart — it would just show a field missing, which is what it shows today.
    """
    import ast
    from pathlib import Path

    src = Path("website/backend/routers/availability.py").read_text()
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.AsyncFunctionDef)
              and n.name == "get_availability_range")

    gates = [ast.unparse(n) for n in ast.walk(fn)
             if isinstance(n, ast.BoolOp) and isinstance(n.op, ast.And)
             and any(isinstance(v, ast.Name) and v.id == "include_users"
                     for v in n.values)]
    # The gate is written TWICE — once to decide whether to run the roster
    # query, once to decide whether to attach the field to each day. Both must
    # say the same thing; a set comparison catches one of them drifting.
    assert gates, "the include_users gate disappeared"
    assert set(gates) == {"include_users and user_id is not None"}, (
        f"the include_users gate(s) changed to {sorted(set(gates))} — "
        f"`viewer.authenticated` may no longer tell a caller why the field "
        f"is missing")

    viewer_values = [ast.unparse(v)
                     for n in ast.walk(fn) if isinstance(n, ast.Dict)
                     for k, v in zip(n.keys, n.values)
                     if isinstance(k, ast.Constant) and k.value == "authenticated"]
    assert viewer_values == ["user_id is not None"], (
        f"viewer.authenticated is now {viewer_values}, which no longer matches "
        f"the include_users gate — consumers lose the only way to distinguish "
        f"'no users' from 'not allowed to ask'")


class TestUploadsWhereTheAnswerIsUnambiguous:
    """`/api/uploads` and `/api/uploads/{id}` — recorded partly as a NEGATIVE
    result, which is the kind that never gets written down.

    Neither of the two failure classes found elsewhere on this branch is
    present here: no query parameter is accepted and ignored (`sort=nonsense`
    and `category=nonexistent` answer 400, not a silent fallback), and
    visibility does not depend on the session, so an empty list means one
    thing. `offset=999` returns `items: []` with the honest `total: 2` rather
    than pretending the library is empty.
    """

    def _f(self, name):
        return _json.loads((_FIXTURES / name).read_text())

    def _roundtrip(self, model, raw):
        modelled = _json.loads(model.model_validate(raw).model_dump_json())
        assert not missing_keys(raw, modelled), (
            f"{model.__name__} dropped {missing_keys(raw, modelled)}")
        assert raw == modelled, f"{model.__name__} altered a value"
        return modelled

    @pytest.mark.parametrize("fixture", [
        "api_uploads_list.json",
        "api_uploads_list_empty.json",
        "api_uploads_list_offset_past_end.json",
    ])
    def test_the_list_survives_every_recorded_state(self, fixture):
        self._roundtrip(UploadList, self._f(fixture))

    def test_the_three_fields_that_are_null_in_every_live_row(self):
        """⚠️ NULLABLE, NOT OPTIONAL — the keys are present and the values are
        null. A required non-null type here is a 500 on the FIRST item, and
        the whole corpus would agree with the mistake."""
        items = self._f("api_uploads_list.json")["items"]
        assert items, "the fixture lost its items"
        for item in items:
            for field in ("description_preview", "expires_at"):
                assert field in item, f"{field} became optional"
                assert item[field] is None
        modelled = UploadList.model_validate(self._f("api_uploads_list.json"))
        assert all(i.description_preview is None for i in modelled.items)
        assert all(i.expires_at is None for i in modelled.items)

    def test_an_offset_past_the_end_still_reports_the_real_total(self):
        past = self._f("api_uploads_list_offset_past_end.json")
        assert past["items"] == [] and past["total"] > 0, (
            "the fixture no longer distinguishes 'past the end' from 'empty'")
        self._roundtrip(UploadList, past)

    def test_detail_survives_and_can_delete_is_the_only_session_field(self):
        """⭐ MEASURED AGAINST BOTH SESSIONS: the anonymous and owner payloads
        are identical except for `can_delete`. That is what makes it safe to
        say upload visibility is not auth-dependent — not the absence of a
        user clause in the query, which is only where I went looking."""
        anon = self._f("api_uploads_detail.json")
        owner = self._f("api_uploads_detail_owner.json")
        differing = {k for k in anon if anon[k] != owner.get(k)}
        assert differing == {"can_delete"}, (
            f"the two sessions now differ on {sorted(differing)} — visibility "
            f"may have become auth-dependent, and an empty library would then "
            f"have two meanings")
        assert anon["can_delete"] is False and owner["can_delete"] is True
        self._roundtrip(UploadDetail, anon)
        self._roundtrip(UploadDetail, owner)

    def test_description_and_description_preview_are_different_fields(self):
        """⚠️ The list sends `description_preview` (160 chars); the detail
        sends `description` (the whole text). A shared renderer that reads
        `description` off a list item finds nothing."""
        item = self._f("api_uploads_list.json")["items"][0]
        detail = self._f("api_uploads_detail.json")
        assert "description_preview" in item and "description" not in item
        assert "description" in detail and "description_preview" not in detail
        assert set(UploadListItem.model_fields) & {"description"} == set()
        assert set(UploadDetail.model_fields) & {"description_preview"} == set()

    def test_an_upload_that_actually_has_tags(self):
        """⛔ THE CORPUS HAS NO TAGGED UPLOAD, so `tags: list[str]` could be
        widened to `list[Any]` with every test still green — the third time on
        this branch that a fixture could not fail on a value it does not
        contain. Both recorded uploads carry `tags: []`, and an empty list
        proves nothing about its element type. Constructed here instead.
        """
        raw = dict(self._f("api_uploads_detail.json"))
        assert raw["tags"] == [], "the fixture grew tags; update this test"
        raw["tags"] = ["demo", "frag-movie"]
        modelled = UploadDetail.model_validate(raw)
        assert modelled.tags == ["demo", "frag-movie"]
        assert all(isinstance(t, str) for t in modelled.tags)
        # …and a non-string must be refused rather than carried through.
        broken = dict(raw)
        broken["tags"] = [{"tag": "demo"}]
        with pytest.raises(Exception):
            UploadDetail.model_validate(broken)


class TestProximityWhereTheScopeIsTheWholeStory:
    """The three endpoints the proximity page calls most (5, 3 and 3 times per
    render). Typed ahead of the frontend page so it is written against a schema
    rather than against a sample.
    """

    def _f(self, name):
        return _json.loads((_FIXTURES / name).read_text())

    def _roundtrip(self, model, raw):
        modelled = _json.loads(model.model_validate(raw).model_dump_json())
        assert not missing_keys(raw, modelled), (
            f"{model.__name__} dropped {missing_keys(raw, modelled)}")
        assert raw == modelled, f"{model.__name__} altered a value"
        return modelled

    def test_players_and_hit_regions_survive(self):
        self._roundtrip(ProximityPlayers, self._f("api_proximity_players.json"))
        self._roundtrip(ProximityPlayers,
                        self._f("api_proximity_players_empty.json"))
        self._roundtrip(ProximityHitRegions,
                        self._f("api_proximity_hit_regions.json"))

    def test_an_empty_scope_is_an_answer_not_an_error(self):
        empty = self._f("api_proximity_players_empty.json")
        assert empty["status"] == "ok" and empty["players"] == []
        assert empty["scope"]["session_date"] == "2020-01-01", (
            "the fixture no longer records WHICH scope came back empty — "
            "which is the only thing separating it from a broken filter")

    def test_the_scope_echo_carries_nulls_as_meaning(self):
        """⭐ `scope` is how a caller checks the answer was filtered the way it
        asked. Every field is nullable and null means "not filtered on", so a
        model that dropped the nulls would leave a page unable to tell a
        one-round answer from a thirty-day one — which is precisely the bug
        `/proximity/revives` shipped."""
        heat = self._f("api_proximity_player_heatmap.json")
        assert heat["scope"]["session_date"] is None
        assert heat["scope"]["map_name"] == "te_escape2"
        assert "session_date" in heat["scope"], "a null scope key vanished"
        self._roundtrip(PlayerHeatmap, heat)

    def test_player_dies_is_the_only_mode_with_coverage(self):
        """⛔ Measured across all five modes: four return TEN keys,
        `player_dies` returns ELEVEN. `coverage: "kills_only"` says the map is
        deaths-by-enemy because world and suicide deaths are not tracked.

        A single model with `coverage: str | None = None` would put
        `"coverage": null` on the other four, which reads as "coverage
        unknown" — the opposite of the truth, since for them the question does
        not arise. Hence the union.
        """
        from pydantic import TypeAdapter

        plain = self._f("api_proximity_player_heatmap.json")
        dies = self._f("api_proximity_player_heatmap_player_dies.json")
        assert set(dies) - set(plain) == {"coverage"}
        assert dies["coverage"] == "kills_only"
        assert dies["mode"] == "player_dies" and plain["mode"] != "player_dies"

        # ⛔ THE ADAPTER COMES FROM THE ROUTE, NOT FROM THIS FILE. Building
        # `TypeAdapter(A | B)` by hand here tests the union I just wrote down,
        # not the one FastAPI serialises with: narrowing the route to
        # `response_model=PlayerHeatmap` — which silently drops `coverage`
        # from every player_dies response — left all 132 tests green. Same
        # mistake as hand-picking a union member, one level further out.
        from fastapi.routing import APIRoute

        from website.backend.routers import proximity_positions

        route = next(r for r in proximity_positions.router.routes
                     if isinstance(r, APIRoute)
                     and r.path == "/proximity/player-heatmap")
        adapter = TypeAdapter(route.response_model)
        for raw, expected, keys in ((plain, PlayerHeatmap, 10),
                                    (dies, PlayerHeatmapKillsOnly, 11)):
            chosen = adapter.validate_python(raw)
            assert type(chosen) is expected, (
                f"mode={raw['mode']} matched {type(chosen).__name__}")
            out = _json.loads(chosen.model_dump_json())
            assert len(out) == keys and out == raw

    def test_an_unresolvable_player_still_gets_a_name(self):
        """`player_name` falls back to `#` plus eight guid characters, so it is
        never null — an empty heatmap still labels whose it is."""
        empty = self._f("api_proximity_player_heatmap_empty.json")
        assert empty["hotzones"] == [] and empty["total"] == 0
        assert empty["player_name"].startswith("#")
        self._roundtrip(PlayerHeatmap, empty)

    def test_head_pct_is_a_float_because_the_query_guarantees_it(self):
        """⭐ The handler's `else 0` branch is an INT, but `HAVING COUNT(*) >= 10`
        makes `total` unreachable at 0 — a STRUCTURAL guarantee from the query
        in the same function, not a claim about today's rows. That is what
        separates this from `LeaderboardRow.kills`, where the only guarantee
        was "no null rows exist right now" and the type had to widen."""
        rows = self._f("api_proximity_hit_regions.json")["players"]
        assert rows, "the fixture lost its rows"
        assert all(r["total_hits"] >= 10 for r in rows), (
            "a row below the HAVING floor appeared — head_pct's int branch is "
            "reachable after all and the type must widen to int | float")
        modelled = ProximityHitRegions.model_validate(
            self._f("api_proximity_hit_regions.json"))
        assert all(isinstance(r.head_pct, float) for r in modelled.players)


def test_proximity_players_names_are_guaranteed_by_the_handler():
    """⚠️ `ProximityPlayerRef.name` is non-null because of code, not schema.

    `player_track.player_name` is nullable; the handler wraps it in `str(...)`
    and skips the row unless both guid and name are truthy. Loosening the type
    to `str | None` breaks nothing a fixture can see — the values are still
    strings — so the guarantee is pinned where it actually lives. If the
    coercion or the truthiness filter goes, the type must widen with it.
    """
    import ast
    from pathlib import Path

    src = Path("website/backend/routers/proximity_positions.py").read_text()
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.AsyncFunctionDef)
              and n.name == "get_proximity_players")
    comprehensions = [ast.unparse(n) for n in ast.walk(fn)
                      if isinstance(n, ast.ListComp)]
    assert comprehensions, "the players list is no longer built by a comprehension"
    built = comprehensions[0]
    assert "str(r[0])" in built and "str(r[1])" in built, (
        f"the guid/name coercion is gone from {built!r} — `name: str` is no "
        f"longer guaranteed and the model must widen to `str | None`")
    assert "if r and r[0] and r[1]" in built, (
        f"the truthiness filter is gone from {built!r} — an empty or missing "
        f"name can now reach the payload")


class TestProxScoresWhereAWrongTypeMisstatesTheMetric:
    """`/proximity/prox-scores` and its `/formula`.

    ⛔ THE FORMULA ENDPOINT IS DIFFERENT IN KIND FROM EVERY OTHER ONE ON THIS
    BRANCH. Elsewhere a wrong type empties a panel; here it changes what a
    score MEANS. The endpoint exists so the page can CITE the weights instead
    of keeping its own copy, so the schema must not become that second copy:
    `categories`, `metrics` and `category_weights` are OPEN dicts, and the day
    a metric is added or retired the response still validates.
    """

    def _f(self, name):
        return _json.loads((_FIXTURES / name).read_text())

    def _roundtrip(self, model, raw):
        modelled = _json.loads(model.model_validate(raw).model_dump_json())
        assert not missing_keys(raw, modelled), (
            f"{model.__name__} dropped {missing_keys(raw, modelled)}")
        assert raw == modelled, f"{model.__name__} altered a value"
        return modelled

    def test_the_formula_survives_intact(self):
        self._roundtrip(ProxFormula,
                        self._f("api_proximity_prox_scores_formula.json"))

    def test_a_new_metric_does_not_break_the_formula_endpoint(self):
        """The point of the open dicts, checked rather than asserted in prose.
        A schema that pinned the metric names would answer 500 on the first
        formula change — on the endpoint whose job is to publish changes."""
        raw = self._f("api_proximity_prox_scores_formula.json")
        cat = next(iter(raw["categories"]))
        raw["categories"][cat]["metrics"]["a_brand_new_metric"] = {
            "label": "Invented", "weight": 0.25, "invert": True}
        raw["categories"]["prox_invented"] = {
            "label": "Invented", "description": "did not exist yesterday",
            "weight_in_overall": 0.0, "metrics": {}}
        raw["category_weights"]["prox_invented"] = 0.0
        modelled = ProxFormula.model_validate(raw)
        assert "a_brand_new_metric" in modelled.categories[cat].metrics
        assert "prox_invented" in modelled.categories

    @pytest.mark.parametrize("fixture", [
        "api_proximity_prox_scores.json",
        "api_proximity_prox_scores_empty.json",
        "api_proximity_prox_scores_limited.json",
    ])
    def test_scores_survive_every_recorded_state(self, fixture):
        self._roundtrip(ProxScores, self._f(fixture))

    def test_a_live_metric_has_five_keys_and_a_retired_one_six(self):
        """⛔ THE MISTAKE THIS TEST EXISTS FOR WAS MINE, AND THE BEFORE/AFTER
        COMPARISON CAUGHT IT. `retired_in: str | None = None` put
        `"retired_in": null` on every live metric. `exclude_none` would not
        have fixed it either: `raw` and `percentile` use null as a VALUE — a
        player with no measurement still appears, contribution zeroed — and
        would have been stripped with it. Hence a union.
        """
        raw = self._f("api_proximity_prox_scores.json")
        live, retired = [], []
        for player in raw["players"]:
            for metrics in player["breakdown"].values():
                for entry in metrics.values():
                    (retired if "retired_in" in entry else live).append(entry)
        assert live and retired, (
            f"the fixture no longer covers both kinds: {len(live)} live, "
            f"{len(retired)} retired")
        assert all(len(e) == 5 for e in live)
        assert all(len(e) == 6 for e in retired)
        out = self._roundtrip(ProxScores, raw)
        for player in out["players"]:
            for metrics in player["breakdown"].values():
                for name, entry in metrics.items():
                    assert ("retired_in" in entry) == (len(entry) == 6), name

    def test_raw_and_percentile_keep_their_nulls(self):
        """A metric with no measurement stays in the breakdown with its
        contribution zeroed — dropping the null would remove the evidence that
        the player was considered at all."""
        # ⛔ THIS TEST FAILED FIRST, AND THE FIXTURE WAS THE REASON. The
        # date-scoped response has no unmeasured metric at all (0 of 108), so
        # the assertion was true of the model and false of the sample. The
        # round-scoped one carries two — a real null, recorded rather than
        # constructed, which is the difference between pinning the contract
        # and pinning my own guess about it.
        raw = self._f("api_proximity_prox_scores_unmeasured.json")
        nulls = [e for p in raw["players"] for m in p["breakdown"].values()
                 for e in m.values() if e["raw"] is None]
        assert nulls, "the fixture lost its unmeasured metrics"
        assert all(e["contribution"] == 0 for e in nulls)
        out = self._roundtrip(ProxScores, raw)
        still = [e for p in out["players"] for m in p["breakdown"].values()
                 for e in m.values() if e["raw"] is None]
        assert len(still) == len(nulls)

    def test_player_count_is_the_count_before_the_limit(self):
        """⚠️ Like `total` on /api/uploads: `?limit=1` answers one player with
        `player_count: 14`. A consumer reading it as "rows below" gets 14."""
        limited = self._f("api_proximity_prox_scores_limited.json")
        assert len(limited["players"]) == 1
        assert limited["player_count"] > 1

    def test_an_empty_scope_says_so_in_quality(self):
        """⭐ `ranking_available` separates "nobody scored" from "we could not
        score" — an empty list alone cannot."""
        empty = self._f("api_proximity_prox_scores_empty.json")
        assert empty["players"] == []
        assert empty["quality"]["ranking_available"] is False
        full = self._f("api_proximity_prox_scores.json")
        assert full["quality"]["ranking_available"] is True

    def test_the_two_scope_shapes_in_this_family_are_not_the_same(self):
        """⚠️ `ProxScoresScope` carries `scoped` and no `player_guid`;
        `ProximityScope` carries `player_guid` and no `scoped`. A shared
        helper reading one off the other finds a missing key, not a null."""
        scores_scope = self._f("api_proximity_prox_scores.json")["scope"]
        positions_scope = self._f("api_proximity_player_heatmap.json")["scope"]
        assert "scoped" in scores_scope and "player_guid" not in scores_scope
        assert "player_guid" in positions_scope and "scoped" not in positions_scope


def test_no_router_hand_copies_the_round_duration_expression():
    """⛔ CLAUDE.md: round duration ALWAYS comes from `shared/round_time.py`.

    `_SESSION_ROUNDS_SQL` had its own inlined copy of exactly what
    `round_duration_sql()` builds — mine, from #824 — and it went unnoticed
    until a change to the canonical helper made the two disagree: the helper
    tightened its seconds pattern to `[0-5][0-9]` while the copy kept
    `[0-9]{2}`, so `"4:60"` would have been 300 s in one place and unknown in
    the other. Zero rows carry such a clock today across all 3,176 rounds, so
    this was latent — which is the moment to remove the copy, not the moment
    to argue it does not matter.

    A source-level guard on purpose: no fixture can see a second copy of an
    expression, only the text can.
    """
    import re
    from pathlib import Path

    # The tell is `actual_time ~ '...'` written out in a router rather than
    # obtained from the helper.
    offenders = []
    for path in sorted(Path("website/backend/routers").glob("*.py")):
        text = path.read_text()
        for match in re.finditer(r"actual_time\s*~\s*'([^']+)'", text):
            line = text[:match.start()].count("\n") + 1
            offenders.append(f"{path.name}:{line} — {match.group(1)}")
    assert not offenders, (
        "a router spells out the actual_time clock pattern instead of calling "
        "shared.round_time.round_duration_sql(): " + "; ".join(offenders))


class TestTheLastTwoProximityBoards:
    """`/proximity/player-aim` and `/proximity/hotzones` — the last two on the
    frontend author's phase-5 list, typed before the page exists.

    ⚠️ THREE NEAR-IDENTICAL CELL SHAPES LIVE IN THIS ONE FAMILY and none of
    them is interchangeable:

        HeatmapCell   x, y, count
        AimCell       x, y, count, rose, mean_yaw, r
        HotzoneCell   x, y, count, kills, deaths

    A shared renderer that assumes one silently misreads the others, which is
    why they are three models and not one with optional fields.
    """

    def _f(self, name):
        return _json.loads((_FIXTURES / name).read_text())

    def _roundtrip(self, model, raw):
        modelled = _json.loads(model.model_validate(raw).model_dump_json())
        assert not missing_keys(raw, modelled), (
            f"{model.__name__} dropped {missing_keys(raw, modelled)}")
        assert raw == modelled, f"{model.__name__} altered a value"
        return modelled

    def test_the_three_cell_shapes_are_actually_three(self):
        aim = self._f("api_proximity_player_aim.json")["hotzones"][0]
        hot = self._f("api_proximity_hotzones_ready.json")["hotzones"][0]
        heat = self._f("api_proximity_player_heatmap.json")["hotzones"][0]
        assert set(heat) == {"x", "y", "count"}
        assert set(aim) == {"x", "y", "count", "rose", "mean_yaw", "r"}
        assert set(hot) == {"x", "y", "count", "kills", "deaths"}

    def test_player_aim_survives_both_states(self):
        self._roundtrip(PlayerAim, self._f("api_proximity_player_aim.json"))
        self._roundtrip(PlayerAim, self._f("api_proximity_player_aim_empty.json"))

    def test_an_empty_scope_says_maximum_spread_not_zero(self):
        """⭐ The zero-shot answer is CHOSEN, not zeroed: 180° circular
        deviation and a Rayleigh p of 1.0 say "no preferred direction", which
        is the honest reading of no shots. Typing these nullable would invite
        a consumer to render "—" and lose the statement."""
        empty = self._f("api_proximity_player_aim_empty.json")
        assert empty["total"] == 0 and empty["hotzones"] == []
        assert empty["circular"]["circular_std_deg"] == 180.0
        assert empty["circular"]["rayleigh_p"] == 1.0
        assert empty["narrative"] == ["0 shots tracked"]

    def test_the_pitch_histogram_has_one_more_edge_than_bins(self):
        """A consumer that zips edges with counts drops the last bin."""
        for fixture in ("api_proximity_player_aim.json",
                        "api_proximity_player_aim_empty.json"):
            hist = self._f(fixture)["pitch_hist"]
            assert len(hist["edges"]) == len(hist["counts"]) + 1

    @pytest.mark.parametrize(("fixture", "keys"), [
        ("api_proximity_hotzones_ready.json", 10),
        ("api_proximity_hotzones_no_map.json", 8),
        ("api_proximity_hotzones_unknown_map.json", 10),
    ])
    def test_hotzones_survives_every_recorded_shape(self, fixture, keys):
        from fastapi.routing import APIRoute
        from pydantic import TypeAdapter

        from website.backend.routers import proximity_combat

        route = next(r for r in proximity_combat.router.routes
                     if isinstance(r, APIRoute) and r.path == "/proximity/hotzones")
        raw = self._f(fixture)
        assert len(raw) == keys
        out = _json.loads(
            TypeAdapter(route.response_model).validate_python(raw).model_dump_json())
        assert out == raw

    def test_status_is_not_the_discriminator_between_the_two_shapes(self):
        """⛔ THE TRAP A CONSUMER WALKS INTO HERE.

        `status: "prototype"` appears on BOTH the eight-key and the ten-key
        shape — a scope naming a map with no engagements answers ten keys with
        that status, while an empty scope answers eight with the same one. And
        the eight-key shape is also what a swallowed database error produces,
        with only `status: "error"` to say so. So neither the key set nor the
        status alone identifies what happened; they have to be read together.
        """
        no_map = self._f("api_proximity_hotzones_no_map.json")
        unknown = self._f("api_proximity_hotzones_unknown_map.json")
        ready = self._f("api_proximity_hotzones_ready.json")
        assert no_map["status"] == unknown["status"] == "prototype"
        assert len(no_map) == 8 and len(unknown) == 10
        assert ready["status"] == "ok" and len(ready) == 10
        # …and `message` is inverted from what a reader expects:
        assert no_map["message"] and ready["message"] is None


class TestAnOutageMustNotReadAsAnEmptyDatabase:
    """`/api/stats/overview` — the site's headline figures.

    ⛔ HOW THIS WAS FOUND, because reading would not have: every GET endpoint
    was run against a database adapter that raises on every query. ELEVEN
    answered 200 with a payload indistinguishable from an empty database, and
    this one is the most visible of them — `rounds: 0, players: 0,
    total_kills: 0` on the homepage, during an outage, with nothing saying so.

    `_safe_val` substitutes its default per metric and the endpoint still
    answers 200. That is deliberate (one failed aggregate must not take the
    page down) and it is only half a contract without a way to say it
    happened.
    """

    @staticmethod
    def _broken_client():
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from website.backend import dependencies as deps
        from website.backend.routers import records_overview

        class Broken:
            async def fetch_all(self, *a, **k):
                raise RuntimeError("database is down")
            async def fetch_one(self, *a, **k):
                raise RuntimeError("database is down")
            async def fetch_val(self, *a, **k):
                raise RuntimeError("database is down")

        app = FastAPI()
        app.include_router(records_overview.router, prefix="/api")
        app.dependency_overrides[deps.get_db] = lambda: Broken()
        return TestClient(app, raise_server_exceptions=False)

    def test_a_dead_database_says_so_instead_of_reporting_zeros(self):
        with self._broken_client() as client:
            response = client.get("/api/stats/overview")
        assert response.status_code == 200, (
            "one failed aggregate must not take the homepage down")
        body = response.json()
        assert body["rounds"] == 0 and body["total_kills"] == 0
        assert body["status"] == "partial", (
            "every query raised and the payload still called itself ok — the "
            "zeros above are indistinguishable from a quiet fortnight")
        assert body["failed_metrics"], "no metric was named as failed"
        assert body["note"] and "not zero" in body["note"]

    def test_the_three_new_fields_reach_the_wire(self):
        """⚠️ THE FIRST ATTEMPT AT THIS FIX WAS SWALLOWED BY THE MODEL.

        The handler returned `status`, `note` and `failed_metrics`, and the
        response did not carry them, because `response_model` drops what the
        model does not declare — silently, with a 200. This asserts the
        DECLARATION, not the handler, because the handler was already right.
        """
        from website.backend.routers.records_overview import StatsOverview

        assert {"status", "note", "failed_metrics"} <= set(
            StatsOverview.model_fields), (
            "the model stopped declaring the fields that say an outage "
            "happened; the handler still returns them and they will be "
            "dropped from the response with a 200")
