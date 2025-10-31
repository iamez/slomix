#!/usr/bin/env python3
"""
ET:Legacy Retro Sci-Fi Stats Visualizer
Single Round Visualization System (Phase 1 PoC)

Saves a single multi-panel PNG for the provided `*-round-1.txt` stats file.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import numpy as np
from pathlib import Path
import sys

# Add parent directory for imports
sys.path.append(str(Path(__file__).parent))
# Resolve parser class from whichever module provides it. Some repos use
# `CommunityStatsParser`, others use `C0RNP0RN3StatsParser` (historical).
ParserClass = None
try:
    # Preferred location when running as package
    from bot.community_stats_parser import CommunityStatsParser as _CSP
    ParserClass = _CSP
except Exception:
    try:
        from bot.community_stats_parser import C0RNP0RN3StatsParser as _CSP2
        ParserClass = _CSP2
    except Exception:
        # Fallback to top-level compatibility shim
        try:
            from community_stats_parser import CommunityStatsParser as _CSP3
            ParserClass = _CSP3
        except Exception:
            try:
                from community_stats_parser import C0RNP0RN3StatsParser as _CSP4
                ParserClass = _CSP4
            except Exception as e:
                raise ImportError("Could not find a stats parser class in project: " + str(e))

# ============== STYLE CONFIGURATION ==============

COLORS = {
    'background': '#0a1f3d',
    'background_dark': '#000000',
    'grid': '#00ffff',
    'primary': '#00ffff',
    'secondary': '#ff6b35',
    'accent': '#ffbe0b',
    'success': '#00ff41',
    'danger': '#ff006e',
    'player_colors': [
        '#00ffff', '#ff006e', '#ffbe0b', '#00ff41',
        '#ff6b35', '#9d4edd', '#06ffa5', '#ff5e5b',
    ],
    'text': '#ffffff',
    'text_dim': '#8892b0',
}

FONTS = {
    'title': {'family': 'monospace', 'size': 20, 'weight': 'bold'},
    'subtitle': {'family': 'monospace', 'size': 14, 'weight': 'bold'},
    'body': {'family': 'monospace', 'size': 10},
    'small': {'family': 'monospace', 'size': 8},
}


def add_glow_effect(ax, color='#00ffff', alpha=0.3):
    ax.grid(True, color=color, alpha=alpha, linestyle='--', linewidth=0.5)
    for spine in ('top', 'right', 'bottom', 'left'):
        try:
            ax.spines[spine].set_color(color)
            ax.spines[spine].set_linewidth(1.5)
        except Exception:
            pass


def normalize_stat(value, min_val, max_val):
    if max_val == min_val:
        return 50
    return ((value - min_val) / (max_val - min_val)) * 100


def create_spider_chart(ax, players_data, title="COMBAT OVERVIEW"):
    ax.set_facecolor(COLORS['background_dark'])
    categories = ['Kills', 'Deaths\n(inv)', 'DPM', 'Damage', 'Efficiency', 'Gibs']
    num_vars = len(categories)
    angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
    angles += angles[:1]

    max_kills = max((p.get('kills', 0) for p in players_data), default=1) or 1
    max_deaths = max((p.get('deaths', 0) for p in players_data), default=1) or 1
    max_dpm = max((p.get('dpm', 0) for p in players_data), default=1) or 1
    max_damage = max((p.get('damage_given', 0) for p in players_data), default=1) or 1
    max_gibs = max((p.get('gibs', 0) for p in players_data), default=1) or 1

    for idx, player in enumerate(players_data[:6]):
        values = [
            normalize_stat(player.get('kills', 0), 0, max_kills),
            normalize_stat(max_deaths - player.get('deaths', 0), 0, max_deaths),
            normalize_stat(player.get('dpm', 0), 0, max_dpm),
            normalize_stat(player.get('damage_given', 0), 0, max_damage),
            player.get('efficiency', 0),
            normalize_stat(player.get('gibs', 0), 0, max_gibs),
        ]
        values += values[:1]
        color = COLORS['player_colors'][idx % len(COLORS['player_colors'])]
        ax.plot(angles, values, 'o-', linewidth=2, label=player.get('name', ''),
                color=color, alpha=0.9)
        ax.fill(angles, values, alpha=0.12, color=color)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, color=COLORS['text'], fontsize=9)
    ax.set_ylim(0, 100)
    ax.set_yticks([25, 50, 75, 100])
    ax.set_yticklabels(['25', '50', '75', '100'], color=COLORS['text_dim'], fontsize=8)
    ax.grid(True, color=COLORS['grid'], alpha=0.25, linestyle='--')
    ax.set_title(title, color=COLORS['primary'], pad=12, fontsize=14, fontweight='bold')
    ax.legend(loc='upper right', bbox_to_anchor=(1.25, 1.05), fontsize=8)


def create_racing_bars(ax, players_data, stat='kills', title="TOP FRAGGERS"):
    ax.set_facecolor(COLORS['background_dark'])
    top_players = sorted(players_data, key=lambda x: x.get(stat, 0), reverse=True)[:10]
    names = [p.get('name', '')[:15] for p in top_players]
    values = [p.get(stat, 0) for p in top_players]
    y_pos = np.arange(len(names))
    colors = [COLORS['primary'] for _ in names]
    if values:
        colors[:3] = ['#FFD700', '#C0C0C0', '#CD7F32'][:min(3, len(colors))]

    bars = ax.barh(y_pos, values, color=colors, alpha=0.85, edgecolor=COLORS['grid'], linewidth=0.8)
    for bar, value in zip(bars, values):
        ax.text(value + (max(values) * 0.02 if values else 0.5),
                bar.get_y() + bar.get_height() / 2,
                f'{int(value)}', ha='left', va='center', color=COLORS['text'], fontsize=9, fontweight='bold')

    ax.set_yticks(y_pos)
    ax.set_yticklabels(names, color=COLORS['text'], fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel(stat.upper(), color=COLORS['text'])
    ax.set_title(title, color=COLORS['accent'], fontsize=12)
    add_glow_effect(ax, COLORS['grid'])


def create_heatmap_grid(ax, players_data, title="DAMAGE BREAKDOWN"):
    ax.set_facecolor(COLORS['background_dark'])
    ax.axis('off')
    top_players = players_data[:6]
    categories = ['Dmg Given', 'Dmg Recv', 'TDG', 'TDR']
    stat_keys = ['damage_given', 'damage_received', 'team_damage_given', 'team_damage_received']
    max_vals = {k: max((p.get(k, 0) for p in top_players), default=1) or 1 for k in stat_keys}

    ax.text(0.5, 0.96, title, ha='center', va='top', color=COLORS['secondary'], fontsize=12, fontweight='bold')
    start_x = 0.08
    start_y = 0.82
    cell_w = 0.18
    cell_h = 0.12

    for col_idx, cat in enumerate(categories):
        ax.text(start_x + col_idx * cell_w + cell_w/2, start_y + 0.05, cat, ha='center', va='center', color=COLORS['text'], fontsize=9, fontweight='bold')

    for row_idx, player in enumerate(top_players):
        y = start_y - row_idx * cell_h
        ax.text(start_x - 0.02, y - cell_h/2, player.get('name', '')[:12], ha='right', va='center', color=COLORS['text'], fontsize=9, fontweight='bold')
        for col_idx, key in enumerate(stat_keys):
            x = start_x + col_idx * cell_w
            value = player.get(key, 0)
            intensity = value / (max_vals.get(key, 1) or 1)
            base_color = COLORS['danger'] if 'recv' in key or 'tdr' in key else COLORS['success']
            rect = mpatches.Rectangle((x, y - cell_h), cell_w, cell_h, facecolor=base_color, alpha=0.25 + intensity * 0.6, edgecolor=COLORS['grid'], linewidth=0.8)
            ax.add_patch(rect)
            ax.text(x + cell_w/2, y - cell_h/2, f'{int(value)}', ha='center', va='center', color=COLORS['text'], fontsize=8, fontweight='bold')


def create_support_stats(ax, players_data, title="SUPPORT PERFORMANCE"):
    ax.set_facecolor(COLORS['background_dark'])
    ax.axis('off')
    top_players = players_data[:6]
    names = [p.get('name', '')[:10] for p in top_players]
    stats = {
        'Revives': ([p.get('revives_given', 0) for p in top_players], COLORS['success']),
        'Denied': ([p.get('playtime_denied', 0) for p in top_players], COLORS['accent']),
        'Dead (m)': ([p.get('time_dead_seconds', 0) / 60 for p in top_players], COLORS['danger']),
    }
    ax.text(0.5, 0.95, title, ha='center', va='top', color=COLORS['accent'], fontsize=12, fontweight='bold')
    chart_w = 0.28
    start_x = 0.06
    y_pos = 0.74
    for idx, (stat_name, (values, color)) in enumerate(stats.items()):
        x = start_x + idx * chart_w
        ax.text(x + chart_w/2, y_pos + 0.05, stat_name, ha='center', va='bottom', color=COLORS['text'], fontsize=9, fontweight='bold')
        max_val = max(values) if any(values) else 1
        bar_h = 0.08
        spacing = 0.012
        for player_idx, value in enumerate(values):
            by = y_pos - player_idx * spacing - bar_h
            bw = (value / max_val) * chart_w * 0.9 if max_val else 0
            rect = mpatches.Rectangle((x, by), bw, bar_h * 0.8, facecolor=color, alpha=0.8, edgecolor=COLORS['grid'], linewidth=0.5)
            ax.add_patch(rect)
            if value > 0:
                ax.text(x + bw + 0.01, by + bar_h * 0.4, f'{value:.0f}' if stat_name != 'Dead (m)' else f'{value:.1f}', ha='left', va='center', color=COLORS['text_dim'], fontsize=7)


def create_time_distribution(ax, players_data, title="TIME DISTRIBUTION"):
    ax.set_facecolor(COLORS['background_dark'])
    top_players = players_data[:6]
    names = [p.get('name', '')[:12] for p in top_players]
    time_played = [p.get('time_played_seconds', 0) / 60 for p in top_players]
    time_dead = [p.get('time_dead_seconds', 0) / 60 for p in top_players]
    x = np.arange(len(names))
    width = 0.6
    ax.bar(x, time_played, width, label='Active Time', color=COLORS['success'], alpha=0.8, edgecolor=COLORS['grid'])
    ax.bar(x, time_dead, width, bottom=time_played, label='Dead Time', color=COLORS['danger'], alpha=0.6, edgecolor=COLORS['grid'])
    ax.set_ylabel('Minutes', color=COLORS['text'])
    ax.set_title(title, color=COLORS['primary'], fontsize=12)
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=45, ha='right', color=COLORS['text'], fontsize=8)
    ax.legend(loc='upper right', fontsize=8)
    add_glow_effect(ax, COLORS['grid'])


def create_info_box(ax, match_data, title="MATCH SUMMARY"):
    ax.set_facecolor(COLORS['background_dark'])
    ax.axis('off')
    ax.text(0.5, 0.95, title, ha='center', va='top', color=COLORS['primary'], fontsize=14, fontweight='bold')
    info_lines = [
        f"MAP: {match_data.get('map_name', 'Unknown')}",
        f"ROUND: {match_data.get('round_num', '?')}",
        f"DATE: {match_data.get('date', 'Unknown')}",
        f"DURATION: {match_data.get('duration', 'Unknown')}",
        '',
        f"MVP: {match_data.get('mvp', 'Unknown')}",
        f"BEST DPM: {match_data.get('best_dpm', ('?', 0))[0]} ({match_data.get('best_dpm', ('?', 0))[1]:.1f})",
        f"MOST KILLS: {match_data.get('most_kills', ('?', 0))[0]} ({match_data.get('most_kills', ('?', 0))[1]})",
    ]
    y_start = 0.82
    spacing = 0.09
    for idx, line in enumerate(info_lines):
        color = COLORS['text'] if line else COLORS['background_dark']
        if line.startswith(('MVP', 'BEST', 'MOST')):
            color = COLORS['accent']
        ax.text(0.5, y_start - idx * spacing, line, ha='center', va='top', color=color, fontsize=11, fontweight='bold', family='monospace')


def create_round_visualization(stats_file_path):
    parser = ParserClass()
    result = parser.parse_stats_file(str(stats_file_path))
    if not result.get('success'):
        raise ValueError(f"Failed to parse stats file: {result.get('error', 'Unknown')}")

    players = result.get('players', [])
    map_name = result.get('map_name', 'Unknown')
    round_num = result.get('round_num', 1)

    players_sorted = sorted(players, key=lambda x: x.get('kills', 0), reverse=True)
    players_data = []
    for p in players_sorted:
        # Support multiple parser key variants: some parsers place objective
        # fields under `objective_stats` while others expose them at top-level.
        obj = p.get('objective_stats', {}) if isinstance(p.get('objective_stats', {}), dict) else {}

        # time played (seconds) -- prefer explicit seconds, else convert minutes
        tps = p.get('time_played_seconds') or obj.get('time_played_seconds')
        if not tps:
            mins = p.get('time_played_minutes') or obj.get('time_played_minutes')
            tps = int(mins * 60) if mins else 0

        # time dead (seconds)
        tds = p.get('time_dead_seconds') or obj.get('time_dead_seconds')
        if not tds:
            tdm = p.get('time_dead_minutes') or obj.get('time_dead_minutes')
            tds = int(tdm * 60) if tdm else 0

        players_data.append({
            'name': p.get('name', p.get('clean_name', 'Unknown')),
            'kills': p.get('kills', 0),
            'deaths': p.get('deaths', 0),
            'dpm': p.get('dpm') or obj.get('dpm', 0),
            'damage_given': p.get('damage_given') or obj.get('damage_given', 0),
            'damage_received': p.get('damage_received') or obj.get('damage_received', 0),
            'team_damage_given': p.get('team_damage_given') or obj.get('team_damage_given', 0),
            'team_damage_received': p.get('team_damage_received') or obj.get('team_damage_received', 0),
            'efficiency': p.get('efficiency', 0) or obj.get('efficiency', 0),
            'gibs': p.get('gibs', 0) or obj.get('gibs', 0),
            'revives_given': p.get('revives_given', 0) or obj.get('times_revived', 0) or obj.get('revives_given', 0),
            'playtime_denied': p.get('playtime_denied') or obj.get('denied_playtime') or obj.get('playtime_denied', 0),
            'time_played_seconds': tps or 0,
            'time_dead_seconds': tds or 0,
        })

    match_data = {
        'map_name': map_name,
        'round_num': round_num,
        'date': str(result.get('timestamp', 'Unknown'))[:10],
        'duration': str(result.get('actual_time', 'Unknown')),
        'mvp': result.get('mvp', {}).get('name', 'Unknown') if isinstance(result.get('mvp'), dict) else result.get('mvp', 'Unknown'),
        'best_dpm': (players_sorted[0].get('name', '?'), players_sorted[0].get('dpm', 0)) if players_sorted else ('?', 0),
        'most_kills': (players_sorted[0].get('name', '?'), players_sorted[0].get('kills', 0)) if players_sorted else ('?', 0),
    }

    fig = plt.figure(figsize=(20, 12), facecolor=COLORS['background'])
    gs = fig.add_gridspec(3, 3, hspace=0.28, wspace=0.28, left=0.04, right=0.96, top=0.95, bottom=0.05)

    ax1 = fig.add_subplot(gs[0, :2], projection='polar')
    create_spider_chart(ax1, players_data, title=f"COMBAT OVERVIEW - {map_name} R{round_num}")

    ax2 = fig.add_subplot(gs[0, 2])
    create_info_box(ax2, match_data)

    ax3 = fig.add_subplot(gs[1, 0])
    create_racing_bars(ax3, players_data, stat='kills', title="TOP FRAGGERS")

    ax4 = fig.add_subplot(gs[1, 1])
    create_heatmap_grid(ax4, players_data)

    ax5 = fig.add_subplot(gs[1, 2])
    create_support_stats(ax5, players_data)

    ax6 = fig.add_subplot(gs[2, :])
    create_time_distribution(ax6, players_data)

    fig.suptitle(f'═══ ET:LEGACY STATISTICS ═══   {map_name.upper()} - ROUND {round_num}', fontsize=22, color=COLORS['primary'], fontweight='bold', family='monospace', y=0.99)
    plt.tight_layout()
    return fig


def test_visualization(stats_file_path, output_path='tools/tmp/retro_round1.png'):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fig = create_round_visualization(stats_file_path)
    fig.savefig(output_path, dpi=150, facecolor=COLORS['background'], bbox_inches='tight')
    plt.close(fig)
    return output_path


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python retro_viz.py <stats_file.txt>')
        sys.exit(1)
    src = sys.argv[1]
    out = 'tools/tmp/retro_round1.png'
    try:
        path = test_visualization(src, out)
        print('Saved visualization to:', path)
    except Exception as e:
        print('Error creating visualization:', e)
        raise
