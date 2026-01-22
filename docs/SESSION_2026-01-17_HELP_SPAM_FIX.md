# Session 2026-01-17: !help Command Spam Bug Fix

## Problem

When a user ran `!help`, the bot spammed dozens of error messages:
- "Permission check failed." (many times)
- "Synergy analytics is currently disabled." (many times)
- "This command is restricted to the bot root user." (many times)
- Took ~33-45 seconds to complete

## Root Causes Discovered

### 1. Database Attribute Mismatch
```python
# checks.py used:
db = ctx.bot.db          # ERROR: Attribute doesn't exist

# But bot initializes as:
self.db_adapter = ...    # CORRECT attribute name
```

### 2. Wrong Parameter Format for fetch_one
```python
# Wrong - single value:
await db.fetch_one(query, ctx.author.id)

# Correct - tuple:
await db.fetch_one(query, (ctx.author.id,))
```
Error: "Value after * must be an iterable, not int"

### 3. Wrong Result Access (tuple vs dict)
```python
# fetch_one returns tuple, not dict
# Wrong:
result['tier']

# Correct:
result[0]
```
Error: "tuple indices must be integers or slices, not str"

### 4. Sending Messages in Check Predicates
Discord.py's help system calls `can_run()` on every command to filter which ones to show. When check predicates send error messages directly, this spams the channel.

The `ctx.invoked_with` guard doesn't work because during help filtering it's set to `"help"` (truthy), not `None`.

## Solution

**Raise `commands.CheckFailure` instead of sending messages directly.**

- During help filtering: discord.py catches `CheckFailure` silently and excludes the command
- During actual invocation: the global `on_command_error` handler (line 2882 in ultimate_bot.py) catches it and sends the message

## Files Modified

### bot/core/checks.py

**is_owner()** (line 167-169):
```python
# Before:
if ctx.author.id != owner_id:
    await ctx.send("❌ This command is restricted to the bot root user.")
    return False

# After:
if ctx.author.id != owner_id:
    raise commands.CheckFailure("This command is restricted to the bot root user.")
```

**is_admin()** (lines 201-218):
```python
# Before:
db = ctx.bot.db
result = await db.fetch_one(query, ctx.author.id)
if result and result['tier'] in ['admin', 'moderator']:
    ...
await ctx.send("❌ This command requires admin permissions.")
return False

# After:
db = ctx.bot.db_adapter
result = await db.fetch_one(query, (ctx.author.id,))
if result and result[0] in ['admin', 'moderator']:
    ...
raise commands.CheckFailure("This command requires admin permissions.")
```

**is_moderator()** (lines 247-264):
Same pattern as is_admin().

### bot/cogs/synergy_analytics.py

**cog_check()** (lines 79-89):
```python
# Before:
if not is_enabled():
    await ctx.send("🔒 Synergy analytics is currently disabled...")
    return False

# After:
if not is_enabled():
    raise commands.CheckFailure("🔒 Synergy analytics is currently disabled...")
```

## How It Works Now

```
!help command
    ↓
discord.py calls can_run() for each command
    ↓
Check raises CheckFailure
    ↓
discord.py silently excludes command from help (no spam)
    ↓
Help displays quickly

!admin_command (by non-admin)
    ↓
Check raises CheckFailure
    ↓
on_command_error() catches it
    ↓
Sends single error message to user
```

## Verification Steps

1. Restart the bot: `python -m bot.ultimate_bot`
2. Type `!help` as a non-admin user
   - Expected: No spam, help displays quickly (<2 seconds)
3. Type `!sync_all` (admin command) as non-admin
   - Expected: Single "This command requires admin permissions" message
4. Type a synergy command when analytics is disabled
   - Expected: Single "Synergy analytics is currently disabled" message

## Key Learnings

1. **Never send messages from check predicates** - raise `CheckFailure` instead
2. **`ctx.invoked_with` is NOT reliable for detecting help filtering** - it's set to "help" during filtering
3. **`fetch_one` returns tuples** - access with `result[0]`, not `result['tier']`
4. **Parameters must be tuples** - use `(value,)` not `value`
5. **Always check the actual attribute name** - `db_adapter` not `db`
