/**
 * Greatshot upload + analysis frontend module.
 */

import { API_BASE, escapeHtml } from './utils.js';

let currentDetailId = null;
let cachedGreatshotItems = [];
let currentGreatshotSection = 'demos';

const TAB_ACTIVE_CLASSES = 'border-brand-cyan/40 text-brand-cyan bg-brand-cyan/10';
const TAB_INACTIVE_CLASSES = 'border-white/10 text-slate-300 hover:text-white hover:border-brand-cyan/40';

function formatStatus(status) {
    const value = String(status || 'unknown').toLowerCase();
    const palette = {
        uploaded: 'text-slate-300 border-slate-500/40 bg-slate-800/40',
        scanning: 'text-brand-cyan border-brand-cyan/40 bg-brand-cyan/10',
        analyzed: 'text-brand-emerald border-brand-emerald/40 bg-brand-emerald/10',
        failed: 'text-brand-rose border-brand-rose/40 bg-brand-rose/10',
        queued: 'text-brand-amber border-brand-amber/40 bg-brand-amber/10',
        rendering: 'text-brand-cyan border-brand-cyan/40 bg-brand-cyan/10',
        rendered: 'text-brand-emerald border-brand-emerald/40 bg-brand-emerald/10'
    };
    return {
        label: value.toUpperCase(),
        classes: palette[value] || 'text-slate-300 border-white/10 bg-slate-800/40'
    };
}

function fmtMs(ms) {
    if (!Number.isFinite(Number(ms))) return '--';
    const total = Math.max(0, Math.floor(Number(ms) / 1000));
    const minutes = Math.floor(total / 60);
    const seconds = total % 60;
    return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

function fmtDate(value) {
    if (!value) return '--';
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return String(value);
    return d.toLocaleString();
}

async function fetchJSONWithAuth(url, options = {}) {
    const response = await fetch(url, {
        credentials: 'same-origin',
        ...options,
    });

    if (!response.ok) {
        let detail = `HTTP ${response.status}`;
        try {
            const payload = await response.json();
            if (payload?.detail) detail = payload.detail;
        } catch (_) {
            // ignore
        }
        throw new Error(detail);
    }

    return await response.json();
}

function setGreatshotTab(section) {
    const normalized = ['demos', 'highlights', 'clips', 'renders'].includes(section)
        ? section
        : 'demos';
    currentGreatshotSection = normalized;

    document.querySelectorAll('[data-greatshot-tab]').forEach((tabButton) => {
        const isActive = tabButton.dataset.greatshotTab === normalized;
        tabButton.setAttribute('aria-selected', isActive ? 'true' : 'false');
        tabButton.classList.remove(...TAB_ACTIVE_CLASSES.split(' '), ...TAB_INACTIVE_CLASSES.split(' '));
        if (isActive) {
            tabButton.classList.add(...TAB_ACTIVE_CLASSES.split(' '));
        } else {
            tabButton.classList.add(...TAB_INACTIVE_CLASSES.split(' '));
        }
    });

    document.querySelectorAll('[data-greatshot-panel]').forEach((panel) => {
        const isActive = panel.dataset.greatshotPanel === normalized;
        panel.classList.toggle('hidden', !isActive);
    });
}

function renderDemosList(items) {
    const container = document.getElementById('demos-list');
    if (!container) return;

    if (!items || items.length === 0) {
        container.innerHTML = `
            <div class="glass-card p-6 rounded-xl text-center text-slate-500">
                No demos uploaded yet.
            </div>
        `;
        return;
    }

    container.innerHTML = items.map((item) => {
        const status = formatStatus(item.status);
        return `
            <button
                class="glass-card p-4 rounded-xl border border-white/10 text-left hover:border-brand-cyan/40 transition w-full"
                onclick="navigateToGreatshotDemo('${escapeHtml(item.id)}')">
                <div class="flex items-center justify-between gap-3">
                    <div class="text-sm font-bold text-white truncate">${escapeHtml(item.filename || item.id)}</div>
                    <span class="text-[10px] font-bold px-2 py-1 rounded border ${status.classes}">${status.label}</span>
                </div>
                <div class="mt-2 text-xs text-slate-400 flex flex-wrap gap-3">
                    <span>Map: ${escapeHtml(item.map || '--')}</span>
                    <span>Duration: ${fmtMs(item.duration_ms)}</span>
                    <span>Highlights: ${Number(item.highlight_count || 0)}</span>
                    <span>Renders: ${Number(item.rendered_count || 0)}/${Number(item.render_job_count || 0)}</span>
                    <span>Created: ${escapeHtml(fmtDate(item.created_at))}</span>
                </div>
                ${item.error ? `<div class="mt-2 text-xs text-brand-rose">${escapeHtml(item.error)}</div>` : ''}
            </button>
        `;
    }).join('');
}

function renderHighlightsHub(items) {
    const container = document.getElementById('greatshot-highlights-hub');
    if (!container) return;

    const analyzed = (items || []).filter((item) => Number(item.highlight_count || 0) > 0);
    if (analyzed.length === 0) {
        container.innerHTML = '<div class="text-slate-500">No detected highlights yet. Analyze a demo first.</div>';
        return;
    }

    container.innerHTML = analyzed.slice(0, 12).map((item) => `
        <div class="data-row text-sm">
            <div class="text-slate-200">${escapeHtml(item.filename || item.id)}</div>
            <div class="flex items-center gap-3 text-xs">
                <span class="text-brand-amber">${Number(item.highlight_count || 0)} highlights</span>
                <button onclick="navigateToGreatshotDemo('${escapeHtml(item.id)}')"
                    class="px-2 py-1 rounded border border-brand-cyan/40 text-brand-cyan hover:bg-brand-cyan/10 transition">
                    Open
                </button>
            </div>
        </div>
    `).join('');
}

function renderClipsHub(items) {
    const container = document.getElementById('greatshot-clips-hub');
    if (!container) return;

    const candidates = (items || []).filter((item) => Number(item.highlight_count || 0) > 0);
    if (candidates.length === 0) {
        container.innerHTML = '<div class="text-slate-500">No clip candidates yet. Highlights appear after analysis.</div>';
        return;
    }

    container.innerHTML = candidates.slice(0, 12).map((item) => `
        <div class="data-row text-sm">
            <div class="text-slate-200">${escapeHtml(item.filename || item.id)}</div>
            <div class="flex items-center gap-3 text-xs">
                <span class="text-slate-400">${Number(item.highlight_count || 0)} clip windows</span>
                <button onclick="navigateToGreatshotDemo('${escapeHtml(item.id)}')"
                    class="px-2 py-1 rounded border border-brand-cyan/40 text-brand-cyan hover:bg-brand-cyan/10 transition">
                    Manage Clips
                </button>
            </div>
        </div>
    `).join('');
}

function renderRendersHub(items) {
    const container = document.getElementById('greatshot-renders-hub');
    if (!container) return;

    const candidates = (items || []).filter((item) => Number(item.render_job_count || 0) > 0);
    if (candidates.length === 0) {
        container.innerHTML = '<div class="text-slate-500">No render jobs yet. Queue rendering from a demo highlight.</div>';
        return;
    }

    container.innerHTML = candidates.slice(0, 12).map((item) => `
        <div class="data-row text-sm">
            <div class="text-slate-200">${escapeHtml(item.filename || item.id)}</div>
            <div class="flex items-center gap-3 text-xs">
                <span class="text-brand-emerald">${Number(item.rendered_count || 0)} rendered</span>
                <span class="text-slate-400">${Number(item.render_job_count || 0)} total jobs</span>
                <button onclick="navigateToGreatshotDemo('${escapeHtml(item.id)}')"
                    class="px-2 py-1 rounded border border-brand-cyan/40 text-brand-cyan hover:bg-brand-cyan/10 transition">
                    Open
                </button>
            </div>
        </div>
    `).join('');
}

function renderGreatshotHubPanels(items) {
    renderHighlightsHub(items);
    renderClipsHub(items);
    renderRendersHub(items);
}

async function uploadDemo(form) {
    const fileInput = document.getElementById('demo-upload-file');
    const statusBox = document.getElementById('demo-upload-status');
    const submitBtn = document.getElementById('demo-upload-submit');

    if (!fileInput?.files?.length) {
        if (statusBox) statusBox.textContent = 'Select a .dm_84 file first.';
        return;
    }

    const formData = new FormData(form);

    try {
        if (submitBtn) submitBtn.disabled = true;
        if (statusBox) statusBox.textContent = 'Uploading...';

        const response = await fetch(`${API_BASE}/greatshot/upload`, {
            method: 'POST',
            credentials: 'same-origin',
            body: formData,
        });

        if (!response.ok) {
            let detail = `HTTP ${response.status}`;
            try {
                const payload = await response.json();
                if (payload?.detail) detail = payload.detail;
            } catch (_) {
                // ignore
            }
            throw new Error(detail);
        }

        const payload = await response.json();
        if (statusBox) statusBox.textContent = `Uploaded. Demo queued: ${payload.demo_id}`;
        form.reset();
        await loadGreatshotView('demos');
    } catch (error) {
        if (statusBox) statusBox.textContent = `Upload failed: ${error.message}`;
    } finally {
        if (submitBtn) submitBtn.disabled = false;
    }
}

export async function loadGreatshotView(section = 'demos') {
    setGreatshotTab(section);
    try {
        const payload = await fetchJSONWithAuth(`${API_BASE}/greatshot`);
        const items = payload.items || [];
        cachedGreatshotItems = items;
        renderDemosList(items);
        renderGreatshotHubPanels(items);
    } catch (error) {
        const demosContainer = document.getElementById('demos-list');
        if (demosContainer) {
            demosContainer.innerHTML = `<div class="glass-card p-6 rounded-xl text-brand-rose">Failed to load demos: ${escapeHtml(error.message)}</div>`;
        }

        const fallback = `<div class="text-brand-rose">Failed to load Greatshot data: ${escapeHtml(error.message)}</div>`;
        ['greatshot-highlights-hub', 'greatshot-clips-hub', 'greatshot-renders-hub'].forEach((id) => {
            const panel = document.getElementById(id);
            if (panel) panel.innerHTML = fallback;
        });
    }
}

function renderTimeline(events) {
    const container = document.getElementById('demo-detail-timeline');
    if (!container) return;

    if (!events || events.length === 0) {
        container.innerHTML = '<div class="text-slate-500 text-sm">No timeline events available.</div>';
        return;
    }

    const preview = events.slice(0, 120);
    container.innerHTML = preview.map((event) => {
        const t = fmtMs(event.t_ms);
        const type = escapeHtml(event.type || 'event');
        if (event.type === 'kill') {
            return `<div class="data-row text-xs"><span class="text-slate-500">${t}</span><span class="text-slate-200">${escapeHtml(event.attacker || 'world')} -> ${escapeHtml(event.victim || 'unknown')} <span class="text-brand-amber">${escapeHtml(event.weapon || '--')}</span></span></div>`;
        }
        if (event.type === 'chat') {
            return `<div class="data-row text-xs"><span class="text-slate-500">${t}</span><span class="text-slate-300">${escapeHtml(event.attacker || 'unknown')}: ${escapeHtml(event.message || '')}</span></div>`;
        }
        return `<div class="data-row text-xs"><span class="text-slate-500">${t}</span><span class="text-slate-300">${type}</span></div>`;
    }).join('');
}

function renderHighlights(demoId, highlights) {
    const container = document.getElementById('demo-detail-highlights');
    if (!container) return;

    if (!highlights || highlights.length === 0) {
        container.innerHTML = '<div class="text-slate-500 text-sm">No clip-worthy highlights detected.</div>';
        return;
    }

    container.innerHTML = highlights.map((item) => {
        const type = escapeHtml(item.type || '--');
        const player = escapeHtml(item.player || '--');
        const explanation = escapeHtml(item.meta?.explanation || item.explanation || '');
        const clipLink = item.clip_download
            ? `<a href="${escapeHtml(item.clip_download)}" class="px-3 py-2 rounded-lg text-xs font-bold border border-brand-amber/40 text-brand-amber hover:bg-brand-amber/10 transition">Clip</a>`
            : '';
        return `
            <div class="glass-card p-4 rounded-xl border border-white/10">
                <div class="flex items-center justify-between gap-3">
                    <div>
                        <div class="text-sm font-bold text-white">${type}</div>
                        <div class="text-xs text-slate-400 mt-1">${player} | ${fmtMs(item.start_ms)} - ${fmtMs(item.end_ms)} | score ${Number(item.score || 0).toFixed(2)}</div>
                        ${explanation ? `<div class="text-xs text-slate-500 mt-1">${explanation}</div>` : ''}
                    </div>
                    <div class="flex items-center gap-2">
                        ${clipLink}
                        <button class="px-3 py-2 rounded-lg text-xs font-bold border border-brand-cyan/40 text-brand-cyan hover:bg-brand-cyan/10 transition"
                            onclick="queueHighlightRender('${escapeHtml(demoId)}','${escapeHtml(item.id)}')">
                            Render
                        </button>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

function renderRenderJobs(jobs) {
    const container = document.getElementById('demo-detail-renders');
    if (!container) return;

    if (!jobs || jobs.length === 0) {
        container.innerHTML = '<div class="text-slate-500 text-sm">No render jobs yet.</div>';
        return;
    }

    container.innerHTML = jobs.map((job) => {
        const status = formatStatus(job.status);
        const videoLink = job.video_download
            ? `<a href="${escapeHtml(job.video_download)}" class="px-2 py-1 rounded border border-brand-emerald/40 text-brand-emerald hover:bg-brand-emerald/10 transition text-[11px] font-bold">MP4</a>`
            : '';
        return `
            <div class="data-row text-xs">
                <div class="text-slate-300">${escapeHtml(job.id)}</div>
                <div class="flex items-center gap-2">
                    <span class="px-2 py-1 rounded border ${status.classes}">${status.label}</span>
                    ${videoLink}
                    ${job.error ? `<span class="text-brand-rose">${escapeHtml(job.error)}</span>` : ''}
                </div>
            </div>
        `;
    }).join('');
}

export async function loadGreatshotDemoDetail(demoId) {
    currentDetailId = demoId;
    const title = document.getElementById('demo-detail-title');
    const statusChip = document.getElementById('demo-detail-status');
    const meta = document.getElementById('demo-detail-meta');
    const downloads = document.getElementById('demo-detail-downloads');

    if (title) title.textContent = `Demo ${demoId}`;
    if (statusChip) statusChip.textContent = 'Loading...';
    if (meta) meta.innerHTML = '';
    if (downloads) downloads.innerHTML = '';

    try {
        const payload = await fetchJSONWithAuth(`${API_BASE}/greatshot/${encodeURIComponent(demoId)}`);
        const status = formatStatus(payload.status);

        if (title) title.textContent = payload.filename || payload.id;
        if (statusChip) {
            statusChip.textContent = status.label;
            statusChip.className = `px-3 py-1 rounded-md text-xs font-bold border ${status.classes}`;
        }

        if (meta) {
            const md = payload.metadata || {};
            meta.innerHTML = `
                <div class="data-row"><span class="data-label">Map</span><span class="data-value">${escapeHtml(md.map || '--')}</span></div>
                <div class="data-row"><span class="data-label">Duration</span><span class="data-value">${fmtMs(md.duration_ms)}</span></div>
                <div class="data-row"><span class="data-label">Mod</span><span class="data-value">${escapeHtml(md.mod || '--')} ${escapeHtml(md.mod_version || '')}</span></div>
                <div class="data-row"><span class="data-label">Created</span><span class="data-value">${escapeHtml(fmtDate(payload.created_at))}</span></div>
                <div class="data-row"><span class="data-label">Players</span><span class="data-value">${Number(payload.analysis?.stats?.player_count || payload.analysis?.metadata?.player_count || 0)}</span></div>
            `;
        }

        if (downloads) {
            const links = [];
            if (payload.downloads?.json) {
                links.push(`<a href="${escapeHtml(payload.downloads.json)}" class="px-3 py-2 rounded-lg border border-brand-cyan/40 text-brand-cyan text-xs font-bold hover:bg-brand-cyan/10 transition">Download JSON</a>`);
            }
            if (payload.downloads?.txt) {
                links.push(`<a href="${escapeHtml(payload.downloads.txt)}" class="px-3 py-2 rounded-lg border border-brand-amber/40 text-brand-amber text-xs font-bold hover:bg-brand-amber/10 transition">Download TXT</a>`);
            }
            downloads.innerHTML = links.join('') || '<span class="text-slate-500 text-sm">No reports yet.</span>';
        }

        renderTimeline(payload.analysis?.events || []);
        renderHighlights(demoId, payload.highlights || []);
        renderRenderJobs(payload.renders || []);

        const errorBox = document.getElementById('demo-detail-error');
        if (errorBox) {
            errorBox.textContent = payload.error ? `Error: ${payload.error}` : '';
            errorBox.classList.toggle('hidden', !payload.error);
        }
    } catch (error) {
        const errorBox = document.getElementById('demo-detail-error');
        if (errorBox) {
            errorBox.textContent = `Failed to load demo: ${error.message}`;
            errorBox.classList.remove('hidden');
        }
    }
}

export async function queueHighlightRender(demoId, highlightId) {
    try {
        await fetchJSONWithAuth(`${API_BASE}/greatshot/${encodeURIComponent(demoId)}/highlights/render`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ highlight_id: highlightId }),
        });
        await loadGreatshotDemoDetail(demoId);
        await loadGreatshotView(currentGreatshotSection);
    } catch (error) {
        alert(`Render queue failed: ${error.message}`);
    }
}

export function initGreatshotModule() {
    const form = document.getElementById('demo-upload-form');
    if (form && !form.dataset.bound) {
        form.dataset.bound = 'true';
        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            await uploadDemo(form);
        });
    }

    document.querySelectorAll('[data-greatshot-tab]').forEach((tabButton) => {
        if (tabButton.dataset.bound) return;
        tabButton.dataset.bound = 'true';
        tabButton.addEventListener('click', () => {
            const section = tabButton.dataset.greatshotTab || 'demos';
            if (typeof window.navigateTo === 'function') {
                window.navigateTo('greatshot', true, { section });
            } else {
                setGreatshotTab(section);
            }
        });
    });
}

window.queueHighlightRender = queueHighlightRender;
window.navigateToGreatshotDemo = (demoId) => {
    if (typeof window.navigateTo === 'function') {
        window.navigateTo('greatshot-demo', true, { demoId });
    }
};
window.navigateToDemo = window.navigateToGreatshotDemo;

export function getCurrentGreatshotDetailId() {
    return currentDetailId;
}

export function getCachedGreatshotItems() {
    return cachedGreatshotItems.slice();
}

