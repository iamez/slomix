/**
 * Admin Panel - Reactor Overview
 * Local-only manual overrides with lightweight auto health checks.
 */

import { API_BASE, fetchJSON, escapeHtml } from './utils.js';

const OVERRIDE_KEY = 'slomix_admin_overrides_v1';
const CHECKLIST_KEY = 'slomix_admin_checklist_v1';
const STORY_MODE_KEY = 'slomix_admin_story_mode_v1';
const REFRESH_MS = 10000;

let adminInitialized = false;
let autoRefreshTimer = null;
let autoRefreshEnabled = true;
let refreshLifecycleBound = false;
let flowDrawPending = false;
let flowInitialized = false;
let fullMapReady = false;
let fullMapNav = null;
let luaMapReady = false;
let luaMapNav = null;
let statusElementCache = { nodes: new Map(), metrics: new Map() };
let statusStateCache = { nodes: new Map(), metrics: new Map() };

const FULL_MAP_STATE_KEY = 'slomix_full_map_state_v1';
const FULL_MAP_COLLAPSED_KEY = 'slomix_full_map_collapsed_v1';
const FULL_MAP_WIDE_KEY = 'slomix_full_map_wide_v1';
const FULL_MAP_VIEW_KEY = 'slomix_full_map_view_v1';
const LUA_MAP_STATE_KEY = 'slomix_lua_map_state_v1';
const LUA_MAP_COLLAPSED_KEY = 'slomix_lua_map_collapsed_v1';
const LUA_MAP_WIDE_KEY = 'slomix_lua_map_wide_v1';
const FULL_MAP_FULLSCREEN_KEY = 'slomix_full_map_fullscreen_v1';
const LUA_MAP_FULLSCREEN_KEY = 'slomix_lua_map_fullscreen_v1';

const NODE_DETAILS = {
    core_game_server: {
        title: 'puran.hehe.si (Game Server)',
        eli5: 'This is the live game server where matches are played.',
        summary: 'The ET:Legacy runtime plus Lua scripts that generate raw stats.',
        why: 'All stats begin here. No game, no data.',
        how: 'Players join, rounds run, and Lua writes stats outputs.',
        inputs: 'Players, map configs, server lifecycle.',
        outputs: 'Lua stats files + timing webhooks.',
        files: 'ET:Legacy runtime + Lua scripts'
    },
    core_postgres: {
        title: 'PostgreSQL (Central DB)',
        eli5: 'The vault that stores every stat safely.',
        summary: 'Central source of truth for all round, player, and session data.',
        why: 'Everything reads from here—Discord, website, analytics.',
        how: 'Importers write tables; services query them for displays.',
        inputs: 'Parsed stats + timing payloads.',
        outputs: 'Queryable stats for bot + website.',
        files: 'postgresql_database_manager.py'
    },
    core_bot_web: {
        title: 'Bot + Website Host',
        eli5: 'The server that turns database stats into Discord + website views.',
        summary: 'Runs the Discord bot, API backend, and website frontend.',
        why: 'This is how players see stats and interact with commands.',
        how: 'Bot queries DB and posts to Discord; API serves the website.',
        inputs: 'Database queries + Discord events.',
        outputs: 'Embeds, API responses, UI pages.',
        files: 'bot/, website/'
    },
    et_server: {
        title: 'ET:Legacy Runtime',
        eli5: 'The game itself running on the server.',
        summary: 'The game server process that drives rounds, players, and Lua hooks.',
        how: 'Emits game events that Lua modules listen to and write stats output files.',
        inputs: 'Players, map configs, server lifecycle events.',
        outputs: 'Lua stats files, round lifecycle signals.',
        files: 'Game server runtime + configs'
    },
    lua_modules: {
        title: 'Lua Modules',
        eli5: 'Small scripts that watch the game and write stats files.',
        summary: 'Load order and Lua scripting layer for stats + proximity.',
        how: 'Configured in legacy.cfg to run c0rnp0rn7, endstats, and proximity modules.',
        inputs: 'Game server hooks.',
        outputs: 'Lua-driven outputs.',
        files: 'server config / legacy.cfg'
    },
    server_watchdog: {
        title: 'Server Watchdogs',
        eli5: 'The babysitter that restarts the server if it crashes.',
        summary: 'Operational scripts that keep the game server running.',
        how: 'Auto-restart or health-check scripts that ensure the server process stays alive.',
        inputs: 'Server process + uptime checks.',
        outputs: 'Restart actions, uptime logs.',
        files: 'Server watchdog scripts'
    },
    lua_c0rnp0rn7: {
        title: 'c0rnp0rn7.lua',
        eli5: 'Writes the main stats file after each round.',
        summary: 'Primary stats exporter for each round.',
        how: 'Writes per-player tab fields (time, damage, objectives) into gamestats files.',
        inputs: 'Round events, player stats.',
        outputs: 'gamestats/*.txt',
        files: 'Lua module on server'
    },
    lua_endstats: {
        title: 'endstats.lua',
        eli5: 'Writes the awards file when a round ends.',
        summary: 'End-of-round awards and highlights exporter.',
        how: 'Writes award-centric data to endstats files.',
        inputs: 'Round end event.',
        outputs: 'endstats/*.txt',
        files: 'Lua module on server'
    },
    lua_webhook: {
        title: 'stats_discord_webhook.lua',
        eli5: 'Sends a quick ping when rounds start/end.',
        summary: 'Realtime Lua webhook for round timing and metadata.',
        how: 'Sends round start/end payloads to the bot webhook endpoint.',
        inputs: 'Game state transitions.',
        outputs: 'Webhook POST to bot; lua_round_teams rows.',
        files: 'vps_scripts/stats_discord_webhook.lua'
    },
    lua_proximity: {
        title: 'proximity_tracker.lua',
        eli5: 'Prototype script that logs how close players are.',
        summary: 'Prototype proximity telemetry module.',
        how: 'Samples player positions and engagements into proximity output files.',
        inputs: 'Player movement + combat events.',
        outputs: 'proximity/*_engagements.txt',
        files: 'proximity/lua/proximity_tracker.lua'
    },
    lua_c0rnp0rn: {
        title: 'c0rnp0rn.lua (Legacy)',
        eli5: 'Old stats script kept for reference.',
        summary: 'Legacy gamestats exporter retained for fallback.',
        how: 'Writes older gamestats format with fewer fields.',
        inputs: 'ET:Legacy round stats.',
        outputs: 'gamestats/*.txt (legacy format).',
        files: 'c0rnp0rn.lua'
    },
    lua_c0rnp0rn7real: {
        title: 'c0rnp0rn7real.lua (Legacy)',
        eli5: 'Alternate legacy variant of the stats script.',
        summary: 'Alternative gamestats exporter variant.',
        how: 'Maintains an older format for comparison/debug.',
        inputs: 'ET:Legacy round stats.',
        outputs: 'gamestats/*.txt (legacy variant).',
        files: 'c0rnp0rn7real.lua'
    },
    lua_et_initgame: {
        title: 'et_InitGame()',
        eli5: 'Boots the Lua stats system when the server starts.',
        summary: 'Initializes arrays and reads server config for c0rnp0rn7.',
        how: 'Resets trackers like topshots, death_time, and timing tables.',
        inputs: 'Game start event.',
        outputs: 'Fresh Lua state for the round.',
        files: 'c0rnp0rn7.lua'
    },
    lua_et_runframe: {
        title: 'et_RunFrame()',
        eli5: 'Runs every frame to keep stats up-to-date.',
        summary: 'Periodic StoreStats + intermission save logic.',
        how: 'Stores stats every few seconds and handles pause/intermission timing.',
        inputs: 'Frame tick + gamestate.',
        outputs: 'Updated stats buffers, saved files.',
        files: 'c0rnp0rn7.lua'
    },
    lua_et_obituary: {
        title: 'et_Obituary()',
        eli5: 'Fires whenever someone dies.',
        summary: 'Tracks deaths, kill sprees, and denied playtime timers.',
        how: 'Sets death_time and starts denies timers for the killer/victim pair.',
        inputs: 'Kill event.',
        outputs: 'death_time, denies, topshots updates.',
        files: 'c0rnp0rn7.lua'
    },
    lua_et_clientspawn: {
        title: 'et_ClientSpawn()',
        eli5: 'Fires when a player spawns or respawns.',
        summary: 'Closes death timers and denied timers on spawn.',
        how: 'Adds to death_time_total and denied_playtime when the victim returns.',
        inputs: 'Spawn event.',
        outputs: 'death_time_total + topshots[16] updates.',
        files: 'c0rnp0rn7.lua'
    },
    lua_et_clientdisconnect: {
        title: 'et_ClientDisconnect()',
        eli5: 'Fires when a player leaves.',
        summary: 'Finalizes timers so totals are not lost on disconnect.',
        how: 'Flushes denies/death timers before clearing state.',
        inputs: 'Disconnect event.',
        outputs: 'Final denied/dead totals.',
        files: 'c0rnp0rn7.lua'
    },
    lua_et_damage: {
        title: 'et_Damage()',
        eli5: 'Fires when someone takes damage.',
        summary: 'Tracks hit regions and headshots for weapon stats.',
        how: 'Logs hit data to support weapon and accuracy stats.',
        inputs: 'Damage event.',
        outputs: 'Hitters + headshot tallies.',
        files: 'c0rnp0rn7.lua'
    },
    lua_et_print: {
        title: 'et_Print()',
        eli5: 'Reads game text output.',
        summary: 'Parses objective messages and round text markers.',
        how: 'Watches server text to detect objective events.',
        inputs: 'Server print output.',
        outputs: 'Objective event counters.',
        files: 'c0rnp0rn7.lua'
    },
    lua_et_shutdown: {
        title: 'et_ShutdownGame()',
        eli5: 'Runs when the map or server is closing.',
        summary: 'Ensures stats are saved even if round ends early.',
        how: 'Calls StoreStats/SaveStats when the server shuts down.',
        inputs: 'Shutdown event.',
        outputs: 'Final gamestats file.',
        files: 'c0rnp0rn7.lua'
    },
    lua_death_time: {
        title: 'death_time[] (start)',
        eli5: 'Stores the exact moment a player died.',
        summary: 'Per-player timer start set in et_Obituary.',
        how: 'death_time[victim] = et.trap_Milliseconds().',
        inputs: 'Death events.',
        outputs: 'Used to compute death_time_total.',
        files: 'c0rnp0rn7.lua'
    },
    lua_death_time_total: {
        title: 'death_time_total[]',
        eli5: 'Adds up how long a player was dead.',
        summary: 'Accumulator of dead time in milliseconds.',
        how: 'Incremented on spawn/team-change/disconnect using death_time.',
        inputs: 'Spawn/leave events.',
        outputs: 'time_dead_minutes + time_dead_ratio.',
        files: 'c0rnp0rn7.lua'
    },
    lua_denies_table: {
        title: 'denies[] (tracker)',
        eli5: 'Marks who denied whose playtime.',
        summary: 'Tracks killer/victim pairs for denied playtime.',
        how: 'Set on kill; cleared on spawn/intermission/disconnect.',
        inputs: 'Kill events.',
        outputs: 'topshots[16] denied playtime.',
        files: 'c0rnp0rn7.lua'
    },
    lua_denied_playtime: {
        title: 'denied_playtime (topshots[16])',
        eli5: 'How much time a killer removed from a victim.',
        summary: 'Denied playtime accumulator in milliseconds.',
        how: 'Added when victim respawns or leaves; converted to seconds on write.',
        inputs: 'denies[] + respawn events.',
        outputs: 'TAB[28] denied_playtime (seconds).',
        files: 'c0rnp0rn7.lua'
    },
    lua_time_played_pct: {
        title: 'time_played %',
        eli5: 'Percent of time a player was active.',
        summary: 'Normalized time_played from sess.time_played.',
        how: 'Computed as 100 * timePlayed / (timeAxis + timeAllies).',
        inputs: 'sess.time_axis + sess.time_allies.',
        outputs: 'TAB[10] time_played_percent.',
        files: 'c0rnp0rn7.lua'
    },
    lua_time_played_minutes: {
        title: 'time_played_minutes',
        eli5: 'Total minutes played in the round.',
        summary: 'Round time in minutes used for DPM.',
        how: 'tp = timeAxis + timeAllies; roundNum((tp/1000)/60, 1).',
        inputs: 'sess.time_axis + sess.time_allies.',
        outputs: 'TAB[22] time_played_minutes.',
        files: 'c0rnp0rn7.lua'
    },
    lua_time_dead_minutes: {
        title: 'time_dead_minutes',
        eli5: 'Minutes spent dead in the round.',
        summary: 'Derived from death_time_total (ms) / 60000.',
        how: 'roundNum((death_time_total/60000), 1).',
        inputs: 'death_time_total.',
        outputs: 'TAB[25] time_dead_minutes.',
        files: 'c0rnp0rn7.lua'
    },
    lua_time_dead_ratio: {
        title: 'time_dead_ratio %',
        eli5: 'Percent of the round spent dead.',
        summary: 'death_time_total / total_playtime * 100.',
        how: 'Computed when tp > 120000ms and written to TAB[24].',
        inputs: 'death_time_total + tp.',
        outputs: 'TAB[24] time_dead_ratio.',
        files: 'c0rnp0rn7.lua'
    },
    lua_topshots_array: {
        title: 'topshots[] array',
        eli5: 'Bucket of special stats like sprees and denied time.',
        summary: 'Holds DPM, sprees, denied playtime, and utility metrics.',
        how: 'Updated across multiple hooks; written in the stats line.',
        inputs: 'Kills, deaths, objectives.',
        outputs: 'TAB[11..31] special stats.',
        files: 'c0rnp0rn7.lua'
    },
    lua_weapon_stats_buffer: {
        title: 'weaponStats buffer',
        eli5: 'Tracks hits, shots, kills per weapon.',
        summary: 'Per-weapon hit/att/kill/death/headshot counts.',
        how: 'Aggregated and appended before TAB fields.',
        inputs: 'Damage and obituary events.',
        outputs: 'Weapon block + TAB fields.',
        files: 'c0rnp0rn7.lua'
    },
    lua_round_header: {
        title: 'Round header',
        eli5: 'Top line in the gamestats file.',
        summary: 'Includes server, map, round number, timelimits, and winner.',
        how: 'Built before writing player stat lines.',
        inputs: 'Server cvars + round metadata.',
        outputs: 'gamestats file header.',
        files: 'c0rnp0rn7.lua'
    },
    lua_tab_fields: {
        title: 'TAB fields',
        eli5: 'The core per-player stats line.',
        summary: 'Final formatted stats row written to gamestats.',
        how: 'Combines weapon block + TAB fields + timing stats.',
        inputs: 'topshots, weaponStats, timing.',
        outputs: 'gamestats player lines.',
        files: 'c0rnp0rn7.lua'
    },
    lua_gamestats_file: {
        title: 'gamestats/*.txt',
        eli5: 'Main stats file written each round.',
        summary: 'Primary output file used by the bot parser.',
        how: 'SaveStats writes header + player lines.',
        inputs: 'TAB fields + header.',
        outputs: 'Files consumed by stats ingest.',
        files: '/gamestats/*.txt'
    },
    lua_weaponstats_file: {
        title: 'gamestats_*_ws.txt',
        eli5: 'Optional weapon-only stats file.',
        summary: 'Weapon stats export (currently commented out).',
        how: 'Would write weapon stats per player if enabled.',
        inputs: 'WeaponStats buffer.',
        outputs: 'Weapon stats file.',
        files: 'c0rnp0rn7.lua (commented)'
    },
    lua_endstats_file: {
        title: 'endstats/*.txt',
        eli5: 'Awards file written at round end.',
        summary: 'Used for award embeds and summaries.',
        how: 'endstats.lua outputs award stats.',
        inputs: 'Round end event.',
        outputs: 'endstats files.',
        files: 'endstats.lua'
    },
    lua_webhook_payload: {
        title: 'Webhook payload',
        eli5: 'Small JSON ping sent at round start/end.',
        summary: 'Contains timing metadata + scores for webhook sync.',
        how: 'stats_discord_webhook.lua POSTs to bot.',
        inputs: 'Round start/end events.',
        outputs: 'Webhook HTTP POST.',
        files: 'vps_scripts/stats_discord_webhook.lua'
    },
    lua_webhook_round_start: {
        title: 'Lua Webhook: RoundStart',
        eli5: 'Hook that fires when a round begins.',
        summary: 'Captures start timestamp and round metadata.',
        how: 'Sends a webhook payload on round start.',
        inputs: 'Round start event.',
        outputs: 'Webhook payload.',
        files: 'stats_discord_webhook.lua'
    },
    lua_webhook_round_end: {
        title: 'Lua Webhook: RoundEnd',
        eli5: 'Hook that fires when a round ends.',
        summary: 'Captures end timestamp, scores, and reason.',
        how: 'Sends a webhook payload on round end.',
        inputs: 'Round end event.',
        outputs: 'Webhook payload.',
        files: 'stats_discord_webhook.lua'
    },
    lua_proximity_logs: {
        title: 'Proximity logs',
        eli5: 'Prototype files for player positions and engagements.',
        summary: 'Logs positions/engagements for proximity analytics.',
        how: 'proximity_tracker.lua writes engagement files.',
        inputs: 'Player movement + combat.',
        outputs: 'proximity/*_engagements.txt and related logs.',
        files: 'proximity/lua/proximity_tracker.lua'
    },
    players: {
        title: 'Players',
        eli5: 'Real people playing the game or chatting in Discord.',
        summary: 'Players generate game actions and Discord activity.',
        how: 'They connect to the game server and Discord.',
        inputs: 'Human gameplay + voice chat.',
        outputs: 'Game events + Discord messages.'
    },
    game_server_host: {
        title: 'Game Server Host',
        eli5: 'The machine that runs the game.',
        summary: 'Physical/virtual server hosting ET:Legacy.',
        how: 'Runs the ET server process and Lua scripts.',
        inputs: 'Player connections.',
        outputs: 'Stats files + logs.'
    },
    bot_server_host: {
        title: 'Stats/Bot/Website Host',
        eli5: 'The machine that runs the bot, database, and website.',
        summary: 'Main VPS hosting bot + DB + web stack.',
        how: 'Runs Discord bot, Postgres, and FastAPI.',
        inputs: 'Stats files, webhooks, Discord events.',
        outputs: 'Discord updates + website data.'
    },
    discord_cloud: {
        title: 'Discord Cloud',
        eli5: 'Discord’s servers where chat and voice happen.',
        summary: 'Discord platform for text + voice.',
        how: 'Relays messages, voice activity, and webhooks.',
        inputs: 'User chats + voice.',
        outputs: 'Events to the bot.'
    },
    discord_text: {
        title: 'Discord Text Channels',
        eli5: 'Where commands and stats messages appear.',
        summary: 'Text channels for commands and updates.',
        how: 'Users type commands; bot posts embeds.',
        inputs: 'Commands + webhooks.',
        outputs: 'Embeds + responses.'
    },
    discord_voice: {
        title: 'Discord Voice Channels',
        eli5: 'Where players join voice to trigger session tracking.',
        summary: 'Voice channels for session detection.',
        how: 'Voice activity is tracked for auto session posts.',
        inputs: 'Voice join/leave events.',
        outputs: 'Session activity signals.'
    },
    stats_ingest: {
        title: 'Stats Ingest',
        eli5: 'Folder watcher that grabs new stats files.',
        summary: 'File watcher / sync layer for gamestats.',
        how: 'Pulls new files, deduplicates by timestamp and queues parse.',
        inputs: 'gamestats/*.txt',
        outputs: 'Parsed rounds queued.',
        files: 'bot file scanner'
    },
    endstats_ingest: {
        title: 'Endstats Ingest',
        eli5: 'Folder watcher that grabs awards files.',
        summary: 'File watcher for endstats award files.',
        how: 'Scans endstats output and queues award parsing.',
        inputs: 'endstats/*.txt',
        outputs: 'Award records.',
        files: 'bot endstats ingest'
    },
    webhook_receiver: {
        title: 'Webhook Receiver',
        eli5: 'Small web server that catches Lua pings.',
        summary: 'Receives Lua webhook timing payloads.',
        how: 'Processes stats_discord_webhook.lua POSTs and stores lua_round_teams.',
        inputs: 'Lua webhook HTTP POST.',
        outputs: 'lua_round_teams rows + timing metadata.',
        files: 'bot/ultimate_bot.py'
    },
    proximity_ingest: {
        title: 'Proximity Ingest',
        eli5: 'Watcher for proximity log files.',
        summary: 'Prototype watcher for proximity engagement files.',
        how: 'Scans proximity directory for new engagement files.',
        inputs: 'proximity/*_engagements.txt',
        outputs: 'Parsed proximity rows.',
        files: 'proximity ingest task'
    },
    stats_parser: {
        title: 'Stats Parser',
        eli5: 'Translator that turns raw text into clean numbers.',
        summary: 'Parses gamestats into per-player records.',
        how: 'Reads tab fields and weapon stats; constructs objective_stats map.',
        inputs: 'gamestats/*.txt',
        outputs: 'Parsed player + weapon stats.',
        files: 'bot/community_stats_parser.py'
    },
    differential_calc: {
        title: 'R1/R2 Differential',
        eli5: 'Figures out Round 2 only by subtracting Round 1.',
        summary: 'Computes round 2-only values from cumulative stats.',
        how: 'Subtracts R1 for cumulative fields and keeps R2-only fields intact.',
        inputs: 'Round 1 + Round 2 stats.',
        outputs: 'Differential player data.',
        files: 'bot/community_stats_parser.py'
    },
    validation_caps: {
        title: 'Validation & Caps',
        eli5: 'Stops impossible numbers from sneaking in.',
        summary: 'Sanity checks for impossible values.',
        how: 'Caps time_dead to time_played, clamps ratios and negatives.',
        inputs: 'Parsed player stats.',
        outputs: 'Cleaned stats + warnings.',
        files: 'postgresql_database_manager.py'
    },
    proximity_parser: {
        title: 'Proximity Parser',
        eli5: 'Translator for proximity logs.',
        summary: 'Prototype parser for engagement telemetry.',
        how: 'Transforms engagement logs into proximity tables.',
        inputs: 'proximity files.',
        outputs: 'proximity_* tables.',
        files: 'proximity/parser/parser.py'
    },
    community_stats_parser: {
        title: 'Stats Parser (Community)',
        eli5: 'Turns the main stats file into clean numbers.',
        summary: 'Parses gamestats files into structured stats.',
        how: 'Reads the stats file format and builds player + weapon stats.',
        inputs: 'gamestats/*.txt',
        outputs: 'Parsed stats dictionaries.',
        files: 'community_stats_parser.py'
    },
    endstats_parser: {
        title: 'Endstats Parser',
        eli5: 'Turns the awards file into clean award rows.',
        summary: 'Parses endstats files into award records.',
        how: 'Extracts award lines and maps them to players.',
        inputs: 'endstats/*.txt',
        outputs: 'Award data.',
        files: 'endstats_parser.py'
    },
    postgresql_database_manager: {
        title: 'PostgreSQL Database Manager',
        eli5: 'The importer that saves parsed stats into the database.',
        summary: 'Handles inserts, updates, and validation for stats imports.',
        how: 'Wraps parsing output into DB transactions.',
        inputs: 'Parsed stats dictionaries.',
        outputs: 'Postgres rows + logs.',
        files: 'postgresql_database_manager.py'
    },
    ssh_monitor: {
        title: 'SSH Monitor',
        eli5: 'Watches the game server and downloads new files.',
        summary: 'Detects new stats files and syncs them locally.',
        how: 'Polls over SSH/SFTP and downloads to local_stats.',
        inputs: 'Remote gamestats/endstats files.',
        outputs: 'Local file copies.',
        files: 'bot/services/automation/ssh_monitor.py'
    },
    ssh_handler: {
        title: 'SSH Handler',
        eli5: 'Low-level SSH helper for downloads.',
        summary: 'Reusable SSH/SFTP connection logic.',
        how: 'Provides connection + file transfer utilities.',
        inputs: 'SSH credentials.',
        outputs: 'Downloaded files.',
        files: 'bot/automation/ssh_handler.py'
    },
    file_tracker: {
        title: 'File Tracker',
        eli5: 'Keeps track of which files are new.',
        summary: 'Tracks processed vs pending files.',
        how: 'Records file metadata and timestamps.',
        inputs: 'File lists.',
        outputs: 'Processing queue.',
        files: 'bot/automation/file_tracker.py'
    },
    file_repository: {
        title: 'File Repository',
        eli5: 'Stores local copies of downloaded files.',
        summary: 'Provides file access for parsers.',
        how: 'Abstracts file paths and read operations.',
        inputs: 'Downloaded files.',
        outputs: 'File content for parsers.',
        files: 'bot/repositories/file_repository.py'
    },
    gamestats_files: {
        title: 'gamestats/*.txt',
        eli5: 'The main stats file written by Lua.',
        summary: 'Round stats output from c0rnp0rn7.lua.',
        how: 'Written at round end on the game server.',
        inputs: 'Game events + stats.',
        outputs: 'Raw stats text.',
        files: 'server gamestats folder'
    },
    endstats_files: {
        title: 'endstats/*.txt',
        eli5: 'The awards file written by Lua.',
        summary: 'Awards output from endstats.lua.',
        how: 'Written at round end on the game server.',
        inputs: 'Round end awards.',
        outputs: 'Raw awards text.',
        files: 'server endstats folder'
    },
    gametimes_files: {
        title: 'gametimes.json',
        eli5: 'Fallback timing files when webhook is down.',
        summary: 'Lua timing payloads saved locally as JSON.',
        how: 'Saved when webhook cannot deliver timing.',
        inputs: 'Lua timing data.',
        outputs: 'JSON files.',
        files: 'local gametimes folder'
    },
    proximity_positions: {
        title: 'Proximity: positions.txt',
        eli5: 'Player positions captured every second.',
        summary: 'Position snapshots from proximity tracker.',
        how: 'Written each round by proximity_tracker.lua.',
        inputs: 'Player movement.',
        outputs: 'Position logs.',
        files: 'proximity outputs'
    },
    proximity_combat: {
        title: 'Proximity: combat.txt',
        eli5: 'Every shot/hit/kill logged.',
        summary: 'Combat event logs from proximity tracker.',
        how: 'Written each round by proximity_tracker.lua.',
        inputs: 'Combat events.',
        outputs: 'Combat logs.',
        files: 'proximity outputs'
    },
    proximity_engagements: {
        title: 'Proximity: engagements.txt',
        eli5: 'Summaries of fights and engagements.',
        summary: 'Engagement summaries from proximity tracker.',
        how: 'Aggregated at round end.',
        inputs: 'Combat logs.',
        outputs: 'Engagement summaries.',
        files: 'proximity outputs'
    },
    proximity_heatmap: {
        title: 'Proximity: heatmap.txt',
        eli5: 'Grid heatmap of kill locations.',
        summary: 'Heatmap grid output from proximity tracker.',
        how: 'Computed at round end.',
        inputs: 'Kill events.',
        outputs: 'Heatmap cells.',
        files: 'proximity outputs'
    },
    round_linker: {
        title: 'Round Linker',
        eli5: 'Matches stats rounds with webhook/endstats rounds.',
        summary: 'Links related round data together.',
        how: 'Uses timestamps + metadata to link round IDs.',
        inputs: 'Parsed stats + webhook metadata.',
        outputs: 'Linked round records.',
        files: 'bot/core/round_linker.py'
    },
    logging_config: {
        title: 'Logging Config',
        eli5: 'Controls log files for the bot.',
        summary: 'Defines loggers and log file outputs.',
        how: 'Configures rotating log handlers.',
        inputs: 'Log messages.',
        outputs: 'logs/*.log',
        files: 'bot/logging_config.py'
    },
    monitoring_service: {
        title: 'Monitoring Service',
        eli5: 'Watches health and sends alerts.',
        summary: 'Tracks uptime, errors, and failures.',
        how: 'Runs periodic checks and reports status.',
        inputs: 'Health checks.',
        outputs: 'Alerts + logs.',
        files: 'bot/services/monitoring_service.py'
    },
    voice_session_service: {
        title: 'Voice Session Service',
        eli5: 'Auto-posts sessions based on voice activity.',
        summary: 'Detects session start/end from voice channels.',
        how: 'Monitors voice channel population.',
        inputs: 'Discord voice state.',
        outputs: 'Auto posts.',
        files: 'bot/services/voice_session_service.py'
    },
    session_data_service: {
        title: 'Session Data Service',
        eli5: 'Fetches session data for other modules.',
        summary: 'Shared session query helper.',
        how: 'Wraps DB queries for sessions.',
        inputs: 'Session queries.',
        outputs: 'Session datasets.',
        files: 'bot/services/session_data_service.py'
    },
    player_analytics_service: {
        title: 'Player Analytics Service',
        eli5: 'Calculates deeper player analytics.',
        summary: 'Builds advanced player metrics.',
        how: 'Aggregates stats and trends.',
        inputs: 'Player stats.',
        outputs: 'Analytics data.',
        files: 'bot/services/player_analytics_service.py'
    },
    player_badge_service: {
        title: 'Player Badge Service',
        eli5: 'Assigns badges like MVP or Sharpshooter.',
        summary: 'Calculates badge awards.',
        how: 'Scores players by criteria.',
        inputs: 'Session stats.',
        outputs: 'Badge assignments.',
        files: 'bot/services/player_badge_service.py'
    },
    player_display_name_service: {
        title: 'Player Display Name Service',
        eli5: 'Keeps player names consistent.',
        summary: 'Normalizes player display names.',
        how: 'Maps aliases to canonical names.',
        inputs: 'Player identifiers.',
        outputs: 'Display names.',
        files: 'bot/services/player_display_name_service.py'
    },
    prediction_engine: {
        title: 'Prediction Engine',
        eli5: 'Calculates match predictions.',
        summary: 'Builds prediction models for matches.',
        how: 'Uses player stats + matchup info.',
        inputs: 'Team + player stats.',
        outputs: 'Prediction results.',
        files: 'bot/services/prediction_engine.py'
    },
    prediction_embed_builder: {
        title: 'Prediction Embed Builder',
        eli5: 'Formats predictions for Discord.',
        summary: 'Creates prediction embeds.',
        how: 'Builds formatted Discord embeds.',
        inputs: 'Prediction results.',
        outputs: 'Discord embeds.',
        files: 'bot/services/prediction_embed_builder.py'
    },
    matchup_analytics_service: {
        title: 'Matchup Analytics Service',
        eli5: 'Analyzes team vs team matchups.',
        summary: 'Computes matchup stats.',
        how: 'Aggregates team performance data.',
        inputs: 'Team stats.',
        outputs: 'Matchup analytics.',
        files: 'bot/services/matchup_analytics_service.py'
    },
    timing_debug_service: {
        title: 'Timing Debug Service',
        eli5: 'Extra debugging for round timing.',
        summary: 'Compares Lua timing to stats timing.',
        how: 'Builds detailed debug reports.',
        inputs: 'lua_round_teams + stats.',
        outputs: 'Debug reports.',
        files: 'bot/services/timing_debug_service.py'
    },
    website_router_api: {
        title: 'Website API Router',
        eli5: 'Routes the main API endpoints.',
        summary: 'FastAPI router for stats endpoints.',
        how: 'Defines /api routes.',
        inputs: 'HTTP requests.',
        outputs: 'JSON responses.',
        files: 'website/backend/routers/api.py'
    },
    website_router_auth: {
        title: 'Website Auth Router',
        eli5: 'Routes auth endpoints.',
        summary: 'FastAPI router for auth.',
        how: 'Defines /auth routes.',
        inputs: 'HTTP requests.',
        outputs: 'JSON responses.',
        files: 'website/backend/routers/auth.py'
    },
    website_router_predictions: {
        title: 'Website Predictions Router',
        eli5: 'Routes prediction endpoints.',
        summary: 'FastAPI router for predictions.',
        how: 'Defines /predictions routes.',
        inputs: 'HTTP requests.',
        outputs: 'JSON responses.',
        files: 'website/backend/routers/predictions.py'
    },
    website_session_data_service: {
        title: 'Website Session Data Service',
        eli5: 'Fetches session data for the website.',
        summary: 'Website-facing session query helper.',
        how: 'Queries DB and formats responses.',
        inputs: 'DB queries.',
        outputs: 'Session JSON.',
        files: 'website/backend/services/website_session_data_service.py'
    },
    voice_channel_tracker: {
        title: 'Voice Channel Tracker',
        eli5: 'Tracks voice activity for the website.',
        summary: 'Website voice tracking helper.',
        how: 'Monitors voice channel metrics.',
        inputs: 'Voice activity.',
        outputs: 'Voice stats.',
        files: 'website/backend/services/voice_channel_tracker.py'
    },
    game_server_query: {
        title: 'Game Server Query',
        eli5: 'Reads live server status for the website.',
        summary: 'Queries game server status.',
        how: 'Sends server queries for live info.',
        inputs: 'Server endpoints.',
        outputs: 'Status JSON.',
        files: 'website/backend/services/game_server_query.py'
    },
    db_adapter: {
        title: 'DB Adapter',
        eli5: 'Shared helper that talks to the database.',
        summary: 'Shared database access for bot + website.',
        how: 'Abstracts SQLite/Postgres queries and connections.',
        inputs: 'SQL queries.',
        outputs: 'DB results.',
        files: 'bot/core/database_adapter.py'
    },
    postgres: {
        title: 'PostgreSQL',
        eli5: 'The big database where all stats live.',
        summary: 'Primary persistent storage.',
        how: 'Stores rounds, players, weapons, proximity data.',
        inputs: 'Insert/update queries.',
        outputs: 'Query results.',
        files: 'Postgres database'
    },
    table_rounds: {
        title: 'Table: rounds',
        eli5: 'The list of every round we played.',
        summary: 'Round metadata (map, times, outcome).',
        how: 'Inserted on each round import.',
        inputs: 'Round headers.',
        outputs: 'Round rows.',
        files: 'player_comprehensive_stats schema'
    },
    table_player_stats: {
        title: 'Table: player_comprehensive_stats',
        eli5: 'The big table with each player’s stats.',
        summary: 'Core per-player stats table.',
        how: 'Holds time, damage, objectives, K/D, etc.',
        inputs: 'Parsed player records.',
        outputs: 'Aggregated stats.',
        files: 'postgresql_database_manager.py'
    },
    table_weapon_stats: {
        title: 'Table: weapon_comprehensive_stats',
        eli5: 'The table with weapon hits, shots, and accuracy.',
        summary: 'Per-weapon hits, shots, kills, accuracy.',
        how: 'Used for accuracy + headshots.',
        inputs: 'Weapon stats.',
        outputs: 'Weapon rows.',
        files: 'weapon_comprehensive_stats schema'
    },
    table_processed_files: {
        title: 'Table: processed_files',
        eli5: 'Keeps track of which files are already imported.',
        summary: 'Prevents double-importing stats files.',
        how: 'Records filename + status after import.',
        inputs: 'Import results.',
        outputs: 'File status rows.',
        files: 'processed_files schema'
    },
    table_gaming_sessions: {
        title: 'Table: gaming_sessions',
        eli5: 'Groups many rounds into a session.',
        summary: 'Session metadata table.',
        how: 'Created when session boundaries are detected.',
        inputs: 'Round timing gaps.',
        outputs: 'Session rows.',
        files: 'gaming_sessions schema'
    },
    table_session_rounds: {
        title: 'Table: session_rounds',
        eli5: 'Links rounds to their sessions.',
        summary: 'Mapping between sessions and rounds.',
        how: 'Populated during imports.',
        inputs: 'Round IDs + session IDs.',
        outputs: 'Link rows.',
        files: 'session_rounds schema'
    },
    table_lua_round_teams: {
        title: 'Table: lua_round_teams',
        eli5: 'The timing table from Lua webhook pings.',
        summary: 'Lua webhook metadata for timing comparison.',
        how: 'Stored from Lua webhook events.',
        inputs: 'Lua webhook payloads.',
        outputs: 'Timing comparison.',
        files: 'lua webhook ingestion'
    },
    table_proximity: {
        title: 'Tables: proximity_*',
        eli5: 'Prototype tables for proximity analytics.',
        summary: 'Prototype proximity analytics tables.',
        how: 'Populated by proximity parser.',
        inputs: 'Engagement logs.',
        outputs: 'Prototype analytics.',
        files: 'proximity/schema/schema.sql'
    },
    discord_bot: {
        title: 'Discord Bot Runtime',
        eli5: 'The bot that posts stats into Discord.',
        summary: 'Main bot process and cogs.',
        how: 'Runs commands, posts round/session summaries.',
        inputs: 'DB queries + live events.',
        outputs: 'Discord messages.',
        files: 'bot/ultimate_bot.py'
    },
    discord_webhook: {
        title: 'Discord Webhook',
        eli5: 'A Discord endpoint the game server can ping.',
        summary: 'Receives webhook notifications from the game server.',
        how: 'Discord stores the webhook and posts into a control channel.',
        inputs: 'HTTP POST from server scripts.',
        outputs: 'Webhook messages in control channel.'
    },
    discord_control_channel: {
        title: 'Discord Control Channel',
        eli5: 'Private channel for webhook trigger messages.',
        summary: 'Receives STATS_READY or file notifications.',
        how: 'Bot watches this channel for webhook triggers.',
        inputs: 'Webhook posts.',
        outputs: 'Triggers bot processing.'
    },
    discord_stats_channel: {
        title: 'Discord Stats Channel',
        eli5: 'Where final stats are posted.',
        summary: 'Public channel for round/session embeds.',
        how: 'Bot posts rich embeds after processing.',
        inputs: 'Bot embeds.',
        outputs: 'User-facing stats.'
    },
    stats_webhook_notify: {
        title: 'stats_webhook_notify.py',
        eli5: 'VPS script that sends file notifications to Discord.',
        summary: 'Watches gamestats directory and posts webhooks.',
        how: 'Uses watchdog/inotify and sends Discord webhooks.',
        inputs: 'New stats files.',
        outputs: 'Discord webhook message.',
        files: 'vps_scripts/stats_webhook_notify.py'
    },
    et_stats_webhook_service: {
        title: 'et-stats-webhook.service',
        eli5: 'Keeps the webhook notifier running.',
        summary: 'Systemd service for stats webhook notifier.',
        how: 'Runs stats_webhook_notify.py continuously.',
        inputs: 'Systemd unit.',
        outputs: 'Webhook notifier process.'
    },
    webhook_trigger_handler: {
        title: 'Webhook Trigger Handler',
        eli5: 'Bot listener for webhook messages.',
        summary: 'Parses webhook messages and starts processing.',
        how: 'Handles STATS_READY or filename webhook messages.',
        inputs: 'Discord webhook message.',
        outputs: 'Processing task.',
        files: 'bot/ultimate_bot.py'
    },
    webhook_security_gate: {
        title: 'Webhook Security Gate',
        eli5: 'Safety checks before processing.',
        summary: 'Validates webhook ID, rate limits, and filenames.',
        how: 'Whitelist + rate limit + filename regex.',
        inputs: 'Webhook metadata.',
        outputs: 'Allow/deny decision.',
        files: 'bot/ultimate_bot.py'
    },
    endstats_monitor: {
        title: 'endstats_monitor',
        eli5: 'Background loop that polls for files.',
        summary: 'SSH polling fallback when webhooks fail.',
        how: 'Periodically checks remote stats directories.',
        inputs: 'SSH file list.',
        outputs: 'Downloaded files.',
        files: 'bot/ultimate_bot.py'
    },
    cache_refresher: {
        title: 'cache_refresher',
        eli5: 'Refreshes processed files cache.',
        summary: 'Keeps in-memory cache synced with DB.',
        how: 'Loads processed_files list on a timer.',
        inputs: 'DB processed_files.',
        outputs: 'Updated cache.',
        files: 'bot/ultimate_bot.py'
    },
    etconsole_log: {
        title: 'etconsole.log',
        eli5: 'Live server log for match events.',
        summary: 'Game server console log stream.',
        how: 'Tailed via SSH during live monitoring.',
        inputs: 'Game server events.',
        outputs: 'Log lines.',
        files: '/home/et/.etlegacy/legacy/etconsole.log'
    },
    bot_log_stream: {
        title: 'Bot Log Stream',
        eli5: 'Live bot logs while games run.',
        summary: 'journalctl tail for etlegacy-bot service.',
        how: 'Tailed during live monitoring.',
        inputs: 'Bot events.',
        outputs: 'Log lines.',
        files: 'journalctl -u etlegacy-bot -f'
    },
    webhook_log_stream: {
        title: 'Webhook Log Stream',
        eli5: 'Logs for webhook activity.',
        summary: 'Dedicated webhook logger output.',
        how: 'Writes to webhook.log or journalctl.',
        inputs: 'Webhook events.',
        outputs: 'Webhook log lines.',
        files: 'logs/webhook.log'
    },
    live_monitoring_session: {
        title: 'Live Monitoring Session',
        eli5: 'Manual live watching of game + bot.',
        summary: 'Human observes console + bot logs in real time.',
        how: 'Compare timestamps between server log and bot log.',
        inputs: 'etconsole + bot logs.',
        outputs: 'Notes + timeline.',
        files: 'docs/LIVE_MONITORING_NOTES_2026-02-03.md'
    },
    round_status_filter: {
        title: 'Round Status Filter',
        eli5: 'Only completed rounds count in stats.',
        summary: 'Filters out cancelled/incomplete rounds.',
        how: 'SQL filters on round_status fields.',
        inputs: 'Rounds table.',
        outputs: 'Filtered stats.',
        files: 'bot/services/session_stats_aggregator.py'
    },
    round_end_reason: {
        title: 'Round End Reason',
        eli5: 'Why the round ended (time, objective, surrender).',
        summary: 'End reason from Lua webhook timing.',
        how: 'Captured on round end and stored.',
        inputs: 'Lua webhook metadata.',
        outputs: 'rounds.end_reason.',
        files: 'vps_scripts/stats_discord_webhook.lua'
    },
    round_completed: {
        title: 'Completed Round',
        eli5: 'A normal finished round.',
        summary: 'Round finished by objective or time.',
        how: 'Stored with completed status.',
        inputs: 'Round data.',
        outputs: 'Included in stats.'
    },
    round_surrender: {
        title: 'Surrender Round',
        eli5: 'Round ended early by surrender.',
        summary: 'Lua webhook captures actual duration.',
        how: 'End reason = surrender.',
        inputs: 'Lua webhook metadata.',
        outputs: 'Accurate timing in DB.'
    },
    round_timelimit: {
        title: 'Time Limit Round',
        eli5: 'Round ended because time ran out.',
        summary: 'Time limit reached.',
        how: 'Captured in stats + webhook.',
        inputs: 'Round end.',
        outputs: 'Completed stats.'
    },
    round_cancelled: {
        title: 'Cancelled Round',
        eli5: 'Round ignored or cancelled.',
        summary: 'Filtered out from stats.',
        how: 'Round status not completed.',
        inputs: 'Round data.',
        outputs: 'Excluded from totals.'
    },
    round_substitution: {
        title: 'Substitution Round',
        eli5: 'Round marked as substitution.',
        summary: 'Special status used in some queries.',
        how: 'Included in some stats filters.',
        inputs: 'Round status.',
        outputs: 'Conditional inclusion.'
    },
    session_aggregator: {
        title: 'Session Stats Aggregator',
        eli5: 'Adds many rounds together into a session.',
        summary: 'Totals and weighted DPM for session views.',
        how: 'Aggregates across rounds by player.',
        inputs: 'player_comprehensive_stats rows.',
        outputs: 'Session aggregates.',
        files: 'bot/services/session_stats_aggregator.py'
    },
    session_embed_builder: {
        title: 'Session Embed Builder',
        eli5: 'Builds the pretty Discord summary box.',
        summary: 'Builds the main !last_session summary embed.',
        how: 'Formats totals with time dead/denied and badges.',
        inputs: 'Session aggregates.',
        outputs: 'Discord embeds.',
        files: 'bot/services/session_embed_builder.py'
    },
    session_view_handlers: {
        title: 'Session View Handlers',
        eli5: 'Other views of the session (combat, obj, maps).',
        summary: 'Alternative !last_session views (obj, combat, maps).',
        how: 'Queries DB and renders view-specific embeds.',
        inputs: 'DB session data.',
        outputs: 'Discord embeds.',
        files: 'bot/services/session_view_handlers.py'
    },
    round_publisher: {
        title: 'Round Publisher',
        eli5: 'Posts a single round summary to Discord.',
        summary: 'Posts per-round summaries in Discord.',
        how: 'Queries round stats and formats embed.',
        inputs: 'Round IDs + DB data.',
        outputs: 'Discord round posts.',
        files: 'bot/services/round_publisher_service.py'
    },
    graph_generator: {
        title: 'Graph Generator',
        eli5: 'Makes the PNG charts.',
        summary: 'Generates session charts (PNG).',
        how: 'Builds charts for offense/defense/metrics.',
        inputs: 'Aggregated session data.',
        outputs: 'PNG graphs.',
        files: 'bot/services/session_graph_generator.py'
    },
    endstats_aggregator: {
        title: 'Endstats Aggregator',
        eli5: 'Collects awards for the session.',
        summary: 'Produces awards for last_session endstats.',
        how: 'Parses award files and formats output.',
        inputs: 'endstats files.',
        outputs: 'Awards list.',
        files: 'bot/services/endstats_aggregator.py'
    },
    timing_comparison: {
        title: 'Timing Comparison',
        eli5: 'Compares Lua timing to file timing.',
        summary: 'Compares stats file timing vs Lua webhook timing.',
        how: 'Creates debug report in dev channel.',
        inputs: 'Stats DB + lua_round_teams.',
        outputs: 'Discord debug embed.',
        files: 'bot/services/timing_comparison_service.py'
    },
    proximity_cog: {
        title: 'Proximity Cog',
        eli5: 'Prototype Discord commands for proximity.',
        summary: 'Prototype Discord commands + scanners.',
        how: 'Manual scan/import + status commands.',
        inputs: 'Proximity files + DB.',
        outputs: 'Discord responses.',
        files: 'bot/cogs/proximity_cog.py'
    },
    website_api: {
        title: 'Website API',
        eli5: 'The server that gives data to the website.',
        summary: 'FastAPI backend for the SPA.',
        how: 'Serves stats, sessions, diagnostics.',
        inputs: 'DB queries.',
        outputs: 'JSON API.',
        files: 'website/backend/routers/api.py'
    },
    website_frontend: {
        title: 'Website Frontend',
        eli5: 'The website you click and browse.',
        summary: 'SPA UI for stats browsing.',
        how: 'Fetches API endpoints and renders views.',
        inputs: 'API JSON responses.',
        outputs: 'UI pages.',
        files: 'website/index.html + js/*'
    },
    admin_panel: {
        title: 'Admin Panel',
        eli5: 'This overview page you are looking at.',
        summary: 'Reactor view of the full system.',
        how: 'Combines diagnostics + manual overrides.',
        inputs: 'Diagnostics + local overrides.',
        outputs: 'Systems overview.',
        files: 'website/js/admin-panel.js'
    },
    proximity_api: {
        title: 'Proximity API',
        eli5: 'Prototype API for proximity data.',
        summary: 'Prototype API endpoints for proximity data.',
        how: 'Returns ready status + placeholder payloads.',
        inputs: 'Proximity tables (when live).',
        outputs: 'Prototype JSON.',
        files: 'website/backend/routers/api.py'
    },
    proximity_ui: {
        title: 'Proximity UI',
        eli5: 'Prototype screens for proximity.',
        summary: 'Prototype proximity visualization.',
        how: 'Renders placeholder cards and readiness message.',
        inputs: 'Proximity API.',
        outputs: 'Prototype UI view.',
        files: 'website/js/proximity.js'
    },
    tools_block: {
        title: 'Maintenance Tools',
        eli5: 'Manual scripts used by the admin.',
        summary: 'Manual scripts that keep data in sync.',
        how: 'Run by admin when needed.',
        inputs: 'DB + files.',
        outputs: 'Schema + data fixes.',
        files: 'scripts/*'
    },
    tool_schema_verify: {
        title: 'Schema Verifier',
        eli5: 'Checks that the tables exist and match.',
        summary: 'Checks tables and migrations for consistency.',
        how: 'Runs schema validation scripts.',
        inputs: 'DB schema.',
        outputs: 'Validation report.',
        files: 'scripts/verify_proximity_schema.py'
    },
    tool_proximity_objectives: {
        title: 'Proximity Objective Sync',
        eli5: 'Updates objective locations for proximity.',
        summary: 'Syncs objective coordinates into Lua.',
        how: 'Updates proximity_tracker.lua objective blocks.',
        inputs: 'objective_coords_template.json.',
        outputs: 'Lua updates.',
        files: 'scripts/update_proximity_objectives_from_json.py'
    },
    tool_backup_restore: {
        title: 'Backup + Restore',
        eli5: 'Makes safety copies of the database.',
        summary: 'Database safety snapshots.',
        how: 'Manual dumps and restore operations.',
        inputs: 'Postgres DB.',
        outputs: 'Backup files.',
        files: 'backups/*'
    },
    tool_time_audit: {
        title: 'Time Audit Export',
        eli5: 'Exports raw time stats for checking.',
        summary: 'Raw Lua time export for validation.',
        how: 'Exports time_dead + denied_playtime raw values.',
        inputs: 'player_comprehensive_stats.',
        outputs: 'CSV export.',
        files: 'bot/services/session_view_handlers.py'
    },
    tool_migrations: {
        title: 'Migration Helpers',
        eli5: 'Applies database structure changes.',
        summary: 'Schema migration scripts.',
        how: 'Applies DB changes safely.',
        inputs: 'SQL migration files.',
        outputs: 'Updated schema.',
        files: 'proximity/schema/migrations/*'
    },
    tool_debug: {
        title: 'Debug Utilities',
        eli5: 'One-off scripts for investigating issues.',
        summary: 'Ad-hoc diagnostics & reports.',
        how: 'One-off scripts and checks.',
        inputs: 'DB + logs.',
        outputs: 'Reports.',
        files: 'docs/codexreport-*'
    },
    health_monitor: {
        title: 'Health Monitor',
        eli5: 'Watches if systems are alive.',
        summary: 'Automation health checks.',
        how: 'Runs periodic checks and reports issues.',
        inputs: 'System state.',
        outputs: 'Alerts + logs.',
        files: 'bot/services/automation/health_monitor.py'
    },
    metrics_logger: {
        title: 'Metrics Logger',
        eli5: 'Writes system metrics over time.',
        summary: 'Collects telemetry for debugging.',
        how: 'Logs health stats on intervals.',
        inputs: 'Runtime metrics.',
        outputs: 'Metrics logs.',
        files: 'bot/services/automation/metrics_logger.py'
    },
    database_maintenance: {
        title: 'Database Maintenance',
        eli5: 'Keeps the database clean.',
        summary: 'Automated DB cleanup and checks.',
        how: 'Runs scheduled maintenance tasks.',
        inputs: 'DB tables.',
        outputs: 'Maintenance logs.',
        files: 'bot/services/automation/database_maintenance.py'
    },
    ws_client: {
        title: 'WS Client',
        eli5: 'Old websocket client (deprecated).',
        summary: 'Legacy websocket automation.',
        how: 'Previously used for live status.',
        inputs: 'Websocket events.',
        outputs: 'Deprecated.',
        files: 'bot/services/automation/ws_client.py'
    },
    stopwatch_scoring_tool: {
        title: 'Stopwatch Scoring Tool',
        eli5: 'Old script for stopwatch scoring.',
        summary: 'Sync stopwatch scoring helper.',
        how: 'Used by tools/session commands.',
        inputs: 'Rounds table.',
        outputs: 'Stopwatch scores.',
        files: 'tools/stopwatch_scoring.py'
    },
    core_checks: {
        title: 'Core Checks',
        eli5: 'Safety rules that stop bad commands.',
        summary: 'Shared validation and permission checks.',
        how: 'Used by cogs to validate inputs and permissions.',
        inputs: 'Command context + arguments.',
        outputs: 'Allow/deny decisions.',
        files: 'bot/core/checks.py'
    },
    core_utils: {
        title: 'Core Utils',
        eli5: 'Helper functions used everywhere.',
        summary: 'Shared helpers for formatting and logic.',
        how: 'Imported by multiple cogs and services.',
        inputs: 'Utility calls.',
        outputs: 'Reusable helpers.',
        files: 'bot/core/utils.py'
    },
    pagination_view: {
        title: 'Pagination View',
        eli5: 'Turns big lists into paged Discord embeds.',
        summary: 'Discord UI paginator.',
        how: 'Creates buttons + pages for long results.',
        inputs: 'Large lists.',
        outputs: 'Paged embed views.',
        files: 'bot/core/pagination_view.py'
    },
    lazy_pagination_view: {
        title: 'Lazy Pagination View',
        eli5: 'Loads pages only when needed.',
        summary: 'Deferred pagination for heavy data.',
        how: 'Fetches pages on demand.',
        inputs: 'Query callbacks.',
        outputs: 'Paged embed views.',
        files: 'bot/core/lazy_pagination_view.py'
    },
    endstats_pagination_view: {
        title: 'Endstats Pagination',
        eli5: 'Paginates awards and endstats lists.',
        summary: 'Endstats-specific pagination.',
        how: 'Specialized paginator for award views.',
        inputs: 'Awards data.',
        outputs: 'Paged award embeds.',
        files: 'bot/core/endstats_pagination_view.py'
    },
    stats_calculator: {
        title: 'Stats Calculator',
        eli5: 'Math formulas for ratios and percentages.',
        summary: 'Shared stat calculations (ratios, caps).',
        how: 'Provides reusable math helpers.',
        inputs: 'Numeric stats.',
        outputs: 'Calculated metrics.',
        files: 'bot/stats/calculator.py'
    },
    player_formatter: {
        title: 'Player Formatter',
        eli5: 'Turns raw stats into nice text lines.',
        summary: 'Formats player stats for embeds.',
        how: 'Builds clean strings and badges.',
        inputs: 'Player stats rows.',
        outputs: 'Formatted display strings.',
        files: 'bot/services/player_formatter.py'
    },
    image_generator: {
        title: 'Image Generator',
        eli5: 'Draws images for stats panels.',
        summary: 'Generates PNG visuals for Discord.',
        how: 'Renders charts and summary cards.',
        inputs: 'Stats + images.',
        outputs: 'PNG images.',
        files: 'bot/image_generator.py'
    },
    last_session_helpers: {
        title: 'Last Session Helpers',
        eli5: 'Helper math for !last_session.',
        summary: 'Utility helpers for session summaries.',
        how: 'Used by last_session cog and services.',
        inputs: 'Session rows.',
        outputs: 'Derived aggregates + charts.',
        files: 'bot/last_session_helpers.py'
    },
    hybrid_processing_helpers: {
        title: 'Hybrid Processing Helpers',
        eli5: 'Glue code for old + new pipelines.',
        summary: 'Compatibility helpers for mixed pipelines.',
        how: 'Bridges legacy and new imports.',
        inputs: 'Parsed stats.',
        outputs: 'Normalized rows.',
        files: 'bot/hybrid_processing_helpers.py'
    },
    insert_helpers: {
        title: 'Insert Helpers',
        eli5: 'Helper methods for database inserts.',
        summary: 'Reusable insert utilities.',
        how: 'Shared DB insert logic.',
        inputs: 'Parsed stats.',
        outputs: 'DB insert payloads.',
        files: 'bot/insert_helpers.py'
    },
    helper_remove_duplicates: {
        title: 'Remove Duplicates',
        eli5: 'Cleanup helper for duplicate rows.',
        summary: 'Utility to remove duplicate stats.',
        how: 'Run manually when duplicates appear.',
        inputs: 'DB rows.',
        outputs: 'Cleaned tables.',
        files: 'bot/remove_duplicates.py'
    },
    retro_text_stats: {
        title: 'Retro Text Stats',
        eli5: 'Old-school text report output.',
        summary: 'Legacy text stats generator.',
        how: 'Builds ANSI/text summaries.',
        inputs: 'Aggregated stats.',
        outputs: 'Text report.',
        files: 'bot/retro_text_stats.py'
    },
    retro_viz: {
        title: 'Retro Viz',
        eli5: 'Old-school charts and visuals.',
        summary: 'Legacy visualization generator.',
        how: 'Builds charts for reports.',
        inputs: 'Aggregated stats.',
        outputs: 'Chart images.',
        files: 'bot/retro_viz.py'
    },
    bot_config: {
        title: 'Bot Config (Python)',
        eli5: 'Main bot settings file.',
        summary: 'Python config for bot runtime.',
        how: 'Loaded at bot startup.',
        inputs: 'Config values.',
        outputs: 'Runtime settings.',
        files: 'bot/config.py'
    },
    bot_config_json: {
        title: 'Bot Config (JSON)',
        eli5: 'JSON config for bot settings.',
        summary: 'Secondary config values.',
        how: 'Read by the bot for settings.',
        inputs: 'Config values.',
        outputs: 'Runtime settings.',
        files: 'bot/config.json'
    },
    bot_fiveeyes_config: {
        title: 'FiveEyes Config',
        eli5: 'Config for synergy analytics.',
        summary: 'Toggles and settings for synergy analytics.',
        how: 'Read when FiveEyes is enabled.',
        inputs: 'Config values.',
        outputs: 'Analytics settings.',
        files: 'bot/fiveeyes_config.json'
    },
    website_service_unit: {
        title: 'Website Systemd Service',
        eli5: 'Keeps the website running.',
        summary: 'Systemd service for the FastAPI app.',
        how: 'Starts and restarts the website API.',
        inputs: 'Systemd unit config.',
        outputs: 'Running API service.',
        files: 'website/etlegacy-website.service'
    },
    website_backend_main: {
        title: 'Website Backend App',
        eli5: 'FastAPI app entry point.',
        summary: 'Main FastAPI application for website.',
        how: 'Mounts routes and middleware.',
        inputs: 'HTTP requests.',
        outputs: 'API responses.',
        files: 'website/backend/main.py'
    },
    website_backend_dependencies: {
        title: 'Website Dependencies',
        eli5: 'Dependency wiring for FastAPI.',
        summary: 'Dependency injection helpers.',
        how: 'Provides DB adapters and config.',
        inputs: 'Request context.',
        outputs: 'Injected services.',
        files: 'website/backend/dependencies.py'
    },
    website_backend_logging: {
        title: 'Website Logging Config',
        eli5: 'Logging setup for the website.',
        summary: 'Logging and formatting for backend.',
        how: 'Defines loggers + formatters.',
        inputs: 'Log events.',
        outputs: 'Log files.',
        files: 'website/backend/logging_config.py'
    },
    website_backend_local_db: {
        title: 'Website Local DB Adapter',
        eli5: 'SQLite adapter for local testing.',
        summary: 'Local DB adapter for dev.',
        how: 'Provides SQLite access.',
        inputs: 'SQL queries.',
        outputs: 'Query results.',
        files: 'website/backend/local_database_adapter.py'
    },
    website_backend_init_db: {
        title: 'Website Init DB',
        eli5: 'Bootstraps the website database.',
        summary: 'Database initialization helpers.',
        how: 'Creates required tables if needed.',
        inputs: 'DB connection.',
        outputs: 'Initialized schema.',
        files: 'website/backend/init_db.py'
    },
    website_backend_check_bot_db: {
        title: 'Website Check Bot DB',
        eli5: 'Debug script for bot DB access.',
        summary: 'Checks database wiring for the website.',
        how: 'Runs local checks and prints results.',
        inputs: 'DB connection.',
        outputs: 'Debug output.',
        files: 'website/backend/check_bot_db.py'
    },
    website_backend_check_schema: {
        title: 'Website Check Schema',
        eli5: 'Debug script for schema health.',
        summary: 'Validates schema availability.',
        how: 'Runs schema queries.',
        inputs: 'DB connection.',
        outputs: 'Schema report.',
        files: 'website/backend/check_schema.py'
    },
    website_backend_check_stats_schema: {
        title: 'Website Check Stats Schema',
        eli5: 'Debug script for stats tables.',
        summary: 'Checks stats table structure.',
        how: 'Runs schema queries on stats tables.',
        inputs: 'DB connection.',
        outputs: 'Schema report.',
        files: 'website/backend/check_stats_schema.py'
    },
    website_backend_debug_player_stats: {
        title: 'Website Debug Player Stats',
        eli5: 'Debug script for player stats.',
        summary: 'Inspects player stats rows.',
        how: 'Runs targeted debug queries.',
        inputs: 'DB connection.',
        outputs: 'Debug output.',
        files: 'website/backend/debug_player_stats.py'
    },
    website_backend_debug_records: {
        title: 'Website Debug Records',
        eli5: 'Debug script for record data.',
        summary: 'Inspects records and summaries.',
        how: 'Runs targeted debug queries.',
        inputs: 'DB connection.',
        outputs: 'Debug output.',
        files: 'website/backend/debug_records.py'
    },
    website_logging_middleware: {
        title: 'Website Logging Middleware',
        eli5: 'Logs every API request.',
        summary: 'FastAPI middleware for request logging.',
        how: 'Wraps requests and records timing.',
        inputs: 'HTTP requests.',
        outputs: 'Log entries.',
        files: 'website/backend/middleware/logging_middleware.py'
    },
    bot_setup_automation: {
        title: 'Bot Setup Automation',
        eli5: 'Installer script for automation tools.',
        summary: 'Bootstraps automation services.',
        how: 'Run once during setup.',
        inputs: 'System config.',
        outputs: 'Automation setup.',
        files: 'bot/setup_automation.py'
    },
    bot_integrate_automation: {
        title: 'Integrate Automation',
        eli5: 'Connects automation into the bot.',
        summary: 'Wires automation services into runtime.',
        how: 'Run during setup or upgrades.',
        inputs: 'Bot config.',
        outputs: 'Automation integration.',
        files: 'bot/integrate_automation.py'
    },
    bot_automation_architecture: {
        title: 'Automation Architecture',
        eli5: 'Notes on how automation fits together.',
        summary: 'Documentation for automation design.',
        how: 'Reference during setup.',
        inputs: 'Architecture notes.',
        outputs: 'Planning reference.',
        files: 'bot/automation_architecture.py'
    },
    bot_automation_enhancements: {
        title: 'Automation Enhancements',
        eli5: 'Ideas for improving automation.',
        summary: 'Enhancement notes for automation.',
        how: 'Reference during upgrades.',
        inputs: 'Enhancement notes.',
        outputs: 'Planning reference.',
        files: 'bot/automation_enhancements.py'
    },
    bot_check_db: {
        title: 'Bot Check DB',
        eli5: 'Quick DB connectivity check.',
        summary: 'Manual DB connectivity test.',
        how: 'Run during troubleshooting.',
        inputs: 'DB config.',
        outputs: 'Connectivity result.',
        files: 'bot/check_db.py'
    },
    bot_last_session_redesigned: {
        title: 'Last Session (Redesign)',
        eli5: 'Prototype of a newer session layout.',
        summary: 'Experimental redesign for session display.',
        how: 'Used during experimentation.',
        inputs: 'Session stats.',
        outputs: 'Prototype formatting.',
        files: 'bot/last_session_redesigned_impl.py'
    }
};

const METRIC_DETAILS = {
    kills: {
        title: 'Kills',
        eli5: 'How many enemies a player killed.',
        summary: 'Total confirmed kills per player.',
        how: 'Summed from weapon stats + Lua totals.',
        inputs: 'Weapon stats, Lua fields.',
        outputs: 'player_comprehensive_stats.kills',
        files: 'bot/community_stats_parser.py'
    },
    deaths: {
        title: 'Deaths',
        eli5: 'How many times a player died.',
        summary: 'Total deaths per player.',
        how: 'Tracked in weapon stats and Lua totals.',
        inputs: 'Weapon stats.',
        outputs: 'player_comprehensive_stats.deaths',
        files: 'bot/community_stats_parser.py'
    },
    gibs: {
        title: 'Gibs',
        eli5: 'How many times a player gibbed enemies.',
        summary: 'Gibs caused (Lua tab field).',
        how: 'Pulled from TAB[4] in stats file.',
        inputs: 'Lua stats field.',
        outputs: 'player_comprehensive_stats.gibs',
        files: 'bot/community_stats_parser.py'
    },
    revives: {
        title: 'Revives',
        eli5: 'How many teammates a player revived.',
        summary: 'Revives given to teammates.',
        how: 'Pulled from TAB[37] in stats file.',
        inputs: 'Lua stats field.',
        outputs: 'player_comprehensive_stats.revives_given',
        files: 'bot/community_stats_parser.py'
    },
    dpm: {
        title: 'DPM',
        eli5: 'Damage per minute (how fast damage is dealt).',
        summary: 'Damage per minute (weighted).',
        how: 'Uses time_played_seconds as denominator.',
        inputs: 'damage_given + time_played_seconds.',
        outputs: 'weighted DPM.',
        files: 'bot/services/session_stats_aggregator.py'
    },
    time_dead: {
        title: 'Time Dead',
        eli5: 'Minutes spent dead.',
        summary: 'Minutes spent dead (Lua field).',
        how: 'Reads TAB[25] (minutes). Capped against time_played_seconds in summaries.',
        inputs: 'Lua stats field (time_dead_minutes).',
        outputs: 'player_comprehensive_stats.time_dead_minutes',
        files: 'bot/community_stats_parser.py'
    },
    time_denied: {
        title: 'Time Denied',
        eli5: 'Seconds the enemy was dead because of you.',
        summary: 'Seconds enemies were dead due to your damage.',
        how: 'Reads TAB[28] (seconds). Displayed as MM:SS in embeds.',
        inputs: 'Lua stats field (denied_playtime).',
        outputs: 'player_comprehensive_stats.denied_playtime',
        files: 'bot/community_stats_parser.py'
    },
    accuracy: {
        title: 'Accuracy',
        eli5: 'Percent of shots that hit.',
        summary: 'Hits / shots * 100.',
        how: 'Calculated from weapon stats.',
        inputs: 'Weapon hits + shots.',
        outputs: 'player_comprehensive_stats.accuracy',
        files: 'bot/community_stats_parser.py'
    }
};

const LUA_R2_ONLY_FIELDS = [
    'xp',
    'death_spree',
    'kill_assists',
    'headshot_kills',
    'objectives_stolen',
    'dynamites_planted',
    'times_revived',
    'time_dead_ratio',
    'time_dead_minutes',
    'useful_kills',
    'denied_playtime',
    'revives_given'
];

const LUA_TIMING_FIELDS = new Set([
    'time_played_minutes',
    'time_dead_ratio',
    'time_dead_minutes',
    'denied_playtime'
]);

const LUA_FIELD_MAP = [
    { idx: 0, field: 'damage_given', units: 'points', note: 'Player damage dealt' },
    { idx: 1, field: 'damage_received', units: 'points', note: 'Damage taken' },
    { idx: 2, field: 'team_damage_given', units: 'points', note: 'Friendly damage dealt' },
    { idx: 3, field: 'team_damage_received', units: 'points', note: 'Friendly damage taken' },
    { idx: 4, field: 'gibs', units: 'count', note: 'Gibs caused' },
    { idx: 5, field: 'self_kills', units: 'count', note: 'Self kills' },
    { idx: 6, field: 'team_kills', units: 'count', note: 'Team kills' },
    { idx: 7, field: 'team_gibs', units: 'count', note: 'Team gibs' },
    { idx: 8, field: 'time_played_percent', units: 'percent', note: 'Percent of round played' },
    { idx: 9, field: 'xp', units: 'points', note: 'R2-only' },
    { idx: 10, field: 'killing_spree', units: 'count', note: 'Best killing spree' },
    { idx: 11, field: 'death_spree', units: 'count', note: 'R2-only' },
    { idx: 12, field: 'kill_assists', units: 'count', note: 'R2-only' },
    { idx: 13, field: 'kill_steals', units: 'count', note: 'Kill steals' },
    { idx: 14, field: 'headshot_kills', units: 'count', note: 'R2-only' },
    { idx: 15, field: 'objectives_stolen', units: 'count', note: 'R2-only' },
    { idx: 16, field: 'objectives_returned', units: 'count', note: 'Objective returns' },
    { idx: 17, field: 'dynamites_planted', units: 'count', note: 'R2-only' },
    { idx: 18, field: 'dynamites_defused', units: 'count', note: 'Defuses' },
    { idx: 19, field: 'times_revived', units: 'count', note: 'R2-only' },
    { idx: 20, field: 'bullets_fired', units: 'count', note: 'Shots fired' },
    { idx: 21, field: 'dpm', units: 'damage/min', note: 'Lua reported' },
    { idx: 22, field: 'time_played_minutes', units: 'minutes', note: 'Lua time played' },
    { idx: 23, field: 'tank_meatshield', units: 'score', note: 'Refuses to die score' },
    { idx: 24, field: 'time_dead_ratio', units: 'percent', note: 'R2-only' },
    { idx: 25, field: 'time_dead_minutes', units: 'minutes', note: 'R2-only' },
    { idx: 26, field: 'kd_ratio', units: 'ratio', note: 'Lua KD ratio' },
    { idx: 27, field: 'useful_kills', units: 'count', note: 'R2-only' },
    { idx: 28, field: 'denied_playtime', units: 'seconds', note: 'R2-only' },
    { idx: 29, field: 'multikill_2x', units: 'count', note: 'Double kills' },
    { idx: 30, field: 'multikill_3x', units: 'count', note: 'Triple kills' },
    { idx: 31, field: 'multikill_4x', units: 'count', note: 'Quad kills' },
    { idx: 32, field: 'multikill_5x', units: 'count', note: 'Mega kills' },
    { idx: 33, field: 'multikill_6x', units: 'count', note: 'Ultra kills' },
    { idx: 34, field: 'useless_kills', units: 'count', note: 'Low impact kills' },
    { idx: 35, field: 'full_selfkills', units: 'count', note: 'Full selfkills' },
    { idx: 36, field: 'repairs_constructions', units: 'count', note: 'Repairs + constructions' },
    { idx: 37, field: 'revives_given', units: 'count', note: 'R2-only' }
];

const LUA_WEAPON_ENUM = [
    { id: 0, name: 'WS_KNIFE' },
    { id: 1, name: 'WS_KNIFE_KBAR' },
    { id: 2, name: 'WS_LUGER' },
    { id: 3, name: 'WS_COLT' },
    { id: 4, name: 'WS_MP40' },
    { id: 5, name: 'WS_THOMPSON' },
    { id: 6, name: 'WS_STEN' },
    { id: 7, name: 'WS_FG42' },
    { id: 8, name: 'WS_PANZERFAUST' },
    { id: 9, name: 'WS_BAZOOKA' },
    { id: 10, name: 'WS_FLAMETHROWER' },
    { id: 11, name: 'WS_GRENADE' },
    { id: 12, name: 'WS_MORTAR' },
    { id: 13, name: 'WS_MORTAR2' },
    { id: 14, name: 'WS_DYNAMITE' },
    { id: 15, name: 'WS_AIRSTRIKE' },
    { id: 16, name: 'WS_ARTILLERY' },
    { id: 17, name: 'WS_SATCHEL' },
    { id: 18, name: 'WS_GRENADELAUNCHER' },
    { id: 19, name: 'WS_LANDMINE' },
    { id: 20, name: 'WS_MG42' },
    { id: 21, name: 'WS_BROWNING' },
    { id: 22, name: 'WS_CARBINE' },
    { id: 23, name: 'WS_KAR98' },
    { id: 24, name: 'WS_GARAND' },
    { id: 25, name: 'WS_K43' },
    { id: 26, name: 'WS_MP34' },
    { id: 27, name: 'WS_SYRINGE' }
];

const LUA_WEAPON_BLOCK = [
    'Weapon mask (bitfield) comes first',
    'For each weapon bit set → 5 numbers:',
    'hits, shots, kills, deaths, headshots',
    'Example: mask 5 → includes weapon 0 + 2',
    'Parsed in bot/community_stats_parser.py'
];

const LUA_FILE_LOCATIONS = [
    { label: 'Main gamestats Lua', value: 'server/c0rnp0rn7.lua', note: 'Active stats exporter' },
    { label: 'Legacy gamestats Lua', value: 'server/c0rnp0rn.lua', note: 'Older variant / backup' },
    { label: 'Alternate variant', value: 'c0rnp0rn7real.lua', note: 'Legacy variant' },
    { label: 'Endstats awards', value: 'endstats.lua', note: 'Awards output' },
    { label: 'Webhook timing', value: 'vps_scripts/stats_discord_webhook.lua', note: 'Accurate timing + teams' },
    { label: 'Proximity telemetry', value: 'proximity_tracker.lua', note: 'Prototype tracking' }
];

const LUA_SCRIPT_CARDS = [
    {
        title: 'c0rnp0rn7.lua (Gamestats)',
        subtitle: 'Main per-round stats file.',
        outputs: 'gamestats/*.txt + weapon stats lines',
        chips: [
            { label: 'weapon hits/shots', kind: 'default' },
            { label: 'kills/deaths', kind: 'default' },
            { label: 'damage given/received', kind: 'default' },
            { label: 'objectives + revives', kind: 'default' },
            { label: 'time_played_minutes', kind: 'timing' },
            { label: 'time_dead_minutes', kind: 'timing' },
            { label: 'time_dead_ratio', kind: 'timing' },
            { label: 'denied_playtime', kind: 'timing' }
        ],
        notes: 'Round 2 files are cumulative; R2-only fields should NOT be subtracted.'
    },
    {
        title: 'c0rnp0rn.lua (Legacy)',
        subtitle: 'Older gamestats exporter.',
        outputs: 'gamestats/*.txt',
        chips: [
            { label: 'legacy format', kind: 'default' },
            { label: 'timing fields', kind: 'timing' }
        ],
        notes: 'Keep for reference or fallback.'
    },
    {
        title: 'c0rnp0rn7real.lua (Legacy)',
        subtitle: 'Alternate variant of gamestats exporter.',
        outputs: 'gamestats/*.txt',
        chips: [
            { label: 'legacy variant', kind: 'default' },
            { label: 'timing fields', kind: 'timing' }
        ],
        notes: 'Not used in production unless swapped in.'
    },
    {
        title: 'endstats.lua (Awards)',
        subtitle: 'End-of-round awards file.',
        outputs: 'endstats/*.txt',
        chips: [
            { label: 'most damage', kind: 'default' },
            { label: 'most kills', kind: 'default' },
            { label: 'most revives', kind: 'default' },
            { label: 'most playtime denied', kind: 'timing' },
            { label: 'highest accuracy', kind: 'default' }
        ],
        notes: 'Parsed into award categories in bot/endstats_parser.py.'
    },
    {
        title: 'stats_discord_webhook.lua',
        subtitle: 'Accurate timing + team snapshot.',
        outputs: 'Discord webhook + lua_round_teams + gametimes.json fallback',
        chips: [
            { label: 'Lua_Playtime', kind: 'timing' },
            { label: 'Lua_Warmup', kind: 'timing' },
            { label: 'Lua_Pauses_JSON', kind: 'timing' },
            { label: 'RoundStart/RoundEnd', kind: 'timing' },
            { label: 'Surrender info', kind: 'webhook' },
            { label: 'Axis/Allies score', kind: 'webhook' }
        ],
        notes: 'Fixes surrender timing vs gamestats files.'
    },
    {
        title: 'proximity_tracker.lua',
        subtitle: 'Prototype proximity telemetry.',
        outputs: 'proximity/*_positions.txt, *_combat.txt, *_engagements.txt, *_heatmap.txt',
        chips: [
            { label: 'positions', kind: 'default' },
            { label: 'engagements', kind: 'default' },
            { label: 'kill heatmap', kind: 'default' }
        ],
        notes: 'Prototype pipeline for proximity analytics.'
    }
];

const LUA_TIMING_FOCUS = [
    {
        title: 'Hooks That Start/Stop Timers',
        lines: [
            'et_Obituary: sets death_time[victim] + denies[victim]',
            'et_ClientSpawn: closes death_time_total + denied_playtime',
            'et_ClientDisconnect / team change: flushes timers',
            'All raw timers are in milliseconds'
        ]
    },
    {
        title: 'Raw → Output Conversions (Lua)',
        lines: [
            'time_played_minutes = (time_axis + time_allies) / 60000',
            'time_dead_minutes = death_time_total / 60000',
            'time_dead_ratio = (death_time_total / tp) * 100',
            'denied_playtime = floor(topshots[16] / 1000) seconds'
        ]
    },
    {
        title: 'Parser + Database Fields',
        lines: [
            'community_stats_parser.py maps timing fields into objective_stats',
            'player_comprehensive_stats: time_dead_minutes, time_dead_ratio, denied_playtime',
            'Last-session summary reads the DB values directly'
        ]
    },
    {
        title: 'Aggregation + Caps',
        lines: [
            'SessionStatsAggregator caps time_dead vs time_played_seconds',
            'Session views display denied_playtime as MM:SS',
            'Potential bug zone: ms ↔ seconds ↔ minutes conversions'
        ]
    }
];

const DEV_TIMELINE = [
    {
        date: 'Foundations',
        title: 'Lua creates the raw stats files',
        need: 'ET:Legacy does not store player history by default.',
        change: 'c0rnp0rn7.lua hooks game events and writes gamestats/*.txt each round.',
        outcome: 'We finally have raw data to parse and show on Discord.',
        tags: ['lua', 'gamestats', 'foundation'],
        refs: ['docs/PROJECT_OVERVIEW.md']
    },
    {
        date: 'Early Pipeline',
        title: 'Move files from game server to bot server',
        need: 'Stats files live on the game server, but the bot runs elsewhere.',
        change: 'SSH polling copies new gamestats into bot/local_stats for parsing.',
        outcome: 'Reliable ingestion even if real-time systems fail.',
        tags: ['ingest', 'ssh', 'reliability'],
        refs: ['docs/PROJECT_OVERVIEW.md']
    },
    {
        date: 'Core Parser',
        title: 'Translate raw files into database rows',
        need: 'Raw tab files are unreadable and not queryable.',
        change: 'community_stats_parser.py extracts player + weapon stats and writes to player_comprehensive_stats.',
        outcome: 'Bot commands can query clean stats instantly.',
        tags: ['parser', 'database', 'stats'],
        refs: ['docs/TECHNICAL_OVERVIEW.md']
    },
    {
        date: 'Session Logic',
        title: 'Group rounds into sessions for !last_session',
        need: 'Players think in sessions, not isolated rounds.',
        change: 'Rounds within a 60-minute gap become one gaming session.',
        outcome: 'Discord can show full session summaries.',
        tags: ['sessions', 'discord', 'analytics'],
        refs: ['docs/PROJECT_OVERVIEW.md', 'docs/TECHNICAL_OVERVIEW.md']
    },
    {
        date: '2025-12-04',
        title: 'Auto-post full round stats to Discord',
        need: 'Manual commands were too slow; players wanted instant results.',
        change: 'Round Publisher Service posts rich embeds after each round. WebSocket push speeds detection.',
        outcome: 'Stats appear in Discord automatically within seconds.',
        tags: ['discord', 'rounds', 'realtime'],
        refs: ['docs/CHANGELOG.md']
    },
    {
        date: '2026-01-14',
        title: 'Endstats awards pipeline',
        need: 'Players wanted awards and highlights, not just raw stats.',
        change: 'endstats.lua + endstats parser added awards tracking.',
        outcome: 'Discord posts award summaries and fun stats.',
        tags: ['endstats', 'awards', 'discord'],
        refs: ['docs/SESSION_INDEX.md']
    },
    {
        date: '2026-01',
        title: 'Lua webhook for real-time timing',
        need: 'Surrender rounds had wrong timing and SSH polling was slow.',
        change: 'stats_discord_webhook.lua sends RoundStart/End timing directly to the bot.',
        outcome: 'Accurate playtime + faster Discord updates.',
        tags: ['webhook', 'timing', 'discord'],
        refs: ['docs/CHANGELOG.md', 'docs/PROJECT_OVERVIEW.md']
    },
    {
        date: '2026-02-01',
        title: 'Time-dead calculation fix',
        need: 'R2 rounds were undercounting time dead in session summaries.',
        change: 'Use time_dead_minutes directly instead of ratio * playtime.',
        outcome: 'Discord session summaries show correct dead time.',
        tags: ['timing', 'bugfix', 'sessions'],
        refs: ['docs/CHANGELOG.md']
    },
    {
        date: '2026-02',
        title: 'Admin atlas + visual onboarding',
        need: 'Non-coders needed a clear picture of what works and how data flows.',
        change: 'Admin panel shows system maps, timing pipelines, and health lights.',
        outcome: 'Faster troubleshooting and shared understanding.',
        tags: ['admin', 'onboarding', 'ops'],
        refs: ['docs/WEBSITE_UI_UPGRADE_PLAN_2026-02-03.md']
    }
];

const FLOW_COLORS = {
    core: 'rgba(56, 189, 248, 0.6)',
    stats: 'rgba(34, 197, 94, 0.7)',
    endstats: 'rgba(251, 191, 36, 0.7)',
    webhook: 'rgba(244, 63, 94, 0.7)',
    timing: 'rgba(244, 114, 182, 0.75)',
    proximity: 'rgba(14, 165, 233, 0.7)',
    web: 'rgba(129, 140, 248, 0.7)',
    ops: 'rgba(148, 163, 184, 0.6)'
};

const SVG_NS = 'http://www.w3.org/2000/svg';

function getOffsetRect(element, container) {
    let x = 0;
    let y = 0;
    let current = element;
    while (current && current !== container) {
        x += current.offsetLeft;
        y += current.offsetTop;
        current = current.offsetParent;
    }
    return {
        left: x,
        top: y,
        right: x + element.offsetWidth,
        bottom: y + element.offsetHeight,
        width: element.offsetWidth,
        height: element.offsetHeight
    };
}

const FLOW_CONNECTIONS = [
    { from: 'et_server', to: 'server_watchdog', type: 'ops', label: 'Health checks + restarts' },
    { from: 'et_server', to: 'lua_modules', type: 'core', label: 'Live game events' },
    { from: 'lua_modules', to: 'lua_c0rnp0rn7', type: 'stats', label: 'Write stats files' },
    { from: 'lua_modules', to: 'lua_endstats', type: 'endstats', label: 'Write awards files' },
    { from: 'lua_modules', to: 'lua_webhook', type: 'webhook', label: 'Send timing pings' },
    { from: 'lua_modules', to: 'lua_proximity', type: 'proximity', label: 'Write proximity logs' },
    { from: 'lua_c0rnp0rn7', to: 'stats_ingest', type: 'stats', label: 'gamestats files' },
    { from: 'stats_ingest', to: 'stats_parser', type: 'stats', label: 'New file queue' },
    { from: 'stats_parser', to: 'differential_calc', type: 'stats', label: 'Round 2 split' },
    { from: 'differential_calc', to: 'validation_caps', type: 'stats', label: 'Sanity checks' },
    { from: 'validation_caps', to: 'db_adapter', type: 'stats', label: 'Ready for DB' },
    { from: 'lua_endstats', to: 'endstats_ingest', type: 'endstats', label: 'endstats files' },
    { from: 'endstats_ingest', to: 'endstats_parser', type: 'endstats', label: 'Awards queue' },
    { from: 'endstats_parser', to: 'endstats_aggregator', type: 'endstats', label: 'Awards summary' },
    { from: 'endstats_parser', to: 'db_adapter', type: 'endstats', label: 'Awards rows' },
    { from: 'lua_webhook', to: 'webhook_receiver', type: 'webhook', label: 'HTTP POST payload' },
    { from: 'webhook_receiver', to: 'db_adapter', type: 'webhook', label: 'Timing rows' },
    { from: 'lua_proximity', to: 'proximity_ingest', type: 'proximity', label: 'Proximity logs' },
    { from: 'proximity_ingest', to: 'proximity_parser', type: 'proximity', label: 'Engagement queue' },
    { from: 'proximity_parser', to: 'db_adapter', type: 'proximity', label: 'Proximity rows' },
    { from: 'db_adapter', to: 'postgres', type: 'core', label: 'DB writes + reads' },
    { from: 'postgres', to: 'session_aggregator', type: 'stats', label: 'Session queries' },
    { from: 'session_aggregator', to: 'session_embed_builder', type: 'stats', label: 'Session totals' },
    { from: 'session_aggregator', to: 'session_view_handlers', type: 'stats', label: 'View-specific data' },
    { from: 'session_aggregator', to: 'graph_generator', type: 'stats', label: 'Chart datasets' },
    { from: 'postgres', to: 'round_publisher', type: 'stats', label: 'Round stats' },
    { from: 'postgres', to: 'timing_comparison', type: 'webhook', label: 'Timing comparison query' },
    { from: 'postgres', to: 'endstats_aggregator', type: 'endstats', label: 'Award data' },
    { from: 'session_embed_builder', to: 'discord_bot', type: 'stats', label: 'Session embed' },
    { from: 'session_view_handlers', to: 'discord_bot', type: 'stats', label: 'Alternate embeds' },
    { from: 'graph_generator', to: 'discord_bot', type: 'stats', label: 'PNG charts' },
    { from: 'round_publisher', to: 'discord_bot', type: 'stats', label: 'Round embed' },
    { from: 'endstats_aggregator', to: 'discord_bot', type: 'endstats', label: 'Awards embed' },
    { from: 'timing_comparison', to: 'discord_bot', type: 'webhook', label: 'Debug report' },
    { from: 'postgres', to: 'proximity_cog', type: 'proximity', label: 'Proximity queries' },
    { from: 'proximity_cog', to: 'discord_bot', type: 'proximity', label: 'Proximity commands' },
    { from: 'postgres', to: 'website_api', type: 'web', label: 'API queries' },
    { from: 'website_api', to: 'website_frontend', type: 'web', label: 'JSON responses' },
    { from: 'website_frontend', to: 'admin_panel', type: 'web', label: 'Admin UI data' },
    { from: 'postgres', to: 'proximity_api', type: 'proximity', label: 'Proximity endpoints' },
    { from: 'proximity_api', to: 'proximity_ui', type: 'proximity', label: 'Prototype UI data' }
];

const FULL_COGS = [
    'stats_cog',
    'leaderboard_cog',
    'last_session_cog',
    'session_cog',
    'session_management_cog',
    'team_cog',
    'team_management_cog',
    'matchup_cog',
    'analytics_cog',
    'synergy_analytics',
    'achievements_cog',
    'predictions_cog',
    'admin_predictions_cog',
    'admin_cog',
    'permission_management_cog',
    'link_cog',
    'proximity_cog',
    'server_control',
    'sync_cog',
    'automation_commands'
];

const FULL_SERVICES = [
    'session_aggregator',
    'session_embed_builder',
    'session_view_handlers',
    'session_data_service',
    'round_publisher',
    'graph_generator',
    'image_generator',
    'endstats_aggregator',
    'timing_comparison',
    'timing_debug_service',
    'player_analytics_service',
    'player_badge_service',
    'player_formatter',
    'player_display_name_service',
    'matchup_analytics_service',
    'prediction_engine',
    'prediction_embed_builder',
    'stopwatch_scoring_service'
];

const FULL_CORE = [
    'achievement_system',
    'advanced_team_detector',
    'core_checks',
    'core_utils',
    'endstats_pagination_view',
    'lazy_pagination_view',
    'pagination_view',
    'stats_calculator',
    'team_detector_integration',
    'substitution_detector',
    'match_tracker',
    'team_manager',
    'team_history',
    'season_manager',
    'stats_cache',
    'frag_potential',
    'round_linker'
];

const FULL_TABLES = [
    'table_rounds',
    'table_player_stats',
    'table_weapon_stats',
    'table_processed_files',
    'table_gaming_sessions',
    'table_session_rounds',
    'table_lua_round_teams',
    'table_proximity'
];

const FULL_WEBSITE_ROUTERS = [
    'website_router_api',
    'website_router_auth',
    'website_router_predictions'
];

const FULL_WEBSITE_SERVICES = [
    'website_session_data_service',
    'voice_channel_tracker',
    'game_server_query'
];

const FULL_CONFIG_FILES = [
    { id: 'bot_config', label: 'bot/config.py', tag: 'Config' },
    { id: 'bot_config_json', label: 'bot/config.json', tag: 'Config' },
    { id: 'bot_fiveeyes_config', label: 'bot/fiveeyes_config.json', tag: 'Config' },
    { id: 'website_service_unit', label: 'etlegacy-website.service', tag: 'Service' }
];

const FULL_BOT_UTILITIES = [
    { id: 'last_session_helpers', label: 'last_session_helpers.py', tag: 'Helper' },
    { id: 'hybrid_processing_helpers', label: 'hybrid_processing_helpers.py', tag: 'Helper' },
    { id: 'insert_helpers', label: 'insert_helpers.py', tag: 'Helper' },
    { id: 'helper_remove_duplicates', label: 'remove_duplicates.py', tag: 'Helper' },
    { id: 'retro_text_stats', label: 'retro_text_stats.py', tag: 'Report' },
    { id: 'retro_viz', label: 'retro_viz.py', tag: 'Report' }
];

const FULL_BOT_MAINTENANCE = [
    { id: 'bot_setup_automation', label: 'bot/setup_automation.py', tag: 'Setup' },
    { id: 'bot_integrate_automation', label: 'bot/integrate_automation.py', tag: 'Setup' },
    { id: 'bot_automation_architecture', label: 'bot/automation_architecture.py', tag: 'Doc' },
    { id: 'bot_automation_enhancements', label: 'bot/automation_enhancements.py', tag: 'Doc' },
    { id: 'bot_check_db', label: 'bot/check_db.py', tag: 'Diag' },
    { id: 'bot_last_session_redesigned', label: 'bot/last_session_redesigned_impl.py', tag: 'Prototype' }
];

const FULL_DIAGNOSTIC_NODES = [
    { id: 'diag_check_all_rounds', label: 'check_all_rounds.py', tag: 'Diag' },
    { id: 'diag_check_duplicates', label: 'check_duplicates.py', tag: 'Diag' },
    { id: 'diag_check_playtime_issue', label: 'check_playtime_issue.py', tag: 'Diag' },
    { id: 'diag_check_session_boundary', label: 'check_session_boundary.py', tag: 'Diag' },
    { id: 'diag_check_sessions', label: 'check_sessions.py', tag: 'Diag' },
    { id: 'diag_reimport_missing', label: 'reimport_missing.py', tag: 'Diag' },
    { id: 'diag_remove_duplicates', label: 'remove_duplicates.py', tag: 'Diag' },
    { id: 'diag_test_import', label: 'test_import.py', tag: 'Diag' }
];

const FULL_DEV_TOOLS = [
    { id: 'tool_check_fstrings_balance', label: 'check_fstrings_balance.py', tag: 'Tool' },
    { id: 'tool_clean_conflicts_keep_head', label: 'clean_conflicts_keep_head.py', tag: 'Tool' },
    { id: 'tool_find_empty_f_braces', label: 'find_empty_f_braces.py', tag: 'Tool' },
    { id: 'tool_find_fstrings', label: 'find_fstrings.py', tag: 'Tool' },
    { id: 'tool_inspect_syntax', label: 'inspect_syntax.py', tag: 'Tool' }
];

const FULL_MAINTENANCE_SCRIPTS = [
    { id: 'script_audit_round_pairs', label: 'audit_round_pairs.py', tag: 'Script' },
    { id: 'script_backfill_endstats', label: 'backfill_endstats.py', tag: 'Script' },
    { id: 'script_backfill_full_selfkills', label: 'backfill_full_selfkills.py', tag: 'Script' },
    { id: 'script_backfill_gametimes', label: 'backfill_gametimes.py', tag: 'Script' },
    { id: 'script_backfill_lua_round_ids', label: 'backfill_lua_round_ids.py', tag: 'Script' },
    { id: 'script_bot_scrim_mode', label: 'bot_scrim_mode.py', tag: 'Script' },
    { id: 'script_debug_import', label: 'debug_import.py', tag: 'Script' },
    { id: 'script_generate_omnibot_botnames', label: 'generate_omnibot_botnames.py', tag: 'Script' },
    { id: 'script_generate_retro', label: 'generate_retro.py', tag: 'Script' },
    { id: 'script_generate_retro_text', label: 'generate_retro_text.py', tag: 'Script' },
    { id: 'script_objective_coords_to_lua', label: 'objective_coords_to_lua.py', tag: 'Script' },
    { id: 'script_omnibot_toggle', label: 'omnibot_toggle.py', tag: 'Script' },
    { id: 'script_rcon_command', label: 'rcon_command.py', tag: 'Script' },
    { id: 'script_run_retro_test', label: 'run_retro_test.py', tag: 'Script' },
    { id: 'script_smoke_pipeline', label: 'smoke_pipeline.py', tag: 'Script' },
    { id: 'script_smoke_team_consistency', label: 'smoke_team_consistency.py', tag: 'Script' },
    { id: 'script_sync_objective_placeholders', label: 'sync_objective_placeholders.py', tag: 'Script' },
    { id: 'script_system_smoke_tests', label: 'system_smoke_tests.sh', tag: 'Script' },
    { id: 'script_update_proximity_objectives', label: 'update_proximity_objectives_from_json.py', tag: 'Script' },
    { id: 'script_verify_proximity_schema', label: 'verify_proximity_schema.py', tag: 'Script' }
];

const FULL_WEBSITE_BACKEND_CORE = [
    { id: 'website_backend_main', label: 'backend/main.py', tag: 'Backend' },
    { id: 'website_backend_dependencies', label: 'backend/dependencies.py', tag: 'Backend' },
    { id: 'website_backend_logging', label: 'backend/logging_config.py', tag: 'Backend' },
    { id: 'website_backend_local_db', label: 'backend/local_database_adapter.py', tag: 'Backend' },
    { id: 'website_backend_init_db', label: 'backend/init_db.py', tag: 'Backend' },
    { id: 'website_backend_check_bot_db', label: 'backend/check_bot_db.py', tag: 'Debug' },
    { id: 'website_backend_check_schema', label: 'backend/check_schema.py', tag: 'Debug' },
    { id: 'website_backend_check_stats_schema', label: 'backend/check_stats_schema.py', tag: 'Debug' },
    { id: 'website_backend_debug_player_stats', label: 'backend/debug_player_stats.py', tag: 'Debug' },
    { id: 'website_backend_debug_records', label: 'backend/debug_records.py', tag: 'Debug' }
];

const FULL_WEBSITE_MIDDLEWARE = [
    { id: 'website_logging_middleware', label: 'backend/middleware/logging_middleware.py', tag: 'Middleware' }
];

const LUA_MAP_GROUPS = [
    {
        id: 'lua_scripts',
        title: 'Lua Scripts (Server)',
        nodes: [
            { id: 'lua_c0rnp0rn7', label: 'c0rnp0rn7.lua', tag: 'Lua', subtitle: 'Main stats exporter' },
            { id: 'lua_endstats', label: 'endstats.lua', tag: 'Lua', subtitle: 'Awards exporter' },
            { id: 'lua_webhook', label: 'stats_discord_webhook.lua', tag: 'Lua', subtitle: 'Timing webhook' },
            { id: 'lua_proximity', label: 'proximity_tracker.lua', tag: 'Lua', subtitle: 'Prototype telemetry' },
            { id: 'lua_c0rnp0rn', label: 'c0rnp0rn.lua', tag: 'Legacy', subtitle: 'Old format' },
            { id: 'lua_c0rnp0rn7real', label: 'c0rnp0rn7real.lua', tag: 'Legacy', subtitle: 'Legacy variant' }
        ]
    },
    {
        id: 'lua_hooks',
        title: 'c0rnp0rn7 Hooks',
        nodes: [
            { id: 'lua_et_initgame', label: 'et_InitGame()', tag: 'Hook', subtitle: 'Init arrays + config' },
            { id: 'lua_et_runframe', label: 'et_RunFrame()', tag: 'Hook', subtitle: 'Store stats + intermission' },
            { id: 'lua_et_obituary', label: 'et_Obituary()', tag: 'Hook', subtitle: 'Death + deny timers' },
            { id: 'lua_et_clientspawn', label: 'et_ClientSpawn()', tag: 'Hook', subtitle: 'Close timers' },
            { id: 'lua_et_clientdisconnect', label: 'et_ClientDisconnect()', tag: 'Hook', subtitle: 'Flush timers' },
            { id: 'lua_et_damage', label: 'et_Damage()', tag: 'Hook', subtitle: 'Hits + headshots' },
            { id: 'lua_et_print', label: 'et_Print()', tag: 'Hook', subtitle: 'Objective messages' },
            { id: 'lua_et_shutdown', label: 'et_ShutdownGame()', tag: 'Hook', subtitle: 'Force save' }
        ]
    },
    {
        id: 'lua_timing_core',
        title: 'Timing Core',
        nodes: [
            { id: 'lua_death_time', label: 'death_time[]', tag: 'Timer', subtitle: 'Set on death' },
            { id: 'lua_death_time_total', label: 'death_time_total[]', tag: 'Timer', subtitle: 'Accumulate ms dead' },
            { id: 'lua_denies_table', label: 'denies[]', tag: 'Timer', subtitle: 'Kill → denied timer' },
            { id: 'lua_denied_playtime', label: 'denied_playtime', tag: 'Timing', subtitle: 'topshots[16]', autoStatus: 'red' },
            { id: 'lua_time_played_pct', label: 'time_played %', tag: 'Timing', subtitle: 'sess.time_played' },
            { id: 'lua_time_played_minutes', label: 'time_played_min', tag: 'Timing', subtitle: 'tp/60' },
            { id: 'lua_time_dead_minutes', label: 'time_dead_min', tag: 'Timing', subtitle: 'ms/60000' },
            { id: 'lua_time_dead_ratio', label: 'time_dead_ratio', tag: 'Timing', subtitle: 'dead/played', autoStatus: 'red' }
        ]
    },
    {
        id: 'lua_stats_buffers',
        title: 'Stats Buffers',
        nodes: [
            { id: 'lua_topshots_array', label: 'topshots[]', tag: 'Buffer', subtitle: 'Sprees + DPM' },
            { id: 'lua_weapon_stats_buffer', label: 'weaponStats', tag: 'Buffer', subtitle: 'Hits/atts/kills' },
            { id: 'lua_round_header', label: 'Round header', tag: 'Meta', subtitle: 'Map + winner + time' },
            { id: 'lua_tab_fields', label: 'TAB fields', tag: 'Format', subtitle: 'Player stat line' }
        ]
    },
    {
        id: 'lua_outputs',
        title: 'Lua Outputs',
        nodes: [
            { id: 'lua_gamestats_file', label: 'gamestats/*.txt', tag: 'File', subtitle: 'Main output' },
            { id: 'lua_weaponstats_file', label: 'gamestats_*_ws.txt', tag: 'File', subtitle: 'Optional weapon file' },
            { id: 'lua_endstats_file', label: 'endstats/*.txt', tag: 'File', subtitle: 'Awards output' },
            { id: 'lua_webhook_payload', label: 'Webhook payload', tag: 'Webhook', subtitle: 'Round timing JSON' },
            { id: 'lua_proximity_logs', label: 'proximity logs', tag: 'File', subtitle: 'Prototype output' }
        ]
    },
    {
        id: 'lua_webhook_timing',
        title: 'Webhook Timing Script',
        nodes: [
            { id: 'lua_webhook_round_start', label: 'RoundStart hook', tag: 'Webhook', subtitle: 'Start timestamp' },
            { id: 'lua_webhook_round_end', label: 'RoundEnd hook', tag: 'Webhook', subtitle: 'End timestamp' },
            { id: 'webhook_receiver', label: 'Webhook Receiver', tag: 'Ingest', subtitle: 'Bot endpoint' },
            { id: 'table_lua_round_teams', label: 'lua_round_teams', tag: 'Table', subtitle: 'Timing table' }
        ]
    },
    {
        id: 'lua_downstream',
        title: 'Ingest + Usage',
        nodes: [
            { id: 'stats_ingest', label: 'Stats Ingest', tag: 'Ingest', subtitle: 'File watcher' },
            { id: 'stats_parser', label: 'Stats Parser', tag: 'Parser', subtitle: 'TAB decoding' },
            { id: 'differential_calc', label: 'R1/R2 Differential', tag: 'Logic', subtitle: 'Split round 2' },
            { id: 'validation_caps', label: 'Validation + Caps', tag: 'Guard', subtitle: 'Sanity checks' },
            { id: 'db_adapter', label: 'DB Adapter', tag: 'DB', subtitle: 'Writes rows' },
            { id: 'postgres', label: 'PostgreSQL', tag: 'DB', subtitle: 'Source of truth' },
            { id: 'session_aggregator', label: 'Session Aggregator', tag: 'Service', subtitle: 'Totals' },
            { id: 'session_embed_builder', label: 'Session Embed Builder', tag: 'Service', subtitle: '!last_session' },
            { id: 'discord_bot', label: 'Discord Bot', tag: 'Runtime', subtitle: 'Posts embeds' },
            { id: 'endstats_ingest', label: 'Endstats Ingest', tag: 'Ingest', subtitle: 'Award files' },
            { id: 'endstats_parser', label: 'Endstats Parser', tag: 'Parser', subtitle: 'Awards decode' },
            { id: 'endstats_aggregator', label: 'Endstats Aggregator', tag: 'Service', subtitle: 'Awards embeds' },
            { id: 'proximity_ingest', label: 'Proximity Ingest', tag: 'Ingest', subtitle: 'Prototype scan' },
            { id: 'proximity_parser', label: 'Proximity Parser', tag: 'Parser', subtitle: 'Prototype parse' }
        ]
    }
];

const FULL_MAP_GROUPS = [
    {
        id: 'core_topology',
        title: 'Core Topology (Servers + Database)',
        layout: 'core',
        nodes: [
            { id: 'core_game_server', label: 'puran.hehe.si (Game Server)', tag: 'Server', subtitle: 'ET:Legacy + Lua outputs', className: 'core-left' },
            { id: 'core_postgres', label: 'PostgreSQL (Central DB)', tag: 'DB', subtitle: 'Central source of truth', className: 'core-center' },
            { id: 'core_bot_web', label: 'Bot + Website Host', tag: 'Server', subtitle: 'Discord bot + API/UI', className: 'core-right' }
        ]
    },
    {
        id: 'infra',
        title: 'Infrastructure + Players',
        nodes: [
            { id: 'players', label: 'Players', tag: 'People' },
            { id: 'game_server_host', label: 'Game Server Host', tag: 'Server' },
            { id: 'bot_server_host', label: 'Stats/Bot/Website Host', tag: 'Server' }
        ]
    },
    {
        id: 'discord',
        title: 'Discord Platform',
        nodes: [
            { id: 'discord_cloud', label: 'Discord Cloud', tag: 'External' },
            { id: 'discord_text', label: 'Discord Text', tag: 'External' },
            { id: 'discord_voice', label: 'Discord Voice', tag: 'External' },
            { id: 'discord_webhook', label: 'Discord Webhook', tag: 'External' },
            { id: 'discord_control_channel', label: 'Control Channel', tag: 'Discord' },
            { id: 'discord_stats_channel', label: 'Stats Channel', tag: 'Discord' }
        ]
    },
    {
        id: 'game',
        title: 'Game Server + Lua',
        nodes: [
            { id: 'et_server', label: 'ET:Legacy Runtime', tag: 'Server' },
            { id: 'server_watchdog', label: 'Server Watchdog', tag: 'Ops' },
            { id: 'lua_modules', label: 'Lua Modules', tag: 'Lua' },
            { id: 'lua_c0rnp0rn7', label: 'c0rnp0rn7.lua', tag: 'Lua' },
            { id: 'lua_endstats', label: 'endstats.lua', tag: 'Lua' },
            { id: 'lua_webhook', label: 'stats_discord_webhook.lua', tag: 'Lua' },
            { id: 'lua_proximity', label: 'proximity_tracker.lua', tag: 'Lua' }
        ]
    },
    {
        id: 'round_outcomes',
        title: 'Round Outcomes + Filters',
        nodes: [
            { id: 'round_end_reason', label: 'Round End Reason', tag: 'Logic' },
            { id: 'round_completed', label: 'Completed Round', tag: 'Logic' },
            { id: 'round_surrender', label: 'Surrender Round', tag: 'Logic' },
            { id: 'round_timelimit', label: 'Time Limit Round', tag: 'Logic' },
            { id: 'round_cancelled', label: 'Cancelled Round', tag: 'Logic' },
            { id: 'round_substitution', label: 'Substitution Round', tag: 'Logic' },
            { id: 'round_status_filter', label: 'Round Status Filter', tag: 'Guard' }
        ]
    },
    {
        id: 'outputs',
        title: 'Raw Outputs',
        nodes: [
            { id: 'gamestats_files', label: 'gamestats/*.txt', tag: 'Files' },
            { id: 'endstats_files', label: 'endstats/*.txt', tag: 'Files' },
            { id: 'gametimes_files', label: 'gametimes.json', tag: 'Fallback' },
            { id: 'proximity_positions', label: '*_positions.txt', tag: 'Proximity' },
            { id: 'proximity_combat', label: '*_combat.txt', tag: 'Proximity' },
            { id: 'proximity_engagements', label: '*_engagements.txt', tag: 'Proximity' },
            { id: 'proximity_heatmap', label: '*_heatmap.txt', tag: 'Proximity' }
        ]
    },
    {
        id: 'webhook_relay',
        title: 'Webhook Relay',
        nodes: [
            { id: 'et_stats_webhook_service', label: 'et-stats-webhook.service', tag: 'Ops' },
            { id: 'stats_webhook_notify', label: 'stats_webhook_notify.py', tag: 'Webhook' },
            { id: 'webhook_security_gate', label: 'Webhook Security Gate', tag: 'Guard' },
            { id: 'webhook_trigger_handler', label: 'Webhook Trigger Handler', tag: 'Webhook' }
        ]
    },
    {
        id: 'ingest',
        title: 'Ingest + Automation',
        nodes: [
            { id: 'ssh_monitor', label: 'SSH Monitor', tag: 'Automation' },
            { id: 'ssh_handler', label: 'SSH Handler', tag: 'Automation' },
            { id: 'file_tracker', label: 'File Tracker', tag: 'Automation' },
            { id: 'file_repository', label: 'File Repository', tag: 'Storage' },
            { id: 'endstats_monitor', label: 'Endstats Monitor', tag: 'Ops' },
            { id: 'cache_refresher', label: 'Cache Refresher', tag: 'Ops' },
            { id: 'webhook_receiver', label: 'Webhook Receiver', tag: 'Webhook' },
            { id: 'stats_ingest', label: 'Stats Ingest', tag: 'Ingest' },
            { id: 'endstats_ingest', label: 'Endstats Ingest', tag: 'Ingest' },
            { id: 'proximity_ingest', label: 'Proximity Ingest', tag: 'Ingest' }
        ]
    },
    {
        id: 'parse',
        title: 'Parsing + Validation',
        nodes: [
            { id: 'stats_parser', label: 'Stats Parser', tag: 'Parser' },
            { id: 'differential_calc', label: 'R1/R2 Differential', tag: 'Logic' },
            { id: 'validation_caps', label: 'Validation + Caps', tag: 'Guard' },
            { id: 'endstats_parser', label: 'Endstats Parser', tag: 'Parser' },
            { id: 'proximity_parser', label: 'Proximity Parser', tag: 'Parser' },
            { id: 'round_linker', label: 'Round Linker', tag: 'Logic' }
        ]
    },
    {
        id: 'database',
        title: 'Database + Tables',
        nodes: [
            { id: 'postgresql_database_manager', label: 'Postgres DB Manager', tag: 'Importer' },
            { id: 'db_adapter', label: 'DB Adapter', tag: 'Shared' },
            { id: 'postgres', label: 'PostgreSQL', tag: 'DB' },
            { id: 'table_rounds', label: 'rounds', tag: 'Table' },
            { id: 'table_player_stats', label: 'player_comprehensive_stats', tag: 'Table' },
            { id: 'table_weapon_stats', label: 'weapon_comprehensive_stats', tag: 'Table' },
            { id: 'table_processed_files', label: 'processed_files', tag: 'Table' },
            { id: 'table_gaming_sessions', label: 'gaming_sessions', tag: 'Table' },
            { id: 'table_session_rounds', label: 'session_rounds', tag: 'Table' },
            { id: 'table_lua_round_teams', label: 'lua_round_teams', tag: 'Table' },
            { id: 'table_proximity', label: 'proximity_*', tag: 'Table' }
        ]
    },
    {
        id: 'bot_core',
        title: 'Bot Core',
        nodes: [
            { id: 'discord_bot', label: 'ultimate_bot.py', tag: 'Runtime' },
            { id: 'logging_config', label: 'Logging Config', tag: 'Ops' },
            { id: 'core_checks', label: 'core/checks.py', tag: 'Core' },
            { id: 'core_utils', label: 'core/utils.py', tag: 'Core' },
            { id: 'pagination_view', label: 'pagination_view.py', tag: 'UI' },
            { id: 'lazy_pagination_view', label: 'lazy_pagination_view.py', tag: 'UI' },
            { id: 'endstats_pagination_view', label: 'endstats_pagination_view.py', tag: 'UI' },
            { id: 'stats_calculator', label: 'stats/calculator.py', tag: 'Core' },
            { id: 'stats_cache', label: 'Stats Cache', tag: 'Core' },
            { id: 'match_tracker', label: 'Match Tracker', tag: 'Core' },
            { id: 'team_manager', label: 'Team Manager', tag: 'Core' },
            { id: 'team_history', label: 'Team History', tag: 'Core' },
            { id: 'advanced_team_detector', label: 'Advanced Team Detector', tag: 'Core' },
            { id: 'team_detector_integration', label: 'Team Detector Bridge', tag: 'Core' },
            { id: 'substitution_detector', label: 'Substitution Detector', tag: 'Core' },
            { id: 'season_manager', label: 'Season Manager', tag: 'Core' },
            { id: 'achievement_system', label: 'Achievement System', tag: 'Core' },
            { id: 'frag_potential', label: 'Frag Potential', tag: 'Core' },
            { id: 'round_linker', label: 'Round Linker', tag: 'Core' }
        ]
    },
    {
        id: 'bot_services',
        title: 'Bot Services',
        nodes: [
            { id: 'session_aggregator', label: 'Session Aggregator', tag: 'Service' },
            { id: 'session_embed_builder', label: 'Session Embed Builder', tag: 'Service' },
            { id: 'session_view_handlers', label: 'Session View Handlers', tag: 'Service' },
            { id: 'session_data_service', label: 'Session Data Service', tag: 'Service' },
            { id: 'round_publisher', label: 'Round Publisher', tag: 'Service' },
            { id: 'graph_generator', label: 'Graph Generator', tag: 'Service' },
            { id: 'image_generator', label: 'Image Generator', tag: 'Service' },
            { id: 'endstats_aggregator', label: 'Endstats Aggregator', tag: 'Service' },
            { id: 'timing_comparison', label: 'Timing Comparison', tag: 'Service' },
            { id: 'timing_debug_service', label: 'Timing Debug Service', tag: 'Service' },
            { id: 'player_analytics_service', label: 'Player Analytics', tag: 'Service' },
            { id: 'player_badge_service', label: 'Player Badge Service', tag: 'Service' },
            { id: 'player_formatter', label: 'Player Formatter', tag: 'Service' },
            { id: 'player_display_name_service', label: 'Player Display Names', tag: 'Service' },
            { id: 'matchup_analytics_service', label: 'Matchup Analytics', tag: 'Service' },
            { id: 'prediction_engine', label: 'Prediction Engine', tag: 'Service' },
            { id: 'prediction_embed_builder', label: 'Prediction Embeds', tag: 'Service' },
            { id: 'monitoring_service', label: 'Monitoring Service', tag: 'Service' },
            { id: 'voice_session_service', label: 'Voice Session Service', tag: 'Service' },
            { id: 'stopwatch_scoring_service', label: 'Stopwatch Scoring', tag: 'Service' }
        ]
    },
    {
        id: 'bot_utilities',
        title: 'Bot Utilities + Reports',
        nodes: FULL_BOT_UTILITIES
    },
    {
        id: 'bot_maintenance',
        title: 'Bot Setup + Maintenance',
        nodes: FULL_BOT_MAINTENANCE
    },
    {
        id: 'diagnostics',
        title: 'Diagnostics Scripts',
        nodes: FULL_DIAGNOSTIC_NODES
    },
    {
        id: 'dev_tools',
        title: 'Developer Tools',
        nodes: FULL_DEV_TOOLS
    },
    {
        id: 'maintenance_scripts',
        title: 'Maintenance Scripts',
        nodes: FULL_MAINTENANCE_SCRIPTS
    },
    {
        id: 'config_files',
        title: 'Config + Services',
        nodes: FULL_CONFIG_FILES
    },
    {
        id: 'discord_cogs',
        title: 'Discord Cogs',
        nodes: FULL_COGS.map((id) => ({ id, label: titleize(id), tag: 'Cog' }))
    },
    {
        id: 'website_backend',
        title: 'Website Backend Core',
        nodes: FULL_WEBSITE_BACKEND_CORE
    },
    {
        id: 'website_middleware',
        title: 'Website Middleware',
        nodes: FULL_WEBSITE_MIDDLEWARE
    },
    {
        id: 'website',
        title: 'Website Stack',
        nodes: [
            { id: 'website_api', label: 'FastAPI API', tag: 'API' },
            { id: 'website_router_api', label: 'API Router', tag: 'Router' },
            { id: 'website_router_auth', label: 'Auth Router', tag: 'Router' },
            { id: 'website_router_predictions', label: 'Predictions Router', tag: 'Router' },
            { id: 'website_session_data_service', label: 'Session Data Service', tag: 'Service' },
            { id: 'voice_channel_tracker', label: 'Voice Channel Tracker', tag: 'Service' },
            { id: 'game_server_query', label: 'Game Server Query', tag: 'Service' },
            { id: 'proximity_api', label: 'Proximity API', tag: 'API' },
            { id: 'proximity_ui', label: 'Proximity UI', tag: 'UI' },
            { id: 'website_frontend', label: 'Website Frontend', tag: 'UI' },
            { id: 'admin_panel', label: 'Admin Panel', tag: 'UI' }
        ]
    },
    {
        id: 'monitoring',
        title: 'Monitoring + Logs',
        nodes: [
            { id: 'etconsole_log', label: 'etconsole.log', tag: 'Logs' },
            { id: 'bot_log_stream', label: 'Bot Log Stream', tag: 'Logs' },
            { id: 'webhook_log_stream', label: 'Webhook Log Stream', tag: 'Logs' },
            { id: 'live_monitoring_session', label: 'Live Monitoring Session', tag: 'Ops' },
            { id: 'health_monitor', label: 'Health Monitor', tag: 'Ops' },
            { id: 'metrics_logger', label: 'Metrics Logger', tag: 'Ops' },
            { id: 'database_maintenance', label: 'DB Maintenance', tag: 'Ops' },
            { id: 'ws_client', label: 'WS Client', tag: 'Ops' }
        ]
    },
    {
        id: 'ops_tools',
        title: 'Ops + Tools',
        nodes: [
            { id: 'smart_scheduler', label: 'Smart Scheduler', tag: 'Tool' },
            { id: 'smart_sync_scheduler', label: 'Smart Sync Scheduler', tag: 'Tool' },
            { id: 'sync_stats', label: 'Sync Stats', tag: 'Tool' },
            { id: 'ssh_sync_and_import', label: 'SSH Sync + Import', tag: 'Tool' },
            { id: 'preview_last_session', label: 'Preview Last Session', tag: 'Tool' },
            { id: 'validate_last_session_graphs', label: 'Validate Session Graphs', tag: 'Tool' },
            { id: 'stopwatch_scoring_tool', label: 'Stopwatch Scoring Tool', tag: 'Tool' }
        ]
    }
];

const ALL_GROUP_IDS = FULL_MAP_GROUPS.map(group => group.id);

const FLOW_GROUP_IDS = [
    'core_topology',
    'infra',
    'game',
    'outputs',
    'round_outcomes',
    'webhook_relay',
    'ingest',
    'parse',
    'database',
    'bot_core',
    'bot_services',
    'discord',
    'website',
    'monitoring'
];

const ATLAS_TABS = [
    { id: 'all', label: 'All', groups: null },
    { id: 'flow', label: 'Flow', groups: FLOW_GROUP_IDS },
    { id: 'game', label: 'Game', groups: ['core_topology', 'infra', 'game', 'round_outcomes', 'outputs'] },
    { id: 'webhook', label: 'Webhook', groups: ['game', 'outputs', 'webhook_relay', 'ingest', 'discord'] },
    { id: 'ingest', label: 'Ingest', groups: ['outputs', 'webhook_relay', 'ingest', 'parse'] },
    { id: 'database', label: 'Database', groups: ['core_topology', 'database', 'round_outcomes', 'config_files'] },
    { id: 'bot', label: 'Bot', groups: ['core_topology', 'bot_core', 'bot_services', 'discord_cogs', 'bot_utilities', 'bot_maintenance', 'monitoring', 'ops_tools'] },
    { id: 'website', label: 'Website', groups: ['core_topology', 'website_backend', 'website_middleware', 'website', 'config_files'] },
    { id: 'diagnostics', label: 'Diagnostics', groups: ['diagnostics', 'dev_tools', 'maintenance_scripts', 'bot_maintenance', 'monitoring'] }
];

const ATLAS_PRESETS = [
    { id: 'spectator', label: 'Spectator', groups: ['core_topology', 'infra', 'discord', 'game', 'outputs', 'ingest', 'parse', 'database', 'bot_core', 'website'] },
    { id: 'developer', label: 'Developer', groups: ALL_GROUP_IDS },
    { id: 'admin', label: 'Admin', groups: ALL_GROUP_IDS },
    { id: 'debug', label: 'Debug', groups: ['core_topology', 'monitoring', 'diagnostics', 'dev_tools', 'maintenance_scripts', 'webhook_relay', 'ingest', 'parse', 'database', 'bot_services', 'bot_core'] }
];

const FULL_STORY_STEPS = [
    {
        id: 'players_to_server',
        label: '1. Players → Server',
        title: 'Players join the game server',
        description: 'Players connect to the ET:Legacy server. Live matches happen here and Lua begins collecting raw stats.',
        focus: 'core_game_server',
        nodes: ['players', 'game_server_host', 'et_server', 'lua_modules', 'lua_c0rnp0rn7']
    },
    {
        id: 'lua_outputs',
        label: '2. Lua → Files',
        title: 'Lua writes raw files + webhooks',
        description: 'Lua scripts export raw gamestats/endstats files and webhook timing data after each round.',
        focus: 'lua_c0rnp0rn7',
        nodes: ['lua_c0rnp0rn7', 'lua_endstats', 'lua_webhook', 'gamestats_files', 'endstats_files', 'gametimes_files']
    },
    {
        id: 'ingest_parse',
        label: '3. Ingest → Parse',
        title: 'Bots ingest + parse raw stats',
        description: 'File trackers pull outputs, parsers decode them, and validation guards clean bad data.',
        focus: 'stats_parser',
        nodes: ['ssh_monitor', 'file_repository', 'stats_ingest', 'stats_parser', 'differential_calc', 'validation_caps', 'endstats_ingest', 'endstats_parser', 'round_linker']
    },
    {
        id: 'database_store',
        label: '4. Store → DB',
        title: 'PostgreSQL stores everything',
        description: 'Parsed stats are inserted into PostgreSQL tables. This becomes the single source of truth.',
        focus: 'core_postgres',
        nodes: ['postgresql_database_manager', 'postgres', 'db_adapter', 'table_rounds', 'table_player_stats', 'table_weapon_stats', 'table_lua_round_teams']
    },
    {
        id: 'discord_outputs',
        label: '5. Bot → Discord',
        title: 'Discord bot turns data into updates',
        description: 'The bot queries the DB, builds embeds, and posts sessions, awards, and round summaries.',
        focus: 'discord_bot',
        nodes: ['discord_bot', 'session_aggregator', 'session_embed_builder', 'round_publisher', 'endstats_aggregator', 'discord_stats_channel']
    },
    {
        id: 'website_outputs',
        label: '6. API → Website',
        title: 'Website shows live analytics',
        description: 'The website API pulls from Postgres and renders dashboards, profiles, and the admin atlas.',
        focus: 'website_api',
        nodes: ['website_api', 'website_frontend', 'admin_panel', 'players']
    }
];

const FULL_MAP_NODE_INDEX = FULL_MAP_GROUPS.flatMap(group =>
    group.nodes.map(node => ({
        id: node.id,
        label: node.label || node.id,
        groupId: group.id
    }))
);

const LUA_MAP_NODE_INDEX = LUA_MAP_GROUPS.flatMap(group =>
    group.nodes.map(node => ({
        id: node.id,
        label: node.label || node.id,
        groupId: group.id
    }))
);

const FULL_FLOW_BASE = [
    { from: 'core_game_server', to: 'core_postgres', type: 'core', label: 'Stats stored' },
    { from: 'core_postgres', to: 'core_bot_web', type: 'core', label: 'Queries + outputs' },
    { from: 'players', to: 'game_server_host', type: 'core', label: 'Join matches' },
    { from: 'game_server_host', to: 'et_server', type: 'core', label: 'Runs ET server' },
    { from: 'players', to: 'discord_cloud', type: 'web', label: 'Chat + voice' },
    { from: 'discord_cloud', to: 'discord_text', type: 'web', label: 'Text traffic' },
    { from: 'discord_cloud', to: 'discord_voice', type: 'web', label: 'Voice traffic' },
    { from: 'discord_cloud', to: 'discord_webhook', type: 'web', label: 'Webhook posts' },
    { from: 'discord_text', to: 'discord_control_channel', type: 'web', label: 'Control channel' },
    { from: 'discord_text', to: 'discord_stats_channel', type: 'web', label: 'Stats channel' },
    { from: 'discord_text', to: 'discord_bot', type: 'stats', label: 'Commands + webhooks' },
    { from: 'discord_bot', to: 'discord_text', type: 'stats', label: 'Embeds + updates' },
    { from: 'discord_bot', to: 'discord_stats_channel', type: 'stats', label: 'Posts stats' },
    { from: 'discord_voice', to: 'voice_session_service', type: 'ops', label: 'Voice activity' },
    { from: 'voice_session_service', to: 'discord_bot', type: 'ops', label: 'Auto session posts' },
    { from: 'players', to: 'website_frontend', type: 'web', label: 'Visit website' },
    { from: 'game_server_host', to: 'ssh_monitor', type: 'ops', label: 'SSH/SFTP access' },
    { from: 'game_server_host', to: 'webhook_receiver', type: 'webhook', label: 'Lua webhooks' },
    { from: 'bot_server_host', to: 'discord_bot', type: 'core', label: 'Hosts bot process' },
    { from: 'bot_server_host', to: 'postgres', type: 'core', label: 'Hosts database' },
    { from: 'bot_server_host', to: 'website_api', type: 'web', label: 'Hosts API' },
    { from: 'et_server', to: 'lua_modules', type: 'core', label: 'Live game events' },
    { from: 'et_server', to: 'server_watchdog', type: 'ops', label: 'Health checks' },
    { from: 'et_server', to: 'etconsole_log', type: 'ops', label: 'Server log' },
    { from: 'lua_modules', to: 'lua_c0rnp0rn7', type: 'stats', label: 'Write stats files' },
    { from: 'lua_modules', to: 'lua_endstats', type: 'endstats', label: 'Write awards files' },
    { from: 'lua_modules', to: 'lua_webhook', type: 'webhook', label: 'Send timing pings' },
    { from: 'lua_modules', to: 'lua_proximity', type: 'proximity', label: 'Write proximity logs' },
    { from: 'lua_c0rnp0rn7', to: 'gamestats_files', type: 'stats', label: 'gamestats output' },
    { from: 'lua_endstats', to: 'endstats_files', type: 'endstats', label: 'endstats output' },
    { from: 'lua_webhook', to: 'webhook_receiver', type: 'webhook', label: 'Webhook payloads' },
    { from: 'lua_webhook', to: 'gametimes_files', type: 'webhook', label: 'Fallback JSON' },
    { from: 'lua_webhook', to: 'round_end_reason', type: 'webhook', label: 'End reason' },
    { from: 'round_end_reason', to: 'round_completed', type: 'webhook', label: 'Complete' },
    { from: 'round_end_reason', to: 'round_surrender', type: 'webhook', label: 'Surrender' },
    { from: 'round_end_reason', to: 'round_timelimit', type: 'webhook', label: 'Time limit' },
    { from: 'round_end_reason', to: 'round_cancelled', type: 'webhook', label: 'Cancelled' },
    { from: 'round_end_reason', to: 'round_substitution', type: 'webhook', label: 'Substitution' },
    { from: 'lua_proximity', to: 'proximity_positions', type: 'proximity', label: 'Positions log' },
    { from: 'lua_proximity', to: 'proximity_combat', type: 'proximity', label: 'Combat log' },
    { from: 'lua_proximity', to: 'proximity_engagements', type: 'proximity', label: 'Engagements log' },
    { from: 'lua_proximity', to: 'proximity_heatmap', type: 'proximity', label: 'Heatmap log' },
    { from: 'gamestats_files', to: 'stats_webhook_notify', type: 'ops', label: 'File watcher' },
    { from: 'stats_webhook_notify', to: 'discord_webhook', type: 'webhook', label: 'STATS_READY ping' },
    { from: 'discord_webhook', to: 'discord_control_channel', type: 'webhook', label: 'Webhook message' },
    { from: 'discord_control_channel', to: 'webhook_security_gate', type: 'webhook', label: 'Trigger' },
    { from: 'webhook_security_gate', to: 'webhook_trigger_handler', type: 'webhook', label: 'Allow + parse' },
    { from: 'webhook_trigger_handler', to: 'ssh_handler', type: 'ops', label: 'Fetch files' },
    { from: 'et_stats_webhook_service', to: 'stats_webhook_notify', type: 'ops', label: 'Runs notifier' },
    { from: 'gamestats_files', to: 'ssh_monitor', type: 'ops', label: 'Detect new files' },
    { from: 'endstats_files', to: 'ssh_monitor', type: 'ops', label: 'Detect new files' },
    { from: 'proximity_positions', to: 'ssh_monitor', type: 'ops', label: 'Detect new files' },
    { from: 'ssh_monitor', to: 'ssh_handler', type: 'ops', label: 'SSH helper' },
    { from: 'ssh_monitor', to: 'file_repository', type: 'ops', label: 'Download files' },
    { from: 'discord_bot', to: 'endstats_monitor', type: 'ops', label: 'Fallback polling' },
    { from: 'endstats_monitor', to: 'ssh_handler', type: 'ops', label: 'Pull files' },
    { from: 'discord_bot', to: 'cache_refresher', type: 'ops', label: 'Refresh cache' },
    { from: 'cache_refresher', to: 'file_tracker', type: 'ops', label: 'Update cache' },
    { from: 'file_tracker', to: 'stats_ingest', type: 'ops', label: 'Queue tracking' },
    { from: 'file_tracker', to: 'endstats_ingest', type: 'ops', label: 'Queue tracking' },
    { from: 'file_tracker', to: 'proximity_ingest', type: 'ops', label: 'Queue tracking' },
    { from: 'file_repository', to: 'stats_ingest', type: 'stats', label: 'Queue stats import' },
    { from: 'file_repository', to: 'endstats_ingest', type: 'endstats', label: 'Queue awards import' },
    { from: 'file_repository', to: 'proximity_ingest', type: 'proximity', label: 'Queue proximity import' },
    { from: 'stats_ingest', to: 'stats_parser', type: 'stats', label: 'Parse stats' },
    { from: 'stats_parser', to: 'differential_calc', type: 'stats', label: 'Round split' },
    { from: 'differential_calc', to: 'validation_caps', type: 'stats', label: 'Sanity checks' },
    { from: 'validation_caps', to: 'postgresql_database_manager', type: 'stats', label: 'DB import' },
    { from: 'endstats_ingest', to: 'endstats_parser', type: 'endstats', label: 'Parse awards' },
    { from: 'endstats_parser', to: 'round_linker', type: 'endstats', label: 'Link round IDs' },
    { from: 'round_linker', to: 'postgresql_database_manager', type: 'endstats', label: 'DB import' },
    { from: 'proximity_ingest', to: 'proximity_parser', type: 'proximity', label: 'Parse proximity' },
    { from: 'proximity_parser', to: 'postgresql_database_manager', type: 'proximity', label: 'DB import' },
    { from: 'webhook_receiver', to: 'postgresql_database_manager', type: 'webhook', label: 'Timing rows' },
    { from: 'postgresql_database_manager', to: 'postgres', type: 'core', label: 'Write rows' },
    { from: 'postgres', to: 'db_adapter', type: 'core', label: 'Shared access' },
    { from: 'db_adapter', to: 'discord_bot', type: 'stats', label: 'Bot queries' },
    { from: 'postgres', to: 'round_status_filter', type: 'stats', label: 'Completed rounds' },
    { from: 'round_status_filter', to: 'session_aggregator', type: 'stats', label: 'Session queries' },
    { from: 'postgres', to: 'round_publisher', type: 'stats', label: 'Round stats' },
    { from: 'postgres', to: 'timing_comparison', type: 'webhook', label: 'Timing comparison query' },
    { from: 'postgres', to: 'endstats_aggregator', type: 'endstats', label: 'Award data' },
    { from: 'session_aggregator', to: 'session_embed_builder', type: 'stats', label: 'Session totals' },
    { from: 'session_aggregator', to: 'session_view_handlers', type: 'stats', label: 'View-specific data' },
    { from: 'session_aggregator', to: 'graph_generator', type: 'stats', label: 'Chart datasets' },
    { from: 'session_embed_builder', to: 'discord_bot', type: 'stats', label: 'Session embed' },
    { from: 'session_view_handlers', to: 'discord_bot', type: 'stats', label: 'Alternate embeds' },
    { from: 'graph_generator', to: 'discord_bot', type: 'stats', label: 'PNG charts' },
    { from: 'round_publisher', to: 'discord_bot', type: 'stats', label: 'Round embed' },
    { from: 'endstats_aggregator', to: 'discord_bot', type: 'endstats', label: 'Awards embed' },
    { from: 'timing_comparison', to: 'discord_bot', type: 'webhook', label: 'Debug report' },
    { from: 'discord_bot', to: 'bot_log_stream', type: 'ops', label: 'Bot log stream' },
    { from: 'webhook_trigger_handler', to: 'webhook_log_stream', type: 'ops', label: 'Webhook log stream' },
    { from: 'etconsole_log', to: 'live_monitoring_session', type: 'ops', label: 'Observer notes' },
    { from: 'bot_log_stream', to: 'live_monitoring_session', type: 'ops', label: 'Observer notes' },
    { from: 'webhook_log_stream', to: 'live_monitoring_session', type: 'ops', label: 'Observer notes' },
    { from: 'postgres', to: 'proximity_cog', type: 'proximity', label: 'Proximity queries' },
    { from: 'proximity_cog', to: 'discord_bot', type: 'proximity', label: 'Proximity commands' },
    { from: 'postgres', to: 'website_api', type: 'web', label: 'API queries' },
    { from: 'website_api', to: 'proximity_api', type: 'proximity', label: 'Proximity endpoints' },
    { from: 'website_api', to: 'website_frontend', type: 'web', label: 'JSON responses' },
    { from: 'website_frontend', to: 'admin_panel', type: 'web', label: 'Admin UI' },
    { from: 'postgres', to: 'proximity_api', type: 'proximity', label: 'Proximity endpoints' },
    { from: 'proximity_api', to: 'proximity_ui', type: 'proximity', label: 'Prototype UI data' }
];

const FULL_FLOW_CONNECTIONS = [
    ...FULL_FLOW_BASE,
    ...FULL_TABLES.map(id => ({ from: 'postgres', to: id, type: 'core', label: 'Stores data' })),
    ...FULL_CORE.map(id => ({ from: 'discord_bot', to: id, type: 'core', label: 'Core logic' })),
    ...FULL_SERVICES.map(id => ({ from: 'discord_bot', to: id, type: 'stats', label: 'Uses service' })),
    ...FULL_BOT_UTILITIES.map(node => ({ from: 'discord_bot', to: node.id, type: 'core', label: 'Helpers + reports' })),
    ...FULL_BOT_MAINTENANCE.map(node => ({ from: 'bot_server_host', to: node.id, type: 'ops', label: 'Setup + maintenance' })),
    ...FULL_COGS.map(id => ({ from: 'discord_bot', to: id, type: 'stats', label: 'Command module' })),
    ...FULL_WEBSITE_ROUTERS.map(id => ({ from: 'website_api', to: id, type: 'web', label: 'Routes' })),
    ...FULL_WEBSITE_SERVICES.map(id => ({ from: 'website_api', to: id, type: 'web', label: 'Service' })),
    ...FULL_WEBSITE_BACKEND_CORE.map(node => ({ from: 'website_api', to: node.id, type: 'web', label: 'Backend core' })),
    ...FULL_WEBSITE_MIDDLEWARE.map(node => ({ from: 'website_api', to: node.id, type: 'web', label: 'Middleware' })),
    ...FULL_CONFIG_FILES.map(node => ({ from: 'bot_server_host', to: node.id, type: 'ops', label: 'Config/service' })),
    ...FULL_DIAGNOSTIC_NODES.map(node => ({ from: 'bot_server_host', to: node.id, type: 'ops', label: 'Diagnostics' })),
    ...FULL_DEV_TOOLS.map(node => ({ from: 'bot_server_host', to: node.id, type: 'ops', label: 'Dev tools' })),
    ...FULL_MAINTENANCE_SCRIPTS.map(node => ({ from: 'bot_server_host', to: node.id, type: 'ops', label: 'Manual scripts' })),
    { from: 'discord_bot', to: 'monitoring_service', type: 'ops', label: 'Health alerts' },
    { from: 'discord_bot', to: 'voice_session_service', type: 'ops', label: 'Auto session posts' },
    { from: 'last_session_cog', to: 'stopwatch_scoring_service', type: 'stats', label: 'Stopwatch scoring' },
    { from: 'team_cog', to: 'stopwatch_scoring_service', type: 'stats', label: 'Stopwatch scoring' },
    { from: 'voice_session_service', to: 'stopwatch_scoring_service', type: 'stats', label: 'Stopwatch scoring' }
];

const LUA_FLOW_CONNECTIONS = [
    { from: 'lua_c0rnp0rn7', to: 'lua_et_initgame', type: 'core', label: 'Init hook' },
    { from: 'lua_c0rnp0rn7', to: 'lua_et_runframe', type: 'core', label: 'Frame hook' },
    { from: 'lua_c0rnp0rn7', to: 'lua_et_obituary', type: 'core', label: 'Death hook' },
    { from: 'lua_c0rnp0rn7', to: 'lua_et_clientspawn', type: 'core', label: 'Spawn hook' },
    { from: 'lua_c0rnp0rn7', to: 'lua_et_clientdisconnect', type: 'core', label: 'Disconnect hook' },
    { from: 'lua_c0rnp0rn7', to: 'lua_et_damage', type: 'core', label: 'Damage hook' },
    { from: 'lua_c0rnp0rn7', to: 'lua_et_print', type: 'core', label: 'Print hook' },
    { from: 'lua_c0rnp0rn7', to: 'lua_et_shutdown', type: 'core', label: 'Shutdown hook' },
    { from: 'lua_et_obituary', to: 'lua_death_time', type: 'timing', label: 'Start dead timer' },
    { from: 'lua_death_time', to: 'lua_death_time_total', type: 'timing', label: 'Accumulate dead ms' },
    { from: 'lua_et_clientspawn', to: 'lua_death_time_total', type: 'timing', label: 'Close dead timer' },
    { from: 'lua_et_obituary', to: 'lua_denies_table', type: 'timing', label: 'Start deny timer' },
    { from: 'lua_denies_table', to: 'lua_denied_playtime', type: 'timing', label: 'Accumulate denied' },
    { from: 'lua_et_clientspawn', to: 'lua_denied_playtime', type: 'timing', label: 'Close deny timer' },
    { from: 'lua_et_clientdisconnect', to: 'lua_denied_playtime', type: 'timing', label: 'Flush deny timer' },
    { from: 'lua_et_runframe', to: 'lua_time_played_pct', type: 'timing', label: 'Normalize time_played' },
    { from: 'lua_et_runframe', to: 'lua_time_played_minutes', type: 'timing', label: 'tp → minutes' },
    { from: 'lua_time_played_minutes', to: 'lua_time_dead_ratio', type: 'timing', label: 'Ratio denominator' },
    { from: 'lua_death_time_total', to: 'lua_time_dead_minutes', type: 'timing', label: 'ms → minutes' },
    { from: 'lua_death_time_total', to: 'lua_time_dead_ratio', type: 'timing', label: 'dead / played' },
    { from: 'lua_et_obituary', to: 'lua_topshots_array', type: 'stats', label: 'Spree counters' },
    { from: 'lua_et_damage', to: 'lua_weapon_stats_buffer', type: 'stats', label: 'Hit + HS data' },
    { from: 'lua_topshots_array', to: 'lua_tab_fields', type: 'stats', label: 'Topshots fields' },
    { from: 'lua_weapon_stats_buffer', to: 'lua_tab_fields', type: 'stats', label: 'Weapon block' },
    { from: 'lua_time_played_pct', to: 'lua_tab_fields', type: 'timing', label: 'TAB[10]' },
    { from: 'lua_time_played_minutes', to: 'lua_tab_fields', type: 'timing', label: 'TAB[22]' },
    { from: 'lua_time_dead_ratio', to: 'lua_tab_fields', type: 'timing', label: 'TAB[24]' },
    { from: 'lua_time_dead_minutes', to: 'lua_tab_fields', type: 'timing', label: 'TAB[25]' },
    { from: 'lua_denied_playtime', to: 'lua_tab_fields', type: 'timing', label: 'TAB[28]' },
    { from: 'lua_et_runframe', to: 'lua_round_header', type: 'core', label: 'Round metadata' },
    { from: 'lua_round_header', to: 'lua_gamestats_file', type: 'stats', label: 'Header line' },
    { from: 'lua_tab_fields', to: 'lua_gamestats_file', type: 'stats', label: 'Player lines' },
    { from: 'lua_weapon_stats_buffer', to: 'lua_weaponstats_file', type: 'ops', label: 'Optional export' },
    { from: 'lua_et_shutdown', to: 'lua_gamestats_file', type: 'core', label: 'Force save' },
    { from: 'lua_c0rnp0rn', to: 'lua_gamestats_file', type: 'ops', label: 'Legacy exporter' },
    { from: 'lua_c0rnp0rn7real', to: 'lua_gamestats_file', type: 'ops', label: 'Legacy variant' },
    { from: 'lua_gamestats_file', to: 'stats_ingest', type: 'stats', label: 'File scan' },
    { from: 'stats_ingest', to: 'stats_parser', type: 'stats', label: 'Parse queue' },
    { from: 'stats_parser', to: 'differential_calc', type: 'stats', label: 'R2 split' },
    { from: 'differential_calc', to: 'validation_caps', type: 'stats', label: 'Validate' },
    { from: 'validation_caps', to: 'db_adapter', type: 'stats', label: 'Write rows' },
    { from: 'db_adapter', to: 'postgres', type: 'core', label: 'Store stats' },
    { from: 'postgres', to: 'session_aggregator', type: 'stats', label: 'Session totals' },
    { from: 'session_aggregator', to: 'session_embed_builder', type: 'stats', label: 'Build embeds' },
    { from: 'session_embed_builder', to: 'discord_bot', type: 'stats', label: 'Post results' },
    { from: 'lua_endstats', to: 'lua_endstats_file', type: 'endstats', label: 'Awards export' },
    { from: 'lua_endstats_file', to: 'endstats_ingest', type: 'endstats', label: 'Award files' },
    { from: 'endstats_ingest', to: 'endstats_parser', type: 'endstats', label: 'Decode awards' },
    { from: 'endstats_parser', to: 'endstats_aggregator', type: 'endstats', label: 'Summary' },
    { from: 'endstats_parser', to: 'db_adapter', type: 'endstats', label: 'Award rows' },
    { from: 'endstats_aggregator', to: 'discord_bot', type: 'endstats', label: 'Awards embed' },
    { from: 'lua_webhook', to: 'lua_webhook_round_start', type: 'webhook', label: 'RoundStart' },
    { from: 'lua_webhook', to: 'lua_webhook_round_end', type: 'webhook', label: 'RoundEnd' },
    { from: 'lua_webhook_round_start', to: 'lua_webhook_payload', type: 'webhook', label: 'Payload' },
    { from: 'lua_webhook_round_end', to: 'lua_webhook_payload', type: 'webhook', label: 'Payload' },
    { from: 'lua_webhook_payload', to: 'webhook_receiver', type: 'webhook', label: 'HTTP POST' },
    { from: 'webhook_receiver', to: 'table_lua_round_teams', type: 'webhook', label: 'Timing rows' },
    { from: 'table_lua_round_teams', to: 'postgres', type: 'core', label: 'Stored in DB' },
    { from: 'lua_proximity', to: 'lua_proximity_logs', type: 'proximity', label: 'Prototype output' },
    { from: 'lua_proximity_logs', to: 'proximity_ingest', type: 'proximity', label: 'Scan logs' },
    { from: 'proximity_ingest', to: 'proximity_parser', type: 'proximity', label: 'Parse logs' },
    { from: 'proximity_parser', to: 'db_adapter', type: 'proximity', label: 'Store rows' }
];

function buildConnectionLookup(connections) {
    const lookup = {};
    connections.forEach((connection) => {
        if (!lookup[connection.from]) lookup[connection.from] = new Set();
        if (!lookup[connection.to]) lookup[connection.to] = new Set();
        lookup[connection.from].add(connection.to);
        lookup[connection.to].add(connection.from);
    });
    return lookup;
}

const FULL_CONNECTION_LOOKUP = buildConnectionLookup(FULL_FLOW_CONNECTIONS);
const FLOW_CONNECTION_LOOKUP = buildConnectionLookup(FLOW_CONNECTIONS);
const LUA_CONNECTION_LOOKUP = buildConnectionLookup(LUA_FLOW_CONNECTIONS);

function loadOverrides() {
    try {
        const parsed = JSON.parse(localStorage.getItem(OVERRIDE_KEY));
        if (parsed && typeof parsed === 'object') {
            return parsed;
        }
    } catch (err) {
        console.warn('Failed to parse overrides:', err);
    }
    return { nodes: {}, metrics: {} };
}

function saveOverrides(overrides) {
    localStorage.setItem(OVERRIDE_KEY, JSON.stringify(overrides));
}

function loadChecklistState() {
    try {
        const parsed = JSON.parse(localStorage.getItem(CHECKLIST_KEY));
        if (parsed && typeof parsed === 'object') {
            return parsed;
        }
    } catch (err) {
        console.warn('Failed to parse checklist state:', err);
    }
    return {};
}

function saveChecklistState(state) {
    localStorage.setItem(CHECKLIST_KEY, JSON.stringify(state));
}

function ensureDefaultOverrides(overrides) {
    if (!overrides.metrics) overrides.metrics = {};
    const defaults = {
        time_dead: 'red',
        time_denied: 'red'
    };

    Object.entries(defaults).forEach(([metric, status]) => {
        if (!overrides.metrics[metric]) {
            overrides.metrics[metric] = { mode: 'manual', status };
        }
    });
    return overrides;
}

function rebuildStatusElementCache() {
    const nodes = new Map();
    document.querySelectorAll('[data-node]').forEach((element) => {
        const id = element.dataset.node;
        if (!id) return;
        if (!nodes.has(id)) nodes.set(id, []);
        nodes.get(id).push(element);
    });

    const metrics = new Map();
    document.querySelectorAll('[data-metric]').forEach((element) => {
        const id = element.dataset.metric;
        if (!id) return;
        if (!metrics.has(id)) metrics.set(id, []);
        metrics.get(id).push(element);
    });

    statusElementCache = { nodes, metrics };
    statusStateCache.nodes.clear();
    statusStateCache.metrics.clear();
}

function getCachedStatusElements(kind, id) {
    const key = kind === 'metric' ? 'metrics' : 'nodes';
    if (statusElementCache.nodes.size === 0 && statusElementCache.metrics.size === 0) {
        rebuildStatusElementCache();
    }
    return statusElementCache[key].get(id) || [];
}

function applyStatusToElement(element, status, mode) {
    if (!element) return;
    const light = element.querySelector('.status-light');
    if (light) {
        if (light.dataset.status !== status) {
            light.dataset.status = status;
        }
        if (light.dataset.mode !== mode) {
            light.dataset.mode = mode;
        }
    }

    const modeLabel = element.querySelector('.status-mode');
    if (modeLabel) {
        const label = mode === 'manual' ? 'MANUAL' : 'AUTO';
        if (modeLabel.textContent !== label) {
            modeLabel.textContent = label;
        }
    }
}

function getAutoStatus(element) {
    return element.dataset.autoStatus || 'blue';
}

function setEntityStatus(kind, id, mode, status, overrides) {
    const entityOverrides = kind === 'metric' ? overrides.metrics : overrides.nodes;
    if (mode === 'auto') {
        if (kind === 'metric') {
            entityOverrides[id] = { mode: 'auto' };
        } else {
            delete entityOverrides[id];
        }
    } else {
        entityOverrides[id] = { mode: 'manual', status };
    }
    saveOverrides(overrides);
    applyStatuses(overrides);
}

function applyStatuses(overrides) {
    if (statusElementCache.nodes.size === 0 && statusElementCache.metrics.size === 0) {
        rebuildStatusElementCache();
    }

    const nodeOverrides = overrides.nodes || {};
    statusElementCache.nodes.forEach((elements, id) => {
        const override = nodeOverrides[id];
        const mode = override?.mode || 'auto';
        const status = override?.status || getAutoStatus(elements[0]);
        const previous = statusStateCache.nodes.get(id);
        if (previous && previous.mode === mode && previous.status === status) return;
        statusStateCache.nodes.set(id, { mode, status });
        elements.forEach((element) => applyStatusToElement(element, status, mode));
    });

    const metricOverrides = overrides.metrics || {};
    statusElementCache.metrics.forEach((elements, id) => {
        const override = metricOverrides[id];
        const mode = override?.mode || 'auto';
        const status = override?.status || getAutoStatus(elements[0]);
        const previous = statusStateCache.metrics.get(id);
        if (previous && previous.mode === mode && previous.status === status) return;
        statusStateCache.metrics.set(id, { mode, status });
        elements.forEach((element) => applyStatusToElement(element, status, mode));
    });
}

function renderFullMap() {
    const container = document.getElementById('admin-full-map-content');
    if (!container || container.dataset.rendered === 'true') return;

    const collapsedGroups = loadFullMapCollapsed();

    const renderNode = (node, groupId, extraClass = '') => {
        const nodeClass = [extraClass, node.className].filter(Boolean).join(' ');
        return `
        <div class="reactor-node mini-node rounded-xl ${nodeClass}" data-node="${escapeHtml(node.id)}" data-node-tag="${escapeHtml(node.tag || '')}" data-node-group="${escapeHtml(groupId)}" data-full-map="true" data-auto-status="${escapeHtml(node.autoStatus || 'blue')}">
            <div class="flex items-center gap-2">
                <span class="status-light" data-status="${escapeHtml(node.autoStatus || 'blue')}" data-mode="auto"></span>
                <div class="text-[11px] font-semibold text-white">${escapeHtml(node.label)}</div>
                ${node.tag ? `<span class="node-tag px-2 py-0.5 rounded-full">${escapeHtml(node.tag)}</span>` : ''}
            </div>
            ${node.subtitle ? `<div class="text-[10px] text-slate-500 mt-1">${escapeHtml(node.subtitle)}</div>` : ''}
        </div>
    `;
    };

    container.innerHTML = FULL_MAP_GROUPS.map((group) => {
        const isCollapsed = collapsedGroups.has(group.id);
        if (group.layout === 'core') {
            return `
                <div class="full-map-group core-topology ${isCollapsed ? 'collapsed' : ''}" data-group="${escapeHtml(group.id)}">
                    <div class="full-map-header">
                        <div class="full-map-title">${escapeHtml(group.title)}</div>
                        <button class="full-map-toggle" data-group-toggle="${escapeHtml(group.id)}">
                            ${isCollapsed ? 'Expand' : 'Collapse'}
                        </button>
                    </div>
                    <div class="core-topology-grid full-map-nodes">
                        ${group.nodes.map((node) => renderNode(node, group.id, 'core-topology-node')).join('')}
                    </div>
                    <div class="core-topology-caption">Left: game servers generate stats. Center: PostgreSQL stores truth. Right: bot + website read and publish.</div>
                </div>
            `;
        }

        return `
            <div class="full-map-group ${isCollapsed ? 'collapsed' : ''}" data-group="${escapeHtml(group.id)}">
                <div class="full-map-header">
                    <div class="full-map-title">${escapeHtml(group.title)}</div>
                    <button class="full-map-toggle" data-group-toggle="${escapeHtml(group.id)}">
                        ${isCollapsed ? 'Expand' : 'Collapse'}
                    </button>
                </div>
                <div class="space-y-2 full-map-nodes">
                    ${group.nodes.map((node) => renderNode(node, group.id)).join('')}
                </div>
            </div>
        `;
    }).join('');

    container.dataset.rendered = 'true';
    rebuildStatusElementCache();

    syncFullMapStageSize();
    updateFullMapSearchIndex();
    bindFullMapGroupToggles();
}

function renderLuaMap() {
    const container = document.getElementById('admin-lua-map-content');
    if (!container || container.dataset.rendered === 'true') return;

    const collapsedGroups = loadLuaMapCollapsed();

    container.innerHTML = LUA_MAP_GROUPS.map((group) => `
        <div class="full-map-group ${collapsedGroups.has(group.id) ? 'collapsed' : ''}" data-group="${escapeHtml(group.id)}">
            <div class="full-map-header">
                <div class="full-map-title">${escapeHtml(group.title)}</div>
                <button class="full-map-toggle" data-lua-group-toggle="${escapeHtml(group.id)}">
                    ${collapsedGroups.has(group.id) ? 'Expand' : 'Collapse'}
                </button>
            </div>
            <div class="space-y-2 full-map-nodes">
                ${group.nodes.map((node) => `
                    <div class="reactor-node mini-node rounded-xl" data-node="${escapeHtml(node.id)}" data-node-tag="${escapeHtml(node.tag || '')}" data-node-group="${escapeHtml(group.id)}" data-full-map="true" data-auto-status="${escapeHtml(node.autoStatus || 'blue')}">
                        <div class="flex items-center gap-2">
                            <span class="status-light" data-status="${escapeHtml(node.autoStatus || 'blue')}" data-mode="auto"></span>
                            <div class="text-[11px] font-semibold text-white">${escapeHtml(node.label)}</div>
                            ${node.tag ? `<span class="node-tag px-2 py-0.5 rounded-full">${escapeHtml(node.tag)}</span>` : ''}
                        </div>
                        ${node.subtitle ? `<div class="text-[10px] text-slate-500 mt-1">${escapeHtml(node.subtitle)}</div>` : ''}
                    </div>
                `).join('')}
            </div>
        </div>
    `).join('');

    container.dataset.rendered = 'true';
    rebuildStatusElementCache();

    syncLuaMapStageSize();
    updateLuaMapSearchIndex();
    bindLuaMapGroupToggles();
}

function renderLuaChips(chips) {
    return chips.map((chip) => {
        const kind = chip.kind || 'default';
        const className = kind === 'timing' ? 'lua-chip timing' : kind === 'webhook' ? 'lua-chip webhook' : 'lua-chip';
        return `<span class="${className}">${escapeHtml(chip.label)}</span>`;
    }).join('');
}

function renderDevTimeline() {
    const container = document.getElementById('admin-dev-timeline');
    if (!container || container.dataset.rendered === 'true') return;

    container.innerHTML = DEV_TIMELINE.map((entry) => `
        <div class="dev-item">
            <div class="dev-dot" aria-hidden="true"></div>
            <div class="dev-card space-y-3">
                <div class="flex flex-wrap items-center justify-between gap-3">
                    <div class="text-xs uppercase tracking-[0.3em] text-slate-500">${escapeHtml(entry.date)}</div>
                    <div class="flex flex-wrap gap-2">
                        ${(entry.tags || []).map(tag => `<span class="dev-chip">${escapeHtml(tag)}</span>`).join('')}
                    </div>
                </div>
                <div class="text-sm font-semibold text-white">${escapeHtml(entry.title)}</div>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
                    <div>
                        <div class="text-[11px] uppercase tracking-[0.3em] text-slate-500">Need</div>
                        <div class="text-slate-300 mt-1">${escapeHtml(entry.need)}</div>
                    </div>
                    <div>
                        <div class="text-[11px] uppercase tracking-[0.3em] text-slate-500">Built</div>
                        <div class="text-slate-300 mt-1">${escapeHtml(entry.change)}</div>
                    </div>
                    <div>
                        <div class="text-[11px] uppercase tracking-[0.3em] text-slate-500">Discord Impact</div>
                        <div class="text-slate-300 mt-1">${escapeHtml(entry.outcome)}</div>
                    </div>
                </div>
                ${entry.refs ? `<div class="text-[11px] text-slate-500">Docs: ${entry.refs.map(ref => `<span class="text-slate-300">${escapeHtml(ref)}</span>`).join(', ')}</div>` : ''}
            </div>
        </div>
    `).join('');

    container.dataset.rendered = 'true';
}

function renderLuaAtlas() {
    const cards = document.getElementById('admin-lua-atlas-cards');
    const timing = document.getElementById('admin-lua-timing-focus');
    const r2Panel = document.getElementById('admin-lua-r2-only');
    const weaponFormat = document.getElementById('admin-lua-weapon-format');
    const weaponEnum = document.getElementById('admin-lua-weapon-enum');
    const fileLocations = document.getElementById('admin-lua-file-locations');
    const fieldMap = document.getElementById('admin-lua-field-map');
    if (!cards || cards.dataset.rendered === 'true') return;

    cards.innerHTML = LUA_SCRIPT_CARDS.map((card) => `
        <div class="lua-card rounded-2xl p-5 space-y-3">
            <div class="text-xs uppercase tracking-[0.3em] text-slate-500">${escapeHtml(card.title)}</div>
            <div class="text-sm font-semibold text-white">${escapeHtml(card.subtitle)}</div>
            <div class="text-xs text-slate-400">Outputs: <span class="text-slate-200">${escapeHtml(card.outputs)}</span></div>
            <div class="flex flex-wrap gap-2">${renderLuaChips(card.chips)}</div>
            <div class="text-xs text-slate-500">${escapeHtml(card.notes)}</div>
        </div>
    `).join('');

    if (timing) {
        timing.innerHTML = `
            <div class="text-xs uppercase tracking-[0.3em] text-slate-500">Timing Stats Focus</div>
            <div class="text-xs text-slate-500 mt-2">Raw Lua timing fields and where they flow.</div>
            <div class="space-y-4 mt-4">
                ${LUA_TIMING_FOCUS.map(step => `
                    <div>
                        <div class="text-xs font-semibold text-white">${escapeHtml(step.title)}</div>
                        <div class="text-xs text-slate-400 mt-1">${step.lines.map(line => escapeHtml(line)).join('<br>')}</div>
                    </div>
                `).join('')}
            </div>
        `;
    }

    if (r2Panel) {
        r2Panel.innerHTML = `
            <div class="text-xs uppercase tracking-[0.3em] text-slate-500">R2-Only Fields</div>
            <div class="text-xs text-slate-500 mt-2">These fields reset between rounds. Use R2 value directly.</div>
            <div class="flex flex-wrap gap-2 mt-4">
                ${LUA_R2_ONLY_FIELDS.map(field => `<span class="lua-chip">${escapeHtml(field)}</span>`).join('')}
            </div>
        `;
    }

    if (weaponFormat) {
        weaponFormat.innerHTML = `
            <div class="text-xs uppercase tracking-[0.3em] text-slate-500">Weapon Block Format</div>
            <div class="text-xs text-slate-500 mt-2">How weapon stats are stored before TAB fields.</div>
            <div class="text-xs text-slate-300 mt-4 space-y-1">
                ${LUA_WEAPON_BLOCK.map(line => `<div>${escapeHtml(line)}</div>`).join('')}
            </div>
        `;
    }

    if (weaponEnum) {
        weaponEnum.innerHTML = `
            <div class="text-xs uppercase tracking-[0.3em] text-slate-500">Weapon Enumeration</div>
            <div class="text-xs text-slate-500 mt-2">ID → weapon name (c0rnp0rn3 mapping).</div>
            <div class="lua-table mt-4">
                <div class="lua-table-header">
                    <div>ID</div>
                    <div>Weapon</div>
                    <div></div>
                    <div></div>
                </div>
                ${LUA_WEAPON_ENUM.map(entry => `
                    <div class="lua-table-row">
                        <div>${entry.id}</div>
                        <div>${escapeHtml(entry.name)}</div>
                        <div></div>
                        <div></div>
                    </div>
                `).join('')}
            </div>
        `;
    }

    if (fileLocations) {
        fileLocations.innerHTML = `
            <div class="text-xs uppercase tracking-[0.3em] text-slate-500">Lua File Locations</div>
            <div class="text-xs text-slate-500 mt-2">Where the scripts live and what they do.</div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
                ${LUA_FILE_LOCATIONS.map(item => `
                    <div class="lua-card rounded-xl p-3">
                        <div class="text-xs font-semibold text-white">${escapeHtml(item.label)}</div>
                        <div class="text-xs text-slate-300 mt-1"><code>${escapeHtml(item.value)}</code></div>
                        <div class="text-[11px] text-slate-500 mt-1">${escapeHtml(item.note)}</div>
                    </div>
                `).join('')}
            </div>
        `;
    }

    if (fieldMap) {
        fieldMap.innerHTML = LUA_FIELD_MAP.map(entry => `
            <div class="lua-table-row ${LUA_TIMING_FIELDS.has(entry.field) ? 'timing' : ''}">
                <div>Tab[${entry.idx}]</div>
                <div>${escapeHtml(entry.field)}</div>
                <div>${escapeHtml(entry.units)}</div>
                <div>${escapeHtml(entry.note || '')}</div>
            </div>
        `).join('');
    }

    cards.dataset.rendered = 'true';
}

let flowMapFocusId = null;
let fullMapFocusId = null;
let luaMapFocusId = null;
let fullStoryStepId = null;

function applyFlowMapFocus(id) {
    const container = document.getElementById('admin-flow-map');
    const svg = document.getElementById('admin-flow-lines');
    if (!container || !svg) return;

    const focusEnabled = container.classList.contains('flow-focus');
    const nodes = container.querySelectorAll('[data-node]');
    const lines = svg.querySelectorAll('path.flow-line');

    nodes.forEach((node) => node.classList.remove('active-node', 'active-peer'));
    lines.forEach((line) => line.classList.remove('active'));

    if (!focusEnabled || !id) return;

    const peers = FLOW_CONNECTION_LOOKUP[id];
    nodes.forEach((node) => {
        if (node.dataset.node === id) {
            node.classList.add('active-node');
        } else if (peers && peers.has(node.dataset.node)) {
            node.classList.add('active-peer');
        }
    });

    lines.forEach((line) => {
        if (line.dataset.from === id || line.dataset.to === id) {
            line.classList.add('active');
        }
    });
}

function bindFlowMapFocus() {
    const container = document.getElementById('admin-flow-map');
    if (!container) return;

    container.addEventListener('mouseenter', (event) => {
        const target = event.target.closest('[data-node]');
        if (!target) return;
        flowMapFocusId = target.dataset.node;
        applyFlowMapFocus(flowMapFocusId);
    });

    container.addEventListener('mousemove', (event) => {
        const target = event.target.closest('[data-node]');
        if (!target) return;
        if (flowMapFocusId !== target.dataset.node) {
            flowMapFocusId = target.dataset.node;
            applyFlowMapFocus(flowMapFocusId);
        }
    });

    container.addEventListener('mouseleave', () => {
        flowMapFocusId = null;
        applyFlowMapFocus(null);
    });
}

function applyFullMapFocus(id) {
    const container = document.getElementById('admin-full-map');
    const svg = document.getElementById('admin-full-lines');
    if (!container || !svg) return;

    const focusEnabled = container.classList.contains('focus-lines');
    const nodes = container.querySelectorAll('[data-node]');
    const lines = svg.querySelectorAll('path.flow-line');

    nodes.forEach((node) => node.classList.remove('active-node', 'active-peer'));
    lines.forEach((line) => line.classList.remove('active'));

    if (!focusEnabled || !id) return;

    const peers = FULL_CONNECTION_LOOKUP[id];
    nodes.forEach((node) => {
        if (node.dataset.node === id) {
            node.classList.add('active-node');
        } else if (peers && peers.has(node.dataset.node)) {
            node.classList.add('active-peer');
        }
    });

    lines.forEach((line) => {
        if (line.dataset.from === id || line.dataset.to === id) {
            line.classList.add('active');
        }
    });
}

function bindFullMapFocus() {
    const container = document.getElementById('admin-full-map');
    if (!container) return;

    container.addEventListener('mouseenter', (event) => {
        const target = event.target.closest('[data-node]');
        if (!target) return;
        fullMapFocusId = target.dataset.node;
        applyFullMapFocus(fullMapFocusId);
    });

    container.addEventListener('mousemove', (event) => {
        const target = event.target.closest('[data-node]');
        if (!target) return;
        if (fullMapFocusId !== target.dataset.node) {
            fullMapFocusId = target.dataset.node;
            applyFullMapFocus(fullMapFocusId);
        }
    });

    container.addEventListener('mouseleave', () => {
        fullMapFocusId = null;
        applyFullMapFocus(null);
    });
}

function applyLuaMapFocus(id) {
    const container = document.getElementById('admin-lua-map');
    const svg = document.getElementById('admin-lua-lines');
    if (!container || !svg) return;

    const focusEnabled = container.classList.contains('focus-lines');
    const nodes = container.querySelectorAll('[data-node]');
    const lines = svg.querySelectorAll('path.flow-line');

    nodes.forEach((node) => node.classList.remove('active-node', 'active-peer'));
    lines.forEach((line) => line.classList.remove('active'));

    if (!focusEnabled || !id) return;

    const peers = LUA_CONNECTION_LOOKUP[id];
    nodes.forEach((node) => {
        if (node.dataset.node === id) {
            node.classList.add('active-node');
        } else if (peers && peers.has(node.dataset.node)) {
            node.classList.add('active-peer');
        }
    });

    lines.forEach((line) => {
        if (line.dataset.from === id || line.dataset.to === id) {
            line.classList.add('active');
        }
    });
}

function bindLuaMapFocus() {
    const container = document.getElementById('admin-lua-map');
    if (!container) return;

    container.addEventListener('mouseenter', (event) => {
        const target = event.target.closest('[data-node]');
        if (!target) return;
        luaMapFocusId = target.dataset.node;
        applyLuaMapFocus(luaMapFocusId);
    });

    container.addEventListener('mousemove', (event) => {
        const target = event.target.closest('[data-node]');
        if (!target) return;
        if (luaMapFocusId !== target.dataset.node) {
            luaMapFocusId = target.dataset.node;
            applyLuaMapFocus(luaMapFocusId);
        }
    });

    container.addEventListener('mouseleave', () => {
        luaMapFocusId = null;
        applyLuaMapFocus(null);
    });
}

function bindFullLinesToggle() {
    const toggle = document.getElementById('admin-full-lines-toggle');
    const container = document.getElementById('admin-full-map');
    if (!toggle || !container) return;

    const setState = (focusOn) => {
        container.classList.toggle('focus-lines', focusOn);
        toggle.textContent = focusOn ? 'Focus Lines: On' : 'Focus Lines: Off';
        toggle.classList.toggle('active', focusOn);
        applyFullMapFocus(fullMapFocusId);
    };

    setState(true);
    toggle.addEventListener('click', () => {
        const next = !container.classList.contains('focus-lines');
        setState(next);
    });
}

function bindLuaLinesToggle() {
    const toggle = document.getElementById('admin-lua-lines-toggle');
    const container = document.getElementById('admin-lua-map');
    if (!toggle || !container) return;

    const setState = (focusOn) => {
        container.classList.toggle('focus-lines', focusOn);
        toggle.textContent = focusOn ? 'Focus Lines: On' : 'Focus Lines: Off';
        toggle.classList.toggle('active', focusOn);
        applyLuaMapFocus(luaMapFocusId);
    };

    setState(true);
    toggle.addEventListener('click', () => {
        const next = !container.classList.contains('focus-lines');
        setState(next);
    });
}

function scheduleDrawFlowLines() {
    if (flowDrawPending) return;
    flowDrawPending = true;
    requestAnimationFrame(() => {
        flowDrawPending = false;
        drawAllFlowLines();
    });
}

function loadFullMapState() {
    try {
        const parsed = JSON.parse(localStorage.getItem(FULL_MAP_STATE_KEY));
        if (parsed && typeof parsed === 'object') {
            return {
                scale: typeof parsed.scale === 'number' ? parsed.scale : 1,
                x: typeof parsed.x === 'number' ? parsed.x : 0,
                y: typeof parsed.y === 'number' ? parsed.y : 0
            };
        }
    } catch (err) {
        console.warn('Failed to parse full map state:', err);
    }
    return { scale: 1, x: 0, y: 0 };
}

function saveFullMapState(state) {
    localStorage.setItem(FULL_MAP_STATE_KEY, JSON.stringify(state));
}

function loadLuaMapState() {
    try {
        const parsed = JSON.parse(localStorage.getItem(LUA_MAP_STATE_KEY));
        if (parsed && typeof parsed === 'object') {
            return {
                scale: typeof parsed.scale === 'number' ? parsed.scale : 1,
                x: typeof parsed.x === 'number' ? parsed.x : 0,
                y: typeof parsed.y === 'number' ? parsed.y : 0
            };
        }
    } catch (err) {
        console.warn('Failed to parse lua map state:', err);
    }
    return { scale: 1, x: 0, y: 0 };
}

function saveLuaMapState(state) {
    localStorage.setItem(LUA_MAP_STATE_KEY, JSON.stringify(state));
}

function loadFullMapCollapsed() {
    try {
        const parsed = JSON.parse(localStorage.getItem(FULL_MAP_COLLAPSED_KEY));
        if (Array.isArray(parsed)) {
            return new Set(parsed);
        }
    } catch (err) {
        console.warn('Failed to parse full map collapsed groups:', err);
    }
    return new Set();
}

function saveFullMapCollapsed(collapsed) {
    localStorage.setItem(FULL_MAP_COLLAPSED_KEY, JSON.stringify(Array.from(collapsed)));
}

function loadLuaMapCollapsed() {
    try {
        const parsed = JSON.parse(localStorage.getItem(LUA_MAP_COLLAPSED_KEY));
        if (Array.isArray(parsed)) {
            return new Set(parsed);
        }
    } catch (err) {
        console.warn('Failed to parse lua map collapsed groups:', err);
    }
    return new Set();
}

function saveLuaMapCollapsed(collapsed) {
    localStorage.setItem(LUA_MAP_COLLAPSED_KEY, JSON.stringify(Array.from(collapsed)));
}

function loadFullMapView() {
    try {
        const parsed = JSON.parse(localStorage.getItem(FULL_MAP_VIEW_KEY));
        if (parsed && typeof parsed === 'object') {
            return {
                tab: parsed.tab || 'all',
                preset: parsed.preset || 'spectator'
            };
        }
    } catch (err) {
        console.warn('Failed to parse full map view:', err);
    }
    return { tab: 'all', preset: 'spectator' };
}

function saveFullMapView(state) {
    localStorage.setItem(FULL_MAP_VIEW_KEY, JSON.stringify(state));
}

function syncFullMapStageSize() {
    const stage = document.getElementById('admin-full-stage');
    const content = document.getElementById('admin-full-map-content');
    if (!stage || !content) return;
    const width = Math.max(content.scrollWidth, 300);
    const height = Math.max(content.scrollHeight, 200);
    stage.style.width = `${width}px`;
    stage.style.height = `${height}px`;
}

function syncLuaMapStageSize() {
    const stage = document.getElementById('admin-lua-stage');
    const content = document.getElementById('admin-lua-map-content');
    if (!stage || !content) return;
    const width = Math.max(content.scrollWidth, 300);
    const height = Math.max(content.scrollHeight, 200);
    stage.style.width = `${width}px`;
    stage.style.height = `${height}px`;
}

function updateFullMapSearchIndex(allowedGroups = null) {
    const input = document.getElementById('admin-full-search');
    const list = document.getElementById('admin-full-search-list');
    if (!input || !list) return;

    const options = FULL_MAP_NODE_INDEX.filter(node => !allowedGroups || allowedGroups.has(node.groupId));

    list.innerHTML = options.map(opt => `<option value="${escapeHtml(opt.label)}"></option>`).join('');
    input.dataset.mapIndex = JSON.stringify(options);
}

function updateLuaMapSearchIndex() {
    const input = document.getElementById('admin-lua-search');
    const list = document.getElementById('admin-lua-search-list');
    if (!input || !list) return;

    list.innerHTML = LUA_MAP_NODE_INDEX.map(opt => `<option value="${escapeHtml(opt.label)}"></option>`).join('');
    input.dataset.mapIndex = JSON.stringify(LUA_MAP_NODE_INDEX);
}

function bindFullMapGroupToggles() {
    const container = document.getElementById('admin-full-map-content');
    if (!container) return;
    const collapsed = loadFullMapCollapsed();

    container.querySelectorAll('[data-group-toggle]').forEach((btn) => {
        btn.addEventListener('click', (event) => {
            event.stopPropagation();
            const groupId = btn.dataset.groupToggle;
            const group = container.querySelector(`[data-group="${groupId}"]`);
            if (!group) return;
            const isCollapsed = group.classList.toggle('collapsed');
            btn.textContent = isCollapsed ? 'Expand' : 'Collapse';
            if (isCollapsed) {
                collapsed.add(groupId);
            } else {
                collapsed.delete(groupId);
            }
            saveFullMapCollapsed(collapsed);
            syncFullMapStageSize();
            scheduleDrawFlowLines();
        });
    });
}

function bindLuaMapGroupToggles() {
    const container = document.getElementById('admin-lua-map-content');
    if (!container) return;
    const collapsed = loadLuaMapCollapsed();

    container.querySelectorAll('[data-lua-group-toggle]').forEach((btn) => {
        btn.addEventListener('click', (event) => {
            event.stopPropagation();
            const groupId = btn.dataset.luaGroupToggle;
            const group = container.querySelector(`[data-group="${groupId}"]`);
            if (!group) return;
            const isCollapsed = group.classList.toggle('collapsed');
            btn.textContent = isCollapsed ? 'Expand' : 'Collapse';
            if (isCollapsed) {
                collapsed.add(groupId);
            } else {
                collapsed.delete(groupId);
            }
            saveLuaMapCollapsed(collapsed);
            syncLuaMapStageSize();
            scheduleDrawFlowLines();
        });
    });
}

function setFullMapCollapsedGroups(collapsed) {
    const container = document.getElementById('admin-full-map-content');
    if (!container) return;

    container.querySelectorAll('.full-map-group').forEach(group => {
        const groupId = group.dataset.group;
        const isCollapsed = collapsed.has(groupId);
        group.classList.toggle('collapsed', isCollapsed);
        const toggle = group.querySelector('[data-group-toggle]');
        if (toggle) toggle.textContent = isCollapsed ? 'Expand' : 'Collapse';
    });

    saveFullMapCollapsed(collapsed);
    syncFullMapStageSize();
    scheduleDrawFlowLines();
    applyFullStoryStep(fullStoryStepId, { skipCenter: true });
}

function bindAtlasGroupControls() {
    const collapseAllBtn = document.getElementById('admin-full-collapse-all');
    const expandFlowBtn = document.getElementById('admin-full-expand-flow');
    const expandAllBtn = document.getElementById('admin-full-expand-all');

    if (collapseAllBtn) {
        collapseAllBtn.addEventListener('click', () => {
            const collapsed = new Set(FULL_MAP_GROUPS.map(group => group.id));
            setFullMapCollapsedGroups(collapsed);
            if (fullMapNav?.fitToView) {
                setTimeout(() => fullMapNav.fitToView(), 60);
            }
        });
    }

    if (expandFlowBtn) {
        expandFlowBtn.addEventListener('click', () => {
            const collapsed = new Set(FULL_MAP_GROUPS.map(group => group.id));
            FLOW_GROUP_IDS.forEach(groupId => collapsed.delete(groupId));
            setFullMapCollapsedGroups(collapsed);
            if (fullMapNav?.fitToView) {
                setTimeout(() => fullMapNav.fitToView(), 60);
            }
        });
    }

    if (expandAllBtn) {
        expandAllBtn.addEventListener('click', () => {
            const collapsed = new Set();
            setFullMapCollapsedGroups(collapsed);
            if (fullMapNav?.fitToView) {
                setTimeout(() => fullMapNav.fitToView(), 60);
            }
        });
    }
}

function renderAtlasControls(state) {
    const tabs = document.getElementById('admin-atlas-tabs');
    const presets = document.getElementById('admin-atlas-presets');
    if (!tabs || !presets) return;

    tabs.innerHTML = ATLAS_TABS.map(tab => `
        <button class="control-chip atlas-chip px-3 py-2 rounded-full" data-atlas-tab="${escapeHtml(tab.id)}">${escapeHtml(tab.label)}</button>
    `).join('');

    presets.innerHTML = ATLAS_PRESETS.map(preset => `
        <button class="control-chip atlas-chip px-3 py-2 rounded-full" data-atlas-preset="${escapeHtml(preset.id)}">${escapeHtml(preset.label)}</button>
    `).join('');

    updateAtlasButtons(state);

    tabs.querySelectorAll('[data-atlas-tab]').forEach(button => {
        button.addEventListener('click', () => {
            const next = button.dataset.atlasTab;
            const view = loadFullMapView();
            view.tab = next;
            saveFullMapView(view);
            applyAtlasFilters();
            if (fullMapNav && typeof fullMapNav.fitToView === 'function') {
                setTimeout(() => fullMapNav.fitToView(), 60);
            }
        });
    });

    presets.querySelectorAll('[data-atlas-preset]').forEach(button => {
        button.addEventListener('click', () => {
            const next = button.dataset.atlasPreset;
            const view = loadFullMapView();
            view.preset = next;
            saveFullMapView(view);
            applyAtlasFilters();
            if (fullMapNav && typeof fullMapNav.fitToView === 'function') {
                setTimeout(() => fullMapNav.fitToView(), 60);
            }
        });
    });
}

function updateAtlasButtons(state) {
    document.querySelectorAll('[data-atlas-tab]').forEach(button => {
        button.classList.toggle('active', button.dataset.atlasTab === state.tab);
    });
    document.querySelectorAll('[data-atlas-preset]').forEach(button => {
        button.classList.toggle('active', button.dataset.atlasPreset === state.preset);
    });
}

function getAllowedAtlasGroups(state) {
    const preset = ATLAS_PRESETS.find(p => p.id === state.preset) || ATLAS_PRESETS[0];
    const tab = ATLAS_TABS.find(t => t.id === state.tab) || ATLAS_TABS[0];
    let allowed = new Set(preset.groups || ALL_GROUP_IDS);
    if (tab.groups) {
        allowed = new Set(tab.groups.filter(id => allowed.has(id)));
    }
    return allowed;
}

function updateAtlasJumpList(allowedGroups) {
    const container = document.getElementById('admin-atlas-jump');
    if (!container) return;

    const groups = FULL_MAP_GROUPS.filter(group => allowedGroups.has(group.id));
    container.innerHTML = groups.map(group => `
        <button class="control-chip atlas-chip px-3 py-2 rounded-full" data-atlas-jump="${escapeHtml(group.id)}">${escapeHtml(group.title)}</button>
    `).join('');

    container.querySelectorAll('[data-atlas-jump]').forEach(button => {
        button.addEventListener('click', () => {
            const groupId = button.dataset.atlasJump;
            const groupEl = document.querySelector(`.full-map-group[data-group="${groupId}"]`);
            if (!groupEl) return;
            ensureGroupExpanded(groupId);
            centerAtlasElement(groupEl);
        });
    });
}

function ensureGroupExpanded(groupId) {
    const container = document.getElementById('admin-full-map-content');
    if (!container) return;
    const group = container.querySelector(`.full-map-group[data-group="${groupId}"]`);
    if (!group) return;
    if (group.classList.contains('collapsed')) {
        group.classList.remove('collapsed');
        const toggle = group.querySelector('[data-group-toggle]');
        if (toggle) toggle.textContent = 'Collapse';
        const collapsed = loadFullMapCollapsed();
        collapsed.delete(groupId);
        saveFullMapCollapsed(collapsed);
        syncFullMapStageSize();
        scheduleDrawFlowLines();
    }
}

function centerAtlasElement(element) {
    if (!fullMapNav || !element) return;
    const { container, nav, applyTransform } = fullMapNav;
    const rect = container.getBoundingClientRect();
    const elemRect = element.getBoundingClientRect();
    const deltaX = rect.left + rect.width / 2 - (elemRect.left + elemRect.width / 2);
    const deltaY = rect.top + rect.height / 2 - (elemRect.top + elemRect.height / 2);
    nav.origin.x += deltaX;
    nav.origin.y += deltaY;
    applyTransform();
}

function centerLuaMapElement(element) {
    if (!luaMapNav || !element) return;
    const { container, nav, applyTransform } = luaMapNav;
    const rect = container.getBoundingClientRect();
    const elemRect = element.getBoundingClientRect();
    const deltaX = rect.left + rect.width / 2 - (elemRect.left + elemRect.width / 2);
    const deltaY = rect.top + rect.height / 2 - (elemRect.top + elemRect.height / 2);
    nav.origin.x += deltaX;
    nav.origin.y += deltaY;
    applyTransform();
}

function applyAtlasFilters() {
    const view = loadFullMapView();
    const allowed = getAllowedAtlasGroups(view);
    updateAtlasButtons(view);
    updateFullMapSearchIndex(allowed);
    updateAtlasJumpList(allowed);

    document.querySelectorAll('.full-map-group').forEach(group => {
        const groupId = group.dataset.group;
        group.classList.toggle('atlas-hidden', !allowed.has(groupId));
    });

    syncFullMapStageSize();
    scheduleDrawFlowLines();
    applyFullStoryStep(fullStoryStepId, { skipCenter: true });
}

function renderFullStorySteps() {
    const container = document.getElementById('admin-full-story-steps');
    const detail = document.getElementById('admin-full-story-detail');
    if (!container) return;

    if (detail && !detail.dataset.defaultText) {
        detail.dataset.defaultText = detail.textContent || 'Select a step to see the explanation.';
    }

    const buttons = FULL_STORY_STEPS.map(step => `
        <button class="control-chip atlas-chip px-3 py-2 rounded-full" data-story-step="${escapeHtml(step.id)}">${escapeHtml(step.label)}</button>
    `).join('');

    container.innerHTML = `
        ${buttons}
        <button class="control-chip atlas-chip px-3 py-2 rounded-full" data-story-step="clear">Clear</button>
    `;

    container.querySelectorAll('[data-story-step]').forEach(button => {
        button.addEventListener('click', () => {
            const target = button.dataset.storyStep;
            if (target === 'clear') {
                applyFullStoryStep(null);
                return;
            }
            const next = fullStoryStepId === target ? null : target;
            applyFullStoryStep(next);
        });
    });

    updateStoryButtons();
}

function updateStoryButtons() {
    const container = document.getElementById('admin-full-story-steps');
    if (!container) return;
    container.querySelectorAll('[data-story-step]').forEach(button => {
        const id = button.dataset.storyStep;
        const isActive = id && id !== 'clear' && id === fullStoryStepId;
        button.classList.toggle('active', isActive);
    });
}

function centerFullMapNode(nodeId) {
    if (!nodeId) return;
    const entry = FULL_MAP_NODE_INDEX.find(node => node.id === nodeId);
    if (entry) {
        ensureGroupExpanded(entry.groupId);
    }
    const nodeEl = document.querySelector(`#admin-full-map [data-node="${nodeId}"]`);
    if (nodeEl) {
        centerAtlasElement(nodeEl);
    }
}

function applyFullStoryStep(stepId, options = {}) {
    const container = document.getElementById('admin-full-map');
    const svg = document.getElementById('admin-full-lines');
    const detail = document.getElementById('admin-full-story-detail');
    if (!container || !svg) return;

    const nodes = container.querySelectorAll('[data-node]');
    const lines = svg.querySelectorAll('path.flow-line');

    nodes.forEach(node => node.classList.remove('story-focus', 'story-dim'));
    lines.forEach(line => line.classList.remove('story-active', 'story-dim'));

    if (!stepId) {
        fullStoryStepId = null;
        container.classList.remove('story-mode');
        if (detail) {
            detail.textContent = detail.dataset.defaultText || 'Select a step to see the explanation.';
        }
        updateStoryButtons();
        return;
    }

    const step = FULL_STORY_STEPS.find(item => item.id === stepId);
    if (!step) return;

    fullStoryStepId = stepId;
    container.classList.add('story-mode');
    const focusSet = new Set(step.nodes || []);

    nodes.forEach(node => {
        const id = node.dataset.node;
        if (focusSet.has(id)) {
            node.classList.add('story-focus');
        } else {
            node.classList.add('story-dim');
        }
    });

    lines.forEach(line => {
        const from = line.dataset.from;
        const to = line.dataset.to;
        if (focusSet.has(from) || focusSet.has(to)) {
            line.classList.add('story-active');
        } else {
            line.classList.add('story-dim');
        }
    });

    if (detail) {
        detail.innerHTML = `
            <div class="text-[11px] uppercase tracking-[0.3em] text-slate-500">${escapeHtml(step.title)}</div>
            <div class="text-sm text-slate-300 mt-2">${escapeHtml(step.description)}</div>
        `;
    }

    updateStoryButtons();

    if (!options.skipCenter && step.focus) {
        centerFullMapNode(step.focus);
    }
}

function initFullMapNavigator() {
    if (fullMapReady) return;
    const container = document.getElementById('admin-full-map');
    const stage = document.getElementById('admin-full-stage');
    if (!container || !stage) return;

    const zoomIn = document.getElementById('admin-full-zoom-in');
    const zoomOut = document.getElementById('admin-full-zoom-out');
    const reset = document.getElementById('admin-full-reset');
    const fit = document.getElementById('admin-full-fit');
    const wideToggle = document.getElementById('admin-full-wide-toggle');
    const search = document.getElementById('admin-full-search');

    const state = loadFullMapState();
    let isDragging = false;
    let dragStart = { x: 0, y: 0 };
    const nav = {
        origin: { x: state.x, y: state.y },
        scale: Math.min(Math.max(state.scale, 0.3), 2.5)
    };

    const applyTransform = () => {
        stage.style.transform = `translate(${nav.origin.x}px, ${nav.origin.y}px) scale(${nav.scale})`;
        stage.dataset.scale = String(nav.scale);
        saveFullMapState({ x: nav.origin.x, y: nav.origin.y, scale: nav.scale });
    };

    const zoomAt = (delta, clientX, clientY) => {
        const rect = container.getBoundingClientRect();
        const cx = clientX - rect.left;
        const cy = clientY - rect.top;
        const nextScale = Math.min(2.5, Math.max(0.3, nav.scale * delta));
        const worldX = (cx - nav.origin.x) / nav.scale;
        const worldY = (cy - nav.origin.y) / nav.scale;
        nav.scale = nextScale;
        nav.origin.x = cx - worldX * nav.scale;
        nav.origin.y = cy - worldY * nav.scale;
        applyTransform();
    };

    const fitToView = () => {
        syncFullMapStageSize();
        const rect = container.getBoundingClientRect();
        const stageWidth = stage.offsetWidth || 1;
        const stageHeight = stage.offsetHeight || 1;
        const scaleX = rect.width / stageWidth;
        const scaleY = rect.height / stageHeight;
        nav.scale = Math.min(1.8, Math.max(0.3, Math.min(scaleX, scaleY) * 0.92));
        nav.origin.x = (rect.width - stageWidth * nav.scale) / 2;
        nav.origin.y = (rect.height - stageHeight * nav.scale) / 2;
        applyTransform();
    };

    const resetView = () => {
        nav.scale = 1;
        nav.origin = { x: 0, y: 0 };
        applyTransform();
    };

    const applyWide = (enabled) => {
        const bleed = document.getElementById('admin-full-bleed');
        container.classList.toggle('atlas-wide', enabled);
        if (bleed) bleed.classList.toggle('atlas-wide', enabled);
        if (wideToggle) {
            wideToggle.classList.toggle('active', enabled);
            wideToggle.textContent = enabled ? 'Wide: On' : 'Wide: Off';
        }
        localStorage.setItem(FULL_MAP_WIDE_KEY, enabled ? 'on' : 'off');
        syncFullMapStageSize();
        scheduleDrawFlowLines();
    };

    const savedWide = localStorage.getItem(FULL_MAP_WIDE_KEY);
    const initialWide = savedWide !== 'off';
    applyWide(initialWide);

    if (wideToggle) {
        wideToggle.addEventListener('click', () => {
            const enabled = !container.classList.contains('atlas-wide');
            applyWide(enabled);
        });
    }

    applyTransform();

    container.addEventListener('pointerdown', (event) => {
        if (event.button !== 0) return;
        if (event.target.closest('[data-node]') || event.target.closest('button') || event.target.closest('input')) {
            return;
        }
        isDragging = true;
        stage.classList.add('dragging');
        dragStart = { x: event.clientX, y: event.clientY };
        const state = loadFullMapState();
        nav.origin = { x: state.x, y: state.y };
        container.setPointerCapture(event.pointerId);
    });

    container.addEventListener('pointermove', (event) => {
        if (!isDragging) return;
        nav.origin.x = nav.origin.x + (event.clientX - dragStart.x);
        nav.origin.y = nav.origin.y + (event.clientY - dragStart.y);
        dragStart = { x: event.clientX, y: event.clientY };
        applyTransform();
    });

    container.addEventListener('pointerup', (event) => {
        if (!isDragging) return;
        isDragging = false;
        stage.classList.remove('dragging');
        container.releasePointerCapture(event.pointerId);
    });

    container.addEventListener('pointerleave', () => {
        if (!isDragging) return;
        isDragging = false;
        stage.classList.remove('dragging');
    });

    container.addEventListener('wheel', (event) => {
        event.preventDefault();
    }, { passive: false });

    if (zoomIn) zoomIn.addEventListener('click', () => zoomAt(1.12, container.getBoundingClientRect().left + container.offsetWidth / 2, container.getBoundingClientRect().top + container.offsetHeight / 2));
    if (zoomOut) zoomOut.addEventListener('click', () => zoomAt(0.88, container.getBoundingClientRect().left + container.offsetWidth / 2, container.getBoundingClientRect().top + container.offsetHeight / 2));
    if (reset) reset.addEventListener('click', resetView);
    if (fit) fit.addEventListener('click', fitToView);

    if (search) {
        search.addEventListener('change', () => {
            const value = search.value.trim().toLowerCase();
            if (!value) return;
            let targetId = null;
            try {
                const options = JSON.parse(search.dataset.mapIndex || '[]');
                const byLabel = options.find(opt => opt.label.toLowerCase() === value);
                const byId = options.find(opt => opt.id.toLowerCase() === value);
                targetId = byLabel?.id || byId?.id || null;
            } catch (err) {
                targetId = null;
            }
            if (!targetId) return;
            const node = container.querySelector(`[data-node="${targetId}"]`);
            if (!node) return;
            centerAtlasElement(node);
            node.classList.add('active-node');
            setTimeout(() => node.classList.remove('active-node'), 1200);
        });
    }

    window.addEventListener('resize', () => {
        syncFullMapStageSize();
    });

    fullMapNav = { container, stage, nav, applyTransform, fitToView };
    fitToView();
    fullMapReady = true;
}

function initLuaMapNavigator() {
    if (luaMapReady) return;
    const container = document.getElementById('admin-lua-map');
    const stage = document.getElementById('admin-lua-stage');
    if (!container || !stage) return;

    const zoomIn = document.getElementById('admin-lua-zoom-in');
    const zoomOut = document.getElementById('admin-lua-zoom-out');
    const reset = document.getElementById('admin-lua-reset');
    const fit = document.getElementById('admin-lua-fit');
    const wideToggle = document.getElementById('admin-lua-wide-toggle');
    const search = document.getElementById('admin-lua-search');

    const state = loadLuaMapState();
    let isDragging = false;
    let dragStart = { x: 0, y: 0 };
    const nav = {
        origin: { x: state.x, y: state.y },
        scale: Math.min(Math.max(state.scale, 0.3), 2.5)
    };

    const applyTransform = () => {
        stage.style.transform = `translate(${nav.origin.x}px, ${nav.origin.y}px) scale(${nav.scale})`;
        stage.dataset.scale = String(nav.scale);
        saveLuaMapState({ x: nav.origin.x, y: nav.origin.y, scale: nav.scale });
    };

    const zoomAt = (delta, clientX, clientY) => {
        const rect = container.getBoundingClientRect();
        const cx = clientX - rect.left;
        const cy = clientY - rect.top;
        const nextScale = Math.min(2.5, Math.max(0.3, nav.scale * delta));
        const worldX = (cx - nav.origin.x) / nav.scale;
        const worldY = (cy - nav.origin.y) / nav.scale;
        nav.scale = nextScale;
        nav.origin.x = cx - worldX * nav.scale;
        nav.origin.y = cy - worldY * nav.scale;
        applyTransform();
    };

    const fitToView = () => {
        syncLuaMapStageSize();
        const rect = container.getBoundingClientRect();
        const stageWidth = stage.offsetWidth || 1;
        const stageHeight = stage.offsetHeight || 1;
        const scaleX = rect.width / stageWidth;
        const scaleY = rect.height / stageHeight;
        nav.scale = Math.min(1.8, Math.max(0.3, Math.min(scaleX, scaleY) * 0.92));
        nav.origin.x = (rect.width - stageWidth * nav.scale) / 2;
        nav.origin.y = (rect.height - stageHeight * nav.scale) / 2;
        applyTransform();
    };

    const resetView = () => {
        nav.scale = 1;
        nav.origin = { x: 0, y: 0 };
        applyTransform();
    };

    const applyWide = (enabled) => {
        const bleed = document.getElementById('admin-lua-bleed');
        container.classList.toggle('atlas-wide', enabled);
        if (bleed) bleed.classList.toggle('atlas-wide', enabled);
        if (wideToggle) {
            wideToggle.classList.toggle('active', enabled);
            wideToggle.textContent = enabled ? 'Wide: On' : 'Wide: Off';
        }
        localStorage.setItem(LUA_MAP_WIDE_KEY, enabled ? 'on' : 'off');
        syncLuaMapStageSize();
        scheduleDrawFlowLines();
    };

    const savedWide = localStorage.getItem(LUA_MAP_WIDE_KEY);
    const initialWide = savedWide !== 'off';
    applyWide(initialWide);

    if (wideToggle) {
        wideToggle.addEventListener('click', () => {
            const enabled = !container.classList.contains('atlas-wide');
            applyWide(enabled);
        });
    }

    applyTransform();

    container.addEventListener('pointerdown', (event) => {
        if (event.button !== 0) return;
        if (event.target.closest('[data-node]') || event.target.closest('button') || event.target.closest('input')) {
            return;
        }
        isDragging = true;
        stage.classList.add('dragging');
        dragStart = { x: event.clientX, y: event.clientY };
        const state = loadLuaMapState();
        nav.origin = { x: state.x, y: state.y };
        container.setPointerCapture(event.pointerId);
    });

    container.addEventListener('pointermove', (event) => {
        if (!isDragging) return;
        nav.origin.x = nav.origin.x + (event.clientX - dragStart.x);
        nav.origin.y = nav.origin.y + (event.clientY - dragStart.y);
        dragStart = { x: event.clientX, y: event.clientY };
        applyTransform();
    });

    container.addEventListener('pointerup', (event) => {
        if (!isDragging) return;
        isDragging = false;
        stage.classList.remove('dragging');
        container.releasePointerCapture(event.pointerId);
    });

    container.addEventListener('pointerleave', () => {
        if (!isDragging) return;
        isDragging = false;
        stage.classList.remove('dragging');
    });

    container.addEventListener('wheel', (event) => {
        event.preventDefault();
    }, { passive: false });

    if (zoomIn) zoomIn.addEventListener('click', () => zoomAt(1.12, container.getBoundingClientRect().left + container.offsetWidth / 2, container.getBoundingClientRect().top + container.offsetHeight / 2));
    if (zoomOut) zoomOut.addEventListener('click', () => zoomAt(0.88, container.getBoundingClientRect().left + container.offsetWidth / 2, container.getBoundingClientRect().top + container.offsetHeight / 2));
    if (reset) reset.addEventListener('click', resetView);
    if (fit) fit.addEventListener('click', fitToView);

    if (search) {
        search.addEventListener('change', () => {
            const value = search.value.trim().toLowerCase();
            if (!value) return;
            let targetId = null;
            try {
                const options = JSON.parse(search.dataset.mapIndex || '[]');
                const byLabel = options.find(opt => opt.label.toLowerCase() === value);
                const byId = options.find(opt => opt.id.toLowerCase() === value);
                targetId = byLabel?.id || byId?.id || null;
            } catch (err) {
                targetId = null;
            }
            if (!targetId) return;
            const node = container.querySelector(`[data-node="${targetId}"]`);
            if (!node) return;
            centerLuaMapElement(node);
            node.classList.add('active-node');
            setTimeout(() => node.classList.remove('active-node'), 1200);
        });
    }

    window.addEventListener('resize', () => {
        syncLuaMapStageSize();
    });

    luaMapNav = { container, stage, nav, applyTransform, fitToView };
    fitToView();
    luaMapReady = true;
}

function buildFlowMarkers() {
    const defs = document.createElementNS(SVG_NS, 'defs');
    Object.entries(FLOW_COLORS).forEach(([type, color]) => {
        const marker = document.createElementNS(SVG_NS, 'marker');
        marker.setAttribute('id', `arrow-${type}`);
        marker.setAttribute('markerWidth', '10');
        marker.setAttribute('markerHeight', '10');
        marker.setAttribute('refX', '8');
        marker.setAttribute('refY', '5');
        marker.setAttribute('orient', 'auto');
        marker.setAttribute('markerUnits', 'strokeWidth');
        const path = document.createElementNS(SVG_NS, 'path');
        path.setAttribute('d', 'M 0 0 L 10 5 L 0 10 z');
        path.setAttribute('fill', color);
        marker.appendChild(path);
        defs.appendChild(marker);
    });
    return defs;
}

function getAnchorPoints(fromRect, toRect, containerRect) {
    const fromCenterX = fromRect.left + fromRect.width / 2;
    const fromCenterY = fromRect.top + fromRect.height / 2;
    const toCenterX = toRect.left + toRect.width / 2;
    const toCenterY = toRect.top + toRect.height / 2;
    const dx = toCenterX - fromCenterX;
    const dy = toCenterY - fromCenterY;

    let startX;
    let startY;
    let endX;
    let endY;
    let orientation = 'horizontal';

    if (Math.abs(dx) >= Math.abs(dy)) {
        startX = dx >= 0 ? fromRect.right : fromRect.left;
        endX = dx >= 0 ? toRect.left : toRect.right;
        startY = fromCenterY;
        endY = toCenterY;
    } else {
        orientation = 'vertical';
        startY = dy >= 0 ? fromRect.bottom : fromRect.top;
        endY = dy >= 0 ? toRect.top : toRect.bottom;
        startX = fromCenterX;
        endX = toCenterX;
    }

    return {
        startX: startX - containerRect.left,
        startY: startY - containerRect.top,
        endX: endX - containerRect.left,
        endY: endY - containerRect.top,
        orientation
    };
}

function drawFlowLinesForMap(containerId, svgId, connections) {
    const container = document.getElementById(containerId);
    const svg = document.getElementById(svgId);
    if (!container || !svg) return;

    const useOffsets = container.dataset.flowStage === 'true';
    const rect = useOffsets
        ? { left: 0, top: 0, width: container.clientWidth, height: container.clientHeight }
        : container.getBoundingClientRect();
    if (!rect.width || !rect.height) return;

    svg.setAttribute('width', rect.width);
    svg.setAttribute('height', rect.height);
    svg.setAttribute('viewBox', `0 0 ${rect.width} ${rect.height}`);
    while (svg.firstChild) {
        svg.removeChild(svg.firstChild);
    }

    svg.appendChild(buildFlowMarkers());

    connections.forEach((connection) => {
        const fromEl = container.querySelector(`[data-node="${connection.from}"]`);
        const toEl = container.querySelector(`[data-node="${connection.to}"]`);
        if (!fromEl || !toEl) return;
        if (fromEl.offsetParent === null || toEl.offsetParent === null) return;

        const fromRect = useOffsets ? getOffsetRect(fromEl, container) : fromEl.getBoundingClientRect();
        const toRect = useOffsets ? getOffsetRect(toEl, container) : toEl.getBoundingClientRect();
        const anchor = getAnchorPoints(fromRect, toRect, rect);
        if (!anchor) return;

        const { startX, startY, endX, endY, orientation } = anchor;
        const distance = orientation === 'vertical' ? Math.abs(endY - startY) : Math.abs(endX - startX);
        const curve = Math.min(180, Math.max(60, distance * 0.35));
        let cp1x;
        let cp1y;
        let cp2x;
        let cp2y;

        if (orientation === 'vertical') {
            const direction = endY >= startY ? 1 : -1;
            cp1x = startX;
            cp1y = startY + curve * direction;
            cp2x = endX;
            cp2y = endY - curve * direction;
        } else {
            const direction = endX >= startX ? 1 : -1;
            cp1x = startX + curve * direction;
            cp1y = startY;
            cp2x = endX - curve * direction;
            cp2y = endY;
        }

        const path = document.createElementNS(SVG_NS, 'path');
        path.setAttribute('d', `M ${startX} ${startY} C ${cp1x} ${cp1y} ${cp2x} ${cp2y} ${endX} ${endY}`);
        path.setAttribute('class', `flow-line ${connection.type || 'core'}`);
        path.dataset.from = connection.from;
        path.dataset.to = connection.to;
        const markerType = FLOW_COLORS[connection.type] ? connection.type : 'core';
        path.setAttribute('marker-end', `url(#arrow-${markerType})`);
        const label = connection.label || 'Data moves';
        const fromTitle = getNodeTitle(connection.from);
        const toTitle = getNodeTitle(connection.to);
        const tooltip = `${fromTitle} → ${toTitle}: ${label}`;
        path.dataset.flowLabel = tooltip;
        path.setAttribute('aria-label', tooltip);
        svg.appendChild(path);
    });
}

function drawAllFlowLines() {
    drawFlowLinesForMap('admin-flow-map', 'admin-flow-lines', FLOW_CONNECTIONS);
    drawFlowLinesForMap('admin-full-stage', 'admin-full-lines', FULL_FLOW_CONNECTIONS);
    drawFlowLinesForMap('admin-lua-stage', 'admin-lua-lines', LUA_FLOW_CONNECTIONS);
    applyFlowMapFocus(flowMapFocusId);
    applyFullMapFocus(fullMapFocusId);
    applyLuaMapFocus(luaMapFocusId);
    if (fullStoryStepId) {
        applyFullStoryStep(fullStoryStepId, { skipCenter: true });
    }
}

function initFlowLines() {
    if (flowInitialized) return;
    window.addEventListener('resize', scheduleDrawFlowLines);
    flowInitialized = true;
}

function titleize(raw) {
    return raw
        .replace(/_/g, ' ')
        .replace(/-/g, ' ')
        .replace(/\b\w/g, (match) => match.toUpperCase());
}

function buildFallbackDetails(id, meta = {}) {
    if (!id) return null;
    const pretty = titleize(id);
    const tag = (meta?.tag || '').toLowerCase();
    const group = (meta?.group || '').toLowerCase();
    const lower = id.toLowerCase();

    const role = (() => {
        if (lower.startsWith('lua_et_') || lower.includes('lua_et_')) return 'lua_hook';
        if (lower.startsWith('lua_') && (lower.includes('time_') || lower.includes('death_time') || lower.includes('denied'))) return 'lua_timer';
        if (lower.startsWith('lua_')) return 'lua';
        if (lower.startsWith('script_') || tag === 'script') return 'script';
        if (lower.startsWith('tool_') || tag === 'tool') return 'tool';
        if (lower.startsWith('diag_') || tag === 'diag' || group === 'diagnostics') return 'diagnostic';
        if (tag === 'server' || lower.includes('server') || lower.includes('host')) return 'server';
        if (lower.includes('webhook')) return 'webhook';
        if (lower.includes('ingest') || lower.includes('monitor')) return 'ingest';
        if (lower.includes('parser')) return 'parser';
        if (lower.includes('validation') || lower.includes('caps')) return 'validation';
        if (lower.startsWith('table_') || tag === 'table') return 'table';
        if (FULL_COGS.includes(id) || lower.endsWith('_cog') || lower.includes('cog') || tag === 'cog') return 'cog';
        if (FULL_SERVICES.includes(id) || lower.endsWith('_service') || tag === 'service') return 'service';
        if (FULL_CORE.includes(id) || lower.startsWith('core_')) return 'core';
        if (lower.includes('api') || tag === 'api' || lower.includes('router')) return 'api';
        if (tag === 'ui' || lower.includes('frontend') || lower.includes('panel')) return 'ui';
        if (tag === 'db' || lower === 'postgres' || lower.includes('database')) return 'db';
        if (lower.includes('config') || tag === 'config') return 'config';
        if (tag === 'ops' || group === 'monitoring') return 'ops';
        if (tag === 'people' || lower === 'players' || lower.includes('players')) return 'people';
        if (tag === 'discord' || lower.includes('discord')) return 'discord';
        if (tag === 'file' || lower.includes('files') || lower.endsWith('.txt')) return 'file';
        return 'module';
    })();

    const connectionSummary = getConnectionSummary(id);

    if (role === 'cog') {
        return {
            title: `Cog: ${pretty.replace(/ Cog/i, '')}`,
            eli5: 'A Discord command module. It listens for chat commands and turns them into stats queries and embeds.',
            summary: `Discord command module for ${pretty.replace(/ Cog/i, '').toLowerCase()} requests.`,
            why: 'Gives players a simple way to ask for stats without touching the database.',
            how: 'Loaded by the bot at startup; each command calls services or database queries.',
            inputs: 'Discord messages + database queries.',
            outputs: 'Discord embeds and responses.',
            links: connectionSummary
        };
    }
    if (role === 'service') {
        return {
            title: `Service: ${pretty.replace(/ Service/i, '')}`,
            eli5: 'A reusable helper that does heavy lifting for the bot (math, formatting, analytics).',
            summary: `Background service for ${pretty.replace(/ Service/i, '').toLowerCase()}.`,
            why: 'Keeps cogs small and consistent by putting shared logic in one place.',
            how: 'Called by cogs or tasks; returns structured results.',
            inputs: 'Database rows + configs.',
            outputs: 'Processed stats ready for Discord.',
            links: connectionSummary
        };
    }
    if (role === 'core') {
        return {
            title: `Core: ${pretty}`,
            eli5: 'Shared logic the whole system relies on.',
            summary: `Core helper module: ${pretty.toLowerCase()}.`,
            why: 'Prevents duplication and ensures consistent decisions across features.',
            how: 'Used by multiple cogs and services.',
            inputs: 'Stats + metadata.',
            outputs: 'Processed results.',
            links: connectionSummary
        };
    }
    if (role === 'table') {
        return {
            title: `Table: ${pretty.replace('Table ', '')}`,
            eli5: 'A database table that stores stats so we can query history later.',
            summary: `Database table ${pretty.replace('Table ', '').toLowerCase()}.`,
            why: 'Turns raw files into permanent, queryable records.',
            how: 'Written during imports; read by bot and website.',
            inputs: 'Parsed stats.',
            outputs: 'Query results.',
            links: connectionSummary
        };
    }
    if (role === 'parser') {
        return {
            title: `Parser: ${pretty}`,
            eli5: 'The translator. It turns raw text files into clean numbers.',
            summary: `Parses raw stats files into structured data.`,
            why: 'Without parsing, Discord would have unreadable text instead of stats.',
            how: 'Reads gamestats/endstats files and extracts player + weapon fields.',
            inputs: 'Raw stats files.',
            outputs: 'Structured stats objects for database writes.',
            links: connectionSummary
        };
    }
    if (role === 'ingest') {
        return {
            title: `Ingest: ${pretty}`,
            eli5: 'The file catcher. It watches for new files and brings them into the pipeline.',
            summary: 'Detects and queues new stats files for parsing.',
            why: 'Moves raw files from the game server into the bot pipeline.',
            how: 'Scans directories or listens for webhook triggers.',
            inputs: 'New file arrivals or webhook alerts.',
            outputs: 'Queued files for parsing.',
            links: connectionSummary
        };
    }
    if (role === 'validation') {
        return {
            title: `Validation: ${pretty}`,
            eli5: 'The sanity checker. It stops impossible stats from entering the database.',
            summary: 'Applies caps and consistency rules to parsed stats.',
            why: 'Prevents bad data from corrupting leaderboards.',
            how: 'Checks ratios, time limits, and known edge cases.',
            inputs: 'Parsed stats.',
            outputs: 'Validated stats.',
            links: connectionSummary
        };
    }
    if (role === 'db') {
        return {
            title: `Database: ${pretty.replace(/postgres/i, 'PostgreSQL')}`,
            eli5: 'The long-term memory of the project. Every stat lives here.',
            summary: 'Stores all rounds, players, weapons, and sessions.',
            why: 'Lets Discord and the website query stats instantly.',
            how: 'Receives inserts from the import pipeline and serves queries.',
            inputs: 'Validated stats writes.',
            outputs: 'Query results for commands and UI.',
            links: connectionSummary
        };
    }
    if (role === 'api') {
        return {
            title: `API: ${pretty}`,
            eli5: 'The website door. It answers web requests for stats.',
            summary: 'Website backend endpoint that returns JSON.',
            why: 'Lets the public website fetch data from the database safely.',
            how: 'Handles HTTP requests and queries the DB.',
            inputs: 'HTTP requests.',
            outputs: 'JSON responses.',
            links: connectionSummary
        };
    }
    if (role === 'ui') {
        return {
            title: `UI: ${pretty}`,
            eli5: 'The screen people see. It turns data into readable visuals.',
            summary: 'Frontend component that displays stats.',
            why: 'Humans need visuals, not raw numbers.',
            how: 'Requests JSON from the API and renders cards, charts, and tables.',
            inputs: 'API JSON responses.',
            outputs: 'Visual UI.',
            links: connectionSummary
        };
    }
    if (role === 'webhook') {
        return {
            title: `Webhook: ${pretty}`,
            eli5: 'A real-time ping that moves data instantly instead of waiting.',
            summary: 'Sends or receives real-time signals about round timing.',
            why: 'Fixes timing accuracy and speeds up Discord posting.',
            how: 'Posts JSON payloads that trigger the ingest pipeline.',
            inputs: 'Round start/end events.',
            outputs: 'Webhook payloads or stored timing rows.',
            links: connectionSummary
        };
    }
    if (role === 'server') {
        return {
            title: `Server: ${pretty}`,
            eli5: 'A machine or process that runs the game or bot.',
            summary: 'Infrastructure that hosts the game server or bot stack.',
            why: 'Stats only exist if the server is alive and running.',
            how: 'Runs ET:Legacy, Lua scripts, or the bot pipeline.',
            inputs: 'Player connections or service processes.',
            outputs: 'Game events, files, or API responses.',
            links: connectionSummary
        };
    }
    if (role === 'people') {
        return {
            title: 'Players',
            eli5: 'Real humans creating the data.',
            summary: 'Players generate every kill, death, and objective event.',
            why: 'No players means no stats.',
            how: 'They play the game and use Discord commands.',
            inputs: 'Gameplay and voice activity.',
            outputs: 'Stats events and Discord commands.',
            links: connectionSummary
        };
    }
    if (role === 'lua_hook') {
        return {
            title: `Lua Hook: ${pretty.replace(/Lua Et /i, 'et_')}`,
            eli5: 'A built-in game callback that fires on a specific event.',
            summary: 'Lua callback invoked by the game engine.',
            why: 'Captures the exact moment events happen (kills, spawns, round end).',
            how: 'ET:Legacy calls this function; it updates timers or stats buffers.',
            inputs: 'Live game events.',
            outputs: 'Updated Lua stats.',
            links: connectionSummary
        };
    }
    if (role === 'lua_timer') {
        return {
            title: `Lua Timer: ${pretty}`,
            eli5: 'A Lua-side counter that tracks time in milliseconds.',
            summary: 'Accumulates timing stats like time dead or time denied.',
            why: 'Timing accuracy needs exact start/stop tracking inside the game.',
            how: 'Starts on death, ends on spawn, then converts to seconds/minutes.',
            inputs: 'Lua timestamps.',
            outputs: 'Timing fields in the stats file.',
            links: connectionSummary
        };
    }
    if (role === 'lua') {
        return {
            title: `Lua Script: ${pretty.replace(/Lua /i, '')}`,
            eli5: 'A script running inside the game server that creates the raw stats.',
            summary: 'Collects in-game events and writes stats or timing data.',
            why: 'Without Lua, the game does not store stats at all.',
            how: 'Hooks ET events and writes gamestats or webhook payloads.',
            inputs: 'Live game events.',
            outputs: 'Stats files or webhook timing data.',
            links: connectionSummary
        };
    }
    if (role === 'config') {
        return {
            title: `Config: ${pretty}`,
            eli5: 'Settings that control how the system behaves.',
            summary: 'Configuration values read at startup.',
            why: 'Lets us change behavior without rewriting code.',
            how: 'Loaded by the bot or services on startup.',
            inputs: 'Config values.',
            outputs: 'Runtime settings.',
            links: connectionSummary
        };
    }
    if (role === 'ops') {
        return {
            title: `Ops: ${pretty}`,
            eli5: 'Operational tooling that keeps the system alive.',
            summary: 'Monitoring, automation, or maintenance process.',
            why: 'Keeps the pipeline stable and detects failures.',
            how: 'Runs on timers or system hooks.',
            inputs: 'Logs, health checks, configs.',
            outputs: 'Alerts, restarts, or maintenance actions.',
            links: connectionSummary
        };
    }
    if (role === 'script') {
        return {
            title: `Script: ${pretty.replace(/Script/i, '').trim()}`,
            eli5: 'A manual helper you run to fix or backfill data.',
            summary: 'One-off or periodic maintenance script.',
            why: 'Used when we need to correct data or migrate stats safely.',
            how: 'Run from the command line; writes to the database or files.',
            inputs: 'Database rows, files, or configs.',
            outputs: 'Data fixes, reports, or backups.',
            links: connectionSummary
        };
    }
    if (role === 'tool') {
        return {
            title: `Tool: ${pretty.replace(/Tool/i, '').trim()}`,
            eli5: 'A small helper for testing or previews.',
            summary: 'Dev/QA helper tool for quick checks.',
            why: 'Speeds up debugging without digging through raw logs.',
            how: 'Runs a targeted check and reports output.',
            inputs: 'Local data or API calls.',
            outputs: 'Quick diagnostics or previews.',
            links: connectionSummary
        };
    }
    if (role === 'diagnostic') {
        return {
            title: `Diagnostic: ${pretty.replace(/Diag/i, '').trim()}`,
            eli5: 'A health check that tells us what’s broken.',
            summary: 'Consistency or integrity check for stats.',
            why: 'Catches bad imports and missing data early.',
            how: 'Scans rows and reports issues.',
            inputs: 'Database tables.',
            outputs: 'Warnings or pass/fail summaries.',
            links: connectionSummary
        };
    }
    if (role === 'discord') {
        return {
            title: `Discord: ${pretty}`,
            eli5: 'Where players see the stats and use commands.',
            summary: 'Discord platform surface for bot messages.',
            why: 'Discord is the main frontend for players.',
            how: 'Bot posts embeds and listens for commands.',
            inputs: 'Bot responses + player commands.',
            outputs: 'Messages and embeds.',
            links: connectionSummary
        };
    }
    if (role === 'file') {
        return {
            title: `File Output: ${pretty}`,
            eli5: 'A raw file written by Lua or the pipeline.',
            summary: 'Stats or telemetry output file.',
            why: 'Acts as the raw source of truth before parsing.',
            how: 'Generated by Lua scripts on round end.',
            inputs: 'In-game stats.',
            outputs: 'Text files for ingestion.',
            links: connectionSummary
        };
    }
    return {
        title: pretty,
        eli5: 'A system module that helps move stats from the game to Discord.',
        summary: `System module: ${pretty.toLowerCase()}.`,
        why: 'Plays a role in the stats pipeline.',
        how: 'Participates in data flow between game, database, and Discord.',
        inputs: 'Upstream data.',
        outputs: 'Downstream data.',
        links: connectionSummary
    };
}

function mergeDetails(details, fallback) {
    if (!details) return fallback;
    const merged = { ...fallback, ...details };
    const minLen = 45;
    const mergeField = (key) => {
        const primary = details?.[key];
        const secondary = fallback?.[key];
        if (!primary) return secondary;
        if (!secondary) return primary;
        if (primary.length >= minLen) return primary;
        return `${primary} ${secondary}`;
    };
    merged.eli5 = mergeField('eli5');
    merged.summary = mergeField('summary');
    merged.why = mergeField('why');
    merged.how = mergeField('how');
    merged.inputs = mergeField('inputs');
    merged.outputs = mergeField('outputs');
    merged.files = mergeField('files');
    merged.links = mergeField('links');
    return merged;
}

function renderDetails(details, id, meta = {}) {
    const fallback = meta.disableFallback ? details : buildFallbackDetails(id, meta);
    const resolved = meta.disableFallback ? details : mergeDetails(details, fallback);
    if (!resolved) {
        return `
            <div class="detail-title">Details</div>
            <div class="detail-row">
                <div class="detail-label">Info</div>
                <div class="detail-value">No description available yet.</div>
            </div>
        `;
    }
    const rows = [
        { label: 'ELI5', value: resolved.eli5 },
        { label: 'Summary', value: resolved.summary },
        { label: 'Why', value: resolved.why },
        { label: 'How', value: resolved.how },
        { label: 'Inputs', value: resolved.inputs },
        { label: 'Outputs', value: resolved.outputs },
        { label: 'Links', value: resolved.links },
        { label: 'Files', value: resolved.files },
    ].filter(row => row.value);

    return `
        <div class="detail-title">${escapeHtml(resolved.title || 'Details')}</div>
        ${rows.map(row => `
            <div class="detail-row" data-label="${escapeHtml(row.label)}">
                <div class="detail-label">${escapeHtml(row.label)}</div>
                <div class="detail-value">${escapeHtml(row.value)}</div>
            </div>
        `).join('')}
    `;
}

function getNodeTitle(id) {
    const detail = NODE_DETAILS[id] || buildFallbackDetails(id);
    return detail?.title || id;
}

function getConnectionSummary(id) {
    if (!id) return '';
    const upstream = new Set();
    const downstream = new Set();
    const connections = [
        ...FLOW_CONNECTIONS,
        ...FULL_FLOW_CONNECTIONS,
        ...LUA_FLOW_CONNECTIONS
    ];
    connections.forEach((connection) => {
        if (connection.to === id) upstream.add(connection.from);
        if (connection.from === id) downstream.add(connection.to);
    });
    const formatTitle = (nodeId) => NODE_DETAILS[nodeId]?.title || titleize(nodeId);
    const formatList = (items) => items
        .map(item => formatTitle(item))
        .filter(Boolean)
        .slice(0, 4)
        .join(', ');
    const upText = formatList(Array.from(upstream));
    const downText = formatList(Array.from(downstream));
    if (!upText && !downText) return '';
    if (upText && downText) {
        return `Upstream: ${upText}. Downstream: ${downText}.`;
    }
    if (upText) return `Upstream: ${upText}.`;
    return `Downstream: ${downText}.`;
}

function applyStoryMode(enabled) {
    const adminView = document.getElementById('view-admin');
    if (!adminView) return;
    adminView.classList.toggle('story-mode', enabled);
}

function bindStoryModeControls() {
    const toggle = document.getElementById('admin-story-toggle');
    if (!toggle) return;
    const saved = localStorage.getItem(STORY_MODE_KEY);
    const initial = saved === 'on';
    applyStoryMode(initial);
    toggle.textContent = initial ? 'Story Mode: On' : 'Story Mode: Off';
    toggle.classList.toggle('active', initial);
    toggle.addEventListener('click', () => {
        const next = !toggle.classList.contains('active');
        toggle.classList.toggle('active', next);
        toggle.textContent = next ? 'Story Mode: On' : 'Story Mode: Off';
        localStorage.setItem(STORY_MODE_KEY, next ? 'on' : 'off');
        applyStoryMode(next);
    });
}

function ensureFlowTooltip(container, tooltipId) {
    let tooltip = document.getElementById(tooltipId);
    if (!tooltip) {
        tooltip = document.createElement('div');
        tooltip.id = tooltipId;
        tooltip.className = 'flow-tooltip';
        tooltip.style.opacity = '0';
        tooltip.style.left = '0px';
        tooltip.style.top = '0px';
        container.appendChild(tooltip);
    }
    return tooltip;
}

function bindFlowTooltipsForMap(containerId, svgId, tooltipId) {
    const container = document.getElementById(containerId);
    const svg = document.getElementById(svgId);
    if (!container || !svg) return;
    const tooltip = ensureFlowTooltip(container, tooltipId);

    const hideTooltip = () => {
        tooltip.style.opacity = '0';
    };

    svg.addEventListener('mousemove', (event) => {
        const target = event.target;
        if (!target || target.tagName !== 'path' || !target.dataset.flowLabel) {
            hideTooltip();
            return;
        }

        const rect = container.getBoundingClientRect();
        tooltip.textContent = target.dataset.flowLabel;
        tooltip.style.opacity = '1';

        const offset = 12;
        const maxX = rect.width - tooltip.offsetWidth - offset;
        const maxY = rect.height - tooltip.offsetHeight - offset;
        const left = Math.max(offset, Math.min(event.clientX - rect.left + offset, maxX));
        const top = Math.max(offset, Math.min(event.clientY - rect.top + offset, maxY));
        tooltip.style.left = `${left}px`;
        tooltip.style.top = `${top}px`;
    });

    svg.addEventListener('mouseleave', hideTooltip);
}

function bindFlowTooltips() {
    bindFlowTooltipsForMap('admin-flow-map', 'admin-flow-lines', 'admin-flow-tooltip');
    bindFlowTooltipsForMap('admin-full-map', 'admin-full-lines', 'admin-full-tooltip');
    bindFlowTooltipsForMap('admin-lua-map', 'admin-lua-lines', 'admin-lua-tooltip');
}

const WALKTHROUGH_STEPS = [
    {
        selector: '#admin-flow-map',
        title: 'The Big Picture',
        text: 'Every box is a real system. Lines show where data goes next.'
    },
    {
        selector: '[data-node="et_server"]',
        title: 'Game Server',
        text: 'The match runs here. It creates the raw events and stats.'
    },
    {
        selector: '[data-node="lua_c0rnp0rn7"]',
        title: 'Lua Stats File',
        text: 'This script writes the main stats file each round.'
    },
    {
        selector: '[data-node="stats_parser"]',
        title: 'Parser',
        text: 'Turns raw text into clean numbers we can store.'
    },
    {
        selector: '[data-node="postgres"]',
        title: 'Database',
        text: 'The official source of truth for all stats.'
    },
    {
        selector: '[data-node="session_embed_builder"]',
        title: 'Session Summary',
        text: 'Builds the Discord summary for !last_session.'
    },
    {
        selector: '[data-node="discord_bot"]',
        title: 'Discord Bot',
        text: 'Posts results and responds to commands.'
    },
    {
        selector: '[data-node="website_api"]',
        title: 'Website API',
        text: 'The website asks for data here.'
    },
    {
        selector: '[data-metric="time_dead"]',
        title: 'Data Quality Lights',
        text: 'Use these lights to mark what is working or broken.'
    },
    {
        selector: '#admin-checklist',
        title: 'Checklist',
        text: 'Tap items to track what you are fixing right now.'
    }
];

let walkthroughIndex = 0;
let walkthroughActive = false;

function clearWalkthroughFocus() {
    document.querySelectorAll('.walkthrough-focus').forEach((el) => {
        el.classList.remove('walkthrough-focus');
    });
}

function findValidStep(startIndex) {
    let index = startIndex;
    while (index >= 0 && index < WALKTHROUGH_STEPS.length) {
        const step = WALKTHROUGH_STEPS[index];
        const target = document.querySelector(step.selector);
        if (target) return { index, step, target };
        index += 1;
    }
    return null;
}

function applyWalkthroughStep(index) {
    const panel = document.getElementById('admin-walkthrough');
    const title = document.getElementById('walkthrough-title');
    const text = document.getElementById('walkthrough-text');
    const progress = document.getElementById('walkthrough-progress');
    if (!panel || !title || !text || !progress) return;

    const resolved = findValidStep(index);
    if (!resolved) {
        stopWalkthrough();
        return;
    }

    walkthroughIndex = resolved.index;
    const { step, target } = resolved;
    clearWalkthroughFocus();
    target.classList.add('walkthrough-focus');
    target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    title.textContent = step.title;
    text.textContent = step.text;
    progress.textContent = `${walkthroughIndex + 1} / ${WALKTHROUGH_STEPS.length}`;
    panel.classList.remove('hidden');
    panel.setAttribute('aria-hidden', 'false');
}

function startWalkthrough() {
    walkthroughActive = true;
    applyWalkthroughStep(0);
}

function stopWalkthrough() {
    walkthroughActive = false;
    clearWalkthroughFocus();
    const panel = document.getElementById('admin-walkthrough');
    if (panel) {
        panel.classList.add('hidden');
        panel.setAttribute('aria-hidden', 'true');
    }
}

function bindWalkthroughControls() {
    const start = document.getElementById('admin-walkthrough-start');
    const next = document.getElementById('walkthrough-next');
    const prev = document.getElementById('walkthrough-prev');
    const exit = document.getElementById('walkthrough-exit');
    const panel = document.getElementById('admin-walkthrough');

    if (start) {
        start.addEventListener('click', () => {
            startWalkthrough();
        });
    }
    if (next) {
        next.addEventListener('click', () => {
            if (!walkthroughActive) return;
            applyWalkthroughStep(walkthroughIndex + 1);
        });
    }
    if (prev) {
        prev.addEventListener('click', () => {
            if (!walkthroughActive) return;
            const nextIndex = Math.max(0, walkthroughIndex - 1);
            applyWalkthroughStep(nextIndex);
        });
    }
    if (exit) {
        exit.addEventListener('click', () => {
            stopWalkthrough();
        });
    }
    if (panel) {
        panel.addEventListener('click', (event) => {
            if (event.target === panel) {
                stopWalkthrough();
            }
        });
    }
}

function buildInlineNodeControls() {
    return `
        <div class="node-controls inline-controls mt-3 flex flex-wrap gap-2">
            <button class="control-chip px-2 py-1 rounded-full" data-set-status="auto">Auto</button>
            <button class="control-chip px-2 py-1 rounded-full" data-set-status="green">Green</button>
            <button class="control-chip px-2 py-1 rounded-full" data-set-status="blue">Blue</button>
            <button class="control-chip px-2 py-1 rounded-full" data-set-status="red">Red</button>
            <button class="control-chip px-2 py-1 rounded-full" data-set-status="black">Black</button>
        </div>
    `;
}

function setAtlasDetails(panelKey, html) {
    const panel = document.getElementById(`admin-${panelKey}-details-panel`);
    const content = document.getElementById(`admin-${panelKey}-details-content`);
    if (!panel || !content) return;
    content.innerHTML = html;
    panel.classList.add('active');
    panel.scrollTop = 0;
}

function resetAtlasDetails(panelKey) {
    const panel = document.getElementById(`admin-${panelKey}-details-panel`);
    const content = document.getElementById(`admin-${panelKey}-details-content`);
    if (!panel || !content) return;
    panel.classList.remove('active');
    content.innerHTML = panelKey === 'lua'
        ? 'Click a Lua node to read a full explanation here.'
        : 'Click a box to read a full explanation here.';
}

function bindAtlasDetailsControls() {
    const fullClear = document.getElementById('admin-full-details-clear');
    const luaClear = document.getElementById('admin-lua-details-clear');
    const fullCollapse = document.getElementById('admin-full-details-collapse');
    const luaCollapse = document.getElementById('admin-lua-details-collapse');
    const fullToggle = document.getElementById('admin-full-details-toggle');
    const luaToggle = document.getElementById('admin-lua-details-toggle');

    if (fullClear) {
        fullClear.addEventListener('click', (event) => {
            event.preventDefault();
            resetAtlasDetails('full');
            document.querySelectorAll('#admin-full-map [data-node].expanded').forEach(el => el.classList.remove('expanded'));
        });
    }
    if (fullCollapse) {
        fullCollapse.addEventListener('click', (event) => {
            event.preventDefault();
            const panel = document.getElementById('admin-full-details-panel');
            if (!panel) return;
            panel.classList.remove('active');
        });
    }
    if (fullToggle) {
        fullToggle.addEventListener('click', (event) => {
            event.preventDefault();
            const panel = document.getElementById('admin-full-details-panel');
            if (!panel) return;
            panel.classList.toggle('active');
        });
    }
    if (luaClear) {
        luaClear.addEventListener('click', (event) => {
            event.preventDefault();
            resetAtlasDetails('lua');
            document.querySelectorAll('#admin-lua-map [data-node].expanded').forEach(el => el.classList.remove('expanded'));
        });
    }
    if (luaCollapse) {
        luaCollapse.addEventListener('click', (event) => {
            event.preventDefault();
            const panel = document.getElementById('admin-lua-details-panel');
            if (!panel) return;
            panel.classList.remove('active');
        });
    }
    if (luaToggle) {
        luaToggle.addEventListener('click', (event) => {
            event.preventDefault();
            const panel = document.getElementById('admin-lua-details-panel');
            if (!panel) return;
            panel.classList.toggle('active');
        });
    }
}

function setAtlasFullscreen(bleedId, button, storageKey, enabled, onResize) {
    const bleed = document.getElementById(bleedId);
    if (!bleed) return;
    const isEnabled = Boolean(enabled);
    bleed.classList.toggle('atlas-fullscreen', isEnabled);
    document.body.classList.toggle('atlas-locked', isEnabled);
    if (button) {
        button.classList.toggle('active', isEnabled);
        button.textContent = isEnabled ? 'Exit Fullscreen' : 'Fullscreen';
    }
    if (storageKey) {
        localStorage.setItem(storageKey, isEnabled ? 'on' : 'off');
    }
    if (typeof onResize === 'function') {
        setTimeout(() => {
            onResize();
        }, 60);
    }
}

function bindAtlasFullscreenControls() {
    const fullButton = document.getElementById('admin-full-fullscreen');
    const luaButton = document.getElementById('admin-lua-fullscreen');
    const fullExit = document.getElementById('admin-full-exit');
    const luaExit = document.getElementById('admin-lua-exit');
    const fullBleed = document.getElementById('admin-full-bleed');
    const luaBleed = document.getElementById('admin-lua-bleed');

    const syncFull = () => {
        syncFullMapStageSize();
        scheduleDrawFlowLines();
        if (fullMapNav && typeof fullMapNav.fitToView === 'function') {
            fullMapNav.fitToView();
        }
    };
    const syncLua = () => {
        syncLuaMapStageSize();
        scheduleDrawFlowLines();
        if (luaMapNav && typeof luaMapNav.fitToView === 'function') {
            luaMapNav.fitToView();
        }
    };

    const disableOther = (target) => {
        if (target !== 'full') {
            setAtlasFullscreen('admin-full-bleed', fullButton, FULL_MAP_FULLSCREEN_KEY, false, syncFull);
        }
        if (target !== 'lua') {
            setAtlasFullscreen('admin-lua-bleed', luaButton, LUA_MAP_FULLSCREEN_KEY, false, syncLua);
        }
    };

    if (fullButton && fullBleed) {
        const initial = localStorage.getItem(FULL_MAP_FULLSCREEN_KEY) === 'on';
        if (initial) disableOther('full');
        setAtlasFullscreen('admin-full-bleed', fullButton, FULL_MAP_FULLSCREEN_KEY, initial, syncFull);
        fullButton.addEventListener('click', () => {
            const next = !fullBleed.classList.contains('atlas-fullscreen');
            if (next) disableOther('full');
            setAtlasFullscreen('admin-full-bleed', fullButton, FULL_MAP_FULLSCREEN_KEY, next, syncFull);
        });
    }

    if (fullExit && fullBleed) {
        fullExit.addEventListener('click', () => {
            setAtlasFullscreen('admin-full-bleed', fullButton, FULL_MAP_FULLSCREEN_KEY, false, syncFull);
        });
    }

    if (luaButton && luaBleed) {
        const initial = localStorage.getItem(LUA_MAP_FULLSCREEN_KEY) === 'on';
        if (initial) disableOther('lua');
        setAtlasFullscreen('admin-lua-bleed', luaButton, LUA_MAP_FULLSCREEN_KEY, initial, syncLua);
        luaButton.addEventListener('click', () => {
            const next = !luaBleed.classList.contains('atlas-fullscreen');
            if (next) disableOther('lua');
            setAtlasFullscreen('admin-lua-bleed', luaButton, LUA_MAP_FULLSCREEN_KEY, next, syncLua);
        });
    }

    if (luaExit && luaBleed) {
        luaExit.addEventListener('click', () => {
            setAtlasFullscreen('admin-lua-bleed', luaButton, LUA_MAP_FULLSCREEN_KEY, false, syncLua);
        });
    }

    window.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            disableOther('none');
        }
    });
}

function attachDetailsPanels() {
    const nodes = document.querySelectorAll('[data-node]');
    nodes.forEach((node) => {
        const id = node.dataset.node;
        let details = node.querySelector('.node-details');
        if (!details) {
            details = document.createElement('div');
            details.className = 'node-details';
            node.appendChild(details);
        }
        const meta = {
            tag: node.dataset.nodeTag || '',
            group: node.dataset.nodeGroup || ''
        };
        details.innerHTML = renderDetails(NODE_DETAILS[id], id, meta);
        if (!node.getAttribute('title')) {
            const fallbackTitle = getNodeTitle(id);
            node.setAttribute('title', fallbackTitle);
        }
        if (node.dataset.fullMap === 'true' && !details.querySelector('.node-controls')) {
            details.insertAdjacentHTML('beforeend', buildInlineNodeControls());
        }
        node.addEventListener('click', (event) => {
            if (event.target.closest('button')) return;
            const isExpanded = node.classList.contains('expanded');
            document.querySelectorAll('[data-node].expanded').forEach(el => el.classList.remove('expanded'));
            if (!isExpanded) {
                node.classList.add('expanded');
            }
            const panelKey = node.closest('#admin-lua-map') ? 'lua' : (node.closest('#admin-full-map') ? 'full' : null);
            if (panelKey) {
                setAtlasDetails(panelKey, renderDetails(NODE_DETAILS[id], id, meta));
            }
            scheduleDrawFlowLines();
        });
    });

    const metrics = document.querySelectorAll('[data-metric]');
    metrics.forEach((metric) => {
        const id = metric.dataset.metric;
        let details = metric.querySelector('.node-details');
        if (!details) {
            details = document.createElement('div');
            details.className = 'node-details';
            metric.appendChild(details);
        }
        details.innerHTML = renderDetails(METRIC_DETAILS[id], id, { disableFallback: true });
        metric.addEventListener('click', (event) => {
            if (event.target.closest('button')) return;
            const isExpanded = metric.classList.contains('expanded');
            document.querySelectorAll('[data-metric].expanded').forEach(el => el.classList.remove('expanded'));
            if (!isExpanded) {
                metric.classList.add('expanded');
            }
            scheduleDrawFlowLines();
        });
    });
}

function bindOverrideControls() {
    const overrides = ensureDefaultOverrides(loadOverrides());
    saveOverrides(overrides);
    applyStatuses(overrides);

    document.querySelectorAll('.node-toggle').forEach((toggle) => {
        toggle.addEventListener('click', (event) => {
            const container = event.currentTarget.closest('.reactor-node');
            if (!container) return;
            const controls = container.querySelector('.node-controls');
            if (controls) {
                controls.classList.toggle('hidden');
            }
        });
    });

    document.querySelectorAll('.node-controls button[data-set-status]').forEach((button) => {
        button.addEventListener('click', (event) => {
            const target = event.currentTarget;
            const container = target.closest('[data-node]');
            if (!container) return;
            const id = container.dataset.node;
            const status = target.dataset.setStatus;
            const nextMode = status === 'auto' ? 'auto' : 'manual';
            const updated = loadOverrides();
            setEntityStatus('node', id, nextMode, status, updated);
        });
    });

    document.querySelectorAll('[data-metric] .control-chip[data-set-status]').forEach((button) => {
        button.addEventListener('click', (event) => {
            const target = event.currentTarget;
            const container = target.closest('[data-metric]');
            if (!container) return;
            const id = container.dataset.metric;
            const status = target.dataset.setStatus;
            const nextMode = status === 'auto' ? 'auto' : 'manual';
            const updated = loadOverrides();
            setEntityStatus('metric', id, nextMode, status, updated);
        });
    });

    const resetBtn = document.getElementById('admin-reset-overrides');
    if (resetBtn) {
        resetBtn.addEventListener('click', () => {
            localStorage.removeItem(OVERRIDE_KEY);
            const fresh = ensureDefaultOverrides(loadOverrides());
            saveOverrides(fresh);
            applyStatuses(fresh);
        });
    }
}

function cycleChecklistState(element, stateStore) {
    const order = ['fixing', 'working', 'broken', 'blocked'];
    const current = element.dataset.state || 'fixing';
    const currentIndex = order.indexOf(current);
    const next = order[(currentIndex + 1) % order.length];
    element.dataset.state = next;
    stateStore[element.dataset.task] = next;
}

function bindChecklist() {
    const state = loadChecklistState();
    const items = document.querySelectorAll('[data-task]');
    items.forEach((item) => {
        const taskId = item.dataset.task;
        if (state[taskId]) {
            item.dataset.state = state[taskId];
        }
        item.addEventListener('click', () => {
            cycleChecklistState(item, state);
            saveChecklistState(state);
        });
    });
}

function updateWarnings(diag) {
    const container = document.getElementById('admin-warnings');
    if (!container) return;

    const warnings = [];
    if (diag?.issues?.length) warnings.push(...diag.issues.map(msg => ({ level: 'red', msg })));
    if (diag?.warnings?.length) warnings.push(...diag.warnings.map(msg => ({ level: 'blue', msg })));

    if (!warnings.length) {
        container.innerHTML = `
            <div class="flex items-start gap-3">
                <span class="status-light" data-status="green"></span>
                <div>Diagnostics clean. No critical warnings detected.</div>
            </div>
        `;
        return;
    }

    container.innerHTML = warnings.slice(0, 8).map((warn) => `
        <div class="flex items-start gap-3">
            <span class="status-light" data-status="${warn.level}"></span>
            <div>${escapeHtml(warn.msg)}</div>
        </div>
    `).join('');
}

function formatSeconds(value) {
    if (value === null || value === undefined) return '--';
    if (typeof value === 'string') {
        const trimmed = value.trim();
        if (!trimmed) return '--';
        if (trimmed.includes(':')) return trimmed;
        const num = Number(trimmed);
        if (!Number.isFinite(num)) return trimmed;
        value = num;
    }
    if (typeof value !== 'number' || !Number.isFinite(value)) return '--';
    const negative = value < 0 ? '-' : '';
    let seconds = Math.floor(Math.abs(value));
    const hours = Math.floor(seconds / 3600);
    seconds -= hours * 3600;
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    if (hours > 0) {
        return `${negative}${hours}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    }
    return `${negative}${minutes}:${String(secs).padStart(2, '0')}`;
}

function updateTimeMetrics(diag) {
    const rawDead = document.getElementById('admin-time-raw-dead');
    const aggDead = document.getElementById('admin-time-agg-dead');
    const rawDenied = document.getElementById('admin-time-raw-denied');
    const capHits = document.getElementById('admin-time-cap-hits');
    const capSeconds = document.getElementById('admin-time-cap-seconds');

    const rawDeadVal = diag?.time?.raw_dead_seconds ?? diag?.time?.raw_dead ?? '--';
    const aggDeadVal = diag?.time?.agg_dead_seconds ?? diag?.time?.agg_dead ?? '--';
    const rawDeniedVal = diag?.time?.raw_denied_seconds ?? diag?.time?.raw_denied ?? '--';
    const capHitsVal = diag?.time?.cap_hits ?? '--';
    const capSecondsVal = diag?.time?.cap_seconds ?? '--';

    if (rawDead) rawDead.textContent = formatSeconds(rawDeadVal);
    if (aggDead) aggDead.textContent = formatSeconds(aggDeadVal);
    if (rawDenied) rawDenied.textContent = formatSeconds(rawDeniedVal);
    if (capHits) capHits.textContent = capHitsVal;
    if (capSeconds) capSeconds.textContent = formatSeconds(capSecondsVal);
}

function updateRefreshLabel() {
    const label = document.getElementById('admin-last-refresh');
    if (!label) return;
    const now = new Date();
    label.textContent = now.toLocaleTimeString();
}

function isAdminViewActive() {
    const view = document.getElementById('view-admin');
    if (!view) return false;
    return view.classList.contains('active') && !view.classList.contains('hidden');
}

function stopAutoRefreshTimer() {
    if (autoRefreshTimer) {
        clearInterval(autoRefreshTimer);
        autoRefreshTimer = null;
    }
}

function syncAdminRefreshLifecycle(refreshNow = false) {
    const shouldRun = autoRefreshEnabled && !document.hidden && isAdminViewActive();
    if (!shouldRun) {
        stopAutoRefreshTimer();
        return;
    }
    if (refreshNow) {
        void refreshAutoStatus();
    }
    if (!autoRefreshTimer) {
        autoRefreshTimer = setInterval(refreshAutoStatus, REFRESH_MS);
    }
}

function setAutoStatus(id, status) {
    const elements = getCachedStatusElements('node', id);
    elements.forEach((element) => {
        if (element.dataset.autoStatus !== status) {
            element.dataset.autoStatus = status;
        }
    });
}

async function refreshAutoStatus() {
    if (!isAdminViewActive() || document.hidden) {
        stopAutoRefreshTimer();
        return;
    }

    try {
        const diag = await fetchJSON(`${API_BASE}/diagnostics`);
        if (diag?.database?.status === 'connected') {
            setAutoStatus('postgres', 'green');
            setAutoStatus('db_adapter', 'green');
            setAutoStatus('core_postgres', 'green');
        } else if (diag?.database?.status === 'error') {
            setAutoStatus('postgres', 'red');
            setAutoStatus('db_adapter', 'red');
            setAutoStatus('core_postgres', 'red');
        }

        const tables = Array.isArray(diag?.tables) ? diag.tables : [];
        const tableStatus = (name) => {
            const table = tables.find(t => t.name === name);
            if (!table) return 'blue';
            if (table.status === 'ok') return 'green';
            if (table.status === 'not_found') return 'red';
            if (table.status === 'permission_denied') return 'blue';
            return 'red';
        };
        setAutoStatus('table_rounds', tableStatus('rounds'));
        setAutoStatus('table_player_stats', tableStatus('player_comprehensive_stats'));
        setAutoStatus('table_weapon_stats', tableStatus('weapon_comprehensive_stats'));
        setAutoStatus('table_lua_round_teams', tableStatus('lua_round_teams'));

        updateWarnings(diag);
        updateTimeMetrics(diag);
    } catch (err) {
        console.warn('Diagnostics fetch failed:', err);
    }

    try {
        const status = await fetchJSON(`${API_BASE}/status`);
        if (status?.status === 'online') {
            setAutoStatus('website_api', 'green');
            setAutoStatus('core_bot_web', 'green');
        } else {
            setAutoStatus('website_api', 'red');
            setAutoStatus('core_bot_web', 'red');
        }
    } catch (err) {
        setAutoStatus('website_api', 'red');
        setAutoStatus('core_bot_web', 'red');
    }

    try {
        const live = await fetchJSON(`${API_BASE}/live-status`);
        if (live?.game_server?.online) {
            setAutoStatus('et_server', 'green');
            setAutoStatus('core_game_server', 'green');
        } else {
            setAutoStatus('et_server', 'red');
            setAutoStatus('core_game_server', 'red');
        }
    } catch (err) {
        setAutoStatus('et_server', 'red');
        setAutoStatus('core_game_server', 'red');
    }

    const overrides = ensureDefaultOverrides(loadOverrides());
    applyStatuses(overrides);
    updateRefreshLabel();
}

function bindRefreshControls() {
    const toggle = document.getElementById('admin-toggle-refresh');
    const manual = document.getElementById('admin-refresh-now');

    if (toggle) {
        toggle.textContent = autoRefreshEnabled ? 'On' : 'Off';
        toggle.classList.toggle('active', autoRefreshEnabled);
        toggle.addEventListener('click', () => {
            autoRefreshEnabled = !autoRefreshEnabled;
            toggle.textContent = autoRefreshEnabled ? 'On' : 'Off';
            toggle.classList.toggle('active', autoRefreshEnabled);
            syncAdminRefreshLifecycle(true);
        });
    }

    if (manual) {
        manual.addEventListener('click', () => {
            refreshAutoStatus();
        });
    }
}

function bindRefreshLifecycle() {
    if (refreshLifecycleBound) return;

    document.addEventListener('visibilitychange', () => {
        syncAdminRefreshLifecycle(document.visibilityState === 'visible');
    });
    window.addEventListener('hashchange', () => {
        syncAdminRefreshLifecycle(false);
    });

    const adminView = document.getElementById('view-admin');
    if (adminView && typeof MutationObserver !== 'undefined') {
        const observer = new MutationObserver(() => {
            syncAdminRefreshLifecycle(false);
        });
        observer.observe(adminView, { attributes: true, attributeFilter: ['class'] });
    }

    refreshLifecycleBound = true;
}

export function loadAdminPanelView() {
    if (!adminInitialized) {
        renderFullMap();
        renderLuaMap();
        renderDevTimeline();
        renderLuaAtlas();
        renderAtlasControls(loadFullMapView());
        renderFullStorySteps();
        applyAtlasFilters();
        attachDetailsPanels();
        bindAtlasDetailsControls();
        bindOverrideControls();
        bindChecklist();
        bindRefreshControls();
        bindRefreshLifecycle();
        bindStoryModeControls();
        bindAtlasGroupControls();
        bindFullLinesToggle();
        bindFullMapFocus();
        bindLuaLinesToggle();
        bindLuaMapFocus();
        bindWalkthroughControls();
        bindFlowTooltips();
        bindFlowMapFocus();
        initFullMapNavigator();
        initLuaMapNavigator();
        bindAtlasFullscreenControls();
        initFlowLines();
        adminInitialized = true;
    }

    refreshAutoStatus();
    syncAdminRefreshLifecycle(false);

    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }

    scheduleDrawFlowLines();
    setTimeout(scheduleDrawFlowLines, 250);
}
