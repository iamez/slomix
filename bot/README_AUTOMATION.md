# 🤖 Automation Enhancement Files

This directory contains production-ready automation enhancements for the ET:Legacy Discord Bot.

## 📁 Files Overview

| File | Purpose | Use When |
|------|---------|----------|
| `automation_enhancements.py` | **Main Code** - All automation features | Integrating features into bot |
| `setup_automation.py` | **Setup Script** - Install deps & check config | First time setup |
| `test_automation.py` | **Testing** - Validate setup & integration | Testing/debugging |
| `integrate_automation.py` | **Integration Helper** - Step-by-step guide | Integrating into bot |

## 🚀 Quick Start (5 Steps)

### 1. Install Dependencies
```powershell
pip install psutil
```

### 2. Run Setup
```powershell
python bot/setup_automation.py
```

This will:
- Install required packages
- Check bot files exist
- Validate `.env` configuration
- Create backup directories

### 3. Run Tests
```powershell
python bot/test_automation.py
```

This shows:
- Dependency status
- Configuration status
- Integration progress
- Feature tests

### 4. Integrate Features

**Option A: Follow the guide**
```powershell
python bot/integrate_automation.py
```

**Option B: Manual integration**
- Open `automation_enhancements.py`
- Copy methods to `ultimate_bot.py`
- Follow instructions at bottom

### 5. Test Your Bot
```powershell
python bot/ultimate_bot.py
```

Check startup logs for:
```
✅ Health monitoring task ready
✅ Daily report task ready
✅ Database maintenance task ready
```

## 🎯 What You Get

### 6 Major Enhancements

1. **🏥 Health Monitoring**
   - Runs every 5 minutes
   - Tracks: uptime, errors, memory, CPU, DB stats
   - Sends alerts when issues detected

2. **📊 Daily Reports**
   - Runs at 23:00 CET
   - Posts daily statistics summary
   - Includes bot health status

3. **🔧 Database Maintenance**
   - Runs at 04:00 CET
   - Automatic backups (keeps last 7)
   - Database optimization (VACUUM)
   - Old log cleanup (30+ days)

4. **🔄 Error Recovery**
   - Automatic SSH reconnection
   - Database error recovery
   - Exponential backoff retry
   - Smart error tracking

5. **🚨 Alert System**
   - Sends alerts to admin channel
   - Rate-limited (5-min cooldown)
   - Severity levels: Info/Warning/Critical
   - Actionable error messages

6. **👋 Graceful Shutdown**
   - Saves state before exit
   - Posts maintenance notice
   - Closes connections cleanly
   - Cancels tasks properly

### 4 New Commands

- `!health` - Show bot health status
- `!backup` - Manual database backup (admin)
- `!vacuum` - Optimize database (admin)
- `!errors` - Show error statistics

## 📚 Documentation

### For Quick Reference
- `README_AUTOMATION.md` (this file) - Quick start

### For Complete Guide
- `../PRODUCTION_AUTOMATION_GUIDE.md` - Full documentation
- `../AUTOMATION_SETUP_GUIDE.md` - Original automation guide

### For Integration
- `automation_enhancements.py` - Code + instructions at bottom
- `integrate_automation.py` - Step-by-step helper

## 🔧 Configuration

Add to your `.env` file:

```bash
# Admin channel for health alerts
ADMIN_CHANNEL_ID=your_channel_id

# Optional: Adjust if needed
AUTOMATION_ENABLED=true
SSH_ENABLED=true
```

## 🧪 Testing

### Test Individual Features

```powershell
# Check setup
python bot/test_automation.py

# Check integration status
python bot/test_automation.py | findstr "Integration"

# Check dependencies
python bot/test_automation.py | findstr "Dependencies"
```

### Test In Production

After integrating, test in Discord:

```
!health          # Check bot health
!errors          # View error stats
!backup          # Test backup (admin only)
```

## 📊 Daily Schedule

Once integrated, your bot will:

| Time | Task |
|------|------|
| **04:00 CET** | Database backup + maintenance |
| **23:00 CET** | Daily statistics report |
| **Every 5 min** | Health monitoring |
| **Every 30 sec** | SSH monitoring (if active) |

## 🛠️ Troubleshooting

### Setup Issues

**Problem:** `psutil` not installing
```powershell
python -m pip install --upgrade pip
pip install psutil
```

**Problem:** Can't find bot files
```powershell
# Make sure you're in project root
cd C:\Users\seareal\Documents\stats
python bot/setup_automation.py
```

### Integration Issues

**Problem:** Don't know where to add code
```powershell
# Run the integration helper
python bot/integrate_automation.py
```

**Problem:** Syntax errors after integration
- Make sure indentation is correct (4 spaces)
- Check for missing imports at top of file
- Verify all parentheses are balanced

### Runtime Issues

**Problem:** Tasks not starting
- Check logs for "task ready" messages
- Verify tasks are started in `on_ready()` or `setup_hook()`
- Make sure `psutil` is installed

**Problem:** Alerts not working
- Check `ADMIN_CHANNEL_ID` in `.env`
- Verify bot has permissions in admin channel
- Check error count hasn't exceeded alert cooldown

## 📈 Success Criteria

After running for a week, you should see:

- ✅ Zero manual intervention needed
- ✅ Daily backups being created
- ✅ Daily reports posting at 23:00
- ✅ Health checks every 5 minutes
- ✅ Low error count (<10 per day)
- ✅ Automatic error recovery working
- ✅ Clean, organized logs

## 🎯 Integration Checklist

- [ ] Install `psutil` package
- [ ] Run `setup_automation.py`
- [ ] Configure `ADMIN_CHANNEL_ID` in `.env`
- [ ] Add health monitoring init to `__init__`
- [ ] Copy background tasks from `automation_enhancements.py`
- [ ] Start tasks in `on_ready()` or `setup_hook()`
- [ ] Add admin commands
- [ ] Test with `test_automation.py`
- [ ] Run bot and verify startup messages
- [ ] Test `!health` command in Discord
- [ ] Monitor for 24 hours
- [ ] Check daily report posts
- [ ] Verify backups are created

## 💡 Tips

### Before Integration
1. Create a backup of `ultimate_bot.py`
2. Test in development environment first
3. Read through `automation_enhancements.py` completely

### During Integration
1. Add features one at a time
2. Test after each addition
3. Check logs frequently

### After Integration
1. Monitor for first 24 hours
2. Check `!health` regularly
3. Verify backups are created
4. Review error logs
5. Adjust thresholds if needed

## 🆘 Need Help?

1. **Check logs:** `bot/logs/`
2. **Run tests:** `python bot/test_automation.py`
3. **Review guide:** `../PRODUCTION_AUTOMATION_GUIDE.md`
4. **Check integration:** Look for "task ready" in logs

## 📝 Next Steps

After successful integration:

1. **Week 1:** Monitor closely, check health daily
2. **Week 2:** Verify backups and reports working
3. **Week 3:** Review error patterns, adjust thresholds
4. **Week 4:** Consider it production-ready! 🎉

---

**Ready to start?**

```powershell
# Step 1: Setup
python bot/setup_automation.py

# Step 2: Test
python bot/test_automation.py

# Step 3: Integrate
python bot/integrate_automation.py

# Step 4: Run!
python bot/ultimate_bot.py
```

**Good luck! Your bot is about to become fully autonomous!** 🤖✨
