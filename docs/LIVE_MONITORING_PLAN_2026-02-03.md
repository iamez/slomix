# Live Monitoring Plan - 2026-02-03

## Goal
Monitor live round flow and compare bot logs vs game server logs to detect timing,
missing files, webhook issues, or posting failures before the session ends.

## What We Will Monitor
1. **Bot service logs** (`journalctl -u etlegacy-bot -f`)
   - Session start detection
   - Stats file processing + posting
   - STATS_READY webhook handling
   - Endstats processing + posting
   - Achievement notifications

2. **Game server log** (`etconsole.log`)
   - Client download errors (FastDL fallbacks)
   - Map changes / round end lines
   - Any Lua webhook errors (if logged)
   - File write confirmations (if present)

## Correlation We’ll Check
- **STATS_READY** in bot logs ⇄ round end in server log
- **File detection** in bot logs ⇄ file write in server log
- **Endstats posted** ⇄ endstats file appearance
- **Timing values** (Lua vs stats) for anomalies

## Output / Documentation
- Create `docs/LIVE_MONITORING_NOTES_2026-02-03.md` with:
  - Timeline of events (timestamps from both sources)
  - Detected mismatches or delays
  - Suggested fixes (if any)

## Safety Constraints
- Read‑only monitoring only
- No config changes while live session is in progress

## Required Inputs
- Confirm full path to `etconsole.log`
- Confirm SSH access is allowed for read‑only tail
  - Example command: `ssh et@puran.hehe.si -p 48101 "tail -F /path/to/etconsole.log"`

## Start/Stop
- Start immediately before the session begins
- Stop after Round 1 or Round 2 (per your call)
