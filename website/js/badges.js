/**
 * Badge System - SVG badges for achievements and player ranks
 * @module badges
 */

// Badge configuration with SVG icons
const BADGE_CONFIG = {
    // Special user badges
    admin: {
        name: 'Server Owner',
        svg: `<svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z"/></svg>`,
        class: 'badge-admin',
        color: 'text-yellow-400',
        bgColor: 'bg-yellow-400/10',
        borderColor: 'border-yellow-400/30'
    },

    // Achievement badges (from bot system)
    killer: {
        name: 'Killer',
        emoji: '💀',
        svg: `<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></svg>`,
        threshold: 1000,
        color: 'text-red-400'
    },

    veteran: {
        name: 'Veteran',
        emoji: '🕹️',
        svg: `<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="7" width="20" height="15" rx="2" ry="2"/><polyline points="17 2 12 7 7 2"/></svg>`,
        threshold: 100,
        stat: 'games',
        color: 'text-purple-400'
    },

    balanced: {
        name: 'Balanced',
        emoji: '⚖️',
        svg: `<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="2" x2="12" y2="22"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>`,
        kdRange: [0.9, 1.1],
        color: 'text-blue-400'
    },

    medic: {
        name: 'Medic',
        emoji: '💉',
        svg: `<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>`,
        threshold: 100,
        stat: 'revives',
        color: 'text-green-400'
    },

    resurrector: {
        name: 'Resurrector',
        emoji: '♻️',
        svg: `<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/></svg>`,
        threshold: 200,
        stat: 'revives',
        color: 'text-cyan-400'
    },

    demolitionist: {
        name: 'Demolitionist',
        emoji: '💣',
        svg: `<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v12M6 12h12"/></svg>`,
        threshold: 50,
        stat: 'dynamites',
        color: 'text-orange-400'
    },

    objective: {
        name: 'Objective Master',
        emoji: '🚩',
        svg: `<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" y1="22" x2="4" y2="15"/></svg>`,
        threshold: 30,
        stat: 'objectives',
        color: 'text-yellow-400'
    },

    // Rank badges (progression)
    bronze: {
        name: 'Bronze Shield',
        svg: `<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`,
        killRange: [0, 99],
        color: 'text-orange-600'
    },

    silver: {
        name: 'Silver Sword',
        svg: `<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>`,
        killRange: [100, 499],
        color: 'text-gray-400'
    },

    gold: {
        name: 'Gold Crown',
        svg: `<svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z"/></svg>`,
        killRange: [500, 999],
        color: 'text-yellow-400'
    },

    diamond: {
        name: 'Diamond Star',
        svg: `<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>`,
        killRange: [1000, 4999],
        color: 'text-cyan-400'
    },

    platinum: {
        name: 'Platinum Skull',
        svg: `<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></svg>`,
        killRange: [5000, Infinity],
        color: 'text-purple-400'
    }
};

/**
 * Get badges for a player based on their stats and Discord ID
 * @param {Object} stats - Player statistics
 * @param {string} discordId - Discord user ID (optional)
 * @returns {Array} Array of badge objects
 */
export function getBadgesForPlayer(stats, discordId = null) {
    const badges = [];

    // Special admin badge for seareal
    if (discordId === '231165917604741121') {
        badges.push({
            ...BADGE_CONFIG.admin,
            key: 'admin'
        });
    }

    // Achievement badges
    if (stats.total_kills >= BADGE_CONFIG.killer.threshold) {
        badges.push({
            ...BADGE_CONFIG.killer,
            key: 'killer'
        });
    }

    if (stats.games_played >= BADGE_CONFIG.veteran.threshold) {
        badges.push({
            ...BADGE_CONFIG.veteran,
            key: 'veteran'
        });
    }

    // K/D balanced badge
    if (stats.kd >= BADGE_CONFIG.balanced.kdRange[0] && stats.kd <= BADGE_CONFIG.balanced.kdRange[1]) {
        badges.push({
            ...BADGE_CONFIG.balanced,
            key: 'balanced'
        });
    }

    if (stats.revives_given >= BADGE_CONFIG.medic.threshold) {
        badges.push({
            ...BADGE_CONFIG.medic,
            key: 'medic'
        });
    }

    if (stats.revives_given >= BADGE_CONFIG.resurrector.threshold) {
        badges.push({
            ...BADGE_CONFIG.resurrector,
            key: 'resurrector'
        });
    }

    // Rank badge (only show highest)
    const killCount = stats.total_kills || 0;
    let rankBadge = null;

    for (const [key, badge] of Object.entries(BADGE_CONFIG)) {
        if (badge.killRange) {
            if (killCount >= badge.killRange[0] && killCount <= badge.killRange[1]) {
                rankBadge = { ...badge, key };
            }
        }
    }

    if (rankBadge) {
        badges.push(rankBadge);
    }

    return badges;
}

/**
 * Render badges as HTML
 * @param {Array} badges - Array of badge objects from getBadgesForPlayer
 * @returns {string} HTML string of badges
 */
export function renderBadges(badges) {
    if (!badges || badges.length === 0) return '';

    return badges.map(badge => {
        const bgClass = badge.bgColor || 'bg-slate-800/50';
        const borderClass = badge.borderColor || 'border-slate-600/30';
        const colorClass = badge.color || 'text-slate-400';

        return `
            <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full ${bgClass} border ${borderClass} ${colorClass}"
                  title="${badge.name}">
                ${badge.svg}
                <span class="text-xs font-bold">${badge.emoji || ''}</span>
            </span>
        `;
    }).join('');
}

/**
 * Render a single badge inline
 * @param {string} badgeKey - Key from BADGE_CONFIG
 * @returns {string} HTML string
 */
export function renderBadge(badgeKey) {
    const badge = BADGE_CONFIG[badgeKey];
    if (!badge) return '';

    const bgClass = badge.bgColor || 'bg-slate-800/50';
    const borderClass = badge.borderColor || 'border-slate-600/30';
    const colorClass = badge.color || 'text-slate-400';

    return `
        <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full ${bgClass} border ${borderClass} ${colorClass}"
              title="${badge.name}">
            ${badge.svg}
        </span>
    `;
}

// Expose to window for onclick handlers
if (typeof window !== 'undefined') {
    window.getBadgesForPlayer = getBadgesForPlayer;
    window.renderBadges = renderBadges;
    window.renderBadge = renderBadge;
}
