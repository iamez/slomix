/**
 * Authentication and player linking module
 * @module auth
 */

import { AUTH_BASE, fetchJSON, escapeHtml } from './utils.js';

// Will be set by app.js
let loadPlayerProfileFn = null;

/**
 * Set the loadPlayerProfile function reference (to avoid circular imports)
 */
export function setLoadPlayerProfile(fn) {
    loadPlayerProfileFn = fn;
}

/**
 * Check if user is logged in and update UI
 */
export async function checkLoginStatus() {
    try {
        const user = await fetchJSON(`${AUTH_BASE}/me`);
        console.log('User:', user);

        // Update UI
        document.getElementById('auth-guest')?.classList.add('hidden');
        const userEl = document.getElementById('auth-user');
        if (userEl) {
            userEl.classList.remove('hidden');
            userEl.classList.add('flex');
        }

        // Update Nav Username & Avatar
        const navName = document.getElementById('nav-username');
        if (navName) navName.textContent = user.linked_player || user.username;

        const navAvatar = document.getElementById('nav-avatar');
        if (navAvatar) {
            const displayName = user.linked_player || user.username || '?';
            navAvatar.textContent = displayName.substring(0, 2).toUpperCase();
        }

        // Check Link
        if (!user.linked_player) {
            openModal('modal-link-player');
        } else {
            console.log('Linked to:', user.linked_player);
        }

    } catch (e) {
        console.log('Not logged in');
        document.getElementById('auth-guest')?.classList.remove('hidden');
        const userEl = document.getElementById('auth-user');
        if (userEl) {
            userEl.classList.add('hidden');
            userEl.classList.remove('flex');
        }
    }
}

/**
 * Redirect to Discord login
 */
export function loginWithDiscord() {
    window.location.href = `${AUTH_BASE}/login`;
}

/**
 * Logout and redirect
 */
export function logout() {
    window.location.href = `${AUTH_BASE}/logout`;
}

// Modal Logic
export function openModal(id) {
    const el = document.getElementById(id);
    if (el) {
        el.classList.remove('hidden');
        if (id === 'modal-link-player') {
            const input = document.getElementById('player-search-input');
            if (input) input.focus();
        }
    }
}

export function closeModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.add('hidden');
}

/**
 * Search for players to link
 */
export async function searchPlayer(query) {
    try {
        const results = await fetchJSON(`${AUTH_BASE}/players/search?q=${encodeURIComponent(query)}`);
        const list = document.getElementById('player-search-results');
        if (!list) return;
        list.innerHTML = '';

        results.forEach(player => {
            const isString = typeof player === 'string';
            const displayName = isString ? player : (player.name || player.canonical_name || 'Unknown');
            const linkName = isString ? player : (player.canonical_name || player.name || 'Unknown');
            const div = document.createElement('div');
            div.className = 'p-3 rounded bg-white/5 hover:bg-white/10 cursor-pointer flex justify-between items-center transition';
            const safeName = escapeHtml(displayName);
            div.innerHTML = `<span class="font-bold text-white">${safeName}</span> <span class="text-xs text-brand-blue font-bold">CLAIM</span>`;
            div.onclick = () => {
                if (isString || !player.guid) return;
                linkPlayer(player.guid, linkName);
            };
            list.appendChild(div);
        });

        if (results.length === 0) {
            list.innerHTML = '<div class="p-3 text-slate-500 text-center">No players found</div>';
        }
    } catch (e) {
        console.error(e);
    }
}

/**
 * Link Discord account to player
 */
export async function linkPlayer(guid, name) {
    if (!confirm(`Link your Discord account to "${name}"?`)) return;

    try {
        const res = await fetch(`${AUTH_BASE}/link`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ player_guid: guid, player_name: name })
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Failed to link');
        }

        const data = await res.json();
        alert(`Successfully linked to ${data.linked_player}!`);
        closeModal('modal-link-player');
        location.reload();

    } catch (e) {
        alert('Failed to link: ' + e.message);
    }
}

/**
 * Search for players in hero search bar
 */
export async function searchHeroPlayer(query) {
    const heroSearchResults = document.getElementById('hero-search-results');
    const heroSearchInput = document.getElementById('hero-search-input');

    if (!heroSearchResults) return;

    try {
        const results = await fetchJSON(`${AUTH_BASE}/players/search?q=${encodeURIComponent(query)}`);

        if (results.length === 0) {
            heroSearchResults.innerHTML = '<div class="p-4 text-slate-500 text-sm text-center">No players found</div>';
        } else {
            heroSearchResults.innerHTML = '';
            results.forEach(player => {
                const isString = typeof player === 'string';
                const displayName = isString ? player : (player.name || player.canonical_name || 'Unknown');
                const lookupId = isString ? displayName : (player.guid || player.name || displayName);
                const div = document.createElement('div');
                div.className = 'p-4 hover:bg-white/5 cursor-pointer flex justify-between items-center transition border-b border-white/5 last:border-0';
                const safeName = escapeHtml(displayName);
                const safeInitials = escapeHtml(displayName.replace(/\^./g, '').substring(0, 2).toUpperCase());
                div.innerHTML = `
                <div class="flex items-center gap-3">
                    <div class="w-8 h-8 rounded bg-slate-800 flex items-center justify-center text-xs font-bold text-slate-400">
                        ${safeInitials}
                    </div>
                    <span class="font-bold text-white">${safeName}</span>
                </div>
                <span class="text-xs text-brand-blue font-bold opacity-0 group-hover:opacity-100 transition">VIEW STATS</span>
            `;
                div.onclick = () => {
                    heroSearchResults.classList.add('hidden');
                    if (heroSearchInput) heroSearchInput.value = '';
                    if (loadPlayerProfileFn) loadPlayerProfileFn(lookupId);
                };
                heroSearchResults.appendChild(div);
            });
        }
        heroSearchResults.classList.remove('hidden');
    } catch (e) {
        console.error(e);
    }
}

/**
 * Initialize search input event listeners
 */
export function initSearchListeners() {
    // Player link search
    const searchInput = document.getElementById('player-search-input');
    let searchTimeout;

    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            clearTimeout(searchTimeout);
            const query = e.target.value;
            if (query.length < 2) return;
            searchTimeout = setTimeout(() => searchPlayer(query), 300);
        });
    }

    // Hero search
    const heroSearchInput = document.getElementById('hero-search-input');
    const heroSearchResults = document.getElementById('hero-search-results');
    let heroSearchTimeout;

    if (heroSearchInput && heroSearchResults) {
        heroSearchInput.addEventListener('input', (e) => {
            clearTimeout(heroSearchTimeout);
            const query = e.target.value;
            if (query.length < 2) {
                heroSearchResults.classList.add('hidden');
                return;
            }
            heroSearchTimeout = setTimeout(() => searchHeroPlayer(query), 300);
        });

        // Hide results when clicking outside
        document.addEventListener('click', (e) => {
            if (!heroSearchInput.contains(e.target) && !heroSearchResults.contains(e.target)) {
                heroSearchResults.classList.add('hidden');
            }
        });
    }
}

// Expose to window for onclick handlers in HTML
window.loginWithDiscord = loginWithDiscord;
window.logout = logout;
window.openModal = openModal;
window.closeModal = closeModal;
