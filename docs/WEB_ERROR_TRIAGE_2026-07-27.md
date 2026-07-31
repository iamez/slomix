# Web error triage — 2026-07-27

**Status:** diagnosis complete. **Re-verified 2026-07-31 — three of the five findings have since been fixed by other work.** This document is the handoff, kept as the record of what was measured and what closed it.
**Trigger:** the owner browsed the site and found errors in the `etlegacy-bot` / `etlegacy-web` journals.

Everything below was reproduced or measured on 2026-07-27 against the dev database and the running service on `127.0.0.1:8000`. Line references are against `main` at the time of writing. Where a claim was not verified, it says so. **Every numeric claim was re-measured on 2026-07-31**; where the number moved, both are shown rather than the older one silently replaced.

**Five findings — N1–N4 substantive, N5 cosmetic** (an earlier revision said "four" in the title and summary while the body carried an N5 section; the count is corrected rather than the section dropped, since a recorded 404 is worth keeping).

| | 2026-07-27 | 2026-07-31 |
|---|---|---|
| N1 proximity leaderboards default | 500 | **200, fixed** |
| N2 lua mislinks / duplicates | 44 / 37 | **0 / 0, repaired by #565** |
| N3 re-linker query | 3.1–4.4 s | still open |
| N4 false "876 unimported files" | 876 reported, 0 real | still open |
| N5 `/favicon.ico` 404 | cosmetic | cosmetic |
| Environment debt (Python 3.10) | blocking | **resolved — box is on 3.13.14** |

---

## Povzetek za ownerja (slovensko)

Pet najdb, zelo različne teže — in tri so se med 27. in 31. julijem **že rešile**:

1. ~~**Proximity leaderboards vračajo 500 privzeto**~~ — **POPRAVLJENO.** Danes vrne 200 z resničnimi podatki. Poleg tega vpliv nikoli ni bil takšen, kot je pisalo tu: React stran uporablja `crossfire`, ne `power`, zato navadni obiskovalci pokvarjene privzete poti sploh niso zadeli.
2. ~~**44 napačno povezanih lua vrstic in 37 podvojenih**~~ — **POPRAVLJENO.** Obe metriki sta danes 0. Popravek, ki ga ta dokument šele predlaga, je bil medtem napisan v #565 (`scripts/repair_lua_round_links.py` + migracija 067).
3. **Re-linker poizvedba traja 3–4,4 s** — performanca ozadja. **Še odprto.**
4. **"876 neuvoženih datotek" je lažni alarm** — dejansko jih je 0. **Še odprto.**
5. **`/favicon.ico` → 404** — kozmetično, brez ukrepa.

Okoljski dolg (Python 3.10) je prav tako **zaprt**: box je 2026-07-31 nadgrajen na 3.13.14.

Ostaneta torej **N3 in N4**, oba v ozadju in oba nevidna uporabniku.

---

## N1 — `/api/proximity/leaderboards` returned 500 on the default category

**Severity: API bug on the default code path — NOT a visible site outage.** An earlier revision of this document called it "a live outage… the panel is dead for every visitor". That was wrong, and the correction matters because it changes the priority (Codex review on #563).

The shipped React Proximity page never exercises the failing default. `website/frontend/src/pages/Proximity.tsx:1499` initializes `useState('crossfire')` and passes that category explicitly to `useProximityLeaderboards(activeTab, …)` at :1502 — and `power` is not among the offered tabs at all; the file's own comment at :22 records it as cut ("cut tabs (power, spawn, trades, …)"). The two remaining `power` references (:33, :47) are value formatters, not tabs. The route catalog marks this React page as the live modern `proximity` route, so ordinary visitors got a 200.

**Who was actually affected:** direct API clients that omit `category` or explicitly request `category=power`.

**Re-measured 2026-07-31 — the bug itself is gone:**

```
GET /api/proximity/leaderboards                  -> 200  {"status":"ok","category":"power","formula_version":"power-v2",…}
GET /api/proximity/leaderboards?category=power   -> 200
GET /api/proximity/leaderboards?category=crossfire -> 200
```

The default is still `power`; it now returns real data. The root-cause analysis below is kept because the two-conventions defect it documents is the kind that recurs.

### Symptom (as observed 2026-07-27)

```
ERROR | DatabaseAdapter | fetch_one failed (SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE round_id IS NOT NULL AND EXISTS (   SELECT 1 FROM r)
asyncpg.exceptions.PostgresSyntaxError: syntax error at or near "="
ERROR | api.proximity | leaderboards failed
WARNING | access | ← GET /api/proximity/leaderboards → 500
```

### Root cause

`attribution_breakdown()` — `website/backend/routers/proximity_helpers.py:192`, offending line **221**:

```python
f" FROM {table} {prefix.rstrip('.') or ''} {ungated}",
```

It splices the clause straight after `FROM {table}` with **no `WHERE` keyword**, producing:

```sql
FROM combat_engagement  session_date = $1 AND map_name = $2 AND (...)
```

PostgreSQL reads `session_date` as a table alias, then hits the operator. Reproduced exactly:

```
ERROR:  syntax error at or near ">="
LINE 1: ...(*) AS total FROM combat_engagement  session_date >= DATE '2...
```

(The log shows `=` rather than `>=` because a selected session date uses `=`; the rolling window uses `>=`. Same defect.)

### Why it happened — two conflicting conventions

| Function | Returns |
|---|---|
| `_build_proximity_where_clause()` — `proximity_helpers.py:240` | `"WHERE " + " AND ".join(...)` — **with** the keyword |
| `_lb_scope()` — `proximity_scoring.py:100` (return at :139) | `" AND ".join(clauses)` — **without** |

`attribution_breakdown` was written against the first. Its only real caller — `proximity_scoring.py:417`, category `power` — passes the second. The docstring says only "`where_sql` must be the gated clause", which is ambiguous enough that neither side is obviously wrong.

Other `FROM {table} {where_sql}` splices exist (`proximity_dashboard.py`, `proximity_positions.py`) and are **fine**: they receive the `WHERE`-prefixed form.

### Blast radius — measured live

`category: str = "power"` is the default (`proximity_scoring.py:81`), so a bare GET hits the broken path.

| Endpoint | Code |
|---|---|
| `/api/proximity/leaderboards` (default = power) | **500** |
| `?category=spawn` / `crossfire` / `trades` | 200 |
| `/api/proximity/{dashboard,classes,reactions,teamplay,aim-lock,kill-outcomes,session-scores,weapon-accuracy}` | 200 |
| `/api/{sessions,skill/leaderboard,storytelling/formula}` | 200 |

Exactly one code path is broken — but it is the default one.

### Why the tests did not catch it

`tests/unit/test_proximity_serving_layer_audit.py:390`:

```python
out = await attribution_breakdown(db, "combat_engagement", "WHERE x", ())
```

The fixture passes a shape **no real caller uses**, and the fake DB does not parse SQL, so a syntactically invalid query passes silently.

### Second, latent defect in the same function

```python
ungated = where_sql.replace(f" AND {gate}", "").replace(gate, "TRUE")
```

If neither replacement matches — a different `prefix`, a whitespace difference, a future edit to `_round_quality_gate_sql` — the gate silently **stays** in the "ungated" query. That raises nothing. It returns wrong numbers: `total_rows` equals the gated count and `linked_invalid_excluded` is always 0, i.e. the attribution block claims perfect attribution precisely when it is broken.

A wrong number is worse than a 500. Make a failed replacement an error.

### Fix

1. `attribution_breakdown` normalises the clause: accept either shape, prepend `WHERE` when missing, reject an empty clause loudly rather than silently scanning the whole table.
2. Document which shape each helper returns — the ambiguity is the root cause.
3. Harden the `ungated` construction: assert the gate was actually removed.
4. Fix the unit fixture to the real shape, and keep a `WHERE`-prefixed case so both are covered.
5. Add an **integration test against real PostgreSQL**, following `tests/integration/test_replay_track_linkage_pg.py`. A fake connection cannot catch a SQL syntax error — that is precisely how this shipped.

### Verification

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/api/proximity/leaderboards   # expect 200
```

The response must carry an `attribution` block with plausible numbers, not all zeros. The integration test must fail without the fix.

---

## N2 — 44 mislinked lua rows, 37 duplicate link *targets* — REPAIRED 2026-07-31

**Severity: data integrity. Both anomaly thresholds are configured at 0 and both are breached.**

```
WARNING | bot.services.round_linkage_anomaly | Anomaly detection found 2 breach(es): ['wrong_start_lua_rows', 'duplicate_lua_round_links']
```

Measured:

| Metric | Value |
|---|---:|
| linked `lua_round_teams` rows | 799 |
| `wrong_start_lua_rows` (`l.round_start_unix <> r.round_start_unix`) | **44 (5.5%)** |
| `map_name` mismatches | 0 |
| `round_number` mismatches | 0 |
| mean drift | **660 s** |
| date range | 2026-02-20 → 2026-07-19 |
| `duplicate_lua_round_links` | **37 duplicate _targets_, not 37 rows** |

**That last figure does not mean what an earlier revision implied** (Codex review on #563). The metric in `round_linkage_anomaly_service.py:178-186` counts *groups*, not rows:

```sql
SELECT COUNT(*) FROM (
  SELECT round_id FROM lua_round_teams WHERE round_id IS NOT NULL
  GROUP BY round_id HAVING COUNT(*) > 1
) t
```

So 37 was the number of `round_id` values carrying more than one Lua row — each contributing at least two rows, and some of those rows potentially also among the 44 wrong-start rows. Writing "44 + 37 rows" therefore both undercounted the group members and double-counted the overlap. Sizing a repair requires enumerating the rows inside those groups and deduplicating them against the mismatch set first.

Map name and round number agree **perfectly**, and the drift is roughly one round's length. That is the signature of a nearest-neighbour mislink onto the **adjacent replay of the same map**, not random corruption. `round_linkage_anomaly_service.py` already calls this out: "the classic back-to-back-replay nearest-neighbor mislink".

### Re-measured 2026-07-31 — both counts are now zero

```
duplicate_lua_round_links                 0     (was 37 groups)
wrong_start_lua_rows                      0     (was 44)
linked lua_round_teams rows             806     (was 799)
total / unlinked                    865 / 59
```

**The repair this section asked for has since been written and is on `main`** — PR #565, as `scripts/repair_lua_round_links.py` plus `migrations/067_repair_lua_round_links.sql`, with `068_add_relinker_unlinked_indexes.sql` alongside.

Its policy answers the determinism objection directly, and answers it the strict way rather than the convenient one — quoting the migration header:

> exactly one round matching source-native (`round_start_unix`, normalized `map_name`, `round_number`) → rebind; **zero or multiple exact targets → set `round_id` NULL, never guess**; abort before mutation if this projection would retain duplicate non-NULL `round_id` values.

That is what this section originally got wrong. Matching `map_name` and `round_number` against the *currently linked* round establishes only that the current link is wrong — never that exactly one *different* `rounds` row matches on `round_start_unix`. Missing stats and duplicate cross-server identities make the zero-candidate and multi-candidate cases unsafe to repair automatically, and 067 handles them by unlinking rather than by choosing.

The runtime re-linker gained a stale-fix path in the same wave (#566); the dev bot log shows it working, e.g. `lua_id=77 moved 999 → 42 (dist: 198966830s→30s, map=supply R1)`.

**Migration 067 IS applied on dev**, recorded `success=true` at 2026-07-29 08:19:44, alongside `068_add_relinker_unlinked_indexes.sql`. `apply_migrations.py --validate` reports `Applied: 70, Failed: 0, Pending: 0, Checksum mismatches: 0 — CLEAN`.

> **Correction (2026-07-31).** An earlier revision of this section claimed 067 was *not* recorded on dev, and attributed the zero counts to the runtime re-linker alone. That was wrong, and the cause is worth recording because it is silent: the check used `WHERE filename LIKE '06[78]%'`. **PostgreSQL `LIKE` has no bracket character classes** — `[`, `7`, `8`, `]` are matched literally — so the query returned zero rows and looked like a clean negative result rather than a malformed pattern. Use `LIKE '067%' OR LIKE '068%'`, or `~ '^06[78]'` for a real regex.

**The open question from 2026-07-27 — whether the cause was still active — is answered:** no new mislinks in the four days since, and the most recent remains 2026-07-19.

---

## N3 — orphan re-linker query takes 3.1–4.4 s

**Severity: background performance.**

```
WARNING | DatabaseAdapter | SLOW QUERY (3136ms, 50 rows): SELECT DISTINCT map_name, round_number, round_start_unix, session_date FROM (... WHERE round_id IS NULL UNION ...
WARNING | DatabaseAdapter | SLOW QUERY (4401ms, 50 rows): ...
```

Source: `bot/cogs/proximity_mixins/relinker_mixin.py:118`. **Counted exactly** (an earlier revision said "roughly 48 subqueries, each scanning for `round_id IS NULL`", which was wrong on both halves — Codex review on #563):

| | count |
|---|---:|
| tables in `tables_with_round_number` | 24 |
| null legs (`WHERE round_id IS NULL`) | 24 + `lua_round_teams` = **25** |
| mismatch legs (`JOIN rounds` … `round_start_unix != r.round_start_unix`) | 24 + `lua_round_teams` = **25** |
| **total subqueries** | **50** |

**Only half the query scans for `round_id IS NULL`.** The other 25 legs join already-linked rows to `rounds` and filter on mismatched start times — a completely different access pattern. A partial index predicated on `round_id IS NULL` cannot serve them at all.

Two candidate causes, with the correction applied to the second:

1. **`UNION` instead of `UNION ALL`.** `UNION` deduplicates at every step, although the outer query is already `SELECT DISTINCT`. This applies to all 50 legs.
2. **Missing partial indexes — but they can only address the null half.** Exactly **11** partial indexes on `round_id IS NULL` exist across the schema against 25 null legs. Adding the missing ones is worth doing, yet on its own it leaves the 25 mismatch legs untouched, and nothing here establishes which half dominates the 3.1–4.4 s.

**Do not prescribe indexes off this diagnosis.** Profile the two leg types separately first (`EXPLAIN (ANALYZE, BUFFERS)` on one representative null leg and one mismatch leg) and let the measurement name the cause. An implementer who adds 14 partial indexes on the strength of the old text could plausibly move the number very little.

NULL volumes, for sizing the benefit:

| Table | NULL `round_id` | Total |
|---|---:|---:|
| `proximity_shot_fired` | 51,610 | 648,214 |
| `combat_engagement` | 6,282 | 117,594 |
| `player_track` | 2,927 | 57,311 |
| `proximity_hit_region` | 682 | 309,464 |
| `proximity_reaction_metric` | 244 | 104,303 |

**Note:** `proximity_shot_fired` has by far the largest orphan pool (8%) and is **not** in the re-linker's table list. Whether that is deliberate or an oversight is an open question.

Partial indexes go in a **new migration**. Measure with `EXPLAIN (ANALYZE)` before and after and state the real number rather than a target.

---

## N4 — "876 unimported files" is a false alarm

**Severity: noise, but the corrosive kind.**

```
WARNING | bot.automation.file_tracker | ⚠️  Found 22 unimported recent files in local_stats/ (total unimported: 876, total files: 5827)
```

Measured:

| | |
|---|---:|
| files in `local_stats/` | 5,827 |
| rows in `processed_files` | 5,071 |
| "unimported" | 876 |
| of those, `-endstats.txt` | **759** |
| of those, `_ws.txt` (2024 sidecars) | **117** |
| **genuinely unimported stats files** | **0** |

`file_tracker` compares **every** file in `local_stats/` against `processed_files`, which only tracks the main stats files. Endstats are handled by a separate pipeline and never recorded there; `_ws.txt` is a different format entirely.

So the warning has been crying wolf on every start. That is worse than silence, because it trains everyone to ignore the one time it is real.

**Fix:** count only what this pipeline actually imports. Report the other kinds separately as information, if at all.

---

## N5 — `GET /favicon.ico → 404`

Cosmetic; no fix required. Counted as the fifth finding rather than left uncounted — the summary above says five, not four.

---

## Environment debt (found while checking the above) — RESOLVED 2026-07-31

`website/backend/map_geometry/pk3_index.py:10` uses `from enum import StrEnum`, which requires **Python 3.11**.

| | 2026-07-27 | 2026-07-31 |
|---|---|---|
| `pyproject.toml` declares | `requires-python = ">=3.11,<3.14"` | unchanged |
| CI runs | 3.11 → all 12 checks pass | unchanged |
| **the running service uses** | **Python 3.10.12** | **Python 3.13.14** |

This was the **only** 3.11-only construct in the codebase. The risk described here — that wiring `map_geometry` into a live route would break the web service at import, invisibly to CI — is closed: the box was upgraded to **3.13.14** on 2026-07-31, which also took `pytest tests/` from `Interrupted: 2 errors during collection` to 3971 passed. See `docs/PYTHON_313_UPGRADE_2026-07-31.md`.

The alternative suggested here (`class MapAssetKind(str, Enum)`, which works on both) was **not** taken, and should not be retrofitted now — the environment was the drift, not the code.

---

## Suggested order (revised 2026-07-31)

N1, N2 and the environment debt are closed. What remains:

1. **N3** — profile the null and mismatch legs separately *before* proposing indexes
2. **N4** — the false "876 unimported files" alarm, which trains everyone to ignore a real one

Separate PRs; the causes are unrelated and bundling them would mix risks. No merging without the owner's approval.

## Provenance

Originally measured 2026-07-27 against `etlegacy` on `127.0.0.1:5432` and the service on `127.0.0.1:8000`. **Re-verified 2026-07-31** against the same database and service, now on Python 3.13.14:

- N1 re-check: `curl` on the default, `?category=power` and `?category=crossfire` — all 200; `Proximity.tsx:1499` read for the actual initial tab
- N2 re-check: the anomaly service's own two queries re-run verbatim — both 0; `migrations/067_repair_lua_round_links.sql` read on `origin/main`; `schema_migrations` queried for 067/068 (re-done 2026-07-31 after the first attempt used an invalid `LIKE '06[78]%'` pattern — see the correction above) and cross-checked against `apply_migrations.py --validate`
- N3 re-check: subquery legs counted by parsing `tables_with_round_number` out of `relinker_mixin.py` — 24 tables → 50 legs, 25 of them null legs

Original measurements:

- N1 reproduction: rebuilt the `ungated` string from `_lb_scope`'s output and executed it — `syntax error at or near ">="`
- N1 blast radius: `curl` sweep over 20 endpoints
- N2: `lua_round_teams` joined to `rounds`, comparing `round_start_unix`, `map_name`, `round_number`
- N3: `pg_indexes` filtered on `indexdef ILIKE '%round_id IS NULL%'`; NULL counts per table
- N4: set difference between `os.listdir("local_stats")` and `processed_files.filename`, split by suffix
- Environment: `venv/bin/python --version`, `/proc/<uvicorn pid>/exe --version`, `pyproject.toml`, `.github/workflows/tests.yml`

Related: #548 (introduced `attribution_breakdown`), #560 (real-PostgreSQL test pattern), `docs/PROXIMITY_SPIDER_WEB_SPEC_2026-07.md`.
