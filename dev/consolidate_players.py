#!/usr/bin/env python3
"""
Player Alias Consolidation and Discord Linking
Manual mappings provided by server admin
Created: October 3, 2025
"""

import sqlite3
import re
from typing import Dict, Tuple

# ============================================================================
# MANUAL PLAYER MAPPINGS - Provided by Admin
# ============================================================================

# Primary name mappings: GUID -> preferred display name
PRIMARY_NAMES = {
    '1C747DF1': 'Lagger',           # EUROSpinLagger/s&o.lgz/SBudgetLagger/SmetarskiProner
    'FDA127DF': 'wiseBoy',          # temu.wjs/.wjs/wiseBoy
    '0A26D447': 'carniee',          # carniee/-slo.carniee-
    '2B5938F5': 'bronze',           # bronze./bronzelow-
    '652EB4A6': 'qmr',              # qmr/XI-WANG
    'E587CA5F': 'seareal',          # ciril/Zlatorog/Jaka V./ez/fl0w3r (SPECIAL FLAG - bot creator!)
    '3C0354D3': 'squaze',           # one^>4ass.squAze/It's squAze/squAze Bros
    'A2C6BEBA': 'KaNii',            # KaNii/Kanii/Aimless.KaNii
    '42E142B3': 'immoo',            # immoo/immoo!
    'C74FB315': 'imb3cil',          # Imb3cil/Vincent
    'E2B2A2B2': 'aLive',            # aLive/aLive aka cannonfodder
    '5D989160': 'olympu',           # .olz (olympu)
    'EDBB5DA9': 'superboyy',        # SuperBoyy
    'D8423F90': 'vid',              # vid
    '7B84BE88': 'endekk',           # endekk
    'A0B2063D': 'i p k i s s',      # i p k i s s
}

# Discord linkings (if available - to be added later)
# Format: GUID -> (discord_id, discord_username)
DISCORD_LINKS = {
    # Add Discord links here when available
    # Example:
    # '1C747DF1': ('123456789012345678', 'Lagger#1234'),
    # 'E587CA5F': ('987654321098765432', 'seareal#5678'),  # Bot creator - special flag
}

# Special flags for players
SPECIAL_FLAGS = {
    'E587CA5F': '🛠️',  # Bot creator badge for seareal/ciril
}

# All known aliases for each GUID (for reference)
ALL_ALIASES = {
    '1C747DF1': ['EUROSpinLagger', 's&o.lgz', 'SBudgetLagger', 'SmetarskiProner'],
    'FDA127DF': ['temu.wjs', '.wjs', 'wiseBoy'],
    '0A26D447': ['carniee', '-slo.carniee-'],
    '2B5938F5': ['bronze.', 'bronzelow-'],
    '652EB4A6': ['qmr', 'XI-WANG'],
    'E587CA5F': ['ciril', 'Zlatorog', 'Jaka V. #1001noc', 'ez', 'Jaka V.', 'fl0w3r', 'Ciril', 'warmup week'],
    '3C0354D3': ['one^>4ass.squAze', "It's squAze", 'squAze Bros', '^<ABD-AL-KL3M3N'],
    'A2C6BEBA': ['KaNii', 'Kanii', 'Aimless.KaNii'],
    '42E142B3': ['immoo', 'immoo!'],
    'C74FB315': ['Imb3cil', 'Vincent'],
    'E2B2A2B2': ['aLive', 'aLive aka cannonfodder'],
    '5D989160': ['.olz'],  # Clean player, olympu
    'EDBB5DA9': ['SuperBoyy'],  # Clean player
    'D8423F90': ['vid'],  # Clean player
    '7B84BE88': ['endekk'],  # Clean player
    'A0B2063D': ['i p k i s s'],  # Clean player
}

# Duplicate GUIDs to merge (wrong GUID -> correct GUID)
GUID_MERGES = {
    '326729E5': '9CC78CFE',  # v_kt_r duplicate (1 game -> 601 games)
}


def strip_color_codes(name: str) -> str:
    """Remove ET color codes from player names"""
    if not name:
        return ""
    return re.sub(r'\^.', '', name).strip()


def consolidate_player_aliases():
    """Consolidate all player aliases to primary names"""
    
    print("\n" + "="*80)
    print("  PLAYER ALIAS CONSOLIDATION")
    print("="*80 + "\n")
    
    conn = sqlite3.connect('etlegacy_production.db')
    cur = conn.cursor()
    
    updates_made = 0
    
    # 1. Update primary names
    print("📝 Step 1: Setting Primary Names\n")
    for guid, primary_name in PRIMARY_NAMES.items():
        # Count current records with this GUID
        cur.execute("""
            SELECT COUNT(*), SUM(kills), SUM(deaths)
            FROM player_comprehensive_stats
            WHERE player_guid = ?
        """, (guid,))
        
        result = cur.fetchone()
        if result and result[0] > 0:
            count, kills, deaths = result
            
            # Update all records for this GUID to use primary name
            cur.execute("""
                UPDATE player_comprehensive_stats
                SET player_name = ?,
                    clean_name = ?
                WHERE player_guid = ?
            """, (primary_name, primary_name, guid))
            
            updated = cur.rowcount
            updates_made += updated
            
            special = SPECIAL_FLAGS.get(guid, '')
            print(f"✅ {guid} -> {primary_name:<15} {special}")
            print(f"   Updated {updated:4,} records ({count} games, {kills:,}K/{deaths:,}D)")
            
            if guid in ALL_ALIASES:
                aliases = ', '.join(ALL_ALIASES[guid][:3])
                if len(ALL_ALIASES[guid]) > 3:
                    aliases += f"... +{len(ALL_ALIASES[guid])-3} more"
                print(f"   Aliases: {aliases}")
            print()
    
    # 2. Merge duplicate GUIDs
    if GUID_MERGES:
        print("\n" + "="*80)
        print("🔀 Step 2: Merging Duplicate GUIDs\n")
        
        for old_guid, new_guid in GUID_MERGES.items():
            cur.execute("""
                SELECT COUNT(*), SUM(kills), SUM(deaths)
                FROM player_comprehensive_stats
                WHERE player_guid = ?
            """, (old_guid,))
            
            result = cur.fetchone()
            if result and result[0] > 0:
                count, kills, deaths = result
                
                print(f"Merging {old_guid} -> {new_guid}")
                print(f"   Moving {count} records ({kills}K/{deaths}D)")
                
                # Update GUID
                cur.execute("""
                    UPDATE player_comprehensive_stats
                    SET player_guid = ?
                    WHERE player_guid = ?
                """, (new_guid, old_guid))
                
                # Also update weapon stats
                cur.execute("""
                    UPDATE weapon_comprehensive_stats
                    SET player_guid = ?
                    WHERE player_guid = ?
                """, (new_guid, old_guid))
                
                updates_made += cur.rowcount
                print(f"   ✅ Merged successfully\n")
    
    # 3. Add special_flag column to existing player_links table
    print("="*80)
    print("🔗 Step 3: Setting Up Player Links Table\n")
    
    # Check if special_flag column exists, add if not
    cur.execute("PRAGMA table_info(player_links)")
    columns = [col[1] for col in cur.fetchall()]
    
    if 'special_flag' not in columns:
        print("   Adding special_flag column...")
        cur.execute("ALTER TABLE player_links ADD COLUMN special_flag TEXT")
    
    # Insert/update primary name as player_name in player_links
    for guid, primary_name in PRIMARY_NAMES.items():
        special_flag = SPECIAL_FLAGS.get(guid)
        
        # Check if link exists
        cur.execute("SELECT player_name FROM player_links WHERE player_guid = ?", (guid,))
        existing = cur.fetchone()
        
        if existing:
            # Update existing record
            cur.execute("""
                UPDATE player_links
                SET player_name = ?,
                    special_flag = ?
                WHERE player_guid = ?
            """, (primary_name, special_flag, guid))
            print(f"   Updated: {guid} -> {primary_name} {special_flag or ''}")
        else:
            # Insert new record
            discord_link = DISCORD_LINKS.get(guid)
            if discord_link:
                discord_id, discord_username = discord_link
                cur.execute("""
                    INSERT INTO player_links (player_guid, discord_id, discord_username, player_name, special_flag)
                    VALUES (?, ?, ?, ?, ?)
                """, (guid, discord_id, discord_username, primary_name, special_flag))
                print(f"   Created: {guid} -> {primary_name} (Discord: {discord_username}) {special_flag or ''}")
            else:
                # Insert without Discord info
                cur.execute("""
                    INSERT OR IGNORE INTO player_links (player_guid, player_name, special_flag)
                    VALUES (?, ?, ?)
                """, (guid, primary_name, special_flag))
                print(f"   Created: {guid} -> {primary_name} {special_flag or ''}")
    
    # Commit all changes
    conn.commit()
    
    # 4. Verification
    print("\n" + "="*80)
    print("✅ Step 4: Verification\n")
    
    print("Top 10 Players After Consolidation:")
    print("-" * 80)
    
    cur.execute("""
        SELECT 
            p.player_guid,
            p.clean_name,
            pl.special_flag,
            COUNT(*) as games,
            SUM(p.kills) as total_kills,
            SUM(p.deaths) as total_deaths,
            ROUND(CAST(SUM(p.kills) AS FLOAT) / NULLIF(SUM(p.deaths), 0), 2) as kd
        FROM player_comprehensive_stats p
        LEFT JOIN player_links pl ON p.player_guid = pl.player_guid
        GROUP BY p.player_guid
        ORDER BY total_kills DESC
        LIMIT 10
    """)
    
    top_players = cur.fetchall()
    
    for i, (guid, name, flag, games, kills, deaths, kd) in enumerate(top_players, 1):
        flag_str = flag if flag else ''
        print(f"{i:2}. {name:<15} {flag_str:<3} {guid}  {games:4} games  {kills:6,}K/{deaths:6,}D  K/D: {kd:.2f}")
    
    conn.close()
    
    print("\n" + "="*80)
    print(f"✅ Consolidation Complete!")
    print(f"   Total updates made: {updates_made:,}")
    print(f"   Primary names set: {len(PRIMARY_NAMES)}")
    print(f"   Special flags: {len(SPECIAL_FLAGS)} (Bot Creator: seareal/ciril 🛠️)")
    print("="*80 + "\n")


def show_consolidated_players():
    """Show all players after consolidation"""
    
    conn = sqlite3.connect('etlegacy_production.db')
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print("  ALL PLAYERS (Consolidated)")
    print("="*80 + "\n")
    
    cur.execute("""
        SELECT 
            p.player_guid,
            p.clean_name,
            pl.special_flag,
            pl.discord_username,
            COUNT(*) as games,
            SUM(p.kills) as total_kills,
            SUM(p.deaths) as total_deaths
        FROM player_comprehensive_stats p
        LEFT JOIN player_links pl ON p.player_guid = pl.player_guid
        GROUP BY p.player_guid
        ORDER BY total_kills DESC
    """)
    
    players = cur.fetchall()
    
    print(f"{'GUID':<10} {'Name':<15} {'Flag':<5} {'Discord':<25} {'Games':<7} {'K/D':<15}")
    print("-" * 80)
    
    for guid, name, flag, discord, games, kills, deaths in players:
        flag_str = flag if flag else ''
        discord_str = discord[:22] + '...' if discord and len(discord) > 25 else (discord or 'Not linked')
        kd_str = f"{kills:,}/{deaths:,}"
        print(f"{guid:<10} {name:<15} {flag_str:<5} {discord_str:<25} {games:<7} {kd_str:<15}")
    
    print(f"\nTotal Players: {len(players)}")
    
    conn.close()


def add_discord_link(guid: str, discord_id: str, discord_username: str):
    """Add Discord link for a player"""
    
    conn = sqlite3.connect('etlegacy_production.db')
    cur = conn.cursor()
    
    # Check if player exists
    cur.execute("SELECT primary_name FROM player_links WHERE player_guid = ?", (guid,))
    result = cur.fetchone()
    
    if not result:
        print(f"❌ GUID {guid} not found in player_links table")
        conn.close()
        return False
    
    primary_name = result[0]
    
    # Update Discord info
    cur.execute("""
        UPDATE player_links
        SET discord_id = ?,
            discord_username = ?
        WHERE player_guid = ?
    """, (discord_id, discord_username, guid))
    
    conn.commit()
    conn.close()
    
    print(f"✅ Linked {primary_name} ({guid}) to Discord: {discord_username}")
    return True


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "consolidate":
            consolidate_player_aliases()
        elif command == "show":
            show_consolidated_players()
        elif command == "link" and len(sys.argv) == 5:
            # python consolidate_players.py link <guid> <discord_id> <discord_username>
            guid, discord_id, discord_username = sys.argv[2:5]
            add_discord_link(guid, discord_id, discord_username)
        else:
            print("Usage:")
            print("  python consolidate_players.py consolidate     # Apply all consolidations")
            print("  python consolidate_players.py show           # Show all consolidated players")
            print("  python consolidate_players.py link <guid> <discord_id> <username>  # Add Discord link")
    else:
        # Default: run consolidation
        consolidate_player_aliases()
        print("\n💡 Run 'python consolidate_players.py show' to see all players")
