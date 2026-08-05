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
 *   node scripts/audit_website_browser.mjs --out /tmp/audit
 *   AUDIT_BASE_URL=http://192.168.64.116:8000 node scripts/audit_website_browser.mjs
 *
 * Writes results.json + JPEG screenshots to the output directory. Never writes
 * into the repo.
 */
import { execFileSync } from 'node:child_process';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const { chromium } = await import(
    path.join(REPO_ROOT, 'website/frontend/node_modules/playwright/index.js')
).then((m) => m.default ?? m);

const BASE_URL = process.env.AUDIT_BASE_URL ?? 'http://127.0.0.1:8000';
const ANON_ONLY = process.argv.includes('--anon-only');
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

// Every route from docs/ROUTE_MAP_2026-07.md. Parametrised ones carry real
// values so they are actually exercised rather than bouncing off a guard — the
// stale-contract findings in the master review all live behind a param.
const ROUTES = [
    { name: 'home', hash: '' },
    { name: 'sessions', hash: '#/sessions' },
    { name: 'sessions2', hash: '#/sessions2' },
    { name: 'session-detail (date, multi-session)', hash: '#/session-detail/date/2026-08-04' },
    { name: 'leaderboards', hash: '#/leaderboards' },
    { name: 'form', hash: '#/form' },
    { name: 'maps', hash: '#/maps' },
    { name: 'weapons', hash: '#/weapons' },
    { name: 'records (alias)', hash: '#/records' },
    { name: 'record-book', hash: '#/record-book' },
    { name: 'hall-of-fame', hash: '#/hall-of-fame' },
    { name: 'awards', hash: '#/awards' },
    { name: 'profile (owner)', hash: '#/profile/E587CA5F' },
    { name: 'profile (other)', hash: '#/profile/D8423F90' },
    { name: 'skill-rating', hash: '#/skill-rating' },
    { name: 'rivalries', hash: '#/rivalries' },
    { name: 'story', hash: '#/story' },
    { name: 'replay', hash: '#/replay' },
    { name: 'retro-viz', hash: '#/retro-viz' },
    { name: 'tonight', hash: '#/tonight' },
    { name: 'proximity', hash: '#/proximity' },
    { name: 'proximity-player', hash: '#/proximity/player/D8423F90' },
    { name: 'proximity-replay', hash: '#/proximity/round/11175' },
    { name: 'proximity-teams', hash: '#/proximity/round/11175/teams' },
    { name: 'smart-stats-diag', hash: '#/smart-stats-diag' },
    { name: 'greatshot', hash: '#/greatshot/demos' },
    { name: 'uploads', hash: '#/uploads' },
    { name: 'availability', hash: '#/availability' },
    { name: 'admin', hash: '#/admin' },
];

// ---------------------------------------------------------------------------
// Session cookie
// ---------------------------------------------------------------------------

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
    return execFileSync(path.join(REPO_ROOT, 'venv/bin/python'), ['-c', script], {
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

const passes = ANON_ONLY ? ['anon'] : ['anon', 'owner'];
let ownerCookie = null;
if (passes.includes('owner')) {
    ownerCookie = mintOwnerSession();
}

for (const pass of passes) {
    const context = await browser.newContext({ ignoreHTTPSErrors: true });
    if (pass === 'owner') {
        const { hostname } = new URL(BASE_URL);
        await context.addCookies([
            { name: 'session', value: ownerCookie, domain: hostname, path: '/' },
        ]);
    }
    for (const route of ROUTES) {
        for (const viewport of VIEWPORTS) {
            const r = await auditRoute(context, route, viewport, pass, OUT_DIR);
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
                `  ${pass.padEnd(5)} ${route.name.padEnd(38)} ${viewport.name.padEnd(13)}` +
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
