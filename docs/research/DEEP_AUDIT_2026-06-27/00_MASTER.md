# Slomix — Globok audit, Wave 1 (zadnji mesec)

**Datum:** 2026-06-27 · **Obseg:** spremembe od 2026-05-27 (S1–S7, betting/seasons, proximity v7, bot reliability, data integrity)
**Metoda:** večagentni Mandelbrot RCA v2 + adversarialno prove-or-drop preverjanje (49 agentov, ~2.7M tokenov)
**Predhodni audit:** `docs/research/WHOLE_CODEBASE_AUDIT_2026-06-15.md` (scanner-voden) — ta gradi nanj, ne ponavlja.

**Rezultat:** 27 potrjenih najdb (0 critical, 1 high, 7 medium, 19 low) · 4 ovrženih (false-positive, glej `99_false_positives.md`).

## Izvršni povzetek in sinteza

## Executive Summary

Last month's work (S1-S7 sprints, betting/seasons, proximity v7, bot reliability) is **broadly healthy**: every confirmed finding was adversarially verified, and there are **zero criticals and no exploitable web XSS or SQLi** — the parameterized-query and output-escaping conventions held everywhere they were checked. The single **high** is a data-correctness bug in the brand-new proximity v7 aim-lock feature (round-end flush stamps `duration_ms` with round-end time instead of `last_seen`, inflating the headline "lock time" leaderboard by ~20% / 795k ms of phantom time). The dominant pattern is **not security but quantitative correctness**: roughly half the findings are "a real-looking number that is silently wrong" — contaminated baselines, grain mismatches, bot-polluted season awards, double-fullhold mis-scoring, and a coverage-biased bait score — which matter precisely because "no fabricated numbers" is the project's north star. Security findings are all **low-to-medium and mostly defense-in-depth or insecure-defaults** (Secure-cookie default, one missing CSRF header on a read-only route, unsanitized display name), with the one genuine integrity gap being the **parimutuel betting market having no cutoff**, allowing hindsight bets to fabricate a permanent "Oracle" season award. UX findings are consistently **small polish/accessibility gaps in newly-shipped legacy-JS pages** (Tonight, Wrapped, Record Book, auth). Performance findings are real N+1 / cache-omission patterns but correctly self-scoped as low-impact at 30-50 players. Overall: ship-quality work, but the new live/proximity/awards surfaces need a correctness pass before their numbers are trusted as "memory."

## Cross-Cutting Themes

1. **Population/grain mismatches in aggregates** (the most recurring class). The same conceptual error appears across S1, S5, awards, and proximity: numerator and denominator are drawn from different row populations or different time grains.
   - Baseline includes the session being narrated *and future sessions* (`narrative.py:399` drops `before_session_id`).
   - Session-DATE kills compared against per-`gaming_session_id` baseline averages (`baseline.py:47`).
   - On-This-Day SUMs winners across multiple gaming sessions on one date (`on_this_day_service.py:50-60`).
   - bait_score divides full-coverage lifetime deaths by proximity-only (~20%-coverage) avenged counts (`players_profile_router.py:273`).
   - **Root lesson:** scope everything to `gaming_session_id` and to the *same* round-coverage set — exactly the convention CLAUDE.md already mandates but these new surfaces drift from.

2. **Bot/test-data not excluded from new aggregates.** The `OMNIBOT%` / `[BOT]%` exclusion is applied 11x in older routers but was *omitted* in season awards (`season_awards_service.py:68-133`) and the proximity aim-lock leaderboard. The upstream `is_bot_round=false` detection gap (a known, documented issue) means the per-GUID/name filter is the *only* reliable guard, so its absence in new code directly risks engraving a bot as a permanent award.

3. **UTC-vs-local timezone drift, recurring.** Two independent instances (`players_router.py:284` Tonight date boundary; `stopwatch_pairing.py:141-169` mixed-source pairing) repeat a bug class the codebase has *already fixed once* in the round linker — and the code even contradicts itself on host TZ (`round_linker.py:257` "UTC prod" vs `ultimate_bot.py:1737` "Both machines are CET"). This contradiction should be reconciled centrally.

4. **The `executemany` batch helper exists but new import code uses row-by-row `execute`.** Both v7 parser imports (`parser.py:2775-2865`) and weapon-stat imports (`stats_import_mixin.py:877-901`) loop one await per row despite `database_adapter.py:348`. Low impact at current scale, but it's a consistent missed-convention.

5. **Legacy-JS UX consistency drift on freshly-shipped pages.** New pages (Tonight, Wrapped, Record Book) and the account flow reuse ad-hoc patterns (`div.onclick`, native `prompt`/`alert`, hide-on-error, premature `_loaded=true`) instead of the file's own established helpers (real `<button>`s in `renderLinkCandidates`, `openModal`, inline error messaging). The right fixes already exist in the same files.

## Top Priority Fixes — Suggested Bundled PR Waves

### Wave 1 — Data Correctness (highest value; defends the "no fabricated numbers" north star)
Bundle these; they are the trust-critical bugs:
- **[HIGH] proximity aim-lock round-end flush** (`proximity_tracker.lua:3372`) — close at `last_seen`, add a duration clamp as defense-in-depth. *Note: requires Lua deploy (full map reload, owner-gated) + backfill/flag of pre-fix rows.*
- **[MED] narrative baseline contamination** (`narrative.py:399`) — pass `before_session_id` (the gsid is already resolved at `narrative.py:277-281`).
- **[MED] season awards bot pollution** (`season_awards_service.py:68-133` + `_session_player_pool`) — add the shared `OMNIBOT%`/`[BOT]%` predicate (extract a helper to stop the drift).
- **[MED] Tonight double-fullhold mis-score** (`players_router.py:375-388`) — mirror `BOXScoringService.score_map`'s draw handling.
- **[MED] parimutuel auto-settle label binding** (`bets_router.py:272-283`) — bind market to roster (or require explicit admin outcome) so 1→a/2→b isn't a silent assumption.
- *(Lower in the same wave, cheap to include):* baseline grain mismatch (`baseline.py`), On-This-Day per-session grouping, bait_score coverage scoping, aim-lock sample-weighted means, aim-lock bot/orphan exclusion.

### Wave 2 — Security + Integrity (small, mostly trivial)
- **[MED] betting cutoff** (`bets_router.py:110-147`) — enforce `closes_at` / require a `closed` state before settle; this also protects the permanent Oracle award (overlaps Wave 1 in spirit).
- **[LOW] Secure-cookie default** (`auth.py:8`) — default `SESSION_HTTPS_ONLY=true`, opt-out for local dev.
- **[LOW] display-name sanitization** (`auth.py:946`) — strip markdown/control chars on the `custom` path.
- **[LOW] missing CSRF header** (`planning.py:1001`) — one-line `_require_ajax_csrf_header`.

### Wave 3 — Performance + Cache (low-impact, do opportunistically)
- **[LOW] Tonight/hold-probability HTTP cache** (`http_cache_middleware.py:31-51`) — add to `cacheable_prefixes` + 15s live TTL (trivial, coalesces 8s polls).
- **[LOW] v7 parser executemany** (`parser.py:2775-2865`) and **weapon-stats executemany** (`stats_import_mixin.py:877-901`) — drop-in batch (savepoint atomicity preserved).

### Wave 4 — UX Polish (legacy JS; reuse existing in-file patterns)
- ET Rating scale mismatch (`player-profile.js:527` → use `_num(...,3)`) — the most visible (looks like a bug to every visitor).
- Record Book `_loaded=true`-before-fetch (`record-book.js:31`); display-name block hide-on-error (`auth.js:699`); Tonight scroll reset (`tonight.js:176`); a11y `<button>` for search results (`auth.js:570`); Wrapped modal Escape/backdrop + inert error buttons (`wrapped.js:21`); native `prompt/alert` → themed modal (`auth.js:705`).

### Separate / owner-gated
- **[MED] stopwatch pairing host-TZ dependence** (`stopwatch_pairing.py`) — fix only matters when the backfill script runs on a non-CET host; pair the TZ-explicit parse with reconciling the contradictory TZ comments. Dormant on the CET dev host, live risk on UTC prod.
- **[LOW] promotion-job stale-claim reaper** (`scheduler_mixin.py:233-395`) — add a requeue for `status='running'` orphaned by a mid-dispatch restart.

## Risky-Looking, Checked Out Clean (confidence signal)

These were investigated and **proven not to be bugs** — worth recording so they aren't re-flagged:
- **No web XSS** despite the unsanitized display name and several `innerHTML`-shaped paths: legacy JS `escapeHtml` (auth.js:148/331/572) and React auto-escaping neutralize it. The display-name issue is real only for **Discord embed markdown**, not the website.
- **No SQLi**: every flagged query is parameterized via the `?`→`$n` adapter.
- **The `alias` display-name path is correctly guarded** (must match a recorded `player_aliases` row) — only the `custom` path is the gap.
- **On-This-Day "per-map inflation" and "MAX picks arbitrary roster" sub-claims are false** against real data (all 33 rows are `map_name='ALL'`, one distinct team name each); only the multi-gaming-session conflation is real and minor.
- **Aim-lock "bots top the leaderboard" is overstated** — real humans hold ranks 1-5 at 4-5x bot totals; bots are ~10% of rows at ranks 6/8. Still worth filtering, but not "the panel is bot-test data."
- **executemany fixes are safe inside existing savepoints** — `connection()` reuses the active tx connection, so atomicity is preserved (verified, not assumed).
- **The promotion-job 20:00 daily restart is NOT the trigger** for the stale-claim bug (restart precedes the dispatch window); only an ad-hoc crash/deploy during dispatch triggers it — the defect stands but the cited scenario doesn't.

Net: the team's new code is solid on the hard guarantees (no injection, no escaping holes, safe transactions). The work needed is a **correctness sweep of the new aggregate/live surfaces** to align them with the project's own scoping conventions — concentrated, cheap fixes, none requiring any of the scale/architecture machinery the project explicitly rejects.

## Tabela vseh potrjenih najdb

| ID | Sev | Dim | Področje | Najdba | Datoteka |
|----|-----|-----|----------|--------|----------|
| W1-01 | HIG | corr | proximity | Aim-lock round-end flush uses round-end time (not last_seen), inflating dur | `proximity_tracker.lua:3372` |
| W1-02 | MED | corr | data | Stopwatch pairing mixes UTC-epoch (round_start_unix) with host-local-naive  | `stopwatch_pairing.py:158-169 (_parse_dt_` |
| W1-03 | MED | corr | s1 | Per-player baseline includes the session being narrated (and newer ones) —  | `narrative.py:398-401 (root cause spans w` |
| W1-04 | MED | corr | s3 | Season Iron Man / Most Improved awards do not exclude bots (OMNIBOT/[BOT]); | `season_awards_service.py:68-133` |
| W1-05 | MED | corr | s3 | Parimutuel auto-settle maps session winning_team to team_a/team_b with no b | `bets_router.py:272-283` |
| W1-06 | MED | secu | s3 | Parimutuel market has no betting cutoff — hindsight bets game the points le | `bets_router.py:110-147, 245-284` |
| W1-07 | MED | corr | s5 | bait_score mixes full-coverage lifetime deaths with proximity-only avenged  | `players_profile_router.py:248-275` |
| W1-08 | MED | corr | s5 | Tonight live hub mis-scores double-fullhold maps as a win instead of a 1-1  | `players_router.py:375-388` |
| W1-09 | LOW | corr | bot | Promotion job claimed to 'running' is never recovered if the bot restarts m | `scheduler_mixin.py:233-395` |
| W1-10 | LOW | perf | bot | Weapon stats inserted one-row-per-await (N+1) instead of executemany within | `stats_import_mixin.py:877-901` |
| W1-11 | LOW | corr | proximity | avg_err_deg / avg_dist are an unweighted mean-of-means across lock windows | `proximity_teamplay.py:184-185` |
| W1-12 | LOW | corr | proximity | Aim-lock leaderboard surfaces omni-bot players and orphan (unlinked) rounds | `proximity_teamplay.py:176-201` |
| W1-13 | LOW | perf | proximity | v7 import methods do row-by-row INSERTs instead of using the available exec | `parser.py:2775-2865` |
| W1-14 | LOW | corr | s1 | Baseline granularity mismatch: session-DATE kill totals compared against a  | `narrative.py:350-361, 499-501` |
| W1-15 | LOW | corr | s1 | On-This-Day day score conflates multiple gaming sessions / different roster | `on_this_day_service.py:46-69` |
| W1-16 | LOW | secu | s1 | Custom display name accepts arbitrary content (no sanitization) and is surf | `auth.py:914-979` |
| W1-17 | LOW | secu | s1 | Authenticated session cookie lacks Secure flag by default (SESSION_HTTPS_ON | `auth.py:8` |
| W1-18 | LOW | ux | s1 | Player-search result rows are clickable <div>s — not keyboard/screen-reader | `auth.js:570-588 (also 328-336)` |
| W1-19 | LOW | ux | s1 | Display-name management block silently disappears on any transient API erro | `auth.js:684-702` |
| W1-20 | LOW | ux | s1 | S2 account flow uses native prompt()/confirm()/alert() instead of the site' | `auth.js:351, 705` |
| W1-21 | LOW | secu | s3 | `/today/balanced-teams` POST is the only planning write-shaped endpoint mis | `planning.py:1001-1010` |
| W1-22 | LOW | corr | s5 | Tonight uses UTC date boundary (captured_at::date = CURRENT_DATE) which spl | `players_router.py:284` |
| W1-23 | LOW | perf | s5 | Tonight live hub endpoint (/api/stats/tonight) and /api/stats/hold-probabil | `http_cache_middleware.py:31-51 (cacheabl` |
| W1-24 | LOW | ux | s5 | ET Rating shown on two different scales on the same profile page ("342" vs  | `player-profile.js:527` |
| W1-25 | LOW | ux | s5 | Record Book tab marks itself loaded BEFORE the fetch, so a transient failur | `record-book.js:31` |
| W1-26 | LOW | ux | s5 | Tonight hub rebuilds its entire DOM every 8s poll, resetting horizontal scr | `tonight.js:176` |
| W1-27 | LOW | ux | s5 | Wrapped share-card modal: no Escape/backdrop close, no dialog semantics, in | `wrapped.js:21` |

## Predlagani fix-valovi
Glej sintezo zgoraj (Top Priority Fixes). Po `feedback_single_pr_when_possible` se sorodne najdbe bundle-ajo v en PR na temo. Vrstni red: (1) data-correctness, (2) security+integrity, (3) performance+cache, (4) UX polish. Lua deploy + backfill ostajata owner-gated.

## Per-dimenzija poročila
- `01_security.md` — varnostne najdbe
- `02_performance_cache.md` — performance & cache
- `03_data_correctness.md` — data correctness ('no fabricated numbers')
- `04_ux_design.md` — UI/UX & dizajn
- `99_false_positives.md` — ovržene najdbe (prove-or-drop transparentnost)