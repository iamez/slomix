#!/usr/bin/env python3
"""Simple Bulk Import for Seconds-Based Schema
Imports all stats files from local_stats/ into production database.

This cleaned implementation supports a safe --dry-run mode which parses
files and prints a small preview without writing to the database.
"""

import argparse
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

    def __init__(self, db_path="bot/etlegacy_production.db", stats_dir="local_stats", file_patterns=None, dry_run=False):
        self.db_path = db_path
        self.stats_dir = stats_dir
        self.file_patterns = file_patterns  # Optional: specific files to import
        self.parser = C0RNP0RN3StatsParser()
        self.processed = 0
        self.failed = 0
        self.skipped = 0
        self.failed_files = []
        self.dry_run = bool(dry_run)

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

    def insert_session(self, conn, session_timestamp, result, filename):
        """Insert session and return session_id"""
        cursor = conn.cursor()

        # Use timestamp (YYYY-MM-DD-HHMMSS) for unique session identification
        cursor.execute(
            '''
            SELECT id FROM sessions
            WHERE session_date = ? AND map_name = ? AND round_number = ?
            ''',
            (session_timestamp, result['map_name'], result['round_num']),
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
                session_timestamp,  # Use timestamp for uniqueness
                result['map_name'],
                result['round_num'],
                result.get('defender_team', 0),
                result.get('winner_team', 0),
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
        #!/usr/bin/env python3
        """Simple Bulk Import for Seconds-Based Schema
        Cleaned canonical importer with --dry-run support and robust INSERT generation.
        """

        import argparse
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

            def __init__(self, db_path="bot/etlegacy_production.db", stats_dir="local_stats", file_patterns=None, dry_run=False):
                self.db_path = db_path
                self.stats_dir = stats_dir
                self.file_patterns = file_patterns
                self.parser = C0RNP0RN3StatsParser()
                self.processed = 0
                self.failed = 0
                self.skipped = 0
                self.failed_files = []
                self.dry_run = bool(dry_run)

            def get_stats_files(self):
                files = []
                if self.file_patterns:
                    for pattern in self.file_patterns:
                        matched = glob.glob(pattern)
                        files.extend([Path(f) for f in matched])
                    return sorted(set(files))

                stats_path = Path(self.stats_dir)
                if not stats_path.exists():
                    raise Exception(f"Stats directory not found: {self.stats_dir}")
                return sorted(stats_path.glob("*.txt"))

            def is_file_processed(self, conn, filename):
                cursor = conn.cursor()
                result = cursor.execute('SELECT 1 FROM processed_files WHERE filename = ?', (filename,)).fetchone()
                return result is not None

            def mark_file_processed(self, conn, filename, success=True, error_msg=None):
                cursor = conn.cursor()
                cursor.execute(
                    'INSERT INTO processed_files (filename, success, error_message) VALUES (?, ?, ?)',
                    (filename, 1 if success else 0, error_msg),
                )

            def insert_session(self, conn, session_timestamp, result, filename):
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT id FROM sessions WHERE session_date = ? AND map_name = ? AND round_number = ?',
                    (session_timestamp, result['map_name'], result['round_num']),
                )
                existing = cursor.fetchone()
                if existing:
                    return existing[0]

                cursor.execute(
                    '''INSERT INTO sessions (session_date, map_name, round_number, defender_team, winner_team, time_limit, actual_time)
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (
                        session_timestamp,
                        result['map_name'],
                        result['round_num'],
                        result.get('defender_team', 0),
                        result.get('winner_team', 0),
                        result.get('map_time', ''),
                        result.get('actual_time', ''),
                    ),
                )
                return cursor.lastrowid

            def insert_player_stats(self, conn, session_id, session_date, result, player):
                cursor = conn.cursor()
                obj_stats = player.get('objective_stats', {})

                time_seconds = player.get('time_played_seconds', 0)
                time_minutes = time_seconds / 60.0 if time_seconds > 0 else 0.0

                dpm = player.get('dpm', 0.0)
                kills = player.get('kills', 0)
                deaths = player.get('deaths', 0)
                kd_ratio = kills / deaths if deaths > 0 else float(kills)

                bullets_fired = obj_stats.get('bullets_fired', 0)
                accuracy = (kills / bullets_fired * 100) if bullets_fired > 0 else 0.0
                efficiency = accuracy

                raw_td = obj_stats.get('time_dead_ratio', 0) or 0
                try:
                    raw_td_f = float(raw_td)
                except Exception:
                    raw_td_f = 0.0

                td_percent = raw_td_f * 100.0 if raw_td_f <= 1.0 else raw_td_f
                time_dead_mins = time_minutes * (td_percent / 100.0)
                time_dead_ratio = td_percent

                # Columns in exact order to match DB schema
                columns = [
                    'session_id', 'session_date', 'map_name', 'round_number',
                    'player_guid', 'player_name', 'clean_name', 'team',
                    'kills', 'deaths', 'damage_given', 'damage_received',
                    'team_damage_given', 'team_damage_received',
                    'gibs', 'self_kills', 'team_kills', 'team_gibs', 'headshot_kills',
                    'time_played_seconds', 'time_played_minutes',
                    'time_dead_minutes', 'time_dead_ratio',
                    'xp', 'kd_ratio', 'dpm', 'efficiency',
                    'bullets_fired', 'accuracy',
                    'kill_assists',
                    'objectives_completed', 'objectives_destroyed',
                    'objectives_stolen', 'objectives_returned',
                    'dynamites_planted', 'dynamites_defused',
                    'times_revived', 'revives_given',
                    'most_useful_kills', 'useless_kills', 'kill_steals',
                    'denied_playtime', 'constructions', 'tank_meatshield',
                    'double_kills', 'triple_kills', 'quad_kills',
                    'multi_kills', 'mega_kills',
                    'killing_spree_best', 'death_spree_worst',
                ]

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

                # Ensure values and columns match and build SQL dynamically
                if len(values) != len(columns):
                    raise Exception(f"Schema mismatch: values={len(values)} columns={len(columns)}")

                cols_sql = ', '.join(columns)
                placeholders_sql = ', '.join('?' for _ in columns)
                sql = f"INSERT INTO player_comprehensive_stats ({cols_sql}) VALUES ({placeholders_sql})"

                cursor.execute(sql, values)

            def insert_weapon_stats(self, conn, session_id, session_date, result, player):
                cursor = conn.cursor()

                weapon_stats = player.get('weapon_stats', {})
                if not weapon_stats:
                    return

                player_guid = player.get('guid', '')
                player_name = player.get('name', '')

                for weapon_name, weapon in weapon_stats.items():
                    cursor.execute(
                        '''INSERT INTO weapon_comprehensive_stats (
                               session_id, session_date, map_name, round_number,
                               player_guid, player_name, weapon_name,
                               kills, deaths, headshots, shots, hits
                           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
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

            def process_file(self, file_path):
                filename = file_path.name
                conn = sqlite3.connect(self.db_path)

                try:
                    if self.is_file_processed(conn, filename):
                        self.skipped += 1
                        if self.skipped <= 5:
                            print(f"⏭️  Skipping {filename} (already processed)")
                        return

                    session_timestamp = '-'.join(filename.split('-')[:4])

                    result = self.parser.parse_stats_file(str(file_path))
                    if not result.get('success'):
                        raise Exception(result.get('error', 'parser_failed'))

                    if self.dry_run:
                        players = result.get('players', [])
                        print(f"[dry-run] {filename}: parsed session_date={result.get('session_date','?')} map={result.get('map_name','?')} rounds={result.get('round_num','?')}")
                        print(f"[dry-run] players={len(players)} (showing up to 3)")
                        for p in players[:3]:
                            obj = p.get('objective_stats', {})
                            raw_td = obj.get('time_dead_ratio', 0) or 0
                            try:
                                raw_td_f = float(raw_td)
                            except Exception:
                                raw_td_f = 0.0
                            td_percent = raw_td_f * 100.0 if raw_td_f <= 1.0 else raw_td_f
                            time_seconds = p.get('time_played_seconds', 0)
                            time_minutes = time_seconds / 60.0 if time_seconds > 0 else 0.0
                            computed_td_minutes = time_minutes * (td_percent / 100.0)
                            print(f"  - {p.get('guid','?')} / {p.get('name','?')}: time_min={time_minutes:.2f}, td_ratio={td_percent}, td_min(computed)={computed_td_minutes:.2f}")
                        return

                    # Insert session + players
                    session_id = self.insert_session(conn, session_timestamp, result, filename)

                    for player in result.get('players', []):
                        self.insert_player_stats(conn, session_id, session_timestamp, result, player)
                        self.insert_weapon_stats(conn, session_id, session_timestamp, result, player)

                    self.mark_file_processed(conn, filename, success=True)
                    conn.commit()
                    self.processed += 1

                except Exception as e:
                    # Record failure and try to persist it
                    try:
                        self.mark_file_processed(conn, filename, success=False, error_msg=str(e))
                        conn.commit()
                    except Exception:
                        pass
                    self.failed += 1
                    self.failed_files.append((str(file_path), str(e)))
                    if self.failed <= 10:
                        print(f"❌ Error processing {file_path.name}: {e}")

                finally:
                    conn.close()

            def import_all(self):
                print("\n" + "=" * 60)
                print("🚀 Starting Bulk Import")
                print("=" * 60)

                files = self.get_stats_files()
                total = len(files)
                print(f"\n📁 Found {total} stats files")
                print(f"📊 Database: {self.db_path}")
                print(f"⏱️  Starting import at {datetime.now().strftime('%H:%M:%S')}\n")

                start_time = datetime.now()
                for file_path in files:
                    self.process_file(file_path)
                duration = (datetime.now() - start_time).total_seconds()

                print("\n" + "=" * 60)
                print("📊 IMPORT COMPLETE")
                print("=" * 60)
                print(f"✅ Successfully imported: {self.processed}/{total} files")
                print(f"⏭️  Skipped (already processed): {self.skipped}/{total} files")
                print(f"❌ Failed: {self.failed}/{total} files")
                print(f"⏱️  Duration: {duration:.1f} seconds")


        def parse_args(argv=None):
            p = argparse.ArgumentParser()
            p.add_argument('patterns', nargs='*', help='File patterns to import (e.g. local_stats/*.txt)')
            p.add_argument('--dry-run', action='store_true', help='Parse files and print preview without writing to DB')
            p.add_argument('--db', default='bot/etlegacy_production.db', help='Path to sqlite DB')
            return p.parse_args(argv)


        if __name__ == "__main__":
            args = parse_args()
            file_patterns = args.patterns or None
            importer = SimpleBulkImporter(db_path=args.db, file_patterns=file_patterns, dry_run=args.dry_run)
            importer.import_all()
                ),
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

            # Extract timestamp from filename: YYYY-MM-DD-HHMMSS-mapname-round-N.txt
            session_timestamp = '-'.join(filename.split('-')[:4])  # YYYY-MM-DD-HHMMSS

            # Parse file
            result = self.parser.parse_stats_file(str(file_path))

            if not result.get('success'):
                error_msg = result.get('error', 'Unknown error')
                raise Exception(f"Parser failed: {error_msg}")

            try:
                # Insert session and player/weapon stats
                session_id = self.insert_session(conn, session_timestamp, result, filename)

                for player in result.get('players', []):
                    self.insert_player_stats(conn, session_id, session_timestamp, result, player)
                    self.insert_weapon_stats(conn, session_id, session_timestamp, result, player)

                # Mark processed and commit
                self.mark_file_processed(conn, filename, success=True)
                conn.commit()

                self.processed += 1

                # Progress update every 50 files
                if self.processed % 50 == 0:
                    print(f"✅ Processed {self.processed} files...")

            except Exception:
                # Try to record failure state in processed_files
                try:
                    self.mark_file_processed(conn, filename, success=False, error_msg=str(sys.exc_info()[1]))
                    conn.commit()
                except Exception:
                    pass
                raise

        except Exception as e:
            self.failed += 1
            self.failed_files.append((str(file_path), str(e)))

            if self.failed <= 10:  # Only show first 10 errors
                print(f"❌ Error processing {file_path.name}: {e}")

        finally:
            conn.close()

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
        print(f"✅ Successfully imported: {self.processed}/{total} files")
        print(f"⏭️  Skipped (already processed): {self.skipped}/{total} files")
        print(f"❌ Failed: {self.failed}/{total} files")
        print(f"⏱️  Duration: {duration:.1f} seconds")
        if total > 0:
            print(f"⚡ Average: {duration / total:.2f} seconds per file")

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
