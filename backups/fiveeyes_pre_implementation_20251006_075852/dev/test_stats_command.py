#!/usr/bin/env python3
"""Test the stats command logic without Discord"""

import sqlite3
from datetime import datetime

def test_stats_command(player_name):
    """Test stats retrieval for a player"""
    
    conn = sqlite3.connect('etlegacy_production.db')
    cur = conn.cursor()
    
    print(f"\n🔍 Testing stats for: {player_name}")
    print("="*70)
    
    # Search for player
    result = cur.execute('''
        SELECT player_guid, player_name FROM player_links 
        WHERE LOWER(player_name) = LOWER(?)
        LIMIT 1
    ''', (player_name,)).fetchone()
    
    if result:
        player_guid, primary_name = result
        print(f"✅ Found in player_links: {primary_name} (GUID: {player_guid})")
    else:
        result = cur.execute('''
            SELECT player_guid, player_name 
            FROM player_comprehensive_stats
            WHERE LOWER(player_name) LIKE LOWER(?)
            GROUP BY player_guid
            LIMIT 1
        ''', (f'%{player_name}%',)).fetchone()
        
        if not result:
            print(f"❌ Player '{player_name}' not found")
            conn.close()
            return
        
        player_guid, primary_name = result
        print(f"✅ Found in stats: {primary_name} (GUID: {player_guid})")
    
    # Get overall stats
    overall = cur.execute('''
        SELECT 
            COUNT(DISTINCT session_id) as total_games,
            SUM(kills) as total_kills,
            SUM(deaths) as total_deaths,
            SUM(damage_given) as total_damage,
            SUM(damage_received) as total_damage_received,
            SUM(headshot_kills) as total_headshots,
            AVG(dpm) as avg_dpm,
            AVG(kd_ratio) as avg_kd
        FROM player_comprehensive_stats
        WHERE player_guid = ?
    ''', (player_guid,)).fetchone()
    
    # Get weapon stats
    weapon_overall = cur.execute('''
        SELECT 
            SUM(w.hits) as total_hits,
            SUM(w.shots) as total_shots,
            SUM(w.headshots) as total_hs
        FROM weapon_comprehensive_stats w
        WHERE w.player_guid = ?
    ''', (player_guid,)).fetchone()
    
    # Get favorite weapons
    fav_weapons = cur.execute('''
        SELECT weapon_name, SUM(kills) as total_kills
        FROM weapon_comprehensive_stats
        WHERE player_guid = ?
        GROUP BY weapon_name
        ORDER BY total_kills DESC
        LIMIT 3
    ''', (player_guid,)).fetchall()
    
    # Get recent activity
    recent = cur.execute('''
        SELECT s.session_date, s.map_name, p.kills, p.deaths
        FROM player_comprehensive_stats p
        JOIN sessions s ON p.session_id = s.id
        WHERE p.player_guid = ?
        ORDER BY s.session_date DESC
        LIMIT 3
    ''', (player_guid,)).fetchall()
    
    # Get special flag
    flag_result = cur.execute('''
        SELECT special_flag FROM player_links 
        WHERE player_guid = ?
    ''', (player_guid,)).fetchone()
    special_flag = flag_result[0] if flag_result and flag_result[0] else ""
    
    # Calculate stats
    games, kills, deaths, dmg, dmg_recv, hs, avg_dpm, avg_kd = overall
    hits, shots, hs_weapon = weapon_overall if weapon_overall else (0, 0, 0)
    
    kd_ratio = kills / deaths if deaths > 0 else kills
    accuracy = (hits / shots * 100) if shots > 0 else 0
    hs_pct = (hs / hits * 100) if hits > 0 else 0
    
    # Display results
    print(f"\n📊 STATS FOR {primary_name} {special_flag}")
    print("="*70)
    
    print(f"\n🎮 OVERVIEW")
    print(f"  Games Played: {games:,}")
    print(f"  K/D Ratio: {kd_ratio:.2f}")
    print(f"  Avg DPM: {avg_dpm:.1f}" if avg_dpm else "  Avg DPM: 0.0")
    
    print(f"\n⚔️ COMBAT")
    print(f"  Kills: {kills:,}")
    print(f"  Deaths: {deaths:,}")
    print(f"  Headshots: {hs:,} ({hs_pct:.1f}%)")
    
    print(f"\n🎯 ACCURACY")
    print(f"  Overall: {accuracy:.1f}%")
    print(f"  Damage Given: {dmg:,}")
    print(f"  Damage Taken: {dmg_recv:,}")
    
    if fav_weapons:
        print(f"\n🔫 FAVORITE WEAPONS")
        for weapon, weapon_kills in fav_weapons:
            weapon_display = weapon.replace('WS_', '').title()
            print(f"  {weapon_display}: {weapon_kills:,} kills")
    
    if recent:
        print(f"\n📅 RECENT MATCHES")
        for date, map_name, r_kills, r_deaths in recent:
            print(f"  {date} {map_name} - {r_kills}K/{r_deaths}D")
    
    print(f"\nGUID: {player_guid}\n")
    conn.close()


if __name__ == "__main__":
    # Test with some players
    test_players = ["bronze", "vid", "Lagger", "seareal", "superboyy"]
    
    for player in test_players:
        test_stats_command(player)
        print()
