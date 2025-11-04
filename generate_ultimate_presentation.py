#!/usr/bin/env python3
"""
ULTIMATE INTERACTIVE PRESENTATION
ALL data, ALL players, ALL fields, fully interactive with pages and drill-down
"""

import sqlite3
from datetime import datetime
import glob
import json

FIELD_MAPPING = {
    'damage_given': {'db': 'damage_given', 'type': 'direct'},
    'damage_received': {'db': 'damage_received', 'type': 'direct'},
    'team_damage_given': {'db': 'team_damage_given', 'type': 'direct'},
    'team_damage_received': {'db': 'team_damage_received', 'type': 'direct'},
    'gibs': {'db': 'gibs', 'type': 'direct'},
    'self_kills': {'db': 'self_kills', 'type': 'direct'},
    'team_kills': {'db': 'team_kills', 'type': 'direct'},
    'team_gibs': {'db': 'team_gibs', 'type': 'direct'},
    'xp': {'db': 'xp', 'type': 'direct'},
    'kill_assists': {'db': 'kill_assists', 'type': 'direct'},
    'kill_steals': {'db': 'kill_steals', 'type': 'direct'},
    'headshot_kills': {'db': 'headshot_kills', 'type': 'direct'},
    'objectives_stolen': {'db': 'objectives_stolen', 'type': 'direct'},
    'objectives_returned': {'db': 'objectives_returned', 'type': 'direct'},
    'dynamites_planted': {'db': 'dynamites_planted', 'type': 'direct'},
    'dynamites_defused': {'db': 'dynamites_defused', 'type': 'direct'},
    'times_revived': {'db': 'times_revived', 'type': 'direct'},
    'bullets_fired': {'db': 'bullets_fired', 'type': 'direct'},
    'time_played_minutes': {'db': 'time_played_minutes', 'type': 'direct'},
    'tank_meatshield': {'db': 'tank_meatshield', 'type': 'direct'},
    'time_dead_minutes': {'db': 'time_dead_minutes', 'type': 'direct'},
    'useless_kills': {'db': 'useless_kills', 'type': 'direct'},
    'revives_given': {'db': 'revives_given', 'type': 'direct'},
    'denied_playtime': {'db': 'denied_playtime', 'type': 'direct'},
    'killing_spree': {'db': 'killing_spree_best', 'type': 'renamed',
                      'note': 'Stored as killing_spree_best in DB'},
    'death_spree': {'db': 'death_spree_worst', 'type': 'renamed',
                    'note': 'Stored as death_spree_worst in DB'},
    'useful_kills': {'db': 'most_useful_kills', 'type': 'renamed',
                     'note': 'Stored as most_useful_kills in DB'},
    'multikill_2x': {'db': 'double_kills', 'type': 'renamed',
                     'note': 'Stored as double_kills in DB'},
    'multikill_3x': {'db': 'triple_kills', 'type': 'renamed',
                     'note': 'Stored as triple_kills in DB'},
    'multikill_4x': {'db': 'quad_kills', 'type': 'renamed',
                     'note': 'Stored as quad_kills in DB'},
    'multikill_5x': {'db': 'multi_kills', 'type': 'renamed',
                     'note': 'Stored as multi_kills in DB'},
    'multikill_6x': {'db': 'mega_kills', 'type': 'renamed',
                     'note': 'Stored as mega_kills in DB'},
    'repairs_constructions': {'db': 'constructions', 'type': 'renamed',
                              'note': 'Stored as constructions in DB'},
    'dpm': {'db': 'dpm', 'type': 'calculated',
            'note': 'Recalculated by DB: (damage*60)/time_seconds'},
    'kd_ratio': {'db': 'kd_ratio', 'type': 'calculated',
                 'note': 'Recalculated by DB: kills/deaths'},
    'time_dead_ratio': {'db': 'time_dead_ratio', 'type': 'calculated',
                        'note': 'May differ due to rounding'},
}


def parse_player_line(line):
    """Parse player line with all stats."""
    parts = line.split('\\')
    if len(parts) < 5:
        return None
    
    guid, name, _, team = parts[:4]
    stats_section = parts[4]
    
    if '\t' not in stats_section:
        return None
    
    _, extended = stats_section.split('\t', 1)
    fields = extended.split('\t')
    
    if len(fields) < 38:
        return None
    
    return {
        'guid': guid,
        'name': name,
        'team': team,
        'stats': {
            'damage_given': int(fields[0]),
            'damage_received': int(fields[1]),
            'team_damage_given': int(fields[2]),
            'team_damage_received': int(fields[3]),
            'gibs': int(fields[4]),
            'self_kills': int(fields[5]),
            'team_kills': int(fields[6]),
            'team_gibs': int(fields[7]),
            'time_played_percent': float(fields[8]),
            'xp': int(fields[9]),
            'killing_spree': int(fields[10]),
            'death_spree': int(fields[11]),
            'kill_assists': int(fields[12]),
            'kill_steals': int(fields[13]),
            'headshot_kills': int(fields[14]),
            'objectives_stolen': int(fields[15]),
            'objectives_returned': int(fields[16]),
            'dynamites_planted': int(fields[17]),
            'dynamites_defused': int(fields[18]),
            'times_revived': int(fields[19]),
            'bullets_fired': int(fields[20]),
            'dpm': float(fields[21]),
            'time_played_minutes': float(fields[22]),
            'tank_meatshield': float(fields[23]),
            'time_dead_ratio': float(fields[24]),
            'time_dead_minutes': float(fields[25]),
            'kd_ratio': float(fields[26]),
            'useful_kills': int(fields[27]),
            'denied_playtime': int(fields[28]),
            'multikill_2x': int(fields[29]),
            'multikill_3x': int(fields[30]),
            'multikill_4x': int(fields[31]),
            'multikill_5x': int(fields[32]),
            'multikill_6x': int(fields[33]),
            'useless_kills': int(fields[34]),
            'full_selfkills': int(fields[35]),
            'repairs_constructions': int(fields[36]),
            'revives_given': int(fields[37]),
        }
    }


def collect_all_data():
    """Collect ALL data from files and database."""
    conn = sqlite3.connect('bot/etlegacy_production.db')
    c = conn.cursor()
    
    # Get rounds
    c.execute("""
        SELECT id, round_date, map_name, round_number, winner_team,
               original_time_limit, time_to_beat, completion_time
        FROM rounds
        WHERE round_date LIKE '2025-10-28%'
           OR round_date LIKE '2025-10-30%'
        ORDER BY round_date, round_number
    """)
    sessions = c.fetchall()
    
    all_data = []
    
    for row in sessions:
        sid, date, map_name, rnd, winner, tl, tb, tc = row
        
        print(f"   {date} {map_name} R{rnd}")
        
        # Get DB stats
        c.execute("PRAGMA table_info(player_comprehensive_stats)")
        cols = [r[1] for r in c.fetchall()]
        
        c.execute(
            f"SELECT {', '.join(cols)} FROM player_comprehensive_stats "
            f"WHERE round_id = ?", (sid,)
        )
        db_rows = [dict(zip(cols, r)) for r in c.fetchall()]
        
        # Get file stats
        pattern = f"local_stats/{date}-{map_name}-round-{rnd}.txt"
        files = glob.glob(pattern)
        
        if not files:
            continue
        
        with open(files[0], 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        file_players = {}
        for line in lines[1:]:
            p = parse_player_line(line.strip())
            if p:
                file_players[p['guid']] = p
        
        # Match and compare
        session_data = {
            'id': sid,
            'date': date,
            'map': map_name,
            'round': rnd,
            'winner': winner,
            'time_limit': tl,
            'time_beat': tb,
            'time_complete': tc,
            'players': []
        }
        
        for db_p in db_rows:
            guid = db_p['player_guid']
            file_p = file_players.get(guid)
            
            if not file_p:
                continue
            
            player_comp = {
                'guid': guid,
                'name': db_p['player_name'],
                'team': db_p['team'],
                'fields': []
            }
            
            for raw_field, mapping in FIELD_MAPPING.items():
                db_field = mapping['db']
                file_val = file_p['stats'].get(raw_field)
                db_val = db_p.get(db_field)
                
                if file_val is not None and db_val is not None:
                    match = abs(float(file_val) - float(db_val)) < 0.1
                    
                    player_comp['fields'].append({
                        'raw': raw_field,
                        'db': db_field,
                        'file': file_val,
                        'database': db_val,
                        'match': match,
                        'type': mapping['type'],
                        'note': mapping.get('note', '')
                    })
            
            session_data['players'].append(player_comp)
        
        all_data.append(session_data)
    
    conn.close()
    return all_data


print("="*80)
print("ULTIMATE INTERACTIVE PRESENTATION GENERATOR")
print("="*80)
print("\nCollecting ALL data...\n")

all_data = collect_all_data()

print(f"\nCollected {len(all_data)} sessions")
print(f"Total players: {sum(len(s['players']) for s in all_data)}")

# Now generate the HTML
print("\nGenerating HTML presentation...")

html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Complete Field Mapping - Interactive Analysis</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: #1a1a2e;
    color: #eee;
}}

/* Navigation */
.nav {{
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    background: rgba(30, 30, 46, 0.98);
    backdrop-filter: blur(10px);
    padding: 15px 30px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 2px 20px rgba(0,0,0,0.5);
    z-index: 1000;
    border-bottom: 2px solid #4fc3f7;
}}

.nav-title {{
    font-size: 20px;
    font-weight: bold;
    color: #4fc3f7;
}}

.nav-buttons {{
    display: flex;
    gap: 10px;
}}

.btn {{
    background: #3a3a4a;
    color: #e0e0e0;
    border: none;
    padding: 10px 20px;
    border-radius: 5px;
    cursor: pointer;
    font-size: 14px;
    transition: all 0.3s ease;
}}

.btn:hover {{
    background: #4fc3f7;
    color: #1e1e2e;
    transform: translateY(-2px);
}}

.btn.active {{
    background: #4fc3f7;
    color: #1e1e2e;
}}

/* Pages */
.page {{
    display: none;
    padding: 100px 40px 40px;
    max-width: 1600px;
    margin: 0 auto;
}}

.page.active {{
    display: block;
    animation: fadeIn 0.3s ease-in;
}}

@keyframes fadeIn {{
    from {{ opacity: 0; transform: translateY(10px); }}
    to {{ opacity: 1; transform: translateY(0); }}
}}

/* Cards */
.card {{
    background: #2d2d3d;
    border-radius: 8px;
    padding: 25px;
    margin: 20px 0;
    box-shadow: 0 4px 16px rgba(0,0,0,0.3);
    border: 1px solid #3a3a4a;
}}

.card-title {{
    font-size: 24px;
    color: #4fc3f7;
    margin-bottom: 15px;
    border-bottom: 2px solid #4fc3f7;
    padding-bottom: 10px;
}}

/* Stats Grid */
.stats-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 20px;
    margin: 20px 0;
}}

.stat-box {{
    background: linear-gradient(135deg, #3a3a4a 0%, #2d2d3d 100%);
    padding: 30px;
    border-radius: 8px;
    text-align: center;
    transition: transform 0.3s ease;
}}

.stat-box:hover {{
    transform: translateY(-5px);
}}

.stat-number {{
    font-size: 42px;
    font-weight: bold;
    color: #4fc3f7;
    margin-bottom: 10px;
}}

.stat-label {{
    font-size: 14px;
    color: #aaa;
    text-transform: uppercase;
    letter-spacing: 1px;
}}

/* Session Cards */
.session {{
    background: #353545;
    border-radius: 8px;
    padding: 20px;
    margin: 15px 0;
    cursor: pointer;
    border-left: 4px solid #4fc3f7;
    transition: all 0.3s ease;
}}

.session:hover {{
    background: #3a3a4a;
    transform: translateX(5px);
}}

.session-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
}}

.session-title {{
    font-size: 18px;
    color: #4fc3f7;
    font-weight: bold;
}}

.session-meta {{
    font-size: 13px;
    color: #999;
}}

.session-details {{
    max-height: 0;
    overflow: hidden;
    transition: max-height 0.5s ease;
}}

.session.expanded .session-details {{
    max-height: 10000px;
    margin-top: 20px;
}}

.session .arrow {{
    transition: transform 0.3s ease;
}}

.session.expanded .arrow {{
    transform: rotate(180deg);
}}

/* Player Cards */
.player {{
    background: #2d2d2d;
    border-radius: 6px;
    padding: 15px;
    margin: 10px 0;
    border-left: 3px solid #666;
}}

.player-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    cursor: pointer;
    padding: 10px;
}}

.player-header:hover {{
    background: #353545;
}}

.player-name {{
    font-size: 16px;
    font-weight: bold;
    color: #fff;
}}

.player-guid {{
    font-size: 11px;
    color: #666;
    font-family: 'Courier New', monospace;
}}

.player-details {{
    max-height: 0;
    overflow: hidden;
    transition: max-height 0.5s ease;
}}

.player.expanded .player-details {{
    max-height: 3000px;
    margin-top: 15px;
}}

/* Field Comparison Table */
.field-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
    margin-top: 10px;
}}

.field-table th {{
    background: #3a3a4a;
    color: #4fc3f7;
    padding: 10px;
    text-align: left;
    font-weight: 600;
    position: sticky;
    top: 70px;
}}

.field-table td {{
    padding: 8px 10px;
    border-bottom: 1px solid #3a3a3a;
}}

.field-table tr:hover {{
    background: #353545;
}}

.field-name {{
    font-family: 'Courier New', monospace;
    color: #4fc3f7;
}}

.value {{
    font-family: 'Courier New', monospace;
    font-size: 13px;
    font-weight: bold;
}}

.match {{ color: #4caf50; }}
.mismatch {{ color: #f44336; }}

.badge {{
    display: inline-block;
    padding: 3px 8px;
    border-radius: 10px;
    font-size: 10px;
    font-weight: bold;
    text-transform: uppercase;
}}

.badge-direct {{ background: #4caf50; color: white; }}
.badge-renamed {{ background: #ff9800; color: white; }}
.badge-calculated {{ background: #2196f3; color: white; }}

/* Filter Bar */
.filter-bar {{
    background: #3a3a4a;
    padding: 20px;
    border-radius: 8px;
    margin-bottom: 20px;
    display: flex;
    gap: 15px;
}}

.filter-input {{
    flex: 1;
    padding: 10px 15px;
    background: #2d2d2d;
    border: 1px solid #555;
    border-radius: 5px;
    color: #eee;
    font-size: 14px;
}}

.filter-input:focus {{
    outline: none;
    border-color: #4fc3f7;
}}

/* Info Box */
.info {{
    background: #3a3a4a;
    border-left: 4px solid #4fc3f7;
    padding: 15px 20px;
    margin: 15px 0;
    border-radius: 4px;
}}

.info.warning {{ border-left-color: #ff9800; }}
.info.success {{ border-left-color: #4caf50; }}

</style>
</head>
<body>

<!-- Navigation -->
<div class="nav">
    <div class="nav-title">🔍 Complete Field Mapping Analysis</div>
    <div class="nav-buttons">
        <button class="btn active" onclick="showPage('overview')">
            Overview
        </button>
        <button class="btn" onclick="showPage('rounds')">
            All Sessions ({len(all_data)})
        </button>
        <button class="btn" onclick="showPage('mapping')">
            Field Mapping
        </button>
        <button class="btn" onclick="showPage('mismatches')">
            Mismatches
        </button>
    </div>
</div>

<!-- PAGE: OVERVIEW -->
<div class="page active" id="page-overview">
    <div class="card">
        <h1 style="font-size: 36px; color: #4fc3f7; text-align: center;">
            Complete Field Mapping Analysis
        </h1>
        <p style="text-align: center; color: #aaa; font-size: 16px; margin: 10px 0;">
            October 28 & 30, 2025 • All Players • All Rounds • All Maps
        </p>
        <p style="text-align: center; color: #666; font-size: 13px;">
            Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </p>
    </div>
    
    <div class="card">
        <div class="card-title">📊 Summary Statistics</div>
        <div class="stats-grid">
"""

# Calculate stats
total_rounds = len(all_data)
total_players = sum(len(s['players']) for s in all_data)
total_comparisons = sum(
    sum(len(p['fields']) for p in s['players'])
    for s in all_data
)
total_matches = sum(
    sum(sum(1 for f in p['fields'] if f['match']) for p in s['players'])
    for s in all_data
)
total_mismatches = total_comparisons - total_matches
accuracy = (total_matches / total_comparisons * 100) if total_comparisons else 0

html += f"""
            <div class="stat-box">
                <div class="stat-number">{total_rounds}</div>
                <div class="stat-label">Sessions Analyzed</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{total_players}</div>
                <div class="stat-label">Players Verified</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{total_comparisons:,}</div>
                <div class="stat-label">Field Comparisons</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{accuracy:.1f}%</div>
                <div class="stat-label">Accuracy Rate</div>
            </div>
            <div class="stat-box">
                <div class="stat-number" style="color: #4caf50;">
                    {total_matches:,}
                </div>
                <div class="stat-label">Perfect Matches</div>
            </div>
            <div class="stat-box">
                <div class="stat-number" style="color: #f44336;">
                    {total_mismatches}
                </div>
                <div class="stat-label">Mismatches</div>
            </div>
        </div>
    </div>
    
    <div class="card">
        <div class="card-title">ℹ️ About This Analysis</div>
        <div class="info success">
            <strong>What is this?</strong><br>
            Complete verification of all stat file data vs database storage for
            October 28 & 30, 2025. Every player, every field, every round.
        </div>
        <div class="info warning">
            <strong>Understanding Mismatches:</strong><br>
            Not all "mismatches" are errors! Some fields are:
            <ul style="margin: 10px 0 0 20px; line-height: 1.8;">
                <li><strong>Renamed</strong> - Stored under different column names (by design)</li>
                <li><strong>Recalculated</strong> - DB recalculates using more precise formula</li>
                <li><strong>Rounded</strong> - Minor floating-point differences</li>
            </ul>
        </div>
    </div>
</div>

<!-- PAGE: ALL SESSIONS -->
<div class="page" id="page-sessions">
    <div class="card">
        <div class="card-title">🎮 All Sessions - Oct 28 & 30</div>
        <div class="filter-bar">
            <input type="text" class="filter-input" id="sessionFilter"
                   placeholder="Filter by map, date, or player name..."
                   onkeyup="filterSessions()">
        </div>
        <div id="sessionList">
"""

# Generate session cards with ALL data
for s in all_data:
    perfect = sum(
        1 for p in s['players']
        if all(f['match'] for f in p['fields'])
    )
    total_p = len(s['players'])
    
    html += f"""
        <div class="session" onclick="this.classList.toggle('expanded')">
            <div class="session-header">
                <div>
                    <div class="session-title">
                        {s['map']} - Round {s['round']}
                    </div>
                    <div class="session-meta">
                        {s['date']} | Winner: Team {s['winner']} |
                        Players: {total_p} | Perfect: {perfect}/{total_p}
                    </div>
                </div>
                <span class="arrow">▼</span>
            </div>
            <div class="session-details">
                <div class="info">
                    <strong>Time Information:</strong><br>
                    Original Limit: {s['time_limit'] or 'N/A'} |
                    Time to Beat: {s['time_beat'] or 'N/A'} |
                    Completion: {s['time_complete'] or 'N/A'}
                </div>
    """
    
    # Add all players
    for p in s['players']:
        matches = sum(1 for f in p['fields'] if f['match'])
        mismatches = len(p['fields']) - matches
        
        html += f"""
                <div class="player" onclick="event.stopPropagation(); 
                            this.classList.toggle('expanded')">
                    <div class="player-header">
                        <div>
                            <div class="player-name">{p['name']}</div>
                            <div class="player-guid">{p['guid']}</div>
                        </div>
                        <div style="text-align: right;">
                            <div style="font-size: 18px;">
                                {'✅' if mismatches == 0 else f'⚠️ {mismatches}'}
                            </div>
                            <div style="font-size: 11px; color: #aaa;">
                                {matches}/{len(p['fields'])} match
                            </div>
                        </div>
                    </div>
                    <div class="player-details">
                        <table class="field-table">
                            <thead>
                                <tr>
                                    <th>Raw Field</th>
                                    <th>DB Field</th>
                                    <th>File Value</th>
                                    <th>DB Value</th>
                                    <th>Status</th>
                                    <th>Type</th>
                                </tr>
                            </thead>
                            <tbody>
        """
        
        # Add ALL field comparisons
        for f in p['fields']:
            status = '✅' if f['match'] else '❌'
            val_class = 'match' if f['match'] else 'mismatch'
            badge_class = f"badge-{f['type']}"
            
            html += f"""
                                <tr>
                                    <td class="field-name">{f['raw']}</td>
                                    <td class="field-name">{f['db']}</td>
                                    <td class="value {val_class}">
                                        {f['file']}
                                    </td>
                                    <td class="value {val_class}">
                                        {f['database']}
                                    </td>
                                    <td style="text-align: center; font-size: 18px;">
                                        {status}
                                    </td>
                                    <td>
                                        <span class="badge {badge_class}">
                                            {f['type']}
                                        </span>
                                        {f'<br><small style="color: #888;">{f["note"]}</small>' if f['note'] else ''}
                                    </td>
                                </tr>
            """
        
        html += """
                            </tbody>
                        </table>
                    </div>
                </div>
        """
    
    html += """
            </div>
        </div>
    """

html += """
        </div>
    </div>
</div>

<!-- PAGE: FIELD MAPPING -->
<div class="page" id="page-mapping">
    <div class="card">
        <div class="card-title">📋 Field Mapping Reference</div>
        <div class="info">
            <strong>Permanent Documentation</strong><br>
            This table shows how each raw file field maps to database columns.
        </div>
        <table class="field-table">
            <thead>
                <tr>
                    <th>Raw File Field</th>
                    <th>Database Column</th>
                    <th>Type</th>
                    <th>Notes</th>
                </tr>
            </thead>
            <tbody>
"""

for raw, mapping in sorted(FIELD_MAPPING.items()):
    badge_class = f"badge-{mapping['type']}"
    note = mapping.get('note', 'Direct 1:1 mapping')
    
    html += f"""
                <tr>
                    <td class="field-name">{raw}</td>
                    <td class="field-name">{mapping['db']}</td>
                    <td><span class="badge {badge_class}">{mapping['type']}</span></td>
                    <td style="color: #aaa; font-size: 12px;">{note}</td>
                </tr>
    """

html += """
            </tbody>
        </table>
    </div>
</div>

<!-- PAGE: MISMATCHES -->
<div class="page" id="page-mismatches">
    <div class="card">
        <div class="card-title">⚠️ All Mismatches</div>
        <div class="info warning">
            <strong>Remember:</strong> Most mismatches are intentional (renamed fields
            or recalculated values). This page lists ALL non-matching comparisons for review.
        </div>
        <table class="field-table">
            <thead>
                <tr>
                    <th>Session</th>
                    <th>Player</th>
                    <th>Field</th>
                    <th>File Value</th>
                    <th>DB Value</th>
                    <th>Type</th>
                </tr>
            </thead>
            <tbody>
"""

# Collect all mismatches
for s in all_data:
    for p in s['players']:
        for f in p['fields']:
            if not f['match']:
                html += f"""
                <tr>
                    <td>{s['date']} {s['map']} R{s['round']}</td>
                    <td>{p['name']}</td>
                    <td class="field-name">{f['raw']} → {f['db']}</td>
                    <td class="value mismatch">{f['file']}</td>
                    <td class="value mismatch">{f['database']}</td>
                    <td><span class="badge badge-{f['type']}">{f['type']}</span></td>
                </tr>
                """

html += """
            </tbody>
        </table>
    </div>
</div>

<script>
function showPage(pageId) {
    // Hide all pages
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    // Show selected page
    document.getElementById('page-' + pageId).classList.add('active');
    // Update nav buttons
    document.querySelectorAll('.nav-buttons .btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
}

function filterSessions() {
    const filter = document.getElementById('sessionFilter').value.toLowerCase();
    const sessions = document.querySelectorAll('.session');
    
    sessions.forEach(s => {
        const text = s.textContent.toLowerCase();
        s.style.display = text.includes(filter) ? 'block' : 'none';
    });
}
</script>

</body>
</html>
"""

# Save the HTML
with open('interactive_field_mapping.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("\n✅ Complete!")
print(f"   Total HTML size: {len(html):,} bytes")
print(f"\n📄 Open: interactive_field_mapping.html")
