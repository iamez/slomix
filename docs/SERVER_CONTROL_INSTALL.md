# 🚀 Server Control - Quick Installation

## Step 1: Configure RCON on Server

SSH to your server:
```bash
ssh et@puran.hehe.si -p 48101
```

Edit vektor.cfg:
```bash
cd ~/etlegacy-v2.83.1-x86_64
nano vektor.cfg
```

Add these lines:
```cfg
// RCON Configuration
set rconPassword "GENERATE_SECURE_PASSWORD"
set net_port "27960"
```

Generate secure password:
```bash
openssl rand -base64 32
```

Save and exit (Ctrl+X, Y, Enter)

---

## Step 2: Update .env File

On your Windows PC, edit `.env` and add:

```bash
# Server Control Configuration
RCON_ENABLED=true
RCON_HOST=puran.hehe.si
RCON_PORT=27960
RCON_PASSWORD=paste_generated_password_here
ADMIN_CHANNEL_ID=paste_your_admin_channel_id_here
```

To get channel ID:
1. Enable Developer Mode in Discord (Settings → Advanced)
2. Right-click your admin channel → Copy ID
3. Paste into `.env`

---

## Step 3: Test Installation

Restart bot:
```powershell
Stop-Process -Name python -Force
python bot/ultimate_bot.py
```

Look for this in logs:
```
✅ Server Control cog loaded
   SSH: et@puran.hehe.si:48101
   Server Path: /home/et/etlegacy-v2.83.1-x86_64
   Screen: vektor
   RCON: Enabled
```

---

## Step 4: Test Commands

In your admin channel, try:
```
!server_status
!map_list
!rcon status
```

If working, you'll see:
- Server status with CPU/memory/player count
- List of maps in etmain
- Current players from RCON

---

## Troubleshooting

**"RCON is not configured!"**
- Check `RCON_ENABLED=true` in .env
- Verify password matches vektor.cfg
- Restart bot

**"Permission Denied"**
- Use commands in admin channel only
- Check `ADMIN_CHANNEL_ID` is correct

**"SSH connection failed"**
- Test: `ssh et@puran.hehe.si -p 48101`
- Check SSH_KEY_PATH in .env

---

## Success! 🎉

You can now:
- ✅ Start/stop/restart server remotely
- ✅ Upload and change maps
- ✅ Kick players and send announcements
- ✅ Execute any RCON command

**Full Documentation:**
- Setup Guide: `docs/SERVER_CONTROL_SETUP.md`
- Quick Reference: `docs/SERVER_CONTROL_QUICK_REF.md`
- Commands: See `!help` in Discord

---

## Quick Command Reference

```
# Server
!status            - Check server
!restart           - Restart server

# Maps
!maps              - List maps
!map <name>        - Change map
!addmap            - Upload map (attach file)

# Players
!rcon status       - Show players
!kick <id>         - Kick player
!say <msg>         - Announce
```

---

**Need help? Check the full setup guide in `docs/SERVER_CONTROL_SETUP.md`**
