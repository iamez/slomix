"""Highlight detection for clip-worthy ET:Legacy moments."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Tuple

from greatshot.config import HIGHLIGHT_DEFAULTS
from greatshot.contracts.types import Highlight


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
                        meta={
                            "kill_count": count,
                            "headshots": hs_count,
                            "window_ms": window_ms,
                        },
                    )
                )

    return highlights


def _detect_sprees(kills: List[Dict[str, Any]], cfg: Dict[str, int]) -> List[Highlight]:
    spree_count: Dict[str, int] = defaultdict(int)
    spree_start: Dict[str, int] = {}
    highlights: List[Highlight] = []

    for event in kills:
        attacker = event["attacker"]
        victim = event["victim"]
        t_ms = int(event["t_ms"])

        if spree_count[attacker] == 0:
            spree_start[attacker] = t_ms
        spree_count[attacker] += 1

        if spree_count[attacker] >= cfg["spree_min"]:
            highlights.append(
                Highlight(
                    highlight_type="spree",
                    player=attacker,
                    start_ms=spree_start.get(attacker, t_ms),
                    end_ms=t_ms,
                    score=float(spree_count[attacker] * 7),
                    explanation=f"{spree_count[attacker]} kills without dying",
                    meta={"kills_without_death": spree_count[attacker]},
                )
            )

        spree_count[victim] = 0
        spree_start.pop(victim, None)

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

            start_ms = int(headshots[left]["t_ms"])
            end_ms = int(headshots[right]["t_ms"])
            duration = max(1, end_ms - start_ms)
            is_aim_moment = count >= cfg["aim_moment_headshots"]
            h_type = "aim_moment" if is_aim_moment else "quick_headshot_chain"
            explanation = (
                f"{count} headshot kills in {duration / 1000:.2f}s"
                if is_aim_moment
                else f"Headshot burst: {count} in {duration / 1000:.2f}s"
            )
            highlights.append(
                Highlight(
                    highlight_type=h_type,
                    player=player,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    score=float(count * (9 if is_aim_moment else 6)),
                    explanation=explanation,
                    meta={"headshots": count, "window_ms": duration},
                )
            )

    return highlights


def detect_highlights(
    events: Iterable[Dict[str, Any]],
    thresholds: Dict[str, int] | None = None,
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
