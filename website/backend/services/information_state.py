"""§6 Layer 3: what each player could plausibly have known at time `t`.

This is the most original part of the spider web and the one most easily
overclaimed, so almost every rule here is a restriction rather than a feature.

⭐ BELIEFS ARE PER PLAYER, NEVER PER TEAM. A team-wide set would hand a player on
the far side of the map the same knowledge as the one standing next to the
fight. Team-level answers are derived by union when a team-level question is
actually asked.

⛔ WHAT THIS IS NOT

  * Not what anyone saw. Facing is unknown between shots — view angles exist
    only in `proximity_shot_fired`, and only between 2026-05-19 and 2026-08-05.
    A clear line is a NECESSARY, not sufficient, condition for having seen
    someone, so line-of-sight is an oracle upper bound and never a belief.
  * Not the server's truth. World lifecycle (revived, gibbed, tapped_out) is
    telemetry; it does not update an opponent's belief. A holder's picture of a
    downed enemy changes only on evidence that holder could observe.
  * Not complete. The players talk on Discord. That channel does not exist in
    any dataset and never will, so this is a LOWER BOUND on what a team knew,
    permanently and by construction.

⚠️ CAPABILITY IS PART OF THE DATA. Rows prove a capture happened; their absence
proves nothing. A round whose manifest does not prove the gunfire feature was on
has nothing to say about heard shots — and equally no right to say "they heard
nothing". That distinction is why the capability manifest had to exist first.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable

#: How long a positional belief stays worth acting on, per source, in seconds.
#:
#: ⛔ CHOSEN FROM THE GAME, FROZEN BEFORE ANY MEASUREMENT. §6.3 is explicit that
#: tuning these against the outcome you later test with is the same leakage as
#: P1. The reasoning, so a later reader can disagree with the reasoning rather
#: than guess at it:
#:
#:   gunfire (5 s)  a shot says someone WAS there. At ET running speeds a player
#:                  crosses a room in two to three seconds, so the location is
#:                  stale almost immediately; five seconds is roughly the point
#:                  where acting on it stops being reasonable.
#:   contact (8 s)  being hit means you are in a fight with them and they are
#:                  probably still engaged, which holds a little longer than a
#:                  noise from elsewhere.
#:   aim_lock (5 s) you had them in your crosshair — same decay as gunfire,
#:                  because it is the same kind of fact about a position.
DECAY_TAU_S: dict[str, float] = {
    "gunfire": 5.0,
    "contact_hit": 8.0,
    "incoming_damage": 8.0,
    "aim_lock": 5.0,
}

#: Below this, a belief is too faded to count as knowledge. Not a tuned value:
#: e^-1 is one time constant, which is what τ means.
CONFIDENCE_FLOOR = math.exp(-1.0)

#: Below this a belief is not shown at all.
#:
#: ⚠️ An exponential never reaches zero, so filtering on `confidence > 0` keeps
#: every belief forever: a shot heard sixty seconds ago sits in the payload at
#: 6e-06, and after ten minutes at 1e-87. The panel would accumulate every noise
#: of the round and the reader would have to know that 1e-87 means nothing.
#:
#: Displayed beliefs go down to 1%, but each one is flagged with whether it is
#: above CONFIDENCE_FLOOR — so a faded item can be drawn faint WITHOUT the panel
#: and `known_enemy_count` disagreeing about what counts as knowledge.
DISPLAY_FLOOR = 0.01

#: How far off a heard shot can be located. A player hears a direction and a
#: rough distance, not a coordinate — §6.3 forbids exposing the telemetry origin
#: as a belief point, so the region carries this radius from the start.
GUNFIRE_REGION_RADIUS = 400.0

#: Weapons whose damage does not prove the attacker resolved a target.
#:
#: §6.3: "delayed/area causes such as grenades, artillery, airstrikes and
#: landmines ... must not hand the attacker a subject they may never have seen."
#: A grenade thrown at a doorway can kill someone the thrower never saw, so a
#: hit from one is evidence about the WORLD, not about the attacker's knowledge.
#:
#: ⭐ Derived from the engine, cross-checked twice — because the last time this
#: project hand-wrote a weapon set it missed 1,120 kills. The ids come from
#: `weapon_t` in bg_public.h and the classification from `splashRadius > 0` in
#: `weaponTable` (bg_misc.c), then verified against the enum's own `///< N`
#: comments (0 mismatches) and against WP_WEAPON_NAMES in this repository.
#:
#: ⚠️ The first derivation was WRONG and looked right: the enum contains one
#: member without the `WP_` prefix (`VERYBIGEXPLOSION`, id 18), the parser's
#: pattern rejected that line without incrementing its counter, and every id
#: from 19 on came out one too low. It agreed with itself and disagreed with the
#: repository — the repository was correct. A filter that skips instead of
#: failing is how that happens.
#:
#: WP_FLAMETHROWER is included although it is aimed directly: its splash is
#: small (5/5) but including it only ever REMOVES a resolved subject, and
#: erring toward "the attacker may not have known" is the honest direction here.
INDIRECT_WEAPON_IDS: frozenset[int] = frozenset({
    4,   # WP_GRENADE_LAUNCHER
    5,   # WP_PANZERFAUST
    6,   # WP_FLAMETHROWER
    9,   # WP_GRENADE_PINEAPPLE
    13,  # WP_ARTY
    15,  # WP_DYNAMITE
    17,  # WP_MAPMORTAR
    22,  # WP_SMOKE_MARKER
    26,  # WP_LANDMINE
    27,  # WP_SATCHEL
    28,  # WP_SATCHEL_DET
    29,  # WP_SMOKE_BOMB
    34,  # WP_MORTAR
    37,  # WP_GPG40
    38,  # WP_M7
    43,  # WP_MORTAR_SET
    51,  # WP_MORTAR2
    52,  # WP_MORTAR2_SET
    53,  # WP_BAZOOKA
    55,  # WP_AIRSTRIKE
})


def resolves_a_subject(weapon_ids: Iterable[int]) -> bool:
    """Whether a hit with these weapons lets the attacker name their target.

    Conservative by construction: ANY indirect weapon in the engagement
    withholds the subject, because the per-hit sequence is not recoverable
    (`attackers` carries only first/last hit and a per-weapon count) and we
    cannot tell which weapon produced which hit.
    """
    ids = [int(w) for w in weapon_ids]
    return bool(ids) and not any(w in INDIRECT_WEAPON_IDS for w in ids)


#: Roster states a holder can hold about someone else.
OBSERVED_OUT_OF_ACTION = "observed_out_of_action"
UNCERTAIN_AFTER_DOWN = "uncertain_after_down"
POSSIBLY_ACTIVE = "possibly_active"
ROUND_OVER = "round_over"

UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class Region:
    """A place a holder could infer, with its uncertainty attached.

    Never a bare point. The centre is our telemetry; the radius is what the
    holder could actually have narrowed it to.
    """

    x: float
    y: float
    z: float
    radius: float

    def distance_interval(self, px: float, py: float, pz: float) -> tuple[float, float]:
        """Nearest and furthest this region could be from a point.

        Returned as an interval because that is what is known. Collapsing it to
        the centre distance would invent precision the holder never had.
        """
        d = math.dist((self.x, self.y, self.z), (px, py, pz))
        return max(0.0, d - self.radius), d + self.radius


@dataclass(frozen=True, slots=True)
class BeliefItem:
    """One thing one player could have known, and how it decays. §6.3."""

    holder_guid: str
    kind: str                  # position_region | roster_state | nonspatial_contact
    source: str                # gunfire | contact_hit | incoming_damage |
                               # public_obituary | aim_lock
    t_observed: int
    region: Region | None = None
    subject_guid: str | None = None
    roster_state: str | None = None
    #: Manifest evidence for the optional capture this came from. "core" for
    #: sources that need no feature flag.
    capability: str = "core"
    #: Set when the belief does not decay smoothly — a roster fact holds until
    #: the subject's team can reinforce, which the validated Layer 2 clock knows.
    expires_at_ms: int | None = None

    def confidence(self, t_ms: int) -> float:
        """How much of this is still worth acting on at `t_ms`.

        Positional beliefs fade exponentially. Roster facts do not: "he is down"
        is true until his team's next wave, and then it is not — a step, not a
        curve. Modelling that as decay would have a player half-believing a
        corpse.
        """
        if t_ms < self.t_observed:
            return 0.0
        if self.expires_at_ms is not None:
            return 1.0 if t_ms < self.expires_at_ms else 0.0
        tau = DECAY_TAU_S.get(self.source)
        if tau is None:
            return 1.0
        return math.exp(-(t_ms - self.t_observed) / 1000.0 / tau)


@dataclass(slots=True)
class HolderState:
    """Everything one player could have known at one moment."""

    holder_guid: str
    beliefs: list[BeliefItem] = field(default_factory=list)
    #: source -> why it is unavailable. A channel that could not be captured is
    #: named here rather than contributing silence.
    unavailable: dict[str, str] = field(default_factory=dict)


def _capability_state(manifest: dict | None, flag: str) -> str:
    if not manifest:
        return "unknown"
    return (manifest.get("capabilities") or {}).get(flag, "unknown")


def gunfire_beliefs(
    shots: Iterable[tuple],
    holders: dict[str, tuple[float, float, float]],
    *,
    audible_radius: float,
) -> list[BeliefItem]:
    """A shot is heard by whoever was close enough, as a REGION.

    `shots` rows are (shooter_guid, event_time_ms, x, y, z).

    ⛔ The shooter's telemetry coordinate never becomes the belief. What the
    holder gets is a circle they could have localised the noise to, and it is
    the same circle whether or not our row is exact.

    ⚠️ `subject_guid` stays None. `proximity_shot_fired` has no target, and
    firing proves a direction, not which player was perceived — so a shot can
    never resolve WHO. That is what keeps `known_enemy_count` honest.
    """
    out: list[BeliefItem] = []
    for guid, t_ms, sx, sy, sz in shots:
        for holder, (hx, hy, hz) in holders.items():
            if holder == guid:
                continue
            if math.dist((sx, sy, sz), (hx, hy, hz)) > audible_radius:
                continue
            out.append(BeliefItem(
                holder_guid=holder,
                kind="position_region",
                source="gunfire",
                t_observed=int(t_ms),
                region=Region(float(sx), float(sy), float(sz), GUNFIRE_REGION_RADIUS),
                subject_guid=None,
                capability="shot_fired",
            ))
    return out


def known_enemy_count(state: HolderState, t_ms: int, *, floor: float = CONFIDENCE_FLOOR) -> int | str:
    """Distinct enemies this holder could name — not a count of belief items.

    ⛔ §6.3 names the trap directly: `proximity_shot_fired` emits one row per
    shot, and contact evidence repeats for the same person, so counting items
    turns one enemy firing a burst into a phantom squad.

    Unresolved gunfire regions are deliberately NOT counted. They are evidence
    that someone is somewhere, which is a different fact from knowing who, and
    promoting them would reintroduce the phantom squad through the back door.
    """
    subjects = {
        b.subject_guid
        for b in state.beliefs
        if b.subject_guid and b.confidence(t_ms) >= floor
    }
    return len(subjects)


def nearest_known_enemy_distance(
    state: HolderState, t_ms: int, holder_pos: tuple[float, float, float],
    *, floor: float = CONFIDENCE_FLOOR,
) -> dict | None:
    """How close the nearest believed enemy could be — as an interval.

    Returns None when nothing is believed. A distribution is not collapsed to a
    scalar: a region 400 units wide seen from 900 away is "between 500 and
    1,300", and reporting 900 would be a number the holder never had.
    """
    best: tuple[float, float] | None = None
    for belief in state.beliefs:
        if belief.region is None or belief.confidence(t_ms) < floor:
            continue
        lo, hi = belief.region.distance_interval(*holder_pos)
        if best is None or lo < best[0]:
            best = (lo, hi)
    if best is None:
        return None
    return {"min": round(best[0], 1), "max": round(best[1], 1)}


def to_dict(state: HolderState, t_ms: int, holder_pos: tuple[float, float, float] | None) -> dict:
    """The holder's picture, with every channel's availability stated."""
    live = [b for b in state.beliefs if b.confidence(t_ms) >= DISPLAY_FLOOR]
    return {
        "holder_guid": state.holder_guid,
        "known_enemy_count": known_enemy_count(state, t_ms),
        "nearest_known_enemy_distance": (
            nearest_known_enemy_distance(state, t_ms, holder_pos) if holder_pos else None
        ),
        "beliefs": [
            {
                "kind": b.kind,
                "source": b.source,
                "subject_guid": b.subject_guid,
                "roster_state": b.roster_state,
                "t_observed": b.t_observed,
                "confidence": round(b.confidence(t_ms), 3),
                # Whether this item is inside `known_enemy_count`. Carried per
                # item so the panel can fade a belief out without ever showing
                # something the count has already discarded.
                "counts_as_known": b.confidence(t_ms) >= CONFIDENCE_FLOOR,
                "capability": b.capability,
                "region": (
                    {"x": b.region.x, "y": b.region.y, "z": b.region.z,
                     "radius": b.region.radius}
                    if b.region else None
                ),
            }
            for b in sorted(live, key=lambda x: -x.confidence(t_ms))
        ],
        #: ⛔ Named channels, not silence. A round that could not capture gunfire
        #: has nothing to say about heard shots — and no right to say nobody
        #: heard anything.
        "unavailable": dict(state.unavailable),
        "notes": [
            ("beliefs are per player and a LOWER BOUND: Discord voice is not "
             "capturable and never will be"),
            ("gunfire gives a region, never the shooter's telemetry point, and "
             "never resolves WHO fired"),
            ("line-of-sight is not included here: it is an oracle upper bound, "
             "not an observation"),
        ],
    }


def group_by_holder(beliefs: Iterable[BeliefItem]) -> dict[str, HolderState]:
    grouped: dict[str, HolderState] = defaultdict(lambda: HolderState(holder_guid=""))
    for belief in beliefs:
        state = grouped[belief.holder_guid]
        state.holder_guid = belief.holder_guid
        state.beliefs.append(belief)
    return dict(grouped)


# --- building a round's beliefs from what was recorded -----------------------


def obituary_beliefs(
    deaths: Iterable[tuple],
    holders: Iterable[str],
    *,
    wave_expiry: dict[str, int] | None = None,
) -> list[BeliefItem]:
    """A death is announced to everyone — that is what makes it public.

    `deaths` rows are (victim_guid, victim_team, death_time_ms).

    ⭐ The belief expires at the victim's team's next reinforcement wave, not on
    a decay curve. "He is down" is true until his team can spawn and then it is
    not — a step, not a fade. Modelling it as decay would leave every player
    half-believing a corpse forever.
    ⚠️ At the wave it becomes `uncertain_after_down`, never server truth: a wave
    says someone COULD be back, not that this GUID spawned.
    """
    out: list[BeliefItem] = []
    holders = list(holders)
    for victim, team, t_ms in deaths:
        expiry = (wave_expiry or {}).get(str(team or ""))
        for holder in holders:
            if holder == victim:
                continue
            out.append(BeliefItem(
                holder_guid=holder,
                kind="roster_state",
                source="public_obituary",
                t_observed=int(t_ms),
                subject_guid=str(victim),
                roster_state=OBSERVED_OUT_OF_ACTION,
                expires_at_ms=expiry,
            ))
    return out


def contact_beliefs(engagements: Iterable[tuple]) -> list[BeliefItem]:
    """What a fight tells the two sides — and it is not the same thing.

    `engagements` rows are (target_guid, attackers_json) where each attacker
    carries guid, weapons and first/last hit times.

    ⭐ Asymmetric on purpose (§6.3):
      * the ATTACKER may name their target, but only for direct-fire weapons —
        a grenade can kill someone the thrower never saw;
      * the VICTIM gets `nonspatial_contact` and nothing more. No bearing, no
        attacker identity. Nothing in the data records a perceived direction,
        and inventing one is exactly the overclaim this layer exists to avoid;
      * TEAMMATES get nothing. Proximity is not knowledge.
    """
    out: list[BeliefItem] = []
    for target, attackers in engagements:
        for att in (attackers or []):
            guid = att.get("guid")
            if not guid:
                continue
            weapons = [int(w) for w in (att.get("weapons") or {})]
            first = att.get("first_hit_ms")
            if first is None:
                continue
            if resolves_a_subject(weapons):
                out.append(BeliefItem(
                    holder_guid=str(guid),
                    kind="position_region",
                    source="contact_hit",
                    t_observed=int(first),
                    subject_guid=str(target),
                ))
            # The victim learns they are being hit, and only that.
            out.append(BeliefItem(
                holder_guid=str(target),
                kind="nonspatial_contact",
                source="incoming_damage",
                t_observed=int(first),
                subject_guid=None,
            ))
    return out


def aim_lock_beliefs(locks: Iterable[tuple]) -> list[BeliefItem]:
    """The only channel that resolves WHO for a holder who was not hit.

    `locks` rows are (holder_guid, target_guid, start_ms).

    A crosshair held on an enemy is recipient-observable by construction: the
    holder was the one looking. That is why this, unlike gunfire, may carry a
    `subject_guid` — and why it is capability-gated just as hard.
    """
    return [
        BeliefItem(
            holder_guid=str(holder),
            kind="position_region",
            source="aim_lock",
            t_observed=int(start_ms),
            subject_guid=str(target),
            capability="aim_lock",
        )
        for holder, target, start_ms in locks
    ]


def apply_capability(
    states: dict[str, HolderState],
    manifest: dict | None,
    holders: Iterable[str],
) -> None:
    """Mark every channel the round cannot support, and drop its beliefs.

    ⛔ The rule that made the capability manifest worth building: a round whose
    manifest does not PROVE a feature was on has nothing to say through that
    channel — and no right to say the players learned nothing from it. The
    channel is named in `unavailable`; it never becomes silence.
    """
    gated = {"gunfire": "shot_fired", "aim_lock": "aim_lock"}
    for source, flag in gated.items():
        state = _capability_state(manifest, flag)
        if state == "enabled":
            continue
        reason = (
            f"{flag} capture was not enabled for this round"
            if state == "disabled"
            else f"{flag} capture cannot be proven for this round "
                 f"(manifest says {state})"
        )
        for holder in holders:
            holder_state = states.setdefault(holder, HolderState(holder_guid=holder))
            holder_state.unavailable[source] = reason
            holder_state.beliefs = [
                b for b in holder_state.beliefs if b.source != source
            ]
