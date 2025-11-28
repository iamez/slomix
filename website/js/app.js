// Navigation Logic (Global)
window.navigateTo = function (viewId) {
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

    // Scroll to top
    window.scrollTo(0, 0);
};

// Slomix Frontend Logic
const API_BASE = 'http://localhost:8000/api';
const AUTH_BASE = 'http://localhost:8000/auth';

document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

async function initApp() {
    console.log('🚀 Slomix App Initializing...');

    // Check API Status
    try {
        const status = await fetchJSON(`${API_BASE}/status`);
        console.log('API Status:', status);
        document.getElementById('server-status-dot').classList.remove('bg-red-500');
        document.getElementById('server-status-dot').classList.add('bg-green-500');
        document.getElementById('server-status-text').textContent = 'Online';
    } catch (e) {
        console.error('API Offline:', e);
        document.getElementById('server-status-dot').classList.add('bg-red-500');
        document.getElementById('server-status-text').textContent = 'Offline';
    }

    // Load Data
    loadSeasonInfo();
    loadLastSession();
    loadPredictions(); // New
    loadLeaderboard();
    loadMatches();
    checkLoginStatus();
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

            // Determine status
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
                            <span class="text-[10px] font-bold text-slate-500 uppercase bg-slate-800 px-1.5 py-0.5 rounded">${pred.format}</span>
                            <span class="text-[10px] font-mono text-slate-400">${timeAgo}</span>
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
                            <span>Confidence: <span class="text-white font-bold uppercase">${pred.confidence}</span></span>
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

        // Update "Last Session" widget
        document.getElementById('ls-date').textContent = data.date;
        document.getElementById('ls-players').textContent = data.player_count;
        document.getElementById('ls-rounds').textContent = data.rounds;
        document.getElementById('ls-maps').textContent = data.maps.length;

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

        const html = `
            <div class="glass-card p-4 rounded-xl flex items-center justify-between gap-4 hover:bg-white/5 transition group">
                <div class="flex items-center gap-4">
                    <div class="w-12 h-12 rounded bg-slate-800 flex items-center justify-center font-bold text-slate-500 text-xs uppercase border border-white/5">
                        ${match.map_name.substring(0, 3)}
                    </div>
                    <div>
                        <div class="font-bold text-white group-hover:text-brand-cyan transition">${match.map_name}</div>
                        <div class="text-xs text-slate-500 font-mono">Round ${match.round_number} • ${match.duration}</div>
                    </div>
                </div>
                
                <div class="flex items-center gap-6">
                    <div class="text-right">
                        <div class="text-[10px] uppercase font-bold text-slate-500">Winner</div>
                        <div class="font-black ${winnerColor}">${match.winner}</div>
                    </div>
                    <div class="px-3 py-1 rounded ${winnerBg} text-xs font-bold text-white">
                        ${match.outcome || 'Victory'}
                    </div>
                </div>
            </div>
        `;
        container.insertAdjacentHTML('beforeend', html);
    });
}

async function loadLeaderboard() {
    try {
        const leaders = await fetchJSON(`${API_BASE}/stats/leaderboard?limit=5`);
        const list = document.getElementById('quick-leaders-list');
        if (!list) return;

        list.innerHTML = '';

        leaders.forEach((player, index) => {
            const rankColor = index === 0 ? 'text-brand-gold' : index === 1 ? 'text-slate-400' : 'text-brand-rose';
            const initials = player.name.substring(0, 2).toUpperCase();

            const html = `
                <div class="flex items-center justify-between group cursor-pointer">
                    <div class="flex items-center gap-3">
                        <div class="font-mono font-bold ${rankColor} text-sm">${player.rank}</div>
                        <div class="w-8 h-8 rounded bg-slate-800 flex items-center justify-center text-xs font-bold text-slate-400">${initials}</div>
                        <div class="text-sm font-bold text-white group-hover:text-brand-blue transition">${player.name}</div>
                    </div>
                    <div class="text-sm font-mono font-bold text-brand-emerald">${player.dpm} DPM</div>
                </div>
            `;
            list.insertAdjacentHTML('beforeend', html);
        });
    } catch (e) {
        console.error('Failed to load leaderboard:', e);
        const list = document.getElementById('quick-leaders-list');
        if (list) list.innerHTML = '<div class="text-center text-red-500 text-xs py-4">Failed to load</div>';
    }
}

async function loadMatches() {
    try {
        const matches = await fetchJSON(`${API_BASE}/stats/matches?limit=5`);
        const list = document.getElementById('match-history-list');
        if (!list) return;

        list.innerHTML = '';

        if (matches.length === 0) {
            list.innerHTML = '<div class="text-center text-slate-500 py-12">No matches found</div>';
            return;
        }

        matches.forEach(match => {
            const winnerColor = match.winner === 'Allies' ? 'text-brand-blue' : 'text-brand-rose';
            const winnerBg = match.winner === 'Allies' ? 'bg-brand-blue/10 border-brand-blue/20 text-brand-blue' : 'bg-brand-rose/10 border-brand-rose/20 text-brand-rose';

            // Calculate relative time (simple version)
            const date = new Date(match.date);
            const now = new Date();
            const diffMs = now - date;
            const diffHrs = Math.floor(diffMs / (1000 * 60 * 60));
            const timeAgo = diffHrs > 24 ? Math.floor(diffHrs / 24) + 'd ago' : diffHrs + 'h ago';

            const html = `
            <div class="glass-card p-4 md:p-6 rounded-xl flex flex-col md:flex-row items-center justify-between gap-6 cursor-pointer group"
                onclick="navigateTo('match-details')">
                <div class="flex items-center gap-6 w-full md:w-auto">
                    <div class="w-16 h-16 rounded-lg bg-slate-800 border border-white/10 flex items-center justify-center flex-shrink-0">
                        <span class="text-xs font-bold text-slate-500 uppercase">${match.map_name.substring(0, 3)}</span>
                    </div>
                    <div>
                        <div class="flex items-center gap-3 mb-1">
                            <h3 class="text-lg font-bold text-white group-hover:text-brand-blue transition">${match.map_name}</h3>
                            <span class="px-2 py-0.5 rounded ${winnerBg} text-[10px] font-bold uppercase">${match.winner} Victory</span>
                        </div>
                        <div class="text-sm text-slate-400 font-mono">${timeAgo} • ${match.duration}</div>
                    </div>
                </div>

                <div class="flex items-center gap-8 md:gap-12">
                    <div class="text-center">
                        <div class="text-[10px] uppercase font-bold text-slate-500 mb-1">Winner</div>
                        <div class="text-xl font-black ${winnerColor}">${match.winner.toUpperCase()}</div>
                    </div>
                    <div class="h-8 w-px bg-white/10"></div>
                    <div class="text-center">
                        <div class="text-[10px] uppercase font-bold text-slate-500 mb-1">Round</div>
                        <div class="text-xl font-black text-white">${match.round_number}</div>
                    </div>
                </div>

                <button class="w-full md:w-auto px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm font-bold text-white transition border border-white/5">
                    Details
                </button>
            </div>
            `;
            list.insertAdjacentHTML('beforeend', html);
        });
    } catch (e) {
        console.error('Failed to load matches:', e);
        const list = document.getElementById('match-history-list');
        if (list) list.innerHTML = '<div class="text-center text-red-500 py-12">Failed to load matches</div>';
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
            div.innerHTML = `<span class="font-bold text-white">${name}</span> <span class="text-xs text-brand-blue font-bold">CLAIM</span>`;
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
                div.innerHTML = `
                <div class="flex items-center gap-3">
                    <div class="w-8 h-8 rounded bg-slate-800 flex items-center justify-center text-xs font-bold text-slate-400">
                        ${name.substring(0, 2).toUpperCase()}
                    </div>
                    <span class="font-bold text-white">${name}</span>
                </div>
                <span class="text-xs text-brand-blue font-bold opacity-0 group-hover:opacity-100 transition">VIEW STATS</span>
            `;
                // For now, just link/claim. In future, navigate to profile.
                div.onclick = () => linkPlayer(name);
                heroSearchResults.appendChild(div);
            });
        }
        heroSearchResults.classList.remove('hidden');
    } catch (e) {
        console.error(e);
    }
}
