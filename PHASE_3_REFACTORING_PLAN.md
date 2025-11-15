# PHASE 3: Monolith Splitting - Refactoring Plan

## 📊 Current State Analysis

### File Sizes
| File | Lines | Status |
|------|-------|--------|
| `bot/ultimate_bot.py` | 2,687 | ⚠️ Monolith - needs splitting |
| `bot/cogs/last_session_cog.py` | 2,407 | ⚠️ God class - needs splitting |

**Total lines in these 2 files: 5,094 lines**

---

## 🎯 Refactoring Strategy

### A. ultimate_bot.py (2,687 lines)

**Found Issues:**

1. **Duplicate Utility Methods** (lines 358-370)
   - `safe_divide()` - DUPLICATE of `StatsCalculator.safe_divide()`
   - `safe_percentage()` - DUPLICATE of `StatsCalculator.safe_percentage()`
   - `safe_dpm()` - DUPLICATE of `StatsCalculator.calculate_dpm()`

   ✅ **Action**: Remove these methods, replace all calls with `StatsCalculator` methods

2. **SSH/File Operations** (lines 786-914)
   - `ssh_list_remote_files()`
   - `_ssh_list_files_sync()`
   - `ssh_download_file()`
   - `_ssh_download_file_sync()`
   - `parse_gamestats_filename()`

   ✅ **Action**: Extract to `bot/automation/ssh_handler.py`

3. **Stats Processing/Import** (lines 914-1911)
   - `process_gamestats_file()`
   - `post_round_stats_auto()`
   - `_check_and_post_map_completion()`
   - `_post_map_summary()`
   - `_import_stats_to_db()`
   - `_calculate_gaming_session_id()`
   - `_insert_player_stats()`
   - `_update_player_alias()`
   - `post_round_summary()`
   - `post_map_summary()`

   ✅ **Action**: Extract to `bot/automation/stats_importer.py`

4. **File Tracking Logic** (lines 1936-2173)
   - `should_process_file()`
   - `_is_in_processed_files_table()`
   - `_session_exists_in_db()`
   - `_mark_file_processed()`
   - `sync_local_files_to_processed_table()`
   - `_auto_end_session()`

   ✅ **Action**: Extract to `bot/automation/file_tracker.py`

**Keep in ultimate_bot.py:**
- Bot initialization and configuration
- Database validation
- Background tasks (endstats_monitor, cache_refresher, voice_session_monitor)
- Event handlers (on_ready, on_message, on_command, on_command_error)
- Voice session management (needs Discord API access)

**Expected Result:**
- `ultimate_bot.py`: 2,687 → ~800 lines (-70%)
- New modules: ~1,887 lines

---

### B. last_session_cog.py (2,407 lines)

**Found Issues:**

Classic **God Class** antipattern - does everything:
1. Data fetching
2. Data aggregation
3. View rendering
4. Embed building
5. Graph generation
6. Command handling

**Breakdown by Responsibility:**

1. **Data Fetching** (lines 43-188, ~145 lines)
   - `_get_latest_session_date()`
   - `_fetch_session_data()`
   - `_get_hardcoded_teams()`
   - `_ensure_player_name_alias()`

   ✅ **Action**: Extract to `bot/session_views/data_fetcher.py`

2. **Data Aggregation** (lines 878-1273, ~395 lines)
   - `_aggregate_all_player_stats()`
   - `_aggregate_team_stats()`
   - `_aggregate_weapon_stats()`
   - `_get_dpm_leaderboard()`
   - `_calculate_team_scores()`
   - `_build_team_mappings()`
   - `_get_team_mvps()`

   ✅ **Action**: Extract to `bot/session_views/data_aggregator.py`

3. **View Rendering** (lines 227-762, ~535 lines)
   - `_show_objectives_view()`
   - `_show_combat_view()`
   - `_show_weapons_view()`
   - `_show_support_view()`
   - `_show_sprees_view()`
   - `_show_top_view()`
   - `_show_maps_view()`
   - `_show_maps_full_view()`
   - `_send_round_stats()`

   ✅ **Action**: Extract to `bot/session_views/view_renderer.py`

4. **Embed Building** (lines 1273-1603, ~330 lines)
   - `_build_session_overview_embed()`
   - `_build_team_analytics_embed()`
   - `_build_team_composition_embed()`
   - `_build_dpm_analytics_embed()`
   - `_build_weapon_mastery_embed()`
   - `_build_special_awards_embed()`

   ✅ **Action**: Extract to `bot/session_views/embed_builder.py`

5. **Graph Generation** (lines 1769-2287, ~518 lines)
   - `_generate_performance_graphs()`
   - `_generate_combat_efficiency_graphs()`

   ✅ **Action**: Extract to `bot/session_views/graph_generator.py`

6. **Command Entry Points** (lines 2056-2407, ~351 lines)
   - `last_session()` - main command with subcommand routing
   - `team_history_command()`
   - Help text

   ✅ **Action**: Keep in `last_session_cog.py` (coordination only)

**Expected Result:**
- `last_session_cog.py`: 2,407 → ~400 lines (-83%)
- New modules: ~2,000 lines organized by responsibility

---

## 📐 Architecture: Single Responsibility Principle

### Before (Monoliths):
```
ultimate_bot.py (2,687 lines)
├── Bot initialization
├── Database operations
├── SSH operations
├── File tracking
├── Stats import
├── Background tasks
├── Event handlers
└── Voice sessions

last_session_cog.py (2,407 lines)
├── Data fetching
├── Data aggregation
├── View rendering
├── Embed building
├── Graph generation
└── Command handling
```

### After (Modular):
```
bot/
├── ultimate_bot.py (~800 lines)          # Bot core + lifecycle
├── automation/
│   ├── ssh_handler.py (~200 lines)       # SSH operations
│   ├── stats_importer.py (~1,000 lines)  # Stats processing
│   └── file_tracker.py (~700 lines)      # File tracking
├── session_views/
│   ├── data_fetcher.py (~200 lines)      # Data retrieval
│   ├── data_aggregator.py (~400 lines)   # Stats aggregation
│   ├── view_renderer.py (~550 lines)     # View logic
│   ├── embed_builder.py (~350 lines)     # Embed creation
│   └── graph_generator.py (~500 lines)   # Graph generation
└── cogs/
    └── last_session_cog.py (~400 lines)  # Command coordination
```

---

## ✅ Benefits

### 1. **Maintainability**
- Each module has a single, clear responsibility
- Easier to locate and fix bugs
- Reduced cognitive load when reading code

### 2. **Testability**
- Can test SSH operations independently
- Can test stats import without Discord bot
- Can test data aggregation without database

### 3. **Reusability**
- SSH handler can be used by other automation tasks
- Data aggregator can be used by other cogs
- Graph generator can be used for different visualizations

### 4. **Performance**
- Smaller modules load faster
- Easier to identify performance bottlenecks
- Can optimize individual modules

### 5. **Team Development**
- Multiple developers can work on different modules
- Reduced merge conflicts
- Clear ownership boundaries

---

## 🔧 Implementation Order

### Step 1: Remove Duplicate Utilities (Quick Win)
- Replace `self.safe_*` methods with `StatsCalculator.*` in ultimate_bot.py
- Remove duplicate methods
- **Time**: 10 minutes
- **Risk**: Low (StatsCalculator already tested)

### Step 2: Extract SSH Handler
- Create `bot/automation/ssh_handler.py`
- Move SSH methods
- Update ultimate_bot.py to use handler
- **Time**: 20 minutes
- **Risk**: Low (self-contained module)

### Step 3: Extract Stats Importer
- Create `bot/automation/stats_importer.py`
- Move stats processing methods
- Update ultimate_bot.py to use importer
- **Time**: 30 minutes
- **Risk**: Medium (complex logic)

### Step 4: Extract File Tracker
- Create `bot/automation/file_tracker.py`
- Move file tracking methods
- Update ultimate_bot.py to use tracker
- **Time**: 20 minutes
- **Risk**: Low (self-contained module)

### Step 5: Split LastSessionCog
- Create `bot/session_views/` directory
- Extract modules in order:
  1. `data_fetcher.py`
  2. `data_aggregator.py`
  3. `embed_builder.py`
  4. `graph_generator.py`
  5. `view_renderer.py` (depends on all above)
- Slim down `last_session_cog.py` to coordination only
- **Time**: 60 minutes
- **Risk**: Medium (many interdependencies)

---

## 🧪 Testing Strategy

After each step:
1. ✅ Start bot: `python3 bot/ultimate_bot.py`
2. ✅ Test command: `!last_session`
3. ✅ Test stats import (if automation enabled)
4. ✅ Check logs for errors

**Total Implementation Time**: ~140 minutes (~2.5 hours)

---

## 📊 Expected Metrics

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Largest file | 2,687 lines | ~800 lines | -70% |
| Modules < 1000 lines | 0 of 2 | 9 of 11 | +900% |
| Average module size | 2,547 lines | ~340 lines | -87% |
| Total lines | 5,094 | 5,094 | 0% (just reorganized) |
| Modules following SRP | 0% | 100% | +100% |

---

## 🎯 Success Criteria

1. ✅ No file exceeds 1,000 lines
2. ✅ Each module has single responsibility
3. ✅ All existing commands work
4. ✅ No performance degradation
5. ✅ Bot starts without errors
6. ✅ All cogs load successfully
7. ✅ Code is more maintainable (subjective but measurable via developer feedback)

---

**Status**: Ready to execute
**Start Date**: 2025-11-14
**Estimated Completion**: 2025-11-14 (same day)
