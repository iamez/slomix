#!/usr/bin/env python3
"""
Analyze player aliases and identify duplicate/similar names
Helps consolidate player identities for accurate stats
"""

import sqlite3
from collections import defaultdict
import re

def strip_color_codes(name):
    """Remove ET color codes from player name"""
    return re.sub(r'\^[0-9a-zA-Z]', '', name)

def get_all_players():
    """Get all unique players from database"""
    conn = sqlite3.connect('etlegacy_production.db')
    cur = conn.cursor()
    
    # Get all unique GUID + name combinations with stats
    players = cur.execute('''
        SELECT 
            player_guid,
            player_name,
            clean_name,
            COUNT(*) as games_played,
            SUM(kills) as total_kills,
            SUM(deaths) as total_deaths,
            MIN(created_at) as first_seen,
            MAX(created_at) as last_seen
        FROM player_comprehensive_stats
        GROUP BY player_guid, clean_name
        ORDER BY player_guid, games_played DESC
    ''').fetchall()
    
    conn.close()
    return players

def analyze_aliases():
    """Analyze and group player aliases"""
    
    print("\n" + "="*80)
    print("  PLAYER ALIAS ANALYSIS - Manual Matching Required")
    print("="*80 + "\n")
    
    players = get_all_players()
    
    # Group by GUID
    guid_groups = defaultdict(list)
    for player in players:
        guid, name, clean, games, kills, deaths, first, last = player
        guid_groups[guid].append({
            'name': name,
            'clean': clean,
            'games': games,
            'kills': kills,
            'deaths': deaths,
            'first_seen': first,
            'last_seen': last
        })
    
    print(f"📊 Total Unique GUIDs: {len(guid_groups)}")
    print(f"📊 Total Name Variations: {len(players)}\n")
    
    # Find GUIDs with multiple names
    print("="*80)
    print("👥 PLAYERS WITH MULTIPLE NAMES (Same GUID, Different Names)")
    print("="*80 + "\n")
    
    multi_name_count = 0
    for guid, names in sorted(guid_groups.items(), key=lambda x: len(x[1]), reverse=True):
        if len(names) > 1:
            multi_name_count += 1
            total_games = sum(n['games'] for n in names)
            total_kills = sum(n['kills'] for n in names)
            
            print(f"GUID: {guid} ({len(names)} names, {total_games} games, {total_kills:,} kills)")
            print("-" * 80)
            
            for i, alias in enumerate(names, 1):
                kd = f"{alias['kills']}/{alias['deaths']}"
                print(f"  {i}. {alias['clean']:<30} "
                      f"{alias['games']:>4} games  "
                      f"{kd:>10}  "
                      f"Last: {alias['last_seen'][:10]}")
            print()
    
    if multi_name_count == 0:
        print("✅ No players with multiple names found!\n")
    else:
        print(f"Found {multi_name_count} players with multiple names\n")
    
    # Find similar names (possible duplicates)
    print("="*80)
    print("🔍 SIMILAR NAMES (Different GUIDs, Similar Names)")
    print("="*80 + "\n")
    
    # Group by clean name similarity
    name_groups = defaultdict(list)
    for guid, names in guid_groups.items():
        # Use the most played name
        primary_name = max(names, key=lambda x: x['games'])
        base_name = primary_name['clean'].lower().strip()
        # Remove common variations
        base_name = base_name.replace('.', '').replace('_', '').replace('-', '')
        
        name_groups[base_name].append({
            'guid': guid,
            'display_name': primary_name['clean'],
            'total_games': sum(n['games'] for n in names),
            'total_kills': sum(n['kills'] for n in names),
            'aliases': [n['clean'] for n in names]
        })
    
    # Find groups with multiple GUIDs
    similar_count = 0
    for base_name, players in sorted(name_groups.items(), key=lambda x: len(x[1]), reverse=True):
        if len(players) > 1:
            similar_count += 1
            print(f"Similar to: '{base_name}'")
            print("-" * 80)
            
            for player in players:
                print(f"  GUID: {player['guid']}")
                print(f"    Names: {', '.join(player['aliases'])}")
                print(f"    Stats: {player['total_games']} games, {player['total_kills']:,} kills")
                print()
            print()
    
    if similar_count == 0:
        print("✅ No similar names found!\n")
    else:
        print(f"Found {similar_count} groups of similar names\n")
    
    # Top 50 players by games played
    print("="*80)
    print("🏆 TOP 50 PLAYERS (By Games Played)")
    print("="*80 + "\n")
    print(f"{'Rank':<6} {'GUID':<10} {'Primary Name':<25} {'Games':<8} {'Kills':<10} {'Aliases':<20}")
    print("-" * 80)
    
    # Sort by total games
    top_players = []
    for guid, names in guid_groups.items():
        total_games = sum(n['games'] for n in names)
        total_kills = sum(n['kills'] for n in names)
        primary = max(names, key=lambda x: x['games'])
        aliases = [n['clean'] for n in names if n['clean'] != primary['clean']]
        
        top_players.append({
            'guid': guid,
            'name': primary['clean'],
            'games': total_games,
            'kills': total_kills,
            'aliases': aliases
        })
    
    top_players.sort(key=lambda x: x['games'], reverse=True)
    
    for i, player in enumerate(top_players[:50], 1):
        alias_str = f"+{len(player['aliases'])}" if player['aliases'] else ""
        print(f"{i:<6} {player['guid']:<10} {player['name']:<25} "
              f"{player['games']:<8} {player['kills']:<10,} {alias_str:<20}")
    
    print("\n" + "="*80)
    print("✅ Analysis Complete")
    print("="*80 + "\n")
    
    print("NEXT STEPS:")
    print("1. Review players with multiple names (same GUID)")
    print("2. Identify players with similar names (different GUIDs)")
    print("3. Manually match duplicate players")
    print("4. Create GUID merge list for consolidation\n")

if __name__ == "__main__":
    analyze_aliases()
