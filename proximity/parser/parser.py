"""
PROXIMITY TRACKER v4.1 - FULL PLAYER TRACKING PARSER
Parse engagement-centric data AND full player tracks

Features:
- Parse PLAYER_TRACKS: Full spawn-to-death movement for all players
- Parse combat engagements with position paths
- Detect and track crossfire coordination
- Update player teamplay stats (aggregated forever)
- Update crossfire pair stats
- Update per-map heatmaps

v4.1 Output Format:
- PLAYER_TRACKS: guid;name;team;class;spawn_time;death_time;first_move_time;death_type;samples;path
- death_type: killed|selfkill|fallen|world|teamkill|round_end|disconnect|unknown
- path format: time,x,y,z,health,speed,weapon,stance,sprint,event separated by |
"""

import os
import json
import logging
import re
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, field

PROXIMITY_FILENAME_ROUND_RE = re.compile(r"-round-(\d+)_engagements\.txt$", re.IGNORECASE)
GAMETIME_FILENAME_RE = re.compile(r"^gametime-(?P<map>.+)-R(?P<round>\d+)-(?P<ts>\d+)\.json$")


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


@dataclass
class PathPoint:
    """Single point in a player's movement path"""
    time: int           # Timestamp in ms
    x: float
    y: float
    z: float
    health: int
    speed: float
    weapon: int
    stance: int         # 0=standing, 1=crouching, 2=prone
    sprint: int         # 0=not sprinting, 1=sprinting
    event: str          # spawn, sample, death, round_end


@dataclass
class PlayerTrack:
    """Full player track from spawn to death"""
    guid: str
    name: str
    team: str
    player_class: str   # SOLDIER, MEDIC, ENGINEER, FIELDOPS, COVERTOPS
    spawn_time: int
    death_time: Optional[int]
    first_move_time: Optional[int]  # When player first moved after spawn
    death_type: Optional[str]  # v4.1: killed|selfkill|fallen|world|teamkill|round_end|disconnect|unknown
    sample_count: int
    path: List[PathPoint] = field(default_factory=list)

    @property
    def duration_ms(self) -> int:
        """How long player was alive"""
        if self.death_time and self.spawn_time:
            return self.death_time - self.spawn_time
        return 0

    @property
    def time_to_first_move_ms(self) -> Optional[int]:
        """Time from spawn until first movement"""
        if self.first_move_time and self.spawn_time:
            return self.first_move_time - self.spawn_time
        return None

    @property
    def total_distance(self) -> float:
        """Calculate total distance traveled"""
        if len(self.path) < 2:
            return 0.0
        total = 0.0
        for i in range(1, len(self.path)):
            p1, p2 = self.path[i-1], self.path[i]
            dx = p2.x - p1.x
            dy = p2.y - p1.y
            dz = p2.z - p1.z
            total += (dx*dx + dy*dy + dz*dz) ** 0.5
        return total

    @property
    def avg_speed(self) -> float:
        """Average speed across all samples"""
        if not self.path:
            return 0.0
        speeds = [p.speed for p in self.path if p.speed > 0]
        return sum(speeds) / len(speeds) if speeds else 0.0

    @property
    def sprint_percentage(self) -> float:
        """Percentage of time sprinting"""
        if not self.path:
            return 0.0
        sprinting = sum(1 for p in self.path if p.sprint == 1)
        return (sprinting / len(self.path)) * 100


class ProximityParserV4:
    """Parser for proximity_tracker v4 output files with full player tracking"""

    def __init__(self, db_adapter=None, output_dir: str = "gamestats", gametimes_dir: str = "local_gametimes"):
        self.db_adapter = db_adapter
        self.output_dir = output_dir
        self.gametimes_dir = gametimes_dir
        self.logger = logging.getLogger(__name__)

        # Parsed data
        self.engagements: List[Engagement] = []
        self.player_tracks: List[PlayerTrack] = []  # v4: Full player tracks
        self.kill_heatmap: List[Dict] = []
        self.movement_heatmap: List[Dict] = []
        self.trade_events: List[Dict] = []
        self.support_summary: Optional[Dict] = None
        self.metadata = self._metadata_defaults()
        self._schema_cache: Dict[tuple, bool] = {}

    @staticmethod
    def _metadata_defaults() -> Dict:
        return {
            'map_name': '',
            'round_num': 0,
            'round_num_source': 'header',
            'crossfire_window': 1000,
            'escape_time': 5000,
            'escape_distance': 300,
            'position_sample_interval': 1000,  # v4: track sample rate
            'round_start_unix': 0,
            'round_end_unix': 0,
        }

    @staticmethod
    def _extract_round_from_filename(filepath: str) -> Optional[int]:
        match = PROXIMITY_FILENAME_ROUND_RE.search(os.path.basename(filepath))
        if not match:
            return None
        try:
            value = int(match.group(1))
        except ValueError:
            return None
        return value if value > 0 else None

    def _extract_round_from_gametime(self, map_name: str, round_end_unix: int) -> Optional[int]:
        if not map_name or round_end_unix <= 0:
            return None

        gametime_root = Path(self.gametimes_dir)
        if not gametime_root.exists():
            return None

        # Use round_end_unix as the stable join key between proximity and gametimes fallback files.
        pattern = f"gametime-*-R*-{round_end_unix}.json"
        map_name_lower = map_name.lower()
        for candidate in sorted(gametime_root.glob(pattern)):
            match = GAMETIME_FILENAME_RE.match(candidate.name)
            if not match:
                continue
            if match.group('map').lower() != map_name_lower:
                continue
            try:
                value = int(match.group('round'))
            except ValueError:
                return None
            return value if value > 0 else None
        return None

    def _normalize_round_metadata(self, filepath: str) -> None:
        header_round = int(self.metadata.get('round_num') or 0)
        map_name = str(self.metadata.get('map_name') or '')
        round_end_unix = int(self.metadata.get('round_end_unix') or 0)

        gametime_round = self._extract_round_from_gametime(map_name, round_end_unix)
        filename_round = self._extract_round_from_filename(filepath)

        normalized_round = header_round
        source = 'header'
        if gametime_round:
            normalized_round = gametime_round
            source = 'gametime'
        elif filename_round:
            normalized_round = filename_round
            source = 'filename'
        elif normalized_round <= 0:
            normalized_round = 1
            source = 'default'

        if normalized_round != header_round:
            self.logger.info(
                "[ROUND NORMALIZED] file=%s map=%s header=%s normalized=%s source=%s round_end_unix=%s",
                os.path.basename(filepath),
                map_name,
                header_round,
                normalized_round,
                source,
                round_end_unix,
            )

        self.metadata['round_num'] = normalized_round
        self.metadata['round_num_source'] = source
    
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
        """Parse an engagement file (v3 or v4 format)"""
        self.metadata = self._metadata_defaults()
        self.engagements = []
        self.player_tracks = []
        self.kill_heatmap = []
        self.movement_heatmap = []
        self.objective_focus = []
        self.trade_events = []
        self.support_summary = None

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
                        try:
                            self.metadata['round_num'] = int(line.split('=')[1])
                        except ValueError:
                            self.metadata['round_num'] = 0
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
                    if line.startswith('# position_sample_interval='):
                        self.metadata['position_sample_interval'] = int(line.split('=')[1])
                        continue
                    if line.startswith('# round_start_unix='):
                        try:
                            self.metadata['round_start_unix'] = int(line.split('=')[1])
                        except ValueError:
                            self.metadata['round_start_unix'] = 0
                        continue
                    if line.startswith('# round_end_unix='):
                        try:
                            self.metadata['round_end_unix'] = int(line.split('=')[1])
                        except ValueError:
                            self.metadata['round_end_unix'] = 0
                        continue

                    # Section detection
                    if line.startswith('# ENGAGEMENTS'):
                        section = 'engagements'
                        continue
                    if line.startswith('# PLAYER_TRACKS'):
                        section = 'player_tracks'
                        continue
                    if line.startswith('# KILL_HEATMAP'):
                        section = 'kill_heatmap'
                        continue
                    if line.startswith('# MOVEMENT_HEATMAP'):
                        section = 'movement_heatmap'
                        continue
                    if line.startswith('# OBJECTIVE_FOCUS'):
                        section = 'objective_focus'
                        continue

                    # Skip other comments
                    if line.startswith('#'):
                        continue

                    # Parse data
                    if section == 'engagements':
                        self._parse_engagement_line(line)
                    elif section == 'player_tracks':
                        self._parse_player_track_line(line)
                    elif section == 'kill_heatmap':
                        self._parse_kill_heatmap_line(line)
                    elif section == 'movement_heatmap':
                        self._parse_movement_heatmap_line(line)
                    elif section == 'objective_focus':
                        self._parse_objective_focus_line(line)

            self._normalize_round_metadata(filepath)
            self.logger.info(f"Parsed {len(self.engagements)} engagements, {len(self.player_tracks)} tracks from {filepath}")
            return True

        except Exception as e:
            self.logger.error(f"Error parsing {filepath}: {e}")
            return False

    async def _table_has_column(self, table: str, column: str) -> bool:
        if not self.db_adapter:
            return False
        key = (table, column)
        cached = self._schema_cache.get(key)
        if cached is not None:
            return cached
        query = """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = $1
              AND column_name = $2
            LIMIT 1
        """
        try:
            row = await self.db_adapter.fetch_one(query, (table, column))
            self._schema_cache[key] = bool(row)
        except Exception:
            self._schema_cache[key] = False
        return self._schema_cache[key]
    
    def _parse_engagement_line(self, line: str):
        """Parse engagement data line (semicolon-delimited)"""
        # Keep attacker payload intact: it contains weapon pairs separated by ';'
        # so we only split the first 23 delimiters (24 columns total).
        parts = line.split(';', 23)
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

    def _parse_player_track_line(self, line: str):
        """Parse player track line (v4/v4.1 format)

        v4.1 Format: guid;name;team;class;spawn_time;death_time;first_move_time;death_type;samples;path
        v4 Format:   guid;name;team;class;spawn_time;death_time;first_move_time;samples;path
        Path format: time,x,y,z,health,speed,weapon,stance,sprint,event separated by |
        """
        parts = line.split(';')
        if len(parts) < 9:
            self.logger.warning(f"Invalid track line: {line[:50]}...")
            return

        try:
            guid = parts[0]
            name = parts[1]
            team = parts[2]
            player_class = parts[3]
            spawn_time = int(parts[4])
            death_time = int(parts[5]) if parts[5] and parts[5] != '0' else None
            first_move_time = int(parts[6]) if parts[6] else None

            # v4.1 format has death_type as 8th field, v4 has samples
            # Detect format by checking if field 7 looks like a number (sample_count) or a string (death_type)
            if len(parts) >= 10:
                # v4.1 format: death_type is field 7, samples is field 8, path is field 9
                death_type = parts[7] if parts[7] and parts[7] != 'unknown' else None
                sample_count = int(parts[8])
                path_data = parts[9] if len(parts) > 9 else ""
            else:
                # v4 format: samples is field 7, path is field 8, no death_type
                death_type = None
                sample_count = int(parts[7])
                path_data = parts[8] if len(parts) > 8 else ""

            # Parse path
            path = []
            if path_data:
                for point_str in path_data.split('|'):
                    point_parts = point_str.split(',')
                    if len(point_parts) >= 10:
                        path.append(PathPoint(
                            time=int(point_parts[0]),
                            x=float(point_parts[1]),
                            y=float(point_parts[2]),
                            z=float(point_parts[3]),
                            health=int(point_parts[4]),
                            speed=float(point_parts[5]),
                            weapon=int(point_parts[6]),
                            stance=int(point_parts[7]),
                            sprint=int(point_parts[8]),
                            event=point_parts[9]
                        ))

            track = PlayerTrack(
                guid=guid,
                name=name,
                team=team,
                player_class=player_class,
                spawn_time=spawn_time,
                death_time=death_time,
                first_move_time=first_move_time,
                death_type=death_type,
                sample_count=sample_count,
                path=path
            )

            self.player_tracks.append(track)

        except (ValueError, IndexError) as e:
            self.logger.warning(f"Error parsing track: {e}")

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
            except ValueError as exc:
                self.logger.debug("Skipping invalid kill heatmap entry: %s (%s)", line, exc)
    
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
            except ValueError as exc:
                self.logger.debug("Skipping invalid movement heatmap entry: %s (%s)", line, exc)

    def _parse_objective_focus_line(self, line: str):
        """Parse objective focus line (optional section)"""
        parts = line.split(';')
        if len(parts) >= 7:
            try:
                self.objective_focus.append({
                    'guid': parts[0],
                    'name': parts[1],
                    'team': parts[2],
                    'objective': parts[3],
                    'avg_distance': float(parts[4]),
                    'time_within_radius_ms': int(parts[5]),
                    'samples': int(parts[6]),
                })
            except ValueError as exc:
                self.logger.debug("Skipping invalid objective focus entry: %s (%s)", line, exc)
    
    async def import_file(self, filepath: str, session_date) -> bool:
        """Parse and import to database

        Args:
            filepath: Path to engagement file
            session_date: Date as string (YYYY-MM-DD) or datetime.date object
        """
        if not self.db_adapter:
            self.logger.error("No database adapter")
            return False

        if not self.parse_file(filepath):
            return False

        # Convert string date to date object if needed
        if isinstance(session_date, str):
            from datetime import datetime
            session_date = datetime.strptime(session_date, '%Y-%m-%d').date()

        try:
            # Import engagements
            await self._import_engagements(session_date)

            # Import player tracks (v4)
            if self.player_tracks:
                await self._import_player_tracks(session_date)

            # Update player stats
            await self._update_player_stats()

            # Update crossfire pairs
            await self._update_crossfire_pairs()

            # Import heatmaps
            await self._import_heatmaps()

            # Import objective focus (optional)
            if self.objective_focus:
                await self._import_objective_focus(session_date)

            # Compute + import trade events (v1)
            if self.engagements and self.player_tracks:
                self._compute_trade_events()
                await self._import_trade_events(session_date)

            # Compute + import support uptime summary
            if self.player_tracks:
                self.support_summary = self._compute_support_uptime()
                if self.support_summary:
                    await self._import_support_summary(session_date)

            self.logger.info(f"Successfully imported {filepath}")
            return True

        except Exception as e:
            self.logger.error(f"Import error: {e}")
            return False
    
    async def _import_engagements(self, session_date: str):
        """Import engagements to combat_engagement table"""
        supports_round_end = await self._table_has_column('combat_engagement', 'round_end_unix')
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

            columns = [
                "session_date", "round_number", "round_start_unix",
                "map_name", "engagement_id",
                "start_time_ms", "end_time_ms", "duration_ms",
                "target_guid", "target_name", "target_team",
                "outcome", "total_damage_taken", "killer_guid", "killer_name",
                "position_path", "start_x", "start_y", "start_z", "end_x", "end_y", "end_z",
                "distance_traveled", "attackers", "num_attackers",
                "is_crossfire", "crossfire_delay_ms", "crossfire_participants",
            ]
            values = [
                session_date,
                self.metadata['round_num'],
                self.metadata.get('round_start_unix', 0),
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
                cf_participants_json,
            ]
            if supports_round_end:
                columns.insert(3, "round_end_unix")
                values.insert(3, self.metadata.get('round_end_unix', 0))
            placeholders = ", ".join(f"${i}" for i in range(1, len(values) + 1))
            query = f"""
                INSERT INTO combat_engagement ({", ".join(columns)})
                VALUES ({placeholders})
                ON CONFLICT (session_date, round_number, round_start_unix, engagement_id)
                DO NOTHING
            """
            await self.db_adapter.execute(query, tuple(values))

    async def _import_player_tracks(self, session_date: str):
        """Import player tracks to player_track table (v4)"""
        supports_round_end = await self._table_has_column('player_track', 'round_end_unix')
        for track in self.player_tracks:
            # Serialize path as JSONB
            path_json = json.dumps([
                {
                    'time': p.time,
                    'x': p.x,
                    'y': p.y,
                    'z': p.z,
                    'health': p.health,
                    'speed': p.speed,
                    'weapon': p.weapon,
                    'stance': p.stance,
                    'sprint': p.sprint,
                    'event': p.event
                }
                for p in track.path
            ])

            # Calculate derived stats
            duration_ms = track.duration_ms
            time_to_first_move = track.time_to_first_move_ms
            total_distance = track.total_distance
            avg_speed = track.avg_speed
            sprint_pct = track.sprint_percentage

            columns = [
                "session_date", "round_number", "round_start_unix",
                "map_name",
                "player_guid", "player_name", "team", "player_class",
                "spawn_time_ms", "death_time_ms", "duration_ms",
                "first_move_time_ms", "time_to_first_move_ms",
                "sample_count", "path",
                "total_distance", "avg_speed", "sprint_percentage",
            ]
            values = [
                session_date,
                self.metadata['round_num'],
                self.metadata.get('round_start_unix', 0),
                self.metadata['map_name'],
                track.guid,
                track.name,
                track.team,
                track.player_class,
                track.spawn_time,
                track.death_time,
                duration_ms,
                track.first_move_time,
                time_to_first_move,
                track.sample_count,
                path_json,
                total_distance,
                avg_speed,
                sprint_pct,
            ]
            if supports_round_end:
                columns.insert(3, "round_end_unix")
                values.insert(3, self.metadata.get('round_end_unix', 0))
            placeholders = ", ".join(f"${i}" for i in range(1, len(values) + 1))
            query = f"""
                INSERT INTO player_track ({", ".join(columns)})
                VALUES ({placeholders})
                ON CONFLICT (session_date, round_number, round_start_unix, player_guid, spawn_time_ms)
                DO NOTHING
            """
            await self.db_adapter.execute(query, tuple(values))

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

    async def _import_objective_focus(self, session_date: str):
        """Import objective focus metrics if table exists"""
        supports_round_end = await self._table_has_column('proximity_objective_focus', 'round_end_unix')
        for row in self.objective_focus:
            columns = [
                "session_date", "round_number", "round_start_unix",
                "map_name",
                "player_guid", "player_name", "team",
                "objective", "avg_distance", "time_within_radius_ms", "samples",
            ]
            values = [
                session_date,
                self.metadata['round_num'],
                self.metadata.get('round_start_unix', 0),
                self.metadata['map_name'],
                row['guid'],
                row['name'],
                row['team'],
                row['objective'],
                row['avg_distance'],
                row['time_within_radius_ms'],
                row['samples'],
            ]
            if supports_round_end:
                columns.insert(3, "round_end_unix")
                values.insert(3, self.metadata.get('round_end_unix', 0))
            placeholders = ", ".join(f"${i}" for i in range(1, len(values) + 1))
            query = f"""
                INSERT INTO proximity_objective_focus ({", ".join(columns)})
                VALUES ({placeholders})
                ON CONFLICT (session_date, round_number, round_start_unix, player_guid) DO UPDATE SET
                    player_name = EXCLUDED.player_name,
                    team = EXCLUDED.team,
                    objective = EXCLUDED.objective,
                    avg_distance = EXCLUDED.avg_distance,
                    time_within_radius_ms = EXCLUDED.time_within_radius_ms,
                    samples = EXCLUDED.samples
            """
            await self.db_adapter.execute(query, tuple(values))

    def _distance2d(self, a: Tuple[float, float, float], b: Tuple[float, float, float]) -> float:
        dx = (a[0] or 0) - (b[0] or 0)
        dy = (a[1] or 0) - (b[1] or 0)
        return (dx * dx + dy * dy) ** 0.5

    def _closest_track_point(self, track: PlayerTrack, target_time: int, max_delta_ms: int) -> Optional[PathPoint]:
        if not track.path:
            return None
        closest = None
        best_delta = None
        for p in track.path:
            delta = abs(p.time - target_time)
            if best_delta is None or delta < best_delta:
                best_delta = delta
                closest = p
        if best_delta is None or best_delta > max_delta_ms:
            return None
        return closest

    def _track_for_time(self, tracks: List[PlayerTrack], target_time: int) -> Optional[PlayerTrack]:
        for track in tracks:
            if track.spawn_time <= target_time and (track.death_time is None or track.death_time >= target_time):
                return track
        return None

    def _merge_intervals(self, intervals: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        if not intervals:
            return []
        intervals_sorted = sorted(intervals, key=lambda x: x[0])
        merged = [intervals_sorted[0]]
        for start, end in intervals_sorted[1:]:
            last_start, last_end = merged[-1]
            if start <= last_end + 1:
                merged[-1] = (last_start, max(last_end, end))
            else:
                merged.append((start, end))
        return merged

    def _is_in_combat(self, intervals: List[Tuple[int, int]], time_ms: int) -> bool:
        if not intervals:
            return False
        for start, end in intervals:
            if start <= time_ms <= end:
                return True
        return False

    def _compute_support_uptime(self) -> Optional[Dict]:
        if not self.player_tracks:
            return None

        support_dist = float(os.getenv("PROXIMITY_SUPPORT_DIST", "600"))
        combat_recent_ms = int(os.getenv("PROXIMITY_COMBAT_RECENT_MS", "1500"))
        max_pos_delta = int(os.getenv("PROXIMITY_SUPPORT_POS_DELTA_MS", "1500"))

        combat_intervals_by_guid: Dict[str, List[Tuple[int, int]]] = {}

        for eng in self.engagements:
            if eng.start_time and eng.end_time:
                combat_intervals_by_guid.setdefault(eng.target_guid, []).append(
                    (eng.start_time, eng.end_time + combat_recent_ms)
                )
            for attacker in eng.attackers.values():
                if attacker.first_hit and attacker.last_hit:
                    combat_intervals_by_guid.setdefault(attacker.guid, []).append(
                        (attacker.first_hit, attacker.last_hit + combat_recent_ms)
                    )

        for guid, intervals in list(combat_intervals_by_guid.items()):
            combat_intervals_by_guid[guid] = self._merge_intervals(intervals)

        tracks = list(self.player_tracks)
        support_samples = 0
        total_samples = 0

        for track in tracks:
            if not track.path:
                continue
            for point in track.path:
                total_samples += 1
                in_support = False
                for teammate in tracks:
                    if teammate.guid == track.guid or teammate.team != track.team:
                        continue
                    if not (teammate.spawn_time <= point.time and (teammate.death_time is None or teammate.death_time >= point.time)):
                        continue
                    if not self._is_in_combat(combat_intervals_by_guid.get(teammate.guid, []), point.time):
                        continue
                    teammate_point = self._closest_track_point(teammate, point.time, max_pos_delta)
                    if not teammate_point:
                        continue
                    dist = self._distance2d((point.x, point.y, point.z), (teammate_point.x, teammate_point.y, teammate_point.z))
                    if dist <= support_dist:
                        in_support = True
                        break
                if in_support:
                    support_samples += 1

        if total_samples == 0:
            return None

        return {
            "support_samples": support_samples,
            "total_samples": total_samples,
            "support_uptime_pct": round(support_samples * 100 / total_samples, 2),
        }

    def _compute_trade_events(self):
        if not self.engagements or not self.player_tracks:
            return

        trade_window_ms = int(os.getenv("PROXIMITY_TRADE_WINDOW_MS", "3000"))
        trade_dist = float(os.getenv("PROXIMITY_TRADE_DIST", "800"))
        max_pos_delta = int(os.getenv("PROXIMITY_TRADE_POS_DELTA_MS", "1500"))
        isolation_dist = float(os.getenv("PROXIMITY_ISOLATION_DIST", "1200"))

        tracks_by_guid: Dict[str, List[PlayerTrack]] = {}
        for track in self.player_tracks:
            tracks_by_guid.setdefault(track.guid, []).append(track)
        for guid in tracks_by_guid:
            tracks_by_guid[guid].sort(key=lambda t: t.spawn_time)

        engagements_by_target: Dict[str, List[Engagement]] = {}
        for eng in self.engagements:
            engagements_by_target.setdefault(eng.target_guid, []).append(eng)
        for engs in engagements_by_target.values():
            engs.sort(key=lambda e: e.start_time)

        trade_events = []
        for eng in self.engagements:
            if eng.outcome != 'killed' or not eng.killer_guid:
                continue

            death_time = eng.end_time
            victim_team = eng.target_team
            victim_guid = eng.target_guid
            victim_pos = (eng.end_x, eng.end_y, eng.end_z)

            opportunities = []
            nearest_teammate_dist = None
            for guid, tracks in tracks_by_guid.items():
                if guid == victim_guid:
                    continue
                track = self._track_for_time(tracks, death_time)
                if not track or track.team != victim_team:
                    continue
                point = self._closest_track_point(track, death_time, max_pos_delta)
                if not point:
                    continue
                dist = self._distance2d(victim_pos, (point.x, point.y, point.z))
                if nearest_teammate_dist is None or dist < nearest_teammate_dist:
                    nearest_teammate_dist = dist
                if dist <= trade_dist:
                    opportunities.append({
                        "guid": track.guid,
                        "name": track.name,
                        "distance": round(dist, 1),
                        "delta_ms": abs(point.time - death_time),
                    })

            attempts_map: Dict[str, Dict] = {}
            successes_map: Dict[str, Dict] = {}

            killer_engagements = engagements_by_target.get(eng.killer_guid, [])
            for k_eng in killer_engagements:
                for attacker in k_eng.attackers.values():
                    if attacker.team != victim_team:
                        continue
                    if attacker.first_hit < death_time or attacker.first_hit > death_time + trade_window_ms:
                        continue
                    existing = attempts_map.get(attacker.guid)
                    if not existing or attacker.first_hit < existing["first_hit_ms"]:
                        attempts_map[attacker.guid] = {
                            "guid": attacker.guid,
                            "name": attacker.name,
                            "first_hit_ms": attacker.first_hit,
                            "damage": attacker.damage,
                        }

                if k_eng.outcome == 'killed' and death_time <= k_eng.end_time <= death_time + trade_window_ms:
                    for attacker in k_eng.attackers.values():
                        if attacker.team != victim_team or not attacker.got_kill:
                            continue
                        successes_map[attacker.guid] = {
                            "guid": attacker.guid,
                            "name": attacker.name,
                            "kill_time_ms": k_eng.end_time,
                        }

            attempts = list(attempts_map.values())
            successes = list(successes_map.values())

            missed_candidates = []
            if opportunities and not attempts and not successes:
                for opp in opportunities:
                    missed_candidates.append({
                        "guid": opp["guid"],
                        "name": opp["name"],
                        "distance": opp["distance"],
                        "reason": "no_attempt",
                    })

            is_isolation = bool(
                (nearest_teammate_dist is None or nearest_teammate_dist > isolation_dist)
                and not opportunities
            )

            trade_events.append({
                "victim_guid": victim_guid,
                "victim_name": eng.target_name,
                "victim_team": victim_team,
                "killer_guid": eng.killer_guid,
                "killer_name": eng.killer_name,
                "death_time_ms": death_time,
                "trade_window_ms": trade_window_ms,
                "opportunities": opportunities,
                "attempts": attempts,
                "successes": successes,
                "missed_candidates": missed_candidates,
                "nearest_teammate_dist": round(nearest_teammate_dist, 1) if nearest_teammate_dist is not None else None,
                "is_isolation_death": is_isolation,
            })

        self.trade_events = trade_events

    async def _import_trade_events(self, session_date: str):
        if not self.trade_events:
            return
        if not await self._table_has_column('proximity_trade_event', 'victim_guid'):
            self.logger.info("proximity_trade_event table not found; skipping trade import")
            return
        supports_round_end = await self._table_has_column('proximity_trade_event', 'round_end_unix')
        for event in self.trade_events:
            columns = [
                "session_date", "round_number", "round_start_unix",
                "map_name",
                "victim_guid", "victim_name", "victim_team",
                "killer_guid", "killer_name",
                "death_time_ms", "trade_window_ms",
                "nearest_teammate_dist", "is_isolation_death",
                "opportunity_count", "opportunities",
                "attempt_count", "attempts",
                "success_count", "successes",
                "missed_count", "missed_candidates",
            ]
            values = [
                session_date,
                self.metadata['round_num'],
                self.metadata.get('round_start_unix', 0),
                self.metadata['map_name'],
                event["victim_guid"],
                event["victim_name"],
                event["victim_team"],
                event["killer_guid"],
                event["killer_name"],
                event["death_time_ms"],
                event["trade_window_ms"],
                event.get("nearest_teammate_dist"),
                event.get("is_isolation_death", False),
                len(event["opportunities"]),
                json.dumps(event["opportunities"]),
                len(event["attempts"]),
                json.dumps(event["attempts"]),
                len(event["successes"]),
                json.dumps(event["successes"]),
                len(event["missed_candidates"]),
                json.dumps(event["missed_candidates"]),
            ]
            if supports_round_end:
                columns.insert(3, "round_end_unix")
                values.insert(3, self.metadata.get('round_end_unix', 0))
            placeholders = ", ".join(f"${i}" for i in range(1, len(values) + 1))
            query = f"""
                INSERT INTO proximity_trade_event ({", ".join(columns)})
                VALUES ({placeholders})
                ON CONFLICT (session_date, round_number, round_start_unix, victim_guid, death_time_ms)
                DO NOTHING
            """
            await self.db_adapter.execute(query, tuple(values))

    async def _import_support_summary(self, session_date: str):
        if not self.support_summary:
            return
        if not await self._table_has_column('proximity_support_summary', 'support_samples'):
            self.logger.info("proximity_support_summary table not found; skipping support summary import")
            return
        supports_round_end = await self._table_has_column('proximity_support_summary', 'round_end_unix')

        columns = [
            "session_date", "round_number", "round_start_unix",
            "map_name",
            "support_samples", "total_samples", "support_uptime_pct",
        ]
        values = [
            session_date,
            self.metadata['round_num'],
            self.metadata.get('round_start_unix', 0),
            self.metadata['map_name'],
            self.support_summary["support_samples"],
            self.support_summary["total_samples"],
            self.support_summary["support_uptime_pct"],
        ]
        if supports_round_end:
            columns.insert(3, "round_end_unix")
            values.insert(3, self.metadata.get('round_end_unix', 0))

        placeholders = ", ".join(f"${i}" for i in range(1, len(values) + 1))
        query = f"""
            INSERT INTO proximity_support_summary ({", ".join(columns)})
            VALUES ({placeholders})
            ON CONFLICT (session_date, round_number, round_start_unix)
            DO UPDATE SET
                support_samples = EXCLUDED.support_samples,
                total_samples = EXCLUDED.total_samples,
                support_uptime_pct = EXCLUDED.support_uptime_pct,
                computed_at = CURRENT_TIMESTAMP
        """
        await self.db_adapter.execute(query, tuple(values))
    
    def get_stats(self) -> Dict:
        """Get summary of parsed data"""
        crossfire_count = sum(1 for e in self.engagements if e.is_crossfire)
        kills = sum(1 for e in self.engagements if e.outcome == 'killed')
        escapes = sum(1 for e in self.engagements if e.outcome == 'escaped')

        # Track stats (v4)
        total_samples = sum(t.sample_count for t in self.player_tracks)
        total_distance = sum(t.total_distance for t in self.player_tracks)
        positive_duration_tracks = [t for t in self.player_tracks if t.duration_ms > 0]
        avg_life = (
            sum(t.duration_ms for t in positive_duration_tracks) / len(positive_duration_tracks)
            if positive_duration_tracks else 0
        )

        return {
            'map': self.metadata['map_name'],
            'round': self.metadata['round_num'],
            'total_engagements': len(self.engagements),
            'crossfire_engagements': crossfire_count,
            'kills': kills,
            'escapes': escapes,
            'heatmap_cells': len(self.kill_heatmap),
            # v4 track stats
            'total_tracks': len(self.player_tracks),
            'total_samples': total_samples,
            'total_distance': total_distance,
            'avg_life_ms': avg_life
        }


# Backwards compatibility alias
ProximityParserV3 = ProximityParserV4


# ===== CLI TESTING =====
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    parser = ProximityParserV4(output_dir="gamestats")

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

    # v4 track stats
    if stats['total_tracks'] > 0:
        print(f"\n=== PLAYER TRACKS (v4) ===")
        print(f"Total tracks: {stats['total_tracks']}")
        print(f"Total samples: {stats['total_samples']}")
        print(f"Total distance: {stats['total_distance']:.1f} units")
        print(f"Avg life time: {stats['avg_life_ms']:.0f}ms")

    if parser.engagements:
        print(f"\n=== SAMPLE ENGAGEMENT ===")
        e = parser.engagements[0]
        print(f"ID: {e.id}, Target: {e.target_name}")
        print(f"Outcome: {e.outcome}, Duration: {e.duration}ms")
        print(f"Attackers: {[a.name for a in e.attackers.values()]}")
        print(f"Crossfire: {e.is_crossfire}, Delay: {e.crossfire_delay}ms")
        print(f"Position path: {len(e.position_path)} points")

    if parser.player_tracks:
        print(f"\n=== SAMPLE TRACK ===")
        t = parser.player_tracks[0]
        print(f"Player: {t.name} ({t.player_class})")
        print(f"Team: {t.team}")
        print(f"Lived: {t.duration_ms}ms")
        print(f"Death type: {t.death_type or 'N/A'}")  # v4.1
        print(f"Distance: {t.total_distance:.1f} units")
        print(f"Avg speed: {t.avg_speed:.1f}")
        print(f"Sprint %: {t.sprint_percentage:.1f}%")
        print(f"Time to first move: {t.time_to_first_move_ms}ms")
        print(f"Path samples: {len(t.path)}")
