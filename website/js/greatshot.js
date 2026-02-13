/**
 * Greatshot upload + analysis frontend module.
 */

import { API_BASE, escapeHtml, escapeJsString } from './utils.js';

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
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    const seconds = total % 60;
    if (hours > 0) {
        return `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    }
    return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

/** Format absolute server-time ms as gameplay-relative time by subtracting round start offset. */
function fmtRelMs(ms, offsetMs) {
    if (!Number.isFinite(Number(ms))) return '--';
    const relative = Number(ms) - (Number(offsetMs) || 0);
    return fmtMs(Math.max(0, relative));
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
                onclick="navigateToGreatshotDemo('${escapeJsString(item.id)}')">
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
                <button onclick="navigateToGreatshotDemo('${escapeJsString(item.id)}')"
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
                <button onclick="navigateToGreatshotDemo('${escapeJsString(item.id)}')"
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
                <button onclick="navigateToGreatshotDemo('${escapeJsString(item.id)}')"
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

// --- Multi-file analysis polling state ---
let analysisPollingTimer = null;
let analysisStartTime = null;
let analysisElapsedTimer = null;
/** @type {Map<string, {filename: string, status: string, data: object|null}>} */
let pendingDemos = new Map();

function showAnalysisProgress(show) {
    const panel = document.getElementById('demo-analysis-progress');
    if (panel) panel.classList.toggle('hidden', !show);
}

function setAnalysisPhase(phase) {
    const phaseEl = document.getElementById('analysis-phase');
    const phases = { upload: 'phase-upload', queued: 'phase-queue', scanning: 'phase-scan', done: 'phase-done' };
    const labels = { upload: 'Uploaded', queued: 'Queued for analysis...', scanning: 'Scanning demo...', done: 'Analysis complete!' };
    const activeClasses = 'border-brand-cyan/40 text-brand-cyan bg-brand-cyan/10';
    const doneClasses = 'border-brand-emerald/40 text-brand-emerald bg-brand-emerald/10';
    const inactiveClasses = 'border-white/10 text-slate-500';

    if (phaseEl) phaseEl.textContent = labels[phase] || phase;

    const order = ['upload', 'queued', 'scanning', 'done'];
    const currentIdx = order.indexOf(phase);

    for (let i = 0; i < order.length; i++) {
        const el = document.getElementById(phases[order[i]]);
        if (!el) continue;
        el.className = 'text-[10px] px-2 py-0.5 rounded border ';
        if (i < currentIdx) {
            el.className += doneClasses;
        } else if (i === currentIdx) {
            el.className += (phase === 'done' ? doneClasses : activeClasses);
        } else {
            el.className += inactiveClasses;
        }
    }
}

function updateElapsedTime() {
    const el = document.getElementById('analysis-elapsed');
    if (!el || !analysisStartTime) return;
    const secs = Math.floor((Date.now() - analysisStartTime) / 1000);
    el.textContent = secs < 60 ? `${secs}s` : `${Math.floor(secs / 60)}m ${secs % 60}s`;
}

function stopAnalysisPolling() {
    if (analysisPollingTimer) { clearInterval(analysisPollingTimer); analysisPollingTimer = null; }
    if (analysisElapsedTimer) { clearInterval(analysisElapsedTimer); analysisElapsedTimer = null; }
    pendingDemos.clear();
}

function showAnalysisResult(status, data) {
    const resultEl = document.getElementById('analysis-result');
    const spinnerEl = document.getElementById('analysis-spinner');
    if (spinnerEl) spinnerEl.classList.add('hidden');

    if (!resultEl) return;
    resultEl.classList.remove('hidden');

    if (status === 'analyzed') {
        const parts = [];
        if (data.map) parts.push(`Map: ${data.map}`);
        if (data.highlight_count != null) parts.push(`${data.highlight_count} highlight${data.highlight_count !== 1 ? 's' : ''} found`);
        resultEl.innerHTML = `<span class="text-brand-emerald font-bold">Analysis complete.</span> ${escapeHtml(parts.join(' · '))}`;
    } else if (status === 'failed') {
        resultEl.innerHTML = `<span class="text-brand-rose font-bold">Analysis failed:</span> ${escapeHtml(data.error || 'Unknown error')}`;
    }
}

/** Render multi-file progress list in the analysis panel. */
function renderMultiProgress() {
    const listEl = document.getElementById('analysis-multi-list');
    if (!listEl) return;

    let html = '';
    for (const [demoId, entry] of pendingDemos) {
        const name = escapeHtml(entry.filename);
        let icon, statusText, statusClass;
        if (entry.status === 'analyzed') {
            icon = '<span class="text-brand-emerald">&#10003;</span>';
            statusText = 'Done';
            statusClass = 'text-brand-emerald';
        } else if (entry.status === 'failed') {
            icon = '<span class="text-brand-rose">&#10007;</span>';
            statusText = entry.data?.error ? escapeHtml(entry.data.error) : 'Failed';
            statusClass = 'text-brand-rose';
        } else if (entry.status === 'scanning') {
            icon = '<span class="w-3 h-3 inline-block border-2 border-brand-cyan/30 border-t-brand-cyan rounded-full animate-spin"></span>';
            statusText = 'Scanning...';
            statusClass = 'text-brand-cyan';
        } else {
            icon = '<span class="w-3 h-3 inline-block border-2 border-brand-amber/30 border-t-brand-amber rounded-full animate-spin"></span>';
            statusText = 'Queued';
            statusClass = 'text-brand-amber';
        }
        html += `<div class="flex items-center gap-2 text-xs">
            ${icon}
            <span class="text-slate-200 truncate flex-1">${name}</span>
            <span class="${statusClass}">${statusText}</span>
        </div>`;
    }
    listEl.innerHTML = html;
}

/** Poll status for all pending demos. */
async function pollMultiAnalysisStatus() {
    const stillPending = [];
    for (const [demoId, entry] of pendingDemos) {
        if (entry.status === 'analyzed' || entry.status === 'failed') continue;
        stillPending.push(demoId);
    }

    if (stillPending.length === 0) {
        // All done
        stopAnalysisPolling();
        const phaseEl = document.getElementById('analysis-phase');
        const spinnerEl = document.getElementById('analysis-spinner');
        if (phaseEl) phaseEl.textContent = 'All analyses complete!';
        if (spinnerEl) spinnerEl.classList.add('hidden');
        await loadGreatshotView('demos');
        return;
    }

    // Update header with progress count
    const total = pendingDemos.size;
    const done = total - stillPending.length;
    const phaseEl = document.getElementById('analysis-phase');
    if (phaseEl) phaseEl.textContent = `Analyzing ${done}/${total} complete...`;

    for (const demoId of stillPending) {
        try {
            const data = await fetchJSONWithAuth(`${API_BASE}/greatshot/${encodeURIComponent(demoId)}/status`);
            const entry = pendingDemos.get(demoId);
            if (!entry) continue;
            entry.status = data.status;
            entry.data = data;
        } catch (_) {
            // keep trying
        }
    }

    renderMultiProgress();

    // Check if all done now
    let allDone = true;
    for (const [, entry] of pendingDemos) {
        if (entry.status !== 'analyzed' && entry.status !== 'failed') {
            allDone = false;
            break;
        }
    }

    if (allDone) {
        stopAnalysisPolling();
        const spinnerEl = document.getElementById('analysis-spinner');
        if (spinnerEl) spinnerEl.classList.add('hidden');
        if (phaseEl) phaseEl.textContent = 'All analyses complete!';
        await loadGreatshotView('demos');

        // For single file, navigate to detail after short delay
        if (total === 1) {
            const singleId = [...pendingDemos.keys()][0];
            const singleEntry = pendingDemos.get(singleId);
            if (singleEntry?.status === 'analyzed') {
                setTimeout(() => {
                    if (typeof window.navigateToGreatshotDemo === 'function') {
                        window.navigateToGreatshotDemo(singleId);
                    }
                }, 2000);
            }
        }
    }
}

async function uploadDemo(form) {
    const fileInput = document.getElementById('demo-upload-file');
    const statusBox = document.getElementById('demo-upload-status');
    const submitBtn = document.getElementById('demo-upload-submit');

    if (!fileInput?.files?.length) {
        if (statusBox) statusBox.textContent = 'Select a .dm_84 file first.';
        return;
    }

    const files = Array.from(fileInput.files);
    const totalFiles = files.length;

    stopAnalysisPolling();
    showAnalysisProgress(false);
    pendingDemos.clear();

    // Toggle single vs multi progress UI
    const singlePhases = document.getElementById('analysis-phases-single');
    const multiList = document.getElementById('analysis-multi-list');
    if (totalFiles === 1) {
        if (singlePhases) singlePhases.classList.remove('hidden');
        if (multiList) multiList.classList.add('hidden');
    } else {
        if (singlePhases) singlePhases.classList.add('hidden');
        if (multiList) multiList.classList.remove('hidden');
    }

    try {
        if (submitBtn) submitBtn.disabled = true;

        // Upload each file individually
        const uploadedIds = [];
        for (let i = 0; i < totalFiles; i++) {
            const file = files[i];
            if (statusBox) statusBox.textContent = totalFiles > 1
                ? `Uploading ${i + 1}/${totalFiles}: ${file.name}`
                : 'Uploading...';

            const fd = new FormData();
            fd.append('file', file);

            const response = await fetch(`${API_BASE}/greatshot/upload`, {
                method: 'POST',
                credentials: 'same-origin',
                body: fd,
            });

            if (!response.ok) {
                let detail = `HTTP ${response.status}`;
                try {
                    const payload = await response.json();
                    if (payload?.detail) detail = payload.detail;
                } catch (_) {
                    // ignore
                }
                // For multi-file, show error but continue
                if (totalFiles > 1) {
                    pendingDemos.set(`error-${i}`, { filename: file.name, status: 'failed', data: { error: detail } });
                    continue;
                }
                throw new Error(detail);
            }

            const payload = await response.json();
            uploadedIds.push(payload.demo_id);
            pendingDemos.set(payload.demo_id, { filename: file.name, status: 'uploaded', data: null });
        }

        if (statusBox) statusBox.textContent = '';
        form.reset();

        if (uploadedIds.length === 0 && pendingDemos.size > 0) {
            // All uploads failed
            showAnalysisProgress(true);
            renderMultiProgress();
            const phaseEl = document.getElementById('analysis-phase');
            const spinnerEl = document.getElementById('analysis-spinner');
            if (phaseEl) phaseEl.textContent = 'All uploads failed';
            if (spinnerEl) spinnerEl.classList.add('hidden');
            return;
        }

        // Show progress panel and start polling
        showAnalysisProgress(true);
        analysisStartTime = Date.now();
        analysisElapsedTimer = setInterval(updateElapsedTime, 1000);

        if (totalFiles === 1) {
            // Single file: use original single-file UX
            setAnalysisPhase('queued');
            analysisPollingTimer = setInterval(() => pollMultiAnalysisStatus(), 2000);
        } else {
            // Multi file: use list-based UX
            const phaseEl = document.getElementById('analysis-phase');
            if (phaseEl) phaseEl.textContent = `Analyzing 0/${pendingDemos.size} complete...`;
            renderMultiProgress();
            analysisPollingTimer = setInterval(() => pollMultiAnalysisStatus(), 2000);
        }

        await loadGreatshotView('demos');
    } catch (error) {
        if (statusBox) statusBox.textContent = `Upload failed: ${error.message}`;
        showAnalysisProgress(false);
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

function renderTimeline(events, roundStartMs = 0) {
    const container = document.getElementById('demo-detail-timeline');
    if (!container) return;

    if (!events || events.length === 0) {
        container.innerHTML = '<div class="text-slate-500 text-sm">No timeline events available.</div>';
        return;
    }

    const preview = events.slice(0, 120);
    container.innerHTML = preview.map((event) => {
        const t = fmtRelMs(event.t_ms, roundStartMs);
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

function renderKillSequence(meta, roundStartMs) {
    const seq = meta?.kill_sequence;
    if (!seq || seq.length === 0) return '';

    const rows = seq.map((k) => {
        const t = fmtRelMs(k.t_ms, roundStartMs);
        const hs = k.headshot ? '<span class="text-brand-rose">HS</span>' : '';
        return `<span class="text-slate-500">${t}</span> ${escapeHtml(k.victim || '?')} <span class="text-brand-amber">${escapeHtml(k.weapon || '?')}</span> ${hs}`;
    }).join('<br>');

    return `<div class="mt-2 text-xs leading-relaxed">${rows}</div>`;
}

function renderWeaponBadges(meta) {
    const weapons = meta?.weapons_used;
    if (!weapons) return '';

    const sorted = Object.entries(weapons).sort((a, b) => b[1] - a[1]);
    const badges = sorted.map(([w, c]) => {
        const isHs = meta.headshot_weapons && meta.headshot_weapons[w];
        const hsClass = isHs ? 'border-brand-rose/40 text-brand-rose' : 'border-white/10 text-slate-300';
        return `<span class="px-2 py-0.5 rounded border ${hsClass} text-[10px]">${escapeHtml(w)} x${c}</span>`;
    }).join('');

    return `<div class="mt-2 flex flex-wrap gap-1">${badges}</div>`;
}

function renderKillRhythm(meta) {
    const gaps = meta?.kill_gaps_ms;
    if (!gaps || gaps.length === 0) return '';

    const avg = meta.avg_kill_gap_ms || 0;
    const fastest = meta.fastest_kill_gap_ms || 0;
    return `<div class="mt-1 text-[10px] text-slate-500">Rhythm: avg ${avg}ms, fastest ${fastest}ms</div>`;
}

function renderAttackerStats(meta) {
    const s = meta?.attacker_stats;
    if (!s) return '';

    const kdr = s.kdr || 0;
    const acc = s.accuracy != null ? `, ${s.accuracy}% acc` : '';
    return `<div class="mt-1 text-[10px] text-slate-400">Match: ${s.kills || 0}K/${s.deaths || 0}D (${kdr} KDR${acc})</div>`;
}

function renderHighlights(demoId, highlights, roundStartMs = 0) {
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
        const meta = item.meta || {};
        const clipLink = item.clip_download
            ? `<a href="${escapeHtml(item.clip_download)}" class="px-3 py-2 rounded-lg text-xs font-bold border border-brand-amber/40 text-brand-amber hover:bg-brand-amber/10 transition">Clip</a>`
            : '';
        return `
            <div class="glass-card p-4 rounded-xl border border-white/10">
                <div class="flex items-center justify-between gap-3">
                    <div class="flex-1 min-w-0">
                        <div class="text-sm font-bold text-white">${type}</div>
                        <div class="text-xs text-slate-400 mt-1">${player} | ${fmtRelMs(item.start_ms, roundStartMs)} - ${fmtRelMs(item.end_ms, roundStartMs)} | score ${Number(item.score || 0).toFixed(2)}</div>
                        ${explanation ? `<div class="text-xs text-slate-500 mt-1">${explanation}</div>` : ''}
                        ${renderKillSequence(meta, roundStartMs)}
                        ${renderWeaponBadges(meta)}
                        ${renderKillRhythm(meta)}
                        ${renderAttackerStats(meta)}
                    </div>
                    <div class="flex items-center gap-2 flex-shrink-0">
                        ${clipLink}
                        <button class="px-3 py-2 rounded-lg text-xs font-bold border border-brand-cyan/40 text-brand-cyan hover:bg-brand-cyan/10 transition"
                            onclick="queueHighlightRender('${escapeJsString(demoId)}','${escapeJsString(item.id)}')">
                            Render
                        </button>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

async function renderCrossref(demoId) {
    const container = document.getElementById('demo-detail-crossref');
    if (!container) return;

    container.innerHTML = '<div class="text-slate-500 text-sm">Checking database...</div>';

    try {
        const data = await fetchJSONWithAuth(`${API_BASE}/greatshot/${encodeURIComponent(demoId)}/crossref`);

        if (!data.matched) {
            container.innerHTML = `<div class="text-slate-500 text-sm">${escapeHtml(data.reason || 'No match found')}</div>`;
            return;
        }

        const round = data.round || {};
        const confidence = Number(round.confidence || 0);
        const confColor = confidence >= 80 ? 'text-brand-emerald' : confidence >= 50 ? 'text-brand-amber' : 'text-brand-rose';

        let html = `
            <div class="flex items-center gap-3 mb-3">
                <span class="text-xs font-bold ${confColor}">${confidence}% confidence</span>
                <span class="text-xs text-slate-400">${(round.match_details || []).join(', ')}</span>
            </div>
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs mb-4">
                <div><span class="text-slate-500">Round ID:</span> <span class="text-white">${round.round_id || '--'}</span></div>
                <div><span class="text-slate-500">Session:</span> <span class="text-white">${round.gaming_session_id || '--'}</span></div>
                <div><span class="text-slate-500">Date:</span> <span class="text-white">${escapeHtml(round.round_date || '--')}</span></div>
                <div><span class="text-slate-500">Winner:</span> <span class="text-white">${escapeHtml(round.winner_team || '--')}</span></div>
            </div>
        `;

        const comparison = data.comparison || [];
        if (comparison.length > 0) {
            html += '<div class="text-xs font-bold uppercase text-slate-500 mb-2">Player Stats Comparison</div>';
            html += '<div class="overflow-x-auto"><table class="w-full text-xs">';
            html += '<thead><tr class="text-slate-500 border-b border-white/10">';
            html += '<th class="text-left py-1 pr-2">Player</th>';
            html += '<th class="text-right pr-2">Demo K</th><th class="text-right pr-2">DB K</th>';
            html += '<th class="text-right pr-2">Demo D</th><th class="text-right pr-2">DB D</th>';
            html += '<th class="text-right pr-2">Demo DMG</th><th class="text-right pr-2">DB DMG</th>';
            html += '<th class="text-right pr-2">Demo ACC%</th><th class="text-right pr-2">DB ACC%</th>';
            html += '<th class="text-right pr-2">Demo TPM</th><th class="text-right pr-2">DB TPM</th>';
            html += '<th class="text-right pr-2">DB KDR</th><th class="text-right">DB DPM</th>';
            html += '</tr></thead><tbody>';

            for (const c of comparison) {
                const name = escapeHtml(c.db_name || c.demo_name || '?');
                const ds = c.demo_stats || {};
                const bs = c.db_stats || {};
                const matchIcon = c.matched ? '' : '<span class="text-brand-amber">*</span>';
                const demoTpm = ds.tpm ?? ds.time_played_minutes;
                const dbTpm = bs.tpm ?? bs.time_played_minutes;
                html += `<tr class="border-b border-white/5">`;
                html += `<td class="py-1 pr-2 text-slate-200">${name}${matchIcon}</td>`;
                html += `<td class="text-right pr-2 text-slate-300">${ds.kills ?? '--'}</td>`;
                html += `<td class="text-right pr-2 text-white">${bs.kills ?? '--'}</td>`;
                html += `<td class="text-right pr-2 text-slate-300">${ds.deaths ?? '--'}</td>`;
                html += `<td class="text-right pr-2 text-white">${bs.deaths ?? '--'}</td>`;
                html += `<td class="text-right pr-2 text-slate-300">${ds.damage_given ?? '--'}</td>`;
                html += `<td class="text-right pr-2 text-white">${bs.damage_given ?? '--'}</td>`;
                html += `<td class="text-right pr-2 text-slate-300">${ds.accuracy != null ? Number(ds.accuracy).toFixed(1) : '--'}</td>`;
                html += `<td class="text-right pr-2 text-white">${bs.accuracy != null ? Number(bs.accuracy).toFixed(1) : '--'}</td>`;
                html += `<td class="text-right pr-2 text-slate-300">${demoTpm != null ? Number(demoTpm).toFixed(2) : '--'}</td>`;
                html += `<td class="text-right pr-2 text-white">${dbTpm != null ? Number(dbTpm).toFixed(2) : '--'}</td>`;
                html += `<td class="text-right pr-2 text-white">${bs.kdr != null ? Number(bs.kdr).toFixed(2) : '--'}</td>`;
                html += `<td class="text-right text-white">${bs.dpm != null ? Number(bs.dpm).toFixed(1) : '--'}</td>`;
                html += `</tr>`;
            }

            html += '</tbody></table></div>';
        }

        container.innerHTML = html;
    } catch (error) {
        container.innerHTML = `<div class="text-brand-rose text-sm">Cross-reference failed: ${escapeHtml(error.message)}</div>`;
    }
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

function renderPlayerStats(playerStats) {
    const container = document.getElementById('demo-detail-playerstats');
    if (!container) return;

    if (!playerStats || typeof playerStats !== 'object' || Object.keys(playerStats).length === 0) {
        container.innerHTML = '<div class="text-slate-500 text-sm">No player stats available.</div>';
        return;
    }

    // Convert object {name: {kills, deaths, ...}} to sorted array
    const players = Object.entries(playerStats).map(([name, stats]) => ({
        name,
        kills: Number(stats.kills || 0),
        deaths: Number(stats.deaths || 0),
        damage: Number(stats.damage_given || stats.damage || 0),
        accuracy: stats.accuracy != null ? Number(stats.accuracy) : null,
        headshots: Number(stats.headshots || stats.headshot_kills || 0),
        tpm: stats.tpm != null
            ? Number(stats.tpm)
            : (stats.time_played_minutes != null ? Number(stats.time_played_minutes) : null),
    }));

    // Sort by kills descending
    players.sort((a, b) => b.kills - a.kills);

    let html = '<table class="w-full text-xs">';
    html += '<thead><tr class="text-slate-500 border-b border-white/10">';
    html += '<th class="text-left py-1 pr-3">Player</th>';
    html += '<th class="text-right pr-3">Kills</th>';
    html += '<th class="text-right pr-3">Deaths</th>';
    html += '<th class="text-right pr-3">KDR</th>';
    html += '<th class="text-right pr-3">Damage</th>';
    html += '<th class="text-right pr-3">Acc%</th>';
    html += '<th class="text-right pr-3">TPM</th>';
    html += '<th class="text-right">HS</th>';
    html += '</tr></thead><tbody>';

    for (const p of players) {
        const kdr = p.deaths > 0 ? (p.kills / p.deaths).toFixed(2) : p.kills > 0 ? p.kills.toFixed(2) : '0.00';
        html += '<tr class="border-b border-white/5">';
        html += `<td class="py-1 pr-3 text-slate-200">${escapeHtml(p.name)}</td>`;
        html += `<td class="text-right pr-3 text-white">${p.kills}</td>`;
        html += `<td class="text-right pr-3 text-white">${p.deaths}</td>`;
        html += `<td class="text-right pr-3 text-white">${kdr}</td>`;
        html += `<td class="text-right pr-3 text-white">${p.damage}</td>`;
        html += `<td class="text-right pr-3 text-white">${p.accuracy != null ? p.accuracy.toFixed(1) : '--'}</td>`;
        html += `<td class="text-right pr-3 text-white">${p.tpm != null ? p.tpm.toFixed(2) : '--'}</td>`;
        html += `<td class="text-right text-white">${p.headshots}</td>`;
        html += '</tr>';
    }

    html += '</tbody></table>';
    container.innerHTML = html;
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

        const roundStartMs = Number(payload.metadata?.start_ms || 0);
        renderTimeline(payload.analysis?.events || [], roundStartMs);
        renderHighlights(demoId, payload.highlights || [], roundStartMs);
        renderRenderJobs(payload.renders || []);
        renderPlayerStats(payload.player_stats);

        if (payload.status === 'analyzed') {
            renderCrossref(demoId);
        }

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
