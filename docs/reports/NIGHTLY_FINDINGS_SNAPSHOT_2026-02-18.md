# Nightly Findings Snapshot (2026-02-18)

## Context
- Workspace: `slomix_discord`
- Branch during stabilization: `fix/codebase-review-findings`
- Primary PR: `https://github.com/iamez/slomix/pull/37`
- Snapshot time (UTC): `2026-02-18 16:18:43 UTC`

## Confirmed Closed
1. PR #37 is merged (`2026-02-18T16:15:17Z`) and green at merge.
2. CI/test/lint/security blockers from the stabilization cycle were resolved (tests, lint, CodeQL, Codacy all passed before merge).
3. Greatshot topshots privacy + accuracy issues flagged in review were addressed:
- user scoping enforced in topshots routes
- `player_count` sourced correctly from stats summary with backward-compatible fallback
4. Database adapter transaction behavior was corrected so rollback and in-transaction execution use the same connection context.

## Open / Follow-Up Items (from runtime and user validation logs)
1. Website weapons page had historical `404` on `GET /api/stats/weapons/by-player`.
- Current code now defines both `/api/stats/weapons/by-player` and `/api/stats/weapons/by_player` in `website/backend/routers/api.py`.
- If this reappears, verify deployed backend version and frontend request path/caching.
2. SSH monitor intermittently logged DNS resolution failures (`[Errno -3] Temporary failure in name resolution`).
- This looks infra/network-level, not an application logic exception.
3. Some automation commands previously failed in logs (`backup_db`, `metrics_report`, `duo_perf`).
- Backup logic now uses DB type detection and avoids hard-failing when SQLite path is absent in PostgreSQL mode.
- Metrics logger initializes its local metrics DB/table set on startup.
- `duo_perf` SQL issue was reported historically; re-run in Discord to confirm current behavior after latest deploy.
4. Session split/date anomalies were likely influenced by intentionally injected local test data in `local_stats/`.
- Data hygiene step remains important before final session analytics validation.

## Expected / Accepted Warnings
1. `greatshot.store` DDL privilege warning (`must be owner of table greatshot_demos`) can be expected when running with limited DB privileges and pre-existing schema.
2. Unimported historical files in `local_stats/` were intentionally deprioritized per operator instruction.

## Notes
- This report is a handoff snapshot only (no new code changes implied).
- Detailed stabilization ledger remains in:
- `docs/reports/PR37_STABILIZATION_FINDINGS_2026-02-18.md`
- `docs/SESSION_2026-02-18_PR37_STABILIZATION.md`
