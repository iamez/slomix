# Deployment Runbook

> **Created:** 2026-02-20
> **Scope:** Step-by-step procedure for deploying code to the production VM
> **Rule:** Do NOT improvise. Follow these steps in order.

---

## Quick Reference

| Item | Value |
|------|-------|
| **VM IP** | `192.168.64.159` |
| **VM User** | `slomix` |
| **VM Project Dir** | `/opt/slomix` |
| **Bot Service** | `slomix-bot` |
| **Web Service** | `slomix-web` |
| **Env File** | `/opt/slomix/.env` |
| **Bot Venv** | `/opt/slomix/venv-bot` |
| **Web Venv** | `/opt/slomix/venv-web` |
| **Health Check** | `https://www.slomix.fyi/api/status` |
| **Domain** | `https://www.slomix.fyi` (Cloudflare Tunnel) |

---

## Recommended Deploy Method: Git-Based Deploy on VM

**Why this method:**
- Simple, auditable, repeatable
- VM always tracks a known git commit/tag
- Rollback = `git checkout <previous-tag>`
- No custom tooling needed beyond git + SSH
- CI validates code before it reaches `main`

**Why NOT the alternatives:**
- `sync_from_samba.py` (tar approach): No audit trail, no rollback, hardcoded passwords, bypasses GitHub entirely
- rsync from dev machine: Same drift risk as tar; which dev machine is canonical?
- Full CI/CD SSH push: Ideal long-term but over-engineered for a 1-person team with occasional deploys
- Docker: Infrastructure already works; containerizing adds complexity without proportional benefit right now

---

## Pre-Deploy Checklist

Before deploying, verify ALL of these:

- [ ] Code is merged to `main` via PR
- [ ] CI is green on `main` (check GitHub Actions)
- [ ] Release tag created (e.g., `v1.1.0`)
- [ ] You have SSH access to the VM
- [ ] You know what changed (read the PR/changelog)
- [ ] No active gaming session (check Discord voice or `!session_status`)

---

## Step-by-Step Deploy

### 1. SSH to VM

```bash
ssh slomix@192.168.64.159
# Or if using key auth (recommended, see VM_ACCESS.md):
ssh -i ~/.ssh/slomix_vm_ed25519 slomix@192.168.64.159
```

### 2. Check Current State

```bash
# What's currently running?
cd /opt/slomix
git log --oneline -3
git status
sudo systemctl status slomix-bot slomix-web --no-pager
```

Note the current commit hash for rollback.

### 3. Pull Latest Code

```bash
cd /opt/slomix

# Fetch and checkout the release tag
git fetch origin
git checkout v1.1.0   # Replace with actual tag

# Or if deploying latest main (not recommended for prod):
# git pull origin main
```

### 4. Update Dependencies (If Changed)

```bash
# Bot dependencies
sudo -u slomix_bot /opt/slomix/venv-bot/bin/pip install -r requirements.txt --quiet

# Web dependencies
sudo -u slomix_web /opt/slomix/venv-web/bin/pip install -r website/requirements.txt --quiet
```

### 5. Run Database Migrations (If Needed)

```bash
# Check if any new migrations exist
ls -la website/migrations/

# Review the migration SQL BEFORE running
cat website/migrations/006_*.sql   # Replace with actual migration file

# Run migration (ALWAYS review first)
PGPASSWORD='<password>' psql -h localhost -U etlegacy_user -d etlegacy -f website/migrations/006_*.sql

# Verify
PGPASSWORD='<password>' psql -h localhost -U etlegacy_user -d etlegacy \
  -c "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
```

### 6. Restart Services (Correct Order)

```bash
# Web first (faster restart, less critical)
sudo systemctl restart slomix-web
sleep 3
sudo systemctl status slomix-web --no-pager | head -5

# Then bot (handles webhooks, SSH monitoring)
sudo systemctl restart slomix-bot
sleep 5
sudo systemctl status slomix-bot --no-pager | head -5
```

### 7. Post-Deploy Verification

```bash
# API health
curl -s https://www.slomix.fyi/api/status
# Expected: {"status":"online","database":"ok"}

curl -s https://www.slomix.fyi/health
# Expected: {"status":"ok","database":"ok"}

# Stats overview (confirms DB access)
curl -s https://www.slomix.fyi/api/stats/overview | head -c 200

# Check for errors in recent logs
sudo journalctl -u slomix-web -n 20 --no-pager | grep -i error
sudo journalctl -u slomix-bot -n 20 --no-pager | grep -i error

# Verify deployed version matches tag
cat /opt/slomix/pyproject.toml | grep version
git log --oneline -1
```

### 8. Verify Pipeline Health (If Bot Changed)

```bash
# Check webhook log for recent STATS_READY events
sudo tail -20 /opt/slomix/logs/webhook.log

# Check lua_round_teams has recent data
PGPASSWORD='<password>' psql -h localhost -U etlegacy_user -d etlegacy \
  -c "SELECT COUNT(*) FROM lua_round_teams WHERE captured_at > NOW() - INTERVAL '7 days'"
```

### 9. Document the Deploy

After successful deploy, note in a deployment log or Discord channel:
```
Deployed v1.1.0 to prod (2026-02-21 19:00 CET)
Commit: abc1234
Changes: availability system, formula fixes
Status: healthy
```

---

## Rollback Procedure

If something goes wrong after deploy:

### Quick Rollback (< 2 minutes)

```bash
ssh slomix@192.168.64.159
cd /opt/slomix

# Go back to previous known-good tag
git checkout v1.0.8   # Replace with previous tag

# Restart services
sudo systemctl restart slomix-web
sudo systemctl restart slomix-bot

# Verify
curl -s https://www.slomix.fyi/api/status
```

### If Database Migration Was Run

**Forward-only migrations** (most cases): The old code should still work with the new schema (we design migrations to be backward-compatible by using `ADD COLUMN ... DEFAULT NULL`).

**Breaking migration** (rare): If the migration dropped/renamed columns:
```bash
# Restore from pg_dump backup taken before migration
PGPASSWORD='<password>' pg_dump -h localhost -U etlegacy_user etlegacy > /tmp/pre_migration_backup.sql

# To restore (DESTRUCTIVE):
PGPASSWORD='<password>' psql -h localhost -U etlegacy_user -d etlegacy < /tmp/pre_migration_backup.sql
```

**Rule:** Always take a pg_dump backup BEFORE running a migration that drops or renames anything.

---

## Database Backup Before Deploy

```bash
# Run this BEFORE Step 5 (migrations)
PGPASSWORD='<password>' pg_dump -h localhost -U etlegacy_user -d etlegacy \
  | gzip > /opt/slomix/backups/pre-deploy-$(date +%Y%m%d-%H%M%S).sql.gz

# Verify backup
ls -lh /opt/slomix/backups/pre-deploy-*.sql.gz | tail -1
```

---

## VM Git State (Verified 2026-02-20)

The VM is already a git clone from GitHub:
- **Repo:** `https://github.com/iamez/slomix.git`
- **Branch:** `main`
- **Current commit:** `8dca0e1` (same as GitHub `origin/main`)
- **Git version:** 2.47.3

No first-time setup needed. `git fetch` + `git checkout <tag>` works directly.

---

## Emergency Hotfix Procedure

For critical production-down situations where the normal workflow is too slow:

1. Fix the issue on a local branch
2. Push directly to a `hotfix/` branch
3. Merge to `main` (skip PR if truly emergency)
4. Deploy immediately using the steps above
5. **Follow up**: Create a PR retroactively, document what happened

**This should be extremely rare.** Most issues can wait for a normal PR cycle.

---

## Cron / Scheduled Tasks

Currently no deploy-related cron jobs on the VM. If we add automated deploys later, they would go here.

---

*See also: `docs/DEVELOPMENT_WORKFLOW.md` for branch/PR/release process.*
*See also: `docs/VM_ACCESS.md` for SSH setup and VM details.*
