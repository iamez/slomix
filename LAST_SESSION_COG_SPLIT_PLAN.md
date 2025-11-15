# Last Session Cog Splitting Plan

## 📊 Current State

**File**: `bot/cogs/last_session_cog.py`
**Size**: 2,407 lines
**Methods**: 33 total
**Problem**: God Class antipattern - violates Single Responsibility Principle

---

## 🎯 Proposed Split (6 Modules)

### Module 1: `bot/session_views/data_fetcher.py` (~200 lines)
**Responsibility**: Fetch session data from database

**Methods to Extract** (4 methods):
1. Line 43: `_get_latest_session_date()` - Get most recent session date
2. Line 67: `_fetch_session_data()` - Fetch sessions, hardcoded teams, map name
3. Line 129: `_get_hardcoded_teams()` - Get team assignments from team_sessions
4. Line 188: `_ensure_player_name_alias()` - Database compatibility helper

**Dependencies**:
- Needs: `db_adapter`
- Returns: Raw database data (lists, dicts)

---

### Module 2: `bot/session_views/data_aggregator.py` (~450 lines)
**Responsibility**: Aggregate and calculate session statistics

**Methods to Extract** (7 methods):
1. Line 878: `_aggregate_all_player_stats()` - Sum player stats across sessions
2. Line 916: `_aggregate_team_stats()` - Calculate team-level statistics
3. Line 973: `_aggregate_weapon_stats()` - Aggregate weapon usage stats
4. Line 996: `_get_dpm_leaderboard()` - Get top DPM players
5. Line 1015: `_calculate_team_scores()` - Calculate team scores and MVP
6. Line 1048: `_build_team_mappings()` - Map players to teams
7. Line 1206: `_get_team_mvps()` - Get MVP for each team

**Dependencies**:
- Needs: `db_adapter`, session data
- Returns: Aggregated statistics (dicts, lists)

---

### Module 3: `bot/session_views/embed_builder.py` (~350 lines)
**Responsibility**: Build Discord embeds for different views

**Methods to Extract** (6 methods):
1. Line 1273: `_build_session_overview_embed()` - Main overview embed
2. Line 1379: `_build_team_analytics_embed()` - Team performance embed
3. Line 1453: `_build_team_composition_embed()` - Team roster embed
4. Line 1513: `_build_dpm_analytics_embed()` - DPM leaderboard embed
5. Line 1552: `_build_weapon_mastery_embed()` - Weapon stats embed
6. Line 1603: `_build_special_awards_embed()` - Special awards/achievements embed

**Dependencies**:
- Needs: Aggregated data
- Returns: `discord.Embed` objects

---

### Module 4: `bot/session_views/graph_generator.py` (~350 lines)
**Responsibility**: Generate matplotlib graphs

**Methods to Extract** (2 methods):
1. Line 1769: `_generate_performance_graphs()` - Player performance graphs
2. Line 1913: `_generate_combat_efficiency_graphs()` - Combat efficiency graphs

**Dependencies**:
- Needs: Aggregated data, matplotlib, io
- Returns: `io.BytesIO` image buffers

---

### Module 5: `bot/session_views/view_renderer.py` (~800 lines)
**Responsibility**: Render complete views by combining data, embeds, graphs

**Methods to Extract** (9 methods):
1. Line 227: `_show_objectives_view()` - Show objectives/support stats view
2. Line 324: `_show_combat_view()` - Show combat stats view
3. Line 377: `_show_weapons_view()` - Show weapon stats view
4. Line 426: `_show_support_view()` - Show support/revive stats view
5. Line 460: `_show_sprees_view()` - Show killing spree stats view
6. Line 499: `_show_top_view()` - Show top performers view
7. Line 562: `_show_maps_view()` - Show maps summary view
8. Line 703: `_show_maps_full_view()` - Show detailed maps view
9. Line 762: `_send_round_stats()` - Send individual round stats

**Dependencies**:
- Needs: DataFetcher, DataAggregator, EmbedBuilder, GraphGenerator
- Returns: None (sends embeds to Discord channel)

---

### Module 6: `bot/cogs/last_session_cog.py` (~250 lines remaining)
**Responsibility**: Command entry points and orchestration

**Methods to Keep** (5 methods):
1. Line 35: `__init__()` - Initialize cog with bot reference
2. Line 213: `_enable_sql_diag()` - SQL diagnostic toggle
3. Line 218: `_send_last_session_help()` - Send help message
4. Line 2056: `last_session()` - Main command entry point with subcommands
5. Line 2339: `team_history_command()` - Team history command

**Dependencies**:
- Creates instances of all 5 helper modules
- Coordinates between modules
- Handles Discord command routing

---

## 🏗️ Architecture After Split

```
bot/
├── session_views/
│   ├── __init__.py
│   ├── data_fetcher.py        (~200 lines) - Database queries
│   ├── data_aggregator.py     (~450 lines) - Statistics calculation
│   ├── embed_builder.py       (~350 lines) - Discord embed creation
│   ├── graph_generator.py     (~350 lines) - Matplotlib graphs
│   └── view_renderer.py       (~800 lines) - View composition
└── cogs/
    └── last_session_cog.py    (~250 lines) - Command routing

Total: 2,407 lines → 2,400 lines (reorganized)
Cog size: 2,407 → 250 lines (-90% reduction!)
```

---

## 📝 Implementation Strategy

### Phase 1: Extract Independent Modules (Safest)
1. **graph_generator.py** - No dependencies on other modules
2. **data_fetcher.py** - Only depends on database
3. **data_aggregator.py** - Depends on data_fetcher results

### Phase 2: Extract UI Modules
4. **embed_builder.py** - Depends on aggregated data
5. **view_renderer.py** - Depends on all above modules

### Phase 3: Slim Down Cog
6. **last_session_cog.py** - Remove extracted methods, add imports

---

## ⚠️ Risks and Mitigation

### Risk 1: Circular Dependencies
**Mitigation**: Extract in order of dependency (bottom-up)

### Risk 2: Shared State
**Problem**: Methods may share instance variables
**Mitigation**: Pass data explicitly, no shared state

### Risk 3: Discord Context
**Problem**: Methods need `ctx` for sending messages
**Mitigation**: Pass `ctx` as parameter to view_renderer methods

### Risk 4: Database Adapter
**Problem**: Multiple modules need DB access
**Mitigation**: Pass `db_adapter` to constructors

---

## 🧪 Testing Plan

After each module extraction:
1. ✅ Verify imports work: `python3 -c "from bot.session_views import ModuleName"`
2. ✅ Test bot startup: `python3 bot/ultimate_bot.py`
3. ✅ Load all cogs successfully
4. ✅ Test command: `!last_session`
5. ✅ Test subcommands: `!last_session objectives`, `!last_session combat`, etc.
6. ✅ Verify no errors in logs

---

## 📊 Expected Benefits

### Code Quality
- ✅ Each module has single responsibility
- ✅ Clear boundaries between data/logic/presentation
- ✅ Easier to locate and fix bugs

### Testability
- ✅ Can test data fetching independently
- ✅ Can test aggregation logic without database
- ✅ Can test embed building without Discord

### Reusability
- ✅ DataAggregator can be used by other cogs
- ✅ GraphGenerator can create graphs for any data
- ✅ EmbedBuilder can be used for other embeds

### Maintainability
- ✅ 90% reduction in cog file size (2,407 → 250 lines)
- ✅ Each file under 1,000 lines (easy to navigate)
- ✅ Clear module organization

---

## ⏱️ Estimated Effort

| Phase | Task | Time | Risk |
|-------|------|------|------|
| 1a | Extract graph_generator.py | 15 min | Low |
| 1b | Extract data_fetcher.py | 15 min | Low |
| 1c | Extract data_aggregator.py | 20 min | Medium |
| 2a | Extract embed_builder.py | 15 min | Medium |
| 2b | Extract view_renderer.py | 25 min | High |
| 3  | Slim down last_session_cog.py | 20 min | High |
| Test | Full integration testing | 15 min | - |

**Total**: ~125 minutes (~2 hours)

---

## 🚦 Decision Point

**Recommendation**: This is a complex refactoring that requires:
- Careful dependency management
- Extensive testing
- Potential debugging

**Options**:
1. **Proceed Now**: Complete the split in this session (~2 hours)
2. **Plan First**: Create detailed implementation plan, test in separate branch
3. **Incremental**: Extract one module at a time, test between each

**Suggested Approach**: Option 3 (Incremental)
- Safest approach
- Can rollback if issues arise
- Test after each extraction

---

**Status**: Plan Complete | **Ready to Execute**: Yes | **Complexity**: High
