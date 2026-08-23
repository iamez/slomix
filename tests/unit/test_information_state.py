"""§6 Layer 3: what a player could have known — and what we refuse to claim.

Most of these tests assert a restriction rather than a feature, because this is
the layer where overclaiming is cheap and invisible. A model that says too much
still returns numbers; nothing fails until someone believes them.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

from website.backend.services.information_state import (
    CONFIDENCE_FLOOR,
    DECAY_TAU_S,
    EXPIRY_BOUND,
    EXPIRY_INTERVAL_ONLY,
    EXPIRY_VALIDATED_WAVE,
    GUNFIRE_REGION_RADIUS,
    INDIRECT_WEAPON_IDS,
    MAX_OBSERVED_REINFORCE_MS,
    OBSERVED_OUT_OF_ACTION,
    BeliefItem,
    HolderState,
    Region,
    aim_lock_beliefs,
    apply_capability,
    contact_beliefs,
    group_by_holder,
    gunfire_beliefs,
    known_enemy_count,
    nearest_heard_activity_distance,
    nearest_known_enemy_distance,
    obituary_beliefs,
    resolve_expiry,
    resolves_a_subject,
    to_dict,
)


class TestGunfireResolvesNoOne:
    """⭐ The phantom squad, which §6.3 names directly."""

    @staticmethod
    def _burst(n: int) -> list[BeliefItem]:
        shots = [("SHOOTER", 1000 + i * 100, 100.0, 0.0, 0.0) for i in range(n)]
        # ⚠️ The shooter is a candidate holder ON PURPOSE. Without them here the
        # `holder == guid` guard is never exercised and this whole class would
        # pass with that branch deleted (CodeRabbit, PR #799).
        return gunfire_beliefs(
            shots,
            {"H": (200.0, 0.0, 0.0), "SHOOTER": (100.0, 0.0, 0.0)},
            audible_radius=1500,
        )

    def test_a_burst_is_not_a_squad(self):
        """`proximity_shot_fired` emits one row per shot. Counting belief items
        would turn one enemy firing ten times into ten enemies."""
        state = group_by_holder(self._burst(10))["H"]
        assert len(state.beliefs) == 10
        assert known_enemy_count(state, 2000) == 0

    def test_gunfire_never_resolves_who(self):
        """The table has no target column: firing proves a direction, not which
        player was perceived. A subject here would be invented."""
        assert all(b.subject_guid is None for b in self._burst(3))

    def test_the_shooter_does_not_hear_themselves(self):
        assert all(b.holder_guid == "H" for b in self._burst(3))

    def test_out_of_earshot_hears_nothing(self):
        shots = [("SHOOTER", 1000, 100.0, 0.0, 0.0)]
        assert gunfire_beliefs(shots, {"FAR": (9000.0, 0.0, 0.0)}, audible_radius=1500) == []

    def test_the_region_is_never_the_telemetry_point(self):
        """§6.3: do not expose the stored origin as a belief point."""
        belief = self._burst(1)[0]
        assert belief.region is not None
        assert belief.region.radius == GUNFIRE_REGION_RADIUS > 0


class TestDistanceIsAnInterval:
    def test_a_region_gives_a_range_not_a_number(self):
        region = Region(1000.0, 0.0, 0.0, 400.0)
        lo, hi = region.distance_interval(0.0, 0.0, 0.0)
        assert (lo, hi) == (600.0, 1400.0)

    def test_standing_inside_the_region_cannot_be_negative(self):
        lo, _hi = Region(0.0, 0.0, 0.0, 400.0).distance_interval(10.0, 0.0, 0.0)
        assert lo == 0.0

    def test_nearest_reports_the_interval(self):
        state = HolderState("H", [BeliefItem(
            holder_guid="H", source="gunfire", t_observed=0,
            region=Region(1000.0, 0.0, 0.0, 400.0))])
        # A region with a subject is a known enemy; one without is heard noise.
        assert nearest_known_enemy_distance(state, 0, (0.0, 0.0, 0.0)) is None
        assert nearest_heard_activity_distance(state, 0, (0.0, 0.0, 0.0)) == {
            "min": 600.0, "max": 1400.0
        }

    def test_nothing_believed_is_none_not_zero(self):
        """Zero would read as "an enemy is right here"."""
        assert nearest_known_enemy_distance(HolderState("H"), 0, (0.0, 0.0, 0.0)) is None

    def test_a_tighter_belief_lowers_the_upper_bound(self):
        """⭐ The bound the holder can PROVE, not the bound of one belief.

        Two enemies: AAA somewhere in [500, 1300], BBB certainly in [520, 600].
        The nearest of the two is therefore at most 600 — the holder can rule
        1300 out. Taking `max` from whichever belief happened to win on `min`
        threw that proof away and reported an enemy possibly twice as far as
        anything believed, which is the same overclaiming the docstring
        forbids one line up ("a number the holder never had").
        """
        def believe(guid, x, radius):
            return BeliefItem(
                holder_guid="H", source="obituary", t_observed=0,
                region=Region(x, 0.0, 0.0, radius), subject_guid=guid,
                expires_at_ms=100_000)

        wide = believe("AAA", 900.0, 400.0)
        tight = believe("BBB", 560.0, 40.0)
        pos = (0.0, 0.0, 0.0)
        expected = {"min": 500.0, "max": 600.0}
        # Order must not matter: this is a property of the set of beliefs.
        assert nearest_known_enemy_distance(
            HolderState("H", [wide, tight]), 1000, pos) == expected
        assert nearest_known_enemy_distance(
            HolderState("H", [tight, wide]), 1000, pos) == expected

    def test_the_interval_never_inverts(self):
        """min <= max holds however the two bounds are chosen."""
        def believe(guid, x, radius):
            return BeliefItem(
                holder_guid="H", source="obituary", t_observed=0,
                region=Region(x, 0.0, 0.0, radius), subject_guid=guid,
                expires_at_ms=100_000)

        state = HolderState("H", [believe("A", 2000.0, 100.0),
                                  believe("B", 300.0, 250.0),
                                  believe("C", 900.0, 600.0)])
        out = nearest_known_enemy_distance(state, 1000, (0.0, 0.0, 0.0))
        assert out["min"] <= out["max"]

    def test_a_zero_length_life_is_never_believed(self):
        """A belief that expires when it was observed is worth nothing.

        It returns 0.0 through the expiry check, NOT through the `span <= 0`
        guard below it: `t >= expires_at_ms` is already true. Mutating that
        guard changes no output for any input (verified by exhaustive search
        over t_observed/expires_at/t), which is why it is documented as
        unreachable rather than covered by a test that cannot exist.
        """
        belief = BeliefItem(holder_guid="H", source="obituary", t_observed=5_000,
                            subject_guid="X", expires_at_ms=5_000)
        assert belief.confidence(5_000) == 0.0


class TestDecay:
    def test_one_time_constant_is_one_over_e(self):
        b = BeliefItem(holder_guid="H", source="gunfire",
                       t_observed=0)
        tau_ms = DECAY_TAU_S["gunfire"] * 1000
        assert b.confidence(int(tau_ms)) == pytest.approx(math.exp(-1), abs=1e-6)

    def test_nothing_is_known_before_it_happened(self):
        b = BeliefItem(holder_guid="H", source="gunfire",
                       t_observed=5000)
        assert b.confidence(4999) == 0.0

    def test_tau_values_are_documented_where_they_are_defined(self):
        """⛔ §6.3 forbids tuning these against the outcome later tested. The
        defence is that the reasoning is written down and can be argued with."""
        source = Path(
            "website/backend/services/information_state.py"
        ).read_text()
        block = source[source.index("DECAY_TAU_S"):]
        preamble = source[:source.index("DECAY_TAU_S")]
        assert "FROZEN BEFORE ANY MEASUREMENT" in preamble
        for name in DECAY_TAU_S:
            assert name in preamble or name in block[:400]


class TestRosterStateExpiry:
    """⭐ Where the validated Layer 2 clock earns its place — and where its
    absence must be admitted rather than papered over."""

    @staticmethod
    def _down(expiry: int, basis: str) -> BeliefItem:
        return BeliefItem(
            holder_guid="H", source="public_obituary", t_observed=5000,
            subject_guid="E1", roster_state=OBSERVED_OUT_OF_ACTION,
            expires_at_ms=expiry, expiry_basis=basis,
        )

    @pytest.mark.parametrize("t,expected", [
        (5000, 1.0), (15000, 1.0), (24999, 1.0), (25000, 0.0), (60000, 0.0),
    ])
    def test_a_validated_wave_is_a_step(self, t: int, expected: float):
        """"He is down" is true until his team can spawn, and then it is not."""
        assert self._down(25000, EXPIRY_VALIDATED_WAVE).confidence(t) == expected

    @pytest.mark.parametrize("basis", [EXPIRY_INTERVAL_ONLY, EXPIRY_BOUND])
    def test_without_a_phase_it_falls_linearly(self, basis: str):
        """⭐ With the period known but not the phase, he returns SOMEWHERE
        inside the next cycle and every point in it is equally likely. A step
        would claim a wave time we do not have."""
        b = self._down(25000, basis)
        assert b.confidence(5000) == 1.0
        assert b.confidence(15000) == pytest.approx(0.5)
        assert b.confidence(25000) == 0.0

    def test_a_roster_belief_can_never_be_permanent(self):
        """⛔ `public_obituary` has no decay constant. Before the fix, a belief
        with no expiry fell through to `tau is None` and returned 1.0 for the
        rest of the round — everyone fully believing a corpse for ten minutes."""
        orphan = BeliefItem(holder_guid="H", source="public_obituary",
                            t_observed=0, roster_state=OBSERVED_OUT_OF_ACTION)
        with pytest.raises(AssertionError, match="believed forever"):
            orphan.confidence(600_000)

    @pytest.mark.parametrize("clock,basis,span", [
        ({"interval_ms": 20000, "offset_ms": 15000}, EXPIRY_VALIDATED_WAVE, None),
        ({"interval_ms": 20000, "offset_ms": None}, EXPIRY_INTERVAL_ONLY, 20000),
        ({}, EXPIRY_BOUND, MAX_OBSERVED_REINFORCE_MS),
        (None, EXPIRY_BOUND, MAX_OBSERVED_REINFORCE_MS),
    ])
    def test_every_clock_state_yields_a_named_basis(self, clock, basis, span):
        expiry, got = resolve_expiry(clock, 30_000)
        assert got == basis
        assert expiry > 30_000, "an expiry must never fall before the death"
        if span is not None:
            assert expiry - 30_000 == span

    def test_expiry_is_computed_per_death_not_per_team(self):
        """⛔ One timestamp per team cannot be the next wave for deaths at
        different times: waves repeat all round. A death at 30 s given a 25 s
        wave got an expiry in its own past and was dead on arrival."""
        clock = {"AXIS": {"interval_ms": 20000, "offset_ms": 15000}}
        early = obituary_beliefs([("V1", "AXIS", 5000)], ["H"], clock=clock)[0]
        late = obituary_beliefs([("V2", "AXIS", 30000)], ["H"], clock=clock)[0]
        assert early.expires_at_ms != late.expires_at_ms
        for belief in (early, late):
            assert belief.confidence(belief.t_observed) == 1.0

    def test_a_death_is_public(self):
        beliefs = obituary_beliefs(
            [("V", "AXIS", 5000)], ["A", "B", "V"],
            clock={"AXIS": {"interval_ms": 20000, "offset_ms": 15000}})
        assert {b.holder_guid for b in beliefs} == {"A", "B"}
        assert all(b.expiry_basis == EXPIRY_VALIDATED_WAVE for b in beliefs)

    def test_the_bound_is_the_longest_interval_this_project_has_seen(self):
        """⚠️ 35 s, not the 30 s "everyone knows" ET uses: the intervals present
        in proximity_spawn_timing are 15, 20, 25, 30 AND 35."""
        assert MAX_OBSERVED_REINFORCE_MS == 35_000


class TestContactIsAsymmetric:
    ENGAGEMENT = [("VICTIM", [{
        "guid": "ATT", "weapons": {"3": 4}, "first_hit_ms": 1000, "last_hit_ms": 1600,
    }])]

    def test_the_attacker_may_name_a_direct_fire_target(self):
        beliefs = contact_beliefs(self.ENGAGEMENT)
        attacker = [b for b in beliefs if b.holder_guid == "ATT"]
        assert len(attacker) == 1
        assert attacker[0].subject_guid == "VICTIM"

    def test_the_victim_learns_only_that_they_are_hit(self):
        """No bearing, no identity. Nothing in the data records a perceived
        direction and §6.3 forbids inventing one."""
        victim = [b for b in contact_beliefs(self.ENGAGEMENT)
                  if b.holder_guid == "VICTIM"]
        assert len(victim) == 1
        assert victim[0].kind == "nonspatial_contact"
        assert victim[0].subject_guid is None
        assert victim[0].region is None

    def test_a_grenade_hands_the_attacker_nothing(self):
        """⭐ A grenade thrown at a doorway kills people the thrower never saw."""
        grenade = [("VICTIM", [{"guid": "ATT", "weapons": {"9": 1},
                                "first_hit_ms": 1000}])]
        assert [b for b in contact_beliefs(grenade) if b.holder_guid == "ATT"] == []

    def test_one_indirect_weapon_withholds_the_whole_engagement(self):
        """Per-hit attribution is not recoverable: `attackers` carries only
        first/last hit and a per-weapon count, so we cannot tell which weapon
        produced which hit. Conservative is the only honest option."""
        mixed = [("VICTIM", [{"guid": "ATT", "weapons": {"3": 4, "9": 1},
                              "first_hit_ms": 1000}])]
        assert [b for b in contact_beliefs(mixed) if b.holder_guid == "ATT"] == []

    def test_teammates_get_nothing_from_proximity(self):
        holders = {b.holder_guid for b in contact_beliefs(self.ENGAGEMENT)}
        assert holders == {"ATT", "VICTIM"}


#: The fourteen whose id AND name this repository already carries.
INDIRECT_BY_REPO_NAME = {
    4: "Grenade Launcher", 5: "Panzerfaust", 6: "Flamethrower", 9: "Grenade",
    13: "Artillery", 15: "Dynamite", 17: "Map Mortar", 26: "Landmine",
    27: "Satchel", 29: "Smoke Bomb", 37: "GPG40", 38: "M7", 53: "Bazooka",
    55: "Airstrike",
}

#: The six `WP_WEAPON_NAMES` cannot distinguish: it has no entry for 22 or 28,
#: and calls 34, 43 and 51 all "Mortar". Pinned to the engine enum instead.
INDIRECT_BY_ENGINE_NAME = {
    22: "WP_SMOKE_MARKER", 28: "WP_SATCHEL_DET", 34: "WP_MORTAR",
    43: "WP_MORTAR_SET", 51: "WP_MORTAR2", 52: "WP_MORTAR2_SET",
}

ENGINE_HEADER = Path("/home/samba/share/etlegacy-source/src/game/bg_public.h")


class TestMalformedRowsAreSkippedNotGuessed:
    """A row the database could not fill must produce no belief at all.

    Both fields come straight out of the engagement JSON, so both can be NULL.
    A missing attacker guid has no holder to attribute the belief to, and a
    missing first_hit_ms has no instant to attach it at — inventing either
    would put a fabricated belief in front of a real player.
    """

    def test_an_attacker_without_a_guid_is_skipped(self):
        rows = [("VICTIM", [{"guid": None, "weapons": {"3": 1},
                             "first_hit_ms": 1000}])]
        assert contact_beliefs(rows) == []

    def test_an_attacker_without_a_hit_time_is_skipped(self):
        rows = [("VICTIM", [{"guid": "ATT", "weapons": {"3": 1},
                             "first_hit_ms": None}])]
        assert contact_beliefs(rows) == []

    def test_a_well_formed_row_beside_a_broken_one_still_lands(self):
        """The skip must drop one row, not abandon the batch."""
        rows = [("VICTIM", [
            {"guid": None, "weapons": {"3": 1}, "first_hit_ms": 1000},
            {"guid": "ATT", "weapons": {"3": 1}, "first_hit_ms": 2000},
        ])]
        holders = {b.holder_guid for b in contact_beliefs(rows)}
        assert "ATT" in holders


class TestWeaponClassification:
    def test_derived_ids_match_this_repository_s_own_names(self):
        """⚠️ The first derivation of these ids was wrong and self-consistent:
        the `weapon_t` enum has one member without the `WP_` prefix
        (VERYBIGEXPLOSION, 18), the parser skipped that line without counting
        it, and every later id came out one low. It disagreed with
        WP_WEAPON_NAMES, and WP_WEAPON_NAMES was right."""
        from website.backend.services.player_profile_metrics import WP_WEAPON_NAMES

        for wid, name in INDIRECT_BY_REPO_NAME.items():
            assert wid in INDIRECT_WEAPON_IDS, f"{name} ({wid}) must be indirect"
            assert WP_WEAPON_NAMES.get(wid) == name, (
                f"id {wid} is {WP_WEAPON_NAMES.get(wid)!r} here, expected {name!r}"
            )

    def test_every_indirect_id_is_accounted_for(self):
        """⭐ Six ids had no second source at all.

        `WP_WEAPON_NAMES` has no entry for 22 or 28, and 34/43/51/52 are all
        spelled "Mortar", so fourteen of twenty were cross-checked and six were
        taken on trust (CodeRabbit, PR #799). Those six are pinned here against
        the ET:Legacy enum's own `///< N` comments, which is where every id in
        this set came from.
        """
        assert set(INDIRECT_BY_REPO_NAME) | set(INDIRECT_BY_ENGINE_NAME) == (
            INDIRECT_WEAPON_IDS
        ), "an indirect id is verified against neither source"

    @pytest.mark.skipif(not ENGINE_HEADER.exists(),
                        reason="ET:Legacy source not present on this host")
    @pytest.mark.parametrize("wid,name", sorted(INDIRECT_BY_ENGINE_NAME.items()))
    def test_the_unnamed_ids_match_the_engine_enum(self, wid: int, name: str):
        """Runs only where the source is checked out. The test above holds
        everywhere, so this one adds evidence without being the only guard."""
        text = ENGINE_HEADER.read_text().splitlines()[845:913]
        by_id = {}
        for raw in text:
            m = re.match(r"^\s*([A-Z][A-Z0-9_]*),?\s*///<\s*(\d+)", raw)
            if m:
                by_id[int(m.group(2))] = m.group(1)
        assert by_id.get(wid) == name

    @pytest.mark.parametrize("wid,name", [(3, "MP40"), (8, "Thompson"),
                                          (23, "Kar98"), (32, "FG42")])
    def test_direct_fire_weapons_are_not_listed(self, wid: int, name: str):
        assert wid not in INDIRECT_WEAPON_IDS

    def test_no_weapons_resolves_nothing(self):
        assert resolves_a_subject([]) is False


class TestCapabilityIsNotSilence:
    """⛔ The rule the whole capability manifest was built for."""

    @staticmethod
    def _states() -> dict[str, HolderState]:
        beliefs = gunfire_beliefs(
            [("S", 1000, 0.0, 0.0, 0.0)], {"H": (10.0, 0.0, 0.0)}, audible_radius=1500)
        beliefs += aim_lock_beliefs([("H", "E1", 2000)])
        return group_by_holder(beliefs)

    @pytest.mark.parametrize("state,fragment", [
        ("unknown", "cannot be proven"),
        ("disabled", "was not enabled"),
    ])
    def test_an_unproven_channel_is_named_not_dropped(self, state: str, fragment: str):
        states = self._states()
        manifest = {"capabilities": {"shot_fired": state, "aim_lock": state}}
        apply_capability(states, manifest, ["H"])
        assert fragment in states["H"].unavailable["gunfire"]
        assert not [b for b in states["H"].beliefs if b.source == "gunfire"]

    def test_a_proven_channel_survives(self):
        states = self._states()
        apply_capability(
            states, {"capabilities": {"shot_fired": "enabled", "aim_lock": "enabled"}},
            ["H"])
        assert states["H"].unavailable == {}
        assert [b for b in states["H"].beliefs if b.source == "gunfire"]

    def test_a_holder_with_no_beliefs_still_gets_the_reason(self):
        """Otherwise a player who heard nothing and a player whose round could
        not record hearing look identical."""
        states: dict[str, HolderState] = {}
        apply_capability(states, None, ["QUIET"])
        assert "gunfire" in states["QUIET"].unavailable

    def test_aim_lock_is_the_only_channel_that_names_a_subject_unprompted(self):
        """Gunfire cannot; contact requires being hit. This is what makes
        aim_lock worth its capability gate."""
        locks = aim_lock_beliefs([("H", "E1", 2000)])
        assert locks[0].subject_guid == "E1"
        assert locks[0].capability == "aim_lock"


class TestPayloadTellsTheTruth:
    def test_it_says_what_it_is_not(self):
        payload = to_dict(HolderState("H"), 0, (0.0, 0.0, 0.0))
        joined = " ".join(payload["notes"]).lower()
        assert "lower bound" in joined and "discord" in joined
        assert "oracle upper bound" in joined

    def test_faded_beliefs_leave_the_payload(self):
        state = HolderState("H", [BeliefItem(
            holder_guid="H", source="gunfire",
            t_observed=0, region=Region(0.0, 0.0, 0.0, 400.0))])
        assert to_dict(state, 0, (0.0, 0.0, 0.0))["beliefs"]
        assert to_dict(state, 60_000, (0.0, 0.0, 0.0))["beliefs"] == [], (
            "an exponential never reaches zero; without a display floor every "
            "noise of the round accumulates in the panel forever"
        )

    def test_the_panel_and_the_count_never_disagree(self):
        """⭐ Two thresholds, one truth.

        Beliefs are shown down to 1% so a reader can watch one fade, but the
        count uses CONFIDENCE_FLOOR. Without `counts_as_known` on each item the
        panel would draw something `known_enemy_count` has already discarded,
        and the two numbers on screen would contradict each other.
        """
        belief = BeliefItem(
            holder_guid="H", source="aim_lock",
            t_observed=0, subject_guid="E1")
        state = HolderState("H", [belief])
        tau_ms = int(DECAY_TAU_S["aim_lock"] * 1000)

        fresh = to_dict(state, 0, (0.0, 0.0, 0.0))
        assert fresh["beliefs"][0]["counts_as_known"] is True
        assert fresh["known_enemy_count"] == 1

        # Just past one time constant: still drawn, no longer counted.
        faded = to_dict(state, tau_ms + 500, (0.0, 0.0, 0.0))
        assert faded["beliefs"], "it should still be visible while it fades"
        assert faded["beliefs"][0]["counts_as_known"] is False
        assert faded["known_enemy_count"] == 0
        assert belief.confidence(tau_ms + 500) < CONFIDENCE_FLOOR

    def test_the_module_never_claims_seeing(self):
        """⛔ §6.1: never label a trace "saw"; label it line-of-sight
        availability.

        The word itself is fine and in fact necessary — every occurrence in the
        module is a NEGATION explaining what is not claimed ("not what anyone
        saw", "someone the thrower never saw"). This asserts the negations are
        there and that no affirmative claim slipped in beside them.
        """
        source = Path("website/backend/services/information_state.py").read_text()
        for match in re.finditer(r"[^.\n]*\bsaw\b[^.\n]*", source):
            phrase = match.group(0).lower()
            assert any(neg in phrase for neg in ("not ", "never", "may not")), (
                f"an affirmative claim of seeing: {match.group(0).strip()!r}"
            )
        assert "never saw" in source, "the model must still say what it refuses"


class TestTheTwoNumbersNeverContradict:
    """⛔ [5]: a holder who only heard shots used to get `known_enemy_count: 0`
    and a populated enemy distance in the same payload."""

    @staticmethod
    def _heard_only() -> HolderState:
        shots = gunfire_beliefs(
            [("S", 1000, 1000.0, 0.0, 0.0)], {"H": (0.0, 0.0, 0.0)},
            audible_radius=5000)
        return group_by_holder(shots)["H"]

    def test_noise_is_not_an_enemy_distance(self):
        payload = to_dict(self._heard_only(), 1000, (0.0, 0.0, 0.0))
        assert payload["known_enemy_count"] == 0
        assert payload["nearest_known_enemy_distance"] is None

    def test_but_the_noise_is_still_reported(self):
        """⭐ Hearing shots 900 units away IS information — just not an enemy.
        Dropping it would lose real evidence to avoid a contradiction."""
        payload = to_dict(self._heard_only(), 1000, (0.0, 0.0, 0.0))
        assert payload["nearest_heard_activity_distance"] == {"min": 600.0, "max": 1400.0}

    def test_a_named_enemy_appears_in_the_enemy_distance(self):
        state = HolderState("H", [BeliefItem(
            holder_guid="H", source="aim_lock", t_observed=0, subject_guid="E1",
            region=Region(1000.0, 0.0, 0.0, 400.0))])
        payload = to_dict(state, 0, (0.0, 0.0, 0.0))
        assert payload["known_enemy_count"] == 1
        assert payload["nearest_known_enemy_distance"] == {"min": 600.0, "max": 1400.0}
        assert payload["nearest_heard_activity_distance"] is None

    def test_the_count_and_the_distance_agree_on_every_channel(self):
        """The property, rather than three examples: a resolved subject appears
        in both, an unresolved region in neither."""
        for source, subject in [("gunfire", None), ("aim_lock", "E1"),
                                ("contact_hit", "E2")]:
            state = HolderState("H", [BeliefItem(
                holder_guid="H", source=source, t_observed=0, subject_guid=subject,
                region=Region(500.0, 0.0, 0.0, 100.0))])
            payload = to_dict(state, 0, (0.0, 0.0, 0.0))
            counted = payload["known_enemy_count"] > 0
            has_distance = payload["nearest_known_enemy_distance"] is not None
            assert counted == has_distance, (
                f"{source}: counted={counted} but distance={has_distance}"
            )


class TestKindCannotLie:
    """⛔ [7]: two call sites labelled a belief `position_region` and left
    `region` as None, because neither input row carries coordinates."""

    @pytest.mark.parametrize("region,subject,expected", [
        (Region(0.0, 0.0, 0.0, 10.0), "E1", "subject_position"),
        (Region(0.0, 0.0, 0.0, 10.0), None, "position_region"),
        (None, "E1", "subject_contact"),
        (None, None, "nonspatial_contact"),
    ])
    def test_the_label_is_read_off_the_contents(self, region, subject, expected):
        belief = BeliefItem(holder_guid="H", source="gunfire", t_observed=0,
                            region=region, subject_guid=subject)
        assert belief.kind == expected

    def test_a_roster_fact_is_a_roster_fact(self):
        belief = BeliefItem(holder_guid="H", source="public_obituary", t_observed=0,
                            subject_guid="E1", roster_state=OBSERVED_OUT_OF_ACTION,
                            expires_at_ms=1000, expiry_basis=EXPIRY_BOUND)
        assert belief.kind == "roster_state"

    def test_no_builder_promises_a_region_it_does_not_carry(self):
        """The property across every producer in the module."""
        produced = (
            contact_beliefs([("V", [{"guid": "A", "weapons": {"3": 1},
                                     "first_hit_ms": 1000}])])
            + aim_lock_beliefs([("H", "E1", 1000)])
            + gunfire_beliefs([("S", 1, 0.0, 0.0, 0.0)], {"H": (1.0, 0.0, 0.0)},
                              audible_radius=999)
            + obituary_beliefs([("V", "AXIS", 5000)], ["H"], clock={})
        )
        assert produced
        for belief in produced:
            if "position" in belief.kind or belief.kind == "position_region":
                assert belief.region is not None, f"{belief.kind} without a region"
            if "subject" in belief.kind:
                assert belief.subject_guid is not None


class TestHoldersMayBeAnyIterable:
    """⛔ [8]: `apply_capability` walks `holders` once per gated source, and a
    generator is exhausted by the first — leaving the second channel untouched
    and the payload looking like a proven capture."""

    @staticmethod
    def _states() -> dict[str, HolderState]:
        beliefs = gunfire_beliefs([("S", 1000, 0.0, 0.0, 0.0)],
                                  {"H": (10.0, 0.0, 0.0)}, audible_radius=1500)
        beliefs += aim_lock_beliefs([("H", "E1", 2000)])
        return group_by_holder(beliefs)

    @pytest.mark.parametrize("make", [
        pytest.param(lambda: ["H"], id="list"),
        pytest.param(lambda: (h for h in ["H"]), id="generator"),
        pytest.param(lambda: iter(["H"]), id="iterator"),
    ])
    def test_both_gated_channels_are_handled(self, make):
        states = self._states()
        apply_capability(
            states, {"capabilities": {"shot_fired": "unknown", "aim_lock": "unknown"}},
            make())
        assert set(states["H"].unavailable) == {"gunfire", "aim_lock"}, (
            "the second gated source was skipped"
        )
        assert states["H"].beliefs == [], "gated beliefs survived"
