/**
 * Availability Module
 * Today-first availability UI backed by /api/availability.
 */

import { API_BASE, AUTH_BASE, fetchJSON, escapeHtml } from './utils.js';

const NO_STORE_FETCH = { cachePolicy: 'no-store', credentials: 'same-origin' };

const LOOKBACK_DAYS = 31;
const LOOKAHEAD_DAYS = 90;
const UPCOMING_DAYS = 3;
const UPCOMING_START_OFFSET = 2;

const POLL_INTERVAL_MS = 45_000;
const LOCAL_PREFS_KEY = 'availability_local_prefs_v3';
const READY_SOUND_STATE_KEY = 'availability_ready_sound_state_v1';

const STATUS_ORDER = ['looking', 'available', 'maybe', 'not_playing'];

const STATUS_META = {
    looking: {
        label: 'Looking to play',
        shortLabel: 'Looking',
        emoji: '🎯',
        barClass: 'bg-brand-cyan',
        valueClass: 'text-brand-cyan',
        selectedClass: 'bg-brand-cyan/20 border-brand-cyan/50 text-brand-cyan',
        idleClass: 'bg-slate-900/60 border-white/10 text-slate-300 hover:border-brand-cyan/40'
    },
    available: {
        label: 'Available',
        shortLabel: 'Available',
        emoji: '✅',
        barClass: 'bg-brand-emerald',
        valueClass: 'text-brand-emerald',
        selectedClass: 'bg-brand-emerald/20 border-brand-emerald/50 text-brand-emerald',
        idleClass: 'bg-slate-900/60 border-white/10 text-slate-300 hover:border-brand-emerald/40'
    },
    maybe: {
        label: 'Maybe',
        shortLabel: 'Maybe',
        emoji: '❔',
        barClass: 'bg-brand-amber',
        valueClass: 'text-brand-amber',
        selectedClass: 'bg-brand-amber/20 border-brand-amber/50 text-brand-amber',
        idleClass: 'bg-slate-900/60 border-white/10 text-slate-300 hover:border-brand-amber/40'
    },
    not_playing: {
        label: 'Not playing',
        shortLabel: 'Not playing',
        emoji: '⛔',
        barClass: 'bg-brand-rose',
        valueClass: 'text-brand-rose',
        selectedClass: 'bg-brand-rose/20 border-brand-rose/50 text-brand-rose',
        idleClass: 'bg-slate-900/60 border-white/10 text-slate-300 hover:border-brand-rose/40'
    }
};

const STATUS_TO_API = {
    looking: 'LOOKING',
    available: 'AVAILABLE',
    maybe: 'MAYBE',
    not_playing: 'NOT_PLAYING'
};

let currentUser = null;
let accessState = {
    authenticated: false,
    linkedDiscord: false,
    canSubmit: false,
    isAdmin: false,
    canPromote: false
};

let availabilityByDate = new Map();
let selectedDateIso = toISODate(new Date());
let visibleMonth = startOfMonth(new Date());
let calendarExpanded = false;
let sessionReadyState = {
    ready: false,
    eventKey: null,
    date: null,
    threshold: 0,
    lookingCount: 0
};

let responseInFlight = false;
let prefsInFlight = false;
let createTodayInFlight = false;
let refreshInFlight = false;
let promoteInFlight = false;
let promotePreviewInFlight = false;
let planningActionInFlight = false;

let promoteState = {
    campaign: null,
    preview: null
};
let planningState = {
    data: null,
    panelOpen: false,
    assignments: new Map(),
    actionStatus: { message: '', error: false },
    error: ''
};

let responseStatus = { message: '', error: false };
let prefsStatus = { message: '', error: false };
let adminStatus = { message: '', error: false };
let aggregateError = '';

let refreshTimer = null;
let runtimeListenersBound = false;
let audioCtx = null;

const localPrefs = loadLocalPrefs();
let prefsState = {
    discordNotify: true,
    telegramNotify: Boolean(localPrefs.telegramNotify),
    signalNotify: Boolean(localPrefs.signalNotify),
    getReadySound: localPrefs.getReadySound !== false,
    soundCooldownSeconds: Number.isFinite(Number(localPrefs.soundCooldownSeconds))
        ? Math.max(30, Number(localPrefs.soundCooldownSeconds))
        : 480,
    remindersEnabled: true,
    timezone: 'UTC'
};

// ============================================================================
// PUBLIC ENTRYPOINTS
// ============================================================================

export async function loadAvailabilityView() {
    ensureRuntimeListeners();
    ensureRefreshTimer();
    renderLoadingState();
    await refreshAvailabilityView();
}

async function refreshAvailabilityView() {
    if (refreshInFlight) return;
    refreshInFlight = true;

    try {
        responseStatus = { message: '', error: false };
        aggregateError = '';

        await loadCurrentUser();
        await loadAccessState();
        await loadAvailabilityRange();
        await loadPromotionCampaignState();
        await loadPlanningState();

        if (accessState.authenticated && accessState.linkedDiscord) {
            await loadSettings();
        }

        ensureSelectedDate();
        renderAll();
        maybePlayGetReadySound();
    } finally {
        refreshInFlight = false;
    }
}

// ============================================================================
// DATA LOAD
// ============================================================================

async function loadCurrentUser() {
    currentUser = null;
    try {
        const resp = await fetch('/auth/me', { credentials: 'same-origin', cache: 'no-store' });
        if (!resp.ok) return;
        const payload = await resp.json();
        currentUser = payload && payload.id ? payload : null;
    } catch (_err) {
        currentUser = null;
    }
}

async function loadAccessState() {
    accessState = {
        authenticated: false,
        linkedDiscord: false,
        canSubmit: false,
        isAdmin: false,
        canPromote: false
    };

    try {
        const payload = await fetchJSON(`${API_BASE}/availability/access`, NO_STORE_FETCH);
        accessState.authenticated = Boolean(payload?.authenticated);
        accessState.linkedDiscord = Boolean(payload?.linked_discord);
        accessState.canSubmit = Boolean(payload?.can_submit);
        accessState.isAdmin = Boolean(payload?.is_admin);
        accessState.canPromote = Boolean(payload?.can_promote);
    } catch (_err) {
        // Keep defaults.
    }
}

async function loadAvailabilityRange() {
    availabilityByDate = new Map();

    const fromIso = toISODate(addDays(new Date(), -LOOKBACK_DAYS));
    const toIso = toISODate(addDays(new Date(), LOOKAHEAD_DAYS));

    try {
        const payload = await fetchJSON(
            `${API_BASE}/availability?from=${fromIso}&to=${toIso}&include_users=${accessState.authenticated ? 'true' : 'false'}`,
            NO_STORE_FETCH
        );

        const days = Array.isArray(payload?.days) ? payload.days : [];
        for (const day of days) {
            const dateIso = String(day?.date || '').trim();
            if (!dateIso) continue;

            const counts = normalizeCounts(day?.counts);
            availabilityByDate.set(dateIso, {
                dateIso,
                counts,
                total: countValue(day?.total),
                myStatus: normalizeStatus(day?.my_status),
                usersByStatus: normalizeUsersByStatus(day?.users_by_status)
            });
        }

        const session = payload?.session_ready || {};
        sessionReadyState = {
            ready: Boolean(session.ready),
            eventKey: typeof session.event_key === 'string' ? session.event_key : null,
            date: typeof session.date === 'string' ? session.date : null,
            threshold: countValue(session.threshold),
            lookingCount: countValue(session.looking_count)
        };
    } catch (err) {
        aggregateError = formatErrorMessage(err, 'Failed to load availability data');
    }
}

async function loadPromotionCampaignState() {
    promoteState.campaign = null;
    if (!accessState.authenticated) return;
    try {
        const payload = await fetchJSON(`${API_BASE}/availability/promotions/campaign`, NO_STORE_FETCH);
        promoteState.campaign = payload?.campaign || null;
    } catch (_err) {
        promoteState.campaign = null;
    }
}

async function loadPlanningState() {
    planningState.error = '';
    planningState.actionStatus = { message: '', error: false };

    try {
        const payload = await fetchJSON(`${API_BASE}/planning/today`, NO_STORE_FETCH);
        planningState.data = payload || null;
        reconcilePlanningAssignments();
    } catch (err) {
        planningState.data = null;
        planningState.assignments = new Map();
        planningState.error = formatErrorMessage(err, 'Failed to load planning room');
    }
}

async function loadSettings() {
    try {
        const payload = await fetchJSON(`${API_BASE}/availability/settings`, NO_STORE_FETCH);
        prefsState.discordNotify = Boolean(payload?.discord_notify ?? true);
        prefsState.telegramNotify = Boolean(payload?.telegram_notify ?? false);
        prefsState.signalNotify = Boolean(payload?.signal_notify ?? false);
        prefsState.getReadySound = Boolean(payload?.get_ready_sound ?? true);
        prefsState.soundCooldownSeconds = Math.max(30, countValue(payload?.sound_cooldown_seconds) || 480);
        prefsState.remindersEnabled = payload?.availability_reminders_enabled !== false;
        prefsState.timezone = typeof payload?.timezone === 'string' ? payload.timezone : 'UTC';

        persistLocalPrefs();
    } catch (err) {
        prefsStatus = {
            message: `Settings unavailable: ${formatErrorMessage(err, 'Unknown error')}`,
            error: true
        };
    }
}

// ============================================================================
// RENDER
// ============================================================================

function renderAll() {
    updateAdminControls();
    renderAnonMessage();
    renderStatusMessages();
    renderTodayTomorrowActions();
    renderCurrentQueue();
    renderPromoteControls();
    renderCampaignStatus();
    renderPlanningRoom();
    renderCalendarVisibility();
    renderCalendar();
    renderQuickView();
    renderSelectedDayPanel();
    renderPreferencesSection();
}

function renderLoadingState() {
    const actions = document.getElementById('availability-actions');
    if (actions) {
        actions.innerHTML = '<div class="text-center py-6 text-slate-500 text-sm">Loading your availability controls...</div>';
    }

    const grid = document.getElementById('availability-calendar-grid');
    if (grid) {
        grid.innerHTML = '<div class="col-span-7 text-center py-8 text-slate-500 text-sm">Loading calendar...</div>';
    }

    const quick = document.getElementById('availability-quick-view');
    if (quick) {
        quick.innerHTML = '<div class="text-center py-8 text-slate-500 text-sm">Loading upcoming days...</div>';
    }

    const queue = document.getElementById('availability-current-queue');
    if (queue) {
        queue.innerHTML = '<div class="text-xs text-slate-500">Loading current queue...</div>';
    }

    renderCalendarVisibility();
}

function updateAdminControls() {
    const createBtn = document.getElementById('availability-create-today-btn');
    if (!createBtn) return;

    // Legacy poll fallback is not used in date-based mode.
    createBtn.classList.add('hidden');
    createBtn.disabled = createTodayInFlight;

    const msg = document.getElementById('availability-admin-msg');
    if (!msg) return;
    msg.textContent = adminStatus.message || '';
    msg.classList.remove('text-brand-rose', 'text-brand-emerald', 'text-slate-500');
    if (!adminStatus.message) {
        msg.classList.add('text-slate-500');
    } else {
        msg.classList.add(adminStatus.error ? 'text-brand-rose' : 'text-brand-emerald');
    }
}

function renderAnonMessage() {
    const msg = document.getElementById('availability-anon-message');
    if (!msg) return;

    if (accessState.canSubmit) {
        msg.classList.add('hidden');
        msg.innerHTML = '';
        return;
    }

    const copy = 'Aggregate view only. Link your Discord account to a player profile to submit or subscribe.';

    msg.innerHTML = `
        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <span>${escapeHtml(copy)}</span>
            <button
                type="button"
                data-av-action="start-link"
                class="w-full sm:w-auto px-3 py-1.5 rounded-lg text-xs font-bold border border-brand-amber/60 text-brand-amber hover:bg-brand-amber/20 transition">
                Link Discord
            </button>
        </div>
    `;
    msg.classList.remove('hidden');
    msg.classList.remove('border-brand-rose/40', 'text-brand-rose');
    msg.classList.add('border-brand-amber/40', 'text-brand-amber', 'bg-brand-amber/10');
}

function startAvailabilityLinkFlow() {
    if (accessState.authenticated && !accessState.linkedDiscord) {
        window.location.href = `${AUTH_BASE}/link/start`;
        return;
    }

    if (!accessState.authenticated) {
        window.location.href = `${AUTH_BASE}/login`;
        return;
    }

    window.location.href = `${AUTH_BASE}/link/start`;
}

function renderStatusMessages() {
    const responseEl = document.getElementById('availability-response-status');
    if (responseEl) {
        responseEl.textContent = responseStatus.message || '';
        responseEl.classList.remove('text-brand-rose', 'text-brand-emerald', 'text-slate-500');
        if (!responseStatus.message) {
            responseEl.classList.add('text-slate-500');
        } else {
            responseEl.classList.add(responseStatus.error ? 'text-brand-rose' : 'text-brand-emerald');
        }
    }

    const prefsEl = document.getElementById('prefs-status-msg');
    if (prefsEl) {
        prefsEl.textContent = prefsStatus.message || '';
        prefsEl.classList.remove('text-brand-rose', 'text-brand-emerald', 'text-brand-amber', 'text-slate-400');

        if (prefsStatus.message) {
            prefsEl.classList.add(prefsStatus.error ? 'text-brand-rose' : 'text-brand-emerald');
        } else if (!accessState.canSubmit && accessState.authenticated) {
            prefsEl.textContent = 'Link your Discord profile to manage settings.';
            prefsEl.classList.add('text-brand-amber');
        } else {
            prefsEl.classList.add('text-slate-400');
        }
    }
}

function renderTodayTomorrowActions() {
    const container = document.getElementById('availability-actions');
    if (!container) return;

    const canAct = accessState.canSubmit && !responseInFlight;
    const todayIso = toISODate(new Date());
    const tomorrowIso = toISODate(addDays(new Date(), 1));

    const cards = [
        renderActionCard('Today', todayIso, canAct),
        renderActionCard('Tomorrow', tomorrowIso, canAct)
    ];

    container.innerHTML = cards.join('');
}

function renderCurrentQueue() {
    const container = document.getElementById('availability-current-queue');
    if (!container) return;

    const todayIso = toISODate(new Date());
    const entry = getEntry(todayIso);
    const lookingUsers = Array.isArray(entry.usersByStatus?.LOOKING) ? entry.usersByStatus.LOOKING : [];

    if (!entry.usersByStatus || !lookingUsers.length) {
        container.innerHTML = '<div class="text-xs text-slate-500">Queue is empty</div>';
        return;
    }

    const maxRows = 12;
    const rows = lookingUsers.slice(0, maxRows).map((user) => {
        const displayName = escapeHtml(user?.display_name || (user?.user_id ? `User ${user.user_id}` : 'Player'));
        const timeWindow = escapeHtml(extractQueueTimeWindow(user));
        const timeHtml = timeWindow
            ? `<div class="text-[11px] text-slate-400 whitespace-nowrap">${timeWindow}</div>`
            : '';
        return `
            <div class="flex items-center justify-between gap-3 rounded-lg border border-white/10 bg-slate-950/35 px-3 py-2">
                <div class="text-sm font-semibold text-slate-100 truncate">${displayName}</div>
                ${timeHtml}
            </div>
        `;
    });

    const remaining = Math.max(0, lookingUsers.length - maxRows);
    const moreHtml = remaining > 0
        ? `<div class="text-[11px] text-slate-500">+${remaining} more in queue</div>`
        : '';

    container.innerHTML = `${rows.join('')}${moreHtml}`;
}

function renderPromoteControls() {
    const promoteBtn = document.getElementById('availability-promote-btn');
    if (!promoteBtn) return;

    const eligible = accessState.authenticated && accessState.linkedDiscord && accessState.canPromote;
    if (eligible) {
        promoteBtn.classList.remove('hidden', 'opacity-60', 'cursor-not-allowed');
        promoteBtn.disabled = promoteInFlight;
        return;
    }

    if (accessState.authenticated && accessState.linkedDiscord && !accessState.canPromote) {
        promoteBtn.classList.remove('hidden');
        promoteBtn.disabled = true;
        promoteBtn.classList.add('opacity-60', 'cursor-not-allowed');
        promoteBtn.title = 'Promote requires promoter/admin permission.';
        return;
    }

    if (accessState.authenticated && !accessState.linkedDiscord) {
        promoteBtn.classList.remove('hidden');
        promoteBtn.disabled = true;
        promoteBtn.classList.add('opacity-60', 'cursor-not-allowed');
        promoteBtn.title = 'Link Discord to promote.';
        return;
    }

    promoteBtn.classList.add('hidden');
}

function renderCampaignStatus() {
    const statusEl = document.getElementById('availability-campaign-status');
    if (!statusEl) return;

    const campaign = promoteState.campaign;
    if (!campaign) {
        statusEl.classList.add('hidden');
        statusEl.textContent = '';
        return;
    }

    const jobs = Array.isArray(campaign.jobs) ? campaign.jobs : [];
    const jobSummary = jobs.map((job) => `${job.job_type}:${job.status}`).join(' | ');
    const channels = campaign.channels_summary || {};
    const channelBits = ['discord', 'telegram', 'signal']
        .map((channel) => `${channel}: ${Number(channels[channel] || 0)}`)
        .join(', ');

    statusEl.classList.remove('hidden');
    statusEl.innerHTML = `
        <div class="font-semibold text-brand-purple">Campaign: ${escapeHtml(String(campaign.status || 'scheduled'))}</div>
        <div class="text-slate-300 mt-1">${escapeHtml(`Recipients: ${campaign.recipient_count || 0} (${channelBits})`)}</div>
        <div class="text-slate-400 mt-1 text-[11px]">${escapeHtml(jobSummary || 'No jobs')}</div>
    `;
}

function renderPlanningRoom() {
    const statusEl = document.getElementById('availability-planning-status');
    const errorEl = document.getElementById('availability-planning-error');
    const openBtn = document.getElementById('availability-planning-open-btn');
    const joinBtn = document.getElementById('availability-planning-join-btn');
    const panel = document.getElementById('availability-planning-panel');
    const actionStatusEl = document.getElementById('availability-planning-action-status');

    if (!statusEl || !openBtn || !panel || !actionStatusEl) return;

    const data = planningState.data || {};
    const session = data.session || null;
    const participants = Array.isArray(data.participants) ? data.participants : [];
    const sessionReady = data.session_ready || {};
    const unlocked = Boolean(data.unlocked || session);
    const linked = accessState.linkedDiscord;
    const authenticated = accessState.authenticated;
    const participantIds = new Set(participants.map((row) => Number(row?.user_id || 0)).filter((value) => value > 0));
    const meDiscordId = Number(currentUser?.id || 0);
    const iAmParticipant = meDiscordId > 0 && participantIds.has(meDiscordId);

    if (planningState.error) {
        errorEl?.classList.remove('hidden');
        if (errorEl) errorEl.textContent = planningState.error;
    } else if (errorEl) {
        errorEl.classList.add('hidden');
        errorEl.textContent = '';
    }

    if (!authenticated) {
        openBtn.disabled = false;
        openBtn.textContent = 'Log in to plan';
        openBtn.classList.remove('opacity-60', 'cursor-not-allowed');
        statusEl.textContent = 'Planning room is available to linked users once session-ready threshold is met.';
    } else if (!linked) {
        openBtn.disabled = false;
        openBtn.textContent = 'Link Discord';
        openBtn.classList.remove('opacity-60', 'cursor-not-allowed');
        statusEl.textContent = 'Link Discord to create or join planning room.';
    } else if (session) {
        openBtn.disabled = false;
        openBtn.textContent = planningState.panelOpen ? 'Hide planning room' : 'Open planning room';
        openBtn.classList.remove('opacity-60', 'cursor-not-allowed');
        const threadSuffix = session.discord_thread_id ? `, thread: ${session.discord_thread_id}` : '';
        statusEl.textContent = `Session active for ${String(data.date || '--')} (${participants.length} participants${threadSuffix}).`;
    } else if (unlocked) {
        openBtn.disabled = false;
        openBtn.textContent = 'Create planning room';
        openBtn.classList.remove('opacity-60', 'cursor-not-allowed');
        statusEl.textContent = 'Session-ready threshold reached. Create the planning room to start drafting.';
    } else {
        openBtn.disabled = true;
        openBtn.textContent = 'Planning locked';
        openBtn.classList.add('opacity-60', 'cursor-not-allowed');
        statusEl.textContent = `Waiting for Looking threshold: ${Number(sessionReady.looking_count || 0)}/${Number(sessionReady.threshold || 0)}.`;
    }

    if (joinBtn) {
        const canShowJoin = authenticated && linked && Boolean(session) && !iAmParticipant;
        joinBtn.classList.toggle('hidden', !canShowJoin);
        joinBtn.disabled = planningActionInFlight;
        joinBtn.classList.toggle('opacity-60', planningActionInFlight);
        joinBtn.classList.toggle('cursor-not-allowed', planningActionInFlight);
    }

    if (!planningState.actionStatus.message) {
        actionStatusEl.textContent = '';
        actionStatusEl.classList.remove('text-brand-rose', 'text-brand-emerald');
        actionStatusEl.classList.add('text-slate-400');
    } else {
        actionStatusEl.textContent = planningState.actionStatus.message;
        actionStatusEl.classList.remove('text-slate-400', 'text-brand-rose', 'text-brand-emerald');
        actionStatusEl.classList.add(planningState.actionStatus.error ? 'text-brand-rose' : 'text-brand-emerald');
    }

    if (!planningState.panelOpen || !session) {
        panel.classList.add('hidden');
        return;
    }

    panel.classList.remove('hidden');
    renderPlanningParticipants(participants);
    renderPlanningSuggestions(session);
    renderPlanningDraft(participants, session);
}

function renderPlanningParticipants(participants) {
    const container = document.getElementById('availability-planning-participants');
    if (!container) return;
    if (!Array.isArray(participants) || !participants.length) {
        container.innerHTML = '<div class="text-xs text-slate-500">No participants yet.</div>';
        return;
    }

    container.innerHTML = participants.map((row) => {
        const status = String(row?.status || '').toUpperCase();
        const statusClass = status === 'LOOKING'
            ? 'text-brand-cyan'
            : status === 'AVAILABLE'
                ? 'text-brand-emerald'
                : 'text-brand-amber';
        return `
            <div class="flex items-center justify-between gap-2 rounded-lg border border-white/10 bg-slate-950/35 px-2.5 py-1.5">
                <span class="text-xs text-slate-200">${escapeHtml(row?.display_name || `User ${row?.user_id || '?'}`)}</span>
                <span class="text-[11px] font-semibold ${statusClass}">${escapeHtml(status)}</span>
            </div>
        `;
    }).join('');
}

function renderPlanningSuggestions(session) {
    const container = document.getElementById('availability-planning-suggestions');
    const suggestInput = document.getElementById('availability-planning-suggestion-input');
    const suggestBtn = document.getElementById('availability-planning-suggest-btn');
    if (!container) return;

    const suggestions = Array.isArray(session?.suggestions) ? session.suggestions : [];
    const canSubmit = accessState.canSubmit && !planningActionInFlight;
    if (suggestInput) suggestInput.disabled = !canSubmit;
    if (suggestBtn) {
        suggestBtn.disabled = !canSubmit;
        suggestBtn.classList.toggle('opacity-60', !canSubmit);
        suggestBtn.classList.toggle('cursor-not-allowed', !canSubmit);
    }

    if (!suggestions.length) {
        container.innerHTML = '<div class="text-xs text-slate-500">No suggestions yet.</div>';
        return;
    }

    container.innerHTML = suggestions.map((row) => {
        const voted = Boolean(row?.voted_by_me);
        const voteDisabled = accessState.canSubmit && !planningActionInFlight ? '' : 'disabled';
        const voteClass = voted
            ? 'border-brand-purple/50 text-brand-purple bg-brand-purple/10'
            : 'border-white/15 text-slate-300 hover:border-brand-purple/40 hover:text-brand-purple';
        return `
            <div class="rounded-lg border border-white/10 bg-slate-950/30 px-2.5 py-2">
                <div class="flex items-start justify-between gap-2">
                    <div class="min-w-0">
                        <div class="text-sm font-semibold text-slate-100 truncate">${escapeHtml(String(row?.name || 'Unnamed'))}</div>
                        <div class="text-[11px] text-slate-500">by ${escapeHtml(String(row?.suggested_by_name || 'Unknown'))}</div>
                    </div>
                    <div class="text-xs text-slate-300 font-semibold">${Number(row?.votes || 0)} vote${Number(row?.votes || 0) === 1 ? '' : 's'}</div>
                </div>
                <div class="mt-2">
                    <button
                        type="button"
                        data-av-action="vote-suggestion"
                        data-suggestion-id="${Number(row?.id || 0)}"
                        ${voteDisabled}
                        class="px-2.5 py-1 rounded-lg text-[11px] font-bold border transition ${voteClass}">
                        ${voted ? 'Voted' : 'Vote'}
                    </button>
                </div>
            </div>
        `;
    }).join('');
}

function renderPlanningDraft(participants, session) {
    const poolEl = document.getElementById('availability-planning-draft-pool');
    const teamAEl = document.getElementById('availability-planning-team-a');
    const teamBEl = document.getElementById('availability-planning-team-b');
    const autoBtn = document.getElementById('availability-planning-auto-draft-btn');
    const saveBtn = document.getElementById('availability-planning-save-teams-btn');
    if (!poolEl || !teamAEl || !teamBEl || !autoBtn || !saveBtn) return;

    const canManage = canManagePlanningTeams(session);
    const disableManage = !canManage || planningActionInFlight;

    autoBtn.disabled = disableManage;
    autoBtn.classList.toggle('opacity-60', disableManage);
    autoBtn.classList.toggle('cursor-not-allowed', disableManage);
    saveBtn.disabled = disableManage;
    saveBtn.classList.toggle('opacity-60', disableManage);
    saveBtn.classList.toggle('cursor-not-allowed', disableManage);

    if (!Array.isArray(participants) || !participants.length) {
        poolEl.innerHTML = '<span class="text-[11px] text-slate-500">No participants available for drafting.</span>';
        teamAEl.innerHTML = '<div class="text-[11px] text-slate-500">No members.</div>';
        teamBEl.innerHTML = '<div class="text-[11px] text-slate-500">No members.</div>';
        return;
    }

    const assignment = planningState.assignments;
    poolEl.innerHTML = participants.map((row) => {
        const userId = Number(row?.user_id || 0);
        const side = String(assignment.get(userId) || '');
        const chipClass = side === 'A'
            ? 'border-brand-cyan/50 text-brand-cyan bg-brand-cyan/10'
            : side === 'B'
                ? 'border-brand-emerald/50 text-brand-emerald bg-brand-emerald/10'
                : 'border-white/15 text-slate-300 bg-slate-950/40';
        const disabled = disableManage ? 'disabled' : '';
        const sideLabel = side ? ` · ${side}` : '';
        return `
            <button
                type="button"
                data-av-action="cycle-assignment"
                data-user-id="${userId}"
                ${disabled}
                class="px-2.5 py-1 rounded-full text-[11px] font-semibold border transition ${chipClass}">
                ${escapeHtml(String(row?.display_name || `User ${userId}`))}${escapeHtml(sideLabel)}
            </button>
        `;
    }).join('');

    const teamA = participants.filter((row) => String(assignment.get(Number(row?.user_id || 0))) === 'A');
    const teamB = participants.filter((row) => String(assignment.get(Number(row?.user_id || 0))) === 'B');
    teamAEl.innerHTML = renderPlanningTeamMembers(teamA);
    teamBEl.innerHTML = renderPlanningTeamMembers(teamB);
}

function renderPlanningTeamMembers(rows) {
    if (!Array.isArray(rows) || !rows.length) {
        return '<div class="text-[11px] text-slate-500">No members.</div>';
    }
    return rows.map((row) => `
        <div class="text-xs text-slate-200 rounded-md border border-white/10 bg-slate-950/35 px-2 py-1">
            ${escapeHtml(String(row?.display_name || `User ${row?.user_id || '?'}`))}
        </div>
    `).join('');
}

function reconcilePlanningAssignments() {
    const participants = Array.isArray(planningState.data?.participants) ? planningState.data.participants : [];
    const participantIds = new Set(participants.map((row) => Number(row?.user_id || 0)).filter((value) => value > 0));

    const serverAssignments = new Map();
    const teams = planningState.data?.session?.teams || {};
    ['A', 'B'].forEach((side) => {
        const members = Array.isArray(teams?.[side]?.members) ? teams[side].members : [];
        members.forEach((member) => {
            const memberId = Number(member?.user_id || 0);
            if (memberId > 0) serverAssignments.set(memberId, side);
        });
    });

    if (serverAssignments.size > 0) {
        planningState.assignments = serverAssignments;
        return;
    }

    const next = new Map();
    for (const [rawId, side] of planningState.assignments.entries()) {
        const userId = Number(rawId);
        if (!participantIds.has(userId)) continue;
        if (side !== 'A' && side !== 'B') continue;
        next.set(userId, side);
    }
    planningState.assignments = next;
}

function canManagePlanningTeams(session) {
    if (!session) return false;
    if (!accessState.canSubmit) return false;
    const viewerWebsiteId = Number(planningState.data?.viewer?.website_user_id || currentUser?.id || 0);
    if (viewerWebsiteId > 0 && viewerWebsiteId === Number(session.created_by_user_id || 0)) return true;
    return Boolean(accessState.canPromote);
}

function renderActionCard(title, dateIso, canAct) {
    const entry = getEntry(dateIso);
    const selected = entry.myStatus;

    const buttonHtml = STATUS_ORDER.map((statusKey) => {
        const meta = STATUS_META[statusKey];
        const selectedClass = selected === statusKey ? meta.selectedClass : meta.idleClass;
        const disabledClass = canAct ? '' : 'opacity-60 cursor-not-allowed';
        const disabled = canAct ? '' : 'disabled';

        return `
            <button
                type="button"
                data-av-action="set-status"
                data-date-iso="${escapeHtml(dateIso)}"
                data-status-key="${escapeHtml(statusKey)}"
                ${disabled}
                class="px-2.5 py-1.5 rounded-lg text-[11px] font-bold border transition ${selectedClass} ${disabledClass}">
                ${meta.shortLabel}
            </button>
        `;
    }).join('');

    return `
        <div class="glass-card rounded-xl p-4 border border-white/10">
            <div class="flex items-start justify-between gap-3">
                <div>
                    <div class="text-sm font-bold text-white">${escapeHtml(title)}</div>
                    <div class="text-[11px] text-slate-500 mt-1">${escapeHtml(formatDate(dateIso, { weekday: 'short', month: 'short', day: 'numeric' }))}</div>
                </div>
                <div class="text-[11px] text-slate-400">${escapeHtml(selected ? `${STATUS_META[selected].emoji} ${STATUS_META[selected].label}` : 'Not set')}</div>
            </div>
            <div class="flex flex-wrap gap-2 mt-3">${buttonHtml}</div>
            <div class="text-[11px] text-slate-500 mt-3">${entry.total} responses</div>
        </div>
    `;
}

function renderCalendar() {
    const label = document.getElementById('availability-calendar-month-label');
    if (label) {
        label.textContent = visibleMonth.toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
    }

    const grid = document.getElementById('availability-calendar-grid');
    if (!grid) return;

    const monthStart = startOfMonth(visibleMonth);
    const gridStart = addDays(monthStart, -monthStart.getDay());

    const cells = [];
    for (let i = 0; i < 42; i += 1) {
        const cellDate = addDays(gridStart, i);
        const dateIso = toISODate(cellDate);
        const entry = getEntry(dateIso);

        const inMonth = cellDate.getMonth() === visibleMonth.getMonth();
        const isSelected = dateIso === selectedDateIso;
        const isToday = dateIso === toISODate(new Date());

        const toneClass = inMonth
            ? 'bg-slate-950/40 border-white/10 hover:border-brand-cyan/40'
            : 'bg-slate-950/20 border-white/5 text-slate-600 hover:border-white/10';
        const selectedClass = isSelected ? 'ring-2 ring-brand-cyan/50 border-brand-cyan/50' : '';
        const todayClass = isToday ? 'shadow-[0_0_0_1px_rgba(16,185,129,0.45)]' : '';

        const dayClass = inMonth ? 'text-slate-100' : 'text-slate-600';

        cells.push(`
            <button
                type="button"
                data-av-action="select-date"
                data-date-iso="${escapeHtml(dateIso)}"
                class="rounded-xl border p-2 text-left transition min-h-[90px] ${toneClass} ${selectedClass} ${todayClass}">
                <div class="flex items-center justify-between">
                    <span class="text-xs font-semibold ${dayClass}">${cellDate.getDate()}</span>
                    <span class="text-[10px] text-slate-400">${entry.total}</span>
                </div>
                <div class="mt-2">${renderStackedBar(entry.counts, entry.total, 'h-1.5')}</div>
            </button>
        `);
    }

    grid.innerHTML = cells.join('');
}

function renderCalendarVisibility() {
    const body = document.getElementById('availability-calendar-body');
    if (body) {
        body.classList.toggle('hidden', !calendarExpanded);
    }

    const toggleBtn = document.getElementById('availability-calendar-toggle');
    if (toggleBtn) {
        toggleBtn.textContent = calendarExpanded ? 'Close calendar' : 'Open calendar';
        toggleBtn.setAttribute('aria-expanded', calendarExpanded ? 'true' : 'false');
    }
}

function toggleAvailabilityCalendar() {
    calendarExpanded = !calendarExpanded;
    renderCalendarVisibility();
    if (calendarExpanded) {
        renderCalendar();
    }
}

function renderQuickView() {
    const container = document.getElementById('availability-quick-view');
    if (!container) return;

    const rows = [];
    for (let i = 0; i < UPCOMING_DAYS; i += 1) {
        const dayDate = addDays(new Date(), UPCOMING_START_OFFSET + i);
        const dateIso = toISODate(dayDate);
        const entry = getEntry(dateIso);
        const selected = selectedDateIso === dateIso;

        rows.push(`
            <button
                type="button"
                data-av-action="select-upcoming-date"
                data-date-iso="${escapeHtml(dateIso)}"
                class="w-full rounded-xl border p-3 text-left transition ${selected ? 'border-brand-cyan/50 bg-brand-cyan/10' : 'border-white/10 bg-slate-950/30 hover:border-brand-cyan/35'}">
                <div class="flex items-center justify-between gap-2 mb-1">
                    <div>
                        <div class="text-xs font-bold text-white">${escapeHtml(formatDate(dateIso, { weekday: 'short' }))}</div>
                        <div class="text-[11px] text-slate-500">${escapeHtml(formatDate(dateIso, { month: 'short', day: 'numeric' }))}</div>
                    </div>
                    <div class="text-[11px] text-slate-300">${entry.total} total</div>
                </div>
                <div class="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-[11px]">
                    <span class="text-brand-cyan">Looking: ${entry.counts.looking}</span>
                    <span class="text-brand-emerald">Available: ${entry.counts.available}</span>
                    <span class="text-brand-amber">Maybe: ${entry.counts.maybe}</span>
                    <span class="text-brand-rose">Not playing: ${entry.counts.not_playing}</span>
                </div>
                ${renderStackedBar(entry.counts, entry.total, 'h-1.5')}
            </button>
        `);
    }

    if (!rows.length) {
        container.innerHTML = '<div class="text-xs text-slate-500">No upcoming days available.</div>';
        return;
    }

    container.innerHTML = rows.join('');
}

function renderSelectedDayPanel() {
    const titleEl = document.getElementById('availability-selected-date-title');
    const subtitleEl = document.getElementById('availability-selected-date-subtitle');
    const totalEl = document.getElementById('availability-selected-date-total');
    const countsEl = document.getElementById('availability-selected-date-counts');
    const actionsEl = document.getElementById('availability-selected-date-actions');
    const notesEl = document.getElementById('availability-selected-date-notes');

    if (!titleEl || !subtitleEl || !totalEl || !countsEl || !actionsEl || !notesEl) return;

    const entry = getEntry(selectedDateIso);
    titleEl.textContent = formatDate(selectedDateIso, { weekday: 'long', month: 'long', day: 'numeric' });
    subtitleEl.textContent = selectedDateIso;
    totalEl.textContent = `${entry.total} response${entry.total === 1 ? '' : 's'}`;

    countsEl.innerHTML = STATUS_ORDER.map((statusKey) => {
        const meta = STATUS_META[statusKey];
        const value = entry.counts[statusKey] || 0;
        return `
            <div class="glass-card rounded-lg p-3 text-center border border-white/10">
                <div class="text-xs text-slate-500">${meta.shortLabel}</div>
                <div class="text-2xl font-black ${meta.valueClass}">${value}</div>
            </div>
        `;
    }).join('');

    const selectedDate = parseISODate(selectedDateIso);
    const isPast = selectedDate ? selectedDate < startOfDay(new Date()) : true;
    const canAct = accessState.canSubmit && !isPast && !responseInFlight;

    if (canAct) {
        actionsEl.innerHTML = `
            <div class="text-[11px] text-slate-500 mb-2">Set your status for ${escapeHtml(selectedDateIso)}</div>
            <div class="flex flex-wrap gap-2">
                ${STATUS_ORDER.map((statusKey) => {
                    const meta = STATUS_META[statusKey];
                    const selected = entry.myStatus === statusKey;
                    return `
                        <button
                            type="button"
                            data-av-action="set-status"
                            data-date-iso="${escapeHtml(selectedDateIso)}"
                            data-status-key="${escapeHtml(statusKey)}"
                            class="px-3 py-1.5 rounded-lg text-xs font-bold border transition ${selected ? meta.selectedClass : meta.idleClass}">
                            ${meta.emoji} ${meta.shortLabel}
                        </button>
                    `;
                }).join('')}
            </div>
        `;
    } else if (isPast) {
        actionsEl.innerHTML = '<div class="text-[11px] text-slate-500">Past days are read-only.</div>';
    } else if (!accessState.canSubmit) {
        actionsEl.innerHTML = '<div class="text-[11px] text-brand-amber">Log in and link Discord to set availability.</div>';
    } else {
        actionsEl.innerHTML = '<div class="text-[11px] text-slate-500">Saving in progress...</div>';
    }

    const notes = [];
    if (aggregateError) {
        notes.push(`<div class="text-brand-rose">${escapeHtml(aggregateError)}</div>`);
    } else if (entry.total === 0) {
        notes.push('<div>No availability entries for this date yet.</div>');
    } else {
        notes.push('<div>Aggregated from website availability entries.</div>');
    }

    if (selectedDateIso === sessionReadyState.date) {
        if (sessionReadyState.ready) {
            notes.push(`<div class="mt-1 text-brand-emerald">Session ready: ${sessionReadyState.lookingCount}/${sessionReadyState.threshold} players marked Looking.</div>`);
        } else {
            notes.push(`<div class="mt-1">Session not ready yet: ${sessionReadyState.lookingCount}/${sessionReadyState.threshold} Looking.</div>`);
        }
    }

    const users = entry.usersByStatus;
    if (users) {
        const chips = STATUS_ORDER.map((statusKey) => {
            const statusName = STATUS_TO_API[statusKey];
            const list = Array.isArray(users[statusName]) ? users[statusName] : [];
            if (!list.length) return '';
            const names = list.slice(0, 8).map((u) => escapeHtml(u.display_name || `User ${u.user_id}`)).join(', ');
            return `<div>${STATUS_META[statusKey].emoji} ${STATUS_META[statusKey].shortLabel}: ${names}</div>`;
        }).filter(Boolean);
        if (chips.length) {
            notes.push(`<div class="mt-2 space-y-1">${chips.join('')}</div>`);
        }
    }

    notesEl.className = 'text-xs text-slate-500';
    notesEl.innerHTML = notes.join('');
}

function renderPreferencesSection() {
    const section = document.getElementById('availability-prefs-section');
    if (!section) return;

    if (!accessState.authenticated) {
        section.classList.add('hidden');
        return;
    }

    section.classList.remove('hidden');

    const canEdit = accessState.canSubmit && !prefsInFlight;

    setCheckboxState('pref-discord', prefsState.discordNotify, canEdit);
    setCheckboxState('pref-telegram', prefsState.telegramNotify, canEdit);
    setCheckboxState('pref-signal', prefsState.signalNotify, canEdit);
    setCheckboxState('pref-ready-sound', prefsState.getReadySound, canEdit);

    const saveBtn = document.getElementById('save-prefs-btn');
    if (saveBtn) {
        saveBtn.disabled = !canEdit;
        saveBtn.classList.toggle('opacity-60', !canEdit);
        saveBtn.classList.toggle('cursor-not-allowed', !canEdit);
    }
}

function setCheckboxState(id, checked, enabled) {
    const el = document.getElementById(id);
    if (!el) return;
    el.checked = Boolean(checked);
    el.disabled = !enabled;
}

async function openAvailabilityPromoteModal() {
    if (!accessState.canPromote || promoteInFlight) return;
    const modal = document.getElementById('modal-availability-promote');
    if (!modal) return;
    modal.classList.remove('hidden');
    await refreshPromotePreview();
}

function closeAvailabilityPromoteModal() {
    const modal = document.getElementById('modal-availability-promote');
    if (!modal) return;
    modal.classList.add('hidden');
    setPromoteError('');
}

function setPromoteError(message) {
    const errorEl = document.getElementById('availability-promote-error');
    if (!errorEl) return;
    const text = String(message || '').trim();
    if (!text) {
        errorEl.classList.add('hidden');
        errorEl.textContent = '';
        return;
    }
    errorEl.classList.remove('hidden');
    errorEl.textContent = text;
}

function promoteOptionsFromUi() {
    const includeAvailable = document.getElementById('availability-promote-include-available')?.checked !== false;
    const includeMaybe = Boolean(document.getElementById('availability-promote-include-maybe')?.checked);
    const dryRun = Boolean(document.getElementById('availability-promote-dry-run')?.checked);
    return { includeAvailable, includeMaybe, dryRun };
}

async function refreshPromotePreview() {
    if (promotePreviewInFlight) return;
    promotePreviewInFlight = true;

    const previewEl = document.getElementById('availability-promote-preview');
    if (previewEl) {
        previewEl.textContent = 'Loading recipient preview...';
    }
    setPromoteError('');

    try {
        const opts = promoteOptionsFromUi();
        const query = new URLSearchParams({
            include_available: opts.includeAvailable ? 'true' : 'false',
            include_maybe: opts.includeMaybe ? 'true' : 'false'
        }).toString();
        const payload = await fetchJSON(`${API_BASE}/availability/promotions/preview?${query}`, NO_STORE_FETCH);
        promoteState.preview = payload;

        if (!previewEl) return;
        const channels = payload?.channels_summary || {};
        const channelSummary = ['discord', 'telegram', 'signal']
            .map((channel) => `${channel}: ${Number(channels[channel] || 0)}`)
            .join(', ');
        previewEl.innerHTML = `
            <div class="font-semibold text-slate-200">Date: ${escapeHtml(String(payload?.campaign_date || '--'))} (21:00 CET)</div>
            <div class="mt-1">Recipients: <span class="text-brand-purple font-bold">${Number(payload?.recipient_count || 0)}</span></div>
            <div class="mt-1 text-slate-400">${escapeHtml(channelSummary)}</div>
        `;
    } catch (err) {
        setPromoteError(formatErrorMessage(err, 'Failed to load preview'));
        if (previewEl) {
            previewEl.textContent = 'Could not load preview.';
        }
    } finally {
        promotePreviewInFlight = false;
    }
}

async function confirmAvailabilityPromote() {
    if (promoteInFlight) return;
    promoteInFlight = true;
    setPromoteError('');

    const confirmBtn = document.getElementById('availability-promote-confirm-btn');
    if (confirmBtn) {
        confirmBtn.disabled = true;
        confirmBtn.classList.add('opacity-60', 'cursor-not-allowed');
    }

    try {
        const opts = promoteOptionsFromUi();
        const resp = await fetch(`${API_BASE}/availability/promotions/campaigns`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'same-origin',
            body: JSON.stringify({
                include_available: opts.includeAvailable,
                include_maybe: opts.includeMaybe,
                dry_run: opts.dryRun
            })
        });

        let payload = null;
        try {
            payload = await resp.json();
        } catch (_err) {
            payload = null;
        }

        if (!resp.ok) {
            throw new Error(payload?.detail || `HTTP ${resp.status}`);
        }

        responseStatus = {
            message: 'Scheduled: 20:45 CET and 21:00 CET promotion jobs.',
            error: false
        };
        renderStatusMessages();
        closeAvailabilityPromoteModal();
        await loadPromotionCampaignState();
        renderCampaignStatus();
    } catch (err) {
        setPromoteError(formatErrorMessage(err, 'Failed to schedule campaign'));
    } finally {
        promoteInFlight = false;
        if (confirmBtn) {
            confirmBtn.disabled = false;
            confirmBtn.classList.remove('opacity-60', 'cursor-not-allowed');
        }
        renderPromoteControls();
    }
}

async function openAvailabilityPlanningRoom() {
    if (!accessState.authenticated) {
        window.location.href = `${AUTH_BASE}/login`;
        return;
    }
    if (!accessState.linkedDiscord) {
        startAvailabilityLinkFlow();
        return;
    }
    if (planningActionInFlight) return;

    const data = planningState.data || {};
    const session = data.session || null;

    if (session) {
        planningState.panelOpen = !planningState.panelOpen;
        planningState.actionStatus = { message: '', error: false };
        renderPlanningRoom();
        return;
    }

    if (!data.unlocked) {
        planningState.actionStatus = {
            message: 'Planning room is still locked until readiness threshold is reached.',
            error: true
        };
        renderPlanningRoom();
        return;
    }

    planningActionInFlight = true;
    planningState.actionStatus = { message: 'Creating planning room...', error: false };
    renderPlanningRoom();

    try {
        const payload = await postPlanningJson('/today/create', {});
        planningState.data = payload?.state || planningState.data;
        planningState.panelOpen = true;
        reconcilePlanningAssignments();
        planningState.actionStatus = {
            message: payload?.thread_created
                ? 'Planning room created with Discord thread.'
                : 'Planning room created.',
            error: false
        };
    } catch (err) {
        planningState.actionStatus = {
            message: formatErrorMessage(err, 'Failed to create planning room'),
            error: true
        };
    } finally {
        planningActionInFlight = false;
        renderPlanningRoom();
    }
}

async function joinAvailabilityPlanningRoom() {
    if (!accessState.canSubmit || planningActionInFlight) return;
    planningActionInFlight = true;
    planningState.actionStatus = { message: 'Joining planning room...', error: false };
    renderPlanningRoom();

    try {
        const payload = await postPlanningJson('/today/join', {});
        planningState.data = payload?.state || planningState.data;
        planningState.panelOpen = true;
        reconcilePlanningAssignments();
        planningState.actionStatus = { message: 'Joined planning room and marked as Looking.', error: false };
    } catch (err) {
        planningState.actionStatus = {
            message: formatErrorMessage(err, 'Failed to join planning room'),
            error: true
        };
    } finally {
        planningActionInFlight = false;
        renderPlanningRoom();
    }
}

async function submitAvailabilityPlanningSuggestion() {
    if (!accessState.canSubmit || planningActionInFlight) return;
    const input = document.getElementById('availability-planning-suggestion-input');
    const value = String(input?.value || '').trim();
    if (value.length < 2) {
        planningState.actionStatus = { message: 'Suggestion must be at least 2 characters.', error: true };
        renderPlanningRoom();
        return;
    }

    planningActionInFlight = true;
    planningState.actionStatus = { message: 'Saving suggestion...', error: false };
    renderPlanningRoom();

    try {
        const payload = await postPlanningJson('/today/suggestions', { name: value });
        planningState.data = payload?.state || planningState.data;
        planningState.panelOpen = true;
        reconcilePlanningAssignments();
        planningState.actionStatus = { message: 'Suggestion added.', error: false };
        if (input) input.value = '';
    } catch (err) {
        planningState.actionStatus = {
            message: formatErrorMessage(err, 'Failed to save suggestion'),
            error: true
        };
    } finally {
        planningActionInFlight = false;
        renderPlanningRoom();
    }
}

async function voteAvailabilityPlanningSuggestion(suggestionId) {
    if (!accessState.canSubmit || planningActionInFlight) return;
    const numericId = Number(suggestionId);
    if (!Number.isInteger(numericId) || numericId <= 0) return;

    planningActionInFlight = true;
    planningState.actionStatus = { message: 'Saving vote...', error: false };
    renderPlanningRoom();

    try {
        const payload = await postPlanningJson('/today/vote', { suggestion_id: numericId });
        planningState.data = payload?.state || planningState.data;
        planningState.panelOpen = true;
        reconcilePlanningAssignments();
        planningState.actionStatus = { message: 'Vote saved.', error: false };
    } catch (err) {
        planningState.actionStatus = {
            message: formatErrorMessage(err, 'Failed to save vote'),
            error: true
        };
    } finally {
        planningActionInFlight = false;
        renderPlanningRoom();
    }
}

function cycleAvailabilityPlanningAssignment(userId) {
    if (planningActionInFlight) return;
    const numericId = Number(userId);
    if (!Number.isInteger(numericId) || numericId <= 0) return;
    const participants = Array.isArray(planningState.data?.participants) ? planningState.data.participants : [];
    const allowedIds = new Set(participants.map((row) => Number(row?.user_id || 0)));
    if (!allowedIds.has(numericId)) return;
    if (!canManagePlanningTeams(planningState.data?.session)) return;

    const current = String(planningState.assignments.get(numericId) || '');
    if (current === 'A') {
        planningState.assignments.set(numericId, 'B');
    } else if (current === 'B') {
        planningState.assignments.delete(numericId);
    } else {
        planningState.assignments.set(numericId, 'A');
    }
    renderPlanningRoom();
}

function autoDraftAvailabilityPlanningTeams() {
    if (!canManagePlanningTeams(planningState.data?.session) || planningActionInFlight) return;
    const participants = Array.isArray(planningState.data?.participants) ? planningState.data.participants : [];
    if (!participants.length) return;

    const pool = participants.map((row) => Number(row?.user_id || 0)).filter((value) => value > 0);
    for (let i = pool.length - 1; i > 0; i -= 1) {
        const j = Math.floor(Math.random() * (i + 1));
        const tmp = pool[i];
        pool[i] = pool[j];
        pool[j] = tmp;
    }

    planningState.assignments = new Map();
    pool.forEach((userId, idx) => {
        planningState.assignments.set(userId, idx % 2 === 0 ? 'A' : 'B');
    });
    planningState.actionStatus = { message: 'Auto draft generated. Save to persist.', error: false };
    renderPlanningRoom();
}

async function saveAvailabilityPlanningTeams() {
    if (!canManagePlanningTeams(planningState.data?.session) || planningActionInFlight) return;
    const participants = Array.isArray(planningState.data?.participants) ? planningState.data.participants : [];
    if (!participants.length) return;

    const sideA = [];
    const sideB = [];
    for (const row of participants) {
        const userId = Number(row?.user_id || 0);
        const side = String(planningState.assignments.get(userId) || '');
        if (side === 'A') sideA.push(userId);
        if (side === 'B') sideB.push(userId);
    }

    planningActionInFlight = true;
    planningState.actionStatus = { message: 'Saving teams...', error: false };
    renderPlanningRoom();

    try {
        const payload = await postPlanningJson('/today/teams', {
            side_a: sideA,
            side_b: sideB,
            captain_a: sideA.length ? sideA[0] : null,
            captain_b: sideB.length ? sideB[0] : null
        });
        planningState.data = payload?.state || planningState.data;
        planningState.panelOpen = true;
        reconcilePlanningAssignments();
        planningState.actionStatus = { message: 'Teams saved.', error: false };
    } catch (err) {
        planningState.actionStatus = {
            message: formatErrorMessage(err, 'Failed to save teams'),
            error: true
        };
    } finally {
        planningActionInFlight = false;
        renderPlanningRoom();
    }
}

async function postPlanningJson(path, body) {
    const response = await fetch(`${API_BASE}/planning${path}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        },
        credentials: 'same-origin',
        body: JSON.stringify(body || {})
    });

    let payload = null;
    try {
        payload = await response.json();
    } catch (_err) {
        payload = null;
    }

    if (!response.ok) {
        throw new Error(payload?.detail || `HTTP ${response.status}`);
    }
    return payload;
}

// ============================================================================
// ACTIONS
// ============================================================================

async function setAvailabilityForDate(dateIso, statusKey) {
    if (!accessState.canSubmit || responseInFlight) return;
    if (!STATUS_TO_API[statusKey]) return;

    const targetDate = parseISODate(dateIso);
    if (!targetDate) return;
    if (targetDate < startOfDay(new Date())) {
        responseStatus = { message: 'Past dates are read-only.', error: true };
        renderStatusMessages();
        return;
    }

    responseInFlight = true;
    responseStatus = { message: 'Saving availability...', error: false };
    renderStatusMessages();

    try {
        const resp = await fetch(`${API_BASE}/availability`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'same-origin',
            body: JSON.stringify({
                date: dateIso,
                status: STATUS_TO_API[statusKey]
            })
        });

        let payload = null;
        try {
            payload = await resp.json();
        } catch (_err) {
            payload = null;
        }

        if (!resp.ok) {
            throw new Error(payload?.detail || `HTTP ${resp.status}`);
        }

        responseStatus = {
            message: `Saved ${STATUS_META[statusKey].label} for ${dateIso}.`,
            error: false
        };

        await loadAvailabilityRange();
        renderAll();
        maybePlayGetReadySound();
    } catch (err) {
        responseStatus = {
            message: formatErrorMessage(err, 'Failed to save availability'),
            error: true
        };
        renderStatusMessages();
    } finally {
        responseInFlight = false;
        renderAll();
    }
}

async function submitAvailabilityResponse(dayOffset, statusKey) {
    if (!Number.isInteger(dayOffset)) return;
    const targetDate = toISODate(addDays(new Date(), dayOffset));
    await setAvailabilityForDate(targetDate, statusKey);
}

async function saveAvailabilityPrefs() {
    if (!accessState.canSubmit || prefsInFlight) return;

    prefsInFlight = true;
    prefsStatus = { message: 'Saving settings...', error: false };
    renderStatusMessages();
    renderPreferencesSection();

    const discordNotify = document.getElementById('pref-discord')?.checked ?? prefsState.discordNotify;
    const telegramNotify = document.getElementById('pref-telegram')?.checked ?? prefsState.telegramNotify;
    const signalNotify = document.getElementById('pref-signal')?.checked ?? prefsState.signalNotify;
    const getReadySound = document.getElementById('pref-ready-sound')?.checked ?? prefsState.getReadySound;

    try {
        const resp = await fetch(`${API_BASE}/availability/settings`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'same-origin',
            body: JSON.stringify({
                sound_enabled: Boolean(getReadySound),
                sound_cooldown_seconds: prefsState.soundCooldownSeconds,
                availability_reminders_enabled: prefsState.remindersEnabled,
                timezone: prefsState.timezone,
                discord_notify: Boolean(discordNotify),
                telegram_notify: Boolean(telegramNotify),
                signal_notify: Boolean(signalNotify)
            })
        });

        let payload = null;
        try {
            payload = await resp.json();
        } catch (_err) {
            payload = null;
        }

        if (!resp.ok) {
            throw new Error(payload?.detail || `HTTP ${resp.status}`);
        }

        prefsState.discordNotify = Boolean(payload?.discord_notify ?? discordNotify);
        prefsState.telegramNotify = Boolean(payload?.telegram_notify ?? telegramNotify);
        prefsState.signalNotify = Boolean(payload?.signal_notify ?? signalNotify);
        prefsState.getReadySound = Boolean(payload?.get_ready_sound ?? getReadySound);
        prefsState.soundCooldownSeconds = Math.max(30, countValue(payload?.sound_cooldown_seconds) || prefsState.soundCooldownSeconds);
        prefsState.remindersEnabled = payload?.availability_reminders_enabled !== false;
        prefsState.timezone = typeof payload?.timezone === 'string' ? payload.timezone : prefsState.timezone;

        persistLocalPrefs();
        prefsStatus = { message: 'Settings saved.', error: false };
    } catch (err) {
        prefsStatus = {
            message: formatErrorMessage(err, 'Failed to save settings'),
            error: true
        };
    } finally {
        prefsInFlight = false;
        renderStatusMessages();
        renderPreferencesSection();
    }
}

async function createTodayPoll() {
    // Legacy compatibility button.
    adminStatus = {
        message: 'Date-based availability is active. Poll fallback creation is disabled.',
        error: false
    };
    updateAdminControls();
}

// ============================================================================
// GET READY SOUND
// ============================================================================

function maybePlayGetReadySound() {
    if (!prefsState.getReadySound) return;
    if (!accessState.canSubmit) return;
    if (!isAvailabilityViewActive()) return;
    if (document.visibilityState !== 'visible') return;
    if (!sessionReadyState.ready) return;

    const readyDate = sessionReadyState.date || toISODate(new Date());
    const readyKey = `${readyDate}:${sessionReadyState.eventKey || 'SESSION_READY'}`;
    const now = Date.now();

    const previous = loadReadySoundState();
    const lastKey = previous.key || '';
    const lastAt = Number(previous.ts || 0);

    if (lastKey === readyKey) return;

    const cooldownMs = Math.max(30, prefsState.soundCooldownSeconds) * 1000;
    if (now - lastAt < cooldownMs) return;

    if (playReadySound()) {
        saveReadySoundState({ key: readyKey, ts: now });
    }
}

function playReadySound() {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return false;

    try {
        if (!audioCtx) audioCtx = new Ctx();
        if (audioCtx.state === 'suspended') {
            void audioCtx.resume();
        }

        const start = audioCtx.currentTime + 0.02;
        const notes = [523.25, 659.25, 783.99];

        notes.forEach((frequency, index) => {
            const oscillator = audioCtx.createOscillator();
            const gain = audioCtx.createGain();
            const toneStart = start + index * 0.12;

            oscillator.type = 'triangle';
            oscillator.frequency.value = frequency;

            gain.gain.setValueAtTime(0.0001, toneStart);
            gain.gain.exponentialRampToValueAtTime(0.16, toneStart + 0.02);
            gain.gain.exponentialRampToValueAtTime(0.0001, toneStart + 0.11);

            oscillator.connect(gain);
            gain.connect(audioCtx.destination);
            oscillator.start(toneStart);
            oscillator.stop(toneStart + 0.12);
        });

        return true;
    } catch (err) {
        console.warn('Get-ready sound could not play:', err);
        return false;
    }
}

// ============================================================================
// HELPERS
// ============================================================================

function ensureSelectedDate() {
    if (!selectedDateIso || !parseISODate(selectedDateIso)) {
        selectedDateIso = toISODate(new Date());
    }
}

function getEntry(dateIso) {
    const entry = availabilityByDate.get(dateIso);
    if (entry) return entry;
    return {
        dateIso,
        counts: { looking: 0, available: 0, maybe: 0, not_playing: 0 },
        total: 0,
        myStatus: null,
        usersByStatus: null
    };
}

function normalizeCounts(countsRaw) {
    const raw = countsRaw && typeof countsRaw === 'object' ? countsRaw : {};
    const looking = countValue(raw.LOOKING ?? raw.looking);
    const available = countValue(raw.AVAILABLE ?? raw.available);
    const maybe = countValue(raw.MAYBE ?? raw.maybe);
    const notPlaying = countValue(raw.NOT_PLAYING ?? raw.not_playing ?? raw.notPlaying);
    return {
        looking,
        available,
        maybe,
        not_playing: notPlaying
    };
}

function normalizeStatus(rawStatus) {
    const value = String(rawStatus || '').toUpperCase();
    if (value === 'LOOKING') return 'looking';
    if (value === 'AVAILABLE') return 'available';
    if (value === 'MAYBE') return 'maybe';
    if (value === 'NOT_PLAYING') return 'not_playing';
    return null;
}

function normalizeUsersByStatus(raw) {
    if (!raw || typeof raw !== 'object') return null;
    return {
        LOOKING: Array.isArray(raw.LOOKING) ? raw.LOOKING : [],
        AVAILABLE: Array.isArray(raw.AVAILABLE) ? raw.AVAILABLE : [],
        MAYBE: Array.isArray(raw.MAYBE) ? raw.MAYBE : [],
        NOT_PLAYING: Array.isArray(raw.NOT_PLAYING) ? raw.NOT_PLAYING : []
    };
}

function renderStackedBar(counts, total, heightClass = 'h-2') {
    if (!total || total <= 0) {
        return `<div class="${heightClass} rounded-full bg-slate-800"></div>`;
    }

    const segments = STATUS_ORDER.map((statusKey) => {
        const value = countValue(counts?.[statusKey]);
        const width = ((value / total) * 100).toFixed(1);
        return `<div class="${STATUS_META[statusKey].barClass}" style="width:${width}%"></div>`;
    }).join('');

    return `<div class="flex ${heightClass} rounded-full overflow-hidden bg-slate-800">${segments}</div>`;
}

function formatErrorMessage(err, fallback = 'Request failed') {
    const raw = String(err?.message || fallback);
    if (raw.includes('HTTP 401')) return 'Please log in to continue.';
    if (raw.includes('HTTP 403')) return 'You do not have permission for this action.';
    if (raw.includes('Failed to fetch')) return 'API is currently unavailable.';
    return raw;
}

function countValue(value) {
    const num = Number(value);
    if (!Number.isFinite(num) || num < 0) return 0;
    return Math.floor(num);
}

function isAvailabilityViewActive() {
    const view = document.getElementById('view-availability');
    if (!view) return false;
    return view.classList.contains('active') && !view.classList.contains('hidden');
}

function isAvailabilityRefreshAllowed() {
    return isAvailabilityViewActive() && document.visibilityState === 'visible';
}

function handleDelegatedAvailabilityAction(event) {
    const trigger = event.target?.closest?.('[data-av-action]');
    if (!trigger) return;

    const action = String(trigger.dataset.avAction || '').trim();
    if (!action) return;
    event.preventDefault();

    if (action === 'start-link') {
        startAvailabilityLinkFlow();
        return;
    }

    if (action === 'set-status') {
        const dateIso = String(trigger.dataset.dateIso || '').trim();
        const statusKey = String(trigger.dataset.statusKey || '').trim();
        if (!dateIso || !statusKey) return;
        void setAvailabilityForDate(dateIso, statusKey);
        return;
    }

    if (action === 'select-date') {
        const dateIso = String(trigger.dataset.dateIso || '').trim();
        if (!dateIso) return;
        selectAvailabilityDate(dateIso);
        return;
    }

    if (action === 'select-upcoming-date') {
        const dateIso = String(trigger.dataset.dateIso || '').trim();
        if (!dateIso) return;
        selectUpcomingAvailabilityDate(dateIso);
        return;
    }

    if (action === 'vote-suggestion') {
        const suggestionId = Number(trigger.dataset.suggestionId || 0);
        if (!Number.isFinite(suggestionId) || suggestionId <= 0) return;
        void voteAvailabilityPlanningSuggestion(suggestionId);
        return;
    }

    if (action === 'cycle-assignment') {
        const userId = Number(trigger.dataset.userId || 0);
        if (!Number.isFinite(userId) || userId <= 0) return;
        cycleAvailabilityPlanningAssignment(userId);
    }
}

function stopRefreshTimer() {
    if (!refreshTimer) return;
    clearInterval(refreshTimer);
    refreshTimer = null;
}

function startRefreshTimer() {
    if (refreshTimer || !isAvailabilityRefreshAllowed()) return;

    refreshTimer = window.setInterval(() => {
        if (!isAvailabilityRefreshAllowed()) {
            stopRefreshTimer();
            return;
        }
        void refreshAvailabilityView();
    }, POLL_INTERVAL_MS);
}

function syncRefreshTimer() {
    if (isAvailabilityRefreshAllowed()) {
        startRefreshTimer();
    } else {
        stopRefreshTimer();
    }
}

function ensureRefreshTimer() {
    syncRefreshTimer();
}

function ensureRuntimeListeners() {
    if (runtimeListenersBound) return;

    const availabilityView = document.getElementById('view-availability');
    if (availabilityView) {
        availabilityView.addEventListener('click', handleDelegatedAvailabilityAction);
        if (typeof window.bindInlineClickActions === 'function') {
            window.bindInlineClickActions(availabilityView);
        }
    }

    document.addEventListener('visibilitychange', () => {
        syncRefreshTimer();
        if (document.visibilityState === 'visible' && isAvailabilityViewActive()) {
            void refreshAvailabilityView();
        }
    });

    if (availabilityView && typeof MutationObserver !== 'undefined') {
        const viewObserver = new MutationObserver(() => {
            syncRefreshTimer();
        });
        viewObserver.observe(availabilityView, { attributes: true, attributeFilter: ['class'] });
    }

    ['availability-promote-include-available', 'availability-promote-include-maybe', 'availability-promote-dry-run']
        .forEach((id) => {
            const element = document.getElementById(id);
            if (!element) return;
            element.addEventListener('change', () => {
                const modal = document.getElementById('modal-availability-promote');
                if (modal && !modal.classList.contains('hidden')) {
                    void refreshPromotePreview();
                }
            });
        });

    runtimeListenersBound = true;
}

function selectAvailabilityDate(dateIso) {
    const parsed = parseISODate(dateIso);
    if (!parsed) return;

    selectedDateIso = dateIso;
    visibleMonth = startOfMonth(parsed);

    renderCalendar();
    renderQuickView();
    renderSelectedDayPanel();
}

function selectUpcomingAvailabilityDate(dateIso) {
    selectAvailabilityDate(dateIso);
    const detailPanel = document.getElementById('availability-selected-day-panel');
    if (detailPanel && typeof detailPanel.scrollIntoView === 'function') {
        detailPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

function availabilityPrevMonth() {
    visibleMonth = new Date(visibleMonth.getFullYear(), visibleMonth.getMonth() - 1, 1);
    renderCalendar();
}

function availabilityNextMonth() {
    visibleMonth = new Date(visibleMonth.getFullYear(), visibleMonth.getMonth() + 1, 1);
    renderCalendar();
}

function extractQueueTimeWindow(user) {
    if (!user || typeof user !== 'object') return '';

    const direct = firstNonEmptyString([
        user.time_window,
        user.timeWindow,
        user.window,
        user.availability_window,
        user.time_range
    ]);
    if (direct) return direct;

    const start = firstNonEmptyString([
        user.start_time,
        user.startTime,
        user.window_start,
        user.from,
        user.from_time
    ]);
    const end = firstNonEmptyString([
        user.end_time,
        user.endTime,
        user.window_end,
        user.to,
        user.to_time
    ]);

    if (start && end) return `${start} - ${end}`;
    if (start) return `from ${start}`;
    if (end) return `until ${end}`;
    return '';
}

function firstNonEmptyString(values) {
    if (!Array.isArray(values)) return '';
    for (const value of values) {
        const normalized = String(value || '').trim();
        if (normalized) return normalized;
    }
    return '';
}

function toISODate(dateObj) {
    const y = dateObj.getFullYear();
    const m = String(dateObj.getMonth() + 1).padStart(2, '0');
    const d = String(dateObj.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
}

function parseISODate(dateIso) {
    const match = String(dateIso || '').match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!match) return null;
    const [, y, m, d] = match;
    return new Date(Number(y), Number(m) - 1, Number(d));
}

function startOfMonth(dateObj) {
    return new Date(dateObj.getFullYear(), dateObj.getMonth(), 1);
}

function startOfDay(dateObj) {
    return new Date(dateObj.getFullYear(), dateObj.getMonth(), dateObj.getDate());
}

function addDays(dateObj, days) {
    const copy = new Date(dateObj);
    copy.setDate(copy.getDate() + days);
    return copy;
}

function formatDate(dateIso, options) {
    const dateObj = parseISODate(dateIso);
    if (!dateObj) return String(dateIso || '');
    return dateObj.toLocaleDateString(undefined, options);
}

function loadLocalPrefs() {
    try {
        const raw = localStorage.getItem(LOCAL_PREFS_KEY);
        if (!raw) return {};
        const parsed = JSON.parse(raw);
        return parsed && typeof parsed === 'object' ? parsed : {};
    } catch (_err) {
        return {};
    }
}

function persistLocalPrefs() {
    const payload = {
        telegramNotify: prefsState.telegramNotify,
        signalNotify: prefsState.signalNotify,
        getReadySound: prefsState.getReadySound,
        soundCooldownSeconds: prefsState.soundCooldownSeconds
    };
    try {
        localStorage.setItem(LOCAL_PREFS_KEY, JSON.stringify(payload));
    } catch (_err) {
        // no-op
    }
}

function loadReadySoundState() {
    try {
        const raw = localStorage.getItem(READY_SOUND_STATE_KEY);
        if (!raw) return { key: '', ts: 0 };
        const parsed = JSON.parse(raw);
        return {
            key: typeof parsed?.key === 'string' ? parsed.key : '',
            ts: Number.isFinite(Number(parsed?.ts)) ? Number(parsed.ts) : 0
        };
    } catch (_err) {
        return { key: '', ts: 0 };
    }
}

function saveReadySoundState(state) {
    try {
        localStorage.setItem(READY_SOUND_STATE_KEY, JSON.stringify(state));
    } catch (_err) {
        // no-op
    }
}

// ============================================================================
// EXPOSE TO WINDOW
// ============================================================================

window.saveAvailabilityPrefs = saveAvailabilityPrefs;
window.createTodayPoll = createTodayPoll;
window.submitAvailabilityResponse = submitAvailabilityResponse;
window.setAvailabilityForDate = setAvailabilityForDate;
window.refreshAvailabilityView = refreshAvailabilityView;
window.selectAvailabilityDate = selectAvailabilityDate;
window.selectUpcomingAvailabilityDate = selectUpcomingAvailabilityDate;
window.toggleAvailabilityCalendar = toggleAvailabilityCalendar;
window.startAvailabilityLinkFlow = startAvailabilityLinkFlow;
window.openAvailabilityPromoteModal = openAvailabilityPromoteModal;
window.closeAvailabilityPromoteModal = closeAvailabilityPromoteModal;
window.confirmAvailabilityPromote = confirmAvailabilityPromote;
window.openAvailabilityPlanningRoom = openAvailabilityPlanningRoom;
window.joinAvailabilityPlanningRoom = joinAvailabilityPlanningRoom;
window.submitAvailabilityPlanningSuggestion = submitAvailabilityPlanningSuggestion;
window.voteAvailabilityPlanningSuggestion = voteAvailabilityPlanningSuggestion;
window.cycleAvailabilityPlanningAssignment = cycleAvailabilityPlanningAssignment;
window.autoDraftAvailabilityPlanningTeams = autoDraftAvailabilityPlanningTeams;
window.saveAvailabilityPlanningTeams = saveAvailabilityPlanningTeams;
window.availabilityPrevMonth = availabilityPrevMonth;
window.availabilityNextMonth = availabilityNextMonth;
window.loadAvailabilityHistory = refreshAvailabilityView;
