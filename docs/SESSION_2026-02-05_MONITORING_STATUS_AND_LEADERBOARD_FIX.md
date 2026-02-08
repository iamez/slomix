# Monitoring Status + Leaderboard Autoload
Date: 2026-02-05

## Summary
Addressed two issues:
1) Monitoring history visibility (server/voice charts looked empty with no clear reason).
2) Leaderboards not auto-populating on entry.

## Changes
- Added `/api/monitoring/status` for quick counts + last sample timestamps.
- Added monitoring info to `/api/diagnostics` payload.
- Updated server/voice history widgets to display last sample time (e.g., “last 5m ago”).
- If no data points yet, widgets now fetch monitoring status and show “no samples yet / unavailable”.
- Refactored leaderboard initialization to avoid redundant fetches and guarantee auto-load on entry.

## Files Touched
- `website/backend/routers/api.py`
- `website/js/live-status.js`
- `website/js/leaderboard.js`
- `website/js/app.js`
- `docs/TODO_MASTER_2026-02-04.md`

## Notes
- Local DB connection check from sandbox timed out; verify monitoring history via the web UI or `/api/monitoring/status`.
