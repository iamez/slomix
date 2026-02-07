/**
 * Sessions module - Gaming sessions browser and related widgets
 * @module sessions
 */

import { API_BASE, fetchJSON, escapeHtml, escapeJsString } from './utils.js';

// Sessions state
let sessionsData = [];
let sessionsOffset = 0;
const SESSIONS_LIMIT = 15;
let expandedSessions = new Set();

const MAP_IMAGE_MAP = {
    "supply": "assets/maps/supply.svg",
    "etl_adlernest": "assets/maps/etl_adlernest.svg",
    "etl_sp_delivery": "assets/maps/etl_sp_delivery.svg",
    "etl_delivery": "assets/maps/etl_sp_delivery.svg",
    "etl_battery": "assets/maps/etl_battery.svg",
    "etl_oasis": "assets/maps/etl_oasis.svg",
    "etl_frostbite": "assets/maps/etl_frostbite.svg",
    "etl_goldrush": "assets/maps/etl_goldrush.svg",
    "etl_brewdog": "assets/maps/etl_brewdog.svg",
    "etl_erdenberg": "assets/maps/etl_erdenberg.svg",
    "etl_bradendorf": "assets/maps/etl_bradendorf.svg",
    "etl_escape2": "assets/maps/etl_escape2.svg",
    "etl_adlernest_a3": "assets/maps/etl_adlernest.svg"
};
const AXIS_ICON = "assets/icons/axis.svg";
const ALLIES_ICON = "assets/icons/allies.svg";

function normalizeMapKey(mapName) {
    const raw = (mapName || '').toString().trim().toLowerCase();
    if (!raw) return '';

    const cleaned = raw
        .replace(/^maps[\\/]/, '')
        .replace(/\.(bsp|pk3|arena)$/i, '')
        .replace(/[^a-z0-9]+/g, '_')
        .replace(/_+/g, '_')
        .replace(/^_+|_+$/g, '');

    return cleaned;
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

    const trimmed = key
        .replace(/^etl_/, '')
        .replace(/^sw_/, '')
        .replace(/^et_/, '');

    const candidates = [
        trimmed,
        `etl_${trimmed}`,
        `sw_${trimmed}`,
        `et_${trimmed}`,
        key
    ];

    for (const candidate of candidates) {
        if (MAP_IMAGE_MAP[candidate]) return MAP_IMAGE_MAP[candidate];
    }

    // Fuzzy match if map name includes a known key
    const keyCompact = key.replace(/_/g, '');
    for (const [mapKey, mapPath] of Object.entries(MAP_IMAGE_MAP)) {
        if (mapKey === 'map_generic') continue;
        const mapCompact = mapKey.replace(/_/g, '');
        if (
            key.includes(mapKey) ||
            mapKey.includes(key) ||
            keyCompact.includes(mapCompact) ||
            mapCompact.includes(keyCompact)
        ) {
            return mapPath;
        }
    }

    return "assets/maps/map_generic.svg";
}

function mapTile(mapName) {
    const safeMapName = escapeHtml(mapLabel(mapName));
    const mapImg = mapImageFor(mapName);
    const isFallbackMap = mapImg.includes('map_generic.svg');

    if (isFallbackMap) {
        return `
            <div class="w-16 h-10 rounded-md bg-slate-900/60 border border-white/10 flex items-center justify-center text-[9px] font-bold text-white px-1 text-center leading-tight">
                <span class="truncate" title="${safeMapName}">${safeMapName}</span>
            </div>
        `;
    }

    return `
        <div class="relative w-16 h-10 rounded-md border border-white/10 overflow-hidden bg-slate-900/60">
            <div class="absolute inset-0 bg-cover bg-center" style="background-image: url('${mapImg}')"></div>
            <div class="absolute bottom-0 left-0 right-0 bg-black/50 text-[9px] text-slate-100 px-1 truncate">
                ${safeMapName}
            </div>
        </div>
    `;
}

function formatDuration(seconds) {
    const total = Number(seconds || 0);
    if (!total || total < 0) return "0:00";
    const mins = Math.floor(total / 60);
    const secs = Math.floor(total % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Load season info widget
 */
export async function loadSeasonInfo() {
    try {
        const season = await fetchJSON(`${API_BASE}/seasons/current`);
        const seasonEl = document.getElementById('current-season-display');
        if (seasonEl) seasonEl.textContent = season.name;

        const startEl = document.getElementById('season-start-date');
        const endEl = document.getElementById('season-end-date');
        const nextEl = document.getElementById('season-next-name');
        const nextStartEl = document.getElementById('season-next-start');
        const rangeEl = document.getElementById('season-date-range');
        const daysLeftEl = document.getElementById('season-days-left');
        const progressEl = document.getElementById('season-progress-bar');

        const formatDate = (raw) => {
            if (!raw) return '--';
            const date = new Date(`${raw}T00:00:00`);
            if (Number.isNaN(date.getTime())) return raw;
            return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
        };

        if (startEl) startEl.textContent = formatDate(season.start_date);
        if (endEl) endEl.textContent = formatDate(season.end_date);
        if (nextEl) nextEl.textContent = season.next_season_name || '--';
        if (nextStartEl) nextStartEl.textContent = formatDate(season.next_season_start);
        if (rangeEl) rangeEl.textContent = season.start_date && season.end_date
            ? `${formatDate(season.start_date)} → ${formatDate(season.end_date)}`
            : '--';
        if (daysLeftEl) daysLeftEl.textContent = typeof season.days_left === 'number'
            ? `${season.days_left} days left`
            : '-- days left';

        if (progressEl && season.start_date && season.end_date) {
            const start = new Date(`${season.start_date}T00:00:00`);
            const end = new Date(`${season.end_date}T00:00:00`);
            const now = new Date();
            const total = end.getTime() - start.getTime();
            const elapsed = Math.min(Math.max(now.getTime() - start.getTime(), 0), total);
            const pct = total > 0 ? Math.round((elapsed / total) * 100) : 0;
            progressEl.style.width = `${pct}%`;
        }
    } catch (e) {
        console.error('Failed to load season:', e);
    }
}

export function toggleSeasonDetails() {
    const panel = document.getElementById('season-expanded-content');
    const icon = document.getElementById('season-expand-icon');
    if (!panel) return;
    panel.classList.toggle('hidden');
    if (icon) {
        icon.classList.toggle('rotate-180');
    }
}

/**
 * Load last session widget on home page
 */
export async function loadLastSession() {
    try {
        const data = await fetchJSON(`${API_BASE}/stats/last-session`);
        console.log('Last Session:', data);

        // Update "Last Session" widget
        const lsDate = document.getElementById('ls-date');
        const lsPlayers = document.getElementById('ls-players');
        const lsRounds = document.getElementById('ls-rounds');
        const lsMaps = document.getElementById('ls-maps');

        if (lsDate) lsDate.textContent = data.date;
        if (lsPlayers) lsPlayers.textContent = data.player_count;
        if (lsRounds) lsRounds.textContent = data.rounds;
        if (lsMaps) lsMaps.textContent = data.maps.length;

        // Render detailed view
        renderSessionDetails(data);

    } catch (e) {
        console.error('Failed to load last session:', e);
    }
}

/**
 * Render session details (home page widget)
 */
export function renderSessionDetails(data) {
    const container = document.getElementById('session-matches-list');
    const dateEl = document.getElementById('session-details-date');
    if (!container) return;

    if (dateEl) dateEl.textContent = `Session Date: ${data.date}`;
    container.innerHTML = '';

    // Session scoring (prefer team-aware scoring payload)
    const scoring = data.scoring || {};
    const hasScoring = scoring.available && scoring.team_a_name && scoring.team_b_name;
    const teamAName = hasScoring ? scoring.team_a_name : 'Allies';
    const teamBName = hasScoring ? scoring.team_b_name : 'Axis';
    let teamAScore = hasScoring ? (scoring.team_a_score || 0) : 0;
    let teamBScore = hasScoring ? (scoring.team_b_score || 0) : 0;
    let teamAWins = 0;
    let teamBWins = 0;
    let ties = 0;
    let notCounted = 0;

    if (hasScoring && Array.isArray(scoring.maps) && scoring.maps.length > 0) {
        scoring.maps.forEach(m => {
            if (m.counted === false) {
                notCounted += 1;
                return;
            }
            const a = Number(m.team_a_points || 0);
            const b = Number(m.team_b_points || 0);
            if (a > b) teamAWins += 1;
            else if (b > a) teamBWins += 1;
            else ties += 1;
        });
    } else {
        teamAWins = (data.matches || []).filter(m => m.winner === teamAName).length;
        teamBWins = (data.matches || []).filter(m => m.winner === teamBName).length;
        ties = (data.matches || []).filter(m => m.winner !== teamAName && m.winner !== teamBName).length;
        teamAScore = teamAWins;
        teamBScore = teamBWins;
    }

    const scoreColor = teamAScore > teamBScore
        ? 'text-brand-blue'
        : teamBScore > teamAScore
            ? 'text-brand-rose'
            : 'text-slate-400';
    const scoreNote = hasScoring
        ? `${teamAName} - ${teamBName}${notCounted > 0 ? ` • ${notCounted} uncounted` : ''}`
        : 'Allies - Axis';

    // 1. Add Summary Cards
    const summaryHtml = `
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <div class="glass-card p-4 rounded-xl text-center">
                <div class="text-xs text-slate-500 uppercase font-bold">Total Rounds</div>
                <div class="text-2xl font-black text-white">${data.rounds}</div>
            </div>
            <div class="glass-card p-4 rounded-xl text-center">
                <div class="text-xs text-slate-500 uppercase font-bold">Maps Played</div>
                <div class="text-2xl font-black text-brand-blue">${data.maps.length}</div>
            </div>
            <div class="glass-card p-4 rounded-xl text-center">
                <div class="text-xs text-slate-500 uppercase font-bold">Total Players</div>
                <div class="text-2xl font-black text-brand-purple">${data.player_count}</div>
            </div>
            <div class="glass-card p-4 rounded-xl text-center border-l-4 ${teamAScore > teamBScore ? 'border-l-brand-blue' : teamBScore > teamAScore ? 'border-l-brand-rose' : 'border-l-slate-600'}">
                <div class="text-xs text-slate-500 uppercase font-bold">Session Score${ties > 0 ? ` (${ties} ties)` : ''}</div>
                <div class="text-2xl font-black ${scoreColor}">${teamAScore} - ${teamBScore}</div>
                <div class="text-xs text-slate-400 mt-1">${escapeHtml(scoreNote)}</div>
            </div>
        </div>
    `;
    container.insertAdjacentHTML('beforeend', summaryHtml);

    // 2. Add Charts Section
    const chartsHtml = `
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <div class="glass-panel p-6 rounded-xl">
                <h3 class="font-bold text-white mb-4">Map Distribution</h3>
                <div class="h-48 relative">
                    <canvas id="sessionMapChart"></canvas>
                </div>
            </div>
            <div class="glass-panel p-6 rounded-xl">
                <h3 class="font-bold text-white mb-4">Round Outcomes</h3>
                <div class="h-48 relative">
                    <canvas id="sessionOutcomeChart"></canvas>
                </div>
            </div>
            <div class="glass-panel p-6 rounded-xl flex items-center justify-center" id="session-mvp-widget">
                <div class="text-center">
                    <h3 class="font-bold text-white mb-2">Session MVP</h3>
                    <div class="w-20 h-20 rounded-full bg-gradient-to-br from-brand-gold to-brand-amber mx-auto flex items-center justify-center text-2xl font-black text-white shadow-[0_0_30px_rgba(251,191,36,0.4)] mb-4">
                        ?
                    </div>
                    <p class="text-slate-400 text-xs">Loading...</p>
                </div>
            </div>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
            <div class="glass-panel p-6 rounded-xl">
                <h3 class="font-bold text-white mb-4">Team Comparison</h3>
                <div class="h-56 relative">
                    <canvas id="sessionTeamChart"></canvas>
                </div>
            </div>
            <div class="glass-panel p-6 rounded-xl">
                <h3 class="font-bold text-white mb-4">Player Performance (DPM vs K/D)</h3>
                <div class="h-56 relative">
                    <canvas id="sessionScatterChart"></canvas>
                </div>
            </div>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
            <div class="glass-panel p-6 rounded-xl">
                <h3 class="font-bold text-white mb-4">Time Alive vs Dead</h3>
                <div class="h-56 relative">
                    <canvas id="sessionTimeChart"></canvas>
                </div>
            </div>
            <div class="glass-panel p-6 rounded-xl">
                <h3 class="font-bold text-white mb-4">Damage Given vs Received</h3>
                <div class="h-56 relative">
                    <canvas id="sessionDamageChart"></canvas>
                </div>
            </div>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
            <div class="glass-panel p-6 rounded-xl">
                <h3 class="font-bold text-white mb-4">Session DPM Timeline</h3>
                <div class="h-56 relative">
                    <canvas id="sessionTimelineChart"></canvas>
                </div>
            </div>
            <div class="glass-panel p-6 rounded-xl">
                <h3 class="font-bold text-white mb-4">Top 3 Player Radar</h3>
                <div class="h-56 relative">
                    <canvas id="sessionRadarChart"></canvas>
                </div>
            </div>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
            <div class="glass-panel p-6 rounded-xl">
                <h3 class="font-bold text-white mb-4">Damage Efficiency</h3>
                <div class="h-56 relative">
                    <canvas id="sessionEfficiencyChart"></canvas>
                </div>
            </div>
            <div class="glass-panel p-6 rounded-xl">
                <h3 class="font-bold text-white mb-4">Selfkill Heatmap</h3>
                <div class="h-56 relative">
                    <canvas id="sessionSelfkillChart"></canvas>
                </div>
            </div>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
            <div class="glass-panel p-6 rounded-xl">
                <h3 class="font-bold text-white mb-4">Team Utility Mix</h3>
                <div class="h-56 relative">
                    <canvas id="sessionUtilityChart"></canvas>
                </div>
            </div>
            <div class="glass-panel p-6 rounded-xl">
                <h3 class="font-bold text-white mb-4">Objective Pressure (Prototype)</h3>
                <div class="h-56 relative flex items-center justify-center text-xs text-slate-500">
                    Objective stats coming next.
                </div>
            </div>
        </div>
    `;
    container.insertAdjacentHTML('beforeend', chartsHtml);

    // Initialize Charts
    setTimeout(() => {
        // Map Chart
        const ctxMap = document.getElementById('sessionMapChart');
        if (ctxMap) {
            new Chart(ctxMap.getContext('2d'), {
                type: 'doughnut',
                data: {
                    labels: Object.keys(data.map_counts),
                    datasets: [{
                        data: Object.values(data.map_counts),
                        backgroundColor: [
                            'rgba(59, 130, 246, 0.8)',
                            'rgba(139, 92, 246, 0.8)',
                            'rgba(16, 185, 129, 0.8)',
                            'rgba(244, 63, 94, 0.8)',
                            'rgba(6, 182, 212, 0.8)'
                        ],
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'right', labels: { color: '#94a3b8', font: { size: 10 } } }
                    }
                }
            });
        }

        // Outcome Chart
        const ctxOutcome = document.getElementById('sessionOutcomeChart');
        if (ctxOutcome) {
            const outcomeLabels = [];
            const outcomeData = [];
            const outcomeColors = [];

            if (teamAWins > 0 || teamBWins > 0 || ties > 0 || notCounted > 0) {
                outcomeLabels.push(teamAName, teamBName);
                outcomeData.push(teamAWins, teamBWins);
                outcomeColors.push(
                    'rgba(16, 185, 129, 0.8)', // Emerald
                    'rgba(244, 63, 94, 0.8)'   // Rose
                );

                if (ties > 0) {
                    outcomeLabels.push('Ties');
                    outcomeData.push(ties);
                    outcomeColors.push('rgba(148, 163, 184, 0.8)'); // Slate
                }
                if (notCounted > 0) {
                    outcomeLabels.push('Uncounted');
                    outcomeData.push(notCounted);
                    outcomeColors.push('rgba(99, 102, 241, 0.5)'); // Indigo
                }
            }

            new Chart(ctxOutcome.getContext('2d'), {
                type: 'pie',
                data: {
                    labels: outcomeLabels.length > 0 ? outcomeLabels : ['No data'],
                    datasets: [{
                        data: outcomeData.length > 0 ? outcomeData : [1],
                        backgroundColor: outcomeColors.length > 0 ? outcomeColors : ['rgba(148, 163, 184, 0.5)'],
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'right', labels: { color: '#94a3b8', font: { size: 10 } } }
                    }
                }
            });
        }

        // Team Comparison Chart
        const ctxTeam = document.getElementById('sessionTeamChart');
        if (ctxTeam && Array.isArray(data.teams) && data.teams.length >= 2) {
            const teamStats = data.teams.map(team => {
                const players = Array.isArray(team.players) ? team.players : [];
                const totals = players.reduce((acc, p) => {
                    acc.kills += Number(p.kills || 0);
                    acc.deaths += Number(p.deaths || 0);
                    acc.damage += Number(p.damage_given || 0);
                    acc.revives += Number(p.revives_given || 0);
                    acc.useful += Number(p.useful_kills || 0);
                    acc.selfKills += Number(p.self_kills || 0);
                    return acc;
                }, { kills: 0, deaths: 0, damage: 0, revives: 0, useful: 0, selfKills: 0 });
                return {
                    name: team.name || 'Team',
                    totals
                };
            });

            const labels = ['Kills', 'Deaths', 'Damage', 'Revives', 'Useful Kills', 'Self Kills'];
            const colors = [
                'rgba(59, 130, 246, 0.8)',
                'rgba(244, 63, 94, 0.8)'
            ];
            const datasets = teamStats.map((team, idx) => ({
                label: team.name,
                data: [
                    team.totals.kills,
                    team.totals.deaths,
                    team.totals.damage,
                    team.totals.revives,
                    team.totals.useful,
                    team.totals.selfKills
                ],
                backgroundColor: colors[idx % colors.length],
                borderRadius: 6
            }));

            new Chart(ctxTeam.getContext('2d'), {
                type: 'bar',
                data: { labels, datasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'bottom', labels: { color: '#94a3b8', font: { size: 10 } } }
                    },
                    scales: {
                        x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148, 163, 184, 0.1)' } },
                        y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148, 163, 184, 0.1)' } }
                    }
                }
            });
        }

        // Player Performance Scatter
        const ctxScatter = document.getElementById('sessionScatterChart');
        if (ctxScatter && Array.isArray(data.teams)) {
            const players = data.teams.flatMap(team => team.players || []);
            if (players.length > 0) {
                const points = players.map(p => ({
                    x: Number(p.kd || 0),
                    y: Number(p.dpm || 0),
                    name: p.name || 'Unknown'
                }));

                new Chart(ctxScatter.getContext('2d'), {
                    type: 'scatter',
                    data: {
                        datasets: [{
                            label: 'Players',
                            data: points,
                            backgroundColor: 'rgba(16, 185, 129, 0.8)'
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            x: { title: { display: true, text: 'K/D', color: '#94a3b8' }, ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148, 163, 184, 0.1)' } },
                            y: { title: { display: true, text: 'DPM', color: '#94a3b8' }, ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148, 163, 184, 0.1)' } }
                        },
                        plugins: {
                            legend: { display: false },
                            tooltip: {
                                callbacks: {
                                    label: (ctx) => `${ctx.raw.name}: K/D ${ctx.raw.x.toFixed(2)}, DPM ${Math.round(ctx.raw.y)}`
                                }
                            }
                        }
                    }
                });
            }
        }

        // Time Alive vs Dead (top 8 by playtime)
        const ctxTime = document.getElementById('sessionTimeChart');
        if (ctxTime && Array.isArray(data.teams)) {
            const players = data.teams.flatMap(team => team.players || []);
            const topPlayers = players
                .slice()
                .sort((a, b) => Number(b.time_played_seconds || 0) - Number(a.time_played_seconds || 0))
                .slice(0, 8);
            if (topPlayers.length > 0) {
                const labels = topPlayers.map(p => p.name || 'Unknown');
                const timeDead = topPlayers.map(p => Math.round((p.time_dead_seconds || 0) / 60));
                const timeAlive = topPlayers.map(p => Math.max(0, Math.round((p.time_played_seconds || 0) / 60) - Math.round((p.time_dead_seconds || 0) / 60)));

                new Chart(ctxTime.getContext('2d'), {
                    type: 'bar',
                    data: {
                        labels,
                        datasets: [
                            { label: 'Alive (min)', data: timeAlive, backgroundColor: 'rgba(34, 197, 94, 0.8)', stack: 'time' },
                            { label: 'Dead (min)', data: timeDead, backgroundColor: 'rgba(248, 113, 113, 0.8)', stack: 'time' }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { position: 'bottom', labels: { color: '#94a3b8', font: { size: 10 } } }
                        },
                        scales: {
                            x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148, 163, 184, 0.1)' } },
                            y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148, 163, 184, 0.1)' } }
                        }
                    }
                });
            }
        }

        // Damage Given vs Received (top 8 by damage given)
        const ctxDamage = document.getElementById('sessionDamageChart');
        if (ctxDamage && Array.isArray(data.teams)) {
            const players = data.teams.flatMap(team => team.players || []);
            const topPlayers = players
                .slice()
                .sort((a, b) => Number(b.damage_given || 0) - Number(a.damage_given || 0))
                .slice(0, 8);

            if (topPlayers.length > 0) {
                const labels = topPlayers.map(p => p.name || 'Unknown');
                const damageGiven = topPlayers.map(p => Number(p.damage_given || 0));
                const damageReceived = topPlayers.map(p => Number(p.damage_received || 0));

                new Chart(ctxDamage.getContext('2d'), {
                    type: 'bar',
                    data: {
                        labels,
                        datasets: [
                            { label: 'Damage Given', data: damageGiven, backgroundColor: 'rgba(59, 130, 246, 0.8)' },
                            { label: 'Damage Received', data: damageReceived, backgroundColor: 'rgba(244, 63, 94, 0.7)' }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { position: 'bottom', labels: { color: '#94a3b8', font: { size: 10 } } }
                        },
                        scales: {
                            x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148, 163, 184, 0.1)' } },
                            y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148, 163, 184, 0.1)' } }
                        }
                    }
                });
            }
        }
    }, 100);

    // Load MVP widget
    loadSessionMVP();

    // Load advanced graph data for timeline + radar + efficiency + heatmap
    loadSessionGraphExtras(data.date, data);

    // 3. Render Map Breakdown
    if (hasScoring && Array.isArray(scoring.maps) && scoring.maps.length > 0) {
        const rows = scoring.maps.map((m) => {
            const mapName = escapeHtml(mapLabel(m.map || 'Unknown'));
            const counted = m.counted !== false;
            const note = escapeHtml((m.note || '').trim());
            const teamATime = escapeHtml(m.team_a_time || '--');
            const teamBTime = escapeHtml(m.team_b_time || '--');
            const aPts = Number(m.team_a_points || 0);
            const bPts = Number(m.team_b_points || 0);
            const teamAWin = aPts > bPts;
            const teamBWin = bPts > aPts;
            const statusText = counted ? 'Counted' : (note || 'Not counted');
            const statusClass = counted ? 'text-slate-400' : 'text-amber-300';
            const rowOpacity = counted ? '' : 'opacity-70';
            const mapImg = mapImageFor(m.map || '');
            const isFallbackMap = mapImg.includes('map_generic.svg');
            const winnerSide = Number(m.winner_side || 0);
            const winnerIcon = winnerSide === 1 ? AXIS_ICON : winnerSide === 2 ? ALLIES_ICON : null;
            const winnerLabel = winnerSide === 1 ? 'Axis' : winnerSide === 2 ? 'Allies' : 'Side ?';

            const mapThumb = isFallbackMap
                ? `
                    <div class="w-full h-full flex items-center justify-center text-[10px] font-bold text-white bg-gradient-to-br from-slate-700 to-slate-900">
                        <span class="px-1 text-center truncate" title="${mapName}">${mapName}</span>
                    </div>
                  `
                : `<div class="w-full h-full bg-cover bg-center" style="background-image: url('${mapImg}')"></div>`;

            return `
                <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-4 p-3 rounded-lg bg-slate-900/40 ${rowOpacity}">
                    <div class="flex items-center gap-3">
                        <div class="w-16 h-12 rounded-md bg-slate-900/60 border border-white/10 overflow-hidden shadow-inner">
                            ${mapThumb}
                        </div>
                        <div>
                            <div class="font-bold text-white">${mapName}</div>
                            <div class="text-xs ${statusClass}">${statusText}</div>
                        </div>
                    </div>
                    <div class="flex flex-wrap items-center gap-3 text-sm">
                        <span class="${teamAWin ? 'text-brand-emerald font-bold' : 'text-slate-300'}">${escapeHtml(teamAName)} ${aPts}</span>
                        <span class="text-slate-500">vs</span>
                        <span class="${teamBWin ? 'text-brand-rose font-bold' : 'text-slate-300'}">${escapeHtml(teamBName)} ${bPts}</span>
                    </div>
                    <div class="flex items-center gap-2 text-xs text-slate-400">
                        <span>${teamATime} / ${teamBTime}</span>
                        ${winnerIcon ? `
                            <span class="flex items-center gap-1 px-2 py-1 rounded-full bg-slate-900/60 border border-white/10">
                                <img src="${winnerIcon}" alt="${winnerLabel}" class="w-4 h-4" />
                                <span>${winnerLabel}</span>
                            </span>
                        ` : ''}
                    </div>
                </div>
            `;
        }).join('');

        const mapBreakdownHtml = `
            <div class="glass-panel p-5 rounded-xl mt-6">
                <h3 class="font-bold text-white mb-3">Map Breakdown</h3>
                <div class="space-y-2">${rows}</div>
            </div>
        `;
        container.insertAdjacentHTML('beforeend', mapBreakdownHtml);
    }

    // Team rosters grouped by team
    if (Array.isArray(data.teams) && data.teams.length > 0) {
        const teamHtml = data.teams.map((team, idx) => {
            const players = Array.isArray(team.players) ? team.players : [];
            const icon = idx === 0 ? ALLIES_ICON : AXIS_ICON;
            const rows = players.map(player => {
                const name = escapeHtml(player.name || 'Unknown');
                const kills = Number(player.kills || 0);
                const deaths = Number(player.deaths || 0);
                const dpm = Number(player.dpm || 0);
                const kd = (player.kd || 0).toFixed ? player.kd.toFixed(2) : Number(player.kd || 0).toFixed(2);
                const timePlayed = formatDuration(player.time_played_seconds);
                const selfKills = Number(player.self_kills || 0);
                const fullSelf = Number(player.full_selfkills || 0);
                return `
                    <div class="flex items-center justify-between text-sm py-2 border-b border-white/5">
                        <div class="flex items-center gap-2">
                            <span class="font-semibold text-white">${name}</span>
                            <span class="text-xs text-slate-500">K/D ${kd}</span>
                        </div>
                        <div class="flex items-center gap-3 text-xs text-slate-400">
                            <span>K ${kills}</span>
                            <span>D ${deaths}</span>
                            <span>DPM ${dpm}</span>
                            <span>⏱ ${timePlayed}</span>
                            <span>SK ${selfKills}</span>
                            <span>FSK ${fullSelf}</span>
                        </div>
                    </div>
                `;
            }).join('');

            return `
                <div class="glass-panel p-5 rounded-xl">
                    <div class="flex items-center justify-between mb-3">
                        <div class="flex items-center gap-2">
                            <img src="${icon}" alt="Team" class="w-6 h-6" />
                            <h3 class="font-bold text-white">${escapeHtml(team.name || `Team ${idx + 1}`)}</h3>
                        </div>
                        <span class="text-xs text-slate-500">${players.length} players</span>
                    </div>
                    <div class="divide-y divide-white/5">
                        ${rows || '<div class="text-xs text-slate-500 py-2">No player stats</div>'}
                    </div>
                </div>
            `;
        }).join('');

        const rosterHtml = `
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
                ${teamHtml}
            </div>
        `;
        container.insertAdjacentHTML('beforeend', rosterHtml);
    }

    if (Array.isArray(data.unassigned_players) && data.unassigned_players.length > 0) {
        const names = data.unassigned_players.map(p => escapeHtml(p.name)).join(', ');
        container.insertAdjacentHTML(
            'beforeend',
            `<div class="mt-4 text-xs text-amber-300">Unassigned players: ${names}</div>`
        );
    }

    if (Array.isArray(data.stats_checks) && data.stats_checks.length > 0) {
        const checks = data.stats_checks.map(check => `<li>${escapeHtml(check)}</li>`).join('');
        container.insertAdjacentHTML(
            'beforeend',
            `<div class="glass-panel p-4 rounded-xl mt-4">
                <h3 class="font-bold text-white mb-2">Stat Checks</h3>
                <ul class="text-xs text-amber-300 space-y-1">${checks}</ul>
            </div>`
        );
    }

    // Fallback: simple map list
    if (!data.maps || data.maps.length === 0) {
        return;
    }
    data.maps.forEach((mapData) => {
        const safeMapName = escapeHtml(mapData.name || mapData);
        const mapHtml = `
            <div class="glass-card p-4 rounded-lg mb-3">
                <div class="font-bold text-white">${safeMapName}</div>
            </div>
        `;
        container.insertAdjacentHTML('beforeend', mapHtml);
    });
}

async function loadSessionGraphExtras(date, data) {
    let graphData = null;
    try {
        const sessionId = data && data.gaming_session_id ? `?gaming_session_id=${data.gaming_session_id}` : '';
        graphData = await fetchJSON(`${API_BASE}/sessions/${date}/graphs${sessionId}`);
    } catch (e) {
        console.warn('Failed to load session graph stats:', e);
        return;
    }

    if (!graphData || !Array.isArray(graphData.players)) {
        return;
    }

    const players = graphData.players;

    // DPM Timeline (average across players)
    const ctxTimeline = document.getElementById('sessionTimelineChart');
    if (ctxTimeline) {
        const labelOrder = [];
        const labelIndex = new Map();
        const sums = [];
        const counts = [];

        players.forEach(player => {
            (player.dpm_timeline || []).forEach(entry => {
                if (!labelIndex.has(entry.label)) {
                    labelIndex.set(entry.label, labelOrder.length);
                    labelOrder.push(entry.label);
                    sums.push(0);
                    counts.push(0);
                }
                const idx = labelIndex.get(entry.label);
                sums[idx] += Number(entry.dpm || 0);
                counts[idx] += 1;
            });
        });

        const avgDpm = sums.map((sum, idx) => counts[idx] > 0 ? Math.round(sum / counts[idx]) : 0);

        new Chart(ctxTimeline.getContext('2d'), {
            type: 'line',
            data: {
                labels: labelOrder,
                datasets: [{
                    label: 'Avg DPM',
                    data: avgDpm,
                    borderColor: 'rgba(34, 197, 94, 0.9)',
                    backgroundColor: 'rgba(34, 197, 94, 0.2)',
                    tension: 0.3,
                    fill: true,
                    pointRadius: 3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom', labels: { color: '#94a3b8', font: { size: 10 } } }
                },
                scales: {
                    x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148, 163, 184, 0.1)' } },
                    y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148, 163, 184, 0.1)' } }
                }
            }
        });
    }

    // Top 3 Player Radar
    const ctxRadar = document.getElementById('sessionRadarChart');
    if (ctxRadar) {
        const topPlayers = players
            .slice()
            .sort((a, b) => (b.combat_offense?.dpm || 0) - (a.combat_offense?.dpm || 0))
            .slice(0, 3);

        if (topPlayers.length > 0) {
            const labels = ['Kills', 'DPM', 'Revives', 'FragPotential', 'DamageEff', 'Survival', 'TimeDenied'];
            const maxValues = {
                kills: Math.max(...topPlayers.map(p => p.combat_offense?.kills || 0), 1),
                dpm: Math.max(...topPlayers.map(p => p.combat_offense?.dpm || 0), 1),
                revives: Math.max(...topPlayers.map(p => p.combat_defense?.revives || 0), 1),
                frag: Math.max(...topPlayers.map(p => p.advanced_metrics?.frag_potential || 0), 1),
                efficiency: 100,
                survival: 100,
                denied: Math.max(...topPlayers.map(p => p.advanced_metrics?.time_denied || 0), 1)
            };

            const colors = [
                'rgba(59, 130, 246, 0.6)',
                'rgba(244, 63, 94, 0.6)',
                'rgba(16, 185, 129, 0.6)'
            ];

            const datasets = topPlayers.map((player, idx) => ({
                label: player.name,
                data: [
                    Math.round((player.combat_offense?.kills || 0) / maxValues.kills * 100),
                    Math.round((player.combat_offense?.dpm || 0) / maxValues.dpm * 100),
                    Math.round((player.combat_defense?.revives || 0) / maxValues.revives * 100),
                    Math.round((player.advanced_metrics?.frag_potential || 0) / maxValues.frag * 100),
                    Math.round(player.advanced_metrics?.damage_efficiency || 0),
                    Math.round(player.advanced_metrics?.survival_rate || 0),
                    Math.round((player.advanced_metrics?.time_denied || 0) / maxValues.denied * 100)
                ],
                backgroundColor: colors[idx % colors.length],
                borderColor: colors[idx % colors.length],
                borderWidth: 2
            }));

            new Chart(ctxRadar.getContext('2d'), {
                type: 'radar',
                data: { labels, datasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'bottom', labels: { color: '#94a3b8', font: { size: 10 } } }
                    },
                    scales: {
                        r: {
                            angleLines: { color: 'rgba(148, 163, 184, 0.2)' },
                            grid: { color: 'rgba(148, 163, 184, 0.2)' },
                            pointLabels: { color: '#94a3b8', font: { size: 10 } },
                            ticks: { display: false }
                        }
                    }
                }
            });
        }
    }

    // Damage Efficiency Chart
    const ctxEfficiency = document.getElementById('sessionEfficiencyChart');
    if (ctxEfficiency) {
        const topPlayers = players
            .slice()
            .sort((a, b) => (b.combat_offense?.damage_given || 0) - (a.combat_offense?.damage_given || 0))
            .slice(0, 8);
        const labels = topPlayers.map(p => p.name);
        const values = topPlayers.map(p => p.advanced_metrics?.damage_efficiency || 0);

        new Chart(ctxEfficiency.getContext('2d'), {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label: 'Damage Efficiency (%)',
                    data: values,
                    backgroundColor: 'rgba(59, 130, 246, 0.8)',
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148, 163, 184, 0.1)' } },
                    y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148, 163, 184, 0.1)' }, max: 100 }
                }
            }
        });
    }

    // Selfkill Heatmap (bar with intensity)
    const ctxSelfkill = document.getElementById('sessionSelfkillChart');
    if (ctxSelfkill) {
        const topPlayers = players
            .slice()
            .sort((a, b) => (b.combat_defense?.self_kills || 0) - (a.combat_defense?.self_kills || 0))
            .slice(0, 10);
        const labels = topPlayers.map(p => p.name);
        const values = topPlayers.map(p => p.combat_defense?.self_kills || 0);
        const maxValue = Math.max(...values, 1);
        const colors = values.map(v => {
            const intensity = Math.min(1, v / maxValue);
            return `rgba(244, 63, 94, ${0.25 + intensity * 0.65})`;
        });

        new Chart(ctxSelfkill.getContext('2d'), {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label: 'Self Kills',
                    data: values,
                    backgroundColor: colors,
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148, 163, 184, 0.1)' } },
                    y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148, 163, 184, 0.1)' } }
                }
            }
        });
    }

    // Team Utility Mix
    const ctxUtility = document.getElementById('sessionUtilityChart');
    if (ctxUtility && Array.isArray(data.teams) && data.teams.length >= 2) {
        const teamStats = data.teams.map(team => {
            const players = Array.isArray(team.players) ? team.players : [];
            const totals = players.reduce((acc, p) => {
                acc.revives += Number(p.revives_given || 0);
                acc.gibs += Number(p.gibs || 0);
                acc.useful += Number(p.useful_kills || 0);
                acc.timesRevived += Number(p.times_revived || 0);
                acc.denied += Number(p.denied_playtime || 0);
                return acc;
            }, { revives: 0, gibs: 0, useful: 0, timesRevived: 0, denied: 0 });
            return { name: team.name || 'Team', totals };
        });

        const labels = ['Revives', 'Gibs', 'Useful Kills', 'Times Revived', 'Time Denied'];
        const datasets = teamStats.map((team, idx) => ({
            label: team.name,
            data: [
                team.totals.revives,
                team.totals.gibs,
                team.totals.useful,
                team.totals.timesRevived,
                Math.round(team.totals.denied / 60)
            ],
            backgroundColor: idx === 0 ? 'rgba(14, 165, 233, 0.8)' : 'rgba(251, 113, 133, 0.8)',
            borderRadius: 6
        }));

        new Chart(ctxUtility.getContext('2d'), {
            type: 'bar',
            data: { labels, datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom', labels: { color: '#94a3b8', font: { size: 10 } } }
                },
                scales: {
                    x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148, 163, 184, 0.1)' } },
                    y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148, 163, 184, 0.1)' } }
                }
            }
        });
    }
}

/**
 * Load session MVP widget
 */
export async function loadSessionMVP(sessionDate) {
    const widget = document.getElementById('session-mvp-widget');
    if (!widget) return;

    try {
        const leaderboard = await fetchJSON(`${API_BASE}/stats/session-leaderboard?limit=1`);

        if (leaderboard.length === 0) {
            widget.innerHTML = `
                <h3 class="font-bold text-white mb-2">Session MVP</h3>
                <div class="w-20 h-20 rounded-full bg-slate-800 mx-auto flex items-center justify-center text-2xl font-black text-slate-600 mb-4">
                    ?
                </div>
                <p class="text-slate-500 text-xs">No MVP data</p>
            `;
            return;
        }

        const mvp = leaderboard[0];
        const safeName = escapeHtml(mvp.name);
        const jsName = escapeJsString(mvp.name);
        const initials = escapeHtml(mvp.name.substring(0, 2).toUpperCase());

        widget.innerHTML = `
            <h3 class="font-bold text-white mb-2">Session MVP</h3>
            <div class="w-20 h-20 rounded-full bg-gradient-to-br from-brand-gold to-brand-amber mx-auto flex items-center justify-center text-2xl font-black text-white shadow-[0_0_30px_rgba(251,191,36,0.4)] mb-4 animate-pulse-slow cursor-pointer" onclick="loadPlayerProfile('${jsName}')">
                ${initials}
            </div>
            <p class="font-bold text-white mb-1 cursor-pointer hover:text-brand-gold transition" onclick="loadPlayerProfile('${jsName}')">${safeName}</p>
            <div class="flex items-center justify-center gap-3 text-xs">
                <span class="text-slate-400">DPM: <span class="font-bold text-brand-emerald">${mvp.dpm}</span></span>
                <span class="text-slate-600">•</span>
                <span class="text-slate-400">K/D: <span class="font-bold text-white">${(mvp.kills / (mvp.deaths || 1)).toFixed(2)}</span></span>
            </div>
            <div class="mt-2 px-3 py-1 rounded-full bg-brand-gold/10 border border-brand-gold/20 text-brand-gold text-[10px] font-bold uppercase">
                Top Performer
            </div>
        `;
        if (typeof lucide !== 'undefined') lucide.createIcons();

    } catch (e) {
        console.error('Failed to load MVP:', e);
        widget.innerHTML = `
            <h3 class="font-bold text-white mb-2">Session MVP</h3>
            <div class="w-20 h-20 rounded-full bg-slate-800 mx-auto flex items-center justify-center text-2xl font-black text-slate-600 mb-4">
                ?
            </div>
            <p class="text-red-500 text-xs">Failed to load</p>
        `;
    }
}

// ============================================================================
// SESSIONS VIEW - Gaming Session Browser
// ============================================================================

/**
 * Initialize sessions view
 */
export async function loadSessionsView() {
    console.log('🎮 loadSessionsView called');
    sessionsData = [];
    sessionsOffset = 0;
    expandedSessions.clear();
    await loadSessions(true);
}

/**
 * Load sessions list
 */
export async function loadSessions(reset = false) {
    console.log('📦 loadSessions called, reset:', reset);
    const container = document.getElementById('sessions-list');
    if (!container) {
        console.error('❌ sessions-list container not found!');
        return;
    }

    if (reset) {
        container.innerHTML = `
            <div class="text-center py-12">
                <i data-lucide="loader" class="w-8 h-8 text-brand-blue animate-spin mx-auto mb-4"></i>
                <div class="text-slate-400">Loading sessions...</div>
            </div>
        `;
        if (typeof lucide !== 'undefined') lucide.createIcons();
    }

    try {
        const data = await fetchJSON(`${API_BASE}/sessions?limit=${SESSIONS_LIMIT}&offset=${sessionsOffset}`);
        console.log('📊 Sessions data received:', data.length, 'sessions');

        if (reset) {
            container.innerHTML = '';
            sessionsData = data;
        } else {
            sessionsData = [...sessionsData, ...data];
        }

        // Render sessions
        data.forEach((session) => {
            const html = renderSessionCard(session);
            container.insertAdjacentHTML('beforeend', html);
        });

        if (typeof lucide !== 'undefined') lucide.createIcons();

        // Show/hide load more button
        const loadMoreBtn = document.getElementById('sessions-load-more');
        if (loadMoreBtn) {
            loadMoreBtn.classList.toggle('hidden', data.length < SESSIONS_LIMIT);
        }

        sessionsOffset += data.length;

    } catch (e) {
        console.error('Failed to load sessions:', e);
        container.innerHTML = '<div class="text-center text-red-500 py-12">Failed to load sessions</div>';
    }
}

/**
 * Load more sessions (pagination)
 */
export function loadMoreSessions() {
    loadSessions(false);
}

/**
 * Render a single session card
 */
function renderSessionCard(session) {
    const safeDate = escapeHtml(session.date);
    const safeTimeAgo = escapeHtml(session.time_ago);
    const safeFormattedDate = escapeHtml(session.formatted_date);
    const isExpanded = expandedSessions.has(session.date);
    const missingRounds = session.rounds % 2 !== 0;
    const sessionId = session.session_id;

    // Map tiles
    const mapTiles = session.maps_played.slice(0, 5).map(map => mapTile(map)).join('');
    const moreMapsBadge = session.maps_played.length > 5
        ? `<span class="text-slate-500 text-xs">+${session.maps_played.length - 5} more</span>`
        : '';

    return `
        <div class="glass-panel rounded-xl overflow-hidden session-card" data-date="${safeDate}">
            <!-- Session Header (clickable) -->
            <div class="p-6 cursor-pointer hover:bg-white/5 transition" onclick="toggleSession('${safeDate}')">
                <div class="flex flex-wrap items-center justify-between gap-4">
                    <!-- Left: Date & Time Ago -->
                    <div class="flex items-center gap-4">
                        <div class="w-12 h-12 rounded-lg bg-gradient-to-br from-brand-purple to-brand-blue flex items-center justify-center">
                            <i data-lucide="calendar" class="w-6 h-6 text-white"></i>
                        </div>
                        <div>
                            <div class="text-lg font-black text-white">${safeFormattedDate}</div>
                            <div class="text-sm text-slate-400 flex items-center gap-2">
                                <span>${safeTimeAgo}</span>
                                ${sessionId ? `<span class="px-2 py-0.5 rounded-full bg-slate-800 text-[10px] uppercase tracking-wide text-slate-400">Session ${sessionId}</span>` : ''}
                                ${missingRounds ? `<span class="px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 text-[10px] uppercase tracking-wide">Missing Round</span>` : ''}
                            </div>
                        </div>
                    </div>

                    <!-- Center: Stats -->
                    <div class="flex items-center gap-6">
                        <div class="text-center">
                            <div class="text-2xl font-black text-brand-cyan">${session.players}</div>
                            <div class="text-xs text-slate-500 uppercase">Players</div>
                        </div>
                        <div class="text-center">
                            <div class="text-2xl font-black text-brand-purple">${session.maps}</div>
                            <div class="text-xs text-slate-500 uppercase">Maps</div>
                        </div>
                        <div class="text-center">
                            <div class="text-2xl font-black text-brand-amber">${session.rounds}</div>
                            <div class="text-xs text-slate-500 uppercase">Rounds</div>
                        </div>
                        <div class="text-center">
                            <div class="text-2xl font-black ${session.allies_wins > session.axis_wins ? 'text-brand-blue' : session.axis_wins > session.allies_wins ? 'text-brand-rose' : 'text-slate-400'}">${session.allies_wins} - ${session.axis_wins}</div>
                            <div class="text-xs text-slate-500 uppercase">Score${session.draws > 0 ? ` (${session.draws} draws)` : ''}</div>
                        </div>
                    </div>

                    <!-- Right: Expand Icon -->
                    <div class="flex items-center gap-3">
                        <i data-lucide="${isExpanded ? 'chevron-up' : 'chevron-down'}"
                           class="w-5 h-5 text-slate-400 session-chevron transition-transform"></i>
                    </div>
                </div>

                <!-- Maps Played -->
                <div class="flex flex-wrap items-center gap-2 mt-4">
                    ${mapTiles}
                    ${moreMapsBadge}
                </div>
            </div>

            <!-- Session Details (expandable) -->
            <div class="session-details ${isExpanded ? '' : 'hidden'}" id="session-details-${safeDate}">
                <div class="border-t border-white/5 p-6 bg-black/20">
                    <div class="text-center py-8 text-slate-500">
                        <i data-lucide="loader" class="w-6 h-6 animate-spin mx-auto mb-2"></i>
                        Loading session details...
                    </div>
                </div>
            </div>
        </div>
    `;
}

/**
 * Toggle session details expansion
 */
export async function toggleSession(date) {
    const detailsEl = document.getElementById(`session-details-${date}`);
    const cardEl = document.querySelector(`.session-card[data-date="${date}"]`);
    const chevron = cardEl?.querySelector('.session-chevron');

    if (!detailsEl) return;

    const isHidden = detailsEl.classList.contains('hidden');

    if (isHidden) {
        // Expand
        detailsEl.classList.remove('hidden');
        expandedSessions.add(date);
        if (chevron) {
            chevron.setAttribute('data-lucide', 'chevron-up');
            if (typeof lucide !== 'undefined') lucide.createIcons();
        }
        // Load details if not already loaded
        if (detailsEl.querySelector('.session-leaderboard') === null) {
            await loadSessionDetailsExpanded(date);
        }
    } else {
        // Collapse
        detailsEl.classList.add('hidden');
        expandedSessions.delete(date);
        if (chevron) {
            chevron.setAttribute('data-lucide', 'chevron-down');
            if (typeof lucide !== 'undefined') lucide.createIcons();
        }
    }
}

// Session graphs state
let sessionGraphsData = {};
let sessionGraphCharts = {};
let currentGraphTab = 'offense';

/**
 * Load expanded session details
 */
async function loadSessionDetailsExpanded(date) {
    const detailsEl = document.getElementById(`session-details-${date}`);
    if (!detailsEl) return;

    try {
        const data = await fetchJSON(`${API_BASE}/sessions/${date}`);

        // Build leaderboard HTML
        const leaderboardHtml = data.leaderboard.map((player, idx) => {
            const safeName = escapeHtml(player.name);
            const jsName = escapeJsString(player.name);
            const rankColors = ['text-brand-gold', 'text-slate-300', 'text-amber-600'];
            const rankColor = rankColors[idx] || 'text-slate-400';
            return `
                <div class="flex items-center justify-between p-3 rounded-lg hover:bg-white/5 transition cursor-pointer"
                     onclick="loadPlayerProfile('${jsName}')">
                    <div class="flex items-center gap-3">
                        <span class="w-6 text-center font-black ${rankColor}">#${player.rank}</span>
                        <span class="font-bold text-white">${safeName}</span>
                    </div>
                    <div class="flex items-center gap-4 text-sm">
                        <span class="text-brand-cyan font-mono">${player.dpm} DPM</span>
                        <span class="text-slate-400">${player.kills}/${player.deaths}</span>
                        <span class="text-slate-500">${player.kd} K/D</span>
                    </div>
                </div>
            `;
        }).join('');

        // Build matches HTML
        const matchesHtml = data.matches.map(mapMatch => {
            const displayMapName = mapLabel(mapMatch.map_name || 'Unknown');
            const safeMapName = escapeHtml(displayMapName);
            const mapImg = mapImageFor(mapMatch.map_name || '');
            const isFallbackMap = mapImg.includes('map_generic.svg');
            const mapThumb = isFallbackMap
                ? `
                    <div class="w-16 h-12 rounded-md bg-slate-900/70 border border-white/10 flex items-center justify-center text-[9px] font-bold text-white px-1 text-center leading-tight">
                        <span class="truncate" title="${safeMapName}">${safeMapName}</span>
                    </div>
                  `
                : `
                    <div class="relative w-16 h-12 rounded-md overflow-hidden border border-white/10 bg-slate-900/60">
                        <div class="absolute inset-0 bg-cover bg-center" style="background-image: url('${mapImg}')"></div>
                        <div class="absolute bottom-0 left-0 right-0 bg-black/55 text-[9px] text-slate-100 px-1 truncate">
                            ${safeMapName}
                        </div>
                    </div>
                  `;
            const roundsHtml = mapMatch.rounds.map(round => {
                const safeWinner = escapeHtml(round.winner);
                const winnerColor = round.winner === 'Allies' ? 'text-brand-blue' :
                                   round.winner === 'Axis' ? 'text-brand-rose' : 'text-slate-400';
                return `
                    <div class="flex items-center justify-between p-2 rounded bg-black/30 cursor-pointer hover:bg-black/50 transition"
                         onclick="loadMatchDetails(${round.id})">
                        <div class="flex items-center gap-3">
                            <span class="text-xs text-slate-500">R${round.round_number}</span>
                            <span class="text-sm ${winnerColor} font-bold">${safeWinner} Win</span>
                        </div>
                        <div class="flex items-center gap-2 text-xs text-slate-500">
                            <span>${escapeHtml(round.duration || 'N/A')}</span>
                            <i data-lucide="chevron-right" class="w-4 h-4"></i>
                        </div>
                    </div>
                `;
            }).join('');

            return `
                <div class="glass-card rounded-lg p-4">
                    <div class="flex items-center gap-3 mb-3">
                        ${mapThumb}
                        <div>
                            <div class="flex items-center gap-2">
                                <i data-lucide="map" class="w-4 h-4 text-brand-cyan"></i>
                                <span class="font-bold text-white">${safeMapName}</span>
                            </div>
                            <span class="text-xs text-slate-500">${mapMatch.rounds.length} rounds</span>
                        </div>
                    </div>
                    <div class="space-y-2">
                        ${roundsHtml}
                    </div>
                </div>
            `;
        }).join('');

        detailsEl.innerHTML = `
            <div class="border-t border-white/5 p-6 bg-black/20">
                <!-- Session Graphs Toggle -->
                <div class="mb-6">
                    <button id="toggle-graphs-${date}" onclick="toggleSessionGraphs('${date}')"
                        class="flex items-center gap-2 px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-sm font-bold text-slate-300 transition">
                        <i data-lucide="bar-chart-3" class="w-4 h-4"></i>
                        <span>Show Session Graphs</span>
                        <i data-lucide="chevron-down" class="w-4 h-4 graphs-chevron"></i>
                    </button>
                </div>

                <!-- Session Graphs Section (hidden by default) -->
                <div id="session-graphs-${date}" class="hidden mb-6">
                    <!-- Graph Tabs -->
                    <div class="flex flex-wrap gap-2 mb-4">
                        <button onclick="switchGraphTab('${date}', 'offense')" 
                            class="graph-tab px-4 py-2 rounded-lg text-sm font-bold transition" data-tab="offense">
                            Combat (Offense)
                        </button>
                        <button onclick="switchGraphTab('${date}', 'defense')" 
                            class="graph-tab px-4 py-2 rounded-lg text-sm font-bold transition" data-tab="defense">
                            Combat (Defense)
                        </button>
                        <button onclick="switchGraphTab('${date}', 'advanced')" 
                            class="graph-tab px-4 py-2 rounded-lg text-sm font-bold transition" data-tab="advanced">
                            Advanced Metrics
                        </button>
                        <button onclick="switchGraphTab('${date}', 'playstyle')" 
                            class="graph-tab px-4 py-2 rounded-lg text-sm font-bold transition" data-tab="playstyle">
                            Playstyle
                        </button>
                        <button onclick="switchGraphTab('${date}', 'timeline')" 
                            class="graph-tab px-4 py-2 rounded-lg text-sm font-bold transition" data-tab="timeline">
                            DPM Timeline
                        </button>
                    </div>

                    <!-- Graph Container -->
                    <div class="glass-panel rounded-xl p-6">
                        <div id="graph-title-${date}" class="flex items-center gap-2 mb-4">
                            <i data-lucide="sword" class="w-5 h-5 text-brand-rose"></i>
                            <h3 class="text-lg font-bold text-white">Combat Stats (Offense)</h3>
                        </div>
                        
                        <!-- Player Legend -->
                        <div id="graph-legend-${date}" class="flex flex-wrap justify-center gap-4 mb-4">
                            <!-- Populated dynamically -->
                        </div>

                        <!-- Chart Canvas -->
                        <div class="relative h-80">
                            <canvas id="session-graph-${date}"></canvas>
                        </div>
                    </div>
                </div>

                <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <!-- Leaderboard -->
                    <div class="session-leaderboard">
                        <h3 class="text-lg font-bold text-white mb-4 flex items-center gap-2">
                            <i data-lucide="trophy" class="w-5 h-5 text-brand-gold"></i>
                            Top Performers
                        </h3>
                        <div class="space-y-1">
                            ${leaderboardHtml || '<div class="text-slate-500 text-center py-4">No data</div>'}
                        </div>
                    </div>

                    <!-- Matches -->
                    <div>
                        <h3 class="text-lg font-bold text-white mb-4 flex items-center gap-2">
                            <i data-lucide="swords" class="w-5 h-5 text-brand-purple"></i>
                            Maps Played
                        </h3>
                        <div class="space-y-3">
                            ${matchesHtml || '<div class="text-slate-500 text-center py-4">No matches</div>'}
                        </div>
                    </div>
                </div>
            </div>
        `;

        if (typeof lucide !== 'undefined') lucide.createIcons();
        
        // Initialize graph tab styling
        updateGraphTabStyles(date, 'offense');

    } catch (e) {
        console.error('Failed to load session details:', e);
        detailsEl.innerHTML = `
            <div class="border-t border-white/5 p-6 bg-black/20">
                <div class="text-center text-red-500 py-8">Failed to load session details</div>
            </div>
        `;
    }
}

/**
 * Toggle session graphs visibility
 */
async function toggleSessionGraphs(date) {
    const graphsEl = document.getElementById(`session-graphs-${date}`);
    const toggleBtn = document.getElementById(`toggle-graphs-${date}`);
    const chevron = toggleBtn?.querySelector('.graphs-chevron');
    
    if (!graphsEl) return;
    
    const isHidden = graphsEl.classList.contains('hidden');
    
    if (isHidden) {
        // Show graphs
        graphsEl.classList.remove('hidden');
        toggleBtn.querySelector('span').textContent = 'Hide Session Graphs';
        if (chevron) chevron.setAttribute('data-lucide', 'chevron-up');
        
        // Load graph data if not already loaded
        if (!sessionGraphsData[date]) {
            await loadSessionGraphData(date);
        } else {
            renderSessionGraph(date, currentGraphTab);
        }
    } else {
        // Hide graphs
        graphsEl.classList.add('hidden');
        toggleBtn.querySelector('span').textContent = 'Show Session Graphs';
        if (chevron) chevron.setAttribute('data-lucide', 'chevron-down');
    }
    
    if (typeof lucide !== 'undefined') lucide.createIcons();
}

/**
 * Player colors for graphs (consistent per-session ordering)
 */
const PLAYER_COLORS = [
    '#3b82f6', // blue
    '#10b981', // emerald
    '#f59e0b', // amber
    '#ef4444', // red
    '#8b5cf6', // violet
    '#06b6d4', // cyan
    '#f97316', // orange
    '#ec4899', // pink
    '#84cc16', // lime
    '#6366f1', // indigo
];

/**
 * Transform API response to match expected chart data structure
 */
function transformGraphData(apiData) {
    if (!apiData?.players) return apiData;

    // Assign colors to players
    const players = apiData.players.map((p, idx) => ({
        name: p.name,
        color: PLAYER_COLORS[idx % PLAYER_COLORS.length],
        // Flatten combat_offense
        kills: p.combat_offense?.kills || 0,
        deaths: p.combat_offense?.deaths || 0,
        damage_given: p.combat_offense?.damage_given || 0,
        kd: p.combat_offense?.kd || 0,
        dpm: p.combat_offense?.dpm || 0,
        // Flatten combat_defense
        revives: p.combat_defense?.revives || 0,
        gibs: p.combat_defense?.gibs || 0,
        headshots: p.combat_defense?.headshots || 0,
        times_revived: p.combat_defense?.times_revived || 0,
        team_kills: p.combat_defense?.team_kills || 0,
        // Flatten advanced_metrics (convert snake_case to camelCase)
        fragPotential: p.advanced_metrics?.frag_potential || 0,
        damageEfficiency: p.advanced_metrics?.damage_efficiency || 0,
        survivalRate: p.advanced_metrics?.survival_rate || 0,
        timeDenied: p.advanced_metrics?.time_denied || 0,
        // Keep playstyle as-is
        playstyle: p.playstyle || {},
        // Keep raw dpm_timeline for building combined timeline
        _dpmTimeline: p.dpm_timeline || []
    }));

    // Build combined DPM timeline (all players on same chart)
    // Collect all unique labels from all players
    const allLabels = new Set();
    players.forEach(p => {
        p._dpmTimeline.forEach(point => allLabels.add(point.label));
    });
    const labels = Array.from(allLabels);

    // Build datasets for timeline
    const datasets = players.map(p => {
        const dataMap = new Map(p._dpmTimeline.map(point => [point.label, point.dpm]));
        return {
            name: p.name,
            color: p.color,
            data: labels.map(label => dataMap.get(label) || null)
        };
    });

    return {
        ...apiData,
        players,
        dpmTimeline: { labels, datasets }
    };
}

/**
 * Load session graph data from API
 */
async function loadSessionGraphData(date) {
    try {
        const apiData = await fetchJSON(`${API_BASE}/sessions/${date}/graphs`);
        // Transform API data to match expected chart structure
        sessionGraphsData[date] = transformGraphData(apiData);
        renderSessionGraph(date, 'offense');
        renderPlayerLegend(date);
    } catch (e) {
        console.error('Failed to load session graphs:', e);
        const graphsEl = document.getElementById(`session-graphs-${date}`);
        if (graphsEl) {
            graphsEl.innerHTML = `
                <div class="text-center text-red-500 py-8">
                    Failed to load session graphs
                </div>
            `;
        }
    }
}

/**
 * Render player legend for graphs
 */
function renderPlayerLegend(date) {
    const legendEl = document.getElementById(`graph-legend-${date}`);
    const data = sessionGraphsData[date];
    
    if (!legendEl || !data?.players) return;
    
    legendEl.innerHTML = data.players.map(player => `
        <div class="flex items-center gap-2">
            <span class="w-3 h-3 rounded-full" style="background-color: ${player.color}"></span>
            <span class="text-sm text-slate-300">${escapeHtml(player.name)}</span>
        </div>
    `).join('');
}

/**
 * Switch between graph tabs
 */
function switchGraphTab(date, tab) {
    currentGraphTab = tab;
    updateGraphTabStyles(date, tab);
    renderSessionGraph(date, tab);
}

/**
 * Update graph tab button styles
 */
function updateGraphTabStyles(date, activeTab) {
    const container = document.getElementById(`session-graphs-${date}`)?.parentElement;
    if (!container) return;
    
    container.querySelectorAll('.graph-tab').forEach(btn => {
        const isActive = btn.dataset.tab === activeTab;
        btn.classList.toggle('bg-brand-blue', isActive);
        btn.classList.toggle('text-white', isActive);
        btn.classList.toggle('bg-white/5', !isActive);
        btn.classList.toggle('text-slate-400', !isActive);
        btn.classList.toggle('hover:bg-white/10', !isActive);
    });
}

/**
 * Render session graph based on active tab
 */
function renderSessionGraph(date, tab) {
    const data = sessionGraphsData[date];
    if (!data?.players) return;

    // Destroy existing chart
    if (sessionGraphCharts[date]) {
        sessionGraphCharts[date].destroy();
    }

    const canvas = document.getElementById(`session-graph-${date}`);
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const titleEl = document.getElementById(`graph-title-${date}`);
    
    // Chart configurations based on tab
    const chartConfigs = {
        offense: {
            icon: 'sword',
            title: 'Combat Stats (Offense)',
            type: 'bar',
            data: {
                labels: data.players.map(p => p.name),
                datasets: [
                    {
                        label: 'Kills',
                        data: data.players.map(p => p.kills),
                        backgroundColor: 'rgba(16, 185, 129, 0.8)',
                        borderWidth: 0,
                    },
                    {
                        label: 'Deaths',
                        data: data.players.map(p => p.deaths),
                        backgroundColor: 'rgba(244, 63, 94, 0.8)',
                        borderWidth: 0,
                    },
                    {
                        label: 'DPM',
                        data: data.players.map(p => p.dpm),
                        backgroundColor: 'rgba(88, 101, 242, 0.8)',
                        borderWidth: 0,
                    }
                ]
            },
            options: getBarChartOptions()
        },
        defense: {
            icon: 'shield',
            title: 'Combat Stats (Defense)',
            type: 'bar',
            data: {
                labels: data.players.map(p => p.name),
                datasets: [
                    {
                        label: 'Revives',
                        data: data.players.map(p => p.revives),
                        backgroundColor: 'rgba(16, 185, 129, 0.8)',
                        borderWidth: 0,
                    },
                    {
                        label: 'Gibs',
                        data: data.players.map(p => p.gibs),
                        backgroundColor: 'rgba(244, 63, 94, 0.8)',
                        borderWidth: 0,
                    },
                    {
                        label: 'Headshots',
                        data: data.players.map(p => p.headshots),
                        backgroundColor: 'rgba(251, 191, 36, 0.8)',
                        borderWidth: 0,
                    }
                ]
            },
            options: getBarChartOptions()
        },
        advanced: {
            icon: 'zap',
            title: 'Advanced Metrics',
            type: 'radar',
            data: {
                labels: ['Frag Potential', 'Damage Efficiency', 'Survival Rate', 'Time Denied'],
                datasets: data.players.map(p => ({
                    label: p.name,
                    data: [p.fragPotential, p.damageEfficiency, p.survivalRate, p.timeDenied],
                    borderColor: p.color,
                    backgroundColor: p.color + '33',
                    borderWidth: 2,
                    pointBackgroundColor: p.color,
                }))
            },
            options: getRadarChartOptions()
        },
        playstyle: {
            icon: 'target',
            title: 'Playstyle Analysis',
            type: 'bar',
            data: {
                labels: ['Aggression', 'Precision', 'Survivability', 'Support', 'Lethality', 'Brutality', 'Consistency', 'Efficiency'],
                datasets: data.players.map(p => ({
                    label: p.name,
                    data: [
                        p.playstyle.aggression,
                        p.playstyle.precision,
                        p.playstyle.survivability,
                        p.playstyle.support,
                        p.playstyle.lethality,
                        p.playstyle.brutality,
                        p.playstyle.consistency,
                        p.playstyle.efficiency
                    ],
                    backgroundColor: p.color + 'CC',
                    borderWidth: 0,
                }))
            },
            options: getHorizontalBarChartOptions()
        },
        timeline: {
            icon: 'trending-up',
            title: 'DPM Timeline',
            type: 'line',
            data: {
                labels: data.dpmTimeline?.labels || [],
                datasets: (data.dpmTimeline?.datasets || []).map(ds => ({
                    label: ds.name,
                    data: ds.data,
                    borderColor: ds.color,
                    backgroundColor: ds.color + '33',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.3,
                    pointRadius: 4,
                    pointBackgroundColor: ds.color,
                }))
            },
            options: getLineChartOptions()
        }
    };
    
    const config = chartConfigs[tab];
    if (!config) return;
    
    // Update title
    if (titleEl) {
        titleEl.innerHTML = `
            <i data-lucide="${config.icon}" class="w-5 h-5 text-brand-cyan"></i>
            <h3 class="text-lg font-bold text-white">${config.title}</h3>
        `;
        if (typeof lucide !== 'undefined') lucide.createIcons();
    }
    
    // Create chart
    sessionGraphCharts[date] = new Chart(ctx, {
        type: config.type,
        data: config.data,
        options: config.options
    });
}

/**
 * Chart options for bar charts
 */
function getBarChartOptions() {
    return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                position: 'top',
                labels: { color: '#94a3b8', font: { size: 11 } }
            }
        },
        scales: {
            x: {
                ticks: { color: '#94a3b8', font: { size: 10 } },
                grid: { color: 'rgba(255,255,255,0.05)' }
            },
            y: {
                ticks: { color: '#94a3b8' },
                grid: { color: 'rgba(255,255,255,0.05)' },
                beginAtZero: true
            }
        }
    };
}

/**
 * Chart options for horizontal bar charts (playstyle)
 */
function getHorizontalBarChartOptions() {
    return {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                position: 'bottom',
                labels: { color: '#94a3b8', font: { size: 11 } }
            }
        },
        scales: {
            x: {
                ticks: { color: '#94a3b8' },
                grid: { color: 'rgba(255,255,255,0.05)' },
                beginAtZero: true,
                max: 100
            },
            y: {
                ticks: { color: '#94a3b8', font: { size: 10 } },
                grid: { color: 'rgba(255,255,255,0.05)' }
            }
        }
    };
}

/**
 * Chart options for radar charts
 */
function getRadarChartOptions() {
    return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                position: 'top',
                labels: { color: '#94a3b8', font: { size: 11 } }
            }
        },
        scales: {
            r: {
                angleLines: { color: 'rgba(255,255,255,0.1)' },
                grid: { color: 'rgba(255,255,255,0.1)' },
                pointLabels: { color: '#94a3b8', font: { size: 11 } },
                ticks: { 
                    color: '#94a3b8',
                    backdropColor: 'transparent',
                    stepSize: 20
                },
                suggestedMin: 0,
                suggestedMax: 60
            }
        }
    };
}

/**
 * Chart options for line charts (timeline)
 */
function getLineChartOptions() {
    return {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
            mode: 'index',
            intersect: false,
        },
        plugins: {
            legend: {
                position: 'bottom',
                labels: { color: '#94a3b8', font: { size: 11 } }
            }
        },
        scales: {
            x: {
                ticks: { 
                    color: '#94a3b8', 
                    font: { size: 9 },
                    maxRotation: 45,
                    minRotation: 45
                },
                grid: { color: 'rgba(255,255,255,0.05)' }
            },
            y: {
                ticks: { color: '#94a3b8' },
                grid: { color: 'rgba(255,255,255,0.05)' },
                beginAtZero: true,
                title: {
                    display: true,
                    text: 'DPM',
                    color: '#94a3b8'
                }
            }
        }
    };
}

// Expose to window for onclick handlers in HTML
window.toggleSession = toggleSession;
window.loadMoreSessions = loadMoreSessions;
window.toggleSessionGraphs = toggleSessionGraphs;
window.switchGraphTab = switchGraphTab;
