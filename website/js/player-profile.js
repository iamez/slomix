/**
 * Player profile module - profile page, charts, recent matches
 * @module player-profile
 */

import { API_BASE, fetchJSON, escapeHtml, escapeJsString } from './utils.js';

// Chart instances
let sessionChartInstance = null;
let roundChartInstance = null;

// Navigation function (set by app.js to avoid circular imports)
let navigateToFn = null;
let loadMatchDetailsFn = null;

/**
 * Set navigation function reference
 */
export function setNavigateTo(fn) {
    navigateToFn = fn;
}

/**
 * Set loadMatchDetails function reference
 */
export function setLoadMatchDetails(fn) {
    loadMatchDetailsFn = fn;
}

/**
 * Load player profile page
 */
export async function loadPlayerProfile(playerName) {
    if (navigateToFn) navigateToFn('profile');
    console.log('📋 Loading profile for:', playerName);

    // Reset UI
    const profileName = document.getElementById('profile-name');
    const profileInitials = document.getElementById('profile-initials');
    if (profileName) profileName.textContent = playerName;
    if (profileInitials) profileInitials.textContent = playerName.substring(0, 2).toUpperCase();

    try {
        const data = await fetchJSON(`${API_BASE}/stats/player/${encodeURIComponent(playerName)}`);
        console.log('📋 Profile data received:', data);
        const stats = data.stats;

        // Update Header
        if (profileName) profileName.textContent = data.name;

        const profilePlaytime = document.getElementById('profile-playtime');
        const profileSeen = document.getElementById('profile-seen');
        const profileDpm = document.getElementById('profile-dpm');

        if (profilePlaytime) profilePlaytime.textContent = stats.playtime_hours + 'h';
        if (profileSeen) profileSeen.textContent = new Date(stats.last_seen).toLocaleDateString();
        if (profileDpm) profileDpm.textContent = stats.dpm;

        // Update Cards
        const profileKd = document.getElementById('profile-kd');
        const profileKills = document.getElementById('profile-kills');
        const profileDeaths = document.getElementById('profile-deaths');

        if (profileKd) profileKd.textContent = stats.kd;
        if (profileKills) profileKills.textContent = stats.kills;
        if (profileDeaths) profileDeaths.textContent = stats.deaths;

        const profileWinrate = document.getElementById('profile-winrate');
        const profileWins = document.getElementById('profile-wins');
        const profileGames = document.getElementById('profile-games');

        if (profileWinrate) profileWinrate.textContent = stats.win_rate + '%';
        if (profileWins) profileWins.textContent = stats.wins;
        if (profileGames) profileGames.textContent = stats.games;

        const profileXp = document.getElementById('profile-xp');
        const profileDamage = document.getElementById('profile-damage');
        const profileLosses = document.getElementById('profile-losses');

        if (profileXp) profileXp.textContent = stats.total_xp.toLocaleString();
        if (profileDamage) profileDamage.textContent = (stats.damage / 1000).toFixed(1) + 'k';
        if (profileLosses) profileLosses.textContent = stats.losses;

        // Player info cards - favorite weapon and map
        const favWeapon = document.getElementById('profile-fav-weapon');
        const favMap = document.getElementById('profile-fav-map');

        if (favWeapon) favWeapon.textContent = stats.favorite_weapon || '--';
        if (favMap) favMap.textContent = stats.favorite_map || '--';

        // DPM records - highest and lowest
        const highestDpm = document.getElementById('profile-highest-dpm');
        const lowestDpm = document.getElementById('profile-lowest-dpm');

        if (highestDpm) highestDpm.textContent = stats.highest_dpm || '--';
        if (lowestDpm) lowestDpm.textContent = stats.lowest_dpm || '--';

        // Known aliases
        const aliasContainer = document.getElementById('profile-aliases');
        if (aliasContainer) {
            if (data.aliases && data.aliases.length > 0) {
                aliasContainer.innerHTML = data.aliases
                    .map(a => `<span class="px-2 py-1 rounded bg-slate-700 text-slate-300 text-xs">${escapeHtml(a)}</span>`)
                    .join(' ');
            } else {
                aliasContainer.innerHTML = '<span class="text-slate-500 text-sm">No other aliases</span>';
            }
        }

        // Discord status
        const discordEl = document.getElementById('profile-discord-status');
        if (discordEl) {
            discordEl.textContent = data.discord_linked ? 'Linked' : 'Not Linked';
            discordEl.className = data.discord_linked ? 'text-green-400' : 'text-slate-500';
        }

        // Load recent matches and form chart
        loadPlayerRecentMatches(playerName);
        loadPlayerFormChart(playerName);

    } catch (e) {
        console.error('Failed to load profile:', e);
        alert('Player not found!');
        if (navigateToFn) navigateToFn('home');
    }
}

/**
 * Load both player charts
 */
export async function loadPlayerFormChart(playerName) {
    loadSessionChart(playerName);
    loadRoundChart(playerName);
}

/**
 * Session DPM chart - form over gaming sessions
 */
export async function loadSessionChart(playerName) {
    const canvas = document.getElementById('sessionChart');
    if (!canvas) return;

    try {
        const data = await fetchJSON(`${API_BASE}/stats/player/${encodeURIComponent(playerName)}/form?limit=15`);

        if (!data.sessions || data.sessions.length === 0) {
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = '#64748b';
            ctx.font = '12px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('No sessions', canvas.width / 2, canvas.height / 2);
            return;
        }

        if (sessionChartInstance) sessionChartInstance.destroy();

        const ctx = canvas.getContext('2d');
        const gradient = ctx.createLinearGradient(0, 0, 0, 200);
        gradient.addColorStop(0, 'rgba(16, 185, 129, 0.3)');
        gradient.addColorStop(1, 'rgba(16, 185, 129, 0)');

        sessionChartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.sessions.map(s => s.label),
                datasets: [{
                    label: 'Session DPM',
                    data: data.sessions.map(s => s.dpm),
                    borderColor: '#10b981',
                    backgroundColor: gradient,
                    fill: true,
                    tension: 0.3,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    borderWidth: 2,
                }, {
                    label: 'Avg',
                    data: data.sessions.map(() => data.avg_dpm),
                    borderColor: '#f59e0b',
                    borderDash: [4, 4],
                    borderWidth: 1,
                    pointRadius: 0,
                    fill: false,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            title: (items) => {
                                const s = data.sessions[items[0].dataIndex];
                                return s.date + ' (' + s.rounds + ' rounds)';
                            },
                            label: (item) => item.datasetIndex === 0
                                ? 'DPM: ' + item.raw + ' | K/D: ' + data.sessions[item.dataIndex].kd
                                : 'Avg: ' + item.raw
                        }
                    }
                },
                scales: {
                    y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#64748b', font: { size: 10 } } },
                    x: { grid: { display: false }, ticks: { color: '#64748b', font: { size: 10 }, maxRotation: 45 } }
                }
            }
        });

        // Update title with trend
        const title = document.getElementById('session-chart-title');
        if (title) {
            let icon = '', color = '';
            if (data.trend === 'improving') { icon = '↑'; color = 'text-green-400'; }
            else if (data.trend === 'declining') { icon = '↓'; color = 'text-red-400'; }
            else if (data.trend === 'stable') { icon = '→'; color = 'text-yellow-400'; }
            title.innerHTML = `<i data-lucide="trending-up" class="w-5 h-5 text-brand-emerald inline"></i> Session Form ${icon ? `<span class="${color}">${icon}</span>` : ''}`;
            if (typeof lucide !== 'undefined') lucide.createIcons();
        }
    } catch (e) {
        console.error('Failed to load session chart:', e);
    }
}

/**
 * Round DPM chart - individual map performance
 */
export async function loadRoundChart(playerName) {
    const canvas = document.getElementById('roundChart');
    if (!canvas) return;

    try {
        const data = await fetchJSON(`${API_BASE}/stats/player/${encodeURIComponent(playerName)}/rounds?limit=30`);

        if (!data.rounds || data.rounds.length === 0) {
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = '#64748b';
            ctx.font = '12px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('No rounds', canvas.width / 2, canvas.height / 2);
            return;
        }

        if (roundChartInstance) roundChartInstance.destroy();

        const ctx = canvas.getContext('2d');
        const gradient = ctx.createLinearGradient(0, 0, 0, 200);
        gradient.addColorStop(0, 'rgba(59, 130, 246, 0.3)');
        gradient.addColorStop(1, 'rgba(59, 130, 246, 0)');

        roundChartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.rounds.map(r => r.label),
                datasets: [{
                    label: 'Round DPM',
                    data: data.rounds.map(r => r.dpm),
                    borderColor: '#3b82f6',
                    backgroundColor: gradient,
                    fill: true,
                    tension: 0.2,
                    pointRadius: 2,
                    pointHoverRadius: 5,
                    borderWidth: 1.5,
                }, {
                    label: 'Avg',
                    data: data.rounds.map(() => data.avg_dpm),
                    borderColor: '#f59e0b',
                    borderDash: [4, 4],
                    borderWidth: 1,
                    pointRadius: 0,
                    fill: false,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            title: (items) => {
                                const r = data.rounds[items[0].dataIndex];
                                return r.date + ' - ' + r.label;
                            },
                            label: (item) => item.datasetIndex === 0
                                ? 'DPM: ' + item.raw
                                : 'Avg: ' + item.raw
                        }
                    }
                },
                scales: {
                    y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#64748b', font: { size: 10 } } },
                    x: { grid: { display: false }, ticks: { color: '#64748b', font: { size: 10 }, maxRotation: 45, maxTicksLimit: 15 } }
                }
            }
        });
    } catch (e) {
        console.error('Failed to load round chart:', e);
    }
}

/**
 * Load recent matches for a player
 */
export async function loadPlayerRecentMatches(playerName) {
    console.log('📋 Loading recent matches for:', playerName);
    const container = document.getElementById('profile-recent-matches');
    if (!container) {
        console.error('❌ profile-recent-matches container not found!');
        return;
    }

    container.innerHTML = '<div class="text-center py-4 text-slate-500"><i data-lucide="loader" class="w-6 h-6 animate-spin mx-auto"></i></div>';
    if (typeof lucide !== 'undefined') lucide.createIcons();

    try {
        const matches = await fetchJSON(`${API_BASE}/player/${encodeURIComponent(playerName)}/matches?limit=10`);

        if (matches.length === 0) {
            container.innerHTML = '<div class="text-center py-4 text-slate-500">No recent matches found</div>';
            return;
        }

        container.innerHTML = '';

        matches.forEach(match => {
            const kd = match.kd;
            const kdColor = kd >= 2.0 ? 'text-brand-emerald' : kd >= 1.0 ? 'text-brand-blue' : 'text-brand-rose';
            const safeMapName = escapeHtml(match.map_name);
            const matchDate = new Date(match.round_date).toLocaleDateString();

            const html = `
                <div class="glass-card p-4 rounded-lg hover:bg-white/10 transition cursor-pointer" onclick="loadMatchDetails('${match.round_date}')">
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-4">
                            <div class="w-12 h-12 rounded-lg bg-slate-800 border border-white/10 flex items-center justify-center">
                                <span class="text-xs font-bold text-slate-400 uppercase">${safeMapName.substring(0, 3)}</span>
                            </div>
                            <div>
                                <div class="font-bold text-white">${safeMapName}</div>
                                <div class="text-xs text-slate-400 font-mono">${matchDate} • Round ${match.round_number}</div>
                            </div>
                        </div>
                        <div class="flex gap-6 text-right">
                            <div>
                                <div class="text-xs text-slate-500 uppercase">K/D</div>
                                <div class="text-lg font-bold ${kdColor}">${kd}</div>
                            </div>
                            <div>
                                <div class="text-xs text-slate-500 uppercase">DPM</div>
                                <div class="text-lg font-bold text-brand-emerald">${match.dpm}</div>
                            </div>
                            <div>
                                <div class="text-xs text-slate-500 uppercase">Kills</div>
                                <div class="text-lg font-bold text-brand-rose">${match.kills}</div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            container.insertAdjacentHTML('beforeend', html);
        });

        if (typeof lucide !== 'undefined') lucide.createIcons();
    } catch (e) {
        console.error('Failed to load player matches:', e);
        container.innerHTML = '<div class="text-center text-red-500 py-4">Failed to load recent matches</div>';
    }
}

/**
 * Load weapon breakdown chart for player profile
 */
export async function loadPlayerWeaponChart(playerName) {
    // API endpoint pending
    console.log('Weapon chart for', playerName, '- API endpoint pending');
}

// Expose to window for onclick handlers in HTML
window.loadPlayerProfile = loadPlayerProfile;
