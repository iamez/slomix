/**
 * Player comparison module
 * @module compare
 */

import { API_BASE, fetchJSON, escapeHtml } from './utils.js';

/**
 * Open the compare modal with a pre-filled player name
 */
export function openCompareModal(playerName = '') {
    const modal = document.getElementById('modal-player-compare');
    const player1Input = document.getElementById('compare-player1');
    const player2Input = document.getElementById('compare-player2');
    const resultsDiv = document.getElementById('compare-results');

    if (modal) {
        modal.classList.remove('hidden');
    }

    // Pre-fill player 1 with the provided name
    if (player1Input && playerName) {
        player1Input.value = playerName;
    }

    // Clear player 2 and results
    if (player2Input) {
        player2Input.value = '';
        player2Input.focus();
    }
    if (resultsDiv) {
        resultsDiv.innerHTML = '';
    }
}

/**
 * Compare two players and display results
 */
export async function comparePlayers() {
    const player1Name = document.getElementById('compare-player1')?.value.trim();
    const player2Name = document.getElementById('compare-player2')?.value.trim();
    const resultsDiv = document.getElementById('compare-results');

    if (!player1Name || !player2Name) {
        if (resultsDiv) resultsDiv.innerHTML = '<div class="text-center text-red-500 py-4">Please enter both player names</div>';
        return;
    }

    if (resultsDiv) {
        resultsDiv.innerHTML = '<div class="text-center py-12"><i data-lucide="loader" class="w-8 h-8 text-brand-purple animate-spin mx-auto mb-4"></i><div class="text-slate-400">Comparing players...</div></div>';
        if (typeof lucide !== 'undefined') lucide.createIcons();
    }

    try {
        const [player1, player2] = await Promise.all([
            fetchJSON(`${API_BASE}/stats/player/${encodeURIComponent(player1Name)}`),
            fetchJSON(`${API_BASE}/stats/player/${encodeURIComponent(player2Name)}`)
        ]);

        const stats1 = player1.stats;
        const stats2 = player2.stats;

        const comparisons = [
            { label: 'K/D Ratio', val1: stats1.kd, val2: stats2.kd, higherIsBetter: true, format: (v) => v.toFixed(2) },
            { label: 'DPM', val1: stats1.dpm, val2: stats2.dpm, higherIsBetter: true },
            { label: 'Total Kills', val1: stats1.kills, val2: stats2.kills, higherIsBetter: true },
            { label: 'Win Rate', val1: stats1.win_rate, val2: stats2.win_rate, higherIsBetter: true, format: (v) => v + '%' },
            { label: 'Games Played', val1: stats1.games, val2: stats2.games, higherIsBetter: true },
            { label: 'Playtime', val1: stats1.playtime_hours, val2: stats2.playtime_hours, higherIsBetter: false, format: (v) => v + 'h' },
        ];

        let html = `
            <div class="glass-panel p-6 rounded-xl">
                <div class="grid grid-cols-3 gap-4 mb-6 text-center">
                    <div>
                        <div class="w-16 h-16 rounded-full bg-brand-blue/20 flex items-center justify-center text-2xl font-black text-brand-blue mx-auto mb-2">
                            ${escapeHtml(player1Name.substring(0, 2).toUpperCase())}
                        </div>
                        <div class="font-bold text-white">${escapeHtml(player1Name)}</div>
                    </div>
                    <div class="flex items-center justify-center">
                        <div class="text-3xl font-black text-slate-600">VS</div>
                    </div>
                    <div>
                        <div class="w-16 h-16 rounded-full bg-brand-rose/20 flex items-center justify-center text-2xl font-black text-brand-rose mx-auto mb-2">
                            ${escapeHtml(player2Name.substring(0, 2).toUpperCase())}
                        </div>
                        <div class="font-bold text-white">${escapeHtml(player2Name)}</div>
                    </div>
                </div>

                <div class="space-y-4">
        `;

        comparisons.forEach(comp => {
            const formatFn = comp.format || ((v) => v);
            const winner1 = comp.higherIsBetter ? comp.val1 > comp.val2 : comp.val1 < comp.val2;
            const winner2 = comp.higherIsBetter ? comp.val2 > comp.val1 : comp.val2 < comp.val1;

            html += `
                <div class="glass-card p-4 rounded-lg">
                    <div class="grid grid-cols-3 gap-4 items-center">
                        <div class="text-right">
                            <span class="text-xl font-bold ${winner1 ? 'text-brand-emerald' : 'text-slate-400'}">${formatFn(comp.val1)}</span>
                            ${winner1 ? '<span class="ml-2">🏆</span>' : ''}
                        </div>
                        <div class="text-center text-sm text-slate-500 uppercase font-bold">${comp.label}</div>
                        <div class="text-left">
                            ${winner2 ? '<span class="mr-2">🏆</span>' : ''}
                            <span class="text-xl font-bold ${winner2 ? 'text-brand-emerald' : 'text-slate-400'}">${formatFn(comp.val2)}</span>
                        </div>
                    </div>
                </div>
            `;
        });

        html += `
                </div>
            </div>
        `;

        if (resultsDiv) resultsDiv.innerHTML = html;
        if (typeof lucide !== 'undefined') lucide.createIcons();

    } catch (e) {
        console.error('Failed to compare players:', e);
        if (resultsDiv) resultsDiv.innerHTML = '<div class="text-center text-red-500 py-4">Failed to compare players. Make sure both names are correct.</div>';
    }
}

// Expose to window for onclick handlers in HTML
window.openCompareModal = openCompareModal;
window.comparePlayers = comparePlayers;
