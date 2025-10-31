# 🔄 ENHANCED SYNC_STATS INTEGRATION GUIDE

## 📋 Overview

Enhanced sync_stats command with time period filtering:
- `!sync_stats` - Default 2 weeks
- `!sync_stats 1day` - Last 24 hours
- `!sync_stats 2weeks` - Last 2 weeks
- `!sync_stats 1month` - Last 30 days
- `!sync_stats 1year` - Last year
- `!sync_stats all` - No filter (everything)

Plus quick shortcuts:
- `!sync_today` - Today only
- `!sync_week` - This week
- `!sync_month` - This month
- `!sync_all` - Everything

---

## 🎯 STEP-BY-STEP INTEGRATION

### **Step 1: Add Helper Functions**

Add these helper functions at the **TOP of the ETLegacyCommands class** (after line 548):

```python
def parse_time_period(self, period_str):
    """
    Parse time period string like '2weeks', '1day', '1month', '1year'
    Returns number of days to look back
    
    Examples:
        '2weeks' -> 14
        '1day' -> 1
        '3days' -> 3
        '1month' -> 30
        '2months' -> 60
        '1year' -> 365
        None or 'all' -> None (no filter)
    """
    if not period_str or period_str.lower() == 'all':
        return None
    
    # Parse pattern: <number><unit>
    match = re.match(r'(\d+)\s*(day|days|week|weeks|month|months|year|years|d|w|m|y)s?', 
                     period_str.lower())
    
    if not match:
        return None
    
    number = int(match.group(1))
    unit = match.group(2)
    
    # Convert to days
    if unit in ('day', 'days', 'd'):
        return number
    elif unit in ('week', 'weeks', 'w'):
        return number * 7
    elif unit in ('month', 'months', 'm'):
        return number * 30  # Approximate
    elif unit in ('year', 'years', 'y'):
        return number * 365  # Approximate
    
    return None

def should_include_file(self, filename, days_back=None):
    """
    Check if a stats file should be included based on date
    
    Filename format: YYYY-MM-DD-HHMMSS-mapname-round-N.txt
    
    Args:
        filename: The stats filename
        days_back: Number of days to look back (None = include all)
    
    Returns:
        True if file should be included, False otherwise
    """
    if days_back is None:
        return True
    
    try:
        # Extract date from filename (YYYY-MM-DD)
        parts = filename.split('-')
        if len(parts) < 3:
            return True  # Can't parse, include it
        
        date_str = '-'.join(parts[:3])
        file_date = datetime.strptime(date_str, '%Y-%m-%d')
        
        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        # Include if file is newer than cutoff
        return file_date >= cutoff_date
        
    except (ValueError, IndexError):
        # If we can't parse the date, include the file
        return True
```

### **Step 2: Replace sync_stats Command**

**FIND** the existing sync_stats command (line 838-1029)

**REPLACE** the command signature from:
```python
async def sync_stats(self, ctx):
```

**TO:**
```python
async def sync_stats(self, ctx, period: str = None):
```

### **Step 3: Update Docstring**

**REPLACE** the docstring from:
```python
"""🔄 Manually sync and process unprocessed stats files from server"""
```

**TO:**
```python
"""
🔄 Manually sync and process stats files from server

Usage:
    !sync_stats              - Sync files from last 2 weeks (default)
    !sync_stats 1day         - Sync files from last 24 hours
    !sync_stats 2days        - Sync files from last 2 days
    !sync_stats 1week        - Sync files from last 7 days
    !sync_stats 2weeks       - Sync files from last 14 days
    !sync_stats 1month       - Sync files from last 30 days
    !sync_stats 3months      - Sync files from last 90 days
    !sync_stats 1year        - Sync files from last year
    !sync_stats all          - Sync ALL unprocessed files (no filter)

Examples:
    !sync_stats 3d           - Last 3 days (shorthand)
    !sync_stats 2w           - Last 2 weeks (shorthand)
    !sync_stats 1m           - Last 1 month (shorthand)
"""
```

### **Step 4: Add Time Period Parsing**

**ADD** this code right after the SSH check (after line 847):

```python
# Parse time period
days_back = self.parse_time_period(period) if period else 14  # Default: 2 weeks

# Build status message
if days_back:
    period_display = f"last {days_back} days"
    if days_back == 1:
        period_display = "last 24 hours"
    elif days_back == 7:
        period_display = "last week"
    elif days_back == 14:
        period_display = "last 2 weeks"
    elif days_back == 30:
        period_display = "last month"
    elif days_back == 365:
        period_display = "last year"
else:
    period_display = "all time (no filter)"
```

### **Step 5: Update Status Message**

**REPLACE** the initial status message (line 850-852) from:
```python
status_msg = await ctx.send(
    "🔄 Checking remote server for new stats files..."
)
```

**TO:**
```python
status_msg = await ctx.send(
    f"🔄 Checking remote server for new stats files...\n"
    f"📅 Time period: **{period_display}**"
)
```

### **Step 6: Add File Filtering**

**ADD** this code right after `remote_files = await self.bot.ssh_list_remote_files(ssh_config)` (after line 864):

```python
# Filter files by time period
if days_back:
    filtered_files = [f for f in remote_files if self.should_include_file(f, days_back)]
    excluded_count = len(remote_files) - len(filtered_files)
    remote_files = filtered_files
    
    if excluded_count > 0:
        await status_msg.edit(
            content=(
                f"🔄 Checking remote server...\n"
                f"📅 Time period: **{period_display}**\n"
                f"📊 Found **{len(remote_files)}** files in period "
                f"({excluded_count} older files excluded)"
            )
        )
```

### **Step 7: Update "No Files" Message**

**REPLACE** (around line 878-882) from:
```python
if not files_to_process:
    await status_msg.edit(
        content="✅ All files are already processed! Nothing new to sync."
    )
    return
```

**TO:**
```python
if not files_to_process:
    await status_msg.edit(
        content=(
            f"✅ All files from {period_display} are already processed!\n"
            f"Nothing new to sync."
        )
    )
    return
```

### **Step 8: Update Download Message**

**REPLACE** (around line 902-904) from:
```python
await status_msg.edit(
    content=f"📥 Downloading {len(files_to_process)} file(s)..."
)
```

**TO:**
```python
await status_msg.edit(
    content=(
        f"📥 Downloading {len(files_to_process)} file(s)...\n"
        f"📅 Period: {period_display}"
    )
)
```

### **Step 9: Update Final Embed**

**ADD** this field to the embed (after line 996, before the Download Phase field):

```python
embed.add_field(
    name="📅 Time Period",
    value=f"**{period_display}**",
    inline=False,
)
```

**AND ADD** footer to embed (before `await status_msg.edit`):

```python
embed.set_footer(text="💡 Tip: Use !sync_stats 1day for today's matches only")
```

### **Step 10: Update "What's Next" Message**

**REPLACE** (around line 1018-1020) from:
```python
value=(
    "Round summaries have been posted above!\n"
    "Use `!last_session` to see full session details."
),
```

**TO:**
```python
value=(
    "Round summaries have been posted above!\n"
    "Use `!last_session` or `!last_session graphs` to see full details."
),
```

### **Step 11: Add Quick Shortcut Commands**

**ADD** these commands right after the sync_stats command (after line 1029):

```python
@commands.command(name="sync_today", aliases=["sync1day"])
async def sync_today(self, ctx):
    """🔄 Quick sync: Today's matches only (last 24 hours)"""
    await self.sync_stats(ctx, period="1day")

@commands.command(name="sync_week", aliases=["sync1week"])
async def sync_week(self, ctx):
    """🔄 Quick sync: This week's matches (last 7 days)"""
    await self.sync_stats(ctx, period="1week")

@commands.command(name="sync_month", aliases=["sync1month"])
async def sync_month(self, ctx):
    """🔄 Quick sync: This month's matches (last 30 days)"""
    await self.sync_stats(ctx, period="1month")

@commands.command(name="sync_all")
async def sync_all(self, ctx):
    """🔄 Quick sync: ALL unprocessed files (no time filter)"""
    await self.sync_stats(ctx, period="all")
```

### **Step 12: Add Import at Top**

**CHECK** if `re` is imported at the top of the file. If not, add:

```python
import re
```

---

## 🧪 TESTING

### **Test Commands:**

```
# Default (2 weeks)
!sync_stats

# Specific periods
!sync_stats 1day
!sync_stats 3days
!sync_stats 1week
!sync_stats 2weeks
!sync_stats 1month
!sync_stats 3months
!sync_stats 1year

# Shorthand
!sync_stats 3d
!sync_stats 2w
!sync_stats 1m
!sync_stats 1y

# Quick shortcuts
!sync_today
!sync_week
!sync_month
!sync_all

# No filter
!sync_stats all
```

---

## ✅ WHAT THIS ADDS

### **User Benefits:**
1. ✅ **Faster syncs** - Only download recent files
2. ✅ **Flexible periods** - Choose exactly what to sync
3. ✅ **Quick shortcuts** - One command for common needs
4. ✅ **Better feedback** - Shows what period is syncing
5. ✅ **Excludes old files** - Shows how many old files skipped

### **Example Output:**
```
🔄 Checking remote server for new stats files...
📅 Time period: last 24 hours

🔄 Checking remote server...
📅 Time period: last 24 hours
📊 Found 6 files in period (142 older files excluded)

📥 Downloading 4 file(s)...
📅 Period: last 24 hours

✅ Stats Sync Complete!

📅 Time Period
last 24 hours

📥 Download Phase
✅ Downloaded: 4 file(s)
❌ Failed: 0 file(s)

⚙️ Processing Phase
✅ Processed: 4 file(s)
❌ Failed: 0 file(s)

💡 What's Next?
Round summaries have been posted above!
Use !last_session or !last_session graphs to see full details.

💡 Tip: Use !sync_stats 1day for today's matches only
```

---

## 📊 SUPPORTED TIME FORMATS

| Format | Meaning | Days |
|--------|---------|------|
| `1day` | Last 24 hours | 1 |
| `2days` | Last 2 days | 2 |
| `1week` | Last 7 days | 7 |
| `2weeks` | Last 14 days | 14 |
| `1month` | Last 30 days | 30 |
| `3months` | Last 90 days | 90 |
| `1year` | Last year | 365 |
| `all` | Everything | ∞ |

**Shorthand:**
- `d` = days
- `w` = weeks
- `m` = months
- `y` = years

**Examples:**
- `3d` = 3 days
- `2w` = 2 weeks
- `6m` = 6 months

---

## 🔧 TROUBLESHOOTING

### **Problem: "No files found"**

**Check:**
- Your date range might be too narrow
- Try `!sync_stats all` to see all files
- Check if files exist on server

### **Problem: "Invalid period format"**

**Valid formats:**
- Number + unit: `2weeks`, `3days`, `1month`
- Shorthand: `2w`, `3d`, `1m`
- Special: `all`

**Invalid:**
- Just numbers: `2`, `14`
- Just units: `week`, `month`

### **Problem: Files still syncing when they shouldn't**

The date filter uses filename dates (YYYY-MM-DD-HHMMSS format).
Files without proper date format will be included by default.

---

## 💡 USAGE TIPS

### **After a 5v5 Match:**
```
!sync_today
```
or
```
!sync_stats 1day
```

### **Weekly Review:**
```
!sync_week
```

### **First Time Setup:**
```
!sync_all
```

### **Regular Maintenance:**
```
!sync_stats 2weeks
```
(This is the default if you just type `!sync_stats`)

---

## 🚀 DEPLOYMENT CHECKLIST

- [ ] Add helper functions to class
- [ ] Update sync_stats signature
- [ ] Update docstring
- [ ] Add time period parsing
- [ ] Update status messages
- [ ] Add file filtering
- [ ] Update embed with period field
- [ ] Add shortcut commands
- [ ] Add `re` import if missing
- [ ] Test with `!sync_stats 1day`
- [ ] Test with `!sync_today`
- [ ] Test with `!sync_all`
- [ ] Verify old files are excluded
- [ ] Check Discord output formatting

---

## 📝 QUICK REFERENCE

**For your 5v5 matches right now:**
```
!sync_today
```

**For regular use:**
```
!sync_stats          # Default: last 2 weeks
```

**For first time:**
```
!sync_all            # Get everything
```

---

**READY TO INTEGRATE!** Follow the steps above and your bot will have flexible time-based sync! 🎮🔥
