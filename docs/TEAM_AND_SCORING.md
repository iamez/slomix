## Persistent Teams and Stopwatch Scoring

### Overview
- **Axis/Allies are roles**, not real teams. Real teams (e.g., `Lakers` vs `Mavericks`) persist across side switches in Stopwatch mode.
- This bot automatically detects persistent teams per session date and stores them for downstream use (summaries, MVPs, scoring).

### Where Teams Are Stored
- Table: `session_teams`
  - Key columns:
    - `session_start_date` (YYYY-MM-DD)
    - `map_name` (set to `ALL` for persistent session teams)
    - `team_name` (e.g., `Team A`, `Team B` or custom names if present)
    - `player_guids` (JSON array of GUIDs)
    - `player_names` (JSON array of latest known aliases)

### Automatic Team Detection
- Entry point: `ETLegacyCommands._detect_and_store_persistent_teams(db, session_date)`
- Heuristic:
  1. Seed both teams from Round 1 game teams (team 1 vs team 2). If Round 1 is missing, seeds from earliest available round.
  2. For players who join later, assign to the team with whom they most frequently shared a game-team across rounds (co-membership voting).
  3. Persist two rows in `session_teams` (`map_name='ALL'`) containing GUIDs and names.

### How The Bot Uses Teams
- Command `last_session`:
  1. Attempts to read `session_teams` via `get_hardcoded_teams`.
  2. If not present, auto-detects persistent teams and re-reads.
  3. Uses detected team names/rosters throughout the session summary (MVPs, player lists). Falls back only if detection truly fails.

### Stopwatch Scoring (Correct Rules)
- File: `tools/stopwatch_scoring.py`
- Rules per map:
  - Two rounds share a time limit.
  - Round 1: Team1 attacks, Team2 defends
    - If attackers finish before time limit → Team1 +1
    - If time runs out (fullhold) → Team2 +1
  - Round 2: Team2 attacks, Team1 defends
    - If attackers finish before time limit → Team2 +1
    - If time runs out (fullhold) → Team1 +1
  - Map score = sum of both rounds (possible: 2-0, 1-1, 0-2)

### Implementation Highlights
- `StopwatchScoring.calculate_map_score(limit, r1_time, r2_time)`:
  - Compares each round’s `actual_time` to `time_limit` independently.
  - Returns `(team1_points, team2_points, description)` with round-by-round summary.
- `StopwatchScoring.calculate_session_scores(session_date)`:
  - Groups rounds into map pairs by `map_name`.
  - Computes map points and totals keyed by the two persistent team names.

### Integration Points
- `bot/ultimate_bot.py` uses `StopwatchScoring(...).calculate_session_scores(latest_date)` to render the final scoreboard.
- Persistent team names/rosters come from `session_teams`; if absent, the bot auto-detects and stores them before displaying.

### Troubleshooting
- If team names don’t appear:
  - Ensure there’s data in `player_comprehensive_stats` for the session date.
  - The detector seeds from Round 1; if no Round 1 exists, it falls back to earliest round.
  - Confirm `session_teams` exists and is indexed: `idx_session_teams_date`, `idx_session_teams_map`.


