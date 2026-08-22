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
    GUNFIRE_REGION_RADIUS,
    INDIRECT_WEAPON_IDS,
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
    nearest_known_enemy_distance,
    obituary_beliefs,
    resolves_a_subject,
    to_dict,
)


class TestGunfireResolvesNoOne:
    """⭐ The phantom squad, which §6.3 names directly."""

    @staticmethod
    def _burst(n: int) -> list[BeliefItem]:
        shots = [("SHOOTER", 1000 + i * 100, 100.0, 0.0, 0.0) for i in range(n)]
        return gunfire_beliefs(shots, {"H": (200.0, 0.0, 0.0)}, audible_radius=1500)

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
            holder_guid="H", kind="position_region", source="gunfire", t_observed=0,
            region=Region(1000.0, 0.0, 0.0, 400.0))])
        assert nearest_known_enemy_distance(state, 0, (0.0, 0.0, 0.0)) == {
            "min": 600.0, "max": 1400.0
        }

    def test_nothing_believed_is_none_not_zero(self):
        """Zero would read as "an enemy is right here"."""
        assert nearest_known_enemy_distance(HolderState("H"), 0, (0.0, 0.0, 0.0)) is None


class TestDecay:
    def test_one_time_constant_is_one_over_e(self):
        b = BeliefItem(holder_guid="H", kind="position_region", source="gunfire",
                       t_observed=0)
        tau_ms = DECAY_TAU_S["gunfire"] * 1000
        assert b.confidence(int(tau_ms)) == pytest.approx(math.exp(-1), abs=1e-6)

    def test_nothing_is_known_before_it_happened(self):
        b = BeliefItem(holder_guid="H", kind="position_region", source="gunfire",
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


class TestRosterStateIsAStepNotACurve:
    """⭐ Where the validated Layer 2 clock earns its place."""

    @staticmethod
    def _down(expiry: int | None) -> BeliefItem:
        return BeliefItem(
            holder_guid="H", kind="roster_state", source="public_obituary",
            t_observed=5000, subject_guid="E1",
            roster_state=OBSERVED_OUT_OF_ACTION, expires_at_ms=expiry,
        )

    @pytest.mark.parametrize("t,expected", [
        (5000, 1.0), (15000, 1.0), (24999, 1.0), (25000, 0.0), (60000, 0.0),
    ])
    def test_it_holds_until_the_wave_then_stops(self, t: int, expected: float):
        """"He is down" is true until his team can spawn, and then it is not.
        A decay curve would leave everyone half-believing a corpse."""
        assert self._down(25000).confidence(t) == expected

    def test_a_death_is_public(self):
        beliefs = obituary_beliefs(
            [("V", "AXIS", 5000)], ["A", "B", "V"], wave_expiry={"AXIS": 25000})
        assert {b.holder_guid for b in beliefs} == {"A", "B"}
        assert all(b.expires_at_ms == 25000 for b in beliefs)

    def test_without_a_validated_clock_there_is_no_expiry(self):
        """No clock means no known wave, so the belief cannot be given a
        principled end — it must not be given an invented one either."""
        beliefs = obituary_beliefs([("V", "AXIS", 5000)], ["A"], wave_expiry={})
        assert beliefs[0].expires_at_ms is None


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


class TestWeaponClassification:
    def test_derived_ids_match_this_repository_s_own_names(self):
        """⚠️ The first derivation of these ids was wrong and self-consistent:
        the `weapon_t` enum has one member without the `WP_` prefix
        (VERYBIGEXPLOSION, 18), the parser skipped that line without counting
        it, and every later id came out one low. It disagreed with
        WP_WEAPON_NAMES, and WP_WEAPON_NAMES was right."""
        from website.backend.services.player_profile_metrics import WP_WEAPON_NAMES

        expected = {
            4: "Grenade Launcher", 5: "Panzerfaust", 6: "Flamethrower",
            9: "Grenade", 13: "Artillery", 15: "Dynamite", 17: "Map Mortar",
            26: "Landmine", 27: "Satchel", 29: "Smoke Bomb", 37: "GPG40",
            38: "M7", 53: "Bazooka", 55: "Airstrike",
        }
        for wid, name in expected.items():
            assert wid in INDIRECT_WEAPON_IDS, f"{name} ({wid}) must be indirect"
            assert WP_WEAPON_NAMES.get(wid) == name, (
                f"id {wid} is {WP_WEAPON_NAMES.get(wid)!r} here, expected {name!r}"
            )

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
            holder_guid="H", kind="position_region", source="gunfire",
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
            holder_guid="H", kind="position_region", source="aim_lock",
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
