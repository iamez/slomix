#!/usr/bin/env python3
"""
ET:Legacy Database Analysis - Unlinked Players & GUID Duplicates
Helps identify players for better Discord linking
"""
import sqlite3
import re
from collections import defaultdict

def remove_et_color_codes(name: str) -> str:
    """Remove ET:Legacy color codes from player names"""
    if not name:
        return ""
    return re.sub(r'\^.', '', name).strip()

def analyze_unlinked_players():
    """Show all unlinked players sorted by kills"""
    conn = sqlite3.connect('etlegacy_fixed_bulk.db')
    cursor = conn.cursor()
    
    print("🔍 UNLINKED PLAYERS ANALYSIS")
    print("="*80)
    
    # Get all players with their stats
    cursor.execute('''
        SELECT 
            ps.player_guid,
            ps.clean_name_final,
            SUM(ps.kills) as total_kills,
            COUNT(ps.id) as total_rounds,
            ROUND(AVG(ps.kd_ratio), 2) as avg_kd,
            MAX(ps.processed_at) as last_seen
        FROM player_round_stats ps
        LEFT JOIN player_links pl ON ps.player_guid = pl.et_guid
        WHERE ps.player_guid IS NOT NULL 
          AND pl.et_guid IS NULL  -- Not linked
        GROUP BY ps.player_guid
        ORDER BY total_kills DESC
    ''')
    
    unlinked_players = cursor.fetchall()
    
    print(f"📊 Found {len(unlinked_players)} unlinked players")
    print("\nTop Unlinked Players (by kills):")
    print("-"*80)
    print(f"{'Rank':<4} {'Name':<20} {'GUID':<10} {'Kills':<8} {'Rounds':<7} {'K/D':<6} {'Last Seen'}")
    print("-"*80)
    
    for i, (guid, name, kills, rounds, kd, last_seen) in enumerate(unlinked_players[:20], 1):
        last_date = last_seen[:10] if last_seen else "Unknown"
        print(f"{i:<4} {name:<20} {guid[:8]+'...':<10} {kills:<8,} {rounds:<7} {kd:<6.2f} {last_date}")
    
    if len(unlinked_players) > 20:
        print(f"\n... and {len(unlinked_players) - 20} more unlinked players")
    
    conn.close()
    return unlinked_players

def analyze_duplicate_guids():
    """Identify players with multiple GUIDs (same clean name, different GUIDs)"""
    conn = sqlite3.connect('etlegacy_fixed_bulk.db')
    cursor = conn.cursor()
    
    print("\n\n👥 POTENTIAL DUPLICATE PLAYERS (Multiple GUIDs)")
    print("="*80)
    
    # Get all players with their clean names
    cursor.execute('''
        SELECT 
            player_guid,
            clean_name_final,
            SUM(kills) as total_kills,
            COUNT(id) as total_rounds,
            MIN(processed_at) as first_seen,
            MAX(processed_at) as last_seen
        FROM player_round_stats
        WHERE player_guid IS NOT NULL AND clean_name_final IS NOT NULL
        GROUP BY player_guid, clean_name_final
        ORDER BY clean_name_final, total_kills DESC
    ''')
    
    all_players = cursor.fetchall()
    
    # Group by clean name to find duplicates
    name_groups = defaultdict(list)
    for player_data in all_players:
        guid, name, kills, rounds, first_seen, last_seen = player_data
        name_groups[name].append((guid, kills, rounds, first_seen, last_seen))
    
    # Find names with multiple GUIDs
    duplicates = {name: guids for name, guids in name_groups.items() if len(guids) > 1}
    
    if not duplicates:
        print("✅ No duplicate GUIDs found - all players have unique GUID/name combinations")
        conn.close()
        return
    
    print(f"📊 Found {len(duplicates)} players with multiple GUIDs:")
    print()
    
    for name, guid_list in sorted(duplicates.items(), key=lambda x: sum(g[1] for g in x[1]), reverse=True):
        total_kills = sum(g[1] for g in guid_list)
        total_rounds = sum(g[2] for g in guid_list)
        
        print(f"🎮 PLAYER: {name}")
        print(f"   Total across all GUIDs: {total_kills:,} kills, {total_rounds:,} rounds")
        print("   GUID Details:")
        
        # Check if any GUIDs are linked
        linked_guids = []
        for guid, kills, rounds, first_seen, last_seen in guid_list:
            cursor.execute('SELECT discord_username FROM player_links WHERE et_guid = ?', (guid,))
            link = cursor.fetchone()
            linked_status = f" → LINKED to {link[0]}" if link else " → NOT LINKED"
            linked_guids.append((guid, linked_status))
            
            first_date = first_seen[:10] if first_seen else "Unknown"
            last_date = last_seen[:10] if last_seen else "Unknown"
            
            print(f"     • {guid}: {kills:,} kills, {rounds:,} rounds ({first_date} to {last_date}){linked_status}")
        
        # Show linking recommendation
        if any("LINKED" in status for _, status in linked_guids):
            print("   💡 Some GUIDs already linked - consider consolidating")
        else:
            print("   💡 No GUIDs linked - good candidate for linking")
        print()
    
    conn.close()

def analyze_similar_names():
    """Find players with very similar names (might be same person)"""
    conn = sqlite3.connect('etlegacy_fixed_bulk.db')
    cursor = conn.cursor()
    
    print("\n\n🔤 SIMILAR NAME ANALYSIS")
    print("="*80)
    
    # Get all unique clean names with their stats
    cursor.execute('''
        SELECT 
            clean_name_final,
            COUNT(DISTINCT player_guid) as guid_count,
            SUM(kills) as total_kills,
            COUNT(id) as total_rounds
        FROM player_round_stats
        WHERE clean_name_final IS NOT NULL
        GROUP BY clean_name_final
        HAVING guid_count > 1 OR total_kills > 500
        ORDER BY total_kills DESC
    ''')
    
    name_stats = cursor.fetchall()
    
    # Group similar names
    similar_groups = []
    processed_names = set()
    
    for name1, guid_count1, kills1, rounds1 in name_stats:
        if name1 in processed_names:
            continue
            
        similar_names = [(name1, guid_count1, kills1, rounds1)]
        processed_names.add(name1)
        
        # Find similar names
        for name2, guid_count2, kills2, rounds2 in name_stats:
            if name2 != name1 and name2 not in processed_names:
                # Check similarity (basic fuzzy matching)
                if (name1.lower() in name2.lower() or name2.lower() in name1.lower() or
                    name1.replace('.', '') == name2.replace('.', '') or
                    name1.replace(' ', '') == name2.replace(' ', '')):
                    similar_names.append((name2, guid_count2, kills2, rounds2))
                    processed_names.add(name2)
        
        if len(similar_names) > 1:
            similar_groups.append(similar_names)
    
    if similar_groups:
        print(f"📊 Found {len(similar_groups)} groups of similar names:")
        print()
        
        for group in similar_groups:
            print("🔍 Similar Names Group:")
            total_group_kills = sum(kills for _, _, kills, _ in group)
            for name, guid_count, kills, rounds in group:
                print(f"   • {name:<20} | {guid_count} GUID(s) | {kills:,} kills | {rounds:,} rounds")
            print(f"   Group Total: {total_group_kills:,} kills")
            print()
    else:
        print("✅ No obviously similar names found")
    
    conn.close()

def show_linking_recommendations():
    """Provide recommendations for linking players"""
    conn = sqlite3.connect('etlegacy_fixed_bulk.db')
    cursor = conn.cursor()
    
    print("\n\n💡 LINKING RECOMMENDATIONS")
    print("="*80)
    
    # High-value unlinked players
    cursor.execute('''
        SELECT 
            ps.player_guid,
            ps.clean_name_final,
            SUM(ps.kills) as total_kills,
            COUNT(ps.id) as total_rounds
        FROM player_round_stats ps
        LEFT JOIN player_links pl ON ps.player_guid = pl.et_guid
        WHERE ps.player_guid IS NOT NULL 
          AND pl.et_guid IS NULL
          AND ps.clean_name_final IS NOT NULL
        GROUP BY ps.player_guid
        HAVING total_kills >= 1000  -- High-activity players
        ORDER BY total_kills DESC
        LIMIT 10
    ''')
    
    high_value_unlinked = cursor.fetchall()
    
    print("🎯 HIGH-PRIORITY LINKING CANDIDATES (1000+ kills):")
    print("   These players should be prioritized for Discord linking")
    print()
    
    for guid, name, kills, rounds in high_value_unlinked:
        print(f"   • {name:<20} | GUID: {guid} | {kills:,} kills | {rounds:,} rounds")
        print(f"     Command: python link_existing.py link {guid} <discord_id> \"{name}#0000\"")
        print()
    
    if not high_value_unlinked:
        print("✅ All high-activity players (1000+ kills) are already linked!")
    
    conn.close()

def main():
    print("🎮 ET:Legacy Player Linking Analysis")
    print("="*50)
    
    # Analyze unlinked players
    unlinked = analyze_unlinked_players()
    
    # Analyze potential duplicates
    analyze_duplicate_guids()
    
    # Analyze similar names
    analyze_similar_names()
    
    # Show recommendations
    show_linking_recommendations()
    
    print("\n" + "="*80)
    print("📋 SUMMARY:")
    print(f"   • Total unlinked players analyzed")
    print("   • Potential duplicate GUID situations identified")
    print("   • Similar name groups found")
    print("   • High-priority linking candidates listed")
    print("\n💡 Use the provided commands to link high-value players to Discord")

if __name__ == "__main__":
    main()