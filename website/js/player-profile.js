/**
 * Player profile module - profile page, charts, recent matches
 * @module player-profile
 */

import { API_BASE, fetchJSON, escapeHtml, safeInsertHTML, sparklineSVG } from './utils.js';

// Chart instances
let sessionChartInstance = null;
let roundChartInstance = null;

function _hasChartJs() {
    return typeof Chart !== 'undefined';
}

// Navigation function (set by app.js to avoid circular imports)
let navigateToFn = null;
let loadMatchDetailsFn = null;

/**
 * Set navigation function reference
 */
export function setNavigateTo(fn) {
    navigateToFn = fn;
}

/**
 * Set loadMatchDetails function reference
 */
export function setLoadMatchDetails(fn) {
    loadMatchDetailsFn = fn;
}

/**
 * Load player profile page
 */
export async function loadPlayerProfile(playerIdentifier) {
    // Keep #/profile/<id> shareable WITHOUT re-entrant dispatch. The route
    // registry's profile.load also calls this function, so if we navigated
    // unconditionally we'd loop (load → navigateTo → dispatch → load …). Only
    // navigate when the hash differs, then return early: the resulting
    // hashchange re-invokes this with the hash already matching, falling through
    // to the actual load exactly once.
    const targetHash = `#/profile/${encodeURIComponent(playerIdentifier)}`;
    if (window.location.hash !== targetHash) {
        if (navigateToFn) navigateToFn('profile', true, { id: playerIdentifier });
        else window.location.hash = targetHash;
        return;
    }
    console.log('📋 Loading profile for:', playerIdentifier);

    // Reset UI
    const profileName = document.getElementById('profile-name');
    const profileInitials = document.getElementById('profile-initials');
    if (profileName) profileName.textContent = playerIdentifier;
    if (profileInitials) profileInitials.textContent = playerIdentifier.substring(0, 2).toUpperCase();

    try {
        const data = await fetchJSON(`${API_BASE}/stats/player/${encodeURIComponent(playerIdentifier)}`);
        console.log('📋 Profile data received:', data);
        const stats = data.stats;
        const resolvedId = data.guid || playerIdentifier;

        // Update Header
        if (profileName) profileName.textContent = data.name;
        if (profileInitials) profileInitials.textContent = data.name.substring(0, 2).toUpperCase();

        const profilePlaytime = document.getElementById('profile-playtime');
        const profileSeen = document.getElementById('profile-seen');
        const profileDpm = document.getElementById('profile-dpm');

        if (profilePlaytime) profilePlaytime.textContent = stats.playtime_hours + 'h';
        if (profileSeen) profileSeen.textContent = new Date(stats.last_seen).toLocaleDateString();
        if (profileDpm) profileDpm.textContent = stats.dpm;

        // Update Cards
        const profileKd = document.getElementById('profile-kd');
        const profileKills = document.getElementById('profile-kills');
        const profileDeaths = document.getElementById('profile-deaths');

        if (profileKd) profileKd.textContent = stats.kd;
        if (profileKills) profileKills.textContent = stats.kills;
        if (profileDeaths) profileDeaths.textContent = stats.deaths;

        const profileWinrate = document.getElementById('profile-winrate');
        const profileWins = document.getElementById('profile-wins');
        const profileGames = document.getElementById('profile-games');

        if (profileWinrate) profileWinrate.textContent = stats.win_rate + '%';
        if (profileWins) profileWins.textContent = stats.wins;
        if (profileGames) profileGames.textContent = stats.games;

        const profileXp = document.getElementById('profile-xp');
        const profileDamage = document.getElementById('profile-damage');
        const profileLosses = document.getElementById('profile-losses');

        if (profileXp) profileXp.textContent = stats.total_xp.toLocaleString();
        if (profileDamage) profileDamage.textContent = (stats.damage / 1000).toFixed(1) + 'k';
        if (profileLosses) profileLosses.textContent = stats.losses;

        // Player info cards - favorite weapon and map
        const favWeapon = document.getElementById('profile-fav-weapon');
        const favMap = document.getElementById('profile-fav-map');

        if (favWeapon) favWeapon.textContent = stats.favorite_weapon || '--';
        if (favMap) favMap.textContent = stats.favorite_map || '--';

        // DPM records - highest and lowest
        const highestDpm = document.getElementById('profile-highest-dpm');
        const lowestDpm = document.getElementById('profile-lowest-dpm');

        if (highestDpm) highestDpm.textContent = stats.highest_dpm || '--';
        if (lowestDpm) lowestDpm.textContent = stats.lowest_dpm || '--';

        // Known aliases
        const aliasContainer = document.getElementById('profile-aliases');
        if (aliasContainer) {
            if (data.aliases && data.aliases.length > 0) {
                aliasContainer.innerHTML = data.aliases
                    .map(a => `<span class="px-2 py-1 rounded bg-slate-700 text-slate-300 text-xs">${escapeHtml(a)}</span>`)
                    .join(' ');
            } else {
                aliasContainer.innerHTML = '<span class="text-slate-500 text-sm">No other aliases</span>';
            }
        }

        // Discord status
        const discordEl = document.getElementById('profile-discord-status');
        if (discordEl) {
            discordEl.textContent = data.discord_linked ? 'Linked' : 'Not Linked';
            discordEl.className = data.discord_linked ? 'text-green-400' : 'text-slate-500';
        }

        // Load recent matches and form chart
        loadPlayerRecentMatches(resolvedId);
        loadPlayerFormChart(resolvedId);

        // Load enhanced gibhub.gg-parity sections (composite endpoint)
        loadEnhancedProfileSections(resolvedId);

    } catch (e) {
        console.error('Failed to load profile:', e);
        alert('Player not found!');
        if (navigateToFn) navigateToFn('home');
    }
}

/**
 * Load both player charts
 */
export async function loadPlayerFormChart(playerIdentifier) {
    loadSessionChart(playerIdentifier);
    loadRoundChart(playerIdentifier);
}

/**
 * Session DPM chart - form over gaming sessions
 */
export async function loadSessionChart(playerIdentifier) {
    const canvas = document.getElementById('sessionChart');
    if (!canvas) return;

    try {
        const data = await fetchJSON(`${API_BASE}/stats/player/${encodeURIComponent(playerIdentifier)}/form?limit=15`);

        if (!data.sessions || data.sessions.length === 0) {
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = '#64748b';
            ctx.font = '12px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('No sessions', canvas.width / 2, canvas.height / 2);
            return;
        }

        if (!_hasChartJs()) return;
        if (sessionChartInstance) sessionChartInstance.destroy();

        const ctx = canvas.getContext('2d');
        const gradient = ctx.createLinearGradient(0, 0, 0, 200);
        gradient.addColorStop(0, 'rgba(16, 185, 129, 0.3)');
        gradient.addColorStop(1, 'rgba(16, 185, 129, 0)');

        sessionChartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.sessions.map(s => s.label),
                datasets: [{
                    label: 'Session DPM',
                    data: data.sessions.map(s => s.dpm),
                    borderColor: '#10b981',
                    backgroundColor: gradient,
                    fill: true,
                    tension: 0.3,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    borderWidth: 2,
                }, {
                    label: 'Avg',
                    data: data.sessions.map(() => data.avg_dpm),
                    borderColor: '#f59e0b',
                    borderDash: [4, 4],
                    borderWidth: 1,
                    pointRadius: 0,
                    fill: false,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            title: (items) => {
                                const s = data.sessions[items[0].dataIndex];
                                return s.date + ' (' + s.rounds + ' rounds)';
                            },
                            label: (item) => item.datasetIndex === 0
                                ? 'DPM: ' + item.raw + ' | K/D: ' + data.sessions[item.dataIndex].kd
                                : 'Avg: ' + item.raw
                        }
                    }
                },
                scales: {
                    y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#64748b', font: { size: 10 } } },
                    x: { grid: { display: false }, ticks: { color: '#64748b', font: { size: 10 }, maxRotation: 45 } }
                }
            }
        });

        // Update title with trend
        const title = document.getElementById('session-chart-title');
        if (title) {
            let icon = '', color = '';
            if (data.trend === 'improving') { icon = '↑'; color = 'text-green-400'; }
            else if (data.trend === 'declining') { icon = '↓'; color = 'text-red-400'; }
            else if (data.trend === 'stable') { icon = '→'; color = 'text-yellow-400'; }
            title.innerHTML = `<i data-lucide="trending-up" class="w-5 h-5 text-brand-emerald inline"></i> Session Form ${icon ? `<span class="${color}">${icon}</span>` : ''}`;
            if (typeof lucide !== 'undefined') lucide.createIcons();
        }
    } catch (e) {
        console.error('Failed to load session chart:', e);
    }
}

/**
 * Round DPM chart - individual map performance
 */
export async function loadRoundChart(playerIdentifier) {
    const canvas = document.getElementById('roundChart');
    if (!canvas) return;

    try {
        const data = await fetchJSON(`${API_BASE}/stats/player/${encodeURIComponent(playerIdentifier)}/rounds?limit=30`);

        if (!data.rounds || data.rounds.length === 0) {
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = '#64748b';
            ctx.font = '12px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('No rounds', canvas.width / 2, canvas.height / 2);
            return;
        }

        if (!_hasChartJs()) return;
        if (roundChartInstance) roundChartInstance.destroy();

        const ctx = canvas.getContext('2d');
        const gradient = ctx.createLinearGradient(0, 0, 0, 200);
        gradient.addColorStop(0, 'rgba(59, 130, 246, 0.3)');
        gradient.addColorStop(1, 'rgba(59, 130, 246, 0)');

        roundChartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.rounds.map(r => r.label),
                datasets: [{
                    label: 'Round DPM',
                    data: data.rounds.map(r => r.dpm),
                    borderColor: '#3b82f6',
                    backgroundColor: gradient,
                    fill: true,
                    tension: 0.2,
                    pointRadius: 2,
                    pointHoverRadius: 5,
                    borderWidth: 1.5,
                }, {
                    label: 'Avg',
                    data: data.rounds.map(() => data.avg_dpm),
                    borderColor: '#f59e0b',
                    borderDash: [4, 4],
                    borderWidth: 1,
                    pointRadius: 0,
                    fill: false,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            title: (items) => {
                                const r = data.rounds[items[0].dataIndex];
                                return r.date + ' - ' + r.label;
                            },
                            label: (item) => item.datasetIndex === 0
                                ? 'DPM: ' + item.raw
                                : 'Avg: ' + item.raw
                        }
                    }
                },
                scales: {
                    y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#64748b', font: { size: 10 } } },
                    x: { grid: { display: false }, ticks: { color: '#64748b', font: { size: 10 }, maxRotation: 45, maxTicksLimit: 15 } }
                }
            }
        });
    } catch (e) {
        console.error('Failed to load round chart:', e);
    }
}

/**
 * Load recent matches for a player
 */
export async function loadPlayerRecentMatches(playerIdentifier) {
    console.log('📋 Loading recent matches for:', playerIdentifier);
    const container = document.getElementById('profile-recent-matches');
    if (!container) {
        console.error('❌ profile-recent-matches container not found!');
        return;
    }

    container.innerHTML = '<div class="text-center py-4 text-slate-500"><i data-lucide="loader" class="w-6 h-6 animate-spin mx-auto"></i></div>';
    if (typeof lucide !== 'undefined') lucide.createIcons();

    try {
        const matches = await fetchJSON(`${API_BASE}/player/${encodeURIComponent(playerIdentifier)}/matches?limit=10`);

        if (matches.length === 0) {
            container.innerHTML = '<div class="text-center py-4 text-slate-500">No recent matches found</div>';
            return;
        }

        container.innerHTML = '';

        matches.forEach(match => {
            const kd = match.kd;
            const kdColor = kd >= 2.0 ? 'text-brand-emerald' : kd >= 1.0 ? 'text-brand-blue' : 'text-brand-rose';
            const safeMapName = escapeHtml(match.map_name);
            // Truncate the RAW name before escaping so the 3-char badge can't
            // slice an HTML entity (e.g. '&amp;') mid-sequence.
            const badge = escapeHtml(String(match.map_name || '').substring(0, 3));
            const matchDate = new Date(match.round_date).toLocaleDateString();
            const roundId = Number.parseInt(String(match.round_id), 10);
            if (!Number.isFinite(roundId) || roundId <= 0) {
                return;
            }

            const html = `
                <div class="glass-card p-4 rounded-lg hover:bg-white/10 transition cursor-pointer">
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-4">
                            <div class="w-12 h-12 rounded-lg bg-slate-800 border border-white/10 flex items-center justify-center">
                                <span class="text-xs font-bold text-slate-400 uppercase">${badge}</span>
                            </div>
                            <div>
                                <div class="font-bold text-white">${safeMapName}</div>
                                <div class="text-xs text-slate-400 font-mono">${matchDate} • Round ${match.round_number}</div>
                            </div>
                        </div>
                        <div class="flex gap-6 text-right">
                            <div>
                                <div class="text-xs text-slate-500 uppercase">K/D</div>
                                <div class="text-lg font-bold ${kdColor}">${kd}</div>
                            </div>
                            <div>
                                <div class="text-xs text-slate-500 uppercase">DPM</div>
                                <div class="text-lg font-bold text-brand-emerald">${match.dpm}</div>
                            </div>
                            <div>
                                <div class="text-xs text-slate-500 uppercase">Kills</div>
                                <div class="text-lg font-bold text-brand-rose">${match.kills}</div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            container.insertAdjacentHTML('beforeend', html);
            const card = container.lastElementChild;
            if (card) {
                card.addEventListener('click', () => {
                    if (loadMatchDetailsFn) loadMatchDetailsFn(roundId);
                    else if (typeof window.loadMatchDetails === 'function') window.loadMatchDetails(roundId);
                });
            }
        });

        if (typeof lucide !== 'undefined') lucide.createIcons();
    } catch (e) {
        console.error('Failed to load player matches:', e);
        container.innerHTML = '<div class="text-center text-red-500 py-4">Failed to load recent matches</div>';
    }
}

/**
 * Load weapon breakdown chart for player profile
 */
export async function loadPlayerWeaponChart(playerName) {
    // API endpoint pending
    console.log('Weapon chart for', playerName, '- API endpoint pending');
}

// ─────────────────────────────────────────────────────────────────────────
// Enhanced profile (gibhub.gg parity) — composite /api/players/{id}/profile
// ─────────────────────────────────────────────────────────────────────────

const _AIM_YAW_BUCKETS = 16;

function _panel(title, icon, bodyHtml, tab = 'overview') {
    return `
        <div class="glass-panel p-6 rounded-xl" data-pf-tab="${tab}">
            <h3 class="font-bold text-white mb-5 flex items-center gap-2">
                <i data-lucide="${icon}" class="w-5 h-5 text-brand-cyan"></i> ${escapeHtml(title)}
            </h3>
            ${bodyHtml}
        </div>`;
}

// S5 IDENTITETA — tab categories for the profile panels (IA reorganization).
const _PF_TABS = [
    { key: 'overview', label: 'Overview' },
    { key: 'combat', label: 'Combat' },
    { key: 'timing', label: 'Timing' },
    { key: 'movement', label: 'Movement' },
    { key: 'history', label: 'History' },
];

function _renderPfTabBar() {
    const btns = _PF_TABS.map((t, i) => `
        <button data-pf-tabbtn="${t.key}"
                class="px-3 py-1.5 rounded-lg text-xs font-bold transition ${i === 0
                    ? 'bg-brand-cyan/20 text-brand-cyan'
                    : 'bg-white/5 text-slate-400 hover:bg-white/10'}">${t.label}</button>`).join('');
    return `<div id="pf-tabbar" class="flex flex-wrap gap-2 mb-4">${btns}</div>`;
}

let _pfActiveTab = 'overview';

// Apply the active tab to ALL panels (incl. async-appended competitive/history).
function _applyActivePfTab() {
    document.querySelectorAll('[data-pf-tab]').forEach(el => {
        el.classList.toggle('hidden', el.getAttribute('data-pf-tab') !== _pfActiveTab);
    });
    // The rating sparkline can only size correctly once its panel is visible.
    if (_pfActiveTab === 'history') _drawRatingSparkline('pf-rating-spark');
    const bar = document.getElementById('pf-tabbar');
    if (bar) {
        bar.querySelectorAll('[data-pf-tabbtn]').forEach(b => {
            const active = b.getAttribute('data-pf-tabbtn') === _pfActiveTab;
            b.classList.toggle('bg-brand-cyan/20', active);
            b.classList.toggle('text-brand-cyan', active);
            b.classList.toggle('bg-white/5', !active);
            b.classList.toggle('text-slate-400', !active);
        });
    }
}

function _wirePfTabs() {
    const bar = document.getElementById('pf-tabbar');
    if (!bar) return;
    _pfActiveTab = 'overview';
    bar.querySelectorAll('[data-pf-tabbtn]').forEach(b => {
        b.addEventListener('click', () => {
            _pfActiveTab = b.getAttribute('data-pf-tabbtn');
            _applyActivePfTab();
        });
    });
    _applyActivePfTab();
}

// S5 IDENTITETA — archetype (strongest percentile) + focus line (weakest), both
// derived from the ET-Rating components the composite already returns.
const _ARCHETYPE_LABEL = {
    dpm: 'Pressure Engine', kpr: 'Fragger', accuracy: 'Marksman',
    revive_rate: 'Medic Anchor', survival_rate: 'Survivor',
    useful_kill_rate: 'Efficient Killer', objective_rate: 'Objective Specialist',
    denied_playtime_pm: 'Wall Breaker', kill_quality: 'Impact Player',
    crossfire_rate: 'Crossfire Specialist', trade_rate: 'Trade Master',
    kill_permanence: 'Executioner', clutch_factor: 'Clutch Master',
    spawn_timing_eff: 'Wave Timer',
};
const _FOCUS_LABEL = {
    dpm: 'damage output', kpr: 'frag rate', accuracy: 'accuracy',
    revive_rate: 'revive rate', survival_rate: 'survival',
    useful_kill_rate: 'kill efficiency', objective_rate: 'objective play',
    denied_playtime_pm: 'spawn denial', kill_quality: 'kill impact',
    crossfire_rate: 'crossfire setups', trade_rate: 'trade-kill rate',
    kill_permanence: 'kill permanence', clutch_factor: 'clutch play',
    spawn_timing_eff: 'spawn timing',
};

function _ordinal(n) {
    const s = ['th', 'st', 'nd', 'rd'];
    const v = n % 100;
    return n + (s[(v - 20) % 10] || s[v] || s[0]);
}

function _renderIdentityStrip(data) {
    const host = document.getElementById('profile-identity-strip');
    if (!host) return;
    const skill = data.skill || {};
    const streaks = data.streaks || {};
    const comps = (skill.components && typeof skill.components === 'object') ? skill.components : null;
    let archetype = null, focusMetric = null, hi = -1, lo = 2;
    if (comps) {
        for (const [m, c] of Object.entries(comps)) {
            if (m === 'dpr' || !c || c.percentile == null) continue;
            if (c.percentile > hi) { hi = c.percentile; archetype = m; }
            if (c.percentile < lo) { lo = c.percentile; focusMetric = m; }
        }
    }
    const chips = [];
    if (skill.et_rating != null) {
        chips.push(`<span class="px-2.5 py-1 rounded-lg bg-brand-amber/15 text-brand-amber text-xs font-bold">ET Rating ${_num(skill.et_rating, 3)}${skill.tier ? ` · ${escapeHtml(String(skill.tier))}` : ''}</span>`);
    }
    if (archetype) {
        chips.push(`<span class="px-2.5 py-1 rounded-lg bg-brand-purple/15 text-brand-purple text-xs font-bold">${escapeHtml(_ARCHETYPE_LABEL[archetype] || 'All-Rounder')}</span>`);
    }
    if (streaks && streaks.current_streak) {
        const won = streaks.current_type === 'W';
        chips.push(`<span class="px-2.5 py-1 rounded-lg ${won ? 'bg-emerald-500/15 text-emerald-300' : 'bg-rose-500/15 text-rose-300'} text-xs font-bold">${streaks.current_streak}${won ? 'W' : 'L'} streak</span>`);
    }
    const focus = focusMetric
        ? `<div class="text-xs text-slate-400 mt-2">🎯 Focus: your <span class="text-slate-200">${escapeHtml(_FOCUS_LABEL[focusMetric] || focusMetric)}</span> sits in the <span class="text-brand-cyan font-bold">${_ordinal(Math.round(lo * 100))}</span> percentile — your area to climb.</div>`
        : '';
    if (data.guid) {
        chips.push(`<button data-click-action="openWrapped('${escapeHtml(String(data.guid))}')" class="px-2.5 py-1 rounded-lg bg-brand-emerald/15 text-brand-emerald text-xs font-bold hover:bg-brand-emerald/25 transition">🎁 Season Wrapped</button>`);
    }
    host.textContent = '';
    if (!chips.length && !focus) return;
    safeInsertHTML(host, 'beforeend', `<div class="flex flex-wrap gap-2">${chips.join('')}</div>${focus}`);
}

// "Your form" — this player's last session vs their OWN recent baseline, per
// metric, with a trend sparkline (rank-vs-self, mirrors the Form page / home card).
async function loadPlayerForm(root, guid) {
    if (!root || !guid) return;
    let data;
    try {
        data = await fetchJSON(`${API_BASE}/skill/player/${encodeURIComponent(guid)}/form`);
    } catch {
        return;
    }
    const metrics = data?.metrics || {};
    const keys = Object.keys(metrics).filter(k => metrics[k] && metrics[k].latest != null);
    if (!keys.length) return;

    // Composite headline — ONE form number (100% = this player's own usual),
    // blending every metric below; chips show what pushed it up/down.
    const comp = data?.composite;
    let headline = '';
    if (comp && comp.latest != null) {
        const cFlat = comp.delta_pct === 0;
        const cUp = comp.delta_pct != null && comp.delta_pct > 0;
        const cCls = cFlat ? 'text-slate-400' : cUp ? 'text-emerald-400' : 'text-rose-400';
        const cTxt = comp.delta_pct == null ? ''
            : cFlat ? '±0%' : `${cUp ? '▲ +' : '▼ '}${Math.abs(comp.delta_pct)}%`;
        const cSpark = sparklineSVG(comp.series, { up: cFlat ? null : cUp, width: 110, height: 26 });
        const SHORT = { dpm: 'DPM', kd: 'K/D', obj: 'OBJ', acc: 'ACC', kills: 'K', impact: 'IMP' };
        const chips = (comp.breakdown || [])
            .filter((b) => b.delta_pct != null)
            .map((b) => {
                const bFlat = b.delta_pct === 0;
                const bUp = b.delta_pct > 0;
                const bCls = bFlat ? 'text-slate-500' : bUp ? 'text-emerald-400/90' : 'text-rose-400/90';
                const bTxt = bFlat ? '±0' : `${bUp ? '+' : '-'}${Math.abs(b.delta_pct)}`;
                return `<span class="${bCls}">${SHORT[b.metric] || b.metric} ${bTxt}%</span>`;
            })
            .join('<span class="text-slate-600"> · </span>');
        headline = `
            <div class="mb-3 pb-3 border-b border-white/10">
                <div class="flex items-center justify-between gap-3">
                    <div>
                        <span class="text-2xl font-black text-white">${comp.latest}%</span>
                        <span class="font-mono text-sm ${cCls} ml-2">${escapeHtml(cTxt)}</span>
                    </div>
                    ${cSpark}
                </div>
                <div class="text-[11px] text-slate-500 mt-1">Overall form — 100% = your usual, all metrics blended</div>
                ${chips ? `<div class="text-[11px] font-mono mt-1">${chips}</div>` : ''}
            </div>`;
    }

    const rows = keys.map((k) => {
        const m = metrics[k];
        const hasDelta = m.delta_pct != null;
        const flat = hasDelta && m.delta_pct === 0;
        const up = hasDelta && m.delta_pct > 0;
        const deltaCls = !hasDelta ? 'text-slate-500' : flat ? 'text-slate-400'
            : up ? 'text-emerald-400' : 'text-rose-400';
        const deltaTxt = !hasDelta ? '—'
            : flat ? '±0%' : `${up ? '▲ +' : '▼ '}${Math.abs(m.delta_pct)}%`;
        const spark = sparklineSVG(m.series, { up: (hasDelta && !flat) ? up : null, width: 72, height: 20 });
        const base = m.baseline != null ? `${m.latest} <span class="text-slate-600">vs</span> ${m.baseline} <span class="text-slate-600">${escapeHtml(m.unit || '')}</span>` : `${m.latest}`;
        return `<div class="flex items-center justify-between gap-3 py-2 border-b border-white/5">
            <span class="text-slate-400 text-xs font-bold uppercase tracking-wide w-28">${escapeHtml(m.label || k)}</span>
            <div class="flex items-center gap-3">
                <span class="text-slate-300 text-xs font-mono hidden sm:inline">${base}</span>
                ${spark}
                <span class="font-mono text-sm ${deltaCls} w-20 text-right">${escapeHtml(deltaTxt)}</span>
            </div></div>`;
    }).join('');

    const html = _panel('Your form · vs own baseline', 'activity', `
        <p class="text-[11px] text-slate-500 mb-3">Last session vs your own recent-session average (~10 sessions) — rank-vs-self, not a global ranking. ▲ above your usual, ▼ below.</p>
        ${headline}
        ${rows}
    `, 'history');
    safeInsertHTML(root, 'beforeend', html);
    // Re-apply the active tab so this History-only panel shows/hides correctly when
    // it resolves after the initial render (mirrors loadCareerHistory).
    _applyActivePfTab();
    if (typeof lucide !== 'undefined') lucide.createIcons();
}

// S5-C — career timeline: ET-Rating sparkline + engraved season awards (History tab).
async function loadCareerHistory(root, guid) {
    if (!root || !guid) return;
    const [histRes, awardsRes] = await Promise.allSettled([
        fetchJSON(`${API_BASE}/skill/player/${encodeURIComponent(guid)}/history`),
        fetchJSON(`${API_BASE}/players/${encodeURIComponent(guid)}/awards`),
    ]);
    const hist = histRes.status === 'fulfilled' ? histRes.value : null;
    const awardsData = awardsRes.status === 'fulfilled' ? awardsRes.value : null;
    const sessions = Array.isArray(hist) ? hist : (hist?.sessions || hist?.history || []);
    const awards = awardsData?.awards || [];
    if (!sessions.length && !awards.length) return;

    const awardBadges = awards.map(a =>
        `<div class="glass-card px-3 py-2 rounded-lg border-l-2 border-brand-amber/60">
            <div class="text-xs font-black text-brand-amber">🏆 ${escapeHtml(a.label)}</div>
            <div class="text-[11px] text-slate-400">${escapeHtml(a.season_name || a.season_id)}${a.value_text ? ` · ${escapeHtml(a.value_text)}` : ''}</div>
        </div>`).join('');

    const html = _panel('Career Timeline', 'line-chart', `
        ${sessions.length ? '<canvas id="pf-rating-spark" height="80" class="w-full mb-4"></canvas>' : ''}
        ${awards.length
            ? `<div class="text-[11px] uppercase tracking-widest text-slate-500 font-bold mb-2">Engraved season awards</div>
               <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">${awardBadges}</div>`
            : '<p class="text-xs text-slate-500">No season awards engraved yet.</p>'}
    `, 'history');
    safeInsertHTML(root, 'beforeend', html);
    _applyActivePfTab();
    if (typeof lucide !== 'undefined') lucide.createIcons();

    if (sessions.length) {
        _drawRatingSparkline('pf-rating-spark',
            sessions.map(s => Number(s.session_rating ?? s.rating ?? 0)));
    }
}

// Slomix Museum memory card (Good Night plan rank 10) — a friendship-safe
// keepsake of the player's whole history. Rank-vs-self only: "playing since",
// nights, lifetime kills, personal-best round/spree, signature map. Lives in the
// History tab next to the Career Timeline.
async function loadMemoryCard(root, guid) {
    if (!root || !guid) return;
    let data;
    try {
        data = await fetchJSON(`${API_BASE}/players/${encodeURIComponent(guid)}/memory-card`);
    } catch (_) {
        return; // optional keepsake — never block the profile
    }
    const facts = (data && data.facts) || [];
    if (!facts.length) return;

    const cells = facts.map((f) => {
        const isSig = f.key === 'signature_map';
        const accent = isSig ? 'border-brand-amber/50' : 'border-white/5';
        return `
            <div class="bg-slate-800/40 rounded-lg p-3 border ${accent}">
                <div class="text-[10px] uppercase tracking-wide text-slate-500">${escapeHtml(f.label)}</div>
                <div class="text-lg font-bold ${isSig ? 'text-brand-amber' : 'text-white'}">${escapeHtml(String(f.value))}</div>
                ${f.sub ? `<div class="text-[11px] text-slate-400 mt-0.5">${escapeHtml(String(f.sub))}</div>` : ''}
            </div>`;
    }).join('');

    const html = _panel('Memory card', 'scroll-text', `
        <p class="text-xs text-slate-500 mb-4">A keepsake of your Slomix history — measured against your own past, never a ladder.</p>
        <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">${cells}</div>
    `, 'history');
    safeInsertHTML(root, 'beforeend', html);
    _applyActivePfTab();
    if (typeof lucide !== 'undefined') lucide.createIcons();
}

// Cached series so the sparkline can be (re)drawn when the History tab becomes
// visible — a hidden canvas reports clientWidth 0, which would size it wrong.
let _sparkValues = null;

function _drawRatingSparkline(canvasId, values) {
    if (values) _sparkValues = values;
    const cv = document.getElementById(canvasId);
    if (!cv || !_sparkValues || !_sparkValues.length) return;
    const w = cv.clientWidth;
    if (!w) return;  // panel hidden → defer; _applyActivePfTab redraws on activation
    const h = cv.height || 80;
    cv.width = w;
    const vals = _sparkValues;
    const ctx = cv.getContext('2d');
    if (!ctx) return;
    const pad = 6;
    const min = Math.min(...vals), max = Math.max(...vals);
    const span = (max - min) || 1;
    const x = (i) => pad + (w - 2 * pad) * (vals.length === 1 ? 0.5 : i / (vals.length - 1));
    const y = (v) => h - pad - (h - 2 * pad) * ((v - min) / span);
    ctx.clearRect(0, 0, w, h);
    ctx.strokeStyle = '#06b6d4';
    ctx.lineWidth = 2;
    ctx.beginPath();
    vals.forEach((v, i) => { i ? ctx.lineTo(x(i), y(v)) : ctx.moveTo(x(i), y(v)); });
    ctx.stroke();
    // last-point dot
    ctx.fillStyle = '#22d3ee';
    ctx.beginPath();
    ctx.arc(x(vals.length - 1), y(vals[vals.length - 1]), 3, 0, Math.PI * 2);
    ctx.fill();
}

function _statCell(label, value, color = 'text-white') {
    return `
        <div class="bg-slate-800/40 rounded-lg p-3 border border-white/5">
            <div class="text-[10px] uppercase tracking-wide text-slate-500">${escapeHtml(label)}</div>
            <div class="text-lg font-bold ${color}">${value}</div>
        </div>`;
}

function _na(msg = 'No data available') {
    return `<div class="text-sm text-slate-500 italic py-2">${escapeHtml(msg)}</div>`;
}

function _num(v, d = 0) {
    if (v === null || v === undefined || Number.isNaN(Number(v))) return '--';
    return Number(v).toLocaleString(undefined, { maximumFractionDigits: d });
}

/**
 * Load + render every enhanced section from the composite endpoint.
 */
export async function loadEnhancedProfileSections(playerIdentifier) {
    const root = document.getElementById('profile-enhanced');
    if (!root) return;
    root.innerHTML = '<div class="text-center py-6 text-slate-500"><i data-lucide="loader" class="w-6 h-6 animate-spin mx-auto"></i></div>';
    if (typeof lucide !== 'undefined') lucide.createIcons();

    let data;
    try {
        data = await fetchJSON(`${API_BASE}/players/${encodeURIComponent(playerIdentifier)}/profile`);
    } catch (e) {
        console.error('Failed to load enhanced profile:', e);
        root.innerHTML = '';
        return;
    }

    // S5: populate the identity strip (rating/tier/archetype/focus/streak) from
    // the composite — header is filled by the base loader, this adds the IA bits.
    _renderIdentityStrip(data);

    // Tag each panel with its tab category (panels default to data-pf-tab="overview";
    // replace the first occurrence per section). No change to the render functions.
    const _tag = (html, tab) => (html || '').replace('data-pf-tab="overview"', `data-pf-tab="${tab}"`);
    const sections = [
        _tag(renderGatherSummary(data), 'overview'),
        _tag(renderSkillAndLifetime(data), 'overview'),
        _tag(renderMapsTable(data.maps), 'overview'),
        _tag(renderRelationships(data.relationships), 'overview'),
        _tag(renderWeapons(data.weapons), 'combat'),
        _tag(renderHitRegions(data.hit_regions), 'combat'),
        _tag(renderAimSection(data.aim, data.guid), 'combat'),
        _tag(renderCombatTiming(data.combat_timing), 'timing'),
        _tag(renderMovement(data.movement), 'movement'),
        _tag(renderNickHistory(data.nick_history), 'history'),
    ];
    // All section HTML is built from escapeHtml-sanitized values; insert via
    // the shared safeInsertHTML helper (utils.js) after clearing.
    root.innerHTML = '';
    safeInsertHTML(root, 'beforeend', _renderPfTabBar() + sections.filter(Boolean).join(''));
    _wirePfTabs();
    if (typeof lucide !== 'undefined') lucide.createIcons();

    // History tab: rating sparkline + engraved season awards (S5-C, async).
    loadCareerHistory(root, data.guid).catch((e) => console.warn('career history failed', e));
    loadMemoryCard(root, data.guid).catch((e) => console.warn('memory card failed', e));
    loadPlayerForm(root, data.guid).catch((e) => console.warn('player form failed', e));

    // Wire the aim map dropdown (rose) after the DOM exists. Pass the
    // structured map list directly (most-played first) — no DOM scraping.
    const mapList = (data.maps && data.maps.available && Array.isArray(data.maps.maps))
        ? data.maps.maps.map(m => m.map).filter(Boolean)
        : [];
    wireAimRose(data.guid, mapList);

    // Stopwatch Competitive card loads separately (own endpoint, like aim).
    loadCompetitiveCard(root, data.guid).catch((e) =>
        console.warn('competitive card load failed', e));

    // Reactions & Readiness (SSR components; owner answer A3 — profile surface).
    loadReactionsCard(root, data.guid).catch((e) =>
        console.warn('reactions card load failed', e));
}

// ── Reactions & Readiness card (SSR components, owner answer A3) ────────────

async function loadReactionsCard(root, guid) {
    if (!guid) return;
    const ssr = await fetchJSON(`${API_BASE}/skill/ssr`);
    const g8 = String(guid).slice(0, 8).toUpperCase();
    const me = (ssr?.players || []).find(p => p.player_guid === g8);
    if (!me) return; // below min sessions/components — no panel
    const c = me.components || {};
    const ms = (comp) => (comp && comp.raw != null) ? `${Math.round(comp.raw)}ms` : '--';
    const pct = (comp) => (comp && comp.pct != null) ? `top ${Math.round((1 - comp.pct) * 100) || 1}%` : '';
    const cells = [
        _statCell('Target Acquisition', ms(c.target_acq_ms), 'text-cyan-300'),
        _statCell('· vs group', pct(c.target_acq_ms) || '--'),
        _statCell('Spawn Readiness', ms(c.spawn_ready_ms), 'text-emerald-300'),
        _statCell('· vs group', pct(c.spawn_ready_ms) || '--'),
        _statCell('Comp Skill (SSR)', Number(me.ssr).toFixed(3), 'text-amber-300'),
        _statCell('Coverage', me.coverage),
    ].join('');
    const html = _panel('Reactions & Readiness', 'zap', `
        <div class="grid grid-cols-2 sm:grid-cols-3 gap-3">${cells}</div>
        <p class="text-[10px] text-slate-600 mt-2">Group-relative medians (~200ms telemetry grid).
        Raw times mix crosshair placement, ping and hardware — compare ranks, not milliseconds.</p>
    `, 'timing');
    safeInsertHTML(root, 'beforeend', html);
    _applyActivePfTab();
    if (typeof lucide !== 'undefined') lucide.createIcons();
}

// ── Stopwatch Competitive card (player passport) ────────────────────────────

async function loadCompetitiveCard(root, guid) {
    if (!guid) return;
    const card = await fetchJSON(
        `${API_BASE}/proximity/competitive/player-card?player_guid=${encodeURIComponent(guid)}`);
    if (!card || !card.player) return;
    const st = card.stagger || {};
    const cl = card.clutch || {};
    const att = (card.sides || {}).attack;
    const def = (card.sides || {}).defense;
    const cells = [
        _statCell('Stagger Kills', `${_num(st.stagger_kills)} (${_num(st.stagger_rate, 1)}%)`, 'text-rose-300'),
        _statCell('Respawn Denied', `${_num(st.denied_s)}s`, 'text-cyan-300'),
        _statCell('Clutch 1vN', cl.situations
            ? `${_num(cl.wins)}/${_num(cl.situations)} (${_num(cl.win_pct, 1)}%)`
            : '--', 'text-amber-300'),
        _statCell('Advantage Conversions', _num((card.man_advantage || {}).conversions), 'text-emerald-300'),
        _statCell('Attack Kills', att ? _num(att.kills) : '--'),
        _statCell('Defense Kills', def ? _num(def.kills) : '--'),
    ].join('');
    const best = cl.best
        ? `<p class="text-[11px] text-slate-500 mt-2">Best clutch: 1v${cl.best.enemies}, ${cl.best.kills} kill${cl.best.kills === 1 ? '' : 's'}${cl.best.survived ? ', survived to the wave' : ''}.</p>`
        : '';
    const html = _panel('Stopwatch Competitive', 'swords', `
        <div class="grid grid-cols-2 sm:grid-cols-3 gap-3">${cells}</div>
        ${best}
        <p class="text-[11px] text-slate-500 mt-2">Stagger/sides over ${_num(card.range_days)} days; clutch + advantage over ${_num(card.timeline_range_days)} days. Stagger = kill that costs the victim 80%+ of their spawn wave.</p>
    `, 'combat');
    safeInsertHTML(root, 'beforeend', html);
    _applyActivePfTab();
    if (typeof lucide !== 'undefined') lucide.createIcons();
}

function renderSkillAndLifetime(data) {
    const lt = data.lifetime || {};
    const skill = data.skill || {};
    const adv = data.advanced || {};
    const streaks = data.streaks || {};
    if (!lt.available) return '';

    const tierColors = {
        elite: 'text-amber-300', veteran: 'text-violet-300',
        experienced: 'text-cyan-300', regular: 'text-emerald-300', newcomer: 'text-slate-300',
    };
    let skillHtml = '';
    if (skill.available) {
        const tc = tierColors[skill.tier] || 'text-white';
        const rankHtml = skill.rank
            ? `<div class="px-4 py-2 rounded-lg bg-slate-800/60 border border-white/10">
                   <div class="text-[10px] uppercase text-slate-500">Rank</div>
                   <div class="text-2xl font-bold text-white">#${_num(skill.rank)}
                       <span class="text-xs text-slate-500">/ ${_num(skill.total_rated)} · top ${_num(Math.max(0, 100 - (skill.percentile || 0)), 1)}%</span></div>
               </div>`
            : '';
        skillHtml = `
            <div class="flex items-center gap-4 mb-5 flex-wrap">
                <div class="px-4 py-2 rounded-lg bg-slate-800/60 border border-white/10">
                    <div class="text-[10px] uppercase text-slate-500">ET Rating</div>
                    <div class="text-2xl font-bold ${tc}">${_num(skill.et_rating, 3)}
                        <span class="text-sm uppercase">${escapeHtml(skill.tier || '')}</span></div>
                </div>
                ${rankHtml}
                <div class="text-xs text-slate-500">${_num(skill.games_rated)} games rated</div>
            </div>`;
    }

    const utro = adv.utro && adv.utro.available
        ? `${_num(adv.utro.utro, 1)} <span class="text-xs text-slate-500">(${_num(adv.utro.utro_per_kill, 2)}/kill)</span>` : '--';
    const bait = adv.bait && adv.bait.available ? `${_num(adv.bait.score, 1)}%` : '--';
    let streakStr = '--';
    if (streaks.available) {
        const t = streaks.current_type === 'W' ? 'text-emerald-400' : streaks.current_type === 'L' ? 'text-rose-400' : 'text-slate-400';
        streakStr = `<span class="${t}">${streaks.current_streak}${escapeHtml(streaks.current_type || '')}</span>
            <span class="text-xs text-slate-500">(best W${streaks.longest_win}/L${streaks.longest_loss})</span>`;
    }

    const combat = [
        _statCell('Rounds', _num(lt.rounds)),
        _statCell('Win Rate', `${_num(lt.win_rate, 1)}%`, lt.win_rate >= 50 ? 'text-emerald-400' : 'text-rose-400'),
        _statCell('K/D', _num(lt.kd, 2), lt.kd >= 1 ? 'text-emerald-400' : 'text-rose-400'),
        _statCell('Kills', _num(lt.kills)),
        _statCell('Deaths', _num(lt.deaths)),
        _statCell('Gibs', _num(lt.gibs)),
        _statCell('DPM', _num(lt.dpm, 1), 'text-brand-emerald'),
        _statCell('Headshot Kills', _num(lt.headshot_kills)),
        _statCell('Hours', _num(lt.hours_played, 1)),
        _statCell('XP', _num(lt.xp)),
        _statCell('Self Kills', _num(lt.self_kills)),
        _statCell('Team Kills', _num(lt.team_kills)),
    ].join('');
    const support = [
        _statCell('Revives', _num(lt.revives_given)),
        _statCell('Assists', _num(lt.kill_assists)),
        _statCell('Useful Kills', _num(lt.useful_kills)),
        _statCell('Obj. Stolen', _num(lt.objectives_stolen)),
        _statCell('Dyn. Planted', _num(lt.dynamites_planted)),
        _statCell('Dyn. Defused', _num(lt.dynamites_defused)),
        _statCell('Double Kills', _num(lt.double_kills)),
        _statCell('Triple Kills', _num(lt.triple_kills)),
        _statCell('Best Spree', _num(lt.best_killing_spree)),
        _statCell('UTRO', utro, 'text-amber-300'),
        _statCell('Bait Score', bait, 'text-cyan-300'),
        _statCell('Streak', streakStr),
    ].join('');

    return _panel('Lifetime Stats', 'bar-chart-3', `
        ${skillHtml}
        <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-4">${combat}</div>
        <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">${support}</div>
    `);
}

function renderWeapons(weapons) {
    if (!weapons || !weapons.available) return _panel('Weapons', 'crosshair', _na('No weapon data'));
    const rows = (weapons.weapons || []).map(w => `
        <tr class="border-b border-white/5 hover:bg-white/5">
            <td class="py-2 px-2 font-medium text-white">${escapeHtml(w.weapon)}</td>
            <td class="py-2 px-2 text-right">${_num(w.kills)}</td>
            <td class="py-2 px-2 text-right text-slate-400">${_num(w.deaths)}</td>
            <td class="py-2 px-2 text-right">${_num(w.headshots)}</td>
            <td class="py-2 px-2 text-right text-brand-emerald">${_num(w.accuracy, 1)}%</td>
            <td class="py-2 px-2 text-right text-amber-300">${_num(w.hs_accuracy, 1)}%</td>
        </tr>`).join('');
    return _panel('Weapons', 'crosshair', `
        <div class="flex gap-4 mb-3 text-sm">
            <span class="text-slate-400">Overall accuracy: <span class="text-brand-emerald font-bold">${_num(weapons.overall_accuracy, 1)}%</span></span>
            <span class="text-slate-400">HS accuracy: <span class="text-amber-300 font-bold">${_num(weapons.overall_hs_accuracy, 1)}%</span></span>
        </div>
        <div class="overflow-x-auto">
        <table class="w-full text-sm">
            <thead><tr class="text-[10px] uppercase text-slate-500 border-b border-white/10">
                <th class="py-2 px-2 text-left">Weapon</th><th class="py-2 px-2 text-right">Kills</th>
                <th class="py-2 px-2 text-right">Deaths</th><th class="py-2 px-2 text-right">HS</th>
                <th class="py-2 px-2 text-right">Acc</th><th class="py-2 px-2 text-right">HS Acc</th>
            </tr></thead><tbody>${rows}</tbody>
        </table></div>
    `);
}

function _regionBar(label, pct, color) {
    return `
        <div class="mb-2">
            <div class="flex justify-between text-xs mb-1"><span class="text-slate-400">${escapeHtml(label)}</span>
                <span class="text-white font-medium">${_num(pct, 1)}%</span></div>
            <div class="h-2 rounded bg-slate-800 overflow-hidden">
                <div class="h-full ${color}" style="width:${Math.min(100, Number(pct) || 0)}%"></div>
            </div>
        </div>`;
}

// Heat color (cyan→amber→rose) by intensity 0..1 for body regions.
function _heat(intensity) {
    const i = Math.max(0, Math.min(1, Number(intensity) || 0));
    // 0 = dim cyan, 0.5 = amber, 1 = hot rose
    const r = Math.round(34 + i * (244 - 34));
    const g = Math.round(211 - i * (211 - 63));
    const b = Math.round(238 - i * (238 - 94));
    return `rgb(${r},${g},${b})`;
}

// SVG body silhouette: each region (head/arms/body/legs) filled by its share of
// hits (brighter/hotter = more hits there). t = totals with *_pct fields.
function _bodySvg(t) {
    const head = Number(t.head_pct) || 0;
    const arms = Number(t.arms_pct) || 0;
    const body = Number(t.body_pct) || 0;
    const legs = Number(t.legs_pct) || 0;
    const max = Math.max(head, arms, body, legs, 1);
    const fill = (pct) => _heat(pct / max);
    const lbl = (x, y, txt) => `<text x="${x}" y="${y}" text-anchor="middle" font-size="7" fill="#e2e8f0" font-weight="bold">${txt}</text>`;
    return `
    <svg viewBox="0 0 100 210" width="150" height="300" class="mx-auto" role="img" aria-label="hit region body map">
      <!-- arms -->
      <rect x="16" y="44" width="13" height="54" rx="5" fill="${fill(arms)}" stroke="#0f172a" stroke-width="1"/>
      <rect x="71" y="44" width="13" height="54" rx="5" fill="${fill(arms)}" stroke="#0f172a" stroke-width="1"/>
      <!-- legs -->
      <rect x="37" y="100" width="12" height="72" rx="5" fill="${fill(legs)}" stroke="#0f172a" stroke-width="1"/>
      <rect x="51" y="100" width="12" height="72" rx="5" fill="${fill(legs)}" stroke="#0f172a" stroke-width="1"/>
      <!-- torso -->
      <rect x="33" y="42" width="34" height="58" rx="7" fill="${fill(body)}" stroke="#0f172a" stroke-width="1"/>
      <!-- head -->
      <circle cx="50" cy="24" r="15" fill="${fill(head)}" stroke="#0f172a" stroke-width="1"/>
      ${lbl(50, 26, _num(head, 0) + '%')}
      ${lbl(50, 74, _num(body, 0) + '%')}
      ${lbl(22, 74, _num(arms, 0) + '%')}
      ${lbl(50, 140, _num(legs, 0) + '%')}
    </svg>
    <div class="text-[11px] text-slate-500 text-center mt-1">Hotter = more of your hits land there</div>`;
}

function renderHitRegions(hr) {
    if (!hr || !hr.available) return '';
    const t = hr.totals || {};
    const bars = [
        _regionBar('Head', t.head_pct, 'bg-rose-500'),
        _regionBar('Arms', t.arms_pct, 'bg-amber-500'),
        _regionBar('Body', t.body_pct, 'bg-cyan-500'),
        _regionBar('Legs', t.legs_pct, 'bg-emerald-500'),
    ].join('');
    const perWeapon = (hr.per_weapon || []).slice(0, 8).map(w => `
        <tr class="border-b border-white/5">
            <td class="py-1 px-2 text-white">${escapeHtml(w.weapon)}</td>
            <td class="py-1 px-2 text-right text-rose-300">${_num(w.head_pct, 1)}%</td>
            <td class="py-1 px-2 text-right text-slate-400">${_num(w.total)}</td>
        </tr>`).join('');
    return _panel('Where You Hit', 'target', `
        <div class="grid md:grid-cols-3 gap-6 items-center">
            <div>${_bodySvg(t)}</div>
            <div>${bars}</div>
            <div class="overflow-x-auto">
                <div class="text-[11px] uppercase tracking-wide text-slate-500 mb-2">Head % by weapon</div>
                <table class="w-full text-sm">
                    <thead><tr class="text-[10px] uppercase text-slate-500 border-b border-white/10">
                        <th class="py-1 px-2 text-left">Weapon</th><th class="py-1 px-2 text-right">Head %</th>
                        <th class="py-1 px-2 text-right">Hits</th></tr></thead>
                    <tbody>${perWeapon}</tbody>
                </table>
            </div>
        </div>
    `);
}

function renderMovement(mv) {
    if (!mv || !mv.available) return '';
    const st = mv.stance || {};
    const cells = [
        _statCell('Avg Speed', _num(mv.avg_speed, 1)),
        _statCell('Peak Speed', _num(mv.peak_speed, 1)),
        _statCell('Sprint %', `${_num(mv.sprint_pct, 1)}%`),
        _statCell('Dist/Life', _num(mv.avg_distance_per_life)),
        _statCell('Standing', `${_num(st.standing_pct, 1)}%`),
        _statCell('Crouching', `${_num(st.crouching_pct, 1)}%`),
        _statCell('Prone', `${_num(st.prone_pct, 1)}%`),
        _statCell('Post-spawn Dist', _num(mv.avg_post_spawn_distance)),
    ].join('');
    return _panel('Movement & Stance', 'footprints',
        `<div class="grid grid-cols-2 sm:grid-cols-4 gap-3">${cells}</div>`);
}

function _relList(title, items, valueFn, color) {
    if (!items || items.length === 0) return '';
    const rows = items.map(p => `
        <div class="flex justify-between items-center py-1.5 border-b border-white/5">
            <span class="text-sm text-white truncate">${escapeHtml(p.name || p.opponent_name || '?')}</span>
            <span class="text-sm font-bold ${color}">${valueFn(p)}</span>
        </div>`).join('');
    return `<div><div class="text-[11px] uppercase tracking-wide text-slate-500 mb-2">${escapeHtml(title)}</div>${rows}</div>`;
}

function renderRelationships(rel) {
    if (!rel || !rel.available) return '';
    const cols = [
        _relList('Top Killers (kill you most)', rel.top_killers, p => `${_num(p.kills_on_player)}`, 'text-rose-400'),
        _relList('Top Victims (you kill most)', rel.top_victims, p => `${_num(p.kills_by_player)}`, 'text-emerald-400'),
        _relList('Best Teammates (synergy)', rel.best_teammates, p => `${p.synergy >= 0 ? '+' : ''}${_num(p.synergy, 1)}${p.win_rate_with != null ? ` · ${_num(p.win_rate_with, 0)}% W` : ''}`, 'text-emerald-400'),
        _relList('Worst Teammates', rel.worst_teammates, p => `${p.synergy >= 0 ? '+' : ''}${_num(p.synergy, 1)}${p.win_rate_with != null ? ` · ${_num(p.win_rate_with, 0)}% W` : ''}`, 'text-rose-400'),
        _relList('Hardest Opponents', rel.hardest_opponents, p => `${_num((p.win_rate || 0) * 100, 0)}%`, 'text-rose-400'),
        _relList('Easiest Opponents', rel.easiest_opponents, p => `${_num((p.win_rate || 0) * 100, 0)}%`, 'text-emerald-400'),
    ].filter(Boolean).join('');
    return _panel('Rivals & Teammates', 'users',
        `<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-8 gap-y-4">${cols}</div>`);
}

function renderMapsTable(maps) {
    if (!maps || !maps.available) return '';
    const rows = (maps.maps || []).map(m => `
        <tr class="border-b border-white/5 hover:bg-white/5">
            <td class="py-2 px-2 text-white">${escapeHtml(m.map)}</td>
            <td class="py-2 px-2 text-right">${_num(m.rounds)}</td>
            <td class="py-2 px-2 text-right ${m.win_rate >= 50 ? 'text-emerald-400' : 'text-rose-400'}">${_num(m.win_rate, 1)}%</td>
            <td class="py-2 px-2 text-right">${_num(m.kd, 2)}</td>
            <td class="py-2 px-2 text-right text-brand-emerald">${_num(m.dpm, 1)}</td>
        </tr>`).join('');
    return _panel('Maps', 'map', `
        <div class="overflow-x-auto"><table class="w-full text-sm">
            <thead><tr class="text-[10px] uppercase text-slate-500 border-b border-white/10">
                <th class="py-2 px-2 text-left">Map</th><th class="py-2 px-2 text-right">Rounds</th>
                <th class="py-2 px-2 text-right">Win%</th><th class="py-2 px-2 text-right">K/D</th>
                <th class="py-2 px-2 text-right">DPM</th></tr></thead>
            <tbody>${rows}</tbody>
        </table></div>
    `);
}

function renderGatherSummary(data) {
    const g = data.gather_summary || {};
    const id = data.identity || {};
    const badges = [];
    if (id.country && id.country.flag) {
        badges.push(`<span class="px-2 py-1 rounded bg-slate-800 text-sm" title="approx. from Discord locale">${id.country.flag} ${escapeHtml(id.country.country || '')}</span>`);
    }
    if (id.twitch && id.twitch.login) {
        badges.push(`<a href="${escapeHtml(id.twitch.url)}" target="_blank" rel="noopener" class="px-2 py-1 rounded bg-violet-900/50 text-violet-200 text-sm hover:bg-violet-800/60">📺 ${escapeHtml(id.twitch.login)}</a>`);
    }
    const badgeRow = badges.length ? `<div class="flex flex-wrap gap-2 mb-4">${badges.join('')}</div>` : '';
    if (!g.available) {
        if (!badgeRow) return '';
        return _panel('Gather Record', 'trophy', badgeRow + _na('No gather results yet'));
    }
    const st = g.current_type === 'W' ? 'text-emerald-400' : g.current_type === 'L' ? 'text-rose-400' : 'text-slate-400';
    const streakTxt = `${_num(g.current_streak)}${escapeHtml(g.current_type || '')}`;
    const cells = [
        _statCell('Gathers', _num(g.gathers)),
        _statCell('Win Rate', `${_num(g.win_rate, 1)}%`, g.win_rate >= 50 ? 'text-emerald-400' : 'text-rose-400'),
        _statCell('Record (W-L-D)', `${_num(g.wins)}-${_num(g.losses)}-${_num(g.draws)}`),
        _statCell('Current Streak', streakTxt, st),
        _statCell('Longest Win', _num(g.longest_win), 'text-emerald-400'),
        _statCell('Longest Loss', _num(g.longest_loss), 'text-rose-400'),
    ].join('');
    return _panel('Gather Record', 'trophy',
        `${badgeRow}<div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">${cells}</div>`);
}

function renderNickHistory(nh) {
    if (!nh || !nh.available || !(nh.names || []).length) return '';
    const rows = nh.names.map(n => `
        <tr class="border-b border-white/5">
            <td class="py-1 px-2 text-white">${escapeHtml(n.name)}</td>
            <td class="py-1 px-2 text-right text-slate-400">${_num(n.uses)}</td>
            <td class="py-1 px-2 text-right text-slate-500 text-xs">${escapeHtml(n.first_seen || '')} → ${escapeHtml(n.last_seen || '')}</td>
        </tr>`).join('');
    return _panel('Name History', 'history', `
        <div class="overflow-x-auto"><table class="w-full text-sm">
            <thead><tr class="text-[10px] uppercase text-slate-500 border-b border-white/10">
                <th class="py-1 px-2 text-left">Name</th><th class="py-1 px-2 text-right">Uses</th>
                <th class="py-1 px-2 text-right">Seen</th></tr></thead>
            <tbody>${rows}</tbody>
        </table></div>`);
}

function renderCombatTiming(ct) {
    if (!ct || !ct.available) return '';
    const ttk = ct.time_to_kill || {};
    const rf = ct.return_fire || {};
    const cells = [];
    if (ttk.median_ms !== undefined) {
        cells.push(_statCell('Time to Kill (med)', `${(ttk.median_ms / 1000).toFixed(2)}s`, 'text-cyan-300'));
        cells.push(_statCell('Kills sampled', _num(ttk.kills)));
    }
    if (rf.median_ms !== undefined) {
        cells.push(_statCell('Return-fire (med)', `${_num(rf.median_ms)}ms`, 'text-amber-300'));
        cells.push(_statCell('RF coverage', `${_num(rf.coverage_pct, 0)}%`));
    }
    if (!cells.length) return '';
    return _panel('Combat Timing', 'timer', `
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">${cells.join('')}</div>
        <p class="text-[11px] text-slate-500 mt-2">Medians (outliers dropped, Leetify-style). Time-to-Kill = first contact → kill; return-fire = got-hit → shoot-back.</p>
    `);
}

// ── Aim section (true-aim + improvements) ───────────────────────────────────

function renderAimSection(aim, guid) {
    if (!aim || !aim.available) return _panel('True Aim', 'crosshair', _na('No true-aim data for this player'));
    const lt = aim.lifetime || {};
    const flick = aim.flick || {};
    const er = aim.enemy_relative || {};
    const sp = aim.spread || {};
    const bu = aim.burst || {};

    const head = [
        _statCell('Shots Tracked', _num(lt.n)),
        _statCell('Pitch Mean', `${_num(lt.pitch_mean_deg, 1)}°`),
        _statCell('Pitch Discipline', `±${_num(lt.pitch_std_deg, 1)}°`, 'text-cyan-300'),
        flick.available ? _statCell('Flick Shots', `${_num(flick.flick_pct, 1)}%`, 'text-amber-300') : _statCell('Flick Shots', '--'),
        flick.available ? _statCell('Tracking', `${_num(flick.track_pct, 1)}%`, 'text-emerald-300') : _statCell('Tracking', '--'),
        er.available ? _statCell('Crosshair Error (med)', `${_num(er.median_error_deg, 1)}°`, 'text-violet-300') : _statCell('Crosshair Error', '--'),
    ].join('');

    // Spread control + burst-fire profile (from consecutive-shot timing/angles)
    const spreadBurst = [
        sp.available ? _statCell('Spread Control', `${_num(sp.control_pct, 1)}%`, 'text-emerald-300') : _statCell('Spread Control', '--'),
        sp.available ? _statCell('Min Spread', `${_num(sp.min_spread_deg, 1)}°`, 'text-cyan-300') : _statCell('Min Spread', '--'),
        sp.available ? _statCell('Median Spread', `${_num(sp.median_spread_deg, 1)}°`) : _statCell('Median Spread', '--'),
        sp.available ? _statCell('Max Spread', `${_num(sp.max_spread_deg, 1)}°`, 'text-rose-300') : _statCell('Max Spread', '--'),
        bu.available ? _statCell('Avg Burst', `${_num(bu.avg_burst_len, 1)} shots`, 'text-amber-300') : _statCell('Avg Burst', '--'),
        bu.available ? _statCell('Tap / Burst', `${_num(bu.tap_pct, 0)}% / ${_num(bu.burst_pct, 0)}%`) : _statCell('Tap / Burst', '--'),
    ].join('');

    const perWeapon = (aim.per_weapon || []).slice(0, 10).map(w => `
        <tr class="border-b border-white/5">
            <td class="py-1 px-2 text-white">${escapeHtml(w.weapon)}</td>
            <td class="py-1 px-2 text-right">${_num(w.shots)}</td>
            <td class="py-1 px-2 text-right">${_num(w.pitch_mean_deg, 1)}°</td>
            <td class="py-1 px-2 text-right text-slate-400">±${_num(w.circular_std_deg, 0)}°</td>
        </tr>`).join('');

    const erNote = er.available
        ? `<p class="text-[11px] text-slate-500 mt-2">Crosshair error is approximate (vs engagement-end enemy position), ${_num(er.matched_shots)} shots, avg ${_num(er.avg_error_deg, 1)}°.</p>`
        : '';

    return _panel('True Aim', 'crosshair', `
        <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-3">${head}</div>
        <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-5">${spreadBurst}</div>
        <div class="grid md:grid-cols-2 gap-6">
            <div>
                <div class="text-[11px] uppercase tracking-wide text-slate-500 mb-2">Per-weapon vertical aim</div>
                <div class="overflow-x-auto"><table class="w-full text-sm">
                    <thead><tr class="text-[10px] uppercase text-slate-500 border-b border-white/10">
                        <th class="py-1 px-2 text-left">Weapon</th><th class="py-1 px-2 text-right">Shots</th>
                        <th class="py-1 px-2 text-right">Pitch</th><th class="py-1 px-2 text-right">Spread</th>
                    </tr></thead><tbody>${perWeapon}</tbody>
                </table></div>
            </div>
            <div>
                <div class="flex items-center justify-between mb-2">
                    <div class="text-[11px] uppercase tracking-wide text-slate-500">Aim direction (per map)</div>
                    <select id="aim-map-select" class="bg-slate-800 text-slate-200 text-xs rounded px-2 py-1 border border-white/10"></select>
                </div>
                <canvas id="aim-rose-canvas" width="280" height="280" class="mx-auto"></canvas>
                <div id="aim-rose-note" class="text-[11px] text-slate-500 mt-1 text-center"></div>
            </div>
        </div>
        ${erNote}
    `);
}

async function wireAimRose(guid, maps) {
    const select = document.getElementById('aim-map-select');
    const canvas = document.getElementById('aim-rose-canvas');
    if (!select || !canvas || !guid) return;

    // The aim endpoint requires a map. `maps` is the structured list from the
    // profile payload (most-played first); no DOM scraping.
    const list = (Array.isArray(maps) ? maps : []).slice(0, 12);
    // Build <option>s via the DOM (textContent) — no innerHTML, inherently
    // XSS-safe regardless of map-name contents.
    select.replaceChildren();
    if (list.length === 0) {
        const opt = document.createElement('option');
        opt.textContent = 'no maps';
        select.appendChild(opt);
        return;
    }
    for (const m of list) {
        const opt = document.createElement('option');
        opt.value = m;
        opt.textContent = m;
        select.appendChild(opt);
    }
    const load = () => drawAimRose(guid, select.value, canvas);
    select.addEventListener('change', load);
    load();
}

async function drawAimRose(guid, mapName, canvas) {
    const note = document.getElementById('aim-rose-note');
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!mapName) return;
    let resp;
    try {
        resp = await fetchJSON(`${API_BASE}/proximity/player-aim?map_name=${encodeURIComponent(mapName)}&player_guid=${encodeURIComponent(guid)}`);
    } catch (e) {
        if (note) note.textContent = 'Failed to load aim rose';
        return;
    }
    // Aggregate a global 16-bucket rose from all hotzones.
    const buckets = new Array(_AIM_YAW_BUCKETS).fill(0);
    (resp.hotzones || []).forEach(hz => {
        (hz.rose || []).forEach((c, i) => { buckets[i] += (c || 0); });
    });
    const total = buckets.reduce((a, b) => a + b, 0);
    if (total === 0) {
        if (note) note.textContent = `No aim samples on ${mapName}`;
        return;
    }
    const cx = canvas.width / 2, cy = canvas.height / 2, R = Math.min(cx, cy) - 12;
    const max = Math.max(...buckets);
    // grid
    ctx.strokeStyle = 'rgba(255,255,255,0.08)';
    for (let g = 1; g <= 3; g++) {
        ctx.beginPath(); ctx.arc(cx, cy, R * g / 3, 0, Math.PI * 2); ctx.stroke();
    }
    // petals
    for (let i = 0; i < _AIM_YAW_BUCKETS; i++) {
        const frac = buckets[i] / max;
        const a0 = (i / _AIM_YAW_BUCKETS) * Math.PI * 2 - Math.PI / 2;
        const a1 = ((i + 1) / _AIM_YAW_BUCKETS) * Math.PI * 2 - Math.PI / 2;
        const r = R * frac;
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.arc(cx, cy, r, a0, a1);
        ctx.closePath();
        ctx.fillStyle = `rgba(34,211,238,${0.25 + 0.55 * frac})`;
        ctx.fill();
    }
    const circ = resp.circular || {};
    if (note) {
        note.textContent = `${_num(total)} shots • spread ±${_num(circ.circular_std_deg, 0)}° • ${(resp.narrative && resp.narrative[1]) || ''}`;
    }
}

// Expose to window for onclick handlers in HTML
window.loadPlayerProfile = loadPlayerProfile;
