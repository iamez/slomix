#!/usr/bin/env python3
"""Write the PR bodies for the review slices into docs/review/SLICES.md.

One `## <slice>` section per slice in scripts/review_slices.sh: the shared
preamble (what a slice is, that it is never merged, where the review guide
is) plus the area's own focus list. Re-run after editing FOCUS;
`review_slices.sh prs` extracts the section for each PR body.
"""
from __future__ import annotations

import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "review" / "SLICES.md"

PREAMBLE = """\
**Review vehicle — NEVER MERGE.** Production runs v1.39.0; this PR's diff is
exactly what changed in *{area}* since then. The base branch is `main` with
these paths put back to their v1.39.0 state (`scripts/review_slices.sh`), so
the checkout you review in is the full current repository while the diff
stays under the review size limit.

Read `docs/REVIEW_GUIDE.md` first: it lists the conventions that look like
bugs and are deliberate, the items already known to be open, and how proofs
are run here. Findings are triaged with `docs/process/MANDELBROT_RCA.md`;
please tag each with the checklist item it belongs to (1–12).

Size at cut time: {files} files, {lines} changed lines (limit 500 / 8 000).
"""

FOCUS: dict[str, str] = {
    "01-proximity-spiderweb-lua": """\
**Area: proximity capture (Lua v6.14), parser, storytelling/moments services, the spider-web layer 1 and replay.**
Context: `docs/SPIDERWEB_STATUS.md`, `docs/PROXIMITY_SPIDER_WEB_SPEC_2026-07.md` §4–§8, `docs/design/17_PROXIMITY_POPIS.md`.
- `proximity/lua/proximity_tracker.lua`: the damage hook fires at the top of `G_Damage` (pre-hit health, every entity incl. `script_mover`); the frame-health section (`FM wall / self`); `recordVehicleDamage`; the unified start-state gate. Look for work on the frame path that could stall the server (the sweep in `stats_discord_webhook.lua` is a known one).
- `proximity/parser/parser.py`: R2 differential is never recomputed; `first/last_escort_time`; `VehicleDestroyed`.
- `website/backend/services/round_web_service.py`: life resolution (§4.3, half-open death boundary), staleness measured from `t` not from death, `derive_velocity`/`build_edges` z-axis, the empty-round shortcut returning every key, clock-quality verdicts.
- `website/backend/services/storytelling/*`: camp episodes, escort mover detector thresholds (from measurement, control ≈ 21 %), kill impact; `advanced_metrics.py` must not weight stats artificially.
- Migrations 078–082 touched by this area are immutable; judge the code that reads them.
""",
    "02-backend-routers": """\
**Area: FastAPI routers (except proximity/storytelling/replay).**
- The `response_model` layer added in phase 2–4 (220 handlers still untyped are listed in `tests/data/response_model_gap.txt`; the file is a ratchet). Typed handlers must not drop fields the legacy JS reads — `docs/parity/keymap.json` is the map.
- `sessions_router.py`: `round_time` as a string (four incidents; `'2026-06-11 4918'` parsed two days off with no error) — one site near line ~2400 was still open.
- Sessions by `gaming_session_id`, never by date; `round_number IN (1, 2)`; durations via `shared/round_time.py`.
- Auth/admin gates: `dependencies.py:_configured_admin_ids`, the 401 vs 403 distinction, rate limits (`/auth/players/search` 30/min).
- Snowflake ids must leave as strings (`auth.py` does, `uploads.py` did not — #849).
- Handlers that answer 200 + `{"status":"error"}` are deliberate (see the guide); a handler that answers 200 with an EMPTY body on a DB outage is not.
""",
    "03-spa-core-lib": """\
**Area: the new SPA's data layer — `src/app/lib` (queries, types, api client, formatting, wrapped card).**
Context: `docs/design/06_ARHITEKTURA.md`, `09_KAKO_DOKAZEMO_PARITETO.md`.
- `types.ts` is hand-written against `docs/api/openapi.json` recordings: types must be the UNION of observed shapes (older sessions lack fields; `total_votes` absent ≠ 0).
- `apiGet` throws only on `!res.ok`; callers must handle `status: "error"` bodies as data.
- Query keys and `staleTime` per endpoint; no unbounded polling of cold backbones (`/proximity/players` 12.7 s cold vs 8 ms warm).
- `guidKey` (8-char) vs full 32-char guid: which functions take which.
- `wrappedCard.ts`: pure drawing function, no gradients/radius/shadows by rule (pinned by test).
""",
    "04-spa-core-shell": """\
**Area: the SPA shell — components, layout primitives, routes, main entry, CSS tokens.**
Context: `docs/design/11` (local) is summarised in `website/frontend/AGENTS.md`.
- `components/ui.tsx`: `Absent` must refuse a reason-less absence (empty array, empty fragment = silence); `Unavailable`, `Pending` separate.
- `routes.data.json` is the one route table (Node reads JSON); `routes.ts` redirects (`/replay` → `/proximity`, `PARAM_REDIRECTS`), the hash shim for legacy `#/…` URLs.
- `AppShell` nav prefixes; hidden routes (`compare`, `wrapped`) reachable only by link.
- Tokens: Tailwind v4 `@theme static` (unreferenced tokens were dropped at runtime once); the vocabulary/token ratchets.
- `PickPlayer`: 300 ms debounce against a 30/min endpoint.
""",
    "05-spa-pages-a": """\
**Area: SPA pages — home, players, leaderboards, records, rivalries, matchups, team comparison, compare, wrapped, about/admin, awards, maps.**
Context: `docs/design/12_PRESLIKAVA_ROUT.md`, `docs/parity/keymap.json` (`data-parity` keys).
- Every panel names its absent state with a reason; no panel renders zeros for `no_data`.
- Profile: proximity link carries the full guid; `compare` scores `played` higher-wins (owner, 2026-09-06); wrapped facts are also text.
- About/admin: diagnostics requested only for an admin, the response is a union (degraded states from #911 are a known follow-up).
- Pages must run against 3–5 DIFFERENT sessions/players — a fixture from one recording hides the short form.
""",
    "06-spa-pages-b": """\
**Area: SPA pages — sessions (Stats 2.0 tabs, drilldown), proximity (6 slices + outcome instruments), spider web SW-1.**
Context: `docs/design/17_PROXIMITY_POPIS.md`, `docs/SPIDERWEB_STATUS.md`, `docs/design/18` (local, summarised in PLAN).
- Session basics/awards/detail come through one gate (`SESSION_ROUNDS_SQL`); KIS `null` = not covered, not zero; 14 sessions without counted rounds are 404 by design.
- Proximity pages compare full guids; `Absent` for players without capture is a valid render.
- `SpiderWebPage`: point of view is a SERVER parameter; WITHHELD before any clock-quality state; what SW-1 leaves out is named in the footer.
- Drilldown: the four kinds of claim (measured / derived / withheld / unavailable) stay apart.
""",
    "07-spa-pages-c": """\
**Area: SPA pages — availability (polls, market, admin half), uploads (library, resumable), greatshot, live.**
- Availability: linked forms via link token, promotions, betting pool/wallet, admin open/settle (#915); Discord ids as strings.
- Uploads: single-shot ≤ 50 MiB with XHR progress, resumable init/PATCH/finalize with 409 resync, HEAD resync, stall guard, abort as fire-and-forget DELETE; delete is two-step; the uploader must see the delete button for their OWN file (snowflake-as-int bug, #849).
- Greatshot: anonymous 401 is a state, not an error; `highlights/render` is unconfigured on dev (known).
- Live: feed cursor, no generic message bus; reducer state is ephemeral by design.
""",
    "08-backend-services": """\
**Area: backend services, middleware, main, dependencies, caching (everything outside routers and proximity/storytelling/replay).**
- `dependencies.py`: DB pool init, admin allowlist, the adapter that must THROW on outage (11 endpoints once returned 200 with empty bodies).
- `http_cache_middleware.py` TTLs (default 120 s, live 15 s, leaderboard 300 s) and their interaction with bot-side `stats_cache` (no cross-process invalidation — known, doc 21).
- Skill rating / composite coverage flags from SOURCES not from zeros (#848); `sds` stops at ≤ 40, not 0.
- Time-field repair services and the plausibility audit (`Rule.armed_from`, no acknowledged rule may silence a fresh recurrence).
- Greatshot job service workers and startup gating; upload services (resumable session state).
""",
    "09-legacy-js-bot-db-tools": """\
**Area: legacy JS (production frontend), Discord bot changes, migrations 078–082, tools, CI workflows, install/deploy scripts, root files.**
- Legacy JS gets fixes only (design decision 2026-08-23); `fetchJSON` throws on any non-2xx.
- Bot: `!teams` collision with another bot (multi-bot guild); `HealthMonitor` never started; SSH monitor single loop; `WebhookEventQueue` dedup.
- Migrations: immutable; `078` view `player_match_stats`; `080` GIN; `082` vehicle move times (needs `website_app` GRANT pattern).
- `tools/slomix_rcon.py`: `botnames` reads `POSTGRES_*` with fallback; RCON never `lua_restart`.
- `.github/workflows`: whitespace gate (`git diff --check`), repo-hygiene 1 MB limit, ShellCheck scope.
""",
    "10-frontend-legacy-react": """\
**Area: the OLDER React tree under `website/frontend/src` (pages/components/lib outside `src/app`).**
Kept only as the legacy route host (`npm run build`); it is not the new site and receives fixes only. Findings here are welcome but rank below `src/app`.
""",
    "11-frontend-e2e-config": """\
**Area: Playwright e2e, vite/vitest/tsconfig/eslint configuration, public assets.**
- e2e runs against a live backend (`SMOKE_BASE_URL`); the owner project is a signed-in NON-admin (sentinel id −1); `SAMPLES`/`SAMPLES_THIN` must fill every `:param` with a real id (8-char for pages, 32-char for proximity).
- Two vite configs = two build targets; `generate:api` runs from `pre*` hooks.
""",
    "12-spa-tests-pages": """\
**Area: SPA page tests and fixtures.**
- A test must be able to SEE its subject: count carriers, not `x in text`; fixtures are recordings (union of shapes); a fixture cannot fail on a value it does not contain — look for tests that pass on an empty collection.
- Mutation evidence: does each guard have a test that fails when the guard is removed?
""",
    "13-spa-tests-lib-components": """\
**Area: SPA lib/component tests, vocabulary/token/route/fixture-coverage ratchets.**
- Ratchets use `toBe` on a budget, never `toBeLessThanOrEqual`; the budget only goes down.
- `fixturesCoverage.test` derives fixture names from path literals; `routes.test.ts` checks PAGES ↔ `built`.
- Guards over source text must introspect objects, not grep prose.
""",
    "14-scripts-a": """\
**Area: scripts a–l (audits, backtests, build tools, e2e sentinel, health check, frame-health report).**
- `audit_website_browser.mjs`: SPA-aware dead-state detection, sample params, page-closed-after-timeout hardening.
- `check_manual_types_against_openapi.py`: schema is not the arbiter (lies both ways).
- `data_plausibility_audit.py`: rules with `armed_from`; exit codes.
- `health_check.sh` is read-only and unscheduled (known).
""",
    "15-scripts-b": """\
**Area: scripts m–z (record_api_corpus, repair_playtime, route audit list, validation family, review_slices, twins generator).**
- `validation_family.py`: shared draws for family-wise claims; `nan` comparisons must not pass silently.
- `repair_playtime_against_capture.py`: measure scope, back up rows, dry-run diff, write only what the source proves.
- `review_slices.sh`: pathspec `*` matches `/`; `:(glob)` for one level.
""",
    "16-python-tests-a": """\
**Area: integration, Lua, smoke and data tests (everything under `tests/` except `tests/unit`).**
- `test_endpoint_gap.py`: the extractor must not count a truncated prefix as covered; templated writes must not register their prefix.
- Lua tests parse + runtime-semantics smoke: `return 0` vs `isstring` hook-chain trap.
""",
    "17-python-tests-unit-a": """\
**Area: unit tests a–h.**
- Look for tests that cannot see their subject (grep-shaped assertions), controls that never fail, and `pytest` fixtures that mask a DB outage as empty data.
""",
    "18-python-tests-unit-b": """\
**Area: unit tests i–o.**
- Same lens as 17: a guarantee check must not be able to CAUSE the failure it detects (the empty-collection case); mutation evidence per guard.
""",
    "18b-python-tests-unit-b2": """\
**Area: unit tests p–r (parity keymap, pre-push secret guard, proximity, response models, round time).**
- `test_pre_push_secret_guard.py` fixtures document the four credential shapes the hook still misses.
- `test_parity_keymap.py`: a route `built` in `routes.data.json` cannot carry `phase-N`.
""",
    "19-python-tests-unit-c": """\
**Area: unit tests s–z and non-test helpers under `tests/unit`.**
- Session scoring, skill rating, storytelling, time fields, twins, upload validation. Same lens as 17.
""",
}


def measure(name: str) -> tuple[int, int]:
    out = subprocess.run(["bash", "scripts/review_slices.sh", "measure"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout
    for line in out.splitlines():
        if line.startswith(name + " "):
            m = re.search(r"files=\s*(\d+) lines=\s*(\d+)", line)
            if m:
                return int(m.group(1)), int(m.group(2))
    return 0, 0


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    parts = ["# Review slices — PR bodies\n\nGenerated by `scripts/review_slice_bodies.py`; "
             "`scripts/review_slices.sh prs` posts each `##` section as the body of its draft PR. "
             "Sizes are measured at generation time against `origin/main`.\n"]
    for name, focus in FOCUS.items():
        files, lines = measure(name)
        area = name.split("-", 1)[1].replace("-", " ")
        parts.append(f"\n## {name}\n\n" + PREAMBLE.format(area=area, files=files, lines=lines) + "\n" + focus)
        print(f"{name}: {files} files, {lines} lines")
    OUT.write_text("".join(parts), encoding="utf-8")


if __name__ == "__main__":
    main()
