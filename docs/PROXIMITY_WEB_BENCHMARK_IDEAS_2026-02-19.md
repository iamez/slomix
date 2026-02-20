# Proximity Web Benchmark Ideas (2026-02-19)

## Why this doc
Capture web research patterns for analytics UX and convert them into concrete proximity metrics we can track with Lua + parser + website.

## External patterns worth copying

### 1) Tooltips and metric definitions must be first-class UX
- Power BI docs emphasize report page tooltips to explain data context and improve user interpretation.
- Tableau docs show custom tooltip patterns to clarify meaning directly in-chart.
- Proximity takeaway: every card/leader metric needs an in-context definition, not only raw numbers.

Sources:
- https://learn.microsoft.com/en-us/power-bi/create-reports/desktop-tooltips
- https://help.tableau.com/current/pro/desktop/en-us/viz_in_tooltip.htm

### 2) Composite team-performance scoring is effective when decomposed
- Tracker Score 2.0 (Valorant) combines multiple performance dimensions into a single headline score.
- HLTV Rating 3.0 and 2.0 break performance into context-aware components (opening impact, multi-kill, clutch, KAST-style consistency), then aggregate.
- Proximity takeaway: we can have one headline team-cohesion score, but must expose sub-scores and sample sizes.

Sources:
- https://tracker.gg/valorant/articles/trn-roundtable-whats-good-whats-next-with-tracker-score
- https://www.hltv.org/news/42183/introducing-rating-30
- https://www.hltv.org/news/20695/introducing-rating-20

### 3) Context matters more than raw volume
- HLTV Rating 3.0 emphasizes context (round swing, opening situations, clutches), not just totals.
- Proximity takeaway: metrics should account for when events happen (early/late round, objective phase, trade window), not only event counts.

Source:
- https://www.hltv.org/news/42183/introducing-rating-30

## New Lua-trackable proximity metrics (practical set)

## Tier A (low risk, high value, mostly existing data)
- Trade Attempt Rate: `trade_attempts / trade_opportunities`
- Trade Conversion Rate: `trade_success / trade_opportunities`
- Miss Rate: `missed_trade_candidates / trade_opportunities`
- Median Trade Delay (ms): p50 delay between teammate death and retaliation damage/kill.
- Crossfire Activation Rate: `% of engagements where overlapping teammate pressure is active`
- Focus Survival Rate: already present, add p50/p95 survival time under focus.
- Support Exposure Rate: `% of tracked time without support radius` (inverse of support uptime).

## Tier B (moderate effort, Lua additions helpful)
- Return Fire Time (ms): first outgoing shot/damage after taking damage.
- Dodge Reaction Time (ms): first meaningful strafe/vector change after incoming damage.
- Support Reaction Time (ms): first teammate damage to attacker after ally receives damage.
- Multi-Angle Pressure Duration (ms): continuous time under 2+ attacker angles.
- Isolation Streaks: consecutive deaths without support window.

## Tier C (advanced, chemistry model)
- Duo Cohesion Score: weighted from crossfire volume, sync delay, trade conversion, support uptime.
- Role-Interaction Matrix: entry/support/anchor interactions inferred from timing + spacing.
- Round Momentum Swing: net pressure shift after key death/trade within a time window.

## UX display model for these metrics
- Every metric card has:
  - Plain definition (one line)
  - Formula (short)
  - Sample size (`n=`) to avoid misleading small-sample ranks
  - Scope tag (session/map/round)
- Leaderboards use dual columns:
  - Value
  - Confidence (sample size tier)
- Add a "Metric Glossary" panel inside proximity page and link each card label to it.

## Implementation sequence
1. UX clarity baseline (tooltips, glossary, renamed misleading labels).
2. Add derived metrics from existing API payloads (rates and delays).
3. Expand Lua capture for damage-triggered reaction telemetry.
4. Add parser/schema fields + API fields with backward compatibility.
5. Add confidence/sample-size rendering rules in UI.

## Guardrails
- Do not ship rank tables without sample counts.
- Do not present composite score without exposing sub-score components.
- Keep formulas versioned so historical comparisons remain interpretable.

## Implementation Status (2026-02-19)
- Implemented:
  - in-page metric glossary + formula/capture-source notes,
  - sample-size confidence tags in leaders/duos,
  - class summary and reaction leaderboards,
  - Tier-B reaction telemetry storage and API.
- Pending:
  - percentile rollups for reaction metrics (p50/p95),
  - composite cohesion score with explicit sub-score breakdown,
  - richer event table ergonomics (sorting/filtering refinement).
