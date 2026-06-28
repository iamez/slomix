/**
 * Slomix Wrapped (VISION_2026 S6 SPOMIN) — a shareable season card rendered to a
 * 1080×1920 canvas with copy-image / download. First reusable share-card infra.
 * @module wrapped
 */
import { API_BASE, fetchJSON, safeInsertHTML } from './utils.js';

const W = 1080;
const H = 1920;

function _overlay() {
    let el = document.getElementById('wrapped-overlay');
    if (el) return el;
    el = document.createElement('div');
    el.id = 'wrapped-overlay';
    el.className = 'fixed inset-0 z-[100] hidden items-center justify-center bg-black/80 p-4 overflow-auto';
    document.body.appendChild(el);
    return el;
}

export async function openWrapped(guid) {
    if (!guid) return;
    const overlay = _overlay();
    overlay.textContent = '';
    overlay.classList.remove('hidden');
    overlay.classList.add('flex');
    safeInsertHTML(overlay, 'beforeend', `
        <div class="max-w-md w-full text-center" role="dialog" aria-modal="true" aria-label="Slomix Wrapped">
            <div class="text-slate-400 text-sm mb-3">Generating your Slomix Wrapped…</div>
            <canvas id="wrapped-canvas" class="w-full rounded-xl shadow-2xl" style="max-height:80vh;"></canvas>
            <div class="flex justify-center gap-2 mt-4">
                <button id="wrapped-copy" class="px-4 py-2 rounded-lg text-sm font-bold bg-brand-cyan/20 text-brand-cyan hover:bg-brand-cyan/30">Copy image</button>
                <button id="wrapped-download" class="px-4 py-2 rounded-lg text-sm font-bold bg-white/10 text-slate-200 hover:bg-white/20">Download</button>
                <button id="wrapped-close" class="px-4 py-2 rounded-lg text-sm font-bold bg-white/5 text-slate-400 hover:bg-white/10">Close</button>
            </div>
            <div id="wrapped-status" class="text-xs text-slate-500 mt-2"></div>
        </div>`);

    // Close via button, Escape, or backdrop click — with listener cleanup.
    const onKey = (e) => { if (e.key === 'Escape') closeWrapped(); };
    function closeWrapped() {
        overlay.classList.add('hidden');
        overlay.classList.remove('flex');
        document.removeEventListener('keydown', onKey);
        overlay.removeEventListener('click', onBackdrop);
    }
    const onBackdrop = (e) => { if (e.target === overlay) closeWrapped(); };
    overlay.querySelector('#wrapped-close').addEventListener('click', closeWrapped);
    document.addEventListener('keydown', onKey);
    overlay.addEventListener('click', onBackdrop);
    overlay.querySelector('#wrapped-close').focus();

    // Until the canvas is drawn, Copy/Download do nothing — don't let them look
    // actionable. Re-enabled only on the success path below.
    const _copyBtn = overlay.querySelector('#wrapped-copy');
    const _dlBtn = overlay.querySelector('#wrapped-download');
    const _setExportEnabled = (on) => {
        for (const b of [_copyBtn, _dlBtn]) {
            if (!b) continue;
            b.disabled = !on;
            b.classList.toggle('opacity-40', !on);
            b.classList.toggle('cursor-not-allowed', !on);
        }
    };
    _setExportEnabled(false);

    let data;
    try {
        data = await fetchJSON(`${API_BASE}/players/${encodeURIComponent(guid)}/wrapped?season=current`);
    } catch (_e) {
        overlay.querySelector('#wrapped-status').textContent = 'Could not load season data.';
        return;
    }
    if (!data || !data.cards || !data.cards.length) {
        overlay.querySelector('#wrapped-status').textContent = 'No season data for this player yet.';
        return;
    }
    _setExportEnabled(true);

    const canvas = document.getElementById('wrapped-canvas');
    _drawWrapped(canvas, data);

    overlay.querySelector('#wrapped-download').addEventListener('click', () => {
        const a = document.createElement('a');
        a.download = `slomix-wrapped-${(data.player_name || 'player').replace(/\s+/g, '_')}.png`;
        a.href = canvas.toDataURL('image/png');
        a.click();
    });
    overlay.querySelector('#wrapped-copy').addEventListener('click', async () => {
        const status = overlay.querySelector('#wrapped-status');
        try {
            const blob = await new Promise(res => canvas.toBlob(res, 'image/png'));
            if (!blob) {
                status.textContent = 'Could not export image — use Download instead.';
                return;
            }
            await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]);
            status.textContent = 'Copied! Paste it into Discord.';
        } catch (_e) {
            status.textContent = 'Copy not supported — use Download instead.';
        }
    });
}

function _drawWrapped(canvas, data) {
    canvas.width = W;
    canvas.height = H;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Background gradient
    const g = ctx.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, '#0b1220');
    g.addColorStop(1, '#1e1b4b');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);

    ctx.textAlign = 'center';
    ctx.fillStyle = '#22d3ee';
    ctx.font = 'bold 56px sans-serif';
    ctx.fillText('SLOMIX WRAPPED', W / 2, 150);

    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 72px sans-serif';
    ctx.fillText(String(data.player_name || '').slice(0, 22), W / 2, 250);

    ctx.fillStyle = '#94a3b8';
    ctx.font = '40px sans-serif';
    ctx.fillText(String(data.season_name || data.season_id || ''), W / 2, 320);

    // Stat tiles — 2 columns
    const cards = data.cards.slice(0, 8);
    const cols = 2;
    const padX = 70;
    const tileW = (W - padX * 2 - 40) / cols;
    const tileH = 300;
    const top = 420;
    ctx.textAlign = 'left';
    cards.forEach((c, i) => {
        const col = i % cols;
        const row = Math.floor(i / cols);
        const x = padX + col * (tileW + 40);
        const y = top + row * (tileH + 30);
        // tile bg
        ctx.fillStyle = 'rgba(255,255,255,0.05)';
        _roundRect(ctx, x, y, tileW, tileH, 24);
        ctx.fill();
        ctx.fillStyle = '#64748b';
        ctx.font = 'bold 30px sans-serif';
        ctx.fillText(String(c.label || '').toUpperCase().slice(0, 22), x + 36, y + 70);
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 64px sans-serif';
        ctx.fillText(String(c.value || '').slice(0, 16), x + 36, y + 160);
        if (c.sub) {
            ctx.fillStyle = '#22d3ee';
            ctx.font = '32px sans-serif';
            ctx.fillText(String(c.sub).slice(0, 26), x + 36, y + 220);
        }
    });

    ctx.textAlign = 'center';
    ctx.fillStyle = '#64748b';
    ctx.font = '34px sans-serif';
    ctx.fillText('slomix.fyi', W / 2, H - 80);
}

function _roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
}
