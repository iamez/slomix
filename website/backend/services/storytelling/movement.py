"""How players moved through the session — distance, speed, sprint share.

`player_track` has recorded this for every life all along (670 tracks in
session 144): `total_distance`, `avg_speed`, `peak_speed`,
`sprint_percentage`, `post_spawn_distance` and the stance seconds. None of it
reaches the story page, even though "who actually moves" separates a lurker
from an entry player as sharply as any kill statistic.

Units are ET engine units and units-per-second, reported raw. gibhub.gg
converts to metres and km/h, but its own numbers disagree with each other
(15.9 kph next to 10.6 mph is a 7 % gap), so a conversion constant would be
invented precision. `ups` is what the community already speaks in.

Scoped by `gaming_session_id` through `round_id` for the same reason as the
kill matrix: the canonical round key depends on `rounds.round_start_unix`,
which is only as complete as the Lua linkage.
"""
from __future__ import annotations

from website.backend.services.session_scope import GamingSessionScope

from .base import logger, strip_et_colors


class _MovementMixin:
    """Per-player movement summary for one session."""

    async def compute_movement(self, scope: GamingSessionScope) -> dict:
        rows = await self.db.fetch_all("""
            SELECT
                LEFT(pt.player_guid, 8)                    AS guid_short,
                MAX(pt.player_name)                        AS name,
                COUNT(*)                                   AS lives,
                SUM(pt.total_distance)                     AS total_distance,
                AVG(pt.avg_speed)                          AS avg_speed,
                MAX(pt.peak_speed)                         AS peak_speed,
                AVG(pt.sprint_percentage)                  AS sprint_pct,
                AVG(pt.post_spawn_distance)                AS post_spawn_distance,
                SUM(pt.duration_ms)                        AS alive_ms
            FROM player_track pt
            JOIN rounds r ON r.id = pt.round_id
            WHERE r.gaming_session_id = $1
              AND r.round_number IN (1, 2)
              AND r.is_bot_round IS DISTINCT FROM TRUE
              AND r.is_valid IS DISTINCT FROM FALSE
              AND pt.total_distance IS NOT NULL
            GROUP BY LEFT(pt.player_guid, 8)
        """, (scope.gaming_session_id,))

        players = []
        for r in (rows or []):
            distance = float(r[3] or 0)
            alive_ms = int(r[8] or 0)
            players.append({
                "guid_short": r[0],
                "name": strip_et_colors(r[1] or r[0]),
                "lives": int(r[2] or 0),
                "total_distance": round(distance),
                # Distance per minute alive says something a session total
                # cannot: a player with twice the alive time naturally walks
                # twice as far without being any more active.
                "distance_per_min": round(distance / (alive_ms / 60000), 1) if alive_ms > 0 else None,
                "avg_speed": round(float(r[4] or 0), 1),
                "peak_speed": round(float(r[5] or 0), 1),
                "sprint_pct": round(float(r[6] or 0), 1),
                "post_spawn_distance": round(float(r[7] or 0), 1),
                "alive_ms": alive_ms,
            })

        if not players:
            return {
                "status": "ok",
                "available": False,
                "reason": "no_track_data",
                "players": [],
            }

        players.sort(key=lambda p: p["total_distance"], reverse=True)
        logger.debug(
            "movement: gsid=%s players=%d", scope.gaming_session_id, len(players)
        )
        return {
            "status": "ok",
            "available": True,
            "unit": "et_units",
            "players": players,
        }


__all__ = ["_MovementMixin"]
