#!/usr/bin/env python3
"""
🔍 Missing Rounds Audit - Complete File Tracking
================================================================================

Checks the complete pipeline for missing rounds:
1. SSH Remote (game server) - What files exist on server?
2. Local Directory (local_stats/) - What did we download?
3. Database (PostgreSQL) - What did we store?
4. Processed Files Table - What did we attempt to import?

Identifies:
- Files on server but not downloaded
- Files downloaded but not in database
- Files in database but missing their pair (R1 without R2, or vice versa)
- Files that would appear in !last_session command

Author: ET:Legacy Stats System
Date: November 7, 2025
"""

import sys
import os
import asyncio
import asyncssh
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timedelta
import re

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from bot.config import load_config
import asyncpg

# Load configuration
config = load_config()

# SSH Configuration (use getattr for BotConfig object)
SSH_HOST = getattr(config, 'ssh_host', None) or os.getenv('SSH_HOST', '192.168.64.116')
SSH_USER = getattr(config, 'ssh_user', None) or os.getenv('SSH_USER', 'samba')
SSH_KEY_PATH = getattr(config, 'ssh_key_path', None) or os.getenv('SSH_KEY_PATH', '~/.ssh/id_rsa')
# Use REMOTE_STATS_PATH (not ssh_remote_path) to match ssh_monitor.py
SSH_REMOTE_PATH = os.getenv('REMOTE_STATS_PATH', '/home/samba/share/slomix_discord/local_stats')

# PostgreSQL Configuration (BotConfig has these as attributes)
PG_HOST = config.postgres_host
PG_PORT = config.postgres_port
PG_DATABASE = config.postgres_database
PG_USER = config.postgres_user
PG_PASSWORD = config.postgres_password

# Local stats directory
LOCAL_STATS = Path(config.stats_directory)


class MissingRoundsAuditor:
    def __init__(self):
        self.ssh_files = set()
        self.local_files = set()
        self.db_rounds = {}
        self.processed_files = {}
        self.matches = defaultdict(lambda: {'r1': None, 'r2': None, 'r0': None})
        
    async def audit_ssh_remote(self):
        """Check what files exist on SSH server"""
        print("\n" + "="*70)
        print("📡 STEP 1: Checking SSH Remote Directory")
        print("="*70)
        print(f"   Host: {SSH_HOST}")
        print(f"   Path: {SSH_REMOTE_PATH}")
        
        try:
            async with asyncssh.connect(
                SSH_HOST,
                username=SSH_USER,
                client_keys=[SSH_KEY_PATH],
                known_hosts=None
            ) as conn:
                # List all .txt files
                result = await conn.run(f'find {SSH_REMOTE_PATH} -name "*.txt" -type f')
                
                if result.exit_status == 0:
                    files = [line.strip() for line in result.stdout.split('\n') if line.strip()]
                    self.ssh_files = set([Path(f).name for f in files])
                    
                    print(f"✅ Found {len(self.ssh_files)} files on SSH server")
                    
                    # Count by round type
                    r1_count = len([f for f in self.ssh_files if '-round-1.txt' in f])
                    r2_count = len([f for f in self.ssh_files if '-round-2.txt' in f])
                    
                    print(f"   - Round 1 files: {r1_count}")
                    print(f"   - Round 2 files: {r2_count}")
                    
                else:
                    print(f"❌ Failed to list files: {result.stderr}")
                    
        except Exception as e:
            print(f"❌ SSH Error: {e}")
            print("⚠️  Skipping SSH check (not critical - local_stats is source of truth)")
    
    def audit_local_directory(self):
        """Check what files exist in local_stats/"""
        print("\n" + "="*70)
        print("💾 STEP 2: Checking Local Stats Directory")
        print("="*70)
        
        if not LOCAL_STATS.exists():
            print(f"❌ Directory not found: {LOCAL_STATS}")
            return
        
        txt_files = list(LOCAL_STATS.glob("*.txt"))
        self.local_files = set([f.name for f in txt_files])
        
        print(f"✅ Found {len(self.local_files)} files in {LOCAL_STATS}")
        
        # Count by round type
        r1_count = len([f for f in self.local_files if '-round-1.txt' in f])
        r2_count = len([f for f in self.local_files if '-round-2.txt' in f])
        
        print(f"   - Round 1 files: {r1_count}")
        print(f"   - Round 2 files: {r2_count}")
    
    async def audit_database(self):
        """Check what rounds are stored in database"""
        print("\n" + "="*70)
        print("🐘 STEP 3: Checking PostgreSQL Database")
        print("="*70)
        
        try:
            conn = await asyncpg.connect(
                host=PG_HOST,
                port=PG_PORT,
                database=PG_DATABASE,
                user=PG_USER,
                password=PG_PASSWORD
            )
            
            # Get all rounds with their match_id and round_number
            rounds = await conn.fetch("""
                SELECT id, match_id, round_number, round_date, map_name
                FROM rounds
                ORDER BY round_date DESC, round_number
            """)
            
            print(f"✅ Found {len(rounds)} rounds in database")
            
            r0_count = len([r for r in rounds if r['round_number'] == 0])
            r1_count = len([r for r in rounds if r['round_number'] == 1])
            r2_count = len([r for r in rounds if r['round_number'] == 2])
            
            print(f"   - Round 0 (Match Summaries): {r0_count}")
            print(f"   - Round 1: {r1_count}")
            print(f"   - Round 2: {r2_count}")
            
            # Store rounds organized by match
            for r in rounds:
                match_id = r['match_id']
                round_num = r['round_number']
                
                if round_num == 0:
                    self.matches[match_id]['r0'] = r
                elif round_num == 1:
                    self.matches[match_id]['r1'] = r
                elif round_num == 2:
                    self.matches[match_id]['r2'] = r
                
                # Also store by filename (match_id + .txt)
                filename = f"{match_id}.txt"
                self.db_rounds[filename] = r
            
            # Check processed_files table
            processed = await conn.fetch("""
                SELECT filename, success, error_message, processed_at
                FROM processed_files
                ORDER BY processed_at DESC
            """)
            
            print(f"✅ Found {len(processed)} entries in processed_files table")
            
            success_count = len([p for p in processed if p['success']])
            failed_count = len([p for p in processed if not p['success']])
            
            print(f"   - Successfully processed: {success_count}")
            print(f"   - Failed: {failed_count}")
            
            for p in processed:
                self.processed_files[p['filename']] = p
            
            await conn.close()
            
        except Exception as e:
            print(f"❌ Database Error: {e}")
            print("⚠️  Continuing without database data...")
    
    def analyze_discrepancies(self):
        """Find missing or incomplete matches"""
        print("\n" + "="*70)
        print("🔍 STEP 4: Analyzing Discrepancies")
        print("="*70)
        
        # Files on SSH but not local
        ssh_only = self.ssh_files - self.local_files
        if ssh_only:
            print(f"\n⚠️  {len(ssh_only)} files on SSH but NOT in local_stats/:")
            for f in sorted(list(ssh_only)[:10]):  # Show first 10
                print(f"   - {f}")
            if len(ssh_only) > 10:
                print(f"   ... and {len(ssh_only) - 10} more")
        else:
            print("\n✅ All SSH files are downloaded locally")
        
        # Files local but not in database
        local_only = self.local_files - set(self.db_rounds.keys())
        if local_only:
            print(f"\n⚠️  {len(local_only)} files in local_stats/ but NOT in database:")
            for f in sorted(list(local_only)[:10]):
                status = "Not attempted" if f not in self.processed_files else \
                         f"Failed: {self.processed_files[f].get('error_message', 'Unknown')}"
                print(f"   - {f} ({status})")
            if len(local_only) > 10:
                print(f"   ... and {len(local_only) - 10} more")
        else:
            print("\n✅ All local files are in database")
        
        # Incomplete matches (R1 without R2, or R2 without R1)
        print("\n" + "="*70)
        print("🎮 STEP 5: Checking Match Completeness")
        print("="*70)
        
        incomplete_matches = []
        orphaned_r2 = []
        orphaned_r1 = []
        complete_matches = []
        
        for match_id, rounds in self.matches.items():
            has_r0 = rounds['r0'] is not None
            has_r1 = rounds['r1'] is not None
            has_r2 = rounds['r2'] is not None
            
            if has_r1 and has_r2 and has_r0:
                complete_matches.append(match_id)
            elif has_r1 and not has_r2:
                orphaned_r1.append(match_id)
            elif has_r2 and not has_r1:
                orphaned_r2.append(match_id)
            elif has_r0 and not (has_r1 and has_r2):
                incomplete_matches.append(match_id)
        
        print(f"\n✅ {len(complete_matches)} complete matches (R1 + R2 + R0)")
        
        if orphaned_r1:
            print(f"\n⚠️  {len(orphaned_r1)} matches with R1 but NO R2:")
            for match_id in sorted(orphaned_r1)[-5:]:  # Show last 5
                r1 = self.matches[match_id]['r1']
                if r1:  # Safety check
                    print(f"   - {r1['round_date']} - {r1['map_name']} [{match_id}]")
        
        if orphaned_r2:
            print(f"\n⚠️  {len(orphaned_r2)} matches with R2 but NO R1:")
            for match_id in sorted(orphaned_r2)[-5:]:
                r2 = self.matches[match_id]['r2']
                if r2:  # Safety check
                    print(f"   - {r2['round_date']} - {r2['map_name']} [{match_id}]")
        
        if incomplete_matches:
            print(f"\n⚠️  {len(incomplete_matches)} matches with R0 but incomplete rounds:")
            for match_id in incomplete_matches[:5]:
                print(f"   - {match_id}")
        
        if not orphaned_r1 and not orphaned_r2 and not incomplete_matches:
            print("\n✅ All matches are complete!")
    
    async def check_last_session_visibility(self):
        """Check which rounds would appear in !last_session command"""
        print("\n" + "="*70)
        print("💬 STEP 6: Last Session Command Visibility")
        print("="*70)
        
        try:
            conn = await asyncpg.connect(
                host=PG_HOST,
                port=PG_PORT,
                database=PG_DATABASE,
                user=PG_USER,
                password=PG_PASSWORD
            )
            
            # Get the latest gaming session
            latest_session = await conn.fetchrow("""
                SELECT gaming_session_id, MIN(round_date) as start_date, 
                       MAX(round_date) as end_date, COUNT(*) as round_count
                FROM rounds
                WHERE gaming_session_id IS NOT NULL
                GROUP BY gaming_session_id
                ORDER BY gaming_session_id DESC
                LIMIT 1
            """)
            
            if not latest_session:
                print("❌ No gaming sessions found in database")
                await conn.close()
                return
            
            session_id = latest_session['gaming_session_id']
            print(f"\n📊 Latest Gaming Session: #{session_id}")
            print(f"   - Date Range: {latest_session['start_date']} to {latest_session['end_date']}")
            print(f"   - Total Rounds: {latest_session['round_count']}")
            
            # Get rounds in this session
            session_rounds = await conn.fetch("""
                SELECT round_number, COUNT(*) as count
                FROM rounds
                WHERE gaming_session_id = $1
                GROUP BY round_number
                ORDER BY round_number
            """, session_id)
            
            print("\n   Round Distribution:")
            for r in session_rounds:
                round_type = {0: 'Match Summaries', 1: 'Round 1', 2: 'Round 2'}.get(r['round_number'], f'Round {r["round_number"]}')
                print(f"   - {round_type}: {r['count']}")
            
            # Check if !last_session would use round_number=0
            r0_count = next((r['count'] for r in session_rounds if r['round_number'] == 0), 0)
            
            if r0_count > 0:
                print(f"\n✅ !last_session WILL use {r0_count} match summaries (optimized)")
            else:
                print("\n⚠️  !last_session will fall back to aggregating all rounds (slower)")
            
            await conn.close()
            
        except Exception as e:
            print(f"❌ Error checking last session: {e}")
    
    async def run_full_audit(self):
        """Run complete audit"""
        print("\n" + "="*70)
        print("🔍 MISSING ROUNDS AUDIT - COMPLETE PIPELINE CHECK")
        print("="*70)
        
        await self.audit_ssh_remote()
        self.audit_local_directory()
        await self.audit_database()
        self.analyze_discrepancies()
        await self.check_last_session_visibility()
        
        print("\n" + "="*70)
        print("✅ Audit Complete!")
        print("="*70)


async def main():
    auditor = MissingRoundsAuditor()
    await auditor.run_full_audit()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user")
    except Exception as e:
        print(f"\n❌ Fatal Error: {e}")
        import traceback
        traceback.print_exc()
