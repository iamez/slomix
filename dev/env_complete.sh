# ===============================================
# ET:Legacy Discord Bot - Complete Configuration
# ===============================================
# Copy this file to .env and fill in your values

# ==================
# REQUIRED SETTINGS
# ==================

# Discord Bot Token (Get from: https://discord.com/developers/applications)
DISCORD_BOT_TOKEN=your_bot_token_here

# Your Discord Server ID
GUILD_ID=your_server_id_here

# Channel where stats will be posted
STATS_CHANNEL_ID=your_channel_id_here

# ==================
# SSH CONNECTION (Required for all remote features)
# ==================

SSH_ENABLED=true
SSH_HOST=your.vps.com
SSH_PORT=22
SSH_USER=et
SSH_KEY_PATH=~/.ssh/id_rsa
SSH_CHECK_INTERVAL=30

# Remote stats directory (for stats syncing)
REMOTE_STATS_DIR=/home/et/.etlegacy/legacy/gamestats

# ==================
# SERVER CONTROL (NEW!)
# ==================

# ET:Legacy Server Installation Path
ETLEGACY_PATH=/home/et/.etlegacy

# Screen session name for server process
SCREEN_NAME=etlegacy

# Server binary and config
SERVER_BINARY=./etlded
SERVER_CONFIG=server.cfg

# ==================
# RCON CONFIGURATION (NEW!)
# ==================
# Required for: map changes, kick/ban, server messages

RCON_ENABLED=true
RCON_HOST=your.vps.com
RCON_PORT=27960
RCON_PASSWORD=your_secure_rcon_password_here

# ==================
# SECURITY (NEW!)
# ==================

# Discord role name for admin commands
# Users with this role can control the server
ADMIN_ROLE=Server Admin

# Optional: Channel ID for audit logging
# All admin actions will be logged here
AUDIT_CHANNEL_ID=your_audit_channel_id

# ==================
# VOICE CHANNEL AUTOMATION (Optional)
# ==================
# Auto-start monitoring when players join voice

AUTOMATION_ENABLED=false
GAMING_VOICE_CHANNELS=channel_id1,channel_id2
ACTIVE_PLAYER_THRESHOLD=6
INACTIVE_DURATION_SECONDS=180

# ==================
# EXAMPLE VALUES
# ==================
# Here's what a complete config might look like:

# Discord
# DISCORD_BOT_TOKEN=MTIzNDU2Nzg5MDEyMzQ1Njc4OQ.GHI7jK.LMNOPqrstuvwxyzABCDEFGHIJKLMNOP
# GUILD_ID=987654321098765432
# STATS_CHANNEL_ID=123456789012345678

# SSH
# SSH_HOST=etlegacy.example.com
# SSH_PORT=22
# SSH_USER=et
# SSH_KEY_PATH=/home/yourname/.ssh/etlegacy_bot
# REMOTE_STATS_DIR=/home/et/.etlegacy/legacy/gamestats

# Server Control
# ETLEGACY_PATH=/home/et/.etlegacy
# SCREEN_NAME=etlegacy
# SERVER_BINARY=./etlded
# SERVER_CONFIG=server.cfg

# RCON
# RCON_ENABLED=true
# RCON_HOST=etlegacy.example.com
# RCON_PORT=27960
# RCON_PASSWORD=super_secure_random_password_here

# Security
# ADMIN_ROLE=Server Admin
# AUDIT_CHANNEL_ID=123456789012345679

# ==================
# SETUP CHECKLIST
# ==================
# 
# [ ] 1. Created Discord bot at https://discord.com/developers/applications
# [ ] 2. Added bot to your Discord server with proper permissions
# [ ] 3. Set up SSH key authentication to your VPS
# [ ] 4. Created "Server Admin" role in Discord
# [ ] 5. Configured RCON in your ET:Legacy server.cfg
# [ ] 6. Tested SSH connection: ssh -i ~/.ssh/id_rsa et@your.vps.com
# [ ] 7. Verified server directory structure exists
# [ ] 8. Created audit log channel (optional)
# [ ] 9. Set up gaming voice channels for automation (optional)
# [ ] 10. Tested RCON connection manually
#
# ==================
# SECURITY NOTES
# ==================
#
# ⚠️  CRITICAL SECURITY:
# - NEVER commit .env file to git (it's in .gitignore)
# - Use SSH keys, NOT passwords
# - Use strong RCON password (32+ random characters)
# - Only give "Server Admin" role to trusted people
# - Enable audit logging to track all actions
# - Regularly review who has admin access
#
# 🔒 Generate secure RCON password:
#    openssl rand -base64 32
#
# 🔑 Set up SSH key (if you don't have one):
#    ssh-keygen -t rsa -b 4096 -f ~/.ssh/etlegacy_bot
#    ssh-copy-id -i ~/.ssh/etlegacy_bot.pub et@your.vps.com
#
# ==================
# TROUBLESHOOTING
# ==================
#
# Bot won't connect to VPS:
#   - Test: ssh -i ~/.ssh/id_rsa et@your.vps.com
#   - Check: chmod 600 ~/.ssh/id_rsa
#   - Verify: SSH_HOST and SSH_PORT are correct
#
# RCON not working:
#   - Check: rconPassword in server.cfg matches RCON_PASSWORD
#   - Verify: Server is running and listening on RCON_PORT
#   - Test manually with nc: nc -u your.vps.com 27960
#
# Permission denied in Discord:
#   - Check: User has "Server Admin" role
#   - Verify: ADMIN_ROLE matches your Discord role name exactly
#   - Ensure: Bot has "Read Members" permission
#
# Server won't start:
#   - SSH to server and check: screen -ls
#   - View logs: tail -f /home/et/.etlegacy/legacy/etserver.log
#   - Try manual start: cd /home/et/.etlegacy && ./etlded +exec server.cfg
#
# ==================
# SUPPORT
# ==================
# Documentation: See README.md and docs/ folder
# Issues: https://github.com/yourusername/etlegacy-discord-bot/issues
# ET:Legacy: https://www.etlegacy.com
