/**
 * Proximity analytics module (prototype)
 * @module proximity
 */

import { API_BASE, fetchJSON, formatNumber, escapeHtml } from './utils.js';

const DEFAULT_RANGE_DAYS = 30;
const DEFAULT_EVENTS_LIMIT = 20;

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function stripEtColors(text) {
    if (!text) return '';
    return String(text).replace(/\^[0-9A-Za-z]/g, '');
}

function formatMs(ms) {
    if (ms == null) return '--';
    const value = Number(ms);
    if (!Number.isFinite(value)) return '--';
    if (value >= 1000) return `${(value / 1000).toFixed(1)}s`;
    return `${Math.round(value)}ms`;
}

function formatDurationMs(ms) {
    if (ms == null) return '--';
    const value = Number(ms);
    if (!Number.isFinite(value)) return '--';
    const totalSeconds = Math.max(0, Math.round(value / 1000));
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    if (mins <= 0) return `${secs}s`;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function renderLeaderList(containerId, rows, formatter, emptyLabel = 'No data yet') {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!rows || rows.length === 0) {
        container.innerHTML = `<div class="text-[11px] text-slate-500">${escapeHtml(emptyLabel)}</div>`;
        return;
    }

    container.innerHTML = rows.map((row, idx) => {
        const label = stripEtColors(row.name || row.player || `Player ${idx + 1}`);
        const value = formatter(row);
        return `
            <div class="flex items-center justify-between text-[11px] text-slate-300">
                <span>${escapeHtml(label)}</span>
                <span class="text-slate-500">${escapeHtml(value)}</span>
            </div>
        `;
    }).join('');
}

function renderTradeSummary(summary) {
    if (!summary) return;
    const opportunities = summary.trade_opportunities ?? summary.opportunities ?? null;
    const attempts = summary.trade_attempts ?? summary.attempts ?? null;
    const success = summary.trade_success ?? summary.success ?? null;
    const missed = summary.missed_trade_candidates ?? summary.missed ?? null;
    const support = summary.support_uptime_pct ?? summary.support_uptime ?? null;
    const isolation = summary.isolation_deaths ?? summary.isolated_deaths ?? null;

    setText('proximity-trade-opportunities', opportunities != null ? formatNumber(opportunities) : '--');
    setText('proximity-trade-attempts', attempts != null ? formatNumber(attempts) : '--');
    setText('proximity-trade-success', success != null ? formatNumber(success) : '--');
    setText('proximity-trade-missed', missed != null ? formatNumber(missed) : '--');
    setText('proximity-support-uptime', support != null ? `${support.toFixed(1)}%` : '--');
    setText('proximity-isolation-deaths', isolation != null ? formatNumber(isolation) : '--');
}

function renderTradeEvents(events) {
    const container = document.getElementById('proximity-trade-events');
    if (!container) return;
    if (!events || events.length === 0) {
        container.innerHTML = `<div class="text-xs text-slate-600">No trade events yet.</div>`;
        return;
    }
    container.innerHTML = events.map((e) => {
        const map = stripEtColors(e.map || 'unknown');
        const victim = stripEtColors(e.victim || e.victim_name || 'unknown');
        const killer = stripEtColors(e.killer || e.killer_name || 'unknown');
        const outcome = e.outcome || 'trade';
        const round = e.round != null ? `R${e.round}` : 'R?';
        const date = e.round_date || e.date || '';
        const time = e.round_time || e.time || '';
        const roundButton = e.round_id != null
            ? `<button class="text-[10px] text-brand-cyan hover:text-white" data-round-id="${e.round_id}">View round</button>`
            : '';
        return `
            <div class="glass-card p-3 rounded-lg border border-white/5">
                <div class="flex items-center justify-between text-[10px] text-slate-500">
                    <span>${escapeHtml(map)} • ${escapeHtml(round)} • ${escapeHtml(date)} ${escapeHtml(time)}</span>
                    ${roundButton}
                </div>
                <div class="text-sm font-semibold text-white mt-1">${escapeHtml(victim)} → ${escapeHtml(killer)}</div>
                <div class="text-[10px] text-slate-400 mt-1">${escapeHtml(outcome)}</div>
            </div>
        `;
    }).join('');

    container.querySelectorAll('[data-round-id]').forEach((btn) => {
        btn.addEventListener('click', (event) => {
            event.stopPropagation();
            const roundId = btn.getAttribute('data-round-id');
            if (!roundId || typeof window.loadMatchDetails !== 'function') return;
            window.loadMatchDetails(parseInt(roundId, 10));
        });
    });
}

function renderDuos(duos) {
    const container = document.getElementById('proximity-top-duos');
    if (!container) return;

    if (!duos || duos.length === 0) {
        container.innerHTML = `
            <div class="glass-card p-4 rounded-lg text-center">
                <div class="text-sm font-bold text-white">--</div>
                <div class="text-xs text-slate-500 mt-1">No data yet</div>
            </div>
            <div class="glass-card p-4 rounded-lg text-center">
                <div class="text-sm font-bold text-white">--</div>
                <div class="text-xs text-slate-500 mt-1">No data yet</div>
            </div>
            <div class="glass-card p-4 rounded-lg text-center">
                <div class="text-sm font-bold text-white">--</div>
                <div class="text-xs text-slate-500 mt-1">No data yet</div>
            </div>
        `;
        return;
    }

    container.innerHTML = duos.slice(0, 6).map((duo, idx) => {
        const player1 = stripEtColors(duo.player1 || '');
        const player2 = stripEtColors(duo.player2 || '');
        const players = player1 && player2 ? `${player1} + ${player2}` : (duo.label || `Duo ${idx + 1}`);
        const kills = duo.crossfire_kills != null ? formatNumber(duo.crossfire_kills) : '--';
        const count = duo.crossfire_count != null ? formatNumber(duo.crossfire_count) : '--';
        const delay = duo.avg_delay_ms != null ? `${duo.avg_delay_ms.toFixed(0)}ms` : '--';
        const detail = `Kills ${kills} • Crossfires ${count} • Δ ${delay}`;
        return `
            <div class="glass-card p-4 rounded-lg text-center">
                <div class="text-sm font-bold text-white">${escapeHtml(players)}</div>
                <div class="text-[10px] text-slate-500 mt-2">${detail}</div>
            </div>
        `;
    }).join('');
}

function renderTimeline(buckets) {
    const container = document.getElementById('proximity-timeline');
    const empty = document.getElementById('proximity-timeline-empty');
    if (!container) return;

    if (!buckets || buckets.length === 0) {
        if (empty) empty.classList.remove('hidden');
        return;
    }

    if (empty) empty.classList.add('hidden');
    const max = Math.max(...buckets.map(b => b.engagements || 0), 1);
    container.innerHTML = buckets.map((b) => {
        const height = Math.max(6, Math.round((b.engagements / max) * 120));
        const label = b.date?.slice(5) || '';
        return `
            <div class="flex-1 flex flex-col items-center justify-end gap-1">
                <div class="w-full rounded bg-brand-cyan/40" style="height:${height}px"></div>
                <div class="text-[10px] text-slate-500">${escapeHtml(label)}</div>
            </div>
        `;
    }).join('');
}

function renderHeatmap(payload) {
    const canvas = document.getElementById('proximity-heatmap');
    const empty = document.getElementById('proximity-heatmap-empty');
    const caption = document.getElementById('proximity-heatmap-caption');
    if (!canvas) return;

    const hotzones = payload?.hotzones || [];
    if (!hotzones.length) {
        if (empty) empty.classList.remove('hidden');
        if (caption) caption.textContent = 'No hotzone data yet.';
        return;
    }

    if (empty) empty.classList.add('hidden');
    const mapName = payload?.map_name || 'unknown';
    if (caption) caption.textContent = `Map: ${stripEtColors(mapName)} • ${hotzones.length} hotzones`;

    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const width = canvas.clientWidth || 480;
    const height = canvas.clientHeight || 192;
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    ctx.scale(dpr, dpr);

    ctx.clearRect(0, 0, width, height);

    const xs = hotzones.map(h => h.grid_x);
    const ys = hotzones.map(h => h.grid_y);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const maxKills = Math.max(...hotzones.map(h => h.kills || 0), 1);

    const pad = 6;
    const spanX = Math.max(maxX - minX, 1);
    const spanY = Math.max(maxY - minY, 1);

    for (const h of hotzones) {
        const normX = (h.grid_x - minX) / spanX;
        const normY = (h.grid_y - minY) / spanY;
        const size = 6 + Math.min(18, (h.kills / maxKills) * 18);
        const x = pad + normX * (width - pad * 2);
        const y = pad + normY * (height - pad * 2);
        const alpha = 0.2 + Math.min(0.75, (h.kills / maxKills) * 0.75);
        ctx.fillStyle = `rgba(244, 63, 94, ${alpha})`;
        ctx.beginPath();
        ctx.arc(x, y, size / 2, 0, Math.PI * 2);
        ctx.fill();
    }
}

function renderEventList(events) {
    const container = document.getElementById('proximity-event-list');
    if (!container) return;

    if (!events || events.length === 0) {
        container.innerHTML = `<div class="text-xs text-slate-600">No events loaded yet.</div>`;
        return;
    }

    container.innerHTML = events.map((e) => {
        const map = stripEtColors(e.map || 'unknown');
        const target = stripEtColors(e.target || 'unknown');
        const outcome = e.outcome || 'unknown';
        const round = e.round != null ? `R${e.round}` : 'R?';
        const roundButton = e.round_id != null
            ? `<button class="text-[10px] text-brand-cyan hover:text-white" data-round-id="${e.round_id}">View round</button>`
            : '';
        const date = e.round_date || e.date || '';
        const time = e.round_time || '';
        const crossfire = e.crossfire ? 'Crossfire' : 'Solo';
        const duration = e.duration_ms != null ? formatDurationMs(e.duration_ms) : '--';
        const distance = e.distance_traveled != null ? `${Math.round(e.distance_traveled)}u` : '--';
        return `
            <div class="glass-card p-3 rounded-lg hover:border-brand-cyan/40 border border-white/5 transition cursor-pointer" data-event-id="${e.id}">
                <div class="flex items-center justify-between text-xs text-slate-500">
                    <span>${escapeHtml(map)} • ${escapeHtml(round)} • ${escapeHtml(date)} ${escapeHtml(time)}</span>
                    ${roundButton}
                </div>
                <div class="text-sm font-semibold text-white mt-1">${escapeHtml(target)}</div>
                <div class="text-[10px] text-slate-400 mt-1">${escapeHtml(outcome)} • ${escapeHtml(crossfire)} • ${formatNumber(e.attackers || 0)} attackers • ${escapeHtml(duration)} • ${escapeHtml(distance)}</div>
            </div>
        `;
    }).join('');

    container.querySelectorAll('[data-event-id]').forEach((card) => {
        card.addEventListener('click', async () => {
            const id = card.getAttribute('data-event-id');
            if (!id) return;
            await loadEventDetail(id);
        });
    });

    container.querySelectorAll('[data-round-id]').forEach((btn) => {
        btn.addEventListener('click', (event) => {
            event.stopPropagation();
            const roundId = btn.getAttribute('data-round-id');
            if (!roundId || typeof window.loadMatchDetails !== 'function') return;
            window.loadMatchDetails(parseInt(roundId, 10));
        });
    });
}

function drawEngagementPath(targetPath, attackerPath = [], strafeEvents = []) {
    const canvas = document.getElementById('proximity-event-canvas');
    const empty = document.getElementById('proximity-event-empty');
    if (!canvas) return;

    const targetPointsRaw = Array.isArray(targetPath) ? targetPath : [];
    const attackerPointsRaw = Array.isArray(attackerPath) ? attackerPath : [];
    const allRaw = targetPointsRaw.concat(attackerPointsRaw);

    if (!allRaw || allRaw.length === 0) {
        if (empty) empty.classList.remove('hidden');
        return;
    }
    if (empty) empty.classList.add('hidden');

    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const width = canvas.clientWidth || 600;
    const height = canvas.clientHeight || 260;
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    ctx.scale(dpr, dpr);

    ctx.clearRect(0, 0, width, height);

    const xs = allRaw.map(p => p.x);
    const ys = allRaw.map(p => p.y);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const spanX = Math.max(maxX - minX, 1);
    const spanY = Math.max(maxY - minY, 1);
    const pad = 12;

    const mapPoints = (path) => path.map(p => {
        const nx = (p.x - minX) / spanX;
        const ny = (p.y - minY) / spanY;
        return {
            x: pad + nx * (width - pad * 2),
            y: pad + ny * (height - pad * 2),
            event: p.event,
            t: p.time
        };
    });

    const targetPoints = mapPoints(targetPointsRaw);
    const attackerPoints = mapPoints(attackerPointsRaw);

    if (attackerPoints.length > 1) {
        ctx.save();
        ctx.strokeStyle = 'rgba(249, 115, 22, 0.8)';
        ctx.lineWidth = 2;
        ctx.setLineDash([6, 4]);
        ctx.beginPath();
        attackerPoints.forEach((pt, idx) => {
            if (idx === 0) ctx.moveTo(pt.x, pt.y);
            else ctx.lineTo(pt.x, pt.y);
        });
        ctx.stroke();
        ctx.restore();
    }

    ctx.strokeStyle = 'rgba(56, 189, 248, 0.85)';
    ctx.lineWidth = 3;
    ctx.beginPath();
    targetPoints.forEach((pt, idx) => {
        if (idx === 0) ctx.moveTo(pt.x, pt.y);
        else ctx.lineTo(pt.x, pt.y);
    });
    ctx.stroke();

    const start = targetPoints[0];
    const end = targetPoints[targetPoints.length - 1];
    if (start && end) {
        ctx.fillStyle = 'rgba(52, 211, 153, 0.95)';
        ctx.beginPath();
        ctx.arc(start.x, start.y, 6, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = 'rgba(226, 232, 240, 0.9)';
        ctx.beginPath();
        ctx.arc(end.x, end.y, 5, 0, Math.PI * 2);
        ctx.fill();
    }

    for (const pt of targetPoints) {
        if (pt.event === 'hit' || pt.event === 'death') {
            ctx.fillStyle = pt.event === 'death' ? 'rgba(248,113,113,0.9)' : 'rgba(250,204,21,0.9)';
            ctx.beginPath();
            ctx.arc(pt.x, pt.y, pt.event === 'death' ? 5 : 4, 0, Math.PI * 2);
            ctx.fill();
        }
    }

    if (strafeEvents && strafeEvents.length) {
        ctx.fillStyle = 'rgba(167, 139, 250, 0.9)';
        for (const ev of strafeEvents) {
            const match = targetPoints.reduce((closest, pt) => {
                const dt = Math.abs((pt.t ?? 0) - (ev.time ?? 0));
                if (!closest || dt < closest.dt) {
                    return { dt, pt };
                }
                return closest;
            }, null);
            const drawPt = match ? match.pt : null;
            if (drawPt) {
                ctx.beginPath();
                ctx.arc(drawPt.x, drawPt.y, 4, 0, Math.PI * 2);
                ctx.fill();
            }
        }
    }
}

async function loadEventDetail(id) {
    const meta = document.getElementById('proximity-event-meta');
    const details = document.getElementById('proximity-event-details');
    const statsEl = document.getElementById('proximity-event-stats');
    if (meta) meta.textContent = 'Loading…';
    if (statsEl) statsEl.innerHTML = '';
    try {
        const data = await fetchJSON(`${API_BASE}/proximity/event/${id}`);
        const map = stripEtColors(data.map_name || 'unknown');
        const target = stripEtColors(data.target_name || 'unknown');
        const outcome = data.outcome || 'unknown';
        const round = data.round_number != null ? `R${data.round_number}` : 'R?';
        const roundDate = data.round_date || data.session_date || '';
        const roundTime = data.round_time || '';
        if (meta) meta.textContent = `${map} • ${round} • ${roundDate} ${roundTime}`;

        let attackers = data.attackers;
        if (typeof attackers === 'string') {
            try {
                attackers = JSON.parse(attackers);
            } catch {
                attackers = [];
            }
        }
        attackers = Array.isArray(attackers) ? attackers : Object.values(attackers || {});
        const attackerNames = attackers.map(a => stripEtColors(a.name || 'unknown')).slice(0, 3).join(', ');
        const killer = attackers.find(a => a.got_kill) || {};
        const killerName = stripEtColors(data.attacker_name || killer.name || 'unknown');
        const roundId = data.round_id != null ? `Round ID: ${data.round_id}` : 'Round ID: n/a';
        const duration = data.duration_ms != null ? formatDurationMs(data.duration_ms) : '--';
        const distance = data.distance_traveled != null ? `${Math.round(data.distance_traveled)}u` : '--';
        const crossfire = data.is_crossfire ? 'Crossfire' : 'Solo';
        const attackersCount = attackers.length;
        if (statsEl) {
            statsEl.innerHTML = `
                <span class="px-2 py-1 rounded bg-white/5 border border-white/10">Duration: ${duration}</span>
                <span class="px-2 py-1 rounded bg-white/5 border border-white/10">Distance: ${distance}</span>
                <span class="px-2 py-1 rounded bg-white/5 border border-white/10">Attackers: ${attackersCount}</span>
                <span class="px-2 py-1 rounded bg-white/5 border border-white/10">Killer: ${escapeHtml(killerName)}</span>
                <span class="px-2 py-1 rounded bg-white/5 border border-white/10">${crossfire}</span>
            `;
        }
        if (details) {
            details.textContent = `${roundId} • Target: ${target} • Killer: ${killerName} • Outcome: ${outcome} • ${crossfire} • Duration: ${duration} • Distance: ${distance} • Damage: ${data.total_damage ?? 0} • Attackers: ${attackers.length} (${attackerNames || 'n/a'})`;
        }

        let targetPath = data.target_path && data.target_path.length ? data.target_path : data.position_path;
        if (typeof targetPath === 'string') {
            try {
                targetPath = JSON.parse(targetPath);
            } catch {
                targetPath = [];
            }
        }
        let attackerPath = data.attacker_path || [];
        if (typeof attackerPath === 'string') {
            try {
                attackerPath = JSON.parse(attackerPath);
            } catch {
                attackerPath = [];
            }
        }
        const strafe = data.strafe || {};
        const targetStrafe = strafe.target || {};
        const attackerStrafe = strafe.attacker || {};
        const targetTurns = targetStrafe.turn_count != null ? targetStrafe.turn_count : 0;
        const targetRate = targetStrafe.turn_rate != null ? `${targetStrafe.turn_rate.toFixed(2)}/s` : '--';
        const attackerTurns = attackerStrafe.turn_count != null ? attackerStrafe.turn_count : 0;
        const attackerRate = attackerStrafe.turn_rate != null ? `${attackerStrafe.turn_rate.toFixed(2)}/s` : '--';
        let strafeSummary = `Target strafe: ${targetTurns} turns (${targetRate}) • Attacker strafe: ${attackerTurns} turns (${attackerRate})`;
        if (Array.isArray(targetStrafe.events) && targetStrafe.events.length && data.start_time_ms != null) {
            const times = targetStrafe.events
                .slice(0, 5)
                .map(ev => ((ev.time - data.start_time_ms) / 1000).toFixed(1) + 's');
            strafeSummary += ` • Turns @ ${times.join(', ')}${targetStrafe.events.length > 5 ? '…' : ''}`;
        }
        if (details) {
            details.textContent = `${details.textContent} • ${strafeSummary}`;
        }

        drawEngagementPath(targetPath || [], attackerPath || [], targetStrafe.events || []);
    } catch (e) {
        if (meta) meta.textContent = 'Failed to load';
        if (details) details.textContent = 'Unable to load engagement details.';
        if (statsEl) statsEl.innerHTML = '';
    }
}

function renderSummary(data) {
    const engagements = data.total_engagements ?? data.engagements ?? null;
    const avgDistance = data.avg_distance_m ?? data.avg_distance ?? null;
    const crossfire = data.crossfire_events ?? data.crossfire ?? null;
    const hotzones = data.hotzones ?? data.hotzone_count ?? null;
    const escapeRate = data.escape_rate_pct ?? null;
    const avgDuration = data.avg_duration_ms ?? null;
    const avgAttackers = data.avg_attackers ?? null;
    const avgSprint = data.avg_sprint_pct ?? null;

    setText('proximity-total-engagements', engagements != null ? formatNumber(engagements) : '--');
    setText('proximity-avg-distance', avgDistance != null ? `${avgDistance.toFixed(1)}u` : '--');
    setText('proximity-crossfire', crossfire != null ? formatNumber(crossfire) : '--');
    setText('proximity-hotzones', hotzones != null ? formatNumber(hotzones) : '--');
    setText('proximity-escape-rate', escapeRate != null ? `${escapeRate.toFixed(1)}%` : '--');
    setText('proximity-avg-duration', avgDuration != null ? formatDurationMs(avgDuration) : '--');
    setText('proximity-avg-attackers', avgAttackers != null ? avgAttackers.toFixed(2) : '--');
    setText('proximity-avg-sprint', avgSprint != null ? `${avgSprint.toFixed(1)}%` : '--');

    renderDuos(data.top_duos || []);
}

export async function loadProximityView() {
    const stateEl = document.getElementById('proximity-state');
    if (stateEl) {
        stateEl.innerHTML = `
            <i data-lucide="clock" class="w-4 h-4 text-brand-cyan"></i>
            <span>Prototype mode: waiting for proximity data ingestion.</span>
        `;
    }

    setText('proximity-total-engagements', '--');
    setText('proximity-avg-distance', '--');
    setText('proximity-crossfire', '--');
    setText('proximity-hotzones', '--');
    setText('proximity-escape-rate', '--');
    setText('proximity-avg-duration', '--');
    setText('proximity-avg-attackers', '--');
    setText('proximity-avg-sprint', '--');
    setText('proximity-trade-opportunities', '--');
    setText('proximity-trade-attempts', '--');
    setText('proximity-trade-success', '--');
    setText('proximity-trade-missed', '--');
    setText('proximity-support-uptime', '--');
    setText('proximity-isolation-deaths', '--');

    try {
        const data = await fetchJSON(`${API_BASE}/proximity/summary?range_days=${DEFAULT_RANGE_DAYS}`);
        renderSummary(data);
        const ready = data?.ready === true || data?.status === 'ready';
        if (!ready) {
            if (stateEl) {
                const message = data?.message || 'Prototype mode: proximity data not ready yet.';
                stateEl.innerHTML = `
                    <i data-lucide="alert-circle" class="w-4 h-4 text-brand-rose"></i>
                    <span>${escapeHtml(message)}</span>
                `;
            }
        } else if (stateEl) {
            const rounds = data.sample_rounds != null ? formatNumber(data.sample_rounds) : 'n/a';
            stateEl.innerHTML = `
                <i data-lucide="activity" class="w-4 h-4 text-brand-emerald"></i>
                <span>Live proximity snapshot • ${rounds} rounds analyzed • ${DEFAULT_RANGE_DAYS}d window</span>
            `;
        }

        if (ready) {
            const [
                timelineRes,
                heatmapRes,
                moversRes,
                teamplayRes,
                eventsRes,
                tradesSummaryRes,
                tradesEventsRes
            ] = await Promise.allSettled([
                fetchJSON(`${API_BASE}/proximity/engagements?range_days=${DEFAULT_RANGE_DAYS}`),
                fetchJSON(`${API_BASE}/proximity/hotzones?range_days=${DEFAULT_RANGE_DAYS}`),
                fetchJSON(`${API_BASE}/proximity/movers?range_days=${DEFAULT_RANGE_DAYS}`),
                fetchJSON(`${API_BASE}/proximity/teamplay?limit=6`),
                fetchJSON(`${API_BASE}/proximity/events?range_days=${DEFAULT_RANGE_DAYS}&limit=${DEFAULT_EVENTS_LIMIT}`),
                fetchJSON(`${API_BASE}/proximity/trades/summary?range_days=${DEFAULT_RANGE_DAYS}`),
                fetchJSON(`${API_BASE}/proximity/trades/events?range_days=${DEFAULT_RANGE_DAYS}&limit=10`)
            ]);

            if (timelineRes.status === 'fulfilled') {
                renderTimeline(timelineRes.value.buckets || []);
            }
            if (heatmapRes.status === 'fulfilled') {
                renderHeatmap(heatmapRes.value);
            }
            if (eventsRes.status === 'fulfilled') {
                renderEventList(eventsRes.value.events || []);
            }
            if (moversRes.status === 'fulfilled') {
                const movers = moversRes.value;
                renderLeaderList('proximity-distance-leaders', movers.distance, (row) => {
                    const distance = row.total_distance != null ? `${formatNumber(Math.round(row.total_distance))}u` : '--';
                    return distance;
                });
                renderLeaderList('proximity-sprint-leaders', movers.sprint, (row) => {
                    const pct = row.sprint_pct != null ? `${row.sprint_pct.toFixed(1)}%` : '--';
                    return pct;
                });
                renderLeaderList('proximity-reaction-leaders', movers.reaction, (row) => {
                    return formatMs(row.reaction_ms);
                });
                renderLeaderList('proximity-survival-leaders', movers.survival, (row) => {
                    return row.duration_ms != null ? formatDurationMs(row.duration_ms) : '--';
                });
            }
            if (teamplayRes.status === 'fulfilled') {
                const teamplay = teamplayRes.value;
                renderLeaderList('proximity-crossfire-leaders', teamplay.crossfire_kills, (row) => {
                    const kills = row.crossfire_kills != null ? formatNumber(row.crossfire_kills) : '--';
                    const rate = row.kill_rate_pct != null ? `${row.kill_rate_pct.toFixed(1)}%` : '--';
                    return `${kills} (${rate})`;
                });
                renderLeaderList('proximity-sync-leaders', teamplay.sync, (row) => {
                    const delay = row.avg_delay_ms != null ? `${row.avg_delay_ms.toFixed(0)}ms` : '--';
                    return delay;
                });
                renderLeaderList('proximity-focus-leaders', teamplay.focus_survival, (row) => {
                    const rate = row.survival_rate_pct != null ? `${row.survival_rate_pct.toFixed(1)}%` : '--';
                    return `${rate} (${row.focus_escapes || 0}/${row.times_focused || 0})`;
                });
            }
            if (tradesSummaryRes.status === 'fulfilled') {
                renderTradeSummary(tradesSummaryRes.value);
            }
            if (tradesEventsRes.status === 'fulfilled') {
                renderTradeEvents(tradesEventsRes.value.events || []);
            }
        }
    } catch (e) {
        if (stateEl) {
            stateEl.innerHTML = `
                <i data-lucide="alert-circle" class="w-4 h-4 text-brand-rose"></i>
                <span>Prototype mode: proximity API not connected yet.</span>
            `;
        }
    }

    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
}
