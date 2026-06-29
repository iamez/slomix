# Wave 1 — Data Correctness (13 najdb)

> Vse najdbe adversarialno preverjene (prove-or-drop). Severity je po-verifikaciji prilagojena.

### W1-01 · 🟠 HIGH · Aim-lock round-end flush uses round-end time (not last_seen), inflating duration_ms by ~20% of total leaderboard lock-time

- **Področje:** Proximity v7 (aim-lock + teamplay endpointi + Lua flag)
- **Datoteka:** `proximity/lua/proximity_tracker.lua:3372`
- **Dimenzija:** correctness · **Effort:** small

**Dokaz:** closeAimLock() computes `duration = end_time - lock.start_time` (line 1117). EVERY normal close path passes `last_seen` (in-loop closes lines 1194/1211/1214/1218 and the stale-owner sweep line 1234). The ONLY exception is the round-end flush at line 3371-3373: `for clientnum in pairs(tracker.aim_lock.active) do closeAimLock(clientnum, now) end`, where `now = gameTime()` (round end). So any lock still 'active' when sampling stops (pause/intermission/last tick) is stamped end_time = round-end, stretching its duration from one observation up to tens of seconds. The 2026-06-11 probe comment at lines 1186-1190 ('duration 31s with samples=2') shows this class of bug was known and only the in-loop gap path (1192-1196) was patched — the flush path was missed. Live DB (proximity_aim_lock, 3921 rows) confirms it: rows with samples=1 and duration_ms=28800/25600, samples=2 and duration_ms=42800. SQL: 54 rows where duration_ms > samples*400+800 carry 795,250 ms = 20.4% of total SUM(duration_ms). The endpoint /api/proximity/aim-lock ranks the leaderboard by `total_lock_ms = SUM(duration_ms)` and shows it as the headline 'Lock time' column (proximity_teamplay.py:185, proximity.js renderAimLock), so the primary ranking metric is ~20% phantom time and avg_lock_ms is likewise skewed.

**Zakaj (RCA):** The 'no fabricated numbers' core: the headline leaderboard metric (total lock time) and avg lock ms are materially wrong (~20% inflated) and can reorder the ranking, because a single 400 ms observation can be credited as 28 s of 'crosshair-on-enemy' time.

**Predlog popravka:** In the round-end flush (line 3372) close at the last confirmed sample like every other path: `local l = tracker.aim_lock.active[clientnum]; closeAimLock(clientnum, (l and l.last_seen) or now)`. Optionally add a sanity cap in closeAimLock (e.g. clamp duration to samples*interval_ms + interval_ms) as defense in depth. After deploy, backfill/refresh existing rows or note that pre-fix data over-counts.

**Verifikacija (skeptik, conf=high):** Could not refute. Tried: (1) checking whether another close path already neutralizes the flush — no, the round-end flush at proximity_tracker.lua:3371-3373 is the unique path passing `now` instead of `last_seen`; the 2026-06-11 gap fix (lines 1186-1196) and the stale sweep (1234) all use last_seen. (2) Checking whether the duration formula or a cap clamps it — closeAimLock() line 1117 is a raw `end_time - lock.start_time` with only a min_duration_ms floor (1118), no upper clamp. (3) Checking whether the endpoint avoids ranking by the inflated sum — it does NOT: proximity_teamplay.py:183/190 selects SUM(duration_ms) AS total_lock_ms and ORDER BY total_lock_ms DESC, the headline column. (4) DB sanity: the reviewer's exact figures reproduce (54 phantom rows, 795,250 ms = 20.4% of 3,892,725 total; samples=1/duration_ms=28800 row exists). The feature is live (commit 'chore(lua): activate v7 aim_lock capture flag' + endpoint shipped), 3921 rows present.

_Ground-truth preverjeno:_ Read proximity_tracker.lua:1107-1236 (all closeAimLock call sites) and 3340-3399 (flush). Confirmed line 3372 `closeAimLock(clientnum, now)` with now=gameTime() at 3370, vs every other site using `lock.last_seen or now`. Read proximity_teamplay.py:155-208 confirming ORDER BY total_lock_ms and avg_lock_ms exposure. Ran mcp__db__query: total=3892725ms, phantom(>samples*400+800)=795250ms across 54 rows = 20.4%; extreme rows incl samples=1→28800ms, samples=2→42800ms. Rank-impact query: real-player top-5 unaffected (corrected==tot), but OMNIBOT rows drop several ranks and human ranks 6/7/8 (DB00AA45, EDBB5DA9, 7B84BE88) shift up by 1 when corrected — so leaderboard does reorder, though milder for humans than headline 20% suggests. Not present in WHOLE_CODEBASE_AUDIT_2026-06-15.md (new finding).

---

### W1-02 · 🟡 MEDIUM · Stopwatch pairing mixes UTC-epoch (round_start_unix) with host-local-naive parse of CET filenames — mispairs mixed-source sessions on a non-CET host

- **Področje:** Data integrity (filler maps, match_id backfill, rounds.is_valid, round linking)
- **Datoteka:** `/home/samba/share/slomix_discord/bot/core/stopwatch_pairing.py:158-169 (_parse_dt_unix), 141-155 (_sort_key)`
- **Dimenzija:** correctness · **Effort:** small

**Dokaz:** round_start_unix is an absolute UTC epoch (verified: round id at round_date=2026-02-11 round_time=212900 has round_start_unix=1770841218 = 20:20:18 UTC, i.e. 21:29 CET file time minus the +1h winter offset). _parse_dt_unix() builds the fallback timeline via datetime.strptime(date+time).timestamp(), which interprets the naive CET wall-clock string in the HOST's local tz. _sort_key() places both kinds of round in the SAME sort group (group 0) on this single axis. They only agree when host tz == game-server tz (CET). On a UTC host the parsed value is shifted +1h(winter)/+2h(summer) relative to round_start_unix. I simulated session 88 (a real mixed session) on a UTC host: the parsed-only R2 rounds sort ~1h late, so the chronological R1->R2 walk pairs etl_adlernest R1 with the wrong R2 and orphans most maps. DB confirms 4 real mixed-source sessions exist (gaming_session_id 88,89,90,96: each has both round_start_unix IS NULL and IS NOT NULL R1/R2 rows; 1154 of 1797 play-rounds lack round_start_unix). The module docstring/_gap_seconds claim 'consistent within a session — absolute offset is irrelevant', which is false once unix and parsed rounds interleave. The codebase itself disagrees on the host tz: round_linker.py:257 says 'CET game server + UTC prod (PR #216)', while ultimate_bot.py:1737 says 'Both machines are CET — do NOT change to utcfromtimestamp()'. The only runtime caller is scripts/backfill_match_id_stopwatch.py (pair_rounds at line 143), which then rewrites rounds.match_id AND lua_round_teams.match_id; running it on a UTC host would silently mis-key these 4 sessions while presenting itself as 'deterministic'.

**Zakaj (RCA):** Core philosophy is 'no fabricated numbers'; a host-tz-dependent pairing silently produces wrong R1<->R2 match_id groupings (and re-keys lua_round_teams) for 4 known sessions, presented as authoritative/deterministic. Bounded scope and the dev host being CET keep it from being high.

**Predlog popravka:** Make the fallback parse timezone-explicit instead of host-dependent so it lands on the same UTC-epoch axis as round_start_unix: parse the filename wall-clock in the game-server zone, e.g. datetime.strptime(...).replace(tzinfo=ZoneInfo('Europe/Berlin')).timestamp() (or convert round_start_unix to the same naive-local basis for both). Then drop the inaccurate 'absolute offset is irrelevant' comment. Add a unit test that feeds a mixed unix/no-unix session and asserts identical pairing under TZ=UTC and TZ=Europe/Berlin (e.g. via a tz-injectable parse). Also reconcile the contradictory tz comments in round_linker.py:257 vs ultimate_bot.py:1737.

**Verifikacija (skeptik, conf=high):** Could not refute. I reproduced the exact failure on real DB data. _sort_key (stopwatch_pairing.py:150-154) mixes round_start_unix (true UTC epoch) and _parse_dt_unix (naive strptime().timestamp(), host-local) in the same group-0 axis. Running pair_rounds on real session 88 (16 rounds: 6 without unix, 10 with) gives 8/8 complete pairs under TZ=Europe/Berlin but only 1 complete + 7 abandoned_r1 + 7 orphan_r2 under TZ=UTC — proving the pairing is host-tz-dependent for mixed-source sessions. The docstring claim 'absolute offset is irrelevant' (line 160) is false once unix and parsed rounds interleave. The one mitigation (dry-run by default + --i-have-a-backup gate in backfill_match_id_stopwatch.py) reduces blast radius but does not neutralize the bug: dry-run on a UTC host shows the *broken* pairing as authoritative, and --apply rewrites rounds.match_id + lua_round_teams.match_id (lines 229-245).

_Ground-truth preverjeno:_ Inspected: (1) stopwatch_pairing.py:141-169 full logic; (2) DB query confirming 4 mixed sessions exist (88,89,90,96); (3) DB query of all 16 session-88 rounds confirming round_start_unix is UTC epoch (9818: 212900 CET -> 1770841218 ~20:20 UTC); (4) Python simulation of pair_rounds on real session-88 data under TZ=Europe/Berlin (8 complete) vs TZ=UTC (1 complete, 14 orphans) — bug reproduced; (5) the contradictory tz comments at round_linker.py:257 ('UTC prod, PR #216') and ultimate_bot.py:1737 ('Both machines are CET'); (6) the sole caller scripts/backfill_match_id_stopwatch.py:142-245 which rewrites rounds.match_id and lua_round_teams.match_id; (7) confirmed dev host is Europe/Ljubljana (CEST), so the bug is dormant here but live on the UTC prod the code's own comment describes.

---

### W1-03 · 🟡 MEDIUM · Per-player baseline includes the session being narrated (and newer ones) — delta vs "your usual" is wrong

- **Področje:** S1–S2 Jutro/Račun (digest, on-this-day, baseline, auth)
- **Datoteka:** `website/backend/services/storytelling/narrative.py:398-401 (root cause spans website/backend/services/storytelling/baseline.py:22-33)`
- **Dimenzija:** correctness · **Effort:** small

**Dokaz:** baseline.py:22-30 defines trailing_averages(..., before_session_id) and documents it precisely: "before_session_id: exclude that session and anything newer (so 'tonight' is compared against history, not against itself)." The only production caller, narrative.generate_player_narratives, calls it WITHOUT that arg: `trailing_averages(self.db, g[:8])` (narrative.py:399). trailing_averages then takes the 10 most-recent sessions by `gaming_session_id DESC` (baseline.py:46-51) with no upper bound. So: (a) for the latest session, tonight is averaged into its own baseline (~1/N=10% self-dilution, systematically understating the headline delta); (b) for any HISTORICAL session_date — and session_date is a free public query param (storytelling_router.py:68,88,118) — the baseline is drawn from sessions PLAYED AFTER the narrated one, i.e. "X above your usual" compares a 2026-03 game against the player's 2026-06 form. The computed kills `k.get("kills")` (narrative.py:423,499-501) is then formatted by format_with_baseline against this contaminated average.

**Zakaj (RCA):** The delta vs baseline is the headline value of the whole S1.3 baseline feature ('no raw number without its delta'); a baseline drawn from the same or future sessions makes that delta quantitatively wrong, directly violating the 'no fabricated numbers' rule.

**Predlog popravka:** Resolve the narrated session's gaming_session_id once (generate_narrative already does this at narrative.py:277-281 via `SELECT gaming_session_id FROM rounds WHERE round_date=$1`) and pass before_session_id=that_gsid into every trailing_averages call in generate_player_narratives so the baseline strictly precedes the narrated session.

**Verifikacija (skeptik, conf=high):** Could not refute. I tried three refutation angles, all failed: (1) No guard/override elsewhere — grep shows trailing_averages is called from exactly one site (narrative.py:399) and before_session_id is never passed anywhere in the repo, so the documented exclusion is dead. (2) The query genuinely lacks an upper bound (baseline.py:43-48, ORDER BY gaming_session_id DESC LIMIT n, with before_sql empty in this call path), so the narrated + newer sessions ARE included. (3) session_date is a free public param validated only for date range (storytelling_router.py:455 -> _parse_date 2020..today+1), so historical dates pull future-session baselines. The narrated session's kills (get_kis_leaderboard(sd)) are session-scoped while the baseline avg is contaminated, and the result feeds format_with_baseline.

_Ground-truth preverjeno:_ Read baseline.py (full): confirmed before_session_id docstring + unbounded DESC/LIMIT query. Read narrative.py:260-520: confirmed generate_player_narratives calls trailing_averages without before_session_id (line 399), and own_baseline is consumed only once via format_with_baseline in the solo-lurker branch (lines 499-501). Read storytelling_router.py (full): confirmed session_date is a public query param with only range validation, and generate_narrative resolves gaming_session_id via SELECT...FROM rounds WHERE round_date (the exact pattern the fix proposal cites, narrative.py:277-281). Grep confirmed trailing_averages/before_session_id have no other callers and before_session_id is never supplied in tests or code. The one overstatement in the finding: format_with_baseline affects a single narrative sentence in one branch, not the whole feature's headline.

---

### W1-04 · 🟡 MEDIUM · Season Iron Man / Most Improved awards do not exclude bots (OMNIBOT/[BOT]); MVP path does

- **Področje:** S3–S4 Večer/Tekma (parimutuel stave, izzivi, planning, season awards)
- **Datoteka:** `/home/samba/share/slomix_discord/website/backend/services/season_awards_service.py:68-133`
- **Dimenzija:** correctness · **Effort:** small

**Dokaz:** _compute_iron_man (lines 68-91) and _compute_most_improved (lines 94-133) aggregate player_comprehensive_stats joined to rounds with only `is_valid IS DISTINCT FROM FALSE` and `time_played_seconds > 0` — no bot filter. The MVP/KIS query in sessions_router.py:1831-1832 deliberately filters `killer_guid NOT LIKE 'OMNIBOT%' AND killer_name NOT LIKE '[BOT]%'`, proving the codebase knows bots pollute these aggregates, but the season-award computation omits the same guard. Live DB proof: 810 player_comprehensive_stats rows for OMNIBOT/[BOT] players sit in valid rounds with time_played>0, and re-running the exact most_improved DPM-delta query for 2026-Q2 ranks `[BOT]wajs` (OMNIBOT0b84bf80...) #4 (delta 28.4, just behind humans 46.1/45.8/36.0). A season with more bot-test activity would engrave a bot as 'Most Improved'/'Iron Man'. The MVP candidate pool (_session_player_pool, sessions_router.py:1764-1786) likewise includes bots, so a bot can also be a nominee.

**Zakaj (RCA):** Engraving a bot as a permanent season award directly violates the 'no fabricated numbers' core philosophy; awards are permanent (season_awards is keyed and meant to be HoF-style).

**Predlog popravka:** Add `AND pcs.player_guid NOT LIKE 'OMNIBOT%' AND pcs.player_name NOT LIKE '[BOT]%'` (matching the MVP/KIS convention) to the WHERE clauses of _compute_iron_man and _compute_most_improved in season_awards_service.py, and to _session_player_pool so bots can't be MVP candidates. Consider a shared helper for the bot-exclusion predicate to avoid further drift.

**Verifikacija (skeptik, conf=high):** Could not refute. The cited lines lack any bot-exclusion predicate, while the same '[BOT]%'/'OMNIBOT%' guard appears 11x elsewhere in the backend (sessions_router.py, players_profile_router.py, rivalries_service.py), confirming an established convention the season-award path drifts from. The only inaccuracy is the framing that 'MVP path filters bots' — the actual MVP candidate pool (_session_player_pool) and _compute_mvp (session_mvp_votes) do NOT filter bots either; only the KIS-rank sub-query at sessions_router.py:1831-1832 does. The finding itself notes this, so the core claim stands.

_Ground-truth preverjeno:_ Read season_awards_service.py:1-223 (confirmed _compute_iron_man/_compute_most_improved/_session_player_pool have no bot filter). Read sessions_router.py:1755-1844 (KIS sub-query filters bots; candidate pool does not). grep -rn 'OMNIBOT%' website/backend = 11 hits across 3 files. DB: 810 bot PCS rows / 30 GUIDs sit in valid rounds (is_valid IS DISTINCT FROM FALSE) with time_played>0. Re-ran exact most_improved query for 2026-04-01..06-30: [BOT]wajs (OMNIBOT0b84bf80...) ranks #4 delta 28.4 vs humans 46.1/45.8/36.0 — near-miss, not winning. iron_man for same window: top is human 'vid' 20 sessions, no bot in top 8 (bots have 3 sessions each). All 810 bot rows are in rounds with is_bot_round=false, so the is_bot_round flag does NOT catch them — per-player GUID/name filter (the proposed fix) is the correct/only reliable guard.

---

### W1-05 · 🟡 MEDIUM · Parimutuel auto-settle maps session winning_team to team_a/team_b with no binding to the market's labels

- **Področje:** S3–S4 Večer/Tekma (parimutuel stave, izzivi, planning, season awards)
- **Datoteka:** `/home/samba/share/slomix_discord/website/backend/routers/bets_router.py:272-283`
- **Dimenzija:** correctness · **Effort:** medium

**Dokaz:** settle_market resolves an empty outcome from `session_results.winning_team` as `team_a if winning_team==1 else team_b` (lines 280-281). session_results.winning_team is the persistent-team index (schema comment line 3992: '1 = Team 1 won, 2 = Team 2 won, 0 = draw'), computed by bot/services/stopwatch_scoring_service.py from team_1_guids/team_2_guids. The parimutuel_markets row stores only free-text `team_a_label`/`team_b_label` (set by the admin in open_market, lines 238-240) and NO roster/team-id linking team_a to session Team 1. So auto-settle silently assumes the admin happened to label team_a == the scoring service's Team 1. If the labels were entered in the other order, every payout in settle (lines 300-336) goes to the wrong side with no warning. Draws (winning_team==0) fall through and force a manual outcome (acceptable), but the 1/2 mismatch is undetectable.

**Zakaj (RCA):** Silently paying the wrong winners is a data-correctness/trust bug even with valueless points; the Oracle season award is derived from these net winnings, so a mis-settle also corrupts a permanent award.

**Predlog popravka:** Bind the market to the roster: store team_a_guids/team_b_guids (or the resolved team index) when opening the market, then resolve the outcome by intersecting session_results.team_1_guids/team_2_guids with the stored rosters instead of assuming positional 1->a/2->b. Until then, drop the auto-resolution (or require the admin to confirm an explicit outcome) so a wrong-side payout can't happen implicitly.

**Verifikacija (skeptik, conf=high):** Tried to refute by looking for (a) a roster/team-id binding on the market, (b) any label-to-name matching in settle, and (c) a deterministic admin-predictable definition of session 'Team 1'. All three failed. open_market (bets_router.py:231-241) stores only free-text team_a_label/team_b_label; settle_market (272-283) maps winning_team positionally (1->team_a, 2->team_b) with no name/roster comparison. In stopwatch_scoring_service.py the 'Team 1'/'Team 2' identity is derived non-deterministically: team_names_list comes from a DISTINCT query with no ORDER BY (288-302) and team_mapping flips on an arbitrary R1 sample player's side (358-370). Since session_results doesn't exist at market-open time and the positional assignment is post-hoc/unstable, even a careful admin cannot pre-align labels. The only real mitigations are the optional explicit `outcome` override and valueless points — they reduce but don't eliminate the silent wrong-side payout on the auto-resolve path. Bug is genuine, not neutralized by any guard.

_Ground-truth preverjeno:_ Read bets_router.py lines 1-345 (open_market, place_bet, settle_market). Read schema_postgresql.sql 8714-8744 (parimutuel_markets has no roster columns; only team_a_label/team_b_label) and 3940-3992 (session_results has team_1_guids/team_2_guids/team_1_name/team_2_name; winning_team comment '1=Team 1, 2=Team 2, 0=draw'). Read stopwatch_scoring_service.py 200-419 confirming team_1/team_2 ordering is derived from session_teams (no ORDER BY) + sample-player side flip, i.e. not stable/admin-predictable. Grepped frontend (React src + legacy js) — no client code binds team_a to a roster either. Checked docs/research/WHOLE_CODEBASE_AUDIT_2026-06-15.md: only parimutuel atomicity/payout was previously reviewed (line 35), not this label-binding correctness gap, so this is net-new depth.

---

### W1-07 · 🟡 MEDIUM · bait_score mixes full-coverage lifetime deaths with proximity-only avenged count → systematically deflated, meaningless number presented as real

- **Področje:** S5–S7 Identiteta/Spomin/Live (profil v2, wrapped, record-book, Tonight)
- **Datoteka:** `website/backend/routers/players_profile_router.py:248-275`
- **Dimenzija:** correctness · **Effort:** medium

**Dokaz:** _fetch_advanced computes `untraded = max(0, lifetime_deaths - avenged)` (line 273). `lifetime_deaths` comes from _fetch_lifetime which sums deaths over ALL valid rounds (1797 rounds), but `avenged` and `trades_made` come from proximity_lua_trade_kill, which exists for only ~29% of rounds (verified: 521 of 1797 rounds have any trade rows). So the denominator (trades + untraded) is dominated by deaths from rounds that have NO trade tracking at all and therefore could never be 'avenged'. Verified on the top player (guid 5D989160): lifetime_deaths=13732, avenged=487, trades_made=459 → bait_score = 459/(459+13245)*100 = 3.3%. Every player collapses to ~trades/deaths, a value that varies with each player's proximity-coverage fraction rather than with their actual trade involvement. bait_score returns available:True with this misleading percentage, violating the project's 'no fabricated numbers' rule. The metric docstring (player_profile_metrics.py:85-109) even codifies the wrong intent ('total_deaths - deaths_avenged_for_player').

**Zakaj (RCA):** Profile 'advanced' teamplay metric shows a real-looking percentage that is wrong for every player and biased by data coverage, not skill.

**Predlog popravka:** Count deaths over the SAME round set that has trade-kill coverage (e.g., restrict lifetime_deaths to rounds present in proximity_lua_trade_kill / proximity-covered rounds for this player), so numerator and denominator share one population. Alternatively derive untraded_deaths directly from proximity death rows (e.g., proximity_kill_outcome victim rows) minus avenged, all within proximity-covered rounds. Mark the section approximate and surface the coverage % like _fetch_combat_timing does.

**Verifikacija (skeptik, conf=high):** I tried to refute this and could not. The mechanism is objectively proven in code and data. In players_profile_router.py:248-275, _fetch_advanced receives `lifetime_deaths` from _fetch_lifetime (line 140-185), which sums p.deaths over ALL valid rounds (player_comprehensive_stats JOIN rounds WHERE r.is_valid, no proximity restriction). But `trades_made` (line 262-263) and `avenged` (line 266-268) come exclusively from proximity_lua_trade_kill. Then untraded = max(0, lifetime_deaths - avenged) (line 273) and bait = bait_score(trades_made, untraded). Since bait_score = trades/(trades+untraded)*100 (player_profile_metrics.py:85-108), the denominator is dominated by deaths from rounds that have no trade tracking at all and thus can never be 'avenged'. This is a genuine apples-to-oranges population mismatch: a ~20%-coverage numerator divided by a near-full-coverage denominator. The only debatable point is severity, not validity — I could not find any guard, disclaimer, or coverage normalization neutralizing it. The bait_score returns available:True whenever denom>0 (almost always), and it is surfaced live in the legacy UI (website/js/player-profile.js:761,794) as a 'Bait Score' percentage stat cell with NO coverage caveat, so it is presented to users as a real number.

_Ground-truth preverjeno:_ Read players_profile_router.py:140-185 (_fetch_lifetime — confirmed lifetime deaths span all valid rounds, no proximity gate) and :248-275 (_fetch_advanced — confirmed trades/avenged are proximity-only). Read player_profile_metrics.py:83-109 (bait_score formula + docstring codifying 'total_deaths − deaths_avenged_for_player', i.e. the lifetime-deaths intent). Confirmed UI surfacing in website/js/player-profile.js:761 and :794 ('Bait Score' cell, no disclaimer). DB sanity checks via mcp__db__query: (1) coverage — only 521 of 2655 valid stat-bearing rounds (~20%) have any proximity_lua_trade_kill rows; (2) reproduced the cited top player (guid 5D989160): lifetime_deaths=13718, trades_made=459, avenged=487 → bait = 459/(459+13231)*100 = 3.4%, confirming the score collapses to ~trades/lifetime_deaths and is dominated by untracked deaths. Checked docs/research/WHOLE_CODEBASE_AUDIT_2026-06-15.md — bait/trade_kill/untraded NOT mentioned, so this is not a duplicate of the prior scanner audit.

---

### W1-08 · 🟡 MEDIUM · Tonight live hub mis-scores double-fullhold maps as a win instead of a 1-1 draw (diverges from canonical BOX scorer)

- **Področje:** S5–S7 Identiteta/Spomin/Live (profil v2, wrapped, record-book, Tonight)
- **Datoteka:** `website/backend/routers/players_router.py:375-388`
- **Dimenzija:** correctness · **Effort:** small

**Dokaz:** get_tonight determines the map winner with `if r2 and r2["winner"]: winner = r2["winner"]` (lines 376-381) and only treats it as a draw when R2 has no round winner (`elif r2 and not r2["winner"]`, line 383). It never inspects whether the rounds were fullholds, even though it already computes per-round `duration`. The canonical stopwatch scorers disagree: box_scoring_service.py score_map (lines 94-99) scores `r1.is_fullhold and r2.is_fullhold` as winner='draw' 1-1, and stopwatch_scoring_service.py (lines 891-901) explicitly handles 'Double fullhold: 1-1 draw'. In a double-fullhold map each defender wins their own round, so r2 has a winner_team and Tonight awards the whole map (2 pts, a_maps/b_maps++) to the R2 defender instead of scoring a draw. This makes the live a_maps/b_maps tally and per-map winner pills wrong for defense-heavy maps.

**Zakaj (RCA):** Live 'Tonight' score is the headline of the LIVE sprint; a double-fullhold map silently flips a draw into a 2-0 map for one team.

**Predlog popravka:** Mirror BOX score_map: compute is_fullhold per round (R1/R2 duration vs map time limit, or carry a fullhold flag from lua), and when both R1 and R2 are fullholds emit winner='draw' with no map point to either side. Reuse BOXScoringService.get_expected_alpha_side/score_map instead of the ad-hoc 'R2 winner takes the map' branch so Tonight stays consistent with session-detail scoring.

**Verifikacija (skeptik, conf=high):** Could not refute. The Tonight scorer (players_router.py:376-381) awards 2 points + a_maps/b_maps++ to the R2 round winner with no fullhold check, while the canonical BOXScoringService.score_map (box_scoring_service.py:94-99) scores r1.is_fullhold and r2.is_fullhold as a 1-1 draw. The Tonight SQL doesn't even fetch round_outcome, so it cannot detect fullholds. I confirmed the bug fires on real, valid (is_valid != FALSE) data: many double-fullhold map pairs have both R1 and R2 lua_round_teams.winner_team set non-zero (e.g. session 119 r1_id=10640 R1 winner=2/R2 winner=1, session 121 r1_id=10670, session 117 r1_id=10583, plus many sw_goldrush_te/supply maps), so r2['winner'] is truthy and Tonight mis-awards a 2-0 map. The only divergence is the double-fullhold case; I verified the other three round-outcome combinations resolve identically in both scorers, so the finding is precisely scoped.

_Ground-truth preverjeno:_ Read players_router.py get_tonight (lines 267-388): scoring branch and the SQL that omits round_outcome. Read box_scoring_service.py score_map (73-114) and _fetch_session_rounds (204-268): confirmed fullhold derived from rounds.round_outcome and double-fullhold => draw. Ran DB queries joining rounds+lua_round_teams: confirmed real valid double-fullhold maps with both rounds' winner_team non-zero across sessions 107-128. Grepped prior audit (WHOLE_CODEBASE_AUDIT_2026-06-15.md) for fullhold/tonight — not previously reported.

---

### W1-09 · 🟢 LOW · Promotion job claimed to 'running' is never recovered if the bot restarts mid-dispatch (no stale-job reaper)

- **Področje:** Bot reliability (advisory-lock, webhook queue, stats-ready, watchdog)
- **Datoteka:** `bot/cogs/availability_mixins/scheduler_mixin.py:233-395`
- **Dimenzija:** correctness · **Effort:** small
- **Zunanja ref:** Not in WHOLE_CODEBASE_AUDIT_2026-06-15.md

**Dokaz:** In `_process_promotion_jobs` the work is selected with `WHERE status = 'pending' AND run_at <= $1` (lines 235-245), then atomically claimed with `UPDATE ... SET status='running' ... WHERE id=$1 AND status='pending' RETURNING attempts,max_attempts` (lines 254-265). The job is only moved out of 'running' by the in-process success/skip updates (lines 312-373) or the `except` block (lines 374-386). If the process dies AFTER the claim commits but BEFORE one of those terminal updates (e.g. a crash, or the documented daily 20:00 systemd restart landing during the 20:45/21:00 Discord-DM dispatch loop in `_dispatch_promotion_notification`), the row is left at status='running'. The selector only ever picks `status='pending'`, and `grep` confirms no reaper/requeue resets stale 'running' rows anywhere in bot/cogs/availability_mixins/ — so the session reminder/start notification is silently never sent and never retried. The advisory_lock refactor (a928dab) wraps this body but did not introduce or address the gap; it is pre-existing.

**Zakaj (RCA):** A missed 21:00 session-start promotion notification with no retry undermines the availability/promotion feature; impact is bounded (one community, infrequent campaigns) but the failure is silent and permanent for that campaign.

**Predlog popravka:** Add a stale-claim reaper at the top of `_process_promotion_jobs` (inside the advisory lock so it stays single-flight): `UPDATE availability_promotion_jobs SET status='pending', last_error='requeued (stale running)' WHERE status='running' AND updated_at < NOW() - INTERVAL '10 minutes' AND COALESCE(attempts,0) < COALESCE(max_attempts, <default>)` (rows past max_attempts → 'failed'). This lets a crashed-mid-dispatch job be retried on the next tick, with dispatch idempotency already provided by `notifier` event_key dedup.

**Verifikacija (skeptik, conf=high):** I tried to refute this on three fronts and failed on all three: (1) a recovery/reaper elsewhere, (2) a surrounding transaction that would roll back the claim on crash, and (3) job re-creation that would re-schedule a stuck campaign. None exist. The mechanism holds. The only nitpick is the finding's mention of the 'documented daily 20:00 systemd restart landing during the 20:45/21:00 dispatch' — the daily restart at 20:00 is actually BEFORE the dispatch window, so that exact scenario is not the trigger; but any crash/OOM/deploy during the few-second DM-dispatch loop is, so the core defect stands regardless.

_Ground-truth preverjeno:_ Read scheduler_mixin.py lines 233-395: the SELECT (line 239) filters `status='pending'` only; the claim UPDATE (lines 256-262) sets `status='running'` guarded by `status='pending'`; terminal updates to sent/skipped/failed/pending all live inside the try/except body. grep across bot/, website/, scripts/ for `availability_promotion_jobs` UPDATEs and for `stale|reaper|requeue|orphan|'running'` found NO code that ever resets a stale 'running' row back to 'pending' — only external_channels_mixin references 'running' in read-only status-IN filters. Confirmed commit durability in database_adapter.py: `_process_promotion_jobs` does not use `transaction()`; each `execute`/`fetch_one` runs via `connection()` (pool.acquire) under asyncpg implicit per-statement auto-commit, so the claim commits immediately and survives a subsequent process death before the terminal update. Index `idx_promotion_jobs_due ON (status, run_at)` confirms the pending-only access path. Not present in WHOLE_CODEBASE_AUDIT_2026-06-15.md.

---

### W1-11 · 🟢 LOW · avg_err_deg / avg_dist are an unweighted mean-of-means across lock windows

- **Področje:** Proximity v7 (aim-lock + teamplay endpointi + Lua flag)
- **Datoteka:** `website/backend/routers/proximity_teamplay.py:184-185`
- **Dimenzija:** correctness · **Effort:** trivial

**Dokaz:** The endpoint computes `ROUND(AVG(avg_err_deg)...)` and `ROUND(AVG(avg_dist)...)` over rows of proximity_aim_lock. Each row's avg_err_deg/avg_dist is itself a per-window average over `samples` (Lua closeAimLock lines 1129-1130: err_sum/n). Averaging those per-window averages gives a 1-sample window the same weight as a 14-sample window. Verified against live DB: for top players mean-of-means vs SUM(avg_err_deg*samples)/SUM(samples) differs only ~0.03-0.2 deg (vid 2.758 vs 2.725), so impact is small at current sample sizes — but it is presented as the headline 'Avg err' tracking-tightness metric.

**Zakaj (RCA):** Statistically incorrect aggregation presented as a precise per-player figure; magnitude is small today but grows if window sample counts diverge.

**Predlog popravka:** Use sample-weighted aggregation: `SUM(avg_err_deg*samples)/NULLIF(SUM(samples),0)` and likewise for avg_dist. The proximity_aim_lock.samples column is already stored for exactly this.

**Verifikacija (skeptik, conf=high):** Could not refute. The cited code at website/backend/routers/proximity_teamplay.py:184-185 does compute ROUND(AVG(avg_err_deg)) and ROUND(AVG(avg_dist)) grouped by guid, with no sample weighting. There is no guard or correction elsewhere — the SELECT is the final aggregation returned to the client as avg_err_deg/avg_dist. The mean-of-means is statistically incorrect for a tracking-tightness metric; the correct aggregate is sample-weighted SUM(x*samples)/SUM(samples). The only thing arguing against it is magnitude, not correctness.

_Ground-truth preverjeno:_ Read proximity_teamplay.py lines 140-219: confirmed the aim-lock leaderboard query uses AVG(avg_err_deg) and AVG(avg_dist) over rows grouped by guid (lines 184-185). Read tools/schema_postgresql.sql lines 2365-2390: confirmed proximity_aim_lock has avg_err_deg (real, per-window avg), avg_dist (integer, per-window avg), and samples (integer) columns — so each row already is a per-window average and the samples weight needed for a correct aggregate is stored but unused. The fix proposal (SUM(avg_err_deg*samples)/NULLIF(SUM(samples),0)) is valid against this schema. Finding self-reports tiny live-DB delta (~0.03-0.2 deg), consistent with low magnitude.

---

### W1-12 · 🟢 LOW · Aim-lock leaderboard surfaces omni-bot players and orphan (unlinked) rounds as real human leaders

- **Področje:** Proximity v7 (aim-lock + teamplay endpointi + Lua flag)
- **Datoteka:** `website/backend/routers/proximity_teamplay.py:176-201`
- **Dimenzija:** correctness · **Effort:** small

**Dokaz:** The query selects from proximity_aim_lock with no exclusion of bot players (OMNIBOT* guids / '[BOT]' names) and no round-validity join. Live DB shows the leaderboard's top entries include OMNIBOT0400... '[BOT]endekk' (72 locks) and '[BOT]vid' (92 locks), and the largest single durations all belong to '[BOT]wajs/lagger/carniee/vid'. All current proximity_aim_lock rounds are flagged rounds.is_bot_round=false despite being omni-bot test sessions (the known is_bot_round detection gap), and ~396 locks have round_id IS NULL (orphan/unlinked rounds) yet are still counted because the scope filter is date-based only. Net: the v7 'Aim Lock' panel's only real-world data so far is bot-test-heavy and is presented as a genuine player leaderboard. (Bot inclusion is systemic across proximity routers — none filter OMNIBOT — so this is a surfacing of a pre-existing gap, not unique to this endpoint.)

**Zakaj (RCA):** Presenting bot/test rows as a real leaderboard violates the 'no fabricated numbers' philosophy; users will see [BOT] names topping the v7 panel.

**Predlog popravka:** Exclude bot actors (e.g. `WHERE guid NOT LIKE 'OMNIBOT%'`, or join rounds and require is_bot_round = false once that flag is fixed) consistently across proximity leaderboards; consider requiring round_id IS NOT NULL (or is_valid) to drop orphan captures. Independently, fix the upstream is_bot_round detection so omni-bot rounds are flagged.

**Verifikacija (skeptik, conf=high):** Could not refute the core claim. Confirmed at proximity_teamplay.py:178-194 that the aim-lock leaderboard query has no OMNIBOT/[BOT] exclusion and no rounds.is_bot_round / round_id validity join; the only filtering comes from _build_proximity_where_clause (proximity_helpers.py:136-202) which is date/map/round/guid only. No other proximity router filters OMNIBOT either. However, the finding's framing is overstated: the live leaderboard top-5 are all real humans (^pvid 519600ms, wiseBoy 423125ms, .olz 419600ms) with 4-5x any bot total; bots appear interspersed at ranks ~6 ([BOT]endekk) and ~8 ([BOT]vid), not 'topping' the panel. 'Largest single durations all belong to bots' and 'only data so far is bot-test-heavy' are false against ground truth — bots are ~10% of locks (377/3921) and do not lead.

_Ground-truth preverjeno:_ Read proximity_teamplay.py:155-215 (aim-lock endpoint) and proximity_helpers.py:136-202 (where-clause builder) — no bot or round-validity filter present. grep confirmed no OMNIBOT filter in any proximity_*.py router. Live DB (mcp__db__query) on proximity_aim_lock: total 3921 locks, 377 OMNIBOT% locks, 396 round_id IS NULL; leaderboard ordering by SUM(duration_ms) shows OMNIBOT0400 ([BOT]endekk, 228800ms) and OMNIBOT0300 ([BOT]vid, 214000ms) within top 20, but real humans occupy ranks 1-5. Finding NOT present in prior audit doc WHOLE_CODEBASE_AUDIT_2026-06-15.md.

---

### W1-14 · 🟢 LOW · Baseline granularity mismatch: session-DATE kill totals compared against a per-gaming_session average

- **Področje:** S1–S2 Jutro/Račun (digest, on-this-day, baseline, auth)
- **Datoteka:** `website/backend/services/storytelling/narrative.py:350-361, 499-501`
- **Dimenzija:** correctness · **Effort:** small

**Dokaz:** The 'tonight' value comes from get_kis_leaderboard(sd) keyed on session_DATE (narrative.py:350), so k.get('kills') is the sum over the whole calendar date. trailing_averages groups strictly `GROUP BY r.gaming_session_id` (baseline.py:47), i.e. its average is per gaming session. When a single date contains more than one gaming_session_id, the two scopes diverge. Live DB confirms this happens: session_results shows dates 2026-06-15 and 2026-05-26 each map to 2 distinct gaming_session_id values. On such dates 'tonight' sums two sessions' kills while 'your usual' is a single-session average, inflating the delta.

**Zakaj (RCA):** On multi-session days the 'above your usual' figure is overstated, mildly misrepresenting the player's night against the no-fabricated-numbers philosophy.

**Predlog popravka:** Compare like-for-like: either compute the 'tonight' kills per gaming_session_id (matching the baseline grain) or have trailing_averages aggregate per session_date when the narrative scope is a date. Simplest: scope both to gaming_session_id.

**Verifikacija (skeptik, conf=medium):** Could not refute. The grain mismatch is real: get_kis_leaderboard (narrative.py:350 -> archetypes.py:36) sums kills over the whole calendar date (WHERE session_date=$1), while trailing_averages (baseline.py:46) returns a per-gaming_session average (GROUP BY r.gaming_session_id). format_with_baseline at narrative.py:499-501 compares the two directly. No guard normalizes the grain. The only thing that softens it is rarity + a narrow code path.

_Ground-truth preverjeno:_ Read narrative.py:331-505 (generate_player_narratives), archetypes.py:20-67 (get_kis_leaderboard uses WHERE session_date=$1, kills=COUNT(*)), baseline.py full (trailing_averages GROUP BY r.gaming_session_id, called without before_session_id so it includes tonight). DB query confirmed 8 multi-session dates exist (e.g. 2026-03-25 has 4 gaming_session_ids; 2026-06-21/06-16/06-11/05-27 have 2). The reviewer's exact dates differ (they read session_results, I read rounds.round_date) but the multi-session phenomenon is confirmed. Not present in WHOLE_CODEBASE_AUDIT_2026-06-15.md.

---

### W1-15 · 🟢 LOW · On-This-Day day score conflates multiple gaming sessions / different rosters on the same date

- **Področje:** S1–S2 Jutro/Račun (digest, on-this-day, baseline, auth)
- **Datoteka:** `bot/services/on_this_day_service.py:46-69`
- **Dimenzija:** correctness · **Effort:** small

**Dokaz:** _fetch_day_history groups session_results by `CAST(session_date AS DATE)` and reports MAX(team_1_name)/MAX(team_2_name) with SUM(winning_team=1)/SUM(winning_team=2) (lines 50-60). session_results is one row PER MAP per gaming session (schema: map_name NOT NULL, gaming_session_id column), and winning_team=1/2 is relative to that row's team_1_guids/team_2_guids — which differ across gaming sessions. When a date has >1 gaming session (confirmed for 2026-06-15 and 2026-05-26 in the live DB) the throwback line 'TeamA n–m TeamB' blends distinct teams/sides and MAX() picks an arbitrary name, so the displayed historical score can be wrong. Also note the query reads the nullable singular columns team_1_name/team_2_name (the NOT NULL plural team_1_names/team_2_names exist too); older rows with NULL singulars silently fall back to the 'N maps played' branch (lines 113-116).

**Zakaj (RCA):** Surfaced as a factual historical result ('on this day, X beat Y n–m'); on multi-session days it can present a fabricated score, contrary to the archive-as-memory intent.

**Predlog popravka:** Group by gaming_session_id (not date) and render one line per gaming session, or restrict to dates with a single gaming_session_id; pick team names consistently with the winning side rather than MAX().

**Verifikacija (skeptik, conf=medium):** The core mechanism is real: `_fetch_day_history` (bot/services/on_this_day_service.py:50-60) groups `session_results` by `CAST(session_date AS DATE)` and SUMs `winning_team=1/2` across all rows for that date. Confirmed via DB that two calendar dates have >1 gaming_session_id (text dates 2026-06-16 → sessions 125+126, and 2026-05-27). For such a day the throwback line blends two distinct gaming sessions into one count, e.g. 'Team A 1–1 Team B', which merges two separate matchups whose 'team_1' rosters differ — a genuine (if minor) misrepresentation in an archive feature.\n\nHOWEVER, most of the finding's supporting evidence is wrong or moot against actual data, which sharply limits the impact:\n1. 'one row PER MAP per gaming session' is FALSE — all 33 rows have map_name='ALL'; session_results is one aggregated row per gaming_session (not per map). So a multi-session day produces a tiny N (2), not an inflated map-level tally.\n2. 'MAX() picks an arbitrary name' is MOOT — there is exactly one distinct team_1_name ('Team A') and one team_2_name ('Team B') across all 33 rows; MAX always returns the same generic placeholder, and team_1_names/team_2_names are '[]'. No real roster is ever misattributed.\n3. 'older rows with NULL singulars silently fall back to N maps played' is unsubstantiated — 0 of 33 rows have NULL team_1_name/team_2_name, so that branch is never hit in practice.

_Ground-truth preverjeno:_ Read on_this_day_service.py fully (query at 50-64, render at 108-121). Read schema_postgresql.sql:3933-3964 — confirmed map_name NOT NULL, gaming_session_id nullable, team_1_name/team_2_name nullable singulars exist alongside NOT NULL plural team_1_names/team_2_names. Ran DB queries: (a) dates with >1 gaming_session_id exist (2 such dates); (b) ALL 33 rows have map_name='ALL' (refutes per-map premise); (c) 0 NULL singular team names, distinct team_1_name=1 ('Team A'), distinct team_2_name=1 ('Team B') (refutes MAX-arbitrary and NULL-fallback claims).

---

### W1-22 · 🟢 LOW · Tonight uses UTC date boundary (captured_at::date = CURRENT_DATE) which splits an evening session that runs past local midnight

- **Področje:** S5–S7 Identiteta/Spomin/Live (profil v2, wrapped, record-book, Tonight)
- **Datoteka:** `website/backend/routers/players_router.py:284`
- **Dimenzija:** correctness · **Effort:** small

**Dokaz:** get_tonight filters `WHERE l.captured_at::date = CURRENT_DATE`. captured_at is `timestamp with time zone` and the DB session timezone is Etc/UTC (verified: current_setting('TimeZone')='Etc/UTC'). The community plays CEST evenings; a session running past ~02:00 CEST crosses UTC midnight (00:00 UTC = 02:00 CEST), so the night's early maps fall on the previous UTC date and drop out of the 'maps'/score payload once CURRENT_DATE flips, even though the gather is one continuous evening. This is the same UTC-vs-local class of bug already fixed once in the round linker.

**Zakaj (RCA):** On long nights the live map list and team-map tally truncate mid-session, contradicting the at-a-glance 'what's happening tonight' purpose.

**Predlog popravka:** Anchor the Tonight window on the live gaming_session_id (group by r.gaming_session_id of the most recent active session) or on a local-time-adjusted day boundary / a rolling lookback window, rather than the UTC calendar date, so a session that crosses local midnight stays intact.

**Verifikacija (skeptik, conf=high):** Could not refute. The query at players_router.py:284 uses `WHERE l.captured_at::date = CURRENT_DATE` as the only temporal boundary; `last_gsid` (line 326) is captured but never used to widen the window. captured_at is timestamptz and the DB session TZ is Etc/UTC, so the cast resolves in UTC. The whole Tonight payload is derived solely from rows passing this filter, so there is no compensating guard.

_Ground-truth preverjeno:_ Verified TZ via mcp__db__query: current_setting('TimeZone')='Etc/UTC'. Verified lua_round_teams hour distribution: peak 19-23 UTC (=21:00-01:00 CEST), with 13 rows at UTC hour 0 (=02:00 CEST), confirming evenings can cross 00:00 UTC. Found gaming_session_ids whose lua rows span two distinct captured_at::date values. Read players_router.py:267-418 to confirm no gaming_session_id-based widening of the query. The 'round linker UTC vs local' fix referenced in the finding matches CLAUDE.md's documented bug fix, supporting the same-class claim.

---
