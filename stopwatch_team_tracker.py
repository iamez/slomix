"""
PROPER STOPWATCH TEAM DETECTION
================================
Track players by GUID through rounds, ignoring Axis/Allies labels.

In stopwatch:
- Round 1: Team A plays Axis, Team B plays Allies  
- Round 2: Team A plays Allies, Team B plays Axis (they SWAP)

We identify the teams by tracking WHO plays TOGETHER across rounds,
ignoring which side (Axis/Allies) they're on.
"""

import sqlite3
from collections import defaultdict
from typing import Dict, List, Set

def get_round_roster(cursor, session_date: str, round_num: int, team: int) -> Set[str]:
    """
    Get FINAL (deduplicated) roster for a specific round/team.
    Uses MAX(time_played) to get the last snapshot.
    """
    cursor.execute("""
        WITH RankedStats AS (
            SELECT *,
                   ROW_NUMBER() OVER (
                       PARTITION BY session_date, round_number, player_guid, team
                       ORDER BY time_played_minutes DESC, id DESC
                   ) as rn
            FROM player_comprehensive_stats
            WHERE session_date = ? AND round_number = ? AND team = ?
        )
        SELECT DISTINCT player_guid, player_name
        FROM RankedStats
        WHERE rn = 1
    """, (session_date, round_num, team))
    
    return {row[0]: row[1] for row in cursor.fetchall()}

def detect_stopwatch_teams(session_date: str):
    """
    Detect persistent teams in stopwatch mode by tracking GUIDs.
    """
    conn = sqlite3.connect('bot/etlegacy_production.db')
    cursor = conn.cursor()
    
    print("="*80)
    print(f"STOPWATCH TEAM DETECTION: {session_date}")
    print("="*80)
    print("\nStrategy: Track players by GUID across rounds")
    print("Round 1 Axis = Team A, Round 1 Allies = Team B")
    print("Then track those GUIDs through all rounds\n")
    
    # Get all rounds
    cursor.execute("""
        SELECT DISTINCT round_number
        FROM player_comprehensive_stats
        WHERE session_date = ?
        ORDER BY round_number
    """, (session_date,))
    
    rounds = [r[0] for r in cursor.fetchall()]
    print(f"Rounds: {rounds}\n")
    
    if not rounds:
        print("❌ No rounds found!")
        conn.close()
        return
    
    # ROUND 1: Establish the baseline teams
    # Whoever plays Axis in R1 = Team A
    # Whoever plays Allies in R1 = Team B
    
    print("="*80)
    print("ROUND 1 - ESTABLISHING BASELINE TEAMS")
    print("="*80)
    
    r1_axis = get_round_roster(cursor, session_date, rounds[0], 1)
    r1_allies = get_round_roster(cursor, session_date, rounds[0], 2)
    
    print(f"\n🔴 Round 1 AXIS (we'll call this TEAM A):")
    print(f"   {len(r1_axis)} players")
    for guid, name in sorted(r1_axis.items(), key=lambda x: x[1]):
        print(f"   - {name:<30} ({guid})")
    
    print(f"\n🔵 Round 1 ALLIES (we'll call this TEAM B):")
    print(f"   {len(r1_allies)} players")
    for guid, name in sorted(r1_allies.items(), key=lambda x: x[1]):
        print(f"   - {name:<30} ({guid})")
    
    # Now track these GUIDs through all rounds
    team_a_guids = set(r1_axis.keys())
    team_b_guids = set(r1_allies.keys())
    
    print("\n" + "="*80)
    print("TRACKING TEAMS THROUGH ALL ROUNDS")
    print("="*80)
    
    for round_num in rounds:
        print(f"\n{'='*80}")
        print(f"ROUND {round_num}")
        print(f"{'='*80}")
        
        # Get actual rosters for this round
        axis_players = get_round_roster(cursor, session_date, round_num, 1)
        allies_players = get_round_roster(cursor, session_date, round_num, 2)
        
        print(f"\n📊 Actual game sides:")
        print(f"   Axis:   {len(axis_players)} players")
        print(f"   Allies: {len(allies_players)} players")
        
        # Now map them to our persistent teams
        team_a_on_axis = team_a_guids & set(axis_players.keys())
        team_a_on_allies = team_a_guids & set(allies_players.keys())
        team_b_on_axis = team_b_guids & set(axis_players.keys())
        team_b_on_allies = team_b_guids & set(allies_players.keys())
        
        print(f"\n🏆 Team A (O*F or similar) - {len(team_a_guids)} total players:")
        if team_a_on_axis:
            print(f"   Playing as AXIS: {len(team_a_on_axis)} players")
            for guid in sorted(team_a_on_axis, key=lambda g: axis_players[g]):
                name = axis_players[guid]
                print(f"      🔴 {name}")
        if team_a_on_allies:
            print(f"   Playing as ALLIES: {len(team_a_on_allies)} players")
            for guid in sorted(team_a_on_allies, key=lambda g: allies_players[g]):
                name = allies_players[guid]
                print(f"      🔵 {name}")
        
        print(f"\n🏆 Team B (slomix or similar) - {len(team_b_guids)} total players:")
        if team_b_on_axis:
            print(f"   Playing as AXIS: {len(team_b_on_axis)} players")
            for guid in sorted(team_b_on_axis, key=lambda g: axis_players[g]):
                name = axis_players[guid]
                print(f"      🔴 {name}")
        if team_b_on_allies:
            print(f"   Playing as ALLIES: {len(team_b_on_allies)} players")
            for guid in sorted(team_b_on_allies, key=lambda g: allies_players[g]):
                name = allies_players[guid]
                print(f"      🔵 {name}")
        
        # Check for stopwatch swap
        if team_a_on_axis and team_b_on_allies and not team_a_on_allies and not team_b_on_axis:
            print(f"\n   ✅ Normal: Team A on Axis, Team B on Allies")
        elif team_a_on_allies and team_b_on_axis and not team_a_on_axis and not team_b_on_allies:
            print(f"\n   ✅ Swapped: Team A on Allies, Team B on Axis (STOPWATCH!)")
        else:
            print(f"\n   ⚠️  Mixed/Unclear team assignments")
    
    # Final summary
    print("\n" + "="*80)
    print("FINAL TEAM SUMMARY")
    print("="*80)
    
    # Get all player names
    cursor.execute("""
        SELECT DISTINCT player_guid, player_name
        FROM player_comprehensive_stats
        WHERE session_date = ?
    """, (session_date,))
    
    all_names = {row[0]: row[1] for row in cursor.fetchall()}
    
    print(f"\n🏆 TEAM A ({len(team_a_guids)} players):")
    for guid in sorted(team_a_guids, key=lambda g: all_names.get(g, '')):
        name = all_names.get(guid, 'Unknown')
        print(f"   - {name:<30} ({guid})")
    
    print(f"\n🏆 TEAM B ({len(team_b_guids)} players):")
    for guid in sorted(team_b_guids, key=lambda g: all_names.get(g, '')):
        name = all_names.get(guid, 'Unknown')
        print(f"   - {name:<30} ({guid})")
    
    # Detect any players not in either team
    all_guids = set(all_names.keys())
    unassigned = all_guids - team_a_guids - team_b_guids
    
    if unassigned:
        print(f"\n⚠️  UNASSIGNED PLAYERS ({len(unassigned)}):")
        for guid in unassigned:
            print(f"   - {all_names[guid]:<30} ({guid})")
    
    conn.close()
    
    return {
        'team_a': team_a_guids,
        'team_b': team_b_guids,
        'player_names': all_names
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python stopwatch_team_tracker.py <session_date>")
        print("Example: python stopwatch_team_tracker.py 2024-10-28")
        sys.exit(1)
    
    session_date = sys.argv[1]
    result = detect_stopwatch_teams(session_date)
