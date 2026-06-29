/**
 * Tonight fun-betting panel (VISION_2026 S4 "TEKMA", surfaced on the S7 LIVE hub).
 * Valueless-points parimutuel on the session winner — pure engagement, no money.
 * Wires the existing /api/bets backend (no backend changes) into a self-contained
 * panel that lives in its OWN container (#tonight-betting), separate from the 8s
 * polled #tonight-content, so the stake input never gets wiped mid-typing.
 * Production frontend = legacy JS.
 * @module bets
 */
import { API_BASE, fetchJSON, escapeHtml, safeInsertHTML } from './utils.js';
import { getCurrentUser } from './auth.js';

// Set element content from a template whose user-controlled parts are already
// escapeHtml()'d. Uses the project's safeInsertHTML (insertAdjacentHTML) wrapper
// rather than raw .innerHTML (Codacy-flagged anti-pattern).
function _set(el, html) {
    el.textContent = '';
    safeInsertHTML(el, 'beforeend', html);
}

const BETS_BASE = `${API_BASE}/bets`;
const POLL_MS = 12000;     // own cadence; the static shell is never rebuilt
let _interval = null;
let _marketId = null;
let _wired = false;

const A_COLOR = '#06b6d4';  // Team A — cyan (matches tonight.js)
const B_COLOR = '#8b5cf6';  // Team B — purple

function _viewActive() {
    const v = document.getElementById('view-tonight');
    return v && v.classList.contains('active') && !v.classList.contains('hidden') && !document.hidden;
}

function _stopPolling() {
    if (_interval) { clearInterval(_interval); _interval = null; }
}

// Implied parimutuel multiplier for a side: total_pool / side_pool (what 1 point
// on that side pays if it wins). Guarded against an empty side.
function _mult(total, side) {
    if (!side || side <= 0) return null;
    return total / side;
}

function _shell(host) {
    _set(host, `
        <div class="glass-panel p-5 rounded-xl mb-6" aria-label="Session betting">
            <div class="flex items-center justify-between mb-1">
                <div class="text-xs uppercase tracking-widest text-slate-500 font-bold">🎲 Session bets <span class="text-slate-600 normal-case tracking-normal">· fun points, no money</span></div>
                <div id="bets-wallet" class="text-xs text-slate-400"></div>
            </div>
            <div id="bets-body" class="mt-3 text-sm text-slate-500">Loading…</div>
            <div id="bets-leaderboard" class="mt-4"></div>
        </div>`);
}

function _renderClosed(body, market, outcome) {
    const aWon = outcome === 'team_a';
    const bWon = outcome === 'team_b';
    const tag = (label, won) =>
        `<span class="px-2 py-1 rounded text-xs font-bold ${won ? 'bg-emerald-500/20 text-emerald-300' : 'bg-white/5 text-slate-400'}">${escapeHtml(label)}${won ? ' ✓' : ''}</span>`;
    _set(body, `
        <div class="text-slate-400">Betting is closed for this market.</div>
        <div class="flex gap-2 mt-2">${tag(market.team_a_label || 'Team A', aWon)} ${tag(market.team_b_label || 'Team B', bWon)}</div>
        ${outcome === 'void' ? '<div class="text-xs text-slate-500 mt-2">Voided — stakes refunded.</div>' : ''}`);
}

function _renderOpen(body, market, wallet) {
    const split = market.pool || {};
    const aPool = (split.team_a && split.team_a.pool) || 0;
    const bPool = (split.team_b && split.team_b.pool) || 0;
    const total = split.total_pool || (aPool + bPool);
    const aMult = _mult(total, aPool);
    const bMult = _mult(total, bPool);
    const my = market.my_bet;
    const loggedIn = !!getCurrentUser();

    const sideCard = (key, label, color, pool, mult) => `
        <button type="button" data-bet-side="${key}" ${loggedIn ? '' : 'disabled'}
            class="flex-1 text-left p-3 rounded-lg border transition ${my && my.choice === key ? 'border-white/40 bg-white/10' : 'border-white/10 bg-white/5 hover:bg-white/10'} ${loggedIn ? '' : 'opacity-50 cursor-not-allowed'}">
            <div class="text-sm font-bold" style="color:${color}">${escapeHtml(label)}</div>
            <div class="text-xs text-slate-400 mt-1">${pool} pts · ${mult ? mult.toFixed(2) + '×' : '—'}</div>
        </button>`;

    const myLine = my
        ? `<div class="text-xs text-slate-400 mt-2">Your bet: <span class="font-bold text-white">${my.amount} pts on ${escapeHtml(my.choice === 'team_a' ? (market.team_a_label || 'Team A') : (market.team_b_label || 'Team B'))}</span> · tap a side to change</div>`
        : '';

    const controls = loggedIn ? `
        <div class="flex items-center gap-2 mt-3">
            <input id="bets-stake" type="number" min="1" inputmode="numeric" placeholder="stake"
                value="${my ? my.amount : ''}"
                class="w-24 px-2 py-1.5 rounded-lg bg-black/30 border border-white/10 text-white text-sm" />
            <span class="text-xs text-slate-500">points</span>
            <span id="bets-msg" class="text-xs ml-auto"></span>
        </div>`
        : `<div class="text-xs text-slate-500 mt-3">Log in with Discord to place a fun bet.</div>`;

    _set(body, `
        <div class="text-xs text-slate-500 mb-2">Total pool <span class="text-white font-bold">${total} pts</span> · winners split it proportionally.</div>
        <div class="flex gap-2">
            ${sideCard('team_a', market.team_a_label || 'Team A', A_COLOR, aPool, aMult)}
            ${sideCard('team_b', market.team_b_label || 'Team B', B_COLOR, bPool, bMult)}
        </div>
        ${myLine}
        ${controls}`);

    if (loggedIn) {
        body.querySelectorAll('[data-bet-side]').forEach(btn => {
            btn.addEventListener('click', () => _placeBet(btn.getAttribute('data-bet-side')));
        });
    }
}

async function _placeBet(choice) {
    const stakeEl = document.getElementById('bets-stake');
    const msg = document.getElementById('bets-msg');
    const amount = parseInt(stakeEl && stakeEl.value, 10);
    if (!_marketId) return;
    if (!Number.isFinite(amount) || amount <= 0) {
        if (msg) { msg.textContent = 'Enter a stake'; msg.className = 'text-xs ml-auto text-amber-300'; }
        return;
    }
    if (msg) { msg.textContent = 'Placing…'; msg.className = 'text-xs ml-auto text-slate-400'; }
    try {
        const res = await fetch(`${BETS_BASE}/market/${_marketId}/bet`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin',
            body: JSON.stringify({ choice, amount }),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Bet failed');
        }
        if (msg) { msg.textContent = 'Bet placed!'; msg.className = 'text-xs ml-auto text-emerald-300'; }
        await _loadAndRender();
    } catch (e) {
        // textContent escapes on its own — do NOT escapeHtml here or entities double-escape.
        if (msg) { msg.textContent = e.message || 'Bet failed'; msg.className = 'text-xs ml-auto text-rose-300'; }
    }
}

async function _renderLeaderboard(el) {
    try {
        const data = await fetchJSON(`${BETS_BASE}/leaderboard?limit=5`, { cachePolicy: 'no-store' });
        const players = (data && data.players) || [];
        if (!players.length) { el.textContent = ''; return; }
        _set(el, `
            <div class="text-[11px] uppercase tracking-widest text-slate-500 font-bold mb-2">Points leaders</div>
            <div class="space-y-1">${players.map((p, i) => `
                <div class="flex items-center justify-between text-xs">
                    <span class="text-slate-300">${i + 1}. ${escapeHtml(p.name || 'Player')}</span>
                    <span class="text-slate-400">${p.balance} pts <span class="text-slate-600">(${p.lifetime_earned >= 0 ? '+' : ''}${p.lifetime_earned})</span></span>
                </div>`).join('')}</div>`);
    } catch (_e) {
        el.textContent = '';
    }
}

async function _loadAndRender() {
    const body = document.getElementById('bets-body');
    const walletEl = document.getElementById('bets-wallet');
    const lbEl = document.getElementById('bets-leaderboard');
    if (!body) return;

    let market = null;
    try {
        const data = await fetchJSON(`${BETS_BASE}/market/current`, { cachePolicy: 'no-store', credentials: 'same-origin' });
        market = data && data.market;
    } catch (_e) {
        _set(body, '<div class="text-slate-500">Bets unavailable right now.</div>');
        return;
    }

    if (!market) {
        _set(body, '<div class="text-slate-500">No market open yet — bets open when a session starts.</div>');
        if (walletEl) walletEl.textContent = '';
        if (lbEl) await _renderLeaderboard(lbEl);
        return;
    }
    _marketId = market.id;

    // Wallet (only when logged in).
    if (walletEl) {
        walletEl.textContent = '';
        if (getCurrentUser()) {
            try {
                const w = await fetchJSON(`${BETS_BASE}/wallet`, { cachePolicy: 'no-store', credentials: 'same-origin' });
                walletEl.textContent = `Wallet: ${w.balance} pts`;
            } catch (_e) { /* not logged in / transient */ }
        }
    }

    // Don't clobber a stake the user is actively typing.
    const stakeEl = document.getElementById('bets-stake');
    const typing = stakeEl && document.activeElement === stakeEl;
    if (!typing) {
        if (market.status === 'open' && !market.outcome) {
            _renderOpen(body, market, null);
        } else {
            _renderClosed(body, market, market.outcome);
        }
    }
    if (lbEl) await _renderLeaderboard(lbEl);
}

/** Render the betting panel once and start its own light refresh loop. */
export async function initTonightBetting() {
    const host = document.getElementById('tonight-betting');
    if (!host) return;
    _shell(host);
    await _loadAndRender();
    _stopPolling();
    _interval = setInterval(() => {
        if (!_viewActive()) { _stopPolling(); return; }
        _loadAndRender().catch(e => console.warn('bets refresh failed', e));
    }, POLL_MS);
    if (!_wired) {
        _wired = true;
        document.addEventListener('visibilitychange', () => {
            if (!_viewActive()) _stopPolling();
        });
    }
}
