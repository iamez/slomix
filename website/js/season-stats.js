/**
 * Season Statistics - Activity calendar and leader panels
 * @module season-stats
 */

import { API_BASE, fetchJSON, formatNumber } from './utils.js';

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
        container.innerHTML = '';

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
            if (!payload || !payload.player) return null;
            const row = document.createElement('div');
            row.className = 'flex items-center justify-between';
            const labelWrap = document.createElement('span');
            labelWrap.className = 'text-slate-400 flex items-center gap-2';
            const emoji = document.createElement('span');
            emoji.textContent = item.emoji;
            const label = document.createElement('span');
            label.textContent = item.label;
            labelWrap.appendChild(emoji);
            labelWrap.appendChild(label);

            const valueWrap = document.createElement('span');
            valueWrap.className = 'font-bold text-white';
            valueWrap.textContent = payload.player;
            const valueSub = document.createElement('span');
            valueSub.className = 'text-slate-400';
            valueSub.textContent = ` (${item.format(payload.value)})`;
            valueWrap.appendChild(valueSub);

            row.appendChild(labelWrap);
            row.appendChild(valueWrap);
            return row;
        };

        const panel = document.createElement('div');
        panel.className = 'space-y-3 text-sm';
        const primaryRows = primary.map(renderRow).filter(Boolean);
        const extraRows = extras.map(renderRow).filter(Boolean);
        const longest = leaders?.longest_session;
        if (primaryRows.length === 0) {
            const empty = document.createElement('div');
            empty.className = 'text-slate-500';
            empty.textContent = 'No season leaders yet.';
            panel.appendChild(empty);
        } else {
            primaryRows.forEach((row) => panel.appendChild(row));
        }

        if (extraRows.length > 0) {
            const extraWrap = document.createElement('div');
            extraWrap.className = 'border-t border-white/5 pt-3 space-y-2';
            extraRows.forEach((row) => extraWrap.appendChild(row));
            panel.appendChild(extraWrap);
        }

        if (longest && longest.rounds) {
            const longestWrap = document.createElement('div');
            longestWrap.className = 'border-t border-white/5 pt-3';
            const row = document.createElement('div');
            row.className = 'flex items-center justify-between';
            row.innerHTML = '<span class="text-slate-400 flex items-center gap-2"><span>🏁</span><span>Longest Session</span></span>';
            const value = document.createElement('span');
            value.className = 'font-bold text-white';
            value.textContent = longest.date || 'N/A';
            const rounds = document.createElement('span');
            rounds.className = 'text-slate-400';
            rounds.textContent = ` (${longest.rounds} rounds)`;
            value.appendChild(rounds);
            row.appendChild(value);
            longestWrap.appendChild(row);
            panel.appendChild(longestWrap);
        }

        container.appendChild(panel);
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
        container.innerHTML = '';
        const heading = document.createElement('div');
        heading.className = 'text-xs text-slate-500 mb-2';
        heading.textContent = `Last ${data?.days || 90} days`;
        const grid = document.createElement('div');
        grid.id = 'activity-grid';
        grid.className = 'text-xs text-slate-400';
        grid.textContent = 'Loading calendar...';
        container.appendChild(heading);
        container.appendChild(grid);

        // If we have Chart.js, render a proper heatmap
        // For now, show a simple text-based summary
        if (data && data.activity) {
            const totalRounds = Object.values(data.activity).reduce((a, b) => a + b, 0);
            const daysActive = Object.keys(data.activity).length;

            const windowDays = data.days || 90;
            if (grid) {
                grid.innerHTML = '';
                const summary = document.createElement('div');
                summary.className = 'space-y-2';
                const rows = [
                    ['Total Rounds', String(totalRounds)],
                    ['Days Active', String(daysActive)],
                    ['Avg Rounds/Day', (totalRounds / windowDays).toFixed(1)],
                ];
                rows.forEach(([label, value]) => {
                    const row = document.createElement('div');
                    row.className = 'flex justify-between';
                    const left = document.createElement('span');
                    left.textContent = label + ':';
                    const right = document.createElement('span');
                    right.className = 'font-bold text-white';
                    right.textContent = value;
                    row.appendChild(left);
                    row.appendChild(right);
                    summary.appendChild(row);
                });
                grid.appendChild(summary);
            }
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
