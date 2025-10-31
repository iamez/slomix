#!/usr/bin/env python3
"""
Simulate Bot Import of Real C0RNP0RN3.lua Stats Files
Tests the bot's ability to import and parse actual stats files into comprehensive database
"""

import os
import sys
import sqlite3
from pathlib import Path
import logging
from datetime import datetime, date

# Add the bot directory to path so we can import the parser
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'bot'))

try:
    from community_stats_parser import C0RNP0RN3StatsParser
    parser_available = True
    print("✅ Successfully imported C0RNP0RN3StatsParser")
except ImportError as e:
    parser_available = False
    print(f"❌ Could not import parser: {e}")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('BotImportTest')

class BotStatsImporter:
    """Simulates the bot's stats import functionality"""
    
    def __init__(self):
        self.db_path = "dev/etlegacy_comprehensive.db"
        self.parser = C0RNP0RN3StatsParser() if parser_available else None
        self.processed_files = 0
        self.failed_files = 0
        
    def initialize_fresh_database(self):
        """Initialize a fresh comprehensive database"""
        logger.info("🗑️ Clearing database for fresh import test...")
        
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
            
        # Use our comprehensive database schema
        from initialize_database import initialize_comprehensive_database
        conn, cursor = initialize_comprehensive_database()
        conn.close()
        
        logger.info("✅ Fresh comprehensive database initialized")
        
    def process_stats_file(self, file_path):
        """Process a single stats file like the bot would"""
        
        if not self.parser:
            logger.error("❌ Parser not available")
            return False
            
        try:
            logger.info(f"📄 Processing: {file_path.name}")
            
            # Parse the file
            stats_data = self.parser.parse_stats_file(str(file_path))
            
            if stats_data.get('error'):
                logger.warning(f"⚠️ Parse error: {stats_data['error']}")
                return False
                
            # Extract session info from filename
            filename = file_path.name
            date_str = filename[:10]  # 2024-03-24
            session_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            map_name = stats_data.get('map_name', 'unknown')
            round_num = 2 if 'round-2' in filename else 1
            
            # Store in comprehensive database
            return self.store_comprehensive_stats(stats_data, session_date, map_name, round_num)
            
        except Exception as e:
            logger.error(f"❌ Error processing {file_path.name}: {e}")
            self.failed_files += 1
            return False
    
    def store_comprehensive_stats(self, stats_data, session_date, map_name, round_num):
        """Store parsed stats in comprehensive database format"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Create or get session
            cursor.execute("""
                INSERT OR IGNORE INTO sessions 
                (session_date, map_name, round_number, server_name, config_name, 
                 defender_team, winner_team, time_limit, next_time_limit)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_date.isoformat(), map_name, round_num,
                'ET:Legacy Community Server', 'etpub',
                1, 2, '20:00', '20:00'
            ))
            
            cursor.execute("""
                SELECT id FROM sessions 
                WHERE session_date = ? AND map_name = ? AND round_number = ?
            """, (session_date.isoformat(), map_name, round_num))
            
            session_id = cursor.fetchone()[0]
            
            # Process players
            players_added = 0
            weapons_added = 0
            
            for player in stats_data.get('players', []):
                player_guid = player.get('guid', 'UNKNOWN')
                if player_guid == 'UNKNOWN':
                    continue
                    
                player_name = player.get('name', 'Unknown')
                clean_name = player.get('clean_name', player_name)
                team = player.get('team', 1)
                
                # Extract all comprehensive stats from C0RNP0RN3.lua format
                # This maps the actual parsed data to our comprehensive schema
                
                cursor.execute("""
                    INSERT INTO player_comprehensive_stats (
                        session_id, player_guid, player_name, clean_name, team,
                        kills, deaths, damage_given, damage_received,
                        killing_spree_best, death_spree_worst, kill_assists, kill_steals,
                        headshot_kills, objectives_stolen, objectives_returned,
                        dynamites_planted, dynamites_defused, times_revived,
                        bullets_fired, dpm, tank_meatshield, time_dead_ratio,
                        most_useful_kills, denied_playtime, useless_kills,
                        double_kills, triple_kills, quad_kills,
                        kd_ratio, accuracy, headshot_ratio,
                        time_played_minutes, xp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id, player_guid, player_name, clean_name, team,
                    # Map the actual data from C0RNP0RN3.lua format
                    player.get('kills', 0),
                    player.get('deaths', 0), 
                    player.get('damage_given', 0),
                    player.get('damage_received', 0),
                    player.get('killing_spree_best', 0),
                    player.get('death_spree_worst', 0),
                    player.get('kill_assists', 0),
                    player.get('kill_steals', 0),
                    player.get('headshot_kills', 0),
                    player.get('objectives_stolen', 0),
                    player.get('objectives_returned', 0),
                    player.get('dynamites_planted', 0),
                    player.get('dynamites_defused', 0),
                    player.get('times_revived', 0),
                    player.get('bullets_fired', 0),
                    player.get('dpm', 0.0),
                    player.get('tank_meatshield', 0.0),
                    player.get('time_dead_ratio', 0.0),
                    player.get('most_useful_kills', 0),
                    player.get('denied_playtime', 0),
                    player.get('useless_kills', 0),
                    player.get('double_kills', 0),
                    player.get('triple_kills', 0),
                    player.get('quad_kills', 0),
                    player.get('kd_ratio', 0.0),
                    player.get('accuracy', 0.0),
                    player.get('headshot_ratio', 0.0),
                    player.get('time_played_minutes', 0.0),
                    player.get('xp', 0)
                ))
                
                players_added += 1
                
                # Add weapon stats if available
                for weapon_id, weapon_data in player.get('weapons', {}).items():
                    if isinstance(weapon_data, dict) and weapon_data.get('kills', 0) > 0:
                        cursor.execute("""
                            INSERT INTO weapon_comprehensive_stats 
                            (session_id, player_guid, weapon_id, weapon_name, kills, hits, shots, headshots, accuracy)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            session_id, player_guid, int(weapon_id), 
                            weapon_data.get('name', f'Weapon_{weapon_id}'),
                            weapon_data.get('kills', 0),
                            weapon_data.get('hits', 0),
                            weapon_data.get('shots', 0),
                            weapon_data.get('headshots', 0),
                            weapon_data.get('accuracy', 0.0)
                        ))
                        weapons_added += 1
            
            conn.commit()
            logger.info(f"✅ Stored: {players_added} players, {weapons_added} weapon stats")
            self.processed_files += 1
            return True
            
        except Exception as e:
            logger.error(f"❌ Database error: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def run_import_test(self, max_files=10):
        """Run the bot import simulation"""
        
        logger.info("🚀 SIMULATING BOT IMPORT OF REAL C0RNP0RN3.LUA FILES")
        logger.info("=" * 70)
        
        if not parser_available:
            logger.error("❌ Cannot run test - parser not available")
            return
            
        # Initialize fresh database
        self.initialize_fresh_database()
        
        # Find stats files (get larger ones that have actual content)
        stats_dir = Path("local_stats")
        if not stats_dir.exists():
            logger.error(f"❌ Stats directory not found: {stats_dir}")
            return
            
        stats_files = list(stats_dir.glob("*.txt"))
        # Sort by file size to get files with actual content first
        stats_files.sort(key=lambda f: f.stat().st_size, reverse=True)
        
        logger.info(f"📁 Found {len(stats_files)} stats files")
        
        if not stats_files:
            logger.error("❌ No stats files found")
            return
            
        # Process files (limit for testing, start with largest)
        files_to_process = stats_files[:max_files]
        logger.info(f"🎯 Processing {len(files_to_process)} largest files for testing...")
        
        for i, file_path in enumerate(files_to_process, 1):
            logger.info(f"📄 [{i}/{len(files_to_process)}] Size: {file_path.stat().st_size} bytes")
            self.process_stats_file(file_path)
        
        # Show results
        self.show_import_results()
    
    def show_import_results(self):
        """Show what was imported"""
        
        logger.info(f"\n📊 IMPORT RESULTS:")
        logger.info(f"   ✅ Files processed: {self.processed_files}")
        logger.info(f"   ❌ Files failed: {self.failed_files}")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Show database contents
        cursor.execute("SELECT COUNT(*) FROM sessions")
        session_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM player_comprehensive_stats")
        player_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT player_guid) FROM player_comprehensive_stats")
        unique_players = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM weapon_comprehensive_stats")
        weapon_count = cursor.fetchone()[0]
        
        logger.info(f"\n🎮 DATABASE CONTENTS:")
        logger.info(f"   📅 Sessions: {session_count}")
        logger.info(f"   👤 Player records: {player_count}")
        logger.info(f"   🆔 Unique players: {unique_players}")
        logger.info(f"   🔫 Weapon stats: {weapon_count}")
        
        # Show some players
        if unique_players > 0:
            logger.info(f"\n👥 IMPORTED PLAYERS:")
            cursor.execute("""
                SELECT DISTINCT player_guid, clean_name, COUNT(*) as rounds
                FROM player_comprehensive_stats 
                GROUP BY player_guid, clean_name
                ORDER BY rounds DESC
                LIMIT 10
            """)
            
            for guid, name, rounds in cursor.fetchall():
                logger.info(f"   {name:<15} {guid:<12} ({rounds} rounds)")
        
        conn.close()
        
        if unique_players > 0:
            logger.info(f"\n🎉 SUCCESS! Bot import functionality working!")
            logger.info(f"💡 Now you can run Discord linking on real players")
            logger.info(f"📝 Next: python dev/link_discord_users.py")
        else:
            logger.info(f"\n❌ No players imported - check parser compatibility")

def main():
    """Run the bot import simulation"""
    importer = BotStatsImporter()
    importer.run_import_test(max_files=5)  # Test with 5 files first

if __name__ == "__main__":
    main()