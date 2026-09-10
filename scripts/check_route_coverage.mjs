#!/usr/bin/env node
/**
 * The route-coverage check, on its own, in about a second.
 *
 * WHY IT EXISTS SEPARATELY. `audit_website_browser.mjs` carries the guard
 * that joins its own route list to `website/js/route-registry.js` — the one
 * that caught "29 routes audited, 32 in the registry, 36 in the app table",
 * with `system`, `spider-web`, `greatshot-demo` and `upload-detail` never
 * once loaded by a sweep that called itself complete. But that script
 * imports Playwright at module load, so the guard could only run where a
 * browser was installed, which meant it ran when somebody remembered.
 *
 * A guard that runs when somebody remembers is the same guard that was
 * missing: the original 29-vs-36 gap survived for months under exactly that
 * condition (brother's review on #839). This runner needs Node and two
 * files, so CI can run it on every push.
 *
 * Exit codes: 0 agree · 2 disagree (assertRegistryCovered's own exit).
 */
import { ROUTES, appRoutes, assertRegistryCovered } from './route_audit_list.mjs';

await assertRegistryCovered();

// Not just the join: the app table has to be READABLE and non-empty too. A
// renamed or moved routes.data.json would otherwise sail through the check
// above (it only reads the legacy side) and fail later, in a browser, in a
// sweep nobody runs. `appRoutes()` throws on a missing file.
const app = appRoutes();
if (app.length === 0) {
  process.stderr.write('routes.data.json produced no routes\n');
  process.exit(2);
}

process.stdout.write(
  `route coverage ok — ${ROUTES.length} legacy entries against the registry, `
  + `${app.length} app routes readable\n`,
);
