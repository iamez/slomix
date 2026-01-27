--[[
    Slomix Stats Discord Webhook (stats_discord_webhook.lua)
    =========================================================

    This Lua script runs on the ET:Legacy game server and sends round metadata
    to a Discord webhook when rounds complete. This provides instant notification
    to the Slomix bot with accurate timing data (including surrender scenarios).

    IMPORTANT: TIMING DATA SOURCES
    ------------------------------
    There are TWO Lua scripts that capture timing:

    1. oksii-game-stats-web.lua (c0rnp0rn) - Writes stats files
       - Has surrender timing bug (shows full map time on surrender)
       - Provides per-player stats (kills, deaths, time_played, etc.)
       - Stored in: rounds table, player_comprehensive_stats table

    2. THIS SCRIPT (stats_discord_webhook.lua) - Real-time webhook
       - Accurate timing via gamestate hooks (no surrender bug)
       - Captures team composition at exact round end
       - Stored in: lua_round_teams table
       - All fields prefixed with "Lua_" to distinguish from stats file

    See: docs/reference/TIMING_DATA_SOURCES.md for full documentation

    Features:
    - Instant round-end notification (~1 sec vs 60s polling)
    - Accurate timing on surrenders (captures real end time)
    - Pause tracking with timestamps (v1.3.0)
    - Warmup duration tracking (v1.2.0)
    - Team composition capture (who was on Axis/Allies)
    - Winner detection from game engine
    - Timing legend in embed (v1.3.0)
    - Surrender vote tracking (v1.4.0) - who called, which team
    - Match score tracking (v1.4.0) - running Axis/Allies win count

    Webhook Fields (v1.4.0):
    - Lua_Playtime: Actual play time (excludes pauses)
    - Lua_Warmup: Pre-round warmup duration
    - Lua_Pauses: Count and total seconds
    - Lua_Pauses_JSON: Detailed pause events [{n,start,end,sec},...] (v1.3.0)
    - Lua_WarmupStart/Lua_WarmupEnd: Warmup phase timestamps (v1.3.0)
    - Lua_RoundStart/Lua_RoundEnd: Round gameplay timestamps
    - Lua_SurrenderCaller: GUID of player who called surrender vote (v1.4.0)
    - Lua_SurrenderCallerName: Name of player who called surrender vote (v1.4.0)
    - Lua_SurrenderTeam: Team that surrendered (1=Axis, 2=Allies) (v1.4.0)
    - Lua_AxisScore/Lua_AlliesScore: Running match score (v1.4.0)
    - Legend in embed description explaining timing values

    Bot-Side Computations:
    - Intermission = R2.Lua_WarmupStart - R1.Lua_RoundEnd
    - Map total playtime = R1.Lua_Playtime + R2.Lua_Playtime
    - Session totals = Sum across all rounds

    Installation:
    1. Copy this file to your ET:Legacy server's luascripts/ directory
    2. Add to your server's lua_modules cvar
    3. Configure the DISCORD_WEBHOOK_URL below
    4. Run migrations: tools/migrations/003_add_warmup_columns.sql
                       tools/migrations/004_add_pause_events.sql (v1.3.0)
                       migrations/005_add_surrender_and_score.sql (v1.4.0)

    Copyright (C) 2026 Slomix Project
    License: MIT
]]--

local modname = "stats_discord_webhook"
local version = "1.4.2"

-- ============================================================================
-- CONFIGURATION - EDIT THESE VALUES
-- ============================================================================

local configuration = {
    -- Discord webhook URL - create one in your control channel
    -- Format: https://discord.com/api/webhooks/WEBHOOK_ID/WEBHOOK_TOKEN
    discord_webhook_url = "https://discord.com/api/webhooks/1463967551049437356/TlHYbosz59fxmgXrkPiqZdwMmtqewqQM1GK6vQ8tC9Ui8yHCQssMoW6vfDSFOM0Q-bOv",

    -- Enable/disable the webhook notifications
    enabled = true,

    -- Enable debug logging to server console
    debug = true,

    -- Delay before sending webhook (seconds)
    -- NOTE: Set to 0 because ET:Legacy reloads lua scripts during map transitions,
    -- which resets all state variables. Any delay risks losing the webhook.
    send_delay_seconds = 0
}

-- ============================================================================
-- STATE TRACKING
-- ============================================================================

local round_start_unix = 0
local round_end_unix = 0
local pause_start_time = 0
local pause_start_unix = 0       -- Unix timestamp when current pause started (v1.3.0)
local total_pause_seconds = 0
local pause_count = 0
local pause_events = {}          -- Array of {start_unix, end_unix, duration_sec} (v1.3.0)
local last_gamestate = -1
local last_frame_time = 0
local scheduled_send_time = 0
local send_pending = false

-- Warmup/intermission timing (v1.2.0)
local warmup_start_unix = 0      -- When warmup phase began
local warmup_seconds = 0         -- Total warmup duration for this round
local map_load_unix = 0          -- When this map instance loaded (for R1, equals warmup_start)

-- Team data captured at round end
local axis_players_json = "[]"
local allies_players_json = "[]"
local axis_names = ""
local allies_names = ""

-- Surrender vote tracking (v1.4.0)
local surrender_vote = {
    caller_guid = "",            -- GUID of player who called surrender
    caller_name = "",            -- Name of player who called surrender
    caller_team = 0,             -- Team of caller (1=Axis, 2=Allies)
    vote_time = 0,               -- Unix timestamp when vote was called
    active = false               -- Whether a surrender vote is currently active
}

-- Match score tracking (v1.4.0)
-- Persists across rounds within a map, reset on map change
local match_score = {
    axis_wins = 0,               -- Number of rounds won by Axis
    allies_wins = 0,             -- Number of rounds won by Allies
    current_map = ""             -- Track map changes to reset score
}

-- ET:Legacy gamestate constants
-- NOTE: Use et.GS_* constants from the ET:Legacy API, not hardcoded values!
-- Other scripts (c0rnp0rn7.lua, endstats.lua) use et.GS_INTERMISSION etc.
-- Hardcoded values may not match the actual engine values.
local GS_WARMUP = et.GS_WARMUP or 0
local GS_WARMUP_COUNTDOWN = et.GS_WARMUP_COUNTDOWN or 1
local GS_PLAYING = et.GS_PLAYING or 2
local GS_INTERMISSION = et.GS_INTERMISSION or 3

-- Connection state
local CON_CONNECTED = 2

-- Team constants
local TEAM_AXIS = 1
local TEAM_ALLIES = 2
local TEAM_SPECTATOR = 3

-- ============================================================================
-- UTILITY FUNCTIONS
-- ============================================================================

local function log(msg)
    if configuration.debug then
        et.G_Print(string.format("[%s] %s\n", modname, msg))
    end
end

local function Info_ValueForKey(info, key)
    if not info or not key then return nil end
    local pattern = "\\" .. key .. "\\([^\\]*)"
    local value = string.match(info, pattern)
    return value
end

-- ============================================================================
-- TEAM DATA COLLECTION
-- ============================================================================

local function collect_team_data()
    local axis_players = {}
    local allies_players = {}

    for clientNum = 0, 63 do  -- ET:Legacy max 64 players
        -- Check if player is connected
        local connected = et.gentity_get(clientNum, "pers.connected")
        if connected == CON_CONNECTED then
            local guid = et.gentity_get(clientNum, "pers.cl_guid") or ""
            local name = et.gentity_get(clientNum, "pers.netname") or "unknown"
            local team = tonumber(et.gentity_get(clientNum, "sess.sessionTeam")) or 0

            -- Clean the name (remove color codes for cleaner display)
            local clean_name = name:gsub("%^[0-9]", "")

            local player_data = {
                guid = guid:sub(1, 32),  -- First 32 chars of GUID
                name = clean_name
            }

            if team == TEAM_AXIS then
                table.insert(axis_players, player_data)
                log(string.format("Axis player: %s (%s)", clean_name, guid:sub(1,8)))
            elseif team == TEAM_ALLIES then
                table.insert(allies_players, player_data)
                log(string.format("Allies player: %s (%s)", clean_name, guid:sub(1,8)))
            end
        end
    end

    return axis_players, allies_players
end

local function format_player_names(players)
    local names = {}
    for _, p in ipairs(players) do
        table.insert(names, p.name)
    end
    if #names == 0 then
        return "(none)"
    end
    return table.concat(names, ", ")
end

local function format_player_json(players)
    -- JSON array format for database storage
    if #players == 0 then
        return "[]"
    end

    local parts = {}
    for _, p in ipairs(players) do
        -- Escape special characters for JSON
        local safe_name = p.name:gsub('\\', '\\\\'):gsub('"', '\\"')
        local safe_guid = p.guid:gsub('\\', '\\\\'):gsub('"', '\\"')
        table.insert(parts, string.format('{"guid":"%s","name":"%s"}', safe_guid, safe_name))
    end
    return "[" .. table.concat(parts, ",") .. "]"
end

local function format_pause_events_json()
    -- JSON array of pause events (v1.3.0)
    -- Format: [{"start":unix,"end":unix,"sec":duration}, ...]
    if #pause_events == 0 then
        return "[]"
    end

    local parts = {}
    for i, p in ipairs(pause_events) do
        table.insert(parts, string.format(
            '{"n":%d,"start":%d,"end":%d,"sec":%d}',
            i, p.start_unix, p.end_unix, p.duration_sec
        ))
    end
    return "[" .. table.concat(parts, ",") .. "]"
end

-- ============================================================================
-- GAME DATA EXTRACTION
-- ============================================================================

local function get_mapname()
    return et.trap_Cvar_Get("mapname") or "unknown"
end

local function get_current_round()
    -- g_currentRound: 0 means we're on second half, 1 means first half
    -- We want: 1 = first round, 2 = second round
    local g_current = tonumber(et.trap_Cvar_Get("g_currentRound")) or 1
    return (g_current == 0) and 2 or 1
end

local function get_winner_team()
    -- Read winner from CS_MULTI_MAPWINNER config string
    local config_str = et.trap_GetConfigstring(et.CS_MULTI_MAPWINNER)
    if not config_str or config_str == "" then
        return 0  -- Unknown
    end

    local winner = tonumber(Info_ValueForKey(config_str, "w"))
    if winner then
        return winner + 1  -- Convert 0-indexed to 1=Axis, 2=Allies
    end
    return 0
end

local function get_defender_team()
    -- Read defender from CS_MULTI_INFO config string
    local config_str = et.trap_GetConfigstring(et.CS_MULTI_INFO)
    if not config_str or config_str == "" then
        return 0
    end

    local defender = tonumber(Info_ValueForKey(config_str, "d"))
    if defender then
        return defender + 1  -- Convert to 1=Axis, 2=Allies
    end
    return 0
end

local function get_time_limit()
    return tonumber(et.trap_Cvar_Get("timelimit")) or 0
end

local function get_end_reason()
    local time_limit = get_time_limit()
    local actual_time = round_end_unix - round_start_unix
    local time_limit_seconds = time_limit * 60

    -- If a surrender vote was active and round ended early, it was surrender
    if surrender_vote.active and surrender_vote.caller_team > 0 then
        return "surrender"
    end

    -- If round ended significantly before time limit, it was surrender or objective
    if time_limit_seconds > 0 and actual_time < (time_limit_seconds * 0.9) then
        local winner = get_winner_team()
        if winner > 0 then
            return "objective"
        else
            return "surrender"
        end
    end

    return "time_expired"
end

-- ============================================================================
-- SURRENDER VOTE TRACKING (v1.4.0)
-- ============================================================================

local function reset_surrender_vote()
    surrender_vote.caller_guid = ""
    surrender_vote.caller_name = ""
    surrender_vote.caller_team = 0
    surrender_vote.vote_time = 0
    surrender_vote.active = false
end

local function get_surrender_team()
    -- If we tracked a surrender vote, return that team
    if surrender_vote.active and surrender_vote.caller_team > 0 then
        return surrender_vote.caller_team
    end

    -- Otherwise, determine from end_reason and winner
    local end_reason = get_end_reason()
    if end_reason == "surrender" then
        -- The losing team surrendered
        local winner = get_winner_team()
        if winner == TEAM_AXIS then
            return TEAM_ALLIES  -- Allies surrendered
        elseif winner == TEAM_ALLIES then
            return TEAM_AXIS    -- Axis surrendered
        end
    end

    return 0  -- Unknown
end

-- ============================================================================
-- MATCH SCORE TRACKING (v1.4.0)
-- ============================================================================

local function update_match_score(winner)
    if winner == TEAM_AXIS then
        match_score.axis_wins = match_score.axis_wins + 1
        log(string.format("Axis wins round! Score: Axis %d - %d Allies",
            match_score.axis_wins, match_score.allies_wins))
    elseif winner == TEAM_ALLIES then
        match_score.allies_wins = match_score.allies_wins + 1
        log(string.format("Allies wins round! Score: Axis %d - %d Allies",
            match_score.axis_wins, match_score.allies_wins))
    end
end

local function reset_match_score_if_new_map()
    local current_map = get_mapname()
    if current_map ~= match_score.current_map then
        match_score.axis_wins = 0
        match_score.allies_wins = 0
        match_score.current_map = current_map
        log(string.format("New map detected: %s - resetting score", current_map))
    end
end

-- ============================================================================
-- WEBHOOK SENDING
-- ============================================================================

local function send_webhook()
    if not configuration.enabled then
        log("Webhook disabled, skipping send")
        return
    end

    if configuration.discord_webhook_url == "REPLACE_WITH_YOUR_WEBHOOK_URL" then
        et.G_Print(string.format("[%s] ERROR: Discord webhook URL not configured!\n", modname))
        return
    end

    local mapname = get_mapname()
    local round = get_current_round()
    local winner = get_winner_team()
    local defender = get_defender_team()
    local actual_duration = round_end_unix - round_start_unix - total_pause_seconds
    local end_reason = get_end_reason()
    local time_limit = get_time_limit()
    local surrendering_team = get_surrender_team()

    -- Update match score based on winner
    update_match_score(winner)

    -- Build the Discord embed JSON
    -- Using embed fields for structured data that the bot can parse
    --
    -- NAMING CONVENTION (v1.2.0):
    -- All timing fields are prefixed to distinguish from stats file (oksii lua) data:
    --   "Lua_*" = Captured by THIS script (stats_discord_webhook.lua / Slomix)
    --   Stats file has its own: round_start_unix, round_end_unix, etc.
    --
    -- The Lua_ prefix makes it clear these come from real-time gamestate hooks,
    -- not from the stats file which has the surrender timing bug.
    --
    -- Format pause events for JSON field (v1.3.0)
    local pause_events_json = format_pause_events_json()

    -- Escape surrender caller name for JSON (v1.4.0)
    local safe_surrender_name = surrender_vote.caller_name:gsub('\\', '\\\\'):gsub('"', '\\"')

    local payload = string.format([[{
        "username": "ET:Legacy Stats",
        "content": "STATS_READY",
        "embeds": [{
            "title": "Round Complete: %s R%d",
            "description": "**Timing Legend:**\n• Playtime = actual gameplay (pauses excluded)\n• Warmup = waiting before round\n• Wall-clock = WarmupStart→RoundEnd",
            "color": 3447003,
            "fields": [
                {"name": "Map", "value": "%s", "inline": true},
                {"name": "Round", "value": "%d", "inline": true},
                {"name": "Winner", "value": "%d", "inline": true},
                {"name": "Defender", "value": "%d", "inline": true},
                {"name": "Lua_Playtime", "value": "%d sec", "inline": true},
                {"name": "Lua_Timelimit", "value": "%d min", "inline": true},
                {"name": "Lua_Pauses", "value": "%d (%d sec)", "inline": true},
                {"name": "Lua_EndReason", "value": "%s", "inline": true},
                {"name": "Lua_Warmup", "value": "%d sec", "inline": true},
                {"name": "Lua_WarmupStart", "value": "%d", "inline": true},
                {"name": "Lua_WarmupEnd", "value": "%d", "inline": true},
                {"name": "Lua_RoundStart", "value": "%d", "inline": true},
                {"name": "Lua_RoundEnd", "value": "%d", "inline": true},
                {"name": "Lua_SurrenderTeam", "value": "%d", "inline": true},
                {"name": "Lua_SurrenderCaller", "value": "%s", "inline": true},
                {"name": "Lua_SurrenderCallerName", "value": "%s", "inline": true},
                {"name": "Lua_AxisScore", "value": "%d", "inline": true},
                {"name": "Lua_AlliesScore", "value": "%d", "inline": true},
                {"name": "Axis", "value": "%s", "inline": false},
                {"name": "Allies", "value": "%s", "inline": false},
                {"name": "Axis_JSON", "value": "%s", "inline": false},
                {"name": "Allies_JSON", "value": "%s", "inline": false},
                {"name": "Lua_Pauses_JSON", "value": "%s", "inline": false}
            ],
            "footer": {"text": "Slomix Lua Webhook v%s"}
        }]
    }]],
        mapname, round,  -- title
        mapname, round, winner, defender,  -- first row
        actual_duration, time_limit,  -- second row
        pause_count, total_pause_seconds, end_reason,  -- third row
        warmup_seconds,  -- warmup duration
        warmup_start_unix, round_start_unix,  -- WarmupStart, WarmupEnd (=RoundStart)
        round_start_unix, round_end_unix,  -- RoundStart, RoundEnd
        surrendering_team,  -- Which team surrendered (v1.4.0)
        surrender_vote.caller_guid,  -- GUID of surrender caller (v1.4.0)
        safe_surrender_name,  -- Name of surrender caller (v1.4.0)
        match_score.axis_wins,  -- Axis round wins (v1.4.0)
        match_score.allies_wins,  -- Allies round wins (v1.4.0)
        axis_names, allies_names,  -- human-readable team lists
        axis_players_json:gsub('"', '\\"'),  -- JSON escaped for embedding
        allies_players_json:gsub('"', '\\"'),  -- JSON escaped for embedding
        pause_events_json:gsub('"', '\\"'),  -- Pause events JSON (v1.3.0)
        version  -- footer
    )

    -- Escape single quotes in payload for shell command
    payload = payload:gsub("'", "'\\''")

    -- Execute curl asynchronously (& at end) to avoid blocking game server
    local curl_cmd = string.format(
        "curl -s -X POST -H 'Content-Type: application/json' -d '%s' '%s' > /dev/null 2>&1 &",
        payload,
        configuration.discord_webhook_url
    )

    log(string.format("Sending webhook for %s R%d (winner=%d, playtime=%ds, warmup=%ds, pauses=%d, reason=%s)",
        mapname, round, winner, actual_duration, warmup_seconds, pause_count, end_reason))
    if surrender_vote.active then
        log(string.format("Surrender called by %s (team %d, guid %s)",
            surrender_vote.caller_name, surrender_vote.caller_team, surrender_vote.caller_guid:sub(1,8)))
    end
    log(string.format("Match score: Axis %d - %d Allies", match_score.axis_wins, match_score.allies_wins))
    if #pause_events > 0 then
        log(string.format("Pause events: %s", pause_events_json))
    end
    log(string.format("Axis: %s", axis_names))
    log(string.format("Allies: %s", allies_names))

    os.execute(curl_cmd)

    et.G_Print(string.format("[%s] Sent round notification: %s R%d (Axis: %d, Allies: %d players) Score: %d-%d\n",
        modname, mapname, round,
        #(axis_names:gsub("[^,]", "") or "") + 1,
        #(allies_names:gsub("[^,]", "") or "") + 1,
        match_score.axis_wins, match_score.allies_wins))

    -- Reset surrender vote state after sending (for next round)
    reset_surrender_vote()
end

-- ============================================================================
-- GAMESTATE HANDLING
-- ============================================================================

local function handle_gamestate_change(new_gamestate)
    if new_gamestate == last_gamestate then
        return
    end

    local old_gamestate = last_gamestate
    last_gamestate = new_gamestate

    -- Warmup started (transition to WARMUP or WARMUP_COUNTDOWN)
    -- This happens at map load (R1) or after intermission (R2)
    if (new_gamestate == GS_WARMUP or new_gamestate == GS_WARMUP_COUNTDOWN) then
        if old_gamestate == GS_INTERMISSION or old_gamestate == -1 then
            -- Fresh warmup start (coming from intermission or map load)
            warmup_start_unix = os.time()
            log(string.format("Warmup started at %d", warmup_start_unix))
        end
    end

    -- Round started (transition to PLAYING)
    if new_gamestate == GS_PLAYING and old_gamestate ~= GS_PLAYING then
        round_start_unix = os.time()

        -- Check for new map and reset score if needed (v1.4.0)
        reset_match_score_if_new_map()

        -- Calculate warmup duration
        if warmup_start_unix > 0 then
            warmup_seconds = round_start_unix - warmup_start_unix
            log(string.format("Warmup ended, duration: %d sec", warmup_seconds))
        else
            warmup_seconds = 0
        end

        total_pause_seconds = 0
        pause_count = 0
        pause_events = {}        -- Reset pause events array (v1.3.0)
        pause_start_unix = 0
        send_pending = false
        axis_players_json = "[]"
        allies_players_json = "[]"
        axis_names = ""
        allies_names = ""
        reset_surrender_vote()   -- Reset surrender vote for new round (v1.4.0)
        log(string.format("Round started at %d", round_start_unix))
    end

    -- Round ended (transition to INTERMISSION)
    -- This is the CRITICAL moment - captures accurate end time even on surrender!
    if new_gamestate == GS_INTERMISSION and old_gamestate == GS_PLAYING then
        round_end_unix = os.time()
        log(string.format("Round ended at %d (duration: %d sec)",
            round_end_unix, round_end_unix - round_start_unix))

        -- Collect team data NOW before players disconnect
        local axis, allies = collect_team_data()
        axis_players_json = format_player_json(axis)
        allies_players_json = format_player_json(allies)
        axis_names = format_player_names(axis)
        allies_names = format_player_names(allies)

        log(string.format("Teams captured - Axis: %d, Allies: %d", #axis, #allies))

        -- Send webhook immediately or schedule for later
        -- NOTE: Immediate send (delay=0) recommended because ET:Legacy reloads
        -- lua scripts during map transitions, resetting all state variables.
        if configuration.send_delay_seconds <= 0 then
            -- Send immediately
            send_webhook()
        else
            -- Schedule for later (may not work if scripts reload)
            scheduled_send_time = et.trap_Milliseconds() + (configuration.send_delay_seconds * 1000)
            send_pending = true
        end
    end
end

-- ============================================================================
-- PAUSE DETECTION (OPTIONAL)
-- ============================================================================

local function detect_pause(level_time)
    -- Simple pause detection: if frame delta is unusually large, game was paused
    -- This is a heuristic - ET:Legacy doesn't have explicit pause events
    if last_frame_time > 0 then
        local frame_delta = level_time - last_frame_time

        -- If more than 2 seconds between frames, consider it a pause
        if frame_delta > 2000 then
            if pause_start_time == 0 then
                pause_start_time = last_frame_time
                pause_start_unix = os.time()  -- Record when pause started (v1.3.0)
                pause_count = pause_count + 1
                log(string.format("Pause #%d detected at %d (unix: %d)",
                    pause_count, level_time, pause_start_unix))
            end
        elseif pause_start_time > 0 then
            -- Pause ended
            local pause_duration = (level_time - pause_start_time) / 1000
            local pause_end_unix = os.time()
            total_pause_seconds = total_pause_seconds + pause_duration

            -- Record this pause event (v1.3.0)
            table.insert(pause_events, {
                start_unix = pause_start_unix,
                end_unix = pause_end_unix,
                duration_sec = math.floor(pause_duration)
            })

            log(string.format("Pause #%d ended, duration: %d sec (total: %d sec)",
                #pause_events, pause_duration, total_pause_seconds))
            pause_start_time = 0
            pause_start_unix = 0
        end
    end

    last_frame_time = level_time
end

-- ============================================================================
-- ET:LEGACY CALLBACKS
-- ============================================================================

function et_InitGame(levelTime, randomSeed, restart)
    et.RegisterModname(string.format("%s %s", modname, version))

    -- Initialize state
    last_gamestate = tonumber(et.trap_Cvar_Get("gamestate")) or -1
    last_frame_time = levelTime
    map_load_unix = os.time()

    -- Check for new map and reset score if needed (v1.4.0)
    reset_match_score_if_new_map()

    -- Initialize timing based on current gamestate
    if last_gamestate == GS_PLAYING then
        -- Server restart mid-round - record start time, warmup already passed
        round_start_unix = os.time()
        warmup_seconds = 0
        warmup_start_unix = 0
        log("Game already in progress, recording start time")
    elseif last_gamestate == GS_WARMUP or last_gamestate == GS_WARMUP_COUNTDOWN then
        -- Map just loaded, in warmup
        warmup_start_unix = os.time()
        log(string.format("Map loaded in warmup, tracking from %d", warmup_start_unix))
    end

    et.G_Print(string.format("[%s] v%s loaded - Discord webhook with surrender tracking\n",
        modname, version))

    if configuration.discord_webhook_url == "REPLACE_WITH_YOUR_WEBHOOK_URL" then
        et.G_Print(string.format("[%s] WARNING: Webhook URL not configured!\n", modname))
    end
end

function et_RunFrame(levelTime)
    -- Check for gamestate changes
    local gamestate = tonumber(et.trap_Cvar_Get("gamestate"))
    handle_gamestate_change(gamestate)

    -- Detect pauses (optional feature)
    if gamestate == GS_PLAYING then
        detect_pause(levelTime)
    end

    -- Send scheduled webhook
    if send_pending and levelTime >= scheduled_send_time then
        send_pending = false
        send_webhook()
    end
end

-- ============================================================================
-- CLIENT COMMAND INTERCEPTION (v1.4.0)
-- Captures surrender vote caller information
-- ============================================================================

function et_ClientCommand(clientNum, command)
    -- Get the actual command being executed
    local cmd = et.trap_Argv(0)

    -- Track callvote surrender
    if cmd == "callvote" then
        local vote_type = et.trap_Argv(1)

        if vote_type == "surrender" then
            -- Validate client before accessing gentity fields
            -- This prevents errors when spectators or invalid clients call votes
            local connected = et.gentity_get(clientNum, "pers.connected")
            if connected ~= CON_CONNECTED then
                return 0  -- Invalid client, skip tracking
            end

            -- Capture who called the surrender vote
            local guid = et.gentity_get(clientNum, "pers.cl_guid") or ""
            local name = et.gentity_get(clientNum, "pers.netname") or "unknown"
            local team = tonumber(et.gentity_get(clientNum, "sess.sessionTeam")) or 0

            -- Clean the name (remove color codes)
            local clean_name = name:gsub("%^[0-9]", "")

            surrender_vote.caller_guid = guid:sub(1, 32)
            surrender_vote.caller_name = clean_name
            surrender_vote.caller_team = team
            surrender_vote.vote_time = os.time()
            surrender_vote.active = true

            local team_name = "Unknown"
            if team == TEAM_AXIS then
                team_name = "Axis"
            elseif team == TEAM_ALLIES then
                team_name = "Allies"
            end

            log(string.format("SURRENDER VOTE called by %s (%s, team %s, guid %s)",
                clean_name, team_name, team, guid:sub(1, 8)))

            et.G_Print(string.format("[%s] Surrender vote called by %s (%s)\n",
                modname, clean_name, team_name))
        end
    end

    -- Return 0 to pass through (don't intercept the command)
    return 0
end

function et_ShutdownGame(restart)
    log("Shutdown")
end

-- ============================================================================
-- END OF SCRIPT
-- ============================================================================
