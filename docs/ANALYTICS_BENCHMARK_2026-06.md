# Analytics Benchmark: Sports & Esports Platforms vs Slomix (June 2026)

**Purpose**: Benchmark what leading FPS-esports and traditional-sports analytics platforms ship, translate their best ideas into ET:Legacy stopwatch terms, and rank a Top-10 implementation list for Slomix.

**Method**: Web research (Leetify, scope.gg, CS Demo Manager, Tracker.gg, Winston's Lab/OW analytics, qlstats/Quake Champions, StatsBomb/Opta, NBA tracking, WP models, WAR) cross-checked against the live Slomix schema (90 tables) and codebase on 2026-06-10. Claims about platforms are sourced; uncertain ones are flagged.

**Slomix baseline (verified in repo/DB — do not re-propose)**: per-round/match/session stats; ET Rating (9-metric percentile composite); proximity Lua tracker (200ms positions, engagements with attacker lists + crossfire, spawn-timing denial with both teams' reinforcement clocks, trade kills, kill outcomes incl. gib/revive with `effective_denied_ms`, carrier/objective/vehicle tracking, per-shot aim with circular yaw stats); KIS (health × alive-count × reinforcement multipliers); BOX stopwatch scoring; storytelling layer (gravity, space-created, enabler, lurker, archetypes, moments, momentum, narratives); per-life Player Journey; Discord bot (80+ commands); website with leaderboards/records/awards/replay/heatmaps.

**Data inventory snapshot (2026-06-10)**: `rounds` 2,520 (849 R2-paired) spanning 2025-01 → 2026-06; `combat_engagement` 83,462; `proximity_kill_outcome` 23,339; `proximity_spawn_timing` 27,110 (with `enemy_spawn_interval`, `time_to_next_spawn`, `killer_reinf`, `victim_reinf`); `lua_spawn_stats` per-player spawn/death/dead-seconds. This inventory drives the HAVE/DERIVABLE/NEEDS-LUA-V7 column below.

> ⚠️ **`killer_reinf` caveat**: all historical rows were computed WITHOUT the per-team CS_REINFSEEDS offset (Lua bug F1, fixed repo-side 2026-06-10, live deploy pending — see `docs/PROXIMITY_E2E_AUDIT_2026-06-10.md`). Wave-cycle models should derive the killer-side clock from `victim_reinf` of the opposing team's kills, or backfill killer_reinf via the per-round implied offset, until the fixed Lua is deployed.

---

## 1. Leetify (CS2)

**What they do well**: The reference for "single number with context." Every stat is benchmarked against the playerbase and against *your rank cohort*, color-coded by percentile band (Poor = bottom 10%, Subpar = 10–30%, Average = 30–70%, Good = 70–90%, Great = top 10%). The genius is not the metrics themselves — it's that every number answers "is this good *for someone like me*?"

**Signature metrics**:
1. **Leetify Rating** — zero-sum match impact rating. Kills are not equal: reward is split 35% kill / 30% damage / 15% flash assist / 20% traded death, then scaled by **change in round win probability**, which conditions on economy tier (4 levels, CT/T-specific), players alive, and which side died last. Surviving with equipment earns rating via next-round odds. All ratings in a match sum to zero.
2. **Aim Rating** — mechanical composite (crosshair placement, time-to-damage, spray accuracy, HS%) normalized so playerbase average = 50.
3. **Utility Rating** — Quantity × Quality: you must throw a lot *and* it must consistently interfere with enemies (flash duration on enemies, HE damage).
4. **Opening Duels** — first-kill-of-round attempt rate, win rate, T/CT splits.
5. **Trade rates** — traded-death % and trade-kill %, both sides.
6. **Clutch rating** — 1vN situations entered/won.
7. **Personal Bests** — notifications when a session sets a personal record; "session report card" framing of recent matches.

**UX patterns that matter**: percentile bands everywhere; rank-cohort benchmarks ("vs players at your CS Rating"); one headline number that decomposes into sub-ratings on click; personal-best celebration moments; public Data Library of global benchmark distributions.

**Slomix gap**: Slomix has the *components* (ET Rating percentiles, KIS) but not the **zero-sum, win-probability-weighted** framing, not rank-cohort benchmarks, and no personal-best/session-report-card surfacing.

## 2. scope.gg (CS2)

**What they do well**: Trainer-oriented dashboards — "in-game shape" trends (ADR, HLTV rating, KAST, KPR, K/D), aim micro-stats (time-to-kill, first-bullet accuracy, HS%), grenade usage quality (enemy flash time, nade damage), and an interactive grenade-lineup predictor with copyable `setpos` console coordinates. Demo viewer with schematic 2D round playback.

**Signature metrics**: TTK, first-bullet accuracy, enemy-flash-time per match, economy management score, map-specific splits, clutch situation logs.

**UX pattern that matters**: the **`setpos` bridge from analytics back into the game** — analysis that ends in a practice action. Slomix's heatmaps/journeys could similarly export ET `setviewpos` coordinates for position review. Also: "shape" trendlines (rolling form over last N sessions) rather than lifetime averages.

## 3. CS Demo Manager (open source)

**What they do well**: Local-first, exhaustive per-demo extraction: opening-duels panel, utility stats, 2k–5k multi-kill columns, player-filterable heatmaps, kill-context sequence export (N seconds before/after each kill), 2D playback, even Grafana-dashboard community integrations. It's the "power user's raw layer" under sites like Leetify.

**Lesson for Slomix**: Slomix already *is* this layer (it owns the pipeline). The transferable idea is the **multi-kill column convention** (2k/3k/4k/5k per round) and kill-sequence clipping hooks (Slomix's greatshot system is adjacent — wiring "every 3k+ within one wave" into greatshot highlight candidates is cheap).

## 4. Tracker.gg (Valorant)

**What they do well**: Mass-market profile UX. **Tracker Score** (0–1000, graded S/A/B/C/D) is a weighted composite of K/D, ADR, damage delta, first bloods, with **KAST weighted highest**. Per-agent and per-weapon splits, act/map filters, live overlay app.

**Signature metrics**: Tracker Score, KAST (Kill/Assist/Survive/Trade % of rounds), first bloods / first deaths, damage delta (ADR dealt − received), clutch counts, econ rating (damage per credit spent — legacy from CSGO trackers).

**UX pattern that matters**: the **letter-grade per match** plus role/agent splits. ET equivalent: per-class splits (medic/engineer/fieldops/covert/soldier) on every metric — Slomix tracks class but does not consistently split leaderboards by class. Honest caveat: KAST needs discrete rounds; ET's analogue is per-wave-cycle involvement (see §8).

## 5. Overwatch analytics (Winston's Lab, OW community stats)

Winston's Lab (now defunct/archived, but the canonical OW esports stats methodology) pioneered **fight-based analytics** — the closest structural cousin to ET stopwatch, since OW is also objective + wave-ish respawn play without discrete buy rounds.

**Signature metrics (Winston's Lab, from 11,596 logged teamfights)**:
1. **Teamfight win rate** — fights segmented automatically from kill-event clusters; team-level and per-hero fight W/L.
2. **First blood → fight conversion** — team drawing first blood won **77.2%** of all fights (74.8% of "big" fights with 3+ deaths). The single most quoted OW stat.
3. **First-pick / first-death rates per player** — who opens fights, who gets opened on. A hero being first casualty mapped to a 28% fight win chance.
4. **Ult economy** — team using more ults won 68% of fights; using fewer = 28% win chance. (ET analogue: fieldops/medic charge-bar usage — *not currently tracked*, would need Lua v7.)
5. **Staggers** — kills on players separated from the regroup, forcing one-by-one respawns and delaying the next coordinated fight. Recognized as so impactful Blizzard built the OW2 "Stranded Spawn System" specifically to reduce stagger value.

**UX pattern that matters**: the **fight ledger** — every fight a row: start/end, first blood, ults used, winner. ET stopwatch maps almost 1:1 to **wave-cycle ledgers** (fights bounded by spawn waves). This is the single most portable structure in this whole document.

## 6. Quake (qlstats / Quake Champions stats)

**What they ship**: qlstats (XonStat fork) ships **Glicko ratings** (Elo + uncertainty RD) per gametype, with performance normalized by partial play time; official QC stats ship duel/TDM ladders, weapon accuracy, medals, champion usage. Notably, *no public Quake tracker actually ships spawn-control or item-timing metrics* — those remain casting/coaching vocabulary, not productized stats (verified by search; mark this as an open niche).

**Lesson for Slomix**: (a) Glicko-style **uncertainty/confidence** on ratings — Slomix's ET Rating already shows a confidence indicator; extend it to shrink-toward-mean for low-sample players. (b) The spawn/item-timing gap means Slomix's spawn-denial analytics are already **ahead of every Quake tracker** — that's a differentiator to deepen, not a gap.

## 7. Traditional sports concepts

### StatsBomb / Opta (football)
- **xG (expected goals)**: P(shot → goal) from shot context (location, GK position, defenders in frame, impact height). Value: more predictive of future results than actual goals. ET translation: **expected objective value** — P(objective completes | game state) — and per-engagement **expected kill value**.
- **OBV (On-Ball Value)** / possession-value models (xT): every action valued by how much it changes expected goal difference over current+next possession. ET translation: value every kill/death/revive/construction by **Δ P(round objective)** — this is exactly the Leetify-Rating architecture, with the round-win model swapped for an objective model.
- **Progressive actions**: passes/carries that significantly advance the ball. ET translation: **map-progress actions** — movement/kills that advance the attacking front line (derivable from `player_track` + objective coordinates; Slomix's team_push table is adjacent).
- **Possession-adjusted defensive stats**: normalize by opportunity. ET translation: normalize defensive stats by **time spent defending** (attack/defense role per round is known in stopwatch) — e.g., kills per defensive minute, not per round.
- **Radars**: fixed-axis percentile spider charts per position. ET translation: per-class radar (medic radar ≠ fieldops radar). Slomix's profile is close; the discipline is *fixed axes per class* so shapes are comparable.

### NBA tracking
- **Shot charts/hexbins**: Slomix already has kill/movement heatmaps. The refinement worth stealing is **efficiency-vs-league hexbins** (color = your kill success in this zone relative to population average, not raw volume).
- **Gravity/spacing**: Slomix already ships a "gravity" (enemy attention drawn) — genuinely ahead of most esports trackers here; NBA gravity validates the concept.
- **Plus-minus / RAPM**: team point differential while player on/off floor; RAPM regularizes via ridge regression to untangle shared lineups. ET translation: per-player and per-pairing round-score differential. **Big caveat**: RAPM needs lineup variation; a 6v6 community with stable rosters has weak identification. Ship raw on/off + pairing splits with sample-size badges; do not ship full RAPM.
- **WAR/VORP**: value over a "replacement-level" player, with positional adjustment. ET translation: **wins above replacement lineup-slot** — how much a player's presence shifts expected BOX score vs the community's median player *of that class*. Realistic as a season-level fun stat, not a precise one.

### Win probability models
NFL/NBA in-game WP: logistic regression (or random forest) on score diff, time remaining, possession/field state; play-by-play trained; displayed as the famous live WP chart. ET stopwatch is well-suited: the state is (time remaining vs time-to-beat, objective stage, alive differential, both wave clocks). With 2,520 rounds the training set is *small but viable* for a coarse logistic model; a calibrated heuristic version can ship first. Slomix's momentum chart is the display slot; WP would give it a principled y-axis.

---

## 8. Translation table: industry metric → ET stopwatch equivalent

Availability: **HAVE** = computable today from existing tables; **DERIVABLE** = computable today but needs new aggregation/service code; **NEEDS-LUA-V7** = requires new capture.

| Industry metric (platform) | ET stopwatch equivalent | Availability |
|---|---|---|
| WP-weighted impact rating (Leetify Rating) | Objective-WP-weighted KIS; zero-sum per match | DERIVABLE (needs WP model first) |
| Opening duel W/L, T/CT split (Leetify/CSDM) | First-blood-of-round + first-blood-of-each-wave-cycle, attack/defense split | DERIVABLE (kill timestamps + wave clocks in `proximity_spawn_timing`) |
| Trade kill / traded death % (Leetify) | Already shipped (`proximity_trade_event`, `proximity_lua_trade_kill`) | HAVE |
| Clutch 1vN detection (Leetify/Tracker.gg) | Alive-count-disadvantage engagements won (no round-end, so fight-scoped) | DERIVABLE (alive_count in Lua v6.01 events + kill/spawn timeline) |
| KAST (Tracker.gg) | Wave-cycle involvement %: kill/assist/survive/trade within each wave cycle | DERIVABLE |
| Personal bests + session report card (Leetify) | PB detection over existing per-session aggregates; Discord embed + web card | HAVE (UX only) |
| Percentile vs rank-cohort benchmarks (Leetify) | Percentile vs ET-Rating-tier cohort (tiers already exist server-side) | HAVE (re-cut existing percentiles per tier) |
| Damage delta (Tracker.gg) | Damage given − received per round (both columns exist in PCS) | HAVE (trivial) |
| Multi-kill columns 2k–5k (CSDM) | Multi-kills within one wave cycle / within 10s window | DERIVABLE |
| Fight ledger + fight win rate (Winston's Lab) | **Wave-cycle ledger**: engagements bucketed by both teams' wave clocks, winner = side with net alive/objective gain | DERIVABLE (this is the keystone — see Top-10 #1) |
| First blood → fight win % (Winston's Lab 77%) | First blood of wave cycle → cycle win %; first blood of round → round win % | DERIVABLE |
| First-pick / first-death player rates (Winston's Lab) | Who draws/concedes first blood per cycle, per class | DERIVABLE |
| Stagger metric (OW vocabulary, no platform ships a number) | **Stagger index**: kills whose `effective_denied_ms` ≈ full wave (victim just spawned or just missed wave) | HAVE (`effective_denied_ms`, `time_to_next_spawn` already stored) |
| Ult economy (Winston's Lab) | Fieldops airstrike/arty + medic-pack charge economy per fight | NEEDS-LUA-V7 (charge-bar + ability events not captured) |
| Spawn control / item timing (Quake vocabulary, unshipped) | Spawn-denial suite — already shipped and ahead of the field | HAVE |
| Glicko uncertainty (qlstats) | Confidence-weighted ET Rating shrinkage | DERIVABLE (confidence indicator exists; add shrinkage) |
| xG (StatsBomb) | **xOV — expected objective value**: P(objective stage completes \| state) | DERIVABLE coarse / better with more rounds |
| OBV / possession value (StatsBomb) | Per-action Δ round-WP (kills, revives, constructions, carrier pickups) | DERIVABLE (after WP model) |
| Progressive actions (StatsBomb) | Map-progress kills/carries toward objective (front-line advance) | DERIVABLE (`player_track`, carrier/objective coords) |
| Possession-adjusted stats (Opta) | Defense-time-adjusted and attack-time-adjusted rates | HAVE (attack/defense side known per round) |
| Per-position radars (StatsBomb) | Per-class fixed-axis percentile radars | DERIVABLE |
| Hexbin efficiency vs league (NBA) | Heatmap zones colored vs population average, not raw counts | DERIVABLE (heatmap tables exist) |
| Gravity / spacing (NBA tracking) | Already shipped (storytelling gravity/space-created) | HAVE |
| On/off plus-minus (NBA) | BOX/round-score differential with player in vs out of lineup; pairing splits | DERIVABLE (small-sample caveat) |
| RAPM (NBA) | Regularized lineup regression | DERIVABLE but **not recommended** (lineup collinearity) |
| WAR/VORP (MLB) | Season-level wins-above-median-of-class | DERIVABLE (fun stat tier) |
| In-game WP chart (NFL/NBA) | Live round WP curve: time-vs-target, objective stage, alive diff, wave clocks | DERIVABLE (2,520 rounds = coarse model) |
| Economy/buy metrics (CS2 all platforms) | No equivalent (no buy system) | N/A — do not copy |

---

## 9. Top-10 proposals for Slomix (ranked)

Effort: S = days, M = 1–2 weeks, L = multi-week. Ranked by (stopwatch-nativeness × user value) / effort. Items 1–3 form a dependency spine: the wave-cycle ledger (#1) powers #2, #4, #5, #7.

### 1. Respawn-Wave Fight Model ("wave-cycle ledger") — M
The Winston's Lab fight ledger, rebuilt on ET's actual clock. Segment each round into **wave cycles** using both teams' reinforcement clocks (already per-kill in `proximity_spawn_timing.killer_reinf/victim_reinf` and `enemy_spawn_interval`). A cycle = the window between consecutive enemy-wave landings (~25–30s). For each cycle record: engagements (`combat_engagement` rows in window), first blood, kills for/against, net alive swing, objective progress delta, denied-ms total. Cycle winner = side with positive net (kills weighted by denied-ms).
*Formula sketch*: `cycle_score(team) = Σ kills × (1 + effective_denied_ms/wave_ms) + objective_progress_norm`; winner = argmax.
*Ships*: per-round fight timeline (web), team fight-win-rate, every metric below as a column on this ledger. **This is the keystone table.**

### 2. First Blood → Conversion (cycle and round) — S
Two numbers, Winston's Lab style: (a) % of wave cycles won by the side drawing first blood in that cycle; (b) % of rounds where the team with round-opening first blood sets/beats the time. Plus per-player **first-pick rate** and **first-death rate** per class. All from kill timestamps + ledger.
*Why first*: it's the stat people quote. If ET's number lands anywhere near OW's 77%, it's an instant community talking point and validates the ledger.

### 3. Stagger Index + Personal-Best Session Cards — S (bundle of two small wins)
**Stagger index**: per-player rate of kills landing on victims who just spawned or just missed a wave. Data is *already stored*: `proximity_kill_outcome.effective_denied_ms` and `proximity_spawn_timing.time_to_next_spawn`.
*Formula sketch*: `stagger_kill := effective_denied_ms ≥ 0.8 × enemy_spawn_interval`; `stagger_index = stagger_kills / kills`; leaderboard + per-round callout ("X staggered 5 allies for 142 denied seconds").
**PB session cards** (Leetify pattern): after each session, compare ~12 existing per-session aggregates (DPM, KDR, denied-ms, gravity, KIS, acc...) against the player's history; emit Discord embed + web card for any personal best, with percentile band vs ET-Rating tier cohort. Pure UX over existing data; highest delight-per-line-of-code on this list.

### 4. Man-Advantage Conversion % — M
From the kill/respawn timeline, maintain an alive-count differential series per round (alive_count already flows through Lua v6.01 events; respawn times from wave clocks + `lua_spawn_stats`). Whenever a team goes +1 or more, track whether they convert the advantage within that cycle (more kills, objective tick) or bleed it back.
*Formula sketch*: `man_adv_conv = converted_advantage_windows / total_advantage_windows`, split by advantage size (+1/+2/+3) and side (attack/defense). Team-level and "while player X alive" splits.

### 5. Clutch Detection (1vN, fight-scoped) — M
ET has no round-end elimination state, so define clutch per cycle: player is the **last alive of their wave group** (all teammates dead/awaiting wave) facing N living enemies, and either survives until the wave lands or trades up.
*Formula sketch*: from alive-timeline (per #4), `clutch_situation := teammates_alive == 0 ∧ enemies_alive ≥ 2 ∧ time_to_friendly_wave ≥ 5s`; won if `kills ≥ 1 ∧ survived_to_wave` or `kills ≥ enemies_alive − 1`. Surfaces as "held the fort" moments — plugs directly into the existing match-moments storytelling.

### 6. Defense/Attack-Adjusted Splits (Opta-style normalization) — S
Re-cut existing leaderboards by side with opportunity normalization: kills per defensive minute, denied-ms per attacking minute, damage delta by side. Side is known per round in stopwatch; columns exist. This is the T/CT-split feature ET has always implicitly had but never displayed. Also add **damage delta** (given − received) as a headline column — trivial and popular.

### 7. Round Win-Probability Curve — L (M for v0 heuristic)
Logistic model: `P(attack sets time t < target) ~ f(time_elapsed/target, objective_stage, alive_diff, attack_wave_phase, defense_wave_phase, map FE)`. Train on the 849 paired R2 matches + R1 outcomes; with ~2.5k rounds expect a coarse, map-pooled model — ship with calibration plot, mark beta. v0 can be a hand-tuned heuristic feeding the existing momentum chart so the y-axis becomes "P(attack wins)". Unlocks #8.
*Honest caveat*: NFL models train on millions of plays; this will be directional, not sharp. Fine for storytelling, not for betting.

### 8. Objective-WP-Weighted Impact (Leetify-Rating architecture) — L (after #7)
Re-weight KIS by ΔWP: each kill/death/revive/gib/construction/carrier event valued by the change in round win probability it caused, distributed Leetify-style (e.g. 50% killer / 25% damage contributors / 25% traded death — tune to ET). Zero-sum per match. This becomes "ET Rating v3: Impact" and finally answers "who actually won us this map" with one number that decomposes on click.

### 9. On/Off Plus-Minus per Player & Pairing — M
Per player: average BOX/round-score differential in matches with vs without them; per pairing: differential when both in lineup. Display with sample-size badges (n matches) and shrinkage toward 0 for n < 10. Explicitly do **not** attempt RAPM — community lineups are too collinear; document this in the UI tooltip to preempt arguments.
*Formula sketch*: `on_off(p) = mean(score_diff | p in lineup) − mean(score_diff | p absent)`, empirical-Bayes shrunk: `× n/(n+10)`.

### 10. Expected Objective Value (xOV) + progressive-action credit — L
xG translated: for each objective stage (flag, tank stage, gate, doc grab, transmit), model `P(stage completes within remaining time | alive_diff, front-line position, wave phases)`. Credit players for actions that raise xOV (carrier pickups, escort proximity, front-line-advancing kills) even when the stage ultimately fails — the "productive failed push" finally gets a number, completing what space-created started. Needs #1+#7 and objective-coordinate gates (already in repo, WS11). Most ambitious; highest ceiling for the storytelling layer.

**Deliberately not in the Top-10**: WAR-above-replacement (fun but late-stage, after #8 exists); KAST-per-cycle (folds into #1 as a column); Glicko shrinkage (small tweak to existing confidence — just do it inside ET Rating maintenance).

---

## 10. What NOT to copy

1. **Economy/buy metrics** (Leetify econ tiers, Tracker.gg econ rating, eco/force/full-buy splits) — ET has no buy system. The *architecture* of economy-conditioned WP survives (as wave/objective state), the metrics don't.
2. **Utility ratings as a separate pillar** (Leetify Utility, scope.gg flash time) — ET grenades/airstrikes aren't a purchasable economy and current Lua doesn't capture ability events. Fieldops arty/airstrike efficiency is a legitimate future Lua-v7 metric, but copying "utility rating" wholesale would measure nothing today.
3. **Round-based KAST verbatim** — no discrete buy-rounds; involvement % only makes sense per wave cycle (#1), not per "round" (an ET round is 10+ minutes).
4. **Ult economy** — no ultimates. Charge-bar economy is the analogue but needs new capture; don't fake it from kills.
5. **Full RAPM / adjusted plus-minus** — needs thousands of lineup permutations; a small community with stable 6v6 rosters gives a singular design matrix. Ship simple on/off with shrinkage (#9) and stop there.
6. **Aim-rating-as-skill-headline** — Leetify can lead with Aim Rating because CS is hitscan-duel-dominated. ET's medic-revive meta means raw aim explains less of winning; Slomix's aim suite (already shipped) belongs one level down, with impact/objective metrics as the headline. (Slomix's own KIS/ET-Rating ordering is already correct here.)
7. **Map pick/ban & matchmaking meta analytics** (Counterwatch-style tier lists, veto stats) — irrelevant to a fixed-community server with map rotation.
8. **Per-shot xG-style "shot quality"** — football shots are single decisive events; ET kills are multi-hit sequences with revives. Model value at the *engagement/kill-outcome* level (already the Slomix unit), not per bullet.
9. **Global percentile benchmarks without cohorts** — with a ~40-rated-player community, "vs all players" percentiles are nearly the same as the leaderboard. Cohort by ET-Rating tier and by class, or percentiles add no information.

---

## Sources

- Leetify: [Rating explained](https://leetify.com/blog/leetify-rating-explained/), [CS2 benchmarks](https://leetify.com/blog/cs2-benchmarks/), [Utility ratings](https://leetify.com/blog/utility-ratings/), [leetify.com](https://leetify.com/)
- scope.gg: [scope.gg](https://scope.gg/), [grenade predictor](https://scope.gg/grenade-predictor), [esports.gg review](https://esports.gg/news/counter-strike-2/scope-gg-review/)
- CS Demo Manager: [changelog](https://cs-demo-manager.com/changelog), [GitHub](https://github.com/akiver/cs-demo-manager)
- Tracker.gg: [Tracker Score announcement](https://tracker.gg/articles/tracker-score-our-new-performance-rating), [Valorant tracker](https://tracker.gg/valorant)
- Overwatch: [Winston's Lab teamfight statistics](https://www.winstonslab.com/news/2017/03/07/teamfight-statistics/), [OWL stagger explained](https://overwatchleague.com/en-us/news/21803540/stagger-explained), [Dexerto OW2 stranded-spawn](https://www.dexerto.com/overwatch/overwatch-2s-new-stranded-spawn-system-explained-2107148/)
- Quake: [qlstats.net](https://qlstats.net/), [QC stats](https://stats.quake-champions.com/), [Plus Forward rating Q&A](https://www.plusforward.net/quake/post/4488/Rating-QA/)
- StatsBomb/Opta: [possession value models](https://statsbomb.com/soccer-metrics/possession-value-models-explained/), [OBV introduction](https://blogarchive.statsbomb.com/news/introducing-on-ball-value-obv/), [ball progression](https://statsbomb.com/articles/soccer/unpacking-ball-progression/), [Hudl xG](https://www.hudl.com/blog/expected-goals-xg-explained)
- NBA/WP/WAR: [RAPM explained (NBAstuffer)](https://www.nbastuffer.com/analytics101/regularized-adjusted-plus-minus-rapm/), [adjusted plus-minus](https://www.roycewebb.com/p/adjusted-plus-minus-explained), [iWinRNFL WP model](https://arxiv.org/abs/1704.00197), [MLB WAR glossary](https://www.mlb.com/glossary/advanced-stats/wins-above-replacement), [FanGraphs WAR](https://library.fangraphs.com/misc/war/)

*Uncertainty notes*: Winston's Lab is no longer operating (figures are from its 2017 archive and remain the best published OW fight data). Leetify's exact Aim Rating feature weights are not public; the kill-reward split and WP conditioning are from their own blog. The claim that no Quake tracker ships spawn-control/item-timing metrics is based on absence of evidence in qlstats/QC-stats documentation, not a definitive catalogue.

---

**Document version**: 1.0 — 2026-06-10 — research benchmark, no code changes.
