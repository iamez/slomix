/**
 * Reusable UI Component System for Slomix ET:Legacy
 * Returns HTML strings consistent with the dark glass-panel theme.
 * @module components
 */

import { escapeHtml } from './utils.js';

// ============================================================================
// PAGE HEADER
// ============================================================================

/**
 * Consistent page header with title and optional subtitle.
 * @param {string} title - Page title (user content, will be escaped)
 * @param {string} [subtitle] - Optional subtitle text
 * @returns {string} HTML string
 */
export function PageHeader(title, subtitle) {
    return `
        <div class="mb-8">
            <h1 class="text-2xl md:text-3xl font-black text-white tracking-tight">${escapeHtml(title)}</h1>
            ${subtitle ? `<p class="text-sm text-slate-400 mt-1.5">${escapeHtml(subtitle)}</p>` : ''}
        </div>`;
}

// ============================================================================
// KPI TILE
// ============================================================================

/**
 * Stat tile with monospace value, label, optional sub-text and accent color.
 * @param {object} opts
 * @param {string} opts.label - Stat label (escaped)
 * @param {string|number} opts.value - Main value displayed in mono
 * @param {string} [opts.sub] - Sub-text below value
 * @param {string} [opts.icon] - SVG string for the icon
 * @param {string} [opts.accent='blue'] - Brand accent: blue|cyan|purple|emerald|rose|amber|gold
 * @returns {string} HTML string
 */
export function KpiTile({ label, value, sub, icon, accent = 'blue' }) {
    const accentColor = `brand-${accent}`;
    return `
        <div class="glass-panel rounded-xl p-4 group hover:border-${accentColor}/30 transition-colors">
            <div class="flex items-center justify-between mb-2">
                <span class="text-[10px] uppercase tracking-widest text-slate-600 font-bold">${escapeHtml(label)}</span>
                ${icon ? `<span class="text-${accentColor}/60 group-hover:text-${accentColor} transition-colors">${icon}</span>` : ''}
            </div>
            <div class="text-xl font-bold font-mono text-white">${escapeHtml(String(value))}</div>
            ${sub ? `<div class="text-[11px] text-slate-500 mt-1">${escapeHtml(sub)}</div>` : ''}
        </div>`;
}

// ============================================================================
// CHART CARD
// ============================================================================

/**
 * Wrapper card for a Chart.js canvas.
 * @param {string} title - Card title
 * @param {string} chartId - DOM id for the <canvas>
 * @param {string} [subtitle] - Optional subtitle
 * @returns {string} HTML string
 */
export function ChartCard(title, chartId, subtitle) {
    return `
        <div class="glass-card rounded-xl p-5">
            <div class="mb-4">
                <h3 class="text-sm font-bold text-white">${escapeHtml(title)}</h3>
                ${subtitle ? `<p class="text-[11px] text-slate-500 mt-0.5">${escapeHtml(subtitle)}</p>` : ''}
            </div>
            <div class="chart-container">
                <canvas id="${escapeHtml(chartId)}"></canvas>
            </div>
        </div>`;
}

// ============================================================================
// TABLE CARD
// ============================================================================

/**
 * Data table inside a glass card.
 * @param {object} opts
 * @param {string} opts.title - Table title
 * @param {Array<{label: string, key: string, align?: string, mono?: boolean}>} opts.columns
 * @param {Array<object>} opts.rows - Row data objects keyed by column.key
 * @param {string} [opts.emptyText='No data available'] - Message when rows is empty
 * @returns {string} HTML string
 */
export function TableCard({ title, columns, rows, emptyText = 'No data available' }) {
    if (!rows || rows.length === 0) {
        return `
            <div class="glass-card rounded-xl p-5">
                <h3 class="text-sm font-bold text-white mb-4">${escapeHtml(title)}</h3>
                ${EmptyState(emptyText)}
            </div>`;
    }

    const headerCells = columns.map(col => {
        const align = col.align === 'right' ? 'text-right' : 'text-left';
        return `<th class="px-4 py-3 ${align} text-[10px] uppercase tracking-widest text-slate-600 font-bold">${escapeHtml(col.label)}</th>`;
    }).join('');

    const bodyRows = rows.map(row => {
        const cells = columns.map(col => {
            const align = col.align === 'right' ? 'text-right' : 'text-left';
            const mono = col.mono ? 'font-mono' : '';
            const val = row[col.key] != null ? row[col.key] : '';
            return `<td class="px-4 py-3 text-sm ${align} ${mono} text-slate-300">${escapeHtml(String(val))}</td>`;
        }).join('');
        return `<tr class="hover:bg-white/5 transition border-b border-white/5 last:border-0">${cells}</tr>`;
    }).join('');

    return `
        <div class="glass-card rounded-xl overflow-hidden">
            <div class="px-5 pt-5 pb-3">
                <h3 class="text-sm font-bold text-white">${escapeHtml(title)}</h3>
            </div>
            <div class="overflow-x-auto">
                <table class="w-full">
                    <thead><tr class="border-b border-white/5">${headerCells}</tr></thead>
                    <tbody>${bodyRows}</tbody>
                </table>
            </div>
        </div>`;
}

// ============================================================================
// PODIUM CARD
// ============================================================================

const PODIUM_STYLES = {
    1: { border: 'border-brand-gold/40', bg: 'bg-brand-gold/10', text: 'text-brand-gold', label: '1st', icon: `<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M5 16L3 5l5.5 5L12 4l3.5 6L21 5l-2 11H5zm14 3c0 .6-.4 1-1 1H6c-.6 0-1-.4-1-1v-1h14v1z"/></svg>` },
    2: { border: 'border-slate-400/40', bg: 'bg-slate-400/10', text: 'text-slate-300', label: '2nd', icon: '' },
    3: { border: 'border-amber-700/40', bg: 'bg-amber-700/10', text: 'text-amber-600', label: '3rd', icon: '' },
};

/**
 * Podium card with gold/silver/bronze styling.
 * @param {object} opts
 * @param {number} opts.rank - 1, 2, or 3
 * @param {string} opts.name - Player name (escaped)
 * @param {string|number} opts.value - Stat value
 * @param {string} [opts.unit] - Unit label (e.g. "kills", "DPM")
 * @returns {string} HTML string
 */
export function PodiumCard({ rank, name, value, unit }) {
    const style = PODIUM_STYLES[rank] || { border: 'border-white/10', bg: 'bg-white/5', text: 'text-slate-400', label: `#${rank}`, icon: '' };
    return `
        <div class="glass-panel rounded-xl p-5 ${style.border} ${style.bg} text-center">
            <div class="flex items-center justify-center gap-1.5 mb-3">
                ${style.icon ? `<span class="${style.text}">${style.icon}</span>` : ''}
                <span class="text-xs font-bold ${style.text} uppercase tracking-wider">${style.label}</span>
            </div>
            <div class="text-base font-bold text-white mb-1 truncate">${escapeHtml(name)}</div>
            <div class="text-2xl font-black font-mono ${style.text}">${escapeHtml(String(value))}</div>
            ${unit ? `<div class="text-[10px] text-slate-500 uppercase tracking-widest mt-1">${escapeHtml(unit)}</div>` : ''}
        </div>`;
}

// ============================================================================
// EXPANDABLE LIST
// ============================================================================

/**
 * List that shows a limited number of items with a "show more" toggle.
 * @param {object} opts
 * @param {string[]} opts.items - Array of HTML-safe display strings (pre-escaped by caller or plain text)
 * @param {number} [opts.limit=5] - Items visible before expand
 * @param {boolean} [opts.escapeItems=true] - Whether to escape items (set false if pre-escaped)
 * @returns {string} HTML string
 */
export function ExpandableList({ items, limit = 5, escapeItems = true }) {
    if (!items || items.length === 0) return EmptyState('No items');

    const id = 'expand-' + Math.random().toString(36).slice(2, 9);
    const visible = items.slice(0, limit);
    const hidden = items.slice(limit);
    const esc = escapeItems ? escapeHtml : (s) => s;

    let html = `<ul class="space-y-1">`;
    visible.forEach(item => {
        html += `<li class="text-sm text-slate-300 py-1 border-b border-white/5 last:border-0">${esc(item)}</li>`;
    });
    if (hidden.length > 0) {
        hidden.forEach(item => {
            html += `<li class="text-sm text-slate-300 py-1 border-b border-white/5 last:border-0 hidden" data-expand-group="${id}">${esc(item)}</li>`;
        });
        html += `</ul>`;
        html += `<button onclick="document.querySelectorAll('[data-expand-group=\\'${id}\\']').forEach(el=>el.classList.remove('hidden'));this.remove();"
            class="mt-2 text-xs font-bold text-brand-cyan hover:text-white transition cursor-pointer">
            Show ${hidden.length} more
        </button>`;
    } else {
        html += `</ul>`;
    }
    return html;
}

// ============================================================================
// EMPTY STATE
// ============================================================================

/**
 * Empty-state placeholder with optional icon.
 * @param {string} [message='No data available'] - Message to display
 * @param {string} [icon] - Optional SVG string for icon
 * @returns {string} HTML string
 */
export function EmptyState(message = 'No data available', icon) {
    const defaultIcon = `<svg class="w-8 h-8 text-slate-600" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5m6 4.125l2.25 2.25m0 0l2.25 2.25M12 13.875l2.25-2.25M12 13.875l-2.25 2.25M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z"/></svg>`;
    return `
        <div class="py-10 text-center">
            <div class="w-16 h-16 mx-auto mb-4 rounded-2xl bg-slate-800/80 flex items-center justify-center">
                ${icon || defaultIcon}
            </div>
            <p class="text-sm text-slate-500">${escapeHtml(message)}</p>
        </div>`;
}

// ============================================================================
// LOADING SKELETON
// ============================================================================

/**
 * Loading skeleton placeholders.
 * @param {string} [type='card'] - Skeleton type: 'card' | 'table' | 'kpi' | 'chart'
 * @param {number} [count=1] - Number of skeleton items
 * @returns {string} HTML string
 */
export function LoadingSkeleton(type = 'card', count = 1) {
    const skeletons = {
        card: (i) => `
            <div class="glass-card rounded-xl p-5 flex flex-col gap-3" style="animation: pulse 1.5s ease-in-out infinite; animation-delay: ${i * 0.1}s;">
                <div class="flex items-start justify-between gap-3">
                    <div class="flex items-center gap-3 min-w-0 flex-1">
                        <div class="w-10 h-10 rounded-lg bg-slate-700/50 shrink-0"></div>
                        <div class="flex-1 space-y-2">
                            <div class="h-4 bg-slate-700/50 rounded w-3/4"></div>
                            <div class="h-3 bg-slate-700/30 rounded w-1/2"></div>
                        </div>
                    </div>
                    <div class="w-14 h-5 bg-slate-700/40 rounded-full"></div>
                </div>
                <div class="flex justify-between">
                    <div class="h-3 bg-slate-700/30 rounded w-20"></div>
                    <div class="h-3 bg-slate-700/30 rounded w-16"></div>
                </div>
            </div>`,

        table: () => `
            <div class="glass-card rounded-xl overflow-hidden" style="animation: pulse 1.5s ease-in-out infinite;">
                <div class="px-5 pt-5 pb-3"><div class="h-4 bg-slate-700/50 rounded w-1/4"></div></div>
                <div class="px-5 space-y-3 pb-5">
                    ${Array(5).fill(0).map(() => `
                        <div class="flex justify-between items-center py-2 border-b border-white/5">
                            <div class="h-3 bg-slate-700/30 rounded w-1/3"></div>
                            <div class="h-3 bg-slate-700/30 rounded w-16"></div>
                        </div>`).join('')}
                </div>
            </div>`,

        kpi: (i) => `
            <div class="glass-panel rounded-xl p-4" style="animation: pulse 1.5s ease-in-out infinite; animation-delay: ${i * 0.1}s;">
                <div class="h-3 bg-slate-700/40 rounded w-16 mb-3"></div>
                <div class="h-6 bg-slate-700/50 rounded w-20 mb-2"></div>
                <div class="h-2.5 bg-slate-700/30 rounded w-12"></div>
            </div>`,

        chart: () => `
            <div class="glass-card rounded-xl p-5" style="animation: pulse 1.5s ease-in-out infinite;">
                <div class="h-4 bg-slate-700/50 rounded w-1/4 mb-4"></div>
                <div class="h-[300px] bg-slate-800/30 rounded-lg flex items-end justify-around p-4 gap-2">
                    ${Array(8).fill(0).map(() => {
                        const h = 20 + Math.floor(Math.random() * 60);
                        return `<div class="flex-1 bg-slate-700/30 rounded-t" style="height: ${h}%;"></div>`;
                    }).join('')}
                </div>
            </div>`,
    };

    const renderer = skeletons[type] || skeletons.card;
    return Array(count).fill(0).map((_, i) => renderer(i)).join('');
}
