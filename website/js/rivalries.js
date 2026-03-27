/**
 * Player Rivalries module (legacy)
 * Nemesis / Prey / Rival detection + H2H breakdown
 * @module rivalries
 */

import { API_BASE, fetchJSON, escapeHtml } from './utils.js';

function stripEtColors(text) {
    if (!text) return '';
    return String(text).replace(/\^[0-9A-Za-z]/g, '');
}

const CLASSIFICATION_STYLES = {
    NEMESIS:            { icon: '\u2620\uFE0F', label: 'Nemesis',   bg: 'bg-red-500/20',    border: 'border-red-500/40',    text: 'text-red-400' },
    PREY:               { icon: '\uD83C\uDFAF', label: 'Prey',      bg: 'bg-emerald-500/20', border: 'border-emerald-500/40', text: 'text-emerald-400' },
    RIVAL:              { icon: '\u2694\uFE0F', label: 'Rival',     bg: 'bg-amber-500/20',  border: 'border-amber-500/40',  text: 'text-amber-400' },
    CONTENDER:          { icon: '\uD83E\uDD4A', label: 'Contender', bg: 'bg-blue-500/20',   border: 'border-blue-500/40',   text: 'text-blue-400' },
    INSUFFICIENT_DATA:  { icon: '\u2753',       label: 'Too Few',   bg: 'bg-slate-500/20',  border: 'border-slate-500/40',  text: 'text-slate-400' },
};

let rivalriesLoadId = 0;

const state = {
    players: [],
    selectedGuid: null,
    rivalryData: null,
    h2hData: null,
    loading: false,
};

// ── Player list loading ──────────────────────────────────────

async function loadPlayerList() {
    try {
        const data = await fetchJSON(`${API_BASE}/rivalries/leaderboard?limit=100`);
        if (data.status !== 'ok') return;
        // Collect unique players from pairs
        const seen = new Set();
        const players = [];
        for (const p of data.pairs) {
            if (!seen.has(p.guid1)) {
                seen.add(p.guid1);
                players.push({ guid: p.guid1, name: p.name1 });
            }
            if (!seen.has(p.guid2)) {
                seen.add(p.guid2);
                players.push({ guid: p.guid2, name: p.name2 });
            }
        }
        players.sort((a, b) => a.name.localeCompare(b.name));
        state.players = players;
        renderPlayerSelect();
    } catch (err) {
        console.error('Failed to load player list:', err);
    }
}

function renderPlayerSelect() {
    const select = document.getElementById('rivalries-player-select');
    if (!select) return;

    select.innerHTML = '<option value="">-- Select Player --</option>';
    for (const p of state.players) {
        const opt = document.createElement('option');
        opt.value = p.guid;
        opt.textContent = stripEtColors(p.name);
        select.appendChild(opt);
    }
}

// ── Main view loader ─────────────────────────────────────────

export async function loadRivalriesView() {
    const loadId = ++rivalriesLoadId;
    const container = document.getElementById('rivalries-content');
    if (!container) return;

    container.innerHTML = '<div class="text-center text-slate-400 py-12">Loading rivalries...</div>';

    // Load leaderboard + player list in parallel
    await Promise.all([loadPlayerList(), loadLeaderboard(container, loadId)]);
}

// ── Leaderboard ──────────────────────────────────────────────

async function loadLeaderboard(container, loadId) {
    try {
        const data = await fetchJSON(`${API_BASE}/rivalries/leaderboard?limit=20`);
        if (loadId !== rivalriesLoadId) return;
        if (data.status !== 'ok') {
            container.innerHTML = '<div class="text-center text-red-400 py-8">Failed to load rivalries</div>';
            return;
        }
        renderLeaderboard(container, data.pairs);
    } catch (err) {
        if (loadId !== rivalriesLoadId) return;
        container.innerHTML = `<div class="text-center text-red-400 py-8">${escapeHtml(err.message)}</div>`;
    }
}

function renderLeaderboard(container, pairs) {
    if (!pairs.length) {
        container.innerHTML = '<div class="text-center text-slate-400 py-8">No rivalry data yet</div>';
        return;
    }

    const rows = pairs.map((p, i) => {
        const style = CLASSIFICATION_STYLES[p.classification] || CLASSIFICATION_STYLES.INSUFFICIENT_DATA;
        const total = p.total;
        const p1Pct = total > 0 ? Math.round((p.kills_1to2 / total) * 100) : 50;
        const p2Pct = 100 - p1Pct;
        return `
        <tr class="border-b border-white/5 hover:bg-white/5 cursor-pointer transition"
            data-guid1="${escapeHtml(p.guid1)}" data-guid2="${escapeHtml(p.guid2)}">
            <td class="py-3 px-4 text-slate-500 text-sm">${i + 1}</td>
            <td class="py-3 px-4">
                <span class="text-white font-bold text-sm">${escapeHtml(p.name1)}</span>
            </td>
            <td class="py-3 px-4 text-center text-xs text-slate-400">vs</td>
            <td class="py-3 px-4">
                <span class="text-white font-bold text-sm">${escapeHtml(p.name2)}</span>
            </td>
            <td class="py-3 px-4 text-center">
                <div class="flex items-center gap-2 justify-center">
                    <span class="text-emerald-400 font-mono text-sm">${p.kills_1to2}</span>
                    <div class="w-24 h-2 bg-slate-700 rounded-full overflow-hidden flex">
                        <div class="bg-emerald-500 h-full" style="width:${p1Pct}%"></div>
                        <div class="bg-red-500 h-full" style="width:${p2Pct}%"></div>
                    </div>
                    <span class="text-red-400 font-mono text-sm">${p.kills_2to1}</span>
                </div>
            </td>
            <td class="py-3 px-4 text-center font-mono text-white text-sm">${total}</td>
            <td class="py-3 px-4 text-center">
                <span class="px-2 py-0.5 rounded text-xs font-bold ${style.bg} ${style.border} ${style.text} border">
                    ${style.icon} ${style.label}
                </span>
            </td>
        </tr>`;
    }).join('');

    container.innerHTML = `
    <div class="glass-panel rounded-xl border border-white/10 overflow-hidden">
        <div class="px-6 py-4 border-b border-white/10">
            <h3 class="text-lg font-black text-white">Top Rivalries</h3>
            <p class="text-xs text-slate-400 mt-1">Ranked by total encounters. Click any pair for H2H details.</p>
        </div>
        <div class="overflow-x-auto">
            <table class="w-full">
                <thead>
                    <tr class="border-b border-white/10 text-xs text-slate-500 uppercase tracking-wider">
                        <th class="py-2 px-4 text-left">#</th>
                        <th class="py-2 px-4 text-left">Player 1</th>
                        <th class="py-2 px-4"></th>
                        <th class="py-2 px-4 text-left">Player 2</th>
                        <th class="py-2 px-4 text-center">Score</th>
                        <th class="py-2 px-4 text-center">Total</th>
                        <th class="py-2 px-4 text-center">Type</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>
    </div>`;

    // Attach click handlers
    container.querySelectorAll('tr[data-guid1]').forEach(tr => {
        tr.addEventListener('click', () => {
            const g1 = tr.dataset.guid1;
            const g2 = tr.dataset.guid2;
            loadH2HDetail(g1, g2);
        });
    });
}

// ── Player Rivalries ─────────────────────────────────────────

async function loadPlayerRivalries(guid) {
    const panel = document.getElementById('rivalries-player-panel');
    if (!panel) return;

    state.selectedGuid = guid;
    panel.innerHTML = '<div class="text-center text-slate-400 py-8">Loading...</div>';
    panel.classList.remove('hidden');

    try {
        const data = await fetchJSON(`${API_BASE}/rivalries/player/${encodeURIComponent(guid)}`);
        if (data.status !== 'ok') {
            panel.innerHTML = '<div class="text-red-400 text-center py-8">Failed to load</div>';
            return;
        }
        state.rivalryData = data;
        renderPlayerRivalries(panel, data);
    } catch (err) {
        panel.innerHTML = `<div class="text-red-400 text-center py-8">${escapeHtml(err.message)}</div>`;
    }
}

function renderPlayerRivalries(panel, data) {
    const cards = [
        { key: 'nemesis', title: 'Nemesis', subtitle: 'Dominates you', pair: data.nemesis },
        { key: 'prey', title: 'Prey', subtitle: 'You dominate', pair: data.prey },
        { key: 'rival', title: 'Rival', subtitle: 'Evenly matched', pair: data.rival },
    ];

    const cardsHtml = cards.map(c => {
        if (!c.pair) {
            return `
            <div class="glass-panel rounded-xl border border-white/10 p-4 opacity-50">
                <div class="text-xs text-slate-500 uppercase tracking-wider mb-1">${c.title}</div>
                <div class="text-sm text-slate-400">No ${c.title.toLowerCase()} found</div>
                <div class="text-[10px] text-slate-600 mt-1">${c.subtitle}</div>
            </div>`;
        }
        const style = CLASSIFICATION_STYLES[c.pair.classification] || CLASSIFICATION_STYLES.INSUFFICIENT_DATA;
        return `
        <div class="glass-panel rounded-xl border ${style.border} p-4 cursor-pointer hover:bg-white/5 transition rivalries-h2h-link"
             data-opponent-guid="${escapeHtml(c.pair.opponent_guid)}">
            <div class="text-xs ${style.text} uppercase tracking-wider mb-1">${style.icon} ${c.title}</div>
            <div class="text-lg font-black text-white">${escapeHtml(c.pair.opponent_name)}</div>
            <div class="text-[10px] text-slate-500 mt-1">${c.subtitle}</div>
            <div class="flex items-center gap-3 mt-3">
                <div class="text-sm">
                    <span class="text-emerald-400 font-mono">${c.pair.kills_by_player}</span>
                    <span class="text-slate-600 mx-1">-</span>
                    <span class="text-red-400 font-mono">${c.pair.kills_on_player}</span>
                </div>
                <div class="text-xs text-slate-500">${c.pair.total_encounters} encounters</div>
            </div>
            <div class="mt-2 w-full h-1.5 bg-slate-700 rounded-full overflow-hidden flex">
                <div class="bg-emerald-500 h-full" style="width:${Math.round(c.pair.win_rate * 100)}%"></div>
                <div class="bg-red-500 h-full" style="width:${100 - Math.round(c.pair.win_rate * 100)}%"></div>
            </div>
        </div>`;
    }).join('');

    // All pairs table
    const pairsRows = (data.all_pairs || []).slice(0, 20).map(p => {
        const style = CLASSIFICATION_STYLES[p.classification] || CLASSIFICATION_STYLES.INSUFFICIENT_DATA;
        return `
        <tr class="border-b border-white/5 hover:bg-white/5 cursor-pointer transition rivalries-h2h-link"
            data-opponent-guid="${escapeHtml(p.opponent_guid)}">
            <td class="py-2 px-3 text-white text-sm font-bold">${escapeHtml(p.opponent_name)}</td>
            <td class="py-2 px-3 text-center text-emerald-400 font-mono text-sm">${p.kills_by_player}</td>
            <td class="py-2 px-3 text-center text-red-400 font-mono text-sm">${p.kills_on_player}</td>
            <td class="py-2 px-3 text-center text-white font-mono text-sm">${p.total_encounters}</td>
            <td class="py-2 px-3 text-center text-sm">${Math.round(p.win_rate * 100)}%</td>
            <td class="py-2 px-3 text-center">
                <span class="px-1.5 py-0.5 rounded text-[10px] font-bold ${style.bg} ${style.text}">${style.label}</span>
            </td>
        </tr>`;
    }).join('');

    panel.innerHTML = `
    <div class="mb-4">
        <h3 class="text-lg font-black text-white">${escapeHtml(data.player_name)}'s Rivalries</h3>
        <p class="text-xs text-slate-400">${data.total_opponents} opponents found</p>
    </div>
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">${cardsHtml}</div>
    ${pairsRows ? `
    <div class="glass-panel rounded-xl border border-white/10 overflow-hidden">
        <div class="px-4 py-3 border-b border-white/10">
            <h4 class="text-sm font-bold text-white">All Opponents</h4>
        </div>
        <div class="overflow-x-auto">
            <table class="w-full">
                <thead>
                    <tr class="border-b border-white/10 text-[10px] text-slate-500 uppercase tracking-wider">
                        <th class="py-2 px-3 text-left">Opponent</th>
                        <th class="py-2 px-3 text-center">Kills</th>
                        <th class="py-2 px-3 text-center">Deaths</th>
                        <th class="py-2 px-3 text-center">Total</th>
                        <th class="py-2 px-3 text-center">Win%</th>
                        <th class="py-2 px-3 text-center">Type</th>
                    </tr>
                </thead>
                <tbody>${pairsRows}</tbody>
            </table>
        </div>
    </div>` : ''}`;

    // Attach H2H click handlers
    panel.querySelectorAll('.rivalries-h2h-link').forEach(el => {
        el.addEventListener('click', () => {
            loadH2HDetail(data.player_guid, el.dataset.opponentGuid);
        });
    });
}

// ── H2H Detail ───────────────────────────────────────────────

async function loadH2HDetail(guid1, guid2) {
    const panel = document.getElementById('rivalries-h2h-panel');
    if (!panel) return;

    panel.innerHTML = '<div class="text-center text-slate-400 py-8">Loading H2H...</div>';
    panel.classList.remove('hidden');

    try {
        const data = await fetchJSON(`${API_BASE}/rivalries/h2h/${encodeURIComponent(guid1)}/${encodeURIComponent(guid2)}`);
        if (data.status !== 'ok') {
            panel.innerHTML = '<div class="text-red-400 text-center py-8">Failed to load H2H</div>';
            return;
        }
        state.h2hData = data;
        renderH2HDetail(panel, data);
    } catch (err) {
        panel.innerHTML = `<div class="text-red-400 text-center py-8">${escapeHtml(err.message)}</div>`;
    }
}

function renderH2HDetail(panel, data) {
    const style = CLASSIFICATION_STYLES[data.classification] || CLASSIFICATION_STYLES.INSUFFICIENT_DATA;
    const total = data.total;
    const p1Pct = total > 0 ? Math.round((data.p1_kills / total) * 100) : 50;

    // Weapon bars helper
    function weaponBars(weapons, color) {
        if (!weapons.length) return '<div class="text-xs text-slate-500">No kills</div>';
        const maxKills = weapons[0].kills;
        return weapons.slice(0, 6).map(w => {
            const pct = maxKills > 0 ? Math.round((w.kills / maxKills) * 100) : 0;
            return `
            <div class="flex items-center gap-2 mb-1">
                <div class="w-20 text-xs text-slate-300 truncate">${escapeHtml(w.weapon)}</div>
                <div class="flex-1 h-3 bg-slate-700 rounded-full overflow-hidden">
                    <div class="h-full ${color} rounded-full" style="width:${pct}%"></div>
                </div>
                <div class="w-8 text-xs text-slate-400 text-right font-mono">${w.kills}</div>
            </div>`;
        }).join('');
    }

    // Per-map table
    const mapRows = (data.per_map || []).map(m => `
        <tr class="border-b border-white/5">
            <td class="py-1.5 px-3 text-white text-sm">${escapeHtml(m.map)}</td>
            <td class="py-1.5 px-3 text-center text-emerald-400 font-mono text-sm">${m.p1_kills}</td>
            <td class="py-1.5 px-3 text-center text-red-400 font-mono text-sm">${m.p2_kills}</td>
            <td class="py-1.5 px-3 text-center text-white font-mono text-sm">${m.total}</td>
        </tr>`).join('');

    panel.innerHTML = `
    <div class="glass-panel rounded-xl border ${style.border} p-6 mb-4">
        <!-- Header -->
        <div class="flex items-center justify-between mb-4">
            <button id="rivalries-h2h-close" class="text-xs text-slate-400 hover:text-white transition">&larr; Back</button>
            <span class="px-2 py-0.5 rounded text-xs font-bold ${style.bg} ${style.border} ${style.text} border">
                ${style.icon} ${style.label}
            </span>
        </div>

        <!-- Score -->
        <div class="text-center mb-6">
            <div class="flex items-center justify-center gap-6">
                <div>
                    <div class="text-2xl font-black text-white">${escapeHtml(data.p1_name)}</div>
                    <div class="text-3xl font-black text-emerald-400 mt-1">${data.p1_kills}</div>
                </div>
                <div class="text-slate-500 text-2xl font-bold">vs</div>
                <div>
                    <div class="text-2xl font-black text-white">${escapeHtml(data.p2_name)}</div>
                    <div class="text-3xl font-black text-red-400 mt-1">${data.p2_kills}</div>
                </div>
            </div>
            <div class="mt-3 max-w-sm mx-auto">
                <div class="w-full h-3 bg-slate-700 rounded-full overflow-hidden flex">
                    <div class="bg-emerald-500 h-full transition-all" style="width:${p1Pct}%"></div>
                    <div class="bg-red-500 h-full transition-all" style="width:${100 - p1Pct}%"></div>
                </div>
                <div class="flex justify-between mt-1 text-xs text-slate-400">
                    <span>${p1Pct}%</span>
                    <span>${total} total encounters</span>
                    <span>${100 - p1Pct}%</span>
                </div>
            </div>
        </div>

        <!-- Weapons -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
            <div>
                <h4 class="text-xs text-emerald-400 uppercase tracking-wider font-bold mb-2">${escapeHtml(data.p1_name)}'s Weapons</h4>
                ${weaponBars(data.p1_weapons || [], 'bg-emerald-500')}
            </div>
            <div>
                <h4 class="text-xs text-red-400 uppercase tracking-wider font-bold mb-2">${escapeHtml(data.p2_name)}'s Weapons</h4>
                ${weaponBars(data.p2_weapons || [], 'bg-red-500')}
            </div>
        </div>

        <!-- Per Map -->
        ${mapRows ? `
        <div>
            <h4 class="text-xs text-slate-400 uppercase tracking-wider font-bold mb-2">Per Map</h4>
            <div class="overflow-x-auto">
                <table class="w-full">
                    <thead>
                        <tr class="border-b border-white/10 text-[10px] text-slate-500 uppercase tracking-wider">
                            <th class="py-1 px-3 text-left">Map</th>
                            <th class="py-1 px-3 text-center">${escapeHtml(data.p1_name)}</th>
                            <th class="py-1 px-3 text-center">${escapeHtml(data.p2_name)}</th>
                            <th class="py-1 px-3 text-center">Total</th>
                        </tr>
                    </thead>
                    <tbody>${mapRows}</tbody>
                </table>
            </div>
        </div>` : ''}
    </div>`;

    // Back button
    document.getElementById('rivalries-h2h-close')?.addEventListener('click', () => {
        panel.innerHTML = '';
        panel.classList.add('hidden');
    });
}

// ── Init: wire up select ─────────────────────────────────────

function initRivalriesListeners() {
    const select = document.getElementById('rivalries-player-select');
    if (select) {
        select.addEventListener('change', (e) => {
            const guid = e.target.value;
            if (guid) {
                loadPlayerRivalries(guid);
            } else {
                const panel = document.getElementById('rivalries-player-panel');
                if (panel) { panel.innerHTML = ''; panel.classList.add('hidden'); }
            }
        });
    }
}

// Auto-init when module loads
document.addEventListener('DOMContentLoaded', initRivalriesListeners);
// Also try immediately (for SPA navigation after DOMContentLoaded)
if (document.readyState !== 'loading') {
    setTimeout(initRivalriesListeners, 0);
}
