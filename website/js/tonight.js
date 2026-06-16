/**
 * Tonight live hub (VISION_2026 S7 LIVE) — live LOGICAL-TEAM score (not Axis/Allies,
 * which swap every round in stopwatch), per-map stopwatch strip, the current-map
 * R2 time-to-beat chase, team momentum and a hold-probability curve. Polled ~8s
 * while the view is active. Also exposes a compact Home card shown only when a
 * session is live. Production frontend = legacy JS.
 * @module tonight
 */
import { API_BASE, fetchJSON, escapeHtml, safeInsertHTML } from './utils.js';

const POLL_MS = 8000;
let _interval = null;
let _lifecycleBound = false;

const A_COLOR = '#06b6d4';  // Team A — cyan
const B_COLOR = '#8b5cf6';  // Team B — purple

function _viewActive() {
    const v = document.getElementById('view-tonight');
    return v && v.classList.contains('active') && !v.classList.contains('hidden') && !document.hidden;
}

function _stopPolling() {
    if (_interval) { clearInterval(_interval); _interval = null; }
}

function _startPolling() {
    _stopPolling();
    _interval = setInterval(() => {
        if (!_viewActive()) { _stopPolling(); return; }
        _refresh().catch(e => console.warn('tonight refresh failed', e));
    }, POLL_MS);
}

export async function loadTonightView() {
    const host = document.getElementById('tonight-content');
    if (!host) return;
    await _refresh();
    _startPolling();
    // Bind the visibility lifecycle once (loadTonightView runs on every entry).
    if (!_lifecycleBound) {
        _lifecycleBound = true;
        document.addEventListener('visibilitychange', () => {
            if (_viewActive()) _startPolling(); else _stopPolling();
        });
    }
}

function _mmss(sec) {
    if (sec == null) return '—';
    const s = Math.max(0, Math.round(sec));
    return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

// Live server pulse from the UDP query (/live-status) — the actual "right now"
// state, which the lua feed (round-end only) can't show. Empty string when the
// server is offline so the strip simply doesn't render.
function _serverStrip(gs) {
    if (!gs || !gs.online) return '';
    const map = escapeHtml(gs.map || '—');
    const pc = gs.player_count || 0, mx = gs.max_players || 0;
    const hostname = escapeHtml(gs.hostname || 'server');
    const names = (gs.players || [])
        .map(p => escapeHtml((p && p.name) || ''))
        .filter(Boolean)
        .join(' · ');
    return `<div class="glass-panel p-4 rounded-xl mb-6 flex items-center justify-between flex-wrap gap-2">
        <div class="flex items-center gap-2">
            <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 text-[10px] font-bold">
                <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>SERVER LIVE
            </span>
            <span class="text-sm text-slate-300">${hostname} · <span class="text-white font-bold">${map}</span></span>
        </div>
        <span class="text-xs text-slate-400">${pc}/${mx} on server${names ? ` — ${names}` : ''}</span>
    </div>`;
}

// One round's outcome as a small team-coloured pill (R1 · winner · time).
function _roundPill(rd) {
    const color = rd.winner === 'a' ? A_COLOR : rd.winner === 'b' ? B_COLOR : '#64748b';
    const who = rd.winner === 'a' ? 'A' : rd.winner === 'b' ? 'B' : '–';
    return `<div class="flex items-center justify-between text-[11px] py-0.5">
        <span class="text-slate-500">R${rd.round}</span>
        <span class="font-bold" style="color:${color}">Team ${who}</span>
        <span class="text-slate-400 font-mono">${_mmss(rd.duration)}</span>
    </div>`;
}

function _teamPanel(team, maps, rounds, lead, side) {
    const color = side === 'a' ? A_COLOR : B_COLOR;
    const roster = (team.roster || []).map(n => escapeHtml(n)).join(' · ') || '—';
    return `<div class="flex-1 text-center ${lead ? '' : 'opacity-80'}">
        <div class="text-[10px] uppercase tracking-widest text-slate-500 mb-1">${escapeHtml(team.name || 'Team')}</div>
        <div class="text-5xl font-black leading-none" style="color:${color}">${maps}</div>
        <div class="text-[10px] uppercase tracking-widest text-slate-500 mt-1">maps · ${rounds} rounds</div>
        <div class="text-[11px] text-slate-400 mt-2 leading-snug">${roster}</div>
    </div>`;
}

async function _refresh() {
    const host = document.getElementById('tonight-content');
    if (!host) return;
    // Fetch the round feed and the live server pulse in parallel — independent
    // so the slow UDP server query never blocks (or breaks) the lua-based payload.
    const [tRes, lRes] = await Promise.allSettled([
        fetchJSON(`${API_BASE}/stats/tonight`, { cachePolicy: 'no-store', credentials: 'same-origin' }),
        fetchJSON(`${API_BASE}/live-status`, { cachePolicy: 'no-store', credentials: 'same-origin' }),
    ]);
    const data = tRes.status === 'fulfilled' ? tRes.value : null;
    const gs = (lRes.status === 'fulfilled' && lRes.value) ? lRes.value.game_server : null;

    if (!data) {
        host.textContent = '';
        safeInsertHTML(host, 'beforeend', `<div class="glass-panel p-6 rounded-xl text-center text-slate-400">Live data unavailable right now.</div>`);
        return;
    }

    const serverOnline = !!(gs && gs.online);
    const serverPlayers = serverOnline ? (gs.player_count || 0) : 0;

    if (!data.active) {
        // Server has players but no completed round yet → keep polling, the
        // results strip will fill in as rounds land. Otherwise truly idle.
        if (serverPlayers > 0) {
            host.textContent = '';
            safeInsertHTML(host, 'beforeend', _serverStrip(gs) + `
                <div class="glass-panel p-8 rounded-xl text-center">
                    <div class="text-xl font-black text-white mb-1">Session warming up…</div>
                    <div class="text-slate-400">Rounds will appear here as they complete.</div>
                </div>`);
            return;
        }
        _stopPolling();
        host.textContent = '';
        safeInsertHTML(host, 'beforeend', (serverOnline ? _serverStrip(gs) : '') + `
            <div class="glass-panel p-8 rounded-xl text-center">
                <div class="text-2xl font-black text-white mb-2">No session live right now</div>
                <div class="text-slate-400 mb-4">Come back when the games are on.</div>
                <div class="flex justify-center gap-3">
                    <a href="#/availability" class="px-4 py-2 rounded-lg text-sm font-bold bg-brand-cyan/20 text-brand-cyan">Next session</a>
                    <a href="#/sessions2" class="px-4 py-2 rounded-lg text-sm font-bold bg-white/10 text-slate-200">Last session</a>
                </div>
            </div>`);
        return;
    }

    const score = data.score || {};
    const teams = data.teams || { a: {}, b: {} };
    const cur = data.current || {};
    const age = Number(data.age_seconds || 0);
    const fresh = age < 90;
    const aMaps = score.a_maps || 0, bMaps = score.b_maps || 0;
    const aLead = aMaps >= bMaps;

    // Per-map stopwatch strip (team terms).
    const mapCards = (data.maps || []).map(mp => {
        const winColor = mp.winner === 'a' ? `border-l-4` : mp.winner === 'b' ? `border-l-4` : 'border-l-4 border-white/10';
        const winStyle = mp.winner === 'a' ? `border-color:${A_COLOR}` : mp.winner === 'b' ? `border-color:${B_COLOR}` : '';
        const badge = mp.winner === 'pending'
            ? `<span class="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300">live</span>`
            : `<span class="text-sm font-black font-mono text-white">${mp.a_points}–${mp.b_points}</span>`;
        return `<div class="flex-shrink-0 w-40 glass-card p-3 rounded-lg ${winColor}" style="${winStyle}">
            <div class="flex items-center justify-between mb-1">
                <span class="text-xs font-bold text-white truncate">${escapeHtml(mp.map)}</span>
                ${badge}
            </div>
            ${(mp.rounds || []).map(_roundPill).join('')}
        </div>`;
    }).join('');

    // Current-map card with the R2 chase callout.
    const chase = cur.r2_pending && cur.beat_seconds != null
        ? `<div class="mt-3 text-sm"><span class="text-amber-300 font-bold">🏁 Attack must beat ${_mmss(cur.beat_seconds)}</span> <span class="text-slate-400">to take the map.</span></div>`
        : '';

    host.textContent = '';
    safeInsertHTML(host, 'beforeend', _serverStrip(gs) + `
        <div class="glass-panel p-6 rounded-xl mb-6">
            <div class="flex items-center justify-between flex-wrap gap-3 mb-5">
                <div class="flex items-center gap-3">
                    <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full ${fresh ? 'bg-rose-500/15 text-rose-300' : 'bg-white/10 text-slate-400'} text-xs font-bold">
                        <span class="w-2 h-2 rounded-full ${fresh ? 'bg-rose-400 animate-pulse' : 'bg-slate-500'}"></span>${fresh ? 'LIVE' : 'IDLE'}
                    </span>
                    <span class="text-sm text-slate-400">on <span class="text-white font-bold">${escapeHtml(cur.map || data.current_map || '—')}</span> <span class="text-slate-500">${escapeHtml(cur.status || '')}</span></span>
                </div>
                <span class="text-xs text-slate-500">updated ${_mmss(age)} ago</span>
            </div>
            <div class="flex items-stretch gap-4">
                ${_teamPanel(teams.a || {}, aMaps, score.a_rounds || 0, aLead, 'a')}
                <div class="flex items-center text-slate-600 text-xl font-black">vs</div>
                ${_teamPanel(teams.b || {}, bMaps, score.b_rounds || 0, !aLead, 'b')}
            </div>
            <div class="text-center text-xs text-slate-500 mt-3">${score.maps_completed || 0} maps completed tonight</div>
            ${chase}
        </div>

        <div class="glass-panel p-5 rounded-xl mb-6">
            <div class="text-xs uppercase tracking-widest text-slate-500 font-bold mb-2">Tonight's maps</div>
            <div class="flex gap-3 overflow-x-auto pb-1">${mapCards || '<span class="text-sm text-slate-500">No maps yet.</span>'}</div>
        </div>

        <div class="glass-panel p-5 rounded-xl mb-6">
            <div class="flex items-center justify-between mb-2">
                <div class="text-xs uppercase tracking-widest text-slate-500 font-bold">Team momentum</div>
                <div class="text-[11px]"><span style="color:${A_COLOR}">■ ${escapeHtml((teams.a || {}).name || 'Team A')}</span> <span class="ml-2" style="color:${B_COLOR}">■ ${escapeHtml((teams.b || {}).name || 'Team B')}</span></div>
            </div>
            <canvas id="tonight-momentum" height="120" class="w-full"></canvas>
        </div>

        <div class="glass-panel p-5 rounded-xl">
            <div class="text-xs uppercase tracking-widest text-slate-500 font-bold mb-1">Hold probability — ${escapeHtml(cur.map || data.current_map || '')}</div>
            <div class="text-[11px] text-slate-500 mb-2">Historical chance the attack has completed by a given time${cur.beat_seconds != null ? ` · tonight's R1 = ${_mmss(cur.beat_seconds)}` : ''}.</div>
            <canvas id="tonight-holdprob" height="120" class="w-full"></canvas>
        </div>`);

    _drawMomentum('tonight-momentum', data.momentum || []);
    _drawHoldProb('tonight-holdprob', (data.hold_probability && data.hold_probability.curve) || [], cur.beat_seconds);
}

function _drawMomentum(canvasId, momentum) {
    const cv = document.getElementById(canvasId);
    if (!cv || !momentum.length) return;
    const w = cv.clientWidth; if (!w) return;
    cv.width = w; const h = cv.height || 120;
    const ctx = cv.getContext('2d'); if (!ctx) return;
    const pad = 6;
    const x = (i) => pad + (w - 2 * pad) * (momentum.length === 1 ? 0.5 : i / (momentum.length - 1));
    const y = (v) => h - pad - (h - 2 * pad) * (v / 100);
    ctx.clearRect(0, 0, w, h);
    // midline
    ctx.strokeStyle = 'rgba(255,255,255,0.08)';
    ctx.beginPath(); ctx.moveTo(pad, y(50)); ctx.lineTo(w - pad, y(50)); ctx.stroke();
    const line = (key, color) => {
        ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.beginPath();
        momentum.forEach((p, i) => { i ? ctx.lineTo(x(i), y(p[key])) : ctx.moveTo(x(i), y(p[key])); });
        ctx.stroke();
    };
    line('a', A_COLOR);
    line('b', B_COLOR);
}

function _drawHoldProb(canvasId, curve, markerSeconds) {
    const cv = document.getElementById(canvasId);
    if (!cv) return;
    const w = cv.clientWidth; if (!w) return;
    cv.width = w; const h = cv.height || 120;
    const ctx = cv.getContext('2d'); if (!ctx) return;
    ctx.clearRect(0, 0, w, h);
    if (!curve.length) {
        ctx.fillStyle = '#64748b'; ctx.font = '12px sans-serif'; ctx.textAlign = 'center';
        ctx.fillText('Not enough history for this map', w / 2, h / 2);
        return;
    }
    const pad = 6;
    const maxT = curve[curve.length - 1].t || 1;
    const x = (tt) => pad + (w - 2 * pad) * (tt / maxT);
    const y = (p) => h - pad - (h - 2 * pad) * (p / 100);
    ctx.strokeStyle = '#22d3ee'; ctx.lineWidth = 2; ctx.beginPath();
    curve.forEach((pt, i) => { i ? ctx.lineTo(x(pt.t), y(pt.p)) : ctx.moveTo(x(pt.t), y(pt.p)); });
    ctx.stroke();
    // Tonight's R1 time marker — where the chase target sits on the curve.
    if (markerSeconds != null && markerSeconds > 0 && markerSeconds <= maxT) {
        const mx = x(markerSeconds);
        ctx.strokeStyle = '#fbbf24'; ctx.lineWidth = 1.5; ctx.setLineDash([4, 3]);
        ctx.beginPath(); ctx.moveTo(mx, pad); ctx.lineTo(mx, h - pad); ctx.stroke();
        ctx.setLineDash([]);
    }
}

// Home card — appears only when a session is live (S7 part C).
export async function loadHomeTonightCard() {
    const host = document.getElementById('home-tonight-card');
    if (!host) return;
    let data;
    try {
        data = await fetchJSON(`${API_BASE}/stats/tonight`, { cachePolicy: 'no-store', credentials: 'same-origin' });
    } catch (_e) { host.textContent = ''; return; }
    if (!data || !data.active) { host.textContent = ''; return; }
    const score = data.score || {};
    const teams = data.teams || { a: {}, b: {} };
    const cur = data.current || {};
    const aMaps = score.a_maps || 0, bMaps = score.b_maps || 0;
    const leadName = aMaps >= bMaps ? (teams.a || {}).name : (teams.b || {}).name;
    host.textContent = '';
    safeInsertHTML(host, 'beforeend', `
        <div class="glass-panel p-5 rounded-xl border-l-4 border-rose-500/60">
            <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                    <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-rose-500/15 text-rose-300 text-[10px] font-bold">
                        <span class="w-1.5 h-1.5 rounded-full bg-rose-400 animate-pulse"></span>LIVE
                    </span>
                    <span class="text-sm text-white font-bold">${aMaps}–${bMaps}</span>
                    <span class="text-xs text-slate-400">maps · on ${escapeHtml(cur.map || data.current_map || '—')}</span>
                    ${leadName ? `<span class="text-xs text-slate-500">(${escapeHtml(leadName)} lead)</span>` : ''}
                </div>
                <a href="#/tonight" class="text-xs font-bold text-rose-300 hover:text-white transition">Open Tonight →</a>
            </div>
        </div>`);
}
