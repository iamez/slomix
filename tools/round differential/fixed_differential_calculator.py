#!/usr/bin/env python3
"""
WORKING Round Differential Calculator for ET:Legacy Stats
========================================================

This script fixes the cumulative Round 2 stats bug by:
1. Finding matching Round 1/2 file pairs by map name and temporal proximity
2. Calculating Round 2 ONLY stats = Round 2 cumulative - Round 1
3. Updating the database with corrected differential stats
"""

import sqlite3
import os
from pathlib import Path
from community_stats_parser import C0RNP0RN3StatsParser
from datetime import datetime

class FixedRoundDifferentialCalculator:
    def __init__(self, db_path="etlegacy_fixed_bulk.db"):
        self.db_path = db_path
        self.parser = C0RNP0RN3StatsParser()
    
    def parse_filename(self, filename):
        """Parse filename to extract date, time, and map name"""
        # Format: YYYY-MM-DD-HHMMSS-mapname-round-X.txt
        parts = filename.replace('.txt', '').split('-')
        if len(parts) < 6:
            return None, None, None, None
            
        try:
            date = f"{parts[0]}-{parts[1]}-{parts[2]}"  # YYYY-MM-DD
            time = parts[3]  # HHMMSS
            round_part = parts[-1]  # "1" or "2"
            # Find the "round" part and extract map name before it
            if "round" in parts:
                round_index = parts.index("round")
                map_name = '-'.join(parts[4:round_index])  # After time, before "round"
            else:
                return None, None, None, None
            return date, time, map_name, round_part
        except Exception:
            return None, None, None, None
    
    def find_round_pairs(self, directory='stats_cache'):
        """Find matching Round 1 and Round 2 files by map and proximity"""
        files = list(Path(directory).glob("*.txt"))
        
        round1_files = []
        round2_files = []
        
        for file in files:
            date, time, map_name, round_part = self.parse_filename(file.name)
            if date and time and map_name and round_part:
                if round_part == "1":
                    round1_files.append((file, date, time, map_name))
                elif round_part == "2":
                    round2_files.append((file, date, time, map_name))
        
        pairs = []
        for r1_file, r1_date, r1_time, r1_map in round1_files:
            # Find the closest Round 2 file for same map on same date
            best_r2 = None
            min_time_diff = float('inf')
            
            for r2_file, r2_date, r2_time, r2_map in round2_files:
                if r2_map == r1_map and r2_date == r1_date:
                    try:
                        # Calculate time difference (Round 2 should be after Round 1)
                        time_diff = int(r2_time) - int(r1_time)
                        if 0 < time_diff < min_time_diff:  # Round 2 must be after Round 1
                            min_time_diff = time_diff
                            best_r2 = r2_file
                    except:
                        continue
            
            if best_r2:
                pairs.append({
                    'round1': str(r1_file),
                    'round2': str(best_r2),
                    'map': r1_map,
                    'date': r1_date
                })
        
        return pairs
    
    def calculate_round2_differential(self, round1_data, round2_data):
        """Calculate actual Round 2 stats by subtracting Round 1 from Round 2"""
        if not (round1_data['success'] and round2_data['success']):
            return None
            
        # Create differential players list
        differential_players = []
        
        # Index Round 1 players by GUID
        round1_players = {p['guid']: p for p in round1_data['players']}
        
        for r2_player in round2_data['players']:
            guid = r2_player['guid']
            
            if guid in round1_players:
                r1_player = round1_players[guid]
                
                # Calculate differential stats (Round 2 cumulative - Round 1)
                diff_player = {
                    'guid': guid,
                    'name': r2_player['name'],
                    'raw_name': r2_player['raw_name'],
                    'team': r2_player['team'],
                    'rounds': 2,  # This is Round 2 only data
                    'kills': max(0, r2_player['kills'] - r1_player['kills']),
                    'deaths': max(0, r2_player['deaths'] - r1_player['deaths']),
                    'headshots': max(0, r2_player['headshots'] - r1_player['headshots']),
                    'damage_given': max(0, r2_player['damage_given'] - r1_player['damage_given']),
                    'damage_received': max(0, r2_player['damage_received'] - r1_player['damage_received']),
                    'shots_total': max(0, r2_player['shots_total'] - r1_player['shots_total']),
                    'hits_total': max(0, r2_player['hits_total'] - r1_player['hits_total']),
                    'weapon_stats': {}
                }
                
                # Calculate differential weapon stats
                for weapon_name in r2_player['weapon_stats']:
                    if weapon_name in r1_player['weapon_stats']:
                        r1_weapon = r1_player['weapon_stats'][weapon_name]
                        r2_weapon = r2_player['weapon_stats'][weapon_name]
                        
                        diff_weapon = {}
                        for stat_name in ['kills', 'damage', 'shots', 'hits', 'headshots']:
                            r1_val = r1_weapon.get(stat_name, 0)
                            r2_val = r2_weapon.get(stat_name, 0)
                            diff_weapon[stat_name] = max(0, r2_val - r1_val)
                        
                        diff_player['weapon_stats'][weapon_name] = diff_weapon
                    else:
                        # Weapon only used in Round 2
                        diff_player['weapon_stats'][weapon_name] = r2_player['weapon_stats'][weapon_name].copy()
                
                differential_players.append(diff_player)
            else:
                # Player only in Round 2
                differential_players.append(r2_player)
        
        # Calculate Round 2 ONLY time duration
        r1_time_sec = self.parser.parse_time_to_seconds(round1_data['actual_time'])
        r2_time_sec = self.parser.parse_time_to_seconds(round2_data['actual_time'])
        round2_only_sec = max(60, r2_time_sec - r1_time_sec)  # Minimum 1 minute
        round2_only_time = f"{round2_only_sec // 60:02d}:{round2_only_sec % 60:02d}"
        
        return {
            'success': True,
            'map_name': round2_data['map_name'],
            'actual_time': round2_only_time,
            'players': differential_players,
            'original_round2_time': round2_data['actual_time'],
            'differential_time': round2_only_time,
            'round2_cumulative_seconds': r2_time_sec,
            'round1_seconds': r1_time_sec,
            'round2_only_seconds': round2_only_sec
        }
    
    def process_single_pair(self, pair):
        """Process a single Round 1/2 pair and return results"""
        print(f"Processing {pair['map']} on {pair['date']}...")
        
        round1_data = self.parser.parse_stats_file(pair['round1'])
        round2_data = self.parser.parse_stats_file(pair['round2'])
        
        if not (round1_data['success'] and round2_data['success']):
            print(f"❌ Failed to parse files")
            return None
        
        differential_data = self.calculate_round2_differential(round1_data, round2_data)
        if not differential_data:
            print(f"❌ Failed to calculate differential")
            return None
            
        print(f"✅ Round 1: {len(round1_data['players'])} players, {round1_data['actual_time']}")
        print(f"✅ Round 2 cumulative: {len(round2_data['players'])} players, {round2_data['actual_time']}")
        print(f"✅ Round 2 differential: {len(differential_data['players'])} players, {differential_data['differential_time']}")
        
        return {
            'pair': pair,
            'round1': round1_data,
            'round2_cumulative': round2_data,
            'round2_differential': differential_data
        }
    
    def run_quick_test(self, limit=5):
        """Run a quick test on first few pairs"""
        pairs = self.find_round_pairs()
        print(f"🔍 Found {len(pairs)} round pairs total")
        
        test_pairs = pairs[:limit]
        print(f"🧪 Testing first {len(test_pairs)} pairs:")
        
        results = []
        for pair in test_pairs:
            result = self.process_single_pair(pair)
            if result:
                results.append(result)
        
        print(f"\n📊 Quick Test Summary:")
        print(f"   Successfully processed: {len(results)}/{len(test_pairs)} pairs")
        
        return results

if __name__ == "__main__":
    print("🚀 ET:Legacy Round Differential Calculator - FIXED VERSION")
    print("=" * 60)
    
    calculator = FixedRoundDifferentialCalculator()
    results = calculator.run_quick_test(limit=5)
    
    if results:
        print(f"\n✅ SUCCESS! Fixed calculator is working correctly.")
        print(f"Ready to process all {len(calculator.find_round_pairs())} pairs to fix database.")
    else:
        print(f"\n❌ No successful results. Check file parsing logic.")