# Website Upgrade Plan (Prototype → Closer to Production)
Date: 2026-02-03

This plan captures **all steps** we can take to move the website from prototype toward a more production‑ready experience, while staying aligned with bot logic and data flow. Use as a checklist and rollback reference.

## Data & Correctness
1. ✅ Use team‑aware stopwatch scoring (map‑winner logic) from `StopwatchScoringService`.
2. ✅ Expose `scoring` in `/api/stats/last-session` so the web UI matches bot output.
3. ✅ Include `teams` (rosters + per‑player session stats) in `/api/stats/last-session`.
4. ✅ Add `stats_checks` to highlight data anomalies (kill/death mismatch, unassigned players).
5. ☐ Add `/api/stats/session-score/{date}` endpoint for non‑latest sessions.
6. ☐ Add `/api/sessions/{date}` to return scoring + rosters (not just rounds).
7. ☐ Add side‑mapping debug payload for QA (“winner_side”, “r1_defender_side”).
8. ☐ Add optional `warnings` field for missing Lua timing data.

## UI & UX (Home / Last Session)
1. ✅ Use team names + map‑winner score instead of Allies/Axis.
2. ✅ Show uncounted maps (R1‑only) explicitly.
3. ✅ Add map breakdown with per‑map times + scoring.
4. ✅ Group players by team with per‑player stats.
5. ✅ Surface stat checks (if any) in a dedicated panel.
6. ✅ Add multi‑chart visuals (team comparison, player scatter, time alive/dead, damage given/received).
6. ☐ Add a “Scoring Source” tooltip (Header vs Time fallback).
7. ☐ Add “Side Winner” legend (Axis/Allies) with clear labeling.
8. ☐ Add player badges/icons (medic, engineer, etc.) for flavor.

## Visual Upgrades
1. ✅ Add map thumbnail assets (SVG) with fallback.
2. ✅ Add Axis/Allies icon assets for UI accents.
3. ☐ Add hero “Last Session” banner using the map thumbnail of the latest map.
4. ☐ Add subtle map‑specific color accents (per map theme).

## Visual Analytics
1. ✅ Team comparison chart (kills, deaths, damage, revives, useful kills, self kills).
2. ✅ Player scatter plot (K/D vs DPM) for quick performance clustering.
3. ✅ Time alive vs dead stacked bars for top playtime players.
4. ✅ Damage given vs received bars for top damage dealers.
5. ✅ Add per‑map timeline (avg DPM across rounds).
6. ✅ Add radar chart for top 3 players (kills, DPM, revives, frag potential, efficiency, survival, time denied).
7. ✅ Add damage efficiency chart (top damage dealers).
8. ✅ Add selfkill heatmap (top selfkillers).
9. ✅ Add team utility chart (revives, gibs, useful kills, times revived, time denied).

## Validation & QA
1. ✅ Kill/Death totals check displayed for quick sanity.
2. ☐ Compare team total kills vs sum of roster kills (warn if mismatch).
3. ☐ Compare total rounds shown vs `session_ids` length / 2.
4. ☐ Add map‑pair validation: flag missing R2.
5. ☐ Add click‑to‑expand per map to show R1/R2 details.

## Deployment & Rollback
1. ✅ Document all changes in `docs/SESSION_2026-02-03_CHANGELOG_LOCAL.md`.
2. ☐ Add a `docs/WEBSITE_ROLLBACK_2026-02-03.md` file with revert steps.
3. ☐ Tag assets and JS changes for easy reversion if visuals regress.

## Notes
- Website and proximity features remain **prototypes**. These steps are to bring the site closer to reliable, bot‑aligned presentation.
- All new UI changes are **non‑destructive** and can be reverted by removing the new API payloads and replacing the session widget rendering logic.
