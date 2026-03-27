"""
Player Rivalries Service — Nemesis, Prey, Rival detection from H2H kill data.

Uses proximity_kill_outcome to find head-to-head pairs and classify them:
- NEMESIS: opponent who kills you >70% of encounters
- PREY: opponent you kill >70% of encounters
- RIVAL: balanced matchup (40-60% win rate)
- INSUFFICIENT_DATA: fewer than 5 total encounters
"""

import re
from typing import Optional
from website.backend.logging_config import get_app_logger

logger = get_app_logger("rivalries")

MIN_ENCOUNTERS = 5

# ET:Legacy kill_mod → weapon name mapping
KILL_MOD_NAMES = {
    3: "Knife", 4: "Luger", 5: "Colt", 6: "Luger", 7: "Colt",
    8: "MP40", 9: "Thompson", 10: "Sten", 11: "Garand",
    12: "Silenced", 13: "FG42", 14: "FG42 Scope", 15: "Panzerfaust",
    16: "Grenade", 17: "Flamethrower", 18: "Grenade",
    22: "Dynamite", 23: "Airstrike", 26: "Artillery",
    37: "Carbine", 38: "K98", 39: "GPG40", 40: "M7",
    41: "Landmine", 42: "Satchel", 44: "Mobile MG42",
    45: "Silenced Colt", 46: "Garand Scope",
    50: "K43", 51: "K43 Scope", 52: "Mortar",
    53: "Akimbo Colt", 54: "Akimbo Luger",
    55: "Akimbo Silenced Colt", 56: "Akimbo Silenced Luger",
    60: "Sten",
    66: "Backstab",
}


def _strip_et_colors(name: str) -> str:
    """Remove ET:Legacy color codes (^0-^9, ^a-^z, ^A-^Z) from names."""
    if not name:
        return name
    return re.sub(r'\^[0-9a-zA-Z]', '', name)


def _weapon_name(kill_mod) -> str:
    """Map kill_mod integer to human-readable weapon name."""
    if kill_mod is None:
        return "Unknown"
    return KILL_MOD_NAMES.get(int(kill_mod), f"MOD_{kill_mod}")


def _classify(win_rate: float, total: int) -> str:
    """Classify a H2H relationship based on win rate and encounter count."""
    if total < MIN_ENCOUNTERS:
        return "INSUFFICIENT_DATA"
    if win_rate >= 0.70:
        return "PREY"
    if win_rate <= 0.30:
        return "NEMESIS"
    if 0.40 <= win_rate <= 0.60:
        return "RIVAL"
    return "CONTENDER"


class RivalriesService:
    def __init__(self, db):
        self.db = db

    async def get_player_rivalries(self, player_guid: str) -> dict:
        """Get nemesis, prey, rival for a player from all H2H pairs."""
        # Get kills BY this player against each opponent
        kills_as_killer = await self.db.fetch_all("""
            SELECT victim_guid,
                   MAX(victim_name) as victim_name,
                   COUNT(*) as kills
            FROM proximity_kill_outcome
            WHERE killer_guid = $1
              AND killer_guid NOT LIKE 'OMNIBOT%'
              AND victim_guid NOT LIKE 'OMNIBOT%'
              AND killer_guid != victim_guid
            GROUP BY victim_guid
        """, (player_guid,))

        # Get kills ON this player by each opponent
        kills_as_victim = await self.db.fetch_all("""
            SELECT killer_guid,
                   MAX(killer_name) as killer_name,
                   COUNT(*) as kills
            FROM proximity_kill_outcome
            WHERE victim_guid = $1
              AND killer_guid NOT LIKE 'OMNIBOT%'
              AND victim_guid NOT LIKE 'OMNIBOT%'
              AND killer_guid != victim_guid
            GROUP BY killer_guid
        """, (player_guid,))

        # Get player name
        player_name_row = await self.db.fetch_one("""
            SELECT COALESCE(
                (SELECT MAX(killer_name) FROM proximity_kill_outcome WHERE killer_guid = $1),
                (SELECT MAX(victim_name) FROM proximity_kill_outcome WHERE victim_guid = $1)
            )
        """, (player_guid,))
        player_name = _strip_et_colors((player_name_row[0] if player_name_row else None) or player_guid[:8])

        # Build opponent map: guid -> {name, kills_by_player, kills_on_player}
        opponents = {}
        for row in (kills_as_killer or []):
            guid = row[0]
            opponents[guid] = {
                "guid": guid,
                "name": _strip_et_colors(row[1] or guid[:8]),
                "kills_by_player": row[2],
                "kills_on_player": 0,
            }

        for row in (kills_as_victim or []):
            guid = row[0]
            if guid in opponents:
                opponents[guid]["kills_on_player"] = row[2]
                # Use the more recent name if available
                name = _strip_et_colors(row[1] or guid[:8])
                if name:
                    opponents[guid]["name"] = name
            else:
                opponents[guid] = {
                    "guid": guid,
                    "name": _strip_et_colors(row[1] or guid[:8]),
                    "kills_by_player": 0,
                    "kills_on_player": row[2],
                }

        # Classify each pair
        pairs = []
        for guid, data in opponents.items():
            total = data["kills_by_player"] + data["kills_on_player"]
            win_rate = data["kills_by_player"] / total if total > 0 else 0.5
            classification = _classify(win_rate, total)
            pairs.append({
                "opponent_guid": guid,
                "opponent_name": data["name"],
                "guid": guid,
                "name": data["name"],
                "kills_by_player": data["kills_by_player"],
                "kills_on_player": data["kills_on_player"],
                "total_encounters": total,
                "win_rate": round(win_rate, 3),
                "classification": classification,
            })

        # Sort by total encounters descending
        pairs.sort(key=lambda p: p["total_encounters"], reverse=True)

        # Find top nemesis, prey, rival (only from pairs with enough data)
        nemesis = None
        prey = None
        rival = None

        for p in pairs:
            if p["classification"] == "NEMESIS" and nemesis is None:
                nemesis = p
            elif p["classification"] == "PREY" and prey is None:
                prey = p
            elif p["classification"] == "RIVAL" and rival is None:
                rival = p
            if nemesis and prey and rival:
                break

        return {
            "player_guid": player_guid,
            "player_name": player_name,
            "nemesis": nemesis,
            "prey": prey,
            "rival": rival,
            "all_pairs": pairs[:50],
            "total_opponents": len(pairs),
        }

    async def get_head_to_head(self, guid1: str, guid2: str) -> dict:
        """Full H2H breakdown between two players."""
        # Kills p1 → p2
        p1_kills_row = await self.db.fetch_one("""
            SELECT COUNT(*), MAX(killer_name)
            FROM proximity_kill_outcome
            WHERE killer_guid = $1 AND victim_guid = $2
        """, (guid1, guid2))

        # Kills p2 → p1
        p2_kills_row = await self.db.fetch_one("""
            SELECT COUNT(*), MAX(killer_name)
            FROM proximity_kill_outcome
            WHERE killer_guid = $1 AND victim_guid = $2
        """, (guid2, guid1))

        p1_kills = p1_kills_row[0] if p1_kills_row else 0
        p1_name = _strip_et_colors((p1_kills_row[1] if p1_kills_row else None) or guid1[:8])
        p2_kills = p2_kills_row[0] if p2_kills_row else 0
        p2_name = _strip_et_colors((p2_kills_row[1] if p2_kills_row else None) or guid2[:8])

        # If p1 has no name from kills, try as victim
        if p1_name == guid1[:8]:
            fallback = await self.db.fetch_one(
                "SELECT MAX(victim_name) FROM proximity_kill_outcome WHERE victim_guid = $1",
                (guid1,))
            if fallback and fallback[0]:
                p1_name = _strip_et_colors(fallback[0])
        if p2_name == guid2[:8]:
            fallback = await self.db.fetch_one(
                "SELECT MAX(victim_name) FROM proximity_kill_outcome WHERE victim_guid = $1",
                (guid2,))
            if fallback and fallback[0]:
                p2_name = _strip_et_colors(fallback[0])

        total = p1_kills + p2_kills
        win_rate = p1_kills / total if total > 0 else 0.5
        classification = _classify(win_rate, total)

        # Weapon breakdown p1 → p2
        p1_weapons_rows = await self.db.fetch_all("""
            SELECT kill_mod, COUNT(*) as cnt
            FROM proximity_kill_outcome
            WHERE killer_guid = $1 AND victim_guid = $2
            GROUP BY kill_mod ORDER BY cnt DESC
        """, (guid1, guid2))

        p1_weapons = [
            {"weapon": _weapon_name(r[0]), "kill_mod": r[0], "kills": r[1]}
            for r in (p1_weapons_rows or [])
        ]

        # Weapon breakdown p2 → p1
        p2_weapons_rows = await self.db.fetch_all("""
            SELECT kill_mod, COUNT(*) as cnt
            FROM proximity_kill_outcome
            WHERE killer_guid = $1 AND victim_guid = $2
            GROUP BY kill_mod ORDER BY cnt DESC
        """, (guid2, guid1))

        p2_weapons = [
            {"weapon": _weapon_name(r[0]), "kill_mod": r[0], "kills": r[1]}
            for r in (p2_weapons_rows or [])
        ]

        # Per-map breakdown
        per_map_rows = await self.db.fetch_all("""
            SELECT map_name,
                   SUM(CASE WHEN killer_guid = $1 AND victim_guid = $2 THEN 1 ELSE 0 END) as p1_kills,
                   SUM(CASE WHEN killer_guid = $2 AND victim_guid = $1 THEN 1 ELSE 0 END) as p2_kills
            FROM proximity_kill_outcome
            WHERE (killer_guid = $1 AND victim_guid = $2)
               OR (killer_guid = $2 AND victim_guid = $1)
            GROUP BY map_name
            ORDER BY (SUM(CASE WHEN killer_guid = $1 AND victim_guid = $2 THEN 1 ELSE 0 END)
                    + SUM(CASE WHEN killer_guid = $2 AND victim_guid = $1 THEN 1 ELSE 0 END)) DESC
        """, (guid1, guid2))

        per_map = [
            {
                "map": r[0],
                "p1_kills": r[1],
                "p2_kills": r[2],
                "total": r[1] + r[2],
            }
            for r in (per_map_rows or [])
        ]

        return {
            "guid1": guid1,
            "guid2": guid2,
            "p1_name": p1_name,
            "p2_name": p2_name,
            "p1_kills": p1_kills,
            "p2_kills": p2_kills,
            "total": total,
            "win_rate": round(win_rate, 3),
            "classification": classification,
            "p1_weapons": p1_weapons,
            "p2_weapons": p2_weapons,
            "per_map": per_map,
        }

    async def get_rivalry_leaderboard(self, limit: int = 20) -> list:
        """Top rivalry pairs by total encounters (human players only)."""
        rows = await self.db.fetch_all("""
            SELECT
                a.killer_guid as guid1,
                a.victim_guid as guid2,
                a.killer_name as name1,
                a.victim_name as name2,
                a.kills as kills_1to2,
                COALESCE(b.kills, 0) as kills_2to1
            FROM (
                SELECT killer_guid, victim_guid,
                       MAX(killer_name) as killer_name,
                       MAX(victim_name) as victim_name,
                       COUNT(*) as kills
                FROM proximity_kill_outcome
                WHERE killer_guid NOT LIKE 'OMNIBOT%'
                  AND victim_guid NOT LIKE 'OMNIBOT%'
                  AND killer_guid != victim_guid
                GROUP BY killer_guid, victim_guid
            ) a
            LEFT JOIN (
                SELECT killer_guid, victim_guid, COUNT(*) as kills
                FROM proximity_kill_outcome
                WHERE killer_guid NOT LIKE 'OMNIBOT%'
                  AND victim_guid NOT LIKE 'OMNIBOT%'
                  AND killer_guid != victim_guid
                GROUP BY killer_guid, victim_guid
            ) b ON a.killer_guid = b.victim_guid AND a.victim_guid = b.killer_guid
            WHERE a.killer_guid < a.victim_guid
            ORDER BY (a.kills + COALESCE(b.kills, 0)) DESC
            LIMIT $1
        """, (limit,))

        pairs = []
        for r in (rows or []):
            guid1, guid2 = r[0], r[1]
            name1 = _strip_et_colors(r[2] or guid1[:8])
            name2 = _strip_et_colors(r[3] or guid2[:8])
            kills_1to2 = r[4]
            kills_2to1 = r[5]
            total = kills_1to2 + kills_2to1
            win_rate = kills_1to2 / total if total > 0 else 0.5
            classification = _classify(win_rate, total)

            pairs.append({
                "guid1": guid1,
                "guid2": guid2,
                "name1": name1,
                "name2": name2,
                "kills_1to2": kills_1to2,
                "kills_2to1": kills_2to1,
                "total": total,
                "win_rate": round(win_rate, 3),
                "classification": classification,
            })

        return pairs
