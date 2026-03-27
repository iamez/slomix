/**
 * Round Replay Timeline module (legacy)
 * Dual-pane replay viewer: event feed + 2D map canvas
 * @module replay
 */

import { API_BASE, fetchJSON, escapeHtml } from './utils.js';

function stripEtColors(text) {
    if (!text) return '';
    return String(text).replace(/\^[0-9A-Za-z]/g, '');
}

// ── State ──────────────────────────────────────────────────────────────────────
let replayLoadId = 0;

const replayState = {
    rounds: [],
    roundId: null,
    timeline: null,      // { round_id, map_name, duration_ms, events[] }
    tracks: null,        // { tracks[] } from /tracks endpoint
    selectedIdx: -1,     // index into timeline.events
    mapTransforms: null, // loaded once from map_transforms.json
    mapImage: null,      // Image object for current map
    mapReady: false,
};

// ── Event display config ───────────────────────────────────────────────────────
const EVENT_ICONS = {
    engagement:        '\u{1F480}', // 💀
    spawn_timing_kill: '\u{1F489}', // 💉
    trade_kill:        '\u26A1',    // ⚡
    team_push:         '\u{1F6E1}', // 🛡
};

const EVENT_COLORS = {
    engagement:        'text-rose-400',
    spawn_timing_kill: 'text-cyan-400',
    trade_kill:        'text-amber-400',
    team_push:         'text-emerald-400',
};

const EVENT_LABELS = {
    engagement:        'Kill',
    spawn_timing_kill: 'Spawn Kill',
    trade_kill:        'Trade',
    team_push:         'Push',
};

// ── Coordinate transform ───────────────────────────────────────────────────────
const CANVAS_W = 640;
const CANVAS_H = 640;

function worldToCanvas(x, y, transform) {
    if (!transform) return { cx: CANVAS_W / 2, cy: CANVAS_H / 2 };
    const [minX, maxY] = transform.mapcoordsmins;
    const [maxX, minY] = transform.mapcoordsmaxs;
    const worldW = maxX - minX;
    const worldH = maxY - minY;
    if (worldW === 0 || worldH === 0) return { cx: CANVAS_W / 2, cy: CANVAS_H / 2 };
    const cx = ((x - minX) / worldW) * CANVAS_W;
    const cy = ((maxY - y) / (maxY - minY)) * CANVAS_H;
    return { cx, cy };
}

// ── Formatting helpers ─────────────────────────────────────────────────────────
function fmtTime(ms) {
    if (ms == null || ms < 0) return '0:00';
    const totalSec = Math.floor(ms / 1000);
    const m = Math.floor(totalSec / 60);
    const s = totalSec % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
}

function eventLabel(ev) {
    const icon = EVENT_ICONS[ev.type] || '\u2022';
    const color = EVENT_COLORS[ev.type] || 'text-slate-400';
    const label = EVENT_LABELS[ev.type] || ev.type;

    let detail = '';
    if (ev.type === 'engagement') {
        const outcome = ev.outcome === 'KILL' ? 'killed' : 'escaped';
        const name = stripEtColors(ev.victim_name || '???');
        detail = `${escapeHtml(name)} ${outcome}`;
    } else if (ev.type === 'trade_kill') {
        const trader = stripEtColors(ev.trader_name || '???');
        const avenged = stripEtColors(ev.avenged_name || '???');
        detail = `${escapeHtml(trader)} avenged ${escapeHtml(avenged)}`;
    } else if (ev.type === 'spawn_timing_kill') {
        const att = stripEtColors(ev.attacker_name || '???');
        const vic = stripEtColors(ev.victim_name || '???');
        detail = `${escapeHtml(att)} \u2192 ${escapeHtml(vic)}`;
    } else if (ev.type === 'team_push') {
        const team = ev.team === 'AXIS' ? 'Axis' : 'Allies';
        detail = `${team} push (${ev.participants}p, q${(ev.quality || 0).toFixed(2)})`;
    }

    return { icon, color, label, detail };
}

// ── Map transforms loader ──────────────────────────────────────────────────────
async function ensureMapTransforms() {
    if (replayState.mapTransforms) return replayState.mapTransforms;
    try {
        const data = await fetchJSON('/assets/maps/proximity/map_transforms.json', { cachePolicy: 'swr' });
        replayState.mapTransforms = data?.maps || {};
    } catch {
        replayState.mapTransforms = {};
    }
    return replayState.mapTransforms;
}

function loadMapImage(mapName) {
    return new Promise((resolve) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = () => resolve(null);
        img.src = `/assets/maps/proximity/${encodeURIComponent(mapName)}.png`;
    });
}

// ── Main entry ─────────────────────────────────────────────────────────────────
export async function loadReplayView() {
    const container = document.getElementById('replay-container');
    if (!container) return;

    const loadId = ++replayLoadId;

    container.innerHTML = `
        <div class="text-center py-12">
            <div class="inline-block w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin mb-4"></div>
            <p class="text-slate-400 text-sm">Loading rounds...</p>
        </div>
    `;

    try {
        const [rounds] = await Promise.all([
            fetchJSON(`${API_BASE}/rounds/recent?limit=60`),
            ensureMapTransforms(),
        ]);
        if (loadId !== replayLoadId) return;
        replayState.rounds = Array.isArray(rounds) ? rounds : [];
    } catch {
        if (loadId !== replayLoadId) return;
        replayState.rounds = [];
    }

    if (replayState.rounds.length === 0) {
        container.innerHTML = '<div class="text-center text-slate-500 py-12">No rounds available for replay.</div>';
        return;
    }

    renderShell(container);

    // Auto-select latest round
    const latest = replayState.rounds[0];
    if (latest) {
        const sel = document.getElementById('replay-round-select');
        if (sel) sel.value = String(latest.id);
        await selectRound(latest.id);
    }
}

// ── Shell (static layout) ──────────────────────────────────────────────────────
function renderShell(container) {
    container.innerHTML = `
        <!-- Round selector -->
        <div class="flex items-center gap-3 mb-4">
            <label class="text-xs text-slate-400 font-bold uppercase tracking-wider">Round:</label>
            <select id="replay-round-select"
                class="bg-slate-800 border border-white/10 text-slate-200 text-xs rounded-lg px-3 py-1.5 focus:outline-none focus:border-purple-500/50 max-w-md">
                ${replayState.rounds.map(r => {
                    const label = `${escapeHtml(r.map_name || '???')} R${r.round_number || '?'} — ${escapeHtml(r.round_date || '')} (${r.player_count || 0}p)`;
                    return `<option value="${r.id}">${label}</option>`;
                }).join('')}
            </select>
        </div>

        <!-- Main dual-pane -->
        <div class="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-4">
            <!-- Left: event feed -->
            <div class="glass-panel rounded-xl border border-white/10 flex flex-col" style="max-height:680px">
                <div class="px-3 py-2 border-b border-white/10">
                    <span class="text-xs font-bold text-purple-400 uppercase tracking-widest">Event Feed</span>
                    <span id="replay-event-count" class="ml-2 text-xs text-slate-500"></span>
                </div>
                <div id="replay-event-list" class="flex-1 overflow-y-auto px-1 py-1" style="min-height:200px">
                    <div class="text-center text-slate-500 text-xs py-8">Select a round</div>
                </div>
            </div>

            <!-- Right: map canvas -->
            <div class="glass-panel rounded-xl border border-white/10 p-4 flex flex-col items-center">
                <div id="replay-map-status" class="text-xs text-slate-500 mb-2"></div>
                <canvas id="replay-canvas" width="${CANVAS_W}" height="${CANVAS_H}"
                    class="rounded-lg bg-slate-900/80 border border-white/5 max-w-full" style="image-rendering:auto"></canvas>
                <div id="replay-map-legend" class="flex gap-4 mt-3 text-xs text-slate-400">
                    <span><span class="inline-block w-2 h-2 rounded-full bg-red-500 mr-1"></span>Axis</span>
                    <span><span class="inline-block w-2 h-2 rounded-full bg-blue-500 mr-1"></span>Allies</span>
                    <span><span class="inline-block w-2 h-2 rounded-full bg-slate-500 mr-1"></span>Dead</span>
                </div>
            </div>
        </div>

        <!-- Scrubber -->
        <div class="mt-4 glass-panel rounded-xl border border-white/10 p-3">
            <div class="flex items-center gap-3 mb-1">
                <span id="replay-time-current" class="text-xs font-mono text-slate-300 w-12">0:00</span>
                <div class="flex-1 relative h-6 cursor-pointer" id="replay-scrubber">
                    <div class="absolute top-2 left-0 right-0 h-1 bg-slate-700 rounded"></div>
                    <div id="replay-scrubber-fill" class="absolute top-2 left-0 h-1 bg-purple-500 rounded" style="width:0%"></div>
                    <div id="replay-scrubber-ticks" class="absolute top-0 left-0 right-0 h-6"></div>
                    <div id="replay-scrubber-thumb" class="absolute top-0.5 w-3 h-3 bg-white rounded-full shadow-lg border-2 border-purple-500" style="left:0%"></div>
                </div>
                <span id="replay-time-total" class="text-xs font-mono text-slate-500 w-12 text-right">0:00</span>
            </div>
        </div>
    `;

    // Wire events
    const sel = document.getElementById('replay-round-select');
    if (sel) sel.addEventListener('change', () => selectRound(parseInt(sel.value, 10)));

    const scrubber = document.getElementById('replay-scrubber');
    if (scrubber) scrubber.addEventListener('click', onScrubberClick);
}

// ── Round selection ────────────────────────────────────────────────────────────
async function selectRound(roundId) {
    const loadId = ++replayLoadId;
    replayState.roundId = roundId;
    replayState.timeline = null;
    replayState.tracks = null;
    replayState.selectedIdx = -1;
    replayState.mapImage = null;
    replayState.mapReady = false;

    const eventList = document.getElementById('replay-event-list');
    if (eventList) {
        eventList.innerHTML = `
            <div class="text-center py-8">
                <div class="inline-block w-6 h-6 border-2 border-purple-500 border-t-transparent rounded-full animate-spin mb-2"></div>
                <p class="text-slate-500 text-xs">Loading timeline...</p>
            </div>
        `;
    }

    const mapStatus = document.getElementById('replay-map-status');
    if (mapStatus) mapStatus.textContent = 'Loading...';
    drawEmptyCanvas('Loading...');

    try {
        const [timeline, tracks] = await Promise.all([
            fetchJSON(`${API_BASE}/proximity/round/${roundId}/timeline`),
            fetchJSON(`${API_BASE}/proximity/round/${roundId}/tracks`).catch(() => null),
        ]);
        if (loadId !== replayLoadId) return;

        if (timeline?.status === 'error') {
            throw new Error(timeline.detail || 'Timeline error');
        }

        replayState.timeline = timeline;
        replayState.tracks = tracks;

        // Load map image
        const mapName = timeline.map_name;
        if (mapName) {
            replayState.mapImage = await loadMapImage(mapName);
        }
        replayState.mapReady = true;

        if (loadId !== replayLoadId) return;

        renderEventList();
        renderScrubber();

        if (mapStatus) {
            mapStatus.textContent = mapName
                ? (replayState.mapImage ? escapeHtml(mapName) : `${escapeHtml(mapName)} (no map image)`)
                : '';
        }

        // Auto-select first event
        if (timeline.events && timeline.events.length > 0) {
            selectEvent(0);
        } else {
            drawEmptyCanvas('No events in this round');
        }
    } catch (err) {
        if (loadId !== replayLoadId) return;
        if (eventList) eventList.innerHTML = `<div class="text-center text-rose-400 text-xs py-8">Failed to load: ${escapeHtml(String(err.message || err))}</div>`;
        drawEmptyCanvas('Error loading data');
    }
}

// ── Event list rendering ───────────────────────────────────────────────────────
function renderEventList() {
    const eventList = document.getElementById('replay-event-list');
    const eventCount = document.getElementById('replay-event-count');
    if (!eventList) return;

    const events = replayState.timeline?.events || [];
    if (eventCount) eventCount.textContent = `(${events.length})`;

    if (events.length === 0) {
        eventList.innerHTML = '<div class="text-center text-slate-500 text-xs py-8">No events recorded</div>';
        return;
    }

    eventList.innerHTML = events.map((ev, idx) => {
        const { icon, color, label, detail } = eventLabel(ev);
        const time = fmtTime(ev.time);
        return `
            <button data-idx="${idx}"
                class="replay-ev-btn w-full text-left px-2 py-1.5 rounded-lg hover:bg-white/5 transition flex items-start gap-2 group ${idx === replayState.selectedIdx ? 'bg-purple-500/20 border border-purple-500/40' : ''}"
            >
                <span class="text-[10px] font-mono text-slate-500 w-10 shrink-0 mt-0.5">${time}</span>
                <span class="text-sm">${icon}</span>
                <span class="flex-1 min-w-0">
                    <span class="text-[11px] font-bold ${color}">${escapeHtml(label)}</span>
                    <span class="text-[10px] text-slate-400 block truncate">${detail}</span>
                </span>
            </button>
        `;
    }).join('');

    // Wire click events
    eventList.querySelectorAll('.replay-ev-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const idx = parseInt(btn.dataset.idx, 10);
            selectEvent(idx);
        });
    });
}

// ── Event selection ────────────────────────────────────────────────────────────
function selectEvent(idx) {
    const events = replayState.timeline?.events || [];
    if (idx < 0 || idx >= events.length) return;

    replayState.selectedIdx = idx;
    const ev = events[idx];

    // Update event list highlight
    const list = document.getElementById('replay-event-list');
    if (list) {
        list.querySelectorAll('.replay-ev-btn').forEach((btn, i) => {
            if (i === idx) {
                btn.classList.add('bg-purple-500/20', 'border', 'border-purple-500/40');
                btn.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
            } else {
                btn.classList.remove('bg-purple-500/20', 'border', 'border-purple-500/40');
            }
        });
    }

    // Update scrubber position
    updateScrubberPosition(ev.time);

    // Draw map at event time
    drawMapAtTime(ev.time, idx);
}

// ── Canvas drawing ─────────────────────────────────────────────────────────────
function drawEmptyCanvas(message) {
    const canvas = document.getElementById('replay-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, CANVAS_W, CANVAS_H);
    ctx.fillStyle = '#0f172a';
    ctx.fillRect(0, 0, CANVAS_W, CANVAS_H);
    ctx.fillStyle = '#64748b';
    ctx.font = '14px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(message || 'Click an event to see player positions', CANVAS_W / 2, CANVAS_H / 2);
}

function drawMapAtTime(timeMs, eventIdx) {
    const canvas = document.getElementById('replay-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, CANVAS_W, CANVAS_H);

    // Draw map background
    if (replayState.mapImage) {
        ctx.drawImage(replayState.mapImage, 0, 0, CANVAS_W, CANVAS_H);
        // Darken overlay for visibility
        ctx.fillStyle = 'rgba(15, 23, 42, 0.35)';
        ctx.fillRect(0, 0, CANVAS_W, CANVAS_H);
    } else {
        ctx.fillStyle = '#0f172a';
        ctx.fillRect(0, 0, CANVAS_W, CANVAS_H);
        // Grid
        ctx.strokeStyle = 'rgba(255,255,255,0.03)';
        ctx.lineWidth = 1;
        for (let i = 0; i < CANVAS_W; i += 64) {
            ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, CANVAS_H); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(0, i); ctx.lineTo(CANVAS_W, i); ctx.stroke();
        }
    }

    const mapName = replayState.timeline?.map_name;
    const transform = mapName ? (replayState.mapTransforms || {})[mapName] : null;

    // Draw player tracks at this time
    const tracks = replayState.tracks?.tracks;
    if (tracks && tracks.length > 0 && transform) {
        drawTracks(ctx, tracks, timeMs, transform);
    }

    // Draw event marker
    const events = replayState.timeline?.events || [];
    if (eventIdx >= 0 && eventIdx < events.length) {
        drawEventMarker(ctx, events[eventIdx], transform);
    }

    // Time overlay
    ctx.fillStyle = 'rgba(15,23,42,0.7)';
    ctx.fillRect(0, 0, 90, 28);
    ctx.fillStyle = '#c084fc';
    ctx.font = 'bold 13px JetBrains Mono, monospace';
    ctx.textAlign = 'left';
    ctx.fillText(fmtTime(timeMs), 8, 19);
}

function drawTracks(ctx, tracks, timeMs, transform) {
    for (const track of tracks) {
        const path = track.path;
        if (!path || !Array.isArray(path) || path.length === 0) continue;

        // Check if track is alive at this time
        const spawnT = track.spawn_time || 0;
        const deathT = track.death_time || Infinity;
        const isAlive = timeMs >= spawnT && timeMs <= deathT;

        // Find closest point in path to current time
        let closestPt = null;
        let minDelta = Infinity;
        const trailPoints = [];

        for (const pt of path) {
            const ptTime = pt.t || pt[0] || 0;
            const ptX = pt.x ?? pt[1];
            const ptY = pt.y ?? pt[2];
            if (ptX == null || ptY == null) continue;

            if (ptTime <= timeMs) {
                trailPoints.push({ x: ptX, y: ptY, t: ptTime });
            }
            const delta = Math.abs(ptTime - timeMs);
            if (delta < minDelta) {
                minDelta = delta;
                closestPt = { x: ptX, y: ptY };
            }
        }

        if (!closestPt) continue;

        const isAxis = (track.team || '').toUpperCase() === 'AXIS';
        const teamColor = isAxis ? '#ef4444' : '#3b82f6';
        const deadColor = '#64748b';
        const dotColor = isAlive ? teamColor : deadColor;

        // Draw trail (last few points)
        const recentTrail = trailPoints.slice(-8);
        if (recentTrail.length > 1) {
            ctx.beginPath();
            ctx.strokeStyle = dotColor + '40'; // 25% opacity
            ctx.lineWidth = 1.5;
            for (let i = 0; i < recentTrail.length; i++) {
                const { cx, cy } = worldToCanvas(recentTrail[i].x, recentTrail[i].y, transform);
                if (i === 0) ctx.moveTo(cx, cy);
                else ctx.lineTo(cx, cy);
            }
            ctx.stroke();
        }

        // Draw player dot
        const { cx, cy } = worldToCanvas(closestPt.x, closestPt.y, transform);
        ctx.beginPath();
        if (isAlive) {
            ctx.arc(cx, cy, 5, 0, Math.PI * 2);
            ctx.fillStyle = dotColor;
            ctx.fill();
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 1.5;
            ctx.stroke();
        } else {
            // Dead marker: X
            ctx.strokeStyle = deadColor;
            ctx.lineWidth = 2;
            ctx.moveTo(cx - 4, cy - 4); ctx.lineTo(cx + 4, cy + 4);
            ctx.moveTo(cx + 4, cy - 4); ctx.lineTo(cx - 4, cy + 4);
            ctx.stroke();
        }

        // Player name
        const name = stripEtColors(track.name || '');
        if (name) {
            ctx.fillStyle = isAlive ? '#e2e8f0' : '#64748b';
            ctx.font = '9px Inter, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(name, cx, cy - 9);
        }
    }
}

function drawEventMarker(ctx, ev, transform) {
    // Try to find coordinates from event
    // engagement events have start_x, start_y from combat_engagement
    // For now, show a pulse circle at the event position if available
    // The timeline API doesn't always include coords, so we show a notification area instead

    const icon = EVENT_ICONS[ev.type] || '\u2022';
    const { detail } = eventLabel(ev);

    // Event info overlay at bottom
    ctx.fillStyle = 'rgba(15,23,42,0.85)';
    const boxY = CANVAS_H - 44;
    ctx.fillRect(0, boxY, CANVAS_W, 44);
    ctx.strokeStyle = 'rgba(168,85,247,0.4)';
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(0, boxY); ctx.lineTo(CANVAS_W, boxY); ctx.stroke();

    ctx.fillStyle = '#c084fc';
    ctx.font = '12px Inter, sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText(`${icon} ${EVENT_LABELS[ev.type] || ev.type}`, 12, boxY + 18);

    ctx.fillStyle = '#94a3b8';
    ctx.font = '11px Inter, sans-serif';
    // Strip HTML entities from detail
    const plainDetail = detail.replace(/&[^;]+;/g, m => {
        const el = document.createElement('span');
        el.innerHTML = m;
        return el.textContent || '';
    });
    ctx.fillText(plainDetail.slice(0, 80), 12, boxY + 34);
}

// ── Scrubber ───────────────────────────────────────────────────────────────────
function renderScrubber() {
    const totalEl = document.getElementById('replay-time-total');
    const ticksEl = document.getElementById('replay-scrubber-ticks');
    const durationMs = replayState.timeline?.duration_ms || 0;

    if (totalEl) totalEl.textContent = fmtTime(durationMs);
    if (!ticksEl || durationMs <= 0) return;

    const events = replayState.timeline?.events || [];
    const ticks = events.map((ev, idx) => {
        const pct = Math.min(100, (ev.time / durationMs) * 100);
        const color = ({
            engagement: '#f43f5e',
            trade_kill: '#f59e0b',
            spawn_timing_kill: '#06b6d4',
            team_push: '#10b981',
        })[ev.type] || '#64748b';
        const h = ev.type === 'engagement' ? 12 : 8;
        return `<div data-tick-idx="${idx}" class="absolute cursor-pointer" style="left:${pct}%;top:${(24 - h) / 2}px;width:2px;height:${h}px;background:${color};border-radius:1px;transform:translateX(-1px)" title="${fmtTime(ev.time)} ${EVENT_LABELS[ev.type] || ev.type}"></div>`;
    });
    ticksEl.innerHTML = ticks.join('');

    // Wire tick clicks
    ticksEl.querySelectorAll('[data-tick-idx]').forEach(tick => {
        tick.addEventListener('click', (e) => {
            e.stopPropagation();
            const idx = parseInt(tick.dataset.tickIdx, 10);
            selectEvent(idx);
        });
    });
}

function updateScrubberPosition(timeMs) {
    const durationMs = replayState.timeline?.duration_ms || 0;
    const pct = durationMs > 0 ? Math.min(100, (timeMs / durationMs) * 100) : 0;

    const fill = document.getElementById('replay-scrubber-fill');
    const thumb = document.getElementById('replay-scrubber-thumb');
    const currentEl = document.getElementById('replay-time-current');

    if (fill) fill.style.width = `${pct}%`;
    if (thumb) thumb.style.left = `calc(${pct}% - 6px)`;
    if (currentEl) currentEl.textContent = fmtTime(timeMs);
}

function onScrubberClick(e) {
    const scrubber = document.getElementById('replay-scrubber');
    if (!scrubber) return;
    const rect = scrubber.getBoundingClientRect();
    const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const durationMs = replayState.timeline?.duration_ms || 0;
    const targetTime = pct * durationMs;

    // Find closest event to this time
    const events = replayState.timeline?.events || [];
    if (events.length === 0) return;

    let closest = 0;
    let minDelta = Infinity;
    for (let i = 0; i < events.length; i++) {
        const delta = Math.abs(events[i].time - targetTime);
        if (delta < minDelta) {
            minDelta = delta;
            closest = i;
        }
    }
    selectEvent(closest);
}
