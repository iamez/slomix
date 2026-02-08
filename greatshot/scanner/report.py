"""Human-readable report generator for demo analysis."""

from __future__ import annotations

from typing import Any, Dict, Iterable


def _fmt_ms(ms: int | None) -> str:
    if ms is None:
        return "--"
    ms = int(ms)
    total = max(0, ms // 1000)
    minutes = total // 60
    seconds = total % 60
    return f"{minutes:02d}:{seconds:02d}"


def _lines_for_players(players: Iterable[Dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for player in players:
        name = player.get("name") or "unknown"
        teams = ",".join(player.get("teams") or []) or "unknown"
        first_seen = _fmt_ms(player.get("first_seen_ms"))
        lines.append(f"- {name} | teams={teams} | first_seen={first_seen}")
    return lines


def build_text_report(analysis: Dict[str, Any]) -> str:
    metadata = analysis.get("metadata", {})
    stats = analysis.get("stats", {})
    players = analysis.get("players", [])
    timeline = analysis.get("timeline", [])
    highlights = analysis.get("highlights", [])
    warnings = analysis.get("warnings", [])

    out: list[str] = []
    out.append("ET:Legacy Demo Analysis Report")
    out.append("=" * 32)
    out.append(f"Schema version: {analysis.get('schema_version', '--')}")
    out.append(f"Parser: {analysis.get('parser', {}).get('name', '--')}")
    out.append(f"Profile: {metadata.get('profile', '--')}")
    out.append(f"Map: {metadata.get('map', '--')}")
    out.append(f"Gametype: {metadata.get('gametype', '--')}")
    out.append(f"Mod: {metadata.get('mod', '--')} {metadata.get('mod_version', '')}".rstrip())
    out.append(f"Duration: {_fmt_ms(metadata.get('duration_ms'))}")
    out.append(f"Rounds detected: {len(metadata.get('rounds', []))}")
    out.append("")

    out.append("Quick Stats")
    out.append("-" * 10)
    out.append(f"Players: {len(players)}")
    out.append(f"Timeline events: {len(timeline)}")
    out.append(f"Kills: {stats.get('kill_count', 0)}")
    out.append(f"Headshots: {stats.get('headshot_count', 0)}")
    out.append(f"Chat lines: {stats.get('chat_count', 0)}")
    out.append("")

    out.append("Players")
    out.append("-" * 7)
    out.extend(_lines_for_players(players))
    out.append("")

    out.append("Highlights")
    out.append("-" * 10)
    if highlights:
        for idx, item in enumerate(highlights, start=1):
            out.append(
                f"{idx:02d}. {item.get('type', '--')} | {item.get('player', '--')} | "
                f"{_fmt_ms(item.get('start_ms'))}-{_fmt_ms(item.get('end_ms'))} | "
                f"score={item.get('score', 0):.2f}"
            )
            explanation = item.get("explanation")
            if explanation:
                out.append(f"    {explanation}")
    else:
        out.append("No highlights detected.")
    out.append("")

    if warnings:
        out.append("Warnings")
        out.append("-" * 8)
        for warning in warnings:
            out.append(f"- {warning}")

    return "\n".join(out).rstrip() + "\n"
