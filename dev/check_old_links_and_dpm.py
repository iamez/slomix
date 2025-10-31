#!/usr/bin/env python3
"""Check old database links and investigate DPM values"""

import sqlite3

def check_old_database_links():
    """Check existing player links from old database"""
    print('🔍 CHECKING OLD DATABASE PLAYER LINKS:')
    print('=' * 50)
    
    try:
        conn = sqlite3.connect('etlegacy.db')
        cursor = conn.cursor()
        
        # Check what tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        tables = cursor.fetchall()
        table_names = [t[0] for t in tables]
        print(f'Old database tables: {table_names}')
        
        # Check for player_links table
        if 'player_links' in table_names:
            cursor.execute('SELECT COUNT(*) FROM player_links')
            link_count = cursor.fetchone()[0]
            print(f'Player links in old database: {link_count}')
            
            if link_count > 0:
                print('\nExisting player links:')
                cursor.execute('SELECT et_guid, discord_id, discord_username FROM player_links LIMIT 15')
                links = cursor.fetchall()
                for guid, discord_id, username in links:
                    print(f'   {guid} -> {discord_id} ({username})')
        else:
            print('No player_links table found in old database')
        
        conn.close()
    except Exception as e:
        print(f'Error accessing old database: {e}')

def investigate_dpm_values():
    """Investigate suspiciously high DPM values"""
    print('\n🔍 INVESTIGATING DPM VALUES:')
    print('=' * 50)
    
    conn = sqlite3.connect('etlegacy_fixed_bulk.db')
    cursor = conn.cursor()
    
    # Check DPM column structure
    cursor.execute('PRAGMA table_info(player_round_stats)')
    columns = cursor.fetchall()
    dpm_column = [col for col in columns if 'dpm' in col[1].lower()]
    print(f'DPM column info: {dpm_column}')
    
    # Check some DPM values with their context
    cursor.execute('''
        SELECT clean_name_final, dpm, kills, deaths, round_id, processed_at
        FROM player_round_stats 
        WHERE dpm > 500
        ORDER BY dpm DESC
        LIMIT 10
    ''')
    
    print('\nHigh DPM values (>500):')
    high_dpm = cursor.fetchall()
    for name, dpm, kills, deaths, round_id, processed_at in high_dpm:
        print(f'   {name}: {dpm:.1f} DPM | {kills}K/{deaths}D | Round {round_id}')
    
    # Check average DPM distribution
    cursor.execute('''
        SELECT 
            COUNT(*) as total_records,
            AVG(dpm) as avg_dpm,
            MIN(dpm) as min_dpm,
            MAX(dpm) as max_dmp,
            COUNT(CASE WHEN dpm > 500 THEN 1 END) as high_dpm_count,
            COUNT(CASE WHEN dpm > 1000 THEN 1 END) as very_high_dpm_count
        FROM player_round_stats 
        WHERE dpm > 0
    ''')
    
    stats = cursor.fetchone()
    total, avg_dpm, min_dmp, max_dpm, high_count, very_high_count = stats
    
    print(f'\nDPM Statistics:')
    print(f'   Total records with DPM: {total:,}')
    print(f'   Average DPM: {avg_dpm:.1f}')
    print(f'   Min DPM: {min_dmp:.1f}')
    print(f'   Max DPM: {max_dpm:.1f}')
    print(f'   Records with DPM > 500: {high_count} ({high_count/total*100:.1f}%)')
    print(f'   Records with DPM > 1000: {very_high_count} ({very_high_count/total*100:.1f}%)')
    
    # Sample calculation check
    print(f'\nSample DPM calculation check:')
    cursor.execute('''
        SELECT clean_name_final, dpm, kills, deaths, headshots
        FROM player_round_stats 
        WHERE clean_name_final = 'vid' AND dpm > 0
        ORDER BY dpm DESC
        LIMIT 5
    ''')
    
    vid_samples = cursor.fetchall()
    for name, dpm, kills, deaths, hs in vid_samples:
        print(f'   {name}: {dpm:.1f} DPM | {kills}K/{deaths}D {hs}HS')
        # Normal DPM should be around 200-400 for good players
        if dpm > 600:
            print(f'     ⚠️  This DPM seems too high for a normal round')
    
    conn.close()

def copy_player_links_from_old_db():
    """Copy player links from old database to new database"""
    print('\n🔗 COPYING PLAYER LINKS:')
    print('=' * 50)
    
    try:
        # Connect to old database
        old_conn = sqlite3.connect('etlegacy.db')
        old_cursor = old_conn.cursor()
        
        # Connect to new database
        new_conn = sqlite3.connect('etlegacy_fixed_bulk.db')
        new_cursor = new_conn.cursor()
        
        # Check if old database has player_links
        old_cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'player_links'")
        if not old_cursor.fetchone():
            print('No player_links table in old database')
            return
        
        # Get all links from old database
        old_cursor.execute('SELECT et_guid, discord_id, discord_username FROM player_links')
        old_links = old_cursor.fetchall()
        
        print(f'Found {len(old_links)} player links in old database')
        
        # Clear existing links in new database
        new_cursor.execute('DELETE FROM player_links')
        
        # Copy links to new database
        copied = 0
        for et_guid, discord_id, discord_username in old_links:
            # Check if this GUID exists in new database
            new_cursor.execute('SELECT COUNT(*) FROM player_round_stats WHERE player_guid = ?', (et_guid,))
            if new_cursor.fetchone()[0] > 0:
                # Insert the link
                new_cursor.execute('''
                    INSERT OR REPLACE INTO player_links (et_guid, discord_id, discord_username)
                    VALUES (?, ?, ?)
                ''', (et_guid, discord_id, discord_username))
                copied += 1
                print(f'   Copied: {et_guid} -> {discord_username}')
            else:
                print(f'   Skipped: {et_guid} -> {discord_username} (GUID not found in new database)')
        
        new_conn.commit()
        print(f'\n✅ Successfully copied {copied} player links to new database')
        
        old_conn.close()
        new_conn.close()
        
    except Exception as e:
        print(f'❌ Error copying player links: {e}')

if __name__ == "__main__":
    check_old_database_links()
    investigate_dpm_values()
    
    # Ask user if they want to copy links
    print('\n🤔 Would you like to copy player links from old database? (This will preserve Discord associations)')
    print('   This will NOT change any statistics, only link players to Discord accounts')
    # Uncomment the next line to actually copy:
    # copy_player_links_from_old_db()