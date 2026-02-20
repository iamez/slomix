# Development Workflow

> **Created:** 2026-02-20
> **Scope:** How we develop, test, and ship code for slomix.fyi
> **Rule #1:** Production is sacred. No direct edits on the VM.

---

## Environments

| Environment | Location | Purpose | Branch/Tag |
|-------------|----------|---------|------------|
| **Dev** | Local machines (Samba, laptops) | Feature development, testing | Feature branches |
| **Prod** | VM `192.168.64.159` (`/opt/slomix`) | Live site at `slomix.fyi` | Tagged releases only |

We do NOT run a separate staging environment today. If needed later, a second systemd service pair on the VM (different port, different `.env`) can serve as staging.

---

## Source of Truth

**GitHub `main` branch** is the single source of truth for code.

| What | Where | Why |
|------|-------|-----|
| Code | GitHub `main` | All changes flow through PRs; CI validates |
| Secrets | `/opt/slomix/.env` on VM | Never in repo; `.env.example` is the template |
| Database | PostgreSQL on VM (`localhost:5432`) | Authoritative production data |
| Config | `.env` per environment | Dev uses local `.env`, prod uses VM `.env` |

### What This Means in Practice

1. **All code changes** go through feature branches -> PR -> merge to `main`
2. **Production** runs a specific commit or release tag from `main`
3. **No one edits code on the VM** directly. If a hotfix is needed, it goes through a branch first (exception: emergency one-liner with immediate follow-up PR)
4. The old pattern of "edit on Samba, run `sync_from_samba.py`" is **retired** for production deploys. That script remains for historical reference but is replaced by the deployment workflow below.

---

## Branch Strategy

```
main (protected)
  |
  +-- feat/my-feature     # New features
  +-- fix/my-bugfix       # Bug fixes
  +-- chore/my-cleanup    # Maintenance, docs, CI
```

### Rules

| Rule | Detail |
|------|--------|
| **Never commit directly to `main`** | All changes via PR (enforced in CLAUDE.md) |
| **Branch naming** | `<type>/<short-description>` using conventional commit types |
| **PR required** | At minimum, CI must pass. Code review recommended for non-trivial changes |
| **Squash merge preferred** | Keeps `main` history clean |
| **Delete branch after merge** | Keeps branch list manageable |

### Conventional Commits

All commit messages follow: `<type>(<scope>): <description>`

- **Types:** `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `security`, `perf`
- **Scopes:** `bot`, `website`, `proximity`, `greatshot`, `ci`, `db`, `lua`
- Release Please auto-generates changelog entries from these

---

## Release Process

We use **Release Please** (already configured in `.release-please-config.json` + `.github/workflows/release.yml`) to auto-create release PRs from conventional commits.

### How It Works

1. Merge feature PRs to `main` with conventional commit messages
2. Release Please opens a "Release PR" bumping the version
3. Merge the Release PR to create a **git tag** (e.g., `v1.1.0`)
4. The tag is what gets deployed to production

### Manual Tagging (Fallback)

If Release Please isn't generating tags yet (it needs at least one release):
```bash
# After merging to main, create a release tag
git tag -a v1.1.0 -m "Release v1.1.0: availability system, formula fixes"
git push origin v1.1.0
```

---

## CI Pipeline

GitHub Actions (`.github/workflows/tests.yml`) runs on every push to `main` and every PR:

1. **Python lint** (ruff)
2. **Python tests** (pytest against PostgreSQL 14 + Redis)
3. **JS lint** (node --check)
4. **CodeQL** security scan

### CI Must Pass Before

- Merging any PR to `main`
- Creating a release tag
- Deploying to production

---

## Config Per Environment

### Dev (Local)

```bash
# .env (local, gitignored)
DATABASE_TYPE=postgres
DB_HOST=localhost
DB_PORT=5432
DB_NAME=etlegacy
DB_USER=etlegacy_user
DB_PASSWORD=<local_password>
CORS_ORIGINS=http://localhost:7000,http://localhost:8000
SSH_ENABLED=true
# ... other dev settings
```

### Prod (VM)

```bash
# /opt/slomix/.env (on VM, never in repo)
DATABASE_TYPE=postgres
DB_HOST=localhost
DB_PORT=5432
DB_NAME=etlegacy
DB_USER=etlegacy_user
DB_PASSWORD=<production_password>
CORS_ORIGINS=https://www.slomix.fyi,http://localhost:7000
DISCORD_REDIRECT_URI=https://www.slomix.fyi/auth/callback
# ... other prod settings
```

### Key Differences

| Setting | Dev | Prod |
|---------|-----|------|
| `CORS_ORIGINS` | `localhost:*` | `https://www.slomix.fyi` |
| `DISCORD_REDIRECT_URI` | `http://localhost:8000/auth/callback` | `https://www.slomix.fyi/auth/callback` |
| `SESSION_HTTPS_ONLY` | `false` | `true` (when ready) |
| Secrets | In local `.env` | In `/opt/slomix/.env` |
| Logs | `./logs/` | `/opt/slomix/logs/` |

---

## What NOT to Do

| Don't | Why |
|-------|-----|
| Edit code directly on the VM | Creates drift; no review, no CI, no rollback |
| Push to `main` without a PR | Bypasses CI and review |
| Put secrets in the repo | Use `.env` files (gitignored) |
| Run `sync_from_samba.py` for production deploys | Legacy tool; use the deployment runbook instead |
| Deploy without checking CI status | Broken code reaches production |
| Forget to tag after deploy | No way to rollback to a known state |

---

## Current State (Feb 2026)

| Item | Status | Action Needed |
|------|--------|---------------|
| Feature branch merged to `main` | PR #41 merged | Done |
| `wip/forgot-push` branch | Active, has merge conflicts | Resolve conflicts, merge, or rebase |
| Release tags | Only 1 historical tag (`pre-competitive-analytics-v1.0`) | Create `v1.1.0` after cleanup |
| VM running | Code from Samba tar sync | Needs first proper deploy from GitHub |
| `sync_from_samba.py` | Working but deprecated for prod | Keep as emergency fallback only |

---

*See also: `docs/DEPLOYMENT_RUNBOOK.md` for exact deploy steps.*
