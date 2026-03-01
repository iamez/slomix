/**
 * Records module - Hall of Fame / Records view
 * @module records
 */

import { API_BASE, fetchJSON, escapeHtml } from './utils.js';

let currentRecordsData = {};
let currentMapFilter = '';

/**
 * Load the records view
 */
export async function loadRecordsView() {
    const container = document.getElementById('records-grid');
    const filterSelect = document.getElementById('records-map-filter');

    if (!container) return;

    // Initialize filter listener if not already set
    if (filterSelect && !filterSelect.dataset.listenerAttached) {
        filterSelect.addEventListener('change', (e) => {
            currentMapFilter = e.target.value;
            fetchAndRenderRecords();
        });
        filterSelect.dataset.listenerAttached = 'true';

        // Load maps for filter
        loadMapFilter(filterSelect);
    }

    await fetchAndRenderRecords();
}

/**
 * Load maps for filter dropdown
 */
async function loadMapFilter(selectElement) {
    try {
        const maps = await fetchJSON(`${API_BASE}/stats/maps`);
        if (maps && Array.isArray(maps)) {
            const currentVal = selectElement.value;
            selectElement.innerHTML = '<option value="">All Maps</option>' +
                maps.map(map => `<option value="${escapeHtml(map)}">${escapeHtml(map)}</option>`).join('');
            selectElement.value = currentVal;
        }
    } catch (e) {
        console.error("Failed to load maps for filter", e);
    }
}

/**
 * Fetch and render records grid
 */
async function fetchAndRenderRecords() {
    const container = document.getElementById('records-grid');

    // Show loading state
    container.innerHTML = `
        <div class="col-span-full text-center py-12">
            <i data-lucide="loader" class="w-8 h-8 animate-spin mx-auto mb-4 text-brand-blue"></i>
            <p class="text-slate-400">Loading Hall of Fame...</p>
        </div>
    `;
    if (typeof lucide !== 'undefined') lucide.createIcons();

    try {
        // Fetch records (limit 5 for modal data)
        const url = `${API_BASE}/stats/records?limit=5${currentMapFilter ? `&map_name=${currentMapFilter}` : ''}`;
        const data = await fetchJSON(url);
        currentRecordsData = data; // Store for modal usage

        container.innerHTML = '';

        if (Object.keys(data).length === 0) {
            container.innerHTML = '<div class="col-span-full text-center text-slate-500 py-12">No records found for this selection.</div>';
            return;
        }

        // Define category order and styling
        const categories = [
            { key: 'kills', icon: 'skull', color: 'text-brand-rose', bg: 'bg-brand-rose/10', border: 'border-brand-rose/20' },
            { key: 'damage', icon: 'zap', color: 'text-brand-blue', bg: 'bg-brand-blue/10', border: 'border-brand-blue/20' },
            { key: 'xp', icon: 'star', color: 'text-brand-gold', bg: 'bg-brand-gold/10', border: 'border-brand-gold/20' },
            { key: 'headshots', icon: 'crosshair', color: 'text-brand-purple', bg: 'bg-brand-purple/10', border: 'border-brand-purple/20' },
            { key: 'accuracy', icon: 'target', color: 'text-brand-emerald', bg: 'bg-brand-emerald/10', border: 'border-brand-emerald/20' },
            { key: 'revives', icon: 'heart', color: 'text-brand-cyan', bg: 'bg-brand-cyan/10', border: 'border-brand-cyan/20' },
            { key: 'gibs', icon: 'bomb', color: 'text-orange-500', bg: 'bg-orange-500/10', border: 'border-orange-500/20' },
            { key: 'dyna_planted', icon: 'flame', color: 'text-red-500', bg: 'bg-red-500/10', border: 'border-red-500/20' },
            { key: 'dyna_defused', icon: 'shield', color: 'text-blue-400', bg: 'bg-blue-400/10', border: 'border-blue-400/20' },
            { key: 'obj_stolen', icon: 'flag', color: 'text-yellow-400', bg: 'bg-yellow-400/10', border: 'border-yellow-400/20' },
            { key: 'obj_returned', icon: 'check-circle', color: 'text-green-400', bg: 'bg-green-400/10', border: 'border-green-400/20' },
            { key: 'useful_kills', icon: 'swords', color: 'text-indigo-400', bg: 'bg-indigo-400/10', border: 'border-indigo-400/20' }
        ];

        categories.forEach(cat => {
            const recordList = data[cat.key];
            if (!recordList || recordList.length === 0) return;

            const topRecord = recordList[0];
            const value = formatRecordValue(topRecord.value);
            const safePlayer = escapeHtml(topRecord.player);
            const safePlayerInitials = escapeHtml(topRecord.player.substring(0, 2).toUpperCase());
            const safeMap = escapeHtml(topRecord.map);

            const html = `
                <div class="glass-card p-6 rounded-xl hover:bg-white/5 transition group relative overflow-hidden cursor-pointer border border-white/5 hover:border-white/10"
                     onclick="openRecordModal('${cat.key}')">
                    <div class="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition transform group-hover:scale-110 duration-500">
                        <i data-lucide="${cat.icon}" class="w-16 h-16 ${cat.color}"></i>
                    </div>

                    <div class="flex items-center gap-3 mb-4">
                        <div class="w-10 h-10 rounded-lg ${cat.bg} ${cat.border} border flex items-center justify-center">
                            <i data-lucide="${cat.icon}" class="w-5 h-5 ${cat.color}"></i>
                        </div>
                        <div class="text-sm font-bold text-slate-400 uppercase tracking-wider">${cat.key.replace('_', ' ')}</div>
                    </div>

                    <div class="mb-4">
                        <div class="text-4xl font-black text-white mb-1 tracking-tight">${value}</div>
                        <div class="text-xs text-slate-500 font-mono flex items-center gap-2">
                            <span class="bg-slate-800 px-1.5 py-0.5 rounded text-slate-400">${safeMap}</span>
                            <span>${new Date(topRecord.date).toLocaleDateString()}</span>
                        </div>
                    </div>

                    <div class="flex items-center justify-between pt-4 border-t border-white/5">
                        <div class="flex items-center gap-4">
                            <div class="w-8 h-8 rounded bg-slate-800 flex items-center justify-center text-xs font-bold text-slate-400">
                                ${safePlayerInitials}
                            </div>
                            <div class="font-bold text-white group-hover:text-brand-blue transition">
                                ${safePlayer}
                            </div>
                        </div>
                        <div class="text-xs text-brand-blue font-medium opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
                            View Top 5 <i data-lucide="arrow-right" class="w-3 h-3"></i>
                        </div>
                    </div>
                </div>
            `;
            container.insertAdjacentHTML('beforeend', html);
        });

        if (typeof lucide !== 'undefined') lucide.createIcons();

    } catch (e) {
        console.error('Failed to load records:', e);
        container.innerHTML = '<div class="col-span-full text-center text-red-500 py-12">Failed to load records.</div>';
    }
}

/**
 * Format record value for display
 */
function formatRecordValue(val) {
    return typeof val === 'number' && !Number.isInteger(val)
        ? val.toFixed(2)
        : Math.round(val);
}

/**
 * Open record details modal
 */
export function openRecordModal(categoryKey) {
    const modal = document.getElementById('record-modal');
    const titleEl = document.getElementById('modal-title');
    const contentEl = document.getElementById('modal-content');

    if (!modal || !currentRecordsData[categoryKey]) return;

    const records = currentRecordsData[categoryKey];
    const catName = escapeHtml(categoryKey.replace('_', ' ').toUpperCase());

    // Set Title
    titleEl.innerHTML = `<span>${catName}</span> <span class="text-slate-500 text-sm font-normal ml-2">Top 5 All-Time</span>`;

    // Build Content
    contentEl.innerHTML = records.map((rec, index) => {
        const isFirst = index === 0;
        const rankColor = isFirst ? 'text-brand-gold' : 'text-slate-400';
        const bgClass = isFirst ? 'bg-brand-gold/10 border-brand-gold/20' : 'bg-slate-800/50 border-white/5';
        const safePlayer = escapeHtml(rec.player);
        const safeMap = escapeHtml(rec.map);

        return `
            <div class="flex items-center justify-between p-3 rounded-lg border ${bgClass} hover:bg-white/5 transition">
                <div class="flex items-center gap-4">
                    <div class="font-mono font-bold text-lg w-6 text-center ${rankColor}">#${index + 1}</div>
                    <div class="flex flex-col">
                        <span class="font-bold text-white ${isFirst ? 'text-lg' : ''}">${safePlayer}</span>
                        <span class="text-xs text-slate-500 font-mono">${safeMap} • ${new Date(rec.date).toLocaleDateString()}</span>
                    </div>
                </div>
                <div class="font-black text-white ${isFirst ? 'text-2xl' : 'text-xl'}">
                    ${formatRecordValue(rec.value)}
                </div>
            </div>
        `;
    }).join('');

    modal.classList.remove('hidden');
}

/**
 * Close record modal
 */
export function closeRecordModal() {
    const modal = document.getElementById('record-modal');
    if (modal) modal.classList.add('hidden');
}

// Expose to window for onclick handlers in HTML
window.loadRecordsView = loadRecordsView;
window.openRecordModal = openRecordModal;
window.closeRecordModal = closeRecordModal;
