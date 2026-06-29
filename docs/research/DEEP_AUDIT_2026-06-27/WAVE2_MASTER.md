# Slomix — Globok audit, Wave 2 (vse od prvega dne)

**Datum:** 2026-06-29 · **Obseg:** temeljna/jedrna koda od prvega dne (data pipeline, god-files, frontends, skill/storytelling, CI backlog)
**Metoda:** večagentni Mandelbrot RCA v2 + adversarialno prove-or-drop (66 agentov). Gradi na `WHOLE_CODEBASE_AUDIT_2026-06-15.md` + Wave 1 — ne ponavlja.

**Rezultat:** 31 potrjenih (1 high, 7 medium, 23 low), 18 ovrženih. Opomba: del ci_backlog verifikacij ni dokončal (session limit); ti so iz 06-15 backloga.

## Izvršni povzetek (ročna sinteza — agentova je padla na session limitu)

Temeljna koda Slomixa je **v jedru zdrava, a nosi precej tihega dolga**. Adversarialno preverjenih je 31 najdb (1 high, 7 medium, 23 low); 18 jih je padlo kot false-positive. **Edina HIGH je pravi, ponovljiv crash:** `!last_session maps` in `maps full` vedno crashata, ker SQL placeholder `{map_ids_str}`/`{round_ids_str}` ni nikoli `.format()`-an (vse druge poizvedbe v isti datoteki ga imajo) — uporabniško viden. Prevladujoča tema je enaka kot v Wave 1: **`round_date` namesto `gaming_session_id`** (per-session skill rating, substitution detector) in **napačno parjenje rund** (BOX scoring zruši orphan/dup R2 v en map_number; parser shrani R2 kot raw cumulative brez markerja ob midnight-crossoverju) — vse ogroža "no fabricated numbers". Drugi sklop je **podvajanje, ki se je že razšlo**: `MAP_IMAGE_MAP`+helperji kopirani čez 3 JS datoteke (Sessions kaže generičen placeholder), ~150 vrstic backend helperjev, dva vira resnice za shemo, dva migracijska sistema. Najtežji strukturni problem je **dual-frontend**: ~9.200–10k vrstic React strani je vzdrževanih a **nedosegljivih v produkciji** (le 4 od 29 rout MODERN), hkrati pa 4 produkcijske React route visijo na gitignored, netrackanem, 3 mesece zastarelem buildu, ki ob odsotnosti pokaže "Modern Route Offline". Varnostno ni nič kritičnega novega. Skupno: nobena arhitekturna prenova; potreben **ciljani correctness sweep + odločitev o kanonični frontend površini + de-duplikacija**, vse v obsegu majhne ekipe.

## Cross-cutting teme
1. **round_date vs gaming_session_id** (ponovitev Wave 1): skill rating per-session, substitution detector, BOX scoring mešajo seje istega dneva. → dosledno `gaming_session_id`.
2. **Parjenje rund / orphan R2**: parser shrani R2 kot raw cumulative BREZ markerja ko R1 ni najden (root-cause orphan-R2 inflacije); BOX scoring zruši dup R2. → eksplicitni `is_cumulative_r2`/`orphan_r2` marker + deterministično parjenje po match_id/round_start_unix.
3. **Podvajanje**: MAP_IMAGE_MAP/helperji×3 JS, ~150 vrstic backend, dva schema vira, dva migracijska sistema. → en vir resnice za vsako.
4. **Dual-frontend dolg** (glej spodaj).
5. **A11y/konsistenca legacy JS**: session kartice mouse-only; winner_team Axis/Allies invertiran na sessions strani.

## Dual-frontend strategija (priporočilo)
Legacy JS (`website/js/`) JE produkcija; React je večinoma nedosegljiv (~10k vrstic, 4 route MODERN), te 4 route visijo na netrackanem zastarelem buildu (→ "Modern Route Offline"). Glede na severnico priporočam **legacy JS = kanonična površina**: (a) 4 MODERN route vrni na legacy (player-profile.js že renderira aim/hit-region/heatmap; proximity.js pokriva replay/teams) + `VIEW_MODE.LEGACY`; (b) arhiviraj/izbriši ~10k vrstic nedosegljivih React strani; (c) odstrani modern-route-host "Offline" pot. NI React rewrite — odstranitev mrtve vzporedne veje. (Alternativa: pravilno buildaj+committaj React in migriraj ostale route — obraten, večji vložek, trči z "legacy je produkcija".)

## CI / backlog status (delno — večina verifikacij padla na limitu)
Potrjeno: mrtvi flake8/pylint/pycodestyle config. Ostalo (multipart/starlette/paramiko CVE, mypy/pip-audit/bandit v CI, paramiko AutoAddPolicy, docs drift) je iz 06-15 audita (M1–M4), owner-gated, brez novih kritičnih.

## Zunanji input (Codex, PREVERJENO): prox-scores scope gap
`/proximity/prox-scores` sprejme le range_days/player_guid/limit; frontend pošlje scope prek scopedUrl, backend ignorira → prox_overall izgleda scoped a kaže 30-dnevni globalni score. MEDIUM correctness. Glej `_codex_proximity_scope_verified.md`.

## Predlagani fix-valovi
- **Val A (correctness):** HIGH maps-crash; skill/substitution/BOX na gaming_session_id; parser orphan-R2 marker + midnight-crossover; winner_team invert; prox-scores scope.
- **Val B (de-dup):** MAP_IMAGE_MAP/helperji → shared modul; backend helper mixin; en schema vir; en migracijski sistem.
- **Val C (dual-frontend):** po owner potrditvi strategije.
- **Val D (a11y/perf, low):** session kartice keyboard/aria; N+1 (campaign recipients, skill history); non-sargable SUBSTRING.


## Tabela vseh potrjenih najdb

| ID | Sev | Dim | Področje | Najdba | Datoteka |
|----|-----|-----|----------|--------|----------|
| W2-01 | HIG | corr | god | `!last_session maps` / `maps full` always crash — SQL placeholder `{map_ids_st | `session_view_handlers.py:976-1004, 120` |
| W2-02 | MED | ux | dual | 4 production React routes depend on a gitignored, untracked, 3-month-stale bui | `modern-route-host.js:35-110` |
| W2-03 | MED | main | dual | ~9,200 lines of React page components are built/maintained but unreachable in  | `route-host.tsx:14-38` |
| W2-04 | MED | main | god | ~150 lines of helper logic duplicated near-byte-for-byte between session_view_ | `session_view_handlers.py:107-162, 555-` |
| W2-05 | MED | main | god | Full table DDL embedded as inline Python strings duplicates tools/schema_postg | `postgresql_database_manager.py:338-100` |
| W2-06 | MED | corr | god | winner_team Axis/Allies mapping is INVERTED on legacy sessions page | `sessions.js:1453-1457, 1708-1710` |
| W2-07 | MED | corr | skill | BOX scoring collapses orphan/duplicate R2 rounds into one map_number, silently | `box_scoring_service.py:234-266` |
| W2-08 | MED | corr | skill | Per-session skill rating keyed on round_date conflates multiple distinct gamin | `skill_rating_service.py:440-481` |
| W2-09 | LOW | main | ci | Dead flake8/pylint/pycodestyle config blocks for tools that are never installe | `pyproject.toml:8-65` |
| W2-10 | LOW | corr | data | Substitution detector collapses every match in a calendar day into 2-3 round b | `substitution_detector.py:164-230` |
| W2-11 | LOW | corr | data | Midnight-crossover R1 lookup skips the previous-day search whenever any same-d | `community_stats_parser.py:473-491` |
| W2-12 | LOW | ux | dual | React route-mode catalog contradicts the production router (claims ~19 'modern | `catalog.ts:18-42` |
| W2-13 | LOW | ux | dual | ~21 React page components (~10k LOC) duplicate live legacy-JS surfaces but are | `Proximity.tsx:1-1980` |
| W2-14 | LOW | ux | dual | Inconsistent / stale cache-bust versioning across the dual frontend invites Cl | `modern-route-host.js:1` |
| W2-15 | LOW | main | dual | Display/business logic duplicated across both stacks; the React copy diverges  | `SessionDetail.tsx:1` |
| W2-16 | LOW | main | dual | Canonical stack's own god-files: index.html 4894 lines holds all 27 view conta | `index.html:1` |
| W2-17 | LOW | perf | god | N+1 query in _collect_campaign_recipients (2 extra queries per recipient) | `availability.py:1127-1163` |
| W2-18 | LOW | perf | god | Non-sargable SUBSTRING(round_date,1,10) fallback seq-scans the largest table | `sessions_router.py:691` |
| W2-19 | LOW | main | god | Second, frozen migration system competes with migrations/*.sql + scripts/apply | `postgresql_database_manager.py:1003-13` |
| W2-20 | LOW | main | god | Overlapping session-summary endpoints each re-derive map_counts/scoring instea | `sessions_router.py:129,346,395,567,118` |
| W2-21 | LOW | main | god | Fatal-error troubleshooting message points at a non-existent schema path | `postgresql_database_manager.py:3196` |
| W2-22 | LOW | ux | god | 50-entry MAP_IMAGE_MAP + map helpers duplicated verbatim across 3 production J | `sessions.js:16-117` |
| W2-23 | LOW | ux | god | Collapsible session card and clickable rows are mouse-only (no keyboard/aria), | `sessions.js:1335-1443` |
| W2-24 | LOW | ux | god | Collapsed session-card 'Score' uses R1-only side wins, disagreeing with the te | `sessions.js:1376-1379` |
| W2-25 | LOW | corr | god | Running map score overlay desyncs when a map has an odd round count (orphan R1 | `sessions.js:1680-1690` |
| W2-26 | LOW | main | god | MAP_IMAGE_MAP copy-pasted across 3 modules and has drifted — Sessions list sho | `sessions.js:16` |
| W2-27 | LOW | main | god | Byte-identical helpers (formatDuration, coerceRoundId, mapImageFor, mapLabel)  | `session-detail.js:102` |
| W2-28 | LOW | main | god | Frontend god-files (proximity.js 4573 lines / 125 functions, session-detail.js | `proximity.js:1` |
| W2-29 | LOW | corr | skill | pcs_only rating scaling leaves CONSTANT unscaled, so session ratings are syste | `skill_rating_service.py:211-217` |
| W2-30 | LOW | perf | skill | Skill history endpoint is N+1 with O(N^2) cumulative full-history rescans (ran | `skill_rating_service.py:554-630` |
| W2-31 | LOW | perf | skill | compute_all_ratings scans proximity_kill_outcome twice for two derivable metri | `skill_rating_service.py:312-340` |

## Detajli (HIGH + MEDIUM)

### W2-01 · 🟠 HIGH · `!last_session maps` / `maps full` always crash — SQL placeholder `{map_ids_str}`/`{round_ids_str}` is never substituted
- **Področje:** God-files (backend) · `bot/services/session_view_handlers.py:976-1004, 1206-1234` · effort: trivial

**Dokaz:** In `show_maps_view` the query string (line 976, NOT an f-string) contains a literal CTE `SELECT id FROM rounds WHERE id IN ({map_ids_str})`, then is run via `fetch_all(query, tuple(map_session_ids))` at line 1004 with NO `.format(...)` call. `_send_round_stats` has the identical defect with `{round_ids_str}` (line 1208 / fetch_all line 1234). Every OTHER query in this file (lines 583,595,698,751,807,848,891,1396,1593) correctly calls `query.format(session_ids_str=session_ids_str)` — only these two omit it. I ran the exact CTE against Postgres via the db tool: `SELECT id FROM rounds WHERE id IN ({map_ids_str})` -> `syntax error at or near "{"`. Additionally the query has zero `?`/`$N` placeholders yet receives params, which asyncpg also rejects. Both methods are live-wired: last_session_cog.py:257-259 and session_cog.py:186-188 route `!last_session maps`, `!last_session maps full`, `!session ... maps` to them, with no surrounding try/except, so the command errors out for the user. Introduced 2026-02-28 (commit cbea046 'fix: resolve ruff lint errors') — a botched de-f-stringing that dropped both the `f` prefix and the substitution.

**Popravek:** Mirror the working siblings: build `placeholders = ','.join('?' * len(map_session_ids))`, change the CTE to `... WHERE id IN ({placeholders})`, and call `fetch_all(query.format(placeholders=placeholders), tuple(map_session_ids))` (same for `_send_round_stats` with round_session_ids). Or drop the CTE and inline `WHERE p.round_id IN ({placeholders})`. Add a smoke test that actually executes `!last_session maps` against a seeded session so a missing `.format()` regresses CI.

**Verifikacija (high):** I tried to refute this on three fronts and all failed. (1) Hidden substitution at the adapter layer: bot/core/database_adapter.py only translates `?`→`$N` (_translate_placeholders, line ~438); it does no `.format()` / brace substitution, so the literal `{map_ids_str}`/`{round_ids_str}` passes straight to asyncpg and the query also has zero `?` placeholders. (2) Outer error handling that masks/recovers: last_session_cog.py has a top-level try at line 98 with except at 491, but it merely sends '❌ Error...' to the user — it does not fix the query, confirming user-facing breakage rather than refut

---

### W2-02 · 🟡 MEDIUM · 4 production React routes depend on a gitignored, untracked, 3-month-stale build; absence renders a user-facing "Modern Route Offline" error panel
- **Področje:** Dual-frontend dolg · `website/js/modern-route-host.js:35-110` · effort: medium

**Dokaz:** route-registry.js marks exactly 4 viewIds as VIEW_MODE.MODERN (lines 168,181,194,291: proximity-player, proximity-replay, proximity-teams, skill-rating). These mount React from /static/modern/route-host.js. But `git ls-files website/static/modern/` returns 0 (the dir is gitignored: .gitignore:49 `website/static/modern/`). The on-disk build is dated Mar 31 09:01 while SkillRating.tsx has commits on Apr 1 (8d3ef81, 8bd889b 'ET Rating v2') AFTER the build — so the deployed skill-rating page is stale by the entire ET Rating v2 change. If prod is deployed without a manual `vite build` (and the artifact is not in git), loadModernRuntime() fails and renderUnavailable() (modern-route-host.js:35) shows users a literal 'Modern Route Offline / The modern renderer is not built yet' panel (modern-route-host.js:38) instead of the page.

**Popravek:** Pick ONE canonical surface for these 4 routes. Lowest-risk given 'legacy JS is production' + no-page-proliferation: fold them back to legacy (player-profile.js already renders the proximity-player aim/hit-region/heatmap surfaces; proximity.js covers replay/teams) and flip their mode to VIEW_MODE.LEGACY, then delete the modern-route-host plumbing. If React must stay, add `website/static/modern/` to a build step in deploy (deploy_release.sh) and to CI so the artifact is never missing/stale, and check the build into the release path. Do not leave a gitignored build as the only renderer for live routes.

**Verifikacija (high):** I tried to refute this by hunting for (a) the build being tracked in git, (b) a deploy/CI step that builds it, or (c) the routes falling back to legacy — none exist. All core claims hold: route-registry.js sets exactly 4 routes to VIEW_MODE.MODERN (proximity-player:168, proximity-replay:181, proximity-teams:194, skill-rating:291), which load from /static/modern/ (vite.config.ts:6 outputs to ../static/modern). `git ls-files website/static/modern/` returns 0 files; .gitignore:49 lists `website/static/modern/`. modern-route-host.js:35-48 renderUnavailable() renders the literal "Modern Route Offli

---

### W2-03 · 🟡 MEDIUM · ~9,200 lines of React page components are built/maintained but unreachable in production (only 4 of 29 routes are MODERN)
- **Področje:** Dual-frontend dolg · `website/frontend/src/route-host.tsx:14-38` · effort: medium

**Dokaz:** route-host.tsx:14-38 registers 25 React page components (lazy imports). But the production router website/js/route-registry.js dispatches only 4 viewIds to React: proximity-player (line 168), proximity-replay (181), proximity-teams (194), skill-rating (291). The other 25 routes use mode: VIEW_MODE.LEGACY and call legacy.loadXView() (grep -c: 4 MODERN vs 25 LEGACY). Production serves website/index.html + website/js/ (backend/main.py:335-336,372-373); React only mounts lazily via js/modern-route-host.js when a route is MODERN. So React pages NOT among those 4 are never reached. Measured dead/duplicate page lines: Proximity.tsx 1980, SessionDetail.tsx 1578, Availability.tsx 692, Admin.tsx 683, Home.tsx 466, RetroViz.tsx 387, GreatshotDemo.tsx 364, Profile.tsx 352, Greatshot.tsx 344, Weapons.tsx 272, Records.tsx 271, Uploads.tsx 271, Awards.tsx 286, Sessions2.tsx 267, Story.tsx 242, Maps.tsx 224, Leaderboards.tsx 197, UploadDetail.tsx 181, HallOfFame.tsx 144 (Rivalries.tsx/Replay.tsx already collapsed to 3-line 'not yet migrated' stubs) = ~9,207 lines. Each duplicates a live legacy file (SessionDetail.tsx 1578 vs js/session-detail.js 3740; Proximity.tsx 1980 vs js/proximity.js 4573).

**Popravek:** Pick ONE canonical stack. Pragmatic here: treat legacy js/ as canonical (it is what ships) and DELETE the ~9,200 lines of unreachable React pages plus their route-host.tsx:14-38 registrations, keeping only the 4 served React pages (ProximityPlayer, ProximityReplay, ProximityTeams, SkillRating). No user-visible change, removes a whole rotting parallel codebase (Rivalries/Replay already rotted to stubs). If instead finishing the migration, flip each route to MODERN incrementally and delete its legacy counterpart in the SAME PR — never leave both live-and-dead.

**Verifikacija (high):** I tried to refute this but the factual core holds up. (1) route-host.tsx:13-39 registers 27 lazy React page components (the finding says 25 plus the 2 stubbed rivalries/replay). (2) route-registry.js dispatch: grep confirms exactly 4 VIEW_MODE.MODERN entries (viewId proximity-player:166/168, proximity-replay:179/181, proximity-teams:192/194, skill-rating:289/291) vs 25 VIEW_MODE.LEGACY. (3) loadRoute() at route-registry.js:450-464 only calls runtime.modern.mountRoute for MODERN; LEGACY routes call definition.load (legacy renderer), so the other ~25 React pages are unreachable at runtime in pro

---

### W2-04 · 🟡 MEDIUM · ~150 lines of helper logic duplicated near-byte-for-byte between session_view_handlers and session_graph_generator
- **Področje:** God-files (backend) · `bot/services/session_view_handlers.py:107-162, 555-573, 163-477` · effort: medium

**Dokaz:** session_view_handlers.py and bot/services/session_graph_generator.py carry the same private helpers with effectively identical bodies: `_parse_time_to_seconds` (view 78-95 vs graph 81-99), `_row_get` (view 98-105 vs graph 101-108), `_call_service_method`+`_normalize_round_factor_payload` (view 107-162 vs graph 110-164 — diff is a single blank line), and `_get_player_stats_columns` (view 555-573 vs graph 61-80 — only a `@staticmethod` decorator differs). `diff` over view 78-162 vs graph 81-164 reports only 3 changed lines across ~85 lines. The larger timing helpers `_get_round_timing_shadow` (view 163-311 vs graph 165-266) and `get_session_timing_dual_by_guid` (view 313-477 vs graph 266-385) started from the same source and have since DIVERGED (view added round_rows / missing_reason fields the graph version lacks), so timing fixes must be made twice and are already drifting.

**Popravek:** Extract the stable helpers (`_parse_time_to_seconds`, `_row_get`, `_call_service_method`, `_normalize_round_factor_payload`, `_get_player_stats_columns`) into one `SessionTimingMixin` or module `bot/services/session_timing_helpers.py` shared by both classes, then reconcile the two timing-shadow / dual-by-guid implementations into one parameterized method.

**Verifikacija (high):** Could not refute the core claim. Read both files and diffed the cited regions: `_parse_time_to_seconds`, `_row_get`, `_call_service_method`, `_normalize_round_factor_payload`, and `_get_player_stats_columns` are near-byte-for-byte duplicated (diff of view 78-162 vs graph 81-164 = only 2 changed lines: a docstring and a blank line). The timing helpers `_get_round_timing_shadow` and `get_session_timing_dual_by_guid` have genuinely diverged (view emits round_rows/diff_seconds/missing_reason/rounds_played that the graph versions omit), confirming the two-places-to-fix drift risk. One evidence deta

---

### W2-05 · 🟡 MEDIUM · Full table DDL embedded as inline Python strings duplicates tools/schema_postgresql.sql (two schema sources of truth)
- **Področje:** God-files (backend) · `postgresql_database_manager.py:338-1002` · effort: medium

**Dokaz:** `_create_schema_if_missing` (lines 338-1002, ~660 lines) hand-writes 25 `CREATE TABLE IF NOT EXISTS` statements as Python triple-quoted strings (e.g. the 57-column player_comprehensive_stats DDL at lines 393-450). The canonical tools/schema_postgresql.sql defines 101 `CREATE TABLE`s. The manager never reads that .sql file (no grep reference), so it creates only a partial subset and maintains column definitions in parallel; any column added in the .sql or a migration is invisible here and vice-versa.

**Popravek:** Make tools/schema_postgresql.sql the single source of truth: have `_create_schema_if_missing` load and execute that file instead of inlining DDL, or delete the inline DDL for tables already defined in the .sql and document the authoritative file.

**Verifikacija (high):** Attempted to refute by checking whether the manager loads tools/schema_postgresql.sql (it does not — only a stale, wrong-path log string references it), and whether install/bootstrap uses the .sql directly (install.sh lines 669-677 bootstraps via the manager's inline DDL, not the canonical file). Both checks confirm the duplication rather than refute it. Counts verified: 25 inline CREATE TABLE IF NOT EXISTS in postgresql_database_manager.py vs 101 CREATE TABLE in tools/schema_postgresql.sql. Line range 338-1002 for _create_schema_if_missing is accurate (next def at 1003). The dual-source-of-tr

---

### W2-06 · 🟡 MEDIUM · winner_team Axis/Allies mapping is INVERTED on legacy sessions page
- **Področje:** God-files (frontend, legacy JS) · `website/js/sessions.js:1453-1457, 1708-1710` · effort: small

**Dokaz:** sessions.js winnerTeamLabel() maps winner_team===1 -> 'Allies' and ===2 -> 'Axis' (lines 1454-1455), and the colour branch at 1710 maps 1->brand-blue / 2->brand-rose. Ground truth proves the opposite: the Lua webhook hard-codes TEAM_AXIS=1 / TEAM_ALLIES=2 (vps_scripts/stats_discord_webhook.lua:199-200, get_winner_team() returns 1=Axis,2=Allies at :829-838) and the parser comments 'defender_team defaults to 1 (Axis)' (bot/community_stats_parser.py:113). DB cross-check confirms rounds.winner_team agrees with lua_round_teams.winner_team on the same scale (winner_team=1 -> 275/278 lua=1; =2 -> 383/388 lua=2). The sibling god-file session-detail.js:567 maps the SAME column correctly: winnerTeam===1 -> 'Axis', ===2 -> 'Allies' (and colour 1->rose/2->blue at :568) — i.e. the two production JS files render the identical rounds.winner_team value with OPPOSITE side labels and OPPOSITE colours. The upstream backend helper website_session_data_service._team_name (:13-19) shares sessions.js's inverted mapping (1->'Allies'), so the round 'winner' string fed to sessions.js is already flipped, making the wrong side visible to users.

**Popravek:** Flip winnerTeamLabel to 1->'Axis', 2->'Allies' and swap the colour branch at line 1710 to match session-detail.js:567-568. Also fix the shared backend inversion in website_session_data_service._team_name (and the allies_wins/axis_wins CASE labels in sessions_router.py:474-475) so the whole sessions path uses the canonical 1=Axis,2=Allies; add a single shared constant to stop the convention drifting again.

**Verifikacija (high):** Tried to refute on three fronts and failed each: (1) Canonical scale — DB proves winner_team=1 is Axis (281 axis-won vs 3) and =2 is Allies (391 allies-won vs 5), matching Lua (TEAM_AXIS=1/TEAM_ALLIES=2, get_winner_team comment) and the parser comment; so sessions.js (1->'Allies') is genuinely inverted. (2) Dead-code defense — sessions.js is NOT dead: route-registry.js:62-69 wires #/sessions to loadSessionsView and app.js:18 imports it; the /stats/session/{id}/detail endpoint (sessions_router.py:1450-1454) passes raw numeric winner_team straight to the inverting winnerTeamLabel. (3) Self-consi

---

### W2-07 · 🟡 MEDIUM · BOX scoring collapses orphan/duplicate R2 rounds into one map_number, silently dropping real rounds and pairing mismatched maps
- **Področje:** Skill rating + storytelling · `/home/samba/share/slomix_discord/website/backend/services/box_scoring_service.py:234-266` · effort: medium

**Dokaz:** _fetch_session_rounds() assigns map_number by incrementing ONLY when round_number==1 ('if round_num == 1: map_number += 1'), then calculate_session_score() groups with 'maps.setdefault(r.map_number, {})[r.round_number] = r'. When a session contains R2 rounds with no preceding R1 (orphan R2) or two R2s in a row, every such R2 keeps the previous map_number and overwrites dict slot [2]. DB confirms this is common: gaming_session_id 51 is 5 consecutive orphan R2 rows (supply, te_escape2, sw_goldrush_te, etl_frostbite, erdenberg_t2, all round_number=2, no R1), so all 5 land on map_number=0; maps[0] keeps only the LAST R2 and score_map returns immediately because r1 is None -> the entire session (5 decisive maps incl. a Fullhold and Completeds) scores 0-0. A query for R2 whose prior round in time-order is also R2/none found 9 affected sessions (ids 99,51,84 each with 5; 50,41,44,56,47,42 with 2). In mixed sessions the surviving R2 is paired with an R1 from a DIFFERENT map, so winner_team is checked against the wrong alpha_side and the map score is fabricated.

**Popravek:** Pair rounds deterministically by the existing match/round-linker key (map_name + match_id / round_start_unix), not 'increment on R1'. At minimum start a new map_number whenever round_number==1 OR the current map_number already holds a round_number==2 (so a second R2 starts a fresh bucket), and skip/flag orphan R2 instead of overwriting. Surface a 'rounds_dropped' count in the API response.

**Verifikacija (high):** I tried to refute this finding and could not. The code at box_scoring_service.py:240-266 (_fetch_session_rounds) increments map_number ONLY when round_num==1 ('if round_num == 1: map_number += 1'), and calculate_session_score (line 135) groups via 'maps.setdefault(r.map_number, {})[r.round_number] = r', which overwrites slot [2] for every consecutive R2. Both failure modes reproduce against live data:\n\n(1) Orphan-only collapse -> 0-0: gaming_session_id 51 (2025-05-10) has exactly 5 rounds with round_number=2 and NO R1 rows at all (only round_number 0 and 2 exist; ids 9294/9296/9298/9300/9302

---

### W2-08 · 🟡 MEDIUM · Per-session skill rating keyed on round_date conflates multiple distinct gaming sessions played on the same calendar day
- **Področje:** Skill rating + storytelling · `/home/samba/share/slomix_discord/website/backend/services/skill_rating_service.py:440-481` · effort: medium

**Dokaz:** compute_session_ratings(), compute_session_map_ratings() and get_player_session_history() scope a 'session' with 'WHERE ... round_date = $2' / 'round_date <= $2' (TEXT date), and the docstring calls round_date a 'gaming session proxy'. This violates the project CRITICAL RULE 'ALWAYS use gaming_session_id for session queries (NOT dates)'. DB shows the conflation is real: round_date 2026-03-25 maps to 4 distinct gaming_session_id values, and 2026-06-21/06-16/06-11/05-27/2025-12-21/2025-05-11/2025-01-07 each map to 2. On those days the 'session rating' merges 2-4 separate evenings' aggregates (SUM(kills)/COUNT rounds across all of them), producing a per-session number and history delta that correspond to no actual gaming session.

**Popravek:** Scope these queries by gaming_session_id (join rounds r ON pcs.round_id = r.id and filter r.gaming_session_id), and key history/percentile lookups on gaming_session_id rather than round_date. If a date-based API contract must be kept, return one entry per gaming_session_id within the date.

**Verifikacija (high):** I tried to refute this but could not. The code at skill_rating_service.py:440-481 (compute_session_ratings), 498-537 (compute_session_map_ratings) and 554-575 (get_player_session_history) all scope a "session" via WHERE player_guid=$1 AND round_date=$2 (and round_date>=... for history), never via gaming_session_id. The docstring at line 443 explicitly admits round_date is a "gaming session proxy", and skill_router.py:204-214 exposes this as a date-keyed session drill-down (session_date ISO date). This directly violates the documented CRITICAL RULE "ALWAYS use gaming_session_id for session quer

---

## Detajli (LOW — strnjeno)

- **W2-09** [maintainability/CI / backlog / security] Dead flake8/pylint/pycodestyle config blocks for tools that are never installed or run — `pyproject.toml:8-65`. _Fix:_ Delete the [tool.pycodestyle], [tool.flake8], and [tool.pylint] sections (lines 8-65). All their concerns are already expressed in [tool.ruff.lint] ignore/selec
- **W2-10** [correctness/Data pipeline core] Substitution detector collapses every match in a calendar day into 2-3 round buckets and is keyed on round_date, not gaming_session_id — `substitution_detector.py:164-230`. _Fix:_ Scope both queries by gaming_session_id (join rounds on round_id) instead of `round_date LIKE`, and key rosters by a true per-match identifier (gaming_session_i
- **W2-11** [correctness/Data pipeline core] Midnight-crossover R1 lookup skips the previous-day search whenever any same-day R1 of the map exists, even if none precede the R2 — `community_stats_parser.py:473-491`. _Fix:_ Always run the previous-day search and merge its results into potential_files (or run STEP 3 whenever STEP 2 produced no candidate strictly before the R2 within
- **W2-12** [ux/Dual-frontend dolg] React route-mode catalog contradicts the production router (claims ~19 'modern' routes; reality is 4) — abandoned strangler migration left misleading state — `catalog.ts:18-42`. _Fix:_ Treat route-registry.js as the single source of truth. Either delete catalog.ts/route-host.tsx mode metadata or regenerate it from route-registry so the two can
- **W2-13** [ux/Dual-frontend dolg] ~21 React page components (~10k LOC) duplicate live legacy-JS surfaces but are unreachable in production — divergence means fixes land in only one twin — `Proximity.tsx:1-1980`. _Fix:_ Decide canonical = legacy JS (matches north star: small community, no page proliferation, no React build mandated). Delete the unreachable React page set (or mo
- **W2-14** [ux/Dual-frontend dolg] Inconsistent / stale cache-bust versioning across the dual frontend invites Cloudflare 24h drift — `modern-route-host.js:1`. _Fix:_ Adopt one release-version constant (e.g. read package version / git short-sha) appended as `?v=` to ALL JS/CSS including the modern build entry, set once per re
- **W2-15** [maintainability/Dual-frontend dolg] Display/business logic duplicated across both stacks; the React copy diverges silently because it is not served — `SessionDetail.tsx:1`. _Fix:_ After removing the dead React pages (prior finding) this duplication vanishes for those routes. For the few concerns that must exist in both surviving stacks (c
- **W2-16** [maintainability/Dual-frontend dolg] Canonical stack's own god-files: index.html 4894 lines holds all 27 view containers; proximity.js 4573, session-detail.js 3740 — `index.html:1`. _Fix:_ Low priority for a small team: opportunistically split index.html into per-view HTML partials fetched on demand (route-registry already lazy-loads view logic), 
- **W2-17** [performance/God-files (backend)] N+1 query in _collect_campaign_recipients (2 extra queries per recipient) — `availability.py:1127-1163`. _Fix:_ Collapse into the initial query with two LEFT JOINs: `availability_entries ae LEFT JOIN subscription_preferences sp ON sp.user_id = ae.user_id LEFT JOIN player_
- **W2-18** [performance/God-files (backend)] Non-sargable SUBSTRING(round_date,1,10) fallback seq-scans the largest table — `sessions_router.py:691`. _Fix:_ Prefer the gaming_session_id branch (already sargable). For the date fallback, query rounds by `round_date` (which IS indexed via idx_rounds_date) and join to P
- **W2-19** [maintainability/God-files (backend)] Second, frozen migration system competes with migrations/*.sql + scripts/apply_migrations.py — `postgresql_database_manager.py:1003-1344`. _Fix:_ Retire the inline ladder: confirm migrations 1-11 exist as numbered files under migrations/, then delete `_migrate_schema_if_needed` and route the manager throu
- **W2-20** [maintainability/God-files (backend)] Overlapping session-summary endpoints each re-derive map_counts/scoring instead of sharing one path — `sessions_router.py:129,346,395,567,1180,1379`. _Fix:_ Collapse date-keyed and id-keyed paths onto one internal `_load_session_summary(gaming_session_id)` helper (date endpoints already resolve date->gaming_session_
- **W2-21** [maintainability/God-files (backend)] Fatal-error troubleshooting message points at a non-existent schema path — `postgresql_database_manager.py:3196`. _Fix:_ Update the message to `tools/schema_postgresql.sql`.
- **W2-22** [ux/God-files (frontend, legacy JS)] 50-entry MAP_IMAGE_MAP + map helpers duplicated verbatim across 3 production JS files (asset drift) — `sessions.js:16-117`. _Fix:_ Extract the map-image table + normalizeMapKey/mapImageFor/mapLabel/formatDuration into a shared module (e.g. js/map-utils.js, alongside existing js/utils.js) an
- **W2-23** [ux/God-files (frontend, legacy JS)] Collapsible session card and clickable rows are mouse-only (no keyboard/aria), inconsistent with availability.js — `sessions.js:1335-1443`. _Fix:_ Make the session-card header a `<button>` (or add role="button" tabindex="0" + Enter/Space handler) and set aria-expanded to mirror expandedSessions state; give
- **W2-24** [ux/God-files (frontend, legacy JS)] Collapsed session-card 'Score' uses R1-only side wins, disagreeing with the team-aware score shown when expanded — `sessions.js:1376-1379`. _Fix:_ Either surface the team-aware scoring summary (already returned by the detail/scoring payload) on the collapsed card, or relabel the collapsed metric as 'R1 sid
- **W2-25** [correctness/God-files (frontend, legacy JS)] Running map score overlay desyncs when a map has an odd round count (orphan R1/R2) — `sessions.js:1680-1690`. _Fix:_ Match scoring entries to rounds by a stable key (map_name + round_start_unix or round_id) instead of floor(rounds.length/2); or count only completed R1+R2 pairs
- **W2-26** [maintainability/God-files (frontend, legacy JS)] MAP_IMAGE_MAP copy-pasted across 3 modules and has drifted — Sessions list shows generic placeholder for maps that Session Detail renders correctly — `sessions.js:16`. _Fix:_ Move MAP_IMAGE_MAP plus mapImageFor()/mapLabel()/normalizeMapKey() into a single shared module (e.g. website/js/maps.js) and import it in sessions.js, session-d
- **W2-27** [maintainability/God-files (frontend, legacy JS)] Byte-identical helpers (formatDuration, coerceRoundId, mapImageFor, mapLabel) duplicated despite both files already importing utils.js — `session-detail.js:102`. _Fix:_ Hoist formatDuration, coerceRoundId, mapLabel, mapImageFor (and MAP_IMAGE_MAP per the high finding) into utils.js or a maps.js shim and import them. Removes ~80
- **W2-28** [maintainability/God-files (frontend, legacy JS)] Frontend god-files (proximity.js 4573 lines / 125 functions, session-detail.js 3740, availability.js 2415, sessions.js 2343) exceed maintainable size — `proximity.js:1`. _Fix:_ Pragmatic, low-risk ES-module splits along the existing section boundaries (the functions are already grouped). e.g. proximity.js -> proximity-scope.js (scope/c
- **W2-29** [correctness/Skill rating + storytelling] pcs_only rating scaling leaves CONSTANT unscaled, so session ratings are systematically below global ratings (contradicting the stated intent) — `skill_rating_service.py:211-217`. _Fix:_ Scale CONSTANT consistently in pcs_only mode, or recompute CONSTANT/scale so both global and pcs_only average players land on the same target (e.g. 0.50). Add a
- **W2-30** [performance/Skill rating + storytelling] Skill history endpoint is N+1 with O(N^2) cumulative full-history rescans (range_days up to 3650) — `skill_rating_service.py:554-630`. _Fix:_ Replace the per-date loop with a single GROUP BY round_date query to get all per-session aggregates in one pass, and compute the cumulative line with SQL window
- **W2-31** [performance/Skill rating + storytelling] compute_all_ratings scans proximity_kill_outcome twice for two derivable metrics — `skill_rating_service.py:312-340`. _Fix:_ Merge prox_quality and prox_perm into one subquery selecting both AVG(CASE outcome...) and COUNT(*) FILTER (WHERE outcome='gibbed')::REAL / NULLIF(COUNT(*),0) g

## Ovržene (false-positive, 18)

- [data_pipeline_core] R2 stored as raw cumulative (no differential, no marker) when the R1 file cannot be found
- [data_pipeline_core] round_correlations.map_name has no index; Strategy 1/2 lookups seq-scan + sort on every pipeline eve
- [data_pipeline_core] SubstitutionDetector scans entire player_comprehensive_stats twice via unindexed round_date LIKE (cu
- [god_files_backend] gaming_session_id gap computed against the GLOBAL latest round, not the chronological neighbor — out
- [god_files_backend] Per-round N+1 in _get_round_timing_shadow compat path
- [god_files_frontend] sessions.js and availability.js loaded without ?v= cache-bust while peers have it (stale-module SPA 
- [god_files_frontend] Triple-implemented sessions surface (legacy x2 + React) — page proliferation with no canonical owner
- [god_files_frontend] Session MVP widget ignores its date argument and always fetches the global session leaderboard
- [god_files_frontend] normalizeMapKey() has the same name but different semantics in proximity.js vs the session modules
- [dual_frontend_debt] Docs/memory claim 'React migration COMPLETE — 19/19 routes' but ground truth is 4 of 29 routes serve
- [ci_backlog_security] python-multipart still pinned to vulnerable 0.0.22 (CVE-2026-40347 / CVE-2026-42561) — backlog item 
- [ci_backlog_security] No dependency-CVE scanning in CI (no pip-audit, no dependabot) — root cause that lets pinned CVEs pe
- [ci_backlog_security] starlette transitive CVE (PYSEC-2026-161) still unpatched — pinned by fastapi==0.133.1, backlog open
- [ci_backlog_security] paramiko AutoAddPolicy (blind host-key trust) still present in dev/ops SSH tools — MITM on first con
- [ci_backlog_security] mypy is configured in pyproject and claimed in docs, but is not installed or enforced anywhere
- [ci_backlog_security] No dependency-vulnerability gate in CI; 2026-06-15 backlog CVEs (multipart, starlette) still unremed
- [ci_backlog_security] Inconsistent paramiko host-key policy across tools/ (AutoAddPolicy vs RejectPolicy in same directory
- [ci_backlog_security] docs/CLAUDE.md is a byte-identical duplicate of root CLAUDE.md