#!/usr/bin/env python3
"""
Quick Database Population for Testing Discord Commands
Creates test data in comprehensive database for immediate Discord command testing
"""

import sqlite3
import json
from datetime import datetime, date, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('QuickPopulation')

def populate_test_data():
    """Populate comprehensive database with realistic test data"""
    
    db_path = "etlegacy_comprehensive.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        logger.info("🎯 Creating realistic test data for Discord commands...")
        
        # Create test sessions for the last few days
        test_dates = [
            (date.today() - timedelta(days=2), 'et_supply', 1),
            (date.today() - timedelta(days=2), 'et_supply', 2),
            (date.today() - timedelta(days=1), 'et_goldrush', 1),
            (date.today() - timedelta(days=1), 'et_goldrush', 2),
            (date.today(), 'etl_adlernest', 1),
        ]
        
        session_ids = []
        for session_date, map_name, round_num in test_dates:
            cursor.execute("""
                INSERT OR REPLACE INTO sessions 
                (session_date, map_name, round_number, server_name, config_name, 
                 defender_team, winner_team, time_limit, next_time_limit)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_date.isoformat(), map_name, round_num, 
                'ET:Legacy Community Server', 'etpub',
                1 if round_num == 1 else 2,  # Defender team
                2 if round_num == 1 else 1,  # Winner team (opposite)
                '20:00', '20:00'
            ))
            session_ids.append(cursor.lastrowid)
        
        logger.info(f"✅ Created {len(session_ids)} test sessions")
        
        # Create realistic player data
        test_players = [
            {
                'guid': 'SEAREAL01',
                'name': 'seareal',
                'discord_id': '123456789012345678',
                'discord_name': 'seareal#1234',
                'skill_level': 'high'
            },
            {
                'guid': 'ZEBRA001',
                'name': 'zebra',
                'discord_id': '234567890123456789', 
                'discord_name': 'zebra#5678',
                'skill_level': 'expert'
            },
            {
                'guid': 'KANI0001',
                'name': 'KaNii',
                'discord_id': '345678901234567890',
                'discord_name': 'kani#9012',
                'skill_level': 'medium'
            },
            {
                'guid': 'NEWBIE01',
                'name': 'NewPlayer',
                'discord_id': None,
                'discord_name': None,
                'skill_level': 'beginner'
            },
            {
                'guid': 'VETERAN1',
                'name': 'OldSchool',
                'discord_id': '456789012345678901',
                'discord_name': 'oldschool#3456',
                'skill_level': 'high'
            }
        ]
        
        # Create player links for Discord integration
        for player in test_players:
            if player['discord_id']:
                cursor.execute("""
                    INSERT OR REPLACE INTO player_links 
                    (et_guid, discord_id, discord_username, player_name)
                    VALUES (?, ?, ?, ?)
                """, (
                    player['guid'], player['discord_id'], 
                    player['discord_name'], player['name']
                ))
        
        logger.info(f"✅ Created {len([p for p in test_players if p['discord_id']])} player links")
        
        # Generate realistic stats for each player in each session
        player_stats_count = 0
        weapon_stats_count = 0
        
        for session_id, (session_date, map_name, round_num) in zip(session_ids, test_dates):
            for player in test_players:
                # Generate stats based on skill level
                skill_multiplier = {
                    'beginner': 0.4,
                    'medium': 0.7,
                    'high': 1.0,
                    'expert': 1.3
                }[player['skill_level']]
                
                # Base stats
                base_kills = int(20 * skill_multiplier + (round_num - 1) * 5)
                kills = max(5, base_kills + (hash(player['name'] + str(session_id)) % 10 - 5))
                deaths = max(3, int(kills * (0.6 + (1 - skill_multiplier) * 0.4)))
                damage_given = kills * 130 + (hash(str(session_id) + player['name']) % 500)
                
                # Advanced stats
                headshot_kills = max(1, int(kills * (0.15 + skill_multiplier * 0.1)))
                bullets_fired = kills * (8 + hash(player['guid']) % 5) + 50
                accuracy = min(65.0, 15 + skill_multiplier * 25 + (hash(player['name']) % 15))
                dpm = (damage_given / 15.0) + (skill_multiplier - 0.5) * 50
                
                # Sprees and multikills
                killing_spree_best = max(0, int(skill_multiplier * 8) + (hash(str(session_id)) % 3))
                double_kills = max(0, int(kills / 8) + (hash(player['guid'] + str(session_id)) % 3))
                triple_kills = 1 if skill_multiplier > 0.8 and hash(player['name']) % 3 == 0 else 0
                
                # Objectives
                dynamites_planted = 1 if hash(player['guid'] + map_name) % 4 == 0 else 0
                dynamites_defused = 1 if hash(player['name'] + map_name) % 5 == 0 else 0
                kill_assists = max(2, int(kills * 0.3))
                times_revived = hash(player['name'] + str(session_id)) % 4
                repairs_constructions = 1 if hash(player['guid']) % 3 == 0 else 0
                
                # Insert comprehensive player stats
                cursor.execute("""
                    INSERT INTO player_comprehensive_stats (
                        session_id, player_guid, player_name, clean_name, team, rounds,
                        kills, deaths, damage_given, damage_received, 
                        headshot_kills, bullets_fired, dpm, kd_ratio, accuracy,
                        killing_spree_best, kill_assists, double_kills, triple_kills,
                        dynamites_planted, dynamites_defused, times_revived, repairs_constructions,
                        time_played_minutes, xp, processed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id, player['guid'], player['name'], player['name'],
                    1 if hash(player['name']) % 2 == 0 else 2,  # Random team
                    1,  # rounds
                    kills, deaths, damage_given, int(damage_given * 0.7),  # damage_received
                    headshot_kills, bullets_fired, dpm, kills/max(deaths, 1), accuracy,
                    killing_spree_best, kill_assists, double_kills, triple_kills,
                    dynamites_planted, dynamites_defused, times_revived, repairs_constructions,
                    15.0 + (session_id % 5),  # time_played_minutes
                    kills * 15 + headshot_kills * 5,  # xp
                    datetime.now().isoformat()
                ))
                
                player_stats_id = cursor.lastrowid
                player_stats_count += 1
                
                # Create weapon stats for top weapons
                weapons = [
                    ('MP40', 0.3), ('Thompson', 0.25), ('Sten', 0.15), 
                    ('FG42', 0.1), ('Luger', 0.08), ('Panzerfaust', 0.07), ('Grenade', 0.05)
                ]
                
                for weapon_name, kill_ratio in weapons:
                    weapon_kills = max(0, int(kills * kill_ratio))
                    if weapon_kills > 0:
                        weapon_attempts = weapon_kills * (6 + hash(weapon_name) % 4)
                        weapon_hits = int(weapon_attempts * (accuracy / 100.0))
                        weapon_headshots = max(0, int(weapon_kills * 0.2)) if weapon_name not in ['Panzerfaust', 'Grenade'] else 0
                        
                        cursor.execute("""
                            INSERT INTO weapon_comprehensive_stats (
                                player_stats_id, weapon_id, weapon_name,
                                hits, attempts, kills, headshots, accuracy
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            player_stats_id, hash(weapon_name) % 28, weapon_name,
                            weapon_hits, weapon_attempts, weapon_kills, weapon_headshots,
                            (weapon_hits / weapon_attempts * 100) if weapon_attempts > 0 else 0
                        ))
                        weapon_stats_count += 1
        
        conn.commit()
        conn.close()
        
        logger.info("📊 Test Data Summary:")
        logger.info(f"   Sessions: {len(session_ids)}")
        logger.info(f"   Player stats records: {player_stats_count}")
        logger.info(f"   Weapon stats records: {weapon_stats_count}")
        logger.info(f"   Player links: {len([p for p in test_players if p['discord_id']])}")
        
        logger.info("\n🎮 Test Discord Commands:")
        logger.info("   !stats seareal")
        logger.info("   !stats @seareal")
        logger.info(f"   !stats seareal {date.today().strftime('%d.%m.%Y')}")
        logger.info(f"   !session_stats {date.today().strftime('%d.%m')}")
        logger.info("   !link NewPlayer")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error creating test data: {e}")
        return False

if __name__ == "__main__":
    logger.info("🚀 Creating comprehensive test data for Discord commands...")
    
    if populate_test_data():
        logger.info("🎉 Test data created successfully!")
        logger.info("💡 You can now test Discord commands!")
    else:
        logger.error("❌ Failed to create test data")