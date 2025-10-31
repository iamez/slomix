#!/usr/bin/env python3
"""
Round Differential Calculator
=============================

Fixes the ET:Legacy c0rnp0rn3.lua cumulative stats issue where:
- Round 1: Shows actual Round 1 stats
- Round 2: Shows Round 1 + Round 2 combined (cumulative)

This tool calculates the actual Round 2 ONLY stats by differential analysis.
"""

import sqlite3
import os
from pathlib import Path
from community_stats_parser import C0RNP0RN3StatsParser

class RoundDifferentialCalculator:
    def __init__(self, db_path="etlegacy_fixed_bulk.db"):
        self.db_path = db_path
        self.parser = C0RNP0RN3StatsParser()
    
    def find_round_pairs(self, directory='stats_cache'):
        """Find matching Round 1 and Round 2 files"""
        round_pairs = []
        files = list(Path(directory).glob("*.txt"))
        
        print(f"🔍 Found {len(files)} total files in {directory}")
        
        for file in files:
            if "round-1" in file.name:
                print(f"📄 Round 1 file: {file.name}")
                # Look for corresponding round-2 file
                round2_name = file.name.replace("round-1", "round-2")
                round2_path = file.parent / round2_name
                
                print(f"🔍 Looking for: {round2_name}")
                
                if round2_path.exists():
                    print(f"✅ Found pair: {file.name} <-> {round2_name}")
                    round_pairs.append({
                        'round1': str(file),
                        'round2': str(round2_path),
                        'session_id': file.name.split('-')[0:4]  # Date-time prefix
                    })
                else:
                    print(f"❌ Missing Round 2: {round2_name}")
        
        return round_pairs
    
    def calculate_round2_differential(self, round1_data, round2_data):
        """Calculate actual Round 2 stats by subtracting Round 1 from Round 2"""
        if not (round1_data['success'] and round2_data['success']):
            return None
            
        # Verify they're from the same match
        if (round1_data['map_name'] != round2_data['map_name']):
            print(f"⚠️  Map mismatch: {round1_data['map_name']} vs {round2_data['map_name']}")
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
                    'rounds': r2_player['rounds'],
                    'kills': max(0, r2_player['kills'] - r1_player['kills']),
                    'deaths': max(0, r2_player['deaths'] - r1_player['deaths']),
                    'headshots': max(0, r2_player['headshots'] - r1_player['headshots']),
                    'damage_given': max(0, r2_player['damage_given'] - r1_player['damage_given']),
                    'damage_received': max(0, r2_player['damage_received'] - r1_player['damage_received']),
                    'shots_total': max(0, r2_player['shots_total'] - r1_player['shots_total']),
                    'hits_total': max(0, r2_player['hits_total'] - r1_player['hits_total']),
                    'weapon_stats': {}
                }
                
                # Calculate Round 2 time (assuming map times are cumulative)
                r1_time_sec = self.parser.parse_time_to_seconds(round1_data['actual_time'])
                r2_time_sec = self.parser.parse_time_to_seconds(round2_data['actual_time'])
                round2_only_sec = max(60, r2_time_sec - r1_time_sec)  # Minimum 1 minute
                
                # Calculate differential weapon stats
                for weapon_name in r2_player['weapon_stats']:
                    if weapon_name in r1_player['weapon_stats']:
                        r1_weapon = r1_player['weapon_stats'][weapon_name]
                        r2_weapon = r2_player['weapon_stats'][weapon_name]
                        
                        diff_weapon = {
                            'hits': max(0, r2_weapon['hits'] - r1_weapon['hits']),
                            'shots': max(0, r2_weapon['shots'] - r1_weapon['shots']),
                            'kills': max(0, r2_weapon['kills'] - r1_weapon['kills']),
                            'deaths': max(0, r2_weapon['deaths'] - r1_weapon['deaths']),
                            'headshots': max(0, r2_weapon['headshots'] - r1_weapon['headshots'])
                        }
                        
                        diff_weapon['accuracy'] = (diff_weapon['hits'] / diff_weapon['shots'] * 100) if diff_weapon['shots'] > 0 else 0
                        diff_player['weapon_stats'][weapon_name] = diff_weapon
                    else:
                        # New weapon in Round 2
                        diff_player['weapon_stats'][weapon_name] = r2_player['weapon_stats'][weapon_name]
                
                # Recalculate derived stats
                diff_player['kd_ratio'] = diff_player['kills'] / diff_player['deaths'] if diff_player['deaths'] > 0 else diff_player['kills']
                diff_player['accuracy'] = (diff_player['hits_total'] / diff_player['shots_total'] * 100) if diff_player['shots_total'] > 0 else 0
                diff_player['efficiency'] = diff_player['kills'] / (diff_player['kills'] + diff_player['deaths']) * 100 if (diff_player['kills'] + diff_player['deaths']) > 0 else 0
                
                # Calculate correct Round 2 DPM
                diff_player['dpm'] = (diff_player['damage_given'] / (round2_only_sec / 60)) if round2_only_sec > 0 else 0
                
                differential_players.append(diff_player)
            else:
                # Player only in Round 2 (joined mid-match)
                new_player = r2_player.copy()
                # Calculate DPM for full Round 2 time
                r2_time_sec = self.parser.parse_time_to_seconds(round2_data['actual_time'])
                new_player['dpm'] = (new_player['damage_given'] / (r2_time_sec / 60)) if r2_time_sec > 0 else 0
                differential_players.append(new_player)
        
        # Create corrected Round 2 data
        corrected_round2 = round2_data.copy()
        corrected_round2['players'] = differential_players
        corrected_round2['corrected'] = True
        corrected_round2['original_actual_time'] = round2_data['actual_time']
        
        # Calculate Round 2 only time
        r1_time_sec = self.parser.parse_time_to_seconds(round1_data['actual_time'])
        r2_time_sec = self.parser.parse_time_to_seconds(round2_data['actual_time'])
        round2_only_sec = max(60, r2_time_sec - r1_time_sec)
        corrected_round2['round2_only_time'] = f"{round2_only_sec // 60}:{round2_only_sec % 60:02d}"
        
        return corrected_round2
    
    def analyze_directory(self, directory):
        """Analyze all round pairs in a directory"""
        round_pairs = self.find_round_pairs(directory)
        results = []
        
        print(f"🔍 Found {len(round_pairs)} round pairs to analyze")
        
        for i, pair in enumerate(round_pairs, 1):
            print(f"\n📊 Analyzing pair {i}/{len(round_pairs)}")
            print(f"   Round 1: {os.path.basename(pair['round1'])}")
            print(f"   Round 2: {os.path.basename(pair['round2'])}")
            
            # Parse both rounds
            round1_data = self.parser.parse_stats_file(pair['round1'])
            round2_data = self.parser.parse_stats_file(pair['round2'])
            
            if not (round1_data['success'] and round2_data['success']):
                print(f"   ❌ Parse error - skipping")
                continue
            
            # Calculate differential
            corrected_round2 = self.calculate_round2_differential(round1_data, round2_data)
            
            if corrected_round2:
                results.append({
                    'round1': round1_data,
                    'round2_original': round2_data,
                    'round2_corrected': corrected_round2,
                    'files': pair
                })
                print(f"   ✅ Differential calculated successfully")
                
                # Show sample stats
                if corrected_round2['players']:
                    sample_player = corrected_round2['players'][0]
                    original_player = next(p for p in round2_data['players'] if p['guid'] == sample_player['guid'])
                    
                    print(f"   📈 Sample: {sample_player['name']}")
                    print(f"      Original Round 2 DPM: {original_player.get('dpm', 0):.1f}")
                    print(f"      Corrected Round 2 DPM: {sample_player['dpm']:.1f}")
            else:
                print(f"   ❌ Could not calculate differential")
        
        return results


def test_differential_calculation():
    """Test the differential calculation with sample files"""
    calculator = RoundDifferentialCalculator()
    
    # Test with stats_cache directory
    cache_dir = "stats_cache"
    if os.path.exists(cache_dir):
        print(f"🧪 Testing differential calculation with {cache_dir}")
        results = calculator.analyze_directory(cache_dir)
        
        if results:
            print(f"\n🎯 DIFFERENTIAL ANALYSIS COMPLETE")
            print(f"   Processed: {len(results)} round pairs")
            print(f"   Ready for corrected database import!")
            
            return results
        else:
            print("❌ No valid round pairs found")
    else:
        print(f"❌ Directory {cache_dir} not found")
    
    return []


if __name__ == "__main__":
    test_differential_calculation()