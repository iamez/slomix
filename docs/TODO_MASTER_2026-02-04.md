# Master TODO — Website + Bot Ops
Date: 2026-02-04

This is the single source of truth for the remaining UI + data tasks.
Update this file as items are completed or reprioritized.

## Monitoring & History
- [x] Confirm bot is writing `server_status_history` after restart.
- [x] Confirm bot is writing `voice_status_history` after restart.
- [x] If empty after 2–3 minutes, check `/api/diagnostics` table counts.
- [x] Add dashboard indicator: “Collecting history” vs “History available”.

## Home Page — Data Correctness
- [x] Verify overview stats (rounds/players/sessions/kills) after date fixes + session_date fallback.
- [ ] Verify overview stats fallback works when rounds table is empty (sessions data only).
- [x] Harden round_date/session_date casts to handle DATE/TIMESTAMP types consistently.
- [x] Verify “Most Active (All‑time + 14d)” uses GUID‑grouped data.
- [x] Recent Matches: ensure only legal rounds, show score + R1/R2 labels.
- [x] Quick Leaders (XP + DPM/session 7d) date‑type errors addressed (verify after restart).
- [x] Season box shows start/end/next season + expanded details.
- [x] Season leaders fallback to session_date per metric.

## Home Page — UX Polish
- [x] Tighten stats row spacing and clarity.
- [x] Show “Since <date>” for rounds tracked.
- [x] Ensure most‑active cards are visually prominent.

## Sessions Page
- [x] Improve map thumbnails/labels in sessions view (fallback tiles + stronger map matching).
- [x] Add clearer round grouping and score in session cards.
- [x] Ensure only legal rounds are displayed.

## Leaderboards
- [x] Auto‑load default leaderboard on entry.
- [x] Validate time window labels and stat units.
- [x] Ensure GUID alias unification is applied everywhere (search + lists).

## Maps Page
- [x] Add sort controls (most played, fastest, longest, last played, nade spam).
- [x] Show last played and average duration per map.
- [x] Add grenade/panzer/mortar metrics per map.
- [x] Add “fastest/longest/most played” highlight cards.

## Weapons Page
- [x] Hall of Fame (top player per iconic weapon).
- [x] Period toggles (all‑time/season/30d/7d).
- [x] Category filters (rifle/smg/heavy/sidearm).
- [x] Add weapon usage grid with improved readability.

## Admin Atlas
- [x] Improve grouping and flow arrows for onboarding clarity.
- [x] Add guided flow steps for ELI5 onboarding.
- [x] Add Flow tab + group controls + legend.
- [x] Reduce vertical scroll; widen atlas layout.
- [ ] Expand ELI5 labels and purpose descriptions.

## Documentation & Onboarding
- [ ] Project history: Lua → DB → Discord → Website story.
- [ ] ELI5 explanations for all systems and data flows.
- [ ] Save report after each major fix.
