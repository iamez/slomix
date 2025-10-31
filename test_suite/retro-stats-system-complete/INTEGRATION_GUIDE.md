# 🎮 COMPLETE INTEGRATION GUIDE: RETRO STATS SYSTEM
## Visualization + Text Stats for ET:Legacy Discord Bot

---

## 📋 OVERVIEW

You now have TWO complete systems:
1. **Retro Visualization** (6-panel sci-fi graphic) - `retro_viz_v2.py`
2. **Text Stats Output** (2 versions) - `retro_text_stats.py`

Both should be posted together in Discord when users run `!last_session graphs`

---

## 🎯 EXPECTED USER EXPERIENCE

When user types: `!last_session graphs`

**Bot should post:**
1. Retro visualization PNG (the 6-panel sci-fi graphic)
2. Primary text stats (matches the visualization data)
3. Detailed text stats (all remaining data fields)

**For each round, then map summary, then session summary.**

---

## 📂 FILE STRUCTURE

```
bot/
├── retro_viz.py          # Visualization generator (6-panel)
├── retro_text_stats.py   # Text stats generator (both versions)
└── ultimate_bot.py       # Main bot (integrate here)
```

---

## 💻 INTEGRATION CODE

### **Step 1: Import the modules**

Add to top of `ultimate_bot.py`:

```python
from bot.retro_viz import create_round_visualization
from bot.retro_text_stats import generate_text_stats
import matplotlib.pyplot as plt
import io
```

---

### **Step 2: Create helper function for posting round stats**

Add this function to the `ETLegacyCommands` cog:

```python
async def _post_retro_round_complete(self, ctx, stats_file_path, map_name, round_num):
    """
    Post complete retro stats package:
    1. Visualization (PNG)
    2. Primary text stats
    3. Detailed text stats
    """
    
    try:
        # ========== GENERATE VISUALIZATION ==========
        try:
            fig = create_round_visualization(stats_file_path)
            
            # Convert to buffer
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=150, 
                       facecolor='#0a1f3d', bbox_inches='tight')
            buf.seek(0)
            plt.close(fig)
            
            # Post visualization
            filename = f"{map_name}_round{round_num}_retro.png"
            file = discord.File(buf, filename=filename)
            await ctx.send(file=file)
            
        except Exception as e:
            logger.error(f"Error creating visualization: {e}")
            await ctx.send(f"⚠️ Could not generate visualization for {map_name} R{round_num}")
        
        # Small delay between image and text
        await asyncio.sleep(1)
        
        # ========== GENERATE TEXT STATS ==========
        try:
            primary_text, detailed_text = generate_text_stats(stats_file_path)
            
            if primary_text:
                # Post primary stats (matches visualization)
                await ctx.send(f"**📊 PRIMARY STATS - {map_name.upper()} R{round_num}**")
                await ctx.send(primary_text)
            
            if detailed_text:
                # Post detailed stats (all extra data)
                await ctx.send(f"**📋 DETAILED STATS - {map_name.upper()} R{round_num}**")
                await ctx.send(detailed_text)
                
        except Exception as e:
            logger.error(f"Error creating text stats: {e}")
            await ctx.send(f"⚠️ Could not generate text stats for {map_name} R{round_num}")
        
        # Delay before next round/map
        await asyncio.sleep(2)
        
    except Exception as e:
        logger.error(f"Error posting retro stats: {e}")
        await ctx.send(f"❌ Error generating stats for {map_name} R{round_num}: {e}")
```

---

### **Step 3: Modify the !last_session graphs command**

Find the `!last_session graphs` section (around line 5324) and replace with:

```python
if subcommand and subcommand.lower() in ("graphs", "graph", "charts"):
    try:
        # Progress message
        progress_msg = await ctx.send(
            f"📊 **Generating Complete Statistics Package**\n"
            f"Session Date: `{latest_date}`\n"
            f"Maps: `{len(maps_aggregates)}`\n"
            f"⏳ *Generating visualizations and detailed text stats...*"
        )
        
        # Prepare map -> sessions mapping
        maps_to_sessions = {}
        for sid, mname, rnd, atime in sessions:
            maps_to_sessions.setdefault(mname, []).append((sid, rnd))
        
        # Track stats files to process
        stats_files_to_process = []
        
        # Get stats file paths for each session
        # Assuming you have access to stats files directory
        stats_dir = Path("/path/to/gamestats")  # UPDATE THIS PATH
        
        for map_name in maps_to_sessions.keys():
            sessions_for_map = maps_to_sessions[map_name]
            
            for sid, rnd in sessions_for_map:
                # Find matching stats file
                # Format: YYYY-MM-DD-HHMMSS-mapname-round-N.txt
                pattern = f"*{map_name}*round-{rnd}.txt"
                matching_files = list(stats_dir.glob(pattern))
                
                if matching_files:
                    # Use most recent file
                    stats_file = sorted(matching_files)[-1]
                    stats_files_to_process.append({
                        'file': stats_file,
                        'map_name': map_name,
                        'round_num': rnd,
                        'session_id': sid
                    })
        
        # Process each round
        for idx, item in enumerate(stats_files_to_process, 1):
            await ctx.send(
                f"**━━━━━━━━━━━━━━━━━━━━━━━━━━**\n"
                f"**{idx}/{len(stats_files_to_process)}: {item['map_name'].upper()} - ROUND {item['round_num']}**\n"
                f"**━━━━━━━━━━━━━━━━━━━━━━━━━━**"
            )
            
            await self._post_retro_round_complete(
                ctx,
                str(item['file']),
                item['map_name'],
                item['round_num']
            )
        
        # Update progress message
        await progress_msg.edit(
            content=f"✅ **Complete! Generated {len(stats_files_to_process)} stat packages**"
        )
        
        return
        
    except Exception as e:
        logger.exception(f"Error generating graphs: {e}")
        await ctx.send(f"❌ Error generating statistics: {e}")
        return
```

---

## 🗂️ STATS FILE HANDLING

### **Option A: If stats files are stored locally**

```python
# Define stats directory
STATS_DIR = Path("/path/to/gamestats")

# Find stats file for specific round
def find_stats_file(map_name, round_num, date=None):
    """Find stats file matching criteria"""
    pattern = f"*{map_name}*round-{round_num}.txt"
    
    if date:
        pattern = f"{date}-*{map_name}*round-{round_num}.txt"
    
    files = list(STATS_DIR.glob(pattern))
    return sorted(files)[-1] if files else None
```

### **Option B: If stats files are in database/uploaded**

```python
# Query database for stats file content
async def get_stats_file_for_session(session_id, round_num):
    """Retrieve stats file from DB or recreate from session data"""
    async with aiosqlite.connect(self.bot.db_path) as db:
        # Query session data
        query = """
            SELECT map_name, round_number, session_date
            FROM sessions
            WHERE id = ?
        """
        async with db.execute(query, (session_id,)) as cur:
            result = await cur.fetchone()
            
        if not result:
            return None
        
        map_name, round_num, date = result
        
        # Reconstruct or fetch stats file path
        # ...implementation depends on your setup
```

---

## 📝 TEXT FORMATTING FOR DISCORD

The text stats use ANSI color codes in code blocks. Discord supports this with:

```python
# ANSI colors work in Discord code blocks
message = "```ansi\n\x1b[36mCyan Text\x1b[0m\n```"
await ctx.send(message)
```

**Color codes used:**
- `\x1b[36m` = Cyan (headers)
- `\x1b[32m` = Green (positive stats)
- `\x1b[33m` = Yellow (warnings/important)
- `\x1b[31m` = Red (damage/deaths)
- `\x1b[35m` = Magenta (special)
- `\x1b[0m` = Reset

---

## 🎨 CUSTOMIZATION OPTIONS

### **Change colors in text output:**

Edit `retro_text_stats.py`:

```python
COLORS = {
    'cyan': '```ansi\n\x1b[36m',    # Change to other codes
    'green': '```ansi\n\x1b[32m',
    # etc...
}
```

### **Change emojis:**

Edit `retro_text_stats.py`:

```python
EMOJI = {
    'kill': '💀',    # Change to any emoji
    'medal': '🏆',
    # etc...
}
```

### **Adjust table widths:**

In each table creation function, adjust the `widths` array:

```python
cols = ['Player', 'Kills', 'Deaths']
widths = [25, 10, 10]  # Change these numbers
```

---

## 🧪 TESTING

### **Test locally:**

```bash
# Test visualization
python bot/retro_viz.py /path/to/stats-file.txt

# Test text stats
python bot/retro_text_stats.py /path/to/stats-file.txt

# Check outputs
cat stats_primary.txt
cat stats_detailed.txt
```

### **Test in Discord:**

1. Start bot: `python ultimate_bot.py`
2. Run: `!last_session graphs`
3. Verify:
   - ✅ PNG visualization appears
   - ✅ Primary text stats appear
   - ✅ Detailed text stats appear
   - ✅ All sections formatted correctly
   - ✅ No errors in console

---

## 🔧 TROUBLESHOOTING

### **Problem: Visualization won't generate**

```python
# Check matplotlib installation
pip install matplotlib --break-system-packages

# Check file parsing
result = parse_stats_file_simple('/path/to/file.txt')
print(result)  # Should show player data
```

### **Problem: Text is cut off**

Discord has message limits (2000 chars). Split long messages:

```python
# Split text if too long
def split_message(text, max_len=1900):
    """Split text into chunks for Discord"""
    lines = text.split('\n')
    chunks = []
    current = []
    current_len = 0
    
    for line in lines:
        if current_len + len(line) > max_len:
            chunks.append('\n'.join(current))
            current = [line]
            current_len = len(line)
        else:
            current.append(line)
            current_len += len(line) + 1
    
    if current:
        chunks.append('\n'.join(current))
    
    return chunks

# Usage
for chunk in split_message(primary_text):
    await ctx.send(chunk)
```

### **Problem: Stats files not found**

```python
# Debug file paths
print(f"Looking for: {pattern}")
print(f"In directory: {stats_dir}")
print(f"Found files: {list(stats_dir.glob('*.txt'))}")
```

---

## ✅ SUCCESS CRITERIA

When working correctly, users should see:

1. **Progress message** appears
2. **For each map:**
   - Round 1: Image → Primary text → Detailed text
   - Round 2: Image → Primary text → Detailed text
3. **Completion message** appears
4. **No errors** in console
5. **All text formatted** with colors and tables
6. **All images render** properly

---

## 📊 OUTPUT EXAMPLES

### **What users will see:**

```
📊 Generating Complete Statistics Package
Session Date: 2025-10-30
Maps: 3
⏳ Generating visualizations and detailed text stats...

━━━━━━━━━━━━━━━━━━━━━━━━━━
1/6: TE_ESCAPE2 - ROUND 1
━━━━━━━━━━━━━━━━━━━━━━━━━━

[IMAGE: 6-panel retro visualization]

📊 PRIMARY STATS - TE_ESCAPE2 R1

[Formatted text tables with ANSI colors]

📋 DETAILED STATS - TE_ESCAPE2 R1

[More formatted text tables]

━━━━━━━━━━━━━━━━━━━━━━━━━━
2/6: TE_ESCAPE2 - ROUND 2
━━━━━━━━━━━━━━━━━━━━━━━━━━

[Repeat...]

✅ Complete! Generated 6 stat packages
```

---

## 🚀 DEPLOYMENT CHECKLIST

- [ ] Copy `retro_viz_v2.py` to `bot/retro_viz.py`
- [ ] Copy `retro_text_stats.py` to `bot/retro_text_stats.py`
- [ ] Update `ultimate_bot.py` with integration code
- [ ] Set correct `STATS_DIR` path
- [ ] Test with one stats file locally
- [ ] Test `!last_session graphs` in Discord
- [ ] Verify all colors/formatting work
- [ ] Check console for errors
- [ ] Test with multiple maps
- [ ] Verify message splitting if needed

---

## 💡 FUTURE ENHANCEMENTS

1. **Add map summary** after each map's rounds
2. **Add session summary** at the end
3. **Player comparison mode** (2 players side-by-side)
4. **Weapon breakdown visualization**
5. **Interactive buttons** (React to see detailed stats)
6. **Save to file option** (DM user a PDF)
7. **Leaderboard across multiple sessions**

---

## 📞 SUPPORT

If something breaks:
1. Check console logs
2. Verify stats file format
3. Test parsers individually
4. Check Discord API limits
5. Review error messages carefully

---

**READY TO INTEGRATE!** Follow the steps above and your bot will have awesome retro stats! 🎮🔥
