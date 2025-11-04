#!/usr/bin/env python3
"""
Generate comprehensive machine-readable analysis log.
Outputs detailed JSON/text log for automated analysis.
"""

import sqlite3
import json
from datetime import datetime

def parse_player_extended_stats(line):
    """Parse all extended stats from a player line."""
    parts = line.split('\\')
    if len(parts) < 5:
        return None
    
    guid = parts[0]
    name = parts[1]
    team_start = parts[2]
    team_end = parts[3]
    stats_section = parts[4]
    
    if '\t' in stats_section:
        weapon_section, extended_section = stats_section.split('\t', 1)
        weapon_parts = weapon_section.split()
        tab_fields = extended_section.split('\t')
    else:
        weapon_parts = stats_section.split()
        tab_fields = []
    
    extended = {}
    if len(tab_fields) >= 38:
        extended = {
            'damage_given': int(tab_fields[0]),
            'damage_received': int(tab_fields[1]),
            'team_damage_given': int(tab_fields[2]),
            'team_damage_received': int(tab_fields[3]),
            'gibs': int(tab_fields[4]),
            'self_kills': int(tab_fields[5]),
            'team_kills': int(tab_fields[6]),
            'team_gibs': int(tab_fields[7]),
            'time_played_percent': float(tab_fields[8]),
            'xp': int(tab_fields[9]),
            'killing_spree': int(tab_fields[10]),
            'death_spree': int(tab_fields[11]),
            'kill_assists': int(tab_fields[12]),
            'kill_steals': int(tab_fields[13]),
            'headshot_kills': int(tab_fields[14]),
            'objectives_stolen': int(tab_fields[15]),
            'objectives_returned': int(tab_fields[16]),
            'dynamites_planted': int(tab_fields[17]),
            'dynamites_defused': int(tab_fields[18]),
            'times_revived': int(tab_fields[19]),
            'bullets_fired': int(tab_fields[20]),
            'dpm': float(tab_fields[21]),
            'time_played_minutes': float(tab_fields[22]),
            'tank_meatshield': float(tab_fields[23]),
            'time_dead_ratio': float(tab_fields[24]),
            'time_dead_minutes': float(tab_fields[25]),
            'kd_ratio': float(tab_fields[26]),
            'useful_kills': int(tab_fields[27]),
            'denied_playtime': int(tab_fields[28]),
            'multikill_2x': int(tab_fields[29]),
            'multikill_3x': int(tab_fields[30]),
            'multikill_4x': int(tab_fields[31]),
            'multikill_5x': int(tab_fields[32]),
            'multikill_6x': int(tab_fields[33]),
            'useless_kills': int(tab_fields[34]),
            'full_selfkills': int(tab_fields[35]),
            'repairs_constructions': int(tab_fields[36]),
            'revives_given': int(tab_fields[37]),
        }
    
    return {
        'guid': guid,
        'name': name,
        'team_start': team_start,
        'team_end': team_end,
        'extended': extended,
        'tab_fields_count': len(tab_fields),
    }

def get_db_player_stats(round_id, guid):
    """Get all player stats from database."""
    conn = sqlite3.connect('bot/etlegacy_production.db')
    c = conn.cursor()
    
    c.execute("PRAGMA table_info(player_comprehensive_stats)")
    columns = [row[1] for row in c.fetchall()]
    
    query = f"SELECT {', '.join(columns)} FROM player_comprehensive_stats WHERE round_id = ? AND player_guid = ?"
    c.execute(query, (round_id, guid))
    
    row = c.fetchone()
    conn.close()
    
    if not row:
        return None
    
    return dict(zip(columns, row))

def generate_analysis_log():
    """Generate comprehensive analysis log."""
    
    # Parse files
    with open('local_stats/2025-10-28-212120-etl_adlernest-round-1.txt', 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    r1_line = [line.strip() for line in lines if '7B84BE88' in line and 'endekk' in line][0]
    r1_data = parse_player_extended_stats(r1_line)
    
    with open('local_stats/2025-10-28-212654-etl_adlernest-round-2.txt', 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    r2_line = [line.strip() for line in lines if '7B84BE88' in line and 'endekk' in line][0]
    r2_data = parse_player_extended_stats(r2_line)
    
    # Get database stats
    r1_db = get_db_player_stats(3404, '7B84BE88')
    r2_db = get_db_player_stats(3405, '7B84BE88')
    
    # Build comprehensive analysis
    analysis = {
        'metadata': {
            'generated_at': datetime.now().isoformat(),
            'player': 'endekk',
            'guid': '7B84BE88',
            'map': 'etl_adlernest',
            'date': '2025-10-28',
            'rounds': {
                'r1': 3404,
                'r2': 3405
            }
        },
        'field_analysis': [],
        'summary': {
            'total_fields': 0,
            'perfect_matches': 0,
            'mismatches': 0,
            'missing_in_db': 0,
            'r1_accuracy': 0.0,
            'r2_accuracy': 0.0
        },
        'critical_findings': [],
        'recommendations': []
    }
    
    # Analyze each field
    for field_name in sorted(r1_data['extended'].keys()):
        r1_file = r1_data['extended'][field_name]
        r2_file = r2_data['extended'][field_name]
        
        if isinstance(r1_file, (int, float)):
            r2_calc = max(0, r2_file - r1_file)
        else:
            r2_calc = None
        
        r1_db_val = r1_db.get(field_name)
        r2_db_val = r2_db.get(field_name)
        
        # Determine match status
        r1_match = False
        r2_match = False
        status = 'unknown'
        
        if r1_db_val is None or r2_db_val is None:
            status = 'missing_in_db'
            analysis['summary']['missing_in_db'] += 1
        elif isinstance(r1_file, (int, float)) and isinstance(r1_db_val, (int, float)):
            r1_match = abs(float(r1_file) - float(r1_db_val)) < 0.1
            if r2_calc is not None and isinstance(r2_db_val, (int, float)):
                r2_match = abs(float(r2_db_val) - float(r2_calc)) < 0.1
                if r1_match and r2_match:
                    status = 'perfect'
                    analysis['summary']['perfect_matches'] += 1
                else:
                    status = 'mismatch'
                    analysis['summary']['mismatches'] += 1
                    # Flag critical mismatches
                    if field_name in ['damage_given', 'damage_received', 'kills', 'deaths']:
                        analysis['critical_findings'].append({
                            'field': field_name,
                            'issue': 'Core stat mismatch',
                            'r1_expected': r1_file,
                            'r1_actual': r1_db_val,
                            'r2_expected': r2_calc,
                            'r2_actual': r2_db_val
                        })
        
        analysis['summary']['total_fields'] += 1
        
        field_info = {
            'field_name': field_name,
            'r1_file': r1_file,
            'r2_file_cumulative': r2_file,
            'r2_calculated_differential': r2_calc,
            'r1_database': r1_db_val,
            'r2_database': r2_db_val,
            'r1_match': r1_match,
            'r2_match': r2_match,
            'status': status,
            'variance': {
                'r1': abs(float(r1_file) - float(r1_db_val)) if r1_db_val and isinstance(r1_file, (int, float)) else None,
                'r2': abs(float(r2_calc) - float(r2_db_val)) if r2_db_val and r2_calc and isinstance(r2_db_val, (int, float)) else None
            }
        }
        
        analysis['field_analysis'].append(field_info)
    
    # Calculate accuracy
    if analysis['summary']['total_fields'] > 0:
        total_checked = analysis['summary']['total_fields'] - analysis['summary']['missing_in_db']
        if total_checked > 0:
            analysis['summary']['r1_accuracy'] = (analysis['summary']['perfect_matches'] / total_checked) * 100
            analysis['summary']['r2_accuracy'] = (analysis['summary']['perfect_matches'] / total_checked) * 100
    
    # Add recommendations
    if analysis['summary']['mismatches'] > 0:
        analysis['recommendations'].append({
            'priority': 'high',
            'issue': f"{analysis['summary']['mismatches']} field mismatches detected",
            'action': 'Review differential calculation logic in calculate_round_2_differential()'
        })
    
    if analysis['summary']['missing_in_db'] > 0:
        analysis['recommendations'].append({
            'priority': 'medium',
            'issue': f"{analysis['summary']['missing_in_db']} fields not stored in database",
            'action': 'Consider adding missing fields to player_comprehensive_stats schema'
        })
    
    # Write JSON log
    with open('field_analysis_log.json', 'w', encoding='utf-8') as f:
        json.dump(analysis, f, indent=2)
    
    # Write human-readable text log
    with open('field_analysis_log.txt', 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("COMPREHENSIVE FIELD MAPPING ANALYSIS LOG\n")
        f.write("="*80 + "\n")
        f.write(f"Generated: {analysis['metadata']['generated_at']}\n")
        f.write(f"Player: {analysis['metadata']['player']} ({analysis['metadata']['guid']})\n")
        f.write(f"Map: {analysis['metadata']['map']}\n")
        f.write(f"Date: {analysis['metadata']['date']}\n")
        f.write("\n")
        
        f.write("SUMMARY\n")
        f.write("-"*80 + "\n")
        f.write(f"Total Fields Analyzed: {analysis['summary']['total_fields']}\n")
        f.write(f"Perfect Matches: {analysis['summary']['perfect_matches']}\n")
        f.write(f"Mismatches: {analysis['summary']['mismatches']}\n")
        f.write(f"Missing in DB: {analysis['summary']['missing_in_db']}\n")
        f.write(f"R1 Accuracy: {analysis['summary']['r1_accuracy']:.2f}%\n")
        f.write(f"R2 Accuracy: {analysis['summary']['r2_accuracy']:.2f}%\n")
        f.write("\n")
        
        if analysis['critical_findings']:
            f.write("CRITICAL FINDINGS\n")
            f.write("-"*80 + "\n")
            for finding in analysis['critical_findings']:
                f.write(f"Field: {finding['field']}\n")
                f.write(f"  Issue: {finding['issue']}\n")
                f.write(f"  R1 Expected: {finding['r1_expected']}, Actual: {finding['r1_actual']}\n")
                f.write(f"  R2 Expected: {finding['r2_expected']}, Actual: {finding['r2_actual']}\n")
                f.write("\n")
        
        f.write("RECOMMENDATIONS\n")
        f.write("-"*80 + "\n")
        for rec in analysis['recommendations']:
            f.write(f"[{rec['priority'].upper()}] {rec['issue']}\n")
            f.write(f"  Action: {rec['action']}\n")
            f.write("\n")
        
        f.write("DETAILED FIELD ANALYSIS\n")
        f.write("-"*80 + "\n")
        f.write(f"{'Field':<30} {'Status':<15} {'R1 Match':<10} {'R2 Match':<10}\n")
        f.write("-"*80 + "\n")
        
        for field in analysis['field_analysis']:
            status_symbol = {
                'perfect': '✅',
                'mismatch': '❌',
                'missing_in_db': '⚠️',
                'unknown': '❓'
            }.get(field['status'], '?')
            
            f.write(f"{field['field_name']:<30} {status_symbol + ' ' + field['status']:<15} ")
            f.write(f"{'✓' if field['r1_match'] else '✗':<10} ")
            f.write(f"{'✓' if field['r2_match'] else '✗':<10}\n")
        
        f.write("\n")
        f.write("="*80 + "\n")
        f.write("END OF ANALYSIS\n")
        f.write("="*80 + "\n")
    
    print("✅ Analysis logs generated:")
    print("   - field_analysis_log.json (machine-readable)")
    print("   - field_analysis_log.txt (human-readable)")
    print("\nAnalyzing logs now...\n")
    
    return analysis

def analyze_logs(analysis):
    """Automated analysis of the generated logs."""
    
    print("="*80)
    print("AUTOMATED LOG ANALYSIS")
    print("="*80)
    print()
    
    # Overall health check
    print("📊 SYSTEM HEALTH:")
    total = analysis['summary']['total_fields']
    perfect = analysis['summary']['perfect_matches']
    missing = analysis['summary']['missing_in_db']
    mismatches = analysis['summary']['mismatches']
    
    health_score = (perfect / (total - missing) * 100) if (total - missing) > 0 else 0
    
    print(f"   Health Score: {health_score:.1f}%")
    if health_score >= 90:
        print("   Status: ✅ EXCELLENT - System working as designed")
    elif health_score >= 75:
        print("   Status: ✅ GOOD - Minor issues detected")
    elif health_score >= 50:
        print("   Status: ⚠️ WARNING - Several discrepancies found")
    else:
        print("   Status: ❌ CRITICAL - Major issues require attention")
    
    print()
    print("🔍 PATTERN DETECTION:")
    
    # Check for systematic issues
    time_fields = [f for f in analysis['field_analysis'] if 'time' in f['field_name'].lower()]
    time_mismatches = [f for f in time_fields if f['status'] == 'mismatch']
    
    if time_mismatches:
        print(f"   ⚠️ Time-related fields: {len(time_mismatches)}/{len(time_fields)} mismatches")
        print("      Possible cause: Cumulative vs differential time calculation")
    else:
        print(f"   ✅ Time-related fields: All {len(time_fields)} fields consistent")
    
    damage_fields = [f for f in analysis['field_analysis'] if 'damage' in f['field_name'].lower()]
    damage_perfect = [f for f in damage_fields if f['status'] == 'perfect']
    
    print(f"   ✅ Damage fields: {len(damage_perfect)}/{len(damage_fields)} perfect matches")
    
    objective_fields = [f for f in analysis['field_analysis'] if any(x in f['field_name'].lower() for x in ['objective', 'dynamite', 'revive'])]
    objective_perfect = [f for f in objective_fields if f['status'] == 'perfect']
    
    print(f"   ✅ Objective fields: {len(objective_perfect)}/{len(objective_fields)} perfect matches")
    
    print()
    print("📈 DIFFERENTIAL CALCULATION VERIFICATION:")
    
    # Check differential logic
    core_stats = ['damage_given', 'damage_received', 'gibs', 'self_kills']
    core_analysis = [f for f in analysis['field_analysis'] if f['field_name'] in core_stats]
    core_perfect = [f for f in core_analysis if f['status'] == 'perfect']
    
    print(f"   Core stats verified: {len(core_perfect)}/{len(core_analysis)}")
    for stat in core_perfect:
        print(f"      ✅ {stat['field_name']}: R2_db({stat['r2_database']}) = R2_file({stat['r2_file_cumulative']}) - R1_file({stat['r1_file']})")
    
    print()
    print("💾 DATABASE SCHEMA GAPS:")
    
    missing_fields = [f for f in analysis['field_analysis'] if f['status'] == 'missing_in_db']
    if missing_fields:
        print(f"   {len(missing_fields)} fields not stored in database:")
        for field in missing_fields[:5]:  # Show first 5
            print(f"      • {field['field_name']}")
        if len(missing_fields) > 5:
            print(f"      ... and {len(missing_fields) - 5} more")
    else:
        print("   ✅ All fields stored in database")
    
    print()
    print("="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)

if __name__ == '__main__':
    analysis = generate_analysis_log()
    analyze_logs(analysis)
