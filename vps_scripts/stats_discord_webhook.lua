--[[
    ET:Legacy Stats Discord Webhook Notifier
    =========================================

    This Lua script runs on the ET:Legacy game server and sends round metadata
    to a Discord webhook when rounds complete. This provides instant notification
    to the Slomix bot with accurate timing data (including surrender scenarios).

    Features:
    - Instant round-end notification (~1 sec vs 60s polling)
    - Accurate timing on surrenders (captures real end time)
    - Pause tracking
    - Team composition capture (who was on Axis/Allies)
    - Winner detection from game engine

    Installation:
    1. Copy this file to your ET:Legacy server's luascripts/ directory
    2. Add to your server's lua_modules cvar
    3. Configure the DISCORD_WEBHOOK_URL below

    Copyright (C) 2026 Slomix Project
    License: MIT
]]--

local modname = "stats_discord_webhook"
local version = "1.1.0"

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
    debug = false,

    -- Delay before sending webhook (seconds) - allows stats file to be written
    send_delay_seconds = 3
}

-- ============================================================================
-- STATE TRACKING
-- ============================================================================

local round_start_unix = 0
local round_end_unix = 0
local pause_start_time = 0
local total_pause_seconds = 0
local pause_count = 0
local last_gamestate = -1
local last_frame_time = 0
local scheduled_send_time = 0
local send_pending = false

-- Team data captured at round end
local axis_players_json = "[]"
local allies_players_json = "[]"
local axis_names = ""
local allies_names = ""

-- ET:Legacy gamestate constants
local GS_WARMUP = 0
local GS_WARMUP_COUNTDOWN = 1
local GS_PLAYING = 2
local GS_INTERMISSION = 3

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

    -- Build the Discord embed JSON
    -- Using embed fields for structured data that the bot can parse
    -- Note: Axis_JSON and Allies_JSON contain full player data for database storage
    local payload = string.format([[{
        "content": "STATS_READY",
        "embeds": [{
            "title": "Round Complete: %s R%d",
            "color": 3447003,
            "fields": [
                {"name": "Map", "value": "%s", "inline": true},
                {"name": "Round", "value": "%d", "inline": true},
                {"name": "Winner", "value": "%d", "inline": true},
                {"name": "Defender", "value": "%d", "inline": true},
                {"name": "Duration", "value": "%d sec", "inline": true},
                {"name": "Time Limit", "value": "%d min", "inline": true},
                {"name": "Pauses", "value": "%d (%d sec)", "inline": true},
                {"name": "End Reason", "value": "%s", "inline": true},
                {"name": "Start Unix", "value": "%d", "inline": true},
                {"name": "End Unix", "value": "%d", "inline": true},
                {"name": "Axis", "value": "%s", "inline": false},
                {"name": "Allies", "value": "%s", "inline": false},
                {"name": "Axis_JSON", "value": "%s", "inline": false},
                {"name": "Allies_JSON", "value": "%s", "inline": false}
            ],
            "footer": {"text": "Slomix Lua Webhook v%s"}
        }]
    }]],
        mapname, round,  -- title
        mapname, round, winner, defender,  -- first row
        actual_duration, time_limit,  -- second row
        pause_count, total_pause_seconds, end_reason,  -- third row
        round_start_unix, round_end_unix,  -- timestamps
        axis_names, allies_names,  -- human-readable team lists
        axis_players_json:gsub('"', '\\"'),  -- JSON escaped for embedding
        allies_players_json:gsub('"', '\\"'),  -- JSON escaped for embedding
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

    log(string.format("Sending webhook for %s R%d (winner=%d, duration=%ds, reason=%s)",
        mapname, round, winner, actual_duration, end_reason))
    log(string.format("Axis: %s", axis_names))
    log(string.format("Allies: %s", allies_names))

    os.execute(curl_cmd)

    et.G_Print(string.format("[%s] Sent round notification: %s R%d (Axis: %d, Allies: %d players)\n",
        modname, mapname, round,
        #(axis_names:gsub("[^,]", "") or "") + 1,
        #(allies_names:gsub("[^,]", "") or "") + 1))
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

    -- Round started (transition to PLAYING)
    if new_gamestate == GS_PLAYING and old_gamestate ~= GS_PLAYING then
        round_start_unix = os.time()
        total_pause_seconds = 0
        pause_count = 0
        send_pending = false
        axis_players_json = "[]"
        allies_players_json = "[]"
        axis_names = ""
        allies_names = ""
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

        -- Schedule webhook send after delay (allows stats file to be written)
        scheduled_send_time = et.trap_Milliseconds() + (configuration.send_delay_seconds * 1000)
        send_pending = true
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
                pause_count = pause_count + 1
                log(string.format("Pause detected at %d", level_time))
            end
        elseif pause_start_time > 0 then
            -- Pause ended
            local pause_duration = (level_time - pause_start_time) / 1000
            total_pause_seconds = total_pause_seconds + pause_duration
            log(string.format("Pause ended, duration: %d sec", pause_duration))
            pause_start_time = 0
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

    -- If game is already in progress (server restart mid-round), record start time
    if last_gamestate == GS_PLAYING then
        round_start_unix = os.time()
        log("Game already in progress, recording start time")
    end

    et.G_Print(string.format("[%s] v%s loaded - Discord webhook with team tracking\n",
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

function et_ShutdownGame(restart)
    log("Shutdown")
end

-- ============================================================================
-- END OF SCRIPT
-- ============================================================================
