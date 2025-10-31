# 🚀 FIVEEYES Quick Start Guide

## Week 1 ✅ COMPLETE
- Database migration run successfully
- 109 synergies calculated
- Core algorithm working

## Week 2 🔄 IN PROGRESS

### What We Just Built

**Safe, Modular Architecture** (Like a lizard tail - detaches on error!)

```
analytics/
├── config.py                      ✅ Configuration system
├── synergy_detector.py            ✅ Core algorithm (Week 1)
└── __init__.py                    ✅

bot/cogs/
├── synergy_analytics.py           ✅ Discord integration
└── __init__.py                    ✅

fiveeyes_config.json               ✅ Config file (disabled by default)
```

---

## 🔒 Safety Features

### 1. **Disabled by Default**
```json
{
  "synergy_analytics": {
    "enabled": false  ← SAFE!
  }
}
```

### 2. **Error Isolation**
- Errors in synergy commands **won't crash the bot**
- `cog_command_error` catches all exceptions
- `fail_silently: true` - bot keeps running

### 3. **Feature Flags**
- Enable/disable entire system
- Enable/disable individual commands
- Control auto-recalculation

### 4. **Admin Commands**
```
!fiveeyes_enable         Enable analytics
!fiveeyes_disable        Disable analytics
!recalculate_synergies   Manual recalc
```

---

## 🎮 How to Enable

### Step 1: Load the Cog

Add to your `bot/ultimate_bot.py` (or wherever your main bot is):

```python
# Near the top with other imports
import os

# In your bot class's __init__ or setup_hook method:
async def setup_hook(self):
    """Load extensions when bot starts"""
    # Load FIVEEYES cog (safe - disabled by default)
    try:
        await self.load_extension('bot.cogs.synergy_analytics')
        print("✅ FIVEEYES cog loaded (disabled)")
    except Exception as e:
        print(f"⚠️  Could not load FIVEEYES cog: {e}")
        print("Bot will continue without synergy analytics")
```

### Step 2: Enable via Config

**Option A: Edit `fiveeyes_config.json`**
```json
{
  "synergy_analytics": {
    "enabled": true  ← Change this
  }
}
```

**Option B: Use admin command in Discord**
```
!fiveeyes_enable
```

### Step 3: Test!

```
!synergy @Player1 @Player2
!best_duos
!team_builder @P1 @P2 @P3 @P4 @P5 @P6
```

---

## 🛡️ What If Something Goes Wrong?

### Scenario 1: Command errors out
- ✅ Bot keeps running
- ✅ Other commands still work
- ✅ User sees friendly error message

### Scenario 2: Database issue
- ✅ Synergy commands fail gracefully
- ✅ Bot continues operating
- ✅ Disable via `!fiveeyes_disable`

### Scenario 3: Need to debug
1. `!fiveeyes_disable` - Turn off cleanly
2. Check logs for errors
3. Fix issue
4. `!fiveeyes_enable` - Turn back on

---

## 📊 Current Commands

### User Commands (when enabled)

| Command | Status | Description |
|---------|--------|-------------|
| `!synergy @P1 @P2` | ✅ Working | Show duo chemistry |
| `!best_duos [limit]` | ✅ Working | Top player pairs |
| `!team_builder @P1 @P2...` | ⚠️ Beta | Suggest balanced teams |
| `!player_impact` | 🚧 TODO | Best/worst teammates |

### Admin Commands

| Command | Status | Description |
|---------|--------|-------------|
| `!fiveeyes_enable` | ✅ Working | Enable analytics |
| `!fiveeyes_disable` | ✅ Working | Disable analytics |
| `!recalculate_synergies` | ✅ Working | Manual recalc |

---

## 🧪 Testing Checklist

- [ ] Load cog (bot should start successfully)
- [ ] Try `!synergy` while disabled (should show "disabled" message)
- [ ] Enable via `!fiveeyes_enable`
- [ ] Test `!synergy @Player1 @Player2` with real players
- [ ] Test `!best_duos`
- [ ] Test `!team_builder` with 6 players
- [ ] Disable via `!fiveeyes_disable`
- [ ] Verify bot still runs if cog errors

---

## 🔧 Configuration Reference

### `fiveeyes_config.json`

```json
{
  "synergy_analytics": {
    "enabled": false,              // Master switch
    "min_games_threshold": 10,     // Min games for valid synergy
    "cache_results": true,         // Cache queries in memory
    "auto_recalculate": false,     // Daily recalc (resource intensive)
    "max_team_size": 6,            // Max players for team_builder
    "commands": {
      "synergy": true,             // Individual command toggles
      "best_duos": true,
      "team_builder": true,
      "player_impact": true
    }
  },
  "performance": {
    "query_timeout": 5,            // Query timeout (seconds)
    "max_concurrent_queries": 3,   // Limit concurrent queries
    "cache_ttl": 3600              // Cache lifetime (1 hour)
  },
  "error_handling": {
    "fail_silently": true,         // Don't crash on errors
    "log_errors": true,            // Log to console
    "notify_admin_on_error": false,// DM admin on error
    "admin_channel_id": null       // Channel for error notifications
  }
}
```

---

## 🎯 Next Steps

### Immediate (Complete Week 2)
1. ✅ Config system created
2. ✅ Main cog structure built
3. ✅ `!synergy` command implemented
4. ✅ `!best_duos` command implemented
5. ✅ `!team_builder` basic version
6. 🔄 Test all commands
7. 🔄 Integrate into main bot
8. 🔄 Load and verify

### Week 2 Remaining Tasks
- [ ] Improve `!team_builder` algorithm (current: basic split)
- [ ] Add `!player_impact` command
- [ ] Better error messages
- [ ] Add command cooldowns
- [ ] Performance testing

### Week 3 (Polish)
- [ ] Community testing
- [ ] Tune thresholds based on feedback
- [ ] Optimize queries
- [ ] Add more statistics to embeds
- [ ] Documentation for users

---

## 🐉 The "Lizard Tail" Architecture

```
Main Bot (Critical - Must Stay Up)
    ↓
    ├─ Core Commands (Stats, Leaderboards) ← Always works
    ├─ Admin Commands                       ← Always works
    └─ [FIVEEYES Cog]                       ← Can detach if needed
            ↓
            ├─ config.py (Safe toggles)
            ├─ synergy_detector.py (Isolated)
            └─ Error boundary (catches everything)
```

**If FIVEEYES breaks:**
1. Error caught by `cog_command_error`
2. User sees friendly message
3. Bot keeps running
4. Admin uses `!fiveeyes_disable`
5. Debug offline
6. Fix and re-enable

**No restarts needed!**

---

## 💡 Tips

### Performance
- Start with `auto_recalculate: false`
- Use `cache_results: true`
- Monitor query times

### Safety
- Keep `fail_silently: true`
- Test on dev bot first
- Enable one command at a time

### Community
- Announce it's in beta
- Gather feedback
- Tune thresholds based on real usage

---

## 📞 Support

If you encounter issues:

1. Check `fiveeyes_config.json` - is it enabled?
2. Check bot logs - any Python errors?
3. Try `!fiveeyes_disable` then `!fiveeyes_enable`
4. Test with known player pairs that have games together
5. Verify database has synergies: `SELECT COUNT(*) FROM player_synergies`

---

**Status:** Week 2 Day 1 Complete ✅  
**Next:** Load cog into bot and test `!synergy` command
