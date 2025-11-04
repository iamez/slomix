#!/usr/bin/env python3
"""
🔍 TRACE DATA SOURCE - October 2, 2025
=====================================
Shows EXACTLY where the database data came from:
- Which files were imported
- When they were imported
- Raw file content vs parsed data
- Database records created
"""
import sys
sys.path.insert(0, 'bot')

import sqlite3
from pathlib import Path
from datetime import datetime

def trace_data_source():
    """Trace where October 2 data came from."""
    
    conn = sqlite3.connect('etlegacy_production.db')
    c = conn.cursor()
    
    print("=" * 120)
    print("🔍 DATA SOURCE TRACE - October 2, 2025")
    print("=" * 120)
    print()
    
    # First, check if we have a processed_files table
    tables = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    table_names = [t[0] for t in tables]
    
    print("📊 Available tables:")
    for table in table_names:
        count = c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
        print(f"  - {table}: {count} records")
    print()
    
    has_processed = 'processed_files' in table_names
    
    if has_processed:
        print("=" * 120)
        print("📁 PROCESSED FILES - October 2, 2025")
        print("=" * 120)
        print()
        
        # Get processed files for October 2
        processed = c.execute('''
            SELECT filename, processed_at, success, file_size, player_count
            FROM processed_files
            WHERE filename LIKE '2025-10-02%'
            ORDER BY processed_at
        ''').fetchall()
        
        if processed:
            print(f"Found {len(processed)} files processed on October 2:")
            print()
            print(f"{'Filename':<50} {'Processed At':<20} {'Success':<8} {'Size':<10} {'Players':<8}")
            print("-" * 120)
            
            for filename, processed_at, success, file_size, player_count in processed:
                success_str = "✅" if success else "❌"
                print(f"{filename:<50} {processed_at:<20} {success_str:<8} {file_size:<10} {player_count:<8}")
            print()
        else:
            print("❌ No processed files found for October 2!")
            print()
    else:
        print("⚠️ No processed_files table found - can't trace import history")
        print()
    
    # Check what sessions we have for October 2
    print("=" * 120)
    print("📅 SESSIONS IN DATABASE - October 2, 2025")
    print("=" * 120)
    print()
    
    sessions = c.execute('''
        SELECT 
            id,
            session_date,
            map_name,
            round_number,
            time_limit,
            actual_time
        FROM sessions
        WHERE session_date LIKE '2025-10-02%'
        ORDER BY session_date, round_number
    ''').fetchall()
    
    if sessions:
        print(f"Found {len(sessions)} sessions:")
        print()
        print(f"{'ID':<6} {'Datetime':<20} {'Map':<20} {'Rnd':<5} {'Limit':<10} {'Actual':<10}")
        print("-" * 120)
        for sid, date, map_name, rnd, limit, actual in sessions:
            print(f"{sid:<6} {date:<20} {map_name:<20} {rnd:<5} {limit:<10} {actual:<10}")
        print()
    else:
        print("❌ No sessions found for October 2!")
        print()
        return
    
    # Now check what files SHOULD exist in local_stats
    print("=" * 120)
    print("📂 FILES IN local_stats - October 2, 2025")
    print("=" * 120)
    print()
    
    stats_dir = Path('local_stats')
    oct2_files = sorted(stats_dir.glob('2025-10-02*.txt'))
    
    print(f"Found {len(oct2_files)} files:")
    print()
    print(f"{'Filename':<60} {'Size':<10} {'Modified':<20}")
    print("-" * 120)
    
    for f in oct2_files:
        size = f.stat().st_size
        mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        print(f"{f.name:<60} {size:<10} {mtime:<20}")
    
    print()
    
    # Match files to sessions
    print("=" * 120)
    print("🔗 FILE → SESSION MAPPING")
    print("=" * 120)
    print()
    
    for session in sessions:
        sid, date, map_name, rnd, limit, actual = session
        
        # Try to find matching file
        # Filename format: YYYY-MM-DD-HHMMSS-mapname-round-N.txt
        date_part = date.split()[0]  # Get just YYYY-MM-DD
        
        matching_files = [f for f in oct2_files 
                         if map_name.replace('_', '-') in f.name.replace('_', '-')
                         and f'round-{rnd}' in f.name]
        
        if matching_files:
            print(f"Session {sid} ({map_name} R{rnd}):")
            for mf in matching_files:
                print(f"  → {mf.name}")
        else:
            print(f"Session {sid} ({map_name} R{rnd}): ❌ NO MATCHING FILE FOUND!")
        print()
    
    # Deep dive: Pick one suspicious session and show raw data
    print("=" * 120)
    print("🔬 DEEP DIVE: etl_adlernest Round 2 (SUSPICIOUS)")
    print("=" * 120)
    print()
    
    # Get the session
    adlernest_r2 = c.execute('''
        SELECT id, session_date, actual_time
        FROM sessions
        WHERE session_date LIKE '2025-10-02%'
        AND map_name = 'etl_adlernest'
        AND round_number = 2
    ''').fetchone()
    
    if adlernest_r2:
        sid, date, actual = adlernest_r2
        print(f"Session ID: {sid}")
        print(f"Date: {date}")
        print(f"Actual time: {actual}")
        print()
        
        # Find the file
        adlernest_files = [f for f in oct2_files if 'adlernest' in f.name and 'round-2' in f.name]
        
        if adlernest_files:
            filename = adlernest_files[0]
            print(f"File: {filename.name}")
            print()
            
            # Read raw file
            print("RAW FILE HEADER:")
            print("-" * 120)
            with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                
            header = lines[0].strip()
            print(header)
            print()
            
            # Parse header
            parts = header.split('\\')
            print("Header fields:")
            print(f"  [0] Server: {parts[0]}")
            print(f"  [1] Map: {parts[1]}")
            print(f"  [2] Config: {parts[2]}")
            print(f"  [3] Round: {parts[3]}")
            print(f"  [4] Defender Team: {parts[4]}")
            print(f"  [5] Winner Team: {parts[5]}")
            print(f"  [6] Time Limit: {parts[6]}")
            print(f"  [7] Actual Time: {parts[7]}")
            print()
            
            # Show first 3 player lines
            print("PLAYER DATA (first 3):")
            print("-" * 120)
            
            for i, line in enumerate(lines[1:4], 1):
                parts = line.strip().split('\t')
                if len(parts) > 22:
                    print(f"Player {i}:")
                    print(f"  Weapon stats part: {parts[0][:80]}...")
                    print(f"  Tab[22] time_played_minutes: {parts[22]}")
                    print()
            
            # Now check what's in database for this session
            print("DATABASE RECORDS FOR THIS SESSION:")
            print("-" * 120)
            
            players = c.execute('''
                SELECT 
                    player_name,
                    kills,
                    deaths,
                    damage_given,
                    time_played_minutes,
                    dpm
                FROM player_comprehensive_stats
                WHERE session_id = ?
                ORDER BY damage_given DESC
            ''', (sid,)).fetchall()
            
            print(f"{'Player':<20} {'Kills':<7} {'Deaths':<8} {'Damage':<9} {'Time(min)':<12} {'DPM':<10}")
            print("-" * 120)
            
            for name, kills, deaths, damage, time_mins, dpm in players:
                time_str = f"{time_mins:.1f}" if time_mins > 0 else "0.0 ❌"
                print(f"{name:<20} {kills:<7} {deaths:<8} {damage:<9} {time_str:<12} {dpm:<10.2f}")
            
            print()
            
            # Compare raw vs database
            print("COMPARISON:")
            print("-" * 120)
            print("Question: Does the database time match the raw file time?")
            print()
            
            # Parse the raw file with the parser to see what it produces
            print("Let's parse this file NOW with current parser:")
            print()
            
            from community_stats_parser import C0RNP0RN3StatsParser
            parser = C0RNP0RN3StatsParser()
            result = parser.parse_stats_file(str(filename))
            
            if result:
                print("✅ Parser result:")
                print(f"  Round: {result.get('round_number')}")
                print(f"  Session time: {result.get('actual_time')}")
                print()
                
                if 'players' in result:
                    print("  Players:")
                    for player in result['players'][:3]:
                        name = player.get('name', 'Unknown')
                        time_mins = player.get('objective_stats', {}).get('time_played_minutes', 0)
                        damage = player.get('damage_given', 0)
                        print(f"    {name}: time={time_mins:.1f}min, damage={damage}")
            else:
                print("❌ Parser returned None!")
        else:
            print("❌ No file found for etl_adlernest Round 2")
    else:
        print("❌ No etl_adlernest Round 2 session found in database")
    
    print()
    conn.close()

if __name__ == '__main__':
    trace_data_source()
