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

/**
 * Load season info widget
 */
export async function loadSeasonInfo() {
    try {
        const season = await fetchJSON(`${API_BASE}/seasons/current`);
        const seasonEl = document.getElementById('current-season-display');
        if (seasonEl) seasonEl.textContent = season.name;
    } catch (e) {
        console.error('Failed to load season:', e);
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
            <div class="glass-card p-4 rounded-xl text-center">
                <div class="text-xs text-slate-500 uppercase font-bold">Duration</div>
                <div class="text-2xl font-black text-brand-cyan">${data.duration || 'N/A'}</div>
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
        if (ctxOutcome && data.matches) {
            const wins = data.matches.filter(m => m.winner === 'Allies').length;
            const losses = data.matches.filter(m => m.winner !== 'Allies').length;

            new Chart(ctxOutcome.getContext('2d'), {
                type: 'pie',
                data: {
                    labels: ['Victory', 'Defeat'],
                    datasets: [{
                        data: [wins, losses],
                        backgroundColor: [
                            'rgba(16, 185, 129, 0.8)', // Emerald
                            'rgba(244, 63, 94, 0.8)'   // Rose
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
    }, 100);

    // Load MVP widget
    loadSessionMVP();

    // 3. Render Match List (optional detailed list below charts)
    if (!data.matches || data.matches.length === 0) {
        return;
    }

    data.maps.forEach((mapData, idx) => {
        const safeMapName = escapeHtml(mapData.name || mapData);
        const mapHtml = `
            <div class="glass-card p-4 rounded-lg mb-3">
                <div class="font-bold text-white">${safeMapName}</div>
            </div>
        `;
        container.insertAdjacentHTML('beforeend', mapHtml);
    });
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

    // Map badges
    const mapBadges = session.maps_played.slice(0, 5).map(map => {
        const safeMap = escapeHtml(map.replace('etl_', '').replace('sw_', '').replace('_te', ''));
        return `<span class="px-2 py-0.5 rounded bg-slate-800 text-slate-400 text-xs">${safeMap}</span>`;
    }).join('');
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
                            <div class="text-sm text-slate-400">${safeTimeAgo}</div>
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
                            <div class="text-2xl font-black text-brand-rose">${session.total_kills.toLocaleString()}</div>
                            <div class="text-xs text-slate-500 uppercase">Kills</div>
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
                    ${mapBadges}
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
                     onclick="loadPlayerProfile('${jsName}')">>
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
            const safeMapName = escapeHtml(mapMatch.map_name.replace('etl_', '').replace('sw_', ''));
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
                        <i data-lucide="map" class="w-5 h-5 text-brand-cyan"></i>
                        <span class="font-bold text-white">${safeMapName}</span>
                        <span class="text-xs text-slate-500">${mapMatch.rounds.length} rounds</span>
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
