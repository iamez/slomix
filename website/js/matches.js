/**
 * Matches module - match views, maps, weapons, match details
 * @module matches
 */

import { API_BASE, fetchJSON, escapeHtml, formatStopwatchTime } from './utils.js';
import { openModal } from './auth.js';

function formatClockTime(seconds) {
    const value = Number(seconds || 0);
    const mins = Math.floor(value / 60);
    const secs = Math.max(0, Math.floor(value % 60));
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function safeDomIdPart(value) {
    return String(value ?? '').replace(/[^a-zA-Z0-9_-]/g, '_');
}

/**
 * Load matches grid view
 */
export async function loadMatchesView(filter = 'all') {
    const grid = document.getElementById('matches-grid');
    if (!grid) return;

    grid.innerHTML = '<div class="text-center py-12"><i data-lucide="loader" class="w-8 h-8 text-brand-blue animate-spin mx-auto mb-4"></i><div class="text-slate-400">Loading matches...</div></div>';
    if (typeof lucide !== 'undefined') lucide.createIcons();

    try {
        const matches = await fetchJSON(`${API_BASE}/stats/matches?limit=50`);

        grid.innerHTML = '';

        if (matches.length === 0) {
            grid.innerHTML = '<div class="text-center text-slate-500 py-12">No matches found</div>';
            return;
        }

        matches.forEach(match => {
            const winnerTeam = match.winner;
            const team1Win = winnerTeam === 'Allies';
            const team2Win = winnerTeam === 'Axis';

            const formatColors = {
                '1v1': 'bg-purple-500/20 text-purple-400 border-purple-500/30',
                '3v3': 'bg-brand-cyan/20 text-brand-cyan border-brand-cyan/30',
                '6v6': 'bg-brand-gold/20 text-brand-gold border-brand-gold/30',
            };
            const formatClass = formatColors[match.format] || 'bg-slate-700 text-slate-400 border-slate-600';

            const safeMapName = escapeHtml(match.map_name);
            const safeFormat = escapeHtml(match.format || '');
            const safeTimeAgo = escapeHtml(match.time_ago || '');

            const team1Html = (match.team1_players || [])
                .map(p => `<span class="text-slate-300">${escapeHtml(p)}</span>`)
                .join(' <span class="text-slate-600">-</span> ');

            const team2Html = (match.team2_players || [])
                .map(p => `<span class="text-slate-300">${escapeHtml(p)}</span>`)
                .join(' <span class="text-slate-600">-</span> ');

            const html = `
            <div class="glass-panel rounded-xl hover:bg-white/5 transition cursor-pointer group border-l-4 ${team1Win ? 'border-l-brand-blue' : team2Win ? 'border-l-brand-rose' : 'border-l-slate-600'}"
                 data-match-id="${Number(match.id) || 0}">
                <div class="p-4">
                    <div class="flex items-center gap-2 mb-1 ${team1Win ? '' : 'opacity-70'}">
                        ${team1Win ? '<span class="text-brand-gold text-sm">🏆</span>' : ''}
                        <div class="text-sm">${team1Html || '<span class="text-slate-500 italic">No players</span>'}</div>
                    </div>
                    <div class="flex items-center gap-2 mb-3 ${team2Win ? '' : 'opacity-70'}">
                        ${team2Win ? '<span class="text-brand-gold text-sm">🏆</span>' : ''}
                        <div class="text-sm">${team2Html || '<span class="text-slate-500 italic">No players</span>'}</div>
                    </div>
                    <div class="flex items-center gap-2 text-xs">
                        <span class="text-slate-500">${safeMapName}</span>
                        <span class="px-2 py-0.5 rounded border ${formatClass} font-bold">${safeFormat}</span>
                        <span class="text-slate-500">${safeTimeAgo}</span>
                    </div>
                </div>
            </div>
            `;
            const wrapper = document.createElement('div');
            wrapper.innerHTML = html.trim();
            const card = wrapper.firstElementChild;
            if (card) {
                card.addEventListener('click', () => {
                    loadMatchDetails(Number(match.id) || 0);
                });
                grid.appendChild(card);
            }
        });
    } catch (e) {
        console.error('Failed to load matches:', e);
        grid.innerHTML = '<div class="text-center text-red-500 py-12">Failed to load matches</div>';
    }
}

/**
 * Load maps statistics view
 */
export async function loadMapsView() {
    const grid = document.getElementById('maps-grid');
    if (!grid) return;

    grid.innerHTML = '<div class="text-center py-12"><i data-lucide="loader" class="w-8 h-8 text-brand-cyan animate-spin mx-auto mb-4"></i><div class="text-slate-400">Loading map statistics...</div></div>';
    if (typeof lucide !== 'undefined') lucide.createIcons();

    try {
        const maps = await fetchJSON(`${API_BASE}/stats/maps`);
        mapsCache = Array.isArray(maps) ? maps : [];

        renderMapsSummary(mapsCache);
        renderMapsGrid();

        if (typeof lucide !== 'undefined') lucide.createIcons();
    } catch (e) {
        console.error('Failed to load maps:', e);
        grid.innerHTML = '<div class="text-center text-red-500 py-12">Failed to load map statistics</div>';
    }
}

let mapsCache = [];
let mapsSort = 'most-played';

function formatSeconds(seconds) {
    const total = Number(seconds || 0);
    if (!total) return '--';
    const mins = Math.floor(total / 60);
    const secs = Math.floor(total % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function formatShortDate(raw) {
    if (!raw) return '--';
    const date = new Date(`${raw}T00:00:00`);
    if (Number.isNaN(date.getTime())) return raw;
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function sortMaps(list) {
    const maps = [...list];
    switch (mapsSort) {
        case 'fastest':
            return maps.sort((a, b) => (a.avg_duration || 0) - (b.avg_duration || 0));
        case 'longest':
            return maps.sort((a, b) => (b.avg_duration || 0) - (a.avg_duration || 0));
        case 'last-played':
            return maps.sort((a, b) => String(b.last_played || '').localeCompare(String(a.last_played || '')));
        case 'grenade-spam':
            return maps.sort((a, b) => (b.grenade_kills || 0) - (a.grenade_kills || 0));
        case 'most-played':
        default:
            return maps.sort((a, b) => (b.matches_played || 0) - (a.matches_played || 0));
    }
}

function renderMapsSummary(maps) {
    const container = document.getElementById('maps-summary');
    if (!container) return;
    if (!maps.length) {
        container.innerHTML = '<div class="text-center text-slate-500">No map data yet.</div>';
        return;
    }

    const byPlays = [...maps].sort((a, b) => (b.matches_played || 0) - (a.matches_played || 0));
    const byFast = [...maps].filter(m => m.avg_duration).sort((a, b) => a.avg_duration - b.avg_duration);
    const byLong = [...maps].filter(m => m.avg_duration).sort((a, b) => b.avg_duration - a.avg_duration);
    const byNade = [...maps].sort((a, b) => (b.grenade_kills || 0) - (a.grenade_kills || 0));

    const mostPlayed = byPlays[0];
    const fastest = byFast[0];
    const longest = byLong[0];
    const nadeSpam = byNade[0];

    container.innerHTML = `
        <div class="glass-card p-4 rounded-xl border border-white/10">
            <div class="text-xs text-slate-500 uppercase">Most Played</div>
            <div class="text-lg font-black text-white">${escapeHtml(mostPlayed.name)}</div>
            <div class="text-xs text-slate-400">${mostPlayed.matches_played || 0} matches</div>
        </div>
        <div class="glass-card p-4 rounded-xl border border-white/10">
            <div class="text-xs text-slate-500 uppercase">Fastest Avg</div>
            <div class="text-lg font-black text-white">${escapeHtml(fastest?.name || '--')}</div>
            <div class="text-xs text-slate-400">${formatSeconds(fastest?.avg_duration || 0)}</div>
        </div>
        <div class="glass-card p-4 rounded-xl border border-white/10">
            <div class="text-xs text-slate-500 uppercase">Longest Avg</div>
            <div class="text-lg font-black text-white">${escapeHtml(longest?.name || '--')}</div>
            <div class="text-xs text-slate-400">${formatSeconds(longest?.avg_duration || 0)}</div>
        </div>
        <div class="glass-card p-4 rounded-xl border border-white/10">
            <div class="text-xs text-slate-500 uppercase">Nade Spam</div>
            <div class="text-lg font-black text-white">${escapeHtml(nadeSpam?.name || '--')}</div>
            <div class="text-xs text-slate-400">${nadeSpam?.grenade_kills || 0} nade kills</div>
        </div>
    `;
}

function renderMapsGrid() {
    const grid = document.getElementById('maps-grid');
    if (!grid) return;

    if (!mapsCache.length) {
        grid.innerHTML = '<div class="col-span-full text-center text-slate-500 py-12">No map statistics available</div>';
        return;
    }

    const maps = sortMaps(mapsCache);
    grid.innerHTML = maps.map((map) => {
        const alliesRate = map.allies_win_rate ?? 50;
        const axisRate = map.axis_win_rate ?? 50;
        const totalMatches = map.matches_played || 0;
        const avgDuration = formatSeconds(map.avg_duration);
        const lastPlayed = formatShortDate(map.last_played);
        const grenadeKills = map.grenade_kills || 0;
        const panzerKills = map.panzer_kills || 0;
        const mortarKills = map.mortar_kills || 0;

        return `
        <div class="glass-card p-5 rounded-2xl border border-white/10 hover:bg-white/5 transition">
            <div class="flex items-center justify-between">
                <div>
                    <div class="text-[10px] uppercase text-slate-500">Map</div>
                    <div class="text-xl font-black text-white">${escapeHtml(map.name)}</div>
                </div>
                <div class="text-right">
                    <div class="text-2xl font-black text-brand-cyan">${totalMatches}</div>
                    <div class="text-[10px] text-slate-500 uppercase">Matches</div>
                </div>
            </div>
            <div class="mt-3 grid grid-cols-2 gap-2 text-xs">
                <div class="p-2 rounded bg-slate-900/60">
                    <div class="text-[10px] text-slate-500 uppercase">Avg Time</div>
                    <div class="font-bold text-white">${avgDuration}</div>
                </div>
                <div class="p-2 rounded bg-slate-900/60">
                    <div class="text-[10px] text-slate-500 uppercase">Last Played</div>
                    <div class="font-bold text-white">${lastPlayed}</div>
                </div>
                <div class="p-2 rounded bg-slate-900/60">
                    <div class="text-[10px] text-slate-500 uppercase">Players</div>
                    <div class="font-bold text-white">${map.unique_players || 0}</div>
                </div>
                <div class="p-2 rounded bg-slate-900/60">
                    <div class="text-[10px] text-slate-500 uppercase">Avg DPM</div>
                    <div class="font-bold text-white">${map.avg_dpm || 0}</div>
                </div>
            </div>
            <div class="mt-4">
                <div class="flex items-center justify-between text-[10px] uppercase text-slate-500">
                    <span>Allies</span>
                    <span>Axis</span>
                </div>
                <div class="w-full bg-slate-800 h-2 rounded-full overflow-hidden mt-1">
                    <div class="bg-brand-blue h-full" style="width: ${alliesRate}%"></div>
                </div>
                <div class="flex items-center justify-between text-xs mt-1">
                    <span class="text-brand-blue font-bold">${alliesRate}%</span>
                    <span class="text-brand-rose font-bold">${axisRate}%</span>
                </div>
            </div>
            <div class="mt-3 flex flex-wrap gap-2 text-[10px]">
                <span class="px-2 py-1 rounded-full bg-slate-900/60 text-slate-300">Kills ${map.total_kills || 0}</span>
                <span class="px-2 py-1 rounded-full bg-slate-900/60 text-slate-300">Rounds ${map.total_rounds || 0}</span>
                <span class="px-2 py-1 rounded-full bg-slate-900/60 text-slate-300">Nades ${grenadeKills}</span>
                <span class="px-2 py-1 rounded-full bg-slate-900/60 text-slate-300">Panzer ${panzerKills}</span>
                <span class="px-2 py-1 rounded-full bg-slate-900/60 text-slate-300">Mortar ${mortarKills}</span>
            </div>
        </div>
        `;
    }).join('');
}

export function setMapsSort(sortKey) {
    mapsSort = sortKey;
    document.querySelectorAll('[data-map-sort]').forEach(btn => {
        btn.classList.remove('bg-brand-cyan/20', 'text-brand-cyan', 'active');
        btn.classList.add('bg-slate-800', 'text-slate-400');
    });
    const active = document.querySelector(`[data-map-sort="${sortKey}"]`);
    if (active) {
        active.classList.remove('bg-slate-800', 'text-slate-400');
        active.classList.add('bg-brand-cyan/20', 'text-brand-cyan', 'active');
    }
    renderMapsGrid();
}

window.setMapsSort = setMapsSort;

/**
 * Load weapons statistics view
 */
export async function loadWeaponsView() {
    const grid = document.getElementById('weapons-grid');
    if (!grid) return;

    grid.innerHTML = '<div class="text-center py-12"><i data-lucide="loader" class="w-8 h-8 text-brand-rose animate-spin mx-auto mb-4"></i><div class="text-slate-400">Loading weapon statistics...</div></div>';
    if (typeof lucide !== 'undefined') lucide.createIcons();

    try {
        await refreshWeaponsData();
        bindWeaponFilters();
        renderWeaponHallOfFame();
        renderWeaponsGrid();
        if (typeof lucide !== 'undefined') lucide.createIcons();
    } catch (e) {
        console.error('Failed to load weapons:', e);
        grid.innerHTML = '<div class="col-span-full text-center text-red-500 py-12">Failed to load weapon statistics</div>';
    }
}

const weaponCategories = {
    'knife': 'Melee', 'luger': 'Pistol', 'colt': 'Pistol',
    'mp40': 'SMG', 'thompson': 'SMG', 'sten': 'SMG',
    'fg42': 'Rifle', 'garand': 'Rifle', 'k43': 'Rifle', 'kar98': 'Rifle',
    'panzerfaust': 'Heavy', 'flamethrower': 'Heavy', 'mortar': 'Heavy', 'mg42': 'Heavy',
    'grenade': 'Explosive', 'dynamite': 'Explosive', 'landmine': 'Explosive',
    'airstrike': 'Support', 'artillery': 'Support', 'syringe': 'Support', 'smokegrenade': 'Support'
};

const categoryColors = {
    'Melee': 'brand-amber', 'Pistol': 'brand-slate', 'SMG': 'brand-blue',
    'Rifle': 'brand-purple', 'Heavy': 'brand-rose', 'Explosive': 'brand-gold',
    'Support': 'brand-emerald', 'Other': 'brand-cyan'
};

let weaponsCache = [];
let weaponsHall = {};
let weaponPeriod = 'all';
let weaponCategory = 'all';
let weaponFiltersBound = false;

async function refreshWeaponsData() {
    const [weapons, hof] = await Promise.all([
        fetchJSON(`${API_BASE}/stats/weapons?limit=200&period=${weaponPeriod}`),
        fetchJSON(`${API_BASE}/stats/weapons/hall-of-fame?period=${weaponPeriod}`)
    ]);
    weaponsCache = Array.isArray(weapons) ? weapons : [];
    weaponsHall = hof?.leaders || {};
}

function normalizeWeaponKey(name) {
    return (name || '').toLowerCase().replace(/\s+/g, '');
}

function getWeaponCategory(weaponName) {
    const key = normalizeWeaponKey(weaponName);
    return weaponCategories[key] || 'Other';
}

function bindWeaponFilters() {
    if (weaponFiltersBound) return;
    weaponFiltersBound = true;

    document.querySelectorAll('.weapon-period-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const period = btn.dataset.weaponPeriod;
            if (!period || period === weaponPeriod) return;
            weaponPeriod = period;
            document.querySelectorAll('.weapon-period-btn').forEach(b => {
                b.classList.remove('bg-brand-rose/20', 'text-brand-rose', 'active');
                b.classList.add('bg-slate-800', 'text-slate-400');
            });
            btn.classList.remove('bg-slate-800', 'text-slate-400');
            btn.classList.add('bg-brand-rose/20', 'text-brand-rose', 'active');
            await refreshWeaponsData();
            renderWeaponHallOfFame();
            renderWeaponsGrid();
        });
    });

    document.querySelectorAll('.weapon-category-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const category = btn.dataset.weaponCategory || 'all';
            weaponCategory = category;
            document.querySelectorAll('.weapon-category-btn').forEach(b => {
                b.classList.remove('bg-brand-rose', 'text-white', 'shadow-lg');
                b.classList.add('text-slate-400');
            });
            btn.classList.add('bg-brand-rose', 'text-white', 'shadow-lg');
            btn.classList.remove('text-slate-400');
            renderWeaponsGrid();
        });
    });
}

function renderWeaponHallOfFame() {
    const container = document.getElementById('weapons-hof');
    if (!container) return;

    const entries = Object.values(weaponsHall);
    if (!entries.length) {
        container.innerHTML = '<div class="col-span-full text-center text-slate-500">No hall of fame data yet.</div>';
        return;
    }

    const order = ['luger','colt','mp40','thompson','sten','fg42','garand','k43','kar98','panzerfaust','mortar','grenade'];
    const sorted = entries.sort((a, b) => order.indexOf(normalizeWeaponKey(a.weapon)) - order.indexOf(normalizeWeaponKey(b.weapon)));

    container.innerHTML = sorted.map(entry => {
        const category = getWeaponCategory(entry.weapon);
        const color = categoryColors[category] || 'brand-cyan';
        return `
            <div class="glass-card p-4 rounded-xl border border-white/10">
                <div class="flex items-center justify-between mb-3">
                    <span class="text-xs uppercase text-slate-500">${escapeHtml(category)}</span>
                    <span class="text-${color} text-xs font-bold">${escapeHtml(entry.weapon)}</span>
                </div>
                <div class="text-lg font-black text-white">${escapeHtml(entry.player_name || 'Unknown')}</div>
                <div class="text-xs text-slate-400 mt-1">
                    ${entry.kills} kills · ${entry.headshots || 0} HS · ${entry.accuracy || 0}% acc
                </div>
            </div>
        `;
    }).join('');
}

function renderWeaponsGrid() {
    const grid = document.getElementById('weapons-grid');
    if (!grid) return;

    let weapons = [...weaponsCache];
    if (weaponCategory !== 'all') {
        weapons = weapons.filter(w => getWeaponCategory(w.name).toLowerCase() === weaponCategory);
    }

    if (weapons.length === 0) {
        grid.innerHTML = '<div class="col-span-full text-center text-slate-500 py-12">No weapons found for this filter.</div>';
        return;
    }

    const totalKills = weapons.reduce((sum, w) => sum + (w.kills || 0), 0);

    grid.innerHTML = weapons.map(weapon => {
        const weaponKey = normalizeWeaponKey(weapon.name);
        const category = weaponCategories[weaponKey] || 'Other';
        const color = categoryColors[category] || 'brand-cyan';
        const usage = totalKills > 0 ? ((weapon.kills / totalKills) * 100).toFixed(1) : 0;
        const safeWeaponName = escapeHtml(weapon.name);
        const safeCategory = escapeHtml(category);

        return `
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
                    <span class="font-bold text-white">${(weapon.kills || 0).toLocaleString()}</span>
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
    }).join('');
    if (typeof lucide !== 'undefined') lucide.createIcons();
}

/**
 * Load detailed match information in modal
 * @param {number} matchId - The match/round ID
 * @param {boolean} skipTabs - If true, don't add tab buttons (used when switching tabs)
 */
export async function loadMatchDetails(matchId, skipTabs = false) {
    console.log('[loadMatchDetails] Called with ID:', matchId, 'skipTabs:', skipTabs);
    
    if (!matchId) {
        console.error('[loadMatchDetails] No matchId provided!');
        return;
    }

    try {
        if (!skipTabs) {
            console.log('[loadMatchDetails] Opening modal...');
            openModal('modal-match-details');
            console.log('[loadMatchDetails] Modal should be visible now');
        }

        const content = document.getElementById('match-modal-content');
        if (!content) {
            console.error('[loadMatchDetails] Could not find match-modal-content element!');
            return;
        }
        
        console.log('[loadMatchDetails] Setting loading state...');
        content.innerHTML = '<div class="text-center py-12"><i data-lucide="loader" class="w-8 h-8 text-brand-blue animate-spin mx-auto mb-4"></i><div class="text-slate-400">Loading match details...</div></div>';
        if (typeof lucide !== 'undefined') lucide.createIcons();

        console.log('[loadMatchDetails] Fetching match details for ID:', matchId);
        const data = await fetchJSON(`${API_BASE}/stats/matches/${encodeURIComponent(matchId)}`);
        console.log('[loadMatchDetails] Match data received:', data);

        const m = data.match;
        const team1 = data.team1;
        const team2 = data.team2;

        document.getElementById('match-modal-title').textContent = m.map_name;
        document.getElementById('match-modal-subtitle').textContent = `Round ${m.round_number} • ${m.round_date} • ${data.player_count} players`;

        const totalKills = team1.totals.kills + team2.totals.kills;
        const totalDamage = team1.totals.damage + team2.totals.damage;
        const allPlayers = [...team1.players, ...team2.players];
        const avgDpm = allPlayers.length > 0
            ? Math.round(allPlayers.reduce((sum, p) => sum + p.dpm, 0) / allPlayers.length)
            : 0;

        const team1Color = team1.is_winner ? 'text-brand-gold' : 'text-slate-400';
        const team2Color = team2.is_winner ? 'text-brand-gold' : 'text-slate-400';

        // Tab buttons
        let html = `
        <div class="flex gap-2 mb-4">
            <button id="match-tab-stats" class="match-tab-btn px-4 py-2 rounded-lg font-bold text-sm transition bg-brand-blue text-white"
                    onclick="switchMatchTab(${matchId}, 'stats')">
                📊 Stats
            </button>
            <button id="match-tab-awards" class="match-tab-btn px-4 py-2 rounded-lg font-bold text-sm transition bg-slate-700 text-slate-300 hover:bg-slate-600"
                    onclick="switchMatchTab(${matchId}, 'awards')">
                🏆 Awards
            </button>
        </div>
        <div class="space-y-6">
            <div class="flex items-center justify-center gap-8 py-4">
                <div class="text-center flex-1">
                    <div class="text-xs text-slate-500 uppercase mb-1">Allies</div>
                    <div class="flex items-center justify-center gap-2">
                        ${team1.is_winner ? '<span class="text-brand-gold text-2xl">🏆</span>' : ''}
                        <div>
                            <div class="text-lg font-black ${team1Color}">${team1.totals.kills} kills</div>
                            <div class="text-xs text-slate-500">${(team1.totals.damage / 1000).toFixed(1)}k dmg</div>
                        </div>
                    </div>
                </div>
                <div class="text-center px-6">
                    <div class="text-xs text-slate-500 uppercase mb-2">Round Result</div>
                    <div class="text-2xl font-black text-white">${escapeHtml(m.winner)}</div>
                    <div class="text-xs text-slate-400 mt-1">${escapeHtml(m.outcome || 'objective')}</div>
                    <div class="text-xl font-black text-brand-cyan mt-2">${escapeHtml(m.duration || '0:00')}</div>
                    <div class="text-xs text-slate-500">Duration${m.time_limit ? ` / ${escapeHtml(m.time_limit)} limit` : ''}</div>
                </div>
                <div class="text-center flex-1">
                    <div class="text-xs text-slate-500 uppercase mb-1">Axis</div>
                    <div class="flex items-center justify-center gap-2">
                        <div>
                            <div class="text-lg font-black ${team2Color}">${team2.totals.kills} kills</div>
                            <div class="text-xs text-slate-500">${(team2.totals.damage / 1000).toFixed(1)}k dmg</div>
                        </div>
                        ${team2.is_winner ? '<span class="text-brand-gold text-2xl">🏆</span>' : ''}
                    </div>
                </div>
            </div>

            <div class="grid grid-cols-3 gap-3">
                <div class="glass-card p-3 rounded-xl text-center">
                    <div class="text-[10px] text-slate-500 uppercase font-bold">Total Kills</div>
                    <div class="text-xl font-black text-brand-rose">${totalKills}</div>
                </div>
                <div class="glass-card p-3 rounded-xl text-center">
                    <div class="text-[10px] text-slate-500 uppercase font-bold">Total Damage</div>
                    <div class="text-xl font-black text-brand-purple">${(totalDamage / 1000).toFixed(1)}k</div>
                </div>
                <div class="glass-card p-3 rounded-xl text-center">
                    <div class="text-[10px] text-slate-500 uppercase font-bold">Avg DPM</div>
                    <div class="text-xl font-black text-brand-emerald">${avgDpm}</div>
                </div>
            </div>
        `;

        [team1, team2].forEach((team, idx) => {
            const teamName = idx === 0 ? 'Allies' : 'Axis';
            const teamColor = idx === 0 ? 'brand-blue' : 'brand-rose';
            const players = team.players.sort((a, b) => b.dpm - a.dpm);

            html += `
            <div class="glass-panel rounded-xl overflow-hidden">
                <div class="p-4 border-b border-white/10 flex items-center justify-between">
                    <div class="flex items-center gap-3">
                        <div class="w-3 h-3 rounded-full bg-${teamColor}"></div>
                        <h3 class="text-lg font-black text-white">${teamName}</h3>
                        ${team.is_winner ? '<span class="text-brand-gold text-sm">🏆 Winner</span>' : ''}
                    </div>
                    <div class="flex gap-4 text-xs">
                        <span class="text-slate-400">K: <span class="font-bold text-white">${team.totals.kills}</span></span>
                        <span class="text-slate-400">D: <span class="font-bold text-white">${team.totals.deaths}</span></span>
                        <span class="text-slate-400">DMG: <span class="font-bold text-white">${(team.totals.damage / 1000).toFixed(1)}k</span></span>
                    </div>
                </div>

                <div class="overflow-x-auto">
                    <table class="w-full text-xs">
                        <thead>
                            <tr class="text-[10px] text-slate-500 uppercase bg-slate-900/50">
                                <th class="text-left py-2 px-3 font-bold">Name</th>
                                <th class="text-right py-2 px-2 font-bold">K/D/G</th>
                                <th class="text-right py-2 px-2 font-bold">KDR</th>
                                <th class="text-right py-2 px-2 font-bold">DPM</th>
                                <th class="text-right py-2 px-2 font-bold">DMG↑/↓</th>
                                <th class="text-right py-2 px-2 font-bold">ACC</th>
                                <th class="text-right py-2 px-2 font-bold">HS</th>
                                <th class="text-right py-2 px-2 font-bold">UK</th>
                                <th class="text-right py-2 px-2 font-bold">REV↑/↓</th>
                                <th class="text-right py-2 px-2 font-bold">Time</th>
                            </tr>
                        </thead>
                        <tbody>
            `;

            players.forEach((player, index) => {
                const isTop = index === 0;
                const rowBg = isTop ? 'bg-brand-gold/5' : '';
                const safeName = escapeHtml(player.name);
                const kdColor = player.kd >= 2.0 ? 'text-brand-emerald' : player.kd >= 1.0 ? 'text-white' : 'text-brand-rose';
                const encodedGuid = encodeURIComponent(String(player.player_guid || ''));
                const rowId = `player-row-${matchId}-${index}`;
                html += `
                    <tr id="${rowId}" class="border-b border-white/5 hover:bg-white/5 transition cursor-pointer ${rowBg}"
                        data-round-id="${Number(matchId) || 0}"
                        data-player-guid="${encodedGuid}">
                        <td class="py-2 px-3">
                            <div class="flex items-center gap-2">
                                ${isTop ? '<span class="text-brand-gold">🏆</span>' : ''}
                                <span class="hover:text-${teamColor} transition font-medium ${isTop ? 'text-brand-gold' : 'text-white'}">${safeName}</span>
                            </div>
                        </td>
                        <td class="text-right py-2 px-2 font-mono text-slate-300">${player.kills}/${player.deaths}/${player.gibs || 0}</td>
                        <td class="text-right py-2 px-2 font-mono ${kdColor} font-bold">${player.kd.toFixed(2)}</td>
                        <td class="text-right py-2 px-2 font-mono text-brand-cyan font-bold">${player.dpm}</td>
                        <td class="text-right py-2 px-2 font-mono text-brand-purple">${(player.damage_given/1000).toFixed(1)}k/${(player.damage_received/1000).toFixed(1)}k</td>
                        <td class="text-right py-2 px-2 font-mono text-slate-300">${player.accuracy}% (${player.hits || 0}/${player.shots || 0})</td>
                        <td class="text-right py-2 px-2 font-mono text-slate-300">${player.headshots}</td>
                        <td class="text-right py-2 px-2 font-mono text-brand-emerald">${player.useful_kills || 0}</td>
                        <td class="text-right py-2 px-2 font-mono text-brand-emerald">${player.revives_given || 0}/${player.times_revived || 0}</td>
                        <td class="text-right py-2 px-2 font-mono text-slate-400">${formatClockTime(player.time_played || 0)}</td>
                    </tr>
                `;
            });

            html += `
                        </tbody>
                    </table>
                </div>
            </div>
            `;
        });

        html += '</div>';
        content.innerHTML = html;
        content.querySelectorAll('tr[data-player-guid][data-round-id]').forEach((row) => {
            row.addEventListener('click', () => {
                const roundId = Number(row.getAttribute('data-round-id') || 0);
                const playerGuidRaw = row.getAttribute('data-player-guid') || '';
                let playerGuid = '';
                try {
                    playerGuid = decodeURIComponent(playerGuidRaw);
                } catch {
                    playerGuid = playerGuidRaw;
                }
                if (!roundId || !playerGuid) return;
                togglePlayerDetails(roundId, playerGuid, row);
            });
        });
        if (typeof lucide !== 'undefined') lucide.createIcons();

    } catch (e) {
        console.error('Failed to load match details:', e);
        content.innerHTML = '<div class="text-center text-red-500 py-12">Failed to load match details</div>';
    }
}

/**
 * Load awards tab content for a match
 */
async function loadMatchAwards(roundId) {
    const content = document.getElementById('match-modal-content');
    content.innerHTML = '<div class="text-center py-12"><i data-lucide="loader" class="w-8 h-8 text-brand-gold animate-spin mx-auto mb-4"></i><div class="text-slate-400">Loading awards...</div></div>';
    if (typeof lucide !== 'undefined') lucide.createIcons();

    try {
        const [awardsData, vsData] = await Promise.all([
            fetchJSON(`${API_BASE}/rounds/${roundId}/awards`),
            fetchJSON(`${API_BASE}/rounds/${roundId}/vs-stats`)
        ]);

        if (Object.keys(awardsData.categories).length === 0) {
            content.innerHTML = '<div class="text-center py-12 text-slate-400">No awards data available for this round</div>';
            return;
        }

        let html = '<div class="space-y-4">';

        // Awards by category
        for (const [catKey, catData] of Object.entries(awardsData.categories)) {
            html += `
            <div class="glass-panel rounded-xl overflow-hidden">
                <div class="p-3 border-b border-white/10 flex items-center gap-2">
                    <span class="text-lg">${catData.emoji}</span>
                    <h3 class="font-bold text-white">${escapeHtml(catData.name)}</h3>
                </div>
                <div class="p-3 space-y-2">
            `;

            for (const award of catData.awards) {
                html += `
                    <div class="flex items-center justify-between text-sm">
                        <span class="text-slate-400">${escapeHtml(award.award)}</span>
                        <span class="flex items-center gap-2">
                            <span class="font-bold text-white">${escapeHtml(award.player)}</span>
                            <span class="text-brand-gold">(${escapeHtml(award.value)})</span>
                        </span>
                    </div>
                `;
            }

            html += '</div></div>';
        }

        // VS Stats table
        if (vsData.stats && vsData.stats.length > 0) {
            html += `
            <div class="glass-panel rounded-xl overflow-hidden">
                <div class="p-3 border-b border-white/10 flex items-center gap-2">
                    <span class="text-lg">📊</span>
                    <h3 class="font-bold text-white">VS Stats</h3>
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full text-sm">
                        <thead>
                            <tr class="text-[10px] text-slate-500 uppercase bg-slate-900/50">
                                <th class="text-left py-2 px-3 font-bold">Player</th>
                                <th class="text-right py-2 px-3 font-bold">Kills</th>
                                <th class="text-right py-2 px-3 font-bold">Deaths</th>
                                <th class="text-right py-2 px-3 font-bold">K/D</th>
                            </tr>
                        </thead>
                        <tbody>
            `;

            for (const stat of vsData.stats) {
                const kd = stat.deaths > 0 ? (stat.kills / stat.deaths).toFixed(2) : stat.kills.toFixed(2);
                const kdColor = kd >= 2.0 ? 'text-brand-emerald' : kd >= 1.0 ? 'text-white' : 'text-brand-rose';
                html += `
                    <tr class="border-b border-white/5 hover:bg-white/5 transition">
                        <td class="py-2 px-3 font-medium text-white">${escapeHtml(stat.player)}</td>
                        <td class="text-right py-2 px-3 font-mono text-brand-emerald">${stat.kills}</td>
                        <td class="text-right py-2 px-3 font-mono text-slate-400">${stat.deaths}</td>
                        <td class="text-right py-2 px-3 font-mono ${kdColor} font-bold">${kd}</td>
                    </tr>
                `;
            }

            html += '</tbody></table></div></div>';
        }

        html += '</div>';
        content.innerHTML = html;

    } catch (e) {
        console.error('Failed to load match awards:', e);
        content.innerHTML = '<div class="text-center text-red-500 py-12">Failed to load awards data</div>';
    }
}

/**
 * Switch between Stats and Awards tabs in match modal
 */
function switchMatchTab(roundId, tab) {
    // Update tab button states
    document.querySelectorAll('.match-tab-btn').forEach(btn => {
        btn.classList.remove('bg-brand-blue', 'text-white');
        btn.classList.add('bg-slate-700', 'text-slate-300');
    });
    document.getElementById(`match-tab-${tab}`).classList.remove('bg-slate-700', 'text-slate-300');
    document.getElementById(`match-tab-${tab}`).classList.add('bg-brand-blue', 'text-white');

    if (tab === 'awards') {
        loadMatchAwards(roundId);
    } else {
        // Reload stats - we stored the match ID, need to reload
        loadMatchDetails(roundId, true);
    }
}

/**
 * Toggle expanded player details inline
 */
async function togglePlayerDetails(roundId, playerGuid, rowElement) {
    const detailsId = `details-${safeDomIdPart(roundId)}-${safeDomIdPart(playerGuid)}`;
    const existingRow = document.getElementById(detailsId);

    // If already expanded, collapse it
    if (existingRow) {
        existingRow.remove();
        return;
    }

    try {
        // Fetch detailed player stats
        const data = await fetchJSON(`${API_BASE}/rounds/${roundId}/player/${playerGuid}/details`);

        // Create expanded details row
        const detailsRow = document.createElement('tr');
        detailsRow.id = detailsId;
        detailsRow.className = 'bg-slate-800/30 border-b border-white/10';

        const weapons = Array.isArray(data.weapons) ? data.weapons : [];
        const weaponRows = weapons.map(w => `
            <tr class="border-b border-white/5">
                <td class="py-1 px-2 text-slate-300">${escapeHtml(w.weapon_name)}</td>
                <td class="text-right py-1 px-2 font-mono text-white">${Number(w.kills || 0)}</td>
                <td class="text-right py-1 px-2 font-mono text-slate-400">${Number(w.deaths || 0)}</td>
                <td class="text-right py-1 px-2 font-mono text-brand-rose">${Number(w.headshots || 0)}</td>
                <td class="text-right py-1 px-2 font-mono ${Number(w.accuracy || 0) >= 30 ? 'text-brand-emerald' : 'text-slate-300'}">${Number(w.accuracy || 0)}%</td>
                <td class="text-right py-1 px-2 font-mono text-slate-400">${Number(w.hits || 0)}/${Number(w.shots || 0)}</td>
            </tr>
        `).join('');

        detailsRow.innerHTML = `
            <td colspan="10" class="py-4 px-4">
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <!-- Combat Stats -->
                    <div class="glass-card p-4 rounded-lg">
                        <h4 class="text-sm font-bold text-white mb-3 flex items-center gap-2">
                            <span>⚔️</span>
                            <span>Combat Performance</span>
                        </h4>
                        <div class="grid grid-cols-2 gap-2 text-xs">
                            <div class="flex justify-between">
                                <span class="text-slate-400">Kills:</span>
                                <span class="font-mono text-white">${data.combat.kills}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-slate-400">Deaths:</span>
                                <span class="font-mono text-white">${data.combat.deaths}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-slate-400">Gibs:</span>
                                <span class="font-mono text-brand-rose">${data.combat.gibs}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-slate-400">Useful Kills:</span>
                                <span class="font-mono text-brand-emerald">${data.combat.useful_kills}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-slate-400">Headshots:</span>
                                <span class="font-mono text-brand-rose">${data.combat.headshots}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-slate-400">HS Kills:</span>
                                <span class="font-mono text-brand-rose">${data.combat.headshot_kills}</span>
                            </div>
                        </div>
                    </div>

                    <!-- Support & Objectives -->
                    <div class="glass-card p-4 rounded-lg">
                        <h4 class="text-sm font-bold text-white mb-3 flex items-center gap-2">
                            <span>🎯</span>
                            <span>Support & Objectives</span>
                        </h4>
                        <div class="grid grid-cols-2 gap-2 text-xs">
                            <div class="flex justify-between">
                                <span class="text-slate-400">Revives Given:</span>
                                <span class="font-mono text-brand-emerald">${data.support.revives_given}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-slate-400">Times Revived:</span>
                                <span class="font-mono text-brand-emerald">${data.support.times_revived}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-slate-400">Health Given:</span>
                                <span class="font-mono text-slate-300">${data.support.health_given}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-slate-400">Ammo Given:</span>
                                <span class="font-mono text-slate-300">${data.support.ammo_given}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-slate-400">Objectives:</span>
                                <span class="font-mono text-brand-gold">${data.objectives.objectives_stolen + data.objectives.objectives_returned}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-slate-400">Dynamites:</span>
                                <span class="font-mono text-orange-400">${data.objectives.dynamites_planted}</span>
                            </div>
                        </div>
                    </div>

                    <!-- Weapon Breakdown -->
                    <div class="lg:col-span-2 glass-card p-4 rounded-lg">
                        <h4 class="text-sm font-bold text-white mb-3 flex items-center gap-2">
                            <span>🔫</span>
                            <span>Weapon Breakdown</span>
                        </h4>
                        <div class="overflow-x-auto">
                            <table class="w-full text-xs">
                                <thead>
                                    <tr class="border-b border-white/10 text-slate-400">
                                        <th class="text-left py-2 px-2">Weapon</th>
                                        <th class="text-right py-2 px-2">K</th>
                                        <th class="text-right py-2 px-2">D</th>
                                        <th class="text-right py-2 px-2">HS</th>
                                        <th class="text-right py-2 px-2">ACC</th>
                                        <th class="text-right py-2 px-2">Hits/Shots</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${weaponRows}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <!-- Time Stats & Sprees -->
                    <div class="lg:col-span-2 grid grid-cols-2 gap-4">
                        <div class="glass-card p-4 rounded-lg">
                            <h4 class="text-sm font-bold text-white mb-3 flex items-center gap-2">
                                <span>⏱️</span>
                                <span>Time Stats</span>
                            </h4>
                            <div class="grid grid-cols-2 gap-2 text-xs">
                                <div class="flex justify-between">
                                    <span class="text-slate-400">Playtime:</span>
                                    <span class="font-mono text-white">${formatClockTime(data.time.time_played)}</span>
                                </div>
                                <div class="flex justify-between">
                                    <span class="text-slate-400">Time Dead:</span>
                                    <span class="font-mono text-slate-400">${formatClockTime(data.time.time_dead)}</span>
                                </div>
                            </div>
                        </div>
                        ${data.sprees && data.sprees.length > 0 ? `
                        <div class="glass-card p-4 rounded-lg">
                            <h4 class="text-sm font-bold text-white mb-3 flex items-center gap-2">
                                <span>🔥</span>
                                <span>Kill Sprees</span>
                            </h4>
                            <div class="space-y-1 text-xs">
                                ${data.sprees.map(s => `
                                    <div class="flex justify-between">
                                        <span class="text-slate-400">${escapeHtml(s.spree_type)}:</span>
                                        <span class="font-mono text-brand-gold">${Number(s.count || 0)}x</span>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                        ` : ''}
                    </div>
                </div>
            </td>
        `;

        // Insert after current row
        rowElement.parentNode.insertBefore(detailsRow, rowElement.nextSibling);

    } catch (e) {
        console.error('Failed to load player details:', e);
    }
}

// Expose to window for onclick handlers in HTML
window.loadMatchDetails = loadMatchDetails;
window.loadMatchAwards = loadMatchAwards;
window.switchMatchTab = switchMatchTab;
window.togglePlayerDetails = togglePlayerDetails;
