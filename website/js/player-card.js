/**
 * Player Card (SUPER LIVE 2.0, Val C) — the FUT × tracker.gg style snapshot:
 * "core insight in 3 seconds". One data source (GET /api/players/{id}/card,
 * a composite of EXISTING rating/archetype/form/badge computations) and one
 * renderer with size variants:
 *   L — profile embed, M — modal (live roster click / leaderboards).
 * The modal accepts optional live numbers (kills/deaths/dpm/alive) so the
 * live page can show tonight's line next to the 90-day identity.
 * @module player-card
 */
import { API_BASE, fetchJSON, escapeHtml, safeInsertHTML } from './utils.js';

// Actual player_skill_ratings.rating_class values (dev DB, 2026-08):
// veteran / experienced / regular / newcomer.
const TIER_COLORS = {
    veteran: '#f59e0b', experienced: '#22d3ee', regular: '#34d399',
    newcomer: '#a78bfa', unknown: '#64748b',
};
const ARCHETYPE_LABELS = {
    pressure_engine: 'Pressure Engine', fragger: 'Fragger',
    objective_specialist: 'Objective Specialist', support_anchor: 'Support Anchor',
    survivor: 'Survivor', trader: 'Trader', clutch_player: 'Clutch Player',
    allrounder: 'All-rounder',
};

function _tierColor(tier) {
    return TIER_COLORS[String(tier || '').toLowerCase()] || TIER_COLORS.unknown;
}

function _archetypeLabel(key) {
    return ARCHETYPE_LABELS[key] || String(key || 'All-rounder')
        .replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

/** Percentile ring (SVG): value label centred, ring fill = percentile. */
function _ring(label, value, pct, color) {
    const r = 17, c = 2 * Math.PI * r;
    const filled = pct == null ? 0 : Math.max(0.02, pct / 100);
    return `<div class="flex flex-col items-center gap-0.5">
        <svg width="46" height="46" viewBox="0 0 46 46" role="img" aria-label="${escapeHtml(label)} ${escapeHtml(String(value))}">
            <circle cx="23" cy="23" r="${r}" fill="none" stroke="#ffffff14" stroke-width="4"/>
            <circle cx="23" cy="23" r="${r}" fill="none" stroke="${color}" stroke-width="4"
                stroke-dasharray="${(c * filled).toFixed(1)} ${c.toFixed(1)}"
                stroke-linecap="round" transform="rotate(-90 23 23)"/>
            <text x="23" y="26" text-anchor="middle" font-size="11" font-weight="800" fill="#e2e8f0">${escapeHtml(String(value))}</text>
        </svg>
        <span class="text-[9px] uppercase tracking-widest text-slate-500">${escapeHtml(label)}${pct != null ? ` · p${pct}` : ''}</span>
    </div>`;
}

function _sparkline(values, color) {
    if (!values || values.length < 2) return '';
    const w = 160, h = 34, pad = 2;
    const min = Math.min(...values), max = Math.max(...values);
    const span = Math.max(1, max - min);
    const pts = values.map((v, i) => {
        const x = pad + i * (w - 2 * pad) / (values.length - 1);
        const y = h - pad - (v - min) * (h - 2 * pad) / span;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
    return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" aria-label="DPM form">
        <polyline points="${pts}" fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round"/>
    </svg>`;
}

const TREND_ARROW = { up: '<span style="color:#34d399">▲</span>', down: '<span style="color:#f87171">▼</span>', flat: '<span class="text-slate-500">▬</span>' };

/** Render the card's inner HTML from the API payload. */
export function renderPlayerCardHTML(card, { live = null } = {}) {
    const color = _tierColor(card.rating && card.rating.tier);
    const f = card.form || {};
    const p = card.percentiles || {};
    const badges = (card.badges || []).map(b =>
        `<span title="${escapeHtml(b.title || '')}" class="text-lg">${escapeHtml(b.emoji || '🏅')}</span>`).join('');
    // Coerce to numbers before interpolation — live objects come from
    // callers, and a stray string here would be an XSS sink (coderabbit).
    const ln = (v) => (Number.isFinite(Number(v)) ? Number(v) : 0);
    const liveRow = live ? `
        <div class="mt-2 pt-2 border-t border-white/10 flex items-center justify-between text-xs">
            <span class="uppercase tracking-widest text-rose-300 font-black text-[10px]">● Live tonight</span>
            <span class="text-slate-200 font-mono">${ln(live.kills)}K/${ln(live.deaths)}D · DPM ${live.dpm != null ? ln(live.dpm) : '—'} ${live.alive === false ? '· <span class="text-slate-500">dead</span>' : ''}</span>
        </div>` : '';
    return `
    <div class="player-card relative overflow-hidden rounded-2xl p-4"
         style="background:linear-gradient(160deg,#0b1220 0%,#0f172a 70%);box-shadow:inset 0 0 0 1.5px ${color}55, 0 18px 50px -18px ${color}44; min-width:280px; max-width:330px">
        <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
                <div class="text-lg font-black text-white truncate">${escapeHtml(card.name || card.guid)}</div>
                <div class="text-[11px] font-bold tracking-wide" style="color:${color}">${escapeHtml(_archetypeLabel(card.archetype))}</div>
            </div>
            <div class="text-right shrink-0">
                <div class="text-3xl font-black leading-none" style="color:${color}">${card.rating && card.rating.value != null ? card.rating.value.toFixed(2) : '—'}</div>
                <div class="text-[9px] uppercase tracking-widest text-slate-500">ET rating ${card.rating && card.rating.trend ? TREND_ARROW[card.rating.trend] || '' : ''}</div>
            </div>
        </div>
        <div class="flex items-center justify-between mt-3">
            ${_ring('DPM', Math.round(f.dpm || 0), p.dpm, color)}
            ${_ring('K/D', (f.kd || 0).toFixed(2), p.kd, color)}
            ${_ring('REV', ((f.revives || 0) / Math.max(f.rounds || 1, 1)).toFixed(1), p.revives, color)}
            ${_ring('ALIVE', `${Math.round(100 - (f.time_dead_pct || 0))}%`, p.survival, color)}
        </div>
        <div class="flex items-end justify-between mt-3 gap-2">
            <div>
                <div class="text-[9px] uppercase tracking-widest text-slate-500 mb-0.5">Form · last ${(card.sparkline_dpm || []).length} sessions (DPM)</div>
                ${_sparkline(card.sparkline_dpm, color)}
            </div>
            <div class="text-right">
                <div class="flex gap-1 justify-end">${badges || '<span class="text-slate-600 text-xs">—</span>'}</div>
                <div class="text-[9px] text-slate-500 mt-1">${(card.career && card.career.kills || 0).toLocaleString()} career kills · ${card.career && card.career.sessions || 0} nights</div>
            </div>
        </div>
        ${liveRow}
        <div class="text-[8px] text-slate-600 mt-2 text-right">last ${card.window_days || 90} days · slomix.fyi</div>
    </div>`;
}

let _overlay = null;
let _openSeq = 0;  // supersede guard: only the latest open may render

function _closeModal() {
    if (_overlay) { _overlay.remove(); _overlay = null; }
    document.removeEventListener('keydown', _escClose);
}

function _escClose(e) { if (e.key === 'Escape') _closeModal(); }

/** Fetch + show the card as a centred modal. `identifier` = guid or name. */
export async function openPlayerCard(identifier, { live = null } = {}) {
    const seq = ++_openSeq;
    _closeModal();
    _overlay = document.createElement('div');
    _overlay.className = 'fixed inset-0 z-50 flex items-center justify-center';
    _overlay.style.background = 'rgba(2,6,23,0.72)';
    _overlay.addEventListener('click', (e) => { if (e.target === _overlay) _closeModal(); });
    document.addEventListener('keydown', _escClose);
    safeInsertHTML(_overlay, 'beforeend',
        '<div class="text-slate-400 text-sm" data-card-slot>Loading card…</div>');
    document.body.appendChild(_overlay);
    try {
        const card = await fetchJSON(
            `${API_BASE}/players/${encodeURIComponent(identifier)}/card`,
            { cachePolicy: 'no-store', credentials: 'same-origin' });
        if (seq !== _openSeq) return;  // a newer card superseded this one
        const slot = _overlay && _overlay.querySelector('[data-card-slot]');
        if (!slot) return;
        slot.textContent = '';
        safeInsertHTML(slot, 'beforeend', renderPlayerCardHTML(card, { live }));
    } catch (e) {
        const slot = _overlay && _overlay.querySelector('[data-card-slot]');
        if (slot) slot.textContent = 'No card for this player.';
        console.warn('player card load failed', e);
    }
}
