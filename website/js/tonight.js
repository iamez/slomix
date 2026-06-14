/**
 * Tonight live hub (VISION_2026 S7 LIVE) — live score + map-chip strip + a light
 * score-swing momentum + hold-probability curve, polled every ~8s while the view
 * is active. Also exposes a compact Home card that appears only when a session is
 * live. Production frontend = legacy JS. Reuses the live-status polling lifecycle idea.
 * @module tonight
 */
import { API_BASE, fetchJSON, escapeHtml, safeInsertHTML } from './utils.js';

const POLL_MS = 8000;
let _interval = null;
let _lifecycleBound = false;

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
    const s = Math.max(0, Math.round(sec));
    return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

async function _refresh() {
    const host = document.getElementById('tonight-content');
    if (!host) return;
    let data;
    try {
        data = await fetchJSON(`${API_BASE}/stats/tonight`, { cachePolicy: 'no-store', credentials: 'same-origin' });
    } catch (_e) {
        host.textContent = '';
        safeInsertHTML(host, 'beforeend', `<div class="glass-panel p-6 rounded-xl text-center text-slate-400">Live data unavailable right now.</div>`);
        return;
    }

    if (!data || !data.active) {
        _stopPolling();
        host.textContent = '';
        safeInsertHTML(host, 'beforeend', `
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

    const t = data.tally || {};
    const age = Number(data.age_seconds || 0);
    const fresh = age < 90;
    const maps = data.maps || [];

    const chips = maps.map(mp => {
        const w = mp.winner_team === 1 ? 'border-brand-cyan/60' : mp.winner_team === 2 ? 'border-brand-purple/60' : 'border-white/10';
        return `<div class="flex-shrink-0 glass-card px-3 py-2 rounded-lg border ${w}">
            <div class="text-xs font-bold text-white">${escapeHtml(mp.map)} <span class="text-slate-500">R${mp.round}</span></div>
            <div class="text-[11px] text-slate-400 font-mono">${mp.axis_score}–${mp.allies_score}</div>
        </div>`;
    }).join('');

    host.textContent = '';
    safeInsertHTML(host, 'beforeend', `
        <div class="glass-panel p-6 rounded-xl mb-6">
            <div class="flex items-center justify-between flex-wrap gap-3 mb-4">
                <div class="flex items-center gap-3">
                    <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full ${fresh ? 'bg-rose-500/15 text-rose-300' : 'bg-white/10 text-slate-400'} text-xs font-bold">
                        <span class="w-2 h-2 rounded-full ${fresh ? 'bg-rose-400 animate-pulse' : 'bg-slate-500'}"></span>${fresh ? 'LIVE' : 'IDLE'}
                    </span>
                    <span class="text-sm text-slate-400">on <span class="text-white font-bold">${escapeHtml(data.current_map || '—')}</span></span>
                </div>
                <span class="text-xs text-slate-500">updated ${_mmss(age)} ago</span>
            </div>
            <div class="flex items-center justify-center gap-6 mb-1">
                <div class="text-center"><div class="text-3xl font-black text-brand-cyan">${t.axis_rounds || 0}</div><div class="text-[10px] uppercase tracking-widest text-slate-500">Axis rounds</div></div>
                <div class="text-slate-600 text-2xl">·</div>
                <div class="text-center"><div class="text-3xl font-black text-brand-purple">${t.allies_rounds || 0}</div><div class="text-[10px] uppercase tracking-widest text-slate-500">Allies rounds</div></div>
            </div>
            <div class="text-center text-xs text-slate-500">${t.maps_played || 0} maps played tonight</div>
        </div>

        <div class="glass-panel p-5 rounded-xl mb-6">
            <div class="text-xs uppercase tracking-widest text-slate-500 font-bold mb-2">Tonight's maps</div>
            <div class="flex gap-2 overflow-x-auto pb-1">${chips || '<span class="text-sm text-slate-500">No rounds yet.</span>'}</div>
        </div>

        <div class="glass-panel p-5 rounded-xl mb-6">
            <div class="flex items-center justify-between mb-2">
                <div class="text-xs uppercase tracking-widest text-slate-500 font-bold">Round momentum</div>
                <div class="text-[11px]"><span class="text-brand-cyan">■ Axis</span> <span class="text-brand-purple ml-2">■ Allies</span></div>
            </div>
            <canvas id="tonight-momentum" height="120" class="w-full"></canvas>
        </div>

        <div class="glass-panel p-5 rounded-xl">
            <div class="text-xs uppercase tracking-widest text-slate-500 font-bold mb-1">Hold probability — ${escapeHtml(data.current_map || '')}</div>
            <div class="text-[11px] text-slate-500 mb-2">Historical chance the attack has completed by a given time.</div>
            <canvas id="tonight-holdprob" height="120" class="w-full"></canvas>
        </div>`);

    _drawMomentum('tonight-momentum', data.momentum || []);
    _drawHoldProb('tonight-holdprob', (data.hold_probability && data.hold_probability.curve) || []);
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
    line('axis', '#06b6d4');
    line('allies', '#8b5cf6');
}

function _drawHoldProb(canvasId, curve) {
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
    const t = data.tally || {};
    host.textContent = '';
    safeInsertHTML(host, 'beforeend', `
        <div class="glass-panel p-5 rounded-xl border-l-4 border-rose-500/60">
            <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                    <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-rose-500/15 text-rose-300 text-[10px] font-bold">
                        <span class="w-1.5 h-1.5 rounded-full bg-rose-400 animate-pulse"></span>LIVE
                    </span>
                    <span class="text-sm text-white font-bold">${t.axis_rounds || 0}–${t.allies_rounds || 0}</span>
                    <span class="text-xs text-slate-400">on ${escapeHtml(data.current_map || '—')}</span>
                </div>
                <a href="#/tonight" class="text-xs font-bold text-rose-300 hover:text-white transition">Open Tonight →</a>
            </div>
        </div>`);
}
