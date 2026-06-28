/**
 * Record Book (VISION_2026 S6 SPOMIN) — consolidates All-Time Records, the Hall
 * of Fame, and Season champions into one tabbed page. Reuses the existing
 * loaders (records.js, hall-of-fame.js) which render into containers now hosted
 * inside #view-record-book; the Season tab is rendered here.
 * @module record-book
 */
import { API_BASE, fetchJSON, escapeHtml, safeInsertHTML } from './utils.js';
import { loadRecordsView } from './records.js';
import { loadHallOfFameView } from './hall-of-fame.js';

const _loaded = { records: false, hof: false, season: false };

function _showTab(key) {
    document.querySelectorAll('[data-rb-tab]').forEach(el => {
        el.classList.toggle('hidden', el.getAttribute('data-rb-tab') !== key);
    });
    const bar = document.getElementById('rb-tabbar');
    if (bar) {
        bar.querySelectorAll('[data-rb-tabbtn]').forEach(b => {
            const active = b.getAttribute('data-rb-tabbtn') === key;
            b.classList.toggle('bg-brand-cyan/20', active);
            b.classList.toggle('text-brand-cyan', active);
            b.classList.toggle('bg-white/5', !active);
            b.classList.toggle('text-slate-400', !active);
        });
    }
    _ensureLoaded(key);
}

function _ensureLoaded(key) {
    if (_loaded[key]) return;
    const loaders = {
        records: loadRecordsView,
        hof: loadHallOfFameView,
        season: loadRecordBookSeason,
    };
    const loader = loaders[key];
    if (!loader) return;
    // Mark loaded only AFTER the fetch succeeds — otherwise a transient failure
    // leaves the tab permanently empty (the early `_loaded=true` blocked retry).
    // Leaving it false on error means re-clicking the tab retries.
    loader()
        .then(() => { _loaded[key] = true; })
        .catch(e => console.warn(`record book: ${key} failed`, e));
}

export async function loadRecordBookView(params = {}) {
    const bar = document.getElementById('rb-tabbar');
    if (bar && !bar.dataset.wired) {
        bar.dataset.wired = '1';
        bar.querySelectorAll('[data-rb-tabbtn]').forEach(b => {
            b.addEventListener('click', () => _showTab(b.getAttribute('data-rb-tabbtn')));
        });
    }
    const tab = ['records', 'hof', 'season'].includes(params.tab) ? params.tab : 'records';
    _showTab(tab);
}

// Season tab — current season champions + category leaders (self-contained).
async function loadRecordBookSeason() {
    const host = document.getElementById('rb-season-content');
    if (!host) return;
    host.textContent = '';
    const [seasonRes, leadersRes, awardsRes] = await Promise.allSettled([
        fetchJSON(`${API_BASE}/seasons/current`),
        fetchJSON(`${API_BASE}/seasons/current/leaders`),
        fetchJSON(`${API_BASE}/seasons/current/awards`),
    ]);
    const season = seasonRes.status === 'fulfilled' ? seasonRes.value : null;
    const leaders = leadersRes.status === 'fulfilled' ? (leadersRes.value?.leaders || {}) : {};
    const awards = awardsRes.status === 'fulfilled' ? (awardsRes.value?.awards || []) : [];

    const title = season?.name || season?.id || 'Current season';
    const daysLeft = Number.isFinite(season?.days_left) ? season.days_left : null;

    const _AWARD_EMOJI = { mvp: '👑', iron_man: '🛡️', most_improved: '📈', oracle: '🔮' };
    const champions = awards.length
        ? awards.map(a => `
            <div class="glass-panel p-4 rounded-xl border-l-4 border-brand-amber/60">
                <div class="text-[10px] uppercase tracking-widest text-slate-500 font-bold mb-1">${_AWARD_EMOJI[a.award_key] || '🏆'} ${escapeHtml(a.label || a.award_key)}</div>
                <div class="text-base text-white font-black">${escapeHtml(a.player_name || '?')}</div>
                ${a.value_text ? `<div class="text-xs text-slate-400 mt-0.5">${escapeHtml(a.value_text)}</div>` : ''}
            </div>`).join('')
        : '<div class="text-sm text-slate-400">No engraved season awards yet.</div>';

    const _LEADER_LABELS = {
        damage_given: 'Most damage', kills: 'Most kills', dpm: 'Top DPM',
        revives: 'Most revives', objectives: 'Most objectives', gibs: 'Most gibs',
        xp: 'Most XP',
    };
    const leaderRows = Object.entries(_LEADER_LABELS)
        .filter(([k]) => leaders[k])
        .map(([k, label]) => {
            const l = leaders[k];
            const val = typeof l.value === 'number' ? l.value.toLocaleString() : l.value;
            return `<div class="flex justify-between text-sm py-1.5 border-b border-white/5">
                <span class="text-slate-500">${label}</span>
                <span class="text-slate-200 font-semibold">${escapeHtml(String(l.player || '—'))} · ${escapeHtml(String(val))}</span>
            </div>`;
        }).join('');

    safeInsertHTML(host, 'beforeend', `
        <div class="flex items-center justify-between mb-4">
            <h2 class="text-2xl font-black text-white">🏟️ ${escapeHtml(title)}</h2>
            ${daysLeft !== null ? `<span class="text-xs uppercase tracking-widest text-brand-cyan font-bold">${daysLeft} days left</span>` : ''}
        </div>
        <div class="text-xs uppercase tracking-widest text-brand-amber font-bold mb-3">Season Champions</div>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">${champions}</div>
        <div class="text-xs uppercase tracking-widest text-slate-500 font-bold mb-2">Category leaders</div>
        <div class="glass-panel p-5 rounded-xl">${leaderRows || '<div class="text-sm text-slate-400">No leaders yet.</div>'}</div>
        <a href="#/leaderboards?period=season" class="mt-4 inline-block text-xs font-bold text-brand-cyan hover:text-white transition">Full season leaderboard →</a>
    `);
}
