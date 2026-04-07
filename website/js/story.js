/**
 * Smart Stats / Storytelling module (legacy)
 * Kill Impact Score (KIS) visualization
 * @module story
 */

import { API_BASE, fetchJSON, formatNumber } from './utils.js';

function stripEtColors(text) {
    if (!text) return '';
    return String(text).replace(/\^[0-9A-Za-z]/g, '');
}

/** Safe DOM element factory. Strings become text nodes; null/undefined children are skipped. */
function _el(tag, className, ...children) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    for (const c of children) {
        if (c == null) continue;
        el.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    }
    return el;
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

    select.textContent = '';
    storyState.sessions.forEach(s => {
        const d = s.session_date;
        const count = s.maps?.length || 0;
        const opt = document.createElement('option');
        opt.value = d;
        opt.textContent = `${d} (${count} map${count !== 1 ? 's' : ''})`;
        if (d === storyState.sessionDate) opt.selected = true;
        select.appendChild(opt);
    });

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

        // Fetch narrative, momentum, moments, synergy, win-contribution in parallel (non-blocking)
        fetchJSON(
            `${API_BASE}/storytelling/narrative?session_date=${encodeURIComponent(storyState.sessionDate)}`
        ).then(narData => {
            if (loadId === storyLoadId) renderNarrative(narData);
        }).catch(() => renderNarrative(null));

        fetchJSON(
            `${API_BASE}/storytelling/momentum?session_date=${encodeURIComponent(storyState.sessionDate)}`
        ).then(momtData => {
            if (loadId === storyLoadId) renderMomentum(momtData);
        }).catch(() => renderMomentum(null));

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

        fetchJSON(
            `${API_BASE}/skill/composite?session_date=${encodeURIComponent(storyState.sessionDate)}`
        ).then(compData => {
            if (loadId === storyLoadId) renderAdvancedMetrics(compData);
        }).catch(() => renderAdvancedMetrics(null));

        // Box Score
        const enc = encodeURIComponent(storyState.sessionDate);
        fetchJSON(`${API_BASE}/storytelling/box-score?session_date=${enc}`)
            .then(d => { if (loadId === storyLoadId) renderBoxScore(d); })
            .catch(() => renderBoxScore(null));

        // Invisible Value — 4 parallel fetches
        Promise.allSettled([
            fetchJSON(`${API_BASE}/storytelling/gravity?session_date=${enc}`),
            fetchJSON(`${API_BASE}/storytelling/space-created?session_date=${enc}`),
            fetchJSON(`${API_BASE}/storytelling/enabler?session_date=${enc}`),
            fetchJSON(`${API_BASE}/storytelling/lurker-profile?session_date=${enc}`),
        ]).then(([g, s, e, l]) => {
            if (loadId !== storyLoadId) return;
            renderInvisibleValue(
                g.status === 'fulfilled' ? g.value : null,
                s.status === 'fulfilled' ? s.value : null,
                e.status === 'fulfilled' ? e.value : null,
                l.status === 'fulfilled' ? l.value : null
            );
        }).catch(() => renderInvisibleValue(null, null, null, null));
    } catch (err) {
        console.error('Story data load failed:', err);
        renderEmpty('Failed to load Smart Stats');
    } finally {
        storyState.loading = false;
    }
}

function renderLoading() {
    const title = document.getElementById('story-title');
    const subtitle = document.getElementById('story-subtitle');
    const statsRow = document.getElementById('story-stats-row');
    if (title) title.textContent = 'Loading...';
    if (subtitle) subtitle.textContent = '';
    if (statsRow) statsRow.textContent = '';

    const narrative = document.getElementById('story-narrative');
    if (narrative) narrative.textContent = '';
    const momentum = document.getElementById('story-momentum');
    if (momentum) momentum.textContent = '';
    const moments = document.getElementById('story-moments');
    if (moments) moments.textContent = '';
    const players = document.getElementById('story-players');
    if (players) {
        players.textContent = '';
        players.appendChild(_el('div', 'col-span-full text-center text-slate-500 py-12', 'Loading kill impact data...'));
    }
    const breakdown = document.getElementById('story-kis-breakdown');
    if (breakdown) breakdown.textContent = '';
    const synergy = document.getElementById('story-team-synergy');
    if (synergy) synergy.textContent = '';
    const pwc = document.getElementById('story-win-contribution');
    if (pwc) pwc.textContent = '';
    const adv = document.getElementById('story-advanced-metrics');
    if (adv) adv.textContent = '';
    const boxScore = document.getElementById('story-box-score');
    if (boxScore) boxScore.textContent = '';
    const invisValue = document.getElementById('story-invisible-value');
    if (invisValue) invisValue.textContent = '';
}

function renderEmpty(message) {
    const title = document.getElementById('story-title');
    const subtitle = document.getElementById('story-subtitle');
    const statsRow = document.getElementById('story-stats-row');
    if (title) title.textContent = 'Smart Stats';
    if (subtitle) subtitle.textContent = message;
    if (statsRow) statsRow.textContent = '';

    const players = document.getElementById('story-players');
    if (players) {
        players.textContent = '';
        players.appendChild(_el('div', 'col-span-full text-center py-16',
            _el('div', 'text-slate-600 text-4xl mb-3', '\u{1F4CA}'),
            _el('div', 'text-slate-400 text-sm', message)
        ));
    }
    for (const id of ['story-narrative', 'story-momentum', 'story-moments', 'story-kis-breakdown', 'story-team-synergy', 'story-win-contribution', 'story-box-score', 'story-invisible-value']) {
        const el = document.getElementById(id);
        if (el) el.textContent = '';
    }
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
        statsRow.textContent = '';
        const stat = (label, value, cls) => _el('div', 'flex flex-col',
            _el('span', 'text-xs text-slate-500 uppercase tracking-wider', label),
            _el('span', `text-lg font-bold ${cls}`, value)
        );
        statsRow.appendChild(stat('Total KIS', formatNumber(Math.round(totalKIS)), 'text-amber-400'));
        statsRow.appendChild(stat('Kills', formatNumber(totalKills), 'text-white'));
        statsRow.appendChild(stat('Players', String(players.length), 'text-white'));
        statsRow.appendChild(stat('MVP', topPlayer ? stripEtColors(topPlayer.name) : '-', 'text-amber-400'));
    }
}

function renderNarrative(data) {
    const container = document.getElementById('story-narrative');
    if (!container) return;
    container.textContent = '';

    const text = data?.narrative;
    if (!text) return;

    const card = _el('div', 'rounded-xl border border-white/[0.06] bg-white/[0.02] px-5 py-4');
    const content = _el('div', 'text-sm text-slate-400 italic leading-relaxed', text);
    content.style.opacity = '0.8';
    card.appendChild(content);
    container.appendChild(card);
}

let _momentumChart = null;

function _createMomentumChart(canvas, round, idx) {
    const points = Array.isArray(round.points) ? round.points : [];
    if (points.length === 0) return null;

    const labels = points.map(pt => Math.round((pt.t_ms || 0) / 1000));
    const axisData = points.map(pt => pt.axis ?? 0);
    const alliesData = points.map(pt => pt.allies ?? 0);

    return new Chart(canvas, {
        type: 'line',
        data: {
            labels,
            datasets: [
                {
                    label: 'Axis',
                    data: axisData,
                    borderColor: 'rgba(239, 68, 68, 0.8)',
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    borderWidth: 1.5,
                    pointRadius: 0,
                    tension: 0.3,
                    fill: false,
                },
                {
                    label: 'Allies',
                    data: alliesData,
                    borderColor: 'rgba(59, 130, 246, 0.8)',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    borderWidth: 1.5,
                    pointRadius: 0,
                    tension: 0.3,
                    fill: false,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        color: 'rgba(148, 163, 184, 0.7)',
                        font: { size: 10 },
                        boxWidth: 12,
                        padding: 8,
                    },
                },
            },
            scales: {
                x: {
                    title: { display: true, text: 'Time (s)', color: 'rgba(148, 163, 184, 0.5)', font: { size: 9 } },
                    ticks: { color: 'rgba(148, 163, 184, 0.4)', font: { size: 9 }, maxTicksLimit: 8 },
                    grid: { color: 'rgba(255,255,255,0.04)' },
                },
                y: {
                    min: 0,
                    max: 100,
                    title: { display: true, text: 'Momentum', color: 'rgba(148, 163, 184, 0.5)', font: { size: 9 } },
                    ticks: { color: 'rgba(148, 163, 184, 0.4)', font: { size: 9 } },
                    grid: { color: 'rgba(255,255,255,0.04)' },
                },
            },
        },
    });
}

function renderMomentum(data) {
    const container = document.getElementById('story-momentum');
    if (!container) return;
    container.textContent = '';

    const rounds = Array.isArray(data?.rounds) ? data.rounds : [];
    if (rounds.length === 0) return;

    const heading = _el('h3', 'text-sm font-bold text-amber-400 tracking-widest uppercase mb-3', 'Momentum');
    container.appendChild(heading);

    // Tab bar (hidden if only 1 round)
    if (rounds.length > 1) {
        const tabBar = _el('div', 'flex gap-1 mb-3 overflow-x-auto');
        rounds.forEach((round, idx) => {
            const label = `R${round.round_number || idx + 1} ${round.map_name || ''}`;
            const btn = _el('button', '', label);
            btn.dataset.roundIdx = idx;
            btn.className = idx === 0
                ? 'px-3 py-1 text-xs rounded-lg bg-white/10 text-white border border-white/20 whitespace-nowrap'
                : 'px-3 py-1 text-xs rounded-lg text-slate-500 hover:text-slate-300 hover:bg-white/5 whitespace-nowrap';
            tabBar.appendChild(btn);
        });

        tabBar.addEventListener('click', (e) => {
            const btn = e.target.closest('button[data-round-idx]');
            if (!btn) return;
            const idx = parseInt(btn.dataset.roundIdx, 10);

            // Update tab styles
            tabBar.querySelectorAll('button').forEach(b => {
                b.className = 'px-3 py-1 text-xs rounded-lg text-slate-500 hover:text-slate-300 hover:bg-white/5 whitespace-nowrap';
            });
            btn.className = 'px-3 py-1 text-xs rounded-lg bg-white/10 text-white border border-white/20 whitespace-nowrap';

            // Recreate chart
            if (_momentumChart) { _momentumChart.destroy(); _momentumChart = null; }
            const canvas = document.createElement('canvas');
            const wrapper = container.querySelector('.momentum-chart-wrapper');
            wrapper.textContent = '';
            wrapper.style.height = '200px';
            wrapper.appendChild(canvas);
            _momentumChart = _createMomentumChart(canvas, rounds[idx], idx);
        });

        container.appendChild(tabBar);
    }

    // Chart wrapper with single canvas — fixed 200px height
    const wrapper = _el('div', 'rounded-xl border border-white/[0.08] bg-white/[0.03] p-4 momentum-chart-wrapper');
    wrapper.style.overflow = 'hidden';
    wrapper.style.height = '200px';
    const canvas = document.createElement('canvas');
    wrapper.appendChild(canvas);
    container.appendChild(wrapper);

    // Render first round
    if (_momentumChart) { _momentumChart.destroy(); _momentumChart = null; }
    _momentumChart = _createMomentumChart(canvas, rounds[0], 0);
}

function renderPlayerCards(players) {
    const container = document.getElementById('story-players');
    if (!container) return;
    container.textContent = '';

    players.forEach((p, idx) => {
        const archKey = getArchetype(p);
        const arch = ARCHETYPES[archKey];
        const colors = ARCHETYPE_COLORS[arch.color];
        const tier = getKISTier(p.total_kis);
        const rank = idx + 1;

        const carrierBar = p.kills > 0 ? ((p.carrier_kills / p.kills) * 100).toFixed(0) : 0;
        const pushBar = p.kills > 0 ? ((p.push_kills / p.kills) * 100).toFixed(0) : 0;
        const crossfireBar = p.kills > 0 ? ((p.crossfire_kills / p.kills) * 100).toFixed(0) : 0;

        const card = _el('div', 'rounded-xl border border-white/[0.08] bg-white/[0.03] hover:bg-white/[0.06] transition-all duration-200 p-4 group');

        // Header
        const headerLeft = _el('div', 'flex items-center gap-2.5',
            _el('div', `w-7 h-7 rounded-lg bg-gradient-to-br ${tier.css} flex items-center justify-center text-xs font-black text-black/80`, String(rank)),
            _el('div', null,
                _el('div', 'text-sm font-semibold text-white leading-tight', stripEtColors(p.name)),
                _el('div', 'flex items-center gap-1.5 mt-0.5',
                    _el('span', `inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold ${colors.bg} ${colors.border} ${colors.text} border`, `${arch.icon} ${arch.label}`)
                )
            )
        );
        const headerRight = _el('div', 'text-right',
            _el('div', `text-lg font-black bg-gradient-to-r ${tier.css} bg-clip-text text-transparent`, (p.total_kis ?? 0).toFixed(1)),
            _el('div', `text-[10px] ${tier.textCss} font-bold uppercase tracking-wider`, tier.label)
        );
        card.appendChild(_el('div', 'flex items-start justify-between mb-3', headerLeft, headerRight));

        // Stats grid
        const statCell = (val, label, cls) => _el('div', null,
            _el('div', `text-xs font-bold ${cls}`, String(val)),
            _el('div', 'text-[10px] text-slate-500', label)
        );
        card.appendChild(_el('div', 'grid grid-cols-4 gap-2 text-center mb-3',
            statCell(p.kills, 'Kills', 'text-white'),
            statCell(p.carrier_kills, 'Carrier', 'text-rose-400'),
            statCell(p.push_kills, 'Push', 'text-amber-400'),
            statCell(p.crossfire_kills, 'Crossfire', 'text-cyan-400')
        ));

        // Context bar
        const barContainer = _el('div', 'h-1.5 rounded-full bg-slate-800 overflow-hidden flex');
        const seg = (cls, w) => { const s = _el('div', `${cls} transition-all`); s.style.width = `${w}%`; return s; };
        barContainer.appendChild(seg('bg-rose-500/80', carrierBar));
        barContainer.appendChild(seg('bg-amber-500/80', pushBar));
        barContainer.appendChild(seg('bg-cyan-500/80', crossfireBar));
        card.appendChild(barContainer);

        // DPM + denied time + dead % info row
        const infoRow = _el('div', 'flex justify-between mt-2 text-[10px] text-slate-500');
        if (p.dpm) infoRow.appendChild(_el('span', null, `DPM: ${(p.dpm).toFixed(0)}`));
        if (p.denied_time) infoRow.appendChild(_el('span', null, `Denied: ${Math.round(p.denied_time / 60)}m`));
        if (p.time_dead_pct != null) infoRow.appendChild(_el('span', null, `Dead: ${(p.time_dead_pct * 100).toFixed(0)}%`));
        card.appendChild(infoRow);

        // Oksii multiplier badges
        const oksiiRow = _el('div', 'flex flex-wrap gap-1 mt-2');
        const badge = (label, count, cls) => {
            if (!count) return null;
            return _el('span', `inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[9px] font-bold ${cls}`, `${label} ${count}`);
        };
        const clutchBadge = badge('\u2764\uFE0F Clutch', p.clutch_kills, 'bg-red-500/20 text-red-400 border border-red-500/30');
        const soloBadge = badge('\u{1F451} Solo', p.solo_clutch_kills, 'bg-amber-500/20 text-amber-400 border border-amber-500/30');
        const outnumBadge = badge('\u{1F4AA} Outnum', p.outnumbered_kills, 'bg-purple-500/20 text-purple-400 border border-purple-500/30');
        const denyBadge = badge('\u23F1 Deny', p.spawn_denial_kills, 'bg-teal-500/20 text-teal-400 border border-teal-500/30');
        if (clutchBadge) oksiiRow.appendChild(clutchBadge);
        if (soloBadge) oksiiRow.appendChild(soloBadge);
        if (outnumBadge) oksiiRow.appendChild(outnumBadge);
        if (denyBadge) oksiiRow.appendChild(denyBadge);
        if (oksiiRow.children.length > 0) card.appendChild(oksiiRow);

        // Footer
        card.appendChild(_el('div', 'flex justify-between mt-1 text-[9px] text-slate-600',
            _el('span', null, `Avg impact: ${(p.avg_impact ?? 0).toFixed(2)}`),
            _el('span', null, `Context: ${p.kills > 0 ? (((p.carrier_kills + p.push_kills + p.crossfire_kills) / p.kills) * 100).toFixed(0) : 0}%`)
        ));

        container.appendChild(card);
    });
}

function renderKISBreakdown(players) {
    const container = document.getElementById('story-kis-breakdown');
    if (!container) return;
    container.textContent = '';

    const top = players.slice(0, 12);
    const maxKIS = Math.max(...top.map(p => p.total_kis), 1);

    const SEGMENTS = [
        { key: 'base',        label: 'Base',         color: 'bg-slate-500' },
        { key: 'carrier',     label: 'Carrier',      color: 'bg-rose-500' },
        { key: 'push',        label: 'Push',         color: 'bg-amber-500' },
        { key: 'crossfire',   label: 'Crossfire',    color: 'bg-cyan-500' },
        { key: 'clutch',      label: 'Clutch',       color: 'bg-purple-500' },
        { key: 'spawn',       label: 'Spawn Denial', color: 'bg-emerald-500' },
        { key: 'outnumbered', label: 'Outnumbered',  color: 'bg-orange-500' },
    ];

    // Legend
    const legendRow = _el('div', 'flex flex-wrap gap-3 mb-4');
    SEGMENTS.forEach(s => {
        legendRow.appendChild(_el('span', 'inline-flex items-center gap-1.5 text-[10px] text-slate-400',
            _el('span', `w-2.5 h-2.5 rounded-sm ${s.color}`),
            s.label
        ));
    });
    container.appendChild(legendRow);

    // Bars
    top.forEach(p => {
        const carrierK = p.carrier_kills || 0;
        const pushK = p.push_kills || 0;
        const crossfireK = p.crossfire_kills || 0;
        const clutchK = p.clutch_kills || 0;
        const spawnK = p.spawn_denial_kills || 0;
        const outnumberedK = p.outnumbered_kills || 0;

        // Waterfall KIS distribution — handles overlapping kill categories
        const totalKIS = p.total_kis ?? 0;
        const k = Math.max(p.kills, 1);
        const rawSeg = (count) => totalKIS * (count / k);
        const rawSum = rawSeg(carrierK) + rawSeg(pushK) + rawSeg(crossfireK) + rawSeg(clutchK) + rawSeg(spawnK) + rawSeg(outnumberedK);
        const scale = rawSum > totalKIS ? totalKIS / rawSum : 1;
        const segKIS = (count) => rawSeg(count) * scale;
        const baseKIS = Math.max(0, totalKIS - rawSum * scale);
        const pct = (v) => ((v / maxKIS) * 100).toFixed(1);
        const safeName = stripEtColors(p.name);

        const row = _el('div', 'mb-3');

        // Main bar row
        const barRow = _el('div', 'flex items-center gap-3');

        const nameDiv = _el('div', 'w-24 text-xs text-slate-400 truncate text-right', safeName);
        nameDiv.title = safeName;
        barRow.appendChild(nameDiv);

        const barTrack = _el('div', 'flex-1 h-5 rounded bg-slate-800/50 overflow-hidden flex');
        const addSeg = (cls, val) => { const s = _el('div', `${cls} h-full`); s.style.width = `${pct(val)}%`; barTrack.appendChild(s); };
        addSeg(`${SEGMENTS[0].color}/60`, baseKIS);
        addSeg(`${SEGMENTS[1].color}/80`, segKIS(carrierK));
        addSeg(`${SEGMENTS[2].color}/80`, segKIS(pushK));
        addSeg(`${SEGMENTS[3].color}/80`, segKIS(crossfireK));
        addSeg(`${SEGMENTS[4].color}/80`, segKIS(clutchK));
        addSeg(`${SEGMENTS[5].color}/80`, segKIS(spawnK));
        addSeg(`${SEGMENTS[6].color}/80`, segKIS(outnumberedK));
        barRow.appendChild(barTrack);

        barRow.appendChild(_el('div', 'w-12 text-xs text-slate-400 text-right font-mono', (p.total_kis ?? 0).toFixed(1)));
        row.appendChild(barRow);

        // Mini badge row (archetype + avg impact + context highlights)
        const badgeRow = _el('div', 'flex items-center gap-2 ml-[calc(6rem+0.75rem)] mt-1');

        // Archetype badge
        const arch = getArchetype(p);
        const archDef = ARCHETYPES[arch];
        const archColors = ARCHETYPE_COLORS[archDef.color] || ARCHETYPE_COLORS.slate;
        badgeRow.appendChild(_el('span',
            `inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-bold ${archColors.bg} ${archColors.text} ${archColors.border} border`,
            `${archDef.icon} ${archDef.label}`
        ));

        // Avg impact
        if (p.avg_impact) {
            badgeRow.appendChild(_el('span', 'text-[9px] text-slate-500 font-mono', `avg ${p.avg_impact.toFixed(2)}`));
        }

        // Solo clutch highlight
        if (p.solo_clutch_kills > 0) {
            badgeRow.appendChild(_el('span', 'text-[9px] text-purple-400 font-bold', `${p.solo_clutch_kills} solo clutch`));
        }

        // Outnumbered highlight
        if (outnumberedK > 0) {
            badgeRow.appendChild(_el('span', 'text-[9px] text-orange-400 font-bold', `${outnumberedK} outnumbered`));
        }

        row.appendChild(badgeRow);
        container.appendChild(row);
    });
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
        container.textContent = '';
        container.appendChild(_el('div', 'text-slate-500 text-sm py-4', 'No key moments for this session'));
        return;
    }

    container.textContent = '';
    moments.forEach((m, idx) => {
        const mt = MOMENT_TYPES[m.type] || MOMENT_TYPES.kill_streak;
        const stars = '\u2605'.repeat(Math.min(Math.max(Math.round(m.impact_stars || m.impact || 0), 0), 5));
        const safeName = stripEtColors(m.player || m.player_name || '');
        const safeNarrative = m.narrative || '';
        const safeMap = m.map_name || '';
        const roundLabel = (m.round_number || m.round_num) ? `R${m.round_number || m.round_num}` : '';
        const timeLabel = m.time_formatted || '';
        const delay = idx * 80;

        const cardWidth = (m.kills && m.kills.length > 0) ? 'w-72' : 'w-56';
        const card = _el('div', `flex-shrink-0 ${cardWidth} rounded-xl border ${mt.border} ${mt.bg} p-4 opacity-0 translate-y-3`);
        card.style.animation = `momentFadeUp 0.4s ease-out ${delay}ms forwards`;

        // Top row: icon + stars + time
        const topRow = _el('div', 'flex items-center justify-between mb-2');
        topRow.appendChild(_el('span', 'text-lg', mt.icon));
        const rightGroup = _el('div', 'flex items-center gap-2');
        if (timeLabel) rightGroup.appendChild(_el('span', 'text-[10px] text-slate-500 font-mono', timeLabel));
        rightGroup.appendChild(_el('span', 'text-amber-400 text-xs tracking-wider', stars));
        topRow.appendChild(rightGroup);
        card.appendChild(topRow);

        // Name
        const nameEl = _el('div', 'text-xs font-bold text-white mb-1 truncate', safeName);
        nameEl.title = safeName;
        card.appendChild(nameEl);

        // Narrative
        card.appendChild(_el('div', 'text-[11px] text-slate-300 mb-2 line-clamp-2 leading-relaxed', safeNarrative));

        // Round + map labels
        const meta = _el('div', 'flex items-center gap-2 text-[10px] text-slate-500');
        if (roundLabel) meta.appendChild(_el('span', null, roundLabel));
        if (safeMap) meta.appendChild(_el('span', 'truncate', safeMap));
        card.appendChild(meta);

        // Kill breakdown
        if (Array.isArray(m.kills) && m.kills.length > 0) {
            const breakdown = _el('div', 'mt-2 pt-2 border-t border-white/5 space-y-0.5 text-[10px]');
            m.kills.forEach(k => {
                const killRow = _el('div', 'flex items-center gap-1',
                    _el('span', 'text-white', stripEtColors(k.killer || '')),
                    _el('span', 'text-slate-600', '\u2192'),
                    _el('span', 'text-red-400', stripEtColors(k.victim || ''))
                );
                if (k.weapon) {
                    killRow.appendChild(_el('span', 'text-slate-600 ml-auto', k.weapon));
                }
                if (k.time_formatted) {
                    killRow.appendChild(_el('span', 'text-slate-700 w-8 text-right', k.time_formatted));
                }
                breakdown.appendChild(killRow);
            });
            if (m.duration_ms != null) {
                breakdown.appendChild(_el('div', 'text-slate-600 mt-1', `Duration: ${(m.duration_ms / 1000).toFixed(1)}s`));
            }
            card.appendChild(breakdown);
        }

        container.appendChild(card);
    });
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
        container.textContent = '';
        container.appendChild(_el('div', 'text-center text-slate-500 py-8 text-sm', 'No synergy data available'));
        return;
    }

    function buildPanel(gkey) {
        const style = GROUP_STYLES[gkey];
        const gd = groups[gkey];
        if (!gd) return null;
        const composite = gd.composite ?? 0;
        const playerList = Array.isArray(gd.players) ? gd.players : [];
        const nameList = playerList.map(n => stripEtColors(n)).join(', ');

        const panel = _el('div', `flex-1 rounded-xl border ${style.border} ${style.bg} p-5`);

        const panelHeader = _el('div', 'flex items-center justify-between mb-4');
        panelHeader.appendChild(_el('div', null,
            _el('div', 'text-sm font-bold text-white', nameList || gkey)
        ));
        panelHeader.appendChild(_el('div', `text-2xl font-black ${style.text}`, composite.toFixed(1)));
        panel.appendChild(panelHeader);

        SYNERGY_AXES.forEach(axis => {
            const val = gd[axis.key] ?? 0;
            const row = _el('div', 'flex items-center gap-2 mb-2');
            row.appendChild(_el('div', 'w-24 text-[11px] text-slate-400 truncate', axis.label));
            const track = _el('div', 'flex-1 h-2.5 rounded-full bg-slate-800 overflow-hidden');
            const fill = _el('div', `${style.bar}/70 h-full rounded-full transition-all duration-500`);
            fill.style.width = `${val.toFixed(1)}%`;
            track.appendChild(fill);
            row.appendChild(track);
            row.appendChild(_el('div', 'w-8 text-[11px] text-slate-400 text-right font-mono', val.toFixed(0)));
            panel.appendChild(row);
        });

        return panel;
    }

    container.textContent = '';
    const grid = _el('div', 'grid grid-cols-1 md:grid-cols-2 gap-4');
    const panelA = buildPanel('group_a');
    const panelB = buildPanel('group_b');
    if (panelA) grid.appendChild(panelA);
    if (panelB) grid.appendChild(panelB);
    container.appendChild(grid);
}

// ── Helpers for new panels ──────────────────────────────────────

function formatMs(ms) {
    const s = Math.round((ms || 0) / 1000);
    const m = Math.floor(s / 60);
    return m > 0 ? `${m}m ${s % 60}s` : `${s}s`;
}

function _statCell(label, value) {
    return _el('div', 'rounded-lg bg-white/[0.03] px-2 py-1.5',
        _el('div', 'text-[10px] text-slate-500 uppercase tracking-wider', label),
        _el('div', 'text-sm font-bold tabular-nums text-white', String(value))
    );
}

// ── BOX Score ───────────────────────────────────────────────────

function renderBoxScore(data) {
    const container = document.getElementById('story-box-score');
    if (!container) return;
    container.textContent = '';

    const maps = Array.isArray(data?.maps) ? data.maps : [];
    if (maps.length === 0) return;

    function fmtTime(sec) {
        if (!sec || sec <= 0) return '';
        const m = Math.floor(sec / 60);
        const s = Math.round(sec % 60);
        return `${m}:${s < 10 ? '0' : ''}${s}`;
    }

    const alpha = data.alpha_team || 'Alpha';
    const beta = data.beta_team || 'Beta';
    const aScore = data.alpha_score || 0;
    const bScore = data.beta_score || 0;

    // Header
    const header = _el('div', 'flex items-center gap-3 mb-3');
    header.appendChild(_el('h3', 'text-xs text-slate-500 uppercase tracking-wider font-bold', 'Box Score'));
    if (data.winner_name) {
        const winColor = data.winner === 'alpha' ? 'text-cyan-400' : 'text-rose-400';
        header.appendChild(_el('span', `text-xs font-bold ${winColor}`, `${data.winner_name} wins`));
    } else if (aScore === bScore) {
        header.appendChild(_el('span', 'text-xs font-bold text-amber-400', 'Draw'));
    }
    container.appendChild(header);

    // Score card
    const card = _el('div', 'rounded-xl border border-white/[0.08] bg-white/[0.03] p-5');

    // Score header
    const scoreRow = _el('div', 'flex items-center justify-center gap-6 mb-4');
    scoreRow.appendChild(_el('div', 'text-right',
        _el('div', 'text-xs text-slate-400 uppercase', stripEtColors(alpha)),
        _el('div', 'text-2xl font-black text-cyan-400 tabular-nums', String(aScore))
    ));
    scoreRow.appendChild(_el('div', 'text-slate-600 text-sm', 'vs'));
    scoreRow.appendChild(_el('div', 'text-left',
        _el('div', 'text-xs text-slate-400 uppercase', stripEtColors(beta)),
        _el('div', 'text-2xl font-black text-rose-400 tabular-nums', String(bScore))
    ));
    card.appendChild(scoreRow);

    // Map rows
    const mapList = _el('div', 'space-y-1.5');
    maps.forEach((m, i) => {
        const row = _el('div', 'flex items-center gap-3 rounded-lg bg-white/[0.02] px-3 py-2 hover:bg-white/[0.04] transition-colors');
        row.appendChild(_el('span', 'text-[10px] text-slate-600 w-5', `#${m.map_number || i + 1}`));
        row.appendChild(_el('span', 'text-xs text-slate-300 flex-1 truncate', m.map_name || ''));
        row.appendChild(_el('span', 'text-xs font-bold text-cyan-400 tabular-nums w-4 text-right', String(m.alpha_points || 0)));
        row.appendChild(_el('span', 'text-slate-600 text-[10px]', '-'));
        row.appendChild(_el('span', 'text-xs font-bold text-rose-400 tabular-nums w-4', String(m.beta_points || 0)));

        // Round times
        const r1 = fmtTime(m.r1_time);
        const r2 = fmtTime(m.r2_time);
        if (r1) {
            const times = _el('span', 'text-[10px] text-slate-500 tabular-nums', `R1:${r1}`);
            if (r2) times.textContent += ` R2:${r2}`;
            row.appendChild(times);
        }

        // Fullhold badge
        if (m.is_fullhold_draw) {
            row.appendChild(_el('span', 'text-[9px] font-bold text-amber-400 bg-amber-400/10 rounded px-1', 'FH'));
        }

        mapList.appendChild(row);
    });
    card.appendChild(mapList);
    container.appendChild(card);
}

// ── Invisible Value (Gravity / Space / Enabler / Lurker) ────────

const IV_TABS = [
    { key: 'gravity', label: 'GRAVITY', color: 'rose',   scoreField: 'gravity_score', scoreFmt: v => v.toFixed(0),
      cells: p => [['ENG', p.engagements], ['AVG ATK', (p.avg_attackers || 0).toFixed(1)], ['ATTN', formatMs(p.total_attention_ms)]] },
    { key: 'space',   label: 'SPACE',   color: 'purple', scoreField: 'space_score',   scoreFmt: v => (v * 100).toFixed(0) + '%',
      cells: p => [['PROD', p.productive_deaths], ['WASTE', p.wasted_deaths], ['TM KILLS', p.teammate_kills_after]] },
    { key: 'enabler', label: 'ENABLER', color: 'teal',   scoreField: 'enabler_score', scoreFmt: v => v.toFixed(1),
      cells: p => [['ENABLED', p.enabled_kills], ['CF', p.crossfire_assists], ['TRADE', p.trade_assists]] },
    { key: 'lurker',  label: 'LURKER',  color: 'cyan',   scoreField: 'solo_pct',      scoreFmt: v => v.toFixed(0) + '%',
      cells: p => [['SOLO', formatMs((p.solo_time_est_s || 0) * 1000)], ['LIVES', p.tracks], ['ALIVE', formatMs(p.alive_ms)]] },
];

function renderInvisibleValue(gravity, space, enabler, lurker) {
    const container = document.getElementById('story-invisible-value');
    if (!container) return;
    container.textContent = '';

    const dataMap = { gravity, space, enabler, lurker };
    const hasData = tab => {
        const d = dataMap[tab.key];
        return Array.isArray(d?.players) && d.players.length > 0;
    };

    if (!IV_TABS.some(hasData)) return;

    // Find first tab with data
    let activeKey = IV_TABS.find(hasData)?.key || 'gravity';

    // Header
    const headerRow = _el('div', 'flex items-center gap-3 mb-3');
    headerRow.appendChild(_el('h3', 'text-xs text-slate-500 uppercase tracking-wider font-bold', 'Invisible Value'));
    const activeBadge = _el('span', 'text-[10px] font-bold uppercase px-2 py-0.5 rounded-full');
    headerRow.appendChild(activeBadge);
    container.appendChild(headerRow);

    // Tab bar
    const tabBar = _el('div', 'flex gap-1.5 mb-4');
    const tabButtons = {};
    IV_TABS.forEach(tab => {
        const has = hasData(tab);
        const btn = _el('button',
            `px-3 py-1.5 rounded-lg text-xs font-bold uppercase border transition-colors ${has ? '' : 'opacity-30 cursor-default'}`,
            tab.label
        );
        if (!has) btn.disabled = true;
        tabButtons[tab.key] = btn;
        tabBar.appendChild(btn);
    });
    container.appendChild(tabBar);

    // Content area
    const card = _el('div', 'rounded-xl border border-white/[0.08] bg-white/[0.03] p-5');
    const content = _el('div');
    card.appendChild(content);
    container.appendChild(card);

    function renderTab(key) {
        activeKey = key;
        const tab = IV_TABS.find(t => t.key === key);
        if (!tab) return;
        const c = tab.color;

        // Update badge
        activeBadge.className = `text-[10px] font-bold uppercase px-2 py-0.5 rounded-full border border-${c}-400/30 bg-${c}-400/10 text-${c}-400`;
        activeBadge.textContent = tab.label;

        // Update tab buttons
        IV_TABS.forEach(t => {
            const btn = tabButtons[t.key];
            if (t.key === key) {
                btn.className = `px-3 py-1.5 rounded-lg text-xs font-bold uppercase border border-${c}-400/40 bg-${c}-500/20 text-${c}-400 transition-colors`;
            } else {
                const has = hasData(t);
                btn.className = `px-3 py-1.5 rounded-lg text-xs font-bold uppercase border border-transparent text-slate-500 bg-white/[0.02] hover:bg-white/[0.04] transition-colors ${has ? '' : 'opacity-30 cursor-default'}`;
            }
        });

        // Build player list
        content.textContent = '';
        const players = dataMap[key]?.players || [];
        const list = _el('div', 'space-y-1.5');

        players.forEach((p, i) => {
            const safeName = stripEtColors(p.name || p.guid_short || '');
            const score = p[tab.scoreField] || 0;

            const row = _el('div', 'flex items-center gap-3 rounded-xl bg-white/[0.02] px-3 py-2.5 hover:bg-white/[0.04] transition-colors');
            row.style.animation = `fadeUp 0.3s ease-out ${i * 0.04}s both`;

            // Score
            row.appendChild(_el('span', `text-lg font-black text-${c}-400 tabular-nums w-14 text-right`, tab.scoreFmt(score)));

            // Name
            row.appendChild(_el('span', 'text-sm text-white font-medium flex-1 truncate', safeName));

            // Stat cells
            const cellsWrap = _el('div', 'flex gap-2');
            tab.cells(p).forEach(([label, val]) => {
                cellsWrap.appendChild(_statCell(label, val ?? 0));
            });
            row.appendChild(cellsWrap);

            list.appendChild(row);
        });

        content.appendChild(list);
    }

    // Tab click handler
    tabBar.addEventListener('click', e => {
        const btn = e.target.closest('button');
        if (!btn || btn.disabled) return;
        const tab = IV_TABS.find(t => t.label === btn.textContent);
        if (tab) renderTab(tab.key);
    });

    // Initial render
    renderTab(activeKey);
}

// ── Player Win Contribution (PWC) ────────────────────────────────

const PWC_COMPONENTS = [
    { key: 'kills',      label: 'Kills',      color: 'bg-rose-500' },
    { key: 'damage',     label: 'Damage',     color: 'bg-amber-500' },
    { key: 'objectives', label: 'Objectives', color: 'bg-blue-500' },
    { key: 'revives',    label: 'Revives',    color: 'bg-emerald-500' },
    { key: 'survival',   label: 'Survival',   color: 'bg-cyan-500' },
    { key: 'crossfire',  label: 'Crossfire',  color: 'bg-purple-500' },
    { key: 'trade',      label: 'Trades',     color: 'bg-orange-500' },
    { key: 'clutch',     label: 'Clutch',     color: 'bg-pink-500' },
];

function renderWinContribution(data) {
    const container = document.getElementById('story-win-contribution');
    if (!container) return;

    const players = Array.isArray(data?.players) ? data.players : [];
    const mvp = data?.mvp;

    if (players.length === 0) {
        container.textContent = '';
        container.appendChild(_el('div', 'text-center text-slate-500 py-8 text-sm', 'No win contribution data available'));
        return;
    }

    container.textContent = '';

    // MVP highlight card
    if (mvp) {
        const mvpName = stripEtColors(mvp.name);
        const wisSign = mvp.wis >= 0 ? '+' : '';

        const mvpCard = _el('div', 'rounded-xl border border-amber-500/30 bg-gradient-to-br from-amber-500/10 via-amber-900/10 to-slate-900 p-5 mb-5');
        const mvpRow = _el('div', 'flex items-center justify-between');

        const mvpLeft = _el('div', 'flex items-center gap-3',
            _el('div', 'w-10 h-10 rounded-xl bg-gradient-to-br from-amber-400 to-yellow-500 flex items-center justify-center text-lg font-black text-black/80', '\u2605'),
            _el('div', null,
                _el('div', 'text-xs text-amber-400 font-bold tracking-[0.2em] uppercase', 'Session MVP'),
                _el('div', 'text-lg font-black text-white', mvpName),
                _el('div', 'text-[9px] text-slate-500 mt-0.5', 'Highest avg contribution in winning rounds')
            )
        );

        const mvpRight = _el('div', 'text-right',
            _el('div', 'text-2xl font-black text-amber-400', mvp.total_pwc.toFixed(2)),
            _el('div', 'text-[10px] text-slate-400', `PWC \u00B7 WIS ${wisSign}${mvp.wis.toFixed(3)}`)
        );

        mvpRow.appendChild(mvpLeft);
        mvpRow.appendChild(mvpRight);
        mvpCard.appendChild(mvpRow);
        container.appendChild(mvpCard);
    }

    // Legend
    const legendRow = _el('div', 'flex gap-4 mb-4');
    PWC_COMPONENTS.forEach(c => {
        legendRow.appendChild(_el('span', 'inline-flex items-center gap-1.5 text-[10px] text-slate-400',
            _el('span', `w-2.5 h-2.5 rounded-sm ${c.color}`),
            c.label
        ));
    });
    container.appendChild(legendRow);

    // Column headers
    const header = _el('div', 'flex items-center gap-3 mb-2 text-[10px] text-slate-600 uppercase tracking-wider');
    header.appendChild(_el('div', 'w-5 text-right', '#'));
    header.appendChild(_el('div', 'w-24 text-right', 'Player'));
    header.appendChild(_el('div', 'flex-1', 'Contribution'));
    header.appendChild(_el('div', 'w-12 text-right', 'PWC'));
    header.appendChild(_el('div', 'w-16 text-right', 'WIS'));
    header.appendChild(_el('div', 'w-10 text-right', 'W/L'));
    container.appendChild(header);

    // Per-player stacked bars (top 15)
    const top = players.slice(0, 15);
    const maxPWC = Math.max(...top.map(p => p.total_pwc), 0.01);

    // Sum raw stats per player (for tooltips)
    function _sumRaw(perRound, key) {
        return (perRound || []).reduce((s, r) => s + (r[key] || 0), 0);
    }

    top.forEach((p, idx) => {
        const safeName = stripEtColors(p.name);
        const comp = p.components || {};
        const compTotal = Object.values(comp).reduce((s, v) => s + v, 0) || 1;
        const wisSign = p.wis >= 0 ? '+' : '';
        const rank = idx + 1;
        const totalRounds = p.total_rounds || (p.rounds_won + p.rounds_lost);

        // Raw stat totals for tooltips
        const rawTotals = {
            kills: _sumRaw(p.per_round, 'kills'),
            damage: _sumRaw(p.per_round, 'damage'),
            objectives: _sumRaw(p.per_round, 'objectives'),
            revives: _sumRaw(p.per_round, 'revives'),
        };

        const row = _el('div', 'flex items-center gap-3 mb-2 group');
        row.appendChild(_el('div', 'w-5 text-[10px] text-slate-600 text-right font-mono', String(rank)));

        const nameDiv = _el('div', 'w-24 text-xs text-slate-400 truncate text-right', safeName);
        nameDiv.title = safeName;
        row.appendChild(nameDiv);

        // Stacked bar segments with tooltips
        const barContainer = _el('div', 'flex-1 h-5 rounded bg-slate-800/50 overflow-hidden flex');
        PWC_COMPONENTS.forEach(c => {
            const val = comp[c.key] || 0;
            const pct = ((val / maxPWC) * 100).toFixed(1);
            const compPct = ((val / compTotal) * 100).toFixed(0);
            const s = _el('div', `${c.color}/70 h-full`);
            s.style.width = `${pct}%`;
            // Tooltip with raw value + percentage of player's PWC
            let tip = `${c.label}: ${val.toFixed(3)} (${compPct}% of PWC)`;
            if (rawTotals[c.key] !== undefined) {
                tip += ` \u2014 ${rawTotals[c.key]} raw`;
            }
            s.title = tip;
            barContainer.appendChild(s);
        });
        row.appendChild(barContainer);

        row.appendChild(_el('div', 'w-12 text-xs text-slate-400 text-right font-mono', p.total_pwc.toFixed(2)));

        // WIS with round count for context
        const wisText = `${wisSign}${p.wis.toFixed(3)}`;
        const wisEl = _el('div', `w-16 text-[10px] text-right font-mono ${p.wis >= 0 ? 'text-emerald-400' : 'text-red-400'}`, wisText);
        wisEl.title = `Win Impact Score: avg PWC in wins \u2212 avg PWC in losses (${totalRounds} rounds: W${p.rounds_won} L${p.rounds_lost})`;
        row.appendChild(wisEl);

        // W/L badge
        const wlBadge = _el('div', 'w-10 text-[9px] text-slate-500 text-right font-mono', `${p.rounds_won}W${p.rounds_lost}L`);
        row.appendChild(wlBadge);

        // Per-round mini dots
        const dotsContainer = _el('div', 'hidden group-hover:flex items-center gap-0.5 w-20');
        (p.per_round || []).forEach(r => {
            const dot = _el('span', `inline-block w-1.5 h-1.5 rounded-full ${r.won ? 'bg-emerald-400' : 'bg-red-400'}`);
            dot.title = `R${r.round_number} ${r.map_name} \u2014 PWC ${r.pwc}${r.won ? ' W' : ' L'} | K:${r.kills} D:${r.damage} O:${r.objectives} R:${r.revives}`;
            dotsContainer.appendChild(dot);
        });
        row.appendChild(dotsContainer);

        container.appendChild(row);
    });
}

// ── Advanced Metrics Panel (TIR, CI, KPI, SDS, CP) ────────────────────────

const COMPOSITE_METRICS = [
    { key: 'tir', label: 'Team Impact',      icon: '\u{1F91D}', color: 'cyan',    desc: 'Crossfire + trade coordination' },
    { key: 'ci',  label: 'Clutch Index',      icon: '\u{1F4AA}', color: 'rose',    desc: 'Low HP & outnumbered kills' },
    { key: 'kpi', label: 'Kill Permanence',   icon: '\u{1F480}', color: 'purple',  desc: 'Gib rate (permanent kills)' },
    { key: 'sds', label: 'Spawn Denial',      icon: '\u{23F1}\uFE0F', color: 'amber',   desc: 'Timing + denied playtime' },
    { key: 'cp',  label: 'Combat Presence',   icon: '\u{1F6E1}\uFE0F', color: 'emerald', desc: 'Survival + focus escape' },
];

function renderAdvancedMetrics(data) {
    const container = document.getElementById('story-advanced-metrics');
    if (!container) return;
    container.textContent = '';

    if (!data?.players?.length) {
        container.appendChild(_el('div', 'text-center text-slate-500 py-8 text-sm', 'No advanced metrics data'));
        return;
    }

    // Section header
    const header = _el('div', 'flex items-center gap-3 mb-4');
    header.appendChild(_el('div', 'w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center text-white text-sm font-bold', 'v2'));
    const headerText = _el('div', '');
    headerText.appendChild(_el('h3', 'text-lg font-bold text-white', 'Advanced Metrics'));
    headerText.appendChild(_el('p', 'text-xs text-slate-400', 'ET Rating v2 — proximity-derived composite scores'));
    header.appendChild(headerText);
    container.appendChild(header);

    // Player rows
    data.players.forEach(player => {
        const card = _el('div', 'glass-card rounded-xl p-4 mb-3');

        // Player name row
        const nameRow = _el('div', 'flex items-center justify-between mb-3');
        nameRow.appendChild(_el('span', 'text-sm font-bold text-white', stripEtColors(player.player_name)));
        nameRow.appendChild(_el('span', 'text-xs text-slate-400 font-mono', `${player.kills} kills`));
        card.appendChild(nameRow);

        // Metrics grid
        const grid = _el('div', 'grid grid-cols-5 gap-2');

        COMPOSITE_METRICS.forEach(m => {
            const value = player[m.key] ?? 0;
            const colorSet = ARCHETYPE_COLORS[m.color] || ARCHETYPE_COLORS.slate;

            const cell = _el('div', 'text-center');

            // Icon + label
            cell.appendChild(_el('div', 'text-lg mb-1', m.icon));
            cell.appendChild(_el('div', `text-[10px] font-bold uppercase tracking-wider ${colorSet.text} mb-1`, m.label));

            // Progress bar
            const barBg = _el('div', 'w-full h-1.5 rounded-full bg-slate-700 mb-1 overflow-hidden');
            const barFill = _el('div', `h-full rounded-full transition-all duration-500`);
            barFill.style.width = `${Math.min(100, value)}%`;
            barFill.style.background = `linear-gradient(90deg, var(--tw-gradient-from, #06b6d4), var(--tw-gradient-to, #3b82f6))`;
            // Color the bar based on metric color
            const barColors = {
                cyan: '#06b6d4', rose: '#f43f5e', purple: '#8b5cf6',
                amber: '#f59e0b', emerald: '#10b981',
            };
            barFill.style.background = barColors[m.color] || '#3b82f6';
            barBg.appendChild(barFill);
            cell.appendChild(barBg);

            // Value
            cell.appendChild(_el('div', `text-sm font-bold font-mono ${colorSet.text}`, value.toFixed(1)));

            // Tooltip
            cell.title = `${m.label}: ${m.desc} (${value.toFixed(1)}/100)`;

            grid.appendChild(cell);
        });

        card.appendChild(grid);
        container.appendChild(card);
    });
}

export async function loadStoryView() {
    await loadStoryScopes();
    await loadStoryData();
}
