"""
PROXIMITY TRACKER v3 - ENGAGEMENT PARSER
Parse engagement-centric data and update aggregated stats

Features:
- Parse combat engagements with position paths
- Detect and track crossfire coordination
- Update player teamplay stats (aggregated forever)
- Update crossfire pair stats
- Update per-map heatmaps
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class Attacker:
    guid: str
    name: str
    team: str
    damage: int
    hits: int
    first_hit: int
    last_hit: int
    got_kill: bool
    weapons: Dict[int, int] = field(default_factory=dict)


@dataclass
class Engagement:
    id: int
    start_time: int
    end_time: int
    duration: int
    target_guid: str
    target_name: str
    target_team: str
    outcome: str  # 'killed', 'escaped', 'round_end'
    total_damage: int
    killer_guid: Optional[str]
    killer_name: Optional[str]
    num_attackers: int
    is_crossfire: bool
    crossfire_delay: Optional[int]
    crossfire_participants: List[str]
    start_x: float
    start_y: float
    start_z: float
    end_x: float
    end_y: float
    end_z: float
    distance_traveled: float
    position_path: List[Dict]
    attackers: Dict[str, Attacker]


class ProximityParserV3:
    """Parser for proximity_tracker_v3.lua output files"""
    
    def __init__(self, db_adapter=None, output_dir: str = "gamestats"):
        self.db_adapter = db_adapter
        self.output_dir = output_dir
        self.logger = logging.getLogger(__name__)
        
        # Parsed data
        self.engagements: List[Engagement] = []
        self.kill_heatmap: List[Dict] = []
        self.movement_heatmap: List[Dict] = []
        self.metadata = {
            'map_name': '',
            'round_num': 0,
            'crossfire_window': 1000,
            'escape_time': 5000,
            'escape_distance': 300
        }
    
    def find_files(self, session_date: str = None) -> List[str]:
        """Find v3 engagement files"""
        files = []
        try:
            for filename in os.listdir(self.output_dir):
                if not filename.endswith('_engagements.txt'):
                    continue
                if session_date and not filename.startswith(session_date):
                    continue
                files.append(os.path.join(self.output_dir, filename))
        except Exception as e:
            self.logger.error(f"Error finding files: {e}")
        return sorted(files)
    
    def parse_file(self, filepath: str) -> bool:
        """Parse an engagement file"""
        self.engagements = []
        self.kill_heatmap = []
        self.movement_heatmap = []
        
        section = 'header'
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Metadata
                    if line.startswith('# map='):
                        self.metadata['map_name'] = line.split('=')[1]
                        continue
                    if line.startswith('# round='):
                        self.metadata['round_num'] = int(line.split('=')[1])
                        continue
                    if line.startswith('# crossfire_window='):
                        self.metadata['crossfire_window'] = int(line.split('=')[1])
                        continue
                    if line.startswith('# escape_time='):
                        self.metadata['escape_time'] = int(line.split('=')[1])
                        continue
                    if line.startswith('# escape_distance='):
                        self.metadata['escape_distance'] = int(line.split('=')[1])
                        continue
                    
                    # Section detection
                    if line.startswith('# ENGAGEMENTS'):
                        section = 'engagements'
                        continue
                    if line.startswith('# KILL_HEATMAP'):
                        section = 'kill_heatmap'
                        continue
                    if line.startswith('# MOVEMENT_HEATMAP'):
                        section = 'movement_heatmap'
                        continue
                    
                    # Skip other comments
                    if line.startswith('#'):
                        continue
                    
                    # Parse data
                    if section == 'engagements':
                        self._parse_engagement_line(line)
                    elif section == 'kill_heatmap':
                        self._parse_kill_heatmap_line(line)
                    elif section == 'movement_heatmap':
                        self._parse_movement_heatmap_line(line)
            
            self.logger.info(f"Parsed {len(self.engagements)} engagements from {filepath}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error parsing {filepath}: {e}")
            return False
    
    def _parse_engagement_line(self, line: str):
        """Parse engagement data line (semicolon-delimited)"""
        parts = line.split(';')
        if len(parts) < 24:
            self.logger.warning(f"Invalid engagement line: {line[:50]}...")
            return
        
        try:
            # Parse crossfire participants
            cf_participants = []
            if parts[14]:
                cf_participants = parts[14].split(',')
            
            # Parse position path
            position_path = []
            if parts[22]:
                for pos_str in parts[22].split('|'):
                    pos_parts = pos_str.split(',')
                    if len(pos_parts) >= 5:
                        position_path.append({
                            'time': int(pos_parts[0]),
                            'x': float(pos_parts[1]),
                            'y': float(pos_parts[2]),
                            'z': float(pos_parts[3]),
                            'event': pos_parts[4]
                        })
            
            # Parse attackers
            attackers = {}
            if parts[23]:
                for att_str in parts[23].split('|'):
                    att_parts = att_str.split(',')
                    if len(att_parts) >= 9:
                        # Parse weapons
                        weapons = {}
                        if att_parts[8]:
                            for wp in att_parts[8].split(';'):
                                if ':' in wp:
                                    w_id, w_count = wp.split(':')
                                    if w_id and w_count:
                                        weapons[int(w_id)] = int(w_count)
                        
                        attacker = Attacker(
                            guid=att_parts[0],
                            name=att_parts[1],
                            team=att_parts[2],
                            damage=int(att_parts[3]),
                            hits=int(att_parts[4]),
                            first_hit=int(att_parts[5]),
                            last_hit=int(att_parts[6]),
                            got_kill=att_parts[7] == '1',
                            weapons=weapons
                        )
                        attackers[attacker.guid] = attacker
            
            engagement = Engagement(
                id=int(parts[0]),
                start_time=int(parts[1]),
                end_time=int(parts[2]) if parts[2] else 0,
                duration=int(parts[3]) if parts[3] else 0,
                target_guid=parts[4],
                target_name=parts[5],
                target_team=parts[6],
                outcome=parts[7],
                total_damage=int(parts[8]),
                killer_guid=parts[9] if parts[9] else None,
                killer_name=parts[10] if parts[10] else None,
                num_attackers=int(parts[11]),
                is_crossfire=parts[12] == '1',
                crossfire_delay=int(parts[13]) if parts[13] else None,
                crossfire_participants=cf_participants,
                start_x=float(parts[15]),
                start_y=float(parts[16]),
                start_z=float(parts[17]),
                end_x=float(parts[18]),
                end_y=float(parts[19]),
                end_z=float(parts[20]),
                distance_traveled=float(parts[21]),
                position_path=position_path,
                attackers=attackers
            )
            
            self.engagements.append(engagement)
            
        except (ValueError, IndexError) as e:
            self.logger.warning(f"Error parsing engagement: {e}")
    
    def _parse_kill_heatmap_line(self, line: str):
        """Parse kill heatmap line"""
        parts = line.split(';')
        if len(parts) >= 4:
            try:
                self.kill_heatmap.append({
                    'grid_x': int(parts[0]),
                    'grid_y': int(parts[1]),
                    'axis_kills': int(parts[2]),
                    'allies_kills': int(parts[3])
                })
            except ValueError:
                pass
    
    def _parse_movement_heatmap_line(self, line: str):
        """Parse movement heatmap line"""
        parts = line.split(';')
        if len(parts) >= 5:
            try:
                self.movement_heatmap.append({
                    'grid_x': int(parts[0]),
                    'grid_y': int(parts[1]),
                    'traversal': int(parts[2]),
                    'combat': int(parts[3]),
                    'escape': int(parts[4])
                })
            except ValueError:
                pass
    
    async def import_file(self, filepath: str, session_date: str) -> bool:
        """Parse and import to database"""
        if not self.db_adapter:
            self.logger.error("No database adapter")
            return False
        
        if not self.parse_file(filepath):
            return False
        
        try:
            # Import engagements
            await self._import_engagements(session_date)
            
            # Update player stats
            await self._update_player_stats()
            
            # Update crossfire pairs
            await self._update_crossfire_pairs()
            
            # Import heatmaps
            await self._import_heatmaps()
            
            self.logger.info(f"Successfully imported {filepath}")
            return True
            
        except Exception as e:
            self.logger.error(f"Import error: {e}")
            return False
    
    async def _import_engagements(self, session_date: str):
        """Import engagements to combat_engagement table"""
        for eng in self.engagements:
            # Serialize for JSONB
            position_path_json = json.dumps(eng.position_path)
            attackers_json = json.dumps([
                {
                    'guid': a.guid,
                    'name': a.name,
                    'team': a.team,
                    'damage': a.damage,
                    'hits': a.hits,
                    'first_hit_ms': a.first_hit,
                    'last_hit_ms': a.last_hit,
                    'got_kill': a.got_kill,
                    'weapons': a.weapons
                }
                for a in eng.attackers.values()
            ])
            cf_participants_json = json.dumps(eng.crossfire_participants) if eng.crossfire_participants else None
            
            query = """
                INSERT INTO combat_engagement (
                    session_date, round_number, map_name, engagement_id,
                    start_time_ms, end_time_ms, duration_ms,
                    target_guid, target_name, target_team,
                    outcome, total_damage_taken, killer_guid, killer_name,
                    position_path, start_x, start_y, start_z, end_x, end_y, end_z,
                    distance_traveled, attackers, num_attackers,
                    is_crossfire, crossfire_delay_ms, crossfire_participants
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14,
                    $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27
                )
                ON CONFLICT (session_date, round_number, engagement_id) DO NOTHING
            """
            
            await self.db_adapter.execute(query, (
                session_date,
                self.metadata['round_num'],
                self.metadata['map_name'],
                eng.id,
                eng.start_time,
                eng.end_time,
                eng.duration,
                eng.target_guid,
                eng.target_name,
                eng.target_team,
                eng.outcome,
                eng.total_damage,
                eng.killer_guid,
                eng.killer_name,
                position_path_json,
                eng.start_x, eng.start_y, eng.start_z,
                eng.end_x, eng.end_y, eng.end_z,
                eng.distance_traveled,
                attackers_json,
                eng.num_attackers,
                eng.is_crossfire,
                eng.crossfire_delay,
                cf_participants_json
            ))
    
    async def _update_player_stats(self):
        """Update player_teamplay_stats from engagements"""
        
        # Aggregate stats per player
        player_stats = {}
        
        for eng in self.engagements:
            # Target stats (defensive)
            tg = eng.target_guid
            if tg not in player_stats:
                player_stats[tg] = self._new_player_stats(eng.target_name)
            
            ps = player_stats[tg]
            ps['times_targeted'] += 1
            ps['total_damage_taken'] += eng.total_damage
            
            if eng.num_attackers >= 2:
                ps['times_focused'] += 1
                if eng.outcome == 'escaped':
                    ps['focus_escapes'] += 1
                elif eng.outcome == 'killed':
                    ps['focus_deaths'] += 1
            else:
                if eng.outcome == 'escaped':
                    ps['solo_escapes'] += 1
                elif eng.outcome == 'killed':
                    ps['solo_deaths'] += 1
            
            ps['escape_distances'].append(eng.distance_traveled)
            ps['engagement_durations'].append(eng.duration)
            
            # Attacker stats (offensive)
            for guid, attacker in eng.attackers.items():
                if guid not in player_stats:
                    player_stats[guid] = self._new_player_stats(attacker.name)
                
                ps = player_stats[guid]
                ps['name'] = attacker.name  # Update name
                
                if eng.is_crossfire and guid in eng.crossfire_participants:
                    ps['crossfire_participations'] += 1
                    ps['crossfire_damage'] += attacker.damage
                    
                    if eng.outcome == 'killed':
                        ps['crossfire_kills'] += 1
                        if attacker.got_kill:
                            ps['crossfire_final_blows'] += 1
                    
                    if eng.crossfire_delay:
                        ps['crossfire_delays'].append(eng.crossfire_delay)
                
                elif eng.num_attackers == 1:
                    ps['solo_engagements'] += 1
                    if attacker.got_kill:
                        ps['solo_kills'] += 1
        
        # Upsert to database
        for guid, stats in player_stats.items():
            avg_escape = sum(stats['escape_distances']) / len(stats['escape_distances']) \
                if stats['escape_distances'] else None
            avg_duration = sum(stats['engagement_durations']) / len(stats['engagement_durations']) \
                if stats['engagement_durations'] else None
            avg_crossfire_delay = sum(stats['crossfire_delays']) / len(stats['crossfire_delays']) \
                if stats['crossfire_delays'] else None
            
            query = """
                INSERT INTO player_teamplay_stats (
                    player_guid, player_name,
                    crossfire_participations, crossfire_kills, crossfire_damage,
                    crossfire_final_blows, avg_crossfire_delay_ms,
                    solo_kills, solo_engagements,
                    times_targeted, times_focused, focus_escapes, focus_deaths,
                    solo_escapes, solo_deaths,
                    avg_escape_distance, avg_engagement_duration_ms, total_damage_taken
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18
                )
                ON CONFLICT (player_guid) DO UPDATE SET
                    player_name = EXCLUDED.player_name,
                    crossfire_participations = player_teamplay_stats.crossfire_participations + EXCLUDED.crossfire_participations,
                    crossfire_kills = player_teamplay_stats.crossfire_kills + EXCLUDED.crossfire_kills,
                    crossfire_damage = player_teamplay_stats.crossfire_damage + EXCLUDED.crossfire_damage,
                    crossfire_final_blows = player_teamplay_stats.crossfire_final_blows + EXCLUDED.crossfire_final_blows,
                    solo_kills = player_teamplay_stats.solo_kills + EXCLUDED.solo_kills,
                    solo_engagements = player_teamplay_stats.solo_engagements + EXCLUDED.solo_engagements,
                    times_targeted = player_teamplay_stats.times_targeted + EXCLUDED.times_targeted,
                    times_focused = player_teamplay_stats.times_focused + EXCLUDED.times_focused,
                    focus_escapes = player_teamplay_stats.focus_escapes + EXCLUDED.focus_escapes,
                    focus_deaths = player_teamplay_stats.focus_deaths + EXCLUDED.focus_deaths,
                    solo_escapes = player_teamplay_stats.solo_escapes + EXCLUDED.solo_escapes,
                    solo_deaths = player_teamplay_stats.solo_deaths + EXCLUDED.solo_deaths,
                    total_damage_taken = player_teamplay_stats.total_damage_taken + EXCLUDED.total_damage_taken,
                    last_updated = CURRENT_TIMESTAMP
            """
            
            await self.db_adapter.execute(query, (
                guid, stats['name'],
                stats['crossfire_participations'], stats['crossfire_kills'],
                stats['crossfire_damage'], stats['crossfire_final_blows'],
                avg_crossfire_delay,
                stats['solo_kills'], stats['solo_engagements'],
                stats['times_targeted'], stats['times_focused'],
                stats['focus_escapes'], stats['focus_deaths'],
                stats['solo_escapes'], stats['solo_deaths'],
                avg_escape, avg_duration, stats['total_damage_taken']
            ))
    
    def _new_player_stats(self, name: str) -> Dict:
        """Create empty player stats dict"""
        return {
            'name': name,
            'crossfire_participations': 0,
            'crossfire_kills': 0,
            'crossfire_damage': 0,
            'crossfire_final_blows': 0,
            'crossfire_delays': [],
            'solo_kills': 0,
            'solo_engagements': 0,
            'times_targeted': 0,
            'times_focused': 0,
            'focus_escapes': 0,
            'focus_deaths': 0,
            'solo_escapes': 0,
            'solo_deaths': 0,
            'total_damage_taken': 0,
            'escape_distances': [],
            'engagement_durations': []
        }
    
    async def _update_crossfire_pairs(self):
        """Update crossfire_pairs table for duo tracking"""
        
        pairs = {}  # (guid1, guid2) -> stats
        
        for eng in self.engagements:
            if not eng.is_crossfire or len(eng.crossfire_participants) < 2:
                continue
            
            # Create pairs from all participants
            participants = eng.crossfire_participants
            for i in range(len(participants)):
                for j in range(i + 1, len(participants)):
                    # Sort GUIDs for consistency
                    g1, g2 = sorted([participants[i], participants[j]])
                    key = (g1, g2)
                    
                    if key not in pairs:
                        pairs[key] = {
                            'name1': None,
                            'name2': None,
                            'crossfire_count': 0,
                            'crossfire_kills': 0,
                            'total_damage': 0,
                            'delays': []
                        }
                    
                    # Get names from attackers
                    if g1 in eng.attackers:
                        pairs[key]['name1'] = eng.attackers[g1].name
                    if g2 in eng.attackers:
                        pairs[key]['name2'] = eng.attackers[g2].name
                    
                    pairs[key]['crossfire_count'] += 1
                    if eng.outcome == 'killed':
                        pairs[key]['crossfire_kills'] += 1
                    
                    # Sum damage from both
                    if g1 in eng.attackers:
                        pairs[key]['total_damage'] += eng.attackers[g1].damage
                    if g2 in eng.attackers:
                        pairs[key]['total_damage'] += eng.attackers[g2].damage
                    
                    if eng.crossfire_delay:
                        pairs[key]['delays'].append(eng.crossfire_delay)
        
        # Upsert pairs
        for (g1, g2), stats in pairs.items():
            avg_delay = sum(stats['delays']) / len(stats['delays']) if stats['delays'] else None
            
            query = """
                INSERT INTO crossfire_pairs (
                    player1_guid, player1_name, player2_guid, player2_name,
                    crossfire_count, crossfire_kills, total_combined_damage, avg_delay_ms,
                    games_together, last_played
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 1, CURRENT_TIMESTAMP)
                ON CONFLICT (player1_guid, player2_guid) DO UPDATE SET
                    player1_name = COALESCE(EXCLUDED.player1_name, crossfire_pairs.player1_name),
                    player2_name = COALESCE(EXCLUDED.player2_name, crossfire_pairs.player2_name),
                    crossfire_count = crossfire_pairs.crossfire_count + EXCLUDED.crossfire_count,
                    crossfire_kills = crossfire_pairs.crossfire_kills + EXCLUDED.crossfire_kills,
                    total_combined_damage = crossfire_pairs.total_combined_damage + EXCLUDED.total_combined_damage,
                    games_together = crossfire_pairs.games_together + 1,
                    last_played = CURRENT_TIMESTAMP
            """
            
            await self.db_adapter.execute(query, (
                g1, stats['name1'], g2, stats['name2'],
                stats['crossfire_count'], stats['crossfire_kills'],
                stats['total_damage'], avg_delay
            ))
    
    async def _import_heatmaps(self):
        """Import heatmap data"""
        map_name = self.metadata['map_name']
        
        # Kill heatmap
        for cell in self.kill_heatmap:
            query = """
                INSERT INTO map_kill_heatmap (
                    map_name, grid_x, grid_y,
                    total_kills, axis_kills, allies_kills,
                    total_deaths, axis_deaths, allies_deaths
                ) VALUES ($1, $2, $3, $4, $5, $6, $4, $6, $5)
                ON CONFLICT (map_name, grid_x, grid_y) DO UPDATE SET
                    total_kills = map_kill_heatmap.total_kills + EXCLUDED.total_kills,
                    axis_kills = map_kill_heatmap.axis_kills + EXCLUDED.axis_kills,
                    allies_kills = map_kill_heatmap.allies_kills + EXCLUDED.allies_kills,
                    total_deaths = map_kill_heatmap.total_deaths + EXCLUDED.total_deaths,
                    axis_deaths = map_kill_heatmap.axis_deaths + EXCLUDED.axis_deaths,
                    allies_deaths = map_kill_heatmap.allies_deaths + EXCLUDED.allies_deaths,
                    updated_at = CURRENT_TIMESTAMP
            """
            total = cell['axis_kills'] + cell['allies_kills']
            await self.db_adapter.execute(query, (
                map_name, cell['grid_x'], cell['grid_y'],
                total, cell['axis_kills'], cell['allies_kills']
            ))
        
        # Movement heatmap
        for cell in self.movement_heatmap:
            query = """
                INSERT INTO map_movement_heatmap (
                    map_name, grid_x, grid_y,
                    traversal_count, combat_count, escape_count
                ) VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (map_name, grid_x, grid_y) DO UPDATE SET
                    traversal_count = map_movement_heatmap.traversal_count + EXCLUDED.traversal_count,
                    combat_count = map_movement_heatmap.combat_count + EXCLUDED.combat_count,
                    escape_count = map_movement_heatmap.escape_count + EXCLUDED.escape_count,
                    updated_at = CURRENT_TIMESTAMP
            """
            await self.db_adapter.execute(query, (
                map_name, cell['grid_x'], cell['grid_y'],
                cell['traversal'], cell['combat'], cell['escape']
            ))
    
    def get_stats(self) -> Dict:
        """Get summary of parsed data"""
        crossfire_count = sum(1 for e in self.engagements if e.is_crossfire)
        kills = sum(1 for e in self.engagements if e.outcome == 'killed')
        escapes = sum(1 for e in self.engagements if e.outcome == 'escaped')
        
        return {
            'map': self.metadata['map_name'],
            'round': self.metadata['round_num'],
            'total_engagements': len(self.engagements),
            'crossfire_engagements': crossfire_count,
            'kills': kills,
            'escapes': escapes,
            'heatmap_cells': len(self.kill_heatmap)
        }


# ===== CLI TESTING =====
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    
    parser = ProximityParserV3(output_dir="gamestats")
    
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
    else:
        files = parser.find_files()
        if not files:
            print("No engagement files found")
            sys.exit(1)
        filepath = files[-1]
    
    print(f"Parsing: {filepath}")
    parser.parse_file(filepath)
    
    stats = parser.get_stats()
    print(f"\n=== STATS ===")
    print(f"Map: {stats['map']}, Round: {stats['round']}")
    print(f"Engagements: {stats['total_engagements']}")
    print(f"  Crossfire: {stats['crossfire_engagements']}")
    print(f"  Kills: {stats['kills']}")
    print(f"  Escapes: {stats['escapes']}")
    print(f"Heatmap cells: {stats['heatmap_cells']}")
    
    if parser.engagements:
        print(f"\n=== SAMPLE ENGAGEMENT ===")
        e = parser.engagements[0]
        print(f"ID: {e.id}, Target: {e.target_name}")
        print(f"Outcome: {e.outcome}, Duration: {e.duration}ms")
        print(f"Attackers: {[a.name for a in e.attackers.values()]}")
        print(f"Crossfire: {e.is_crossfire}, Delay: {e.crossfire_delay}ms")
        print(f"Position path: {len(e.position_path)} points")
