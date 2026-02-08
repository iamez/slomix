/**
 * Live status module - Game server & voice channel status
 * @module live-status
 */

import { API_BASE, fetchJSON, escapeHtml, formatTimeAgo } from './utils.js';

// Polling configuration
const LIVE_POLL_INTERVAL = 10000; // 10 seconds
let liveSessionInterval = null;

function refreshLucideIcons() {
    if (typeof lucide !== 'undefined' && typeof lucide.createIcons === 'function') {
        lucide.createIcons();
    }
}

function hasChartJs() {
    return typeof Chart !== 'undefined';
}

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

async function updateMonitoringHistoryStatus(kind, historyStatusEl) {
    if (!historyStatusEl) return;
    try {
        const status = await fetchJSON(`${API_BASE}/monitoring/status`);
        const entry = status?.[kind];
        if (!entry) return;

        if (entry.count > 0) {
            const last = entry.last_recorded_at ? formatTimeAgo(new Date(entry.last_recorded_at)) : 'unknown';
            historyStatusEl.textContent = `History: ${entry.count} samples · last ${last}`;
            return;
        }

        if (entry.error) {
            historyStatusEl.textContent = 'History: unavailable';
        } else {
            historyStatusEl.textContent = 'History: no samples yet';
        }
    } catch (e) {
        historyStatusEl.textContent = 'History: unavailable';
    }
}

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
        const historyStatus = document.getElementById('server-history-status');

        if (data.data_points.length === 0) {
            // No data yet
            if (chartContainer) chartContainer.style.display = 'none';
            if (noDataDiv) noDataDiv.classList.remove('hidden');
            if (summaryDiv) summaryDiv.classList.add('hidden');
            if (historyStatus) historyStatus.textContent = 'History: collecting';
            if (historyStatus) {
                updateMonitoringHistoryStatus('server', historyStatus);
            }
            return;
        }

        // Show chart, hide no-data
        if (chartContainer) chartContainer.style.display = 'block';
        if (noDataDiv) noDataDiv.classList.add('hidden');
        if (summaryDiv) summaryDiv.classList.remove('hidden');
        if (historyStatus) {
            const lastPoint = data.data_points[data.data_points.length - 1];
            const lastLabel = lastPoint?.timestamp ? formatTimeAgo(new Date(lastPoint.timestamp)) : 'unknown';
            historyStatus.textContent = `History: ${data.summary.total_records} samples · last ${lastLabel}`;
        }

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

        if (!hasChartJs()) {
            if (historyStatus) historyStatus.textContent = 'History: chart library unavailable';
            return;
        }

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
        const historyStatus = document.getElementById('server-history-status');
        if (historyStatus) historyStatus.textContent = 'History: unavailable';
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
        container.innerHTML = '';

        if (data.total_count === 0) {
            const row = document.createElement('div');
            row.className = 'flex items-center gap-3 text-slate-500';
            row.innerHTML = '<i data-lucide="mic-off" class="w-4 h-4"></i><span class="text-sm">No one currently in voice</span>';
            container.appendChild(row);
            refreshLucideIcons();
            return;
        }

        const makeMemberRow = (member) => {
            const row = document.createElement('div');
            row.className = 'flex items-center justify-between p-2 rounded-lg bg-slate-800/50 hover:bg-slate-800 transition';

            const left = document.createElement('div');
            left.className = 'flex items-center gap-2';

            const avatar = document.createElement('div');
            avatar.className = 'w-6 h-6 rounded-full bg-gradient-to-br from-brand-purple to-brand-blue flex items-center justify-center text-[10px] font-bold text-white';
            const memberName = String(member?.name || 'U');
            avatar.textContent = memberName.charAt(0).toUpperCase();

            const nameEl = document.createElement('span');
            nameEl.className = 'text-sm font-medium text-white';
            nameEl.textContent = memberName;

            left.appendChild(avatar);
            left.appendChild(nameEl);
            row.appendChild(left);

            if (member?.duration_seconds) {
                const right = document.createElement('div');
                right.className = 'flex items-center gap-2 text-xs text-slate-500';
                right.innerHTML = '<i data-lucide="clock" class="w-3 h-3"></i>';
                const duration = document.createElement('span');
                duration.textContent = formatDuration(member.duration_seconds);
                right.appendChild(duration);
                row.appendChild(right);
            }

            return row;
        };

        // Group by channel if we have channel info
        if (data.channels && data.channels.length > 0) {
            for (const channel of data.channels) {
                const channelWrap = document.createElement('div');
                channelWrap.className = 'mb-3 last:mb-0';

                const header = document.createElement('div');
                header.className = 'flex items-center gap-2 mb-2';
                header.innerHTML = '<i data-lucide="hash" class="w-3 h-3 text-slate-500"></i>';

                const nameEl = document.createElement('span');
                nameEl.className = 'text-xs font-bold text-slate-400 uppercase';
                nameEl.textContent = String(channel?.name || '');
                const countEl = document.createElement('span');
                countEl.className = 'text-xs text-slate-600';
                countEl.textContent = `(${Array.isArray(channel?.members) ? channel.members.length : 0})`;
                header.appendChild(nameEl);
                header.appendChild(countEl);

                const membersWrap = document.createElement('div');
                membersWrap.className = 'space-y-1.5 ml-5';
                for (const member of (channel.members || [])) {
                    membersWrap.appendChild(makeMemberRow(member));
                }

                channelWrap.appendChild(header);
                channelWrap.appendChild(membersWrap);
                container.appendChild(channelWrap);
            }
        } else {
            const membersWrap = document.createElement('div');
            membersWrap.className = 'space-y-1.5';
            for (const member of (data.members || [])) {
                membersWrap.appendChild(makeMemberRow(member));
            }
            container.appendChild(membersWrap);
        }

        refreshLucideIcons();

    } catch (e) {
        console.error('Failed to load current voice members:', e);
        container.textContent = '';
        const msg = document.createElement('div');
        msg.className = 'text-sm text-slate-500';
        msg.textContent = 'Could not load member details';
        container.appendChild(msg);
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
        const historyStatus = document.getElementById('voice-history-status');

        if (data.data_points.length === 0) {
            // No data yet
            if (chartContainer) chartContainer.style.display = 'none';
            if (noDataDiv) noDataDiv.classList.remove('hidden');
            if (summaryDiv) summaryDiv.classList.add('hidden');
            if (historyStatus) historyStatus.textContent = 'History: collecting';
            if (historyStatus) {
                updateMonitoringHistoryStatus('voice', historyStatus);
            }
            return;
        }

        // Show chart, hide no-data
        if (chartContainer) chartContainer.style.display = 'block';
        if (noDataDiv) noDataDiv.classList.add('hidden');
        if (summaryDiv) summaryDiv.classList.remove('hidden');
        if (historyStatus) {
            const lastPoint = data.data_points[data.data_points.length - 1];
            const lastLabel = lastPoint?.timestamp ? formatTimeAgo(new Date(lastPoint.timestamp)) : 'unknown';
            historyStatus.textContent = `History: ${data.summary.total_records} samples · last ${lastLabel}`;
        }

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

        if (!hasChartJs()) {
            if (historyStatus) historyStatus.textContent = 'History: chart library unavailable';
            return;
        }

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
        const historyStatus = document.getElementById('voice-history-status');
        if (historyStatus) historyStatus.textContent = 'History: unavailable';
    }
}

// Expose voice functions to window
window.toggleVoiceDetails = toggleVoiceDetails;
window.loadVoiceActivity = loadVoiceActivity;
window.loadCurrentVoiceMembers = loadCurrentVoiceMembers;
