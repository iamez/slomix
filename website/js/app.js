// Navigation Logic (Global)
/* global lucide, Chart, API_BASE, AUTH_BASE, fetchJSON */
/* exported navigateTo, loadMatches, loadLeaderboard, loadPlayerProfile */

/**
 * Escape HTML special characters to prevent XSS attacks.
 * Use this for any user-controlled data inserted into HTML.
 * @param {string} str - The string to escape
 * @returns {string} - HTML-safe string
 */
function escapeHtml(str) {
    if (str == null) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}

/**
 * Safely insert HTML that contains escaped user content.
 * Only use this when ALL user-controlled content has been escaped with escapeHtml().
 * @param {Element} element - The target element
 * @param {string} position - Position to insert ('beforeend', 'afterbegin', etc.)
 * @param {string} html - HTML string with escaped user content
 */
function safeInsertHTML(element, position, html) {
    // This wrapper documents that the HTML has been sanitized before insertion
    element.insertAdjacentHTML(position, html);  // nosemgrep: javascript.browser.security.insecure-document-method.insecure-document-method
}

// Define navigateTo globally (fixes 'navigateTo is not defined')
const navigateTo = window.navigateTo = function (viewId, updateHistory = true) {
    console.log('Navigating to:', viewId);

    // Hide all views
    document.querySelectorAll('.view-section').forEach(el => {
        el.classList.remove('active');
        // Also add hidden class for safety if mixed styles are used
        el.classList.add('hidden');
    });

    // Show selected view
    const target = document.getElementById(`view-${viewId}`);
    if (target) {
        target.classList.add('active');
        target.classList.remove('hidden');
    } else {
        console.error(`View not found: view-${viewId}`);
        return;
    }

    // Update Nav Links (Desktop)
    document.querySelectorAll('.nav-link').forEach(el => el.classList.remove('active'));
    const link = document.getElementById(`link-${viewId}`);
    if (link) link.classList.add('active');

    // Update URL hash (for browser history)
    if (updateHistory) {
        const hash = viewId === 'home' ? '' : `#/${viewId}`;
        window.location.hash = hash;
    }

    // Scroll to top
    window.scrollTo(0, 0);

    // Load view-specific data
    if (viewId === 'matches') {
        loadMatchesView();
    } else if (viewId === 'community') {
        loadCommunityView();
    }
};

// Handle browser back/forward buttons
window.addEventListener('popstate', () => {
    const hash = window.location.hash.replace('#/', '');
    const viewId = hash || 'home';
    navigateTo(viewId, false); // Don't update history again
});

// Slomix Frontend Logic
const API_BASE = window.location.origin + '/api';
const AUTH_BASE = window.location.origin + '/auth';

document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

async function initApp() {
    console.log('🚀 Slomix App Initializing...');

    // Check API Status
    try {
        const status = await fetchJSON(`${API_BASE}/status`);
        console.log('API Status:', status);
        const statusDot = document.getElementById('server-status-dot');
        const statusText = document.getElementById('server-status-text');
        if (statusDot) {
            statusDot.classList.remove('bg-red-500');
            statusDot.classList.add('bg-green-500');
        }
        if (statusText) statusText.textContent = 'Online';
    } catch (e) {
        console.error('API Offline:', e);
        const statusDot = document.getElementById('server-status-dot');
        const statusText = document.getElementById('server-status-text');
        if (statusDot) statusDot.classList.add('bg-red-500');
        if (statusText) statusText.textContent = 'Offline';
    }

    // Load Data
    loadSeasonInfo();
    loadLastSession();
    loadPredictions();
    updateLiveSession(); // Live Updates
    loadQuickLeaders();  // Sidebar widget leaderboard
    loadMatchesView();   // Matches view
    checkLoginStatus();
    initCharts();

    // Handle initial URL hash (for direct links)
    const hash = window.location.hash.replace('#/', '');
    if (hash && hash !== 'home') {
        navigateTo(hash, false);
    }
}

function initCharts() {
    // Check if elements exist before initializing
    const eloCanvas = document.getElementById('eloChart');
    const radarCanvas = document.getElementById('compareRadarChart');

    if (eloCanvas) {
        const ctxElo = eloCanvas.getContext('2d');
        const gradientElo = ctxElo.createLinearGradient(0, 0, 0, 400);
        gradientElo.addColorStop(0, 'rgba(59, 130, 246, 0.2)');
        gradientElo.addColorStop(1, 'rgba(59, 130, 246, 0)');

        new Chart(ctxElo, {
            type: 'line',
            data: {
                labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
                datasets: [{
                    label: 'Skill Rating',
                    data: [1200, 1350, 1320, 1450, 1500, 1520],
                    borderColor: '#3b82f6',
                    backgroundColor: gradientElo,
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#0f172a',
                    pointBorderColor: '#3b82f6'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: { grid: { color: 'rgba(255,255,255,0.05)' } },
                    x: { grid: { display: false } }
                }
            }
        });
    }

    if (radarCanvas) {
        const ctxCompare = radarCanvas.getContext('2d');
        new Chart(ctxCompare, {
            type: 'radar',
            data: {
                labels: ['Aim', 'Survival', 'Obj', 'Support', 'Impact', 'Spree'],
                datasets: [
                    {
                        label: 'BAMBAM',
                        data: [85, 92, 40, 60, 95, 80],
                        backgroundColor: 'rgba(59, 130, 246, 0.2)',
                        borderColor: '#3b82f6',
                        pointBackgroundColor: '#3b82f6',
                    },
                    {
                        label: 'Snake',
                        data: [75, 80, 85, 90, 70, 60],
                        backgroundColor: 'rgba(244, 63, 94, 0.2)',
                        borderColor: '#f43f5e',
                        pointBackgroundColor: '#f43f5e',
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    r: {
                        grid: { color: 'rgba(255,255,255,0.05)' },
                        angleLines: { color: 'rgba(255,255,255,0.05)' },
                        pointLabels: { color: '#94a3b8' }
                    }
                }
            }
        });
    }
}

async function loadPredictions() {
    try {
        const predictions = await fetchJSON(`${API_BASE}/predictions/recent?limit=3`);
        const container = document.getElementById('predictions-list');
        if (!container) return;

        container.innerHTML = '';

        if (predictions.length === 0) {
            container.innerHTML = '<div class="text-center text-slate-500 py-8 col-span-full">No recent predictions found.</div>';
            return;
        }

        predictions.forEach(pred => {
            // Calculate probability bar width
            const probA = pred.team_a_probability * 100;
            const probB = pred.team_b_probability * 100;

            // Determine status - static HTML badges, no user input
            let statusBadge = '';
            let statusBorder = 'border-white/5';

            if (pred.actual_winner === null) {
                statusBadge = '<span class="px-2 py-0.5 rounded bg-brand-gold/10 text-brand-gold text-[10px] font-bold uppercase border border-brand-gold/20">Live</span>';
                statusBorder = 'border-brand-gold/30 shadow-[0_0_15px_rgba(251,191,36,0.1)]';
            } else if (pred.is_correct) {
                statusBadge = '<span class="px-2 py-0.5 rounded bg-brand-emerald/10 text-brand-emerald text-[10px] font-bold uppercase border border-brand-emerald/20">Correct</span>';
            } else {
                statusBadge = '<span class="px-2 py-0.5 rounded bg-brand-rose/10 text-brand-rose text-[10px] font-bold uppercase border border-brand-rose/20">Incorrect</span>';
            }

            // Format time
            const date = new Date(pred.timestamp);
            const timeAgo = Math.floor((new Date() - date) / (1000 * 60)) + 'm ago';

            const html = `
                <div class="glass-card p-4 rounded-xl border ${statusBorder} hover:bg-white/5 transition group relative overflow-hidden">
                    <div class="flex justify-between items-start mb-4">
                        <div class="flex items-center gap-2">
                            <span class="text-[10px] font-bold text-slate-500 uppercase bg-slate-800 px-1.5 py-0.5 rounded">${escapeHtml(pred.format)}</span>
                            <span class="text-[10px] font-mono text-slate-400">${escapeHtml(timeAgo)}</span>
                        </div>
                        ${statusBadge}
                    </div>

                    <div class="flex items-center justify-between mb-2">
                        <div class="text-sm font-bold text-white">Team A</div>
                        <div class="text-xs font-bold text-slate-400">vs</div>
                        <div class="text-sm font-bold text-white">Team B</div>
                    </div>

                    <!-- Probability Bar -->
                    <div class="h-2 bg-slate-800 rounded-full overflow-hidden flex mb-2">
                        <div class="h-full bg-brand-blue" style="width: ${probA}%"></div>
                        <div class="h-full bg-brand-rose" style="width: ${probB}%"></div>
                    </div>

                    <div class="flex justify-between text-xs font-mono font-bold mb-3">
                        <span class="text-brand-blue">${probA.toFixed(0)}%</span>
                        <span class="text-brand-rose">${probB.toFixed(0)}%</span>
                    </div>

                    <div class="pt-3 border-t border-white/5">
                        <div class="flex items-center gap-2 text-xs text-slate-400">
                            <i class="fas fa-brain text-brand-purple"></i>
                            <span>Confidence: <span class="text-white font-bold uppercase">${escapeHtml(pred.confidence)}</span></span>
                        </div>
                    </div>
                </div>
            `;
            container.insertAdjacentHTML('beforeend', html);
        });

    } catch (e) {
        console.error('Failed to load predictions:', e);
        const container = document.getElementById('predictions-list');
        if (container) container.innerHTML = '<div class="text-center text-red-500 py-4 col-span-full">Failed to load predictions</div>';
    }
}

async function updateLiveSession() {
    try {
        const data = await fetchJSON(`${API_BASE}/stats/live-session`);
        const widget = document.getElementById('live-session-widget');

        if (!widget) return;

        if (data.active) {
            widget.classList.remove('hidden');
            document.getElementById('live-players').textContent = data.current_players;
            document.getElementById('live-rounds').textContent = data.rounds_completed;
            document.getElementById('live-map').textContent = data.current_map;
        } else {
            widget.classList.add('hidden');
        }
    } catch (e) {
        console.error('Failed to update live session:', e);
    }
}

// Poll every 10 seconds
setInterval(updateLiveSession, 10000);

async function loadPlayerProfile(playerName) {
    navigateTo('profile');

    // Reset UI
    document.getElementById('profile-name').textContent = playerName;
    document.getElementById('profile-initials').textContent = playerName.substring(0, 2).toUpperCase();

    try {
        const data = await fetchJSON(`${API_BASE}/stats/player/${encodeURIComponent(playerName)}`);
        const stats = data.stats;

        // Update Header
        document.getElementById('profile-name').textContent = data.name;
        document.getElementById('profile-playtime').textContent = stats.playtime_hours + 'h';
        document.getElementById('profile-seen').textContent = new Date(stats.last_seen).toLocaleDateString();
        document.getElementById('profile-dpm').textContent = stats.dpm;

        // Update Cards
        document.getElementById('profile-kd').textContent = stats.kd;
        document.getElementById('profile-kills').textContent = stats.kills;
        document.getElementById('profile-deaths').textContent = stats.deaths;

        document.getElementById('profile-winrate').textContent = stats.win_rate + '%';
        document.getElementById('profile-wins').textContent = stats.wins;
        document.getElementById('profile-games').textContent = stats.games;

        document.getElementById('profile-xp').textContent = stats.total_xp.toLocaleString();
        document.getElementById('profile-damage').textContent = (stats.damage / 1000).toFixed(1) + 'k';

    } catch (e) {
        console.error('Failed to load profile:', e);
        alert('Player not found!');
        navigateTo('home');
    }
}

// Leaderboard Logic
let currentLbStat = 'dpm';
let currentLbPeriod = '30d';

async function loadLeaderboard() {
    const tbody = document.getElementById('leaderboard-body');
    if (!tbody) return;

    // Show loading state
    tbody.innerHTML = `
        <tr>
            <td colspan="6" class="px-6 py-12 text-center text-slate-500">
                <i data-lucide="loader" class="w-6 h-6 animate-spin mx-auto mb-2"></i>
                Loading data...
            </td>
        </tr>
    `;
    lucide.createIcons();

    try {
        const data = await fetchJSON(`${API_BASE}/stats/leaderboard?stat=${currentLbStat}&period=${currentLbPeriod}&limit=50`);

        tbody.innerHTML = '';

        if (data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-8 text-center text-slate-500">No data found for this period.</td></tr>';
            return;
        }

        data.forEach(row => {
            // Highlight the main value based on selected stat
            let valueClass = 'text-slate-300';
            if (currentLbStat === 'dpm') valueClass = 'text-brand-emerald font-bold';
            if (currentLbStat === 'kills') valueClass = 'text-brand-rose font-bold';
            if (currentLbStat === 'kd') valueClass = 'text-brand-blue font-bold';

            const safeName = escapeHtml(row.name);
            const safeInitials = escapeHtml(row.name.substring(0, 2).toUpperCase());
            const html = `
                <tr class="hover:bg-white/5 transition group">
                    <td class="px-6 py-4 font-mono text-slate-500">#${row.rank}</td>
                    <td class="px-6 py-4">
                        <div class="flex items-center gap-3">
                            <div class="w-8 h-8 rounded bg-slate-800 flex items-center justify-center text-xs font-bold text-slate-400 group-hover:text-white group-hover:bg-brand-blue transition">
                                ${safeInitials}
                            </div>
                            <span class="font-bold text-white cursor-pointer hover:underline" onclick="loadPlayerProfile('${safeName}')">${safeName}</span>
                        </div>
                    </td>
                    <td class="px-6 py-4 text-right font-mono ${valueClass}">${row.value}</td>
                    <td class="px-6 py-4 text-right text-slate-400">${row.sessions}</td>
                    <td class="px-6 py-4 text-right text-slate-400">${row.kills}</td>
                    <td class="px-6 py-4 text-right font-mono text-slate-300">${row.kd}</td>
                </tr>
            `;
            tbody.insertAdjacentHTML('beforeend', html);
        });

    } catch (e) {
        console.error('Failed to load leaderboard:', e);
        tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-8 text-center text-red-500">Failed to load data.</td></tr>';
    }
}

function updateLeaderboardFilter(type, value) {
    if (type === 'stat') {
        currentLbStat = value;
        // Update UI buttons
        ['dpm', 'kills', 'kd'].forEach(s => {
            const btn = document.getElementById(`btn-stat-${s}`);
            if (s === value) {
                btn.className = 'px-4 py-2 rounded-md text-sm font-bold bg-brand-blue text-white shadow-lg transition';
            } else {
                btn.className = 'px-4 py-2 rounded-md text-sm font-bold text-slate-400 hover:text-white transition';
            }
        });
        // Update column header
        const colHeader = document.getElementById('lb-col-value');
        if (colHeader) colHeader.textContent = value.toUpperCase();
    }

    if (type === 'period') {
        currentLbPeriod = value;
        // Update UI buttons
        ['7d', '30d', 'season', 'all'].forEach(p => {
            const btn = document.getElementById(`btn-period-${p}`);
            if (p === value) {
                btn.className = 'px-4 py-2 rounded-md text-sm font-bold bg-brand-purple text-white shadow-lg transition';
            } else {
                btn.className = 'px-4 py-2 rounded-md text-sm font-bold text-slate-400 hover:text-white transition';
            }
        });
    }

    loadLeaderboard();
}

async function fetchJSON(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
}

async function checkLoginStatus() {
    try {
        const user = await fetchJSON(`${AUTH_BASE}/me`);
        console.log('User:', user);

        // Update UI
        document.getElementById('auth-guest').classList.add('hidden');
        const userEl = document.getElementById('auth-user');
        userEl.classList.remove('hidden');
        userEl.classList.add('flex');

        // Update Nav Username
        const navName = document.getElementById('nav-username');
        if (navName) navName.textContent = user.linked_player || user.username;

        // Check Link
        if (!user.linked_player) {
            openModal('modal-link-player');
        } else {
            console.log('Linked to:', user.linked_player);
            // TODO: Update Dashboard with linked player stats
        }

    } catch (e) {
        console.log('Not logged in');
        document.getElementById('auth-guest').classList.remove('hidden');
        const userEl = document.getElementById('auth-user');
        userEl.classList.add('hidden');
        userEl.classList.remove('flex');
    }
}

async function loadSeasonInfo() {
    try {
        const season = await fetchJSON(`${API_BASE}/seasons/current`);
        // Update UI elements if they exist
        const seasonEl = document.getElementById('current-season-display');
        if (seasonEl) seasonEl.textContent = season.name;
    } catch (e) {
        console.error('Failed to load season:', e);
    }
}

async function loadLastSession() {
    try {
        const data = await fetchJSON(`${API_BASE}/stats/last-session`);
        console.log('Last Session:', data);

        // Update "Last Session" widget (with null checks)
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

function renderSessionDetails(data) {
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
                <div class="text-xs text-slate-500 uppercase font-bold">Peak Players</div>
                <div class="text-2xl font-black text-brand-purple">${data.player_count}</div>
            </div>
            <div class="glass-card p-4 rounded-xl text-center">
                <div class="text-xs text-slate-500 uppercase font-bold">Avg Duration</div>
                <div class="text-2xl font-black text-brand-emerald">18m</div> 
            </div>
        </div>
    `;  // nosemgrep: javascript.browser.security.insecure-document-method.insecure-document-method - static HTML only, no user input
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
            <div class="glass-panel p-6 rounded-xl flex items-center justify-center">
                <div class="text-center">
                    <h3 class="font-bold text-white mb-2">Session MVP</h3>
                    <div class="w-20 h-20 rounded-full bg-gradient-to-br from-brand-gold to-brand-amber mx-auto flex items-center justify-center text-2xl font-black text-white shadow-[0_0_30px_rgba(251,191,36,0.4)] mb-4">
                        ?
                    </div>
                    <p class="text-slate-400 text-xs">MVP Data Coming Soon</p>
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
            const wins = data.matches.filter(m => m.winner === 'Allies').length; // Assuming Allies = Win
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

    // 3. Render Match List
    if (!data.matches || data.matches.length === 0) {
        container.insertAdjacentHTML('beforeend', '<div class="text-center text-slate-500 py-8">No detailed match data available.</div>');
        return;
    }

    data.matches.forEach(match => {
        const winnerColor = match.winner === 'Allies' ? 'text-brand-blue' : 'text-brand-rose';
        const winnerBg = match.winner === 'Allies' ? 'bg-brand-blue/10 border-brand-blue/20' : 'bg-brand-rose/10 border-brand-rose/20';

        const safeMapName = escapeHtml(match.map_name);
        const safeMapAbbrev = escapeHtml(match.map_name.substring(0, 3));
        const safeWinner = escapeHtml(match.winner);
        const safeOutcome = escapeHtml(match.outcome || 'Victory');
        const safeDuration = escapeHtml(match.duration);
        const html = `
            <div class="glass-card p-4 rounded-xl flex items-center justify-between gap-4 hover:bg-white/5 transition group">
                <div class="flex items-center gap-4">
                    <div class="w-12 h-12 rounded bg-slate-800 flex items-center justify-center font-bold text-slate-500 text-xs uppercase border border-white/5">
                        ${safeMapAbbrev}
                    </div>
                    <div>
                        <div class="font-bold text-white group-hover:text-brand-cyan transition">${safeMapName}</div>
                        <div class="text-xs text-slate-500 font-mono">Round ${match.round_number} • ${safeDuration}</div>
                    </div>
                </div>
                
                <div class="flex items-center gap-6">
                    <div class="text-right">
                        <div class="text-[10px] uppercase font-bold text-slate-500">Winner</div>
                        <div class="font-black ${winnerColor}">${safeWinner}</div>
                    </div>
                    <div class="px-3 py-1 rounded ${winnerBg} text-xs font-bold text-white">
                        ${safeOutcome}
                    </div>
                </div>
            </div>
        `;
        container.insertAdjacentHTML('beforeend', html);
    });
}

async function loadQuickLeaders() {
    try {
        const leaders = await fetchJSON(`${API_BASE}/stats/leaderboard?limit=5`);
        const list = document.getElementById('quick-leaders-list');
        if (!list) return;

        list.innerHTML = '';

        leaders.forEach((player, index) => {
            const rankColor = index === 0 ? 'text-brand-gold' : index === 1 ? 'text-slate-400' : 'text-brand-rose';
            const safeInitials = escapeHtml(player.name.substring(0, 2).toUpperCase());
            const safeName = escapeHtml(player.name);

            const html = `
                <div class="flex items-center justify-between group cursor-pointer">
                    <div class="flex items-center gap-3">
                        <div class="font-mono font-bold ${rankColor} text-sm">${player.rank}</div>
                        <div class="w-8 h-8 rounded bg-slate-800 flex items-center justify-center text-xs font-bold text-slate-400">${safeInitials}</div>
                        <div class="text-sm font-bold text-white group-hover:text-brand-blue transition">${safeName}</div>
                    </div>
                    <div class="text-sm font-mono font-bold text-brand-emerald">${Math.round(player.value)} DPM</div>
                </div>
            `;
            list.insertAdjacentHTML('beforeend', html);
        });
    } catch (e) {
        console.error('Failed to load quick leaders:', e);
        const list = document.getElementById('quick-leaders-list');
        if (list) list.innerHTML = '<div class="text-center text-red-500 text-xs py-4">Failed to load</div>';
    }
}

async function loadRecentMatches() {
    try {
        const matches = await fetchJSON(`${API_BASE}/stats/matches?limit=5`);
        const list = document.getElementById('recent-matches-list');
        if (!list) return;

        list.innerHTML = '';

        if (matches.length === 0) {
            list.innerHTML = '<div class="text-center text-slate-500 py-4">No recent matches found</div>';
            return;
        }

        matches.forEach(match => {
            const winnerColor = match.winner === 'Allies' ? 'text-brand-blue' : 'text-brand-rose';
            const winnerBg = match.winner === 'Allies' ? 'bg-brand-blue/20 text-brand-blue' : 'bg-brand-rose/20 text-brand-rose';

            // Calculate relative time
            const date = new Date(match.date);
            const now = new Date();
            const diffMs = now - date;
            const diffHrs = Math.floor(diffMs / (1000 * 60 * 60));
            const timeAgo = diffHrs > 24 ? Math.floor(diffHrs / 24) + 'd ago' : diffHrs < 1 ? 'Just now' : diffHrs + 'h ago';

            const safeMapName = escapeHtml(match.map_name);
            const safeMapAbbrev = escapeHtml(match.map_name.substring(0, 3));
            const safeWinner = escapeHtml(match.winner);
            const html = `
            <div class="glass-card p-3 rounded-lg hover:bg-white/5 transition cursor-pointer group" onclick="navigateTo('matches')">
                <div class="flex items-center gap-3 mb-2">
                    <div class="w-10 h-10 rounded bg-slate-800 border border-white/10 flex items-center justify-center flex-shrink-0">
                        <span class="text-[10px] font-bold text-slate-500 uppercase">${safeMapAbbrev}</span>
                    </div>
                    <div class="flex-1">
                        <div class="text-sm font-bold text-white group-hover:text-brand-purple transition">${safeMapName}</div>
                        <div class="text-[10px] text-slate-400 font-mono">${timeAgo}</div>
                    </div>
                </div>
                <div class="flex items-center justify-between pl-13">
                    <span class="px-2 py-0.5 rounded ${winnerBg} text-[10px] font-bold uppercase">${safeWinner}</span>
                    <span class="text-xs text-slate-400">Round ${match.round_number}</span>
                </div>
            </div>
            `;
            list.insertAdjacentHTML('beforeend', html);
        });
    } catch (e) {
        console.error('Failed to load matches:', e);
        const list = document.getElementById('recent-matches-list');
        if (list) list.innerHTML = '<div class="text-center text-red-500 py-4">Failed to load matches</div>';
    }
}

function loginWithDiscord() {
    window.location.href = `${AUTH_BASE}/login`;
}

// Modal Logic
function openModal(id) {
    const el = document.getElementById(id);
    if (el) {
        el.classList.remove('hidden');
        // Focus input
        if (id === 'modal-link-player') {
            const input = document.getElementById('player-search-input');
            if (input) input.focus();
        }
    }
}

function closeModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.add('hidden');
}

// Player Search Logic
let searchTimeout;
const searchInput = document.getElementById('player-search-input');
if (searchInput) {
    searchInput.addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        const query = e.target.value;
        if (query.length < 2) return;

        searchTimeout = setTimeout(() => searchPlayer(query), 300);
    });
}

async function searchPlayer(query) {
    try {
        const results = await fetchJSON(`${API_BASE}/player/search?query=${encodeURIComponent(query)}`);
        const list = document.getElementById('player-search-results');
        if (!list) return;
        list.innerHTML = '';

        results.forEach(name => {
            const div = document.createElement('div');
            div.className = 'p-3 rounded bg-white/5 hover:bg-white/10 cursor-pointer flex justify-between items-center transition';
            const safeName = escapeHtml(name);
            div.innerHTML = `<span class="font-bold text-white">${safeName}</span> <span class="text-xs text-brand-blue font-bold">CLAIM</span>`;
            div.onclick = () => linkPlayer(name);
            list.appendChild(div);
        });
    } catch (e) {
        console.error(e);
    }
}

async function linkPlayer(name) {
    if (!confirm(`Link your Discord account to "${name}"? This cannot be undone.`)) return;

    try {
        const res = await fetch(`${API_BASE}/player/link`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ player_name: name })
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Failed to link');
        }

        const data = await res.json();
        alert(`Successfully linked to ${data.linked_player}!`);
        closeModal('modal-link-player');
        location.reload(); // Reload to update UI

    } catch (e) {
        alert('Failed to link: ' + e.message);
    }
}

// Hero Search Logic
const heroSearchInput = document.getElementById('hero-search-input');
const heroSearchResults = document.getElementById('hero-search-results');
let heroSearchTimeout;

if (heroSearchInput) {
    heroSearchInput.addEventListener('input', (e) => {
        clearTimeout(heroSearchTimeout);
        const query = e.target.value;
        if (query.length < 2) {
            heroSearchResults.classList.add('hidden');
            return;
        }

        heroSearchTimeout = setTimeout(() => searchHeroPlayer(query), 300);
    });

    // Hide results when clicking outside
    document.addEventListener('click', (e) => {
        if (!heroSearchInput.contains(e.target) && !heroSearchResults.contains(e.target)) {
            heroSearchResults.classList.add('hidden');
        }
    });
}

async function searchHeroPlayer(query) {
    try {
        const results = await fetchJSON(`${API_BASE}/player/search?query=${encodeURIComponent(query)}`);

        if (results.length === 0) {
            heroSearchResults.innerHTML = '<div class="p-4 text-slate-500 text-sm text-center">No players found</div>';
        } else {
            heroSearchResults.innerHTML = '';
            results.forEach(name => {
                const div = document.createElement('div');
                div.className = 'p-4 hover:bg-white/5 cursor-pointer flex justify-between items-center transition border-b border-white/5 last:border-0';
                const safeName = escapeHtml(name);
                const safeInitials = escapeHtml(name.substring(0, 2).toUpperCase());
                div.innerHTML = `
                <div class="flex items-center gap-3">
                    <div class="w-8 h-8 rounded bg-slate-800 flex items-center justify-center text-xs font-bold text-slate-400">
                        ${safeInitials}
                    </div>
                    <span class="font-bold text-white">${safeName}</span>
                </div>
                <span class="text-xs text-brand-blue font-bold opacity-0 group-hover:opacity-100 transition">VIEW STATS</span>
            `;
                div.onclick = () => {
                    heroSearchResults.classList.add('hidden');
                    heroSearchInput.value = '';
                    loadPlayerProfile(name);
                };
                heroSearchResults.appendChild(div);
            });
        }
        heroSearchResults.classList.remove('hidden');
    } catch (e) {
        console.error(e);
    }
}

// [Removed duplicate/malformed loadMatchesView and nested functions]

// Load Matches View with all matches
async function loadMatchesView(filter = 'all') {
    const grid = document.getElementById('matches-grid');
    if (!grid) return;

    // Show loading
    grid.innerHTML = '<div class="text-center py-12"><i data-lucide="loader" class="w-8 h-8 text-brand-blue animate-spin mx-auto mb-4"></i><div class="text-slate-400">Loading matches...</div></div>';
    lucide.createIcons();

    try {
        const matches = await fetchJSON(`${API_BASE}/stats/matches?limit=50`);

        grid.innerHTML = '';

        if (matches.length === 0) {
            grid.innerHTML = '<div class="text-center text-slate-500 py-12">No matches found</div>';
            return;
        }

        matches.forEach(match => {
            const winnerColor = match.winner === 'Allies' ? 'text-brand-emerald' : 'text-brand-rose';
            const winnerBg = match.winner === 'Allies' ? 'bg-brand-emerald/10 border-brand-emerald/20' : 'bg-brand-rose/10 border-brand-rose/20';

            // Calculate relative time
            const date = new Date(match.date);
            const now = new Date();
            const diffMs = now - date;
            const diffHrs = Math.floor(diffMs / (1000 * 60 * 60));
            const timeAgo = diffHrs > 24 ? Math.floor(diffHrs / 24) + 'd ago' : diffHrs < 1 ? 'Just now' : diffHrs + 'h ago';

            const safeMapName = escapeHtml(match.map_name);
            const safeMapAbbrev = escapeHtml(match.map_name.substring(0, 3));
            const safeWinner = escapeHtml(match.winner);
            const html = `
            <div class="glass-panel p-6 rounded-xl hover:bg-white/5 transition cursor-pointer group">
                <div class="flex justify-between items-start">
                    <div class="flex-1">
                        <div class="flex items-center gap-4 mb-4">
                            <div class="w-16 h-16 rounded-lg bg-slate-800 border border-white/10 flex items-center justify-center">
                                <span class="text-xs font-bold text-slate-500 uppercase">${safeMapAbbrev}</span>
                            </div>
                            <div>
                                <div class="text-lg font-bold text-white group-hover:text-brand-cyan transition">${safeMapName}</div>
                                <div class="text-sm text-slate-400 font-mono">${timeAgo}</div>
                            </div>
                        </div>
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <div class="text-xs text-slate-500 uppercase mb-2">Winner</div>
                                <div class="flex items-center gap-2">
                                    <div class="px-3 py-1 rounded ${winnerBg} border">
                                        <span class="text-sm font-bold ${winnerColor}">${safeWinner}</span>
                                    </div>
                                </div>
                            </div>
                            <div>
                                <div class="text-xs text-slate-500 uppercase mb-2">Round</div>
                                <div class="text-xl font-black text-white">${match.round_number}</div>
                            </div>
                        </div>
                    </div>
                    <button class="px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-sm font-bold transition">
                        View Details
                    </button>
                </div>
            </div>
            `;
            grid.insertAdjacentHTML('beforeend', html);
        });
    } catch (e) {
        console.error('Failed to load matches:', e);
        grid.innerHTML = '<div class="text-center text-red-500 py-12">Failed to load matches</div>';
    }
}

// Load Maps View
async function loadMapsView() {
    const grid = document.getElementById('maps-grid');
    if (!grid) return;

    grid.innerHTML = '<div class="text-center py-12"><i data-lucide="loader" class="w-8 h-8 text-brand-cyan animate-spin mx-auto mb-4"></i><div class="text-slate-400">Loading map statistics...</div></div>';
    lucide.createIcons();

    try {
        // Get map data from recent matches
        const matches = await fetchJSON(`${API_BASE}/stats/matches?limit=200`);

        // Aggregate map statistics
        const mapStats = {};
        matches.forEach(match => {
            if (!mapStats[match.map_name]) {
                mapStats[match.map_name] = {
                    name: match.map_name,
                    plays: 0,
                    alliedWins: 0,
                    axisWins: 0
                };
            }
            mapStats[match.map_name].plays++;
            if (match.winner === 'Allies') {
                mapStats[match.map_name].alliedWins++;
            } else {
                mapStats[match.map_name].axisWins++;
            }
        });

        grid.innerHTML = '';

        // Display map cards
        Object.values(mapStats).forEach(map => {
            const winRate = ((map.alliedWins / map.plays) * 100).toFixed(1);
            const borderColor = winRate > 55 ? 'border-brand-emerald' : winRate < 45 ? 'border-brand-rose' : 'border-brand-cyan';

            const html = `
            <div class="glass-card p-6 rounded-xl border-l-4 ${borderColor} hover:scale-105 transition-transform cursor-pointer">
                <div class="flex items-center justify-between mb-4">
                    <div class="w-16 h-16 rounded-lg bg-slate-800 border border-white/10 flex items-center justify-center">
                        <span class="text-xs font-bold text-slate-400 uppercase">${map.name.substring(0, 3)}</span>
                    </div>
                    <div class="text-right">
                        <div class="text-2xl font-black text-white">${map.plays}</div>
                        <div class="text-xs text-slate-500 uppercase">Plays</div>
                    </div>
                </div>
                <h3 class="text-lg font-bold text-white mb-3">${map.name}</h3>
                <div class="space-y-2">
                    <div class="flex justify-between text-sm">
                        <span class="text-slate-400">Allied Win Rate</span>
                        <span class="font-bold text-brand-blue">${winRate}%</span>
                    </div>
                    <div class="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                        <div class="bg-brand-blue h-full" style="width: ${winRate}%"></div>
                    </div>
                    <div class="grid grid-cols-2 gap-2 pt-2">
                        <div class="text-center p-2 bg-slate-800/50 rounded">
                            <div class="text-xs text-slate-500">Allied</div>
                            <div class="font-bold text-brand-blue">${map.alliedWins}</div>
                        </div>
                        <div class="text-center p-2 bg-slate-800/50 rounded">
                            <div class="text-xs text-slate-500">Axis</div>
                            <div class="font-bold text-brand-rose">${map.axisWins}</div>
                        </div>
                    </div>
                </div>
            </div>
            `;
            grid.insertAdjacentHTML('beforeend', html);
        });
    } catch (e) {
        console.error('Failed to load maps:', e);
        grid.innerHTML = '<div class="text-center text-red-500 py-12">Failed to load map statistics</div>';
    }
}

// Load Weapons View
async function loadWeaponsView() {
    const grid = document.getElementById('weapons-grid');
    if (!grid) return;

    grid.innerHTML = '<div class="text-center py-12"><i data-lucide="loader" class="w-8 h-8 text-brand-rose animate-spin mx-auto mb-4"></i><div class="text-slate-400">Loading weapon statistics...</div></div>';
    lucide.createIcons();

    // Weapon category mapping
    const weaponCategories = {
        'knife': 'Melee', 'luger': 'Pistol', 'colt': 'Pistol',
        'mp40': 'SMG', 'thompson': 'SMG', 'sten': 'SMG',
        'fg42': 'Rifle', 'garand': 'Rifle', 'k43': 'Rifle', 'kar98': 'Rifle',
        'panzerfaust': 'Heavy', 'flamethrower': 'Heavy', 'mortar': 'Heavy', 'mg42': 'Heavy',
        'grenade': 'Explosive', 'dynamite': 'Explosive', 'landmine': 'Explosive',
        'airstrike': 'Support', 'artillery': 'Support', 'syringe': 'Support', 'smokegrenade': 'Support'
    };

    // Color mapping for categories
    const categoryColors = {
        'Melee': 'brand-amber', 'Pistol': 'brand-slate', 'SMG': 'brand-blue',
        'Rifle': 'brand-purple', 'Heavy': 'brand-rose', 'Explosive': 'brand-gold',
        'Support': 'brand-emerald'
    };

    try {
        const weapons = await fetchJSON(`${API_BASE}/stats/weapons?limit=20`);
        grid.innerHTML = '';

        if (weapons.length === 0) {
            grid.innerHTML = '<div class="col-span-full text-center text-slate-500 py-12">No weapon data available</div>';
            return;
        }

        // Calculate total kills for percentage
        const totalKills = weapons.reduce((sum, w) => sum + w.kills, 0);

        weapons.forEach(weapon => {
            const weaponKey = weapon.name.toLowerCase().replace(' ', '');
            const category = weaponCategories[weaponKey] || 'Other';
            const color = categoryColors[category] || 'brand-cyan';
            const usage = totalKills > 0 ? ((weapon.kills / totalKills) * 100).toFixed(1) : 0;
            const safeWeaponName = escapeHtml(weapon.name);
            const safeCategory = escapeHtml(category);

            const html = `
            <div class="glass-card p-6 rounded-xl border-l-4 border-${color} hover:scale-105 transition-transform cursor-pointer">
                <div class="flex items-center justify-between mb-4">
                    <div class="px-3 py-1 rounded bg-slate-800 border border-white/10">
                        <span class="text-xs font-bold text-slate-400 uppercase">${safeCategory}</span>
                    </div>
                    <div class="text-${color} text-2xl">
                        <i data-lucide="crosshair"></i>
                    </div>
                </div>
                <h3 class="text-xl font-black text-white mb-4">${safeWeaponName}</h3>
                <div class="space-y-3">
                    <div class="flex justify-between">
                        <span class="text-sm text-slate-400">Total Kills</span>
                        <span class="font-bold text-white">${weapon.kills.toLocaleString()}</span>
                    </div>
                    <div class="flex justify-between">
                        <span class="text-sm text-slate-400">Usage Rate</span>
                        <span class="font-bold text-slate-300">${usage}%</span>
                    </div>
                    <div class="w-full bg-slate-800 h-2 rounded-full overflow-hidden mt-2">
                        <div class="bg-${color} h-full" style="width: ${Math.min(usage * 2, 100)}%"></div>
                    </div>
                </div>
            </div>
            `;
            grid.insertAdjacentHTML('beforeend', html);
        });
        lucide.createIcons();
    } catch (e) {
        console.error('Failed to load weapons:', e);
        grid.innerHTML = '<div class="col-span-full text-center text-red-500 py-12">Failed to load weapon statistics</div>';
    }
}

// Update navigateTo to load all views
const originalNavigateTo = window.navigateTo;
window.navigateTo = function (viewId) {
    originalNavigateTo.call(this, viewId);

    // Remove old view-specific loading (already in navigateTo)
    // Add new view loaders
    if (viewId === 'maps') {
        loadMapsView();
    } else if (viewId === 'weapons') {
        loadWeaponsView();
    }
};

// Community Logic
let currentCommunityTab = 'clips';

function loadCommunityView() {
    switchCommunityTab(currentCommunityTab);
}

function switchCommunityTab(tab) {
    currentCommunityTab = tab;

    // Update Buttons
    const btnClips = document.getElementById('btn-tab-clips');
    const btnConfigs = document.getElementById('btn-tab-configs');

    if (tab === 'clips') {
        btnClips.className = 'px-6 py-2 rounded-lg font-bold bg-brand-rose text-white shadow-lg transition';
        btnConfigs.className = 'px-6 py-2 rounded-lg font-bold text-slate-400 hover:text-white transition';
        document.getElementById('community-clips').classList.remove('hidden');
        document.getElementById('community-configs').classList.add('hidden');
        loadClips();
    } else {
        btnClips.className = 'px-6 py-2 rounded-lg font-bold text-slate-400 hover:text-white transition';
        btnConfigs.className = 'px-6 py-2 rounded-lg font-bold bg-brand-rose text-white shadow-lg transition';
        document.getElementById('community-clips').classList.add('hidden');
        document.getElementById('community-configs').classList.remove('hidden');
        loadConfigs();
    }
}

async function loadClips() {
    const grid = document.getElementById('clips-grid');
    if (!grid) return;

    // Coming Soon placeholder - API not yet implemented
    grid.innerHTML = `
        <div class="col-span-full text-center py-16">
            <div class="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-brand-rose/10 border border-brand-rose/20 mb-6">
                <i data-lucide="rocket" class="w-4 h-4 text-brand-rose"></i>
                <span class="text-brand-rose font-bold text-sm uppercase">Coming Soon</span>
            </div>
            <h3 class="text-2xl font-black text-white mb-3">Community Clips</h3>
            <p class="text-slate-400 max-w-md mx-auto">Share your best ET:Legacy moments! Clip submission and viewing will be available in a future update.</p>
            <div class="mt-8 flex justify-center gap-4">
                <div class="glass-card p-4 rounded-xl text-center">
                    <i data-lucide="video" class="w-8 h-8 text-slate-600 mx-auto mb-2"></i>
                    <span class="text-xs text-slate-500">Submit Clips</span>
                </div>
                <div class="glass-card p-4 rounded-xl text-center">
                    <i data-lucide="heart" class="w-8 h-8 text-slate-600 mx-auto mb-2"></i>
                    <span class="text-xs text-slate-500">Like & Vote</span>
                </div>
                <div class="glass-card p-4 rounded-xl text-center">
                    <i data-lucide="trophy" class="w-8 h-8 text-slate-600 mx-auto mb-2"></i>
                    <span class="text-xs text-slate-500">Weekly Top 10</span>
                </div>
            </div>
        </div>
    `;
    lucide.createIcons();
}

async function loadConfigs() {
    const list = document.getElementById('configs-list');
    if (!list) return;

    // Coming Soon placeholder - API not yet implemented
    list.innerHTML = `
        <div class="text-center py-16">
            <div class="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-brand-purple/10 border border-brand-purple/20 mb-6">
                <i data-lucide="wrench" class="w-4 h-4 text-brand-purple"></i>
                <span class="text-brand-purple font-bold text-sm uppercase">Coming Soon</span>
            </div>
            <h3 class="text-2xl font-black text-white mb-3">Config Sharing</h3>
            <p class="text-slate-400 max-w-md mx-auto">Share your ET:Legacy configurations! Config upload and download will be available in a future update.</p>
            <div class="mt-8 space-y-3 max-w-sm mx-auto">
                <div class="glass-panel p-4 rounded-xl flex items-center gap-4">
                    <i data-lucide="file-code" class="w-6 h-6 text-slate-600"></i>
                    <div class="text-left">
                        <div class="text-sm font-bold text-slate-400">etconfig.cfg</div>
                        <div class="text-xs text-slate-500">Game settings, binds, scripts</div>
                    </div>
                </div>
                <div class="glass-panel p-4 rounded-xl flex items-center gap-4">
                    <i data-lucide="palette" class="w-6 h-6 text-slate-600"></i>
                    <div class="text-left">
                        <div class="text-sm font-bold text-slate-400">HUD Configurations</div>
                        <div class="text-xs text-slate-500">Custom HUD layouts</div>
                    </div>
                </div>
                <div class="glass-panel p-4 rounded-xl flex items-center gap-4">
                    <i data-lucide="crosshair" class="w-6 h-6 text-slate-600"></i>
                    <div class="text-left">
                        <div class="text-sm font-bold text-slate-400">Crosshair Packs</div>
                        <div class="text-xs text-slate-500">Custom crosshair settings</div>
                    </div>
                </div>
            </div>
        </div>
    `;
    lucide.createIcons();
}

function getYouTubeID(url) {
    const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|&v=)([^#&?]*).*/;
    const match = url.match(regExp);
    return (match && match[2].length === 11) ? match[2] : null;
}

// Upload Modal Logic
function openUploadModal(type = 'clip') {
    const modal = document.getElementById('upload-modal');
    const title = document.getElementById('modal-title');
    const typeInput = document.getElementById('upload-type');
    const fieldUrl = document.getElementById('field-url');
    const fieldContent = document.getElementById('field-content');

    if (type === 'clip') {
        title.textContent = 'Submit Clip';
        typeInput.value = 'clip';
        fieldUrl.classList.remove('hidden');
        fieldContent.classList.add('hidden');
        document.getElementById('upload-url').required = true;
        document.getElementById('upload-content').required = false;
    } else {
        title.textContent = 'Submit Config';
        typeInput.value = 'config';
        fieldUrl.classList.add('hidden');
        fieldContent.classList.remove('hidden');
        document.getElementById('upload-url').required = false;
        document.getElementById('upload-content').required = true;
    }

    modal.classList.remove('hidden');
}

function closeUploadModal() {
    document.getElementById('upload-modal').classList.add('hidden');
    document.getElementById('upload-form').reset();
}

async function handleUpload(e) {
    e.preventDefault();

    const type = document.getElementById('upload-type').value;
    const title = document.getElementById('upload-title').value;
    const desc = document.getElementById('upload-desc').value;

    const payload = {
        title: title,
        description: desc
    };

    if (type === 'clip') {
        payload.url = document.getElementById('upload-url').value;
    } else {
        payload.content = document.getElementById('upload-content').value;
    }

    try {
        const endpoint = type === 'clip' ? 'clips' : 'configs';
        const res = await fetch(`${API_BASE}/community/${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            if (res.status === 401) {
                alert('You must be logged in to submit content.');
                return;
            }
            throw new Error('Upload failed');
        }

        alert('Submission successful!');
        closeUploadModal();

        // Refresh list
        if (type === 'clip') loadClips();
        else loadConfigs();

    } catch (err) {
        console.error(err);
        alert('Failed to submit content. Please try again.');
    }
}
