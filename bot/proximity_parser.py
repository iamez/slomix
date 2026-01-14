"""
PROXIMITY TRACKER DATA PARSER
ET:Legacy Lua Module Data Ingestion

Parses output files from proximity_tracker.lua:
- *_positions.txt     : Position snapshots (x,y,z,velocity,angles)
- *_combat.txt        : Combat events (fire, hit, kill with spatial context)
- *_engagements.txt   : Engagement analysis (1v1, 2v1, crossfire, etc.)
- *_heatmap.txt       : Kill location heatmap grid

Integrates with existing bot database and stats parser.
Stores in PostgreSQL tables for visualization and analytics.
"""

import os
import logging
from typing import Dict, List, Optional


class ProximityDataParser:
    """Parser for proximity_tracker.lua output files"""
    
    def __init__(self, db_adapter=None, output_dir: str = "gamestats"):
        """
        Initialize proximity data parser
        
        Args:
            db_adapter: DatabaseAdapter instance for PostgreSQL access
            output_dir: Directory containing proximity tracker output files
        """
        self.db_adapter = db_adapter
        self.output_dir = output_dir
        self.logger = logging.getLogger(__name__)
        
        # Track parsing state
        self.parsed_data = {
            'positions': [],
            'combat_events': [],
            'engagements': [],
            'heatmap': []
        }
    
    def find_proximity_files(self, session_date: str, round_num: int) -> Dict[str, str]:
        """
        Find proximity tracker output files for a specific session/round
        
        Args:
            session_date: Session date (YYYY-MM-DD format)
            round_num: Round number (1 or 2)
        
        Returns:
            Dictionary with file paths:
            {
                'positions': 'path/to/*_positions.txt',
                'combat': 'path/to/*_combat.txt',
                'engagements': 'path/to/*_engagements.txt',
                'heatmap': 'path/to/*_heatmap.txt'
            }
        """
        files = {
            'positions': None,
            'combat': None,
            'engagements': None,
            'heatmap': None
        }
        
        # List files in output directory
        try:
            for filename in os.listdir(self.output_dir):
                if not filename.startswith(session_date):
                    continue
                
                if f"round-{round_num}" not in filename:
                    continue
                
                filepath = os.path.join(self.output_dir, filename)
                
                if filename.endswith('_positions.txt'):
                    files['positions'] = filepath
                elif filename.endswith('_combat.txt'):
                    files['combat'] = filepath
                elif filename.endswith('_engagements.txt'):
                    files['engagements'] = filepath
                elif filename.endswith('_heatmap.txt'):
                    files['heatmap'] = filepath
        
        except Exception as e:
            self.logger.error(f"Error finding proximity files: {e}")
        
        return files
    
    def parse_positions_file(self, filepath: str) -> List[Dict]:
        """
        Parse position snapshots file
        
        Format: clientnum\ttime\tx\ty\tz\tyaw\tpitch\tspeed\tmoving
        
        Args:
            filepath: Path to *_positions.txt file
        
        Returns:
            List of position snapshots: [{'clientnum': int, 'time': int, 'x': float, ...}]
        """
        positions = []
        
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    
                    # Skip comments and empty lines
                    if not line or line.startswith('#'):
                        continue
                    
                    parts = line.split('\t')
                    if len(parts) < 9:
                        continue
                    
                    try:
                        snapshot = {
                            'clientnum': int(parts[0]),
                            'time': int(parts[1]),
                            'x': float(parts[2]),
                            'y': float(parts[3]),
                            'z': float(parts[4]),
                            'yaw': float(parts[5]),
                            'pitch': float(parts[6]),
                            'speed': float(parts[7]),
                            'moving': int(parts[8])
                        }
                        positions.append(snapshot)
                    
                    except (ValueError, IndexError):
                        self.logger.warning(f"Skipped invalid position line: {line}")
                        continue
        
        except Exception as e:
            self.logger.error(f"Error parsing positions file {filepath}: {e}")
        
        self.parsed_data['positions'] = positions
        self.logger.info(f"Parsed {len(positions)} position snapshots from {filepath}")
        
        return positions
    
    def parse_combat_file(self, filepath: str) -> List[Dict]:
        """
        Parse combat events file
        
        Format: time\ttype\tattacker\ttarget\tdistance\tnearby_allies\tnearby_enemies\tdamage
        
        Args:
            filepath: Path to *_combat.txt file
        
        Returns:
            List of combat events
        """
        events = []
        
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    
                    if not line or line.startswith('#'):
                        continue
                    
                    parts = line.split('\t')
                    if len(parts) < 8:
                        continue
                    
                    try:
                        event = {
                            'timestamp': int(parts[0]),
                            'type': parts[1],  # 'fire', 'hit', 'kill'
                            'attacker': int(parts[2]),
                            'target': int(parts[3]) if parts[3] != 'NONE' else None,
                            'distance': float(parts[4]),
                            'nearby_allies': int(parts[5]),
                            'nearby_enemies': int(parts[6]),
                            'damage': int(parts[7])
                        }
                        events.append(event)
                    
                    except (ValueError, IndexError) as e:
                        self.logger.warning(f"Skipped invalid combat line: {line}")
                        continue
        
        except Exception as e:
            self.logger.error(f"Error parsing combat file {filepath}: {e}")
        
        self.parsed_data['combat_events'] = events
        self.logger.info(f"Parsed {len(events)} combat events from {filepath}")
        
        return events
    
    def parse_engagements_file(self, filepath: str) -> List[Dict]:
        """
        Parse engagement analysis file
        
        Format: engagement_type\tdistance\tkiller\tvictim
        
        Args:
            filepath: Path to *_engagements.txt file
        
        Returns:
            List of engagements
        """
        engagements = []
        
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    
                    if not line or line.startswith('#'):
                        continue
                    
                    parts = line.split('\t')
                    if len(parts) < 4:
                        continue
                    
                    try:
                        engagement = {
                            'type': parts[0],  # '1v1', '2v1', etc.
                            'distance': float(parts[1]),
                            'killer': parts[2],
                            'victim': parts[3]
                        }
                        engagements.append(engagement)
                    
                    except (ValueError, IndexError) as e:
                        self.logger.warning(f"Skipped invalid engagement line: {line}")
                        continue
        
        except Exception as e:
            self.logger.error(f"Error parsing engagements file {filepath}: {e}")
        
        self.parsed_data['engagements'] = engagements
        self.logger.info(f"Parsed {len(engagements)} engagements from {filepath}")
        
        return engagements
    
    def parse_heatmap_file(self, filepath: str) -> List[Dict]:
        """
        Parse heatmap file
        
        Format: grid_x\tgrid_y\taxis_kills\tallies_kills
        
        Args:
            filepath: Path to *_heatmap.txt file
        
        Returns:
            List of heatmap grid cells
        """
        heatmap = []
        
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    
                    if not line or line.startswith('#'):
                        continue
                    
                    parts = line.split('\t')
                    if len(parts) < 4:
                        continue
                    
                    try:
                        cell = {
                            'grid_x': int(parts[0]),
                            'grid_y': int(parts[1]),
                            'axis_kills': int(parts[2]),
                            'allies_kills': int(parts[3])
                        }
                        heatmap.append(cell)
                    
                    except (ValueError, IndexError) as e:
                        self.logger.warning(f"Skipped invalid heatmap line: {line}")
                        continue
        
        except Exception as e:
            self.logger.error(f"Error parsing heatmap file {filepath}: {e}")
        
        self.parsed_data['heatmap'] = heatmap
        self.logger.info(f"Parsed {len(heatmap)} heatmap cells from {filepath}")
        
        return heatmap
    
    async def import_proximity_data(self, session_date: str, round_num: int) -> bool:
        """
        Full import pipeline: find files, parse, and store in database
        
        Args:
            session_date: Session date (YYYY-MM-DD format)
            round_num: Round number (1 or 2)
        
        Returns:
            True if successful, False otherwise
        """
        if not self.db_adapter:
            self.logger.error("Database adapter not initialized")
            return False
        
        # Find proximity files
        files = self.find_proximity_files(session_date, round_num)
        
        if not any(files.values()):
            self.logger.warning(f"No proximity files found for {session_date} round {round_num}")
            return False
        
        # Parse each file
        if files['positions']:
            self.parse_positions_file(files['positions'])
        
        if files['combat']:
            self.parse_combat_file(files['combat'])
        
        if files['engagements']:
            self.parse_engagements_file(files['engagements'])
        
        if files['heatmap']:
            self.parse_heatmap_file(files['heatmap'])
        
        # Store in database
        try:
            await self.store_in_database(session_date, round_num)
            self.logger.info(f"Successfully imported proximity data for {session_date}")
            return True
        
        except Exception as e:
            self.logger.error(f"Error storing proximity data: {e}")
            return False
    
    async def store_in_database(self, session_date: str, round_num: int):
        """
        Store parsed proximity data in PostgreSQL
        
        Creates entries in:
        - player_positions
        - combat_events
        - engagement_analysis
        - proximity_heatmap
        
        Args:
            session_date: Session date
            round_num: Round number
        """
        # Insert positions
        for pos in self.parsed_data['positions']:
            query = """
                INSERT INTO player_positions 
                (session_date, round_number, clientnum, timestamp, x, y, z, yaw, pitch, speed, moving)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (session_date, round_number, clientnum, timestamp) DO NOTHING
            """
            
            await self.db_adapter.execute(
                query,
                (session_date, round_num, pos['clientnum'], pos['time'],
                 pos['x'], pos['y'], pos['z'], pos['yaw'], pos['pitch'],
                 pos['speed'], pos['moving'])
            )
        
        # Insert combat events
        for event in self.parsed_data['combat_events']:
            query = """
                INSERT INTO combat_events
                (session_date, round_number, timestamp, event_type, attacker, target, 
                 distance, nearby_allies, nearby_enemies, damage)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT DO NOTHING
            """
            
            await self.db_adapter.execute(
                query,
                (session_date, round_num, event['timestamp'], event['type'],
                 event['attacker'], event['target'], event['distance'],
                 event['nearby_allies'], event['nearby_enemies'], event['damage'])
            )
        
        # Insert engagement analysis
        for eng in self.parsed_data['engagements']:
            query = """
                INSERT INTO engagement_analysis
                (session_date, round_number, engagement_type, distance, killer_name, victim_name)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT DO NOTHING
            """
            
            await self.db_adapter.execute(
                query,
                (session_date, round_num, eng['type'], eng['distance'],
                 eng['killer'], eng['victim'])
            )
        
        # Insert heatmap
        for cell in self.parsed_data['heatmap']:
            query = """
                INSERT INTO proximity_heatmap
                (session_date, round_number, grid_x, grid_y, axis_kills, allies_kills)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (session_date, round_number, grid_x, grid_y) 
                DO UPDATE SET 
                    axis_kills = axis_kills + EXCLUDED.axis_kills,
                    allies_kills = allies_kills + EXCLUDED.allies_kills
            """
            
            await self.db_adapter.execute(
                query,
                (session_date, round_num, cell['grid_x'], cell['grid_y'],
                 cell['axis_kills'], cell['allies_kills'])
            )
        
        self.logger.info(f"Stored {len(self.parsed_data['positions'])} position records")
        self.logger.info(f"Stored {len(self.parsed_data['combat_events'])} combat events")
        self.logger.info(f"Stored {len(self.parsed_data['engagements'])} engagements")
        self.logger.info(f"Stored {len(self.parsed_data['heatmap'])} heatmap cells")
    
    def get_statistics(self) -> Dict:
        """
        Generate statistics from parsed data
        
        Returns:
            Dictionary with engagement stats, hotspots, etc.
        """
        stats = {
            'total_positions': len(self.parsed_data['positions']),
            'total_combat_events': len(self.parsed_data['combat_events']),
            'total_engagements': len(self.parsed_data['engagements']),
            'total_heatmap_cells': len(self.parsed_data['heatmap']),
            
            # Combat breakdown
            'combat_by_type': {},
            'engagement_type_count': {},
            'average_engagement_distance': 0.0,
            'hotspots': []
        }
        
        # Count combat types
        for event in self.parsed_data['combat_events']:
            event_type = event['type']
            stats['combat_by_type'][event_type] = stats['combat_by_type'].get(event_type, 0) + 1
        
        # Count engagement types
        total_distance = 0
        for eng in self.parsed_data['engagements']:
            eng_type = eng['type']
            stats['engagement_type_count'][eng_type] = \
                stats['engagement_type_count'].get(eng_type, 0) + 1
            total_distance += eng['distance']
        
        if stats['total_engagements'] > 0:
            stats['average_engagement_distance'] = \
                total_distance / stats['total_engagements']
        
        # Top hotspots
        sorted_cells = sorted(
            self.parsed_data['heatmap'],
            key=lambda x: (x['axis_kills'] + x['allies_kills']),
            reverse=True
        )[:5]
        
        stats['hotspots'] = [
            {
                'grid': f"({c['grid_x']}, {c['grid_y']})",
                'axis_kills': c['axis_kills'],
                'allies_kills': c['allies_kills']
            }
            for c in sorted_cells
        ]
        
        return stats
