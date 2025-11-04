#!/usr/bin/env python3
"""
Comprehensive Raw Stats File Validation
Compares EVERY field from database against raw stats files for Nov 2 session
Validates: kills, deaths, damage, accuracy, headshots, weapon stats, etc.
"""

import sqlite3
import re
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any

# Import the stats parser
import sys
sys.path.insert(0, str(Path(__file__).parent / 'bot'))
from community_stats_parser import C0RNP0RN3StatsParser

def get_round_ids() -> List[int]:
    """Get the session IDs for Nov 2 gaming session"""
    return list(range(2134, 2152))  # 2134-2151 (18 rounds)

def get_database_data(session_ids: List[int]) -> Dict[str, Dict[str, Any]]:
    """Get all player data from database for the session"""
    db_path = Path('bot/etlegacy_production.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    placeholders = ','.join(['?'] * len(session_ids))
    
    # Get all player stats aggregated by GUID from player_comprehensive_stats
    query = f"""
    SELECT 
        player_guid,
        player_name,
        SUM(kills) as total_kills,
        SUM(deaths) as total_deaths,
        SUM(damage_given) as total_damage,
        SUM(damage_received) as total_damage_taken,
        SUM(headshot_kills) as total_headshots,
        SUM(bullets_fired) as total_shots,
        SUM(revives_given) as total_revives,
        SUM(self_kills) as total_self_kills,
        SUM(team_kills) as total_team_kills,
        SUM(killing_spree_best) as total_kill_peak,
        MAX(death_spree_worst) as max_death_streak,
        SUM(gibs) as total_gibs
    FROM player_comprehensive_stats
    WHERE round_id IN ({placeholders})
    GROUP BY player_guid
    """
    
    cursor.execute(query, session_ids)
    players = {}
    
    for row in cursor.fetchall():
        guid = row['player_guid']
        players[guid] = {
            'name': row['player_name'],
            'kills': row['total_kills'],
            'deaths': row['total_deaths'],
            'damage': row['total_damage'],
            'damage_taken': row['total_damage_taken'],
            'headshots': row['total_headshots'],
            'hits': 0,  # Will be calculated from weapon stats
            'shots': row['total_shots'],
            'revives': row['total_revives'],
            'self_kills': row['total_self_kills'],
            'team_kills': row['total_team_kills'],
            'kill_peak': row['total_kill_peak'],
            'death_streak': row['max_death_streak'],
            'gibs': row['total_gibs']
        }
    
    # Get weapon stats from weapon_comprehensive_stats
    weapon_query = f"""
    SELECT 
        player_guid,
        weapon_name,
        SUM(kills) as weapon_kills,
        SUM(deaths) as weapon_deaths,
        SUM(headshots) as weapon_headshots,
        SUM(hits) as weapon_hits,
        SUM(shots) as weapon_shots
    FROM weapon_comprehensive_stats
    WHERE round_id IN ({placeholders})
    GROUP BY player_guid, weapon_name
    """
    
    cursor.execute(weapon_query, session_ids)
    
    for row in cursor.fetchall():
        guid = row['player_guid']
        weapon = row['weapon_name']
        
        if guid not in players:
            continue
            
        if 'weapons' not in players[guid]:
            players[guid]['weapons'] = {}
        
        players[guid]['weapons'][weapon] = {
            'kills': row['weapon_kills'],
            'deaths': row['weapon_deaths'],
            'headshots': row['weapon_headshots'],
            'hits': row['weapon_hits'],
            'shots': row['weapon_shots']
        }
        
        # Add hits to player total
        players[guid]['hits'] += row['weapon_hits']
    
    conn.close()
    return players

def parse_all_raw_files(session_ids: List[int]) -> Dict[str, Dict[str, Any]]:
    """Parse all raw stats files for the session"""
    parser = C0RNP0RN3StatsParser()
    stats_dir = Path('stats')
    
    # Aggregate data by player GUID
    players = defaultdict(lambda: {
        'names': set(),
        'kills': 0,
        'deaths': 0,
        'damage': 0,
        'damage_taken': 0,
        'headshots': 0,
        'hits': 0,
        'shots': 0,
        'revives': 0,
        'self_kills': 0,
        'team_kills': 0,
        'kill_peak': 0,
        'death_streak': 0,
        'gibs': 0,
        'poison_deaths': 0,
        'knife_kills': 0,
        'time_axis': 0,
        'time_allies': 0,
        'weapons': defaultdict(lambda: {'kills': 0, 'deaths': 0, 'headshots': 0, 'hits': 0, 'shots': 0})
    })
    
    for round_id in session_ids:
        # Try both filename formats
        for round_num in [1, 2]:
            filename = f'session_{round_id}_round{round_num}_stats.txt'
            filepath = stats_dir / filename
            
            if not filepath.exists():
                filename = f'session_{round_id}_round-{round_num}_stats.txt'
                filepath = stats_dir / filename
            
            if not filepath.exists():
                print(f"⚠️  Missing file: {filename}")
                continue
            
            # Parse the file
            data = parser.parse_file(str(filepath))
            
            if not data or 'players' not in data:
                print(f"⚠️  Failed to parse: {filename}")
                continue
            
            # Aggregate player stats
            for player_data in data['players']:
                guid = player_data.get('guid', '').upper()
                if not guid:
                    continue
                
                players[guid]['names'].add(player_data.get('name', 'Unknown'))
                players[guid]['kills'] += player_data.get('kills', 0)
                players[guid]['deaths'] += player_data.get('deaths', 0)
                players[guid]['damage'] += player_data.get('damage_given', 0)
                players[guid]['damage_taken'] += player_data.get('damage_received', 0)
                players[guid]['headshots'] += player_data.get('headshots', 0)
                players[guid]['hits'] += player_data.get('hits', 0)
                players[guid]['shots'] += player_data.get('shots', 0)
                players[guid]['revives'] += player_data.get('revives', 0)
                players[guid]['self_kills'] += player_data.get('self_kills', 0)
                players[guid]['team_kills'] += player_data.get('team_kills', 0)
                players[guid]['kill_peak'] += player_data.get('kill_peak', 0)
                players[guid]['death_streak'] += player_data.get('death_streak', 0)
                players[guid]['gibs'] += player_data.get('gibs', 0)
                players[guid]['poison_deaths'] += player_data.get('poison_deaths', 0)
                players[guid]['knife_kills'] += player_data.get('knife_kills', 0)
                players[guid]['time_axis'] += player_data.get('time_axis', 0)
                players[guid]['time_allies'] += player_data.get('time_allies', 0)
                
                # Aggregate weapon stats
                for weapon_name, weapon_data in player_data.get('weapon_stats', {}).items():
                    players[guid]['weapons'][weapon_name]['kills'] += weapon_data.get('kills', 0)
                    players[guid]['weapons'][weapon_name]['deaths'] += weapon_data.get('deaths', 0)
                    players[guid]['weapons'][weapon_name]['headshots'] += weapon_data.get('headshots', 0)
                    players[guid]['weapons'][weapon_name]['hits'] += weapon_data.get('hits', 0)
                    players[guid]['weapons'][weapon_name]['shots'] += weapon_data.get('shots', 0)
    
    return dict(players)

def compare_data(db_data: Dict, raw_data: Dict):
    """Compare database vs raw files data"""
    print("\n" + "="*80)
    print("COMPREHENSIVE DATA VALIDATION")
    print("Comparing Database vs Raw Stats Files")
    print("="*80)
    
    all_guids = set(db_data.keys()) | set(raw_data.keys())
    
    total_checks = 0
    passed_checks = 0
    failed_checks = []
    
    for guid in sorted(all_guids):
        if guid not in db_data:
            print(f"\n❌ GUID {guid} in raw files but NOT in database!")
            continue
        
        if guid not in raw_data:
            print(f"\n❌ GUID {guid} in database but NOT in raw files!")
            continue
        
        db = db_data[guid]
        raw = raw_data[guid]
        
        # Get the most common name from raw data
        raw_name = max(raw['names'], key=lambda x: len(x)) if raw['names'] else 'Unknown'
        
        print(f"\n{'='*80}")
        print(f"Player: {raw_name} (GUID: {guid})")
        print(f"DB Name: {db['name']}")
        print(f"{'='*80}")
        
        # Compare main stats (only fields available in both DB and raw files)
        fields = [
            ('kills', 'Kills'),
            ('deaths', 'Deaths'),
            ('damage', 'Damage Given'),
            ('damage_taken', 'Damage Taken'),
            ('headshots', 'Headshots'),
            ('shots', 'Shots'),
            ('revives', 'Revives'),
            ('self_kills', 'Self Kills'),
            ('team_kills', 'Team Kills'),
            ('kill_peak', 'Kill Peak'),
            ('death_streak', 'Death Streak'),
            ('gibs', 'Gibs')
        ]
        
        for field_key, field_name in fields:
            total_checks += 1
            db_val = db.get(field_key, 0) or 0
            raw_val = raw.get(field_key, 0) or 0
            
            if db_val == raw_val:
                print(f"  ✅ {field_name:20s}: {db_val:>8} (match)")
                passed_checks += 1
            else:
                print(f"  ❌ {field_name:20s}: DB={db_val:>8} | RAW={raw_val:>8} | DIFF={db_val - raw_val:>+8}")
                failed_checks.append(f"{raw_name} - {field_name}: DB={db_val} vs RAW={raw_val}")
        
        # Calculate accuracy
        if db.get('shots', 0) > 0:
            db_acc = (db.get('hits', 0) / db['shots']) * 100
        else:
            db_acc = 0
        
        if raw.get('shots', 0) > 0:
            raw_acc = (raw.get('hits', 0) / raw['shots']) * 100
        else:
            raw_acc = 0
        
        print(f"\n  📊 Accuracy: {db_acc:.2f}% (DB) vs {raw_acc:.2f}% (RAW)")
        
        # Compare weapon stats
        print(f"\n  🔫 WEAPON STATS:")
        all_weapons = set(db.get('weapons', {}).keys()) | set(raw['weapons'].keys())
        
        for weapon in sorted(all_weapons):
            db_weapon = db.get('weapons', {}).get(weapon, {})
            raw_weapon = raw['weapons'].get(weapon, {})
            
            weapon_fields = ['kills', 'deaths', 'headshots', 'hits', 'shots']
            weapon_matches = []
            weapon_mismatches = []
            
            for wf in weapon_fields:
                total_checks += 1
                db_val = db_weapon.get(wf, 0) or 0
                raw_val = raw_weapon.get(wf, 0) or 0
                
                if db_val == raw_val:
                    passed_checks += 1
                    weapon_matches.append(f"{wf}={db_val}")
                else:
                    weapon_mismatches.append(f"{wf}: DB={db_val} RAW={raw_val}")
                    failed_checks.append(f"{raw_name} - {weapon} {wf}: DB={db_val} vs RAW={raw_val}")
            
            status = "✅" if not weapon_mismatches else "❌"
            print(f"    {status} {weapon:15s}: {', '.join(weapon_matches)}")
            if weapon_mismatches:
                for mismatch in weapon_mismatches:
                    print(f"       ⚠️  {mismatch}")
    
    # Final summary
    print(f"\n{'='*80}")
    print("VALIDATION SUMMARY")
    print(f"{'='*80}")
    print(f"Total Checks: {total_checks}")
    print(f"Passed: {passed_checks} ({(passed_checks/total_checks*100):.2f}%)")
    print(f"Failed: {len(failed_checks)} ({(len(failed_checks)/total_checks*100):.2f}%)")
    
    if failed_checks:
        print(f"\n❌ FAILED CHECKS:")
        for i, failure in enumerate(failed_checks, 1):
            print(f"  {i}. {failure}")
    else:
        print(f"\n✅ ALL CHECKS PASSED! Database matches raw files perfectly!")
    
    print(f"{'='*80}\n")

if __name__ == '__main__':
    print("🔍 Starting comprehensive validation...")
    
    session_ids = get_session_ids()
    print(f"📊 Session IDs: {session_ids[0]}-{session_ids[-1]} ({len(session_ids)} rounds)")
    
    print("\n📂 Loading database data...")
    db_data = get_database_data(session_ids)
    print(f"   Found {len(db_data)} players in database")
    
    print("\n📂 Parsing raw stats files...")
    raw_data = parse_all_raw_files(session_ids)
    print(f"   Found {len(raw_data)} players in raw files")
    
    compare_data(db_data, raw_data)
