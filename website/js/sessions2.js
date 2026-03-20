/**
 * Sessions 2.0 — Master Session List
 * Each session card navigates to the dedicated detail page.
 * @module sessions2
 */
import { API_BASE, fetchJSON, escapeHtml, escapeJsString } from './utils.js';

// ---- Map image constants (copied from sessions.js) ----
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
// Team icons available for future use
// const AXIS_ICON = "assets/icons/axis.svg";
// const ALLIES_ICON = "assets/icons/allies.svg";

// ---- Utility functions (copied from sessions.js — pure/stateless) ----

function normalizeMapKey(mapName) {
    const raw = (mapName || '').toString().trim().toLowerCase();
    if (!raw) return '';
    return raw
        .replace(/^maps[\\/]/, '')
        .replace(/\.(bsp|pk3|arena)$/i, '')
        .replace(/[^a-z0-9]+/g, '_')
        .replace(/_+/g, '_')
        .replace(/^_+|_+$/g, '');
}

function mapLabel(mapName) {
    return (mapName || 'Unknown')
        .toString()
        .replace(/^maps[\\/]/, '')
        .replace(/\.(bsp|pk3|arena)$/i, '')
        .replace(/_/g, ' ');
}

function mapImageFor(mapName) {
    const key = normalizeMapKey(mapName);
    if (MAP_IMAGE_MAP[key]) return MAP_IMAGE_MAP[key];

    const trimmed = key.replace(/^etl_/, '').replace(/^sw_/, '').replace(/^et_/, '');
    const candidates = [trimmed, `etl_${trimmed}`, `sw_${trimmed}`, `et_${trimmed}`, key];
    for (const candidate of candidates) {
        if (MAP_IMAGE_MAP[candidate]) return MAP_IMAGE_MAP[candidate];
    }

    const keyCompact = key.replace(/_/g, '');
    for (const [mapKey, mapPath] of Object.entries(MAP_IMAGE_MAP)) {
        if (mapKey === 'map_generic') continue;
        const mapCompact = mapKey.replace(/_/g, '');
        if (key.includes(mapKey) || mapKey.includes(key) || keyCompact.includes(mapCompact) || mapCompact.includes(keyCompact)) {
            return mapPath;
        }
    }
    return "assets/maps/map_generic.svg";
}

function mapTile(mapName) {
    const safeMapName = escapeHtml(mapLabel(mapName));
    const mapImg = mapImageFor(mapName);
    const isFallback = mapImg.includes('map_generic');
    if (isFallback) {
        return `<div class="w-16 h-10 rounded-md bg-slate-900/60 border border-white/10 flex items-center justify-center text-[9px] font-bold text-white px-1 text-center leading-tight"><span class="truncate" title="${safeMapName}">${safeMapName}</span></div>`;
    }
    return `<div class="relative w-16 h-10 rounded-md border border-white/10 overflow-hidden bg-slate-900/60"><div class="absolute inset-0 bg-cover bg-center" style="background-image: url('${mapImg}')"></div><div class="absolute bottom-0 left-0 right-0 bg-black/50 text-[9px] text-slate-100 px-1 truncate">${safeMapName}</div></div>`;
}

function formatSessionDuration(seconds) {
    const total = Number(seconds || 0);
    if (!total || total <= 0) return '';
    const hrs = Math.floor(total / 3600);
    const mins = Math.floor((total % 3600) / 60);
    if (hrs > 0) return `${hrs}h ${mins}m`;
    return `${mins}m`;
}

function stripEtColors(text) {
    if (!text) return '';
    return String(text).replace(/\^[0-9A-Za-z]/g, '');
}

// ---- Module state ----
let s2Data = [];
let s2Offset = 0;
const S2_LIMIT = 15;
let s2SearchQuery = '';
let s2SearchTimer = null;

// ============================================================
// PUBLIC API
// ============================================================

export async function loadSessions2View() {
    s2Data = [];
    s2Offset = 0;
    s2SearchQuery = '';
    await _loadS2Page(true);
    _initS2Search();
}

export function loadMoreSessions2() {
    _loadS2Page(false);
}

// ============================================================
// INTERNAL
// ============================================================

async function _loadS2Page(reset) {
    const container = document.getElementById('sessions2-list');
    if (!container) return;

    if (reset) {
        container.innerHTML = `
            <div class="text-center py-12">
                <i data-lucide="loader" class="w-8 h-8 text-brand-blue animate-spin mx-auto mb-4"></i>
                <div class="text-slate-400">Loading sessions...</div>
            </div>`;
        if (typeof lucide !== 'undefined') lucide.createIcons();
    }

    try {
        let url = `${API_BASE}/stats/sessions?limit=${S2_LIMIT}&offset=${s2Offset}`;
        if (s2SearchQuery) url += `&search=${encodeURIComponent(s2SearchQuery)}`;
        const data = await fetchJSON(url);

        if (reset) {
            container.innerHTML = '';
            s2Data = data;
        } else {
            s2Data = [...s2Data, ...data];
        }

        if (reset && data.length === 0) {
            const emptyMessage = s2SearchQuery
                ? `No sessions found for "${escapeHtml(s2SearchQuery)}".`
                : 'No sessions available yet.';
            container.innerHTML = `
                <div class="glass-panel rounded-xl p-8 text-center text-slate-400">
                    ${emptyMessage}
                </div>
            `;
            const loadMoreBtn = document.getElementById('sessions2-load-more');
            if (loadMoreBtn) loadMoreBtn.classList.add('hidden');
        }

        data.forEach(session => {
            container.insertAdjacentHTML('beforeend', _renderS2Card(session));
        });

        if (typeof lucide !== 'undefined') lucide.createIcons();

        const loadMoreBtn = document.getElementById('sessions2-load-more');
        if (loadMoreBtn) loadMoreBtn.classList.toggle('hidden', data.length < S2_LIMIT);

        const countEl = document.getElementById('sessions2-search-count');
        if (countEl) {
            if (s2SearchQuery) {
                countEl.textContent = `${data.length} session${data.length !== 1 ? 's' : ''} found for "${s2SearchQuery}"`;
                countEl.classList.remove('hidden');
            } else {
                countEl.classList.add('hidden');
            }
        }

        s2Offset += data.length;
    } catch (e) {
        console.error('Failed to load sessions2:', e);
        container.innerHTML = '<div class="text-center text-red-500 py-12">Failed to load sessions</div>';
    }
}

function _renderS2Card(session) {
    const rawDate = String(session.date ?? '');
    const safeFormattedDate = escapeHtml(session.formatted_date || rawDate);
    const safeTimeAgo = escapeHtml(session.time_ago || '');
    const sessionId = session.session_id;
    const roundCount = session.round_count ?? session.rounds ?? 0;
    const playerCount = session.player_count ?? session.players ?? 0;
    const mapsPlayed = session.maps_played || [];
    const mapCount = mapsPlayed.length || (session.maps ?? 0);
    const totalKills = session.total_kills || 0;
    const durationStr = formatSessionDuration(session.duration_seconds);
    const startTime = session.start_time || '';
    const endTime = session.end_time || '';
    const timeRange = (startTime && endTime) ? `${startTime} — ${endTime}` : '';
    const missingRounds = roundCount % 2 !== 0;
    const mapTiles = mapsPlayed.slice(0, 5).map(map => mapTile(map)).join('');
    const moreMapsBadge = mapsPlayed.length > 5
        ? `<span class="text-slate-500 text-xs">+${mapsPlayed.length - 5} more</span>` : '';

    // Player lineup
    const playerNames = (session.player_names || []).map(n => stripEtColors(n)).filter(Boolean);

    // Navigation — prefer session_id, fall back to date
    const clickHandler = sessionId
        ? `navigateTo('session-detail', true, { sessionId: ${Number(sessionId)} })`
        : `navigateTo('session-detail', true, { sessionDate: '${escapeJsString(rawDate)}' })`;

    const alliesWins = session.allies_wins ?? 0;
    const axisWins = session.axis_wins ?? 0;
    const scoreColor = alliesWins > axisWins
        ? 'text-brand-blue'
        : axisWins > alliesWins
            ? 'text-brand-rose'
            : 'text-slate-400';

    return `
        <div class="glass-panel rounded-xl overflow-hidden session2-card cursor-pointer
                    hover:ring-1 hover:ring-brand-blue/30 transition-all"
             onclick="${clickHandler}">
            <div class="p-6">
                <div class="flex flex-wrap items-center justify-between gap-4">
                    <!-- Left: Date -->
                    <div class="flex items-center gap-4">
                        <div class="w-12 h-12 rounded-lg bg-gradient-to-br from-brand-purple to-brand-blue
                                    flex items-center justify-center shrink-0">
                            <i data-lucide="calendar" class="w-6 h-6 text-white"></i>
                        </div>
                        <div>
                            <div class="text-lg font-black text-white">${safeFormattedDate}</div>
                            <div class="text-sm text-slate-400 flex flex-wrap items-center gap-2">
                                <span>${safeTimeAgo}</span>
                                ${timeRange ? `<span class="text-slate-500">·</span><span>${escapeHtml(timeRange)}</span>` : ''}
                                ${durationStr ? `<span class="text-slate-500">·</span><span class="text-slate-500">${escapeHtml(durationStr)}</span>` : ''}
                                ${sessionId ? `<span class="px-2 py-0.5 rounded-full bg-slate-800 text-[10px] uppercase tracking-wide text-slate-400">Session ${sessionId}</span>` : ''}
                                ${missingRounds ? `<span class="px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 text-[10px] uppercase">Missing Round</span>` : ''}
                            </div>
                        </div>
                    </div>

                    <!-- Center: Stats -->
                    <div class="flex items-center gap-6">
                        <div class="text-center">
                            <div class="text-2xl font-black text-brand-cyan">${playerCount}</div>
                            <div class="text-xs text-slate-500 uppercase">Players</div>
                        </div>
                        <div class="text-center">
                            <div class="text-2xl font-black text-brand-purple">${mapCount}</div>
                            <div class="text-xs text-slate-500 uppercase">Maps</div>
                        </div>
                        <div class="text-center">
                            <div class="text-2xl font-black text-brand-amber">${roundCount}</div>
                            <div class="text-xs text-slate-500 uppercase">Rounds</div>
                        </div>
                        ${totalKills > 0 ? `
                        <div class="text-center">
                            <div class="text-2xl font-black text-brand-emerald">${totalKills.toLocaleString()}</div>
                            <div class="text-xs text-slate-500 uppercase">Kills</div>
                        </div>` : ''}
                        <div class="text-center">
                            <div class="text-2xl font-black ${scoreColor}">${alliesWins} - ${axisWins}</div>
                            <div class="text-xs text-slate-500 uppercase">Score</div>
                        </div>
                    </div>

                    <!-- Right: Arrow -->
                    <div class="flex items-center">
                        <i data-lucide="chevron-right" class="w-5 h-5 text-slate-400"></i>
                    </div>
                </div>

                <!-- Maps + lineup row -->
                <div class="mt-4 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
                    <div class="flex flex-wrap items-center gap-2">
                        ${mapTiles}
                        ${moreMapsBadge}
                    </div>
                    ${playerNames.length > 0 ? `
                    <div class="flex flex-wrap items-center gap-2">
                        <i data-lucide="users" class="w-3.5 h-3.5 text-slate-500 shrink-0"></i>
                        ${playerNames.map(name => `<span class="px-2 py-0.5 rounded-full bg-slate-800/80 text-xs text-slate-300 font-medium">${escapeHtml(name)}</span>`).join('')}
                    </div>
                    ` : ''}
                </div>
            </div>
        </div>
    `;
}

function _initS2Search() {
    const input = document.getElementById('sessions2-search-input');
    const clearBtn = document.getElementById('sessions2-search-clear');
    if (!input) return;

    if (input.dataset.s2ListenersAttached === '1') {
        input.value = '';
        if (clearBtn) clearBtn.classList.add('hidden');
        return;
    }

    input.value = '';
    if (clearBtn) clearBtn.classList.add('hidden');
    input.addEventListener('input', () => {
        const val = input.value.trim();
        if (clearBtn) clearBtn.classList.toggle('hidden', val.length === 0);
        if (s2SearchTimer) clearTimeout(s2SearchTimer);
        s2SearchTimer = setTimeout(() => {
            s2SearchQuery = val;
            s2Offset = 0;
            _loadS2Page(true);
        }, 300);
    });
    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            input.value = '';
            clearBtn.classList.add('hidden');
            s2SearchQuery = '';
            s2Offset = 0;
            if (s2SearchTimer) clearTimeout(s2SearchTimer);
            _loadS2Page(true);
        });
    }

    input.dataset.s2ListenersAttached = '1';
}

window.loadMoreSessions2 = loadMoreSessions2;
