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

⚠️ CAPTURE POLICY IS UNKNOWN FOR EVERY HISTORICAL ROUND, and that is the normal
case, not an edge case. `proximity_processed_files.capabilities` is NULL in all
828 rows and the per-file `position_sample_interval` is parsed but never
persisted. So `mode = "unknown"` and the staleness tolerance has no default the
data can justify — the caller supplies one or gets everything back with its
staleness stated. Absence of a capability is `unavailable`, never zero (§6.2).
"""

from __future__ import annotations

import math
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from website.backend.logging_config import get_app_logger
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
    overlap_conflicts: int


def find_position_floor(path: list, target_ms: int) -> tuple[dict | None, int]:
    """The last sample at or before `target_ms`, and how stale it is.

    FLOOR, never nearest. `replay_service._find_position_at_time` compares the
    two neighbours and returns the closer one, which for a target between
    samples can be the LATER one — a position from after the moment being asked
    about. That is the single most important difference between a replay slider
    and a relational layer, so it gets its own function rather than a flag on
    the existing one: the replay page depends on the current behaviour and §4.4
    forbids changing it underneath.

    Returns (sample, stale_ms). No sample at or before `target_ms` yields
    (None, -1) — the player has no causal state yet, which is a gap to report,
    not a zero to invent.
    """
    if not path:
        return None, -1
    times = [s.get("time", 0) for s in path]
    idx = bisect_right(times, target_ms)
    if idx == 0:
        return None, -1
    sample = path[idx - 1]
    return sample, int(target_ms - (sample.get("time", 0) or 0))


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
    cur, prev = path[sample_index], path[sample_index - 1]
    dt_ms = int((cur.get("time", 0) or 0) - (prev.get("time", 0) or 0))
    if dt_ms <= 0:
        return None, None, None, None, "non_monotonic_samples"
    if max_dt_ms is not None and dt_ms > max_dt_ms:
        return None, None, None, None, f"gap_exceeds_max_dt_{dt_ms}ms"

    dt_s = dt_ms / 1000.0
    try:
        vx = (float(cur["x"]) - float(prev["x"])) / dt_s
        vy = (float(cur["y"]) - float(prev["y"])) / dt_s
        vz = (float(cur.get("z", 0)) - float(prev.get("z", 0))) / dt_s
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


def _sample_index(path: list, sample: dict) -> int:
    times = [s.get("time", 0) for s in path]
    return bisect_right(times, sample.get("time", 0)) - 1


def build_snapshot(
    tracks_by_guid: dict[str, list],
    t_ms: int,
    *,
    engagements: list | None = None,
    max_stale_ms: int | None = None,
    velocity_max_dt_ms: int | None = None,
) -> Snapshot:
    """One moment: who was where, and how they related.

    `max_stale_ms` is the caller's tolerance, not ours. With capture policy
    unknown for every historical round (see module docstring) there is no
    default the data can justify, so None means "return everything and state its
    staleness" and a value means "drop states older than this".
    """
    players: dict[str, PlayerState] = {}
    conflicts = 0

    for guid, track_list in tracks_by_guid.items():
        track, alive, conflict = select_life(track_list, t_ms)
        if track is None:
            continue
        conflicts += 1 if conflict else 0

        path = _ensure_path_list(track[6])
        # A dead player is shown at the position they died in, which is a state
        # from their death time and is labelled with that staleness — not
        # silently presented as current.
        lookup_ms = t_ms if alive else int(track[5] or t_ms)
        sample, stale_ms = find_position_floor(path, lookup_ms)
        if sample is None:
            continue
        if max_stale_ms is not None and stale_ms > max_stale_ms:
            continue

        vx = vy = vz = None
        v_dt = v_reason = None
        if alive:
            vx, vy, vz, v_dt, v_reason = derive_velocity(
                path, _sample_index(path, sample), velocity_max_dt_ms
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
    alive = [p for p in players.values() if p.alive and p.x is not None]
    edges: list[Edge] = []
    for i, a in enumerate(alive):
        for b in alive[i + 1:]:
            if b.x is None:
                continue
            edges.append(Edge(
                a_guid=a.guid,
                b_guid=b.guid,
                kind="teammate" if a.team == b.team else "opponent",
                distance=math.dist((a.x, a.y, a.z or 0.0), (b.x, b.y, b.z or 0.0)),
                recently_contested=(a.guid in contested or b.guid in contested),
            ))
    return edges


def nearest_teammate_separation(snapshot: Snapshot) -> dict[str, float | None]:
    """Straight-line distance to the nearest living teammate, per player.

    None when a player has no living teammate — a real state (last man standing),
    not a distance of zero.
    """
    out: dict[str, float | None] = {}
    for guid, p in snapshot.players.items():
        if not p.alive or p.x is None:
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
    grouped: dict[str, list] = defaultdict(list)
    for row in rows:
        grouped[row[0]].append(row)
    return grouped


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
        "vx": st.vx, "vy": st.vy, "vz": st.vz,
        "velocity_stale_ms": st.velocity_stale_ms,
        "velocity_reason": st.velocity_reason,
    }


async def get_round_snapshot(
    db, round_id: int, t_ms: int, *, max_stale_ms: int | None = None,
    velocity_max_dt_ms: int | None = None,
) -> dict[str, Any]:
    """One reconstructed moment of a round, as a plain dict.

    ⛔ Reconstruction only (§4.6). Nothing here ranks anyone.

    `capture_policy` is reported as `unknown` because it is: no round in the
    database carries a persisted cadence or capability manifest today. That is
    published rather than defaulted, so a consumer cannot mistake our software
    fallback for evidence about the file.
    """
    tracks = await load_round_tracks(db, round_id)
    if not tracks:
        return {
            "round_id": round_id, "t_ms": t_ms, "players": [], "edges": [],
            "unavailable": "no linked player_track rows for this round",
        }
    engagements = await load_round_engagements(db, round_id)
    snap = build_snapshot(
        tracks, t_ms, engagements=engagements,
        max_stale_ms=max_stale_ms, velocity_max_dt_ms=velocity_max_dt_ms,
    )
    separation = nearest_teammate_separation(snap)
    policy = CapturePolicy()
    return {
        "round_id": round_id,
        "t_ms": t_ms,
        "capture_policy": {
            "mode": policy.mode,
            "observation_interval_ms": policy.observation_interval_ms,
            "source": policy.source,
        },
        "player_count": len(snap.players),
        "overlap_conflicts": snap.overlap_conflicts,
        "players": [_player_to_dict(p) for p in snap.players.values()],
        "nearest_teammate_separation": separation,
        "edges": [
            {"a": e.a_guid, "b": e.b_guid, "kind": e.kind,
             "distance": round(e.distance, 1),
             "recently_contested": e.recently_contested}
            for e in snap.edges
        ],
        "notes": [
            "line-of-sight is NOT included: it is an oracle upper bound and stays "
            "unvalidated until W6 (spec §6, §12)",
            "recently_contested means an engagement was open, which the tracker "
            "holds for up to 15s after the last hit — not 'under attack'",
            "distances are geometric separation, not tactical support distance",
        ],
    }
