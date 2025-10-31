#!/usr/bin/env python3
"""
Complete Auto-Linking Integration for ET:Legacy Bot
Integrates auto-linking into the main stats processing pipeline
"""
import asyncio
import logging
from pathlib import Path
import sys
import os
import re
from datetime import datetime
from typing import Dict, List, Optional

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from auto_link_database import AutoLinkDatabase, DEFAULT_AUTO_LINK_MAPPINGS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('AutoLinkIntegration')

class SimpleStatsParser:
    """Simplified stats parser for auto-linking integration"""
    
    async def parse_stats_file(self, file_path: str) -> Optional[Dict]:
        """Parse c0rnp0rn3.lua stats file"""
        try:
            with open(file_path, 'r', encoding='latin-1') as f:
                content = f.read()
            
            lines = content.strip().split('\n')
            if len(lines) < 2:
                return None
                
            # Parse header line
            header = lines[0].split('\\')
            if len(header) < 8:
                return None
                
            map_name = header[1]
            round_num = int(header[3]) if header[3].isdigit() else 1
            winner_team = header[5]
            
            # Extract scores from winner_team if format is "allies:3:axis:1"
            team1_score = 0
            team2_score = 0
            if ':' in winner_team:
                parts = winner_team.split(':')
                if len(parts) >= 4:
                    try:
                        team1_score = int(parts[1])
                        team2_score = int(parts[3])
                        winner_team = parts[0]  # Clean team name
                    except ValueError:
                        pass
            
            # Parse players
            players = []
            for line in lines[1:]:
                if not line.strip():
                    continue
                    
                parts = line.split('\\')
                if len(parts) < 10:
                    continue
                    
                try:
                    player_data = {
                        'guid': parts[0],
                        'name': parts[1],
                        'kills': int(parts[3]) if parts[3].isdigit() else 0,
                        'deaths': int(parts[4]) if parts[4].isdigit() else 0,
                        'damage_given': int(parts[5]) if parts[5].isdigit() else 0,
                        'damage_received': int(parts[6]) if parts[6].isdigit() else 0,
                        'headshots': int(parts[7]) if parts[7].isdigit() else 0,
                        'kill_quality': float(parts[8]) if parts[8].replace('.', '').isdigit() else 0.0,
                        'playtime_denied': float(parts[9]) if parts[9].replace('.', '').isdigit() else 0.0
                    }
                    players.append(player_data)
                except (ValueError, IndexError):
                    continue
            
            if not players:
                return None
                
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'map_name': map_name,
                'round_num': round_num,
                'team1_score': team1_score,
                'team2_score': team2_score,
                'winner_team': winner_team,
                'players': players
            }
            
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            return None

class AutoLinkStatsProcessor:
    """Main processor with auto-linking capabilities"""
    
    def __init__(self, db_path: str = "etlegacy_autolink.db"):
        self.db_path = db_path
        self.database = AutoLinkDatabase(db_path, DEFAULT_AUTO_LINK_MAPPINGS)
        self.stats_parser = SimpleStatsParser()
        
    async def initialize(self):
        """Initialize the auto-linking system"""
        await self.database.initialize()
        logger.info("Auto-linking stats processor initialized")
        
    async def process_stats_file(self, file_path: str, is_historical: bool = False):
        """Process a single stats file with auto-linking"""
        try:
            # Check if file was already processed
            filename = Path(file_path).name
            if await self.database.is_file_processed(filename):
                logger.info(f"⏭️  Skipping already processed file: {filename}")
                return False
                
            # Parse the stats file
            logger.info(f"📊 Processing stats file: {filename}")
            parsed_data = await self.stats_parser.parse_stats_file(file_path)
            
            if not parsed_data:
                logger.warning(f"⚠️  No data parsed from {filename}")
                return False
                
            # Save to database with auto-linking
            match_id = await self.database.save_match_stats_with_auto_link(parsed_data)
            
            # Mark file as processed
            file_hash = "placeholder_hash"  # You could implement actual hashing
            await self.database.mark_file_processed(filename, file_hash)
            
            # Log results
            players_count = len(parsed_data.get('players', []))
            logger.info(f"✅ Processed match {match_id} with {players_count} players from {filename}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error processing {file_path}: {e}")
            return False
    
    async def process_directory(self, directory_path: str, is_historical: bool = True):
        """Process all stats files in a directory"""
        directory = Path(directory_path)
        if not directory.exists():
            logger.error(f"Directory not found: {directory_path}")
            return
            
        stats_files = list(directory.glob("*.txt")) + list(directory.glob("*.log"))
        logger.info(f"📁 Found {len(stats_files)} stats files in {directory_path}")
        
        if not stats_files:
            logger.warning("No .txt or .log files found in directory")
            return
            
        processed_count = 0
        skipped_count = 0
        
        for file_path in sorted(stats_files):
            success = await self.process_stats_file(str(file_path), is_historical)
            if success:
                processed_count += 1
            else:
                skipped_count += 1
                
        logger.info(f"📈 Batch processing complete: {processed_count} processed, {skipped_count} skipped")
        
        # Show auto-linking statistics
        await self.show_auto_link_stats()
    
    async def show_auto_link_stats(self):
        """Display auto-linking statistics"""
        stats = await self.database.get_auto_link_stats()
        
        logger.info("🔗 AUTO-LINKING STATISTICS:")
        logger.info(f"   Total Players: {stats['total_players']}")
        logger.info(f"   Auto-linked: {stats['auto_linked']} ({stats['auto_link_rate']:.1f}%)")
        logger.info(f"   Manual-linked: {stats['manual_linked']}")
        logger.info(f"   Unlinked: {stats['unlinked']}")
        logger.info(f"   Available mappings: {stats['available_mappings']}")
        
        if stats['recent_auto_links']:
            logger.info("   Recent auto-links:")
            for et_name, discord_name, linked_at in stats['recent_auto_links'][:5]:
                logger.info(f"     • {et_name} -> {discord_name}")
    
    async def add_discord_mapping(self, guid: str, discord_id: str, discord_name: str):
        """Add a new Discord mapping and apply it retroactively"""
        success = await self.database.add_auto_link_mapping(guid, discord_id, discord_name)
        if success:
            logger.info(f"✅ Successfully linked existing player: {guid} -> {discord_name}")
        else:
            logger.info(f"📝 Added mapping for future auto-linking: {guid} -> {discord_name}")

async def main():
    """Demo of the auto-linking system"""
    processor = AutoLinkStatsProcessor()
    await processor.initialize()
    
    # Test with sample files
    sample_dir = "sample_stats"
    if Path(sample_dir).exists():
        logger.info("🚀 Processing sample stats files with auto-linking...")
        await processor.process_directory(sample_dir, is_historical=True)
    else:
        logger.info("📁 Sample directory not found, creating test data...")
        
        # Create a test entry
        test_data = {
            'timestamp': '2024-01-15T20:30:00Z',
            'map_name': 'te_escape2',
            'round_num': 1,
            'team1_score': 3,
            'team2_score': 1,
            'winner_team': 'allies',
            'players': [
                {
                    'guid': '1C747DF1',
                    'name': 'SmetarskiProner',
                    'kills': 15,
                    'deaths': 8,
                    'damage_given': 1250,
                    'damage_received': 800,
                    'headshots': 3
                },
                {
                    'guid': 'EDBB5DA9', 
                    'name': 'SuperBoyy',
                    'kills': 12,
                    'deaths': 10,
                    'damage_given': 1100,
                    'damage_received': 950,
                    'headshots': 2
                }
            ]
        }
        
        await processor.database.save_match_stats_with_auto_link(test_data)
        await processor.show_auto_link_stats()

if __name__ == "__main__":
    asyncio.run(main())