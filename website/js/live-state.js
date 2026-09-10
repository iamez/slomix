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
import { openPlayerCard } from './player-card.js?v=20260819-card';

const POLL_MS = 4000;
const AXIS_COLOR = '#ef4444', ALLIES_COLOR = '#3b82f6';

let _snapshot = null;
let _interval = null;
let _ticker = null;
let _snapshotAt = 0;  // Date.now() when the current snapshot arrived
let _lastOk = null;
let _pollSeq = 0;     // monotonic: a poll only commits if still the current one

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

// M:SS / H:MM:SS clock for the round timer — a scoreboard always shows seconds,
// so this ticks visibly every second (unlike _dur, which rolls to whole minutes).
function _clock(sec) {
    // floor, not round: an elapsed timer shows the COMPLETED second (a stopwatch
    // reads 0:45 through the 46th second). round would let a tick that fires
    // slightly early/late cross the .5 boundary and show the same second twice
    // or skip one (Copilot).
    const s = Math.max(0, Math.floor(sec));
    const h = Math.floor(s / 3600);
    const mm = String(Math.floor((s % 3600) / 60)).padStart(h ? 2 : 1, '0');
    const ss = String(s % 60).padStart(2, '0');
    return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

async function _poll() {
    if (!_viewActive()) { stopLiveState(); return; }
    // Sequence guard: if a slow fetch resolves after a newer poll started (or
    // after stopLiveState), it must NOT overwrite the fresher snapshot/timestamp
    // — that would rewind _snapshotAt and glitch the timer (CodeRabbit).
    const seq = ++_pollSeq;
    try {
        const snap = await fetchJSON(`${API_BASE}/live/state`,
            { cachePolicy: 'no-store', credentials: 'same-origin' });
        if (seq !== _pollSeq) return;  // superseded — drop this stale response
        _snapshot = snap;
        _snapshotAt = Date.now();
        _lastOk = true;
        renderLiveState();
    } catch (e) {
        if (seq !== _pollSeq) return;
        _lastOk = false;
        console.warn('live state poll failed', e);
    }
}

// Between 4 s polls the round + session timers would sit frozen, then jump —
// the opposite of a live scoreboard. A 1 s tick interpolates them from the last
// snapshot (base + wall-time since it arrived), so the HUD-critical round timer
// counts up smoothly. Only the two prominent timers tick; per-player times
// refresh on the poll.
function _tick() {
    if (!_snapshot || !_snapshotAt) return;
    const elapsed = (Date.now() - _snapshotAt) / 1000;
    if (_snapshot.game_state === 'live' && _snapshot.round_elapsed_seconds != null) {
        const rt = document.getElementById('live-round-elapsed');
        if (rt) rt.textContent = _clock(_snapshot.round_elapsed_seconds + elapsed);
    }
    if (_snapshot.session_start_seconds != null) {
        const st = document.getElementById('live-session-elapsed');
        if (st) st.textContent = _dur(_snapshot.session_start_seconds + elapsed);
    }
}

export function startLiveState() {
    if (_interval) return;
    _poll();
    _interval = setInterval(_poll, POLL_MS);
    _ticker = setInterval(_tick, 1000);
}

export function stopLiveState() {
    _pollSeq++;  // invalidate any in-flight poll so it can't commit after stop
    if (_interval) { clearInterval(_interval); _interval = null; }
    if (_ticker) { clearInterval(_ticker); _ticker = null; }
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
    // Live Ladder (Val A): per-round K/D + DPM from LIVEX aggregates and an
    // alive dot (instant, from LIVE_KILL/LIVE_MOVEMENT). Absent while the
    // LIVEX tailer is quiet — the row falls back to the roster-only look.
    const lv = m.live;
    const liveBits = lv
        ? `<span class="font-mono text-[11px] ml-1 ${lv.alive === false ? 'text-slate-500' : 'text-slate-300'}">`
          + `${lv.alive === false ? '○' : '<span class="text-emerald-400">●</span>'} `
          + `${lv.kills ?? 0}/${lv.deaths ?? 0}${lv.dpm != null ? ` · ${lv.dpm}` : (lv.damage ? ` · ${lv.damage}dmg` : '')}</span>`
        : '';
    return `<div class="text-sm text-slate-200 truncate ${alignRight ? 'text-right' : ''}">`
        + `<button type="button" data-player-card="${escapeHtml(m.name)}" `
        + `class="hover:underline decoration-dotted underline-offset-2">${escapeHtml(m.name)}</button>`
        + `${liveBits}${sub}</div>`;
}

function _column(icon, label, color, members, alignRight) {
    // Ladder order: hottest first (live DPM desc), roster order otherwise.
    const sorted = [...members].sort((a, b) =>
        ((b.live && b.live.dpm) || -1) - ((a.live && a.live.dpm) || -1));
    const rows = sorted.length
        ? sorted.map(m => _member(m, alignRight)).join('')
        : '<div class="text-sm text-slate-400">—</div>';
    return `<div class="flex-1 min-w-0 ${alignRight ? 'text-right' : ''}">
        <div class="text-[10px] uppercase tracking-widest font-black mb-1.5" style="color:${color}">
            ${alignRight ? `${label} ${icon}` : `${icon} ${label}`}
        </div>
        ${rows}
    </div>`;
}

const _OBJ_ICON = {
    grabbed: '🚩', plant: '💣', planted: '💣', defuse: '🧨', defused: '🧨',
    stole: '📦', returned: '↩️',
};
const _OBJ_VERB = { grabbed: 'grabbed', plant: 'planted', defuse: 'defused' };

/** POPUP carries the side as a lowercased string ("axis"/"allies"), not the
 * 1/2 engine int the roster uses — accept both so POPUP objectives aren't
 * flattened to "Someone" (Copilot). */
function _teamLabel(t) {
    if (t === 1 || t === '1') return 'Axis';
    if (t === 2 || t === '2') return 'Allies';
    const s = t == null ? '' : String(t);
    return s ? s.charAt(0).toUpperCase() + s.slice(1) : null;
}

const _CHANGE_ICON = { joined: '➕', left: '➖', switched: '🔀' };

/** One roster change → "➕ vid joined Axis" / "➖ ownator left" / "🔀 carniee
 * switched to Allies". The "menjave" (substitutions) a spectator wants. A3. */
function _changeLine(c) {
    const icon = _CHANGE_ICON[c.action] || '•';
    const verb = c.action === 'switched' ? 'switched to' : c.action;
    const side = (c.action !== 'left' && c.side)
        ? ` <span class="text-slate-500">${escapeHtml(c.side)}</span>` : '';
    return `${icon} <span class="text-slate-300">${escapeHtml(c.name)}</span> ${verb}${side}`;
}

/** One recent objective action → "🚩 vid grabbed Gold Documents". Names the
 * actor when the source event carried a slot (flag/dynamite); POPUP stays
 * team-level. A4. */
function _objLine(o) {
    const who = escapeHtml(o.player || _teamLabel(o.team) || 'Someone');
    const verb = _OBJ_VERB[o.verb] || o.verb || 'took';
    const what = o.objective ? ` <span class="text-slate-400">${escapeHtml(o.objective)}</span>` : '';
    return `${_OBJ_ICON[o.verb] || '⚑'} <span class="text-slate-200">${who}</span> ${verb}${what}`;
}

/** Render the current-state panel into the #live-state shell if present. */
/**
 * How much the map may be trusted, from the snapshot's own evidence.
 *
 * Exported and pure so the rule can be tested where it is DECIDED rather than
 * through the polling loop that renders it — and so the React port inherits
 * the decision instead of re-deriving it from a screenshot.
 *
 * `unconfirmed` is deliberately `=== false`, not falsy: an older backend that
 * does not send the field at all must keep the previous behaviour rather than
 * label every map as doubtful.
 */
export function mapEvidence(snapshot) {
    const s = snapshot || {};
    const age = s.map_age_seconds;
    return {
        unconfirmed: s.map_confirmed === false,
        // Only worth saying once it is old enough to matter; below that the
        // number is noise beside a map that is plainly current.
        ageMinutes: (typeof age === 'number' && age > 300)
            ? Math.round(age / 60)
            : null,
    };
}


export function renderLiveState() {
    const host = document.getElementById('live-state');
    if (!host) return;
    const s = _snapshot;
    if (!s) { host.textContent = ''; return; }

    const [dotColor, stateLabel] = _STATE_BADGE[s.game_state] || _STATE_BADGE.unknown;
    const r = s.roster || { axis: [], allies: [], spectators: [] };
    // ⛔ THE MAP CAN OUTLIVE ITS EVIDENCE. The reducer keeps `current_map`
    // across a session boundary on purpose — a restarted server usually comes
    // back on the same map — but the first event after a gap is normally a
    // CONNECT, not a MAP. `is_live` then reads true and the age reads seconds
    // while the map is still the previous session's. `map_confirmed` is the
    // only thing that knows, and rendering it in bold without reading that
    // flag was the whole user-visible failure (Codex, PR #808).
    //
    // Same treatment as the roster two lines down: shown, dimmed, labelled.
    // Blanking it would trade a stale answer for no answer.
    const { unconfirmed: mapUnconfirmed, ageMinutes } = mapEvidence(s);
    const mapAgeNote = ageMinutes != null
        ? `<span class="text-slate-500 text-xs"> · seen ${ageMinutes}m ago</span>`
        : '';
    const mapLine = s.current_map
        ? `<span class="${mapUnconfirmed ? 'text-slate-400 font-bold' : 'text-white font-bold'}">${escapeHtml(s.current_map)}</span>${
            mapUnconfirmed ? '<span class="text-amber-400/80 text-[10px] ml-1 tracking-wider">UNCONFIRMED</span>' : mapAgeNote}${
            s.previous_map ? `<span class="text-slate-500 text-xs"> · prev ${escapeHtml(s.previous_map)}</span>` : ''}`
        : '<span class="text-slate-500">no map</span>';
    const roundTimer = s.round_elapsed_seconds != null
        ? `<span class="text-slate-400 text-xs ml-2">R${s.round_number || '?'} · <span id="live-round-elapsed">${_clock(s.round_elapsed_seconds)}</span></span>` : '';
    const sessionLine = s.session_start_seconds != null
        ? `<span class="text-slate-500 text-xs">session <span id="live-session-elapsed">${_dur(s.session_start_seconds)}</span></span>` : '';
    // Roster now LINGERS through tailer delivery gaps (backend
    // roster_age_seconds) instead of flapping away — dim it when the
    // supporting events are stale so nobody mistakes it for live truth.
    const rosterAge = r.roster_age_seconds;
    const rosterStaleNote = (rosterAge != null && rosterAge > 45)
        ? `<span class="text-[10px] text-slate-500">last data ${rosterAge}s ago</span>` : '';
    const rosterDim = (rosterAge != null && rosterAge > 45) ? 'opacity-60' : '';
    const botBadge = r.has_bots
        ? '<span class="px-1.5 py-0.5 rounded bg-fuchsia-500/20 text-fuchsia-300 text-[10px] font-black tracking-wider">BOT TEST</span>' : '';
    const specStrip = (r.spectators && r.spectators.length)
        ? `<div class="mt-3 pt-2 border-t border-white/5 text-[11px] text-slate-500 text-center truncate">👁 spectating: ${r.spectators.map(m => escapeHtml(m.name)).join(' · ')}</div>` : '';
    const objStrip = (s.recent_objectives && s.recent_objectives.length)
        ? `<div class="mt-3 pt-2 border-t border-white/5 text-[11px] text-slate-400 space-y-0.5">
            ${s.recent_objectives.slice(-4).map(o => `<div class="truncate">${_objLine(o)}</div>`).join('')}
           </div>` : '';
    const changeStrip = (s.recent_roster_changes && s.recent_roster_changes.length)
        ? `<div class="mt-3 pt-2 border-t border-white/5 text-[11px] text-slate-400 space-y-0.5">
            ${s.recent_roster_changes.slice(-4).map(c => `<div class="truncate">${_changeLine(c)}</div>`).join('')}
           </div>` : '';
    const staleWarn = _lastOk === false
        ? '<span class="text-rose-400 text-xs">state unavailable</span>' : '';

    if (!host.dataset.cardBound) {
        host.dataset.cardBound = '1';
        host.addEventListener('click', (e) => {
            const btn = e.target.closest('[data-player-card]');
            if (!btn) return;
            const name = btn.getAttribute('data-player-card');
            const snap = _snapshot || {};
            const all = [].concat(
                (snap.roster && snap.roster.axis) || [],
                (snap.roster && snap.roster.allies) || []);
            const me = all.find(m => m.name === name);
            openPlayerCard(name, { live: me && me.live ? me.live : null });
        });
    }
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
                <div class="flex items-center gap-2">${sessionLine}${rosterStaleNote}${staleWarn}</div>
            </div>
            <div class="flex items-start gap-4 ${rosterDim}">
                ${_column('🔴', 'Axis', AXIS_COLOR, r.axis || [], false)}
                <div class="text-center shrink-0 px-2 text-slate-400 self-center">
                    <div class="text-lg font-black text-slate-500">${(r.axis || []).length}<span class="text-slate-700 mx-0.5">v</span>${(r.allies || []).length}</div>
                </div>
                ${_column('🔵', 'Allies', ALLIES_COLOR, r.allies || [], true)}
            </div>
            ${objStrip}
            ${changeStrip}
            ${specStrip}
        </div>`);
}
