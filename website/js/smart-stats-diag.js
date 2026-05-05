/**
 * Smart Stats Diagnostics view (legacy)
 * Per-session health check: KIS completeness, kill→round linkage, R1+R2 korelacija.
 * @module smart-stats-diag
 */

import { API_BASE, fetchJSON, escapeHtml } from './utils.js';

const CONTAINER_ID = 'smart-stats-diag-container';

let lastSessionDate = null;

function fmtPct(ratio) {
    if (ratio == null || Number.isNaN(ratio)) return '—';
    return `${(ratio * 100).toFixed(1)}%`;
}

function ratioBadge(ratio, goodThreshold = 0.95, warnThreshold = 0.80) {
    if (ratio == null || Number.isNaN(ratio)) {
        return '<span class="px-2 py-1 rounded text-xs font-bold bg-slate-700 text-slate-300">—</span>';
    }
    let cls;
    if (ratio >= goodThreshold) {
        cls = 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40';
    } else if (ratio >= warnThreshold) {
        cls = 'bg-amber-500/20 text-amber-400 border border-amber-500/40';
    } else {
        cls = 'bg-rose-500/20 text-rose-400 border border-rose-500/40';
    }
    return `<span class="px-2 py-1 rounded text-xs font-bold ${cls}">${fmtPct(ratio)}</span>`;
}

function warningCard(w) {
    const tone = w.level === 'warning'
        ? 'border-amber-500/40 bg-amber-500/10 text-amber-200'
        : 'border-slate-500/40 bg-slate-500/10 text-slate-300';
    return `
        <div class="rounded-lg border p-3 text-sm ${tone}">
            <span class="font-bold uppercase text-xs tracking-wider mr-2">${escapeHtml(w.level)}</span>
            ${escapeHtml(w.message)}
        </div>
    `;
}

function knownIssueCard(issue) {
    return `
        <div class="rounded-lg border border-slate-700/60 bg-slate-900/40 p-3">
            <div class="flex items-center gap-2 mb-1">
                <span class="text-xs font-bold uppercase tracking-wider text-slate-400">${escapeHtml(issue.key)}</span>
            </div>
            <div class="font-bold text-white text-sm mb-1">${escapeHtml(issue.title)}</div>
            <div class="text-slate-400 text-xs">${escapeHtml(issue.detail)}</div>
        </div>
    `;
}

function renderSummary(data) {
    const completeness = ratioBadge(data.completeness_ratio);
    const linkage = ratioBadge(data.linkage_ratio, 0.99, 0.90);
    const correlation = ratioBadge(data.correlation_ratio, 0.90, 0.60);
    return `
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <div class="rounded-xl border border-white/10 bg-slate-900/60 p-4">
                <div class="text-xs uppercase tracking-wider text-slate-400 mb-1">KIS pokritost</div>
                <div class="flex items-baseline gap-2">
                    <span class="text-3xl font-black text-white">${data.kis_rows}</span>
                    <span class="text-slate-500">/ ${data.kills_total}</span>
                </div>
                <div class="mt-2">${completeness}</div>
                <div class="text-xs text-slate-500 mt-2">kills z izračunanim KIS</div>
            </div>
            <div class="rounded-xl border border-white/10 bg-slate-900/60 p-4">
                <div class="text-xs uppercase tracking-wider text-slate-400 mb-1">Round linkage</div>
                <div class="flex items-baseline gap-2">
                    <span class="text-3xl font-black text-white">${data.kills_with_round}</span>
                    <span class="text-slate-500">/ ${data.kills_total}</span>
                </div>
                <div class="mt-2">${linkage}</div>
                <div class="text-xs text-slate-500 mt-2">kills povezani na round_id</div>
            </div>
            <div class="rounded-xl border border-white/10 bg-slate-900/60 p-4">
                <div class="text-xs uppercase tracking-wider text-slate-400 mb-1">R1+R2 korelacija</div>
                <div class="flex items-baseline gap-2">
                    <span class="text-3xl font-black text-white">${data.rounds_correlated}</span>
                    <span class="text-slate-500">/ ${data.rounds_total}</span>
                </div>
                <div class="mt-2">${correlation}</div>
                <div class="text-xs text-slate-500 mt-2">rounds-ov z match korelacijo</div>
            </div>
        </div>
    `;
}

function renderWarnings(warnings) {
    if (!warnings || warnings.length === 0) {
        return `
            <div class="rounded-lg border border-emerald-500/40 bg-emerald-500/10 text-emerald-300 p-3 text-sm mb-6">
                <span class="font-bold uppercase text-xs tracking-wider mr-2">OK</span>
                Brez opozoril — Smart Stats za ta datum so kompletni in povezani.
            </div>
        `;
    }
    return `
        <div class="space-y-2 mb-6">
            ${warnings.map(warningCard).join('')}
        </div>
    `;
}

function renderKnownIssues(issues) {
    if (!issues || issues.length === 0) return '';
    return `
        <div class="rounded-xl border border-white/10 bg-slate-950/40 p-4 mb-6">
            <div class="text-xs uppercase tracking-wider text-slate-400 mb-3">
                Sistemska opozorila (vplivajo na vse datume)
            </div>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
                ${issues.map(knownIssueCard).join('')}
            </div>
        </div>
    `;
}

function renderRawDump(data) {
    const json = JSON.stringify(data, null, 2);
    return `
        <details class="rounded-xl border border-white/10 bg-slate-950/40 p-4">
            <summary class="cursor-pointer text-xs uppercase tracking-wider text-slate-400 select-none">
                Surovi JSON odgovor
            </summary>
            <pre class="mt-3 text-xs text-slate-300 overflow-x-auto">${escapeHtml(json)}</pre>
        </details>
    `;
}

function renderControls(sessionDate) {
    return `
        <div class="flex flex-wrap items-end gap-3 mb-6">
            <div>
                <label for="diag-session-date" class="block text-xs uppercase tracking-wider text-slate-400 mb-1">
                    Session date
                </label>
                <input
                    type="date"
                    id="diag-session-date"
                    value="${escapeHtml(sessionDate || '')}"
                    class="bg-slate-900 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-brand-blue" />
            </div>
            <button
                id="diag-refresh-btn"
                class="bg-brand-blue/20 hover:bg-brand-blue/30 border border-brand-blue/40 text-brand-blue px-4 py-2 rounded-lg text-sm font-bold transition">
                Osveži
            </button>
        </div>
    `;
}

function renderError(msg) {
    return `
        <div class="rounded-lg border border-rose-500/40 bg-rose-500/10 text-rose-300 p-4 text-sm">
            <span class="font-bold uppercase text-xs tracking-wider mr-2">Napaka</span>
            ${escapeHtml(msg)}
        </div>
    `;
}

function renderLoading() {
    return `
        <div class="rounded-lg border border-white/10 bg-slate-900/40 p-6 text-center text-slate-400 text-sm">
            Nalagam diagnostiko...
        </div>
    `;
}

async function fetchAndRender(sessionDate, container) {
    container.innerHTML = renderControls(sessionDate) + renderLoading();
    wireControls(container);

    try {
        const data = await fetchJSON(
            `${API_BASE}/diagnostics/storytelling-completeness?session_date=${encodeURIComponent(sessionDate)}`
        );
        container.innerHTML = `
            ${renderControls(sessionDate)}
            ${renderSummary(data)}
            ${renderWarnings(data.warnings)}
            ${renderKnownIssues(data.known_issues)}
            ${renderRawDump(data)}
        `;
        wireControls(container);
    } catch (err) {
        container.innerHTML = renderControls(sessionDate) + renderError(err?.message || 'Endpoint ni dostopen.');
        wireControls(container);
    }
}

function wireControls(container) {
    const input = container.querySelector('#diag-session-date');
    const btn = container.querySelector('#diag-refresh-btn');
    if (!input || !btn) return;

    const trigger = () => {
        const v = input.value;
        if (!v) return;
        lastSessionDate = v;
        fetchAndRender(v, container);
    };
    btn.addEventListener('click', trigger);
    input.addEventListener('change', trigger);
}

async function pickDefaultSessionDate() {
    if (lastSessionDate) return lastSessionDate;
    try {
        const scopes = await fetchJSON(`${API_BASE}/proximity/scopes?range_days=30`);
        const sessions = scopes?.sessions || [];
        if (sessions.length > 0 && sessions[0].session_date) {
            return sessions[0].session_date;
        }
    } catch (_) { /* fallthrough */ }
    return new Date().toISOString().slice(0, 10);
}

export async function loadSmartStatsDiagView() {
    const container = document.getElementById(CONTAINER_ID);
    if (!container) {
        console.error('Smart Stats Diag container manjka');
        return;
    }
    const sessionDate = await pickDefaultSessionDate();
    lastSessionDate = sessionDate;
    await fetchAndRender(sessionDate, container);
}
