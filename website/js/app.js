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
import { loadLeaderboard, loadQuickLeaders, loadRecentMatches, setNavigateTo as setLeaderboardNavigateTo } from './leaderboard.js';
import { loadSeasonInfo, loadLastSession, loadSessionsView, loadSessionMVP } from './sessions.js';
import { loadMatchesView, loadMapsView, loadWeaponsView, loadMatchDetails } from './matches.js';
import { loadCommunityView } from './community.js';
import { loadRecordsView } from './records.js';
import './compare.js'; // Self-registers to window

// ============================================================================
// NAVIGATION
// ============================================================================

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
    } else if (viewId === 'weapons') {
        loadWeaponsView();
    } else if (viewId === 'records') {
        loadRecordsView();
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

        if (statRounds) statRounds.textContent = formatNumber(data.rounds);
        if (statPlayers) statPlayers.textContent = formatNumber(data.players);
        if (statSessions) statSessions.textContent = formatNumber(data.sessions);
        if (statKills) statKills.textContent = formatNumber(data.total_kills);
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
