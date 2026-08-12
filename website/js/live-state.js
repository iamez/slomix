/**
 * Live current-state panel (Live-view A1) — the authoritative "right now":
 * who is on the server, which side (Axis / Allies / Spectators), how long
 * they've been on, the game state and current/previous map.
 *
 * Reads GET /api/live/state — the server-side reducer snapshot (A0) — NOT
 * the raw event ring, so it never shows a stale roster or an old state as
 * live. Owns its own poll loop; tonight.js renders the #live-state shell
 * and calls renderLiveState().
 *
 * HUD note (esports best practice): sides are distinguished by icon + label
 * + position, not colour alone.
 * @module live-state
 */
import { API_BASE, fetchJSON, escapeHtml, safeInsertHTML } from './utils.js';

const POLL_MS = 4000;
const AXIS_COLOR = '#ef4444', ALLIES_COLOR = '#3b82f6';

let _snapshot = null;
let _interval = null;
let _lastOk = null;

function _viewActive() {
    const v = document.getElementById('view-live');
    return v && v.classList.contains('active') && !v.classList.contains('hidden') && !document.hidden;
}

function _dur(sec) {
    if (sec == null) return '';
    const s = Math.max(0, Math.round(sec));
    if (s < 60) return `${s}s`;
    const m = Math.floor(s / 60);
    if (m < 60) return `${m}m`;
    return `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, '0')}m`;
}

async function _poll() {
    if (!_viewActive()) { stopLiveState(); return; }
    try {
        _snapshot = await fetchJSON(`${API_BASE}/live/state`,
            { cachePolicy: 'no-store', credentials: 'same-origin' });
        _lastOk = true;
        renderLiveState();
    } catch (e) {
        _lastOk = false;
        console.warn('live state poll failed', e);
    }
}

export function startLiveState() {
    if (_interval) return;
    _poll();
    _interval = setInterval(_poll, POLL_MS);
}

export function stopLiveState() {
    if (_interval) { clearInterval(_interval); _interval = null; }
}

/** Latest snapshot (or null) — lets other modules reuse the authoritative
 * roster/state instead of re-deriving it. */
export function getSnapshot() {
    return _snapshot;
}

const _STATE_BADGE = {
    live:      ['#34d399', 'LIVE'],
    warmup:    ['#fbbf24', 'WARMUP'],
    between:   ['#94a3b8', 'BETWEEN ROUNDS'],
    mapchange: ['#818cf8', 'MAP CHANGING'],
    idle:      ['#64748b', 'IDLE'],
    unknown:   ['#64748b', '—'],
};

function _member(m, alignRight) {
    const times = [];
    if (m.on_server_seconds != null) times.push(`server ${_dur(m.on_server_seconds)}`);
    if (m.on_side_seconds != null && m.on_side_seconds + 5 < m.on_server_seconds) {
        times.push(`side ${_dur(m.on_side_seconds)}`);
    }
    const sub = times.length
        ? `<span class="text-slate-500 text-[10px] ml-1">${times.join(' · ')}</span>` : '';
    return `<div class="text-sm text-slate-200 truncate ${alignRight ? 'text-right' : ''}">${escapeHtml(m.name)}${sub}</div>`;
}

function _column(icon, label, color, members, alignRight) {
    const rows = members.length
        ? members.map(m => _member(m, alignRight)).join('')
        : '<div class="text-sm text-slate-600">—</div>';
    return `<div class="flex-1 min-w-0 ${alignRight ? 'text-right' : ''}">
        <div class="text-[10px] uppercase tracking-widest font-black mb-1.5" style="color:${color}">
            ${alignRight ? `${label} ${icon}` : `${icon} ${label}`}
        </div>
        ${rows}
    </div>`;
}

/** Render the current-state panel into the #live-state shell if present. */
export function renderLiveState() {
    const host = document.getElementById('live-state');
    if (!host) return;
    const s = _snapshot;
    if (!s) { host.textContent = ''; return; }

    const [dotColor, stateLabel] = _STATE_BADGE[s.game_state] || _STATE_BADGE.unknown;
    const r = s.roster || { axis: [], allies: [], spectators: [] };
    const mapLine = s.current_map
        ? `<span class="text-white font-bold">${escapeHtml(s.current_map)}</span>${
            s.previous_map ? `<span class="text-slate-500 text-xs"> · prev ${escapeHtml(s.previous_map)}</span>` : ''}`
        : '<span class="text-slate-500">no map</span>';
    const roundTimer = s.round_elapsed_seconds != null
        ? `<span class="text-slate-400 text-xs ml-2">R${s.round_number || '?'} · ${_dur(s.round_elapsed_seconds)}</span>` : '';
    const sessionLine = s.session_start_seconds != null
        ? `<span class="text-slate-500 text-xs">session ${_dur(s.session_start_seconds)}</span>` : '';
    const botBadge = r.has_bots
        ? '<span class="px-1.5 py-0.5 rounded bg-fuchsia-500/20 text-fuchsia-300 text-[10px] font-black tracking-wider">BOT TEST</span>' : '';
    const specStrip = (r.spectators && r.spectators.length)
        ? `<div class="mt-3 pt-2 border-t border-white/5 text-[11px] text-slate-500 text-center truncate">👁 spectating: ${r.spectators.map(m => escapeHtml(m.name)).join(' · ')}</div>` : '';
    const staleWarn = _lastOk === false
        ? '<span class="text-rose-400 text-xs">state unavailable</span>' : '';

    host.textContent = '';
    safeInsertHTML(host, 'beforeend', `
        <div class="glass-panel rounded-xl p-5 ${r.has_bots ? 'opacity-90' : ''}">
            <div class="flex items-center justify-between flex-wrap gap-2 mb-3">
                <div class="flex items-center gap-2 text-sm">
                    <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-bold"
                          style="background:${dotColor}22;color:${dotColor}">
                        <span class="w-1.5 h-1.5 rounded-full ${s.is_live ? 'animate-pulse' : ''}" style="background:${dotColor}"></span>${stateLabel}
                    </span>
                    <span class="text-slate-400">on ${mapLine}${roundTimer}</span>
                    ${botBadge}
                </div>
                <div class="flex items-center gap-2">${sessionLine}${staleWarn}</div>
            </div>
            <div class="flex items-start gap-4">
                ${_column('🔴', 'Axis', AXIS_COLOR, r.axis || [], false)}
                <div class="text-center shrink-0 px-2 text-slate-600 self-center">
                    <div class="text-lg font-black text-slate-500">${(r.axis || []).length}<span class="text-slate-700 mx-0.5">v</span>${(r.allies || []).length}</div>
                </div>
                ${_column('🔵', 'Allies', ALLIES_COLOR, r.allies || [], true)}
            </div>
            ${specStrip}
        </div>`);
}
