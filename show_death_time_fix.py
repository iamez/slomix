#!/usr/bin/env python3
"""Show actual death time values from a real stats file pair."""

from bot.community_stats_parser import C0RNP0RN3StatsParser
import os

parser = C0RNP0RN3StatsParser()
stats_dir = 'local_stats'
files = os.listdir(stats_dir)
r1_files = [f for f in files if 'round-1' in f]

print("=" * 70)
print("REAL STATS FILE ANALYSIS - DEATH TIME FIX DEMONSTRATION")
print("=" * 70)
print()

found = False
for r1 in r1_files:
    r2 = r1.replace('round-1', 'round-2')
    if r2 not in files:
        continue
    
    r1_path = os.path.join(stats_dir, r1)
    r2_path = os.path.join(stats_dir, r2)
    
    r1_data = parser.parse_file(r1_path)
    r2_data = parser.parse_file(r2_path)
    
    if not (r1_data.get('success') and r2_data.get('success')):
        continue
    
    # Find a player with meaningful death time
    for p in r2_data['players'][:5]:  # Check first 5 players
        obj = p.get('objective_stats', {})
        dead = obj.get('time_dead_minutes', 0) or 0
        played = obj.get('time_played_minutes', 0) or 0
        
        if dead > 1 and played > 5:  # Has some death time and played >5 min
            # Find same player in R1
            r1_player = None
            for r1p in r1_data['players']:
                if r1p['name'] == p['name']:
                    r1_player = r1p
                    break
            
            if r1_player:
                found = True
                r1_obj = r1_player.get('objective_stats', {})
                
                print(f"MAP: {r1_data['map_name']}")
                print(f"FILES: {r1} + {r2}")
                print(f"PLAYER: {p['name']}")
                print()
                
                r1_played = r1_obj.get('time_played_minutes', 0) or 0
                r1_dead = r1_obj.get('time_dead_minutes', 0) or 0
                r1_ratio = r1_obj.get('time_dead_ratio', 0) or 0
                
                r2_played = played
                r2_dead = dead
                r2_ratio = obj.get('time_dead_ratio', 0) or 0
                
                print("RAW VALUES FROM LUA:")
                print("-" * 50)
                print("Round 1:")
                print(f"  time_played: {r1_played:.1f} min")
                print(f"  time_dead:   {r1_dead:.1f} min")
                print(f"  ratio:       {r1_ratio:.1f}%")
                print()
                print("Round 2 (CUMULATIVE - both rounds):")
                print(f"  time_played: {r2_played:.1f} min")
                print(f"  time_dead:   {r2_dead:.1f} min")
                print(f"  ratio:       {r2_ratio:.1f}%")
                print()
                
                # Calculate what R2-only should be
                print("EXPECTED R2-ONLY (by subtraction):")
                print("-" * 50)
                expected_played = r2_played - r1_played
                expected_dead = r2_dead - r1_dead
                expected_ratio = (expected_dead / expected_played * 100) if expected_played > 0 else 0
                print(f"  time_played: {r2_played:.1f} - {r1_played:.1f} = {expected_played:.1f} min")
                print(f"  time_dead:   {r2_dead:.1f} - {r1_dead:.1f} = {expected_dead:.1f} min")
                print(f"  ratio:       {expected_dead:.1f}/{expected_played:.1f}*100 = {expected_ratio:.1f}%")
                print()
                
                # OLD buggy calculation
                print("OLD BUGGY CALCULATION (what database had):")
                print("-" * 50)
                old_dead = expected_played * (r2_ratio / 100)  # Used R2 cumulative ratio!
                print(f"  Used R2 cumulative ratio ({r2_ratio:.1f}%) on R2-only time ({expected_played:.1f} min)")
                print(f"  time_dead = {expected_played:.1f} * {r2_ratio:.1f}/100 = {old_dead:.1f} min")
                print("  This is WRONG because ratio is cumulative, not R2-only!")
                print()
                
                # Now show what the fix produces
                r2_only = parser.calculate_round_2_differential(r1_data, r2_data)
                for dp in r2_only['players']:
                    if dp['name'] == p['name']:
                        dobj = dp.get('objective_stats', {})
                        actual_played = dobj.get('time_played_minutes', 0)
                        actual_dead = dobj.get('time_dead_minutes', 0)
                        actual_ratio = dobj.get('time_dead_ratio', 0)
                        
                        print("FIXED CALCULATION (after our fix):")
                        print("-" * 50)
                        print(f"  time_played: {actual_played:.1f} min")
                        print(f"  time_dead:   {actual_dead:.1f} min")
                        print(f"  ratio:       {actual_ratio:.1f}%")
                        print()
                        
                        print("=" * 70)
                        print("SUMMARY")
                        print("=" * 70)
                        print(f"  OLD (buggy):  {old_dead:.1f} min dead ({old_dead/expected_played*100:.1f}% ratio)")
                        print(f"  NEW (fixed):  {actual_dead:.1f} min dead ({actual_ratio:.1f}% ratio)")
                        print(f"  Difference:   {abs(old_dead - actual_dead):.1f} min error corrected")
                        break
                
                break
    
    if found:
        break

if not found:
    print("Could not find a suitable stats file pair with death time data.")
