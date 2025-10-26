#!/usr/bin/env python3
"""
Explain October 2nd Stopwatch Scoring Step-by-Step

Shows the math behind each map's score calculation
"""

print("\n" + "="*70)
print("🧮 STOPWATCH SCORING MATH - October 2nd, 2025")
print("="*70)

print("\n📜 SCORING RULES:")
print("   Round 1:")
print("      • Attackers complete objective → 1 point")
print("      • Defenders fullhold → 2 points")
print("   Round 2:")
print("      • Attackers beat R1 time → 2 points total")
print("      • Defenders hold (tie/slower) → +1 point to defenders")
print("\n   NOTE: Teams swap sides, so Team A attacks R1, Team B attacks R2")
print("="*70)

maps = [
    {
        'name': 'etl_adlernest',
        'r1_time': '3:51',
        'r1_attacker': 'slomix',
        'r2_time': '3:51',
        'r2_attacker': 'slo'
    },
    {
        'name': 'supply',
        'r1_time': '9:41',
        'r1_attacker': 'slomix',
        'r2_time': '8:22',
        'r2_attacker': 'slo'
    },
    {
        'name': 'etl_sp_delivery',
        'r1_time': '6:16',
        'r1_attacker': 'slomix',
        'r2_time': '6:16',
        'r2_attacker': 'slo'
    },
    {
        'name': 'te_escape2 (1st)',
        'r1_time': '4:23',
        'r1_attacker': 'slomix',
        'r2_time': '4:23',
        'r2_attacker': 'slo'
    },
    {
        'name': 'te_escape2 (2nd)',
        'r1_time': '4:35',
        'r1_attacker': 'slomix',
        'r2_time': '3:57',
        'r2_attacker': 'slo'
    },
    {
        'name': 'sw_goldrush_te',
        'r1_time': '9:28',
        'r1_attacker': 'slomix',
        'r2_time': '8:40',
        'r2_attacker': 'slo'
    },
    {
        'name': 'et_brewdog',
        'r1_time': '3:25',
        'r1_attacker': 'slomix',
        'r2_time': '3:25',
        'r2_attacker': 'slo'
    },
    {
        'name': 'etl_frostbite',
        'r1_time': '4:27',
        'r1_attacker': 'slomix',
        'r2_time': '3:27',
        'r2_attacker': 'slo'
    },
    {
        'name': 'braundorf_b4',
        'r1_time': '7:52',
        'r1_attacker': 'slomix',
        'r2_time': '7:52',
        'r2_attacker': 'slo'
    },
    {
        'name': 'erdenberg_t2',
        'r1_time': '7:27',
        'r1_attacker': 'slomix',
        'r2_time': '4:00',
        'r2_attacker': 'slo'
    }
]

def time_to_seconds(time_str):
    parts = time_str.split(':')
    return int(parts[0]) * 60 + int(parts[1])

slo_total = 0
slomix_total = 0
map_num = 1

for map_data in maps:
    print(f"\n{'─'*70}")
    print(f"MAP #{map_num}: {map_data['name']}")
    print(f"{'─'*70}")
    
    r1_sec = time_to_seconds(map_data['r1_time'])
    r2_sec = time_to_seconds(map_data['r2_time'])
    
    print(f"\n   Round 1: {map_data['r1_attacker']} attacks")
    print(f"      Time: {map_data['r1_time']} ({r1_sec} seconds)")
    print(f"      ✅ Objective completed!")
    print(f"      📊 Score: {map_data['r1_attacker']} gets 1 point")
    
    if map_data['r1_attacker'] == 'slomix':
        slomix_score_r1 = 1
        slo_score_r1 = 0
        slomix_total += 1
    else:
        slo_score_r1 = 1
        slomix_score_r1 = 0
        slo_total += 1
    
    print(f"\n   Round 2: {map_data['r2_attacker']} attacks")
    print(f"      Time Limit: {map_data['r1_time']} (must beat R1 time)")
    print(f"      Actual Time: {map_data['r2_time']} ({r2_sec} seconds)")
    
    if r2_sec < r1_sec:
        print(f"      ✅ Beat the time! ({r2_sec}s < {r1_sec}s)")
        print(f"      📊 Score: {map_data['r2_attacker']} gets 2 points total")
        if map_data['r2_attacker'] == 'slomix':
            slomix_score_r2 = 2
            slo_score_r2 = 0
            slomix_total += 2
        else:
            slo_score_r2 = 2
            slomix_score_r2 = 0
            slo_total += 2
    else:
        print(f"      ❌ Did NOT beat time ({r2_sec}s >= {r1_sec}s)")
        print(f"      🛡️  Defenders held!")
        print(f"      📊 Score: {map_data['r1_attacker']} (defenders) gets +1 point")
        if map_data['r1_attacker'] == 'slomix':
            slomix_score_r2 = 1
            slo_score_r2 = 0
            slomix_total += 1
        else:
            slo_score_r2 = 1
            slomix_score_r2 = 0
            slo_total += 1
    
    print(f"\n   🏆 MAP RESULT:")
    print(f"      slo:    {slo_score_r1 + slo_score_r2} points")
    print(f"      slomix: {slomix_score_r1 + slomix_score_r2} points")
    
    print(f"\n   📈 RUNNING TOTAL:")
    print(f"      slo:    {slo_total} points")
    print(f"      slomix: {slomix_total} points")
    
    map_num += 1

print(f"\n{'='*70}")
print(f"🏁 FINAL SCORE:")
print(f"{'='*70}")
print(f"   slo:    {slo_total} points")
print(f"   slomix: {slomix_total} points")
print(f"{'='*70}\n")

# Verify against calculator output
print("✅ VERIFICATION:")
print(f"   Expected: slo: 10, slomix: 15")
print(f"   Calculated: slo: {slo_total}, slomix: {slomix_total}")
if slo_total == 10 and slomix_total == 15:
    print("   ✅ MATH CHECKS OUT! 🎉")
else:
    print(f"   ❌ ERROR: Mismatch detected!")
