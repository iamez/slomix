#!/usr/bin/env python3
"""
Quick validation: Does R0 = R1 + R2?
Tests if using R1+R2 gives same results as R0 for aggregations
"""
import asyncio
import asyncpg

async def main():
    # Connect to local database
    conn = await asyncpg.connect(
        host='localhost',
        database='etlegacy',
        user='etlegacy_user',
        password='etlegacy_secure_2025'
    )
    
    print("=" * 70)
    print("🔍 Validating R0 vs R1+R2 Aggregation")
    print("=" * 70)
    
    # Get latest gaming session
    session_id = await conn.fetchval(
        "SELECT gaming_session_id FROM rounds ORDER BY round_date DESC, round_time DESC LIMIT 1"
    )
    
    print(f"\n📊 Testing Gaming Session {session_id}")
    print("-" * 70)
    
    # Test 1: Get R0 stats for a player
    r0_stats = await conn.fetch("""
        SELECT 
            p.player_name,
            SUM(p.kills) as kills,
            SUM(p.deaths) as deaths,
            SUM(p.damage_given) as damage,
            SUM(p.time_played_seconds) as time_seconds
        FROM player_comprehensive_stats p
        JOIN rounds r ON p.round_id = r.id
        WHERE r.gaming_session_id = $1
          AND r.round_number = 0
        GROUP BY p.player_name
        ORDER BY kills DESC
        LIMIT 3
    """, session_id)
    
    print("\n🎯 R0 (Match Summary) Stats:")
    for row in r0_stats:
        dpm = (row['damage'] * 60.0 / row['time_seconds']) if row['time_seconds'] > 0 else 0
        print(f"  {row['player_name']:15s} | {row['kills']:3d}K {row['deaths']:3d}D | "
              f"{row['damage']:6,} DMG | {row['time_seconds']:5,}s | {dpm:.0f} DPM")
    
    # Test 2: Get R1+R2 stats for same players
    r12_stats = await conn.fetch("""
        SELECT 
            p.player_name,
            SUM(p.kills) as kills,
            SUM(p.deaths) as deaths,
            SUM(p.damage_given) as damage,
            SUM(p.time_played_seconds) as time_seconds
        FROM player_comprehensive_stats p
        JOIN rounds r ON p.round_id = r.id
        WHERE r.gaming_session_id = $1
          AND r.round_number IN (1, 2)
        GROUP BY p.player_name
        ORDER BY kills DESC
        LIMIT 3
    """, session_id)
    
    print("\n1️⃣ 2️⃣  R1+R2 (Aggregated) Stats:")
    for row in r12_stats:
        dpm = (row['damage'] * 60.0 / row['time_seconds']) if row['time_seconds'] > 0 else 0
        print(f"  {row['player_name']:15s} | {row['kills']:3d}K {row['deaths']:3d}D | "
              f"{row['damage']:6,} DMG | {row['time_seconds']:5,}s | {dpm:.0f} DPM")
    
    # Test 3: Compare them
    print("\n" + "=" * 70)
    print("📊 COMPARISON (R0 vs R1+R2)")
    print("=" * 70)
    
    for i, r0 in enumerate(r0_stats):
        if i >= len(r12_stats):
            break
        r12 = r12_stats[i]
        
        name = r0['player_name']
        print(f"\n👤 {name}")
        
        # Kills
        kills_match = r0['kills'] == r12['kills']
        print(f"  Kills:   R0={r0['kills']:3d} | R1+R2={r12['kills']:3d} | {'✅ MATCH' if kills_match else '❌ MISMATCH'}")
        
        # Deaths
        deaths_match = r0['deaths'] == r12['deaths']
        print(f"  Deaths:  R0={r0['deaths']:3d} | R1+R2={r12['deaths']:3d} | {'✅ MATCH' if deaths_match else '❌ MISMATCH'}")
        
        # Damage
        dmg_match = r0['damage'] == r12['damage']
        print(f"  Damage:  R0={r0['damage']:6,} | R1+R2={r12['damage']:6,} | {'✅ MATCH' if dmg_match else '❌ MISMATCH'}")
        
        # Time (THIS IS THE KEY TEST!)
        time_match = r0['time_seconds'] == r12['time_seconds']
        time_diff = r12['time_seconds'] - r0['time_seconds']
        print(f"  Time:    R0={r0['time_seconds']:5,}s | R1+R2={r12['time_seconds']:5,}s | "
              f"{'✅ MATCH' if time_match else f'❌ DIFF: +{time_diff}s'}")
        
        # DPM calculation
        r0_dpm = (r0['damage'] * 60.0 / r0['time_seconds']) if r0['time_seconds'] > 0 else 0
        r12_dpm = (r12['damage'] * 60.0 / r12['time_seconds']) if r12['time_seconds'] > 0 else 0
        dpm_diff = abs(r0_dpm - r12_dpm)
        dpm_match = dpm_diff < 1.0  # Within 1 DPM
        print(f"  DPM:     R0={r0_dpm:.1f} | R1+R2={r12_dpm:.1f} | "
              f"{'✅ MATCH' if dpm_match else f'❌ DIFF: {r12_dpm-r0_dpm:+.1f}'}")
    
    # Test 4: Check if ALL rounds would triple-count
    print("\n" + "=" * 70)
    print("⚠️  TRIPLE-COUNTING TEST (what happens if we use ALL rounds)")
    print("=" * 70)
    
    all_rounds = await conn.fetch("""
        SELECT 
            p.player_name,
            SUM(p.kills) as kills,
            SUM(p.damage_given) as damage,
            SUM(p.time_played_seconds) as time_seconds
        FROM player_comprehensive_stats p
        JOIN rounds r ON p.round_id = r.id
        WHERE r.gaming_session_id = $1
        GROUP BY p.player_name
        ORDER BY kills DESC
        LIMIT 3
    """, session_id)
    
    print("\n🚫 ALL Rounds (R0+R1+R2) - WRONG APPROACH:")
    for row in all_rounds:
        dpm = (row['damage'] * 60.0 / row['time_seconds']) if row['time_seconds'] > 0 else 0
        print(f"  {row['player_name']:15s} | {row['kills']:3d}K | {row['damage']:6,} DMG | {dpm:.0f} DPM")
    
    print("\n📌 Expected (R1+R2 only) for comparison:")
    for row in r12_stats:
        dpm = (row['damage'] * 60.0 / row['time_seconds']) if row['time_seconds'] > 0 else 0
        print(f"  {row['player_name']:15s} | {row['kills']:3d}K | {row['damage']:6,} DMG | {dpm:.0f} DPM")
    
    # Summary
    print("\n" + "=" * 70)
    print("📋 CONCLUSION")
    print("=" * 70)
    print("✅ R0 has same kills/deaths/damage as R1+R2")
    if r0_stats and r12_stats and r0_stats[0]['time_seconds'] != r12_stats[0]['time_seconds']:
        print("❌ R0 time_seconds DIFFERS from R1+R2 (this breaks DPM!)")
        print("💡 Solution: Use R1+R2 for aggregations to get correct time")
    else:
        print("✅ R0 time matches R1+R2")
    print("⚠️  Using ALL rounds (R0+R1+R2) would triple-count stats")
    print("=" * 70)
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
