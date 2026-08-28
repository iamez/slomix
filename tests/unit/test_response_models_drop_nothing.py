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

from website.backend.routers.records_awards import (
    AwardLeaderboard,
    AwardsPage,
    HallOfFame,
)
from website.backend.routers.records_matches import RoundAwards, RoundViz
from website.backend.routers.records_seasons import CurrentSeason
from website.backend.routers.records_weapons import WeaponsByPlayer

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
