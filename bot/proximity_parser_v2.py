"""
PROXIMITY TRACKER v2 - PARSER
Kill-Centric Data Ingestion

Parses single output file from proximity_tracker_v2.lua:
- *_proximity.txt - Kill events with full context + heatmap

350x less data than v1. ~70 rows/round vs ~24,500.
"""

import os
import logging
from typing import Dict, List, Tuple


class ProximityParserV2:
    """Parser for proximity_tracker_v2.lua output files"""
    
    def __init__(self, db_adapter=None, output_dir: str = "gamestats"):
        self.db_adapter = db_adapter
        self.output_dir = output_dir
        self.logger = logging.getLogger(__name__)
        
        # Parsed data
        self.kills = []
        self.heatmap = []
        self.metadata = {
            'map_name': '',
            'round_num': 0
        }
    
    def find_proximity_files(self, session_date: str = None) -> List[str]:
        """
        Find proximity tracker v2 output files
        
        Args:
            session_date: Optional YYYY-MM-DD filter
        
        Returns:
            List of file paths matching *_proximity.txt
        """
        files = []
        
        try:
            for filename in os.listdir(self.output_dir):
                if not filename.endswith('_proximity.txt'):
                    continue
                
                if session_date and not filename.startswith(session_date):
                    continue
                
                files.append(os.path.join(self.output_dir, filename))
        
        except Exception as e:
            self.logger.error(f"Error finding proximity files: {e}")
        
        return sorted(files)
    
    def parse_file(self, filepath: str) -> Tuple[List[Dict], List[Dict], Dict]:
        """
        Parse a proximity v2 output file
        
        Args:
            filepath: Path to *_proximity.txt file
        
        Returns:
            Tuple of (kills, heatmap, metadata)
        """
        self.kills = []
        self.heatmap = []
        self.metadata = {'map_name': '', 'round_num': 0}
        
        section = 'kills'  # Start in kills section
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    line = line.strip()
                    
                    # Skip empty lines
                    if not line:
                        continue
                    
                    # Parse metadata comments
                    if line.startswith('# map='):
                        self.metadata['map_name'] = line.split('=')[1]
                        continue
                    
                    if line.startswith('# round='):
                        self.metadata['round_num'] = int(line.split('=')[1])
                        continue
                    
                    # Skip other comments
                    if line.startswith('#'):
                        # Check for section switch
                        if 'HEATMAP' in line:
                            section = 'heatmap'
                        continue
                    
                    # Parse data based on section
                    if section == 'kills':
                        self._parse_kill_line(line)
                    elif section == 'heatmap':
                        self._parse_heatmap_line(line)
        
        except Exception as e:
            self.logger.error(f"Error parsing file {filepath}: {e}")
        
        self.logger.info(f"Parsed {len(self.kills)} kills, {len(self.heatmap)} heatmap cells from {filepath}")
        
        return self.kills, self.heatmap, self.metadata
    
    def _parse_kill_line(self, line: str):
        """Parse a kill data line (pipe-delimited)"""
        parts = line.split('|')
        
        if len(parts) < 22:
            self.logger.warning(f"Skipped invalid kill line: {line[:50]}...")
            return
        
        try:
            kill = {
                'game_time': int(parts[0]),
                'killer_slot': int(parts[1]),
                'killer_guid': parts[2],
                'killer_name': parts[3],
                'killer_team': parts[4],
                'killer_x': float(parts[5]),
                'killer_y': float(parts[6]),
                'killer_z': float(parts[7]),
                'victim_slot': int(parts[8]),
                'victim_guid': parts[9],
                'victim_name': parts[10],
                'victim_team': parts[11],
                'victim_x': float(parts[12]),
                'victim_y': float(parts[13]),
                'victim_z': float(parts[14]),
                'distance': float(parts[15]),
                'weapon': int(parts[16]),
                'mod': int(parts[17]),
                'engagement_type': parts[18],
                'killer_nearby_allies': int(parts[19]),
                'victim_nearby_allies': int(parts[20]),
                'supporting_allies': parts[21] if parts[21] != 'NONE' else None
            }
            self.kills.append(kill)
        
        except (ValueError, IndexError) as e:
            self.logger.warning(f"Error parsing kill line: {e}")
    
    def _parse_heatmap_line(self, line: str):
        """Parse a heatmap data line (pipe-delimited)"""
        parts = line.split('|')
        
        if len(parts) < 4:
            return
        
        try:
            cell = {
                'grid_x': int(parts[0]),
                'grid_y': int(parts[1]),
                'axis_kills': int(parts[2]),
                'allies_kills': int(parts[3])
            }
            self.heatmap.append(cell)
        
        except (ValueError, IndexError) as e:
            self.logger.warning(f"Error parsing heatmap line: {e}")
    
    async def import_file(self, filepath: str, session_date: str) -> bool:
        """
        Parse file and import to database
        
        Args:
            filepath: Path to proximity file
            session_date: Session date (YYYY-MM-DD)
        
        Returns:
            True if successful
        """
        if not self.db_adapter:
            self.logger.error("Database adapter not initialized")
            return False
        
        kills, heatmap, metadata = self.parse_file(filepath)
        
        if not kills and not heatmap:
            self.logger.warning(f"No data parsed from {filepath}")
            return False
        
        try:
            # Import kills
            for kill in kills:
                # Convert supporting_allies to JSON array or null
                supporting_json = None
                if kill['supporting_allies']:
                    allies_list = kill['supporting_allies'].split(',')
                    import json
                    supporting_json = json.dumps(allies_list)
                
                query = """
                    INSERT INTO kill_context (
                        session_date, round_number, map_name, game_time,
                        killer_slot, killer_guid, killer_name, killer_team,
                        killer_x, killer_y, killer_z,
                        victim_slot, victim_guid, victim_name, victim_team,
                        victim_x, victim_y, victim_z,
                        kill_distance, weapon, means_of_death,
                        engagement_type, killer_nearby_allies, victim_nearby_allies,
                        supporting_allies
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
                        $12, $13, $14, $15, $16, $17, $18, $19, $20, $21,
                        $22, $23, $24, $25
                    )
                    ON CONFLICT (session_date, round_number, game_time, killer_slot, victim_slot) 
                    DO NOTHING
                """
                
                await self.db_adapter.execute(query, (
                    session_date,
                    metadata['round_num'],
                    metadata['map_name'],
                    kill['game_time'],
                    kill['killer_slot'],
                    kill['killer_guid'],
                    kill['killer_name'],
                    kill['killer_team'],
                    kill['killer_x'],
                    kill['killer_y'],
                    kill['killer_z'],
                    kill['victim_slot'],
                    kill['victim_guid'],
                    kill['victim_name'],
                    kill['victim_team'],
                    kill['victim_x'],
                    kill['victim_y'],
                    kill['victim_z'],
                    kill['distance'],
                    kill['weapon'],
                    kill['mod'],
                    kill['engagement_type'],
                    kill['killer_nearby_allies'],
                    kill['victim_nearby_allies'],
                    supporting_json
                ))
            
            # Import heatmap (upsert - add to existing counts)
            for cell in heatmap:
                query = """
                    INSERT INTO kill_heatmap (
                        session_date, map_name, grid_x, grid_y,
                        axis_kills, allies_kills, total_kills
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (session_date, map_name, grid_x, grid_y) 
                    DO UPDATE SET
                        axis_kills = kill_heatmap.axis_kills + EXCLUDED.axis_kills,
                        allies_kills = kill_heatmap.allies_kills + EXCLUDED.allies_kills,
                        total_kills = kill_heatmap.total_kills + EXCLUDED.total_kills
                """
                
                total = cell['axis_kills'] + cell['allies_kills']
                await self.db_adapter.execute(query, (
                    session_date,
                    metadata['map_name'],
                    cell['grid_x'],
                    cell['grid_y'],
                    cell['axis_kills'],
                    cell['allies_kills'],
                    total
                ))
            
            # Update player proximity stats (aggregate)
            await self._update_player_stats(session_date, kills)
            
            self.logger.info(f"Imported {len(kills)} kills from {filepath}")
            return True
        
        except Exception as e:
            self.logger.error(f"Error importing to database: {e}")
            return False
    
    async def _update_player_stats(self, session_date: str, kills: List[Dict]):
        """Update player_proximity_stats table from kills data"""
        
        # Aggregate by player GUID
        player_stats = {}
        
        for kill in kills:
            # Update killer stats
            k_guid = kill['killer_guid']
            if k_guid not in player_stats:
                player_stats[k_guid] = {
                    'name': kill['killer_name'],
                    'kills': 0, 'deaths': 0,
                    'solo_kills': 0, 'assisted_kills': 0, 'outgunned_kills': 0,
                    'solo_deaths': 0, 'ganked_deaths': 0,
                    'distances': [], 'crossfire': 0
                }
            
            ps = player_stats[k_guid]
            ps['name'] = kill['killer_name']  # Update to latest name
            ps['kills'] += 1
            ps['distances'].append(kill['distance'])
            
            eng = kill['engagement_type']
            if eng == '1v1':
                ps['solo_kills'] += 1
            elif kill['killer_nearby_allies'] > 0:
                ps['assisted_kills'] += 1
            elif kill['victim_nearby_allies'] > 0:
                ps['outgunned_kills'] += 1
            
            # Update victim stats
            v_guid = kill['victim_guid']
            if v_guid not in player_stats:
                player_stats[v_guid] = {
                    'name': kill['victim_name'],
                    'kills': 0, 'deaths': 0,
                    'solo_kills': 0, 'assisted_kills': 0, 'outgunned_kills': 0,
                    'solo_deaths': 0, 'ganked_deaths': 0,
                    'distances': [], 'crossfire': 0
                }
            
            ps = player_stats[v_guid]
            ps['name'] = kill['victim_name']
            ps['deaths'] += 1
            
            if eng == '1v1':
                ps['solo_deaths'] += 1
            elif kill['killer_nearby_allies'] > 0:
                ps['ganked_deaths'] += 1
            
            # Track crossfire participation (supporting allies)
            if kill['supporting_allies']:
                for ally_name in kill['supporting_allies'].split(','):
                    # Find GUID for this ally name (approximation)
                    for guid, stats in player_stats.items():
                        if stats['name'] == ally_name:
                            stats['crossfire'] += 1
                            break
        
        # Upsert player stats
        for guid, stats in player_stats.items():
            avg_dist = sum(stats['distances']) / len(stats['distances']) if stats['distances'] else 0
            min_dist = min(stats['distances']) if stats['distances'] else 0
            max_dist = max(stats['distances']) if stats['distances'] else 0
            
            query = """
                INSERT INTO player_proximity_stats (
                    session_date, player_guid, player_name,
                    total_kills, solo_kills, assisted_kills, outgunned_kills,
                    total_deaths, solo_deaths, ganked_deaths,
                    avg_kill_distance, min_kill_distance, max_kill_distance,
                    crossfire_participations
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                ON CONFLICT (session_date, player_guid) 
                DO UPDATE SET
                    player_name = EXCLUDED.player_name,
                    total_kills = player_proximity_stats.total_kills + EXCLUDED.total_kills,
                    solo_kills = player_proximity_stats.solo_kills + EXCLUDED.solo_kills,
                    assisted_kills = player_proximity_stats.assisted_kills + EXCLUDED.assisted_kills,
                    outgunned_kills = player_proximity_stats.outgunned_kills + EXCLUDED.outgunned_kills,
                    total_deaths = player_proximity_stats.total_deaths + EXCLUDED.total_deaths,
                    solo_deaths = player_proximity_stats.solo_deaths + EXCLUDED.solo_deaths,
                    ganked_deaths = player_proximity_stats.ganked_deaths + EXCLUDED.ganked_deaths,
                    crossfire_participations = player_proximity_stats.crossfire_participations + EXCLUDED.crossfire_participations,
                    updated_at = CURRENT_TIMESTAMP
            """
            
            await self.db_adapter.execute(query, (
                session_date, guid, stats['name'],
                stats['kills'], stats['solo_kills'], stats['assisted_kills'], stats['outgunned_kills'],
                stats['deaths'], stats['solo_deaths'], stats['ganked_deaths'],
                avg_dist, min_dist, max_dist,
                stats['crossfire']
            ))
    
    def get_stats(self) -> Dict:
        """Get summary statistics from last parsed file"""
        
        if not self.kills:
            return {'kills': 0, 'heatmap_cells': 0}
        
        engagement_counts = {}
        for kill in self.kills:
            eng = kill['engagement_type']
            engagement_counts[eng] = engagement_counts.get(eng, 0) + 1
        
        distances = [k['distance'] for k in self.kills]
        
        return {
            'map': self.metadata['map_name'],
            'round': self.metadata['round_num'],
            'total_kills': len(self.kills),
            'heatmap_cells': len(self.heatmap),
            'engagement_breakdown': engagement_counts,
            'avg_kill_distance': sum(distances) / len(distances) if distances else 0,
            'min_distance': min(distances) if distances else 0,
            'max_distance': max(distances) if distances else 0
        }


# ===== STANDALONE TESTING =====
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format='%(message)s')
    logger = logging.getLogger(__name__)

    parser = ProximityParserV2(output_dir="gamestats")

    if len(sys.argv) > 1:
        filepath = sys.argv[1]
    else:
        files = parser.find_proximity_files()
        if not files:
            logger.warning("No proximity files found in gamestats/")
            sys.exit(1)
        filepath = files[-1]  # Most recent

    logger.info(f"Parsing: {filepath}")
    kills, heatmap, meta = parser.parse_file(filepath)

    stats = parser.get_stats()
    logger.info("=== STATS ===")
    logger.info(f"Map: {stats['map']}, Round: {stats['round']}")
    logger.info(f"Kills: {stats['total_kills']}")
    logger.info(f"Heatmap cells: {stats['heatmap_cells']}")
    logger.info(f"Engagement breakdown: {stats['engagement_breakdown']}")
    logger.info(f"Kill distance: avg={stats['avg_kill_distance']:.1f}, min={stats['min_distance']:.1f}, max={stats['max_distance']:.1f}")
