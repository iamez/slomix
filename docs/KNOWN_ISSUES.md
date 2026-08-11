# Known Issues

> **Re-verified against code, database and live logs on 2026-08-11.**
> Rule for this file: every OPEN entry carries a `Verify:` command that proves
> the claim today. If the command stops reproducing the claim, the entry is
> stale — remove it instead of letting it mislead the next session.
> Closed entries are removed; the closure ledger at the bottom records what was
> removed in the 2026-08-11 sweep and the proof of closure. Details live in git
> history.

---

## Open — data pipeline

### Dead-hours orphan mechanism (deterministic permanent orphans) — High

Three constants disagree and together guarantee permanent proximity orphans for
rounds played 02:00-05:00 CET on the SSH-poll path:

- `bot/services/monitor_tasks_mixin.py` — the `if 2 <= hour < 11` gate makes
  the endstats monitor return outright during dead hours (02:00-11:00 CET),
  before any SSH work.
- `bot/cogs/proximity_mixins/ingestion_mixin.py` — proximity ingestion loop is
  NOT dead-hours gated, so proximity rows arrive with no `rounds` parent during
  that window.
- `bot/cogs/proximity_mixins/relinker_mixin.py` —
  `_PERMANENT_ORPHAN_AGE_HOURS = 6` (deliberately lowered 48h→6h on 2026-06-09
  for log-spam reasons) is SHORTER than the 9h dead-hours window, so those rows
  age out of relinking before imports resume at 11:00.

Measured live 2026-08-11 (supervised bot test): 5 rounds → 8,810 dev orphans
(`team_cohesion` 8,054, `reaction_metric` 492, `kill_outcome` 264); relinker ran
5×, linked 0. Full evidence: `docs/research/FINDINGS_FOR_CODEX_2026-08-11.md` §1.

Fix directions (pick one): unify the dead-hours policy across both loops, raise
`_PERMANENT_ORPHAN_AGE_HOURS` above 10h (respecting why it was lowered), or make
staleness dead-hours-aware.

Verify:
```bash
grep -n "2 <= hour < 11" bot/services/monitor_tasks_mixin.py        # gate exists
grep -n "_PERMANENT_ORPHAN_AGE_HOURS = " bot/cogs/proximity_mixins/relinker_mixin.py  # still 6
grep -n "dead" bot/cogs/proximity_mixins/ingestion_mixin.py         # no dead-hours gate
```

### Re-linker inventory covers 7 of 27 proximity round_id tables — High

27 `proximity_*` tables carry a `round_id` column; `LINKAGE_INVENTORY_TABLES`
(`bot/services/linkage_inventory_service.py`) lists 7 of them (plus
`combat_engagement` and `player_track`). ~28,000 orphan rows sit in uncovered
tables, outside every repair tool — largest: `proximity_team_cohesion` (21,170),
`proximity_weapon_accuracy` (2,462), `proximity_aim_lock` (2,383),
`proximity_revive` (1,088). `proximity_shot_fired` was not an exception, just
the only instance anyone noticed. Additionally 4 round_id tables lack a
`*_round_lookup_unlinked` partial index (`aim_lock`, `comm_event`,
`skill_snapshot`, `spawn_select`).

Fix is two-part (FIX 9 in `docs/research/FIX_ME_2026-08-11.md`): derive the list
from the schema with a failing test, then run the re-linker over the expanded
set with a dry-run report before `--apply`.

Verify:
```bash
PGPASSWORD=... psql -h 127.0.0.1 -U etlegacy_user -d etlegacy -tAc \
  "SELECT COUNT(*) FROM information_schema.columns
   WHERE column_name='round_id' AND table_schema='public' AND table_name LIKE 'proximity%'"
# → 27; compare against LINKAGE_INVENTORY_TABLES in bot/services/linkage_inventory_service.py
```

### round_number disagreement defeats the relinker on covered tables — Medium

Same physical round (te_escape2, `round_start_unix=1786418696`): the stats path
recorded `round_number=2`, the proximity path `round_number=1` →
`round_link_reason='no_rows_for_map_round'`, ~159 rows permanently unlinked even
though the table has its lookup index. Historic scope on prod: 2 of 643 linkable
rounds (0.31%); second recorded occurrence (first: mp_sillyctf 2026-06-08).
Suggested direction: when `map_name` + `round_start_unix` (+`round_end_unix`)
match exactly, trust the timestamps over `round_number` equality. Evidence:
`docs/research/FINDINGS_FOR_CODEX_2026-08-11.md` §2.

Verify:
```sql
SELECT round_link_reason, COUNT(*) FROM proximity_combat_position
WHERE round_id IS NULL GROUP BY 1;  -- 'no_rows_for_map_round' rows present
```

### Proximity NULL-round_id orphans predating migration 065 — Medium

Rows imported before migration 065 with a NULL `round_id` carry no round
identity (revive/weapon-accuracy) or only a date (other tables) and cannot be
relinked or deduped against linked siblings. Serving keeps them (dropping would
shrink long-standing totals).

Verify (weapon_accuracy is the sentinel table — it is where the identity-less
form was first proven; the same pre-065 population exists in `proximity_revive`):
```sql
SELECT COUNT(*) FROM proximity_weapon_accuracy
WHERE round_id IS NULL AND round_start_unix IS NULL;  -- > 0 identity-less rows
SELECT COUNT(*) FROM proximity_revive
WHERE round_id IS NULL AND round_start_unix IS NULL;  -- > 0 identity-less rows
```

### escort_credit / vehicle_progress: spatial capture is dead, time/count is live — Medium

Not a "dead table": time/count dimensions ARE captured (`mounted_time_ms`
2,500-48,500, `samples` 5-97, `max_health`/`destroyed_count`/`final_health`
incl. the −999 sentinel), while ALL spatial dimensions are zero. The broken
piece is the spatial capture path in the tracker. Note the live tracker on puran
now emits a new `# VEHICLE_PROGRESS` file section the repo parser has never seen
(`docs/research/FINDINGS_FOR_CODEX_2026-08-11.md` §3, §6). Owner decision
pending (FIX 13): fix Lua capture vs remove the fields from API responses —
serving zeros as data is worse than either.

Verify:
```sql
SELECT COUNT(*), COUNT(*) FILTER (WHERE total_escort_distance = 0 AND credit_distance = 0)
FROM proximity_escort_credit;   -- both counts equal (256|256 on 2026-08-11)
SELECT COUNT(*), COUNT(*) FILTER (WHERE total_distance = 0)
FROM proximity_vehicle_progress; -- both counts equal (94|94 on 2026-08-11)
```

---

## Open — Lua / game server

### Lua drift repo ↔ puran (deploy owner-gated) — High

Live SSH diff 2026-08-07: 4 of 5 scripts on puran differ from the repo
(`c0rnp0rn8.lua`, `endstats.lua`, `stats_discord_webhook.lua`,
`proximity_tracker.lua`; only `team-lock.lua` matches). The drift is
**two-directional** — neither side is a superset:

- Repo has UNDEPLOYED safety fixes: `proximity_tracker.lua` aim_lock duration
  clamp + `last_seen` round-end flush, and the `c0rnp0rn8.lua` reinf-offset
  `% 8` clamp (in the repo since #356, 2026-06-02 — the live copy predates it,
  so `bit.rshift(...) >= 8` can still nil out `aReinfOffset` live and silently
  kill wave-dependent metrics for a team).
- Live tracker is AHEAD of the repo: `shot_fired=false` with an 8-line rationale
  comment, and (new, 2026-08-11) a `# VEHICLE_PROGRESS` output section the repo
  file does not have.

Consequence already measured in data: `proximity_aim_lock` max duration
220,000 ms (3 min 40 s, 78× above p99, ~15 rows > 5 s) from the missing clamp.

**Never blind-copy in either direction.** Fix = per-file three-way merge →
commit → `scp` → activation via full map load (never `lua_restart`), in an
owner-scheduled window. Plan: `docs/research/BACKLOG_MASTER_2026-08-10.md` §1.2
+ §3b.

Verify (documented, runs against the game server):
```bash
ssh et@puran.hehe.si -p 48101 'sha256sum legacy/luascripts/*.lua'  # compare vs repo sha256sum
grep -n "% 8" vps_scripts/c0rnp0rn8.lua                            # repo clamp present (lines 193-194)
```

### full_selfkills semantics (owner decision) — Medium

The 2026-05-15 complaint (superboyy/wajs) was not a software bug — DB, stats
file and Lua all agree. It is a gap between metric semantics and player
expectation: the `>= limbotime/1000 - 2` threshold yields ~7% hit rate; players
expect ~50% ("every /kill that wasted a reinforcement"), which
`>= limbotime/1000/2` would give. Changing it changes historical numbers —
owner must choose: new separate field, or a clean cut with a date. (The related
latent `bit.rshift` clamp bug is repo-fixed and tracked under Lua drift above.)

Verify:
```bash
grep -n "limbotime" vps_scripts/c0rnp0rn8.lua   # threshold formula unchanged
```

### Planned: Lua Time Stats Overhaul — largest open plan

Status: **Not started — planning phase** (since Feb 20, 2026). Add
comprehensive per-player time tracking to `stats_discord_webhook.lua`
(spawn/death/alive/dead/denied/pause-overlap/streaks), write `-timestats.txt`
files, extend the webhook JSON, add 8 columns to `player_comprehensive_stats`,
and switch consumers once the dual-source comparison proves out. This is the
only **upstream** fix for the time-dead anomalies below; today's mitigation is
read-time only.

Phased plan (from `docs/research/BACKLOG_MASTER_2026-08-10.md` §2.1 — full
original 10-step component table in this file's git history, pre-2026-08-11):

| Phase | Content | Why this cut |
|---|---|---|
| A | Lua writes `-timestats.txt` + adds data to existing webhook JSON | Data starts flowing, nothing depends on it → zero risk |
| B | Migration: 8 new nullable columns in `player_comprehensive_stats` | Write without read; old path keeps working |
| C | `TimeStatsParser` + SSH monitor picks up new files | Dual source: compare new vs old on live data |
| D | Switch consumers (bot commands, graphs, website) | Only once B/C prove agreement |

Phase A shares the Lua deploy window with the drift merge above.

Verify (covers the Lua producer side and the Python consumer side):
```bash
grep -rn "timestats" bot/ website/backend/ vps_scripts/ --include='*.py' --include='*.lua' | wc -l  # 0 → still not started
```

### Time dead anomalies — mitigated, upstream fix pending — Low

Between 211 and 301 player-rows (explicit range — the count varies with the
counting method, measured 2026-06-02) have `time_dead > time_played` (max
overage ~573 min),
caused by the server idling on a stale map + buggy c0rnp0rn Lua time stats.
Mitigated read-time via `LEAST(time_dead, time_played)` (PR #350/#352) and the
FM6 idle-map watchdog (PR #354); stored rows are intentionally untouched (owner
decision — no backfill). True fix = Lua Time Stats Overhaul above.

Verify:
```sql
SELECT COUNT(*) FROM player_comprehensive_stats
WHERE time_dead_minutes > time_played_minutes;  -- still > 200 stored rows
```

---

## Open — website backend

### Proximity is date-scoped, not gsid (S7) — Medium

9 proximity routers still scope by `session_date` (`combat`, `player`,
`dashboard`, `trades`, `movement`, `quality`, `support`, `events`, `journey`);
a midnight-crossing session shows only its pre-midnight rounds (gsid 138:
2 rounds / 88 kills invisible). Storytelling already migrated
(`GamingSessionScope`); the infrastructure exists
(`ProximityQueryBuilder.with_session_scope`,
`website/backend/routers/proximity_helpers.py`). ⚠️ Coordinate with Codex after
2026-08-15 — these are his redesign files (serving-scope vs UI, overlapping
files, not content).

Verify (both directions: date predicate present, gsid scope absent):
```bash
grep -ln "session_date" website/backend/routers/proximity_{combat,player,dashboard,trades,movement,quality,support,events,journey}.py | wc -l  # 9
grep -ln "with_session_scope" website/backend/routers/proximity_{combat,player,dashboard,trades,movement,quality,support,events,journey}.py | wc -l  # 0
```

### `/skill/composite` single-date, no validity gate — Medium

`get_composite_stats` in `website/backend/routers/skill_router.py` accepts only `session_date`,
falls back to `SELECT MAX(session_date) FROM proximity_kill_outcome`, and has
neither `is_valid` nor bot filters — bot rounds count into the Comp Skill
composite. Last SS-D holdout (together with React `client.ts` single-date).
Fix pattern exists: storytelling routers + `_round_quality_gate_sql`
(`proximity_helpers.py`).

Verify:
```bash
sed -n '/def get_composite_stats/,/fetch_all/p' website/backend/routers/skill_router.py | grep -c "gaming_session_id\|is_valid"  # 0
```

### skill_router SDS reads capped PCS `denied_playtime` — Low

Still reads `pcs.denied_playtime` (capped) instead of `effective_denied_ms`
from `kill_outcome` — PR #541's own noted follow-up.

Verify:
```bash
grep -n "denied_playtime" website/backend/routers/skill_router.py  # PCS source still used
```

### KIS `distance_multiplier` stub — Low

Hardcoded `DISTANCE_NORMAL` (`dist_mult` assignment in
`website/backend/services/storytelling/kis.py`)
but stored/returned as a real per-kill field — falsely precise. Needs per-kill
distance data, or removal from the response.

Verify:
```bash
grep -n "dist_mult = DISTANCE_NORMAL" website/backend/services/storytelling/kis.py
```

### `website/migrations/` has no ledger — Low

17 SQL files, no drift guard — the #545 ledger cannot cover it (documented in
that PR). Same-guard adoption is the fix.

Verify (the runner's ledger covers only the root `migrations/` directory):
```bash
grep -n "MIGRATIONS_DIR" scripts/apply_migrations.py        # points at root migrations/ only
grep -c "website/migrations" scripts/apply_migrations.py    # 0 — runner never sees them
ls website/migrations/*.sql | wc -l                          # 17 unguarded files
```

### `storytelling/loaders.py` is per-date only — Low

Safe today only because `_load_context_for_dates`
(`website/backend/services/storytelling/kis.py`) merges per-date fragments;
any future direct caller of the loaders inherits the midnight bug.

Verify:
```bash
grep -n "session_date = \$1" website/backend/services/storytelling/loaders.py | head -3
```

### Formula registry gaps — Low

23 entries registered. Still missing entirely: archetypes, moments, synergy,
momentum, gravity/space/enabler/lurker, objective_pressure, session_matrix,
rivalries, season_awards. Where a module lacks a `FORMULA_VERSION` constant,
introduce one and have the registry import it (pattern: `_s_effort_version()`);
`tests/unit/test_formula_registry_contract.py` guards registered entries.

Verify (uses the registry contract, not source-line counts):
```bash
python3 -c "
from website.backend.services.formula_registry import get_registry
names = [e['name'] for e in get_registry()]
print(len(names), 'archetypes' in names)"   # → 23 False
```

---

## Open — website UX / infra (owner decisions)

### Availability page UX overhaul — needs owner go/no-go

The page works functionally; the complaint set (six items, Feb 2026) is
cosmetic: built for data display, not social pull. Proposed direction (build in
legacy JS — `website/js/availability.js` is the live implementation per
`route-registry.js`): names instead of counts, progress ring to threshold,
today/tomorrow as hero, status-click micro-confirmation, "1 player missing"
nudge. Full diagnosis: `docs/research/BACKLOG_MASTER_2026-08-10.md` §1.5.

Verify:
```bash
grep -n "availability" website/js/route-registry.js | head -3  # legacy JS is live
```

### Upload Library "Share" opens the detail page — design decision

Not a bug: "Share" navigates to `#/uploads/{id}` (detail page with embedded
player + copy-link button). UX question: should it copy the link directly?

Verify:
```bash
grep -n "uploads/" website/js/uploads.js | head -3
```

### VM migration remainders — Low

| Item | Status | Verify |
|---|---|---|
| `http://www.slomix.fyi` bypasses Cloudflare (hits Samba directly) | Open — shut down Samba web or redirect | `curl -sI http://www.slomix.fyi \| head -3` |
| `slomix.fyi` apex has no A record | Open (re-verified 2026-08-11: `dig` returns nothing) | `dig +short slomix.fyi` → empty; `dig +short www.slomix.fyi` → Cloudflare IPs |
| `MPLCONFIGDIR` not in prod `.env` (`/opt/slomix/.config` read-only under systemd sandbox) | Open — add `MPLCONFIGDIR=/tmp/matplotlib_cache` | `ssh slomix-vm 'grep MPLCONFIGDIR /opt/slomix/.env'` |

Note: dual bot replies (Samba + VM answering `!ping`) are **intentional**
(dev + prod share the guild) — not an issue, recorded here so it stops being
rediscovered.

---

## Closure ledger — removed in the 2026-08-11 re-verification

Every row was verified against code/DB before removal. Do not re-open without
re-running the proof.

| Removed claim | Proof of closure (2026-08-11) |
|---|---|
| REL-01: "no v1.27.x release config — **blocks deploy**" | `scripts/release_configs/` contains `v1.27.0.sh` … `v1.30.1.sh`; the config-per-release requirement is now a CI contract for EVERY release (`tests/unit/test_release_config_contract.py`, enforced in `.github/workflows/tests.yml` — release PR #630 failed on exactly this until #635 added the config) |
| "Prod runs v1.25.0 (`b29977c0`), ~50 PR backlog" | Prod deployed to v1.30.0 on 2026-08-10 and to v1.30.1 on 2026-08-11 ~05:55 (`scripts/deploy_release.sh` + `v1.30.1.sh`); migration ledger 045-070 reconciled, `--validate` CLEAN |
| "Prometheus: code exists, `prometheus_client` not installed" | `prometheus-client==0.24.1` + `prometheus-fastapi-instrumentator==8.1.0` in `requirements.txt:26-27` AND `website/requirements.txt:22-23` |
| D2: "`proximity_shot_fired` not in the re-linker table list" | Present — `LINKAGE_INVENTORY_TABLES`, `bot/services/linkage_inventory_service.py:37` (coverage of OTHER tables is still open, see above) |
| W4: "browser errors land nowhere" | `website/js/error-bootstrap.js`, `website/js/error-reporting.js`, `website/backend/routers/client_error_router.py`, `website/frontend/src/lib/errorReporting.ts` |
| W5: "production builds have no source maps" | `website/frontend/vite.config.ts:39` → `sourcemap: 'hidden'` |
| W7: "there is no Playwright in the project" | `website/frontend/package.json`: `@playwright/test ^1.62.0` + `test:e2e` script |
| Webhook token live in the public repo | PR #634 (v1.7.2): `vps_scripts/stats_discord_webhook.lua` now carries `REPLACE_WITH_YOUR_WEBHOOK_URL`; token rotation remains owner-gated (git history) |
| KIS v2 residue (1,812 `kis-v2` rows) | Closed as **won't-fix by design**: 88 rows from gsid 127 (scope resolver rejects it) + 1,724 identity-orphans matching no gsid-stamped round — unattributable; revisit only if a session-level attribution source appears |
| Session scoring divergence (bot 2-4 vs BOX 3-7) | Resolved 2026-07-05; empirically 0/12 divergent sums |
| `guid_canonical` columns not in migrations | Resolved by migrations 035/036, verified |
| Feb-2026 audit deferral preamble (PRs #546-#549 "still open") | All merged; migrations 063/064/065 present in `migrations/` |
| Spawn reaction time inflated (2-6 s) | Fixed + deployed Feb 21, 2026 (tracker v4.2, `gamestate == 0` gating) |
| Greatshot "broken" | Upload flow fully wired: `initGreatshotModule()` binds the submit handler on `demo-upload-form` and calls `uploadDemo` (`website/js/greatshot.js`, re-verified 2026-08-11) |
| Demo upload "broken" | Same handler chain as Greatshot above — form binding + `uploadDemo` present in `website/js/greatshot.js` |
| Clickable cards / dropdown items unresponsive | Fixed in commit `9d45d3fc` (`event.stopPropagation()` for `[role="menu"]` items in `website/js/inline-actions.js`) |
| Sessions nav not highlighting | Fixed in commit `9d805940` (`'sessions'` added to `statsViews`, nav ID mapping corrected in `website/js/app.js`) |
| Upload "Watch" button dead | `openVideoPlayer` defined and exposed on `window` in `website/js/uploads.js` (re-verified 2026-08-11: definition + `window.openVideoPlayer =` export both present) |
| Upload "Download" streams instead of downloading | Download link uses `?force_download=true` + the `download` attribute in `website/js/uploads.js` (re-verified 2026-08-11); backend `inline` default is intentional for Watch's Range seeking |
| "Website Debugging Audit Results (Feb 20)" snapshot incl. `/api/proximity/reactions` prototype | Stale point-in-time report, not an issue list; `proximity_reaction_metric` now holds 116,854 rows |
| VM item "Prometheus monitoring" | Same as Prometheus row above |
| VM item "Samba bot duplication" | Intentional (dev + prod), recorded as a note above, not an issue |
