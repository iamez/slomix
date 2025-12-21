# Slomix Bot Code Review - Part 2/3 Implementation Guide

**For: AI Agent (Claude Sonnet 4.5)**
**Project: slomix Discord Bot for ET:Legacy**
**Date: November 2025**
**Branch: refactor/configuration-object (or create new branch)**

---

## Overview

This document contains code review findings for 6 files in the slomix bot. Each section describes issues found and provides exact code fixes to implement. Work through each file systematically, testing after each change.

**Priority Order:**
1. `bot/stats/calculator.py` - Add missing method (LOW RISK)
2. `bot/logging_config.py` - Fix deprecated API (LOW RISK)
3. `bot/community_stats_parser.py` - Fix unreachable code (LOW RISK)
4. `bot/image_generator.py` - Fix exception handling (MEDIUM RISK)
5. `bot/automation/file_tracker.py` - Add race condition protection (MEDIUM RISK)
6. `bot/automation/ssh_handler.py` - Add timeout handling (MEDIUM RISK)

---

## File 1: bot/stats/calculator.py

### Status: ⭐⭐⭐⭐⭐ Excellent - NO CHANGES NEEDED

The calculator module is well-designed and complete. 

**Note:** The Lua script (c0rnp0rn3.lua) already calculates `time_dead_ratio` and `time_dead_minutes` server-side:
- `topshots[i][14]` → TAB field 24 → `time_dead_ratio` (percentage)
- `death_time_total[i] / 60000` → TAB field 25 → `time_dead_minutes`

The parser correctly extracts these pre-computed values, so no additional calculator methods are needed.

**Verification:** (optional)
```python
from bot.stats import StatsCalculator
assert StatsCalculator.calculate_dpm(1200, 300) == 240.0
assert StatsCalculator.calculate_kd(20, 10) == 2.0
print("calculator.py is working correctly!")
```

---

## File 2: bot/logging_config.py

### Status: ⭐⭐⭐⭐ Good - Fix Deprecated API

### Task 2.1: Fix deprecated Discord discriminator usage

**Location:** Function `log_command_execution`, approximately line 127

**Find this code:**
```python
def log_command_execution(ctx, command_name, start_time=None, end_time=None, error=None):
    """
    Log command execution with full context
    ...
    """
    logger = logging.getLogger('bot.commands')
    
    # Build context info
    user = f"{ctx.author.name}#{ctx.author.discriminator} ({ctx.author.id})"
```

**Replace with:**
```python
def log_command_execution(ctx, command_name, start_time=None, end_time=None, error=None):
    """
    Log command execution with full context
    
    Args:
        ctx: Discord context
        command_name: Name of the command
        start_time: When command started (optional)
        end_time: When command finished (optional)
        error: Exception if command failed (optional)
    """
    logger = logging.getLogger('bot.commands')
    
    # Build context info
    # Note: Discord removed discriminators in 2023, use display_name instead
    user = f"{ctx.author.display_name} ({ctx.author.id})"
```

### Task 2.2: Add automation event logger (Optional Enhancement)

**Location:** After the `log_performance_warning` function, before `get_logger`

**Add this new function:**
```python
def log_automation_event(event_type, details, success=True, error=None):
    """
    Log automation events (SSH monitor, file tracker, etc.)
    
    Args:
        event_type: Type of event (e.g., 'SSH_DOWNLOAD', 'FILE_PROCESS', 'STATS_IMPORT')
        details: Description of the event
        success: Whether the event succeeded
        error: Exception if event failed (optional)
    """
    logger = logging.getLogger('bot.automation')
    
    if error:
        logger.error(f"❌ {event_type} FAILED: {details} | Error: {error}", exc_info=True)
    elif success:
        logger.info(f"✓ {event_type}: {details}")
    else:
        logger.warning(f"⚠️ {event_type}: {details}")
```

**Verification:** Import test:
```python
from bot.logging_config import log_command_execution, log_automation_event
print("logging_config.py imports successfully!")
```

---

## File 3: bot/community_stats_parser.py

### Status: ⭐⭐⭐⭐ Good - Fix Unreachable Code

### Task 3.1: Move important comment before return statement

**Location:** Function `parse_player_line`, approximately lines 640-660

**Find this code (at the END of parse_player_line):**
```python
            return {
                'guid': guid[:8],  # Truncate GUID
                'clean_name': clean_name,  # ✅ FIXED: Use clean_name
                'name': clean_name,  # Keep both for compatibility
                'raw_name': raw_name,
                'team': team,
                'rounds': rounds,
                'kills': total_kills,
                'deaths': total_deaths,
                'headshots': total_headshots,  # ⚠️ IMPORTANT: This is sum of weapon headshot HITS (not kills!)
                'kd_ratio': kd_ratio,
                'shots_total': total_shots,
                'hits_total': total_hits,
                'accuracy': total_accuracy,
                'damage_given': additional_stats.get('damage_given', 0),
                'damage_received': additional_stats.get('damage_received', 0),
                'dpm': objective_stats.get('dpm', 0.0),
                'weapon_stats': weapon_stats,
                'efficiency': efficiency,
                'objective_stats': objective_stats,  # ✅ Contains headshot_KILLS (TAB field 14) + revives + all other stats
            }
            
            # ⚠️ CRITICAL DISTINCTION - DO NOT CONFUSE THESE TWO:
            # 1. player['headshots'] = Sum of all weapon headshot HITS (shots that hit head, may not kill)
            # 2. objective_stats['headshot_kills'] = TAB field 14 (kills where FINAL BLOW was to head)
            # These are DIFFERENT stats! Database stores headshot_kills, NOT weapon sum.
            # Validated Nov 3, 2025: 100% accuracy confirmed.

        except Exception as e:
            print(f"Error parsing player line: {e}")
            return None
```

**Replace with (move comment BEFORE return):**
```python
            # ⚠️ CRITICAL DISTINCTION - DO NOT CONFUSE THESE TWO:
            # 1. player['headshots'] = Sum of all weapon headshot HITS (shots that hit head, may not kill)
            # 2. objective_stats['headshot_kills'] = TAB field 14 (kills where FINAL BLOW was to head)
            # These are DIFFERENT stats! Database stores headshot_kills, NOT weapon sum.
            # Validated Nov 3, 2025: 100% accuracy confirmed.

            return {
                'guid': guid[:8],  # Truncate GUID
                'clean_name': clean_name,
                'name': clean_name,  # Keep both for compatibility
                'raw_name': raw_name,
                'team': team,
                'rounds': rounds,
                'kills': total_kills,
                'deaths': total_deaths,
                'headshots': total_headshots,  # Sum of weapon headshot HITS (not kills!)
                'kd_ratio': kd_ratio,
                'shots_total': total_shots,
                'hits_total': total_hits,
                'accuracy': total_accuracy,
                'damage_given': additional_stats.get('damage_given', 0),
                'damage_received': additional_stats.get('damage_received', 0),
                'dpm': objective_stats.get('dpm', 0.0),
                'weapon_stats': weapon_stats,
                'efficiency': efficiency,
                'objective_stats': objective_stats,  # Contains headshot_KILLS (TAB field 14)
            }

        except Exception as e:
            print(f"Error parsing player line: {e}")
            return None
```

### Task 3.2: Add format documentation comment

**Location:** Top of file, after the imports, before `C0RNP0RN3_WEAPONS`

**Add this comment block:**
```python
# =============================================================================
# FILENAME FORMAT: YYYY-MM-DD-HHMMSS-<map_name>-round-<N>.txt
# Example: 2025-10-02-232818-erdenberg_t2-round-2.txt
#
# The timestamp (first 17 characters) is used for:
# - Deduplication (file_tracker.py)
# - Round 1/Round 2 pairing (differential calculation)
# - Session identification (match_id generation)
#
# ROUND 2 DIFFERENTIAL CALCULATION:
# Round 2 files contain CUMULATIVE stats from both rounds.
# To get Round 2-only stats: R2_cumulative - R1 = R2_only
# =============================================================================
```

**Verification:**
```python
from bot.community_stats_parser import C0RNP0RN3StatsParser
parser = C0RNP0RN3StatsParser()
print("community_stats_parser.py imports successfully!")
```

---

## File 4: bot/image_generator.py

### Status: ⭐⭐⭐½ Good - Fix Exception Handling

### Task 4.1: Replace `BaseException` with `Exception`

**Location:** Multiple places in the file. Search for `BaseException` and replace all occurrences.

**Find all instances of:**
```python
except BaseException:
```

**Replace each with:**
```python
except Exception:
```

There should be approximately 4-5 occurrences in:
- `create_session_overview` (font loading)
- `create_performance_graphs` (if any)
- `create_weapon_mastery_image` (font loading)

### Task 4.2: Add logging for font fallback

**Location:** At the top of the file, after imports

**Add:**
```python
import logging

logger = logging.getLogger('bot.image_generator')
```

**Then modify font loading blocks. Find:**
```python
        try:
            title_font = ImageFont.truetype("arial.ttf", 48)
            header_font = ImageFont.truetype("arialbd.ttf", 32)
            stat_font = ImageFont.truetype("arial.ttf", 24)
            small_font = ImageFont.truetype("arial.ttf", 18)
        except Exception:
            title_font = ImageFont.load_default()
            header_font = ImageFont.load_default()
            stat_font = ImageFont.load_default()
            small_font = ImageFont.load_default()
```

**Replace with:**
```python
        try:
            title_font = ImageFont.truetype("arial.ttf", 48)
            header_font = ImageFont.truetype("arialbd.ttf", 32)
            stat_font = ImageFont.truetype("arial.ttf", 24)
            small_font = ImageFont.truetype("arial.ttf", 18)
        except Exception as e:
            logger.warning(f"Could not load custom fonts, using defaults: {e}")
            title_font = ImageFont.load_default()
            header_font = ImageFont.load_default()
            stat_font = ImageFont.load_default()
            small_font = ImageFont.load_default()
```

### Task 4.3: Extract magic numbers to constants (Optional)

**Location:** Top of the `StatsImageGenerator` class, after `COLORS`

**Add:**
```python
    # Layout spacing constants
    SPACING = {
        'title_margin': 70,
        'section_margin': 50,
        'line_spacing': 30,
        'player_entry_height': 32,
        'divider_height': 2,
    }
```

**Note:** This is optional. If you do this, you'll need to update the magic numbers throughout the file to use `self.SPACING['title_margin']` etc. This is a larger refactor and can be done later.

**Verification:**
```python
from bot.image_generator import StatsImageGenerator
gen = StatsImageGenerator()
print("image_generator.py imports successfully!")
```

---

## File 5: bot/automation/file_tracker.py

### Status: ⭐⭐⭐⭐ Good - Add Race Condition Protection

### Task 5.1: Add asyncio Lock for thread safety

**Location:** Top of file, add to imports

**Find:**
```python
import asyncio
import logging
import os
from datetime import datetime
from typing import Optional, Set
```

**No change needed to imports** (asyncio is already imported)

### Task 5.2: Add lock to __init__

**Location:** In the `__init__` method

**Find:**
```python
    def __init__(self, db_adapter, config, bot_startup_time: datetime, processed_files: Set[str]):
        """
        Initialize file tracker
        ...
        """
        self.db_adapter = db_adapter
        self.config = config
        self.bot_startup_time = bot_startup_time
        self.processed_files = processed_files  # Reference to bot's set
```

**Replace with:**
```python
    def __init__(self, db_adapter, config, bot_startup_time: datetime, processed_files: Set[str]):
        """
        Initialize file tracker

        Args:
            db_adapter: Database adapter (PostgreSQL or SQLite)
            config: Bot configuration object
            bot_startup_time: When the bot started (for age filtering)
            processed_files: In-memory set of processed filenames
        """
        self.db_adapter = db_adapter
        self.config = config
        self.bot_startup_time = bot_startup_time
        self.processed_files = processed_files  # Reference to bot's set
        self._process_lock = asyncio.Lock()  # Prevent race conditions
```

### Task 5.3: Use lock in should_process_file

**Location:** In `should_process_file` method

**Find the beginning of the method:**
```python
    async def should_process_file(
        self, filename: str, ignore_startup_time: bool = False, check_db_only: bool = False
    ) -> bool:
        """
        Smart file processing decision (Hybrid Approach)
        ...
        """
        try:
            # 1. Check file age - only import files created AFTER bot startup
```

**Replace with (add lock context manager):**
```python
    async def should_process_file(
        self, filename: str, ignore_startup_time: bool = False, check_db_only: bool = False
    ) -> bool:
        """
        Smart file processing decision (Hybrid Approach)

        Checks multiple sources to avoid re-processing:
        1. File age (prevent importing old files) - SKIPPED if ignore_startup_time=True
        2. In-memory cache (fastest)
        3. Local file exists (fast) - SKIPPED if check_db_only=True
        4. Processed files table (fast, persistent)
        5. Sessions table (slower, definitive)

        Args:
            filename: Name of the file to check
            ignore_startup_time: If True, skip the bot startup time check (used by manual sync commands)
            check_db_only: If True, only check database, not local files (used to find files needing import)

        Returns:
            bool: True if file should be processed, False if already done
        """
        async with self._process_lock:  # Prevent race conditions
            return await self._should_process_file_impl(filename, ignore_startup_time, check_db_only)

    async def _should_process_file_impl(
        self, filename: str, ignore_startup_time: bool, check_db_only: bool
    ) -> bool:
        """Internal implementation of should_process_file (called under lock)"""
        try:
            # 1. Check file age - only import files created AFTER bot startup
```

**IMPORTANT:** You need to rename the rest of the original method body. The entire `try:` block and everything after stays the same, just inside `_should_process_file_impl`.

**Full structure should be:**
```python
async def should_process_file(...) -> bool:
    """Docstring..."""
    async with self._process_lock:
        return await self._should_process_file_impl(...)

async def _should_process_file_impl(...) -> bool:
    """Internal implementation..."""
    try:
        # ALL the original code goes here
        # ... (file age check)
        # ... (memory check)
        # ... (local file check)
        # ... (processed_files table check)
        # ... (session exists check)
        return True
    except Exception as e:
        logger.error(f"Error checking if should process {filename}: {e}")
        return False
```

### Task 5.4: Fix diagnostic message for both DB types

**Location:** In `sync_local_files_to_processed_table`, find the warning message

**Find:**
```python
                logger.warning(
                    f"💡 To import them, use: python postgresql_database_manager.py "
                    f"or !import command"
                )
```

**Replace with:**
```python
                if self.config.database_type == "postgresql":
                    logger.warning(
                        f"💡 To import them, use: python postgresql_database_manager.py "
                        f"or !import command"
                    )
                else:
                    logger.warning(
                        f"💡 To import them, use the !import command"
                    )
```

**Verification:**
```python
from bot.automation.file_tracker import FileTracker
print("file_tracker.py imports successfully!")
```

---

## File 6: bot/automation/ssh_handler.py

### Status: ⭐⭐⭐⭐ Good - Add Timeout Handling

### Task 6.1: Add SFTP operation timeout

**Location:** In `_download_file_sync` method

**Find:**
```python
    @staticmethod
    def _download_file_sync(ssh_config: Dict, filename: str, local_dir: str) -> str:
        """Synchronous SSH file download"""
        import paramiko

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        key_path = os.path.expanduser(ssh_config["key_path"])

        ssh.connect(
            hostname=ssh_config["host"],
            port=ssh_config["port"],
            username=ssh_config["user"],
            key_filename=key_path,
            timeout=10,
        )

        sftp = ssh.open_sftp()

        remote_file = f"{ssh_config['remote_path']}/{filename}"
        local_file = os.path.join(local_dir, filename)

        logger.info(f"📥 Downloading {filename}...")
        sftp.get(remote_file, local_file)

        sftp.close()
        ssh.close()

        return local_file
```

**Replace with:**
```python
    @staticmethod
    def _download_file_sync(ssh_config: Dict, filename: str, local_dir: str) -> str:
        """Synchronous SSH file download with timeout protection"""
        import paramiko

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        key_path = os.path.expanduser(ssh_config["key_path"])

        try:
            ssh.connect(
                hostname=ssh_config["host"],
                port=ssh_config["port"],
                username=ssh_config["user"],
                key_filename=key_path,
                timeout=10,
            )

            sftp = ssh.open_sftp()
            
            # Set timeout for SFTP operations (30 seconds for file transfers)
            sftp.get_channel().settimeout(30.0)

            remote_file = f"{ssh_config['remote_path']}/{filename}"
            local_file = os.path.join(local_dir, filename)

            logger.info(f"📥 Downloading {filename}...")
            sftp.get(remote_file, local_file)

            return local_file
            
        finally:
            # Ensure connections are closed even on error
            try:
                sftp.close()
            except Exception:
                pass
            try:
                ssh.close()
            except Exception:
                pass
```

### Task 6.2: Add timeout to list files operation

**Location:** In `_list_files_sync` method

**Find:**
```python
        sftp = ssh.open_sftp()
        files = sftp.listdir(ssh_config["remote_path"])
```

**Replace with:**
```python
        sftp = ssh.open_sftp()
        
        # Set timeout for SFTP operations
        sftp.get_channel().settimeout(15.0)
        
        files = sftp.listdir(ssh_config["remote_path"])
```

### Task 6.3: Add security comment about AutoAddPolicy

**Location:** Near the top of the file, after the docstring

**Add this comment:**
```python
# SECURITY NOTE: This module uses paramiko.AutoAddPolicy() which accepts any SSH host key.
# This is acceptable for connecting to our own VPS (puran.hehe.si) but should be
# changed to RejectPolicy with a known_hosts file if connecting to untrusted servers.
# See: https://docs.paramiko.org/en/stable/api/client.html#paramiko.client.AutoAddPolicy
```

**Verification:**
```python
from bot.automation.ssh_handler import SSHHandler
print("ssh_handler.py imports successfully!")
```

---

## Testing Checklist

After implementing all fixes, run these tests:

### 1. Import Tests
```bash
cd /path/to/slomix
python -c "
from bot.stats import StatsCalculator
from bot.logging_config import log_command_execution, get_logger
from bot.community_stats_parser import C0RNP0RN3StatsParser
from bot.image_generator import StatsImageGenerator
from bot.automation.file_tracker import FileTracker
from bot.automation.ssh_handler import SSHHandler
print('All imports successful!')
"
```

### 2. Calculator Tests
```bash
python -c "
from bot.stats import StatsCalculator
assert StatsCalculator.calculate_dpm(1200, 300) == 240.0
assert StatsCalculator.calculate_kd(20, 10) == 2.0
assert StatsCalculator.calculate_time_dead_ratio(30, 300) == 10.0
print('Calculator tests passed!')
"
```

### 3. Parser Test
```bash
python -c "
from bot.community_stats_parser import C0RNP0RN3StatsParser
parser = C0RNP0RN3StatsParser()
# Test with a sample file if available
import os
if os.path.exists('local_stats'):
    files = [f for f in os.listdir('local_stats') if f.endswith('.txt')]
    if files:
        result = parser.parse_stats_file(f'local_stats/{files[0]}')
        print(f'Parsed {files[0]}: success={result[\"success\"]}')
print('Parser test passed!')
"
```

### 4. Bot Startup Test
```bash
# Start the bot briefly to verify no import errors
timeout 10 python main.py || echo "Bot started successfully (timeout expected)"
```

---

## Commit Message Template

```
refactor: code review fixes part 2/3

- stats/calculator.py: Add calculate_time_dead_ratio method
- logging_config.py: Fix deprecated Discord discriminator, add automation logger
- community_stats_parser.py: Move unreachable comment, add format documentation
- image_generator.py: Replace BaseException with Exception, add font fallback logging
- file_tracker.py: Add asyncio Lock for race condition protection, fix DB-specific message
- ssh_handler.py: Add SFTP timeout handling, add security documentation

Part of ongoing refactoring effort for slomix Discord bot.
```

---

## Questions?

If you encounter issues:
1. Check Python syntax with `python -m py_compile <filename>`
2. Run import tests to isolate which file has issues
3. Check git diff to see what changed
4. If a change breaks something, `git checkout <filename>` to revert

**Priority:** Focus on tasks marked as fixes (BaseException, unreachable code, deprecated API). Enhancement tasks (magic numbers, connection pooling) can wait for future iterations.
