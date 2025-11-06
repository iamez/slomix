#!/usr/bin/env python3
"""
🧪 DRY RUN - Database Rebuild Simulation
================================================================================

Simulates the nuclear wipe and rebuild process WITHOUT touching the database.

This script will:
1. Connect to PostgreSQL (read-only)
2. Show current database stats
3. Find files for last 14 days
4. Simulate parsing and validation
5. Show what WOULD be inserted
6. Provide detailed report

NO DATA IS MODIFIED - completely safe to run!

Usage:
    python dry_run_rebuild.py
"""
import asyncio
import asyncpg
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List
import time

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from bot.community_stats_parser import C0RNP0RN3StatsParser
from bot.config import load_config


class DryRunSimulator:
    """Simulates database rebuild without modifying data"""
    
    def __init__(self, stats_dir: str = "local_stats"):
        self.config = load_config()
        self.stats_dir = Path(stats_dir)
        self.parser = C0RNP0RN3StatsParser()
        self.pool = None
        
        # Simulation stats
        self.sim_stats = {
            'files_found': 0,
            'files_would_process': 0,
            'files_would_skip': 0,
            'rounds_would_create': 0,
            'players_would_insert': 0,
            'weapons_would_insert': 0,
            'total_kills': 0,
            'total_deaths': 0,
            'total_damage': 0,
            'parse_errors': 0
        }
        
        self.player_names = set()
        self.weapon_types = set()
        self.maps_played = set()
    
    async def connect(self):
        """Connect to PostgreSQL (read-only)"""
        try:
            self.pool = await asyncpg.create_pool(
                host=self.config.postgres_host.split(':')[0],
                port=int(self.config.postgres_host.split(':')[1]) if ':' in self.config.postgres_host else 5432,
                database=self.config.postgres_database,
                user=self.config.postgres_user,
                password=self.config.postgres_password,
                min_size=1,
                max_size=3
            )
            print(f"✅ Connected to PostgreSQL: {self.config.postgres_host}/{self.config.postgres_database}")
        except Exception as e:
            print(f"❌ Failed to connect: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from PostgreSQL"""
        if self.pool:
            await self.pool.close()
            print("✅ Disconnected from PostgreSQL")
    
    async def show_current_stats(self):
        """Show current database statistics"""
        print("\n" + "=" * 70)
        print("📊 CURRENT DATABASE STATE (Before Wipe)")
        print("=" * 70)
        
        async with self.pool.acquire() as conn:
            # Get table counts
            rounds = await conn.fetchval("SELECT COUNT(*) FROM rounds")
            players = await conn.fetchval("SELECT COUNT(*) FROM player_comprehensive_stats")
            weapons = await conn.fetchval("SELECT COUNT(*) FROM weapon_comprehensive_stats")
            processed = await conn.fetchval("SELECT COUNT(*) FROM processed_files")
            
            print(f"   Rounds: {rounds:,}")
            print(f"   Player stats: {players:,}")
            print(f"   Weapon stats: {weapons:,}")
            print(f"   Processed files: {processed:,}")
            
            # Date range
            date_range = await conn.fetchrow(
                "SELECT MIN(round_date) as min_date, MAX(round_date) as max_date FROM rounds"
            )
            if date_range and date_range['min_date']:
                print(f"   Date range: {date_range['min_date']} to {date_range['max_date']}")
            
            # Top players
            top_players = await conn.fetch(
                """
                SELECT player_name, SUM(kills) as total_kills, COUNT(*) as rounds
                FROM player_comprehensive_stats
                GROUP BY player_name
                ORDER BY total_kills DESC
                LIMIT 5
                """
            )
            print("\n   Top 5 Players:")
            for i, p in enumerate(top_players, 1):
                print(f"      {i}. {p['player_name']}: {p['total_kills']:,} kills ({p['rounds']} rounds)")
    
    def find_files_for_period(self, days: int = 14) -> List[Path]:
        """Find all files for the last N days"""
        print(f"\n🔍 Finding files for last {days} days...")
        
        # Calculate cutoff date
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        print(f"   Cutoff date: {cutoff_date}")
        
        # Find all stat files
        all_files = sorted(self.stats_dir.glob("*.txt"))
        
        # Filter by date
        files_in_range = [f for f in all_files if f.name[:10] >= cutoff_date]
        
        print(f"   Total files in stats directory: {len(all_files):,}")
        print(f"   Files in last {days} days: {len(files_in_range):,}")
        
        self.sim_stats['files_found'] = len(files_in_range)
        
        return files_in_range
    
    def simulate_file_processing(self, file_path: Path) -> Dict:
        """Simulate processing a single file"""
        try:
            # Parse the file
            parsed_data = self.parser.parse_stats_file(str(file_path))
            
            if not parsed_data or parsed_data.get('error'):
                self.sim_stats['parse_errors'] += 1
                return {'success': False, 'error': parsed_data.get('error', 'Parse failed')}
            
            # Extract stats
            players = parsed_data.get('players', [])
            map_name = parsed_data.get('map_name', 'unknown')
            round_num = parsed_data.get('round_number', 1)
            
            # Count what would be inserted
            player_count = len(players)
            weapon_count = sum(len(p.get('weapon_stats', {}) or p.get('weapons', {})) for p in players)
            total_kills = sum(p.get('kills', 0) for p in players)
            total_deaths = sum(p.get('deaths', 0) for p in players)
            total_damage = sum(p.get('damage_given', 0) for p in players)
            
            # Track unique items
            for p in players:
                self.player_names.add(p.get('name', 'Unknown'))
                weapons = p.get('weapon_stats', {}) or p.get('weapons', {})
                for w in weapons.keys():
                    self.weapon_types.add(w)
            self.maps_played.add(map_name)
            
            # Update simulation stats
            self.sim_stats['rounds_would_create'] += 1
            self.sim_stats['players_would_insert'] += player_count
            self.sim_stats['weapons_would_insert'] += weapon_count
            self.sim_stats['total_kills'] += total_kills
            self.sim_stats['total_deaths'] += total_deaths
            self.sim_stats['total_damage'] += total_damage
            
            return {
                'success': True,
                'players': player_count,
                'weapons': weapon_count,
                'kills': total_kills,
                'map': map_name,
                'round': round_num
            }
            
        except Exception as e:
            self.sim_stats['parse_errors'] += 1
            return {'success': False, 'error': str(e)}
    
    async def simulate_rebuild(self, days: int = 14):
        """Simulate the complete rebuild process"""
        print("\n" + "=" * 70)
        print("🧪 DRY RUN SIMULATION - Nuclear Wipe & Rebuild")
        print("=" * 70)
        print("\n⚠️  THIS IS A SIMULATION - NO DATA WILL BE MODIFIED!")
        print()
        
        # Step 1: Show current state
        await self.show_current_stats()
        
        # Step 2: Find files
        files = self.find_files_for_period(days)
        
        if not files:
            print("\n❌ No files found for this period!")
            return
        
        # Step 3: Simulate processing
        print(f"\n🔄 Simulating processing of {len(files):,} files...")
        print()
        
        start_time = time.time()
        
        for i, file_path in enumerate(files, 1):
            result = self.simulate_file_processing(file_path)
            
            if result['success']:
                self.sim_stats['files_would_process'] += 1
            else:
                self.sim_stats['files_would_skip'] += 1
            
            # Progress update every 50 files
            if i % 50 == 0 or i == len(files):
                elapsed = time.time() - start_time
                rate = i / elapsed if elapsed > 0 else 0
                print(f"   Progress: {i}/{len(files)} files ({i/len(files)*100:.1f}%) - {rate:.1f} files/sec")
        
        elapsed = time.time() - start_time
        
        # Step 4: Show simulation results
        print("\n" + "=" * 70)
        print("📈 SIMULATION RESULTS (What WOULD Happen)")
        print("=" * 70)
        print("\n🔄 Processing Stats:")
        print(f"   Files found: {self.sim_stats['files_found']:,}")
        print(f"   Files would process: {self.sim_stats['files_would_process']:,}")
        print(f"   Files would skip: {self.sim_stats['files_would_skip']:,}")
        print(f"   Parse errors: {self.sim_stats['parse_errors']:,}")
        print(f"   Processing time: {elapsed:.1f} seconds")
        print(f"   Processing rate: {self.sim_stats['files_found']/elapsed:.1f} files/sec")
        
        print("\n📊 Data That Would Be Inserted:")
        print(f"   Rounds: {self.sim_stats['rounds_would_create']:,}")
        print(f"   Player stats: {self.sim_stats['players_would_insert']:,}")
        print(f"   Weapon stats: {self.sim_stats['weapons_would_insert']:,}")
        
        print("\n🎮 Game Statistics:")
        print(f"   Total kills: {self.sim_stats['total_kills']:,}")
        print(f"   Total deaths: {self.sim_stats['total_deaths']:,}")
        print(f"   Total damage: {self.sim_stats['total_damage']:,}")
        print(f"   Unique players: {len(self.player_names):,}")
        print(f"   Unique weapons: {len(self.weapon_types):,}")
        print(f"   Maps played: {len(self.maps_played):,}")
        
        print("\n🗺️  Maps in simulation:")
        for map_name in sorted(self.maps_played):
            print(f"   - {map_name}")
        
        print("\n🔫 Weapons in simulation:")
        weapon_list = sorted(list(self.weapon_types))
        for i in range(0, len(weapon_list), 4):
            weapons_row = weapon_list[i:i+4]
            print(f"   {', '.join(weapons_row)}")
        
        # Compare with current
        print("\n" + "=" * 70)
        print("📉 DATABASE IMPACT COMPARISON")
        print("=" * 70)
        
        async with self.pool.acquire() as conn:
            current_rounds = await conn.fetchval("SELECT COUNT(*) FROM rounds")
            current_players = await conn.fetchval("SELECT COUNT(*) FROM player_comprehensive_stats")
            current_weapons = await conn.fetchval("SELECT COUNT(*) FROM weapon_comprehensive_stats")
        
        print(f"\n   Current Database:")
        print(f"      Rounds: {current_rounds:,}")
        print(f"      Player stats: {current_players:,}")
        print(f"      Weapon stats: {current_weapons:,}")
        
        print(f"\n   After Rebuild (simulated):")
        print(f"      Rounds: {self.sim_stats['rounds_would_create']:,}")
        print(f"      Player stats: {self.sim_stats['players_would_insert']:,}")
        print(f"      Weapon stats: {self.sim_stats['weapons_would_insert']:,}")
        
        print(f"\n   Difference:")
        rounds_diff = self.sim_stats['rounds_would_create'] - current_rounds
        players_diff = self.sim_stats['players_would_insert'] - current_players
        weapons_diff = self.sim_stats['weapons_would_insert'] - current_weapons
        
        print(f"      Rounds: {rounds_diff:+,} ({rounds_diff/current_rounds*100:+.1f}%)")
        print(f"      Player stats: {players_diff:+,} ({players_diff/current_players*100:+.1f}%)")
        print(f"      Weapon stats: {weapons_diff:+,} ({weapons_diff/current_weapons*100:+.1f}%)")
        
        # Recommendations
        print("\n" + "=" * 70)
        print("💡 RECOMMENDATIONS")
        print("=" * 70)
        
        if self.sim_stats['parse_errors'] > 0:
            print(f"\n⚠️  WARNING: {self.sim_stats['parse_errors']} files had parse errors!")
            print("   These files will be skipped during real rebuild.")
        
        if rounds_diff < 0:
            print(f"\n⚠️  WARNING: Rebuild would DELETE {abs(rounds_diff):,} rounds!")
            print(f"   Current database has data from BEFORE last {days} days.")
            print(f"   Consider using a longer period or don't do nuclear wipe.")
        
        if self.sim_stats['files_would_process'] == 0:
            print("\n❌ ERROR: No files would be processed!")
            print("   DO NOT proceed with rebuild - database would be empty!")
        else:
            print("\n✅ Simulation looks good!")
            print(f"   {self.sim_stats['files_would_process']:,} files ready to import")
            print(f"   {self.sim_stats['rounds_would_create']:,} rounds would be created")
            print(f"   {self.sim_stats['players_would_insert']:,} player stats would be inserted")
            
            if rounds_diff < 0:
                print("\n⚠️  However, you would LOSE older data!")
                print("   Consider these options:")
                print("   1. Increase days period to cover all data")
                print("   2. Use surgical date range fix instead of nuclear wipe")
                print("   3. Proceed if you only want recent data")
            else:
                print("\n✅ Safe to proceed with nuclear rebuild!")
                print(f"   Database would have MORE data after rebuild")
        
        print("\n" + "=" * 70)
        print("🧪 DRY RUN COMPLETE - No changes made to database")
        print("=" * 70)


async def main():
    """Run the dry run simulation"""
    print("\n" + "=" * 70)
    print("🧪 DRY RUN - Database Rebuild Simulation")
    print("=" * 70)
    print("\nThis script simulates a nuclear wipe and rebuild WITHOUT modifying data.")
    print("It's completely safe to run!")
    print()
    
    # Get period
    days_input = input("How many days to simulate? [14]: ").strip()
    days = int(days_input) if days_input else 14
    
    print(f"\n🚀 Starting simulation for last {days} days...")
    
    simulator = DryRunSimulator()
    
    try:
        await simulator.connect()
        await simulator.simulate_rebuild(days=days)
    except KeyboardInterrupt:
        print("\n\n⚠️  Simulation interrupted by user")
    except Exception as e:
        print(f"\n❌ Simulation failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await simulator.disconnect()
    
    print("\n👋 Simulation complete!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
