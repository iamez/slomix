# Feature Roadmap 2026

Planned features and enhancements for the Slomix platform.

**Last updated:** 2026-02-15

---

## Greatshot: Demo Cut Tool

**Status:** Planned
**Priority:** High
**Sub-project:** `greatshot/`

### Description

A user-facing tool to cut segments from ET:Legacy demo files (`.dm_84`).

### User Flow

1. Upload a `.dm_84` demo file through the website
2. View the timeline with detected highlights
3. Specify a time range (start/end) for the desired clip
4. Server-side cut extracts the specified segment
5. Download the trimmed `.dm_84` clip

### Future Extension: Render Button

- "Render to video" button on each clip
- Backend queues an offline render job (ET:Legacy client + FFmpeg)
- User receives `.mp4` download when complete
- **Not in initial scope** - requires headless ET:Legacy client setup

### Technical Requirements

- Wire `greatshot/cutter/api.py` to the verified ET:Legacy UDT cutter backend
- Add time-range selection UI in `website/js/greatshot.js`
- Add cut endpoint in `website/backend/routers/greatshot.py`
- Store cut clips in `{GREATSHOT_STORAGE_ROOT}/{demo_id}/clips/`

---

## Proximity: Reaction Time Intel

**Status:** Planned (requires Lua tracker updates)
**Priority:** Medium
**Sub-project:** `proximity/`

### Current State

The "Fastest Reaction" metric currently measures **spawn reaction time** only:

```
time_to_first_move_ms = first_move_time - spawn_time
```

This captures how fast a player starts moving after respawn, but misses tactical reaction metrics.

### New Metrics (Requires Lua Changes)

| Metric | Formula | What It Measures |
|--------|---------|-----------------|
| `time_to_return_fire_ms` | `first_damage_dealt - first_damage_taken` | How quickly player shoots back when hit |
| `dodge_reaction_ms` | `first_direction_change - first_damage_taken` | How quickly player changes direction after taking damage |
| `teammate_support_reaction_ms` | `player_engages_attacker - teammate_under_fire_start` | How quickly player helps a teammate being attacked |

### Lua Tracker Requirements

The proximity Lua tracker (`proximity/lua/proximity_tracker.lua`) needs:

- Hook into `et_Damage()` to capture exact timestamps of damage taken/dealt per player
- Track velocity direction changes (already has position sampling, needs direction delta)
- Cross-reference damage events with nearby teammate engagement timestamps
- Output new fields in the engagement file format

### Database Changes

New columns in `player_track` or new table `player_reaction_metrics`:

- `avg_return_fire_ms` - average time to return fire across round
- `avg_dodge_reaction_ms` - average time to change direction after hit
- `avg_support_reaction_ms` - average time to engage attacker targeting teammate
- Sample counts for each metric

---

## Proximity: UX Improvements

**Status:** Planned
**Priority:** Medium
**Sub-project:** `website/js/proximity.js`

### Rename "Fastest Reaction" to "Spawn Reaction Time"

The current label "Fastest Reaction" is misleading - it suggests reaction to enemy contact, but it measures spawn-to-first-movement time.

- Rename label to "Spawn Reaction Time"
- Add tooltip explaining: "Average time from character spawn to first movement (lower = faster)"
- Keep displaying in milliseconds

### ELI5 Storytelling Explanations

Add plain-language explanations to each analytics card:

| Card | Current | Proposed ELI5 |
|------|---------|---------------|
| Engagement Timeline | Raw chart | "This shows when fights happened during the round. Clusters = intense moments." |
| Crossfire Leaders | Table | "These players coordinate best - they attack the same enemy together." |
| Trade Analysis | Table | "When a teammate dies, could someone have fought back? This shows who trades well." |
| Support Uptime | Percentage | "How much of the round was this player near a teammate? Low = lone wolf." |

### Engagement Inspector Legend

Add a legend/key to the engagement detail view explaining:

- Position path colors (attacker vs target)
- Strafe metrics (turn count, dodge events)
- Crossfire delay interpretation
- Damage breakdown fields

### Trade & Support Detail Boxes

- Name the actual traders in trade events (currently just counts)
- Add expandable detail boxes showing who-traded-whom
- Show support uptime as a mini-timeline (not just a percentage)

### Pagination for Engagements

Replace infinite scroll with paginated table:

- 25 engagements per page
- Sort by: time, duration, damage, crossfire status
- Filter by: player, map, crossfire-only, isolation deaths

---

## Infrastructure Improvements (from Deep Research)

**Status:** Planned (deferred to post-2-week sprint)
**Priority:** Varies

| Item | Priority | Description |
|------|----------|-------------|
| CI/CD pipeline | P0 | GitHub Actions: lint (Ruff) + unit tests + Postgres smoke test |
| Dependency lockfile | P0 | pip-compile with pinned versions for reproducible installs |
| Pre-commit hooks | P1 | Ruff format + lint, trailing whitespace, YAML checks |
| Dependabot | P1 | Automated dependency update PRs |
| Systemd hardening | P1 | ProtectSystem, PrivateTmp, NoNewPrivileges on service units |
| Bot core decomposition | P2 | Break `ultimate_bot.py` (4,990 lines) into focused modules |
| Version single source of truth | P2 | Align README, pyproject.toml, and script versions |

See `docs/reports/deep-research-report.md` for the full industry-baseline audit.
