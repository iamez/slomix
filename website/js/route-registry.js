export const VIEW_MODE = Object.freeze({
    LEGACY: 'legacy',
    MODERN: 'modern',
});

const GREATSHOT_SECTIONS = new Set(['demos', 'highlights', 'clips', 'renders']);
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
        buildHash: () => '#/profile',
        load: () => undefined,
    },
    records: {
        viewId: 'records',
        label: 'Records',
        mode: VIEW_MODE.LEGACY,
        surfaceType: 'read-heavy',
        migrationWave: 'A',
        buildHash: () => '#/records',
        load: ({ legacy }) => legacy.loadRecordsView(),
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
        label: 'Availability',
        mode: VIEW_MODE.LEGACY,
        surfaceType: 'write/auth-heavy',
        migrationWave: 'C',
        buildHash: () => '#/availability',
        load: ({ legacy }) => legacy.loadAvailabilityView(),
    },
    admin: {
        viewId: 'admin',
        label: 'Admin',
        mode: VIEW_MODE.LEGACY,
        surfaceType: 'write/auth-heavy',
        migrationWave: 'C',
        buildHash: () => '#/admin',
        load: ({ legacy }) => legacy.loadAdminPanelView(),
    },
    'hall-of-fame': {
        viewId: 'hall-of-fame',
        label: 'Hall of Fame',
        mode: VIEW_MODE.LEGACY,
        surfaceType: 'read-heavy',
        migrationWave: 'B',
        buildHash: () => '#/hall-of-fame',
        load: ({ legacy }) => legacy.loadHallOfFameView(),
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
    story: {
        viewId: 'story',
        label: 'Smart Stats',
        mode: VIEW_MODE.MODERN,
        surfaceType: 'read-heavy',
        migrationWave: 'C',
        buildHash: () => '#/story',
        load: () => undefined,
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
        buildHash: ({ sessionId, sessionDate } = {}) => {
            if (sessionId) {
                return `#/session-detail/${encodeURIComponent(sessionId)}`;
            }
            if (sessionDate) {
                return `#/session-detail/date/${encodeURIComponent(sessionDate)}`;
            }
            return '#/sessions2';
        },
        load: ({ legacy, params }) => legacy.loadSessionDetailView({
            sessionId: params.sessionId,
            sessionDate: params.sessionDate,
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
        return {
            viewId: 'session-detail',
            params: { sessionDate: safeDecode(segments[2]) },
        };
    }

    if (segments[0] === 'session-detail' && segments[1]) {
        return {
            viewId: 'session-detail',
            params: { sessionId: safeDecode(segments[1]) },
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
