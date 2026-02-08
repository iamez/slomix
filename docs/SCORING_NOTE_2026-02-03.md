# Scoring Note - 2026-02-03

## Context
User reported a scoring rule mismatch in `!last_session`:
- Example symptom: A session shows a perfect tie like `11:11` even when one team clearly wins more maps by time.
- Desired behavior (Superboyy-style): **map winner by time** should decide the score.

This document captures the hypothesis and intended change for easy revert if incorrect.

## Previous Implementation (before 2026-02-03 change)
Scoring logic is implemented in:
- `bot/services/stopwatch_scoring_service.py`

Current rule (independent round scoring):
- Round 1:
  - Attackers complete under time limit => Team1 +1
  - Fullhold => Team2 +1
- Round 2:
  - Attackers complete under time limit => Team2 +1
  - Fullhold => Team1 +1
- Map score = sum of both rounds (0–2 points per team)

This can yield 1–1 ties even when one team beats the other team's time in Round 2.

## Implemented Change (2026-02-03)
We switched to **map-winner scoring** to match Superboyy’s results:
- **Primary source**: Round 2 header `winnerteam` (side winner) → map winner.
- **Fallback**: time comparison if header winner is missing.
- **Tie-break**: if times are equal, Round 1 attackers win (legacy-safe).

Map score = **1 point** to the map winner (0–0 if tie). 

### Example
- R1 attackers set time: 11:11
- R2 attackers finish in 10:30 (beat time)
=> R2 attackers win the map (score 0–1).

## Files Changed
- `bot/services/stopwatch_scoring_service.py`

## Revert Guidance
To revert back to independent round scoring:
- Restore `bot/services/stopwatch_scoring_service.py` to the prior per‑round logic.
- Verify `!last_session` and `!session_score` outputs (they will return to ties on equal completions).

## Notes
This should be validated against ET:Legacy stopwatch scoring rules or known match results.
If the correct rule is the current independent-round scoring, no action is required.
