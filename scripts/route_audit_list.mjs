/**
 * The route lists both sweeps use, and the check that joins them.
 *
 * Split out of audit_website_browser.mjs so it can run WITHOUT a browser:
 * that script imports Playwright at module load, which made the one guard
 * standing between us and the "29 routes audited, 36 in the table" class
 * impossible to run in CI — so it ran only when somebody remembered, which
 * is exactly the condition under which the original gap survived unnoticed
 * (brother's review on #839).
 *
 * scripts/check_route_coverage.mjs runs the check alone in a second; the
 * audit script imports the same list for its sweeps.
 */
import { readFileSync } from 'node:fs';

// Every route in the legacy registry. Parametrised ones carry real values so
// they are actually exercised rather than bouncing off a guard — the
// stale-contract findings in the master review all live behind a param.
//
// `key` is the registry's own viewId, and assertRegistryCovered() below fails
// the run when the registry grows a route this list does not exercise. That
// guard was written after the list and the registry were compared for the
// first time: 29 entries against 32 keys, with `system`, `spider-web`,
// `greatshot-demo` and `upload-detail` never once loaded by an audit that
// reported itself as covering every route.
export const ROUTES = [
    { key: 'home', name: 'home', hash: '' },
    { key: 'sessions', name: 'sessions', hash: '#/sessions' },
    { key: 'sessions2', name: 'sessions2', hash: '#/sessions2' },
    { key: 'session-detail', name: 'session-detail (date, multi-session)', hash: '#/session-detail/date/2026-08-04' },
    { key: 'leaderboards', name: 'leaderboards', hash: '#/leaderboards' },
    { key: 'form', name: 'form', hash: '#/form' },
    { key: 'maps', name: 'maps', hash: '#/maps' },
    { key: 'weapons', name: 'weapons', hash: '#/weapons' },
    { key: 'records', name: 'records (alias)', hash: '#/records' },
    { key: 'record-book', name: 'record-book', hash: '#/record-book' },
    { key: 'hall-of-fame', name: 'hall-of-fame', hash: '#/hall-of-fame' },
    { key: 'awards', name: 'awards', hash: '#/awards' },
    { key: 'profile', name: 'profile (owner)', hash: '#/profile/E587CA5F' },
    { key: 'profile', name: 'profile (other)', hash: '#/profile/D8423F90' },
    { key: 'skill-rating', name: 'skill-rating', hash: '#/skill-rating' },
    { key: 'rivalries', name: 'rivalries', hash: '#/rivalries' },
    { key: 'story', name: 'story', hash: '#/story' },
    { key: 'replay', name: 'replay', hash: '#/replay' },
    { key: 'retro-viz', name: 'retro-viz', hash: '#/retro-viz' },
    { key: 'live', name: 'tonight', hash: '#/tonight' },
    { key: 'proximity', name: 'proximity', hash: '#/proximity' },
    { key: 'proximity-player', name: 'proximity-player', hash: '#/proximity/player/D8423F90' },
    { key: 'proximity-replay', name: 'proximity-replay', hash: '#/proximity/round/11175' },
    { key: 'proximity-teams', name: 'proximity-teams', hash: '#/proximity/round/11175/teams' },
    { key: 'smart-stats-diag', name: 'smart-stats-diag', hash: '#/smart-stats-diag' },
    { key: 'greatshot', name: 'greatshot', hash: '#/greatshot/demos' },
    { key: 'uploads', name: 'uploads', hash: '#/uploads' },
    { key: 'availability', name: 'availability', hash: '#/availability' },
    { key: 'admin', name: 'admin', hash: '#/admin' },
    // The four the guard found. Ids are real rows on the dev database; a
    // missing one turns into an ordinary "page said no data" finding rather
    // than a silent skip.
    { key: 'system', name: 'system', hash: '#/system' },
    { key: 'spider-web', name: 'spider-web', hash: '#/spider-web/round/11365' },
    { key: 'greatshot-demo', name: 'greatshot-demo', hash: '#/greatshot/demo/7dc01a5727344cd8afece44a1cc572e6' },
    { key: 'upload-detail', name: 'upload-detail', hash: '#/uploads/de4f8d8628c148e5a8756a522aeb43b0' },
];

/**
 * The list above and website/js/route-registry.js are two halves of one fact.
 * Nothing joined them, so the audit could report "every route" while three
 * whole pages had never been loaded. Node can import the registry directly —
 * it is a plain ES module — so the join is a check, not a copy.
 */
export async function assertRegistryCovered() {
    // A literal specifier, relative to this file: a computed import path is
    // a finding for every scanner and buys nothing here.
    const registry = await import('../website/js/route-registry.js');
    const known = new Set(Object.keys(registry.listRouteDefinitions()));
    const audited = new Set(ROUTES.map((r) => r.key));
    const missing = [...known].filter((k) => !audited.has(k));
    const unknown = [...audited].filter((k) => !known.has(k));
    if (missing.length || unknown.length) {
        process.stderr.write(
            `route list and the legacy registry disagree\n`
            + (missing.length ? `  never audited: ${missing.join(', ')}\n` : '')
            + (unknown.length ? `  not in the registry: ${unknown.join(', ')}\n` : ''),
        );
        process.exit(2);
    }
}

/**
 * The NEW app's routes, read from the table the app itself uses.
 *
 * routes.data.json exists so this line can be an import rather than a second
 * copy: scripts run in plain Node and cannot read the TypeScript the app is
 * written in, which is exactly how the two lists drifted apart before.
 * Parameters are filled from the same sample values as the legacy pass, so a
 * side-by-side manifest compares the same rows of data.
 */
export function appRoutes() {
    const table = JSON.parse(
        readFileSync(new URL('../website/frontend/src/app/routes.data.json', import.meta.url), 'utf8'),
    );
    // A Map, not an object: the key comes out of a file, and an object
    // indexed by a value read from data is an injection sink to every
    // scanner in this repo's CI (same reason layout.tsx's SPACE is a Map).
    const samples = new Map([
        [':id?', 'D8423F90'], [':guid', 'D8423F90'], [':roundId', '11365'],
        [':sessionId', '154'], [':sessionDate', '2026-08-04'], [':gsid', '154'],
        [':date', '2026-08-27'], [':section?', 'demos'],
        [':demoId', '7dc01a5727344cd8afece44a1cc572e6'],
        [':uploadId', 'de4f8d8628c148e5a8756a522aeb43b0'],
        [':tab?', ''],
    ]);
    return table.map((row) => {
        const filled = row.path
            .split('/')
            .map((seg) => (seg.startsWith(':') ? samples.get(seg) ?? seg.replace(/[:?]/g, '') : seg))
            .filter((seg, i) => seg !== '' || i === 0)
            .join('/');
        return { key: row.key, name: row.key, hash: `app${filled === '/' ? '' : filled}` };
    });
}
