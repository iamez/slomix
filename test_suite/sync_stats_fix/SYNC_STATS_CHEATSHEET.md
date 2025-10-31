# 🎮 SYNC_STATS QUICK REFERENCE

## 🚀 FOR YOUR 5v5 MATCH RIGHT NOW

After your match finishes, just type in Discord:

```
!sync_today
```

or

```
!sync_stats 1day
```

Then check your stats:

```
!last_session
!last_session graphs
```

---

## 📋 ALL AVAILABLE COMMANDS

### **Main Command (with period)**
```
!sync_stats              # Default: last 2 weeks
!sync_stats 1day         # Last 24 hours
!sync_stats 2days        # Last 2 days  
!sync_stats 3days        # Last 3 days
!sync_stats 1week        # Last 7 days
!sync_stats 2weeks       # Last 14 days
!sync_stats 1month       # Last 30 days
!sync_stats 3months      # Last 90 days
!sync_stats 1year        # Last year
!sync_stats all          # Everything (no filter)
```

### **Shorthand (quicker to type)**
```
!sync_stats 1d           # 1 day
!sync_stats 3d           # 3 days
!sync_stats 1w           # 1 week
!sync_stats 2w           # 2 weeks
!sync_stats 1m           # 1 month
!sync_stats 1y           # 1 year
```

### **Quick Shortcuts**
```
!sync_today              # Today only (24 hours)
!sync_week               # This week (7 days)
!sync_month              # This month (30 days)
!sync_all                # Everything (no filter)
```

---

## 💡 WHEN TO USE WHAT

| Scenario | Command | Why |
|----------|---------|-----|
| **Just finished a match** | `!sync_today` | Get today's matches fast |
| **Weekly game night** | `!sync_week` | Get this week's sessions |
| **Monthly review** | `!sync_month` | Check the whole month |
| **First time setup** | `!sync_all` | Get all historical data |
| **Regular maintenance** | `!sync_stats` | Default 2 weeks is good |
| **Server was down** | `!sync_stats 3days` | Catch up last few days |

---

## 📊 WHAT YOU'LL SEE

### **Step 1: Checking**
```
🔄 Checking remote server for new stats files...
📅 Time period: last 24 hours
```

### **Step 2: Found Files**
```
🔄 Checking remote server...
📅 Time period: last 24 hours
📊 Found 6 files in period (142 older files excluded)
```

### **Step 3: Downloading**
```
📥 Downloading 4 file(s)...
📅 Period: last 24 hours
```

### **Step 4: Processing**
```
⚙️ Processing 4 file(s) for database import...
```

### **Step 5: Complete!**
```
✅ Stats Sync Complete!

📅 Time Period: last 24 hours
📥 Download: ✅ 4 files | ❌ 0 failed
⚙️ Processing: ✅ 4 files | ❌ 0 failed

💡 What's Next?
Use !last_session or !last_session graphs to see full details.
```

---

## ⚡ QUICK WORKFLOW

### **After Every Match:**
```bash
# In Discord:
!sync_today              # Sync today's matches
!last_session graphs     # See beautiful stats
```

### **Weekly Review:**
```bash
!sync_week               # Sync this week
!leaderboard             # Check rankings
!stats <your_name>       # Your personal stats
```

### **First Time:**
```bash
!sync_all                # Get everything
!last_session            # Check latest session
```

---

## 🎯 EXAMPLES

### **Example 1: Just played a 5v5**
```
You: !sync_today
Bot: 🔄 Checking remote server...
     📅 Time period: last 24 hours
     📊 Found 2 files in period
     
     [Downloads and processes files]
     
     ✅ Stats Sync Complete!
     
You: !last_session graphs
Bot: [Posts beautiful retro visualization]
     [Posts primary text stats]
     [Posts detailed text stats]
```

### **Example 2: Weekly game night**
```
You: !sync_week
Bot: 🔄 Checking remote server...
     📅 Time period: last 7 days
     📊 Found 14 files in period (89 older files excluded)
     
     [Processes all files]
     
     ✅ Stats Sync Complete!
     
You: !leaderboard
Bot: [Shows top players from this week]
```

### **Example 3: Need last 3 days**
```
You: !sync_stats 3d
Bot: 🔄 Checking remote server...
     📅 Time period: last 3 days
     📊 Found 8 files in period
     
     [Processes files]
     
     ✅ Stats Sync Complete!
```

---

## 🔥 PRO TIPS

1. **Use shortcuts for speed**
   - `!sync_today` is faster than `!sync_stats 1day`

2. **Smaller periods = faster syncs**
   - `!sync_today` processes 2-4 files
   - `!sync_all` might process 1000+ files

3. **Default is smart**
   - Just `!sync_stats` does 2 weeks (good balance)

4. **After server downtime**
   - Use `!sync_stats 3days` to catch up

5. **First time setup**
   - `!sync_all` to get all history

---

## ❓ FAQ

**Q: What's the default if I just type `!sync_stats`?**
A: Last 2 weeks (14 days)

**Q: How do I get ALL files?**
A: `!sync_stats all` or `!sync_all`

**Q: What's fastest for today's matches?**
A: `!sync_today` (shortcut for 1 day)

**Q: Can I use hours?**
A: No, minimum is 1 day. Use `!sync_stats 1day` or `!sync_today`

**Q: Files are already processed?**
A: That's good! The bot tracks what's processed. Nothing to sync.

**Q: How do I see the stats after syncing?**
A: `!last_session` or `!last_session graphs`

---

## 🎮 FOR YOUR CURRENT 5v5 MATCH

**Right now, do this:**

```
!sync_today
```

**Wait for it to finish, then:**

```
!last_session graphs
```

**You'll get:**
- ✨ Beautiful retro sci-fi visualization
- 📊 Primary stats tables
- 📋 Detailed stats breakdown
- 🏆 All the glory!

---

**TL;DR:** After your match, just type `!sync_today` then `!last_session graphs` 🎯🔥
