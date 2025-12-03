import asyncio
import asyncpg
from bot.config import load_config

async def deep_check():
    config = load_config()
    
    conn = await asyncpg.connect(
        host=config.postgres_host,
        port=config.postgres_port,
        database=config.postgres_database,
        user=config.postgres_user,
        password=config.postgres_password
    )
    
    problem_files = [
        '2025-11-04-225627-etl_frostbite-round-1.txt',
        '2025-11-04-224353-te_escape2-round-2.txt'
    ]
    
    print("\n=== DEEP INVESTIGATION ===\n")
    
    for filename in problem_files:
        print(f"📄 {filename}")
        
        # Check processed_files
        pf = await conn.fetchrow(
            "SELECT success, error_message FROM processed_files WHERE filename = $1",
            filename
        )
        
        if pf:
            print(f"  processed_files: Success={pf['success']}, Error={pf['error_message']}")
        else:
            print("  processed_files: NOT FOUND")
            continue
        
        # Extract match_id from filename (everything except .txt)
        match_id = filename.replace('.txt', '')
        
        # Check if round exists
        round_data = await conn.fetchrow(
            "SELECT id, map_name, round_number FROM rounds WHERE match_id = $1",
            match_id
        )
        
        if round_data:
            print(f"  rounds table: FOUND (id={round_data['id']}, map={round_data['map_name']}, round={round_data['round_number']})")
            
            # Check player stats count
            player_count = await conn.fetchval(
                "SELECT COUNT(*) FROM player_comprehensive_stats WHERE round_id = $1",
                round_data['id']
            )
            print(f"  player_comprehensive_stats: {player_count} records")
            
            # Check weapon stats count
            weapon_count = await conn.fetchval(
                "SELECT COUNT(*) FROM weapon_comprehensive_stats WHERE round_id = $1",
                round_data['id']
            )
            print(f"  weapon_comprehensive_stats: {weapon_count} records")
            
        else:
            print("  rounds table: ❌ NOT FOUND - File processed but NO round created!")
        
        print()
    
    await conn.close()

asyncio.run(deep_check())
