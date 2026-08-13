/**
 * Uploads Library Module
 * Browse, upload, and download community files (configs, HUDs, archives, clips).
 */

import { API_BASE, fetchJSON, escapeHtml, escapeJsString } from './utils.js';
import { ensureCurrentUser } from './auth.js?v=20260804-auth-dedupe';

let currentCategory = '';
let currentOffset = 0;
let currentSort = 'newest';
const PAGE_SIZE = 50;

// Category config: colors, icons (SVG paths), glow colors
const CATEGORIES = {
    config: {
        label: 'Config',
        color: 'text-brand-cyan border-brand-cyan/30 bg-brand-cyan/10',
        glow: 'rgba(6,182,212,0.15)',
        icon: `<svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>`,
    },
    hud: {
        label: 'HUD',
        color: 'text-brand-purple border-brand-purple/30 bg-brand-purple/10',
        glow: 'rgba(139,92,246,0.15)',
        icon: `<svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>`,
    },
    archive: {
        label: 'Archive',
        color: 'text-brand-amber border-brand-amber/30 bg-brand-amber/10',
        glow: 'rgba(245,158,11,0.15)',
        icon: `<svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/></svg>`,
    },
    clip: {
        label: 'Clip',
        color: 'text-brand-emerald border-brand-emerald/30 bg-brand-emerald/10',
        glow: 'rgba(16,185,129,0.15)',
        icon: `<svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg>`,
    },
};

// ============================================================================
// TOAST NOTIFICATION SYSTEM
// ============================================================================

function showToast(message, type = 'success') {
    const colors = {
        success: 'from-brand-emerald/90 to-emerald-700/90 border-brand-emerald/50',
        error: 'from-brand-rose/90 to-rose-700/90 border-brand-rose/50',
        info: 'from-brand-blue/90 to-blue-700/90 border-brand-blue/50',
    };
    const icons = {
        success: `<svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>`,
        error: `<svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>`,
        info: `<svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>`,
    };

    const toast = document.createElement('div');
    toast.className = `fixed bottom-6 right-6 z-[60] flex items-center gap-2.5 px-4 py-3 rounded-xl border bg-gradient-to-r ${colors[type] || colors.info} text-white text-sm font-medium shadow-2xl backdrop-blur-sm`;
    toast.style.cssText = 'transform: translateY(20px); opacity: 0; transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);';
    toast.innerHTML = `${icons[type] || icons.info}<span>${escapeHtml(message)}</span>`;

    document.body.appendChild(toast);
    requestAnimationFrame(() => {
        toast.style.transform = 'translateY(0)';
        toast.style.opacity = '1';
    });

    setTimeout(() => {
        toast.style.transform = 'translateY(20px)';
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ============================================================================
// SKELETON LOADING
// ============================================================================

function renderSkeletonCards(count = 6) {
    return Array(count).fill(0).map((_, i) => `
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
            <div class="flex gap-2 mt-auto pt-1">
                <div class="flex-1 h-8 bg-slate-700/30 rounded-lg"></div>
                <div class="flex-1 h-8 bg-slate-700/30 rounded-lg"></div>
            </div>
        </div>
    `).join('');
}

// ============================================================================
// LOAD UPLOADS VIEW
// ============================================================================

export async function loadUploadsView() {
    setupUploadForm();
    setupDragDrop();
    loadPopularTags();
    await loadUploadsList();
}

// ============================================================================
// DRAG & DROP UPLOAD ZONE
// ============================================================================

// Extension → category + per-category size cap, mirroring the backend
// (upload_validators: detect_category + SIZE_LIMITS). Used to give the uploader
// immediate, inline feedback about how their file will be categorised and
// whether it's within limits — before they submit.
// Mirrors backend upload_validators.ALLOWED_EXTENSIONS EXACTLY: detect_category
// puts .hud under 'config' (there is no separate 'hud' category), so the feedback
// shows the category the backend will actually assign — not a guess that diverges.
const _EXT_CATEGORY = {
    '.cfg': 'config', '.hud': 'config',
    '.zip': 'archive', '.rar': 'archive',
    '.mp4': 'clip', '.avi': 'clip', '.mkv': 'clip',
};
const _SIZE_LIMIT_MB = { config: 2, archive: 50, clip: 500 };  // backend SIZE_LIMITS

// Reflect a just-chosen file in the inline feedback strip: detected category +
// size when valid, a clear reason when not, and disable the submit button on an
// invalid file so it can't be sent. Returns whether the file is acceptable.
function _updateFileFeedback(file) {
    const fb = document.getElementById('upload-file-feedback');
    const submitBtn = document.getElementById('upload-submit-btn');
    if (!fb) return true;
    if (!file) {
        fb.className = 'hidden';
        fb.textContent = '';
        if (submitBtn) submitBtn.disabled = false;
        return true;
    }
    const name = file.name.toLowerCase();
    const ext = name.includes('.') ? '.' + name.split('.').pop() : '';
    const cat = _EXT_CATEGORY[ext];
    const sizeStr = formatFileSize(file.size);

    let ok = true;
    let msg = '';
    if (!cat) {
        ok = false;
        msg = `Unsupported type ${ext || '(none)'} — allowed: .cfg .hud .zip .rar .mp4 .avi .mkv`;
    } else {
        const maxMB = _SIZE_LIMIT_MB[cat] || 50;
        if (file.size > maxMB * 1024 * 1024) {
            ok = false;
            msg = `Too large: ${sizeStr} (max ${maxMB} MB for ${cat})`;
        }
    }

    if (ok) {
        const meta = CATEGORIES[cat] || { label: cat };
        const note = (cat === 'clip' && !isBrowserPlayable(ext))
            ? ' · not playable in the browser (download-only)' : '';
        fb.className = 'rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-300 px-3 py-2 text-xs flex items-center gap-2 flex-wrap';
        // Build with textContent (no innerHTML) — file.name is untrusted, and DOM
        // text can never be reinterpreted as markup.
        fb.textContent = '';
        const label = document.createElement('span');
        label.className = 'font-bold uppercase tracking-wider';
        label.textContent = meta.label || cat;
        const detail = document.createElement('span');
        detail.className = 'text-slate-400';
        detail.textContent = `${file.name} · ${sizeStr}${note}`;
        fb.append(label, detail);
    } else {
        fb.className = 'rounded-lg border border-rose-500/30 bg-rose-500/10 text-rose-300 px-3 py-2 text-xs';
        fb.textContent = msg;
    }
    if (submitBtn) submitBtn.disabled = !ok;
    return ok;
}

// Shared handler for both drop and file-input change: show the name and the
// inline feedback in one place.
function _onFileSelected(file) {
    const nameEl = document.getElementById('upload-drop-filename');
    if (nameEl) {
        if (file) {
            nameEl.textContent = file.name;
            nameEl.classList.remove('hidden');
        } else {
            // Symmetric reset: no file → clear the shown name too, not just the
            // feedback strip, so nothing stale lingers (Copilot #719).
            nameEl.textContent = '';
            nameEl.classList.add('hidden');
        }
    }
    _updateFileFeedback(file);
}

function setupDragDrop() {
    const zone = document.getElementById('upload-drop-zone');
    if (!zone) return;
    // loadUploadsView() runs on EVERY entry to the route, and these elements are
    // static in index.html — they are never torn down — so without this each
    // visit stacked another copy of every listener below (Codex/master review
    // P1-2). The dataset flag lives on the element itself, so it survives
    // exactly as long as the listeners do.
    if (zone.dataset.dropBound === '1') return;
    zone.dataset.dropBound = '1';

    const fileInput = document.getElementById('upload-file-input');

    // No click listener here: the zone is now a <label for="upload-file-input">
    // (index.html), so the browser opens the file picker natively on click AND
    // on keyboard activation once the input has focus — a manual fileInput.click()
    // here would double-open it (#621 review).
    zone.addEventListener('dragover', (e) => {
        e.preventDefault();
        zone.classList.add('upload-drop-active');
    });

    zone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        zone.classList.remove('upload-drop-active');
    });

    zone.addEventListener('drop', (e) => {
        e.preventDefault();
        zone.classList.remove('upload-drop-active');
        if (e.dataTransfer.files.length && fileInput) {
            fileInput.files = e.dataTransfer.files;
            _onFileSelected(e.dataTransfer.files[0]);
        }
    });

    // Same feedback on a normal file-picker selection. Only act when a file is
    // actually present: cancelling the picker fires no change on most browsers,
    // but guarding here also keeps a spurious empty change from wiping the
    // feedback for an already-chosen file (Copilot #719).
    if (fileInput) {
        fileInput.addEventListener('change', () => {
            if (fileInput.files.length) _onFileSelected(fileInput.files[0]);
        });
    }
}

// ============================================================================
// UPLOAD FORM
// ============================================================================

function setupUploadForm() {
    const form = document.getElementById('upload-form');
    const formSection = document.getElementById('upload-form-section');
    const authActions = document.getElementById('upload-auth-actions');

    // Check if user is logged in (session cookie). Reuses the startup probe
    // rather than issuing a second /auth/me.
    ensureCurrentUser()
        .then(user => {
            if (user && user.id) {
                if (formSection) formSection.classList.remove('hidden');
                if (authActions) {
                    authActions.innerHTML = `<span class="text-xs text-slate-400">Logged in as <span class="text-brand-cyan font-bold">${escapeHtml(user.username || 'User')}</span></span>`;
                }
            } else {
                if (authActions) {
                    authActions.innerHTML = `
                        <a href="/auth/discord" class="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[#5865F2]/20 border border-[#5865F2]/30 text-[#5865F2] text-xs font-bold hover:bg-[#5865F2]/30 transition">
                            <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M20.317 4.37a19.791 19.791 0 00-4.885-1.515.074.074 0 00-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 00-5.487 0 12.64 12.64 0 00-.617-1.25.077.077 0 00-.079-.037A19.736 19.736 0 003.677 4.37a.07.07 0 00-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 00.031.057 19.9 19.9 0 005.993 3.03.078.078 0 00.084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 00-.041-.106 13.107 13.107 0 01-1.872-.892.077.077 0 01-.008-.128 10.2 10.2 0 00.372-.292.074.074 0 01.077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 01.078.01c.12.098.246.198.373.292a.077.077 0 01-.006.127 12.299 12.299 0 01-1.873.892.077.077 0 00-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 00.084.028 19.839 19.839 0 006.002-3.03.077.077 0 00.032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 00-.031-.03z"/></svg>
                            Log in to upload
                        </a>`;
                }
            }
        })
        .catch(err => console.warn('Upload auth check failed:', err));

    if (!form) return;
    // Same re-entry problem, and this one duplicated the UPLOAD itself: two
    // visits meant handleUpload() fired twice per submit.
    if (form.dataset.submitBound === '1') return;
    form.dataset.submitBound = '1';
    form.addEventListener('submit', handleUpload);
}

// Capture a poster thumbnail from the first ~1s of a video file, entirely in the
// browser (no server ffmpeg). Best-effort: returns null on any failure so the
// upload proceeds without a poster (the card falls back to the category icon).
function _capturePoster(file) {
    return new Promise((resolve) => {
        let settled = false;
        let timer = null;
        // Single settle point: clear the give-up timer here so it never fires
        // after the promise has resolved (whichever path resolves first).
        const finish = (blob) => { if (settled) return; settled = true; clearTimeout(timer); resolve(blob); };
        try {
            const url = URL.createObjectURL(file);
            const video = document.createElement('video');
            video.muted = true;
            video.preload = 'metadata';
            const cleanup = () => { try { URL.revokeObjectURL(url); } catch { /* ignore */ } };
            const fail = () => { cleanup(); finish(null); };
            timer = setTimeout(fail, 8000);  // give up on a slow/corrupt file
            video.addEventListener('error', fail, { once: true });
            video.addEventListener('loadeddata', () => {
                try { video.currentTime = Math.min(1, (video.duration || 2) / 2); }
                catch { fail(); }
            }, { once: true });
            video.addEventListener('seeked', () => {
                clearTimeout(timer);
                try {
                    const w = video.videoWidth, h = video.videoHeight;
                    if (!w || !h) { fail(); return; }
                    const scale = Math.min(1, 640 / w);  // cap poster width for a thumbnail
                    const canvas = document.createElement('canvas');
                    canvas.width = Math.round(w * scale);
                    canvas.height = Math.round(h * scale);
                    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
                    canvas.toBlob((blob) => { cleanup(); finish(blob); }, 'image/jpeg', 0.8);
                } catch { fail(); }
            }, { once: true });
            video.src = url;
        } catch { finish(null); }
    });
}

async function handleUpload(e) {
    e.preventDefault();

    const fileInput = document.getElementById('upload-file-input');
    const titleInput = document.getElementById('upload-title-input');
    const descInput = document.getElementById('upload-desc-input');
    const tagsInput = document.getElementById('upload-tags-input');
    const submitBtn = document.getElementById('upload-submit-btn');
    const progressWrap = document.getElementById('upload-progress-wrap');
    const progressBar = document.getElementById('upload-progress-bar');
    const progressText = document.getElementById('upload-progress-text');

    if (!fileInput.files.length) return;

    const file = fileInput.files[0];

    // Client-side file type validation
    const allowedExts = ['.cfg', '.hud', '.zip', '.rar', '.mp4', '.avi', '.mkv'];
    const fileName = file.name.toLowerCase();
    if (!allowedExts.some(ext => fileName.endsWith(ext))) {
        showToast(`Invalid file type. Allowed: ${allowedExts.join(', ')}`, 'error');
        return;
    }

    // Client-side file size validation
    const ext = '.' + fileName.split('.').pop();
    const sizeLimits = { '.cfg': 2, '.hud': 2, '.zip': 50, '.rar': 50, '.mp4': 500, '.avi': 500, '.mkv': 500 };
    const maxMB = sizeLimits[ext] || 50;
    if (file.size > maxMB * 1024 * 1024) {
        showToast(`File too large (max ${maxMB}MB for ${ext})`, 'error');
        return;
    }

    submitBtn.disabled = true;
    submitBtn.classList.add('opacity-50', 'cursor-not-allowed');
    if (progressWrap) progressWrap.classList.remove('hidden');
    if (progressBar) progressBar.style.width = '0%';
    if (progressText) progressText.textContent = '0%';

    const formData = new FormData();
    formData.append('file', file);
    if (titleInput.value.trim()) formData.append('title', titleInput.value.trim());
    if (descInput.value.trim()) formData.append('description', descInput.value.trim());
    if (tagsInput.value.trim()) formData.append('tags', tagsInput.value.trim());
    // Empty value = keep forever, which is the default and the first option.
    // Send nothing in that case: the backend treats an absent retention_days as
    // lifetime, so "" would have to be parsed into None somewhere, and an empty
    // string reaching an int field is a 422 waiting to happen.
    const retentionSelect = document.getElementById('upload-retention-select');
    if (retentionSelect && retentionSelect.value) {
        formData.append('retention_days', retentionSelect.value);
    }

    // Capture a poster thumbnail for playable clips (best-effort; never blocks
    // the upload — a null poster just means the card shows the category icon).
    if (fileName.endsWith('.mp4')) {
        const posterBlob = await _capturePoster(file);
        if (posterBlob) formData.append('poster', posterBlob, 'poster.jpg');
    }

    try {
        const data = await new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhr.upload.addEventListener('progress', (ev) => {
                if (ev.lengthComputable) {
                    const pct = Math.round((ev.loaded / ev.total) * 100);
                    if (progressBar) progressBar.style.width = `${pct}%`;
                    if (progressText) progressText.textContent = `${pct}%`;
                }
            });
            xhr.addEventListener('load', () => {
                if (xhr.status >= 200 && xhr.status < 300) {
                    resolve(JSON.parse(xhr.responseText));
                } else {
                    try {
                        const err = JSON.parse(xhr.responseText);
                        reject(new Error(err.detail || `HTTP ${xhr.status}`));
                    } catch { reject(new Error(`HTTP ${xhr.status}`)); }
                }
            });
            xhr.addEventListener('error', () => reject(new Error('Network error')));
            xhr.addEventListener('abort', () => reject(new Error('Upload cancelled')));
            xhr.open('POST', `${API_BASE}/uploads`);
            xhr.withCredentials = true;
            xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');  // CSRF
            xhr.send(formData);
        });

        showToast(`Uploaded: ${data.filename}`, 'success');

        // Reset form
        fileInput.value = '';
        titleInput.value = '';
        descInput.value = '';
        tagsInput.value = '';
        // Back to Forever, like every other field goes back to empty. Leaving
        // "7 days" selected would silently apply it to the NEXT upload too,
        // which is the one choice here a user cannot undo later (CodeRabbit
        // on #615).
        if (retentionSelect) retentionSelect.value = '';
        _onFileSelected(null);  // clear the shown name + feedback, re-enable submit

        await loadUploadsList();
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        submitBtn.disabled = false;
        submitBtn.classList.remove('opacity-50', 'cursor-not-allowed');
        if (progressWrap) progressWrap.classList.add('hidden');
    }
}

// ============================================================================
// BROWSE UPLOADS
// ============================================================================

async function loadUploadsList() {
    const grid = document.getElementById('upload-grid');
    if (!grid) return;

    // Show skeleton loading
    grid.innerHTML = renderSkeletonCards(6);

    const search = document.getElementById('upload-search-input')?.value || '';
    const params = new URLSearchParams({ limit: PAGE_SIZE, offset: currentOffset, sort: currentSort });
    if (currentCategory) params.set('category', currentCategory);
    if (search.trim()) params.set('search', search.trim());

    try {
        const data = await fetchJSON(`${API_BASE}/uploads?${params}`);
        const items = data.items || [];

        if (items.length === 0) {
            grid.innerHTML = renderEmptyState();
            renderPagination(0);
            return;
        }

        grid.innerHTML = items.map((item, i) => renderUploadCard(item, i)).join('');
        renderPagination(data.total || 0);
    } catch (err) {
        grid.innerHTML = `
            <div class="col-span-full">
                <div class="glass-card rounded-xl p-10 text-center">
                    <svg class="w-10 h-10 mx-auto mb-3 text-brand-rose/60" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"/></svg>
                    <div class="text-sm font-bold text-brand-rose mb-1">Failed to load uploads</div>
                    <div class="text-xs text-slate-500">${escapeHtml(err.message)}</div>
                </div>
            </div>`;
    }
}

function renderEmptyState() {
    return `
        <div class="col-span-full">
            <div class="glass-card rounded-xl p-12 text-center">
                <div class="w-16 h-16 mx-auto mb-4 rounded-2xl bg-slate-800/80 flex items-center justify-center">
                    <svg class="w-8 h-8 text-slate-400" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/></svg>
                </div>
                <h3 class="text-base font-bold text-slate-300 mb-1">No uploads found</h3>
                <p class="text-xs text-slate-500 max-w-xs mx-auto">Try adjusting your filters or search, or be the first to upload something.</p>
            </div>
        </div>`;
}

function renderUploadCard(item, index = 0) {
    const cat = CATEGORIES[item.category] || { label: item.category, color: 'text-slate-400 border-white/10 bg-white/5', glow: 'rgba(255,255,255,0.05)', icon: '' };
    const sizeStr = formatFileSize(item.file_size_bytes || 0);
    const isVideo = isVideoFile(item.extension);
    const canPlay = isBrowserPlayable(item.extension);
    const delay = Math.min(index * 0.05, 0.3);

    return `
        <div class="group relative" style="animation: fadeSlideUp 0.4s ease-out both; animation-delay: ${delay}s;">
            <!-- Glow effect on hover -->
            <div class="absolute -inset-[1px] rounded-xl opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none"
                 style="background: linear-gradient(135deg, ${cat.glow}, transparent 60%);"></div>

            <div class="glass-card relative rounded-xl p-5 flex flex-col gap-3 h-full">
                ${item.poster_url ? `
                <!-- Poster thumbnail (lazy) with a play overlay for playable clips -->
                <button data-poster ${canPlay
                    ? `onclick="window.openVideoPlayer('${escapeJsString(item.id)}', '${escapeJsString(item.title || item.filename)}')" aria-label="Play ${escapeHtml(item.title || item.filename)}"`
                    : 'aria-hidden="true" tabindex="-1"'}
                    class="relative block w-full aspect-video rounded-lg overflow-hidden bg-black/40 ${canPlay ? 'cursor-pointer' : 'cursor-default'}">
                    <img loading="lazy" src="${escapeHtml(item.poster_url)}" alt=""
                        onerror="this.closest('[data-poster]').remove()"
                        class="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105">
                    ${canPlay ? `
                    <span class="absolute inset-0 flex items-center justify-center bg-black/10 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                        <span class="w-12 h-12 rounded-full bg-black/60 flex items-center justify-center ring-1 ring-white/20">
                            <svg class="w-6 h-6 text-white ml-0.5" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                        </span>
                    </span>` : ''}
                </button>
                ` : ''}
                <!-- Header: icon + title + badge -->
                <div class="flex items-start gap-3">
                    <div class="w-10 h-10 rounded-lg shrink-0 flex items-center justify-center border ${cat.color}">
                        ${cat.icon}
                    </div>
                    <div class="min-w-0 flex-1">
                        <div class="text-sm font-bold text-white truncate group-hover:text-brand-cyan transition-colors duration-200">${escapeHtml(item.title || item.filename)}</div>
                        <div class="text-[11px] text-slate-500 truncate font-mono">${escapeHtml(item.filename)}</div>
                    </div>
                    <span class="shrink-0 inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase border ${cat.color}">
                        <span class="w-1.5 h-1.5 rounded-full bg-current"></span>
                        ${escapeHtml(cat.label)}
                    </span>
                </div>

                <!-- Meta row -->
                <div class="flex items-center justify-between text-[11px] text-slate-500">
                    <span class="flex items-center gap-1.5">
                        <svg class="w-3 h-3 text-slate-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0"/></svg>
                        ${escapeHtml(item.uploader_name || 'Anonymous')}
                    </span>
                    <span>${sizeStr}</span>
                </div>
                <div class="flex items-center justify-between text-[11px] text-slate-400">
                    <span>${item.created_at ? new Date(item.created_at).toLocaleDateString() : ''}</span>
                    <span class="flex items-center gap-1">
                        <svg class="w-3 h-3" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3"/></svg>
                        ${item.download_count || 0}
                    </span>
                </div>
                ${item.description_preview ? `
                <div class="text-[11px] text-slate-500 leading-snug" style="display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;">${escapeHtml(item.description_preview)}</div>` : ''}

                <!-- Actions -->
                <div class="mt-auto flex gap-2 pt-1">
                    ${canPlay ? `
                    <button onclick="window.openVideoPlayer('${escapeJsString(item.id)}', '${escapeJsString(item.title || item.filename)}')"
                        class="flex-1 inline-flex items-center justify-center gap-1.5 bg-brand-emerald/15 hover:bg-brand-emerald/25 text-brand-emerald text-xs font-bold px-3 py-2 rounded-lg transition-all duration-200 hover:shadow-[0_0_12px_rgba(16,185,129,0.2)]">
                        <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                        Watch
                    </button>` : (isVideo ? `
                    <span title="${escapeHtml(item.extension)} isn't playable in the browser — download to watch"
                        class="flex-1 inline-flex items-center justify-center gap-1.5 bg-white/[0.03] text-slate-500 text-xs font-semibold px-3 py-2 rounded-lg cursor-default">
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"/></svg>
                        DL only
                    </span>` : '')}
                    <a href="#/uploads/${encodeURIComponent(item.id)}"
                        class="flex-1 inline-flex items-center justify-center gap-1.5 bg-brand-purple/15 hover:bg-brand-purple/25 text-brand-purple text-xs font-bold px-3 py-2 rounded-lg transition-all duration-200 hover:shadow-[0_0_12px_rgba(139,92,246,0.2)]">
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m9.86-2.54a4.5 4.5 0 00-6.364-6.364L4.5 8.25"/></svg>
                        Share
                    </a>
                    <a href="${API_BASE}/uploads/${encodeURIComponent(item.id)}/download?force_download=true" download
                        class="flex-1 inline-flex items-center justify-center gap-1.5 bg-brand-blue/15 hover:bg-brand-blue/25 text-brand-blue text-xs font-bold px-3 py-2 rounded-lg transition-all duration-200 hover:shadow-[0_0_12px_rgba(59,130,246,0.2)]">
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3"/></svg>
                        Download
                    </a>
                </div>
            </div>
        </div>
    `;
}

function renderPagination(total) {
    const container = document.getElementById('upload-pagination');
    if (!container) return;

    const pages = Math.ceil(total / PAGE_SIZE);
    const currentPage = Math.floor(currentOffset / PAGE_SIZE) + 1;
    const rangeStart = total === 0 ? 0 : currentOffset + 1;
    const rangeEnd = Math.min(currentOffset + PAGE_SIZE, total);
    const rangeText = `Page ${currentPage} of ${Math.max(pages, 1)} • showing ${rangeStart}–${rangeEnd} of ${total} upload${total !== 1 ? 's' : ''}`;

    if (pages <= 1) {
        container.textContent = '';
        if (total > 0) {
            const info = document.createElement('div');
            info.className = 'text-[11px] text-slate-400';
            info.textContent = rangeText;
            container.appendChild(info);
        }
        return;
    }

    let html = '<div class="flex items-center gap-1">';

    // Prev
    if (currentPage > 1) {
        html += `<button onclick="window.uploadPage(${currentPage - 2})" class="px-3 py-1.5 rounded-lg text-xs font-bold text-slate-400 hover:text-white hover:bg-white/5 transition">Prev</button>`;
    }

    // Page numbers (show max 5 pages around current)
    const startPage = Math.max(1, currentPage - 2);
    const endPage = Math.min(pages, startPage + 4);
    for (let p = startPage; p <= endPage; p++) {
        if (p === currentPage) {
            html += `<span class="px-3 py-1.5 rounded-lg text-xs font-bold bg-brand-blue/20 text-brand-blue border border-brand-blue/30">${p}</span>`;
        } else {
            html += `<button onclick="window.uploadPage(${p - 1})" class="px-3 py-1.5 rounded-lg text-xs font-bold text-slate-500 hover:text-white hover:bg-white/5 transition">${p}</button>`;
        }
    }

    // Next
    if (currentPage < pages) {
        html += `<button onclick="window.uploadPage(${currentPage})" class="px-3 py-1.5 rounded-lg text-xs font-bold text-slate-400 hover:text-white hover:bg-white/5 transition">Next</button>`;
    }

    html += '</div>';
    html += `<div class="text-[11px] text-slate-400">${rangeText}</div>`;

    container.innerHTML = html;
}

function setUploadSort(sort) {
    if (sort === currentSort) return;
    currentSort = sort;
    currentOffset = 0;
    loadUploadsList();
}

// ============================================================================
// TAGS
// ============================================================================

async function loadPopularTags() {
    const container = document.getElementById('upload-popular-tags');
    if (!container) return;

    try {
        const tags = await fetchJSON(`${API_BASE}/uploads/tags/popular?limit=15`);
        if (!tags || tags.length === 0) {
            container.innerHTML = '';
            return;
        }
        container.innerHTML = tags.map(t =>
            `<button onclick="window.filterUploadsByTag('${escapeJsString(t.tag)}')"
                class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-bold text-slate-400 border border-white/10 hover:border-brand-cyan/40 hover:text-brand-cyan hover:bg-brand-cyan/5 transition-all duration-200">
                <span class="opacity-60">#</span>${escapeHtml(t.tag)}
                <span class="text-slate-400 ml-0.5">${t.count}</span>
            </button>`
        ).join('');
    } catch (err) {
        console.warn('Failed to load popular tags:', err);
        container.innerHTML = '';
    }
}

// ============================================================================
// FILTERS
// ============================================================================

function filterUploads(category) {
    currentCategory = category;
    currentOffset = 0;

    document.querySelectorAll('.upload-filter-btn').forEach(btn => {
        const isActive = btn.dataset.category === category;
        btn.classList.toggle('upload-filter-active', isActive);
    });

    loadUploadsList();
}

function filterUploadsByTag(tag) {
    const searchInput = document.getElementById('upload-search-input');
    if (searchInput) searchInput.value = '';
    currentCategory = '';
    currentOffset = 0;

    const grid = document.getElementById('upload-grid');
    if (!grid) return;

    grid.innerHTML = renderSkeletonCards(6);

    const params = new URLSearchParams({ limit: PAGE_SIZE, offset: 0, tag });
    fetchJSON(`${API_BASE}/uploads?${params}`)
        .then(data => {
            const items = data.items || [];
            if (items.length === 0) {
                grid.innerHTML = `
                    <div class="col-span-full">
                        <div class="glass-card rounded-xl p-10 text-center">
                            <div class="text-sm font-bold text-slate-400 mb-1">No uploads tagged "${escapeHtml(tag)}"</div>
                            <div class="text-xs text-slate-400">Try a different tag or browse all uploads</div>
                        </div>
                    </div>`;
            } else {
                grid.innerHTML = items.map((item, i) => renderUploadCard(item, i)).join('');
            }
            renderPagination(data.total || 0);
        })
        .catch(err => {
            grid.innerHTML = `<div class="text-center py-12 text-brand-rose col-span-full">Error: ${escapeHtml(err.message)}</div>`;
        });
}

function uploadPage(page) {
    currentOffset = page * PAGE_SIZE;
    loadUploadsList();
}

// ============================================================================
// HELPERS
// ============================================================================

function isVideoFile(ext) {
    if (!ext) return false;
    return ['.mp4', '.avi', '.mkv'].includes(ext.toLowerCase());
}

// Browsers reliably play .mp4 (H.264/AAC); .avi/.mkv are NOT natively playable,
// so they stay download-only with a clear hint until a server-side .mp4
// transcode is added — the owner's future option 3 (see
// docs/UPLOADS_MEDIA_NOTES.md). isVideoFile() still recognises them as videos;
// only isBrowserPlayable() gates inline playback.
function isBrowserPlayable(ext) {
    return (ext || '').toLowerCase() === '.mp4';
}

const _PLAYBACK_SPEEDS = [0.5, 1, 1.25, 1.5, 2];
let _lastFocusedBeforeModal = null;
let _volumeSaveHandler = null;

function openVideoPlayer(uploadId, title) {
    const existing = document.getElementById('video-player-modal');
    if (existing) existing.remove();

    _lastFocusedBeforeModal = document.activeElement;
    const videoUrl = `${API_BASE}/uploads/${encodeURIComponent(uploadId)}/download`;

    const modal = document.createElement('div');
    modal.id = 'video-player-modal';
    modal.className = 'fixed inset-0 z-50 flex items-center justify-center';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-label', `Video player: ${title}`);
    modal.style.cssText = 'background: rgba(0,0,0,0); transition: background 0.3s ease;';
    modal.innerHTML = `
        <div class="absolute inset-0 backdrop-blur-md"></div>
        <div class="relative w-full max-w-5xl mx-4" style="transform: scale(0.95); opacity: 0; transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);">
            <div class="flex items-center justify-between mb-3 px-1 gap-2">
                <h3 class="text-sm font-bold text-white truncate pr-2 flex items-center gap-2 min-w-0">
                    <svg class="w-4 h-4 text-brand-emerald shrink-0" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                    <span class="truncate">${escapeHtml(title)}</span>
                </h3>
                <div class="flex items-center gap-1.5 shrink-0">
                    <select id="video-speed-select" aria-label="Playback speed"
                        class="h-8 rounded-lg bg-white/10 hover:bg-white/15 text-slate-200 text-xs font-semibold px-2 outline-none border border-white/10 cursor-pointer">
                        ${_PLAYBACK_SPEEDS.map(s => `<option value="${s}"${s === 1 ? ' selected' : ''}>${s}×</option>`).join('')}
                    </select>
                    <button id="video-pip-btn" title="Picture-in-picture (P)" aria-label="Picture-in-picture"
                        class="w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:text-white hover:bg-white/10 transition">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="2"/><rect x="12" y="11" width="7" height="6" rx="1" fill="currentColor" stroke="none"/></svg>
                    </button>
                    <button onclick="window.closeVideoPlayer()" title="Close (Esc)" aria-label="Close video"
                        class="w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:text-white hover:bg-white/10 transition">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
                    </button>
                </div>
            </div>
            <div class="rounded-xl overflow-hidden shadow-[0_25px_60px_-12px_rgba(0,0,0,0.8)] ring-1 ring-white/10">
                <video id="video-player-element" controls autoplay playsinline
                    class="w-full bg-black" style="max-height: 80vh;">
                    <source src="${videoUrl}" type="video/mp4">
                    Your browser does not support video playback.
                </video>
            </div>
            <div class="mt-2 px-1 text-[11px] text-slate-500 flex flex-wrap gap-x-3 gap-y-0.5">
                <span>Space play/pause</span><span>&larr; &rarr; seek</span><span>&uarr; &darr; volume</span><span>F fullscreen</span><span>M mute</span><span>P picture-in-picture</span>
            </div>
        </div>
    `;

    modal.addEventListener('click', (e) => {
        if (e.target === modal || e.target.classList.contains('backdrop-blur-md')) closeVideoPlayer();
    });

    document.body.appendChild(modal);

    const video = modal.querySelector('video');
    // Restore the viewer's last volume (persisted across sessions).
    const savedVol = parseFloat(localStorage.getItem('slomix-video-volume'));
    if (!Number.isNaN(savedVol)) video.volume = Math.min(1, Math.max(0, savedVol));
    _volumeSaveHandler = () => localStorage.setItem('slomix-video-volume', String(video.volume));
    video.addEventListener('volumechange', _volumeSaveHandler);

    const speedSel = modal.querySelector('#video-speed-select');
    if (speedSel) speedSel.addEventListener('change', () => { video.playbackRate = parseFloat(speedSel.value) || 1; });

    const pipBtn = modal.querySelector('#video-pip-btn');
    if (pipBtn) {
        if (!document.pictureInPictureEnabled) pipBtn.style.display = 'none';
        else pipBtn.addEventListener('click', () => _togglePip(video));
    }

    // Animate in
    requestAnimationFrame(() => {
        modal.style.background = 'rgba(0,0,0,0.85)';
        const inner = modal.querySelector('.relative');
        if (inner) {
            inner.style.transform = 'scale(1)';
            inner.style.opacity = '1';
        }
    });

    // Capture phase so our shortcuts win before the video's native handling,
    // and so Tab is trapped inside the modal.
    document.addEventListener('keydown', handleVideoKeydown, true);
    video.focus({ preventScroll: true });
}

async function _togglePip(video) {
    try {
        if (document.pictureInPictureElement) await document.exitPictureInPicture();
        else if (video) await video.requestPictureInPicture();
    } catch { /* PiP can be blocked by the browser; ignore */ }
}

function _toggleFullscreen(el) {
    // requestFullscreen/exitFullscreen return Promises; a rejection (fullscreen
    // blocked by the browser/permissions) is async and NOT caught by try/catch,
    // so swallow it on the promise itself to avoid an unhandled rejection
    // (CodeRabbit #717).
    try {
        const p = document.fullscreenElement
            ? document.exitFullscreen()
            : (el && el.requestFullscreen ? el.requestFullscreen() : null);
        if (p && typeof p.catch === 'function') p.catch(() => { /* fullscreen denied; ignore */ });
    } catch { /* synchronous failure (unsupported); ignore */ }
}

function handleVideoKeydown(e) {
    const modal = document.getElementById('video-player-modal');
    if (!modal) return;

    // Focus trap: keep Tab within the modal (accessibility).
    if (e.key === 'Tab') {
        const focusables = modal.querySelectorAll('button, select, video, [tabindex]:not([tabindex="-1"])');
        if (focusables.length) {
            const first = focusables[0];
            const last = focusables[focusables.length - 1];
            if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
            else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
        }
        return;
    }

    // Never hijack typing in the speed <select>.
    if (e.target && e.target.tagName === 'SELECT') return;
    const video = modal.querySelector('video');
    if (!video) return;

    switch (e.key) {
        case 'Escape': closeVideoPlayer(); break;
        case ' ': case 'k': e.preventDefault(); if (video.paused) { video.play(); } else { video.pause(); } break;
        case 'ArrowLeft': e.preventDefault(); video.currentTime = Math.max(0, video.currentTime - 5); break;
        case 'ArrowRight': e.preventDefault(); video.currentTime = Math.min(video.duration || Infinity, video.currentTime + 5); break;
        case 'ArrowUp': e.preventDefault(); video.volume = Math.min(1, video.volume + 0.1); break;
        case 'ArrowDown': e.preventDefault(); video.volume = Math.max(0, video.volume - 0.1); break;
        case 'f': case 'F': e.preventDefault(); _toggleFullscreen(modal.querySelector('.relative') || video); break;
        case 'm': case 'M': e.preventDefault(); video.muted = !video.muted; break;
        case 'p': case 'P': e.preventDefault(); _togglePip(video); break;
        default: break;
    }
}

function closeVideoPlayer() {
    const modal = document.getElementById('video-player-modal');
    if (modal) {
        const video = modal.querySelector('video');
        if (video) {
            if (_volumeSaveHandler) video.removeEventListener('volumechange', _volumeSaveHandler);
            // Pause AND release the stream (clear src + load) so closing frees the
            // buffered download, not just pauses it.
            video.pause();
            video.querySelectorAll('source').forEach((s) => s.removeAttribute('src'));
            video.removeAttribute('src');
            try { video.load(); } catch { /* ignore */ }
        }
        const inner = modal.querySelector('.relative');
        if (inner) {
            inner.style.transform = 'scale(0.95)';
            inner.style.opacity = '0';
        }
        modal.style.background = 'rgba(0,0,0,0)';
        setTimeout(() => modal.remove(), 300);
    }
    document.removeEventListener('keydown', handleVideoKeydown, true);
    _volumeSaveHandler = null;
    // Restore focus to whatever opened the modal (accessibility).
    if (_lastFocusedBeforeModal && typeof _lastFocusedBeforeModal.focus === 'function') {
        try { _lastFocusedBeforeModal.focus({ preventScroll: true }); } catch { /* ignore */ }
    }
    _lastFocusedBeforeModal = null;
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return (bytes / Math.pow(1024, i)).toFixed(i > 0 ? 1 : 0) + ' ' + units[i];
}

// ============================================================================
// UPLOAD DETAIL VIEW (shareable link page)
// ============================================================================

export async function loadUploadDetail(uploadId) {
    const container = document.getElementById('upload-detail-content');
    if (!container) return;

    // Skeleton loading for detail
    container.innerHTML = `
        <div class="space-y-6 animate-pulse">
            <div class="h-8 bg-slate-700/50 rounded w-2/3"></div>
            <div class="h-4 bg-slate-700/30 rounded w-1/3"></div>
            <div class="aspect-video bg-slate-800/50 rounded-xl"></div>
            <div class="grid grid-cols-4 gap-4">
                ${Array(4).fill('<div class="h-20 bg-slate-700/30 rounded-lg"></div>').join('')}
            </div>
        </div>`;

    try {
        const data = await fetchJSON(`${API_BASE}/uploads/${encodeURIComponent(uploadId)}`);

        const sizeStr = formatFileSize(data.file_size_bytes || 0);
        const canPlay = isBrowserPlayable(data.extension);
        const isVideoNotPlayable = isVideoFile(data.extension) && !canPlay;  // .avi/.mkv
        const shareUrl = `${window.location.origin}${window.location.pathname}#/uploads/${encodeURIComponent(data.id)}`;
        const downloadUrl = `${API_BASE}/uploads/${encodeURIComponent(data.id)}/download?force_download=true`;
        // Inline playback streams from the non-force URL (the backend serves .mp4
        // inline there); force_download is only for the explicit Download button.
        const streamUrl = `${API_BASE}/uploads/${encodeURIComponent(data.id)}/download`;
        const cat = CATEGORIES[data.category] || { label: data.category, color: 'text-slate-400 border-white/10 bg-white/5', icon: '' };

        container.innerHTML = `
            <div class="space-y-8" style="animation: fadeSlideUp 0.4s ease-out both;">
                <!-- Header -->
                <div class="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
                    <div class="min-w-0">
                        <h1 class="text-2xl md:text-3xl font-black text-white tracking-tight">${escapeHtml(data.title || data.filename)}</h1>
                        <div class="text-xs text-slate-500 mt-1.5 font-mono flex items-center gap-2">
                            ${cat.icon.replace('w-5 h-5', 'w-3.5 h-3.5')}
                            ${escapeHtml(data.filename)}
                        </div>
                    </div>
                    <div class="shrink-0 flex items-center gap-2">
                        <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold uppercase border ${cat.color}">
                            <span class="w-1.5 h-1.5 rounded-full bg-current"></span>
                            ${escapeHtml(cat.label)}
                        </span>
                        <span id="upload-detail-owner-actions"></span>
                    </div>
                </div>

                ${data.description ? `
                <div class="text-sm text-slate-300 leading-relaxed glass-panel rounded-lg p-4">${escapeHtml(data.description)}</div>
                ` : ''}

                <!-- Video Player -->
                ${canPlay ? `
                <div class="rounded-xl overflow-hidden shadow-[0_20px_50px_-12px_rgba(0,0,0,0.7)] ring-1 ring-white/10">
                    <video controls playsinline class="w-full bg-black" style="max-height: 70vh;">
                        <source src="${streamUrl}" type="video/mp4">
                        Your browser does not support video playback.
                    </video>
                </div>
                ` : isVideoNotPlayable ? `
                <div class="glass-panel rounded-xl p-12 text-center">
                    <div class="w-20 h-20 mx-auto mb-4 rounded-2xl flex items-center justify-center border border-amber-500/30 bg-amber-500/10 text-amber-300">
                        <svg class="w-10 h-10" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 10.5l4.72-4.72a.75.75 0 011.28.53v11.38a.75.75 0 01-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 002.25-2.25v-9a2.25 2.25 0 00-2.25-2.25h-9A2.25 2.25 0 002.25 7.5v9a2.25 2.25 0 002.25 2.25z"/></svg>
                    </div>
                    <div class="text-sm text-slate-200 font-semibold">${escapeHtml(data.extension)} isn't playable in the browser</div>
                    <div class="text-xs text-slate-400 mt-1">Download it to watch (${sizeStr}). In-browser playback for .avi/.mkv is coming with a future .mp4 transcode.</div>
                </div>
                ` : `
                <div class="glass-panel rounded-xl p-12 text-center">
                    <div class="w-20 h-20 mx-auto mb-4 rounded-2xl flex items-center justify-center border ${cat.color}">
                        ${cat.icon.replace('w-5 h-5', 'w-10 h-10')}
                    </div>
                    <div class="text-sm text-slate-400">${escapeHtml(data.filename)}</div>
                    <div class="text-xs text-slate-400 mt-1">${sizeStr}</div>
                </div>
                `}

                <!-- Metadata Grid -->
                <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div class="glass-panel rounded-xl p-4 text-center group hover:border-brand-cyan/30 transition-colors">
                        <div class="text-[10px] uppercase tracking-widest text-slate-400 mb-1.5 font-bold">Uploaded by</div>
                        <div class="text-sm font-bold text-white">${escapeHtml(data.uploader_name || 'Anonymous')}</div>
                    </div>
                    <div class="glass-panel rounded-xl p-4 text-center group hover:border-brand-purple/30 transition-colors">
                        <div class="text-[10px] uppercase tracking-widest text-slate-400 mb-1.5 font-bold">Size</div>
                        <div class="text-sm font-bold text-white">${sizeStr}</div>
                    </div>
                    <div class="glass-panel rounded-xl p-4 text-center group hover:border-brand-blue/30 transition-colors">
                        <div class="text-[10px] uppercase tracking-widest text-slate-400 mb-1.5 font-bold">Downloads</div>
                        <div class="text-sm font-bold text-white">${data.download_count || 0}</div>
                    </div>
                    <div class="glass-panel rounded-xl p-4 text-center group hover:border-brand-amber/30 transition-colors">
                        <div class="text-[10px] uppercase tracking-widest text-slate-400 mb-1.5 font-bold">Uploaded</div>
                        <div class="text-sm font-bold text-white">${data.created_at ? new Date(data.created_at).toLocaleDateString() : 'Unknown'}</div>
                    </div>
                </div>

                <!-- Tags -->
                ${data.tags && data.tags.length > 0 ? `
                <div class="flex flex-wrap gap-2">
                    ${data.tags.map(t => `<span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-bold text-slate-400 border border-white/10"><span class="opacity-50">#</span>${escapeHtml(t)}</span>`).join('')}
                </div>
                ` : ''}

                <!-- Action Buttons -->
                <div class="flex flex-wrap gap-3">
                    <a href="${downloadUrl}" download
                        class="inline-flex items-center gap-2 bg-brand-blue hover:bg-blue-600 text-white text-sm font-bold px-6 py-2.5 rounded-xl transition-all shadow-[0_0_20px_rgba(59,130,246,0.3)] hover:shadow-[0_0_30px_rgba(59,130,246,0.5)]">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3"/></svg>
                        Download
                    </a>
                    <button id="copy-share-btn" onclick="window.copyShareLink()"
                        class="inline-flex items-center gap-2 bg-brand-purple/20 hover:bg-brand-purple/30 text-brand-purple text-sm font-bold px-6 py-2.5 rounded-xl border border-brand-purple/30 transition-all hover:shadow-[0_0_20px_rgba(139,92,246,0.2)]">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m9.86-2.54a4.5 4.5 0 00-6.364-6.364L4.5 8.25"/></svg>
                        Copy Link
                    </button>
                </div>

                <!-- Share URL -->
                <div class="glass-panel rounded-xl p-4">
                    <div class="text-[10px] uppercase tracking-widest text-slate-400 font-bold mb-2">Shareable Link</div>
                    <div class="flex items-center gap-2">
                        <input type="text" id="share-url-input" readonly value="${escapeHtml(shareUrl)}"
                            class="flex-1 bg-slate-900/50 border border-white/5 rounded-lg px-3 py-2 text-xs text-slate-300 font-mono outline-none focus:border-brand-purple/30 transition"
                            onclick="this.select()">
                        <button onclick="window.copyShareLink()"
                            class="shrink-0 px-3 py-2 rounded-lg text-xs font-bold text-brand-purple hover:bg-brand-purple/10 border border-brand-purple/20 transition">
                            Copy
                        </button>
                    </div>
                </div>
            </div>
        `;
        _maybeShowDeleteButton(data);
    } catch (err) {
        container.innerHTML = `
            <div class="glass-card rounded-xl p-12 text-center" style="animation: fadeSlideUp 0.4s ease-out both;">
                <svg class="w-12 h-12 mx-auto mb-4 text-brand-rose/60" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"/></svg>
                <div class="text-base font-bold text-brand-rose mb-1">Upload not found</div>
                <div class="text-xs text-slate-500">This upload may have been deleted or the link is invalid.</div>
                <a href="#/uploads" class="inline-block mt-4 text-xs text-brand-cyan hover:text-white transition">Browse all uploads</a>
            </div>`;
    }
}

// Delete: shown to the uploader AND to admins — hence the name change from
// _maybeShowOwnerDelete, which stopped being true when admins gained the
// ability (Copilot on #615). The decision is the server's —
// the detail payload carries can_delete for this session, computed by the same
// rule the DELETE endpoint enforces, so the button and the answer cannot drift
// apart and the admin list never reaches the browser.
//
// Falls back to the uploader check for a payload from an older backend, so a
// stale cached response degrades to the previous behaviour rather than hiding
// the button from someone who owns the file.
async function _maybeShowDeleteButton(data) {
    try {
        if (data.can_delete === false) return;
        if (data.can_delete !== true) {
            const user = await ensureCurrentUser();
            if (!user || String(user.id) !== String(data.uploader_discord_id)) return;
        }
        const host = document.getElementById('upload-detail-owner-actions');
        if (!host) return;
        host.innerHTML = `
            <button class="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold uppercase border text-brand-rose border-brand-rose/30 bg-brand-rose/10 hover:bg-brand-rose/20 transition">
                Delete
            </button>`;
        host.querySelector('button').addEventListener('click', async () => {
            const label = data.title || data.filename || 'this upload';
            if (!window.confirm(`Delete "${label}" permanently?\n\nThis cannot be undone.`)) return;
            try {
                const resp = await fetch(`${API_BASE}/uploads/${encodeURIComponent(data.id)}`, {
                    method: 'DELETE', credentials: 'same-origin',
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },  // CSRF
                });
                if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
                showToast('Upload deleted', 'success');
                window.location.hash = '#/uploads';
            } catch (e) {
                showToast(`Delete failed: ${e.message}`, 'error');
            }
        });
    } catch { /* not logged in — no owner actions */ }
}

function copyShareLink() {
    const input = document.getElementById('share-url-input');
    const btn = document.getElementById('copy-share-btn');

    const url = input ? input.value : window.location.href;

    navigator.clipboard.writeText(url).then(() => {
        showToast('Link copied to clipboard', 'success');
        if (btn) {
            const svg = btn.querySelector('svg');
            const originalSvg = svg ? svg.outerHTML : '';
            btn.innerHTML = `<svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg> Copied!`;
            btn.classList.add('text-brand-emerald', 'border-brand-emerald/30');
            btn.classList.remove('text-brand-purple', 'border-brand-purple/30');
            setTimeout(() => {
                btn.innerHTML = `${originalSvg} Copy Link`;
                btn.classList.remove('text-brand-emerald', 'border-brand-emerald/30');
                btn.classList.add('text-brand-purple', 'border-brand-purple/30');
            }, 2000);
        }
    }).catch(() => {
        if (input) {
            input.select();
            document.execCommand('copy');
            showToast('Link copied', 'info');
        }
    });
}

// ============================================================================
// SEARCH DEBOUNCE
// ============================================================================

let searchTimeout = null;
document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('upload-search-input');
    if (searchInput) {
        searchInput.addEventListener('input', () => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                currentOffset = 0;
                loadUploadsList();
            }, 400);
        });
    }
});

// ============================================================================
// EXPOSE TO WINDOW
// ============================================================================

window.filterUploads = filterUploads;
window.setUploadSort = setUploadSort;
window.filterUploadsByTag = filterUploadsByTag;
window.uploadPage = uploadPage;
window.openVideoPlayer = openVideoPlayer;
window.closeVideoPlayer = closeVideoPlayer;
window.copyShareLink = copyShareLink;
