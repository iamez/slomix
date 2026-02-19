/**
 * Authentication and player linking module
 * @module auth
 */

import { AUTH_BASE, fetchJSON, escapeHtml } from './utils.js';

let loadPlayerProfileFn = null;
let profileSearchTimer = null;

function updateAdminButton(_user) {
    const adminButton = document.getElementById('link-admin');
    if (adminButton) {
        adminButton.classList.remove('hidden');
    }
}

function updateAvailabilityNavBadge(user) {
    const badge = document.getElementById('availability-nav-badge');
    if (!badge) return;

    const authenticated = Boolean(user && (user.authenticated !== false));
    const linkedPlayer = Boolean(
        user?.player_linked
        || user?.linked_player
        || user?.linked_player_guid
    );
    const shouldShow = authenticated && !linkedPlayer;
    badge.classList.toggle('hidden', !shouldShow);
}

function setProfileLinkStatusMessage(message, isError = false) {
    const metaEl = document.getElementById('profile-discord-meta');
    if (!metaEl) return;
    metaEl.textContent = message;
    metaEl.classList.toggle('text-brand-rose', isError);
    metaEl.classList.toggle('text-slate-500', !isError);
}

function setChannelLinkStatus(message, tone = 'neutral') {
    const el = document.getElementById('profile-channel-link-status');
    if (!el) return;

    el.classList.remove('text-slate-400', 'text-brand-emerald', 'text-brand-rose', 'text-brand-cyan');
    if (tone === 'error') {
        el.classList.add('text-brand-rose');
    } else if (tone === 'success') {
        el.classList.add('text-brand-emerald');
    } else if (tone === 'info') {
        el.classList.add('text-brand-cyan');
    } else {
        el.classList.add('text-slate-400');
    }
    el.textContent = String(message || '');
}

function toggleHidden(id, hidden) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.toggle('hidden', hidden);
}

function clearPlayerPicker() {
    toggleHidden('profile-link-picker', true);
    const list = document.getElementById('profile-link-search-results');
    if (list) list.innerHTML = '';
    const input = document.getElementById('profile-link-search-input');
    if (input) input.value = '';
}

async function refreshProfileLinkCard() {
    const statusEl = document.getElementById('profile-discord-status');
    if (!statusEl) return;

    try {
        const status = await fetchJSON(`${AUTH_BASE}/link/status`);
        const playerLinked = Boolean(status?.player_linked);
        const authenticated = Boolean(status?.authenticated);
        updateAvailabilityNavBadge({
            authenticated,
            player_linked: playerLinked
        });

        statusEl.textContent = playerLinked ? 'Linked' : (authenticated ? 'Not Linked' : 'Guest');
        statusEl.className = playerLinked
            ? 'text-xl font-black text-brand-emerald'
            : authenticated
                ? 'text-xl font-black text-brand-amber'
                : 'text-xl font-black text-slate-500';

        if (!authenticated) {
            setProfileLinkStatusMessage('Log in with Discord to link your player profile.');
            toggleHidden('profile-discord-link-btn', false);
            toggleHidden('profile-player-change-btn', true);
            toggleHidden('profile-player-unlink-btn', true);
            toggleHidden('profile-discord-unlink-btn', true);
            clearPlayerPicker();
            return;
        }

        if (playerLinked) {
            const linkedName = status?.linked_player?.name || 'Linked player';
            setProfileLinkStatusMessage(`Linked player: ${linkedName}`);
            toggleHidden('profile-discord-link-btn', true);
            toggleHidden('profile-player-change-btn', false);
            toggleHidden('profile-player-unlink-btn', false);
            toggleHidden('profile-discord-unlink-btn', false);
        } else {
            setProfileLinkStatusMessage('Link your Discord account to a player profile to use availability and subscriptions.');
            toggleHidden('profile-discord-link-btn', false);
            toggleHidden('profile-player-change-btn', false);
            toggleHidden('profile-player-unlink-btn', true);
            toggleHidden('profile-discord-unlink-btn', false);
        }
    } catch (err) {
        updateAvailabilityNavBadge({ authenticated: false, player_linked: false });
        statusEl.textContent = 'Unavailable';
        statusEl.className = 'text-xl font-black text-slate-500';
        setProfileLinkStatusMessage(`Link status unavailable: ${String(err?.message || 'Unknown error')}`, true);
    }
}

function renderLinkCandidates(results) {
    const list = document.getElementById('profile-link-search-results');
    if (!list) return;

    if (!Array.isArray(results) || !results.length) {
        list.innerHTML = '<div class="rounded-lg border border-white/10 bg-slate-950/30 px-3 py-2 text-slate-500">No players found</div>';
        return;
    }

    list.innerHTML = '';
    results.forEach((player) => {
        if (!player?.guid) return;
        const displayName = player.name || player.canonical_name || player.guid;
        const linkName = player.canonical_name || player.name || displayName;

        const row = document.createElement('button');
        row.type = 'button';
        row.className = 'w-full text-left rounded-lg border border-white/10 bg-slate-950/30 px-3 py-2 hover:border-brand-cyan/40 transition';
        row.innerHTML = `
            <div class="text-sm font-bold text-white">${escapeHtml(displayName)}</div>
            <div class="text-[11px] text-slate-500 mt-0.5">GUID: ${escapeHtml(player.guid)}</div>
        `;
        row.addEventListener('click', () => {
            void linkPlayer(player.guid, linkName);
        });
        list.appendChild(row);
    });
}

async function fetchPlayerSuggestions() {
    const list = document.getElementById('profile-link-search-results');
    if (!list) return;
    list.innerHTML = '<div class="rounded-lg border border-white/10 bg-slate-950/30 px-3 py-2 text-slate-500">Loading suggestions...</div>';
    try {
        const payload = await fetchJSON(`${AUTH_BASE}/players/suggestions`);
        renderLinkCandidates(payload?.suggestions || []);
    } catch (_err) {
        list.innerHTML = '<div class="rounded-lg border border-brand-rose/40 bg-brand-rose/10 px-3 py-2 text-brand-rose">Suggestions unavailable.</div>';
    }
}

async function loadPromotionPreferences() {
    const statusEl = document.getElementById('profile-promotions-status');
    if (!statusEl) return;

    try {
        const payload = await fetchJSON(`/api/availability/promotion-preferences`, { credentials: 'same-origin', cachePolicy: 'no-store' });

        const allow = document.getElementById('profile-allow-promotions');
        const preferred = document.getElementById('profile-preferred-channel');
        const telegram = document.getElementById('profile-telegram-handle');
        const signal = document.getElementById('profile-signal-handle');
        const quietStart = document.getElementById('profile-quiet-start');
        const quietEnd = document.getElementById('profile-quiet-end');
        const tz = document.getElementById('profile-promotions-timezone');

        if (allow) allow.checked = Boolean(payload?.allow_promotions);
        if (preferred) preferred.value = payload?.preferred_channel || 'any';
        if (telegram) telegram.value = payload?.telegram_handle || '';
        if (signal) signal.value = payload?.signal_handle || '';
        if (quietStart) quietStart.value = payload?.quiet_hours?.start || '';
        if (quietEnd) quietEnd.value = payload?.quiet_hours?.end || '';
        if (tz) tz.value = payload?.timezone || 'Europe/Ljubljana';

        statusEl.textContent = payload?.encryption_enabled
            ? 'Handles are encrypted at rest.'
            : (payload?.encryption_reason || 'Encryption key missing; handles cannot be stored.');
        statusEl.classList.remove('text-brand-rose');
        statusEl.classList.add(payload?.encryption_enabled ? 'text-slate-400' : 'text-brand-rose');
    } catch (err) {
        statusEl.textContent = `Promotion settings unavailable: ${String(err?.message || 'Unknown error')}`;
        statusEl.classList.remove('text-slate-400');
        statusEl.classList.add('text-brand-rose');
    }
}

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

        document.getElementById('auth-guest')?.classList.add('hidden');
        const userEl = document.getElementById('auth-user');
        if (userEl) {
            userEl.classList.remove('hidden');
            userEl.classList.add('flex');
        }

        const navName = document.getElementById('nav-username');
        if (navName) navName.textContent = user.linked_player || user.display_name || user.username;

        const navAvatar = document.getElementById('nav-avatar');
        if (navAvatar) {
            const displayName = user.linked_player || user.display_name || user.username || '?';
            navAvatar.textContent = displayName.substring(0, 2).toUpperCase();
        }

        updateAdminButton(user);
        updateAvailabilityNavBadge({
            authenticated: true,
            linked_player: user.linked_player,
            linked_player_guid: user.linked_player_guid,
        });

        await refreshProfileLinkCard();
        await loadPromotionPreferences();
        return user;
    } catch (_e) {
        document.getElementById('auth-guest')?.classList.remove('hidden');
        const userEl = document.getElementById('auth-user');
        if (userEl) {
            userEl.classList.add('hidden');
            userEl.classList.remove('flex');
        }
        updateAdminButton(null);
        updateAvailabilityNavBadge(null);

        await refreshProfileLinkCard();
        return null;
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
export async function logout() {
    try {
        const response = await fetch(`${AUTH_BASE}/logout`, {
            method: 'POST',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin'
        });

        let redirectUrl = '/';
        if (response.ok) {
            const payload = await response.json().catch(() => null);
            if (payload?.redirect_url) {
                redirectUrl = payload.redirect_url;
            }
        }

        window.location.href = redirectUrl;
    } catch (_err) {
        window.location.href = '/';
    }
}

export function openModal(id) {
    const el = document.getElementById(id);
    if (el) {
        el.classList.remove('hidden');
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
        const list = document.getElementById('profile-link-search-results')
            || document.getElementById('player-search-results');
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
                void linkPlayer(player.guid, linkName);
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
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'same-origin',
            body: JSON.stringify({ player_guid: guid, player_name: name })
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Failed to link');
        }

        await checkLoginStatus();
        clearPlayerPicker();
    } catch (e) {
        alert(`Failed to link: ${e.message}`);
    }
}

export async function unlinkPlayerProfile() {
    if (!confirm('Unlink your player profile from this Discord account?')) return;
    try {
        const res = await fetch(`${AUTH_BASE}/link`, {
            method: 'DELETE',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin'
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Failed to unlink player');
        }
        await checkLoginStatus();
    } catch (err) {
        alert(String(err?.message || 'Failed to unlink player'));
    }
}

export async function unlinkDiscordAccount() {
    if (!confirm('Unlink Discord from your website account? This will log you out.')) return;
    try {
        const res = await fetch(`${AUTH_BASE}/discord/unlink`, {
            method: 'POST',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin'
        });

        const payload = await res.json().catch(() => null);
        if (!res.ok) {
            throw new Error(payload?.detail || 'Failed to unlink Discord');
        }
        window.location.href = payload?.redirect_url || '/';
    } catch (err) {
        alert(String(err?.message || 'Failed to unlink Discord'));
    }
}

export async function createAvailabilityLinkToken(channelType) {
    const channel = String(channelType || '').trim().toLowerCase();
    if (!['telegram', 'signal'].includes(channel)) return;

    setChannelLinkStatus(`Generating ${channel} link token...`, 'info');
    try {
        const res = await fetch('/api/availability/link-token', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'same-origin',
            body: JSON.stringify({
                channel_type: channel,
                ttl_minutes: 30
            })
        });

        const payload = await res.json().catch(() => null);
        if (!res.ok) {
            throw new Error(payload?.detail || `Failed to generate ${channel} link token`);
        }

        const token = String(payload?.token || '').trim();
        const expiresAt = String(payload?.expires_at || '').trim();
        const expiresText = expiresAt
            ? new Date(expiresAt).toLocaleString()
            : 'soon';
        setChannelLinkStatus(
            `${channel.toUpperCase()} token: ${token}. Expires: ${expiresText}. Send "/link ${token}" to the bot.`,
            'success'
        );
    } catch (err) {
        setChannelLinkStatus(String(err?.message || `Failed to generate ${channel} link token`), 'error');
    }
}

export async function unlinkAvailabilityChannel(channelType) {
    const channel = String(channelType || '').trim().toLowerCase();
    if (!['telegram', 'signal'].includes(channel)) return;

    if (!confirm(`Unlink ${channel} from your availability notifications?`)) return;
    setChannelLinkStatus(`Unlinking ${channel}...`, 'info');

    try {
        const res = await fetch(`/api/availability/subscriptions/${encodeURIComponent(channel)}`, {
            method: 'DELETE',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin'
        });
        const payload = await res.json().catch(() => null);
        if (!res.ok) {
            throw new Error(payload?.detail || `Failed to unlink ${channel}`);
        }

        const inputId = channel === 'telegram' ? 'profile-telegram-handle' : 'profile-signal-handle';
        const input = document.getElementById(inputId);
        if (input) input.value = '';

        await loadPromotionPreferences();
        setChannelLinkStatus(`${channel} unlinked successfully.`, 'success');
    } catch (err) {
        setChannelLinkStatus(String(err?.message || `Failed to unlink ${channel}`), 'error');
    }
}

export function openPlayerLinkPicker() {
    const picker = document.getElementById('profile-link-picker');
    if (!picker) return;
    picker.classList.toggle('hidden');
    if (!picker.classList.contains('hidden')) {
        const input = document.getElementById('profile-link-search-input');
        if (input) input.focus();
        void fetchPlayerSuggestions();
    }
}

export async function savePromotionPreferences() {
    const statusEl = document.getElementById('profile-promotions-status');
    if (!statusEl) return;

    const allow = Boolean(document.getElementById('profile-allow-promotions')?.checked);
    const preferred = document.getElementById('profile-preferred-channel')?.value || 'any';
    const telegram = document.getElementById('profile-telegram-handle')?.value?.trim() || null;
    const signal = document.getElementById('profile-signal-handle')?.value?.trim() || null;
    const quietStart = document.getElementById('profile-quiet-start')?.value?.trim() || '';
    const quietEnd = document.getElementById('profile-quiet-end')?.value?.trim() || '';
    const timezone = document.getElementById('profile-promotions-timezone')?.value?.trim() || 'Europe/Ljubljana';

    const quietHours = (quietStart && quietEnd) ? { start: quietStart, end: quietEnd } : {};

    statusEl.textContent = 'Saving...';
    statusEl.classList.remove('text-brand-rose');
    statusEl.classList.add('text-slate-400');

    try {
        const res = await fetch(`/api/availability/promotion-preferences`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'same-origin',
            body: JSON.stringify({
                allow_promotions: allow,
                preferred_channel: preferred,
                telegram_handle: telegram,
                signal_handle: signal,
                quiet_hours: quietHours,
                timezone
            })
        });

        const payload = await res.json().catch(() => null);
        if (!res.ok) {
            throw new Error(payload?.detail || 'Failed to save promotion settings');
        }

        statusEl.textContent = 'Promotion settings saved.';
        statusEl.classList.remove('text-brand-rose');
        statusEl.classList.add('text-brand-emerald');

        await loadPromotionPreferences();
    } catch (err) {
        statusEl.textContent = String(err?.message || 'Failed to save promotion settings');
        statusEl.classList.remove('text-slate-400', 'text-brand-emerald');
        statusEl.classList.add('text-brand-rose');
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
    const profileSearchInput = document.getElementById('profile-link-search-input');
    if (profileSearchInput) {
        profileSearchInput.addEventListener('input', (e) => {
            const query = String(e.target.value || '').trim();
            clearTimeout(profileSearchTimer);
            if (query.length < 2) {
                void fetchPlayerSuggestions();
                return;
            }
            profileSearchTimer = setTimeout(async () => {
                try {
                    const results = await fetchJSON(`${AUTH_BASE}/players/search?q=${encodeURIComponent(query)}`);
                    renderLinkCandidates(results || []);
                } catch (_err) {
                    const list = document.getElementById('profile-link-search-results');
                    if (list) {
                        list.innerHTML = '<div class="rounded-lg border border-brand-rose/40 bg-brand-rose/10 px-3 py-2 text-brand-rose">Search failed.</div>';
                    }
                }
            }, 250);
        });
    }

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

        document.addEventListener('click', (e) => {
            if (!heroSearchInput.contains(e.target) && !heroSearchResults.contains(e.target)) {
                heroSearchResults.classList.add('hidden');
            }
        });
    }
}

window.loginWithDiscord = loginWithDiscord;
window.logout = logout;
window.openModal = openModal;
window.closeModal = closeModal;
window.openPlayerLinkPicker = openPlayerLinkPicker;
window.unlinkPlayerProfile = unlinkPlayerProfile;
window.unlinkDiscordAccount = unlinkDiscordAccount;
window.createAvailabilityLinkToken = createAvailabilityLinkToken;
window.unlinkAvailabilityChannel = unlinkAvailabilityChannel;
window.savePromotionPreferences = savePromotionPreferences;
