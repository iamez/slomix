# 🔧 Bot Refactoring Plan - Split the 9,587-Line Monster

**Goal:** Transform `ultimate_bot.py` from a 9,587-line monolith into a clean, modular architecture.

---

## 📊 Current State Analysis

### File Size Breakdown (estimated):
```
ultimate_bot.py (9,587 lines):
  - Imports & Setup:          ~50 lines
  - StatsCache class:         ~100 lines
  - SeasonManager class:      ~150 lines
  - AchievementSystem class:  ~200 lines
  - ETLegacyCommands (Cog):   ~6,000 lines
    - Stats commands:         ~1,500 lines
    - Round commands:       ~800 lines
    - Admin commands:         ~1,200 lines
    - Link commands:          ~1,500 lines
    - Helper methods:         ~1,000 lines
  - UltimateETLegacyBot:      ~2,500 lines
    - Database setup:         ~200 lines
    - SSH operations:         ~600 lines
    - File monitoring:        ~800 lines
    - Voice tracking:         ~400 lines
    - Background tasks:       ~500 lines
  - Helper functions:         ~500 lines
```

---

## 🎯 Target Architecture

```
bot/
├── __init__.py
├── ultimate_bot.py              # Main bot class (300 lines)
│
├── cogs/                        # Discord command groups
│   ├── __init__.py
│   ├── stats_cog.py            # !stats, !leaderboard, !compare
│   ├── session_cog.py          # !last_round, !sessions, !session_start/end
│   ├── admin_cog.py            # Server management commands
│   └── link_cog.py             # !link, !unlink, player linking
│
├── core/                        # Business logic
│   ├── __init__.py
│   ├── cache.py                # StatsCache
│   ├── seasons.py              # SeasonManager
│   ├── achievements.py         # AchievementSystem
│   └── database.py             # Database helper methods
│
├── services/                    # External integrations
│   ├── __init__.py
│   ├── ssh_service.py          # SSH operations
│   ├── monitoring_service.py   # File monitoring
│   └── parser_service.py       # Wrapper for community_stats_parser
│
├── utils/                       # Utilities
│   ├── __init__.py
│   ├── formatters.py           # Discord embed formatting
│   ├── validators.py           # Input validation
│   └── helpers.py              # Misc helper functions
│
└── community_stats_parser.py   # (existing file - keep as is)
```

---

## 📝 Step-by-Step Refactoring Process

### Phase 1: Extract Core Classes (Day 1)

#### Step 1.1: Extract StatsCache
**File:** `bot/core/cache.py`

```python
#!/usr/bin/env python3
"""
Statistics caching system for high-performance query optimization.
"""
import logging
from datetime import datetime
from typing import Any, Optional, Dict

logger = logging.getLogger("StatsCache")

class StatsCache:
    """
    High-performance caching system for database queries.
    Reduces repeated queries by 80% during active sessions.
    """
    
    def __init__(self, ttl_seconds: int = 300):
        self.cache: Dict[str, Any] = {}
        self.timestamps: Dict[str, datetime] = {}
        self.ttl = ttl_seconds
        logger.info(f"📦 StatsCache initialized (TTL: {ttl_seconds}s)")

    def get(self, key: str) -> Optional[Any]:
        """Get cached value if still valid, None otherwise"""
        if key in self.cache:
            age = (datetime.now() - self.timestamps[key]).total_seconds()
            if age < self.ttl:
                logger.debug(f"✅ Cache HIT: {key} (age: {age:.1f}s)")
                return self.cache[key]
            else:
                logger.debug(f"⏰ Cache EXPIRED: {key} (age: {age:.1f}s)")
                del self.cache[key]
                del self.timestamps[key]
        return None

    def set(self, key: str, value: Any) -> None:
        """Store value in cache with current timestamp"""
        self.cache[key] = value
        self.timestamps[key] = datetime.now()
        logger.debug(f"💾 Cache SET: {key} (total keys: {len(self.cache)})")

    def clear(self) -> int:
        """Clear all cached data and return number of keys cleared"""
        count = len(self.cache)
        self.cache.clear()
        self.timestamps.clear()
        logger.info(f"🗑️  Cache CLEARED: {count} keys removed")
        return count

    def stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        total = len(self.cache)
        expired = sum(
            1 for k in self.cache 
            if (datetime.now() - self.timestamps[k]).total_seconds() >= self.ttl
        )
        return {
            "total_keys": total,
            "valid_keys": total - expired,
            "expired_keys": expired,
            "ttl_seconds": self.ttl,
        }
```

**Update ultimate_bot.py:**
```python
# Old
class StatsCache:
    # ... 100 lines ...

# New
from bot.core.cache import StatsCache
```

#### Step 1.2: Extract SeasonManager
**File:** `bot/core/seasons.py`

```python
#!/usr/bin/env python3
"""
Seasonal competition system with quarterly resets.
"""
from datetime import datetime
from typing import Dict, Tuple, Optional

class SeasonManager:
    """
    Manages quarterly competitive seasons with leaderboard resets.
    Q1: Jan-Mar, Q2: Apr-Jun, Q3: Jul-Sep, Q4: Oct-Dec
    """
    
    def __init__(self):
        self.seasons = {
            1: {"name": "Season 1: Winter Warriors", "months": (1, 2, 3)},
            2: {"name": "Season 2: Spring Assault", "months": (4, 5, 6)},
            3: {"name": "Season 3: Summer Siege", "months": (7, 8, 9)},
            4: {"name": "Season 4: Autumn Advance", "months": (10, 11, 12)},
        }
        
    def get_current_season(self) -> int:
        """Get current season ID (1-4)"""
        month = datetime.now().month
        return (month - 1) // 3 + 1
        
    def get_season_name(self, season_id: Optional[int] = None) -> str:
        """Get season name"""
        if season_id is None:
            season_id = self.get_current_season()
        return self.seasons.get(season_id, {}).get("name", "Unknown Season")
        
    # ... rest of methods ...
```

#### Step 1.3: Extract AchievementSystem
**File:** `bot/core/achievements.py`

```python
#!/usr/bin/env python3
"""
Player achievement and milestone tracking system.
"""
import logging
from typing import List, Dict, Any, Optional
import discord

logger = logging.getLogger("Achievements")

class AchievementSystem:
    """
    Tracks player milestones and awards achievements.
    """
    
    def __init__(self, bot):
        self.bot = bot
        self.achievements = {
            "first_kill": {
                "name": "🎯 First Blood",
                "description": "Get your first kill",
                "check": lambda stats: stats.get("kills", 0) >= 1,
            },
            # ... rest of achievements ...
        }
    
    async def check_player_achievements(
        self, 
        player_guid: str, 
        channel: Optional[discord.TextChannel] = None
    ) -> List[Dict[str, Any]]:
        """Check and award new achievements for a player"""
        # ... implementation ...
```

---

### Phase 2: Extract Command Cogs (Day 2-3)

#### Step 2.1: Extract Stats Commands
**File:** `bot/cogs/stats_cog.py`

```python
#!/usr/bin/env python3
"""
Statistics and leaderboard commands for ET:Legacy bot.
"""
import discord
from discord.ext import commands
import logging

logger = logging.getLogger("StatsCog")

class StatsCog(commands.Cog):
    """Commands for viewing player statistics and leaderboards"""
    
    def __init__(self, bot):
        self.bot = bot
        
    @commands.command(name="stats")
    async def stats(self, ctx, *, player_name: str = None):
        """Display comprehensive player statistics"""
        # Move stats command logic here
        # ... implementation ...
        
    @commands.command(name="leaderboard")
    async def leaderboard(self, ctx, stat_type: str = "kills", page: int = 1):
        """Display leaderboards for various statistics"""
        # Move leaderboard command logic here
        # ... implementation ...
        
    @commands.command(name="compare")
    async def compare(self, ctx, player1: str, player2: str):
        """Compare two players' statistics"""
        # Move compare command logic here
        # ... implementation ...

async def setup(bot):
    """Required setup function for cogs"""
    await bot.add_cog(StatsCog(bot))
```

#### Step 2.2: Extract Session Commands ⭐ ENHANCED!
**File:** `bot/cogs/session_cog.py`

**NOTE:** The `!last_round` command is HUGE and deserves special attention.
See **LAST_SESSION_REDESIGN.md** for the complete redesign plan!

```python
#!/usr/bin/env python3
"""
Game session management commands.

This cog handles the complex !last_round command with multiple views:
- Overview: Quick summary
- Maps: Map-level aggregation with graphs
- Rounds: Round-by-round breakdown  
- Graphs: Statistical analysis with charts

A "session" is all games played in one day (with 1-hour grace period
after midnight for late-night gaming).
"""
import discord
from discord.ext import commands
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger("SessionCog")

class SessionCog(commands.Cog):
    """Commands for managing and viewing game sessions"""
    
    def __init__(self, bot):
        self.bot = bot
        
    # ================================================================
    # MAIN COMMAND: !last_round (with subcommands)
    # ================================================================
    
    @commands.command(name="last_round")
    async def last_round(self, ctx, subcommand: str = None):
        """
        Display the most recent gaming session.
        
        Usage:
            !last_round              - Quick overview
            !last_round overview     - Same as default
            !last_round maps         - Map summaries + graphs
            !last_round rounds       - Round-by-round details
            !last_round graphs       - Statistical analysis
        """
        # Route to appropriate subcommand handler
        if subcommand is None or subcommand.lower() == "overview":
            await self._last_session_overview(ctx)
        elif subcommand.lower() == "maps":
            await self._last_session_maps(ctx)
        elif subcommand.lower() == "rounds":
            await self._last_session_rounds(ctx)
        elif subcommand.lower() == "graphs":
            await self._last_session_graphs(ctx)
        else:
            await ctx.send(f"❌ Unknown option: `{subcommand}`")
    
    async def _last_session_overview(self, ctx):
        """Quick summary with navigation menu"""
        # Move overview logic here (simplified version)
        pass
        
    async def _last_session_maps(self, ctx):
        """Map-level view with performance graphs"""
        # Aggregate by map, show stats + graphs
        pass
        
    async def _last_session_rounds(self, ctx):
        """Detailed round-by-round breakdown"""
        # Show each round individually
        pass
        
    async def _last_session_graphs(self, ctx):
        """Statistical analysis with matplotlib charts"""
        # Generate comprehensive graphs
        pass
    
    # ================================================================
    # OTHER SESSION COMMANDS
    # ================================================================
        
    @commands.command(name="rounds")
    async def list_sessions(self, ctx, *, month: str = None):
        """List past gaming sessions"""
        # Move logic here
        
    @commands.command(name="session_start")
    @commands.has_permissions(administrator=True)
    async def session_start(self, ctx, *, map_name: str = "Unknown"):
        """Manually start a gaming session"""
        # Move logic here
        
    @commands.command(name="session_end")
    @commands.has_permissions(administrator=True)
    async def session_end(self, ctx):
        """Manually end the current gaming session"""
        # Move logic here
    
    # ================================================================
    # HELPER METHODS
    # ================================================================
    
    async def _get_latest_session_data(self) -> Optional[Dict]:
        """
        Fetch most recent session (one day worth of games).
        Includes 1-hour grace period after midnight.
        """
        pass
    
    async def _aggregate_by_map(self, rounds: List[Dict]) -> List[Dict]:
        """Group rounds by map and calculate totals"""
        pass
    
    async def _create_map_graph(self, map_data: Dict) -> discord.File:
        """Generate map performance chart"""
        pass
    
    # ... more helpers ...

async def setup(bot):
    await bot.add_cog(SessionCog(bot))
```

**📖 See LAST_SESSION_REDESIGN.md** for:
- Complete command examples
- Graph layouts
- Round definition logic
- Implementation details

#### Step 2.3: Extract Link Commands
**File:** `bot/cogs/link_cog.py`

```python
#!/usr/bin/env python3
"""
Player linking system for Discord-to-game account association.
"""
import discord
from discord.ext import commands

class LinkCog(commands.Cog):
    """Commands for linking Discord accounts to game profiles"""
    
    def __init__(self, bot):
        self.bot = bot
        
    @commands.command(name="link")
    async def link(self, ctx, target: str = None, *, guid: str = None):
        """Link your Discord account to your in-game profile"""
        # Move logic here
        
    @commands.command(name="unlink")
    async def unlink(self, ctx):
        """Unlink your Discord account from your game profile"""
        # Move logic here

async def setup(bot):
    await bot.add_cog(LinkCog(bot))
```

---

### Phase 3: Extract Services (Day 4)

#### Step 3.1: SSH Service
**File:** `bot/services/ssh_service.py`

```python
#!/usr/bin/env python3
"""
SSH service for remote file operations and server management.
"""
import paramiko
import logging
from typing import List, Optional, Dict
from pathlib import Path

logger = logging.getLogger("SSHService")

class SSHService:
    """Handles SSH connections and file operations"""
    
    def __init__(self, config: Dict[str, str]):
        self.config = config
        self.client: Optional[paramiko.SSHClient] = None
        
    async def connect(self) -> bool:
        """Establish SSH connection"""
        # Move SSH connection logic here
        
    async def list_remote_files(self, directory: str) -> List[str]:
        """List files in remote directory"""
        # Move logic here
        
    async def download_file(self, remote_path: str, local_path: str) -> bool:
        """Download file from remote server"""
        # Move logic here
        
    def disconnect(self):
        """Close SSH connection"""
        if self.client:
            self.client.close()
```

#### Step 3.2: Monitoring Service
**File:** `bot/services/monitoring_service.py`

```python
#!/usr/bin/env python3
"""
File monitoring and automatic import service.
"""
import logging
from typing import Callable, Optional
from datetime import datetime

logger = logging.getLogger("MonitoringService")

class MonitoringService:
    """Monitors game server for new stats files"""
    
    def __init__(self, bot, ssh_service):
        self.bot = bot
        self.ssh = ssh_service
        self.is_monitoring = False
        self.last_check = None
        
    async def start_monitoring(self):
        """Start monitoring for new files"""
        # Move monitoring logic here
        
    async def stop_monitoring(self):
        """Stop monitoring"""
        # Move logic here
        
    async def check_for_new_files(self) -> List[str]:
        """Check for new stats files"""
        # Move logic here
```

---

### Phase 4: Extract Utilities (Day 5)

#### Step 4.1: Formatters
**File:** `bot/utils/formatters.py`

```python
#!/usr/bin/env python3
"""
Discord embed formatting utilities.
"""
import discord
from typing import Dict, Any, List

def create_stats_embed(player_data: Dict[str, Any]) -> discord.Embed:
    """Create beautiful stats embed for a player"""
    # Move embed creation logic here
    
def create_leaderboard_embed(
    rankings: List[Dict[str, Any]], 
    stat_type: str, 
    page: int
) -> discord.Embed:
    """Create leaderboard embed"""
    # Move logic here
    
def format_accuracy_bar(accuracy: float) -> str:
    """Create visual accuracy bar"""
    filled = int(accuracy / 10)
    empty = 10 - filled
    return f"{'█' * filled}{'░' * empty} {accuracy:.1f}%"
    
def format_kd_ratio(kills: int, deaths: int) -> str:
    """Format K/D ratio with indicators"""
    # Move logic here
```

---

## 🚀 Migration Script

**File:** `scripts/refactor_bot.py`

```python
#!/usr/bin/env python3
"""
Automated refactoring script to split ultimate_bot.py
WARNING: Creates a backup before making changes
"""
import shutil
from pathlib import Path
from datetime import datetime

def backup_current_file():
    """Backup ultimate_bot.py before refactoring"""
    source = Path("bot/ultimate_bot.py")
    backup_name = f"bot/ultimate_bot.py.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(source, backup_name)
    print(f"✅ Backup created: {backup_name}")

def extract_class(class_name: str, start_line: int, end_line: int, output_file: str):
    """Extract a class from ultimate_bot.py to a new file"""
    # Implementation here
    pass

def main():
    print("🔧 Starting bot refactoring...")
    print("=" * 60)
    
    # Backup first
    backup_current_file()
    
    # Create directory structure
    dirs = [
        "bot/cogs",
        "bot/core",
        "bot/services",
        "bot/utils",
    ]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
        Path(f"{d}/__init__.py").touch()
    
    # Extract classes (would need proper line numbers)
    print("📝 Extracting classes...")
    # extract_class("StatsCache", ..., "bot/core/cache.py")
    # extract_class("SeasonManager", ..., "bot/core/seasons.py")
    # etc.
    
    print("✅ Refactoring complete!")
    print("⚠️  Don't forget to:")
    print("   1. Update imports in ultimate_bot.py")
    print("   2. Test each command")
    print("   3. Run tests")

if __name__ == "__main__":
    main()
```

---

## ✅ Testing Checklist

After each extraction, test:

```python
# Run this after each phase
python -m pytest tests/ -v

# Test individual components
python -c "from bot.core.cache import StatsCache; c = StatsCache(); print('✅ Cache works')"
python -c "from bot.core.seasons import SeasonManager; s = SeasonManager(); print('✅ Seasons work')"

# Test bot startup
python bot/ultimate_bot.py --dry-run
```

---

## 📊 Progress Tracking

- [ ] Phase 1: Extract Core Classes (Day 1)
  - [ ] StatsCache → `bot/core/cache.py`
  - [ ] SeasonManager → `bot/core/seasons.py`
  - [ ] AchievementSystem → `bot/core/achievements.py`
  
- [ ] Phase 2: Extract Command Cogs (Day 2-3)
  - [ ] Stats commands → `bot/cogs/stats_cog.py`
  - [ ] Session commands → `bot/cogs/session_cog.py`
  - [ ] Link commands → `bot/cogs/link_cog.py`
  - [ ] Admin commands → `bot/cogs/admin_cog.py`
  
- [ ] Phase 3: Extract Services (Day 4)
  - [ ] SSH operations → `bot/services/ssh_service.py`
  - [ ] Monitoring → `bot/services/monitoring_service.py`
  
- [ ] Phase 4: Extract Utilities (Day 5)
  - [ ] Formatters → `bot/utils/formatters.py`
  - [ ] Validators → `bot/utils/validators.py`
  - [ ] Helpers → `bot/utils/helpers.py`
  
- [ ] Phase 5: Final Cleanup
  - [ ] Update all imports
  - [ ] Write unit tests
  - [ ] Update documentation
  - [ ] Final verification

---

## 🎯 Expected Results

**Before:**
```
ultimate_bot.py: 9,587 lines (impossible to maintain)
```

**After:**
```
bot/
├── ultimate_bot.py          300 lines  ✅
├── cogs/
│   ├── stats_cog.py        800 lines  ✅
│   ├── session_cog.py      500 lines  ✅
│   ├── link_cog.py         400 lines  ✅
│   └── admin_cog.py        600 lines  ✅
├── core/
│   ├── cache.py            100 lines  ✅
│   ├── seasons.py          150 lines  ✅
│   ├── achievements.py     200 lines  ✅
│   └── database.py         300 lines  ✅
├── services/
│   ├── ssh_service.py      300 lines  ✅
│   ├── monitoring.py       400 lines  ✅
│   └── parser.py           200 lines  ✅
└── utils/
    ├── formatters.py       300 lines  ✅
    ├── validators.py       150 lines  ✅
    └── helpers.py          200 lines  ✅
```

**Total:** Still ~5,000 lines of logic, but now:
- ✅ Each file has a single responsibility
- ✅ Easy to test individual components
- ✅ Easy to find and fix bugs
- ✅ Multiple people can work without conflicts
- ✅ Readable and maintainable

---

## 💡 Pro Tips

1. **One class at a time** - Don't try to refactor everything at once
2. **Test after each extraction** - Make sure nothing breaks
3. **Commit frequently** - Each successful extraction should be a commit
4. **Keep the bot running** - Don't refactor while users are active
5. **Document as you go** - Update docstrings and comments

---

Ready to start? Begin with Phase 1, Step 1.1 (StatsCache extraction). It's the simplest and least risky!
