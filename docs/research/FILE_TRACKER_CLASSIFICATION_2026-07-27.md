# File tracker startup classification (N4)

Date: 2026-07-27 22:05 CEST
Target: dev filesystem plus read-only dev PostgreSQL
Persistent writes: none

## Problem

`sync_local_files_to_processed_table()` compared every `.txt` file in
`local_stats/` with `processed_files`. That table belongs to the primary stats
pipeline; endstats use a separate pipeline and legacy weapon-stat sidecars are
outside the primary importer. The result was a false unimported warning on
every startup.

The old implementation also issued one `fetch_one` call per text file. On the
measured snapshot that meant 5,835 sequential database round-trips before it
could print the misleading warning.

## Measured inventory

The live directory changed while this work was in progress, so these numbers
record one exact snapshot rather than repeating the earlier 5,827-file count.

| Local file class | Count |
|---|---:|
| Primary stats | 4,840 |
| Endstats | 871 |
| `_ws.txt` sidecars | 124 |
| Other `.txt` files | 0 |
| Total | 5,835 |

The old set difference against `processed_files` contained 880 names:

- primary stats: **0**
- endstats: 763
- `_ws.txt` sidecars: 117

Therefore the actionable backlog was zero; every reported name was outside
the primary `processed_files` contract.

## Change

1. Reuse `SSHHandler.parse_gamestats_filename()` as the primary-pipeline
   classifier. This is the same filename grammar already used by ingestion.
2. Exclude sidecars and unsupported names before querying `processed_files`.
3. Fetch all matching primary filenames with one bounded `ANY(text[])` query
   rather than one query per local file.
4. Label log totals as `primary stats files` so the scope is explicit.

## Post-change measurement

The real sync method was run from the dev checkout against a read-only
PostgreSQL connection (`default_transaction_read_only=on`):

```text
DEBUG Ignoring 995 non-primary sidecar/unsupported files in local_stats
INFO All 4840 local primary stats files are tracked in database
MEASURED total_txt=5835 primary=4840 ignored=995 queries=1 bound=4840 elapsed_ms=31.981
```

This proves the warning is removed for the current zero-backlog snapshot and
the startup database work drops from 5,835 sequential lookups to one query.
Focused tests separately prove that a genuinely missing recent primary file
still produces a warning.
