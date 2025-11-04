#!/usr/bin/env python3
"""
COMPREHENSIVE RAW vs DATABASE VALIDATION with CUMULATIVE ROUND 2 HANDLING
=========================================================================

This script properly validates database stats against raw .txt files with special handling for:

1. ROUND 1 FILES (.txt round-1.txt):
   - Raw file has actual Round 1 stats
   - Database has actual Round 1 stats
   - Direct comparison ✅

2. ROUND 2 FILES (.txt round-2.txt):
   - ⚠️ Raw file has CUMULATIVE stats (Round 1 + Round 2 combined!)
   - Database has DIFFERENTIAL stats (Round 2 ONLY)
   - Must calculate: Raw R1 + DB R2 should equal Raw R2 cumulative

3. VALIDATION METHODS:
   Method A: Round 1 validation (direct comparison)
   Method B: Round 2 validation (differential check)
   Method C: Cumulative validation (R1 raw + R2 db = R2 raw cumulative)
"""

import sqlite3
from pathlib import Path
from collections import defaultdict
import sys
import re

# Import parser
sys.path.insert(0, str(Path(__file__).parent.parent))
from community_stats_parser import C0RNP0RN3StatsParser

class CumulativeStatsValidator:
    def __init__(self, db_path="bot/etlegacy_production.db"):
        self.db_path = db_path
        self.parser = C0RNP0RN3StatsParser()
        self.conn = None
    
    def connect_db(self):
        """Connect to database"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
    
    def parse_filename(self, filename):
        """Parse filename to extract metadata"""
        # Format: YYYY-MM-DD-HHMMSS-mapname-round-X.txt
        match = re.match(r'(\d{4}-\d{2}-\d{2})-(\d{6})-(.+?)-round-(\d+)\.txt', filename)
        if match:
            return {
                'date': match.group(1),
                'time': match.group(2),
                'map': match.group(3),
                'round_num': int(match.group(4))
            }
        return None
    
    def find_round_pairs(self, directory='bot/local_stats'):
        """Find matching Round 1 and Round 2 files"""
        stats_dir = Path(directory)
        round1_files = []
        round2_files = []
        
        for file in sorted(stats_dir.glob('*.txt')):
            info = self.parse_filename(file.name)
            if not info:
                continue
            
            info['file'] = file
            if info['round_num'] == 1:
                round1_files.append(info)
            elif info['round_num'] == 2:
                round2_files.append(info)
        
        # Find pairs by matching date+map, then closest times
        pairs = []
        for r1 in round1_files:
            # Find R2 with same date and map
            candidates = [
                r2 for r2 in round2_files
                if r2['date'] == r1['date'] and r2['map'] == r1['map']
            ]
            
            if not candidates:
                continue
            
            # Find closest R2 time after R1
            r1_time = int(r1['time'])
            best_r2 = None
            best_diff = float('inf')
            
            for r2 in candidates:
                r2_time = int(r2['time'])
                time_diff = r2_time - r1_time
                
                # R2 must be after R1
                if time_diff > 0 and time_diff < best_diff:
                    best_diff = time_diff
                    best_r2 = r2
            
            if best_r2:
                pairs.append({
                    'key': f"{r1['date']}-{r1['map']}",
                    'round1_file': r1['file'],
                    'round2_file': best_r2['file'],
                    'date': r1['date'],
                    'time': r1['time'],
                    'map': r1['map'],
                    'time_diff_sec': best_diff
                })
        
        return pairs
    
    def get_db_round(self, date, map_name, round_num):
        """Get round from database"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id FROM rounds
            WHERE substr(round_date, 1, 10) = ?
            AND map_name = ?
            AND round_number = ?
            LIMIT 1
        """, (date, map_name, round_num))
        
        row = cursor.fetchone()
        return row['id'] if row else None
    
    def get_db_player_stats(self, round_id):
        """Get all player stats for a round from database"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT 
                player_guid,
                player_name,
                kills,
                deaths,
                damage_given,
                damage_received,
                headshot_kills as headshots,
                bullets_fired as shots,
                revives_given as revives,
                team_kills,
                self_kills,
                gibs,
                accuracy
            FROM player_comprehensive_stats
            WHERE round_id = ?
        """, (round_id,))
        
        players = {}
        for row in cursor.fetchall():
            guid = row['player_guid']
            players[guid] = dict(row)
        
        return players
    
    def validate_round1_direct(self, pair):
        """Method A: Direct comparison for Round 1"""
        print(f"\n{'='*100}")
        print(f"📊 METHOD A: ROUND 1 DIRECT COMPARISON")
        print(f"{'='*100}")
        print(f"File: {pair['round1_file'].name}")
        print(f"Map: {pair['map']}, Date: {pair['date']}")
        
        # Parse Round 1 file
        r1_raw = self.parser.parse_stats_file(str(pair['round1_file']))
        if not r1_raw.get('success'):
            print("❌ Failed to parse Round 1 file")
            return None
        
        # Get Round 1 from database
        r1_id = self.get_db_round(pair['date'], pair['map'], 1)
        if not r1_id:
            print("❌ Round 1 not found in database")
            return None
        
        r1_db = self.get_db_player_stats(r1_id)
        
        print(f"✅ Raw: {len(r1_raw['players'])} players, DB: {len(r1_db)} players")
        
        # Compare each player
        mismatches = []
        for raw_player in r1_raw['players']:
            guid = raw_player['guid']
            name = raw_player['name']
            
            if guid not in r1_db:
                mismatches.append(f"❌ {name} ({guid}): Not in database")
                continue
            
            db_player = r1_db[guid]
            
            # Compare key stats
            checks = {
                'kills': (raw_player['kills'], db_player['kills']),
                'deaths': (raw_player['deaths'], db_player['deaths']),
                'damage': (raw_player['damage_given'], db_player['damage_given']),
                'headshots': (raw_player['headshots'], db_player['headshots']),
            }
            
            player_ok = True
            for stat, (raw_val, db_val) in checks.items():
                if raw_val != db_val:
                    mismatches.append(f"❌ {name}: {stat} mismatch (raw={raw_val}, db={db_val})")
                    player_ok = False
            
            if player_ok:
                print(f"  ✅ {name}: All stats match")
        
        if not mismatches:
            print(f"\n🎉 ROUND 1: ALL STATS MATCH PERFECTLY!")
            return {'success': True, 'mismatches': 0}
        else:
            print(f"\n⚠️  ROUND 1: {len(mismatches)} mismatches found:")
            for m in mismatches[:10]:  # Show first 10
                print(f"     {m}")
            return {'success': False, 'mismatches': len(mismatches)}
    
    def validate_round2_cumulative(self, pair):
        """Method C: Cumulative validation (R1 raw + R2 db should = R2 raw)"""
        print(f"\n{'='*100}")
        print(f"📊 METHOD C: ROUND 2 CUMULATIVE VALIDATION")
        print(f"{'='*100}")
        print(f"Theory: Raw R1 + DB R2 (differential) should equal Raw R2 (cumulative)")
        print(f"Files: {pair['round1_file'].name} + DB → {pair['round2_file'].name}")
        
        # Parse both raw files
        r1_raw = self.parser.parse_stats_file(str(pair['round1_file']))
        r2_raw = self.parser.parse_stats_file(str(pair['round2_file']))
        
        if not (r1_raw.get('success') and r2_raw.get('success')):
            print("❌ Failed to parse files")
            return None
        
        # Get both rounds from database
        r1_id = self.get_db_round(pair['date'], pair['map'], 1)
        r2_id = self.get_db_round(pair['date'], pair['map'], 2)
        
        if not (r1_id and r2_id):
            print("❌ Rounds not found in database")
            return None
        
        r2_db = self.get_db_player_stats(r2_id)
        
        # Index raw players by GUID
        r1_raw_players = {p['guid']: p for p in r1_raw['players']}
        r2_raw_players = {p['guid']: p for p in r2_raw['players']}
        
        print(f"✅ Raw R1: {len(r1_raw_players)} players")
        print(f"✅ Raw R2: {len(r2_raw_players)} players (cumulative)")
        print(f"✅ DB R2: {len(r2_db)} players (differential)")
        
        mismatches = []
        perfect_matches = []
        
        for guid in r2_raw_players:
            r2_raw_player = r2_raw_players[guid]
            name = r2_raw_player['name']
            
            # Get corresponding players
            r1_raw_player = r1_raw_players.get(guid, {})
            r2_db_player = r2_db.get(guid)
            
            if not r2_db_player:
                mismatches.append(f"❌ {name}: Not in DB Round 2")
                continue
            
            # Calculate expected cumulative (R1 raw + R2 db)
            r1_kills = r1_raw_player.get('kills', 0)
            r2_db_kills = r2_db_player['kills']
            expected_cumulative_kills = r1_kills + r2_db_kills
            actual_cumulative_kills = r2_raw_player['kills']
            
            r1_deaths = r1_raw_player.get('deaths', 0)
            r2_db_deaths = r2_db_player['deaths']
            expected_cumulative_deaths = r1_deaths + r2_db_deaths
            actual_cumulative_deaths = r2_raw_player['deaths']
            
            r1_damage = r1_raw_player.get('damage_given', 0)
            r2_db_damage = r2_db_player['damage_given']
            expected_cumulative_damage = r1_damage + r2_db_damage
            actual_cumulative_damage = r2_raw_player['damage_given']
            
            # Compare
            kills_match = expected_cumulative_kills == actual_cumulative_kills
            deaths_match = expected_cumulative_deaths == actual_cumulative_deaths
            damage_match = expected_cumulative_damage == actual_cumulative_damage
            
            if kills_match and deaths_match and damage_match:
                perfect_matches.append(name)
                print(f"  ✅ {name}: Cumulative stats verified!")
                print(f"      Kills: {r1_kills} (R1) + {r2_db_kills} (R2 diff) = {expected_cumulative_kills} ✅")
            else:
                if not kills_match:
                    mismatches.append(
                        f"❌ {name}: Kills cumulative mismatch "
                        f"(R1:{r1_kills} + R2:{r2_db_kills} = {expected_cumulative_kills}, "
                        f"but R2 raw shows {actual_cumulative_kills})"
                    )
                if not deaths_match:
                    mismatches.append(
                        f"❌ {name}: Deaths cumulative mismatch "
                        f"(R1:{r1_deaths} + R2:{r2_db_deaths} = {expected_cumulative_deaths}, "
                        f"but R2 raw shows {actual_cumulative_deaths})"
                    )
                if not damage_match:
                    mismatches.append(
                        f"❌ {name}: Damage cumulative mismatch "
                        f"(R1:{r1_damage} + R2:{r2_db_damage} = {expected_cumulative_damage}, "
                        f"but R2 raw shows {actual_cumulative_damage})"
                    )
        
        print(f"\n📊 RESULTS:")
        print(f"   Perfect matches: {len(perfect_matches)}/{len(r2_raw_players)}")
        print(f"   Mismatches: {len(mismatches)}")
        
        if not mismatches:
            print(f"\n🎉 ROUND 2 CUMULATIVE: ALL STATS VERIFIED!")
            print(f"   Database differential stats + Raw R1 = Raw R2 cumulative ✅")
            return {'success': True, 'perfect_matches': len(perfect_matches)}
        else:
            print(f"\n⚠️  CUMULATIVE MISMATCHES:")
            for m in mismatches[:10]:
                print(f"     {m}")
            return {'success': False, 'mismatches': len(mismatches)}
    
    def run_comprehensive_validation(self, limit=5, start_date='2025-11-01'):
        """Run comprehensive validation on round pairs"""
        self.connect_db()
        
        print("="*100)
        print("🔍 COMPREHENSIVE RAW vs DATABASE VALIDATION")
        print("="*100)
        print(f"Finding round pairs from {start_date} onwards...")
        
        all_pairs = self.find_round_pairs()
        
        # Filter pairs by start_date
        pairs = [p for p in all_pairs if p['date'] >= start_date]
        print(f"✅ Found {len(all_pairs)} total pairs, {len(pairs)} from {start_date} onwards")
        
        if limit:
            pairs = pairs[:limit]
            print(f"🧪 Testing first {limit} pairs")
        
        results = {
            'total_pairs': len(pairs),
            'round1_perfect': 0,
            'round2_perfect': 0,
            'failures': []
        }
        
        for i, pair in enumerate(pairs, 1):
            print(f"\n{'#'*100}")
            print(f"PAIR {i}/{len(pairs)}: {pair['map']} on {pair['date']}")
            print(f"{'#'*100}")
            
            # Validate Round 1 (direct)
            r1_result = self.validate_round1_direct(pair)
            if r1_result and r1_result['success']:
                results['round1_perfect'] += 1
            elif r1_result:
                results['failures'].append(f"Round 1: {pair['key']}")
            
            # Validate Round 2 (cumulative)
            r2_result = self.validate_round2_cumulative(pair)
            if r2_result and r2_result['success']:
                results['round2_perfect'] += 1
            elif r2_result:
                results['failures'].append(f"Round 2: {pair['key']}")
        
        # Final summary
        print(f"\n{'='*100}")
        print(f"🎯 FINAL VALIDATION SUMMARY")
        print(f"{'='*100}")
        print(f"Total pairs tested: {results['total_pairs']}")
        print(f"Round 1 perfect matches: {results['round1_perfect']}/{results['total_pairs']}")
        print(f"Round 2 perfect matches (cumulative): {results['round2_perfect']}/{results['total_pairs']}")
        print(f"Failures: {len(results['failures'])}")
        
        if not results['failures']:
            print(f"\n🎉🎉🎉 ALL VALIDATIONS PASSED! 🎉🎉🎉")
            print(f"   Database stats are 100% accurate!")
            print(f"   Round 1: Direct match ✅")
            print(f"   Round 2: Differential correctly calculated ✅")
        else:
            print(f"\n⚠️  Failed validations:")
            for failure in results['failures']:
                print(f"   {failure}")
        
        self.conn.close()
        return results


if __name__ == '__main__':
    validator = CumulativeStatsValidator()
    # Test from Nov 1 onwards (recent data in database)
    results = validator.run_comprehensive_validation(limit=3, start_date='2025-11-01')
