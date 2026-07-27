# Web error triage — 2026-07-27

**Status:** diagnosis complete, no fixes applied. This document is the handoff.
**Trigger:** the owner browsed the site and found errors in the `etlegacy-bot` / `etlegacy-web` journals.

Everything below was reproduced or measured on 2026-07-27 against the dev database and the running service on `127.0.0.1:8000`. Line references are against `main` at the time of writing. Where a claim was not verified, it says so.

---

## Povzetek za ownerja (slovensko)

Štiri stvari, zelo različne teže:

1. **Proximity leaderboards vračajo 500 privzeto** — panel na strani je mrtev za vsakega obiskovalca. To je moj hrošč iz #548, ne Codexov. Reproduciran, vzrok znan.
2. **44 napačno povezanih lua vrstic** (5,5 %) in 37 podvojenih — podatkovna integriteta.
3. **Re-linker poizvedba traja 3–4,4 s** — performanca ozadja.
4. **"876 neuvoženih datotek" je lažni alarm** — dejansko jih je 0.

Plus latenten okoljski dolg: nova `map_geometry` koda rabi Python 3.11, živa storitev pa teče 3.10.

Najpomembnejše: **prva je edina, ki jo uporabnik dejansko vidi.**

---

## N1 — `/api/proximity/leaderboards` returns 500 on the default category

**Severity: live outage on the default code path.**

### Symptom

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

## N2 — 44 mislinked lua rows, 37 duplicate links

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
| `duplicate_lua_round_links` | **37** |

Map name and round number agree **perfectly**, and the drift is roughly one round's length. That is the signature of a nearest-neighbour mislink onto the **adjacent replay of the same map**, not random corruption. `round_linkage_anomaly_service.py` already calls this out: "the classic back-to-back-replay nearest-neighbor mislink".

**Approach:** diagnose before repairing. Because map and round number match, the correct target is identifiable — the round whose `round_start_unix` actually matches. 44 + 37 rows is a small, enumerable set.

Repair belongs in a **new migration**; applied migrations are immutable (editing one puts every target into checksum drift that `--mark` cannot repair). Dry-run output before `--apply`.

**Open question for the owner:** the most recent mislink is 2026-07-19, so it is not clear whether the cause is still active or this is purely historical. Establish that before repairing, or the repair will need repeating.

---

## N3 — orphan re-linker query takes 3.1–4.4 s

**Severity: background performance.**

```
WARNING | DatabaseAdapter | SLOW QUERY (3136ms, 50 rows): SELECT DISTINCT map_name, round_number, round_start_unix, session_date FROM (... WHERE round_id IS NULL UNION ...
WARNING | DatabaseAdapter | SLOW QUERY (4401ms, 50 rows): ...
```

Source: `bot/cogs/proximity_mixins/relinker_mixin.py:118`. It builds a `UNION` across **24 tables**, plus a matching set of mismatch legs — roughly 48 subqueries, each scanning for `round_id IS NULL`.

Two concrete causes:

1. **`UNION` instead of `UNION ALL`.** `UNION` deduplicates at every step, although the outer query is already `SELECT DISTINCT`.
2. **Missing partial indexes.** Exactly **11** partial indexes on `round_id IS NULL` exist across the schema, while the query touches 24 tables. Thirteen are scanned unsupported.

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

Cosmetic. Listed for completeness; no fix required.

---

## Environment debt (found while checking the above)

`website/backend/map_geometry/pk3_index.py:10` uses `from enum import StrEnum`, which requires **Python 3.11**.

| | |
|---|---|
| `pyproject.toml` declares | `requires-python = ">=3.11,<3.14"` |
| CI runs | 3.11 → all 12 checks pass |
| **the running service uses** | **Python 3.10.12** |

This is the **only** 3.11-only construct in the codebase; everything else has been de-facto 3.10-compatible. Nothing breaks today, because `map_geometry` is not imported by any live code path. **The moment W3 or W4 wires it into an API route, the web service will fail at import** — and CI cannot catch it, because CI runs the version the declaration promises rather than the one that is actually deployed.

Either upgrade the environment to 3.11 (correct — the declaration is 3.11+ and the environment is the drift) or use `class MapAssetKind(str, Enum)`, which works on both.

Upgrading is not a `pip install`: it means rebuilding the venv and restarting both services. **Owner-gated** — say so before doing it, not after.

---

## Suggested order

1. **Environment debt** — blocks anything that puts `map_geometry` on a live path
2. **N1** — the site is visibly broken by default
3. **N2**, **N3**, **N4** — separate PRs; the causes are unrelated and bundling them would mix risks

Each as its own PR. No merging without the owner's approval.

## Provenance

All measured 2026-07-27 against `etlegacy` on `127.0.0.1:5432` and the service on `127.0.0.1:8000`.

- N1 reproduction: rebuilt the `ungated` string from `_lb_scope`'s output and executed it — `syntax error at or near ">="`
- N1 blast radius: `curl` sweep over 20 endpoints
- N2: `lua_round_teams` joined to `rounds`, comparing `round_start_unix`, `map_name`, `round_number`
- N3: `pg_indexes` filtered on `indexdef ILIKE '%round_id IS NULL%'`; NULL counts per table
- N4: set difference between `os.listdir("local_stats")` and `processed_files.filename`, split by suffix
- Environment: `venv/bin/python --version`, `/proc/<uvicorn pid>/exe --version`, `pyproject.toml`, `.github/workflows/tests.yml`

Related: #548 (introduced `attribution_breakdown`), #560 (real-PostgreSQL test pattern), `docs/PROXIMITY_SPIDER_WEB_SPEC_2026-07.md`.
