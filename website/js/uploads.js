/**
 * Uploads Library Module
 * Browse, upload, and download community files (configs, HUDs, archives, clips).
 */

import { API_BASE, fetchJSON, escapeHtml, escapeJsString } from './utils.js';

let currentCategory = '';
let currentOffset = 0;
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

function setupDragDrop() {
    const zone = document.getElementById('upload-drop-zone');
    if (!zone) return;

    const fileInput = document.getElementById('upload-file-input');

    zone.addEventListener('click', () => {
        if (fileInput) fileInput.click();
    });

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
            // Show selected file name
            const nameEl = document.getElementById('upload-drop-filename');
            if (nameEl) {
                nameEl.textContent = e.dataTransfer.files[0].name;
                nameEl.classList.remove('hidden');
            }
        }
    });

    // Show filename on normal file select too
    if (fileInput) {
        fileInput.addEventListener('change', () => {
            const nameEl = document.getElementById('upload-drop-filename');
            if (nameEl && fileInput.files.length) {
                nameEl.textContent = fileInput.files[0].name;
                nameEl.classList.remove('hidden');
            }
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

    // Check if user is logged in (session cookie)
    fetch('/auth/me', { credentials: 'same-origin' })
        .then(r => r.ok ? r.json() : null)
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
    form.addEventListener('submit', handleUpload);
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
            xhr.send(formData);
        });

        showToast(`Uploaded: ${data.filename}`, 'success');

        // Reset form
        fileInput.value = '';
        titleInput.value = '';
        descInput.value = '';
        tagsInput.value = '';
        const nameEl = document.getElementById('upload-drop-filename');
        if (nameEl) { nameEl.textContent = ''; nameEl.classList.add('hidden'); }

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
    const params = new URLSearchParams({ limit: PAGE_SIZE, offset: currentOffset });
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
                    <svg class="w-8 h-8 text-slate-600" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/></svg>
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
    const delay = Math.min(index * 0.05, 0.3);

    return `
        <div class="group relative" style="animation: fadeSlideUp 0.4s ease-out both; animation-delay: ${delay}s;">
            <!-- Glow effect on hover -->
            <div class="absolute -inset-[1px] rounded-xl opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none"
                 style="background: linear-gradient(135deg, ${cat.glow}, transparent 60%);"></div>

            <div class="glass-card relative rounded-xl p-5 flex flex-col gap-3 h-full">
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
                        <svg class="w-3 h-3 text-slate-600" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0"/></svg>
                        ${escapeHtml(item.uploader_name || 'Anonymous')}
                    </span>
                    <span>${sizeStr}</span>
                </div>
                <div class="flex items-center justify-between text-[11px] text-slate-600">
                    <span>${item.created_at ? new Date(item.created_at).toLocaleDateString() : ''}</span>
                    <span class="flex items-center gap-1">
                        <svg class="w-3 h-3" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3"/></svg>
                        ${item.download_count || 0}
                    </span>
                </div>

                <!-- Actions -->
                <div class="mt-auto flex gap-2 pt-1">
                    ${isVideo ? `
                    <button onclick="window.openVideoPlayer('${escapeJsString(item.id)}', '${escapeJsString(item.title || item.filename)}')"
                        class="flex-1 inline-flex items-center justify-center gap-1.5 bg-brand-emerald/15 hover:bg-brand-emerald/25 text-brand-emerald text-xs font-bold px-3 py-2 rounded-lg transition-all duration-200 hover:shadow-[0_0_12px_rgba(16,185,129,0.2)]">
                        <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                        Watch
                    </button>` : ''}
                    <a href="#/uploads/${encodeURIComponent(item.id)}"
                        class="flex-1 inline-flex items-center justify-center gap-1.5 bg-brand-purple/15 hover:bg-brand-purple/25 text-brand-purple text-xs font-bold px-3 py-2 rounded-lg transition-all duration-200 hover:shadow-[0_0_12px_rgba(139,92,246,0.2)]">
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m9.86-2.54a4.5 4.5 0 00-6.364-6.364L4.5 8.25"/></svg>
                        Share
                    </a>
                    <a href="${API_BASE}/uploads/${encodeURIComponent(item.id)}/download"
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

    if (pages <= 1) {
        container.innerHTML = '';
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
    html += `<div class="text-[11px] text-slate-600">${total} upload${total !== 1 ? 's' : ''}</div>`;

    container.innerHTML = html;
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
                <span class="text-slate-600 ml-0.5">${t.count}</span>
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
                            <div class="text-xs text-slate-600">Try a different tag or browse all uploads</div>
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

function openVideoPlayer(uploadId, title) {
    const existing = document.getElementById('video-player-modal');
    if (existing) existing.remove();

    const videoUrl = `${API_BASE}/uploads/${encodeURIComponent(uploadId)}/download`;

    const modal = document.createElement('div');
    modal.id = 'video-player-modal';
    modal.className = 'fixed inset-0 z-50 flex items-center justify-center';
    modal.style.cssText = 'background: rgba(0,0,0,0); transition: background 0.3s ease;';
    modal.innerHTML = `
        <div class="absolute inset-0 backdrop-blur-md"></div>
        <div class="relative w-full max-w-5xl mx-4" style="transform: scale(0.95); opacity: 0; transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);">
            <div class="flex items-center justify-between mb-3 px-1">
                <h3 class="text-sm font-bold text-white truncate pr-4 flex items-center gap-2">
                    <svg class="w-4 h-4 text-brand-emerald shrink-0" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                    ${escapeHtml(title)}
                </h3>
                <button onclick="window.closeVideoPlayer()" class="w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:text-white hover:bg-white/10 transition">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
                </button>
            </div>
            <div class="rounded-xl overflow-hidden shadow-[0_25px_60px_-12px_rgba(0,0,0,0.8)] ring-1 ring-white/10">
                <video id="video-player-element" controls autoplay
                    class="w-full bg-black" style="max-height: 80vh;">
                    <source src="${videoUrl}" type="video/mp4">
                    Your browser does not support video playback.
                </video>
            </div>
        </div>
    `;

    modal.addEventListener('click', (e) => {
        if (e.target === modal || e.target.classList.contains('backdrop-blur-md')) closeVideoPlayer();
    });

    document.body.appendChild(modal);

    // Animate in
    requestAnimationFrame(() => {
        modal.style.background = 'rgba(0,0,0,0.85)';
        const inner = modal.querySelector('.relative');
        if (inner) {
            inner.style.transform = 'scale(1)';
            inner.style.opacity = '1';
        }
    });

    document.addEventListener('keydown', handleVideoEscape);
}

function handleVideoEscape(e) {
    if (e.key === 'Escape') closeVideoPlayer();
}

function closeVideoPlayer() {
    const modal = document.getElementById('video-player-modal');
    if (modal) {
        const video = modal.querySelector('video');
        if (video) video.pause();
        const inner = modal.querySelector('.relative');
        if (inner) {
            inner.style.transform = 'scale(0.95)';
            inner.style.opacity = '0';
        }
        modal.style.background = 'rgba(0,0,0,0)';
        setTimeout(() => modal.remove(), 300);
    }
    document.removeEventListener('keydown', handleVideoEscape);
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
        const isVideo = data.is_playable || isVideoFile(data.extension);
        const shareUrl = `${window.location.origin}${window.location.pathname}#/uploads/${encodeURIComponent(data.id)}`;
        const downloadUrl = `${API_BASE}/uploads/${encodeURIComponent(data.id)}/download`;
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
                    <span class="shrink-0 inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold uppercase border ${cat.color}">
                        <span class="w-1.5 h-1.5 rounded-full bg-current"></span>
                        ${escapeHtml(cat.label)}
                    </span>
                </div>

                ${data.description ? `
                <div class="text-sm text-slate-300 leading-relaxed glass-panel rounded-lg p-4">${escapeHtml(data.description)}</div>
                ` : ''}

                <!-- Video Player -->
                ${isVideo ? `
                <div class="rounded-xl overflow-hidden shadow-[0_20px_50px_-12px_rgba(0,0,0,0.7)] ring-1 ring-white/10">
                    <video controls class="w-full bg-black" style="max-height: 70vh;">
                        <source src="${downloadUrl}" type="video/mp4">
                        Your browser does not support video playback.
                    </video>
                </div>
                ` : `
                <div class="glass-panel rounded-xl p-12 text-center">
                    <div class="w-20 h-20 mx-auto mb-4 rounded-2xl flex items-center justify-center border ${cat.color}">
                        ${cat.icon.replace('w-5 h-5', 'w-10 h-10')}
                    </div>
                    <div class="text-sm text-slate-400">${escapeHtml(data.filename)}</div>
                    <div class="text-xs text-slate-600 mt-1">${sizeStr}</div>
                </div>
                `}

                <!-- Metadata Grid -->
                <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div class="glass-panel rounded-xl p-4 text-center group hover:border-brand-cyan/30 transition-colors">
                        <div class="text-[10px] uppercase tracking-widest text-slate-600 mb-1.5 font-bold">Uploaded by</div>
                        <div class="text-sm font-bold text-white">${escapeHtml(data.uploader_name || 'Anonymous')}</div>
                    </div>
                    <div class="glass-panel rounded-xl p-4 text-center group hover:border-brand-purple/30 transition-colors">
                        <div class="text-[10px] uppercase tracking-widest text-slate-600 mb-1.5 font-bold">Size</div>
                        <div class="text-sm font-bold text-white">${sizeStr}</div>
                    </div>
                    <div class="glass-panel rounded-xl p-4 text-center group hover:border-brand-blue/30 transition-colors">
                        <div class="text-[10px] uppercase tracking-widest text-slate-600 mb-1.5 font-bold">Downloads</div>
                        <div class="text-sm font-bold text-white">${data.download_count || 0}</div>
                    </div>
                    <div class="glass-panel rounded-xl p-4 text-center group hover:border-brand-amber/30 transition-colors">
                        <div class="text-[10px] uppercase tracking-widest text-slate-600 mb-1.5 font-bold">Uploaded</div>
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
                    <a href="${downloadUrl}"
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
                    <div class="text-[10px] uppercase tracking-widest text-slate-600 font-bold mb-2">Shareable Link</div>
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
window.filterUploadsByTag = filterUploadsByTag;
window.uploadPage = uploadPage;
window.openVideoPlayer = openVideoPlayer;
window.closeVideoPlayer = closeVideoPlayer;
window.copyShareLink = copyShareLink;
