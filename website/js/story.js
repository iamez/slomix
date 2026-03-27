/**
 * Smart Stats / Storytelling module (legacy)
 * Kill Impact Score (KIS) visualization
 * @module story
 */

import { API_BASE, fetchJSON, formatNumber, escapeHtml } from './utils.js';

function stripEtColors(text) {
    if (!text) return '';
    return String(text).replace(/\^[0-9A-Za-z]/g, '');
}

let storyLoadId = 0;

const DEFAULT_SCOPE_RANGE_DAYS = 365;

const storyState = {
    sessions: [],
    sessionDate: null,
    players: [],
    loading: false,
};

const ARCHETYPES = {
    pressure_engine:      { icon: '\u{1F525}', label: 'Pressure Engine',      color: 'rose' },
    medic_anchor:         { icon: '\u{1F489}', label: 'Medic Anchor',         color: 'emerald' },
    silent_assassin:      { icon: '\u{1F3AF}', label: 'Silent Assassin',      color: 'cyan' },
    frontline_warrior:    { icon: '\u{26A1}',  label: 'Frontline Warrior',    color: 'amber' },
    wall_breaker:         { icon: '\u{1F6E1}\uFE0F', label: 'Wall Breaker',   color: 'purple' },
    objective_specialist: { icon: '\u{1F527}', label: 'Objective Specialist', color: 'blue' },
    trade_master:         { icon: '\u{1F91D}', label: 'Trade Master',         color: 'teal' },
    survivor:             { icon: '\u{1F3C3}', label: 'Survivor',             color: 'lime' },
    chaos_agent:          { icon: '\u{1F4A5}', label: 'Chaos Agent',          color: 'orange' },
};

const ARCHETYPE_COLORS = {
    rose:    { bg: 'bg-rose-500/20',    border: 'border-rose-500/40',    text: 'text-rose-400' },
    cyan:    { bg: 'bg-cyan-500/20',    border: 'border-cyan-500/40',    text: 'text-cyan-400' },
    amber:   { bg: 'bg-amber-500/20',   border: 'border-amber-500/40',   text: 'text-amber-400' },
    yellow:  { bg: 'bg-yellow-500/20',  border: 'border-yellow-500/40',  text: 'text-yellow-400' },
    orange:  { bg: 'bg-orange-500/20',  border: 'border-orange-500/40',  text: 'text-orange-400' },
    purple:  { bg: 'bg-purple-500/20',  border: 'border-purple-500/40',  text: 'text-purple-400' },
    emerald: { bg: 'bg-emerald-500/20', border: 'border-emerald-500/40', text: 'text-emerald-400' },
    blue:    { bg: 'bg-blue-500/20',    border: 'border-blue-500/40',    text: 'text-blue-400' },
    slate:   { bg: 'bg-slate-500/20',   border: 'border-slate-500/40',   text: 'text-slate-400' },
    teal:    { bg: 'bg-teal-500/20',    border: 'border-teal-500/40',    text: 'text-teal-400' },
    lime:    { bg: 'bg-lime-500/20',    border: 'border-lime-500/40',    text: 'text-lime-400' },
    red:     { bg: 'bg-red-500/20',     border: 'border-red-500/40',     text: 'text-red-400' },
};

function getArchetype(player) {
    const a = player.archetype;
    return (a && ARCHETYPES[a]) ? a : 'frontline_warrior';
}

function getKISTier(kis) {
    if (kis >= 40) return { label: 'Legendary', css: 'from-amber-400 to-yellow-500', textCss: 'text-amber-400' };
    if (kis >= 25) return { label: 'Great', css: 'from-emerald-400 to-cyan-500', textCss: 'text-emerald-400' };
    if (kis >= 15) return { label: 'Solid', css: 'from-blue-400 to-indigo-500', textCss: 'text-blue-400' };
    return { label: 'Quiet', css: 'from-slate-400 to-slate-500', textCss: 'text-slate-400' };
}

async function loadStoryScopes() {
    try {
        const data = await fetchJSON(`${API_BASE}/proximity/scopes?range_days=${DEFAULT_SCOPE_RANGE_DAYS}`);
        storyState.sessions = Array.isArray(data?.sessions) ? data.sessions : [];
        if (!storyState.sessionDate && storyState.sessions.length > 0) {
            storyState.sessionDate = storyState.sessions[0].session_date;
        }
    } catch {
        storyState.sessions = [];
        storyState.sessionDate = null;
    }
    renderSessionSelector();
}

function renderSessionSelector() {
    const select = document.getElementById('story-session-select');
    if (!select) return;

    select.innerHTML = storyState.sessions.map(s => {
        const d = s.session_date;
        const count = s.maps?.length || 0;
        const label = `${escapeHtml(d)} (${count} map${count !== 1 ? 's' : ''})`;
        const selected = d === storyState.sessionDate ? ' selected' : '';
        return `<option value="${escapeHtml(d)}"${selected}>${label}</option>`;
    }).join('');

    select.onchange = () => {
        storyState.sessionDate = select.value;
        loadStoryData();
    };
}

async function loadStoryData() {
    if (!storyState.sessionDate) {
        renderEmpty('No sessions available');
        return;
    }

    const loadId = ++storyLoadId;
    storyState.loading = true;
    renderLoading();

    try {
        const data = await fetchJSON(
            `${API_BASE}/storytelling/kill-impact?session_date=${encodeURIComponent(storyState.sessionDate)}&limit=50`
        );
        if (loadId !== storyLoadId) return;
        storyState.players = Array.isArray(data?.players) ? data.players : [];

        if (storyState.players.length === 0) {
            renderEmpty('No kill impact data for this session');
            return;
        }

        renderStoryHero(storyState.sessionDate, storyState.players);
        renderPlayerCards(storyState.players);
        renderKISBreakdown(storyState.players);

        // Fetch moments + team synergy in parallel (non-blocking)
        fetchJSON(
            `${API_BASE}/storytelling/moments?session_date=${encodeURIComponent(storyState.sessionDate)}&limit=10`
        ).then(momData => {
            if (loadId === storyLoadId) renderMoments(momData);
        }).catch(() => renderMoments(null));

        fetchJSON(
            `${API_BASE}/storytelling/synergy?session_date=${encodeURIComponent(storyState.sessionDate)}`
        ).then(synData => {
            if (loadId === storyLoadId) renderTeamSynergy(synData);
        }).catch(() => renderTeamSynergy(null));

        fetchJSON(
            `${API_BASE}/storytelling/win-contribution?session_date=${encodeURIComponent(storyState.sessionDate)}`
        ).then(pwcData => {
            if (loadId === storyLoadId) renderWinContribution(pwcData);
        }).catch(() => renderWinContribution(null));
    } catch (err) {
        console.error('Story data load failed:', err);
        renderEmpty('Failed to load Smart Stats');
    } finally {
        storyState.loading = false;
    }
}

function renderLoading() {
    const hero = document.getElementById('story-hero-content');
    if (hero) {
        const title = document.getElementById('story-title');
        const subtitle = document.getElementById('story-subtitle');
        const statsRow = document.getElementById('story-stats-row');
        if (title) title.textContent = 'Loading...';
        if (subtitle) subtitle.textContent = '';
        if (statsRow) statsRow.innerHTML = '';
    }
    const moments = document.getElementById('story-moments');
    if (moments) moments.innerHTML = '';
    const players = document.getElementById('story-players');
    if (players) players.innerHTML = '<div class="col-span-full text-center text-slate-500 py-12">Loading kill impact data...</div>';
    const breakdown = document.getElementById('story-kis-breakdown');
    if (breakdown) breakdown.innerHTML = '';
    const synergy = document.getElementById('story-team-synergy');
    if (synergy) synergy.innerHTML = '';
    const pwc = document.getElementById('story-win-contribution');
    if (pwc) pwc.innerHTML = '';
}

function renderEmpty(message) {
    const title = document.getElementById('story-title');
    const subtitle = document.getElementById('story-subtitle');
    const statsRow = document.getElementById('story-stats-row');
    if (title) title.textContent = 'Smart Stats';
    if (subtitle) subtitle.textContent = message;
    if (statsRow) statsRow.innerHTML = '';

    const players = document.getElementById('story-players');
    if (players) {
        players.innerHTML = `<div class="col-span-full text-center py-16">
            <div class="text-slate-600 text-4xl mb-3">\u{1F4CA}</div>
            <div class="text-slate-400 text-sm">${escapeHtml(message)}</div>
        </div>`;
    }
    const moments2 = document.getElementById('story-moments');
    if (moments2) moments2.innerHTML = '';
    const breakdown = document.getElementById('story-kis-breakdown');
    if (breakdown) breakdown.innerHTML = '';
    const synergy2 = document.getElementById('story-team-synergy');
    if (synergy2) synergy2.innerHTML = '';
    const pwc2 = document.getElementById('story-win-contribution');
    if (pwc2) pwc2.innerHTML = '';
}

function renderStoryHero(sessionDate, players) {
    const title = document.getElementById('story-title');
    const subtitle = document.getElementById('story-subtitle');
    const statsRow = document.getElementById('story-stats-row');

    const totalKIS = players.reduce((s, p) => s + (p.total_kis || 0), 0);
    const totalKills = players.reduce((s, p) => s + (p.kills || 0), 0);
    const topPlayer = players[0];

    if (title) title.textContent = `Session ${sessionDate}`;
    if (subtitle) subtitle.textContent = `${players.length} players \u2022 Kill Impact Score analysis`;

    if (statsRow) {
        statsRow.innerHTML = `
            <div class="flex flex-col">
                <span class="text-xs text-slate-500 uppercase tracking-wider">Total KIS</span>
                <span class="text-lg font-bold text-amber-400">${formatNumber(Math.round(totalKIS))}</span>
            </div>
            <div class="flex flex-col">
                <span class="text-xs text-slate-500 uppercase tracking-wider">Kills</span>
                <span class="text-lg font-bold text-white">${formatNumber(totalKills)}</span>
            </div>
            <div class="flex flex-col">
                <span class="text-xs text-slate-500 uppercase tracking-wider">Players</span>
                <span class="text-lg font-bold text-white">${players.length}</span>
            </div>
            <div class="flex flex-col">
                <span class="text-xs text-slate-500 uppercase tracking-wider">MVP</span>
                <span class="text-lg font-bold text-amber-400">${topPlayer ? escapeHtml(stripEtColors(topPlayer.name)) : '-'}</span>
            </div>
        `;
    }
}

function renderPlayerCards(players) {
    const container = document.getElementById('story-players');
    if (!container) return;

    container.innerHTML = players.map((p, idx) => {
        const archKey = getArchetype(p);
        const arch = ARCHETYPES[archKey];
        const colors = ARCHETYPE_COLORS[arch.color];
        const tier = getKISTier(p.total_kis);
        const rank = idx + 1;

        const carrierBar = p.kills > 0 ? ((p.carrier_kills / p.kills) * 100).toFixed(0) : 0;
        const pushBar = p.kills > 0 ? ((p.push_kills / p.kills) * 100).toFixed(0) : 0;
        const crossfireBar = p.kills > 0 ? ((p.crossfire_kills / p.kills) * 100).toFixed(0) : 0;

        return `
        <div class="rounded-xl border border-white/[0.08] bg-white/[0.03] hover:bg-white/[0.06] transition-all duration-200 p-4 group">
            <!-- Header -->
            <div class="flex items-start justify-between mb-3">
                <div class="flex items-center gap-2.5">
                    <div class="w-7 h-7 rounded-lg bg-gradient-to-br ${tier.css} flex items-center justify-center text-xs font-black text-black/80">
                        ${rank}
                    </div>
                    <div>
                        <div class="text-sm font-semibold text-white leading-tight">${escapeHtml(stripEtColors(p.name))}</div>
                        <div class="flex items-center gap-1.5 mt-0.5">
                            <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold ${colors.bg} ${colors.border} ${colors.text} border">
                                ${arch.icon} ${escapeHtml(arch.label)}
                            </span>
                        </div>
                    </div>
                </div>
                <div class="text-right">
                    <div class="text-lg font-black bg-gradient-to-r ${tier.css} bg-clip-text text-transparent">${(p.total_kis ?? 0).toFixed(1)}</div>
                    <div class="text-[10px] ${tier.textCss} font-bold uppercase tracking-wider">${escapeHtml(tier.label)}</div>
                </div>
            </div>

            <!-- Stats row -->
            <div class="grid grid-cols-4 gap-2 text-center mb-3">
                <div>
                    <div class="text-xs font-bold text-white">${p.kills}</div>
                    <div class="text-[10px] text-slate-500">Kills</div>
                </div>
                <div>
                    <div class="text-xs font-bold text-rose-400">${p.carrier_kills}</div>
                    <div class="text-[10px] text-slate-500">Carrier</div>
                </div>
                <div>
                    <div class="text-xs font-bold text-amber-400">${p.push_kills}</div>
                    <div class="text-[10px] text-slate-500">Push</div>
                </div>
                <div>
                    <div class="text-xs font-bold text-cyan-400">${p.crossfire_kills}</div>
                    <div class="text-[10px] text-slate-500">Crossfire</div>
                </div>
            </div>

            <!-- Context bar -->
            <div class="h-1.5 rounded-full bg-slate-800 overflow-hidden flex">
                <div class="bg-rose-500/80 transition-all" style="width:${carrierBar}%"></div>
                <div class="bg-amber-500/80 transition-all" style="width:${pushBar}%"></div>
                <div class="bg-cyan-500/80 transition-all" style="width:${crossfireBar}%"></div>
            </div>
            <div class="flex justify-between mt-1 text-[9px] text-slate-600">
                <span>Avg impact: ${(p.avg_impact ?? 0).toFixed(2)}</span>
                <span>Context: ${p.kills > 0 ? (((p.carrier_kills + p.push_kills + p.crossfire_kills) / p.kills) * 100).toFixed(0) : 0}%</span>
            </div>
        </div>`;
    }).join('');
}

function renderKISBreakdown(players) {
    const container = document.getElementById('story-kis-breakdown');
    if (!container) return;

    // Build stacked bar for top 10 players
    const top = players.slice(0, 12);
    const maxKIS = Math.max(...top.map(p => p.total_kis), 1);

    const SEGMENTS = [
        { key: 'base',      label: 'Base',      color: 'bg-slate-500' },
        { key: 'carrier',   label: 'Carrier',   color: 'bg-rose-500' },
        { key: 'push',      label: 'Push',       color: 'bg-amber-500' },
        { key: 'crossfire', label: 'Crossfire',  color: 'bg-cyan-500' },
    ];

    const legend = SEGMENTS.map(s =>
        `<span class="inline-flex items-center gap-1.5 text-[10px] text-slate-400">
            <span class="w-2.5 h-2.5 rounded-sm ${s.color}"></span>${escapeHtml(s.label)}
        </span>`
    ).join('');

    const bars = top.map(p => {
        // NOTE: Segment widths are approximations based on kill counts × avg_impact.
        // Actual per-kill multipliers vary; this is a visualization heuristic only.
        const carrierKIS = p.carrier_kills * (p.avg_impact || 1);
        const pushKIS = p.push_kills * (p.avg_impact || 1) * 0.8;
        const crossfireKIS = p.crossfire_kills * (p.avg_impact || 1) * 0.7;
        const segmentTotal = carrierKIS + pushKIS + crossfireKIS;
        const baseKIS = Math.max(0, (p.total_kis ?? 0) - segmentTotal);
        // baseKIS + segmentTotal should equal p.total_kis

        const pct = (v) => ((v / maxKIS) * 100).toFixed(1);

        const safeName = escapeHtml(stripEtColors(p.name));
        return `
        <div class="flex items-center gap-3 mb-1.5">
            <div class="w-24 text-xs text-slate-400 truncate text-right" title="${safeName}">${safeName}</div>
            <div class="flex-1 h-5 rounded bg-slate-800/50 overflow-hidden flex">
                <div class="${SEGMENTS[0].color}/60 h-full" style="width:${pct(baseKIS)}%"></div>
                <div class="${SEGMENTS[1].color}/80 h-full" style="width:${pct(carrierKIS)}%"></div>
                <div class="${SEGMENTS[2].color}/80 h-full" style="width:${pct(pushKIS)}%"></div>
                <div class="${SEGMENTS[3].color}/80 h-full" style="width:${pct(crossfireKIS)}%"></div>
            </div>
            <div class="w-12 text-xs text-slate-400 text-right font-mono">${(p.total_kis ?? 0).toFixed(1)}</div>
        </div>`;
    }).join('');

    container.innerHTML = `
        <div class="flex gap-4 mb-4">${legend}</div>
        ${bars}
    `;
}

const MOMENT_TYPES = {
    push_success:       { icon: '\u{1F6E1}\uFE0F', color: 'amber',   bg: 'bg-amber-500/15',   border: 'border-amber-500/30',   text: 'text-amber-400' },
    trade_chain:        { icon: '\u26A1',           color: 'cyan',    bg: 'bg-cyan-500/15',    border: 'border-cyan-500/30',    text: 'text-cyan-400' },
    kill_streak:        { icon: '\u{1F480}',        color: 'rose',    bg: 'bg-rose-500/15',    border: 'border-rose-500/30',    text: 'text-rose-400' },
    focus_survival:     { icon: '\u{1F48E}',        color: 'purple',  bg: 'bg-purple-500/15',  border: 'border-purple-500/30',  text: 'text-purple-400' },
    carrier_chain:      { icon: '\u{1F3AF}',        color: 'emerald', bg: 'bg-emerald-500/15', border: 'border-emerald-500/30', text: 'text-emerald-400' },
    objective_secured:  { icon: '\u{1F3C6}',        color: 'yellow',  bg: 'bg-yellow-500/15',  border: 'border-yellow-500/30',  text: 'text-yellow-400' },
    objective_denied:   { icon: '\u{1F6AB}',        color: 'red',     bg: 'bg-red-500/15',     border: 'border-red-500/30',     text: 'text-red-400' },
    objective_run:      { icon: '\u{1F527}',        color: 'blue',    bg: 'bg-blue-500/15',    border: 'border-blue-500/30',    text: 'text-blue-400' },
    multi_revive:       { icon: '\u{1F489}',        color: 'emerald', bg: 'bg-emerald-500/15', border: 'border-emerald-500/30', text: 'text-emerald-400' },
    team_wipe:          { icon: '\u{1F480}',        color: 'rose',    bg: 'bg-rose-500/15',    border: 'border-rose-500/30',    text: 'text-rose-400' },
    multikill:          { icon: '\u{1F525}',        color: 'amber',   bg: 'bg-amber-500/15',   border: 'border-amber-500/30',   text: 'text-amber-400' },
};

function renderMoments(data) {
    const container = document.getElementById('story-moments');
    if (!container) return;

    const moments = Array.isArray(data?.moments) ? data.moments : [];
    if (moments.length === 0) {
        container.innerHTML = '<div class="text-slate-500 text-sm py-4">No key moments for this session</div>';
        return;
    }

    container.innerHTML = moments.map((m, idx) => {
        const mt = MOMENT_TYPES[m.type] || MOMENT_TYPES.kill_streak;
        const stars = '\u2605'.repeat(Math.min(Math.max(Math.round(m.impact_stars || m.impact || 0), 0), 5));
        const safeName = escapeHtml(stripEtColors(m.player || m.player_name || ''));
        const safeNarrative = escapeHtml(m.narrative || '');
        const safeMap = escapeHtml(m.map_name || '');
        const roundLabel = (m.round_number || m.round_num) ? `R${m.round_number || m.round_num}` : '';
        const timeLabel = m.time_formatted || '';
        const delay = idx * 80;

        // Rich kill breakdown for team_wipe and multikill moments
        let killBreakdown = '';
        if (Array.isArray(m.kills) && m.kills.length > 0) {
            const killLines = m.kills.map(k => {
                const killer = escapeHtml(stripEtColors(k.killer || ''));
                const victim = escapeHtml(stripEtColors(k.victim || ''));
                const weapon = escapeHtml(k.weapon || '');
                const kTime = k.time_formatted || '';
                return `<div class="flex items-center gap-1">
                    <span class="text-white">${killer}</span>
                    <span class="text-slate-600">\u2192</span>
                    <span class="text-red-400">${victim}</span>
                    ${weapon ? `<span class="text-slate-600 ml-auto">${weapon}</span>` : ''}
                    ${kTime ? `<span class="text-slate-700 w-8 text-right">${kTime}</span>` : ''}
                </div>`;
            }).join('');
            const durationLabel = m.duration_ms != null ? `${(m.duration_ms / 1000).toFixed(1)}s` : '';
            killBreakdown = `
                <div class="mt-2 pt-2 border-t border-white/5 space-y-0.5 text-[10px]">
                    ${killLines}
                    ${durationLabel ? `<div class="text-slate-600 mt-1">Duration: ${durationLabel}</div>` : ''}
                </div>`;
        }

        // Wider card for moments with kill breakdown
        const cardWidth = (m.kills && m.kills.length > 0) ? 'w-72' : 'w-56';

        return `
        <div class="flex-shrink-0 ${cardWidth} rounded-xl border ${mt.border} ${mt.bg} p-4 opacity-0 translate-y-3"
             style="animation: momentFadeUp 0.4s ease-out ${delay}ms forwards">
            <div class="flex items-center justify-between mb-2">
                <span class="text-lg">${mt.icon}</span>
                <div class="flex items-center gap-2">
                    ${timeLabel ? `<span class="text-[10px] text-slate-500 font-mono">${escapeHtml(timeLabel)}</span>` : ''}
                    <span class="text-amber-400 text-xs tracking-wider">${stars}</span>
                </div>
            </div>
            <div class="text-xs font-bold text-white mb-1 truncate" title="${safeName}">${safeName}</div>
            <div class="text-[11px] text-slate-300 mb-2 line-clamp-2 leading-relaxed">${safeNarrative}</div>
            <div class="flex items-center gap-2 text-[10px] text-slate-500">
                ${roundLabel ? `<span>${escapeHtml(roundLabel)}</span>` : ''}
                ${safeMap ? `<span class="truncate">${safeMap}</span>` : ''}
            </div>
            ${killBreakdown}
        </div>`;
    }).join('');
}

const SYNERGY_AXES = [
    { key: 'crossfire', label: 'Crossfire Rate' },
    { key: 'trade',     label: 'Trade Coverage' },
    { key: 'cohesion',  label: 'Cohesion' },
    { key: 'push',      label: 'Push Quality' },
    { key: 'medic',     label: 'Medic Bond' },
];

const GROUP_STYLES = {
    group_a: { bar: 'bg-red-500',  text: 'text-red-400',  bg: 'bg-red-500/5',  border: 'border-red-500/20' },
    group_b: { bar: 'bg-blue-500', text: 'text-blue-400', bg: 'bg-blue-500/5', border: 'border-blue-500/20' },
};

function renderTeamSynergy(data) {
    const container = document.getElementById('story-team-synergy');
    if (!container) return;

    const groups = data?.groups;
    if (!groups || (!groups.group_a && !groups.group_b)) {
        container.innerHTML = '<div class="text-center text-slate-500 py-8 text-sm">No synergy data available</div>';
        return;
    }

    function renderPanel(gkey) {
        const style = GROUP_STYLES[gkey];
        const gd = groups[gkey];
        if (!gd) return '';
        const composite = gd.composite ?? 0;
        const players = Array.isArray(gd.players) ? gd.players : [];
        const nameList = players.map(n => escapeHtml(stripEtColors(n))).join(', ');

        const bars = SYNERGY_AXES.map(axis => {
            const val = gd[axis.key] ?? 0;
            return `
                <div class="flex items-center gap-2 mb-2">
                    <div class="w-24 text-[11px] text-slate-400 truncate">${escapeHtml(axis.label)}</div>
                    <div class="flex-1 h-2.5 rounded-full bg-slate-800 overflow-hidden">
                        <div class="${style.bar}/70 h-full rounded-full transition-all duration-500" style="width:${val.toFixed(1)}%"></div>
                    </div>
                    <div class="w-8 text-[11px] text-slate-400 text-right font-mono">${val.toFixed(0)}</div>
                </div>`;
        }).join('');

        return `
            <div class="flex-1 rounded-xl border ${style.border} ${style.bg} p-5">
                <div class="flex items-center justify-between mb-4">
                    <div>
                        <div class="text-sm font-bold text-white">${nameList || gkey}</div>
                    </div>
                    <div class="text-2xl font-black ${style.text}">${composite.toFixed(1)}</div>
                </div>
                ${bars}
            </div>`;
    }

    container.innerHTML = `
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            ${renderPanel('group_a')}
            ${renderPanel('group_b')}
        </div>
    `;
}

// ── Player Win Contribution (PWC) ────────────────────────────────

const PWC_COMPONENTS = [
    { key: 'kills',      label: 'Kills',      color: 'bg-rose-500' },
    { key: 'damage',     label: 'Damage',     color: 'bg-amber-500' },
    { key: 'objectives', label: 'Objectives', color: 'bg-blue-500' },
    { key: 'revives',    label: 'Revives',    color: 'bg-emerald-500' },
    { key: 'survival',   label: 'Survival',   color: 'bg-cyan-500' },
];

function renderWinContribution(data) {
    const container = document.getElementById('story-win-contribution');
    if (!container) return;

    const players = Array.isArray(data?.players) ? data.players : [];
    const mvp = data?.mvp;

    if (players.length === 0) {
        container.innerHTML = '<div class="text-center text-slate-500 py-8 text-sm">No win contribution data available</div>';
        return;
    }

    // MVP highlight card
    let mvpCard = '';
    if (mvp) {
        const mvpName = escapeHtml(stripEtColors(mvp.name));
        const wisSign = mvp.wis >= 0 ? '+' : '';
        mvpCard = `
            <div class="rounded-xl border border-amber-500/30 bg-gradient-to-br from-amber-500/10 via-amber-900/10 to-slate-900 p-5 mb-5">
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-3">
                        <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-400 to-yellow-500 flex items-center justify-center text-lg font-black text-black/80">&#9733;</div>
                        <div>
                            <div class="text-xs text-amber-400 font-bold tracking-[0.2em] uppercase">Session MVP</div>
                            <div class="text-lg font-black text-white">${mvpName}</div>
                        </div>
                    </div>
                    <div class="text-right">
                        <div class="text-2xl font-black text-amber-400">${mvp.total_pwc.toFixed(2)}</div>
                        <div class="text-[10px] text-slate-400">PWC &middot; WIS ${wisSign}${mvp.wis.toFixed(3)}</div>
                    </div>
                </div>
            </div>`;
    }

    // Legend
    const legend = PWC_COMPONENTS.map(c =>
        `<span class="inline-flex items-center gap-1.5 text-[10px] text-slate-400">
            <span class="w-2.5 h-2.5 rounded-sm ${c.color}"></span>${escapeHtml(c.label)}
        </span>`
    ).join('');

    // Per-player stacked bars (top 15)
    const top = players.slice(0, 15);
    const maxPWC = Math.max(...top.map(p => p.total_pwc), 0.01);

    const bars = top.map((p, idx) => {
        const safeName = escapeHtml(stripEtColors(p.name));
        const comp = p.components || {};
        const wisSign = p.wis >= 0 ? '+' : '';
        const rank = idx + 1;

        // Stacked bar segments
        const segments = PWC_COMPONENTS.map(c => {
            const val = comp[c.key] || 0;
            const pct = ((val / maxPWC) * 100).toFixed(1);
            return `<div class="${c.color}/70 h-full" style="width:${pct}%"></div>`;
        }).join('');

        // Per-round mini dots
        const roundDots = (p.per_round || []).map(r =>
            `<span class="inline-block w-1.5 h-1.5 rounded-full ${r.won ? 'bg-emerald-400' : 'bg-red-400'}" title="R${r.round_number} ${escapeHtml(r.map_name)} — PWC ${r.pwc}${r.won ? ' W' : ' L'}"></span>`
        ).join('');

        return `
        <div class="flex items-center gap-3 mb-2 group">
            <div class="w-5 text-[10px] text-slate-600 text-right font-mono">${rank}</div>
            <div class="w-24 text-xs text-slate-400 truncate text-right" title="${safeName}">${safeName}</div>
            <div class="flex-1 h-5 rounded bg-slate-800/50 overflow-hidden flex">${segments}</div>
            <div class="w-12 text-xs text-slate-400 text-right font-mono">${p.total_pwc.toFixed(2)}</div>
            <div class="w-16 text-[10px] text-right font-mono ${p.wis >= 0 ? 'text-emerald-400' : 'text-red-400'}">${wisSign}${p.wis.toFixed(3)}</div>
            <div class="hidden group-hover:flex items-center gap-0.5 w-20">${roundDots}</div>
        </div>`;
    }).join('');

    // Column headers
    const header = `
        <div class="flex items-center gap-3 mb-2 text-[10px] text-slate-600 uppercase tracking-wider">
            <div class="w-5 text-right">#</div>
            <div class="w-24 text-right">Player</div>
            <div class="flex-1">Contribution</div>
            <div class="w-12 text-right">PWC</div>
            <div class="w-16 text-right">WIS</div>
        </div>`;

    container.innerHTML = `
        ${mvpCard}
        <div class="flex gap-4 mb-4">${legend}</div>
        ${header}
        ${bars}
    `;
}

export async function loadStoryView() {
    await loadStoryScopes();
    await loadStoryData();
}
