# Wave 1 — Performance & Cache (3 najdb)

> Vse najdbe adversarialno preverjene (prove-or-drop). Severity je po-verifikaciji prilagojena.

### W1-10 · 🟢 LOW · Weapon stats inserted one-row-per-await (N+1) instead of executemany within the player import loop

- **Področje:** Bot reliability (advisory-lock, webhook queue, stats-ready, watchdog)
- **Datoteka:** `/home/samba/share/slomix_discord/bot/services/stats_import_mixin.py:877-901`
- **Dimenzija:** performance · **Effort:** small
- **Zunanja ref:** Not covered in docs/research/WHOLE_CODEBASE_AUDIT_2026-06-15.md (grep for executemany/weapon/N+1 returned nothing).

**Dokaz:** In _insert_player_stats, weapon rows are written with a per-weapon `await self.db_adapter.execute(insert_sql, (...))` inside `for weapon_name, w in weapon_stats.items():` (lines 879-901), itself nested inside the per-player `async with self.db_adapter.transaction()`. The adapter already exposes `executemany` (database_adapter.py:348) used elsewhere, but it is not used here. For a typical round (~10-12 players, each ~6-10 weapons) this issues ~60-120 separate awaited DB round-trips per round file, in addition to one separate transaction()/connection-acquire per player (line 832). The static INSERT and the savepoint isolation are fully compatible with a single executemany call.

**Zakaj (RCA):** Import-path only and at ~30-50 player / handful-of-rounds-per-evening scale this is not a bottleneck, so severity is low; but it is a clear, real N+1 the performance lens explicitly flags, and the fix is a drop-in use of the adapter's existing executemany.

**Predlog popravka:** Build the weapon tuples into a list inside the savepoint and replace the per-weapon `execute` loop with one `await self.db_adapter.executemany(insert_sql, weapon_rows)` call. This preserves the existing savepoint atomicity (all-or-none weapons for the player) while collapsing dozens of round-trips into one. No behavioral change beyond fewer round-trips.

**Verifikacija (skeptik, conf=high):** Tried to refute on two fronts and both failed. (1) The N+1 is exactly as described: stats_import_mixin.py:879-901 awaits db_adapter.execute once per weapon inside the per-player transaction() savepoint. (2) I checked whether the proposed executemany fix would break the savepoint atomicity the surrounding comments rely on — it does not: executemany (database_adapter.py:348-356) acquires its connection via self.connection(), and connection() (lines 222-225) yields the active _active_tx_conn when one is set, so calling executemany while still inside the existing `async with transaction()` runs on the same connection within the savepoint, preserving all-or-none weapon semantics. So the fix is a valid drop-in and the finding stands.

_Ground-truth preverjeno:_ Read stats_import_mixin.py:820-914 (confirmed per-weapon execute loop inside transaction(), static INSERT SQL). Read database_adapter.py:220-361 confirming connection() reuses _active_tx_conn, transaction() does savepoint nesting, executemany() exists and reuses connection() (so it works inside an active tx). Noted executemany() skips _normalize_params (execute() applies it) — irrelevant for these int/float/str weapon tuples but a real difference. Not present in docs/research/WHOLE_CODEBASE_AUDIT_2026-06-15.md per the finding's grep claim; nothing contradicts that.

---

### W1-13 · 🟢 LOW · v7 import methods do row-by-row INSERTs instead of using the available executemany batch API

- **Področje:** Proximity v7 (aim-lock + teamplay endpointi + Lua flag)
- **Datoteka:** `proximity/parser/parser.py:2775-2865`
- **Dimenzija:** performance · **Effort:** small
- **Zunanja ref:** Not covered by docs/research/WHOLE_CODEBASE_AUDIT_2026-06-15.md (no batch-insert/N+1 parser mention found there)

**Dokaz:** The four newly-added v7 import methods (_import_aim_locks 2779, _import_spawn_selects 2803, _import_skill_snapshots 2825, _import_comm_events 2849) each `for ... in self.aim_locks:` and issue one `await self.db_adapter.execute(query, tuple(values))` per row (e.g. line 2797). The per-row helpers (_v7_base_columns_values, _append_round_link_columns, _append_canonical_guid_columns) are pure/cached (no per-row DB query — _table_has_column uses self._schema_cache, round-link context resolved once per file), so the column set is identical for every row in a given import. The adapter already exposes a true batching `executemany` (bot/core/database_adapter.py:348 -> asyncpg conn.executemany). Per the commit, one session emitted 1367 aim_lock rows for 11 rounds, i.e. ~1367 sequential INSERT round-trips on the import path for that one table alone (current table is 3921 rows).

**Zakaj (RCA):** Each row is a separate await/round-trip to Postgres in the async import path; with ON CONFLICT DO NOTHING and a stable column set the whole list could go through one executemany, cutting per-file import latency. This mirrors the legacy parser pattern (player_track imports far more rows the same way and works in production), so impact is modest and this is acceptable at current volume — but it is new code and the batch helper exists, so it is the one concrete efficiency gap in the v7 changes.

**Predlog popravka:** Within each v7 import method, build a single `columns` list once (the schema-cache lookups are deterministic per file) plus a `params_list` of value tuples across all rows, then call `await self.db_adapter.executemany(insert_sql, params_list)` once instead of looping with execute(). Keep the ON CONFLICT DO NOTHING clause. Optionally apply the same to the other proximity import loops if revisited.

**Verifikacija (skeptik, conf=high):** Tried to refute on three fronts and all failed. (1) Code: lines 2797/2819/2843/2865 do issue one execute() per row inside `for ... in self.<list>` loops — verified, not a misread. (2) Batch API exists: database_adapter.py:348 `executemany` wraps asyncpg conn.executemany — verified, so the alternative is genuinely available. (3) Feasibility: I checked whether the helpers do per-row DB work that would block batching — `_table_has_column` (parser.py:1029-1046) is backed by `self._schema_cache` so the schema lookups are pure after the first row, and `_append_round_link_columns`/`_append_canonical_guid_columns` only consult that cache plus already-resolved per-file metadata. So the column set is identical for every row and a single executemany is viable. No guard or batching elsewhere neutralizes the row-by-row pattern.

_Ground-truth preverjeno:_ Read parser.py:2760-2879 (all four v7 import methods + _v7_base_columns_values), confirmed per-row execute() calls and ON CONFLICT DO NOTHING clauses. Read database_adapter.py:330-362, confirmed executemany exists and is a true asyncpg batch. Grepped parser.py for the helper definitions and confirmed _schema_cache caching (lines 618, 1029-1046) making the helpers pure per file. The same row-by-row pattern is used by the older proximity imports (combat_engagement, player_track, kill_outcome, etc.) which run in production — consistent with the reviewer's note that impact is modest.

---

### W1-23 · 🟢 LOW · Tonight live hub endpoint (/api/stats/tonight) and /api/stats/hold-probability bypass the HTTP cache while the sibling /api/stats/live-session is cached

- **Področje:** S5–S7 Identiteta/Spomin/Live (profil v2, wrapped, record-book, Tonight)
- **Datoteka:** `website/backend/middleware/http_cache_middleware.py:31-51 (cacheable_prefixes) + 261-285 (_ttl_for_path)`
- **Dimenzija:** performance · **Effort:** trivial

**Dokaz:** cacheable_prefixes (http_cache_middleware.py:31-51) lists '/api/stats/live-session' (and gives it live_ttl=15s via _ttl_for_path:264/282) but does NOT list '/api/stats/tonight' or '/api/stats/hold-probability'. Any path not matching a prefix gets 'private, no-store' (dispatch line ~83), so the server returns nothing cacheable. The Tonight hub is the new S7 LIVE feature explicitly designed as a hot poll: tonight.js declares POLL_MS = 8000 and polls `${API_BASE}/stats/tonight` every 8s (tonight.js:11,29-32,106), AND the home page loads the same endpoint via loadHomeTonightCard (tonight.js:271-276). Each poll runs get_tonight (players_router.py:267) which fires 3 DB round-trips per call (main lua_round_teams scan at :284, _tonight_team_names session_teams query at :235, and _hold_prob_curve regex scan of rounds at :169). With no server-side cache there is zero cross-client coalescing: N viewers during an active night = N*3 queries every 8s, even though the data only changes once per completed round. live-session, the older equivalent live endpoint polled the same way, is cached at live_ttl=15s — tonight was simply left out.

**Zakaj (RCA):** The Tonight hub is the marquee S7 live feature polled every 8s by every viewer plus the home card; leaving it out of the HTTP cache means redundant DB work scales linearly with concurrent viewers on the busiest moments (active game nights), exactly when the DB is also ingesting rounds.

**Predlog popravka:** Add '/api/stats/tonight' and '/api/stats/hold-probability' to cacheable_prefixes, and add '/api/stats/tonight' to the live_prefixes tuple in _ttl_for_path so it gets the 15s live_ttl (matching live-session). A 10-15s server TTL collapses all viewers' 8s polls into one DB read per window without hurting the 'right now' feel. The frontend's per-client cachePolicy:'no-store' (tonight.js:106) only affects the browser cache; it does not stop the shared server-side cache from coalescing requests across clients.

**Verifikacija (skeptik, conf=high):** Could not refute. The omission is verified in code: http_cache_middleware.py cacheable_prefixes (lines 31-51) lists /api/stats/live-session but not /api/stats/tonight or /api/stats/hold-probability; _ttl_for_path live_prefixes (262-267) gives live-session the 15s live_ttl. Endpoints confirmed at players_router.py:199 (/stats/hold-probability) and :267 (/stats/tonight), mounted under /api (main.py:314). tonight.js:11 sets POLL_MS=8000, :106 polls /stats/tonight, :271-276 home card uses the same endpoint. get_tonight does 3 DB round-trips (:284 lua_round_teams date scan, :218 team-names, :166 hold-prob regex scan). Non-matching paths skip the cache entirely (dispatch line 78 returns call_next with no Cache-Control). No guard elsewhere coalesces these requests. The frontend no-store only affects the browser, not a server-side cache. One minor wording error in the finding: non-matching paths get no Cache-Control header, not the 'private, no-store' set at line 83 (which only fires for authed/cookie requests on matched prefixes) — does not change the conclusion.

_Ground-truth preverjeno:_ Read http_cache_middleware.py in full (prefixes 31-51, dispatch 60-88, _ttl_for_path 261-285). Grepped players_router.py for tonight/hold-probability (199, 267) and read _hold_prob_curve (166-204) and the main tonight query (280-292). Confirmed router mount prefix /api in main.py:314. Verified tonight.js POLL_MS=8000 and the two fetch sites (106, 276). Adjusted severity down because at the project's stated scale (~30-50 players, few concurrent spectators, small rounds/lua_round_teams tables) the redundant DB work is a few queries/sec on small tables — a real but low-impact consistency/perf nit with a trivial fix, not a medium structural risk.

---
