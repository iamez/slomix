# 🚀 QUICK START - SSH Monitoring

## ✅ What's Done

All code implemented! SSH monitoring system is ready to test.

## 📋 Your Next Steps

### 1. Generate SSH Key (5 minutes)

```powershell
# Generate key pair
ssh-keygen -t rsa -b 4096 -f ~/.ssh/etlegacy_bot

# Press Enter when asked for passphrase (no password)
# This creates:
#   ~/.ssh/etlegacy_bot (private key)
#   ~/.ssh/etlegacy_bot.pub (public key)
```

### 2. Upload Public Key to Server (2 minutes)

```powershell
# Show your public key
Get-Content ~\.ssh\etlegacy_bot.pub

# SSH to server
ssh et@puran.hehe.si -p 48101

# On server - add key to authorized_keys
mkdir -p ~/.ssh
echo "PASTE_YOUR_PUBLIC_KEY_HERE" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
exit
```

### 3. Test SSH Connection (1 minute)

```powershell
# Should connect WITHOUT asking for password
ssh -i ~/.ssh/etlegacy_bot et@puran.hehe.si -p 48101

# List stats files
ls /home/et/.etlegacy/legacy/gamestats/

# Exit
exit
```

✅ If it works without password → Success!  
❌ If it asks for password → Check step 2

### 4. Configure Bot (2 minutes)

Edit `.env` file:

```env
# Enable SSH monitoring
SSH_ENABLED=true

# SSH settings (already configured in .env.example)
SSH_HOST=puran.hehe.si
SSH_PORT=48101
SSH_USER=et
SSH_KEY_PATH=~/.ssh/etlegacy_bot
REMOTE_STATS_PATH=/home/et/.etlegacy/legacy/gamestats

# Make sure these are set:
STATS_CHANNEL_ID=your_channel_id_here
```

### 5. Install SSH Library (1 minute)

```powershell
pip install paramiko
```

### 6. Start Bot & Test (5 minutes)

```powershell
# Start bot
python bot/ultimate_bot.py

# Look for:
# ✅ Schema validated: 53 columns (UNIFIED)
# 🎮 Bot ready with 14 commands!
```

In Discord:

```
!session_start
```

Bot should reply:
```
✅ Session started! Now monitoring for EndStats files.
```

### 7. Play a Round & Watch! (varies)

1. Play a round on the server
2. Wait 30-60 seconds after round ends
3. Check Discord → Round summary should appear!

---

## 🐛 If Something Goes Wrong

### SSH Connection Failed

```powershell
# Test manually
ssh -i ~/.ssh/etlegacy_bot et@puran.hehe.si -p 48101

# If fails, check:
# 1. Public key added to server ~/.ssh/authorized_keys
# 2. File permissions: chmod 600 ~/.ssh/authorized_keys (on server)
# 3. Key path correct in .env
```

### No Files Detected

```bash
# On server, check files exist:
ls -la /home/et/.etlegacy/legacy/gamestats/

# Check path in .env matches
```

### Bot Crashes

```powershell
# Check logs
Get-Content logs/ultimate_bot.log -Tail 50
```

---

## 📚 Full Documentation

- **Setup Guide**: `docs/SSH_MONITORING_SETUP.md` (450 lines)
- **Implementation**: `docs/SSH_IMPLEMENTATION_SUMMARY.md` (350 lines)

---

## ⚠️ Known Limitation

Database import is **placeholder** - returns mock data.  
Stats are parsed and downloaded, but not yet saved to database.

**Next step**: Implement `_import_stats_to_db()` method using logic from `tools/simple_bulk_import.py`

---

## 🎯 Success = Seeing This in Discord

```
╔═════════════════════════════════════════════╗
║  🎯 erdenberg_t2 - Round 1 Complete        ║
║                                             ║
║  🏆 Top Performers                          ║
║  1. vid - 15K/8D (543 DPM)                 ║
║  2. SuperBoyy - 12K/9D (498 DPM)           ║
║  3. carniee - 11K/7D (456 DPM)             ║
╚═════════════════════════════════════════════╝
```

Automatically posted 30-60 seconds after round ends!

---

**Time to implement**: ~15 minutes  
**Time to test**: ~10 minutes (includes playing a round)  
**Total**: ~25 minutes to automatic round summaries! 🎉
