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
from typing import Callable, Iterable

from website.backend.services.clock_inputs import wave_position as _wave_position
from website.backend.services.reconstruction_accuracy import reach_bound

#: Widest a grown region may be and still support a distance claim, in units.
#:
#: ⭐ A HORIZON, NOT A CLAMP. Growth alone makes the derived distance useless
#: rather than wrong: measured over 215 holder samples, an ungated model reports
#: an interval every time, with a median width of 2,385 units and 76% of them
#: saying "he could be right on top of me". At 1,000 the number appears in 27%
#: of samples with a median width of 964. The region itself is NEVER trimmed to
#: this — only the derived distance is withheld, and the threshold is published
#: so a missing number is explicable rather than indistinguishable from
#: "no enemy known".
#:
#: ⚠️ Deliberately one tunable number, kept out of the model: the intent is to
#: try 1,000 first and possibly tighten to 500 (about 0.8 s of freshness, 10%
#: coverage, median width 481). Moving it is a one-line change and the payload
#: shows which value produced the picture.
POSITION_CLAIM_MAX_RADIUS = 1000.0

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


#: Longest reinforcement interval this project has ever recorded, in ms.
#:
#: Used only when a round's interval is unknown, as the outer bound on how long
#: "he is down" can still be true. ⚠️ Not a guess: the intervals present in
#: `proximity_spawn_timing` are 15, 20, 25, 30 and 35 seconds. Picking 30 —
#: which is what "everyone knows" ET uses — would be wrong for four rounds.
MAX_OBSERVED_REINFORCE_MS = 35_000

#: How an obituary belief's end was established. Carried into the payload so a
#: reader can tell an exact wave from a bound.
EXPIRY_VALIDATED_WAVE = "validated_wave"   # interval AND phase known: a step
EXPIRY_INTERVAL_ONLY = "interval_only"     # period known, phase not: linear
#: The wave has already passed; this belief ends only when the round does.
EXPIRY_ROUND_END = "round_end"
EXPIRY_BOUND = "bound"                     # neither: linear over the outer bound

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
    source: str                # gunfire | contact_hit | incoming_damage |
                               # public_obituary | aim_lock
    t_observed: int
    region: Region | None = None
    subject_guid: str | None = None
    roster_state: str | None = None
    #: Manifest evidence for the optional capture this came from. "core" for
    #: sources that need no feature flag.
    capability: str = "core"
    #: When this belief stops being true, and on what authority.
    #:
    #: ⛔ A roster belief with neither used to fall through to `tau is None` and
    #: return 1.0 for the rest of the round — "he is down" held at FULL
    #: confidence for ten minutes (CodeRabbit, PR #799). There is now always an
    #: end; only its basis varies.
    expires_at_ms: int | None = None
    expiry_basis: str | None = None

    @property
    def kind(self) -> str:
        """What this item actually is, read off what it carries.

        ⛔ This used to be passed in, and two call sites labelled a belief
        `position_region` while leaving `region` as None — neither input row has
        coordinates. A consumer branching on `kind` then read a missing region,
        and `nearest_known_enemy_distance` skipped the item while
        `known_enemy_count` included it (CodeRabbit, PR #799).

        Derived, the label cannot disagree with the contents.
        """
        if self.roster_state is not None:
            return "roster_state"
        if self.region is not None:
            return "subject_position" if self.subject_guid else "position_region"
        return "subject_contact" if self.subject_guid else "nonspatial_contact"

    def region_at(self, t_ms: int) -> Region | None:
        """Where the subject could be NOW, given where they were then.

        ⭐ §6.3 requires the uncertainty to grow with time, and the first
        version did not: the radius stayed at the reconstruction error for the
        belief's whole life, so a contact belief still claimed +/-44 units seven
        seconds later while the subject could be anywhere within about 2,200.
        A player is 40 units wide — the claim was roughly 50x too tight at the
        maximum age a belief can reach.

        ⛔ Only the radius grows; the centre never moves. Sliding it along a
        last-known heading would invent a direction of travel that nothing
        observed, which is the same overclaim in a different coordinate.
        """
        if self.region is None:
            return None
        grown = reach_bound(t_ms - self.t_observed)
        if not grown:
            return self.region
        return Region(self.region.x, self.region.y, self.region.z,
                      self.region.radius + grown)

    def confidence(self, t_ms: int) -> float:
        """How much of this is still worth acting on at `t_ms`.

        Three shapes, because three different things are known:

        * **Positional** beliefs fade exponentially — a location goes stale.
        * **Roster with a validated wave** is a STEP. "He is down" is true until
          his team can spawn and then it is not; a curve would leave everyone
          half-believing a corpse.
        * ⭐ **Roster without a validated phase** falls LINEARLY across one
          interval. That is what is actually known: he returns somewhere inside
          the next cycle, and with no phase every point in it is equally likely.
          A step here would claim a wave time we do not have.
        """
        if t_ms < self.t_observed:
            return 0.0
        if self.expires_at_ms is not None:
            if t_ms >= self.expires_at_ms:
                return 0.0
            if self.expiry_basis in (EXPIRY_VALIDATED_WAVE, EXPIRY_ROUND_END):
                return 1.0
            span = self.expires_at_ms - self.t_observed
            # ⚠️ UNREACHABLE, kept as a structural guard. Reaching here means
            # t_observed <= t_ms < expires_at_ms, so span > 0 always; an
            # exhaustive search over the three timestamps finds no input that
            # enters this branch, and no mutation of it can be caught by any
            # test. It stays because the division below must never be exposed
            # if either check above is ever narrowed.
            if span <= 0:
                return 0.0
            return 1.0 - (t_ms - self.t_observed) / span
        tau = DECAY_TAU_S.get(self.source)
        if tau is None:
            # ⛔ No decay law and no expiry means the belief would be permanent.
            # Nothing a player knows about another player is permanent.
            raise AssertionError(
                f"belief from {self.source!r} has neither a decay constant nor "
                f"an expiry; it would be believed forever"
            )
        return math.exp(-(t_ms - self.t_observed) / 1000.0 / tau)


#: Where a named player was at a given instant, as a region sized by how wrong
#: our reconstruction is there. Returns None when the moment cannot be
#: reconstructed — a belief then keeps its subject and loses only its place,
#: which is the honest degradation.
Locator = Callable[[str, int], "Region | None"]


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
                source="gunfire",
                t_observed=int(t_ms),
                region=Region(float(sx), float(sy), float(sz), GUNFIRE_REGION_RADIUS),
                subject_guid=None,
                capability="shot_fired",
            ))
    return out


def counts_as_known(belief: BeliefItem, t_ms: int, *, floor: float = CONFIDENCE_FLOOR) -> bool:
    """Whether this item is an enemy the holder could name RIGHT NOW.

    ⭐ ONE rule, used by both `known_enemy_count` and the payload flag. They
    were two separate expressions, and a belief could be `counts_as_known` in
    the payload while the count beside it excluded the same belief — the
    contradiction class this module has already been burned by twice.

    ⛔ `uncertain_after_down` is deliberately excluded. "His team could have
    spawned him by now" is knowledge that someone exists, not knowledge of them
    now; counting it would mean the count never falls again for the rest of the
    round.
    """
    return (
        bool(belief.subject_guid)
        and belief.roster_state != UNCERTAIN_AFTER_DOWN
        and belief.confidence(t_ms) >= floor
    )


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
        b.subject_guid for b in state.beliefs if counts_as_known(b, t_ms, floor=floor)
    }
    return len(subjects)


def _nearest(
    state: HolderState, t_ms: int, holder_pos: tuple[float, float, float],
    *, resolved: bool, floor: float,
) -> dict | None:
    # ⭐ The two bounds come from DIFFERENT beliefs, and that is the point.
    #
    # `min` is the closest anyone could be: min over lower bounds. `max` is the
    # closest anyone is GUARANTEED to be within: min over upper bounds — if one
    # belief proves an enemy is inside 600, the nearest enemy is inside 600
    # whatever the other beliefs allow. Pairing `max` with whichever belief won
    # on `min` discarded that proof and reported a distance the holder could
    # rule out (a wide [500, 1300] beside a tight [520, 600] answered 1,300),
    # which is the same overclaiming the caller's docstring forbids.
    #
    # It cannot invert: min(lo) <= lo_k <= hi_k = min(hi) for the k achieving
    # the minimum upper bound.
    lo_bound: float | None = None
    hi_bound: float | None = None
    for belief in state.beliefs:
        if belief.region is None or belief.confidence(t_ms) < floor:
            continue
        if bool(belief.subject_guid) is not resolved:
            continue
        region = belief.region_at(t_ms)
        # ⭐ Past the horizon the belief still exists and still names its
        # subject — it simply stops supporting a claim about distance. Dropping
        # it from the count as well would lose knowledge the holder really has.
        if region.radius > POSITION_CLAIM_MAX_RADIUS:
            continue
        lo, hi = region.distance_interval(*holder_pos)
        lo_bound = lo if lo_bound is None else min(lo_bound, lo)
        hi_bound = hi if hi_bound is None else min(hi_bound, hi)
    if lo_bound is None or hi_bound is None:
        return None
    return {"min": round(lo_bound, 1), "max": round(hi_bound, 1)}


def nearest_known_enemy_distance(
    state: HolderState, t_ms: int, holder_pos: tuple[float, float, float],
    *, floor: float = CONFIDENCE_FLOOR,
) -> dict | None:
    """How close the nearest enemy the holder could NAME might be.

    ⛔ Only beliefs that resolve a subject. Gunfire carries a region and no
    subject, and `known_enemy_count` excludes it on purpose — so counting it
    here produced a holder with `known_enemy_count: 0` and a populated enemy
    distance in the same payload. Two numbers on one panel, contradicting each
    other (CodeRabbit, PR #799).

    Returns None when nothing is believed. The value is an interval, never a
    scalar: a region 400 units wide seen from 900 away is "between 500 and
    1,300", and reporting 900 would be a number the holder never had.
    """
    return _nearest(state, t_ms, holder_pos, resolved=True, floor=floor)


def nearest_heard_activity_distance(
    state: HolderState, t_ms: int, holder_pos: tuple[float, float, float],
    *, floor: float = CONFIDENCE_FLOOR,
) -> dict | None:
    """How close the nearest unattributed noise was.

    ⭐ Hearing shots 900 units away IS information — it is simply not "an
    enemy". Giving it its own name lets the panel show both without the two
    contradicting each other.
    """
    return _nearest(state, t_ms, holder_pos, resolved=False, floor=floor)


def to_dict(state: HolderState, t_ms: int, holder_pos: tuple[float, float, float] | None) -> dict:
    """The holder's picture, with every channel's availability stated."""
    live = [b for b in state.beliefs if b.confidence(t_ms) >= DISPLAY_FLOOR]
    return {
        "holder_guid": state.holder_guid,
        "known_enemy_count": known_enemy_count(state, t_ms),
        "nearest_known_enemy_distance": (
            nearest_known_enemy_distance(state, t_ms, holder_pos) if holder_pos else None
        ),
        "nearest_heard_activity_distance": (
            nearest_heard_activity_distance(state, t_ms, holder_pos)
            if holder_pos else None
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
                "counts_as_known": counts_as_known(b, t_ms),
                "capability": b.capability,
                "expiry_basis": b.expiry_basis,
                # ⚠️ The GROWN region, not the stored one. Publishing the
                # observation-instant radius would hand a consumer a circle
                # that was true seconds ago and draw it as though it were true
                # now — the defect this whole field exists to correct.
                "region": (
                    {"x": grown.x, "y": grown.y, "z": grown.z,
                     "radius": round(grown.radius, 1)}
                    if (grown := b.region_at(t_ms)) else None
                ),
            }
            for b in sorted(live, key=lambda x: -x.confidence(t_ms))
        ],
        #: ⛔ Named channels, not silence. A round that could not capture gunfire
        #: has nothing to say about heard shots — and no right to say nobody
        #: heard anything.
        #: The horizon that produced the distances above. Without it a missing
        #: distance is indistinguishable from a holder who knows of nobody.
        "position_claim_max_radius": POSITION_CLAIM_MAX_RADIUS,
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


def resolve_expiry(team_clock: dict | None, death_ms: int) -> tuple[int, str]:
    """When "he is down" stops being true, and on what authority.

    `team_clock` is that team's entry from `load_round_clock`.

    ⛔ Computed PER DEATH. The first version took one absolute timestamp per
    team, but reinforcement waves repeat all round: a death at 30 s given the
    25 s wave got an expiry in its own past, so `confidence` returned 0.0 at the
    moment of death — the belief was dead on arrival (CodeRabbit, PR #799).
    """
    interval = (team_clock or {}).get("interval_ms")
    offset = (team_clock or {}).get("offset_ms")
    if interval and offset is not None:
        # Validated: the exact next landing after this death.
        _since, until = _wave_position(death_ms, int(interval), int(offset))
        return death_ms + until, EXPIRY_VALIDATED_WAVE
    if interval:
        # Period known, phase not: he is back somewhere inside one interval.
        return death_ms + int(interval), EXPIRY_INTERVAL_ONLY
    return death_ms + MAX_OBSERVED_REINFORCE_MS, EXPIRY_BOUND


def obituary_beliefs(
    deaths: Iterable[tuple],
    holders: Iterable[str],
    *,
    clock: dict | None = None,
    round_end_ms: int | None = None,
) -> list[BeliefItem]:
    """A death is announced to everyone — that is what makes it public.

    `deaths` rows are (victim_guid, victim_team, death_time_ms).
    `clock` is `load_round_clock`'s per-team mapping.

    ⚠️ At the expiry the subject becomes `uncertain_after_down`, never server
    truth: a wave says someone COULD be back, not that this GUID spawned.

    ⛔ That transition is a SECOND item, and it used to be missing entirely —
    the constant existed, nothing created it, and at the wave the belief simply
    vanished. §6.3 says the holder *retains* `uncertain_after_down`, so the
    holder went from "he is down" to knowing nothing, when what they had
    learned is "his team can have spawned him by now".

    It runs to `round_end_ms` because §6.3 makes round end public and ends every
    live-round belief. Without a round end there is no terminus to give it, so
    it is not created rather than being handed an invented one.
    """
    out: list[BeliefItem] = []
    holders = tuple(holders)
    # ⛔ One roster fact per subject, not one per death. `uncertain_after_down`
    # runs to round end, so emitting a pair per death accumulates them: three
    # rounds produced 16,472 of these against 1,092 `observed_out_of_action`.
    # Five deaths do not make a player five-times-uncertain — only the most
    # recent describes where he stands now. `deaths` is already filtered to
    # `death_time_ms <= t_ms` by the loader, so "latest" is always in the past.
    latest: dict[str, tuple] = {}
    for victim, team, t_ms in deaths:
        previous = latest.get(str(victim))
        if previous is None or int(t_ms) > int(previous[2]):
            latest[str(victim)] = (victim, team, t_ms)
    for victim, team, t_ms in latest.values():
        expiry, basis = resolve_expiry((clock or {}).get(str(team or "")), int(t_ms))
        for holder in holders:
            if holder == victim:
                continue
            out.append(BeliefItem(
                holder_guid=holder,
                source="public_obituary",
                t_observed=int(t_ms),
                subject_guid=str(victim),
                roster_state=OBSERVED_OUT_OF_ACTION,
                expires_at_ms=expiry,
                expiry_basis=basis,
            ))
            if round_end_ms is not None and expiry < int(round_end_ms):
                # Full confidence, because the wave is a PUBLIC fact and the
                # holder is certain it passed. The uncertainty lives in the
                # label — `uncertain_after_down` says nothing about where he is
                # or whether he actually spawned — not in a discounted number
                # that would read as "we are unsure the wave happened".
                out.append(BeliefItem(
                    holder_guid=holder,
                    source="public_obituary",
                    t_observed=expiry,
                    subject_guid=str(victim),
                    roster_state=UNCERTAIN_AFTER_DOWN,
                    expires_at_ms=int(round_end_ms),
                    expiry_basis=EXPIRY_ROUND_END,
                ))
    return out


def contact_beliefs(
    engagements: Iterable[tuple], *, locate: Locator | None = None,
) -> list[BeliefItem]:
    """What a fight tells the two sides — and it is not the same thing.

    `engagements` rows are (target_guid, attackers_json) where each attacker
    carries guid, weapons and first/last hit times.

    ⭐ `locate` gives the attacker WHERE as well as who. Hitting someone with a
    direct-fire weapon means seeing them, so their position at `first_hit_ms`
    is knowledge the attacker genuinely had — and without it this channel
    resolved a subject and no place, which is why `nearest_known_enemy_distance`
    was structurally incapable of returning anything but None (measured 2026-08-23:
    None in 110 of 110 holder samples across three rounds). The region is sized
    by OUR reconstruction error, not by their perception: they saw a player, we
    are the ones unsure where that player was.

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
                    source="contact_hit",
                    t_observed=int(first),
                    region=locate(str(target), int(first)) if locate else None,
                    subject_guid=str(target),
                ))
            # The victim learns they are being hit, and only that.
            out.append(BeliefItem(
                holder_guid=str(target),
                source="incoming_damage",
                t_observed=int(first),
                subject_guid=None,
            ))
    return out


def aim_lock_beliefs(
    locks: Iterable[tuple], *, locate: Locator | None = None,
) -> list[BeliefItem]:
    """The only channel that resolves WHO for a holder who was not hit.

    `locks` rows are (holder_guid, target_guid, start_ms).

    A crosshair held on an enemy is recipient-observable by construction: the
    holder was the one looking. That is why this, unlike gunfire, may carry a
    `subject_guid` — and why it is capability-gated just as hard.

    ⭐ It carries a region for the same reason: someone holding a crosshair on a
    player is looking straight at them. `locate` supplies where that player was
    at `start_ms`, sized by our reconstruction error rather than by their sight.
    """
    return [
        BeliefItem(
            holder_guid=str(holder),
            source="aim_lock",
            t_observed=int(start_ms),
            region=locate(str(target), int(start_ms)) if locate else None,
            subject_guid=str(target),
            capability="aim_lock",
        )
        for holder, target, start_ms in locks
    ]


#: Channels §6.1 names that this implementation does not read at all.
#:
#: ⛔ A channel the spec lists and the payload never mentions is the exact
#: failure §6.2 forbids: the holder looks like someone who had that channel and
#: learned nothing from it. Gating it on the manifest would be worse, not
#: better — the manifest could say `enabled` and we would then claim a channel
#: we have no generator for.
#:
#: `comm_events`: 96 rows across 2 rounds in the whole corpus, measured today
#: and unchanged since the spec was written. There is nothing to build a
#: belief from even where the flag is on.
UNREAD_CHANNELS = {
    "comm_events": (
        "voice macros are not read: proximity_comm_event holds 96 rows across "
        "2 rounds in the entire corpus, so no round can support this channel"
    ),
}


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
    # ⛔ Materialised: the loop below walks `holders` once per gated source, and
    # a generator is exhausted by the first. That left the second channel
    # untouched — no reason recorded, no beliefs dropped — and the payload then
    # looked like a proven capture (CodeRabbit, PR #799).
    # ⛔ THE UNION, NOT THE ARGUMENT. `states` can already hold a holder who is
    # NOT in `holders` — an attacker whose life ended before `t` still has a
    # contact belief, `group_by_holder` keeps that state and the payload
    # serialises it. Marking only the passed-in list left those holders with an
    # EMPTY `unavailable`, i.e. looking like players whose every channel worked
    # and who learned nothing from it — which is the one thing §6.2 forbids,
    # and the reason this function exists (Codex, PR #807).
    holders = tuple(dict.fromkeys((*holders, *states)))
    for holder in holders:
        holder_state = states.setdefault(holder, HolderState(holder_guid=holder))
        holder_state.unavailable.update(UNREAD_CHANNELS)
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
