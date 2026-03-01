/**
 * Hall of Fame Module
 * Top players across 12 stat categories with period filtering.
 * @module hall-of-fame
 */

import { API_BASE, fetchJSON, escapeHtml, formatNumber } from './utils.js';
import { PageHeader, PodiumCard, LoadingSkeleton, EmptyState } from './components.js';
import { renderFilterBar, getFilterState, onFilterChange } from './filters.js';

// Category metadata: key, label, icon SVG, accent color
const CATEGORIES = [
    { key: 'most_active',          label: 'Most Active',           accent: 'cyan',    icon: `<svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>` },
    { key: 'most_wins',            label: 'Most Wins',             accent: 'gold',    icon: `<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M5 16L3 5l5.5 5L12 4l3.5 6L21 5l-2 11H5zm14 3c0 .6-.4 1-1 1H6c-.6 0-1-.4-1-1v-1h14v1z"/></svg>` },
    { key: 'most_damage',          label: 'Most Damage',           accent: 'rose',    icon: `<svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z"/></svg>` },
    { key: 'most_kills',           label: 'Most Kills',            accent: 'red',     icon: `<svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>` },
    { key: 'most_revives',         label: 'Most Revives',          accent: 'emerald', icon: `<svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"/></svg>` },
    { key: 'most_xp',              label: 'Most XP',               accent: 'purple',  icon: `<svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"/></svg>` },
    { key: 'most_assists',         label: 'Most Assists',          accent: 'blue',    icon: `<svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/></svg>` },
    { key: 'most_dpm',             label: 'Most DPM',              accent: 'amber',   icon: `<svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/></svg>` },
    { key: 'most_deaths',          label: 'Most Deaths',           accent: 'slate',   icon: `<svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M12 2a10 10 0 100 20 10 10 0 000-20z"/></svg>` },
    { key: 'most_selfkills',       label: 'Most Selfkills',        accent: 'orange',  icon: `<svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01M12 2a10 10 0 100 20 10 10 0 000-20z"/></svg>` },
    { key: 'most_full_selfkills',  label: 'Most Full Selfkills',   accent: 'red',     icon: `<svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"/></svg>` },
    { key: 'most_consecutive_games', label: 'Longest Streak',      accent: 'cyan',    icon: `<svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/></svg>` },
];

let _filterUnsub = null;

/**
 * Main entry point — called by app.js navigateTo('hall-of-fame').
 */
export async function loadHallOfFameView() {
    const container = document.getElementById('hall-of-fame-container');
    if (!container) return;

    // Render page shell: header + filter bar + grid placeholder
    container.innerHTML = `
        ${PageHeader('Hall of Fame', 'Top players across every stat category')}
        <div id="hof-filter-bar" class="mb-6"></div>
        <div id="hof-grid" class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            ${LoadingSkeleton('card', 12)}
        </div>
    `;

    // Render filter bar
    renderFilterBar('hof-filter-bar', {
        showSeason: false,
        periods: ['all', 'season', '7d', '14d', '30d', '90d'],
    });

    // Unsubscribe previous listener if view was re-entered
    if (_filterUnsub) _filterUnsub();
    _filterUnsub = onFilterChange(() => fetchAndRender());

    await fetchAndRender();
}

/**
 * Map filter state to API query params.
 */
function buildApiUrl() {
    const state = getFilterState();
    const params = new URLSearchParams();

    // Map filter value → API period param
    const periodMap = {
        'all': 'all_time',
        'season': 'season',
        '7d': '7d',
        '14d': '14d',
        '30d': '30d',
        '90d': '90d',
        'custom': 'custom',
    };
    params.set('period', periodMap[state.period] || 'all_time');

    if (state.period === 'custom' && state.dateFrom) params.set('start_date', state.dateFrom);
    if (state.period === 'custom' && state.dateTo) params.set('end_date', state.dateTo);
    if (state.season) params.set('season_id', state.season);

    params.set('limit', '50');

    return `${API_BASE}/hall-of-fame?${params.toString()}`;
}

/**
 * Fetch data and render all category cards.
 */
async function fetchAndRender() {
    const grid = document.getElementById('hof-grid');
    if (!grid) return;

    // Show loading skeletons
    grid.innerHTML = LoadingSkeleton('card', 12);

    try {
        const data = await fetchJSON(buildApiUrl());

        if (!data || !data.categories) {
            grid.innerHTML = `<div class="col-span-full">${EmptyState('No data available for this period')}</div>`;
            return;
        }

        grid.innerHTML = CATEGORIES.map(cat => {
            const entries = data.categories[cat.key] || [];
            return renderCategoryCard(cat, entries);
        }).join('');

        // Wire expand buttons
        wireExpandButtons(grid);

    } catch (err) {
        console.error('Hall of Fame fetch failed:', err);
        grid.innerHTML = `<div class="col-span-full">${EmptyState('Failed to load Hall of Fame data')}</div>`;
    }
}

/**
 * Render a single category card with podium + expandable list.
 */
function renderCategoryCard(cat, entries) {
    if (entries.length === 0) {
        return `
            <div class="glass-card rounded-xl p-5">
                <div class="flex items-center gap-2.5 mb-4">
                    <span class="text-brand-${cat.accent}/70">${cat.icon}</span>
                    <h3 class="text-sm font-bold text-white">${escapeHtml(cat.label)}</h3>
                </div>
                ${EmptyState('No data for this period')}
            </div>`;
    }

    const top3 = entries.slice(0, 3);
    const rest = entries.slice(3, 50);
    const expandId = 'hof-expand-' + cat.key;

    // Podium for top 3
    const podiumHtml = `
        <div class="grid grid-cols-3 gap-2 mb-3">
            ${top3.map(entry => PodiumCard({
                rank: entry.rank,
                name: entry.player_name,
                value: cat.key === 'most_dpm' ? entry.value : formatNumber(entry.value),
                unit: entry.unit,
            })).join('')}
        </div>`;

    // Expandable list for 4–50
    let listHtml = '';
    if (rest.length > 0) {
        const initialShow = Math.min(rest.length, 7);
        const visibleItems = rest.slice(0, initialShow);
        const hiddenItems = rest.slice(initialShow);

        listHtml = `<div class="border-t border-white/5 pt-3 mt-1">`;
        listHtml += `<div class="space-y-1">`;
        visibleItems.forEach(entry => {
            listHtml += renderListRow(entry, cat.key === 'most_dpm');
        });
        if (hiddenItems.length > 0) {
            hiddenItems.forEach(entry => {
                listHtml += `<div class="hidden" data-expand-group="${expandId}">${renderListRow(entry, cat.key === 'most_dpm')}</div>`;
            });
            listHtml += `</div>`;
            listHtml += `<button data-expand-btn="${expandId}"
                class="mt-2 text-xs font-bold text-brand-cyan hover:text-white transition cursor-pointer">
                Show ${hiddenItems.length} more
            </button>`;
        } else {
            listHtml += `</div>`;
        }
        listHtml += `</div>`;
    }

    return `
        <div class="glass-card rounded-xl p-5">
            <div class="flex items-center gap-2.5 mb-4">
                <span class="text-brand-${cat.accent}/70">${cat.icon}</span>
                <h3 class="text-sm font-bold text-white">${escapeHtml(cat.label)}</h3>
            </div>
            ${podiumHtml}
            ${listHtml}
        </div>`;
}

/**
 * Render a compact row for ranks 4+.
 */
function renderListRow(entry, isDpm) {
    const val = isDpm ? entry.value : formatNumber(entry.value);
    return `
        <div class="flex items-center justify-between py-1.5 px-2 rounded hover:bg-white/5 transition">
            <div class="flex items-center gap-2.5 min-w-0">
                <span class="text-[11px] font-mono text-slate-600 w-5 text-right shrink-0">${escapeHtml(String(entry.rank))}</span>
                <span class="text-sm text-slate-300 truncate">${escapeHtml(entry.player_name)}</span>
            </div>
            <span class="text-sm font-mono font-bold text-white shrink-0 ml-3">${escapeHtml(String(val))}</span>
        </div>`;
}

/**
 * Wire "Show N more" expand buttons.
 */
function wireExpandButtons(container) {
    container.querySelectorAll('[data-expand-btn]').forEach(btn => {
        btn.addEventListener('click', () => {
            const groupId = btn.dataset.expandBtn;
            container.querySelectorAll(`[data-expand-group="${groupId}"]`).forEach(el => {
                el.classList.remove('hidden');
            });
            btn.remove();
        });
    });
}
