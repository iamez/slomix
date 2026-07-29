#!/usr/bin/env node
// Generates docs/ROUTE_MAP_2026-07.md from website/js/route-registry.js — the
// single source of truth for which frontend (legacy JS vs. React/modern)
// serves each hash route. Re-run after editing route-registry.js so the doc
// never drifts from the code the way a hand-written table would.
//
// Usage: node scripts/generate_route_map.mjs > docs/ROUTE_MAP_2026-07.md

import { readFileSync, readdirSync } from 'node:fs';
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
// home view is actually populated by initApp() in app.js calling
// loadHomePulseCards() (home.js) directly during startup, not through the
// route dispatch mechanism every other route uses. Static analysis of "what
// does initApp() call for the initial route" isn't reliably automatable the
// way the load()-callback scan is for every other route, so this one file is
// hand-verified instead (Codex review on #575).
const SPECIAL_CASES = {
    home: 'website/js/home.js (via loadHomePulseCards(), called directly from initApp() in app.js — not through load(), see comment in this script)',
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
function computeHashExample(def) {
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
        hashExample: computeHashExample(def),
        file: def.mode === VIEW_MODE.MODERN ? modernFileFor(def.viewId) : legacyFileFor(routeKey, def, legacyIndex),
    }))
    .sort((a, b) => a.routeKey.localeCompare(b.routeKey));

const lines = [];
lines.push('# Route Map — React vs. legacy JS');
lines.push('');
lines.push('**Generated by `scripts/generate_route_map.mjs` from `website/js/route-registry.js`');
lines.push('— do not hand-edit, re-run the generator after route-registry.js or the pages it');
lines.push('references change.**');
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

console.log(lines.join('\n'));
