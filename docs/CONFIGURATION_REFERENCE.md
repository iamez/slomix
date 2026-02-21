# ⚙️ Configuration Reference

> **Complete reference for all .env configuration variables**

Last Updated: October 11, 2025

---

## 📋 Quick Reference

```bash
# Required for basic operation
DISCORD_BOT_TOKEN=your_bot_token_here
RCON_PASSWORD=your_rcon_password

# Required for automation
AUTOMATION_ENABLED=true
SSH_ENABLED=true  
GAMING_VOICE_CHANNELS=1234567890,9876543210

# Optional enhancements
STATS_CHANNEL_ID=1234567890
ADMIN_CHANNEL_ID=1234567890
```sql

---

## 🔐 Discord Configuration

### DISCORD_BOT_TOKEN

**Required:** Yes  
**Type:** String  
**Example:** `MTE3NDM4ODUxNjAwNDgzNTQxOQ.GLlR-y.nqIZFtrSweaX-ZGZ1S2YUARSWvXmYHABjLEukA`

**Description:**  
Your Discord bot authentication token from the Discord Developer Portal.

**How to Get:**

1. Go to <https://discord.com/developers/applications>
2. Create a new application or select existing
3. Go to "Bot" section
4. Click "Reset Token" and copy the token
5. **Keep this secret!** Never commit to git

**Common Issues:**

- ❌ Token expired → Reset token in Discord portal
- ❌ Bot offline → Check token is correct
- ❌ Invalid token → Regenerate in Discord portal

---

### GUILD_ID

**Required:** No (recommended)  
**Type:** Integer  
**Example:** `1420158096801661011`

**Description:**  
Your Discord server (guild) ID for guild-specific commands and faster syncing.

**How to Get:**

1. Enable Developer Mode in Discord (User Settings → Advanced)
2. Right-click your server icon → "Copy Server ID"

**Impact:**

- **With GUILD_ID:** Commands sync instantly to your server
- **Without:** Commands sync globally (takes up to 1 hour)

---

### STATS_CHANNEL_ID

**Required:** No (recommended)  
**Type:** Integer  
**Example:** `1420158097741058130`

**Description:**  
Channel where bot automatically posts match stats and session summaries.

**How to Get:**

1. Right-click channel → "Copy Channel ID" (Developer Mode required)

**Usage:**

- Auto-posted round summaries
- Round end summaries
- Real-time stats updates

---

### ADMIN_CHANNEL_ID

**Required:** No  
**Type:** Integer  
**Example:** `1420158097741058131`

**Description:**  
Admin-only channel for server management commands (!rcon, !restart, etc.)

**Security:**

- Bot restricts admin commands to this channel only
- Prevents accidental server restarts in public channels

---

### GATHER_3V3_CHANNEL_ID

**Required:** No  
**Type:** Integer  
**Example:** `1420158097741058132`

**Description:**  
Channel for 3v3 gather organization (future feature).

---

### GATHER_6V6_CHANNEL_ID

**Required:** No  
**Type:** Integer  
**Example:** `1420158097741058133`

**Description:**  
Channel for 6v6 gather organization (future feature).

---

## 🎮 ET:Legacy Server Configuration

### SERVER_HOST

**Required:** Yes  
**Type:** String (hostname or IP)  
**Example:** `puran.hehe.si`

**Description:**  
Your ET:Legacy game server hostname or IP address.

**Accepted Formats:**

- Domain: `puran.hehe.si`
- IPv4: `192.168.1.100`
- IPv6: `2001:db8::1`

---

### SERVER_PORT

**Required:** Yes  
**Type:** Integer  
**Default:** `27960`  
**Example:** `27960`

**Description:**  
ET:Legacy game server port. Standard ET:Legacy port is 27960.

**Common Ports:**

- 27960 = Standard ET:Legacy
- 27950-27970 = Common ET server ports

---

### SERVER_PASSWORD

**Required:** No  
**Type:** String  
**Example:** `glhf`

**Description:**  
Server password for players joining the game (if password-protected).

---

### RCON_PASSWORD

**Required:** Yes (for server management)  
**Type:** String  
**Example:** `glavni123`

**Description:**  
RCON (Remote Console) password for server administration.

**Used By:**

- `!restart` command
- `!say` command
- `!kick` command
- `!rcon` command (direct RCON access)

**Security:**

- Never share this password
- Keep it different from SERVER_PASSWORD
- Restrict admin commands to ADMIN_CHANNEL_ID

---

## 🔐 SSH Configuration

### SSH_HOST

**Required:** Yes (for automation)  
**Type:** String  
**Example:** `puran.hehe.si`

**Description:**  
SSH hostname for connecting to your VPS/server.

**Usually Same As:** SERVER_HOST (but check your provider)

---

### SSH_PORT

**Required:** Yes  
**Type:** Integer  
**Default:** `22`  
**Example:** `48101`

**Description:**  
SSH port for server access. Standard SSH port is 22, but many servers use custom ports for security.

---

### SSH_USER

**Required:** Yes  
**Type:** String  
**Example:** `et`

**Description:**  
SSH username for server authentication.

---

### SSH_KEY_PATH

**Required:** Yes (for key-based auth)  
**Type:** String (file path)  
**Example:** `~/.ssh/etlegacy_bot`

**Description:**  
Path to your SSH private key file.

**Setup:**

```bash
# Generate SSH key pair
ssh-keygen -t ed25519 -f ~/.ssh/etlegacy_bot -C "etlegacy_bot"

# Copy public key to server
ssh-copy-id -i ~/.ssh/etlegacy_bot.pub et@puran.hehe.si -p 48101

# Set permissions
chmod 600 ~/.ssh/etlegacy_bot

# Test connection
ssh -i ~/.ssh/etlegacy_bot et@puran.hehe.si -p 48101
```sql

**Paths:**

- Windows: `C:/Users/YourName/.ssh/etlegacy_bot`
- Linux/Mac: `~/.ssh/etlegacy_bot` or `/home/user/.ssh/etlegacy_bot`

---

## 📁 ET:Legacy Server Paths

### ETLEGACY_BASE_DIR

**Required:** Yes  
**Type:** String (absolute path)  
**Example:** `/home/et/etlegacy-v2.83.1-x86_64`

**Description:**  
Root installation directory of ET:Legacy on your server.

---

### ETLEGACY_MOD_DIR

**Required:** Yes  
**Type:** String (absolute path)  
**Example:** `/home/et/etlegacy-v2.83.1-x86_64/legacy`

**Description:**  
Legacy mod directory where configs and stats are stored.

---

### ETLEGACY_STATS_DIR

**Required:** Yes (for automation)  
**Type:** String (absolute path)  
**Example:** `/home/et/etlegacy-v2.83.1-x86_64/legacy/gamestats`

**Description:**  
Directory where .stats files are generated by the server.

**Verification:**

```bash
# SSH into server and check
ls /home/et/etlegacy-v2.83.1-x86_64/legacy/gamestats
# Should show .stats files
```sql

---

### ETLEGACY_CONFIG_DIR

**Required:** No  
**Type:** String (absolute path)  
**Example:** `/home/et/etlegacy-v2.83.1-x86_64/legacy/configs`

**Description:**  
Configuration files directory (for future config management features).

---

### ETLEGACY_MAPS_DIR

**Required:** No  
**Type:** String (absolute path)  
**Example:** `/home/et/etlegacy-v2.83.1-x86_64/etmain`

**Description:**  
Maps directory (for future map management features).

---

### ETDAEMON_SCRIPT

**Required:** No  
**Type:** String (absolute path)  
**Example:** `/home/et/etlegacy-v2.83.1-x86_64/etdaemon.sh`

**Description:**  
Server daemon control script (for `!restart` command).

---

## 📂 Local Bot Paths

### LOCAL_STATS_DIR

**Required:** No  
**Type:** String (relative path)  
**Default:** `./stats_cache`  
**Example:** `./stats_cache`

**Description:**  
Local directory where bot caches downloaded .stats files.

**Auto-Created:** Yes

---

### DB_PATH

**Required:** No  
**Type:** String (relative path)  
**Default:** `./bot/etlegacy_production.db`  
**Example:** `./bot/etlegacy_production.db`

**Description:**  
SQLite database file path.

**Current Schema:** UNIFIED (53 columns, 7 tables)

---

### LOG_PATH

**Required:** No  
**Type:** String (relative path)  
**Default:** `./logs`  
**Example:** `./logs`

**Description:**  
Log files directory.

**Auto-Created:** Yes

---

## 🤖 Automation Configuration

### AUTOMATION_ENABLED

**Required:** No  
**Type:** Boolean  
**Default:** `false`  
**Example:** `true`

**Description:**  
Enable fully autonomous bot operation with voice channel detection.

**When Enabled:**

- Bot monitors GAMING_VOICE_CHANNELS
- Auto-starts session when 6+ join voice
- Auto-posts round summaries
- Auto-posts session summaries when everyone leaves

**Requirements:**

- SSH_ENABLED=true
- GAMING_VOICE_CHANNELS configured
- Valid SSH credentials

**Values:**

- `true` = Enable automation
- `false` = Manual commands only

---

### SSH_ENABLED

**Required:** No  
**Type:** Boolean  
**Default:** `false`  
**Example:** `true`

**Description:**  
Enable SSH file monitoring and automatic stats syncing.

**When Enabled:**

- Bot monitors server for new .stats files
- Auto-downloads and processes files
- Background task runs every 60 seconds

**Requirements:**

- Valid SSH credentials (SSH_HOST, SSH_PORT, SSH_USER, SSH_KEY_PATH)
- ETLEGACY_STATS_DIR configured

---

### GAMING_VOICE_CHANNELS

**Required:** No (required if AUTOMATION_ENABLED=true)  
**Type:** Comma-separated integers  
**Example:** `1420158097741058130,1420158097741058131`

**Description:**  
List of voice channel IDs to monitor for automatic session detection.

**Format:** Comma-separated with NO SPACES

**How to Get Channel IDs:**

1. Enable Developer Mode in Discord
2. Right-click voice channel → "Copy Channel ID"
3. Add to .env separated by commas

**Examples:**

```bash
# Single channel
GAMING_VOICE_CHANNELS=1420158097741058130

# Multiple channels
GAMING_VOICE_CHANNELS=1420158097741058130,1420158097741058131,1420158097741058132
```yaml

---

## 🧪 Testing Configuration

### Minimum Required (Basic Bot)

```bash
DISCORD_BOT_TOKEN=your_token_here
SERVER_HOST=puran.hehe.si
SERVER_PORT=27960
RCON_PASSWORD=your_rcon_password
```text

### Full Automation Setup

```bash
# Discord
DISCORD_BOT_TOKEN=your_token_here
GUILD_ID=1420158096801661011
STATS_CHANNEL_ID=1420158097741058130
ADMIN_CHANNEL_ID=1420158097741058131

# ET:Legacy Server
SERVER_HOST=puran.hehe.si
SERVER_PORT=27960
RCON_PASSWORD=glavni123

# SSH Access
SSH_HOST=puran.hehe.si
SSH_PORT=48101
SSH_USER=et
SSH_KEY_PATH=~/.ssh/etlegacy_bot

# Server Paths
ETLEGACY_STATS_DIR=/home/et/etlegacy-v2.83.1-x86_64/legacy/gamestats

# Automation
AUTOMATION_ENABLED=true
SSH_ENABLED=true
GAMING_VOICE_CHANNELS=1420158097741058130,1420158097741058131
```bash

---

## 🔍 Troubleshooting

### Bot Won't Start

1. Check DISCORD_BOT_TOKEN is correct
2. Verify .env file is in root directory
3. Check for syntax errors in .env (no quotes around values)

### Automation Not Working

1. Verify AUTOMATION_ENABLED=true (no quotes)
2. Check SSH_ENABLED=true
3. Verify GAMING_VOICE_CHANNELS has valid IDs
4. Test SSH connection manually

### SSH Connection Fails

1. Test: `ssh -i ~/.ssh/etlegacy_bot et@puran.hehe.si -p 48101`
2. Check SSH_KEY_PATH is correct
3. Verify key permissions: `chmod 600 ~/.ssh/etlegacy_bot`
4. Check SSH_HOST and SSH_PORT are correct

### Commands Not Working

1. Verify bot has correct Discord permissions
2. Check STATS_CHANNEL_ID is correct
3. Test with `!ping` command first

---

## 📝 .env File Template

See `.env.template` for complete working example with all variables and comments.

**Copy template:**

```bash
cp .env.template .env
# Then edit .env with your values
```yaml

---

## 🔒 Security Best Practices

1. **Never commit .env to git**
   - Add `.env` to `.gitignore`
   - Use `.env.template` for documentation

2. **Protect sensitive values**
   - DISCORD_BOT_TOKEN
   - RCON_PASSWORD
   - SSH_KEY_PATH

3. **Use restrictive file permissions**

   ```bash
   chmod 600 .env
   chmod 600 ~/.ssh/etlegacy_bot
   ```

1. **Separate admin channels**
   - Use ADMIN_CHANNEL_ID for server management
   - Restrict access to admin channel in Discord

2. **Regular key rotation**
   - Regenerate SSH keys periodically
   - Reset Discord bot token if compromised

---

**Last Updated:** October 11, 2025  
**Bot Version:** Production (5000+ lines)  
**Config Version:** 1.0  
**Total Variables:** 20+ configuration options
