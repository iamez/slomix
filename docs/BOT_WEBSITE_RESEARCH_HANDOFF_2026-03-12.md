# Bot / Website Research Handoff

**Date:** 2026-03-12  
**Purpose:** Single entry point for the bot-vs-website research work completed in this session, so future continuation can start from one file.

---

## What Was Produced

The following research reports were created or updated during this pass:

### Main synthesis

- `docs/reports/BOT_TO_WEBSITE_MIGRATION_RESEARCH_2026-03-12.md`

This is the broad planning document:
- migration thesis,
- keep/move/hibernate rules,
- staged research program,
- initial classification matrix,
- deep multi-agent findings,
- migration research matrix.

### Surface ownership

- `docs/reports/BOT_WEBSITE_SURFACE_MATRIX_2026-03-12.md`

This maps each major domain across:
- bot commands,
- legacy website pages,
- modern website pages,
- backend routers,
- shared services,
- recommended owner.

### Canonical contracts

- `docs/reports/CANONICAL_CONTRACTS_RESEARCH_2026-03-12.md`

This captures current vs target contract direction for:
- player identity,
- match/session identity,
- team/lineup identity,
- prediction entity shape,
- availability/planning identity.

### Hibernate / retire-later candidates

- `docs/reports/HIBERNATE_CANDIDATES_REPORT_2026-03-12.md`

This identifies low-confidence bot surfaces and classifies them by:
- confidence,
- removal risk,
- suggested hibernate/retire behavior.

---

## High-Signal Findings

### 1. The website already owns more than it first looked like

The biggest problem is **not** “missing website.”

The bigger problem is:
- incomplete parity,
- incomplete canonical contracts,
- duplicate bot UX still alive next to website surfaces.

Already strongly website-owned:
- availability,
- promotions,
- planning room,
- uploads,
- Greatshot,
- leaderboards,
- records,
- maps,
- awards,
- hall of fame,
- admin dashboarding.

Website-owned but still partial/evolving:
- player profile,
- matches / sessions / session detail,
- proximity,
- predictions.

### 2. The bot is carrying several full mini-products

The bot has at least `112` command decorators under `/bot/cogs`.

The most bot-heavy domains discovered in this pass:
- availability workflow,
- synergy / duos / team-builder,
- predictions,
- matchup,
- session drilldown / compare / audits,
- team history / team records,
- player analytics,
- proximity analytics.

Most of these are:
- analytics-like,
- workflow-like,
- or both.

That is a strong signal they want web UX, not Discord-first UX.

### 3. Some things under `/bot/` are not “bot features”

Strong shared backend/domain keepers:
- `bot/services/matchup_analytics_service.py`
- `bot/services/player_analytics_service.py`
- `bot/services/availability_notifier_service.py`
- `bot/core/advanced_team_detector.py`
- `bot/core/substitution_detector.py`
- `bot/services/round_correlation_service.py`
- `bot/core/team_manager.py`

These should feed both bot and website.

Bot-only renderer/presentation services:
- `bot/services/session_view_handlers.py`
- `bot/services/session_graph_generator.py`

Mixed/refactor-needed boundary modules:
- `bot/services/session_data_service.py`
- `bot/services/prediction_engine.py`

### 4. Strongest hibernate bucket

Highest-confidence hibernate or retire-later candidates:
- current bot-side `SynergyAnalytics` UX
- placeholder prediction subfeatures
- most rich proximity bot UX
- `!select`
- SQLite-era leftovers like `bot/core/team_history.py`

Not a hibernate candidate:
- disabled SSH monitor

That looks intentionally disabled for race-condition safety, not abandoned.

---

## Most Important Contract Work

From the canonical-contract research, the order that matters most is:

1. **Player identity**
   - move to GUID-first canonical identity
2. **Match/session identity**
   - move to server-scoped canonical keys
3. **Team/lineup identity**
   - make lineup/team fingerprints first-class
4. **Prediction entity**
   - stabilize only after identity/context contracts are real
5. **Availability/planning**
   - already relatively mature; mostly clean up bot ownership and compatibility leakage

Main contract direction:
- GUID-first player identity
- server-scoped match/session identity
- GUID-based lineup identity
- typed prediction contracts
- website-owned availability/planning, bot reduced to bridge/notifier role

---

## Best Next Continuations

Depending on what you decide later, the cleanest next options are:

### Option A: contract-first continuation

Do entity-by-entity contract drafts for:
- player,
- search,
- match,
- session,
- series,
- lineup,
- prediction.

### Option B: deprecation-first continuation

Do a retirement-readiness checklist for hibernate candidates:
- replacement exists?
- hidden runtime usage checked?
- docs updated?
- rollback path defined?
- target migration wave?

### Option C: execution planning continuation

Turn the surface matrix into a wave-by-wave migration plan:
- wave 1: website-owned domains cleanup
- wave 2: session drilldown and compare
- wave 3: matchup / synergy / team tools
- wave 4: prediction maturity + web surface
- wave 5: bot command retirement

---

## Recommended Starting Point Next Time

If you want the safest continuation, start from:

1. `docs/BOT_WEBSITE_RESEARCH_HANDOFF_2026-03-12.md`
2. `docs/reports/BOT_WEBSITE_SURFACE_MATRIX_2026-03-12.md`
3. `docs/reports/CANONICAL_CONTRACTS_RESEARCH_2026-03-12.md`
4. `docs/reports/HIBERNATE_CANDIDATES_REPORT_2026-03-12.md`

That order gives:
- ownership map first,
- contract map second,
- retirement risk third.

---

## Important Constraint For Future Work

The research points to one consistent rule:

**Do not keep expanding rich, multi-step, graph-heavy, or exploratory UX in the bot unless the website-first path has been explicitly rejected.**

The bot should increasingly focus on:
- ingestion,
- automation,
- alerts,
- quick summaries,
- admin/ops utilities,
- bridge behavior into website-owned flows.

---

## No Runtime Changes In This Pass

This session produced:
- research,
- documentation,
- handoff material.

It did **not** change runtime behavior or migrate any product surface yet.
