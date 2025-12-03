#!/usr/bin/env python3
"""
Check playtime round-by-round to find discrepancy
SuperBoyy recorded: 127.4 minutes
We recorded: 128.4 minutes (7,720s / 60 = 128.67 min)
Difference: ~1 minute

Let's check each round's time to see where the difference comes from.
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
    
    print("=" * 80)
    print("🕐 Round-by-Round Playtime Analysis - Gaming Session 19")
    print("=" * 80)
    
    # Get all rounds for session 19
    rounds = await conn.fetch("""
        SELECT id, map_name, round_number, actual_time, time_limit
        FROM rounds
        WHERE gaming_session_id = 19
        ORDER BY round_date, round_time
    """)
    
    print(f"\n📊 Found {len(rounds)} rounds in session 19")
    print("-" * 80)
    
    # Track totals
    r0_total = 0
    r1_total = 0
    r2_total = 0
    
    # Show each round
    for r in rounds:
        round_id, map_name, round_num, actual_time, time_limit = r
        
        # Convert actual_time to int (it's stored as string in DB)
        actual_time = int(actual_time) if actual_time else 0
        time_limit = int(time_limit) if time_limit else 0
        
        emoji = "🎯" if round_num == 0 else "1️⃣" if round_num == 1 else "2️⃣"
        print(f"{emoji} Round {round_id}: {map_name:20s} R{round_num} | "
              f"actual_time={actual_time:4d}s ({actual_time/60:.1f}min) | "
              f"time_limit={time_limit}s")
        
        if round_num == 0:
            r0_total += actual_time
        elif round_num == 1:
            r1_total += actual_time
        elif round_num == 2:
            r2_total += actual_time
    
    print("\n" + "=" * 80)
    print("📊 TOTALS BY ROUND TYPE")
    print("=" * 80)
    print(f"🎯 R0 total:  {r0_total:6,}s ({r0_total/60:7.2f} min)")
    print(f"1️⃣  R1 total:  {r1_total:6,}s ({r1_total/60:7.2f} min)")
    print(f"2️⃣  R2 total:  {r2_total:6,}s ({r2_total/60:7.2f} min)")
    print(f"➕ R1+R2:     {r1_total+r2_total:6,}s ({(r1_total+r2_total)/60:7.2f} min)")
    print(f"🔢 ALL (R0+R1+R2): {r0_total+r1_total+r2_total:6,}s ({(r0_total+r1_total+r2_total)/60:7.2f} min)")
    
    # Now check player-specific time
    print("\n" + "=" * 80)
    print("👤 PLAYER TIME TRACKING (all players should have same total)")
    print("=" * 80)
    
    # Get player times by round type
    player_times = await conn.fetch("""
        SELECT 
            p.player_name,
            SUM(CASE WHEN r.round_number = 0 THEN p.time_played_seconds ELSE 0 END) as r0_time,
            SUM(CASE WHEN r.round_number = 1 THEN p.time_played_seconds ELSE 0 END) as r1_time,
            SUM(CASE WHEN r.round_number = 2 THEN p.time_played_seconds ELSE 0 END) as r2_time,
            SUM(CASE WHEN r.round_number IN (1,2) THEN p.time_played_seconds ELSE 0 END) as r12_time
        FROM player_comprehensive_stats p
        JOIN rounds r ON p.round_id = r.id
        WHERE r.gaming_session_id = 19
        GROUP BY p.player_name
        ORDER BY r12_time DESC
    """)
    
    for p in player_times:
        name = p['player_name']
        r0 = p['r0_time']
        r1 = p['r1_time']
        r2 = p['r2_time']
        r12 = p['r12_time']
        
        print(f"\n👤 {name}")
        print(f"   R0:     {r0:6,}s ({r0/60:6.1f} min)")
        print(f"   R1:     {r1:6,}s ({r1/60:6.1f} min)")
        print(f"   R2:     {r2:6,}s ({r2/60:6.1f} min)")
        print(f"   R1+R2:  {r12:6,}s ({r12/60:6.1f} min) ← OUR TOTAL")
        
        # Check if this matches the 127.4 or 128.4
        if abs(r12/60 - 127.4) < 1.0:
            print("   ⚠️  Close to SuperBoyy's 127.4 min!")
        if abs(r12/60 - 128.4) < 1.0:
            print("   ⚠️  Close to our 128.4 min!")
    
    # Check the attachment data
    print("\n" + "=" * 80)
    print("📋 COMPARING WITH ATTACHMENT DATA")
    print("=" * 80)
    
    # Map times from attachment
    attachment_times = {
        'etl_adlernest': 928,
        'supply': 1153,
        'etl_sp_delivery': 510,
        'te_escape2': 567 + 358,  # Two plays
        'braundorf_b4': 1062,
        'sw_goldrush_te': 1234,
        'et_brewdog': 198 + 774,  # Two plays
        'etl_frostbite': 859
    }
    
    attachment_total = sum(attachment_times.values())
    print(f"📎 Attachment total: {attachment_total}s ({attachment_total/60:.1f} min)")
    print(f"🗄️  Our R1+R2 total:  {r1_total+r2_total}s ({(r1_total+r2_total)/60:.1f} min)")
    print(f"📊 Difference:       {(r1_total+r2_total)-attachment_total}s ({((r1_total+r2_total)-attachment_total)/60:.1f} min)")
    
    # Show round times by map
    print("\n" + "=" * 80)
    print("🗺️  TIME BY MAP (R1+R2)")
    print("=" * 80)
    
    map_times = await conn.fetch("""
        SELECT 
            r.map_name,
            SUM(CASE WHEN r.round_number = 1 THEN r.actual_time ELSE 0 END) as r1_time,
            SUM(CASE WHEN r.round_number = 2 THEN r.actual_time ELSE 0 END) as r2_time,
            SUM(CASE WHEN r.round_number IN (1,2) THEN r.actual_time ELSE 0 END) as total_time
        FROM rounds r
        WHERE r.gaming_session_id = 19
        GROUP BY r.map_name
        ORDER BY total_time DESC
    """)
    
    db_total = 0
    for m in map_times:
        map_name = m['map_name']
        r1 = m['r1_time']
        r2 = m['r2_time']
        total = m['total_time']
        db_total += total
        
        # Check against attachment
        att_time = attachment_times.get(map_name, 0)
        diff = total - att_time
        match = "✅" if abs(diff) < 10 else "❌"
        
        print(f"{map_name:20s} | R1:{r1:4d}s R2:{r2:4d}s | Total:{total:5d}s | "
              f"Attachment:{att_time:5d}s | Diff:{diff:+4d}s {match}")
    
    print(f"\n{'TOTALS':20s} | {'':13s} | Total:{db_total:5d}s | Attachment:{attachment_total:5d}s | Diff:{db_total-attachment_total:+4d}s")
    print(f"                                       ({db_total/60:.1f} min)     ({attachment_total/60:.1f} min)")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
