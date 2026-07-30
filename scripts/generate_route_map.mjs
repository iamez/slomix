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
// home view is actually populated by initApp()'s criticalLoads array in
// app.js — five functions across four files, called directly during startup,
// not through the route dispatch mechanism every other route uses:
// loadHomePulseCards (home.js), loadOverviewStats (defined in app.js itself,
// not exported), updateLiveSession (live-status.js), and loadQuickLeaders +
// loadRecentMatches (leaderboard.js). Static analysis of "what does
// initApp() call for the initial route" isn't reliably automatable the way
// the load()-callback scan is for every other route, so this one is
// hand-verified instead (Codex review on #575).
const SPECIAL_CASES = {
    home: 'website/js/home.js + website/js/app.js + website/js/live-status.js + website/js/leaderboard.js (loadHomePulseCards / loadOverviewStats / updateLiveSession / loadQuickLeaders + loadRecentMatches, all called directly from initApp() in app.js — not through load(), see comment in this script)',
};

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
    if (SPECIAL_CASES[routeKey]) return SPECIAL_CASES[routeKey];
    const source = def.load.toString();
    const calls = [...source.matchAll(/legacy\.(\w+)\(/g)].map((m) => m[1]);
    const files = new Set(calls.map((name) => legacyIndex.get(name)).filter(Boolean));
    if (files.size === 0) {
        return calls.length ? `unresolved (calls: ${calls.join(', ')})` : '(no legacy.* call in load())';
    }
    return [...files].join(', ');
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
