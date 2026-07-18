"""Canonical parsing for session_results.round_details (IMP-002).

Two shapes exist in production:

  v1 (legacy)  — a bare JSON LIST of per-map entries. Two writer paths used
                 different point keys: ``team1_points/team2_points``
                 (calculate_session_scores) and ``team_a_points/team_b_points``
                 (calculate_session_scores_with_teams). team1 == team_a ==
                 the row's ``team_1_guids`` side in BOTH paths.
  v2 (current) — a JSON DICT ``{"round_details_version": 2, "maps": [...]}``
                 whose entries additionally carry ``match_id``,
                 ``map_play_seq`` and ``round_start_unix`` so a later reader
                 (e.g. the prediction resolver) can place each map in time
                 WITHOUT fragile alignment against the rounds table.

Every reader must go through :func:`parse_round_details` so the shape change
cannot silently break a consumer.
"""
from __future__ import annotations

import json
from typing import Any

ROUND_DETAILS_VERSION = 2


def parse_round_details(raw: Any) -> tuple[int, list[dict]]:
    """Normalize a stored round_details value to ``(version, maps_list)``.

    Returns ``(0, [])`` for NULL/empty/unparseable input — callers treat
    version 0 as "no per-map data".
    """
    if raw is None:
        return 0, []
    if isinstance(raw, (str, bytes)):
        raw = raw.strip() if isinstance(raw, str) else raw
        if not raw:
            return 0, []
        try:
            raw = json.loads(raw)
        except (ValueError, TypeError):
            return 0, []
    if isinstance(raw, list):
        return 1, [e for e in raw if isinstance(e, dict)]
    if isinstance(raw, dict):
        maps = raw.get("maps")
        if isinstance(maps, list):
            try:
                version = int(raw.get("round_details_version", ROUND_DETAILS_VERSION))
            except (TypeError, ValueError):
                version = ROUND_DETAILS_VERSION
            return version, [e for e in maps if isinstance(e, dict)]
    return 0, []


def entry_points(entry: dict) -> tuple[int, int] | None:
    """Per-map points for the row's team_1/team_2, tolerating both key sets.

    Returns None when neither key set is present (reader must treat the entry
    as unusable rather than assume 0:0).
    """
    t1 = entry.get("team1_points", entry.get("team_a_points"))
    t2 = entry.get("team2_points", entry.get("team_b_points"))
    if t1 is None or t2 is None:
        return None
    try:
        return int(t1), int(t2)
    except (TypeError, ValueError):
        return None


def entry_map_name(entry: dict) -> str | None:
    """Map name of an entry, tolerating both key spellings."""
    name = entry.get("map", entry.get("map_name"))
    return name if isinstance(name, str) and name else None
