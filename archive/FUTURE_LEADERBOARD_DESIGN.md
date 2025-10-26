# 🏆 FUTURE FEATURE: LEADERBOARD 2.0
**Status**: 📋 Planned for future implementation  
**Priority**: Medium (after automation system)  
**Estimated Effort**: 4-6 hours

---

## 💡 THE VISION

Create a comprehensive **!lb** (leaderboard) command that ranks players based on a **composite score** that rewards both **combat excellence** AND **team play**.

### Key Requirements:
- 📊 Rank ALL players by composite score
- 📄 Pagination: `!lb`, `!lb 1`, `!lb 2`, `!lb 3` (10 players per page)
- 🥇 Awards/badges for top performers
- ⚖️ Balance individual skill with team contribution

**Important**: `!lb 0` and `!lb 1` both show page 1 (same behavior)

---

## 🎯 SCORING ALGORITHM (Draft)

### What Makes a "Best" Stopwatch Player?

**Combat Skills** (60% weight):
- K/D Ratio (15%)
- DPM - Damage Per Minute (20%)
- Accuracy (10%)
- Headshot % (5%)
- Kill efficiency (10%)

**Team Contribution** (40% weight):
- Survival Rate (deaths per game) (10%) - *Dead players can't help team!*
- Revives given (10%) - *Keeping team alive*
- Kill Assists (5%)
- Objective actions (10%) - *Dynamites, defuses, etc.*
- Gibs (5%) - *Denying enemy revives*

### Formula (Conceptual):
```python
composite_score = (
    # Combat (60%)
    normalize(kd_ratio) * 0.15 +
    normalize(dpm) * 0.20 +
    normalize(accuracy) * 0.10 +
    normalize(headshot_pct) * 0.05 +
    normalize(kill_efficiency) * 0.10 +
    
    # Team Play (40%)
    normalize(survival_rate) * 0.10 +  # Lower deaths/game = better
    normalize(revives_given) * 0.10 +
    normalize(kill_assists) * 0.05 +
    normalize(objective_score) * 0.10 +
    normalize(gibs) * 0.05
) * 1000  # Scale to 0-1000

# Where normalize() scales each stat to 0-1 range
```

---

## 📊 LEADERBOARD DISPLAY

### Example Output:

```
🏆 ET:Legacy Leaderboard - Page 1/5

╔════╦══════════════════╦═══════╦════════════════╗
║ #  ║ Player           ║ Score ║ Stats          ║
╠════╬══════════════════╬═══════╬════════════════╣
║ 🥇 ║ vid              ║  892  ║ 1.46 K/D | 342 DPM
║    ║                  ║       ║ 💀 Kill Leader
╠════╬══════════════════╬═══════╬════════════════╣
║ 🥈 ║ carniee          ║  867  ║ 1.34 K/D | 318 DPM
║    ║                  ║       ║ 🏥 Medic MVP
╠════╬══════════════════╬═══════╬════════════════╣
║ 🥉 ║ .wajs            ║  845  ║ 1.53 K/D | 298 DPM
║    ║                  ║       ║ 🎯 Sharpshooter
╠════╬══════════════════╬═══════╬════════════════╣
║  4 ║ .olz             ║  823  ║ 1.28 K/D | 325 DPM
║  5 ║ endekk           ║  801  ║ 1.19 K/D | 312 DPM
║  6 ║ s&o.lgz          ║  789  ║ 1.42 K/D | 289 DPM
║    ║                  ║       ║ 🛡️ Tank Specialist
║  7 ║ ciril            ║  776  ║ 1.15 K/D | 295 DPM
║  8 ║ bronze.          ║  765  ║ 1.31 K/D | 278 DPM
║  9 ║ Aimless.KaNii    ║  754  ║ 1.08 K/D | 301 DPM
║ 10 ║ squAze           ║  743  ║ 1.22 K/D | 267 DPM
╚════╩══════════════════╩═══════╩════════════════╝

Use !lb 2 for next page
```

---

## 🏅 AWARDS/BADGES SYSTEM

### Top 3 Overall:
- 🥇 **#1** - Gold Medal
- 🥈 **#2** - Silver Medal  
- 🥉 **#3** - Bronze Medal

### Category Leaders:
- 💀 **Kill Leader** - Most total kills
- 🏥 **Medic MVP** - Most revives given
- 🎯 **Sharpshooter** - Highest accuracy
- 🛡️ **Tank Specialist** - Most damage absorbed
- ⚡ **Speed Demon** - Highest DPM
- 🧠 **Tactician** - Most objective actions
- 💪 **Iron Man** - Best survival rate (fewest deaths/game)
- 🤝 **Team Player** - Most assists
- 🎖️ **Veteran** - Most games played
- 🔥 **Hot Streak** - Current best form (last 10 games)

---

## 📄 PAGINATION LOGIC

```python
@commands.command(name='lb', aliases=['leaderboard2'])
async def leaderboard_v2(self, ctx, page: int = 1):
    """🏆 Show competitive leaderboard with rankings
    
    Usage:
    - !lb          → Page 1
    - !lb 1        → Page 1
    - !lb 0        → Page 1 (same as !lb 1)
    - !lb 2        → Page 2
    - !lb 3        → Page 3
    """
    
    # Handle page 0 = page 1
    if page <= 0:
        page = 1
    
    PLAYERS_PER_PAGE = 10
    offset = (page - 1) * PLAYERS_PER_PAGE
    
    # Query ranked players with composite scores
    # ... implementation ...
```

---

## 🔧 IMPLEMENTATION STEPS

### Phase 1: Scoring Algorithm
1. Define normalization functions for each stat
2. Implement composite score calculation
3. Test on current player data
4. Adjust weights based on results

### Phase 2: Database Integration
1. Create `leaderboard_scores` table (optional - can calculate on-the-fly)
2. Add composite score calculation function
3. Add caching for performance (recalculate daily)

### Phase 3: Command Implementation
1. Create `!lb [page]` command
2. Implement pagination (10 per page)
3. Handle edge cases (!lb 0, !lb 999, etc.)

### Phase 4: Awards System
1. Calculate category leaders
2. Assign badges/emojis
3. Display in leaderboard

### Phase 5: Testing & Balancing
1. Review top 20 players
2. Verify scoring makes sense
3. Adjust weights if needed
4. Get community feedback

---

## 🎯 SUCCESS CRITERIA

✅ **Fair Ranking**: Both high-skill fraggers AND dedicated team players rank well  
✅ **Balanced**: No single stat dominates the score  
✅ **Intuitive**: Players understand why they're ranked where they are  
✅ **Motivating**: Encourages both combat improvement AND team play  
✅ **Accurate**: Reflects true player contribution to team success  

---

## 💡 DESIGN CONSIDERATIONS

### Why Survival Rate Matters:
- Dead players can't help their team
- Encourages smart play over reckless fragging
- Rewards players who stay alive and contribute consistently

### Why Revives Matter:
- Medics are crucial in stopwatch mode
- Keeping teammates alive = more firepower
- Rewards support players

### Why DPM Over Raw Damage:
- Accounts for playtime (fair for players who join late)
- Already normalized metric
- Reflects sustained contribution

### Why Composite Score Over Single Stat:
- ET:Legacy is a TEAM game
- Pure fraggers aren't always best players
- Objective-focused players deserve recognition
- Creates more interesting competition

---

## 🚀 FUTURE ENHANCEMENTS

### Leaderboard 3.0 Ideas:
- **Class-specific leaderboards**: Best Medic, Best Engineer, etc.
- **Map-specific rankings**: Who dominates specific maps
- **Seasonal leaderboards**: Monthly/quarterly rankings
- **Clan rankings**: Team-based composite scores
- **Achievement tracking**: Unlock badges over time
- **Skill Rating System**: ELO-style rating based on opponent skill
- **Improvement tracking**: "Most Improved Player" award
- **Consistency rating**: Reward consistent performance over streaky play

---

## 📊 SAMPLE NORMALIZATION LOGIC

```python
def normalize_stat(value, min_val, max_val):
    """Normalize stat to 0-1 range"""
    if max_val == min_val:
        return 0.5
    return (value - min_val) / (max_val - min_val)

def calculate_composite_score(player_stats):
    """Calculate composite leaderboard score"""
    
    # Get min/max for each stat across all players
    all_stats = get_all_player_stats()
    
    # Normalize each component
    kd_norm = normalize_stat(player_stats['kd'], min_kd, max_kd)
    dpm_norm = normalize_stat(player_stats['dpm'], min_dpm, max_dpm)
    # ... etc for all stats
    
    # Apply weights and calculate
    score = (
        kd_norm * 0.15 +
        dpm_norm * 0.20 +
        # ... etc
    ) * 1000
    
    return round(score, 1)
```

---

**Status**: 📋 Design complete - Ready for implementation when prioritized  
**Next Step**: Implement after automation system is complete  
**Estimated Dev Time**: 4-6 hours (including testing and balancing)
