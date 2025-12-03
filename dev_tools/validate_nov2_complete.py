#!/usr/bin/env python3
"""
Comprehensive Nov 2 Session Validation
Compares EVERY field from raw stats files vs database
Based on understanding: c0rnp0rn3.lua -> parser -> database

Field Mapping (Parser -> Database):
- kills -> kills
- deaths -> deaths  
- damage_given -> damage_given
- damage_received -> damage_received
- headshots -> headshot_kills
- gibs -> gibs
- self_kills -> self_kills
- team_kills -> team_kills
- team_damage_given -> team_damage_given
- team_damage_received -> team_damage_received
- revives_given -> revives_given
- objective_stats fields map directly to DB columns
"""

import sqlite3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / 'bot'))
from community_stats_parser import C0RNP0RN3StatsParser

# Session IDs for Nov 2 evening gaming session (excluding orphan)
SESSION_IDS = list(range(2134, 2152))  # 2134-2151 (18 rounds)

def get_nov2_files():
    """Get all Nov 2 stats files (excluding orphan at 00:06)"""
    stats_dir = Path('local_stats')
    files = sorted([f for f in stats_dir.glob('2025-11-02*.txt') if '000624' not in f.name])
    return files

def parse_raw_file(filepath):
    """Parse raw stats file using C0RNP0RN3StatsParser"""
    parser = C0RNP0RN3StatsParser()
    result = parser.parse_stats_file(str(filepath))
    
    if not result or not result.get('success'):
        print(f"  [FAIL] Failed to parse {filepath.name}")
        return None
    
    # Build dict by GUID
    players_by_guid = {}
    for player in result.get('players', []):
        guid = player.get('guid', '')
        if guid:
            players_by_guid[guid] = player
    
    return players_by_guid

def get_db_stats(round_id):
    """Get player and weapon stats from database for a session"""
    db_path = Path('bot/etlegacy_production.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get player stats
    cursor.execute("""
        SELECT 
            player_guid, player_name, kills, deaths, damage_given, damage_received,
            team_damage_given, team_damage_received, gibs, self_kills, team_kills,
            team_gibs, headshot_kills, revives_given, times_revived,
            bullets_fired, xp, kd_ratio, dpm, efficiency,
            kill_assists, objectives_stolen, objectives_returned,
            dynamites_planted, dynamites_defused,
            most_useful_kills, useless_kills, kill_steals,
            double_kills, triple_kills, quad_kills, multi_kills, mega_kills,
            killing_spree_best, death_spree_worst,
            denied_playtime, constructions, tank_meatshield
        FROM player_comprehensive_stats
        WHERE round_id = ?
    """, (round_id,))
    
    players = {}
    for row in cursor.fetchall():
        guid = row['player_guid']
        players[guid] = {
            'name': row['player_name'],
            'kills': row['kills'],
            'deaths': row['deaths'],
            'damage_given': row['damage_given'],
            'damage_received': row['damage_received'],
            'team_damage_given': row['team_damage_given'],
            'team_damage_received': row['team_damage_received'],
            'gibs': row['gibs'],
            'self_kills': row['self_kills'],
            'team_kills': row['team_kills'],
            'team_gibs': row['team_gibs'],
            'headshots': row['headshot_kills'],
            'revives_given': row['revives_given'],
            'times_revived': row['times_revived'],
            'bullets_fired': row['bullets_fired'],
            'xp': row['xp'],
            'killing_spree': row['killing_spree_best'],
            'death_spree': row['death_spree_worst'],
            'kill_assists': row['kill_assists'],
            'objectives_stolen': row['objectives_stolen'],
            'objectives_returned': row['objectives_returned'],
            'dynamites_planted': row['dynamites_planted'],
            'dynamites_defused': row['dynamites_defused'],
            'useful_kills': row['most_useful_kills'],
            'useless_kills': row['useless_kills'],
            'kill_steals': row['kill_steals'],
            'double_kills': row['double_kills'],
            'triple_kills': row['triple_kills'],
            'quad_kills': row['quad_kills'],
            'multi_kills': row['multi_kills'],
            'mega_kills': row['mega_kills'],
            'denied_playtime': row['denied_playtime'],
            'constructions': row['constructions'],
            'weapons': {}
        }
    
    # Get weapon stats
    cursor.execute("""
        SELECT player_guid, weapon_name, kills, deaths, headshots, hits, shots
        FROM weapon_comprehensive_stats
        WHERE round_id = ?
    """, (round_id,))
    
    for row in cursor.fetchall():
        guid = row['player_guid']
        if guid in players:
            weapon = row['weapon_name']
            players[guid]['weapons'][weapon] = {
                'kills': row['kills'],
                'deaths': row['deaths'],
                'headshots': row['headshots'],
                'hits': row['hits'],
                'shots': row['shots']
            }
    
    conn.close()
    return players

def compare_round(filepath, round_id):
    """Compare a single round file vs database"""
    print(f"\n{'='*80}")
    print(f"Round: {filepath.name}")
    print(f"Round ID: {round_id}")
    print(f"{'='*80}")
    
    # Parse raw file
    raw_players = parse_raw_file(filepath)
    if not raw_players:
        print("  [FAIL] Could not parse raw file")
        return 0, 1
    
    # Get DB stats
    db_players = get_db_stats(round_id)
    
    print(f"Players: {len(raw_players)} in file, {len(db_players)} in DB")
    
    passed = 0
    failed = 0
    
    all_guids = set(raw_players.keys()) | set(db_players.keys())
    
    for guid in sorted(all_guids):
        if guid not in raw_players:
            print(f"  [FAIL] {guid}: IN DB BUT NOT IN RAW FILE")
            failed += 1
            continue
        
        if guid not in db_players:
            print(f"  [FAIL] {guid}: IN RAW FILE BUT NOT IN DB")
            failed += 1
            continue
        
        raw = raw_players[guid]
        db = db_players[guid]
        obj = raw.get('objective_stats', {})
        
        # Compare main stats
        mismatches = []
        
        # Core stats
        if raw.get('kills') != db.get('kills'):
            mismatches.append(f"kills: R{raw.get('kills')} != D{db.get('kills')}")
        if raw.get('deaths') != db.get('deaths'):
            mismatches.append(f"deaths: R{raw.get('deaths')} != D{db.get('deaths')}")
        if raw.get('damage_given') != db.get('damage_given'):
            mismatches.append(f"damage_given: R{raw.get('damage_given')} != D{db.get('damage_given')}")
        if raw.get('damage_received') != db.get('damage_received'):
            mismatches.append(f"damage_received: R{raw.get('damage_received')} != D{db.get('damage_received')}")
        if raw.get('headshots') != db.get('headshots'):
            mismatches.append(f"headshots: R{raw.get('headshots')} != D{db.get('headshots')}")
        if obj.get('gibs') != db.get('gibs'):
            mismatches.append(f"gibs: R{obj.get('gibs')} != D{db.get('gibs')}")
        if obj.get('self_kills') != db.get('self_kills'):
            mismatches.append(f"self_kills: R{obj.get('self_kills')} != D{db.get('self_kills')}")
        if obj.get('team_kills') != db.get('team_kills'):
            mismatches.append(f"team_kills: R{obj.get('team_kills')} != D{db.get('team_kills')}")
        if obj.get('team_damage_given') != db.get('team_damage_given'):
            mismatches.append(f"team_damage_given: R{obj.get('team_damage_given')} != D{db.get('team_damage_given')}")
        if obj.get('team_damage_received') != db.get('team_damage_received'):
            mismatches.append(f"team_damage_received: R{obj.get('team_damage_received')} != D{db.get('team_damage_received')}")
        if obj.get('revives_given') != db.get('revives_given'):
            mismatches.append(f"revives_given: R{obj.get('revives_given')} != D{db.get('revives_given')}")
        if obj.get('times_revived') != db.get('times_revived'):
            mismatches.append(f"times_revived: R{obj.get('times_revived')} != D{db.get('times_revived')}")
        
        # Extended stats
        if obj.get('xp') != db.get('xp'):
            mismatches.append(f"xp: R{obj.get('xp')} != D{db.get('xp')}")
        if obj.get('kill_assists') != db.get('kill_assists'):
            mismatches.append(f"kill_assists: R{obj.get('kill_assists')} != D{db.get('kill_assists')}")
        if obj.get('kill_steals') != db.get('kill_steals'):
            mismatches.append(f"kill_steals: R{obj.get('kill_steals')} != D{db.get('kill_steals')}")
        if obj.get('useful_kills') != db.get('useful_kills'):
            mismatches.append(f"useful_kills: R{obj.get('useful_kills')} != D{db.get('useful_kills')}")
        if obj.get('useless_kills') != db.get('useless_kills'):
            mismatches.append(f"useless_kills: R{obj.get('useless_kills')} != D{db.get('useless_kills')}")
        if obj.get('killing_spree') != db.get('killing_spree'):
            mismatches.append(f"killing_spree: R{obj.get('killing_spree')} != D{db.get('killing_spree')}")
        if obj.get('death_spree') != db.get('death_spree'):
            mismatches.append(f"death_spree: R{obj.get('death_spree')} != D{db.get('death_spree')}")
        
        # Compare weapon stats
        all_weapons = set(raw.get('weapon_stats', {}).keys()) | set(db.get('weapons', {}).keys())
        weapon_mismatches = []
        
        for weapon in all_weapons:
            raw_w = raw.get('weapon_stats', {}).get(weapon, {})
            db_w = db.get('weapons', {}).get(weapon, {})
            
            for field in ['kills', 'deaths', 'headshots', 'hits', 'shots']:
                raw_val = raw_w.get(field, 0) or 0
                db_val = db_w.get(field, 0) or 0
                if raw_val != db_val:
                    weapon_mismatches.append(f"{weapon}.{field}: R{raw_val} != D{db_val}")
        
        if mismatches or weapon_mismatches:
            print(f"  [FAIL] {raw.get('name')} ({guid})")
            for m in mismatches:
                print(f"      {m}")
            for wm in weapon_mismatches:
                print(f"      {wm}")
            failed += 1
        else:
            print(f"  [OK] {raw.get('name')} ({guid}) - ALL FIELDS MATCH")
            passed += 1
    
    return passed, failed

def main():
    print("COMPREHENSIVE NOV 2 SESSION VALIDATION")
    print("Comparing ALL fields from raw files vs database")
    print("="*80)
    
    files = get_nov2_files()
    print(f"\nFound {len(files)} Nov 2 files (excluding orphan)")
    print(f"Session IDs: {SESSION_IDS[0]}-{SESSION_IDS[-1]} ({len(SESSION_IDS)} sessions)")
    
    if len(files) != len(SESSION_IDS):
        print(f"\n[WARN] File count mismatch! {len(files)} files but {len(SESSION_IDS)} sessions")
    
    total_passed = 0
    total_failed = 0
    
    for i, filepath in enumerate(files):
        if i < len(SESSION_IDS):
            round_id = SESSION_IDS[i]
            passed, failed = compare_round(filepath, round_id)
            total_passed += passed
            total_failed += failed
        else:
            print(f"\n[WARN] No round ID for file: {filepath.name}")
    
    print(f"\n{'='*80}")
    print("FINAL SUMMARY")
    print(f"{'='*80}")
    print(f"Total player-round validations: {total_passed + total_failed}")
    print(f"[OK] Passed: {total_passed}")
    print(f"[FAIL] Failed: {total_failed}")
    
    if total_failed == 0:
        print("\nPERFECT! All data matches between raw files and database!")
    else:
        accuracy = (total_passed / (total_passed + total_failed) * 100) if (total_passed + total_failed) > 0 else 0
        print(f"\nAccuracy: {accuracy:.2f}%")
    
    print(f"{'='*80}\n")

if __name__ == '__main__':
    main()
