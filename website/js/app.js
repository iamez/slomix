/**
 * Slomix ET:Legacy Statistics Website
 * Main Application Entry Point
 *
 * This is the main entry point that imports and coordinates all modules.
 * Architecture: ES6 Modules for clean separation of concerns.
 */

// ============================================================================
// IMPORTS
// ============================================================================

import { API_BASE, fetchJSON, formatNumber, escapeHtml } from './utils.js';
import { checkLoginStatus, initSearchListeners, setLoadPlayerProfile } from './auth.js';
import { initLivePolling, initLiveStatusPolling, updateLiveSession } from './live-status.js';
import { loadPlayerProfile, setNavigateTo as setProfileNavigateTo, setLoadMatchDetails } from './player-profile.js';
import { loadLeaderboard, loadQuickLeaders, loadRecentMatches, setNavigateTo as setLeaderboardNavigateTo, initLeaderboardDefaults } from './leaderboard.js';
import { loadSeasonInfo, loadLastSession, loadSessionsView, loadSessionMVP, toggleSeasonDetails } from './sessions.js';
import { loadMatchesView, loadMapsView, loadWeaponsView, loadMatchDetails } from './matches.js';
import { loadCommunityView } from './community.js';
import { loadRecordsView } from './records.js';
import { loadAwardsView } from './awards.js';
import { loadProximityView } from './proximity.js';
import { loadAdminPanelView } from './admin-panel.js';
import { loadUploadsView, loadUploadDetail } from './uploads.js';
import { loadAvailabilityView } from './availability.js';
import {
    initGreatshotModule,
    loadGreatshotView,
    loadGreatshotDemoDetail,
} from './greatshot.js';
import './compare.js'; // Self-registers to window
import { getBadgesForPlayer, renderBadges, renderBadge } from './badges.js';
import { loadSeasonLeaders, loadActivityCalendar, loadSeasonSummary } from './season-stats.js';
import { loadHallOfFameView } from './hall-of-fame.js';
import { loadRetroVizView } from './retro-viz.js';

// ============================================================================
// NAVIGATION
// ============================================================================

const PROTOTYPE_TONE_STYLES = {
    amber: {
        border: 'border-brand-amber/30',
        bg: 'bg-brand-amber/10',
        text: 'text-brand-amber',
        icon: 'flask-conical'
    },
    cyan: {
        border: 'border-brand-cyan/30',
        bg: 'bg-brand-cyan/10',
        text: 'text-brand-cyan',
        icon: 'radar'
    },
    rose: {
        border: 'border-brand-rose/30',
        bg: 'bg-brand-rose/10',
        text: 'text-brand-rose',
        icon: 'alert-triangle'
    },
    emerald: {
        border: 'border-brand-emerald/30',
        bg: 'bg-brand-emerald/10',
        text: 'text-brand-emerald',
        icon: 'badge-check'
    }
};

function parseHashRoute() {
    const cleanHash = window.location.hash.replace(/^#\/?/, '');
    if (!cleanHash) return { viewId: 'home', params: {} };
    const routePath = cleanHash.split('?')[0];

    const segments = routePath.split('/').filter(Boolean);
    if (segments[0] === 'greatshot') {
        if (segments[1] === 'demo' && segments[2]) {
            return {
                viewId: 'greatshot-demo',
                params: { demoId: decodeURIComponent(segments[2]) }
            };
        }
        const section = ['demos', 'highlights', 'clips', 'renders'].includes(segments[1] || '')
            ? segments[1]
            : 'demos';
        return {
            viewId: 'greatshot',
            params: { section }
        };
    }

    if (segments[0] === 'uploads' && segments[1]) {
        return {
            viewId: 'upload-detail',
            params: { uploadId: decodeURIComponent(segments[1]) }
        };
    }

    return { viewId: segments[0] || 'home', params: {} };
}

function initNavDropdowns() {
    const toggles = document.querySelectorAll('[data-nav-menu-toggle]');

    const closeMenu = (toggle, menu) => {
        toggle.setAttribute('aria-expanded', 'false');
        menu.classList.add('hidden');
        menu.querySelectorAll('[role="menuitem"]').forEach((item) => {
            item.tabIndex = -1;
        });
    };

    const openMenu = (toggle, menu) => {
        toggle.setAttribute('aria-expanded', 'true');
        menu.classList.remove('hidden');
        menu.querySelectorAll('[role="menuitem"]').forEach((item) => {
            item.tabIndex = 0;
        });
    };

    const closeAll = () => {
        toggles.forEach((toggle) => {
            const menuId = toggle.getAttribute('aria-controls');
            const menu = menuId ? document.getElementById(menuId) : null;
            if (menu) closeMenu(toggle, menu);
        });
    };

    toggles.forEach((toggle) => {
        const menuId = toggle.getAttribute('aria-controls');
        const menu = menuId ? document.getElementById(menuId) : null;
        if (!menu) return;

        closeMenu(toggle, menu);

        toggle.addEventListener('click', (event) => {
            event.stopPropagation();
            const isOpen = toggle.getAttribute('aria-expanded') === 'true';
            closeAll();
            if (!isOpen) {
                openMenu(toggle, menu);
                const first = menu.querySelector('[role="menuitem"]');
                if (first) first.focus();
            }
        });

        toggle.addEventListener('keydown', (event) => {
            if (event.key === 'ArrowDown') {
                event.preventDefault();
                openMenu(toggle, menu);
                const first = menu.querySelector('[role="menuitem"]');
                if (first) first.focus();
            } else if (event.key === 'Escape') {
                closeMenu(toggle, menu);
                toggle.focus();
            }
        });
    });

    document.addEventListener('click', closeAll);
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') closeAll();
    });
}

function renderPrototypeBanner(viewElement) {
    if (!viewElement) return;

    const isPrototype = viewElement.dataset.prototype === 'true';
    const slot = viewElement.querySelector('[data-prototype-slot]');
    const existing = slot ? slot.querySelector('.prototype-banner') : null;

    if (!isPrototype) {
        if (existing) existing.remove();
        return;
    }

    if (!slot) return;

    const title = viewElement.dataset.prototypeTitle || 'Prototype';
    const message = viewElement.dataset.prototypeMessage || 'This view is still under active development.';
    const toneKey = viewElement.dataset.prototypeTone || 'amber';
    const tone = PROTOTYPE_TONE_STYLES[toneKey] || PROTOTYPE_TONE_STYLES.amber;

    const banner = document.createElement('div');
    banner.className = `prototype-banner glass-panel ${tone.border} ${tone.bg} border px-4 py-3 rounded-xl mb-6`;

    const row = document.createElement('div');
    row.className = 'flex items-start gap-3';

    const iconWrap = document.createElement('div');
    iconWrap.className = `${tone.text} mt-0.5`;
    const icon = document.createElement('i');
    icon.className = 'w-4 h-4';
    icon.setAttribute('data-lucide', tone.icon);
    iconWrap.appendChild(icon);

    const textWrap = document.createElement('div');
    const titleEl = document.createElement('div');
    titleEl.className = `text-[11px] font-bold uppercase ${tone.text} tracking-widest`;
    titleEl.textContent = title;
    const messageEl = document.createElement('div');
    messageEl.className = 'text-sm text-slate-300 mt-1';
    messageEl.textContent = message;
    textWrap.appendChild(titleEl);
    textWrap.appendChild(messageEl);

    row.appendChild(iconWrap);
    row.appendChild(textWrap);
    banner.appendChild(row);

    if (existing) {
        existing.replaceWith(banner);
    } else {
        slot.appendChild(banner);
    }

    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
}

/**
 * Navigate to a view section
 */
export function navigateTo(viewId, updateHistory = true, params = {}) {
    console.log('Navigating to:', viewId);

    // Hide all views
    document.querySelectorAll('.view-section').forEach(el => {
        el.classList.remove('active');
        el.classList.add('hidden');
    });

    // Show selected view
    const target = document.getElementById(`view-${viewId}`);
    if (target) {
        target.classList.add('active');
        target.classList.remove('hidden');
        renderPrototypeBanner(target);
    } else {
        console.error(`View not found: view-${viewId}`);
        return;
    }

    // Update Nav Links
    document.querySelectorAll('.nav-link').forEach(el => el.classList.remove('active'));
    const viewToNav = { 'greatshot-demo': 'greatshot', 'upload-detail': 'uploads', 'sessions': 'sessions-stats' };
    const navKey = viewToNav[viewId] || viewId;
    const statsViews = new Set(['sessions', 'leaderboards', 'maps', 'weapons', 'records', 'awards', 'retro-viz']);
    const activeKeys = [`link-${navKey}`];
    if (statsViews.has(viewId)) {
        activeKeys.push('link-stats');
    }
    activeKeys.forEach((id) => {
        const link = document.getElementById(id);
        if (link) link.classList.add('active');
    });

    // Update URL hash
    if (updateHistory) {
        let hash = '';
        if (viewId === 'upload-detail' && params.uploadId) {
            hash = `#/uploads/${encodeURIComponent(params.uploadId)}`;
        } else if (viewId === 'greatshot-demo' && params.demoId) {
            hash = `#/greatshot/demo/${encodeURIComponent(params.demoId)}`;
        } else if (viewId === 'greatshot') {
            const section = ['demos', 'highlights', 'clips', 'renders'].includes(params.section)
                ? params.section
                : 'demos';
            hash = `#/greatshot/${section}`;
        } else if (viewId !== 'home') {
            hash = `#/${viewId}`;
        }
        if (window.location.hash !== hash) {
            window.location.hash = hash;
            return;
        }
    }

    // Scroll to top
    window.scrollTo(0, 0);

    // Load view-specific data
    if (viewId === 'sessions') {
        loadSessionsView();
    } else if (viewId === 'matches') {
        loadMatchesView();
    } else if (viewId === 'community') {
        loadCommunityView();
    } else if (viewId === 'maps') {
        loadMapsView();
    } else if (viewId === 'leaderboards') {
        initLeaderboardDefaults();
    } else if (viewId === 'weapons') {
        loadWeaponsView();
    } else if (viewId === 'records') {
        loadRecordsView();
    } else if (viewId === 'awards') {
        loadAwardsView();
    } else if (viewId === 'proximity') {
        loadProximityView();
    } else if (viewId === 'greatshot') {
        loadGreatshotView(params.section || 'demos');
    } else if (viewId === 'greatshot-demo') {
        if (params.demoId) {
            loadGreatshotDemoDetail(params.demoId);
        }
    } else if (viewId === 'upload-detail') {
        if (params.uploadId) {
            loadUploadDetail(params.uploadId);
        }
    } else if (viewId === 'uploads') {
        loadUploadsView();
    } else if (viewId === 'availability') {
        loadAvailabilityView();
    } else if (viewId === 'admin') {
        loadAdminPanelView();
    } else if (viewId === 'hall-of-fame') {
        loadHallOfFameView();
    } else if (viewId === 'retro-viz') {
        loadRetroVizView();
    }
}

// Wire up navigation to modules that need it
setProfileNavigateTo(navigateTo);
setLeaderboardNavigateTo(navigateTo);
setLoadPlayerProfile(loadPlayerProfile);
setLoadMatchDetails(loadMatchDetails);

// Expose to window for onclick handlers in HTML
window.navigateTo = navigateTo;
window.loadPlayerProfile = loadPlayerProfile;
window.loadMatchDetails = loadMatchDetails;
window.loadLeaderboard = loadLeaderboard;
window.loadAwardsView = loadAwardsView;
window.getBadgesForPlayer = getBadgesForPlayer;
window.renderBadges = renderBadges;
window.renderBadge = renderBadge;
window.toggleSeasonDetails = toggleSeasonDetails;

// ============================================================================
// BROWSER HISTORY
// ============================================================================

window.addEventListener('hashchange', () => {
    const route = parseHashRoute();
    navigateTo(route.viewId, false, route.params);
});

// ============================================================================
// HOME PAGE STATS
// ============================================================================

/**
 * Load overview statistics for home page
 */
async function loadOverviewStats() {
    try {
        const data = await fetchJSON(`${API_BASE}/stats/overview`);

        const statRounds = document.getElementById('stat-rounds');
        const statPlayers = document.getElementById('stat-players');
        const statSessions = document.getElementById('stat-sessions');
        const statKills = document.getElementById('stat-kills');
        const roundsSince = document.getElementById('stat-rounds-since');
        const roundsRecent = document.getElementById('stat-rounds-14d');
        const playersAll = document.getElementById('stat-players-all');
        const sessionsRecent = document.getElementById('stat-sessions-14d');
        const killsRecent = document.getElementById('stat-kills-14d');
        const activeAll = document.getElementById('stat-active-all-name');
        const activeAllCount = document.getElementById('stat-active-all-count');
        const activeRecent = document.getElementById('stat-active-14d-name');
        const activeRecentCount = document.getElementById('stat-active-14d-count');

        const formatDateLabel = (raw) => {
            if (!raw) return '--';
            const parts = String(raw).split('-');
            if (parts.length !== 3) return raw;
            const [year, month, day] = parts;
            const date = new Date(`${year}-${month}-${day}T00:00:00`);
            if (Number.isNaN(date.getTime())) return raw;
            return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
        };

        if (statRounds) statRounds.textContent = formatNumber(data.rounds || 0);
        if (statPlayers) statPlayers.textContent = formatNumber(data.players_14d ?? data.players ?? 0);
        if (statSessions) statSessions.textContent = formatNumber(data.sessions || 0);
        if (statKills) statKills.textContent = formatNumber(data.total_kills || 0);

        if (roundsSince) roundsSince.textContent = data.rounds_since ? `Since ${formatDateLabel(data.rounds_since)}` : 'Since --';
        if (roundsRecent) roundsRecent.textContent = `Last ${data.window_days || 14}d: ${formatNumber(data.rounds_14d || 0)}`;
        if (playersAll) playersAll.textContent = `All-time: ${formatNumber(data.players_all_time || 0)}`;
        if (sessionsRecent) sessionsRecent.textContent = `Last ${data.window_days || 14}d: ${formatNumber(data.sessions_14d || 0)}`;
        if (killsRecent) killsRecent.textContent = `Last ${data.window_days || 14}d: ${formatNumber(data.total_kills_14d || 0)}`;

        if (activeAll) activeAll.textContent = data.most_active_overall?.name || '--';
        if (activeAllCount) activeAllCount.textContent = data.most_active_overall ? `${data.most_active_overall.rounds} rounds` : '-- rounds';
        if (activeRecent) activeRecent.textContent = data.most_active_14d?.name || '--';
        if (activeRecentCount) activeRecentCount.textContent = data.most_active_14d ? `${data.most_active_14d.rounds} rounds` : '-- rounds';
    } catch (e) {
        console.error('Failed to load overview stats:', e);
    }
}

/**
 * Load predictions widget
 */
async function loadPredictions() {
    try {
        const predictions = await fetchJSON(`${API_BASE}/predictions/recent?limit=3`);
        const container = document.getElementById('predictions-list');

        if (!container) return;

        if (!predictions || predictions.length === 0) {
            container.innerHTML = '<div class="text-center py-4 text-slate-500">No recent predictions</div>';
            return;
        }

        container.innerHTML = predictions.map(p => `
            <div class="glass-card p-4 rounded-lg">
                <div class="flex items-center justify-between mb-2">
                    <span class="text-xs text-slate-500">${escapeHtml(p.match_type)}</span>
                    <span class="text-xs ${p.correct ? 'text-brand-emerald' : 'text-brand-rose'}">${p.correct ? '✓' : '✗'}</span>
                </div>
                <div class="text-sm font-bold text-white">${escapeHtml(p.description || 'Match prediction')}</div>
            </div>
        `).join('');
    } catch (e) {
        console.error('Failed to load predictions:', e);
    }
}


// ============================================================================
// INSIGHTS CHARTS
// ============================================================================

/** Chart.js instances for insights strip */
let insightsRoundsChart = null;
let insightsPlayersChart = null;
let insightsMapsChart = null;

const INSIGHTS_MAP_STATE_MESSAGES = {
    loading: 'Loading map distribution...',
    empty: 'No data yet. No rounds recorded in this period.',
    error: 'Could not load map distribution right now.',
};

function setInsightsMapState(state, message = '') {
    const emptyEl = document.getElementById('insights-maps-empty');
    const canvas = document.getElementById('insights-maps-chart');
    if (!emptyEl || !canvas) return;

    const textEl = emptyEl.querySelector('p');
    const iconEl = emptyEl.querySelector('svg, i');

    if (state === 'ready') {
        emptyEl.classList.add('hidden');
        canvas.style.display = '';
    } else {
        emptyEl.classList.remove('hidden');
        canvas.style.display = 'none';
        if (textEl) {
            textEl.textContent = message || INSIGHTS_MAP_STATE_MESSAGES[state] || INSIGHTS_MAP_STATE_MESSAGES.empty;
        }
    }

    if (iconEl) {
        iconEl.classList.toggle('animate-spin', state === 'loading');
    }
}

/**
 * Load community insights charts from /api/stats/trends
 * @param {number} days - Timeframe in days (14, 30, 90)
 */
async function loadInsightsCharts(days = 14) {
    // Update timeframe button states
    document.querySelectorAll('.insights-tf-btn').forEach(btn => {
        const btnDays = parseInt(btn.dataset.days, 10);
        if (btnDays === days) {
            btn.className = 'insights-tf-btn px-2.5 py-1 rounded text-xs font-bold bg-brand-blue/20 text-brand-blue transition active';
        } else {
            btn.className = 'insights-tf-btn px-2.5 py-1 rounded text-xs font-bold bg-slate-700 text-slate-400 hover:bg-slate-600 transition';
        }
    });

    if (typeof Chart === 'undefined') {
        console.warn('Chart.js not loaded, skipping insights charts');
        showInsightsEmpty();
        setInsightsMapState('error', 'Chart rendering is unavailable.');
        return;
    }

    try {
        setInsightsMapState('loading');
        const data = await fetchJSON(`${API_BASE}/stats/trends?days=${days}`);
        if (!data || !data.dates) throw new Error('Invalid response');
        renderInsightsCharts(data, days);
    } catch (e) {
        console.warn('Insights endpoint not available:', e.message);
        showInsightsEmpty();
        setInsightsMapState('error');
    }
}

function showInsightsEmpty() {
    ['insights-rounds-empty', 'insights-players-empty', 'insights-maps-empty'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.classList.remove('hidden');
    });
    ['insights-rounds-chart', 'insights-players-chart', 'insights-maps-chart'].forEach(id => {
        const canvas = document.getElementById(id);
        if (canvas) canvas.style.display = 'none';
    });
    setInsightsMapState('empty');
}

function renderInsightsCharts(data, days) {
    // Show canvases for rounds/players and hide their empty states.
    // Map state is handled separately so we can show loading/empty/error precisely.
    ['insights-rounds-empty', 'insights-players-empty'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.classList.add('hidden');
    });
    ['insights-rounds-chart', 'insights-players-chart'].forEach(id => {
        const canvas = document.getElementById(id);
        if (canvas) canvas.style.display = '';
    });

    const chartDefaults = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: false },
            tooltip: {
                backgroundColor: 'rgba(15,23,42,0.9)',
                borderColor: 'rgba(255,255,255,0.1)',
                borderWidth: 1,
                titleFont: { family: 'Inter', size: 11, weight: 'bold' },
                bodyFont: { family: 'JetBrains Mono', size: 11 },
                padding: 8,
                cornerRadius: 6,
            },
        },
        scales: {
            x: {
                grid: { color: 'rgba(255,255,255,0.04)' },
                ticks: { color: '#64748b', font: { size: 10 }, maxTicksLimit: 7 },
            },
            y: {
                grid: { color: 'rgba(255,255,255,0.04)' },
                ticks: { color: '#64748b', font: { size: 10 } },
                beginAtZero: true,
            },
        },
    };

    // Build labels from dates array
    const labels = (data.dates || []).map(d => {
        const dt = new Date(d + 'T00:00:00');
        return dt.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    });

    // Rounds per Day (line)
    if (insightsRoundsChart) insightsRoundsChart.destroy();
    const roundsCtx = document.getElementById('insights-rounds-chart');
    if (roundsCtx && data.rounds) {
        insightsRoundsChart = new Chart(roundsCtx, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    data: data.rounds,
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59,130,246,0.1)',
                    borderWidth: 2,
                    tension: 0.3,
                    fill: true,
                    pointRadius: days <= 14 ? 3 : 0,
                    pointBackgroundColor: '#3b82f6',
                }],
            },
            options: chartDefaults,
        });
    }

    // Active Players per Day (area)
    if (insightsPlayersChart) insightsPlayersChart.destroy();
    const playersCtx = document.getElementById('insights-players-chart');
    if (playersCtx && data.active_players) {
        insightsPlayersChart = new Chart(playersCtx, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    data: data.active_players,
                    borderColor: '#06b6d4',
                    backgroundColor: 'rgba(6,182,212,0.12)',
                    borderWidth: 2,
                    tension: 0.3,
                    fill: true,
                    pointRadius: days <= 14 ? 3 : 0,
                    pointBackgroundColor: '#06b6d4',
                }],
            },
            options: chartDefaults,
        });
    }

    // Map Distribution (horizontal bar)
    if (insightsMapsChart) insightsMapsChart.destroy();
    const mapsCtx = document.getElementById('insights-maps-chart');
    const rawMapDistribution = data.map_distribution && typeof data.map_distribution === 'object'
        ? data.map_distribution
        : {};
    const mapEntries = Object.entries(rawMapDistribution)
        .map(([name, count]) => [name, Number(count)])
        .filter(([name, count]) => name.trim().length > 0 && Number.isFinite(count) && count > 0)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 8);

    if (!mapsCtx) return;

    if (!mapEntries.length) {
        setInsightsMapState('empty');
        return;
    }

    setInsightsMapState('ready');
    const barColors = ['#3b82f6','#06b6d4','#8b5cf6','#10b981','#f43f5e','#f59e0b','#ec4899','#6366f1'];
    insightsMapsChart = new Chart(mapsCtx, {
        type: 'bar',
        data: {
            labels: mapEntries.map(([name]) => name),
            datasets: [{
                data: mapEntries.map(([, count]) => count),
                backgroundColor: mapEntries.map((_, i) => barColors[i % barColors.length] + '66'),
                borderColor: mapEntries.map((_, i) => barColors[i % barColors.length]),
                borderWidth: 1,
                borderRadius: 4,
            }],
        },
        options: {
            ...chartDefaults,
            indexAxis: 'y',
            scales: {
                ...chartDefaults.scales,
                x: { ...chartDefaults.scales.x, ticks: { ...chartDefaults.scales.x.ticks, maxTicksLimit: 5 } },
                y: { ...chartDefaults.scales.y, beginAtZero: undefined, ticks: { color: '#94a3b8', font: { size: 11, family: 'JetBrains Mono' } } },
            },
        },
    });
}

// Expose to onclick handlers in HTML
window.loadInsightsCharts = loadInsightsCharts;

// ============================================================================
// APPLICATION INITIALIZATION
// ============================================================================

function runDeferredLoad(task, label) {
    try {
        const maybePromise = task();
        if (maybePromise && typeof maybePromise.catch === 'function') {
            maybePromise.catch((err) => {
                console.warn(`Deferred load failed (${label}):`, err);
            });
        }
    } catch (err) {
        console.warn(`Deferred load failed (${label}):`, err);
    }
}

function scheduleDeferredLoads(tasks) {
    const run = () => {
        tasks.forEach(({ task, label }) => runDeferredLoad(task, label));
    };
    if (typeof window.requestIdleCallback === 'function') {
        window.requestIdleCallback(run, { timeout: 1500 });
        return;
    }
    window.setTimeout(run, 0);
}

/**
 * Initialize the application
 */
async function initApp() {
    console.log('🚀 Slomix App Initializing...');
    initNavDropdowns();
    initGreatshotModule();

    // Prototype banner for initial view
    const activeView = document.querySelector('.view-section.active');
    if (activeView) {
        renderPrototypeBanner(activeView);
    }

    // Check API Status
    try {
        const status = await fetchJSON(`${API_BASE}/status`);
        console.log('API Status:', status);
        const statusDot = document.getElementById('server-status-dot');
        const statusText = document.getElementById('server-status-text');
        if (statusDot) {
            statusDot.classList.remove('bg-red-500');
            statusDot.classList.add('bg-green-500');
        }
        if (statusText) statusText.textContent = 'Online';
    } catch (e) {
        console.error('API Offline:', e);
        const statusDot = document.getElementById('server-status-dot');
        const statusText = document.getElementById('server-status-text');
        if (statusDot) statusDot.classList.add('bg-red-500');
        if (statusText) statusText.textContent = 'Offline';
    }

    // Load first-screen data first; defer secondary views until browser idle.
    const criticalLoads = [
        loadOverviewStats,
        updateLiveSession,
        loadQuickLeaders,
        loadRecentMatches,
        checkLoginStatus,
    ];
    await Promise.allSettled(criticalLoads.map((task) => task()));

    // Initialize search listeners
    initSearchListeners();

    // Initialize live polling
    initLivePolling();
    initLiveStatusPolling();

    // Handle initial URL hash
    const route = parseHashRoute();
    if (route.viewId && route.viewId !== 'home') {
        navigateTo(route.viewId, false, route.params);
    }

    scheduleDeferredLoads([
        { task: loadInsightsCharts, label: 'insights-charts' },
        { task: loadSeasonInfo, label: 'season-info' },
        { task: loadLastSession, label: 'last-session' },
        { task: loadPredictions, label: 'predictions' },
        { task: loadMatchesView, label: 'matches-view' },
        { task: loadSeasonLeaders, label: 'season-leaders' },
        { task: loadActivityCalendar, label: 'activity-calendar' },
        { task: loadSeasonSummary, label: 'season-summary' },
    ]);

    console.log('✅ Slomix App Ready');
}

// Expose API_BASE on window so classic (non-module) scripts like diagnostics.js can use it
window.API_BASE = API_BASE;

// Start the app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

// ============================================================================
// EXPORTS
// ============================================================================

export {
    loadOverviewStats,
    loadInsightsCharts,
    loadPredictions,
    initApp
};
