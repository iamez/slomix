#!/usr/bin/env python3
"""
🔍 COMPREHENSIVE TIME ANALYSIS - October 2, 2025
================================================
Check time_played_minutes across ALL maps, rounds, and players
to verify the parser fix is working correctly.

Shows:
- Per-map breakdown of time data
- Round 1 vs Round 2 time patterns
- Which records have time = 0
- Consistency checks
- Player-by-player time tracking
"""
import sys
sys.path.insert(0, 'bot')

import sqlite3
from collections import defaultdict

def analyze_time_data():
    """Comprehensive time data analysis."""
    
    conn = sqlite3.connect('etlegacy_production.db')
    c = conn.cursor()
    
    print("=" * 120)
    print("🔍 COMPREHENSIVE TIME ANALYSIS - October 2, 2025")
    print("=" * 120)
    print()
    
    # Get ALL sessions from October 2
    sessions = c.execute('''
        SELECT id, session_date, map_name, round_number, time_limit, actual_time
        FROM sessions
        WHERE session_date LIKE '2025-10-02%'
        ORDER BY session_date, round_number
    ''').fetchall()
    
    print(f"📅 Found {len(sessions)} sessions from October 2, 2025")
    print()
    
    # Group by map
    map_sessions = defaultdict(list)
    for session in sessions:
        map_name = session[2]
        map_sessions[map_name].append(session)
    
    print("=" * 120)
    print("📊 PER-MAP ANALYSIS")
    print("=" * 120)
    print()
    
    total_players_checked = 0
    total_with_time = 0
    total_without_time = 0
    
    for map_name in sorted(map_sessions.keys()):
        sessions_for_map = map_sessions[map_name]
        
        print(f"🗺️  MAP: {map_name}")
        print("-" * 120)
        
        for session in sessions_for_map:
            sid, date, _, round_num, time_limit, actual_time = session
            
            # Get player stats for this session
            players = c.execute('''
                SELECT 
                    player_name,
                    kills,
                    deaths,
                    damage_given,
                    time_played_minutes,
                    dpm
                FROM player_comprehensive_stats
                WHERE session_id = ?
                ORDER BY damage_given DESC
            ''', (sid,)).fetchall()
            
            players_with_time = sum(1 for p in players if p[4] > 0)
            players_without_time = sum(1 for p in players if p[4] == 0)
            
            total_players_checked += len(players)
            total_with_time += players_with_time
            total_without_time += players_without_time
            
            status = "✅" if players_without_time == 0 else "❌"
            
            print(f"  Round {round_num}: {actual_time} session time | {len(players)} players | "
                  f"Time>0: {players_with_time} | Time=0: {players_without_time} {status}")
            
            # Show top 3 players for this round
            if players:
                print(f"    {'Player':<20} {'Kills':<6} {'Deaths':<7} {'Damage':<8} {'Time(min)':<11} {'DPM':<10}")
                for name, kills, deaths, damage, time_mins, dpm in players[:3]:
                    time_str = f"{time_mins:.1f}" if time_mins > 0 else "0.0 ❌"
                    print(f"    {name:<20} {kills:<6} {deaths:<7} {damage:<8} {time_str:<11} {dpm:<10.2f}")
            
            print()
        
        print()
    
    # Summary statistics
    print("=" * 120)
    print("📈 SUMMARY STATISTICS")
    print("=" * 120)
    print()
    
    total_sessions = len(sessions)
    r1_sessions = sum(1 for s in sessions if s[3] == 1)
    r2_sessions = sum(1 for s in sessions if s[3] == 2)
    
    print(f"Total Sessions: {total_sessions}")
    print(f"  Round 1: {r1_sessions}")
    print(f"  Round 2: {r2_sessions}")
    print()
    
    print(f"Total Player Records: {total_players_checked}")
    print(f"  With time > 0: {total_with_time} ({total_with_time/total_players_checked*100:.1f}%)")
    print(f"  With time = 0: {total_without_time} ({total_without_time/total_players_checked*100:.1f}%)")
    print()
    
    # Per-round breakdown
    print("=" * 120)
    print("🔍 ROUND-SPECIFIC ANALYSIS")
    print("=" * 120)
    print()
    
    for round_num in [1, 2]:
        round_sessions = [s for s in sessions if s[3] == round_num]
        
        # Get all player records for this round
        round_session_ids = [s[0] for s in round_sessions]
        placeholders = ','.join('?' * len(round_session_ids))
        
        stats = c.execute(f'''
            SELECT 
                COUNT(*) as total_players,
                SUM(CASE WHEN time_played_minutes > 0 THEN 1 ELSE 0 END) as with_time,
                SUM(CASE WHEN time_played_minutes = 0 THEN 1 ELSE 0 END) as without_time,
                AVG(CASE WHEN time_played_minutes > 0 THEN time_played_minutes ELSE NULL END) as avg_time,
                MIN(CASE WHEN time_played_minutes > 0 THEN time_played_minutes ELSE NULL END) as min_time,
                MAX(time_played_minutes) as max_time
            FROM player_comprehensive_stats
            WHERE session_id IN ({placeholders})
        ''', round_session_ids).fetchone()
        
        total, with_time, without_time, avg_time, min_time, max_time = stats
        
        print(f"Round {round_num}:")
        print(f"  Total player records: {total}")
        print(f"  With time > 0: {with_time} ({with_time/total*100:.1f}%)")
        print(f"  With time = 0: {without_time} ({without_time/total*100:.1f}%)")
        if avg_time:
            print(f"  Average time: {avg_time:.1f} min")
            print(f"  Min time: {min_time:.1f} min")
            print(f"  Max time: {max_time:.1f} min")
        print()
    
    # Check specific players across all rounds
    print("=" * 120)
    print("👤 PLAYER-SPECIFIC TIME TRACKING")
    print("=" * 120)
    print()
    
    # Get top players by total damage
    top_players = c.execute('''
        SELECT 
            p.player_name,
            COUNT(*) as rounds_played,
            SUM(CASE WHEN p.time_played_minutes > 0 THEN 1 ELSE 0 END) as rounds_with_time,
            SUM(CASE WHEN p.time_played_minutes = 0 THEN 1 ELSE 0 END) as rounds_without_time,
            SUM(p.damage_given) as total_damage,
            SUM(p.time_played_minutes) as total_time
        FROM player_comprehensive_stats p
        JOIN sessions s ON p.session_id = s.id
        WHERE s.session_date LIKE '2025-10-02%'
        GROUP BY p.player_name
        ORDER BY total_damage DESC
        LIMIT 10
    ''').fetchall()
    
    print(f"{'Player':<20} {'Rounds':<8} {'Time>0':<10} {'Time=0':<10} {'Total Dmg':<12} {'Total Time':<12} {'Status':<10}")
    print("-" * 120)
    
    for name, rounds, with_time, without_time, damage, time_mins in top_players:
        status = "✅" if without_time == 0 else f"❌ {without_time} missing"
        print(f"{name:<20} {rounds:<8} {with_time:<10} {without_time:<10} {damage:<12} {time_mins:<12.1f} {status:<10}")
    
    print()
    
    # Detailed per-player, per-round breakdown for vid
    print("=" * 120)
    print("🎯 DETAILED TRACKING: vid (Top Damage)")
    print("=" * 120)
    print()
    
    vid_rounds = c.execute('''
        SELECT 
            s.session_date,
            s.map_name,
            s.round_number,
            s.actual_time,
            p.kills,
            p.deaths,
            p.damage_given,
            p.time_played_minutes,
            p.dpm
        FROM player_comprehensive_stats p
        JOIN sessions s ON p.session_id = s.id
        WHERE s.session_date LIKE '2025-10-02%'
        AND p.player_name = 'vid'
        ORDER BY s.session_date, s.round_number
    ''').fetchall()
    
    print(f"{'Time':<8} {'Map':<20} {'Rnd':<5} {'Session':<10} {'Player':<10} {'K':<4} {'D':<4} {'Dmg':<7} {'DPM':<10} {'Status':<10}")
    print("-" * 120)
    
    for date, map_name, rnd, session_time, kills, deaths, damage, player_time, dpm in vid_rounds:
        time_str = date.split()[1] if ' ' in date else date
        player_time_str = f"{player_time:.1f}" if player_time > 0 else "0.0"
        status = "✅" if player_time > 0 else "❌ MISSING"
        
        print(f"{time_str:<8} {map_name:<20} {rnd:<5} {session_time:<10} {player_time_str:<10} "
              f"{kills:<4} {deaths:<4} {damage:<7} {dpm:<10.2f} {status:<10}")
    
    print()
    
    # Check for patterns
    print("=" * 120)
    print("🔬 PATTERN ANALYSIS")
    print("=" * 120)
    print()
    
    # Are all Round 2s missing time?
    r2_with_time = c.execute('''
        SELECT COUNT(*)
        FROM player_comprehensive_stats p
        JOIN sessions s ON p.session_id = s.id
        WHERE s.session_date LIKE '2025-10-02%'
        AND s.round_number = 2
        AND p.time_played_minutes > 0
    ''').fetchone()[0]
    
    r2_without_time = c.execute('''
        SELECT COUNT(*)
        FROM player_comprehensive_stats p
        JOIN sessions s ON p.session_id = s.id
        WHERE s.session_date LIKE '2025-10-02%'
        AND s.round_number = 2
        AND p.time_played_minutes = 0
    ''').fetchone()[0]
    
    r1_with_time = c.execute('''
        SELECT COUNT(*)
        FROM player_comprehensive_stats p
        JOIN sessions s ON p.session_id = s.id
        WHERE s.session_date LIKE '2025-10-02%'
        AND s.round_number = 1
        AND p.time_played_minutes > 0
    ''').fetchone()[0]
    
    r1_without_time = c.execute('''
        SELECT COUNT(*)
        FROM player_comprehensive_stats p
        JOIN sessions s ON p.session_id = s.id
        WHERE s.session_date LIKE '2025-10-02%'
        AND s.round_number = 1
        AND p.time_played_minutes = 0
    ''').fetchone()[0]
    
    print("Pattern: Round 1 vs Round 2 time data")
    print(f"  Round 1: {r1_with_time} with time, {r1_without_time} without time")
    print(f"  Round 2: {r2_with_time} with time, {r2_without_time} without time")
    print()
    
    if r2_without_time > 0 and r1_without_time == 0:
        print("  ❌ PATTERN DETECTED: All missing time is in Round 2!")
        print("     This confirms the Round 2 differential bug.")
    elif r1_without_time == 0 and r2_without_time == 0:
        print("  ✅ PATTERN GOOD: All rounds have time data!")
        print("     Parser fix is working correctly.")
    else:
        print("  ⚠️ MIXED PATTERN: Some Round 1 also missing time")
        print("     May indicate additional issues.")
    
    print()
    
    # Check time consistency (R1 + R2 should be reasonable)
    print("=" * 120)
    print("⚖️ TIME CONSISTENCY CHECK")
    print("=" * 120)
    print()
    
    # For each map, compare R1 and R2 times
    for map_name in sorted(map_sessions.keys()):
        map_rounds = map_sessions[map_name]
        
        r1_session = [s for s in map_rounds if s[3] == 1]
        r2_session = [s for s in map_rounds if s[3] == 2]
        
        if r1_session and r2_session:
            r1_id = r1_session[0][0]
            r2_id = r2_session[0][0]
            r1_time = r1_session[0][5]  # actual_time
            r2_time = r2_session[0][5]
            
            # Get vid's time in both rounds
            vid_r1 = c.execute('''
                SELECT time_played_minutes 
                FROM player_comprehensive_stats 
                WHERE session_id = ? AND player_name = 'vid'
            ''', (r1_id,)).fetchone()
            
            vid_r2 = c.execute('''
                SELECT time_played_minutes 
                FROM player_comprehensive_stats 
                WHERE session_id = ? AND player_name = 'vid'
            ''', (r2_id,)).fetchone()
            
            if vid_r1 and vid_r2:
                vid_r1_time = vid_r1[0]
                vid_r2_time = vid_r2[0]
                
                status = "✅" if vid_r2_time > 0 else "❌"
                
                print(f"{map_name:<20} | Session: R1={r1_time:<8} R2={r2_time:<8} | "
                      f"vid: R1={vid_r1_time:.1f}min R2={vid_r2_time:.1f}min {status}")
    
    print()
    
    conn.close()

if __name__ == '__main__':
    analyze_time_data()
