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
local version = "1.6.2"

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
    log_gamestate_transitions = true,

    -- Delay before sending webhook (seconds)
    -- NOTE: Set to 0 because ET:Legacy reloads lua scripts during map transitions,
    -- which resets all state variables. Any delay risks losing the webhook.
    send_delay_seconds = 0,

    -- Optional local gametimes output (for fallback + auditing)
    gametimes_enabled = true,
    gametimes_dir = "/home/et/.etlegacy/legacy/gametimes",  -- absolute path to align with bot
    gametimes_write_on_failure_only = false,

    -- Spawn/death tracking (Oksii-inspired validation)
    spawn_tracking_enabled = true,
    spawn_check_interval_ms = 500,  -- throttle per-frame scanning

    -- Curl retry behavior (borrowed from Oksii)
    curl_connect_timeout = 2,
    curl_max_time = 10,
    curl_retry = 3,
    curl_retry_delay = 1,
    curl_retry_max_time = 15
}

-- ============================================================================
-- STATE TRACKING
-- ============================================================================

local round_start_unix = 0
local round_end_unix = 0
local round_end_ms = 0
local pause_start_time = 0
local pause_start_unix = 0       -- Unix timestamp when current pause started (v1.3.0)
local total_pause_seconds = 0
local pause_count = 0
local pause_events = {}          -- Array of {start_unix, end_unix, duration_sec} (v1.3.0)
local last_gamestate = -1
local last_frame_time = 0
local scheduled_send_time = 0
local send_pending = false
local round_started = false
local intermission_handled = false
local round_end_emitted = false
local send_in_progress = false
local last_sent_signature = ""

-- Warmup/intermission timing (v1.2.0)
local warmup_start_unix = 0      -- When warmup phase began
local warmup_seconds = 0         -- Total warmup duration for this round
local map_load_unix = 0          -- When this map instance loaded (for R1, equals warmup_start)

-- Team data captured at round end
local axis_players_json = "[]"
local allies_players_json = "[]"
local axis_names = ""
local allies_names = ""

-- Spawn/death tracking (per round)
local spawn_stats = {}
local client_guid_cache = {}
local client_name_cache = {}
local last_spawn_check_time = 0

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
-- Note: et.GS_PLAYING = 0 exists in the API (confirmed in official docs)
-- Using explicit constants for clarity and fallback safety
-- ET:Legacy gamestate values (from q_shared.h gamestate_t enum):
--   GS_INITIALIZE=-1, GS_PLAYING=0, GS_WARMUP_COUNTDOWN=1,
--   GS_WARMUP=2, GS_INTERMISSION=3, GS_WAITING_FOR_PLAYERS=4, GS_RESET=5
local GS_WARMUP = et.GS_WARMUP or 2           -- Warmup/ready-up state
local GS_WARMUP_COUNTDOWN = et.GS_WARMUP_COUNTDOWN or 1  -- Countdown before playing
local GS_PLAYING = et.GS_PLAYING or 0         -- Playing state
local GS_INTERMISSION = et.GS_INTERMISSION or 3  -- Intermission state

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

local last_gentity_error_time = 0

local function safe_gentity_get(clientNum, field)
    local ok, value = pcall(et.gentity_get, clientNum, field)
    if ok then
        return value
    end
    local now = (et.trap_Milliseconds and et.trap_Milliseconds()) or (os.time() * 1000)
    if now - last_gentity_error_time > 5000 then
        log(string.format("gentity_get failed client=%d field=%s err=%s", clientNum, field, tostring(value)))
        last_gentity_error_time = now
    end
    return nil
end

local function get_max_clients()
    local max_clients = tonumber(et.trap_Cvar_Get("sv_maxclients")) or 0
    if max_clients <= 0 or max_clients > 64 then
        max_clients = 64
    end
    return max_clients
end

local function strip_color_codes(text)
    if not text then return "" end
    return tostring(text):gsub("%^[0-9a-zA-Z]", "")
end

local function shell_escape(str)
    return "'" .. tostring(str or ""):gsub("'", "'\"'\"'") .. "'"
end

local function json_escape(str)
    return tostring(str or ""):gsub("\\", "\\\\"):gsub('"', '\\"')
end

local function get_gametimes_dir()
    local dir = configuration.gametimes_dir or "gametimes"
    if dir:sub(1, 1) == "/" then
        return dir
    end
    local fs_basepath = et.trap_Cvar_Get("fs_basepath")
    local fs_game = et.trap_Cvar_Get("fs_game")
    if fs_basepath and fs_game then
        return string.format("%s/%s/%s", fs_basepath, fs_game, dir)
    end
    return dir
end

local function ensure_dir(path)
    if not path or path == "" then
        return false
    end
    local ok = os.execute(string.format("mkdir -p %s", shell_escape(path)))
    if configuration.debug then
        log(string.format("ensure_dir: %s (ok=%s)", path, tostring(ok)))
    end
    return true
end

local function log_runtime_paths()
    local fs_basepath = et.trap_Cvar_Get("fs_basepath") or ""
    local fs_homepath = et.trap_Cvar_Get("fs_homepath") or ""
    local fs_game = et.trap_Cvar_Get("fs_game") or ""
    local resolved_gametimes = get_gametimes_dir()
    log(string.format("fs_basepath=%s fs_homepath=%s fs_game=%s", fs_basepath, fs_homepath, fs_game))
    log(string.format("gametimes_enabled=%s gametimes_dir=%s resolved=%s",
        tostring(configuration.gametimes_enabled),
        tostring(configuration.gametimes_dir),
        tostring(resolved_gametimes)))
end

local function write_gametime_file(payload_json, meta)
    if not configuration.gametimes_enabled then
        return false
    end

    local dir = get_gametimes_dir()
    ensure_dir(dir)

    local safe_map = (meta.mapname or "unknown"):gsub("[^%w_%-]", "_")
    local ts = (meta.round_end_unix and meta.round_end_unix > 0) and meta.round_end_unix or os.time()
    local server_ip = et.trap_Cvar_Get("net_ip") or ""
    local server_port = et.trap_Cvar_Get("net_port") or ""
    local match_id = tostring(ts)
    local filename = string.format("%s/gametime-%s-R%d-%d.json", dir, safe_map, meta.round or 0, ts)

    log(string.format("Writing gametime file: %s", filename))
    local f, err = io.open(filename, "w")
    if not f then
        log(string.format("Failed to write gametime file: %s", err or "unknown error"))
        return false
    end
    local spawn_stats_json = meta.spawn_stats_json or "[]"
    local meta_json = string.format(
        '{"map":"%s","round":%d,"round_start_unix":%d,"round_end_unix":%d,"actual_duration_seconds":%d,"warmup_seconds":%d,"pause_seconds":%d,"pause_count":%d,"server_ip":"%s","server_port":"%s","match_id":"%s","spawn_stats":%s}',
        json_escape(meta.mapname or "unknown"),
        tonumber(meta.round or 0),
        tonumber(meta.round_start_unix or 0),
        tonumber(ts),
        tonumber(meta.actual_duration_seconds or 0),
        tonumber(meta.warmup_seconds or 0),
        tonumber(meta.pause_seconds or 0),
        tonumber(meta.pause_count or 0),
        json_escape(server_ip),
        json_escape(server_port),
        json_escape(match_id),
        spawn_stats_json
    )
    local gametime_payload = string.format('{"meta":%s,"payload":%s}', meta_json, payload_json)
    f:write(gametime_payload)
    f:close()
    log(string.format("Gametime file written: %s", filename))
    return true
end

local function execute_curl_async(payload_json)
    if not payload_json or payload_json == "" then
        return false, "empty payload"
    end

    local temp_file = os.tmpname() .. ".json"
    local f, err = io.open(temp_file, "w")
    if not f then
        return false, "Failed to create temp file: " .. (err or "unknown")
    end
    f:write(payload_json)
    f:close()

    local curl_cmd = string.format(
        "curl -s -X POST -H 'Content-Type: application/json' --data-binary @%s %s " ..
        "--compressed --connect-timeout %d --max-time %d --retry %d --retry-delay %d --retry-max-time %d " ..
        "> /dev/null 2>&1 &",
        shell_escape(temp_file),
        shell_escape(configuration.discord_webhook_url),
        configuration.curl_connect_timeout,
        configuration.curl_max_time,
        configuration.curl_retry,
        configuration.curl_retry_delay,
        configuration.curl_retry_max_time
    )

    local ok, exit_type, exit_code = os.execute(curl_cmd)
    os.execute(string.format("sleep 15 && rm -f %s &", shell_escape(temp_file)))

    if ok == true or ok == 0 then
        return true, string.format(
            "curl started (ok=%s, type=%s, code=%s)",
            tostring(ok),
            tostring(exit_type),
            tostring(exit_code)
        )
    end
    return false, string.format(
        "curl failed (ok=%s, type=%s, code=%s)",
        tostring(ok),
        tostring(exit_type),
        tostring(exit_code)
    )
end

local function Info_ValueForKey(info, key)
    if not info or not key then return nil end
    local pattern = "\\" .. key .. "\\([^\\]*)"
    local value = string.match(info, pattern)
    return value
end

local function get_client_guid(clientNum)
    local userinfo = et.trap_GetUserinfo(clientNum)
    if not userinfo or userinfo == "" then
        return ""
    end

    local guid = Info_ValueForKey(userinfo, "cl_guid")
    if guid and guid ~= "" then
        return guid
    end

    guid = Info_ValueForKey(userinfo, "guid")
    if guid and guid ~= "" then
        return guid
    end

    return ""
end

local function get_client_name(clientNum)
    local name = safe_gentity_get(clientNum, "pers.netname") or "unknown"
    return strip_color_codes(name)
end

local function ensure_spawn_entry(guid, name)
    if not guid or guid == "" then return nil end
    if not spawn_stats[guid] then
        spawn_stats[guid] = {
            guid = guid:sub(1, 32),
            name = name or "unknown",
            spawn_count = 0,
            death_count = 0,
            dead_time_ms = 0,
            max_dead_ms = 0,
            last_death_ms = 0,
            last_spawn_ms = 0,
        }
    else
        if name and name ~= "" then
            spawn_stats[guid].name = name
        end
    end
    return spawn_stats[guid]
end

local function reset_spawn_tracking()
    spawn_stats = {}
    client_guid_cache = {}
    client_name_cache = {}
    last_spawn_check_time = 0
end

-- ============================================================================
-- TEAM DATA COLLECTION
-- ============================================================================

local function collect_team_data()
    local axis_players = {}
    local allies_players = {}

    local max_clients = get_max_clients()
    for clientNum = 0, max_clients - 1 do
        -- Check if player is connected
        local connected = safe_gentity_get(clientNum, "pers.connected")
        if connected == CON_CONNECTED then
            local guid = get_client_guid(clientNum)
            local name = safe_gentity_get(clientNum, "pers.netname") or "unknown"
            local team = tonumber(safe_gentity_get(clientNum, "sess.sessionTeam")) or 0

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
-- SPAWN TRACKING (Oksii-inspired)
-- ============================================================================

local function track_spawns(levelTime)
    if not configuration.spawn_tracking_enabled then
        return
    end
    if last_spawn_check_time > 0 then
        local delta = levelTime - last_spawn_check_time
        if delta < (configuration.spawn_check_interval_ms or 500) then
            return
        end
    end
    last_spawn_check_time = levelTime

    local max_clients = get_max_clients()
    for clientNum = 0, max_clients - 1 do
        local connected = safe_gentity_get(clientNum, "pers.connected")
        if connected == CON_CONNECTED then
            local team = tonumber(safe_gentity_get(clientNum, "sess.sessionTeam")) or 0
            if team == TEAM_AXIS or team == TEAM_ALLIES then
                local guid = client_guid_cache[clientNum]
                if not guid or guid == "" then
                    guid = get_client_guid(clientNum)
                    client_guid_cache[clientNum] = guid
                end
                if guid and guid ~= "" then
                    local name = client_name_cache[clientNum]
                    if not name or name == "" then
                        name = get_client_name(clientNum)
                        client_name_cache[clientNum] = name
                    end
                    local entry = ensure_spawn_entry(guid, name)
                    if entry then
                        local spawn_ms = tonumber(safe_gentity_get(clientNum, "pers.lastSpawnTime")) or 0
                        if spawn_ms > 0 and spawn_ms ~= entry.last_spawn_ms then
                            entry.spawn_count = entry.spawn_count + 1
                            if entry.last_death_ms > 0 and spawn_ms >= entry.last_death_ms then
                                local dead_ms = spawn_ms - entry.last_death_ms
                                if dead_ms >= 0 then
                                    entry.dead_time_ms = entry.dead_time_ms + dead_ms
                                    if dead_ms > (entry.max_dead_ms or 0) then
                                        entry.max_dead_ms = dead_ms
                                    end
                                end
                                entry.last_death_ms = 0
                            end
                            entry.last_spawn_ms = spawn_ms
                        end
                    end
                end
            end
        end
    end
end

local function build_spawn_stats()
    local list = {}
    local total_spawns = 0
    local total_deaths = 0
    local total_dead_seconds = 0
    local max_respawn_seconds = 0
    local tracked = 0

    for guid, entry in pairs(spawn_stats) do
        if entry.spawn_count > 0 or entry.death_count > 0 then
            tracked = tracked + 1
            local dead_ms = entry.dead_time_ms or 0
            if entry.last_death_ms and entry.last_death_ms > 0 and round_end_ms > entry.last_death_ms then
                dead_ms = dead_ms + (round_end_ms - entry.last_death_ms)
            end
            local dead_seconds = math.floor(dead_ms / 1000)
            local avg_respawn = 0
            if entry.death_count and entry.death_count > 0 then
                avg_respawn = math.floor(dead_seconds / entry.death_count)
            end
            local max_respawn = math.floor((entry.max_dead_ms or 0) / 1000)

            total_spawns = total_spawns + (entry.spawn_count or 0)
            total_deaths = total_deaths + (entry.death_count or 0)
            total_dead_seconds = total_dead_seconds + dead_seconds
            if max_respawn > max_respawn_seconds then
                max_respawn_seconds = max_respawn
            end

            table.insert(list, {
                guid = entry.guid,
                name = entry.name or "unknown",
                spawns = entry.spawn_count or 0,
                deaths = entry.death_count or 0,
                dead_seconds = dead_seconds,
                avg_respawn = avg_respawn,
                max_respawn = max_respawn
            })
        end
    end

    local avg_respawn_seconds = 0
    if total_deaths > 0 then
        avg_respawn_seconds = math.floor(total_dead_seconds / total_deaths)
    end

    local summary = string.format("Players:%d | Spawns:%d | AvgRespawn:%ds | MaxRespawn:%ds",
        tracked, total_spawns, avg_respawn_seconds, max_respawn_seconds)

    -- Build JSON array
    if #list == 0 then
        return "[]", summary
    end

    local parts = {}
    for _, s in ipairs(list) do
        table.insert(parts, string.format(
            '{"guid":"%s","name":"%s","spawns":%d,"deaths":%d,"dead_seconds":%d,"avg_respawn":%d,"max_respawn":%d}',
            json_escape(s.guid),
            json_escape(s.name),
            s.spawns,
            s.deaths,
            s.dead_seconds,
            s.avg_respawn,
            s.max_respawn
        ))
    end

    return "[" .. table.concat(parts, ",") .. "]", summary
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
    if g_current == 0 or g_current == 2 then
        return 2
    end
    if g_current ~= 1 then
        log(string.format("Unexpected g_currentRound=%s, defaulting to R1", tostring(g_current)))
    end
    return 1
end

local function count_names(name_list)
    if not name_list or name_list == "" or name_list == "(none)" then
        return 0
    end
    local _, commas = tostring(name_list):gsub(",", "")
    return commas + 1
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

local function format_timelimit_minutes(value)
    local numeric = tonumber(value) or 0
    if numeric < 0 then
        numeric = 0
    end

    local rounded = math.floor(numeric + 0.5)
    if math.abs(numeric - rounded) < 0.001 then
        return tostring(rounded)
    end

    local text = string.format("%.3f", numeric)
    text = text:gsub("0+$", "")
    text = text:gsub("%.$", "")
    return text
end

local function get_end_reason()
    local time_limit = get_time_limit()
    local actual_time = round_end_unix - round_start_unix
    local time_limit_seconds = math.floor(time_limit * 60 + 0.5)

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

    if send_in_progress then
        log("Webhook send already in progress, skipping")
        return
    end
    send_in_progress = true

    local ok_send, err = pcall(function()
        local mapname = get_mapname()
        local round = get_current_round()
        local winner = get_winner_team()
        local defender = get_defender_team()
        local actual_duration = math.floor(round_end_unix - round_start_unix - total_pause_seconds)
        if actual_duration < 0 then
            actual_duration = 0
        end
        local end_reason = get_end_reason()
        local time_limit = get_time_limit()
        local time_limit_display = format_timelimit_minutes(time_limit)
        local surrendering_team = get_surrender_team()

        -- v1.6.2: Timelimit sanity check — a round CANNOT exceed the timelimit.
        -- If it does, the post-map_restart warmup was included in round_start_unix
        -- (gamestate cvar reads GS_PLAYING before engine warmup completes).
        -- Correct by shifting start time forward and attributing excess to warmup.
        local time_limit_seconds = math.floor(time_limit * 60 + 0.5)
        et.G_Print(string.format("[stats_discord_webhook] timelimit raw=%s seconds=%s\n", tostring(time_limit), tostring(time_limit_seconds)))
        if time_limit_seconds > 0 and actual_duration > time_limit_seconds then
            local overcounting = actual_duration - time_limit_seconds
            log(string.format(
                "Duration %ds exceeds timelimit %ds by %ds — warmup correction applied (v1.6.2)",
                actual_duration, time_limit_seconds, overcounting
            ))
            warmup_seconds = warmup_seconds + overcounting
            round_start_unix = round_start_unix + overcounting
            actual_duration = time_limit_seconds
        end

        log(string.format(
            "Timelimit raw=%s type=%s display=%s",
            tostring(time_limit),
            type(time_limit),
            tostring(time_limit_display)
        ))

        -- Deduplicate sends (same map/round/end_time)
        local signature = nil
        if round_end_unix and round_end_unix > 0 then
            signature = string.format("%s:%d:%d", mapname, round, round_end_unix)
            if signature == last_sent_signature then
                log(string.format("Duplicate webhook detected (%s), skipping", signature))
                return
            end
        end

        -- Update match score based on winner
        update_match_score(winner)

        -- Spawn tracking summary + JSON (per-player)
        local spawn_stats_json, spawn_summary = build_spawn_stats()

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
            "description": "Timing: Playtime (no pauses) · Warmup · Wall-clock",
            "color": 3447003,
            "fields": [
                {"name": "Map", "value": "%s", "inline": true},
                {"name": "Round", "value": "%d", "inline": true},
                {"name": "Winner", "value": "%d", "inline": true},
                {"name": "Defender", "value": "%d", "inline": true},
                {"name": "Lua_Playtime", "value": "%d sec", "inline": true},
                {"name": "Lua_Timelimit", "value": "%s min", "inline": true},
                {"name": "Lua_Pauses", "value": "%d (%d sec)", "inline": true},
                {"name": "Lua_EndReason", "value": "%s", "inline": true},
                {"name": "Lua_Warmup", "value": "%d sec", "inline": true},
                {"name": "Lua_WarmupStart", "value": "%d", "inline": true},
                {"name": "Lua_RoundStart", "value": "%d", "inline": true},
                {"name": "Lua_RoundEnd", "value": "%d", "inline": true},
                {"name": "Lua_SurrenderTeam", "value": "%d", "inline": true},
                {"name": "Lua_SurrenderCaller", "value": "%s", "inline": true},
                {"name": "Lua_SurrenderCallerName", "value": "%s", "inline": true},
                {"name": "Lua_AxisScore", "value": "%d", "inline": true},
                {"name": "Lua_AlliesScore", "value": "%d", "inline": true},
                {"name": "Axis_JSON", "value": "%s", "inline": false},
                {"name": "Allies_JSON", "value": "%s", "inline": false},
                {"name": "Lua_Pauses_JSON", "value": "%s", "inline": false},
                {"name": "Lua_SpawnSummary", "value": "%s", "inline": false}
            ],
            "footer": {"text": "Slomix Lua Webhook v%s"}
        }]
    }]],
            mapname, round,  -- title
            mapname, round, winner, defender,  -- first row
            actual_duration, time_limit_display,  -- second row
            pause_count, math.floor(total_pause_seconds), end_reason,  -- third row
            warmup_seconds,  -- warmup duration
            warmup_start_unix,  -- WarmupStart
            round_start_unix, round_end_unix,  -- RoundStart, RoundEnd
            surrendering_team,  -- Which team surrendered (v1.4.0)
            surrender_vote.caller_guid,  -- GUID of surrender caller (v1.4.0)
            safe_surrender_name,  -- Name of surrender caller (v1.4.0)
            match_score.axis_wins,  -- Axis round wins (v1.4.0)
            match_score.allies_wins,  -- Allies round wins (v1.4.0)
            axis_players_json:gsub('"', '\\"'),  -- JSON escaped for embedding
            allies_players_json:gsub('"', '\\"'),  -- JSON escaped for embedding
            pause_events_json:gsub('"', '\\"'),  -- Pause events JSON (v1.3.0)
            spawn_summary:gsub('"', '\\"'),
            version  -- footer
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
        log(string.format("Spawn summary: %s", spawn_summary))

        local gametime_meta = {
            mapname = mapname,
            round = round,
            round_end_unix = round_end_unix,
            round_start_unix = round_start_unix,
            actual_duration_seconds = actual_duration,
            warmup_seconds = warmup_seconds,
            pause_seconds = total_pause_seconds,
            pause_count = pause_count,
            time_limit_minutes = time_limit,
            spawn_stats_json = spawn_stats_json
        }

        local wrote = false
        if configuration.gametimes_enabled and not configuration.gametimes_write_on_failure_only then
            wrote = write_gametime_file(payload, gametime_meta)
            if not wrote then
                log("Gametime pre-write failed (continuing with webhook send)")
            end
        end

        local ok, msg = execute_curl_async(payload)
        if not ok then
            log(string.format("Webhook send failed: %s", msg or "unknown error"))
        else
            log(string.format("Webhook send started: %s", msg or "ok"))
        end

        if configuration.gametimes_enabled and configuration.gametimes_write_on_failure_only and not ok then
            wrote = write_gametime_file(payload, gametime_meta) or wrote
        end

        if signature and (ok or wrote) then
            last_sent_signature = signature
        end

        local axis_count = count_names(axis_names)
        local allies_count = count_names(allies_names)

        et.G_Print(string.format("[%s] Sent round notification: %s R%d (Axis: %d, Allies: %d players) Score: %d-%d\n",
            modname, mapname, round,
            axis_count,
            allies_count,
            match_score.axis_wins, match_score.allies_wins))

        -- Reset surrender vote state after sending (for next round)
        reset_surrender_vote()
    end)

    send_in_progress = false
    if not ok_send then
        log(string.format("Webhook payload/send crashed: %s", tostring(err)))
    end
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

    if configuration.log_gamestate_transitions then
        log(string.format(
            "Gamestate transition: %s -> %s (round_started=%s, intermission_handled=%s, emitted=%s)",
            tostring(old_gamestate),
            tostring(new_gamestate),
            tostring(round_started),
            tostring(intermission_handled),
            tostring(round_end_emitted)
        ))
    end

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
        round_end_ms = 0
        round_end_emitted = false

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
        reset_spawn_tracking()
        reset_surrender_vote()   -- Reset surrender vote for new round (v1.4.0)
        log(string.format("Round started at %d", round_start_unix))
        intermission_handled = false
    end

    -- Round end is handled in et_RunFrame with an intermission flag
    -- (mirrors c0rnp0rn7.lua pattern for reliability).
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
                #pause_events, math.floor(pause_duration), math.floor(total_pause_seconds)))
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
    reset_spawn_tracking()

    -- Check for new map and reset score if needed (v1.4.0)
    reset_match_score_if_new_map()

    -- Initialize timing based on current gamestate
    -- v1.6.2: For map_restart (restart=1, R2 in stopwatch), the gamestate cvar
    -- may read GS_PLAYING before the engine finishes warmup. The round_start_unix
    -- recorded here will be too early by the warmup duration (~15-40s), causing
    -- overcounting that is corrected in send_webhook() via timelimit cap.
    local is_restart = (tonumber(restart) == 1)

    if last_gamestate == GS_PLAYING and is_restart then
        -- map_restart from countdown→playing (R2 start, or R1 after warmup).
        -- GS_PLAYING is correct, but os.time() here captures the Lua init moment
        -- which may be ~15-40s before the engine's timelimit clock starts
        -- (engine initialization gap). Corrected in send_webhook timelimit cap.
        warmup_start_unix = os.time()
        round_start_unix = os.time()
        warmup_seconds = 0
        log(string.format("Map restart -> GS_PLAYING, tracking from %d", warmup_start_unix))
    elseif last_gamestate == GS_PLAYING then
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

    log_runtime_paths()

    if configuration.discord_webhook_url == "REPLACE_WITH_YOUR_WEBHOOK_URL" then
        et.G_Print(string.format("[%s] WARNING: Webhook URL not configured!\n", modname))
    end
end

function et_RunFrame(levelTime)
    -- Check for gamestate changes
    local gamestate = tonumber(et.trap_Cvar_Get("gamestate"))
    handle_gamestate_change(gamestate)

    -- Fallback: detect round start reliably (even if gamestate transition is missed)
    if gamestate == GS_PLAYING and not round_started then
        round_start_unix = os.time()
        round_end_ms = 0
        round_end_emitted = false

        if warmup_start_unix > 0 then
            warmup_seconds = round_start_unix - warmup_start_unix
            log(string.format("Warmup ended, duration: %d sec (fallback)", warmup_seconds))
        else
            warmup_seconds = 0
        end

        total_pause_seconds = 0
        pause_count = 0
        pause_events = {}
        pause_start_unix = 0
        send_pending = false
        axis_players_json = "[]"
        allies_players_json = "[]"
        axis_names = ""
        allies_names = ""
        reset_spawn_tracking()
        reset_surrender_vote()
        intermission_handled = false
        round_started = true
        log(string.format("Round started at %d (fallback)", round_start_unix))
    elseif gamestate ~= GS_PLAYING then
        round_started = false
    end

    -- Round ended (intermission reached) - use same pattern as c0rnp0rn7.lua
    if gamestate == GS_INTERMISSION and not intermission_handled and not round_end_emitted then
        round_end_unix = os.time()
        round_end_ms = et.trap_Milliseconds()
        log(string.format("Round ended at %d (duration: %d sec)",
            round_end_unix, round_end_unix - round_start_unix))

        -- Collect team data NOW before players disconnect
        local axis, allies = collect_team_data()
        axis_players_json = format_player_json(axis)
        allies_players_json = format_player_json(allies)
        axis_names = format_player_names(axis)
        allies_names = format_player_names(allies)

        log(string.format("Teams captured - Axis: %d, Allies: %d", #axis, #allies))

        if configuration.send_delay_seconds <= 0 then
            send_webhook()
        else
            scheduled_send_time = et.trap_Milliseconds() + (configuration.send_delay_seconds * 1000)
            send_pending = true
        end

        intermission_handled = true
        round_end_emitted = true
    end

    -- Detect pauses (optional feature)
    if gamestate == GS_PLAYING then
        detect_pause(levelTime)
        track_spawns(levelTime)
    end

    -- Send scheduled webhook
    if send_pending and levelTime >= scheduled_send_time then
        send_pending = false
        send_webhook()
    end
end

-- ============================================================================
-- SPAWN TRACKING CALLBACKS
-- ============================================================================

function et_ClientUserinfoChanged(clientNum)
    if not configuration.spawn_tracking_enabled then
        return 0
    end
    local guid = get_client_guid(clientNum)
    if not guid or guid == "" then
        return 0
    end
    local name = get_client_name(clientNum)
    client_guid_cache[clientNum] = guid
    client_name_cache[clientNum] = name
    ensure_spawn_entry(guid, name)
    return 0
end

function et_Obituary(target, attacker, meansOfDeath)
    if not configuration.spawn_tracking_enabled then
        return 0
    end
    local connected = safe_gentity_get(target, "pers.connected")
    if connected ~= CON_CONNECTED then
        return 0
    end
    local team = tonumber(safe_gentity_get(target, "sess.sessionTeam")) or 0
    if team ~= TEAM_AXIS and team ~= TEAM_ALLIES then
        return 0
    end
    local guid = client_guid_cache[target] or get_client_guid(target)
    if not guid or guid == "" then
        return 0
    end
    client_guid_cache[target] = guid
    local name = client_name_cache[target] or get_client_name(target)
    client_name_cache[target] = name
    local entry = ensure_spawn_entry(guid, name)
    if entry then
        local death_ms = et.trap_Milliseconds()
        if death_ms and death_ms > 0 then
            entry.death_count = entry.death_count + 1
            entry.last_death_ms = death_ms
        end
    end
    return 0
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
            local connected = safe_gentity_get(clientNum, "pers.connected")
            if connected ~= CON_CONNECTED then
                return 0  -- Invalid client, skip tracking
            end

            -- Capture who called the surrender vote
            local guid = get_client_guid(clientNum)
            local name = safe_gentity_get(clientNum, "pers.netname") or "unknown"
            local team = tonumber(safe_gentity_get(clientNum, "sess.sessionTeam")) or 0

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
    local gamestate = tonumber(et.trap_Cvar_Get("gamestate")) or -1
    local restart_mode = tonumber(restart or 0)
    local allow_restart_emit = restart_mode == 0 or restart_mode == 1

    -- Fallback for maps that transition before a stable GS_INTERMISSION frame.
    -- c0rnp0rn uses a similar shutdown fallback for late-round persistence.
    if allow_restart_emit and (round_start_unix or 0) > 0 and not round_end_emitted then
        local now_unix = os.time()
        local elapsed = now_unix - (round_start_unix or 0)
        if elapsed < 3 then
            log(string.format(
                "Shutdown fallback skipped (elapsed too small: %ds, gamestate=%d)",
                elapsed,
                gamestate
            ))
            return
        end

        round_end_unix = os.time()
        round_end_ms = (et.trap_Milliseconds and et.trap_Milliseconds()) or 0

        local axis, allies = collect_team_data()
        axis_players_json = format_player_json(axis)
        allies_players_json = format_player_json(allies)
        axis_names = format_player_names(axis)
        allies_names = format_player_names(allies)

        log(string.format(
            "Shutdown fallback emit: %s R%d (gamestate=%d, restart=%d, duration=%d sec)",
            get_mapname(),
            get_current_round(),
            gamestate,
            restart_mode,
            elapsed
        ))

        send_webhook()
        intermission_handled = true
        round_end_emitted = true
        return
    end

    log(string.format(
        "Shutdown (restart=%d, round_started=%s, emitted=%s, gamestate=%d)",
        tonumber(restart or -1),
        tostring(round_started),
        tostring(round_end_emitted),
        gamestate
    ))
end

-- ============================================================================
-- END OF SCRIPT
-- ============================================================================
