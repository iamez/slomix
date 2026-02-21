# Slomix VM Migration Report

**Date:** February 19-20, 2026
**Author:** Generated from migration session logs
**VM:** Debian 13.3 (Trixie) on Proxmox — `192.168.64.159`
**Domain:** `https://www.slomix.fyi` (Cloudflare Tunnel)

---

## Table of Contents

1. [Objective](#1-objective)
2. [Environment Overview](#2-environment-overview)
3. [Phase 1: Fresh Debian Install & Base Setup](#3-phase-1-fresh-debian-install--base-setup)
4. [Phase 2: Code Deployment — GitHub Clone Mismatch](#4-phase-2-code-deployment--github-clone-mismatch)
5. [Phase 3: Samba Code Sync (tar approach)](#5-phase-3-samba-code-sync-tar-approach)
6. [Phase 4: Service Configuration Issues](#6-phase-4-service-configuration-issues)
7. [Phase 5: Database Verification](#7-phase-5-database-verification)
8. [Phase 6: Discord OAuth & Authentication](#8-phase-6-discord-oauth--authentication)
9. [Phase 7: HTTPS / Firefox Debugging](#9-phase-7-https--firefox-debugging)
10. [Phase 8: Final Fix — Relative URLs](#10-phase-8-final-fix--relative-urls)
11. [Current State](#11-current-state)
12. [Remaining Items](#12-remaining-items)
13. [Appendix: Key Files & Credentials Reference](#13-appendix-key-files--credentials-reference)

---

## 1. Objective

Migrate the Slomix ET:Legacy Discord bot and website from the Samba development server (`192.168.64.116`) to a new production VM (`192.168.64.159`) running Debian 13.3. The goal was a clean, hardened production deployment accessible via `https://www.slomix.fyi` through Cloudflare Tunnel.

---

## 2. Environment Overview

| Component | Detail |
|-----------|--------|
| **VM Host** | Proxmox, Debian 13.3 (Trixie) |
| **VM IP** | `192.168.64.159` |
| **Samba (source)** | `192.168.64.116`, user `samba`, project at `/home/samba/share/slomix_discord` |
| **Domain** | `www.slomix.fyi` |
| **DNS** | Cloudflare — `www` CNAME to Cloudflare Tunnel, apex `slomix.fyi` has no A record |
| **Tunnel** | Cloudflare Tunnel routes HTTPS to `http://localhost:7000` on VM |
| **Database** | PostgreSQL 14, database `etlegacy`, user `etlegacy_user` on localhost:5432 |
| **Python** | 3.13.5 |
| **Bot service** | `slomix-bot` — runs `python3 -m bot.ultimate_bot` from `/opt/slomix` |
| **Web service** | `slomix-web` — runs `uvicorn backend.main:app --host 127.0.0.1 --port 7000 --workers 2` from `/opt/slomix/website` |
| **SSH tool** | `python tools/vm_ssh.py --sudo "cmd"` (key-based auth from dev machine) |

---

## 3. Phase 1: Fresh Debian Install & Base Setup

The VM was provisioned on Proxmox with Debian 13.3. Initial setup included:

- System packages installed (Python 3.13, PostgreSQL, build tools)
- Two systemd services created: `slomix-bot` and `slomix-web`
- Service users created: `slomix_bot` and `slomix_web` (non-login, restricted)
- Project directory: `/opt/slomix/`
- Two Python virtual environments: `/opt/slomix/venv-bot` and `/opt/slomix/venv-web`
- Cloudflare Tunnel configured to route `www.slomix.fyi` HTTPS to `http://localhost:7000`
- SSH hardening applied in `/etc/ssh/sshd_config.d/90-hardening.conf`

**No issues in this phase.**

---

## 4. Phase 2: Code Deployment — GitHub Clone Mismatch

### Problem

The initial deployment used `git clone` from the GitHub repository. However, the GitHub version was significantly behind the Samba development version:

- **Missing routers:** `planning.py`, `uploads.py` were absent from the cloned version
- **Missing features:** Several cogs, core modules, and JS files didn't match
- **Website looked different** from the working Samba version

### Root Cause

The GitHub repository (`main` branch) hadn't been updated with recent development work. The active development branch on Samba (`feat/availability-multichannel-notifications`) contained months of additional work including new website routers, JS modules, and bot cogs.

### Decision

Rather than fixing the GitHub branch, we decided to **sync code directly from Samba to VM** using a tar-based approach, bypassing GitHub entirely for this deployment.

---

## 5. Phase 3: Samba Code Sync (tar approach)

### Initial Attempt: File-by-File Sync

The existing `tools/sync_from_samba.py` (438 lines) copied files individually via SSH, which was:
- Extremely slow (thousands of individual SCP operations)
- Fragile (permission errors, encoding issues per file)
- Incomplete (missed nested directories)

### Solution: Tar-Based Rewrite

Rewrote the `sync_code()` function in `sync_from_samba.py` to use a tar.gz approach:

1. **Create tar.gz on Samba** — tars specific runtime directories
2. **Download to Windows** (dev machine) via SFTP
3. **Upload to VM** via SFTP
4. **Extract on VM** into `/opt/slomix/`
5. **Fix ownership** (`chown -R`)
6. **Restart services**

**Synced directories:**
```
bot, website/backend, website/js, website/migrations, website/assets,
tools, proximity, greatshot, docs
```

**Result:** 12.5 MB tar.gz, synced in ~30 seconds. Both services restarted to `active`.

### Unicode Encoding Bug

The rewritten script contained Unicode symbols (→, ✅, ❌, ⚠️, ─) in print statements and comments. Windows PowerShell uses `cp1252` encoding which can't represent these characters, causing `UnicodeEncodeError` on every run.

**Fix:** Replaced all Unicode symbols with ASCII equivalents (`->`, `[OK]`, `[FAIL]`, `[WARN]`, `-`).

---

## 6. Phase 4: Service Configuration Issues

Multiple configuration problems were discovered and fixed sequentially:

### Issue 1: SSH Lockout (Password Authentication Disabled)

**Symptom:** Could not SSH to VM with password after hardening.
**Cause:** `/etc/ssh/sshd_config.d/90-hardening.conf` had `PasswordAuthentication no`.
**Fix:** Changed to `PasswordAuthentication yes`, reloaded sshd.

### Issue 2: Web Service Crash — Read-Only Log Path

**Symptom:** `slomix-web` service crashed on startup after code sync.
**Cause:** New Samba code writes to `/opt/slomix/logs/web.log`, but systemd's `ReadWritePaths` didn't include this directory.
**Fix:**
- Added `/opt/slomix/logs` to `ReadWritePaths` in `slomix-web.service`
- Created directory: `mkdir -p /opt/slomix/logs`
- Fixed ownership: `chown slomix_web:slomix /opt/slomix/logs`
- Fixed permissions: `chmod 775 /opt/slomix/logs`

### Issue 3: Wrong `.env` Path in Service File

**Symptom:** Website returned no data — all stats showed as `--`.
**Cause:** Service file had `EnvironmentFile=/opt/slomix/website/.env` but the actual `.env` was at `/opt/slomix/.env`.
**Fix:** Changed to `EnvironmentFile=/opt/slomix/.env` in the systemd unit file.

**This was the primary "no data" bug** — without the correct `.env`, the web service had no database credentials.

### Issue 4: Missing CORS Configuration

**Symptom:** After fixing `.env` path, API worked from `curl` but browser showed no data.
**Cause:** `CORS_ORIGINS` env var defaulted to `http://localhost:7000` only — didn't include the production domain.
**Fix:** Added to `/opt/slomix/.env`:
```
CORS_ORIGINS=https://www.slomix.fyi,http://localhost:7000,http://127.0.0.1:7000
```

Verified: `access-control-allow-origin: https://www.slomix.fyi` appeared in response headers.

---

## 7. Phase 5: Database Verification

PostgreSQL was already populated from a previous migration step. Verified:

| Metric | Value |
|--------|-------|
| Rounds | 1,034 |
| Players (all-time) | 32 |
| Players (14d active) | 10 |
| Gaming Sessions | 90 |
| Total Kills | 71,212 |
| Data since | January 1, 2025 |

`/api/stats/overview` returned correct JSON. No database issues.

---

## 8. Phase 6: Discord OAuth & Authentication

### Problem

Clicking "Sign In" on the website showed `DISCORD_CLIENT_ID not configured`.

### Cause

Discord OAuth credentials were stored in a separate `website/.env` on Samba, not in the main `.env` that was copied to the VM.

### Fix

Added to `/opt/slomix/.env`:
```
SESSION_SECRET=d43f95c8d88f4f584064510e1a2f748983b596993d446da80ccfbeb7be515220
DISCORD_CLIENT_ID=1174388516004835419
DISCORD_CLIENT_SECRET=fRU1vL4GmoKWBB8cqPcxix4JaEdoTokU
DISCORD_REDIRECT_URI=https://www.slomix.fyi/auth/callback
DISCORD_REDIRECT_URI_ALLOWLIST=https://www.slomix.fyi/auth/callback
```

**Result:** Auth redirects to Discord OAuth correctly. Login works.

---

## 9. Phase 7: HTTPS / Firefox Debugging

### Symptom

- `https://www.slomix.fyi` — **Chrome: works. Firefox: shows `--` (Offline).**
- `http://www.slomix.fyi` — Works in both browsers (but this hits Samba, not VM).

### Investigation Timeline

1. **Checked CORS headers** — Correct (`access-control-allow-origin: https://www.slomix.fyi`)
2. **Checked JS MIME types** — Correct (`text/javascript; charset=utf-8`)
3. **Checked all JS files exist on VM** — All 27 files present
4. **Checked API from PowerShell** — Returns correct data (`200 OK`, valid JSON)
5. **Checked VM service logs** — `GET /api/stats/overview → 200 (68.2ms)`, no errors
6. **Checked DNS** — `www.slomix.fyi` resolves to Cloudflare IPs, `slomix.fyi` (apex) has no A record
7. **Discovered HTTP ≠ VM** — `http://www.slomix.fyi` responses had **no `CF-RAY` header**, confirming HTTP traffic bypasses Cloudflare entirely and hits Samba's web server directly. Only HTTPS goes through Cloudflare Tunnel to VM.
8. **Firefox Private Mode test** — HTTPS **works** in Firefox Private Browsing

### Red Herring: `diagnostics.js` `:8000` Errors

The built-in diagnostics script (`diagnostics.js`) hardcoded a fallback URL with port `:8000`, causing CSP violations. These errors appeared in both Chrome and Firefox console logs and were initially suspected as the cause. However, Chrome and Firefox both showed these errors — they weren't the differentiator.

### Root Cause: Firefox Extension Blocking Absolute URLs

Firefox developer console showed:
```
Error: Absolute URLs are not allowed
    fetchJSON https://www.slomix.fyi/js/utils.js:66
```

`utils.js` constructed absolute URLs:
```javascript
export const API_BASE = window.location.origin + '/api';
// Result: https://www.slomix.fyi/api
```

A Firefox browser extension (likely uBlock Origin, Privacy Badger, or similar privacy tool) was intercepting `fetch()` calls with absolute URLs and blocking them. Chrome was more lenient with the same type of extension.

**Evidence:** Firefox Private Browsing (which disables all extensions) loaded the site perfectly.

---

## 10. Phase 8: Final Fix — Relative URLs

### Changes Made

**`website/js/utils.js`** — Changed API endpoints from absolute to relative:
```javascript
// BEFORE
export const API_BASE = window.location.origin + '/api';
export const AUTH_BASE = window.location.origin + '/auth';

// AFTER
export const API_BASE = '/api';
export const AUTH_BASE = '/auth';
```

**`website/js/diagnostics.js`** — Fixed `getApiBase()` fallback:
```javascript
// BEFORE
function getApiBase() {
    if (typeof API_BASE !== 'undefined') return API_BASE;
    return `${window.location.protocol}//${window.location.hostname}:8000`;
}

// AFTER
function getApiBase() {
    return '';  // Endpoints already include /api/ prefix
}
```

**`website/js/app.js`** — Exposed `API_BASE` on `window` for non-module scripts:
```javascript
window.API_BASE = API_BASE;
```

### Deployment

Ran `python tools/sync_from_samba.py --code-only` to deploy. Both services restarted to `active`.

### Result

Firefox (regular, with extensions) now loads `https://www.slomix.fyi` correctly:
- Stats: ✓ (1.0k rounds, 10 players, 90 sessions, 71.2k kills)
- Auth: ✓ (Logged in as Zlatorog)
- Status: ✓ (Online indicator, green dot)
- All views functional

---

## 11. Current State

| Component | Status |
|-----------|--------|
| `slomix-bot` service | ✅ Active (106 commands, Samba version) |
| `slomix-web` service | ✅ Active (uvicorn, 2 workers) |
| PostgreSQL | ✅ 1,034 rounds, 32 players |
| `https://www.slomix.fyi` | ✅ Working (Chrome + Firefox) |
| Discord OAuth | ✅ Login/logout functional |
| Cloudflare Tunnel | ✅ HTTPS routing to VM |
| Code sync tool | ✅ `sync_from_samba.py` working (tar approach) |
| `/api/stats/overview` | ✅ Returns correct data |
| `/api/status` | ✅ `{"status":"online","database":"ok"}` |
| `/health` | ✅ `{"status":"ok","database":"ok"}` |

---

## 12. Remaining Items

| Item | Priority | Notes |
|------|----------|-------|
| **Prometheus monitoring** | Medium | `prometheus_client` + `prometheus_fastapi_instrumentator` not installed. Code scaffolding exists (`metrics.py`, `/metrics` route) but uses noop counters. |
| **HTTP → HTTPS redirect** | Low | `http://www.slomix.fyi` still hits Samba directly (no Cloudflare). Should either shut down Samba's web service or configure Cloudflare redirect. |
| **`slomix.fyi` apex domain** | Low | No A record — only `www.slomix.fyi` resolves. Could add CNAME flattening in Cloudflare. |
| **GitHub branch sync** | Medium | `feat/availability-multichannel-notifications` branch is way ahead of `main`. Should merge or rebase. |
| **`diagnostics.js` double `/api/`** | Low | Fixed `getApiBase()` to return `''`, but `testSessionGraphs()`, `testBackend()` etc. still prepend `/api/` manually — these work correctly now with the empty base. |
| **matplotlib config** | Low | `/opt/slomix/.config` is read-only due to systemd sandboxing. Non-fatal but generates log warnings. Fix: add `MPLCONFIGDIR=/tmp/matplotlib_cache` to `.env`. |
| **Samba bot duplication** | Medium | Both Samba and VM bots respond to Discord commands (double replies on `!ping`). Need to stop the Samba bot or use a different token. |

---

## 13. Appendix: Key Files & Credentials Reference

### VM File Locations

| File | Purpose |
|------|---------|
| `/opt/slomix/.env` | All credentials (DB, Discord, OAuth, CORS) |
| `/etc/systemd/system/slomix-bot.service` | Bot systemd unit |
| `/etc/systemd/system/slomix-web.service` | Web systemd unit |
| `/opt/slomix/venv-bot/` | Bot Python virtual environment |
| `/opt/slomix/venv-web/` | Web Python virtual environment |
| `/opt/slomix/logs/` | Application logs |
| `/opt/slomix/website/js/` | Frontend JavaScript (27 files) |
| `/etc/ssh/sshd_config.d/90-hardening.conf` | SSH hardening config |

### Key `.env` Variables (on VM)

```bash
DISCORD_BOT_TOKEN=<redacted>
GUILD_ID=<redacted>
DATABASE_TYPE=postgres
DB_HOST=localhost
DB_PORT=5432
DB_NAME=etlegacy
DB_USER=etlegacy_user
DB_PASSWORD=<redacted>
CORS_ORIGINS=https://www.slomix.fyi,http://localhost:7000,http://127.0.0.1:7000
SESSION_SECRET=<redacted>
DISCORD_CLIENT_ID=1174388516004835419
DISCORD_CLIENT_SECRET=<redacted>
DISCORD_REDIRECT_URI=https://www.slomix.fyi/auth/callback
SSH_ENABLED=true
SSH_HOST=puran.hehe.si
SSH_PORT=48101
```

### Useful Commands

```bash
# Deploy code from Samba to VM
python tools/sync_from_samba.py --code-only

# SSH to VM
python tools/vm_ssh.py --sudo "systemctl restart slomix-web"

# Check service status
python tools/vm_ssh.py --sudo "systemctl status slomix-web slomix-bot"

# View web logs
python tools/vm_ssh.py --sudo "journalctl -u slomix-web -n 50 --no-pager"

# Test API
curl https://www.slomix.fyi/api/status
curl https://www.slomix.fyi/api/stats/overview
```

---

## Issue Summary

| # | Issue | Root Cause | Fix | Time Spent |
|---|-------|-----------|-----|------------|
| 1 | GitHub code outdated | Branch not pushed to main | Sync from Samba via tar | ~30 min |
| 2 | SSH lockout | Hardening disabled password auth | Re-enabled in sshd config | ~5 min |
| 3 | Web service crash | Log directory not writable | Added to ReadWritePaths | ~10 min |
| 4 | No data on website | Wrong `.env` path in service | Fixed EnvironmentFile path | ~20 min |
| 5 | CORS blocking | Missing production origin | Added CORS_ORIGINS to .env | ~15 min |
| 6 | Auth broken | Missing OAuth credentials | Added Discord creds to .env | ~10 min |
| 7 | Footer text wrong | Old branding | Updated copyright text | ~2 min |
| 8 | Firefox HTTPS broken | Absolute URLs blocked by extension | Switched to relative URLs | ~90 min |
| 9 | Sync script Unicode crash | Non-ASCII in Python print() | Replaced with ASCII | ~10 min |

**Total estimated debugging time: ~3-4 hours**

---

*Report generated: February 20, 2026*
