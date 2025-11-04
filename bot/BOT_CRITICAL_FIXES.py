"""
🔧 CRITICAL BOT FIXES - October 4, 2025
=======================================
Applies all critical fixes to ultimate_bot.py:
1. Schema validation (53 columns check)
2. NULL/None checks in calculations
3. Better database path handling
4. Consistent async with patterns
5. Rate limiting for Discord messages

Apply these patches to bot/ultimate_bot.py
"""

# ============================================================================
# FIX #1: ADD SCHEMA VALIDATION METHOD
# ============================================================================
# Add this method to UltimateETLegacyBot class (after __init__)

async def validate_database_schema(self):
    """
    ✅ CRITICAL: Validate database has correct unified schema
    Prevents silent failures if wrong schema is used
    """
    try:
        async with aiosqlite.connect(self.db_path) as db:
            # Check player_comprehensive_stats has 53 columns
            cursor = await db.execute(
                "PRAGMA table_info(player_comprehensive_stats)"
            )
            columns = await cursor.fetchall()
            
            expected_columns = 53
            actual_columns = len(columns)
            
            if actual_columns != expected_columns:
                error_msg = (
                    f"❌ DATABASE SCHEMA MISMATCH!\n"
                    f"Expected: {expected_columns} columns (UNIFIED schema)\n"
                    f"Found: {actual_columns} columns\n\n"
                )
                
                if actual_columns == 35:
                    error_msg += (
                        "This database uses SPLIT schema (deprecated).\n"
                        "Bot requires UNIFIED schema.\n\n"
                    )
                else:
                    error_msg += f"Unknown schema with {actual_columns} columns.\n\n"
                
                error_msg += (
                    "Solution:\n"
                    "1. Backup current database\n"
                    "2. Run: python create_unified_database.py\n"
                    "3. Run: python tools/simple_bulk_import.py local_stats/*.txt\n"
                )
                
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            # Verify objective stats columns exist
            column_names = [col[1] for col in columns]
            required_objective_stats = [
                'kill_assists',
                'objectives_completed',
                'dynamites_planted',
                'times_revived',
                'revives_given',
                'most_useful_kills',
                'useless_kills',
                'kill_steals',
                'denied_playtime',
            ]
            
            missing = [
                col for col in required_objective_stats
                if col not in column_names
            ]
            
            if missing:
                error_msg = (
                    f"❌ MISSING OBJECTIVE STATS COLUMNS: {missing}\n"
                    f"Database schema is incomplete!\n"
                    f"Column list: {column_names[:10]}...\n"
                )
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            logger.info(
                f"✅ Database schema validated: {actual_columns} columns (UNIFIED)"
            )
            logger.info(f"✅ All {len(required_objective_stats)} objective stats columns present")
            
    except Exception as e:
        logger.error(f"❌ Schema validation failed: {e}")
        raise


# ============================================================================
# FIX #2: IMPROVED DATABASE PATH HANDLING
# ============================================================================
# Replace the db_path assignment in __init__ with this:

def _find_database(self):
    """
    🔍 Find database in multiple locations
    Returns path if found, raises FileNotFoundError if not
    """
    import os
    
    bot_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(bot_dir)
    
    # Try multiple locations
    possible_paths = [
        os.path.join(parent_dir, 'etlegacy_production.db'),  # Project root
        os.path.join(bot_dir, 'etlegacy_production.db'),     # Bot directory
        'etlegacy_production.db',                             # Current directory
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            logger.info(f"✅ Database found: {path}")
            return path
    
    # Database not found - provide clear error
    error_msg = (
        "❌ DATABASE NOT FOUND!\n\n"
        "Tried the following locations:\n" +
        "\n".join(f"  • {p}" for p in possible_paths) +
        "\n\nSolution:\n"
        "1. Ensure you're in the project directory\n"
        "2. Check database exists: ls etlegacy_production.db\n"
        "3. If missing, run: python create_unified_database.py\n"
    )
    
    logger.error(error_msg)
    raise FileNotFoundError(error_msg)

# Then in __init__, replace the db_path lines with:
#     self.db_path = self._find_database()


# ============================================================================
# FIX #3: NULL-SAFE CALCULATION HELPERS
# ============================================================================
# Add these helper methods to UltimateETLegacyBot class:

def safe_divide(self, numerator, denominator, default=0.0):
    """
    ✅ Safely divide two numbers, handling NULL/None/zero
    Returns default if division not possible
    """
    try:
        if numerator is None or denominator is None:
            return default
        if denominator == 0:
            return default
        return numerator / denominator
    except (TypeError, ZeroDivisionError):
        return default

def safe_percentage(self, part, total, default=0.0):
    """
    ✅ Safely calculate percentage, handling NULL/None/zero
    Returns percentage (0-100) or default
    """
    result = self.safe_divide(part, total, default)
    return result * 100 if result != default else default

def safe_dpm(self, damage, time_seconds, default=0.0):
    """
    ✅ Safely calculate DPM (damage per minute)
    Formula: (damage * 60) / time_seconds
    """
    try:
        if damage is None or time_seconds is None:
            return default
        if time_seconds == 0:
            return default
        return (damage * 60) / time_seconds
    except (TypeError, ZeroDivisionError):
        return default

def safe_format_time(self, seconds):
    """
    ✅ Safely format time in MM:SS, handling NULL/None
    """
    try:
        if seconds is None or seconds == 0:
            return "0:00"
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}:{secs:02d}"
    except (TypeError, ValueError):
        return "0:00"


# ============================================================================
# FIX #4: RATE LIMITING HELPER
# ============================================================================
# Add this method to UltimateETLegacyBot class:

async def send_with_delay(self, ctx, *args, delay=0.5, **kwargs):
    """
    ✅ Send message with delay to avoid Discord rate limits
    Use this instead of ctx.send() when sending multiple messages
    """
    await ctx.send(*args, **kwargs)
    await asyncio.sleep(delay)  # 500ms delay between messages


# ============================================================================
# FIX #5: UPDATE setup_hook TO CALL VALIDATION
# ============================================================================
# Replace setup_hook method with this:

async def setup_hook(self):
    """🔧 Initialize all bot components"""
    logger.info("🚀 Initializing Ultimate ET:Legacy Bot...")
    
    # ✅ CRITICAL: Validate schema FIRST
    await self.validate_database_schema()
    
    # Add the commands cog
    await self.add_cog(ETLegacyCommands(self))
    
    # Initialize database
    await self.initialize_database()
    
    # Start background tasks
    self.endstats_monitor.start()
    self.cache_refresher.start()
    
    logger.info("✅ Ultimate Bot initialization complete!")
    logger.info(f"📋 Commands available: {[cmd.name for cmd in self.commands]}")


# ============================================================================
# FIX #6: EXAMPLE USAGE IN COMMANDS
# ============================================================================
# Update commands to use safe helpers. Example for !stats command:

# OLD CODE (crashes on NULL):
# if hits > 0:
#     accuracy = (hits / shots) * 100

# NEW CODE (NULL-safe):
# accuracy = self.bot.safe_percentage(hits, shots, default=0.0)

# OLD CODE (crashes on NULL):
# dpm = (damage * 60) / time_seconds

# NEW CODE (NULL-safe):
# dpm = self.bot.safe_dpm(damage, time_seconds, default=0.0)

# OLD CODE (crashes on NULL):
# kd_ratio = kills / deaths

# NEW CODE (NULL-safe):
# kd_ratio = self.bot.safe_divide(kills, deaths, default=0.0)


# ============================================================================
# COMPLETE EXAMPLE: FIXED __init__ METHOD
# ============================================================================

def __init__(self):
    intents = discord.Intents.default()
    intents.message_content = True
    super().__init__(command_prefix='!', intents=intents)
    
    # ✅ FIXED: Better database path handling
    self.db_path = self._find_database()
    
    # 🎮 Bot State
    self.current_session = None
    self.monitoring = False
    self.processed_files = set()
    self.auto_link_enabled = True
    self.gather_queue = {"3v3": [], "6v6": []}
    
    # 🏆 Awards and achievements tracking
    self.awards_cache = {}
    self.mvp_cache = {}
    
    # 📈 Performance tracking
    self.command_stats = {}
    self.error_count = 0


# ============================================================================
# TESTING CHECKLIST
# ============================================================================
"""
After applying fixes, test:

1. Schema Validation:
   - Create test DB with wrong schema
   - Try to start bot
   - Should get clear error message

2. NULL Handling:
   - Insert record with NULL values
   - Run !stats command
   - Should show 0.0 instead of crashing

3. Database Path:
   - Run bot from different directories
   - Should find database or show clear error

4. Rate Limiting:
   - Spam !last_session command
   - Should not hit Discord rate limits

Commands to test:
```bash
# Test 1: Wrong schema
sqlite3 test_wrong_schema.db "CREATE TABLE player_comprehensive_stats (id INT)"
# Edit bot to use test DB, run - should error clearly

# Test 2: NULL handling
sqlite3 etlegacy_production.db "UPDATE player_comprehensive_stats SET kills = NULL WHERE id = 1"
# Run !stats - should not crash

# Test 3: Database path
cd bot
python ultimate_bot.py  # Should find database

# Test 4: Rate limiting
# In Discord: !last_session !last_session !last_session
# Should work without errors
```
"""


# ============================================================================
# SUMMARY OF CHANGES
# ============================================================================
"""
✅ Added validate_database_schema() - Checks for 53 columns
✅ Added _find_database() - Tries multiple locations
✅ Added safe_divide() - NULL-safe division
✅ Added safe_percentage() - NULL-safe percentage calc
✅ Added safe_dpm() - NULL-safe DPM calc
✅ Added safe_format_time() - NULL-safe time formatting
✅ Added send_with_delay() - Rate limit protection
✅ Updated setup_hook() - Calls validation first
✅ Updated __init__() - Uses _find_database()

IMPACT:
- Prevents silent failures (schema mismatch detected)
- Prevents crashes (NULL values handled)
- Better error messages (clear instructions)
- Rate limit protection (Discord API compliance)
- Works from any directory (flexible path finding)

ESTIMATED FIX TIME: 40 minutes
- Add methods: 20 minutes
- Update callers: 15 minutes
- Testing: 5 minutes
"""
