/**
 * Sessions 2.0 — Detail Page
 * 4-tab drill-down: Summary, Player Stats, Teamplay, Charts
 * @module session-detail
 */
import { API_BASE, fetchJSON, escapeHtml, escapeJsString } from './utils.js';
import {
    renderMatchSummary,
    renderCombatRadar,
    renderTopFraggers,
    renderDamageBreakdown,
    renderSupportPerformance,
    renderTimeDistribution,
    _rvCharts,
} from './retro-viz.js?v=20260312-site-recovery3';

// ---- Constants (copied from sessions.js) ----
const MAP_IMAGE_MAP = {
    "battery": "assets/maps/levelshots/battery.png",
    "fueldump": "assets/maps/levelshots/fueldump.png",
    "goldrush": "assets/maps/levelshots/goldrush.png",
    "oasis": "assets/maps/levelshots/oasis.png",
    "radar": "assets/maps/levelshots/radar.png",
    "railgun": "assets/maps/levelshots/railgun.png",
    "supply": "assets/maps/levelshots/supply.png",
    "etl_supply": "assets/maps/levelshots/supply.png",
    "adlernest": "assets/maps/levelshots/adlernest.png",
    "etl_adlernest": "assets/maps/levelshots/etl_adlernest.png",
    "etl_adlernest_a3": "assets/maps/levelshots/etl_adlernest.png",
    "etl_sp_delivery": "assets/maps/levelshots/etl_sp_delivery.png",
    "sp_delivery_te": "assets/maps/levelshots/etl_sp_delivery.png",
    "etl_delivery": "assets/maps/levelshots/etl_sp_delivery.png",
    "etl_battery": "assets/maps/levelshots/sw_battery.png",
    "sw_battery": "assets/maps/levelshots/sw_battery.png",
    "etl_oasis": "assets/maps/levelshots/sw_oasis_b3.png",
    "sw_oasis_b3": "assets/maps/levelshots/sw_oasis_b3.png",
    "etl_frostbite": "assets/maps/levelshots/frostbite.png",
    "frostbite": "assets/maps/levelshots/frostbite.png",
    "etl_goldrush": "assets/maps/levelshots/sw_goldrush_te.png",
    "sw_goldrush_te": "assets/maps/levelshots/sw_goldrush_te.png",
    "etl_brewdog": "assets/maps/levelshots/et_brewdog.png",
    "et_brewdog": "assets/maps/levelshots/et_brewdog.png",
    "etl_erdenberg": "assets/maps/levelshots/erdenberg_t2.png",
    "erdenberg_t2": "assets/maps/levelshots/erdenberg_t2.png",
    "etl_bradendorf": "assets/maps/levelshots/etl_braundorf.png",
    "etl_braundorf": "assets/maps/levelshots/etl_braundorf.png",
    "braundorf_b4": "assets/maps/levelshots/braundorf_b4.png",
    "etl_escape2": "assets/maps/levelshots/te_escape2.png",
    "te_escape2": "assets/maps/levelshots/te_escape2.png",
    "etl_beach": "assets/maps/levelshots/etl_beach.png",
    "et_beach": "assets/maps/levelshots/etl_beach.png",
    "etl_base": "assets/maps/levelshots/etl_base.png",
    "etl_ice": "assets/maps/levelshots/etl_ice.png",
    "bremen_b3": "assets/maps/levelshots/bremen_b3.png",
    "decay_sw": "assets/maps/levelshots/decay_sw.png",
    "missile_b3": "assets/maps/levelshots/missile_b3.png",
    "missile_b4": "assets/maps/levelshots/missile_b4.png",
};
const AXIS_ICON = "assets/icons/axis.svg";
const ALLIES_ICON = "assets/icons/allies.svg";
const PLAYER_GRAPH_COLORS = [
    '#38bdf8', '#a78bfa', '#22c55e', '#f59e0b', '#f43f5e',
    '#14b8a6', '#fb7185', '#84cc16', '#60a5fa', '#f97316',
    '#c084fc', '#2dd4bf',
];

// ---- Utility functions (copied from sessions.js) ----

function mapLabel(mapName) {
    return (mapName || 'Unknown').toString()
        .replace(/^maps[\\/]/, '')
        .replace(/\.(bsp|pk3|arena)$/i, '')
        .replace(/_/g, ' ');
}

function normalizeMapKey(mapName) {
    const raw = (mapName || '').toString().trim().toLowerCase();
    if (!raw) return '';
    return raw.replace(/^maps[\\/]/, '').replace(/\.(bsp|pk3|arena)$/i, '')
        .replace(/[^a-z0-9]+/g, '_').replace(/_+/g, '_').replace(/^_+|_+$/g, '');
}

function mapImageFor(mapName) {
    const key = normalizeMapKey(mapName);
    if (MAP_IMAGE_MAP[key]) return MAP_IMAGE_MAP[key];
    const trimmed = key.replace(/^etl_/, '').replace(/^sw_/, '').replace(/^et_/, '');
    for (const c of [trimmed, `etl_${trimmed}`, `sw_${trimmed}`, `et_${trimmed}`, key]) {
        if (MAP_IMAGE_MAP[c]) return MAP_IMAGE_MAP[c];
    }
    const kc = key.replace(/_/g, '');
    for (const [mk, mp] of Object.entries(MAP_IMAGE_MAP)) {
        if (mk === 'map_generic') continue;
        const mc = mk.replace(/_/g, '');
        if (key.includes(mk) || mk.includes(key) || kc.includes(mc) || mc.includes(kc)) return mp;
    }
    return "assets/maps/map_generic.svg";
}



function formatDuration(seconds) {
    const total = Number(seconds || 0);
    if (!total || total < 0) return "0:00";
    const mins = Math.floor(total / 60);
    const secs = Math.floor(total % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function coerceRoundId(roundId) {
    const parsed = Number.parseInt(String(roundId), 10);
    if (!Number.isFinite(parsed) || parsed <= 0) return null;
    return parsed;
}

function num(value, fallback = 0) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
}

function _collectSessionRounds() {
    const rounds = [];
    (_detailData?.matches || []).forEach((mapMatch, mapIndex) => {
        const mapName = mapMatch.map_name || mapMatch.map || 'Unknown';
        (mapMatch.rounds || []).forEach((round, roundIndex) => {
            const roundId = coerceRoundId(round.round_id || round.id);
            if (!roundId) return;
            rounds.push({
                mapIndex,
                roundIndex,
                roundId,
                mapName,
                roundNumber: num(round.round_number, roundIndex + 1),
                winnerTeam: num(round.winner_team),
                alliesScore: round.allies_score,
                axisScore: round.axis_score,
                durationSeconds: round.duration_seconds,
                roundStartUnix: num(round.round_start_unix),
                sessionDate: round.round_date || _sessionDate,
            });
        });
    });
    return rounds;
}

function _findRoundMeta(roundId) {
    const rid = coerceRoundId(roundId);
    if (!rid) return null;
    return _collectSessionRounds().find(round => round.roundId === rid) || null;
}

function _roundScopeLabel() {
    if (!_activeRoundId) return 'Full session';
    const meta = _findRoundMeta(_activeRoundId);
    if (!meta) return `Round ${_activeRoundId}`;
    const mapName = mapLabel(meta.mapName || 'Unknown');
    return `${mapName} / R${meta.roundNumber}`;
}

function _normalizePlayerRow(row = {}, source = 'session') {
    const kills = num(row.kills);
    const deaths = num(row.deaths);
    const damageGiven = num(row.damage_given);
    const damageReceived = num(row.damage_received);
    const killAssists = num(row.kill_assists);
    const timePlayed = num(row.time_played_seconds || row.time_played);
    const guid = row.player_guid || row.guid || null;
    const name = (row.player_name || row.name || 'Unknown').toString();
    const denominator = deaths > 0 ? deaths : 1;
    const kd = num(row.kd, kills / denominator);
    let dpm = num(row.dpm, Number.NaN);
    if (!Number.isFinite(dpm) || dpm < 0) {
        dpm = timePlayed > 0 ? (damageGiven / (timePlayed / 60)) : 0;
    }

    const deadMinutesRaw = row.time_dead_minutes != null
        ? row.time_dead_minutes
        : (row.time_dead != null ? (num(row.time_dead) / 60) : null);
    const deadMinutes = deadMinutesRaw != null ? num(deadMinutesRaw, Number.NaN) : Number.NaN;
    const deniedSecondsRaw = row.denied_playtime ?? row.time_denied_seconds ?? row.time_denied;
    const deniedSeconds = deniedSecondsRaw != null ? num(deniedSecondsRaw, Number.NaN) : Number.NaN;
    const alivePctRaw = row.alive_pct ?? row.alive_pct_computed ?? row.tmp_pct_computed ?? row.tmp_pct;
    const alivePctLuaRaw = row.alive_pct_lua ?? row.tmp_pct_lua;
    const alivePctDiffRaw = row.alive_pct_diff ?? row.tmp_pct_diff;
    const alivePctDriftRaw = row.alive_pct_drift ?? row.tmp_pct_drift;
    const playedPctRaw = row.played_pct;
    const playedPctLuaRaw = row.played_pct_lua ?? row.time_played_percent_lua;
    const playedPctDiffRaw = row.played_pct_diff;
    const playedPctDriftRaw = row.played_pct_drift;
    const supastatsTmpPctRaw = row.supastats_tmp_pct;
    const supastatsTmpRatioRaw = row.supastats_tmp_ratio;

    return {
        source,
        player_guid: guid,
        player_name: name,
        kills,
        deaths,
        kd,
        dpm,
        damage_given: damageGiven,
        damage_received: damageReceived,
        kill_assists: killAssists,
        efficiency: num(row.efficiency),
        headshot_pct: num(row.headshot_pct),
        accuracy: num(row.accuracy),
        gibs: num(row.gibs),
        self_kills: num(row.self_kills ?? row.selfkills),
        revives_given: num(row.revives_given),
        times_revived: num(row.times_revived),
        alive_pct: Number.isFinite(num(alivePctRaw, Number.NaN)) ? num(alivePctRaw) : null,
        alive_pct_lua: Number.isFinite(num(alivePctLuaRaw, Number.NaN)) ? num(alivePctLuaRaw) : null,
        alive_pct_diff: Number.isFinite(num(alivePctDiffRaw, Number.NaN)) ? num(alivePctDiffRaw) : null,
        alive_pct_drift: Boolean(alivePctDriftRaw),
        played_pct: Number.isFinite(num(playedPctRaw, Number.NaN)) ? num(playedPctRaw) : null,
        played_pct_lua: Number.isFinite(num(playedPctLuaRaw, Number.NaN)) ? num(playedPctLuaRaw) : null,
        played_pct_diff: Number.isFinite(num(playedPctDiffRaw, Number.NaN)) ? num(playedPctDiffRaw) : null,
        played_pct_drift: Boolean(playedPctDriftRaw),
        supastats_tmp_pct: Number.isFinite(num(supastatsTmpPctRaw, Number.NaN)) ? num(supastatsTmpPctRaw) : null,
        supastats_tmp_ratio: Number.isFinite(num(supastatsTmpRatioRaw, Number.NaN)) ? num(supastatsTmpRatioRaw) : null,
        tmp_pct_computed: Number.isFinite(num(alivePctRaw, Number.NaN)) ? num(alivePctRaw) : null,
        tmp_pct_lua: Number.isFinite(num(alivePctLuaRaw, Number.NaN)) ? num(alivePctLuaRaw) : null,
        tmp_pct_diff: Number.isFinite(num(alivePctDiffRaw, Number.NaN)) ? num(alivePctDiffRaw) : null,
        tmp_pct_drift: Boolean(alivePctDriftRaw),
        time_dead_minutes: Number.isFinite(deadMinutes) ? deadMinutes : null,
        denied_playtime: Number.isFinite(deniedSeconds) ? deniedSeconds : null,
        time_played_seconds: timePlayed,
    };
}

function _playerSort(a, b) {
    return (
        num(b.dpm) - num(a.dpm)
        || num(b.kills) - num(a.kills)
        || num(a.deaths) - num(b.deaths)
        || String(a.player_name || '').localeCompare(String(b.player_name || ''))
    );
}

function _tradeScopeParams() {
    const date = _activeRoundSessionDate || _sessionDate;
    const params = new URLSearchParams();
    if (date) params.set('session_date', date);
    if (_activeRoundId) {
        if (_activeRoundStartUnix) {
            params.set('round_start_unix', String(_activeRoundStartUnix));
        } else if (_activeRoundMapName && _activeRoundNumber) {
            // Fallback when round_start_unix is missing/0
            params.set('map_name', _activeRoundMapName);
            params.set('round_number', String(_activeRoundNumber));
        }
    }
    return params.toString();
}

// ---- Module state (reset on each page load) ----
let _sessionId = null;
let _sessionDate = null;
let _detailData = null;
let _graphData = null;
let _activeTab = 'summary';
let _activeRoundId = null;
let _activeRoundStartUnix = null;
let _activeRoundSessionDate = null;
let _activeRoundMapName = null;
let _activeRoundNumber = null;
let _signalsLoaded = null;
let _vizLoaded = null;
let _overviewMapIndex = null;
let _overviewRoundId = null;
let _expandedMapIndex = null;
let _overviewRenderToken = 0;
const _overviewRoundStatsCache = new Map();
const _overviewMapStatsCache = new Map();
const _CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes
let _playersRenderToken = 0;
let _playersScopeLoaded = null;
let _playerPanels = {};
const _roundPlayersCache = new Map();
const _playerWeaponCache = new Map();
const _playerTradeScopeCache = new Map();
const _playerPanelCharts = new Map();
let _signalsRequestToken = 0;
let _vizRequestToken = 0;
let _sdCharts = [];
let _playersSummaryCharts = [];
let _sessionGraphDataPromise = null;

// ============================================================
// ENTRY POINT
// ============================================================

export async function loadSessionDetailView({ sessionId, sessionDate } = {}) {
    _sessionId = sessionId ? parseInt(sessionId, 10) : null;
    _sessionDate = sessionDate || null;
    _detailData = null;
    _graphData = null;
    _activeTab = 'summary';
    _activeRoundId = null;
    _activeRoundStartUnix = null;
    _activeRoundSessionDate = null;
    _signalsLoaded = null;
    _vizLoaded = null;
    _overviewMapIndex = null;
    _overviewRoundId = null;
    _expandedMapIndex = null;
    _overviewRenderToken = 0;
    _playersRenderToken = 0;
    _playersScopeLoaded = null;
    _signalsRequestToken = 0;
    _vizRequestToken = 0;
    _overviewRoundStatsCache.clear();
    _overviewMapStatsCache.clear();
    _roundPlayersCache.clear();
    _playerWeaponCache.clear();
    _playerTradeScopeCache.clear();
    _playerPanels = {};
    _sessionGraphDataPromise = null;
    _destroyAllCharts();

    const container = document.getElementById('session-detail-container');
    if (!container) return;

    container.innerHTML = `
        <div class="text-center py-12">
            <i data-lucide="loader" class="w-8 h-8 text-brand-blue animate-spin mx-auto mb-4"></i>
            <div class="text-slate-400">Loading session...</div>
        </div>`;
    if (typeof lucide !== 'undefined') lucide.createIcons();

    try {
        if (_sessionId) {
            try {
                _detailData = await fetchJSON(`${API_BASE}/stats/session/${_sessionId}/detail`);
                _sessionDate = _detailData.session_date || _detailData.date || _sessionDate;
            } catch (err) {
                console.warn('Detail endpoint failed, falling back:', err);
            }
        }
        if (!_detailData && _sessionDate) {
            // Date path: resolve session ID first, then load detail
            const dateResp = await fetchJSON(`${API_BASE}/sessions/${_sessionDate}`);
            const resolvedId = dateResp.gaming_session_id || dateResp.session_id
                || (dateResp.sessions && dateResp.sessions[0] && dateResp.sessions[0].gaming_session_id);
            if (resolvedId) {
                _sessionId = parseInt(resolvedId, 10);
                try {
                    _detailData = await fetchJSON(`${API_BASE}/stats/session/${_sessionId}/detail`);
                } catch (_) { /* fall through */ }
            }
            if (!_detailData) {
                _detailData = dateResp;
            }
            _sessionDate = _detailData.date || _sessionDate;
        }
        if (!_detailData) {
            container.innerHTML = '<div class="text-center text-red-500 py-12">Session not found</div>';
            return;
        }

        _renderShell(container);
        _activateTab('summary');
    } catch (e) {
        console.error('Failed to load session detail:', e);
        container.innerHTML = '<div class="text-center text-red-500 py-12">Failed to load session</div>';
    }
}

// ============================================================
// SHELL
// ============================================================

function _renderSessionHeaderMapStrip(scoring = {}) {
    const matches = _getOverviewMatches();
    const scoringMaps = Array.isArray(scoring.maps) ? scoring.maps : [];
    if (!matches.length) {
        return '<div class="text-xs text-slate-500">No maps available</div>';
    }

    return matches.map((mapMatch, idx) => {
        const mapNameRaw = mapMatch.map_name || mapMatch.map || 'Unknown';
        const mapName = escapeHtml(mapLabel(mapNameRaw));
        const image = mapImageFor(mapNameRaw);
        const mapRounds = Array.isArray(mapMatch.rounds) ? mapMatch.rounds : [];
        const isExpanded = _expandedMapIndex === idx;
        return `
            <button onclick="sdSelectHeaderMap(${idx})"
                class="group relative min-w-[160px] h-20 rounded-xl overflow-hidden border ${isExpanded ? 'border-brand-blue/60 ring-1 ring-brand-blue/30' : 'border-white/10 hover:border-brand-blue/40'} transition text-left shrink-0">
                <div class="absolute inset-0 ${image.includes('map_generic') ? 'bg-slate-900' : ''}"
                    ${image.includes('map_generic') ? '' : `style="background-image:url('${image}');background-size:cover;background-position:center"`}></div>
                <div class="absolute inset-0 bg-gradient-to-b from-black/20 via-black/40 to-black/80"></div>
                <div class="relative h-full p-2.5 flex flex-col justify-between">
                    <div class="text-[10px] uppercase tracking-wider text-slate-300">${mapRounds.length}R</div>
                    <div class="text-sm font-black text-white truncate">${mapName}</div>
                </div>
            </button>`;
    }).join('');
}

function _renderMapRoundTimeline() {
    if (_expandedMapIndex === null) return '';
    const matches = _getOverviewMatches();
    const mapMatch = matches[_expandedMapIndex];
    if (!mapMatch) return '';
    const mapNameRaw = mapMatch.map_name || mapMatch.map || 'Unknown';
    const mapName = escapeHtml(mapLabel(mapNameRaw));
    const rounds = Array.isArray(mapMatch.rounds) ? mapMatch.rounds : [];
    if (!rounds.length) return `<div class="text-xs text-slate-500">No rounds for ${mapName}</div>`;

    const isFullMap = _expandedMapIndex !== null && !_activeRoundId;
    const roundBtns = rounds.map(round => {
        const rid = coerceRoundId(round.round_id || round.id);
        if (!rid) return '';
        const roundNum = round.round_number || 1;
        const isActive = _activeRoundId === rid;
        const winnerTeam = num(round.winner_team);
        const winnerLabel = winnerTeam === 1 ? 'Axis' : winnerTeam === 2 ? 'Allies' : 'Draw';
        const winnerClass = winnerTeam === 1 ? 'text-brand-rose' : winnerTeam === 2 ? 'text-brand-blue' : 'text-slate-400';
        const durationLabel = round.duration_seconds ? formatDuration(round.duration_seconds) : '';
        const roundDate = round.round_date || _sessionDate || '';
        const roundStartUnix = num(round.round_start_unix);
        return `
            <button onclick="sdSelectHeaderRound(${_expandedMapIndex}, ${rid}, ${roundStartUnix}, '${escapeJsString(roundDate)}')"
                class="px-3 py-2 rounded-lg border text-left transition whitespace-nowrap ${isActive ? 'bg-brand-blue/20 border-brand-blue/50 text-white' : 'bg-black/25 border-white/10 text-slate-300 hover:bg-black/40'}">
                <div class="text-[11px] font-black">R${roundNum} <span class="${winnerClass}">${escapeHtml(winnerLabel)}</span></div>
                ${durationLabel ? `<div class="text-[10px] text-slate-500">${escapeHtml(durationLabel)}</div>` : ''}
            </button>`;
    }).join('');

    const fullMapBtn = `
        <button onclick="sdClearRoundKeepMap()"
            class="px-3 py-2 rounded-lg border text-left transition whitespace-nowrap ${isFullMap ? 'bg-brand-emerald/20 border-brand-emerald/50 text-white' : 'bg-black/25 border-white/10 text-slate-300 hover:bg-black/40'}">
            <div class="text-[11px] font-black">Full Map</div>
        </button>`;

    return `
        <div class="flex items-center gap-2 mt-3 p-3 rounded-xl bg-black/20 border border-white/5">
            <span class="text-xs text-slate-400 font-bold mr-1">${mapName}:</span>
            ${roundBtns}
            ${fullMapBtn}
            <button onclick="sdClearHeaderMapScope()" class="ml-auto text-xs px-2 py-1 rounded-lg bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white transition">
                ✕
            </button>
        </div>`;
}

function _renderShell(container) {
    const scoring = _detailData.scoring || {};
    const hasScoring = scoring.available === true;
    const teamAName = hasScoring ? (scoring.team_a_name || 'Allies') : 'Allies';
    const teamBName = hasScoring ? (scoring.team_b_name || 'Axis') : 'Axis';
    const teamAScore = hasScoring ? (scoring.team_a_score || 0) : 0;
    const teamBScore = hasScoring ? (scoring.team_b_score || 0) : 0;
    const aWinning = teamAScore > teamBScore;
    const bWinning = teamBScore > teamAScore;

    container.innerHTML = `
        <div class="mb-6">
            <button onclick="navigateTo('sessions2')"
                class="flex items-center gap-2 text-sm text-slate-400 hover:text-white transition">
                <i data-lucide="arrow-left" class="w-4 h-4"></i>
                Back to Sessions
            </button>
        </div>

        <div class="glass-panel rounded-xl p-6 mb-6 overflow-hidden">
            <div class="flex flex-wrap items-start justify-between gap-4">
                <div>
                    <h1 class="text-2xl font-black text-white">
                        Session ${escapeHtml(String(_sessionId || _sessionDate || ''))}
                    </h1>
                    <div class="text-slate-400 text-sm mt-1">
                        ${escapeHtml(_detailData.date || _sessionDate || '')}
                    </div>
                    <div class="text-xs text-slate-500 mt-1">
                        Click map or round chips to scope stats quickly
                    </div>
                </div>
                ${hasScoring ? `
                <div class="flex items-center gap-5">
                    <span class="text-sm font-bold ${aWinning ? 'text-white' : 'text-slate-400'}">${escapeHtml(teamAName)}</span>
                    <div class="flex items-center gap-3">
                        <span class="text-4xl font-black ${aWinning ? 'text-brand-emerald' : 'text-slate-400'}">${teamAScore}</span>
                        <span class="text-lg text-slate-600">:</span>
                        <span class="text-4xl font-black ${bWinning ? 'text-brand-emerald' : 'text-slate-400'}">${teamBScore}</span>
                    </div>
                    <span class="text-sm font-bold ${bWinning ? 'text-white' : 'text-slate-400'}">${escapeHtml(teamBName)}</span>
                </div>` : ''}
            </div>

            <div class="mt-5">
                <div class="flex items-center gap-3 mb-2">
                    <div class="text-[11px] uppercase tracking-wider text-slate-500 font-bold">Maps</div>
                    <span id="sd-hero-scope-pill" class="text-xs px-2 py-1 rounded bg-brand-blue/20 border border-brand-blue/30 text-brand-blue">
                        ${escapeHtml(_getScopePillLabel())}
                    </span>
                    <button id="sd-hero-clear-btn" onclick="sdClearHeaderMapScope()"
                        class="ml-auto text-xs px-3 py-1 rounded-lg bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white transition ${_expandedMapIndex !== null ? '' : 'hidden'}">
                        Clear scope
                    </button>
                </div>
                <div id="sd-map-strip" class="flex gap-3 overflow-x-auto pb-2 pr-1">
                    ${_renderSessionHeaderMapStrip(scoring)}
                </div>
                <div id="sd-map-round-timeline">
                    ${_renderMapRoundTimeline()}
                </div>
            </div>
        </div>

        <div class="flex gap-1 mb-6 p-1 bg-slate-900/60 rounded-xl flex-wrap" id="sd-tab-nav">
            ${['summary', 'players', 'teamplay', 'charts'].map(tab => `
                <button id="sd-tab-btn-${tab}"
                    onclick="sdSwitchTab('${tab}')"
                    class="sd-tab-btn flex-1 py-2 px-4 rounded-lg text-sm font-bold transition
                           text-slate-400 hover:text-white hover:bg-white/5">
                    ${_tabLabel(tab)}
                </button>`).join('')}
        </div>

        <div id="sd-tab-summary"  class="sd-tab-panel"></div>
        <div id="sd-tab-players"  class="sd-tab-panel hidden"></div>
        <div id="sd-tab-teamplay" class="sd-tab-panel hidden"></div>
        <div id="sd-tab-charts"   class="sd-tab-panel hidden"></div>
    `;
    if (typeof lucide !== 'undefined') lucide.createIcons();
}

function _tabLabel(tab) {
    return { summary: 'Summary', players: 'Player Stats', teamplay: 'Teamplay', charts: 'Charts' }[tab] || tab;
}

function _getScopePillLabel() {
    if (_expandedMapIndex !== null) {
        const matches = _getOverviewMatches();
        const mapMatch = matches[_expandedMapIndex];
        const mapName = mapMatch ? mapLabel(mapMatch.map_name || mapMatch.map || 'Unknown') : 'Unknown';
        if (_activeRoundId) {
            const meta = _findRoundMeta(_activeRoundId);
            return `${mapName} / R${meta?.roundNumber || '?'}`;
        }
        return `Viewing ${mapName}`;
    }
    return 'Full Session';
}

// ============================================================
// TAB SWITCHER
// ============================================================

export function sdSwitchTab(tab) {
    _activeTab = tab;
    document.querySelectorAll('.sd-tab-panel').forEach(el => el.classList.add('hidden'));
    const panel = document.getElementById(`sd-tab-${tab}`);
    if (panel) panel.classList.remove('hidden');

    document.querySelectorAll('.sd-tab-btn').forEach(btn => {
        btn.classList.remove('bg-brand-blue', 'text-white');
        btn.classList.add('text-slate-400');
    });
    const activeBtn = document.getElementById(`sd-tab-btn-${tab}`);
    if (activeBtn) {
        activeBtn.classList.add('bg-brand-blue', 'text-white');
        activeBtn.classList.remove('text-slate-400');
    }

    if (tab === 'summary') _renderSummaryTab();
    else if (tab === 'players') _renderPlayersTab();
    else if (tab === 'teamplay') _loadSignalsTab();
    else if (tab === 'charts') _loadVizTab();
}

function _activateTab(tab) { sdSwitchTab(tab); }

// ============================================================
// OVERVIEW TAB
// ============================================================

function _getOverviewMatches() {
    return Array.isArray(_detailData?.matches) ? _detailData.matches : [];
}

function _isOverviewScoped() {
    return _overviewMapIndex !== null;
}

function _getOverviewScopeLabel() {
    if (!_isOverviewScoped()) return 'All maps combined';
    const matches = _getOverviewMatches();
    const mapMatch = matches[_overviewMapIndex];
    if (!mapMatch) return 'All maps combined';
    const mapName = mapLabel(mapMatch.map_name || mapMatch.map || 'Unknown');
    if (_overviewRoundId) {
        const roundMeta = (mapMatch.rounds || []).find(r => coerceRoundId(r.round_id || r.id) === _overviewRoundId);
        const roundLabel = roundMeta?.round_number ? `R${roundMeta.round_number}` : `Round ${_overviewRoundId}`;
        return `${mapName} / ${roundLabel}`;
    }
    return `${mapName} / All rounds`;
}

function _normalizeScopedPlayerRow(row = {}) {
    const name = (row.player_name || row.name || 'Unknown').toString();
    const kills = num(row.kills);
    const deaths = num(row.deaths);
    const damageGiven = num(row.damage_given);
    const damageReceived = num(row.damage_received);
    const timePlayed = num(row.time_played || row.time_played_seconds);
    let dpm = num(row.dpm, Number.NaN);
    if (!Number.isFinite(dpm) || dpm < 0) dpm = 0;
    if (dpm === 0 && damageGiven > 0 && timePlayed > 0) {
        dpm = damageGiven / (timePlayed / 60);
    }
    return {
        player_name: name,
        kills,
        deaths,
        kd: num(row.kd, kills / (deaths || 1)),
        dpm,
        damage_given: damageGiven,
        damage_received: damageReceived,
        gibs: num(row.gibs),
        self_kills: num(row.self_kills),
        revives_given: num(row.revives_given),
        times_revived: num(row.times_revived),
        time_played: timePlayed,
    };
}

function _sortScopedPlayers(players = []) {
    return players.slice().sort((a, b) => (
        num(b.dpm) - num(a.dpm)
        || num(b.kills) - num(a.kills)
        || num(a.deaths) - num(b.deaths)
    ));
}

function _getOverviewSessionPlayers() {
    let players = Array.isArray(_detailData?.players) ? _detailData.players : [];
    if (!players.length && Array.isArray(_detailData?.teams)) {
        players = _detailData.teams.flatMap(team => (
            (team.players || []).map(p => ({ player_name: p.name, ...p }))
        ));
    }
    return _sortScopedPlayers(players.map(_normalizeScopedPlayerRow));
}

function _getOverviewRoundIdsForMap(mapIndex) {
    const mapMatch = _getOverviewMatches()[mapIndex];
    if (!mapMatch) return [];
    return (mapMatch.rounds || [])
        .map(r => coerceRoundId(r.round_id || r.id))
        .filter(Boolean);
}

async function _fetchOverviewRoundPlayers(roundId) {
    const rid = coerceRoundId(roundId);
    if (!rid) return [];
    if (_overviewRoundStatsCache.has(rid)) return _overviewRoundStatsCache.get(rid);

    const payload = await fetchJSON(`${API_BASE}/stats/matches/${encodeURIComponent(rid)}`);
    const team1Players = Array.isArray(payload?.team1?.players) ? payload.team1.players : [];
    const team2Players = Array.isArray(payload?.team2?.players) ? payload.team2.players : [];
    const normalized = [...team1Players, ...team2Players].map(_normalizeScopedPlayerRow);
    const sorted = _sortScopedPlayers(normalized);
    _overviewRoundStatsCache.set(rid, sorted);
    return sorted;
}

async function _fetchOverviewMapPlayers(mapIndex) {
    const roundIds = _getOverviewRoundIdsForMap(mapIndex);
    if (!roundIds.length) return [];

    const scopeToken = _sessionId || _sessionDate || 'session';
    const cacheKey = `${scopeToken}:${mapIndex}:${roundIds.join(',')}`;
    const cached = _overviewMapStatsCache.get(cacheKey);
    if (cached && (Date.now() - cached._ts) < _CACHE_TTL_MS) return cached.data;

    const settled = await Promise.allSettled(roundIds.map(rid => _fetchOverviewRoundPlayers(rid)));
    settled.forEach((result, i) => {
        if (result.status === 'rejected') {
            console.error(`Overview round fetch ${i} (round ${roundIds[i]}) failed:`, result.reason);
        }
    });
    const byName = new Map();

    settled.forEach(result => {
        if (result.status !== 'fulfilled') return;
        result.value.forEach(player => {
            const key = (player.player_name || 'Unknown').trim().toLowerCase();
            if (!key) return;
            let bucket = byName.get(key);
            if (!bucket) {
                bucket = {
                    player_name: player.player_name || 'Unknown',
                    kills: 0,
                    deaths: 0,
                    damage_given: 0,
                    damage_received: 0,
                    gibs: 0,
                    self_kills: 0,
                    revives_given: 0,
                    times_revived: 0,
                    time_played: 0,
                    dpm_weighted: 0,
                    dpm_weight: 0,
                };
                byName.set(key, bucket);
            }

            const weight = player.time_played > 0 ? player.time_played : 1;
            bucket.kills += num(player.kills);
            bucket.deaths += num(player.deaths);
            bucket.damage_given += num(player.damage_given);
            bucket.damage_received += num(player.damage_received);
            bucket.gibs += num(player.gibs);
            bucket.self_kills += num(player.self_kills);
            bucket.revives_given += num(player.revives_given);
            bucket.times_revived += num(player.times_revived);
            bucket.time_played += num(player.time_played);
            bucket.dpm_weighted += num(player.dpm) * weight;
            bucket.dpm_weight += weight;
        });
    });

    const aggregated = Array.from(byName.values()).map(bucket => {
        const kd = bucket.kills / (bucket.deaths || 1);
        const dpm = bucket.time_played > 0
            ? bucket.damage_given / (bucket.time_played / 60)
            : (bucket.dpm_weight > 0 ? bucket.dpm_weighted / bucket.dpm_weight : 0);
        return {
            player_name: bucket.player_name,
            kills: bucket.kills,
            deaths: bucket.deaths,
            kd,
            dpm,
            damage_given: bucket.damage_given,
            damage_received: bucket.damage_received,
            gibs: bucket.gibs,
            self_kills: bucket.self_kills,
            revives_given: bucket.revives_given,
            times_revived: bucket.times_revived,
            time_played: bucket.time_played,
        };
    });

    const sorted = _sortScopedPlayers(aggregated);
    _overviewMapStatsCache.set(cacheKey, { data: sorted, _ts: Date.now() });
    return sorted;
}

async function _resolveOverviewScopedPlayers() {
    if (!_isOverviewScoped()) return _getOverviewSessionPlayers();

    const matches = _getOverviewMatches();
    if (_overviewMapIndex < 0 || _overviewMapIndex >= matches.length) {
        _overviewMapIndex = null;
        _overviewRoundId = null;
        return _getOverviewSessionPlayers();
    }

    if (_overviewRoundId) {
        return _fetchOverviewRoundPlayers(_overviewRoundId);
    }
    return _fetchOverviewMapPlayers(_overviewMapIndex);
}

function _renderOverviewPlayerStatsSection({ players = [], loading = false, error = null } = {}) {
    const scopeLabel = escapeHtml(_getOverviewScopeLabel());
    const rows = players.slice(0, 24).map((p, idx) => {
        const name = escapeHtml(p.player_name || p.name || 'Unknown');
        const jsName = escapeJsString(p.player_name || p.name || '');
        const rankClass = ['text-brand-gold', 'text-slate-300', 'text-amber-600'][idx] || 'text-slate-500';
        const kills = num(p.kills);
        const deaths = num(p.deaths);
        const kd = num(p.kd, kills / (deaths || 1)).toFixed(2);
        const dpm = num(p.dpm).toFixed(1);
        const dmg = Math.round(num(p.damage_given));
        return `
            <tr class="border-b border-white/5 hover:bg-white/5 cursor-pointer transition"
                onclick="loadPlayerProfile('${jsName}')">
                <td class="px-3 py-2 text-xs font-black ${rankClass}">#${idx + 1}</td>
                <td class="px-3 py-2 text-sm font-semibold text-white">${name}</td>
                <td class="px-2 py-2 text-right text-sm font-mono text-emerald-400">${kills}</td>
                <td class="px-2 py-2 text-right text-sm font-mono text-rose-400">${deaths}</td>
                <td class="px-2 py-2 text-right text-sm font-mono text-slate-300">${kd}</td>
                <td class="px-2 py-2 text-right text-sm font-mono text-brand-cyan font-bold">${dpm}</td>
                <td class="px-2 py-2 text-right text-sm font-mono text-brand-purple">${dmg.toLocaleString()}</td>
            </tr>`;
    }).join('');

    let bodyHtml = '';
    if (loading) {
        bodyHtml = `
            <div class="text-center py-8 text-slate-400">
                <i data-lucide="loader" class="w-5 h-5 animate-spin inline-block mr-2"></i>
                Loading scoped stats...
            </div>`;
    } else if (error) {
        bodyHtml = `
            <div class="text-center py-8 text-amber-300 text-sm">
                Could not load scoped stats. Clear selection or try another map/round.
            </div>`;
    } else if (!rows) {
        bodyHtml = '<div class="text-center py-8 text-slate-500 text-sm">No player stats for this selection.</div>';
    } else {
        bodyHtml = `
            <div class="overflow-x-auto rounded-xl border border-white/5">
                <table class="w-full text-left">
                    <thead>
                        <tr class="bg-white/5 border-b border-white/10 text-xs text-slate-400 uppercase">
                            <th class="px-3 py-2">#</th>
                            <th class="px-3 py-2">Player</th>
                            <th class="px-2 py-2 text-right">K</th>
                            <th class="px-2 py-2 text-right">D</th>
                            <th class="px-2 py-2 text-right">K/D</th>
                            <th class="px-2 py-2 text-right">DPM</th>
                            <th class="px-2 py-2 text-right">DMG</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>`;
    }

    return `
        <div class="glass-panel p-5 rounded-xl mb-8" id="sd-overview-player-stats-section">
            <div class="flex flex-wrap items-center gap-3 mb-4">
                <h3 class="text-lg font-bold text-white flex items-center gap-2">
                    <i data-lucide="users" class="w-5 h-5 text-brand-gold"></i> Player Stats
                </h3>
                <span class="text-xs px-2 py-1 rounded bg-brand-blue/20 text-brand-blue border border-brand-blue/30">${scopeLabel}</span>
                ${_isOverviewScoped() ? `
                    <button onclick="sdClearOverviewScope()"
                        class="ml-auto text-xs px-3 py-1 rounded-lg bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white transition">
                        Clear
                    </button>` : ''}
            </div>
            ${bodyHtml}
        </div>`;
}

function _renderOverviewMapBreakdown({ matches, scoringMaps, teamAName, teamBName }) {
    if (!matches.length && !scoringMaps.length) return '';

    if (!matches.length) {
        const staticRows = scoringMaps.map(m => {
            const mn = escapeHtml(mapLabel(m.map || 'Unknown'));
            const aPts = num(m.team_a_points);
            const bPts = num(m.team_b_points);
            const aWin = aPts > bPts;
            const bWin = bPts > aPts;
            const img = mapImageFor(m.map || '');
            const fb = img.includes('map_generic');
            const thumb = fb
                ? `<div class="w-16 h-12 rounded-md bg-slate-900/60 border border-white/10 flex items-center justify-center text-[9px] font-bold text-white px-1">${mn}</div>`
                : `<div class="relative w-16 h-12 rounded-md overflow-hidden border border-white/10"><div class="absolute inset-0 bg-cover bg-center" style="background-image:url('${img}')"></div><div class="absolute bottom-0 left-0 right-0 bg-black/50 text-[9px] text-slate-100 px-1 truncate">${mn}</div></div>`;
            return `
                <div class="flex items-center justify-between gap-4 p-3 rounded-lg bg-slate-900/40">
                    <div class="flex items-center gap-3">${thumb}<span class="font-bold text-white">${mn}</span></div>
                    <div class="flex items-center gap-3 text-sm">
                        <span class="${aWin ? 'text-brand-emerald font-bold' : 'text-slate-300'}">${escapeHtml(teamAName)} ${aPts}</span>
                        <span class="text-slate-500">vs</span>
                        <span class="${bWin ? 'text-brand-rose font-bold' : 'text-slate-300'}">${escapeHtml(teamBName)} ${bPts}</span>
                    </div>
                </div>`;
        }).join('');
        return `
            <div class="glass-panel p-5 rounded-xl mb-8">
                <h3 class="font-bold text-white mb-3 flex items-center gap-2">
                    <i data-lucide="map" class="w-5 h-5 text-brand-cyan"></i> Map Breakdown
                </h3>
                <div class="space-y-2">${staticRows}</div>
            </div>`;
    }

    const rows = matches.map((mapMatch, idx) => {
        const scoringRow = scoringMaps[idx] || {};
        const mapNameRaw = mapMatch.map_name || mapMatch.map || 'Unknown';
        const mn = escapeHtml(mapLabel(mapNameRaw));
        const img = mapImageFor(mapNameRaw);
        const fb = img.includes('map_generic');
        const isActiveMap = _overviewMapIndex === idx;
        const aPts = num(scoringRow.team_a_points);
        const bPts = num(scoringRow.team_b_points);
        const aWin = aPts > bPts;
        const bWin = bPts > aPts;
        const rounds = Array.isArray(mapMatch.rounds) ? mapMatch.rounds : [];
        const thumb = fb
            ? `<div class="w-16 h-12 rounded-md bg-slate-900/60 border border-white/10 flex items-center justify-center text-[9px] font-bold text-white px-1">${mn}</div>`
            : `<div class="relative w-16 h-12 rounded-md overflow-hidden border border-white/10"><div class="absolute inset-0 bg-cover bg-center" style="background-image:url('${img}')"></div><div class="absolute bottom-0 left-0 right-0 bg-black/50 text-[9px] text-slate-100 px-1 truncate">${mn}</div></div>`;

        const roundButtons = rounds.map(round => {
            const rid = coerceRoundId(round.round_id || round.id);
            if (!rid) return '';
            const roundNum = round.round_number;
            const roundLabel = roundNum ? `R${roundNum}` : `Round ${rid}`;
            const roundStartUnix = num(round.round_start_unix);
            const winnerTeam = num(round.winner_team);
            const winnerLabel = winnerTeam === 1 ? 'Axis' : winnerTeam === 2 ? 'Allies' : (round.winner || 'Draw');
            const winnerClass = winnerTeam === 1 ? 'text-brand-rose' : winnerTeam === 2 ? 'text-brand-blue' : 'text-slate-400';
            const durationLabel = round.duration_seconds ? formatDuration(round.duration_seconds) : (round.duration || '--');
            const isActiveRound = _overviewRoundId === rid;
            const roundDate = round.round_date || _sessionDate || '';
            return `
                <button onclick="event.stopPropagation(); sdSelectOverviewRound(${idx}, ${rid}, ${roundStartUnix}, '${escapeJsString(roundDate)}')"
                    class="px-3 py-1.5 rounded-lg text-xs border transition ${isActiveRound ? 'bg-brand-blue/20 border-brand-blue/40 text-white' : 'bg-black/30 border-white/10 text-slate-300 hover:bg-black/50'}">
                    <span class="font-bold">${roundLabel}</span>
                    <span class="mx-1 ${winnerClass}">${escapeHtml(winnerLabel)}</span>
                    <span class="text-slate-500">${escapeHtml(String(durationLabel))}</span>
                </button>`;
        }).join('');

        return `
            <div class="rounded-lg border ${isActiveMap ? 'border-brand-blue/50 bg-brand-blue/5' : 'border-white/10 bg-slate-900/40'}">
                <button onclick="sdSelectOverviewMap(${idx})"
                    class="w-full text-left flex items-center justify-between gap-4 p-3 transition hover:bg-white/5 rounded-lg">
                    <div class="flex items-center gap-3 min-w-0">
                        ${thumb}
                        <div class="min-w-0">
                            <div class="font-bold text-white truncate">${mn}</div>
                            <div class="text-xs text-slate-500">${rounds.length} rounds</div>
                        </div>
                    </div>
                    <div class="flex items-center gap-4 shrink-0">
                        <div class="text-right text-sm">
                            <div class="${aWin ? 'text-brand-emerald font-bold' : 'text-slate-300'}">${escapeHtml(teamAName)} ${aPts}</div>
                            <div class="${bWin ? 'text-brand-rose font-bold' : 'text-slate-300'}">${escapeHtml(teamBName)} ${bPts}</div>
                        </div>
                        <i data-lucide="${isActiveMap ? 'chevron-down' : 'chevron-right'}" class="w-4 h-4 text-slate-400"></i>
                    </div>
                </button>
                ${isActiveMap ? `
                    <div class="px-3 pb-3 border-t border-white/10">
                        <div class="text-xs text-slate-500 pt-3 mb-2">Select a round to filter player stats below:</div>
                        <div class="flex flex-wrap gap-2">${roundButtons || '<span class="text-xs text-slate-500">No rounds available</span>'}</div>
                    </div>` : ''}
            </div>`;
    }).join('');

    return `
        <div class="glass-panel p-5 rounded-xl mb-8">
            <div class="flex items-center gap-2 mb-3">
                <i data-lucide="map" class="w-5 h-5 text-brand-cyan"></i>
                <h3 class="font-bold text-white">Map Breakdown</h3>
                ${_isOverviewScoped() ? `
                    <button onclick="sdClearOverviewScope()"
                        class="ml-auto text-xs px-3 py-1 rounded-lg bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white transition">
                        Clear selection
                    </button>` : ''}
            </div>
            <div class="text-xs text-slate-500 mb-3">Click map row to expand rounds, then click a round to scope player stats.</div>
            <div class="space-y-2">${rows}</div>
        </div>`;
}

async function _renderSummaryTab(force = false) {
    const panel = document.getElementById('sd-tab-summary');
    if (!panel) return;
    if (!force && panel.dataset.rendered === '1') return;
    panel.dataset.rendered = '1';
    const renderToken = ++_overviewRenderToken;

    const data = _detailData;
    const scoring = data.scoring || {};
    const hasScoring = scoring.available === true;
    const teamAName = hasScoring ? (scoring.team_a_name || 'Allies') : 'Allies';
    const teamBName = hasScoring ? (scoring.team_b_name || 'Axis') : 'Axis';
    const scoringMaps = hasScoring && Array.isArray(scoring.maps) ? scoring.maps : [];
    const matches = _getOverviewMatches();

    let html = `
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <div class="glass-card p-4 rounded-xl text-center">
                <div class="text-xs text-slate-500 uppercase font-bold">Total Rounds</div>
                <div class="text-2xl font-black text-white">${data.round_count ?? data.total_rounds ?? 0}</div>
            </div>
            <div class="glass-card p-4 rounded-xl text-center">
                <div class="text-xs text-slate-500 uppercase font-bold">Maps Played</div>
                <div class="text-2xl font-black text-brand-blue">${matches.length}</div>
            </div>
            <div class="glass-card p-4 rounded-xl text-center">
                <div class="text-xs text-slate-500 uppercase font-bold">Players</div>
                <div class="text-2xl font-black text-brand-purple">${data.player_count ?? 0}</div>
            </div>
            <div class="glass-card p-4 rounded-xl text-center">
                <div class="text-xs text-slate-500 uppercase font-bold">Session Score</div>
                <div class="text-2xl font-black text-white">${scoring.team_a_score ?? 0} - ${scoring.team_b_score ?? 0}</div>
                <div class="text-xs text-slate-400 mt-1">${escapeHtml(teamAName)} vs ${escapeHtml(teamBName)}</div>
            </div>
        </div>`;

    html += _renderOverviewMapBreakdown({ matches, scoringMaps, teamAName, teamBName });
    html += _renderOverviewPlayerStatsSection({ loading: true });

    const teams = data.teams || (scoring.teams ? scoring.teams : []);
    if (Array.isArray(teams) && teams.length > 0) {
        const rosterHtml = teams.map((team, idx) => {
            const players = Array.isArray(team.players) ? team.players : [];
            const icon = idx === 0 ? ALLIES_ICON : AXIS_ICON;
            const rows = players.map(p => {
                const name = escapeHtml(p.name || 'Unknown');
                const jsName = escapeJsString(p.name || '');
                const kd = num(p.kd).toFixed(2);
                return `
                    <div class="flex items-center justify-between text-sm py-2 border-b border-white/5 cursor-pointer hover:bg-white/5"
                         onclick="loadPlayerProfile('${jsName}')">
                        <span class="font-semibold text-white">${name}
                            <span class="text-xs text-slate-500 ml-2">K/D ${kd}</span>
                        </span>
                        <div class="flex items-center gap-3 text-xs text-slate-400">
                            <span>K ${num(p.kills)}</span><span>D ${num(p.deaths)}</span>
                            <span>DPM ${num(p.dpm).toFixed(1)}</span>
                        </div>
                    </div>`;
            }).join('');
            return `
                <div class="glass-panel p-5 rounded-xl">
                    <div class="flex items-center gap-2 mb-3">
                        <img src="${icon}" alt="Team" class="w-6 h-6" />
                        <h3 class="font-bold text-white">${escapeHtml(team.name || `Team ${idx + 1}`)}</h3>
                        <span class="text-xs text-slate-500 ml-auto">${players.length} players</span>
                    </div>
                    ${rows || '<div class="text-xs text-slate-500">No player data</div>'}
                </div>`;
        }).join('');
        html += `<div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">${rosterHtml}</div>`;
    }

    html += _renderRoundsSection();

    panel.innerHTML = html;
    if (typeof lucide !== 'undefined') lucide.createIcons();

    let scopedPlayers = [];
    let scopedError = null;
    try {
        scopedPlayers = await _resolveOverviewScopedPlayers();
    } catch (e) {
        console.error('Overview scoped stats load failed:', e);
        scopedError = e;
    }

    if (renderToken !== _overviewRenderToken || _activeTab !== 'summary') return;

    const statsSection = document.getElementById('sd-overview-player-stats-section');
    if (statsSection) {
        statsSection.outerHTML = _renderOverviewPlayerStatsSection({
            players: scopedPlayers,
            error: scopedError,
            loading: false,
        });
        if (typeof lucide !== 'undefined') lucide.createIcons();
    }
}

export function sdSelectOverviewMap(mapIndex) {
    const parsed = Number.parseInt(String(mapIndex), 10);
    if (!Number.isFinite(parsed) || parsed < 0) return;
    if (_activeRoundId) sdClearRoundScope();
    if (_overviewMapIndex === parsed && !_overviewRoundId) {
        _overviewMapIndex = null;
        _overviewRoundId = null;
    } else {
        _overviewMapIndex = parsed;
        _overviewRoundId = null;
    }
    _renderSummaryTab(true);
}

export function sdSelectOverviewRound(mapIndex, roundId, roundStartUnix = 0, roundDate = '') {
    const parsedMap = Number.parseInt(String(mapIndex), 10);
    const parsedRound = coerceRoundId(roundId);
    const parsedStartUnix = num(roundStartUnix);
    if (!Number.isFinite(parsedMap) || parsedMap < 0 || !parsedRound) return;
    _overviewMapIndex = parsedMap;
    _overviewRoundId = parsedRound;
    sdSelectRound(parsedRound, roundDate || _sessionDate, parsedStartUnix);
    _renderSummaryTab(true);
    setTimeout(() => {
        const section = document.getElementById('sd-overview-player-stats-section');
        if (section) section.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 0);
}

export function sdClearOverviewScope() {
    if (_activeRoundId) sdClearRoundScope();
    _overviewMapIndex = null;
    _overviewRoundId = null;
    _renderSummaryTab(true);
}

// ============================================================
// ROUNDS SECTION (embedded in Summary tab)
// ============================================================

function _renderRoundsSection() {
    const allRounds = _collectSessionRounds();
    if (!allRounds.length) return '';

    const roundRows = allRounds.map(r => {
        const mn = escapeHtml(mapLabel(r.mapName || 'Unknown'));
        const badge = r.roundNumber === 1
            ? `<span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-amber-500/20 text-amber-300">R1</span>`
            : `<span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-violet-500/20 text-violet-300">R2</span>`;
        const wl = r.winnerTeam === 1 ? 'Axis' : r.winnerTeam === 2 ? 'Allies' : (r.winner || 'Draw');
        const wc = r.winnerTeam === 1 ? 'text-brand-rose' : r.winnerTeam === 2 ? 'text-brand-blue' : 'text-slate-400';
        const dt = r.durationSeconds ? formatDuration(r.durationSeconds) : 'N/A';
        const img = mapImageFor(r.mapName || '');
        const fb = img.includes('map_generic');
        const thumb = fb
            ? `<div class="w-14 h-10 rounded bg-slate-900/60 border border-white/10 flex items-center justify-center text-[9px] font-bold text-white px-1 shrink-0">${mn}</div>`
            : `<div class="relative w-14 h-10 rounded overflow-hidden border border-white/10 shrink-0"><div class="absolute inset-0 bg-cover bg-center" style="background-image:url('${img}')"></div></div>`;
        return `
            <div class="glass-card rounded-lg p-4 flex items-center gap-4 cursor-pointer hover:bg-white/5 transition sd-round-row ${_activeRoundId === r.roundId ? 'ring-1 ring-brand-blue' : ''}"
                 id="sd-round-row-${r.roundId}"
                 onclick="sdSelectRound(${r.roundId}, '${escapeJsString(r.sessionDate || '')}', ${r.roundStartUnix}, '${escapeJsString(r.mapName || '')}', ${r.roundNumber || 0})">
                ${thumb}
                <div class="flex items-center gap-2">${badge}</div>
                <div>
                    <div class="font-bold text-white text-sm">${mn}</div>
                    <div class="text-xs ${wc}">${escapeHtml(wl)} Win</div>
                </div>
                <div class="text-xs text-slate-500 ml-auto">${escapeHtml(dt)}</div>
                <div class="text-xs text-brand-cyan font-bold whitespace-nowrap">Scope →</div>
            </div>`;
    }).join('');

    return `
        <div class="glass-panel p-5 rounded-xl mt-8">
            <h3 class="font-bold text-white mb-3 flex items-center gap-2">
                <i data-lucide="list" class="w-5 h-5 text-brand-cyan"></i> All Rounds
            </h3>
            <div class="text-xs text-slate-500 mb-3">Click a round to scope Teamplay and Charts to that round.</div>
            <div class="space-y-3">${roundRows}</div>
        </div>`;
}

// ============================================================
// ROUND SCOPE
// ============================================================

function _refreshRoundScopeUi() {
    const scopePill = document.getElementById('sd-hero-scope-pill');
    if (scopePill) scopePill.textContent = _getScopePillLabel();

    const clearBtn = document.getElementById('sd-hero-clear-btn');
    if (clearBtn) clearBtn.classList.toggle('hidden', _expandedMapIndex === null);

    const timeline = document.getElementById('sd-map-round-timeline');
    if (timeline) timeline.innerHTML = _renderMapRoundTimeline();

    const mapStrip = document.getElementById('sd-map-strip');
    if (mapStrip) {
        const scoring = _detailData?.scoring || {};
        mapStrip.innerHTML = _renderSessionHeaderMapStrip(scoring);
    }
}

export function sdSelectRound(roundId, sessionDate, roundStartUnix, mapName, roundNumber) {
    _activeRoundId = coerceRoundId(roundId);
    if (!_activeRoundId) return;
    _activeRoundStartUnix = roundStartUnix || null;
    _activeRoundSessionDate = sessionDate || _sessionDate;
    _activeRoundMapName = mapName || null;
    _activeRoundNumber = roundNumber || null;

    document.querySelectorAll('.sd-round-row').forEach(el => el.classList.remove('ring-1', 'ring-brand-blue'));
    const row = document.getElementById(`sd-round-row-${_activeRoundId}`);
    if (row) row.classList.add('ring-1', 'ring-brand-blue');

    _refreshRoundScopeUi();

    _signalsLoaded = null;
    _vizLoaded = null;
    _playersScopeLoaded = null;

    if (_activeTab === 'teamplay') _loadSignalsTab();
    else if (_activeTab === 'charts') _loadVizTab();
    else if (_activeTab === 'players') _renderPlayersTab(true);
    else if (_activeTab === 'summary') _renderSummaryTab(true);
}

export function sdClearRoundScope() {
    _activeRoundId = null;
    _activeRoundStartUnix = null;
    _activeRoundSessionDate = null;
    _signalsLoaded = null;
    _vizLoaded = null;
    _playersScopeLoaded = null;

    document.querySelectorAll('.sd-round-row').forEach(el => el.classList.remove('ring-1', 'ring-brand-blue'));
    _refreshRoundScopeUi();

    if (_activeTab === 'teamplay') _loadSignalsTab();
    else if (_activeTab === 'charts') _loadVizTab();
    else if (_activeTab === 'players') _renderPlayersTab(true);
    else if (_activeTab === 'summary') _renderSummaryTab(true);
}

// ============================================================
// PLAYERS TAB
// ============================================================

async function _fetchPlayersForActiveRound(roundId) {
    const rid = coerceRoundId(roundId);
    if (!rid) return [];
    if (_roundPlayersCache.has(rid)) return _roundPlayersCache.get(rid);

    const payload = await fetchJSON(`${API_BASE}/stats/matches/${encodeURIComponent(rid)}`);
    const team1 = Array.isArray(payload?.team1?.players) ? payload.team1.players : [];
    const team2 = Array.isArray(payload?.team2?.players) ? payload.team2.players : [];
    const players = [...team1, ...team2]
        .map(player => _normalizePlayerRow(player, 'round'))
        .sort(_playerSort);
    _roundPlayersCache.set(rid, players);
    return players;
}

function _getSessionPlayersForPlayersTab() {
    let players = Array.isArray(_detailData?.players) ? _detailData.players : [];
    if (!players.length && Array.isArray(_detailData?.teams)) {
        players = _detailData.teams.flatMap(team => (
            (team.players || []).map(player => ({ player_name: player.name, ...player }))
        ));
    }
    return players.map(player => _normalizePlayerRow(player, 'session')).sort(_playerSort);
}

async function _getPlayersForCurrentScope() {
    if (_activeRoundId) return _fetchPlayersForActiveRound(_activeRoundId);
    return _getSessionPlayersForPlayersTab();
}

function _formatDeniedSeconds(rawValue) {
    const deniedSeconds = num(rawValue, Number.NaN);
    if (!Number.isFinite(deniedSeconds)) return '--';
    const clamped = Math.max(0, Math.floor(deniedSeconds));
    return `${Math.floor(clamped / 60)}:${String(clamped % 60).padStart(2, '0')}`;
}

function _formatPctLabel(rawValue) {
    const value = num(rawValue, Number.NaN);
    return Number.isFinite(value) ? `${value.toFixed(1)}%` : '--';
}

function _normalizeLookupName(name) {
    return String(name || '').replace(/\^[0-9A-Za-z]/g, '').trim().toLowerCase();
}

function _chartColor(hex, alpha = 1) {
    const clean = String(hex || '').replace('#', '');
    if (clean.length !== 6) return `rgba(56, 189, 248, ${alpha})`;
    const int = Number.parseInt(clean, 16);
    const r = (int >> 16) & 255;
    const g = (int >> 8) & 255;
    const b = int & 255;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function _destroyPlayerPanelChart(panelId) {
    const chart = _playerPanelCharts.get(panelId);
    if (!chart) return;
    try {
        chart.destroy();
    } catch (e) {
        // ignore
    }
    _playerPanelCharts.delete(panelId);
}

function _destroyAllPlayerPanelCharts() {
    Array.from(_playerPanelCharts.keys()).forEach(_destroyPlayerPanelChart);
}

function _destroyPlayersSummaryCharts() {
    _playersSummaryCharts.forEach(chart => {
        try {
            chart.destroy();
        } catch (e) {
            // ignore
        }
    });
    _playersSummaryCharts = [];
}

async function _getTradePlayerStatsForCurrentScope() {
    const scopeParams = _tradeScopeParams();
    const cacheKey = scopeParams || 'session';
    if (_playerTradeScopeCache.has(cacheKey)) return _playerTradeScopeCache.get(cacheKey);

    const url = `${API_BASE}/proximity/trades/player-stats${scopeParams ? `?${scopeParams}` : ''}`;
    const request = fetchJSON(url).catch(error => {
        _playerTradeScopeCache.delete(cacheKey);
        throw error;
    });
    _playerTradeScopeCache.set(cacheKey, request);
    return request;
}

async function _getSessionGraphData() {
    if (_graphData) return _graphData;
    if (!_sessionDate) return null;
    if (_sessionGraphDataPromise) return _sessionGraphDataPromise;

    const graphUrl = _sessionId
        ? `${API_BASE}/sessions/${encodeURIComponent(_sessionDate)}/graphs?gaming_session_id=${encodeURIComponent(_sessionId)}`
        : `${API_BASE}/sessions/${encodeURIComponent(_sessionDate)}/graphs`;

    _sessionGraphDataPromise = fetchJSON(graphUrl)
        .then(payload => {
            _graphData = payload;
            return payload;
        })
        .catch(error => {
            _sessionGraphDataPromise = null;
            throw error;
        })
        .finally(() => {
            _sessionGraphDataPromise = null;
        });

    return _sessionGraphDataPromise;
}

function _findPlayersLeader(players = [], metricFn = () => 0) {
    return players.reduce((best, player) => {
        if (!best) return player;
        return metricFn(player) > metricFn(best) ? player : best;
    }, null);
}

function _renderPlayersInsightCards(players = []) {
    if (!players.length) return '';

    const dpmLeader = _findPlayersLeader(players, player => num(player.dpm));
    const kdLeader = _findPlayersLeader(players, player => num(player.kd, num(player.kills) / (num(player.deaths) || 1)));
    const accuracyLeader = _findPlayersLeader(players, player => num(player.accuracy));
    const pressureLeader = _findPlayersLeader(players, player => num(player.damage_given) - num(player.damage_received));

    const cards = [
        {
            label: 'Pace Leader',
            tone: 'text-brand-cyan',
            player: dpmLeader,
            value: `${num(dpmLeader?.dpm).toFixed(1)} DPM`,
        },
        {
            label: 'Best K/D',
            tone: 'text-brand-gold',
            player: kdLeader,
            value: `${num(kdLeader?.kd, num(kdLeader?.kills) / (num(kdLeader?.deaths) || 1)).toFixed(2)} K/D`,
        },
        {
            label: 'Sharpest Aim',
            tone: 'text-brand-emerald',
            player: accuracyLeader,
            value: `${num(accuracyLeader?.accuracy).toFixed(1)}% ACC`,
        },
        {
            label: 'Net Pressure',
            tone: 'text-brand-rose',
            player: pressureLeader,
            value: `${Math.round(num(pressureLeader?.damage_given) - num(pressureLeader?.damage_received)).toLocaleString()} DMG`,
        },
    ];

    return `
        <div class="grid grid-cols-2 xl:grid-cols-4 gap-3 mb-4">
            ${cards.map(card => `
                <div class="glass-card rounded-xl p-3">
                    <div class="text-[10px] font-bold uppercase tracking-wider text-slate-500">${card.label}</div>
                    <div class="mt-2 text-sm font-bold text-white truncate">${escapeHtml(card.player?.player_name || 'Unknown')}</div>
                    <div class="mt-1 text-xs ${card.tone} font-mono">${escapeHtml(card.value)}</div>
                </div>`).join('')}
        </div>`;
}

function _renderPlayersAnalyticsSection(players = []) {
    const scopeLabel = escapeHtml(_roundScopeLabel());
    const ladderHeight = Math.max(220, players.length * 34);

    return `
        <div class="glass-panel rounded-xl p-4 mb-4">
            <div class="flex flex-wrap items-center gap-3">
                <div class="flex items-center gap-2 text-white font-bold">
                    <i data-lucide="chart-line" class="w-4 h-4 text-brand-cyan"></i>
                    Player Intelligence
                </div>
                <span class="text-xs px-2 py-1 rounded bg-brand-blue/20 text-brand-blue border border-brand-blue/30">${scopeLabel}</span>
            </div>
            <div class="mt-2 text-xs text-slate-500">
                Use the ladders for raw pressure, the exchange chart for durability, and the scatter to spot efficient outliers.
            </div>
        </div>
        ${_renderPlayersInsightCards(players)}
        <div class="grid grid-cols-1 xl:grid-cols-2 gap-4 mb-4">
            <div class="glass-card rounded-xl p-4">
                <div class="mb-3">
                    <div class="text-sm font-bold text-white">DPM Ladder</div>
                    <div class="text-xs text-slate-500">Who dictated the pace in this scope.</div>
                </div>
                <div style="height:${ladderHeight}px"><canvas id="sd-players-dpm-chart"></canvas></div>
            </div>
            <div class="glass-card rounded-xl p-4">
                <div class="mb-3">
                    <div class="text-sm font-bold text-white">Damage Exchange</div>
                    <div class="text-xs text-slate-500">Pressure generated versus punishment absorbed.</div>
                </div>
                <div style="height:${ladderHeight}px"><canvas id="sd-players-exchange-chart"></canvas></div>
            </div>
        </div>
        <div class="glass-card rounded-xl p-4 mb-4">
            <div class="mb-3">
                <div class="text-sm font-bold text-white">Accuracy vs K/D</div>
                <div class="text-xs text-slate-500">Bubble size tracks damage output. High-right is efficient aim.</div>
            </div>
            <div style="height:320px"><canvas id="sd-players-scatter-chart"></canvas></div>
        </div>`;
}

function _mountPlayersSummaryCharts(players = []) {
    _destroyPlayersSummaryCharts();
    if (!players.length || typeof Chart === 'undefined') return;

    const labels = players.map(player => player.player_name || 'Unknown');
    const palette = players.map((_, idx) => PLAYER_GRAPH_COLORS[idx % PLAYER_GRAPH_COLORS.length]);
    const dpmValues = players.map(player => Number(num(player.dpm).toFixed(1)));
    const killsValues = players.map(player => num(player.kills));
    const damageGivenValues = players.map(player => Math.round(num(player.damage_given)));
    const damageReceivedValues = players.map(player => Math.round(num(player.damage_received)));

    const dpmCanvas = document.getElementById('sd-players-dpm-chart');
    if (dpmCanvas) {
        const chart = new Chart(dpmCanvas.getContext('2d'), {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label: 'DPM',
                    data: dpmValues,
                    backgroundColor: palette.map(color => _chartColor(color, 0.55)),
                    borderColor: palette,
                    borderWidth: 1.5,
                    borderRadius: 6,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y',
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: context => {
                                const index = context.dataIndex;
                                return [
                                    `DPM: ${num(context.raw).toFixed(1)}`,
                                    `Kills: ${killsValues[index]}`,
                                ];
                            },
                        },
                    },
                },
                scales: {
                    x: {
                        ticks: { color: '#94a3b8' },
                        grid: { color: 'rgba(30, 41, 59, 0.9)' },
                        title: { display: true, text: 'Damage per minute', color: '#64748b' },
                    },
                    y: {
                        ticks: { color: '#e2e8f0', font: { size: 11 } },
                        grid: { display: false },
                    },
                },
            },
        });
        _playersSummaryCharts.push(chart);
    }

    const exchangeCanvas = document.getElementById('sd-players-exchange-chart');
    if (exchangeCanvas) {
        const chart = new Chart(exchangeCanvas.getContext('2d'), {
            type: 'bar',
            data: {
                labels,
                datasets: [
                    {
                        label: 'Damage Given',
                        data: damageGivenValues,
                        backgroundColor: _chartColor('#22c55e', 0.55),
                        borderColor: '#22c55e',
                        borderWidth: 1.2,
                        borderRadius: 6,
                    },
                    {
                        label: 'Damage Received',
                        data: damageReceivedValues,
                        backgroundColor: _chartColor('#f43f5e', 0.45),
                        borderColor: '#f43f5e',
                        borderWidth: 1.2,
                        borderRadius: 6,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y',
                plugins: {
                    legend: { labels: { color: '#cbd5e1', font: { size: 11 } } },
                },
                scales: {
                    x: {
                        ticks: {
                            color: '#94a3b8',
                            callback: value => `${Math.round(Number(value) / 1000)}k`,
                        },
                        grid: { color: 'rgba(30, 41, 59, 0.9)' },
                        title: { display: true, text: 'Damage', color: '#64748b' },
                    },
                    y: {
                        ticks: { color: '#e2e8f0', font: { size: 11 } },
                        grid: { display: false },
                    },
                },
            },
        });
        _playersSummaryCharts.push(chart);
    }

    const maxDamage = Math.max(...damageGivenValues, 1);
    const scatterCanvas = document.getElementById('sd-players-scatter-chart');
    if (scatterCanvas) {
        const chart = new Chart(scatterCanvas.getContext('2d'), {
            type: 'bubble',
            data: {
                datasets: [{
                    label: 'Players',
                    data: players.map(player => ({
                        x: Number(num(player.accuracy).toFixed(1)),
                        y: Number(num(player.kd, num(player.kills) / (num(player.deaths) || 1)).toFixed(2)),
                        r: 6 + Math.round(Math.sqrt(num(player.damage_given) / maxDamage) * 12),
                        label: player.player_name || 'Unknown',
                        dpm: Number(num(player.dpm).toFixed(1)),
                        damage: Math.round(num(player.damage_given)),
                        kills: num(player.kills),
                    })),
                    backgroundColor: palette.map(color => _chartColor(color, 0.4)),
                    borderColor: palette,
                    borderWidth: 1.5,
                    hoverBorderWidth: 2,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            title: items => items[0]?.raw?.label || 'Player',
                            label: context => {
                                const raw = context.raw || {};
                                return [
                                    `Accuracy: ${num(raw.x).toFixed(1)}%`,
                                    `K/D: ${num(raw.y).toFixed(2)}`,
                                    `DPM: ${num(raw.dpm).toFixed(1)}`,
                                    `Damage: ${Math.round(num(raw.damage)).toLocaleString()}`,
                                    `Kills: ${num(raw.kills)}`,
                                ];
                            },
                        },
                    },
                },
                scales: {
                    x: {
                        min: 0,
                        max: 100,
                        ticks: { color: '#94a3b8' },
                        grid: { color: 'rgba(30, 41, 59, 0.9)' },
                        title: { display: true, text: 'Accuracy %', color: '#64748b' },
                    },
                    y: {
                        min: 0,
                        ticks: { color: '#94a3b8' },
                        grid: { color: 'rgba(30, 41, 59, 0.9)' },
                        title: { display: true, text: 'K/D', color: '#64748b' },
                    },
                },
            },
        });
        _playersSummaryCharts.push(chart);
    }
}

async function _renderPlayersTab(force = false) {
    const panel = document.getElementById('sd-tab-players');
    if (!panel) return;

    const scopeKey = _activeRoundId ? `round:${_activeRoundId}` : 'session';
    if (!force && panel.dataset.rendered === '1' && _playersScopeLoaded === scopeKey) return;

    panel.dataset.rendered = '1';
    _destroyPlayersSummaryCharts();
    _destroyAllPlayerPanelCharts();
    const renderToken = ++_playersRenderToken;
    panel.innerHTML = `
        <div class="glass-panel rounded-xl p-5 text-center text-slate-400">
            <i data-lucide="loader" class="w-5 h-5 animate-spin inline-block mr-2"></i>
            Loading ${_activeRoundId ? 'round-scoped' : 'session'} player stats...
        </div>`;
    if (typeof lucide !== 'undefined') lucide.createIcons();

    let players = [];
    try {
        players = await _getPlayersForCurrentScope();
    } catch (e) {
        console.error('Players tab load failed:', e);
    }

    if (renderToken !== _playersRenderToken) return;

    if (!players.length) {
        panel.innerHTML = '<div class="text-slate-500 text-center py-12">No player data for this scope</div>';
        return;
    }

    const rows = players.map((player, idx) => {
        const name = escapeHtml(player.player_name || 'Unknown');
        const jsName = escapeJsString(player.player_name || '');
        const guidRaw = player.player_guid || '';
        const guidJs = escapeJsString(guidRaw);
        const panelId = `sd-player-panel-${_activeRoundId || 'session'}-${idx}`;

        const kills = num(player.kills);
        const deaths = num(player.deaths);
        const kd = num(player.kd, kills / (deaths || 1)).toFixed(2);
        const dpm = num(player.dpm).toFixed(1);
        const dmgG = Math.round(num(player.damage_given));
        const dmgR = Math.round(num(player.damage_received));
        const eff = num(player.efficiency).toFixed(1);
        const hsPct = num(player.headshot_pct).toFixed(1);
        const acc = num(player.accuracy).toFixed(1);
        const alivePct = _formatPctLabel(player.alive_pct);
        const playedPct = _formatPctLabel(player.played_pct);
        const playedPctLua = _formatPctLabel(player.played_pct_lua);
        const deadMinutes = player.time_dead_minutes != null ? `${num(player.time_dead_minutes).toFixed(1)}` : '--';
        const denied = _formatDeniedSeconds(player.denied_playtime);
        const actionLabel = _activeRoundId && guidRaw ? '▶ Mastery' : '▶ Details';

        return `
            <tr class="border-b border-white/5 hover:bg-white/5 transition ${idx === 0 ? 'bg-cyan-500/5' : ''}">
                <td class="px-3 py-2 text-sm font-semibold text-white whitespace-nowrap cursor-pointer"
                    onclick="loadPlayerProfile('${jsName}')">
                    <div>${idx === 0 ? '<span class="text-brand-gold mr-1">★</span>' : ''}${name}</div>
                    <div class="md:hidden text-[10px] text-slate-500 mt-0.5">
                        DPM ${dpm} · DMG ${dmgG.toLocaleString()} · Alive ${alivePct} · Played ${playedPct} · Lua ${playedPctLua}
                    </div>
                </td>
                <td class="px-2 py-2 text-sm font-mono text-emerald-400 text-right">${kills}</td>
                <td class="px-2 py-2 text-sm font-mono text-rose-400 text-right">${deaths}</td>
                <td class="px-2 py-2 text-sm font-mono text-slate-300 text-right">${kd}</td>
                <td class="px-2 py-2 text-sm font-mono text-emerald-400 text-right hidden lg:table-cell">${dmgG.toLocaleString()}</td>
                <td class="px-2 py-2 text-sm font-mono text-rose-400 text-right hidden lg:table-cell">${dmgR.toLocaleString()}</td>
                <td class="px-2 py-2 text-sm font-mono text-amber-300 font-bold text-right">${dpm}</td>
                <td class="px-2 py-2 text-sm font-mono text-amber-300 text-right hidden xl:table-cell">${alivePct}</td>
                <td class="px-2 py-2 text-sm font-mono text-cyan-300 text-right hidden xl:table-cell">${playedPct}</td>
                <td class="px-2 py-2 text-sm font-mono text-fuchsia-300 text-right hidden xl:table-cell">${playedPctLua}</td>
                <td class="px-2 py-2 text-sm font-mono text-slate-300 text-right hidden xl:table-cell">${deadMinutes}</td>
                <td class="px-2 py-2 text-sm font-mono text-slate-300 text-right hidden xl:table-cell">${denied}</td>
                <td class="px-2 py-2 text-sm font-mono text-slate-300 text-right hidden xl:table-cell">${eff}%</td>
                <td class="px-2 py-2 text-sm font-mono text-slate-400 text-right hidden xl:table-cell">${hsPct}%</td>
                <td class="px-2 py-2 text-sm font-mono text-slate-400 text-right hidden xl:table-cell">${acc}%</td>
                <td class="px-2 py-2 text-sm font-mono text-slate-400 text-right hidden xl:table-cell">${num(player.gibs)}</td>
                <td class="px-2 py-2 text-sm font-mono text-slate-400 text-right hidden xl:table-cell">${num(player.revives_given)}</td>
                <td class="px-2 py-2 text-sm font-mono text-slate-400 text-right hidden xl:table-cell">${num(player.times_revived)}</td>
                <td class="px-2 py-2 text-right">
                    <button onclick="sdTogglePlayerPanel('${jsName}', '${guidJs}', '${panelId}')"
                        class="text-xs px-2 py-1 rounded bg-brand-blue/20 text-brand-blue hover:bg-brand-blue/30 transition whitespace-nowrap">
                        ${actionLabel}
                    </button>
                </td>
            </tr>
            <tr id="${panelId}" class="hidden">
                <td colspan="19" class="px-4 py-4 bg-slate-900/40">
                    <div class="text-slate-500 text-xs text-center py-2">Loading details...</div>
                </td>
            </tr>`;
    }).join('');

    panel.innerHTML = `
        ${_renderPlayersAnalyticsSection(players)}
        <div class="glass-panel rounded-xl p-4 mb-4 flex items-center gap-3">
            <i data-lucide="users" class="w-4 h-4 text-brand-cyan"></i>
            <span class="text-sm text-slate-300">
                Scope: <strong class="text-white">${escapeHtml(_roundScopeLabel())}</strong>
            </span>
            ${_activeRoundId
        ? '<span class="ml-auto text-xs text-brand-cyan">Round weapon mastery available per player</span>'
        : '<span class="ml-auto text-xs text-brand-cyan">Session weapon mastery available per player</span>'}
        </div>
        <div class="glass-panel rounded-xl p-4 mb-4">
            <div class="flex flex-wrap gap-2 text-[11px]">
                <span class="inline-flex items-center rounded-full border border-amber-400/20 bg-amber-400/10 px-3 py-1 font-medium text-amber-200">
                    Alive% = time not dead while the player was active
                </span>
                <span class="inline-flex items-center rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 font-medium text-cyan-200">
                    Played% = share of the scoped round/session time the player was present
                </span>
                <span class="inline-flex items-center rounded-full border border-fuchsia-400/20 bg-fuchsia-400/10 px-3 py-1 font-medium text-fuchsia-200">
                    Lua Played% = raw TAB[8] percent captured from c0rnp0rn
                </span>
            </div>
        </div>
        <div class="overflow-x-auto rounded-xl border border-white/5">
            <table class="w-full text-left">
                <thead>
                    <tr class="bg-white/5 border-b border-white/10 text-xs text-slate-400 uppercase">
                        <th class="px-3 py-2">Player</th>
                        <th class="px-2 py-2 text-right">K</th>
                        <th class="px-2 py-2 text-right">D</th>
                        <th class="px-2 py-2 text-right">K/D</th>
                        <th class="px-2 py-2 text-right hidden lg:table-cell">DMG G</th>
                        <th class="px-2 py-2 text-right hidden lg:table-cell">DMG R</th>
                        <th class="px-2 py-2 text-right">DPM</th>
                        <th class="px-2 py-2 text-right hidden xl:table-cell text-amber-300" title="Alive%: time not dead during the time the player actually played">Alive%</th>
                        <th class="px-2 py-2 text-right hidden xl:table-cell text-cyan-300" title="Played%: share of the scoped round or session duration the player was present">Played%</th>
                        <th class="px-2 py-2 text-right hidden xl:table-cell text-fuchsia-300" title="Lua Played%: raw TAB[8] time_played_percent from the stats file">Lua Played%</th>
                        <th class="px-2 py-2 text-right hidden xl:table-cell">Dead Min</th>
                        <th class="px-2 py-2 text-right hidden xl:table-cell">Denied</th>
                        <th class="px-2 py-2 text-right hidden xl:table-cell">EFF</th>
                        <th class="px-2 py-2 text-right hidden xl:table-cell">HS%</th>
                        <th class="px-2 py-2 text-right hidden xl:table-cell">ACC</th>
                        <th class="px-2 py-2 text-right hidden xl:table-cell">Gibs</th>
                        <th class="px-2 py-2 text-right hidden xl:table-cell">REV</th>
                        <th class="px-2 py-2 text-right hidden xl:table-cell">Rev'd</th>
                        <th class="px-2 py-2"></th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>`;

    _playersScopeLoaded = scopeKey;
    if (typeof lucide !== 'undefined') lucide.createIcons();
    _mountPlayersSummaryCharts(players);
}

function _playerPanelKey(playerName, playerGuid) {
    const guidKey = (playerGuid || '').trim();
    const nameKey = _normalizeLookupName(playerName);
    const playerKey = guidKey || nameKey || 'unknown';
    return `${_activeRoundId || 'session'}:${playerKey}`;
}

async function _fetchWeaponMastery(roundId, playerGuid) {
    const rid = coerceRoundId(roundId);
    if (!rid || !playerGuid) return null;
    const cacheKey = `${rid}:${playerGuid}`;
    if (_playerWeaponCache.has(cacheKey)) return _playerWeaponCache.get(cacheKey);
    const payload = await fetchJSON(`${API_BASE}/rounds/${rid}/player/${encodeURIComponent(playerGuid)}/details`);
    _playerWeaponCache.set(cacheKey, payload);
    return payload;
}

async function _fetchSessionWeaponMastery(playerGuid) {
    if (!playerGuid || (!_sessionId && !_sessionDate)) return null;
    const scopeKey = _sessionId ? `session:${_sessionId}` : `date:${_sessionDate}`;
    const cacheKey = `${scopeKey}:${playerGuid}`;
    if (_playerWeaponCache.has(cacheKey)) return _playerWeaponCache.get(cacheKey);

    const params = new URLSearchParams({
        player_guid: playerGuid,
        player_limit: '1',
        weapon_limit: '8',
    });
    if (_sessionId) params.set('gaming_session_id', String(_sessionId));
    else if (_sessionDate) params.set('session_date', _sessionDate);

    const payload = await fetchJSON(`${API_BASE}/stats/weapons/by-player?${params.toString()}`);
    const player = Array.isArray(payload?.players) ? payload.players[0] : null;
    const normalized = {
        scope: {
            type: 'session',
            label: _roundScopeLabel(),
        },
        player_guid: playerGuid,
        player_name: player?.player_name || null,
        total_kills: num(player?.total_kills),
        weapons: Array.isArray(player?.weapons) ? player.weapons : [],
    };
    _playerWeaponCache.set(cacheKey, normalized);
    return normalized;
}

function _findTradePlayerStats(rows, playerName, playerGuid) {
    const normalizedTarget = _normalizeLookupName(playerName);
    return (rows || []).find(row => (
        (playerGuid && row.guid === playerGuid)
        || _normalizeLookupName(row.name) === normalizedTarget
    )) || null;
}

export async function sdTogglePlayerPanel(playerName, playerGuidOrPanelId, panelIdMaybe) {
    let playerGuid = playerGuidOrPanelId;
    let panelId = panelIdMaybe;
    if (panelIdMaybe == null) {
        panelId = playerGuidOrPanelId;
        playerGuid = '';
    }
    const panelRow = document.getElementById(panelId);
    if (!panelRow) return;

    if (!panelRow.classList.contains('hidden')) {
        _destroyPlayerPanelChart(panelId);
        panelRow.classList.add('hidden');
        return;
    }
    panelRow.classList.remove('hidden');

    const panelKey = _playerPanelKey(playerName, playerGuid);
    if (_playerPanels[panelKey]?.loaded) {
        _renderPlayerPanelContent(panelKey, panelId);
        return;
    }

    const td = panelRow.querySelector('td');
    if (td) {
        td.innerHTML = '<div class="text-slate-500 text-xs text-center py-4"><i data-lucide="loader" class="w-4 h-4 animate-spin inline-block mr-2"></i>Loading details...</div>';
    }
    if (typeof lucide !== 'undefined') lucide.createIcons();

    try {
        const detailsPromises = [
            _getTradePlayerStatsForCurrentScope(),
            _getSessionGraphData(),
            (playerGuid)
                ? (_activeRoundId
                    ? _fetchWeaponMastery(_activeRoundId, playerGuid)
                    : _fetchSessionWeaponMastery(playerGuid))
                : Promise.resolve(null),
            (playerGuid)
                ? fetchJSON(`${API_BASE}/player/${encodeURIComponent(playerGuid)}/vs-stats?scope=${_activeRoundId ? 'round' : 'session'}${_activeRoundId ? `&round_id=${_activeRoundId}` : (_sessionId ? `&session_id=${_sessionId}` : '')}&limit=5`)
                : Promise.resolve(null),
        ];
        const detailsLabels = ['playerStats', 'graph', 'weapon', 'vsStats'];
        const [playerStatsResult, graphResult, weaponResult, vsStatsResult] = await Promise.allSettled(detailsPromises);
        [playerStatsResult, graphResult, weaponResult, vsStatsResult].forEach((result, i) => {
            if (result.status === 'rejected') {
                console.error(`Player detail fetch "${detailsLabels[i]}" failed:`, result.reason);
            }
        });

        const playerStatsRows = playerStatsResult.status === 'fulfilled'
            ? (playerStatsResult.value.players || [])
            : [];
        const playerTradeStats = _findTradePlayerStats(playerStatsRows, playerName, playerGuid);
        const weaponPayload = weaponResult.status === 'fulfilled' ? weaponResult.value : null;

        const graphPayload = graphResult.status === 'fulfilled' ? graphResult.value : null;
        const playstyleRows = Array.isArray(graphPayload?.players) ? graphPayload.players : [];
        const playstyleEntry = playstyleRows.find(player => (
            (playerGuid && (player.guid === playerGuid || player.player_guid === playerGuid))
            || _normalizeLookupName(player.name) === _normalizeLookupName(playerName)
        ));

        _playerPanels[panelKey] = {
            loaded: true,
            playerName,
            playerGuid: playerGuid || null,
            asVictim: playerTradeStats ? {
                opps: playerTradeStats.trade_opps || 0,
                attempts: playerTradeStats.trade_attempts || 0,
                success: playerTradeStats.trade_success || 0,
                missed: playerTradeStats.trade_missed || 0,
                isolation_deaths: playerTradeStats.isolation_deaths || 0,
            } : { opps: 0, attempts: 0, success: 0, missed: 0, isolation_deaths: 0 },
            asAvenger: playerTradeStats ? {
                avenged: playerTradeStats.avenged_count || 0,
                attempt_events: playerTradeStats.avenger_attempt_events || 0,
                attempt_damage: playerTradeStats.avenger_attempt_damage || 0,
            } : { avenged: 0, attempt_events: 0, attempt_damage: 0 },
            playstyle: playstyleEntry?.playstyle || null,
            advancedMetrics: playstyleEntry?.advanced_metrics || null,
            timeline: Array.isArray(playstyleEntry?.dpm_timeline) ? playstyleEntry.dpm_timeline : [],
            weaponPayload,
            weaponError: weaponResult.status === 'rejected' ? weaponResult.reason : null,
            vsStats: vsStatsResult.status === 'fulfilled' ? vsStatsResult.value : null,
        };

        _renderPlayerPanelContent(panelKey, panelId);
    } catch (e) {
        const td2 = panelRow.querySelector('td');
        if (td2) td2.innerHTML = '<div class="text-red-500 text-xs text-center py-4">Failed to load player details</div>';
    }
}

function _buildVsStatsHtml(vsStats) {
    if (!vsStats) return '';
    const preys = Array.isArray(vsStats.easiest_preys) ? vsStats.easiest_preys : [];
    const enemies = Array.isArray(vsStats.worst_enemies) ? vsStats.worst_enemies : [];
    if (!preys.length && !enemies.length) return '';

    function renderList(entries) {
        if (!entries.length) return '<div class="text-slate-600 text-xs py-2">No data</div>';
        return entries.map((e, i) => {
            const name = escapeHtml(e.opponent_name || 'Unknown');
            const profileHash = `#/profile/${encodeURIComponent(e.opponent_name || '')}`;
            return `
                <div class="flex items-center justify-between rounded-lg bg-slate-900/50 px-3 py-2 text-xs">
                    <div class="flex items-center gap-2 min-w-0">
                        <span class="text-slate-600 font-mono w-4">${i + 1}</span>
                        <a href="${profileHash}" class="text-white font-semibold truncate hover:text-brand-cyan transition">${name}</a>
                    </div>
                    <div class="flex items-center gap-3 shrink-0 font-mono">
                        <span class="text-brand-emerald">${num(e.kills)}K</span>
                        <span class="text-brand-rose">${num(e.deaths)}D</span>
                        <span class="text-slate-400">${num(e.kd).toFixed(1)}</span>
                    </div>
                </div>`;
        }).join('');
    }

    return `
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4">
            <div>
                <div class="flex items-center gap-2 mb-2">
                    <i data-lucide="crosshair" class="w-4 h-4 text-brand-emerald"></i>
                    <span class="text-xs font-bold text-slate-400 uppercase">Easiest Preys</span>
                </div>
                <div class="space-y-1">${renderList(preys)}</div>
            </div>
            <div>
                <div class="flex items-center gap-2 mb-2">
                    <i data-lucide="skull" class="w-4 h-4 text-brand-rose"></i>
                    <span class="text-xs font-bold text-slate-400 uppercase">Worst Enemies</span>
                </div>
                <div class="space-y-1">${renderList(enemies)}</div>
            </div>
        </div>`;
}

function _renderPlayerPanelContent(playerKey, panelId) {
    const row = document.getElementById(panelId);
    if (!row) return;
    const td = row.querySelector('td');
    if (!td) return;

    const data = _playerPanels[playerKey];
    if (!data) return;

    const noTradeData = !data.asVictim.opps && !data.asAvenger.avenged;
    const timelineId = `sd-player-timeline-${panelId}`;
    const weapons = Array.isArray(data.weaponPayload?.weapons) ? data.weaponPayload.weapons : [];
    const weaponRows = weapons.map(weapon => {
        const name = escapeHtml((weapon.name || weapon.weapon_name || 'Unknown').replace(/^WS_/, '').replace(/_/g, ' '));
        const kills = num(weapon.kills);
        const deaths = num(weapon.deaths);
        const headshots = num(weapon.headshots);
        const accuracy = num(weapon.accuracy).toFixed(1);
        const hits = num(weapon.hits);
        const shots = num(weapon.shots);
        const accClass = num(weapon.accuracy) >= 30 ? 'text-brand-emerald' : 'text-slate-300';
        return `
            <tr class="border-b border-white/5">
                <td class="py-1.5 px-2 text-slate-300">${name}</td>
                <td class="py-1.5 px-2 text-right font-mono text-white">${kills}</td>
                <td class="py-1.5 px-2 text-right font-mono text-slate-400">${deaths}</td>
                <td class="py-1.5 px-2 text-right font-mono text-brand-rose">${headshots}</td>
                <td class="py-1.5 px-2 text-right font-mono ${accClass}">${accuracy}%</td>
                <td class="py-1.5 px-2 text-right font-mono text-slate-400">${hits}/${shots}</td>
            </tr>`;
    }).join('');

    const roundLabel = data.weaponPayload?.round
        ? `${mapLabel(data.weaponPayload.round.map_name || 'Unknown')} / R${data.weaponPayload.round.round_number || '?'}`
        : null;
    const weaponScopeLabel = roundLabel || data.weaponPayload?.scope?.label || null;
    const sessionAdv = data.advancedMetrics || {};
    const profileMeta = [
        { label: 'Aggro', value: num(data.playstyle?.aggression, Number.NaN), tone: 'text-brand-amber' },
        { label: 'Pressure', value: num(sessionAdv.pressure_score, Number.NaN), tone: 'text-brand-cyan' },
        { label: 'Discipline', value: num(sessionAdv.discipline_score, Number.NaN), tone: 'text-brand-emerald' },
        { label: 'Empty Death', value: num(sessionAdv.empty_death_burden, Number.NaN), tone: 'text-brand-rose' },
    ].filter(metric => Number.isFinite(metric.value));
    const profileMetaChips = profileMeta.map(metric => `
        <span class="px-2 py-1 rounded-full border border-white/10 bg-white/5 ${metric.tone}">
            ${metric.label} ${metric.value.toFixed(0)}
        </span>`).join('');
    const profileMetrics = [
        { label: 'Aggression', value: num(data.playstyle?.aggression) },
        { label: 'Precision', value: num(data.playstyle?.precision) },
        { label: 'Survivability', value: num(data.playstyle?.survivability) },
        { label: 'Support', value: num(data.playstyle?.support) },
        { label: 'Lethality', value: num(data.playstyle?.lethality) },
        { label: 'Brutality', value: num(data.playstyle?.brutality) },
    ];
    const profileRows = profileMetrics.map(metric => `
        <div>
            <div class="flex items-center justify-between gap-2 text-[11px] mb-1">
                <span class="text-slate-400">${metric.label}</span>
                <span class="font-mono text-white">${metric.value.toFixed(0)}</span>
            </div>
            <div class="h-2 rounded-full bg-slate-900/80 overflow-hidden">
                <div class="h-full rounded-full bg-gradient-to-r from-brand-blue via-brand-cyan to-brand-emerald"
                    style="width:${Math.min(100, metric.value)}%"></div>
            </div>
        </div>`).join('');
    const timeline = Array.isArray(data.timeline) ? data.timeline : [];
    const timelinePeak = timeline.length ? Math.max(...timeline.map(point => num(point.dpm))) : null;
    const timelineAvg = timeline.length
        ? timeline.reduce((sum, point) => sum + num(point.dpm), 0) / timeline.length
        : null;

    td.innerHTML = `
        <div class="grid grid-cols-1 xl:grid-cols-3 gap-4">
            <div class="xl:col-span-1">
                <div class="text-xs font-bold text-slate-400 uppercase mb-2">Trade Detail</div>
                ${noTradeData ? '<div class="text-slate-600 text-xs">No trade data for this scope</div>' : `
                <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center mb-3">
                    <div class="glass-card rounded p-2">
                        <div class="text-[10px] text-slate-500">Opps</div>
                        <div class="text-lg font-black text-white">${data.asVictim.opps}</div>
                    </div>
                    <div class="glass-card rounded p-2">
                        <div class="text-[10px] text-slate-500">Attempts</div>
                        <div class="text-lg font-black text-slate-300">${data.asVictim.attempts}</div>
                    </div>
                    <div class="glass-card rounded p-2">
                        <div class="text-[10px] text-slate-500">Success</div>
                        <div class="text-lg font-black text-brand-emerald">${data.asVictim.success}</div>
                    </div>
                    <div class="glass-card rounded p-2">
                        <div class="text-[10px] text-slate-500">Missed</div>
                        <div class="text-lg font-black text-brand-rose">${data.asVictim.missed}</div>
                    </div>
                </div>
                <div class="grid grid-cols-2 sm:grid-cols-3 gap-2 text-center">
                    <div class="glass-card rounded p-2">
                        <div class="text-[10px] text-slate-500">Avenged</div>
                        <div class="text-lg font-black text-brand-emerald">${data.asAvenger.avenged}</div>
                    </div>
                    <div class="glass-card rounded p-2">
                        <div class="text-[10px] text-slate-500">Attempts</div>
                        <div class="text-lg font-black text-slate-300">${data.asAvenger.attempt_events}</div>
                    </div>
                    <div class="glass-card rounded p-2">
                        <div class="text-[10px] text-slate-500">Dmg Dealt</div>
                        <div class="text-lg font-black text-amber-300">${data.asAvenger.attempt_damage}</div>
                    </div>
                </div>`}
            </div>
            <div class="xl:col-span-1">
                <div class="text-xs font-bold text-slate-400 uppercase mb-2">Session Profile</div>
                ${data.playstyle ? `
                    ${profileMetaChips ? `<div class="flex flex-wrap gap-2 text-[10px] mb-3">${profileMetaChips}</div>` : ''}
                    <div class="text-[11px] text-slate-500 mb-3">Stopwatch trait mix. Aggression rewards productive pressure, denied time, and useful kills, while punishing empty deaths.</div>
                    <div class="space-y-2 mb-4">${profileRows}</div>
                    ${timeline.length ? `
                        <div class="flex flex-wrap items-center gap-2 text-[10px] text-slate-500 mb-2">
                            <span class="px-2 py-1 rounded bg-white/5 border border-white/10">Peak ${num(timelinePeak).toFixed(1)} DPM</span>
                            <span class="px-2 py-1 rounded bg-white/5 border border-white/10">Avg ${num(timelineAvg).toFixed(1)} DPM</span>
                        </div>
                        <div style="height:140px;position:relative"><canvas id="${timelineId}"></canvas></div>`
                    : '<div class="text-slate-600 text-xs">No DPM timeline data</div>'}
                ` : '<div class="text-slate-600 text-xs">No playstyle data</div>'}
            </div>
            <div class="xl:col-span-1">
                <div class="text-xs font-bold text-slate-400 uppercase mb-2">Weapon Mastery ${weaponScopeLabel ? `<span class="normal-case text-slate-500">(${escapeHtml(weaponScopeLabel)})</span>` : ''}</div>
                ${data.weaponError ? `<div class="text-amber-400 text-xs">Weapon details unavailable for this player${_activeRoundId ? '/round' : '/session'}.</div>` : ''}
                ${!data.weaponError && !weapons.length
        ? `<div class="text-slate-600 text-xs">${_activeRoundId ? 'Select a scoped round and player with GUID to load weapon mastery.' : 'No session-scoped weapon mastery data for this player.'}</div>`
        : `
                    <div class="overflow-x-auto rounded-lg border border-white/10">
                        <table class="w-full text-xs">
                            <thead>
                                <tr class="border-b border-white/10 text-slate-400 bg-slate-900/60">
                                    <th class="text-left py-1.5 px-2">Weapon</th>
                                    <th class="text-right py-1.5 px-2">K</th>
                                    <th class="text-right py-1.5 px-2">D</th>
                                    <th class="text-right py-1.5 px-2">HS</th>
                                    <th class="text-right py-1.5 px-2">ACC</th>
                                    <th class="text-right py-1.5 px-2">Hits/Shots</th>
                                </tr>
                            </thead>
                            <tbody>${weaponRows}</tbody>
                        </table>
                    </div>`}
            </div>
        </div>
        ${_buildVsStatsHtml(data.vsStats)}`;

    _destroyPlayerPanelChart(panelId);
    if (timeline.length && typeof Chart !== 'undefined') {
        const canvas = document.getElementById(timelineId);
        if (canvas) {
            const chart = new Chart(canvas.getContext('2d'), {
                type: 'line',
                data: {
                    labels: timeline.map(point => point.label || ''),
                    datasets: [{
                        label: data.playerName,
                        data: timeline.map(point => num(point.dpm)),
                        backgroundColor: 'rgba(56, 189, 248, 0.14)',
                        borderColor: 'rgba(56, 189, 248, 0.95)',
                        borderWidth: 2,
                        pointRadius: 2,
                        pointHoverRadius: 4,
                        tension: 0.28,
                        fill: true,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: {
                            ticks: {
                                color: '#64748b',
                                autoSkip: true,
                                maxRotation: 0,
                                font: { size: 9 },
                            },
                            grid: { color: 'rgba(30, 41, 59, 0.7)' },
                        },
                        y: {
                            ticks: { color: '#94a3b8', font: { size: 10 } },
                            grid: { color: 'rgba(30, 41, 59, 0.7)' },
                            title: { display: true, text: 'DPM', color: '#64748b' },
                        },
                    },
                },
            });
            _playerPanelCharts.set(panelId, chart);
        }
    }
    if (typeof lucide !== 'undefined') lucide.createIcons();
}

// ============================================================
// SIGNALS TAB
// ============================================================

async function _loadSignalsTab() {
    const scopeKey = _activeRoundId ? _activeRoundId : 'session';
    if (_signalsLoaded === scopeKey) return;

    const panel = document.getElementById('sd-tab-teamplay');
    if (!panel) return;
    const requestToken = ++_signalsRequestToken;

    panel.innerHTML = `
        <div class="text-center py-12">
            <i data-lucide="loader" class="w-8 h-8 text-brand-cyan animate-spin mx-auto mb-4"></i>
            <div class="text-slate-400">Loading proximity signals...</div>
        </div>`;
    if (typeof lucide !== 'undefined') lucide.createIcons();

    const baseDate = _activeRoundSessionDate || _sessionDate;
    const scopeQuery = new URLSearchParams();
    if (baseDate) scopeQuery.set('session_date', baseDate);
    if (_activeRoundId && _activeRoundStartUnix) {
        scopeQuery.set('round_start_unix', String(_activeRoundStartUnix));
    }
    const scopeParams = scopeQuery.toString();
    const withScope = (path) => scopeParams ? `${path}?${scopeParams}` : path;
    const eventsScope = new URLSearchParams(scopeParams);
    eventsScope.set('limit', '250');

    const teamplayLabels = ['tradesSummary', 'tradesEvents', 'duos', 'teamplay', 'movers'];
    const [tradesSummary, tradesEvents, duos, teamplay, movers] = await Promise.allSettled([
        fetchJSON(withScope(`${API_BASE}/proximity/trades/summary`)),
        fetchJSON(`${API_BASE}/proximity/trades/events?${eventsScope.toString()}`),
        fetchJSON(`${withScope(`${API_BASE}/proximity/duos`)}${scopeParams ? '&' : '?'}limit=8`),
        fetchJSON(withScope(`${API_BASE}/proximity/teamplay`)),
        fetchJSON(`${withScope(`${API_BASE}/proximity/movers`)}${scopeParams ? '&' : '?'}limit=5`),
    ]);
    [tradesSummary, tradesEvents, duos, teamplay, movers].forEach((result, i) => {
        if (result.status === 'rejected') {
            console.error(`Teamplay fetch "${teamplayLabels[i]}" failed:`, result.reason);
        }
    });
    if (requestToken !== _signalsRequestToken) return;
    if (_activeTab !== 'teamplay') return;
    if (((_activeRoundId ? _activeRoundId : 'session')) !== scopeKey) return;

    const get = (settled, fb) => settled.status === 'fulfilled' ? settled.value : fb;
    const ts = get(tradesSummary, {});
    const te = get(tradesEvents, {});
    const du = get(duos, {});
    const tp = get(teamplay, {});
    const mv = get(movers, {});

    const events = te.events || [];
    const playerTradeMap = {};
    events.forEach(e => {
        if (e.victim) {
            if (!playerTradeMap[e.victim]) playerTradeMap[e.victim] = { opps: 0, attempts: 0, success: 0, missed: 0 };
            playerTradeMap[e.victim].opps += e.opportunities || 0;
            playerTradeMap[e.victim].attempts += e.attempts || 0;
            playerTradeMap[e.victim].success += e.success || 0;
            playerTradeMap[e.victim].missed += e.missed || 0;
        }
    });
    const playerTradeRows = Object.entries(playerTradeMap)
        .sort((a, b) => b[1].opps - a[1].opps)
        .map(([name, d]) => {
            const rate = d.opps > 0 ? Math.min(100, Math.round(d.success / d.opps * 100)) : 0;
            return `
                <tr class="border-b border-white/5 hover:bg-white/5">
                    <td class="px-3 py-2 text-sm font-semibold text-white">${escapeHtml(name)}</td>
                    <td class="px-2 py-2 text-sm font-mono text-slate-300 text-right">${d.opps}</td>
                    <td class="px-2 py-2 text-sm font-mono text-slate-300 text-right">${d.attempts}</td>
                    <td class="px-2 py-2 text-sm font-mono text-brand-emerald text-right">${d.success}</td>
                    <td class="px-2 py-2 text-sm font-mono text-brand-rose text-right">${d.missed}</td>
                    <td class="px-2 py-2 text-sm font-mono text-white font-bold text-right">${rate}%</td>
                </tr>`;
        }).join('');

    const duoCards = (du.duos || []).map((duo, i) => {
        const p1 = escapeHtml(duo.player1_name || duo.player1 || '?');
        const p2 = escapeHtml(duo.player2_name || duo.player2 || '?');
        const crossfires = duo.crossfire_kills ?? duo.crossfires ?? 0;
        const delay = duo.avg_delay_ms ? `${Math.round(duo.avg_delay_ms)}ms` : '—';
        return `
            <div class="glass-card rounded-lg p-4">
                <div class="flex items-center gap-2 mb-2">
                    <span class="font-black ${i === 0 ? 'text-brand-gold' : i === 1 ? 'text-slate-300' : 'text-amber-600'}">#${i + 1}</span>
                    <span class="font-bold text-white">${p1} + ${p2}</span>
                </div>
                <div class="flex gap-4 text-xs text-slate-400 flex-wrap">
                    <span>Crossfires: <strong class="text-white">${crossfires}</strong></span>
                    <span>Avg Delay: <strong class="text-white">${delay}</strong></span>
                </div>
            </div>`;
    }).join('') || '<div class="text-slate-600 text-sm col-span-2">No duo data for this scope</div>';

    const stripColors = (t) => t ? String(t).replace(/\^[0-9A-Za-z]/g, '') : '?';
    const makeTeamplayTable = (rows, label, valueKey, unit) => {
        if (!rows || !rows.length) return `<div class="text-slate-600 text-xs">No ${label} data</div>`;
        return `<table class="w-full text-sm"><thead><tr class="text-xs text-slate-500 border-b border-white/5">
            <th class="py-1 text-left">Player</th><th class="py-1 text-right">${escapeHtml(label)}</th>
        </tr></thead><tbody>
        ${rows.map(r => {
            const val = r[valueKey] ?? r.count ?? r.value ?? 0;
            const display = unit ? Number(val).toFixed(1) + unit : val;
            return `<tr class="border-b border-white/5 hover:bg-white/5">
            <td class="py-1.5 text-white font-semibold">${escapeHtml(stripColors(r.name))}</td>
            <td class="py-1.5 text-right font-mono text-brand-cyan">${display}</td>
        </tr>`;
        }).join('')}
        </tbody></table>`;
    };

    const makeMoversCard = (rows, valueKey, unit) => {
        if (!rows || !rows.length) return `<div class="text-slate-600 text-xs">No data</div>`;
        return rows.map(r => `
            <div class="flex items-center justify-between py-2 border-b border-white/5 last:border-0">
                <span class="text-sm text-white font-semibold">${escapeHtml(stripColors(r.name))}</span>
                <span class="text-sm font-mono text-brand-cyan">${r[valueKey] != null ? Number(r[valueKey]).toFixed(1) + unit : '—'}</span>
            </div>`).join('');
    };

    panel.innerHTML = `
        <div class="glass-panel rounded-xl p-3 mb-6 flex items-center gap-3">
            <i data-lucide="radar" class="w-4 h-4 text-brand-cyan"></i>
            <span class="text-sm text-slate-300">
                Scope: <strong class="text-white">${_activeRoundId ? `Round ${_activeRoundId}` : 'Full Session'}</strong>
            </span>
            ${_activeRoundId ? `<button onclick="sdClearRoundScope()" class="ml-auto text-xs text-slate-400 hover:text-white transition">✕ Clear scope</button>` : ''}
        </div>

        ${ts.ready ? `
        <div class="glass-panel rounded-xl p-5 mb-6">
            <h3 class="font-bold text-white mb-4 flex items-center gap-2">
                <i data-lucide="zap" class="w-5 h-5 text-brand-amber"></i> Trade Summary
            </h3>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
                <div class="glass-card rounded-lg p-3">
                    <div class="text-xs text-slate-500 uppercase">Opportunities</div>
                    <div class="text-2xl font-black text-white">${ts.trade_opportunities ?? 0}</div>
                </div>
                <div class="glass-card rounded-lg p-3">
                    <div class="text-xs text-slate-500 uppercase">Successes</div>
                    <div class="text-2xl font-black text-brand-emerald">${ts.trade_success ?? 0}</div>
                </div>
                <div class="glass-card rounded-lg p-3">
                    <div class="text-xs text-slate-500 uppercase">Missed</div>
                    <div class="text-2xl font-black text-brand-rose">${ts.missed_trade_candidates ?? 0}</div>
                </div>
                <div class="glass-card rounded-lg p-3">
                    <div class="text-xs text-slate-500 uppercase">Isolation Deaths</div>
                    <div class="text-2xl font-black text-brand-amber">${ts.isolation_deaths ?? 0}</div>
                </div>
            </div>
        </div>` : ''}

        ${playerTradeRows ? `
        <div class="glass-panel rounded-xl p-5 mb-6">
            <h3 class="font-bold text-white mb-4 flex items-center gap-2">
                <i data-lucide="table" class="w-5 h-5 text-brand-cyan"></i> Per-Player Trade Stats
            </h3>
            <div class="overflow-x-auto">
                <table class="w-full text-left">
                    <thead><tr class="text-xs text-slate-400 uppercase border-b border-white/10 bg-white/5">
                        <th class="px-3 py-2">Player</th>
                        <th class="px-2 py-2 text-right">Opps</th>
                        <th class="px-2 py-2 text-right">Attempts</th>
                        <th class="px-2 py-2 text-right text-brand-emerald">Success</th>
                        <th class="px-2 py-2 text-right text-brand-rose">Missed</th>
                        <th class="px-2 py-2 text-right">Rate</th>
                    </tr></thead>
                    <tbody>${playerTradeRows}</tbody>
                </table>
            </div>
        </div>` : ''}

        <div class="glass-panel rounded-xl p-5 mb-6">
            <h3 class="font-bold text-white mb-4 flex items-center gap-2">
                <i data-lucide="users" class="w-5 h-5 text-brand-purple"></i> Top Synergy Duos
            </h3>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">${duoCards}</div>
        </div>

        ${tp.ready ? `
        <div class="glass-panel rounded-xl p-5 mb-6">
            <h3 class="font-bold text-white mb-4 flex items-center gap-2">
                <i data-lucide="shield" class="w-5 h-5 text-brand-blue"></i> Teamplay Signals
            </h3>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div><div class="text-xs text-slate-500 uppercase font-bold mb-2">Crossfire Kills</div>
                    <div class="text-xs text-slate-600 mb-2">Kills assisted by nearby teammates</div>
                    ${makeTeamplayTable(tp.crossfire_kills, 'Kills', 'crossfire_kills')}</div>
                <div><div class="text-xs text-slate-500 uppercase font-bold mb-2">Team Sync</div>
                    <div class="text-xs text-slate-600 mb-2">Coordinated actions with team</div>
                    ${makeTeamplayTable(tp.sync, 'Participations', 'crossfire_participations')}</div>
                <div><div class="text-xs text-slate-500 uppercase font-bold mb-2">Focus Survival</div>
                    <div class="text-xs text-slate-600 mb-2">Survived being targeted by multiple enemies</div>
                    ${makeTeamplayTable(tp.focus_survival, 'Survival %', 'survival_rate_pct', '%')}</div>
            </div>
        </div>` : ''}

        ${mv.ready ? `
        <div class="glass-panel rounded-xl p-5 mb-6">
            <h3 class="font-bold text-white mb-4 flex items-center gap-2">
                <i data-lucide="activity" class="w-5 h-5 text-brand-emerald"></i> Movement Leaders
            </h3>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div><div class="text-xs text-slate-500 uppercase font-bold mb-2">Total Distance Covered</div>
                    <div class="text-xs text-slate-600 mb-2">Total map units traveled during the session</div>
                    ${makeMoversCard(mv.distance, 'total_distance', 'u')}</div>
                <div><div class="text-xs text-slate-500 uppercase font-bold mb-2">Sprint Time Ratio</div>
                    <div class="text-xs text-slate-600 mb-2">% of movement time spent sprinting</div>
                    ${makeMoversCard(mv.sprint, 'sprint_pct', '%')}</div>
            </div>
        </div>` : ''}
    `;

    if (requestToken !== _signalsRequestToken) return;
    if (_activeTab !== 'teamplay') return;
    if (((_activeRoundId ? _activeRoundId : 'session')) !== scopeKey) return;
    _signalsLoaded = scopeKey;
    if (typeof lucide !== 'undefined') lucide.createIcons();
}

// ============================================================
// VIZ TAB — SESSION GRAPHS (whole session, no round selected)
// ============================================================

async function _renderSessionGraphs(panel, requestToken) {
    const requestedSessionDate = _sessionDate;
    const requestedSessionId = _sessionId;
    if (!requestedSessionDate || !requestedSessionId) {
        panel.innerHTML = '<div class="text-center text-slate-500 py-12">No session context available.</div>';
        return;
    }

    panel.innerHTML = `
        <div class="text-center py-12">
            <i data-lucide="loader" class="w-8 h-8 text-brand-purple animate-spin mx-auto mb-4"></i>
            <div class="text-slate-400">Loading session graphs…</div>
        </div>`;
    if (typeof lucide !== 'undefined') lucide.createIcons();

    try {
        const [graphPayload, tradePayload] = await Promise.all([
            _getSessionGraphData(),
            _getTradePlayerStatsForCurrentScope().catch(() => null),
        ]);
        const data = graphPayload;
        if (requestToken !== _vizRequestToken || _activeTab !== 'charts' || _activeRoundId) return;
        if (!data || !data.players || data.players.length === 0) {
            panel.innerHTML = '<div class="text-center text-slate-500 py-12">No graph data for this session.</div>';
            return;
        }

        const players = Array.isArray(data.players) ? data.players : [];
        const tradeRows = Array.isArray(tradePayload?.players) ? tradePayload.players : [];
        const timelinePlayers = players.filter(p => Array.isArray(p?.dpm_timeline) && p.dpm_timeline.length > 0);
        const roundLabels = timelinePlayers.length
            ? timelinePlayers[0].dpm_timeline.map(t => t?.label || '')
            : [];
        const COLORS = [
            '#6366f1','#f59e0b','#10b981','#ef4444','#3b82f6',
            '#a855f7','#14b8a6','#f97316','#84cc16','#ec4899',
            '#06b6d4','#eab308','#8b5cf6','#22d3ee','#fb7185'
        ];

        // ── Build HTML skeleton ──────────────────────────────────────────────
        panel.innerHTML = `
            <div class="glass-panel rounded-xl p-3 mb-6 flex items-center gap-3">
                <i data-lucide="chart-line" class="w-4 h-4 text-brand-purple"></i>
                <span class="text-sm text-slate-300">
                    <strong class="text-white">Full Session Overview</strong>
                    — ${players.length} players · ${roundLabels.length} rounds
                </span>
                <button onclick="sdClearRoundScope(); sdSwitchTab('summary')"
                    class="ml-auto text-xs text-slate-400 hover:text-white transition">
                    Select a round →
                </button>
            </div>

            <!-- DPM Timeline -->
            <div class="glass-card rounded-xl p-5 mb-6">
                <h3 class="text-sm font-bold text-white mb-4 flex items-center gap-2">
                    <i data-lucide="trending-up" class="w-4 h-4 text-brand-purple"></i>
                    DPM Timeline — All Rounds
                </h3>
                ${roundLabels.length > 0
        ? '<div style="height:320px"><canvas id="sg-dpm-timeline"></canvas></div>'
        : '<div class="text-xs text-slate-500 py-10 text-center">Timeline data unavailable for this session.</div>'}
            </div>

            <div class="glass-card rounded-xl p-5 mb-6">
                <h3 class="text-sm font-bold text-white mb-4 flex items-center gap-2">
                    <i data-lucide="crosshair" class="w-4 h-4 text-brand-amber"></i>
                    Aggression Map
                </h3>
                <div class="text-xs text-slate-500 mb-4">Right side means more productive pressure. Higher means the pressure cost the team less. Bubble size tracks trade involvement.</div>
                <div style="height:320px"><canvas id="sg-aggression-map"></canvas></div>
            </div>

            <!-- Per-player playstyle radars + stats cards -->
            <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6 mb-6" id="sg-player-cards"></div>

            <!-- Combat summary table -->
            <div class="glass-card rounded-xl p-5">
                <h3 class="text-sm font-bold text-white mb-4 flex items-center gap-2">
                    <i data-lucide="swords" class="w-4 h-4 text-red-400"></i>
                    Session Combat Summary
                </h3>
                <div class="overflow-x-auto">
                    <table class="w-full text-xs font-mono" id="sg-summary-table">
                        <thead>
                            <tr class="text-left text-slate-400 border-b border-white/10">
                                <th class="px-3 py-2">Player</th>
                                <th class="px-3 py-2 text-right">K</th>
                                <th class="px-3 py-2 text-right">D</th>
                                <th class="px-3 py-2 text-right">K/D</th>
                                <th class="px-3 py-2 text-right">Dmg</th>
                                <th class="px-3 py-2 text-right">DPM</th>
                                <th class="px-3 py-2 text-right">FP</th>
                                <th class="px-3 py-2 text-right">Aggro</th>
                                <th class="px-3 py-2 text-right">Discipline</th>
                                <th class="px-3 py-2 text-right">Survive%</th>
                                <th class="px-3 py-2 text-right">Precision%</th>
                            </tr>
                        </thead>
                        <tbody id="sg-summary-tbody"></tbody>
                    </table>
                </div>
            </div>`;

        if (typeof lucide !== 'undefined') lucide.createIcons();

        // ── DPM Timeline Chart ──────────────────────────────────────────────
        const dpmCtx = document.getElementById('sg-dpm-timeline');
        if (roundLabels.length > 0 && dpmCtx && typeof Chart !== 'undefined') {
            const dpmChart = new Chart(dpmCtx.getContext('2d'), {
                type: 'line',
                data: {
                    labels: roundLabels,
                    datasets: timelinePlayers.map((p, i) => ({
                        label: p.name,
                        data: (p.dpm_timeline || []).map(t => t?.dpm ?? 0),
                        borderColor: COLORS[i % COLORS.length],
                        backgroundColor: COLORS[i % COLORS.length] + '20',
                        borderWidth: 2,
                        pointRadius: 4,
                        tension: 0.3,
                        fill: false
                    }))
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: {
                        legend: { labels: { color: '#cbd5e1', font: { size: 11 } } },
                        tooltip: { mode: 'index', intersect: false }
                    },
                    scales: {
                        x: { ticks: { color: '#94a3b8', font: { size: 10 } }, grid: { color: '#1e293b' } },
                        y: { ticks: { color: '#94a3b8' }, grid: { color: '#1e293b' }, title: { display: true, text: 'DPM', color: '#64748b' } }
                    }
                }
            });
            _sdCharts.push(dpmChart);
        }

        const aggressionCanvas = document.getElementById('sg-aggression-map');
        if (aggressionCanvas && typeof Chart !== 'undefined') {
            const tradeLoads = players.map(player => {
                const trade = _findTradePlayerStats(tradeRows, player.name, player.player_guid || player.guid);
                return (trade?.trade_success || 0) + (trade?.avenged_count || 0);
            });
            const maxTradeLoad = Math.max(...tradeLoads, 1);
            const aggressionBackdrop = {
                id: 'aggressionBackdrop',
                beforeDraw(chart) {
                    const { ctx, chartArea, scales } = chart;
                    if (!chartArea || !scales?.x || !scales?.y) return;
                    const { left, right, top, bottom } = chartArea;
                    const midX = scales.x.getPixelForValue(50);
                    const midY = scales.y.getPixelForValue(50);
                    ctx.save();
                    ctx.fillStyle = 'rgba(15, 23, 42, 0.72)';
                    ctx.fillRect(left, top, right - left, bottom - top);
                    ctx.fillStyle = 'rgba(16, 185, 129, 0.08)';
                    ctx.fillRect(midX, top, right - midX, midY - top);
                    ctx.fillStyle = 'rgba(245, 158, 11, 0.08)';
                    ctx.fillRect(midX, midY, right - midX, bottom - midY);
                    ctx.fillStyle = 'rgba(59, 130, 246, 0.07)';
                    ctx.fillRect(left, top, midX - left, midY - top);
                    ctx.fillStyle = 'rgba(239, 68, 68, 0.06)';
                    ctx.fillRect(left, midY, midX - left, bottom - midY);
                    ctx.strokeStyle = 'rgba(148, 163, 184, 0.25)';
                    ctx.setLineDash([4, 4]);
                    ctx.beginPath();
                    ctx.moveTo(midX, top);
                    ctx.lineTo(midX, bottom);
                    ctx.moveTo(left, midY);
                    ctx.lineTo(right, midY);
                    ctx.stroke();
                    ctx.setLineDash([]);
                    ctx.font = '11px system-ui';
                    ctx.fillStyle = 'rgba(226, 232, 240, 0.85)';
                    ctx.fillText('Controlled Pressure', midX + 10, top + 18);
                    ctx.fillText('Measured', left + 10, top + 18);
                    ctx.fillText('Chaotic Pressure', midX + 10, bottom - 12);
                    ctx.fillText('Low Impact', left + 10, bottom - 12);
                    ctx.restore();
                },
            };

            const aggressionChart = new Chart(aggressionCanvas.getContext('2d'), {
                type: 'bubble',
                data: {
                    datasets: players.map((player, idx) => {
                        const color = COLORS[idx % COLORS.length];
                        const adv = player.advanced_metrics || {};
                        const trade = _findTradePlayerStats(tradeRows, player.name, player.player_guid || player.guid);
                        const tradeLoad = (trade?.trade_success || 0) + (trade?.avenged_count || 0);
                        const radius = 8 + ((tradeLoad / maxTradeLoad) * 12);
                        return {
                            label: player.name,
                            backgroundColor: `${color}66`,
                            borderColor: color,
                            borderWidth: 2,
                            hoverBorderWidth: 3,
                            data: [{
                                x: num(player.playstyle?.aggression),
                                y: num(adv.discipline_score, 50),
                                r: radius,
                                playerName: player.name,
                                pressure: num(adv.pressure_score),
                                emptyDeath: num(adv.empty_death_burden),
                                survival: num(adv.survival_rate),
                                fragPotential: num(adv.frag_potential),
                                tradeSuccess: trade?.trade_success || 0,
                                avenged: trade?.avenged_count || 0,
                                isolationDeaths: trade?.isolation_deaths || 0,
                            }],
                        };
                    }),
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { labels: { color: '#cbd5e1', font: { size: 11 } } },
                        tooltip: {
                            callbacks: {
                                label(ctx) {
                                    const point = ctx.raw || {};
                                    return `${point.playerName}: Aggro ${num(point.x).toFixed(1)} · Discipline ${num(point.y).toFixed(1)}`;
                                },
                                afterLabel(ctx) {
                                    const point = ctx.raw || {};
                                    return [
                                        `Pressure ${num(point.pressure).toFixed(1)} · Empty Death ${num(point.emptyDeath).toFixed(1)}`,
                                        `FP ${num(point.fragPotential).toFixed(1)} · Survive ${num(point.survival).toFixed(1)}%`,
                                        `Trade Success ${point.tradeSuccess} · Avenged ${point.avenged} · Isolation ${point.isolationDeaths}`,
                                    ];
                                },
                            },
                        },
                    },
                    scales: {
                        x: {
                            min: 0,
                            max: 100,
                            ticks: { color: '#94a3b8' },
                            grid: { color: 'rgba(30, 41, 59, 0.7)' },
                            title: { display: true, text: 'Aggression', color: '#64748b' },
                        },
                        y: {
                            min: 0,
                            max: 100,
                            ticks: { color: '#94a3b8' },
                            grid: { color: 'rgba(30, 41, 59, 0.7)' },
                            title: { display: true, text: 'Discipline', color: '#64748b' },
                        },
                    },
                },
                plugins: [aggressionBackdrop],
            });
            _sdCharts.push(aggressionChart);
        }

        // ── Per-player cards (radar + stats) ───────────────────────────────
        const cardContainer = document.getElementById('sg-player-cards');
        const RADAR_KEYS = ['aggression','precision','survivability','support','lethality','brutality'];
        const RADAR_LABELS = ['Aggression','Precision','Survivability','Support','Lethality','Brutality'];

        if (requestToken !== _vizRequestToken || _activeTab !== 'charts' || _activeRoundId) return;
        players.forEach((p, i) => {
            const color = COLORS[i % COLORS.length];
            const adv = p.advanced_metrics || {};
            const off = p.combat_offense || {};
            const ps = p.playstyle || {};

            const cardId = `sg-radar-${i}`;
            const card = document.createElement('div');
            card.className = 'glass-card rounded-xl p-5';
            card.innerHTML = `
                <div class="flex items-center gap-2 mb-3">
                    <span class="w-3 h-3 rounded-full flex-shrink-0" style="background:${color}"></span>
                    <span class="text-sm font-bold text-white truncate">${escapeHtml(p.name)}</span>
                </div>
                <div class="grid grid-cols-3 gap-2 text-center mb-4">
                    <div class="bg-white/5 rounded-lg p-2">
                        <div class="text-lg font-bold" style="color:${color}">${off.kd ?? '--'}</div>
                        <div class="text-xs text-slate-500">K/D</div>
                    </div>
                    <div class="bg-white/5 rounded-lg p-2">
                        <div class="text-lg font-bold" style="color:${color}">${off.dpm ?? '--'}</div>
                        <div class="text-xs text-slate-500">DPM</div>
                    </div>
                    <div class="bg-white/5 rounded-lg p-2">
                        <div class="text-lg font-bold" style="color:${color}">${adv.survival_rate != null ? adv.survival_rate.toFixed(1) + '%' : '--'}</div>
                        <div class="text-xs text-slate-500">Survive</div>
                    </div>
                </div>
                <div style="height:200px"><canvas id="${cardId}"></canvas></div>`;
            cardContainer.appendChild(card);

            if (typeof Chart !== 'undefined') {
                const radarCtx = document.getElementById(cardId);
                if (radarCtx) {
                    const radarChart = new Chart(radarCtx.getContext('2d'), {
                        type: 'radar',
                        data: {
                            labels: RADAR_LABELS,
                            datasets: [{
                                label: p.name,
                                data: RADAR_KEYS.map(k => ps[k] ?? 0),
                                borderColor: color,
                                backgroundColor: color + '30',
                                borderWidth: 2,
                                pointRadius: 3
                            }]
                        },
                        options: {
                            responsive: true, maintainAspectRatio: false,
                            plugins: { legend: { display: false } },
                            scales: {
                                r: {
                                    min: 0, max: 100, ticks: { display: false, stepSize: 20 },
                                    grid: { color: '#1e293b' },
                                    pointLabels: { color: '#94a3b8', font: { size: 10 } },
                                    angleLines: { color: '#1e293b' }
                                }
                            }
                        }
                    });
                    _sdCharts.push(radarChart);
                }
            }
        });

        // ── Combat summary table rows ──────────────────────────────────────
        const tbody = document.getElementById('sg-summary-tbody');
        if (tbody) {
            players.forEach((p, i) => {
                const color = COLORS[i % COLORS.length];
                const off = p.combat_offense || {};
                const adv = p.advanced_metrics || {};
                const ps = p.playstyle || {};
                const tr = document.createElement('tr');
                tr.className = 'border-b border-white/5 hover:bg-white/5 transition';
                tr.innerHTML = `
                    <td class="px-3 py-2 flex items-center gap-2">
                        <span class="w-2 h-2 rounded-full" style="background:${color}"></span>
                        <span class="text-white font-semibold">${escapeHtml(p.name)}</span>
                    </td>
                    <td class="px-3 py-2 text-right text-green-400">${off.kills ?? '--'}</td>
                    <td class="px-3 py-2 text-right text-red-400">${off.deaths ?? '--'}</td>
                    <td class="px-3 py-2 text-right text-yellow-400">${off.kd ?? '--'}</td>
                    <td class="px-3 py-2 text-right text-slate-300">${off.damage_given != null ? off.damage_given.toLocaleString() : '--'}</td>
                    <td class="px-3 py-2 text-right text-purple-400">${off.dpm ?? '--'}</td>
                    <td class="px-3 py-2 text-right text-cyan-400">${adv.frag_potential != null ? adv.frag_potential.toFixed(0) : '--'}</td>
                    <td class="px-3 py-2 text-right text-amber-300">${ps.aggression != null ? ps.aggression.toFixed(1) : '--'}</td>
                    <td class="px-3 py-2 text-right text-emerald-300">${adv.discipline_score != null ? adv.discipline_score.toFixed(1) : '--'}</td>
                    <td class="px-3 py-2 text-right text-amber-400">${adv.survival_rate != null ? adv.survival_rate.toFixed(1) + '%' : '--'}</td>
                    <td class="px-3 py-2 text-right text-sky-400">${ps.precision != null ? ps.precision.toFixed(1) + '%' : '--'}</td>`;
                tbody.appendChild(tr);
            });
        }

        if (requestToken !== _vizRequestToken || _activeTab !== 'charts' || _activeRoundId) return;
        _vizLoaded = 'session';
        if (typeof lucide !== 'undefined') lucide.createIcons();
    } catch (e) {
        if (requestToken !== _vizRequestToken || _activeTab !== 'charts' || _activeRoundId) return;
        console.error('Session graphs error:', e);
        panel.innerHTML = '<div class="text-center text-red-500 py-12">Failed to load session graphs.</div>';
    }
}

// ============================================================
// VIZ TAB — ROUND CHARTS
// ============================================================

async function _loadVizTab() {
    const panel = document.getElementById('sd-tab-charts');
    if (!panel) return;
    const requestedRoundId = coerceRoundId(_activeRoundId);

    // When a round is active, cache by round id; otherwise the session view is cached with 'session'
    if (requestedRoundId && _vizLoaded === requestedRoundId) return;

    if (!requestedRoundId) {
        // No round selected — show full session graphs instead
        if (_vizLoaded === 'session') return;
        const requestToken = ++_vizRequestToken;
        _sdCharts.forEach(c => { try { c.destroy(); } catch (e) { /* ignore */ } });
        _sdCharts = [];
        while (_rvCharts.length) { try { _rvCharts.pop().destroy(); } catch (e) { /* ignore */ } }
        await _renderSessionGraphs(panel, requestToken);
        return;
    }

    const requestToken = ++_vizRequestToken;
    _sdCharts.forEach(c => { try { c.destroy(); } catch (e) { /* ignore */ } });
    _sdCharts = [];
    while (_rvCharts.length) { try { _rvCharts.pop().destroy(); } catch (e) { /* ignore */ } }

    panel.innerHTML = `
        <div class="text-center py-12">
            <i data-lucide="loader" class="w-8 h-8 text-brand-purple animate-spin mx-auto mb-4"></i>
            <div class="text-slate-400">Loading round charts...</div>
        </div>`;
    if (typeof lucide !== 'undefined') lucide.createIcons();

    try {
        const vizData = await fetchJSON(`${API_BASE}/rounds/${requestedRoundId}/viz`);
        if (requestToken !== _vizRequestToken || _activeTab !== 'charts' || _activeRoundId !== requestedRoundId) return;
        if (!vizData || !vizData.players || vizData.players.length === 0) {
            panel.innerHTML = '<div class="text-center text-slate-500 py-12">No chart data for this round</div>';
            return;
        }

        const playerCount = vizData.players.length;
        panel.innerHTML = `
            <div class="glass-panel rounded-xl p-3 mb-6 flex items-center gap-3">
                <i data-lucide="crosshair" class="w-4 h-4 text-brand-purple"></i>
                <span class="text-sm text-slate-300">
                    Round <strong class="text-white">${requestedRoundId}</strong> —
                    ${escapeHtml(vizData.map_name || 'Unknown')} ${escapeHtml(vizData.round_label || '')}
                </span>
                <button onclick="sdSwitchTab('summary')" class="ml-auto text-xs text-slate-400 hover:text-white transition">
                    Change round
                </button>
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div id="rv-summary" class="glass-card rounded-xl p-5"></div>
                <div class="glass-card rounded-xl p-5">
                    <h3 class="text-sm font-bold text-white mb-4">Combat Overview</h3>
                    <div style="height:320px"><canvas id="rv-radar"></canvas></div>
                </div>
            </div>
            <div class="glass-card rounded-xl p-5 mt-6">
                <h3 class="text-sm font-bold text-white mb-4">Top Fraggers</h3>
                <div style="height:${Math.max(200, playerCount * 32)}px"><canvas id="rv-fraggers"></canvas></div>
            </div>
            <div class="glass-card rounded-xl p-5 mt-6">
                <h3 class="text-sm font-bold text-white mb-4">Damage Breakdown</h3>
                <div id="rv-damage-table"></div>
            </div>
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
                <div class="glass-card rounded-xl p-5">
                    <h3 class="text-sm font-bold text-white mb-4">Support Performance</h3>
                    <div style="height:${Math.max(200, playerCount * 36)}px"><canvas id="rv-support"></canvas></div>
                </div>
                <div class="glass-card rounded-xl p-5">
                    <h3 class="text-sm font-bold text-white mb-4">Time Distribution</h3>
                    <div style="height:${Math.max(200, playerCount * 32)}px"><canvas id="rv-time"></canvas></div>
                </div>
            </div>`;

        renderMatchSummary(vizData);
        renderCombatRadar(vizData);
        renderTopFraggers(vizData);
        renderDamageBreakdown(vizData);
        renderSupportPerformance(vizData);
        renderTimeDistribution(vizData);

        if (requestToken !== _vizRequestToken || _activeTab !== 'charts' || _activeRoundId !== requestedRoundId) return;
        _vizLoaded = requestedRoundId;
        if (typeof lucide !== 'undefined') lucide.createIcons();
    } catch (e) {
        if (requestToken !== _vizRequestToken || _activeTab !== 'charts' || _activeRoundId !== requestedRoundId) return;
        console.error('Viz tab error:', e);
        panel.innerHTML = '<div class="text-center text-red-500 py-12">Failed to load round charts</div>';
    }
}

// ============================================================
// CLEANUP + WINDOW EXPORTS
// ============================================================

function _destroyAllCharts() {
    _destroyPlayersSummaryCharts();
    _destroyAllPlayerPanelCharts();
    _sdCharts.forEach(c => { try { c.destroy(); } catch (e) { /* ignore */ } });
    _sdCharts = [];
    while (_rvCharts.length) { try { _rvCharts.pop().destroy(); } catch (e) { /* ignore */ } }
}

// ---- Header map/round selection handlers ----

export function sdSelectHeaderMap(mapIndex) {
    const parsed = Number.parseInt(String(mapIndex), 10);
    if (!Number.isFinite(parsed) || parsed < 0) return;
    if (_expandedMapIndex === parsed) {
        _expandedMapIndex = null;
    } else {
        _expandedMapIndex = parsed;
    }
    _activeRoundId = null;
    _activeRoundStartUnix = null;
    _activeRoundSessionDate = null;
    _overviewMapIndex = _expandedMapIndex;
    _overviewRoundId = null;
    _refreshRoundScopeUi();
    if (_activeTab === 'summary') _renderSummaryTab(true);
}

export function sdSelectHeaderRound(mapIndex, roundId, roundStartUnix = 0, roundDate = '') {
    const parsedMap = Number.parseInt(String(mapIndex), 10);
    const parsedRound = coerceRoundId(roundId);
    if (!Number.isFinite(parsedMap) || parsedMap < 0 || !parsedRound) return;
    _expandedMapIndex = parsedMap;
    _overviewMapIndex = parsedMap;
    _overviewRoundId = parsedRound;
    sdSelectRound(parsedRound, roundDate || _sessionDate, roundStartUnix);
    if (_activeTab === 'summary') _renderSummaryTab(true);
}

export function sdClearRoundKeepMap() {
    _activeRoundId = null;
    _activeRoundStartUnix = null;
    _activeRoundSessionDate = null;
    _overviewRoundId = null;
    _signalsLoaded = null;
    _vizLoaded = null;
    _playersScopeLoaded = null;
    _refreshRoundScopeUi();
    if (_activeTab === 'summary') _renderSummaryTab(true);
    else if (_activeTab === 'players') _renderPlayersTab(true);
}

export function sdClearHeaderMapScope() {
    _expandedMapIndex = null;
    _overviewMapIndex = null;
    _overviewRoundId = null;
    sdClearRoundScope();
    _refreshRoundScopeUi();
    if (_activeTab === 'summary') _renderSummaryTab(true);
}

window.sdSwitchTab = sdSwitchTab;
window.sdSelectOverviewMap = sdSelectOverviewMap;
window.sdSelectOverviewRound = sdSelectOverviewRound;
window.sdClearOverviewScope = sdClearOverviewScope;
window.sdSelectRound = sdSelectRound;
window.sdClearRoundScope = sdClearRoundScope;
window.sdTogglePlayerPanel = sdTogglePlayerPanel;
window.sdSelectHeaderMap = sdSelectHeaderMap;
window.sdSelectHeaderRound = sdSelectHeaderRound;
window.sdClearRoundKeepMap = sdClearRoundKeepMap;
window.sdClearHeaderMapScope = sdClearHeaderMapScope;
