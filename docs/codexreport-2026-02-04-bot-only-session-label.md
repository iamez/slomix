# Bot-Only Session Label (2026-02-04)

## Goal
Add a **bot-only session label** so Omni-bot-generated rounds can be filtered from analytics.

## What Was Implemented
### 1) Round-level labeling
New columns in `rounds`:
- `is_bot_round` (BOOLEAN)
- `bot_player_count` (INTEGER)
- `human_player_count` (INTEGER)

These are filled on import based on the player list from the stats file.

### 2) Bot detection (parser)
- Omni-bot names are detected by prefix **`[BOT]`** (after stripping ET color codes).
- Optional override via `.env`:
  - `BOT_NAME_REGEX` (regex, default `^\[BOT\]`)

### 3) Postgres migration
Applied:
- `migrations/008_add_bot_round_flags.sql`

## Files Changed
- `bot/community_stats_parser.py`
  - adds `is_bot` per player
  - adds bot/human counts + `is_bot_round` in stats result
  - supports `BOT_NAME_REGEX`
- `bot/ultimate_bot.py`
  - inserts `is_bot_round`, `bot_player_count`, `human_player_count` into `rounds`
  - supports same fields for match-summary rows
- `migrations/008_add_bot_round_flags.sql`
- `docs/SESSION_2026-02-03_CHANGELOG_LOCAL.md`

## How To Filter Bot-Only Sessions
Given a `gaming_session_id`, filter out sessions where **all rounds** are bot-only:
```sql
SELECT gaming_session_id
FROM rounds
WHERE gaming_session_id IS NOT NULL
GROUP BY gaming_session_id
HAVING SUM(CASE WHEN is_bot_round THEN 1 ELSE 0 END) = COUNT(*)
```

Or filter per round:
```sql
SELECT * FROM rounds WHERE is_bot_round = TRUE;
```

## Notes
- This labels only **newly imported** rounds. Old rounds will remain with default values.
- If bot name prefixes change, set `BOT_NAME_REGEX` in `.env`.

