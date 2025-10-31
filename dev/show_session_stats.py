#!/usr/bin/env python3
"""
Show detailed stats for a specific session date
Usage: python dev/show_session_stats.py 2025-09-30
"""

import sqlite3
import sys
from datetime import datetime

def show_session_stats(date_filter):
    """Display detailed session statistics"""
    
    conn = sqlite3.connect('etlegacy_production.db')
    cur = conn.cursor()
    
    print(f"\n{'='*70}")
    print(f"  SESSIONS ON {date_filter}")
    print(f"{'='*70}\n")
    
    # Get all sessions for the date
    sessions = cur.execute('''
        SELECT id, session_date, map_name, round_number, time_limit, actual_time
        FROM sessions
        WHERE session_date LIKE ?
        ORDER BY session_date DESC
    ''', (f'{date_filter}%',)).fetchall()
    
    if not sessions:
        print(f"❌ No sessions found for date: {date_filter}")
        conn.close()
        return
    
    print(f"Found {len(sessions)} session(s):\n")
    
    for session in sessions:
        session_id, date, map_name, round_num, time_limit, actual_time = session
        
        print(f"{'='*70}")
        print(f"📍 SESSION #{session_id}: {map_name} - Round {round_num}")
        print(f"{'='*70}")
        print(f"📅 Date: {date}")
        print(f"⏱️  Time Limit: {time_limit}")
        print(f"⌛ Actual Duration: {actual_time}")
        
        # Get player count
        player_count = cur.execute('''
            SELECT COUNT(*) FROM player_comprehensive_stats
            WHERE session_id = ?
        ''', (session_id,)).fetchone()[0]
        
        print(f"👥 Players: {player_count}")
        
        # Get top 5 players with accuracy stats
        top_players = cur.execute('''
            SELECT p.player_name, p.kills, p.deaths, p.damage_given, 
                   p.kd_ratio, p.dpm, p.headshot_kills,
                   SUM(w.hits) as total_hits, SUM(w.shots) as total_shots
            FROM player_comprehensive_stats p
            LEFT JOIN weapon_comprehensive_stats w 
                ON p.session_id = w.session_id AND p.player_guid = w.player_guid
            WHERE p.session_id = ?
            GROUP BY p.player_name, p.kills, p.deaths, p.damage_given,
                     p.kd_ratio, p.dpm, p.headshot_kills
            ORDER BY p.kills DESC
            LIMIT 5
        ''', (session_id,)).fetchall()
        
        print("\n🏆 Top 5 Players (by kills):")
        print(f"{'Rank':<6} {'Player':<20} {'K/D':<12} {'DPM':<8} "
              f"{'Acc%':<8} {'HS':<6} {'HS%':<6}")
        print(f"{'-'*70}")
        
        for i, (name, kills, deaths, dmg, kd, dpm, hs, 
                hits, shots) in enumerate(top_players, 1):
            kd_str = f"{kills}/{deaths}"
            dpm_str = f"{dpm:.1f}" if dpm else "0.0"
            acc_pct = f"{(hits/shots*100):.1f}%" if shots > 0 else "N/A"
            hs_pct = f"{(hs/hits*100):.1f}%" if hits > 0 else "0%"
            
            medal = ("🥇" if i == 1 else "🥈" if i == 2 else 
                    "🥉" if i == 3 else f"{i}.")
            print(f"{medal:<6} {name:<20} {kd_str:<12} {dpm_str:<8} "
                  f"{acc_pct:<8} {hs:<6} {hs_pct:<6}")
        
        # Get weapon category accuracy
        weapon_cats = cur.execute('''
            SELECT 
                CASE 
                    WHEN weapon_name IN ('WS_THOMPSON', 'WS_MP40', 'WS_STEN', 
                                         'WS_PPSH') THEN 'SMGs'
                    WHEN weapon_name IN ('WS_LUGER', 'WS_COLT', 'WS_SILENCER', 
                                         'WS_AKIMBO_COLT', 'WS_AKIMBO_LUGER') 
                                         THEN 'Pistols'
                    WHEN weapon_name IN ('WS_GARAND', 'WS_K43', 'WS_FG42', 
                                         'WS_CARBINE', 'WS_KAR98') THEN 'Rifles'
                    ELSE 'Other'
                END as category,
                SUM(kills) as total_kills,
                SUM(hits) as total_hits,
                SUM(shots) as total_shots,
                SUM(headshots) as total_headshots
            FROM weapon_comprehensive_stats
            WHERE session_id = ?
            GROUP BY category
            HAVING category IN ('SMGs', 'Pistols', 'Rifles')
            ORDER BY total_kills DESC
        ''', (session_id,)).fetchall()
        
        if weapon_cats:
            print("\n📊 Weapon Category Accuracy:")
            print(f"   {'Category':<12} {'Kills':<8} {'Acc%':<8} "
                  f"{'HS':<6} {'HS%':<6}")
            print(f"   {'-'*45}")
            for cat, kills, hits, shots, hs in weapon_cats:
                acc = f"{(hits/shots*100):.1f}%" if shots > 0 else "N/A"
                hs_pct = f"{(hs/hits*100):.1f}%" if hits > 0 else "0%"
                print(f"   {cat:<12} {kills:<8} {acc:<8} {hs:<6} {hs_pct:<6}")
        
        # Get top 5 individual weapons
        weapon_stats = cur.execute('''
            SELECT weapon_name,
                   SUM(kills) as total_kills,
                   SUM(hits) as total_hits,
                   SUM(shots) as total_shots,
                   SUM(headshots) as total_headshots
            FROM weapon_comprehensive_stats
            WHERE session_id = ?
            GROUP BY weapon_name
            ORDER BY total_kills DESC
            LIMIT 5
        ''', (session_id,)).fetchall()
        
        if weapon_stats:
            print("\n🔫 Top 5 Individual Weapons:")
            print(f"   {'Weapon':<20} {'Kills':<8} {'Acc%':<8} "
                  f"{'HS':<6} {'HS%':<6}")
            print(f"   {'-'*50}")
            for weapon, kills, hits, shots, hs in weapon_stats:
                weapon_display = weapon.replace('WS_', '').title()
                acc = f"{(hits/shots*100):.1f}%" if shots > 0 else "N/A"
                hs_pct = f"{(hs/hits*100):.1f}%" if hits > 0 else "0%"
                print(f"   {weapon_display:<20} {kills:<8} {acc:<8} "
                      f"{hs:<6} {hs_pct:<6}")
        
        # Get team stats if available
        team_stats = cur.execute('''
            SELECT team, SUM(kills) as total_kills, SUM(deaths) as total_deaths,
                   SUM(damage_given) as total_damage
            FROM player_comprehensive_stats
            WHERE session_id = ?
            GROUP BY team
        ''', (session_id,)).fetchall()
        
        if len(team_stats) > 1:
            print("\n⚔️  Team Statistics:")
            for team, kills, deaths, damage in team_stats:
                if team == 1:
                    team_name = "Axis"
                elif team == 2:
                    team_name = "Allies"
                else:
                    team_name = f"Team {team}"
                print(f"   {team_name:<10} {kills:>4}K / {deaths:>4}D "
                      f"({damage:>8,} dmg)")
        
        print()
    
    # Show overall summary for all sessions
    if len(sessions) > 1:
        print(f"{'='*70}")
        print(f"📊 OVERALL SUMMARY ({len(sessions)} sessions)")
        print(f"{'='*70}")
        
        # Get accuracy stats for overall summary
        overall_top_acc = cur.execute('''
            SELECT p.player_name,
                   SUM(p.kills) as total_kills,
                   SUM(p.deaths) as total_deaths,
                   SUM(p.damage_given) as total_damage,
                   AVG(p.dpm) as avg_dpm,
                   SUM(p.headshot_kills) as total_headshots,
                   SUM(w.hits) as total_hits,
                   SUM(w.shots) as total_shots
            FROM player_comprehensive_stats p
            LEFT JOIN weapon_comprehensive_stats w
                ON p.session_id = w.session_id AND p.player_guid = w.player_guid
            WHERE p.session_id IN ({})
            GROUP BY p.player_name
            ORDER BY total_kills DESC
            LIMIT 10
        '''.format(','.join('?' * len(sessions))),
                                   [s[0] for s in sessions]).fetchall()
        
        print("\n🏆 Top 10 Players Across All Sessions:")
        print(f"{'Rank':<6} {'Player':<20} {'K/D':<12} {'DPM':<8} "
              f"{'Acc%':<8} {'HS%':<8}")
        print(f"{'-'*70}")
        
        for i, (name, kills, deaths, dmg, dpm, hs,
                hits, shots) in enumerate(overall_top_acc, 1):
            kd = f"{kills}/{deaths}"
            dpm_str = f"{dpm:.1f}" if dpm else "0.0"
            acc_pct = f"{(hits/shots*100):.1f}%" if shots > 0 else "N/A"
            hs_pct = f"{(hs/hits*100):.1f}%" if hits > 0 else "0%"
            
            medal = ("🥇" if i == 1 else "🥈" if i == 2 else
                    "🥉" if i == 3 else f"{i}.")
            print(f"{medal:<6} {name:<20} {kd:<12} {dpm_str:<8} "
                  f"{acc_pct:<8} {hs_pct:<8}")
        
        print()
    
    conn.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        date = sys.argv[1]
    else:
        date = "2025-09-30"
    
    show_session_stats(date)
