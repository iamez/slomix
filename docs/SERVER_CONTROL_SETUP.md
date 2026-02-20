# 🎮 ET:Legacy Server Control - Vektor Server Setup Guide

## 📋 Overview

Remote server control has been added to your Discord bot with these features:

- ✅ **Server Management** - Start/Stop/Restart the Vektor server
- ✅ **Map Management** - Upload/Change/Delete maps
- ✅ **RCON Commands** - Kick players, send messages, execute any RCON command
- ✅ **SSH Operations** - Secure file transfers and process control
- ✅ **Audit Logging** - Local logging of all admin actions
- ✅ **Channel Security** - Commands only work in designated admin channel

---

## 🚀 Quick Setup

### Step 1: Configure RCON on Your Server

SSH to your Vektor server and edit your config:

```bash
ssh et@puran.hehe.si -p 48101
cd ~/etlegacy-v2.83.1-x86_64
nano vektor.cfg
```sql

Add or update these lines in `vektor.cfg`:

```cfg
// RCON Configuration
set rconPassword "YOUR_SECURE_PASSWORD_HERE"
set net_port "27960"
set g_log "etserver.log"
set g_logsync "1"
```text

**IMPORTANT:** Use a strong RCON password! Generate one with:

```bash
openssl rand -base64 32
```text

Save and restart your server:

```bash
screen -r vektor
# Press Ctrl+C to stop
# Wait for clean shutdown
# It will auto-restart via your watchdog daemon
```sql

### Step 2: Update Your .env File

Add these settings to your existing `.env` file:

```bash
# ==========================================
# SERVER CONTROL CONFIGURATION
# ==========================================

# RCON (Required for remote control)
RCON_ENABLED=true
RCON_HOST=puran.hehe.si
RCON_PORT=27960
RCON_PASSWORD=paste_your_rcon_password_here

# Admin Channel (get ID via right-click → Copy ID)
# Only commands in this channel will work
ADMIN_CHANNEL_ID=your_admin_channel_id_here

# SSH is already configured - same credentials used for stats sync
# SSH_HOST=puran.hehe.si
# SSH_PORT=48101
# SSH_USER=et
# SSH_KEY_PATH=~/.ssh/etlegacy_bot
```text

### Step 3: Get Your Admin Channel ID

1. Open Discord Desktop/Web (not mobile)
2. Enable Developer Mode: User Settings → Advanced → Developer Mode
3. Right-click your admin channel → "Copy ID"
4. Paste it into `.env` as `ADMIN_CHANNEL_ID=123456789`

### Step 4: Restart Your Bot

```powershell
# Stop the bot if running
Stop-Process -Name python -Force

# Start it again
python bot/ultimate_bot.py
```text

You should see in the logs:

```text

✅ Server Control cog loaded
   SSH: <et@puran.hehe.si>:48101
   Server Path: /home/et/etlegacy-v2.83.1-x86_64
   Screen: vektor
   RCON: Enabled
   Admin Channel: 123456789

```sql

---

## 📖 Commands Reference

### 🔧 Server Management

| Command | Description | Example |
|---------|-------------|---------|
| `!server_status` | Check if server is online | `!status` |
| `!server_start` | Start the server | `!start` |
| `!server_stop` | Stop the server | `!stop` |
| `!server_restart` | Restart the server | `!restart` |

**Note:** Stop/Restart require confirmation (react with ✅)

### 🗺️ Map Management

| Command | Description | Example |
|---------|-------------|---------|
| `!list_maps` | List all maps in etmain/ | `!map_list` |
| `!map_add` | Upload new map (attach .pk3) | `!addmap` + attach file |
| `!map_change <name>` | Change current map | `!map goldrush` |
| `!map_delete <name>` | Delete a map | `!deletemap old_map.pk3` |

### 🎮 RCON Commands

| Command | Description | Example |
|---------|-------------|---------|
| `!rcon <command>` | Send any RCON command | `!rcon status` |
| `!kick <id> [reason]` | Kick a player | `!kick 3 Teamkilling` |
| `!say <message>` | Send message to server | `!say Match starting in 5 min` |

---

## 💡 Usage Examples

### Check Server Status

```text

You: !server_status

Bot: ✅ Server Online
     ET:Legacy server is running in screen session `vektor`
     CPU Usage: 12.5%
     Memory: 3.2%
     Players: 8 online

```text

### Upload a New Map

```text

You: !map_add
[Attach: goldrush_final.pk3]

Bot: 📥 Downloading `goldrush_final.pk3`...
Bot: 📤 Uploading to server... (MD5: `a1b2c3d4`)
Bot: ✅ Map Uploaded
     Size: 15.2 MB
     Use !map_change goldrush_final to load it

```text

### Change the Map

```text

You: !map_change supply

Bot: 🗺️ Changing map to `supply`...
Bot: ✅ Map Changed
     Server is now loading supply

```text

### Send Server Message

```text

You: !say Match will start in 5 minutes, everyone ready up!

Bot: ✅ Message sent to server

```text

### Check Players

```text

You: !rcon status

Bot: 🎮 RCON Response
     ```yaml
     map: goldrush
     num score ping name            lastmsg address
     --- ----- ---- --------------- ------- -------
       0    45   20 ^1Player1           0 1.2.3.4:27960
       1    38   35 ^2Player2           0 5.6.7.8:27960
       2    22   50 ^3Player3           0 9.8.7.6:27960
     ```text

```text

### Restart Server

```text

You: !server_restart

Bot: ⚠️ Confirm RESTART server?
     React with ✅ to confirm (timeout: 30s)

You: [React with ✅]

Bot: 🔄 Restarting ET:Legacy server...
Bot: 🛑 Stopping ET:Legacy server...
Bot: ✅ Server Stopped
     Note: Your watchdog daemon will restart it automatically in ~1 minute
Bot: 🚀 Starting ET:Legacy server...
Bot: ✅ Server Started

```sql

---

## 🔒 Security Features

### 1. Channel-Based Access Control

- Commands only work in the designated admin channel
- Attempts from other channels are denied with error message
- No role checking needed - channel membership = permission

### 2. Local Audit Logging

All admin actions are logged to `logs/server_control_access.log`:

```text

[2025-10-07 14:23:15] Server Stop by YourName (123456789) - Stopping for maintenance
[2025-10-07 14:25:42] Map Upload Success by YourName (123456789) - goldrush.pk3 - MD5: a1b2c3d4
[2025-10-07 14:30:11] RCON Command by YourName (123456789) - Command: say Hello players!

```yaml

### 3. SSH Key Authentication

- Uses existing SSH keys (no passwords)
- Same credentials as stats sync
- Secure file transfers via SFTP

### 4. Confirmation for Destructive Actions

- Server stop/restart require ✅ confirmation
- Map deletion requires ✅ confirmation
- 30-second timeout prevents accidents

---

## 🛠️ Server Structure

Your server setup (already configured in the cog):

```text

/home/et/etlegacy-v2.83.1-x86_64/          # Root installation
├── etlded.x86_64                           # Server binary
├── vektor.cfg                              # Server config
└── etmain/                                 # Maps folder
    ├── goldrush.pk3
    ├── supply.pk3
    └── ... (other maps)

/home/et/.etlegacy/legacy/gamestats/        # Stats files (c0rnp0rn3.lua)

```yaml

Screen session: `vektor`

Watchdog daemon: Automatically restarts server if it crashes

---

## 🐛 Troubleshooting

### Bot Says "RCON is not configured!"

**Problem:** RCON settings not in `.env` or incorrect

**Fix:**

1. Check `.env` has `RCON_ENABLED=true`
2. Verify `RCON_PASSWORD` matches what's in `vektor.cfg`
3. Restart the bot
4. Test RCON manually:

   ```bash
   # On your local PC
   nc -u puran.hehe.si 27960
   # Type: rcon YOUR_PASSWORD status
   ```text

### Commands Don't Work (Permission Denied)

**Problem:** Not using commands in admin channel

**Fix:**

1. Check you're in the correct channel (the one with ID matching `ADMIN_CHANNEL_ID`)
2. Verify the channel ID is correct:

   ```powershell
   python -c "print(int('paste_your_ADMIN_CHANNEL_ID_here'))"
   ```sql

3. If you want to allow commands from anywhere, remove `ADMIN_CHANNEL_ID` from `.env`

### SSH Connection Failed

**Problem:** Bot can't connect to server

**Fix:**

1. Test SSH manually:

   ```powershell
   ssh et@puran.hehe.si -p 48101 -i ~/.ssh/etlegacy_bot
   ```text

2. Check SSH key permissions:

   ```powershell
   icacls ~\.ssh\etlegacy_bot
   # Should show: YOURUSERNAME:(R)
   ```text

3. Verify `SSH_HOST`, `SSH_PORT`, `SSH_USER`, `SSH_KEY_PATH` in `.env`

### Map Upload Fails

**Problem:** Permission denied when uploading map

**Fix:**

1. SSH to server and check permissions:

   ```bash
   ls -la ~/etlegacy-v2.83.1-x86_64/etmain/
   # Should be owned by 'et' user
   ```text

2. Fix if needed:

   ```bash
   chmod 755 ~/etlegacy-v2.83.1-x86_64/etmain/
   ```text

### Server Won't Start

**Problem:** `!server_start` doesn't work

**Fix:**

1. SSH to server manually:

   ```bash
   ssh et@puran.hehe.si -p 48101
   ```text

2. Check if screen exists:

   ```bash
   screen -ls
   ```text

3. Check watchdog is running:

   ```bash
   ps aux | grep etlded
   ```text

4. Try starting manually:

   ```bash
   cd ~/etlegacy-v2.83.1-x86_64
   screen -dmS vektor ./etlded.x86_64 +exec vektor.cfg
   ```text

5. Check server logs:

   ```bash
   tail -f ~/etlegacy-v2.83.1-x86_64/etserver.log
   ```yaml

---

## 📝 Important Notes

### About Your Watchdog Daemon

Your server has an auto-restart watchdog that:

- Checks every 1 minute if `vektor` screen session exists
- Automatically restarts server if it crashes
- Runs via `@reboot` cron job

**This means:**

- ✅ When you `!server_stop`, it will auto-restart in ~1 minute
- ✅ If server crashes, it recovers automatically
- ⚠️ To keep server stopped permanently, you need to SSH in and disable the watchdog

### Map File Locations

Maps go in: `/home/et/etlegacy-v2.83.1-x86_64/etmain/`

**NOT** in the legacy folder - that's for the mod/Lua scripts.

### Mod/Lua Script Management

The cog currently only handles maps. For mod/Lua updates:

1. We can add commands to upload to `/home/et/etlegacy-v2.83.1-x86_64/legacy/`
2. Or continue doing it manually via SSH
3. Let me know if you want mod management commands added!

---

## 🎯 Next Steps

### 1. Test Basic Commands

In your admin channel:

```text

!server_status
!list_maps
!rcon status

```yaml

### 2. Test Map Upload

1. Download a test map (small .pk3 file)
2. In admin channel: `!map_add`
3. Attach the .pk3 file
4. Verify it appears in `!list_maps`

### 3. Set Up Regular Monitoring

You can create simple aliases for common tasks:

- `!status` → Quick server check
- `!players` → `!rcon status` to see who's online
- `!announce <msg>` → `!say <msg>` for server announcements

### 4. Document Your Custom Maps

Keep a list of your custom maps and configs so new admins know what's available.

---

## 🤝 Feature Requests

Want to add more features? Easy possibilities:

### Already Implemented

- ✅ Server start/stop/restart
- ✅ Map upload/change/delete
- ✅ RCON commands
- ✅ Player kick
- ✅ Server announcements
- ✅ Audit logging

### Could Add Later

- 📋 Config file management (upload/edit vektor.cfg)
- 🔧 Mod/Lua script uploads
- 📊 Real-time server stats (player count, map rotation)
- 🔄 Automatic map rotation scheduling
- 📜 Server log viewing
- 🚫 Ban management
- 🎮 Match config loading (for competitive games)

Let me know if you want any of these!

---

## 📞 Support

If you run into issues:

1. **Check the logs:**

   ```powershell
   Get-Content logs\bot.log -Tail 50
   Get-Content logs\webhook.log -Tail 50
   Get-Content logs\database.log -Tail 50
   Get-Content logs\errors.log -Tail 50
   Get-Content logs\server_control_access.log -Tail 20
   ```text

2. **Test SSH connection:**

   ```powershell
   ssh et@puran.hehe.si -p 48101
   ```text

3. **Verify RCON:**

   ```bash
   # On server
   netstat -tulpn | grep 27960
   ```text

4. **Check server logs:**

   ```bash
   tail -f ~/etlegacy-v2.83.1-x86_64/etserver.log
   ```

---

**Made with ❤️ for the Vektor ET:Legacy community**

*Last updated: October 7, 2025*
