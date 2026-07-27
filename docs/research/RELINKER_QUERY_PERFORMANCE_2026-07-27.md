# Proximity relinker query performance (N3)

Date: 2026-07-27  
Target: dev PostgreSQL `192.168.64.116:5432/etlegacy`  
Production writes: none  
Dev schema changes: none persisted; index builds ran inside one transaction
and were rolled back after measurement.

## Problem

The five-minute proximity relinker assembled 50 discovery legs with plain
`UNION`. PostgreSQL therefore performed repeated sort/unique work inside the
tree even though the outer query already uses `SELECT DISTINCT`. Only 11 of
the 24 generic source tables had a partial `round_id IS NULL` lookup index.

The larger cost was hidden behind those two known issues: the SQL read all
historical linked rows for mismatch detection, then Python discarded rows
older than the existing six-hour permanent-orphan limit. On the measured
snapshot, the SQL returned 50 rows and Python considered all 50 stale.

## Change

1. Use `UNION ALL` for every internal leg and retain the single outer
   `SELECT DISTINCT`, preserving the result set.
2. Push the existing six-hour cutoff into every NULL and mismatch leg. Rows
   with a positive source timestamp use the exact Unix cutoff. Legacy rows
   without one use the cutoff date so the date-only resolver remains usable.
3. Migration 068 adds the 13 missing partial covering indexes; the bootstrap
   schema carries the same index set.
4. Release config v1.30.0 includes migration 068. The migration is written
   and tested but was not applied.

## EXPLAIN ANALYZE evidence

The same connection and data snapshot were used for both variants. Three
runs were collected for each. The after measurement executed migration 068
inside the open transaction before measuring, then rolled the transaction
back.

| Metric | Before | After |
|---|---:|---:|
| Execution time, runs (ms) | 2149.682 / 1577.947 / 1665.248 | 213.254 / 191.086 / 185.455 |
| Median execution time | 1665.248 ms | 191.086 ms |
| Median improvement | - | 88.53% |
| Median shared blocks read | 72,128 | 34,304 |
| Temp blocks read/written | 542 / 544 | 0 / 0 |
| Returned rows on snapshot | 50 (all stale in Python) | 0 |

The actionable positive-start result sets were equal (`0 == 0`) on this
snapshot. This is the relevant equivalence check: the old SQL's 50 rows were
all older than the same six-hour policy and would not reach a write.

## Index cost

- Missing tables before: 13 of 24.
- Covered tables inside the measurement transaction: 24 of 24.
- Transactional build time for all 13 indexes: 163.426 ms.
- Total measured index size: 204,800 bytes (200 KiB).
- The transaction was rolled back; the dev catalog returned to its original
  11-index state.

## Verification and limits

- Unit contracts require only `UNION ALL` internally, one outer `DISTINCT`,
  the SQL cutoff parameters, the exact 13-table migration inventory, and
  bootstrap-schema parity.
- The migration runner acceptance and release-config contracts pass.
- A post-deploy measurement should confirm the live service duration when a
  genuinely fresh unlinked row exists. The current snapshot had no telemetry
  inside the six-hour repair window, so it proves the idle/backlog path rather
  than non-empty relinking throughput.
