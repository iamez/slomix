#!/usr/bin/env python3
"""
Simple Bulk Import for Seconds-Based Schema
Imports all stats files from local_stats/ into fresh production database
"""

import os
import sys
import sqlite3
from pathlib import Path
from datetime import datetime
import traceback

# Add bot directory to path to import parser
sys.path.insert(0, 'bot')
from community_stats_parser import C0RNP0RN3StatsParser


class SimpleBulkImporter:
    """Simple bulk importer using existing parser"""
    
    def __init__(self, db_path="etlegacy_production.db", stats_dir="local_stats"):
        self.db_path = db_path
        self.stats_dir = stats_dir
        self.parser = C0RNP0RN3StatsParser()
        self.processed = 0
        self.failed = 0
        self.failed_files = []
        
    def get_stats_files(self):
        """Get all .txt files from stats directory, sorted by date"""
        stats_path = Path(self.stats_dir)
        if not stats_path.exists():
            raise Exception(f"Stats directory not found: {self.stats_dir}")
        
        files = sorted(stats_path.glob("2025-10-02-*.txt"))
        return files
    
    def insert_session(self, conn, session_date, result):
        """Insert session and return session_id"""
        cursor = conn.cursor()
        
        # Check if session already exists
        cursor.execute('''
            SELECT id FROM sessions 
            WHERE session_date = ? AND map_name = ? AND round_number = ?
        ''', (session_date, result['map_name'], result['round_num']))
        
        existing = cursor.fetchone()
        if existing:
            return existing[0]
        
        # Insert new session
        cursor.execute('''
            INSERT INTO sessions (
                session_date, map_name, round_number,
                time_limit, next_time_limit
            ) VALUES (?, ?, ?, ?, ?)
        ''', (
            session_date,
            result['map_name'],
            result['round_num'],
            result.get('map_time', ''),
            result.get('actual_time', '')
        ))
        
        return cursor.lastrowid
    
    def insert_player_stats(self, conn, session_id, session_date, result, player):
        """Insert player comprehensive stats"""
        cursor = conn.cursor()
        
        # Get objective_stats if available
        obj_stats = player.get('objective_stats', {})
        
        # Extract time fields - SECONDS IS PRIMARY!
        time_seconds = player.get('time_played_seconds', 0)
        time_display = player.get('time_display', '0:00')
        
        # DEPRECATED: time_played_minutes (keep for backward compat)
        time_minutes = time_seconds / 60.0 if time_seconds > 0 else 0.0
        
        # DPM is already calculated by parser
        dpm = player.get('dpm', 0.0)
        
        # K/D ratio
        kills = player.get('kills', 0)
        deaths = player.get('deaths', 0)
        kd_ratio = kills / deaths if deaths > 0 else float(kills)
        
        cursor.execute('''
            INSERT INTO player_comprehensive_stats (
                session_id, session_date, map_name, round_number,
                player_guid, player_name, clean_name, team,
                kills, deaths, damage_given, damage_received,
                team_damage_given, team_damage_received,
                gibs, self_kills, team_kills, team_gibs,
                time_played_seconds, time_played_minutes, time_display,
                xp, dpm, kd_ratio,
                killing_spree_best, death_spree_worst,
                kill_assists, kill_steals, headshot_kills,
                objectives_stolen, objectives_returned,
                dynamites_planted, dynamites_defused, times_revived,
                bullets_fired, tank_meatshield, time_dead_ratio,
                most_useful_kills, denied_playtime,
                useless_kills, full_selfkills, repairs_constructions,
                double_kills, triple_kills, quad_kills, multi_kills, mega_kills
            ) VALUES (
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?,
                ?, ?, ?,
                ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?, ?
            )
        ''', (
            session_id, session_date, result['map_name'], result['round_num'],
            player.get('guid', 'UNKNOWN'), player.get('name', 'Unknown'),
            player.get('name', 'Unknown'), player.get('team', 0),
            kills, deaths, player.get('damage_given', 0), 
            player.get('damage_received', 0),
            player.get('team_damage_given', 0), 
            player.get('team_damage_received', 0),
            obj_stats.get('gibs', 0), obj_stats.get('self_kills', 0),
            obj_stats.get('team_kills', 0), obj_stats.get('team_gibs', 0),
            time_seconds, time_minutes, time_display,
            obj_stats.get('xp', 0), dpm, kd_ratio,
            obj_stats.get('killing_spree', 0), 
            obj_stats.get('death_spree', 0),
            obj_stats.get('kill_assists', 0), 
            obj_stats.get('kill_steals', 0),
            player.get('headshots', 0),
            obj_stats.get('objectives_stolen', 0), 
            obj_stats.get('objectives_returned', 0),
            obj_stats.get('dynamites_planted', 0), 
            obj_stats.get('dynamites_defused', 0),
            obj_stats.get('times_revived', 0),
            obj_stats.get('bullets_fired', 0), 
            obj_stats.get('tank_meatshield', 0),
            obj_stats.get('time_dead_ratio', 0),
            obj_stats.get('most_useful_kills', 0), 
            obj_stats.get('denied_playtime', 0),
            obj_stats.get('useless_kills', 0), 
            obj_stats.get('full_selfkills', 0),
            obj_stats.get('repairs_constructions', 0),
            obj_stats.get('double_kills', 0), 
            obj_stats.get('triple_kills', 0),
            obj_stats.get('quad_kills', 0), 
            obj_stats.get('multi_kills', 0),
            obj_stats.get('mega_kills', 0)
        ))
    
    def process_file(self, file_path):
        """Process a single stats file"""
        try:
            # Extract date from filename: YYYY-MM-DD-HHMMSS-mapname-round-N.txt
            filename = file_path.name
            date_part = '-'.join(filename.split('-')[:3])  # YYYY-MM-DD
            
            # Parse file
            result = self.parser.parse_stats_file(str(file_path))
            
            if not result.get('success'):
                error_msg = result.get('error', 'Unknown error')
                raise Exception(f"Parser failed: {error_msg}")
            
            # Connect to database
            conn = sqlite3.connect(self.db_path)
            
            try:
                # Insert session
                session_id = self.insert_session(conn, date_part, result)
                
                # Insert all players
                for player in result.get('players', []):
                    self.insert_player_stats(
                        conn, session_id, date_part, result, player
                    )
                
                conn.commit()
                
                self.processed += 1
                
                # Progress update every 50 files
                if self.processed % 50 == 0:
                    print(f"✅ Processed {self.processed} files...")
                
            finally:
                conn.close()
                
        except Exception as e:
            self.failed += 1
            self.failed_files.append((str(file_path), str(e)))
            if self.failed <= 10:  # Only show first 10 errors
                print(f"❌ Error processing {file_path.name}: {e}")
    
    def import_all(self):
        """Import all stats files"""
        print("\n" + "=" * 60)
        print("🚀 Starting Bulk Import")
        print("=" * 60)
        
        # Get all files
        files = self.get_stats_files()
        total = len(files)
        
        print(f"\n📁 Found {total} stats files")
        print(f"📊 Database: {self.db_path}")
        print(f"⏱️  Starting import at {datetime.now().strftime('%H:%M:%S')}\n")
        
        start_time = datetime.now()
        
        # Process each file
        for file_path in files:
            self.process_file(file_path)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 IMPORT COMPLETE")
        print("=" * 60)
        print(f"✅ Successfully processed: {self.processed}/{total} files")
        print(f"❌ Failed: {self.failed}/{total} files")
        print(f"⏱️  Duration: {duration:.1f} seconds")
        print(f"⚡ Average: {duration/total:.2f} seconds per file")
        
        if self.failed_files:
            print(f"\n⚠️  Failed files ({len(self.failed_files)}):")
            for file_path, error in self.failed_files:
                print(f"   - {Path(file_path).name}: {error}")
        
        print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    importer = SimpleBulkImporter()
    importer.import_all()
