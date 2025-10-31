# ✅ V2 Deployment Checklist

Quick checklist to deploy the new bot successfully.

## Pre-Deployment (5 minutes)

### 1. Backup Everything
- [ ] Backup current bot: `cp ultimate_bot_FINAL.py ultimate_bot_FINAL.py.backup`
- [ ] Backup database: `cp etlegacy_production.db etlegacy_production.db.backup`
- [ ] Backup .env file: `cp .env .env.backup`

### 2. Prepare New Bot
- [ ] Copy `ultimate_bot_v2.py` to your bot directory
- [ ] Copy `requirements.txt` to your bot directory
- [ ] Copy `.env.example` and verify your `.env` matches
- [ ] Copy `backfill_aliases.py` to your bot directory

### 3. Stop Current Bot
```bash
# Systemd
sudo systemctl stop etlegacy-bot

# Or screen/tmux
screen -r etlegacy-bot
# Ctrl+C
# Ctrl+A, D
```

## Deployment (10 minutes)

### 4. Install/Update Dependencies
```bash
pip install -r requirements.txt --upgrade
```

### 5. Run Database Backfill ⭐ CRITICAL
```bash
python3 backfill_aliases.py
```

**This populates player_aliases table from historical data!**

Expected output:
```
✅ Backfilled X aliases!
```

### 6. Test Bot Locally
```bash
python3 ultimate_bot_v2.py
```

Check for:
- [ ] "Bot is online!" message
- [ ] "Commands cog loaded" message
- [ ] No error messages

Press Ctrl+C to stop after verification.

### 7. Deploy to Production
```bash
# Option A: Systemd
sudo systemctl start etlegacy-bot
sudo systemctl status etlegacy-bot

# Option B: Screen
screen -S etlegacy-bot
python3 ultimate_bot_v2.py
# Ctrl+A, D to detach
```

## Post-Deployment Testing (5 minutes)

### 8. Test Core Commands

In Discord, run:

```
!ping
```
Expected: ✅ Bot responds with latency

```
!help_command
```
Expected: ✅ Shows all commands including !list_guids

```
!stats YourPlayerName
```
Expected: ✅ Finds player and shows stats

```
!list_guids
```
Expected: ✅ Shows unlinked players (if any)

```
!link YourPlayerName
```
Expected: ✅ Shows search results and options

### 9. Test Linking Flow

```
# Self-link
!link ABC12345
```
Expected: ✅ Shows confirmation, react with ✅

```
# Verify link worked
!stats
```
Expected: ✅ Shows YOUR stats

```
# Admin link (admin only)
!link @user ABC12345
```
Expected: ✅ Links other user

### 10. Verify Alias Tracking

Process a game or wait for auto-sync, then check:

```bash
tail -f logs/ultimate_bot.log
```

Look for:
- [ ] "✅ Updated alias: PlayerName for GUID ABC12345"

This confirms automatic alias tracking is working!

## Monitoring (Ongoing)

### 11. Watch Logs
```bash
# Real-time
tail -f logs/ultimate_bot.log

# Last 100 lines
tail -n 100 logs/ultimate_bot.log

# Search for errors
grep "ERROR" logs/ultimate_bot.log
```

### 12. Check Database
```bash
# Count aliases (should be > 0)
sqlite3 etlegacy_production.db "SELECT COUNT(*) FROM player_aliases;"

# Check recent links
sqlite3 etlegacy_production.db "SELECT * FROM player_links ORDER BY linked_date DESC LIMIT 5;"
```

## Rollback Plan (If Needed)

If something goes wrong:

```bash
# Stop new bot
sudo systemctl stop etlegacy-bot

# Restore old bot
cp ultimate_bot_FINAL.py.backup ultimate_bot.py

# Restore database if modified
cp etlegacy_production.db.backup etlegacy_production.db

# Restart
sudo systemctl start etlegacy-bot
```

## Success Criteria

Deployment is successful when:

- ✅ Bot starts without errors
- ✅ All commands respond
- ✅ !stats finds players by name
- ✅ !link works interactively
- ✅ !list_guids shows unlinked players
- ✅ Logs show "Updated alias" messages
- ✅ No increase in error rate

## Common Issues & Solutions

### Issue: Bot won't start
**Solution:**
```bash
# Check token
echo $DISCORD_BOT_TOKEN

# Check dependencies
pip install -r requirements.txt

# Check logs
cat logs/ultimate_bot.log
```

### Issue: "Module not found: community_stats_parser"
**Solution:**
```bash
# Verify file exists
ls -l community_stats_parser.py

# Check Python path
python3 -c "import sys; print('\n'.join(sys.path))"
```

### Issue: !stats can't find players
**Solution:**
```bash
# Run backfill
python3 backfill_aliases.py

# Verify aliases
sqlite3 etlegacy_production.db "SELECT COUNT(*) FROM player_aliases;"
```

### Issue: !list_guids shows no one
**Solution:**
Either everyone is linked (good!) or:
```bash
# Check if aliases exist
sqlite3 etlegacy_production.db "SELECT COUNT(*) FROM player_aliases;"

# Check if anyone is unlinked
sqlite3 etlegacy_production.db "SELECT COUNT(*) FROM player_aliases pa WHERE pa.guid NOT IN (SELECT et_guid FROM player_links);"
```

## Next Steps After Deployment

### Day 1-2: Monitor Closely
- [ ] Check logs hourly
- [ ] Test all commands
- [ ] Get user feedback

### Day 3-7: Normal Operation
- [ ] Check logs daily
- [ ] Monitor error rate
- [ ] Document any issues

### Week 2+: Train Admins
- [ ] Show !list_guids workflow
- [ ] Demonstrate faster linking
- [ ] Share new features

### Month 1: Optimization
- [ ] Review performance
- [ ] Adjust cache TTL if needed
- [ ] Add any custom features

## Documentation Reference

- **Full feature list:** README_V2.md
- **Migration details:** MIGRATION_GUIDE.md
- **Change log:** CHANGES.md
- **This checklist:** DEPLOYMENT_CHECKLIST.md

## Support Checklist

Before asking for help:

- [ ] Checked logs for errors
- [ ] Ran backfill_aliases.py
- [ ] Verified .env configuration
- [ ] Tested commands manually
- [ ] Checked database tables exist
- [ ] Read relevant documentation

## Estimated Timeline

| Phase | Time | What |
|-------|------|------|
| Pre-deployment | 5 min | Backup and prep |
| Deployment | 10 min | Install and start |
| Testing | 5 min | Verify works |
| **Total** | **20 min** | Full deployment |

## Quick Command Reference

```bash
# Start bot
sudo systemctl start etlegacy-bot

# Stop bot
sudo systemctl stop etlegacy-bot

# Restart bot
sudo systemctl restart etlegacy-bot

# Check status
sudo systemctl status etlegacy-bot

# View logs
journalctl -u etlegacy-bot -f

# Or direct logs
tail -f logs/ultimate_bot.log
```

## Final Reminders

✅ **Backfill is critical** - Don't skip it!  
✅ **Test before production** - Run locally first  
✅ **Monitor after deployment** - Watch logs  
✅ **Keep backups** - Easy rollback if needed  

---

**Ready to deploy? Follow the checklist and you'll be running V2 in 20 minutes! 🚀**

Good luck! 🎮
