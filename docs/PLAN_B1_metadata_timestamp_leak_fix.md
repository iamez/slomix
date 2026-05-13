# B1 Fix Plan — Stale Lua Metadata Leak

**Status**: Draft / awaiting user sign-off
**Audit reference**: original plan PR 2 / B1 (`_pending_round_metadata` race)
**Memory reference**: `round_metadata_timestamp_leak.md` (2026-05-09)
**Date**: 2026-05-13

---

## 1. Problem

In rare cases, a stats file's `_pop_pending_metadata(filename)` returns a Lua metadata dict that *actually belongs to an earlier, already-imported round on the same map*. The result is two rounds sharing identical `round_start_unix` / `round_end_unix`, collapsing to the same `round_canonical_id`.

### Observed frequency (verified live, 2026-05-13)

| | Memory (2026-05-09) | Today |
|---|---|---|
| DEV `etlegacy` | 1 pair | 1 pair |
| PROD `etlegacy` | 1 pair | **3 pairs** |

Memory's revisit threshold was "> 5 pairs". We're at 3 / trending up (+2 in 4 days). Fix now.

### Collision pairs (PROD)

| `round_start_unix` | round_ids | map | seconds between filename insert |
|---|---|---|---|
| 1771450806 | {9883, 9886} | te_escape2 R2 | 958s |
| 1771969065 | {9955, 9958} | te_escape2 R1 | 1009s |
| 1774403225 | {10173, 10184} | sw_goldrush_te R1 | 30219s |

All three: same `(map, round_number)`, identical `round_start_unix` AND `round_end_unix`, filename `round_time` differs by 16-min/17-min/8-hour windows. The 8-hour case is a backfill — late SSH polling caught a previously-uncovered round.

---

## 2. Why the original "asyncio.Lock" plan was wrong

Original PR 2 audit listed B1 as a **TOCTOU race** ("concurrent dict access from Lua webhook tasks + endstats monitor"). That diagnosis is incorrect on two counts:

1. **Python asyncio is single-threaded.** `_pop_pending_metadata` and `_queue_pending_metadata` are **sync** methods with no `await` between read and write. Each call is atomic relative to other coroutines. No lock can reorder operations that the event loop has already serialized.

2. **The bug is temporal, not concurrent.** Per memory deep-dive:
   - Round N stats file imported via SSH polling → `_pop_pending_metadata` finds empty queue → round imported without Lua metadata.
   - Lua webhook for round N fires *late* → `_queue_pending_metadata` parks the entry, nothing pops it.
   - Round N+1 stats file arrives (~minutes later) → `_pop_pending_metadata` finds the leftover entry → proximity-matcher attaches it to round N+1.

A lock changes nothing; the leftover would still be there.

---

## 3. The fix — Defensive DB lookup at pop time

After the proximity matcher selects a candidate, **check whether its `round_start_unix` is already attached to a round in the DB**. If yes, that entry belongs to that round, so discard it (return `None` to caller — same behavior as "no Lua metadata available", caller proceeds without it).

### Selected approach: minimal-surface async upgrade

- Convert `_pop_pending_metadata` from `def` → `async def`.
- Add `await` at all 3 caller sites (already in async context).
- Add a single targeted SELECT using the existing composite index.
- Fail open on any DB error (preserve legacy behavior on transient failures).

### Pseudo-diff

```python
# bot/services/webhook_metadata_mixin.py

async def _pop_pending_metadata(self, filename: str):
    # ... existing proximity-match logic unchanged ...
    selected = candidates.pop(best_idx)
    metadata = selected.get("metadata")

    # NEW: stale-entry gate.
    if metadata and getattr(self, "db_adapter", None) is not None:
        rsu = _safe_int(metadata.get("round_start_unix"))
        map_name = metadata.get("map_name")
        round_number = _safe_int(metadata.get("round_number"))
        if rsu > 0 and map_name and round_number > 0:
            try:
                row = await self.db_adapter.fetch_one(
                    "SELECT id FROM rounds "
                    "WHERE map_name = ? AND round_number = ? "
                    "  AND round_start_unix = ? LIMIT 1",
                    (str(map_name).lower(), round_number, rsu),
                )
                if row:
                    webhook_logger.warning(
                        "🚫 Stale Lua metadata for %s — round_start_unix=%d "
                        "already attached to round_id=%s; discarding to "
                        "prevent canonical_id collision.",
                        metadata_key, rsu, row[0],
                    )
                    return None
            except Exception as e:
                webhook_logger.warning(
                    "DB lookup failed during stale-metadata gate (%s); "
                    "attaching metadata as before.", e,
                )
                # fall through with metadata intact

    if best_diff is not None:
        webhook_logger.info(
            f"📎 Attached pending Lua metadata for {metadata_key} (Δ {best_diff}s)"
        )
    else:
        webhook_logger.info(f"📎 Attached pending Lua metadata for {metadata_key}")
    return metadata
```

### Caller updates

Three sites, all already inside `async def`:

| File | Line | Change |
|---|---|---|
| `bot/ultimate_bot.py` | 847 | `override_metadata = self._pop_pending_metadata(filename)` → `await self._pop_pending_metadata(filename)` |
| `bot/services/webhook_handler_mixin.py` | 334 | same |
| `bot/services/monitor_tasks_mixin.py` | 246 | same |

`_queue_pending_metadata` stays sync (no DB access needed there).

---

## 4. Mandelbrot RCA verification

### Phase 1 — Discovery ✅
- Three collision pairs verified live on PROD. Same-map, same-round_number, identical unix.
- 3/3 callers of `_pop_pending_metadata` are in `async def` context.

### Phase 2 — Dependencies
- `self.db_adapter` available on `UltimateETLegacyBot` (mixin host).
- Index `idx_rounds_map_round_start` on `(map_name, round_number, round_start_unix)` already exists → query is index-seek, sub-ms.
- No new tables, no new columns, no migration needed.

### Phase 3 — Contracts
- Return-type unchanged: `Optional[dict]`.
- `None` semantics unchanged: callers already treat `None` as "import without metadata".
- Sync→async conversion is the only API break, contained to 3 known call sites.

### Phase 4 — 12-point zoom (edge cases)
| # | Edge case | Behavior |
|---|---|---|
| 1 | `round_start_unix = 0` in metadata | Skip the gate, attach as before |
| 2 | `map_name` or `round_number` missing | Skip the gate, attach as before |
| 3 | `db_adapter` not set (tests, partial init) | Skip the gate, attach as before |
| 4 | DB query raises (transient PG error) | Warn + attach as before (fail open) |
| 5 | DB query returns row | Discard metadata, return None, callers proceed without |
| 6 | Two queued entries, first stale, second fresh | Current matcher picks one; gate removes if stale. We do NOT retry with second — keep one-shot semantics, return None |
| 7 | Concurrent: round being inserted in another coroutine, not yet committed | Lookup returns 0 rows → metadata attaches → race may produce duplicate. Mitigated by existing UNIQUE constraint (migration 050) catching at insert. |
| 8 | Backfill / batch import | Each pop is independent; gate works per-call |
| 9 | Test isolation | Mock `db_adapter.fetch_one` returns `None` (no row) → existing tests pass unchanged |
| 10 | Index miss (LOWER on map_name? schema check needed) | Verified: query uses `str(map_name).lower()` to match `_normalize_metadata_map_name` convention; map_name stored lowercased per schema |
| 11 | Performance | Single index seek on ~2300-row table = sub-ms; called ≤ once per stats import (≤ 1-2/min in live play) |
| 12 | Logging cardinality | WARN per discard — expected ≤ 1/week based on PROD trend. Not noisy |

### Phase 5 — 5-Whys
- Why does the leak happen? Late Lua webhook leaves a leftover entry that the proximity matcher mis-attaches.
- Why doesn't the matcher know it's stale? It operates on in-memory queue without DB context.
- Why no DB context? `_pop_pending_metadata` is sync, mixin was kept sync at extraction time.
- Why sync at extraction? Simplicity; the failure mode wasn't yet observed.
- Why is it surfacing now? Frequency was 0.07% historically; not a priority then. Now trending +200% in 4 days.

### Phase 6 — Fix in 4

Same as section 3. Covered.

---

## 5. Tests

### `tests/unit/test_pop_pending_metadata_stale_gate.py` (new)

1. **happy_path_attaches_metadata_when_no_db_row** — queue an entry, `db_adapter.fetch_one` returns `None`, pop returns the metadata.
2. **stale_gate_discards_when_round_already_has_start_unix** — queue, mock `fetch_one` returns `(round_id,)`, pop returns `None`, WARN log emitted.
3. **gate_skips_when_round_start_unix_is_zero** — metadata with `round_start_unix=0`, gate is bypassed, metadata returned.
4. **gate_fails_open_on_db_error** — `fetch_one` raises, pop returns metadata as before (no crash).
5. **gate_skips_when_db_adapter_absent** — bot mock without `db_adapter` attribute, pop returns metadata.

All tests use a minimal mixin host (`_WebhookMetadataMixin` directly) with mocked attributes — mirrors existing `test_stats_ready_race_reorder.py` pattern.

### Regression: existing tests must still pass

`pytest tests/unit/ -x` — 2917 baseline. Must remain green.

---

## 6. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Async conversion misses a call site | Low | Bot crash on sync call to coroutine | grep verified 3 sites + tests + CI lint |
| DB lookup blocks event loop (slow query) | Very low | Latency spike on stats import | Index already exists, query is sub-ms |
| Mock `db_adapter` in tests misses real interface | Low | False-green tests | Mirror pattern from existing async DB tests |
| Fail-open swallows real bug | Low | Stale metadata still attached on DB outage | WARN log surfaces it; we accept this trade-off vs blocking imports |
| Memory `round_metadata_timestamp_leak.md` becomes stale | Cert | Future readers confused | Update memory at end of PR |

**Out of scope explicitly**:
- Backfill / cleanup of existing 3 collision rows on PROD (data fix, separate decision).
- Refactor of `_queue_pending_metadata` to async (not needed; queue is pure memory op).
- Lock around `_pending_round_metadata` (per RCA, not needed; single-threaded event loop guarantees atomicity for sync methods).

---

## 7. PR sequence

1. **Branch**: `fix/b1-stale-metadata-db-gate`
2. **Commits**:
   - `feat(webhook-metadata): defensive DB lookup in _pop_pending_metadata` — code + caller updates
   - `test(webhook-metadata): cover stale-gate behavior + fail-open` — new tests
   - `docs(memory): refresh round_metadata_timestamp_leak with fix landing date` — local memory only, not in PR
3. **PR description**: link memory + this plan + collision-count timeline
4. **CI**: must pass (Python tests, Codacy, CodeQL, etc.)
5. **Review**: expect 1-2 Copilot/Codex findings (e.g., "should you also check `round_end_unix`?" — addressable inline)

---

## 8. What I'd add / open questions

These are the items I'm not 100% sure about — flagged for user input:

1. **Should the gate also check `round_end_unix`?** Argument for: belt-and-suspenders. Argument against: `round_start_unix` is the canonical-id ingredient; `round_end_unix` matching is implied. Decision: **skip for now**, add only if collisions reappear with different `start_unix` but same `end_unix` (no evidence of that case).

2. **Should we retry with the next-best candidate when the first is stale?** Argument for: maybe a fresh entry is hiding behind a stale one in the bucket. Argument against: complexity; the proximity matcher's `best_diff` selection presumes one-shot. Decision: **skip for now**, one-shot. If a second collision per same key appears in the wild, revisit.

3. **Should we add a metric / counter** (not just WARN log) for stale-discards? Argument for: trend visibility. Argument against: no metrics infrastructure currently. Decision: **WARN log is enough** — easy to count via `journalctl | grep "Stale Lua metadata"`.

4. **Should we clean up the 3 existing collision rows on PROD?** They're caught by migration 050 UNIQUE constraint already. The user worked around them with `--allow-collisions`. Recommendation: **leave them**, fix is forward-looking only.

5. **Should we do the fix on a `fix/...` branch or `chore/...`?** This is a bug fix, so `fix/`. Confirmed.

6. **Conventional commit type for main commit**: `fix(webhook-metadata)` (not `feat` as drafted in §7). Corrected.

---

## 9. Execution checklist

- [ ] Branch off latest main
- [ ] Verify B1 detection count one more time (lock to "3 rows on PROD")
- [ ] Edit `bot/services/webhook_metadata_mixin.py` (async conversion + gate)
- [ ] Edit 3 caller sites: `bot/ultimate_bot.py`, `bot/services/webhook_handler_mixin.py`, `bot/services/monitor_tasks_mixin.py`
- [ ] Write 5 new tests in `tests/unit/test_pop_pending_metadata_stale_gate.py`
- [ ] Run full unit suite: `pytest tests/unit/ -x` — must be 2922+ pass (5 new), 0 fail
- [ ] Run lint: `ruff check .`
- [ ] Commit + push + create PR
- [ ] Address review comments (Codex/Copilot)
- [ ] After merge: update memory `round_metadata_timestamp_leak.md` with fix-landed date + new threshold
