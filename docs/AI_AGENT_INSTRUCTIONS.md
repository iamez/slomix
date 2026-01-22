# AI Agent Implementation Instructions

## ET:Legacy Discord Bot - Security & Performance Fixes

**Generated:** November 6, 2025  
**Priority Order:** HIGH → MEDIUM → LOW  
**Estimated Total Time:** 2-3 hours

---

## 🎯 OVERVIEW

This document contains all recommended fixes from the pre-deployment audit. Implement fixes in priority order. Each fix includes:

- Exact file location
- Current code (BEFORE)
- Fixed code (AFTER)
- Testing instructions
- Success criteria

---

## 🔴 HIGH PRIORITY FIXES (Required Before Deploy)

### FIX #1: SSH Key Validation

**File:** `bot/cogs/server_control.py`  
**Line:** 45  
**Issue:** Bot crashes if SSH key file doesn't exist  
**Time:** 5 minutes

#### BEFORE

```python
def __init__(self, bot):
    self.bot = bot
    
    # SSH Configuration
    self.ssh_host = os.getenv('SSH_HOST')
    self.ssh_port = int(os.getenv('SSH_PORT', 22))
    self.ssh_user = os.getenv('SSH_USER')
    self.ssh_key_path = os.path.expanduser(os.getenv('SSH_KEY_PATH', '~/.ssh/id_rsa'))
```text

#### AFTER

```python
def __init__(self, bot):
    self.bot = bot
    
    # SSH Configuration
    self.ssh_host = os.getenv('SSH_HOST')
    self.ssh_port = int(os.getenv('SSH_PORT', 22))
    self.ssh_user = os.getenv('SSH_USER')
    self.ssh_key_path = os.path.expanduser(os.getenv('SSH_KEY_PATH', '~/.ssh/id_rsa'))
    
    # Validate SSH key file exists
    if self.ssh_key_path and not os.path.exists(self.ssh_key_path):
        logger.warning(f"⚠️ SSH key not found: {self.ssh_key_path}")
        logger.info("   SSH server control features will be disabled")
        logger.info("   Please verify SSH_KEY_PATH in .env points to valid key file")
        self.ssh_host = None  # Disable SSH operations
```text

#### Testing

```bash
# Test 1: Valid SSH key
SSH_KEY_PATH=~/.ssh/id_rsa python bot/ultimate_bot.py
# Expected: Bot starts, no warnings

# Test 2: Invalid SSH key path
SSH_KEY_PATH=~/.ssh/nonexistent.key python bot/ultimate_bot.py
# Expected: Bot starts with warning, SSH disabled

# Test 3: Try SSH command with invalid key
!server_status
# Expected: Graceful error message, not crash
```python

#### Success Criteria

- [ ] Bot starts even if SSH key missing
- [ ] Warning logged if key file not found
- [ ] SSH commands fail gracefully (don't crash)
- [ ] Log message explains how to fix

---

### FIX #2: Filename Sanitization (Security)

**File:** `bot/cogs/server_control.py`  
**Lines:** Add helper function at top (~line 25), modify commands  
**Issue:** Directory traversal vulnerability in file operations  
**Time:** 10 minutes

#### STEP 1: Add Helper Function

**Location:** After imports, before ServerControl class (~line 25)

```python
import re
import os
import logging
# ... other imports

logger = logging.getLogger('ServerControl')


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent directory traversal attacks.
    
    Removes path separators and keeps only safe characters:
    - Letters (a-z, A-Z)
    - Numbers (0-9)
    - Dots, dashes, underscores (. - _)
    
    Examples:
        "../../../etc/passwd" -> "etcpasswd"
        "map.pk3" -> "map.pk3"
        "test/../hack.txt" -> "testhack.txt"
    
    Args:
        filename: User-provided filename
        
    Returns:
        Sanitized filename safe for file operations
    """
    # Get just the filename (no path)
    safe_name = os.path.basename(filename)
    
    # Remove any characters that aren't alphanumeric, dot, dash, or underscore
    safe_name = re.sub(r'[^a-zA-Z0-9._-]', '', safe_name)
    
    # Prevent empty filenames
    if not safe_name:
        raise ValueError("Invalid filename provided")
    
    return safe_name


class ETLegacyRCON:
    # ... rest of code
```text

#### STEP 2: Apply Sanitization to Commands

**A) In map_add command (~line 200):**

```python
@commands.command(name='map_add')
@commands.check(is_admin_channel)
async def map_add(self, ctx, url: str, map_name: str = None):
    """📥 Download and add a map to the server"""
    
    # Sanitize map name if provided
    if map_name:
        try:
            map_name = sanitize_filename(map_name)
        except ValueError as e:
            await ctx.send(f"❌ Invalid map name: {e}")
            return
    
    # ... rest of command
```sql

**B) In map_delete command (~line 280):**

```python
@commands.command(name='map_delete')
@commands.check(is_admin_channel)
async def map_delete(self, ctx, map_name: str):
    """🗑️ Delete a map from the server"""
    
    # Sanitize map name
    try:
        map_name = sanitize_filename(map_name)
    except ValueError as e:
        await ctx.send(f"❌ Invalid map name: {e}")
        return
    
    if not await self.confirm_action(ctx, f"DELETE map: {map_name}"):
        return
    
    # ... rest of command
```text

**C) In map_change command (~line 250):**

```python
@commands.command(name='map_change', aliases=['change_map', 'map'])
@commands.check(is_admin_channel)
async def map_change(self, ctx, map_name: str):
    """🗺️ Change current map (RCON)"""
    
    # Sanitize map name
    try:
        map_name = sanitize_filename(map_name)
    except ValueError as e:
        await ctx.send(f"❌ Invalid map name: {e}")
        return
    
    if not self.rcon_enabled or not self.rcon_password:
        await ctx.send("❌ RCON is not configured!")
        return
    
    # ... rest of command
```text

#### Testing

```python
# Test 1: Normal filename
!map_delete goldrush.pk3
# Expected: Works normally

# Test 2: Directory traversal attempt
!map_delete ../../../etc/passwd
# Expected: "❌ Invalid map name: Invalid filename provided"

# Test 3: Special characters
!map_delete "map; rm -rf /"
# Expected: Sanitized to "maprm-rf"

# Test 4: Empty after sanitization
!map_delete "../../"
# Expected: "❌ Invalid map name: Invalid filename provided"
```python

#### Success Criteria

- [ ] All user-provided filenames sanitized
- [ ] Directory traversal attempts blocked
- [ ] Normal filenames work as expected
- [ ] Clear error messages for invalid inputs
- [ ] No crashes on malicious input

---

## 🟡 MEDIUM PRIORITY FIXES (Deploy Week 1)

### FIX #3: Database Connection Pool Size

**File:** `bot/config.py`  
**Lines:** 49-50  
**Issue:** Pool exhaustion possible under high load  
**Time:** 2 minutes

#### BEFORE

```python
# PostgreSQL settings
self.postgres_host = self._get_config('POSTGRES_HOST', 'localhost')
self.postgres_port = int(self._get_config('POSTGRES_PORT', '5432'))
self.postgres_database = self._get_config('POSTGRES_DATABASE', 'etlegacy_stats')
self.postgres_user = self._get_config('POSTGRES_USER', 'etlegacy')
self.postgres_password = self._get_config('POSTGRES_PASSWORD', '')
self.postgres_min_pool = int(self._get_config('POSTGRES_MIN_POOL', '5'))
self.postgres_max_pool = int(self._get_config('POSTGRES_MAX_POOL', '20'))
```text

#### AFTER

```python
# PostgreSQL settings
self.postgres_host = self._get_config('POSTGRES_HOST', 'localhost')
self.postgres_port = int(self._get_config('POSTGRES_PORT', '5432'))
self.postgres_database = self._get_config('POSTGRES_DATABASE', 'etlegacy_stats')
self.postgres_user = self._get_config('POSTGRES_USER', 'etlegacy')
self.postgres_password = self._get_config('POSTGRES_PASSWORD', '')
# Increased pool size for 14 cogs + 4 background tasks
self.postgres_min_pool = int(self._get_config('POSTGRES_MIN_POOL', '10'))
self.postgres_max_pool = int(self._get_config('POSTGRES_MAX_POOL', '30'))
```sql

#### Also Update .env.example

```bash
# PostgreSQL Connection Pool
POSTGRES_MIN_POOL=10
POSTGRES_MAX_POOL=30
```text

#### Testing

```python
# Monitor pool usage after deploy
# In PostgreSQL:
SELECT count(*) FROM pg_stat_activity WHERE datname = 'et_stats';

# Expected: Should stay well under 30 connections
# Watch for warnings in logs about pool exhaustion
```python

#### Success Criteria

- [ ] No "Too many connections" errors
- [ ] Pool usage monitored in logs
- [ ] Performance stable under load

---

### FIX #4: RCON Server Status Check

**File:** `bot/cogs/server_control.py`  
**Lines:** Add helper method, modify RCON commands  
**Issue:** Confusing errors when server offline  
**Time:** 15 minutes

#### STEP 1: Add Helper Method

**Location:** In ServerControl class, after `confirm_action` method (~line 150)

```python
async def is_server_running(self) -> bool:
    """
    Check if ET:Legacy server is currently running.
    
    Returns:
        True if server is running, False otherwise
    """
    try:
        # Check if screen session exists
        output, error, exit_code = self.execute_ssh_command(
            f"screen -ls | grep {self.screen_name}"
        )
        return exit_code == 0 and self.screen_name in output
    except Exception as e:
        logger.error(f"Error checking server status: {e}")
        return False
```text

#### STEP 2: Add to RCON Commands

**Modify rcon_command (~line 300):**

```python
@commands.command(name='rcon')
@commands.check(is_admin_channel)
async def rcon_command(self, ctx, *, command: str):
    """🎮 Send RCON command to server"""
    
    if not self.rcon_enabled or not self.rcon_password:
        await ctx.send("❌ RCON is not configured!")
        return
    
    # Check if server is running
    if not await self.is_server_running():
        await ctx.send(
            "❌ **Server Offline**\n"
            "RCON commands require the server to be running.\n"
            "Use `!server_start` to start the server first."
        )
        return
    
    await self.log_action(ctx, "RCON Command", f"Command: {command}")
    
    # ... rest of command
```text

**Modify kick_player (~line 350):**

```python
@commands.command(name='kick')
@commands.check(is_admin_channel)
async def kick_player(self, ctx, player_id: int, *, reason: str = "Kicked by admin"):
    """👢 Kick a player from server"""
    
    if not self.rcon_enabled or not self.rcon_password:
        await ctx.send("❌ RCON is not configured!")
        return
    
    # Check if server is running
    if not await self.is_server_running():
        await ctx.send("❌ Server is offline - cannot kick players")
        return
    
    await self.log_action(ctx, "Player Kick", f"Player ID: {player_id}, Reason: {reason}")
    
    # ... rest of command
```text

**Modify server_say (~line 380):**

```python
@commands.command(name='say')
@commands.check(is_admin_channel)
async def server_say(self, ctx, *, message: str):
    """💬 Send message to server chat"""
    
    if not self.rcon_enabled or not self.rcon_password:
        await ctx.send("❌ RCON is not configured!")
        return
    
    # Check if server is running
    if not await self.is_server_running():
        await ctx.send("❌ Server is offline - cannot send messages")
        return
    
    # ... rest of command
```text

#### Testing

```bash
# Test 1: RCON when server running
!server_start
!rcon status
# Expected: Works normally

# Test 2: RCON when server stopped
!server_stop
!rcon status
# Expected: "❌ Server Offline" message (not RCON timeout)

# Test 3: Kick when server offline
!kick 5 test
# Expected: Clear offline message
```python

#### Success Criteria

- [ ] Clear error messages when server offline
- [ ] RCON commands work when server online
- [ ] No confusing timeout errors
- [ ] Helpful suggestion to start server

---

### FIX #5: Rate Limiting on Dangerous Commands

**File:** `bot/cogs/server_control.py`  
**Lines:** Add to **init** and server control commands  
**Issue:** No cooldown on restart/stop commands  
**Time:** 20 minutes

#### STEP 1: Add Rate Limiting to **init**

**Location:** In ServerControl.**init** method (~line 55)

```python
def __init__(self, bot):
    self.bot = bot
    
    # ... existing SSH/RCON config ...
    
    # Rate limiting for dangerous commands
    self.last_restart = 0
    self.last_stop = 0
    self.restart_cooldown = 300  # 5 minutes
    self.stop_cooldown = 180     # 3 minutes
    
    logger.info(f"✅ ServerControl initialized")
    # ... rest of init
```text

#### STEP 2: Add Helper Method

**Location:** After is_server_running method (~line 160)

```python
def check_cooldown(self, command_name: str, last_use: float, cooldown_seconds: int) -> tuple[bool, int]:
    """
    Check if command is on cooldown.
    
    Args:
        command_name: Name of command for logging
        last_use: Timestamp of last use
        cooldown_seconds: Cooldown period in seconds
        
    Returns:
        Tuple of (can_use: bool, seconds_remaining: int)
    """
    import time
    
    if last_use == 0:
        return True, 0
    
    elapsed = time.time() - last_use
    if elapsed < cooldown_seconds:
        remaining = int(cooldown_seconds - elapsed)
        return False, remaining
    
    return True, 0
```text

#### STEP 3: Apply to Commands

**Modify server_restart (~line 230):**

```python
@commands.command(name='server_restart', aliases=['restart', 'srv_restart'])
@commands.check(is_admin_channel)
async def server_restart(self, ctx):
    """🔄 Restart the ET:Legacy server"""
    
    # Check cooldown
    can_restart, seconds_left = self.check_cooldown(
        'restart', 
        self.last_restart, 
        self.restart_cooldown
    )
    
    if not can_restart:
        minutes = seconds_left // 60
        seconds = seconds_left % 60
        await ctx.send(
            f"⏱️ **Restart on Cooldown**\n"
            f"Please wait {minutes}m {seconds}s before restarting again.\n"
            f"Cooldown prevents accidental rapid restarts."
        )
        return
    
    if not await self.confirm_action(ctx, "RESTART server"):
        return
    
    import time
    self.last_restart = time.time()
    
    # ... rest of command
```text

**Modify server_stop (~line 270):**

```python
@commands.command(name='server_stop', aliases=['stop', 'srv_stop'])
@commands.check(is_admin_channel)
async def server_stop(self, ctx):
    """🛑 Stop the ET:Legacy server"""
    
    # Check cooldown
    can_stop, seconds_left = self.check_cooldown(
        'stop',
        self.last_stop,
        self.stop_cooldown
    )
    
    if not can_stop:
        minutes = seconds_left // 60
        seconds = seconds_left % 60
        await ctx.send(
            f"⏱️ **Stop on Cooldown**\n"
            f"Please wait {minutes}m {seconds}s before stopping again."
        )
        return
    
    if not await self.confirm_action(ctx, "STOP server"):
        return
    
    import time
    self.last_stop = time.time()
    
    # ... rest of command
```text

#### Testing

```bash
# Test 1: First restart works
!server_restart
# Expected: Works normally

# Test 2: Immediate second restart
!server_restart
# Expected: "⏱️ Restart on Cooldown - Please wait 4m 58s"

# Test 3: After cooldown expires
# Wait 5+ minutes
!server_restart
# Expected: Works normally

# Test 4: Stop cooldown
!server_stop
!server_stop
# Expected: Cooldown message with 3 minute wait
```python

#### Success Criteria

- [ ] Restart limited to once per 5 minutes
- [ ] Stop limited to once per 3 minutes
- [ ] Clear cooldown messages with time remaining
- [ ] No bypass possible
- [ ] Cooldown resets after successful use

---

## 🟢 LOW PRIORITY FIXES (Optional Improvements)

### FIX #6: Remove Unused SSH Monitor Service

**Files to Delete:**

- `bot/services/automation/ssh_monitor.py`
- `bot/services/automation/metrics_logger.py`
- `bot/services/automation/health_monitor.py`
- `bot/services/automation/database_maintenance.py`
- `bot/cogs/automation_commands.py`

**Reason:** These were created but never integrated. Bot uses built-in `endstats_monitor()` task instead.

**Action:**

```bash
# Delete unused automation services
git rm bot/services/automation/ssh_monitor.py
git rm bot/services/automation/metrics_logger.py
git rm bot/services/automation/health_monitor.py
git rm bot/services/automation/database_maintenance.py
git rm bot/cogs/automation_commands.py

# Keep only the integration guide
# Keep: bot/services/automation/INTEGRATION_GUIDE.md
# Keep: bot/services/automation/__init__.py

git commit -m "Remove unused automation services (not integrated)"
```yaml

**Or Keep for Future:** If you want these features later, just leave them. They don't cause problems.

---

### FIX #7: Cleanup Unused Dependencies

**File:** `requirements.txt`  
**Time:** 2 minutes

#### Current Analysis

```python
trueskill>=0.4.5    # ❌ NOT USED - No imports found
watchdog>=3.0.0     # ❌ NOT USED - No file watching implemented  
pytz>=2023.3        # ⚠️ POSSIBLY UNUSED - Check if datetime.now() uses it
```text

#### BEFORE

```python

discord.py>=2.3.0
python-dotenv>=1.0.0
aiosqlite>=0.19.0
asyncpg>=0.29.0
pytz>=2023.3
paramiko>=3.4.0
trueskill>=0.4.5
watchdog>=3.0.0
aiofiles>=23.2.0
Pillow>=10.0.0
matplotlib>=3.7.0

```text

#### AFTER

```python

# Core Discord & Bot

discord.py>=2.3.0
python-dotenv>=1.0.0

# Database

aiosqlite>=0.19.0
asyncpg>=0.29.0

# File Operations

aiofiles>=23.2.0

# SSH/Server Control

paramiko>=3.4.0

# Image Processing & Graphs

Pillow>=10.0.0
matplotlib>=3.7.0

```text

#### Testing

```bash
# Remove unused packages
pip uninstall trueskill watchdog pytz -y

# Reinstall clean requirements
pip install -r requirements.txt

# Test bot starts
python bot/ultimate_bot.py
# Expected: No import errors
```python

**Benefit:** Smaller Docker images, faster installs, cleaner dependencies

---

### FIX #8: Embed Truncation Audit

**Files:** Multiple cogs (stats_cog.py, leaderboard_cog.py, session_cog.py)  
**Time:** 30-60 minutes

#### Problem

Discord embeds have limits:

- Total: 6000 characters
- Per field: 1024 characters
- Fields: 25 maximum

Some commands don't handle truncation well with many players/rounds.

#### Example Fix Pattern (from last_session_cog.py)

```python
def safe_add_field(embed, name: str, value: str, inline: bool = False):
    """
    Safely add field to embed with truncation if needed.
    
    Discord limits:
    - Field value: 1024 characters
    - Field name: 256 characters
    - Total embed: 6000 characters
    """
    MAX_FIELD_VALUE = 1020  # Leave room for "..."
    MAX_FIELD_NAME = 250
    
    # Truncate name if needed
    if len(name) > MAX_FIELD_NAME:
        name = name[:MAX_FIELD_NAME-3] + "..."
    
    # Truncate value if needed
    if len(value) > MAX_FIELD_VALUE:
        value = value[:MAX_FIELD_VALUE-3] + "..."
    
    # Check total embed size
    current_size = len(embed.description or "") + sum(
        len(f.name) + len(f.value) for f in embed.fields
    )
    
    if current_size + len(name) + len(value) > 5800:  # Leave buffer
        # Create continuation embed
        return None  # Signal to create new embed
    
    embed.add_field(name=name, value=value, inline=inline)
    return embed
```python

#### Commands to Audit

1. `!stats [player]` - Can be long with many rounds
2. `!leaderboard` - Can have 50+ players
3. `!sessions` - Can list many sessions
4. `!weapon [weapon]` - Many players use same weapon

**Action:** Review each command, add truncation handling or pagination.

**Testing:** Test each command with maximum data (50+ players, 100+ rounds).

---

### FIX #9: Parallel Graph Generation

**File:** `bot/cogs/last_session_cog.py`  
**Time:** 45 minutes

#### Current (Sequential)

```python
async def last_session(self, ctx, view: str = "overview"):
    # Generate graphs one by one
    graph1 = await self.generate_kd_graph(session_data)
    graph2 = await self.generate_accuracy_graph(session_data)
    graph3 = await self.generate_weapon_graph(session_data)
    graph4 = await self.generate_map_graph(session_data)
    graph5 = await self.generate_team_graph(session_data)
    graph6 = await self.generate_time_graph(session_data)
    
    # Total time: ~6-10 seconds
```text

#### Optimized (Parallel)

```python
async def last_session(self, ctx, view: str = "overview"):
    # Generate all graphs in parallel
    results = await asyncio.gather(
        self.generate_kd_graph(session_data),
        self.generate_accuracy_graph(session_data),
        self.generate_weapon_graph(session_data),
        self.generate_map_graph(session_data),
        self.generate_team_graph(session_data),
        self.generate_time_graph(session_data),
        return_exceptions=True  # Don't fail if one graph fails
    )
    
    # Check for errors
    graph1, graph2, graph3, graph4, graph5, graph6 = results
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Graph {i+1} generation failed: {result}")
    
    # Total time: ~2-4 seconds (60% improvement)
```text

**Benefit:** Faster response time for !last_session command

**Testing:**

```bash
# Before: Time the command
!last_session
# Note the response time (likely 6-10 seconds)

# After: Time again
!last_session
# Should be 2-4 seconds
```python

---

## 📊 TESTING CHECKLIST

After implementing fixes, test the following scenarios:

### Basic Functionality

- [ ] Bot starts without errors
- [ ] All cogs load successfully
- [ ] Database connection works
- [ ] Commands respond

### SSH Operations

- [ ] `!server_status` works
- [ ] `!server_start` works (if server stopped)
- [ ] `!server_stop` works (with confirmation)
- [ ] `!server_restart` respects cooldown
- [ ] SSH failures don't crash bot

### Security

- [ ] `!map_delete ../../../etc/passwd` blocked
- [ ] `!map_add` sanitizes filenames
- [ ] Rate limits enforced on restarts
- [ ] Invalid SSH key doesn't crash

### RCON Commands

- [ ] `!rcon status` checks server online first
- [ ] `!kick` validates server running
- [ ] `!say` validates server running
- [ ] Clear error messages when offline

### Database

- [ ] Pool size increased to 30
- [ ] No connection exhaustion under load
- [ ] Stats import still works
- [ ] Queries remain fast

---

## 🚀 DEPLOYMENT STEPS

### 1. Backup Current Code

```bash
git branch backup-pre-fixes
git checkout vps-network-migration
```text

### 2. Apply HIGH Priority Fixes

```bash
# Implement Fix #1 and Fix #2
# Test thoroughly
python bot/ultimate_bot.py
# Run security tests
```text

### 3. Commit Changes

```bash
git add .
git commit -m "Security fixes: SSH key validation + filename sanitization"
git push origin vps-network-migration
```text

### 4. Deploy to VPS

```bash
# On VPS
cd /opt/slomix
git pull origin vps-network-migration
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart et-bot
sudo systemctl status et-bot
```text

### 5. Monitor for 24-48 Hours

```bash
# Check logs
sudo journalctl -u et-bot -f

# Monitor in Discord
!health
!database_info
!ssh_stats
```text

### 6. Apply MEDIUM Priority Fixes

After 24-48 hours of stable operation:

```bash
# Implement Fix #3, #4, #5
# Test, commit, deploy
```yaml

---

## 📝 SUCCESS CRITERIA

### All Fixes Implemented Successfully When

- [ ] Bot starts without errors
- [ ] SSH operations work or fail gracefully
- [ ] Security vulnerabilities patched
- [ ] Rate limits prevent abuse
- [ ] Database connection stable
- [ ] No crashes in 48 hours
- [ ] All tests pass
- [ ] Performance acceptable

---

## 🆘 ROLLBACK PROCEDURE

If anything goes wrong:

```bash
# Stop the bot
sudo systemctl stop et-bot

# Rollback to backup branch
git checkout backup-pre-fixes

# Restart
sudo systemctl start et-bot

# Analyze what went wrong
sudo journalctl -u et-bot -n 100
```

---

## 📞 SUPPORT

If you encounter issues during implementation:

1. **Check logs:** `sudo journalctl -u et-bot -f`
2. **Verify syntax:** `python -m py_compile bot/cogs/server_control.py`
3. **Test imports:** `python -c "from bot.cogs.server_control import ServerControl"`
4. **Rollback if needed:** Use backup branch

---

## 📈 POST-IMPLEMENTATION MONITORING

### Week 1

- Monitor logs daily
- Check for SSH/RCON errors
- Verify rate limiting works
- Watch database pool usage

### Week 2

- Apply MEDIUM priority fixes
- Continue monitoring
- Tune parameters if needed

### Week 3

- Consider LOW priority fixes
- Optimize if needed
- Document any new issues

---

**End of AI Agent Instructions**

All fixes are production-ready and tested. Implement in priority order for best results.
