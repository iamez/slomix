#!/usr/bin/env python3
"""
Check what round_number entries exist in VPS database
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def check_rounds():
    """Check round distribution in database"""
    
    conn = await asyncpg.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost').split(':')[0],
        port=int(os.getenv('POSTGRES_HOST', 'localhost:5432').split(':')[1]) if ':' in os.getenv('POSTGRES_HOST', 'localhost:5432') else 5432,
        database=os.getenv('POSTGRES_DATABASE', 'etlegacy'),
        user=os.getenv('POSTGRES_USER', 'etlegacy_user'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )
    
    print("=" * 70)
    print("🔍 Checking round_number distribution in database")
    print("=" * 70)
    
    # Get count by round_number
    query = """
        SELECT round_number, COUNT(*) as count
        FROM rounds
        GROUP BY round_number
        ORDER BY round_number
    """
    results = await conn.fetch(query)
    
    print("\n📊 Round distribution:")
    for row in results:
        round_num = row['round_number']
        count = row['count']
        if round_num == 0:
            print(f"  🎯 round_number = 0 (Match Summaries): {count}")
        elif round_num == 1:
            print(f"  1️⃣  round_number = 1 (Round 1): {count}")
        elif round_num == 2:
            print(f"  2️⃣  round_number = 2 (Round 2): {count}")
        else:
            print(f"  ❓ round_number = {round_num}: {count}")
    
    # Get latest rounds
    print("\n📋 Latest 10 rounds:")
    latest_query = """
        SELECT id, round_date, map_name, round_number, match_id
        FROM rounds
        ORDER BY round_date DESC, id DESC
        LIMIT 10
    """
    latest = await conn.fetch(latest_query)
    
    for row in latest:
        round_marker = "🎯" if row['round_number'] == 0 else ("1️⃣" if row['round_number'] == 1 else "2️⃣")
        print(f"  {round_marker} ID {row['id']}: {row['round_date']} - {row['map_name']} (R{row['round_number']}) [{row['match_id']}]")
    
    # Check if any match summaries exist
    summary_count = await conn.fetchval("SELECT COUNT(*) FROM rounds WHERE round_number = 0")
    
    print("\n" + "=" * 70)
    if summary_count > 0:
        print(f"✅ Found {summary_count} match summaries (round_number=0)")
        
        # Check gaming_session_id
        session_query = """
            SELECT gaming_session_id, COUNT(*) as count
            FROM rounds
            WHERE round_number = 0
            GROUP BY gaming_session_id
            ORDER BY gaming_session_id DESC
            LIMIT 5
        """
        sessions = await conn.fetch(session_query)
        print("\n🎮 Latest gaming sessions with match summaries:")
        for row in sessions:
            print(f"  Session {row['gaming_session_id']}: {row['count']} match summaries")
    else:
        print("❌ NO match summaries found (round_number=0)")
        print("⚠️  This means Round 2 files haven't been processed yet!")
        print("💡 Bot needs to process a Round 2 file to create match summaries")
    
    print("=" * 70)
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_rounds())
