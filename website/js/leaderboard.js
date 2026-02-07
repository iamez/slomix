/**
 * Leaderboard module - leaderboard view and quick leaders widget
 * @module leaderboard
 */

import { API_BASE, fetchJSON, escapeHtml, escapeJsString, formatNumber } from './utils.js';

// Leaderboard state (match UI defaults: Games + Season)
let currentLbStat = 'games';
let currentLbPeriod = 'season';

// Navigation function (set by app.js)
let navigateToFn = null;

/**
 * Set navigation function reference
 */
export function setNavigateTo(fn) {
    navigateToFn = fn;
}

/**
 * Load main leaderboard table
 */
export async function loadLeaderboard() {
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
    if (typeof lucide !== 'undefined') lucide.createIcons();

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

            const displayName = row.name || row.guid || 'Unknown';
            const safeName = escapeHtml(displayName);
            const profileId = row.guid || row.name || 'unknown';
            const jsName = escapeJsString(profileId);
            const safeInitials = escapeHtml(displayName.substring(0, 2).toUpperCase());
            let valueText = row.value;
            if (currentLbStat === 'accuracy') {
                valueText = `${Number(row.value || 0).toFixed(1)}%`;
            } else if (currentLbStat === 'dpm') {
                valueText = Number(row.value || 0).toFixed(1);
            } else if (currentLbStat === 'kd') {
                valueText = Number(row.value || 0).toFixed(2);
            } else {
                valueText = formatNumber(row.value || 0);
            }
            const html = `
                <tr class="hover:bg-white/5 transition group">
                    <td class="px-6 py-4 font-mono text-slate-500">#${row.rank}</td>
                    <td class="px-6 py-4">
                        <div class="flex items-center gap-3">
                            <div class="w-8 h-8 rounded bg-slate-800 flex items-center justify-center text-xs font-bold text-slate-400 group-hover:text-white group-hover:bg-brand-blue transition">
                                ${safeInitials}
                            </div>
                            <span class="font-bold text-white cursor-pointer hover:underline" onclick="loadPlayerProfile('${jsName}')">${safeName}</span>
                        </div>
                    </td>
                    <td class="px-6 py-4 text-right font-mono ${valueClass}">${valueText}</td>
                    <td class="px-6 py-4 text-right text-slate-400">${row.rounds}</td>
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

/**
 * Update leaderboard filter (stat or period)
 */
export function updateLeaderboardFilter(type, value, options = {}) {
    if (type === 'stat') {
        currentLbStat = value;
        // Update UI buttons
        ['dpm', 'kills', 'kd', 'damage', 'headshots', 'accuracy', 'revives', 'gibs', 'games'].forEach(s => {
            const btn = document.getElementById(`btn-stat-${s}`);
            if (btn) {
                if (s === value) {
                    btn.className = 'px-4 py-2 rounded-md text-sm font-bold bg-brand-blue text-white shadow-lg transition';
                } else {
                    btn.className = 'px-4 py-2 rounded-md text-sm font-bold text-slate-400 hover:text-white transition';
                }
            }
        });
        // Update column header
        const colHeader = document.getElementById('lb-col-value');
        if (colHeader) {
            const labelMap = {
                dpm: 'DPM',
                kills: 'Kills',
                kd: 'K/D',
                damage: 'Damage',
                headshots: 'Headshots',
                accuracy: 'Accuracy (%)',
                revives: 'Revives',
                gibs: 'Gibs',
                games: 'Rounds'
            };
            colHeader.textContent = labelMap[value] || value.toUpperCase();
        }
    }

    if (type === 'period') {
        currentLbPeriod = value;
        // Update UI buttons
        ['7d', '30d', 'season', 'all'].forEach(p => {
            const btn = document.getElementById(`btn-period-${p}`);
            if (btn) {
                if (p === value) {
                    btn.className = 'px-4 py-2 rounded-md text-sm font-bold bg-brand-purple text-white shadow-lg transition';
                } else {
                    btn.className = 'px-4 py-2 rounded-md text-sm font-bold text-slate-400 hover:text-white transition';
                }
            }
        });
    }

    if (!options.skipLoad) {
        loadLeaderboard();
    }
}

// Initialize leaderboard with UI defaults (Games + Season)
export function initLeaderboardDefaults() {
    updateLeaderboardFilter('stat', currentLbStat, { skipLoad: true });
    updateLeaderboardFilter('period', currentLbPeriod, { skipLoad: true });
    loadLeaderboard();
}

/**
 * Load quick leaders sidebar widget
 */
export async function loadQuickLeaders() {
    try {
        const data = await fetchJSON(`${API_BASE}/stats/quick-leaders?limit=5`);
        const list = document.getElementById('quick-leaders-list');
        if (!list) return;

        list.innerHTML = '';
        if (data.errors && data.errors.length > 0) {
            const safeErrors = data.errors.map(err => escapeHtml(err)).join('<br>');
            list.insertAdjacentHTML(
                'beforeend',
                `<div class="text-[10px] text-brand-rose/80 uppercase tracking-[0.2em]">Data source errors</div>
                 <div class="text-xs text-slate-500">${safeErrors}</div>`
            );
        }

        const renderRow = (player, index, valueLabel, valueColor = 'text-brand-emerald') => {
            const rankColor = index === 0 ? 'text-brand-gold' : index === 1 ? 'text-slate-400' : 'text-brand-rose';
            const displayName = player.name || player.guid || 'Unknown';
            const safeInitials = escapeHtml(displayName.substring(0, 2).toUpperCase());
            const safeName = escapeHtml(displayName);
            const profileId = player.guid || player.name || 'unknown';
            const jsName = escapeJsString(profileId);
            const valueText = valueLabel === 'XP'
                ? `${formatNumber(player.value)} XP`
                : `${Math.round(player.value)} DPM`;

            return `
                <div class="flex items-center justify-between group cursor-pointer" onclick="loadPlayerProfile('${jsName}')">
                    <div class="flex items-center gap-3">
                        <div class="font-mono font-bold ${rankColor} text-sm">${player.rank}</div>
                        <div class="w-8 h-8 rounded bg-slate-800 flex items-center justify-center text-xs font-bold text-slate-400">${safeInitials}</div>
                        <div class="text-sm font-bold text-white group-hover:text-brand-blue transition">${safeName}</div>
                    </div>
                    <div class="text-sm font-mono font-bold ${valueColor}">${valueText}</div>
                </div>
            `;
        };

        const xpLeaders = data.xp || [];
        const dpmLeaders = data.dpm_sessions || [];
        const windowLabel = data.window_days ? `${data.window_days}d` : '7d';

        list.insertAdjacentHTML('beforeend', `
            <div class="text-[10px] uppercase tracking-[0.3em] text-slate-500">Top XP (${windowLabel})</div>
        `);
        if (xpLeaders.length === 0) {
            list.insertAdjacentHTML('beforeend', '<div class="text-xs text-slate-500">No XP data yet</div>');
        } else {
            xpLeaders.forEach((player, index) => {
                list.insertAdjacentHTML('beforeend', renderRow(player, index, 'XP', 'text-brand-amber'));
            });
        }

        list.insertAdjacentHTML('beforeend', `
            <div class="text-[10px] uppercase tracking-[0.3em] text-slate-500 mt-3">Top DPM/Session (${windowLabel})</div>
        `);
        if (dpmLeaders.length === 0) {
            list.insertAdjacentHTML('beforeend', '<div class="text-xs text-slate-500">No DPM data yet</div>');
        } else {
            dpmLeaders.forEach((player, index) => {
                list.insertAdjacentHTML('beforeend', renderRow(player, index, 'DPM', 'text-brand-emerald'));
            });
        }
    } catch (e) {
        console.error('Failed to load quick leaders:', e);
        const list = document.getElementById('quick-leaders-list');
        if (list) list.innerHTML = '<div class="text-center text-red-500 text-xs py-4">Failed to load</div>';
    }
}

/**
 * Load recent matches widget (home page sidebar)
 */
export async function loadRecentMatches() {
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
            const winnerTeam = match.winner;
            const team1Win = winnerTeam === 'Allies';
            const team2Win = winnerTeam === 'Axis';
            const sessionId = match.gaming_session_id || 0;
            const sessionPalette = ['bg-brand-blue', 'bg-brand-cyan', 'bg-brand-purple', 'bg-brand-amber', 'bg-brand-rose'];
            const sessionColor = sessionPalette[Math.abs(sessionId) % sessionPalette.length];

            // Format badge colors
            const formatColors = {
                '1v1': 'bg-purple-500/20 text-purple-400',
                '3v3': 'bg-brand-cyan/20 text-brand-cyan',
                '6v6': 'bg-brand-gold/20 text-brand-gold',
            };
            const formatClass = formatColors[match.format] || 'bg-slate-700 text-slate-400';

            // Team players (truncate if too many)
            const team1Names = (match.team1_players || []).slice(0, 3).map(p => escapeHtml(p)).join(' - ');
            const team2Names = (match.team2_players || []).slice(0, 3).map(p => escapeHtml(p)).join(' - ');
            const team1Overflow = (match.team1_players || []).length > 3 ? '...' : '';
            const team2Overflow = (match.team2_players || []).length > 3 ? '...' : '';

            const safeMapName = escapeHtml(match.map_name);
            const safeFormat = escapeHtml(match.format || '');
            const safeTimeAgo = escapeHtml(match.time_ago || '');
            const scoreDisplay = match.score_display ? escapeHtml(match.score_display) : '';
            const outcomeText = match.outcome ? escapeHtml(match.outcome) : '';
            const durationText = match.duration ? escapeHtml(match.duration) : '';
            const winnerText = match.winner ? escapeHtml(match.winner) : '';
            const matchId = match.id || match.round_id;
            const roundNumber = match.round_number ? `R${match.round_number}` : '';
            const sessionLabel = sessionId ? `Session ${sessionId}` : 'Session';

            const fallbackLine = (!scoreDisplay && (winnerText || durationText))
                ? `
                    <div class="flex items-center gap-2 text-[10px] mt-1 text-slate-500">
                        ${winnerText ? `<span>${winnerText}</span>` : ''}
                        ${durationText ? `<span>· ${durationText}</span>` : ''}
                    </div>
                  `
                : '';

            const html = `
            <div class="glass-card rounded-lg hover:bg-white/5 transition cursor-pointer group border-l-2 ${team1Win ? 'border-l-brand-blue' : team2Win ? 'border-l-brand-rose' : 'border-l-slate-600'}"
                 data-match-id="${matchId}">
                <div class="p-3">
                    <!-- Team 1 -->
                    <div class="flex items-center gap-1 text-xs mb-0.5 ${team1Win ? '' : 'opacity-60'}">
                        ${team1Win ? '<span class="text-brand-gold">🏆</span>' : ''}
                        <span class="text-slate-300 truncate">${team1Names}${team1Overflow}</span>
                    </div>
                    <!-- Team 2 -->
                    <div class="flex items-center gap-1 text-xs mb-2 ${team2Win ? '' : 'opacity-60'}">
                        ${team2Win ? '<span class="text-brand-gold">🏆</span>' : ''}
                        <span class="text-slate-300 truncate">${team2Names}${team2Overflow}</span>
                    </div>
                    <!-- Info row -->
                    <div class="flex items-center flex-wrap gap-2 text-[10px]">
                        <span class="inline-flex items-center gap-1 text-slate-500">
                            <span class="w-2 h-2 rounded-full ${sessionColor}"></span>
                            ${sessionLabel}
                        </span>
                        <span class="text-slate-500 truncate">${safeMapName}</span>
                        ${roundNumber ? `<span class="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 font-bold">${roundNumber}</span>` : ''}
                        <span class="px-1.5 py-0.5 rounded ${formatClass} font-bold">${safeFormat}</span>
                        <span class="text-slate-600">${safeTimeAgo}</span>
                    </div>
                    ${scoreDisplay || outcomeText ? `
                    <div class="flex items-center gap-2 text-[10px] mt-1">
                        ${scoreDisplay ? `<span class="text-slate-400">${scoreDisplay}</span>` : ''}
                        ${outcomeText ? `<span class="text-slate-600">${outcomeText}</span>` : ''}
                    </div>
                    ` : ''}
                    ${fallbackLine}
                </div>
            </div>
            `;
            list.insertAdjacentHTML('beforeend', html);
        });

        // Add click handlers using event delegation
        list.querySelectorAll('[data-match-id]').forEach(card => {
            card.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                
                try {
                    const matchId = card.dataset.matchId;
                    console.log('[Recent Matches] Card clicked, matchId:', matchId);
                    
                    if (!matchId) {
                        console.error('[Recent Matches] No matchId in dataset!');
                        return;
                    }
                    
                    if (typeof window.loadMatchDetails === 'function') {
                        console.log('[Recent Matches] Calling loadMatchDetails...');
                        window.loadMatchDetails(parseInt(matchId, 10));
                    } else {
                        console.error('[Recent Matches] loadMatchDetails is not available on window!');
                        console.log('[Recent Matches] window.loadMatchDetails =', window.loadMatchDetails);
                        alert('Error: Match details function not loaded. Please refresh the page.');
                    }
                } catch (err) {
                    console.error('[Recent Matches] Error in click handler:', err);
                }
            });
        });
    } catch (e) {
        console.error('Failed to load matches:', e);
        const list = document.getElementById('recent-matches-list');
        if (list) list.innerHTML = '<div class="text-center text-red-500 py-4">Failed to load matches</div>';
    }
}

// Expose to window for onclick handlers in HTML
window.loadLeaderboard = loadLeaderboard;
window.updateLeaderboardFilter = updateLeaderboardFilter;
