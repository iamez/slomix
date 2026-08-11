/**
 * Live event ticker (Live-view S3) — renders the in-round event feed the
 * Tonight page could never show before: objective steals/returns, dynamite
 * plants/defuses, map-script announces, round boundaries — seconds after
 * they happen on the server.
 *
 * Data path: legacy3.log → tailer on the game server (S2) → POST
 * /api/live/events → ring buffer → GET /api/live/feed?since=<seq> polled
 * here every 3 s. The ticker owns its own poll loop and state; tonight.js
 * only renders the shell (#live-ticker) and calls renderLiveTicker() after
 * rebuilding its DOM (its 8 s refresh wipes the container).
 *
 * Filtering (owner call, 2026-08-11): the feed is about OBJECTIVES by
 * default — kills and joins drown the two events per minute that matter.
 * Every event is buffered client-side regardless; the category checkboxes
 * are a pure display filter (persisted in localStorage), so switching one
 * on retroactively reveals the recent history too.
 * @module live-ticker
 */
import { API_BASE, fetchJSON, escapeHtml, safeInsertHTML } from './utils.js';

const POLL_MS = 3000;
const MAX_BUFFER = 200;   // events kept client-side (all categories)
const MAX_SHOWN = 40;     // rows rendered after filtering

const CATEGORIES = {
    objectives: { label: 'Objectives', types: ['POPUP', 'ANNOUNCE', 'OBJECTIVE_DESTROYED', 'DYNAMITE', 'FLAG_PICKUP'], default: true },
    rounds:     { label: 'Rounds',     types: ['ROUND_START', 'ROUND_END', 'EXIT', 'MAP'], default: true },
    kills:      { label: 'Kills',      types: ['KILL'], default: false },
    support:    { label: 'Support',    types: ['REVIVE', 'SHOVE', 'SUPPLY'], default: false },
    chat:       { label: 'Chat',       types: ['SAY'], default: false },
    votes:      { label: 'Votes',      types: ['CALLVOTE', 'VOTE_PASSED'], default: false },
};
const _TYPE_TO_CAT = {};
for (const [cat, def] of Object.entries(CATEGORIES)) {
    for (const t of def.types) _TYPE_TO_CAT[t] = cat;
}

const FILTER_STORE_KEY = 'slomix.liveFeedFilters.v1';

function _loadFilters() {
    try {
        const raw = JSON.parse(localStorage.getItem(FILTER_STORE_KEY) || 'null');
        if (raw && typeof raw === 'object') {
            const out = {};
            for (const cat of Object.keys(CATEGORIES)) {
                out[cat] = typeof raw[cat] === 'boolean' ? raw[cat] : CATEGORIES[cat].default;
            }
            return out;
        }
    } catch { /* corrupted store → defaults */ }
    return Object.fromEntries(Object.entries(CATEGORIES).map(([c, d]) => [c, d.default]));
}

let _filters = _loadFilters();
let _cursor = 0;
let _events = [];          // newest last, ALL categories
let _interval = null;
let _lastFetchOk = null;   // null = never fetched, false = feed erroring

// Live roster derived from the feed: slot -> {name, team}. TEAM_CHANGE
// carries the engine team (1=Axis, 2=Allies, 3=spectator); DISCONNECT
// clears the slot. INIT_GAME does NOT clear — players re-announce
// themselves via userinfo right after a map load, so clearing would blink.
const _roster = new Map();
let _rosterUpdatedAt = 0;

function _rosterApply(ev) {
    if (ev.type === 'TEAM_CHANGE' && ev.slot != null) {
        if (ev.team === 1 || ev.team === 2 || ev.team === 3) {
            _roster.set(ev.slot, { name: ev.name || `slot ${ev.slot}`, team: ev.team });
        }
        _rosterUpdatedAt = Date.now();
    } else if (ev.type === 'DISCONNECT' && ev.slot != null) {
        _roster.delete(ev.slot);
        _rosterUpdatedAt = Date.now();
    }
}

function _slotName(slot) {
    const e = _roster.get(typeof slot === 'string' ? parseInt(slot, 10) : slot);
    return e ? e.name : `#${slot}`;
}

function _slotTeam(slot) {
    const e = _roster.get(typeof slot === 'string' ? parseInt(slot, 10) : slot);
    return e ? e.team : null;
}

/** True when the live roster contains at least one Omni-bot name — the
 * owner wants bot activity visually distinct from real matches. */
export function liveRosterHasBots() {
    for (const { name } of _roster.values()) {
        if (name && name.startsWith('[BOT]')) return true;
    }
    return false;
}

// Kill streak per slot (consecutive kills without dying) + per-round
// scoreline collection for the ROUND_END summary. Reset on round bounds.
const _streak = new Map();
let _roundScores = [];

function _combatApply(ev) {
    if (ev.type === 'KILL') {
        const k = ev.killer_slot, v = ev.victim_slot;
        if (k !== v) _streak.set(k, (_streak.get(k) || 0) + 1);
        _streak.set(v, 0);
        ev._streak = k !== v ? _streak.get(k) : 0;
        const kt = _slotTeam(k), vt = _slotTeam(v);
        ev._teamkill = k !== v && kt != null && kt === vt && kt !== 3;
    } else if (ev.type === 'SCORELINE') {
        _roundScores.push(ev);
    } else if (ev.type === 'ROUND_END') {
        ev._top = _roundScores.slice().sort((a, b) => (b.xp || 0) - (a.xp || 0)).slice(0, 3);
        _roundScores = [];
        _streak.clear();
    } else if (ev.type === 'ROUND_START') {
        _roundScores = [];
        _streak.clear();
    }
}

/** Current sides as seen by the live feed. fresh=false when the feed has
 * not spoken recently — callers should fall back to the UDP player list. */
export function getLiveRoster() {
    const out = { axis: [], allies: [], spectators: [], fresh: false };
    for (const { name, team } of _roster.values()) {
        if (team === 1) out.axis.push(name);
        else if (team === 2) out.allies.push(name);
        else out.spectators.push(name);
    }
    out.fresh = _rosterUpdatedAt > 0 && (Date.now() - _rosterUpdatedAt) < 10 * 60 * 1000;
    return out;
}

function _saveFilters() {
    try { localStorage.setItem(FILTER_STORE_KEY, JSON.stringify(_filters)); } catch { /* private mode */ }
}

function _viewActive() {
    const v = document.getElementById('view-tonight');
    return v && v.classList.contains('active') && !v.classList.contains('hidden') && !document.hidden;
}

async function _poll() {
    if (!_viewActive()) { stopLiveTicker(); return; }
    try {
        const data = await fetchJSON(
            `${API_BASE}/live/feed?since=${_cursor}`,
            { cachePolicy: 'no-store', credentials: 'same-origin' },
        );
        _lastFetchOk = true;
        if (data && Array.isArray(data.events) && data.events.length) {
            _events = _events.concat(data.events).slice(-MAX_BUFFER);
            _cursor = data.last_seq || _cursor;
            renderLiveTicker();
        } else if (data && data.last_seq != null) {
            _cursor = data.last_seq;
        }
    } catch (e) {
        _lastFetchOk = false;
        console.warn('live ticker poll failed', e);
    }
}

export function startLiveTicker() {
    if (_interval) return;
    _poll();
    _interval = setInterval(_poll, POLL_MS);
}

export function stopLiveTicker() {
    if (_interval) { clearInterval(_interval); _interval = null; }
}

function _ago(receivedAt) {
    if (!receivedAt) return '';
    const s = Math.max(0, Math.round(Date.now() / 1000 - receivedAt));
    if (s < 60) return `${s}s ago`;
    return `${Math.floor(s / 60)}m ago`;
}

function _line(ev) {
    const t = ev.type;
    const ago = `<span class="text-slate-500 text-xs shrink-0">${_ago(ev.received_at)}</span>`;
    const wrap = (icon, body, cls = 'text-slate-200') =>
        `<div class="flex items-center gap-2 py-1 ${cls}"><span class="shrink-0">${icon}</span><span class="min-w-0 truncate">${body}</span>${ago}</div>`;

    switch (t) {
        case 'POPUP': {
            const verb = ev.verb;
            const team = escapeHtml(ev.team || '');
            const obj = escapeHtml(ev.objective || '');
            if (verb === 'stole') return wrap('🚩', `<b class="uppercase">${team}</b> stole <b>${obj}</b>`, 'text-amber-300');
            if (verb === 'returned') return wrap('↩️', `<b class="uppercase">${team}</b> returned <b>${obj}</b>`, 'text-emerald-300');
            if (verb === 'planted') return wrap('💣', `<b class="uppercase">${team}</b> planted at <b>${obj}</b>`, 'text-orange-300');
            if (verb === 'defused') return wrap('✂️', `<b class="uppercase">${team}</b> defused <b>${obj}</b>`, 'text-sky-300');
            return wrap('•', `${team} ${escapeHtml(verb || '')} ${obj}`);
        }
        case 'ANNOUNCE':
            return wrap('📣', escapeHtml(ev.text || ''), 'text-cyan-200');
        case 'OBJECTIVE_DESTROYED':
            return wrap('💥', `Objective destroyed: ${escapeHtml(ev.detail || '')}`, 'text-orange-200');
        case 'DYNAMITE':
            return wrap(ev.action === 'plant' ? '🧨' : '✂️',
                `<b>${escapeHtml(_slotName(ev.slot))}</b> ${ev.action === 'plant' ? 'planted dynamite at' : 'defused dynamite at'} <b>${escapeHtml(ev.objective || '')}</b>`,
                'text-orange-200');
        case 'FLAG_PICKUP':
            return wrap('🏳️', `<b>${escapeHtml(_slotName(ev.slot))}</b> picked up the objective`, 'text-amber-200');
        case 'REVIVE': {
            const [rs, vs] = String(ev.slots || '').split(/\s+/);
            return wrap('💉', `<b>${escapeHtml(_slotName(rs))}</b> revived <b>${escapeHtml(_slotName(vs))}</b>`, 'text-emerald-200');
        }
        case 'SHOVE': {
            const [a, b] = String(ev.slots || '').split(/\s+/);
            return wrap('🫸', `${escapeHtml(_slotName(a))} shoved ${escapeHtml(_slotName(b))}`, 'text-slate-400');
        }
        case 'SUPPLY': {
            const [g] = String(ev.slots || '').split(/\s+/);
            return wrap('🎒', `${escapeHtml(_slotName(g))} handed out supplies`, 'text-slate-400');
        }
        case 'KILL': {
            const streak = ev._streak >= 3 ? ` <span class="text-amber-300 text-xs font-bold">🔥 ${ev._streak} streak</span>` : '';
            const tk = ev._teamkill ? ` <span class="text-rose-400 text-xs font-black">TEAMKILL</span>` : '';
            return wrap('⚔️',
                `<b>${escapeHtml(ev.killer || '?')}</b> <span class="text-slate-500">killed</span> ${escapeHtml(ev.victim || '?')} <span class="text-slate-500 text-xs">${escapeHtml((ev.mod || '').replace('MOD_', ''))}</span>${streak}${tk}`,
                ev._teamkill ? 'text-rose-200' : 'text-slate-300');
        }
        case 'ROUND_START':
            return `<div class="py-1.5 my-1 text-center text-xs font-black tracking-widest text-emerald-300 border-y border-emerald-500/20">ROUND START</div>`;
        case 'ROUND_END': {
            const top = (ev._top || [])
                .map(sc => `${escapeHtml(sc.name || _slotName(sc.slot))} ${sc.xp} XP`)
                .join(' · ');
            return `<div class="py-1.5 my-1 text-center text-xs font-black tracking-widest text-rose-300 border-y border-rose-500/20">ROUND END${top ? `<div class="font-normal normal-case tracking-normal text-slate-400 mt-0.5">${top}</div>` : ''}</div>`;
        }
        case 'EXIT':
            return wrap('🏁', escapeHtml(ev.reason || ''), 'text-rose-200');
        case 'MAP':
            return wrap('🗺️', `Map: <b>${escapeHtml(ev.map_name || '')}</b>`, 'text-indigo-200');
        case 'SAY':
            return wrap('💬', `<b>${escapeHtml(ev.name || '')}</b>: ${escapeHtml(ev.text || '')}`, 'text-slate-400');
        case 'CALLVOTE':
            return wrap('🗳️', `Vote called: ${escapeHtml(ev.vote || '')}`, 'text-slate-400');
        case 'VOTE_PASSED':
            return wrap('✅', 'Vote passed', 'text-slate-400');
        default:
            return '';
    }
}

function _filterChips() {
    return Object.entries(CATEGORIES).map(([cat, def]) => {
        const on = !!_filters[cat];
        return `<label class="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg cursor-pointer select-none text-xs font-bold transition-colors ${on ? 'bg-brand-cyan/20 text-brand-cyan' : 'bg-white/5 text-slate-500 hover:text-slate-300'}">
            <input type="checkbox" data-live-cat="${cat}" ${on ? 'checked' : ''} class="accent-cyan-400 w-3 h-3">${def.label}
        </label>`;
    }).join('');
}

/** Re-render into the #live-ticker shell if present (idempotent). */
export function renderLiveTicker() {
    const host = document.getElementById('live-ticker');
    if (!host) return;
    const fresh = _events.length
        ? (Date.now() / 1000 - (_events[_events.length - 1].received_at || 0)) < 120
        : false;
    const botBadge = liveRosterHasBots()
        ? '<span class="px-1.5 py-0.5 rounded bg-fuchsia-500/20 text-fuchsia-300 text-[10px] font-black tracking-wider">BOT TEST</span>'
        : '';
    const dot = _lastFetchOk === false
        ? '<span class="w-2 h-2 rounded-full bg-rose-500 inline-block"></span> feed error'
        : (fresh
            ? '<span class="w-2 h-2 rounded-full bg-emerald-400 inline-block animate-pulse"></span> LIVE'
            : '<span class="w-2 h-2 rounded-full bg-slate-600 inline-block"></span> quiet');
    const visible = _events.filter(e => _filters[_TYPE_TO_CAT[e.type]] === true);
    const rows = visible.slice(-MAX_SHOWN).reverse().map(_line).filter(Boolean).join('');
    host.textContent = '';
    safeInsertHTML(host, 'beforeend', `
        <div class="glass-panel rounded-xl p-4 mt-4">
            <div class="flex items-center justify-between mb-2 flex-wrap gap-2">
                <div class="text-sm font-black text-white tracking-wide flex items-center gap-2">MATCH FEED ${botBadge}</div>
                <div class="text-xs text-slate-400 flex items-center gap-1.5">${dot}</div>
            </div>
            <div class="flex flex-wrap gap-1.5 mb-2">${_filterChips()}</div>
            <div class="max-h-72 overflow-y-auto text-sm divide-y divide-white/5">
                ${rows || '<div class="text-slate-500 text-sm py-3 text-center">No live events in the selected categories.</div>'}
            </div>
        </div>`);
    // Rebind after each render (the shell is rebuilt every time).
    host.querySelectorAll('input[data-live-cat]').forEach(cb => {
        cb.addEventListener('change', () => {
            _filters[cb.dataset.liveCat] = cb.checked;
            _saveFilters();
            renderLiveTicker();
        });
    });
}
