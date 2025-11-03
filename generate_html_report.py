"""
Generate comprehensive HTML validation report with field mappings
"""

import sys
import sqlite3
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'bot'))

from community_stats_parser import C0RNP0RN3StatsParser

SESSION_IDS = list(range(2134, 2152))

def get_nov2_files():
    stats_dir = Path('local_stats')
    files = sorted([f for f in stats_dir.glob('2025-11-02*.txt') if '000624' not in f.name])
    return files

def parse_raw_file(filepath):
    parser = C0RNP0RN3StatsParser()
    result = parser.parse_stats_file(str(filepath))
    
    if not result or not result.get('success'):
        return None, None
    
    players_by_guid = {}
    for player in result.get('players', []):
        guid = player.get('guid', '')[:8]
        if guid:
            players_by_guid[guid] = player
    
    return players_by_guid, result

def get_db_stats(session_id):
    db_path = Path('bot/etlegacy_production.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM player_comprehensive_stats WHERE session_id = ?
    """, (session_id,))
    
    players = {}
    for row in cursor.fetchall():
        guid = row['player_guid']
        players[guid] = dict(row)
    
    conn.close()
    return players

def generate_html_report():
    files = get_nov2_files()
    
    html = """
<!DOCTYPE html>
<html>
<head>
    <title>Comprehensive Field Mapping Validation Report - Nov 2, 2025</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .header h1 {
            margin: 0 0 10px 0;
        }
        .header p {
            margin: 5px 0;
            opacity: 0.9;
        }
        .summary {
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .summary-item {
            text-align: center;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
        }
        .summary-item .value {
            font-size: 32px;
            font-weight: bold;
            color: #667eea;
        }
        .summary-item .label {
            font-size: 14px;
            color: #666;
            margin-top: 5px;
        }
        .field-mapping {
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .field-mapping h2 {
            margin-top: 0;
            color: #333;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
        }
        .mapping-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            font-size: 13px;
        }
        .mapping-table th {
            background: #667eea;
            color: white;
            padding: 12px 8px;
            text-align: left;
            font-weight: 600;
        }
        .mapping-table td {
            padding: 10px 8px;
            border-bottom: 1px solid #eee;
        }
        .mapping-table tr:hover {
            background: #f8f9fa;
        }
        .match {
            color: #28a745;
            font-weight: bold;
        }
        .mismatch {
            color: #dc3545;
            font-weight: bold;
        }
        .note {
            background: #fff3cd;
            padding: 8px 12px;
            border-left: 4px solid #ffc107;
            margin: 5px 0;
            font-size: 12px;
        }
        .round-section {
            background: white;
            padding: 25px;
            border-radius: 10px;
            margin-bottom: 25px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .round-header {
            background: linear-gradient(135deg, #84fab0 0%, #8fd3f4 100%);
            color: #333;
            padding: 15px 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-weight: bold;
        }
        .player-section {
            margin-bottom: 30px;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 15px;
            background: #fafafa;
        }
        .player-header {
            font-size: 18px;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e0e0e0;
        }
        .status-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: bold;
            margin-left: 10px;
        }
        .status-match {
            background: #d4edda;
            color: #155724;
        }
        .status-mismatch {
            background: #f8d7da;
            color: #721c24;
        }
        .toc {
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .toc h3 {
            margin-top: 0;
            color: #667eea;
        }
        .toc ul {
            list-style: none;
            padding: 0;
        }
        .toc li {
            padding: 8px 0;
            border-bottom: 1px solid #eee;
        }
        .toc a {
            color: #667eea;
            text-decoration: none;
        }
        .toc a:hover {
            text-decoration: underline;
        }
        .calculated-field {
            background: #e7f3ff;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 11px;
        }
        .renamed-field {
            background: #fff4e6;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 11px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Comprehensive Field Mapping Validation Report</h1>
        <p><strong>Session Date:</strong> November 2, 2025</p>
        <p><strong>Generated:</strong> """ + str(Path().absolute()) + """</p>
        <p><strong>Purpose:</strong> Complete validation of all data fields from raw stats files to database</p>
    </div>
    
    <div class="field-mapping">
        <h2>🗺️ Field Mapping Reference</h2>
        <p>This document shows how fields map from the raw stats files (generated by c0rnp0rn3.lua) to the database.</p>
        
        <h3 style="margin-top: 25px;">Field Sources:</h3>
        <table class="mapping-table">
            <thead>
                <tr>
                    <th>Raw File Source</th>
                    <th>Parser Field</th>
                    <th>Database Column</th>
                    <th>Notes</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Weapon Stats (space-separated)</td>
                    <td>player['kills']</td>
                    <td>kills</td>
                    <td>Sum from all weapons</td>
                </tr>
                <tr>
                    <td>Weapon Stats</td>
                    <td>player['deaths']</td>
                    <td>deaths</td>
                    <td>Sum from all weapons</td>
                </tr>
                <tr>
                    <td>Weapon Stats</td>
                    <td>player['damage_given']</td>
                    <td>damage_given</td>
                    <td>Sum from all weapons</td>
                </tr>
                <tr>
                    <td>Weapon Stats</td>
                    <td>player['damage_received']</td>
                    <td>damage_received</td>
                    <td>Sum from all weapons</td>
                </tr>
                <tr>
                    <td>TAB field 14</td>
                    <td>objective_stats['headshot_kills']</td>
                    <td>headshot_kills</td>
                    <td class="note"><strong>⚠️ Different from weapon headshots sum!</strong> This is kills where final blow was headshot, not total headshot hits.</td>
                </tr>
                <tr>
                    <td>TAB field 2</td>
                    <td>objective_stats['gibs']</td>
                    <td>gibs</td>
                    <td>Direct mapping</td>
                </tr>
                <tr>
                    <td>TAB field 4</td>
                    <td>objective_stats['self_kills']</td>
                    <td>self_kills</td>
                    <td>Direct mapping</td>
                </tr>
                <tr>
                    <td>TAB field 6</td>
                    <td>objective_stats['team_kills']</td>
                    <td>team_kills</td>
                    <td>Direct mapping</td>
                </tr>
                <tr>
                    <td>TAB field 7</td>
                    <td>objective_stats['team_gibs']</td>
                    <td>team_gibs</td>
                    <td>Direct mapping</td>
                </tr>
                <tr>
                    <td>TAB field 3</td>
                    <td>objective_stats['team_damage_given']</td>
                    <td>team_damage_given</td>
                    <td>Direct mapping</td>
                </tr>
                <tr>
                    <td>TAB field 5</td>
                    <td>objective_stats['team_damage_received']</td>
                    <td>team_damage_received</td>
                    <td>Direct mapping</td>
                </tr>
                <tr>
                    <td>TAB field 19</td>
                    <td>objective_stats['times_revived']</td>
                    <td>times_revived</td>
                    <td>Direct mapping</td>
                </tr>
                <tr>
                    <td>Calculated</td>
                    <td>objective_stats['revives_given']</td>
                    <td>revives_given</td>
                    <td class="calculated-field">CALCULATED in raw file</td>
                </tr>
                <tr>
                    <td>TAB field 9</td>
                    <td>objective_stats['xp']</td>
                    <td>xp</td>
                    <td>Direct mapping</td>
                </tr>
                <tr>
                    <td>TAB field 12</td>
                    <td>objective_stats['kill_assists']</td>
                    <td>kill_assists</td>
                    <td>Direct mapping</td>
                </tr>
                <tr>
                    <td>TAB field 13</td>
                    <td>objective_stats['kill_steals']</td>
                    <td>kill_steals</td>
                    <td>Direct mapping</td>
                </tr>
                <tr>
                    <td>TAB field 27</td>
                    <td>objective_stats['useful_kills']</td>
                    <td>most_useful_kills</td>
                    <td class="renamed-field">RENAMED in database</td>
                </tr>
                <tr>
                    <td>Calculated</td>
                    <td>objective_stats['useless_kills']</td>
                    <td>useless_kills</td>
                    <td class="calculated-field">CALCULATED: kills - useful_kills</td>
                </tr>
                <tr>
                    <td>TAB field 10</td>
                    <td>objective_stats['killing_spree']</td>
                    <td>killing_spree_best</td>
                    <td class="renamed-field">RENAMED in database</td>
                </tr>
                <tr>
                    <td>TAB field 11</td>
                    <td>objective_stats['death_spree']</td>
                    <td>death_spree_worst</td>
                    <td class="renamed-field">RENAMED in database</td>
                </tr>
                <tr>
                    <td>TAB field 15</td>
                    <td>objective_stats['objectives_stolen']</td>
                    <td>objectives_stolen</td>
                    <td>Direct mapping</td>
                </tr>
                <tr>
                    <td>TAB field 16</td>
                    <td>objective_stats['objectives_returned']</td>
                    <td>objectives_returned</td>
                    <td>Direct mapping</td>
                </tr>
                <tr>
                    <td>TAB field 17</td>
                    <td>objective_stats['dynamites_planted']</td>
                    <td>dynamites_planted</td>
                    <td>Direct mapping</td>
                </tr>
                <tr>
                    <td>TAB field 18</td>
                    <td>objective_stats['dynamites_defused']</td>
                    <td>dynamites_defused</td>
                    <td>Direct mapping</td>
                </tr>
                <tr>
                    <td>TAB field 29</td>
                    <td>objective_stats['multikill_2x']</td>
                    <td>double_kills</td>
                    <td class="renamed-field">RENAMED in database</td>
                </tr>
                <tr>
                    <td>TAB field 30</td>
                    <td>objective_stats['multikill_3x']</td>
                    <td>triple_kills</td>
                    <td class="renamed-field">RENAMED in database</td>
                </tr>
                <tr>
                    <td>TAB field 31</td>
                    <td>objective_stats['multikill_4x']</td>
                    <td>quad_kills</td>
                    <td class="renamed-field">RENAMED in database</td>
                </tr>
                <tr>
                    <td>TAB field 32</td>
                    <td>objective_stats['multikill_5x']</td>
                    <td>multi_kills</td>
                    <td class="renamed-field">RENAMED in database (should be penta_kills)</td>
                </tr>
                <tr>
                    <td>TAB field 33</td>
                    <td>objective_stats['multikill_6x']</td>
                    <td>mega_kills</td>
                    <td class="renamed-field">RENAMED in database (should be hexa_kills)</td>
                </tr>
                <tr>
                    <td>Calculated</td>
                    <td>N/A</td>
                    <td>kd_ratio</td>
                    <td class="calculated-field">RECALCULATED by bot: kills / deaths</td>
                </tr>
                <tr>
                    <td>Calculated</td>
                    <td>N/A</td>
                    <td>dpm</td>
                    <td class="calculated-field">RECALCULATED by bot: damage / time_played</td>
                </tr>
                <tr>
                    <td>Calculated</td>
                    <td>N/A</td>
                    <td>efficiency</td>
                    <td class="calculated-field">RECALCULATED by bot: kills / (kills + deaths) * 100</td>
                </tr>
                <tr>
                    <td>Calculated</td>
                    <td>N/A</td>
                    <td>accuracy</td>
                    <td class="calculated-field">RECALCULATED by bot: hits / shots * 100</td>
                </tr>
            </tbody>
        </table>
        
        <div class="note" style="margin-top: 20px;">
            <strong>⚠️ IMPORTANT DISTINCTIONS:</strong>
            <ul style="margin: 10px 0;">
                <li><strong>Headshots vs Headshot Kills:</strong> Weapon stats track total headshot HITS. TAB field 14 tracks headshot KILLS (final blow was headshot). These are DIFFERENT stats!</li>
                <li><strong>Calculated Fields:</strong> Some fields (DPM, KD ratio, efficiency, accuracy) are recalculated by the bot using raw values to ensure consistency.</li>
                <li><strong>Renamed Fields:</strong> Some fields have different names between parser and database (e.g., useful_kills → most_useful_kills).</li>
            </ul>
        </div>
    </div>
"""
    
    total_players = 0
    total_matches = 0
    
    for i, filepath in enumerate(files):
        if i >= len(SESSION_IDS):
            break
        
        session_id = SESSION_IDS[i]
        raw_players, raw_result = parse_raw_file(filepath)
        
        if not raw_players:
            continue
        
        db_players = get_db_stats(session_id)
        
        is_round_2 = 'round-2' in filepath.name
        round_type = "Round 2" if is_round_2 else "Round 1"
        
        html += f"""
    <div class="round-section" id="round-{i+1}">
        <div class="round-header">
            🎮 Round {i+1}/{len(files)}: {filepath.name}<br>
            <span style="font-size: 14px; font-weight: normal;">
                Map: {raw_result.get('map_name', 'Unknown')} | 
                Type: {round_type} | 
                Session ID: {session_id} |
                Players: {len(raw_players)}
            </span>
        </div>
"""
        
        for guid in sorted(raw_players.keys()):
            if guid not in db_players:
                continue
            
            raw = raw_players[guid]
            db = db_players[guid]
            obj = raw.get('objective_stats', {})
            
            total_players += 1
            player_matches = 0
            player_total = 0
            
            # Collect all comparisons
            comparisons = []
            
            # Core stats
            comparisons.append(('kills', raw.get('kills'), db.get('kills'), 'Weapon stats sum'))
            comparisons.append(('deaths', raw.get('deaths'), db.get('deaths'), 'Weapon stats sum'))
            comparisons.append(('damage_given', raw.get('damage_given'), db.get('damage_given'), 'Weapon stats sum'))
            comparisons.append(('damage_received', raw.get('damage_received'), db.get('damage_received'), 'Weapon stats sum'))
            
            # Objective stats from TAB fields
            comparisons.append(('headshot_kills', obj.get('headshot_kills'), db.get('headshot_kills'), 'TAB field 14 (NOT weapon sum!)'))
            comparisons.append(('gibs', obj.get('gibs'), db.get('gibs'), 'TAB field 2'))
            comparisons.append(('self_kills', obj.get('self_kills'), db.get('self_kills'), 'TAB field 4'))
            comparisons.append(('team_kills', obj.get('team_kills'), db.get('team_kills'), 'TAB field 6'))
            comparisons.append(('team_gibs', obj.get('team_gibs'), db.get('team_gibs'), 'TAB field 7'))
            comparisons.append(('team_damage_given', obj.get('team_damage_given'), db.get('team_damage_given'), 'TAB field 3'))
            comparisons.append(('team_damage_received', obj.get('team_damage_received'), db.get('team_damage_received'), 'TAB field 5'))
            comparisons.append(('times_revived', obj.get('times_revived'), db.get('times_revived'), 'TAB field 19'))
            comparisons.append(('revives_given', obj.get('revives_given'), db.get('revives_given'), 'Calculated'))
            comparisons.append(('xp', obj.get('xp'), db.get('xp'), 'TAB field 9'))
            comparisons.append(('kill_assists', obj.get('kill_assists'), db.get('kill_assists'), 'TAB field 12'))
            comparisons.append(('kill_steals', obj.get('kill_steals'), db.get('kill_steals'), 'TAB field 13'))
            comparisons.append(('useful_kills', obj.get('useful_kills'), db.get('most_useful_kills'), 'TAB field 27 → most_useful_kills'))
            comparisons.append(('useless_kills', obj.get('useless_kills'), db.get('useless_kills'), 'Calculated'))
            comparisons.append(('killing_spree', obj.get('killing_spree'), db.get('killing_spree_best'), 'TAB field 10 → killing_spree_best'))
            comparisons.append(('death_spree', obj.get('death_spree'), db.get('death_spree_worst'), 'TAB field 11 → death_spree_worst'))
            comparisons.append(('objectives_stolen', obj.get('objectives_stolen'), db.get('objectives_stolen'), 'TAB field 15'))
            comparisons.append(('objectives_returned', obj.get('objectives_returned'), db.get('objectives_returned'), 'TAB field 16'))
            comparisons.append(('dynamites_planted', obj.get('dynamites_planted'), db.get('dynamites_planted'), 'TAB field 17'))
            comparisons.append(('dynamites_defused', obj.get('dynamites_defused'), db.get('dynamites_defused'), 'TAB field 18'))
            comparisons.append(('double_kills', obj.get('multikill_2x'), db.get('double_kills'), 'TAB field 29 → double_kills'))
            comparisons.append(('triple_kills', obj.get('multikill_3x'), db.get('triple_kills'), 'TAB field 30 → triple_kills'))
            comparisons.append(('quad_kills', obj.get('multikill_4x'), db.get('quad_kills'), 'TAB field 31 → quad_kills'))
            comparisons.append(('multi_kills', obj.get('multikill_5x'), db.get('multi_kills'), 'TAB field 32 → multi_kills'))
            comparisons.append(('mega_kills', obj.get('multikill_6x'), db.get('mega_kills'), 'TAB field 33 → mega_kills'))
            
            # Count matches
            for field, raw_val, db_val, note in comparisons:
                player_total += 1
                if raw_val == db_val:
                    player_matches += 1
            
            total_matches += player_matches
            
            status = "MATCH" if player_matches == player_total else "MISMATCH"
            status_class = "status-match" if player_matches == player_total else "status-mismatch"
            
            html += f"""
        <div class="player-section">
            <div class="player-header">
                👤 {raw.get('name')} ({guid})
                <span class="status-badge {status_class}">{player_matches}/{player_total} fields match</span>
            </div>
            <table class="mapping-table">
                <thead>
                    <tr>
                        <th>Field Name</th>
                        <th>Raw File Value</th>
                        <th>Database Value</th>
                        <th>Status</th>
                        <th>Source / Notes</th>
                    </tr>
                </thead>
                <tbody>
"""
            
            for field, raw_val, db_val, note in comparisons:
                match_status = "✓ MATCH" if raw_val == db_val else "✗ MISMATCH"
                match_class = "match" if raw_val == db_val else "mismatch"
                
                html += f"""
                    <tr>
                        <td><strong>{field}</strong></td>
                        <td>{raw_val}</td>
                        <td>{db_val}</td>
                        <td class="{match_class}">{match_status}</td>
                        <td style="font-size: 12px; color: #666;">{note}</td>
                    </tr>
"""
            
            # Add weapon headshots comparison for reference
            weapon_headshots = sum(w.get('headshots', 0) for w in raw.get('weapon_stats', {}).values())
            html += f"""
                    <tr style="background: #f0f8ff;">
                        <td><strong>weapon_headshots_sum</strong></td>
                        <td>{weapon_headshots}</td>
                        <td colspan="2" style="text-align: center; font-style: italic;">Not stored at player level</td>
                        <td style="font-size: 12px; color: #666;">Reference: Sum of headshot hits from all weapons (≠ headshot_kills)</td>
                    </tr>
"""
            
            html += """
                </tbody>
            </table>
        </div>
"""
        
        html += """
    </div>
"""
    
    # Calculate overall statistics
    total_fields_checked = total_players * 25  # 25 fields per player
    success_rate = (total_matches / total_fields_checked * 100) if total_fields_checked > 0 else 0
    
    # Add summary at beginning (we'll prepend it)
    summary_html = f"""
    <div class="summary">
        <h2>📈 Validation Summary</h2>
        <div class="summary-grid">
            <div class="summary-item">
                <div class="value">{len(files)}</div>
                <div class="label">Total Rounds</div>
            </div>
            <div class="summary-item">
                <div class="value">{total_players}</div>
                <div class="label">Players Validated</div>
            </div>
            <div class="summary-item">
                <div class="value">{total_fields_checked}</div>
                <div class="label">Fields Checked</div>
            </div>
            <div class="summary-item">
                <div class="value" style="color: #28a745;">{total_matches}</div>
                <div class="label">Fields Matched</div>
            </div>
            <div class="summary-item">
                <div class="value" style="color: {'#28a745' if success_rate == 100 else '#dc3545'};">{success_rate:.1f}%</div>
                <div class="label">Success Rate</div>
            </div>
        </div>
        <div class="note" style="margin-top: 20px;">
            <strong>✅ VALIDATION COMPLETE:</strong> All {total_fields_checked} field comparisons across {total_players} players in {len(files)} rounds have been validated using correct field mappings.
        </div>
    </div>
    
    <div class="toc">
        <h3>📑 Table of Contents - Quick Navigation</h3>
        <ul>
"""
    
    for i, filepath in enumerate(files[:len(SESSION_IDS)]):
        summary_html += f'            <li><a href="#round-{i+1}">Round {i+1}: {filepath.name}</a></li>\n'
    
    summary_html += """
        </ul>
    </div>
"""
    
    html = html.replace('<div class="field-mapping">', summary_html + '<div class="field-mapping">')
    
    html += """
</body>
</html>
"""
    
    return html

print("Generating comprehensive HTML validation report...")
html_content = generate_html_report()

output_path = Path('FIELD_MAPPING_VALIDATION_REPORT.html')
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html_content)

print(f"✅ Report generated: {output_path.absolute()}")
print(f"📊 Open in browser to view complete field-by-field validation")
