/**
 * Smart Stats / Storytelling module (legacy)
 * Kill Impact Score (KIS) visualization
 * @module story
 */

import { API_BASE, fetchJSON, formatNumber, escapeHtml } from './utils.js';

const DEFAULT_SCOPE_RANGE_DAYS = 365;

const storyState = {
    sessions: [],
    sessionDate: null,
    players: [],
    loading: false,
};

const ARCHETYPES = {
    carrier_hunter:  { icon: '\u{1F3AF}', label: 'Carrier Hunter',  color: 'rose' },
    crossfire_king:  { icon: '\u{26A1}',  label: 'Crossfire King',  color: 'cyan' },
    push_leader:     { icon: '\u{1F6E1}\uFE0F',  label: 'Push Leader',    color: 'amber' },
    impact_elite:    { icon: '\u{1F451}', label: 'Impact Elite',    color: 'yellow' },
    volume_machine:  { icon: '\u{1F525}', label: 'Volume Machine',  color: 'orange' },
    tactician:       { icon: '\u{1F9E0}', label: 'Tactician',       color: 'purple' },
    all_rounder:     { icon: '\u{2B50}',  label: 'All-Rounder',     color: 'emerald' },
    support_fighter: { icon: '\u{1F91D}', label: 'Support Fighter', color: 'blue' },
    quiet_blade:     { icon: '\u{1F5E1}\uFE0F',  label: 'Quiet Blade',    color: 'slate' },
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
};

function classifyArchetype(player) {
    const { kills, carrier_kills, push_kills, crossfire_kills, avg_impact, total_kis } = player;
    if (!kills || kills === 0) return 'quiet_blade';

    const carrierPct = carrier_kills / kills;
    const pushPct = push_kills / kills;
    const crossfirePct = crossfire_kills / kills;
    const contextPct = (carrier_kills + push_kills + crossfire_kills) / kills;

    if (carrierPct >= 0.15 && carrier_kills >= 3) return 'carrier_hunter';
    if (crossfirePct >= 0.20 && crossfire_kills >= 4) return 'crossfire_king';
    if (pushPct >= 0.25 && push_kills >= 5) return 'push_leader';
    if (avg_impact >= 1.8 && kills >= 10) return 'impact_elite';
    if (kills >= 40 && total_kis >= 30) return 'volume_machine';
    if (contextPct >= 0.30 && kills >= 10) return 'tactician';
    if (contextPct >= 0.15 && avg_impact >= 1.2 && kills >= 8) return 'all_rounder';
    if (kills >= 5 && kills < 20) return 'support_fighter';
    return 'quiet_blade';
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

    storyState.loading = true;
    renderLoading();

    try {
        const data = await fetchJSON(
            `${API_BASE}/storytelling/kill-impact?session_date=${encodeURIComponent(storyState.sessionDate)}&limit=50`
        );
        storyState.players = Array.isArray(data?.players) ? data.players : [];

        if (storyState.players.length === 0) {
            renderEmpty('No kill impact data for this session');
            return;
        }

        renderStoryHero(storyState.sessionDate, storyState.players);
        renderPlayerCards(storyState.players);
        renderKISBreakdown(storyState.players);
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
    const players = document.getElementById('story-players');
    if (players) players.innerHTML = '<div class="col-span-full text-center text-slate-500 py-12">Loading kill impact data...</div>';
    const breakdown = document.getElementById('story-kis-breakdown');
    if (breakdown) breakdown.innerHTML = '';
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
    const breakdown = document.getElementById('story-kis-breakdown');
    if (breakdown) breakdown.innerHTML = '';
}

function renderStoryHero(sessionDate, players) {
    const title = document.getElementById('story-title');
    const subtitle = document.getElementById('story-subtitle');
    const statsRow = document.getElementById('story-stats-row');

    const totalKIS = players.reduce((s, p) => s + (p.total_kis || 0), 0);
    const totalKills = players.reduce((s, p) => s + (p.kills || 0), 0);
    const topPlayer = players[0];

    if (title) title.textContent = `Session ${escapeHtml(sessionDate)}`;
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
                <span class="text-lg font-bold text-amber-400">${topPlayer ? escapeHtml(topPlayer.name) : '-'}</span>
            </div>
        `;
    }
}

function renderPlayerCards(players) {
    const container = document.getElementById('story-players');
    if (!container) return;

    container.innerHTML = players.map((p, idx) => {
        const archKey = classifyArchetype(p);
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
                        <div class="text-sm font-semibold text-white leading-tight">${escapeHtml(p.name)}</div>
                        <div class="flex items-center gap-1.5 mt-0.5">
                            <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold ${colors.bg} ${colors.border} ${colors.text} border">
                                ${arch.icon} ${escapeHtml(arch.label)}
                            </span>
                        </div>
                    </div>
                </div>
                <div class="text-right">
                    <div class="text-lg font-black bg-gradient-to-r ${tier.css} bg-clip-text text-transparent">${p.total_kis.toFixed(1)}</div>
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
                <span>Avg impact: ${p.avg_impact.toFixed(2)}</span>
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
        const carrierKIS = p.carrier_kills * (p.avg_impact || 1);
        const pushKIS = p.push_kills * (p.avg_impact || 1) * 0.8;
        const crossfireKIS = p.crossfire_kills * (p.avg_impact || 1) * 0.7;
        const baseKIS = Math.max(0, p.total_kis - carrierKIS - pushKIS - crossfireKIS);

        const pct = (v) => ((v / maxKIS) * 100).toFixed(1);

        return `
        <div class="flex items-center gap-3 mb-1.5">
            <div class="w-24 text-xs text-slate-400 truncate text-right" title="${escapeHtml(p.name)}">${escapeHtml(p.name)}</div>
            <div class="flex-1 h-5 rounded bg-slate-800/50 overflow-hidden flex">
                <div class="${SEGMENTS[0].color}/60 h-full" style="width:${pct(baseKIS)}%"></div>
                <div class="${SEGMENTS[1].color}/80 h-full" style="width:${pct(carrierKIS)}%"></div>
                <div class="${SEGMENTS[2].color}/80 h-full" style="width:${pct(pushKIS)}%"></div>
                <div class="${SEGMENTS[3].color}/80 h-full" style="width:${pct(crossfireKIS)}%"></div>
            </div>
            <div class="w-12 text-xs text-slate-400 text-right font-mono">${p.total_kis.toFixed(1)}</div>
        </div>`;
    }).join('');

    container.innerHTML = `
        <div class="flex gap-4 mb-4">${legend}</div>
        ${bars}
    `;
}

export async function loadStoryView() {
    await loadStoryScopes();
    await loadStoryData();
}
