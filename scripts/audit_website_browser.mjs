/**
 * Browser audit of the Slomix web app — every route, four viewports, anonymous
 * and signed in.
 *
 * Why this exists: the reviews in docs/ were written against a browser the dev
 * box could not run, so their findings could never be re-checked here and drifted
 * out of date. This makes the sweep repeatable, so the next audit is a diff
 * rather than a fresh argument.
 *
 * Prerequisites (see website/frontend/playwright.config.ts for the full note):
 *   1. npm --prefix website/frontend ci
 *   2. npx --prefix website/frontend playwright install --with-deps chromium
 *   3. the site is being served — normally the etlegacy-web systemd unit
 *
 * Usage, from the repo root:
 *   node scripts/audit_website_browser.mjs                    # both passes
 *   node scripts/audit_website_browser.mjs --anon-only
 *   node scripts/audit_website_browser.mjs --owner-only
 *   node scripts/audit_website_browser.mjs --out /tmp/audit
 *   AUDIT_BASE_URL=http://192.168.64.116:8000 node scripts/audit_website_browser.mjs
 *
 * Writes results.json + JPEG screenshots to the output directory. Never writes
 * into the repo.
 */
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const { chromium } = await import(
    path.join(REPO_ROOT, 'website/frontend/node_modules/playwright/index.js')
).then((m) => m.default ?? m);

const BASE_URL = process.env.AUDIT_BASE_URL ?? 'http://127.0.0.1:8000';
const ANON_ONLY = process.argv.includes('--anon-only');
const MANIFEST = process.argv.includes('--manifest');
// --app sweeps the NEW standalone SPA under /app instead of the legacy hash
// site. Same passes, same viewports, same manifest format, so the two can be
// diffed against each other (docs/design/09 §H2).
const APP_MODE = process.argv.includes('--app');
const OWNER_ONLY = process.argv.includes('--owner-only');
const OUT_DIR = (() => {
    const i = process.argv.indexOf('--out');
    return i !== -1 && process.argv[i + 1]
        ? process.argv[i + 1]
        : path.join(process.env.TMPDIR ?? '/tmp', 'slomix-audit');
})();

// Viewports. 768x1024 is the one the master review found broken everywhere and
// 390x844 is the only phone size in the set; the two desktop widths are there to
// prove a fix at one width did not break another.
const VIEWPORTS = [
    { name: 'desktop-1920', width: 1920, height: 1080, shot: false },
    { name: 'desktop-1440', width: 1440, height: 900, shot: true },
    { name: 'tablet-768', width: 768, height: 1024, shot: true },
    { name: 'phone-390', width: 390, height: 844, shot: false },
];

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
const ROUTES = [
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
async function assertRegistryCovered() {
    const registry = await import(path.join(REPO_ROOT, 'website/js/route-registry.js'));
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
function appRoutes() {
    const table = JSON.parse(
        readFileSync(path.join(REPO_ROOT, 'website/frontend/src/app/routes.data.json'), 'utf8'),
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

// ---------------------------------------------------------------------------
// Session cookie
// ---------------------------------------------------------------------------

// Legacy or app, chosen once so every pass below sweeps the same list.
const ACTIVE_ROUTES = APP_MODE ? appRoutes() : ROUTES;
if (!APP_MODE) await assertRegistryCovered();

/**
 * Locate the interpreter, in the same order and with the same override as
 * scripts/db_backup.sh — this repo has had several venv layouts, so hardcoding
 * one made the audit fail on otherwise-valid checkouts.
 */
function resolvePython() {
    if (process.env.SLOMIX_PYTHON) return process.env.SLOMIX_PYTHON;
    for (const candidate of ['venv-web/bin/python', 'venv/bin/python', '.venv/bin/python']) {
        const full = path.join(REPO_ROOT, candidate);
        if (existsSync(full)) return full;
    }
    return 'python3';
}

/**
 * Mint a Starlette SessionMiddleware cookie for the owner.
 *
 * Delegated to Python rather than reimplemented: itsdangerous derives its key
 * and encodes its timestamp in ways that are easy to get subtly wrong, and the
 * server verifies with the real library. tests/security/test_real_stack_security.py
 * builds the same value the same way.
 */
function mintOwnerSession() {
    const script = `
import base64, json, os, sys
sys.path.insert(0, ${JSON.stringify(REPO_ROOT)})
from dotenv import dotenv_values
import itsdangerous
env = dotenv_values(os.path.join(${JSON.stringify(REPO_ROOT)}, "website/.env"))
secret = env.get("SESSION_SECRET") or os.getenv("SESSION_SECRET")
if not secret:
    raise SystemExit("SESSION_SECRET not found in website/.env")
payload = base64.b64encode(json.dumps({
    "user": {"id": "231165917604741121", "username": "audit-owner"}
}).encode("utf-8"))
print(itsdangerous.TimestampSigner(str(secret)).sign(payload).decode("utf-8"))
`;
    return execFileSync(resolvePython(), ['-c', script], {
        encoding: 'utf-8',
    }).trim();
}

// ---------------------------------------------------------------------------
// Per-page collection
// ---------------------------------------------------------------------------

/**
 * A 401/403 from /auth/* is this app's documented contract for an anonymous
 * visitor, not a fault — logging_middleware.py:40 downgrades it deliberately.
 * Anything else with those statuses is a real finding, so the exemption is
 * scoped by URL rather than by message text. Same rule as
 * website/frontend/e2e/smoke.spec.ts.
 */
function isExpectedAuthNoise(url, text) {
    return /\b(401|403)\b/.test(text ?? '') && (url ?? '').includes('/auth/');
}

/** Text that should never reach a user's screen. */
const RENDER_ROT = [
    '[object Object]',
    'undefined',
    'NaN',
    'Invalid Date',
    'null,',
];

async function collectPageFindings(page) {
    return page.evaluate((rot) => {
        const out = { renderRot: [], overflow: null, deadState: null, a11y: [] };

        // offsetParent is NOT a visibility test for every element: <option> has
        // no layout box and always reports null, so filtering on it silently
        // skipped the exact place the Record Book bug lives (18 "[object Object]"
        // options inside #records-map-filter). Walk the ancestor chain instead.
        const visCache = new WeakMap();
        const isUserVisible = (el) => {
            if (!el) return false;
            if (visCache.has(el)) return visCache.get(el);
            let ok = true;
            for (let n = el; n && n !== document.documentElement; n = n.parentElement) {
                if (n.hasAttribute && n.hasAttribute('hidden')) { ok = false; break; }
                const cs = getComputedStyle(n);
                if (cs.display === 'none' || cs.visibility === 'hidden') { ok = false; break; }
            }
            visCache.set(el, ok);
            return ok;
        };

        // --- render integrity -------------------------------------------------
        const seen = new Map();
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
        for (let n = walker.nextNode(); n; n = walker.nextNode()) {
            const value = n.nodeValue ?? '';
            if (!value.trim()) continue;
            const el = n.parentElement;
            if (!isUserVisible(el)) continue;
            for (const needle of rot) {
                if (!value.includes(needle)) continue;
                const where = el.tagName.toLowerCase() + (el.id ? `#${el.id}` : '');
                const key = `${needle}@${where}`;
                seen.set(key, (seen.get(key) ?? 0) + 1);
            }
        }
        out.renderRot = [...seen].map(([key, count]) => {
            const [needle, where] = key.split('@');
            return { needle, where, count };
        });

        // --- horizontal overflow ---------------------------------------------
        const doc = document.documentElement;
        if (doc.scrollWidth > doc.clientWidth + 1) {
            // Name the widest offenders so the finding is actionable rather than
            // just "the page is too wide".
            const culprits = [];
            for (const el of document.querySelectorAll('body *')) {
                const r = el.getBoundingClientRect();
                if (r.width === 0 || !isUserVisible(el)) continue;
                if (r.right > doc.clientWidth + 1) {
                    culprits.push({
                        sel: el.tagName.toLowerCase() + (el.id ? `#${el.id}` : ''),
                        overBy: Math.round(r.right - doc.clientWidth),
                    });
                }
            }
            culprits.sort((a, b) => b.overBy - a.overBy);
            out.overflow = {
                scrollWidth: doc.scrollWidth,
                clientWidth: doc.clientWidth,
                overBy: doc.scrollWidth - doc.clientWidth,
                culprits: culprits.slice(0, 5),
            };
        }

        // --- dead state -------------------------------------------------------
        // Two DIFFERENT things, kept apart on purpose. An unanchored
        // /loading \w+\.\.\./ over the whole view matched any nested spinner
        // deeper down the page and reported fully-rendered routes as dead —
        // #/profile renders 1,579 characters of real content and was still
        // flagged. A false P0 is worse than a missed one, so "dead" now means
        // the view rendered NOTHING, and a stuck panel is reported separately
        // with the element that owns it.
        out.stuckPanels = [];
        const active = document.querySelector('.view-section.active');
        if (!active) {
            out.deadState = 'no .view-section.active';
        } else {
            const text = (active.innerText ?? '').trim();
            if (!text) {
                out.deadState = 'active view rendered empty';
            } else if (text.length < 120 && /loading/i.test(text)) {
                out.deadState = `whole view is a placeholder: ${text.slice(0, 80)}`;
            }
            // Leaf-ish elements whose OWN text is still a placeholder after
            // settle. Bounded to the smallest element carrying the text so one
            // spinner is not reported once per ancestor.
            for (const el of active.querySelectorAll('*')) {
                if (!isUserVisible(el) || el.children.length > 0) continue;
                const t = (el.textContent ?? '').trim();
                if (t && t.length < 60 && /^loading\b|\bloading\.\.\.$/i.test(t)) {
                    out.stuckPanels.push({
                        where: el.parentElement
                            ? el.parentElement.tagName.toLowerCase() +
                              (el.parentElement.id ? `#${el.parentElement.id}` : '')
                            : el.tagName.toLowerCase(),
                        text: t.slice(0, 60),
                    });
                }
            }
            out.stuckPanels = out.stuckPanels.slice(0, 6);
        }

        // --- basic a11y -------------------------------------------------------
        const accessibleName = (el) =>
            (el.getAttribute('aria-label') || el.textContent || el.getAttribute('title') || '').trim();
        let unnamed = 0;
        for (const el of document.querySelectorAll('button, a[href]')) {
            if (!isUserVisible(el)) continue;
            if (!accessibleName(el)) unnamed += 1;
        }
        if (unnamed) out.a11y.push({ check: 'control without accessible name', count: unnamed });

        let noAlt = 0;
        for (const img of document.querySelectorAll('img')) {
            if (!isUserVisible(img)) continue;
            if (img.getAttribute('alt') === null) noAlt += 1;
        }
        if (noAlt) out.a11y.push({ check: 'img without alt', count: noAlt });

        let unlabelled = 0;
        for (const input of document.querySelectorAll('input, select, textarea')) {
            if (!isUserVisible(input) || input.type === 'hidden') continue;
            const labelled =
                input.getAttribute('aria-label') ||
                input.getAttribute('placeholder') ||
                (input.id && document.querySelector(`label[for="${CSS.escape(input.id)}"]`));
            if (!labelled) unlabelled += 1;
        }
        if (unlabelled) out.a11y.push({ check: 'input without label', count: unlabelled });

        const ids = new Map();
        for (const el of document.querySelectorAll('[id]')) {
            ids.set(el.id, (ids.get(el.id) ?? 0) + 1);
        }
        const dupes = [...ids].filter(([, n]) => n > 1).map(([id, n]) => `${id}×${n}`);
        if (dupes.length) out.a11y.push({ check: 'duplicate id', count: dupes.length, detail: dupes.slice(0, 5) });

        return out;
    }, RENDER_ROT);
}

// --- H2 manifest mode (docs/design/09): one evaluate per route that freezes
// what the page SHOWS — api paths, panel titles, table columns, canvases,
// tabs, data-parity keys. Run once against legacy to produce
// docs/parity/inventory.json; run against /app and feed both to
// scripts/parity_diff.mjs.
async function collectManifest(page) {
    return page.evaluate(() => {
        const norm = (s) => (s ?? '').replace(/\s+/g, ' ').trim();
        // The legacy SPA keeps every view's panels in the DOM and hides the
        // inactive ones — without a visibility walk the manifest freezes the
        // UNION of all routes (measured: 17 identical panels everywhere).
        const visCache = new WeakMap();
        const isUserVisible = (el) => {
            if (!el) return false;
            if (visCache.has(el)) return visCache.get(el);
            let ok = true;
            for (let n = el; n && n !== document.documentElement; n = n.parentElement) {
                if (n.hasAttribute && n.hasAttribute('hidden')) { ok = false; break; }
                const cs = getComputedStyle(n);
                if (cs.display === 'none' || cs.visibility === 'hidden') { ok = false; break; }
            }
            visCache.set(el, ok);
            return ok;
        };
        const out = { panelTitles: [], tableColumns: {}, canvasCount: 0, tabs: [], dataParityKeys: [] };
        // Panels: legacy glass-cards key by heading text; new pages carry
        // data-parity keys (collected separately below).
        for (const card of document.querySelectorAll('.glass-card, .card, section')) {
            if (!isUserVisible(card)) continue;
            const h = card.querySelector('h1,h2,h3,h4,.card-title,.section-title');
            const t = norm(h && h.textContent);
            if (t) out.panelTitles.push(t);
        }
        let anonTable = 0;
        for (const table of document.querySelectorAll('table')) {
            if (!isUserVisible(table)) continue;
            const cols = [...table.querySelectorAll('thead th, tr:first-child th')].map((th) => norm(th.textContent)).filter(Boolean);
            if (!cols.length) continue;
            const key = table.id || `table-${anonTable++}`;
            out.tableColumns[key] = cols;
        }
        out.canvasCount = [...document.querySelectorAll('canvas')].filter(isUserVisible).length;
        for (const tab of document.querySelectorAll('[role="tab"], .tab, .tab-button, .nav-tabs a')) {
            if (!isUserVisible(tab)) continue;
            const t = norm(tab.textContent);
            if (t) out.tabs.push(t);
        }
        for (const el of document.querySelectorAll('[data-parity]')) {
            if (!isUserVisible(el)) continue;
            out.dataParityKeys.push(el.getAttribute('data-parity'));
        }
        out.panelTitles = [...new Set(out.panelTitles)].sort();
        out.tabs = [...new Set(out.tabs)].sort();
        out.dataParityKeys = [...new Set(out.dataParityKeys)].sort();
        return out;
    });
}

async function manifestRoute(context, route) {
    const page = await context.newPage();
    await page.setViewportSize({ width: 1440, height: 900 });
    const apiPaths = new Set();
    page.on('request', (req) => {
        try {
            const u = new URL(req.url());
            if (u.pathname.startsWith('/api/')) apiPaths.add(u.pathname);
        } catch { /* data: etc. */ }
    });
    try {
        await page.goto(`${BASE_URL}/${route.hash}`, { waitUntil: 'networkidle', timeout: 30_000 });
    } catch { /* manifest still collects what rendered */ }
    await page.waitForTimeout(2500);
    const dom = await collectManifest(page);
    await page.close();
    return { apiPaths: [...apiPaths].sort(), ...dom };
}

if (MANIFEST) {
    const browser = await chromium.launch();
    const context = await browser.newContext();
    const ownerCookie = mintOwnerSession();
    if (ownerCookie) {
        const { hostname } = new URL(BASE_URL);
        await context.addCookies([
            { name: 'session', value: ownerCookie, domain: hostname, path: '/' },
        ]);
    }
    const routesOut = {};
    for (const route of ACTIVE_ROUTES) {
        routesOut[route.name] = await manifestRoute(context, route);
        process.stdout.write(`  manifest ${route.name.padEnd(38)} ${routesOut[route.name].apiPaths.length} api, ${routesOut[route.name].panelTitles.length} panels\n`);
    }
    await context.close();
    await browser.close();
    mkdirSync(OUT_DIR, { recursive: true });
    const outFile = path.join(OUT_DIR, 'inventory.json');
    writeFileSync(outFile, JSON.stringify({ baseUrl: BASE_URL, generated: new Date().toISOString(), routes: routesOut }, null, 2));
    process.stdout.write(`\n  manifest -> ${outFile}\n`);
    process.exit(0);
}

async function auditRoute(context, route, viewport, pass, outDir) {
    const page = await context.newPage();
    await page.setViewportSize({ width: viewport.width, height: viewport.height });

    const consoleErrors = [];
    const requests = [];
    const badResponses = [];

    page.on('console', (msg) => {
        if (msg.type() !== 'error' && msg.type() !== 'warning') return;
        const url = msg.location()?.url ?? '';
        if (isExpectedAuthNoise(url, msg.text())) return;
        consoleErrors.push({ level: msg.type(), text: msg.text().slice(0, 300) });
    });
    page.on('pageerror', (err) => {
        consoleErrors.push({ level: 'pageerror', text: String(err.message).slice(0, 300) });
    });
    page.on('request', (req) => requests.push(req.url()));
    page.on('requestfailed', (req) => {
        badResponses.push({ url: req.url(), status: 'failed', why: req.failure()?.errorText });
    });
    page.on('response', (res) => {
        const status = res.status();
        if (status < 400) return;
        if (isExpectedAuthNoise(res.url(), String(status))) return;
        badResponses.push({ url: res.url(), status });
    });

    const started = Date.now();
    let navError = null;
    try {
        await page.goto(`${BASE_URL}/${route.hash}`, { waitUntil: 'networkidle', timeout: 30_000 });
    } catch (err) {
        navError = String(err.message).split('\n')[0];
    }
    // Legacy loaders run after networkidle (the router discards their promise),
    // so give them a beat before reading the DOM.
    await page.waitForTimeout(1800);
    const loadMs = Date.now() - started;

    const findings = navError
        ? { renderRot: [], overflow: null, deadState: `navigation failed: ${navError}`, stuckPanels: [], a11y: [] }
        : await collectPageFindings(page);

    // Duplicate requests expose the same class of problem as the raw count, but
    // more specifically: the same URL fetched twice in one page load.
    // The rate limiter counts /api/ and /auth/ ONLY
    // (rate_limit_middleware.py:251), so the raw request count says nothing
    // about the budget — it is dominated by JS, CSS and images. Recording both
    // stops the next reader drawing the alarming conclusion from the wrong
    // number, which is exactly what happened on the first run of this tool.
    const apiRequestCount = requests.filter((u) => {
        const { pathname } = new URL(u);
        return pathname.startsWith('/api/') || pathname.startsWith('/auth/');
    }).length;

    const counts = new Map();
    for (const u of requests) counts.set(u, (counts.get(u) ?? 0) + 1);
    const duplicates = [...counts]
        .filter(([, n]) => n > 1)
        .map(([url, n]) => ({ url: url.replace(BASE_URL, ''), times: n }))
        .sort((a, b) => b.times - a.times)
        .slice(0, 5);

    let screenshot = null;
    if (viewport.shot && !navError) {
        const slug = `${pass}__${route.name.replace(/[^a-z0-9]+/gi, '-')}__${viewport.name}.jpg`;
        const file = path.join(outDir, 'shots', slug);
        await page.screenshot({ path: file, type: 'jpeg', quality: 55 });
        screenshot = path.join('shots', slug);
    }

    await page.close();

    return {
        route: route.name,
        hash: route.hash,
        pass,
        viewport: viewport.name,
        loadMs,
        requestCount: requests.length,
        apiRequestCount,
        duplicates,
        consoleErrors,
        badResponses,
        screenshot,
        ...findings,
    };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

mkdirSync(path.join(OUT_DIR, 'shots'), { recursive: true });

const browser = await chromium.launch();
const results = [];

// Each pass carries its own authentication decision as a flag. It used to be
// derived by comparing the label (`pass === 'owner'`) a few lines below the
// cookie code, which a static analyser reads as string equality in a
// security-sensitive context and reports as a timing attack (Codacy, critical —
// the actual finding on this PR). The label is not a secret: it is one of two
// literals, and it only ever names a screenshot file and a column of output.
// The flag is clearer regardless — the decision is stated once, where the passes
// are defined, instead of being re-derived from a string in the loop body.
const ANON_PASS = { label: 'anon', asOwner: false };
const OWNER_PASS = { label: 'owner', asOwner: true };
let passes = [ANON_PASS, OWNER_PASS];
if (ANON_ONLY) passes = [ANON_PASS];
// --owner-only re-checks the signed-in surfaces (admin, uploads, greatshot)
// without paying for the anonymous sweep first.
else if (OWNER_ONLY) passes = [OWNER_PASS];

const ownerCookie = passes.some((entry) => entry.asOwner) ? mintOwnerSession() : null;

for (const { label, asOwner } of passes) {
    // No ignoreHTTPSErrors: the audit targets a plain-HTTP dev server, so
    // turning off certificate validation bought nothing and made the tool
    // silently accept a bad certificate if it were ever pointed at HTTPS —
    // which is precisely the kind of thing an audit should report, not skip.
    const context = await browser.newContext();
    if (asOwner) {
        const { hostname } = new URL(BASE_URL);
        await context.addCookies([
            { name: 'session', value: ownerCookie, domain: hostname, path: '/' },
        ]);
    }
    for (const route of ACTIVE_ROUTES) {
        for (const viewport of VIEWPORTS) {
            const r = await auditRoute(context, route, viewport, label, OUT_DIR);
            results.push(r);
            const flags = [
                r.consoleErrors.length && `${r.consoleErrors.length} console`,
                r.badResponses.length && `${r.badResponses.length} http`,
                r.renderRot.length && `${r.renderRot.length} render-rot`,
                r.overflow && `overflow +${r.overflow.overBy}px`,
                r.deadState && 'DEAD',
                r.stuckPanels?.length && `${r.stuckPanels.length} stuck`,
            ].filter(Boolean);
            process.stdout.write(
                `  ${label.padEnd(5)} ${route.name.padEnd(38)} ${viewport.name.padEnd(13)}` +
                `${String(r.requestCount).padStart(4)} req (${String(r.apiRequestCount).padStart(3)} api)  ${flags.join(', ') || 'clean'}\n`,
            );
        }
    }
    await context.close();
}

await browser.close();

const outFile = path.join(OUT_DIR, 'results.json');
writeFileSync(outFile, JSON.stringify({ baseUrl: BASE_URL, generated: new Date().toISOString(), results }, null, 2));
process.stdout.write(`\n  ${results.length} checks -> ${outFile}\n`);
