/**
 * Home pulse cards (VISION_2026 S1.2) — the returning member's three
 * questions, above the fold: when do we play next? what happened last
 * night? who's in form? (HLTV three-zone pattern, R2 §4.1-4.2)
 * @module home
 */

import { API_BASE, fetchJSON, escapeHtml, safeInsertHTML, sparklineSVG } from './utils.js';
import { loadHomeTonightCard } from './tonight.js';

function _card({ title, accent, bodyHtml, href, cta }) {
    const link = href
        ? `<a href="${escapeHtml(href)}" class="mt-3 inline-block text-xs font-bold text-brand-${accent} hover:text-white transition">${escapeHtml(cta || 'Open')} →</a>`
        : '';
    return `
        <div class="glass-panel p-5 rounded-xl border-l-4 border-brand-${accent}/60 hover:border-brand-${accent} transition-colors">
            <div class="text-[10px] uppercase tracking-widest text-slate-500 font-bold mb-2">${escapeHtml(title)}</div>
            ${bodyHtml}
            ${link}
        </div>`;
}

function _nextSessionCard(avail) {
    const days = (avail?.days || []).filter(d => (d.total || 0) > 0);
    if (!days.length) {
        return _card({
            title: 'Next session', accent: 'cyan',
            bodyHtml: '<div class="text-sm text-slate-400">No votes yet — pick a night.</div>',
            href: '#/availability', cta: 'Vote availability',
        });
    }
    const d = days[0];
    const c = d.counts || {};
    const committed = (c.LOOKING || 0) + (c.AVAILABLE || 0);
    const date = new Date(d.date + 'T12:00:00');
    const label = date.toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' });
    return _card({
        title: 'Next session', accent: 'cyan',
        bodyHtml: `
            <div class="text-lg font-black text-white">${escapeHtml(label)}</div>
            <div class="text-sm text-slate-400 mt-1">${committed} in${c.MAYBE ? ` · ${c.MAYBE} maybe` : ''}</div>`,
        href: '#/availability', cta: 'Vote / join',
    });
}

function _lastSessionCard(sessions) {
    const s = Array.isArray(sessions) ? sessions[0] : null;
    if (!s) {
        return _card({
            title: 'Last session', accent: 'amber',
            bodyHtml: '<div class="text-sm text-slate-400">No sessions yet.</div>',
        });
    }
    const maps = (s.maps_played || []).slice(0, 3).join(', ');
    return _card({
        title: `Last session · ${s.time_ago || s.date}`, accent: 'amber',
        bodyHtml: `
            <div class="text-lg font-black text-white">${s.rounds} rounds · ${s.players} players</div>
            <div class="text-sm text-slate-400 mt-1">${escapeHtml(maps)}${s.maps > 3 ? '…' : ''} · ${s.total_kills} kills</div>`,
        href: s.session_id ? `#/session-detail/${s.session_id}` : `#/session-detail/date/${encodeURIComponent(s.date)}`,
        cta: 'Full recap',
    });
}

function _moverRow(m, kind) {
    const spark = sparklineSVG(m.series, { up: kind === 'up' ? true : kind === 'down' ? false : null, width: 56, height: 16 });
    const right = kind === 'new'
        ? '<span class="text-amber-400 font-mono text-xs">FIRST NIGHT</span>'
        : `<span class="${kind === 'up' ? 'text-emerald-400' : 'text-rose-400'} font-mono">${kind === 'up' ? '▲ +' : '▼ '}${m.delta_pct}%</span>`;
    return `<div class="flex items-center justify-between text-sm gap-2">
        <a class="text-slate-300 hover:text-brand-cyan transition truncate max-w-[7rem]" href="#/profile/${encodeURIComponent(m.guid)}">${escapeHtml(m.name)}</a>
        <div class="flex items-center gap-2">${spark}${right}</div></div>`;
}

function _moversCard(movers) {
    const rows = [];
    (movers?.movers_up || []).slice(0, 2).forEach(m => rows.push(_moverRow(m, 'up')));
    (movers?.movers_down || []).slice(0, 2).forEach(m => rows.push(_moverRow(m, 'down')));
    (movers?.new_players || []).slice(0, 1).forEach(m => rows.push(_moverRow(m, 'new')));
    if (!rows.length) {
        return _card({
            title: 'Movers · vs own form', accent: 'purple',
            bodyHtml: '<div class="text-sm text-slate-400">Form data appears after the next session.</div>',
            href: '#/form', cta: 'What is form?',
        });
    }
    return _card({
        title: 'Movers · vs own form', accent: 'purple',
        bodyHtml: `<div class="space-y-1.5">${rows.join('')}</div>`
            + '<div class="text-[10px] text-slate-500 mt-2">Last session vs each player’s own recent average — not a global ranking.</div>',
        href: '#/form', cta: 'Full form',
    });
}

export async function loadHomePulseCards() {
    const host = document.getElementById('home-pulse-cards');
    if (!host) return;
    const [availRes, sessRes, moversRes] = await Promise.allSettled([
        fetchJSON(`${API_BASE}/availability`),
        fetchJSON(`${API_BASE}/sessions?limit=1`),
        fetchJSON(`${API_BASE}/skill/movers`),
    ]);
    const avail = availRes.status === 'fulfilled' ? availRes.value : null;
    const sessions = sessRes.status === 'fulfilled' ? sessRes.value : null;
    const movers = moversRes.status === 'fulfilled' ? moversRes.value : null;

    host.textContent = '';
    safeInsertHTML(host, 'beforeend',
        _nextSessionCard(avail) + _lastSessionCard(sessions) + _moversCard(movers));

    loadChallengeCard().catch((e) => console.warn('challenge card failed', e));
    loadSeasonCard().catch((e) => console.warn('season card failed', e));
    loadHomeTonightCard().catch((e) => console.warn('tonight card failed', e));
}

// Season card (S4) — current quarterly season + top damage leaders + days left.
export async function loadSeasonCard() {
    const host = document.getElementById('home-season-card');
    if (!host) return;
    const [seasonRes, leadersRes] = await Promise.allSettled([
        fetchJSON(`${API_BASE}/seasons/current`),
        fetchJSON(`${API_BASE}/seasons/current/leaders`),
    ]);
    const season = seasonRes.status === 'fulfilled' ? seasonRes.value : null;
    const leaders = leadersRes.status === 'fulfilled' ? leadersRes.value?.leaders : null;
    if (!season) { host.textContent = ''; return; }

    const top = [];
    const dmg = leaders?.damage_given;
    const kills = leaders?.kills;
    const dpm = leaders?.dpm;
    if (dmg) top.push(`<div class="flex justify-between text-sm"><span class="text-slate-500">Most damage</span><span class="text-slate-200 font-semibold">${escapeHtml(dmg.player)} · ${dmg.value.toLocaleString()}</span></div>`);
    if (kills) top.push(`<div class="flex justify-between text-sm"><span class="text-slate-500">Most kills</span><span class="text-slate-200 font-semibold">${escapeHtml(kills.player)} · ${kills.value}</span></div>`);
    if (dpm) top.push(`<div class="flex justify-between text-sm"><span class="text-slate-500">Top DPM</span><span class="text-slate-200 font-semibold">${escapeHtml(dpm.player)} · ${Math.round(dpm.value)}</span></div>`);

    const daysLeft = Number.isFinite(season.days_left) ? season.days_left : null;
    host.textContent = '';
    safeInsertHTML(host, 'beforeend', `
        <div class="glass-panel p-5 rounded-xl border-l-4 border-brand-cyan/60">
            <div class="flex items-center justify-between mb-2">
                <div class="text-[10px] uppercase tracking-widest text-slate-500 font-bold">🏟️ ${escapeHtml(season.name || season.id)}</div>
                ${daysLeft !== null ? `<div class="text-[10px] uppercase tracking-widest text-brand-cyan font-bold">${daysLeft} days left</div>` : ''}
            </div>
            ${top.length ? `<div class="space-y-1.5">${top.join('')}</div>` : '<div class="text-sm text-slate-400">Season standings appear after the first matches.</div>'}
            <a href="#/leaderboards?period=season" class="mt-3 inline-block text-xs font-bold text-brand-cyan hover:text-white transition">Season leaderboard →</a>
        </div>`);
}

// Challenge of the week (S3) — admin-defined, surfaced for everyone.
export async function loadChallengeCard() {
    const host = document.getElementById('home-challenge-card');
    if (!host) return;
    let data;
    try {
        data = await fetchJSON(`${API_BASE}/challenges/current`);
    } catch (_) {
        host.textContent = '';
        return;
    }
    const ch = data?.challenge;
    if (!ch) {
        host.textContent = '';
        return;
    }
    host.textContent = '';
    safeInsertHTML(host, 'beforeend', `
        <div class="glass-panel p-5 rounded-xl border-l-4 border-brand-amber/60">
            <div class="text-[10px] uppercase tracking-widest text-slate-500 font-bold mb-2">🏆 Challenge of the week</div>
            <div class="text-lg font-black text-white">${escapeHtml(ch.title)}</div>
            ${ch.description ? `<div class="text-sm text-slate-400 mt-1">${escapeHtml(ch.description)}</div>` : ''}
        </div>`);
}
