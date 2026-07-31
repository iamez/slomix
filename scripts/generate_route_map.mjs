#!/usr/bin/env node
// Generates docs/ROUTE_MAP_2026-07.md from website/js/route-registry.js — the
// single source of truth for which frontend (legacy JS vs. React/modern)
// serves each hash route. Re-run after editing route-registry.js so the doc
// never drifts from the code the way a hand-written table would.
//
// Usage: node scripts/generate_route_map.mjs            (writes docs/ROUTE_MAP_2026-07.md)
//        node scripts/generate_route_map.mjs --stdout    (prints instead, for diffing)
//
// The script writes the file itself rather than relying on shell redirection.
// A `> file 2>&1` typo captures Node's own stderr warnings into the generated
// markdown — which is exactly what happened once, leaking a
// MODULE_TYPELESS_PACKAGE_JSON warning, a PID, and absolute local paths into
// the committed doc (Codex review on #575). Writing from inside the script
// removes that whole class of mistake.

import { readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

import { listRouteDefinitions, VIEW_MODE } from '../website/js/route-registry.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, '..');
const legacyDir = path.join(repoRoot, 'website/js');
const pagesDir = path.join(repoRoot, 'website/frontend/src/pages');

// Build an index of exported function name -> defining file, e.g.
// "loadSessionsView" -> "sessions.js", by scanning every legacy JS file for
// `export function X(` / `export async function X(`. This is how
// route-registry.js's `load: ({ legacy }) => legacy.loadXView()` callbacks
// actually resolve at runtime, so it's the only accurate way to answer
// "which file serves this route" — filename-guessing gets it wrong (e.g.
// 'admin' -> admin-panel.js, 'leaderboards' -> leaderboard.js singular).
function buildLegacyFunctionIndex() {
    const index = new Map();
    const exportRe = /export\s+(?:async\s+)?function\s+(\w+)\s*\(/g;
    for (const file of readdirSync(legacyDir)) {
        if (!file.endsWith('.js') || file === 'route-registry.js') continue;
        const text = readFileSync(path.join(legacyDir, file), 'utf8');
        let match;
        while ((match = exportRe.exec(text)) !== null) {
            if (!index.has(match[1])) {
                index.set(match[1], file);
            }
        }
    }
    return index;
}

// 'home' is a documented exception: its route definition's load() is an
// intentional no-op (buildHash() -> '', no discrete load call), because the
// home view is populated by initApp() in app.js calling its loaders directly
// during startup, not through the route dispatch mechanism every other route
// uses.
//
// This list is DERIVED, not hand-written. It was hand-written twice and was
// incomplete both times — first missing everything but home.js, then missing
// the whole `scheduleDeferredLoads([...])` batch that populates the season
// widgets (Codex review on #575, twice). Parsing the two arrays out of
// initApp() keeps it honest as the startup sequence changes.
// True if `sym` appears in `text` as a call: `sym(` or `sym (`, not preceded by
// another identifier character.
//
// Deliberately NOT `new RegExp(\`\\b${sym}\\s*\\(\`)`. Building a pattern from a
// parsed symbol is both a Codacy finding and a real bug: `$` is legal in a JS
// identifier but means end-of-input in a regex, so a symbol like `$foo` would
// compile to a pattern that can never match, and the module would be silently
// dropped from the route map. The character classes below are literal regexes,
// which is fine — nothing is constructed from input.
const IDENT_CHAR = /[\w$]/;
const CALL_GAP = /\s/;

function isCalledIn(text, sym) {
    for (let i = text.indexOf(sym); i !== -1; i = text.indexOf(sym, i + 1)) {
        // Must start on a word boundary, or it's a substring of a longer name.
        if (i > 0 && IDENT_CHAR.test(text[i - 1])) continue;
        let j = i + sym.length;
        while (j < text.length && CALL_GAP.test(text[j])) j += 1;
        if (text[j] === '(') return true;
    }
    return false;
}

// True if `sym` appears as a standalone identifier (not a substring).
function isMentionedIn(text, sym) {
    for (let i = text.indexOf(sym); i !== -1; i = text.indexOf(sym, i + 1)) {
        const before = i === 0 ? '' : text[i - 1];
        const after = text[i + sym.length] ?? '';
        if (!IDENT_CHAR.test(before) && !IDENT_CHAR.test(after)) return true;
    }
    return false;
}

// Source of `function name(...) { ... }` (or `async function`), or null if it
// can't be isolated. Brace-matched rather than regex-parsed; naive about braces
// inside strings/comments, which is acceptable here because the caller falls
// back to whole-file scanning when this returns null.
function functionBody(text, name) {
    let start = -1;
    for (let i = text.indexOf(name); i !== -1; i = text.indexOf(name, i + 1)) {
        if (i > 0 && IDENT_CHAR.test(text[i - 1])) continue;
        if (!/function\s+$/.test(text.slice(Math.max(0, i - 40), i))) continue;
        start = i;
        break;
    }
    if (start === -1) return null;
    // Skip the parameter list before looking for the body brace: a default
    // value like `loadRecordBookView(params = {})` puts a `{}` between the name
    // and the body, and naively taking the first `{` returned that empty object
    // as the "body" — silently scoping every scan to nothing.
    const paren = text.indexOf('(', start);
    if (paren === -1) return null;
    let pd = 0;
    let afterParams = -1;
    for (let j = paren; j < text.length; j += 1) {
        if (text[j] === '(') pd += 1;
        else if (text[j] === ')') {
            pd -= 1;
            if (pd === 0) { afterParams = j + 1; break; }
        }
    }
    if (afterParams === -1) return null;
    const open = text.indexOf('{', afterParams);
    if (open === -1) return null;
    let depth = 0;
    for (let j = open; j < text.length; j += 1) {
        if (text[j] === '{') depth += 1;
        else if (text[j] === '}') {
            depth -= 1;
            if (depth === 0) return text.slice(open, j + 1);
        }
    }
    return null;
}

// utils.js is the shared helper module (fetchJSON/escapeHtml/…) imported by
// nearly every file; listing it under every route adds no triage value.
const SHARED_INFRA = new Set(['route-registry.js', 'utils.js']);

// A loader that begins by looking up a DOM id and bailing out when it is absent
// does nothing if that id is not in the served HTML. `loadMatchesView()` is
// exactly this: `getElementById('matches-grid'); if (!grid) return;`
// (matches.js:24) and `matches-grid` appears nowhere in website/ — the home
// page's Recent Matches widget is `loadRecentMatches()` in leaderboard.js.
// Listing matches.js as a home serving file sends triage to dead code
// (Codex review on #575).
function isDeadLoader(body, servedHtml) {
    if (!body) return false;
    const guard = body.match(/getElementById\(\s*['"]([\w-]+)['"]\s*\)[\s\S]{0,120}?if\s*\(\s*!\s*\w+\s*\)\s*return/);
    if (!guard) return false;
    return !servedHtml.includes(`id="${guard[1]}"`) && !servedHtml.includes(`id='${guard[1]}'`);
}

// One level of transitive imports out of each entry-point file, scoped to the
// bodies of the entry points themselves. Direct-only resolution under-reports:
// loadTonightView() calls initTonightBetting() from bets.js (tonight.js:10,42)
// and loadRecordBookView() dispatches into records.js / hall-of-fame.js
// (record-book.js:9-10), none of which appeared in the map. Scoping to the
// entry body avoids the opposite error — attributing an unrelated function's
// imports to the route (Codex review on #575).
function transitiveFiles(entryNames, legacyIndex, files) {
    const byFile = new Map();
    for (const name of entryNames) {
        const f = legacyIndex.get(name);
        if (f && f !== 'app.js') {
            if (!byFile.has(f)) byFile.set(f, []);
            byFile.get(f).push(name);
        }
    }
    for (const [file, loaders] of byFile) {
        const text = readFileSync(path.join(legacyDir, file), 'utf8');
        const bodies = loaders.map((n) => functionBody(text, n)).filter(Boolean);

        // Follow same-file helpers to a fixpoint, not just one level.
        // record-book.js delegates twice: loadRecordBookView() -> _showTab() ->
        // _ensureLoaded(), which assigns loadRecordsView / loadHallOfFameView to
        // a local and calls `loader()` (record-book.js:31-44). Neither the
        // import nor a direct call appears in the entry body, so records.js and
        // hall-of-fame.js went unreported (Codex review on #575). The iteration
        // terminates because a file has finitely many functions and each is
        // pulled in at most once.
        const localFns = [...text.matchAll(/^(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(/gm)]
            .map((m) => m[1])
            .filter((n) => !loaders.includes(n));
        const reached = new Set();
        let frontier = [...bodies];
        while (frontier.length) {
            const next = [];
            for (const fn of localFns) {
                if (reached.has(fn)) continue;
                if (!frontier.some((b) => isCalledIn(b, fn))) continue;
                reached.add(fn);
                const fnBody = functionBody(text, fn);
                if (fnBody) next.push(fnBody);
            }
            bodies.push(...next);
            frontier = next;
        }

        const scope = bodies.length ? bodies.join('\n') : text;
        // The `(?:\?[^']*)?` accepts a cache-busting query suffix and drops it
        // from the captured filename. Without it the pattern simply failed to
        // match every versioned import — `from './retro-viz.js?v=20260513-v142-cf-bust'`
        // (session-detail.js:16, and a dozen more in app.js) — so those serving
        // files were silently missing from the generated rows rather than
        // reported as unresolved (Codex review on #575).
        for (const m of text.matchAll(/import\s*\{([^}]*)\}\s*from\s*'\.\/([\w.-]+)(?:\?[^']*)?'/g)) {
            const symbols = m[1].split(',').map((x) => x.trim().split(/\s+as\s+/).pop()).filter(Boolean);
            const target = m[2];
            if (SHARED_INFRA.has(target)) continue;
            // `isCalledIn` alone misses `loader = loadRecordsView; loader()`.
            // A bare mention inside the (already narrowly scoped) entry/helper
            // bodies is a real use of that import.
            const used = symbols.some((sym) => isCalledIn(scope, sym) || isMentionedIn(scope, sym));
            if (used) files.add(`website/js/${target}`);
        }
    }
}

// Ids that live inside the served `#view-home` block. Used to tell a home-page
// loader apart from unrelated app-wide wiring, so that harvesting unconditional
// startup calls doesn't re-introduce the false positives the transitive scan
// was narrowed to avoid.
function homeViewIds(servedHtml) {
    const start = servedHtml.indexOf('id="view-home"');
    if (start === -1) return new Set();
    const next = servedHtml.indexOf('id="view-', start + 1);
    const block = servedHtml.slice(start, next === -1 ? servedHtml.length : next);
    return new Set([...block.matchAll(/id="([\w-]+)"/g)].map((m) => m[1]));
}

function touchesHomeId(body, homeIds) {
    for (const m of body.matchAll(/getElementById\(\s*['"]([\w-]+)['"]\s*\)/g)) {
        if (homeIds.has(m[1])) return true;
    }
    for (const m of body.matchAll(/querySelector(?:All)?\(\s*['"]#([\w-]+)/g)) {
        if (homeIds.has(m[1])) return true;
    }
    return false;
}

function homeLoaderFiles(legacyIndex) {
    const appJs = readFileSync(path.join(legacyDir, 'app.js'), 'utf8');
    const names = new Set();

    // criticalLoads.unshift(a, b, c, ...) — the synchronous startup batch.
    const critical = appJs.match(/criticalLoads\.unshift\(([\s\S]*?)\)\s*;/);
    if (critical) {
        for (const m of critical[1].matchAll(/\b([A-Za-z_]\w*)\b/g)) names.add(m[1]);
    }
    // scheduleDeferredLoads([{ task: fn, label: '...' }, ...]) — the idle batch.
    const deferred = appJs.match(/scheduleDeferredLoads\(\[([\s\S]*?)\]\s*\)\s*;/);
    if (deferred) {
        for (const m of deferred[1].matchAll(/task:\s*([A-Za-z_]\w*)/g)) names.add(m[1]);
    }

    // Direct calls inside `if (legacyHomeEnabled) { ... }` — initLivePolling()
    // and initLiveStatusPolling() start the home page's live widgets but sit
    // in neither array, so harvesting only the arrays dropped live-status.js
    // from the map (Codex review on #575).
    // NOTE: app.js has more than one `if (legacyHomeEnabled)` block; harvest all.
    for (const blk of appJs.matchAll(/if\s*\(legacyHomeEnabled\)\s*\{([\s\S]*?)\n    \}/g)) {
        for (const m of blk[1].matchAll(/^\s{8}([A-Za-z_]\w*)\s*\(\s*\)\s*;/gm)) names.add(m[1]);
    }

    // Functions declared in app.js itself are never `export`ed, so they aren't
    // in the exported-symbol index — resolve those to app.js directly.
    const localToAppJs = new Set();
    for (const m of appJs.matchAll(/^(?:async\s+)?function\s+(\w+)\s*\(/gm)) {
        localToAppJs.add(m[1]);
    }

    const servedHtml = readFileSync(path.join(repoRoot, 'website/index.html'), 'utf8');

    // initApp() also wires the home page UNCONDITIONALLY, outside every
    // `if (legacyHomeEnabled)` block: `initSearchListeners()` at app.js:764
    // binds #hero-search-input and #hero-search-results (auth.js:629-630),
    // both of which sit inside #view-home — so auth.js serves the home
    // route's search box and was missing from its row (Codex review on #575).
    //
    // Counting every unconditional call here would drag in app-wide wiring
    // that has nothing to do with home, so a call qualifies only when the
    // function it names touches an id that is actually inside the served
    // #view-home block.
    const homeIds = homeViewIds(servedHtml);
    const initAppBody = functionBody(appJs, 'initApp');
    if (initAppBody) {
        for (const m of initAppBody.matchAll(/^\s{4}([A-Za-z_]\w*)\s*\(\s*\)\s*;/gm)) {
            const name = m[1];
            if (names.has(name)) continue;
            const file = legacyIndex.get(name) ?? (localToAppJs.has(name) ? 'app.js' : null);
            if (!file) continue;
            const body = functionBody(readFileSync(path.join(legacyDir, file), 'utf8'), name);
            if (body && touchesHomeId(body, homeIds)) names.add(name);
        }
    }

    const files = new Set();
    const unresolved = [];
    const dead = [];
    const live = [];
    for (const name of names) {
        const file = legacyIndex.get(name) ?? (localToAppJs.has(name) ? 'app.js' : null);
        if (!file) { unresolved.push(name); continue; }
        const src = readFileSync(path.join(legacyDir, file), 'utf8');
        if (isDeadLoader(functionBody(src, name), servedHtml)) { dead.push(`${name} (${file})`); continue; }
        live.push(name);
        files.add(`website/js/${file}`);
    }
    transitiveFiles(live, legacyIndex, files);

    const sorted = [...files].sort();
    const notes = [];
    if (unresolved.length) notes.push(`unresolved: ${unresolved.join(', ')}`);
    if (dead.length) notes.push(`skipped no-op: ${dead.join(', ')}`);
    const suffix = notes.length ? ` (${notes.join('; ')})` : '';
    return `${sorted.join(' + ')} — populated directly from initApp() in app.js (criticalLoads + scheduleDeferredLoads), not through load()${suffix}`;
}

// 'hall-of-fame' is a documented exception: its buildHash() returns the
// generic '#/record-book' (same as the plain 'record-book' route), because
// the router dispatches by viewId, not hash, and both routes share
// viewId 'record-book' — but that hash alone does NOT deep-link to the Hall
// of Fame tab. loadRecordBookView() (website/js/record-book.js:55) defaults
// to the 'records' tab; only the literal hash '#/hall-of-fame' is recognized
// by this route's own parseHash() (which maps it to { tab: 'hof' }). Using
// buildHash()'s output here would print a working-but-wrong example — a
// human clicking it lands on the wrong tab (Codex review on #575).
const HASH_EXAMPLE_OVERRIDES = {
    'hall-of-fame': '#/hall-of-fame',
};

function legacyFileFor(routeKey, def, legacyIndex) {
    if (routeKey === 'home') return homeLoaderFiles(legacyIndex);
    const source = def.load.toString();
    const calls = [...source.matchAll(/legacy\.(\w+)\(/g)].map((m) => m[1]);
    const files = new Set(
        calls.map((name) => legacyIndex.get(name)).filter(Boolean).map((f) => `website/js/${f}`),
    );
    // Same transitive pass the home route gets: an entry point that delegates
    // into another module (tonight.js -> bets.js, record-book.js -> records.js /
    // hall-of-fame.js) would otherwise be under-reported.
    transitiveFiles(calls, legacyIndex, files);
    if (files.size === 0) {
        return calls.length ? `unresolved (calls: ${calls.join(', ')})` : '(no legacy.* call in load())';
    }
    return [...files].sort().map((f) => f.replace('website/js/', '')).join(', ');
}

function modernFileFor(viewId) {
    const pascal = viewId
        .split('-')
        .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
        .join('');
    const candidates = readdirSync(pagesDir).filter((f) => f.endsWith('.tsx'));
    const exact = candidates.find((f) => f === `${pascal}.tsx`);
    return exact ? `website/frontend/src/pages/${exact}` : `website/frontend/src/pages/ (no exact ${pascal}.tsx — check manually)`;
}

// buildHash({}) with no params: some route defs check for the param and
// fall back to a real list-view hash (profile, greatshot-demo,
// upload-detail, story, session-detail) — that fallback IS a valid example,
// not a placeholder. Others (proximity-player/replay/teams) don't check and
// just interpolate the missing param straight into the template, producing
// a malformed hash with an empty segment (trailing '/' or '//') — that one
// needs flagging as "needs params", not printed as if it were real
// (Copilot + Codex review on #575).
function computeHashExample(routeKey, def) {
    if (HASH_EXAMPLE_OVERRIDES[routeKey]) return HASH_EXAMPLE_OVERRIDES[routeKey];
    let result;
    try {
        result = def.buildHash({});
    } catch {
        return '(needs params)';
    }
    if (result === '') return '(root — empty hash)';
    const withoutPrefix = result.replace(/^#\//, '');
    if (withoutPrefix.includes('//') || withoutPrefix.endsWith('/')) {
        return '(needs params)';
    }
    return result;
}

const legacyIndex = buildLegacyFunctionIndex();
const definitions = listRouteDefinitions();
const rows = Object.entries(definitions)
    .map(([routeKey, def]) => ({
        routeKey,
        viewId: def.viewId,
        mode: def.mode,
        hashExample: computeHashExample(routeKey, def),
        file: def.mode === VIEW_MODE.MODERN ? modernFileFor(def.viewId) : legacyFileFor(routeKey, def, legacyIndex),
    }))
    .sort((a, b) => a.routeKey.localeCompare(b.routeKey));

const lines = [];
lines.push('# Route Map — React vs. legacy JS');
lines.push('');
lines.push('**Generated by `scripts/generate_route_map.mjs` from `website/js/route-registry.js`');
lines.push('— do not hand-edit. Re-run `node scripts/generate_route_map.mjs` (no shell');
lines.push('redirection needed; it writes this file itself) after route-registry.js or the');
lines.push('pages it references change.**');
lines.push('');
lines.push(`Generated: ${new Date().toISOString().slice(0, 10)}`);
lines.push('');
lines.push('| Route key | Hash example | Implementation | Serving file |');
lines.push('|---|---|---|---|');
for (const row of rows) {
    const impl = row.mode === VIEW_MODE.MODERN ? 'React (modern)' : 'Legacy JS';
    lines.push(`| \`${row.routeKey}\` | \`${row.hashExample}\` | ${impl} | ${row.file} |`);
}
lines.push('');
lines.push(`Total: ${rows.length} routes — ${rows.filter((r) => r.mode === VIEW_MODE.MODERN).length} React, ${rows.filter((r) => r.mode === VIEW_MODE.LEGACY).length} legacy.`);
lines.push('');
lines.push('"Serving file" for legacy routes is resolved by scanning every `website/js/*.js`');
lines.push('file for the `export function <name>(` that matches the `legacy.<name>()` call in');
lines.push('the route\'s `load()` — not a filename guess. Modern (React) routes mount through');
lines.push('`website/frontend/src/route-host.tsx`; the page file is matched by PascalCase');
lines.push('convention against `website/frontend/src/pages/*.tsx`.');

const output = lines.join('\n') + '\n';
if (process.argv.includes('--stdout')) {
    process.stdout.write(output);
} else {
    const target = path.join(repoRoot, 'docs/ROUTE_MAP_2026-07.md');
    writeFileSync(target, output, 'utf8');
    // stderr, not stdout, so --stdout output stays pipeable/diffable.
    process.stderr.write(`Wrote ${path.relative(repoRoot, target)} (${rows.length} routes)\n`);
}
