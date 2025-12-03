#!/usr/bin/env python3
"""
Comprehensive session-level time analysis for Session 19
Compare what we calculate vs what SuperBoyy sees (127.4 min)
"""
import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        host='localhost',
        database='etlegacy',
        user='etlegacy_user',
        password='etlegacy_secure_2025'
    )
    
    print("=" * 90)
    print("🕐 COMPREHENSIVE SESSION 19 TIME ANALYSIS")
    print("=" * 90)
    
    # Get all rounds for session 19
    print("\n📊 ALL ROUNDS IN SESSION 19:")
    print("-" * 90)
    
    rounds = await conn.fetch("""
        SELECT id, map_name, round_number, actual_time
        FROM rounds
        WHERE gaming_session_id = 19
        ORDER BY id
    """)
    
    r0_rounds = []
    r1_rounds = []
    r2_rounds = []
    
    for r in rounds:
        # Parse MM:SS to seconds
        atime_str = r['actual_time'] if r['actual_time'] else '0:00'
        if ':' in atime_str:
            parts = atime_str.split(':')
            atime = int(parts[0]) * 60 + int(parts[1])
        else:
            atime = int(atime_str) if atime_str else 0
        
        rnum = r['round_number']
        emoji = "🎯" if rnum == 0 else "1️⃣" if rnum == 1 else "2️⃣"
        
        print(f"{emoji} R{rnum} | {r['map_name']:20s} | {atime:4d}s ({atime/60:6.2f}min) [{atime_str}]")
        
        if rnum == 0:
            r0_rounds.append(atime)
        elif rnum == 1:
            r1_rounds.append(atime)
        elif rnum == 2:
            r2_rounds.append(atime)
    
    print("\n" + "=" * 90)
    print("📊 ROUNDS TABLE TOTALS (actual_time field)")
    print("=" * 90)
    
    r0_total = sum(r0_rounds)
    r1_total = sum(r1_rounds)
    r2_total = sum(r2_rounds)
    r12_total = r1_total + r2_total
    all_total = r0_total + r1_total + r2_total
    
    print(f"🎯 R0 count: {len(r0_rounds):2d} rounds | Total: {r0_total:6,}s ({r0_total/60:7.2f} min)")
    print(f"1️⃣  R1 count: {len(r1_rounds):2d} rounds | Total: {r1_total:6,}s ({r1_total/60:7.2f} min)")
    print(f"2️⃣  R2 count: {len(r2_rounds):2d} rounds | Total: {r2_total:6,}s ({r2_total/60:7.2f} min)")
    print(f"➕ R1+R2:                  Total: {r12_total:6,}s ({r12_total/60:7.2f} min) ← OUR APPROACH")
    print(f"🔢 ALL (R0+R1+R2):         Total: {all_total:6,}s ({all_total/60:7.2f} min) ← WRONG (triple count)")
    
    # Now get PLAYER time data
    print("\n" + "=" * 90)
    print("👤 PLAYER TIME DATA (time_played_seconds from player_comprehensive_stats)")
    print("=" * 90)
    
    player_data = await conn.fetch("""
        SELECT 
            p.player_name,
            SUM(CASE WHEN r.round_number = 0 THEN p.time_played_seconds ELSE 0 END) as r0_time,
            SUM(CASE WHEN r.round_number = 1 THEN p.time_played_seconds ELSE 0 END) as r1_time,
            SUM(CASE WHEN r.round_number = 2 THEN p.time_played_seconds ELSE 0 END) as r2_time,
            SUM(CASE WHEN r.round_number IN (1,2) THEN p.time_played_seconds ELSE 0 END) as r12_time,
            SUM(p.time_played_seconds) as all_time
        FROM player_comprehensive_stats p
        JOIN rounds r ON p.round_id = r.id
        WHERE r.gaming_session_id = 19
        GROUP BY p.player_name
        ORDER BY r12_time DESC
    """)
    
    print(f"{'Player':<15} | {'R0 Time':>12} | {'R1 Time':>12} | {'R2 Time':>12} | {'R1+R2':>12} | {'ALL Rounds':>12}")
    print("-" * 90)
    
    for p in player_data:
        name = p['player_name']
        r0 = p['r0_time']
        r1 = p['r1_time']
        r2 = p['r2_time']
        r12 = p['r12_time']
        all_t = p['all_time']
        
        print(f"{name:<15} | {r0:6,}s ({r0/60:5.1f}m) | {r1:6,}s ({r1/60:5.1f}m) | "
              f"{r2:6,}s ({r2/60:5.1f}m) | {r12:6,}s ({r12/60:5.1f}m) | {all_t:6,}s ({all_t/60:5.1f}m)")
    
    # Check SuperBoyy specifically
    print("\n" + "=" * 90)
    print("🔍 SUPERBOYY SPECIFIC CHECK")
    print("=" * 90)
    
    superboyy = next((p for p in player_data if p['player_name'].lower() == 'superboyy'), None)
    if superboyy:
        r12_minutes = superboyy['r12_time'] / 60
        print(f"SuperBoyy's R1+R2 time: {superboyy['r12_time']:,}s = {r12_minutes:.2f} minutes")
        print("SuperBoyy reported:     127.4 minutes (from attachment)")
        print(f"Difference:             {r12_minutes - 127.4:+.2f} minutes")
        
        if abs(r12_minutes - 127.4) < 2.0:
            print("✅ CLOSE MATCH! Within 2 minutes")
        else:
            print(f"⚠️  DISCREPANCY of {abs(r12_minutes - 127.4):.2f} minutes")
    
    # Check if everyone has same playtime (they should for full session)
    print("\n" + "=" * 90)
    print("⚖️  PLAYTIME EQUALITY CHECK")
    print("=" * 90)
    
    r12_times = [p['r12_time'] for p in player_data]
    max_time = max(r12_times)
    min_time = min(r12_times)
    avg_time = sum(r12_times) / len(r12_times)
    
    print(f"Max R1+R2 time: {max_time:,}s ({max_time/60:.2f} min)")
    print(f"Min R1+R2 time: {min_time:,}s ({min_time/60:.2f} min)")
    print(f"Avg R1+R2 time: {avg_time:,.0f}s ({avg_time/60:.2f} min)")
    print(f"Range:          {max_time - min_time:,}s ({(max_time - min_time)/60:.2f} min)")
    
    if max_time - min_time < 60:
        print("✅ All players have similar playtime (within 1 minute)")
    else:
        print("⚠️  Significant playtime variation - some players joined late or left early")
    
    # Compare rounds table vs player table
    print("\n" + "=" * 90)
    print("🔄 ROUNDS TABLE vs PLAYER TABLE COMPARISON")
    print("=" * 90)
    
    print(f"Rounds table R1+R2:  {r12_total:6,}s ({r12_total/60:7.2f} min)")
    print(f"Player avg R1+R2:    {avg_time:6,.0f}s ({avg_time/60:7.2f} min)")
    print(f"Difference:          {r12_total - avg_time:6,.0f}s ({(r12_total - avg_time)/60:7.2f} min)")
    print()
    print("📌 NOTE: Rounds table = wall clock time (total match duration)")
    print("📌 NOTE: Player table = active playtime (excluding deaths/spectating)")
    print("📌 Difference = total time players spent dead across all rounds")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
