/**
 * Live event ticker (Live-view S3) — renders the in-round event feed the
 * Tonight page could never show before: objective steals/returns, dynamite
 * plants/defuses, map-script announces, round boundaries — seconds after
 * they happen on the server.
 *
 * Data path: legacy3.log → tailer on the game server → POST /api/live/events
 * → ring buffer → GET /api/live/feed?since=<seq> polled here every 3 s.
 * The ticker owns its own poll loop and state; tonight.js only renders the
 * shell (#live-ticker) and calls renderLiveTicker() after rebuilding its
 * DOM (its 8 s refresh wipes the container).
 * @module live-ticker
 */
import { API_BASE, fetchJSON, escapeHtml, safeInsertHTML } from './utils.js';

const POLL_MS = 3000;
const MAX_SHOWN = 40;

// Owner call (2026-08-11): the feed is about OBJECTIVES, not a killfeed —
// kills/joins/team shuffles drown the two events per minute that matter.
// The API still carries everything; this is a display choice.
const SHOWN_TYPES = new Set([
    'POPUP', 'ANNOUNCE', 'OBJECTIVE_DESTROYED', 'DYNAMITE',
    'ROUND_START', 'ROUND_END', 'EXIT', 'MAP',
    'SAY', 'CALLVOTE', 'VOTE_PASSED',
]);

let _cursor = 0;
let _events = [];          // newest last
let _interval = null;
let _lastFetchOk = null;   // null = never fetched, false = feed erroring

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
            const shown = data.events.filter(e => SHOWN_TYPES.has(e.type));
            _events = _events.concat(shown).slice(-MAX_SHOWN);
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
                `Dynamite ${escapeHtml(ev.action || '')}: ${escapeHtml(ev.objective || '')}`, 'text-orange-200');
        case 'ROUND_START':
            return `<div class="py-1.5 my-1 text-center text-xs font-black tracking-widest text-emerald-300 border-y border-emerald-500/20">ROUND START</div>`;
        case 'ROUND_END':
            return `<div class="py-1.5 my-1 text-center text-xs font-black tracking-widest text-rose-300 border-y border-rose-500/20">ROUND END</div>`;
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

/** Re-render into the #live-ticker shell if present (idempotent). */
export function renderLiveTicker() {
    const host = document.getElementById('live-ticker');
    if (!host) return;
    const fresh = _events.length
        ? (Date.now() / 1000 - (_events[_events.length - 1].received_at || 0)) < 120
        : false;
    const dot = _lastFetchOk === false
        ? '<span class="w-2 h-2 rounded-full bg-rose-500 inline-block"></span> feed error'
        : (fresh
            ? '<span class="w-2 h-2 rounded-full bg-emerald-400 inline-block animate-pulse"></span> LIVE'
            : '<span class="w-2 h-2 rounded-full bg-slate-600 inline-block"></span> quiet');
    const rows = _events.slice().reverse().map(_line).filter(Boolean).join('');
    host.textContent = '';
    safeInsertHTML(host, 'beforeend', `
        <div class="glass-panel rounded-xl p-4 mt-4">
            <div class="flex items-center justify-between mb-2">
                <div class="text-sm font-black text-white tracking-wide">MATCH FEED</div>
                <div class="text-xs text-slate-400 flex items-center gap-1.5">${dot}</div>
            </div>
            <div class="max-h-72 overflow-y-auto text-sm divide-y divide-white/5">
                ${rows || '<div class="text-slate-500 text-sm py-3 text-center">No live events yet — they appear seconds after they happen in game.</div>'}
            </div>
        </div>`);
}
