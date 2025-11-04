#!/usr/bin/env python3
"""
Discord User Linking Script for Comprehensive Database
Links Discord IDs to player GUIDs for @mention support in Discord commands
"""

import sqlite3
import re

# Discord user mappings provided by user
DISCORD_MAPPINGS = {
    "Lagger": "232574066471600128",
    "illy-ya": "414541532071460874", 
    "seareal": "231165917604741121",  # admin/dev/Ciril
    "m1ke": "335371284085211137",
    "Mravac": "1176115498245697610",
    "vid": "509737538555084810",
    "Dudl": "466585387481956352",
    "rakun": "149266139237711872",
    "twix": "806972265120006215", 
    "alive": "1375773960838578217",
    "Andrei": "1202739906116460608",
    "blauss": "365206423983882260",
    "bronze": "270501528295440385",
    "c0ld": "301726273737064451",
    "c0rn": "482858023447035914",
    "carniee": "121791571468353536",
    "endekk": "636289171962462221",
    "epistola": "347452411410907139",
    "imbecil": "1307780276214173840",
    "immo": "505683365589155855",
    "inert": "319535122594529280",
    "ipkiss": "520934861197017089",
    "janez": "287251032801804289",
    "japonc": "401525753906462722",
    "connor": "1293342207381737573",
    "jype": "647957012994326528",
    "kani": "1276520122302861475",
    "miha": "630842677658910741",
    "mato": "691704574045716500",
    "on3md": "849001562931068979",
    "opti": "130044471214735360",
    "overdoze": "690971690661970050",
    "squaze": "520553260185288725",
    "superboyy": "174638677505343490",
    "vector": "153497212452601856",
    "wajs": "538087838223433728",
    "xi": "384709855774244864",
    "zebra": "688065923839688794"
}

def clean_player_name(name):
    """Clean player names for better matching"""
    if not name:
        return ""
    # Remove ET color codes and extra spaces
    cleaned = re.sub(r'\^.', '', name).strip().lower()
    return cleaned

def find_matching_players():
    """Find players in database that match Discord user names"""
    
    db_path = "dev/etlegacy_comprehensive.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("🔍 FINDING PLAYER MATCHES FOR DISCORD LINKING")
    print("=" * 70)
    
    # Get all players from database
    cursor.execute('''
        SELECT DISTINCT player_guid, clean_name, player_name
        FROM player_comprehensive_stats 
        ORDER BY clean_name
    ''')
    
    db_players = cursor.fetchall()
    
    print(f"📊 Found {len(db_players)} unique players in database:")
    for guid, clean_name, original_name in db_players:
        print(f"   {clean_name:<15} {original_name:<15} {guid}")
    
    print(f"\n🎮 Discord users to link: {len(DISCORD_MAPPINGS)}")
    
    # Try to match Discord names to database players
    matches = []
    unmatched_discord = []
    unmatched_db = list(db_players)
    
    for discord_name, discord_id in DISCORD_MAPPINGS.items():
        discord_clean = clean_player_name(discord_name)
        
        # Look for exact or partial matches
        best_match = None
        match_score = 0
        
        for guid, db_clean, db_original in db_players:
            db_name_clean = clean_player_name(db_clean)
            
            # Exact match
            if discord_clean == db_name_clean:
                best_match = (guid, db_clean, db_original)
                match_score = 100
                break
            
            # Partial match
            if discord_clean in db_name_clean or db_name_clean in discord_clean:
                if len(discord_clean) > match_score:
                    best_match = (guid, db_clean, db_original)
                    match_score = len(discord_clean)
        
        if best_match:
            matches.append((discord_name, discord_id, best_match[0], best_match[1], best_match[2]))
            # Remove from unmatched
            unmatched_db = [p for p in unmatched_db if p[0] != best_match[0]]
        else:
            unmatched_discord.append((discord_name, discord_id))
    
    print(f"\n✅ FOUND {len(matches)} POTENTIAL MATCHES:")
    print("-" * 70)
    print(f"{'Discord Name':<15} {'Discord ID':<20} {'GUID':<10} {'DB Name':<15}")
    print("-" * 70)
    for discord_name, discord_id, guid, db_clean, db_original in matches:
        print(f"{discord_name:<15} {discord_id:<20} {guid:<10} {db_clean:<15}")
    
    if unmatched_discord:
        print(f"\n❌ UNMATCHED DISCORD USERS ({len(unmatched_discord)}):")
        for discord_name, discord_id in unmatched_discord:
            print(f"   {discord_name:<15} {discord_id}")
    
    if unmatched_db:
        print(f"\n🤔 UNMATCHED DATABASE PLAYERS ({len(unmatched_db)}):")
        for guid, clean_name, original_name in unmatched_db:
            print(f"   {clean_name:<15} {guid}")
    
    conn.close()
    return matches

def apply_discord_links(matches):
    """Apply Discord links to the database"""
    
    db_path = "dev/etlegacy_comprehensive.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print(f"\n🔗 APPLYING {len(matches)} DISCORD LINKS")
    print("=" * 70)
    
    links_added = 0
    links_updated = 0
    
    for discord_name, discord_id, guid, db_clean, db_original in matches:
        try:
            # Check if link already exists
            cursor.execute("SELECT * FROM player_links WHERE player_guid = ?", (guid,))
            existing = cursor.fetchone()
            
            if existing:
                # Update existing link
                cursor.execute("""
                    UPDATE player_links 
                    SET discord_id = ?, discord_username = ? 
                    WHERE player_guid = ?
                """, (discord_id, f"{discord_name}#{discord_id[-4:]}", guid))
                links_updated += 1
                print(f"🔄 Updated: {discord_name} -> {db_clean} ({guid})")
            else:
                # Create new link
                cursor.execute("""
                    INSERT INTO player_links (player_guid, discord_id, discord_username, player_name)
                    VALUES (?, ?, ?, ?)
                """, (guid, discord_id, f"{discord_name}#{discord_id[-4:]}", db_clean))
                links_added += 1
                print(f"✅ Added: {discord_name} -> {db_clean} ({guid})")
                
        except sqlite3.Error as e:
            print(f"❌ Error linking {discord_name}: {e}")
    
    conn.commit()
    
    # Show final link count
    cursor.execute("SELECT COUNT(*) FROM player_links")
    total_links = cursor.fetchone()[0]
    
    print(f"\n📊 LINKING SUMMARY:")
    print(f"   ✅ Links added: {links_added}")
    print(f"   🔄 Links updated: {links_updated}")
    print(f"   📈 Total links in database: {total_links}")
    
    # Show all current links
    print(f"\n🔗 ALL CURRENT DISCORD LINKS:")
    cursor.execute("SELECT player_guid, discord_id, discord_username, player_name FROM player_links ORDER BY player_name")
    all_links = cursor.fetchall()
    
    print("-" * 70)
    print(f"{'GUID':<10} {'Discord ID':<20} {'Username':<20} {'Player':<15}")
    print("-" * 70)
    for guid, discord_id, discord_username, player_name in all_links:
        print(f"{guid:<10} {discord_id:<20} {discord_username:<20} {player_name:<15}")
    
    conn.close()
    
    print(f"\n🎉 Discord linking complete!")
    print(f"💡 You can now test commands like: !stats @{matches[0][0]} if they match")

def main():
    """Main linking process"""
    print("🚀 DISCORD USER LINKING FOR COMPREHENSIVE DATABASE")
    print("=" * 70)
    
    # Find matches between Discord users and database players
    matches = find_matching_players()
    
    if matches:
        print(f"\n❓ Apply these {len(matches)} Discord links? (y/n): ", end="")
        
        # For automation, let's apply them
        print("y")  # Auto-confirm for script execution
        apply_discord_links(matches)
    else:
        print("\n❌ No matches found. You may need to:")
        print("   1. Add more test players to the database")
        print("   2. Manually create links for specific GUIDs")
        print("   3. Check if player names match the Discord names")

if __name__ == "__main__":
    main()