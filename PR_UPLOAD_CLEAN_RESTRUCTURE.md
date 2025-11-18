PR Title: Merge snapshot from workspace — clean-restructure (Oct 12–26)

Branch: upload/clean-restructure → base: main

---

Summary
-------
This PR contains a full snapshot of the updated ET:Legacy bot workspace (refactor + features implemented between Oct 12–26). It adds performance improvements, caching, achievements, comparison visualizations, a season system, and extensive documentation and tests.

This PR was created from a local workspace snapshot and is intended to bring the `main` branch up to date with the work in `clean-restructure`.

Key features and files changed
------------------------------
- Performance
  - Added 9 DB indexes (index script: `add_database_indexes.py`) — major speedups for leaderboard and stats queries
  - Query caching: `StatsCache` (5 min TTL) integrated into `!stats` command

- Player engagement
  - Achievement System: `AchievementSystem` (+ `!check_achievements`)
  - Player comparison radar charts: `!compare` (matplotlib) and `test_player_comparison.py`
  - Season System: `SeasonManager` + `!season_info` and `test_season_system.py`

- Docs & Tests
  - Many documentation files: `ENHANCEMENT_IDEAS.md`, `SEASON_SYSTEM.md`, `ACHIEVEMENT_SYSTEM.md`, `AI_PROJECT_STATUS_OCT12.md`, `WHATS_NEXT.md`, etc.
  - Test files: `test_query_cache.py`, `test_player_comparison.py`, `test_season_system.py`, and more test harness files.

- Bot code
  - `bot/ultimate_bot.py` — major additions: StatsCache, AchievementSystem, SeasonManager, new commands, and integrations

Notes about history
-------------------
This branch was pushed from a workspace snapshot and therefore had no common ancestor with `main` on the remote. To avoid accidental data loss, the snapshot was pushed first to `upload/clean-restructure` (backup). The workspace commit was later force-pushed to `clean-restructure` per project owner's instruction. This PR targets `upload/clean-restructure` so you can safely review the diff vs `main`.

Testing performed (local)
-------------------------
- `test_player_comparison.py` executed — generated chart and verified stats
- `test_query_cache.py` executed — confirmed cache hit behavior and speedup
- `test_season_system.py` executed — all 6 tests passed
- Basic runtime checks for `bot/ultimate_bot.py` functions and importability

Merge checklist (please verify before merging)
----------------------------------------------
- [ ] Review major new files (docs + tests) for sensitive data (no secrets should be committed). In particular, confirm `.env.example` and `.env.template` do not include production tokens.
- [ ] Confirm `bot/etlegacy_production.db` backups are not intended to be included in the repo. (I committed backup files; if you prefer, I can remove DB backups from the commit and re-push.)
- [ ] Run CI and unit tests if present
- [ ] Manual smoke test in a staging environment (recommended): start the bot and run `!ping`, `!season_info`, `!compare`, `!check_achievements`.

How to open this PR quickly
---------------------------
Open the following URL in your browser to create the PR with `upload/clean-restructure` as the compare branch:

https://github.com/iamez/slomix/pull/new/upload/clean-restructure

If you prefer to merge `clean-restructure` instead:
- `clean-restructure` exists and was force-updated to the workspace. This branch is currently force-equal to your workspace snapshot.

Post-merge cleanup recommendations
---------------------------------
- Delete the backup branch `upload/clean-restructure` after merge if you no longer need it:
  ```bash
  git push origin --delete upload/clean-restructure
  ```
- Tag the release or create a release note for this major update.

If you want me to:
- Open the PR body on your behalf (I can prepare the text and you can paste it into the PR UI)
- Attempt to create the PR via GitHub API (requires a token)
- Run a smoke test here and summarize the output

Say what you'd like next and I'll proceed. 
