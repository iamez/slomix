#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MAXIMUM DETAIL ANALYSIS
Shows EVERYTHING for each round:
- Source stat filename
- Complete team rosters (who was on which team)
- All time fields
- All statistics
"""

import sqlite3
import json
import sys
from collections import defaultdict

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')


def get_all_round_details(conn, date):
    """Get EVERYTHING about each round"""
    c = conn.cursor()
    
    # Get all session data with ALL available fields
    c.execute("""
        SELECT 
            id,
            round_date,
            map_name,
            map_id,
            round_number,
            winner_team,
            defender_team,
            time_limit,
            actual_time
        FROM rounds
        WHERE round_date LIKE ?
        ORDER BY id
    """, (f"{date}%",))
    
    rounds_data = []
    for row in c.fetchall():
        rounds_data.append({
            'id': row[0],
            'round_date': row[1],
            'map_name': row[2],
            'map_id': row[3],
            'round_number': row[4],
            'winner_team': row[5],
            'defender_team': row[6],
            'time_limit': row[7],
            'actual_time': row[8]
        })
    
    return rounds_data


def get_players_for_round(conn, round_date, map_name, round_num):
    """Get ALL players for a specific round with full details"""
    c = conn.cursor()
    
    c.execute("""
        SELECT 
            player_guid,
            player_name,
            team,
            kills,
            deaths,
            damage_given,
            damage_received,
            team_kills,
            team_damage_given,
            self_kills,
            xp,
            revives_given,
            efficiency
        FROM player_comprehensive_stats
        WHERE round_date = ?
        AND map_name = ?
        AND round_number = ?
        ORDER BY team, kills DESC
    """, (round_date, map_name, round_num))
    
    players = []
    for row in c.fetchall():
        players.append({
            'guid': row[0],
            'name': row[1],
            'team': row[2],
            'kills': row[3],
            'deaths': row[4],
            'damage_given': row[5],
            'damage_received': row[6],
            'team_kills': row[7],
            'team_damage_given': row[8],
            'self_kills': row[9],
            'xp': row[10],
            'revives': row[11],
            'efficiency': row[12]
        })
    
    return players


def get_team_info(conn, date):
    """Get the persistent team assignments"""
    c = conn.cursor()
    
    c.execute("""
        SELECT DISTINCT team_name, player_guids, player_names
        FROM session_teams
        WHERE session_start_date LIKE ?
        LIMIT 2
    """, (f"{date}%",))
    
    teams = []
    for team_name, guids_json, names_json in c.fetchall():
        guids = json.loads(guids_json)
        names = json.loads(names_json)
        teams.append({
            'name': team_name,
            'guids': set(guids),
            'names': names
        })
    
    return teams


def identify_persistent_team(guid, teams):
    """Identify which persistent team this player belongs to"""
    if not teams:
        return "Unknown"
    
    for team in teams:
        if guid in team['guids']:
            return team['name']
    
    return "Unknown"


def analyze_maximum_detail(date, db_path):
    """Maximum detail analysis"""
    
    conn = sqlite3.connect(db_path)
    
    print(f"\n{'='*140}")
    print(f"🔬 MAXIMUM DETAIL ANALYSIS: {date}")
    print(f"{'='*140}\n")
    
    # Get persistent team assignments
    teams = get_team_info(conn, date)
    
    print(f"👥 PERSISTENT TEAM ASSIGNMENTS (across all maps):")
    print(f"{'='*140}")
    for i, team in enumerate(teams, 1):
        print(f"\n{team['name']}:")
        print(f"  Members ({len(team['names'])}): {', '.join(sorted(set(team['names'])))}")
    print(f"\n{'='*140}\n")
    
    # Get all rounds
    rounds = get_all_round_details(conn, date)
    
    print(f"💾 TOTAL ROUNDS IN DATABASE: {len(rounds)}\n")
    print(f"{'='*140}\n")
    
    # Track map pairings
    map_groups = defaultdict(list)
    
    # Analyze each round
    for round_data in rounds:
        map_groups[round_data['map_id']].append(round_data)
        
        rid = round_data['id']
        map_id = round_data['map_id']
        map_name = round_data['map_name']
        round_num = round_data['round_number']
        winner = round_data['winner_team']
        defender = round_data['defender_team']
        
        print(f"╔{'═'*138}╗")
        print(f"║ ROUND #{rid:04d}  │  Map ID: {map_id if map_id else 'NULL':>3}  │  {map_name:<40}  │  R{round_num}{'':>60}║")
        print(f"╠{'═'*138}╣")
        
        # Session date (timestamp from stat filename embedded in round_date)
        round_date = round_data['round_date']
        # round_date format: YYYY-MM-DD-HHMMSS
        # Extract original stat filename from round_date
        stat_file_pattern = f"{round_date}-{map_name}-round-{round_num}-stats.txt"
        
        print(f"║ 📄 SOURCE FILE (derived): {stat_file_pattern:<100} ║")
        print(f"║{'':140}║")
        
        # Session date (timestamp)
        print(f"║ 🕐 SESSION TIMESTAMP: {round_date:<118} ║")
        print(f"║    Format: YYYY-MM-DD-HHMMSS (date + time when round was played){'':58}║")
        print(f"║{'':140}║")
        
        # Time information
        time_limit = round_data['time_limit'] or "N/A"
        actual_time = round_data['actual_time'] or "N/A"
        
        print(f"║ ⏱️  TIME INFORMATION:{'':120}║")
        print(f"║    • Time Limit:  {time_limit:<15} (max time allowed for attackers to complete objectives){'':42}║")
        print(f"║    • Actual Time: {actual_time:<15} (how long it took attackers to complete, or time limit if failed){'':21}║")
        print(f"║{'':140}║")
        
        # Winner and defender
        winner_emoji = "🟢" if winner == 1 else "🔴" if winner == 2 else "⚪"
        defender_emoji = "🛡️"
        print(f"║ {winner_emoji} WINNER: Team {winner}{'':128}║")
        print(f"║ {defender_emoji} DEFENDER: Team {defender}{'':125}║")
        print(f"║{'':140}║")
        
        # Get all players for this round
        players = get_players_for_round(
            conn, 
            round_date, 
            map_name, 
            round_num
        )
        
        if not players:
            print(f"║ ⚠️  NO PLAYER DATA FOUND{'':121}║")
        else:
            # Separate by game team
            team1_players = [p for p in players if p['team'] == 1]
            team2_players = [p for p in players if p['team'] == 2]
            
            # Calculate team totals
            team1_kills = sum(p['kills'] for p in team1_players)
            team1_deaths = sum(p['deaths'] for p in team1_players)
            team1_damage = sum(p['damage_given'] for p in team1_players)
            
            team2_kills = sum(p['kills'] for p in team2_players)
            team2_deaths = sum(p['deaths'] for p in team2_players)
            team2_damage = sum(p['damage_given'] for p in team2_players)
            
            print(f"║ 📊 TEAM STATISTICS:{'':124}║")
            print(f"║    Game Team 1: {len(team1_players):2} players  │  {team1_kills:3} kills  │  {team1_deaths:3} deaths  │  {team1_damage:>7,} damage{'':43}║")
            print(f"║    Game Team 2: {len(team2_players):2} players  │  {team2_kills:3} kills  │  {team2_deaths:3} deaths  │  {team2_damage:>7,} damage{'':43}║")
            print(f"║{'':140}║")
            
            # Show GAME TEAM 1 players
            print(f"║ 🟢 GAME TEAM 1 ROSTER ({len(team1_players)} players):{'':100}║")
            print(f"║{'':140}║")
            
            for p in team1_players:
                persistent_team = identify_persistent_team(p['guid'], teams)
                kd_ratio = f"{p['kills']}/{p['deaths']}"
                eff = f"{p['efficiency']:.1f}%" if p['efficiency'] else "N/A"
                
                # Color indicator based on persistent team
                team_indicator = "🔵" if persistent_team == (teams[0]['name'] if teams else "Unknown") else "🔴"
                
                print(f"║ {team_indicator} {p['name']:<20} │ K/D: {kd_ratio:>7} │ Dmg: {p['damage_given']:>6,} │ XP: {p['xp']:>5} │ Eff: {eff:>6} │ [{persistent_team}]{'':20}║")
            
            print(f"║{'':140}║")
            
            # Show GAME TEAM 2 players
            print(f"║ 🔴 GAME TEAM 2 ROSTER ({len(team2_players)} players):{'':100}║")
            print(f"║{'':140}║")
            
            for p in team2_players:
                persistent_team = identify_persistent_team(p['guid'], teams)
                kd_ratio = f"{p['kills']}/{p['deaths']}"
                eff = f"{p['efficiency']:.1f}%" if p['efficiency'] else "N/A"
                
                team_indicator = "🔵" if persistent_team == (teams[0]['name'] if teams else "Unknown") else "🔴"
                
                print(f"║ {team_indicator} {p['name']:<20} │ K/D: {kd_ratio:>7} │ Dmg: {p['damage_given']:>6,} │ XP: {p['xp']:>5} │ Eff: {eff:>6} │ [{persistent_team}]{'':20}║")
        
        print(f"╚{'═'*138}╝")
        print()
    
    # Map pairing summary
    print(f"\n{'='*140}")
    print(f"🎯 MAP PAIRING SUMMARY")
    print(f"{'='*140}\n")
    
    complete_maps = 0
    orphaned = 0
    
    for map_id in sorted(map_groups.keys()):
        if map_id is None:
            continue
        
        rounds_in_map = map_groups[map_id]
        has_r1 = any(r['round_number'] == 1 for r in rounds_in_map)
        has_r2 = any(r['round_number'] == 2 for r in rounds_in_map)
        
        map_name = rounds_in_map[0]['map_name']
        
        if has_r1 and has_r2:
            complete_maps += 1
            r1 = next(r for r in rounds_in_map if r['round_number'] == 1)
            r2 = next(r for r in rounds_in_map if r['round_number'] == 2)
            
            print(f"✅ Map {map_id:>2}: {map_name:<30} COMPLETE")
            print(f"   R1: DB#{r1['id']:>4} @ {r1['round_date']} - Winner: Team {r1['winner_team']}")
            print(f"   R2: DB#{r2['id']:>4} @ {r2['round_date']} - Winner: Team {r2['winner_team']}")
            
            if r1['winner_team'] == r2['winner_team']:
                print(f"   🏆 Map Winner: Team {r1['winner_team']} (2-0)")
            else:
                print(f"   🤝 Map Tied: 1-1")
        else:
            orphaned += len(rounds_in_map)
            print(f"⚠️  Map {map_id:>2}: {map_name:<30} ORPHANED")
            
            for r in rounds_in_map:
                print(f"   R{r['round_number']}: DB#{r['id']:>4} @ {r['round_date']} - MISSING PAIR!")
        
        print()
    
    # Final summary
    print(f"{'='*140}")
    print(f"📊 FINAL SUMMARY")
    print(f"{'='*140}\n")
    print(f"Complete maps (R1+R2): {complete_maps}")
    print(f"Orphaned rounds: {orphaned}")
    print(f"Total rounds: {len(rounds)}")
    
    print(f"\n{'='*140}\n")
    
    conn.close()


if __name__ == "__main__":
    db_path = "bot/etlegacy_production.db"
    
    # Focus on Oct 30 (the one with issues)
    analyze_maximum_detail("2025-10-30", db_path)
    
    print("\n\n")
    
    # Then Oct 28 (the clean one)
    analyze_maximum_detail("2025-10-28", db_path)
