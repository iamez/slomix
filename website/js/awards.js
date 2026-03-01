/**
 * Awards module - Round awards and player leaderboard
 * @module awards
 */

import { API_BASE, fetchJSON, escapeHtml, escapeJsString, formatNumber } from './utils.js';

// State
let currentTab = 'round';
let currentPage = 0;
const pageSize = 20;

// Award category styling - matches backend categories
const AWARD_CATEGORIES = {
    'combat': { emoji: '⚔️', color: 'text-brand-rose', bg: 'bg-brand-rose/10' },
    'deaths': { emoji: '💀', color: 'text-slate-400', bg: 'bg-slate-700/50' },
    'skills': { emoji: '🎯', color: 'text-brand-purple', bg: 'bg-brand-purple/10' },
    'weapons': { emoji: '🔫', color: 'text-brand-blue', bg: 'bg-brand-blue/10' },
    'teamwork': { emoji: '🤝', color: 'text-brand-emerald', bg: 'bg-brand-emerald/10' },
    'objectives': { emoji: '🚩', color: 'text-brand-gold', bg: 'bg-brand-gold/10' },
    'timing': { emoji: '⏱️', color: 'text-brand-cyan', bg: 'bg-brand-cyan/10' }
};

/**
 * Load the awards view
 */
export async function loadAwardsView() {
    const typeFilter = document.getElementById('awards-type-filter');
    const timeFilter = document.getElementById('awards-time-filter');

    // Set up filter listeners if not already done
    if (typeFilter && !typeFilter.dataset.listenerAttached) {
        typeFilter.addEventListener('change', () => {
            currentPage = 0;
            loadCurrentTab();
        });
        typeFilter.dataset.listenerAttached = 'true';

        // Populate award types
        await loadAwardTypes(typeFilter);
    }

    if (timeFilter && !timeFilter.dataset.listenerAttached) {
        timeFilter.addEventListener('change', () => {
            currentPage = 0;
            loadCurrentTab();
        });
        timeFilter.dataset.listenerAttached = 'true';
    }

    await loadCurrentTab();
}

/**
 * Load award types for filter dropdown
 */
async function loadAwardTypes(selectElement) {
    try {
        const data = await fetchJSON(`${API_BASE}/awards?limit=1`);
        // Get unique award types from leaderboard
        const leaderboard = await fetchJSON(`${API_BASE}/awards/leaderboard?limit=100`);

        // Build unique award names from the data
        const awardTypes = new Set();
        if (leaderboard && leaderboard.leaderboard) {
            leaderboard.leaderboard.forEach(p => {
                if (p.favorite_award) awardTypes.add(p.favorite_award);
            });
        }

        // Add common award types
        const commonAwards = [
            'Most damage given', 'Best K/D ratio', 'Most kills', 'Most deaths',
            'Most selfkills', 'Most revives', 'Most headshots', 'Best accuracy',
            'Most gibs', 'First blood', 'Most dynamite planted', 'Most dynamite defused'
        ];
        commonAwards.forEach(a => awardTypes.add(a));

        const currentVal = selectElement.value;
        selectElement.innerHTML = '<option value="">All Awards</option>' +
            Array.from(awardTypes).sort().map(t =>
                `<option value="${escapeHtml(t)}">${escapeHtml(t)}</option>`
            ).join('');
        selectElement.value = currentVal;
    } catch (e) {
        console.error('Failed to load award types:', e);
    }
}

/**
 * Switch between tabs
 */
export function switchAwardsTab(tab) {
    currentTab = tab;
    currentPage = 0;

    // Update tab button styles
    document.querySelectorAll('.awards-tab-btn').forEach(btn => {
        btn.classList.remove('bg-brand-blue', 'text-white');
        btn.classList.add('bg-slate-700', 'text-slate-300', 'hover:bg-slate-600');
    });

    const activeBtn = document.getElementById(`awards-tab-${tab}`);
    if (activeBtn) {
        activeBtn.classList.remove('bg-slate-700', 'text-slate-300', 'hover:bg-slate-600');
        activeBtn.classList.add('bg-brand-blue', 'text-white');
    }

    loadCurrentTab();
}

/**
 * Load current tab content
 */
async function loadCurrentTab() {
    if (currentTab === 'round') {
        await loadByRoundView();
    } else {
        await loadByPlayerView();
    }
}

/**
 * Load "By Round" view - shows recent rounds with their awards
 */
async function loadByRoundView() {
    const container = document.getElementById('awards-content');
    const countEl = document.getElementById('awards-count');
    const pagination = document.getElementById('awards-pagination');

    if (!container) return;

    // Show loading
    container.innerHTML = `
        <div class="text-center py-12">
            <i data-lucide="loader" class="w-8 h-8 animate-spin mx-auto mb-4 text-brand-blue"></i>
            <p class="text-slate-400">Loading awards by round...</p>
        </div>
    `;
    if (typeof lucide !== 'undefined') lucide.createIcons();

    try {
        const timeFilter = document.getElementById('awards-time-filter');
        const typeFilter = document.getElementById('awards-type-filter');

        const days = timeFilter?.value || '';
        const awardType = typeFilter?.value || '';

        let url = `${API_BASE}/awards?limit=${pageSize}&offset=${currentPage * pageSize}`;
        if (days) url += `&days=${days}`;
        if (awardType) url += `&award_type=${encodeURIComponent(awardType)}`;

        const data = await fetchJSON(url);

        if (!data || !data.awards || data.awards.length === 0) {
            container.innerHTML = `
                <div class="text-center py-12 text-slate-500">
                    <i data-lucide="trophy" class="w-12 h-12 mx-auto mb-4 opacity-30"></i>
                    <p>No awards found for this selection.</p>
                </div>
            `;
            if (countEl) countEl.textContent = '0 awards';
            if (pagination) pagination.classList.add('hidden');
            if (typeof lucide !== 'undefined') lucide.createIcons();
            return;
        }

        if (countEl) countEl.textContent = `${formatNumber(data.total)} awards`;

        // Group awards by round
        const roundsMap = new Map();
        data.awards.forEach(award => {
            const key = `${award.date}-${award.map}-${award.round_number}`;
            if (!roundsMap.has(key)) {
                roundsMap.set(key, {
                    round_id: award.round_id,
                    round_date: award.date,
                    map_name: award.map,
                    round_number: award.round_number,
                    awards: []
                });
            }
            roundsMap.get(key).awards.push(award);
        });

        // Render rounds
        let html = '<div class="space-y-6">';

        roundsMap.forEach((round, key) => {
            const dateStr = new Date(round.round_date).toLocaleDateString('en-US', {
                weekday: 'short', month: 'short', day: 'numeric'
            });

            html += `
                <div class="glass-card rounded-xl overflow-hidden">
                    <div class="bg-slate-800/50 px-6 py-4 flex items-center justify-between border-b border-white/5">
                        <div class="flex items-center gap-4">
                            <div class="w-10 h-10 rounded-lg bg-brand-blue/20 flex items-center justify-center">
                                <i data-lucide="map" class="w-5 h-5 text-brand-blue"></i>
                            </div>
                            <div>
                                <div class="font-bold text-white">${escapeHtml(round.map_name)}</div>
                                <div class="text-xs text-slate-500">Round ${round.round_number} • ${dateStr}</div>
                            </div>
                        </div>
                        <div class="text-sm text-slate-400">${round.awards.length} awards</div>
                    </div>
                    <div class="p-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            `;

            round.awards.forEach(award => {
                const cat = getCategoryForAward(award.award);
                const style = AWARD_CATEGORIES[cat] || AWARD_CATEGORIES['combat'];

                html += `
                    <div class="flex items-center gap-3 p-3 rounded-lg ${style.bg} border border-white/5">
                        <span class="text-lg">${style.emoji}</span>
                        <div class="flex-1 min-w-0">
                            <div class="text-xs text-slate-400 truncate">${escapeHtml(award.award)}</div>
                            <div class="font-bold text-white truncate">${escapeHtml(award.player)}</div>
                        </div>
                        <div class="text-sm font-mono ${style.color}">${escapeHtml(award.value)}</div>
                    </div>
                `;
            });

            html += `
                    </div>
                </div>
            `;
        });

        html += '</div>';
        container.innerHTML = html;

        // Render pagination
        renderPagination(data.total);

        if (typeof lucide !== 'undefined') lucide.createIcons();

    } catch (e) {
        console.error('Failed to load awards by round:', e);
        container.innerHTML = `
            <div class="text-center py-12 text-red-500">
                <i data-lucide="alert-circle" class="w-12 h-12 mx-auto mb-4"></i>
                <p>Failed to load awards.</p>
            </div>
        `;
        if (typeof lucide !== 'undefined') lucide.createIcons();
    }
}

/**
 * Load "By Player" view - leaderboard of award winners
 */
async function loadByPlayerView() {
    const container = document.getElementById('awards-content');
    const countEl = document.getElementById('awards-count');
    const pagination = document.getElementById('awards-pagination');

    if (!container) return;

    // Show loading
    container.innerHTML = `
        <div class="text-center py-12">
            <i data-lucide="loader" class="w-8 h-8 animate-spin mx-auto mb-4 text-brand-blue"></i>
            <p class="text-slate-400">Loading award leaderboard...</p>
        </div>
    `;
    if (typeof lucide !== 'undefined') lucide.createIcons();

    try {
        const timeFilter = document.getElementById('awards-time-filter');
        const typeFilter = document.getElementById('awards-type-filter');

        const days = timeFilter?.value || '';
        const awardType = typeFilter?.value || '';

        let url = `${API_BASE}/awards/leaderboard?limit=50`;
        if (days) url += `&days=${days}`;
        if (awardType) url += `&award_type=${encodeURIComponent(awardType)}`;

        const data = await fetchJSON(url);

        if (!data || !data.leaderboard || data.leaderboard.length === 0) {
            container.innerHTML = `
                <div class="text-center py-12 text-slate-500">
                    <i data-lucide="users" class="w-12 h-12 mx-auto mb-4 opacity-30"></i>
                    <p>No player awards found for this selection.</p>
                </div>
            `;
            if (countEl) countEl.textContent = '0 players';
            if (pagination) pagination.classList.add('hidden');
            if (typeof lucide !== 'undefined') lucide.createIcons();
            return;
        }

        if (countEl) countEl.textContent = `${data.leaderboard.length} players`;
        if (pagination) pagination.classList.add('hidden');

        // Render leaderboard table
        let html = `
            <div class="glass-card rounded-xl overflow-hidden">
                <div class="overflow-x-auto">
                    <table class="w-full">
                        <thead class="bg-slate-800/50 border-b border-white/10">
                            <tr>
                                <th class="px-6 py-4 text-left text-xs font-bold text-slate-400 uppercase tracking-wider">Rank</th>
                                <th class="px-6 py-4 text-left text-xs font-bold text-slate-400 uppercase tracking-wider">Player</th>
                                <th class="px-6 py-4 text-center text-xs font-bold text-slate-400 uppercase tracking-wider">Total Awards</th>
                                <th class="px-6 py-4 text-left text-xs font-bold text-slate-400 uppercase tracking-wider">Most Won Award</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-white/5">
        `;

        data.leaderboard.forEach((player, index) => {
            const rank = index + 1;
            let rankStyle = 'text-slate-400';
            let rankBadge = '';

            if (rank === 1) {
                rankStyle = 'text-brand-gold';
                rankBadge = '<span class="ml-1">🥇</span>';
            } else if (rank === 2) {
                rankStyle = 'text-slate-300';
                rankBadge = '<span class="ml-1">🥈</span>';
            } else if (rank === 3) {
                rankStyle = 'text-amber-600';
                rankBadge = '<span class="ml-1">🥉</span>';
            }

            const initials = player.player.substring(0, 2).toUpperCase();

            html += `
                <tr class="hover:bg-white/5 transition cursor-pointer" onclick="loadPlayerProfile('${escapeJsString(player.player)}')">
                    <td class="px-6 py-4">
                        <span class="font-mono font-bold ${rankStyle}">#${rank}${rankBadge}</span>
                    </td>
                    <td class="px-6 py-4">
                        <div class="flex items-center gap-3">
                            <div class="w-8 h-8 rounded bg-slate-800 flex items-center justify-center text-xs font-bold text-slate-400">
                                ${escapeHtml(initials)}
                            </div>
                            <span class="font-bold text-white hover:text-brand-blue transition">${escapeHtml(player.player)}</span>
                        </div>
                    </td>
                    <td class="px-6 py-4 text-center">
                        <span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-bold bg-brand-blue/20 text-brand-blue">
                            🏆 ${player.award_count}
                        </span>
                    </td>
                    <td class="px-6 py-4">
                        <span class="text-sm text-slate-300">${escapeHtml(player.top_award || '-')}</span>
                        ${player.top_award_count ? `<span class="text-xs text-slate-500 ml-1">(${player.top_award_count}x)</span>` : ''}
                    </td>
                </tr>
            `;
        });

        html += `
                        </tbody>
                    </table>
                </div>
            </div>
        `;

        container.innerHTML = html;
        if (typeof lucide !== 'undefined') lucide.createIcons();

    } catch (e) {
        console.error('Failed to load award leaderboard:', e);
        container.innerHTML = `
            <div class="text-center py-12 text-red-500">
                <i data-lucide="alert-circle" class="w-12 h-12 mx-auto mb-4"></i>
                <p>Failed to load leaderboard.</p>
            </div>
        `;
        if (typeof lucide !== 'undefined') lucide.createIcons();
    }
}

/**
 * Determine category for an award name
 */
function getCategoryForAward(awardName) {
    const name = awardName.toLowerCase();

    if (name.includes('damage') || name.includes('k/d') || name.includes('kills')) return 'combat';
    if (name.includes('death') || name.includes('selfkill') || name.includes('gib')) return 'deaths';
    if (name.includes('headshot') || name.includes('accuracy') || name.includes('first blood')) return 'skills';
    if (name.includes('smg') || name.includes('rifle') || name.includes('pistol') || name.includes('grenade') || name.includes('knife')) return 'weapons';
    if (name.includes('revive') || name.includes('heal') || name.includes('ammo')) return 'teamwork';
    if (name.includes('dynamite') || name.includes('objective') || name.includes('planted') || name.includes('defused')) return 'objectives';
    if (name.includes('time') || name.includes('playtime')) return 'timing';

    return 'combat'; // default
}

/**
 * Render pagination controls
 */
function renderPagination(total) {
    const pagination = document.getElementById('awards-pagination');
    if (!pagination) return;

    const totalPages = Math.ceil(total / pageSize);

    if (totalPages <= 1) {
        pagination.classList.add('hidden');
        return;
    }

    pagination.classList.remove('hidden');

    let html = '';

    // Previous button
    if (currentPage > 0) {
        html += `
            <button onclick="changeAwardsPage(${currentPage - 1})"
                class="px-4 py-2 rounded-lg bg-slate-700 text-white hover:bg-slate-600 transition">
                <i data-lucide="chevron-left" class="w-4 h-4"></i>
            </button>
        `;
    }

    // Page numbers
    const startPage = Math.max(0, currentPage - 2);
    const endPage = Math.min(totalPages - 1, currentPage + 2);

    for (let i = startPage; i <= endPage; i++) {
        const isActive = i === currentPage;
        html += `
            <button onclick="changeAwardsPage(${i})"
                class="px-4 py-2 rounded-lg font-bold transition ${isActive ? 'bg-brand-blue text-white' : 'bg-slate-700 text-slate-300 hover:bg-slate-600'}">
                ${i + 1}
            </button>
        `;
    }

    // Next button
    if (currentPage < totalPages - 1) {
        html += `
            <button onclick="changeAwardsPage(${currentPage + 1})"
                class="px-4 py-2 rounded-lg bg-slate-700 text-white hover:bg-slate-600 transition">
                <i data-lucide="chevron-right" class="w-4 h-4"></i>
            </button>
        `;
    }

    pagination.innerHTML = html;
    if (typeof lucide !== 'undefined') lucide.createIcons();
}

/**
 * Change to a specific page
 */
export function changeAwardsPage(page) {
    currentPage = page;
    loadCurrentTab();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// Expose to window for onclick handlers in HTML
window.loadAwardsView = loadAwardsView;
window.switchAwardsTab = switchAwardsTab;
window.changeAwardsPage = changeAwardsPage;
