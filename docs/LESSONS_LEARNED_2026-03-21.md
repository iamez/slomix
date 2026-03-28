# Lessons Learned: 2026-03-20/21 Session Post-Mortem

**Date**: 2026-03-21
**Severity**: Mixed (one CRITICAL security issue, multiple HIGH operational issues)
**Impact**: ~4 hours of recovery work, one credential rotation required

---

## Table of Contents

1. [FastAPI StaticFiles .env Exposure (CRITICAL)](#1-fastapi-staticfiles-env-exposure)
2. [Git Corrupt Objects & Working Tree Destruction](#2-git-corrupt-objects--working-tree-destruction)
3. [Deployment Drift Between Samba and VM](#3-deployment-drift-between-samba-and-vm)
4. [Database Schema Drift Between Environments](#4-database-schema-drift-between-environments)
5. [Stats Formula Regressions (Recurring)](#5-stats-formula-regressions-recurring)
6. [R0 Summary Row Double-Counting](#6-r0-summary-row-double-counting)
7. [Prevention Checklist (Quick Reference)](#7-prevention-checklist)

---

## 1. FastAPI StaticFiles .env Exposure

**Severity**: CRITICAL -- credentials exposed over HTTP

### What Happened

The FastAPI backend mounted the entire `website/` directory as a static file server:

```python
# website/backend/main.py (line 315)
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
```

Because `website/.env` existed inside the served directory, anyone could retrieve it
with a simple HTTP request:

```bash
curl http://host:7000/.env
# Returned: DB passwords, Discord tokens, session secrets, SSH credentials
```

### Root Cause

1. **Overly broad static mount**: Mounting `/` to serve the entire `website/` directory
   means every file in that directory tree is potentially accessible unless explicitly blocked.
2. **No middleware protection at the time**: The sensitive-file-blocking middleware was
   added only after the vulnerability was discovered.
3. **.env lived inside the served directory**: The `.env` file was placed in `website/`
   for convenience, directly inside the StaticFiles root.

### What We Did to Fix It

1. Added `block_sensitive_files` middleware to `main.py` (now lines 220-230):
   ```python
   _BLOCKED_PATHS = {".env", ".env.example", ".env.production", ".git", ".gitignore"}
   _BLOCKED_PREFIXES = (".env", "backend/", "frontend/src/", "__pycache__/")

   @app.middleware("http")
   async def block_sensitive_files(request, call_next):
       path = request.url.path.lstrip("/")
       if path in _BLOCKED_PATHS or any(path.startswith(p) for p in _BLOCKED_PREFIXES):
           return JSONResponse(status_code=404, content={"detail": "Not Found"})
       return await call_next(request)
   ```
2. Rotated all exposed credentials (DB passwords, Discord tokens, session secrets).
3. Added security headers middleware (X-Frame-Options, X-Content-Type-Options, etc.).

### What The Industry Recommends

This is a **known class of vulnerability**. Starlette (which FastAPI uses) had a formal
CVE for path traversal in StaticFiles: [CVE-2023-29159](https://nvd.nist.gov/vuln/detail/CVE-2023-29159).

Key recommendations from security researchers:

- **Never serve your application root as StaticFiles.** Create a dedicated `public/` or
  `dist/` directory that contains only files intended for public access.
- **Use Nginx as a reverse proxy** with dotfile blocking:
  ```nginx
  # In your server block -- blocks ALL dotfiles
  location ~ /\. {
      deny all;
      access_log off;
      log_not_found off;
  }

  # Exception for LetsEncrypt
  location ~ ^/.well-known {
      allow all;
  }
  ```
- **Defense in depth**: Even with middleware, put Nginx in front. The middleware is the
  second line of defense, not the first.
- **Upgrade Starlette**: Ensure you are on Starlette >= 0.27.0 which fixes the
  `os.path.commonprefix` path traversal bug.

### Prevention Strategy

| Action | Owner | Status |
|--------|-------|--------|
| Move `.env` **outside** the served directory (e.g., to project root or `/etc/slomix/`) | Dev | TODO |
| Add Nginx reverse proxy with dotfile deny rules | Ops | TODO |
| Create a `website/public/` directory; only serve that | Dev | TODO |
| Add automated security scan to CI that checks for exposed dotfiles | Dev | TODO |
| Add startup self-check that verifies `.env` is NOT inside StaticFiles root | Dev | TODO |

**Startup self-check pattern** (add to `main.py`):

```python
# Add after static_dir is defined
_env_in_static = os.path.join(static_dir, ".env")
if os.path.exists(_env_in_static):
    logger.critical(
        "SECURITY: .env file found inside StaticFiles directory (%s). "
        "Move it outside the served directory immediately!",
        _env_in_static
    )
    # In production, refuse to start:
    if os.getenv("ENVIRONMENT") == "production":
        raise RuntimeError(".env must not exist inside the static files directory")
```

### Sources

- [Securing FastAPI Applications (GitHub)](https://github.com/VolkanSah/Securing-FastAPI-Applications)
- [CVE-2023-29159: Starlette Path Traversal in StaticFiles](https://nvd.nist.gov/vuln/detail/CVE-2023-29159)
- [Nginx: Block Access to Sensitive Files](https://www.guyrutenberg.com/2024/01/30/nginx-block-access-to-sensitive-files/)
- [OWASP Path Traversal](https://owasp.org/www-community/attacks/Path_Traversal)
- [Don't Accidentally Serve Dotfiles With Nginx](https://maximorlov.com/tips/dont-accidentally-serve-dotfiles-with-nginx/)

---

## 2. Git Corrupt Objects & Working Tree Destruction

**Severity**: HIGH -- lost uncommitted work, hours of recovery

### What Happened

A sequence of cascading failures:

1. **Corrupt git object**: `.git/objects/bc/071c77...` was an empty file (0 bytes).
2. **`git checkout main`** was run while on a feature branch with uncommitted changes.
   Because the object database was corrupt, Git could not properly verify the working
   tree, and the checkout **deleted tracked files** instead of refusing.
3. **`git clean -fd`** was run to "clean up", which removed untracked files irreversibly.
4. Recovery required replacing `.git/` with a fresh clone and then running
   `git checkout -- .` to restore files from the remote HEAD.

### Root Cause

1. **Empty object files**: Likely caused by a system crash, disk issue, or interrupted
   `git` operation (e.g., killed during `git gc` or `git repack`). On network-mounted
   filesystems (like Samba shares), this is especially common due to write caching
   and incomplete flushes.
2. **No pre-flight check**: We ran `git checkout` without first running `git fsck` to
   verify repository integrity.
3. **Uncommitted changes**: Working on a feature branch without committing frequently
   meant there was no safety net when the checkout went wrong.
4. **Destructive commands**: `git clean -fd` and force checkouts were used as "fixes"
   but actually made things worse.

### Standard Recovery Procedure (What We Should Have Done)

**Step 1: Always backup first**
```bash
cp -a .git .git.backup
# Or tar the whole thing:
tar czf repo-backup-$(date +%Y%m%d).tar.gz .
```

**Step 2: Diagnose**
```bash
git fsck --full 2>&1 | head -50
# Look for: "error: object file ... is empty"
# Also check: find .git/objects -type f -empty
```

**Step 3: Remove empty objects**
```bash
find .git/objects -type f -empty -print -delete
```

**Step 4: Recover from remote**
```bash
git fetch --all --prune
# This downloads all missing objects from the remote
```

**Step 5: Verify and repack**
```bash
git fsck --full       # Should be clean now
git repack -Ad        # Repack objects for efficiency
git prune --expire=now  # Remove dangling objects
```

**Step 6: If HEAD is broken**
```bash
# Find the latest valid commit
git reflog show HEAD | head -10
# Reset to it
git reset --hard <valid-commit-hash>
```

### What The Industry Recommends

From [Git Cookbook - Repairing Broken Repositories](https://git.seveas.net/repairing-and-recovering-broken-git-repositories.html):

> "Your repository is already broken. Don't break it any further without first
> making sure nobody can access it except you."

Key practices:
- **Run `git fsck` periodically** as a cron job or pre-push hook
- **Avoid working directly on network-mounted filesystems** (NFS, Samba/CIFS).
  If you must, set `core.fsyncObjectFiles = true` in git config.
- **Commit frequently** -- uncommitted work is the most vulnerable
- **Never run `git clean -fd` without `--dry-run` first**:
  ```bash
  git clean -fdn  # DRY RUN -- shows what would be deleted
  git clean -fd    # Only after verifying the dry run output
  ```

### Prevention Strategy

| Action | Implementation |
|--------|---------------|
| Add `git fsck` to weekly cron | `0 3 * * 0 cd /home/samba/share/slomix_discord && git fsck --full >> /tmp/git-fsck.log 2>&1` |
| Set fsync for Samba share | `git config core.fsyncObjectFiles true` |
| Pre-checkout safety alias | Add to `.bashrc`: `alias gco='git stash && git checkout'` |
| Never use `git clean` without dry run | Add to `.gitconfig`: `[alias] clean-check = clean -fdn` |
| Commit WIP frequently | Use `git commit -m "WIP: description"` before any branch switch |
| Backup .git before risky ops | Script wrapper for destructive git commands |

**Git safety aliases** (add to `~/.gitconfig`):

```ini
[alias]
    # Safe checkout: stash first, then switch
    sco = "!f() { git stash push -m \"auto-stash before checkout\" && git checkout \"$@\"; }; f"
    # Safe clean: always dry-run first
    clean-preview = clean -fdn
    # Repository health check
    health = "!git fsck --full && echo 'Repository OK' || echo 'CORRUPTION DETECTED'"
```

### Sources

- [Git Cookbook: Repairing Broken Repositories](https://git.seveas.net/repairing-and-recovering-broken-git-repositories.html)
- [GitLab: Fix Missing or Corrupt Git Objects](https://support.gitlab.com/hc/en-us/articles/20902108343068-How-To-Fix-Missing-or-Corrupt-Git-Objects)
- [Fix Git Object File Is Empty](https://oneuptime.com/blog/post/2026-01-24-git-object-file-empty-corruption/view)
- [Git Stash: Saving Changes (Atlassian)](https://www.atlassian.com/git/tutorials/saving-changes/git-stash)
- [Recovering Corrupted Git Objects](https://xnacly.me/posts/2023/corrupted-git/)

---

## 3. Deployment Drift Between Samba and VM

**Severity**: HIGH -- production 69 commits behind, diverged history

### What Happened

1. The production VM had not been deployed to in a long period, falling **69 commits behind**.
2. The VM had a local-only commit (`10919ab`) that was never pushed, creating a
   **diverged history** between `origin/main` and the VM's local main.
3. When a critical security fix needed to be pushed, `git push` failed because local
   was behind remote.
4. Had to resort to the **GitHub API** to push the security commit directly.
5. Samba (dev) had its own local main that was also behind remote main.

### Root Cause

1. **No CI/CD pipeline**: Deployments were manual `ssh + tar` operations.
2. **No deployment cadence**: No regular schedule for syncing VM with latest code.
3. **Ad-hoc changes on VM**: The local-only commit on the VM created a fork in history
   that prevented clean fast-forward merges.
4. **No deployment tracking**: No record of what version was running on the VM.

### What We Did to Fix It

1. Created `scripts/deploy_clean.sh` -- a structured deployment script that:
   - Builds a minimal file list of essential files
   - Stops services, copies via tar+scp, applies schema, restarts
   - Optionally pushes a clean snapshot to a `prod` branch on GitHub
2. Deployed the full codebase to bring VM in sync.
3. Established the `prod` branch on GitHub as the deployment record.

### What The Industry Recommends

From [Octopus Deploy: Multi-Environment Deployments](https://octopus.com/devops/software-deployments/multi-environment-deployments/) and the [12-Factor App](https://12factor.net/dev-prod-parity):

**Core Principles:**

1. **Environment parity**: Dev, staging, and production should be as similar as possible
   in terms of code, config, and backing services.
2. **Infrastructure as Code (IaC)**: Define deployment procedures in version-controlled scripts.
3. **Immutable deployments**: Never modify code directly on production. Always deploy
   from a known artifact (git tag, tarball, container image).
4. **Version tracking**: Every deployment should record what version was deployed, when,
   and by whom.

### Prevention Strategy

**Immediate (this week):**

```bash
# Add version file that deploy script updates
echo "$(git rev-parse HEAD) $(date -Is)" >> /opt/slomix/.deploy_history
```

**Short-term (this month):**

1. Add a **deploy version endpoint** to the website:
   ```python
   @app.get("/api/version")
   async def version():
       version_file = os.path.join(project_root, "VERSION")
       if os.path.exists(version_file):
           with open(version_file) as f:
               return {"version": f.read().strip()}
       return {"version": "unknown"}
   ```

2. Add **deploy-on-merge** GitHub Action:
   ```yaml
   name: Deploy to VM
   on:
     push:
       branches: [main]
   jobs:
     deploy:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - name: Deploy via SSH
           uses: appleboy/ssh-action@v1
           with:
             host: ${{ secrets.VM_HOST }}
             username: ${{ secrets.VM_USER }}
             key: ${{ secrets.VM_KEY }}
             script: |
               cd /opt/slomix
               git pull origin main
               sudo systemctl restart slomix-bot slomix-web
   ```

3. **Never make local-only commits on the VM.** If hotfixes are needed in production:
   ```bash
   # On the VM, always push hotfixes back to origin
   git checkout -b hotfix/description
   # ... make changes ...
   git commit -m "fix(scope): description"
   git push origin hotfix/description
   # Then merge via PR on GitHub
   ```

**Long-term:**

| Practice | Tool/Method |
|----------|-------------|
| Container-based deployment | Docker + docker-compose |
| Automated deploy on merge | GitHub Actions |
| Deploy version dashboard | `/api/version` endpoint + Uptime monitoring |
| Rollback capability | `deploy_clean.sh --rollback` using git tags |
| Never modify prod directly | Read-only deploy user, no git on VM |

### Sources

- [Multi-Environment Deployments (Octopus Deploy)](https://octopus.com/devops/software-deployments/multi-environment-deployments/)
- [Configuration Drift Prevention (CloudRay)](https://cloudray.io/articles/configuration-drift)
- [CI/CD Best Practices (JetBrains)](https://www.jetbrains.com/teamcity/ci-cd-guide/ci-cd-best-practices/)
- [Environment Consistency Guide (VegaStack)](https://vegastack.com/community/guides/deployment-environment-consistency-dev-test-prod)

---

## 4. Database Schema Drift Between Environments

**Severity**: HIGH -- bot crashed on startup, queries returned wrong data

### What Happened

1. **Column mismatch**: `time_played_percent` column existed on samba (dev) but not on
   the VM initially. The bot's schema validation expected a specific column count (55 or 56)
   but found 57.
2. **Data drift**: `round_vs_stats.subject_guid` was populated on samba but empty on VM,
   meaning VS stats features worked in dev but silently failed in production.
3. **Backfill gap**: Data that was backfilled on samba was never backfilled on VM,
   creating a functional difference between environments.

### Root Cause

1. **No migration tracking**: Schema changes were applied ad-hoc via `psql` commands,
   not through versioned migration files.
2. **No schema comparison**: No tooling to compare schemas between environments.
3. **Manual column additions**: New columns were added during development sessions
   without creating corresponding migration files.
4. **Validation was count-based**: The bot checked column counts rather than specific
   column names, making it fragile to any schema addition.

### What We Did to Fix It

1. Manually identified missing columns and added them to the VM.
2. Ran backfill scripts to populate empty columns.
3. Updated schema validation to be more tolerant of additional columns.

### What The Industry Recommends

From [Liquibase: Database Drift](https://www.liquibase.com/blog/database-drift) and
[Bytebase: Schema Drift](https://www.bytebase.com/blog/what-is-database-schema-drift/):

**The Golden Rule**: Schema changes should **only** happen through versioned migration
files that are committed to git and applied in order on every environment.

**Migration tools for Python + PostgreSQL:**

| Tool | Approach | Complexity |
|------|----------|------------|
| **Alembic** | Python scripts, auto-generates diffs from SQLAlchemy models | Medium |
| **Flyway** | Numbered SQL files (V1__name.sql), tracks in schema_history table | Low |
| **Manual SQL files** (our current approach) | Numbered files in `migrations/` | Lowest |

### Prevention Strategy

**1. Formalize the migration workflow:**

Every schema change gets a numbered migration file:

```
migrations/
  001_initial_schema.sql
  002_add_time_played_percent.sql
  ...
  015_add_weapon_accuracy_revives.sql
  016_add_subject_guid_to_vs_stats.sql  <-- THIS WAS MISSING
```

**2. Add a schema version table:**

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     INTEGER PRIMARY KEY,
    filename    TEXT NOT NULL,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    checksum    TEXT  -- SHA256 of the migration file
);
```

**3. Add migration runner to deploy script:**

```bash
# In deploy_clean.sh, after step 8:
for f in $(ls -1 migrations/*.sql | sort -V); do
    VERSION=$(basename "$f" | grep -oP '^\d+')
    ALREADY=$($SSH "PGPASSWORD='$DB_PASS' psql -h localhost -U etlegacy_user -d etlegacy \
        -tAc \"SELECT 1 FROM schema_migrations WHERE version = $VERSION\"" 2>/dev/null)
    if [ -z "$ALREADY" ]; then
        echo "  Applying migration: $f"
        $SSH "PGPASSWORD='$DB_PASS' psql -h localhost -U etlegacy_user -d etlegacy -f $VM_PATH/$f"
        $SSH "PGPASSWORD='$DB_PASS' psql -h localhost -U etlegacy_user -d etlegacy \
            -c \"INSERT INTO schema_migrations (version, filename) VALUES ($VERSION, '$f')\""
    fi
done
```

**4. Add schema diff check to CI:**

```bash
# Compare dev and prod schemas
pg_dump --schema-only -h dev-host -U user -d etlegacy > /tmp/schema_dev.sql
pg_dump --schema-only -h prod-host -U user -d etlegacy > /tmp/schema_prod.sql
diff /tmp/schema_dev.sql /tmp/schema_prod.sql
```

**5. Fix the column-count validation:**

Replace count-based validation with name-based validation:

```python
# Instead of: assert len(columns) in (55, 56, 57)
REQUIRED_COLUMNS = {"kills", "deaths", "damage_given", "time_played_seconds", ...}
actual_columns = set(row[0] for row in cursor.fetchall())
missing = REQUIRED_COLUMNS - actual_columns
if missing:
    raise SchemaError(f"Missing required columns: {missing}")
```

### Sources

- [Liquibase: Detect and Prevent Database Drift](https://www.liquibase.com/blog/database-drift)
- [Bytebase: What is Database Schema Drift](https://www.bytebase.com/blog/what-is-database-schema-drift/)
- [Acceldata: Understanding Schema Drift](https://www.acceldata.io/blog/schema-drift)
- [Database Migrations with Flyway (Baeldung)](https://www.baeldung.com/database-migrations-with-flyway)
- [Alembic for Database Schema Migrations](https://pranav93.github.io/blog/alembic-for-the-database-schema-migrations/)

---

## 5. Stats Formula Regressions (Recurring)

**Severity**: MEDIUM -- user-facing data was wrong repeatedly

### What Happened

The headshot percentage formula was changed to the **wrong formula at least 6 times**
during various development sessions:

| Attempt | Formula | Problem |
|---------|---------|---------|
| Wrong | `headshot_kills / kills * 100` | Measures "% of kills that were headshots" (not what users want) |
| Wrong | `headshot_hits / shots * 100` | Mixes headshot hits with total shots (meaningless) |
| Wrong | `(hs_weapon / hits) * accuracy_weight` | Added accuracy weighting nobody asked for |
| **Correct** | `headshot_hits / total_hits * 100` | "% of hits that landed on the head" |

Additionally, `FragPotential` kept being added back to embeds/leaderboards after being
removed, because different sessions had different context about what the user wanted.

### Root Cause

1. **No canonical formula reference**: The "correct" formula existed only in developer
   memory or scattered comments, not in a single authoritative source.
2. **No regression tests**: No automated tests that verify formula outputs against
   known inputs and expected outputs.
3. **Context loss between sessions**: Each AI session started fresh without knowing
   which formulas had been validated and approved by the user.
4. **Similar-sounding field names**: `headshot_kills`, `headshot_hits`, `headshots`
   (from weapon stats) are three different values that are easy to confuse.

### What The Industry Recommends

From analytics platform best practices and
[Golden Master Testing](https://en.wikipedia.org/wiki/Characterization_test):

**Golden Master / Snapshot Testing**: Capture known-good outputs for specific inputs
and assert they never change unless intentionally updated.

**Formula Registry Pattern**: Define all business formulas in a single, well-documented
location that both code and documentation reference.

### Prevention Strategy

**1. Create a canonical formula registry file:**

```python
# bot/stats/formulas.py -- SINGLE SOURCE OF TRUTH for all stat formulas
"""
CANONICAL STAT FORMULAS
=======================
DO NOT MODIFY without explicit user approval.
Each formula has a test in tests/unit/test_formulas.py.
Last reviewed: 2026-03-21
"""

def headshot_percentage(headshot_hits: int, total_hits: int, headshot_kills: int = 0, kills: int = 0) -> float:
    """
    Headshot accuracy: % of hits that landed on the head.

    Primary: headshot_hits / total_hits * 100  (from weapon_comprehensive_stats)
    Fallback: headshot_kills / kills * 100     (when weapon data unavailable)

    NOT: headshot_kills / kills (that's "headshot kill rate", a different metric)
    NOT: headshot_hits / shots (meaningless cross-stat)
    """
    if total_hits > 0:
        return (headshot_hits / total_hits) * 100
    if kills > 0:
        return (headshot_kills / kills) * 100
    return 0.0


def kd_ratio(kills: int, deaths: int) -> float:
    """Kill/death ratio. Deaths floored to 1 to avoid division by zero."""
    return kills / max(1, deaths)


def damage_per_minute(damage_given: int, time_played_seconds: int) -> float:
    """Standard DPM: total damage / total minutes played."""
    if time_played_seconds <= 0:
        return 0.0
    return (damage_given / time_played_seconds) * 60
```

**2. Add golden master tests:**

```python
# tests/unit/test_formulas.py
"""
Golden master tests for stat formulas.
These MUST NOT be changed without explicit user approval.
If a test fails, the formula was changed -- investigate before updating the test.
"""
import pytest
from bot.stats.formulas import headshot_percentage, kd_ratio, damage_per_minute

class TestHeadshotPercentage:
    """Approved formula: headshot_hits / total_hits * 100"""

    def test_normal_case(self):
        assert headshot_percentage(headshot_hits=25, total_hits=100) == 25.0

    def test_zero_hits_fallback_to_kills(self):
        assert headshot_percentage(headshot_hits=0, total_hits=0, headshot_kills=5, kills=20) == 25.0

    def test_zero_everything(self):
        assert headshot_percentage(0, 0, 0, 0) == 0.0

    def test_high_accuracy(self):
        assert headshot_percentage(headshot_hits=90, total_hits=100) == 90.0

    # REGRESSION GUARD: This test catches the common wrong formula
    def test_not_headshot_kills_over_kills(self):
        """Ensure we use hits-based formula, not kills-based, when hits are available."""
        # Player: 10 HS kills / 50 kills = 20% kill rate
        #         30 HS hits / 200 total hits = 15% hit rate
        result = headshot_percentage(headshot_hits=30, total_hits=200, headshot_kills=10, kills=50)
        assert result == 15.0  # Must be 15% (hits-based), NOT 20% (kills-based)
```

**3. Add a formula freeze comment pattern:**

In every file that uses a formula, add:

```python
# FORMULA FREEZE: headshot_percentage -- see bot/stats/formulas.py
# DO NOT CHANGE without updating tests/unit/test_formulas.py
hs_pct = headshot_percentage(hs_hits, total_hits, hs_kills, kills)
```

**4. Document approved/rejected features:**

```
# docs/FEATURE_DECISIONS.md
| Feature | Status | Decision Date | Reason |
|---------|--------|---------------|--------|
| FragPotential in leaderboard | REJECTED | 2026-03-15 | User doesn't want it shown |
| Accuracy weighting in HS% | REJECTED | 2026-03-20 | Changes meaning of the stat |
| Weapon-based HS% | APPROVED | 2026-03-20 | headshot_hits / total_hits |
```

### Sources

- [Golden Master Testing (Wikipedia)](https://en.wikipedia.org/wiki/Characterization_test)
- [Automated Regression Testing for Data Quality (Datafold)](https://www.datafold.com/blog/automated-regression-testing-data-quality)
- [Understanding Non-Regression Testing (Statsig)](https://www.statsig.com/perspectives/understanding-non-regression-testing)
- [Golden Master Testing: Refactor Complicated Views (SitePoint)](https://www.sitepoint.com/golden-master-testing-refactor-complicated-views/)

---

## 6. R0 Summary Row Double-Counting

**Severity**: HIGH -- stats inflated by ~94% in affected queries

### What Happened

The ET:Legacy stats parser creates three types of rows per match:
- **round_number = 1** (R1): First half stats
- **round_number = 2** (R2): Second half stats (differential -- R1 subtracted)
- **round_number = 0** (R0): **Match summary** = R1 + R2 combined

When queries do not filter `WHERE round_number IN (1, 2)`, they include R0 rows,
effectively counting every stat **twice** (once from R1+R2, once from R0 summary).

An audit found **30+ queries** missing this filter across the codebase, inflating
aggregated stats (kills, deaths, damage) by approximately 94%.

### Root Cause

1. **R0 is an implementation artifact**: The summary rows are useful for quick lookups
   but dangerous for aggregation. Their purpose was not documented clearly.
2. **No database constraint**: Nothing prevents queries from accidentally including R0.
3. **Copy-paste propagation**: New queries were often copied from existing ones. If the
   source query was missing the filter, all copies inherited the bug.
4. **Different conventions in different files**: Some files filtered correctly, others
   did not. No linting or review caught the inconsistency.

### What We Did to Fix It

1. Audited all queries across bot, website backend, and services.
2. Added `round_number IN (1, 2)` to every aggregation query.
3. Documented the rule in CLAUDE.md as a critical rule.

### What The Industry Recommends

This is a variant of the **"summary row mixed with detail rows"** antipattern in data
warehousing. The standard solutions are:

1. **Separate tables**: Store summaries in a different table (e.g., `match_stats` vs
   `round_stats`). This makes accidental mixing impossible.
2. **Database views**: Create views that pre-filter:
   ```sql
   CREATE VIEW player_round_stats AS
   SELECT * FROM player_comprehensive_stats WHERE round_number IN (1, 2);
   ```
3. **Row-level security / policies**: Use PostgreSQL RLS to default-exclude R0 rows.
4. **Linting / static analysis**: Catch queries that reference the table without the
   filter.

### Prevention Strategy

**1. Create a filtered view (RECOMMENDED -- implement immediately):**

```sql
-- Run as superuser or table owner
CREATE OR REPLACE VIEW v_player_round_stats AS
SELECT * FROM player_comprehensive_stats
WHERE round_number IN (1, 2);

COMMENT ON VIEW v_player_round_stats IS
    'Use this view for all aggregation queries. Excludes R0 summary rows to prevent double-counting.';
```

Then update all queries to use the view:
```python
# Before (dangerous):
query = "SELECT SUM(kills) FROM player_comprehensive_stats WHERE ..."

# After (safe):
query = "SELECT SUM(kills) FROM v_player_round_stats WHERE ..."
```

**2. Add a query linter to CI:**

```python
# tests/unit/test_no_r0_double_counting.py
"""
Scan all .py files for queries that reference player_comprehensive_stats
without a round_number filter. Fails CI if any are found.
"""
import os
import re
import pytest

QUERY_TABLE = "player_comprehensive_stats"
SAFE_PATTERNS = [
    r"round_number\s+IN\s*\(\s*1\s*,\s*2\s*\)",
    r"round_number\s*=\s*[12]",
    r"v_player_round_stats",  # Using the safe view
    r"round_number\s*=\s*0",  # Explicitly querying R0 (intentional)
]

def find_python_files():
    for root, dirs, files in os.walk("bot"):
        for f in files:
            if f.endswith(".py"):
                yield os.path.join(root, f)
    for root, dirs, files in os.walk("website/backend"):
        for f in files:
            if f.endswith(".py"):
                yield os.path.join(root, f)

def test_no_unfiltered_pcs_queries():
    violations = []
    for filepath in find_python_files():
        with open(filepath) as f:
            content = f.read()
        # Find all SQL-like strings referencing the table
        if QUERY_TABLE not in content:
            continue
        # Check each line that references the table
        for i, line in enumerate(content.split('\n'), 1):
            if QUERY_TABLE in line and not any(re.search(p, content[max(0,content.find(line)-500):content.find(line)+500], re.IGNORECASE) for p in SAFE_PATTERNS):
                # Check surrounding context (the full query, not just the line)
                pass  # Simplified -- real implementation checks query boundaries
    # In practice, use AST parsing or query extraction
    assert len(violations) == 0, f"Found {len(violations)} unfiltered queries: {violations}"
```

**3. Add a CHECK constraint comment (documentation):**

While PostgreSQL cannot enforce "always filter by round_number", we can add prominent
comments to the table:

```sql
COMMENT ON COLUMN player_comprehensive_stats.round_number IS
    'CRITICAL: 0=match summary (DO NOT include in aggregations), 1=R1, 2=R2. '
    'Always filter round_number IN (1,2) for aggregation queries or use v_player_round_stats view.';
```

### Sources

- [SQL SUM Double Counting (Microsoft Q&A)](https://learn.microsoft.com/en-us/answers/questions/576428/sum-output-double-counting)
- [SQL ROLLUP (SQLTutorial.org)](https://www.sqltutorial.org/sql-rollup/)
- [Aggregating Distinct Values (Peachpit)](https://www.peachpit.com/articles/article.aspx?p=30681&seqNum=7)

---

## 7. Prevention Checklist

Quick-reference checklist to run before and after each development session.

### Before Starting Work

```
[ ] git fsck --full                    # Verify repo integrity
[ ] git stash (if switching branches)  # Protect uncommitted work
[ ] git pull origin main               # Ensure you're up to date
[ ] Check VM deploy status             # curl http://VM:7000/api/version
```

### Before Every Commit

```
[ ] Run formula tests:                 pytest tests/unit/test_formulas.py
[ ] Check for R0 filter:               grep -rn "player_comprehensive_stats" bot/ website/backend/ | grep -v "round_number"
[ ] Check for .env exposure:           curl -s http://localhost:7000/.env | head -1
[ ] Check headshot formula:            grep -rn "headshot" bot/cogs/ | grep -v "IN (1, 2)" | grep -v "#"
```

### Before Every Deploy

```
[ ] Run full test suite:               pytest tests/
[ ] Compare schemas:                   pg_dump --schema-only on both envs, diff
[ ] Check migration files:             ls migrations/*.sql -- any unapplied?
[ ] Verify .env not in served dir:     test ! -f website/.env || echo "DANGER"
[ ] Tag the release:                   git tag -a v$(date +%Y%m%d) -m "Deploy"
```

### Monthly Maintenance

```
[ ] Rotate credentials if any were exposed
[ ] Review git stash list (clean up old stashes)
[ ] Run git gc and git fsck
[ ] Compare dev and prod schemas
[ ] Review deploy history for drift
[ ] Check Starlette/FastAPI for security updates
```

---

## Summary of Root Causes

| Problem | Root Cause Category | Core Issue |
|---------|-------------------|------------|
| .env exposure | **Security misconfiguration** | Serving app directory as static files |
| Git corruption | **Infrastructure** | Network filesystem + no integrity checks |
| Deploy drift | **Process** | No CI/CD, no deployment cadence |
| Schema drift | **Process** | No migration tracking, ad-hoc DDL |
| Formula regressions | **Knowledge management** | No canonical reference, no tests |
| R0 double-counting | **Data architecture** | Summary rows mixed with detail rows |

All six issues share a common theme: **manual processes without automated guardrails**.
The fix for all of them is the same pattern: define the correct state in code/config,
add automated checks that verify it, and make violations impossible or at least loud.

---

*Document generated: 2026-03-21*
*Next review: 2026-04-21 (or after next major incident)*
