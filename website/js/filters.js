/**
 * Shared Filter System for Slomix ET:Legacy
 * URL-synced filter bar with period/season/date-range support.
 * @module filters
 */

import { escapeHtml } from './utils.js';

// ============================================================================
// FILTER STATE
// ============================================================================

const DEFAULT_STATE = {
    period: 'all',       // 'all' | 'season' | '7d' | '14d' | '30d' | '90d' | 'custom'
    season: '',          // season id string, empty = current/all
    dateFrom: '',        // ISO date string for custom range
    dateTo: '',          // ISO date string for custom range
};

let _state = { ...DEFAULT_STATE };
const _listeners = [];

// ============================================================================
// PERIOD OPTIONS
// ============================================================================

const PERIOD_OPTIONS = [
    { value: 'all', label: 'All Time' },
    { value: 'season', label: 'Current Season' },
    { value: '7d', label: 'Last 7d' },
    { value: '14d', label: 'Last 14d' },
    { value: '30d', label: 'Last 30d' },
    { value: '90d', label: 'Last 90d' },
    { value: 'custom', label: 'Custom Range' },
];

// ============================================================================
// URL SYNC
// ============================================================================

/**
 * Read filter state from current URL query params.
 */
function readFromURL() {
    const params = new URLSearchParams(window.location.search);
    const period = params.get('period');
    const season = params.get('season');
    const dateFrom = params.get('from');
    const dateTo = params.get('to');

    if (period && PERIOD_OPTIONS.some(o => o.value === period)) {
        _state.period = period;
    }
    if (season) _state.season = season;
    if (dateFrom) _state.dateFrom = dateFrom;
    if (dateTo) _state.dateTo = dateTo;
}

/**
 * Write current filter state to URL query params (replaceState, no reload).
 */
function writeToURL() {
    const params = new URLSearchParams(window.location.search);

    if (_state.period && _state.period !== 'all') {
        params.set('period', _state.period);
    } else {
        params.delete('period');
    }

    if (_state.season) {
        params.set('season', _state.season);
    } else {
        params.delete('season');
    }

    if (_state.period === 'custom' && _state.dateFrom) {
        params.set('from', _state.dateFrom);
    } else {
        params.delete('from');
    }

    if (_state.period === 'custom' && _state.dateTo) {
        params.set('to', _state.dateTo);
    } else {
        params.delete('to');
    }

    const qs = params.toString();
    const newUrl = window.location.pathname + (qs ? '?' + qs : '') + window.location.hash;
    window.history.replaceState(null, '', newUrl);
}

// ============================================================================
// PUBLIC API
// ============================================================================

/**
 * Get current filter state (immutable copy).
 * @returns {{period: string, season: string, dateFrom: string, dateTo: string}}
 */
export function getFilterState() {
    return { ..._state };
}

/**
 * Update filter state, sync to URL, and notify listeners.
 * @param {Partial<typeof DEFAULT_STATE>} updates
 */
export function setFilterState(updates) {
    Object.assign(_state, updates);
    writeToURL();
    _notifyListeners();
}

/**
 * Register a callback for filter changes.
 * @param {function} callback - Called with the new filter state
 * @returns {function} Unsubscribe function
 */
export function onFilterChange(callback) {
    _listeners.push(callback);
    return () => {
        const idx = _listeners.indexOf(callback);
        if (idx >= 0) _listeners.splice(idx, 1);
    };
}

function _notifyListeners() {
    const state = getFilterState();
    _listeners.forEach(fn => {
        try { fn(state); } catch (e) { console.error('Filter listener error:', e); }
    });
}

// ============================================================================
// FILTER BAR RENDERING
// ============================================================================

/**
 * Render a filter bar into a container element and wire up events.
 * @param {string} containerId - DOM id of the container element
 * @param {object} [options]
 * @param {boolean} [options.showSeason=true] - Show season selector
 * @param {Array<{value: string, label: string}>} [options.seasons] - Available seasons
 * @param {string[]} [options.periods] - Subset of period values to show (default: all)
 */
export function renderFilterBar(containerId, options = {}) {
    const container = document.getElementById(containerId);
    if (!container) return;

    // Hydrate state from URL on first render
    readFromURL();

    container.innerHTML = GlobalFilterBar(options);
    wireFilterEvents(containerId, options);
}

/**
 * Generate filter bar HTML string.
 * @param {object} [options]
 * @param {boolean} [options.showSeason=true]
 * @param {Array<{value: string, label: string}>} [options.seasons]
 * @param {string[]} [options.periods]
 * @returns {string} HTML string
 */
export function GlobalFilterBar(options = {}) {
    const { showSeason = true, seasons = [], periods } = options;

    const activePeriods = periods
        ? PERIOD_OPTIONS.filter(o => periods.includes(o.value))
        : PERIOD_OPTIONS;

    // Period pills
    const periodPills = activePeriods.map(opt => {
        const isActive = _state.period === opt.value;
        const activeClass = isActive
            ? 'bg-brand-blue/20 text-brand-blue border-brand-blue/30'
            : 'text-slate-500 border-white/5 hover:text-white hover:border-white/10';
        return `<button data-filter-period="${escapeHtml(opt.value)}"
            class="px-3 py-1.5 rounded-lg text-xs font-bold border transition-all ${activeClass}">
            ${escapeHtml(opt.label)}
        </button>`;
    }).join('');

    // Season dropdown (optional)
    let seasonHtml = '';
    if (showSeason && seasons.length > 0) {
        const seasonOptions = seasons.map(s => {
            const selected = _state.season === String(s.value) ? 'selected' : '';
            return `<option value="${escapeHtml(String(s.value))}" ${selected}>${escapeHtml(s.label)}</option>`;
        }).join('');
        seasonHtml = `
            <select data-filter-season
                class="bg-slate-900/50 border border-white/5 rounded-lg px-3 py-1.5 text-xs font-bold text-slate-300 outline-none focus:border-brand-cyan/30 transition cursor-pointer">
                <option value="">All Seasons</option>
                ${seasonOptions}
            </select>`;
    }

    // Custom date range (shown only when period=custom)
    const customVisible = _state.period === 'custom' ? '' : 'hidden';
    const dateRangeHtml = `
        <div data-filter-daterange class="flex items-center gap-2 ${customVisible}">
            <input type="date" data-filter-from value="${escapeHtml(_state.dateFrom)}"
                class="bg-slate-900/50 border border-white/5 rounded-lg px-3 py-1.5 text-xs text-slate-300 font-mono outline-none focus:border-brand-purple/30 transition">
            <span class="text-slate-600 text-xs">to</span>
            <input type="date" data-filter-to value="${escapeHtml(_state.dateTo)}"
                class="bg-slate-900/50 border border-white/5 rounded-lg px-3 py-1.5 text-xs text-slate-300 font-mono outline-none focus:border-brand-purple/30 transition">
        </div>`;

    return `
        <div class="glass-panel rounded-xl px-4 py-3 flex flex-wrap items-center gap-3">
            <div class="flex flex-wrap items-center gap-1.5">
                ${periodPills}
            </div>
            ${seasonHtml}
            ${dateRangeHtml}
        </div>`;
}

/**
 * Wire interactive events for a rendered filter bar.
 * Call this after inserting GlobalFilterBar HTML into the DOM.
 * @param {string} containerId - Container DOM id
 * @param {object} [options] - Same options passed to GlobalFilterBar
 */
export function wireFilterEvents(containerId, options = {}) {
    const container = document.getElementById(containerId);
    if (!container) return;

    // Period buttons
    container.querySelectorAll('[data-filter-period]').forEach(btn => {
        btn.addEventListener('click', () => {
            const newPeriod = btn.dataset.filterPeriod;
            _state.period = newPeriod;

            // Toggle custom date range visibility
            const dateRange = container.querySelector('[data-filter-daterange]');
            if (dateRange) {
                dateRange.classList.toggle('hidden', newPeriod !== 'custom');
            }

            // Update active pill styling
            container.querySelectorAll('[data-filter-period]').forEach(b => {
                const isActive = b.dataset.filterPeriod === newPeriod;
                b.classList.toggle('bg-brand-blue/20', isActive);
                b.classList.toggle('text-brand-blue', isActive);
                b.classList.toggle('border-brand-blue/30', isActive);
                b.classList.toggle('text-slate-500', !isActive);
                b.classList.toggle('border-white/5', !isActive);
            });

            writeToURL();
            _notifyListeners();
        });
    });

    // Season dropdown
    const seasonSelect = container.querySelector('[data-filter-season]');
    if (seasonSelect) {
        seasonSelect.addEventListener('change', () => {
            _state.season = seasonSelect.value;
            writeToURL();
            _notifyListeners();
        });
    }

    // Date range inputs
    const fromInput = container.querySelector('[data-filter-from]');
    const toInput = container.querySelector('[data-filter-to]');

    if (fromInput) {
        fromInput.addEventListener('change', () => {
            _state.dateFrom = fromInput.value;
            writeToURL();
            _notifyListeners();
        });
    }
    if (toInput) {
        toInput.addEventListener('change', () => {
            _state.dateTo = toInput.value;
            writeToURL();
            _notifyListeners();
        });
    }
}

// Initialize state from URL on module load
readFromURL();
