/**
 * Season Statistics - Activity calendar and leader panels
 * @module season-stats
 */

import { API_BASE, fetchJSON, escapeHtml, formatNumber } from './utils.js';

function formatDuration(seconds) {
    const total = Number(seconds || 0);
    if (!total || total < 0) return '--';
    const mins = Math.floor(total / 60);
    const hrs = Math.floor(mins / 60);
    const remMins = mins % 60;
    if (hrs > 0) return `${hrs}h ${remMins}m`;
    return `${remMins}m`;
}


/**
 * Load season leaders panel
 */
export async function loadSeasonLeaders() {
    try {
        const data = await fetchJSON(`${API_BASE}/seasons/current/leaders`);
        const container = document.getElementById('season-leaders-panel');
        if (!container) return;

        const leaders = data.leaders;

        const primary = [
            { key: 'kills', label: 'Kills', emoji: '⚔️', format: v => formatNumber(v) },
            { key: 'dpm', label: 'DPM', emoji: '🔥', format: v => Number(v).toFixed(1) },
            { key: 'xp', label: 'XP', emoji: '✨', format: v => formatNumber(v) },
            { key: 'revives', label: 'Revives', emoji: '💉', format: v => formatNumber(v) },
            { key: 'gibs', label: 'Gibs', emoji: '💀', format: v => formatNumber(v) },
            { key: 'objectives', label: 'Objectives', emoji: '🎯', format: v => formatNumber(v) },
            { key: 'time_alive', label: 'Time Alive', emoji: '⏱️', format: v => formatDuration(v) },
            { key: 'time_dead', label: 'Time Dead', emoji: '🕳️', format: v => formatDuration(v * 60) },
        ];

        const extras = [
            { key: 'damage_given', label: 'Damage Given', emoji: '💥', format: v => `${(v / 1000).toFixed(1)}k` },
            { key: 'damage_received', label: 'Damage Taken', emoji: '🛡️', format: v => `${(v / 1000).toFixed(1)}k` },
            { key: 'team_damage', label: 'Team Damage', emoji: '⚠️', format: v => `${(v / 1000).toFixed(1)}k` },
            { key: 'deaths', label: 'Deaths', emoji: '☠️', format: v => formatNumber(v) },
        ];

        const renderRow = (item) => {
            const payload = leaders?.[item.key];
            if (!payload || !payload.player) return '';
            return `
                <div class="flex items-center justify-between">
                    <span class="text-slate-400 flex items-center gap-2">
                        <span>${item.emoji}</span>
                        <span>${item.label}</span>
                    </span>
                    <span class="font-bold text-white">
                        ${escapeHtml(payload.player)}
                        <span class="text-slate-400">(${item.format(payload.value)})</span>
                    </span>
                </div>
            `;
        };

        const primaryRows = primary.map(renderRow).filter(Boolean).join('');
        const extraRows = extras.map(renderRow).filter(Boolean).join('');
        const longest = leaders?.longest_session;
        const longestRow = longest && longest.rounds
            ? `
                <div class="flex items-center justify-between">
                    <span class="text-slate-400 flex items-center gap-2">
                        <span>🏁</span>
                        <span>Longest Session</span>
                    </span>
                    <span class="font-bold text-white">
                        ${longest.date ? escapeHtml(longest.date) : 'N/A'}
                        <span class="text-slate-400">(${longest.rounds} rounds)</span>
                    </span>
                </div>
              `
            : '';

        const html = `
            <div class="space-y-3 text-sm">
                ${primaryRows || '<div class="text-slate-500">No season leaders yet.</div>'}
                ${extraRows ? `<div class="border-t border-white/5 pt-3 space-y-2">${extraRows}</div>` : ''}
                ${longestRow ? `<div class="border-t border-white/5 pt-3">${longestRow}</div>` : ''}
            </div>
        `;

        container.innerHTML = html;
    } catch (e) {
        console.error('Failed to load season leaders:', e);
    }
}

export async function loadSeasonSummary() {
    try {
        const data = await fetchJSON(`${API_BASE}/seasons/current/summary`);
        const totals = data.totals || {};

        const playersEl = document.getElementById('season-players');
        const roundsEl = document.getElementById('season-rounds');
        const mapsEl = document.getElementById('season-maps');
        const sessionsEl = document.getElementById('season-sessions');
        const killsEl = document.getElementById('season-kills');
        const daysEl = document.getElementById('season-active-days');
        const avgEl = document.getElementById('season-avg-rounds');
        const topMapEl = document.getElementById('season-top-map');

        if (playersEl) playersEl.textContent = formatNumber(totals.players || 0);
        if (roundsEl) roundsEl.textContent = formatNumber(totals.rounds || 0);
        if (mapsEl) mapsEl.textContent = formatNumber(totals.maps || 0);
        if (sessionsEl) sessionsEl.textContent = formatNumber(totals.sessions || 0);
        if (killsEl) killsEl.textContent = formatNumber(totals.kills || 0);
        if (daysEl) daysEl.textContent = formatNumber(totals.active_days || 0);
        if (avgEl) avgEl.textContent = totals.avg_rounds_per_day != null ? totals.avg_rounds_per_day : '--';

        if (topMapEl) {
            const topMap = data.top_map?.name;
            const plays = data.top_map?.plays;
            topMapEl.textContent = topMap ? `${topMap} (${plays} plays)` : '--';
        }
    } catch (e) {
        console.error('Failed to load season summary:', e);
    }
}

/**
 * Load activity calendar (GitHub-style heatmap)
 */
export async function loadActivityCalendar() {
    try {
        // Query rounds by date for the last 90 days
        const data = await fetchJSON(`${API_BASE}/stats/activity-calendar?days=90`);
        const container = document.getElementById('season-calendar-panel');
        if (!container) return;

        // Create a simple heatmap using CSS grid
        const html = `
            <div class="text-xs text-slate-500 mb-2">Last ${data?.days || 90} days</div>
            <div id="activity-grid" class="text-xs text-slate-400">Loading calendar...</div>
        `;

        container.innerHTML = html;

        // If we have Chart.js, render a proper heatmap
        // For now, show a simple text-based summary
        if (data && data.activity) {
            const grid = document.getElementById('activity-grid');
            const totalRounds = Object.values(data.activity).reduce((a, b) => a + b, 0);
            const daysActive = Object.keys(data.activity).length;

            const windowDays = data.days || 90;
            grid.innerHTML = `
                <div class="space-y-2">
                    <div class="flex justify-between">
                        <span>Total Rounds:</span>
                        <span class="font-bold text-white">${totalRounds}</span>
                    </div>
                    <div class="flex justify-between">
                        <span>Days Active:</span>
                        <span class="font-bold text-white">${daysActive}</span>
                    </div>
                    <div class="flex justify-between">
                        <span>Avg Rounds/Day:</span>
                        <span class="font-bold text-white">${(totalRounds / windowDays).toFixed(1)}</span>
                    </div>
                </div>
            `;
        }
    } catch (e) {
        console.error('Failed to load activity calendar:', e);
        // Endpoint might not exist yet, that's okay
    }
}

// Expose to window
if (typeof window !== 'undefined') {
    window.loadSeasonLeaders = loadSeasonLeaders;
    window.loadActivityCalendar = loadActivityCalendar;
    window.loadSeasonSummary = loadSeasonSummary;
}
