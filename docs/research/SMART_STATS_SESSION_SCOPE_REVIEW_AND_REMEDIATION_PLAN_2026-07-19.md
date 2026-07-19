# Smart Stats session-scope review and remediation plan

**Date:** 2026-07-19

**Status:** Investigation complete; implementation not started

**Audience:** Implementation agent, reviewer, and owner

**Code changes made during this investigation:** None

**Production sample:** `gaming_session_id=137`, spanning 2026-07-18 and 2026-07-19

---

## 1. Executive summary

The latest Smart Stats page is not showing one complete gaming session. It
uses a calendar `session_date` as its primary scope, while the rest of Slomix
defines a gaming session with `rounds.gaming_session_id`. The latest gaming
session crossed midnight, so Smart Stats split it into two independent date
fragments and automatically selected the small post-midnight fragment.

This is not primarily missing KIS ingestion. Production completeness checks
show that all kill outcomes have KIS rows inside each calendar-date fragment.
The defect is that the UI and most Story APIs ask for the wrong unit of data.

The defect is more serious than a wrong default selection:

1. Neither `2026-07-18` nor `2026-07-19` represents the full gaming session.
2. Different Smart Stats panels use different underlying date fields, so even
   panels requested with the same date can contain different rounds.
3. BOX Score resolves a date back to a `gaming_session_id` and therefore
   returns the full session, while KIS, narrative, moments, composite metrics,
   and most proximity-derived panels remain date fragments.
4. A single Smart Stats screen can therefore compare mutually incompatible
   populations and produce a wrong MVP/story.

The durable fix is to make `gaming_session_id` the canonical Smart Stats scope
and filter every source by the resolved set of canonical `rounds.id` values.
Do not fix this by blindly adding two calendar dates together.

---

## 2. Product terminology and invariant

Slomix already has the correct domain model:

- **Round:** one R1/R2 stats record (`rounds.id`).
- **Match/map play:** the relevant R1/R2 sequence for one played map instance.
- **Gaming session:** multiple matches grouped by
  `rounds.gaming_session_id`, including sessions that cross midnight.
- **Calendar date:** a storage/partition attribute. It is not a stable session
  identity.

The intended invariant is already documented in `docs/CLAUDE.md`:

> Session queries use `gaming_session_id`, not dates, and must be tested with
> midnight crossovers and multiple sessions on one day.

Smart Stats currently violates that invariant.

---

## 3. Conversation-derived report and production evidence

The owner reported two visible symptoms:

1. Smart Stats kill counts looked like only one or two rounds compared with
   normal Session Stats.
2. Changing the date manually appeared not to change ownator's displayed
   value; the reported value remained `16`.

### 3.1 Latest canonical gaming session

The production Sessions API reports the latest complete session as:

| Field | Value |
|---|---:|
| `gaming_session_id` | `137` |
| Start date | `2026-07-18` |
| Accepted rounds | `23` |
| Distinct map names | `6` |
| Players | `8` |
| Normal Session Stats kills | `1182` |

Session Stats is correctly grouped by `gaming_session_id` in
`website/backend/routers/sessions_router.py`. Its detail endpoint selects all
rounds with `WHERE r.gaming_session_id = $1`, so it survives midnight.

### 3.2 How Smart Stats split the same session

The production proximity scope and Story APIs split session 137 as follows:

| Smart Stats calendar scope | Proximity rounds | Scope description | KIS rows/kills |
|---|---:|---|---:|
| `2026-07-18` | `19` | Pre-midnight majority of session | `1039` |
| `2026-07-19` | `4` | Final `et_brewdog` fragment | `143` |
| **Combined** | **23** | Canonical session 137 | **1182** |

The default selector chooses the newest proximity date, `2026-07-19`, so the
initial Smart Stats view contains only `143 / 1182 = 12.1%` of the session's
kills and only six of eight players.

### 3.3 Completeness is good inside each wrong scope

Production diagnostics returned:

| Date | Kill outcomes | KIS rows | Completeness | Round linkage |
|---|---:|---:|---:|---:|
| `2026-07-18` | `1039` | `1039` | `1.0` | `1.0` |
| `2026-07-19` | `143` | `143` | `1.0` | `1.0` |

Therefore this incident is not explained by a partially filled
`storytelling_kill_impact` cache. The date caches are complete for the rows
assigned to them.

### 3.4 Per-player proof

KIS kills from both date fragments add up to normal Session Stats:

| Player | KIS 07-18 | KIS 07-19 | Full-session total |
|---|---:|---:|---:|
| SuperBoyy | 226 | 30 | 256 |
| ownator | 164 | 31 | 195 |
| qmr | 149 | 29 | 178 |
| wiseBoy | 154 | 17 | 171 |
| .olz | 142 | 23 | 165 |
| .lgz | 115 | 0 | 115 |
| KaNii | 81 | 13 | 94 |
| vid | 8 | 0 | 8 |

The scope split changes the visible result:

| Scope | First | Second |
|---|---|---|
| `2026-07-19` fragment | ownator: 83.7 KIS | SuperBoyy: 73.8 KIS |
| Full session 137 | SuperBoyy: 634.8 KIS | ownator: 503.0 KIS |

The default Smart Stats fragment therefore tells a materially different MVP
story from the complete gaming session.

### 3.5 Same date does not mean same rounds across sources

The production composite endpoint demonstrates a second boundary problem:

| Source/field | ownator 07-18 | ownator 07-19 | Combined |
|---|---:|---:|---:|
| KIS kill outcomes | 164 | 31 | 195 |
| PCS/composite kills | 159 | 36 | 195 |

Both sources reconcile over the complete gaming session, but five kills land
on opposite sides of the date boundary. PCS uses `round_date`; proximity/KIS
uses the proximity file's `session_date`. A date-scoped composite can therefore
mix a numerator and denominator that do not cover the same rounds even before
BOX Score is considered.

### 3.6 Status of the reported `16` value

The exact UI observation has not been reproduced from the production API:

- KIS returns ownator `kills=164` for `2026-07-18` and `kills=31` for
  `2026-07-19`.
- Composite returns `kills=159` and `kills=36` respectively.
- The production and repository legacy `story.js` both bind the selector's
  `onchange` to a fresh, date-specific request.
- React Query keys also include `sessionDate`.
- The server HTTP cache key includes the sorted query string.

However, `16` occurs in two relevant production values:

1. ownator has `push_kills=16` in the `2026-07-18` KIS card.
2. ownator has `kills=16` in the first per-round PWC row on
   `etl_adlernest` R1.

This makes a mislabeled/misread submetric or panel-specific display plausible,
but it must not be dismissed. The implementation must add an end-to-end UI
test that changes the selected session and proves the hero total and ownator's
main KIS `Kills` field both change. Obtain a screenshot or exact panel name
from the owner if the value remains reproducible.

---

## 4. Findings

### SS-001 - HIGH: Smart Stats uses a calendar date as a gaming-session ID

**Evidence**

- Production legacy selector: `website/js/story.js` stores only
  `storyState.sessionDate` and loads `/proximity/scopes`.
- Staged React selector: `website/frontend/src/pages/Story.tsx` stores only
  `sessionDate` and also loads `/proximity/scopes`.
- `/proximity/scopes` groups `combat_engagement` by `session_date` in
  `website/backend/routers/proximity_dashboard.py`.
- Smart Stats API calls in both frontends send `session_date`.

**Impact**

- Every midnight-spanning gaming session is split.
- The newest post-midnight fragment wins auto-selection even when it contains
  only a small tail of the real session.
- A date containing multiple independent gaming sessions is also ambiguous.

### SS-002 - HIGH: Panels on one screen use incompatible scopes

Most storytelling services contain `WHERE session_date = $1`. In contrast,
BOX Score does:

```sql
SELECT gaming_session_id
FROM rounds
WHERE round_date = $1
LIMIT 1
```

and then computes the whole gaming session. Thus a page selected as
`2026-07-19` can combine a full BOX Score for session 137 with four-round KIS,
narrative, composite, and proximity fragments.

### SS-003 - HIGH: Date-to-session resolution is ambiguous and nondeterministic

`LIMIT 1` without an ordering or uniqueness assertion is not a valid resolver.
One calendar date may contain more than one `gaming_session_id`, and one gaming
session may contain more than one date. A date and a gaming session therefore
have a many-to-many-like relationship at the API boundary even if individual
rounds have exactly one of each.

### SS-004 - HIGH: Date fields differ between canonical and proximity sources

PCS and proximity rows can put the same logical round on different calendar
dates around midnight. Joining date-scoped aggregates by player silently mixes
different denominators. The ownator `159/36` versus `164/31` production split
is a direct example.

### SS-005 - MEDIUM: Production and staged Story frontends can drift

`website/frontend/src/runtime/catalog.ts` marks `story` as legacy in
production, while a full React Story implementation also exists. A fix made
only in React will not fix production; a fix made only in legacy JS will be
lost when the React route is promoted. Both implementations need the same
contract and regression tests.

### SS-006 - MEDIUM: No cross-panel midnight-session regression test

There are tests for midnight-safe SessionDataService behavior and for KIS
cache invalidation across all touched dates. There is no test proving that all
Smart Stats panels use one canonical scope or that changing the selector
changes rendered player values.

### SS-007 - MEDIUM, separate program: spawn timing is a universal uplift

Lua records a spawn timing for every eligible kill:

```lua
score = time_to_next / interval
```

KIS applies:

```python
spawn_mult = 1.0 + best_score
```

For a valid interval, modulo arithmetic makes the score effectively greater
than zero and at most one. Almost every linked kill therefore receives a
multiplier above `1.0`, with a rough neutral expectation near `1.5`. This can
be intentional, but it is not a rare bonus and materially inflates absolute
KIS. It did not cause the missing-session symptom and must be calibrated in a
separate formula/version PR.

There is also a latent zero/null defect in
`website/backend/services/storytelling/loaders.py`:

```python
float(r[2] or 0.5)
```

A valid numeric zero becomes `0.5`. The null-safe form is:

```python
0.5 if r[2] is None else float(r[2])
```

### SS-008 - LOW: KIS version reporting has drifted

- `kis.py` stores `FORMULA_VERSION = "kis-v2"`.
- loader comments describe KIS v3 reinforcement tiers.
- `/storytelling/formula` returns `version: "1.0"`.

This does not explain the incomplete page, but it prevents reliable cache,
audit, and model-card interpretation after formula changes.

---

## 5. Required design: one canonical scope object

Introduce one request-scoped value object and require every Smart Stats service
to consume it. Do not pass a naked date into internal Story methods.

Illustrative shape:

```python
@dataclass(frozen=True)
class GamingSessionScope:
    gaming_session_id: int
    round_ids: tuple[int, ...]
    start_date: date
    end_date: date
    dates_touched: tuple[date, ...]
    accepted_round_count: int
    distinct_map_names: tuple[str, ...]
    scope_version: str = "gaming-session-v1"
```

The resolver should select canonical rounds once:

```sql
SELECT r.id,
       SUBSTRING(CAST(r.round_date AS TEXT), 1, 10) AS round_date,
       r.map_name,
       r.round_number,
       r.round_start_unix
FROM rounds r
WHERE r.gaming_session_id = $1
  AND r.round_number IN (1, 2)
  AND r.is_valid IS DISTINCT FROM FALSE
  AND (r.round_status IN ('completed', 'substitution')
       OR r.round_status IS NULL)
ORDER BY SUBSTRING(CAST(r.round_date AS TEXT), 1, 10),
         r.round_start_unix,
         r.id;
```

Use the repository's established completed/substitution and validity rules.
If another session surface intentionally uses a different gate, document and
test the difference rather than silently inheriting it.

Every response should include the same scope metadata:

```json
{
  "scope": {
    "kind": "gaming_session",
    "version": "gaming-session-v1",
    "gaming_session_id": 137,
    "start_date": "2026-07-18",
    "end_date": "2026-07-19",
    "accepted_round_count": 23,
    "round_ids": [/* optional for internal/diagnostic responses */],
    "coverage": {"linked": 23, "expected": 23, "ratio": 1.0}
  }
}
```

The UI should reject or visibly mark a response whose scope ID/version differs
from the currently selected scope. This prevents a future panel from silently
reintroducing date-scoped data.

---

## 6. Query strategy: use `round_id`, not date unions

The schema already supports the right fix:

- `player_comprehensive_stats.round_id` is mandatory and indexed.
- `proximity_kill_outcome.round_id` exists, is indexed, and links to `rounds`.
- Most proximity source tables already have indexed `round_id` columns.
- `storytelling_kill_impact` links to
  `proximity_kill_outcome` through `kill_outcome_id`.

Therefore, do not initially duplicate `gaming_session_id` into every telemetry
table. Resolve the session to round IDs once and query those IDs.

### 6.1 KIS leaderboard

Illustrative query:

```sql
SELECT ski.killer_guid,
       MAX(ski.killer_name) AS name,
       ROUND(SUM(ski.total_impact)::numeric, 1) AS total_kis,
       COUNT(*) AS kills
FROM storytelling_kill_impact ski
JOIN proximity_kill_outcome ko ON ko.id = ski.kill_outcome_id
JOIN rounds r ON r.id = ko.round_id
WHERE r.gaming_session_id = $1
GROUP BY ski.killer_guid
ORDER BY SUM(ski.total_impact) DESC;
```

Preserve the current context columns and archetype calculation; only replace
the scope predicate. For unlinked `ko.round_id IS NULL`, do not silently pull
rows in by date. Return explicit degraded coverage and provide a separately
reviewed relink/backfill path.

### 6.2 KIS computation/materialization

The existing materialized KIS rows can remain date-partitioned during the
transition. For an internal session-scoped compute:

1. Resolve session round IDs.
2. Find distinct proximity `session_date` values for kill outcomes belonging
   to those round IDs.
3. Warm/recompute each touched date using the existing serialized path.
4. Read the final leaderboard strictly through linked round IDs.

This avoids a risky immediate migration while producing a correct session
read. A later migration may add `round_id` directly to
`storytelling_kill_impact` for simpler queries, populated from
`kill_outcome_id`, but that is an optimization rather than a correctness
prerequisite.

### 6.3 Composite and PWC

Replace both:

```sql
WHERE pcs.round_date = $1
WHERE proximity_table.session_date = $1
```

with a common round-ID predicate. PCS can use `pcs.round_id`; proximity sources
can use their `round_id`; KIS uses the join above. This closes the observed
`159/36` versus `164/31` boundary mismatch.

### 6.4 Sources without a reliable round link

For each Story source, build a capability matrix before conversion:

| Source table | Has `round_id` | Latest-session link coverage | Action |
|---|---|---|---|
| `proximity_kill_outcome` | Yes | Verify 100% | Required for KIS |
| `player_comprehensive_stats` | Yes, required | Verify 100% | Canonical PCS source |
| spawn/crossfire/trade/player track | Usually yes | Measure separately | Degrade individual metric if incomplete |
| any legacy source without link | Unknown | Measure | Relink or withhold; no date fallback |

An endpoint may return partial metrics, but it must return `status=degraded`,
the missing source names, and per-source linked/expected counts. It must never
present a partial source as a neutral zero.

---

## 7. API and frontend contract

### 7.1 Session selector source

Smart Stats must stop using `/api/proximity/scopes` as its session selector.
Use the canonical `/api/sessions` source or add a thin
`/api/storytelling/scopes` endpoint built from `rounds.gaming_session_id` with
per-source coverage metadata.

Recommended option value and label:

```text
value: 137
label: Session 137 | 18-19 Jul | 23 rounds | 6 maps
```

Preserve map-play sequence separately from distinct map names so repeated maps
are not collapsed.

### 7.2 Endpoint migration

Add `gaming_session_id` to every Smart Stats endpoint:

- kill impact and kill details
- narrative and player narratives
- moments
- momentum and momentum-session
- gravity
- space-created
- enabler
- lurker profile
- useless-defense-deaths
- synergy
- win contribution
- BOX Score
- skill composite
- storytelling completeness diagnostic

During transition, accept exactly one of `gaming_session_id` or
`session_date`. Existing date callers may retain legacy behavior temporarily,
but responses must declare `scope.kind="calendar_date"` and a deprecation
marker. New Smart Stats clients must send only `gaming_session_id`.

Do not silently map an ambiguous date to the first session. A compatibility
resolver should return `409 Conflict` with candidate session IDs when a date
touches more than one gaming session.

### 7.3 Production legacy frontend

Production currently serves the legacy Story route. Update
`website/js/story.js` first:

- replace `storyState.sessionDate` with a canonical scope object or
  `gamingSessionId`;
- populate from canonical sessions;
- include `gaming_session_id` in every request;
- update deep links to `#/story/session/<id>`;
- keep old `#/story/date/<date>` links as a temporary redirect/resolution path;
- on selector change, clear all old panels before loading;
- apply one monotonically increasing request generation ID to every panel;
- discard any response whose returned scope ID differs from the selected ID.

The existing `storyLoadId` is a good basis for stale-response rejection, but
scope validation must be explicit.

### 7.4 Staged React frontend

Update `website/frontend/src/pages/Story.tsx`, API client types, and all Story
hooks in the same program. React Query keys should become:

```typescript
['story-kill-impact', gamingSessionId, 'gaming-session-v1']
```

All other Story keys follow the same pattern. This prevents the staged React
implementation from reintroducing the date bug when promoted.

### 7.5 Clarify the visible metrics

The player card must keep the labels visually bound to their values, especially
on mobile:

```text
164 Kills | 3 Carrier | 16 Push | 24 Crossfire
```

Add stable test IDs or semantic accessible labels such as
`ownator-kis-kills`, not position-only assertions. This is required to close
the unresolved report that `16` appeared to be ownator's total kills.

---

## 8. Recommended delivery plan

Do not bundle the scope conversion with KIS formula tuning. The following PRs
are independently reviewable and preserve backward compatibility.

### PR-A - Canonical Smart Stats scope contract

**Changes**

- Add `GamingSessionScope` and one resolver service.
- Add canonical Story scopes endpoint or extend `/api/sessions` with the
  required coverage metadata.
- Add common query parameter validation: exactly one of session ID/date.
- Fix BOX Score to take `gaming_session_id` directly.
- Add scope metadata to responses.

**Tests**

- session crossing midnight resolves all round IDs;
- two sessions on one date remain distinct;
- repeated maps remain separate map plays;
- invalid/unknown session ID is 404;
- ambiguous legacy date is 409, never `LIMIT 1`.

### PR-B - KIS and completeness conversion

**Changes**

- Session-scoped KIS compute/warm orchestration.
- KIS leaderboard/details filtered through
  `kill_outcome_id -> round_id -> gaming_session_id`.
- Gaming-session completeness diagnostic.
- Session-scoped cache keys and locks.
- Explicit degraded response for unlinked kill outcomes.

**Tests**

- the 19+4-round fixture returns all kills once;
- per-player KIS sums match canonical session stats;
- KIS MVP is computed over the complete session;
- cache cannot mix session IDs;
- an unlinked row is reported, not silently date-included.

### PR-C - Remaining panels and composite conversion

Convert narrative, moments, momentum, gravity, space, enabler, lurker,
synergy, PWC, composite, and any direct KIS readers to the common scope.

Every endpoint test must assert the same `gaming_session_id`, scope version,
and expected round count. Add a contract test that enumerates all Smart Stats
routes so a new date-only route cannot be added unnoticed.

### PR-D - Legacy and React UI conversion

**Changes**

- Canonical session selector in both frontends.
- New deep link.
- Visible date range and round/map count.
- Stale-response and scope-ID rejection.
- Accessible metric labels.

**Tests**

- DOM/unit tests for both frontends where available;
- browser E2E against a fixture API;
- selector change must update hero total and ownator's KIS kills;
- a deliberately delayed old response must not overwrite the new session;
- mobile screenshot verifies `Kills`, `Carrier`, `Push`, and `Crossfire` do not
  visually detach from their numbers.

### PR-E - Formula correctness and versioning (separate, non-blocking)

- Fix zero/null handling in the spawn loader.
- Unify formula version in storage, endpoint, registry, and documentation.
- Backtest current spawn multiplier distribution.
- If tuning is approved, create a new formula version and recompute in shadow.
- Do not rewrite historical KIS rows without owner-approved migration,
  comparison report, and rollback.

---

## 9. Regression fixture and acceptance matrix

Create a deterministic fixture modeled on production session 137:

- one `gaming_session_id`;
- 23 accepted rounds;
- dates `2026-07-18` and `2026-07-19`;
- repeated map instances;
- eight players;
- 1182 kill outcomes/KIS rows;
- one source assigns a boundary round to a different calendar date than
  another source, while both link to the same canonical round ID;
- at least one substitution/completed status case;
- a separate fixture with two gaming sessions on one date;
- a degraded fixture with one unlinked proximity source row.

### Must-pass results for production session 137

| Assertion | Expected |
|---|---:|
| Selected scope | `gaming_session_id=137` |
| Scope dates | `2026-07-18` through `2026-07-19` |
| Accepted rounds | `23` |
| Players represented in KIS | `8` |
| KIS kills | `1182` |
| ownator KIS kills | `195` |
| SuperBoyy KIS kills | `256` |
| KIS leader | SuperBoyy, approximately `634.8` |
| BOX scope | session 137 |
| Composite/PWC scope | session 137 round IDs |
| Cross-panel scope IDs | all identical |

Do not hardcode these production values into long-term generic unit tests
outside the explicit regression fixture. The reusable invariant is that every
panel consumes the same round-ID set and all source totals reconcile to that
set.

---

## 10. Observability and diagnostics

Add one session-scoped diagnostic response that reports:

- `gaming_session_id` and scope version;
- expected canonical round IDs/count;
- start/end dates;
- per-source linked round count;
- per-source unlinked row count;
- KIS outcomes versus materialized KIS rows;
- per-player PCS kills versus kill-outcome counts;
- list of panels that returned degraded data;
- formula version(s) involved.

Recommended invariant metrics/logs:

```text
smart_stats_scope_mismatch_total{panel=...}
smart_stats_unlinked_rows{source=...}
smart_stats_kis_completeness_ratio
smart_stats_selected_round_count
```

Log one structured line per page aggregate, not per row. Include the request
ID, gaming session ID, round count, and scope version. Never log secrets or
full player identifiers where short canonical GUIDs are sufficient.

---

## 11. Rollout and rollback

1. Ship additive session-scoped APIs while legacy date APIs continue working.
2. Run a read-only comparison over recent sessions, especially every session
   crossing midnight and every date with multiple gaming sessions.
3. Require zero duplicated/missing KIS rows and matching per-player totals for
   fully linked sessions.
4. Deploy the production legacy frontend using session IDs.
5. Monitor mismatch/degraded metrics for at least two real sessions.
6. Update the staged React frontend before promoting its Story route.
7. Deprecate date-only Story calls only after all known consumers, including
   bot digest/warm hooks and deep links, use the new contract.

Rollback is frontend-first: switch the selector back to the legacy date API
without removing the additive session endpoints. No destructive data migration
is required for the recommended first implementation.

---

## 12. Explicit non-solutions

Do not accept any of the following as closure:

- defaulting to `2026-07-18` instead of `2026-07-19`;
- summing all rows from two adjacent dates;
- resolving a date with `LIMIT 1`;
- fixing only BOX Score or only KIS;
- changing only the React Story page while production remains legacy;
- treating unlinked proximity rows as zero;
- tuning KIS multipliers before fixing the population/scope;
- clearing browser/Redis cache as the permanent fix.

These may change the visible symptom but preserve the underlying ambiguity.

---

## 13. Definition of done

The work is complete only when all of the following are true:

- Smart Stats selects a `gaming_session_id`, not a calendar date.
- Every Smart Stats panel returns and renders the same scope ID/version.
- Session 137 reconciles to 23 rounds, 1182 KIS kills, and eight players.
- Midnight-spanning and same-day-multiple-session tests are green.
- PCS and proximity metrics are filtered by the same canonical round IDs.
- BOX Score contains no date-based `LIMIT 1` resolver.
- Legacy production and staged React implementations both use the new API.
- A browser test proves selector changes alter hero and player-card values.
- The reported ownator `16` symptom is either reproduced and fixed or closed
  with screenshot-backed proof that it was the clearly labeled Push/per-round
  submetric.
- Per-source missing linkage is explicit and observable.
- Formula tuning/version cleanup is tracked separately and is not smuggled
  into the scope PRs.
- A final reviewer records change, test, and production evidence for every
  finding SS-001 through SS-008.

---

## 14. Delegation brief

Recommended first assignment:

> Implement PR-A only. Start by writing the midnight and ambiguous-date
> resolver tests. Introduce `GamingSessionScope`, add a canonical Story scopes
> endpoint, add optional `gaming_session_id` to BOX Score, and remove the
> nondeterministic date resolver from the new code path. Preserve legacy date
> behavior for existing clients. Do not change KIS formulas, production data,
> deploy scripts, or frontend behavior in this PR.

After PR-A is reviewed, PR-B can convert KIS and diagnostics. PR-C and PR-D may
then proceed in parallel only if both consume the merged scope contract.

Owner decisions recommended in advance:

1. Approve `gaming_session_id` as the only canonical Smart Stats identity.
2. Approve `409` for ambiguous legacy dates rather than guessing.
3. Approve degraded/withheld metrics when round linkage is incomplete rather
   than date fallback.
4. Keep spawn multiplier calibration in a separate, evidence-gated program.

---

## 15. Relevant code map

- `website/backend/routers/sessions_router.py`: canonical session list/detail.
- `website/backend/routers/proximity_dashboard.py`: current date-based scopes.
- `website/backend/routers/storytelling_router.py`: Story route parameters and
  BOX date resolver.
- `website/backend/routers/skill_router.py`: date-scoped composite query.
- `website/backend/services/storytelling/`: KIS, narrative, moments, momentum,
  advanced metrics, synergy, and PWC date predicates.
- `website/backend/services/storytelling/kis.py`: KIS computation and cache.
- `website/backend/services/storytelling/loaders.py`: spawn zero/null issue.
- `proximity/parser/parser.py`: existing canonical `round_id` linkage.
- `bot/services/voice_session_service.py`: KIS invalidation/warming for all
  dates touched by a gaming session.
- `website/js/story.js`: current production Smart Stats frontend.
- `website/frontend/src/pages/Story.tsx`: staged React Smart Stats frontend.
- `website/frontend/src/api/hooks.ts`: staged React cache keys.
- `website/backend/middleware/http_cache_middleware.py`: query-aware HTTP cache.
- `tests/unit/test_session_data_service.py`: existing midnight session test.
- `tests/unit/test_kis_cache_invalidation_hook.py`: existing all-dates KIS
  invalidation tests.

---

## 16. Follow-up audit: `/proximity/` dev versus production incident

### 16.1 Scope and safety

This follow-up was requested because the owner observed substantially more
problems on the local development `/proximity/` page than on production
(`slomix_vm` / `www.slomix.fyi`). The investigation was read-only:

- no application code was changed;
- neither the dev nor production web service was restarted;
- no database rows were changed;
- no dependency was installed or upgraded;
- the active Fable/Opus worktree was left untouched.

The observations below are a snapshot from 2026-07-19. Re-run the verification
matrix after the in-progress Proximity branches are merged because the local
checkout is intentionally moving while those agents work.

### 16.2 Executive verdict

The primary dev-only failure is not evidence that dev has worse Proximity
telemetry. It is a **mixed-revision runtime incident**:

1. `etlegacy-web.service` has kept one Uvicorn process alive since
   2026-07-07 22:17 CEST, with zero restarts.
2. Python backend routes imported by that process remain the July 7 versions.
3. FastAPI's `StaticFiles` mount reads frontend files from the mutable checkout
   on every request, so the browser receives much newer JavaScript.
4. Some request-time lazy imports also load newer Python modules from disk into
   the old process.
5. The resulting process is not one coherent commit: old route handlers, new
   service contracts, and new frontend calls execute together.

This explains both confirmed dev-only symptoms:

- `/api/proximity/quality` is requested by the current frontend but is absent
  from the July 7 router graph, so dev returns `404`.
- the old `prox-scores` handler expects `compute_prox_scores()` to return a
  list, while the newly loaded v2 service returns a dict. The old handler runs
  `results[:limit]` on that dict and returns `500` with
  `TypeError: unhashable type: 'slice'`.

Production is older but internally coherent: its public quality endpoint is
present and its v1 Prox score handler and v1 score service agree on the list
contract. That is why production appears healthier even though it has not yet
received the current Prox v2 work.

Do **not** restart the dev service immediately while the checkout is on an
in-progress feature branch. A restart would load whichever branch happens to
be checked out, and the service virtualenv is also behind the current manifest.
First finish/merge the active work, pin the intended revision, install the
correct web requirements, run fresh-process gates, and only then restart.

### 16.3 Reproduced HTTP matrix

All requests used the same session scope, `session_date=2026-07-18`, on
2026-07-19. These are direct API observations, not inferred browser symptoms.

| Endpoint | Local dev | Production | Interpretation |
|---|---:|---:|---|
| `/api/proximity/scopes?range_days=3` | `200` | `200` | Same session/map/round data |
| `/api/proximity/summary?session_date=2026-07-18` | `200` | `200` | Same aggregate values |
| `/api/proximity/quality?session_date=2026-07-18` | `404` | `200` | Dev route graph predates quality router |
| `/api/proximity/prox-scores?session_date=2026-07-18` | `500` | `200` | Dev mixed list/dict contract; prod coherent v1 |
| `/api/proximity/objective-pressure?...` | `404` | `404` | New code exists in checkout, deployed route absent in both runtimes |
| `/api/storytelling/best-lives?...` | `404` | `404` | Same deploy-contract gap; not dev-specific |

Representative data was not merely similar. The dev and production scope
responses both reported:

- 2026-07-19: 371 engagements, one map, four rounds;
- 2026-07-18: 2,837 engagements, six map names, 19 rounds;
- the same map names, round start/end times, and per-round engagement counts.

The dev and production summary responses also agreed on 2,837 engagements,
eight players, 19 sample rounds, 51.4% kill rate, 46.7% escape rate, the same
top duos, and the same v5 source counts.

This rejects the initial hypothesis that the visible dev breakage is caused by
a stale or smaller dev telemetry dataset.

### 16.4 Exact `prox-scores` failure mechanism

The July 7 handler contract was:

```python
results = await compute_prox_scores(...)
return {
    "player_count": len(results),
    "players": results[:limit],
}
```

The current v2 service contract is:

```python
return {
    "status": "ok" | "degraded",
    "formula_version": "prox-web-v2.0",
    "quality": {...},
    "players": [...],
}
```

The active router code object is old, but its request-local import resolves the
new `website.backend.services.prox_scoring` module. Consequently
`results[:limit]` is a dict slice lookup and Python raises exactly the observed
`TypeError: unhashable type: 'slice'`.

The journal traceback names current source text at line 718 because traceback
rendering reads the file presently on disk. The active code object retains its
old line table; the historical July 7 file shows line 718 was precisely
`"players": results[:limit]`. This is useful forensic evidence and also a
warning: traceback source can be misleading when files underneath a running
Python process are replaced.

The current coherent handler correctly does:

```python
result = await compute_prox_scores(...)
players = result.get("players", [])
quality = dict(result.get("quality", {}))
limited = players[:limit]
```

All 62 targeted current-code tests passed from the root test environment:

```text
tests/unit/test_prox_scoring_quality.py
tests/unit/test_prox_scoring_helpers.py
tests/unit/test_api_middleware.py

62 passed in 76.18s
```

That proves the checked-out code's unit contracts are internally consistent.
It does not prove that the long-running service or its separate virtualenv is
consistent.

### 16.5 Runtime and dependency drift

The dev systemd unit runs:

```text
WorkingDirectory=/home/samba/share/slomix_discord/website
ExecStart=.../website/venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000
Restart=always
```

It has no reload/watch mode and no explicit revision gate. Branch switches,
merges, and file replacements therefore change static assets but do not reload
already imported Python modules.

The service environment is also behind `website/requirements.txt`:

| Package | Active `website/venv` | Current manifest |
|---|---:|---:|
| FastAPI | `0.110.3` | `0.133.1` |
| Starlette | `0.37.2` | `0.52.1` |
| Uvicorn | `0.29.0` | `0.41.0` |
| asyncpg | `0.29.0` | `0.31.0` |
| prometheus-client | absent | `0.24.1` |
| prometheus-fastapi-instrumentator | absent | `7.1.0` |
| redis | absent | `7.2.1` |

`website/venv` also does not contain pytest, so the successful targeted tests
ran in the root `venv`. A runtime smoke test must therefore be executed with
the actual `website/venv` after its manifest is installed; unit success in the
root environment is not a substitute.

This dependency drift aligns with the already planned deploy fix that installs
`website/requirements.txt` into the web virtualenv. It should be treated as a
release prerequisite, not solved ad hoc during this incident.

### 16.6 Finding PX-DEV-001 - HIGH: mutable checkout plus long-lived process

**Impact**

- Backend and frontend contracts can differ even on one machine and one URL.
- Request-local imports can create an intra-Python-process hybrid, not merely a
  frontend/backend mismatch.
- Tracebacks may show source that the process is not actually executing.
- A feature can pass review and tests yet look broken only in dev.
- Restarting at the wrong moment can load an unmerged feature branch.

**Required correction**

Separate the runtime release from the collaborative mutable checkout. The
professional pattern is an immutable release directory (or image) per commit,
with one atomic `current` pointer and a controlled process restart:

```text
/opt/slomix/releases/<git-sha>/
/opt/slomix/current -> /opt/slomix/releases/<git-sha>/
```

The service must execute from `current`, not from the directory in which
agents switch branches. A deployment should install dependencies, validate the
route/schema contract, atomically switch `current`, restart, and verify the
reported revision. Rollback switches the pointer back and restarts.

For a true developer-only server, `uvicorn --reload` is acceptable when it is
bound to a dedicated dev checkout and port. It is not a replacement for the
immutable systemd release path.

### 16.7 Finding PX-DEV-002 - HIGH: no runtime revision handshake

The current health endpoint says only that the process and database answer. It
cannot reveal that the browser assets and backend come from different commits.

Add non-secret build metadata to both artifacts:

```python
@app.get("/api/build", include_in_schema=False)
async def build_info():
    return {
        "revision": settings.build_sha,
        "started_at": PROCESS_STARTED_AT,
        "api_contract": "proximity-v2",
        "schema_ledger": await current_schema_ledger(),
    }
```

The frontend build should embed its own revision/API contract and compare it
with `/api/build` once at bootstrap. In dev, a mismatch should show a clear
non-secret diagnostic and avoid loading known-incompatible panels. Production
monitoring should alert; the normal public UI need not expose repository or
infrastructure details beyond an opaque build ID.

Also emit `X-Slomix-Build` on API responses and record the build ID in
structured error logs. This turns the present forensic exercise into an
immediate, machine-checkable diagnosis.

### 16.8 Finding PX-DEV-003 - MEDIUM: frontend/API route drift is silently masked

The checked-out frontend calls routes that neither running environment
currently serves (`objective-pressure` and `best-lives`). Those enrichments
catch all failures and render nothing, so route drift can live unnoticed.

Add a real-stack contract test which:

1. imports a fresh `website.backend.main.app` in a subprocess;
2. extracts its OpenAPI/route set;
3. checks every statically declared frontend API path;
4. executes representative requests with a fake/test database;
5. fails CI when a non-feature-gated frontend call has no backend route.

Optional panels may remain optional at runtime, but optional must mean
"endpoint returned no usable data", not "frontend calls a route absent from
the release". Use an explicit capability manifest or feature flag for features
that intentionally ship frontend-first/backend-later.

### 16.9 Finding PX-DEV-004 - MEDIUM: `/proximity/` produces a request burst

The current legacy page starts two initial calls and then roughly 35 section
calls in one `Promise.allSettled`; the file contains 51 scoped Proximity fetch
sites when interactive/competitive follow-ups are included. The `loadId`
guard prevents stale results from rendering, but it does not cancel the stale
HTTP requests or database queries.

This is not the cause of the reproduced 404/500 failures, and one warm local
sample was fast (`summary` cache hit about 9 ms; `engagements` miss about
13 ms). It remains an avoidable load and tail-latency risk, especially on a
single-worker service with a finite database pool.

There is an existing `/api/proximity/dashboard` aggregator, but it is **not a
drop-in fix**:

- the frontend does not use it;
- it covers only the older section catalog;
- it still fans queries out concurrently on the server;
- its `prox_scores` dispatcher currently forwards `range_days` but not the
  selected session/map/round scope;
- it does not provide the new quality/competitive/objective sections;
- one large response makes independent cache invalidation and partial retry
  more difficult.

Recommended evolution:

1. Load only scope, summary, quality, and above-the-fold panels initially.
2. Lazy-load below-the-fold groups with an intersection observer.
3. Limit client concurrency to a small measured value (for example 4-6), not
   an unbounded burst.
4. Use `AbortController` when scope changes so stale requests are cancelled.
5. Build a versioned BFF/dashboard contract around a canonical scope object and
   shared prefetched data, not a thin wrapper that calls 29 router functions.
6. Keep groups independently cacheable and report per-section status/timing.
7. Load-test cold and warm paths against a production-like database before
   choosing concurrency and cache TTLs.

Do this as a separate performance PR after runtime coherence is fixed. Changing
transport shape while diagnosing a mixed process would hide evidence and make
rollback harder.

### 16.10 Finding PX-DATA-001 - MEDIUM: production quality is still partial

The production quality endpoint works, but for `2026-07-18` it reports
`overall_status="partial"`:

| Signal | Observed value |
|---|---:|
| Core/source tables | present and ready |
| Round-correlation rows | 10 |
| Complete correlation rows | 9 |
| Missing proximity flag rows | 1 |
| Average completeness | 89% |
| Global unlinked Lua rows | 28 / 789 (3.55%) |
| Global `match_id` mismatch rows | 752 |
| Global duplicate Lua round links | 74 |
| Global correlation round mismatch rows | 1,022 |

The last four linkage values are explicitly global even in a session-scoped
quality response. They must not be presented as proof that all those anomalies
belong to the 2026-07-18 session. The session-specific fact is narrower: one of
ten correlation records lacks a proximity flag and overall correlation
completeness is 89%.

This is real data-trust debt, but it is separate from the dev 404/500 incident.
Before changing formulas or backfilling anything:

1. make linkage quality scope-aware by canonical round IDs;
2. separate historical/global debt from the selected session badge;
3. list exact affected round IDs for a scoped failure;
4. run guarded dry-run repair diagnostics;
5. require owner approval for any relink/backfill mutation;
6. re-run the quality endpoint and Smart Stats reconciliation afterward.

This should share the canonical `GamingSessionScope` introduced by the main
Smart Stats plan rather than invent another date-based scope.

### 16.11 Rejected explanations

The current evidence does **not** support these as the main dev-only cause:

- **"Dev has fewer/newer Proximity rows."** The sampled scope and summary
  payloads match production.
- **"The local database is simply slower."** Sampled local API calls were
  faster than public production calls; this was not a full load benchmark, but
  it rules out an obvious single-request slowdown.
- **"Browser cache alone is stale."** The backend itself returns the confirmed
  404 and 500 responses.
- **"Prox v2 code is inherently broken."** Its targeted current-code tests are
  green; the running process is executing a mixed v1/v2 contract.
- **"Restart now and everything is done."** The checkout is on an active
  feature branch and `website/venv` does not match the manifest. Restart is one
  step in a controlled recovery, not the whole fix.

### 16.12 Owner-gated recovery runbook after Fable/Opus finish

Do not perform this while another agent is still switching branches or editing
the release surface.

1. Confirm all intended PRs are merged and the checkout is clean on the exact
   target `main` commit.
2. Record `git rev-parse HEAD`, active schema ledger, dependency lock/manifest
   hashes, and current service start time.
3. Install `website/requirements.txt` into the actual web virtualenv using the
   reviewed deploy path; run `pip check`.
4. In a fresh subprocess using `website/venv`, import the real app and assert
   that the route set includes at least quality, prox-scores,
   objective-pressure, and best-lives.
5. Run the target Proximity, middleware, security-stack, and migration tests.
6. Start an ephemeral fresh-process smoke instance on a private port and query
   the representative matrix. This proves the target revision before touching
   the existing service.
7. Restart `etlegacy-web.service` through the controlled deploy/recovery path.
8. Assert the new process start time and reported build SHA.
9. Verify `quality=200`, `prox-scores=200` with the intended formula/quality
   contract, and no new traceback in the journal.
10. Verify that optional frontend routes either return `200` or are disabled by
    the same release capability manifest.
11. Compare dev and production scope/summary totals again.
12. Keep production deployment owner-gated and separate; do not assume a dev
    restart deploys or validates `slomix_vm`.

If any pre-restart smoke fails, stop before restarting. If the post-restart
matrix fails, roll back to the recorded coherent release rather than editing
files under the live process.

### 16.13 Proposed delivery split

Keep these changes separate from the Smart Stats formula/scope implementation:

| Work item | Scope | Dependency |
|---|---|---|
| `PX-R0` | Controlled dev recovery on merged revision | Owner operation after current PRs |
| `PX-R1` | Immutable release path, build handshake, fresh-process gates | Deploy/migration PR closure |
| `PX-R2` | Frontend/backend route manifest contract test | Stable API route catalog |
| `PX-R3` | Lazy grouped loading, cancellation, measured concurrency | `PX-R0` and baseline timings |
| `PX-R4` | Scope-aware linkage quality and guarded repair plan | Smart Stats `GamingSessionScope` |

`PX-R0` is operational recovery, not a code-feature PR. `PX-R1` and `PX-R2`
should be prioritized before performance work because they prevent recurrence
and make subsequent measurements trustworthy.

### 16.14 Definition of done for the Proximity follow-up

- Dev serves frontend and backend from one recorded revision.
- `website/venv` matches the reviewed web dependency manifest and passes
  `pip check`.
- A fresh-process smoke runs before every service switch.
- `/api/build` (or equivalent) exposes a non-secret build/API contract ID.
- Frontend/API contract mismatch is detectable automatically.
- The representative route matrix returns expected statuses with no journal
  traceback.
- `prox-scores` returns the intended v2 quality contract after its PR is merged.
- Optional frontend panels never call unavailable routes without an explicit
  capability gate.
- Cold/warm request counts and latency are measured before and after loading
  changes.
- Proximity linkage warnings are scoped to canonical round IDs, with global
  historical debt labeled separately.
- No repair/backfill or production deployment occurs without owner approval.

## 17. Additional Proximity/system review sweep (2026-07-19)

This section records a second read-only sweep requested after the dev-versus-
production incident review. No application code, schema, service, database, or
deployment state was changed while collecting this evidence. The findings are
ordered by risk, not by proposed implementation order.

### 17.1 Findings at a glance

| ID | Severity | Finding | Current effect |
|---|---|---|---|
| `PX-SCOPE-001` | **HIGH** | The exact-round UI sends scope keys which at least six loaded endpoints do not accept | Several panels can display broad results under an exact-round caption |
| `PX-DEV-005` | **HIGH** | Player radar is a second confirmed mixed-revision contract failure | Dev returns `500`; production returns `200` |
| `PX-DB-001` | **HIGH** | The web service and migration runner resolve different environment files/DB targets | A fresh current process can hit schema missing migrations 061/062 even if the other DB validates |
| `PX-OPS-001` | **HIGH** | The prod-to-local sync script currently derives its destructive target from an environment which points off-host | It must not be run until target identity is hardened |
| `PX-IP-001` | **HIGH / OWNER POLICY** | Public formula endpoints expose exact proprietary weights, thresholds, and multipliers | Competitors can reproduce much of the scoring logic without reading the repository |
| `PX-SCOPE-002` | **MEDIUM** | Weapon accuracy combines differently scoped aggregates in one response | Leaderboard and weapon breakdown are not comparable |
| `PX-FE-001` | **MEDIUM** | The two frontend route catalogs disagree and the modern page lacks legacy parity | A route flip can silently remove quality/error semantics |
| `PX-SEC-001` | **MEDIUM** | Production Prometheus metrics are publicly readable | Runtime, route inventory, traffic, and process telemetry are exposed |
| `PX-CONTRACT-001` | **LOW-MEDIUM** | Unknown query parameters are silently accepted and separately cached | Contract mistakes look successful and waste cache entries |
| `PX-ENV-001` | **LOW** | `website/.env` has mixed CRLF/LF terminators | Python loads it, but a normal shell `source` does not |

`PX-IP-001` is intentionally classified separately from an exploit. The API is
behaving as implemented, but the implementation conflicts with the owner's
stated goal of protecting advanced formulas developed over the last year.

### 17.2 `PX-SCOPE-001` - exact-round selection is not an end-to-end contract

#### User-visible promise

The active legacy page builds every request through `scopedUrl()` and includes:

```text
session_date
map_name
round_number
round_start_unix
```

On initial load it selects the newest date, last map, and last round, including
the round start timestamp. The page then presents the selected values as the
scope of the dashboard. Relevant client locations are:

- `website/js/proximity.js:224-245` - canonical query construction;
- `website/js/proximity.js:1790-1830` - automatic exact-round selection;
- `website/js/proximity.js:1935-1953` - the affected panels are loaded with
  `scopedUrl()`.

#### Backend reality

At least these six endpoints loaded by the page cannot consume the full scope:

| Endpoint | Accepted selection keys | Silently ignored selection keys |
|---|---|---|
| `kill-outcomes/player-stats` | date, map | round number, round start |
| `hit-regions/headshot-rates` | date, map | round number, round start |
| `movement-stats` | date, map | round number, round start |
| `support-summary` | date, map | round number, round start |
| `combat-position-stats` | date, map | round number, round start |
| `weapon-accuracy` | map, rolling range | date, round number, round start |

The signatures are visible at:

- `website/backend/routers/proximity_dashboard.py:632-644`;
- `website/backend/routers/proximity_positions.py:405-417` and `1062-1075`;
- `website/backend/routers/proximity_support.py:16-29` and `87-100`;
- `website/backend/routers/proximity_scoring.py:752-781`.

FastAPI ignores query parameters which are not declared by the handler. The
responses therefore look successful instead of exposing the contract error.
For example, the inspected player-outcomes response explicitly reported
`round_number: null` and `round_start_unix: null` even though both were sent.

#### Direct A/B reproduction

Two distinct `etl_adlernest` round-1 instances from the same date were queried:

```text
scope A round_start_unix = 1784402640
scope B round_start_unix = 1784404112
```

The six endpoints above returned byte-identical bodies for A and B. Their
SHA-256 values were identical per endpoint:

```text
combat-position-stats          93e9609285c9b117...
hit-regions/headshot-rates     3ece40ee3f3f8925...
kill-outcomes/player-stats     678dcfde7df50433...
movement-stats                 bf0ab8621ced1444...
support-summary                0248fa02c8d1c948...
weapon-accuracy                5b83766790af142e...
```

The control endpoint, `/proximity/engagements`, changed between the two round
starts (`9c0d...` versus `0302...`). This proves the experiment can distinguish
the two scopes and is not merely comparing duplicate requests. A second check
showed that weapon accuracy was also byte-identical when only
`session_date=2026-07-18` versus `2026-07-19` changed.

#### Why this matters

This produces a mixed-scope dashboard: some panels are exact-round, some are
date/map aggregates, and weapon accuracy can be a rolling window. The title and
filters nevertheless make them look directly comparable. It is a plausible
second instance of the same trust failure observed in Smart Stats: changing a
visible selector does not necessarily change the displayed statistic.

The cache makes diagnosis harder. Its key contains the complete URL query, so
two unsupported round-start values create two cache entries for the same broad
response. The UI sees distinct requests and successful `200` responses while
the backend does identical work/data selection.

#### Required remediation contract

Do not fix the six handlers independently with six slightly different date
predicates. Introduce one strict structured scope, ideally sharing the canonical
round/session identity from this document's Smart Stats plan:

```python
class ProximityScopeQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_date: date | None = None
    map_name: str | None = None
    round_number: int | None = None
    round_start_unix: int | None = None
    gaming_session_id: str | None = None

    @model_validator(mode="after")
    def validate_identity(self):
        # Exact-round requests need the disambiguating round key. Ultimately
        # resolve it once to a canonical round ID rather than repeating SQL.
        return self
```

Each endpoint must then do one of two explicit things:

1. honor the resolved canonical scope completely; or
2. declare a coarser `scope_granularity` in its response and let the UI label it
   as date/map/range data instead of exact-round data.

Unknown or unsupported selection keys should fail with `422/400`, not be
silently ignored. A frontend capability map is acceptable only as an additional
guard; the backend remains authoritative.

Minimum contract test:

```python
async def test_exact_round_scope_disambiguates_repeated_map(client):
    a = await client.get(PATH, params={**base, "round_start_unix": START_A})
    b = await client.get(PATH, params={**base, "round_start_unix": START_B})
    assert a.status_code == b.status_code == 200
    assert a.json()["actual_scope"]["round_id"] != b.json()["actual_scope"]["round_id"]
    assert a.json()["data"] != b.json()["data"]
```

The test should be parametrized over every panel advertised as exact-round. A
separate test should assert rejection for unsupported query parameters.

### 17.3 `PX-SCOPE-002` - weapon accuracy has two scopes inside one payload

The main weapon-accuracy query applies:

- `player_guid` when present;
- `map_name` when present;
- `range_days` through `session_date`/`created_at`.

Its `weapon_breakdown` query applies only `player_guid`:

```sql
FROM proximity_weapon_accuracy
WHERE player_guid = $1 AND shots_fired > 0
GROUP BY weapon_id
```

See `website/backend/routers/proximity_scoring.py:763-831`. A caller can
therefore receive a 30-day, one-map leaderboard beside the selected player's
all-time, all-map weapon breakdown. This is not a missing UI label only; it is
an internally inconsistent API response.

The fix should build both queries from the same resolved scope object and return
that `actual_scope` once. Add tests for range, map, date, and exact-round parity
between `leaders` and `weapon_breakdown`. No endpoint-specific SQL copy should
be allowed to omit a scope predicate silently.

### 17.4 `PX-DEV-005` - player radar confirms mixed-revision failure twice

The earlier incident section proved that dev's old prox-scores route slices the
new dict result and raises `TypeError`. The player radar independently fails at
the inverse consumer assumption:

```text
dev  /api/proximity/player/<guid>/radar?range_days=90 -> 500
prod /api/proximity/player/<guid>/radar?range_days=90 -> 200
```

The dev journal traceback ends at the running July-7 handler's
`prox_scores[0]`, raising `KeyError: 0`. That handler imports
`compute_prox_scores` inside the request, so it receives the current checkout's
v2 dict while the long-lived route function still expects the old list.

Current coherent source at `website/backend/routers/proximity_player.py:178-204`
already consumes `prox_result.get("players", [])`; the issue is the live process,
not a request to re-implement that current fix.

There is also an unusually strong version fingerprint on dev:

```text
/api/proximity/prox-scores              -> old handler, 500
/api/proximity/prox-scores/formula      -> request-local new service, version 2.0
/api/proximity/player/<guid>/radar      -> old handler + new service, 500
```

Production returns the coherent older v1 API and formula version 1.0. This is
direct evidence that one dev process exposes two code generations at once.

Add the radar path to the fresh-process and post-restart matrix. The build
handshake proposed in Section 16 must cover both route registration revision
and lazy service imports; checking only static asset hashes is insufficient.

### 17.5 `PX-DB-001` - migration validation is aimed at a different DB

The local web process and the default migration runner do not load the same
environment source:

- `website/backend/main.py:33-37` loads `website/.env` first;
- `scripts/apply_migrations.py:46-50` loads only repository-root `.env`;
- the two files currently identify different database hosts/roles;
- `scripts/run_validation_bundle_from_env.sh:43-54` loads root first and website
  second, creating a third resolution rule.

Read-only inspection of the database used by the local website found:

- ledger latest entry: migration `052`;
- none of the inspected migration-061 prediction columns;
- none of migration-062's `tracker_version`, `round_key`, or `capabilities`
  columns in `proximity_processed_files`.

Current prediction code queries/inserts 061-era fields. Consequently, validating
the root-environment DB does not prove that a fresh local website process can
serve the current checkout. The failure may be latent until a prediction route
or workflow is exercised; this is not a claim that app import must fail.

Required operational rule:

> Migration validation must run against the exact DSN and role that the service
> about to start will use.

The preflight should emit a non-secret fingerprint such as:

```json
{
  "environment": "dev-local",
  "database_name": "etlegacy",
  "database_role": "website_app",
  "host_fingerprint": "sha256:...",
  "ledger_max": "062_...sql",
  "schema_contract": "slomix-062"
}
```

Do not expose the raw host, password, or full DSN through a public build route.
The deploy script should pass one explicit environment file/DSN to the runner,
then pass the same resolved configuration to the service smoke process. Add an
integration test that intentionally points the runner and app at two databases
and asserts the mismatch aborts the switch.

This finding strengthens, rather than replaces, the existing owner-gated
`OPS-MIG` work. Migrations/backfills remain owner operations.

### 17.6 `PX-OPS-001` - prod-to-local sync target is not safely identified

`scripts/sync_local_from_prod.sh:31-115` calls the repository-root `.env` its
local target source. In the inspected checkout that environment identifies the
off-host database also used for `slomix_vm` work. Later, the script can rename
the selected database, create a replacement, and restore a production dump
(`:188-225`). It has useful active-connection and confirmation gates, but those
do not establish that the target is actually local or distinct from the source.

**Do not run this script in the current configuration.** This is a safety
finding only; it was not executed.

A hardened replacement should require an explicit `LOCAL_DATABASE_URL` (or a
reviewed local env path) and prove target identity before any dump/rename:

```bash
target_fingerprint="$(${PSQL[@]} -Atc \
  "SELECT current_database(), current_user, inet_server_addr(),
          current_setting('slomix.environment', true)")"

is_loopback "$DB_HOST" || die "sync target is not local"
[[ "$target_fingerprint" != "$source_fingerprint" ]] || \
  die "source and destination resolve to the same database"
[[ "$environment_marker" == "dev-local" ]] || \
  die "missing dev-local database sentinel"
```

For a deliberately remote staging target, require a one-use exact fingerprint
approval, not a generic `FORCE=1`. The final confirmation should require typing
both the target host alias and database name. Recovery instructions must be
generated with the same safe env parser the script uses.

### 17.7 `PX-IP-001` - exact scoring formulas are public by design

The following production calls were anonymously accessible during this review:

| Endpoint | HTTP | Public detail observed |
|---|---:|---|
| `/api/proximity/prox-scores/formula` | 200 | 18 metric weights, invert flags, category weights, minimum engagements, version |
| `/api/skill/formula` | 200 | ET Rating constant, all positive/negative metric weights, sources, normalization, range |
| `/api/storytelling/formula` | 200 | KIS carrier/push/crossfire/spawn/outcome/class/distance/clutch/reinforcement multipliers and soft cap |
| `/api/formulas` | 401 | Correctly protected aggregate/admin registry |

For concrete scale, the public skill response was 2,122 bytes and the KIS
response 2,845 bytes. They contain the numeric recipe, not merely human-readable
feature descriptions. The prox endpoint's docstring explicitly says this is
for transparency (`website/backend/routers/proximity_scoring.py:746-749`).

This requires an explicit owner decision. Three coherent policies exist:

1. **Transparent/open:** keep exact formulas public and compete through data,
   community, execution, brand, and iteration speed.
2. **Hybrid (recommended for the stated owner goal):** publish a model card,
   metric meanings, provenance, version, confidence, limitations, and broad
   category contribution; keep exact coefficients/thresholds in an
   admin/internal manifest.
3. **Closed:** expose only results and a version. This maximizes secrecy but
   reduces explainability and makes trust/debugging harder.

Suggested public contract under the hybrid policy:

```json
{
  "version": "kis-2026-07",
  "purpose": "context-sensitive kill impact",
  "factor_groups": ["objective", "teamplay", "outcome", "timing"],
  "inputs": [{"name": "spawn timing", "direction": "higher impact"}],
  "limitations": ["requires complete Proximity telemetry"],
  "calibration": {"population": "competitive ET sessions", "status": "shadow"}
}
```

The exact manifest can remain behind the same admin dependency used by
`/api/formulas`. Do not move coefficients into frontend JavaScript and call that
private: anything shipped to a browser is public. Also audit public docs,
OpenAPI, source maps/static bundles, repository visibility, package artifacts,
and Git history. Removing an endpoint cannot make already-public Git history
secret, so repository/license history must be handled as a separate owner/legal
workstream.

Smart Stats currently renders formula detail as a product feature ("How is this
calculated?"). Preserve useful explanation, but derive it from the safe public
model card if hybrid policy is chosen.

### 17.8 `PX-FE-001` - two route catalogs and incomplete modern parity

There are two conflicting declarations:

- `website/frontend/src/runtime/catalog.ts:27` marks Proximity `modern`;
- `website/js/route-registry.js:166-173` marks it `legacy`.

The latter is the actual application routing truth today, while the TypeScript
catalog is used by the preview entrypoint. This may be intentional migration
scaffolding, but its name and shape make it easy for tests/reviewers to treat it
as the live catalog.

The modern `Proximity.tsx` is not yet a behaviorally equivalent replacement:

- no equivalent quality panel/contract was found;
- the Prox Scores panel uses a global rolling range instead of page exact scope;
- an empty degraded v2 score response can make the panel disappear rather than
  display telemetry degradation;
- several raw `fetch(...).then(r => r.json())` calls do not check `r.ok`, so an
  HTTP error can become blank/partial data instead of a query error;
- its default scope behavior differs from the legacy exact-latest-round choice.

Do not solve the catalog contradiction by simply flipping the live route to
modern. First create one authoritative route manifest plus a parity matrix:

| Capability | Legacy | Modern | Required before promotion |
|---|---:|---:|---|
| exact-round scope | yes | partial | full canonical scope |
| quality/degraded state | visible | missing/partial | visible, tested |
| all current panels | yes | partial | deliberate keep/drop decision |
| failed-request rendering | explicit in loader | inconsistent | `response.ok` gate |
| request fanout/cancellation | high/no grouping | React Query partial | measured budget |

Promotion tests must execute the real `app.js` router, not only the preview
catalog.

### 17.9 `PX-SEC-001` - production metrics are public

Anonymous `GET https://www.slomix.fyi/metrics` returned `200` and approximately
199 KB of Prometheus text. The sample exposed:

- exact Python runtime version;
- process start time, CPU, memory, and file descriptor counts;
- cache hit/miss counters;
- per-template route, method, status, and request counts;
- a broad inventory of auth, admin-like, story, and Proximity surfaces.

The inspection found no password, token, raw player GUID, client IP, filesystem
path, or route parameter value. Route labels were templated. The issue is
operational reconnaissance and privacy of usage/runtime telemetry, not a
confirmed credential leak.

Prometheus is configured to scrape the service internally, so the public
reverse proxy does not need to expose this path. Recommended boundary:

```nginx
location = /metrics {
    allow <internal-prometheus-network>;
    deny all;
    proxy_pass http://api_upstream;
}
```

Equivalent mTLS or an internal-only listener is also acceptable. Add two
smokes: internal scrape returns `200`; public scrape returns `403/404`. Preserve
internal monitoring while closing the Internet route.

Public `/openapi.json` also reveals the route inventory. That is common and is
not classified here as a vulnerability by itself, but docs/OpenAPI exposure
should be included in the same deliberate public-surface policy review.

### 17.10 `PX-CONTRACT-001` - unknown params look valid and pollute cache

The legacy page sends `min_engagements=30` to `/proximity/prox-scores`, but the
current handler does not declare that parameter. FastAPI silently ignores it;
the service's configured minimum remains authoritative. This parameter is dead
contract noise, not proof that the score currently uses 30.

Together with the ignored scope keys, this demonstrates a general boundary
problem: typoed or obsolete client parameters return `200`. Because the cache
keys by full query string, meaningless variations can fragment the cache.

Remediation choices:

- remove dead client parameters;
- use strict query models with `extra="forbid"` for owned internal APIs;
- canonicalize validated query parameters before caching;
- add generated client/route contract checks so a client cannot send a field
  absent from OpenAPI without a failing test.

Do not expose arbitrary client-controlled minimums unless the product truly
supports them. If supported, clamp them, return the effective value, and keep
eligibility/calibration semantics server-owned.

### 17.11 `PX-ENV-001` - local website env is unsafe to shell-source

`website/.env` currently contains mixed CRLF and LF terminators. Python dotenv
parses it, and reviewed helper scripts strip carriage returns, so this does not
explain the running Proximity failures. A normal shell command such as:

```bash
set -a; source website/.env; set +a
```

produced a stray carriage-return command error and values such as
`localhost\r`. This can misdirect ad-hoc migration or diagnostic commands.

Runbooks should use one checked env parser rather than shell `source`. Add a
preflight which rejects CRLF/mixed terminators and prints only non-secret target
identity. Normalizing the ignored local file is an owner operation and was not
performed in this review.

### 17.12 Rejected or bounded conclusions

The evidence does **not** justify these broader claims:

- The six identical scope responses do not prove their underlying calculations
  are wrong for date/map aggregation; they prove the exact-round UI contract is
  false for those panels.
- The player radar's v2 integration is not missing from current source; the
  running process is stale and mixed.
- Missing 061/062 columns do not prove startup import fails. They establish
  latent route/workflow failures when current SQL is exercised.
- Public metrics did not reveal a credential in the sampled response.
- A public formula is not an authentication bypass. It is an intentional
  transparency surface that needs a new owner policy if secrecy is desired.
- The TypeScript route catalog is not currently the production router. It is a
  governance/parity risk, not proof that users are already served the React
  page.
- Cache counters from one public scrape are insufficient to claim that cache
  performance is generally poor.

### 17.13 Updated delivery order and ownership

These findings should not be injected into Fable/Opus branches already in
flight. Re-review after their merges, because line numbers and some current-code
gaps may change.

| Wave | Work | Owner gate/dependency |
|---|---|---|
| `PX-S0` | Decide formula visibility and public metrics policy | Owner before API behavior changes |
| `PX-S1` | Harden/disable unsafe DB sync target resolution | Before any prod-to-local refresh |
| `PX-S2` | Unify service/migration DB identity and migrate exact target | Owner-gated migration/release |
| `PX-S3` | Controlled fresh-process dev recovery, including radar smoke | After active PR merges and dependency install |
| `PX-S4` | Canonical strict scope across all Proximity handlers | Share Smart Stats scope model |
| `PX-S5` | Fix weapon internal scope and add scope A/B matrix | With `PX-S4` |
| `PX-S6` | Single frontend route catalog and modern parity gate | After backend contract stabilizes |
| `PX-S7` | Restrict metrics publicly while preserving internal scrape | Owner/reverse-proxy operation |
| `PX-S8` | Env parser/lint and query/cache canonicalization | Small independent hardening PRs |

Recommended immediate priorities are `PX-S1`, `PX-S2`, and `PX-S3`: they reduce
the chance that a routine sync, migration, or restart makes the environment
worse. `PX-S4` is the highest-priority data-trust implementation. `PX-S0` can be
decided in parallel but should not be silently bundled into a technical fix.

### 17.14 Additional definition of done

- Every Proximity response advertised as exact-round returns a canonical
  `actual_scope.round_id` and uses it in every subquery.
- Repeated map/round-number instances with different starts produce distinct
  exact-round results in contract tests.
- Unsupported query parameters fail validation; validated cache keys are
  canonical.
- Weapon leaderboard and weapon breakdown share exactly the same scope.
- Dev prox-scores, formula, player radar, quality, and representative panels all
  report one build/schema contract after restart.
- Migration validation proves it is using the same DB fingerprint and role as
  the service smoke process.
- The sync script cannot mutate an off-host or source-equal DB without a
  one-use exact target approval, and its default is local-only.
- Owner has recorded one formula visibility policy; public endpoints conform to
  it and tests distinguish public model cards from admin manifests.
- Public `/metrics` is denied while the internal Prometheus scrape remains
  healthy.
- The live route registry is singular; modern Proximity cannot be promoted
  without the documented parity matrix passing.
- Env/runbook tooling handles or rejects CRLF consistently without printing
  secrets.

## 18. Proximity quality-warning decomposition (live read-only check, 2026-07-19)

This section was added after the owner reported two different UI warnings:

```text
slomix_vm: LINKAGE_ANOMALY_BREACH
dev:       QUALITY_FETCH_FAILED
```

They do not describe the same failure. The live checks also exposed a more
important defect: production's quality endpoint measures whether `round_id` is
present, but not whether it points to the correct round.

No row, service, schema, or configuration was changed during this check.

### 18.1 Environment split confirmed

| Environment | Quality HTTP result | Meaning |
|---|---:|---|
| local dev, port 8000 | `404 {"detail":"Not Found"}` | The running old route graph does not contain `/api/proximity/quality` |
| public `slomix_vm` | `200`, `overall_status="partial"` | The endpoint ran and returned database diagnostics |

The legacy client converts any failed quality request into the synthetic
warning at `website/js/proximity.js:1638-1650`:

```json
{
  "code": "QUALITY_FETCH_FAILED",
  "message": "Unable to load proximity quality checks."
}
```

Therefore the dev message is an API/deployment failure, not evidence that the
dev data failed a quality check. It closes only after a coherent fresh process
registers the route and returns a real payload.

The public web service was verified read-only through its actual systemd unit:

- working directory: `/opt/slomix/website`;
- environment: `/opt/slomix/.env`;
- database: PostgreSQL on the VM-local target;
- two Uvicorn workers on port 7000 behind the tunnel.

This also corrected an environment ambiguity found during the investigation:
the previously inspected off-host/private database target is another copy, not
the live VM-local database used by `slomix-web`. Counts from that copy must not
be presented as production evidence. This is concrete support for `PX-DB-001`:
all diagnostics and migrations need an explicit non-secret DB fingerprint.

### 18.2 What the production payload currently says

For `session_date=2026-07-18`, a fresh uncached public request returned:

```text
overall_status: partial
signals:        all required sources reported ready
correlations:   10 rows, 9 complete, 1 missing proximity flag, 89% average
linkage scope:  global
linkage breaches:
  match_id_mismatch_rows           752 (threshold 0)
  duplicate_lua_round_links         74 (threshold 0)
  correlation_round_mismatch_rows 1022 (threshold 0)
```

The response contains two warning codes:

```text
ROUND_CORRELATION_PROXIMITY_INCOMPLETE
LINKAGE_ANOMALY_BREACH
```

The first is selected-scope data. The second is explicitly global historical
data even though it appears beneath the selected date. The UI does label its
card `Global check`, but the top-level status and warning list still combine the
two domains.

### 18.3 `PX-QUALITY-001` - round-correlation warning is a false positive

The single row responsible for
`ROUND_CORRELATION_PROXIMITY_INCOMPLETE` is an `etl_adlernest` correlation with:

```text
status = partial
r1_round_id present
r2_round_id absent
has_r1_proximity = true
has_r2_proximity = false
```

There is no R2 round to which R2 Proximity could attach. The query at
`website/backend/routers/proximity_quality.py:420-435` nevertheless counts a
row as missing when either flag is false:

```sql
WHERE NOT COALESCE(rc.has_r1_proximity, FALSE)
   OR NOT COALESCE(rc.has_r2_proximity, FALSE)
```

The correct invariant is conditional on the corresponding round existing:

```sql
WHERE (rc.r1_round_id IS NOT NULL
       AND NOT COALESCE(rc.has_r1_proximity, FALSE))
   OR (rc.r2_round_id IS NOT NULL
       AND NOT COALESCE(rc.has_r2_proximity, FALSE))
```

If product semantics require both rounds, evaluate only correlations whose
status requires both. Do not mark an intentionally partial/single-round record
as missing telemetry for a nonexistent half.

The response should report separate counts:

```text
expected_round_sides
present_proximity_sides
missing_existing_round_sides
unpaired_round_sides (informational, not telemetry failure)
```

Add tests for complete R1+R2, partial R1-only, partial R2-only, and a real
existing-round/missing-Proximity case.

### 18.4 `PX-QUALITY-002` - raw `match_id` equality is not a valid invariant

`match_id_mismatch_rows=752` sounds catastrophic, but 752 of the 761 linked Lua
rows fail because the two columns are generated from different events:

- `rounds.match_id` is anchored to the stats filename/stopwatch pairing;
- `lua_round_teams.match_id` is generated from `round_end_unix` in
  `bot/services/lua_round_storage_mixin.py:241-257`.

The codebase already documents the distinction at
`bot/services/timing_comparison_service.py:15-18`:

```text
rounds table:          match_id from filename timestamp
lua_round_teams table: match_id from round_end_unix
```

Direct equality in
`bot/services/round_linkage_anomaly_service.py:126-140` is therefore an invalid
health rule. The fact that map and round-number mismatch counts are both zero
supports that conclusion. This breach should be removed or redefined; raising
its threshold would only hide the modeling error.

`correlation_round_mismatch_rows=1022` is also driven by raw match-ID equality
with an `OR map mismatch`. The sampled data had zero map mismatches, and a large
part of the count is historical. It needs decomposition into separate
canonical-ID, map, and start-time invariants before it can be actionable.

### 18.5 `PX-LINK-001` - real wrong-round links are not measured

Although two displayed mismatch metrics are noisy, the production linkage is
not clean. A more appropriate check joins by `round_id` and compares the
canonical round start:

```sql
p.round_id IS NOT NULL
AND p.round_start_unix IS NOT NULL
AND r.round_start_unix IS NOT NULL
AND p.round_start_unix <> r.round_start_unix
```

The Proximity relinker itself describes this as the back-to-back race condition
which can corrupt KIS, momentum, BOX, and round-scoped data
(`bot/cogs/proximity_mixins/relinker_mixin.py:70-108`).

#### Global Lua result on actual `slomix_vm`

```text
lua_round_teams total:             789
round_id present:                  761
round_id absent:                    28
exact round_start match:           657
wrong round_start target:          103
linked row missing comparable start: 1
```

The truthful severe metric is 103 wrong-start links, not 752 raw match-ID
mismatches. `duplicate_lua_round_links=74` is also a real symptom, but it is not
equivalent to the wrong-start count: one incorrectly targeted row can create a
duplicate target while leaving another target empty.

Recent data proves this is ongoing rather than historical only:

| Round date | Lua linked with comparable starts | Exact | Wrong target |
|---|---:|---:|---:|
| 2026-07-13 | 16 | 12 | 4 |
| 2026-07-15 | 16 | 14 | 2 |
| 2026-07-16 | 16 | 12 | 4 |
| 2026-07-18 | 18 | 11 | 7 |
| 2026-07-19 | 5 | 2 | 3 |

The current `_link_lua_round_teams()` attempts a second-pass repair, but it:

- works in the stats-arrival window rather than as a durable full-table guard;
- compares some candidates against filename-derived round time;
- is not included in the generic Proximity relinker table fanout;
- has not prevented the recent wrong-start targets above.

This requires a writer/race fix plus guarded data repair, not only a dashboard
label change.

### 18.6 `PX-QUALITY-003` - “linked ratio” treats wrong links as healthy

`_collect_signal()` currently defines:

```sql
COUNT(*) FILTER (WHERE round_id IS NOT NULL) AS linked_rows
```

and marks a required source healthy when this ratio is at least 90%. A foreign
key can exist and still identify the wrong round. For the 2026-07-18 production
scope, the direct read-only result was:

| Source | Rows | `round_id` NULL | Wrong-start `round_id` | API status |
|---|---:|---:|---:|---|
| `combat_engagement` | 2,837 | 72 | 538 | ready / 97.46% linked |
| `player_track` | 1,300 | 37 | 240 | ready / 97.15% linked |
| `proximity_kill_outcome` | 1,039 | 0 | 30 | ready / 100% linked |
| `proximity_reaction_metric` | 2,837 | 0 | 72 | ready / 100% linked |
| `proximity_spawn_timing` | 1,039 | 0 | 30 | ready / 100% linked |
| `proximity_team_push` | 2,553 | 0 | 64 | ready / 100% linked |
| `proximity_crossfire_opportunity` | 335 | 0 | 8 | ready / 100% linked |

For the two core sources, a strict correct-link numerator is closer to 78-79%,
not 97%. The largest wrong combat groups were four repeated-map/back-to-back
rounds:

```text
te_escape2 R1:     215 rows attached to an earlier start
etl_adlernest R1:  110 rows attached to an earlier start
te_escape2 R2:     108 rows attached to an earlier start
te_escape2 R2:     105 rows attached to an earlier start
```

This does not automatically invalidate every date-level total. Many endpoints
filter a Proximity table's own `session_date/map_name/round_start_unix`, so the
event can still count in the correct date even when its `round_id` is wrong.
The highest-risk consumers are:

- joins through `round_id` to PCS, correlations, teams, or results;
- exact-round APIs which resolve/filter through `round_id`;
- caches or precomputes partitioned by the linked round;
- relink/backfill logic which assumes a non-NULL link is already correct.

This distinction explains how broad Session Stats can look plausible while
Smart Stats or exact-round analytics remain incomplete/inconsistent.

### 18.7 Corrected quality contract

For every source with `round_id`, return all of these separately:

```text
row_count
unlinked_rows
linked_rows
comparable_start_rows
exact_start_rows
wrong_start_rows
missing_start_identity_rows
exact_link_ratio
distinct_event_rounds
distinct_linked_rounds
```

Suggested status logic:

```python
if row_count == 0:
    status = "missing"
elif query_failed:
    status = "error"
elif wrong_start_rows > 0:
    status = "wrong_round_linkage"
elif exact_link_ratio < required_ratio:
    status = "round_linkage_partial"
else:
    status = "ok"
```

Use `round_canonical_id` when both sides have it. Until capability coverage is
complete, exact `(round_start_unix, normalized_map_name, round_number)` is the
fallback invariant. Never replace an exact identity check with nearest-time
matching when two candidates exist inside the window.

The top-level response should separate:

```json
{
  "selected_scope_status": "...",
  "global_maintenance_status": "...",
  "overall_status": "..."
}
```

Global historical debt may remain visible, but it must not masquerade as a
failure limited to the selected round/date.

### 18.8 Remediation order (no mutation performed)

1. **Fix diagnostics first.** Remove invalid raw-ID breaches, fix partial
   correlation expectations, and add wrong-start/exact-link metrics. This makes
   subsequent before/after evidence trustworthy.
2. **Add writer/relinker regression tests.** Reproduce two consecutive plays of
   the same map and round number where Lua arrives before each stats file. Assert
   one-to-one exact-start linkage after both arrivals.
3. **Fix live linking.** Resolve by canonical ID/exact start first. Defer
   ambiguous candidates instead of nearest-neighbor assignment.
4. **Inventory every affected table read-only.** Produce counts and proposed
   old/new `round_id` per canonical event key, split by date/table.
5. **Run a dry-run repair on staging/copy.** Require one target per row and
   prove no unique/FK/correlation conflict. Do not infer missing identity.
6. **Owner-gated production repair.** Snapshot, apply only deterministic rows,
   re-run diagnostics, recompute dependent caches only where their inputs
   changed, and retain a reversible evidence ledger.
7. **Deploy the quality route coherently to dev.** Only then compare dev and
   production quality payloads using explicit DB/build fingerprints.

The repair/backfill is deliberately not included as an automatic action in any
feature PR.

### 18.9 Additional tests and Definition of Done

- Partial correlation with absent R2 is not reported as missing R2 Proximity.
- Existing R2 with absent R2 Proximity is reported as missing.
- Raw filename/end-time `match_id` differences do not trigger a linkage breach.
- A wrong `round_id` with a non-NULL FK triggers `wrong_round_linkage`.
- Same-map/same-round-number replay pairs are linked one-to-one by exact start.
- Ambiguous/no-exact candidates remain unlinked and observable.
- Quality response clearly distinguishes selected-scope and global warnings.
- UI displays `QUALITY_FETCH_FAILED` as endpoint unavailable, not data corrupt.
- UI shows wrong-link counts and correct-link ratio, not only non-NULL ratio.
- Dry-run repair output records table, row ID, old round ID, proposed round ID,
  canonical key, confidence/reason, and dependent cache impact.
- Post-repair checks prove zero deterministic wrong-start links for the repaired
  scope and no increase in unlinked/duplicate/correlation anomalies.
