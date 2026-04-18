"""Session matrix service — player × map grid with per-round team assignment.

Extracted from sessions_router.py (CR-04 in Mega Audit v3 Sprint 2.5 review).

Builds a Player × Map matrix that respects:
- stopwatch side swaps (R1 attack / R2 defense → same team, opposite side)
- mid-session substitutions (player on both teams appears twice, stats split)
- tri-format side values ('1'/1/'Axis' all canonicalised)
"""
from __future__ import annotations

from shared.services.stopwatch_scoring_service import (
    StopwatchScoringService,
    normalize_side,
)
from website.backend.local_database_adapter import DatabaseAdapter
from website.backend.utils.et_constants import (
    UTILITY_WEAPONS_EXCLUDED_FROM_ACC,
    strip_et_colors,
)


def extract_team_rosters(hardcoded_teams: dict | None) -> dict[str, list[str]]:
    """Normalize get_hardcoded_teams() output to {team_name: [guid, ...]}.

    Tolerates both the `{team: {"guids": [...]}}` shape returned by
    SessionDataService and the legacy `{team: [{"guid": ...}, ...]}` shape.
    """
    rosters: dict[str, list[str]] = {}
    if not hardcoded_teams:
        return rosters
    for team_name, data in hardcoded_teams.items():
        if isinstance(data, dict):
            rosters[team_name] = list(data.get("guids", []))
        elif isinstance(data, list):
            guids: list[str] = []
            for p in data:
                if isinstance(p, dict) and "guid" in p:
                    guids.append(p["guid"])
                elif isinstance(p, str):
                    guids.append(p)
            rosters[team_name] = guids
    return rosters


def _empty_cell(map_idx: int) -> dict:
    return {
        "map_index": map_idx,
        "kills": 0, "deaths": 0, "damage": 0, "time_played": 0,
        "revives": 0, "times_revived": 0, "assists": 0, "gibs": 0,
        "hs_kills": 0, "hits": 0, "shots": 0, "weapon_hs": 0,
        "return_fire_sum": 0.0, "return_fire_count": 0,
        "played": False,
    }


def _finalize_cell(cell: dict) -> None:
    """Compute derived ratios on a fully-summed cell and drop scratch fields."""
    time_played = cell["time_played"]
    cell["dpm"] = round(cell["damage"] * 60.0 / time_played, 1) if time_played > 0 else 0.0
    if cell["deaths"] > 0:
        cell["kd"] = round(cell["kills"] / cell["deaths"], 2)
    else:
        cell["kd"] = float(cell["kills"])
    cell["accuracy"] = round(cell["hits"] / cell["shots"] * 100, 1) if cell["shots"] > 0 else 0.0
    cell["hs_pct"] = round(cell["weapon_hs"] / cell["hits"] * 100, 1) if cell["hits"] > 0 else 0.0
    rf_count = cell.pop("return_fire_count", 0)
    rf_sum = cell.pop("return_fire_sum", 0.0)
    cell["return_fire_ms"] = round(rf_sum / rf_count, 1) if rf_count > 0 else None


def _sum_cells(cells: list[dict]) -> dict:
    totals: dict = {
        "kills": 0, "deaths": 0, "damage": 0, "time_played": 0,
        "revives": 0, "times_revived": 0, "assists": 0, "gibs": 0,
        "hs_kills": 0, "hits": 0, "shots": 0, "weapon_hs": 0,
    }
    rf_sum = 0.0
    rf_count = 0
    for cell in cells:
        for k in totals:
            totals[k] += cell.get(k, 0)
        if cell.get("return_fire_ms") is not None:
            rf_sum += cell["return_fire_ms"]
            rf_count += 1
    time_played = totals["time_played"]
    totals["dpm"] = round(totals["damage"] * 60.0 / time_played, 1) if time_played > 0 else 0.0
    totals["kd"] = round(totals["kills"] / totals["deaths"], 2) if totals["deaths"] > 0 else float(totals["kills"])
    totals["accuracy"] = round(totals["hits"] / totals["shots"] * 100, 1) if totals["shots"] > 0 else 0.0
    totals["hs_pct"] = round(totals["weapon_hs"] / totals["hits"] * 100, 1) if totals["hits"] > 0 else 0.0
    totals["return_fire_ms"] = round(rf_sum / rf_count, 1) if rf_count > 0 else None
    return totals


def _aggregate_roster(roster: list[dict]) -> dict:
    totals: dict = {
        "kills": 0, "deaths": 0, "damage": 0, "time_played": 0,
        "revives": 0, "assists": 0, "gibs": 0, "hs_kills": 0,
        "hits": 0, "shots": 0, "weapon_hs": 0,
    }
    rf_sum = 0.0
    rf_count = 0
    for p in roster:
        t = p["totals"]
        for k in totals:
            totals[k] += t.get(k, 0)
        if t.get("return_fire_ms") is not None:
            rf_sum += t["return_fire_ms"]
            rf_count += 1
    time_played = totals["time_played"]
    totals["dpm_avg"] = round(totals["damage"] * 60.0 / time_played, 1) if time_played > 0 else 0.0
    totals["kd_avg"] = round(totals["kills"] / totals["deaths"], 2) if totals["deaths"] > 0 else float(totals["kills"])
    totals["accuracy_avg"] = round(totals["hits"] / totals["shots"] * 100, 1) if totals["shots"] > 0 else 0.0
    totals["hs_pct_avg"] = round(totals["weapon_hs"] / totals["hits"] * 100, 1) if totals["hits"] > 0 else 0.0
    totals["return_fire_avg"] = round(rf_sum / rf_count, 1) if rf_count > 0 else None
    return totals


class SessionMatrixService:
    """Compute player × map matrix for a session detail view.

    Usage:
        matrix = await SessionMatrixService(db, scoring_service).compute(
            round_ids, matches, scoring_payload, hardcoded_teams,
        )
    """

    def __init__(
        self,
        db: DatabaseAdapter,
        scoring_service: StopwatchScoringService,
    ) -> None:
        self.db = db
        self.scoring_service = scoring_service

    async def compute(
        self,
        round_ids: list[int],
        matches: list[dict],
        scoring_payload: dict,
        hardcoded_teams: dict | None,
    ) -> dict:
        if not round_ids or not matches:
            return {"available": False, "reason": "no_rounds"}

        team_rosters = extract_team_rosters(hardcoded_teams)
        if len(team_rosters) < 2:
            return {"available": False, "reason": "no_teams"}

        dict_keys = list(team_rosters.keys())
        team_a_name = scoring_payload.get("team_a_name") or dict_keys[0]
        team_b_name = scoring_payload.get("team_b_name") or dict_keys[1]

        round_to_map_idx: dict[int, int] = {}
        for map_idx, match in enumerate(matches):
            for r in match["rounds"]:
                round_to_map_idx[r["round_id"]] = map_idx

        side_to_team = await self.scoring_service.build_round_side_to_team_mapping(
            round_ids, team_rosters,
            team_a_name=team_a_name, team_b_name=team_b_name,
        )
        if not side_to_team:
            return {"available": False, "reason": "side_mapping_failed"}

        rows = await self._fetch_stats(round_ids)
        rosters_dict, rounds_detail = self._ingest_rows(
            rows, side_to_team, round_to_map_idx, len(matches),
        )
        self._finalize_rosters(rosters_dict)

        team_a_roster, team_b_roster = self._split_by_team(
            rosters_dict, team_a_name, team_b_name,
        )

        maps_list = self._build_maps_list(matches, scoring_payload)

        return {
            "available": True,
            "team_a_name": team_a_name,
            "team_b_name": team_b_name,
            "maps": maps_list,
            "rosters": {"team_a": team_a_roster, "team_b": team_b_roster},
            "aggregates": {
                "team_a": _aggregate_roster(team_a_roster),
                "team_b": _aggregate_roster(team_b_roster),
            },
            "rounds_detail": rounds_detail,
        }

    async def _fetch_stats(self, round_ids: list[int]) -> list:
        placeholders = ",".join(["?"] * len(round_ids))
        utility_placeholders = ",".join(["?"] * len(UTILITY_WEAPONS_EXCLUDED_FROM_ACC))
        query = f"""
            SELECT p.round_id, p.player_guid, MAX(p.player_name) AS name,
                   p.team AS side,
                   SUM(p.kills) AS kills, SUM(p.deaths) AS deaths,
                   SUM(p.damage_given) AS damage,
                   SUM(p.time_played_seconds) AS time_played,
                   SUM(p.revives_given) AS revives,
                   SUM(p.times_revived) AS times_revived,
                   SUM(p.kill_assists) AS assists,
                   SUM(p.gibs) AS gibs,
                   SUM(p.headshot_kills) AS hs_kills,
                   COALESCE(SUM(w.hits), 0) AS hits,
                   COALESCE(SUM(w.shots), 0) AS shots,
                   COALESCE(SUM(w.headshots), 0) AS weapon_hs,
                   AVG(rm.return_fire_ms) AS return_fire_ms
            FROM player_comprehensive_stats p
            LEFT JOIN (
                SELECT round_id, player_guid,
                       SUM(hits) AS hits, SUM(shots) AS shots, SUM(headshots) AS headshots
                FROM weapon_comprehensive_stats
                WHERE weapon_name NOT IN ({utility_placeholders})
                GROUP BY round_id, player_guid
            ) w ON p.round_id = w.round_id AND p.player_guid = w.player_guid
            LEFT JOIN (
                SELECT round_id, target_guid, AVG(return_fire_ms) AS return_fire_ms
                FROM proximity_reaction_metric
                WHERE return_fire_ms IS NOT NULL AND round_id IS NOT NULL
                GROUP BY round_id, target_guid
            ) rm ON rm.round_id = p.round_id AND rm.target_guid = p.player_guid
            WHERE p.round_id IN ({placeholders})
            GROUP BY p.round_id, p.player_guid, p.team
        """  # nosec B608 - safe: parameterized placeholders (adapter translates ? to $N)
        params = tuple(UTILITY_WEAPONS_EXCLUDED_FROM_ACC) + tuple(round_ids)
        return await self.db.fetch_all(query, params)

    def _ingest_rows(
        self,
        rows: list,
        side_to_team: dict,
        round_to_map_idx: dict[int, int],
        num_maps: int,
    ) -> tuple[dict, dict]:
        rosters_dict: dict[tuple[str, str], dict] = {}
        rounds_detail: dict[int, list[dict]] = {}

        for row in rows:
            round_id = row[0]
            player_guid = row[1]
            player_name = strip_et_colors(row[2] or "")
            side = normalize_side(row[3])
            kills = int(row[4] or 0)
            deaths = int(row[5] or 0)
            damage = int(row[6] or 0)
            time_played = int(row[7] or 0)
            revives = int(row[8] or 0)
            times_revived = int(row[9] or 0)
            assists = int(row[10] or 0)
            gibs = int(row[11] or 0)
            hs_kills = int(row[12] or 0)
            hits = int(row[13] or 0)
            shots = int(row[14] or 0)
            weapon_hs = int(row[15] or 0)
            rf_ms = float(row[16]) if row[16] is not None else None

            if side is None:
                continue
            mapping = side_to_team.get(round_id)
            if not mapping:
                continue
            team_for_round = mapping.get(side)
            if not team_for_round:
                continue
            map_idx = round_to_map_idx.get(round_id)
            if map_idx is None:
                continue

            dpm_row = round(damage * 60.0 / time_played, 1) if time_played > 0 else 0.0
            kd_row = round(kills / deaths, 2) if deaths > 0 else float(kills)
            rounds_detail.setdefault(round_id, []).append({
                "player_guid": player_guid,
                "player_name": player_name,
                "team": team_for_round,
                "side": side,
                "kills": kills, "deaths": deaths, "damage": damage,
                "dpm": dpm_row, "kd": kd_row,
                "time_played": time_played,
                "revives": revives, "assists": assists, "gibs": gibs,
                "hs_kills": hs_kills,
                "return_fire_ms": round(rf_ms, 1) if rf_ms is not None else None,
            })

            key = (team_for_round, player_guid)
            if key not in rosters_dict:
                rosters_dict[key] = {
                    "player_guid": player_guid,
                    "player_name": player_name,
                    "cells_by_map": [_empty_cell(i) for i in range(num_maps)],
                }
            elif player_name and not rosters_dict[key]["player_name"]:
                rosters_dict[key]["player_name"] = player_name

            cell = rosters_dict[key]["cells_by_map"][map_idx]
            cell["kills"] += kills
            cell["deaths"] += deaths
            cell["damage"] += damage
            cell["time_played"] += time_played
            cell["revives"] += revives
            cell["times_revived"] += times_revived
            cell["assists"] += assists
            cell["gibs"] += gibs
            cell["hs_kills"] += hs_kills
            cell["hits"] += hits
            cell["shots"] += shots
            cell["weapon_hs"] += weapon_hs
            if rf_ms is not None:
                cell["return_fire_sum"] += rf_ms
                cell["return_fire_count"] += 1
            cell["played"] = True

        return rosters_dict, rounds_detail

    @staticmethod
    def _finalize_rosters(rosters_dict: dict) -> None:
        for data in rosters_dict.values():
            for cell in data["cells_by_map"]:
                _finalize_cell(cell)
            data["totals"] = _sum_cells(data["cells_by_map"])

    @staticmethod
    def _split_by_team(
        rosters_dict: dict,
        team_a_name: str,
        team_b_name: str,
    ) -> tuple[list[dict], list[dict]]:
        team_a_roster: list[dict] = []
        team_b_roster: list[dict] = []
        for (team_name, _guid), data in rosters_dict.items():
            entry = {
                "player_guid": data["player_guid"],
                "player_name": data["player_name"],
                "totals": data["totals"],
                "cells": data["cells_by_map"],
            }
            if team_name == team_a_name:
                team_a_roster.append(entry)
            elif team_name == team_b_name:
                team_b_roster.append(entry)
        team_a_roster.sort(key=lambda p: p["totals"]["dpm"], reverse=True)
        team_b_roster.sort(key=lambda p: p["totals"]["dpm"], reverse=True)
        return team_a_roster, team_b_roster

    @staticmethod
    def _build_maps_list(matches: list[dict], scoring_payload: dict) -> list[dict]:
        scoring_maps = (
            scoring_payload.get("maps", []) if scoring_payload.get("available") else []
        )
        maps_list: list[dict] = []
        for map_idx, match in enumerate(matches):
            score_entry = scoring_maps[map_idx] if map_idx < len(scoring_maps) else {}
            maps_list.append({
                "map_name": match["map_name"],
                "map_index": map_idx,
                "team_a_score": score_entry.get("team_a_points"),
                "team_b_score": score_entry.get("team_b_points"),
            })
        return maps_list
