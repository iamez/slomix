# 🎮 ET:Legacy Server Control - Setup Guide

## 📋 Overview

This adds **remote server control** to your Discord bot:
- ✅ Start/Stop/Restart server
- ✅ Map management (upload/change/delete)
- ✅ RCON commands (kick, say, status)
- ✅ SSH file operations
- ✅ Role-based security
- ✅ Audit logging

---

## 🚀 Installation

### Step 1: Save the Cog

Save the `server_control.py` file to your bot's cogs folder:

```
bot/
├── cogs/
│   ├── __init__.py
│   ├── server_control.py  ← NEW FILE
│   └── synergy_analytics.py
```

### Step 2: Update .env Configuration

Add these settings to your `.env` file:

```bash
# ==========================================
# SERVER CONTROL CONFIGURATION
# ==========================================

# SSH Connection (already exists)
SSH_HOST=your.vps.com
SSH_PORT=22
SSH_USER=et
SSH_KEY_PATH=~/.ssh/id_rsa

# ET:Legacy Server Paths
ETLEGACY_PATH=/home/et/.etlegacy
SCREEN_NAME=etlegacy
SERVER_BINARY=./etlded
SERVER_CONFIG=server.cfg

# RCON Configuration
RCON_ENABLED=true
RCON_HOST=your.vps.com
RCON_PORT=27960
RCON_PASSWORD=your_rcon_password

# Security
ADMIN_ROLE=Server Admin
AUDIT_CHANNEL_ID=your_audit_channel_id
```

### Step 3: Load the Cog in Your Bot

In `bot/ultimate_bot.py`, add to the `setup_hook` method:

```python
async def setup_hook(self):
    """🔧 Initialize all bot components"""
    logger.info("🚀 Initializing Ultimate ET:Legacy Bot...")

    # ... existing code ...

    # Load the commands cog
    await self.add_cog(ETLegacyCommands(self))

    # 🎯 NEW: Load server control cog
    try:
        await self.load_extension('cogs.server_control')
        logger.info("✅ Server Control cog loaded")
    except Exception as e:
        logger.warning(f"⚠️  Could not load Server Control cog: {e}")
        logger.warning("Bot will continue without server control features")

    # ... rest of setup ...
```

### Step 4: Set Up Discord Roles

In your Discord server:

1. Create a role called **"Server Admin"** (or whatever you set in `ADMIN_ROLE`)
2. Assign this role to trusted users who should control the server
3. **IMPORTANT:** Only give this role to people you trust!

### Step 5: Create Audit Log Channel (Optional)

1. Create a Discord channel (e.g., `#server-audit-log`)
2. Get the channel ID (right-click → Copy ID)
3. Add to `.env`: `AUDIT_CHANNEL_ID=123456789`

---

## 🎮 ET:Legacy Server Setup

### Configure RCON

Edit your `server.cfg` on the VPS:

```cfg
// RCON Configuration
set rconPassword "your_secure_password_here"
set g_log "etserver.log"
set g_logsync "1"

// Network
set net_port "27960"
```

**Security Note:** Use a STRONG rcon password! Anyone with it can control your server.

### Screen Session Setup

Your server should be running in a screen session named `etlegacy`:

```bash
# Start server in screen
screen -dmS etlegacy ./etlded +set fs_basepath /home/et/.etlegacy +set fs_homepath /home/et/.etlegacy +exec server.cfg

# List screen sessions
screen -ls

# Attach to session
screen -r etlegacy

# Detach from session (inside screen)
Ctrl+A, then D
```

### Directory Structure

Make sure your server has this structure:

```
/home/et/.etlegacy/
├── etlded                    # Server binary
├── legacy/
│   ├── maps/                 # Map files (.pk3)
│   ├── server.cfg            # Server config
│   ├── etserver.log          # Server logs
│   └── gamestats/            # Stats files
└── ... other files
```

---

## 📖 Commands Reference

### 🔧 Server Management

| Command | Description | Admin? |
|---------|-------------|--------|
| `!server_status` | Check if server is online | No |
| `!server_start` | Start the server | **Yes** |
| `!server_stop` | Stop the server | **Yes** |
| `!server_restart` | Restart the server | **Yes** |

### 🗺️ Map Management

| Command | Description | Admin? |
|---------|-------------|--------|
| `!map_list` | List available maps | No |
| `!map_add` | Upload new map (attach .pk3) | **Yes** |
| `!map_change <name>` | Change current map | **Yes** |
| `!map_delete <name>` | Delete a map | **Yes** |

### 🎮 RCON Commands

| Command | Description | Admin? |
|---------|-------------|--------|
| `!rcon <command>` | Send any RCON command | **Yes** |
| `!kick <id> [reason]` | Kick a player | **Yes** |
| `!say <message>` | Send message to server | **Yes** |

---

## 💡 Usage Examples

### Starting the Server

```
User: !server_start
Bot: 🚀 Starting ET:Legacy server...
Bot: ✅ Server Started
     ET:Legacy server is now running in screen session `etlegacy`
```

### Uploading a New Map

```
User: !map_add
[Attaches goldrush-final.pk3]
Bot: 📥 Downloading `goldrush-final.pk3`...
Bot: 📤 Uploading to server... (MD5: `a1b2c3d4`)
Bot: ✅ Map Uploaded
     goldrush-final.pk3 has been uploaded to the server
     Size: 12.5 MB
     Use !map_change goldrush-final to load it
```

### Changing the Map

```
User: !map_change goldrush-final
Bot: 🗺️ Changing map to `goldrush-final`...
Bot: ✅ Map Changed
     Server is now loading goldrush-final
```

### Sending Server Message

```
User: !say Server will restart in 5 minutes for updates
Bot: ✅ Message sent to server: *Server will restart in 5 minutes for updates*
```

### Checking Server Status

```
User: !server_status
Bot: ✅ Server Online
     ET:Legacy server is running in screen session `etlegacy`
     CPU Usage: 15.2%
     Memory: 3.4%
     Players: 8 online
```

### Using RCON

```
User: !rcon status
Bot: 🎮 RCON Response
     ```
     map: goldrush
     num score ping name            lastmsg address               qport rate
     --- ----- ---- --------------- ------- --------------------- ----- -----
       0     0   50 ^1Player1           0 192.168.1.100:27960   12345 25000
       1    10   75 ^2Player2           0 192.168.1.101:27960   12346 25000
     ```
```

---

## 🔒 Security Best Practices

### 1. SSH Key Authentication
**NEVER use password authentication!** Use SSH keys:

```bash
# Generate key (if you don't have one)
ssh-keygen -t rsa -b 4096 -f ~/.ssh/etlegacy_bot

# Copy to server
ssh-copy-id -i ~/.ssh/etlegacy_bot.pub et@your.vps.com

# Test connection
ssh -i ~/.ssh/etlegacy_bot et@your.vps.com
```

### 2. Strong RCON Password
Use a random 32+ character password:

```bash
# Generate random password
openssl rand -base64 32
```

### 3. Restrict SSH User
Create a dedicated user with limited permissions:

```bash
# On VPS
sudo useradd -m -s /bin/bash et
sudo su - et

# Only give permissions for:
# - Reading/writing maps folder
# - Starting/stopping screen sessions
# - Reading logs
```

### 4. Discord Role Permissions
- Only give "Server Admin" role to trusted people
- Regularly audit who has the role
- Check audit logs for suspicious activity

### 5. Rate Limiting
The bot has basic rate limiting, but consider:
- Limiting how many times someone can restart server per hour
- Cooldown between map changes
- Maximum file upload size

---

## 🐛 Troubleshooting

### Bot Can't Connect to Server

```
Error: SSH connection failed
```

**Fix:**
```bash
# Test SSH connection manually
ssh -i ~/.ssh/id_rsa et@your.vps.com -p 22

# Check SSH key permissions
chmod 600 ~/.ssh/id_rsa

# Verify server is reachable
ping your.vps.com
```

### RCON Not Working

```
Error: RCON is not configured!
```

**Fix:**
1. Check `.env` has `RCON_ENABLED=true`
2. Verify `RCON_PASSWORD` matches server `rconPassword`
3. Check `RCON_PORT` is correct (usually 27960)
4. Test RCON manually:
   ```bash
   # On your PC
   nc -u your.vps.com 27960
   # Type: \xFF\xFF\xFF\xFFrcon YOUR_PASSWORD status
   ```

### Server Won't Start

```
Server may not have started properly
```

**Fix:**
```bash
# SSH to server
ssh et@your.vps.com

# Check screen sessions
screen -ls

# Check server logs
tail -f /home/et/.etlegacy/legacy/etserver.log

# Try starting manually
cd /home/et/.etlegacy
./etlded +exec server.cfg
```

### Map Upload Fails

```
Error uploading map: Permission denied
```

**Fix:**
```bash
# On VPS, check permissions
ls -la /home/et/.etlegacy/legacy/maps/

# Should be owned by 'et' user
sudo chown -R et:et /home/et/.etlegacy/legacy/maps/

# Check write permissions
chmod 755 /home/et/.etlegacy/legacy/maps/
```

### Permission Denied in Discord

```
❌ Permission Denied
You need the Server Admin role to use this command!
```

**Fix:**
1. Make sure you have the "Server Admin" role in Discord
2. Check the role name matches exactly what's in `.env`
3. Bot needs to be able to see member roles (Server Members Intent)

---

## 📝 Advanced Configuration

### Custom Screen Name

If your server uses a different screen session name:

```bash
# .env
SCREEN_NAME=my_custom_et_server
```

### Multiple Servers

To control multiple servers, create separate bot instances or extend the cog to support server profiles:

```python
# Future enhancement
!server_status server1
!server_status server2
```

### Auto-Restart on Crash

Add to your VPS crontab:

```bash
# Check every 5 minutes, restart if crashed
*/5 * * * * screen -ls | grep -q etlegacy || cd /home/et/.etlegacy && screen -dmS etlegacy ./etlded +exec server.cfg
```

### Log Rotation

Prevent log files from growing too large:

```bash
# /etc/logrotate.d/etlegacy
/home/et/.etlegacy/legacy/etserver.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
}
```

---

## 🎯 Next Steps

1. **Test all commands** in a private Discord channel first
2. **Set up audit logging** to track all server actions
3. **Create backup procedures** for configs and maps
4. **Document your custom maps** and server settings
5. **Train your admin team** on the commands

---

## 📞 Support

If you run into issues:

1. Check the bot logs: `logs/ultimate_bot.log`
2. Test SSH connection manually
3. Verify RCON is working
4. Check Discord role permissions
5. Look at server logs on VPS

---

**Made with ❤️ for retro gaming communities**

*Last updated: October 7, 2025*
