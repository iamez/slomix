# ✅ Automation Integration Checklist

Use this checklist to track your progress integrating the automation enhancements.

---

## 📦 Phase 1: Setup & Preparation

### Dependencies

- [ ] Installed `psutil` package

  ```powershell
  pip install psutil
  ```

- [ ] Verified all other dependencies exist (discord.py, aiosqlite)
- [ ] Ran `python bot/test_automation.py` successfully

### Configuration

- [ ] Created/updated `.env` file from `.env.example`
- [ ] Added `ADMIN_CHANNEL_ID` to `.env`
- [ ] Verified `AUTOMATION_ENABLED=true` in `.env`
- [ ] Verified `SSH_ENABLED=true` in `.env` (if using SSH)
- [ ] Verified `GAMING_VOICE_CHANNELS` configured (if using voice detection)

### Files & Backups

- [ ] Created backup of `bot/ultimate_bot.py`
- [ ] Verified `bot/etlegacy_production.db` exists
- [ ] Created `bot/backups/` directory (for automatic backups)
- [ ] Created `bot/logs/` directory (if not exists)

---

## 🔧 Phase 2: Code Integration

### Imports (at top of ultimate_bot.py)

- [ ] Added `import psutil` with other imports

### Initialization (in `__init__` method)

- [ ] Added health monitoring variables after `self.error_count = 0`:

  ```python
  # 🏥 Health Monitoring System
  self.bot_start_time = datetime.now()
  self.last_health_check = None
  self.last_db_backup = None
  self.last_stats_post = None
  self.ssh_error_count = 0
  self.db_error_count = 0
  self.processed_files_count = 0
  self.last_error_alert_time = None
  self.error_alert_cooldown = 300
  
  # Task health tracking
  self.task_last_run = {}
  self.task_run_counts = {}
  self.task_errors = {}
  
  # Admin channel
  self.admin_channel_id = int(os.getenv("ADMIN_CHANNEL_ID", self.stats_channel_id))
  ```text

### Core Methods (add these methods to ETStatsBot class)

- [ ] Copied `get_bot_health_status()` method
- [ ] Copied `send_health_alert()` method
- [ ] Copied `backup_database()` method
- [ ] Copied `vacuum_database()` method
- [ ] Copied `cleanup_old_logs()` method
- [ ] Copied `post_daily_summary()` method
- [ ] Copied `recover_from_ssh_error()` method
- [ ] Copied `recover_from_db_error()` method
- [ ] Copied `graceful_shutdown()` method

### Background Tasks (add after existing @tasks.loop definitions)

- [ ] Added `health_monitor_task()` (runs every 5 min)
- [ ] Added `daily_report_task()` (runs at 23:00 CET)
- [ ] Added `database_maintenance_task()` (runs at 04:00 CET)

### Task Startup (in `on_ready()` or `setup_hook()`)

- [ ] Added task starts:

  ```python
  self.loop.create_task(self.health_monitor_task())
  self.loop.create_task(self.daily_report_task())
  self.loop.create_task(self.database_maintenance_task())
  ```python

### Admin Commands (create new Cog or add to bot)

- [ ] Added `!health` command
- [ ] Added `!backup` command
- [ ] Added `!vacuum` command
- [ ] Added `!errors` command

### Shutdown Handler (modify or add `close()` method)

- [ ] Added call to `graceful_shutdown()` in close method

### Error Recovery Integration (in existing error handlers)

- [ ] Updated SSH error handling to call `recover_from_ssh_error()`
- [ ] Updated DB error handling to call `recover_from_db_error()`

---

## 🧪 Phase 3: Testing

### Startup Testing

- [ ] Bot starts without errors
- [ ] Saw log message: "✅ Health monitoring task ready"
- [ ] Saw log message: "✅ Daily report task ready"
- [ ] Saw log message: "✅ Database maintenance task ready"
- [ ] No Python syntax errors or import errors

### Command Testing

- [ ] Tested `!health` command in Discord
  - [ ] Shows bot status
  - [ ] Shows uptime
  - [ ] Shows error counts
  - [ ] Shows database stats
  - [ ] Shows resource usage
  - [ ] Shows task statuses
- [ ] Tested `!errors` command
  - [ ] Shows error statistics
  - [ ] Shows task errors (if any)
- [ ] Tested `!backup` command (admin)
  - [ ] Creates backup file
  - [ ] Posts confirmation
  - [ ] Backup exists in `bot/backups/`
- [ ] Tested `!vacuum` command (admin)
  - [ ] Runs successfully
  - [ ] Posts confirmation

### Background Task Testing

- [ ] Waited 5 minutes, checked logs for health check
- [ ] Health check completed successfully
- [ ] No errors in health check logs

---

## 📊 Phase 4: 24-Hour Validation

### Day 1 Checks

- [ ] Bot ran for 24 hours without crashes
- [ ] Health checks ran every 5 minutes (288 checks per day)
- [ ] Daily report posted at 23:00 CET
- [ ] Database maintenance ran at 04:00 CET
- [ ] Backup created in `bot/backups/`
- [ ] No critical alerts sent
- [ ] Error count stayed low (<10)

### Monitoring

- [ ] Checked `!health` multiple times
- [ ] Reviewed log files for errors
- [ ] Verified database backups exist
- [ ] Checked disk space is adequate

---

## 🚀 Phase 5: Week-Long Production Testing

### Weekly Checks

- [ ] **Day 1:** Initial 24-hour test passed
- [ ] **Day 2:** Normal operation, no issues
- [ ] **Day 3:** Reviewed error patterns
- [ ] **Day 4:** Verified backup rotation (keeping 7)
- [ ] **Day 5:** Checked log cleanup working
- [ ] **Day 6:** Monitored resource usage
- [ ] **Day 7:** Final health check

### Validation Criteria

- [ ] 7 daily reports posted (at 23:00 each day)
- [ ] 7 database backups created (at 04:00 each day)
- [ ] ~2,000 health checks completed (288/day × 7)
- [ ] Total error count < 50 for the week
- [ ] No critical failures requiring manual intervention
- [ ] SSH monitoring working (if enabled)
- [ ] Voice detection working (if enabled)
- [ ] Database size stable and optimized

---

## 🎯 Phase 6: Production Ready

### Final Validation

- [ ] Bot has run continuously for 1 week
- [ ] All automation features working correctly
- [ ] Error recovery tested and working
- [ ] Backups being created and rotated
- [ ] Daily reports posting consistently
- [ ] Health monitoring catching issues
- [ ] Admin commands all functional
- [ ] Documentation reviewed and understood

### Tuning (if needed)

- [ ] Adjusted health check frequency (if desired)
- [ ] Adjusted error alert thresholds (if needed)
- [ ] Adjusted backup retention (if desired)
- [ ] Adjusted log cleanup age (if desired)

### Documentation

- [ ] Documented any custom changes made
- [ ] Noted any issues encountered and solutions
- [ ] Created runbook for common issues
- [ ] Shared results with team (if applicable)

---

## 🎉 Success Criteria

**Your automation is production-ready when:**

✅ Bot runs unattended for 7 days without manual intervention  
✅ All scheduled tasks execute successfully  
✅ Error recovery works automatically  
✅ Health monitoring detects and alerts issues  
✅ Database maintenance happens automatically  
✅ Daily reports post consistently  
✅ Admin commands work correctly  
✅ Resource usage is stable  
✅ Logs are clean and organized  
✅ You're confident in the system!  

---

## 📝 Notes & Issues

Use this space to track any issues or customizations:

```yaml
Date: ___________
Issue: 


Solution:


---

Date: ___________
Issue:


Solution:


---

Date: ___________
Customization:


Reason:


---
```

---

## 🆘 Troubleshooting Quick Reference

| Issue | Check | Solution |
|-------|-------|----------|
| Tasks not starting | Logs on startup | Verify tasks started in `on_ready()` |
| !health not working | Command registered | Check command definition and permissions |
| Alerts not sending | Admin channel ID | Verify `ADMIN_CHANNEL_ID` in `.env` |
| Backups not created | Backup directory | Create `bot/backups/` directory |
| High error count | Error logs | Review specific errors and fix root cause |
| Tasks showing stopped | Task status | Check for task crashes in logs |
| Daily report not posting | Timezone | Verify pytz/zoneinfo installed |
| Database not optimizing | VACUUM errors | Check database permissions |

---

## 📚 Documentation Reference

- **Quick Start:** `bot/README_AUTOMATION.md`
- **Full Guide:** `PRODUCTION_AUTOMATION_GUIDE.md`
- **Architecture:** `bot/automation_architecture.py`
- **Summary:** `AUTOMATION_SUMMARY.md`
- **Code:** `bot/automation_enhancements.py`

---

## ✨ Congratulations

When all boxes are checked, your bot is **production-ready** and can run autonomously for weeks or months!

**Date Completed:** ___________  
**Notes:**

---

*Keep this checklist for reference and future deployments!*
