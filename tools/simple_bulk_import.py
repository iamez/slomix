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
        self.file_patterns = file_patterns
        self.parser = C0RNP0RN3StatsParser()
        self.processed = 0
        self.failed = 0
        self.skipped = 0
        self.failed_files = []
        self.dry_run = bool(dry_run)

    def get_stats_files(self):
        """Get .txt files to process (all or specific patterns)"""
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
            'INSERT INTO processed_files (filename, success, error_message) VALUES (?, ?, ?)',
            (filename, 1 if success else 0, error_msg),
        )

    def insert_session(self, conn, session_timestamp, result, filename):
        """Insert session and return session_id"""
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
                result.get('time_limit', ''),
                result.get('actual_time', ''),
            ),
        )
        return cursor.lastrowid

    def insert_player_stats(self, conn, session_id, session_date, result, player):
        """Insert player comprehensive stats"""
        cursor = conn.cursor()

        obj_stats = player.get('objective_stats', {})
        time_seconds = player.get('time_played_seconds', 0)
        time_minutes = time_seconds / 60.0 if time_seconds > 0 else 0.0

        dpm = player.get('dpm', 0.0)
        kills = player.get('kills', 0)
        deaths = player.get('deaths', 0)
        kd_ratio = kills / deaths if deaths > 0 else float(kills)

        bullets_fired = obj_stats.get('bullets_fired', 0)
        accuracy = player.get('accuracy', 0.0)

        # Get time_dead values
        time_dead_minutes = obj_stats.get('time_dead_minutes', 0.0)
        time_dead_ratio = obj_stats.get('time_dead_ratio', 0.0)

        player_guid = player.get('guid', '')
        player_name = player.get('name', '')
        clean_name = player_name

        cursor.execute(
            '''INSERT INTO player_comprehensive_stats (
                session_id, session_date, map_name, round_number,
                player_guid, player_name, clean_name, team,
                kills, deaths, damage_given, damage_received,
                team_damage_given, team_damage_received,
                gibs, self_kills, team_kills, team_gibs, headshot_kills,
                time_played_seconds, time_played_minutes, time_dead_minutes, time_dead_ratio,
                xp, kd_ratio, dpm, efficiency, bullets_fired, accuracy,
                kill_assists, objectives_completed, objectives_destroyed,
                objectives_stolen, objectives_returned,
                dynamites_planted, dynamites_defused,
                times_revived, revives_given,
                most_useful_kills, useless_kills, kill_steals,
                denied_playtime, constructions, tank_meatshield,
                double_kills, triple_kills, quad_kills, multi_kills, mega_kills,
                killing_spree_best, death_spree_worst
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                session_id,
                session_date,
                result['map_name'],
                result['round_num'],
                player_guid,
                player_name,
                clean_name,
                player.get('team', 0),
                kills,
                deaths,
                player.get('damage_given', 0),
                player.get('damage_received', 0),
                player.get('team_damage_given', 0),
                player.get('team_damage_received', 0),
                player.get('gibs', 0),
                player.get('self_kills', 0),
                obj_stats.get('team_kills', 0),
                obj_stats.get('team_gibs', 0),
                obj_stats.get('headshot_kills', 0),
                time_seconds,
                time_minutes,
                time_dead_minutes,
                time_dead_ratio,
                player.get('xp', 0),
                kd_ratio,
                dpm,
                accuracy,
                bullets_fired,
                accuracy,
                obj_stats.get('kill_assists', 0),
                obj_stats.get('objectives_completed', 0),
                obj_stats.get('objectives_destroyed', 0),
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
                obj_stats.get('constructions', 0),
                obj_stats.get('tank_meatshield', 0.0),
                obj_stats.get('double_kills', 0),
                obj_stats.get('triple_kills', 0),
                obj_stats.get('quad_kills', 0),
                obj_stats.get('multi_kills', 0),
                obj_stats.get('mega_kills', 0),
                obj_stats.get('killing_spree_best', 0),
                obj_stats.get('death_spree_worst', 0),
            ),
        )

    def insert_weapon_stats(self, conn, session_id, session_date, result, player):
        """Insert weapon stats for a player"""
        cursor = conn.cursor()

        player_guid = player.get('guid', '')
        player_name = player.get('name', '')
        weapons = player.get('weapons', {})

        for weapon_name, weapon in weapons.items():
            shots = weapon.get('shots', 0)
            hits = weapon.get('hits', 0)
            weapon_accuracy = (hits / shots * 100) if shots > 0 else 0.0

            cursor.execute(
                '''INSERT INTO weapon_comprehensive_stats (
                    session_id, session_date, map_name, round_number,
                    player_guid, player_name, weapon_name,
                    kills, deaths, headshots, shots, hits, accuracy
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
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
                    shots,
                    hits,
                    weapon_accuracy,
                ),
            )

    def process_file(self, file_path):
        """Process a single stats file"""
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
                print(f"[dry-run] {filename}: map={result.get('map_name','?')} round={result.get('round_num','?')}")
                print(f"[dry-run] players={len(players)}")
                for p in players[:3]:
                    obj = p.get('objective_stats', {})
                    td_ratio = obj.get('time_dead_ratio', 0)
                    time_seconds = p.get('time_played_seconds', 0)
                    print(f"  - {p.get('guid','?')[:8]}... / {p.get('name','?')}: time={time_seconds}s, td_ratio={td_ratio}")
                return

            try:
                session_id = self.insert_session(conn, session_timestamp, result, filename)

                for player in result.get('players', []):
                    self.insert_player_stats(conn, session_id, session_timestamp, result, player)
                    self.insert_weapon_stats(conn, session_id, session_timestamp, result, player)

                self.mark_file_processed(conn, filename, success=True)
                conn.commit()
                self.processed += 1

                if self.processed % 50 == 0:
                    print(f"✅ Processed {self.processed} files...")

            except Exception:
                try:
                    self.mark_file_processed(conn, filename, success=False, error_msg=str(sys.exc_info()[1]))
                    conn.commit()
                except Exception as mark_exc:
                    print(
                        f"⚠️ Failed to record import failure for {filename}: {mark_exc}",
                        file=sys.stderr,
                    )
                raise

        except Exception as e:
            self.failed += 1
            self.failed_files.append((str(file_path), str(e)))
            if self.failed <= 10:
                print(f"❌ Error processing {file_path.name}: {e}")

        finally:
            conn.close()

    def import_all(self):
        """Import all stats files"""
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
        if total > 0:
            print(f"⚡ Average: {duration / total:.2f} seconds per file")

        if self.failed_files:
            print(f"\n⚠️  Failed files ({len(self.failed_files)}):")
            for fp, error in self.failed_files:
                print(f"   - {Path(fp).name}: {error}")

        print("\n" + "=" * 60 + "\n")


def parse_args(argv=None):
    """Parse command line arguments"""
    p = argparse.ArgumentParser(description='Bulk import stats files to SQLite database')
    p.add_argument('patterns', nargs='*', help='File patterns to import (e.g. local_stats/*.txt)')
    p.add_argument('--dry-run', action='store_true', help='Parse files and print preview without writing to DB')
    p.add_argument('--db', default='bot/etlegacy_production.db', help='Path to sqlite DB')
    return p.parse_args(argv)


if __name__ == "__main__":
    args = parse_args()
    file_patterns = args.patterns or None
    importer = SimpleBulkImporter(db_path=args.db, file_patterns=file_patterns, dry_run=args.dry_run)
    importer.import_all()
