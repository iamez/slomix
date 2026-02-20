-- ============================================================
-- PROXIMITY TRACKER v4 - FULL PLAYER TRACKING SCHEMA
-- Forever storage, ~600K rows/year = trivial
-- v4 adds: Full player tracks from spawn to death
-- ============================================================

-- ===== COMBAT ENGAGEMENTS =====
-- One row per "player got attacked" event
-- ~100 rows/round, ~365K/year
CREATE TABLE IF NOT EXISTS combat_engagement (
    id SERIAL PRIMARY KEY,
    
    -- Session context
    session_date DATE NOT NULL,
    round_number INTEGER NOT NULL,
    round_start_unix INTEGER DEFAULT 0,
    round_end_unix INTEGER DEFAULT 0,
    map_name VARCHAR(64) NOT NULL,
    engagement_id INTEGER NOT NULL,  -- unique within round
    
    -- Timing
    start_time_ms INTEGER NOT NULL,
    end_time_ms INTEGER NOT NULL,
    duration_ms INTEGER NOT NULL,
    
    -- Target (the player being attacked)
    target_guid VARCHAR(32) NOT NULL,
    target_name VARCHAR(64) NOT NULL,
    target_team VARCHAR(10) NOT NULL,
    
    -- Outcome
    outcome VARCHAR(20) NOT NULL,  -- 'killed', 'escaped', 'round_end'
    total_damage_taken INTEGER NOT NULL,
    killer_guid VARCHAR(32),  -- NULL if escaped
    killer_name VARCHAR(64),
    
    -- Position path for map visualization (sampled every 2s + at events)
    -- [{time_ms, x, y, z, event: 'start'|'hit'|'sample'|'death'|'escape'}]
    position_path JSONB NOT NULL DEFAULT '[]',
    
    -- Start/end positions (quick access without parsing JSON)
    start_x REAL NOT NULL,
    start_y REAL NOT NULL,
    start_z REAL NOT NULL,
    end_x REAL NOT NULL,
    end_y REAL NOT NULL,
    end_z REAL NOT NULL,
    distance_traveled REAL NOT NULL,
    
    -- Attackers detail
    -- [{guid, name, team, damage, hits, first_hit_ms, last_hit_ms, got_kill, weapons: []}]
    attackers JSONB NOT NULL DEFAULT '[]',
    num_attackers INTEGER NOT NULL,
    
    -- Crossfire detection (2+ attackers hit within 1 second)
    is_crossfire BOOLEAN NOT NULL DEFAULT FALSE,
    crossfire_delay_ms INTEGER,  -- time between first two attackers
    crossfire_participants JSONB,  -- [guid1, guid2, ...]
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(session_date, round_number, round_start_unix, engagement_id)
);

-- ===== PLAYER TEAMPLAY STATS =====
-- Aggregated per player, updated incrementally
-- ~200 unique players total
CREATE TABLE IF NOT EXISTS player_teamplay_stats (
    id SERIAL PRIMARY KEY,
    
    player_guid VARCHAR(32) NOT NULL UNIQUE,
    player_name VARCHAR(64) NOT NULL,  -- last known name
    
    -- Offensive teamplay (helping teammates get kills)
    crossfire_participations INTEGER DEFAULT 0,  -- times hit target teammate also hit (within 1s)
    crossfire_kills INTEGER DEFAULT 0,           -- crossfires that ended in kill (you or teammate)
    crossfire_damage INTEGER DEFAULT 0,          -- damage dealt in crossfire situations
    crossfire_final_blows INTEGER DEFAULT 0,     -- YOU got the kill in crossfire
    avg_crossfire_delay_ms REAL,                 -- how fast you sync (lower = better)
    
    -- Solo performance
    solo_kills INTEGER DEFAULT 0,          -- 1v1 kills (only you attacked)
    solo_engagements INTEGER DEFAULT 0,    -- 1v1 fights you started
    
    -- Getting focused (defensive awareness)
    times_targeted INTEGER DEFAULT 0,      -- total times you were the target
    times_focused INTEGER DEFAULT 0,       -- engaged by 2+ attackers
    focus_escapes INTEGER DEFAULT 0,       -- escaped when 2+ attacked you
    focus_deaths INTEGER DEFAULT 0,        -- died when 2+ attacked you
    solo_escapes INTEGER DEFAULT 0,        -- escaped 1v1
    solo_deaths INTEGER DEFAULT 0,         -- died 1v1
    
    -- Movement/survival stats
    avg_escape_distance REAL,              -- how far you typically run
    avg_engagement_duration_ms REAL,       -- how long fights last for you
    total_damage_taken INTEGER DEFAULT 0,
    total_damage_dealt_crossfire INTEGER DEFAULT 0,
    
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ===== KILL HEATMAP (PER MAP) =====
-- Grid-based kill/death density
-- ~50 cells per map, separate per map
CREATE TABLE IF NOT EXISTS map_kill_heatmap (
    id SERIAL PRIMARY KEY,
    
    map_name VARCHAR(64) NOT NULL,
    grid_x INTEGER NOT NULL,
    grid_y INTEGER NOT NULL,
    grid_size INTEGER DEFAULT 512,
    
    -- Kill counts (who killed here)
    total_kills INTEGER DEFAULT 0,
    axis_kills INTEGER DEFAULT 0,
    allies_kills INTEGER DEFAULT 0,
    
    -- Death counts (who died here)
    total_deaths INTEGER DEFAULT 0,
    axis_deaths INTEGER DEFAULT 0,
    allies_deaths INTEGER DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(map_name, grid_x, grid_y)
);

-- ===== MOVEMENT HEATMAP (PER MAP) =====
-- Traffic patterns for path visualization
CREATE TABLE IF NOT EXISTS map_movement_heatmap (
    id SERIAL PRIMARY KEY,
    
    map_name VARCHAR(64) NOT NULL,
    grid_x INTEGER NOT NULL,
    grid_y INTEGER NOT NULL,
    grid_size INTEGER DEFAULT 512,
    
    traversal_count INTEGER DEFAULT 0,  -- times players passed through
    combat_count INTEGER DEFAULT 0,     -- times combat happened here
    escape_count INTEGER DEFAULT 0,     -- times players escaped through here
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(map_name, grid_x, grid_y)
);

-- ===== CROSSFIRE PAIRS =====
-- Track which player pairs coordinate well
CREATE TABLE IF NOT EXISTS crossfire_pairs (
    id SERIAL PRIMARY KEY,
    
    -- Always store lower GUID first for consistency
    player1_guid VARCHAR(32) NOT NULL,
    player1_name VARCHAR(64),
    player2_guid VARCHAR(32) NOT NULL,
    player2_name VARCHAR(64),
    
    -- Stats
    crossfire_count INTEGER DEFAULT 0,        -- times both hit same target within 1s
    crossfire_kills INTEGER DEFAULT 0,        -- crossfires ending in kill
    total_combined_damage INTEGER DEFAULT 0,
    avg_delay_ms REAL,                        -- avg time between their hits
    
    games_together INTEGER DEFAULT 0,
    first_played TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_played TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(player1_guid, player2_guid)
);

-- ===== PLAYER TRACKS (v4) =====
-- Full player movement from spawn to death
-- Tracks position, health, speed, weapon, stance, sprint every 1 second
-- ~20 tracks/round × 10 rounds/day × 365 = 73,000/year
CREATE TABLE IF NOT EXISTS player_track (
    id SERIAL PRIMARY KEY,

    -- Session context
    session_date DATE NOT NULL,
    round_number INTEGER NOT NULL,
    round_start_unix INTEGER DEFAULT 0,
    round_end_unix INTEGER DEFAULT 0,
    map_name VARCHAR(64) NOT NULL,

    -- Player info
    player_guid VARCHAR(32) NOT NULL,
    player_name VARCHAR(64) NOT NULL,
    team VARCHAR(10) NOT NULL,
    player_class VARCHAR(16) NOT NULL,  -- SOLDIER, MEDIC, ENGINEER, FIELDOPS, COVERTOPS

    -- Timing
    spawn_time_ms INTEGER NOT NULL,
    death_time_ms INTEGER,              -- NULL if round ended before death
    duration_ms INTEGER,                -- total time alive
    first_move_time_ms INTEGER,         -- when player first moved after spawn
    time_to_first_move_ms INTEGER,      -- spawn_time to first_move (reaction time)

    -- Movement data
    sample_count INTEGER NOT NULL,
    path JSONB NOT NULL DEFAULT '[]',
    -- Path format: [{time, x, y, z, health, speed, weapon, stance, sprint, event}, ...]
    -- stance: 0=standing, 1=crouching, 2=prone
    -- sprint: 0=not sprinting, 1=sprinting
    -- event: spawn, sample, death, round_end

    -- Derived stats (calculated at import time)
    total_distance REAL,                -- total distance traveled
    avg_speed REAL,                     -- average movement speed
    sprint_percentage REAL,             -- % of time sprinting

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(session_date, round_number, round_start_unix, player_guid, spawn_time_ms)
);

-- ===== INDEXES =====

-- Engagement queries
CREATE INDEX IF NOT EXISTS idx_engagement_session 
    ON combat_engagement(session_date, round_number);
CREATE INDEX IF NOT EXISTS idx_engagement_map 
    ON combat_engagement(map_name);
CREATE INDEX IF NOT EXISTS idx_engagement_target 
    ON combat_engagement(target_guid);
CREATE INDEX IF NOT EXISTS idx_engagement_crossfire 
    ON combat_engagement(is_crossfire) WHERE is_crossfire = TRUE;
CREATE INDEX IF NOT EXISTS idx_engagement_outcome 
    ON combat_engagement(outcome);

-- Player stats
CREATE INDEX IF NOT EXISTS idx_teamplay_guid 
    ON player_teamplay_stats(player_guid);
CREATE INDEX IF NOT EXISTS idx_teamplay_crossfire 
    ON player_teamplay_stats(crossfire_kills DESC);

-- Heatmaps
CREATE INDEX IF NOT EXISTS idx_kill_heatmap_map 
    ON map_kill_heatmap(map_name);
CREATE INDEX IF NOT EXISTS idx_movement_heatmap_map 
    ON map_movement_heatmap(map_name);

-- Crossfire pairs
CREATE INDEX IF NOT EXISTS idx_crossfire_pairs_player1
    ON crossfire_pairs(player1_guid);
CREATE INDEX IF NOT EXISTS idx_crossfire_pairs_player2
    ON crossfire_pairs(player2_guid);

-- Player tracks (v4)
CREATE INDEX IF NOT EXISTS idx_track_session
    ON player_track(session_date, round_number);
CREATE INDEX IF NOT EXISTS idx_track_player
    ON player_track(player_guid);
CREATE INDEX IF NOT EXISTS idx_track_map
    ON player_track(map_name);
CREATE INDEX IF NOT EXISTS idx_track_class
    ON player_track(player_class);

-- ===== VIEWS =====

-- Teamplay leaderboard
CREATE OR REPLACE VIEW teamplay_leaderboard AS
SELECT 
    player_name,
    player_guid,
    crossfire_kills,
    crossfire_participations,
    ROUND(100.0 * crossfire_kills / NULLIF(crossfire_participations, 0), 1) as crossfire_kill_rate,
    ROUND(avg_crossfire_delay_ms, 0) as avg_sync_ms,
    solo_kills,
    focus_escapes,
    times_focused,
    ROUND(100.0 * focus_escapes / NULLIF(times_focused, 0), 1) as focus_survival_rate
FROM player_teamplay_stats
WHERE crossfire_participations > 0
ORDER BY crossfire_kills DESC;

-- Best duo partners
CREATE OR REPLACE VIEW best_duos AS
SELECT 
    player1_name,
    player2_name,
    crossfire_count,
    crossfire_kills,
    ROUND(100.0 * crossfire_kills / NULLIF(crossfire_count, 0), 1) as kill_rate,
    ROUND(avg_delay_ms, 0) as sync_ms,
    games_together
FROM crossfire_pairs
WHERE crossfire_count >= 5
ORDER BY crossfire_kills DESC;

-- Map hotspots
CREATE OR REPLACE VIEW map_hotspots AS
SELECT 
    map_name,
    grid_x,
    grid_y,
    total_kills,
    total_deaths,
    total_kills + total_deaths as total_combat
FROM map_kill_heatmap
ORDER BY map_name, total_combat DESC;

-- Engagement summary per session
CREATE OR REPLACE VIEW session_engagement_summary AS
SELECT 
    session_date,
    map_name,
    COUNT(*) as total_engagements,
    SUM(CASE WHEN outcome = 'killed' THEN 1 ELSE 0 END) as kills,
    SUM(CASE WHEN outcome = 'escaped' THEN 1 ELSE 0 END) as escapes,
    SUM(CASE WHEN is_crossfire THEN 1 ELSE 0 END) as crossfire_engagements,
    ROUND(AVG(duration_ms), 0) as avg_duration_ms,
    ROUND(AVG(num_attackers), 2) as avg_attackers
FROM combat_engagement
GROUP BY session_date, map_name
ORDER BY session_date DESC;

-- ===== HELPER FUNCTIONS =====

-- Get player's crossfire partners
CREATE OR REPLACE FUNCTION get_crossfire_partners(p_guid VARCHAR(32))
RETURNS TABLE(
    partner_guid VARCHAR(32),
    partner_name VARCHAR(64),
    crossfire_count INTEGER,
    crossfire_kills INTEGER,
    avg_delay_ms REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        CASE WHEN player1_guid = p_guid THEN player2_guid ELSE player1_guid END,
        CASE WHEN player1_guid = p_guid THEN player2_name ELSE player1_name END,
        cp.crossfire_count,
        cp.crossfire_kills,
        cp.avg_delay_ms
    FROM crossfire_pairs cp
    WHERE player1_guid = p_guid OR player2_guid = p_guid
    ORDER BY cp.crossfire_kills DESC;
END;
$$ LANGUAGE plpgsql;

-- Update player stats from engagement data
CREATE OR REPLACE FUNCTION update_player_stats_from_engagement(
    p_engagement_id INTEGER
) RETURNS VOID AS $$
DECLARE
    eng RECORD;
    attacker RECORD;
BEGIN
    -- Get engagement
    SELECT * INTO eng FROM combat_engagement WHERE id = p_engagement_id;
    IF NOT FOUND THEN RETURN; END IF;
    
    -- Update target's defensive stats
    INSERT INTO player_teamplay_stats (player_guid, player_name, times_targeted)
    VALUES (eng.target_guid, eng.target_name, 1)
    ON CONFLICT (player_guid) DO UPDATE SET
        player_name = EXCLUDED.player_name,
        times_targeted = player_teamplay_stats.times_targeted + 1,
        last_updated = CURRENT_TIMESTAMP;
    
    -- Update based on outcome and attacker count
    IF eng.num_attackers >= 2 THEN
        -- Was focused
        UPDATE player_teamplay_stats SET
            times_focused = times_focused + 1,
            focus_escapes = focus_escapes + CASE WHEN eng.outcome = 'escaped' THEN 1 ELSE 0 END,
            focus_deaths = focus_deaths + CASE WHEN eng.outcome = 'killed' THEN 1 ELSE 0 END
        WHERE player_guid = eng.target_guid;
    ELSE
        -- 1v1
        UPDATE player_teamplay_stats SET
            solo_escapes = solo_escapes + CASE WHEN eng.outcome = 'escaped' THEN 1 ELSE 0 END,
            solo_deaths = solo_deaths + CASE WHEN eng.outcome = 'killed' THEN 1 ELSE 0 END
        WHERE player_guid = eng.target_guid;
    END IF;
    
    -- Note: Attacker stats are updated by the Python parser since it needs to iterate JSON
END;
$$ LANGUAGE plpgsql;

-- ===== OBJECTIVE FOCUS (OPTIONAL) =====
-- Per-player focus on closest objective during the round
CREATE TABLE IF NOT EXISTS proximity_objective_focus (
    id SERIAL PRIMARY KEY,

    session_date DATE NOT NULL,
    round_number INTEGER NOT NULL,
    round_start_unix INTEGER DEFAULT 0,
    round_end_unix INTEGER DEFAULT 0,
    map_name VARCHAR(64) NOT NULL,

    player_guid VARCHAR(32) NOT NULL,
    player_name VARCHAR(64) NOT NULL,
    team VARCHAR(10) NOT NULL,

    objective VARCHAR(64) NOT NULL,
    avg_distance REAL NOT NULL,
    time_within_radius_ms INTEGER NOT NULL,
    samples INTEGER NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(session_date, round_number, round_start_unix, player_guid)
);

-- ===== TRADE EVENTS (v1) =====
-- Per-death trade opportunities/attempts/successes
CREATE TABLE IF NOT EXISTS proximity_trade_event (
    id SERIAL PRIMARY KEY,

    session_date DATE NOT NULL,
    round_number INTEGER NOT NULL,
    round_start_unix INTEGER DEFAULT 0,
    round_end_unix INTEGER DEFAULT 0,
    map_name VARCHAR(64) NOT NULL,

    victim_guid VARCHAR(32) NOT NULL,
    victim_name VARCHAR(64) NOT NULL,
    victim_team VARCHAR(10) NOT NULL,

    killer_guid VARCHAR(32),
    killer_name VARCHAR(64),

    death_time_ms INTEGER NOT NULL,
    trade_window_ms INTEGER NOT NULL,

    opportunity_count INTEGER DEFAULT 0,
    opportunities JSONB NOT NULL DEFAULT '[]',

    attempt_count INTEGER DEFAULT 0,
    attempts JSONB NOT NULL DEFAULT '[]',

    success_count INTEGER DEFAULT 0,
    successes JSONB NOT NULL DEFAULT '[]',

    missed_count INTEGER DEFAULT 0,
    missed_candidates JSONB NOT NULL DEFAULT '[]',

    nearest_teammate_dist REAL,
    is_isolation_death BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(session_date, round_number, round_start_unix, victim_guid, death_time_ms)
);

CREATE INDEX IF NOT EXISTS idx_trade_event_session
    ON proximity_trade_event(session_date, round_number);
CREATE INDEX IF NOT EXISTS idx_trade_event_victim
    ON proximity_trade_event(victim_guid);
CREATE INDEX IF NOT EXISTS idx_trade_event_killer
    ON proximity_trade_event(killer_guid);

-- ===== SUPPORT SUMMARY (v1) =====
CREATE TABLE IF NOT EXISTS proximity_support_summary (
    id SERIAL PRIMARY KEY,

    session_date DATE NOT NULL,
    round_number INTEGER NOT NULL,
    round_start_unix INTEGER DEFAULT 0,
    round_end_unix INTEGER DEFAULT 0,
    map_name VARCHAR(64) NOT NULL,

    support_samples INTEGER NOT NULL DEFAULT 0,
    total_samples INTEGER NOT NULL DEFAULT 0,
    support_uptime_pct REAL,

    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(session_date, round_number, round_start_unix)
);

CREATE INDEX IF NOT EXISTS idx_support_summary_session
    ON proximity_support_summary(session_date, round_number);

-- ===== REACTION METRICS (v4.2) =====
-- Per-engagement reaction timing after first incoming hit.
-- Captures return fire, dodge turn, and teammate support reaction windows.
CREATE TABLE IF NOT EXISTS proximity_reaction_metric (
    id SERIAL PRIMARY KEY,

    session_date DATE NOT NULL,
    round_number INTEGER NOT NULL,
    round_start_unix INTEGER DEFAULT 0,
    round_end_unix INTEGER DEFAULT 0,
    map_name VARCHAR(64) NOT NULL,

    engagement_id INTEGER NOT NULL,
    target_guid VARCHAR(32) NOT NULL,
    target_name VARCHAR(64) NOT NULL,
    target_team VARCHAR(10) NOT NULL,
    target_class VARCHAR(16) NOT NULL,

    outcome VARCHAR(20) NOT NULL,
    num_attackers INTEGER NOT NULL DEFAULT 0,

    return_fire_ms INTEGER,
    dodge_reaction_ms INTEGER,
    support_reaction_ms INTEGER,

    start_time_ms INTEGER NOT NULL DEFAULT 0,
    end_time_ms INTEGER NOT NULL DEFAULT 0,
    duration_ms INTEGER NOT NULL DEFAULT 0,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(session_date, round_number, round_start_unix, engagement_id, target_guid)
);

CREATE INDEX IF NOT EXISTS idx_reaction_session
    ON proximity_reaction_metric(session_date, round_number);
CREATE INDEX IF NOT EXISTS idx_reaction_target
    ON proximity_reaction_metric(target_guid);
CREATE INDEX IF NOT EXISTS idx_reaction_class
    ON proximity_reaction_metric(target_class);

-- ===== SAMPLE QUERIES =====

-- Who has the best crossfire coordination?
-- SELECT * FROM teamplay_leaderboard LIMIT 10;

-- Find best duo for a player
-- SELECT * FROM get_crossfire_partners('ABC123');

-- Get engagement paths on a specific map for visualization
-- SELECT engagement_id, target_name, outcome, position_path, attackers
-- FROM combat_engagement
-- WHERE map_name = 'goldrush' AND session_date = CURRENT_DATE;

-- Heatmap data for map overlay
-- SELECT grid_x, grid_y, total_kills, total_deaths
-- FROM map_kill_heatmap
-- WHERE map_name = 'goldrush';

-- Session crossfire summary
-- SELECT * FROM session_engagement_summary WHERE session_date = CURRENT_DATE;


-- ============================================================
-- DATA VOLUME ESTIMATES (v4)
-- ============================================================
--
-- combat_engagement: ~100/round × 10 rounds/day × 365 = 365,000/year
-- player_track (v4): ~20/round × 10 rounds/day × 365 = 73,000/year
-- player_teamplay_stats: ~200 unique players (aggregated)
-- map_kill_heatmap: ~50 cells × 20 maps = 1,000 rows
-- map_movement_heatmap: ~100 cells × 20 maps = 2,000 rows
-- crossfire_pairs: ~200 pairs (aggregated)
--
-- TOTAL: ~440,000 rows/year = ~80MB/year = FOREVER STORABLE
-- ============================================================
