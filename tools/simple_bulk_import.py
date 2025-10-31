#!/usr/bin/env python3
"""
Simple Bulk Import for Seconds-Based Schema
Imports all stats files from local_stats/ into fresh production database
"""

import glob
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Add bot directory to path to import parser
sys.path.insert(0, 'bot')

from community_stats_parser import C0RNP0RN3StatsParser


class SimpleBulkImporter:
    """Simple bulk importer using existing parser"""

    def __init__(
<<<<<<< HEAD
        self, db_path="etlegacy_production.db", stats_dir="local_stats", file_patterns=None
=======
        self, db_path="bot/etlegacy_production.db", stats_dir="local_stats", file_patterns=None
>>>>>>> clean-restructure
    ):
        self.db_path = db_path
        self.stats_dir = stats_dir
        self.file_patterns = file_patterns  # Optional: specific files to import
        self.parser = C0RNP0RN3StatsParser()
        self.processed = 0
        self.failed = 0
<<<<<<< HEAD
=======
        self.skipped = 0
>>>>>>> clean-restructure
        self.failed_files = []

    def get_stats_files(self):
        """Get .txt files to process (all or specific patterns)"""
        files = []

        # If specific file patterns provided, use those
        if self.file_patterns:
            for pattern in self.file_patterns:
                matched = glob.glob(pattern)
                files.extend([Path(f) for f in matched])
            files = sorted(set(files))  # Remove duplicates and sort
            return files

        # Otherwise, get all .txt files from stats directory
        stats_path = Path(self.stats_dir)
        if not stats_path.exists():
            raise Exception(f"Stats directory not found: {self.stats_dir}")

        files = sorted(stats_path.glob("*.txt"))
        return files

    def insert_session(self, conn, session_date, result, filename):
        """Insert session and return session_id"""
        cursor = conn.cursor()

        # Use full timestamp from filename for unique session identification
        # This allows multiple plays of same map per day
        timestamp = '-'.join(filename.split('-')[:4])  # YYYY-MM-DD-HHMMSS
        
        cursor.execute(
            '''
            SELECT id FROM sessions
            WHERE session_date = ? AND map_name = ? AND round_number = ?
        ''',
            (timestamp, result['map_name'], result['round_num']),
        )

        existing = cursor.fetchone()
        if existing:
            return existing[0]

        # Insert new session
        cursor.execute(
            '''
            INSERT INTO sessions (
                session_date, map_name, round_number,
<<<<<<< HEAD
                time_limit, actual_time
            ) VALUES (?, ?, ?, ?, ?)
=======
                defender_team, winner_team,
                time_limit, actual_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
>>>>>>> clean-restructure
        ''',
            (
                timestamp,  # Use full timestamp for uniqueness
                result['map_name'],
                result['round_num'],
<<<<<<< HEAD
=======
                result.get('defender_team', 0),
                result.get('winner_team', 0),
>>>>>>> clean-restructure
                result.get('map_time', ''),
                result.get('actual_time', ''),
            ),
        )

        return cursor.lastrowid

    def insert_player_stats(self, conn, session_id, session_date, result, player):
        """Insert player comprehensive stats"""
        cursor = conn.cursor()

        # Get objective_stats if available
        obj_stats = player.get('objective_stats', {})

        # Extract time fields - SECONDS IS PRIMARY!
        time_seconds = player.get('time_played_seconds', 0)

        # DEPRECATED: time_played_minutes (keep for backward compat)
        time_minutes = time_seconds / 60.0 if time_seconds > 0 else 0.0

        # DPM is already calculated by parser
        dpm = player.get('dpm', 0.0)

        # K/D ratio
        kills = player.get('kills', 0)
        deaths = player.get('deaths', 0)
        kd_ratio = kills / deaths if deaths > 0 else float(kills)

        # Calculate efficiency (accuracy-like metric)
        bullets_fired = obj_stats.get('bullets_fired', 0)
        accuracy = (kills / bullets_fired * 100) if bullets_fired > 0 else 0.0
        efficiency = accuracy  # For now, efficiency is same as accuracy

        # Calculate time dead minutes and ratio
        time_dead_mins = obj_stats.get('time_dead_ratio', 0) * time_minutes
        time_dead_ratio = obj_stats.get('time_dead_ratio', 0)

        values = (
            session_id,
            session_date,
            result['map_name'],
            result['round_num'],
            player.get('guid', 'UNKNOWN'),
            player.get('name', 'Unknown'),
            player.get('name', 'Unknown'),
            player.get('team', 0),
            kills,
            deaths,
            player.get('damage_given', 0),
            player.get('damage_received', 0),
            player.get('team_damage_given', 0),
            player.get('team_damage_received', 0),
            obj_stats.get('gibs', 0),
            obj_stats.get('self_kills', 0),
            obj_stats.get('team_kills', 0),
            obj_stats.get('team_gibs', 0),
            player.get('headshots', 0),
            time_seconds,
            time_minutes,
            time_dead_mins,
            time_dead_ratio,
            obj_stats.get('xp', 0),
            kd_ratio,
            dpm,
            efficiency,
            bullets_fired,
            accuracy,
            obj_stats.get('kill_assists', 0),
            0,  # objectives_completed
            0,  # objectives_destroyed
            obj_stats.get('objectives_stolen', 0),
            obj_stats.get('objectives_returned', 0),
            obj_stats.get('dynamites_planted', 0),
            obj_stats.get('dynamites_defused', 0),
            obj_stats.get('times_revived', 0),
            obj_stats.get('revives_given', 0),
            obj_stats.get('most_useful_kills', 0),
            obj_stats.get('useless_kills', 0),
            obj_stats.get('kill_steals', 0),
            obj_stats.get('denied_playtime', 0),
            0,  # constructions
            obj_stats.get('tank_meatshield', 0),
            obj_stats.get('double_kills', 0),
            obj_stats.get('triple_kills', 0),
            obj_stats.get('quad_kills', 0),
            obj_stats.get('multi_kills', 0),
            obj_stats.get('mega_kills', 0),
            obj_stats.get('killing_spree', 0),
            obj_stats.get('death_spree', 0),
        )

        # Insert into database with schema matching create_unified_database.py
        cursor.execute(
            '''
            INSERT INTO player_comprehensive_stats (
                session_id, session_date, map_name, round_number,
                player_guid, player_name, clean_name, team,
                kills, deaths, damage_given, damage_received,
                team_damage_given, team_damage_received,
                gibs, self_kills, team_kills, team_gibs, headshot_kills,
                time_played_seconds, time_played_minutes,
                time_dead_minutes, time_dead_ratio,
                xp, kd_ratio, dpm, efficiency,
                bullets_fired, accuracy,
                kill_assists,
                objectives_completed, objectives_destroyed,
                objectives_stolen, objectives_returned,
                dynamites_planted, dynamites_defused,
                times_revived, revives_given,
                most_useful_kills, useless_kills, kill_steals,
                denied_playtime, constructions, tank_meatshield,
                double_kills, triple_kills, quad_kills,
                multi_kills, mega_kills,
                killing_spree_best, death_spree_worst
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        ''',
            values,
        )

    def insert_weapon_stats(self, conn, session_id, session_date, result, player):
        """Insert weapon comprehensive stats for a player"""
        cursor = conn.cursor()

        weapon_stats = player.get('weapon_stats', {})
        if not weapon_stats:
            return

        player_guid = player.get('guid', '')
        player_name = player.get('name', '')

        for weapon_name, weapon in weapon_stats.items():
            cursor.execute(
                '''
                INSERT INTO weapon_comprehensive_stats (
                    session_id, session_date, map_name, round_number,
                    player_guid, player_name, weapon_name,
                    kills, deaths, headshots, shots, hits
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
                (
                    session_id,
                    session_date,
                    result['map_name'],
                    result['round_num'],
                    player_guid,
                    player_name,
                    weapon_name,
                    weapon.get('kills', 0),
                    weapon.get('deaths', 0),
                    weapon.get('headshots', 0),
                    weapon.get('shots', 0),
                    weapon.get('hits', 0),
                ),
            )

<<<<<<< HEAD
    def process_file(self, file_path):
        """Process a single stats file"""
        try:
            # Extract date from filename: YYYY-MM-DD-HHMMSS-mapname-round-N.txt
            filename = file_path.name
            date_part = '-'.join(filename.split('-')[:3])  # YYYY-MM-DD for stats
=======
    def is_file_processed(self, conn, filename):
        """Check if file was already processed"""
        cursor = conn.cursor()
        result = cursor.execute(
            'SELECT 1 FROM processed_files WHERE filename = ?',
            (filename,)
        ).fetchone()
        return result is not None

    def mark_file_processed(self, conn, filename, success=True, error_msg=None):
        """Mark file as processed in database"""
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO processed_files 
               (filename, success, error_message) 
               VALUES (?, ?, ?)''',
            (filename, 1 if success else 0, error_msg)
        )

    def process_file(self, file_path):
        """Process a single stats file"""
        filename = file_path.name
        
        # Connect to database first to check if already processed
        conn = sqlite3.connect(self.db_path)
        
        try:
            # Check if already processed
            if self.is_file_processed(conn, filename):
                self.skipped += 1
                if self.skipped <= 5:  # Show first 5 skips
                    print(f"⏭️  Skipping {filename} (already processed)")
                return
            
            # Extract date from filename: YYYY-MM-DD-HHMMSS-mapname-round-N.txt
            date_part = '-'.join(filename.split('-')[:3])  # YYYY-MM-DD
>>>>>>> clean-restructure

            # Parse file
            result = self.parser.parse_stats_file(str(file_path))

            if not result.get('success'):
                error_msg = result.get('error', 'Unknown error')
                raise Exception(f"Parser failed: {error_msg}")

<<<<<<< HEAD
            # Connect to database
            conn = sqlite3.connect(self.db_path)

            try:
                # Insert session
                session_id = self.insert_session(conn, date_part, result, filename)

                # Insert all players and their weapon stats
                for player in result.get('players', []):
                    self.insert_player_stats(conn, session_id, date_part, result, player)
                    self.insert_weapon_stats(conn, session_id, date_part, result, player)

                conn.commit()

                self.processed += 1

                # Progress update every 50 files
                if self.processed % 50 == 0:
                    print(f"✅ Processed {self.processed} files...")

            finally:
                conn.close()
=======
            # Insert session
            session_id = self.insert_session(conn, date_part, result, filename)

            # Insert all players and their weapon stats
            for player in result.get('players', []):
                self.insert_player_stats(
                    conn, session_id, date_part, result, player
                )
                self.insert_weapon_stats(
                    conn, session_id, date_part, result, player
                )

            # Mark as processed
            self.mark_file_processed(conn, filename, success=True)
            
            conn.commit()

            self.processed += 1

            # Progress update every 50 files
            if self.processed % 50 == 0:
                print(f"✅ Processed {self.processed} files...")
>>>>>>> clean-restructure

        except Exception as e:
            self.failed += 1
            self.failed_files.append((str(file_path), str(e)))
<<<<<<< HEAD
            if self.failed <= 10:  # Only show first 10 errors
                print(f"❌ Error processing {file_path.name}: {e}")
=======
            
            # Try to mark as failed
            try:
                self.mark_file_processed(conn, filename, success=False, 
                                        error_msg=str(e))
                conn.commit()
            except:
                pass  # Ignore errors marking failed files
            
            if self.failed <= 10:  # Only show first 10 errors
                print(f"❌ Error processing {file_path.name}: {e}")
        
        finally:
            conn.close()
>>>>>>> clean-restructure

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
<<<<<<< HEAD
        print(f"✅ Successfully processed: {self.processed}/{total} files")
        print(f"❌ Failed: {self.failed}/{total} files")
        print(f"⏱️  Duration: {duration:.1f} seconds")
        print(f"⚡ Average: {duration / total:.2f} seconds per file")
=======
        print(f"✅ Successfully imported: {self.processed}/{total} files")
        print(f"⏭️  Skipped (already processed): {self.skipped}/{total} files")
        print(f"❌ Failed: {self.failed}/{total} files")
        print(f"⏱️  Duration: {duration:.1f} seconds")
        if total > 0:
            print(f"⚡ Average: {duration / total:.2f} seconds per file")
>>>>>>> clean-restructure

        if self.failed_files:
            print(f"\n⚠️  Failed files ({len(self.failed_files)}):")
            for file_path, error in self.failed_files:
                print(f"   - {Path(file_path).name}: {error}")

        print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    # Check if specific files were provided as arguments
    if len(sys.argv) > 1:
        # User provided specific file patterns
        file_patterns = sys.argv[1:]
        print(f"📋 Importing specific files: {file_patterns}")
        importer = SimpleBulkImporter(file_patterns=file_patterns)
    else:
        # No arguments, import all files from local_stats/
        print(f"📋 No files specified, importing ALL from local_stats/")
        importer = SimpleBulkImporter()

    importer.import_all()
