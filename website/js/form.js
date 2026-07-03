/**
 * Form page (#/form) — "who's playing above their own recent level right now".
 * Expands the home "Movers · vs own form" card: full up/down/new lists, a metric
 * switcher, and a per-player trend sparkline. Rank-vs-self (VISION anti-goal):
 * this is NOT a global ladder — every delta is against the player's OWN recent
 * baseline, so a mid-table player on a hot night tops the list.
 * @module form
 */

import { API_BASE, escapeHtml, fetchJSON, safeInsertHTML, sparklineSVG } from './utils.js';

const METRICS = [
    { key: 'overall', label: 'Overall' },
    { key: 'dpm', label: 'Damage / min' },
    { key: 'kd', label: 'Kills / death' },
    { key: 'obj', label: 'Objectives / round' },
    { key: 'acc', label: 'Accuracy' },
    { key: 'kills', label: 'Kills / session' },
    { key: 'impact', label: 'Impact' },
];

// Short labels for the composite breakdown chips (Overall mode).
const _METRIC_SHORT = { dpm: 'DPM', kd: 'K/D', obj: 'OBJ', acc: 'ACC', kills: 'K', impact: 'IMP' };

let _metric = 'overall';

function _tabsHtml() {
    return METRICS.map((m) => {
        const active = m.key === _metric;
        const cls = active
            ? 'bg-brand-purple/25 text-white border-brand-purple'
            : 'bg-slate-800/40 text-slate-400 border-white/10 hover:text-white';
        return `<button type="button" data-metric="${m.key}"
            class="px-3 py-1.5 rounded-lg text-xs font-bold border ${cls} transition">${escapeHtml(m.label)}</button>`;
    }).join('');
}

// Per-metric contribution chips shown under an Overall row: "DPM +18 · K/D +9 …".
// Values are numbers/known labels only (no user text), so no escaping needed here.
function _breakdownChips(breakdown) {
    if (!breakdown || !breakdown.length) return '';
    const chips = breakdown
        .filter((b) => b.delta_pct != null)
        .map((b) => {
            const flat = b.delta_pct === 0;
            const bUp = b.delta_pct > 0;
            const cls = flat ? 'text-slate-500' : bUp ? 'text-emerald-400/90' : 'text-rose-400/90';
            const short = _METRIC_SHORT[b.metric] || b.metric;
            const txt = flat ? '±0' : `${bUp ? '+' : '-'}${Math.abs(b.delta_pct)}`;
            return `<span class="${cls}">${short} ${txt}%</span>`;
        })
        .join('<span class="text-slate-600"> · </span>');
    return chips ? `<div class="text-[11px] font-mono mt-1">${chips}</div>` : '';
}

function _moverRow(m) {
    const overall = _metric === 'overall';
    const isNew = !!m.is_new;
    const flat = !isNew && m.delta_pct === 0;
    const up = m.delta_pct != null && m.delta_pct > 0;
    const deltaCls = isNew ? 'text-amber-400' : flat ? 'text-slate-400'
        : up ? 'text-emerald-400' : 'text-rose-400';
    const deltaTxt = isNew
        ? 'FIRST NIGHT'
        : flat ? '±0%'
            : `${up ? '▲ +' : '▼ '}${Math.abs(m.delta_pct)}%`;
    let baseline;
    if (overall) {
        baseline = (m.latest != null) ? `${m.latest}% <span class="text-slate-600">vs</span> 100%` : '';
    } else {
        baseline = (m.latest != null && m.baseline != null)
            ? `${m.latest} <span class="text-slate-600">vs</span> ${m.baseline}`
            : (m.latest != null ? `${m.latest}` : '');
    }
    const spark = sparklineSVG(m.series, { up: (isNew || flat) ? null : up });
    const chips = overall ? _breakdownChips(m.breakdown) : '';
    return `
        <div class="py-2 border-b border-white/5">
            <div class="flex items-center justify-between gap-3">
                <a class="text-slate-200 hover:text-brand-cyan transition font-medium truncate max-w-[10rem]"
                   href="#/profile/${encodeURIComponent(m.guid)}">${escapeHtml(m.name)}</a>
                <div class="flex items-center gap-3">
                    <span class="text-slate-500 text-xs font-mono hidden sm:inline">${baseline}</span>
                    ${spark}
                    <span class="font-mono text-sm ${deltaCls} w-24 text-right">${escapeHtml(deltaTxt)}</span>
                </div>
            </div>
            ${chips}
        </div>`;
}

function _section(title, accent, movers) {
    if (!movers || !movers.length) return '';
    return `
        <div class="glass-panel p-5 rounded-xl border-l-4 border-brand-${accent}/60 mb-4">
            <div class="text-[10px] uppercase tracking-widest text-slate-500 font-bold mb-2">${escapeHtml(title)}</div>
            ${movers.map(_moverRow).join('')}
        </div>`;
}

async function _render() {
    const list = document.getElementById('form-list');
    if (!list) return;
    list.textContent = 'Loading form…';
    let data;
    try {
        data = await fetchJSON(`${API_BASE}/skill/movers?full=true&metric=${encodeURIComponent(_metric)}`);
    } catch {
        list.textContent = 'Could not load form data.';
        return;
    }
    const up = data?.movers_up || [];
    const down = data?.movers_down || [];
    const fresh = data?.new_players || [];
    if (!up.length && !down.length && !fresh.length) {
        list.textContent = 'Form data appears after the next session.';
        return;
    }
    const dateTxt = data.session_date ? ` · last session ${escapeHtml(String(data.session_date))}` : '';
    list.textContent = '';
    safeInsertHTML(list, 'beforeend',
        `<div class="text-xs text-slate-500 mb-3">Metric: <span class="text-slate-300 font-semibold">${escapeHtml(data.metric_label || _metric)}</span>${dateTxt}</div>`
        + _section('Heating up · above own average', 'purple', up)
        + _section('Cooling off · below own average', 'amber', down)
        + _section('First night', 'cyan', fresh));
}

export async function loadFormView() {
    const host = document.getElementById('view-form');
    if (!host) return;
    host.textContent = '';
    safeInsertHTML(host, 'beforeend', `
        <div class="max-w-3xl mx-auto px-4 py-6">
            <h1 class="text-2xl font-black text-white mb-1">Form <span class="text-brand-purple">· vs own baseline</span></h1>
            <p class="text-sm text-slate-400 mb-3 leading-relaxed">
                <span class="text-slate-300 font-semibold">What is this?</span> <span class="text-slate-300">Overall form</span>
                rolls <span class="text-slate-300">all</span> the stats below into <span class="text-slate-300">one number</span>
                for a player's <span class="text-slate-300">last session</span>:
                <span class="text-slate-300 font-semibold">100% = exactly their own usual</span>, higher = a hot night,
                lower = off form. Each stat is measured against <span class="text-slate-300">that player's own recent-session
                average</span> (trailing ~10 sessions), then blended: damage 25% · impact 25% · K/D 20% · objectives 15% ·
                accuracy 10% · kills 5%. <span class="text-slate-300">Impact</span> = kills that stick — gibs, trade kills
                and clutch kills from proximity data. It's <span class="text-slate-300">rank-vs-self</span>,
                <span class="italic">not</span> a global ranking — a mid-table player having a great night can top the list.
            </p>
            <p class="text-xs text-slate-500 mb-4 leading-relaxed">
                <span class="text-emerald-400">▲</span> = above their usual, <span class="text-rose-400">▼</span> = below;
                the little line is their trend across recent sessions. Switch tabs to see the <span class="text-slate-400">single stat</span>
                that's driving the move — the chips under each name show how each one contributed.
            </p>
            <div id="form-metric-tabs" class="flex flex-wrap gap-2 mb-5">${_tabsHtml()}</div>
            <div id="form-list"></div>
        </div>`);
    const tabs = document.getElementById('form-metric-tabs');
    if (tabs) {
        tabs.addEventListener('click', (e) => {
            const btn = e.target.closest('button[data-metric]');
            if (!btn) return;
            _metric = btn.dataset.metric;
            tabs.textContent = '';
            safeInsertHTML(tabs, 'beforeend', _tabsHtml());
            _render().catch(() => {});
        });
    }
    await _render();
}
