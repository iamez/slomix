"""Season awards computation (VISION_2026 Sprint S4 "TEKMA").

Computes the engraved season awards from existing data, scoped to a quarterly
season (SeasonManager). All sources reuse tables built in earlier sprints:
  - mvp           — most session_mvp_votes (S3) across the season's sessions
  - iron_man      — most distinct gaming sessions attended (valid rounds)
  - most_improved — biggest DPM gain from first to last session in the season
  - oracle        — best parimutuel net winnings (S4-C) in the season

Each computed award upserts into season_awards (season_id, award_key,
player_guid). 'most_improved'/'iron_man' need >=2 / >=1 valid sessions; awards
with no qualifying data are simply skipped.
"""
from __future__ import annotations

import json

from shared.season_manager import SeasonManager

AWARD_KEYS = ("mvp", "iron_man", "most_improved", "oracle")


def _season_bounds(season_id: str | None) -> tuple[str, str, str]:
    sm = SeasonManager()
    sid = season_id or sm.get_current_season()
    start, end = sm.get_season_dates(sid)
    return sid, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


async def _season_session_ids(db, start: str, end: str) -> list[int]:
    rows = await db.fetch_all(
        """
        SELECT DISTINCT gaming_session_id
        FROM rounds
        WHERE gaming_session_id IS NOT NULL
          AND is_valid IS DISTINCT FROM FALSE
          AND SUBSTR(CAST(round_date AS TEXT), 1, 10) BETWEEN ? AND ?
        """,
        (start, end),
    )
    return [int(r[0]) for r in (rows or [])]


async def _compute_mvp(db, session_ids: list[int]) -> dict | None:
    if not session_ids:
        return None
    ph = ",".join(["?"] * len(session_ids))
    rows = await db.fetch_all(
        f"""
        SELECT nominated_guid, COUNT(*) AS votes
        FROM session_mvp_votes
        WHERE gaming_session_id IN ({ph})
        GROUP BY nominated_guid
        ORDER BY votes DESC
        LIMIT 1
        """,  # nosec B608 - ph is ?-bound ints
        tuple(session_ids),
    )
    if not rows:
        return None
    guid, votes = rows[0][0], int(rows[0][1])
    name = await _player_name(db, guid)
    return {"award_key": "mvp", "player_guid": guid, "player_name": name,
            "value_text": f"{votes} MVP votes", "value_num": votes,
            "source": {"votes": votes, "sessions": len(session_ids)}}


async def _compute_iron_man(db, start: str, end: str) -> dict | None:
    rows = await db.fetch_all(
        """
        SELECT pcs.player_guid, MAX(pcs.player_name) AS name,
               COUNT(DISTINCT r.gaming_session_id) AS sessions
        FROM player_comprehensive_stats pcs
        JOIN rounds r ON r.id = pcs.round_id
        WHERE r.gaming_session_id IS NOT NULL
          AND r.is_valid IS DISTINCT FROM FALSE
          AND pcs.time_played_seconds > 0
          AND SUBSTR(CAST(r.round_date AS TEXT), 1, 10) BETWEEN ? AND ?
        GROUP BY pcs.player_guid
        ORDER BY sessions DESC
        LIMIT 1
        """,
        (start, end),
    )
    if not rows:
        return None
    guid, name, sessions = rows[0][0], rows[0][1], int(rows[0][2])
    return {"award_key": "iron_man", "player_guid": guid,
            "player_name": name or guid[:8],
            "value_text": f"{sessions} sessions", "value_num": sessions,
            "source": {"sessions": sessions}}


async def _compute_most_improved(db, start: str, end: str) -> dict | None:
    # Per-player per-session DPM within the season; delta = last - first.
    rows = await db.fetch_all(
        """
        SELECT pcs.player_guid, MAX(pcs.player_name) AS name,
               r.gaming_session_id,
               SUM(pcs.damage_given)::float
                   / NULLIF(SUM(pcs.time_played_seconds) / 60.0, 0) AS dpm
        FROM player_comprehensive_stats pcs
        JOIN rounds r ON r.id = pcs.round_id
        WHERE r.gaming_session_id IS NOT NULL
          AND r.is_valid IS DISTINCT FROM FALSE
          AND pcs.time_played_seconds > 0
          AND SUBSTR(CAST(r.round_date AS TEXT), 1, 10) BETWEEN ? AND ?
        GROUP BY pcs.player_guid, r.gaming_session_id
        ORDER BY pcs.player_guid, r.gaming_session_id
        """,
        (start, end),
    )
    by_player: dict[str, dict] = {}
    for guid, name, sid, dpm in (rows or []):
        p = by_player.setdefault(guid, {"name": name, "sessions": []})
        p["name"] = name or p["name"]
        p["sessions"].append((int(sid), float(dpm or 0)))
    best = None
    for guid, p in by_player.items():
        if len(p["sessions"]) < 2:
            continue
        ordered = sorted(p["sessions"])
        delta = ordered[-1][1] - ordered[0][1]
        if best is None or delta > best[1]:
            best = (guid, delta, p["name"], ordered[0][1], ordered[-1][1])
    if not best or best[1] <= 0:
        return None
    guid, delta, name, first_dpm, last_dpm = best
    return {"award_key": "most_improved", "player_guid": guid,
            "player_name": name or guid[:8],
            "value_text": f"+{delta:.0f} DPM ({first_dpm:.0f}→{last_dpm:.0f})",
            "value_num": round(delta, 1),
            "source": {"first_dpm": round(first_dpm, 1), "last_dpm": round(last_dpm, 1)}}


async def _compute_oracle(db, session_ids: list[int]) -> dict | None:
    # Best parimutuel net winnings on the season's markets, mapped to the
    # bettor's linked player. Skipped if betting isn't in use yet.
    if not session_ids:
        return None
    ph = ",".join(["?"] * len(session_ids))
    rows = await db.fetch_all(
        f"""
        SELECT b.user_id, SUM(b.payout - b.amount) AS net
        FROM parimutuel_bets b
        JOIN parimutuel_markets m ON m.id = b.market_id
        WHERE m.gaming_session_id IN ({ph}) AND b.status IN ('won', 'lost')
        GROUP BY b.user_id
        ORDER BY net DESC
        LIMIT 1
        """,  # nosec B608 - ph is ?-bound ints
        tuple(session_ids),
    )
    if not rows or int(rows[0][1] or 0) <= 0:
        return None
    user_id, net = int(rows[0][0]), int(rows[0][1])
    link = await db.fetch_one(
        "SELECT player_guid, COALESCE(display_name, player_name) FROM player_links WHERE discord_id = ?",
        (user_id,),
    )
    if not link:
        return None  # unlinked bettor — no player to engrave
    return {"award_key": "oracle", "player_guid": link[0],
            "player_name": link[1] or link[0][:8],
            "value_text": f"+{net} points from bets", "value_num": net,
            "source": {"net_points": net}}


async def _player_name(db, guid: str) -> str:
    row = await db.fetch_one(
        "SELECT COALESCE(pl.display_name, MAX(pcs.player_name), ?) "
        "FROM player_comprehensive_stats pcs "
        "LEFT JOIN player_links pl ON pl.player_guid = pcs.player_guid "
        "WHERE pcs.player_guid = ? GROUP BY pl.display_name",
        (guid[:8], guid),
    )
    return (row[0] if row else None) or guid[:8]


async def compute_and_store(db, season_id: str | None, created_by: int | None) -> dict:
    """Compute all season awards and upsert them. Returns the awards list."""
    sid, start, end = _season_bounds(season_id)
    session_ids = await _season_session_ids(db, start, end)

    computed = []
    for fn in (
        _compute_mvp(db, session_ids),
        _compute_iron_man(db, start, end),
        _compute_most_improved(db, start, end),
        _compute_oracle(db, session_ids),
    ):
        award = await fn
        if award:
            computed.append(award)

    # Clear prior COMPUTED awards for this season (so a new winner replaces the
    # old one); manual awards use other keys and are preserved. AWARD_KEYS is a
    # fixed 4-tuple, so the placeholders are hardcoded (no string-built SQL).
    if computed:
        await db.execute(
            "DELETE FROM season_awards WHERE season_id = ? "
            "AND award_key IN (?, ?, ?, ?)",
            (sid, *AWARD_KEYS),
        )
    for a in computed:
        await db.execute(
            """
            INSERT INTO season_awards
                (season_id, award_key, player_guid, player_name, value_text,
                 value_num, source, created_by_user_id)
            VALUES (?, ?, ?, ?, ?, ?, CAST(? AS JSONB), ?)
            ON CONFLICT (season_id, award_key, player_guid) DO UPDATE
            SET player_name = EXCLUDED.player_name,
                value_text = EXCLUDED.value_text,
                value_num = EXCLUDED.value_num,
                source = EXCLUDED.source
            """,
            (sid, a["award_key"], a["player_guid"], a["player_name"],
             a["value_text"], a["value_num"], json.dumps(a["source"]),
             created_by),
        )
    return {"season_id": sid, "awards": computed}
