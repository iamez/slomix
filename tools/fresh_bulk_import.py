#!/usr/bin/env python3
"""
Fresh Bulk Import - Matches fresh database schema
Imports stats files with duplicate prevention
"""

import glob
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Add bot directory to path to import parser
sys.path.insert(0, 'bot')

from community_stats_parser import C0RNP0RN3StatsParser


class FreshBulkImporter:
    """Bulk importer matching fresh database schema"""

    def __init__(
        self, db_path="bot/etlegacy_production.db", 
        stats_dir="local_stats", 
        file_patterns=None
    ):
        self.db_path = db_path
        self.stats_dir = stats_dir
        self.file_patterns = file_patterns
        self.parser = C0RNP0RN3StatsParser()
        self.processed = 0
        self.failed = 0
        self.skipped = 0
        self.failed_files = []

    def get_stats_files(self):
        """Get .txt files to process"""
        files = []

        if self.file_patterns:
            for pattern in self.file_patterns:
                matched = glob.glob(pattern)
                files.extend([Path(f) for f in matched])
            files = sorted(set(files))
            return files

        stats_path = Path(self.stats_dir)
        if not stats_path.exists():
            raise Exception(f"Stats directory not found: {self.stats_dir}")

        files = sorted(stats_path.glob("*.txt"))
        return files

    def is_file_processed(self, conn, filename):
        """Check if file was already processed"""
        cursor = conn.cursor()
        result = cursor.execute(
            'SELECT 1 FROM processed_files WHERE filename = ?',
            (filename,)
        ).fetchone()
        return result is not None

    def mark_file_processed(self, conn, filename, success=True, error_msg=None):
        """Mark file as processed"""
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO processed_files 
               (filename, success, error_message) 
               VALUES (?, ?, ?)''',
            (filename, 1 if success else 0, error_msg)
        )

    def insert_session(self, conn, result, filename):
        """Insert session and return session_id"""
        cursor = conn.cursor()

        # Use full timestamp from filename for unique session identification
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
                defender_team, winner_team,
                time_limit, actual_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''',
            (
                timestamp,
                result['map_name'],
                result['round_num'],
                result.get('defender_team', 0),
                result.get('winner_team', 0),
                result.get('map_time', ''),
                result.get('actual_time', ''),
            ),
        )

        return cursor.lastrowid

    def insert_player_stats(self, conn, session_id, player):
        """Insert player comprehensive stats"""
        cursor = conn.cursor()

        obj_stats = player.get('objective_stats', {})

        # Calculate accuracy
        hits = player.get('hits', 0)
        shots = player.get('shots', 0)
        accuracy = (hits / shots * 100.0) if shots > 0 else 0.0

        # Calculate efficiency
        kills = player.get('kills', 0)
        deaths = player.get('deaths', 0)
        efficiency_val = ((kills / (kills + deaths)) * 100.0) if (kills + deaths) > 0 else 0.0

        cursor.execute(
            '''
            INSERT INTO player_comprehensive_stats (
                session_id, player_name, guid, team,
                kills, deaths, gibs, suicides, teamkills, headshots,
                damage_given, damage_received, damage_team,
                hits, shots, accuracy, revives,
                ammogiven, healthgiven, poisoned, knifekills, killpeak,
                efficiency, score,
                dyn_planted, dyn_defused,
                obj_captured, obj_destroyed, obj_returned, obj_taken,
                obj_checkpoint, obj_killed, obj_protected,
                time_played, time_played_seconds, num_rounds
            ) VALUES (
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?,
                ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?
            )
        ''',
            (
                session_id,
                player.get('name', 'Unknown'),
                player.get('guid', ''),
                player.get('team', 0),
                kills,
                deaths,
                obj_stats.get('gibs', 0),
                obj_stats.get('self_kills', 0),
                obj_stats.get('team_kills', 0),
                player.get('headshots', 0),
                player.get('damage_given', 0),
                player.get('damage_received', 0),
                obj_stats.get('team_damage_given', 0),
                hits,
                shots,
                accuracy,
                player.get('revives', 0),
                player.get('ammogiven', 0),
                player.get('healthgiven', 0),
                player.get('poisoned', 0),
                obj_stats.get('knifekills', 0),
                obj_stats.get('killpeak', 0),
                efficiency_val,
                player.get('score', 0),
                obj_stats.get('dynamites_planted', 0),
                obj_stats.get('dynamites_defused', 0),
                obj_stats.get('obj_captured', 0),
                obj_stats.get('obj_destroyed', 0),
                obj_stats.get('obj_returned', 0),
                obj_stats.get('obj_taken', 0),
                obj_stats.get('obj_checkpoint', 0),
                obj_stats.get('obj_killed', 0),
                obj_stats.get('obj_protected', 0),
                player.get('time_played', ''),
                player.get('time_played_seconds', 0),
                1,  # num_rounds
            ),
        )

    def insert_weapon_stats(self, conn, session_id, player):
        """Insert weapon comprehensive stats"""
        cursor = conn.cursor()

        weapon_stats = player.get('weapon_stats', {})
        if not weapon_stats:
            return

        player_name = player.get('name', 'Unknown')

        for weapon_name, weapon in weapon_stats.items():
            hits_w = weapon.get('hits', 0)
            shots_w = weapon.get('shots', 0)
            accuracy_w = (hits_w / shots_w * 100.0) if shots_w > 0 else 0.0

            cursor.execute(
                '''
                INSERT INTO weapon_comprehensive_stats (
                    session_id, player_name, weapon_name,
                    kills, deaths, headshots, hits, shots, accuracy
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
                (
                    session_id,
                    player_name,
                    weapon_name,
                    weapon.get('kills', 0),
                    weapon.get('deaths', 0),
                    weapon.get('headshots', 0),
                    hits_w,
                    shots_w,
                    accuracy_w,
                ),
            )

    def process_file(self, file_path):
        """Process a single stats file"""
        filename = file_path.name
        
        conn = sqlite3.connect(self.db_path)
        
        try:
            # Check if already processed
            if self.is_file_processed(conn, filename):
                self.skipped += 1
                if self.skipped <= 5:
                    print(f"⏭️  Skipping {filename} (already processed)")
                return

            # Parse file
            result = self.parser.parse_stats_file(str(file_path))

            if not result.get('success'):
                error_msg = result.get('error', 'Unknown error')
                raise Exception(f"Parser failed: {error_msg}")

            # Insert session
            session_id = self.insert_session(conn, result, filename)

            # Insert all players and their weapon stats
            for player in result.get('players', []):
                self.insert_player_stats(conn, session_id, player)
                self.insert_weapon_stats(conn, session_id, player)

            # Mark as processed
            self.mark_file_processed(conn, filename, success=True)
            
            conn.commit()

            self.processed += 1

            # Progress update every 100 files
            if self.processed % 100 == 0:
                print(f"✅ Processed {self.processed} files...")

        except Exception as e:
            self.failed += 1
            self.failed_files.append((str(file_path), str(e)))
            
            # Try to mark as failed
            try:
                self.mark_file_processed(conn, filename, success=False, 
                                        error_msg=str(e))
                conn.commit()
            except Exception:
                pass
            
            if self.failed <= 10:
                print(f"❌ Error processing {file_path.name}: {e}")
        
        finally:
            conn.close()

    def import_all(self):
        """Import all stats files"""
        print("\n" + "=" * 70)
        print("🚀 FRESH BULK IMPORT (with duplicate prevention)")
        print("=" * 70)

        files = self.get_stats_files()
        total = len(files)

        print(f"\n📁 Found {total} stats files")
        print(f"📊 Database: {self.db_path}")
        print(f"⏱️  Start: {datetime.now().strftime('%H:%M:%S')}\n")

        start_time = datetime.now()

        for file_path in files:
            self.process_file(file_path)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Summary
        print("\n" + "=" * 70)
        print("📊 IMPORT COMPLETE")
        print("=" * 70)
        print(f"✅ Successfully imported: {self.processed}/{total}")
        print(f"⏭️  Skipped (already processed): {self.skipped}/{total}")
        print(f"❌ Failed: {self.failed}/{total}")
        print(f"⏱️  Duration: {duration:.1f} seconds")
        if total > 0:
            print(f"⚡ Average: {duration / total:.2f} sec/file")

        if self.failed_files:
            print(f"\n⚠️  Failed files ({len(self.failed_files)}):")
            for file_path, error in self.failed_files[:10]:
                print(f"   - {Path(file_path).name}: {error}")

        print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        file_patterns = sys.argv[1:]
        print(f"📋 Importing: {file_patterns}")
        importer = FreshBulkImporter(file_patterns=file_patterns)
    else:
        print("📋 Importing ALL from local_stats/")
        importer = FreshBulkImporter()

    importer.import_all()
