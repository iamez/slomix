"""Highlight detection for clip-worthy ET:Legacy moments."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Optional, Tuple

from greatshot.config import HIGHLIGHT_DEFAULTS
from greatshot.contracts.types import Highlight


def _build_kill_sequence(segment: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build a structured kill sequence from a list of kill events."""
    return [
        {
            "t_ms": int(ev.get("t_ms", 0)),
            "victim": ev.get("victim", "unknown"),
            "weapon": ev.get("weapon", "unknown"),
            "headshot": ev.get("hit_region") == "head",
        }
        for ev in segment
    ]


def _build_enriched_meta(segment: List[Dict[str, Any]], base_meta: Dict[str, Any]) -> Dict[str, Any]:
    """Enrich a highlight meta dict with kill_sequence, victims, weapons, and timing gaps."""
    meta = dict(base_meta)

    kill_seq = _build_kill_sequence(segment)
    meta["kill_sequence"] = kill_seq

    meta["victims"] = [k["victim"] for k in kill_seq]

    weapons: Counter[str] = Counter()
    headshot_weapons: Counter[str] = Counter()
    for k in kill_seq:
        weapons[k["weapon"]] += 1
        if k["headshot"]:
            headshot_weapons[k["weapon"]] += 1
    meta["weapons_used"] = dict(weapons)
    if headshot_weapons:
        meta["headshot_weapons"] = dict(headshot_weapons)

    if len(kill_seq) >= 2:
        gaps = [
            kill_seq[i]["t_ms"] - kill_seq[i - 1]["t_ms"]
            for i in range(1, len(kill_seq))
        ]
        meta["kill_gaps_ms"] = gaps
        meta["avg_kill_gap_ms"] = round(sum(gaps) / len(gaps))
        meta["fastest_kill_gap_ms"] = min(gaps)

    return meta


def _kill_events(events: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    kills = []
    for event in events:
        if event.get("type") != "kill":
            continue
        attacker = event.get("attacker")
        victim = event.get("victim")
        if not attacker or not victim:
            continue
        event = dict(event)
        event["t_ms"] = int(event.get("t_ms", 0))
        kills.append(event)
    kills.sort(key=lambda item: item["t_ms"])
    return kills


def _event_window_signature(highlight: Highlight) -> Tuple[str, str, int, int]:
    return (
        highlight.highlight_type,
        highlight.player,
        int(highlight.start_ms),
        int(highlight.end_ms),
    )


def _detect_multi_kills(kills: List[Dict[str, Any]], cfg: Dict[str, int]) -> List[Highlight]:
    by_player: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for event in kills:
        by_player[event["attacker"]].append(event)

    highlights: List[Highlight] = []

    windows = [
        (cfg["multi_kill_window_ms"], cfg["multi_kill_min"], "multi_kill"),
        (cfg["multi_kill_big_window_ms"], cfg["multi_kill_big_min"], "burst_multi_kill"),
    ]

    for player, events in by_player.items():
        times = [item["t_ms"] for item in events]
        for window_ms, min_kills, kind in windows:
            left = 0
            for right in range(len(times)):
                while left <= right and times[right] - times[left] > window_ms:
                    left += 1
                count = right - left + 1
                if count < min_kills:
                    continue

                segment = events[left : right + 1]
                hs_count = sum(1 for item in segment if item.get("hit_region") == "head")
                score = float(count * 10 + hs_count * 2)
                base_meta = {
                    "kill_count": count,
                    "headshots": hs_count,
                    "window_ms": window_ms,
                }
                highlights.append(
                    Highlight(
                        highlight_type=kind,
                        player=player,
                        start_ms=segment[0]["t_ms"],
                        end_ms=segment[-1]["t_ms"],
                        score=score,
                        explanation=(
                            f"{count} kills in {(segment[-1]['t_ms'] - segment[0]['t_ms']) / 1000:.2f}s"
                        ),
                        meta=_build_enriched_meta(segment, base_meta),
                    )
                )

    return highlights


def _detect_sprees(kills: List[Dict[str, Any]], cfg: Dict[str, int]) -> List[Highlight]:
    spree_count: Dict[str, int] = defaultdict(int)
    spree_start: Dict[str, int] = {}
    spree_events: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    highlights: List[Highlight] = []

    for event in kills:
        attacker = event["attacker"]
        victim = event["victim"]
        t_ms = int(event["t_ms"])

        if spree_count[attacker] == 0:
            spree_start[attacker] = t_ms
            spree_events[attacker] = []
        spree_count[attacker] += 1
        spree_events[attacker].append(event)

        if spree_count[attacker] >= cfg["spree_min"]:
            segment = list(spree_events[attacker])
            base_meta = {"kills_without_death": spree_count[attacker]}
            highlights.append(
                Highlight(
                    highlight_type="spree",
                    player=attacker,
                    start_ms=spree_start.get(attacker, t_ms),
                    end_ms=t_ms,
                    score=float(spree_count[attacker] * 7),
                    explanation=f"{spree_count[attacker]} kills without dying",
                    meta=_build_enriched_meta(segment, base_meta),
                )
            )

        spree_count[victim] = 0
        spree_start.pop(victim, None)
        spree_events.pop(victim, None)

    return highlights


def _detect_quick_headshots(kills: List[Dict[str, Any]], cfg: Dict[str, int]) -> List[Highlight]:
    by_player: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for event in kills:
        if event.get("hit_region") == "head":
            by_player[event["attacker"]].append(event)

    highlights: List[Highlight] = []
    window_ms = cfg["quick_headshot_window_ms"]

    for player, headshots in by_player.items():
        headshots.sort(key=lambda item: item["t_ms"])
        left = 0
        for right in range(len(headshots)):
            while left <= right and headshots[right]["t_ms"] - headshots[left]["t_ms"] > window_ms:
                left += 1
            count = right - left + 1
            if count < cfg["quick_headshot_min"]:
                continue

            segment = headshots[left : right + 1]
            start_ms = int(segment[0]["t_ms"])
            end_ms = int(segment[-1]["t_ms"])
            duration = max(1, end_ms - start_ms)
            is_aim_moment = count >= cfg["aim_moment_headshots"]
            h_type = "aim_moment" if is_aim_moment else "quick_headshot_chain"
            explanation = (
                f"{count} headshot kills in {duration / 1000:.2f}s"
                if is_aim_moment
                else f"Headshot burst: {count} in {duration / 1000:.2f}s"
            )
            base_meta = {"headshots": count, "window_ms": duration}
            highlights.append(
                Highlight(
                    highlight_type=h_type,
                    player=player,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    score=float(count * (9 if is_aim_moment else 6)),
                    explanation=explanation,
                    meta=_build_enriched_meta(segment, base_meta),
                )
            )

    return highlights


def detect_highlights(
    events: Iterable[Dict[str, Any]],
    thresholds: Dict[str, int] | None = None,
    player_stats: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Highlight]:
    cfg = dict(HIGHLIGHT_DEFAULTS)
    if thresholds:
        cfg.update({k: int(v) for k, v in thresholds.items()})

    kills = _kill_events(events)
    if not kills:
        return []

    candidates: List[Highlight] = []
    candidates.extend(_detect_multi_kills(kills, cfg))
    candidates.extend(_detect_sprees(kills, cfg))
    candidates.extend(_detect_quick_headshots(kills, cfg))

    # Attach attacker_stats from match-level player stats
    if player_stats:
        for item in candidates:
            ps = player_stats.get(item.player)
            if ps:
                kills_val = int(ps.get("kills", 0))
                deaths_val = int(ps.get("deaths", 0))
                item.meta["attacker_stats"] = {
                    "kills": kills_val,
                    "deaths": deaths_val,
                    "kdr": round(kills_val / max(1, deaths_val), 2),
                    "damage_given": int(ps.get("damage_given", 0)),
                    "accuracy": ps.get("accuracy"),
                }

    deduped: Dict[Tuple[str, str, int, int], Highlight] = {}
    for item in candidates:
        key = _event_window_signature(item)
        current = deduped.get(key)
        if current is None or item.score > current.score:
            deduped[key] = item

    ordered = sorted(
        deduped.values(),
        key=lambda item: (-item.score, item.start_ms, item.end_ms, item.player),
    )
    return ordered
