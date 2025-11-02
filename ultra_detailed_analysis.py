#!/usr/bin/env python3
"""
ULTRA-COMPREHENSIVE Database Analysis
Shows every detail about sessions for manual review
"""

import sqlite3
import json
from collections import defaultdict


def get_session_rounds_detailed(conn, date):
    """Get all rounds with full details"""
    c = conn.cursor()
    
    c.execute("""
        SELECT 
            s.id,
            s.session_date,
            s.map_name,
            s.map_id,
            s.round_number,
            s.winner_team,
            s.defender_team,
            s.time_limit,
            s.actual_time,
            COUNT(DISTINCT p.player_guid) as player_count,
            SUM(CASE WHEN p.team = 1 THEN p.kills ELSE 0 END) as team1_kills,
            SUM(CASE WHEN p.team = 2 THEN p.kills ELSE 0 END) as team2_kills,
            SUM(CASE WHEN p.team = 1 THEN p.damage_given ELSE 0 END) as team1_damage,
            SUM(CASE WHEN p.team = 2 THEN p.damage_given ELSE 0 END) as team2_damage,
            SUM(CASE WHEN p.team = 1 THEN 1 ELSE 0 END) as team1_players,
            SUM(CASE WHEN p.team = 2 THEN 1 ELSE 0 END) as team2_players
        FROM sessions s
        LEFT JOIN player_comprehensive_stats p 
            ON p.session_date = s.session_date 
            AND p.map_name = s.map_name 
            AND p.round_number = s.round_number
        WHERE s.session_date LIKE ?
        GROUP BY s.id
        ORDER BY s.id
    """, (f"{date}%",))
    
    return c.fetchall()


def get_round_players(conn, session_date, map_name, round_num):
    """Get all players for a specific round"""
    c = conn.cursor()
    
    c.execute("""
        SELECT team, player_name, player_guid, kills, deaths, 
               damage_given, damage_received, xp
        FROM player_comprehensive_stats
        WHERE session_date LIKE ?
        AND map_name = ?
        AND round_number = ?
        ORDER BY team, kills DESC
    """, (f"{session_date}%", map_name, round_num))
    
    return c.fetchall()


def get_team_info(conn, date):
    """Get team assignments"""
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


def identify_team_from_guids(player_guids, teams):
    """Identify which team a set of player GUIDs belongs to"""
    if not teams or len(teams) < 2:
        return "Unknown"
    
    team1_matches = len(set(player_guids) & teams[0]['guids'])
    team2_matches = len(set(player_guids) & teams[1]['guids'])
    
    if team1_matches > team2_matches:
        return teams[0]['name']
    elif team2_matches > team1_matches:
        return teams[1]['name']
    else:
        return "Mixed"


def analyze_session_ultra_detailed(date, db_path):
    """Ultra-comprehensive analysis with all details"""
    
    conn = sqlite3.connect(db_path)
    
    print(f"\n{'='*120}")
    print(f"📅 ULTRA-COMPREHENSIVE ANALYSIS: {date}")
    print(f"{'='*120}\n")
    
    # Get team info
    teams = get_team_info(conn, date)
    
    if teams:
        print(f"👥 TEAM ASSIGNMENTS:")
        for i, team in enumerate(teams, 1):
            print(f"   Team {i} ({team['name']}): {', '.join(team['names'][:8])}")
            if len(team['names']) > 8:
                print(f"      ... and {len(team['names']) - 8} more")
        print()
    
    # Get all rounds
    rounds = get_session_rounds_detailed(conn, date)
    
    print(f"💾 Total rounds in database: {len(rounds)}\n")
    
    # Group by map_id for pairing analysis
    map_groups = defaultdict(list)
    
    print(f"{'='*120}")
    print(f"🗺️  DETAILED ROUND-BY-ROUND ANALYSIS")
    print(f"{'='*120}\n")
    
    for round_data in rounds:
        (db_id, session_date, map_name, map_id, round_num, winner_team,
         defender_team, time_limit, actual_time, player_count,
         team1_kills, team2_kills, team1_damage, team2_damage,
         team1_players, team2_players) = round_data
        
        # Track for pairing analysis
        map_groups[map_id].append({
            'db_id': db_id,
            'round_num': round_num,
            'winner': winner_team
        })
        
        # Determine completion status
        limit_mins = 0
        actual_mins = 0
        if ':' in str(time_limit):
            parts = time_limit.split(':')
            limit_mins = int(parts[0]) * 60 + int(parts[1])
        if ':' in str(actual_time):
            parts = actual_time.split(':')
            actual_mins = int(parts[0]) * 60 + int(parts[1])
        
        completed = actual_mins < limit_mins if limit_mins > 0 else False
        completion_status = "✅ Completed" if completed else "⏱️  Full Hold"
        
        # Winner emoji
        winner_emoji = "🟢" if winner_team == 1 else "🔴" if winner_team == 2 else "⚪"
        
        # Balance check
        balance_status = "⚖️  Balanced" if abs(team1_players - team2_players) <= 1 else "⚠️  UNBALANCED"
        
        print(f"╔═══════════════════════════════════════════════════════════════════════════════════════════════════════════╗")
        print(f"║ ROUND #{db_id:03d} - Map ID: {map_id if map_id else 'NULL':>3} - R{round_num}                                                                                      ║")
        print(f"╠═══════════════════════════════════════════════════════════════════════════════════════════════════════════╣")
        print(f"║ 🗺️  Map: {map_name:<50} Round: {round_num}                                      ║")
        print(f"║ 📅 Date: {session_date}                                                                               ║")
        print(f"║                                                                                                           ║")
        print(f"║ ⏱️  Time Limit: {time_limit:<10} │ Actual Time: {actual_time:<10} │ {completion_status:<20}                      ║")
        print(f"║ {winner_emoji} Winner: Team {winner_team}                                                                                           ║")
        print(f"║                                                                                                           ║")
        print(f"║ 📊 TEAM STATISTICS:                                                                                       ║")
        print(f"║    Team 1: {team1_players} players │ {team1_kills:>3} kills │ {team1_damage:>6,} damage                                                  ║")
        print(f"║    Team 2: {team2_players} players │ {team2_kills:>3} kills │ {team2_damage:>6,} damage                                                  ║")
        print(f"║    {balance_status}                                                                                       ║")
        print(f"║                                                                                                           ║")
        
        # Get detailed player stats
        players = get_round_players(conn, session_date, map_name, round_num)
        
        if players:
            print(f"║ 👥 PLAYER DETAILS:                                                                                        ║")
            
            # Group by team
            team1_players_list = [p for p in players if p[0] == 1]
            team2_players_list = [p for p in players if p[0] == 2]
            
            print(f"║                                                                                                           ║")
            print(f"║    🟢 TEAM 1 ({len(team1_players_list)} players):                                                                                  ║")
            for team, name, guid, kills, deaths, dmg_given, dmg_recv, xp in team1_players_list[:5]:
                # Identify actual team
                actual_team = identify_team_from_guids([guid], teams) if teams else "?"
                kd_ratio = f"{kills/deaths:.2f}" if deaths > 0 else f"{kills}.00"
                print(f"║       {name:<20} │ K/D: {kills:>2}/{deaths:<2} ({kd_ratio:>5}) │ Dmg: {dmg_given:>6,} │ [{actual_team}]             ║")
            
            if len(team1_players_list) > 5:
                print(f"║       ... and {len(team1_players_list) - 5} more players                                                                         ║")
            
            print(f"║                                                                                                           ║")
            print(f"║    🔴 TEAM 2 ({len(team2_players_list)} players):                                                                                  ║")
            for team, name, guid, kills, deaths, dmg_given, dmg_recv, xp in team2_players_list[:5]:
                actual_team = identify_team_from_guids([guid], teams) if teams else "?"
                kd_ratio = f"{kills/deaths:.2f}" if deaths > 0 else f"{kills}.00"
                print(f"║       {name:<20} │ K/D: {kills:>2}/{deaths:<2} ({kd_ratio:>5}) │ Dmg: {dmg_given:>6,} │ [{actual_team}]             ║")
            
            if len(team2_players_list) > 5:
                print(f"║       ... and {len(team2_players_list) - 5} more players                                                                         ║")
        
        print(f"╚═══════════════════════════════════════════════════════════════════════════════════════════════════════════╝")
        print()
    
    # Pairing analysis
    print(f"\n{'='*120}")
    print(f"🎯 MAP PAIRING ANALYSIS")
    print(f"{'='*120}\n")
    
    complete_maps = 0
    orphaned = 0
    
    for map_id in sorted(map_groups.keys()):
        if map_id is None:
            print(f"⚠️  Map ID NULL: {len(map_groups[map_id])} rounds (cannot pair)")
            orphaned += len(map_groups[map_id])
            continue
        
        rounds_in_map = map_groups[map_id]
        has_r1 = any(r['round_num'] == 1 for r in rounds_in_map)
        has_r2 = any(r['round_num'] == 2 for r in rounds_in_map)
        
        if has_r1 and has_r2:
            status = "✅ COMPLETE"
            complete_maps += 1
            
            r1 = next(r for r in rounds_in_map if r['round_num'] == 1)
            r2 = next(r for r in rounds_in_map if r['round_num'] == 2)
            
            print(f"Map {map_id:>2}: {status}")
            print(f"   R1 (DB:{r1['db_id']:>4}) - Winner: Team {r1['winner']}")
            print(f"   R2 (DB:{r2['db_id']:>4}) - Winner: Team {r2['winner']}")
            
            if r1['winner'] == r2['winner']:
                print(f"   🏆 Map Winner: Team {r1['winner']} (2-0)")
            else:
                print(f"   🤝 Map Result: TIE (1-1)")
        else:
            status = "⚠️  ORPHANED"
            orphaned += len(rounds_in_map)
            
            print(f"Map {map_id:>2}: {status}")
            for r in rounds_in_map:
                print(f"   R{r['round_num']} (DB:{r['db_id']:>4}) - Winner: Team {r['winner']} [MISSING PAIR]")
        
        print()
    
    # Final summary
    print(f"{'='*120}")
    print(f"📊 SCORING SUMMARY")
    print(f"{'='*120}\n")
    
    team_round_wins = defaultdict(int)
    total_rounds = 0
    
    for round_data in rounds:
        winner = round_data[5]
        if winner in [1, 2]:
            team_round_wins[winner] += 1
            total_rounds += 1
    
    print(f"📈 Round Win Percentage (what SuperBoyy shows in screenshots):")
    for team_num in sorted(team_round_wins.keys()):
        wins = team_round_wins[team_num]
        pct = (wins / total_rounds * 100) if total_rounds > 0 else 0
        team_name = teams[team_num - 1]['name'] if team_num <= len(teams) else f"Team {team_num}"
        print(f"   {team_name}: {wins}/{total_rounds} rounds = {pct:.1f}%")
    
    print(f"\n🗺️  Complete Maps: {complete_maps}")
    print(f"⚠️  Orphaned Rounds: {orphaned}")
    
    print(f"\n{'='*120}\n")
    
    conn.close()


if __name__ == "__main__":
    db_path = "bot/etlegacy_production.db"
    
    analyze_session_ultra_detailed("2025-10-28", db_path)
    analyze_session_ultra_detailed("2025-10-30", db_path)
