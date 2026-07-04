# Slomix Good Night Engine - research + implementation plan

Datum: 2026-06-28  
Status: product/technical plan only, no runtime code changes  
Owner context: ET:Legacy friend group, mostly 40+ / 50+ players, 3-4 hour evening sessions a few times per week

## Executive summary

Slomix should not become a tryhard esports ladder. For this group, the best
product is a **memory + fair-night engine**:

- help the group gather with less organizer work
- make the teams feel fair enough
- make the evening feel worth remembering
- surface positive, funny, and team-oriented stories
- preserve 20 years of community history better than Discord can

The core new product layer is:

> **Good Night Engine** - a set of derived metrics and story selectors that
> judge the quality of an evening, compare each player mostly against their own
> baseline, and pick memories worth pushing back into Discord.

The most important implementation rule: public surfaces should be
**friendship-safe**. Show "you were above your usual" much more often than
"you ranked 14/18". Global all-time frag ladders are not the north star.

## Research synthesis

### What to copy

| Pattern | Source examples | Slomix translation |
| --- | --- | --- |
| Contextual impact, not raw K/D | Leetify Rating, HLTV Rating 3.0 | kills/revives/objective actions weighted by game state and baseline |
| Personal benchmarks | Leetify benchmarks, Strava PRs | "best since March", "above your usual", per-map PBs |
| Session recaps | fantasy leagues, Tracker-style reports | morning digest and session detail as the primary story surface |
| Segments and local records | Strava Segments | per-map objective records, holds, route moments |
| Memories pushed into chat | Facebook Memories / On This Day | daily or post-session memory hooks into Discord |
| One-click participation | pick'em pools, fantasy voting | MVP votes, prop bets, challenge votes, team-name votes |
| Practice bridge | Scope.gg style "analytics -> action" | replay/death-zone links and map review coordinates |

### What not to copy

- CS economy stats: ET has no buy system.
- Global K/D as the main hierarchy: it makes skill gaps permanently visible.
- Opaque ML ratings: explainability matters more than precision here.
- Negative auto-posts: no "worst player", no "most useless death" public badge.
- Website chat/comments: Discord is the river; the website is the archive.
- Features that need daily manual feeding.

### Relevant sources

- Leetify Rating: https://leetify.com/blog/leetify-rating-explained/
- Leetify benchmarks: https://leetify.com/blog/cs2-benchmarks/
- HLTV Rating 3.0: https://www.hltv.org/news/42485/introducing-rating-30
- Tracker Score: https://tracker.gg/articles/tracker-score-our-new-performance-rating
- Strava Segments: https://support.strava.com/hc/en-us/articles/216918167-Strava-Segments
- StatsBomb OBV/action value: https://blogarchive.statsbomb.com/news/introducing-on-ball-value-obv/
- Hudl xG primer: https://www.hudl.com/blog/expected-goals-xg-explained
- Facebook nostalgia engineering: https://engineering.fb.com/2016/03/30/ml-applications/engineering-for-nostalgia-building-a-personalized-on-this-day-experience/
- Participation inequality: https://www.nngroup.com/articles/participation-inequality/
- Leaderboard design risk: https://yukaichou.com/gamification-analysis/leaderboard-design-definitive-guide-octalysis/
- AARP 50+ gaming coverage: https://www.axios.com/2023/04/20/over-50-gamers-study-aarp
- Older-adult shared-activity design cue (RemoteChess): https://arxiv.org/abs/2502.11627
- Social play / older-adult wellbeing cue: https://en.wikipedia.org/wiki/Play_%28activity%29#Seniors
- Yahoo-style live game breakdown pattern: https://www.theverge.com/ai-artificial-intelligence/837950/yahoo-sports-game-breakdowns-ai

### Research matrix

This table is the "why this belongs in Slomix" layer. It keeps the plan from
copying features blindly.

| Domain/product | What they do | Why it works | Slomix adaptation | Avoid |
| --- | --- | --- | --- | --- |
| Leetify | performance report cards, benchmark bands, contextual rating | users understand "good for me / my tier" | own-form verdicts and baseline deltas | importing CS economy concepts |
| HLTV Rating 3.0 | impact from round swings, not just kills | rewards context and timing | KIS/impact moments weighted by objective and wave state | opaque rating as the homepage headline |
| Tracker.gg | one simple score/grade over many raw stats | easy profile scanning | simple session cards and grade-like tone | permanent global shame hierarchy |
| CS Demo Manager | demo parsing, kill timelines, heatmaps | power-user review layer | Greatshot + replay deep links | making raw demo tooling the main user journey |
| Scope.gg | analytics returns to practice | "what do I do next?" | replay/death-zone/practice bridge | pro-coach language for casual friends |
| Strava | segments, PRs, local records | personal achievement without global pressure | per-map objective records, best holds, personal PBs | only showing KOM-style winners |
| Fantasy leagues | recaps, trophies, record books, peer banter | long-running small groups need lore | season awards, team-name votes, memories | gambling-heavy framing |
| Facebook Memories | old memories pushed to users | archives need triggers | On This Night Discord post | resurfacing embarrassing moments |
| Older-gamer research | familiar shared activity supports connection | game is a social catalyst | keep ET evening as the ritual, site as memory | designing like a youth esports ladder |
| Recreational/masters sport | handicaps, age-grade, social cadence | context beats absolute rank | own-baseline and role-adjusted comparisons | over-quantifying friendship |

### Audience model

Assumption for product decisions:

- Most users are not looking to grind rank.
- They already know each other; banter is part of the value.
- They play long evening blocks to relax.
- Some players are much stronger than others, and everyone knows it.
- The site should reduce organizer load, not add homework.
- The best stats are the ones that become Discord lines the next day.

Therefore the default public metric should answer:

1. Was the night good?
2. Were teams fair enough?
3. What should we remember?
4. Did I have a decent night compared to myself?
5. What is the next game-night action?

It should not primarily answer:

1. Who is objectively worst?
2. Who should be blamed?
3. Who should stop playing a class?
4. Who is absent too often?

## Product principles

1. **The evening is the product.** Stats exist to make the next evening happen
   and the last evening memorable.
2. **Rank vs yourself first.** Public copy should prefer rolling personal
   baseline deltas over global placement.
3. **Public = positive or team-oriented.** Negative diagnostics belong private,
   opt-in, or admin-only.
4. **Discord triggers, website explains.** Every digest line should deep-link
   into the site.
5. **No ghost-town pages.** Add panels to existing routes before creating new
   pages.
6. **Explain every score.** If a number is shown, users must be able to see why.
7. **Use gentle humor, not shame.** This is a group of friends relaxing after
   work, not a ranked ladder.

## Existing code and data anchors

This plan is intentionally reuse-first. Most primitives already exist.

### Website routes/surfaces

| Surface | Existing code | Use in this plan |
| --- | --- | --- |
| Home | `website/js/home.js`, route registry `home` | next night, last night, memory card |
| Tonight | `website/js/tonight.js`, `website/backend/routers/players_router.py` `/stats/tonight` | fair-team suggestions, live "director" line |
| Sessions | `website/js/sessions.js`, `website/js/session-detail.js`, `website/backend/routers/sessions_router.py` | Good Night card, player own-form cards, moments |
| Player Profile | `website/js/player-profile.js`, `website/backend/routers/players_profile_router.py` | identity, own-form, duo memories |
| Record Book | `website/js/record-book.js`, `website/backend/routers/records_router.py` | estate, segments, named records |
| Story | `website/js/story.js`, `website/backend/routers/storytelling_router.py` | moment selection, narrative lines |
| Greatshot | `website/js/greatshot.js`, `website/backend/routers/greatshot.py` | clip candidates from story-worthy moments |
| Availability | `website/js/availability.js`, `website/backend/routers/availability.py` | gathering and threshold UX |
| Planning | `website/backend/routers/planning.py` | future fair-night team suggestions |

### Bot/Discord anchors

| Area | Existing code | Use |
| --- | --- | --- |
| Morning/session digest | `bot/services/session_digest_service.py` | push Good Night summary and moment links |
| On this day | `bot/services/on_this_day_service.py`, `bot/cogs/on_this_day_cog.py` | memory engine output |
| Availability poll | `bot/cogs/availability_poll_cog.py` and mixins | game-on automation |
| Round publishing | `bot/services/round_publisher_service.py` | later live hooks |

### Existing scoring/story code

| Component | Existing code | Notes |
| --- | --- | --- |
| Own baseline helper | `website/backend/services/storytelling/baseline.py` | already encodes "value + delta vs usual" rule |
| Story facade | `website/backend/services/storytelling/service.py` | mixin facade for KIS, moments, synergy, narrative |
| Session verdicts | `website/backend/routers/sessions_router.py` `/stats/session/{id}/verdicts` | already rank-vs-self via DPM percentile |
| MVP voting | `website/backend/routers/sessions_router.py` `/stats/session/{id}/mvp` | peer recognition, "most underrated" |
| Tonight hold curve | `website/backend/routers/players_router.py` `/stats/hold-probability` | live tension chart seed |
| Greatshot highlights | `greatshot/highlights/detectors.py` | multi-kill/spree/headshot candidates |

### Data tables already useful

| Table | Source | Why it matters |
| --- | --- | --- |
| `rounds` | core schema/migrations | session, map, stopwatch timing, validity |
| `player_comprehensive_stats` | core schema | kills, deaths, DPM, revives, damage, time |
| `session_round_scores` | `migrations/033_add_oksii_adoption_fields.sql` | BOX scoring and map outcomes |
| `player_skill_ratings`, `player_skill_history` | `migrations/024_add_skill_ratings.sql` | team balance and movers |
| `storytelling_kill_impact` | `migrations/032_add_storytelling_kill_impact.sql` | KIS moments and impact |
| `proximity_spawn_timing` | `migrations/013_add_proximity_v5_teamplay.sql` | stagger, wave/fight timing |
| `proximity_kill_outcome` | `migrations/021_add_proximity_kill_outcome.sql` | effective denied time, revive/gib/tapout |
| `proximity_lua_trade_kill` | `migrations/013_add_proximity_v5_teamplay.sql` | trades |
| `proximity_crossfire_opportunity` | `migrations/013_add_proximity_v5_teamplay.sql` | pair/teamplay moments |
| `proximity_team_push` | `migrations/013_add_proximity_v5_teamplay.sql` | push quality |
| `proximity_objective_run` | `migrations/030_add_proximity_objective_runs.sql` | engineer/objective stories |
| `proximity_carrier_event`, `proximity_carrier_kill` | `migrations/028_add_proximity_v6_carrier_intel.sql` | flag/doc carry stories |
| `availability_entries` | `website/migrations/005_date_based_availability.sql` | game-night formation |
| `planning_*` | `website/migrations/007_planning_room_mvp.sql` | team suggestions and votes |
| `session_mvp_votes`, `weekly_challenges` | `website/migrations/009_mvp_votes_and_weekly_challenges.sql` | peer recognition and weekly ritual |
| `season_awards`, `parimutuel_*` | `website/migrations/010_season_awards_and_parimutuel.sql` | season ritual and bench participation |
| `greatshot_*` | `migrations/011_add_greatshot_pipeline_tables.sql` | demo analysis and future clips |

## Bigger-than-proximity opportunity atlas

The proximity stack is not just "who stood near whom". It is the raw material
for a broader product layer:

> **Slomix knows where players were, what they looked at, when they spawned,
> when they moved, who they focused, who they traded, who they revived, who ran
> objectives, and how the map state changed.**

That should become more than tables. It can become:

- a live game director
- a map intelligence system
- a player fingerprint system
- a fair-team and role system
- a story/memory engine
- a practice/review bridge
- a Greatshot clip selector

### Telemetry capability map

| Capability | Existing data | What it can become |
| --- | --- | --- |
| 200ms paths | `player_track` | route DNA, life cards, team shape, movement personality |
| combat positions | `proximity_combat_position` | kill lines, death zones, danger zones, positional efficiency |
| shots + viewangles | `proximity_shot_fired` | aim fingerprint, hold/sweep style, pre-aim zones |
| aim lock | `proximity_aim_lock` | target tracking, time-to-target, crosshair-on-enemy windows |
| spawn timing | `proximity_spawn_timing` | spawn economy, stagger debt, wave fight ledger |
| kill outcome | `proximity_kill_outcome` | kill permanence, revive/gib value, true denied time |
| trades | `proximity_lua_trade_kill`, `proximity_trade_event` | trade trust, revenge speed, duo chemistry |
| focus fire | `proximity_focus_fire` | team target selection, pile-on discipline |
| crossfire | `proximity_crossfire_opportunity` | pair tactics, angle control, visual map stories |
| cohesion | `proximity_team_cohesion` | team shape, stragglers, regroup discipline |
| pushes | `proximity_team_push` | objective pressure waves, failed/successful pushes |
| objective runs | `proximity_objective_run` | engineer hero stories, route efficiency, escort credit |
| carrier events | `proximity_carrier_event`, `proximity_carrier_kill` | doc-run stories, carrier risk, stop-of-night |
| vehicle/construction | `proximity_vehicle_progress`, `proximity_construction_event` | objective-stage timeline |
| hit regions | `proximity_hit_region` | aim outcome, weapon/body profile |
| reaction | `proximity_reaction_metric` | spawn readiness, first-move discipline |
| comm events | `proximity_comm_event` | "Medic!" response, communication proxy |
| skill snapshots | `proximity_skill_snapshot` | XP/class context, role maturity |
| replay endpoints | `/proximity/round/{id}/timeline`, `/tracks`, `/team-comparison` | review mode and story deep links |

### Big bet catalog

| Bet | Product idea | Data | Website surface | Status |
| --- | --- | --- | --- | --- |
| Live Director | one sentence that explains the current game | `/stats/tonight`, wave cycles, momentum, objective events | Tonight | derive |
| Map Intelligence | "where this map is won/lost" | heatmaps, pushes, objective runs, carrier events | Record Book / Maps / Proximity | derive |
| Player Fingerprint | each player has a recognizable style | paths, aim, shots, trades, objectives | Profile | derive |
| Team Shape | spacing, stragglers, regroup quality | cohesion, pushes, tracks | Session Detail / Proximity | derive |
| Spawn Economy | wave control, stagger debt, spawn discipline | spawn_timing, kill_outcome, spawn_select | Session Detail / Story | derive / v7 |
| Objective Pressure | real pressure vs empty movement | objective runs, pushes, carrier, construction | Session Detail / Maps | derive |
| Duo Trust | who trades/revives/crossfires with whom | trades, revive, crossfire, buddy pairs | Profile / Rivalries | derive |
| Review Bridge | "watch this life/wave" from every insight | replay tracks, timeline, Greatshot | Session Detail / Replay | derive |
| Clip Director | not just multi-kills; story-worthy clips | story_score + Greatshot crossref | Greatshot / Digest | derive |
| Old Boys Mode | fun/relaxed trophies and night awards | all above + attendance | Home / Digest / Awards | derive |
| Slomix Museum | old memories, named places, LAN, screenshots | records, uploads, sessions | Record Book | build |
| Team Rotation Engine | fair and fresh teams across weeks | skill, form, team history, availability | Tonight / Planning | derive |
| Map Coach | private tips per map | death zones, routes, aim, spawn | Profile / Proximity | derive |
| Data Trust | "why this insight is safe" | coverage/orphans/source counts | Admin / Diagnostics | build |

### Idea atlas by product area

#### A. Live Director

Goal: make Tonight feel alive without turning it into a noisy esports HUD.

Ideas:

1. **One-line game read**
   - "Team A won 4 of last 5 wave fights, but Team B owns the objective room."
   - Data: `/stats/tonight`, wave cycles, objective events.

2. **Pressure pulse**
   - A single meter for current objective pressure.
   - Data: team_push toward objective, carrier events, enemies/teammates near objective.

3. **Regroup warning**
   - "Allies are staggered; next real push likely after the next wave."
   - Data: spawn_timing, alive counts, wave ledger.

4. **Comeback watch**
   - "R2 chase is inside historical 30% comeback window."
   - Data: hold probability curve, map timing history.

5. **Late chaos badge**
   - If session is past a local-time threshold and weird events spike.
   - Data: time of night, rare weapons, selfkills, close maps.

Display rule: one live sentence at a time. Do not show 12 live panels.

#### B. Map Intelligence

Goal: each map should feel like a place with memory, not just a row in a table.

Ideas:

1. **Map "where pushes die" overlay**
   - Heatmap of failed objective pushes and carrier deaths.
   - Data: `proximity_team_push`, `proximity_objective_run`, `proximity_carrier_kill`.

2. **Chokepoint index**
   - Zones with high deaths, high denied time, high repeated fights.
   - Data: combat positions, kill outcomes, spawn timing.

3. **Route success tree**
   - For doc/carry maps: common routes and success/fail rates.
   - Data: carrier path samples, player_track, objective coords.

4. **Objective stage timeline**
   - "Gate phase usually decides this map."
   - Data: construction/vehicle/objective events, round durations.

5. **Named zones**
   - Let repeated hotspots become friendly lore names later.
   - Data: clusters from death/kill/objective locations.

6. **Personal danger zones**
   - "You die most often entering lower tunnel."
   - Data: player_dies heatmap vs population baseline.

Map page target copy:

```text
supply
Usually decided at depot gate. Most Slomix wipes happen 20-35s after Allied wave.
Your best route: west stairs. Your danger zone: lower tunnel entry.
```

#### C. Player Fingerprint

Goal: profile should explain who someone is in this group.

Fingerprint axes:

| Axis | Data | Label examples |
| --- | --- | --- |
| Aim style | shot_fired, aim_lock, hit regions | Angle holder, Sweeper, Close-range brawler |
| Movement | player_track, reaction, sprint/stance | Fast opener, Slow anchor, Route runner |
| Spawn discipline | spawn_timing, reaction, spawn_select | Wave timer, Late mover, Backspawn brain |
| Objective gravity | objective_run, carrier, pushes | Objective anchor, Escort, Stopper |
| Teamplay | trades, crossfire, focus_fire, revives | Trade buddy, Crossfire setter, Medic trust |
| Pressure | KIS, space-created, gravity | Attention magnet, Enabler, Lurker |
| Night rhythm | hour splits | Early sharp, Late chaos, Steady hand |

Output:

```text
Player DNA: Objective Anchor
Holds angles, trades quickly, strongest around objective rooms.
Best with: Zlatorog (trade trust), SuperBoyy (objective pressure).
```

Private version:

```text
One useful thing: your first death rate spikes on braundorf lower route.
Review 3 waves -> replay links.
```

#### D. Team Shape and Chemistry

Goal: "why did these teams work?" not just "who fragged".

Ideas:

1. **Team shape timeline**
   - compact graph of dispersion/stragglers over the round.
   - Data: `proximity_team_cohesion`.

2. **Buddy pair reliability**
   - who naturally stays close and converts fights.
   - Data: `buddy_pair_guids`, trades, crossfire.

3. **Medic trust**
   - who gets revived, who protects medics, who answers "Medic!" if comms enabled.
   - Data: revives, comm_events, positions near downed teammate.

4. **Focus fire discipline**
   - did team shoot the same target or split damage?
   - Data: `proximity_focus_fire`, combat engagements.

5. **Straggler cost**
   - aggregate team-level only by default.
   - Data: cohesion straggler_count + deaths shortly after separation.

Public tone:

- "Team A grouped better on defense."
- Not "Player X wandered off and lost the map."

#### E. Spawn Economy

Goal: ET has a hidden economy: time denied by spawn waves.

Ideas:

1. **Stagger debt**
   - total seconds one team lost to badly timed deaths.
   - Data: `proximity_spawn_timing`, `effective_denied_ms`.

2. **Spawn steal**
   - deaths right after spawn that delay the next coordinated push.
   - Data: time_to_next_spawn >= 80% interval.

3. **Wave conversion**
   - first blood in a wave -> did the team win that wave?
   - Data: wave cycles.

4. **Backspawn discipline**
   - once spawn_select is reliable, measure smart spawn choices.
   - Data: `proximity_spawn_select`.

5. **Regroup quality**
   - how often team starts a push with enough players alive.
   - Data: tracks, cohesion, spawn waves.

Website language:

```text
Spawn economy
Team B lost 168s to stagger deaths. Team A converted 6/9 first picks into wave wins.
```

#### F. Objective Pressure

Goal: reward the part of ET that raw K/D misses.

Ideas:

1. **Real pressure seconds**
   - time spent near objective with enough teammates alive and enemies contested.
   - Data: objective coords, player_track, alive count.

2. **Empty pressure filter**
   - movement near objective with no team follow-up counts less.
   - Data: team_push participant count, enemies nearby.

3. **Escort credit**
   - already partly exists; surface as story cards.
   - Data: escort credits, carrier events.

4. **Objective denial**
   - kills/blocks that stop a real run.
   - Data: objective_run denied, carrier_kill, construction/defuse events.

5. **Productive failed push**
   - failed pushes that still moved objective state or forced defenders back.
   - Data: push direction, space-created, carrier progress.

This is a strong Slomix differentiator. ET players understand objectives even
when stats pages usually ignore them.

#### G. Aim Truth and Combat Review

Goal: not "you have bad aim", but "what kind of combat do you take?"

Ideas:

1. **Aim fingerprint**
   - angle holder vs sweeper using circular yaw stats already built.
   - Data: `proximity_shot_fired`, `/proximity/player-aim`.

2. **Pre-aim discipline**
   - with aim_lock, how often crosshair is on enemy before first shot.
   - Data: aim_lock + shot_fired + kill timeline.

3. **Panic fire**
   - shots with high yaw/pitch change, low hit outcome, close enemy.
   - Data: shot_fired, aim_lock, hit regions.

4. **Comfort zones**
   - zones where a player gets high kill efficiency, not just high volume.
   - Data: kills_from vs player_dies vs presence.

5. **Weapon/body profile**
   - "rifle body finisher", "SMG headshot streaky", etc.
   - Data: hit regions, weapon stats.

Public:

```text
Aim style: angle holder - tight horizontal spread, most shots SW.
```

Private:

```text
Review: wide panic sweeps in lower tunnel fights.
```

#### H. Life Cards and Replay Review

Goal: convert telemetry into understandable stories.

Each life can become a card:

```text
Life 4 - supply R2
Spawned lower, moved 620u, joined push, traded SuperBoyy, died after 42s.
Impact: + objective pressure, + trade, - late death.
Replay -> map path -> clip candidate
```

Data:

- `player_track`
- timeline endpoint
- proximity events
- KIS
- objective events

Use cases:

- player profile "best life this session"
- Session Detail "turning-point life"
- private review "three lives to watch"

#### I. Slomix Museum / Lore Layer

Goal: make telemetry become group history.

Ideas:

1. **Named records**
   - "The SuperBoyy revive night", not only "revives: 17".

2. **Named places**
   - repeated map hotspot clusters can get community names.

3. **Time capsules**
   - season recap plus screenshots/clips.

4. **LAN bridge**
   - physical event page with photos and stats from that weekend.

5. **Old route ghosts**
   - compare 2025 vs 2026 heatmaps on the same map.

This is not proximity-only, but proximity makes the archive visual.

#### J. Data Trust and Debuggability

Goal: if the site tells richer stories, users need confidence that it is not
hallucinating.

Ideas:

1. **Insight source badge**
   - "based on 8 rounds, 132 proximity events, 0 missing links".

2. **Coverage indicator**
   - proximity/shot/aim availability for a session.

3. **No-data graceful fallback**
   - old sessions still show score/story without proximity-heavy claims.

4. **Admin telemetry health**
   - orphan round_id, latest proximity file, v7 status.

Data trust is product work, not just ops. It prevents arguments.

### Bigger-bet prioritization

Ranked for this specific group, not for a generic esports product.

| Rank | Bet | Why now | First shippable slice |
| ---: | --- | --- | --- |
| 1 | Good Night + Moment Director | turns all telemetry into a story, fits audience | Session Detail top card + 5 moments |
| 2 | Map Intelligence | proximity becomes visual and memorable | one map page panel: where pushes die |
| 3 | Player Fingerprint | profiles become identity, not stat dumps | 4-axis "Player DNA" card |
| 4 | Team Shape / Chemistry | helps team balance and post-game banter | duo trust + team shape summary |
| 5 | Spawn Economy | uniquely ET, already partially implemented | stagger debt panel on Session Detail |
| 6 | Objective Pressure | rewards non-fraggers and ET objective play | real pressure seconds v0 |
| 7 | Greatshot Clip Director | unique moat, but depends on crossref confidence | clip candidates, not auto-render |
| 8 | Live Director | cool, but should wait for stable derived metrics | one live sentence on Tonight |
| 9 | Life Cards | very rich, but can become heavy UI | one "best life" card per session |
| 10 | Slomix Museum | long-term estate value | named records + memory card |
| 11 | Aim Truth | powerful, but potentially too tryhard if framed wrong | aim style card, not aim grade |
| 12 | Data Trust | not flashy, but needed as richness grows | coverage badges on insights |

Recommended big sequence:

1. **Story layer first** - Good Night + moments.
2. **Visual map layer second** - where pushes die / objective pressure.
3. **Identity layer third** - Player DNA and duo trust.
4. **Live layer fourth** - once derived signals are trusted.

This order avoids building a complicated live/proximity dashboard before the
product knows what stories the group actually likes.

## ET:L stopwatch implementation research

### Coverage audit from the second pass

The first version of this document covered the product layer well: Good Night,
own-form cards, memory, tone, team balancing, moment ranking, wave fights,
website placement, API contracts, tests, and risks.

The weak part was the ET:L-specific implementation layer. It had enough
proximity ideas, but it did not yet define the game as a stopwatch domain:

- two attempts on the same map
- teams swapping Axis/Allies roles
- Round 1 setting a target time or fullhold
- Round 2 chasing that target time
- staged objectives that differ by map
- spawn waves and revive/gib permanence
- class-gated objective actions
- map-specific routes, chokes, documents, vehicles, gates, and command posts

That gap matters. If Slomix treats ET:L like a generic kill timeline, the
system will keep rewarding frags more than the actual stopwatch race. The next
implementation layer should therefore be a **Stopwatch Objective Model** that
turns raw telemetry into objective-stage, wave, and time-to-beat context.

### Primary references and local anchors

External references used for this ET:L-specific pass:

- ET:Legacy Lua docs: https://etlegacy-lua-docs.readthedocs.io/en/latest/
- ET:Legacy Lua callbacks: https://etlegacy-lua-docs.readthedocs.io/en/latest/callbacks.html
- ET:Legacy Lua functions: https://etlegacy-lua-docs.readthedocs.io/en/latest/functions.html
- Team Fortress 2 Payload reference: https://wiki.teamfortress.com/wiki/Payload
- Winston's Lab Overwatch fight analytics: https://www.winstonslab.com/news/2017/03/07/teamfight-statistics/
- Overwatch League stagger explainer: https://overwatchleague.com/en-us/news/21803540/stagger-explained

Local project anchors used in this pass:

- `docs/STOPWATCH_IMPLEMENTATION.md`
- `docs/TEAM_AND_SCORING.md`
- `docs/ANALYTICS_BENCHMARK_2026-06.md`
- `proximity/lua/proximity_tracker.lua`
- `proximity/parser/parser.py`
- `proximity/objective_coords_from_etmain.json`
- `website/assets/maps/proximity/objective_zones.json`
- `website/assets/maps/proximity/objective_descriptions.json`
- `migrations/013_add_proximity_v5_teamplay.sql`
- `migrations/021_add_proximity_kill_outcome.sql`
- `migrations/028_add_proximity_v6_carrier_intel.sql`
- `migrations/029_add_proximity_v6_phases.sql`
- `migrations/030_add_proximity_objective_runs.sql`

### What makes ET:L stopwatch unusual

ET:L stopwatch is closer to a timed relay race than to a normal FPS match.
Most analytics products assume either discrete rounds (CS/Valorant), continuous
score accumulation (Quake/TDM), or objective teamfights without mirrored
attempts (Overwatch). Slomix has to model these ET:L-specific properties:

1. **Mirrored map attempts**
   - A map is not one round. It is a pair of attempts.
   - The persistent team is not Axis or Allies. Axis/Allies are temporary
     roles.
   - Round 1 creates the target. Round 2 is judged against the target.
   - A weaker raw stat line can still be the better stopwatch performance if it
     defended the target or forced a slower attack.

2. **Time-to-beat pressure**
   - In Round 1, the attacker is trying to set the fastest possible completion.
   - In Round 2, every second has a known meaning: enough time remains or the
     chase is slipping away.
   - A late kill in Round 2 can be worth much more than an early kill because it
     can burn the last coordinated wave.

3. **Map-specific stage graph**
   - "Objective" is not one thing. It can mean destroy, construct, escort,
     steal, carry, transmit, open a side route, capture a spawn, or repair a
     vehicle.
   - Every map has a different order and different optional shortcuts.
   - A generic "near objective" metric is too flat. The active stage matters.

4. **Spawn-wave economy**
   - ET:L does not have CS-style buy rounds or Overwatch-style hero economy.
   - The economic resource is time lost to respawn waves.
   - A kill is valuable when it denies a wave, forces a stagger, prevents a
     revive, or breaks a synchronized push.

5. **Revive/gib permanence**
   - A kill is not final until the victim is gibbed, taps out, or the revive
     window expires.
   - `proximity_kill_outcome.effective_denied_ms` is therefore more important
     than raw kills for objective impact.

6. **Class and role gates**
   - Engineers, medics, field ops, covert ops, and soldiers do not have the
     same objective meaning.
   - Engineer objective runs, medic revive saves, field ops pressure, and
     soldier clears need different scoring vocabularies.

7. **Social session context**
   - The group plays 3-4 hour evening sessions, usually as older long-term
     friends.
   - The goal is not only competitive precision. The goal is to remember a good
     night, highlight funny/heroic moments, and keep the scoreboard from turning
     into a social weapon.

### Analog game research matrix

No other mainstream FPS is a perfect match. Use analog games as partial
inspiration only.

| Game/product | Useful pattern | ET:L translation | Do not copy |
| --- | --- | --- | --- |
| Overwatch escort/hybrid/fight analytics | fight ledger, first pick conversion, stagger language, objective pressure | wave-cycle ledger, first kill to stage-pressure conversion, stagger debt | hero ult economy, role balance logic, hero-specific counters |
| Team Fortress 2 Payload/Attack-Defend | payload progress, cart presence, spawn waves, attack/defense pacing | vehicle escort credit, route/stage pressure, defense hold windows | cart-only thinking for maps without vehicles |
| Dirty Bomb Stopwatch | closest design lineage: stopwatch, revive, objective classes, EV escort | stage split records, revive/gib permanence, engineer run credit | merc ability economy unless ET:L captures equivalent events |
| Unreal Tournament Assault | staged objective race and fastest-time comparison | stage split table and map-stage records | deathmatch-heavy frag credit |
| CS/Valorant trackers | report cards, percentile bands, personal bests, round swing ratings | own-form cards and impact deltas | economy, buy rounds, KAST per round |
| Traditional sports xG/OBV/WP | expected value of actions, win probability curves | xOV and delta-xOV per ET:L action | pretending the model is precise before calibration |

The strongest implementation lesson is from Overwatch/Winston's Lab, but not
because ET:L plays like Overwatch. The portable idea is the **ledger**: break a
continuous objective game into meaningful fight windows, then explain each
window by first blood, resources, deaths, and objective conversion. ET:L should
replace "teamfight" with **spawn-wave objective cycle**.

### Canonical ET:L data model

Build all advanced features around this hierarchy:

```text
GamingSession
  MapMatch
    AttemptRound
      ObjectiveStage
        WaveCycle
          Life
            Event
```

Definitions:

| Object | Meaning | Existing source |
| --- | --- | --- |
| `GamingSession` | one evening of play | session/date grouping, `rounds`, session services |
| `MapMatch` | two stopwatch attempts on the same map | `rounds` paired by map and order |
| `AttemptRound` | one attack/defense attempt | `rounds`, `actual_time`, `time_limit`, side fields |
| `LogicalTeam` | persistent real team across side swaps | `session_teams` |
| `ObjectiveStage` | current map objective step | objective graph + construction/carrier/vehicle/objective events |
| `WaveCycle` | fight window bounded by spawn waves | `proximity_spawn_timing`, `lua_spawn_stats`, kill timeline |
| `Life` | one spawn-to-death/round-end track | `player_track` |
| `Event` | kill, revive, gib, carry, construct, destroy, escort, push | proximity/story tables |

The important implementation detail: Axis/Allies should be resolved as a
runtime role on an `AttemptRound`, not treated as the real team. Every
objective and impact service should accept both:

```text
side_role: axis | allies
logical_team_id: team_a | team_b
```

This keeps Round 1 and Round 2 comparable after the side swap.

### Map Objective Graph

The next big unlock is a map-specific objective graph. Start as versioned JSON,
not as a DB migration. It should be reviewed by humans for the first 3-5 most
played maps, then improved with script parsing later.

Proposed future path:

```text
website/assets/maps/proximity/objective_graphs/{map_name}.json
```

Example shape:

```json
{
  "map": "supply",
  "version": 1,
  "attackers_default": "allies",
  "stages": [
    {
      "id": "depot_gate",
      "label": "Open depot access",
      "type": "destroy",
      "required_class": "engineer",
      "weight": 0.24,
      "primary_zone": {
        "x": 0,
        "y": 0,
        "z": 0,
        "radius": 650
      },
      "success_events": [
        {
          "table": "proximity_construction_event",
          "event_type": "objective_destroyed",
          "track_name_like": "%gate%"
        }
      ],
      "unlocks": ["documents_pickup"]
    },
    {
      "id": "documents_pickup",
      "label": "Steal documents",
      "type": "carry_pickup",
      "required_class": null,
      "weight": 0.31,
      "primary_zone": {
        "source": "objective_coords_from_etmain",
        "objective": "documents",
        "radius": 550
      },
      "success_events": [
        {
          "table": "proximity_carrier_event",
          "event": "pickup"
        }
      ],
      "unlocks": ["transmit"]
    },
    {
      "id": "transmit",
      "label": "Transmit documents",
      "type": "transmit",
      "required_class": null,
      "weight": 0.45,
      "primary_zone": {
        "source": "objective_coords_from_etmain",
        "objective": "transmitter",
        "radius": 550
      },
      "success_events": [
        {
          "table": "proximity_carrier_event",
          "event": "delivered"
        }
      ],
      "unlocks": []
    }
  ],
  "optional_nodes": [
    {
      "id": "command_post",
      "label": "Command post",
      "type": "command_post",
      "weight": 0.08
    }
  ]
}
```

The coordinates in this example are placeholders; do not ship a graph until the
map's actual zones are verified from `proximity/objective_coords_from_etmain.json`,
`objective_zones.json`, live Lua output, or map script inspection.

Graph fields that matter:

| Field | Why it matters |
| --- | --- |
| `id` | stable key for stage splits and records |
| `type` | tells scoring what action kind completes or progresses the stage |
| `weight` | prior importance when calculating xOV and Good Night reasons |
| `primary_zone` | turns position/proximity into objective pressure |
| `success_events` | maps Lua/parser events to stage completion |
| `unlocks` | converts a flat event list into a stage timeline |
| `required_class` | prevents non-engineer pressure from being treated as plant/construct ability |

Use the graph for five products:

1. stage split table
2. objective pressure seconds
3. xOV model
4. map page visualization
5. story moment selection

### Round state vector

Every objective-impact algorithm should reduce a timestamp to a single state
object. This avoids each feature inventing its own interpretation of the game.

```python
RoundState(
    round_id: int,
    map_name: str,
    elapsed_ms: int,
    attempt_number: int,
    attacking_side: str,
    defending_side: str,
    attacking_logical_team: str,
    defending_logical_team: str,
    target_time_ms: int | None,
    time_to_beat_ms: int | None,
    active_stage_id: str,
    stage_progress: float,
    attack_alive: int,
    defense_alive: int,
    attack_wave_ms: int,
    defense_wave_ms: int,
    carrier_state: dict | None,
    vehicle_progress: float | None,
    frontline_distance_to_objective: float | None,
    team_shape_score: float,
    objective_pressure: float
)
```

Sources for `RoundState`:

| Field family | Source |
| --- | --- |
| attempt, map, elapsed, time limit | `rounds` |
| persistent teams | `session_teams` |
| side role resolver | existing stopwatch scoring logic |
| stage and progress | objective graph plus construction/carrier/vehicle events |
| alive counts | kill timeline, `player_track`, respawn timing |
| wave clocks | `proximity_spawn_timing`, `lua_spawn_stats` |
| revive/gib permanence | `proximity_kill_outcome` |
| carrier state | `proximity_carrier_event`, `proximity_carrier_kill`, `proximity_carrier_return` |
| vehicle state | `proximity_vehicle_progress`, `proximity_escort_credit` |
| pressure and team shape | `proximity_objective_focus`, `proximity_team_push`, `proximity_team_cohesion` |

### ET:L capture feasibility

This plan is implementable because the current Lua and parser already capture
most of the needed raw signals. The next work is mostly interpretation, not
new telemetry.

Useful existing Lua callbacks in `proximity/lua/proximity_tracker.lua`:

| Callback | Current value | ET:L model use |
| --- | --- | --- |
| `et_InitGame` | initializes map/round tracker state | reset graph and round metadata |
| `et_RunFrame` | frame-level sampling during live play | positions, objective proximity, vehicles, constructibles |
| `et_Damage` | damage context | engagement context and assist windows |
| `et_Obituary` | kill events | kill timeline, first blood, wave ledger |
| `et_ClientSpawn` | spawn/revive/tapout resolution | life boundaries, revive/gib permanence |
| `et_ClientCommand` | player commands and vsay hooks | optional comm/medic-call response signals |
| `et_WeaponFire` | shot and aim sampling | aim fingerprint, Greatshot context |
| `et_Print` | server text/event hooks | flag pickup/return and construction event fallback |
| `et_ShutdownGame` | final flush | close active carriers/lives and output files |

Current ET:L state reads already used or probed:

| Signal | Current approach | Notes |
| --- | --- | --- |
| player position | `ps.origin` via `gentity_get` | enough for pressure, paths, heatmaps |
| team/role | `sess.sessionTeam` | Axis/Allies role, not persistent logical team |
| class | `sess.playerType` | needed for engineer/medic weighting |
| stance/sprint/speed | `ps.pm_flags`, velocity, sprint stats | useful for movement style, not core objective model |
| view angles | `ps.viewangles` | useful for aim/hold analysis, runtime validated before use |
| spawn intervals | `g_redlimbotime`, `g_bluelimbotime` | core wave economy input |
| spawn offsets | `CS_REINFSEEDS` configstring | required for correct time-to-next-wave |
| carrier state | `ps.powerups` plus `et_Print` item text | good enough for doc/flag carry model |
| vehicle state | script mover/entity origin and health | good enough for escort progress |
| construction state | constructible/explosive/checkpoint entities | good enough for stage events, needs map verification |
| spawn select | `sess.spawnObjectiveIndex` probe | documented elsewhere, but may be unsupported on current build |

Feasibility by proposed feature:

| Feature | Feasibility now | Why |
| --- | --- | --- |
| stage splits | high for construction/carry/vehicle maps | current parser imports carrier, vehicle, construction, objective-run events |
| objective pressure seconds | high | `player_track.path` + objective zones + active stage graph |
| revive/gib permanence | high | `proximity_kill_outcome` already stores outcome and denied ms |
| wave ledger | high | spawn timing and kill outcomes already exist |
| mirror comparison | high | stopwatch pairs and `session_teams` already exist |
| xOV heuristic | medium-high | state vector is available, but weights need calibration |
| trained xOV | medium-late | needs validated stage splits and enough samples per map/stage |
| live director | medium-late | technically possible, but should wait for offline trust |
| fieldops/medic charge economy | low today | ability/charge events are not fully captured |
| exact spawn-choice analytics | uncertain | `sess.spawnObjectiveIndex` may not work on the deployed build |

Recommended capture strategy:

1. **Prefer existing event tables first.**
   - Do not add Lua capture for a signal that can be derived reliably from
     `player_track`, kill outcomes, carrier events, or construction events.

2. **Use Lua for state that disappears after the round.**
   - carrier state, constructible state, vehicle position, live spawn clocks,
     revive/gib resolution, and per-life paths are worth capturing in Lua.

3. **Keep high-frequency capture behind flags.**
   - `et_RunFrame` and trace-heavy logic can become expensive.
   - Keep objective/vehicle/aim samples at explicit intervals.
   - Continue the current pattern of feature flags and safe `gentity_get`
     wrappers.

4. **Treat server text as useful but not primary.**
   - `et_Print` is good for events that the engine announces clearly.
   - Prefer entity state or parsed structured output when possible.

5. **Backtest before public display.**
   - New stage/xOV labels should be admin-only until 10-20 real map pairs are
     reviewed.

The practical conclusion: build the Stopwatch Objective Model offline first.
Only add more Lua when the offline model proves that a missing signal blocks a
useful story.

### Stage Split Model

This should be the first ET:L-specific feature after the Good Night layer,
because it is visible, intuitive, and map-native.

Goal:

- for each map attempt, derive when each stage was reached or completed
- compare Round 1 vs Round 2
- compare current splits vs historical median for the map
- show where the attack gained or lost the map

Output example:

```json
{
  "map": "supply",
  "round_pair_id": "2026-06-27:supply:1",
  "stages": [
    {
      "stage_id": "depot_gate",
      "label": "Depot access",
      "r1_complete_ms": 142000,
      "r2_complete_ms": 119000,
      "delta_ms": -23000,
      "historical_median_ms": 135000,
      "winner": "r2"
    },
    {
      "stage_id": "documents_pickup",
      "label": "Documents",
      "r1_complete_ms": 411000,
      "r2_complete_ms": 462000,
      "delta_ms": 51000,
      "historical_median_ms": 430000,
      "winner": "r1"
    }
  ]
}
```

Implementation sketch:

1. Pair the rounds into `MapMatch`.
2. Load `objective_graphs/{map}.json`.
3. For each stage, find first matching success event.
4. If no success event exists, infer partial progress from carrier/vehicle/
   objective-focus data.
5. Store nothing at first. Serve computed-on-read behind an admin flag.
6. After validation, cache as a derived `session_stage_split` table.

This gives the group a sentence like:

```text
Supply was not lost on the documents. It was lost at depot access: R2 opened it
23s faster, then slowed down on the carry.
```

That is much better than "Player X had 31 kills".

### Time-to-Beat Pressure

Round 2 should get special handling. The game state is not simply "attack
winning" or "defense winning"; it is "attack is ahead of or behind the Round 1
clock".

Define:

```text
time_to_beat_ms = r1_actual_ms - r2_elapsed_ms
```

Then estimate required pace:

```text
required_stage_rate =
  remaining_stage_weight / max(time_to_beat_ms, 1)
```

Pressure labels:

| Label | Rule of thumb |
| --- | --- |
| comfortable | ahead of median split and one wave buffer remains |
| tight | can still finish, but only with one clean push |
| danger | needs stage completion before next defender wave |
| desperate | behind target pace; only a carrier/plant swing saves it |
| mathematically dead | target time already passed or impossible stage remaining |

This powers:

- live Tonight sentence
- Session Detail R2 chase graph
- story moment weighting
- Greatshot candidate prioritization

### Expected Objective Value (xOV)

xOV is the ET:L equivalent of xG/OBV/win probability. It should answer:

```text
Given this exact stopwatch state, how likely is the attacking team to complete
the current objective or finish the map within the required time?
```

Start with a transparent heuristic. Train later.

Heuristic v0:

```python
raw = (
    0.90 * stage_prior
  + 0.75 * time_pressure_score
  + 0.55 * alive_diff_score
  + 0.45 * wave_advantage_score
  + 0.45 * objective_pressure_score
  + 0.35 * team_shape_score
  + 0.35 * carrier_or_vehicle_score
  + 0.25 * spawn_control_score
)

xov = sigmoid(raw)
```

Component definitions:

| Component | Source | Meaning |
| --- | --- | --- |
| `stage_prior` | objective graph, historical stage completion | later stages and map-specific difficulty |
| `time_pressure_score` | R1/R2 timing and split medians | enough time remains for current stage |
| `alive_diff_score` | life timeline | attack has bodies alive near the stage |
| `wave_advantage_score` | spawn clocks | attack can act before defense wave arrives |
| `objective_pressure_score` | objective focus/push/position | players are actually threatening the active stage |
| `team_shape_score` | team cohesion/crossfire | attackers are grouped enough to convert |
| `carrier_or_vehicle_score` | carrier/vehicle tables | docs/tank are progressing |
| `spawn_control_score` | kill outcome/denied ms | defense is delayed or staggered |

Delta-xOV turns raw events into impact:

```text
delta_xov(event) = xOV(after_event_state) - xOV(before_event_state)
```

Examples:

- kill near active objective that is revived fast: small positive delta
- gib on engineer before plant during tight R2 chase: large negative delta for
  attack, large positive delta for defense
- field clear that allows engineer to plant: positive delta even if the killer
  did not touch the objective
- carrier killed 200 units from transmit with 20s left: huge defensive delta
- failed push that moves frontline and burns defender spawn: positive partial
  delta even if stage fails

Do not call xOV a precise model in the UI at first. Use it internally as a
ranking signal for moments and map explanations.

### Objective Pressure Seconds

Raw proximity can become much better if it is stage-aware.

Current simple version:

```text
objective_pressure_seconds =
  seconds within active_stage_zone
  * class_relevance_multiplier
  * contested_multiplier
  * team_support_multiplier
```

Multipliers:

| Multiplier | Example |
| --- | --- |
| class relevance | engineer near plant zone > soldier near plant zone |
| contested | pressure is worth more if defenders are alive nearby |
| team support | solo presence is less reliable than 3-player push |
| stage active | only count the stage that is currently actionable |
| time pressure | late R2 seconds are worth more |

This is where "think bigger than proximity" becomes real:

- not "Slomix stood near depot"
- but "Slomix created 41s of contested depot pressure during the only clean
  attack wave"

### Productive Failed Push

Older friend-group sessions need metrics that explain useful failure without
mocking anyone. ET:L has many pushes that fail but still matter.

Flag a push as productive when it fails to complete the stage but improves at
least one of these:

- xOV rises by a threshold
- frontline moves closer to active objective
- carrier moves closer to transmit
- vehicle advances
- defense burns spawn wave or field position
- next attack wave starts with better map control

Implementation:

```text
productive_failed_push =
  push.end_state.stage_completed == false
  and (
    delta_xov >= 0.08
    or delta_frontline_distance <= -600
    or carrier_distance_gain >= 800
    or denied_ms_created >= 12000
  )
```

UI tone:

```text
That push did not finish the stage, but it moved the next wave 18s closer to
success.
```

This is one of the most friendship-safe high-value ideas in the whole plan.

### Defense Hold Windows

Defense impact in ET:L is often invisible because good defense can look like
"nothing happened".

Define a defense hold window:

```text
defense_hold_window =
  active_stage unchanged
  and attack objective pressure drops
  and time_to_beat / round time burns materially
```

Credit defenders for:

- clearing the active objective zone
- gibbing high-value attackers
- delaying engineer arrival
- forcing carrier drop or return
- causing attack to miss a spawn-wave sync
- holding a choke while outnumbered

Output example:

```text
Defense held depot for 64s through two attack waves. The important part was not
frag count; it was denying the engineer entry until the next defender spawn.
```

### Revive/Gib Permanence Model

Raw kills are weak in ET:L. Permanent denial is strong.

Use:

- `proximity_kill_outcome.outcome`
- `proximity_kill_outcome.effective_denied_ms`
- `gibber_guid`
- `reviver_guid`
- `proximity_spawn_timing.time_to_next_spawn`

Derived labels:

| Label | Rule |
| --- | --- |
| soft kill | victim revived quickly |
| delay kill | victim revived, but wave/push timing was disrupted |
| permanent kill | gib/tapout/no revive before meaningful window |
| wave-denial kill | denied enough time to miss the next push |
| objective-denial kill | victim was class/carrier/stage-critical |

Moment weighting:

```text
kill_value =
  base_kill
  + denied_ms / 10000
  + stage_relevance
  + wave_miss_bonus
  + class_or_carrier_bonus
  - fast_revive_discount
```

This should become a core ingredient in Good Night, xOV, story ranking, and
Greatshot candidates.

### Wave-Cycle Objective Ledger

The existing optional wave fight ledger should become stage-aware:

```text
WaveCycle:
  round_id
  start_ms
  end_ms
  attacking_team
  defending_team
  active_stage_id
  first_blood
  kill_delta
  permanent_kill_delta
  denied_ms_delta
  objective_pressure_delta
  xOV_start
  xOV_end
  xOV_delta
  stage_completed
  cycle_winner
```

Cycle winner should not be only kill delta. Better v0:

```text
cycle_score(team) =
  0.35 * permanent_kill_delta
  + 0.25 * denied_ms_delta_norm
  + 0.25 * objective_pressure_delta
  + 0.15 * xOV_delta
```

For defense, invert objective pressure and xOV where appropriate:

```text
defense_cycle_score =
  0.35 * permanent_kill_delta
  + 0.25 * denied_ms_delta_norm
  + 0.25 * attack_pressure_reduction
  + 0.15 * (-attack_xOV_delta)
```

Use cases:

- first blood conversion
- stagger index
- push quality
- clutch/hold windows
- fatigue curve
- Greatshot clip selection

### Mirror Comparison

The most ET:L-native analysis is a mirror comparison:

```text
At the same stage and same elapsed time, which logical team was in the better
state?
```

Examples:

- R1 Team A reached documents at 4:12; R2 Team B reached documents at 4:45.
- R1 defense allowed two attack waves before gate; R2 defense allowed four.
- Team A had lower K/D but better stage splits.
- Team B had stronger defense hold windows but weaker carrier conversion.

Mirror comparison needs these joins:

```text
MapMatch
  -> R1 AttemptRound
  -> R2 AttemptRound
  -> ObjectiveStage splits
  -> WaveCycle ledger
  -> LogicalTeam resolver
```

This should be a Session Detail tab eventually:

```text
Map race
Stage | R1 Team A attack | R2 Team B attack | Delta | Why
Gate  | 2:22             | 1:59             | -23s  | faster engineer entry
Docs  | 6:51             | 7:42             | +51s  | carrier killed near exit
End   | 9:41             | 9:58             | +17s  | target defended
```

### Attack Reset Detection

A lot of ET:L value comes from knowing when a push is dead and regrouping. This
is especially useful for post-game explanation because it creates clean
moments.

Detect reset windows:

```text
attack_reset =
  attackers_alive_near_objective <= 1
  and recent_permanent_deaths >= 2
  and time_to_next_attack_wave <= regroup_window
  and objective_pressure_score falling
```

Outputs:

- "Attack reset cleanly" when the team avoids feeding.
- "Staggered attack" when players go one by one and burn time.
- "Hero delay" when one player survives long enough to keep pressure alive.

Public tone should praise good resets and funny hero delays, not shame bad
feeds.

### Map Fingerprint

Every map should eventually get a fingerprint card:

```text
MapFingerprint:
  map_name
  usual_completion_rate
  median_finish_time
  fullhold_rate
  slowest_stage
  fastest_stage
  most decisive stage
  common death zone before active objective
  best defender hold window type
  best attacker route pressure type
```

This can be computed from:

- stage splits
- objective pressure
- kill/death heatmaps
- carrier/vehicle/construction events
- team push direction and quality

Website output:

```text
Supply is usually decided before the documents. In Slomix sessions, depot
access explains more time difference than the final transmit.
```

This turns the archive into map lore, not just player stats.

### Proposed ET:L services

No code changes now, but when implementation starts, these should be small
services behind feature flags:

| Service | Responsibility | Inputs |
| --- | --- | --- |
| `stopwatch_domain.py` | pair rounds, resolve logical teams, expose `MapMatch` | `rounds`, `session_teams` |
| `objective_graph_loader.py` | load and validate map objective graphs | JSON graph files, objective assets |
| `stage_split_service.py` | derive stage completion/partial split timeline | graph, construction/carrier/vehicle events |
| `round_state_service.py` | build timestamped `RoundState` | all proximity/objective tables |
| `xov_service.py` | compute heuristic xOV and delta-xOV | `RoundState`, historical medians |
| `objective_pressure_service.py` | stage-aware pressure seconds and push summaries | focus, push, cohesion, player tracks |
| `wave_objective_ledger.py` | wave cycles with objective context | spawn timing, kill outcome, stage splits |
| `map_fingerprint_service.py` | map-level historical summaries | stage splits, ledger, heatmaps |

Recommended API sequence:

| Endpoint | First consumer |
| --- | --- |
| `GET /api/stats/session/{id}/map-race` | Session Detail |
| `GET /api/stats/round/{id}/stage-splits` | Session Detail / map page |
| `GET /api/stats/round/{id}/objective-pressure` | map visualization |
| `GET /api/stats/round/{id}/xov-timeline` | admin/beta chart |
| `GET /api/maps/{map}/fingerprint` | map page / Record Book |

### ET:L implementation phases

Do not try to build xOV first. Build the explainable scaffolding first.

**ETL-0: Map graph pilot**

- Choose 3 most-played maps.
- Create hand-reviewed objective graph JSON.
- Validate objective coordinates against map assets and live data.
- Add admin-only graph debug view or JSON endpoint.

Success criterion:

- owner can confirm that stages and labels match how the group talks about the
  map.

**ETL-1: Stage split extraction**

- Use objective events to produce R1/R2 stage split tables.
- Show only completed stages and obvious partials.
- Add historical median split where enough samples exist.

Success criterion:

- for 10 known map pairs, the split explanation matches human memory better
  than K/D summaries.

**ETL-2: Objective pressure seconds**

- Count stage-aware pressure from player tracks and objective zones.
- Add class relevance and contested/team support multipliers.
- Display on Session Detail and player cards.

Success criterion:

- non-fraggers, especially engineers/medics, receive credible positive moments.

**ETL-3: Wave-cycle objective ledger**

- Group fight windows by spawn waves.
- Add active stage and pressure/xOV deltas.
- Use internally for moment ranking first.

Success criterion:

- first-blood conversion and stagger debt can be computed per map/session.

**ETL-4: xOV heuristic**

- Build transparent heuristic with logged components.
- Use only for ranking and admin charts first.
- Compare xOV swings to actual stage completions and owner judgement.

Success criterion:

- top 5 xOV swings from a session are mostly moments a human agrees mattered.

**ETL-5: Mirror comparison and map fingerprint**

- Add R1/R2 stage race panel.
- Add map fingerprint page with decisive stages and common pressure zones.

Success criterion:

- Session Detail can explain why a map was won/lost without needing raw tables.

**ETL-6: Greatshot Objective Director**

- Feed high delta-xOV moments into Greatshot candidates.
- Prefer clips with visual explanation: carrier stop, engineer plant, hold
  window, wave wipe, clutch delay.

Success criterion:

- candidate clips feel like ET:L story moments, not random multikills.

### UI placement for ET:L-native features

Session Detail should eventually have this order:

1. Good Night summary
2. Map race card for each stopwatch pair
3. Five story moments
4. Objective pressure and stage splits
5. Player own-form cards
6. Raw stats tables

Map race card:

```text
Supply
Team A set 9:41. Team B chased to 9:58.

Where it moved:
Depot access    Team B +23s faster
Documents       Team A +51s better
Transmit        Team A held final 17s

Moment:
The carrier stop at 8:44 erased the only clean transmit wave.
```

Map page:

```text
Supply fingerprint
Most decisive stage: depot access
Common attack stall: documents exit
Best defender value: gib before first transmit wave
Best attacker value: engineer entry with 3-player support
```

Player profile:

```text
ET:L fingerprint
Best role: pressure engineer
Hidden value: productive failed pushes
Signature: late-stage carrier support
```

Discord digest:

```text
Good night on Supply: the scoreline says 2-0, but the story was the final
transmit hold. Team A defended the target by 17s after two missed carrier waves.
```

### What not to implement yet

- Fully trained xOV before the stage split data is trusted.
- Per-map ML with small samples.
- Public "bad reset" or "feed" labels.
- Permanent global objective-pressure leaderboard before tone review.
- Complex script parser before 3-5 hand-authored graphs prove value.
- Live director until offline Session Detail explanations are consistently
  good.

### Best near-term unique idea

The most unique Slomix feature is not a new rating. It is:

```text
Stopwatch Map Race Story
```

One card per map pair that explains:

- target time
- R2 chase result
- stage split delta
- the decisive wave
- the key objective-pressure player
- one Greatshot candidate
- one friendship-safe line of copy

This is specific to ET:L, specific to the Slomix data stack, and more useful
for a 40+/50+ friend group than another lifetime leaderboard.


## Proposed code architecture

No code should be added until Phase 0 backtesting confirms the tone and scores.
When implementation starts, keep the code behind small service modules and
existing routers.

### Backend services

| Proposed module | Responsibility | Depends on |
| --- | --- | --- |
| `website/backend/services/good_night_engine.py` | session-level Good Night Index and reason chips | rounds, session_round_scores, SessionDataService, StorytellingService |
| `website/backend/services/own_form_cards.py` | multi-metric player cards vs personal baseline | player_comprehensive_stats, storytelling/baseline.py |
| `website/backend/services/fair_team_suggester.py` | 2-3 friendship-safe team splits | availability, planning, skill ratings, duo history |
| `website/backend/services/story_worthiness.py` | rank candidate moments for digest/site/Greatshot | storytelling, proximity, Greatshot |
| `website/backend/services/memory_engine.py` | On This Night candidate scoring | sessions, records, awards, uploads |
| `website/backend/services/wave_fight_ledger.py` | optional derived wave/fight model | proximity_spawn_timing, kill_outcome, objectives |

### Router placement

Prefer extending existing routers:

| Endpoint | Router | Why |
| --- | --- | --- |
| `GET /api/stats/session/{id}/good-night` | `sessions_router.py` | session detail owns the feature |
| `GET /api/stats/session/{id}/player-cards` | `sessions_router.py` | successor to verdict strip |
| `GET /api/stats/session/{id}/moments` | `sessions_router.py` or `storytelling_router.py` | session-scoped story surface |
| `GET /api/stats/session/{id}/clip-candidates` | `sessions_router.py` or `greatshot.py` | bridge from moments to Greatshot |
| `GET /api/planning/{date}/team-suggestions` | `planning.py` | pre-game planning surface |
| `GET /api/memories/on-this-night` | new small router or `records_router.py` | estate/memory surface |
| `GET /api/stats/session/{id}/wave-fights` | `proximity_round.py`/new included router | only after validation |

### Frontend placement

| UI work | File/surface | First-pass scope |
| --- | --- | --- |
| Good Night card | `website/js/session-detail.js` | top of summary tab |
| Own-form player cards | `website/js/session-detail.js` | below moments / above raw player table |
| Team suggestions | `website/js/tonight.js`, `website/js/availability.js` | read-only cards with manual override note |
| Memory card | `website/js/home.js`, `website/js/record-book.js` | one card, deep-link to session |
| Moment list | `website/js/session-detail.js`, `website/js/story.js` | story-safe moment cards |
| Clip candidates | `website/js/session-detail.js`, `website/js/greatshot.js` | candidate cards, render status later |

### Suggested feature flags

Use env/config flags during rollout:

```text
GOOD_NIGHT_ENABLED=false
GOOD_NIGHT_PUBLIC=false
OWN_FORM_CARDS_ENABLED=false
TEAM_SUGGESTIONS_ENABLED=false
MEMORY_ENGINE_ENABLED=false
STORY_CLIP_CANDIDATES_ENABLED=false
WAVE_FIGHT_LEDGER_ENABLED=false
```

Rollout rule:

- enabled but not public -> admin/test view only
- public only after owner has reviewed examples from real sessions

## API data contracts

These are target payload shapes, not implemented yet.

### `GET /api/stats/session/{id}/good-night`

```json
{
  "status": "ok",
  "gaming_session_id": 123,
  "score": 86,
  "label": "Good night",
  "lede": "Close teams, 11 players, 3 comeback maps.",
  "components": {
    "balance": 82,
    "tension": 91,
    "attendance": 100,
    "story_density": 76,
    "flow": 94,
    "variety": 72,
    "participation": 61
  },
  "reason_chips": [
    {"kind": "balance", "label": "Close teams", "detail": "3 maps decided by under 45s"},
    {"kind": "attendance", "label": "11 players", "detail": "above usual Tuesday turnout"},
    {"kind": "comeback", "label": "3 comeback maps", "detail": "late swings after halftime"}
  ],
  "warnings": []
}
```

### `GET /api/stats/session/{id}/player-cards`

```json
{
  "status": "ok",
  "gaming_session_id": 123,
  "baseline": "last 10 previous sessions, per-player",
  "players": [
    {
      "guid": "abc123",
      "name": "carniel",
      "label": "Good night",
      "own_form_score": 68,
      "summary": "23 frags - 6 above your usual",
      "positive_lines": [
        "4 clean trades",
        "best carrier stop of the night"
      ],
      "private_focus": {
        "enabled": false,
        "line": null
      },
      "baseline_sessions": 10
    }
  ]
}
```

### `GET /api/planning/{date}/team-suggestions`

```json
{
  "status": "ok",
  "date": "2026-06-28",
  "players_considered": 10,
  "suggestions": [
    {
      "mode": "balanced",
      "title": "Balanced split",
      "cost": 0.18,
      "explanation": "Skill diff 2.8%, medics balanced, avoids last session stack.",
      "team_a": [{"user_id": 1, "name": "Player A", "guid": "abc"}],
      "team_b": [{"user_id": 2, "name": "Player B", "guid": "def"}],
      "reason_chips": [
        {"label": "Skill diff 2.8%"},
        {"label": "Fresh pairs"},
        {"label": "No hard stack"}
      ]
    }
  ],
  "manual_override": true
}
```

### `GET /api/stats/session/{id}/moments`

```json
{
  "status": "ok",
  "gaming_session_id": 123,
  "moments": [
    {
      "id": "derived:carrier-stop:456",
      "type": "carrier_stop",
      "title": "Carrier stopped at the door",
      "player_guid": "abc123",
      "player_name": "carniel",
      "round_id": 456,
      "map_name": "supply",
      "time_ms": 431000,
      "story_score": 84,
      "shame_safe": true,
      "explanation": "Carrier kill, high denied time, close map state.",
      "deep_link": "#/proximity/round/456"
    }
  ]
}
```

### `GET /api/memories/on-this-night`

```json
{
  "status": "ok",
  "date": "2026-06-28",
  "memory": {
    "title": "On this night in 2025",
    "summary": "11-player supply night, Team B won 3-2, SuperBoyy set a revive PB.",
    "memory_score": 79,
    "deep_link": "#/sessions/2025-06-28",
    "source": {
      "gaming_session_id": 77,
      "round_ids": [1001, 1002]
    }
  }
}
```

## Algorithm family 1: Good Night Index

Purpose: rate the **evening**, not the players.

This should be shown on Session Detail and Morning Digest:

> "Good Night: 86/100 - close teams, 11 players, 3 comeback maps, 7 story moments."

### Formula v0

All components normalized 0..100, with explicit explanation lines.

```text
good_night_index =
    0.25 * balance_score
  + 0.20 * tension_score
  + 0.15 * attendance_score
  + 0.15 * story_density_score
  + 0.10 * flow_score
  + 0.10 * variety_score
  + 0.05 * participation_score
```

### Components

**balance_score**

Measures whether teams were close enough to feel fair.

Inputs:
- map score difference from `session_round_scores` or session scoring payload
- R2 time-to-beat closeness from `rounds.actual_time`, `rounds.actual_duration_seconds`
- number of full holds vs stomps

Sketch:

```text
map_closeness = 100 - min(100, abs(team_a_maps - team_b_maps) * 25)
round_closeness = avg(100 - min(100, abs(r2_secs - r1_secs) / 6))
balance_score = 0.6 * map_closeness + 0.4 * round_closeness
```

**tension_score**

Measures whether the evening had suspense.

Inputs:
- close R2 chases
- lead changes in map score
- comeback wins
- hold-probability curve from `/stats/hold-probability`

Sketch:

```text
tension_score = clamp(
  close_maps * 18
  + comeback_maps * 22
  + final_map_decider_bonus
  - stomp_maps * 12,
  0, 100
)
```

**attendance_score**

For this community, "we got enough people" is a real win.

Inputs:
- player count from session detail
- availability threshold context
- duration target, e.g. 2h to 4h

Sketch:

```text
attendance_score =
  100 if players >= 10
  85  if players >= 8
  70  if players >= 6
  45  otherwise
```

**story_density_score**

Counts positive or interesting moments per hour.

Inputs:
- KIS spikes from `storytelling_kill_impact`
- PBs vs baseline
- close maps
- peer MVP votes
- objective runs, carrier kills, trades, crossfires
- Greatshot highlights

Sketch:

```text
story_density_score = clamp(moment_count / session_hours * 18, 0, 100)
```

**flow_score**

Avoids scoring a broken/import-corrupt evening too high.

Inputs:
- invalid rounds
- long gaps between rounds
- missing proximity coverage
- import warnings

Sketch:

```text
flow_score = 100
flow_score -= invalid_rounds * 20
flow_score -= long_gap_count * 10
flow_score -= missing_proximity_penalty
```

**variety_score**

Rewards evenings that do not feel repetitive.

Inputs:
- distinct maps
- mixed winners
- role/objective variety

**participation_score**

Bench/community layer.

Inputs:
- MVP votes cast
- bets placed
- challenge participation
- availability responses

### UI

Session Detail top panel:

```text
Good Night 86
Close teams | 11 players | 3 comeback maps | 7 moments
```

Expanded breakdown:

- Fairness: 82
- Tension: 91
- Attendance: 100
- Story: 76
- Flow: 94

Important copy rule:

- Do: "This was a good, close night."
- Do not: "Team B was bad."

### Good Night v0 pseudo-SQL

Session base:

```sql
SELECT
    r.gaming_session_id,
    COUNT(DISTINCT r.id) AS round_count,
    COUNT(DISTINCT pcs.player_guid) AS player_count,
    COUNT(DISTINCT r.map_name) AS map_count,
    MIN(r.round_date) AS first_round_date,
    MIN(r.round_start_unix) AS start_unix,
    MAX(r.round_end_unix) AS end_unix
FROM rounds r
JOIN player_comprehensive_stats pcs ON pcs.round_id = r.id
WHERE r.gaming_session_id = :gaming_session_id
  AND r.is_valid IS DISTINCT FROM FALSE
  AND pcs.time_played_seconds > 0
GROUP BY r.gaming_session_id;
```

Map/score closeness:

```sql
SELECT
    map_name,
    MAX(CASE WHEN round_number = 1 THEN actual_duration_seconds END) AS r1_seconds,
    MAX(CASE WHEN round_number = 2 THEN actual_duration_seconds END) AS r2_seconds,
    MAX(round_outcome) AS outcome
FROM rounds
WHERE gaming_session_id = :gaming_session_id
  AND is_valid IS DISTINCT FROM FALSE
GROUP BY map_name
ORDER BY MIN(id);
```

Story density candidates:

```sql
SELECT 'kis_spike' AS kind, killer_guid AS player_guid, map_name,
       MAX(total_impact) AS score
FROM storytelling_kill_impact ski
JOIN rounds r
  ON r.round_date = ski.session_date
 AND r.map_name = ski.map_name
WHERE r.gaming_session_id = :gaming_session_id
GROUP BY killer_guid, map_name
HAVING MAX(total_impact) >= :kis_threshold

UNION ALL

SELECT 'stagger' AS kind, killer_guid AS player_guid, map_name,
       SUM(effective_denied_ms) AS score
FROM proximity_kill_outcome pko
WHERE round_id IN (
    SELECT id FROM rounds WHERE gaming_session_id = :gaming_session_id
)
GROUP BY killer_guid, map_name
HAVING SUM(effective_denied_ms) >= :denied_threshold;
```

Participation:

```sql
SELECT
    (SELECT COUNT(*) FROM session_mvp_votes WHERE gaming_session_id = :gaming_session_id) AS mvp_votes,
    (SELECT COUNT(*) FROM parimutuel_bets b
      JOIN parimutuel_markets m ON m.id = b.market_id
      WHERE m.gaming_session_id = :gaming_session_id) AS bets
```

### Calibration set

Before public UI, produce a review table for 20-30 recent sessions:

| Session | Human memory | Score | Balance | Tension | Story | Notes |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 2026-06-xx | "great close night" | 88 | 83 | 91 | 79 | ok |
| 2026-06-yy | "stomp, but funny" | 58 | 30 | 42 | 86 | story too high? |

Owner should mark:

- `matches_memory`: yes/no
- `too_harsh`: yes/no
- `too_generous`: yes/no
- `bad_copy`: yes/no

Tune weights only after this review. Do not tune from a single favorite session.

## Algorithm family 2: Own-Form Index

Purpose: make every player card meaningful without humiliating lower-skill
players.

Existing seed:
- `/stats/session/{gaming_session_id}/verdicts` already compares DPM against
  each player's own previous sessions.
- `website/backend/services/storytelling/baseline.py` already has trailing
  baselines and `format_with_baseline`.

### Formula v1

Use rolling median and MAD where possible because small samples and outliers are
common.

```text
metric_z = (tonight_metric - median(last_10_metric)) / max(MAD(last_10_metric), floor)
own_form_score = 50 + 15 * weighted_avg(metric_z)
```

Recommended public metrics:

| Metric | Weight | Public reason |
| --- | ---: | --- |
| DPM vs own usual | 0.20 | easy to understand |
| Kills or KIS vs own usual | 0.20 | impact without pure K/D |
| Revives/support vs own usual | 0.15 | non-fragger recognition |
| Objective/carry/trade value | 0.20 | ET-specific contribution |
| Survival/death quality | 0.10 | only if framed gently |
| Team result context | 0.15 | do not over-credit farming |

### Labels

Use friendly labels:

- Great night
- Good night
- About usual
- Rough night
- First night / not enough baseline

Avoid "Subpar" in public if the tone feels too Leetify. "Rough night" is more
human.

### UI

Player card:

```text
carniel - Good night
23 frags - 6 above your usual
4 revives - around your usual
Best moment: carrier stop on supply
```

Private/opt-in coach line:

```text
Focus: your trade response was below your last-10 baseline.
```

Public digest should only include positive own-form lines.

### Own-form pseudo-SQL

Current session per player:

```sql
WITH current_session AS (
    SELECT
        pcs.player_guid,
        MAX(pcs.player_name) AS player_name,
        SUM(pcs.kills) AS kills,
        SUM(pcs.deaths) AS deaths,
        SUM(pcs.damage_given)::float
          / NULLIF(SUM(pcs.time_played_seconds) / 60.0, 0) AS dpm,
        SUM(pcs.revives_given) AS revives,
        SUM(pcs.damage_given) - SUM(pcs.damage_received) AS damage_delta
    FROM player_comprehensive_stats pcs
    JOIN rounds r ON r.id = pcs.round_id
    WHERE r.gaming_session_id = :gaming_session_id
      AND r.is_valid IS DISTINCT FROM FALSE
      AND pcs.time_played_seconds > 0
    GROUP BY pcs.player_guid
)
SELECT * FROM current_session;
```

Previous-session history:

```sql
WITH player_sessions AS (
    SELECT
        pcs.player_guid,
        r.gaming_session_id,
        SUM(pcs.kills) AS kills,
        SUM(pcs.damage_given)::float
          / NULLIF(SUM(pcs.time_played_seconds) / 60.0, 0) AS dpm,
        SUM(pcs.revives_given) AS revives,
        SUM(pcs.damage_given) - SUM(pcs.damage_received) AS damage_delta
    FROM player_comprehensive_stats pcs
    JOIN rounds r ON r.id = pcs.round_id
    WHERE pcs.player_guid = :player_guid
      AND r.gaming_session_id < :gaming_session_id
      AND r.is_valid IS DISTINCT FROM FALSE
      AND pcs.time_played_seconds > 0
    GROUP BY pcs.player_guid, r.gaming_session_id
    ORDER BY r.gaming_session_id DESC
    LIMIT 10
)
SELECT * FROM player_sessions;
```

Storytelling/KIS supplement:

```sql
SELECT
    killer_guid AS player_guid,
    SUM(total_impact) AS kis,
    SUM(CASE WHEN is_carrier_kill THEN 1 ELSE 0 END) AS carrier_kills,
    SUM(CASE WHEN is_crossfire THEN 1 ELSE 0 END) AS crossfire_kills
FROM storytelling_kill_impact
WHERE session_date = :session_date
GROUP BY killer_guid;
```

### Own-form metric dictionary

| Metric | Data source | Public? | Notes |
| --- | --- | --- | --- |
| kills above usual | PCS | yes | simple and intuitive |
| DPM above usual | PCS | yes | already in verdict endpoint |
| revives above usual | PCS | yes | support recognition |
| damage delta vs usual | PCS | maybe | useful but can feel harsh |
| KIS vs usual | storytelling | yes | better than kills when explained |
| trade response | proximity_lua_trade_kill | yes if positive | avoid negative public framing |
| denied seconds | proximity_kill_outcome | yes | ET-specific and satisfying |
| objective helper | objective/carrier tables | yes | important for non-fraggers |
| deaths above usual | PCS | private only | can be a focus line |
| late fatigue drop | PCS/round timing | private/aggregate only | avoid public blame |

### Player-card selection rules

For each player:

1. Compute all possible positive deltas.
2. Pick the top 1-2 positive lines.
3. If no positive line exists, use a neutral line:
   - "About usual"
   - "Solid support presence"
   - "Played X maps, helped keep teams full"
4. Only include private focus if:
   - user is logged in and linked
   - opt-in is enabled
   - line passes tone filter

Public fallback matters. Everyone who played should get a card that does not
feel like a punishment.

## Algorithm family 3: Friendship-Safe Team Balancer

Purpose: reduce organizer work and stomp risk while keeping manual control.

This should plug into Tonight/Planning, not replace captains.

Existing anchors:
- `website/backend/routers/availability.py`
- `website/backend/routers/planning.py`
- `website/migrations/007_planning_room_mvp.sql`
- `player_skill_ratings`, `player_skill_history`
- existing captain draft direction in `docs/WEBSITE_FIRST_ROADMAP_2026-06.md`

### Inputs

- confirmed/available players
- ET Rating and confidence
- recent own-form trend
- role/class tendencies when available
- historical duo synergy
- recent team repetition
- manual locks: "these two must play together", "captains fixed", "sub later"

### Objective function

```text
team_cost =
    0.35 * skill_delta
  + 0.15 * form_delta
  + 0.15 * role_delta
  + 0.10 * duo_stack_penalty
  + 0.10 * repeat_team_penalty
  + 0.10 * stomp_risk
  - 0.05 * novelty_bonus
```

Lower is better.

### Stomp risk

Estimate from historical sessions:

```text
stomp_risk = P(abs(map_score_delta) >= 3 | rating_delta, player_count, map_pool)
```

v0 can be heuristic:

```text
stomp_risk = clamp(rating_delta / 18 + confidence_gap / 30, 0, 1)
```

### Output modes

The UI should show 2-3 options:

1. **Balanced** - lowest predicted stomp risk.
2. **Fresh Mix** - avoids same pairs from last session.
3. **Captain Draft Seed** - balanced pool split suggestion, captains can override.

Copy:

```text
Balanced split
Skill diff 2.8%, medics balanced, avoids last session's stack.
```

Do not show:

```text
Team A wins 78%.
```

For friends, "fair enough" is better than deterministic win prediction.

### Team suggestion algorithm sketch

For N players, brute force combinations are fine for typical 6-12 player nights.
For 12 players, unique balanced splits are manageable if symmetric duplicates are
removed.

```python
players = confirmed_players
target_size = len(players) // 2

best = []
for team_a in combinations(players, target_size):
    team_b = players - team_a
    if canonical_duplicate(team_a, team_b):
        continue
    cost = team_cost(team_a, team_b)
    best.append((cost, team_a, team_b))

return top_k_diverse(best, k=3)
```

Cost components:

```text
skill_delta = abs(sum(skill_a) - sum(skill_b)) / total_skill
form_delta = abs(sum(recent_form_a) - sum(recent_form_b)) / total_form
role_delta = role_distribution_distance(team_a, team_b)
duo_stack_penalty = sum(strong_pair_score(pair) for pairs inside same team)
repeat_team_penalty = overlap_with_last_session_same_side
stomp_risk = heuristic_or_model(skill_delta, confidence_gap)
novelty_bonus = new_pairings_count / possible_pairings
```

Role distribution can start crude:

- high revive/support tendency
- high objective tendency
- high frag/entry tendency
- high defense/anchor tendency

Do not overfit classes yet; players change class and ET roles are fluid.

### Team suggestion pseudo-SQL anchors

Confirmed players:

```sql
SELECT user_id, user_name, status
FROM availability_entries
WHERE entry_date = :date
  AND status IN ('LOOKING', 'AVAILABLE', 'MAYBE');
```

Linked player GUID:

```sql
SELECT upl.user_id, upl.player_guid
FROM user_player_links upl
WHERE upl.user_id = ANY(:user_ids);
```

Skill:

```sql
SELECT player_guid, et_rating, confidence
FROM player_skill_ratings
WHERE player_guid = ANY(:guids);
```

Recent pair history:

```sql
SELECT r.gaming_session_id, st.team_name, unnest(st.player_guids) AS player_guid
FROM session_teams st
JOIN rounds r ON r.gaming_session_id = st.gaming_session_id
WHERE r.round_date >= CURRENT_DATE - INTERVAL '60 days';
```

If `session_teams.player_guids` are short GUIDs, normalize before scoring.

## Algorithm family 4: Story Worthiness Score

Purpose: select digest lines, Session Detail moments, and Greatshot candidates.

Existing anchors:
- `StorytellingService` mixins
- `storytelling_kill_impact`
- `greatshot/highlights/detectors.py`
- `website/backend/routers/greatshot.py`
- proximity objective/carrier/trade/crossfire tables

### Formula

```text
story_score =
    0.25 * impact
  + 0.20 * rarity
  + 0.15 * personal_context
  + 0.15 * objective_context
  + 0.10 * rivalry_or_duo_context
  + 0.10 * visual_clip_potential
  + 0.05 * humor_or_memory_context
  - shame_risk
```

### Positive moment types

- PB or near-PB
- comeback map
- close R2 chase
- carrier stop
- objective run
- big revive chain
- clutch hold until spawn wave
- clean trade sequence
- high crossfire/teamplay moment
- rare weapon/meme moment
- first session back after long absence, if framed positively

### Shame-risk filter

Never auto-push:

- worst K/D
- worst DPM
- most deaths
- "caused loss"
- absence shame
- late-night fatigue blame

Private opt-in only:

- focus line
- rough-night diagnosis
- personal weakness

### Greatshot fusion v0

Do not start by promising rendered MP4s for everything. Start with candidates:

```text
moment -> find matching demo/upload -> candidate timestamp -> queue render only if demo exists
```

Candidate example:

```text
Clip candidate: 3 kills + carrier stop at 07:42 on supply.
```

This can reuse the Greatshot highlight shape:

- `type`
- `player`
- `start_ms`
- `end_ms`
- `score`
- `meta_json`

Future table could be `story_clip_candidates`, but v0 can be computed and stored
inside existing Greatshot metadata only after a working candidate flow is proven.

### Story candidate sources

Candidate generator should merge multiple evidence streams, then de-duplicate by
round/time/player.

| Candidate type | Source | Public default | Greatshot potential |
| --- | --- | --- | --- |
| KIS spike | `storytelling_kill_impact` | yes | high |
| multi-kill | Greatshot analysis events | yes | high |
| carrier stop | `proximity_carrier_kill` | yes | high |
| carrier run | `proximity_carrier_event` | yes | medium |
| objective run | `proximity_objective_run` | yes | medium |
| revive swing | PCS / proximity revive | yes if positive | medium |
| trade chain | `proximity_lua_trade_kill` | yes | medium |
| crossfire | `proximity_crossfire_opportunity` | yes | medium |
| stagger | `proximity_kill_outcome` + spawn timing | yes | medium |
| first blood conversion | wave ledger later | yes | medium |
| rough death | proximity/PCS | no | no |

### Story candidate pseudo-SQL

KIS spikes:

```sql
SELECT
    'kis_spike' AS type,
    ski.killer_guid AS player_guid,
    MAX(ski.killer_name) AS player_name,
    ski.map_name,
    ski.round_number,
    MAX(ski.kill_time_ms) AS time_ms,
    MAX(ski.total_impact) AS raw_score,
    jsonb_build_object(
      'carrier', bool_or(ski.is_carrier_kill),
      'crossfire', bool_or(ski.is_crossfire),
      'push', bool_or(ski.is_during_push)
    ) AS meta
FROM storytelling_kill_impact ski
JOIN rounds r
  ON r.round_date = ski.session_date
 AND r.map_name = ski.map_name
WHERE r.gaming_session_id = :gaming_session_id
GROUP BY ski.killer_guid, ski.map_name, ski.round_number
HAVING MAX(ski.total_impact) >= :threshold;
```

Carrier/objective:

```sql
SELECT
    'carrier_stop' AS type,
    killer_guid AS player_guid,
    killer_name AS player_name,
    map_name,
    round_number,
    kill_time AS time_ms,
    80 + LEAST(carrier_distance_at_kill / 100.0, 20) AS raw_score,
    jsonb_build_object('carrier_guid', carrier_guid, 'flag_team', flag_team) AS meta
FROM proximity_carrier_kill
WHERE round_id IN (
    SELECT id FROM rounds WHERE gaming_session_id = :gaming_session_id
);
```

Denied/stagger:

```sql
SELECT
    'denied_time' AS type,
    killer_guid AS player_guid,
    MAX(killer_name) AS player_name,
    map_name,
    round_number,
    MIN(kill_time) AS time_ms,
    SUM(effective_denied_ms) / 1000.0 AS raw_score,
    jsonb_build_object('denied_ms', SUM(effective_denied_ms)) AS meta
FROM proximity_kill_outcome
WHERE round_id IN (
    SELECT id FROM rounds WHERE gaming_session_id = :gaming_session_id
)
GROUP BY killer_guid, map_name, round_number
HAVING SUM(effective_denied_ms) >= :threshold_ms;
```

### De-duplication

Many events describe the same moment. Merge candidates when:

- same round
- same player or same involved player set
- timestamps within 8-12 seconds
- compatible types, e.g. `kis_spike` + `carrier_stop`

Merged candidate:

```json
{
  "types": ["kis_spike", "carrier_stop"],
  "story_score": 91,
  "title": "Carrier stop became the map swing",
  "sources": ["storytelling_kill_impact", "proximity_carrier_kill"]
}
```

### Greatshot timestamp matching

Possible timestamp matching path:

1. Candidate has `round_id`, `map_name`, `round_start_unix`, `time_ms`.
2. Greatshot crossref finds demo with matching date/map/player.
3. Convert candidate time to demo-relative time.
4. Add pre/post padding, e.g. `start_ms = time_ms - 8000`, `end_ms = time_ms + 12000`.
5. Mark confidence:
   - high: same round + player + timestamp alignment
   - medium: same map/session + player
   - low: same day only; do not render automatically

Do not auto-render low-confidence clips.

## Algorithm family 5: Evening Arc / Fatigue Curve

Purpose: match the reality of 3-4 hour relaxed evening sessions.

This is a social/memory feature, not a coaching cudgel.

### Segments

```text
warmup      = first 20-30 minutes
prime time  = middle 60-120 minutes
late chaos  = final hour or after 23:30 local
```

### Metrics

- team balance by segment
- close maps by segment
- player own-form by segment
- aim/accuracy drop only if framed gently
- silly moments or rare weapons in late chaos

### UI

Session Detail:

```text
Evening arc
Warmup: Allies opened strong
Prime time: closest maps of the night
Late chaos: 4 knife/panzer moments, 2 comeback attempts
```

Avoid:

```text
Everyone got worse after 23:30.
```

## Algorithm family 6: On This Night Memory Engine

Purpose: preserve the estate and pull old memories back into Discord.

Existing anchors:
- `bot/services/on_this_day_service.py`
- `bot/cogs/on_this_day_cog.py`
- `docs/WEBSITE_FIRST_ROADMAP_2026-06.md` S6
- `Record Book`, `Hall of Fame`, `Wrapped`

### Candidate scoring

```text
memory_score =
    0.25 * date_match
  + 0.20 * age_bonus
  + 0.20 * positivity
  + 0.15 * people_overlap
  + 0.10 * map_or_rivalry_overlap
  + 0.10 * rarity
  - sensitivity_penalty
```

### Candidate types

- same calendar day from prior years
- old PB
- first recorded session for a player
- old rivalry matchup
- old map comeback
- old LAN/photo upload
- old Greatshot clip
- season award anniversary

### Discord copy

```text
Na današnji dan 2025:
11-player supply night, Team B won 3-2, SuperBoyy set a revive PB.
Full memory -> slomix.fyi/#/sessions/...
```

Need sensitivity rule:

- skip negative memories
- skip users who opted out
- prefer team/story memories over individual embarrassment

## Algorithm family 7: Duo Chemistry without toxicity

Purpose: social fuel, not hard truth.

Existing anchors:
- `website/backend/services/storytelling/synergy.py`
- `website/backend/routers/rivalries_router.py`
- `bot/cogs/matchup_cog.py`
- `proximity_crossfire_opportunity`
- `proximity_lua_trade_kill`

### Shrinkage

Small sample pair stats lie, so every pair score needs shrinkage:

```text
display_score = raw_score * n / (n + 10)
```

Where `n` can be shared rounds or shared sessions.

### Duo labels

Prefer qualitative labels:

- Reliable pair
- Chaos duo
- Objective helpers
- Trade buddies
- Crossfire pair
- Comeback pair
- Rare but dangerous

Avoid:

- "bad pair"
- "do not play together"
- "dragging down"

### UI

Player Profile:

```text
Best recent duo: carniel + Zlatorog
7 shared maps, +12% trade response vs baseline.
```

Session Detail:

```text
Duo moment: two crossfires converted on goldrush.
```

## Algorithm family 8: Gentle Weekly Challenges

Purpose: one-click, low-pressure participation for active players and bench.

Existing anchors:
- `weekly_challenges`
- `website/backend/routers/challenges_router.py`
- morning digest/home

### Challenge categories

Prefer baseline-relative or role-based:

- most above own revive baseline
- best comeback contribution
- cleanest trade night
- objective helper
- most improved vs last 10
- best support moment
- rare weapon night, if explicitly fun

Avoid:

- most kills every week
- lowest deaths
- anything that repeatedly rewards only top fraggers

### Challenge generator idea

```text
candidate_challenge_score =
    fairness
  + data_availability
  + novelty
  + role_diversity
  + story_potential
  - repeat_penalty
```

## Optional advanced layer: Wave Fight Ledger

This is still valuable, but it should serve the Good Night Engine rather than
become the product itself.

Purpose:
- explain first blood conversion
- explain stagger value
- support live "director" lines
- identify Greatshot clip candidates

### v0 derivation

Use existing proximity data:

- `proximity_spawn_timing.kill_time`
- `enemy_spawn_interval`
- `time_to_next_spawn`
- `killer_reinf`, `victim_reinf`
- `proximity_kill_outcome.effective_denied_ms`
- `round_id`

Sketch:

```text
wave_bucket = floor((kill_time + phase_offset) / enemy_spawn_interval)
fight_window = [bucket_start - 5s, bucket_end + 5s]
```

Per fight:

- first blood team/player
- kills for each side
- denied seconds
- trade count
- objective event count
- winner by weighted score

Weighted fight score:

```text
fight_score(team) =
  kills
  + effective_denied_ms / wave_ms
  + objective_event_weight
  + trade_bonus
```

### UI

Session Detail:

```text
Fight strip: each chip is a wave fight
green = Team A won, red = Team B won, icons = first blood/objective/stagger
```

Tonight:

```text
Director line: Team A won 4 of last 5 waves near objective.
```

Important caveat:

Wave logic needs validation against real ET stopwatch behavior. Backtest on
recent sessions before showing public claims.

## Website audit and community revamp research

No runtime code changes should happen during this planning pass. The website
revamp should be implemented later as one deliberate batch after the product
shape is agreed.

### Current website audit

The website currently has two frontends living together:

- legacy route system in `website/index.html` and `website/js/*.js`
- modern React/Vite route system in `website/frontend/src/pages/*.tsx`

The modern route host already includes a React `Home` page, and
`website/frontend/src/runtime/catalog.ts` marks `home` as modern. But the live
route registry still treats `home` as legacy in `website/js/route-registry.js`.
So the visible homepage is still the large legacy homepage.

That explains why the homepage feels duplicated. The first page is trying to be
all of these at once:

- marketing hero
- player search
- live server/voice status
- next-session planner
- last-session card
- movers card
- challenge card
- season card
- overview stat grid
- insights charts
- current season widget
- recent matches widget
- quick leaders widget
- retro-viz teaser

Startup loading reinforces the duplication. `website/js/app.js` loads these
home-related jobs when legacy Home is enabled:

- `loadHomePulseCards`
- `loadOverviewStats`
- `updateLiveSession`
- `loadQuickLeaders`
- `loadRecentMatches`
- deferred `loadInsightsCharts`
- deferred `loadSeasonInfo`
- deferred `loadLastSession`
- deferred `loadPredictions`
- deferred `loadMatchesView`
- deferred season leaders/activity/summary loaders

The result is not one homepage story. It is multiple dashboards stacked on top
of each other.

### Concrete duplication found

| Concept | Currently appears as | Problem |
| --- | --- | --- |
| last session | pulse card, recent matches, detailed last-session loader, sessions archive CTA | same user question answered several times |
| session summary | last-session card and older session details/charts | users see repeated counts before deeper context |
| season | home season card and Current Season widget | duplicated leaders/dates/progress |
| community activity | overview stat grid, insights strip, season activity | too many global counters |
| live/today status | home tonight card, server status, voice status, availability page | spread across too many panels |
| leaderboards | quick leaders, leaderboards page, season leaders | top performers repeated on Home |
| archive | recent matches, Sessions 2.0, Record Book, Retro Viz teaser | archive paths compete with each other |

### Deep website audit: route, navigation, and data ownership

This audit treats the website as a product for returning community members, not
as a generic stats landing page. The practical risk is that the current site
already has a lot of good pieces, but they compete for attention because route
ownership, page ownership, and API ownership are not aligned.

#### Audit method

- Read the live hash router in `website/js/route-registry.js`.
- Read the React route catalog and host in `website/frontend/src/runtime/catalog.ts`
  and `website/frontend/src/route-host.tsx`.
- Read the visible legacy homepage and navigation in `website/index.html`.
- Read startup loaders in `website/js/app.js`.
- Read homepage/session loaders in `website/js/home.js`, `website/js/sessions.js`,
  `website/js/leaderboard.js`, `website/js/live-status.js`, and `website/js/tonight.js`.
- Checked backend endpoint ownership from router references.
- Compared the current shape against stable UX principles: NN/g information
  architecture mistakes, NN/g usability heuristics, and Material navigation
  guidance.

#### Severity findings

| Severity | Finding | Evidence | Why it matters |
| --- | --- | --- | --- |
| Critical | There are two route truths. | `route-registry.js` keeps most routes legacy; `runtime/catalog.ts` marks many as modern. | A later revamp can accidentally switch a route to modern because a React page exists, while live routing and legacy loaders still assume the old world. |
| Critical | Home is not a single product decision. | Legacy Home loads pulse cards, overview, live server, voice, quick leaders, recent matches, insights, season, last session, predictions, and matches. | The page answers the same user question several ways and makes every widget feel less important. |
| High | Desktop and mobile navigation teach different mental models. | Desktop has Stats dropdown plus Tonight, Proximity, Greatshot, Uploads, `#ETL`, About. Mobile has Home, Session, Me, Boards. | Older returning players will form habits on one device that do not transfer to the other. |
| High | Some labels are internal or ambiguous. | `#ETL` means availability/planning; `About` opens admin; `Sessions / Stats` mixes archive and analytics. | Labels should match how the group talks: "Tonight", "Last Session", "Archive", "My Stats", "Records". |
| High | Home uses heavy/archive endpoints for preview jobs. | Legacy deferred Home calls `/stats/last-session`, `/stats/matches`, season summary, activity, leaders, and predictions. | Home becomes slower and harder to reason about than it needs to be. Deep archive endpoints should belong to archive/detail pages. |
| Medium | Modern Home exists, but is not automatically the final answer. | React `Home.tsx` is closer to "latest session first", but still has visible planning copy and repeats leaders/trends. | Switching the route alone would reduce some legacy duplication but would not finish the product design. |
| Medium | README/product docs are stale. | `website/README.md` says Vanilla JS + Tailwind and 5 routers, while the app is now hybrid React/Vite plus many routers. | New implementation work will be slower and riskier because architecture docs do not match reality. |
| Medium | Visual language is more marketing/glass than operational community dashboard. | Large `TRACK YOUR LEGACY` hero, glow gradients, many `glass-card`/`glass-panel` sections, big rounded panels. | This community already knows the site. The page should be faster to scan than a public landing page. |
| Medium | Game assets are underused on Home. | The repo has map levelshots, team icons, class icons, weapon icons, and medals under `website/assets/game/*`. | ET:L is map/objective/session memory. The archive and recap should feel game-specific, not like generic SaaS stats. |

#### Route truth inventory

The most important implementation lesson: do not start by editing the visual
page. First make a conscious route ownership decision.

| Area | Live registry state | React/catalog state | Audit decision |
| --- | --- | --- | --- |
| `home` | Legacy in `route-registry.js`; legacy startup loaders run. | Marked modern in `runtime/catalog.ts`; React Home chunk exists. | Treat Home as a deliberate migration, not a cleanup. Switch only after Home V2 content and smoke tests are ready. |
| `leaderboards`, `maps`, `profile`, `records`, `awards`, `weapons` | Mostly legacy in live routing. | Marked modern in catalog and lazy route host. | Catalog is ahead of production routing. Document as planned migration, not current truth. |
| `sessions2`, `session-detail` | Legacy in live routing. | Marked modern in catalog and React pages exist. | These are archive-critical. Do not migrate in the same batch as Home unless smoke coverage is strong. |
| `proximity` | Main Proximity route is legacy. | Proximity page exists; deep player/replay/team routes are modern. | Keep Proximity as a tool surface. Do not put raw Proximity first on Home; extract only interpretable summaries later. |
| `skill-rating` | Modern in live routing. | Modern in catalog. | This is the cleanest modern route precedent. Use it as the migration pattern reference. |
| `availability`, `uploads`, `greatshot`, `admin` | Legacy in live routing. | Modern pages/chunks exist. | These are write/auth-heavy or operational; migrate after read-only routes are stable. |

Implementation implication: the `home` route registry mode is the clean cutpoint.
`app.js` checks `legacyHomeEnabled`; if Home becomes modern, legacy startup jobs
such as `loadHomePulseCards`, `loadOverviewStats`, `loadQuickLeaders`,
`loadRecentMatches`, and deferred Home jobs stop running. That is good, but it
also means the modern Home must intentionally replace only the jobs we still
want.

#### Modern route host risk

The modern route host is useful but sharp:

- `modern-route-host.js` hides all existing legacy children with
  `data-legacy-hidden` when a modern route mounts.
- If the modern bundle fails to load, users see "Modern Route Offline" inside
  the page, not the legacy fallback content.
- The cache-bust version in `modern-route-host.js` is separate from the built
  chunk names under `website/static/modern/`.
- React pages are lazy-loaded through one route host, so a broken shared chunk
  can break multiple pages.
- The same DOM view can contain legacy HTML and a modern mount root over time,
  which means smoke tests must include route switching, not only direct load.

Recommended migration rule: for Home, build and verify the modern route, update
the route registry mode in one commit, smoke direct `/`, `#/home`, `#/sessions2`,
`#/profile`, `#/tonight`, and then check that legacy Home network calls are no
longer firing.

#### Homepage data ownership map

The homepage should become a thin orchestrator. It should not be the owner of
deep archive analytics.

| Current loader or hook | Current endpoint(s) | Current Home role | Recommended owner | Homepage V2 treatment |
| --- | --- | --- | --- | --- |
| `loadHomePulseCards` | `/availability`, `/sessions?limit=1`, `/skill/movers` | Next session, last session, movers | Home pulse / Tonight / Players | Keep only next session and last session. Move movers to Players or Leaderboards. |
| `loadHomeTonightCard` | `/stats/tonight` | Live-session card | Tonight | Keep as one compact live strip when active; otherwise hide or show next planned night. |
| `loadOverviewStats` | `/stats/overview` | Global counters | Home pulse / Records | Keep 3-4 community pulse numbers maximum. Move full counters to Records/Archive. |
| `updateLiveSession` and live polling | `/live-status`, `/voice-activity/current`, `/voice-activity/history` | Server and voice cards | Tonight / status strip | Collapse to one status strip. Do not show two large expandable cards on Home. |
| `loadQuickLeaders` | quick leaders endpoint | Top performers | Players / Leaderboards | Remove from Home except maybe one "in form" teaser after Home is calmer. |
| `loadRecentMatches` | `/stats/matches?limit=5` | Recent rounds/matches | Sessions archive | Remove from Home. Last session preview already covers this question. |
| `loadLastSession` | `/stats/last-session` | Heavy last-session widget/details | Session Detail | Do not use on Home. Use `/stats/sessions?limit=1` for preview and deep-link to detail. |
| `loadSeasonInfo` and season loaders | `/seasons/current`, `/seasons/current/leaders`, `/seasons/current/summary` | Season card, season widget, leaders | Records / Leaderboards | Keep one season chip only. Move leaders and summary out of Home. |
| `loadInsightsCharts` | trends/history endpoints | Activity chart strip | Records / Community rhythm | Optional below fold, but only one chart if kept. |
| `loadPredictions` | predictions endpoints | Forecast/match prediction | Tonight or experimental Tools | Do not load on Home until prediction UX is trusted and useful. |

This suggests a Home API budget:

- Always: `/live-status`, `/stats/sessions?limit=1`, `/stats/overview`.
- Conditional if relevant: `/stats/tonight` only during or near a live session.
- Optional: `/availability?from=...&to=...` for the next planned night.
- Avoid on Home: `/stats/last-session`, `/stats/matches`, season leaders,
  full season summary, full activity calendar, raw Proximity round payloads.

#### Homepage content inventory and pruning

Keep the homepage focused on the old-friend evening loop:

1. Are we live or playing soon?
2. What happened last time?
3. Where do I click for my stats?
4. Where is the archive?
5. What memory is worth revisiting?

First-pass Home V2 modules:

| Module | Keep? | Reason |
| --- | --- | --- |
| Compact live/planning strip | Yes | Answers "are we playing tonight?" immediately. |
| Last session hero | Yes | This is the most common returning-member question. |
| Player lookup / My Stats | Yes | Fast personal entry point. |
| Session archive CTA | Yes | Old nights are a core community value. |
| One memory/record teaser | Yes, small | Adds personality without turning Home into a wall of stats. |
| Full quick leaders | No | Leaderboards already own competition. |
| Recent matches list | No | Duplicates last session and archive. |
| Large overview stat grid | No | Keep a smaller pulse only. |
| Two large live server/voice cards | No | Collapse into one strip or Tonight page. |
| Season card plus season widget | No | Keep one season chip; Records/Leaderboards own the rest. |
| Retro Viz teaser | No on Home | Move under Tools/Archive unless a specific session memory uses it. |
| Raw Proximity panels | No | Translate Proximity into simple stories before surfacing. |

#### Explicit Home hero decision

Remove the large marketing hero headline `TRACK YOUR LEGACY` from the first
viewport.

Reason:

- The visitors are already community members; they do not need a pitch.
- The phrase takes the most valuable screen space on desktop and mobile.
- It pushes the useful community information down: tonight status, last
  session, player lookup, archive, and memory/records.
- It makes the site feel like a product landing page instead of the group's
  evening clubhouse.

Replacement:

- Keep `slomix.fyi` in the nav/brand area.
- Use a compact Home header such as "Tonight", "Last Session", or no big
  headline at all.
- Put the first viewport budget into:
  - live/playing-soon strip
  - last-session recap
  - Find My Stats search
  - archive/records entry

This is a product decision, not just a style preference: removing the hero is
how Home becomes a community dashboard.

#### Desktop navigation audit

Current desktop nav:

- Logo -> Home
- Stats dropdown -> Smart Stats, Sessions / Stats, Replay, Rivalries,
  Record Book, ET Rating
- Top-level -> Tonight, Proximity, Greatshot, Uploads, `#ETL`, About

Problems:

- The Stats dropdown mixes archive, diagnostics/story, replay, rivalries,
  records, and skill rating. These are not one user task.
- Proximity is top-level but Records is hidden, even though Records is easier
  for casual returning players to understand.
- `#ETL` is not self-explanatory for availability/planning.
- `About` maps to admin, which is an operational/admin concept, not public
  website information.
- Greatshot and Uploads are related and should probably share a Tools/media
  area.

Recommended desktop nav:

| Top-level item | Owns | Notes |
| --- | --- | --- |
| Home | daily hub | Keep first. |
| Tonight | live status, availability, planning, team draft | Rename `#ETL` into Tonight/Planning language or place Planning under Tonight. |
| Sessions | latest session, archive, session detail | This should be more important than generic Stats. |
| Players | player lookup, profiles, leaderboards, skill rating | People remember each other by names, not stat categories. |
| Records | record book, hall of fame, map records, season records | Easy community engagement surface. |
| Tools | Proximity, Greatshot, Uploads, Replay, Retro Viz, Admin if allowed | Keeps specialist tools available without overwhelming Home. |

If space is tight, use: Home, Tonight, Sessions, Players, Records, Tools.

#### Mobile navigation audit

Current mobile bottom nav:

- Home
- Session -> `sessions2`
- Me -> linked profile or availability when unlinked
- Boards -> leaderboards

Problems:

- Mobile has no explicit Tonight, even though the group plays evening sessions.
- Mobile has no explicit Records/Archive path.
- "Session" means archive in code, but a user may expect current/last session.
- "Boards" is a leaderboard term, not a community memory term.
- The unlinked "Me" fallback to availability is useful technically, but
  conceptually surprising.

Recommended mobile bottom nav:

| Slot | Label | Destination | Reason |
| --- | --- | --- | --- |
| 1 | Home | Home | daily hub |
| 2 | Tonight | Tonight/planning | most time-sensitive mobile task |
| 3 | Last | latest session detail or sessions2 | fast recap after a night |
| 4 | Me | linked profile/login/linking | personal stats |
| 5 if allowed | Records | record book | community memory |

If only four tabs are acceptable: Home, Tonight, Last, Me. Put Records as a
prominent Home/Archive CTA rather than a bottom tab.

#### Page ownership after revamp

| Page | Future job | Should not do |
| --- | --- | --- |
| Home | daily hub, last session entry, personal lookup, one memory teaser | full archive, full leaderboards, raw analytics, repeated counters |
| Tonight | live server, voice, availability, "who is in", team planning, current round/session pulse | historical archive |
| Sessions | archive list, filters, map/date/player search, latest-session routing | global leaderboards |
| Session Detail | full recap, players, maps, charts, verdicts, MVP, Good Night summary | next-session planning |
| Players | profile lookup, personal progress, own-form, leaderboards, rivalries | raw server status |
| Records | record book, hall of fame, seasons, map records, on-this-night | live polling |
| Tools | Proximity, Replay, Retro Viz, Greatshot, Uploads, admin tools | primary daily member journey |

#### Design-system audit

Current visual direction:

- Strong dark slate base with cyan/blue/purple/rose/amber accents.
- Large glassmorphism surfaces with backdrop blur.
- Repeated `rounded-xl`, `rounded-2xl`, `rounded-[20px+]`, and glow/shadow
  treatments.
- Marketing-style Home hero: oversized headline, slogan copy, animated badge,
  glow background.
- Many panels inside panels, especially on analytic views.

Recommended direction:

- Keep the dark ET:L mood, but make Home more like an operational clubhouse
  dashboard than a public product landing page.
- Use map levelshots as real game texture on session/archive cards.
- Use team/class/weapon/medal icons where they add meaning.
- Reduce decorative glow on Home; reserve strong color for status, live state,
  and important deltas.
- Prefer 8-12px radius for new dense dashboard components unless a shared
  existing component forces a larger radius.
- Avoid visible "this page is designed to..." explanatory copy. User-facing text
  should sound like the site, not like the implementation plan.

Proposed color semantics:

| Meaning | Color role |
| --- | --- |
| Live / ready | emerald |
| Action / primary link | cyan |
| Memory / archive | amber |
| Warning / missing link | amber/rose |
| Competitive delta | cyan for up, rose for down, neutral slate for stable |
| Admin/tooling | muted slate/purple, not primary Home color |

#### Modern Home audit

The React Home page is directionally better than legacy Home because it starts
with latest session and fast next steps. But it should not be switched on as-is
without content cleanup.

Specific notes:

- It still uses "Latest session, first" and planning-style explanatory text
  that sounds like internal rationale.
- It still includes trends and quick leaders, which recreates some legacy Home
  duplication.
- It uses larger rounded cards and radial gradients, so visual density is still
  closer to a showcase dashboard than a calm returning-member hub.
- Its `useLatestSession()` uses `/stats/sessions?limit=1`, which is the right
  direction for Home preview and better than the legacy `/stats/last-session`
  Home dependency.
- It already has a better action model: last session, find my stats, browse
  archive.

Decision: use React Home as the implementation base, but rewrite the content
hierarchy before flipping `home` to modern.

#### Website-specific engagement ideas

These are website surfaces, not game-metric algorithms:

| Idea | Where it lives | Why it fits this group |
| --- | --- | --- |
| "Last night in 30 seconds" | Home + Session Detail | Older friends want quick memory before deep stats. |
| "On this night" | Home small memory card + Records | Turns archive into nostalgia, not only numbers. |
| "Who was in voice?" | Tonight / Session Detail | Evening sessions are social, not only match results. |
| "Same squad again?" | Tonight | Uses friendship/session habit data without making it sweaty. |
| "Map memory lane" | Sessions / Records | ET:L is map-driven; map levelshots make archive recognizable. |
| "Personal evening card" | Me/Profile | Shows own-form and session attendance without shaming casual players. |
| "Friendly challenges" | Tonight/Home small | Light engagement between old friends; opt-in and non-toxic. |
| "Clip/moment queue" | Session Detail + Greatshot | Converts stats into shareable Discord memories. |

#### Measurement plan

Add lightweight analytics later only for product questions, not surveillance:

- Home primary CTA click-through: Last Session, Tonight, My Stats, Archive.
- Percentage of mobile users who reach Tonight or Last Session in one tap.
- Search usage: hero/player lookup queries and successful profile opens.
- Session Detail open rate from Home.
- Archive filter usage by date/map/player.
- Availability vote click-through from Home/Tonight.
- Route errors and modern bundle load errors.
- API request count for first Home render.
- Time to first useful Home content.

Success for Home V2 is not "more widgets". It is fewer decisions before the
player reaches the right memory.

#### Implementation gates for the later code batch

Before touching code:

1. Decide final top-level nav labels.
2. Decide whether `#ETL` becomes Tonight, Planning, or disappears into Tonight.
3. Decide whether Home V2 launches as modern React immediately or legacy cleanup
   first.
4. Decide which four or five mobile tabs are acceptable.
5. Decide whether private/social signals such as voice presence and availability
   should be visible to everyone or only logged-in users.

Before flipping Home to modern:

1. Build modern assets into `website/static/modern/`.
2. Update the modern route host cache version.
3. Smoke test `/`, `#/home`, `#/tonight`, `#/sessions2`, `#/session-detail/...`,
   `#/profile`, and `#/skill-rating`.
4. Verify legacy Home startup loaders no longer fire.
5. Verify mobile nav highlight state for Home, Tonight, Last, Me.
6. Verify no "Modern Route Offline" state appears on normal load.

#### What not to implement yet

- Do not add a social feed or chat replacement. Discord already owns chat.
- Do not migrate every route to React in one batch just because React chunks
  exist.
- Do not put raw Proximity panels on Home. Translate them into simple session
  stories first.
- Do not keep both legacy Home and modern Home concepts active at the same time.
- Do not add more counters to Home until ownership is reduced.
- Do not make Home a public marketing page. This is a clubhouse for people who
  already know why they are there.

### Proximity scope audit: selected date vs overall stats

The Proximity prototype has grown into a large analysis surface, but it does
not yet have one consistent scope contract. This is the likely cause of the
"I clicked a date/map, but this panel still looks overall" problem.

The important distinction:

- `overall` can mean a score category such as `prox_overall`.
- `overall` can also be perceived by users as "all dates / global data".

Right now those meanings are too easy to confuse because some panels obey the
selected session/map/round while other panels silently fall back to a rolling
range such as 30 days.

#### Current scope model

Canonical user scope should be:

```text
session_date
map_name
round_number
round_start_unix
```

Fallback scope should be:

```text
range_days
```

Rule: a Proximity panel should use either the selected session/map/round scope
or an explicitly labelled time window. It should never silently mix both.

#### What the current code appears to do

| Layer | Current behavior | Risk | Later action |
| --- | --- | --- | --- |
| Legacy Proximity page | `website/js/proximity.js` has `proximityScopeState` and `buildScopeParams()`, and most fetches use `scopedUrl()`. | Mostly scope-aware, but a few controls still behave like range controls even when only a date is selected. | Keep the scope helper, but make every panel state which scope it is rendering. |
| React Proximity page | `website/frontend/src/pages/Proximity.tsx` has page-level `sessionDate`, `mapName`, `roundNumber`, `roundStartUnix`. | Several large panels ignore that scope and call hooks with `rangeDays: 30` or only `mapName`. | Pass one `apiScope` object into every scope-sensitive panel. |
| API client/hooks | `buildScopedQuery()` exists and works for many endpoints. | Some hook/client methods still expose only `rangeDays`, not the full `ProximityScope`. | Make all Proximity hooks accept `ProximityScope` first, with range as fallback. |
| Backend helpers | `_build_proximity_where_clause()` supports full session/map/round scope. | Backend capability exists, but not every endpoint uses it. | Reuse the helper everywhere possible. |
| Scoring endpoint | `/proximity/prox-scores` accepts only `range_days`, `player_guid`, `limit`. | Strongest bug candidate: `session_date`, `map_name`, `round_number`, and `round_start_unix` are ignored even if the UI sends them. | Extend `compute_prox_scores()` and endpoint signature to support full scope, or label it as deliberately global. |

#### Likely broken or misleading paths

1. `Proximity Score` / `prox_overall`

   React panel:

   ```text
   ProxScoresPanel -> useProxScores(rangeDays, undefined, 30)
   ```

   Backend:

   ```text
   GET /proximity/prox-scores?range_days=30
   ```

   The endpoint currently does not accept session/map/round scope. If the user
   selected a specific evening, map, or round, the score can still represent a
   rolling window. This is probably the panel that makes the page feel like it
   is showing "overall" instead of selected-date stats.

2. React player heatmap / player aim

   The page has selected scope, but `PlayerHeatmapPanel` receives only
   `mapName`. The hooks then use `rangeDays: 30` or map-only parameters. This
   makes the map look session-specific because the page selector is visible,
   while the data may actually be a 30-day map aggregate.

3. React movement analytics

   `MovementStatsPanel` calls `useMovementStats(30)`. Backend movement stats
   can be made session/map aware, but the current React panel is a rolling
   window panel.

4. React danger zones and combat heatmap

   `DangerZonesPanel` and `CombatHeatmapPanel` pass `mapName` plus
   `rangeDays: 30`. They ignore `sessionDate`, `roundNumber`, and
   `roundStartUnix`.

5. React leaderboards

   `LeaderboardTabs` uses `useProximityLeaderboards(activeTab, rangeDays, 10)`.
   The backend leaderboard endpoint supports session/map/round scope, but the
   React hook path does not pass it.

6. Legacy leaderboard date-only scope

   Legacy code hides range buttons when `mapName` or `roundNumber` exists:

   ```text
   hasScope = mapName || roundNumber != null
   ```

   A selected `sessionDate` alone is also a scope, but that expression does not
   treat it as one. So date-only leaderboard UI can still look like a range
   leaderboard even though the query includes `session_date`.

7. Partial-scope backend endpoints

   Some backend routes support only part of the canonical scope:

   - kill lines: session/map/range, but not full round scope
   - danger zones: session/map/range, but not full round scope
   - movement stats: session/map/player/range, but not full round scope

   These panels can still be useful, but they need a visible label such as
   "session/map scope" instead of pretending to be exact round scope.

#### Product rule for Proximity

Every Proximity panel needs a small scope badge near its title:

```text
Session 2026-06-24
Session 2026-06-24 / supplydepot2
Session 2026-06-24 / supplydepot2 / R2
Last 30 days
All collected data
```

If the panel cannot support the selected scope, it should say so:

```text
Showing map aggregate because round-level data is not available for this panel.
```

This matters more than perfect math at first. The user must be able to trust
what each number means.

#### Proximity implementation plan for the later code batch

1. Define one frontend `ProximityScope` contract.

   Shape:

   ```text
   {
     session_date?: string
     map_name?: string
     round_number?: number
     round_start_unix?: number
     range_days?: number
   }
   ```

   Rules:

   - If `session_date` exists, do not also use `range_days` unless the endpoint
     explicitly documents a comparison window.
   - If `round_number` exists, send `round_start_unix` too whenever available.
   - A panel may degrade from round -> map -> session -> range, but must label
     that downgrade.

2. Update React Proximity panels to receive `scope`.

   First-pass target panels:

   - `ProxScoresPanel(scope)`
   - `MovementStatsPanel(scope)`
   - `DangerZonesPanel(mapName, scope)`
   - `CombatHeatmapPanel(mapName, scope)`
   - `PlayerHeatmapPanel(mapName, scope)`
   - `LeaderboardTabs(scope)`

3. Update API hooks/client signatures.

   Convert range-first hooks into scope-first hooks:

   ```text
   useProxScores(scope, playerGuid?, limit?)
   useMovementStats(scope, playerGuid?)
   useProximityLeaderboards(category, scope, limit?)
   useCombatHeatmap(mapName, scope, opts?)
   useDangerZones(mapName, scope, opts?)
   usePlayerHeatmap(mapName, playerGuid, mode, scope, opts?)
   usePlayerAim(mapName, playerGuid, scope, opts?)
   ```

4. Fix backend score scope.

   `/proximity/prox-scores` should either:

   - support `session_date`, `map_name`, `round_number`, `round_start_unix`, or
   - be renamed/labelled as "30-day Proximity Score" and separated from scoped
     session analysis.

   Preferred path: make `compute_prox_scores()` accept a filter/scope object,
   not just `range_days`.

5. Normalize legacy behavior.

   In the legacy page, `hasScope` should include `sessionDate`, not only
   `mapName` and `roundNumber`. Range buttons should disappear or be visually
   secondary whenever a selected date is active.

6. Add scope-aware empty states.

   For old sessions without Proximity data, show:

   ```text
   No Proximity data collected for this selected scope.
   ```

   Avoid silently falling back to all-time data. Silent fallback is the thing
   that breaks trust.

#### Proximity acceptance tests

Before shipping a Proximity revamp, verify these manually or with browser tests:

- Select a session date: every scope-sensitive request includes
  `session_date=YYYY-MM-DD`, or the panel is explicitly labelled as a range
  panel.
- Select a map: every map-sensitive request includes `map_name`.
- Select a round: every endpoint that supports round scope includes
  `round_number` and `round_start_unix`.
- `Proximity Score` changes or clearly explains why it does not change after
  changing session/map/round.
- `LeaderboardTabs` does not show range controls as primary UI when a date,
  map, or round is selected.
- Browser network log contains no unexpected `/proximity/*range_days=30`
  requests after selecting a session scope, except panels explicitly labelled
  "Last 30 days".
- Empty selected scopes never auto-fallback to global data without a warning.

#### How to show Proximity better on the site

Do not expose the prototype as one huge statistics wall forever. Split it into
clear mental models:

| Surface | What users think they are asking | Best Proximity content |
| --- | --- | --- |
| Session Detail | "What happened that night?" | best fight, biggest save, push that failed, revive swing, map pressure |
| Map Page | "Where do we win or die on this map?" | death zones, kill lines, objective pressure, route quality |
| Player Profile | "How do I play?" | personal heatmap, weapon/aim profile, revive/gib value, role fingerprint |
| Team/Party View | "Who works well together?" | duo chemistry, trade trust, cohesion, crossfire |
| Tools / Proximity | "Let me inspect the raw prototype." | full panels, filters, replay, debug-quality stats |

For the older friend-group use case, Home should not show raw Proximity. It
should show translated memories:

- "Best save of the night"
- "Most stubborn defense"
- "Funniest repeat duel"
- "Map where we finally broke through"
- "Medic chain that kept the push alive"

The raw Proximity page can remain a power-user tool, but the community-facing
site should turn Proximity into stories, archive entries, and map memories.

### Research synthesis for the web revamp

Relevant external UX patterns:

- Nielsen Norman Group IA guidance: avoid unclear categories and duplicate
  navigation paths; users need a structure that matches their mental model, not
  the org/code structure. Source:
  https://www.nngroup.com/articles/top-10-ia-mistakes/
- Nielsen Norman Group usability heuristics: visibility of system status,
  match with real-world language, consistency, recognition over recall, and
  minimalist design are the strongest rules for this homepage. Source:
  https://www.nngroup.com/articles/ten-usability-heuristics/
- Material Design navigation guidance: top-level destinations should be stable,
  few, and predictable; secondary tools should not compete with primary
  journeys. Source: https://m3.material.io/components/navigation-rail/overview
- Strava/club-style community pattern: recurring activity feeds, segments,
  records, and personal progress work because they combine personal memory with
  group rhythm. Slomix translation: session archive, map records, personal
  profiles, and friendly weekly/community pulse.
- Discord community pattern: Discord remains the conversation layer. The
  website should not replace chat; it should answer questions Discord is bad at:
  "what happened?", "who played?", "where is that old night?", "what are my
  stats?", and "what clip/memory should we keep?"

### Deep research translation for Slomix

The sources are not copied as generic design theory. They translate into
specific decisions for this site.

| Research principle | Source | Slomix interpretation | Concrete website decision |
| --- | --- | --- | --- |
| Structure and navigation must support each other. | NN/g IA mistakes | If Home, Sessions, Records, and Tools all show "recent activity", the structure is lying. | Assign one primary owner per concept before editing UI. |
| Hidden or inconsistent paths hurt findability. | NN/g IA mistakes | Desktop Stats dropdown and mobile Boards/Session tabs create different maps of the site. | Align desktop and mobile around the same mental model: Home, Tonight, Last/Sessions, Me, Records/Tools. |
| Labels should match user language. | NN/g heuristics, match with real-world language | The group does not think in route IDs like `sessions2`, `#ETL`, or Proximity metric names. | Use labels like Tonight, Last Session, Archive, My Stats, Records, Tools. |
| Keep system status visible. | NN/g heuristics | Live server, voice, and availability are valuable, but only if they read as one "are we playing?" answer. | Replace two large status cards plus availability links with one compact Tonight strip. |
| Recognition beats recall. | NN/g heuristics | Older returning players should not remember where "last night" lives. | Put Last Session and My Stats in the first viewport every time. |
| Minimalist design is about relevance, not empty space. | NN/g heuristics | Removing widgets is not making the site boring; it makes the important evening questions faster. | Cut repeated leader/recent/season widgets from Home and move them to owned pages. |
| Primary destinations should be few and stable. | Material navigation guidance | The site currently exposes too many competing top-level tools. | Cap primary nav to about 5-6 destinations; put specialist utilities under Tools. |
| Community sites need engagement and safety, but not another chat. | Discord community resources | Discord already handles live conversation. The website should preserve memory, stats, and archive. | Build durable session recaps, records, clips, and "on this night" instead of a feed. |

#### Pattern notes from other communities

| Pattern | What others commonly do | What Slomix should borrow | What Slomix should avoid |
| --- | --- | --- | --- |
| Sports club dashboards | Next event, latest result, standings, player profiles. | The "next event + latest result" structure maps well to Tonight + Last Session. | Do not over-formalize the group into a league if the tone is old friends relaxing. |
| Strava-like activity communities | Activity history, segments, personal progress, clubs. | Own-form progress, map records, recurring weekly rhythm. | Do not make every metric public competition; keep some stats personal/friendly. |
| HLTV/esports match sites | Recent matches, rankings, player/team pages, match detail. | Session archive and player detail hierarchy. | Do not mimic pro-esports intensity; this group needs memory and banter more than scouting. |
| Discord communities | Conversation, events, moderation, lightweight identity. | Keep Discord as the live social layer and website as memory layer. | Do not duplicate chat or build a second notification system without a clear need. |
| Game clip/archive tools | Clips, demos, highlights, shareable moments. | Greatshot and Session Detail should create shareable memories. | Do not put raw upload/render workflows on the homepage. |

#### Resulting UX rule

For every homepage widget, ask:

1. Does it answer a question the player has in the first 30 seconds?
2. Is this the only place that answer appears?
3. Does the label sound like how the group talks?
4. Does it lead to one obvious next action?
5. Would it still matter on a phone after a 3-4 hour evening session?

If the answer is no, the widget belongs deeper in Sessions, Players, Records,
Tonight, or Tools.

### Product principle for the website

The website should not be a marketing landing page. The users already know the
community and the game. It should be a returning-member dashboard.

Primary questions:

1. Are we playing tonight?
2. What happened last session?
3. Where are my stats?
4. Where is the archive?
5. What is worth remembering?

Everything on the homepage should map to one of those questions. If a widget
does not answer one of them, it belongs deeper in the site.

### One-source-of-truth rule

Each concept gets one primary home:

| Concept | Primary home | Homepage treatment |
| --- | --- | --- |
| tonight/live/availability | Tonight | one compact status strip |
| last session | Home + Session Detail | one hero recap card with CTA |
| player stats | Player Profile | search/lookup entry only |
| sessions archive | Sessions | 2-3 recent rows or one archive CTA |
| records/history | Record Book | one archive/memory CTA |
| leaderboards | Leaderboards/Players | one gentle snapshot at most |
| maps | Maps/Record Book | not a homepage grid |
| proximity/deep analysis | Tools/Session Detail | not above the fold |
| Greatshot/uploads | Archive/Tools | memory/clip CTA, not a full widget |
| admin/diagnostics | Admin | never homepage except error badge |

### Recommended top-level navigation

Keep the nav small and user-worded:

```text
Home
Tonight
Sessions
Players
Records
Tools
```

Where:

- `Home` = today/last session/personal entry
- `Tonight` = availability, live server, voice, team planning
- `Sessions` = session archive and session detail
- `Players` = player search, profiles, leaderboards
- `Records` = record book, map records, seasons, Hall of Fame, memories
- `Tools` = proximity, Greatshot, uploads, replay, retro-viz, admin for admins

Mobile bottom nav should be even simpler:

```text
Home | Tonight | Last | Me | Records
```

`Last` deep-links to the latest session. `Me` opens player lookup / linked
profile once Discord linking is available.

### Homepage target layout

Homepage should be dense but calm, not a hero/marketing page.

```text
+------------------------------------------------------------------+
| Slomix Tonight                                                    |
| Server: online/offline | Voice: 4 in | Next session: Tue 20:30    |
+------------------------------------------------------------------+
| Last Session                                                      |
| Team A 12 - 8 Team B | 10 rounds | 12 players | 4 maps            |
| Story line / Good Night line later                                |
| [Open recap] [Greatshot candidates]                               |
+------------------------------------+-----------------------------+
| Find My Stats                      | Play / Join                 |
| player search                      | availability status         |
| recent own-form teaser later       | confirmed/maybe count       |
+------------------------------------+-----------------------------+
| Community Pulse                    | Archive                     |
| last 14d: sessions, active players | Sessions | Records | Clips  |
| one gentle leader/mover only       |                             |
+------------------------------------------------------------------+
```

Above the fold should contain only:

- tonight/live status
- last session recap
- player lookup
- archive entry

Everything else comes after.

### Homepage components to keep, merge, move, or remove

| Existing piece | Decision | Reason |
| --- | --- | --- |
| marketing hero "TRACK YOUR LEGACY" | remove from first viewport | users are returning members, not prospects; space belongs to community status, last session, search, and archive |
| hero search | keep, but make it "Find my stats" | direct high-frequency task |
| `home-tonight-card` | keep/merge into top strip | answers "are we playing?" |
| `home-pulse-cards` next session | keep/merge into top strip or Play card | useful, but not three separate cards |
| `home-pulse-cards` last session | keep as the only last-session card | do not duplicate elsewhere on Home |
| `home-pulse-cards` movers | move below fold or Players | can feel competitive; not primary |
| challenge card | below fold | good engagement, not above-fold core |
| season card | merge with Records/Season snapshot | duplicated with Current Season widget |
| overview stat grid | reduce to 3 community pulse numbers | six cards is too much |
| live server status | merge into top strip; expandable in Tonight | current version is useful but too large |
| voice status | merge into top strip; expandable in Tonight | same |
| insights strip | move below fold or Records/Community Pulse | useful, but not before user tasks |
| Current Season widget | move to Records/Season page or below fold | duplicates season card |
| Recent Matches | replace with Last Session + Archive CTA | too close to last-session card |
| Quick Leaders | move to Players/Leaderboards | not primary homepage content |
| Retro Viz teaser | move to Tools/Archive | fun, but not homepage core |

### Modern-vs-legacy implementation decision

There are two viable implementation paths.

Recommended path: **activate and finish the modern React Home**.

Why:

- `website/frontend/src/pages/Home.tsx` already exists.
- `website/frontend/src/runtime/catalog.ts` already marks Home as modern.
- Vite output already exists in `website/static/modern`.
- React Home already has cleaner sections than legacy Home.
- It is easier to remove duplication by routing to one modern Home than by
  pruning a very large legacy `index.html` block.

Fallback path: **simplify legacy Home in place**.

Use this only if modern route activation has deployment risk. It would require
removing or hiding large chunks from `website/index.html` and disabling several
home startup loaders in `website/js/app.js`.

Decision rule:

```text
If modern Home renders reliably in local/prod static build -> activate modern.
If not -> simplify legacy but keep the same IA and component order.
```

### Modern Home content rewrite

The current React Home still has prototype copy like:

```text
Latest session, first.
Put the last session, tonight's roster, and personal lookup in front of everything else.
```

That should be rewritten before activation. The UI should not explain the
design. It should sound like the community.

Better hero copy:

```text
Slomix Tonight
Who is around, what happened last time, and where the archive lives.
```

Primary CTA:

```text
Open Last Session
```

Secondary CTAs:

```text
Find My Stats
Vote Tonight
Browse Archive
```

Do not use a giant marketing headline. The first viewport should feel like a
tool, not a product launch.

### Homepage data mapping

No new API is needed for the first revamp.

| UI need | Existing endpoint/source |
| --- | --- |
| latest session | `api.getSessions({ limit: 1 })` / `/api/stats/sessions?limit=1` |
| overview pulse | `/api/stats/overview` |
| trends after fold | `/api/stats/trends?days=14` |
| live server/voice | `/api/live-status` |
| season strip | `/api/seasons/current` |
| player search | existing auth/search/player lookup |
| quick leaders, if kept below fold | `/api/stats/quick-leaders` |
| sessions archive CTA | `#/sessions2` |
| records CTA | `#/record-book` |
| Greatshot CTA | `#/greatshot` |
| availability CTA | `#/availability` or `#/tonight` |

### Community engagement surfaces

The homepage should push users into four loops:

1. **Tonight loop**
   - vote availability
   - check voice/server status
   - see live session once game starts

2. **Post-session loop**
   - open latest session
   - read story/Good Night summary later
   - jump to Greatshot candidates later

3. **Personal loop**
   - find my profile
   - see recent form and memories
   - compare against own baseline, not just global rank

4. **Archive loop**
   - browse old sessions
   - records and map lore
   - clips/uploads/memories

This is better than a generic dashboard because it matches how the group uses
the site before, during, and after evenings.

### Revised page roles

| Page | New role |
| --- | --- |
| Home | daily hub: tonight, last session, my stats, archive |
| Tonight | organizer surface and live hub |
| Sessions | archive browser |
| Session Detail | main story/recap page |
| Players/Profile | personal identity and own-form |
| Records | estate, lore, seasons, map records |
| Proximity | power-user analysis |
| Greatshot | clip/memory evidence |
| Uploads | raw archive assets |
| Admin | operations only |

### Visual design direction

Keep the app dark and ET-flavored, but reduce the one-note blue/purple glow.
The homepage should use a restrained operational palette:

- slate/dark base
- cyan for live/links
- amber for records/memories
- green for ready/online
- rose only for errors or opposing-side accents

Use map images and levelshots where helpful:

- latest session card can show the top map levelshot
- archive cards can use map thumbnails
- records/memory cards can use map or Greatshot thumbnails later

Avoid:

- giant gradient hero
- decorative orbs
- nested cards
- duplicated stat cards
- in-app text explaining why the design exists
- leaderboard-first homepage

### Future tickets for website revamp

**WEB-00: Homepage duplication audit**

Status: documented here.

Acceptance:
- list every duplicated home concept
- choose one primary owner for each concept

**WEB-01: Decide modern Home activation**

Scope:
- verify modern Home static build in local/prod
- compare modern `Home.tsx` to legacy homepage
- decide activate modern or simplify legacy

Acceptance:
- no runtime change until the decision is explicit
- rollback path documented

**WEB-02: One-source homepage**

Scope if modern path:
- route `home` to modern
- stop legacy home boot loaders from running for Home
- keep legacy HTML as fallback only

Scope if legacy path:
- remove duplicate legacy sections
- keep one last-session card
- keep one season/community pulse area

Acceptance:
- no duplicated session summary
- no duplicated season summary
- no duplicated recent/latest match list

**WEB-03: Homepage content rewrite**

Scope:
- replace prototype/marketing copy
- make CTAs action-based
- remove "design explanation" text from UI

Acceptance:
- first viewport answers tonight/last session/my stats/archive
- no headline larger than the actual page job requires
- copy sounds like Slomix community, not SaaS marketing

**WEB-04: Navigation taxonomy**

Scope:
- settle primary nav labels
- group specialist routes under Tools/Archive where possible
- make mobile bottom nav task-based

Acceptance:
- top-level nav has 5-6 items max
- Record Book/Hall of Fame/Records aliases do not confuse users
- Proximity/Greatshot/Uploads are discoverable but not homepage noise

**WEB-05: Session Detail as recap center**

Scope:
- move heavy last-session analytics out of Home
- Session Detail becomes the place for charts, team matrix, moments, and later
  Good Night

Acceptance:
- Home has recap preview only
- Session Detail holds the depth

**WEB-06: Archive and memory routes**

Scope:
- make Sessions, Records, Greatshot, Uploads feel like one archive ecosystem
- add cross-links from session recap to clips/records/memories

Acceptance:
- old sessions are easy to find
- clips and uploaded assets have clear relation to sessions

**WEB-07: Responsive QA**

Scope:
- test mobile and desktop
- check text overflow
- check card heights
- check nav and first viewport

Acceptance:
- no overlapping text
- first viewport shows at least hint of next content
- buttons and cards are tappable
- no layout shift when data loads

### Website rollout order

Recommended order:

1. Document IA and approve one-source rule.
2. Build/verify modern Home locally.
3. Rewrite modern Home copy/layout.
4. Activate modern Home behind an easy rollback.
5. Remove duplicate legacy home startup loads.
6. Clean nav taxonomy.
7. Move archive/deep-analysis teasers out of Home.
8. Add Good Night/ET:L story features later.

Do not start with CSS polish. The main problem is information architecture and
duplicated content ownership.

### Website success criteria

The revamp works if:

- users can open the site and know within 5 seconds whether something is
  happening tonight
- last session appears once, not three times
- player lookup is obvious
- old sessions and records are easy to find
- advanced proximity tools do not dominate casual users
- the homepage feels like the group's clubhouse/archive, not a public SaaS
  landing page
- mobile users can tap through without hunting

## Website information architecture

No new primary page is needed for v1. Add panels to existing pages.

### Home

Purpose: "should I care today?"

Panels:

1. Tonight status
2. Last Night card with Good Night Index
3. On This Night memory

### Tonight

Purpose: get the group into a fair game.

Panels:

1. availability threshold
2. confirmed / maybe / standby
3. suggested fair teams
4. team-name vote
5. live score once session starts
6. one live director sentence

### Session Detail

Purpose: main story page.

Recommended order:

1. result and Good Night Index
2. one narrative lede
3. map strip / evening arc
4. team balance and score
5. moments
6. player own-form cards
7. MVP vote / peer recognition
8. Greatshot clip candidates
9. deeper tabs for players/teamplay/charts

### Player Profile

Purpose: identity, not a punishment table.

Panels:

1. identity header
2. own-form trend
3. role/persona
4. best maps
5. favorite duos
6. personal memories
7. private/opt-in focus line

### Record Book

Purpose: estate.

Panels:

1. named records
2. per-map segments
3. season awards
4. old memories
5. LAN/photo archive
6. database/export ritual status

### Greatshot

Purpose: memories with video/demo evidence.

Panels:

1. uploaded demos
2. detected highlights
3. story clip candidates
4. rendered clips when available

## UI blueprint

These are text wireframes. They should be adapted to the existing Slomix visual
language, not built as marketing cards.

### Session Detail summary tab

Primary goal: tell the evening back in 30 seconds.

```text
+--------------------------------------------------------------+
| Team A 3 - 2 Team B                    Good Night 86         |
| Close teams | 11 players | 3 comeback maps | 7 moments       |
+--------------------------------------------------------------+
| Tonight's story                                             |
| Team B opened strong, but the closest maps came after 23:00.|
| carniel's carrier stop on supply was the night's swing.      |
+--------------------------------------------------------------+
| Map strip                                                    |
| supply  A+12s | goldrush B hold | braundorf A comeback ...  |
+--------------------------------------------------------------+
| Moments                                                      |
| [Carrier stop] [Revive swing] [Late chaos] [PB: revives]     |
+--------------------------------------------------------------+
| Player cards vs own form                                     |
| carniel: Good night, 23 frags - 6 above usual                |
| Zlatorog: About usual, 5 revives kept teams alive            |
+--------------------------------------------------------------+
```

Do not open with a raw leaderboard. The story and Good Night score should set
the tone before the table appears.

### Tonight / planning

Primary goal: reduce organizer work.

```text
+--------------------------------------------------------------+
| Tonight                                                      |
| 7 confirmed, 2 maybe, need 1 more for 5v5                    |
+--------------------------------------------------------------+
| Suggested teams                                              |
| Balanced split                                               |
| Skill diff 2.8% | roles balanced | fresh pairs               |
| Team A: ...                                                  |
| Team B: ...                                                  |
| [Use as draft seed] [Shuffle another way]                    |
+--------------------------------------------------------------+
| Team name vote                                               |
| Old Boys vs Late Chaos                                       |
+--------------------------------------------------------------+
```

The copy should say "suggested", never "correct".

### Home

Primary goal: answer "what's happening?" in three cards.

```text
+----------------+----------------+----------------------------+
| Tonight        | Last night     | On this night              |
| 7/10 ready     | Good Night 86  | 2025 supply comeback       |
| Need 1 more    | View recap     | View memory                |
+----------------+----------------+----------------------------+
```

### Player profile

Primary goal: identity + memories, not a punishment sheet.

```text
+--------------------------------------------------------------+
| carniel                                                      |
| Objective Anchor | Current form: Good | Favorite map: supply  |
+--------------------------------------------------------------+
| Last 10 sessions                                             |
| form sparkline, PB markers, rough nights softened            |
+--------------------------------------------------------------+
| What you bring                                               |
| carrier stops, trades, objective pressure, reliable turnout  |
+--------------------------------------------------------------+
| Favorite duos                                                |
| Zlatorog: reliable pair, +12% trade response                 |
+--------------------------------------------------------------+
| Memories                                                     |
| best night, old PB, season awards                            |
+--------------------------------------------------------------+
```

Private focus area should be hidden unless the logged-in linked user is viewing
their own page and has opted in.

### Record Book

Primary goal: estate and lore.

```text
+--------------------------------------------------------------+
| Record Book                                                  |
| [Segments] [Seasons] [Named records] [Memories] [LAN]        |
+--------------------------------------------------------------+
| Map segments                                                 |
| supply fastest doc run | goldrush longest hold               |
+--------------------------------------------------------------+
| Named records                                                |
| "The SuperBoyy revive night"                                 |
+--------------------------------------------------------------+
```

Named records matter because friend groups remember stories better than metric
names.

## Copy and tone system

### Public labels

Use:

- Good night
- Great night
- About usual
- Rough night, if shown only to owner or softened
- Late chaos
- Reliable pair
- Fresh mix
- Close one
- Comeback map
- Best since [month]

Avoid:

- Bad
- Worst
- Choked
- Throw
- Useless
- Bottom
- Liability

### Public stat sentence template

```text
{player} had {label}: {positive_metric} - {baseline_delta}, plus {teamplay_line}.
```

Examples:

```text
Zlatorog had a good night: 6 revives above usual, plus two clean trades.
carniel was about usual on frags, but had the night's biggest carrier stop.
```

### Private focus sentence template

```text
Focus: {metric} was below your usual. Review {specific_replay_link}.
```

Rules:

- focus is not public
- one focus only
- always include a concrete review link or action
- no moral language

## Empty/loading/error states

Friend-group UX should avoid making the site feel dead.

| State | Bad | Better |
| --- | --- | --- |
| no session last night | "No data" | "No games last night. Next planned night: Tuesday." |
| not enough baseline | "Insufficient stats" | "Need a few more sessions before we rate this fairly." |
| no memory today | "No memories" | hide card or show "No strong memory today" only admin-side |
| Greatshot no demo | "Clip unavailable" | "Moment found; no matching demo uploaded yet." |
| team suggestions impossible | "Error" | "Need at least 6 confirmed players for a useful split." |

## Implementation roadmap

### Phase 0 - Backtest and tone calibration

No UI first. Run proposed scoring on last 20-30 sessions and manually review:

- Does Good Night Index match human memory?
- Does it avoid rewarding stomps too much?
- Do bottom-half players still get positive cards?
- Are generated lines funny/true, or awkward?

Deliverable:
- a script/notebook or admin-only endpoint later
- owner-reviewed examples

### Phase 1 - Good Night v0 on Session Detail

No schema required at first.

Backend:
- add service function later, likely near session/storytelling services
- derive from existing session detail/scoring/stats payloads

Frontend:
- add top card to `session-detail`
- include breakdown and explanation

Acceptance:
- one score
- 3-5 reason chips
- no negative player callouts

### Phase 2 - Own-form cards v2

Build on:
- `/stats/session/{gaming_session_id}/verdicts`
- `storytelling/baseline.py`

Add:
- multi-metric own-form score
- better labels
- positive public highlights
- private focus line later

Acceptance:
- every active player gets a card
- first-night / low-baseline handled gracefully

### Phase 3 - Friendship-safe team suggestions

Build on:
- availability confirmed list
- planning room
- skill ratings
- duo history

Add:
- endpoint that returns 2-3 suggested splits
- UI cards in Tonight/Planning
- manual override always visible

Acceptance:
- suggestions explain why they are fair
- no hard win prediction copy

### Phase 4 - Memory engine

Build on:
- `OnThisDayService`
- sessions/records/awards

Add:
- memory candidate scoring
- safe memory filters
- website deep links
- Discord push

Acceptance:
- no shame memories
- at least one useful memory per week, not forced daily if weak

### Phase 5 - Story Worthiness + Greatshot candidates

Build on:
- storytelling moments
- Greatshot highlights
- demo crossref

Add:
- story score
- clip candidate list on Session Detail
- render queue only after confidence is good

Acceptance:
- candidate timestamp is explainable
- if no matching demo exists, UI says so clearly

### Phase 6 - Wave Fight Ledger

Build on:
- proximity spawn timing
- kill outcomes
- objective/carrier events

Add:
- derived wave/fight model
- first-blood conversion
- stagger story lines
- live director line

Acceptance:
- backtested against real sessions
- no public claims until mapping is trustworthy

## Implementation ticket breakdown

These are not code changes yet; they are future ticket scopes.

### Ticket GN-00: Backtest harness

Goal:
- print Good Night candidates for last 20-30 sessions
- no public UI

Likely touchpoints:
- new dev/admin script or admin-only endpoint
- `website/backend/services/good_night_engine.py` later

Deliverables:
- session score table
- component breakdown
- reason chips
- owner review notes

Tests:
- component scores are 0..100
- no crash on missing proximity
- invalid rounds excluded
- no bot/test rounds counted

### Ticket GN-01: Good Night service v0

Goal:
- compute session-level score on demand

Likely touchpoints:
- `website/backend/services/good_night_engine.py`
- `website/backend/routers/sessions_router.py`

Acceptance:
- deterministic payload
- reason chips are sourced from real data
- warnings explain missing data

### Ticket GN-02: Session Detail Good Night panel

Goal:
- top panel on session detail

Likely touchpoints:
- `website/js/session-detail.js`
- maybe modern route counterpart if active

Acceptance:
- readable on mobile
- no table-first experience
- handles missing score gracefully

### Ticket OF-01: Own-form cards v2 backend

Goal:
- multi-metric player cards using own baseline

Likely touchpoints:
- `website/backend/services/own_form_cards.py`
- `website/backend/services/storytelling/baseline.py`
- `website/backend/routers/sessions_router.py`

Acceptance:
- every player gets a non-hostile card
- positive lines selected first
- low-baseline handled

### Ticket OF-02: Own-form cards UI

Likely touchpoints:
- `website/js/session-detail.js`

Acceptance:
- cards do not displace raw table for power users
- negative focus not public

### Ticket TS-01: Team suggestion backend

Goal:
- return 2-3 suggested splits from confirmed players

Likely touchpoints:
- `website/backend/services/fair_team_suggester.py`
- `website/backend/routers/planning.py`
- `website/backend/routers/availability.py`

Acceptance:
- balanced/fresh/captain-seed modes
- manual override remains primary
- no hard win probability copy

### Ticket TS-02: Team suggestion UI

Likely touchpoints:
- `website/js/tonight.js`
- `website/js/availability.js`

Acceptance:
- one-click copy/use suggestion
- reason chips explain split

### Ticket ME-01: Memory candidate service

Goal:
- score one safe memory for a date

Likely touchpoints:
- `website/backend/services/memory_engine.py`
- `bot/services/on_this_day_service.py`
- `website/js/home.js`

Acceptance:
- can choose no memory if weak
- deep link included
- no negative memories

### Ticket SW-01: Story worthiness service

Goal:
- merge story candidates and expose top moments

Likely touchpoints:
- `website/backend/services/story_worthiness.py`
- `website/backend/routers/storytelling_router.py`
- `website/backend/routers/sessions_router.py`

Acceptance:
- de-duplicates overlapping moments
- provides source evidence
- `shame_safe` always explicit

### Ticket GS-01: Greatshot clip candidates

Goal:
- show "moment found; demo available/unavailable" cards

Likely touchpoints:
- `website/backend/routers/greatshot.py`
- `website/backend/services/greatshot_crossref.py`
- `website/js/greatshot.js`
- `website/js/session-detail.js`

Acceptance:
- no auto-render for low confidence
- candidate timestamp explainable

### Ticket WF-00: Wave ledger research/backtest

Goal:
- validate wave/fight bucketing before public use

Likely touchpoints:
- `website/backend/services/wave_fight_ledger.py`
- proximity tables

Acceptance:
- manual review on 10 rounds
- no public UI until validated

## Testing and validation plan

### Unit tests

Good Night:

- score clamps to 0..100
- missing components degrade gracefully
- invalid rounds filtered
- no division by zero for short sessions
- reason chips match component drivers

Own-form:

- low baseline returns "New" or "Need more sessions"
- positive line selection prefers best deltas
- private focus excluded by default
- outlier sessions do not dominate median/MAD

Team suggestions:

- symmetric team duplicates removed
- locked players respected
- odd player counts handled with standby/sub
- output has at least one explanation chip

Story worthiness:

- shame-risk candidate excluded from public output
- close timestamps are merged
- source metadata preserved

Memory engine:

- same-day prior years selected
- current-year sessions excluded
- sensitivity filter blocks negative memories

### Golden-session review

Create a fixed list of known sessions:

| Category | Need at least |
| --- | ---: |
| close great night | 3 |
| stomp night | 3 |
| low turnout night | 2 |
| high story / bad balance night | 2 |
| missing proximity night | 2 |
| old memory candidate | 5 |

For each, store expected qualitative behavior:

- high/medium/low Good Night
- public player cards are acceptable
- no obvious shame line
- top moment makes sense

### Manual owner review

Before public release, generate examples:

```text
Session: 2026-xx-xx
Good Night: 84
Digest line: ...
Player cards: ...
Moments: ...
```

Owner marks:

- keep
- adjust wording
- score wrong
- too harsh
- too boring
- not our humor

This is not optional. Tone is product quality here.

## Risk register

| Risk | Why it matters | Mitigation |
| --- | --- | --- |
| Score rewards stomps | bad nights look "good" due to high kills | balance component weight, stomp penalty |
| Bottom players feel targeted | friend group damage | own-baseline first, no negative public cards |
| Too many panels | ghost-town feeling | add to existing pages, prune old views |
| Greatshot overpromises | render/cut pipeline still limited | start with candidates and confidence |
| Wave model wrong | ET timing is subtle | admin/backtest first |
| Team suggestions cause arguments | algorithm perceived as authority | show as suggestions with reason chips |
| Memories surface embarrassment | archive becomes unsafe | sensitivity filter and opt-outs |
| Metrics feel too serious | wrong tone for relaxed nights | use Good Night and lore framing |
| Slow endpoints | many joins across proximity tables | compute-on-read first, cache/store later |
| Data gaps | old sessions lack proximity | warnings and graceful fallback |

## Privacy and consent

Suggested rules:

1. Public digest only positive/team/story moments.
2. Personal focus lines only for the linked player.
3. Memory opt-out should exist before daily memories become prominent.
4. Do not show "absence" or "inactive" shame.
5. Do not auto-post negative records.
6. Admin diagnostics may show rough data, but not in public cards.

Potential future settings:

```text
show_private_focus=true/false
allow_memory_mentions=true/false
allow_greatshot_auto_candidates=true/false
```

## Coverage checklist

Included in this plan:

- product positioning for older friend-group sessions
- external research mapping
- code/data anchors in current repo
- bigger-than-proximity telemetry atlas
- big bet catalog across live/map/profile/team/story/archive
- Good Night Index algorithm
- own-form player cards
- friendship-safe team balancer
- story/moment ranking
- Greatshot fusion path
- evening arc / fatigue framing
- On This Night memory engine
- duo chemistry shrinkage
- gentle weekly challenges
- optional wave fight ledger
- ET:L stopwatch domain model
- analog game matrix for Overwatch/TF2/Dirty Bomb/UT Assault
- map objective graph manifest proposal
- RoundState vector for ET:L objective impact
- ET:L Lua capture feasibility matrix
- stage split model and R1/R2 mirror comparison
- time-to-beat pressure model for Round 2
- xOV / delta-xOV heuristic
- objective pressure seconds
- productive failed push detection
- defense hold windows
- revive/gib permanence model
- attack reset detection
- map fingerprint plan
- ET:L service/module breakdown
- website duplication audit
- website community revamp research
- revised homepage one-source-of-truth plan
- modern-vs-legacy Home implementation decision plan
- website navigation taxonomy
- website revamp ticket breakdown
- deep website route truth inventory
- homepage loader/API ownership audit
- desktop vs mobile navigation audit
- modern route host migration risk notes
- website visual/design-system audit
- explicit removal of `TRACK YOUR LEGACY` first-viewport hero
- website external UX research translation
- homepage measurement plan
- Proximity selected-date vs overall-scope audit
- ProximityScope frontend/API/backend contract plan
- `/proximity/prox-scores` scope gap and `prox_overall` ambiguity
- React Proximity panels that still use hardcoded 30-day/map-only scope
- legacy Proximity leaderboard date-only scope risk
- Proximity panel scope-badge and acceptance-test plan
- README/product documentation drift note
- map intelligence / objective pressure / player fingerprint ideas
- spawn economy / aim truth / life card ideas
- data trust and coverage ideas
- website IA and wireframes
- API payload contracts
- pseudo-SQL sketches
- implementation tickets
- testing plan
- risk register
- privacy/tone rules

Not included / intentionally deferred:

- actual code implementation
- schema migrations
- ML model training
- finalized visual design mockups
- exact CSS/component specs
- production rollout dates
- real session calibration results
- clip rendering implementation details beyond candidate flow
- verified per-map objective graph JSON files
- live xOV director
- public objective-pressure leaderboards

## Data/model recommendations

Start computed-on-read. Store later only if endpoints become slow or need
history snapshots.

Potential future tables:

```sql
-- future only; do not create until the service design is proven
session_good_night_summary (
  gaming_session_id integer primary key,
  score real not null,
  components jsonb not null,
  reason_chips jsonb not null,
  generated_at timestamp not null
)

session_story_moment (
  id bigserial primary key,
  gaming_session_id integer not null,
  round_id integer,
  player_guid text,
  moment_type text not null,
  score real not null,
  title text not null,
  explanation text,
  source jsonb not null,
  shame_safe boolean not null default true,
  created_at timestamp default current_timestamp
)

session_wave_fight (
  id bigserial primary key,
  round_id integer not null,
  start_ms integer not null,
  end_ms integer not null,
  winner_side text,
  first_blood_guid text,
  score jsonb not null,
  events jsonb not null,
  created_at timestamp default current_timestamp
)

map_objective_graph (
  map_name text primary key,
  version integer not null,
  graph jsonb not null,
  source_notes text,
  verified_by text,
  verified_at timestamp
)

session_stage_split (
  id bigserial primary key,
  round_id integer not null,
  map_name text not null,
  stage_id text not null,
  started_ms integer,
  completed_ms integer,
  partial_progress real,
  source jsonb not null,
  created_at timestamp default current_timestamp
)

round_xov_snapshot (
  id bigserial primary key,
  round_id integer not null,
  elapsed_ms integer not null,
  active_stage_id text,
  attacking_logical_team text,
  xov real not null,
  components jsonb not null,
  created_at timestamp default current_timestamp
)
```

Recommendation:
- Phase 1-3: no new tables.
- Phase 4+: consider storing memory/moment candidates.
- ETL-0/ETL-1: keep objective graphs as versioned JSON first.
- ETL-3: wave fights likely deserve a stored derived table after validation.
- ETL-4+: only store xOV snapshots after the heuristic matches real sessions.

## Copy examples

Good:

```text
Good Night 86 - close teams, 11 players, 3 comeback maps.
```

Good:

```text
Zlatorog had a Good night: 19 frags, 5 above his usual, plus 3 clean trades.
```

Good:

```text
Late chaos: the final hour had two comeback attempts and the night's rarest kill.
```

Bad:

```text
Worst player tonight: ...
```

Bad:

```text
You died uselessly 14 times.
```

Better private/opt-in:

```text
Focus: late deaths were above your usual. Review the two replay waves where it changed the map.
```

## Open questions

1. Should player focus lines be private-only, opt-in, or visible to logged-in owner only?
2. Should "Good Night Index" be Slovenian, English, or mixed Discord slang?
3. How goofy can the labels be? Example: "Late chaos", "Old reliable duo", "Kava aim".
4. Should team suggestions account for voice-channel/social preferences?
5. Do we want "Memory Engine" daily, or only when the candidate is actually strong?
6. Which stats are off-limits for public negative framing?

## Success criteria

This plan is working if:

- morning digest gets clicked because it tells a story, not because it dumps stats
- weaker players still see something positive and true
- the organizer spends less time arranging teams
- post-session pages feel like "that was our evening"
- old memories start resurfacing in Discord
- Greatshot clips become evidence of shared moments, not just frag montages

## Final recommendation

Build in this order:

1. **Good Night Index v0**
2. **Own-form player cards v2**
3. **Friendship-safe team suggestions**
4. **On This Night memory scoring**
5. **Story Worthiness + Greatshot candidates**
6. **Wave Fight Ledger**

This gives Slomix a unique identity: not "the best ET stats site", but the
operating system and memory archive for a long-running friend group.
