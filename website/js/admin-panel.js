/**
 * About / System Overview view.
 *
 * Renamed from "Admin Panel" — the legacy reactor/atlas UI was removed in favor
 * of a project-overview page. The route id stays "admin" so existing bookmarks
 * keep working; the visible label is "About" and the content is informational.
 *
 * Pulls live numbers from /api/stats/overview (public) and a status ping from
 * /api/status. Everything else is static markup in index.html (#view-admin).
 */

import { API_BASE, fetchJSON } from './utils.js';

let initialized = false;

const VERSION_FALLBACK = 'v1.11.1';
const PAGE_REVISION = 'about-1.0';

function formatNumber(n) {
    if (n == null || Number.isNaN(Number(n))) return '—';
    return Number(n).toLocaleString('en-US');
}

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function setStatus(state, label) {
    // state: 'ok' | 'warn' | 'down'
    const dot = document.getElementById('about-status-dot');
    const text = document.getElementById('about-status-text');
    if (!dot || !text) return;
    text.textContent = label;
    dot.classList.remove('bg-slate-500', 'bg-emerald-400', 'bg-amber-400', 'bg-rose-500');
    dot.classList.add(
        state === 'ok' ? 'bg-emerald-400'
        : state === 'warn' ? 'bg-amber-400'
        : state === 'down' ? 'bg-rose-500'
        : 'bg-slate-500'
    );
}

async function loadOverview() {
    try {
        const data = await fetchJSON(`${API_BASE}/stats/overview`);
        setText('about-stat-rounds', formatNumber(data.rounds));
        setText('about-stat-kills', formatNumber(data.total_kills));
        setText('about-stat-players', formatNumber(data.players_all_time ?? data.players));
        setText('about-stat-sessions', formatNumber(data.sessions));

        if (data.rounds_since && data.rounds_latest) {
            setText('about-stat-rounds-sub', `${data.rounds_since} → ${data.rounds_latest}`);
        }
        if (data.players_14d != null) {
            setText('about-stat-players-sub', `${data.players_14d} active in last 14d`);
        }
        if (data.sessions_14d != null) {
            setText('about-stat-sessions-sub', `${data.sessions_14d} session(s) in last 14d`);
        }
    } catch (err) {
        console.warn('[about] overview fetch failed:', err);
        // Leave em-dashes in place; not fatal.
    }
}

async function loadStatus() {
    try {
        const data = await fetchJSON(`${API_BASE}/status`);
        const dbOk = (data.database || '').toLowerCase() === 'ok';
        const apiOk = (data.status || '').toLowerCase() === 'online';
        if (dbOk && apiOk) {
            setStatus('ok', 'API + DB online');
        } else if (apiOk) {
            setStatus('warn', 'API online, DB degraded');
        } else {
            setStatus('warn', 'Service degraded');
        }
    } catch (err) {
        console.warn('[about] status fetch failed:', err);
        setStatus('down', 'API unreachable');
    }
}

function setVersion() {
    // Future: pull from a /api/version endpoint. For now the README badge
    // wins so this stays a static fallback.
    setText('about-version', VERSION_FALLBACK);
    setText('about-build-info', `page rev: ${PAGE_REVISION}`);
}

export function loadAdminPanelView() {
    setVersion();
    // Fire both in parallel; neither is critical to render.
    Promise.all([loadOverview(), loadStatus()]).catch(() => { /* swallowed per-call */ });
    initialized = true;
}

// Expose for debugging in the browser console without re-importing.
if (typeof window !== 'undefined') {
    window.__about_reload = () => {
        if (!initialized) loadAdminPanelView();
        else { loadOverview(); loadStatus(); }
    };
}
