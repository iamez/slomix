# 🎯 FIVEEYES PROJECT - Master Plan
## ET:Legacy Player Synergy & Team Chemistry Analytics System

**Project Codename:** FIVEEYES  
**Start Date:** October 6, 2025  
**Estimated Duration:** 8 weeks  
**Status:** Planning Phase  

---

## 🌟 Executive Summary

Transform your ET:Legacy community stats bot from basic stat tracking into an **advanced esports analytics platform** that detects player chemistry, team synergy, and individual impact beyond raw numbers.

### The Problem
- Engineers don't get credit (low K/D but critical objective work)
- Stats don't show teamwork, support play, or "game sense"
- Can't identify which player combinations work best
- Team balancing is manual and subjective

### The Solution
A **3-phase analytics system** that:
1. **Detects player synergy** using 2 years of historical data
2. **Normalizes performance** across roles (medic ≠ engineer ≠ soldier)
3. **Tracks proximity & teamwork** via enhanced Lua scripting

### Expected Outcomes
- 📊 **Synergy scores** for all player pairs (win rate boost, performance boost)
- 🏆 **Fair leaderboards** that value engineers and support players
- 🤝 **Team recommendations** based on chemistry analysis
- 🎮 **Crossfire detection** and positioning analytics (Phase 3)

---

## 🎯 Project Goals

### Primary Goals
1. ✅ Identify which players perform better together
2. ✅ Create role-normalized performance metrics
3. ✅ Build automated team balancing recommendations
4. ✅ Detect support play and teamwork patterns

### Secondary Goals
1. 🎯 Track proximity during combat (crossfire setups)
2. 🎯 Detect "team player" traits beyond stats
3. 🎯 Predict match outcomes based on team composition
4. 🎯 Visualize synergy networks

### Success Criteria
- **Community adoption**: Players use `!synergy` and `!team_builder` regularly
- **Fairness**: Engineers/support players recognized in leaderboards
- **Accuracy**: Synergy predictions correlate with actual performance (>70%)
- **Performance**: All queries respond in <2 seconds

---

## 📋 Three-Phase Implementation

### **Phase 1: Synergy Detection** (Weeks 1-3)
**Status:** Ready to Start  
**Complexity:** ⭐⭐ Medium  
**Dependencies:** None (uses existing data)

**What:**
- Analyze 2 years of historical data
- Calculate performance when players team together vs apart
- Detect win rate correlations
- Identify class synergies (engineer + medic pairs)

**Deliverables:**
- New Discord commands: `!synergy`, `!best_duos`, `!team_builder`
- Database queries optimized for synergy analysis
- Initial synergy scores for all player pairs (20-30 players)

**Risk Level:** 🟢 Low (Python-only, no server changes)

---

### **Phase 2: Role Normalization** (Weeks 4-5)
**Status:** Planned  
**Complexity:** ⭐⭐ Medium  
**Dependencies:** Phase 1 complete

**What:**
- Define role-specific performance weights
- Create normalized scoring system
- Update leaderboards to use fair metrics
- Add per-class/per-map ratings

**Deliverables:**
- Updated `!leaderboard` command (role-normalized)
- New commands: `!best_engineers`, `!best_medics`, `!class_stats`
- Performance score algorithm
- Role weight tuning based on community feedback

**Risk Level:** 🟡 Medium (requires community validation)

---

### **Phase 3: Proximity Tracking** (Weeks 6-8) 
**Status:** Optional  
**Complexity:** ⭐⭐⭐⭐ High  
**Dependencies:** Phase 1 + 2 complete, Lua expertise required

**What:**
- Enhanced Lua script to track player positions
- Detect crossfire setups (teammates near during combat)
- Log support positioning (medic near teammates)
- Export proximity data in stats files

**Deliverables:**
- Updated `c0rnp0rn3.lua` with proximity tracking
- New stats parser for proximity data
- Commands: `!teamwork_score`, `!crossfire_stats`
- Proximity visualization tools

**Risk Level:** 🔴 High (server performance, Lua complexity)

---

## 🗄️ Database Changes

### New Tables Required

#### `player_ratings` (Phase 2)
```sql
CREATE TABLE player_ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_guid TEXT NOT NULL,
    overall_rating REAL DEFAULT 1500,
    medic_rating REAL DEFAULT 1500,
    engineer_rating REAL DEFAULT 1500,
    soldier_rating REAL DEFAULT 1500,
    fieldops_rating REAL DEFAULT 1500,
    covert_rating REAL DEFAULT 1500,
    rating_confidence REAL DEFAULT 1.0,
    games_played INTEGER DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_guid)
);
```

#### `player_synergies` (Phase 1)
```sql
CREATE TABLE player_synergies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_a_guid TEXT NOT NULL,
    player_b_guid TEXT NOT NULL,
    games_together INTEGER DEFAULT 0,
    games_same_team INTEGER DEFAULT 0,
    games_opposite_team INTEGER DEFAULT 0,
    win_rate_together REAL DEFAULT 0,
    win_rate_apart REAL DEFAULT 0,
    win_rate_boost REAL DEFAULT 0,
    avg_performance_together REAL DEFAULT 0,
    avg_performance_apart REAL DEFAULT 0,
    performance_boost REAL DEFAULT 0,
    synergy_score REAL DEFAULT 0,
    confidence_level REAL DEFAULT 0,
    last_played_together TEXT,
    UNIQUE(player_a_guid, player_b_guid)
);
```

#### `proximity_events` (Phase 3 - Optional)
```sql
CREATE TABLE proximity_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    player_a_guid TEXT NOT NULL,
    player_b_guid TEXT NOT NULL,
    time_near_seconds REAL DEFAULT 0,
    shared_kills INTEGER DEFAULT 0,
    support_actions INTEGER DEFAULT 0,
    combat_proximity_seconds REAL DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
```

### Table Modifications
- ✅ No changes to existing tables (backward compatible)
- ✅ All new tables are additive only
- ✅ Migration scripts provided

---

## 🤖 Bot Architecture Changes

### New Cog: `SynergyAnalytics`
```python
# bot/ultimate_bot.py - Add new Cog

class SynergyAnalytics(commands.Cog):
    """Player chemistry and team synergy analysis"""
    
    # Phase 1 Commands
    @commands.command(name='synergy')
    async def calculate_synergy(...)
    
    @commands.command(name='best_duos')
    async def show_best_duos(...)
    
    @commands.command(name='team_builder')
    async def suggest_teams(...)
    
    @commands.command(name='player_impact')
    async def show_player_impact(...)
    
    # Phase 2 Commands
    @commands.command(name='class_stats')
    async def show_class_stats(...)
    
    @commands.command(name='best_engineers')
    async def show_best_engineers(...)
    
    # Phase 3 Commands (optional)
    @commands.command(name='teamwork_score')
    async def show_teamwork_score(...)
```

### New Module: `analytics/`
```
analytics/
├── __init__.py
├── synergy_detector.py      # Core synergy algorithm
├── performance_normalizer.py # Role weighting system
├── rating_calculator.py     # ELO/TrueSkill implementation
├── team_builder.py          # Team composition optimizer
└── statistical_utils.py     # Confidence intervals, etc.
```

---

## 📊 Data Requirements

### What You Have (✅ Ready)
- ✅ 2 years of historical stats files
- ✅ 12,414+ player records in database
- ✅ Team composition tracking (`session_teams` table)
- ✅ 53 stat fields per player per session
- ✅ Weapon stats, objective stats, advanced metrics

### What You Need
- 🔧 Synergy calculation queries (Phase 1)
- 🔧 Role weight definitions (Phase 2)
- 🔧 Enhanced Lua script (Phase 3 - optional)

### Sample Size Analysis
- **Current players:** ~20-30 active
- **Sessions per week:** ~3-5 (2-4 hours each)
- **Player combinations (3v3):** ~60-90 pairs
- **Minimum games for synergy:** 10+ together
- **Statistical confidence:** Achievable after 2-3 months

---

## ⚠️ Risk Assessment

### High Risks 🔴
1. **Phase 3 Lua Performance**
   - Tracking all player positions may cause lag
   - Mitigation: Only track during key events, not every frame
   
2. **Sample Size Issues**
   - Small community = limited data per player pair
   - Mitigation: Set minimum game thresholds, confidence intervals

### Medium Risks 🟡
3. **Role Weight Subjectivity**
   - Community may disagree on engineer vs medic value
   - Mitigation: Make weights configurable, gather feedback
   
4. **Database Query Performance**
   - Complex synergy calculations may be slow
   - Mitigation: Indexed queries, caching, background tasks

### Low Risks 🟢
5. **Backward Compatibility**
   - New tables won't break existing bot
   - Mitigation: All changes are additive

---

## 📈 Performance Estimates

### Query Performance Targets
- `!synergy @player1 @player2` - < 1 second
- `!best_duos` (top 10) - < 2 seconds
- `!team_builder` (6 players) - < 3 seconds
- Background synergy calculation (all pairs) - < 30 seconds

### Database Growth
- `player_synergies`: ~400-900 rows (n*(n-1)/2 pairs for 30 players)
- `player_ratings`: ~30 rows (one per player)
- `proximity_events`: ~1000 rows per session (Phase 3 only)

### Server Performance (Phase 3)
- Proximity check overhead: ~5-10% CPU increase
- Memory footprint: +10-20 MB
- Acceptable if checking every 1000ms (not every frame)

---

## 🛠️ Development Environment

### Required Tools
- ✅ Python 3.11+ (already have)
- ✅ SQLite (already have)
- ✅ Discord.py (already have)
- 🔧 `trueskill` library (Phase 2) - `pip install trueskill`
- 🔧 `numpy`/`pandas` (optional for advanced analytics)

### Testing Strategy
1. **Unit tests** for synergy algorithm
2. **Integration tests** with sample data
3. **Community beta** (Phase 1 first, gather feedback)
4. **Performance profiling** before Phase 3

---

## 📚 Documentation Structure

```
fiveeyes/
├── 00_MASTER_PLAN.md                    # This file
├── 01_PHASE1_SYNERGY_DETECTION.md       # Week 1-3 implementation
├── 02_PHASE2_ROLE_NORMALIZATION.md      # Week 4-5 implementation
├── 03_PHASE3_PROXIMITY_TRACKING.md      # Week 6-8 implementation (optional)
├── 04_DATABASE_SCHEMA.md                # All new tables + migrations
├── 05_API_REFERENCE.md                  # All new commands + methods
├── 06_ALGORITHM_SPECIFICATIONS.md       # Math behind synergy scores
├── 07_TECHNICAL_PREDICTIONS.md          # Performance, risks, bottlenecks
└── 08_TESTING_GUIDE.md                  # How to validate everything
```

---

## 🚀 Quick Start (Phase 1)

### Week 1: Setup
1. ✅ Read all blueprint documents
2. ✅ Create `player_synergies` table
3. ✅ Write synergy detection queries
4. ✅ Test with sample player pairs

### Week 2: Implementation
1. ✅ Add `SynergyAnalytics` Cog
2. ✅ Implement `!synergy` command
3. ✅ Calculate synergy for all existing player pairs
4. ✅ Test with community members

### Week 3: Polish
1. ✅ Add `!best_duos` and `!team_builder`
2. ✅ Optimize query performance
3. ✅ Create Discord embeds (pretty output)
4. ✅ Deploy to production

---

## 🎯 Success Metrics

### Phase 1 Success
- ✅ All player pairs have synergy scores
- ✅ Commands respond in <2 seconds
- ✅ Community uses commands regularly (5+ times/day)
- ✅ Synergy predictions are accurate (subjective validation)

### Phase 2 Success
- ✅ Engineers appear in top 10 leaderboards
- ✅ Community agrees scores are "fair"
- ✅ Class-specific leaderboards active

### Phase 3 Success (Optional)
- ✅ Proximity data collected without lag
- ✅ Crossfire detection works accurately
- ✅ No server performance degradation

---

## 📞 Decision Points

### After Phase 1 (Week 3)
**Question:** Is synergy detection valuable? Does it match reality?  
**If YES:** Proceed to Phase 2  
**If NO:** Revise algorithm, adjust weights, gather more data

### After Phase 2 (Week 5)
**Question:** Are role-normalized scores accepted by community?  
**If YES:** Consider Phase 3  
**If NO:** Iterate on weights, gather feedback

### Before Phase 3 (Week 6)
**Question:** Is proximity tracking worth the complexity?  
**If YES:** Implement Lua changes carefully  
**If NO:** Stop at Phase 2, you already have valuable analytics

---

## 🎓 Learning Resources

### Recommended Reading
- TrueSkill algorithm: https://www.microsoft.com/en-us/research/project/trueskill-ranking-system/
- ET:Legacy Lua API: https://github.com/etlegacy/etlegacy/wiki/Lua
- Discord.py pagination: https://discordpy.readthedocs.io/

### Code References
- Existing bot: `bot/ultimate_bot.py` (study command structure)
- Existing parser: `bot/community_stats_parser.py` (study data extraction)
- Lua script: `c0rnp0rn3.lua` (study stat collection)

---

## 🎉 Next Steps

1. **Read all blueprint documents** in `fiveeyes/`
2. **Start with Phase 1** (safest, highest value)
3. **Test early and often** with real data
4. **Gather community feedback** after each phase
5. **Iterate based on results** before moving forward

---

**Last Updated:** October 6, 2025  
**Status:** 📋 Planning Complete - Ready to Build  
**Next:** Read `01_PHASE1_SYNERGY_DETECTION.md` to start implementation
