# Slomix Production Deploy Plan — 2026-05-07

> **Companion to** `docs/audit_2026-05-07.md` and the `audit/2026-05-07-bundle` PR.
> This is the runbook for pushing the audit-bundle changes (and any merged
> changes since 1.12.0) to the production VM.

## Pre-flight checks

Run these from a workstation BEFORE touching production. All must pass.

```bash
# 1. Local working tree clean
git status -s
# (expect empty output)

# 2. main is at origin/main
git fetch origin
test "$(git rev-parse main)" = "$(git rev-parse origin/main)" || echo "FAIL: main not synced with origin"

# 3. Tests green locally (PGPASSWORD must be set in your shell, never committed)
pytest -q tests/unit/ 2>&1 | tail -5
# (expect "X passed" — was 2,859 baseline; we added ~5)

# 4. CI green on main
gh run list --branch main --limit 5
# (latest run conclusion: success)

# 5. Schema drift check vs prod (export PGPASSWORD first; do not paste in scripts)
psql -h 127.0.0.1 -U etlegacy_user -d etlegacy \
  -c "SELECT version, applied_at FROM schema_migrations ORDER BY applied_at DESC LIMIT 5;"
# (compare to expected from main; flag any mismatch)
```

## Step 1 — Migrations

### Apply `migrations/051_add_audit_indexes.sql`

This is **the only schema change in the bundle**. Indexes use `CREATE INDEX
IF NOT EXISTS` (idempotent across environments). PostgreSQL takes a brief
`SHARE` lock on the table while building each index; on the current data
volume that's a sub-second pause per index. Use `CREATE INDEX CONCURRENTLY`
manually if you want zero-lock builds during peak hours, but it cannot run
inside a transaction (which the migration runner wraps everything in).

```bash
# On production VM (slomix_vm):
sudo -u postgres psql -d etlegacy -f /home/samba/share/slomix_discord/migrations/051_add_audit_indexes.sql

# Verify indexes were created:
sudo -u postgres psql -d etlegacy -c "\di idx_round_correlations*"
sudo -u postgres psql -d etlegacy -c "\di idx_pcs_player_guid*"
sudo -u postgres psql -d etlegacy -c "\di idx_rounds_date_map*"
```

**Expected output**: 4 new indexes (one for each line in the migration).

**Rollback** (if a query plan regression appears):
```sql
DROP INDEX IF EXISTS idx_round_correlations_r1_round_id;
DROP INDEX IF EXISTS idx_round_correlations_r2_round_id;
DROP INDEX IF EXISTS idx_pcs_player_guid_round_number;
DROP INDEX IF EXISTS idx_rounds_date_map_round;
```

## Step 2 — Code deploy (website + bot)

### Strategy: independent service restarts

Production runs **two systemd units** (per memories):
- `slomix-web` — FastAPI website on :8000
- `slomix-bot` — Discord bot

These are independent; restart `slomix-web` first because the audit changes
are **website-only** at the code level (the migration applies to both). The
bot code touches only `bot/core/utils.py` (additive — `validate_embed_size`
helper) and the migration file itself.

```bash
# 1. Pull on production
cd /home/samba/share/slomix_discord
git fetch origin
git log --oneline origin/main..HEAD  # (should be empty if local was push)
git pull --ff-only origin main

# 2. Sanity check imports load
python3 -c "from website.backend.routers import auth, players_router; print('imports OK')"
python3 -c "from bot.core.utils import validate_embed_size; print('embed util OK')"

# 3. Restart website (graceful)
sudo systemctl restart slomix-web
sleep 5
sudo systemctl status slomix-web --no-pager | tail -10

# 4. Smoke test the website
curl -fs http://localhost:8000/api/status
curl -fs "http://localhost:8000/api/stats/overview" | head -c 200
curl -fs "http://localhost:8000/api/player/search?query=bronze" | head -c 200

# 5. If web smoke clean, restart bot (separate unit so failures don't compound)
sudo systemctl restart slomix-bot
sleep 5
sudo systemctl status slomix-bot --no-pager | tail -10
```

## Step 3 — Smoke tests

### Website (live in browser at production URL)

| Page | What to check |
|------|---------------|
| `/` (Home) | Loads, no console errors |
| `/#/admin` (About) | Hero shows version, live numbers, status pill green |
| `/#/availability` (#ETL) | Today/Tomorrow cards big, queue/empty state renders |
| `/#/story` | Smart Stats KIS leaderboard, archetypes show, Team Impact NOT all 100.0 |
| `/#/skill-rating` | ET Rating leaderboard loads (0 errors) |
| `/#/sessions2` | Session detail matrix renders |

### Discord bot (in Discord)

```
!leaderboard kpr      # rate-limited search underneath; should still work
!last_session         # round correlation read path
!stats <player>       # PCS aggregations through new index
!skill <player>       # ET Rating via skill_rating_service
```

### Background tasks

```bash
# Watch logs for 5 minutes after restart
journalctl -u slomix-bot -f --since "5 min ago" | grep -E "ERROR|WARNING|Round|correlation"
journalctl -u slomix-web -f --since "5 min ago" | grep -E "ERROR|WARNING|429|500"
```

**Tripwires** (any of these = rollback):
- `ERROR` log lines from `round_correlation_service` (new indexes mis-used)
- `429 Too Many Requests` rate from `/api/player/search` (too aggressive limit)
- HTTP 500 spikes on the website
- Discord bot reconnect loop

## Step 4 — Rollback plan

### If migration is fine but code is bad

```bash
# Revert to the prior tag
git checkout v1.12.0  # the last known-good release
sudo systemctl restart slomix-web slomix-bot
```

### If migration introduced an issue

Indexes are zero-risk to drop (revert SQL above). Code revert + index drop is
fully reversible.

### If a deeper regression (data) appears

Stop services first, take a DB snapshot, then debug:

```bash
sudo systemctl stop slomix-bot slomix-web
pg_dump -h 127.0.0.1 -U etlegacy_user etlegacy \  # PGPASSWORD set in shell env, do not inline
  > /tmp/etlegacy_pre_audit_rollback_$(date +%s).sql
# … debug …
sudo systemctl start slomix-web
sudo systemctl start slomix-bot
```

## Post-deploy verification (T+30 min)

```bash
# Bot still alive?
sudo systemctl is-active slomix-bot
# Website still alive?
sudo systemctl is-active slomix-web

# Check the rate-limit cleanup actually ran
# (no easy way to introspect; just verify search still works)
curl -fs "http://localhost:8000/api/player/search?query=ab" -o /dev/null -w "%{http_code}\n"
# 30/min limit means 30 tries → 429

# Check new indexes are being used
sudo -u postgres psql -d etlegacy -c "
EXPLAIN ANALYZE
SELECT correlation_id FROM round_correlations
WHERE r1_round_id = 100 LIMIT 1;
"
# Look for "Index Scan using idx_round_correlations_r1_round_id"
```

## Items NOT in this deploy

The following audit findings are documented but **deferred** for a separate
release after staging soak:

- File-tracker auto-mark-old behavior change (data loss risk on misconfig)
- Lua server version drift verification (need ops shell access first)
- CSP `'unsafe-inline'` removal (large frontend refactor, weeks of work)
- Voice session race-condition lock (rare in 1-channel community)

See `docs/audit_2026-05-07.md` "Deferred" section for the full list.

## Communication

After successful deploy:
1. Drop a one-liner in the team Discord with the version + change summary.
2. Update the announcement embed (if any) with the new version badge.
3. Snapshot the deploy timestamp in `MEMORY.md` (already in CLAUDE memory pattern).

## Sign-off

When all of the above passes, this deploy is considered complete. The
`audit/2026-05-07-bundle` PR can be marked merged-and-deployed.
