#!/usr/bin/env python3
"""
Production Auto-Linking Integration for ET:Legacy Discord Bot
Ready for deployment with historical data processing

This script integrates the auto-linking system into the main bot pipeline.
It can:
1. Process historical stats files with auto-linking (silent mode)
2. Handle live stats with Discord notifications and auto-linking
3. Manage auto-link mappings and statistics
"""
import asyncio
import logging
import os
from pathlib import Path
import sys
from typing import Dict, Optional

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from auto_link_database import AutoLinkDatabase, DEFAULT_AUTO_LINK_MAPPINGS
from auto_link_integration import SimpleStatsParser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/auto_link_system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('ProductionAutoLink')

class ProductionAutoLinkSystem:
    """Production-ready auto-linking system for ET:Legacy bot"""
    
    def __init__(self, db_path: str = "src/etlegacy.db"):
        self.db_path = db_path
        self.database = AutoLinkDatabase(db_path, DEFAULT_AUTO_LINK_MAPPINGS)
        self.stats_parser = SimpleStatsParser()
        
        # Configuration from environment
        self.process_historical = os.getenv('PROCESS_HISTORICAL_DATA', 'true').lower() == 'true'
        self.discord_notify_historical = os.getenv('DISCORD_NOTIFY_HISTORICAL', 'false').lower() == 'true'
        
    async def initialize(self):
        """Initialize the production auto-linking system"""
        await self.database.initialize()
        logger.info(f"🚀 Production auto-linking system initialized")
        logger.info(f"   Database: {self.db_path}")
        logger.info(f"   Process Historical: {self.process_historical}")
        logger.info(f"   Discord Notify Historical: {self.discord_notify_historical}")
        logger.info(f"   Auto-link mappings: {len(self.database.auto_link_mappings)}")
        
    async def process_stats_file(self, file_path: str, is_historical: bool = False) -> Dict:
        """Process a stats file with full auto-linking and optional Discord notification"""
        try:
            filename = Path(file_path).name
            
            # Check if already processed
            if await self.database.is_file_processed(filename):
                return {
                    'success': False,
                    'reason': 'already_processed',
                    'message': f"File {filename} already processed"
                }
            
            # Parse the stats
            parsed_data = await self.stats_parser.parse_stats_file(file_path)
            if not parsed_data:
                return {
                    'success': False,
                    'reason': 'parse_failed',
                    'message': f"Failed to parse {filename}"
                }
            
            # Save with auto-linking
            match_id = await self.database.save_match_stats_with_auto_link(parsed_data)
            
            # Mark as processed
            file_hash = "prod_hash"  # Could implement proper hashing
            await self.database.mark_file_processed(filename, file_hash)
            
            # Count auto-links in this match
            auto_linked_count = sum(1 for player in parsed_data.get('players', []) 
                                  if player.get('guid') in self.database.auto_link_mappings)
            
            result = {
                'success': True,
                'match_id': match_id,
                'players_count': len(parsed_data.get('players', [])),
                'auto_linked_count': auto_linked_count,
                'map_name': parsed_data.get('map_name'),
                'timestamp': parsed_data.get('timestamp'),
                'should_notify_discord': not is_historical or self.discord_notify_historical
            }
            
            # Log the processing
            log_level = logging.INFO if not is_historical else logging.DEBUG
            logger.log(log_level, 
                f"✅ Processed {filename}: Match {match_id}, "
                f"{result['players_count']} players, "
                f"{auto_linked_count} auto-linked")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error processing {file_path}: {e}")
            return {
                'success': False,
                'reason': 'exception',
                'message': str(e)
            }
    
    async def process_historical_batch(self, directory_path: str) -> Dict:
        """Process historical stats files in batch mode"""
        directory = Path(directory_path)
        if not directory.exists():
            logger.error(f"Historical directory not found: {directory_path}")
            return {'success': False, 'reason': 'directory_not_found'}
        
        # Find all stats files
        stats_files = list(directory.glob("*.txt")) + list(directory.glob("*.log"))
        if not stats_files:
            # Try .txt files too
            stats_files = list(directory.glob("*.txt"))
            
        logger.info(f"📦 Starting historical batch processing: {len(stats_files)} files")
        
        processed = 0
        skipped = 0
        errors = 0
        auto_linked_total = 0
        
        for file_path in sorted(stats_files):
            result = await self.process_stats_file(str(file_path), is_historical=True)
            
            if result['success']:
                processed += 1
                auto_linked_total += result.get('auto_linked_count', 0)
            elif result['reason'] == 'already_processed':
                skipped += 1
            else:
                errors += 1
        
        # Final statistics
        stats = await self.database.get_auto_link_stats()
        
        batch_result = {
            'success': True,
            'files_processed': processed,
            'files_skipped': skipped,
            'files_errors': errors,
            'total_auto_linked': auto_linked_total,
            'database_stats': stats
        }
        
        logger.info(f"🏁 Historical batch complete:")
        logger.info(f"   Processed: {processed}, Skipped: {skipped}, Errors: {errors}")
        logger.info(f"   Auto-linked in batch: {auto_linked_total}")
        logger.info(f"   Total database players: {stats['total_players']}")
        logger.info(f"   Auto-link rate: {stats['auto_link_rate']:.1f}%")
        
        return batch_result
    
    async def add_discord_mapping(self, guid: str, discord_id: str, discord_name: str) -> bool:
        """Add a new Discord mapping (for live management)"""
        success = await self.database.add_auto_link_mapping(guid, discord_id, discord_name)
        logger.info(f"🔗 Added Discord mapping: {guid} -> {discord_name} ({'applied retroactively' if success else 'for future use'})")
        return success
    
    async def get_system_stats(self) -> Dict:
        """Get comprehensive system statistics"""
        return await self.database.get_auto_link_stats()

# CLI interface for production deployment
async def main():
    """Main entry point for production auto-linking system"""
    import argparse
    
    parser = argparse.ArgumentParser(description='ET:Legacy Auto-Linking System')
    parser.add_argument('--historical-dir', help='Process historical stats directory')
    parser.add_argument('--process-file', help='Process single stats file')
    parser.add_argument('--add-mapping', nargs=3, metavar=('GUID', 'DISCORD_ID', 'DISCORD_NAME'), 
                       help='Add Discord mapping')
    parser.add_argument('--show-stats', action='store_true', help='Show auto-linking statistics')
    parser.add_argument('--db-path', default='src/etlegacy.db', help='Database path')
    
    args = parser.parse_args()
    
    # Initialize system
    system = ProductionAutoLinkSystem(args.db_path)
    await system.initialize()
    
    if args.historical_dir:
        logger.info(f"🔄 Processing historical directory: {args.historical_dir}")
        result = await system.process_historical_batch(args.historical_dir)
        print(f"Batch processing result: {result}")
        
    elif args.process_file:
        logger.info(f"📄 Processing single file: {args.process_file}")
        result = await system.process_stats_file(args.process_file, is_historical=False)
        print(f"File processing result: {result}")
        
    elif args.add_mapping:
        guid, discord_id, discord_name = args.add_mapping
        logger.info(f"➕ Adding Discord mapping: {guid} -> {discord_name}")
        success = await system.add_discord_mapping(guid, discord_id, discord_name)
        print(f"Mapping added successfully: {success}")
        
    elif args.show_stats:
        stats = await system.get_system_stats()
        print("\n🔗 AUTO-LINKING SYSTEM STATISTICS:")
        print(f"   Total Players: {stats['total_players']}")
        print(f"   Auto-linked: {stats['auto_linked']} ({stats['auto_link_rate']:.1f}%)")
        print(f"   Manual-linked: {stats['manual_linked']}")
        print(f"   Unlinked: {stats['unlinked']}")
        print(f"   Available mappings: {stats['available_mappings']}")
        
        if stats['recent_auto_links']:
            print("\n   Recent Auto-Links:")
            for et_name, discord_name, linked_at in stats['recent_auto_links'][:10]:
                print(f"     • {et_name} -> {discord_name}")
    else:
        logger.info("ℹ️  No action specified. Use --help for options.")
        await system.get_system_stats()

if __name__ == "__main__":
    asyncio.run(main())