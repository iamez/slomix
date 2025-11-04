"""
Show October 2, 2025 session stats and compare with expected values.
This is the session we've been debugging.
"""
import sys
from pathlib import Path
# Add project root to sys.path (relative, portable)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sqlite3
from datetime import datetime

def show_last_session_summary():
    """Show the complete last session summary."""
    
    conn = sqlite3.connect('etlegacy_production.db')
    c = conn.cursor()
    
    print("=" * 100)
    print("📅 LAST SESSION - October 2, 2025")
    print("=" * 100)
    print()
    
    # Get all sessions from October 2
    sessions = c.execute('''
        SELECT id, session_date, map_name, round_number, time_limit, actual_time
        FROM sessions
        WHERE session_date LIKE '2025-10-02%'
        ORDER BY session_date
    ''').fetchall()
    
    if not sessions:
        print("❌ No sessions found for October 2, 2025!")
        print()
        latest = c.execute('SELECT MAX(session_date) FROM sessions').fetchone()[0]
        print(f"Latest session in database: {latest}")
        conn.close()
        return
    
    print(f"🎮 Total Sessions: {len(sessions)}")
    print()
    
    # Show session details
    print("📋 SESSION BREAKDOWN:")
    print(f"{'ID':<6} {'Date':<20} {'Map':<20} {'Round':<7} {'Time Limit':<12} {'Actual':<10}")
    print("-" * 100)
    for session in sessions:
        sid, date, map_name, rnd, limit, actual = session
        print(f"{sid:<6} {date:<20} {map_name:<20} {rnd:<7} {limit:<12} {actual:<10}")
    
    print()
    print("=" * 100)
    print("🏆 TOP PLAYERS - KILLS")
    print("=" * 100)
    print()
    
    # Get top players by total kills
    top_killers = c.execute('''
        SELECT 
            p.player_name,
            SUM(p.kills) as total_kills,
            SUM(p.deaths) as total_deaths,
            SUM(p.damage_given) as total_damage,
            SUM(p.time_played_minutes) as total_time,
            ROUND(CAST(SUM(p.kills) AS REAL) / NULLIF(SUM(p.deaths), 0), 2) as kd_ratio,
            COUNT(DISTINCT s.id) as rounds_played
        FROM player_comprehensive_stats p
        JOIN sessions s ON p.session_id = s.id
        WHERE s.session_date LIKE '2025-10-02%'
        GROUP BY p.player_name
        ORDER BY total_kills DESC
        LIMIT 10
    ''').fetchall()
    
    print(f"{'Rank':<6} {'Player':<20} {'Kills':<8} {'Deaths':<8} {'K/D':<8} {'Damage':<10} {'Time(min)':<12} {'Rounds':<8}")
    print("-" * 100)
    
    for i, (name, kills, deaths, damage, time_mins, kd, rounds) in enumerate(top_killers, 1):
        time_display = f"{time_mins:.1f}" if time_mins else "N/A"
        print(f"{i:<6} {name:<20} {kills:<8} {deaths:<8} {kd:<8} {damage:<10} {time_display:<12} {rounds:<8}")
    
    print()
    print("=" * 100)
    print("💪 DAMAGE PER MINUTE ANALYSIS")
    print("=" * 100)
    print()
    
    # Calculate DPM properly - per player across all rounds
    print("Method 1: BOT's CURRENT METHOD (AVG of per-round DPM)")
    print("-" * 100)
    
    bot_dpm = c.execute('''
        SELECT 
            p.player_name,
            ROUND(AVG(p.dpm), 2) as avg_dpm,
            COUNT(*) as rounds
        FROM player_comprehensive_stats p
        JOIN sessions s ON p.session_id = s.id
        WHERE s.session_date LIKE '2025-10-02%'
        GROUP BY p.player_name
        ORDER BY avg_dpm DESC
        LIMIT 10
    ''').fetchall()
    
    print(f"{'Rank':<6} {'Player':<20} {'Bot DPM':<12} {'Rounds':<8}")
    print("-" * 100)
    for i, (name, dpm, rounds) in enumerate(bot_dpm, 1):
        print(f"{i:<6} {name:<20} {dpm:<12.2f} {rounds:<8}")
    
    print()
    print("Method 2: CORRECT METHOD (Total Damage / Total Time)")
    print("-" * 100)
    
    correct_dpm = c.execute('''
        SELECT 
            p.player_name,
            SUM(p.damage_given) as total_damage,
            SUM(p.time_played_minutes) as total_time,
            ROUND(CAST(SUM(p.damage_given) AS REAL) / NULLIF(SUM(p.time_played_minutes), 0), 2) as correct_dpm,
            COUNT(*) as rounds
        FROM player_comprehensive_stats p
        JOIN sessions s ON p.session_id = s.id
        WHERE s.session_date LIKE '2025-10-02%'
        GROUP BY p.player_name
        HAVING total_time > 0
        ORDER BY correct_dpm DESC
        LIMIT 10
    ''').fetchall()
    
    print(f"{'Rank':<6} {'Player':<20} {'Total Dmg':<12} {'Total Time':<12} {'Correct DPM':<15} {'Rounds':<8}")
    print("-" * 100)
    for i, (name, damage, time_mins, dpm, rounds) in enumerate(correct_dpm, 1):
        print(f"{i:<6} {name:<20} {damage:<12} {time_mins:<12.1f} {dpm:<15.2f} {rounds:<8}")
    
    print()
    print("=" * 100)
    print("🔍 DETAILED COMPARISON - VID")
    print("=" * 100)
    print()
    
    # Get vid's per-round stats
    vid_rounds = c.execute('''
        SELECT 
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
        ORDER BY s.session_date
    ''').fetchall()
    
    if vid_rounds:
        print("Per-Round Breakdown:")
        print(f"{'Map':<20} {'Rnd':<5} {'Session Time':<14} {'Player Time':<13} {'Kills':<7} {'Deaths':<8} {'Damage':<9} {'Parser DPM':<12}")
        print("-" * 100)
        
        total_damage = 0
        total_time = 0
        
        for map_name, rnd, session_time, kills, deaths, damage, player_time, parser_dpm in vid_rounds:
            total_damage += damage
            total_time += player_time if player_time else 0
            
            time_display = f"{player_time:.1f}" if player_time else "0.0"
            print(f"{map_name:<20} {rnd:<5} {session_time:<14} {time_display:<13} {kills:<7} {deaths:<8} {damage:<9} {parser_dpm:<12.2f}")
        
        print("-" * 100)
        print(f"{'TOTALS':<20} {'':<5} {'':<14} {total_time:<13.1f} {'':<7} {'':<8} {total_damage:<9}")
        print()
        
        # Calculate different DPM methods
        bot_avg = c.execute('''
            SELECT AVG(p.dpm)
            FROM player_comprehensive_stats p
            JOIN sessions s ON p.session_id = s.id
            WHERE s.session_date LIKE '2025-10-02%'
            AND p.player_name = 'vid'
        ''').fetchone()[0]
        
        correct_dpm_val = total_damage / total_time if total_time > 0 else 0
        
        print("📊 DPM COMPARISON:")
        print(f"  Bot's AVG(dpm):           {bot_avg:.2f} DPM")
        print(f"  Correct (Total/Total):    {correct_dpm_val:.2f} DPM")
        print(f"  Difference:               {abs(correct_dpm_val - bot_avg):.2f} DPM ({abs(correct_dpm_val - bot_avg) / bot_avg * 100:.1f}%)")
        print()
        
        # Check for records with time = 0
        zero_time = c.execute('''
            SELECT COUNT(*)
            FROM player_comprehensive_stats p
            JOIN sessions s ON p.session_id = s.id
            WHERE s.session_date LIKE '2025-10-02%'
            AND p.player_name = 'vid'
            AND p.time_played_minutes = 0
        ''').fetchone()[0]
        
        total_rounds = len(vid_rounds)
        
        print("⚠️ DATA QUALITY CHECK:")
        print(f"  Total rounds:             {total_rounds}")
        print(f"  Rounds with time = 0:     {zero_time}")
        print(f"  Rounds with time > 0:     {total_rounds - zero_time}")
        
        if zero_time > 0:
            print()
            print(f"  ❌ PROBLEM: {zero_time} rounds have time_played_minutes = 0!")
            print(f"     This is {zero_time / total_rounds * 100:.1f}% of rounds")
            print(f"     This causes the inflated DPM we saw (514.88)")
        else:
            print()
            print(f"  ✅ All rounds have time data!")
    else:
        print("❌ No data found for player 'vid'")
    
    print()
    conn.close()

if __name__ == '__main__':
    show_last_session_summary()
