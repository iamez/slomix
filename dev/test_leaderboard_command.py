#!/usr/bin/env python3
"""Test the leaderboard command logic without Discord"""

import sqlite3


def test_leaderboard(stat_type='kills'):
    """Test leaderboard retrieval"""
    
    conn = sqlite3.connect('etlegacy_production.db')
    cur = conn.cursor()
    
    print(f"\n🏆 Testing leaderboard: {stat_type.upper()}")
    print("="*70)
    
    if stat_type == 'kills':
        query = '''
            SELECT p.player_name,
                   SUM(p.kills) as total_kills,
                   SUM(p.deaths) as total_deaths,
                   COUNT(DISTINCT p.session_id) as games
            FROM player_comprehensive_stats p
            GROUP BY p.player_guid, p.player_name
            HAVING games > 10
            ORDER BY total_kills DESC
            LIMIT 10
        '''
        title = "Top 10 by Kills"
        
    elif stat_type == 'kd':
        query = '''
            SELECT p.player_name,
                   SUM(p.kills) as total_kills,
                   SUM(p.deaths) as total_deaths,
                   COUNT(DISTINCT p.session_id) as games
            FROM player_comprehensive_stats p
            GROUP BY p.player_guid, p.player_name
            HAVING games > 50 AND total_deaths > 0
            ORDER BY (CAST(total_kills AS FLOAT) / total_deaths) DESC
            LIMIT 10
        '''
        title = "Top 10 by K/D Ratio"
        
    elif stat_type == 'dpm':
        query = '''
            SELECT p.player_name,
                   AVG(p.dpm) as avg_dpm,
                   SUM(p.kills) as total_kills,
                   COUNT(DISTINCT p.session_id) as games
            FROM player_comprehensive_stats p
            GROUP BY p.player_guid, p.player_name
            HAVING games > 50
            ORDER BY avg_dpm DESC
            LIMIT 10
        '''
        title = "Top 10 by DPM"
        
    elif stat_type == 'accuracy':
        query = '''
            SELECT p.player_name,
                   SUM(w.hits) as total_hits,
                   SUM(w.shots) as total_shots,
                   SUM(p.kills) as total_kills,
                   COUNT(DISTINCT p.session_id) as games
            FROM player_comprehensive_stats p
            JOIN weapon_comprehensive_stats w 
                ON p.session_id = w.session_id 
                AND p.player_guid = w.player_guid
            GROUP BY p.player_guid, p.player_name
            HAVING games > 50 AND total_shots > 1000
            ORDER BY (CAST(total_hits AS FLOAT) / total_shots) DESC
            LIMIT 10
        '''
        title = "Top 10 by Accuracy"
        
    elif stat_type == 'headshots':
        query = '''
            SELECT p.player_name,
                   SUM(p.headshot_kills) as total_hs,
                   SUM(w.hits) as total_hits,
                   SUM(p.kills) as total_kills,
                   COUNT(DISTINCT p.session_id) as games
            FROM player_comprehensive_stats p
            JOIN weapon_comprehensive_stats w 
                ON p.session_id = w.session_id 
                AND p.player_guid = w.player_guid
            GROUP BY p.player_guid, p.player_name
            HAVING games > 50 AND total_hits > 1000
            ORDER BY (CAST(total_hs AS FLOAT) / total_hits) DESC
            LIMIT 10
        '''
        title = "Top 10 by Headshot %"
    
    results = cur.execute(query).fetchall()
    
    print(f"\n{title}")
    print("-"*70)
    
    medals = ["🥇", "🥈", "🥉", "4.", "5.", "6.", "7.", "8.", "9.", "10."]
    
    for i, row in enumerate(results):
        medal = medals[i]
        name = row[0]
        
        if stat_type == 'kills':
            kills, deaths, games = row[1], row[2], row[3]
            kd = kills / deaths if deaths > 0 else kills
            print(f"{medal:<4} {name:<20} {kills:>6,}K ({kd:>5.2f} K/D, {games:>4} games)")
            
        elif stat_type == 'kd':
            kills, deaths, games = row[1], row[2], row[3]
            kd = kills / deaths if deaths > 0 else kills
            print(f"{medal:<4} {name:<20} {kd:>5.2f} K/D ({kills:>5,}K/{deaths:>5,}D, {games:>4} games)")
            
        elif stat_type == 'dpm':
            avg_dpm, kills, games = row[1], row[2], row[3]
            print(f"{medal:<4} {name:<20} {avg_dpm:>6.1f} DPM ({kills:>5,}K, {games:>4} games)")
            
        elif stat_type == 'accuracy':
            hits, shots, kills, games = row[1], row[2], row[3], row[4]
            acc = (hits / shots * 100) if shots > 0 else 0
            print(f"{medal:<4} {name:<20} {acc:>5.1f}% Acc ({kills:>5,}K, {games:>4} games)")
            
        elif stat_type == 'headshots':
            hs, hits, kills, games = row[1], row[2], row[3], row[4]
            hs_pct = (hs / hits * 100) if hits > 0 else 0
            print(f"{medal:<4} {name:<20} {hs_pct:>5.1f}% HS ({hs:>5,} HS, {games:>4} games)")
    
    print()
    conn.close()


if __name__ == "__main__":
    # Test all leaderboard types
    leaderboard_types = ['kills', 'kd', 'dpm', 'accuracy', 'headshots']
    
    for lb_type in leaderboard_types:
        test_leaderboard(lb_type)
