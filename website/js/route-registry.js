export const VIEW_MODE = Object.freeze({
    LEGACY: 'legacy',
    MODERN: 'modern',
});

const GREATSHOT_SECTIONS = new Set(['demos', 'highlights', 'clips', 'renders']);

// Single source of truth for session-detail tab keys. Imported by
// `session-detail.js` so adding/removing a tab is a one-file change.
export const SESSION_DETAIL_TABS = ['summary', 'players', 'teamplay', 'charts'];
const STATS_VIEWS = new Set([
    'sessions',
    'leaderboards',
    'maps',
    'weapons',
    'records',
    'awards',
    'profile',
    'retro-viz',
    'sessions2',
    'session-detail',
    'skill-rating',
    'rivalries',
    'story',
    'replay',
    'smart-stats-diag',
]);

const VIEW_TO_NAV = Object.freeze({
    'greatshot-demo': 'greatshot',
    'proximity-player': 'proximity',
    'proximity-replay': 'proximity',
    'proximity-teams': 'proximity',
    'upload-detail': 'uploads',
    sessions: 'sessions-stats',
    sessions2: 'sessions-stats',
    'session-detail': 'sessions-stats',
});

function safeDecode(value) {
    try {
        return decodeURIComponent(value);
    } catch (error) {
        return value;
    }
}

function normalizeGreatshotSection(section) {
    return GREATSHOT_SECTIONS.has(section) ? section : 'demos';
}

const ROUTE_DEFINITIONS = Object.freeze({
    home: {
        viewId: 'home',
        label: 'Home',
        mode: VIEW_MODE.LEGACY,
        surfaceType: 'read-heavy',
        migrationWave: 'A',
        buildHash: () => '',
        load: () => undefined,
    },
    sessions: {
        viewId: 'sessions',
        label: 'Sessions',
        mode: VIEW_MODE.LEGACY,
        surfaceType: 'read-heavy',
        migrationWave: 'A',
        buildHash: () => '#/sessions',
        load: ({ legacy }) => legacy.loadSessionsView(),
    },
    leaderboards: {
        viewId: 'leaderboards',
        label: 'Leaderboards',
        mode: VIEW_MODE.LEGACY,
        surfaceType: 'read-heavy',
        migrationWave: 'A',
        buildHash: () => '#/leaderboards',
        load: ({ legacy }) => legacy.initLeaderboardDefaults(),
    },
    maps: {
        viewId: 'maps',
        label: 'Maps',
        mode: VIEW_MODE.LEGACY,
        surfaceType: 'read-heavy',
        migrationWave: 'A',
        buildHash: () => '#/maps',
        load: ({ legacy }) => legacy.loadMapsView(),
    },
    weapons: {
        viewId: 'weapons',
        label: 'Weapons',
        mode: VIEW_MODE.LEGACY,
        surfaceType: 'read-heavy',
        migrationWave: 'B',
        buildHash: () => '#/weapons',
        load: ({ legacy }) => legacy.loadWeaponsView(),
    },
    profile: {
        viewId: 'profile',
        label: 'Profile',
        mode: VIEW_MODE.LEGACY,
        surfaceType: 'read-heavy',
        migrationWave: 'A',
        buildHash: ({ id } = {}) => (id ? `#/profile/${encodeURIComponent(id)}` : '#/profile'),
        parseHash: (hash) => {
            const m = hash.match(/^#\/profile\/([^/?]+)/);
            return m ? { id: safeDecode(m[1]) } : null;
        },
        load: ({ legacy, params } = {}) => (
            params && params.id && legacy && legacy.loadPlayerProfile
                ? legacy.loadPlayerProfile(params.id)
                : undefined
        ),
    },
    // S6: 'records' is now an alias that opens the consolidated Record Book on its
    // Records tab (viewId points at #view-record-book; old #/records deep links resolve).
    records: {
        viewId: 'record-book',
        label: 'Records',
        mode: VIEW_MODE.LEGACY,
        surfaceType: 'read-heavy',
        migrationWave: 'A',
        buildHash: () => '#/record-book',
        load: ({ legacy }) => legacy.loadRecordBookView({ tab: 'records' }),
    },
    'record-book': {
        viewId: 'record-book',
        label: 'Record Book',
        mode: VIEW_MODE.LEGACY,
        surfaceType: 'read-heavy',
        migrationWave: 'A',
        buildHash: () => '#/record-book',
        load: ({ legacy, params }) => legacy.loadRecordBookView(params || {}),
    },
    awards: {
        viewId: 'awards',
        label: 'Awards',
        mode: VIEW_MODE.LEGACY,
        surfaceType: 'read-heavy',
        migrationWave: 'A',
        buildHash: () => '#/awards',
        load: ({ legacy }) => legacy.loadAwardsView(),
    },
    proximity: {
        viewId: 'proximity',
        label: 'Proximity',
        mode: VIEW_MODE.LEGACY,
        surfaceType: 'read-heavy',
        migrationWave: 'B',
        buildHash: () => '#/proximity',
        load: ({ legacy }) => legacy.loadProximityView(),
    },
    'proximity-player': {
        viewId: 'proximity-player',
        label: 'Player Profile',
        mode: VIEW_MODE.MODERN,
        surfaceType: 'read-heavy',
        migrationWave: 'B',
        buildHash: ({ guid } = {}) => `#/proximity/player/${guid || ''}`,
        load: () => undefined,
        parseHash: (hash) => {
            const m = hash.match(/^#\/proximity\/player\/([^/]+)/);
            return m ? { guid: safeDecode(m[1]) } : null;
        },
    },
    'proximity-replay': {
        viewId: 'proximity-replay',
        label: 'Round Replay',
        mode: VIEW_MODE.MODERN,
        surfaceType: 'read-heavy',
        migrationWave: 'B',
        buildHash: ({ roundId } = {}) => `#/proximity/round/${roundId || ''}`,
        load: () => undefined,
        parseHash: (hash) => {
            const m = hash.match(/^#\/proximity\/round\/(\d+)$/);
            return m ? { roundId: m[1] } : null;
        },
    },
    'proximity-teams': {
        viewId: 'proximity-teams',
        label: 'Team Comparison',
        mode: VIEW_MODE.MODERN,
        surfaceType: 'read-heavy',
        migrationWave: 'B',
        buildHash: ({ roundId } = {}) => `#/proximity/round/${roundId || ''}/teams`,
        load: () => undefined,
        parseHash: (hash) => {
            const m = hash.match(/^#\/proximity\/round\/(\d+)\/teams$/);
            return m ? { roundId: m[1] } : null;
        },
    },
    greatshot: {
        viewId: 'greatshot',
        label: 'Greatshot',
        mode: VIEW_MODE.LEGACY,
        surfaceType: 'mixed',
        migrationWave: 'C',
        buildHash: ({ section } = {}) => `#/greatshot/${normalizeGreatshotSection(section)}`,
        load: ({ legacy, params }) => legacy.loadGreatshotView(normalizeGreatshotSection(params.section)),
    },
    'greatshot-demo': {
        viewId: 'greatshot-demo',
        label: 'Greatshot Demo',
        mode: VIEW_MODE.LEGACY,
        surfaceType: 'write/auth-heavy',
        migrationWave: 'C',
        buildHash: ({ demoId } = {}) => (demoId ? `#/greatshot/demo/${encodeURIComponent(demoId)}` : '#/greatshot/demos'),
        load: ({ legacy, params }) => {
            if (params.demoId) {
                return legacy.loadGreatshotDemoDetail(params.demoId);
            }
            return legacy.loadGreatshotView('demos');
        },
    },
    uploads: {
        viewId: 'uploads',
        label: 'Uploads',
        mode: VIEW_MODE.LEGACY,
        surfaceType: 'write/auth-heavy',
        migrationWave: 'C',
        buildHash: () => '#/uploads',
        load: ({ legacy }) => legacy.loadUploadsView(),
    },
    'upload-detail': {
        viewId: 'upload-detail',
        label: 'Upload Detail',
        mode: VIEW_MODE.LEGACY,
        surfaceType: 'mixed',
        migrationWave: 'C',
        buildHash: ({ uploadId } = {}) => (uploadId ? `#/uploads/${encodeURIComponent(uploadId)}` : '#/uploads'),
        load: ({ legacy, params }) => {
            if (params.uploadId) {
                return legacy.loadUploadDetail(params.uploadId);
            }
            return legacy.loadUploadsView();
        },
    },
    availability: {
        viewId: 'availability',
        label: '#ETL',
        mode: VIEW_MODE.LEGACY,
        surfaceType: 'write/auth-heavy',
        migrationWave: 'C',
        buildHash: () => '#/availability',
        load: ({ legacy }) => legacy.loadAvailabilityView(),
    },
    admin: {
        viewId: 'admin',
        label: 'About',
        mode: VIEW_MODE.LEGACY,
        surfaceType: 'static',
        migrationWave: 'C',
        buildHash: () => '#/admin',
        load: ({ legacy }) => legacy.loadAdminPanelView(),
    },
    // S6: 'hall-of-fame' now opens the consolidated Record Book on its Hall of Fame tab.
    'hall-of-fame': {
        viewId: 'record-book',
        label: 'Hall of Fame',
        mode: VIEW_MODE.LEGACY,
        surfaceType: 'read-heavy',
        migrationWave: 'B',
        buildHash: () => '#/record-book',
        load: ({ legacy }) => legacy.loadRecordBookView({ tab: 'hof' }),
    },
    'retro-viz': {
        viewId: 'retro-viz',
        label: 'Retro Viz',
        mode: VIEW_MODE.LEGACY,
        surfaceType: 'read-heavy',
        migrationWave: 'B',
        buildHash: () => '#/retro-viz',
        load: ({ legacy }) => legacy.loadRetroVizView(),
    },
    'skill-rating': {
        viewId: 'skill-rating',
        label: 'ET Rating',
        mode: VIEW_MODE.MODERN,
        surfaceType: 'read-heavy',
        migrationWave: 'C',
        buildHash: () => '#/skill-rating',
        load: () => undefined,
    },
    rivalries: {
        viewId: 'rivalries',
        label: 'Rivalries',
        mode: VIEW_MODE.LEGACY,
        surfaceType: 'read-heavy',
        migrationWave: 'C',
        buildHash: () => '#/rivalries',
        load: ({ legacy }) => legacy.loadRivalriesView(),
    },
    story: {
        viewId: 'story',
        label: 'Smart Stats',
        mode: VIEW_MODE.LEGACY,
        surfaceType: 'read-heavy',
        migrationWave: 'C',
        buildHash: () => '#/story',
        load: ({ legacy }) => legacy.loadStoryView(),
    },
    replay: {
        viewId: 'replay',
        label: 'Replay',
        mode: VIEW_MODE.LEGACY,
        surfaceType: 'read-heavy',
        migrationWave: 'C',
        buildHash: () => '#/replay',
        load: ({ legacy }) => legacy.loadReplayView(),
    },
    'smart-stats-diag': {
        viewId: 'smart-stats-diag',
        label: 'Smart Stats — Diag',
        mode: VIEW_MODE.LEGACY,
        surfaceType: 'read-heavy',
        migrationWave: 'C',
        buildHash: () => '#/smart-stats-diag',
        load: ({ legacy }) => legacy.loadSmartStatsDiagView(),
    },
    sessions2: {
        viewId: 'sessions2',
        label: 'Sessions 2.0',
        mode: VIEW_MODE.LEGACY,
        surfaceType: 'read-heavy',
        migrationWave: 'B',
        buildHash: () => '#/sessions2',
        load: ({ legacy }) => legacy.loadSessions2View(),
    },
    'session-detail': {
        viewId: 'session-detail',
        label: 'Session Detail',
        mode: VIEW_MODE.LEGACY,
        surfaceType: 'read-heavy',
        migrationWave: 'B',
        buildHash: ({ sessionId, sessionDate, tab } = {}) => {
            const tabSeg = tab && tab !== 'summary' && SESSION_DETAIL_TABS.includes(tab)
                ? `/${tab}`
                : '';
            if (sessionId) {
                return `#/session-detail/${encodeURIComponent(sessionId)}${tabSeg}`;
            }
            if (sessionDate) {
                return `#/session-detail/date/${encodeURIComponent(sessionDate)}${tabSeg}`;
            }
            return '#/sessions2';
        },
        load: ({ legacy, params }) => legacy.loadSessionDetailView({
            sessionId: params.sessionId,
            sessionDate: params.sessionDate,
            tab: params.tab,
        }),
    },
});

export function listRouteDefinitions() {
    return ROUTE_DEFINITIONS;
}

export function getRouteDefinition(viewId) {
    return ROUTE_DEFINITIONS[viewId] || null;
}

export function getRouteHash(viewId, params = {}) {
    const definition = getRouteDefinition(viewId);
    return definition ? definition.buildHash(params) : '';
}

export function getActiveNavKeys(viewId) {
    const navKey = VIEW_TO_NAV[viewId] || viewId;
    const activeKeys = [`link-${navKey}`];
    if (STATS_VIEWS.has(viewId)) {
        activeKeys.push('link-stats');
    }
    return activeKeys;
}

export function parseHashRoute(hashValue = window.location.hash) {
    const cleanHash = String(hashValue || '').replace(/^#\/?/, '');
    if (!cleanHash) {
        return { viewId: 'home', params: {} };
    }

    const routePath = cleanHash.split('?')[0];
    const normalizedHash = `#/${routePath}`;
    const segments = routePath.split('/').filter(Boolean);

    if (segments[0] === 'greatshot') {
        if (segments[1] === 'demo' && segments[2]) {
            return {
                viewId: 'greatshot-demo',
                params: { demoId: safeDecode(segments[2]) },
            };
        }
        return {
            viewId: 'greatshot',
            params: { section: normalizeGreatshotSection(segments[1] || 'demos') },
        };
    }

    if (segments[0] === 'uploads' && segments[1]) {
        return {
            viewId: 'upload-detail',
            params: { uploadId: safeDecode(segments[1]) },
        };
    }

    if (segments[0] === 'session-detail' && segments[1] === 'date' && segments[2]) {
        const tab = SESSION_DETAIL_TABS.includes(segments[3]) ? segments[3] : 'summary';
        return {
            viewId: 'session-detail',
            params: { sessionDate: safeDecode(segments[2]), tab },
        };
    }

    if (segments[0] === 'session-detail' && segments[1]) {
        const tab = SESSION_DETAIL_TABS.includes(segments[2]) ? segments[2] : 'summary';
        return {
            viewId: 'session-detail',
            params: { sessionId: safeDecode(segments[1]), tab },
        };
    }

    for (const definition of Object.values(ROUTE_DEFINITIONS)) {
        if (typeof definition.parseHash !== 'function') continue;
        const params = definition.parseHash(normalizedHash);
        if (params) {
            return {
                viewId: definition.viewId,
                params,
            };
        }
    }

    return { viewId: segments[0] || 'home', params: {} };
}

export function loadRoute(viewId, params, runtime) {
    const definition = getRouteDefinition(viewId);
    if (!definition) {
        return false;
    }
    if (definition.mode === VIEW_MODE.MODERN) {
        return runtime.modern.mountRoute({ viewId, params });
    }
    return definition.load({
        definition,
        params,
        legacy: runtime.legacy,
        modern: runtime.modern,
    });
}
