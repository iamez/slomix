# 🎯 Quick Reference Card

## 📦 Your Files

```
📁 ET:Legacy Bot V2 Package
├── 🤖 ultimate_bot_v2.py          ← THE NEW BOT (deploy this!)
├── 🔄 backfill_aliases.py         ← Run once after deployment
├── ⚙️  env.example                 ← Copy to .env and configure
├── 📋 requirements.txt            ← pip install -r requirements.txt
│
├── 📚 Documentation
│   ├── V2_SUMMARY.md              ← START HERE! Overview
│   ├── DEPLOYMENT_CHECKLIST.md   ← Step-by-step deployment
│   ├── README_V2.md               ← Complete feature guide
│   ├── MIGRATION_GUIDE.md         ← Detailed upgrade guide
│   ├── CHANGES.md                 ← What changed V1→V2
│   └── QUICK_REFERENCE.md         ← This file!
```

## ⚡ Quick Start Commands

```bash
# 1. Backup everything
cp ultimate_bot_FINAL.py ultimate_bot_FINAL.py.backup
cp etlegacy_production.db etlegacy_production.db.backup

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run backfill (CRITICAL!)
python3 backfill_aliases.py

# 4. Test locally
python3 ultimate_bot_v2.py

# 5. Deploy to production
cp ultimate_bot_v2.py /path/to/bot/ultimate_bot.py
sudo systemctl restart etlegacy-bot
```

## 🎮 New Commands Quick Reference

### !stats [player]
```
!stats              → Your stats (if linked)
!stats @user        → User's stats
!stats PlayerName   → Search by name
!stats ABC12345     → Look up by GUID
```

### !link [target] [guid]
```
!link                    → Interactive linking
!link PlayerName         → Search and link
!link ABC12345           → Direct GUID link
!link @user ABC12345     → Admin: link another user
```

### !list_guids [search] ⭐ NEW!
```
!list_guids              → Top 10 most active unlinked
!list_guids recent       → Last 7 days
!list_guids PlayerName   → Search by name
!list_guids all          → All unlinked (max 20)
```

## 📊 What Got Fixed

| Issue | Status |
|-------|--------|
| Alias tracking | ✅ Fixed (automatic now) |
| !stats command | ✅ Fixed (finds by name) |
| !link command | ✅ Fixed (interactive) |
| Admin linking | ✅ New tool (!list_guids) |
| Code quality | ✅ Clean rewrite |
| Documentation | ✅ Complete docs |

## 🚨 Critical Steps

### MUST DO:
1. ✅ Run `backfill_aliases.py` after deployment
2. ✅ Test commands before going live
3. ✅ Keep backups (easy rollback)

### SHOULD DO:
1. Read DEPLOYMENT_CHECKLIST.md
2. Verify .env configuration
3. Monitor logs after deployment

## 💡 Admin Workflow (New!)

### Before (Old Way):
```
Player asks for link → Admin hunts GUID in logs (5 min) → Maybe finds it
```

### After (New Way):
```
!list_guids PlayerName → Copy GUID → !link @player GUID (10 seconds!)
```

## 🆘 Emergency Rollback

```bash
# If something goes wrong:
sudo systemctl stop etlegacy-bot
cp ultimate_bot_FINAL.py.backup /path/to/bot/ultimate_bot.py
sudo systemctl start etlegacy-bot
```

## 📖 Which Doc to Read?

- **Just getting started?** → V2_SUMMARY.md
- **Ready to deploy?** → DEPLOYMENT_CHECKLIST.md
- **Want details?** → README_V2.md
- **Need migration help?** → MIGRATION_GUIDE.md
- **Curious what changed?** → CHANGES.md
- **Quick lookup?** → This file!

## ⏱️ Time Investment

- Reading docs: 10 min
- Deployment: 20 min
- **Total: 30 min for HUGE improvement!**

## ✅ Success Checklist

After deployment, verify:

- [ ] Bot starts without errors
- [ ] `!ping` responds
- [ ] `!stats PlayerName` finds players
- [ ] `!list_guids` shows unlinked
- [ ] `!link` works interactively
- [ ] Logs show "Updated alias" messages

## 🎯 Key Benefits

### For Admins:
- ⚡ 10x faster player linking
- 🔍 Easy GUID lookup
- 👀 See player stats at a glance

### For Players:
- ✅ !stats actually works
- ✅ Easy account linking
- ✅ Better bot reliability

### For You (Maintainer):
- 📚 Clean, documented code
- 🔧 Easy to extend
- 🐛 Easier debugging
- ✅ Better performance

## 📞 Support Quick Links

**Problem:** Commands not working  
**Solution:** Run `python3 backfill_aliases.py`

**Problem:** Can't find players  
**Solution:** Check player_aliases table populated

**Problem:** Module not found  
**Solution:** Check community_stats_parser.py location

**Problem:** Database errors  
**Solution:** Verify ETLEGACY_DB_PATH in .env

## 🎉 Bottom Line

**What:** Complete bot rewrite  
**Why:** Fix critical bugs + clean code  
**How:** 20 minute deployment  
**Result:** Everything works + new features!  

---

**Ready? Start with: DEPLOYMENT_CHECKLIST.md** 🚀

*ET:Legacy Bot V2 - Built Better*
