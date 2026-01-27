/**
 * Matches module - match views, maps, weapons, match details
 * @module matches
 */

import { API_BASE, fetchJSON, escapeHtml, escapeJsString, formatStopwatchTime } from './utils.js';
import { openModal } from './auth.js';

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
                 onclick="loadMatchDetails(${match.id})">
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
            grid.insertAdjacentHTML('beforeend', html);
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
        const matches = await fetchJSON(`${API_BASE}/stats/matches?limit=200`);

        const mapStats = {};
        matches.forEach(match => {
            if (!mapStats[match.map_name]) {
                mapStats[match.map_name] = {
                    name: match.map_name,
                    plays: 0,
                    alliedWins: 0,
                    axisWins: 0
                };
            }
            mapStats[match.map_name].plays++;
            if (match.winner === 'Allies') {
                mapStats[match.map_name].alliedWins++;
            } else {
                mapStats[match.map_name].axisWins++;
            }
        });

        grid.innerHTML = '';

        Object.values(mapStats).forEach(map => {
            const winRate = ((map.alliedWins / map.plays) * 100).toFixed(1);
            const borderColor = winRate > 55 ? 'border-brand-emerald' : winRate < 45 ? 'border-brand-rose' : 'border-brand-cyan';

            const html = `
            <div class="glass-card p-6 rounded-xl border-l-4 ${borderColor} hover:scale-105 transition-transform cursor-pointer">
                <div class="flex items-center justify-between mb-4">
                    <div class="w-16 h-16 rounded-lg bg-slate-800 border border-white/10 flex items-center justify-center">
                        <span class="text-xs font-bold text-slate-400 uppercase">${escapeHtml(map.name.substring(0, 3))}</span>
                    </div>
                    <div class="text-right">
                        <div class="text-2xl font-black text-white">${map.plays}</div>
                        <div class="text-xs text-slate-500 uppercase">Plays</div>
                    </div>
                </div>
                <h3 class="text-lg font-bold text-white mb-3">${escapeHtml(map.name)}</h3>
                <div class="space-y-2">
                    <div class="flex justify-between text-sm">
                        <span class="text-slate-400">Allied Win Rate</span>
                        <span class="font-bold text-brand-blue">${winRate}%</span>
                    </div>
                    <div class="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                        <div class="bg-brand-blue h-full" style="width: ${winRate}%"></div>
                    </div>
                    <div class="grid grid-cols-2 gap-2 pt-2">
                        <div class="text-center p-2 bg-slate-800/50 rounded">
                            <div class="text-xs text-slate-500">Allied</div>
                            <div class="font-bold text-brand-blue">${map.alliedWins}</div>
                        </div>
                        <div class="text-center p-2 bg-slate-800/50 rounded">
                            <div class="text-xs text-slate-500">Axis</div>
                            <div class="font-bold text-brand-rose">${map.axisWins}</div>
                        </div>
                    </div>
                </div>
            </div>
            `;
            grid.insertAdjacentHTML('beforeend', html);
        });
    } catch (e) {
        console.error('Failed to load maps:', e);
        grid.innerHTML = '<div class="text-center text-red-500 py-12">Failed to load map statistics</div>';
    }
}

/**
 * Load weapons statistics view
 */
export async function loadWeaponsView() {
    const grid = document.getElementById('weapons-grid');
    if (!grid) return;

    grid.innerHTML = '<div class="text-center py-12"><i data-lucide="loader" class="w-8 h-8 text-brand-rose animate-spin mx-auto mb-4"></i><div class="text-slate-400">Loading weapon statistics...</div></div>';
    if (typeof lucide !== 'undefined') lucide.createIcons();

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
        'Support': 'brand-emerald'
    };

    try {
        const weapons = await fetchJSON(`${API_BASE}/stats/weapons?limit=20`);
        grid.innerHTML = '';

        if (weapons.length === 0) {
            grid.innerHTML = '<div class="col-span-full text-center text-slate-500 py-12">No weapon data available</div>';
            return;
        }

        const totalKills = weapons.reduce((sum, w) => sum + w.kills, 0);

        weapons.forEach(weapon => {
            const weaponKey = weapon.name.toLowerCase().replace(' ', '');
            const category = weaponCategories[weaponKey] || 'Other';
            const color = categoryColors[category] || 'brand-cyan';
            const usage = totalKills > 0 ? ((weapon.kills / totalKills) * 100).toFixed(1) : 0;
            const safeWeaponName = escapeHtml(weapon.name);
            const safeCategory = escapeHtml(category);

            const html = `
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
                        <span class="font-bold text-white">${weapon.kills.toLocaleString()}</span>
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
            grid.insertAdjacentHTML('beforeend', html);
        });
        if (typeof lucide !== 'undefined') lucide.createIcons();
    } catch (e) {
        console.error('Failed to load weapons:', e);
        grid.innerHTML = '<div class="col-span-full text-center text-red-500 py-12">Failed to load weapon statistics</div>';
    }
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
                <div class="text-center">
                    <div class="text-xs text-slate-500 uppercase mb-1">Allies</div>
                    <div class="flex items-center gap-2">
                        ${team1.is_winner ? '<span class="text-brand-gold">🏆</span>' : ''}
                        <span class="text-3xl font-black ${team1Color}">${team1.totals.kills}</span>
                    </div>
                    <div class="text-xs text-slate-500">${(team1.totals.damage / 1000).toFixed(1)}k dmg</div>
                </div>
                <div class="text-4xl font-black text-slate-600">:</div>
                <div class="text-center">
                    <div class="text-xs text-slate-500 uppercase mb-1">Axis</div>
                    <div class="flex items-center gap-2">
                        <span class="text-3xl font-black ${team2Color}">${team2.totals.kills}</span>
                        ${team2.is_winner ? '<span class="text-brand-gold">🏆</span>' : ''}
                    </div>
                    <div class="text-xs text-slate-500">${(team2.totals.damage / 1000).toFixed(1)}k dmg</div>
                </div>
            </div>

            <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div class="glass-card p-3 rounded-xl text-center">
                    <div class="text-[10px] text-slate-500 uppercase font-bold">Duration</div>
                    <div class="text-xl font-black text-white">${escapeHtml(m.duration || '0:00')}</div>
                </div>
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
                    <table class="w-full text-sm">
                        <thead>
                            <tr class="text-[10px] text-slate-500 uppercase bg-slate-900/50">
                                <th class="text-left py-2 px-3 font-bold">Name</th>
                                <th class="text-right py-2 px-2 font-bold">KDR</th>
                                <th class="text-right py-2 px-2 font-bold">K</th>
                                <th class="text-right py-2 px-2 font-bold">D</th>
                                <th class="text-right py-2 px-2 font-bold">DMG</th>
                                <th class="text-right py-2 px-2 font-bold">DPM</th>
                                <th class="text-right py-2 px-2 font-bold">HS</th>
                                <th class="text-right py-2 px-2 font-bold">GIBS</th>
                                <th class="text-right py-2 px-2 font-bold">REV</th>
                                <th class="text-right py-2 px-2 font-bold">ACC</th>
                            </tr>
                        </thead>
                        <tbody>
            `;

            players.forEach((player, index) => {
                const isTop = index === 0;
                const rowBg = isTop ? 'bg-brand-gold/5' : '';
                const safeName = escapeHtml(player.name);
                const jsName = escapeJsString(player.name);
                const kdColor = player.kd >= 2.0 ? 'text-brand-emerald' : player.kd >= 1.0 ? 'text-white' : 'text-brand-rose';

                html += `
                    <tr class="border-b border-white/5 hover:bg-white/5 transition ${rowBg}">
                        <td class="py-2 px-3">
                            <div class="flex items-center gap-2">
                                ${isTop ? '<span class="text-brand-gold">🏆</span>' : ''}
                                <span class="cursor-pointer hover:text-${teamColor} transition font-medium ${isTop ? 'text-brand-gold' : 'text-white'}"
                                      onclick="closeModal('modal-match-details'); loadPlayerProfile('${jsName}')">${safeName}</span>
                            </div>
                        </td>
                        <td class="text-right py-2 px-2 font-mono ${kdColor} font-bold">${player.kd.toFixed(2)}</td>
                        <td class="text-right py-2 px-2 font-mono text-brand-emerald">${player.kills}</td>
                        <td class="text-right py-2 px-2 font-mono text-slate-400">${player.deaths}</td>
                        <td class="text-right py-2 px-2 font-mono text-brand-purple">${player.damage_given.toLocaleString()}</td>
                        <td class="text-right py-2 px-2 font-mono text-brand-cyan font-bold">${player.dpm}</td>
                        <td class="text-right py-2 px-2 font-mono text-slate-300">${player.headshots}</td>
                        <td class="text-right py-2 px-2 font-mono text-slate-300">${player.gibs || 0}</td>
                        <td class="text-right py-2 px-2 font-mono text-brand-emerald">${player.revives || 0}</td>
                        <td class="text-right py-2 px-2 font-mono text-slate-300">${player.accuracy}%</td>
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

// Expose to window for onclick handlers in HTML
window.loadMatchDetails = loadMatchDetails;
window.loadMatchAwards = loadMatchAwards;
window.switchMatchTab = switchMatchTab;
