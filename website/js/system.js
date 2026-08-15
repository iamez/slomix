/**
 * System overview (legacy)
 *
 * One page that answers "is the chain running?" — game server → Lua capture →
 * parser → Smart Stats → website API — from a single composite endpoint
 * (`/api/system/overview`). Every stage renders on its own, so one dead
 * source greys out one row instead of blanking the page.
 *
 * Deliberately NOT here: systemd units, prod-vs-main drift and Lua file
 * hashes on the game server. The web process cannot see any of those, and a
 * status page that guesses is worse than one that says nothing —
 * `scripts/system_status.sh` reports them from a host that can.
 *
 * @module system
 */

import { API_BASE, fetchJSON } from './utils.js';

/** Safe DOM element factory. Strings become text nodes; null children are skipped. */
function _el(tag, className, ...children) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    for (const c of children) {
        if (c == null) continue;
        el.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    }
    return el;
}

// Every class here already exists in the committed tailwind.css (checked
// class by class — the build is prebuilt, lesson #699).
const STATE_STYLE = {
    ok:      { dot: 'bg-emerald-500', text: 'text-emerald-400', label: 'OK' },
    idle:    { dot: 'bg-slate-600',   text: 'text-slate-400',   label: 'IDLE' },
    warn:    { dot: 'bg-amber-500',   text: 'text-amber-400',   label: 'WARN' },
    down:    { dot: 'bg-rose-500',    text: 'text-rose-400',    label: 'DOWN' },
    unknown: { dot: 'bg-slate-600',   text: 'text-slate-500',   label: 'N/A' },
};

const OVERALL_HEADLINE = {
    ok: 'Everything is running',
    idle: 'Everything is running — nobody has played lately',
    warn: 'Running, with something worth a look',
    down: 'Something is down',
    unknown: 'State unknown',
};

function _style(state) {
    return STATE_STYLE[state] || STATE_STYLE.unknown;
}

/** "2 h ago" / "3 d ago" from a seconds count the API already computed. */
function _age(seconds) {
    if (seconds == null || !Number.isFinite(seconds)) return '';
    if (seconds < 90) return 'just now';
    if (seconds < 5400) return `${Math.round(seconds / 60)} min ago`;
    if (seconds < 172800) return `${Math.round(seconds / 3600)} h ago`;
    return `${Math.round(seconds / 86400)} d ago`;
}

/** The one detail line per stage that is worth reading at a glance. */
function _stageFacts(stage) {
    const d = stage.detail || {};
    const facts = [];
    switch (stage.key) {
        case 'game_server':
            if (d.ping_ms != null) facts.push(`${d.ping_ms} ms`);
            break;
        case 'capture':
            if (d.age_seconds != null) facts.push(`last capture ${_age(d.age_seconds)}`);
            if (d.unlinked_last_48h) facts.push(`${d.unlinked_last_48h} unlinked`);
            break;
        case 'parser':
            if (d.age_seconds != null) facts.push(`last round ${_age(d.age_seconds)}`);
            if (d.last_round_at) facts.push(String(d.last_round_at).replace('T', ' ').slice(0, 16));
            break;
        case 'derived':
            if (d.gaming_session_id != null) facts.push(`session ${d.gaming_session_id}`);
            if (d.rounds != null) facts.push(`${d.rounds} rounds`);
            if (d.kill_impact_rows != null) facts.push(`${d.kill_impact_rows} KIS rows`);
            if (d.proximity_kills != null) facts.push(`${d.proximity_kills} tracked kills`);
            break;
        default:
            break;
    }
    return facts;
}

function _renderStage(stage) {
    const st = _style(stage.state);
    const row = _el('div', 'flex items-start gap-3 py-3 border-b border-white/5');

    const dotWrap = _el('div', 'flex flex-col items-center pt-1');
    dotWrap.appendChild(_el('span', `w-2.5 h-2.5 rounded-full ${st.dot}`));
    row.appendChild(dotWrap);

    const body = _el('div', 'flex-1 min-w-0');
    const head = _el('div', 'flex items-center gap-2 flex-wrap');
    head.appendChild(_el('span', 'text-sm font-bold text-white', stage.label || stage.key));
    head.appendChild(_el('span', `text-[10px] font-bold uppercase tracking-wider ${st.text}`, st.label));
    body.appendChild(head);
    body.appendChild(_el('div', 'text-xs text-slate-400 mt-0.5', stage.summary || ''));

    const facts = _stageFacts(stage);
    if (facts.length > 0) {
        const factRow = _el('div', 'flex flex-wrap gap-2 mt-1');
        facts.forEach(f => factRow.appendChild(
            _el('span', 'text-[10px] text-slate-500 tabular-nums', f)
        ));
        body.appendChild(factRow);
    }
    row.appendChild(body);
    return row;
}

function _renderLinkage(linkage) {
    const card = _el('div', 'rounded-2xl border border-white/10 bg-white/[0.03] p-6 mt-6');
    card.appendChild(_el('h3', 'text-sm font-bold text-white mb-3', 'Data integrity'));

    if (!linkage || linkage.available !== true) {
        card.appendChild(_el('div', 'text-xs text-slate-500', 'Linkage check unavailable.'));
        return card;
    }

    const m = linkage.metrics || {};
    const ratio = Number(m.unlinked_lua_ratio);
    const grid = _el('div', 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3');
    const cell = (label, value) => _el('div', 'rounded-lg bg-white/[0.03] px-3 py-2',
        _el('div', 'text-[10px] text-slate-500 uppercase tracking-wider', label),
        _el('div', 'text-sm font-bold tabular-nums text-white', value)
    );
    if (Number.isFinite(ratio)) grid.appendChild(cell('Unlinked captures', `${(ratio * 100).toFixed(1)}%`));
    if (m.total_lua_rows != null) grid.appendChild(cell('Captured rounds', String(m.total_lua_rows)));
    if (m.wrong_start_lua_rows != null) grid.appendChild(cell('Wrong-round links', String(m.wrong_start_lua_rows)));
    if (grid.children.length > 0) card.appendChild(grid);

    const breaches = Array.isArray(linkage.breaches) ? linkage.breaches : [];
    if (breaches.length === 0) {
        card.appendChild(_el('div', 'text-xs text-emerald-400 mt-3', 'No thresholds breached.'));
    } else {
        const list = _el('div', 'mt-3 space-y-1');
        breaches.forEach(b => list.appendChild(_el('div', 'text-xs text-amber-400',
            `${b.metric}: ${b.value} (threshold ${b.threshold})`)));
        card.appendChild(list);
    }
    return card;
}

function _renderError(container, message) {
    container.textContent = '';
    container.appendChild(_el('div', 'rounded-2xl border border-rose-500/30 bg-rose-500/10 p-6',
        _el('div', 'text-rose-400 text-sm font-bold mb-1', 'Overview unavailable'),
        _el('div', 'text-xs text-slate-400', message)
    ));
}

function _render(container, data) {
    container.textContent = '';

    const overall = data.overall || 'unknown';
    const st = _style(overall);

    const header = _el('div', 'flex items-start justify-between gap-3 flex-wrap mb-4');
    const left = _el('div', null,
        _el('h2', 'text-2xl font-black text-white', OVERALL_HEADLINE[overall] || OVERALL_HEADLINE.unknown),
        _el('div', 'text-xs text-slate-500 mt-1',
            data.generated_at ? `Checked ${String(data.generated_at).replace('T', ' ').slice(0, 19)} UTC` : '')
    );
    header.appendChild(left);
    header.appendChild(_el('span',
        `inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wider ${st.text}`,
        st.label));
    container.appendChild(header);

    const chain = _el('div', 'rounded-2xl border border-white/10 bg-white/[0.03] p-6');
    const stages = Array.isArray(data.stages) ? data.stages : [];
    if (stages.length === 0) {
        chain.appendChild(_el('div', 'text-xs text-slate-500', 'No stages reported.'));
    } else {
        stages.forEach(s => chain.appendChild(_renderStage(s)));
    }
    container.appendChild(chain);
    container.appendChild(_renderLinkage(data.linkage));
}

let _systemTimer = null;

export async function loadSystemView() {
    const container = document.getElementById('system-content');
    if (!container) return;

    container.textContent = '';
    container.appendChild(_el('div', 'text-center text-slate-500 py-12', 'Checking the chain…'));

    async function refresh() {
        try {
            // `no-store` is not optional here. fetchJSON's default is
            // stale-while-revalidate: it hands back the cached body and
            // refreshes in the background, so a status page would keep
            // claiming everything is fine for a full extra cycle after a
            // stage went down. A status page must never read from a cache.
            const data = await fetchJSON(`${API_BASE}/system/overview`, { cachePolicy: 'no-store' });
            _render(container, data);
        } catch (err) {
            // The page itself IS a status report: say the API is unreachable
            // rather than showing a spinner forever.
            _renderError(container, 'The website API did not answer. That itself is the status.');
            console.error('system overview failed:', err);
        }
    }

    await refresh();

    // Light auto-refresh: the acceptance test for this page is that a stage
    // going bad shows up without a manual reload.
    if (_systemTimer) clearInterval(_systemTimer);
    _systemTimer = setInterval(() => {
        const view = document.getElementById('view-system');
        if (!view || view.classList.contains('hidden')) {
            clearInterval(_systemTimer);
            _systemTimer = null;
            return;
        }
        refresh();
    }, 30000);
}
