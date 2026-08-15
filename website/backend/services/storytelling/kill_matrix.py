"""Kill matrix — who killed whom, for one gaming session.

Every duel in the session already sits in `proximity_kill_outcome`, one row per
kill with both sides named. Nothing on the platform ever showed the pairing,
even though it is the first thing players argue about after a night ("you died
to him eight times"). gibhub.gg publishes the same thing per round; this is the
session view of data we already store.

Scoping deliberately differs from the older metrics here. They select rows by
session dates plus the canonical round key `(round_start_unix, map_name,
round_number)`, which is only as complete as `rounds.round_start_unix` — and
that column is filled from linked Lua webhook rows. Measured 2026-08-15:
session 144 has 4 of 14 rounds with a start unix, so the round-key path sees
**78 of its 507 kills (15 %)**, and session 146 sees none; sessions up to 143
still resolve 96-100 %. This matrix therefore joins `rounds` on `round_id` and
filters by `gaming_session_id`, which is exact regardless of Lua coverage.
(Rows whose `round_id` is NULL — 541 table-wide — cannot be attributed to any
session by either route and are out of scope for all of them.)
"""
from __future__ import annotations

from website.backend.services.session_scope import GamingSessionScope

from .base import logger, short_guid, strip_et_colors


class _KillMatrixMixin:
    """Who-killed-whom pairings for a session (mixed into StorytellingService)."""

    async def compute_kill_matrix(self, scope: GamingSessionScope) -> dict:
        rows = await self.db.fetch_all("""
            SELECT
                COALESCE(o.killer_guid_canonical, LEFT(o.killer_guid, 8)) AS killer_key,
                LEFT(o.victim_guid, 8)                                    AS victim_key,
                MAX(o.killer_name)                                        AS killer_name,
                MAX(o.victim_name)                                        AS victim_name,
                COUNT(*)                                                  AS kills,
                COUNT(*) FILTER (WHERE o.outcome = 'gibbed')              AS gibs,
                COUNT(*) FILTER (WHERE o.outcome = 'revived')             AS revived
            FROM proximity_kill_outcome o
            JOIN rounds r ON r.id = o.round_id
            WHERE r.gaming_session_id = $1
              AND r.round_number IN (1, 2)
              AND r.is_bot_round IS DISTINCT FROM TRUE
              AND r.is_valid IS DISTINCT FROM FALSE
              AND o.killer_guid IS NOT NULL
              AND o.victim_guid IS NOT NULL
            GROUP BY killer_key, victim_key
        """, (scope.gaming_session_id,))

        names: dict[str, str] = {}
        kills_by: dict[str, int] = {}
        deaths_by: dict[str, int] = {}
        cells: list[dict] = []

        for r in (rows or []):
            killer, victim = r[0], r[1]
            if not killer or not victim:
                continue
            # A player killing himself (world/selfkill rows) is not a duel and
            # would sit on the diagonal claiming a dominance that never happened.
            if killer == victim:
                continue
            kills = int(r[4] or 0)
            names.setdefault(killer, strip_et_colors(r[2] or killer))
            names.setdefault(victim, strip_et_colors(r[3] or victim))
            kills_by[killer] = kills_by.get(killer, 0) + kills
            deaths_by[victim] = deaths_by.get(victim, 0) + kills
            cells.append({
                "killer": killer,
                "victim": victim,
                "kills": kills,
                "gibs": int(r[5] or 0),
                "revived": int(r[6] or 0),
            })

        if not cells:
            return {
                "status": "ok",
                "available": False,
                "reason": "no_kill_data",
                "players": [],
                "cells": [],
            }

        # One axis for both rows and columns, so the matrix is square and the
        # diagonal is meaningful (blank), ordered by kills so the most active
        # players read first.
        keys = sorted(
            set(kills_by) | set(deaths_by),
            key=lambda k: (-kills_by.get(k, 0), names.get(k, k).lower()),
        )
        players = [
            {
                "guid_short": k,
                "name": names.get(k, k),
                "kills": kills_by.get(k, 0),
                "deaths": deaths_by.get(k, 0),
            }
            for k in keys
        ]

        logger.debug(
            "kill matrix: gsid=%s players=%d cells=%d",
            scope.gaming_session_id, len(players), len(cells),
        )
        return {
            "status": "ok",
            "available": True,
            "players": players,
            "cells": cells,
            "total_kills": sum(kills_by.values()),
        }


__all__ = ["_KillMatrixMixin", "short_guid"]
