# Team Suggestion System - Feature Plan

## 🎯 Vision

When players gather in a voice channel before a match, the bot automatically suggests balanced team compositions based on historical synergy data, skill ratings, and player preferences. This happens BEFORE the match starts, giving players time to discuss and vote on team options.

## 🔄 Dynamic Flow

```
Voice Channel Changes → Recalculate → Update Suggestions

[17:08] 6 players join → "Here's 3 balanced 3v3 options"
[17:12] vid leaves    → "5 players now - uneven, waiting..."
[17:14] player7 joins → "6 players! Updated 3v3 suggestions"
[17:15] player8 joins → "7 players - uneven, waiting..."
[17:16] player9 joins → "8 players! Here's 3 balanced 4v4 options"
[17:20] Match starts  → Compare actual vs suggestions → Predict winner
```

## 🧩 Existing Systems to Connect

| System | File | What It Does |
|--------|------|--------------|
| **Synergy Detector** | `analytics/synergy_detector.py` | Calculates how well player pairs perform together |
| **Team Builder** | `bot/cogs/synergy_analytics.py` `_optimize_teams()` | Tries ALL combinations to find most balanced split |
| **Prediction Engine** | `bot/services/prediction_engine.py` | 4-factor weighted match outcome prediction |
| **Voice Session Service** | `bot/services/voice_session_service.py` | Tracks who's in voice channels |
| **Frag Potential** | `bot/core/frag_potential.py` | Player skill classification (Fragger, Medic, Tank, etc.) |

### Existing Commands (Already Work!)
- `!team_builder @P1 @P2 @P3 @P4 @P5 @P6` - Suggests balanced teams
- `!synergy @Player1 @Player2` - Show duo chemistry
- `!best_duos` - Top performing pairs
- `!player_impact` - Best/worst teammates

## 🏗️ New Components Needed

### 1. Voice Channel Hook Enhancement
**File:** `bot/services/voice_session_service.py`

```python
async def on_player_count_change(self, channel, players):
    """Triggered when voice channel membership changes"""
    count = len(players)
    
    # Only trigger for even player counts (potential teams)
    if count >= 4 and count % 2 == 0:
        # Debounce: wait 30 seconds after last change
        await self._schedule_suggestion(channel, players)
    else:
        # Update message to show "waiting for even teams"
        await self._update_waiting_message(channel, count)
```

### 2. Team Suggestion Generator
**File:** `bot/services/team_suggestion_service.py` (NEW)

```python
class TeamSuggestionService:
    async def generate_suggestions(self, player_guids: List[str], count: int = 3):
        """
        Generate N different balanced team suggestions
        
        Uses existing _optimize_teams() but returns top N options
        instead of just the best one
        """
        # Get synergy data for all player pairs
        synergies = await self.synergy_detector.get_pair_synergies(player_guids)
        
        # Get individual skill ratings
        skills = await self.get_player_skills(player_guids)
        
        # Generate all possible team splits
        all_splits = self._enumerate_splits(player_guids)
        
        # Score each split
        scored_splits = []
        for split in all_splits:
            score = self._calculate_balance_score(split, synergies, skills)
            scored_splits.append((split, score))
        
        # Return top N most balanced (with diversity)
        return self._select_diverse_top_n(scored_splits, count)
```

### 3. Suggestion Embed with Reactions
**File:** `bot/services/team_suggestion_embed.py` (NEW)

```
🎮 Team Suggestions (6 players in voice)
Updated: 17:14 • Waiting 30s for more changes...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Option A (Balance: 94% ✨)
🔵 Team 1: bronze, carniee, vid
🔴 Team 2: Cru3lzor, endekk, superboyy
📈 Predicted: 51% - 49% (Very Even!)
Votes: ✅ 3  ❌ 0

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Option B (Balance: 87%)
🔵 Team 1: bronze, Cru3lzor, superboyy  
🔴 Team 2: carniee, endekk, vid
📈 Predicted: 55% - 45%
Votes: ✅ 1  ❌ 2

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Option C (Balance: 82%)
🔵 Team 1: bronze, endekk, vid
🔴 Team 2: carniee, Cru3lzor, superboyy
📈 Predicted: 58% - 42%
Votes: ✅ 0  ❌ 1

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 React with 1️⃣ 2️⃣ 3️⃣ to vote for your preferred option
🔒 Any participant can click [Accept] to lock in teams (requires voice channel presence)
```

### 4. Reaction Handler & Vote Tracker
**File:** `bot/cogs/team_suggestions_cog.py` (NEW)

```python
@commands.Cog.listener()
async def on_raw_reaction_add(self, payload):
    """Track votes on team suggestions"""
    if payload.message_id in self.active_suggestions:
        suggestion = self.active_suggestions[payload.message_id]
        
        if str(payload.emoji) in ['1️⃣', '2️⃣', '3️⃣']:
            option = int(str(payload.emoji)[0])
            await suggestion.add_vote(payload.user_id, option)
            await suggestion.update_embed()
```

### 5. Match Start Detection & Comparison
**File:** Integration with `endstats_monitor`

```python
async def on_match_start(self, teams_from_stats):
    """When actual match starts, compare to suggestions"""
    
    if self.active_suggestion:
        # Check if teams match any suggestion
        match_option = self._find_matching_option(teams_from_stats)
        
        if match_option:
            await self.post_message(
                f"✅ Teams matched **Option {match_option}**! "
                f"Good luck everyone!"
            )
        else:
            # Teams are different - generate prediction for actual teams
            prediction = await self.prediction_engine.predict_match(
                teams_from_stats['team_a'],
                teams_from_stats['team_b']
            )
            await self.post_prediction(prediction)
```

## 📊 Balance Score Algorithm

```python
def calculate_balance_score(team_a, team_b, synergies, skills):
    """
    Calculate how balanced a team split is (0.0 - 1.0)
    
    Factors:
    - Individual skill difference (40%)
    - Team synergy totals (30%)
    - Role diversity (15%)
    - Historical head-to-head (15%)
    """
    
    # 1. Skill difference (want it close to 0)
    skill_a = sum(skills[p] for p in team_a)
    skill_b = sum(skills[p] for p in team_b)
    skill_balance = 1 - abs(skill_a - skill_b) / max(skill_a, skill_b)
    
    # 2. Synergy totals (want similar synergy sums)
    synergy_a = calculate_team_synergy(team_a, synergies)
    synergy_b = calculate_team_synergy(team_b, synergies)
    synergy_balance = min(synergy_a, synergy_b) / max(synergy_a, synergy_b)
    
    # 3. Role diversity (want both teams to have variety)
    roles_a = get_role_distribution(team_a)  # Uses frag_potential.py
    roles_b = get_role_distribution(team_b)
    role_balance = compare_role_diversity(roles_a, roles_b)
    
    # 4. H2H history (avoid lopsided matchups)
    h2h = get_historical_h2h(team_a, team_b)
    h2h_balance = 1 - abs(h2h - 0.5) * 2  # 0.5 = perfectly even history
    
    return (
        skill_balance * 0.40 +
        synergy_balance * 0.30 +
        role_balance * 0.15 +
        h2h_balance * 0.15
    )
```

## 🎛️ Configuration Options

```python
TEAM_SUGGESTIONS_CONFIG = {
    # Trigger conditions
    'min_players': 4,
    'max_players': 12,
    'debounce_seconds': 30,  # Wait after last join/leave
    
    # Suggestions
    'num_suggestions': 3,
    'show_predictions': True,
    'show_synergy_scores': True,
    
    # Voting
    'enable_voting': True,
    'vote_duration_minutes': 10,
    
    # Channels
    'voice_channels': ['Fireteam Triglav'],  # Monitor these
    'post_channel': 'et-stats',  # Post suggestions here
    
    # Admin features
    'allow_accept_button': True,
    'accept_role': 'Admin',
}
```

## 🔌 Integration Points

1. **Voice State Changes** → `voice_session_service.py` already tracks these
2. **Player GUIDs** → `player_links` table maps Discord ID to GUID
3. **Synergy Data** → `analytics/synergy_detector.py` has `calculate_synergy()`
4. **Team Optimization** → `synergy_analytics.py` has `_optimize_teams()`
5. **Predictions** → `prediction_engine.py` has `predict_match()`
6. **Player Skills** → `frag_potential.py` has skill classification

## 📋 Implementation Phases

### Phase 1: Core Infrastructure
- [ ] Create `TeamSuggestionService` class
- [ ] Hook into voice state changes
- [ ] Generate single best suggestion (use existing `_optimize_teams`)

### Phase 2: Multiple Suggestions
- [ ] Modify algorithm to return top N options
- [ ] Create embed with multiple options
- [ ] Add reaction handling for votes

### Phase 3: Smart Features
- [ ] Add prediction for each option
- [ ] Show synergy highlights ("bronze + carniee: 🔥 Excellent duo!")
- [ ] Track which suggestions get followed

### Phase 4: Learning
- [ ] Log actual teams vs suggestions
- [ ] Track match outcomes
- [ ] Improve algorithm based on results

## 🐛 CRITICAL: Current Bugs to Fix First!

### Bug 1: `!last_session` and `!session` Broken
**Error:** `syntax error at or near "{"`

**Error log evidence (2025-12-03):**
```
20:22:12 | ERROR | bot.cogs.last_session | Error in last_session command: syntax error at or near "{"
asyncpg.exceptions.PostgresSyntaxError: syntax error at or near "{"

20:22:52 | ERROR | UltimateBot.SessionCog | Error in session command: syntax error at or near "{"
asyncpg.exceptions.PostgresSyntaxError: syntax error at or near "{"
```

**Root Cause:** Queries use `{placeholder}` but are NOT f-strings - literal `{session_ids_str}` sent to PostgreSQL

**Files Affected:**

| File | Lines | Variables |
|------|-------|-----------|
| `bot/services/session_data_service.py` | 121, 197, 338, 372, 505, 522 | `{session_ids_str}` |
| `bot/cogs/session_cog.py` | 243, 366, 387, 411, 432 | Various `{...}` |

**Fix Required:**
```python
# BEFORE (broken):
query = """
    SELECT * FROM player_comprehensive_stats
    WHERE round_id IN ({session_ids_str})
"""

# AFTER (working):
query = f"""
    SELECT * FROM player_comprehensive_stats
    WHERE round_id IN ({session_ids_str})
"""
```

**Fix locations in `session_data_service.py`:**
- Line 121: `query = """` → `query = f"""`
- Line 197: `query = """` → `query = f"""`
- Line 338: `query = """` → `query = f"""`
- Line 372: `query = """` → `query = f"""`
- Line 505: `query = """` → `query = f"""`
- Line 522: `detail_query = """` → `detail_query = f"""`

**Fix locations in `session_cog.py`:**
- Line 243: `top_players_query = """` → Check if needs `f` prefix
- Lines 366, 387, 411, 432: Check each `query = """` for `{...}` usage

---

## 🚀 Quick Win

The **fastest** way to demo this feature:
1. Fix the f-string bug (so bot works again)
2. Add a `!suggest_teams` command that manually triggers suggestion
3. Connect it to existing `_optimize_teams()` algorithm
4. Later: automate via voice channel detection
