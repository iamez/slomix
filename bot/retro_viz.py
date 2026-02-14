#!/usr/bin/env python3
"""
Retro Viz v2 - embedded PoC for retro HUD-style 6-panel visualizations
Placed in bot/ so ultimate_bot can import create_round_visualization()

This file is intentionally self-contained: it will parse a given
`local_stats/*.txt` stats file using the repo's existing parser (if
available) or a minimal internal fallback, then render the 6-panel
visualization and return a matplotlib Figure.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from pathlib import Path
import sys
import os

# Try to reuse existing parser if available
ParserClass = None
try:
    from bot.community_stats_parser import CommunityStatsParser as _CSP
    ParserClass = _CSP
except ImportError:
    try:
        from bot.community_stats_parser import C0RNP0RN3StatsParser as _CSP2
        ParserClass = _CSP2
    except ImportError:
        try:
            # Fallback to top-level shim
            from community_stats_parser import CommunityStatsParser as _CSP3
            ParserClass = _CSP3
        except ImportError:
            ParserClass = None

# Simple internal parser fallback (very small subset) if no parser found
def parse_stats_file_simple(path: str):
    """Minimal, tolerant parser that extracts map, round and simple per-player rows.
    This fallback is only used when no project parser is importable.
    """
    if not os.path.exists(path):
        return {"success": False, "error": "file not found", "players": []}

    players = []
    map_name = "Unknown"
    round_num = 1
    timestamp = "Unknown"

    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = [line.rstrip("\n") for line in f.readlines()]
        if lines:
            header = lines[0]
            parts = header.split("\\")
            if len(parts) >= 4:
                map_name = parts[1]
                round_num = int(parts[3]) if parts[3].isdigit() else 1
            timestamp = Path(path).stem.split("-")[0]

            for ln in lines[1:]:
                if ln.strip() and "\\" in ln:
                    parts = ln.split("\\")
                    name = parts[1] if len(parts) > 1 else "unknown"
                    # crude extraction of damage/kills in the tail if present
                    tail = ln.split("\t")[-1]
                    # fallback values
                    kills = 0
                    deaths = 0
                    dmg = 0
                    try:
                        fields = tail.split()
                        if fields:
                            # heuristic: first numeric near end -> kills
                            nums = [int(x) for x in fields if x.isdigit()]
                            if nums:
                                kills = nums[0]
                    except Exception:
                        pass
                    players.append({"name": name, "kills": kills, "deaths": deaths, "dpm": 0, "damage_given": dmg})

        return {"success": True, "map_name": map_name, "round_num": round_num, "players": players, "timestamp": timestamp}
    except Exception as e:
        return {"success": False, "error": str(e), "players": []}


# --- Styling/config ---
COLORS = {
    'background': '#0a1f3d',
    'background_dark': '#081626',
    'grid': '#00ffff',
    'primary': '#00ffff',
    'secondary': '#ff6b35',
    'accent': '#ffbe0b',
    'success': '#00ff41',
    'danger': '#ff006e',
    'text': '#ffffff',
    'text_dim': '#8892b0',
}

FONTS = {
    'title': {'family': 'monospace', 'size': 18, 'weight': 'bold'},
    'subtitle': {'family': 'monospace', 'size': 12, 'weight': 'bold'},
    'body': {'family': 'monospace', 'size': 9},
}


def _normalize_players(raw_players):
    """Normalize different parser outputs into list of player dicts with keys we expect."""
    out = []
    for p in raw_players:
        name = p.get('name') or p.get('clean_name') or p.get('player_name') or p.get('raw_name') or 'Unknown'
        kills = int(p.get('kills') or p.get('kills_total') or 0)
        deaths = int(p.get('deaths') or 0)
        dpm = float(p.get('dpm') or p.get('dpm_value') or 0)
        dmg = int(p.get('damage_given') or p.get('damage') or 0)
        gibs = int(p.get('gibs') or 0)
        denied = int(p.get('playtime_denied') or p.get('denied_playtime') or 0)
        time_played = int(p.get('time_played_seconds') or int(p.get('time_played_minutes',0)*60) or 0)
        time_dead = int(p.get('time_dead_seconds') or int(p.get('time_dead_minutes',0)*60) or 0)
        revives = int(p.get('revives_given') or p.get('times_revived') or 0)
        out.append({
            'name': name,
            'kills': kills,
            'deaths': deaths,
            'dpm': dpm,
            'damage_given': dmg,
            'gibs': gibs,
            'denied': denied,
            'time_played_seconds': time_played,
            'time_dead_seconds': time_dead,
            'revives_given': revives,
        })
    return out


def create_round_visualization(stats_file_path):
    """Main entrypoint used by ultimate_bot: accepts a path to the .txt stats file and returns a matplotlib Figure."""
    # Parse using repo parser if available
    if ParserClass:
        try:
            parser = ParserClass()
            parsed = parser.parse_stats_file(stats_file_path)
        except Exception:
            parsed = parse_stats_file_simple(stats_file_path)
    else:
        parsed = parse_stats_file_simple(stats_file_path)

    if not parsed or not parsed.get('success'):
        raise ValueError(f"Failed to parse stats file: {stats_file_path} - {parsed.get('error')}")

    raw_players = parsed.get('players', [])
    players = _normalize_players(raw_players)
    map_name = parsed.get('map_name') or 'Unknown'
    round_num = parsed.get('round_num') or parsed.get('round_number') or 1
    timestamp = parsed.get('timestamp') or parsed.get('date') or ''

    # Sort players by kills
    players_sorted = sorted(players, key=lambda x: x['kills'], reverse=True)

    # Begin figure
    fig = plt.figure(figsize=(20, 12), facecolor=COLORS['background'])
    gs = fig.add_gridspec(3, 3, hspace=0.25, wspace=0.25, left=0.04, right=0.96, top=0.94, bottom=0.04)

    # Panel 1: Radar (combat overview)
    ax1 = fig.add_subplot(gs[0, :2], projection='polar')
    categories = ['Kills', 'Deaths', 'DPM', 'Damage', 'Gibs']
    angles = np.linspace(0, 2*np.pi, len(categories), endpoint=False).tolist()
    angles += angles[:1]

    # Plot up to 4 players
    max_vals = {k: max((p.get(k.lower(),0) for p in players_sorted), default=1) or 1 for k in categories}
    for i, p in enumerate(players_sorted[:4]):
        vals = [p['kills'], max_vals['Deaths'] - p['deaths'], p['dpm'], p['damage_given'], p['gibs']]
        vals = [ (v / max_vals[c]) * 100 if max_vals[c] else 0 for v, c in zip(vals, categories)]
        vals += vals[:1]
        ax1.plot(angles, vals, label=p['name'], linewidth=2)
        ax1.fill(angles, vals, alpha=0.15)
    ax1.set_xticks(angles[:-1])
    ax1.set_xticklabels(categories, color=COLORS['text'])
    ax1.set_yticklabels([])
    ax1.set_title(f"COMBAT OVERVIEW - {map_name} R{round_num}", color=COLORS['primary'])

    # Panel 2: Info box
    ax2 = fig.add_subplot(gs[0, 2])
    ax2.axis('off')
    ax2.text(0.5, 0.9, f"{map_name} - ROUND {round_num}", ha='center', va='top', color=COLORS['primary'], fontsize=14, weight='bold')
    ax2.text(0.5, 0.7, f"{timestamp}", ha='center', va='center', color=COLORS['text_dim'], fontsize=10)
    if players_sorted:
        ax2.text(0.5, 0.45, f"MVP: {players_sorted[0]['name']}", ha='center', va='center', color=COLORS['accent'], fontsize=11)

    # Panel 3: Racing bars (kills)
    ax3 = fig.add_subplot(gs[1, 0])
    top_players = players_sorted[:10]
    names = [p['name'][:15] for p in top_players]
    vals = [p['kills'] for p in top_players]
    y = np.arange(len(names))
    ax3.barh(y, vals, color=COLORS['primary'])
    ax3.set_yticks(y)
    ax3.set_yticklabels(names, color=COLORS['text'])
    ax3.invert_yaxis()
    ax3.set_title('TOP FRAGGERS', color=COLORS['accent'])

    # Panel 4: Heatmap (Gibs/Kills)
    ax4 = fig.add_subplot(gs[1, 1])
    ax4.axis('off')
    ax4.text(0.5, 0.95, 'GIBS / KILLS', ha='center', color=COLORS['secondary'])
    for i, p in enumerate(players_sorted[:6]):
        ax4.text(0.1, 0.8 - i*0.12, f"{p['name'][:12]:12}  K:{p['kills']:3d}  G:{p['gibs']:3d}", color=COLORS['text'])

    # Panel 5: Support stats (revives / denied / dead)
    ax5 = fig.add_subplot(gs[1, 2])
    ax5.axis('off')
    ax5.text(0.5, 0.95, 'SUPPORT', ha='center', color=COLORS['accent'])
    for i, p in enumerate(players_sorted[:6]):
        ax5.text(0.05, 0.8 - i*0.12, f"{p['name'][:12]:12} RV:{p['revives_given']:2d} DEN:{int(p['denied']/60):3d}m", color=COLORS['text'])

    # Panel 6: Playtime Denied focused bottom panel
    ax6 = fig.add_subplot(gs[2, :])
    names = [p['name'][:12] for p in players_sorted[:10]]
    denied_vals = [p['denied']/60 for p in players_sorted[:10]]
    kills_vals = [p['kills'] for p in players_sorted[:10]]
    gibs_vals = [p['gibs'] for p in players_sorted[:10]]
    x = np.arange(len(names))
    width = 0.6
    ax6.bar(x - width/3, denied_vals, width/3, label='Denied (mins)', color=COLORS['secondary'])
    ax6.bar(x, kills_vals, width/3, label='Kills', color=COLORS['success'])
    ax6.bar(x + width/3, gibs_vals, width/3, label='Gibs', color=COLORS['primary'])
    # DPM overlay
    dpm_vals = [p['dpm'] for p in players_sorted[:10]]
    ax6.plot(x, dpm_vals, color=COLORS['grid'], marker='o', linewidth=1.5)
    ax6.set_xticks(x)
    ax6.set_xticklabels(names, rotation=45, ha='right', color=COLORS['text'])
    ax6.set_title('PLAYTIME DENIED - KEY METRIC', color=COLORS['accent'])
    ax6.legend(loc='upper right', fontsize=8)

    fig.suptitle(f'═══ ET:LEGACY RETRO VIS ═══   {map_name.upper()} - ROUND {round_num}', fontsize=18, color=COLORS['primary'])
    plt.tight_layout()
    return fig
