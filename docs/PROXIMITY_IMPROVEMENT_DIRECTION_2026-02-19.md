# Proximity Improvement Direction (2026-02-19)

## Status Update (Implemented on 2026-02-19)
- Source-of-truth Lua baseline is now explicit: `proximity/lua/proximity_tracker.lua`.
- UI clarity shipped:
  - glossary/microtext for formula + capture source,
  - tooltip-style metric explanations,
  - sample-size confidence labels in leaderboards.
- Class tracking shipped in API/UI (`/proximity/classes` + class panels).
- Tier-B reaction telemetry shipped end-to-end:
  - Lua writes `REACTION_METRICS`,
  - parser imports into `proximity_reaction_metric`,
  - API serves `/proximity/reactions`,
  - UI renders return-fire/dodge/support leaderboards.
- Migration added: `proximity/schema/migrations/2026-02-19_reaction_metrics.sql`.
- Backward compatibility behavior confirmed: old files without reaction section import safely.

## Problem Statement
The current proximity experience has useful data but weak clarity. Core UX issues (ambiguous labels, low explainability, limited drill-down) make tactical insights hard to trust and act on. In parallel, current "reaction" analytics are mostly spawn-motion based and do not yet capture combat reaction behavior.

## Goals
- Make proximity cards understandable in seconds for non-technical users.
- Align metric names with what is actually measured.
- Add event-level drill-down for trade and support metrics.
- Expand data capture to support combat reaction metrics (return fire, dodge, teammate support reaction).
- Deliver in phases without breaking existing proximity import flow.

## UX Gaps
- "Fastest Reaction" label is misleading; it currently reflects spawn-to-first-move timing.
- Cards lack plain-language explanations of what each metric means.
- Engagement inspector has no legend for path colors and derived fields.
- Trade/support views show counts but not "who did what to whom."
- Engagement browsing relies on infinite scroll with weak sorting/filtering ergonomics.

## Data Expansion Ideas
- Lua tracker:
  - Capture timestamped damage taken/dealt events (`et_Damage`) per player.
  - Detect first meaningful direction change after incoming damage for dodge reaction.
  - Track teammate-under-fire windows and first support engagement against attacker.
- Parser/schema:
  - Add per-engagement reaction fields (`return_fire_ms`, `dodge_reaction_ms`, `support_reaction_ms`).
  - Add aggregated player-level reaction metrics with sample counts.
  - Preserve backward compatibility when new fields are absent.
- API/UI:
  - Expose averages plus sample count (and optionally p95) to prevent misleading rankings.
  - Show "insufficient sample" states instead of forcing comparisons.

## Implementation Phases
1. Phase 1: UX Clarity (no schema changes)
   - Rename "Fastest Reaction" to "Spawn Reaction Time."
   - Add tooltip + ELI5 text for key cards.
   - Add engagement inspector legend.
2. Phase 2: UX Drill-Down
   - Add paginated/sortable/filterable engagements table.
   - Add expandable trade/support detail boxes with named participants.
   - Add support mini-timeline view.
3. Phase 3: Data Capture Expansion
   - Patch Lua tracker for combat reaction events.
   - Extend parser and migrations for reaction fields/aggregates.
   - Add feature flags for safe rollout.
4. Phase 4: Validation and Rollout
   - Validate metrics against controlled scenarios.
   - Confirm null-handling and backward compatibility on old files.
   - Enable by environment, monitor, then make default.

## Remaining Open Questions
- Should reaction metrics also be materialized into persistent player-level aggregate tables, or stay computed at query-time from per-engagement rows?
- Should we backfill historical sessions (not possible for reaction metrics unless raw files include `REACTION_METRICS`), or treat 2026-02-19+ as telemetry epoch start?
- Should proximity reaction/class metrics remain website-first, or be promoted into Discord outputs next?
- Do we want percentile views (p50/p95) in UI for reaction metrics in addition to averages?
