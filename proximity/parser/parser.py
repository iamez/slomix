"""
PROXIMITY TRACKER v4.2 - FULL PLAYER TRACKING PARSER
Parse engagement-centric data AND full player tracks

Features:
- Parse PLAYER_TRACKS: Full spawn-to-death movement for all players
- Parse combat engagements with position paths
- Detect and track crossfire coordination
- Update player teamplay stats (aggregated forever)
- Update crossfire pair stats
- Update per-map heatmaps
- Parse reaction telemetry (return fire / dodge / support reaction)

v4.2 Output Format:
- PLAYER_TRACKS: guid;name;team;class;spawn_time;death_time;first_move_time;death_type;samples;path
- death_type: killed|selfkill|fallen|world|teamkill|round_end|disconnect|unknown
- path format: time,x,y,z,health,speed,weapon,stance,sprint,event separated by |
- REACTION_METRICS:
  engagement_id;target_guid;target_name;target_team;target_class;outcome;num_attackers;
  return_fire_ms;dodge_reaction_ms;support_reaction_ms;start_time;end_time;duration
"""

import json
import logging
import os
import re
from bisect import bisect_left
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

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
    weapons: dict[int, int] = field(default_factory=dict)


@dataclass
class Engagement:
    id: int
    start_time: int
    end_time: int
    duration: int
    target_guid: str
    target_name: str
    target_team: str
    outcome: str  # 'killed', 'escaped', 'round_end', 'teamkill', 'selfkill', 'fallen', 'world'
    total_damage: int
    killer_guid: str | None
    killer_name: str | None
    num_attackers: int
    is_crossfire: bool
    crossfire_delay: int | None
    crossfire_participants: list[str]
    start_x: float
    start_y: float
    start_z: float
    end_x: float
    end_y: float
    end_z: float
    distance_traveled: float
    position_path: list[dict]
    attackers: dict[str, Attacker]


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
    death_time: int | None
    first_move_time: int | None  # When player first moved after spawn
    death_type: str | None  # v4.1: killed|selfkill|fallen|world|teamkill|round_end|disconnect|unknown
    sample_count: int
    path: list[PathPoint] = field(default_factory=list)

    @property
    def duration_ms(self) -> int:
        """How long player was alive"""
        if self.death_time and self.spawn_time:
            return self.death_time - self.spawn_time
        return 0

    @property
    def time_to_first_move_ms(self) -> int | None:
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

    @property
    def peak_speed(self) -> float:
        """Maximum speed recorded across all samples"""
        if not self.path:
            return 0.0
        return max((p.speed for p in self.path), default=0.0)

    @property
    def stance_standing_sec(self) -> float:
        """Seconds spent standing (stance=0), excluding spawn/death events"""
        return sum(0.2 for p in self.path if p.stance == 0 and p.event == 'sample')

    @property
    def stance_crouching_sec(self) -> float:
        """Seconds spent crouching (stance=1)"""
        return sum(0.2 for p in self.path if p.stance == 1 and p.event == 'sample')

    @property
    def stance_prone_sec(self) -> float:
        """Seconds spent prone (stance=2)"""
        return sum(0.2 for p in self.path if p.stance == 2 and p.event == 'sample')

    @property
    def sprint_sec(self) -> float:
        """Seconds spent sprinting"""
        return sum(0.2 for p in self.path if p.sprint == 1 and p.event == 'sample')

    @property
    def post_spawn_distance(self) -> float:
        """Distance traveled in first 3 seconds after spawn (15 samples at 200ms)"""
        if len(self.path) < 2:
            return 0.0
        # Find spawn sample, then measure distance for next 15 samples
        start_idx = 0
        for i, p in enumerate(self.path):
            if p.event == 'spawn':
                start_idx = i
                break
        end_idx = min(start_idx + 16, len(self.path))  # 15 intervals = 16 points
        total = 0.0
        for i in range(start_idx + 1, end_idx):
            p1, p2 = self.path[i-1], self.path[i]
            dx = p2.x - p1.x
            dy = p2.y - p1.y
            dz = p2.z - p1.z
            total += (dx*dx + dy*dy + dz*dz) ** 0.5
        return total


@dataclass
class ReactionMetric:
    engagement_id: int
    target_guid: str
    target_name: str
    target_team: str
    target_class: str
    outcome: str
    num_attackers: int
    return_fire_ms: int | None
    dodge_reaction_ms: int | None
    support_reaction_ms: int | None
    start_time_ms: int
    end_time_ms: int
    duration_ms: int


@dataclass
class SpawnTimingEvent:
    killer_guid: str
    killer_name: str
    killer_team: str
    victim_guid: str
    victim_name: str
    victim_team: str
    kill_time: int
    enemy_spawn_interval: int
    time_to_next_spawn: int
    spawn_timing_score: float
    killer_reinf: float = 0.0
    victim_reinf: float = 0.0


@dataclass
class TeamCohesionSnapshot:
    sample_time: int
    team: str
    alive_count: int
    centroid_x: float
    centroid_y: float
    dispersion: float
    max_spread: float
    straggler_count: int
    buddy_pair_guids: str | None
    buddy_distance: float | None


@dataclass
class CrossfireOpportunity:
    event_time: int
    target_guid: str
    target_name: str
    target_team: str
    teammate1_guid: str
    teammate2_guid: str
    angular_separation: float
    was_executed: bool
    damage_within_window: int


@dataclass
class TeamPush:
    start_time: int
    end_time: int
    team: str
    avg_speed: float
    direction_x: float
    direction_y: float
    alignment_score: float
    push_quality: float
    participant_count: int
    toward_objective: str


@dataclass
class LuaTradeKill:
    original_kill_time: int
    traded_kill_time: int
    delta_ms: int
    original_victim_guid: str
    original_victim_name: str
    original_killer_guid: str
    original_killer_name: str
    trader_guid: str
    trader_name: str


@dataclass
class ReviveEvent:
    time: int
    medic_guid: str
    medic_name: str
    revived_guid: str
    revived_name: str
    x: float
    y: float
    z: float
    distance_to_enemy: float
    nearest_enemy_guid: str
    under_fire: bool


@dataclass
class WeaponAccuracy:
    player_guid: str
    player_name: str
    team: str
    weapon_id: int
    shots_fired: int
    hits: int
    kills: int
    headshots: int


@dataclass
class FocusFireEvent:
    engagement_id: int
    target_guid: str
    target_name: str
    attacker_count: int
    attacker_guids: str
    total_damage: int
    duration: int
    focus_score: float


@dataclass
class KillOutcome:
    kill_time: int
    victim_guid: str
    victim_name: str
    killer_guid: str
    killer_name: str
    kill_mod: int
    outcome: str
    outcome_time: int
    delta_ms: int
    effective_denied_ms: int
    gibber_guid: str
    gibber_name: str
    reviver_guid: str
    reviver_name: str


@dataclass
class HitRegionEvent:
    time: int
    attacker_guid: str
    attacker_name: str
    victim_guid: str
    victim_name: str
    weapon: int
    region: int       # 0=HEAD, 1=ARMS, 2=BODY, 3=LEGS
    damage: int


@dataclass
class CombatPosition:
    time: int
    event_type: str
    attacker_guid: str
    attacker_name: str
    attacker_team: str
    attacker_class: str
    victim_guid: str
    victim_name: str
    victim_team: str
    victim_class: str
    attacker_x: int
    attacker_y: int
    attacker_z: int
    victim_x: int
    victim_y: int
    victim_z: int
    weapon: int
    mod: int
    killer_health: int = 0
    axis_alive: int = 0
    allies_alive: int = 0


@dataclass
class CarrierEvent:
    carrier_guid: str
    carrier_name: str
    carrier_team: str
    flag_team: str
    pickup_time: int
    drop_time: int
    duration_ms: int
    outcome: str
    carry_distance: float
    beeline_distance: float
    efficiency: float
    path_samples: int
    pickup_x: int
    pickup_y: int
    pickup_z: int
    drop_x: int
    drop_y: int
    drop_z: int
    killer_guid: str
    killer_name: str


@dataclass
class CarrierKill:
    kill_time: int
    carrier_guid: str
    carrier_name: str
    carrier_team: str
    killer_guid: str
    killer_name: str
    killer_team: str
    means_of_death: int
    carrier_distance_at_kill: float
    flag_team: str


@dataclass
class CarrierReturn:
    return_time: int
    returner_guid: str
    returner_name: str
    returner_team: str
    flag_team: str
    original_carrier_guid: str
    drop_time: int
    return_delay_ms: int
    drop_x: int
    drop_y: int
    drop_z: int


@dataclass
class VehicleProgress:
    vehicle_name: str
    vehicle_type: str
    start_x: int
    start_y: int
    start_z: int
    end_x: int
    end_y: int
    end_z: int
    total_distance: float
    max_health: int
    final_health: int
    destroyed_count: int


@dataclass
class EscortCredit:
    player_guid: str
    player_name: str
    player_team: str
    vehicle_name: str
    mounted_time_ms: int
    proximity_time_ms: int
    total_escort_distance: float
    credit_distance: float
    samples: int


@dataclass
class ConstructionEvent:
    event_time: int
    event_type: str
    player_guid: str
    player_name: str
    player_team: str
    track_name: str
    player_x: int
    player_y: int
    player_z: int


@dataclass
class ObjectiveRun:
    engineer_guid: str
    engineer_name: str
    engineer_team: str
    action_type: str       # dynamite_plant, objective_destroyed, construction_complete, dynamite_defuse, approach_killed
    track_name: str
    action_time: int
    approach_time_ms: int
    approach_distance: float
    beeline_distance: float
    path_efficiency: float
    self_kills: int
    team_kills: int
    escort_guids: str      # pipe-separated GUIDs
    enemies_nearby: int
    nearby_teammates: int
    run_type: str           # solo, assisted, unopposed, contested_solo, team_effort, denied
    obj_x: int
    obj_y: int
    obj_z: int
    killer_guid: str
    killer_name: str


class ProximityParserV4:
    """Parser for proximity_tracker v4 output files with full player tracking"""

    def __init__(self, db_adapter=None, output_dir: str = "gamestats", gametimes_dir: str = "local_gametimes"):
        self.db_adapter = db_adapter
        self.output_dir = output_dir
        self.gametimes_dir = gametimes_dir
        self.logger = logging.getLogger(__name__)

        # Parsed data
        self.engagements: list[Engagement] = []
        self.player_tracks: list[PlayerTrack] = []  # v4: Full player tracks
        self.reaction_metrics: list[ReactionMetric] = []
        self.kill_heatmap: list[dict] = []
        self.movement_heatmap: list[dict] = []
        self.trade_events: list[dict] = []
        self.support_summary: dict | None = None
        # v5 teamplay data
        self.spawn_timing_events: list[SpawnTimingEvent] = []
        self.team_cohesion_snapshots: list[TeamCohesionSnapshot] = []
        self.crossfire_opportunities: list[CrossfireOpportunity] = []
        self.team_pushes: list[TeamPush] = []
        self.lua_trade_kills: list[LuaTradeKill] = []
        self.revive_events: list[ReviveEvent] = []
        self.weapon_accuracy: list[WeaponAccuracy] = []
        self.focus_fire_events: list[FocusFireEvent] = []
        self.kill_outcomes: list[KillOutcome] = []
        self.hit_regions: list[HitRegionEvent] = []
        self.combat_positions: list[CombatPosition] = []
        # v6 carrier intelligence
        self.carrier_events: list[CarrierEvent] = []
        self.carrier_kills: list[CarrierKill] = []
        # v6 phases 1.5-4
        self.carrier_returns: list[CarrierReturn] = []
        self.vehicle_progress: list[VehicleProgress] = []
        self.escort_credits: list[EscortCredit] = []
        self.construction_events: list[ConstructionEvent] = []
        self.objective_runs: list[ObjectiveRun] = []
        self.metadata = self._metadata_defaults()
        self._schema_cache: dict[tuple, bool] = {}
        self._round_link_context: dict[str, object | None] = {
            "round_id": None,
            "round_link_source": "unresolved",
            "round_link_reason": "not_resolved",
            "round_linked_at": None,
        }

    @staticmethod
    def _metadata_defaults() -> dict:
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
            'axis_spawn_interval': 0,
            'allies_spawn_interval': 0,
            'tracker_version': 4,
        }

    @staticmethod
    def _extract_round_from_filename(filepath: str) -> int | None:
        match = PROXIMITY_FILENAME_ROUND_RE.search(os.path.basename(filepath))
        if not match:
            return None
        try:
            value = int(match.group(1))
        except ValueError:
            return None
        return value if value > 0 else None

    @staticmethod
    def _extract_timestamp_from_filename(filepath: str) -> int | None:
        """Parse `YYYY-MM-DD-HHMMSS` prefix out of an engagement filename.

        Audit P7 fallback: when the `# round_start_unix=…` header is
        missing or zero, every INSERT site stores `round_start_unix = 0`
        and the natural UNIQUE constraint
        `(session_date, round_number, round_start_unix, …)` silently
        merges multiple same-day rounds into the first one that landed.
        Filename timestamp gives a second-granularity fallback good
        enough to disambiguate rounds on the same day.
        """
        basename = os.path.basename(filepath)
        match = re.match(r"^(\d{4})-(\d{2})-(\d{2})-(\d{2})(\d{2})(\d{2})-", basename)
        if not match:
            return None
        try:
            y, mo, d, h, mi, s = (int(x) for x in match.groups())
            return int(datetime(y, mo, d, h, mi, s).timestamp())
        except (ValueError, OSError):
            return None

    def _extract_round_from_gametime(self, map_name: str, round_end_unix: int) -> int | None:
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
        # Audit P7: fall back to filename timestamp when header lacks
        # round_start_unix. Without this, UNIQUE constraints keyed on
        # (session_date, round_number, round_start_unix, …) silently
        # merge multiple rounds from the same day into the first one.
        if int(self.metadata.get('round_start_unix') or 0) == 0:
            fallback_ts = self._extract_timestamp_from_filename(filepath)
            if fallback_ts:
                self.metadata['round_start_unix'] = fallback_ts
                self.logger.warning(
                    "[ROUND_START_UNIX FALLBACK] file=%s header=0 fallback=%d",
                    os.path.basename(filepath),
                    fallback_ts,
                )

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

    def find_files(self, session_date: str = None) -> list[str]:
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
        self.reaction_metrics = []
        self.kill_heatmap = []
        self.movement_heatmap = []
        self.objective_focus = []
        self.trade_events = []
        self.support_summary = None
        self.spawn_timing_events = []
        self.team_cohesion_snapshots = []
        self.crossfire_opportunities = []
        self.team_pushes = []
        self.lua_trade_kills = []
        self.revive_events = []
        self.weapon_accuracy = []
        self.focus_fire_events = []
        self.kill_outcomes = []
        self.hit_regions = []
        self.combat_positions = []
        self.carrier_events = []
        self.carrier_kills = []
        self.carrier_returns = []
        self.vehicle_progress = []
        self.escort_credits = []
        self.construction_events = []
        self.objective_runs = []

        section = 'header'

        try:
            with open(filepath, encoding='utf-8', errors='replace') as f:
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
                    if line.startswith('# REACTION_METRICS'):
                        section = 'reaction_metrics'
                        continue
                    if line.startswith('# SPAWN_TIMING'):
                        section = 'spawn_timing'
                        continue
                    if line.startswith('# TEAM_COHESION'):
                        section = 'team_cohesion'
                        continue
                    if line.startswith('# CROSSFIRE_OPPORTUNITIES'):
                        section = 'crossfire_opportunities'
                        continue
                    if line.startswith('# TEAM_PUSHES'):
                        section = 'team_pushes'
                        continue
                    if line.startswith('# TRADE_KILLS'):
                        section = 'trade_kills'
                        continue
                    if line.startswith('# REVIVES'):
                        section = 'revives'
                        continue
                    if line.startswith('# WEAPON_ACCURACY'):
                        section = 'weapon_accuracy'
                        continue
                    if line.startswith('# FOCUS_FIRE'):
                        section = 'focus_fire'
                        continue
                    if line.startswith('# KILL_OUTCOME'):
                        section = 'kill_outcome'
                        continue
                    if line.startswith('# HIT_REGIONS'):
                        section = 'hit_regions'
                        continue
                    if line.startswith('# COMBAT_POSITIONS'):
                        section = 'combat_positions'
                        continue
                    if line.startswith('# CARRIER_EVENTS'):
                        section = 'carrier_events'
                        continue
                    if line.startswith('# CARRIER_KILLS'):
                        section = 'carrier_kills'
                        continue
                    if line.startswith('# CARRIER_RETURNS'):
                        section = 'carrier_returns'
                        continue
                    if line.startswith('# VEHICLE_PROGRESS'):
                        section = 'vehicle_progress'
                        continue
                    if line.startswith('# ESCORT_CREDIT'):
                        section = 'escort_credit'
                        continue
                    if line.startswith('# CONSTRUCTION_EVENTS'):
                        section = 'construction_events'
                        continue
                    if line.startswith('# OBJECTIVE_RUNS'):
                        section = 'objective_runs'
                        continue

                    if line.startswith('# axis_spawn_interval='):
                        try:
                            self.metadata['axis_spawn_interval'] = int(line.split('=')[1])
                        except ValueError:
                            self.metadata['axis_spawn_interval'] = 0
                        continue
                    if line.startswith('# allies_spawn_interval='):
                        try:
                            self.metadata['allies_spawn_interval'] = int(line.split('=')[1])
                        except ValueError:
                            self.metadata['allies_spawn_interval'] = 0
                        continue
                    if line.startswith('# PROXIMITY_TRACKER_V5'):
                        self.metadata['tracker_version'] = 5
                        continue
                    if line.startswith('# PROXIMITY_TRACKER_V6'):
                        self.metadata['tracker_version'] = 6
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
                    elif section == 'reaction_metrics':
                        self._parse_reaction_metric_line(line)
                    elif section == 'spawn_timing':
                        self._parse_spawn_timing_line(line)
                    elif section == 'team_cohesion':
                        self._parse_team_cohesion_line(line)
                    elif section == 'crossfire_opportunities':
                        self._parse_crossfire_opportunity_line(line)
                    elif section == 'team_pushes':
                        self._parse_team_push_line(line)
                    elif section == 'trade_kills':
                        self._parse_trade_kill_line(line)
                    elif section == 'revives':
                        self._parse_revive_line(line)
                    elif section == 'weapon_accuracy':
                        self._parse_weapon_accuracy_line(line)
                    elif section == 'focus_fire':
                        self._parse_focus_fire_line(line)
                    elif section == 'kill_outcome':
                        self._parse_kill_outcome_line(line)
                    elif section == 'hit_regions':
                        self._parse_hit_region_line(line)
                    elif section == 'combat_positions':
                        self._parse_combat_position_line(line)
                    elif section == 'carrier_events':
                        self._parse_carrier_event_line(line)
                    elif section == 'carrier_kills':
                        self._parse_carrier_kill_line(line)
                    elif section == 'carrier_returns':
                        self._parse_carrier_return_line(line)
                    elif section == 'vehicle_progress':
                        self._parse_vehicle_progress_line(line)
                    elif section == 'escort_credit':
                        self._parse_escort_credit_line(line)
                    elif section == 'construction_events':
                        self._parse_construction_event_line(line)
                    elif section == 'objective_runs':
                        self._parse_objective_run(line)

            self._normalize_round_metadata(filepath)
            self.logger.info(
                "Parsed %d engagements, %d tracks, %d reaction rows from %s",
                len(self.engagements),
                len(self.player_tracks),
                len(self.reaction_metrics),
                filepath,
            )
            if self.objective_runs:
                self.logger.info(f"Objective runs: {len(self.objective_runs)}")
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

    async def _resolve_round_link_context(self, session_date) -> None:
        """
        Resolve a canonical rounds.id once per imported proximity file.

        Keeps per-source timestamps (R1/R2 are physically distinct rounds) while
        linking all rows to a stable round_id for cross-source joins.
        """
        context: dict[str, object | None] = {
            "round_id": None,
            "round_link_source": "unresolved",
            "round_link_reason": "not_resolved",
            "round_linked_at": datetime.now(timezone.utc).replace(tzinfo=None),
        }
        self._round_link_context = context

        if not self.db_adapter:
            context["round_link_reason"] = "db_unavailable"
            return

        map_name = str(self.metadata.get("map_name") or "").strip()
        try:
            round_number = int(self.metadata.get("round_num") or 0)
        except (TypeError, ValueError):
            round_number = 0

        if not map_name or round_number <= 0:
            context["round_link_reason"] = "invalid_metadata"
            return

        round_end_unix = int(self.metadata.get("round_end_unix") or 0)
        round_start_unix = int(self.metadata.get("round_start_unix") or 0)
        target_dt = None
        if round_end_unix > 0:
            target_dt = datetime.fromtimestamp(round_end_unix)
        elif round_start_unix > 0:
            target_dt = datetime.fromtimestamp(round_start_unix)

        try:
            from bot.core.round_linker import resolve_round_id_with_reason
        except Exception:
            context["round_link_reason"] = "round_linker_import_failed"
            return

        round_date = (
            session_date.isoformat()
            if hasattr(session_date, "isoformat")
            else str(session_date)
        )

        try:
            window_minutes = int(os.getenv("PROXIMITY_ROUND_LINK_WINDOW_MINUTES", "45"))
        except ValueError:
            window_minutes = 45
        window_minutes = max(1, min(window_minutes, 180))

        try:
            round_id, diag = await resolve_round_id_with_reason(
                self.db_adapter,
                map_name,
                round_number,
                target_dt=target_dt,
                round_date=round_date,
                round_time=None,
                window_minutes=window_minutes,
            )
        except Exception as exc:
            context["round_link_reason"] = f"round_linker_error:{type(exc).__name__}"
            return

        reason_code = (diag or {}).get("reason_code")
        context["round_id"] = round_id
        context["round_link_source"] = "round_linker" if round_id else "unresolved"
        context["round_link_reason"] = None if round_id else (reason_code or "unresolved")

        if round_id:
            self.logger.info(
                "[ROUND LINK] map=%s round=%s round_id=%s reason=%s candidates=%s diff_s=%s",
                map_name,
                round_number,
                round_id,
                reason_code,
                (diag or {}).get("candidate_count"),
                (diag or {}).get("best_diff_seconds"),
            )
        else:
            self.logger.warning(
                "[ROUND LINK] unresolved map=%s round=%s reason=%s candidates=%s parsed=%s diff_s=%s",
                map_name,
                round_number,
                reason_code,
                (diag or {}).get("candidate_count"),
                (diag or {}).get("parsed_candidate_count"),
                (diag or {}).get("best_diff_seconds"),
            )

    async def _append_round_link_columns(self, table: str, columns: list[str], values: list[object]) -> None:
        context = self._round_link_context or {}
        if await self._table_has_column(table, "round_id"):
            columns.append("round_id")
            values.append(context.get("round_id"))
        if await self._table_has_column(table, "round_link_source"):
            columns.append("round_link_source")
            values.append(context.get("round_link_source"))
        if await self._table_has_column(table, "round_link_reason"):
            columns.append("round_link_reason")
            values.append(context.get("round_link_reason"))
        if await self._table_has_column(table, "round_linked_at"):
            columns.append("round_linked_at")
            values.append(context.get("round_linked_at"))

    async def _round_link_update_clauses(self, table: str) -> list[str]:
        clauses: list[str] = []
        if await self._table_has_column(table, "round_id"):
            clauses.append(f"round_id = COALESCE(EXCLUDED.round_id, {table}.round_id)")
        if await self._table_has_column(table, "round_link_source"):
            clauses.append(
                f"round_link_source = COALESCE(EXCLUDED.round_link_source, {table}.round_link_source)"
            )
        if await self._table_has_column(table, "round_link_reason"):
            clauses.append(
                f"round_link_reason = COALESCE(EXCLUDED.round_link_reason, {table}.round_link_reason)"
            )
        if await self._table_has_column(table, "round_linked_at"):
            clauses.append(
                f"round_linked_at = COALESCE(EXCLUDED.round_linked_at, {table}.round_linked_at)"
            )
        return clauses

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

    @staticmethod
    def _parse_optional_int(value: str) -> int | None:
        text = str(value or '').strip()
        if not text:
            return None
        try:
            return int(text)
        except ValueError:
            return None

    def _parse_reaction_metric_line(self, line: str):
        """
        Parse REACTION_METRICS line:
        engagement_id;target_guid;target_name;target_team;target_class;outcome;num_attackers;
        return_fire_ms;dodge_reaction_ms;support_reaction_ms;start_time;end_time;duration
        """
        parts = line.split(';')
        if len(parts) < 13:
            self.logger.debug("Skipping invalid reaction metric entry (columns): %s", line[:120])
            return

        try:
            self.reaction_metrics.append(
                ReactionMetric(
                    engagement_id=int(parts[0]),
                    target_guid=parts[1],
                    target_name=parts[2],
                    target_team=parts[3],
                    target_class=parts[4] or "UNKNOWN",
                    outcome=parts[5] or "unknown",
                    num_attackers=int(parts[6]) if parts[6] else 0,
                    return_fire_ms=self._parse_optional_int(parts[7]),
                    dodge_reaction_ms=self._parse_optional_int(parts[8]),
                    support_reaction_ms=self._parse_optional_int(parts[9]),
                    start_time_ms=int(parts[10]) if parts[10] else 0,
                    end_time_ms=int(parts[11]) if parts[11] else 0,
                    duration_ms=int(parts[12]) if parts[12] else 0,
                )
            )
        except ValueError as exc:
            self.logger.debug("Skipping invalid reaction metric entry: %s (%s)", line[:120], exc)

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

        await self._resolve_round_link_context(session_date)

        # Check if this file was already imported (reimport idempotency)
        aggregates_already_applied = await self._check_processed_file(os.path.basename(filepath))

        async def _run_import_steps():
            # Import engagements (ON CONFLICT DO NOTHING — safe for reimport)
            await self._import_engagements(session_date)

            # Import player tracks (v4) (ON CONFLICT DO NOTHING — safe)
            if self.player_tracks:
                await self._import_player_tracks(session_date)

            # Aggregate updates — ONLY on first import to prevent doubling
            if not aggregates_already_applied:
                await self._update_player_stats()
                await self._update_crossfire_pairs()
                await self._import_heatmaps()
            else:
                self.logger.info("Skipping aggregate updates (file already processed)")

            # Import objective focus (optional, ON CONFLICT DO NOTHING — safe)
            if self.objective_focus:
                await self._import_objective_focus(session_date)

            # Import reaction telemetry (optional)
            if self.reaction_metrics:
                await self._import_reaction_metrics(session_date)

            # Compute + import trade events (v1)
            if self.engagements and self.player_tracks:
                self._compute_trade_events()
                await self._import_trade_events(session_date)

            # Compute + import support uptime summary
            if self.player_tracks:
                self.support_summary = self._compute_support_uptime()
                if self.support_summary:
                    await self._import_support_summary(session_date)

            # v5 teamplay imports (all ON CONFLICT DO NOTHING — safe)
            if self.spawn_timing_events:
                await self._import_spawn_timing(session_date)
            if self.team_cohesion_snapshots:
                await self._import_team_cohesion(session_date)
            if self.crossfire_opportunities:
                await self._import_crossfire_opportunities(session_date)
            if self.team_pushes:
                await self._import_team_pushes(session_date)
            if self.lua_trade_kills:
                await self._import_lua_trade_kills(session_date)
            if self.revive_events:
                await self._import_revive_events(session_date)
            if self.weapon_accuracy:
                await self._import_weapon_accuracy(session_date)
            if self.focus_fire_events:
                await self._import_focus_fire_events(session_date)
            if self.kill_outcomes:
                await self._import_kill_outcomes(session_date)
            if self.hit_regions:
                await self._import_hit_regions(session_date)
            if self.combat_positions:
                await self._import_combat_positions(session_date)
            # v6 carrier intelligence
            if self.carrier_events:
                await self._import_carrier_events(session_date)
            if self.carrier_kills:
                await self._import_carrier_kills(session_date)
            # v6 phases 1.5-4
            if self.carrier_returns:
                await self._import_carrier_returns(session_date)
            if self.vehicle_progress:
                await self._import_vehicle_progress(session_date)
            if self.escort_credits:
                await self._import_escort_credits(session_date)
            if self.construction_events:
                await self._import_construction_events(session_date)
            if self.objective_runs:
                await self._import_objective_runs(session_date)

            # Mark file as processed
            await self._mark_file_processed(os.path.basename(filepath))

        try:
            tx_context = getattr(self.db_adapter, "transaction", None)
            if callable(tx_context):
                async with tx_context():
                    await _run_import_steps()
            else:
                self.logger.warning("DB adapter has no transaction() context; import is non-transactional")
                await _run_import_steps()

            self.logger.info(f"Successfully imported {filepath}")
            return True

        except Exception as e:
            self.logger.error(f"Import error: {e}")
            return False

    async def _check_processed_file(self, filename: str) -> bool:
        """Check if file was already imported and aggregates applied."""
        if not await self._table_has_column('proximity_processed_files', 'filename'):
            return False
        try:
            row = await self.db_adapter.fetch_one(
                "SELECT aggregates_applied FROM proximity_processed_files WHERE filename = $1",
                (filename,),
            )
            return bool(row and row[0])
        except Exception:
            return False

    async def _mark_file_processed(self, filename: str) -> None:
        """Record that this file was imported with aggregates applied."""
        if not await self._table_has_column('proximity_processed_files', 'filename'):
            return
        try:
            await self.db_adapter.execute(
                """INSERT INTO proximity_processed_files (filename, aggregates_applied)
                   VALUES ($1, TRUE)
                   ON CONFLICT (filename) DO UPDATE SET aggregates_applied = TRUE""",
                (filename,),
            )
        except Exception as e:
            self.logger.warning(f"Could not mark file processed: {e}")

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
            await self._append_round_link_columns("combat_engagement", columns, values)
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
                "peak_speed", "stance_standing_sec", "stance_crouching_sec",
                "stance_prone_sec", "sprint_sec", "post_spawn_distance",
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
                track.peak_speed,
                track.stance_standing_sec,
                track.stance_crouching_sec,
                track.stance_prone_sec,
                track.sprint_sec,
                track.post_spawn_distance,
            ]
            if supports_round_end:
                columns.insert(3, "round_end_unix")
                values.insert(3, self.metadata.get('round_end_unix', 0))
            await self._append_round_link_columns("player_track", columns, values)
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
                    avg_crossfire_delay_ms = CASE
                        WHEN COALESCE(player_teamplay_stats.crossfire_participations, 0) + COALESCE(EXCLUDED.crossfire_participations, 0) > 0
                        THEN (
                            COALESCE(
                                player_teamplay_stats.avg_crossfire_delay_ms
                                * NULLIF(player_teamplay_stats.crossfire_participations, 0),
                                0
                            )
                            + COALESCE(
                                EXCLUDED.avg_crossfire_delay_ms
                                * NULLIF(EXCLUDED.crossfire_participations, 0),
                                0
                            )
                        ) / NULLIF(
                            COALESCE(player_teamplay_stats.crossfire_participations, 0)
                            + COALESCE(EXCLUDED.crossfire_participations, 0),
                            0
                        )
                        ELSE COALESCE(EXCLUDED.avg_crossfire_delay_ms, player_teamplay_stats.avg_crossfire_delay_ms)
                    END,
                    solo_kills = player_teamplay_stats.solo_kills + EXCLUDED.solo_kills,
                    solo_engagements = player_teamplay_stats.solo_engagements + EXCLUDED.solo_engagements,
                    times_targeted = player_teamplay_stats.times_targeted + EXCLUDED.times_targeted,
                    times_focused = player_teamplay_stats.times_focused + EXCLUDED.times_focused,
                    focus_escapes = player_teamplay_stats.focus_escapes + EXCLUDED.focus_escapes,
                    focus_deaths = player_teamplay_stats.focus_deaths + EXCLUDED.focus_deaths,
                    solo_escapes = player_teamplay_stats.solo_escapes + EXCLUDED.solo_escapes,
                    solo_deaths = player_teamplay_stats.solo_deaths + EXCLUDED.solo_deaths,
                    avg_escape_distance = CASE
                        WHEN COALESCE(player_teamplay_stats.times_targeted, 0) + COALESCE(EXCLUDED.times_targeted, 0) > 0
                        THEN (
                            COALESCE(
                                player_teamplay_stats.avg_escape_distance
                                * NULLIF(player_teamplay_stats.times_targeted, 0),
                                0
                            )
                            + COALESCE(
                                EXCLUDED.avg_escape_distance
                                * NULLIF(EXCLUDED.times_targeted, 0),
                                0
                            )
                        ) / NULLIF(
                            COALESCE(player_teamplay_stats.times_targeted, 0)
                            + COALESCE(EXCLUDED.times_targeted, 0),
                            0
                        )
                        ELSE COALESCE(EXCLUDED.avg_escape_distance, player_teamplay_stats.avg_escape_distance)
                    END,
                    avg_engagement_duration_ms = CASE
                        WHEN COALESCE(player_teamplay_stats.times_targeted, 0) + COALESCE(EXCLUDED.times_targeted, 0) > 0
                        THEN (
                            COALESCE(
                                player_teamplay_stats.avg_engagement_duration_ms
                                * NULLIF(player_teamplay_stats.times_targeted, 0),
                                0
                            )
                            + COALESCE(
                                EXCLUDED.avg_engagement_duration_ms
                                * NULLIF(EXCLUDED.times_targeted, 0),
                                0
                            )
                        ) / NULLIF(
                            COALESCE(player_teamplay_stats.times_targeted, 0)
                            + COALESCE(EXCLUDED.times_targeted, 0),
                            0
                        )
                        ELSE COALESCE(
                            EXCLUDED.avg_engagement_duration_ms,
                            player_teamplay_stats.avg_engagement_duration_ms
                        )
                    END,
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

    def _new_player_stats(self, name: str) -> dict:
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
                    avg_delay_ms = CASE
                        WHEN COALESCE(crossfire_pairs.crossfire_count, 0) + COALESCE(EXCLUDED.crossfire_count, 0) > 0
                        THEN (
                            COALESCE(
                                crossfire_pairs.avg_delay_ms
                                * NULLIF(crossfire_pairs.crossfire_count, 0),
                                0
                            )
                            + COALESCE(
                                EXCLUDED.avg_delay_ms
                                * NULLIF(EXCLUDED.crossfire_count, 0),
                                0
                            )
                        ) / NULLIF(
                            COALESCE(crossfire_pairs.crossfire_count, 0)
                            + COALESCE(EXCLUDED.crossfire_count, 0),
                            0
                        )
                        ELSE COALESCE(EXCLUDED.avg_delay_ms, crossfire_pairs.avg_delay_ms)
                    END,
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

    def _parse_spawn_timing_line(self, line: str):
        try:
            parts = line.split(';')
            if len(parts) < 10:
                return
            self.spawn_timing_events.append(SpawnTimingEvent(
                killer_guid=parts[0],
                killer_name=parts[1],
                killer_team=parts[2],
                victim_guid=parts[3],
                victim_name=parts[4],
                victim_team=parts[5],
                kill_time=int(parts[6]),
                enemy_spawn_interval=int(parts[7]),
                time_to_next_spawn=int(parts[8]),
                spawn_timing_score=float(parts[9]),
                killer_reinf=float(parts[10]) if len(parts) > 10 else 0.0,
                victim_reinf=float(parts[11]) if len(parts) > 11 else 0.0,
            ))
        except (ValueError, IndexError) as e:
            self.logger.debug(f"Skip spawn_timing line: {e}")

    def _parse_team_cohesion_line(self, line: str):
        try:
            parts = line.split(';')
            if len(parts) < 10:
                return
            self.team_cohesion_snapshots.append(TeamCohesionSnapshot(
                sample_time=int(parts[0]),
                team=parts[1],
                alive_count=int(parts[2]),
                centroid_x=float(parts[3]),
                centroid_y=float(parts[4]),
                dispersion=float(parts[5]),
                max_spread=float(parts[6]),
                straggler_count=int(parts[7]),
                buddy_pair_guids=parts[8] if parts[8] else None,
                buddy_distance=float(parts[9]) if parts[9] else None,
            ))
        except (ValueError, IndexError) as e:
            self.logger.debug(f"Skip team_cohesion line: {e}")

    def _parse_crossfire_opportunity_line(self, line: str):
        try:
            parts = line.split(';')
            if len(parts) < 9:
                return
            self.crossfire_opportunities.append(CrossfireOpportunity(
                event_time=int(parts[0]),
                target_guid=parts[1],
                target_name=parts[2],
                target_team=parts[3],
                teammate1_guid=parts[4],
                teammate2_guid=parts[5],
                angular_separation=float(parts[6]),
                was_executed=parts[7] == '1',
                damage_within_window=int(parts[8]),
            ))
        except (ValueError, IndexError) as e:
            self.logger.debug(f"Skip crossfire_opportunity line: {e}")

    def _parse_team_push_line(self, line: str):
        try:
            parts = line.split(';')
            if len(parts) < 10:
                return
            self.team_pushes.append(TeamPush(
                start_time=int(parts[0]),
                end_time=int(parts[1]),
                team=parts[2],
                avg_speed=float(parts[3]),
                direction_x=float(parts[4]),
                direction_y=float(parts[5]),
                alignment_score=float(parts[6]),
                push_quality=float(parts[7]),
                participant_count=int(parts[8]),
                toward_objective=parts[9],
            ))
        except (ValueError, IndexError) as e:
            self.logger.debug(f"Skip team_push line: {e}")

    def _parse_trade_kill_line(self, line: str):
        try:
            parts = line.split(';')
            if len(parts) < 9:
                return
            self.lua_trade_kills.append(LuaTradeKill(
                original_kill_time=int(parts[0]),
                traded_kill_time=int(parts[1]),
                delta_ms=int(parts[2]),
                original_victim_guid=parts[3],
                original_victim_name=parts[4],
                original_killer_guid=parts[5],
                original_killer_name=parts[6],
                trader_guid=parts[7],
                trader_name=parts[8],
            ))
        except (ValueError, IndexError) as e:
            self.logger.debug(f"Skip trade_kill line: {e}")

    def _parse_revive_line(self, line: str):
        try:
            parts = line.split(';')
            if len(parts) < 11:
                return
            self.revive_events.append(ReviveEvent(
                time=int(parts[0]),
                medic_guid=parts[1],
                medic_name=parts[2],
                revived_guid=parts[3],
                revived_name=parts[4],
                x=float(parts[5]),
                y=float(parts[6]),
                z=float(parts[7]),
                distance_to_enemy=float(parts[8]),
                nearest_enemy_guid=parts[9],
                under_fire=parts[10] == '1',
            ))
        except (ValueError, IndexError) as e:
            self.logger.debug(f"Skip revive line: {e}")

    def _parse_weapon_accuracy_line(self, line: str):
        try:
            parts = line.split(';')
            if len(parts) < 8:
                return
            self.weapon_accuracy.append(WeaponAccuracy(
                player_guid=parts[0],
                player_name=parts[1],
                team=parts[2],
                weapon_id=int(parts[3]),
                shots_fired=int(parts[4]),
                hits=int(parts[5]),
                kills=int(parts[6]),
                headshots=int(parts[7]),
            ))
        except (ValueError, IndexError) as e:
            self.logger.debug(f"Skip weapon_accuracy line: {e}")

    def _parse_focus_fire_line(self, line: str):
        try:
            parts = line.split(';')
            if len(parts) < 8:
                return
            self.focus_fire_events.append(FocusFireEvent(
                engagement_id=int(parts[0]),
                target_guid=parts[1],
                target_name=parts[2],
                attacker_count=int(parts[3]),
                attacker_guids=parts[4],
                total_damage=int(parts[5]),
                duration=int(parts[6]),
                focus_score=float(parts[7]),
            ))
        except (ValueError, IndexError) as e:
            self.logger.debug(f"Skip focus_fire line: {e}")

    def _parse_kill_outcome_line(self, line: str):
        try:
            parts = line.split(';')
            if len(parts) < 14:
                return
            self.kill_outcomes.append(KillOutcome(
                kill_time=int(parts[0]),
                victim_guid=parts[1],
                victim_name=parts[2],
                killer_guid=parts[3],
                killer_name=parts[4],
                kill_mod=int(parts[5]),
                outcome=parts[6],
                outcome_time=int(parts[7]),
                delta_ms=int(parts[8]),
                effective_denied_ms=int(parts[9]),
                gibber_guid=parts[10],
                gibber_name=parts[11],
                reviver_guid=parts[12],
                reviver_name=parts[13],
            ))
        except (ValueError, IndexError) as e:
            self.logger.debug(f"Skip kill_outcome line: {e}")

    async def _import_kill_outcomes(self, session_date):
        """Import kill outcome events to proximity_kill_outcome table"""
        if not await self._table_has_column('proximity_kill_outcome', 'victim_guid'):
            return
        supports_round_end = await self._table_has_column('proximity_kill_outcome', 'round_end_unix')
        for ko in self.kill_outcomes:
            columns = [
                "session_date", "round_number", "round_start_unix",
                "map_name", "kill_time",
                "victim_guid", "victim_name",
                "killer_guid", "killer_name", "kill_mod",
                "outcome", "outcome_time", "delta_ms", "effective_denied_ms",
                "gibber_guid", "gibber_name",
                "reviver_guid", "reviver_name",
            ]
            values = [
                session_date,
                self.metadata['round_num'],
                self.metadata.get('round_start_unix', 0),
                self.metadata['map_name'],
                ko.kill_time,
                ko.victim_guid, ko.victim_name,
                ko.killer_guid, ko.killer_name, ko.kill_mod,
                ko.outcome, ko.outcome_time, ko.delta_ms, ko.effective_denied_ms,
                ko.gibber_guid, ko.gibber_name,
                ko.reviver_guid, ko.reviver_name,
            ]
            if supports_round_end:
                columns.insert(3, "round_end_unix")
                values.insert(3, self.metadata.get('round_end_unix', 0))
            await self._append_round_link_columns("proximity_kill_outcome", columns, values)
            placeholders = ", ".join(f"${i}" for i in range(1, len(values) + 1))
            query = f"""
                INSERT INTO proximity_kill_outcome ({", ".join(columns)})
                VALUES ({placeholders})
                ON CONFLICT (session_date, round_number, round_start_unix, kill_time, victim_guid)
                DO NOTHING
            """
            await self.db_adapter.execute(query, tuple(values))

    def _parse_hit_region_line(self, line: str):
        try:
            parts = line.split(';')
            if len(parts) < 8:
                return
            self.hit_regions.append(HitRegionEvent(
                time=int(parts[0]),
                attacker_guid=parts[1],
                attacker_name=parts[2],
                victim_guid=parts[3],
                victim_name=parts[4],
                weapon=int(parts[5]),
                region=int(parts[6]),
                damage=int(parts[7]),
            ))
        except (ValueError, IndexError) as e:
            self.logger.debug(f"Skip hit_region line: {e}")

    async def _import_hit_regions(self, session_date):
        """Import hit region events to proximity_hit_region table"""
        if not await self._table_has_column('proximity_hit_region', 'attacker_guid'):
            return
        supports_round_end = await self._table_has_column('proximity_hit_region', 'round_end_unix')
        for hr in self.hit_regions:
            columns = [
                "session_date", "round_number", "round_start_unix",
                "map_name", "event_time",
                "attacker_guid", "attacker_name",
                "victim_guid", "victim_name",
                "weapon_id", "hit_region", "damage",
            ]
            values = [
                session_date,
                self.metadata['round_num'],
                self.metadata.get('round_start_unix', 0),
                self.metadata['map_name'],
                hr.time,
                hr.attacker_guid, hr.attacker_name,
                hr.victim_guid, hr.victim_name,
                hr.weapon, hr.region, hr.damage,
            ]
            if supports_round_end:
                columns.insert(3, "round_end_unix")
                values.insert(3, self.metadata.get('round_end_unix', 0))
            await self._append_round_link_columns("proximity_hit_region", columns, values)
            placeholders = ", ".join(f"${i}" for i in range(1, len(values) + 1))
            # Natural key match migration 042 — prevents 8 % dup pollution
            # discovered in the proximity audit 2026-04-21. The previous
            # INSERT had no ON CONFLICT and relied on PK (serial id), so
            # every reimport silently accumulated duplicates.
            query = f"""
                INSERT INTO proximity_hit_region ({", ".join(columns)})
                VALUES ({placeholders})
                ON CONFLICT (session_date, round_number, round_start_unix,
                             attacker_guid, victim_guid, event_time, weapon_id)
                DO NOTHING
            """
            await self.db_adapter.execute(query, tuple(values))

    def _parse_combat_position_line(self, line: str):
        try:
            parts = line.split(';')
            if len(parts) < 18:
                return
            self.combat_positions.append(CombatPosition(
                time=int(parts[0]),
                event_type=parts[1],
                attacker_guid=parts[2],
                attacker_name=parts[3],
                attacker_team=parts[4],
                attacker_class=parts[5],
                victim_guid=parts[6],
                victim_name=parts[7],
                victim_team=parts[8],
                victim_class=parts[9],
                attacker_x=int(parts[10]),
                attacker_y=int(parts[11]),
                attacker_z=int(parts[12]),
                victim_x=int(parts[13]),
                victim_y=int(parts[14]),
                victim_z=int(parts[15]),
                weapon=int(parts[16]),
                mod=int(parts[17]),
                killer_health=int(parts[18]) if len(parts) > 18 else 0,
                axis_alive=int(parts[19]) if len(parts) > 19 else 0,
                allies_alive=int(parts[20]) if len(parts) > 20 else 0,
            ))
        except (ValueError, IndexError) as e:
            self.logger.debug(f"Skip combat_position line: {e}")

    def _parse_carrier_event_line(self, line: str):
        try:
            parts = line.split(';')
            if len(parts) < 20:
                return
            self.carrier_events.append(CarrierEvent(
                carrier_guid=parts[0],
                carrier_name=parts[1],
                carrier_team=parts[2],
                flag_team=parts[3],
                pickup_time=int(parts[4]),
                drop_time=int(parts[5]),
                duration_ms=int(parts[6]),
                outcome=parts[7],
                carry_distance=float(parts[8]),
                beeline_distance=float(parts[9]),
                efficiency=float(parts[10]),
                path_samples=int(parts[11]),
                pickup_x=int(parts[12]),
                pickup_y=int(parts[13]),
                pickup_z=int(parts[14]),
                drop_x=int(parts[15]),
                drop_y=int(parts[16]),
                drop_z=int(parts[17]),
                killer_guid=parts[18],
                killer_name=parts[19].strip(),
            ))
        except (ValueError, IndexError) as e:
            self.logger.debug(f"Skip carrier_event line: {e}")

    def _parse_carrier_kill_line(self, line: str):
        try:
            parts = line.split(';')
            if len(parts) < 10:
                return
            self.carrier_kills.append(CarrierKill(
                kill_time=int(parts[0]),
                carrier_guid=parts[1],
                carrier_name=parts[2],
                carrier_team=parts[3],
                killer_guid=parts[4],
                killer_name=parts[5],
                killer_team=parts[6],
                means_of_death=int(parts[7]),
                carrier_distance_at_kill=float(parts[8]),
                flag_team=parts[9].strip(),
            ))
        except (ValueError, IndexError) as e:
            self.logger.debug(f"Skip carrier_kill line: {e}")

    def _parse_carrier_return_line(self, line: str):
        try:
            parts = line.split(';')
            if len(parts) < 11:
                return
            self.carrier_returns.append(CarrierReturn(
                return_time=int(parts[0]),
                returner_guid=parts[1],
                returner_name=parts[2],
                returner_team=parts[3],
                flag_team=parts[4],
                original_carrier_guid=parts[5],
                drop_time=int(parts[6]),
                return_delay_ms=int(parts[7]),
                drop_x=int(parts[8]),
                drop_y=int(parts[9]),
                drop_z=int(parts[10].strip()),
            ))
        except (ValueError, IndexError) as e:
            self.logger.debug(f"Skip carrier_return line: {e}")

    def _parse_vehicle_progress_line(self, line: str):
        try:
            parts = line.split(';')
            if len(parts) < 12:
                return
            self.vehicle_progress.append(VehicleProgress(
                vehicle_name=parts[0],
                vehicle_type=parts[1],
                start_x=int(parts[2]),
                start_y=int(parts[3]),
                start_z=int(parts[4]),
                end_x=int(parts[5]),
                end_y=int(parts[6]),
                end_z=int(parts[7]),
                total_distance=float(parts[8]),
                max_health=int(parts[9]),
                final_health=int(parts[10]),
                destroyed_count=int(parts[11].strip()),
            ))
        except (ValueError, IndexError) as e:
            self.logger.debug(f"Skip vehicle_progress line: {e}")

    def _parse_escort_credit_line(self, line: str):
        try:
            parts = line.split(';')
            if len(parts) < 9:
                return
            self.escort_credits.append(EscortCredit(
                player_guid=parts[0],
                player_name=parts[1],
                player_team=parts[2],
                vehicle_name=parts[3],
                mounted_time_ms=int(parts[4]),
                proximity_time_ms=int(parts[5]),
                total_escort_distance=float(parts[6]),
                credit_distance=float(parts[7]),
                samples=int(parts[8].strip()),
            ))
        except (ValueError, IndexError) as e:
            self.logger.debug(f"Skip escort_credit line: {e}")

    def _parse_construction_event_line(self, line: str):
        try:
            parts = line.split(';')
            if len(parts) < 9:
                return
            self.construction_events.append(ConstructionEvent(
                event_time=int(parts[0]),
                event_type=parts[1],
                player_guid=parts[2],
                player_name=parts[3],
                player_team=parts[4],
                track_name=parts[5],
                player_x=int(parts[6]),
                player_y=int(parts[7]),
                player_z=int(parts[8].strip()),
            ))
        except (ValueError, IndexError) as e:
            self.logger.debug(f"Skip construction_event line: {e}")

    def _parse_objective_run(self, line: str) -> None:
        """Parse an OBJECTIVE_RUNS line (21 semicolon-separated fields)."""
        if line.startswith("#") or not line.strip():
            return
        parts = line.strip().split(";")
        if len(parts) < 21:
            self.logger.warning(f"OBJECTIVE_RUN line has {len(parts)} parts, expected 21: {line[:80]}")
            return
        try:
            run = ObjectiveRun(
                engineer_guid=parts[0],
                engineer_name=parts[1],
                engineer_team=parts[2],
                action_type=parts[3],
                track_name=parts[4],
                action_time=int(parts[5]),
                approach_time_ms=int(parts[6]),
                approach_distance=float(parts[7]),
                beeline_distance=float(parts[8]),
                path_efficiency=float(parts[9]),
                self_kills=int(parts[10]),
                team_kills=int(parts[11]),
                escort_guids=parts[12],
                enemies_nearby=int(parts[13]),
                nearby_teammates=int(parts[14]),
                run_type=parts[15],
                obj_x=int(float(parts[16])),
                obj_y=int(float(parts[17])),
                obj_z=int(float(parts[18])),
                killer_guid=parts[19],
                killer_name=parts[20],
            )
            self.objective_runs.append(run)
        except (ValueError, IndexError) as e:
            self.logger.warning(f"Failed to parse OBJECTIVE_RUN: {e}")

    async def _import_combat_positions(self, session_date):
        """Import combat position events to proximity_combat_position table"""
        if not await self._table_has_column('proximity_combat_position', 'attacker_guid'):
            return
        supports_round_end = await self._table_has_column('proximity_combat_position', 'round_end_unix')
        for cp in self.combat_positions:
            columns = [
                "session_date", "round_number", "round_start_unix",
                "map_name", "event_time", "event_type",
                "attacker_guid", "attacker_name", "attacker_team", "attacker_class",
                "victim_guid", "victim_name", "victim_team", "victim_class",
                "attacker_x", "attacker_y", "attacker_z",
                "victim_x", "victim_y", "victim_z",
                "weapon_id", "means_of_death",
            ]
            values = [
                session_date,
                self.metadata['round_num'],
                self.metadata.get('round_start_unix', 0),
                self.metadata['map_name'],
                cp.time, cp.event_type,
                cp.attacker_guid, cp.attacker_name, cp.attacker_team, cp.attacker_class,
                cp.victim_guid, cp.victim_name, cp.victim_team, cp.victim_class,
                cp.attacker_x, cp.attacker_y, cp.attacker_z,
                cp.victim_x, cp.victim_y, cp.victim_z,
                cp.weapon, cp.mod,
            ]
            # Oksii adoption fields (optional — backward compatible)
            if await self._table_has_column('proximity_combat_position', 'killer_health'):
                columns.extend(["killer_health", "axis_alive", "allies_alive"])
                values.extend([cp.killer_health, cp.axis_alive, cp.allies_alive])
            if supports_round_end:
                columns.insert(3, "round_end_unix")
                values.insert(3, self.metadata.get('round_end_unix', 0))
            await self._append_round_link_columns("proximity_combat_position", columns, values)
            placeholders = ", ".join(f"${i}" for i in range(1, len(values) + 1))
            query = f"""
                INSERT INTO proximity_combat_position ({", ".join(columns)})
                VALUES ({placeholders})
                ON CONFLICT (session_date, round_number, round_start_unix, event_time, attacker_guid, victim_guid)
                DO NOTHING
            """
            await self.db_adapter.execute(query, tuple(values))

    async def _import_carrier_events(self, session_date):
        """Import v6 carrier event data"""
        if not await self._table_has_column('proximity_carrier_event', 'carrier_guid'):
            return
        supports_round_end = await self._table_has_column('proximity_carrier_event', 'round_end_unix')
        for evt in self.carrier_events:
            columns = [
                "session_date", "round_number", "round_start_unix",
                "map_name",
                "carrier_guid", "carrier_name", "carrier_team", "flag_team",
                "pickup_time", "drop_time", "duration_ms", "outcome",
                "carry_distance", "beeline_distance", "efficiency", "path_samples",
                "pickup_x", "pickup_y", "pickup_z",
                "drop_x", "drop_y", "drop_z",
                "killer_guid", "killer_name",
            ]
            values = [
                session_date,
                self.metadata['round_num'],
                self.metadata.get('round_start_unix', 0),
                self.metadata['map_name'],
                evt.carrier_guid, evt.carrier_name, evt.carrier_team, evt.flag_team,
                evt.pickup_time, evt.drop_time, evt.duration_ms, evt.outcome,
                evt.carry_distance, evt.beeline_distance, evt.efficiency, evt.path_samples,
                evt.pickup_x, evt.pickup_y, evt.pickup_z,
                evt.drop_x, evt.drop_y, evt.drop_z,
                evt.killer_guid, evt.killer_name,
            ]
            if supports_round_end:
                columns.insert(3, "round_end_unix")
                values.insert(3, self.metadata.get('round_end_unix', 0))
            await self._append_round_link_columns("proximity_carrier_event", columns, values)
            placeholders = ", ".join(f"${i}" for i in range(1, len(values) + 1))
            query = f"""
                INSERT INTO proximity_carrier_event ({", ".join(columns)})
                VALUES ({placeholders})
                ON CONFLICT (session_date, round_number, round_start_unix, carrier_guid, pickup_time)
                DO NOTHING
            """
            await self.db_adapter.execute(query, tuple(values))

    async def _import_carrier_kills(self, session_date):
        """Import v6 carrier kill data"""
        if not await self._table_has_column('proximity_carrier_kill', 'killer_guid'):
            return
        supports_round_end = await self._table_has_column('proximity_carrier_kill', 'round_end_unix')
        for ck in self.carrier_kills:
            columns = [
                "session_date", "round_number", "round_start_unix",
                "map_name",
                "kill_time", "carrier_guid", "carrier_name", "carrier_team",
                "killer_guid", "killer_name", "killer_team",
                "means_of_death", "carrier_distance_at_kill", "flag_team",
            ]
            values = [
                session_date,
                self.metadata['round_num'],
                self.metadata.get('round_start_unix', 0),
                self.metadata['map_name'],
                ck.kill_time, ck.carrier_guid, ck.carrier_name, ck.carrier_team,
                ck.killer_guid, ck.killer_name, ck.killer_team,
                ck.means_of_death, ck.carrier_distance_at_kill, ck.flag_team,
            ]
            if supports_round_end:
                columns.insert(3, "round_end_unix")
                values.insert(3, self.metadata.get('round_end_unix', 0))
            await self._append_round_link_columns("proximity_carrier_kill", columns, values)
            placeholders = ", ".join(f"${i}" for i in range(1, len(values) + 1))
            query = f"""
                INSERT INTO proximity_carrier_kill ({", ".join(columns)})
                VALUES ({placeholders})
                ON CONFLICT (session_date, round_number, round_start_unix, carrier_guid, kill_time)
                DO NOTHING
            """
            await self.db_adapter.execute(query, tuple(values))

    async def _import_carrier_returns(self, session_date):
        """Import v6 carrier return data"""
        if not await self._table_has_column('proximity_carrier_return', 'returner_guid'):
            return
        supports_round_end = await self._table_has_column('proximity_carrier_return', 'round_end_unix')
        for cr in self.carrier_returns:
            columns = [
                "session_date", "round_number", "round_start_unix",
                "map_name",
                "return_time", "returner_guid", "returner_name", "returner_team",
                "flag_team", "original_carrier_guid", "drop_time", "return_delay_ms",
                "drop_x", "drop_y", "drop_z",
            ]
            values = [
                session_date,
                self.metadata['round_num'],
                self.metadata.get('round_start_unix', 0),
                self.metadata['map_name'],
                cr.return_time, cr.returner_guid, cr.returner_name, cr.returner_team,
                cr.flag_team, cr.original_carrier_guid, cr.drop_time, cr.return_delay_ms,
                cr.drop_x, cr.drop_y, cr.drop_z,
            ]
            if supports_round_end:
                columns.insert(3, "round_end_unix")
                values.insert(3, self.metadata.get('round_end_unix', 0))
            await self._append_round_link_columns("proximity_carrier_return", columns, values)
            placeholders = ", ".join(f"${i}" for i in range(1, len(values) + 1))
            query = f"""
                INSERT INTO proximity_carrier_return ({", ".join(columns)})
                VALUES ({placeholders})
                ON CONFLICT (session_date, round_number, round_start_unix, returner_guid, return_time)
                DO NOTHING
            """
            await self.db_adapter.execute(query, tuple(values))

    async def _import_vehicle_progress(self, session_date):
        """Import v6 vehicle progress data"""
        if not await self._table_has_column('proximity_vehicle_progress', 'vehicle_name'):
            return
        supports_round_end = await self._table_has_column('proximity_vehicle_progress', 'round_end_unix')
        for vp in self.vehicle_progress:
            columns = [
                "session_date", "round_number", "round_start_unix",
                "map_name",
                "vehicle_name", "vehicle_type",
                "start_x", "start_y", "start_z",
                "end_x", "end_y", "end_z",
                "total_distance", "max_health", "final_health", "destroyed_count",
            ]
            values = [
                session_date,
                self.metadata['round_num'],
                self.metadata.get('round_start_unix', 0),
                self.metadata['map_name'],
                vp.vehicle_name, vp.vehicle_type,
                vp.start_x, vp.start_y, vp.start_z,
                vp.end_x, vp.end_y, vp.end_z,
                vp.total_distance, vp.max_health, vp.final_health, vp.destroyed_count,
            ]
            if supports_round_end:
                columns.insert(3, "round_end_unix")
                values.insert(3, self.metadata.get('round_end_unix', 0))
            await self._append_round_link_columns("proximity_vehicle_progress", columns, values)
            placeholders = ", ".join(f"${i}" for i in range(1, len(values) + 1))
            query = f"""
                INSERT INTO proximity_vehicle_progress ({", ".join(columns)})
                VALUES ({placeholders})
                ON CONFLICT (session_date, round_number, round_start_unix, vehicle_name)
                DO NOTHING
            """
            await self.db_adapter.execute(query, tuple(values))

    async def _import_escort_credits(self, session_date):
        """Import v6 escort credit data"""
        if not await self._table_has_column('proximity_escort_credit', 'player_guid'):
            return
        supports_round_end = await self._table_has_column('proximity_escort_credit', 'round_end_unix')
        for ec in self.escort_credits:
            columns = [
                "session_date", "round_number", "round_start_unix",
                "map_name",
                "player_guid", "player_name", "player_team", "vehicle_name",
                "mounted_time_ms", "proximity_time_ms",
                "total_escort_distance", "credit_distance", "samples",
            ]
            values = [
                session_date,
                self.metadata['round_num'],
                self.metadata.get('round_start_unix', 0),
                self.metadata['map_name'],
                ec.player_guid, ec.player_name, ec.player_team, ec.vehicle_name,
                ec.mounted_time_ms, ec.proximity_time_ms,
                ec.total_escort_distance, ec.credit_distance, ec.samples,
            ]
            if supports_round_end:
                columns.insert(3, "round_end_unix")
                values.insert(3, self.metadata.get('round_end_unix', 0))
            await self._append_round_link_columns("proximity_escort_credit", columns, values)
            placeholders = ", ".join(f"${i}" for i in range(1, len(values) + 1))
            query = f"""
                INSERT INTO proximity_escort_credit ({", ".join(columns)})
                VALUES ({placeholders})
                ON CONFLICT (session_date, round_number, round_start_unix, player_guid, vehicle_name)
                DO NOTHING
            """
            await self.db_adapter.execute(query, tuple(values))

    async def _import_construction_events(self, session_date):
        """Import v6 construction event data"""
        if not await self._table_has_column('proximity_construction_event', 'player_guid'):
            return
        supports_round_end = await self._table_has_column('proximity_construction_event', 'round_end_unix')
        for ce in self.construction_events:
            columns = [
                "session_date", "round_number", "round_start_unix",
                "map_name",
                "event_time", "event_type",
                "player_guid", "player_name", "player_team",
                "track_name", "player_x", "player_y", "player_z",
            ]
            values = [
                session_date,
                self.metadata['round_num'],
                self.metadata.get('round_start_unix', 0),
                self.metadata['map_name'],
                ce.event_time, ce.event_type,
                ce.player_guid, ce.player_name, ce.player_team,
                ce.track_name, ce.player_x, ce.player_y, ce.player_z,
            ]
            if supports_round_end:
                columns.insert(3, "round_end_unix")
                values.insert(3, self.metadata.get('round_end_unix', 0))
            await self._append_round_link_columns("proximity_construction_event", columns, values)
            placeholders = ", ".join(f"${i}" for i in range(1, len(values) + 1))
            query = f"""
                INSERT INTO proximity_construction_event ({", ".join(columns)})
                VALUES ({placeholders})
                ON CONFLICT (session_date, round_number, round_start_unix, player_guid, event_time, event_type)
                DO NOTHING
            """
            await self.db_adapter.execute(query, tuple(values))

    async def _import_objective_runs(self, session_date):
        """Import objective run records into proximity_objective_run."""
        if not await self._table_has_column('proximity_objective_run', 'engineer_guid'):
            return
        supports_round_end = await self._table_has_column('proximity_objective_run', 'round_end_unix')
        for run in self.objective_runs:
            columns = [
                "session_date", "round_number", "round_start_unix",
                "map_name",
                "engineer_guid", "engineer_name", "engineer_team",
                "action_type", "track_name", "action_time",
                "approach_time_ms", "approach_distance", "beeline_distance", "path_efficiency",
                "self_kills", "team_kills", "escort_guids", "enemies_nearby", "nearby_teammates",
                "run_type", "obj_x", "obj_y", "obj_z",
                "killer_guid", "killer_name",
            ]
            values = [
                session_date,
                self.metadata['round_num'],
                self.metadata.get('round_start_unix', 0),
                self.metadata['map_name'],
                run.engineer_guid, run.engineer_name, run.engineer_team,
                run.action_type, run.track_name, run.action_time,
                run.approach_time_ms, run.approach_distance, run.beeline_distance, run.path_efficiency,
                run.self_kills, run.team_kills, run.escort_guids, run.enemies_nearby, run.nearby_teammates,
                run.run_type, run.obj_x, run.obj_y, run.obj_z,
                run.killer_guid, run.killer_name,
            ]
            if supports_round_end:
                columns.insert(3, "round_end_unix")
                values.insert(3, self.metadata.get('round_end_unix', 0))
            await self._append_round_link_columns("proximity_objective_run", columns, values)
            placeholders = ", ".join(f"${i}" for i in range(1, len(values) + 1))
            query = f"""
                INSERT INTO proximity_objective_run ({", ".join(columns)})
                VALUES ({placeholders})
                ON CONFLICT DO NOTHING
            """
            await self.db_adapter.execute(query, tuple(values))

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
            await self._append_round_link_columns("proximity_objective_focus", columns, values)
            placeholders = ", ".join(f"${i}" for i in range(1, len(values) + 1))
            round_link_updates = await self._round_link_update_clauses("proximity_objective_focus")
            extra_updates = ""
            if round_link_updates:
                extra_updates = ",\n                    " + ",\n                    ".join(round_link_updates)
            query = f"""
                INSERT INTO proximity_objective_focus ({", ".join(columns)})
                VALUES ({placeholders})
                ON CONFLICT (session_date, round_number, round_start_unix, player_guid) DO UPDATE SET
                    player_name = EXCLUDED.player_name,
                    team = EXCLUDED.team,
                    objective = EXCLUDED.objective,
                    avg_distance = EXCLUDED.avg_distance,
                    time_within_radius_ms = EXCLUDED.time_within_radius_ms,
                    samples = EXCLUDED.samples{extra_updates}
            """
            await self.db_adapter.execute(query, tuple(values))

    async def _import_spawn_timing(self, session_date):
        """Import v5 spawn timing events"""
        if not await self._table_has_column('proximity_spawn_timing', 'killer_guid'):
            return
        supports_round_end = await self._table_has_column('proximity_spawn_timing', 'round_end_unix')
        for evt in self.spawn_timing_events:
            columns = [
                "session_date", "round_number", "round_start_unix",
                "map_name",
                "killer_guid", "killer_name", "killer_team",
                "victim_guid", "victim_name", "victim_team",
                "kill_time", "enemy_spawn_interval",
                "time_to_next_spawn", "spawn_timing_score",
            ]
            values = [
                session_date,
                self.metadata['round_num'],
                self.metadata.get('round_start_unix', 0),
                self.metadata['map_name'],
                evt.killer_guid, evt.killer_name, evt.killer_team,
                evt.victim_guid, evt.victim_name, evt.victim_team,
                evt.kill_time, evt.enemy_spawn_interval,
                evt.time_to_next_spawn, evt.spawn_timing_score,
            ]
            if supports_round_end:
                columns.insert(3, "round_end_unix")
                values.insert(3, self.metadata.get('round_end_unix', 0))
            # Oksii adoption fields (optional — backward compatible)
            if await self._table_has_column('proximity_spawn_timing', 'killer_reinf'):
                columns.extend(["killer_reinf", "victim_reinf"])
                values.extend([evt.killer_reinf, evt.victim_reinf])
            await self._append_round_link_columns("proximity_spawn_timing", columns, values)
            placeholders = ", ".join(f"${i}" for i in range(1, len(values) + 1))
            query = f"""
                INSERT INTO proximity_spawn_timing ({", ".join(columns)})
                VALUES ({placeholders})
                ON CONFLICT DO NOTHING
            """
            await self.db_adapter.execute(query, tuple(values))

    async def _import_team_cohesion(self, session_date):
        """Import v5 team cohesion snapshots"""
        if not await self._table_has_column('proximity_team_cohesion', 'team'):
            return
        supports_round_end = await self._table_has_column('proximity_team_cohesion', 'round_end_unix')
        for snap in self.team_cohesion_snapshots:
            columns = [
                "session_date", "round_number", "round_start_unix",
                "map_name",
                "sample_time", "team", "alive_count",
                "centroid_x", "centroid_y", "dispersion", "max_spread",
                "straggler_count", "buddy_pair_guids", "buddy_distance",
            ]
            values = [
                session_date,
                self.metadata['round_num'],
                self.metadata.get('round_start_unix', 0),
                self.metadata['map_name'],
                snap.sample_time, snap.team, snap.alive_count,
                snap.centroid_x, snap.centroid_y, snap.dispersion, snap.max_spread,
                snap.straggler_count, snap.buddy_pair_guids, snap.buddy_distance,
            ]
            if supports_round_end:
                columns.insert(3, "round_end_unix")
                values.insert(3, self.metadata.get('round_end_unix', 0))
            await self._append_round_link_columns("proximity_team_cohesion", columns, values)
            placeholders = ", ".join(f"${i}" for i in range(1, len(values) + 1))
            query = f"""
                INSERT INTO proximity_team_cohesion ({", ".join(columns)})
                VALUES ({placeholders})
                ON CONFLICT DO NOTHING
            """
            await self.db_adapter.execute(query, tuple(values))

    async def _import_crossfire_opportunities(self, session_date):
        """Import v5 crossfire opportunity events"""
        if not await self._table_has_column('proximity_crossfire_opportunity', 'target_guid'):
            return
        supports_round_end = await self._table_has_column('proximity_crossfire_opportunity', 'round_end_unix')
        for opp in self.crossfire_opportunities:
            columns = [
                "session_date", "round_number", "round_start_unix",
                "map_name",
                "event_time", "target_guid", "target_name", "target_team",
                "teammate1_guid", "teammate2_guid",
                "angular_separation", "was_executed", "damage_within_window",
            ]
            values = [
                session_date,
                self.metadata['round_num'],
                self.metadata.get('round_start_unix', 0),
                self.metadata['map_name'],
                opp.event_time, opp.target_guid, opp.target_name, opp.target_team,
                opp.teammate1_guid, opp.teammate2_guid,
                opp.angular_separation, opp.was_executed, opp.damage_within_window,
            ]
            if supports_round_end:
                columns.insert(3, "round_end_unix")
                values.insert(3, self.metadata.get('round_end_unix', 0))
            await self._append_round_link_columns("proximity_crossfire_opportunity", columns, values)
            placeholders = ", ".join(f"${i}" for i in range(1, len(values) + 1))
            query = f"""
                INSERT INTO proximity_crossfire_opportunity ({", ".join(columns)})
                VALUES ({placeholders})
                ON CONFLICT DO NOTHING
            """
            await self.db_adapter.execute(query, tuple(values))

    async def _import_team_pushes(self, session_date):
        """Import v5 team push events"""
        if not await self._table_has_column('proximity_team_push', 'team'):
            return
        supports_round_end = await self._table_has_column('proximity_team_push', 'round_end_unix')
        for push in self.team_pushes:
            columns = [
                "session_date", "round_number", "round_start_unix",
                "map_name",
                "start_time", "end_time", "team", "avg_speed",
                "direction_x", "direction_y", "alignment_score",
                "push_quality", "participant_count", "toward_objective",
            ]
            values = [
                session_date,
                self.metadata['round_num'],
                self.metadata.get('round_start_unix', 0),
                self.metadata['map_name'],
                push.start_time, push.end_time, push.team, push.avg_speed,
                push.direction_x, push.direction_y, push.alignment_score,
                push.push_quality, push.participant_count, push.toward_objective,
            ]
            if supports_round_end:
                columns.insert(3, "round_end_unix")
                values.insert(3, self.metadata.get('round_end_unix', 0))
            await self._append_round_link_columns("proximity_team_push", columns, values)
            placeholders = ", ".join(f"${i}" for i in range(1, len(values) + 1))
            query = f"""
                INSERT INTO proximity_team_push ({", ".join(columns)})
                VALUES ({placeholders})
                ON CONFLICT DO NOTHING
            """
            await self.db_adapter.execute(query, tuple(values))

    async def _import_lua_trade_kills(self, session_date):
        """Import v5 Lua-side trade kill events"""
        if not await self._table_has_column('proximity_lua_trade_kill', 'trader_guid'):
            return
        supports_round_end = await self._table_has_column('proximity_lua_trade_kill', 'round_end_unix')
        for tk in self.lua_trade_kills:
            columns = [
                "session_date", "round_number", "round_start_unix",
                "map_name",
                "original_kill_time", "traded_kill_time", "delta_ms",
                "original_victim_guid", "original_victim_name",
                "original_killer_guid", "original_killer_name",
                "trader_guid", "trader_name",
            ]
            values = [
                session_date,
                self.metadata['round_num'],
                self.metadata.get('round_start_unix', 0),
                self.metadata['map_name'],
                tk.original_kill_time, tk.traded_kill_time, tk.delta_ms,
                tk.original_victim_guid, tk.original_victim_name,
                tk.original_killer_guid, tk.original_killer_name,
                tk.trader_guid, tk.trader_name,
            ]
            if supports_round_end:
                columns.insert(3, "round_end_unix")
                values.insert(3, self.metadata.get('round_end_unix', 0))
            await self._append_round_link_columns("proximity_lua_trade_kill", columns, values)
            placeholders = ", ".join(f"${i}" for i in range(1, len(values) + 1))
            query = f"""
                INSERT INTO proximity_lua_trade_kill ({", ".join(columns)})
                VALUES ({placeholders})
                ON CONFLICT DO NOTHING
            """
            await self.db_adapter.execute(query, tuple(values))

    async def _import_revive_events(self, session_date):
        """Import revive events to proximity_revive table"""
        if not await self._table_has_column('proximity_revive', 'revived_guid'):
            return
        for evt in self.revive_events:
            columns = [
                "round_id", "map_name",
                "medic_guid", "medic_name",
                "revived_guid", "revived_name",
                "revive_time", "revive_x", "revive_y", "revive_z",
                "distance_to_enemy", "under_fire", "nearest_enemy_guid",
            ]
            values = [
                self._round_link_context.get("round_id"),
                self.metadata['map_name'],
                evt.medic_guid, evt.medic_name,
                evt.revived_guid, evt.revived_name,
                evt.time, evt.x, evt.y, evt.z,
                evt.distance_to_enemy, evt.under_fire, evt.nearest_enemy_guid,
            ]
            placeholders = ", ".join(f"${i}" for i in range(1, len(values) + 1))
            query = f"""
                INSERT INTO proximity_revive ({", ".join(columns)})
                VALUES ({placeholders})
                ON CONFLICT DO NOTHING
            """
            await self.db_adapter.execute(query, tuple(values))

    async def _import_weapon_accuracy(self, session_date):
        """Import weapon accuracy data to proximity_weapon_accuracy table"""
        if not await self._table_has_column('proximity_weapon_accuracy', 'player_guid'):
            return
        for wa in self.weapon_accuracy:
            columns = [
                "round_id", "map_name",
                "player_guid", "player_name", "team",
                "weapon_id", "shots_fired", "hits", "kills", "headshots",
            ]
            values = [
                self._round_link_context.get("round_id"),
                self.metadata['map_name'],
                wa.player_guid, wa.player_name, wa.team,
                wa.weapon_id, wa.shots_fired, wa.hits, wa.kills, wa.headshots,
            ]
            placeholders = ", ".join(f"${i}" for i in range(1, len(values) + 1))
            query = f"""
                INSERT INTO proximity_weapon_accuracy ({", ".join(columns)})
                VALUES ({placeholders})
                ON CONFLICT DO NOTHING
            """
            await self.db_adapter.execute(query, tuple(values))

    async def _import_focus_fire_events(self, session_date):
        """Import focus fire events to proximity_focus_fire table"""
        if not await self._table_has_column('proximity_focus_fire', 'target_guid'):
            return
        supports_round_end = await self._table_has_column('proximity_focus_fire', 'round_end_unix')
        for ff in self.focus_fire_events:
            columns = [
                "session_date", "round_number", "round_start_unix",
                "map_name", "engagement_id",
                "target_guid", "target_name",
                "attacker_count", "attacker_guids",
                "total_damage", "duration", "focus_score",
            ]
            values = [
                session_date,
                self.metadata['round_num'],
                self.metadata.get('round_start_unix', 0),
                self.metadata['map_name'],
                ff.engagement_id,
                ff.target_guid, ff.target_name,
                ff.attacker_count, ff.attacker_guids,
                ff.total_damage, ff.duration, ff.focus_score,
            ]
            if supports_round_end:
                columns.insert(3, "round_end_unix")
                values.insert(3, self.metadata.get('round_end_unix', 0))
            await self._append_round_link_columns("proximity_focus_fire", columns, values)
            placeholders = ", ".join(f"${i}" for i in range(1, len(values) + 1))
            query = f"""
                INSERT INTO proximity_focus_fire ({", ".join(columns)})
                VALUES ({placeholders})
                ON CONFLICT (session_date, round_number, round_start_unix, engagement_id)
                DO NOTHING
            """
            await self.db_adapter.execute(query, tuple(values))

    def _distance2d(self, a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
        dx = (a[0] or 0) - (b[0] or 0)
        dy = (a[1] or 0) - (b[1] or 0)
        return (dx * dx + dy * dy) ** 0.5

    def _closest_track_point(
        self,
        track: PlayerTrack,
        target_time: int,
        max_delta_ms: int,
        point_times: list[int] | None = None,
    ) -> PathPoint | None:
        if not track.path:
            return None
        if point_times and len(point_times) == len(track.path):
            idx = bisect_left(point_times, target_time)
            candidate_indexes = []
            if idx < len(point_times):
                candidate_indexes.append(idx)
            if idx > 0:
                candidate_indexes.append(idx - 1)
            if not candidate_indexes:
                return None

            best_idx = candidate_indexes[0]
            best_delta = abs(point_times[best_idx] - target_time)
            for cand_idx in candidate_indexes[1:]:
                cand_delta = abs(point_times[cand_idx] - target_time)
                if cand_delta < best_delta or (cand_delta == best_delta and cand_idx < best_idx):
                    best_idx = cand_idx
                    best_delta = cand_delta

            if best_delta > max_delta_ms:
                return None
            return track.path[best_idx]

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

    def _track_for_time(self, tracks: list[PlayerTrack], target_time: int) -> PlayerTrack | None:
        for track in tracks:
            if track.spawn_time <= target_time and (track.death_time is None or track.death_time >= target_time):
                return track
        return None

    def _merge_intervals(self, intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
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

    def _is_in_combat(self, intervals: list[tuple[int, int]], time_ms: int) -> bool:
        if not intervals:
            return False
        left = 0
        right = len(intervals) - 1
        while left <= right:
            mid = (left + right) // 2
            start, end = intervals[mid]
            if time_ms < start:
                right = mid - 1
                continue
            if time_ms > end:
                left = mid + 1
                continue
            return True
        return False

    def _compute_support_uptime(self) -> dict | None:
        if not self.player_tracks:
            return None

        support_dist = float(os.getenv("PROXIMITY_SUPPORT_DIST", "600"))
        combat_recent_ms = int(os.getenv("PROXIMITY_COMBAT_RECENT_MS", "1500"))
        max_pos_delta = int(os.getenv("PROXIMITY_SUPPORT_POS_DELTA_MS", "1500"))
        max_samples_per_track = max(
            200, int(os.getenv("PROXIMITY_SUPPORT_MAX_SAMPLES_PER_TRACK", "1200"))
        )

        combat_intervals_by_guid: dict[str, list[tuple[int, int]]] = {}

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
        teammates_by_team: dict[str, list[PlayerTrack]] = {}
        path_times_by_track_id: dict[int, list[int]] = {}
        for track in tracks:
            teammates_by_team.setdefault(track.team, []).append(track)
            if track.path:
                point_times = [p.time for p in track.path]
                is_sorted = True
                for idx in range(1, len(point_times)):
                    if point_times[idx] < point_times[idx - 1]:
                        is_sorted = False
                        break
                if is_sorted:
                    path_times_by_track_id[id(track)] = point_times

        support_samples = 0
        total_samples = 0

        for track in tracks:
            if not track.path:
                continue
            teammates = teammates_by_team.get(track.team, [])
            sample_points = track.path
            if len(sample_points) > max_samples_per_track:
                # Keep runtime bounded on very long rounds by sampling points uniformly.
                stride = max(1, len(sample_points) // max_samples_per_track)
                sample_points = sample_points[::stride]

            for point in sample_points:
                total_samples += 1
                in_support = False
                for teammate in teammates:
                    if teammate is track:
                        continue
                    teammate_combat = combat_intervals_by_guid.get(teammate.guid, [])
                    if not teammate_combat:
                        continue
                    if not (teammate.spawn_time <= point.time and (teammate.death_time is None or teammate.death_time >= point.time)):
                        continue
                    if not self._is_in_combat(teammate_combat, point.time):
                        continue
                    teammate_point = self._closest_track_point(
                        teammate,
                        point.time,
                        max_pos_delta,
                        point_times=path_times_by_track_id.get(id(teammate)),
                    )
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
        extended_window_ms = 5000  # For diagnostic comparison vs industry 5s standard
        trade_dist = float(os.getenv("PROXIMITY_TRADE_DIST", "800"))
        max_pos_delta = int(os.getenv("PROXIMITY_TRADE_POS_DELTA_MS", "1500"))
        isolation_dist = float(os.getenv("PROXIMITY_ISOLATION_DIST", "1200"))

        tracks_by_guid: dict[str, list[PlayerTrack]] = {}
        for track in self.player_tracks:
            tracks_by_guid.setdefault(track.guid, []).append(track)
        for guid in tracks_by_guid:
            tracks_by_guid[guid].sort(key=lambda t: t.spawn_time)

        engagements_by_target: dict[str, list[Engagement]] = {}
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

            attempts_map: dict[str, dict] = {}
            successes_map: dict[str, dict] = {}

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

        # Diagnostic: count trades that would be caught with 5s window but missed at 3s.
        # This helps validate whether our tighter window misses legitimate trades.
        if trade_window_ms < extended_window_ms:
            extended_only_successes = 0
            for eng in self.engagements:
                if eng.outcome != 'killed' or not eng.killer_guid:
                    continue
                death_time = eng.end_time
                victim_team = eng.target_team
                killer_engs = engagements_by_target.get(eng.killer_guid, [])
                for k_eng in killer_engs:
                    if (k_eng.outcome == 'killed'
                            and death_time + trade_window_ms < k_eng.end_time <= death_time + extended_window_ms):
                        for att in k_eng.attackers.values():
                            if att.team == victim_team and att.got_kill:
                                extended_only_successes += 1
                                break
            if extended_only_successes > 0:
                current_count = sum(len(e.get("successes", [])) for e in trade_events)
                self.logger.info(
                    f"Trade window diagnostic: {current_count} trades at {trade_window_ms}ms, "
                    f"+{extended_only_successes} additional at {extended_window_ms}ms "
                    f"({extended_only_successes / max(1, current_count + extended_only_successes) * 100:.0f}%% missed)"
                )

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
            await self._append_round_link_columns("proximity_trade_event", columns, values)
            placeholders = ", ".join(f"${i}" for i in range(1, len(values) + 1))
            query = f"""
                INSERT INTO proximity_trade_event ({", ".join(columns)})
                VALUES ({placeholders})
                ON CONFLICT (session_date, round_number, round_start_unix, victim_guid, death_time_ms)
                DO NOTHING
            """
            await self.db_adapter.execute(query, tuple(values))

    async def _import_reaction_metrics(self, session_date: str):
        if not self.reaction_metrics:
            return
        if not await self._table_has_column('proximity_reaction_metric', 'engagement_id'):
            self.logger.info("proximity_reaction_metric table not found; skipping reaction import")
            return

        supports_round_end = await self._table_has_column('proximity_reaction_metric', 'round_end_unix')
        for metric in self.reaction_metrics:
            columns = [
                "session_date", "round_number", "round_start_unix",
                "map_name",
                "engagement_id",
                "target_guid", "target_name", "target_team", "target_class",
                "outcome", "num_attackers",
                "return_fire_ms", "dodge_reaction_ms", "support_reaction_ms",
                "start_time_ms", "end_time_ms", "duration_ms",
            ]
            values = [
                session_date,
                self.metadata['round_num'],
                self.metadata.get('round_start_unix', 0),
                self.metadata['map_name'],
                metric.engagement_id,
                metric.target_guid,
                metric.target_name,
                metric.target_team,
                metric.target_class,
                metric.outcome,
                metric.num_attackers,
                metric.return_fire_ms,
                metric.dodge_reaction_ms,
                metric.support_reaction_ms,
                metric.start_time_ms,
                metric.end_time_ms,
                metric.duration_ms,
            ]
            if supports_round_end:
                columns.insert(3, "round_end_unix")
                values.insert(3, self.metadata.get('round_end_unix', 0))
            await self._append_round_link_columns("proximity_reaction_metric", columns, values)

            placeholders = ", ".join(f"${i}" for i in range(1, len(values) + 1))
            round_link_updates = await self._round_link_update_clauses("proximity_reaction_metric")
            extra_updates = ""
            if round_link_updates:
                extra_updates = ",\n                    " + ",\n                    ".join(round_link_updates)
            query = f"""
                INSERT INTO proximity_reaction_metric ({", ".join(columns)})
                VALUES ({placeholders})
                ON CONFLICT (session_date, round_number, round_start_unix, engagement_id, target_guid)
                DO UPDATE SET
                    target_name = EXCLUDED.target_name,
                    target_team = EXCLUDED.target_team,
                    target_class = EXCLUDED.target_class,
                    outcome = EXCLUDED.outcome,
                    num_attackers = EXCLUDED.num_attackers,
                    return_fire_ms = EXCLUDED.return_fire_ms,
                    dodge_reaction_ms = EXCLUDED.dodge_reaction_ms,
                    support_reaction_ms = EXCLUDED.support_reaction_ms,
                    start_time_ms = EXCLUDED.start_time_ms,
                    end_time_ms = EXCLUDED.end_time_ms,
                    duration_ms = EXCLUDED.duration_ms{extra_updates}
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
        await self._append_round_link_columns("proximity_support_summary", columns, values)

        placeholders = ", ".join(f"${i}" for i in range(1, len(values) + 1))
        round_link_updates = await self._round_link_update_clauses("proximity_support_summary")
        extra_updates = ""
        if round_link_updates:
            extra_updates = ",\n                " + ",\n                ".join(round_link_updates)
        query = f"""
            INSERT INTO proximity_support_summary ({", ".join(columns)})
            VALUES ({placeholders})
            ON CONFLICT (session_date, round_number, round_start_unix)
            DO UPDATE SET
                support_samples = EXCLUDED.support_samples,
                total_samples = EXCLUDED.total_samples,
                support_uptime_pct = EXCLUDED.support_uptime_pct,
                computed_at = CURRENT_TIMESTAMP{extra_updates}
        """
        await self.db_adapter.execute(query, tuple(values))

    def get_stats(self) -> dict:
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
            'avg_life_ms': avg_life,
            'reaction_metrics': len(self.reaction_metrics),
            # v5 teamplay
            'tracker_version': self.metadata.get('tracker_version', 4),
            'spawn_timing_events': len(self.spawn_timing_events),
            'team_cohesion_snapshots': len(self.team_cohesion_snapshots),
            'crossfire_opportunities': len(self.crossfire_opportunities),
            'team_pushes': len(self.team_pushes),
            'lua_trade_kills': len(self.lua_trade_kills),
            'focus_fire_events': len(self.focus_fire_events),
            'kill_outcomes': len(self.kill_outcomes),
            'hit_regions': len(self.hit_regions),
            'combat_positions': len(self.combat_positions),
            'carrier_events': len(self.carrier_events),
            'carrier_kills': len(self.carrier_kills),
            'carrier_returns': len(self.carrier_returns),
            'vehicle_progress': len(self.vehicle_progress),
            'escort_credits': len(self.escort_credits),
            'construction_events': len(self.construction_events),
            'objective_runs': len(self.objective_runs),
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
    print("\n=== STATS ===")
    print(f"Map: {stats['map']}, Round: {stats['round']}")
    print(f"Engagements: {stats['total_engagements']}")
    print(f"  Crossfire: {stats['crossfire_engagements']}")
    print(f"  Kills: {stats['kills']}")
    print(f"  Escapes: {stats['escapes']}")
    print(f"Heatmap cells: {stats['heatmap_cells']}")

    # v4 track stats
    if stats['total_tracks'] > 0:
        print("\n=== PLAYER TRACKS (v4) ===")
        print(f"Total tracks: {stats['total_tracks']}")
        print(f"Total samples: {stats['total_samples']}")
        print(f"Total distance: {stats['total_distance']:.1f} units")
        print(f"Avg life time: {stats['avg_life_ms']:.0f}ms")

    if parser.engagements:
        print("\n=== SAMPLE ENGAGEMENT ===")
        e = parser.engagements[0]
        print(f"ID: {e.id}, Target: {e.target_name}")
        print(f"Outcome: {e.outcome}, Duration: {e.duration}ms")
        print(f"Attackers: {[a.name for a in e.attackers.values()]}")
        print(f"Crossfire: {e.is_crossfire}, Delay: {e.crossfire_delay}ms")
        print(f"Position path: {len(e.position_path)} points")

    if parser.player_tracks:
        print("\n=== SAMPLE TRACK ===")
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
