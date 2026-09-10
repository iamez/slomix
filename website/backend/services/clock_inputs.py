"""Database side of the reinforcement clock: rows in, `reinforcement_clock` types out.

`reinforcement_clock` is deliberately pure — it takes dataclasses and returns
verdicts, with no idea where the rows came from. The queries that feed it lived
as private helpers inside `routers/proximity_competitive.py`, which meant a
second consumer had to either import from a router (backwards: services must not
depend on routers) or write the same queries again. They live here now, and the
router uses them.

⚠️⚠️ THE ONE THING TO GET RIGHT: `proximity_spawn_timing.enemy_spawn_interval`
belongs to the VICTIM's team, as its name says — it is the interval of the team
the killer was shooting at. Pairing it with `killer_team` produces a clock built
from the other side's interval, and the result is not obviously broken: it
validates nothing at all, so it reads as "this data has no wave structure".

That is not a hypothetical. Measuring 400 rounds with `killer_team` returned
**zero** validated clocks out of 800, with residuals spread evenly across the
interval — a convincing picture of a signal that does not exist. The same 400
rounds with `victim_team` return **667 validated clocks**, with a median
residual of 25 ms. The spawn waves were textbook the whole time: on one round
AXIS landed at 500, 24975, 54975, 84975 and ALLIES at 500, 9975, 29975 — and
83.5% of all recorded spawns share an exact timestamp with a teammate.
"""

from __future__ import annotations

from typing import Any

from website.backend.services.reinforcement_clock import (
    ClockValidation,
    PlayerLife,
    ReviveObservation,
    TimingObservation,
)


def is_bot_player(guid: str | None, name: str | None) -> bool:
    """Bots spawn on the same waves but are not who the clock is about.

    §13.2 records that `is_bot` is computed but never backfilled, so the flag
    cannot be trusted and the guid/name prefixes are what we have.
    """
    return (guid or "").upper().startswith("OMNIBOT") or (name or "").upper().startswith("[BOT]")


def strict_clock_round_gate_sql(prefix: str = "") -> str:
    """Round gate shared by the measured clock protocol and live consumers."""
    return (
        "EXISTS (SELECT 1 FROM rounds clock_round "
        f"WHERE clock_round.id = {prefix}round_id "
        "AND clock_round.round_number IN (1, 2) "
        "AND clock_round.is_valid IS DISTINCT FROM FALSE "
        "AND clock_round.is_bot_round IS DISTINCT FROM TRUE "
        "AND (clock_round.round_status IN ('completed', 'substitution') "
        "OR clock_round.round_status IS NULL))"
    )


def clock_validation_payload(validation: ClockValidation) -> dict:
    """The verdict as JSON. `offset_ms` appears only once validated.

    An unvalidated offset is a number the protocol explicitly refuses to stand
    behind, and publishing it would let a consumer treat "internally consistent"
    as "known" — which is the distinction §5.2 exists to draw.
    """
    return {
        "status": validation.status,
        "interval_ms": validation.interval_ms,
        "offset_ms": validation.offset_ms if validation.status == "validated" else None,
        "timing_observations": validation.timing_observation_count,
        "landing_clusters": validation.landing_count,
        "spawn_callbacks": validation.spawn_observation_count,
        "post_revive_spawn_callbacks": validation.post_revive_spawn_count,
        "passing_landing_clusters": validation.passing_landing_count,
        "pass_ratio": (
            round(validation.pass_ratio, 6)
            if validation.pass_ratio is not None
            else None
        ),
    }


async def fetch_clock_lives_and_revives(
    db: Any,
    round_id: int,
) -> tuple[list[PlayerLife], list[ReviveObservation], int]:
    """Lives and revives for one round, bots removed."""
    track_rows = await db.fetch_all(
        """
        SELECT id, player_guid, player_name, team, spawn_time_ms, death_time_ms,
               path -> -1 ->> 'event' AS death_type
        FROM player_track
        WHERE round_id = $1
        ORDER BY player_guid, spawn_time_ms, id
        """,
        (round_id,),
    )
    revive_rows = await db.fetch_all(
        """
        SELECT revived_guid, revived_name, revive_time
        FROM proximity_revive
        WHERE round_id = $1
        ORDER BY revive_time, id
        """,
        (round_id,),
    )
    lives = [
        PlayerLife(
            row_id=int(row[0]),
            player_guid=str(row[1]),
            team=str(row[3] or ""),
            spawn_time_ms=int(row[4]),
            death_time_ms=int(row[5]) if row[5] is not None else None,
            death_type=row[6],
        )
        for row in (track_rows or [])
        if row[4] is not None and not is_bot_player(row[1], row[2])
    ]
    revives = [
        ReviveObservation(player_guid=str(row[0]), time_ms=int(row[2]))
        for row in (revive_rows or [])
        if not is_bot_player(row[0], row[1])
    ]
    track_bounds = [
        value
        for life in lives
        for value in (life.spawn_time_ms, life.death_time_ms)
        if value is not None
    ]
    return lives, revives, max(track_bounds, default=0)


async def fetch_timing_observations(db: Any, round_id: int) -> list[TimingObservation]:
    """Spawn-timing rows for one round, keyed to the team the interval describes.

    ⚠️ `team=victim_team`, paired with `enemy_spawn_interval`. See the module
    docstring: swapping in `killer_team` silently yields a clock that validates
    nothing, and looks exactly like missing data.
    """
    rows = await db.fetch_all(
        f"""
        SELECT victim_team, kill_time, enemy_spawn_interval, time_to_next_spawn,
               spawn_timing_score, killer_guid, killer_name
        FROM proximity_spawn_timing
        WHERE round_id = $1 AND {strict_clock_round_gate_sql()}
        ORDER BY kill_time
        """,  # nosec B608 - the gate is a literal, no user data interpolated
        (round_id,),
    )
    return [
        TimingObservation(
            team=str(row[0] or ""),
            kill_time_ms=int(row[1] or 0),
            interval_ms=int(row[2] or 0),
            time_to_next_spawn_ms=int(row[3]) if row[3] is not None else None,
            spawn_timing_score=float(row[4]) if row[4] is not None else None,
        )
        for row in (rows or [])
        if not is_bot_player(row[5], row[6])
    ]


def wave_position(t_ms: int, interval_ms: int, offset_ms: int) -> tuple[int, int]:
    """Where `t_ms` sits between two wave landings: (since previous, until next).

    ⚠️⚠️ `offset_ms` IS NOT A LANDING TIME. `infer_clock` derives it as
    `(interval - time_to_next - kill_time) % interval` and `circular_residual_ms`
    consumes it as `(time + offset) % interval` — a PLUS. A landing L therefore
    satisfies `(L + offset) % interval == 0`, which means the offset is the
    negated phase, not the moment of the first wave.

    Reading it as a landing time gives `(t - offset) % interval`, which is
    plausible, never raises, and is wrong by `2 * offset` — on a validated round
    it turned "5 seconds to the next wave" into "15". The unit fixture is built
    from real landings for exactly this reason; the arithmetic here is not
    self-evident and must not be re-derived from the name.
    """
    phase = (t_ms + offset_ms) % interval_ms
    return phase, interval_ms - phase
