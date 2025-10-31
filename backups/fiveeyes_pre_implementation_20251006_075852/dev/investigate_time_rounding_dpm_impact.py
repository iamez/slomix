#!/usr/bin/env python3
"""
Investigate if time conversion/rounding causes 1.5% DPM difference
compared to SuperBoyy's manual analysis
"""
import sys
sys.path.insert(0, 'bot')
from community_stats_parser import C0RNP0RN3StatsParser

def analyze_time_rounding_impact():
    """
    Check if our time conversion creates systematic DPM inflation
    """
    
    print("=" * 80)
    print("🔬 TIME ROUNDING DPM IMPACT ANALYSIS")
    print("=" * 80)
    print()
    print("Question: Does our time conversion cause 1.5% higher DPM?")
    print()
    
    # Test with actual October 2nd files
    test_cases = [
        ('etl_adlernest R1', 'local_stats/2025-10-02-211808-etl_adlernest-round-1.txt'),
        ('supply R1', 'local_stats/2025-10-02-213333-supply-round-1.txt'),
        ('etl_sp_delivery R1', 'local_stats/2025-10-02-214959-etl_sp_delivery-round-1.txt'),
        ('te_escape2 R1', 'local_stats/2025-10-02-220201-te_escape2-round-1.txt'),
    ]
    
    parser = C0RNP0RN3StatsParser()
    
    print("=" * 80)
    print("THEORY 1: Lua Rounding Creates LOWER Time (HIGHER DPM)")
    print("=" * 80)
    print()
    
    total_raw_time = 0
    total_rounded_time = 0
    
    for label, filepath in test_cases:
        try:
            # Read raw header
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                header = f.readline().strip()
                header_parts = header.split('\\')
                actual_time_mmss = header_parts[7]
            
            # Parse MM:SS to exact decimal minutes
            if ':' in actual_time_mmss:
                parts = actual_time_mmss.split(':')
                minutes = int(parts[0])
                seconds = int(parts[1])
                total_seconds = minutes * 60 + seconds
                exact_decimal = total_seconds / 60.0
            else:
                exact_decimal = float(actual_time_mmss)
                total_seconds = int(exact_decimal * 60)
            
            # Lua rounding simulation: roundNum(x, 1) = floor(x * 10 + 0.5) / 10
            lua_rounded = round(exact_decimal, 1)
            
            # Calculate DPM impact (example: 5000 damage)
            example_damage = 5000
            dpm_exact = example_damage / exact_decimal
            dpm_rounded = example_damage / lua_rounded
            
            dpm_difference = dpm_rounded - dpm_exact
            percent_diff = (dpm_difference / dpm_exact) * 100
            
            print(f"{label}:")
            print(f"  Raw: {actual_time_mmss} ({total_seconds} seconds)")
            print(f"  Exact decimal: {exact_decimal:.6f} minutes")
            print(f"  Lua rounded:   {lua_rounded:.1f} minutes")
            print(f"  Time diff: {lua_rounded - exact_decimal:+.6f} minutes")
            print()
            print(f"  Example DPM (5000 damage):")
            print(f"    With exact time:   {dpm_exact:.2f}")
            print(f"    With lua rounded:  {dpm_rounded:.2f}")
            print(f"    DPM difference:    {dpm_difference:+.2f} ({percent_diff:+.3f}%)")
            print()
            
            total_raw_time += exact_decimal
            total_rounded_time += lua_rounded
            
        except Exception as e:
            print(f"❌ Error processing {label}: {e}")
            print()
    
    print("=" * 80)
    print("AGGREGATE ANALYSIS")
    print("=" * 80)
    print()
    print(f"Total exact time:   {total_raw_time:.6f} minutes")
    print(f"Total rounded time: {total_rounded_time:.1f} minutes")
    print(f"Time difference:    {total_rounded_time - total_raw_time:+.6f} minutes")
    print()
    
    # Aggregate DPM impact
    total_damage = 20000  # Example
    agg_dpm_exact = total_damage / total_raw_time
    agg_dpm_rounded = total_damage / total_rounded_time
    agg_diff = agg_dpm_rounded - agg_dpm_exact
    agg_percent = (agg_diff / agg_dpm_exact) * 100
    
    print(f"Example aggregate DPM (20000 damage):")
    print(f"  With exact time:   {agg_dpm_exact:.2f}")
    print(f"  With lua rounded:  {agg_dpm_rounded:.2f}")
    print(f"  DPM difference:    {agg_diff:+.2f} ({agg_percent:+.3f}%)")
    print()
    
    print("=" * 80)
    print("THEORY 2: Parser Time vs SuperBoyy's Manual Calculation")
    print("=" * 80)
    print()
    print("SuperBoyy might be using:")
    print("  1. EXACT time from MM:SS (e.g., 3:51 = 3.85 min exactly)")
    print("  2. RAW damage numbers from file")
    print()
    print("We might be using:")
    print("  1. ROUNDED time (e.g., 3.9 min from lua rounding)")
    print("  2. SAME damage numbers")
    print()
    print("Result: Our DPM would be LOWER (more time = less DPM)")
    print("But you said YOUR DPM is 1.5% HIGHER!")
    print()
    
    print("=" * 80)
    print("THEORY 3: We're Using EXACT Time, SuperBoyy Uses ROUNDED")
    print("=" * 80)
    print()
    print("If SuperBoyy is reading the Tab[22] field (which is lua-rounded):")
    print("  His time: 3.9 minutes (rounded UP)")
    print("  Our time: 3.85 minutes (exact from MM:SS)")
    print("  Result: Our time SHORTER → Our DPM HIGHER ✅")
    print()
    print("This would explain 1.5% difference!")
    print()
    
    # Calculate typical rounding impact
    print("=" * 80)
    print("ROUNDING IMPACT CALCULATION")
    print("=" * 80)
    print()
    
    examples = [
        ("3:51", 3.85, 3.9),
        ("4:23", 4.383, 4.4),
        ("8:23", 8.383, 8.4),
        ("9:41", 9.683, 9.7),
    ]
    
    print(f"{'MM:SS':<10} {'Exact':<10} {'Rounded':<10} {'Diff%':<10} {'DPM Impact':<15}")
    print("-" * 80)
    
    total_impact = 0
    count = 0
    
    for mmss, exact, rounded in examples:
        diff_percent = ((rounded - exact) / exact) * 100
        
        # DPM impact (inverse relationship)
        # If time increases by X%, DPM decreases by ~X%
        dpm_impact = -diff_percent  # Negative because more time = less DPM
        
        # But if WE use exact and THEY use rounded, OUR DPM is higher
        our_advantage = -dpm_impact  # Flip the sign
        
        print(f"{mmss:<10} {exact:<10.3f} {rounded:<10.1f} {diff_percent:<10.3f} {our_advantage:<15.3f}%")
        
        total_impact += our_advantage
        count += 1
    
    avg_impact = total_impact / count
    print()
    print(f"Average DPM advantage if we use exact vs rounded: {avg_impact:.3f}%")
    print()
    
    if abs(avg_impact - 1.5) < 0.5:
        print("🎯 MATCH! This explains the 1.5% difference!")
        print()
        print("CONCLUSION:")
        print("  - We use EXACT time from MM:SS header (3:51 = 3.85 min)")
        print("  - SuperBoyy uses ROUNDED time from Tab[22] or lua display (3.9 min)")
        print("  - Result: Our time is ~1.5% shorter → Our DPM is ~1.5% higher")
        print()
        print("This is NOT a bug - it's a difference in precision!")
    else:
        print(f"⚠️ Average impact ({avg_impact:.3f}%) doesn't match reported 1.5%")
        print("Need to investigate other sources of difference...")
    
    print()
    print("=" * 80)
    print("VERIFICATION NEEDED")
    print("=" * 80)
    print()
    print("Questions for user:")
    print("  1. Does SuperBoyy use Tab[22] field (time_played_minutes)?")
    print("  2. Or does he parse MM:SS from header like us?")
    print("  3. Is the 1.5% difference consistent across all players?")
    print("  4. Can you share SuperBoyy's calculation method?")
    print()

if __name__ == '__main__':
    analyze_time_rounding_impact()
