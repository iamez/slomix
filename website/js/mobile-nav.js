/**
 * Mobile bottom navigation (VISION_2026 S5 — phones only, md:hidden).
 * Four tabs: Home / Last Session / Me / Boards. The "Me" tab deep-links to the
 * logged-in player's profile (via /auth/me cache); if unlinked it sends the user
 * to the availability page where account linking lives.
 * @module mobile-nav
 */
import { checkLoginStatus, getCurrentUser } from './auth.js';
import { parseHashRoute } from './route-registry.js';

const _TAB_VIEW = { home: 'home', sessions2: 'sessions2', leaderboards: 'leaderboards' };

function _highlight() {
    const nav = document.getElementById('mobile-bottom-nav');
    if (!nav) return;
    let active = 'home';
    try {
        active = parseHashRoute().viewId || 'home';
    } catch (_e) {
        active = 'home';
    }
    nav.querySelectorAll('[data-mnav]').forEach((btn) => {
        const key = btn.getAttribute('data-mnav');
        // "Me" highlights when viewing a profile; others match their view id.
        const isActive = key === 'me' ? active === 'profile' : _TAB_VIEW[key] === active;
        btn.classList.toggle('text-brand-cyan', isActive);
        btn.classList.toggle('text-slate-400', !isActive);
    });
}

export function initMobileNav(navigateTo) {
    const nav = document.getElementById('mobile-bottom-nav');
    if (!nav) return;
    nav.querySelectorAll('[data-mnav]').forEach((btn) => {
        btn.addEventListener('click', async () => {
            const key = btn.getAttribute('data-mnav');
            if (key === 'me') {
                // The auth cache may still be empty if the session check hasn't
                // finished on first load — resolve it lazily before deciding.
                let user = getCurrentUser();
                if (!user) {
                    try { user = await checkLoginStatus(); } catch (_e) { user = null; }
                }
                if (user && user.linked_player_guid) {
                    navigateTo('profile', true, { id: user.linked_player_guid });
                } else {
                    // Logged out / not linked → go where linking happens.
                    navigateTo('availability');
                }
                return;
            }
            navigateTo(_TAB_VIEW[key] || 'home');
        });
    });
    window.addEventListener('hashchange', _highlight);
    _highlight();
}
