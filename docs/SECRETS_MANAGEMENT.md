# Secrets Management Guide

## Superseded Notice (2026-02-12)
This guide remains valid for workflow, but occurrence counts in this document are historical snapshots and may be outdated.

For current hardcoded-secret counts/status, use:
1. `python3 tools/secrets_manager.py audit` (live count)
2. `docs/evidence/2026-02-18_ws4_reaudit.md`
3. `docs/evidence/2026-02-19_ws4_secret_rotation.md`

**Date:** 2026-02-08
**Version:** 1.0.0
**Status:** Ready for activation (NOT yet deployed)

---

## Overview

This document describes the secrets management system for the Slomix Discord Bot. The system is **ready to use** but **not yet activated** - current passwords remain unchanged until you explicitly rotate them.

## Secrets Manager Tool

Location: `tools/secrets_manager.py`

### Features

- ✅ Generate secure passwords: `random-words-typed-together-like-this1337`
- ✅ Rotate database passwords (with SQL command generation)
- ✅ Rotate Discord bot token
- ✅ Backup `.env` before any changes
- ✅ Audit codebase for hardcoded secrets
- ✅ Preserve comments and formatting from `.env.example`

### Installation

No installation needed - the tool is standalone Python 3.

### Usage

#### 1. Generate a Password

```bash
# Generate default (3 words + 4 digits)
python tools/secrets_manager.py generate

# Custom format (4 words + 6 digits)
python tools/secrets_manager.py generate --words 4 --digits 6
```

**Example output:**
```
Generated password: thunder-mountain-eagle-crystal123456
```

#### 2. Rotate Database Password

```bash
# Auto-generate new password
python tools/secrets_manager.py rotate-db

# Use specific password
python tools/secrets_manager.py rotate-db --password your-new-password
```

**What it does:**
1. Backs up `.env` to `.env.backup.YYYYMMDD_HHMMSS`
2. Generates new password (if not provided)
3. Updates `POSTGRES_PASSWORD` in `.env`
4. Prints SQL command you need to run

**You must then run:**
```bash
psql -U postgres -d etlegacy
ALTER USER etlegacy_user WITH PASSWORD 'new-password-here';
```

#### 3. Rotate Discord Bot Token

```bash
# Get new token from https://discord.com/developers/applications
python tools/secrets_manager.py rotate-discord YOUR_NEW_TOKEN_HERE
```

**What it does:**
1. Backs up `.env`
2. Updates `DISCORD_BOT_TOKEN` in `.env`
3. Reminds you to restart the bot

#### 4. Backup `.env` File

```bash
python tools/secrets_manager.py backup-env
```

Creates timestamped backup: `.env.backup.20260208_143022`

#### 5. Audit for Hardcoded Secrets

```bash
python tools/secrets_manager.py audit
```

Scans entire codebase for the hardcoded production password `REDACTED_DB_PASSWORD` and reports all occurrences.

---

## Current Situation (Before Rotation)

### Hardcoded Password Locations

The production password `REDACTED_DB_PASSWORD` is currently hardcoded in **33+ files**:

| Location | Count | Risk Level |
|----------|-------|------------|
| `docs/2026-01-30-r2-parser-fix/scripts/*.py` | 10 | MEDIUM (archived scripts) |
| `tests/conftest.py` | 2 | HIGH (uses as fallback) |
| `.github/workflows/tests.yml` | 3 | HIGH (CI workflow) |
| `docs/CLAUDE.md` + session notes | 15+ | LOW (documentation) |
| Other docs | 3+ | LOW (references) |

### Migration Plan

When you're ready to rotate:

1. ✅ **Backup everything:**
   ```bash
   python tools/secrets_manager.py backup-env
   pg_dump etlegacy > backup.sql
   ```

2. ✅ **Generate new password:**
   ```bash
   python tools/secrets_manager.py generate --words 4 --digits 6
   ```

3. ✅ **Update PostgreSQL:**
   ```bash
   psql -U postgres -d etlegacy
   ALTER USER etlegacy_user WITH PASSWORD 'new-password';
   \q
   ```

4. ✅ **Update `.env`:**
   ```bash
   python tools/secrets_manager.py rotate-db --password new-password
   ```

5. ✅ **Update CI/CD:**
   - GitHub Secrets: `POSTGRES_TEST_PASSWORD`
   - Update `.github/workflows/tests.yml` to use secret

6. ✅ **Fix hardcoded references:**
   ```bash
   # Find all occurrences
   python tools/secrets_manager.py audit

   # Replace in files:
   # - tests/conftest.py: Use os.getenv without fallback
   # - docs scripts: Replace with os.getenv or use test password
   # - CLAUDE.md: Replace with placeholder like 'your_secure_password_here'
   ```

7. ✅ **Restart services:**
   ```bash
   sudo systemctl restart etlegacy-bot
   sudo systemctl restart etlegacy-website  # if applicable
   ```

8. ✅ **Verify:**
   ```bash
   # Test bot connection
   python -c "import asyncpg; asyncpg.connect(...)"

   # Check bot logs
   sudo journalctl -u etlegacy-bot -n 50
   ```

---

## Security Best Practices

### DO ✅

- Use `os.getenv()` for all secrets in code
- Store secrets only in `.env` (gitignored)
- Use GitHub Secrets for CI/CD
- Rotate passwords every 6-12 months
- Use different passwords for test/prod
- Keep `.env.backup.*` files secure (don't commit!)

### DON'T ❌

- Never commit `.env` to git
- Never hardcode passwords in source code
- Never use production passwords in tests
- Never share passwords in documentation
- Never use default/example passwords in production

---

## Password Format Specification

Generated passwords follow this format:

```
<word1>-<word2>-<word3>-<word4><digits>
```

**Example:** `thunder-mountain-eagle-crystal123456`

**Characteristics:**
- Length: 35-50 characters
- Entropy: ~60-70 bits (from word selection) + 20 bits (6 digits) = 80+ bits
- Memorability: Words are readable English nouns
- Complexity: Meets all standard requirements (uppercase, lowercase, numbers, special chars via hyphens)

**Word list:** 64 carefully selected words from nature, mythology, science, and technology domains.

---

## Secrets Inventory

### Current Secrets

| Secret | Location | Purpose |
|--------|----------|---------|
| `POSTGRES_PASSWORD` | `.env` | Database authentication |
| `DISCORD_BOT_TOKEN` | `.env` | Discord API authentication |
| `SESSION_SECRET` | Website `.env` | Web session encryption |
| `DISCORD_CLIENT_ID` | Website `.env` | OAuth |
| `DISCORD_CLIENT_SECRET` | Website `.env` | OAuth |
| `SSH_KEY_PATH` | `.env` | VPS access |
| `RCON_PASSWORD` | Not in repo | Game server (if used) |

### Rotation Schedule (Recommended)

| Secret | Frequency | Last Rotated | Next Due |
|--------|-----------|--------------|----------|
| Database password | 12 months | Never | TBD |
| Discord bot token | On compromise | Dec 2025 | N/A |
| Session secret | 6 months | Dec 2025 | Jun 2026 |
| SSH keys | 12 months | Dec 2025 | Dec 2026 |

---

## Troubleshooting

### "Can't connect to database after rotation"

1. Check `.env` has correct password
2. Verify PostgreSQL user password was updated:
   ```sql
   ALTER USER etlegacy_user WITH PASSWORD 'new-password';
   ```
3. Restart bot: `sudo systemctl restart etlegacy-bot`
4. Check logs: `sudo journalctl -u etlegacy-bot -n 50`

### "Bot won't start after token rotation"

1. Verify new token is valid on Discord developers portal
2. Check token has no extra whitespace in `.env`
3. Token should be 70-80 characters long
4. Restart bot

### "Audit finds too many results"

This is expected before first rotation. After rotating and fixing hardcoded references, the audit should show 0 results.

---

## Future Enhancements

Planned features for secrets_manager.py v2.0:

- [ ] Automated PostgreSQL password rotation (execute ALTER USER)
- [ ] SSH key rotation and deployment
- [ ] Integration with HashiCorp Vault
- [ ] Automated GitHub Secrets update via API
- [ ] Secret expiration tracking and alerts
- [ ] Multi-environment support (dev/staging/prod)
- [ ] Encrypted secrets storage

---

**Status:** System ready. Waiting for activation command.
**Next step:** When ready, run `python tools/secrets_manager.py audit` to see current state.
