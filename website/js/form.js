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
    { key: 'dpm', label: 'Damage / min' },
    { key: 'kd', label: 'Kills / death' },
    { key: 'obj', label: 'Objectives / round' },
    { key: 'acc', label: 'Accuracy' },
    { key: 'kills', label: 'Kills / session' },
];

let _metric = 'dpm';

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

function _moverRow(m) {
    const isNew = !!m.is_new;
    const up = m.delta_pct != null && m.delta_pct > 0;
    const deltaCls = isNew ? 'text-amber-400' : up ? 'text-emerald-400' : 'text-rose-400';
    const deltaTxt = isNew
        ? 'FIRST NIGHT'
        : `${up ? '▲ +' : '▼ '}${m.delta_pct}%`;
    const baseline = (m.latest != null && m.baseline != null)
        ? `${m.latest} <span class="text-slate-600">vs</span> ${m.baseline}`
        : (m.latest != null ? `${m.latest}` : '');
    const spark = sparklineSVG(m.series, { up: isNew ? null : up });
    return `
        <div class="flex items-center justify-between gap-3 py-2 border-b border-white/5">
            <a class="text-slate-200 hover:text-brand-cyan transition font-medium truncate max-w-[10rem]"
               href="#/profile/${encodeURIComponent(m.guid)}">${escapeHtml(m.name)}</a>
            <div class="flex items-center gap-3">
                <span class="text-slate-500 text-xs font-mono hidden sm:inline">${baseline}</span>
                ${spark}
                <span class="font-mono text-sm ${deltaCls} w-24 text-right">${escapeHtml(deltaTxt)}</span>
            </div>
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
    list.innerHTML = '<div class="text-sm text-slate-400 py-6 text-center">Loading form…</div>';
    let data;
    try {
        data = await fetchJSON(`${API_BASE}/skill/movers?full=true&metric=${encodeURIComponent(_metric)}`);
    } catch {
        list.innerHTML = '<div class="text-sm text-rose-400 py-6 text-center">Could not load form data.</div>';
        return;
    }
    const up = data?.movers_up || [];
    const down = data?.movers_down || [];
    const fresh = data?.new_players || [];
    if (!up.length && !down.length && !fresh.length) {
        list.innerHTML = '<div class="text-sm text-slate-400 py-6 text-center">Form data appears after the next session.</div>';
        return;
    }
    const dateTxt = data.session_date ? ` · last session ${escapeHtml(String(data.session_date))}` : '';
    list.innerHTML = '';
    safeInsertHTML(list, 'beforeend',
        `<div class="text-xs text-slate-500 mb-3">Metric: <span class="text-slate-300 font-semibold">${escapeHtml(data.metric_label || _metric)}</span>${dateTxt}</div>`
        + _section('Heating up · above own average', 'purple', up)
        + _section('Cooling off · below own average', 'amber', down)
        + _section('First night', 'cyan', fresh));
}

export async function loadFormView() {
    const host = document.getElementById('view-form');
    if (!host) return;
    host.innerHTML = `
        <div class="max-w-3xl mx-auto px-4 py-6">
            <h1 class="text-2xl font-black text-white mb-1">Form <span class="text-brand-purple">· vs own baseline</span></h1>
            <p class="text-sm text-slate-400 mb-4 leading-relaxed">
                <span class="text-slate-300 font-semibold">What is this?</span> Form compares each player's
                <span class="text-slate-300">last session</span> to <span class="text-slate-300">their own recent-session average</span>
                (trailing ~10 sessions) for the chosen metric. It's <span class="text-slate-300">rank-vs-self</span>,
                <span class="italic">not</span> a global ranking — a mid-table player having a great night can top
                the list. <span class="text-emerald-400">▲</span> = above their usual, <span class="text-rose-400">▼</span> = below.
                The little line is their trend across recent sessions.
            </p>
            <div id="form-metric-tabs" class="flex flex-wrap gap-2 mb-5">${_tabsHtml()}</div>
            <div id="form-list"></div>
        </div>`;
    const tabs = document.getElementById('form-metric-tabs');
    if (tabs) {
        tabs.addEventListener('click', (e) => {
            const btn = e.target.closest('button[data-metric]');
            if (!btn) return;
            _metric = btn.dataset.metric;
            tabs.innerHTML = _tabsHtml();
            _render().catch(() => {});
        });
    }
    await _render();
}
