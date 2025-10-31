-- ============================================================================
-- QUICK SQL DIAGNOSTICS - Check if weapon stats fix worked
-- ============================================================================
-- Run these queries against your etlegacy_production.db database
-- Copy/paste into SQLite or your database tool

-- ============================================================================
-- QUERY 1: Check latest sessions
-- ============================================================================
-- Shows your 5 most recent sessions
SELECT 
    id AS session_id,
    session_date,
    map_name,
    round_number,
    actual_time
FROM sessions 
ORDER BY session_date DESC 
LIMIT 5;

-- Expected: Should see your recent games
-- Note the session_id for next queries

-- ============================================================================
-- QUERY 2: Check weapon stats for a specific session
-- ============================================================================
-- Replace <session_id> with actual ID from Query 1
SELECT 
    COUNT(*) AS total_weapon_rows,
    COUNT(DISTINCT player_guid) AS unique_players,
    SUM(hits) AS total_hits,
    SUM(shots) AS total_shots,
    SUM(kills) AS total_kills,
    SUM(deaths) AS total_deaths,
    SUM(headshots) AS total_headshots,
    CASE 
        WHEN SUM(shots) > 0 
        THEN ROUND(SUM(hits) * 100.0 / SUM(shots), 2)
        ELSE 0 
    END AS overall_accuracy
FROM weapon_comprehensive_stats
WHERE session_id = <session_id>;

-- Expected BEFORE fix:
-- total_weapon_rows = 0 (PROBLEM!)

-- Expected AFTER fix:
-- total_weapon_rows > 0 (should be ~5-10 per player, so 50-100 for 10 players)
-- total_hits > 0
-- total_shots > 0

-- ============================================================================
-- QUERY 3: Check which sessions have weapon data
-- ============================================================================
-- Shows all recent sessions and whether they have weapon stats
SELECT 
    s.id,
    s.session_date,
    s.map_name,
    s.round_number,
    COUNT(w.id) AS weapon_rows,
    SUM(w.hits) AS total_hits,
    SUM(w.shots) AS total_shots
FROM sessions s
LEFT JOIN weapon_comprehensive_stats w ON w.session_id = s.id
WHERE s.session_date >= date('now', '-7 days')
GROUP BY s.id
ORDER BY s.session_date DESC;

-- Expected: 
-- Sessions from BEFORE fix: weapon_rows = 0
-- Sessions from AFTER fix: weapon_rows > 0

-- ============================================================================
-- QUERY 4: Check player comprehensive stats (main table)
-- ============================================================================
-- Replace <session_id> with actual ID
SELECT 
    player_name,
    kills,
    deaths,
    damage_given,
    dpm,
    accuracy,
    headshot_kills,
    gibs,
    revives_given,
    time_played_seconds
FROM player_comprehensive_stats
WHERE session_id = <session_id>
ORDER BY kills DESC
LIMIT 10;

-- Expected: Should see realistic values
-- DPM: 50-300 range
-- Accuracy: 10-50%
-- If all zeros → parser issue

-- ============================================================================
-- QUERY 5: Check weapon stats per player for latest session
-- ============================================================================
-- Replace <session_id> with actual ID
SELECT 
    player_name,
    weapon_name,
    kills,
    deaths,
    hits,
    shots,
    headshots,
    accuracy
FROM weapon_comprehensive_stats
WHERE session_id = <session_id>
ORDER BY player_name, kills DESC;

-- Expected: Multiple rows per player (one per weapon used)
-- If empty → weapon insert is still failing

-- ============================================================================
-- QUERY 6: Diagnostic - Check for missing required columns
-- ============================================================================
-- Check weapon_comprehensive_stats schema
PRAGMA table_info(weapon_comprehensive_stats);

-- Expected columns to exist:
-- - session_id (NOT NULL)
-- - session_date (NOT NULL) ← Agent added this
-- - map_name (NOT NULL) ← Agent added this  
-- - round_number (NOT NULL) ← Agent added this
-- - player_guid or player_name
-- - weapon_name
-- - kills, deaths, hits, shots, headshots, accuracy

-- ============================================================================
-- QUERY 7: Check for constraint violations (recent errors)
-- ============================================================================
-- This won't show in SQLite but useful concept:
-- If inserts are failing, check bot logs for:
-- "IntegrityError: NOT NULL constraint failed: weapon_comprehensive_stats.XXX"

-- ============================================================================
-- QUICK VERIFICATION (One Query)
-- ============================================================================
-- Run this single query to check if fix worked:
SELECT 
    'Latest Session Info' AS category,
    s.id AS session_id,
    s.map_name,
    COUNT(w.id) AS weapon_rows,
    COUNT(DISTINCT w.player_guid) AS players_with_weapons,
    SUM(w.kills) AS total_kills,
    CASE 
        WHEN COUNT(w.id) > 0 THEN '✅ WEAPON STATS EXIST'
        ELSE '❌ NO WEAPON STATS - FIX FAILED'
    END AS status
FROM sessions s
LEFT JOIN weapon_comprehensive_stats w ON w.session_id = s.id
WHERE s.id = (SELECT id FROM sessions ORDER BY session_date DESC LIMIT 1)
GROUP BY s.id;

-- Expected after fix: status = '✅ WEAPON STATS EXIST'
-- If status = '❌ NO WEAPON STATS - FIX FAILED', check bot logs

-- ============================================================================
-- COMPARISON QUERY - Before vs After Fix
-- ============================================================================
-- Shows sessions before and after fix timestamp
SELECT 
    s.session_date,
    s.map_name,
    COUNT(w.id) AS weapon_rows,
    CASE 
        WHEN COUNT(w.id) > 0 THEN 'Has Weapons ✅'
        ELSE 'Missing Weapons ❌'
    END AS status
FROM sessions s
LEFT JOIN weapon_comprehensive_stats w ON w.session_id = s.id
GROUP BY s.id
ORDER BY s.session_date DESC
LIMIT 10;

-- Expected: 
-- Older sessions: Missing Weapons ❌
-- Newer sessions (after fix): Has Weapons ✅

-- ============================================================================
-- DELETE & REIMPORT (if needed)
-- ============================================================================
-- If you need to delete a session and re-import it:

-- Step 1: Find the session
SELECT id, session_date, map_name, round_number 
FROM sessions 
WHERE session_date LIKE '2025-10-30%';

-- Step 2: Delete it (cascades to weapon_stats and player_stats)
-- DELETE FROM sessions WHERE id = <session_id>;  -- UNCOMMENT TO RUN

-- Step 3: Re-import via Discord bot
-- !import_file 2025-10-30-HHMMSS-mapname-round-N.txt

-- ============================================================================
-- NOTES
-- ============================================================================
-- 1. All queries assume your DB is named 'etlegacy_production.db'
-- 2. Replace <session_id> with actual values from Query 1
-- 3. If weapon_rows = 0 after fix, check bot logs for errors
-- 4. If you see errors about missing columns, tell AI agent which column
-- ============================================================================
