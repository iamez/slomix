"""
🔍 POSTGRESQL IMPORT MONITOR - Real-time tracking
Run this in a separate terminal WHILE running the nuclear reset

Monitors:
- Total files processed
- Files failed
- Problem files from Nov 4
- Round/player/weapon counts
- Real-time progress

Usage:
  Terminal 1: python monitor_import_pg.py
  Terminal 2: python postgresql_database_manager.py (choose option 3)
"""
import asyncio
import asyncpg
import time
from datetime import datetime
from bot.config import load_config

# Known problem files
PROBLEM_FILES = [
    '2025-11-04-225627-etl_frostbite-round-1.txt',
    '2025-11-04-224353-te_escape2-round-2.txt'
]

class ImportMonitor:
    def __init__(self):
        self.config = load_config()
        self.conn = None
        self.last_counts = {}
        
    async def connect(self):
        """Connect to PostgreSQL"""
        self.conn = await asyncpg.connect(
            host=self.config.postgres_host,
            port=self.config.postgres_port,
            database=self.config.postgres_database,
            user=self.config.postgres_user,
            password=self.config.postgres_password
        )
        print(f"✅ Connected to PostgreSQL: {self.config.postgres_database}")
    
    async def get_stats(self):
        """Get current database stats"""
        try:
            # Get counts
            rounds = await self.conn.fetchval("SELECT COUNT(*) FROM rounds")
            players = await self.conn.fetchval("SELECT COUNT(*) FROM player_comprehensive_stats")
            weapons = await self.conn.fetchval("SELECT COUNT(*) FROM weapon_comprehensive_stats")
            processed = await self.conn.fetchval("SELECT COUNT(*) FROM processed_files")
            failed = await self.conn.fetchval("SELECT COUNT(*) FROM processed_files WHERE success = false")
            
            # Check problem files
            problem_status = {}
            for pf in PROBLEM_FILES:
                result = await self.conn.fetchrow(
                    "SELECT success, error_message FROM processed_files WHERE filename = $1",
                    pf
                )
                if result:
                    problem_status[pf] = {
                        'processed': True,
                        'success': result['success'],
                        'error': result['error_message']
                    }
                else:
                    problem_status[pf] = {'processed': False}
            
            # Get recent imports (last 5)
            recent = await self.conn.fetch(
                """
                SELECT filename, success, processed_at 
                FROM processed_files 
                ORDER BY processed_at DESC 
                LIMIT 5
                """
            )
            
            return {
                'rounds': rounds,
                'players': players,
                'weapons': weapons,
                'processed': processed,
                'failed': failed,
                'problem_files': problem_status,
                'recent': recent
            }
        except Exception as e:
            return {'error': str(e)}
    
    async def monitor(self):
        """Main monitoring loop"""
        print("\n" + "=" * 80)
        print("🔍 POSTGRESQL IMPORT MONITOR - Real-time tracking")
        print("=" * 80)
        print(f"\nDatabase: {self.config.postgres_database}")
        print(f"Known problem files: {len(PROBLEM_FILES)}")
        for pf in PROBLEM_FILES:
            print(f"  - {pf}")
        print("\nPress Ctrl+C to stop monitoring\n")
        print("=" * 80)
        
        iteration = 0
        try:
            while True:
                iteration += 1
                stats = await self.get_stats()
                
                if 'error' in stats:
                    print(f"\r⚠️  Waiting for database... ({stats['error']})", end='', flush=True)
                    await asyncio.sleep(2)
                    continue
                
                # Clear previous line and print new stats
                timestamp = datetime.now().strftime("%H:%M:%S")
                
                # Main stats
                print(f"\r[{timestamp}] ", end='')
                print(f"📊 Rounds: {stats['rounds']:>3} | ", end='')
                print(f"Players: {stats['players']:>4} | ", end='')
                print(f"Weapons: {stats['weapons']:>4} | ", end='')
                print(f"Processed: {stats['processed']:>3} | ", end='')
                print(f"❌ Failed: {stats['failed']:>2}", end='', flush=True)
                
                # Check if counts changed (new imports happening)
                if self.last_counts and stats['rounds'] != self.last_counts.get('rounds', 0):
                    delta_rounds = stats['rounds'] - self.last_counts.get('rounds', 0)
                    delta_players = stats['players'] - self.last_counts.get('players', 0)
                    print(f" 🆕 +{delta_rounds}R +{delta_players}P", end='')
                
                self.last_counts = stats.copy()
                
                # Every 10 iterations, show problem file status
                if iteration % 10 == 0:
                    print("\n" + "-" * 80)
                    print("🎯 Problem Files Status:")
                    for filename, status in stats['problem_files'].items():
                        if status['processed']:
                            if status['success']:
                                print(f"   ✅ {filename} - SUCCESS")
                            else:
                                print(f"   ❌ {filename} - FAILED: {status['error']}")
                        else:
                            print(f"   ⏳ {filename} - Not yet processed")
                    
                    # Show recent imports
                    if stats['recent']:
                        print("\n📝 Last 5 Imports:")
                        for r in stats['recent']:
                            status_icon = "✅" if r['success'] else "❌"
                            print(f"   {status_icon} {r['filename']}")
                    print("-" * 80)
                
                await asyncio.sleep(1)  # Check every second
                
        except KeyboardInterrupt:
            print("\n\n🛑 Monitoring stopped by user")
        except Exception as e:
            print(f"\n\n❌ Monitor error: {e}")
        finally:
            if self.conn:
                await self.conn.close()
                print("✅ Disconnected from database")

async def main():
    monitor = ImportMonitor()
    await monitor.connect()
    await monitor.monitor()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
