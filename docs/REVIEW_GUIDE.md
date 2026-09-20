# Review guide — for the ultra review slices (2026-09-06)

Production runs **v1.39.0** (2026-08-19) and is frozen. Everything on `main`
since then — the new React site, the typed backend layer, proximity /
spider-web layer 1, the time-field repair, Lua v6.14 — is what a reviewer is
asked to judge before the production switch. That is ~93 k changed code lines
and a single review accepts 8 000, so the diff is cut into **area slices**:
each `review-base/NN-<area>` branch is `main` with that area's files put back
to their v1.39.0 state, and the review PR is `review-base/NN-<area>` → `main`.
The PR diff is exactly the area's change since production; the checkout the
reviewer works in is the full, current repository. **None of these PRs is
ever merged** — they are review vehicles. Slice index: PR titles start with
`review:`; the numbered order is the priority order.

## Read first (10 minutes)

`docs/CLAUDE.md` (rules and pitfalls) → `docs/HANDOFF-next.md` (where we
are, how proofs are run) → `docs/design/README.md` → `05` (why React, the
four rules) → `06` (architecture) → `09` (how parity is proven) → `12`
(route mapping) → `17` (proximity inventory) → `docs/SPIDERWEB_STATUS.md`.
`docs/PLAN.md` is the plan of record; `docs/BACKLOG.md` is the list of what is
already known to be open — read its first screen before reporting anything.

## Deliberate conventions that look like bugs (do not report as bugs)

- **HTTP 200 with `{"status": "error"}`** on ~25 handlers (20 of them
  proximity). Deliberate (owner, 2026-08-30); pinned by
  `tests/unit/test_ok_with_status_error_is_a_deliberate_convention.py`. The
  new SPA's `apiGet` throws only on `!res.ok`, so those bodies are handled as
  data. Report it only if a *new* handler adopts the pattern.
- **`round_number = 0` rows are still written and never read.** Every
  consumer filters `round_number IN (1, 2)` or uses the `player_match_stats`
  view. An unfiltered query doubles kills — that is the bug to look for, not
  the rows' existence.
- **`rounds.actual_time` is a target, not a measurement**; durations come from
  `shared/round_time.py`.
- **`tests/data/endpoint_gap.txt` has lines that will never close by building
  a page**: `/api/bets` (a legacy base string, no such endpoint), `/api/bets/
  market` (admin POST kept in legacy by decision), `/api/stats/sessions`
  (closes when legacy JS retires), `/api/uploads/{id}/download` (functionally
  covered via the server's `download_url`; only the literal is absent). Each
  line carries its reason in the file. A number that went *up* on 2026-09-06
  (3 → 13) was a correction of the extractor (`_FE_FULL_PATH_RE`: a truncated
  prefix used to count as covered), not a regression.
- **Absent vs unavailable vs loading** are three states by design
  (`components/ui.tsx`: `Absent` requires a reason; `Unavailable` is a failed
  request). A panel that renders a reason is a valid render, not an empty
  page.
- **The e2e "owner" project is not an admin**: admin is an env allowlist of
  Discord ids (`website/backend/dependencies.py:_configured_admin_ids`), the
  sentinel id −1 is not in it. Admin rendering is proven in vitest with a
  recording made as a real admin; Playwright proves only the gate.
- **Two build targets**: `npm run build` is the legacy route host, the SPA is
  `npm run build:app`. `src/api/generated/openapi.d.ts` is generated and
  gitignored; the npm scripts regenerate it via `pre*` hooks.
- **Proximity endpoints compare the full 32-character guid**; session and
  profile pages key on the 8-character prefix. The session → proximity link
  now carries the full guid (#921). Accepting the prefix on the 10 proximity
  endpoints is an open item, not a bug in the pages.
- **Session queries use `gaming_session_id`, never dates; grouping is by
  `player_guid`, never by name; the session gap is 60 minutes.**
- **Migrations are immutable once merged**; a fix is a new migration.
- **Time fields**: the 2025 bulk import wrote `denied_playtime` and dead time
  on a different scale (Lua ×2.2 vs import × share of time); the repair
  (#885–#904) reconstructed 8,721 rows and the monthly dead-time share is
  flat 0.19–0.23 across 20 months. Old rows that still look impossible sit in
  rounds the pipeline already excludes.

## Known open (already recorded — verify, don't rediscover)

- `GET /api/rounds/{id}/vs-stats`: no `GROUP BY`, drops `subject_guid` — 18
  rows for 6 players on round 11425. Not migrated to the SPA until fixed.
- `greatshot/{id}/highlights/render`: renderer is not configured on the dev
  box (no ffmpeg, no `GREATSHOT_RENDER_COMMAND`); `greatshot_renders` has one
  row ever, `failed`.
- `/api/stats/session/{id}/detail` has no `response_model` (8 fields the TS
  interface did not know); the drift checker is blind there until it does.
- Lua tank `total_distance` < 1 000 u in 112 of 128 `sw_goldrush_te` rounds
  (`script_mover` origin suspect).
- Corpus `destroyed_count` carries a phantom +1 on goldrush rounds before
  v6.14 (owner decision pending).
- `docs/CLAUDE.md` says Redis 7.4.2; the dev box runs 6.0.16 (7.4.2 is the CI
  image). Only `RedisCacheBackend` uses it and only with `CACHE_BACKEND=redis`.
- The SPA parity sweep (`scripts/audit_website_browser.mjs --app`) last ran in
  full on 2026-09-06 morning; the re-run after #921's fixes was aborted for
  RAM, so `#921`'s changes are proven by e2e, not by the full sweep.
- `HealthMonitor` is constructed but never started (`bot/ultimate_bot.py`);
  nothing schedules `scripts/health_check.sh`. A watchdog lane is planned.

## What a finding needs

A finding is a claim about behaviour, so it should carry the input, the
observed output and the expected one, and — where the reviewer can run it —
the command. Green tests are not a proof here; neither is a red one without a
run. Preferred proofs, all runnable from the checkout:

```bash
venv/bin/python -m pytest tests/unit tests/integration -q -x     # Python (~4 200 tests)
(cd website/frontend && npm run typecheck && npx vitest run)      # SPA
bash scripts/lint-js.sh && venv/bin/ruff check bot/ website/backend/
venv/bin/python -m pytest tests/unit/test_parity_keymap.py tests/integration/test_endpoint_gap.py tests/integration/test_route_contract.py -q
```
The database is not available to a remote reviewer; anything that needs
data is a question for the owner, phrased so it can be measured
(`docs/HANDOFF-next.md` §3 has the live-server and sweep commands).

Findings are triaged with the six-phase loop in
`docs/process/MANDELBROT_RCA.md` (discovery → dependency map → contract →
zoom checklist → root cause → fix + verify with a mutation seen failing).
Please classify each finding by that checklist's item number where you can;
it makes the triage mechanical.

## Datapoint ledger (2026-09-08)

`docs/parity/datapoints.json` lists, for every endpoint the new SPA calls, which
keys of its recorded response the app reads and which it does not
(`scripts/datapoint_ledger.py`; ratchet in `tests/unit/test_datapoint_ledger.py`).
An `unread` row is not a bug in the page that fetches it — it is a captured
datapoint waiting for a panel. The ratchet is per ROW (`docs/parity/
datapoints_unread_baseline.txt`, which the script only ever shrinks), not a sum,
so a new unread key cannot hide behind an unrelated gain. A `dropped` row carries a
reason in `docs/parity/datapoint_decisions.json`; a decision without a reason, or
naming a key no fixture has, fails the test. Endpoints whose recording is empty are
`unmeasured`, not covered. A name match is an upper bound: a key can be
counted `read` and still not reach the DOM — the page tests are the other half.

