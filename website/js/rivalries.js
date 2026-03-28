/**
 * Player Rivalries module (legacy)
 * Nemesis / Prey / Rival detection + H2H breakdown
 * @module rivalries
 */

import { API_BASE, fetchJSON } from './utils.js';

function stripEtColors(text) {
    if (!text) return '';
    return String(text).replace(/\^[0-9A-Za-z]/g, '');
}

/** Safe DOM element factory. Strings become text nodes; null/undefined children are skipped. */
function _el(tag, className, ...children) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    for (const c of children) {
        if (c == null) continue;
        el.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    }
    return el;
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

    select.textContent = '';
    const defaultOpt = document.createElement('option');
    defaultOpt.value = '';
    defaultOpt.textContent = '-- Select Player --';
    select.appendChild(defaultOpt);

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

    container.textContent = '';
    container.appendChild(_el('div', 'text-center text-slate-400 py-12', 'Loading rivalries...'));

    // Load leaderboard + player list in parallel
    await Promise.all([loadPlayerList(), loadLeaderboard(container, loadId)]);
}

// ── Leaderboard ──────────────────────────────────────────────

async function loadLeaderboard(container, loadId) {
    try {
        const data = await fetchJSON(`${API_BASE}/rivalries/leaderboard?limit=20`);
        if (loadId !== rivalriesLoadId) return;
        if (data.status !== 'ok') {
            container.textContent = '';
            container.appendChild(_el('div', 'text-center text-red-400 py-8', 'Failed to load rivalries'));
            return;
        }
        renderLeaderboard(container, data.pairs);
    } catch (err) {
        if (loadId !== rivalriesLoadId) return;
        container.textContent = '';
        container.appendChild(_el('div', 'text-center text-red-400 py-8', err.message));
    }
}

function renderLeaderboard(container, pairs) {
    if (!pairs.length) {
        container.textContent = '';
        container.appendChild(_el('div', 'text-center text-slate-400 py-8', 'No rivalry data yet'));
        return;
    }

    container.textContent = '';

    const panel = _el('div', 'glass-panel rounded-xl border border-white/10 overflow-hidden');

    // Header
    const headerDiv = _el('div', 'px-6 py-4 border-b border-white/10',
        _el('h3', 'text-lg font-black text-white', 'Top Rivalries'),
        _el('p', 'text-xs text-slate-400 mt-1', 'Ranked by total encounters. Click any pair for H2H details.')
    );
    panel.appendChild(headerDiv);

    // Table
    const tableWrap = _el('div', 'overflow-x-auto');
    const table = document.createElement('table');
    table.className = 'w-full';

    // Thead
    const thead = document.createElement('thead');
    const thRow = _el('tr', 'border-b border-white/10 text-xs text-slate-500 uppercase tracking-wider');
    [
        { text: '#', cls: 'py-2 px-4 text-left' },
        { text: 'Player 1', cls: 'py-2 px-4 text-left' },
        { text: '', cls: 'py-2 px-4' },
        { text: 'Player 2', cls: 'py-2 px-4 text-left' },
        { text: 'Score', cls: 'py-2 px-4 text-center' },
        { text: 'Total', cls: 'py-2 px-4 text-center' },
        { text: 'Type', cls: 'py-2 px-4 text-center' },
    ].forEach(th => {
        const thEl = document.createElement('th');
        thEl.className = th.cls;
        thEl.textContent = th.text;
        thRow.appendChild(thEl);
    });
    thead.appendChild(thRow);
    table.appendChild(thead);

    // Tbody
    const tbody = document.createElement('tbody');
    pairs.forEach((p, i) => {
        const style = CLASSIFICATION_STYLES[p.classification] || CLASSIFICATION_STYLES.INSUFFICIENT_DATA;
        const total = p.total;
        const p1Pct = total > 0 ? Math.round((p.kills_1to2 / total) * 100) : 50;
        const p2Pct = 100 - p1Pct;

        const tr = document.createElement('tr');
        tr.className = 'border-b border-white/5 hover:bg-white/5 cursor-pointer transition';
        tr.dataset.guid1 = p.guid1;
        tr.dataset.guid2 = p.guid2;

        // Rank
        tr.appendChild(_el('td', 'py-3 px-4 text-slate-500 text-sm', String(i + 1)));

        // Player 1
        const td2 = document.createElement('td');
        td2.className = 'py-3 px-4';
        td2.appendChild(_el('span', 'text-white font-bold text-sm', p.name1));
        tr.appendChild(td2);

        // vs
        tr.appendChild(_el('td', 'py-3 px-4 text-center text-xs text-slate-400', 'vs'));

        // Player 2
        const td4 = document.createElement('td');
        td4.className = 'py-3 px-4';
        td4.appendChild(_el('span', 'text-white font-bold text-sm', p.name2));
        tr.appendChild(td4);

        // Score bar
        const td5 = document.createElement('td');
        td5.className = 'py-3 px-4 text-center';
        const scoreRow = _el('div', 'flex items-center gap-2 justify-center');
        scoreRow.appendChild(_el('span', 'text-emerald-400 font-mono text-sm', String(p.kills_1to2)));

        const barTrack = _el('div', 'w-24 h-2 bg-slate-700 rounded-full overflow-hidden flex');
        const bar1 = _el('div', 'bg-emerald-500 h-full');
        bar1.style.width = `${p1Pct}%`;
        const bar2 = _el('div', 'bg-red-500 h-full');
        bar2.style.width = `${p2Pct}%`;
        barTrack.appendChild(bar1);
        barTrack.appendChild(bar2);
        scoreRow.appendChild(barTrack);

        scoreRow.appendChild(_el('span', 'text-red-400 font-mono text-sm', String(p.kills_2to1)));
        td5.appendChild(scoreRow);
        tr.appendChild(td5);

        // Total
        tr.appendChild(_el('td', 'py-3 px-4 text-center font-mono text-white text-sm', String(total)));

        // Type badge
        const td7 = document.createElement('td');
        td7.className = 'py-3 px-4 text-center';
        td7.appendChild(_el('span', `px-2 py-0.5 rounded text-xs font-bold ${style.bg} ${style.border} ${style.text} border`, `${style.icon} ${style.label}`));
        tr.appendChild(td7);

        tr.addEventListener('click', () => loadH2HDetail(p.guid1, p.guid2));
        tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    tableWrap.appendChild(table);
    panel.appendChild(tableWrap);
    container.appendChild(panel);
}

// ── Player Rivalries ─────────────────────────────────────────

async function loadPlayerRivalries(guid) {
    const panel = document.getElementById('rivalries-player-panel');
    if (!panel) return;

    state.selectedGuid = guid;
    panel.textContent = '';
    panel.appendChild(_el('div', 'text-center text-slate-400 py-8', 'Loading...'));
    panel.classList.remove('hidden');

    try {
        const data = await fetchJSON(`${API_BASE}/rivalries/player/${encodeURIComponent(guid)}`);
        if (data.status !== 'ok') {
            panel.textContent = '';
            panel.appendChild(_el('div', 'text-red-400 text-center py-8', 'Failed to load'));
            return;
        }
        state.rivalryData = data;
        renderPlayerRivalries(panel, data);
    } catch (err) {
        panel.textContent = '';
        panel.appendChild(_el('div', 'text-red-400 text-center py-8', err.message));
    }
}

function renderPlayerRivalries(panel, data) {
    panel.textContent = '';

    // Header
    panel.appendChild(_el('div', 'mb-4',
        _el('h3', 'text-lg font-black text-white', `${data.player_name}'s Rivalries`),
        _el('p', 'text-xs text-slate-400', `${data.total_opponents} opponents found`)
    ));

    // Cards
    const cards = [
        { key: 'nemesis', title: 'Nemesis', subtitle: 'Dominates you', pair: data.nemesis },
        { key: 'prey', title: 'Prey', subtitle: 'You dominate', pair: data.prey },
        { key: 'rival', title: 'Rival', subtitle: 'Evenly matched', pair: data.rival },
    ];

    const cardsGrid = _el('div', 'grid grid-cols-1 md:grid-cols-3 gap-4 mb-6');
    cards.forEach(c => {
        if (!c.pair) {
            cardsGrid.appendChild(_el('div', 'glass-panel rounded-xl border border-white/10 p-4 opacity-50',
                _el('div', 'text-xs text-slate-500 uppercase tracking-wider mb-1', c.title),
                _el('div', 'text-sm text-slate-400', `No ${c.title.toLowerCase()} found`),
                _el('div', 'text-[10px] text-slate-600 mt-1', c.subtitle)
            ));
            return;
        }

        const style = CLASSIFICATION_STYLES[c.pair.classification] || CLASSIFICATION_STYLES.INSUFFICIENT_DATA;
        const card = _el('div', `glass-panel rounded-xl border ${style.border} p-4 cursor-pointer hover:bg-white/5 transition rivalries-h2h-link`);
        card.dataset.opponentGuid = c.pair.opponent_guid;

        card.appendChild(_el('div', `text-xs ${style.text} uppercase tracking-wider mb-1`, `${style.icon} ${c.title}`));
        card.appendChild(_el('div', 'text-lg font-black text-white', c.pair.opponent_name));
        card.appendChild(_el('div', 'text-[10px] text-slate-500 mt-1', c.subtitle));

        const statsRow = _el('div', 'flex items-center gap-3 mt-3');
        const scoreDiv = _el('div', 'text-sm',
            _el('span', 'text-emerald-400 font-mono', String(c.pair.kills_by_player)),
            _el('span', 'text-slate-600 mx-1', '-'),
            _el('span', 'text-red-400 font-mono', String(c.pair.kills_on_player))
        );
        statsRow.appendChild(scoreDiv);
        statsRow.appendChild(_el('div', 'text-xs text-slate-500', `${c.pair.total_encounters} encounters`));
        card.appendChild(statsRow);

        const progressBar = _el('div', 'mt-2 w-full h-1.5 bg-slate-700 rounded-full overflow-hidden flex');
        const greenBar = _el('div', 'bg-emerald-500 h-full');
        greenBar.style.width = `${Math.round(c.pair.win_rate * 100)}%`;
        const redBar = _el('div', 'bg-red-500 h-full');
        redBar.style.width = `${100 - Math.round(c.pair.win_rate * 100)}%`;
        progressBar.appendChild(greenBar);
        progressBar.appendChild(redBar);
        card.appendChild(progressBar);

        cardsGrid.appendChild(card);
    });
    panel.appendChild(cardsGrid);

    // All pairs table
    const allPairs = (data.all_pairs || []).slice(0, 20);
    if (allPairs.length > 0) {
        const tablePanel = _el('div', 'glass-panel rounded-xl border border-white/10 overflow-hidden');
        tablePanel.appendChild(_el('div', 'px-4 py-3 border-b border-white/10',
            _el('h4', 'text-sm font-bold text-white', 'All Opponents')
        ));

        const tableWrap = _el('div', 'overflow-x-auto');
        const table = document.createElement('table');
        table.className = 'w-full';

        const thead = document.createElement('thead');
        const thRow = _el('tr', 'border-b border-white/10 text-[10px] text-slate-500 uppercase tracking-wider');
        ['Opponent', 'Kills', 'Deaths', 'Total', 'Win%', 'Type'].forEach((text, i) => {
            const th = document.createElement('th');
            th.className = i === 0 ? 'py-2 px-3 text-left' : 'py-2 px-3 text-center';
            th.textContent = text;
            thRow.appendChild(th);
        });
        thead.appendChild(thRow);
        table.appendChild(thead);

        const tbody = document.createElement('tbody');
        allPairs.forEach(p => {
            const pStyle = CLASSIFICATION_STYLES[p.classification] || CLASSIFICATION_STYLES.INSUFFICIENT_DATA;
            const tr = _el('tr', 'border-b border-white/5 hover:bg-white/5 cursor-pointer transition rivalries-h2h-link');
            tr.dataset.opponentGuid = p.opponent_guid;

            tr.appendChild(_el('td', 'py-2 px-3 text-white text-sm font-bold', p.opponent_name));
            tr.appendChild(_el('td', 'py-2 px-3 text-center text-emerald-400 font-mono text-sm', String(p.kills_by_player)));
            tr.appendChild(_el('td', 'py-2 px-3 text-center text-red-400 font-mono text-sm', String(p.kills_on_player)));
            tr.appendChild(_el('td', 'py-2 px-3 text-center text-white font-mono text-sm', String(p.total_encounters)));
            tr.appendChild(_el('td', 'py-2 px-3 text-center text-sm', `${Math.round(p.win_rate * 100)}%`));

            const typeTd = document.createElement('td');
            typeTd.className = 'py-2 px-3 text-center';
            typeTd.appendChild(_el('span', `px-1.5 py-0.5 rounded text-[10px] font-bold ${pStyle.bg} ${pStyle.text}`, pStyle.label));
            tr.appendChild(typeTd);

            tbody.appendChild(tr);
        });
        table.appendChild(tbody);
        tableWrap.appendChild(table);
        tablePanel.appendChild(tableWrap);
        panel.appendChild(tablePanel);
    }

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

    panel.textContent = '';
    panel.appendChild(_el('div', 'text-center text-slate-400 py-8', 'Loading H2H...'));
    panel.classList.remove('hidden');

    try {
        const data = await fetchJSON(`${API_BASE}/rivalries/h2h/${encodeURIComponent(guid1)}/${encodeURIComponent(guid2)}`);
        if (data.status !== 'ok') {
            panel.textContent = '';
            panel.appendChild(_el('div', 'text-red-400 text-center py-8', 'Failed to load H2H'));
            return;
        }
        state.h2hData = data;
        renderH2HDetail(panel, data);
    } catch (err) {
        panel.textContent = '';
        panel.appendChild(_el('div', 'text-red-400 text-center py-8', err.message));
    }
}

function renderH2HDetail(panel, data) {
    const style = CLASSIFICATION_STYLES[data.classification] || CLASSIFICATION_STYLES.INSUFFICIENT_DATA;
    const total = data.total;
    const p1Pct = total > 0 ? Math.round((data.p1_kills / total) * 100) : 50;

    panel.textContent = '';

    const card = _el('div', `glass-panel rounded-xl border ${style.border} p-6 mb-4`);

    // Header with back button and badge
    const headerRow = _el('div', 'flex items-center justify-between mb-4');
    const backBtn = document.createElement('button');
    backBtn.id = 'rivalries-h2h-close';
    backBtn.className = 'text-xs text-slate-400 hover:text-white transition';
    backBtn.textContent = '\u2190 Back';
    headerRow.appendChild(backBtn);
    headerRow.appendChild(_el('span', `px-2 py-0.5 rounded text-xs font-bold ${style.bg} ${style.border} ${style.text} border`, `${style.icon} ${style.label}`));
    card.appendChild(headerRow);

    // Score section
    const scoreSection = _el('div', 'text-center mb-6');
    const vsRow = _el('div', 'flex items-center justify-center gap-6',
        _el('div', null,
            _el('div', 'text-2xl font-black text-white', data.p1_name),
            _el('div', 'text-3xl font-black text-emerald-400 mt-1', String(data.p1_kills))
        ),
        _el('div', 'text-slate-500 text-2xl font-bold', 'vs'),
        _el('div', null,
            _el('div', 'text-2xl font-black text-white', data.p2_name),
            _el('div', 'text-3xl font-black text-red-400 mt-1', String(data.p2_kills))
        )
    );
    scoreSection.appendChild(vsRow);

    // Progress bar
    const progressWrap = _el('div', 'mt-3 max-w-sm mx-auto');
    const progressTrack = _el('div', 'w-full h-3 bg-slate-700 rounded-full overflow-hidden flex');
    const pBar1 = _el('div', 'bg-emerald-500 h-full transition-all');
    pBar1.style.width = `${p1Pct}%`;
    const pBar2 = _el('div', 'bg-red-500 h-full transition-all');
    pBar2.style.width = `${100 - p1Pct}%`;
    progressTrack.appendChild(pBar1);
    progressTrack.appendChild(pBar2);
    progressWrap.appendChild(progressTrack);

    progressWrap.appendChild(_el('div', 'flex justify-between mt-1 text-xs text-slate-400',
        _el('span', null, `${p1Pct}%`),
        _el('span', null, `${total} total encounters`),
        _el('span', null, `${100 - p1Pct}%`)
    ));
    scoreSection.appendChild(progressWrap);
    card.appendChild(scoreSection);

    // Weapon bars helper
    function buildWeaponBars(weapons, color) {
        const frag = document.createDocumentFragment();
        if (!weapons.length) {
            frag.appendChild(_el('div', 'text-xs text-slate-500', 'No kills'));
            return frag;
        }
        const maxKills = weapons[0].kills;
        weapons.slice(0, 6).forEach(w => {
            const pct = maxKills > 0 ? Math.round((w.kills / maxKills) * 100) : 0;
            const row = _el('div', 'flex items-center gap-2 mb-1');
            row.appendChild(_el('div', 'w-20 text-xs text-slate-300 truncate', w.weapon));
            const track = _el('div', 'flex-1 h-3 bg-slate-700 rounded-full overflow-hidden');
            const fill = _el('div', `h-full ${color} rounded-full`);
            fill.style.width = `${pct}%`;
            track.appendChild(fill);
            row.appendChild(track);
            row.appendChild(_el('div', 'w-8 text-xs text-slate-400 text-right font-mono', String(w.kills)));
            frag.appendChild(row);
        });
        return frag;
    }

    const weaponsGrid = _el('div', 'grid grid-cols-1 md:grid-cols-2 gap-6 mb-6');

    const p1WeaponsDiv = _el('div', null);
    p1WeaponsDiv.appendChild(_el('h4', 'text-xs text-emerald-400 uppercase tracking-wider font-bold mb-2', `${data.p1_name}'s Weapons`));
    p1WeaponsDiv.appendChild(buildWeaponBars(data.p1_weapons || [], 'bg-emerald-500'));
    weaponsGrid.appendChild(p1WeaponsDiv);

    const p2WeaponsDiv = _el('div', null);
    p2WeaponsDiv.appendChild(_el('h4', 'text-xs text-red-400 uppercase tracking-wider font-bold mb-2', `${data.p2_name}'s Weapons`));
    p2WeaponsDiv.appendChild(buildWeaponBars(data.p2_weapons || [], 'bg-red-500'));
    weaponsGrid.appendChild(p2WeaponsDiv);
    card.appendChild(weaponsGrid);

    // Per-map table
    const perMap = data.per_map || [];
    if (perMap.length > 0) {
        const mapSection = _el('div', null);
        mapSection.appendChild(_el('h4', 'text-xs text-slate-400 uppercase tracking-wider font-bold mb-2', 'Per Map'));

        const mapTableWrap = _el('div', 'overflow-x-auto');
        const mapTable = document.createElement('table');
        mapTable.className = 'w-full';

        const mapThead = document.createElement('thead');
        const mapThRow = _el('tr', 'border-b border-white/10 text-[10px] text-slate-500 uppercase tracking-wider');
        [
            { text: 'Map', cls: 'py-1 px-3 text-left' },
            { text: data.p1_name, cls: 'py-1 px-3 text-center' },
            { text: data.p2_name, cls: 'py-1 px-3 text-center' },
            { text: 'Total', cls: 'py-1 px-3 text-center' },
        ].forEach(th => {
            const thEl = document.createElement('th');
            thEl.className = th.cls;
            thEl.textContent = th.text;
            mapThRow.appendChild(thEl);
        });
        mapThead.appendChild(mapThRow);
        mapTable.appendChild(mapThead);

        const mapTbody = document.createElement('tbody');
        perMap.forEach(m => {
            const tr = _el('tr', 'border-b border-white/5');
            tr.appendChild(_el('td', 'py-1.5 px-3 text-white text-sm', m.map));
            tr.appendChild(_el('td', 'py-1.5 px-3 text-center text-emerald-400 font-mono text-sm', String(m.p1_kills)));
            tr.appendChild(_el('td', 'py-1.5 px-3 text-center text-red-400 font-mono text-sm', String(m.p2_kills)));
            tr.appendChild(_el('td', 'py-1.5 px-3 text-center text-white font-mono text-sm', String(m.total)));
            mapTbody.appendChild(tr);
        });
        mapTable.appendChild(mapTbody);
        mapTableWrap.appendChild(mapTable);
        mapSection.appendChild(mapTableWrap);
        card.appendChild(mapSection);
    }

    panel.appendChild(card);

    // Back button
    backBtn.addEventListener('click', () => {
        panel.textContent = '';
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
                if (panel) { panel.textContent = ''; panel.classList.add('hidden'); }
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
