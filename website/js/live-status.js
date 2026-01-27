/**
 * Live status module - Game server & voice channel status
 * @module live-status
 */

import { API_BASE, fetchJSON, escapeHtml, formatTimeAgo } from './utils.js';

// Polling configuration
const LIVE_POLL_INTERVAL = 10000; // 10 seconds
let liveSessionInterval = null;

/**
 * Load game server and voice channel status
 */
export async function loadLiveStatus() {
    try {
        const data = await fetchJSON(`${API_BASE}/live-status`);

        // ========== GAME SERVER STATUS ==========
        const serverBadge = document.getElementById('server-status-badge');
        const serverDetails = document.getElementById('server-status-details');
        const serverPlayerCount = document.getElementById('server-player-count');
        const serverCard = document.getElementById('live-server-status');

        if (serverBadge && serverDetails) {
            const server = data.game_server;

            if (server.online) {
                // Server is ONLINE
                serverBadge.textContent = 'ONLINE';
                serverBadge.className = 'px-2 py-0.5 rounded text-[10px] font-bold bg-brand-emerald/20 text-brand-emerald';

                // Build server info display
                const hostname = escapeHtml(server.hostname) || 'Game Server';
                const mapName = escapeHtml(server.map) || 'Unknown';
                const pingDisplay = server.ping_ms !== null ? `${server.ping_ms}ms` : '';
                const playerCount = `${server.player_count}/${server.max_players}`;

                if (server.player_count > 0) {
                    // Show players when server has players
                    const playerNames = server.players.map(p => escapeHtml(p.name)).join(', ');
                    serverDetails.innerHTML = `
                        <span class="text-white font-semibold">${hostname}</span>
                        <span class="text-slate-500 mx-1">·</span>
                        <span class="text-brand-cyan">${mapName}</span>
                        <span class="text-slate-500 mx-1">·</span>
                        <span class="text-slate-400">${playerNames}</span>
                        ${pingDisplay ? `<span class="text-slate-600 ml-2 text-xs">(${pingDisplay})</span>` : ''}
                    `;
                    if (serverPlayerCount) {
                        serverPlayerCount.classList.remove('hidden');
                        serverPlayerCount.querySelector('div').textContent = server.player_count;
                    }
                } else {
                    // Empty server
                    serverDetails.innerHTML = `
                        <span class="text-white font-semibold">${hostname}</span>
                        <span class="text-slate-500 mx-1">·</span>
                        <span class="text-brand-cyan">${mapName}</span>
                        <span class="text-slate-500 mx-1">·</span>
                        <span class="text-slate-500">${playerCount} players</span>
                        ${pingDisplay ? `<span class="text-slate-600 ml-2 text-xs">(${pingDisplay})</span>` : ''}
                    `;
                    if (serverPlayerCount) serverPlayerCount.classList.add('hidden');
                }

                // Add green glow to card
                if (serverCard) {
                    serverCard.classList.add('border-brand-emerald/30');
                }
            } else {
                // Server is OFFLINE
                serverBadge.textContent = 'OFFLINE';
                serverBadge.className = 'px-2 py-0.5 rounded text-[10px] font-bold bg-red-500/20 text-red-400';

                const hostname = escapeHtml(server.hostname) || 'Game Server';
                const errorMsg = server.error || 'Server is not responding';
                serverDetails.innerHTML = `
                    <span class="text-slate-400">${hostname}</span>
                    <span class="text-slate-500 mx-1">·</span>
                    <span class="text-red-400/70">${errorMsg}</span>
                `;

                if (serverPlayerCount) serverPlayerCount.classList.add('hidden');
                if (serverCard) {
                    serverCard.classList.remove('border-brand-emerald/30');
                }
            }
        }

        // ========== VOICE CHANNEL STATUS ==========
        const voiceBadge = document.getElementById('voice-status-badge');
        const voiceMembersList = document.getElementById('voice-members-list');
        const voiceMemberCount = document.getElementById('voice-member-count');
        const voiceCard = document.getElementById('live-voice-status');

        if (voiceBadge && voiceMembersList) {
            const voice = data.voice_channel;

            if (voice.count > 0) {
                // People in voice
                voiceBadge.textContent = 'ACTIVE';
                voiceBadge.className = 'px-2 py-0.5 rounded text-[10px] font-bold bg-brand-purple/20 text-brand-purple';

                // List member names
                const memberNames = voice.members.map(m => escapeHtml(m.name)).join(', ');
                voiceMembersList.innerHTML = `<span class="text-white">${memberNames}</span>`;

                if (voiceMemberCount) {
                    voiceMemberCount.querySelector('div').textContent = voice.count;
                }

                // Add purple glow to card
                if (voiceCard) {
                    voiceCard.classList.add('border-brand-purple/30');
                }
            } else {
                // Voice empty
                voiceBadge.textContent = 'EMPTY';
                voiceBadge.className = 'px-2 py-0.5 rounded text-[10px] font-bold bg-slate-700 text-slate-400';
                voiceMembersList.textContent = 'No one in voice';

                if (voiceMemberCount) {
                    voiceMemberCount.querySelector('div').textContent = '0';
                }

                if (voiceCard) {
                    voiceCard.classList.remove('border-brand-purple/30');
                }
            }
        }

    } catch (e) {
        console.error('Failed to load live status:', e);

        // Show error state
        const serverBadge = document.getElementById('server-status-badge');
        const serverDetails = document.getElementById('server-status-details');
        if (serverBadge) {
            serverBadge.textContent = 'ERROR';
            serverBadge.className = 'px-2 py-0.5 rounded text-[10px] font-bold bg-slate-700 text-slate-400';
        }
        if (serverDetails) {
            serverDetails.textContent = 'Could not fetch status';
        }
    }
}

/**
 * Update live session status
 */
export async function updateLiveSession() {
    try {
        const data = await fetchJSON(`${API_BASE}/stats/live-session`);
        const widget = document.getElementById('live-session-widget');

        if (!widget) return;

        if (data.active) {
            widget.classList.remove('hidden');
            const livePlayers = document.getElementById('live-players');
            const liveRounds = document.getElementById('live-rounds');
            const liveMap = document.getElementById('live-map');

            if (livePlayers) livePlayers.textContent = data.current_players;
            if (liveRounds) liveRounds.textContent = data.rounds_completed;
            if (liveMap) liveMap.textContent = data.current_map;
        } else {
            widget.classList.add('hidden');
        }
    } catch (e) {
        console.error('Failed to update live session:', e);
    }
}

/**
 * Start live session polling
 */
export function startLivePolling() {
    if (!liveSessionInterval) {
        updateLiveSession();
        liveSessionInterval = setInterval(updateLiveSession, LIVE_POLL_INTERVAL);
        console.log('🟢 Live session polling started');
    }
}

/**
 * Stop live session polling
 */
export function stopLivePolling() {
    if (liveSessionInterval) {
        clearInterval(liveSessionInterval);
        liveSessionInterval = null;
        console.log('🔴 Live session polling paused (tab hidden)');
    }
}

/**
 * Initialize visibility change listener for polling
 */
export function initLivePolling() {
    startLivePolling();

    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            stopLivePolling();
        } else {
            startLivePolling();
        }
    });
}

// ==================== SERVER ACTIVITY CHART ====================

let serverActivityChart = null;
let serverExpanded = false;
let currentTimeRange = 720; // Default 30 days

/**
 * Toggle server details expansion
 */
export function toggleServerDetails() {
    const expandedContent = document.getElementById('server-expanded-content');
    const expandIcon = document.getElementById('server-expand-icon');

    if (!expandedContent) return;

    serverExpanded = !serverExpanded;

    if (serverExpanded) {
        expandedContent.classList.remove('hidden');
        expandIcon?.classList.add('rotate-180');
        // Load chart data on first expand
        loadServerActivity(currentTimeRange);
    } else {
        expandedContent.classList.add('hidden');
        expandIcon?.classList.remove('rotate-180');
    }
}

/**
 * Load server activity data and render chart
 */
export async function loadServerActivity(hours = 720) {
    currentTimeRange = hours;

    // Update active button
    const buttons = document.querySelectorAll('.time-range-btn');
    buttons.forEach(btn => {
        btn.classList.remove('bg-brand-emerald/20', 'text-brand-emerald', 'active');
        btn.classList.add('bg-slate-700', 'text-slate-400');
    });

    const activeBtn = Array.from(buttons).find(btn =>
        btn.textContent.includes(hours === 24 ? '24h' : hours === 72 ? '3d' : hours === 168 ? '7d' : '30d')
    );
    if (activeBtn) {
        activeBtn.classList.remove('bg-slate-700', 'text-slate-400');
        activeBtn.classList.add('bg-brand-emerald/20', 'text-brand-emerald', 'active');
    }

    try {
        const data = await fetchJSON(`${API_BASE}/server-activity/history?hours=${hours}`);

        const chartContainer = document.getElementById('server-activity-chart');
        const noDataDiv = document.getElementById('server-no-data');
        const summaryDiv = document.getElementById('server-stats-summary');

        if (data.data_points.length === 0) {
            // No data yet
            if (chartContainer) chartContainer.style.display = 'none';
            if (noDataDiv) noDataDiv.classList.remove('hidden');
            if (summaryDiv) summaryDiv.classList.add('hidden');
            return;
        }

        // Show chart, hide no-data
        if (chartContainer) chartContainer.style.display = 'block';
        if (noDataDiv) noDataDiv.classList.add('hidden');
        if (summaryDiv) summaryDiv.classList.remove('hidden');

        // Update summary stats
        document.getElementById('stat-peak-players').textContent = data.summary.peak_players;
        document.getElementById('stat-avg-players').textContent = data.summary.avg_players;
        document.getElementById('stat-uptime').textContent = `${data.summary.uptime_percent}%`;

        // Prepare chart data
        const labels = data.data_points.map(p => {
            const d = new Date(p.timestamp);
            if (hours <= 24) {
                return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            } else if (hours <= 168) {
                return d.toLocaleDateString([], { weekday: 'short', hour: '2-digit' });
            } else {
                return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
            }
        });

        const playerCounts = data.data_points.map(p => p.player_count);

        // Destroy existing chart
        if (serverActivityChart) {
            serverActivityChart.destroy();
        }

        // Create gradient
        const ctx = chartContainer.getContext('2d');
        const gradient = ctx.createLinearGradient(0, 0, 0, 128);
        gradient.addColorStop(0, 'rgba(16, 185, 129, 0.3)');
        gradient.addColorStop(1, 'rgba(16, 185, 129, 0)');

        // Create chart
        serverActivityChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Players',
                    data: playerCounts,
                    borderColor: '#10b981',
                    backgroundColor: gradient,
                    fill: true,
                    tension: 0.3,
                    pointRadius: hours > 168 ? 0 : 2,
                    pointHoverRadius: 4,
                    borderWidth: 2,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index',
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: 'rgba(15, 23, 42, 0.9)',
                        titleColor: '#e2e8f0',
                        bodyColor: '#94a3b8',
                        borderColor: 'rgba(255,255,255,0.1)',
                        borderWidth: 1,
                        callbacks: {
                            title: (items) => {
                                const idx = items[0].dataIndex;
                                const point = data.data_points[idx];
                                return new Date(point.timestamp).toLocaleString();
                            },
                            label: (item) => {
                                const idx = item.dataIndex;
                                const point = data.data_points[idx];
                                return `${item.raw} players · ${point.map || 'Unknown map'}`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: Math.max(16, ...playerCounts) + 2,
                        grid: { color: 'rgba(255,255,255,0.05)' },
                        ticks: { color: '#64748b', stepSize: 2 }
                    },
                    x: {
                        grid: { display: false },
                        ticks: {
                            color: '#64748b',
                            maxRotation: 0,
                            autoSkip: true,
                            maxTicksLimit: hours > 168 ? 8 : 12
                        }
                    }
                }
            }
        });

    } catch (e) {
        console.error('Failed to load server activity:', e);
    }
}

// Expose functions to window for onclick handlers
window.toggleServerDetails = toggleServerDetails;
window.loadServerActivity = loadServerActivity;

// ==================== VOICE ACTIVITY CHART ====================

let voiceActivityChart = null;
let voiceExpanded = false;
let currentVoiceTimeRange = 720; // Default 30 days

/**
 * Toggle voice channel details expansion
 */
export function toggleVoiceDetails() {
    const expandedContent = document.getElementById('voice-expanded-content');
    const expandIcon = document.getElementById('voice-expand-icon');

    if (!expandedContent) return;

    voiceExpanded = !voiceExpanded;

    if (voiceExpanded) {
        expandedContent.classList.remove('hidden');
        expandIcon?.classList.add('rotate-180');
        // Load detailed members and chart data on expand
        loadCurrentVoiceMembers();
        loadVoiceActivity(currentVoiceTimeRange);
    } else {
        expandedContent.classList.add('hidden');
        expandIcon?.classList.remove('rotate-180');
    }
}

/**
 * Format duration in seconds to human readable
 */
function formatDuration(seconds) {
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) {
        const mins = Math.floor(seconds / 60);
        return `${mins}m`;
    }
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`;
}

/**
 * Load detailed current voice members
 */
export async function loadCurrentVoiceMembers() {
    const container = document.getElementById('voice-members-detailed');
    if (!container) return;

    try {
        const data = await fetchJSON(`${API_BASE}/voice-activity/current`);

        if (data.total_count === 0) {
            container.innerHTML = `
                <div class="flex items-center gap-3 text-slate-500">
                    <i data-lucide="mic-off" class="w-4 h-4"></i>
                    <span class="text-sm">No one currently in voice</span>
                </div>
            `;
            lucide.createIcons();
            return;
        }

        // Group by channel if we have channel info
        if (data.channels && data.channels.length > 0) {
            container.innerHTML = data.channels.map(channel => `
                <div class="mb-3 last:mb-0">
                    <div class="flex items-center gap-2 mb-2">
                        <i data-lucide="hash" class="w-3 h-3 text-slate-500"></i>
                        <span class="text-xs font-bold text-slate-400 uppercase">${escapeHtml(channel.name)}</span>
                        <span class="text-xs text-slate-600">(${channel.members.length})</span>
                    </div>
                    <div class="space-y-1.5 ml-5">
                        ${channel.members.map(m => `
                            <div class="flex items-center justify-between p-2 rounded-lg bg-slate-800/50 hover:bg-slate-800 transition">
                                <div class="flex items-center gap-2">
                                    <div class="w-6 h-6 rounded-full bg-gradient-to-br from-brand-purple to-brand-blue flex items-center justify-center text-[10px] font-bold text-white">
                                        ${escapeHtml(m.name.charAt(0).toUpperCase())}
                                    </div>
                                    <span class="text-sm font-medium text-white">${escapeHtml(m.name)}</span>
                                </div>
                                <div class="flex items-center gap-2 text-xs text-slate-500">
                                    <i data-lucide="clock" class="w-3 h-3"></i>
                                    <span>${formatDuration(m.duration_seconds || 0)}</span>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `).join('');
        } else {
            // Flat list without channel grouping
            container.innerHTML = `
                <div class="space-y-1.5">
                    ${data.members.map(m => `
                        <div class="flex items-center justify-between p-2 rounded-lg bg-slate-800/50 hover:bg-slate-800 transition">
                            <div class="flex items-center gap-2">
                                <div class="w-6 h-6 rounded-full bg-gradient-to-br from-brand-purple to-brand-blue flex items-center justify-center text-[10px] font-bold text-white">
                                    ${escapeHtml(m.name.charAt(0).toUpperCase())}
                                </div>
                                <span class="text-sm font-medium text-white">${escapeHtml(m.name)}</span>
                            </div>
                            ${m.duration_seconds ? `
                                <div class="flex items-center gap-2 text-xs text-slate-500">
                                    <i data-lucide="clock" class="w-3 h-3"></i>
                                    <span>${formatDuration(m.duration_seconds)}</span>
                                </div>
                            ` : ''}
                        </div>
                    `).join('')}
                </div>
            `;
        }

        lucide.createIcons();

    } catch (e) {
        console.error('Failed to load current voice members:', e);
        container.innerHTML = `
            <div class="text-sm text-slate-500">Could not load member details</div>
        `;
    }
}

/**
 * Load voice activity data and render chart
 */
export async function loadVoiceActivity(hours = 720) {
    currentVoiceTimeRange = hours;

    // Update active button
    const buttons = document.querySelectorAll('.voice-time-range-btn');
    buttons.forEach(btn => {
        btn.classList.remove('bg-brand-purple/20', 'text-brand-purple', 'active');
        btn.classList.add('bg-slate-700', 'text-slate-400');
    });

    const activeBtn = Array.from(buttons).find(btn =>
        btn.textContent.includes(hours === 24 ? '24h' : hours === 72 ? '3d' : hours === 168 ? '7d' : '30d')
    );
    if (activeBtn) {
        activeBtn.classList.remove('bg-slate-700', 'text-slate-400');
        activeBtn.classList.add('bg-brand-purple/20', 'text-brand-purple', 'active');
    }

    try {
        const data = await fetchJSON(`${API_BASE}/voice-activity/history?hours=${hours}`);

        const chartContainer = document.getElementById('voice-activity-chart');
        const noDataDiv = document.getElementById('voice-no-data');
        const summaryDiv = document.getElementById('voice-stats-summary');

        if (data.data_points.length === 0) {
            // No data yet
            if (chartContainer) chartContainer.style.display = 'none';
            if (noDataDiv) noDataDiv.classList.remove('hidden');
            if (summaryDiv) summaryDiv.classList.add('hidden');
            return;
        }

        // Show chart, hide no-data
        if (chartContainer) chartContainer.style.display = 'block';
        if (noDataDiv) noDataDiv.classList.add('hidden');
        if (summaryDiv) summaryDiv.classList.remove('hidden');

        // Update summary stats
        document.getElementById('stat-peak-members').textContent = data.summary.peak_members;
        document.getElementById('stat-avg-members').textContent = data.summary.avg_members;
        document.getElementById('stat-total-sessions').textContent = data.summary.total_sessions;

        // Prepare chart data
        const labels = data.data_points.map(p => {
            const d = new Date(p.timestamp);
            if (hours <= 24) {
                return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            } else if (hours <= 168) {
                return d.toLocaleDateString([], { weekday: 'short', hour: '2-digit' });
            } else {
                return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
            }
        });

        const memberCounts = data.data_points.map(p => p.member_count);

        // Destroy existing chart
        if (voiceActivityChart) {
            voiceActivityChart.destroy();
        }

        // Create gradient
        const ctx = chartContainer.getContext('2d');
        const gradient = ctx.createLinearGradient(0, 0, 0, 128);
        gradient.addColorStop(0, 'rgba(139, 92, 246, 0.3)');
        gradient.addColorStop(1, 'rgba(139, 92, 246, 0)');

        // Create chart
        voiceActivityChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Members',
                    data: memberCounts,
                    borderColor: '#8b5cf6',
                    backgroundColor: gradient,
                    fill: true,
                    tension: 0.3,
                    pointRadius: hours > 168 ? 0 : 2,
                    pointHoverRadius: 4,
                    borderWidth: 2,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index',
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: 'rgba(15, 23, 42, 0.9)',
                        titleColor: '#e2e8f0',
                        bodyColor: '#94a3b8',
                        borderColor: 'rgba(255,255,255,0.1)',
                        borderWidth: 1,
                        callbacks: {
                            title: (items) => {
                                const idx = items[0].dataIndex;
                                const point = data.data_points[idx];
                                return new Date(point.timestamp).toLocaleString();
                            },
                            label: (item) => {
                                return `${item.raw} members in voice`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: Math.max(12, ...memberCounts) + 2,
                        grid: { color: 'rgba(255,255,255,0.05)' },
                        ticks: { color: '#64748b', stepSize: 1 }
                    },
                    x: {
                        grid: { display: false },
                        ticks: {
                            color: '#64748b',
                            maxRotation: 0,
                            autoSkip: true,
                            maxTicksLimit: hours > 168 ? 8 : 12
                        }
                    }
                }
            }
        });

    } catch (e) {
        console.error('Failed to load voice activity:', e);
        // Show no-data state on error
        const chartContainer = document.getElementById('voice-activity-chart');
        const noDataDiv = document.getElementById('voice-no-data');
        if (chartContainer) chartContainer.style.display = 'none';
        if (noDataDiv) noDataDiv.classList.remove('hidden');
    }
}

// Expose voice functions to window
window.toggleVoiceDetails = toggleVoiceDetails;
window.loadVoiceActivity = loadVoiceActivity;
window.loadCurrentVoiceMembers = loadCurrentVoiceMembers;
