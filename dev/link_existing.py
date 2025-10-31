#!/usr/bin/env python3
"""
ET:Legacy Discord GUID Linking Script - Working with existing table structure
Links ET:Legacy player GUIDs to Discord user IDs using the existing player_links table
"""
import sys
import sqlite3
from typing import Optional

DATABASE_PATH = 'etlegacy_fixed_bulk.db'

def remove_et_color_codes(name: str) -> str:
    """Remove ET:Legacy color codes from player names"""
    import re
    if not name:
        return ""
    return re.sub(r'\^.', '', name).strip()

def get_database_connection():
    """Get database connection"""
    return sqlite3.connect(DATABASE_PATH)

def get_player_info(guid: str):
    """Get player information by GUID"""
    conn = get_database_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            clean_name_final,
            SUM(kills) as total_kills,
            COUNT(*) as total_rounds
        FROM player_round_stats 
        WHERE player_guid = ? AND player_guid IS NOT NULL
        GROUP BY player_guid
    ''', (guid,))
    
    result = cursor.fetchone()
    conn.close()
    
    return result

def link_guid_discord(guid: str, discord_id: str, discord_name: Optional[str] = None) -> bool:
    """Link an ET GUID to a Discord user ID using existing table structure"""
    # Check if GUID exists in player_round_stats
    player_info = get_player_info(guid)
    
    if not player_info:
        print(f"❌ GUID {guid} not found in database!")
        print("   Player must have played at least one match to be linkable.")
        return False
    
    clean_name, kills, rounds = player_info
    
    conn = get_database_connection()
    cursor = conn.cursor()
    
    try:
        # Check if GUID or Discord ID already linked using existing column names
        cursor.execute('SELECT discord_id, discord_username FROM player_links WHERE et_guid = ?', (guid,))
        existing_guid = cursor.fetchone()
        
        cursor.execute('SELECT et_guid, et_name FROM player_links WHERE discord_id = ?', (discord_id,))
        existing_discord = cursor.fetchone()
        
        if existing_guid:
            print(f"❌ GUID {guid} is already linked to Discord ID: {existing_guid[0]}")
            if existing_guid[1]:
                print(f"   Linked to: {existing_guid[1]}")
            return False
            
        if existing_discord:
            print(f"❌ Discord ID {discord_id} is already linked to GUID: {existing_discord[0]}")
            print(f"   Linked to player: {existing_discord[1]}")
            return False
        
        # Insert new link using existing table structure
        cursor.execute('''
            INSERT INTO player_links (et_guid, discord_id, discord_username, et_name, verified)
            VALUES (?, ?, ?, ?, ?)
        ''', (guid, discord_id, discord_name or "Unknown", clean_name, True))
        
        conn.commit()
        
        print(f"✅ Successfully linked:")
        print(f"   ET Player: {clean_name}")
        print(f"   ET GUID: {guid}")
        print(f"   Stats: {kills:,} kills, {rounds:,} rounds")
        print(f"   Discord ID: {discord_id}")
        if discord_name:
            print(f"   Discord Name: {discord_name}")
        
        return True
        
    except sqlite3.IntegrityError as e:
        print(f"❌ Database error: {e}")
        return False
    finally:
        conn.close()

def unlink_discord(discord_id: str) -> bool:
    """Unlink a Discord user from their ET GUID"""
    conn = get_database_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT et_guid, et_name, discord_username FROM player_links WHERE discord_id = ?', (discord_id,))
    link = cursor.fetchone()
    
    if not link:
        print(f"❌ Discord ID {discord_id} is not linked to any player!")
        return False
    
    et_guid, et_name, discord_name = link
    
    cursor.execute('DELETE FROM player_links WHERE discord_id = ?', (discord_id,))
    conn.commit()
    conn.close()
    
    print(f"✅ Successfully unlinked:")
    print(f"   ET Player: {et_name}")
    print(f"   ET GUID: {et_guid}")
    print(f"   Discord ID: {discord_id}")
    if discord_name:
        print(f"   Discord Name: {discord_name}")
    
    return True

def list_all_players():
    """List all players in the database with their link status"""
    conn = get_database_connection()
    cursor = conn.cursor()
    
    # Get all players
    cursor.execute('''
        SELECT 
            player_guid,
            clean_name_final,
            SUM(kills) as total_kills,
            COUNT(id) as total_rounds
        FROM player_round_stats
        WHERE player_guid IS NOT NULL AND player_guid != ''
        GROUP BY player_guid
        ORDER BY total_kills DESC
    ''')
    
    players = cursor.fetchall()
    
    if not players:
        print("📭 No players found in database yet.")
        conn.close()
        return
    
    # Get linked players using existing table structure
    cursor.execute('SELECT et_guid, discord_id, discord_username, linked_date FROM player_links')
    links = {row[0]: (row[1], row[2], row[3]) for row in cursor.fetchall()}
    
    linked_count = len(links)
    
    print(f"\n📊 PLAYERS DATABASE ({len(players)} unique players):")
    print("="*100)
    print(f"{'Rank':<4} {'ET Name':<20} {'GUID':<10} {'Kills':<8} {'Rounds':<7} {'Discord ID':<18} {'Status':<12} {'Linked'}")
    print("-"*100)
    
    for i, (guid, name, kills, rounds) in enumerate(players, 1):
        if guid in links:
            discord_id, discord_name, linked_at = links[guid]
            status = "✅ LINKED"
            discord_display = discord_id
            linked_display = linked_at[:10] if linked_at else "Unknown"
        else:
            status = "❌ NOT LINKED"
            discord_display = "None"
            linked_display = "Never"
        
        print(f"{i:<4} {name:<20} {guid[:8]+'...':<10} {kills:<8,} {rounds:<7} {discord_display:<18} {status:<12} {linked_display}")
    
    print("-"*100)
    if len(players) > 0:
        print(f"📈 Summary: {linked_count}/{len(players)} players linked to Discord ({linked_count/len(players)*100:.1f}%)")
    
    conn.close()

def find_player(search_term: str):
    """Find players by name or GUID"""
    conn = get_database_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            ps.player_guid,
            ps.clean_name_final,
            SUM(ps.kills) as total_kills,
            COUNT(ps.id) as total_rounds,
            ROUND(AVG(ps.kd_ratio), 2) as avg_kd
        FROM player_round_stats ps
        WHERE (ps.clean_name_final LIKE ? OR ps.player_guid LIKE ?)
          AND ps.player_guid IS NOT NULL
        GROUP BY ps.player_guid
        ORDER BY total_kills DESC
    ''', (f'%{search_term}%', f'%{search_term}%'))
    
    players = cursor.fetchall()
    
    if not players:
        print(f"❌ No players found matching '{search_term}'")
        conn.close()
        return
    
    # Get linked status
    cursor.execute('SELECT et_guid, discord_id, discord_username FROM player_links')
    links = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
    
    print(f"\n🔍 SEARCH RESULTS for '{search_term}':")
    print("="*80)
    
    for guid, name, kills, rounds, kd in players:
        status = "✅ LINKED" if guid in links else "❌ NOT LINKED"
        
        print(f"Name: {name}")
        print(f"GUID: {guid}")
        print(f"Stats: {kills:,} kills, {rounds:,} rounds, {kd:.2f} K/D")
        
        if guid in links:
            discord_id, discord_name = links[guid]
            print(f"Discord: {discord_id} ({discord_name}) {status}")
        else:
            print(f"Discord: Not linked {status}")
        print("-"*60)
    
    conn.close()

def get_linked_players():
    """Get all linked players for bot integration"""
    conn = get_database_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            pl.et_guid,
            pl.discord_id,
            pl.discord_username,
            pl.et_name,
            ps.total_kills,
            ps.total_rounds
        FROM player_links pl
        JOIN (
            SELECT 
                player_guid,
                SUM(kills) as total_kills,
                COUNT(*) as total_rounds
            FROM player_round_stats
            WHERE player_guid IS NOT NULL
            GROUP BY player_guid
        ) ps ON pl.et_guid = ps.player_guid
        ORDER BY ps.total_kills DESC
    ''')
    
    results = cursor.fetchall()
    conn.close()
    
    if not results:
        print("📭 No linked players found.")
        return []
    
    print(f"\n🔗 LINKED PLAYERS ({len(results)} players):")
    print("="*80)
    
    for guid, discord_id, discord_name, et_name, kills, rounds in results:
        print(f"ET: {et_name:<18} | Discord: {discord_name or discord_id:<20} | {kills:,} kills")
    
    return results

def print_usage():
    print("""
🔗 ET:Legacy Discord GUID Linking Tool (Compatible with existing table)

USAGE:
    python link_existing.py link <guid> <discord_id> [discord_name]
    python link_existing.py unlink <discord_id>
    python link_existing.py list
    python link_existing.py find <search_term>
    python link_existing.py linked

EXAMPLES:
    # Link player GUID to Discord user
    python link_existing.py link EDBB5DA9 123456789012345678 "PlayerName#1234"
    
    # Unlink Discord user
    python link_existing.py unlink 123456789012345678
    
    # List all players with link status
    python link_existing.py list
    
    # Find player by name
    python link_existing.py find "SuperBoyy"
    python link_existing.py find "EDBB5DA9"
    
    # Show only linked players
    python link_existing.py linked

NOTES:
    - Works with existing player_links table structure
    - Uses clean player names (color codes removed)
    - Players must appear in match data before linking
    - Discord IDs are 18-digit numbers (right-click user → Copy ID)
    - Enable Developer Mode in Discord to see Copy ID option
    """)

def main():
    if len(sys.argv) < 2:
        print_usage()
        return
    
    command = sys.argv[1].lower()
    
    if command == "link":
        if len(sys.argv) < 4:
            print("❌ Usage: python link_existing.py link <guid> <discord_id> [discord_name]")
            return
        guid = sys.argv[2]
        discord_id = sys.argv[3]
        discord_name = sys.argv[4] if len(sys.argv) > 4 else None
        link_guid_discord(guid, discord_id, discord_name)
        
    elif command == "unlink":
        if len(sys.argv) < 3:
            print("❌ Usage: python link_existing.py unlink <discord_id>")
            return
        discord_id = sys.argv[2]
        unlink_discord(discord_id)
        
    elif command == "list":
        list_all_players()
        
    elif command == "find":
        if len(sys.argv) < 3:
            print("❌ Usage: python link_existing.py find <search_term>")
            return
        search_term = sys.argv[2]
        find_player(search_term)
        
    elif command == "linked":
        get_linked_players()
        
    else:
        print(f"❌ Unknown command: {command}")
        print_usage()

if __name__ == "__main__":
    main()