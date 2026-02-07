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
import { loadLiveStatus, initLivePolling, updateLiveSession } from './live-status.js';
import { loadPlayerProfile, setNavigateTo as setProfileNavigateTo, setLoadMatchDetails } from './player-profile.js';
import { loadLeaderboard, loadQuickLeaders, loadRecentMatches, setNavigateTo as setLeaderboardNavigateTo, initLeaderboardDefaults } from './leaderboard.js';
import { loadSeasonInfo, loadLastSession, loadSessionsView, loadSessionMVP, toggleSeasonDetails } from './sessions.js';
import { loadMatchesView, loadMapsView, loadWeaponsView, loadMatchDetails } from './matches.js';
import { loadCommunityView } from './community.js';
import { loadRecordsView } from './records.js';
import { loadAwardsView } from './awards.js';
import { loadProximityView } from './proximity.js';
import { loadAdminPanelView } from './admin-panel.js';
import './compare.js'; // Self-registers to window
import { getBadgesForPlayer, renderBadges, renderBadge } from './badges.js';
import { loadSeasonLeaders, loadActivityCalendar, loadSeasonSummary } from './season-stats.js';

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

    const bannerHtml = `
        <div class="prototype-banner glass-panel ${tone.border} ${tone.bg} border px-4 py-3 rounded-xl mb-6">
            <div class="flex items-start gap-3">
                <div class="${tone.text} mt-0.5">
                    <i data-lucide="${tone.icon}" class="w-4 h-4"></i>
                </div>
                <div>
                    <div class="text-[11px] font-bold uppercase ${tone.text} tracking-widest">${escapeHtml(title)}</div>
                    <div class="text-sm text-slate-300 mt-1">${escapeHtml(message)}</div>
                </div>
            </div>
        </div>
    `;

    if (existing) {
        existing.outerHTML = bannerHtml;
    } else {
        slot.insertAdjacentHTML('beforeend', bannerHtml);
    }

    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
}

/**
 * Navigate to a view section
 */
export function navigateTo(viewId, updateHistory = true) {
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
    const link = document.getElementById(`link-${viewId}`);
    if (link) link.classList.add('active');

    // Update URL hash
    if (updateHistory) {
        const hash = viewId === 'home' ? '' : `#/${viewId}`;
        window.location.hash = hash;
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
    } else if (viewId === 'admin') {
        loadAdminPanelView();
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

window.addEventListener('popstate', () => {
    const hash = window.location.hash.replace('#/', '');
    const viewId = hash || 'home';
    navigateTo(viewId, false);
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
// APPLICATION INITIALIZATION
// ============================================================================

/**
 * Initialize the application
 */
async function initApp() {
    console.log('🚀 Slomix App Initializing...');

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

    // Load Data
    loadOverviewStats();
    loadSeasonInfo();
    loadLastSession();
    loadPredictions();
    updateLiveSession();
    loadQuickLeaders();
    loadRecentMatches();
    loadMatchesView();
    checkLoginStatus();
    loadLiveStatus();
    loadSeasonLeaders();
    loadActivityCalendar();
    loadSeasonSummary();

    // Initialize search listeners
    initSearchListeners();

    // Initialize live polling
    initLivePolling();

    // Refresh live status every 30 seconds
    setInterval(loadLiveStatus, 30000);

    // Handle initial URL hash
    const hash = window.location.hash.replace('#/', '');
    if (hash && hash !== 'home') {
        navigateTo(hash, false);
    }

    console.log('✅ Slomix App Ready');
}

// Start the app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

// ============================================================================
// EXPORTS
// ============================================================================

export {
    loadOverviewStats,
    loadPredictions,
    initApp
};
