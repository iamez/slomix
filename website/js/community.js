/**
 * Community module - clips, configs, uploads
 * @module community
 */

import { API_BASE } from './utils.js';

// Community state
let currentCommunityTab = 'clips';

/**
 * Initialize community view
 */
export function loadCommunityView() {
    switchCommunityTab(currentCommunityTab);
}

/**
 * Switch between clips and configs tabs
 */
export function switchCommunityTab(tab) {
    currentCommunityTab = tab;

    const btnClips = document.getElementById('btn-tab-clips');
    const btnConfigs = document.getElementById('btn-tab-configs');

    if (tab === 'clips') {
        if (btnClips) btnClips.className = 'px-6 py-2 rounded-lg font-bold bg-brand-rose text-white shadow-lg transition';
        if (btnConfigs) btnConfigs.className = 'px-6 py-2 rounded-lg font-bold text-slate-400 hover:text-white transition';
        document.getElementById('community-clips')?.classList.remove('hidden');
        document.getElementById('community-configs')?.classList.add('hidden');
        loadClips();
    } else {
        if (btnClips) btnClips.className = 'px-6 py-2 rounded-lg font-bold text-slate-400 hover:text-white transition';
        if (btnConfigs) btnConfigs.className = 'px-6 py-2 rounded-lg font-bold bg-brand-rose text-white shadow-lg transition';
        document.getElementById('community-clips')?.classList.add('hidden');
        document.getElementById('community-configs')?.classList.remove('hidden');
        loadConfigs();
    }
}

/**
 * Load clips grid
 */
export async function loadClips() {
    const grid = document.getElementById('clips-grid');
    if (!grid) return;

    // Coming Soon placeholder
    grid.innerHTML = `
        <div class="col-span-full text-center py-16">
            <div class="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-brand-rose/10 border border-brand-rose/20 mb-6">
                <i data-lucide="rocket" class="w-4 h-4 text-brand-rose"></i>
                <span class="text-brand-rose font-bold text-sm uppercase">Coming Soon</span>
            </div>
            <h3 class="text-2xl font-black text-white mb-3">Community Clips</h3>
            <p class="text-slate-400 max-w-md mx-auto">Share your best ET:Legacy moments! Clip submission and viewing will be available in a future update.</p>
            <div class="mt-8 flex justify-center gap-4">
                <div class="glass-card p-4 rounded-xl text-center">
                    <i data-lucide="video" class="w-8 h-8 text-slate-600 mx-auto mb-2"></i>
                    <span class="text-xs text-slate-500">Submit Clips</span>
                </div>
                <div class="glass-card p-4 rounded-xl text-center">
                    <i data-lucide="heart" class="w-8 h-8 text-slate-600 mx-auto mb-2"></i>
                    <span class="text-xs text-slate-500">Like & Vote</span>
                </div>
                <div class="glass-card p-4 rounded-xl text-center">
                    <i data-lucide="trophy" class="w-8 h-8 text-slate-600 mx-auto mb-2"></i>
                    <span class="text-xs text-slate-500">Weekly Top 10</span>
                </div>
            </div>
        </div>
    `;
    if (typeof lucide !== 'undefined') lucide.createIcons();
}

/**
 * Load configs list
 */
export async function loadConfigs() {
    const list = document.getElementById('configs-list');
    if (!list) return;

    // Coming Soon placeholder
    list.innerHTML = `
        <div class="text-center py-16">
            <div class="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-brand-purple/10 border border-brand-purple/20 mb-6">
                <i data-lucide="wrench" class="w-4 h-4 text-brand-purple"></i>
                <span class="text-brand-purple font-bold text-sm uppercase">Coming Soon</span>
            </div>
            <h3 class="text-2xl font-black text-white mb-3">Config Sharing</h3>
            <p class="text-slate-400 max-w-md mx-auto">Share your ET:Legacy configurations! Config upload and download will be available in a future update.</p>
            <div class="mt-8 space-y-3 max-w-sm mx-auto">
                <div class="glass-panel p-4 rounded-xl flex items-center gap-4">
                    <i data-lucide="file-code" class="w-6 h-6 text-slate-600"></i>
                    <div class="text-left">
                        <div class="text-sm font-bold text-slate-400">etconfig.cfg</div>
                        <div class="text-xs text-slate-500">Game settings, binds, scripts</div>
                    </div>
                </div>
                <div class="glass-panel p-4 rounded-xl flex items-center gap-4">
                    <i data-lucide="palette" class="w-6 h-6 text-slate-600"></i>
                    <div class="text-left">
                        <div class="text-sm font-bold text-slate-400">HUD Configurations</div>
                        <div class="text-xs text-slate-500">Custom HUD layouts</div>
                    </div>
                </div>
                <div class="glass-panel p-4 rounded-xl flex items-center gap-4">
                    <i data-lucide="crosshair" class="w-6 h-6 text-slate-600"></i>
                    <div class="text-left">
                        <div class="text-sm font-bold text-slate-400">Crosshair Packs</div>
                        <div class="text-xs text-slate-500">Custom crosshair settings</div>
                    </div>
                </div>
            </div>
        </div>
    `;
    if (typeof lucide !== 'undefined') lucide.createIcons();
}

/**
 * Open upload modal
 */
export function openUploadModal(type = 'clip') {
    const modal = document.getElementById('upload-modal');
    const title = document.getElementById('modal-title');
    const typeInput = document.getElementById('upload-type');
    const fieldUrl = document.getElementById('field-url');
    const fieldContent = document.getElementById('field-content');

    if (type === 'clip') {
        if (title) title.textContent = 'Submit Clip';
        if (typeInput) typeInput.value = 'clip';
        fieldUrl?.classList.remove('hidden');
        fieldContent?.classList.add('hidden');
        const urlInput = document.getElementById('upload-url');
        const contentInput = document.getElementById('upload-content');
        if (urlInput) urlInput.required = true;
        if (contentInput) contentInput.required = false;
    } else {
        if (title) title.textContent = 'Submit Config';
        if (typeInput) typeInput.value = 'config';
        fieldUrl?.classList.add('hidden');
        fieldContent?.classList.remove('hidden');
        const urlInput = document.getElementById('upload-url');
        const contentInput = document.getElementById('upload-content');
        if (urlInput) urlInput.required = false;
        if (contentInput) contentInput.required = true;
    }

    modal?.classList.remove('hidden');
}

/**
 * Close upload modal
 */
export function closeUploadModal() {
    document.getElementById('upload-modal')?.classList.add('hidden');
    document.getElementById('upload-form')?.reset();
}

/**
 * Handle upload form submission
 */
export async function handleUpload(e) {
    e.preventDefault();

    const type = document.getElementById('upload-type')?.value;
    const title = document.getElementById('upload-title')?.value;
    const desc = document.getElementById('upload-desc')?.value;

    const payload = {
        title: title,
        description: desc
    };

    if (type === 'clip') {
        payload.url = document.getElementById('upload-url')?.value;
    } else {
        payload.content = document.getElementById('upload-content')?.value;
    }

    try {
        const endpoint = type === 'clip' ? 'clips' : 'configs';
        const res = await fetch(`${API_BASE}/community/${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            if (res.status === 401) {
                alert('You must be logged in to submit content.');
                return;
            }
            throw new Error('Upload failed');
        }

        alert('Submission successful!');
        closeUploadModal();

        if (type === 'clip') loadClips();
        else loadConfigs();

    } catch (err) {
        console.error(err);
        alert('Failed to submit content. Please try again.');
    }
}

// Expose to window for onclick handlers in HTML
window.switchCommunityTab = switchCommunityTab;
window.openUploadModal = openUploadModal;
window.closeUploadModal = closeUploadModal;
window.handleUpload = handleUpload;
