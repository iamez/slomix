/**
 * Round Visualizer Module
 * Interactive Chart.js panels for individual round data.
 * @module retro-viz
 */

import { API_BASE, fetchJSON, escapeHtml, formatNumber } from './utils.js';
import { PageHeader, LoadingSkeleton, EmptyState } from './components.js';

// Chart instances for cleanup
let _charts = [];

// ============================================================================
// LOAD VIEW
// ============================================================================

export async function loadRetroVizView() {
    const container = document.getElementById('retro-viz-container');
    if (!container) return;

    container.innerHTML = PageHeader(
        'Round Visualizer',
        'Interactive round-by-round combat analytics'
    ) + `
        <div class="mb-6">
            <label class="text-sm text-slate-400 mr-2">Select Round:</label>
            <select id="retro-viz-picker" class="bg-slate-800/80 border border-slate-700 text-white text-sm rounded-lg px-3 py-2 min-w-[320px] focus:ring-brand-cyan focus:border-brand-cyan">
                <option value="">Loading rounds…</option>
            </select>
        </div>
        <div id="retro-viz-panels">${LoadingSkeleton('card', 6)}</div>
    `;

    // Load round picker
    try {
        const rounds = await fetchJSON(`${API_BASE}/rounds/recent?limit=50`);
        const picker = document.getElementById('retro-viz-picker');
        if (!picker) return;

        if (!rounds || rounds.length === 0) {
            picker.innerHTML = '<option value="">No rounds available</option>';
            document.getElementById('retro-viz-panels').innerHTML =
                EmptyState('No round data found. Play some rounds first!');
            return;
        }

        picker.innerHTML = rounds.map(r => {
            const dateStr = r.round_date ? new Date(r.round_date + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '';
            const label = `${r.map_name || 'Unknown'} R${r.round_number ?? '?'} — ${dateStr} (${r.player_count} players)`;
            return `<option value="${r.id}">${escapeHtml(label)}</option>`;
        }).join('');

        picker.addEventListener('change', () => {
            const id = picker.value;
            if (id) loadRound(parseInt(id, 10));
        });

        // Load most recent round
        loadRound(rounds[0].id);
    } catch {
        document.getElementById('retro-viz-panels').innerHTML =
            EmptyState('Failed to load rounds.');
    }
}

// ============================================================================
// LOAD ROUND DATA & RENDER ALL PANELS
// ============================================================================

async function loadRound(roundId) {
    const panels = document.getElementById('retro-viz-panels');
    if (!panels) return;

    // Destroy previous charts
    _charts.forEach(c => c.destroy());
    _charts = [];

    panels.innerHTML = LoadingSkeleton('card', 6);

    try {
        const data = await fetchJSON(`${API_BASE}/rounds/${roundId}/viz`);
        if (!data || !data.players || data.players.length === 0) {
            panels.innerHTML = EmptyState('No player data for this round.');
            return;
        }
        renderPanels(panels, data);
    } catch {
        panels.innerHTML = EmptyState('Failed to load round data.');
    }
}

function renderPanels(container, data) {
    container.innerHTML = `
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <!-- Row 1: Match Summary + Combat Overview -->
            <div id="rv-summary" class="glass-card rounded-xl p-5 cursor-pointer hover:ring-1 hover:ring-brand-cyan/30 transition"></div>
            <div class="glass-card rounded-xl p-5 cursor-pointer hover:ring-1 hover:ring-brand-cyan/30 transition" id="rv-radar-wrap">
                <h3 class="text-sm font-bold text-white mb-4">Combat Overview</h3>
                <div class="chart-container" style="height:320px"><canvas id="rv-radar"></canvas></div>
            </div>
        </div>

        <!-- Row 2: Top Fraggers -->
        <div class="glass-card rounded-xl p-5 mt-6 cursor-pointer hover:ring-1 hover:ring-brand-cyan/30 transition" id="rv-fraggers-wrap">
            <h3 class="text-sm font-bold text-white mb-4">Top Fraggers</h3>
            <div class="chart-container" style="height:${Math.max(200, data.players.length * 32)}px"><canvas id="rv-fraggers"></canvas></div>
        </div>

        <!-- Row 3: Damage Breakdown -->
        <div class="glass-card rounded-xl p-5 mt-6 cursor-pointer hover:ring-1 hover:ring-brand-cyan/30 transition" id="rv-damage-wrap">
            <h3 class="text-sm font-bold text-white mb-4">Damage Breakdown</h3>
            <div id="rv-damage-table"></div>
        </div>

        <!-- Row 4: Support Performance + Time Distribution -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
            <div class="glass-card rounded-xl p-5 cursor-pointer hover:ring-1 hover:ring-brand-cyan/30 transition" id="rv-support-wrap">
                <h3 class="text-sm font-bold text-white mb-4">Support Performance</h3>
                <div class="chart-container" style="height:${Math.max(200, data.players.length * 36)}px"><canvas id="rv-support"></canvas></div>
            </div>
            <div class="glass-card rounded-xl p-5 cursor-pointer hover:ring-1 hover:ring-brand-cyan/30 transition" id="rv-time-wrap">
                <h3 class="text-sm font-bold text-white mb-4">Time Distribution</h3>
                <div class="chart-container" style="height:${Math.max(200, data.players.length * 32)}px"><canvas id="rv-time"></canvas></div>
            </div>
        </div>
    `;

    renderMatchSummary(data);
    renderCombatRadar(data);
    renderTopFraggers(data);
    renderDamageBreakdown(data);
    renderSupportPerformance(data);
    renderTimeDistribution(data);

    // Lightbox click handlers
    const chartPanels = [
        { id: 'rv-radar-wrap', render: (c) => renderCombatRadar(data, c) },
        { id: 'rv-fraggers-wrap', render: (c) => renderTopFraggers(data, c) },
        { id: 'rv-support-wrap', render: (c) => renderSupportPerformance(data, c) },
        { id: 'rv-time-wrap', render: (c) => renderTimeDistribution(data, c) },
    ];

    chartPanels.forEach(({ id, render }) => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('click', () => openChartLightbox(el.querySelector('h3')?.textContent || 'Chart', render));
    });

    // Damage table lightbox
    const dmgWrap = document.getElementById('rv-damage-wrap');
    if (dmgWrap) {
        dmgWrap.addEventListener('click', () => openHtmlLightbox('Damage Breakdown', () => buildDamageTableHtml(data)));
    }
}

// ============================================================================
// 1. MATCH SUMMARY
// ============================================================================

function renderMatchSummary(data) {
    const el = document.getElementById('rv-summary');
    if (!el) return;

    const h = data.highlights || {};
    const winnerLabel = data.winner_team === 1 ? 'Axis' : data.winner_team === 2 ? 'Allies' : 'Tied';
    const winnerColor = data.winner_team === 1 ? 'text-red-400' : data.winner_team === 2 ? 'text-blue-400' : 'text-slate-400';
    const durationStr = data.duration_seconds ? `${Math.round(data.duration_seconds / 60)}m` : '—';

    el.innerHTML = `
        <h3 class="text-sm font-bold text-white mb-4">Match Summary</h3>
        <div class="grid grid-cols-2 gap-3 text-sm">
            <div class="glass-panel rounded-lg p-3">
                <div class="text-[11px] text-slate-500">Map</div>
                <div class="text-white font-bold">${escapeHtml(data.map_name || 'Unknown')}</div>
            </div>
            <div class="glass-panel rounded-lg p-3">
                <div class="text-[11px] text-slate-500">Round</div>
                <div class="text-white font-bold">R${data.round_number ?? '?'}</div>
            </div>
            <div class="glass-panel rounded-lg p-3">
                <div class="text-[11px] text-slate-500">Date</div>
                <div class="text-white font-bold">${escapeHtml(data.round_date || '—')}</div>
            </div>
            <div class="glass-panel rounded-lg p-3">
                <div class="text-[11px] text-slate-500">Duration</div>
                <div class="text-white font-bold">${durationStr}</div>
            </div>
            <div class="glass-panel rounded-lg p-3">
                <div class="text-[11px] text-slate-500">Players</div>
                <div class="text-white font-bold">${data.player_count}</div>
            </div>
            <div class="glass-panel rounded-lg p-3">
                <div class="text-[11px] text-slate-500">Winner</div>
                <div class="${winnerColor} font-bold">${winnerLabel}</div>
            </div>
        </div>
        ${h.mvp || h.most_kills || h.most_damage ? `
        <div class="mt-4 grid grid-cols-3 gap-2">
            ${h.mvp ? `<div class="glass-panel rounded-lg p-2 text-center">
                <div class="text-[10px] text-yellow-500/80">MVP (DPM)</div>
                <div class="text-xs text-white font-bold truncate">${escapeHtml(h.mvp.name)}</div>
                <div class="text-[10px] text-slate-400">${Math.round(h.mvp.dpm)}</div>
            </div>` : ''}
            ${h.most_kills ? `<div class="glass-panel rounded-lg p-2 text-center">
                <div class="text-[10px] text-red-400/80">Most Kills</div>
                <div class="text-xs text-white font-bold truncate">${escapeHtml(h.most_kills.name)}</div>
                <div class="text-[10px] text-slate-400">${h.most_kills.kills}</div>
            </div>` : ''}
            ${h.most_damage ? `<div class="glass-panel rounded-lg p-2 text-center">
                <div class="text-[10px] text-orange-400/80">Most Damage</div>
                <div class="text-xs text-white font-bold truncate">${escapeHtml(h.most_damage.name)}</div>
                <div class="text-[10px] text-slate-400">${formatNumber(h.most_damage.damage_given)}</div>
            </div>` : ''}
        </div>` : ''}
    `;
}

// ============================================================================
// 2. COMBAT OVERVIEW (Radar)
// ============================================================================

function renderCombatRadar(data, canvasOverride) {
    const canvas = canvasOverride || document.getElementById('rv-radar');
    if (!canvas) return;

    const top5 = data.players.slice().sort((a, b) => b.dpm - a.dpm).slice(0, 5);
    if (top5.length === 0) return;

    const labels = ['Kills', 'Deaths(inv)', 'DPM', 'Damage', 'Efficiency', 'Gibs'];
    const maxVals = {
        kills: Math.max(...top5.map(p => p.kills), 1),
        deaths: Math.max(...top5.map(p => p.deaths), 1),
        dpm: Math.max(...top5.map(p => p.dpm), 1),
        damage: Math.max(...top5.map(p => p.damage_given), 1),
        efficiency: 100,
        gibs: Math.max(...top5.map(p => p.gibs), 1),
    };

    const colors = [
        'rgba(59, 130, 246, 0.6)',
        'rgba(244, 63, 94, 0.6)',
        'rgba(16, 185, 129, 0.6)',
        'rgba(245, 158, 11, 0.6)',
        'rgba(168, 85, 247, 0.6)',
    ];

    const datasets = top5.map((p, i) => ({
        label: p.name,
        data: [
            Math.round(p.kills / maxVals.kills * 100),
            Math.round((1 - p.deaths / maxVals.deaths) * 100),
            Math.round(p.dpm / maxVals.dpm * 100),
            Math.round(p.damage_given / maxVals.damage * 100),
            Math.round(p.efficiency),
            Math.round(p.gibs / maxVals.gibs * 100),
        ],
        backgroundColor: colors[i % colors.length],
        borderColor: colors[i % colors.length],
        borderWidth: 2,
    }));

    const chart = new Chart(canvas.getContext('2d'), {
        type: 'radar',
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom', labels: { color: '#94a3b8', font: { size: 10 } } },
            },
            scales: {
                r: {
                    angleLines: { color: 'rgba(148, 163, 184, 0.2)' },
                    grid: { color: 'rgba(148, 163, 184, 0.2)' },
                    pointLabels: { color: '#94a3b8', font: { size: 10 } },
                    ticks: { display: false },
                    min: 0,
                    max: 100,
                },
            },
        },
    });
    _charts.push(chart);
    return chart;
}

// ============================================================================
// 3. TOP FRAGGERS (Horizontal bar)
// ============================================================================

function renderTopFraggers(data, canvasOverride) {
    const canvas = canvasOverride || document.getElementById('rv-fraggers');
    if (!canvas) return;

    const sorted = data.players.slice().sort((a, b) => a.kills - b.kills); // ascending for horizontal
    const labels = sorted.map(p => p.name);
    const kills = sorted.map(p => p.kills);
    const maxKills = Math.max(...kills, 1);

    const chart = new Chart(canvas.getContext('2d'), {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: 'Kills',
                data: kills,
                backgroundColor: kills.map((k) => {
                    const ratio = k / maxKills;
                    // Gold for top, slate for bottom
                    const r = Math.round(245 * ratio + 100 * (1 - ratio));
                    const g = Math.round(158 * ratio + 116 * (1 - ratio));
                    const b = Math.round(11 * ratio + 148 * (1 - ratio));
                    return `rgba(${r}, ${g}, ${b}, 0.8)`;
                }),
                borderRadius: 4,
            }],
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
            },
            scales: {
                x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148, 163, 184, 0.1)' } },
                y: { ticks: { color: '#94a3b8', font: { size: 11 } }, grid: { display: false } },
            },
        },
    });
    _charts.push(chart);
    return chart;
}

// ============================================================================
// 4. DAMAGE BREAKDOWN (HTML heatmap table)
// ============================================================================

function renderDamageBreakdown(data) {
    const el = document.getElementById('rv-damage-table');
    if (!el) return;
    el.innerHTML = buildDamageTableHtml(data);
}

function buildDamageTableHtml(data) {
    const sorted = data.players.slice().sort((a, b) => b.damage_given - a.damage_given);
    const cols = [
        { key: 'damage_given', label: 'Dmg Given', color: '59, 130, 246' },
        { key: 'damage_received', label: 'Dmg Recv', color: '244, 63, 94' },
        { key: 'team_damage_given', label: 'TK Dmg', color: '245, 158, 11' },
        { key: 'team_damage_received', label: 'TK Recv', color: '168, 85, 247' },
    ];

    const maxes = {};
    cols.forEach(c => {
        maxes[c.key] = Math.max(...sorted.map(p => p[c.key] || 0), 1);
    });

    const headerCells = cols.map(c =>
        `<th class="text-[10px] text-slate-500 font-medium px-2 py-1 text-right">${c.label}</th>`
    ).join('');

    const rows = sorted.map(p => {
        const cells = cols.map(c => {
            const val = p[c.key] || 0;
            const alpha = Math.min(val / maxes[c.key], 1) * 0.5 + 0.05;
            return `<td class="text-right px-2 py-1.5 font-mono text-xs text-white" style="background: rgba(${c.color}, ${alpha.toFixed(2)})">${formatNumber(val)}</td>`;
        }).join('');
        return `<tr class="border-t border-slate-800/50"><td class="text-xs text-slate-300 px-2 py-1.5 truncate max-w-[120px]">${escapeHtml(p.name)}</td>${cells}</tr>`;
    }).join('');

    return `
        <div class="overflow-x-auto">
            <table class="w-full text-left">
                <thead><tr><th class="text-[10px] text-slate-500 font-medium px-2 py-1">Player</th>${headerCells}</tr></thead>
                <tbody>${rows}</tbody>
            </table>
        </div>`;
}

// ============================================================================
// 5. SUPPORT PERFORMANCE (Grouped horizontal bar)
// ============================================================================

function renderSupportPerformance(data, canvasOverride) {
    const canvas = canvasOverride || document.getElementById('rv-support');
    if (!canvas) return;

    const sorted = data.players.slice().sort((a, b) => a.revives_given - b.revives_given);
    const labels = sorted.map(p => p.name);

    const chart = new Chart(canvas.getContext('2d'), {
        type: 'bar',
        data: {
            labels,
            datasets: [
                {
                    label: 'Revives',
                    data: sorted.map(p => p.revives_given),
                    backgroundColor: 'rgba(16, 185, 129, 0.8)',
                    borderRadius: 3,
                },
                {
                    label: 'Denied Playtime (s)',
                    data: sorted.map(p => p.denied_playtime),
                    backgroundColor: 'rgba(245, 158, 11, 0.8)',
                    borderRadius: 3,
                },
                {
                    label: 'Dead Time (min)',
                    data: sorted.map(p => Math.round(p.time_dead_seconds / 60)),
                    backgroundColor: 'rgba(248, 113, 113, 0.8)',
                    borderRadius: 3,
                },
            ],
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom', labels: { color: '#94a3b8', font: { size: 10 } } },
            },
            scales: {
                x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148, 163, 184, 0.1)' } },
                y: { ticks: { color: '#94a3b8', font: { size: 11 } }, grid: { display: false } },
            },
        },
    });
    _charts.push(chart);
    return chart;
}

// ============================================================================
// 6. TIME DISTRIBUTION (Stacked bar)
// ============================================================================

function renderTimeDistribution(data, canvasOverride) {
    const canvas = canvasOverride || document.getElementById('rv-time');
    if (!canvas) return;

    const sorted = data.players.slice().sort((a, b) =>
        (a.time_played_seconds || 0) - (b.time_played_seconds || 0)
    );
    const labels = sorted.map(p => p.name);
    const timeAlive = sorted.map(p => Math.max(0, Math.round((p.time_played_seconds || 0) / 60) - Math.round((p.time_dead_seconds || 0) / 60)));
    const timeDead = sorted.map(p => Math.round((p.time_dead_seconds || 0) / 60));

    const chart = new Chart(canvas.getContext('2d'), {
        type: 'bar',
        data: {
            labels,
            datasets: [
                { label: 'Alive (min)', data: timeAlive, backgroundColor: 'rgba(34, 197, 94, 0.8)', stack: 'time' },
                { label: 'Dead (min)', data: timeDead, backgroundColor: 'rgba(248, 113, 113, 0.8)', stack: 'time' },
            ],
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom', labels: { color: '#94a3b8', font: { size: 10 } } },
            },
            scales: {
                x: { stacked: true, ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148, 163, 184, 0.1)' } },
                y: { stacked: true, ticks: { color: '#94a3b8', font: { size: 11 } }, grid: { display: false } },
            },
        },
    });
    _charts.push(chart);
    return chart;
}

// ============================================================================
// CHART LIGHTBOX
// ============================================================================

function openChartLightbox(title, renderFn) {
    const existing = document.getElementById('retro-viz-lightbox');
    if (existing) existing.remove();

    const modal = document.createElement('div');
    modal.id = 'retro-viz-lightbox';
    modal.className = 'fixed inset-0 z-50 flex items-center justify-center';
    modal.style.cssText = 'background: rgba(0,0,0,0); transition: background 0.3s ease;';
    modal.innerHTML = `
        <div class="absolute inset-0 backdrop-blur-md"></div>
        <div class="relative w-[90vw] h-[80vh] mx-4" style="transform: scale(0.95); opacity: 0; transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);">
            <button class="absolute -top-10 right-0 w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:text-white hover:bg-white/10 transition" id="rv-lightbox-close">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
            </button>
            <div class="glass-card rounded-xl p-6 w-full h-full flex flex-col">
                <h3 class="text-base font-bold text-white mb-4">${escapeHtml(title)}</h3>
                <div class="flex-1 relative"><canvas id="rv-lightbox-canvas"></canvas></div>
            </div>
        </div>
    `;

    modal.addEventListener('click', (e) => {
        if (e.target === modal || e.target.classList.contains('backdrop-blur-md')) closeLightbox();
    });

    document.body.appendChild(modal);

    const closeBtn = document.getElementById('rv-lightbox-close');
    if (closeBtn) closeBtn.addEventListener('click', closeLightbox);

    requestAnimationFrame(() => {
        modal.style.background = 'rgba(0,0,0,0.85)';
        const inner = modal.querySelector('.relative');
        if (inner) {
            inner.style.transform = 'scale(1)';
            inner.style.opacity = '1';
        }
        // Render chart in lightbox canvas
        const canvas = document.getElementById('rv-lightbox-canvas');
        if (canvas) {
            const chart = renderFn(canvas);
            if (chart) _charts.push(chart);
        }
    });

    document.addEventListener('keydown', handleLightboxEscape);
}

function openHtmlLightbox(title, buildHtmlFn) {
    const existing = document.getElementById('retro-viz-lightbox');
    if (existing) existing.remove();

    const modal = document.createElement('div');
    modal.id = 'retro-viz-lightbox';
    modal.className = 'fixed inset-0 z-50 flex items-center justify-center';
    modal.style.cssText = 'background: rgba(0,0,0,0); transition: background 0.3s ease;';
    modal.innerHTML = `
        <div class="absolute inset-0 backdrop-blur-md"></div>
        <div class="relative w-[90vw] max-h-[85vh] mx-4 overflow-auto" style="transform: scale(0.95); opacity: 0; transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);">
            <button class="absolute -top-10 right-0 w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:text-white hover:bg-white/10 transition" id="rv-lightbox-close">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
            </button>
            <div class="glass-card rounded-xl p-6 w-full">
                <h3 class="text-base font-bold text-white mb-4">${escapeHtml(title)}</h3>
                <div id="rv-lightbox-content"></div>
            </div>
        </div>
    `;

    modal.addEventListener('click', (e) => {
        if (e.target === modal || e.target.classList.contains('backdrop-blur-md')) closeLightbox();
    });

    document.body.appendChild(modal);

    const closeBtn = document.getElementById('rv-lightbox-close');
    if (closeBtn) closeBtn.addEventListener('click', closeLightbox);

    requestAnimationFrame(() => {
        modal.style.background = 'rgba(0,0,0,0.85)';
        const inner = modal.querySelector('.relative');
        if (inner) {
            inner.style.transform = 'scale(1)';
            inner.style.opacity = '1';
        }
        const content = document.getElementById('rv-lightbox-content');
        if (content) content.innerHTML = buildHtmlFn();
    });

    document.addEventListener('keydown', handleLightboxEscape);
}

function handleLightboxEscape(e) {
    if (e.key === 'Escape') closeLightbox();
}

function closeLightbox() {
    const modal = document.getElementById('retro-viz-lightbox');
    if (modal) {
        const inner = modal.querySelector('.relative');
        if (inner) {
            inner.style.transform = 'scale(0.95)';
            inner.style.opacity = '0';
        }
        modal.style.background = 'rgba(0,0,0,0)';
        setTimeout(() => modal.remove(), 300);
    }
    document.removeEventListener('keydown', handleLightboxEscape);
}

// ============================================================================
// EXPOSE TO WINDOW (for backwards compat)
// ============================================================================

window._retroVizLightbox = () => {};
window._retroVizCloseLightbox = closeLightbox;
