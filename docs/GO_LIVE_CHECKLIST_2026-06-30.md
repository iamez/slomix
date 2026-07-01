# Go-Live Checklist — activate the merged audit/feature work (2026-06-30)

Everything from the deep audit + remediation + features is merged to `main` and
verified locally (3169 tests, canary + runtime). This is the **owner-gated ops**
sequence to make it live and activate the betting roster-binding + Lua aim-lock fix.
All steps are owner-run; the supporting scripts are read-only / dry-run by default.

> Order: A1 backup → A2 deploy → A3 migration 011 → A4 Lua → (A5 backfills, optional).
> Verify after each before the next.

## A1 — Backup first (always)
```
./scripts/db_backup.sh        # timestamped pg_dump → backups/etlegacy_<ts>.sql.gz
```
Keep the path; it's the restore point for A3/A5 (and Phase C later).

## A2 — Deploy the website
```
./scripts/deploy_release.sh <TAG>     # builds React (step 3c) + cache-bust + migrations + restart
```
What's new vs before: **step 3c builds `website/static/modern/`** (atomic: staging →
verify `route-host.js` non-empty → swap; keeps `static/modern.prev` on failure).
This is what removes "Modern Route Offline".
**Verify:**
```
BASE_URL=https://www.slomix.fyi ./scripts/verify_post_deploy.sh
```
Then open each MODERN route in the browser — `#/proximity-player`, `#/proximity-replay`,
`#/proximity-teams`, `#/skill-rating` — no "Offline" panel. Spot-check a couple of LEGACY
routes (sessions, leaderboards) unchanged.
**Rollback:** re-run `deploy_release.sh` with the previous tag (it's atomic + has a
service-recovery trap; `static/modern.prev` holds the prior build).

## A3 — Apply migration 011 (betting roster-binding)
Not auto-applied (it lives in `website/migrations/`, not root `migrations/`).
`parimutuel_markets` is owned by `etlegacy_user`; the ALTER is `IF NOT EXISTS`:
```
PGPASSWORD=<pw> psql -h 127.0.0.1 -U etlegacy_user -d etlegacy -v ON_ERROR_STOP=1 \
  -f website/migrations/011_add_market_rosters.sql
```
The code is guarded (`_has_roster_cols` caches only True + re-checks), so it activates
**without** a restart; restarting `slomix-web` is clean but optional.
**Verify:**
```
PGPASSWORD=<pw> psql -h 127.0.0.1 -U etlegacy_user -d etlegacy -c "\d parimutuel_markets" | grep team_._guids
```
should show `team_a_guids` + `team_b_guids`. From then on `settle_market` resolves the
winner by roster overlap (not the positional 1→team_a assumption); pre-migration it
fell back safely to positional.
**Rollback:** `website/migrations/011_add_market_rosters_down.sql` (drops the 2 columns).

## A4 — Deploy the Lua aim-lock fix (game server / puran)
Owner-gated. Copy the repo's `proximity/lua/proximity_tracker.lua` to the server, then
**full map reload — NOT `lua_restart`** (lua_restart crashes; see feedback). Mind the
basepath (the live module path on puran).
**Verify:** after the first real round, new `proximity_aim_lock` rows have realistic
`duration_ms` (the flush now closes at `last_seen` + a samples-based clamp).

## A5 — Optional: backfill historical inflated rows (dry-run first)
Forward-fix is already active after A2–A4; this only corrects HISTORY. Both default to
DRY-RUN; run `db_backup.sh` first, then `--apply`.
```
python -m scripts.backfill_orphan_r2            # dry-run (≈48 R2 rounds today, match_id-paired)
python -m scripts.backfill_orphan_r2 --apply    # marks round_status='orphan_r2' + is_valid=FALSE
python -m scripts.backfill_aim_lock_clamp       # dry-run (≈56 rows, ~726k phantom ms today)
python -m scripts.backfill_aim_lock_clamp --apply
```

## After go-live
- Cut release: merge the release-please PR (#410 → 1.19.0).
- Then Phase B (CI/dependency hardening, auto-open betting) per the plan.
- Phase C (schema unification, micro-perf) is backup-first + researched — later.
