# Code Review Fixes for slomix-bot refactor/configuration-object Branch

You are reviewing and fixing the `refactor/configuration-object` branch of the slomix ET:Legacy Discord bot. The codebase has been refactored from a monolithic structure to a service-oriented architecture. Below are issues identified during code review that need to be addressed.

## Project Context
- **Repository:** slomix-bot (ET:Legacy Discord stats bot)
- **Branch:** refactor/configuration-object
- **Database:** PostgreSQL (migrated from SQLite)
- **Framework:** discord.py with Cogs architecture
- **Key directories:**
  - `bot/services/` - Service layer
  - `bot/services/automation/` - SSH monitoring, health, metrics
  - `bot/core/` - Config, database adapter, core utilities
  - `bot/cogs/` - Discord command handlers

---

## 🔴 CRITICAL FIXES (Do These First)

### 1. SQL Placeholder Inconsistency (PostgreSQL uses $1, $2 not ?)

The codebase has mixed SQL placeholder styles. PostgreSQL requires `$1, $2, $3` style, not `?`.

**Files to check and fix:**

```
bot/services/player_badge_service.py
bot/services/player_display_name_service.py
bot/services/session_data_service.py
bot/services/automation/ssh_monitor.py
bot/services/session_view_handlers.py
```

**Pattern to find:** `WHERE.*= \?` or `IN \(\?\)` or `VALUES.*\?`

**Fix approach - Option A:** If `database_adapter.py` has auto-conversion, verify it works. Check `bot/core/database_adapter.py` for a method that converts `?` to `$1, $2, ...`

**Fix approach - Option B:** Manually replace all `?` with positional `$1, $2, $3` parameters:

```python
# BEFORE (SQLite style):
query = "SELECT * FROM players WHERE guid = ? AND name = ?"
result = await self.db_adapter.fetch_one(query, (guid, name))

# AFTER (PostgreSQL style):
query = "SELECT * FROM players WHERE guid = $1 AND name = $2"
result = await self.db_adapter.fetch_one(query, (guid, name))
```

**Specific locations to fix:**

- `player_badge_service.py` line ~85: `WHERE p.player_guid = ?`
- `player_badge_service.py` line ~142: `WHERE p.player_guid IN ({placeholders})`
- `player_display_name_service.py` lines 44, 55, 65, 95, 115, 145, 175, 195, 215
- `session_data_service.py` lines 35, 54, 75, 95, etc.
- `ssh_monitor.py` line ~385: `WHERE map_name = ?`

For dynamic IN clauses, fix the placeholder generation:
```python
# BEFORE:
placeholders = ",".join("?" * len(player_guids))

# AFTER:
placeholders = ",".join(f"${i+1}" for i in range(len(player_guids)))
```

### 2. Verify Import Paths Work

The automation services import from parent package. Verify these imports work:

```python
# In bot/services/automation/ssh_monitor.py
from bot.services.player_badge_service import PlayerBadgeService
from bot.services.player_display_name_service import PlayerDisplayNameService
```

**Test:** Run `python -c "from bot.services.automation.ssh_monitor import SSHMonitor"` from project root.

If imports fail, either:
- Add `__init__.py` files if missing
- Use relative imports: `from ..player_badge_service import PlayerBadgeService`
- Ensure PYTHONPATH includes project root

---

## 🟡 MODERATE FIXES

### 3. Move Hardcoded Values to Config

**File:** `bot/services/automation/health_monitor.py`

Move these hardcoded values to `bot/config.py` (or wherever BotConfig is defined):

```python
# CURRENT (hardcoded in health_monitor.py):
self.error_threshold = 10
self.ssh_error_threshold = 5
self.db_error_threshold = 5
self.alert_cooldown = 300  # 5 minutes

# SHOULD BE:
self.error_threshold = bot.config.health_error_threshold
self.ssh_error_threshold = bot.config.health_ssh_error_threshold
self.db_error_threshold = bot.config.health_db_error_threshold
self.alert_cooldown = bot.config.health_alert_cooldown
```

**Add to BotConfig class:**
```python
health_error_threshold: int = 10
health_ssh_error_threshold: int = 5
health_db_error_threshold: int = 5
health_alert_cooldown: int = 300
```

**File:** `bot/services/automation/ssh_monitor.py`

The 60-minute session gap is hardcoded:
```python
# Line ~290 area - find and make configurable:
if time_gap_minutes > 60:  # Should be config
```

### 4. Remove Duplicate Badge Logic

**Problem:** Both `player_badge_service.py` and `player_formatter.py` calculate badges with DIFFERENT thresholds.

**File:** `bot/services/player_formatter.py`

The `get_player_badges()` method duplicates logic from `PlayerBadgeService` with different thresholds (50 vs 100 for revives, etc.).

**Fix:** Remove badge calculation from `PlayerFormatter` and use `PlayerBadgeService` instead:

```python
# In player_formatter.py, replace get_player_badges with:
async def get_player_badges(self, player_guid: str, session_stats: Optional[Dict] = None) -> str:
    """Delegate to PlayerBadgeService"""
    from bot.services.player_badge_service import PlayerBadgeService
    badge_service = PlayerBadgeService(self.db_adapter)
    return await badge_service.get_player_badges(player_guid)
```

Or better, inject `PlayerBadgeService` in constructor:
```python
def __init__(self, db_adapter, badge_service: PlayerBadgeService = None):
    self.db_adapter = db_adapter
    self.badge_service = badge_service or PlayerBadgeService(db_adapter)
```

### 5. Add Type Hints to Services

**Files missing return type hints:**
- `bot/services/player_formatter.py`
- `bot/services/session_embed_builder.py`

**Example fixes:**
```python
# player_formatter.py
async def get_player_badges(self, player_guid: str, session_stats: Optional[Dict] = None) -> str:

async def get_display_name(self, player_guid: str, fallback_name: str) -> str:

async def format_player(
    self,
    player_guid: str,
    player_name: str,
    include_badges: bool = True,
    session_stats: Optional[Dict] = None
) -> str:

async def format_players_batch(
    self,
    players: List[Tuple[str, str]],
    include_badges: bool = True
) -> Dict[str, str]:
```

---

## 🟢 MINOR FIXES

### 6. Adjust Logging Levels

**File:** `bot/services/automation/ssh_monitor.py`

Change routine "no new files" log from INFO to DEBUG:
```python
# BEFORE (line ~270 area):
logger.info(f"✓ No new files (checked {len(stats_files)} files)")

# AFTER:
logger.debug(f"✓ No new files (checked {len(stats_files)} files)")
```

### 7. Add Admin Notification Fallback

**File:** `bot/services/automation/ssh_monitor.py`

In `_post_round_stats()`, when production channel is not found, notify admin channel:

```python
async def _post_round_stats(self, filename: str):
    try:
        channel = self.bot.get_channel(self.production_channel_id)

        if not channel:
            logger.error(f"❌ Production channel {self.production_channel_id} not found")
            # ADD: Notify admin channel
            admin_channel = self.bot.get_channel(self.admin_channel_id)
            if admin_channel:
                await admin_channel.send(
                    f"⚠️ **Config Issue:** Production channel {self.production_channel_id} not found. "
                    f"Stats for `{filename}` could not be posted."
                )
            return
```

---

## 📋 VERIFICATION STEPS

After making fixes, run these checks:

```bash
# 1. Syntax check all Python files
python -m py_compile bot/services/automation/ssh_monitor.py
python -m py_compile bot/services/player_badge_service.py
python -m py_compile bot/services/player_display_name_service.py
python -m py_compile bot/services/session_data_service.py

# 2. Test imports work
python -c "from bot.services.automation import SSHMonitor, HealthMonitor, MetricsLogger"
python -c "from bot.services.player_badge_service import PlayerBadgeService"

# 3. Run any existing tests
pytest tests/ -v

# 4. Test database queries work (if you have a test DB)
python -c "
import asyncio
from bot.core.database_adapter import create_adapter
from bot.config import load_config

async def test():
    config = load_config()
    adapter = create_adapter(**config.get_database_adapter_kwargs())
    await adapter.connect()
    result = await adapter.fetch_one('SELECT 1')
    print('DB connection OK:', result)
    await adapter.close()

asyncio.run(test())
"
```

---

## FILES SUMMARY

| File | Priority | Issues |
|------|----------|--------|
| `bot/services/player_badge_service.py` | 🔴 | SQL placeholders |
| `bot/services/player_display_name_service.py` | 🔴 | SQL placeholders |
| `bot/services/session_data_service.py` | 🔴 | SQL placeholders |
| `bot/services/automation/ssh_monitor.py` | 🔴 | SQL placeholders, imports |
| `bot/services/automation/health_monitor.py` | 🟡 | Hardcoded config |
| `bot/services/player_formatter.py` | 🟡 | Duplicate badge logic, type hints |
| `bot/services/session_view_handlers.py` | 🟡 | SQL placeholders, query duplication |
| `bot/config.py` | 🟡 | Add health monitor thresholds |

Start with the 🔴 CRITICAL fixes first, then proceed to 🟡 MODERATE.
