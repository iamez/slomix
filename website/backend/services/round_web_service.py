"""Layer 1 of the spider web — a per-moment relational reconstruction of a round.

⛔ RECONSTRUCTION ONLY. Spec §4.6: "If it produces a number that ranks players,
it is out of scope." Nothing here enters a leaderboard, a rating or a composite;
that needs §8, the protocol that retired 13 of 18 `prox_score` metrics — two of
which were ranking players backwards.

WHAT THIS IS. For a time `t`, the available position/state of each trackable
player, the relationships among valid states, and explicit gaps. Spec §1: "It
never fills a missing active player with silence."

WHY IT IS A SIBLING AND NOT AN EDIT. Spec §4.1: "The web extends this module or
a sibling that imports it. Do not re-implement slicing." So this file imports
`replay_service` and reuses its query helpers and its hard-won
`_TRACK_ROUND_JOIN`. It does NOT change `replay_service`: the replay page
depends on that module's current behaviour, and §4.4 says so explicitly.

THE THREE THINGS THIS FIXES, all of which are invisible to a replay slider and
fatal to a relational layer:

1. **Which life.** `get_player_positions` walks lives ordered by ascending
   `spawn_time_ms` and `break`s on the first match, so it deterministically
   picks the EARLIEST overlapping life — the wrong one (§4.3). Here the latest
   spawn wins, ties break on the greatest id, and the conflict is counted and
   exposed rather than hidden.

   Scale, measured 2026-08-21 (the spec's 3,674 pairs / 49 rounds is from July;
   there is more data now): **4,757 overlapping pairs across 87 rounds**. On a
   random sample of 25 rounds the two rules disagree on **1.83%** of living
   player-slices; on the eight rounds with the most overlap, **43.96%**. Both
   numbers are true and neither alone is honest.

2. **Which sample.** `_find_position_at_time` returns whichever neighbour is
   nearer, so it can answer with a position from AFTER `t`. On a slider nobody
   notices. In a snapshot it means one player's position comes from the future
   while another's comes from the past — and any relationship computed between
   them is fiction. Here the rule is floor, never nearest, with `stale_ms`
   recorded (§4.4).

3. **Velocity.** The track writer stores scalar `speed` only, so direction has
   to be derived — from two causal samples of the SAME life, never bridging
   lives, never looking ahead (§4.4.1). When it cannot be derived honestly the
   answer is null plus a machine-readable reason, never a clamped guess.

⚠️ CAPTURE POLICY IS PARTLY KNOWN, AND NEVER DECLARED. This paragraph used to
say `proximity_processed_files.capabilities` was NULL in all 828 rows. That
stopped being true the day #795 landed and the sentence stayed — measured
today, **798 of 838 files carry a manifest** (back to 2026-03-24) and 40 do
not, the most recent of those from 2026-08-23, so a missing manifest is not
simply "an old file".

⭐ And every one of the 798 has `source = "sections_observed"` — ZERO are
`declared`. The manifest is INFERRED from which sections produced rows, which
is why a capability has three states and not two: a section with no rows means
"nothing happened" or "the sensor was off", and the file cannot tell you which.
That is also the whole of A6 that exists; per-sensor schedule, interval,
integration rule and completeness are still absent (spec §12, A6).

So `mode` is `"unknown"` for a real minority rather than for everything, the
staleness tolerance still has no default the data can justify — the caller
supplies one or gets everything back with its staleness stated — and absence
of a capability is `unavailable`, never zero (§6.2).
"""

from __future__ import annotations

import json
import math
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from proximity.parser.capability_manifest import FEATURE_FLAGS, is_declared
from proximity.parser.capability_manifest import UNKNOWN as UNKNOWN_STATE
from shared.round_time import round_duration_sql
from website.backend.logging_config import get_app_logger
from website.backend.services.clock_inputs import (
    clock_validation_payload,
    fetch_clock_lives_and_revives,
    fetch_timing_observations,
    wave_position,
)
from website.backend.services.information_state import (
    HolderState,
    Locator,
    Region,
    aim_lock_beliefs,
    apply_capability,
    contact_beliefs,
    group_by_holder,
    gunfire_beliefs,
    obituary_beliefs,
)
from website.backend.services.information_state import to_dict as belief_payload
from website.backend.services.reconstruction_accuracy import (
    MEASUREMENT as ACCURACY_MEASUREMENT,
)
from website.backend.services.reconstruction_accuracy import (
    position_error,
)
from website.backend.services.reconstruction_accuracy import (
    to_dict as accuracy_to_dict,
)
from website.backend.services.reinforcement_clock import validate_round_clocks
from website.backend.services.replay_service import (
    _TRACK_ROUND_JOIN,
    _ensure_path_list,
    _safe_float,
)
from website.backend.utils.et_constants import strip_et_colors

logger = get_app_logger("service.round_web")


# The tracker leaves an engagement open until this timeout even when nobody has
# fired since. Spec §4.5: "So 'engagement open at t' can mean 'was shot at up to
# fifteen seconds ago and has been standing still since'." The flag is therefore
# named `recently_contested`, not `under_attack`.
ENGAGEMENT_STALE_TIMEOUT_MS = 15_000

# A physical sanity cap for derived velocity. ET's ground speed tops out well
# below this; the cap exists to catch teleports and bad samples, and a sample
# that exceeds it yields null + a reason rather than being clamped into
# plausibility (§4.4.1).
VELOCITY_SANITY_CAP_UPS = 1_200.0

# How far the derived horizontal magnitude may sit from the stored scalar speed
# before we refuse to publish it. Both endpoints are checked.
#
# MEASURED, not chosen (§4.4.1 asks for "a measured tolerance"). The stored
# `speed` is INSTANTANEOUS at the sample; the derived magnitude is the AVERAGE
# over the interval between two samples. At a 200 ms cadence a player who starts,
# stops or turns inside that window makes the two legitimately disagree, so the
# check can only catch the implausible, not the ordinary.
#
# Distribution of |derived - stored| / stored over 932 ordinary samples from 25
# random rounds (2026-08-21): p50 0.069, p75 0.261, p90 0.596, p95 0.834,
# p99 2.434. A first guess of 0.5 rejected 13.7% of perfectly ordinary movement.
# 2.5 sits at the 99th percentile: it still catches a derived value several times
# its own measured speed, and stops calling normal acceleration a fault.
VELOCITY_SPEED_TOLERANCE = 2.5


@dataclass(frozen=True, slots=True)
class CapturePolicy:
    """What the file itself proves about how it was captured.

    Every field defaults to the honest answer for today's data: unknown. Spec
    §4.2: "A policy field being absent is `unknown`, not the current repo
    default."
    """

    mode: str = "unknown"
    observation_interval_ms: int | None = None
    enabled_capabilities: dict[str, Any] = field(default_factory=dict)
    policy_version: str | None = None
    source: str = "absent"
    #: flag -> "enabled" | "disabled" | "unknown". THREE states, never two: a
    #: round whose tracker predates the capability declaration can prove a
    #: capture was on (its section carried rows) but can never prove one was
    #: off, and collapsing that to a boolean turns missing telemetry into a
    #: claim about the match.
    # ⛔ EVERY known flag, defaulting to `unknown` — not an empty map. An empty
    # map made a consumer's capability section vanish entirely for rounds whose
    # manifest could not be resolved, which is the exact failure the manifest
    # exists to prevent: the page went quiet instead of saying it could not tell
    # whether `shot_fired` or `aim_lock` were on. Silence reads as "nothing to
    # report"; `unknown` reads as "we cannot tell" (Codex, #804).
    #
    # ⚠️ THIS is the field the endpoint serialises. The first attempt at this
    # fix initialised `enabled_capabilities` above, which nothing publishes, so
    # the payload still carried `{}` — and the runtime check missed it because
    # both rounds I tried HAVE manifests and never take this path.
    capabilities: dict[str, str] = field(
        default_factory=lambda: dict.fromkeys(FEATURE_FLAGS, "unknown"))
    #: How many manifests this round resolved to. Normally 1; a second means
    #: two processed files map to the same round (1 round in 776 on the dev
    #: corpus).
    manifest_count: int = 0
    #: How many individual flags those manifests disagree about. Each disputed
    #: flag becomes `unknown`, because we cannot tell which file the rows came
    #: from, and silently picking one would be a guess wearing a fact's clothes.
    #:
    #: ⚠️ This counts FLAGS, not files — the two are different numbers and an
    #: earlier version reported the flag count under a file-count name
    #: (CodeRabbit, PR #795).
    conflicting_flags: int = 0


@dataclass(slots=True)
class PlayerState:
    guid: str
    name: str
    team: str | None
    player_class: str | None
    x: float | None
    y: float | None
    z: float | None
    health: int
    weapon: Any
    stance: Any
    speed: float | None
    alive: bool
    track_id: int | None
    stale_ms: int
    overlap_conflict: bool
    vx: float | None = None
    vy: float | None = None
    vz: float | None = None
    velocity_stale_ms: int | None = None
    velocity_reason: str | None = None


@dataclass(slots=True)
class Edge:
    a_guid: str
    b_guid: str
    kind: str  # "teammate" | "opponent"
    distance: float
    recently_contested: bool = False


@dataclass(slots=True)
class Snapshot:
    t_ms: int
    players: dict[str, PlayerState]
    edges: list[Edge]
    # Number of players whose life was ambiguous at this moment (more than one
    # overlapping candidate), NOT the number of overlapping pairs.
    overlap_conflicts: int
    # guid -> why this player has no state here. Never empty by omission: a
    # player is either in `players` or in `gaps`, never in neither.
    gaps: dict[str, str] = field(default_factory=dict)


def find_position_floor(path: list, target_ms: int) -> tuple[dict | None, int, int]:
    """The last sample at or before `target_ms`, how stale it is, and its index.

    FLOOR, never nearest. `replay_service._find_position_at_time` compares the
    two neighbours and returns the closer one, which for a target between
    samples can be the LATER one — a position from after the moment being asked
    about. That is the single most important difference between a replay slider
    and a relational layer, so it gets its own function rather than a flag on
    the existing one: the replay page depends on the current behaviour and §4.4
    forbids changing it underneath.

    ⚠️ Duplicate timestamps are real: 392 of 4,000 sampled tracks carry at least
    two samples with the same `time` (measured 2026-08-21). `bisect_right` lands
    after the whole run, so this returns the LAST sample of a duplicate group —
    the most recently written state for that instant. That is a choice, so it is
    written down rather than left to be rediscovered.

    Returns (sample, stale_ms, index). No sample at or before `target_ms` yields
    (None, -1, -1) — the player has no causal state yet, which is a gap to
    report, not a zero to invent. The index is returned because the caller needs
    it for velocity and recomputing it means walking the path a second time.
    """
    if not path:
        return None, -1, -1
    times = [s.get("time", 0) for s in path]
    idx = bisect_right(times, target_ms)
    if idx == 0:
        return None, -1, -1
    sample = path[idx - 1]
    return sample, int(target_ms - (sample.get("time", 0) or 0)), idx - 1


def select_life(track_list: list, t_ms: int) -> tuple[Any | None, bool, bool]:
    """Pick the one life that was live at `t_ms`, and say whether it was ambiguous.

    Spec §4.3. Candidates are `spawn_time_ms <= t < death_time_ms` — HALF-OPEN,
    because at `t == death_time_ms` the zero-health sample is corpse/event data
    and not a living state. Among candidates the greatest `spawn_time_ms` wins
    (the later spawn is the more recent state) and ties break on the greatest
    id. Determinism matters more than being right in a genuinely ambiguous case;
    the conflict flag is what makes the ambiguity visible.

    Returns (track, alive, overlap_conflict). When nothing was live, falls back
    to the most recently ended life so a dead player still has a last known
    position, with alive=False.

    Rows are (guid, name, team, class, spawn_ms, death_ms, path, map, id).
    """
    candidates = [
        t for t in track_list
        if (t[4] or 0) <= t_ms and (t[5] is None or t_ms < t[5])
    ]
    if candidates:
        chosen = max(candidates, key=lambda t: ((t[4] or 0), (t[8] or 0)))
        return chosen, True, len(candidates) > 1

    ended = [t for t in track_list if t[5] is not None and t[5] <= t_ms]
    if ended:
        return max(ended, key=lambda t: (t[5], (t[8] or 0))), False, False
    return None, False, False


def derive_velocity(
    path: list, sample_index: int, max_dt_ms: int | None
) -> tuple[float | None, float | None, float | None, int | None, str | None]:
    """Direction from two causal samples of the same life, or an honest null.

    Spec §4.4.1. The writer serialises scalar `speed` only, so `vx/vy/vz` cannot
    be read from the row. They are derived from the selected sample and the one
    immediately before it IN THE SAME LIFE — never across lives, never with a
    future sample, never interpolated.

    Every refusal carries a machine-readable reason instead of a plausible
    number. A clamped velocity is a fabricated one.
    """
    if sample_index <= 0:
        return None, None, None, None, "no_causal_predecessor"
    cur = path[sample_index]
    cur_time = cur.get("time", 0) or 0

    # Step back over a run of identical timestamps rather than refusing on the
    # first one. 9.8% of tracks carry duplicate times, and the sample directly
    # behind the chosen one is often its own twin — dt would be 0 and a real,
    # derivable velocity would be thrown away for a bookkeeping artefact. What
    # is NOT allowed is bridging a gap or a life boundary, which the max_dt
    # check below still enforces.
    prev_index = sample_index - 1
    while prev_index >= 0 and (path[prev_index].get("time", 0) or 0) >= cur_time:
        prev_index -= 1
    if prev_index < 0:
        return None, None, None, None, "no_strictly_earlier_sample"

    prev = path[prev_index]
    dt_ms = int(cur_time - (prev.get("time", 0) or 0))
    if dt_ms <= 0:
        return None, None, None, None, "non_monotonic_samples"
    if max_dt_ms is not None and dt_ms > max_dt_ms:
        return None, None, None, None, f"gap_exceeds_max_dt_{dt_ms}ms"

    dt_s = dt_ms / 1000.0
    try:
        # `z` is required, not defaulted. Substituting 0 for a missing height
        # fabricates a vertical velocity out of nothing — the same substitution
        # that was removed from build_edges, missed here on the first pass
        # (CodeRabbit, PR #792).
        vx = (float(cur["x"]) - float(prev["x"])) / dt_s
        vy = (float(cur["y"]) - float(prev["y"])) / dt_s
        vz = (float(cur["z"]) - float(prev["z"])) / dt_s
    except (KeyError, TypeError, ValueError):
        return None, None, None, None, "incomplete_coordinates"

    horizontal = math.hypot(vx, vy)
    if horizontal > VELOCITY_SANITY_CAP_UPS:
        return None, None, None, None, f"exceeds_sanity_cap_{horizontal:.0f}ups"

    # Cross-check against the scalar speed the tracker did store, at both
    # endpoints. A derived direction that disagrees with the measured magnitude
    # is describing movement that did not happen.
    for endpoint in (prev, cur):
        stored = _safe_float(endpoint.get("speed"))
        if stored is None or stored <= 0:
            continue
        if abs(horizontal - stored) > VELOCITY_SPEED_TOLERANCE * max(stored, 1.0):
            return None, None, None, None, "disagrees_with_stored_speed"

    return vx, vy, vz, dt_ms, None


def build_snapshot(
    tracks_by_guid: dict[str, list],
    t_ms: int,
    *,
    engagements: list | None = None,
    max_stale_ms: int | None = None,
    velocity_max_dt_ms: int | None = None,
) -> Snapshot:
    """One moment: who was where, how they related, and who is missing and why.

    `max_stale_ms` is the caller's tolerance, not ours. With capture policy
    unknown for every historical round (see module docstring) there is no
    default the data can justify, so None means "return everything and state its
    staleness" and a value means "exclude states older than this".

    ⭐ EXCLUDED IS NOT ABSENT. Every player who does not make it into `players`
    lands in `gaps` with a reason. An earlier version of this function simply
    `continue`d, which made a player vanish — and a caller could not tell "was
    not in this round" from "was filtered out by the tolerance I passed". Spec
    §1: "It never fills a missing active player with silence." Dropping someone
    silently IS that silence, and the tolerance path makes it the caller's own
    parameter that erases them.
    """
    players: dict[str, PlayerState] = {}
    gaps: dict[str, str] = {}
    conflicts = 0

    for guid, track_list in tracks_by_guid.items():
        track, alive, conflict = select_life(track_list, t_ms)
        if track is None:
            gaps[guid] = "no_life_at_or_before_t"
            continue
        conflicts += 1 if conflict else 0

        path = _ensure_path_list(track[6])
        # A dead player is shown at the position they died in. The LOOKUP uses
        # their death time, but the STALENESS is always measured against t_ms —
        # an earlier version reported it against the death time, so someone who
        # died five minutes ago came back with stale_ms near zero and the
        # caller's max_stale_ms could never exclude them. Staleness has to mean
        # "how old is this state at the moment being asked about", or the
        # tolerance is decorative (CodeRabbit, PR #792).
        lookup_ms = t_ms if alive else int(track[5] or t_ms)
        sample, _lookup_stale, sample_idx = find_position_floor(path, lookup_ms)
        if sample is None:
            gaps[guid] = "no_sample_at_or_before_t"
            continue
        stale_ms = int(t_ms - (sample.get("time", 0) or 0))
        if max_stale_ms is not None and stale_ms > max_stale_ms:
            gaps[guid] = f"exceeds_max_stale_{stale_ms}ms"
            continue

        vx = vy = vz = None
        v_dt = v_reason = None
        if alive:
            vx, vy, vz, v_dt, v_reason = derive_velocity(
                path, sample_idx, velocity_max_dt_ms
            )
        else:
            v_reason = "not_alive"

        players[guid] = PlayerState(
            guid=guid,
            name=strip_et_colors(track[1]),
            team=track[2],
            player_class=track[3],
            x=_safe_float(sample.get("x")),
            y=_safe_float(sample.get("y")),
            z=_safe_float(sample.get("z")),
            health=int(sample.get("health", 0) or 0) if alive else 0,
            weapon=sample.get("weapon"),
            stance=sample.get("stance"),
            speed=_safe_float(sample.get("speed")),
            alive=alive,
            track_id=track[8],
            stale_ms=stale_ms,
            overlap_conflict=conflict,
            vx=vx, vy=vy, vz=vz,
            velocity_stale_ms=v_dt,
            velocity_reason=v_reason,
        )

    return Snapshot(
        t_ms=t_ms,
        players=players,
        edges=build_edges(players, t_ms, engagements or []),
        overlap_conflicts=conflicts,
        gaps=gaps,
    )


def _contested_guids(engagements: list, t_ms: int) -> set[str]:
    """Targets whose engagement is open at `t`, with the per-attacker filter.

    Spec §4.5: an engagement may link its target only to an attacker whose
    stored `first_hit_ms <= t`. The final attacker list includes people who
    joined later, so omitting that filter leaks future participation into the
    past — the exact kind of error that makes a reconstruction confidently
    wrong.

    ⚠️ This says "recently contested", never "under attack": the tracker holds
    an engagement open for ENGAGEMENT_STALE_TIMEOUT_MS after the last hit.
    """
    contested: set[str] = set()
    for eng in engagements:
        start, end, target = eng[0], eng[1], eng[2]
        if start is None or end is None or not target:
            continue
        if not (start <= t_ms <= end):
            continue
        # `attackers` is JSONB but this adapter hands it back as text, exactly
        # like `path`. `_ensure_path_list` is the repo's existing answer to that
        # (spec §4.1 lists it as reusable), so use it rather than adding a
        # second normalisation that can drift from the first.
        for att in _ensure_path_list(eng[3]):
            if not isinstance(att, dict):
                continue
            first_hit = att.get("first_hit_ms")
            if first_hit is not None and first_hit <= t_ms:
                contested.add(target)
                break
    return contested


def build_edges(players: dict[str, PlayerState], t_ms: int, engagements: list) -> list[Edge]:
    """Pairwise relationships among living players.

    Geometric separation only. Spec §4.5 is explicit that this "is not tactical
    support distance through the map": a teammate twenty units away through a
    wall or one floor up is near, and useless. Calling it separation rather than
    isolation keeps that honest until W4b (navigable topology) exists.
    """
    contested = _contested_guids(engagements, t_ms)
    # All three coordinates, checked once. An earlier version guarded only `x`
    # and then wrote `a.z or 0.0`, which put a player with no height at ground
    # level — two people on different floors would have come out as neighbours.
    # Never fired on real data (0 of 416,531 samples carry a null coordinate),
    # but a module whose whole promise is that it invents nothing cannot carry
    # a substitution in it. No complete position, no edge.
    alive = [p for p in players.values() if p.alive and _has_position(p)]
    return [
        Edge(
            a_guid=a.guid,
            b_guid=b.guid,
            kind="teammate" if a.team == b.team else "opponent",
            distance=math.dist((a.x, a.y, a.z), (b.x, b.y, b.z)),
            recently_contested=(a.guid in contested or b.guid in contested),
        )
        for i, a in enumerate(alive)
        for b in alive[i + 1:]
    ]


def _has_position(p: PlayerState) -> bool:
    """One definition of "placeable", used everywhere.

    `build_edges` and this function disagreed once: edges required all three
    coordinates while separation checked only `x`, so a player missing `y` or
    `z` silently became "no living teammate" instead of "no position"
    (CodeRabbit, PR #792).
    """
    return p.x is not None and p.y is not None and p.z is not None


def nearest_teammate_separation(snapshot: Snapshot) -> dict[str, float | None]:
    """Straight-line distance to the nearest living teammate, per player.

    None when a player has no living teammate — a real state (last man standing),
    not a distance of zero. Players without a complete position are absent from
    the result entirely rather than reported as None, because None here has one
    meaning and it is not "we could not place them".
    """
    out: dict[str, float | None] = {}
    for guid, p in snapshot.players.items():
        if not p.alive or not _has_position(p):
            continue
        mates = [
            e.distance for e in snapshot.edges
            if e.kind == "teammate" and guid in (e.a_guid, e.b_guid)
        ]
        out[guid] = min(mates) if mates else None
    return out


async def load_round_tracks(db, round_id: int) -> dict[str, list]:
    """Every life in the round, grouped by player.

    Reuses `_TRACK_ROUND_JOIN` from replay_service rather than re-deriving the
    linkage: that join is the fix for track rows being pulled into several
    rounds at once (24,428 rows bound to more than one round before it), and
    re-implementing it here would be a second place for that bug to come back.

    `pt.id` is selected as the ninth column because Layer 1 needs it twice — as
    `PlayerState.track_id`, and as the tie-break when two lives overlap.
    """
    rows = await db.fetch_all(f"""
        SELECT pt.player_guid, pt.player_name, pt.team, pt.player_class,
               pt.spawn_time_ms, pt.death_time_ms, pt.path, pt.map_name, pt.id
        FROM player_track pt
{_TRACK_ROUND_JOIN}
        WHERE r.id = $1
        ORDER BY pt.player_guid, pt.spawn_time_ms
    """, (round_id,))
    # A plain dict, not the defaultdict used to build it: a caller reaching for
    # a guid that was not in the round should get a KeyError, not a silently
    # created empty life list that reads as "this player had no lives".
    grouped: dict[str, list] = defaultdict(list)
    for row in rows:
        grouped[row[0]].append(row)
    return dict(grouped)


async def load_round_engagements(db, round_id: int) -> list:
    """Engagements with their attacker lists, for the participation edges."""
    return await db.fetch_all("""
        SELECT start_time_ms, end_time_ms, target_guid, attackers
        FROM combat_engagement
        WHERE round_id = $1 AND start_time_ms IS NOT NULL AND end_time_ms IS NOT NULL
    """, (round_id,))


def _player_to_dict(st: PlayerState) -> dict[str, Any]:
    """Serialise a state without hiding anything the caller needs to judge it.

    `stale_ms`, `overlap_conflict` and `velocity_reason` travel with the values
    they qualify. A consumer that drops them is choosing to; a payload that
    omits them would be deciding for everyone (§1: "It never fills a missing
    active player with silence").
    """
    return {
        "guid": st.guid, "name": st.name, "team": st.team, "class": st.player_class,
        "x": st.x, "y": st.y, "z": st.z,
        "health": st.health, "weapon": st.weapon, "stance": st.stance,
        "speed": st.speed, "alive": st.alive,
        "track_id": st.track_id,
        "stale_ms": st.stale_ms,
        "overlap_conflict": st.overlap_conflict,
        # Measured, not assumed, and attached to the player rather than the page:
        # a fresh uncontested sample is good to ~12 units, a contested one to
        # ~875. Drawing both with the same confidence was the prototype's real
        # weakness. None when there is no position to qualify.
        "position_error": accuracy_to_dict(
            position_error(st.stale_ms, overlap_conflict=st.overlap_conflict)
        ) if _has_position(st) else None,
        "vx": st.vx, "vy": st.vy, "vz": st.vz,
        "velocity_stale_ms": st.velocity_stale_ms,
        "velocity_reason": st.velocity_reason,
    }


async def load_capture_policy(db, round_id: int) -> CapturePolicy:
    """What the round's source file says it was able to record.

    `proximity_processed_files` has no round_id, so the bridge is `round_key`
    (migration 062): `date|map|round|start_unix`. Only its LAST field is used.

    ⭐ Matching the whole key would be wrong. The round number in it comes from
    the parser's own normalisation, and two of the 184 keys written so far
    disagree with what re-parsing the same file produces today — so a whole-key
    match would silently drop those rounds. `round_start_unix` alone identifies
    950 of 951 rounds; the single colliding pair returns two manifests and takes
    the disagreement path below, which is the honest outcome rather than a
    coin flip. 828 rows make the unindexed cast free.

    A round with no manifest keeps the default, which is `unknown` on every
    field. That is not a placeholder to be improved away: 30 processed files
    have no raw file left to read, and a round we cannot characterise must say
    so rather than inherit the software's current defaults (§4.2).
    """
    rows = await db.fetch_all("""
        SELECT f.capabilities
        FROM rounds r
        JOIN proximity_processed_files f
          ON split_part(f.round_key, '|', 4) = r.round_start_unix::text
        WHERE r.id = $1
          AND f.capabilities IS NOT NULL
          AND r.round_start_unix IS NOT NULL
          AND r.round_start_unix > 0
        ORDER BY f.filename
    """, (round_id,))
    manifests: list[dict] = []
    for row in rows:
        value = row[0]
        if isinstance(value, str):
            # A value that will not parse is not a manifest. Dropping it leaves
            # the round `unknown`, which is the truth about a round we cannot
            # characterise; raising here would turn one corrupt row into a 500
            # for a page whose entire job is to keep working while saying what
            # it does not know.
            try:
                value = json.loads(value)
            except ValueError:
                logger.warning(
                    "round %s: unparseable capabilities manifest, ignoring", round_id
                )
                continue
        if isinstance(value, dict):
            manifests.append(value)
    if not manifests:
        return CapturePolicy()

    # A declared manifest is exact where an inferred one is a lower bound, so
    # it leads regardless of filename order. Ordering is otherwise by filename
    # (see the query) so the same round always answers the same way — `head`
    # used to be whichever row the database happened to return first, which made
    # `mode`, `source` and the cadence non-deterministic on the rare round with
    # two files (CodeRabbit, PR #795).
    head = next((m for m in manifests if is_declared(m)), manifests[0])

    capabilities: dict[str, str] = dict(head.get("capabilities") or {})
    conflicting_flags = 0
    for other in manifests:
        if other is head:
            continue
        for flag, state in (other.get("capabilities") or {}).items():
            if flag not in capabilities:
                capabilities[flag] = state
            elif capabilities[flag] != state and capabilities[flag] != UNKNOWN_STATE:
                capabilities[flag] = UNKNOWN_STATE
                conflicting_flags += 1

    # The cadence is a fact about the file, so two files disagreeing about it
    # means we do not know this round's cadence — not that one of them wins.
    intervals = {
        m.get("position_sample_interval_ms")
        for m in manifests
        if m.get("position_sample_interval_ms")
    }
    interval = intervals.pop() if len(intervals) == 1 else None
    sources = {m.get("source") for m in manifests if m.get("source")}
    # Same rule for every scalar, `manifest_version` included: one answer or
    # none. Taking this one from `head` while the others fell back to unknown
    # would leave a single field describing one file and the rest describing
    # the round (CodeRabbit, PR #795).
    versions = {
        str(m.get("manifest_version")) for m in manifests
        if m.get("manifest_version") is not None
    }

    return CapturePolicy(
        mode="fixed" if interval else "unknown",
        observation_interval_ms=interval,
        capabilities=capabilities,
        policy_version=versions.pop() if len(versions) == 1 else None,
        source=(sources.pop() if len(sources) == 1 else "conflicting"),
        manifest_count=len(manifests),
        conflicting_flags=conflicting_flags,
    )


async def load_round_clock(db, round_id: int, t_ms: int) -> dict:
    """The reinforcement clock for both teams, and where `t_ms` sits in it.

    §5 calls the clock the round's third opponent: a fight is worth taking or
    not depending on how long the loser stays dead, and that is a property of
    the moment, not of the players. This is what the snapshot needs to say it.

    Every team gets an entry, including one whose clock could not be
    established — a missing key would read as "no clock here" when the truth is
    "we could not verify one", and §5.2 draws precisely that line. `phase_ms`
    and `time_to_next_wave_ms` appear only for a **validated** clock, because
    they are computed from the offset the protocol refuses to publish otherwise.
    """
    observations = await fetch_timing_observations(db, round_id)
    lives, revives, _track_end = await fetch_clock_lives_and_revives(db, round_id)
    if not observations:
        # No eligible spawn-timing rows: either the round fails the strict gate
        # (bot round, invalid, not a played half) or nobody died. Both are
        # "unavailable", never a silently absent clock.
        return {
            team: {"status": "unavailable",
                   "reason": "no eligible spawn-timing rows for this round"}
            for team in ("AXIS", "ALLIES")
        }

    validations = validate_round_clocks(observations, lives, revives)
    clock: dict[str, dict] = {}
    for team in ("AXIS", "ALLIES"):
        validation = validations.get(team)
        if validation is None:
            clock[team] = {"status": "unavailable",
                           "reason": "no timing observations for this team"}
            continue
        payload = clock_validation_payload(validation)
        if validation.status == "validated" and validation.interval_ms:
            phase, remaining = wave_position(
                t_ms, validation.interval_ms, validation.offset_ms or 0
            )
            payload["phase_ms"] = phase
            payload["time_to_next_wave_ms"] = remaining
        clock[team] = payload
    return clock


def restrict_clock_to_pov(clock: dict, pov_team: dict | None) -> dict:
    """The opposing team's clock is an oracle diagnostic, so a team view loses it.

    §6.3: "The holder's enemy clock begins `unknown`; it may become a phase
    distribution only after a timestamped cue that this recipient could
    observe... With no recipient-specific cue, exact enemy phase and
    reachability remain oracle-only." §5.6 says the same from the other end.

    We have no such cue: no capability-proven sight of an enemy wave, no
    captured communication. So the enemy clock is not ours to publish here.

    ⛔ NAMED, NOT DELETED — the same rule `withheld_by_pov` follows. A missing
    key reads as "this team had no clock", which is a different and false
    statement. `interval_ms` stays because §6.3 itself treats the interval as
    known ("constrains phase modulo the KNOWN interval"); what a cue would buy
    you is the phase, and the phase is what goes.
    """
    if not pov_team:
        return clock
    own = pov_team["team"]
    out: dict[str, dict] = {}
    for team, entry in clock.items():
        if team == own or not isinstance(entry, dict):
            out[team] = entry
            continue
        kept = {k: v for k, v in entry.items()
                if k not in ("phase_ms", "time_to_next_wave_ms", "offset_ms")}
        kept["status"] = "unknown_to_this_pov"
        kept["reason"] = (
            "the enemy reinforcement phase is oracle truth: this team had no "
            "observed cue to infer it from (spec §5.6, §6.3)"
        )
        out[team] = kept
    return out


#: How many capture intervals a causal velocity pair may span.
#:
#: §4.4.1 requires `0 < dt <= velocity_max_dt_ms`, and this bound was simply
#: never supplied: the router did not pass one, so `max_dt_ms` was always None
#: and a velocity could be derived across an arbitrarily large gap inside one
#: life. Direction from two samples 30 seconds apart is not a direction.
#:
#: ⛔ THE BOUND COMES FROM THE ROUND, NOT FROM THIS NUMBER. Measured on rounds
#: whose manifest declares a 200 ms interval: of 410,832 consecutive sample
#: gaps, **zero exceed 200 ms** — the declared interval IS the observed
#: maximum. The multiplier only leaves room for one dropped sample.
#:
#: ⚠️ AND THE FIRST MEASUREMENT SAID SOMETHING ELSE. Sampling the most RECENT
#: tracks gave max = 200 ms across 503,552 gaps, which would have justified
#: hard-coding 200. The second measurement, by a different path (oldest tracks
#: first), found max = 30,595 ms and 20.2% of gaps above 200 — because older
#: rounds were captured at 500 ms. A global constant would have declared the
#: entire older regime unusable. Rounds without a manifest therefore get NO
#: bound rather than an invented one, and the snapshot publishes which.
VELOCITY_MAX_DT_INTERVALS = 2

#: How far a shot carries, in game units — DERIVED FROM THE ENGINE, not chosen.
#:
#: This was 1,500: a plausible-sounding number with nothing behind it, sitting
#: in the same file as a radius measured to the p90. The engine settles it.
#: `src/client/snd_dma.c` defines `SOUND_RANGE_DEFAULT 1250` and
#: `SOUND_FULLVOLUME 80`, and `S_SpatializeOrigin` computes
#: `dist_fullvol = range * 0.064` (= 80), then `dist = (d - 80) / 1250` and
#: scales the volume by `1 - dist`. Volume reaches zero at `dist >= 1`, so a
#: shot is inaudible at **d >= 1330**: full volume within 80 units, linear
#: falloff to silence at 1,330.
#:
#: ⭐ THE BETTER ANSWER IS PVS, AND IT IS REACHABLE. Distance is only half of
#: audibility — the client can play a sound only if the event reached it, and
#: in a Quake engine the server decides that with the potentially visible set
#: (`CM_ClusterPVS`; ET:Legacy has no PHS, so there is no separate hearable
#: set). A shot behind a sealed wall is not heard at 400 units, and this
#: constant says it is. Our BSP reader already parses PLANES, NODES and LEAFS
#: with their `cluster`, already knows `VISIBILITY = 16` without reading it,
#: and `BspPointTracer._candidate_leaf_indices` already walks the node tree —
#: so audibility could be `PVS and d < 1330`. Not done here; recorded so the
#: next reader does not have to rediscover that it is a small step.
#:
#: ⚠️ Changing this alters nothing today: `shot_fired` has been off in
#: production since 2026-08-11, so the gunfire channel carries no rows. That is
#: not a reason for the number to stay wrong.
AUDIBLE_GUNFIRE_RADIUS = 1330.0


async def load_round_end_ms(db, round_id: int, tracks: dict[str, list]) -> int | None:
    """When every live-round belief stops, in round-relative ms.

    §6.3 makes round end public and ends all live-round beliefs, so
    `uncertain_after_down` needs it as a terminus — without one it would be
    handed an invented horizon.

    Duration comes from `shared/round_time.py`, never from `rounds.actual_time`
    directly: that column is the stopwatch TARGET (`g_nextTimeLimit`) and
    overstates about 15% of rounds. When it cannot be established the last
    observed life end stands in, which is a measurement rather than a default.
    """
    rows = await db.fetch_all(
        f"SELECT {round_duration_sql('r')} FROM rounds r WHERE r.id = $1",
        (round_id,))
    if rows and rows[0] and rows[0][0]:
        return int(rows[0][0]) * 1000
    ends = [t[5] for lives in tracks.values() for t in lives if t[5] is not None]
    return max(ends) if ends else None


def make_locator(tracks: dict[str, list]) -> Locator:
    """Where a named player was at an instant, as a region we can defend.

    ⭐ The radius is OUR error, not their eyesight. A player who was shot in the
    face knew exactly where the shooter was; what is uncertain is where our
    reconstruction puts them, so the region is sized by the measured p90 of
    Layer 1's position error for that sample's staleness and life-conflict
    state (`reconstruction_accuracy`, measured 2026-08-22 over 150 rounds).
    That is the difference between this radius and `AUDIBLE_GUNFIRE_RADIUS`,
    which is a named model parameter with no measurement behind it.

    ⚠️ FLOOR, and the LATEST overlapping life — the same two contracts Layer 1
    had to be corrected on. A belief must never be handed a position from after
    the instant it was formed.

    Returns None rather than a guess when the moment cannot be reconstructed:
    the belief then keeps its subject and loses only its place.
    """
    # ⚠️ Parsed once per life, not once per belief. `path` arrives as text from
    # some drivers and a round carries hundreds of beliefs against a handful of
    # lives, so parsing inside the loop re-decodes the same half-megabyte
    # document hundreds of times. Keyed on `pt.id`, which is why that column is
    # selected.
    parsed: dict[int, list] = {}

    def locate(guid: str, t_ms: int) -> Region | None:
        track_list = tracks.get(guid)
        if not track_list:
            return None
        track, _alive, conflict = select_life(track_list, t_ms)
        if track is None:
            return None
        path = parsed.get(track[8])
        if path is None:
            path = parsed[track[8]] = _ensure_path_list(track[6])
        sample, stale_ms, _idx = find_position_floor(path, t_ms)
        if sample is None:
            return None
        error = position_error(stale_ms, overlap_conflict=conflict)
        if error is None:
            return None
        try:
            x, y, z = float(sample["x"]), float(sample["y"]), float(sample["z"])
        except (KeyError, TypeError, ValueError):
            return None
        return Region(x, y, z, error.p90)

    return locate


async def load_round_information_state(
    db, round_id: int, t_ms: int, snapshot: Snapshot, clock: dict,
    capture_policy: CapturePolicy, tracks: dict[str, list] | None = None,
) -> dict:
    """§6 Layer 3: what each player in this round could plausibly have known.

    Built from four channels whose coverage differs wildly — obituary and
    contact reach nearly the whole corpus, gunfire and aim_lock only the rounds
    whose manifest proves the capture was on. `apply_capability` names the ones
    this round cannot support; they never become silence.

    ⛔ Line-of-sight is deliberately NOT a channel. It is an oracle upper bound
    on what could have been seen, not an observation, and §6.1 forbids inserting
    a belief merely because a ray was clear.
    """
    holders = [p.guid for p in snapshot.players.values()]
    if not holders:
        return {"holders": {}, "audible_gunfire_radius": AUDIBLE_GUNFIRE_RADIUS}

    positions = {
        p.guid: (p.x, p.y, p.z)
        for p in snapshot.players.values() if _has_position(p)
    }

    deaths = await db.fetch_all("""
        SELECT player_guid, team, death_time_ms
        FROM player_track
        WHERE round_id = $1 AND death_time_ms IS NOT NULL AND death_time_ms <= $2
          AND path -> -1 ->> 'event' IN
              ('killed', 'selfkill', 'fallen', 'world', 'teamkill')
    """, (round_id, t_ms))
    engagements = await db.fetch_all("""
        SELECT target_guid, attackers FROM combat_engagement
        WHERE round_id = $1 AND start_time_ms IS NOT NULL AND start_time_ms <= $2
    """, (round_id, t_ms))
    shots = await db.fetch_all("""
        SELECT guid, event_time, origin_x, origin_y, origin_z
        FROM proximity_shot_fired
        WHERE round_id = $1 AND event_time <= $2 AND origin_x IS NOT NULL
    """, (round_id, t_ms))
    locks = await db.fetch_all("""
        SELECT guid, target_guid, start_time FROM proximity_aim_lock
        WHERE round_id = $1 AND start_time <= $2 AND target_guid IS NOT NULL
    """, (round_id, t_ms))

    round_end_ms = await load_round_end_ms(db, round_id, tracks or {})
    beliefs = obituary_beliefs(
        [(r[0], r[1], r[2]) for r in (deaths or [])], holders, clock=clock,
        round_end_ms=round_end_ms)
    # ⭐ `locate` is what turns "he knows WHO" into "he knows who and roughly
    # where". Without it both subject channels carried a name and no place, and
    # `nearest_known_enemy_distance` could not return a value for any input.
    locate = make_locator(tracks) if tracks else None
    beliefs += contact_beliefs(
        [(r[0], _ensure_attackers(r[1])) for r in (engagements or [])],
        locate=locate)
    beliefs += gunfire_beliefs(
        [(r[0], r[1], float(r[2]), float(r[3]), float(r[4])) for r in (shots or [])],
        positions, audible_radius=AUDIBLE_GUNFIRE_RADIUS)
    beliefs += aim_lock_beliefs(
        [(r[0], r[1], r[2]) for r in (locks or [])], locate=locate)

    states = group_by_holder(beliefs)
    # ⛔ Every player gets an entry, including one with no beliefs: otherwise a
    # player who learned nothing and a player we could not model look identical.
    for guid in holders:
        states.setdefault(guid, HolderState(holder_guid=guid))
    apply_capability(
        states, {"capabilities": capture_policy.capabilities}, holders)

    return {
        "holders": {
            guid: belief_payload(state, t_ms, positions.get(guid))
            for guid, state in states.items()
        },
        "audible_gunfire_radius": AUDIBLE_GUNFIRE_RADIUS,
    }


def _ensure_attackers(value) -> list:
    """`attackers` comes back as a list from asyncpg and as text from others."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return []
    return value or []


#: `load_round_tracks` column order; see its docstring.
_TRACK_GUID, _TRACK_TEAM = 0, 2


def _pov_team(pov: str | None, tracks: dict[str, list]) -> dict | None:
    """Resolve `pov=team:AXIS` into that team's members, or None.

    Returns None for the oracle view, for a single-player pov, and for a team
    nobody played on — the caller distinguishes those, because "not a team
    request" and "a team that was not there" need different answers.

    ⛔ MEMBERSHIP COMES FROM THE TRACKS, NOT FROM THE SNAPSHOT. Reading
    `snap.players` looked equivalent and fails open: when every player is stale
    past `max_stale_ms` the snapshot has nobody, so a team request resolved to
    None and quietly degraded to the ORACLE — `withheld_by_pov` empty, the gaps
    listing both sides. A withholding guarantee that turns into full disclosure
    the moment the data thins is not a guarantee. The tracks say who played on
    which side whether or not they have a state at `t`.
    """
    if not pov or not pov.lower().startswith("team:"):
        return None
    wanted = pov[5:].strip().upper()
    roster = {
        t[_TRACK_GUID]: str(t[_TRACK_TEAM] or "").upper()
        for lives in (tracks or {}).values() for t in lives
    }
    members = {g for g, team in roster.items() if team == wanted}
    if not members:
        return None
    return {"team": wanted, "members": members, "all_guids": set(roster)}


def _team_information(information: dict, pov_team: dict, t_ms: int) -> dict:
    """One synthetic holder carrying the union of the team's beliefs.

    §6.3 is explicit that a belief set is per player and that team-level views
    are DERIVED BY UNION — not modelled separately. Holding a team-wide set
    directly would hand a player on the far side of the map the same knowledge
    as the one standing next to the fight.

    ⛔ Opponent holders are dropped, not kept alongside. Their beliefs are
    "what the enemy knows about us", which this team cannot know; leaving them
    in leaks no position but makes the view incoherent.

    ⛔ `nearest_*_distance` is null for a team. A distance needs a holder's
    position and a team has none; measuring from a team centroid would invent
    exactly the kind of number this layer exists to refuse.
    """
    holders = information.get("holders") or {}
    own = [holders[g] for g in pov_team["members"] if g in holders]

    beliefs: list[dict] = []
    unavailable: dict = {}
    for h in own:
        beliefs.extend(h.get("beliefs") or [])
        unavailable.update(h.get("unavailable") or {})

    named = {b.get("subject_guid") for b in beliefs
             if b.get("counts_as_known") and b.get("subject_guid")}

    return {
        **information,
        "holders": {
            f"team:{pov_team['team']}": {
                "holder_guid": f"team:{pov_team['team']}",
                "known_enemy_count": len(named),
                "nearest_known_enemy_distance": None,
                "nearest_heard_activity_distance": None,
                "beliefs": sorted(beliefs, key=lambda b: -(b.get("confidence") or 0)),
                "unavailable": unavailable,
                # ⚠️ The MAXIMUM across the union, not one member's.
                # `pov_team["members"]` is a set, so `own` has no defined order
                # and `own[0]` picked an arbitrary holder — safe today only
                # because every holder publishes the same module constant, and
                # a latent bug the moment one does not. The consumer uses this
                # as a hard filter (`beliefRegions` drops regions wider than
                # it), so an arbitrary pick could drop a region one member was
                # entitled to draw. Taking the widest keeps the union's promise:
                # what ANY member could claim, the team can (CodeRabbit, #800).
                "position_claim_max_radius": max(
                    (h.get("position_claim_max_radius") for h in own
                     if isinstance(h.get("position_claim_max_radius"), (int, float))),
                    default=None),
                "notes": [
                    ("this is the UNION of the team's per-player beliefs (§6.3); "
                     "no team-wide belief set exists"),
                    ("distances are null: a distance needs a holder position and "
                     "a team has none"),
                ],
            }
        },
        "pov": f"team:{pov_team['team']}",
        "pov_unavailable": None,
        # ⚠️ Own-team positions are treated as known. §6 calls this a defensible
        # simplification — teammates share a voice channel we cannot capture —
        # and requires it to be STATED rather than assumed.
        "own_team_positions_are_a_simplification": True,
    }


async def get_round_snapshot(
    db, round_id: int, t_ms: int, *, max_stale_ms: int | None = None,
    velocity_max_dt_ms: int | None = None, pov: str | None = None,
) -> dict[str, Any]:
    """One reconstructed moment of a round, as a plain dict.

    ⛔ Reconstruction only (§4.6). Nothing here ranks anyone.

    `capture_policy` carries the round's capability manifest where one exists
    and `unknown` where it does not — published rather than defaulted, so a
    consumer cannot mistake our software's current settings for evidence about
    the file. Its `capabilities` map has three states and `unknown` must never
    be read as `disabled`: for every round captured before the tracker began
    declaring its flags, an absent section is equally consistent with the
    capture being off and with it being on and having nothing to report.
    """
    tracks = await load_round_tracks(db, round_id)
    # An empty round takes the SAME path, not a shortcut with a different shape.
    # The early return used to omit capture_policy, player_count, gaps and the
    # rest, so a consumer reading any of them hit a KeyError exactly when the
    # data was thinnest — the worst possible moment to change the contract
    # (CodeRabbit, PR #792). `unavailable` is added alongside, never instead.
    engagements = await load_round_engagements(db, round_id) if tracks else []
    # ⭐ Loaded BEFORE the snapshot, because the round's own capture interval is
    # what bounds a causal velocity pair — see VELOCITY_MAX_DT_INTERVALS. A
    # round that never declared its interval gets no bound, which is the same
    # answer this module gives everywhere else: unknown is published, not
    # replaced by a default that looks like evidence.
    policy = await load_capture_policy(db, round_id)
    if velocity_max_dt_ms is None and policy.observation_interval_ms:
        velocity_max_dt_ms = (
            policy.observation_interval_ms * VELOCITY_MAX_DT_INTERVALS
        )
    snap = build_snapshot(
        tracks, t_ms, engagements=engagements,
        max_stale_ms=max_stale_ms, velocity_max_dt_ms=velocity_max_dt_ms,
    )
    separation = nearest_teammate_separation(snap)
    clock = await load_round_clock(db, round_id, t_ms)

    # ⭐ `pov` selects WHOSE picture is returned, the interaction VALORANT's
    # replay tool settled on: switch between a player and the omniscient view.
    # Their known limitation is that the minimap cannot be restricted; ours can,
    # because the information state is data rather than a rendering choice.
    #
    # ⛔ `world` is the oracle. It is a named diagnostic (§6.4) and never a
    # belief source — which is why it is spelled out rather than being the
    # silent default.
    pov_team = _pov_team(pov, tracks)

    # 🔴 RESOLVED BEFORE THE BELIEFS, because the clock does not only get
    # PUBLISHED — it decides when "he is down" stops being true. `resolve_expiry`
    # reads the SUBJECT's team clock, so with the oracle clock an enemy belief
    # flipped to `uncertain_after_down` at the precise instant the enemy wave
    # landed. Measured on 25 rounds: 46 of 449 beliefs (10.2%) expired on
    # `validated_wave`. Withholding the number from the panel while letting the
    # beliefs keep time with it would publish the same fact as a behaviour —
    # scrub the slider and read the enemy phase off when the circles change.
    #
    # ⭐ The degraded clock keeps `interval_ms` and loses `offset_ms`, so
    # `resolve_expiry` falls to `interval_only`: "he is back somewhere inside
    # one interval", which is what §6.3 says a holder without a cue may hold.
    pov_clock = restrict_clock_to_pov(clock, pov_team)
    information = await load_round_information_state(
        db, round_id, t_ms, snap, pov_clock, policy, tracks
    ) if tracks else {"holders": {}, "audible_gunfire_radius": AUDIBLE_GUNFIRE_RADIUS}

    withheld: list[str] = []

    if pov_team is not None:
        # ⛔ THE WITHHOLDING HAPPENS HERE, NOT IN THE RENDERER.
        #
        # VALORANT's replay hides an enemy outline and admits it cannot hide the
        # minimap: the client is handed the truth and chooses not to draw it.
        # Filtering in the page would leave us with the same limitation while
        # claiming otherwise, and one look at devtools would disprove the claim.
        # This page is also due to be rewritten in React, and a guarantee that
        # lives in a renderer does not survive its replacement.
        #
        # ⭐ Identities stay. Who played is public through the scoreboard and
        # the kill feed; where they stood is not.
        own = pov_team["members"]
        withheld = sorted(g for g in pov_team["all_guids"] if g not in own)
        snap_players = [p for p in snap.players.values() if p.guid in own]
        information = _team_information(information, pov_team, t_ms)
    else:
        snap_players = list(snap.players.values())
        if pov and pov != "world":
            holders = information.get("holders", {})
            information = {
                **information,
                "holders": {pov: holders[pov]} if pov in holders else {},
                "pov": pov,
                "pov_unavailable": (
                    None if pov in holders
                    else f"{pov} has no reconstructed state in this round at t={t_ms}"
                ),
            }
        elif pov and pov.lower().startswith("team:"):
            # A team nobody played on. Named, not silently treated as the oracle.
            information = {
                **information, "holders": {}, "pov": pov,
                "pov_unavailable": f"no players on team {pov[5:]!r} in this round",
            }
        else:
            information = {**information, "pov": pov or "world"}
    payload: dict[str, Any] = {
        "round_id": round_id,
        "t_ms": t_ms,
        # ⭐ Which map, and how long the round ran. Both were missing, and both
        # are things a snapshot cannot be complete without: a consumer holding
        # a moment of a round had no way to say WHERE it happened, so it could
        # not load that map's geometry, and no way to bound a time control
        # without guessing a duration. `map_name` comes off the tracks that
        # were already loaded; the duration is `shared/round_time.py`, never
        # `rounds.actual_time` (that column is the stopwatch target and
        # overstates about 15% of rounds).
        "map_name": next(
            (t[7] for lives in (tracks or {}).values() for t in lives if t[7]), None
        ),
        "round_duration_ms": await load_round_end_ms(db, round_id, tracks or {}),
        # ⚠️ When the round first HAS anybody. At t=0 no player has spawned, so
        # a viewer opening at zero sees an empty map and reads it as "nobody was
        # there" — the warmup trap this project has already been caught by once
        # on the live page. Taken from the tracks in memory, not guessed as a
        # fraction of the duration.
        # ⛔ Never negative. The endpoint rejects `t < 0` with 422, so a
        # negative value here is a moment the API refuses to serve — and 12.5%
        # of rounds (113 of 906) have a track that spawned before the round's
        # zero, during warmup. The page opened at that value, took the 422 and
        # said "could not load", which made every one of those rounds
        # unreachable. Someone who spawned before zero is present AT zero.
        "first_position_ms": max(0, min(
            (t[4] for lives in (tracks or {}).values() for t in lives
             if t[4] is not None), default=0
        )) if tracks else None,
        "capture_policy": {
            "mode": policy.mode,
            "observation_interval_ms": policy.observation_interval_ms,
            "source": policy.source,
            "manifest_version": policy.policy_version,
            "capabilities": policy.capabilities,
            "manifest_count": policy.manifest_count,
            "conflicting_flags": policy.conflicting_flags,
        },
        # Published so a reader can tell "no gap was too large" from "no
        # bound was applied": null means the round never declared an interval.
        "velocity_max_dt_ms": velocity_max_dt_ms,
        "clock": pov_clock,
        "information_state": information,
        "reconstruction_accuracy": dict(ACCURACY_MEASUREMENT),
        "player_count": len(snap.players),
        "overlap_conflicts": snap.overlap_conflicts,
        # `gaps` reasons name tracking state, not position — but under a team
        # view they would still enumerate the other side, so they follow the
        # same boundary as everything else.
        "gaps": {g: why for g, why in snap.gaps.items() if g not in withheld},
        "players": [_player_to_dict(p) for p in snap_players],
        # ⛔ Named, not vanished. Layer 1 promises every player is either placed
        # or in `gaps` with a reason; a withheld enemy is neither, so leaving
        # him out of both would break one contract to keep another.
        "withheld_by_pov": withheld,
        # 🔴 A separation is not a coordinate, which is exactly why it slipped
        # past the guard that scans for coordinates. Keyed by guid, it told a
        # team WHICH enemies were alive and placed and HOW TIGHTLY THE OTHER
        # SIDE WAS GROUPED — the shape of their formation, from the field that
        # was supposed to describe your own.
        "nearest_teammate_separation": {
            g: d for g, d in separation.items() if g not in withheld
        },
        # 🔴 An opponent edge carries `distance`, computed from the real
        # positions — one leaks the range to an enemy, several across time
        # trilaterate him. Withholding the positions and leaving the edges was
        # the hole in the first version of this design (Fable's review).
        "edges": [
            {"a": e.a_guid, "b": e.b_guid, "kind": e.kind,
             "distance": round(e.distance, 1),
             "recently_contested": e.recently_contested}
            for e in snap.edges
            if not withheld
            or (e.a_guid not in withheld and e.b_guid not in withheld)
        ],
        # Each multi-line note is wrapped in its own parentheses. Inside a list
        # of strings, an implicit concatenation is indistinguishable from a
        # forgotten comma — which is exactly what CodeQL flags — so the intent
        # is written out rather than left to the reader (or the next linter).
        "notes": [
            ("line-of-sight is NOT included: it is an oracle upper bound and "
             "stays unvalidated until W6 (spec §6, §12)"),
            ("recently_contested means an engagement was open, which the tracker "
             "holds for up to 15s after the last hit — not 'under attack'"),
            "distances are geometric separation, not tactical support distance",
            ("`gaps` names every player without a state here and why; a player "
             "is never simply absent"),
        ],
    }
    if not tracks:
        payload["unavailable"] = "no linked player_track rows for this round"
    return payload
