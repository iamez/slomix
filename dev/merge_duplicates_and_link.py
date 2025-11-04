#!/usr/bin/env python3
"""
Merge duplicate players and link edo to zebra
"""

import sqlite3
import os

def merge_duplicates_and_link():
    """Merge duplicate GUIDs and link edo to zebra"""
    
    db_path = "etlegacy_fixed_bulk.db"
    
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found!")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("=== MERGING DUPLICATES AND LINKING PLAYERS ===\n")
    
    # 1. Merge KaNii: 86A09825 → A2C6BEBA (keeping A2C6BEBA as it's linked to Discord)
    print("1. Merging KaNii duplicates:")
    print("   From: 86A09825 (unlinked)")
    print("   To:   A2C6BEBA (linked to kani#1276520122302861475)")
    
    # Check current stats for 86A09825
    cursor.execute("""
        SELECT COUNT(*) as rounds, SUM(kills) as total_kills, SUM(deaths) as total_deaths
        FROM player_round_stats 
        WHERE player_guid = ?
    """, ("86A09825",))
    
    old_stats = cursor.fetchone()
    print(f"   Stats to merge: {old_stats[0]} rounds, {old_stats[1]} kills, {old_stats[2]} deaths")
    
    # Update all stats from 86A09825 to A2C6BEBA
    cursor.execute("""
        UPDATE player_round_stats 
        SET player_guid = ? 
        WHERE player_guid = ?
    """, ("A2C6BEBA", "86A09825"))
    
    print(f"   Merged {cursor.rowcount} round records")
    
    # 2. Merge v_kt_r: 326729E5 → 9CC78CFE (keeping 9CC78CFE as it's linked to Discord)
    print("\n2. Merging v_kt_r duplicates:")
    print("   From: 326729E5 (unlinked)")
    print("   To:   9CC78CFE (linked to v_kt_r#1276896142306926622)")
    
    # Check current stats for 326729E5
    cursor.execute("""
        SELECT COUNT(*) as rounds, SUM(kills) as total_kills, SUM(deaths) as total_deaths
        FROM player_round_stats 
        WHERE player_guid = ?
    """, ("326729E5",))
    
    old_stats = cursor.fetchone()
    print(f"   Stats to merge: {old_stats[0]} rounds, {old_stats[1]} kills, {old_stats[2]} deaths")
    
    # Update all stats from 326729E5 to 9CC78CFE
    cursor.execute("""
        UPDATE player_round_stats 
        SET player_guid = ? 
        WHERE player_guid = ?
    """, ("9CC78CFE", "326729E5"))
    
    print(f"   Merged {cursor.rowcount} round records")
    
    # 3. Link edo (0406DAA7) to zebra (688065923839688794)
    print("\n3. Linking edo to zebra:")
    print("   ET GUID: 0406DAA7")
    print("   Discord: zebra (688065923839688794)")
    
    # Check if edo is already linked
    cursor.execute("SELECT discord_username FROM player_links WHERE et_guid = ?", ("0406DAA7",))
    existing = cursor.fetchone()
    
    if existing:
        print(f"   Already linked to: {existing[0]}")
        # Update to zebra
        cursor.execute("""
            UPDATE player_links 
            SET discord_username = ? 
            WHERE et_guid = ?
        """, ("zebra#688065923839688794", "0406DAA7"))
        print("   Updated link to zebra")
    else:
        # Insert new link
        cursor.execute("""
            INSERT INTO player_links (et_guid, discord_username) 
            VALUES (?, ?)
        """, ("0406DAA7", "zebra#688065923839688794"))
        print("   Created new link to zebra")
    
    # 4. Clean up any orphaned player_links entries for merged GUIDs
    print("\n4. Cleaning up orphaned links:")
    
    # Remove link for 86A09825 (merged into A2C6BEBA)
    cursor.execute("DELETE FROM player_links WHERE et_guid = ?", ("86A09825",))
    if cursor.rowcount > 0:
        print(f"   Removed orphaned link for 86A09825")
    
    # Remove link for 326729E5 (merged into 9CC78CFE)
    cursor.execute("DELETE FROM player_links WHERE et_guid = ?", ("326729E5",))
    if cursor.rowcount > 0:
        print(f"   Removed orphaned link for 326729E5")
    
    # 5. Verification - show final status
    print("\n=== VERIFICATION ===")
    
    # Check merged players
    for guid, name in [("A2C6BEBA", "KaNii"), ("9CC78CFE", "v_kt_r"), ("0406DAA7", "edo")]:
        cursor.execute("""
            SELECT COUNT(*) as rounds, SUM(kills) as total_kills, SUM(deaths) as total_deaths
            FROM player_round_stats 
            WHERE player_guid = ?
        """, (guid,))
        
        stats = cursor.fetchone()
        
        cursor.execute("SELECT discord_username FROM player_links WHERE et_guid = ?", (guid,))
        link = cursor.fetchone()
        
        print(f"{name} ({guid}):")
        print(f"  Stats: {stats[0]} rounds, {stats[1]} kills, {stats[2]} deaths")
        print(f"  Discord: {link[0] if link else 'Not linked'}")
        print()
    
    # Commit changes
    conn.commit()
    conn.close()
    
    print("✅ All duplicates merged and edo linked successfully!")
    print("\nNext step: Apply cumulative stats bug fix...")

if __name__ == "__main__":
    merge_duplicates_and_link()