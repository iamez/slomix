"""Human-readable report generator for demo analysis."""

from __future__ import annotations

from typing import Any, Dict, Iterable


def _fmt_ms(ms: int | None, offset_ms: int = 0) -> str:
    if ms is None:
        return "--"
    ms = max(0, int(ms) - int(offset_ms))
    total = ms // 1000
    hours = total // 3600
    minutes = (total % 3600) // 60
    seconds = total % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def _lines_for_players(players: Iterable[Dict[str, Any]], offset_ms: int = 0) -> list[str]:
    lines: list[str] = []
    for player in players:
        name = player.get("name") or "unknown"
        teams = ",".join(player.get("teams") or []) or "unknown"
        first_seen = _fmt_ms(player.get("first_seen_ms"), offset_ms)
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

    # Use round start offset to convert absolute server times to gameplay-relative
    round_offset = int(metadata.get("start_ms") or 0)

    out.append("Players")
    out.append("-" * 7)
    out.extend(_lines_for_players(players, round_offset))
    out.append("")

    out.append("Highlights")
    out.append("-" * 10)
    if highlights:
        for idx, item in enumerate(highlights, start=1):
            out.append(
                f"{idx:02d}. {item.get('type', '--')} | {item.get('player', '--')} | "
                f"{_fmt_ms(item.get('start_ms'), round_offset)}-{_fmt_ms(item.get('end_ms'), round_offset)} | "
                f"score={item.get('score', 0):.2f}"
            )
            explanation = item.get("explanation")
            if explanation:
                out.append(f"    {explanation}")

            meta = item.get("meta") or {}

            victims = meta.get("victims")
            if victims:
                out.append(f"    Victims: {', '.join(victims)}")

            weapons = meta.get("weapons_used")
            if weapons:
                parts = [f"{w}x{c}" for w, c in sorted(weapons.items(), key=lambda p: -p[1])]
                out.append(f"    Weapons: {', '.join(parts)}")

            gaps = meta.get("kill_gaps_ms")
            if gaps:
                avg = meta.get("avg_kill_gap_ms", 0)
                fastest = meta.get("fastest_kill_gap_ms", 0)
                out.append(f"    Kill rhythm: avg {avg}ms, fastest {fastest}ms")

            attacker_stats = meta.get("attacker_stats")
            if attacker_stats:
                k = attacker_stats.get("kills", 0)
                d = attacker_stats.get("deaths", 0)
                kdr = attacker_stats.get("kdr", 0)
                acc = attacker_stats.get("accuracy")
                acc_str = f", acc={acc}%" if acc is not None else ""
                out.append(f"    Match stats: {k}K/{d}D (KDR {kdr}){acc_str}")
    else:
        out.append("No highlights detected.")
    out.append("")

    player_stats = analysis.get("player_stats")
    if player_stats:
        out.append("Player Stats")
        out.append("-" * 12)
        sorted_players = sorted(
            player_stats.items(),
            key=lambda p: -int(p[1].get("kills", 0)),
        )
        for name, ps in sorted_players[:16]:
            k = ps.get("kills", 0)
            d = ps.get("deaths", 0)
            kdr = round(k / max(1, d), 2)
            dmg = ps.get("damage_given", 0)
            acc = ps.get("accuracy")
            parts = [f"{k}K/{d}D (KDR {kdr})"]
            if dmg:
                parts.append(f"dmg={dmg}")
            if acc is not None:
                parts.append(f"acc={acc}%")
            out.append(f"- {name}: {', '.join(parts)}")
        out.append("")

    if warnings:
        out.append("Warnings")
        out.append("-" * 8)
        for warning in warnings:
            out.append(f"- {warning}")

    return "\n".join(out).rstrip() + "\n"
