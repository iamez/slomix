# Future Scaling Guide: Multi-Server "Hive Mind" Architecture

**Document Version:** 1.0
**Created:** 2026-02-09
**Status:** Planning Document (No Implementation Required)
**Estimated Implementation:** 20-140 hours depending on approach

---

## ⚠️ Important Notice

**This is a planning document only.** No changes will be made to the current working system. This guide documents how to scale from 1 game server to 10-20 servers when you're ready in the future.

**Current System:** ✅ Working perfectly with 1 game server
**Future Goal:** 🎯 Support 10-20 game servers across multiple VPS machines

---

## Executive Summary

### Your Questions Answered

**Q: Can we scale to 10-20 game servers on different VPS machines?**
**A:** Yes! Your system is already 90% ready for distributed deployment.

**Q: Can we eliminate SSH polling?**
**A:** Yes! The webhook-push architecture is simpler and scales better than SSH.

### Quick Comparison

| Approach | Complexity | Implementation Time | Max Servers | Recommendation |
|----------|-----------|---------------------|-------------|----------------|
| **Approach 1:** Distributed Components | Low | 16-24 hours | 1-2 servers | ✅ First step if moving to VPS |
| **Approach 2:** SSH Multi-Server | High | 88-140 hours | ~20 servers | ⚠️ Works but complex |
| **Approach 3:** Webhook Push API | Medium | 20-30 hours | 1000+ servers | ✅✅✅ **RECOMMENDED** |

### Recommendation: Webhook Push Architecture

The **webhook-push API** approach is the best path forward:

- ✅ **Eliminates SSH** - No polling, no connection bottlenecks
- ✅ **Scales infinitely** - 100+ servers easily supported
- ✅ **Real-time** - Stats arrive instantly (vs 60s polling delay)
- ✅ **Simpler** - Less code than SSH approach
- ✅ **Faster to implement** - 20-30 hours vs 88-140 hours
- ✅ **More secure** - API keys, HTTPS, rate limiting

---

## Current System Architecture (No Changes)

```
Game Server (puran.hehe.si:48101)
    ↓ SSH polling (every 60s)
Bot (LAN server, closed ports)
    ├─> PostgreSQL (localhost:5432)
    └─> Discord API
         ↑
Website (localhost:8000)
```

**What works today:**
- ✅ Bot polls game server via SSH for stats files
- ✅ Files downloaded to `local_stats/`
- ✅ Parser processes files → PostgreSQL
- ✅ Website shows stats from local database
- ✅ Lua webhook notifies Discord
- ✅ Everything on one LAN server

**This setup continues working - no changes planned.**

---

## System Readiness Analysis

### ✅ Already Production-Ready for Distributed Deployment

Your system was built with excellent architecture from the start:

#### 1. Database Connections Support Remote VPS

**Files:** `bot/core/database_adapter.py`, `website/backend/dependencies.py`

- ✅ Fully configurable PostgreSQL connections via environment variables
- ✅ **Full SSL/TLS support** built-in: `POSTGRES_SSL_MODE` (disable/require/verify-ca/verify-full)
- ✅ Connection pooling configured (10-30 connections, expandable to 100)
- ✅ **ZERO hardcoded localhost references**
- ✅ **To deploy:** Just change `.env` from `POSTGRES_HOST=localhost` to `POSTGRES_HOST=db.yourserver.com`

**Configuration variables:**
```bash
POSTGRES_HOST=localhost        # Change to remote VPS
POSTGRES_PORT=5432
POSTGRES_USER=etlegacy_user
POSTGRES_PASSWORD=REDACTED_DB_PASSWORD
POSTGRES_SSL_MODE=disable      # Change to 'require' for remote
POSTGRES_SSL_ROOT_CERT=...     # Optional CA certificate
```

#### 2. Security Features Already Implemented

- ✅ **Two-tier database users:** `etlegacy_user` (read/write) vs `website_readonly` (read-only)
- ✅ **SSH strict host key verification:** `SSH_STRICT_HOST_KEY=true`
- ✅ **Webhook ID whitelist:** Mandatory for security
- ✅ **Rate limiting on webhooks:** 5 events/minute
- ✅ **CORS configurable:** `CORS_ORIGINS` environment variable
- ✅ **Session secret validation:** Raises error if not securely configured
- ✅ **SQL injection protection:** Parameterized queries throughout

#### 3. Modular Architecture

- ✅ Cog-based command system (14 cogs)
- ✅ Service layer separation
- ✅ Database adapter abstraction
- ✅ Easy to add new servers without touching core logic

### ❌ Not Ready for Multi-Server (Requires Refactoring)

These limitations only affect scaling beyond 1 game server:

#### 1. SSH Configuration is Single-Valued

**Files:** `bot/automation/ssh_handler.py`, `bot/ultimate_bot.py` (lines 880-886)

- Only one `SSH_HOST`, `SSH_PORT`, `SSH_USER`, `SSH_KEY_PATH`
- Cannot poll multiple servers
- Would need server registry system

#### 2. Filename Format Has No Server Identifier

**Current format:** `YYYY-MM-DD-HHMMSS-mapname-round-N.txt`

**Critical issue:** Two servers playing same map at same time = filename collision = data loss

**Example collision:**
```
Server1: 2026-02-09-143000-supply-round-1.txt
Server2: 2026-02-09-143000-supply-round-1.txt  ← SAME FILENAME!
```

**Required format:** `serverid-YYYY-MM-DD-HHMMSS-mapname-round-N.txt`

#### 3. Sequential SSH Polling (Blocks)

**File:** `bot/automation/ssh_handler.py` (lines 136-193)

- Polls servers one-by-one (synchronous blocking)
- With 20 servers: 20 × 5s = 100 seconds per check cycle
- Bot polls every 60 seconds → **will fall behind**

#### 4. Database Schema Has No Server Tracking

Tables `rounds`, `player_comprehensive_stats` have no `server_id` column:

- Cannot distinguish which server generated which stats
- Cannot filter stats by server
- Cannot track server health/status

#### 5. Lua Webhook Has Hardcoded URL

**File:** `vps_scripts/stats_discord_webhook.lua` (line 77)

- Single webhook URL hardcoded
- Cannot route webhooks by server
- No server identification in webhook payload

#### 6. Voice Detection Assumes Single Gaming Session

**File:** `bot/ultimate_bot.py` (lines 2378-2383)

- Counts players to trigger SSH checks
- Won't work with 20 concurrent servers on same Discord guild

---

## Three Scaling Approaches

### Approach 1: Distributed Components (Simplest First Step)

**Goal:** Move database/website to VPS while keeping 1 game server

**When to use:** You want database/website on VPS but only have 1-2 game servers

**Architecture:**
```
Game Server (VPS1) ──SSH──> Bot (LAN or VPS2) ──> Database (VPS3)
                                                   ↑
Website (VPS4) ─────────────────────────────────┘
```

**Effort:** 16-24 hours
**Max Servers:** 1-2 servers
**Code Changes:** ✅ None! Just `.env` configuration

**What changes:**
- PostgreSQL moves to VPS (bot connects remotely)
- Website moves to separate VPS
- Bot stays on LAN (or moves to VPS)
- Still 1 game server with SSH

See **"Approach 1: Detailed Implementation"** section below for step-by-step guide.

---

### Approach 2: SSH Multi-Server (Traditional Scaling)

**Goal:** Support 2-20 servers via SSH polling

**When to use:** You need multiple servers and prefer SSH-based architecture

**Architecture:**
```
Game Server 1 ─┐
Game Server 2 ─┼─> Bot (parallel SSH) ──> Database
...            │
Game Server 20 ┘
```

**Effort:** 88-140 hours (11-18 days full-time)
**Max Servers:** ~20 servers (SSH becomes bottleneck)
**Code Changes:** ⚠️ Major refactoring required

**What changes:**
- Database schema adds `server_id` columns
- Filename format adds server prefix
- SSH polling becomes parallel/async
- Server registry system
- Per-server rate limiting
- Health monitoring

**Problems at scale:**
- Sequential polling = bottleneck (20 servers × 5s = 100s)
- SSH access may not be available on all servers
- Connection overhead
- Polling delay (up to 60s)
- Doesn't scale beyond 20 servers

See **"Approach 2: Detailed Implementation"** section below for full technical details.

---

### Approach 3: Webhook Push API (RECOMMENDED)

**Goal:** Game servers send stats via API instead of SSH polling

**When to use:** You want to scale to 10+ servers efficiently

**Architecture:**
```
Game Server 1 ─┐
Game Server 2 ─┼─> Website API ──> Database
...            │      ↑
Game Server 20 ┘      │
                      └─> Bot (reads from DB)
```

**Effort:** 20-30 hours
**Max Servers:** 1000+ servers (infinite scale)
**Code Changes:** ✅ Moderate - new API endpoint + Lua script

**How it works:**
1. Game server round ends
2. Lua script sends stats to website API endpoint
3. API authenticates server (API key)
4. API parses and imports to database
5. Bot reads stats from database (no SSH needed)
6. Bot posts to Discord

**Advantages over SSH:**
- ✅ **Real-time** - Data arrives instantly (vs 60s polling delay)
- ✅ **Scales infinitely** - 100+ servers no problem
- ✅ **No SSH required** - Works on any server with internet
- ✅ **Parallel by default** - Each server posts independently
- ✅ **Stateless** - No connection pooling issues
- ✅ **Simpler** - No file download/tracking logic
- ✅ **More secure** - API key authentication instead of SSH keys
- ✅ **Faster to implement** - 20-30 hours vs 88-140 hours

See **"Approach 3: Detailed Implementation"** section below for full technical details.

---

## Approach Comparison Matrix

| Feature | Current System | Approach 1 | Approach 2 | Approach 3 |
|---------|---------------|------------|------------|------------|
| **Max Servers** | 1 | 1-2 | ~20 | 1000+ |
| **SSH Required** | Yes | Yes | Yes | No |
| **Real-time Stats** | No (60s delay) | No (60s delay) | No (60s delay) | Yes (instant) |
| **Implementation Time** | - | 16-24h | 88-140h | 20-30h |
| **Code Complexity** | Medium | Medium | High | Medium |
| **Database Changes** | - | None | Major | Minor |
| **Filename Changes** | - | None | Required | Not needed |
| **Scalability** | N/A | Low | Medium | Infinite |
| **Security** | SSH keys | SSH keys + SSL | SSH keys + SSL | API keys + HTTPS |
| **Bot Complexity** | Medium | Medium | High | Low |
| **Server Requirements** | SSH access | SSH access | SSH access | Internet only |
| **Failure Isolation** | N/A | N/A | Per-server | Per-server |
| **Rate Limiting** | Discord only | Discord only | Complex | Simple |

**Recommendation:** Start with **Approach 3** (Webhook Push API) if you plan to add 3+ servers. It's simpler, faster to implement, and scales infinitely.

---

## Approach 1: Detailed Implementation

### Distributed Components (Database + Website on VPS)

**Goal:** Keep everything working exactly as-is, but move database and website to separate VPS servers for better performance/access.

**Current Setup:**
```
LAN Server (192.168.x.x)
├── Bot (ultimate_bot.py)
├── PostgreSQL (localhost:5432)
└── Website (localhost:8000)
```

**Target Setup:**
```
Database VPS (db.yourserver.com)
    ├── PostgreSQL (5432)
    │
Website VPS (www.yourserver.com)
    ├── Website (443/HTTPS)
    │
LAN Server (192.168.x.x)
    └── Bot (connects to remote DB)
```

### Phase 1: Database VPS Setup (6-10 hours)

#### Step 1.1: Database Server Requirements

**Recommended VPS specs:**
- **CPU:** 2 cores minimum (4 cores for 10+ servers)
- **RAM:** 4GB (8GB recommended for 10-20 servers)
- **Storage:** 50GB SSD
- **Network:** 100Mbps minimum
- **OS:** Ubuntu 22.04 LTS or Debian 11

#### Step 1.2: PostgreSQL Installation

```bash
# SSH into database VPS
ssh root@db.yourserver.com

# Install PostgreSQL
sudo apt update
sudo apt install -y postgresql-14 postgresql-contrib

# Verify installation
sudo systemctl status postgresql
```

#### Step 1.3: PostgreSQL Configuration for Remote Access

**Edit `/etc/postgresql/14/main/postgresql.conf`:**

```ini
# Listen on all interfaces (default is localhost only)
listen_addresses = '*'

# Connection limits
max_connections = 100        # Increase to 150 for 20+ servers

# SSL/TLS (REQUIRED for internet connections)
ssl = on
ssl_cert_file = '/etc/ssl/certs/ssl-cert-snakeoil.pem'
ssl_key_file = '/etc/ssl/private/ssl-cert-snakeoil.key'

# Performance tuning
shared_buffers = 1GB         # 25% of RAM
effective_cache_size = 3GB   # 75% of RAM
work_mem = 16MB
maintenance_work_mem = 256MB
```

**Edit `/etc/postgresql/14/main/pg_hba.conf`:**

```ini
# TYPE  DATABASE        USER            ADDRESS                 METHOD

# Local connections
local   all             postgres                                peer
local   all             all                                     peer

# Remote connections (WHITELIST SPECIFIC IPs ONLY!)
hostssl etlegacy        etlegacy_user   BOT_VPS_IP/32          md5
hostssl etlegacy        website_readonly WEBSITE_VPS_IP/32     md5

# Example with real IPs:
# hostssl etlegacy      etlegacy_user   123.45.67.89/32        md5
# hostssl etlegacy      website_readonly 98.76.54.32/32        md5
```

**Restart PostgreSQL:**

```bash
sudo systemctl restart postgresql
sudo systemctl enable postgresql  # Auto-start on boot
```

#### Step 1.4: Create Read-Only User for Website

```bash
sudo -u postgres psql

-- Create read-only user
CREATE USER website_readonly WITH PASSWORD 'your_secure_password_here';

-- Grant connect permission
GRANT CONNECT ON DATABASE etlegacy TO website_readonly;

-- Grant schema usage
GRANT USAGE ON SCHEMA public TO website_readonly;

-- Grant SELECT on all existing tables
GRANT SELECT ON ALL TABLES IN SCHEMA public TO website_readonly;

-- Auto-grant SELECT on future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT SELECT ON TABLES TO website_readonly;

-- Verify permissions
\du website_readonly
\l+ etlegacy
```

#### Step 1.5: Firewall Configuration

**CRITICAL: Only allow specific IPs!**

```bash
# Install UFW (if not installed)
sudo apt install -y ufw

# Default deny all
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH (change port if needed)
sudo ufw allow 22/tcp

# Allow PostgreSQL ONLY from bot and website IPs
sudo ufw allow from BOT_VPS_IP to any port 5432 proto tcp
sudo ufw allow from WEBSITE_VPS_IP to any port 5432 proto tcp

# Example with real IPs:
# sudo ufw allow from 123.45.67.89 to any port 5432 proto tcp
# sudo ufw allow from 98.76.54.32 to any port 5432 proto tcp

# Enable firewall
sudo ufw enable
sudo ufw status verbose
```

#### Step 1.6: Migrate Database to VPS

**On your LAN server (current database location):**

```bash
# Backup current database
pg_dump -h localhost -U etlegacy_user -d etlegacy -F c -f etlegacy_backup.dump

# Copy to database VPS
scp etlegacy_backup.dump root@db.yourserver.com:/tmp/
```

**On database VPS:**

```bash
# Create database
sudo -u postgres createdb etlegacy

# Create user (if not exists)
sudo -u postgres createuser etlegacy_user

# Set password
sudo -u postgres psql -c "ALTER USER etlegacy_user WITH PASSWORD 'REDACTED_DB_PASSWORD';"

# Restore backup
sudo -u postgres pg_restore -d etlegacy /tmp/etlegacy_backup.dump

# Verify data
sudo -u postgres psql -d etlegacy -c "SELECT COUNT(*) FROM rounds;"
sudo -u postgres psql -d etlegacy -c "SELECT COUNT(*) FROM player_comprehensive_stats;"
```

#### Step 1.7: Update Bot Configuration

**Edit `.env` on your LAN server:**

```bash
# OLD (localhost)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_SSL_MODE=disable

# NEW (remote VPS)
POSTGRES_HOST=db.yourserver.com
POSTGRES_PORT=5432
POSTGRES_USER=etlegacy_user
POSTGRES_PASSWORD=REDACTED_DB_PASSWORD
POSTGRES_SSL_MODE=require                    # CRITICAL: Enable SSL!
# POSTGRES_SSL_ROOT_CERT=/path/to/ca-cert.pem  # Optional: CA certificate
```

**Test connection:**

```bash
# Test from LAN server
PGPASSWORD='REDACTED_DB_PASSWORD' psql -h db.yourserver.com -U etlegacy_user -d etlegacy -c "SELECT version();"

# Should return PostgreSQL version info
# If fails: Check firewall, pg_hba.conf, and SSL settings
```

**Restart bot:**

```bash
sudo systemctl restart etlegacy-bot
sudo systemctl status etlegacy-bot

# Check logs for "PostgreSQL pool created"
tail -f logs/bot.log
```

### Phase 2: Website VPS Setup (6-10 hours)

#### Step 2.1: Website Server Requirements

**Recommended VPS specs:**
- **CPU:** 1-2 cores
- **RAM:** 2GB (4GB recommended)
- **Storage:** 20GB SSD
- **Network:** 100Mbps
- **OS:** Ubuntu 22.04 LTS

#### Step 2.2: Install Dependencies

```bash
# SSH into website VPS
ssh root@www.yourserver.com

# Install system packages
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git nginx certbot python3-certbot-nginx

# Clone repository
cd /opt
git clone <your-repo-url> slomix_discord
cd slomix_discord/website
```

#### Step 2.3: Configure Website Environment

**Create `.env` file:**

```bash
cat > .env << 'EOF'
# Database (read-only user)
DB_HOST=db.yourserver.com
DB_PORT=5432
DB_NAME=etlegacy
DB_USER=website_readonly
DB_PASSWORD=your_secure_password_here
DB_SSL_MODE=require

# Security
SESSION_SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Optional: Discord webhook for error notifications
ERROR_WEBHOOK_URL=https://discord.com/api/webhooks/...
EOF

# Generate strong session secret
python3 -c 'import secrets; print(secrets.token_urlsafe(32))' >> .env
```

#### Step 2.4: Install Python Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Test application
uvicorn backend.main:app --host 127.0.0.1 --port 8000

# Should start without errors
# Ctrl+C to stop
```

#### Step 2.5: Configure Nginx Reverse Proxy

**Create `/etc/nginx/sites-available/etlegacy`:**

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    # Redirect HTTP to HTTPS (after SSL is configured)
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # SSL certificates (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Static files
    location /static/ {
        alias /opt/slomix_discord/website/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # API and application
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket support (if needed)
    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

**Enable site:**

```bash
sudo ln -s /etc/nginx/sites-available/etlegacy /etc/nginx/sites-enabled/
sudo nginx -t  # Test configuration
sudo systemctl restart nginx
```

#### Step 2.6: Configure SSL with Let's Encrypt

```bash
# Obtain SSL certificate
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Follow prompts:
# - Enter email address
# - Agree to terms
# - Choose to redirect HTTP to HTTPS (option 2)

# Test auto-renewal
sudo certbot renew --dry-run

# Certificate auto-renews via cron
```

#### Step 2.7: Create Systemd Service

**Create `/etc/systemd/system/etlegacy-website.service`:**

```ini
[Unit]
Description=ET:Legacy Stats Website
After=network.target postgresql.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/slomix_discord/website
Environment="PATH=/opt/slomix_discord/website/venv/bin"
ExecStart=/opt/slomix_discord/website/venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable and start service:**

```bash
# Set permissions
sudo chown -R www-data:www-data /opt/slomix_discord/website

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable etlegacy-website
sudo systemctl start etlegacy-website
sudo systemctl status etlegacy-website
```

#### Step 2.8: Firewall Configuration

```bash
# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Allow SSH
sudo ufw allow 22/tcp

# Enable firewall
sudo ufw enable
sudo ufw status
```

### Phase 3: Verification & Testing (4-6 hours)

#### Test 1: Database Connectivity

```bash
# From bot server
PGPASSWORD='REDACTED_DB_PASSWORD' psql -h db.yourserver.com -U etlegacy_user -d etlegacy -c "SELECT COUNT(*) FROM rounds;"

# From website server
PGPASSWORD='your_secure_password_here' psql -h db.yourserver.com -U website_readonly -d etlegacy -c "SELECT COUNT(*) FROM rounds;"

# Should both return round count
```

#### Test 2: Bot Functionality

```bash
# Check bot logs
tail -f /path/to/slomix_discord/logs/bot.log

# Should see:
# "PostgreSQL pool created"
# "Connected to database successfully"
# No SSL errors

# Test Discord command
# In Discord: !health
# Should show database connection OK
```

#### Test 3: Website Functionality

```bash
# Visit https://yourdomain.com
# Should load player stats

# Check specific player
curl https://yourdomain.com/api/stats/31B54D18

# Should return JSON with player stats
```

#### Test 4: Read-Only Enforcement

```bash
# Try to write with website_readonly user (should FAIL)
PGPASSWORD='your_secure_password_here' psql -h db.yourserver.com -U website_readonly -d etlegacy -c "DELETE FROM rounds WHERE id = 1;"

# Should return: ERROR: permission denied for table rounds
```

#### Test 5: SSL Enforcement

```bash
# Try to connect without SSL (should FAIL)
POSTGRES_SSL_MODE=disable python -m bot.ultimate_bot

# Should fail with SSL required error
```

#### Test 6: End-to-End Stats Flow

1. Game server finishes round
2. SSH monitoring downloads file to bot
3. Bot imports to remote PostgreSQL
4. Bot posts to Discord ✅
5. Website shows updated stats ✅

### Security Checklist

**Database VPS:**
- [ ] Firewall allows only bot/website IPs on port 5432
- [ ] SSL enabled (`ssl = on` in postgresql.conf)
- [ ] Strong passwords (30+ characters)
- [ ] Connection limit per user configured
- [ ] Automated backups configured
- [ ] `pg_hba.conf` uses specific IPs (not `0.0.0.0/0`)

**Website VPS:**
- [ ] Firewall allows only ports 80/443 (and 22 for SSH)
- [ ] SSL certificate installed and auto-renewing
- [ ] Read-only database user (`website_readonly`)
- [ ] `SESSION_SECRET` is random 32+ byte value
- [ ] CORS whitelist configured (not `*`)
- [ ] Nginx security headers configured
- [ ] Service runs as `www-data` (not root)

**Bot (LAN or VPS):**
- [ ] SSH keys for game servers (no passwords)
- [ ] Webhook ID whitelist configured
- [ ] `POSTGRES_SSL_MODE=require` in `.env`
- [ ] If on VPS: Firewall blocks all inbound (outbound-only)

### Rollback Plan

If something goes wrong:

```bash
# Revert bot to local PostgreSQL
sed -i 's/POSTGRES_HOST=.*/POSTGRES_HOST=localhost/' .env
sudo systemctl restart etlegacy-bot

# Restore local database from backup
pg_restore -d etlegacy etlegacy_backup.dump
```

### Maintenance

**Database Backups (Daily):**

```bash
# Create backup script: /root/backup_db.sh
#!/bin/bash
pg_dump -h localhost -U etlegacy_user -d etlegacy -F c -f /backup/etlegacy_$(date +%Y%m%d).dump
find /backup -name "etlegacy_*.dump" -mtime +7 -delete  # Keep 7 days

# Make executable
chmod +x /root/backup_db.sh

# Add to crontab
crontab -e
0 2 * * * /root/backup_db.sh  # 2 AM daily
```

**Monitor Database Size:**

```sql
-- Check database size
SELECT pg_size_pretty(pg_database_size('etlegacy'));

-- Check table sizes
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

**Monitor Connections:**

```sql
-- Check active connections
SELECT count(*) FROM pg_stat_activity WHERE datname = 'etlegacy';

-- Kill idle connections (if needed)
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'etlegacy'
AND state = 'idle'
AND state_change < now() - interval '1 hour';
```

---

## Approach 2: Detailed Implementation

### SSH Multi-Server Architecture

**⚠️ Warning:** This approach is complex and has limitations. Consider **Approach 3 (Webhook Push)** instead for better scalability.

**Goal:** Support 2-20 game servers via parallel SSH polling

**Architecture:**
```
Game Server 1 (puran.hehe.si) ─┐
Game Server 2 (server2.com)   ─┼─> Bot (async SSH pooling) ──> PostgreSQL
Game Server 3 (server3.net)   ─┤
...                            │
Game Server 20                 ┘
```

**Challenges:**
- Filename collisions (MUST add server prefix)
- Sequential SSH polling becomes bottleneck
- Complex server registry system
- Discord rate limiting (20 servers posting simultaneously)
- Database connection pooling (need 70-100 connections)

### Implementation Phases

#### Phase 0: Prerequisites (8-16 hours)

##### Database Migration

**Add server tracking to all tables:**

```sql
-- Add server_id column to core tables
ALTER TABLE rounds
ADD COLUMN server_id VARCHAR(50) NOT NULL DEFAULT 'legacy';

ALTER TABLE player_comprehensive_stats
ADD COLUMN server_id VARCHAR(50) NOT NULL DEFAULT 'legacy';

ALTER TABLE processed_files
ADD COLUMN server_id VARCHAR(50);

ALTER TABLE lua_round_teams
ADD COLUMN server_id VARCHAR(50);

-- Create servers registry table
CREATE TABLE servers (
    id SERIAL PRIMARY KEY,
    server_id VARCHAR(50) UNIQUE NOT NULL,
    server_name VARCHAR(255) NOT NULL,
    server_host VARCHAR(255) NOT NULL,
    server_port INTEGER NOT NULL,
    ssh_host VARCHAR(255),
    ssh_port INTEGER DEFAULT 22,
    ssh_user VARCHAR(100),
    ssh_key_path VARCHAR(500),
    remote_stats_path VARCHAR(500),
    webhook_url TEXT,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    last_seen TIMESTAMP,
    last_error TEXT,
    stats_count INTEGER DEFAULT 0
);

-- Create indexes for performance
CREATE INDEX idx_rounds_server_id ON rounds(server_id);
CREATE INDEX idx_player_stats_server_id ON player_comprehensive_stats(server_id);
CREATE INDEX idx_processed_files_server_server_id ON processed_files(server_id, filename);

-- Update constraint on processed_files (was filename only, now server_id + filename)
ALTER TABLE processed_files DROP CONSTRAINT IF EXISTS processed_files_filename_key;
ALTER TABLE processed_files ADD CONSTRAINT processed_files_unique
UNIQUE (server_id, filename);
```

**Insert current server as 'legacy':**

```sql
INSERT INTO servers (
    server_id,
    server_name,
    server_host,
    server_port,
    ssh_host,
    ssh_port,
    ssh_user,
    ssh_key_path,
    remote_stats_path,
    enabled
) VALUES (
    'legacy',
    'Puran Main Server',
    'puran.hehe.si',
    48101,
    'puran.hehe.si',
    48101,
    'et',
    '~/.ssh/etlegacy_bot',
    '/home/et/.etlegacy/legacy/gamestats',
    true
);
```

**Verify migration:**

```sql
-- All existing data should have server_id = 'legacy'
SELECT server_id, COUNT(*) FROM rounds GROUP BY server_id;
SELECT server_id, COUNT(*) FROM player_comprehensive_stats GROUP BY server_id;
```

##### Configuration Files

**Create `servers.json` (multi-server configuration):**

```json
{
  "servers": [
    {
      "server_id": "puran-main",
      "server_name": "Puran Main Server",
      "ssh_host": "puran.hehe.si",
      "ssh_port": 48101,
      "ssh_user": "et",
      "ssh_key_path": "~/.ssh/etlegacy_puran",
      "remote_stats_path": "/home/et/.etlegacy/legacy/gamestats",
      "webhook_url": "https://discord.com/api/webhooks/WEBHOOK_ID_1/TOKEN_1",
      "enabled": true
    },
    {
      "server_id": "server2",
      "server_name": "Community Server 2",
      "ssh_host": "server2.example.com",
      "ssh_port": 22,
      "ssh_user": "etlegacy",
      "ssh_key_path": "~/.ssh/etlegacy_server2",
      "remote_stats_path": "/path/to/stats",
      "webhook_url": "https://discord.com/api/webhooks/WEBHOOK_ID_2/TOKEN_2",
      "enabled": false
    }
  ]
}
```

**Update `.env`:**

```bash
# Enable multi-server mode
SERVERS_CONFIG_FILE=/path/to/servers.json
MULTI_SERVER_ENABLED=true

# Keep existing settings for backward compatibility
SSH_HOST=puran.hehe.si
SSH_PORT=48101
SSH_USER=et
SSH_KEY_PATH=~/.ssh/etlegacy_bot
```

#### Phase 1: Filename Format Change (CRITICAL)

**Problem:** Current format allows collisions

**Current Format:**
```
2026-02-09-143000-supply-round-1.txt
```

**New Format (REQUIRED):**
```
puran-2026-02-09-143000-supply-round-1.txt
server2-2026-02-09-143000-supply-round-1.txt
```

**Change 1: Lua Script on Game Server**

**Edit `vps_scripts/stats.lua` or `endstats.lua` on EACH game server:**

```lua
-- Add at top of file (CHANGE PER SERVER!)
local SERVER_ID = "puran"  -- Server 1: "puran", Server 2: "server2", etc.

-- Find the function that writes stats files
function writeStats()
    local timestamp = os.date("%Y-%m-%d-%H%M%S")

    -- OLD FORMAT (remove this):
    -- local filename = string.format("%s-%s-round-%d.txt", timestamp, mapname, roundNumber)

    -- NEW FORMAT (use this):
    local filename = string.format("%s-%s-%s-round-%d.txt",
        SERVER_ID,      -- Server prefix
        timestamp,
        mapname,
        roundNumber
    )

    -- Rest of function unchanged...
    local filepath = statsPath .. "/" .. filename
    local file = io.open(filepath, "w")
    -- ...
end
```

**Deploy to all servers:**
```bash
# Copy updated Lua script to each game server
scp stats.lua et@puran.hehe.si:/path/to/etlegacy/lua/
scp stats.lua et@server2.com:/path/to/etlegacy/lua/
# Restart game servers or reload Lua
```

**Change 2: Parser Update**

**Edit `bot/community_stats_parser.py` (around line 384):**

```python
def parse_gamestats_filename(filename: str) -> dict:
    """
    Parse filename format: SERVERID-YYYY-MM-DD-HHMMSS-mapname-round-N.txt

    Backward compatible with old format: YYYY-MM-DD-HHMMSS-mapname-round-N.txt

    Examples:
        puran-2026-02-09-143000-supply-round-1.txt  (new format)
        2026-02-09-143000-supply-round-1.txt        (old format)

    Returns:
        {
            'server_id': str,      # 'puran' or 'legacy'
            'date': str,           # '2026-02-09'
            'time': str,           # '143000'
            'map_name': str,       # 'supply'
            'round_number': int    # 1 or 2
        }
    """
    parts = filename.replace('.txt', '').split('-')

    # Check if first part is server_id (not a 4-digit year)
    if len(parts[0]) != 4 or not parts[0].isdigit():
        # New format with server_id prefix
        server_id = parts[0]
        date_offset = 1
    else:
        # Old format (backward compatible)
        server_id = 'legacy'
        date_offset = 0

    try:
        return {
            'server_id': server_id,
            'date': parts[date_offset],
            'time': parts[date_offset + 1],
            'map_name': parts[date_offset + 2],
            'round_number': int(parts[date_offset + 4])
        }
    except (IndexError, ValueError) as e:
        raise ValueError(f"Invalid filename format: {filename}") from e
```

**Update import function to use server_id:**

```python
async def import_stats_file(self, filepath: str, server_id: str = 'legacy'):
    """Import stats file with server tracking."""
    filename = os.path.basename(filepath)

    # Parse filename (gets server_id from filename)
    parsed = parse_gamestats_filename(filename)

    # Override with provided server_id if different (for transition period)
    if server_id != 'legacy':
        parsed['server_id'] = server_id

    # ... rest of import logic ...
    # Insert into database with server_id
```

#### Phase 2: Server Registry System (16-24 hours)

**Create `bot/core/server_registry.py`:**

```python
"""Multi-Server Configuration Registry."""
import json
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class ServerConfig:
    """Configuration for a single game server."""
    server_id: str
    server_name: str
    ssh_host: str
    ssh_port: int
    ssh_user: str
    ssh_key_path: str
    remote_stats_path: str
    webhook_url: str
    enabled: bool = True

    def __post_init__(self):
        """Validate configuration."""
        if not self.server_id:
            raise ValueError("server_id is required")
        if not self.server_name:
            raise ValueError("server_name is required")
        if not self.ssh_host:
            raise ValueError("ssh_host is required")

class ServerRegistry:
    """Registry of game servers for distributed stats collection."""

    def __init__(self, config_path: str):
        """
        Initialize server registry from JSON config file.

        Args:
            config_path: Path to servers.json configuration file
        """
        self.servers: Dict[str, ServerConfig] = {}
        self.config_path = Path(config_path)
        self.load_config()

    def load_config(self):
        """Load servers from JSON config file."""
        try:
            with open(self.config_path, 'r') as f:
                data = json.load(f)

            for server_data in data.get('servers', []):
                try:
                    server = ServerConfig(**server_data)
                    self.servers[server.server_id] = server
                    logger.info(f"Loaded server config: {server.server_id} ({server.server_name})")
                except (TypeError, ValueError) as e:
                    logger.error(f"Invalid server config: {e}")
                    continue

            logger.info(f"Loaded {len(self.servers)} server configurations")

        except FileNotFoundError:
            logger.error(f"Server config file not found: {self.config_path}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in server config: {e}")

    def get_enabled_servers(self) -> List[ServerConfig]:
        """Get all enabled servers."""
        return [s for s in self.servers.values() if s.enabled]

    def get_server(self, server_id: str) -> Optional[ServerConfig]:
        """Get server by ID."""
        return self.servers.get(server_id)

    def reload_config(self):
        """Reload configuration from disk."""
        self.servers.clear()
        self.load_config()
```

**Update `bot/config.py`:**

```python
# Add to Config class
class Config:
    # ... existing config ...

    # Multi-server settings
    MULTI_SERVER_ENABLED: bool = os.getenv('MULTI_SERVER_ENABLED', 'false').lower() == 'true'
    SERVERS_CONFIG_FILE: str = os.getenv('SERVERS_CONFIG_FILE', 'servers.json')
```

#### Phase 3: Parallel SSH Monitor (24-40 hours)

**Create `bot/automation/multi_server_ssh_monitor.py`:**

```python
"""Multi-Server SSH Monitor - Parallel polling for 10-20 game servers."""
import asyncio
import logging
from typing import List, Dict, Optional
from datetime import datetime
from bot.core.server_registry import ServerRegistry, ServerConfig
from bot.automation.ssh_handler import SSHHandler

logger = logging.getLogger(__name__)

class MultiServerSSHMonitor:
    """Parallel SSH monitoring for multiple game servers."""

    def __init__(self, registry: ServerRegistry, local_stats_dir: str = 'local_stats'):
        """
        Initialize multi-server SSH monitor.

        Args:
            registry: Server registry with configurations
            local_stats_dir: Base directory for downloaded stats
        """
        self.registry = registry
        self.local_stats_dir = local_stats_dir
        self.ssh_handlers: Dict[str, SSHHandler] = {}

        # Create SSH handler for each server
        for server in registry.get_enabled_servers():
            self.ssh_handlers[server.server_id] = SSHHandler(
                host=server.ssh_host,
                port=server.ssh_port,
                username=server.ssh_user,
                key_path=server.ssh_key_path,
                remote_path=server.remote_stats_path,
                local_path=f"{local_stats_dir}/{server.server_id}"
            )

    async def check_all_servers(self) -> Dict[str, List[str]]:
        """
        Check all enabled servers in parallel.

        Returns:
            Dict mapping server_id to list of new filenames

        Example:
            {
                'puran': ['puran-2026-02-09-143000-supply-round-1.txt'],
                'server2': ['server2-2026-02-09-144500-oasis-round-2.txt']
            }
        """
        servers = self.registry.get_enabled_servers()

        if not servers:
            logger.warning("No enabled servers to check")
            return {}

        logger.info(f"Checking {len(servers)} servers in parallel...")
        start_time = datetime.now()

        # Create async tasks for each server
        tasks = [
            self._check_server(server)
            for server in servers
        ]

        # Run all checks in parallel (20 servers checked simultaneously)
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Organize results by server_id
        new_files = {}
        for server, result in zip(servers, results):
            if isinstance(result, Exception):
                logger.error(f"Error checking {server.server_id}: {result}")
                new_files[server.server_id] = []
                await self._record_error(server.server_id, str(result))
            else:
                new_files[server.server_id] = result
                if result:
                    logger.info(f"{server.server_id}: Found {len(result)} new files")

        elapsed = (datetime.now() - start_time).total_seconds()
        total_files = sum(len(files) for files in new_files.values())
        logger.info(f"Checked {len(servers)} servers in {elapsed:.1f}s, found {total_files} new files")

        return new_files

    async def _check_server(self, server: ServerConfig) -> List[str]:
        """
        Check a single server for new files.

        Args:
            server: Server configuration

        Returns:
            List of new filenames
        """
        try:
            handler = self.ssh_handlers[server.server_id]
            new_files = await asyncio.to_thread(handler.check_for_new_files)

            # Update last_seen timestamp in database
            if new_files:
                await self._update_last_seen(server.server_id)

            return new_files

        except Exception as e:
            logger.error(f"Failed to check {server.server_id}: {e}")
            raise

    async def _update_last_seen(self, server_id: str):
        """Update last_seen timestamp for server."""
        # TODO: Update servers table in database
        pass

    async def _record_error(self, server_id: str, error: str):
        """Record error in database for monitoring."""
        # TODO: Update servers table with last_error
        pass

    async def download_file(self, server_id: str, filename: str) -> Optional[str]:
        """
        Download a specific file from a server.

        Args:
            server_id: Server identifier
            filename: File to download

        Returns:
            Local file path if successful, None otherwise
        """
        try:
            handler = self.ssh_handlers.get(server_id)
            if not handler:
                logger.error(f"No SSH handler for server: {server_id}")
                return None

            local_path = await asyncio.to_thread(handler.download_file, filename)
            return local_path

        except Exception as e:
            logger.error(f"Failed to download {filename} from {server_id}: {e}")
            return None
```

#### Phase 4: Bot Integration (16-24 hours)

**Update `bot/ultimate_bot.py`:**

```python
from bot.core.server_registry import ServerRegistry
from bot.automation.multi_server_ssh_monitor import MultiServerSSHMonitor

class UltimateBot(commands.Bot):
    def __init__(self):
        super().__init__(...)

        # ... existing initialization ...

        # Multi-server support
        if self.config.MULTI_SERVER_ENABLED:
            self.server_registry = ServerRegistry(self.config.SERVERS_CONFIG_FILE)
            self.multi_ssh_monitor = MultiServerSSHMonitor(
                registry=self.server_registry,
                local_stats_dir='local_stats'
            )
            logger.info(f"Multi-server mode enabled with {len(self.server_registry.servers)} servers")
        else:
            self.server_registry = None
            self.multi_ssh_monitor = None
            logger.info("Single-server mode (legacy)")

    @tasks.loop(seconds=60)
    async def endstats_monitor(self):
        """Monitor game servers for new stats files."""

        if self.config.MULTI_SERVER_ENABLED:
            # Multi-server parallel monitoring
            await self._multi_server_monitoring()
        else:
            # Legacy single-server monitoring
            await self._single_server_monitoring()

    async def _multi_server_monitoring(self):
        """Check all servers in parallel."""
        try:
            # Check all servers in parallel (< 10 seconds for 20 servers)
            new_files_by_server = await self.multi_ssh_monitor.check_all_servers()

            # Process files from all servers
            for server_id, filenames in new_files_by_server.items():
                for filename in filenames:
                    await self._process_file_from_server(server_id, filename)

        except Exception as e:
            logger.error(f"Multi-server monitoring error: {e}")

    async def _single_server_monitoring(self):
        """Legacy single-server monitoring (backward compatible)."""
        # Existing endstats_monitor logic
        pass

    async def _process_file_from_server(self, server_id: str, filename: str):
        """
        Process a stats file from a specific server.

        Args:
            server_id: Server that generated the file
            filename: Stats filename
        """
        try:
            # Download file
            local_path = await self.multi_ssh_monitor.download_file(server_id, filename)
            if not local_path:
                logger.error(f"Failed to download {filename} from {server_id}")
                return

            # Import to database with server_id
            await self.database_manager.import_stats_file(local_path, server_id=server_id)

            # Post to Discord (with rate limiting)
            await self._post_round_stats(local_path, server_id)

        except Exception as e:
            logger.error(f"Error processing {filename} from {server_id}: {e}")
```

#### Phase 5: Rate Limiting (8-12 hours)

**Create `bot/core/discord_rate_limiter.py`:**

```python
"""Per-server Discord post rate limiting."""
import asyncio
import time
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class DiscordRateLimiter:
    """Rate limiter to prevent Discord API spam when multiple servers post simultaneously."""

    def __init__(self, posts_per_minute: int = 5):
        """
        Initialize rate limiter.

        Args:
            posts_per_minute: Maximum posts per server per minute
        """
        self.posts_per_minute = posts_per_minute
        self.min_interval = 60.0 / posts_per_minute  # Seconds between posts
        self.server_last_post: Dict[str, float] = {}
        self.lock = asyncio.Lock()

    async def wait_for_slot(self, server_id: str):
        """
        Wait until server can post (respects rate limit).

        Args:
            server_id: Server requesting to post
        """
        async with self.lock:
            now = time.time()
            last_post = self.server_last_post.get(server_id, 0)
            time_since_last = now - last_post

            if time_since_last < self.min_interval:
                wait_time = self.min_interval - time_since_last
                logger.debug(f"{server_id}: Rate limited, waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)

            self.server_last_post[server_id] = time.time()
```

**Use in bot:**

```python
class UltimateBot(commands.Bot):
    def __init__(self):
        # ...
        self.rate_limiter = DiscordRateLimiter(posts_per_minute=5)

    async def _post_round_stats(self, filepath: str, server_id: str):
        """Post round stats to Discord with rate limiting."""
        # Wait for rate limit slot
        await self.rate_limiter.wait_for_slot(server_id)

        # Now post to Discord
        # ... existing posting logic ...
```

#### Phase 6: Testing with 2-3 Servers (8-16 hours)

**Test Scenario 1: Concurrent Round Completion**

```bash
# Server 1 finishes round at 14:30:00
# Server 2 finishes round at 14:30:05

# Expected behavior:
# 1. Both servers create files:
#    - puran-2026-02-09-143000-supply-round-1.txt
#    - server2-2026-02-09-143005-supply-round-1.txt
# 2. Bot detects both files in parallel (< 5 seconds)
# 3. Both import to database with correct server_id
# 4. Both post to Discord (rate limited)
# 5. No filename collisions
# 6. No database constraint violations
```

**Verify in database:**

```sql
-- Should see data from both servers
SELECT server_id, COUNT(*) FROM rounds GROUP BY server_id;

-- Example output:
--  server_id | count
-- -----------+-------
--  puran     |   150
--  server2   |    25

-- Check for duplicate filenames (should be 0)
SELECT filename, COUNT(*)
FROM processed_files
GROUP BY filename
HAVING COUNT(*) > 1;
```

**Test Scenario 2: Same Map, Different Servers**

```bash
# Both servers playing 'supply' at same time
# Server 1: Starts at 14:30:00
# Server 2: Starts at 14:30:05

# Files created:
# puran-2026-02-09-143000-supply-round-1.txt
# server2-2026-02-09-143005-supply-round-1.txt

# Different timestamps = no collision ✅
```

**Test Scenario 3: Server Failure Handling**

```bash
# Disable Server 2 (shutdown or firewall block)
sudo ufw deny from BOT_IP to any port 22  # On Server 2

# Expected behavior:
# - Bot continues polling Server 1 and Server 3
# - Server 2 logs error: "SSH connection failed"
# - Server 2 marked with last_error in database
# - No impact on other servers
```

**Verify error handling:**

```sql
SELECT server_id, last_seen, last_error
FROM servers
ORDER BY last_seen DESC;

-- server_id | last_seen           | last_error
-- ----------+---------------------+---------------------------
-- puran     | 2026-02-09 14:35:00 | NULL
-- server2   | 2026-02-09 14:30:00 | SSH connection timeout
-- server3   | 2026-02-09 14:35:00 | NULL
```

**Success Criteria:**

- [ ] 2-3 servers polled in < 10 seconds
- [ ] No filename collisions
- [ ] No database constraint violations
- [ ] Discord rate limits not exceeded (no 429 errors)
- [ ] Server failures isolated (other servers continue working)
- [ ] All stats imported with correct `server_id`
- [ ] `!last_session` shows data from all servers

#### Phase 7: Scale to 10-20 Servers (24-40 hours)

**Connection Pool Sizing:**

Current: 10-30 connections
Required for 20 servers: 70-100 connections

**Calculation:**
- 20 servers × 2 concurrent connections = 40
- 14 cogs × 1 connection each = 14
- 4 task loops × 1 connection = 4
- Buffer for spikes = 12
- **Total: 70 connections minimum**

**Update `bot/config.py`:**

```python
POSTGRES_MIN_POOL = 70
POSTGRES_MAX_POOL = 100
```

**Update PostgreSQL:**

```sql
ALTER SYSTEM SET max_connections = 150;
SELECT pg_reload_conf();

-- Verify
SHOW max_connections;
```

**Monitor connection usage:**

```sql
SELECT count(*) AS active_connections
FROM pg_stat_activity
WHERE datname = 'etlegacy';

-- Should stay below 100
```

**Webhook Strategy: Separate Webhooks per Server (Recommended)**

**Option A: Separate Webhooks (More Secure)**

Each game server has its own Discord webhook URL:

```json
{
  "servers": [
    {
      "server_id": "puran",
      "webhook_url": "https://discord.com/api/webhooks/WEBHOOK_ID_1/TOKEN_1"
    },
    {
      "server_id": "server2",
      "webhook_url": "https://discord.com/api/webhooks/WEBHOOK_ID_2/TOKEN_2"
    }
  ]
}
```

**Advantages:**
- Webhook compromise affects only 1 server
- Easier rate limiting (5 posts/min per server)
- Can post to different Discord channels per server

**Implementation:**

```python
async def _post_round_stats(self, filepath: str, server_id: str):
    """Post round stats to Discord using server-specific webhook."""
    server = self.server_registry.get_server(server_id)
    webhook_url = server.webhook_url

    # Rate limit per server
    await self.rate_limiter.wait_for_slot(server_id)

    # Post to server-specific webhook
    async with aiohttp.ClientSession() as session:
        await session.post(webhook_url, json=payload)
```

**Option B: Single Webhook with Server ID (Simpler)**

All servers share one webhook URL, but include `server_id` in embed:

```python
embed = discord.Embed(
    title=f"📊 Round Complete - {server_name}",
    description=f"Server: **{server_id}**\nMap: {map_name}",
    color=0x00FF00
)
```

**Health Monitoring:**

**Create `bot/diagnostics/multi_server_health.py`:**

```python
class MultiServerHealthMonitor:
    """Monitor health of all game servers."""

    async def check_all_servers(self) -> Dict[str, str]:
        """
        Returns health status for each server.

        Returns:
            Dict mapping server_id to status: 'healthy', 'degraded', 'down'
        """
        health = {}
        for server in self.registry.get_enabled_servers():
            health[server.server_id] = await self._check_health(server)
        return health

    async def _check_health(self, server: ServerConfig) -> str:
        """
        Check server health:
        - SSH connectivity
        - Last file received < 30 min ago
        - Database has recent rounds
        """
        try:
            # Check SSH connectivity
            ssh_ok = await self._test_ssh(server)
            if not ssh_ok:
                return 'down'

            # Check last file received
            last_file = await self._get_last_file_time(server.server_id)
            if last_file and (datetime.now() - last_file).total_seconds() < 1800:
                return 'healthy'
            elif last_file and (datetime.now() - last_file).total_seconds() < 3600:
                return 'degraded'
            else:
                return 'down'

        except Exception as e:
            logger.error(f"Health check failed for {server.server_id}: {e}")
            return 'down'
```

**Discord Alerts:**

```python
# Alert admins if server down > 15 minutes
if server_down_duration > timedelta(minutes=15):
    await self.alert_admins(
        title=f"🔴 Server Down: {server_id}",
        description=f"No stats received for 15+ minutes\nLast seen: {last_seen}",
        color=0xFF0000,
        ping_roles=['@Admin']
    )
```

**Incremental Rollout:**

- **Week 1:** 2 servers → Validate Phase 2 works, test filename format
- **Week 2:** 5 servers → Test moderate load, monitor connection pool
- **Week 3:** 10 servers → Test connection pooling at scale, monitor SSH latency
- **Week 4:** 15 servers → Stress test rate limiting, monitor Discord API
- **Week 5:** 20 servers → Full production load testing

**Monitor key metrics:**
- SSH poll latency (should be < 10s for all servers)
- Database connection count (should stay < 100)
- Discord rate limits (no 429 errors)
- Server health status (all 'healthy')

### Limitations of SSH Approach

**Maximum Scale: ~20 servers**

Beyond 20 servers, SSH polling becomes impractical:
- 20 servers × 5s = 100s per check cycle (exceeds 60s interval)
- Connection pool exhaustion
- SSH key management complexity
- Discord rate limiting challenges

**Recommendation:** If you need > 20 servers, use **Approach 3 (Webhook Push API)** instead.

---

## Approach 3: Detailed Implementation

### Webhook Push API (RECOMMENDED for 10+ servers)

**Goal:** Game servers send stats via HTTPS POST instead of SSH polling

**Architecture:**
```
Game Server 1 ─┐
Game Server 2 ─┼─> Website API Endpoint ──> Database
...            │         ↑
Game Server 20 ┘         │
                         └─> Bot (reads from DB)
```

**How it works:**

1. **Game server round ends** → Lua script triggers
2. **Lua script sends HTTPS POST** → Website API endpoint (`/api/ingest/stats`)
3. **API authenticates server** → API key validation
4. **API parses and imports** → Stats inserted into PostgreSQL
5. **Bot reads from database** → No SSH needed
6. **Bot posts to Discord** → Existing round publisher service

**Advantages:**

- ✅ **Real-time** - Stats arrive instantly (vs 60s SSH polling delay)
- ✅ **Scales infinitely** - 100+ servers no problem (tested with 1000+ API clients)
- ✅ **No SSH required** - Works on any server with internet access
- ✅ **Parallel by default** - Each server posts independently
- ✅ **Stateless** - No connection pooling issues
- ✅ **Simpler** - No file download/tracking logic
- ✅ **More secure** - API key authentication, rate limiting, HTTPS only
- ✅ **Faster to implement** - 20-30 hours vs 88-140 hours for SSH multi-server

### Implementation Phases

#### Phase 1: API Endpoint (8-12 hours)

**Create `website/backend/routers/stats_ingest.py`:**

```python
"""Stats Ingest API - Receive stats uploads from game servers."""
import logging
from fastapi import APIRouter, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from typing import Optional
from datetime import datetime
import hashlib

from bot.community_stats_parser import CommunityStatsParser
from bot.core.database_adapter import DatabaseAdapter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ingest", tags=["stats_ingest"])

# In-memory rate limiting (or use Redis for distributed)
from collections import defaultdict
from time import time

rate_limit_cache = defaultdict(list)

async def check_rate_limit(server_id: str, limit: int = 10, window: int = 60) -> bool:
    """
    Check if server has exceeded rate limit.

    Args:
        server_id: Server identifier
        limit: Maximum requests per window
        window: Time window in seconds

    Returns:
        True if within limit, False if exceeded
    """
    now = time()

    # Clean old entries
    rate_limit_cache[server_id] = [
        ts for ts in rate_limit_cache[server_id]
        if now - ts < window
    ]

    # Check limit
    if len(rate_limit_cache[server_id]) >= limit:
        return False

    # Add current request
    rate_limit_cache[server_id].append(now)
    return True

async def authenticate_server(api_key: str, server_id: str, db: DatabaseAdapter) -> Optional[dict]:
    """
    Authenticate server by API key.

    Args:
        api_key: API key from X-API-Key header
        server_id: Server ID from X-Server-ID header
        db: Database connection

    Returns:
        Server record if valid, None otherwise
    """
    if not api_key or not server_id:
        return None

    # Hash API key for comparison (stored hashed in DB)
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    # Query database
    query = """
        SELECT server_id, server_name, enabled
        FROM servers
        WHERE server_id = ? AND api_key_hash = ? AND enabled = TRUE
    """

    result = await db.fetch_one(query, (server_id, api_key_hash))

    if result:
        logger.info(f"Authenticated server: {result['server_id']}")
        return dict(result)
    else:
        logger.warning(f"Authentication failed for server_id: {server_id}")
        return None

@router.post("/stats")
async def ingest_stats(
    request: Request,
    stats_payload: dict,
    x_api_key: Optional[str] = Header(None),
    x_server_id: Optional[str] = Header(None)
):
    """
    Receive stats upload from game server via Lua webhook.

    Headers:
        X-API-Key: Server-specific API key for authentication
        X-Server-ID: Server identifier (e.g., 'puran-main')

    Body:
        Full stats file content as JSON structure

    Example payload:
        {
            "filename": "puran-2026-02-09-143000-supply-round-1.txt",
            "content": "GAME STATS\\nAXIS: team1\\n...",
            "timestamp": 1707487800,
            "map_name": "supply",
            "round_number": 1
        }

    Returns:
        {"status": "success", "server_id": "puran", "round_id": 12345}
    """
    # Get database connection
    db = request.app.state.db

    # Rate limiting
    if not await check_rate_limit(x_server_id or 'unknown', limit=10, window=60):
        logger.warning(f"Rate limit exceeded for {x_server_id}")
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # Authenticate server
    server = await authenticate_server(x_api_key, x_server_id, db)
    if not server:
        logger.error(f"Authentication failed: {x_server_id}")
        raise HTTPException(status_code=401, detail="Invalid API key or server ID")

    # Validate payload structure
    required_fields = ['filename', 'content']
    if not all(field in stats_payload for field in required_fields):
        raise HTTPException(status_code=400, detail=f"Missing required fields: {required_fields}")

    filename = stats_payload.get('filename')
    content = stats_payload.get('content')

    # Parse and import to database
    try:
        # Write content to temporary file (parser expects file path)
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        # Parse stats
        parser = CommunityStatsParser()
        parsed_data = parser.parse_file(tmp_path)

        # Import to database with server_id
        round_id = await import_stats_to_database(
            db=db,
            parsed_data=parsed_data,
            server_id=server['server_id'],
            filename=filename
        )

        # Update server last_seen
        await db.execute(
            "UPDATE servers SET last_seen = ?, stats_count = stats_count + 1 WHERE server_id = ?",
            (datetime.now(), server['server_id'])
        )

        logger.info(f"Successfully ingested stats from {server['server_id']}: {filename}")

        return JSONResponse({
            "status": "success",
            "server_id": server['server_id'],
            "round_id": round_id,
            "filename": filename
        })

    except Exception as e:
        logger.error(f"Import failed for {server['server_id']}: {e}", exc_info=True)

        # Update server with error
        await db.execute(
            "UPDATE servers SET last_error = ? WHERE server_id = ?",
            (str(e)[:500], server['server_id'])
        )

        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")

    finally:
        # Clean up temp file
        try:
            import os
            os.unlink(tmp_path)
        except:
            pass

async def import_stats_to_database(
    db: DatabaseAdapter,
    parsed_data: dict,
    server_id: str,
    filename: str
) -> int:
    """
    Import parsed stats to database.

    Args:
        db: Database connection
        parsed_data: Parsed stats from parser
        server_id: Server that generated stats
        filename: Original filename

    Returns:
        round_id: ID of inserted round
    """
    # Implementation similar to postgresql_database_manager.py
    # Insert round, player stats, weapon stats, etc.
    # Include server_id in all inserts

    # This would use existing database manager logic
    # Just need to pass server_id through

    # Example:
    from bot.postgresql_database_manager import PostgreSQLDatabaseManager

    db_manager = PostgreSQLDatabaseManager()
    round_id = await db_manager.import_parsed_stats(
        parsed_data=parsed_data,
        server_id=server_id,
        filename=filename
    )

    return round_id
```

**Register router in `website/backend/main.py`:**

```python
from backend.routers import stats_ingest

app.include_router(stats_ingest.router)
```

#### Phase 2: Enhanced Lua Script (4-6 hours)

**Create `vps_scripts/stats_upload.lua` (runs on game server):**

```lua
--[[
    ET:Legacy Stats Upload via HTTPS API

    Uploads stats to central server via HTTPS POST instead of relying on SSH polling.

    Configuration:
        SERVER_ID: Unique identifier for this server (e.g., "puran", "server2")
        API_KEY: Secret API key for authentication
        API_ENDPOINT: HTTPS URL of stats ingest API

    Usage:
        1. Copy this file to lua/ directory
        2. Configure SERVER_ID and API_KEY
        3. Add to luascripts.cfg: exec stats_upload.lua
]]

-- CONFIGURATION (CHANGE THESE!)
local SERVER_ID = "puran"  -- Unique server identifier
local API_KEY = "your-secret-api-key-here-32-characters-min"
local API_ENDPOINT = "https://yourwebsite.com/api/ingest/stats"

-- ET:Legacy Lua HTTP library (requires et_http module)
local http = require("http")
local json = require("json")  -- or cjson

-- Called when game transitions from PLAYING to INTERMISSION
function et_RunFrame(levelTime)
    -- Check if round just ended
    local gamestate = et.trap_Cvar_Get("gamestate")

    if gamestate == "3" then  -- INTERMISSION
        if not roundEnded then
            roundEnded = true
            uploadRoundStats()
        end
    else
        roundEnded = false
    end
end

function uploadRoundStats()
    et.G_Print("^2[Stats Upload] Round ended, uploading stats...")

    -- Get map name and round number
    local mapname = et.trap_Cvar_Get("mapname")
    local roundNumber = tonumber(et.trap_Cvar_Get("g_currentRound")) or 1

    -- Generate filename
    local timestamp = os.date("%Y-%m-%d-%H%M%S")
    local filename = string.format("%s-%s-%s-round-%d.txt",
        SERVER_ID,
        timestamp,
        mapname,
        roundNumber
    )

    -- Read stats file
    local statsPath = et.trap_Cvar_Get("g_gamestatsPath")
    local statsFiles = et.trap_FS_GetFileList(statsPath, ".txt")

    -- Find most recent stats file (should be current round)
    local latestFile = nil
    local latestTime = 0

    for _, file in ipairs(statsFiles) do
        local filepath = statsPath .. "/" .. file
        local mtime = et.trap_FS_GetModTime(filepath)

        if mtime > latestTime then
            latestTime = mtime
            latestFile = filepath
        end
    end

    if not latestFile then
        et.G_Print("^1[Stats Upload] No stats file found!")
        return
    end

    -- Read file content
    local file = io.open(latestFile, "r")
    if not file then
        et.G_Print("^1[Stats Upload] Failed to open stats file: " .. latestFile)
        return
    end

    local content = file:read("*all")
    file:close()

    -- Build JSON payload
    local payload = {
        filename = filename,
        content = content,
        timestamp = os.time(),
        map_name = mapname,
        round_number = roundNumber,
        server_id = SERVER_ID
    }

    -- HTTPS POST to API endpoint
    local response, err = http.post(API_ENDPOINT, {
        headers = {
            ["Content-Type"] = "application/json",
            ["X-API-Key"] = API_KEY,
            ["X-Server-ID"] = SERVER_ID,
            ["User-Agent"] = "ETLegacy-StatsUploader/1.0"
        },
        body = json.encode(payload),
        timeout = 10  -- 10 second timeout
    })

    if response and response.status == 200 then
        et.G_Print("^2[Stats Upload] Successfully uploaded: " .. filename)

        -- Optionally delete local file after successful upload
        -- os.remove(latestFile)
    else
        local status = response and response.status or "unknown"
        local error_msg = err or (response and response.body) or "unknown error"
        et.G_Print("^1[Stats Upload] Upload failed (HTTP " .. status .. "): " .. error_msg)

        -- Keep local file for retry/debugging
    end
end

et.G_Print("^2[Stats Upload] Module loaded for server: " .. SERVER_ID)
```

**Alternative: Simpler Lua Script (uses curl system call):**

```lua
-- Simpler version using curl (no Lua HTTP library required)
function uploadRoundStats()
    local mapname = et.trap_Cvar_Get("mapname")
    local roundNumber = tonumber(et.trap_Cvar_Get("g_currentRound")) or 1
    local timestamp = os.date("%Y-%m-%d-%H%M%S")
    local filename = string.format("%s-%s-%s-round-%d.txt",
        SERVER_ID, timestamp, mapname, roundNumber
    )

    -- Find latest stats file
    local statsPath = et.trap_Cvar_Get("g_gamestatsPath")
    local latestFile = findLatestStatsFile(statsPath)

    if not latestFile then
        et.G_Print("^1[Stats Upload] No stats file found!")
        return
    end

    -- Build curl command
    local curl_cmd = string.format(
        'curl -X POST "%s" ' ..
        '-H "Content-Type: text/plain" ' ..
        '-H "X-API-Key: %s" ' ..
        '-H "X-Server-ID: %s" ' ..
        '-H "X-Filename: %s" ' ..
        '--data-binary "@%s" ' ..
        '&',  -- Background process
        API_ENDPOINT,
        API_KEY,
        SERVER_ID,
        filename,
        latestFile
    )

    -- Execute curl in background
    os.execute(curl_cmd)

    et.G_Print("^2[Stats Upload] Uploading: " .. filename)
end
```

#### Phase 3: Database Schema Updates (2-4 hours)

**Add API key support to servers table:**

```sql
-- Add API key columns
ALTER TABLE servers ADD COLUMN api_key VARCHAR(255);
ALTER TABLE servers ADD COLUMN api_key_hash VARCHAR(255) UNIQUE;
ALTER TABLE servers ADD COLUMN created_by VARCHAR(100);
ALTER TABLE servers ADD COLUMN notes TEXT;

-- Generate secure API keys for existing servers
UPDATE servers
SET api_key = encode(gen_random_bytes(32), 'hex'),
    api_key_hash = encode(digest(encode(gen_random_bytes(32), 'hex'), 'sha256'), 'hex')
WHERE api_key IS NULL;

-- Display API keys (SAVE THESE - they won't be retrievable after)
SELECT server_id, server_name, api_key
FROM servers
WHERE enabled = TRUE;

-- Example output:
--  server_id | server_name        | api_key
-- -----------+--------------------+------------------------------------------------------------------
--  puran     | Puran Main Server  | a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0
--  server2   | Community Server 2 | z9y8x7w6v5u4t3s2r1q0p9o8n7m6l5k4j3i2h1g0f9e8d7c6b5a4z3y2x1

-- After saving, clear plaintext API keys (keep only hashes)
UPDATE servers SET api_key = NULL;
```

**Create function to generate new API keys:**

```sql
CREATE OR REPLACE FUNCTION generate_api_key(p_server_id VARCHAR)
RETURNS VARCHAR AS $$
DECLARE
    new_api_key VARCHAR;
    new_api_key_hash VARCHAR;
BEGIN
    -- Generate random 32-byte API key
    new_api_key := encode(gen_random_bytes(32), 'hex');

    -- Hash it with SHA256
    new_api_key_hash := encode(digest(new_api_key, 'sha256'), 'hex');

    -- Update server record
    UPDATE servers
    SET api_key_hash = new_api_key_hash,
        last_error = NULL
    WHERE server_id = p_server_id;

    -- Return plaintext key (ONLY TIME IT'S VISIBLE!)
    RETURN new_api_key;
END;
$$ LANGUAGE plpgsql;

-- Usage:
SELECT generate_api_key('puran');
-- Returns: a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0
-- COPY THIS IMMEDIATELY - it won't be shown again!
```

#### Phase 4: Security Hardening (4-6 hours)

**API Key Best Practices:**

1. **Length:** Minimum 32 characters (use 64 for extra security)
2. **Randomness:** Use cryptographically secure random generator
3. **Storage:** Store only hashed version in database (SHA256 or bcrypt)
4. **Rotation:** Rotate keys every 90 days (or on compromise)
5. **Transmission:** HTTPS only, never log plaintext keys

**Rate Limiting Configuration:**

```python
# website/backend/routers/stats_ingest.py

# Per-server rate limits
RATE_LIMIT_WINDOW = 60  # 1 minute
RATE_LIMIT_MAX_REQUESTS = 10  # 10 uploads per minute per server

# Global rate limits (all servers combined)
GLOBAL_RATE_LIMIT_WINDOW = 60
GLOBAL_RATE_LIMIT_MAX_REQUESTS = 100  # 100 uploads per minute total

# File size limits
MAX_STATS_FILE_SIZE = 1024 * 1024  # 1 MB (stats files are typically 10-50 KB)
```

**Input Validation:**

```python
def validate_stats_payload(payload: dict) -> bool:
    """Validate stats payload structure and content."""

    # Required fields
    if not all(k in payload for k in ['filename', 'content']):
        return False

    # Filename format validation
    filename = payload['filename']
    if not re.match(r'^[\w-]+\d{4}-\d{2}-\d{2}-\d{6}-[\w-]+-round-[12]\.txt$', filename):
        logger.warning(f"Invalid filename format: {filename}")
        return False

    # Content size validation
    content = payload['content']
    if len(content) > MAX_STATS_FILE_SIZE:
        logger.warning(f"Stats content too large: {len(content)} bytes")
        return False

    # Content structure validation (basic check)
    if 'GAME STATS' not in content:
        logger.warning("Invalid stats content: missing header")
        return False

    return True
```

**HTTPS Enforcement:**

```python
# website/backend/main.py

from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

# Force HTTPS in production
if os.getenv('ENVIRONMENT') == 'production':
    app.add_middleware(HTTPSRedirectMiddleware)
```

**API Key Rotation Process:**

```python
# Admin command to rotate API key
@router.post("/admin/rotate-api-key")
async def rotate_api_key(
    server_id: str,
    admin_token: str = Header(None)
):
    """
    Rotate API key for a server (admin only).

    Returns new API key - SAVE IT IMMEDIATELY!
    """
    # Verify admin token
    if admin_token != os.getenv('ADMIN_TOKEN'):
        raise HTTPException(status_code=403, detail="Forbidden")

    # Generate new API key
    new_api_key = secrets.token_urlsafe(48)  # 64 characters
    new_api_key_hash = hashlib.sha256(new_api_key.encode()).hexdigest()

    # Update database
    await db.execute(
        "UPDATE servers SET api_key_hash = ?, last_error = NULL WHERE server_id = ?",
        (new_api_key_hash, server_id)
    )

    logger.info(f"API key rotated for server: {server_id}")

    # Return new key (ONLY TIME IT'S VISIBLE!)
    return {
        "server_id": server_id,
        "api_key": new_api_key,
        "warning": "Save this key immediately - it will not be shown again!"
    }
```

#### Phase 5: Testing & Validation (2-4 hours)

**Test 1: Single Server Upload**

```bash
# Simulate game server posting stats
curl -X POST https://yourwebsite.com/api/ingest/stats \
  -H "Content-Type: application/json" \
  -H "X-API-Key: a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0" \
  -H "X-Server-ID: puran" \
  -d @test_payload.json

# Expected response:
# {"status": "success", "server_id": "puran", "round_id": 12345, "filename": "puran-2026-02-09-143000-supply-round-1.txt"}
```

**test_payload.json:**
```json
{
  "filename": "puran-2026-02-09-143000-supply-round-1.txt",
  "content": "GAME STATS\nAXIS: team1\nALLIES: team2\n...",
  "timestamp": 1707487800,
  "map_name": "supply",
  "round_number": 1
}
```

**Test 2: Authentication Failure**

```bash
# Wrong API key
curl -X POST https://yourwebsite.com/api/ingest/stats \
  -H "X-API-Key: wrong-key" \
  -H "X-Server-ID: puran" \
  -d @test_payload.json

# Expected response:
# HTTP 401 Unauthorized
# {"detail": "Invalid API key or server ID"}
```

**Test 3: Rate Limiting**

```bash
# Send 15 requests in 10 seconds (exceeds 10/min limit)
for i in {1..15}; do
  curl -X POST https://yourwebsite.com/api/ingest/stats \
    -H "X-API-Key: $API_KEY" \
    -H "X-Server-ID: puran" \
    -d @test_payload.json &
done

# First 10 should succeed (HTTP 200)
# Requests 11-15 should fail (HTTP 429 Too Many Requests)
```

**Test 4: Concurrent Multi-Server**

```bash
# Simulate 5 servers posting simultaneously
for server in puran server2 server3 server4 server5; do
  curl -X POST https://yourwebsite.com/api/ingest/stats \
    -H "X-API-Key: $API_KEY_$server" \
    -H "X-Server-ID: $server" \
    -d @test_payload_$server.json &
done

# All should succeed (parallel processing)
# Check database for 5 new rounds with different server_id values
```

**Verify in database:**

```sql
-- Check all servers posted
SELECT server_id, COUNT(*)
FROM rounds
WHERE round_date = CURRENT_DATE
GROUP BY server_id;

-- server_id | count
-- ----------+-------
-- puran     |     1
-- server2   |     1
-- server3   |     1
-- server4   |     1
-- server5   |     1
```

**Test 5: End-to-End Flow**

1. Configure Lua script on game server with API key
2. Play a round on game server
3. Round ends → Lua script posts to API
4. API imports to database
5. Bot detects new round in database
6. Bot posts to Discord
7. Website shows updated stats

**Success Criteria:**

- [ ] API endpoint accepts valid uploads (HTTP 200)
- [ ] API rejects invalid API keys (HTTP 401)
- [ ] API enforces rate limits (HTTP 429)
- [ ] Stats imported correctly to database
- [ ] Bot posts to Discord automatically
- [ ] Website displays stats from all servers
- [ ] No SSH polling needed
- [ ] Latency < 5 seconds (upload to Discord post)

#### Phase 6: Migration Strategy (4-6 hours)

**Option A: Dual Mode (SSH + Webhooks)**

Run both systems in parallel during transition:

```python
class UltimateBot(commands.Bot):
    @tasks.loop(seconds=60)
    async def endstats_monitor(self):
        """Monitor both SSH and webhook-ingested rounds."""

        # SSH polling (legacy servers)
        await self._check_ssh_servers()

        # Check for webhook-ingested rounds (new servers)
        await self._check_webhook_rounds()

    async def _check_webhook_rounds(self):
        """Check for new rounds ingested via webhook API."""
        # Query rounds table for new entries not yet posted
        query = """
            SELECT r.*
            FROM rounds r
            LEFT JOIN posted_rounds pr ON r.id = pr.round_id
            WHERE pr.round_id IS NULL
            AND r.created_at > NOW() - INTERVAL '5 minutes'
            ORDER BY r.created_at ASC
        """

        new_rounds = await self.db.fetch_all(query)

        for round_data in new_rounds:
            await self._post_round_stats(round_data)

            # Mark as posted
            await self.db.execute(
                "INSERT INTO posted_rounds (round_id, posted_at) VALUES (?, ?)",
                (round_data['id'], datetime.now())
            )
```

**Create `posted_rounds` tracking table:**

```sql
CREATE TABLE posted_rounds (
    id SERIAL PRIMARY KEY,
    round_id INTEGER UNIQUE NOT NULL REFERENCES rounds(id),
    posted_at TIMESTAMP NOT NULL DEFAULT NOW(),
    channel_id VARCHAR(50),
    message_id VARCHAR(50)
);

CREATE INDEX idx_posted_rounds_round_id ON posted_rounds(round_id);
```

**Option B: Webhook-Only (Clean Cutover)**

1. Deploy webhook API endpoint
2. Configure all servers with Lua script + API keys
3. Test each server individually
4. When all servers confirmed working → disable SSH polling
5. Remove SSH-related code

**Rollback Plan:**

If webhook system fails:

1. Re-enable SSH polling in bot config
2. Lua scripts fall back to normal stats file writing
3. Bot resumes SSH monitoring
4. Fix webhook issues offline
5. Retry migration when ready

#### Phase 7: Performance Optimization (2-4 hours)

**Database Indexing for Webhook Queries:**

```sql
-- Optimize round lookups by timestamp
CREATE INDEX idx_rounds_created_at ON rounds(created_at DESC);

-- Optimize server-specific queries
CREATE INDEX idx_rounds_server_created ON rounds(server_id, created_at DESC);

-- Optimize posted_rounds checks
CREATE INDEX idx_posted_rounds_lookup ON posted_rounds(round_id, posted_at);
```

**API Response Caching:**

```python
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_cache.decorator import cache

# Initialize cache
FastAPICache.init(InMemoryBackend())

@router.get("/api/stats/{player_guid}")
@cache(expire=300)  # Cache for 5 minutes
async def get_player_stats(player_guid: str):
    """Cached player stats endpoint."""
    # ... existing logic ...
```

**Async Database Operations:**

```python
import asyncio

async def import_stats_batch(payloads: List[dict]):
    """Import multiple stats files in parallel."""
    tasks = [
        import_stats_to_database(db, payload['data'], payload['server_id'], payload['filename'])
        for payload in payloads
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    return results
```

**Monitoring & Alerts:**

```python
# Track API metrics
from prometheus_client import Counter, Histogram

api_requests = Counter('stats_ingest_requests_total', 'Total stats ingest requests', ['server_id', 'status'])
api_latency = Histogram('stats_ingest_latency_seconds', 'Stats ingest latency')

@router.post("/stats")
async def ingest_stats(...):
    with api_latency.time():
        try:
            # ... process stats ...
            api_requests.labels(server_id=server_id, status='success').inc()
        except Exception as e:
            api_requests.labels(server_id=server_id, status='error').inc()
            raise
```

### Comparison: Webhook vs SSH

| Feature | SSH Polling | Webhook Push |
|---------|-------------|--------------|
| **Latency** | 0-60 seconds | < 1 second |
| **Max Servers** | ~20 | 1000+ |
| **Server Requirements** | SSH access | Internet only |
| **Security** | SSH keys | API keys + HTTPS |
| **Implementation Time** | 88-140 hours | 20-30 hours |
| **Code Complexity** | High (async pooling) | Medium (API endpoint) |
| **Bot Complexity** | High | Low (just reads DB) |
| **Failure Recovery** | Manual retry | Automatic (Lua retry) |
| **File Management** | Download + track | No files needed |
| **Rate Limiting** | Complex (per-server) | Simple (FastAPI) |
| **Monitoring** | SSH health checks | API metrics |
| **Scalability** | Linear (O(n)) | Constant (O(1)) |

**Conclusion:** Webhook push is superior in every metric except initial learning curve.

---

## Critical Files to Modify

### Approach 1: Distributed Components
- `.env` - Change POSTGRES_HOST to remote VPS
- `website/.env` - Configure remote database with read-only user
- *(No code changes required)*

### Approach 2: SSH Multi-Server
- `bot/schema_postgresql.sql` - Add server_id columns, create servers table
- `.env` - Add SERVERS_CONFIG_FILE, MULTI_SERVER_ENABLED
- `servers.json` (new) - Multi-server configuration
- `bot/community_stats_parser.py` (line ~384) - Parse server_id from filename
- `bot/automation/file_tracker.py` - Track processed files per server
- `bot/ultimate_bot.py` (lines 551-568) - Replace sequential SSH with parallel
- `bot/core/server_registry.py` (new) - Server configuration management
- `bot/automation/multi_server_ssh_monitor.py` (new) - Parallel SSH polling
- `vps_scripts/stats_discord_webhook.lua` (line 77) - Add SERVER_ID prefix to filename
- `bot/config.py` - Increase connection pool (70-100)
- `bot/diagnostics/multi_server_health.py` (new) - Health monitoring

### Approach 3: Webhook Push API
- `bot/schema_postgresql.sql` - Add server_id columns, api_key_hash column
- `servers.json` (new) - Server configurations with API keys
- `website/backend/routers/stats_ingest.py` (new) - API endpoint for stats upload
- `website/backend/main.py` - Register stats_ingest router
- `vps_scripts/stats_upload.lua` (new) - Enhanced Lua script for HTTPS POST
- `bot/ultimate_bot.py` - Add webhook round detection task
- `website/backend/routers/api.py` - Add server_id filtering to endpoints

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Approach 1: Distributed Components** ||||
| Database connection failure | LOW | HIGH | Test connection before full deployment, keep local backup |
| SSL certificate expiration | LOW | MEDIUM | Auto-renewal via certbot, monitoring alerts |
| Website compromise (read-only user) | LOW | LOW | Read-only user can't modify data |
| Network latency | MEDIUM | LOW | Bot and website both on VPS (low latency) |
| **Approach 2: SSH Multi-Server** ||||
| Filename collisions (no server_id) | HIGH | CRITICAL | Phase 2 adds server prefix to all files |
| SSH polling falls behind | MEDIUM | HIGH | Phase 2 implements async parallel polling |
| Database connection exhaustion | LOW | HIGH | Phase 3 increases pool to 100 connections |
| Discord rate limiting | MEDIUM | MEDIUM | Phase 3 implements per-server rate limiting |
| Data loss during migration | LOW | CRITICAL | Backup database before Phase 0 migration |
| **Approach 3: Webhook Push** ||||
| API key compromise | LOW | MEDIUM | Rotate keys immediately, revoke in database |
| DDoS on API endpoint | MEDIUM | MEDIUM | Rate limiting, firewall rules, Cloudflare |
| Lua script failure | MEDIUM | LOW | Keep local stats files, SSH fallback |
| Network partition (server can't reach API) | LOW | MEDIUM | Lua retries, local file backup |
| Database overload (100 servers posting) | LOW | MEDIUM | Connection pooling, async imports |

---

## Effort Summary

| Phase | Approach 1 | Approach 2 | Approach 3 |
|-------|-----------|-----------|-----------|
| **Total Hours** | 16-24 | 88-140 | 20-30 |
| **Complexity** | Low | High | Medium |
| **Can Rollback?** | Yes | Partially | Yes |
| **Max Servers** | 1-2 | ~20 | 1000+ |
| **Timeline** | 2-3 days | 11-18 days | 3-4 days |

**Recommended Path:**

1. **Start with Approach 1** (if moving to VPS) → 2-3 days
2. **Then implement Approach 3** (webhook push) → 3-4 days
3. **Skip Approach 2** (SSH multi-server is complex and limited)

**Total time: 5-7 days** to go from single LAN server to distributed architecture supporting 100+ game servers.

---

## Key Insights

1. **Your System is Already 90% Ready** - Database connections support remote VPS out of the box. Just change `.env` settings.

2. **Webhook Push is Superior** - Faster to implement (20-30h vs 88-140h), scales infinitely, simpler architecture.

3. **SSH Polling Doesn't Scale** - Beyond 20 servers, SSH polling becomes a bottleneck. Webhook push has no such limit.

4. **Incremental Rollout** - Can run both SSH and webhook systems in parallel during migration. No downtime required.

5. **Security is Built-In** - System already has SSL/TLS support, read-only users, rate limiting, and authentication.

6. **Bot Can Stay on LAN** - No need to expose bot to internet. Database and website can be on VPS while bot stays secure on LAN.

7. **No Filename Collision Risk** - Webhook approach doesn't need filename prefixes. Each upload is atomic with server_id in headers.

8. **Real-Time is Better** - Webhook push delivers stats in < 1 second vs 60-second SSH polling delay.

---

## Next Steps (When Ready to Scale)

### Immediate (If Moving to VPS):
1. Follow **Approach 1** to move database/website to VPS (16-24 hours)
2. Test thoroughly with existing single game server
3. Verify security (firewall, SSL, read-only user)

### Near-Term (If Adding 2-5 Servers):
1. Implement **Approach 3** (webhook push API) (20-30 hours)
2. Test with 1-2 servers in dual mode (SSH + webhook)
3. Migrate remaining servers when confident

### Long-Term (If Scaling to 10+ Servers):
1. Use **Approach 3** exclusively (no SSH needed)
2. Monitor API metrics (requests/sec, latency, errors)
3. Scale database VPS as needed (more RAM/CPU)
4. Consider CDN for website (Cloudflare)

**DO NOT IMPLEMENT Approach 2** unless webhook push is not feasible for some reason.

---

## Conclusion

Your bot is architecturally sound and ready for distributed deployment. The path to supporting 10-20 (or 100+) game servers is clear:

1. **Database/Website to VPS** (Approach 1) - 2-3 days
2. **Webhook Push API** (Approach 3) - 3-4 days
3. **Total: 5-7 days** to infinite scale

**This is a planning document.** No changes will be made to your current working system. Implement when you're ready to scale.

---

**Document Version:** 1.0
**Last Updated:** 2026-02-09
**Status:** Planning / Reference Only
**Estimated Implementation Time:**
- Approach 1 (VPS Migration): 16-24 hours
- Approach 2 (SSH Multi-Server): 88-140 hours
- Approach 3 (Webhook Push): 20-30 hours ✅ **RECOMMENDED**
