/**
 * Availability Module
 * Calendar-first availability UI backed by /api/availability.
 */

import { API_BASE, fetchJSON, escapeHtml, safeInsertHTML } from './utils.js';

const NO_STORE_FETCH = { cachePolicy: 'no-store', credentials: 'same-origin' };

const LOOKBACK_DAYS = 31;
const LOOKAHEAD_DAYS = 90;
const QUICK_DAYS = 14;

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
    isAdmin: false
};

let availabilityByDate = new Map();
let selectedDateIso = toISODate(new Date());
let visibleMonth = startOfMonth(new Date());
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
        isAdmin: false
    };

    try {
        const payload = await fetchJSON(`${API_BASE}/availability/access`, NO_STORE_FETCH);
        accessState.authenticated = Boolean(payload?.authenticated);
        accessState.linkedDiscord = Boolean(payload?.linked_discord);
        accessState.canSubmit = Boolean(payload?.can_submit);
        accessState.isAdmin = Boolean(payload?.is_admin);
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
    renderCalendar();
    renderQuickView();
    renderSelectedDayPanel();
    renderPreferencesSection();
}

function renderLoadingState() {
    const actions = document.getElementById('availability-actions');
    if (actions) {
        replaceWithMarkup(actions, '<div class="text-center py-6 text-slate-500 text-sm">Loading your availability controls...</div>');
    }

    const grid = document.getElementById('availability-calendar-grid');
    if (grid) {
        replaceWithMarkup(grid, '<div class="col-span-7 text-center py-8 text-slate-500 text-sm">Loading calendar...</div>');
    }

    const quick = document.getElementById('availability-quick-view');
    if (quick) {
        replaceWithMarkup(quick, '<div class="text-center py-8 text-slate-500 text-sm">Loading quick view...</div>');
    }
}

function replaceWithMarkup(element, html) {
    if (!element) return;
    element.replaceChildren();
    safeInsertHTML(element, 'beforeend', html);
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
        msg.textContent = '';
        return;
    }

    const copy = accessState.authenticated
        ? 'Aggregate view only. Link your Discord account to a player profile to submit or subscribe.'
        : 'Aggregate view only. Log in with Discord and link your profile to participate.';

    msg.textContent = copy;
    msg.classList.remove('hidden');
    msg.classList.remove('border-brand-rose/40', 'text-brand-rose');
    msg.classList.add('border-brand-amber/40', 'text-brand-amber', 'bg-brand-amber/10');
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

    replaceWithMarkup(container, cards.join(''));
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
                onclick="window.setAvailabilityForDate('${dateIso}', '${statusKey}')"
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
                onclick="window.selectAvailabilityDate('${dateIso}')"
                class="rounded-xl border p-2 text-left transition min-h-[90px] ${toneClass} ${selectedClass} ${todayClass}">
                <div class="flex items-center justify-between">
                    <span class="text-xs font-semibold ${dayClass}">${cellDate.getDate()}</span>
                    <span class="text-[10px] text-slate-400">${entry.total}</span>
                </div>
                <div class="mt-2">${renderStackedBar(entry.counts, entry.total, 'h-1.5')}</div>
            </button>
        `);
    }

    replaceWithMarkup(grid, cells.join(''));
}

function renderQuickView() {
    const container = document.getElementById('availability-quick-view');
    if (!container) return;

    const rows = [];
    for (let i = 0; i < QUICK_DAYS; i += 1) {
        const dayDate = addDays(new Date(), i);
        const dateIso = toISODate(dayDate);
        const entry = getEntry(dateIso);
        const selected = selectedDateIso === dateIso;

        let title = formatDate(dateIso, { weekday: 'short' });
        if (i === 0) title = 'Today';
        if (i === 1) title = 'Tomorrow';

        rows.push(`
            <button
                onclick="window.selectAvailabilityDate('${dateIso}')"
                class="w-full rounded-xl border p-3 text-left transition ${selected ? 'border-brand-cyan/50 bg-brand-cyan/10' : 'border-white/10 bg-slate-950/30 hover:border-brand-cyan/35'}">
                <div class="flex items-center justify-between gap-2 mb-1">
                    <div>
                        <div class="text-xs font-bold text-white">${escapeHtml(title)}</div>
                        <div class="text-[11px] text-slate-500">${escapeHtml(formatDate(dateIso, { month: 'short', day: 'numeric' }))}</div>
                    </div>
                    <div class="text-xs text-slate-300">${entry.total}</div>
                </div>
                ${renderStackedBar(entry.counts, entry.total, 'h-1.5')}
            </button>
        `);
    }

    replaceWithMarkup(container, rows.join(''));
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

    const countsMarkup = STATUS_ORDER.map((statusKey) => {
        const meta = STATUS_META[statusKey];
        const value = entry.counts[statusKey] || 0;
        return `
            <div class="glass-card rounded-lg p-3 text-center border border-white/10">
                <div class="text-xs text-slate-500">${meta.shortLabel}</div>
                <div class="text-2xl font-black ${meta.valueClass}">${value}</div>
            </div>
        `;
    }).join('');
    replaceWithMarkup(countsEl, countsMarkup);

    const selectedDate = parseISODate(selectedDateIso);
    const isPast = selectedDate ? selectedDate < startOfDay(new Date()) : true;
    const canAct = accessState.canSubmit && !isPast && !responseInFlight;

    if (canAct) {
        const actionsMarkup = `
            <div class="text-[11px] text-slate-500 mb-2">Set your status for ${escapeHtml(selectedDateIso)}</div>
            <div class="flex flex-wrap gap-2">
                ${STATUS_ORDER.map((statusKey) => {
                    const meta = STATUS_META[statusKey];
                    const selected = entry.myStatus === statusKey;
                    return `
                        <button
                            onclick="window.setAvailabilityForDate('${selectedDateIso}', '${statusKey}')"
                            class="px-3 py-1.5 rounded-lg text-xs font-bold border transition ${selected ? meta.selectedClass : meta.idleClass}">
                            ${meta.emoji} ${meta.shortLabel}
                        </button>
                    `;
                }).join('')}
            </div>
        `;
        replaceWithMarkup(actionsEl, actionsMarkup);
    } else if (isPast) {
        replaceWithMarkup(actionsEl, '<div class="text-[11px] text-slate-500">Past days are read-only.</div>');
    } else if (!accessState.canSubmit) {
        replaceWithMarkup(actionsEl, '<div class="text-[11px] text-brand-amber">Log in and link Discord to set availability.</div>');
    } else {
        replaceWithMarkup(actionsEl, '<div class="text-[11px] text-slate-500">Saving in progress...</div>');
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
    replaceWithMarkup(notesEl, notes.join(''));
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
            headers: { 'Content-Type': 'application/json' },
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
            headers: { 'Content-Type': 'application/json' },
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

            gain.gain.setValueAtTime(Number.parseFloat('0.0001'), toneStart);
            gain.gain.exponentialRampToValueAtTime(0.16, toneStart + 0.02);
            gain.gain.exponentialRampToValueAtTime(Number.parseFloat('0.0001'), toneStart + 0.11);

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

function ensureRefreshTimer() {
    if (refreshTimer) return;

    refreshTimer = window.setInterval(() => {
        if (!isAvailabilityViewActive()) return;
        void refreshAvailabilityView();
    }, POLL_INTERVAL_MS);
}

function ensureRuntimeListeners() {
    if (runtimeListenersBound) return;

    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible' && isAvailabilityViewActive()) {
            maybePlayGetReadySound();
        }
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

function availabilityPrevMonth() {
    visibleMonth = new Date(visibleMonth.getFullYear(), visibleMonth.getMonth() - 1, 1);
    renderCalendar();
}

function availabilityNextMonth() {
    visibleMonth = new Date(visibleMonth.getFullYear(), visibleMonth.getMonth() + 1, 1);
    renderCalendar();
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
window.availabilityPrevMonth = availabilityPrevMonth;
window.availabilityNextMonth = availabilityNextMonth;
window.loadAvailabilityHistory = refreshAvailabilityView;
