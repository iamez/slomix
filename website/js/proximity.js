/**
 * Proximity analytics module (prototype)
 * @module proximity
 */

import { API_BASE, fetchJSON, formatNumber, escapeHtml } from './utils.js';

const DEFAULT_RANGE_DAYS = 30;
const DEFAULT_EVENTS_LIMIT = 20;
const DEFAULT_SCOPE_RANGE_DAYS = 365;
const MAP_TRANSFORM_CONFIG_URL = '/assets/maps/proximity/map_transforms.json';
const OBJECTIVE_ZONES_CONFIG_URL = '/assets/maps/proximity/objective_zones.json';
const PROXIMITY_GRID_SIZE = 512;

const proximityScopeState = {
    sessions: [],
    sessionDate: null,
    mapName: null,
    roundNumber: null,
    roundStartUnix: null,
};

const proximityVizState = {
    showObjectiveZones: true,
    heatIntensity: 1.0,
    teamEmphasis: 'auto',
};

const proximityRenderCache = {
    heatmapPayload: null,
    eventPayload: null,
};

let proximityViewLoadPromise = null;
let proximityScopedLoadId = 0;
let mapTransformConfigPromise = null;
let mapTransformConfig = null;
let objectiveZonesConfigPromise = null;
let objectiveZonesConfig = null;
const mapImageCache = new Map();

const TEAM_COLORS = {
    AXIS: 'rgba(239, 68, 68, 0.9)',
    ALLIES: 'rgba(59, 130, 246, 0.9)',
};

function normalizeTeamName(team) {
    const normalized = String(team || '').trim().toUpperCase();
    if (!normalized) return null;
    if (normalized === 'AXIS' || normalized === '1' || normalized === 'RED') return 'AXIS';
    if (normalized === 'ALLIES' || normalized === '2' || normalized === 'BLUE') return 'ALLIES';
    return normalized;
}

function getOpposingTeam(team) {
    const normalized = normalizeTeamName(team);
    if (normalized === 'AXIS') return 'ALLIES';
    if (normalized === 'ALLIES') return 'AXIS';
    return null;
}

function normalizeMapKey(mapName) {
    return stripEtColors(mapName || '').trim().toLowerCase();
}

function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
}

function withAlpha(color, alpha) {
    if (typeof color !== 'string') return color;
    const value = clamp(Number(alpha), 0, 1);
    const rgbaMatch = color.match(/^rgba\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*\)$/i);
    if (rgbaMatch) {
        return `rgba(${rgbaMatch[1]}, ${rgbaMatch[2]}, ${rgbaMatch[3]}, ${value})`;
    }
    const rgbMatch = color.match(/^rgb\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*\)$/i);
    if (rgbMatch) {
        return `rgba(${rgbMatch[1]}, ${rgbMatch[2]}, ${rgbMatch[3]}, ${value})`;
    }
    return color;
}

async function ensureMapTransformConfig() {
    if (mapTransformConfig) return mapTransformConfig;
    if (!mapTransformConfigPromise) {
        mapTransformConfigPromise = fetch(MAP_TRANSFORM_CONFIG_URL)
            .then((res) => (res.ok ? res.json() : null))
            .catch(() => null);
    }
    mapTransformConfig = await mapTransformConfigPromise;
    return mapTransformConfig;
}

async function ensureObjectiveZonesConfig() {
    if (objectiveZonesConfig) return objectiveZonesConfig;
    if (!objectiveZonesConfigPromise) {
        objectiveZonesConfigPromise = fetch(OBJECTIVE_ZONES_CONFIG_URL)
            .then((res) => (res.ok ? res.json() : null))
            .catch(() => null);
    }
    objectiveZonesConfig = await objectiveZonesConfigPromise;
    return objectiveZonesConfig;
}

function getMapTransformEntry(mapName) {
    if (!mapTransformConfig || !mapTransformConfig.maps) return null;
    const key = normalizeMapKey(mapName);
    return mapTransformConfig.maps[key] || mapTransformConfig.maps[mapName] || null;
}

function getObjectiveZonesForMap(mapName) {
    if (!objectiveZonesConfig || !objectiveZonesConfig.maps) return [];
    const key = normalizeMapKey(mapName);
    const entry = objectiveZonesConfig.maps[key] || objectiveZonesConfig.maps[mapName] || null;
    if (!entry || !Array.isArray(entry.objectives)) return [];
    return entry.objectives;
}

function getTeamColor(team, fallback = 'rgba(56, 189, 248, 0.85)') {
    const normalized = normalizeTeamName(team);
    return TEAM_COLORS[normalized] || fallback;
}

async function preloadMapImage(imagePath) {
    if (!imagePath) return null;
    if (mapImageCache.has(imagePath)) {
        return mapImageCache.get(imagePath);
    }
    const promise = new Promise((resolve) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = () => resolve(null);
        img.src = imagePath;
    });
    mapImageCache.set(imagePath, promise);
    return promise;
}

function formatDateLabel(value) {
    if (!value) return '--';
    const date = new Date(`${value}T00:00:00`);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function getSelectedSession() {
    if (!proximityScopeState.sessionDate) return null;
    return proximityScopeState.sessions.find((s) => s.session_date === proximityScopeState.sessionDate) || null;
}

function getSelectedMap() {
    const session = getSelectedSession();
    if (!session || !proximityScopeState.mapName) return null;
    return (session.maps || []).find((m) => m.map_name === proximityScopeState.mapName) || null;
}

function getScopeDescription() {
    const parts = [];
    if (proximityScopeState.sessionDate) {
        parts.push(`Session ${formatDateLabel(proximityScopeState.sessionDate)}`);
    }
    if (proximityScopeState.mapName) {
        parts.push(`Map ${stripEtColors(proximityScopeState.mapName)}`);
    }
    if (proximityScopeState.roundNumber != null) {
        parts.push(`Round ${proximityScopeState.roundNumber}`);
    }
    if (parts.length === 0) {
        return `Last ${DEFAULT_RANGE_DAYS}d window`;
    }
    return parts.join(' • ');
}

function buildScopeParams({ includeRange = true, extra = {} } = {}) {
    const params = new URLSearchParams();
    if (includeRange) params.set('range_days', String(DEFAULT_RANGE_DAYS));
    if (proximityScopeState.sessionDate) params.set('session_date', proximityScopeState.sessionDate);
    if (proximityScopeState.mapName) params.set('map_name', proximityScopeState.mapName);
    if (proximityScopeState.roundNumber != null) params.set('round_number', String(proximityScopeState.roundNumber));
    if (proximityScopeState.roundStartUnix != null) params.set('round_start_unix', String(proximityScopeState.roundStartUnix));
    Object.entries(extra).forEach(([key, value]) => {
        if (value != null && value !== '') params.set(key, String(value));
    });
    return params;
}

function scopedUrl(path, options = {}) {
    const params = buildScopeParams(options);
    return `${API_BASE}${path}?${params.toString()}`;
}

function setSelectOptions(selectEl, options, selectedValue = '') {
    if (!selectEl) return;
    selectEl.innerHTML = '';
    options.forEach((opt) => {
        const optionEl = new Option(opt.label, opt.value);
        if (String(opt.value) === String(selectedValue ?? '')) optionEl.selected = true;
        selectEl.add(optionEl);
    });
}

function ensureValidScopeSelection() {
    const sessionExists = proximityScopeState.sessions.some((s) => s.session_date === proximityScopeState.sessionDate);
    if (!sessionExists) {
        proximityScopeState.sessionDate = proximityScopeState.sessions[0]?.session_date || null;
        proximityScopeState.mapName = null;
        proximityScopeState.roundNumber = null;
        proximityScopeState.roundStartUnix = null;
    }

    const selectedSession = getSelectedSession();
    const maps = selectedSession?.maps || [];
    if (!proximityScopeState.mapName || !maps.some((m) => m.map_name === proximityScopeState.mapName)) {
        proximityScopeState.mapName = null;
        proximityScopeState.roundNumber = null;
        proximityScopeState.roundStartUnix = null;
    }

    const selectedMap = getSelectedMap();
    const rounds = selectedMap?.rounds || [];
    const roundExists = rounds.some((r) => (
        Number(r.round_number) === Number(proximityScopeState.roundNumber)
        && Number(r.round_start_unix || 0) === Number(proximityScopeState.roundStartUnix || 0)
    ));
    if (!roundExists) {
        proximityScopeState.roundNumber = null;
        proximityScopeState.roundStartUnix = null;
    }
}

function updateScopeUIText() {
    const scope = getScopeDescription();
    setText('proximity-scope-caption', scope);
    setText('proximity-window-label', scope);
    setText('proximity-timeline-scope', `Scope: ${scope}`);
    setText('proximity-heatmap-scope', `Scope: ${scope}`);
}

function renderScopeSelectors() {
    const sessionSelect = document.getElementById('proximity-session-select');
    const mapSelect = document.getElementById('proximity-map-select');
    const roundSelect = document.getElementById('proximity-round-select');

    ensureValidScopeSelection();

    const sessionOptions = proximityScopeState.sessions.length
        ? proximityScopeState.sessions.map((session) => ({
            value: session.session_date,
            label: `${formatDateLabel(session.session_date)} (${formatNumber(session.engagements || 0)} ev)`,
        }))
        : [{ value: '', label: 'No sessions available' }];
    setSelectOptions(sessionSelect, sessionOptions, proximityScopeState.sessionDate || '');

    const selectedSession = getSelectedSession();
    const mapOptions = [{ value: '', label: 'All maps' }];
    if (selectedSession) {
        (selectedSession.maps || []).forEach((map) => {
            mapOptions.push({
                value: map.map_name,
                label: `${stripEtColors(map.map_name)} (${formatNumber(map.engagements || 0)} ev)`,
            });
        });
    }
    setSelectOptions(mapSelect, mapOptions, proximityScopeState.mapName || '');

    const selectedMap = getSelectedMap();
    const roundOptions = [{ value: '', label: 'All rounds' }];
    if (selectedMap) {
        (selectedMap.rounds || []).forEach((round) => {
            let start = '';
            if (round.round_start_unix) {
                const stamp = new Date(Number(round.round_start_unix) * 1000);
                if (!Number.isNaN(stamp.getTime())) {
                    start = ` • ${stamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
                }
            }
            roundOptions.push({
                value: `${round.round_number}|${round.round_start_unix || 0}`,
                label: `R${round.round_number}${start} (${formatNumber(round.engagements || 0)} ev)`,
            });
        });
    }
    const selectedRoundValue = proximityScopeState.roundNumber != null
        ? `${proximityScopeState.roundNumber}|${proximityScopeState.roundStartUnix || 0}`
        : '';
    setSelectOptions(roundSelect, roundOptions, selectedRoundValue);

    if (sessionSelect) sessionSelect.disabled = proximityScopeState.sessions.length === 0;
    if (mapSelect) mapSelect.disabled = !selectedSession;
    if (roundSelect) roundSelect.disabled = !selectedMap;

    updateScopeUIText();
}

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function setHtml(id, value) {
    const el = document.getElementById(id);
    if (el) el.innerHTML = value;
}

function stripEtColors(text) {
    if (!text) return '';
    return String(text).replace(/\^[0-9A-Za-z]/g, '');
}

function formatMs(ms) {
    if (ms == null) return '--';
    const value = Number(ms);
    if (!Number.isFinite(value)) return '--';
    if (value >= 1000) return `${(value / 1000).toFixed(1)}s`;
    return `${Math.round(value)}ms`;
}

function formatDurationMs(ms) {
    if (ms == null) return '--';
    const value = Number(ms);
    if (!Number.isFinite(value)) return '--';
    const totalSeconds = Math.max(0, Math.round(value / 1000));
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    if (mins <= 0) return `${secs}s`;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function extractSampleCount(row) {
    if (!row || typeof row !== 'object') return null;
    const candidates = [
        row.sample_count,
        row.samples,
        row.tracks,
        row.crossfire_participations,
        row.crossfire_count,
        row.times_focused,
        row.events,
    ];
    for (const value of candidates) {
        const num = Number(value);
        if (Number.isFinite(num) && num > 0) return Math.round(num);
    }
    return null;
}

function getConfidenceFromSamples(sampleCount) {
    const count = Number(sampleCount);
    if (!Number.isFinite(count) || count <= 0) return null;
    if (count >= 20) return 'High';
    if (count >= 8) return 'Medium';
    return 'Low';
}

function renderLeaderList(containerId, rows, formatter, emptyLabel = 'No data yet') {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!rows || rows.length === 0) {
        container.innerHTML = `<div class="text-[11px] text-slate-500">${escapeHtml(emptyLabel)}</div>`;
        return;
    }

    container.innerHTML = rows.map((row, idx) => {
        const label = stripEtColors(row.name || row.player || `Player ${idx + 1}`);
        const value = formatter(row);
        const sampleCount = extractSampleCount(row);
        const confidence = getConfidenceFromSamples(sampleCount);
        const sampleMeta = sampleCount
            ? `n=${formatNumber(sampleCount)} • ${confidence || 'Low'}`
            : '';
        return `
            <div class="flex items-center justify-between text-[11px] text-slate-300">
                <span>${escapeHtml(label)}</span>
                <span class="text-right">
                    <span class="text-slate-500">${escapeHtml(value)}</span>
                    ${sampleMeta ? `<span class="block text-[10px] text-slate-600">${escapeHtml(sampleMeta)}</span>` : ''}
                </span>
            </div>
        `;
    }).join('');
}

function renderTradeSummary(summary) {
    if (!summary) return;
    const opportunities = summary.trade_opportunities ?? summary.opportunities ?? null;
    const attempts = summary.trade_attempts ?? summary.attempts ?? null;
    const success = summary.trade_success ?? summary.success ?? null;
    const missed = summary.missed_trade_candidates ?? summary.missed ?? null;
    const support = summary.support_uptime_pct ?? summary.support_uptime ?? null;
    const isolation = summary.isolation_deaths ?? summary.isolated_deaths ?? null;

    setText('proximity-trade-opportunities', opportunities != null ? formatNumber(opportunities) : '--');
    setText('proximity-trade-attempts', attempts != null ? formatNumber(attempts) : '--');
    setText('proximity-trade-success', success != null ? formatNumber(success) : '--');
    setText('proximity-trade-missed', missed != null ? formatNumber(missed) : '--');
    const supportValue = Number(support);
    setText('proximity-support-uptime', Number.isFinite(supportValue) ? `${supportValue.toFixed(1)}%` : '--');
    setText('proximity-isolation-deaths', isolation != null ? formatNumber(isolation) : '--');

    const oppValue = Number(opportunities);
    const attemptsValue = Number(attempts);
    const successValue = Number(success);
    const missedValue = Number(missed);
    const hasOpps = Number.isFinite(oppValue) && oppValue > 0;
    const attemptRate = hasOpps && Number.isFinite(attemptsValue) ? `${((attemptsValue / oppValue) * 100).toFixed(1)}%` : '--';
    const conversionRate = hasOpps && Number.isFinite(successValue) ? `${((successValue / oppValue) * 100).toFixed(1)}%` : '--';
    const missRate = hasOpps && Number.isFinite(missedValue) ? `${((missedValue / oppValue) * 100).toFixed(1)}%` : '--';
    setText('proximity-trade-attempt-rate', attemptRate);
    setText('proximity-trade-conversion-rate', conversionRate);
    setText('proximity-trade-miss-rate', missRate);
}

function renderTradeEvents(events) {
    const container = document.getElementById('proximity-trade-events');
    if (!container) return;
    if (!events || events.length === 0) {
        container.innerHTML = `<div class="text-xs text-slate-600">No trade events yet.</div>`;
        return;
    }
    container.innerHTML = events.map((e) => {
        const map = stripEtColors(e.map || 'unknown');
        const victim = stripEtColors(e.victim || e.victim_name || 'unknown');
        const killer = stripEtColors(e.killer || e.killer_name || 'unknown');
        const outcome = e.outcome || 'trade';
        const round = e.round != null ? `R${e.round}` : 'R?';
        const date = e.round_date || e.date || '';
        const time = e.round_time || e.time || '';
        const roundButton = e.round_id != null
            ? `<button class="text-[10px] text-brand-cyan hover:text-white" data-round-id="${e.round_id}">View round</button>`
            : '';
        return `
            <div class="glass-card p-3 rounded-lg border border-white/5">
                <div class="flex items-center justify-between text-[10px] text-slate-500">
                    <span>${escapeHtml(map)} • ${escapeHtml(round)} • ${escapeHtml(date)} ${escapeHtml(time)}</span>
                    ${roundButton}
                </div>
                <div class="text-sm font-semibold text-white mt-1">${escapeHtml(victim)} → ${escapeHtml(killer)}</div>
                <div class="text-[10px] text-slate-400 mt-1">${escapeHtml(outcome)}</div>
            </div>
        `;
    }).join('');

    container.querySelectorAll('[data-round-id]').forEach((btn) => {
        btn.addEventListener('click', (event) => {
            event.stopPropagation();
            const roundId = btn.getAttribute('data-round-id');
            if (!roundId || typeof window.loadMatchDetails !== 'function') return;
            window.loadMatchDetails(parseInt(roundId, 10));
        });
    });
}

function renderDuos(duos) {
    const container = document.getElementById('proximity-top-duos');
    if (!container) return;

    if (!duos || duos.length === 0) {
        container.innerHTML = `
            <div class="glass-card p-4 rounded-lg text-center">
                <div class="text-sm font-bold text-white">--</div>
                <div class="text-xs text-slate-500 mt-1">No data yet</div>
            </div>
            <div class="glass-card p-4 rounded-lg text-center">
                <div class="text-sm font-bold text-white">--</div>
                <div class="text-xs text-slate-500 mt-1">No data yet</div>
            </div>
            <div class="glass-card p-4 rounded-lg text-center">
                <div class="text-sm font-bold text-white">--</div>
                <div class="text-xs text-slate-500 mt-1">No data yet</div>
            </div>
        `;
        return;
    }

    container.innerHTML = duos.slice(0, 6).map((duo, idx) => {
        const player1 = stripEtColors(duo.player1 || '');
        const player2 = stripEtColors(duo.player2 || '');
        const players = player1 && player2 ? `${player1} + ${player2}` : (duo.label || `Duo ${idx + 1}`);
        const kills = duo.crossfire_kills != null ? formatNumber(duo.crossfire_kills) : '--';
        const count = duo.crossfire_count != null ? formatNumber(duo.crossfire_count) : '--';
        const sampleCount = extractSampleCount(duo);
        const confidence = getConfidenceFromSamples(sampleCount);
        const delay = duo.avg_delay_ms != null ? `${duo.avg_delay_ms.toFixed(0)}ms` : '--';
        const detail = `Kills ${kills} • Crossfires ${count} • Δ ${delay}`;
        const confidenceMeta = sampleCount ? `n=${formatNumber(sampleCount)} • ${confidence || 'Low'}` : '';
        return `
            <div class="glass-card p-4 rounded-lg text-center">
                <div class="text-sm font-bold text-white">${escapeHtml(players)}</div>
                <div class="text-[10px] text-slate-500 mt-2">${detail}</div>
                ${confidenceMeta ? `<div class="text-[10px] text-slate-600 mt-1">${escapeHtml(confidenceMeta)}</div>` : ''}
            </div>
        `;
    }).join('');
}

function renderTimeline(buckets) {
    const container = document.getElementById('proximity-timeline');
    if (!container) return;

    if (!buckets || buckets.length === 0) {
        container.innerHTML = `
            <div class="h-full w-full flex items-center justify-center text-slate-500">
                <div class="text-center">
                    <i data-lucide="activity" class="w-8 h-8 mx-auto mb-2 text-slate-600"></i>
                    <div class="text-sm font-bold text-slate-400">Timeline offline</div>
                    <div class="text-xs text-slate-600">Awaiting proximity events stream</div>
                </div>
            </div>
        `;
        return;
    }

    const max = Math.max(...buckets.map(b => b.engagements || 0), 1);
    container.innerHTML = buckets.map((b) => {
        const height = Math.max(6, Math.round((b.engagements / max) * 120));
        const label = b.date?.slice(5) || '';
        return `
            <div class="flex-1 flex flex-col items-center justify-end gap-1">
                <div class="w-full rounded bg-brand-cyan/40" style="height:${height}px"></div>
                <div class="text-[10px] text-slate-500">${escapeHtml(label)}</div>
            </div>
        `;
    }).join('');
}

function getWorldBounds(mapTransform) {
    const boundsMins = Array.isArray(mapTransform?.mapcoordsmins) ? mapTransform.mapcoordsmins : null;
    const boundsMaxs = Array.isArray(mapTransform?.mapcoordsmaxs) ? mapTransform.mapcoordsmaxs : null;
    const valid = boundsMins && boundsMaxs
        && Number.isFinite(boundsMins[0]) && Number.isFinite(boundsMins[1])
        && Number.isFinite(boundsMaxs[0]) && Number.isFinite(boundsMaxs[1])
        && Math.abs(boundsMaxs[0] - boundsMins[0]) > 0.0001
        && Math.abs(boundsMins[1] - boundsMaxs[1]) > 0.0001;
    if (!valid) return null;
    return { mins: boundsMins, maxs: boundsMaxs };
}

function worldToCanvasPoint(x, y, width, height, worldBounds) {
    if (!worldBounds) return null;
    const { mins, maxs } = worldBounds;
    const u = (x - mins[0]) / (maxs[0] - mins[0]);
    const v = (mins[1] - y) / (mins[1] - maxs[1]);
    return {
        x: clamp(u, 0, 1) * width,
        y: clamp(v, 0, 1) * height,
    };
}

function worldRadiusToCanvas(radius, width, height, worldBounds) {
    if (!worldBounds || !Number.isFinite(radius)) return 0;
    const { mins, maxs } = worldBounds;
    const pxPerUnitX = width / Math.max(Math.abs(maxs[0] - mins[0]), 1);
    const pxPerUnitY = height / Math.max(Math.abs(mins[1] - maxs[1]), 1);
    return Math.max(2, radius * ((pxPerUnitX + pxPerUnitY) / 2));
}

function getObjectiveTypeColor(type) {
    const normalized = String(type || '').toLowerCase();
    if (normalized === 'escort') return 'rgba(251, 146, 60, 0.5)';
    if (normalized === 'command_post') return 'rgba(96, 165, 250, 0.5)';
    return 'rgba(110, 231, 183, 0.42)';
}

function shouldRenderObjectiveZone(objective) {
    const type = String(objective?.type || '').toLowerCase();
    const name = String(objective?.name || '').toLowerCase();
    const luaName = String(objective?.lua_name || '').toLowerCase();
    const target = String(objective?.target || '').toLowerCase();
    const haystack = `${name} ${luaName} ${target}`;

    if (type === 'command_post' || type === 'escort') return true;
    if (haystack.includes('barrier')) return true;

    const hasMgToken = /\bmg\b/.test(haystack) || luaName.includes('_mg') || target.includes('mg42') || target.includes('weaponclip');
    if (hasMgToken) return false;
    if (haystack.includes('cabinet') || haystack.includes('healammo') || haystack.includes('health_and_ammo')) return false;
    if (haystack.includes('controls') || haystack.includes('control') || haystack.includes('utility')) return false;

    return true;
}

function getObjectiveStateColor(state) {
    if (state === 'contested') return 'rgba(248, 113, 113, 0.34)';
    if (state === 'core') return 'rgba(34, 197, 94, 0.30)';
    if (state === 'approach') return 'rgba(250, 204, 21, 0.26)';
    return 'rgba(148, 163, 184, 0.2)';
}

function classifyObjectiveZoneState(metrics) {
    if ((metrics.contestedCount || 0) > 0) return 'contested';
    if ((metrics.targetCoreHits || 0) + (metrics.attackerCoreHits || 0) > 0) return 'core';
    if ((metrics.targetApproachHits || 0) + (metrics.attackerApproachHits || 0) > 0) return 'approach';
    return 'outside';
}

function isInsideObjectiveRadius(sample, objective, radius) {
    if (!sample || !objective) return false;
    const sx = Number(sample.x);
    const sy = Number(sample.y);
    const ox = Number(objective.x);
    const oy = Number(objective.y);
    if (![sx, sy, ox, oy, radius].every(Number.isFinite)) return false;
    const dx = sx - ox;
    const dy = sy - oy;
    return Math.sqrt(dx * dx + dy * dy) <= radius;
}

function computeObjectiveZoneStates(targetPath, attackerPath, objectiveZones = []) {
    const target = (Array.isArray(targetPath) ? targetPath : []).filter((p) => Number.isFinite(Number(p?.x)) && Number.isFinite(Number(p?.y)));
    const attacker = (Array.isArray(attackerPath) ? attackerPath : []).filter((p) => Number.isFinite(Number(p?.x)) && Number.isFinite(Number(p?.y)));
    if (!objectiveZones.length) return [];

    const states = [];
    for (const objective of objectiveZones) {
        const baseRadius = Number(objective?.radius || 500);
        if (!Number.isFinite(baseRadius) || baseRadius <= 0) continue;
        const coreRadius = baseRadius * 0.55;
        const approachRadius = baseRadius * 1.2;
        const inZoneRadius = baseRadius;

        const metrics = {
            targetCoreHits: 0,
            targetApproachHits: 0,
            attackerCoreHits: 0,
            attackerApproachHits: 0,
            contestedCount: 0,
        };

        const targetInZone = [];
        const attackerInZone = [];

        for (const sample of target) {
            if (isInsideObjectiveRadius(sample, objective, approachRadius)) metrics.targetApproachHits += 1;
            if (isInsideObjectiveRadius(sample, objective, coreRadius)) metrics.targetCoreHits += 1;
            if (isInsideObjectiveRadius(sample, objective, inZoneRadius)) {
                const sampleTime = Number(sample.time);
                if (Number.isFinite(sampleTime)) targetInZone.push(sampleTime);
            }
        }
        for (const sample of attacker) {
            if (isInsideObjectiveRadius(sample, objective, approachRadius)) metrics.attackerApproachHits += 1;
            if (isInsideObjectiveRadius(sample, objective, coreRadius)) metrics.attackerCoreHits += 1;
            if (isInsideObjectiveRadius(sample, objective, inZoneRadius)) {
                const sampleTime = Number(sample.time);
                if (Number.isFinite(sampleTime)) attackerInZone.push(sampleTime);
            }
        }

        if (targetInZone.length && attackerInZone.length) {
            for (const targetTime of targetInZone) {
                if (attackerInZone.some((attackerTime) => Math.abs(attackerTime - targetTime) <= 1200)) {
                    metrics.contestedCount += 1;
                    break;
                }
            }
        }

        const state = classifyObjectiveZoneState(metrics);
        states.push({
            id: objective.id || objective.lua_name || objective.name || `objective-${states.length}`,
            name: objective.name || objective.lua_name || 'Objective',
            state,
            ...metrics,
        });
    }
    return states;
}

function renderObjectiveStateSummary(states = [], targetTeam = null, attackerTeam = null) {
    const container = document.getElementById('proximity-objective-state-summary');
    if (!container) return;
    if (!Array.isArray(states) || states.length === 0) {
        container.innerHTML = '<div class="text-[10px] text-slate-500">Objective state: no zones available on this map.</div>';
        return;
    }

    const severityOrder = { contested: 0, core: 1, approach: 2, outside: 3 };
    const sorted = states.slice().sort((a, b) => {
        const sa = severityOrder[a.state] ?? 4;
        const sb = severityOrder[b.state] ?? 4;
        if (sa !== sb) return sa - sb;
        const ah = (a.targetCoreHits || 0) + (a.attackerCoreHits || 0) + (a.targetApproachHits || 0) + (a.attackerApproachHits || 0);
        const bh = (b.targetCoreHits || 0) + (b.attackerCoreHits || 0) + (b.targetApproachHits || 0) + (b.attackerApproachHits || 0);
        return bh - ah;
    });

    container.innerHTML = sorted.slice(0, 8).map((row) => {
        const badgeColor = row.state === 'contested'
            ? 'bg-rose-500/20 text-rose-300 border-rose-400/30'
            : row.state === 'core'
                ? 'bg-emerald-500/20 text-emerald-300 border-emerald-400/30'
                : row.state === 'approach'
                    ? 'bg-amber-500/20 text-amber-300 border-amber-400/30'
                    : 'bg-slate-500/20 text-slate-300 border-slate-400/30';
        const targetLabel = normalizeTeamName(targetTeam) || 'Target';
        const attackerLabel = normalizeTeamName(attackerTeam) || 'Attacker';
        return `
            <div class="inline-flex items-center gap-2 mr-2 mb-2 px-2 py-1 rounded border border-white/10 bg-white/5">
                <span class="font-semibold text-slate-200">${escapeHtml(stripEtColors(row.name))}</span>
                <span class="px-1.5 py-0.5 rounded border ${badgeColor} uppercase tracking-wide">${escapeHtml(row.state)}</span>
                <span class="text-slate-400">${escapeHtml(targetLabel)} core:${formatNumber(row.targetCoreHits || 0)}</span>
                <span class="text-slate-500">${escapeHtml(attackerLabel)} core:${formatNumber(row.attackerCoreHits || 0)}</span>
            </div>
        `;
    }).join('');
}

function getObjectiveTimelineStateClass(state) {
    if (state === 'contested') return 'bg-rose-400/90';
    if (state === 'core') return 'bg-emerald-400/80';
    if (state === 'approach') return 'bg-amber-300/80';
    return 'bg-slate-700/50';
}

function formatTimelineSeconds(ms) {
    const value = Number(ms);
    if (!Number.isFinite(value)) return '--';
    return `${(value / 1000).toFixed(1)}s`;
}

function computeObjectiveTimelineRows(targetPath, attackerPath, objectiveZones = [], objectiveStates = [], binCount = 24) {
    const target = (Array.isArray(targetPath) ? targetPath : []).filter((p) => (
        Number.isFinite(Number(p?.x)) && Number.isFinite(Number(p?.y)) && Number.isFinite(Number(p?.time))
    ));
    const attacker = (Array.isArray(attackerPath) ? attackerPath : []).filter((p) => (
        Number.isFinite(Number(p?.x)) && Number.isFinite(Number(p?.y)) && Number.isFinite(Number(p?.time))
    ));
    const allTimes = target.map((s) => Number(s.time)).concat(attacker.map((s) => Number(s.time)));
    if (!objectiveZones.length || !allTimes.length) return null;

    const stateRank = { contested: 0, core: 1, approach: 2, outside: 3 };
    const objectiveById = objectiveZones.reduce((acc, objective) => {
        const id = objective.id || objective.lua_name || objective.name || '';
        if (id) acc[id] = objective;
        return acc;
    }, {});

    const prioritized = (Array.isArray(objectiveStates) ? objectiveStates : [])
        .slice()
        .sort((a, b) => {
            const ar = stateRank[a.state] ?? 4;
            const br = stateRank[b.state] ?? 4;
            if (ar !== br) return ar - br;
            const ah = (a.targetCoreHits || 0) + (a.attackerCoreHits || 0) + (a.targetApproachHits || 0) + (a.attackerApproachHits || 0);
            const bh = (b.targetCoreHits || 0) + (b.attackerCoreHits || 0) + (b.targetApproachHits || 0) + (b.attackerApproachHits || 0);
            return bh - ah;
        })
        .filter((row) => objectiveById[row.id]);

    const selected = prioritized.slice(0, 4);
    if (!selected.length) return null;

    const minTime = Math.min(...allTimes);
    const maxTime = Math.max(...allTimes);
    const span = Math.max(maxTime - minTime, 1);
    const safeBins = Math.max(8, Math.min(40, Number(binCount) || 24));
    const binSize = span / safeBins;

    const rows = selected.map((row) => {
        const objective = objectiveById[row.id];
        const baseRadius = Number(objective?.radius || 500);
        const coreRadius = baseRadius * 0.55;
        const approachRadius = baseRadius * 1.2;
        const inZoneRadius = baseRadius;
        const bins = [];

        for (let idx = 0; idx < safeBins; idx += 1) {
            const start = minTime + idx * binSize;
            const end = idx === safeBins - 1 ? (maxTime + 1) : (start + binSize);
            let targetInApproach = false;
            let attackerInApproach = false;
            let targetInCore = false;
            let attackerInCore = false;
            let targetInZone = false;
            let attackerInZone = false;

            for (const sample of target) {
                const t = Number(sample.time);
                if (t < start || t >= end) continue;
                if (isInsideObjectiveRadius(sample, objective, approachRadius)) targetInApproach = true;
                if (isInsideObjectiveRadius(sample, objective, coreRadius)) targetInCore = true;
                if (isInsideObjectiveRadius(sample, objective, inZoneRadius)) targetInZone = true;
            }
            for (const sample of attacker) {
                const t = Number(sample.time);
                if (t < start || t >= end) continue;
                if (isInsideObjectiveRadius(sample, objective, approachRadius)) attackerInApproach = true;
                if (isInsideObjectiveRadius(sample, objective, coreRadius)) attackerInCore = true;
                if (isInsideObjectiveRadius(sample, objective, inZoneRadius)) attackerInZone = true;
            }

            let state = 'outside';
            if (targetInZone && attackerInZone) state = 'contested';
            else if (targetInCore || attackerInCore) state = 'core';
            else if (targetInApproach || attackerInApproach) state = 'approach';

            bins.push({
                state,
                start,
                end,
            });
        }

        return {
            id: row.id,
            name: row.name,
            bins,
        };
    });

    return {
        minTime,
        maxTime,
        rows,
        binCount: safeBins,
    };
}

function renderObjectiveTimelineStrip(timeline, targetTeam = null, attackerTeam = null) {
    const container = document.getElementById('proximity-objective-timeline');
    if (!container) return;
    if (!timeline || !Array.isArray(timeline.rows) || timeline.rows.length === 0) {
        container.innerHTML = '<div class="text-[10px] text-slate-500">Objective timeline: no timestamped path data.</div>';
        return;
    }

    const targetLabel = normalizeTeamName(targetTeam) || 'Target';
    const attackerLabel = normalizeTeamName(attackerTeam) || 'Attacker';
    const durationMs = Math.max(Number(timeline.maxTime) - Number(timeline.minTime), 0);

    const rowsHtml = timeline.rows.map((row) => {
        const segments = row.bins.map((segment) => (
            `<span class="h-2.5 rounded-sm ${getObjectiveTimelineStateClass(segment.state)} flex-1" title="${escapeHtml(segment.state)} • ${formatTimelineSeconds(segment.start - timeline.minTime)}-${formatTimelineSeconds(segment.end - timeline.minTime)}"></span>`
        )).join('');
        return `
            <div class="grid grid-cols-[120px_1fr] gap-2 items-center mt-1">
                <div class="text-slate-300 truncate" title="${escapeHtml(stripEtColors(row.name || 'Objective'))}">${escapeHtml(stripEtColors(row.name || 'Objective'))}</div>
                <div class="flex gap-0.5">${segments}</div>
            </div>
        `;
    }).join('');

    container.innerHTML = `
        <div class="text-[10px] text-slate-500 mb-1">Objective timeline (${formatTimelineSeconds(durationMs)}) • ${escapeHtml(targetLabel)} vs ${escapeHtml(attackerLabel)}</div>
        <div class="flex items-center gap-3 mb-1 text-[10px] text-slate-500">
            <span class="inline-flex items-center gap-1"><span class="w-2.5 h-2.5 rounded-sm bg-slate-700/50"></span>outside</span>
            <span class="inline-flex items-center gap-1"><span class="w-2.5 h-2.5 rounded-sm bg-amber-300/80"></span>approach</span>
            <span class="inline-flex items-center gap-1"><span class="w-2.5 h-2.5 rounded-sm bg-emerald-400/80"></span>core</span>
            <span class="inline-flex items-center gap-1"><span class="w-2.5 h-2.5 rounded-sm bg-rose-400/90"></span>contested</span>
        </div>
        ${rowsHtml}
    `;
}

function drawObjectiveZones(ctx, width, height, worldBounds, objectiveZones = [], stateByObjective = null) {
    if (!worldBounds || !Array.isArray(objectiveZones) || objectiveZones.length === 0) return;
    for (const objective of objectiveZones) {
        if (!Number.isFinite(objective?.x) || !Number.isFinite(objective?.y)) continue;
        const point = worldToCanvasPoint(objective.x, objective.y, width, height, worldBounds);
        if (!point) continue;
        const radius = worldRadiusToCanvas(Number(objective.radius || 500), width, height, worldBounds);
        const objectiveId = objective.id || objective.lua_name || objective.name || '';
        const state = stateByObjective && objectiveId ? stateByObjective[objectiveId] : null;
        ctx.save();
        ctx.fillStyle = state ? getObjectiveStateColor(state) : getObjectiveTypeColor(objective.type);
        ctx.strokeStyle = state ? withAlpha(getObjectiveStateColor(state), 0.6) : 'rgba(226, 232, 240, 0.45)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.arc(point.x, point.y, radius, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();

        // center marker
        ctx.fillStyle = 'rgba(226, 232, 240, 0.9)';
        ctx.beginPath();
        ctx.arc(point.x, point.y, 2.2, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
    }
}

function updateEventLegend(targetTeam, attackerTeam) {
    const targetDot = document.getElementById('proximity-legend-target-dot');
    const targetText = document.getElementById('proximity-legend-target-text');
    const attackerDot = document.getElementById('proximity-legend-attacker-dot');
    const attackerText = document.getElementById('proximity-legend-attacker-text');
    if (targetDot) targetDot.style.backgroundColor = getTeamColor(targetTeam, 'rgba(56, 189, 248, 0.9)');
    if (attackerDot) attackerDot.style.backgroundColor = getTeamColor(attackerTeam, 'rgba(249, 115, 22, 0.9)');
    if (targetText) targetText.textContent = targetTeam ? `Target path (${targetTeam})` : 'Target path';
    if (attackerText) attackerText.textContent = attackerTeam ? `Attacker path (${attackerTeam}, dashed)` : 'Attacker path (dashed)';
}

async function renderHeatmap(payload) {
    const canvas = document.getElementById('proximity-heatmap');
    const empty = document.getElementById('proximity-heatmap-empty');
    const caption = document.getElementById('proximity-heatmap-caption');
    if (!canvas) return;

    proximityRenderCache.heatmapPayload = payload || { hotzones: [] };

    const hotzones = payload?.hotzones || [];
    const scope = getScopeDescription();
    if (!hotzones.length) {
        if (empty) empty.classList.remove('hidden');
        if (caption) caption.textContent = `No hotzone data yet for ${scope}.`;
        return;
    }

    if (empty) empty.classList.add('hidden');
    const mapName = payload?.map_name || 'unknown';
    if (caption) caption.textContent = `Map: ${stripEtColors(mapName)} • ${hotzones.length} hotzones • ${scope}`;

    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const width = canvas.clientWidth || 480;
    const height = canvas.clientHeight || 192;
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    ctx.scale(dpr, dpr);

    ctx.clearRect(0, 0, width, height);
    await ensureMapTransformConfig();
    const transform = getMapTransformEntry(mapName);
    const worldBounds = getWorldBounds(transform);
    const mapImage = await preloadMapImage(transform?.image || null);
    if (mapImage) {
        ctx.save();
        ctx.globalAlpha = 0.26;
        ctx.drawImage(mapImage, 0, 0, width, height);
        ctx.restore();
    }

    const maxKills = Math.max(...hotzones.map((h) => Number(h.kills || 0)), 1);
    const heatScale = clamp(Number(proximityVizState.heatIntensity || 1), 0.6, 1.8);
    const alphaScale = clamp(heatScale, 0.6, 1.8);

    if (worldBounds) {
        await ensureObjectiveZonesConfig();
        const objectiveZones = getObjectiveZonesForMap(mapName).filter(shouldRenderObjectiveZone);
        if (proximityVizState.showObjectiveZones) {
            drawObjectiveZones(ctx, width, height, worldBounds, objectiveZones);
        }

        const cellRadius = worldRadiusToCanvas(PROXIMITY_GRID_SIZE * 0.65, width, height, worldBounds);
        for (const zone of hotzones) {
            const kills = Number(zone.kills || 0);
            const gx = Number(zone.grid_x);
            const gy = Number(zone.grid_y);
            if (!Number.isFinite(gx) || !Number.isFinite(gy)) continue;
            const worldX = (gx + 0.5) * PROXIMITY_GRID_SIZE;
            const worldY = (gy + 0.5) * PROXIMITY_GRID_SIZE;
            const point = worldToCanvasPoint(worldX, worldY, width, height, worldBounds);
            if (!point) continue;

            const intensity = clamp(kills / maxKills, 0, 1);
            const radius = Math.max(8, cellRadius * (0.65 + intensity * 0.55) * (0.72 + heatScale * 0.28));
            const gradient = ctx.createRadialGradient(point.x, point.y, 0, point.x, point.y, radius);
            gradient.addColorStop(0, `rgba(248, 113, 113, ${(0.65 * intensity + 0.15) * alphaScale})`);
            gradient.addColorStop(0.65, `rgba(244, 63, 94, ${(0.35 * intensity + 0.08) * alphaScale})`);
            gradient.addColorStop(1, 'rgba(244, 63, 94, 0)');
            ctx.fillStyle = gradient;
            ctx.beginPath();
            ctx.arc(point.x, point.y, radius, 0, Math.PI * 2);
            ctx.fill();
        }
        return;
    }

    // Fallback to old relative grid rendering when map transform is unavailable.
    const xs = hotzones.map((h) => h.grid_x);
    const ys = hotzones.map((h) => h.grid_y);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const pad = 6;
    const spanX = Math.max(maxX - minX, 1);
    const spanY = Math.max(maxY - minY, 1);

    for (const h of hotzones) {
        const normX = (h.grid_x - minX) / spanX;
        const normY = (h.grid_y - minY) / spanY;
        const size = (6 + Math.min(18, (h.kills / maxKills) * 18)) * (0.72 + heatScale * 0.28);
        const x = pad + normX * (width - pad * 2);
        const y = pad + normY * (height - pad * 2);
        const alpha = (0.2 + Math.min(0.75, (h.kills / maxKills) * 0.75)) * alphaScale;
        ctx.fillStyle = `rgba(244, 63, 94, ${alpha})`;
        ctx.beginPath();
        ctx.arc(x, y, size / 2, 0, Math.PI * 2);
        ctx.fill();
    }
}

function renderEventList(events) {
    const container = document.getElementById('proximity-event-list');
    if (!container) return;

    if (!events || events.length === 0) {
        container.innerHTML = `<div class="text-xs text-slate-600">No events loaded yet.</div>`;
        return;
    }

    container.innerHTML = events.map((e) => {
        const map = stripEtColors(e.map || 'unknown');
        const target = stripEtColors(e.target || 'unknown');
        const outcome = e.outcome || 'unknown';
        const round = e.round != null ? `R${e.round}` : 'R?';
        const roundButton = e.round_id != null
            ? `<button class="text-[10px] text-brand-cyan hover:text-white" data-round-id="${e.round_id}">View round</button>`
            : '';
        const date = e.round_date || e.date || '';
        const time = e.round_time || '';
        const crossfire = e.crossfire ? 'Crossfire' : 'Solo';
        const duration = e.duration_ms != null ? formatDurationMs(e.duration_ms) : '--';
        const distance = e.distance_traveled != null ? `${Math.round(e.distance_traveled)}u` : '--';
        return `
            <div class="glass-card p-3 rounded-lg hover:border-brand-cyan/40 border border-white/5 transition cursor-pointer" data-event-id="${e.id}">
                <div class="flex items-center justify-between text-xs text-slate-500">
                    <span>${escapeHtml(map)} • ${escapeHtml(round)} • ${escapeHtml(date)} ${escapeHtml(time)}</span>
                    ${roundButton}
                </div>
                <div class="text-sm font-semibold text-white mt-1">${escapeHtml(target)}</div>
                <div class="text-[10px] text-slate-400 mt-1">${escapeHtml(outcome)} • ${escapeHtml(crossfire)} • ${formatNumber(e.attackers || 0)} attackers • ${escapeHtml(duration)} • ${escapeHtml(distance)}</div>
            </div>
        `;
    }).join('');

    container.querySelectorAll('[data-event-id]').forEach((card) => {
        card.addEventListener('click', async () => {
            const id = card.getAttribute('data-event-id');
            if (!id) return;
            await loadEventDetail(id);
        });
    });

    container.querySelectorAll('[data-round-id]').forEach((btn) => {
        btn.addEventListener('click', (event) => {
            event.stopPropagation();
            const roundId = btn.getAttribute('data-round-id');
            if (!roundId || typeof window.loadMatchDetails !== 'function') return;
            window.loadMatchDetails(parseInt(roundId, 10));
        });
    });
}

function drawEngagementPath(
    targetPath,
    attackerPath = [],
    strafeEvents = [],
    mapTransform = null,
    mapImage = null,
    objectiveZones = [],
    targetTeam = null,
    attackerTeam = null
) {
    const canvas = document.getElementById('proximity-event-canvas');
    const empty = document.getElementById('proximity-event-empty');
    if (!canvas) return;

    const targetPointsRaw = Array.isArray(targetPath) ? targetPath : [];
    const attackerPointsRaw = Array.isArray(attackerPath) ? attackerPath : [];
    const allRaw = targetPointsRaw.concat(attackerPointsRaw);

    if (!allRaw || allRaw.length === 0) {
        if (empty) empty.classList.remove('hidden');
        renderObjectiveStateSummary([]);
        renderObjectiveTimelineStrip(null);
        return;
    }
    if (empty) empty.classList.add('hidden');

    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const width = canvas.clientWidth || 600;
    const height = canvas.clientHeight || 260;
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    ctx.scale(dpr, dpr);

    ctx.clearRect(0, 0, width, height);
    if (mapImage) {
        ctx.save();
        ctx.globalAlpha = 0.28;
        ctx.drawImage(mapImage, 0, 0, width, height);
        ctx.restore();
    }

    const xs = allRaw.map(p => p.x);
    const ys = allRaw.map(p => p.y);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const spanX = Math.max(maxX - minX, 1);
    const spanY = Math.max(maxY - minY, 1);
    const pad = 12;

    const worldBounds = getWorldBounds(mapTransform);
    const hasWorldBounds = !!worldBounds;

    const mapPoints = (path) => path.map((p) => {
        let canvasX;
        let canvasY;
        if (hasWorldBounds) {
            const point = worldToCanvasPoint(p.x, p.y, width, height, worldBounds);
            canvasX = point.x;
            canvasY = point.y;
        } else {
            const nx = (p.x - minX) / spanX;
            const ny = (p.y - minY) / spanY;
            canvasX = pad + nx * (width - pad * 2);
            canvasY = pad + ny * (height - pad * 2);
        }
        return {
            x: canvasX,
            y: canvasY,
            event: p.event,
            t: p.time,
        };
    });

    const targetPoints = mapPoints(targetPointsRaw);
    const attackerPoints = mapPoints(attackerPointsRaw);
    const targetStroke = getTeamColor(targetTeam, 'rgba(56, 189, 248, 0.85)');
    const attackerStroke = getTeamColor(attackerTeam, 'rgba(249, 115, 22, 0.8)');
    const objectiveStates = computeObjectiveZoneStates(targetPointsRaw, attackerPointsRaw, objectiveZones);
    const objectiveTimeline = computeObjectiveTimelineRows(targetPointsRaw, attackerPointsRaw, objectiveZones, objectiveStates, 24);
    const objectiveStateById = objectiveStates.reduce((acc, row) => {
        acc[row.id] = row.state;
        return acc;
    }, {});
    renderObjectiveStateSummary(objectiveStates, targetTeam, attackerTeam);
    renderObjectiveTimelineStrip(objectiveTimeline, targetTeam, attackerTeam);

    let targetAlpha = 1;
    let attackerAlpha = 1;
    if (proximityVizState.teamEmphasis === 'target') {
        attackerAlpha = 0.25;
    } else if (proximityVizState.teamEmphasis === 'attacker') {
        targetAlpha = 0.25;
    }

    if (hasWorldBounds && proximityVizState.showObjectiveZones) {
        drawObjectiveZones(ctx, width, height, worldBounds, objectiveZones, objectiveStateById);
    }

    if (attackerPoints.length > 1) {
        ctx.save();
        ctx.strokeStyle = withAlpha(attackerStroke, attackerAlpha);
        ctx.lineWidth = 2;
        ctx.setLineDash([6, 4]);
        ctx.beginPath();
        attackerPoints.forEach((pt, idx) => {
            if (idx === 0) ctx.moveTo(pt.x, pt.y);
            else ctx.lineTo(pt.x, pt.y);
        });
        ctx.stroke();
        ctx.restore();
    }

    ctx.save();
    ctx.strokeStyle = withAlpha(targetStroke, targetAlpha);
    ctx.lineWidth = 3;
    ctx.beginPath();
    targetPoints.forEach((pt, idx) => {
        if (idx === 0) ctx.moveTo(pt.x, pt.y);
        else ctx.lineTo(pt.x, pt.y);
    });
    ctx.stroke();
    ctx.restore();

    const start = targetPoints[0];
    const end = targetPoints[targetPoints.length - 1];
    if (start && end) {
        ctx.fillStyle = withAlpha(targetStroke, targetAlpha);
        ctx.beginPath();
        ctx.arc(start.x, start.y, 6, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = 'rgba(226, 232, 240, 0.9)';
        ctx.beginPath();
        ctx.arc(end.x, end.y, 5, 0, Math.PI * 2);
        ctx.fill();
    }

    for (const pt of targetPoints) {
        if (pt.event === 'hit' || pt.event === 'death') {
            const markerColor = pt.event === 'death' ? 'rgba(248,113,113,0.9)' : 'rgba(250,204,21,0.9)';
            ctx.fillStyle = withAlpha(markerColor, targetAlpha);
            ctx.beginPath();
            ctx.arc(pt.x, pt.y, pt.event === 'death' ? 5 : 4, 0, Math.PI * 2);
            ctx.fill();
        }
    }

    if (strafeEvents && strafeEvents.length) {
        ctx.fillStyle = 'rgba(167, 139, 250, 0.9)';
        for (const ev of strafeEvents) {
            const match = targetPoints.reduce((closest, pt) => {
                const dt = Math.abs((pt.t ?? 0) - (ev.time ?? 0));
                if (!closest || dt < closest.dt) {
                    return { dt, pt };
                }
                return closest;
            }, null);
            const drawPt = match ? match.pt : null;
            if (drawPt) {
                ctx.beginPath();
                ctx.arc(drawPt.x, drawPt.y, 4, 0, Math.PI * 2);
                ctx.fill();
            }
        }
    }
}

function redrawEventFromCache() {
    const payload = proximityRenderCache.eventPayload;
    if (!payload) {
        renderObjectiveStateSummary([]);
        renderObjectiveTimelineStrip(null);
        updateEventLegend(null, null);
        return;
    }
    drawEngagementPath(
        payload.targetPath || [],
        payload.attackerPath || [],
        payload.strafeEvents || [],
        payload.transform || null,
        payload.mapImage || null,
        payload.objectiveZones || [],
        payload.targetTeam || null,
        payload.attackerTeam || null
    );
    updateEventLegend(payload.targetTeam || null, payload.attackerTeam || null);
}

async function redrawHeatmapFromCache() {
    const payload = proximityRenderCache.heatmapPayload;
    if (!payload) return;
    await renderHeatmap(payload);
}

async function loadEventDetail(id) {
    const meta = document.getElementById('proximity-event-meta');
    const details = document.getElementById('proximity-event-details');
    const statsEl = document.getElementById('proximity-event-stats');
    if (meta) meta.textContent = 'Loading…';
    if (statsEl) statsEl.innerHTML = '';
    try {
        const data = await fetchJSON(`${API_BASE}/proximity/event/${id}`);
        const map = stripEtColors(data.map_name || 'unknown');
        const target = stripEtColors(data.target_name || 'unknown');
        const outcome = data.outcome || 'unknown';
        const round = data.round_number != null ? `R${data.round_number}` : 'R?';
        const roundDate = data.round_date || data.session_date || '';
        const roundTime = data.round_time || '';
        if (meta) meta.textContent = `${map} • ${round} • ${roundDate} ${roundTime}`;

        let attackers = data.attackers;
        if (typeof attackers === 'string') {
            try {
                attackers = JSON.parse(attackers);
            } catch {
                attackers = [];
            }
        }
        attackers = Array.isArray(attackers) ? attackers : Object.values(attackers || {});
        const attackerNames = attackers.map(a => stripEtColors(a.name || 'unknown')).slice(0, 3).join(', ');
        const killer = attackers.find(a => a.got_kill) || {};
        const killerName = stripEtColors(data.attacker_name || killer.name || 'unknown');
        const roundId = data.round_id != null ? `Round ID: ${data.round_id}` : 'Round ID: n/a';
        const duration = data.duration_ms != null ? formatDurationMs(data.duration_ms) : '--';
        const distance = data.distance_traveled != null ? `${Math.round(data.distance_traveled)}u` : '--';
        const crossfire = data.is_crossfire ? 'Crossfire' : 'Solo';
        const attackersCount = attackers.length;
        if (statsEl) {
            statsEl.innerHTML = `
                <span class="px-2 py-1 rounded bg-white/5 border border-white/10">Duration: ${duration}</span>
                <span class="px-2 py-1 rounded bg-white/5 border border-white/10">Distance: ${distance}</span>
                <span class="px-2 py-1 rounded bg-white/5 border border-white/10">Attackers: ${attackersCount}</span>
                <span class="px-2 py-1 rounded bg-white/5 border border-white/10">Killer: ${escapeHtml(killerName)}</span>
                <span class="px-2 py-1 rounded bg-white/5 border border-white/10">${crossfire}</span>
            `;
        }
        if (details) {
            details.textContent = `${roundId} • Target: ${target} • Killer: ${killerName} • Outcome: ${outcome} • ${crossfire} • Duration: ${duration} • Distance: ${distance} • Damage: ${data.total_damage ?? 0} • Attackers: ${attackers.length} (${attackerNames || 'n/a'})`;
        }

        let targetPath = data.target_path && data.target_path.length ? data.target_path : data.position_path;
        if (typeof targetPath === 'string') {
            try {
                targetPath = JSON.parse(targetPath);
            } catch {
                targetPath = [];
            }
        }
        let attackerPath = data.attacker_path || [];
        if (typeof attackerPath === 'string') {
            try {
                attackerPath = JSON.parse(attackerPath);
            } catch {
                attackerPath = [];
            }
        }
        const strafe = data.strafe || {};
        const targetStrafe = strafe.target || {};
        const attackerStrafe = strafe.attacker || {};
        const targetTurns = targetStrafe.turn_count != null ? targetStrafe.turn_count : 0;
        const targetRate = targetStrafe.turn_rate != null ? `${targetStrafe.turn_rate.toFixed(2)}/s` : '--';
        const attackerTurns = attackerStrafe.turn_count != null ? attackerStrafe.turn_count : 0;
        const attackerRate = attackerStrafe.turn_rate != null ? `${attackerStrafe.turn_rate.toFixed(2)}/s` : '--';
        let strafeSummary = `Target strafe: ${targetTurns} turns (${targetRate}) • Attacker strafe: ${attackerTurns} turns (${attackerRate})`;
        if (Array.isArray(targetStrafe.events) && targetStrafe.events.length && data.start_time_ms != null) {
            const times = targetStrafe.events
                .slice(0, 5)
                .map(ev => ((ev.time - data.start_time_ms) / 1000).toFixed(1) + 's');
            strafeSummary += ` • Turns @ ${times.join(', ')}${targetStrafe.events.length > 5 ? '…' : ''}`;
        }
        if (details) {
            details.textContent = `${details.textContent} • ${strafeSummary}`;
        }

        const targetTeam = normalizeTeamName(data.target_team);
        let attackerTeam = normalizeTeamName(killer.team);
        if (!attackerTeam) {
            attackerTeam = normalizeTeamName((attackers.find((a) => normalizeTeamName(a?.team)) || {}).team);
        }
        if (!attackerTeam) {
            attackerTeam = getOpposingTeam(targetTeam);
        }

        await Promise.all([ensureMapTransformConfig(), ensureObjectiveZonesConfig()]);
        const transform = getMapTransformEntry(data.map_name || map || '');
        const objectiveZones = getObjectiveZonesForMap(data.map_name || map || '').filter(shouldRenderObjectiveZone);
        const mapImage = await preloadMapImage(transform?.image || null);

        proximityRenderCache.eventPayload = {
            targetPath: targetPath || [],
            attackerPath: attackerPath || [],
            strafeEvents: targetStrafe.events || [],
            transform,
            mapImage,
            objectiveZones,
            targetTeam,
            attackerTeam,
        };
        redrawEventFromCache();
    } catch (e) {
        if (meta) meta.textContent = 'Failed to load';
        if (details) details.textContent = 'Unable to load engagement details.';
        if (statsEl) statsEl.innerHTML = '';
        proximityRenderCache.eventPayload = null;
        renderObjectiveStateSummary([]);
        renderObjectiveTimelineStrip(null);
        updateEventLegend(null, null);
    }
}

function renderSummary(data) {
    const engagements = data.total_engagements ?? data.engagements ?? null;
    const avgDistance = data.avg_distance_m ?? data.avg_distance ?? null;
    const crossfire = data.crossfire_events ?? data.crossfire ?? null;
    const hotzones = data.hotzones ?? data.hotzone_count ?? null;
    const escapeRate = data.escape_rate_pct ?? null;
    const avgDuration = data.avg_duration_ms ?? null;
    const avgAttackers = data.avg_attackers ?? null;
    const avgSprint = data.avg_sprint_pct ?? null;

    setText('proximity-total-engagements', engagements != null ? formatNumber(engagements) : '--');
    setText('proximity-avg-distance', avgDistance != null ? `${avgDistance.toFixed(1)}u` : '--');
    setText('proximity-crossfire', crossfire != null ? formatNumber(crossfire) : '--');
    setText('proximity-hotzones', hotzones != null ? formatNumber(hotzones) : '--');
    setText('proximity-escape-rate', escapeRate != null ? `${escapeRate.toFixed(1)}%` : '--');
    setText('proximity-avg-duration', avgDuration != null ? formatDurationMs(avgDuration) : '--');
    setText('proximity-avg-attackers', avgAttackers != null ? avgAttackers.toFixed(2) : '--');
    setText('proximity-avg-sprint', avgSprint != null ? `${avgSprint.toFixed(1)}%` : '--');

    renderDuos(data.top_duos || []);
}

function renderClassSummary(payload) {
    const container = document.getElementById('proximity-class-summary');
    if (!container) return;
    const rows = payload?.classes || [];
    if (!rows.length) {
        container.innerHTML = `<div class="text-[11px] text-slate-500">No class metrics yet.</div>`;
        return;
    }

    container.innerHTML = rows.map((row) => {
        const classLabel = stripEtColors(row.player_class || 'UNKNOWN');
        const tracks = formatNumber(row.tracks || 0);
        const players = formatNumber(row.players || 0);
        const avgReaction = row.avg_spawn_reaction_ms != null ? formatMs(row.avg_spawn_reaction_ms) : '--';
        const avgDuration = row.avg_duration_ms != null ? formatDurationMs(row.avg_duration_ms) : '--';
        return `
            <div class="glass-card p-3 rounded-lg border border-white/5">
                <div class="flex items-center justify-between">
                    <span class="font-bold text-white">${escapeHtml(classLabel)}</span>
                    <span class="text-[10px] text-slate-500">tracks ${tracks}</span>
                </div>
                <div class="mt-1 text-[10px] text-slate-500">players ${players} • spawn react ${escapeHtml(avgReaction)} • avg life ${escapeHtml(avgDuration)}</div>
            </div>
        `;
    }).join('');
}

function renderClassReactionSummary(rows) {
    const container = document.getElementById('proximity-class-reaction-summary');
    if (!container) return;
    const list = Array.isArray(rows) ? rows : [];
    if (!list.length) {
        container.innerHTML = `<div class="text-[11px] text-slate-500">No class reaction baselines yet.</div>`;
        return;
    }
    container.innerHTML = list.map((row) => {
        const classLabel = stripEtColors(row.player_class || 'UNKNOWN');
        const events = formatNumber(row.events || 0);
        const returnMs = row.avg_return_fire_ms != null ? formatMs(row.avg_return_fire_ms) : '--';
        const dodgeMs = row.avg_dodge_reaction_ms != null ? formatMs(row.avg_dodge_reaction_ms) : '--';
        const supportMs = row.avg_support_reaction_ms != null ? formatMs(row.avg_support_reaction_ms) : '--';
        return `
            <div class="glass-card p-3 rounded-lg border border-white/5">
                <div class="flex items-center justify-between">
                    <span class="font-bold text-white">${escapeHtml(classLabel)}</span>
                    <span class="text-[10px] text-slate-500">${events} events</span>
                </div>
                <div class="mt-1 text-[10px] text-slate-500">rf ${escapeHtml(returnMs)} • dodge ${escapeHtml(dodgeMs)} • support ${escapeHtml(supportMs)}</div>
            </div>
        `;
    }).join('');
}

function renderReactionSignals(payload) {
    const returnRows = payload?.return_fire || [];
    const dodgeRows = payload?.dodge || [];
    const supportRows = payload?.support || [];
    const classRows = payload?.class_summary || [];
    const formatWithClass = (row) => `${stripEtColors(row.player_class || 'UNKNOWN')} • ${formatMs(row.reaction_ms)}`;

    renderLeaderList('proximity-returnfire-leaders', returnRows, formatWithClass);
    renderLeaderList('proximity-dodge-leaders', dodgeRows, formatWithClass);
    renderLeaderList('proximity-support-reaction-leaders', supportRows, formatWithClass);
    renderClassReactionSummary(classRows);
}

function resetProximityValues() {
    proximityRenderCache.eventPayload = null;
    proximityRenderCache.heatmapPayload = { hotzones: [] };

    setText('proximity-total-engagements', '--');
    setText('proximity-avg-distance', '--');
    setText('proximity-crossfire', '--');
    setText('proximity-hotzones', '--');
    setText('proximity-escape-rate', '--');
    setText('proximity-avg-duration', '--');
    setText('proximity-avg-attackers', '--');
    setText('proximity-avg-sprint', '--');
    setText('proximity-trade-opportunities', '--');
    setText('proximity-trade-attempts', '--');
    setText('proximity-trade-success', '--');
    setText('proximity-trade-missed', '--');
    setText('proximity-support-uptime', '--');
    setText('proximity-isolation-deaths', '--');
    setText('proximity-trade-attempt-rate', '--');
    setText('proximity-trade-conversion-rate', '--');
    setText('proximity-trade-miss-rate', '--');
    const defaultScope = `Last ${DEFAULT_RANGE_DAYS}d window`;
    setText('proximity-window-label', defaultScope);
    setText('proximity-scope-caption', defaultScope);
    setText('proximity-timeline-scope', `Scope: ${defaultScope}`);
    setText('proximity-heatmap-scope', `Scope: ${defaultScope}`);
    updateHeatIntensityLabel();

    renderTimeline([]);
    void renderHeatmap({ hotzones: [] }).catch(() => {});
    renderEventList([]);
    renderTradeEvents([]);
    renderDuos([]);
    renderLeaderList('proximity-distance-leaders', [], () => '--');
    renderLeaderList('proximity-sprint-leaders', [], () => '--');
    renderLeaderList('proximity-reaction-leaders', [], () => '--');
    renderLeaderList('proximity-survival-leaders', [], () => '--');
    renderLeaderList('proximity-crossfire-leaders', [], () => '--');
    renderLeaderList('proximity-sync-leaders', [], () => '--');
    renderLeaderList('proximity-focus-leaders', [], () => '--');
    renderLeaderList('proximity-returnfire-leaders', [], () => '--');
    renderLeaderList('proximity-dodge-leaders', [], () => '--');
    renderLeaderList('proximity-support-reaction-leaders', [], () => '--');
    renderClassSummary({ classes: [] });
    // v5 resets
    setHtml('spawn-timing-teams', '');
    setHtml('spawn-timing-leaders', '');
    setHtml('cohesion-summary', '');
    setHtml('crossfire-angles-summary', '');
    setHtml('crossfire-angle-buckets', '');
    setHtml('crossfire-top-duos', '');
    setHtml('team-pushes-summary', '');
    setHtml('lua-trades-summary', '');
    setHtml('lua-trades-leaders', '');
    setHtml('lua-trades-recent', '');
    renderObjectiveStateSummary([]);
    renderObjectiveTimelineStrip(null);
    renderClassReactionSummary([]);

    const meta = document.getElementById('proximity-event-meta');
    const details = document.getElementById('proximity-event-details');
    const stats = document.getElementById('proximity-event-stats');
    const canvas = document.getElementById('proximity-event-canvas');
    const empty = document.getElementById('proximity-event-empty');
    if (meta) meta.textContent = 'Select an event';
    if (details) details.textContent = '';
    if (stats) stats.innerHTML = '';
    if (canvas) {
        const ctx = canvas.getContext('2d');
        if (ctx) {
            const width = canvas.clientWidth || 600;
            const height = canvas.clientHeight || 260;
            ctx.clearRect(0, 0, width, height);
        }
    }
    if (empty) empty.classList.remove('hidden');
    updateEventLegend(null, null);
}

async function loadScopeHierarchy() {
    try {
        const data = await fetchJSON(`${API_BASE}/proximity/scopes?range_days=${DEFAULT_SCOPE_RANGE_DAYS}`);
        proximityScopeState.sessions = Array.isArray(data?.sessions) ? data.sessions : [];
        if (!proximityScopeState.sessionDate) {
            proximityScopeState.sessionDate = data?.scope?.session_date || proximityScopeState.sessions[0]?.session_date || null;
        }
    } catch {
        proximityScopeState.sessions = [];
        proximityScopeState.sessionDate = null;
        proximityScopeState.mapName = null;
        proximityScopeState.roundNumber = null;
        proximityScopeState.roundStartUnix = null;
    }
    renderScopeSelectors();
}

async function loadScopedProximityData() {
    const loadId = ++proximityScopedLoadId;
    resetProximityValues();
    const stateEl = document.getElementById('proximity-state');
    updateScopeUIText();

    if (stateEl) {
        stateEl.innerHTML = `
            <i data-lucide="clock" class="w-4 h-4 text-brand-cyan"></i>
            <span>Loading scoped proximity data...</span>
        `;
    }

    try {
        const data = await fetchJSON(scopedUrl('/proximity/summary'));
        if (loadId !== proximityScopedLoadId) return;
        renderSummary(data);
        const ready = data?.ready === true || data?.status === 'ok' || data?.status === 'ready';
        if (!ready) {
            if (stateEl) {
                const message = data?.message || 'Prototype mode: proximity data not ready yet.';
                stateEl.innerHTML = `
                    <i data-lucide="alert-circle" class="w-4 h-4 text-brand-rose"></i>
                    <span>${escapeHtml(message)}</span>
                `;
            }
        } else if (stateEl) {
            const rounds = data.sample_rounds != null ? formatNumber(data.sample_rounds) : 'n/a';
            stateEl.innerHTML = `
                <i data-lucide="activity" class="w-4 h-4 text-brand-emerald"></i>
                <span>Live proximity snapshot • ${rounds} rounds analyzed • ${escapeHtml(getScopeDescription())}</span>
            `;
        }

        if (ready) {
            const [
                timelineRes,
                heatmapRes,
                moversRes,
                teamplayRes,
                classRes,
                reactionRes,
                eventsRes,
                tradesSummaryRes,
                tradesEventsRes,
                spawnTimingRes,
                cohesionRes,
                crossfireAnglesRes,
                pushesRes,
                luaTradesRes,
                killOutcomesRes,
                killOutcomeStatsRes,
                hitRegionsRes,
                headshotRatesRes,
                movementStatsRes,
                proxScoresRes,
                proxFormulaRes,
                weaponAccuracyRes,
                revivesRes,
                carrierEventsRes,
                carrierKillsRes,
                carrierReturnsRes,
                vehicleProgressRes,
                escortCreditsRes,
                constructionEventsRes,
                objectiveRunsRes,
                focusFireRes,
                objectiveFocusRes,
                supportSummaryRes,
                combatPosStatsRes
            ] = await Promise.allSettled([
                fetchJSON(scopedUrl('/proximity/engagements')),
                fetchJSON(scopedUrl('/proximity/hotzones')),
                fetchJSON(scopedUrl('/proximity/movers')),
                fetchJSON(scopedUrl('/proximity/teamplay', { extra: { limit: 6 } })),
                fetchJSON(scopedUrl('/proximity/classes')),
                fetchJSON(scopedUrl('/proximity/reactions', { extra: { limit: 6 } })),
                fetchJSON(scopedUrl('/proximity/events', { extra: { limit: DEFAULT_EVENTS_LIMIT } })),
                fetchJSON(scopedUrl('/proximity/trades/summary')),
                fetchJSON(scopedUrl('/proximity/trades/events', { extra: { limit: 10 } })),
                fetchJSON(scopedUrl('/proximity/spawn-timing')),
                fetchJSON(scopedUrl('/proximity/cohesion')),
                fetchJSON(scopedUrl('/proximity/crossfire-angles')),
                fetchJSON(scopedUrl('/proximity/pushes')),
                fetchJSON(scopedUrl('/proximity/lua-trades')),
                fetchJSON(scopedUrl('/proximity/kill-outcomes')),
                fetchJSON(scopedUrl('/proximity/kill-outcomes/player-stats')),
                fetchJSON(scopedUrl('/proximity/hit-regions')),
                fetchJSON(scopedUrl('/proximity/hit-regions/headshot-rates')),
                fetchJSON(scopedUrl('/proximity/movement-stats')),
                fetchJSON(scopedUrl('/proximity/prox-scores', { extra: { min_engagements: 30 } })),
                fetchJSON(scopedUrl('/proximity/prox-scores/formula', { includeRange: false })),
                fetchJSON(scopedUrl('/proximity/weapon-accuracy')),
                fetchJSON(scopedUrl('/proximity/revives')),
                fetchJSON(scopedUrl('/proximity/carrier-events')),
                fetchJSON(scopedUrl('/proximity/carrier-kills')),
                fetchJSON(scopedUrl('/proximity/carrier-returns')),
                fetchJSON(scopedUrl('/proximity/vehicle-progress')),
                fetchJSON(scopedUrl('/proximity/escort-credits')),
                fetchJSON(scopedUrl('/proximity/construction-events')),
                fetchJSON(scopedUrl('/proximity/objective-runs')),
                fetchJSON(scopedUrl('/proximity/focus-fire')),
                fetchJSON(scopedUrl('/proximity/objective-focus')),
                fetchJSON(scopedUrl('/proximity/support-summary')),
                fetchJSON(scopedUrl('/proximity/combat-position-stats'))
            ]);
            if (loadId !== proximityScopedLoadId) return;

            if (timelineRes.status === 'fulfilled') {
                renderTimeline(timelineRes.value.buckets || []);
            }
            if (heatmapRes.status === 'fulfilled') {
                await renderHeatmap(heatmapRes.value);
                if (loadId !== proximityScopedLoadId) return;
            }
            if (eventsRes.status === 'fulfilled') {
                renderEventList(eventsRes.value.events || []);
            }
            if (moversRes.status === 'fulfilled') {
                const movers = moversRes.value;
                renderLeaderList('proximity-distance-leaders', movers.distance, (row) => {
                    const distance = row.total_distance != null ? `${formatNumber(Math.round(row.total_distance))}u` : '--';
                    return distance;
                });
                renderLeaderList('proximity-sprint-leaders', movers.sprint, (row) => {
                    const pct = row.sprint_pct != null ? `${row.sprint_pct.toFixed(1)}%` : '--';
                    return pct;
                });
                renderLeaderList('proximity-reaction-leaders', movers.reaction, (row) => {
                    return formatMs(row.reaction_ms);
                });
                renderLeaderList('proximity-survival-leaders', movers.survival, (row) => {
                    return row.duration_ms != null ? formatDurationMs(row.duration_ms) : '--';
                });
            }
            if (teamplayRes.status === 'fulfilled') {
                const teamplay = teamplayRes.value;
                renderLeaderList('proximity-crossfire-leaders', teamplay.crossfire_kills, (row) => {
                    const kills = row.crossfire_kills != null ? formatNumber(row.crossfire_kills) : '--';
                    const rate = row.kill_rate_pct != null ? `${row.kill_rate_pct.toFixed(1)}%` : '--';
                    return `${kills} (${rate})`;
                });
                renderLeaderList('proximity-sync-leaders', teamplay.sync, (row) => {
                    const delay = row.avg_delay_ms != null ? `${row.avg_delay_ms.toFixed(0)}ms` : '--';
                    return delay;
                });
                renderLeaderList('proximity-focus-leaders', teamplay.focus_survival, (row) => {
                    const rate = row.survival_rate_pct != null ? `${row.survival_rate_pct.toFixed(1)}%` : '--';
                    return `${rate} (${row.focus_escapes || 0}/${row.times_focused || 0})`;
                });
            }
            if (classRes.status === 'fulfilled') {
                renderClassSummary(classRes.value);
            }
            if (reactionRes.status === 'fulfilled') {
                renderReactionSignals(reactionRes.value);
            }
            if (tradesSummaryRes.status === 'fulfilled') {
                renderTradeSummary(tradesSummaryRes.value);
            }
            if (tradesEventsRes.status === 'fulfilled') {
                renderTradeEvents(tradesEventsRes.value.events || []);
            }
            // v5 teamplay results
            if (spawnTimingRes.status === 'fulfilled' && spawnTimingRes.value.status === 'ok') {
                renderSpawnTimingTeams(spawnTimingRes.value.team_averages);
                renderSpawnTimingLeaders(spawnTimingRes.value.leaders);
            }
            if (cohesionRes.status === 'fulfilled' && cohesionRes.value.status === 'ok') {
                renderCohesionTeam(cohesionRes.value.team_summary);
                renderCohesionTimeline(cohesionRes.value.timeline);
            }
            if (crossfireAnglesRes.status === 'fulfilled') {
                renderCrossfireAngles(crossfireAnglesRes.value);
            }
            if (pushesRes.status === 'fulfilled') {
                renderTeamPushes(pushesRes.value);
            }
            if (luaTradesRes.status === 'fulfilled') {
                renderLuaTrades(luaTradesRes.value);
            }
            if (killOutcomesRes.status === 'fulfilled') {
                renderKillOutcomes(killOutcomesRes.value);
            }
            if (killOutcomeStatsRes.status === 'fulfilled') {
                renderKillOutcomePlayerStats(killOutcomeStatsRes.value);
            }
            if (hitRegionsRes.status === 'fulfilled') {
                renderHitRegions(hitRegionsRes.value);
            }
            if (headshotRatesRes.status === 'fulfilled') {
                renderHeadshotRates(headshotRatesRes.value);
            }
            if (movementStatsRes.status === 'fulfilled') {
                renderMovementStats(movementStatsRes.value);
            }
            if (proxScoresRes.status === 'fulfilled') {
                const formula = proxFormulaRes.status === 'fulfilled' ? proxFormulaRes.value : null;
                renderProxScores(proxScoresRes.value, formula);
            }
            if (weaponAccuracyRes.status === 'fulfilled') {
                renderWeaponAccuracy(weaponAccuracyRes.value);
            }
            if (revivesRes.status === 'fulfilled') {
                renderRevives(revivesRes.value);
            }
            // v6 carrier intelligence
            if (carrierEventsRes.status === 'fulfilled') {
                renderCarrierIntel(carrierEventsRes.value);
            }
            if (carrierKillsRes.status === 'fulfilled') {
                renderCarrierKillers(carrierKillsRes.value);
            }
            // v6 Phase 1.5: Flag Returns
            if (carrierReturnsRes.status === 'fulfilled') {
                renderFlagReturns(carrierReturnsRes.value);
            }
            // v6 Phase 2: Vehicle + Escort
            if (vehicleProgressRes.status === 'fulfilled') {
                renderVehicleProgress(vehicleProgressRes.value);
            }
            if (escortCreditsRes.status === 'fulfilled') {
                renderEscortLeaders(escortCreditsRes.value);
            }
            // v6 Phase 3: Engineer Intelligence
            if (constructionEventsRes.status === 'fulfilled') {
                renderEngineerIntel(constructionEventsRes.value);
            }
            // v6.5: Objective Run Intelligence
            if (objectiveRunsRes.status === 'fulfilled') {
                renderObjectiveRuns(objectiveRunsRes.value);
            }
            // Focus Fire
            if (focusFireRes.status === 'fulfilled') {
                renderFocusFire(focusFireRes.value);
            }
            // Objective Focus
            if (objectiveFocusRes.status === 'fulfilled') {
                renderObjectiveFocus(objectiveFocusRes.value);
            }
            // Support Summary
            if (supportSummaryRes.status === 'fulfilled') {
                renderSupportSummary(supportSummaryRes.value);
            }
            // Combat Position Stats
            if (combatPosStatsRes.status === 'fulfilled') {
                renderCombatPositionStats(combatPosStatsRes.value);
            }
            bindV52PanelEvents();
        }
    } catch (e) {
        if (stateEl) {
            stateEl.innerHTML = `
                <i data-lucide="alert-circle" class="w-4 h-4 text-brand-rose"></i>
                <span>Prototype mode: proximity API not connected yet.</span>
            `;
        }
    }
}

function updateHeatIntensityLabel() {
    const label = document.getElementById('proximity-heat-intensity-value');
    if (!label) return;
    label.textContent = `${Number(proximityVizState.heatIntensity || 1).toFixed(1)}x`;
}

function bindVisualizationControls() {
    const objectiveToggle = document.getElementById('proximity-toggle-objective-zones');
    const heatSlider = document.getElementById('proximity-heat-intensity');
    const emphasisSelect = document.getElementById('proximity-team-emphasis');

    if (objectiveToggle && !objectiveToggle.dataset.bound) {
        objectiveToggle.dataset.bound = '1';
        objectiveToggle.checked = proximityVizState.showObjectiveZones;
        objectiveToggle.addEventListener('change', async () => {
            proximityVizState.showObjectiveZones = !!objectiveToggle.checked;
            await redrawHeatmapFromCache();
            redrawEventFromCache();
        });
    }

    if (heatSlider && !heatSlider.dataset.bound) {
        heatSlider.dataset.bound = '1';
        heatSlider.value = String(proximityVizState.heatIntensity);
        updateHeatIntensityLabel();
        heatSlider.addEventListener('input', async () => {
            const value = clamp(Number(heatSlider.value), 0.6, 1.8);
            proximityVizState.heatIntensity = value;
            updateHeatIntensityLabel();
            await redrawHeatmapFromCache();
        });
    }

    if (emphasisSelect && !emphasisSelect.dataset.bound) {
        emphasisSelect.dataset.bound = '1';
        emphasisSelect.value = proximityVizState.teamEmphasis;
        emphasisSelect.addEventListener('change', () => {
            const next = emphasisSelect.value || 'auto';
            proximityVizState.teamEmphasis = ['auto', 'target', 'attacker'].includes(next) ? next : 'auto';
            redrawEventFromCache();
        });
    }
}

function bindScopeEvents() {
    const sessionSelect = document.getElementById('proximity-session-select');
    const mapSelect = document.getElementById('proximity-map-select');
    const roundSelect = document.getElementById('proximity-round-select');
    const resetBtn = document.getElementById('proximity-reset-scope');

    if (sessionSelect && !sessionSelect.dataset.bound) {
        sessionSelect.dataset.bound = '1';
        sessionSelect.addEventListener('change', async () => {
            proximityScopeState.sessionDate = sessionSelect.value || null;
            proximityScopeState.mapName = null;
            proximityScopeState.roundNumber = null;
            proximityScopeState.roundStartUnix = null;
            renderScopeSelectors();
            await loadScopedProximityData();
            if (typeof lucide !== 'undefined') lucide.createIcons();
        });
    }

    if (mapSelect && !mapSelect.dataset.bound) {
        mapSelect.dataset.bound = '1';
        mapSelect.addEventListener('change', async () => {
            proximityScopeState.mapName = mapSelect.value || null;
            proximityScopeState.roundNumber = null;
            proximityScopeState.roundStartUnix = null;
            renderScopeSelectors();
            await loadScopedProximityData();
            if (typeof lucide !== 'undefined') lucide.createIcons();
        });
    }

    if (roundSelect && !roundSelect.dataset.bound) {
        roundSelect.dataset.bound = '1';
        roundSelect.addEventListener('change', async () => {
            const value = roundSelect.value || '';
            if (!value) {
                proximityScopeState.roundNumber = null;
                proximityScopeState.roundStartUnix = null;
            } else {
                const [roundStr, startStr] = value.split('|');
                const roundNum = parseInt(roundStr, 10);
                const roundStart = parseInt(startStr || '0', 10);
                proximityScopeState.roundNumber = Number.isFinite(roundNum) ? roundNum : null;
                proximityScopeState.roundStartUnix = Number.isFinite(roundStart) && roundStart > 0 ? roundStart : null;
            }
            renderScopeSelectors();
            await loadScopedProximityData();
            if (typeof lucide !== 'undefined') lucide.createIcons();
        });
    }

    if (resetBtn && !resetBtn.dataset.bound) {
        resetBtn.dataset.bound = '1';
        resetBtn.addEventListener('click', async () => {
            proximityScopeState.sessionDate = proximityScopeState.sessions[0]?.session_date || null;
            proximityScopeState.mapName = null;
            proximityScopeState.roundNumber = null;
            proximityScopeState.roundStartUnix = null;
            renderScopeSelectors();
            await loadScopedProximityData();
            if (typeof lucide !== 'undefined') lucide.createIcons();
        });
    }
}

export async function loadProximityView() {
    if (proximityViewLoadPromise) {
        return proximityViewLoadPromise;
    }

    proximityViewLoadPromise = (async () => {
        resetProximityValues();
        bindScopeEvents();
        bindVisualizationControls();
        await loadScopeHierarchy();
        await loadScopedProximityData();

        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    })();

    try {
        await proximityViewLoadPromise;
    } finally {
        proximityViewLoadPromise = null;
    }
}

/* ===== v5 TEAMPLAY RENDER FUNCTIONS ===== */

/* ---- v5 Spawn Timing ---- */
function renderSpawnTimingTeams(teams) {
    const el = document.getElementById('spawn-timing-teams');
    if (!el) return;
    if (!teams || !teams.length) { el.innerHTML = '<em class="text-slate-500">No data</em>'; return; }
    el.innerHTML = teams.map(t =>
        `<div class="glass-card p-3 rounded-lg border border-white/5 inline-block mr-3"><strong>${t.team}</strong><br>Avg score: ${(t.avg_score * 100).toFixed(1)}% | Kills: ${t.total_kills}</div>`
    ).join('');
}

function renderSpawnTimingLeaders(leaders) {
    const el = document.getElementById('spawn-timing-leaders');
    if (!el) return;
    if (!leaders || !leaders.length) { el.innerHTML = '<em class="text-slate-500">No data</em>'; return; }
    el.innerHTML = '<ol class="list-decimal list-inside text-sm text-slate-300 space-y-1">' + leaders.map(l =>
        `<li><strong>${escapeHtml(l.name)}</strong> — ${(l.avg_score * 100).toFixed(1)}% (${l.kills} kills, avg denial ${l.avg_denial_ms}ms)</li>`
    ).join('') + '</ol>';
}

/* ---- v5 Team Cohesion ---- */
function renderCohesionTeam(summary) {
    const el = document.getElementById('cohesion-summary');
    if (!el) return;
    if (!summary || !summary.length) { el.innerHTML = '<em class="text-slate-500">No data</em>'; return; }
    el.innerHTML = summary.map(t => {
        const cls = t.avg_dispersion < 300 ? 'TIGHT' : t.avg_dispersion < 800 ? 'NORMAL' : t.avg_dispersion < 1500 ? 'LOOSE' : 'SCATTERED';
        return `<div class="glass-card p-3 rounded-lg border border-white/5 inline-block mr-3">
            <strong>${t.team} — ${cls}</strong><br>
            Dispersion: ${t.avg_dispersion} | Spread: ${t.avg_max_spread} | Stragglers: ${t.avg_stragglers} | Alive: ${t.avg_alive}
        </div>`;
    }).join('');
}

function renderCohesionTimeline(timeline) {
    const canvas = document.getElementById('cohesion-timeline-canvas');
    if (!canvas || !timeline || !timeline.length) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width = canvas.parentElement.clientWidth || 600;
    const H = canvas.height = 200;
    ctx.clearRect(0, 0, W, H);

    const axis = timeline.filter(t => t.team === 'AXIS');
    const allies = timeline.filter(t => t.team === 'ALLIES');
    const allDisp = timeline.map(t => t.dispersion);
    const maxDisp = Math.max(...allDisp, 1);
    const minTime = Math.min(...timeline.map(t => t.time));
    const maxTime = Math.max(...timeline.map(t => t.time));
    const timeRange = maxTime - minTime || 1;

    function drawLine(data, color) {
        if (!data.length) return;
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.beginPath();
        data.forEach((p, i) => {
            const x = ((p.time - minTime) / timeRange) * W;
            const y = H - (p.dispersion / maxDisp) * H;
            i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        });
        ctx.stroke();
    }
    drawLine(axis, '#e74c3c');
    drawLine(allies, '#3498db');

    ctx.font = '12px monospace';
    ctx.fillStyle = '#e74c3c'; ctx.fillText('AXIS', 10, 15);
    ctx.fillStyle = '#3498db'; ctx.fillText('ALLIES', 70, 15);
}

/* ---- v5 Crossfire Angles ---- */
function renderCrossfireAngles(data) {
    const el = document.getElementById('crossfire-angles-summary');
    if (!el) return;
    if (!data || data.status !== 'ok') { el.innerHTML = '<em class="text-slate-500">No data</em>'; return; }
    el.innerHTML = `<div class="glass-card p-3 rounded-lg border border-white/5">
        Opportunities: <strong>${data.total_opportunities}</strong> |
        Executed: <strong>${data.executed}</strong> (${data.utilization_rate_pct}%) |
        Avg angle: ${data.avg_angle}&deg;
    </div>`;

    const bucketsEl = document.getElementById('crossfire-angle-buckets');
    if (bucketsEl && data.angle_buckets) {
        const maxCount = Math.max(...data.angle_buckets.map(b => b.count), 1);
        bucketsEl.innerHTML = data.angle_buckets.map(b => {
            const pct = (b.count / maxCount * 100).toFixed(0);
            return `<div style="margin:4px 0" class="text-sm text-slate-300">
                <span style="display:inline-block;width:150px">${b.bucket}</span>
                <span style="display:inline-block;width:${pct}%;max-width:200px;background:#e74c3c;height:16px;border-radius:3px"></span>
                <span> ${b.count} (${b.executed} exec)</span></div>`;
        }).join('');
    }

    const duosEl = document.getElementById('crossfire-top-duos');
    if (duosEl && data.top_duos && data.top_duos.length) {
        duosEl.innerHTML = '<ol class="list-decimal list-inside text-sm text-slate-300 space-y-1">' + data.top_duos.map(d =>
            `<li>${d.teammate1_guid.substring(0,8)} + ${d.teammate2_guid.substring(0,8)} = ${d.executions} exec (avg ${d.avg_angle}&deg;)</li>`
        ).join('') + '</ol>';
    }
}

/* ---- v5 Team Pushes ---- */
function renderTeamPushes(data) {
    const el = document.getElementById('team-pushes-summary');
    if (!el) return;
    if (!data || data.status !== 'ok' || !data.team_summary || !data.team_summary.length) {
        el.innerHTML = '<em class="text-slate-500">No data</em>'; return;
    }
    el.innerHTML = data.team_summary.map(t => {
        const objPct = t.pushes > 0 ? (t.objective_pushes / t.pushes * 100).toFixed(0) : 0;
        return `<div class="glass-card p-3 rounded-lg border border-white/5 inline-block mr-3">
            <strong>${t.team}</strong><br>
            Pushes: ${t.pushes} | Quality: ${t.avg_quality.toFixed(3)} | Alignment: ${t.avg_alignment.toFixed(3)}<br>
            Avg speed: ${t.avg_speed} | Participants: ${t.avg_participants.toFixed(1)} | Obj-oriented: ${objPct}%
        </div>`;
    }).join('');
}

/* ---- v5 Lua Trades ---- */
function renderLuaTrades(data) {
    const el = document.getElementById('lua-trades-summary');
    if (!el) return;
    if (!data || data.status !== 'ok') { el.innerHTML = '<em class="text-slate-500">No data</em>'; return; }
    el.innerHTML = '';

    const leadersEl = document.getElementById('lua-trades-leaders');
    if (leadersEl && data.leaders && data.leaders.length) {
        leadersEl.innerHTML = '<ol class="list-decimal list-inside text-sm text-slate-300 space-y-1">' + data.leaders.map(l =>
            `<li><strong>${escapeHtml(l.name)}</strong> — ${l.trades} trades (avg ${l.avg_reaction_ms}ms, fastest ${l.fastest_ms}ms)</li>`
        ).join('') + '</ol>';
    } else if (leadersEl) {
        leadersEl.innerHTML = '<em class="text-slate-500">No trade leaders</em>';
    }

    const recentEl = document.getElementById('lua-trades-recent');
    if (recentEl && data.recent_trades && data.recent_trades.length) {
        recentEl.innerHTML = data.recent_trades.map(t =>
            `<div class="glass-card p-2 rounded-lg border border-white/5 mb-2 text-sm text-slate-300">
                ${escapeHtml(t.victim)} killed by ${escapeHtml(t.killer)} &rarr; avenged by <strong>${escapeHtml(t.trader)}</strong> (${t.delta_ms}ms) on ${escapeHtml(t.map)}
            </div>`
        ).join('');
    }
}

/* ===== v5.2 Kill Outcomes ===== */

const OUTCOME_COLORS = { gibbed: '#ef4444', revived: '#22c55e', tapped_out: '#f59e0b', expired: '#64748b', round_end: '#6366f1' };

function _buildStatCard(label, value, cls) {
    const card = document.createElement('div');
    card.className = 'text-center';
    const lbl = document.createElement('div');
    lbl.className = 'text-[11px] font-bold text-slate-500 uppercase';
    lbl.textContent = label;
    const val = document.createElement('div');
    val.className = `text-xl font-black ${cls} mt-1`;
    val.textContent = value;
    card.append(lbl, val);
    return card;
}

function _buildBarRow(label, count, pct, widthPct, color) {
    const row = document.createElement('div');
    const header = document.createElement('div');
    header.className = 'flex justify-between text-[11px] mb-0.5';
    const nameSpan = document.createElement('span');
    nameSpan.className = 'text-slate-300';
    nameSpan.textContent = label;
    const countSpan = document.createElement('span');
    countSpan.className = 'text-slate-500';
    countSpan.textContent = `${formatNumber(count)} (${pct}%)`;
    header.append(nameSpan, countSpan);
    const track = document.createElement('div');
    track.className = 'h-2 rounded-full bg-slate-800 overflow-hidden';
    const fill = document.createElement('div');
    fill.className = 'h-full rounded-full';
    fill.style.width = `${widthPct}%`;
    fill.style.background = color;
    track.appendChild(fill);
    row.append(header, track);
    return row;
}

function renderKillOutcomes(data) {
    const s = data?.summary;
    if (!s || s.total_kills === 0) return;

    const statsEl = document.getElementById('kill-outcomes-stats');
    if (statsEl) {
        statsEl.textContent = '';
        [
            { label: 'Total Kills', value: formatNumber(s.total_kills), cls: 'text-white' },
            { label: 'Gib Rate', value: `${s.gib_rate}%`, cls: 'text-red-400' },
            { label: 'Revive Rate', value: `${s.revive_rate}%`, cls: 'text-emerald-400' },
            { label: 'Avg Outcome', value: s.avg_delta_ms ? `${(s.avg_delta_ms / 1000).toFixed(1)}s` : '--', cls: 'text-amber-400' },
            { label: 'Avg Denied', value: s.avg_denied_ms ? `${(s.avg_denied_ms / 1000).toFixed(1)}s` : '--', cls: 'text-purple-400' },
        ].forEach(x => statsEl.appendChild(_buildStatCard(x.label, x.value, x.cls)));
    }

    const barsEl = document.getElementById('kill-outcomes-bars');
    if (barsEl) {
        barsEl.textContent = '';
        const bars = [
            { key: 'gibbed', label: 'Gibbed', count: s.gibbed },
            { key: 'revived', label: 'Revived', count: s.revived },
            { key: 'tapped_out', label: 'Tapped Out', count: s.tapped_out },
            { key: 'expired', label: 'Expired', count: s.expired },
            { key: 'round_end', label: 'Round End', count: s.round_end },
        ].filter(b => b.count > 0);
        const max = Math.max(...bars.map(b => b.count), 1);
        bars.forEach(b => {
            const pct = s.total_kills > 0 ? ((b.count / s.total_kills) * 100).toFixed(1) : '0';
            const color = OUTCOME_COLORS[b.key] || '#64748b';
            barsEl.appendChild(_buildBarRow(b.label, b.count, pct, (b.count / max) * 100, color));
        });
    }
}

function renderKillOutcomePlayerStats(data) {
    renderLeaderList('kill-outcomes-kpr',
        data?.kill_permanence_leaders?.slice(0, 10) ?? [],
        (row) => {
            const kpr = row.kpr != null ? `${(row.kpr * 100).toFixed(1)}% KPR` : '--';
            const detail = `${row.gibs || 0}G / ${row.revives_against || 0}R / ${row.tapouts || 0}T`;
            return `${kpr} — ${detail}`;
        },
        'No kill permanence data yet'
    );
    renderLeaderList('kill-outcomes-revived',
        data?.revive_rate_leaders?.slice(0, 5) ?? [],
        (row) => {
            const rate = row.revive_rate != null ? `${(row.revive_rate * 100).toFixed(1)}%` : '--';
            const detail = `${row.times_revived || 0}R / ${row.times_killed || 0}D`;
            return `${rate} — ${detail}`;
        },
        'No revive data yet'
    );
}

/* ===== v5.2 Hit Regions ===== */

const REGION_COLORS = ['#ef4444', '#60a5fa', '#22c55e', '#f59e0b'];

function renderHitRegions(data) {
    const players = data?.players ?? [];
    if (players.length === 0) return;
    const totals = players.reduce(
        (a, p) => ({ head: a.head + p.head, arms: a.arms + p.arms, body: a.body + p.body, legs: a.legs + p.legs }),
        { head: 0, arms: 0, body: 0, legs: 0 }
    );
    const total = totals.head + totals.arms + totals.body + totals.legs;
    if (total === 0) return;

    const regions = [
        { label: 'Head', count: totals.head, color: REGION_COLORS[0] },
        { label: 'Arms', count: totals.arms, color: REGION_COLORS[1] },
        { label: 'Body', count: totals.body, color: REGION_COLORS[2] },
        { label: 'Legs', count: totals.legs, color: REGION_COLORS[3] },
    ];
    const maxR = Math.max(...regions.map(r => r.count), 1);
    const totalDmg = players.reduce((a, p) => a + (p.total_damage || 0), 0);

    const chartEl = document.getElementById('hit-regions-chart');
    if (chartEl) {
        chartEl.textContent = '';
        const barsRow = document.createElement('div');
        barsRow.className = 'flex items-end gap-1 h-28 justify-center';
        regions.forEach(r => {
            const pct = ((r.count / total) * 100).toFixed(1);
            const barH = Math.max((r.count / maxR) * 100, 4);
            const col = document.createElement('div');
            col.className = 'flex flex-col items-center gap-1 flex-1 max-w-16';
            const pctSpan = document.createElement('span');
            pctSpan.className = 'text-[11px] font-mono text-slate-300';
            pctSpan.textContent = `${pct}%`;
            const bar = document.createElement('div');
            bar.className = 'w-full rounded-t';
            bar.style.height = `${barH}%`;
            bar.style.background = r.color;
            bar.style.opacity = '0.85';
            const lbl = document.createElement('span');
            lbl.className = 'text-[11px] text-slate-400';
            lbl.textContent = r.label;
            col.append(pctSpan, bar, lbl);
            barsRow.appendChild(col);
        });
        const summary = document.createElement('div');
        summary.className = 'text-center text-[11px] text-slate-500 mt-2';
        summary.textContent = `${formatNumber(total)} hits \u00B7 ${formatNumber(totalDmg)} damage tracked`;
        chartEl.append(barsRow, summary);
    }

    const barsEl = document.getElementById('hit-regions-bars');
    if (barsEl) {
        barsEl.textContent = '';
        regions.forEach(r => {
            const pct = ((r.count / total) * 100).toFixed(1);
            barsEl.appendChild(_buildBarRow(r.label, r.count, pct, (r.count / maxR) * 100, r.color));
        });
    }
}

function renderHeadshotRates(data) {
    renderLeaderList('hit-regions-headshot-leaders',
        data?.leaders?.slice(0, 15) ?? [],
        (row) => {
            const pct = row.headshot_pct != null ? `${row.headshot_pct.toFixed(1)}%` : '--';
            return `${pct} — ${row.head_hits || 0}H / ${row.total_hits || 0} total`;
        },
        'No headshot data yet'
    );
}

/* ===== v5.2 Movement Stats ===== */

function renderMovementStats(data) {
    const players = data?.players ?? [];
    if (players.length === 0) return;

    const totals = players.reduce((a, p) => ({
        distance: a.distance + (p.total_distance || 0),
        alive: a.alive + (p.alive_sec || 0),
        sprint: a.sprint + (p.sprint_sec || 0),
        standing: a.standing + (p.standing_sec || 0),
        crouching: a.crouching + (p.crouching_sec || 0),
        prone: a.prone + (p.prone_sec || 0),
    }), { distance: 0, alive: 0, sprint: 0, standing: 0, crouching: 0, prone: 0 });
    const totalStance = totals.standing + totals.crouching + totals.prone;

    const stanceEl = document.getElementById('movement-stance-bar');
    if (stanceEl && totalStance > 0) {
        const sp = (totals.standing / totalStance * 100).toFixed(0);
        const cp = (totals.crouching / totalStance * 100).toFixed(0);
        const pp = (totals.prone / totalStance * 100).toFixed(0);
        stanceEl.innerHTML = `
            <div class="text-[11px] font-bold text-slate-500 uppercase mb-1">Stance Distribution</div>
            <div class="h-4 rounded-full overflow-hidden flex mb-1">
                <div style="width:${sp}%;background:#60a5fa" title="Standing ${sp}%"></div>
                <div style="width:${cp}%;background:#f59e0b" title="Crouching ${cp}%"></div>
                <div style="width:${pp}%;background:#ef4444" title="Prone ${pp}%"></div>
            </div>
            <div class="flex justify-between text-[11px]">
                <span class="text-blue-400">Standing ${sp}%</span>
                <span class="text-amber-400">Crouch ${cp}%</span>
                <span class="text-red-400">Prone ${pp}%</span>
            </div>`;
    }

    const overEl = document.getElementById('movement-overview');
    if (overEl) {
        overEl.innerHTML = [
            { label: 'Total Distance', value: `${(totals.distance / 1000).toFixed(0)}K u`, cls: 'text-white' },
            { label: 'Alive Time', value: `${(totals.alive / 60).toFixed(0)}m`, cls: 'text-white' },
            { label: 'Sprint Time', value: `${(totals.sprint / 60).toFixed(1)}m`, cls: 'text-brand-cyan' },
        ].map(x => `<div class="text-center">
            <div class="text-[11px] font-bold text-slate-500 uppercase">${x.label}</div>
            <div class="text-lg font-black ${x.cls} mt-1">${x.value}</div>
        </div>`).join('');
    }

    renderLeaderList('movement-distance-leaders',
        [...players].sort((a, b) => (b.total_distance || 0) - (a.total_distance || 0)).slice(0, 8),
        (row) => `${((row.total_distance || 0) / 1000).toFixed(1)}K u — ${(row.avg_speed || 0).toFixed(0)} u/s`,
        'No movement data yet'
    );

    renderLeaderList('movement-speed-leaders',
        [...players].sort((a, b) => (b.max_peak_speed || 0) - (a.max_peak_speed || 0)).slice(0, 8),
        (row) => `${(row.max_peak_speed || 0).toFixed(0)} u/s — avg ${(row.avg_peak_speed || 0).toFixed(0)}`,
        'No speed data yet'
    );

    renderLeaderList('movement-sprint-leaders',
        [...players].sort((a, b) => (b.avg_sprint_pct || 0) - (a.avg_sprint_pct || 0)).slice(0, 8),
        (row) => `${(row.avg_sprint_pct || 0).toFixed(1)}% — ${(row.sprint_sec || 0).toFixed(0)}s total`,
        'No sprint data yet'
    );

    renderLeaderList('movement-postspawn-leaders',
        [...players].sort((a, b) => (b.avg_post_spawn_dist || 0) - (a.avg_post_spawn_dist || 0)).slice(0, 5),
        (row) => `${(row.avg_post_spawn_dist || 0).toFixed(0)} u`,
        'No post-spawn data yet'
    );
}

/* ===== v5.2 Proximity Composite Scores ===== */

const SCORE_COLORS = { prox_combat: '#ef4444', prox_team: '#3b82f6', prox_gamesense: '#a855f7', prox_overall: '#22d3ee' };

function renderProxScores(data, formula) {
    const players = data?.players ?? [];
    const listEl = document.getElementById('prox-scores-list');
    if (!listEl) return;
    if (players.length === 0) {
        listEl.innerHTML = '<div class="text-[11px] text-slate-500">No proximity score data yet.</div>';
        return;
    }

    const subtitleEl = document.getElementById('prox-scores-subtitle');
    if (subtitleEl) {
        const catCount = formula?.categories ? Object.keys(formula.categories).length : 3;
        const metricCount = formula?.categories
            ? Object.values(formula.categories).reduce((a, c) => a + Object.keys(c.metrics).length, 0) : 18;
        subtitleEl.textContent = `Composite rating from ${catCount} categories, ${metricCount} metrics — v${data.version || '1.0'}`;
    }

    // Header row
    const hdr = `<div class="flex items-center gap-1 text-[11px] text-slate-500 font-bold uppercase mb-2 px-1">
        <span class="w-6">#</span><span class="flex-1">Player</span>
        <span class="w-14 text-right" style="color:${SCORE_COLORS.prox_combat}">Combat</span>
        <span class="w-14 text-right" style="color:${SCORE_COLORS.prox_team}">Team</span>
        <span class="w-14 text-right" style="color:${SCORE_COLORS.prox_gamesense}">Sense</span>
        <span class="w-16 text-right" style="color:${SCORE_COLORS.prox_overall}">Overall</span>
    </div>`;

    const rows = players.map(p => {
        const name = stripEtColors(p.name || '');
        return `<div class="flex items-center gap-1 text-[11px] px-1 py-1 rounded hover:bg-white/5 cursor-pointer prox-score-row" data-guid="${escapeHtml(p.guid)}">
            <span class="w-6 text-slate-600 font-mono">${p.rank}</span>
            <span class="flex-1 truncate text-slate-200">${escapeHtml(name)}</span>
            <span class="w-14 text-right font-mono font-bold" style="color:${SCORE_COLORS.prox_combat}">${p.prox_combat.toFixed(1)}</span>
            <span class="w-14 text-right font-mono font-bold" style="color:${SCORE_COLORS.prox_team}">${p.prox_team.toFixed(1)}</span>
            <span class="w-14 text-right font-mono font-bold" style="color:${SCORE_COLORS.prox_gamesense}">${p.prox_gamesense.toFixed(1)}</span>
            <span class="w-16 text-right font-mono font-black" style="color:${SCORE_COLORS.prox_overall}">${p.prox_overall.toFixed(1)}</span>
        </div>
        <div class="prox-score-detail hidden ml-6 mb-2 p-3 rounded-lg bg-slate-800/40 border border-white/5" data-guid="${escapeHtml(p.guid)}">
            ${p.prox_radar ? `<div class="flex gap-4 mb-2">${p.prox_radar.map(a => `<div class="text-center"><div class="text-[10px] text-slate-500">${escapeHtml(a.label)}</div><div class="text-sm font-bold text-white">${a.value.toFixed(0)}</div></div>`).join('')}</div>` : ''}
            ${p.breakdown ? `<div class="grid grid-cols-1 sm:grid-cols-3 gap-3">${Object.entries(p.breakdown).map(([catKey, metrics]) => {
                const catLabel = formula?.categories?.[catKey]?.label ?? catKey;
                const color = SCORE_COLORS[catKey] || '#22d3ee';
                return `<div>
                    <div class="text-[11px] font-bold uppercase mb-1" style="color:${color}">${escapeHtml(catLabel)}</div>
                    ${Object.entries(metrics).map(([, m]) => `<div class="flex items-center gap-1 text-[10px]">
                        <span class="text-slate-500 w-20 truncate">${escapeHtml(m.label)}</span>
                        <div class="flex-1 h-1.5 rounded-full bg-slate-700 overflow-hidden"><div class="h-full rounded-full bg-cyan-500/60" style="width:${(m.percentile * 100)}%"></div></div>
                        <span class="text-slate-400 font-mono w-6 text-right">${(m.percentile * 100).toFixed(0)}</span>
                    </div>`).join('')}
                </div>`;
            }).join('')}</div>` : ''}
            <div class="text-[10px] text-slate-600 mt-2">${p.engagements || 0} engagements, ${p.tracks || 0} tracks</div>
        </div>`;
    }).join('');

    listEl.innerHTML = hdr + rows;

    // Formula panel
    const formulaEl = document.getElementById('prox-scores-formula');
    if (formulaEl && formula?.categories) {
        formulaEl.innerHTML = `
            <div class="text-[11px] font-bold uppercase tracking-widest text-slate-400 mb-2">Scoring Formula v${data.version || '1.0'}</div>
            <div class="text-[11px] text-slate-500 mb-3">Each metric is ranked as a percentile (0-100) across all players with ${formula.min_engagements || 30}+ engagements, then weighted.
                Overall = ${Object.entries(formula.category_weights || {}).map(([k, w]) => {
                    const cat = formula.categories[k];
                    return cat ? `${cat.label} ${(w * 100).toFixed(0)}%` : '';
                }).filter(Boolean).join(' + ')}.
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
                ${Object.entries(formula.categories).map(([catKey, cat]) => {
                    const color = SCORE_COLORS[catKey] || '#22d3ee';
                    const weight = formula.category_weights?.[catKey];
                    return `<div>
                        <div class="text-[11px] font-bold mb-1" style="color:${color}">${escapeHtml(cat.label)} <span class="font-normal text-slate-500">(${weight ? (weight * 100).toFixed(0) : '?'}%)</span></div>
                        <div class="text-[10px] text-slate-500 mb-1">${escapeHtml(cat.description || '')}</div>
                        ${Object.entries(cat.metrics).map(([, m]) => `<div class="flex items-center justify-between text-[10px]">
                            <span class="text-slate-400">${escapeHtml(m.label)}${m.invert ? ' *' : ''}</span>
                            <span class="text-slate-600 font-mono">${(m.weight * 100).toFixed(0)}%</span>
                        </div>`).join('')}
                    </div>`;
                }).join('')}
            </div>
            <div class="text-[10px] text-slate-600 mt-2">* Inverted: lower = better (e.g. faster reaction scores higher)</div>`;
    }
}

/* ===== v5.2 Danger Zones ===== */

const CLASS_COLORS_V52 = { SOLDIER: '#ef4444', MEDIC: '#22c55e', ENGINEER: '#f59e0b', FIELDOPS: '#60a5fa', COVERTOPS: '#a855f7' };

function renderDangerZones(mapName, classFilter) {
    if (!mapName) return;
    const params = buildScopeParams({ extra: { map_name: mapName } });
    if (classFilter) params.set('victim_class', classFilter);
    fetchJSON(`${API_BASE}/proximity/combat-positions/danger-zones?${params}`).then(data => {
        const canvas = document.getElementById('danger-zones-canvas');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const W = canvas.width, H = canvas.height;
        ctx.clearRect(0, 0, W, H);
        ctx.fillStyle = '#0f172a';
        ctx.fillRect(0, 0, W, H);
        const zones = data?.zones ?? [];
        const gridSize = data?.grid_size ?? 512;
        const statsEl = document.getElementById('danger-zones-stats');
        const totalDeaths = zones.reduce((a, z) => a + z.deaths, 0);
        if (statsEl) statsEl.textContent = zones.length > 0
            ? `${formatNumber(totalDeaths)} deaths across ${zones.length} zones on ${escapeHtml(mapName)}`
            : `No danger zone data for ${escapeHtml(mapName)}`;
        if (zones.length === 0) {
            ctx.fillStyle = '#64748b'; ctx.font = '12px monospace'; ctx.textAlign = 'center';
            ctx.fillText('No danger zone data for this map', W / 2, H / 2);
            return;
        }
        const maxDeaths = Math.max(...zones.map(z => z.deaths), 1);
        for (const zone of zones) {
            const nx = (zone.x / gridSize) * W, ny = (zone.y / gridSize) * H;
            const intensity = zone.deaths / maxDeaths;
            const radius = 6 + intensity * 18;
            const classes = zone.classes || {};
            const dominant = Object.entries(classes).sort((a, b) => b[1] - a[1])[0];
            const baseColor = (dominant && CLASS_COLORS_V52[dominant[0]]) || '#64748b';
            const alpha = 0.25 + intensity * 0.55;
            const r = parseInt(baseColor.slice(1, 3), 16), g = parseInt(baseColor.slice(3, 5), 16), b = parseInt(baseColor.slice(5, 7), 16);
            ctx.beginPath(); ctx.arc(nx, ny, radius, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(${r},${g},${b},${alpha})`; ctx.fill();
            if (intensity > 0.3) {
                ctx.fillStyle = 'rgba(255,255,255,0.7)'; ctx.font = '9px monospace'; ctx.textAlign = 'center';
                ctx.fillText(String(zone.deaths), nx, ny + 3);
            }
        }
    }).catch(() => {});
}

/* ===== v5.2 Combat Heatmap ===== */

function renderCombatHeatmap(mapName, perspective) {
    if (!mapName) return;
    const params1 = buildScopeParams({ extra: { map_name: mapName, perspective: perspective || 'kills' } });
    const params2 = buildScopeParams({ extra: { map_name: mapName, limit: 200 } });
    Promise.allSettled([
        fetchJSON(`${API_BASE}/proximity/combat-positions/heatmap?${params1}`),
        fetchJSON(`${API_BASE}/proximity/combat-positions/kill-lines?${params2}`)
    ]).then(([heatRes, lineRes]) => {
        const canvas = document.getElementById('combat-heatmap-canvas');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const W = canvas.width, H = canvas.height;
        ctx.clearRect(0, 0, W, H); ctx.fillStyle = '#0f172a'; ctx.fillRect(0, 0, W, H);
        const hotzones = heatRes.status === 'fulfilled' ? (heatRes.value.hotzones ?? []) : [];
        const killLines = lineRes.status === 'fulfilled' ? (lineRes.value.lines ?? []) : [];
        const gridSize = heatRes.status === 'fulfilled' ? (heatRes.value.grid_size ?? 512) : 512;
        if (hotzones.length === 0 && killLines.length === 0) {
            ctx.fillStyle = '#64748b'; ctx.font = '12px monospace'; ctx.textAlign = 'center';
            ctx.fillText('No combat data for this map yet', W / 2, H / 2);
            return;
        }
        const maxCount = Math.max(...hotzones.map(h => h.count), 1);
        for (const hz of hotzones) {
            const nx = (hz.x / gridSize) * W, ny = (hz.y / gridSize) * H;
            const intensity = hz.count / maxCount;
            const radius = 4 + intensity * 16;
            const alpha = 0.2 + intensity * 0.6;
            ctx.beginPath(); ctx.arc(nx, ny, radius, 0, Math.PI * 2);
            ctx.fillStyle = perspective === 'deaths' ? `rgba(96,165,250,${alpha})` : `rgba(239,68,68,${alpha})`;
            ctx.fill();
        }
        for (const line of killLines) {
            const ax = (line.ax / gridSize) * W, ay = (line.ay / gridSize) * H;
            const vx = (line.vx / gridSize) * W, vy = (line.vy / gridSize) * H;
            ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(vx, vy);
            ctx.strokeStyle = line.attacker_team === 'AXIS' ? 'rgba(239,68,68,0.15)' : 'rgba(96,165,250,0.15)';
            ctx.lineWidth = 1; ctx.stroke();
        }
    }).catch(() => {});
}

/* ===== v5.2 Leaderboard Tabs ===== */

const LB_TABS = [
    { key: 'power', label: 'Power Rating' },
    { key: 'spawn', label: 'Spawn Timing' },
    { key: 'crossfire', label: 'Crossfire' },
    { key: 'trades', label: 'Trade Kills' },
    { key: 'reactions', label: 'Reactions' },
    { key: 'survivors', label: 'Survivors' },
    { key: 'movement', label: 'Movement' },
    { key: 'focus_fire', label: 'Focus Fire' },
];
let lbActiveTab = 'power';
let lbRangeDays = 30;

function renderLeaderboardTabs() {
    const tabsEl = document.getElementById('leaderboard-tabs');
    if (!tabsEl) return;
    tabsEl.innerHTML = LB_TABS.map(t => {
        const active = t.key === lbActiveTab;
        return `<button class="lb-tab-btn text-[10px] font-bold px-3 py-1 rounded transition ${active
            ? 'bg-brand-cyan/10 text-brand-cyan border border-brand-cyan/40'
            : 'bg-slate-800 text-slate-500 border border-white/10 hover:text-slate-300'}" data-tab="${t.key}">${t.label}</button>`;
    }).join('');
}

function loadLeaderboardData() {
    const contentEl = document.getElementById('leaderboard-content');
    if (!contentEl) return;
    contentEl.innerHTML = '<div class="text-[11px] text-slate-500">Loading...</div>';
    const lbParams = buildScopeParams({ extra: { category: lbActiveTab, limit: 10 } });
    lbParams.set('range_days', String(lbRangeDays));
    fetchJSON(`${API_BASE}/proximity/leaderboards?${lbParams}`).then(data => {
        const entries = data?.entries ?? [];
        if (entries.length === 0) {
            contentEl.innerHTML = '<div class="text-[11px] text-slate-500">No leaderboard data yet.</div>';
            return;
        }
        contentEl.innerHTML = entries.map((e, i) => {
            const name = lbActiveTab === 'crossfire'
                ? `${stripEtColors(e.name)} + ${stripEtColors(e.partner_name || '?')}`
                : stripEtColors(e.name);
            let val = String(e.value);
            if (lbActiveTab === 'spawn' || lbActiveTab === 'focus_fire') val = Number(e.value).toFixed(3);
            else if (lbActiveTab === 'reactions') val = `${e.value}ms`;
            else if (lbActiveTab === 'survivors') val = `${e.value}%`;
            else if (lbActiveTab === 'movement') val = `${e.value} u/s`;
            return `<div class="flex items-center justify-between text-[11px] text-slate-300 py-0.5">
                <span><span class="font-bold ${i < 3 ? 'text-brand-amber' : 'text-slate-600'} mr-2">#${i + 1}</span>${escapeHtml(name)}</span>
                <span class="text-right text-slate-500">${val}</span>
            </div>`;
        }).join('');
    }).catch(() => { if (contentEl) contentEl.innerHTML = '<div class="text-[11px] text-slate-500">Failed to load.</div>'; });
}

/* ===== v5.2 Weapon Accuracy ===== */

function renderWeaponAccuracy(data) {
    const leaders = data?.leaders ?? [];
    renderLeaderList('weapon-accuracy-leaders', leaders.slice(0, 8), (row) => {
        const acc = row.accuracy != null ? `${row.accuracy}%` : '--';
        const detail = `${formatNumber(row.hits || 0)}/${formatNumber(row.shots || 0)} shots · ${formatNumber(row.kills || 0)}K · ${formatNumber(row.headshots || 0)}HS`;
        return `<span class="text-brand-amber">${acc}</span> <span class="text-slate-500 text-[10px]">${detail}</span>`;
    }, 'No weapon accuracy data yet');
}

/* ===== v5.2 Revives ===== */

function renderRevives(data) {
    const summaryEl = document.getElementById('revive-summary');
    const leadersEl = document.getElementById('revive-leaders');
    if (!data || data.status === 'error') {
        if (leadersEl) leadersEl.innerHTML = '<div class="text-[11px] text-slate-500">No revive data available.</div>';
        return;
    }
    const summary = data.summary || {};
    if (summaryEl) {
        const items = [
            { label: 'Total Revives', value: formatNumber(summary.total_revives || 0), cls: 'text-emerald-400' },
            { label: 'Under Fire', value: `${summary.under_fire_pct || 0}%`, cls: 'text-red-400' },
            { label: 'Avg Enemy Dist', value: `${formatNumber(Math.round(summary.avg_enemy_distance || 0))}u`, cls: 'text-cyan-400' },
        ];
        summaryEl.innerHTML = items.map(item =>
            `<div class="bg-slate-800/60 rounded-lg p-3 text-center">
                <div class="text-[10px] text-slate-500 uppercase">${item.label}</div>
                <div class="text-lg font-bold ${item.cls}">${item.value}</div>
            </div>`
        ).join('');
    }
    renderLeaderList('revive-leaders', (data.leaders || []).slice(0, 8), (row) => {
        const revives = formatNumber(row.revives || 0);
        const risky = row.under_fire_count != null ? ` · ${row.under_fire_count} risky` : '';
        return `<span class="text-emerald-400">${revives} revives</span><span class="text-slate-500 text-[10px]">${risky}</span>`;
    }, 'No revive leaders yet');
}

/* ===== v5.2 Event Bindings ===== */

function bindV52PanelEvents() {
    // Prox scores expand/collapse
    document.querySelectorAll('.prox-score-row').forEach(btn => {
        btn.onclick = () => {
            const guid = btn.dataset.guid;
            document.querySelectorAll('.prox-score-detail').forEach(d => {
                if (d.dataset.guid === guid) d.classList.toggle('hidden');
                else d.classList.add('hidden');
            });
        };
    });

    // Formula toggle
    const formulaBtn = document.getElementById('prox-scores-formula-btn');
    const formulaEl = document.getElementById('prox-scores-formula');
    if (formulaBtn && formulaEl) {
        formulaBtn.onclick = () => {
            const show = formulaEl.classList.toggle('hidden');
            formulaBtn.classList.toggle('bg-brand-emerald/10', !show);
            formulaBtn.classList.toggle('text-brand-emerald', !show);
            formulaBtn.classList.toggle('border-brand-emerald/40', !show);
        };
    }

    // Prox scores range
    document.querySelectorAll('.prox-scores-range-btn').forEach(btn => {
        btn.onclick = () => {
            document.querySelectorAll('.prox-scores-range-btn').forEach(b => {
                b.className = 'prox-scores-range-btn text-[10px] px-2 py-1 rounded bg-slate-800 text-slate-500 border border-white/10';
            });
            btn.className = 'prox-scores-range-btn text-[10px] px-2 py-1 rounded bg-brand-cyan/10 text-brand-cyan border border-brand-cyan/40';
            const scoreParams = buildScopeParams({ extra: { min_engagements: 30 } });
            scoreParams.set('range_days', btn.dataset.days);
            fetchJSON(`${API_BASE}/proximity/prox-scores?${scoreParams}`).then(d => {
                fetchJSON(scopedUrl('/proximity/prox-scores/formula', { includeRange: false })).then(f => renderProxScores(d, f)).catch(() => renderProxScores(d, null));
            }).catch(() => {});
        };
    });

    // Danger zones
    const dzMapInput = document.getElementById('danger-zones-map');
    const dzClassSelect = document.getElementById('danger-zones-class');
    const dzLoad = () => renderDangerZones(dzMapInput?.value || '', dzClassSelect?.value || '');
    if (dzMapInput) {
        dzMapInput.onchange = dzLoad;
        dzMapInput.addEventListener('keyup', (e) => { if (e.key === 'Enter') dzLoad(); });
    }
    if (dzClassSelect) dzClassSelect.onchange = dzLoad;

    // Combat heatmap
    const hmMapInput = document.getElementById('combat-heatmap-map');
    const hmPerspective = document.getElementById('combat-heatmap-perspective');
    const hmLoad = () => renderCombatHeatmap(hmMapInput?.value || '', hmPerspective?.value || 'kills');
    if (hmMapInput) {
        hmMapInput.onchange = hmLoad;
        hmMapInput.addEventListener('keyup', (e) => { if (e.key === 'Enter') hmLoad(); });
    }
    if (hmPerspective) hmPerspective.onchange = hmLoad;

    // Leaderboard tabs
    renderLeaderboardTabs();
    loadLeaderboardData();
    document.getElementById('leaderboard-tabs')?.addEventListener('click', (e) => {
        const btn = e.target.closest('.lb-tab-btn');
        if (!btn) return;
        lbActiveTab = btn.dataset.tab;
        renderLeaderboardTabs();
        loadLeaderboardData();
    });
    document.querySelectorAll('.lb-range-btn').forEach(btn => {
        btn.onclick = () => {
            lbRangeDays = Number(btn.dataset.days);
            document.querySelectorAll('.lb-range-btn').forEach(b => {
                b.className = 'lb-range-btn text-[10px] px-2 py-1 rounded bg-slate-800 text-slate-500 border border-white/10';
            });
            btn.className = 'lb-range-btn text-[10px] px-2 py-1 rounded bg-brand-cyan/10 text-brand-cyan border border-brand-cyan/40';
            loadLeaderboardData();
        };
    });

    if (typeof lucide !== 'undefined') lucide.createIcons();
}

// ===== v6 CARRIER INTELLIGENCE RENDERERS =====

function renderCarrierIntel(data) {
    if (!data || data.status === 'error') return;

    // Summary stats
    const summaryEl = document.getElementById('carrier-summary');
    if (summaryEl && data.summary) {
        const s = data.summary;
        summaryEl.innerHTML = [
            { label: 'Total Carries', value: s.total_carries, cls: 'text-white' },
            { label: 'Secures', value: `${s.total_secures} (${s.secure_rate}%)`, cls: 'text-brand-emerald' },
            { label: 'Avg Distance', value: `${s.avg_distance}u`, cls: 'text-brand-cyan' },
        ].map(x => `<div class="text-center">
            <div class="text-[11px] font-bold text-slate-500 uppercase">${x.label}</div>
            <div class="text-lg font-black ${x.cls} mt-1">${x.value}</div>
        </div>`).join('');
    }

    // Carrier leaderboard
    const leadersEl = document.getElementById('carrier-leaders');
    if (leadersEl && data.carriers && data.carriers.length > 0) {
        leadersEl.innerHTML = data.carriers.map((c, i) => {
            const name = escapeHtml(c.name || c.guid?.substring(0, 8) || '?');
            return `<div class="text-xs text-slate-300 py-0.5">
                <span class="font-bold ${i < 3 ? 'text-brand-amber' : 'text-slate-600'}">#${i + 1}</span>
                ${name} — <span class="text-brand-emerald">${c.secures}</span>/${c.carries} secure
                (${c.secure_rate}%) · ${formatNumber(c.total_distance)}u · eff ${(c.avg_efficiency * 100).toFixed(0)}%
            </div>`;
        }).join('');
    } else if (leadersEl) {
        leadersEl.innerHTML = '<div class="text-[11px] text-slate-500">No carrier data yet.</div>';
    }

    // Event log
    const logEl = document.getElementById('carrier-event-log');
    if (logEl && data.events && data.events.length > 0) {
        const outcomeIcons = { secured: '+', killed: 'X', dropped: 'D', returned: 'R', round_end: 'E', disconnected: 'DC' };
        const outcomeColors = { secured: 'text-brand-emerald', killed: 'text-brand-rose', dropped: 'text-slate-400', round_end: 'text-slate-500' };
        logEl.innerHTML = data.events.map(e => {
            const icon = outcomeIcons[e.outcome] || '?';
            const color = outcomeColors[e.outcome] || 'text-slate-400';
            const name = escapeHtml(e.carrier_name || '?');
            const dur = (e.duration_ms / 1000).toFixed(1);
            const eff = (e.efficiency * 100).toFixed(0);
            let detail = `[${icon}] ${e.outcome} · ${formatNumber(e.carry_distance)}u (${eff}%) · ${dur}s`;
            if (e.outcome === 'killed' && e.killer_name) {
                detail += ` by ${escapeHtml(e.killer_name)}`;
            }
            return `<div class="flex justify-between text-xs py-0.5">
                <span>${name} <span class="text-slate-500">(${escapeHtml(e.carrier_team)})</span> on <span class="text-slate-400">${escapeHtml(e.map_name)}</span></span>
                <span class="${color}">${detail}</span>
            </div>`;
        }).join('');
    } else if (logEl) {
        logEl.innerHTML = '<div class="text-[11px] text-slate-500">No carrier events yet.</div>';
    }
}

function renderCarrierKillers(data) {
    if (!data || data.status === 'error') return;
    const el = document.getElementById('carrier-killer-leaders');
    if (!el) return;

    if (!data.killers || data.killers.length === 0) {
        el.innerHTML = '<div class="text-[11px] text-slate-500">No carrier kill data yet.</div>';
        return;
    }

    el.innerHTML = data.killers.map((k, i) => {
        const name = escapeHtml(k.name || k.guid?.substring(0, 8) || '?');
        return `<div class="text-xs text-slate-300 py-0.5">
            <span class="font-bold ${i < 3 ? 'text-brand-rose' : 'text-slate-600'}">#${i + 1}</span>
            ${name} — <span class="text-brand-rose font-bold">${k.carrier_kills}</span> carrier kills
            · avg stopped at ${formatNumber(k.avg_distance_stopped)}u
        </div>`;
    }).join('');
}

// ──────────── v6 Phase 1.5: Flag Returns ────────────
function renderFlagReturns(data) {
    if (!data || data.status !== 'ok') return;

    // Summary
    const summaryEl = document.getElementById('returns-summary');
    if (summaryEl && data.summary) {
        const s = data.summary;
        summaryEl.innerHTML = `
            <div class="bg-slate-800/50 rounded-lg p-3 text-center">
                <div class="text-lg font-bold text-white">${s.total_returns || 0}</div>
                <div class="text-[10px] text-slate-400 uppercase">Total Returns</div>
            </div>
            <div class="bg-slate-800/50 rounded-lg p-3 text-center">
                <div class="text-lg font-bold text-brand-cyan">${s.avg_delay_ms ? (s.avg_delay_ms / 1000).toFixed(1) + 's' : '--'}</div>
                <div class="text-[10px] text-slate-400 uppercase">Avg Return Time</div>
            </div>`;
    }

    // Returner leaderboard
    const leadersEl = document.getElementById('returns-leaders');
    if (leadersEl && data.returners && data.returners.length > 0) {
        leadersEl.innerHTML = data.returners.map((r, i) => {
            const name = escapeHtml(r.name || 'Unknown');
            const avgDelay = r.avg_delay_ms ? (r.avg_delay_ms / 1000).toFixed(1) + 's' : '--';
            return `<div class="flex justify-between items-center py-0.5 ${i < 3 ? 'text-brand-cyan' : 'text-slate-400'}">
                <span>#${i + 1} ${name}</span>
                <span>${r.returns} returns (avg ${avgDelay})</span>
            </div>`;
        }).join('');
    }
}

// ──────────── v6 Phase 2: Vehicle Progress ────────────
function renderVehicleProgress(data) {
    if (!data || data.status !== 'ok') return;

    const el = document.getElementById('vehicle-progress');
    if (!el || !data.vehicles || data.vehicles.length === 0) return;

    el.innerHTML = data.vehicles.map(v => {
        const name = escapeHtml(v.vehicle_name || 'Unknown');
        const map = escapeHtml(v.map_name || '');
        const dist = v.total_distance ? formatNumber(Math.round(v.total_distance)) + 'u' : '0u';
        const destroyed = v.destroyed_count > 0 ? ` | destroyed: ${v.destroyed_count}x` : '';
        return `<div class="flex justify-between items-center py-0.5">
            <span class="text-brand-purple">${name} <span class="text-slate-500">(${map} R${v.round_number || '?'})</span></span>
            <span class="text-slate-300">${dist}${destroyed}</span>
        </div>`;
    }).join('');
}

// ──────────── v6 Phase 2: Escort Leaders ────────────
function renderEscortLeaders(data) {
    if (!data || data.status !== 'ok') return;

    const el = document.getElementById('escort-leaders');
    if (!el || !data.escorts || data.escorts.length === 0) return;

    el.innerHTML = data.escorts.map((e, i) => {
        const name = escapeHtml(e.name || 'Unknown');
        const dist = e.total_credit_distance ? formatNumber(Math.round(e.total_credit_distance)) + 'u' : '0u';
        const mountedSec = e.total_mounted_ms ? (e.total_mounted_ms / 1000).toFixed(0) + 's mounted' : '';
        const proxSec = e.total_proximity_ms ? (e.total_proximity_ms / 1000).toFixed(0) + 's nearby' : '';
        const timeInfo = [mountedSec, proxSec].filter(Boolean).join(', ');
        return `<div class="flex justify-between items-center py-0.5 ${i < 3 ? 'text-brand-purple' : 'text-slate-400'}">
            <span>#${i + 1} ${name}</span>
            <span>${dist} ${timeInfo ? '(' + timeInfo + ')' : ''}</span>
        </div>`;
    }).join('');
}

// ──────────── v6 Phase 3: Engineer Intelligence ────────────
function renderEngineerIntel(data) {
    if (!data || data.status !== 'ok') return;

    // Engineer leaderboard
    const leadersEl = document.getElementById('engineer-leaders');
    if (leadersEl && data.engineers && data.engineers.length > 0) {
        leadersEl.innerHTML = data.engineers.map((eng, i) => {
            const name = escapeHtml(eng.name || 'Unknown');
            const parts = [];
            if (eng.plants > 0) parts.push(`${eng.plants} plant`);
            if (eng.defuses > 0) parts.push(`${eng.defuses} defuse`);
            if (eng.destructions > 0) parts.push(`${eng.destructions} destroy`);
            if (eng.constructions > 0) parts.push(`${eng.constructions} build`);
            return `<div class="flex justify-between items-center py-0.5 ${i < 3 ? 'text-brand-green' : 'text-slate-400'}">
                <span>#${i + 1} ${name}</span>
                <span>${parts.join(' | ') || eng.total_events + ' events'}</span>
            </div>`;
        }).join('');
    }

    // Event log
    const logEl = document.getElementById('construction-event-log');
    if (logEl && data.events && data.events.length > 0) {
        const typeIcons = {
            dynamite_plant: { icon: 'P', color: 'text-brand-rose' },
            dynamite_defuse: { icon: 'D', color: 'text-brand-cyan' },
            objective_destroyed: { icon: 'X', color: 'text-red-400' },
            construction_complete: { icon: 'B', color: 'text-brand-green' },
        };
        logEl.innerHTML = data.events.map(ev => {
            const ti = typeIcons[ev.event_type] || { icon: '?', color: 'text-slate-400' };
            const name = escapeHtml(ev.player_name || 'Unknown');
            const track = ev.track_name ? escapeHtml(ev.track_name) : '';
            const map = escapeHtml(ev.map_name || '');
            return `<div class="flex items-center gap-2 py-0.5">
                <span class="font-mono font-bold ${ti.color} w-4 text-center">${ti.icon}</span>
                <span class="text-slate-300">${name}</span>
                <span class="text-slate-500">${track ? track + ' @ ' : ''}${map}</span>
            </div>`;
        }).join('');
    }
}

function renderObjectiveRuns(data) {
    const summaryEl = document.getElementById('objective-run-summary');
    const leadersEl = document.getElementById('objective-runners-leaders');
    const logEl = document.getElementById('objective-runs-log');

    if (!data || !data.summary) {
        if (summaryEl) summaryEl.innerHTML = '<span class="text-slate-600">No objective run data available</span>';
        if (leadersEl) leadersEl.innerHTML = '';
        if (logEl) logEl.innerHTML = '';
        return;
    }

    // Summary bar
    const s = data.summary;
    if (summaryEl) {
        summaryEl.innerHTML = `
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div class="bg-white/5 rounded-lg p-3 text-center">
                    <div class="text-2xl font-bold text-white">${s.total_runs || 0}</div>
                    <div class="text-xs text-slate-400">Total Runs</div>
                </div>
                <div class="bg-white/5 rounded-lg p-3 text-center">
                    <div class="text-2xl font-bold text-emerald-400">${s.total_solo || 0}</div>
                    <div class="text-xs text-slate-400">Solo</div>
                </div>
                <div class="bg-white/5 rounded-lg p-3 text-center">
                    <div class="text-2xl font-bold text-blue-400">${s.total_team_effort || 0}</div>
                    <div class="text-xs text-slate-400">Team Effort</div>
                </div>
                <div class="bg-white/5 rounded-lg p-3 text-center">
                    <div class="text-2xl font-bold text-red-400">${s.total_denied || 0}</div>
                    <div class="text-xs text-slate-400">Denied</div>
                </div>
            </div>
            ${s.most_active_objective ? `<div class="mt-2 text-xs text-slate-500">Most targeted: <span class="text-slate-300">${escapeHtml(s.most_active_objective)}</span> | Avg efficiency: <span class="text-slate-300">${((s.avg_path_efficiency || 0) * 100).toFixed(0)}%</span></div>` : ''}
        `;
    }

    // Leaders table
    if (leadersEl && data.objective_runners && data.objective_runners.length > 0) {
        const rows = data.objective_runners.map(r => `
            <tr class="border-b border-white/5">
                <td class="py-2 px-2 text-white text-sm">${escapeHtml(r.engineer_name)}</td>
                <td class="py-2 px-2 text-center text-sm">${r.total_runs}</td>
                <td class="py-2 px-2 text-center text-sm text-emerald-400">${r.solo_runs}</td>
                <td class="py-2 px-2 text-center text-sm text-blue-400">${r.team_effort_runs}</td>
                <td class="py-2 px-2 text-center text-sm text-red-400">${r.denied_runs}</td>
                <td class="py-2 px-2 text-center text-sm text-slate-400">${((r.avg_path_efficiency || 0) * 100).toFixed(0)}%</td>
            </tr>
        `).join('');
        leadersEl.innerHTML = `
            <table class="w-full text-left">
                <thead><tr class="text-xs text-slate-500 border-b border-white/10">
                    <th class="py-1 px-2">Player</th>
                    <th class="py-1 px-2 text-center">Runs</th>
                    <th class="py-1 px-2 text-center">Solo</th>
                    <th class="py-1 px-2 text-center">Team</th>
                    <th class="py-1 px-2 text-center">Denied</th>
                    <th class="py-1 px-2 text-center">Eff%</th>
                </tr></thead>
                <tbody>${rows}</tbody>
            </table>
        `;
    } else if (leadersEl) {
        leadersEl.innerHTML = '<span class="text-slate-600">No runners yet</span>';
    }

    // Recent runs log
    if (logEl && data.recent_runs && data.recent_runs.length > 0) {
        const typeColors = {
            'solo': 'text-emerald-400',
            'assisted': 'text-cyan-400',
            'team_effort': 'text-blue-400',
            'unopposed': 'text-slate-400',
            'contested_solo': 'text-yellow-400',
            'denied': 'text-red-400'
        };
        const actionIcons = {
            'dynamite_plant': '\uD83D\uDCA3',
            'objective_destroyed': '\uD83D\uDCA5',
            'construction_complete': '\uD83D\uDD27',
            'dynamite_defuse': '\uD83D\uDEE1\uFE0F',
            'approach_killed': '\u2620\uFE0F'
        };
        const items = data.recent_runs.slice(0, 15).map(r => {
            const icon = actionIcons[r.action_type] || '\u2753';
            const color = typeColors[r.run_type] || 'text-slate-400';
            const kills = r.self_kills + (r.team_kills || 0);
            const eff = ((r.path_efficiency || 0) * 100).toFixed(0);
            return `
                <div class="flex items-center justify-between py-1.5 border-b border-white/5">
                    <div class="flex items-center gap-2">
                        <span class="text-sm">${icon}</span>
                        <span class="text-sm text-white">${escapeHtml(r.engineer_name)}</span>
                        <span class="text-xs text-slate-500">${escapeHtml(r.track_name || '?')}</span>
                    </div>
                    <div class="flex items-center gap-3">
                        <span class="text-xs ${color} font-medium">${r.run_type}</span>
                        ${kills > 0 ? `<span class="text-xs text-slate-500">${kills} kills</span>` : ''}
                        <span class="text-xs text-slate-600">${eff}%</span>
                    </div>
                </div>
            `;
        }).join('');
        logEl.innerHTML = items;
    } else if (logEl) {
        logEl.innerHTML = '<span class="text-slate-600">No runs recorded yet</span>';
    }
}

// ========================================
// FOCUS FIRE
// ========================================
function renderFocusFire(data) {
    if (!data || data.status === 'error') return;
    const summary = data.summary || {};
    const summaryEl = document.getElementById('focus-fire-summary');
    if (summaryEl) {
        const items = [
            { label: 'Total Events', value: formatNumber(summary.total_events || 0), cls: 'text-rose-400' },
            { label: 'Avg Score', value: (summary.avg_score || 0).toFixed(2), cls: 'text-amber-400' },
            { label: 'Avg Attackers', value: (summary.avg_attackers || 0).toFixed(1), cls: 'text-cyan-400' },
        ];
        summaryEl.innerHTML = items.map(item =>
            `<div class="bg-slate-800/60 rounded-lg p-3 text-center">
                <div class="text-[10px] text-slate-500 uppercase">${item.label}</div>
                <div class="text-lg font-bold ${item.cls}">${item.value}</div>
            </div>`
        ).join('');
    }

    renderLeaderList('focus-fire-targets', (data.targets || []).slice(0, 8), (row) => {
        const times = formatNumber(row.times_focused || 0);
        const score = (row.avg_score != null) ? row.avg_score.toFixed(2) : '--';
        const dmg = formatNumber(row.total_damage_taken || 0);
        return `<span class="text-rose-400">${times}x focused</span> <span class="text-slate-500 text-[10px]">score ${score} · ${dmg} dmg</span>`;
    }, 'No focus fire data yet');

    const recentEl = document.getElementById('focus-fire-recent');
    if (recentEl && data.recent && data.recent.length > 0) {
        recentEl.innerHTML = data.recent.slice(0, 8).map(r => {
            const name = stripEtColors(r.target_name || '?');
            const score = (r.focus_score != null) ? r.focus_score.toFixed(2) : '--';
            return `<div class="flex items-center justify-between text-[11px]">
                <span class="text-slate-300">${escapeHtml(name)}</span>
                <span class="text-right">
                    <span class="text-rose-400">${r.attacker_count}v1</span>
                    <span class="text-slate-500 text-[10px]">${formatNumber(r.total_damage || 0)} dmg · ${score}</span>
                </span>
            </div>`;
        }).join('');
    } else if (recentEl) {
        recentEl.innerHTML = '<span class="text-slate-600">No events</span>';
    }
}

// ========================================
// OBJECTIVE FOCUS
// ========================================
function renderObjectiveFocus(data) {
    if (!data || data.status === 'error') return;
    const summary = data.summary || {};
    const summaryEl = document.getElementById('obj-focus-summary');
    if (summaryEl) {
        const items = [
            { label: 'Players Tracked', value: formatNumber(summary.unique_players || 0), cls: 'text-cyan-400' },
            { label: 'Objectives', value: formatNumber(summary.objectives_tracked || 0), cls: 'text-amber-400' },
            { label: 'Avg Time Near Obj', value: `${summary.avg_time_near_obj_s || 0}s`, cls: 'text-emerald-400' },
        ];
        summaryEl.innerHTML = items.map(item =>
            `<div class="bg-slate-800/60 rounded-lg p-3 text-center">
                <div class="text-[10px] text-slate-500 uppercase">${item.label}</div>
                <div class="text-lg font-bold ${item.cls}">${item.value}</div>
            </div>`
        ).join('');
    }

    renderLeaderList('obj-focus-players', (data.players || []).slice(0, 8), (row) => {
        const time = row.total_time_s != null ? `${formatNumber(Math.round(row.total_time_s))}s` : '--';
        const dist = row.avg_dist != null ? `${formatNumber(Math.round(row.avg_dist))}u` : '';
        const objs = row.objectives_played || 0;
        return `<span class="text-cyan-400">${time}</span> <span class="text-slate-500 text-[10px]">${dist} avg · ${objs} obj</span>`;
    }, 'No objective focus data yet');

    const objEl = document.getElementById('obj-focus-objectives');
    if (objEl && data.objectives && data.objectives.length > 0) {
        objEl.innerHTML = data.objectives.slice(0, 8).map(r => {
            const name = r.objective || '?';
            const map = r.map_name || '';
            return `<div class="flex items-center justify-between text-[11px]">
                <span class="text-slate-300">${escapeHtml(name)}</span>
                <span class="text-right">
                    <span class="text-cyan-400">${r.avg_time_s || 0}s</span>
                    <span class="text-slate-500 text-[10px]">${r.players} players · ${escapeHtml(map)}</span>
                </span>
            </div>`;
        }).join('');
    } else if (objEl) {
        objEl.innerHTML = '<span class="text-slate-600">No objectives tracked</span>';
    }
}

// ========================================
// SUPPORT SUMMARY
// ========================================
function renderSupportSummary(data) {
    if (!data || data.status === 'error') return;
    const summary = data.summary || {};
    const summaryEl = document.getElementById('support-summary-cards');
    if (summaryEl) {
        const items = [
            { label: 'Rounds Tracked', value: formatNumber(summary.total_rounds || 0), cls: 'text-slate-300' },
            { label: 'Avg Uptime', value: `${summary.avg_uptime_pct || 0}%`, cls: 'text-emerald-400' },
            { label: 'Best Uptime', value: `${summary.max_uptime_pct || 0}%`, cls: 'text-amber-400' },
        ];
        summaryEl.innerHTML = items.map(item =>
            `<div class="bg-slate-800/60 rounded-lg p-3 text-center">
                <div class="text-[10px] text-slate-500 uppercase">${item.label}</div>
                <div class="text-lg font-bold ${item.cls}">${item.value}</div>
            </div>`
        ).join('');
    }

    const mapsEl = document.getElementById('support-summary-maps');
    if (mapsEl && data.by_map && data.by_map.length > 0) {
        mapsEl.innerHTML = data.by_map.map(r => {
            const pct = r.avg_uptime_pct != null ? `${r.avg_uptime_pct}%` : '--';
            return `<div class="flex items-center justify-between text-[11px]">
                <span class="text-slate-300">${escapeHtml(r.map_name || '?')}</span>
                <span class="text-right">
                    <span class="text-emerald-400">${pct} avg</span>
                    <span class="text-slate-500 text-[10px]">${r.rounds} rounds · max ${r.max_uptime_pct || 0}%</span>
                </span>
            </div>`;
        }).join('');
    } else if (mapsEl) {
        mapsEl.innerHTML = '<span class="text-slate-600">No support data yet</span>';
    }
}

// ========================================
// COMBAT POSITION STATS
// ========================================
function renderCombatPositionStats(data) {
    if (!data || data.status === 'error') return;
    const summary = data.summary || {};
    const summaryEl = document.getElementById('combat-pos-summary');
    if (summaryEl) {
        const items = [
            { label: 'Tracked Kills', value: formatNumber(summary.total_kills || 0), cls: 'text-rose-400' },
            { label: 'Avg Kill Dist', value: `${formatNumber(Math.round(summary.avg_kill_distance || 0))}u`, cls: 'text-amber-400' },
            { label: 'Median Dist', value: `${formatNumber(Math.round(summary.median_kill_distance || 0))}u`, cls: 'text-cyan-400' },
        ];
        summaryEl.innerHTML = items.map(item =>
            `<div class="bg-slate-800/60 rounded-lg p-3 text-center">
                <div class="text-[10px] text-slate-500 uppercase">${item.label}</div>
                <div class="text-lg font-bold ${item.cls}">${item.value}</div>
            </div>`
        ).join('');
    }

    const classEl = document.getElementById('combat-pos-class');
    if (classEl && data.by_class && data.by_class.length > 0) {
        const classColors = { 'SOLDIER': 'text-rose-400', 'MEDIC': 'text-emerald-400', 'ENGINEER': 'text-amber-400', 'FIELDOPS': 'text-cyan-400', 'COVERTOPS': 'text-purple-400' };
        classEl.innerHTML = data.by_class.map(r => {
            const cls = r.class || '?';
            const color = classColors[cls.toUpperCase()] || 'text-slate-300';
            return `<div class="flex items-center justify-between text-[11px]">
                <span class="${color}">${escapeHtml(cls)}</span>
                <span class="text-right">
                    <span class="text-slate-300">${formatNumber(r.kills || 0)} kills</span>
                    <span class="text-slate-500 text-[10px]">${formatNumber(Math.round(r.avg_distance || 0))}u avg</span>
                </span>
            </div>`;
        }).join('');
    } else if (classEl) {
        classEl.innerHTML = '<span class="text-slate-600">No class data</span>';
    }

    const mapEl = document.getElementById('combat-pos-map');
    if (mapEl && data.by_map && data.by_map.length > 0) {
        mapEl.innerHTML = data.by_map.map(r => {
            return `<div class="flex items-center justify-between text-[11px]">
                <span class="text-slate-300">${escapeHtml(r.map_name || '?')}</span>
                <span class="text-right">
                    <span class="text-amber-400">${formatNumber(r.kills || 0)} kills</span>
                    <span class="text-slate-500 text-[10px]">${formatNumber(Math.round(r.avg_distance || 0))}u avg</span>
                </span>
            </div>`;
        }).join('');
    } else if (mapEl) {
        mapEl.innerHTML = '<span class="text-slate-600">No map data</span>';
    }
}
