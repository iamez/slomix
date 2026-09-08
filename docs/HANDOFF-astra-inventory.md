# HANDOFF — Astra: full open-work inventory (2026-09-07)

> **2026-09-08 intake:** this is the historical inventory, not the execution
> queue. PLAN's Astra ledger records current dispositions and proof limits.
> Runtime section 5's Discord-only `round_ended` proposal is superseded by
> transactional `round_stats_imported` at the canonical importer; consumer
> activation also needs late-update coverage. No automatic historic replay is
> proven by file/Discord persistence. Existing watchdog cadence implies around
> ten minutes plus scheduling/probe time, not a strict two- or ten-minute bound.
> Recount ratchets and recheck merged PRs; do not resurrect closed code work.

> Companion to `HANDOFF-astra.md` §C. Compiled by a read-only inventory pass over
> `docs/PLAN.md`, `docs/BACKLOG.md`, `docs/HANDOFF-next.md`, `docs/KNOWN_ISSUES.md`,
> `docs/INFRA_HANDOFF_2026-02-18.md`, `docs/SPIDERWEB_STATUS.md`, the ratchet files under
> `tests/data/`, `docs/parity/keymap.json` and the local design docs 15/19/20/21/22/24
> (quoted, since those are not in the repo). Each item: `[S|M|L]` size, source line,
> what it depends on, and the proof it needs. Numbers were measured at main `71de6b65`;
> re-measure before acting (see §0). Owner decisions are consolidated in §11.

# Open-work inventory — Slomix (`/home/samba/share/slomix_discord`, main @ `71de6b65`)

## 0. Read-this-first: the docs are already stale in three places

`docs/PLAN.md` and `docs/HANDOFF-next.md` were last written 2026-09-06 evening; four commits landed after them. Astra must re-verify before planning:

- `3fdfd88b` closed PLAN.md:58 (`response_model` for `/proximity/player/{}/profile|radar`).
- `467b6a60` closed two of the three watchdog r. 2 items (PLAN.md:116-118): the `watchdog` key in `/api/diagnostics` and the About-panel line, plus doc 19 r. 1's "N datasets" line (BACKLOG.md:16-17).
- `71de6b65` moved dev services to `/home/samba/share/slomix-dev-run`; every "deploy to dev" instruction older than that is wrong.
- PR **#955** (open) builds `/api/rounds/{}/awards`, i.e. the 13-line ratchet becomes 12 on merge. **#960**, **#958**, **#956** (release 1.46.0), **#912** (sister's arena Lua) are also open; **#924–#943** are the 20 `review:` draft PRs that must never be merged.

Authoritative counts, measured now, not remembered:

| ratchet | value | file |
|---|---|---|
| endpoint gap (H1) | **13** | `tests/data/endpoint_gap.txt` (lines 95-107; 94 lines of triage comments above them) |
| response_model gap | **217** routes of 263 | `tests/data/response_model_gap.txt` |
| manual type drift | **0** (deliberately empty guard) | `tests/data/manual_type_drift.txt` |
| keymap non-built statuses | **4**: 2 `unmapped` (home "Map Distribution" :28, session-detail "Charts" :54), 1 `retired` (replay :275, intentional), 1 `phase-5` (proximity `table-0` roster table :300). The `phase-7` clips entry (:331) is dead — O1 closed as "no Clips page" | `docs/parity/keymap.json` |
| TODO/FIXME/XXX in `bot/ website/backend website/frontend/src/app scripts` | **11 hits, only 2 real** | see §8 |

---

## 1. New site (SPA `website/frontend/src/app`)

The 13 endpoint-gap lines, each with its triage reason from the file's own comments:

- `[M]` `/api/players/{}/card` — hover card: rating, archetype, percentiles, sparkline_dpm, badges, career — `tests/data/endpoint_gap.txt:99` + `HANDOFF-next.md:98-100` — depends on: owner (literal FUT-card port clashes with the typographic design system) — proof: its percentiles are **not** the ET rating components' (measured on one player: card dpm 57 / survival 64 / revives 79 vs components 58.9 / 83.9 / 44.6) — any build must state which pool.
- `[M]` `/api/rounds/{}/player/{}/details` — objectives + sprees exist nowhere in the SPA — `endpoint_gap.txt:101`, `HANDOFF-next.md:101-103` — depends on: nothing — proof: do **not** port `matches.js:970`, which reads `combat.useful_kills` and `w.weapon_name` the handler never returns (legacy modal prints `undefined` today).
- `[S]` `/api/rounds/{}/awards` — **in flight as PR #955** — `endpoint_gap.txt:100`, `HANDOFF-next.md:104-105` — depends on: owner confirming the surface #955 built (`RoundsTable` click → awards panel) — proof: `round_awards` carries 1,472 duplicated (round, award) groups; 929 identical ones are removed by `DISTINCT` in #955, 282 with differing answers from two imports are deliberately left visible (`docs/KNOWN_ISSUES.md`).
- `[S]` `/api/greatshot/{}/crossref` — GET, auth + ownership, 23 analysed demos — `endpoint_gap.txt:96`, `HANDOFF-next.md:106` — depends on: nothing — proof: live call as owner + as anon (401 is a designed state on greatshot).
- `[S–M]` `/api/stats/player/{}/form` — `endpoint_gap.txt:104`, `HANDOFF-next.md:107-108` — depends on: nothing — proof: the DPM/KD series is **already drawn** from `skill/…/form`; this endpoint only adds dates, rounds/session, `avg_dpm`, `trend`. Prove the delta before building.
- `[S]` `/api/stats/player/{}/rounds` — DPM series feeding a canvas sparkline — `endpoint_gap.txt:105` + `:44-46` — depends on: nothing — proof: it is **not** the profile's "last rounds" table (that comes from `/api/player/{name}/matches`) — same word, different data.
- `[S]` `/api/players/{}/awards` — engraved season awards from the legacy History tab — `endpoint_gap.txt:98` + `:42-43` — depends on: nothing — proof: these are not the "milestones" the profile already shows.
- `[L]` `/api/sessions/{}/graphs` — eight `playstyle` axes + `dpm_timeline`, no graphic primitive exists (only precedent `RetroViz.tsx`) — `endpoint_gap.txt:103`, `HANDOFF-next.md:109-112` — depends on: nothing technical — proof: ⚠️ it counts `round_number IN (1,2)` while Stats 2.0 uses `counts_toward_totals`; the panel **must name which gate it used** or the site shows two kill totals for one evening.
- `[?]` ⛔ `/api/rounds/{}/vs-stats` — **do not migrate as-is** — `endpoint_gap.txt:102` + `:53-60`, `HANDOFF-next.md:113-115` — depends on: owner (fix handler vs delete line) — proof: `records_matches.py:491` selects from `round_vs_stats` with no `GROUP BY` and drops `subject_guid`; measured 18 rows for 6 players on round 11425, `vid` three times.
- `[?]` ⛔ `/api/greatshot/{}/highlights/render` — **not a build, a decision** — `endpoint_gap.txt:97` + `:61-65`, `HANDOFF-next.md:116-119` — depends on: **owner** — proof: no ffmpeg, no `GREATSHOT_RENDER_COMMAND`, no `.env`; `greatshot_renders` holds exactly one row ever (2026-02-15, `failed`) against 622 highlights → the button would always produce `queued → failed`.
- `[S]` `/api/uploads/{}/download` — functionally covered via `download_url` (`uploads.py:736` → `UploadsPage.tsx:325`) — `endpoint_gap.txt:107` + `:67-73` — depends on: nothing — proof: what is genuinely missing is smaller: no download button on the list card, and `is_playable`/`poster_url` unused (no inline player). The ratchet line stays either way.
- `[—]` `/api/bets` and `/api/stats/sessions` — **cannot be closed by building** — `endpoint_gap.txt:95,106` + `:12-20`, `PLAN.md:129` — depends on: retiring legacy `sessions.js`/`sessions2.js`/betting JS — proof: `/api/sessions` already carries everything its sibling had (duration_seconds, start_time, end_time, player_names, total_deaths, search) and both agree; ⛔ deleting the line to shrink the number fails the test, which recomputes the set.

Other new-site work:

- `[M]` Final parity sweep re-run (32 routes × 4 viewports × anon/owner = 256 checks) — `PLAN.md:140-143`, `BACKLOG.md:43-48`, `HANDOFF-next.md:43` — depends on **RAM** (run 3 was aborted at 1.8 GB used / 196 MB free; chromium leaves ~240 MB) — proof: `AUDIT_BASE_URL=http://127.0.0.1:8000 node scripts/audit_website_browser.mjs --app --out /tmp/audit` (no `--manifest`: manifest mode opens one owner context at 1440×900 and exits; the full run must leave `results.json` with 256 rows); ⛔ Chromium on this 2-GB box only with the owner's OK per run; ⛔ afterwards check `ps` and kill by PID, never `pkill -f`.
- `[S]` Two `unmapped` keymap panels: home "Map Distribution" (no SPA equivalent for share-of-rounds) and session-detail "Charts" (legacy charts tab was never carried; **no decision retiring it is on record**) — `docs/parity/keymap.json:28,54` — depends on: owner — proof: `tests/unit/test_parity_keymap.py` pins the unmapped count, so debt cannot grow silently.
- `[M]` Proximity `table-0` roster/engagement panel, still `phase-5` — `keymap.json:300` — depends on: nothing — proof: pinned as pending in `proximity_inventory.json` (inventory pending count is otherwise 0, #884).
- `[S]` Switchover blockers, all six must hold at once — `docs/design/09 §"Merilo za dan preklopa"` — depends on **prod freeze lift (owner)**: (1) `endpoint_gap.txt` empty; (2) `parity_diff.mjs` clean on 32 routes × 4 viewports (33 was the pre-Clips count) × anon/owner; (3) H3 green on all routes both projects; (4) canvas pixel-diff green on 3 rounds × 3 maps; (5) openapi snapshot matches the live app; (6) **tested on dev against a real evening of play**, not history. Cutover itself = `build:app` in `scripts/deploy_release.sh` + SPA fallback in `main.py`; rollback = revert that commit + restart `slomix-web`.
- `[S]` Uploads leftovers: poster capture (.mp4 → JPEG via canvas, `uploads.js:300-336`), resume across reload (HEAD + localStorage file identity — legacy has none), category/tag filtering on the list — `BACKLOG.md:234-237`.
- `[S]` `api_storytelling_scopes.json` fixture is orphaned; `useStoryScopes` has no consumer in `src/app` — `BACKLOG.md:225` — proof: grep for consumers before deleting.
- `[S]` Local trap: generated `src/api/generated/openapi.d.ts` was stale twice at typecheck → regenerate it the way `AGENTS.md`/`website/frontend/AGENTS.md` say: run `npm run typecheck` / `npm run test` / `npm run build:app` (their `pre*` hooks regenerate the file); never `rm` it by hand and never call `npx tsc`/`npx vitest` directly — `BACKLOG.md:286-287`.
- `[S]` Replay page: playback canvas is a named follow-up; the `kill-outcomes` `events` list (80 KB) is never drawn — `BACKLOG.md:280-281`.
- `[S]` `weapon-accuracy.weapon_breakdown` only fills under a `player_guid` filter — the player slice should show it — `BACKLOG.md:284-285`.

---

## 2. Backend typing / response models

- `[L, splittable]` **217 routes with no `response_model`** — `tests/data/response_model_gap.txt` — depends on: nothing; do it per router — proof: `tests/unit/test_response_model_gap.py` recomputes and fails in both directions; a fixed route's line must be deleted in the same commit. Pattern proven three times (#812/#820/#830) and again by `feat/dataset-registry-r1`.
- `[M]` **availability + bets round: 24 handlers**, openapi has no schemas → the hand-written `types.ts` is pinned only by harness snapshots (`tests/unit/test_availability_slice2_fixtures.py`) — `BACKLOG.md:246-250` — depends on: owner said 2026-09-02 it is a **separate PR** — proof: openapi snapshot diff + snapshot round-trip with no field loss.
- `[M]` `/stats/session/{id}/detail` still untyped while `/basics` is typed; the Players tab reads 8 fields the TS interface never knew (`self_kills, useful_kills, full_selfkills, time_dead_minutes, denied_playtime, alive_pct_drift, played_pct, played_pct_lua`) and the drift checker is blind to them — `BACKLOG.md:187`, `:219-221` — proof: needs session 154 + 80 recorded into `_RECORDED` and the line struck from the ratchet.
- `[S]` `/storytelling/moments` is now a union of shapes (optional `types`) and still untyped (`response_model_gap.txt:208`); top-level `kills[]`/`victims` for multikill/team_wipe are not in the interface — `BACKLOG.md:173`.
- `[S]` `/stats/session/{id}/detail` drops the `warnings` half of `build_session_scoring`'s tuple → the header cannot say "Lua header winner missing: used time fallback" (doc 12 line 31 requires it); `MapStrip` pairs `detail.matches` with `scoring.maps` **by index** and should pair by `match_id` — `BACKLOG.md:200-205`.
- `[S]` `SessionSummary.maps_played` is alphabetically ordered → the thumbnail is the alphabetically-first map, not the first played; needs play order or `first_map` — `BACKLOG.md:228-230`.
- `[S]` `best-lives` has no coverage flag: `lives: []` conflates "not captured" with "nobody reached the minimum" — `BACKLOG.md:185`.
- `[S]` `bets_router.get_current_market`: `my_bet.payout` goes through `int()` and on `None` silently nulls `my_bet` (bare `except TypeError`). Column is `NOT NULL DEFAULT 0` today, so the type lies only if the schema loosens — `BACKLOG.md:263-266`.
- `[S]` `bets/wallet` 500s for an authenticated session with no `users` row (FK on `user_points` auto-create) — real users get a row at OAuth; deleted/sentinel users still break — handler should catch the FK and return an empty wallet or 403 — `BACKLOG.md:267-272`.
- `[S]` `delete_upload` lacks `_require_valid_upload_id` → a malformed id gives 404 instead of 400; `docs/UPLOAD_SECURITY.md` §3.6 is stale (claims admins cannot delete; the admin gate exists) — `BACKLOG.md:243-245`.
- `[M]` **Resumable upload router handlers have zero tests**: no test calls `init_resumable_upload`/`resumable_patch`/`finalize_resumable_upload`/`abort_resumable_upload`; only the store is covered — `BACKLOG.md:238-242` — proof: `test_uploads_slice2_fixtures.py` covers init/finalize/delete shapes, not PATCH/HEAD.
- `[S]` `scripts/record_api_corpus.py:mint_owner_cookie` mints a cookie with a **hard-coded real Discord id** ("corpus-recorder"); `--sentinel` is the identity-free path — the owner path should go via `E2E_OWNER_*` — `BACKLOG.md:254-256`.
- `[M]` Known-issue backlog with the same flavour: `skill_router` SDS reads capped `pcs.denied_playtime` instead of `effective_denied_ms` (Low); KIS `distance_multiplier` is a hard-coded `DISTANCE_NORMAL` stub returned as a real per-kill field (Low; the only two real `TODO`s in the tree, `kis.py:62,579`); `website/migrations/` has 17 SQL files with **no ledger** (Low); `storytelling/loaders.py` is per-date only (Low); formula registry has 23 entries and is missing archetypes, moments, synergy, momentum, gravity/space/enabler/lurker, objective_pressure, session_matrix, rivalries, season_awards (Low) — `docs/KNOWN_ISSUES.md:333,343,355,367,378`.
- `[M]` **9 proximity routers still scope by `session_date`, not gsid** (`combat, player, dashboard, trades, movement, quality, support, events, journey`) → a midnight-crossing session hides its post-midnight rounds (gsid 138: 2 rounds / 88 kills invisible). Infrastructure already exists (`ProximityQueryBuilder.with_session_scope`) — `KNOWN_ISSUES.md:296`; the Teamplay tab hits the same bug via `/proximity/trades/player-stats` — `BACKLOG.md:190`.

---

## 3. Proximity + spider-web

- `[M]` Layer 3 (information state / belief regions) **not drawn** — edges are computed, nothing renders them — `docs/SPIDERWEB_STATUS.md:19`, `:68-70`, `BACKLOG.md:282-283`, `PLAN.md:131-132` — depends on: **owner ordering** (deliberately deferred behind parity, reason recorded 2026-09-02) — proof: any new metric must name which threads it joins and follow the discipline that already retired six proposed metrics (control group before headline number).
- `[L]` Layer 4 (movement quality) **not started**; §7.5 says the weights are choices, not facts — `SPIDERWEB_STATUS.md:20`, `:71-76` — depends on: owner — proof: a control that kills the instrument, before any headline number.
- `[S]` SW-1's named omissions: 3D camera, belief regions, label placement (in the page footer) — `SPIDERWEB_STATUS.md:68-70`, `PLAN.md:131-132`.
- `[M]` `etl_supply` has **no mesh** — the BSP was never exported — `BACKLOG.md:283`.
- `[S]` Free path / LOS is still marked `unvalidated` in the web output until §8 is signed off; **no metric consumes LOS yet** — W6 validated the tracer, not a metric — `SPIDERWEB_STATUS.md:59-61` — depends on: **owner sign-off**.
- `[S]` `capture_policy.mode = "unknown"` is the truth for historical rounds (`capabilities` NULL in all 828 rows measured 2026-08-21; capture cadence stored nowhere) — shown as three-state snapshot integrity, not an error — `SPIDERWEB_STATUS.md:55-58`.
- `[S]` Objective pressure keeps the radius-500 sphere: objective volumes were measured (containment 5.9 %, free path 48.1 %) and a random-direction control killed both instruments — on 3 of 4 maps the path to the objective is *clearer* than random; only `etl_ice` is worse than random — `SPIDERWEB_STATUS.md:64-67` — this is a **closed** direction; do not reopen without a new control.
- `[S]` KIS details needs the 32-char guid (`storytelling_router.py:400`), fed from a `kill-impact` list capped at 50 → the 51st scored player would read "no scored kills". Impossible today (≤ 12 players) but the limit is named in code — `BACKLOG.md:186`.
- `[M]` Orphan backlog: **57,676 orphan rows** across a now-complete 29-table inventory (`proximity_team_cohesion` 34,870 of 1,094,566, growing) — every session-scoped metric silently excludes them — `KNOWN_ISSUES.md:46` — proof: dry-run relinker report before `--apply`, and find why **new** orphans keep arriving; growth is the live problem, not the tail.
- ~~`[M]` **Dead-hours orphan mechanism — High.**~~ **STALE (Astra, 2026-09-07): the shared `bot/core/dead_hours.py` + `awake_cutoff` fix (PR #652) is in the code (`relinker_mixin.py:253`); only "do new orphans still arrive" remains, as a measurement.** Original: Three constants disagree and *guarantee* permanent orphans for rounds played 02:00–05:00 CET: the endstats monitor's `if 2 <= hour < 11` gate (`bot/services/monitor_tasks_mixin.py`), the un-gated proximity ingestion loop (`bot/cogs/proximity_mixins/ingestion_mixin.py`), and `_PERMANENT_ORPHAN_AGE_HOURS = 6` (`relinker_mixin.py`) being shorter than the 9 h window — `KNOWN_ISSUES.md:15` — proof: measured live 2026-08-11, 5 rounds → 8,810 orphans, relinker ran 5×, linked 0.
- `[S]` `round_number` disagreement defeats the relinker on covered tables (2 of 643 rounds on prod, 0.31 %); direction: trust `map_name` + `round_start_unix` over `round_number` equality — `KNOWN_ISSUES.md:73`.
- `[S]` Pre-migration-065 NULL-`round_id` orphans carry no round identity and cannot be relinked or deduped; serving keeps them — `KNOWN_ISSUES.md:90`.
- `[M]` `escort_credit`/`vehicle_progress`: **all spatial dimensions are zero** while time/count are live — the broken piece is the tracker's spatial capture path — `KNOWN_ISSUES.md:106` — depends on: **owner (FIX 13)** — fix the Lua capture or remove the fields from API responses; serving zeros as data is worse than either.
- `[S]` Proximity page cold-start: `proximity`/`proximity-player` `page.goto` exceed the 30 s `networkidle` budget (cold backbone) — `BACKLOG.md:257-262`.

---

## 4. Watchdog + ops

- `[M]` **Watchdog r. 2 — SSH probes on puran** (tailer `pgrep`, `ls -t stats/`) — `PLAN.md:116-118`, `docs/design/24_WATCHDOG.md:5,27-28,34` — depends on: nothing in-repo (probes are read-only: `ls`/`pgrep`/`stat`) — proof: simulated outage → alarm within ≤ 10 min (5-min timer + confirm-twice; "2 min" was wrong); a night without an outage → 0 alarms + the 09:00 heartbeat; plus a mutation of a check that must fail.
- `[✓ merged, NOT served]` `watchdog` key in `/api/diagnostics` + About-panel line — done in `467b6a60` (#954), but the SPA bundle on dev predates it (built 2026-09-06 11:03) — see `HANDOFF-astra.md` §G1, still listed as open in `PLAN.md:117-118` and `24_WATCHDOG.md:5` — proof: re-read the commit before scheduling.
- ~~`[S, owner]` Install the timer~~ **DONE 2026-09-07 02:41** (timer active, runs every 5 min from the run dir; state in `slomix-dev-run/logs/watchdog_state.json`). Original text: `WATCHDOG_WEBHOOK_URL` into the run-dir `.env`, then `sudo cp deploy/systemd/etlegacy-watchdog.* /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now etlegacy-watchdog.timer` — `PLAN.md:113-115` — depends on: **owner** — proof: the r. 1 dry-run already showed 9/9 `ok` (disk 84.7 %, just under the 85 threshold) and `bot_streaks` `unknown`.
- `[S]` Fix the path in `~/slomix-server-logs/bin/pull_puran_console_log.sh` — **outside the repo, owner** — `PLAN.md:118`.
- ~~`[S, owner]` **Restart the dev bot**~~ **DONE 2026-09-07 02:57** (bot and web run from `slomix-dev-run` at `71de6b65`; `bot_error_streaks.json` is being written). Original text: #923 (SSH monitor) merged at 18:02 on 2026-09-06, but the owner's 17:17 restart ran `ed0dfe22` — **not one line of #923 is running on dev** — `PLAN.md:438-441` — proof: `sudo systemctl restart etlegacy-bot.service` on dev, then confirm the streaks file appears.
- `[M]` SSH monitor: **one connection per cycle instead of one per file** — explicitly left unfinished, "its own slice and its own conversation" (production path rework) — `PLAN.md:443-444` — ⛔ note `connect()` is not thread-safe (paramiko #1904) and our operations run in executor threads, which is why the pooling idea was inverted in slice 3.
- `[S]` `is_bot_round` was historically never true (`postgresql_database_manager.py:2246`) — check rounds dated after the bot tests — `BACKLOG.md:183`.
- `[S]` `docs/GAMESERVER_LIVE_LUA_MAP.md:74` and `deployed_lua/README.md` claim 4 Lua modules; **6 are live** — `BACKLOG.md:308-309`.
- `[S]` Administrative tooling should read only the root `.env` (or take an explicit `--role`) — the root/`website` `.env` divergence remains open even though `db_backup.sh` itself was fixed in #906 — `PLAN.md:342-345`, `BACKLOG.md:177`. Same trap bites `scripts/apply_migrations.py` (picks `website_app` from `website/.env` and dies with "must be owner") — `BACKLOG.md:101-105`.

---

## 5. Runtime v2 (doc 21)

- `[M]` **Slice 1: `events` table + `pg_notify`, shadow mode** — `docs/design/21_RUNTIME_V2_EVENT_BRAIN.md §8` (lines 31-51 of the §7-onward extract), `PLAN.md:225-229`, `HANDOFF-next.md:86` — depends on: ⛔ **owner's explicit go, and only after the ultra review** — content: `events(id, event_type, payload jsonb, created_at, source)` + migration + GRANT `website_app`; one `round_ended` emitter in `_process_stats_ready_round` **in the same transaction** as the round write; `pg_notify('round_events', id)` with the website as first LISTEN subscriber invalidating `stats_cache`/HTTP cache; the bot as second subscriber cross-checking; `EVENT_STREAM_ENABLED` default off.
- Proof required: latency file/webhook → Discord post before/after (≈0 added); `COUNT(events)` per session = number of rounds (dedup on `(map, round_number, round_end_unix)`); website cache staleness before (TTL 30/300 s) vs after (≈immediate). **"No improvement" is also a valid result** — it costs one slice to learn the idea does not pay at this scale.
- Non-goals to reject if proposed (`§9`): rewriting the bot/FastAPI/React, parser or schema changes, Redis Streams / Kafka / Celery, runtime as a systemd supervisor, changing the `/api/live/*` contract, or fixing live-state durability in passing.
- Settled decisions Astra must not relitigate (`§7`): one domain boundary but **separate processes**; `events` + `pg_notify` first, `LiveStateReducer` extraction second; bot and web stay independent readers. Still open: **host** (recommendation: dev, don't touch prod) and **deploy owner** for the new unit/package.

---

## 6. Research lanes

**Doc 22 — bot digital twins**
- `[M]` **Slice 4: verification harness, bot vs human + control against a foreign profile** — `docs/design/22 §6` row 4, `PLAN.md:219`, `HANDOFF-next.md:50-52` — depends on: **owner deploying `server/omnibot/twins/*` to puran + running a bot test** — proof: the control must be part of the report; ⚠️ today's shuffled-session control survives ≈ 21 % (14/67 distinguishing targets), so with 7 regulars the group mean is a noisy baseline. Possible next steps recorded: z-score against other players' dispersion, or more sessions; until then the report prints the control on every run.
- `[S]` `botnames` read `DB_*` env (not in `.env`) → always fell back to default names; fixed with a `POSTGRES_*` fallback, **but the live table on puran is still the fallback** — `BACKLOG.md:83-85`.
- `[S]` Data quirks to carry: `carniee` has two guids; Olympus = olz (one player, two bots) — `BACKLOG.md:85`.
- `[S]` `RoleBoard` shows top 5 and filters players with `hold_pct: null` without saying how many it dropped — `BACKLOG.md:112-114`.
- `[S]` Camp-profile rate limit is 5/min (same as lurker) — six consecutive queries from one IP give 429, measured — `BACKLOG.md:114-115`.
- `[L, owner]` Slice 5: waypoint skeleton for 4 "unplayed" maps from shared traces — live intervention, separate PR — `doc 22 §6` row 5, `§7` decision 3.

**Doc 20 — match moments / vehicle corpus**
- `[M]` ⚠️ **`destroyed_count` corpus fix** — the pre-v6.14 corpus carries a phantom +1 on **every goldrush round**; the detector's "destroyed 1×" was false — `PLAN.md:210-211`, `BACKLOG.md:96-98`, `HANDOFF-next.md:55-56,149` — depends on: **owner decision (da/ne)** — proof: recount destroyed events on goldrush rounds before/after the v6.14 boundary, and show the detector's star ratings that change.
- `[S]` ⚠️ **Tank on `sw_goldrush_te`: `total_distance` < 1000 u on 112 of 128 rounds** — the tank movement measurement (`sampleVehiclePositions`, `r.currentOrigin` for `script_mover`?) is suspect; the truck is normal (p50 8,612 u) — `BACKLOG.md:174` — proof: check the source field and `MAX_SANE_MOVE` in Lua **before** the tank is counted as "not moving".
- `[S]` **Moments has no "not covered" vocabulary**: `[]` also means "proximity was not captured"; the `vehicle_tracking` manifest coverage (`round_web_service.py:635`) would give `status: unavailable` following the `_probe_unavailable` pattern — router change + Story panel — `BACKLOG.md:175`.
- `[S]` The director's cut hides 3★ escorts on rich sessions (154: pool 91, limit 10/50) — by design; a dedicated panel/type filter is the fix, not raising the star threshold — `BACKLOG.md:176`.
- `[S, owner]` Migration **082 to prod** on the next release deploy — `PLAN.md:198`, `HANDOFF-next.md:54,92`.
- Open owner decisions on this doc: R/T backtest thresholds; revive source (2 tables); `sub_type` vs a new type; `proximity_team_cohesion` — **1.28 M rows with no reader** — `PLAN.md:451-453`.

**Doc 19 — modular stats / per-user view (slices 2–6)**
- `[M]` Slice 2: column picker for the basics table — `user_page_layouts` table + migration + `_down` + GRANT, `GET/PATCH /api/preferences/session-detail` — `docs/design/19 §9.2` — depends on: **owner** — proof: sentinel hides 2 columns → reload keeps them; another user unaffected; logout → defaults.
- `[S]` Slice 3: show/hide sections on the session page (+ `Hidden` in `ui.tsx`) — `§9.3` — proof: the hidden section's `data-parity` node is absent and it issues no query, while a low-contrast `Hidden` trace stays (doc 19 §5: never a silent hole — same contract as `docs/SPA_MODULARITY.md` slice 7), un-hiding without reload, anonymous parity inventory unchanged.
- `[M]` Slice 4: limited home customisation — `§9.4` — proof: isolation between users + anonymous view unchanged.
- `[M]` Slice 5: admin site-wide display switch (second table, `tier`) — `§9.5` — proof: site setting overrides user-on **with a visible reason**.
- `[L]` Slice 6: capture switches in Lua/importer — `§9.6` — depends on: **owner gate; only after 1–5, and only with a coverage flag in the same PR**.

**Frame-health / lag lane**
- `[S]` **The whole lane is blocked on one evening of real play**: read `frame_health.log` from puran after a genuine gaming evening, with no new `self` cost from v6.14 — `PLAN.md:196-199`, `:283`, `:292-298`, `HANDOFF-next.md:55` — depends on: **a real evening happening** — proof: baselines already measured (empty server 2026-09-02: stall 363 s, our Lua 16 %, residual 84 %; 2026-09-03 to 18:00: 36 s, 22 %/78 %; bot test with v6.13: 2 gaps, both tracker `round_end` 188–224 ms).
- `[M]` Round-end burst **batch write** (`table.concat` → ~64 KB chunks instead of 8,400 individual `trap_FS_Write`) — `PLAN.md:298`, `BACKLOG.md:179`, `:274-275` — depends on: **one evening of `self` measurement first**, then owner deploy — proof: instrument before/after (the instrument now exists).
- `[S]` `stats_discord_webhook.lua` `pending_retry_sweep` = fork+exec (`os.execute mkdir`, `io.popen find`) every 60 s on the game thread, driven by `os.time()` so it runs during pauses and at 0 players — `BACKLOG.md:181`, `:278-279` — proof: measured as `FM … mod=stats_discord_webhook top=sweep:<ms>`; sweep did **not** exceed 50 ms in 30 min, so it is not the prime suspect yet; gate the fork on a non-empty buffer.
- `[S]` Tracker micro-optimisations: `scanVehicleEntities` + `scanObjectiveEntities` = 2×960 `pcall(gentity_get)` at map load (`top=init_scan`, currently < 50 ms); cache `sv_maxclients` (`isValidClient` re-reads it every call); merge the two cohesion loops (same pairs, same distance twice) — `BACKLOG.md:182`, `:276-277`.
- `[S]` The unexplained 9 s `self` at 0 players (2026-09-02) — on repeat, `FM top=` will name it — `BACKLOG.md:180`.
- `[?]` Population B (host stall) — if the watcher confirms it, **open a hosting ticket** — `PLAN.md:458`. ⚠️ "cannot be ours" covers only the tracker (levelTime freezes during a pause); the webhook's `io.popen` sweep runs on `os.time()` through pauses and is **not** excluded.

**Lua / game server (KNOWN_ISSUES)**
- `[M, owner-gated deploy]` **Lua drift repo ↔ puran — High**: `proximity_tracker.lua` differs by 66 lines and the repo holds four **undeployed** fixes (aim_lock duration clamp, round-end flush at `last_seen`, two-pass stale close, and the C4 escort fix with `MAX_SANE_MOVE`); `live_events.lua` also differs — `KNOWN_ISSUES.md:129` — proof already in the data: `proximity_aim_lock` max duration 220,000 ms (78× above p99) from the missing clamp, and 0 escort distance on every credit. ⛔ Never blind-copy either direction; per-file three-way merge → commit → scp → activation via full map load, never `lua_restart`.
- `[S, owner]` `full_selfkills` semantics: the `>= limbotime/1000 - 2` threshold gives ~7 % hit rate, players expect ~50 % (`>= limbotime/1000/2`). Changing it changes history → owner picks a new field or a clean cut with a date — `KNOWN_ISSUES.md:161`.
- `[L]` **Lua Time Stats Overhaul — the largest open plan, not started since 2026-02-20**: per-player time tracking in `stats_discord_webhook.lua`, `-timestats.txt` files, extended webhook JSON, 8 new columns, then a dual-source comparison before switching consumers (phases A–D) — `KNOWN_ISSUES.md:176` — proof that it is still at zero: `grep -rn "timestats" bot/ website/backend/ vps_scripts/ | wc -l` → 0. Phase A shares the Lua deploy window with the drift merge.

---

## 7. Data-quality debt (Stats 2.0 corpus)

- `[M, owner]` **`denied_playtime` from the 2025 supastats backfill is broken**: Jan–May 2025 ~50 s per kill (max 18,880 s in a 107 s round), from Dec 2025 ~8 s; 352 of 5,538 rows in 2025 have denied > 2× playtime, only 8 in 2026. Same era as the broken `bullets_fired`. `/basics` flags such rows (`denied_pct` null, `coverage.denied_suspect_players`) and leaves the data as-is — `BACKLOG.md:209-214` — owner picks: cut by date, or re-run the backfill.
- `[S]` **`TAB[8] time_played_percent` is 0 in ~35–38 % of rows every month** (5,363/14,163, none NULL) despite correct parsing — a permanent hole, cause unknown, and a **direct input to ALIVE%** on the site (`sessions_router.py:2115-2131`) — `BACKLOG.md:195`, `:305-308`.
- `[S]` `revives_given` is 0 on all 5,538 rows before 2025-12 — every all-time revive leaderboard silently starts in December 2025 — `PLAN.md:406-407`.
- `[S]` `played_pct_lua` is a literal copy of `played_pct` (`sessions_router.py:2298`) — legacy's "Lua Played%" was fiction; a real TAB[8] needs its own column in `session_player_sql` — `BACKLOG.md:188`.
- `[S]` 14 sessions (83, 99–102, 104, 107, 123, 127, 128, 145–147, 151) have no counted round at all → `/detail`, `/basics`, `/awards` 404; 73 sessions before June 2026 have no `round_awards` (only three are computed); KIS exists in only 45 of 139 sessions; 65 player rows have no team (subs) — `BACKLOG.md:215-218`. Consequence: the Playwright "thin" sample (session 151) has been 404 since #855 — ~~`SAMPLES_THIN` needs a different session~~ — already session 80 (`website/frontend/e2e/session-tabs.spec.ts:24`); BACKLOG line is stale.
- `[S]` Reconstructed `time_dead_minutes` (8,721 rows pre-2026-03-24; original kept in `time_dead_minutes_original`, flag `time_dead_reconstructed`) changes `dead min` / `alive %` for old sessions — the tooltip should mention the flag — `BACKLOG.md:178`.
- `[S]` End-to-end proof that the import path writes `time_played_percent` again **only arrives with the next import** (next evening of play); today only the file the bot runs is proven to contain the column (54 columns in the `INSERT`) — `PLAN.md:366-369`.
- `[S]` `endstats_aggregator._format_value` (bot) prints `Least time dead`/`Full respawn king` percentages as `m:ss` and sums K/D across rounds — the bot should adopt `session_awards_service.AWARD_RULES`; `endstats_parser`: `Quickest multikill` numeric is a kill count (the second regex is dead code), `Tank/Meatshield` numeric is NULL — `BACKLOG.md:219-224`.
- `[S]` The legacy "Useful Kills" tooltip is **wrong** — the writer (`c0rnp0rn8.lua:679`, `topshots[15]`) counts a kill where the victim has ≥ half their limbo time ahead of them. The new page tells the truth; `session-detail.js:2484`, `matches.js:986`, `player-profile.js:1186` and `community_stats_parser.py:369` still carry the old text — `BACKLOG.md:193`.
- `[S]` ⛔ Assists are **not** awarded by the engine: `TAB[12]` = `topshots[3]` from our own `c0rnp0rn8.lua:701-741` (MOD filter, 1500 ms window), and our two counters disagree — endstats `topshots[29]` vs `TAB[12]` differ on 40 of 1,005 rounds (±1) — `BACKLOG.md:298-301`.
- `[S]` Measurement traps in `etconsole`: timestamps are right-aligned (`grep '^[0-9]+ Hitch'` returns 1 of 18), and the engine only reports a hitch above 500 ms (65 of 71 round-end bursts are **invisible, not absent**) — `BACKLOG.md:302-304`.
- `[S]` Deferred by owner scope: per-player head-to-head from `/storytelling/kill-matrix` (the matrix is already loaded in the Story tab; the row would only filter it) — `BACKLOG.md:184`; `headshot_kills` dropped from the Players table and would return as its own `hs kills` column — `BACKLOG.md:189`.

---

## 8. Infra + security (`docs/INFRA_HANDOFF_2026-02-18.md` "Required Follow-Ups", :66)

- ~~`[S]` Dependency policy~~ — CI already installs `requirements-dev.txt` (`.github/workflows/tests.yml:93`); only the written policy line is missing.
- `[M]` CI hardening: pin **all** third-party GitHub Actions to commit SHAs; add minimal `permissions` to every workflow job; make the release workflow update one canonical changelog path — `:74-77`.
- `[S]` Docker/runtime verification: `docker compose config` / `build api website` / `up --build`, then verify website `:8000`, API `:8001/api/status`, `/metrics` — `:79-88`.
- `[S]` Container digest pinning: CI and prod release manifests must deploy `image@sha256:…`, refreshed at least monthly with a CVE note in the PR; never merge a switch back to mutable tags — `:90-97`.
- `[S]` Cache/rate-limit review: confirm the cacheable allowlist in `http_cache_middleware.py`, TTLs (live 15 s, aggregates 300 s, default 120 s) and that `rate_limit_middleware.py` limits suit production traffic — `:99-106`.
- `[M]` **Security completion, partly done**: ~~CSRF protection for state-changing endpoints~~ (exists: `website/backend/main.py:145` `csrf_allowed_origins`; verify coverage of every state-changing route); production CORS allowlist validation; explicit TLS reverse-proxy guidance in the deployment docs — `:108-111`.
- `[M]` **Observability completion, still open**: Grafana dashboard + datasource provisioning (JSON), alert rules, and a Discord alert route for threshold breaches — `:113-115`. Note `monitoring/` exists but has **no path to Discord**, which is exactly why `docs/design/24` scoped it out of watchdog r. 1.
- `[S]` VM migration remainders — `KNOWN_ISSUES.md:461`: `http://www.slomix.fyi` bypasses Cloudflare and hits Samba directly (shut down or redirect); the `slomix.fyi` apex has **no A record**; `MPLCONFIGDIR` is missing from the prod `.env` (`/opt/slomix/.config` is read-only under the systemd sandbox → add `MPLCONFIGDIR=/tmp/matplotlib_cache`).
- `[S]` `scripts/codex_audit_prompt.md` is an **untracked duplicate** of `docs/prompts/codex_audit_prompt.md`, and `run_codex_audit.sh` reads the first one — `BACKLOG.md:41-42`.
- **TODO/FIXME/XXX census** (`bot/`, `website/backend`, `website/frontend/src/app`, `scripts/`): 11 hits, and only **two are real work items** — `website/backend/services/storytelling/kis.py:62` and `:579` ("Implement when per-kill distance data available", the `distance_multiplier` stub above). The rest are `mktemp XXXXXX` templates (`scripts/etl_update.sh:40`, `scripts/health_check.sh:26`), a `\\uXXXX` comment (`client_error_router.py:63`), a `#XXXXXXXX` display-name placeholder (`proximity_positions.py:384`), an upstream issue URL (`community_stats_parser.py:1104`), and three archived scripts (`scripts/archive/*`). `website/frontend/src/app` has **zero**. This codebase does not track work in comments — the docs are the backlog.

---

## 9. Docs debt / process

- `[S]` `docs/PLAN.md` header still says "Zadnja posodobitev: 2026-09-03" while lane sections say 2026-09-06 — the per-lane update rule (`PLAN.md:17`) is not being honoured for the shared header.
- `[S]` The endpoint gap number was written into the same document as both **3 and 16** on 2026-09-06; neither was counted — `PLAN.md:233`. The measure is `grep -vcE '^\\s*(#|$)' tests/data/endpoint_gap.txt`, never memory. Same class of drift now exists for the four items closed by `3fdfd88b`/`467b6a60`.
- `[S]` `docs/design/00–23`, `docs/OMNIBOT_PROJECT.md`, `server/omnibot/*`, `docs/archive`, `docs/research` are **gitignored** — visible in this checkout, invisible in a fresh clone (`HANDOFF-next.md:27-29`). A subset (00/05/06/09/12/17 + README) was committed for the ultra review. Anything Astra cites from 15/19/21/22/24 must be quoted, not linked.
- `[S]` `docs/design/24_WATCHDOG.md:5` and `PLAN.md:116-118` describe r. 2 items that `467b6a60` appears to have landed — reconcile before assigning.
- `[S]` 20+ stale local branches not merged into `origin/main` (`docs/*`, `feat/*` for already-merged PRs) — worktree/branch cleanup protocol exists in memory `worktree_cleanup_protocol_2026-09-02.md` (`PLAN.md:38`).
- `[S]` `.claude_session` (SessionEnd hook) is gitignored; after a crash use `--resume` — `BACKLOG.md:288`.

---

## 10. Review lane (gates almost everything else)

- `[L]` **Ultra review = 20 slices, not one PR** — `PLAN.md:158-172`, `HANDOFF-next.md:66-77` — limit is ≤ 8,000 changed lines / ≤ 500 files per review; code since prod (v1.39.0) is 93 k lines. `scripts/review_slices.sh measure|cut --push|prs` cuts `review-base/NN-<area>` (main with the area reverted to v1.39.0) and `review/NN-<area>` (tree = main, parent = base) and opens draft PRs; bodies in `docs/review/SLICES.md`, guide `docs/REVIEW_GUIDE.md`. ⛔ **Never merge.** ⛔ **Re-run `cut --push` on every move of main** — main has moved four times since the slices were cut (#956 release is also open).
- Owner's review order: **#924** (01 proximity+spiderweb+Lua, 5,301 lines) → **#925** (02 backend routers, 6,411) → **#926** (03 SPA lib, 7,708); #927–#943 by day.
- `[L]` **Triage of the ultra findings is Astra's task (1)** — `HANDOFF-next.md:81-82`, `docs/prompts/astra_kickoff.md` — proof discipline: classify each finding by the 12-point checklist, verify by measurement before fixing, and **reject with a measurement** when the finding is wrong; loop = `docs/process/MANDELBROT_RCA.md`.
- `[M]` After fixes: **1–2 weeks of soak on dev**, then the production conversation — `PLAN.md:167`, `HANDOFF-next.md:91-92`.

---

## 11. OWNER decisions that gate work (consolidated)

**Hard gates — nothing downstream can start:**
1. **Prod freeze** on v1.39.0 (decided 2026-08-28) — gates the entire switchover, `build:app` in `deploy_release.sh`, and migration 082 to prod — `PLAN.md:26-27`, `HANDOFF-next.md:44`.
2. **Ultra review must complete first** for runtime v2 (doc 21) — `PLAN.md:228`, `doc 21 §7` row 6; and Astra's work order is triage → open slices → watchdog r. 2 → runtime v2 "only on the owner's go" — `astra_kickoff.md`.
3. **Puran deploys are owner-only** (or explicitly handed over); never `lua_restart` — gates: Lua drift merge, twins deploy, any Lua optimisation — `HANDOFF-next.md:25-26`, `KNOWN_ISSUES.md:129`.
4. **RAM** (~1.8 GB box, ~196 MB free at worst) gates the full parity sweep and any parallel browser run — `BACKLOG.md:43-48`.

**Named open decisions:**
- `docs/design/15` **O2** — planning room auto-opens at threshold 6 (auto-open + Discord post vs manual `POST /today/create`); behavioural change with Discord consequences. **O4** — new upload categories image/audio/backup (recommendation: no, for parity). **O5** — legacy replay/proximity colours `#8bb0d6`/`#d1857c` (recommendation: at phase 5). **O7** — path speed bands (recommendation: derive from measured percentiles, top band still open). O1/O3/O6/O8 and D1–D5 are closed.
- **O-2 watchdog form** — standalone script + systemd timer (recommended, and r. 1 was built that way) vs reviving `HealthMonitor` — `HANDOFF-next.md:148`, `doc 24 §Oblika`. Effectively settled by the build; needs formal confirmation.
- **O-3, after Astra onboarding** — rotate the DB password (194 lines of `~/.codex/rules/default.rules` carry it), clean `default.rules` (`ssh`, `systemctl restart`), or move `.codex/rules` + `hooks.json` into the public repo — `HANDOFF-next.md:147`. ⚠️ This one is a live secret-exposure question, not a preference.
- **`destroyed_count` corpus fix — yes/no** — `HANDOFF-next.md:149`, `PLAN.md:211`.
- **Twins: deploy `server/omnibot/twins/*` to puran + bot test** (unblocks slice 4) — `HANDOFF-next.md:150`.
- **Doc 19 — when**, and its five sub-questions: capture switch global or per-server (rec: global); history when capture is disabled (rec: nothing retroactive); admin UI or config file (rec: config for v1); anonymous localStorage (rec: defer); where in the Stats 2.0 lane (rec: after R4) — `doc 19 §10`, `PLAN.md:448-450`.
- **Doc 20** — R/T backtest thresholds; revive source (2 tables); `sub_type` vs new type; what to do about `proximity_team_cohesion` (1.28 M rows, no reader) — `PLAN.md:451-453`.
- **Doc 21** — host (rec: dev) and deploy owner for the new unit — `PLAN.md:454`, `doc 21 §7` rows 4-5.
- **Doc 22** — slice 5 waypoints yes/no; bot tests as a production overlay acceptable (rec: yes, with `testmode`, short, outside evening slots); ordering vs doc 19 / moments — `doc 22 §7`.
- **Stats 2.0 leftovers** — FSK threshold (−2 s → /2), confirmation of the award nicknames, whether a Charts tab exists at all — `PLAN.md:255`, `BACKLOG.md:194-195`, and the `unmapped` keymap line at `keymap.json:54` ("no decision retiring the charts is on record").
- **`full_selfkills` semantics** — new separate field or a clean cut with a date — `KNOWN_ISSUES.md:161`.
- **FIX 13** — fix the Lua spatial capture for `escort_credit`/`vehicle_progress`, or remove the all-zero spatial fields from API responses — `KNOWN_ISSUES.md:106`.
- **`denied_playtime` 2025 backfill** — cut by date or re-run — `BACKLOG.md:209-214`.
- **Availability page UX overhaul** — go/no-go on six cosmetic items, to be built in legacy JS — `KNOWN_ISSUES.md:437`. **Upload "Share"** — navigate to detail (today) or copy the link directly — `KNOWN_ISSUES.md:451`.
- **`greatshot/{}/highlights/render`** — build a button that can only produce `queued → failed`, configure a renderer, or drop it — `endpoint_gap.txt:61-65`.
- **`rounds/{}/vs-stats`** — fix the handler's missing `GROUP BY` or delete the ratchet line when `matches.js` retires — `endpoint_gap.txt:53-60`.
- ~~**`rounds/{}/awards` placement** — there is no per-round surface yet~~ — surface built in #955 (`RoundsTable` `onSelectRound` → awards panel); open only whether the owner confirms it — `HANDOFF-next.md:104-105`.
- **Puran cron `0 20 * * * kill etlded`** — it throws players out mid-game; conditional kill or reschedule — `PLAN.md:455-456`.
- **`scripts/local_et_setup.sh` P1** — the production webhook is configured in the local test server — `PLAN.md:457`.
- **Hosting ticket** if the watcher confirms population B (host stall) — `PLAN.md:458`.
- **Owner actions, not decisions** (queued, updated 2026-09-07 11:30): ~~install the watchdog timer~~ done; ~~restart the dev bot~~ done; #960 merged; #958 in the merge gate; #955 and #912 next under the owner's "close all open PRs except Don't merge" (with the sister's #912 reservation); build the SPA bundle + `dev_deploy.sh` + restart (owner DA).
