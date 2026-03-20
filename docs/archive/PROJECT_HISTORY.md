# Project History: How Stats Reached Discord

This document tells the story of the **entire project** (not just the admin page) from the earliest Lua files to a full stats pipeline, database, and Discord-facing commands. It is a narrative summary based on the documentation in `docs/` and session reports.

Sources used:
- `docs/PROJECT_OVERVIEW.md`
- `docs/CHANGELOG.md`
- `docs/SESSION_INDEX.md`
- `docs/TECHNICAL_OVERVIEW.md`
- `docs/SYSTEM_ARCHITECTURE.md`
- `docs/SESSION_2026-01-14_ENDSTATS_FEATURE.md`

---

## Phase 0: Raw Lua Files (No Parser, No Database)

**Problem:** ET:Legacy does not save player stats by default.  
**Initial solution:** Community Lua scripts collected stats and wrote raw files.

- **c0rnp0rn.lua / c0rnp0rn7.lua**  
  Hooks game events (kills, deaths, damage, objectives, timing).  
  Writes `gamestats/*.txt` files on the **game server** only.

- **endstats.lua**  
  Writes `*-endstats.txt` files containing awards and VS stats.

At this stage, **data existed but nobody could read it**. The stats lived on the server as raw text files. There was **no parser, no database, and no Discord output**.

---

## Phase 1: Ingest the Files

**Problem:** Stats files lived on the game server, but the bot runs elsewhere.  
**Solution:** Build ingestion tools to move files to the bot.

Two layers were developed:
- **SSH polling** to fetch new files at intervals (reliable fallback).
- **Webhook-based triggers** later added for near-instant detection.

Result: stats files could finally reach the bot server for processing.

---

## Phase 2: Parse Raw Files into Structured Data

**Problem:** Raw tab files were unreadable and not queryable.  
**Solution:** Build a parser and formal data model.

Key work:
- `community_stats_parser.py` (C0RNP0RN3StatsParser)
  - Extracts player stats + weapon stats.
  - Handles ET:Legacy R2 **cumulative** stats by subtracting R1.
- Initial data was still file-based, but now structured into objects.

Result: we could start storing the data consistently.

---

## Phase 3: Database = "Worldwide" Stats

**Problem:** We needed global history and fast queries.  
**Solution:** Create a database schema and persist every round.

Key tables:
- `rounds`
- `player_comprehensive_stats`
- `weapon_comprehensive_stats`
- `gaming_sessions`

This step allowed:
1. **Persistent history** across servers and seasons.
2. **Fast queryable stats** for Discord commands.

Result: stats could now be queried "worldwide," not just per file.

---

## Phase 4: Discord Commands Become the Frontend

**Problem:** How do players actually see stats?  
**Solution:** Build Discord bot commands as the primary frontend.

Examples:
- `!stats <player>` for lifetime stats
- `!last_session` for the most recent gaming session
- `!leaderboard`, `!session`, `!team_stats`, etc.

Result: Discord became the player-facing UI.

---

## Phase 5: Sessions, Rounds, and Real Meaning

**Problem:** Players think in sessions, not individual rounds.  
**Solution:** Group rounds into sessions automatically.

Key logic:
- Rounds within a time gap threshold belong to the same session.
- Session summaries aggregate multiple rounds into one Discord embed.

Result: `!last_session` became the flagship command.

---

## Phase 6: Auto-Posting (No Human Needed)

**Problem:** Players wanted stats without typing commands.  
**Solution:** Auto-post round summaries right after the round ends.

Key additions:
- Automated monitors (file ingest and round publisher).
- Discord embeds posted automatically after processing.

Result: stats show up in Discord within seconds/minutes automatically.

---

## Phase 7: Endstats Awards and Highlights

**Problem:** Raw stats are useful, but players love awards and highlights.  
**Solution:** Parse `endstats.lua` files and post award embeds.

Implemented in 2026-01-14:
- `endstats_parser.py`
- New DB tables for awards and VS stats
- Award categories (Combat, Deaths, Skills, Teamwork, Objectives, Timing)

Result: Discord posts both **round stats** and **awards**.

---

## Phase 8: Real-Time Timing Accuracy

**Problem:** Timing from gamestats files can be wrong (especially on surrender).  
**Solution:** Real-time Lua webhook with timing metadata.

Added:
- `stats_discord_webhook.lua`
  - RoundStart/End timestamps
  - Warmup and pause tracking
  - Accurate playtime for surrendered rounds

Result: timing data is now **more accurate** than the stats file itself.

---

## Phase 9: Deeper Analytics and Quality Improvements

As the core pipeline stabilized, we added:
- Achievement badges
- Matchup analytics (lineup vs lineup)
- Session playstyle analytics
- Team balance suggestions
- Website frontend integration

These were driven by the same pipeline: **Lua → Parser → DB → Discord/UI**.

---

## Where We Are Now

We now have:
- **Multiple data sources** (gamestats + webhook timing + endstats)
- **Database-backed stats** for long-term history
- **Discord commands and auto-posting** as the primary frontend
- **Advanced analytics** layered on top of the reliable core pipeline

Current known pain points include timing edge cases (time_dead, time_denied), which are being traced back through the Lua → parser → DB pipeline.

---

## Timeline Highlights (Quick View)

Use this alongside `docs/CHANGELOG.md` for details:

- **Late 2025**: Core parser + DB + Discord commands become stable.
- **2025-12-04**: Auto-posting improvements + voice session logging.
- **2026-01-14**: Endstats awards pipeline added.
- **2026-01-22 → 2026-01-27**: Lua webhook timing upgrades.
- **2026-02-01**: Timing fixes + analytics expansion.

---

## What To Read Next

If you want the deep detail for any phase, these docs are the source of truth:

- **Full story of the pipeline:** `docs/PROJECT_OVERVIEW.md`
- **Low-level technical details:** `docs/TECHNICAL_OVERVIEW.md`
- **Session reports by date:** `docs/SESSION_INDEX.md`
- **Change history:** `docs/CHANGELOG.md`
