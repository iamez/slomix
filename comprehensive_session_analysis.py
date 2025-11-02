#!/usr/bin/env python3
"""
Comprehensive Session Analysis - Using ACTUAL stat file timestamps
Shows extensive details about sessions, maps, rounds, and scoring
"""

import sqlite3
import json
import os
from datetime import datetime
from collections import defaultdict


def parse_stat_filename(filename):
    """
    Parse stat filename to extract timestamp and metadata
    Format: YYYY-MM-DD-HH-MM-SS-mapname-round-X-stats.txt
    Example: 2025-10-30-18-23-45-te_escape2-round-2-stats.txt
    """
    try:
        parts = filename.replace('-stats.txt', '').split('-')
        
        # Extract date/time components
        year = int(parts[0])
        month = int(parts[1])
        day = int(parts[2])
        hour = int(parts[3])
        minute = int(parts[4])
        second = int(parts[5])
        
        # Create datetime object
        timestamp = datetime(year, month, day, hour, minute, second)
        
        # Find "round" keyword to split map name from round number
        round_idx = None
        for i, part in enumerate(parts):
            if part == 'round':
                round_idx = i
                break
        
        if round_idx is None:
            return None
        
        # Map name is everything between timestamp and "round"
        map_name = '-'.join(parts[6:round_idx])
        
        # Round number is after "round" keyword
        round_num = int(parts[round_idx + 1])
        
        return {
            'filename': filename,
            'timestamp': timestamp,
            'map_name': map_name,
            'round_number': round_num,
            'date': timestamp.strftime('%Y-%m-%d'),
            'time': timestamp.strftime('%H:%M:%S')
        }
    except (ValueError, IndexError) as e:
        print(f"⚠️  Could not parse: {filename} - {e}")
        return None


def get_stat_files_for_date(stats_dir, date):
    """Get all stat files for a specific date with timestamps"""
    files = []
    
    for filename in os.listdir(stats_dir):
        if not filename.endswith('-stats.txt'):
            continue
        
        if not filename.startswith(date):
            continue
        
        parsed = parse_stat_filename(filename)
        if parsed:
            files.append(parsed)
    
    # Sort by actual timestamp
    files.sort(key=lambda x: x['timestamp'])
    
    return files


def get_round_details_from_db(conn, date):
    """Get round details from database including map_id"""
    c = conn.cursor()
    
    c.execute("""
        SELECT id, map_name, map_id, round_number, 
               winner_team, time_limit, actual_time,
               defender_team
        FROM sessions
        WHERE session_date LIKE ?
        ORDER BY id
    """, (f"{date}%",))
    
    rounds = []
    for row in c.fetchall():
        rounds.append({
            'db_id': row[0],
            'map_name': row[1],
            'map_id': row[2],
            'round_number': row[3],
            'winner_team': row[4],
            'time_limit': row[5],
            'actual_time': row[6],
            'defender_team': row[7]
        })
    
    return rounds


def get_team_assignments(conn, date):
    """Get team assignments for the session"""
    c = conn.cursor()
    
    c.execute("""
        SELECT DISTINCT team_name, player_guids, player_names
        FROM session_teams
        WHERE session_start_date LIKE ?
    """, (f"{date}%",))
    
    teams = {}
    for team_name, guids_json, names_json in c.fetchall():
        guids = json.loads(guids_json)
        names = json.loads(names_json)
        teams[team_name] = {
            'guids': guids,
            'names': names
        }
    
    return teams


def get_round_statistics(conn, date, round_db_id):
    """Get detailed statistics for a specific round"""
    c = conn.cursor()
    
    # Get player stats grouped by team
    c.execute("""
        SELECT team, player_name, kills, deaths, damage_given
        FROM player_comprehensive_stats
        WHERE session_date LIKE ?
        AND id IN (
            SELECT id FROM player_comprehensive_stats
            WHERE session_date LIKE ?
            ORDER BY id
            LIMIT (SELECT COUNT(*) FROM player_comprehensive_stats 
                   WHERE session_date LIKE ? AND id <= ?)
        )
        AND id <= ?
        ORDER BY team, kills DESC
    """, (f"{date}%", f"{date}%", f"{date}%", round_db_id, round_db_id))
    
    team_stats = defaultdict(lambda: {
        'players': [],
        'total_kills': 0,
        'total_deaths': 0,
        'total_damage': 0
    })
    
    for team, name, kills, deaths, damage in c.fetchall():
        team_stats[team]['players'].append({
            'name': name,
            'kills': kills,
            'deaths': deaths,
            'damage': damage
        })
        team_stats[team]['total_kills'] += kills
        team_stats[team]['total_deaths'] += deaths
        team_stats[team]['total_damage'] += damage
    
    return dict(team_stats)


def analyze_session_comprehensive(stats_dir, date, db_path):
    """Comprehensive analysis of a single session"""
    
    print(f"\n{'='*100}")
    print(f"📅 COMPREHENSIVE SESSION ANALYSIS: {date}")
    print(f"{'='*100}\n")
    
    # Get stat files with timestamps
    stat_files = get_stat_files_for_date(stats_dir, date)
    
    print(f"📁 Found {len(stat_files)} stat files in local_stats/\n")
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    
    # Get database rounds
    db_rounds = get_round_details_from_db(conn, date)
    
    print(f"💾 Found {len(db_rounds)} rounds in database\n")
    
    # Get team assignments
    teams = get_team_assignments(conn, date)
    
    print(f"👥 Teams detected: {len(teams)}")
    for team_name, team_data in teams.items():
        names = ', '.join(team_data['names'])
        print(f"   • {team_name}: {names} ({len(team_data['names'])} players)")
    print()
    
    # Match stat files to database rounds by map_name and round_number
    print(f"{'='*100}")
    print(f"🗺️  CHRONOLOGICAL ROUND ANALYSIS (by stat file timestamp)")
    print(f"{'='*100}\n")
    
    map_groups = defaultdict(list)
    
    for i, stat_file in enumerate(stat_files, 1):
        # Find matching database round
        db_round = None
        for r in db_rounds:
            if (r['map_name'] == stat_file['map_name'] and 
                r['round_number'] == stat_file['round_number']):
                # Match found
                if db_round is None or r['db_id'] not in [
                    s['db_round']['db_id'] for s in map_groups.values() 
                    for s in s if 'db_round' in s
                ]:
                    db_round = r
                    break
        
        if not db_round:
            print(f"⚠️  Round {i}: No database match for {stat_file['filename']}")
            continue
        
        # Group by map_id for pairing analysis
        map_id = db_round.get('map_id')
        map_groups[map_id].append({
            'seq': i,
            'stat_file': stat_file,
            'db_round': db_round
        })
        
        # Display round details
        winner_emoji = "🟢" if db_round['winner_team'] == 1 else "🔴"
        map_id_str = f"Map{map_id}" if map_id else "NoMapID"
        
        print(f"╔═ Round #{i:02d} [{map_id_str}] ═══════════════════════════════")
        print(f"║")
        print(f"║ 📄 Stat File: {stat_file['filename']}")
        print(f"║ 🕐 Timestamp: {stat_file['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"║ 🗺️  Map: {stat_file['map_name']:<30} Round: R{stat_file['round_number']}")
        print(f"║ 💾 DB ID: {db_round['db_id']:<5} map_id: {map_id}")
        print(f"║")
        print(f"║ ⏱️  Time Limit: {db_round['time_limit']:<10} Actual: {db_round['actual_time']}")
        print(f"║ {winner_emoji} Winner: Team {db_round['winner_team']}")
        print(f"║")
        
        # Get round statistics
        stats = get_round_statistics(conn, date, db_round['db_id'])
        
        if stats:
            print(f"║ 📊 Round Statistics:")
            for team_num in sorted(stats.keys()):
                team_data = stats[team_num]
                print(f"║   Team {team_num}: "
                      f"{team_data['total_kills']} kills, "
                      f"{team_data['total_deaths']} deaths, "
                      f"{team_data['total_damage']:,} damage")
        
        print(f"╚═══════════════════════════════════════════════════════\n")
    
    # Map pairing analysis
    print(f"\n{'='*100}")
    print(f"🎯 MAP PAIRING ANALYSIS")
    print(f"{'='*100}\n")
    
    complete_maps = 0
    orphaned_rounds = 0
    
    for map_id in sorted(map_groups.keys()):
        if map_id is None:
            continue
        
        rounds = map_groups[map_id]
        
        has_r1 = any(r['db_round']['round_number'] == 1 for r in rounds)
        has_r2 = any(r['db_round']['round_number'] == 2 for r in rounds)
        
        if has_r1 and has_r2:
            status = "✅ COMPLETE"
            complete_maps += 1
        else:
            status = "⚠️  ORPHANED"
            orphaned_rounds += len(rounds)
        
        map_name = rounds[0]['db_round']['map_name']
        
        print(f"Map ID {map_id}: {map_name:<25} {status}")
        
        for r in rounds:
            seq = r['seq']
            rnd = r['db_round']['round_number']
            timestamp = r['stat_file']['timestamp'].strftime('%H:%M:%S')
            db_id = r['db_round']['db_id']
            winner = r['db_round']['winner_team']
            
            indent = "  "
            print(f"{indent}Round #{seq:02d}: R{rnd} @ {timestamp} "
                  f"(DB:{db_id}) - Team {winner} won")
    
    print(f"\n{'='*100}")
    print(f"📈 SUMMARY")
    print(f"{'='*100}\n")
    print(f"Total stat files: {len(stat_files)}")
    print(f"Total DB rounds: {len(db_rounds)}")
    print(f"Complete maps (R1+R2): {complete_maps}")
    print(f"Orphaned rounds: {orphaned_rounds}")
    
    # Calculate scoring
    print(f"\n{'='*100}")
    print(f"🏆 SCORING CALCULATIONS")
    print(f"{'='*100}\n")
    
    # Round win percentage
    team_round_wins = defaultdict(int)
    total_rounds_with_winner = 0
    
    for db_round in db_rounds:
        if db_round['winner_team'] in [1, 2]:
            team_round_wins[db_round['winner_team']] += 1
            total_rounds_with_winner += 1
    
    print(f"📊 Round Win Percentage (SuperBoyy's method):")
    for team_num in sorted(team_round_wins.keys()):
        wins = team_round_wins[team_num]
        pct = (wins / total_rounds_with_winner * 100) if total_rounds_with_winner > 0 else 0
        print(f"   Team {team_num}: {wins}/{total_rounds_with_winner} rounds = {pct:.1f}%")
    
    # Map-based scoring (complete maps only)
    print(f"\n🗺️  Map-Based Wins (complete maps only):")
    team_map_wins = defaultdict(int)
    map_ties = 0
    
    for map_id in sorted(map_groups.keys()):
        if map_id is None:
            continue
        
        rounds = map_groups[map_id]
        
        has_r1 = any(r['db_round']['round_number'] == 1 for r in rounds)
        has_r2 = any(r['db_round']['round_number'] == 2 for r in rounds)
        
        if not (has_r1 and has_r2):
            continue
        
        r1_winner = next((r['db_round']['winner_team'] for r in rounds 
                         if r['db_round']['round_number'] == 1), 0)
        r2_winner = next((r['db_round']['winner_team'] for r in rounds 
                         if r['db_round']['round_number'] == 2), 0)
        
        if r1_winner == r2_winner and r1_winner != 0:
            team_map_wins[r1_winner] += 1
        elif r1_winner != r2_winner and r1_winner != 0 and r2_winner != 0:
            map_ties += 1
    
    total_complete_maps = sum(team_map_wins.values()) + map_ties
    
    for team_num in sorted(team_map_wins.keys()):
        wins = team_map_wins[team_num]
        pct = (wins / total_complete_maps * 100) if total_complete_maps > 0 else 0
        print(f"   Team {team_num}: {wins}/{total_complete_maps} maps = {pct:.1f}%")
    
    if map_ties > 0:
        print(f"   Ties: {map_ties}/{total_complete_maps} maps")
    
    print(f"\n{'='*100}\n")
    
    conn.close()


if __name__ == "__main__":
    stats_dir = "local_stats"
    db_path = "bot/etlegacy_production.db"
    
    # Analyze both clean sessions
    analyze_session_comprehensive(stats_dir, "2025-10-28", db_path)
    analyze_session_comprehensive(stats_dir, "2025-10-30", db_path)
