# Deep Research: Algorithms, Metrics & Code Quality Patterns

> **Generated**: 2026-02-23 | **For**: Slomix ET:Legacy Discord Bot v1.0.8

---

## Table of Contents

- [Part A: Algorithms & Metrics](#part-a-algorithms--metrics)
  - [1. Industry-Standard FPS Ratings](#1-industry-standard-fps-ratings)
  - [2. Slomix Custom Metrics vs Industry](#2-slomix-custom-metrics-vs-industry)
  - [3. Skill Rating Systems for Team Games](#3-skill-rating-systems-for-team-games)
  - [4. Academic & Novel Approaches](#4-academic--novel-approaches)
  - [5. Recommendations](#5-recommendations-for-slomix)
- [Part B: Code Quality & Architecture](#part-b-code-quality--architecture)
  - [6. Discord Bot Architecture](#6-discord-bot-architecture)
  - [7. Database & Caching Patterns](#7-database--caching-patterns)
  - [8. Data Pipeline & Monitoring](#8-data-pipeline--monitoring)
  - [9. Web Dashboard Integration](#9-web-dashboard-integration)
  - [10. Code Quality Recommendations](#10-code-quality-recommendations)

---

# Part A: Algorithms & Metrics

## 1. Industry-Standard FPS Ratings

### 1.1 HLTV Rating 2.0 (Counter-Strike)

The gold standard for individual FPS player evaluation. Introduced June 2017 by HLTV.org.

**Reverse-engineered formula** (via [flashed.gg](https://flashed.gg/posts/reverse-engineering-hltv-rating/)):

```
Rating 2.0 = 0.0073×KAST + 0.3591×KPR - 0.5329×DPR + 0.2372×Impact + 0.0032×ADR + 0.1587
```

**Components:**

| Component | Weight | Description |
|-----------|--------|-------------|
| **KAST** | 0.0073 | % of rounds with Kill, Assist, Survive, or Trade |
| **KPR** (Kill Rating) | 0.3591 | Kills per round |
| **DPR** (Survival Rating) | -0.5329 | Deaths per round (negative weight) |
| **Impact** | 0.2372 | Multi-kills, opening kills, clutches |
| **ADR** | 0.0032 | Average damage per round |
| Constant | 0.1587 | Baseline offset |

**Key insight**: KPR and DPR dominate the formula. Survival (not dying) is weighted more heavily than killing — a death costs more than a kill earns.

**Comparison to Slomix**: Slomix has no composite rating. The closest analog is FragPotential, but it only captures damage output efficiency. HLTV 2.0 balances output (kills, damage) with cost (deaths) and consistency (KAST).

Sources: [HLTV Rating 2.0 Introduction](https://www.hltv.org/news/20695/introducing-rating-20), [Reverse Engineering HLTV](https://flashed.gg/posts/reverse-engineering-hltv-rating/), [HLTV Wikipedia](https://en.wikipedia.org/wiki/HLTV)

---

### 1.2 HLTV Rating 3.0 (CS2, 2024+)

The latest evolution, purpose-built for Counter-Strike 2.

**Formula structure:**

```
Rating 3.0 = Rating 2.1 core, adjusted for:
  - Economic difference between opponents (eco-adjusted sub-ratings)
  - Round Swing (win probability delta from each action)
  - Trade denials (2 kills within 5 seconds)
  - Removal of "Impact Rating" component
```

**Sub-ratings (all eco-adjusted):**

| Sub-Rating | Adjustment Method |
|------------|-------------------|
| Kill Rating | Win-rate of duel based on map, side, equipment |
| Damage Rating | Same as Kill Rating |
| Survival Rating | Same as Kill Rating |
| KAST Rating | Probability of action given map, side, individual equipment, avg opposing equipment |
| Multi-Kill Rating | Same as KAST Rating |

**Round Swing** is the headline innovation: it measures the team's win probability before and after each kill, factoring in map, side, and economy. Credit for each kill's "swing" is divided based on: final point of damage, damage share, flash assists, and whether it was a trade kill.

**Target balance**: 60/40 between output (kills, impact, damage) and cost (survival, KAST).

**Comparison to Slomix**: ET:Legacy lacks the round-by-round economy system of CS2, so eco-adjustment doesn't directly apply. However, the *concept* of Round Swing — measuring how much a kill changed the team's win probability — could be adapted to ET:Legacy's spawn-wave system: kills timed to maximize enemy respawn wait have higher "swing."

Sources: [HLTV Rating 3.0](https://www.hltv.org/news/42485/introducing-rating-30), [Rating 3.0 Explained](https://escorenews.com/en/csgo/article/71475-how-hltv-rating-3-0-formula-actually-works-round-swing-and-eco-adjustment-explained), [Rating 3.0 Adjustments](https://www.hltv.org/news/43047/rating-30-adjustments-go-live)

---

### 1.3 ADR (Average Damage per Round)

Universal across CS2, Valorant, and competitive FPS.

```
ADR = Total Damage Dealt / Total Rounds Played
```

- Only real health damage counts (overkill excluded in CS2)
- Average ADR in CS2 is ~70-80; elite players hit 90+
- For multi-map series: `Match ADR = Total Damage All Maps / Total Rounds All Maps`

**Comparison to Slomix**: Slomix tracks `damage_given` and has per-round data, but doesn't compute ADR as a first-class metric. FragPotential is DPM-while-alive, which is different — ADR normalizes per round regardless of time alive. **Recommendation**: Add ADR as a displayed metric; it's universally understood.

Sources: [CS2 ADR Explained](https://www.esports.net/wiki/guides/cs2-adr-explained/), [ADR in Valorant](https://dotesports.com/valorant/news/what-is-adr-in-valorant-and-whats-a-good-adr)

---

### 1.4 KAST (Kill/Assist/Survive/Trade)

```
KAST% = (Rounds with at least one of: Kill, Assist, Survive, Trade) / Total Rounds × 100
```

- Meeting multiple criteria in one round still counts as one "contributing round"
- A "trade" = teammate kills the enemy who killed you within ~5 seconds
- 70%+ KAST is considered excellent
- Measures **consistency** rather than peak performance

**Comparison to Slomix**: Slomix has no KAST equivalent. ET:Legacy lacks trade-kill tracking in its stats files, making full KAST impossible without additional data. However, a **simplified version** (Kill/Assist/Survive per round) could be computed from existing data, omitting the Trade component.

Sources: [HLTV KAST](https://www.hltv.org/news/20695/introducing-rating-20), [KAST in Valorant](https://www.esports.net/wiki/guides/what-is-kast-valorant/)

---

### 1.5 RWS (Round Win Share — ESEA)

```
Per round (winning team only):
  - Bomb plant/defuse: Planter/defuser gets 30 RWS, remaining 70 split by damage share
  - Frag round: All 100 RWS split by damage share among winning team
  - Losing team: 0 RWS

Player RWS = Average of all round RWS values
Average RWS ≈ 10.0
```

**Key property**: Only the winning team's efforts are rewarded. High-damage losers get nothing.

**Comparison to Slomix**: ET:Legacy's objective-based gameplay (dynamite, constructions) parallels CS2's bomb mechanic. An adapted RWS could allocate bonus points to the player who plants/defuses dynamite, and share remaining points by damage among the winning side. This would require round outcome data (which side won each round), which Slomix doesn't currently track comprehensively.

Sources: [ESEA RWS FAQ](https://support.esea.net/hc/en-us/articles/360008740634-What-is-RWS-), [RWS Explained](https://csdb.gg/blog/insights/rws-esea)

---

### 1.6 Valorant ACS (Average Combat Score)

```
ACS = Total Combat Score / Total Rounds Played

Combat Score per round:
  + 1 point per damage dealt
  + Kill bonus: 150/130/110/90/70 (scales down with fewer enemies alive)
  + Multi-kill bonus: +50 per additional kill (ace = +200)
  + Non-damaging assists: +25 each
```

**Key innovation**: Kill bonus scales with enemies alive — killing the last enemy (clutch) is worth more than killing one of five.

- Good ACS: 200-250
- Elite ACS: 300+
- Average: 160-180

**Comparison to Slomix**: The scaling kill bonus based on tactical context is clever. In ET:Legacy terms, a kill when the enemy team is near full strength (close to spawn wave) is worth less than a kill that creates a meaningful numbers advantage. This aligns with Slomix's "Useful Kills" concept.

Sources: [Valorant ACS Tracker.gg](https://tracker.gg/valorant/articles/what-is-acs-in-valorant-and-how-does-it-work), [ACS Calculation](https://www.esports.net/wiki/guides/acs-explained-valorant/)

---

### 1.7 Overwatch SR/MMR System

Overwatch uses a modified Elo-based MMR system:

- Base SR change: ~20-30 per win/loss
- **Streak modifiers**: Win streaks increase gains; loss streaks increase losses
- **Rank modifiers**: Consolation (lost against higher-ranked), Reversal (lost when favored), Uphill Battle (won against odds)
- Individual performance tracking via "On Fire" system (correlated but not directly linked to SR)

**Comparison to Slomix**: Overwatch's emphasis on streaks and contextual modifiers could inspire session-level performance tracking — e.g., tracking hot streaks across rounds within a gaming session.

Sources: [Overwatch SR Explained](https://dotesports.com/overwatch/news/overwatch-sr-calculation-explained-16535), [Overwatch Ranking System](https://www.sirlin.net/posts/overwatchs-ranking-point-system)

---

## 2. Slomix Custom Metrics vs Industry

### 2.1 FragPotential — `(damage_given / time_alive_seconds) × 60`

**What it is**: Damage Per Minute while alive (DPM-alive). Unique to Slomix.

**Industry equivalents**:
- **DPS/DPM** (generic FPS): `damage / time` — but usually includes dead time
- **ADR** (CS2/Valorant): `damage / rounds` — normalizes per round, not per time unit
- **Live-time DPM** is actually uncommon in published metrics

**Assessment**: FragPotential is a **novel and valid metric**. It specifically answers "how dangerous is this player while they're active?" By excluding dead time, it doesn't penalize aggressive players who die often but deal massive damage while alive. This is particularly relevant for ET:Legacy's respawn-wave system where time-dead is predictable.

**Strengths**:
- Captures output efficiency better than raw DPM
- Rewards high-tempo play
- Unique to Slomix — not found in other competitive FPS analytics

**Weaknesses**:
- Players with very short alive time can get inflated FP (e.g., die immediately after doing 200 damage in 10 seconds = 1200 FP)
- No minimum alive-time threshold in current implementation
- Doesn't account for damage *quality* (finishing kills vs. chip damage)

**Recommendation**: Keep FragPotential but add a minimum `time_alive_seconds` threshold (e.g., 60 seconds) to prevent spikes. Consider also tracking standard ADR alongside it for cross-game comparability.

---

### 2.2 Survival Rate — `100 - (time_dead / time_played × 100)`

**Industry equivalents**:
- **Survival Rating** (HLTV): Based on deaths per round (DPR), not time
- **Death%** (generic): Deaths / Rounds

**Assessment**: Time-based survival is more nuanced than death-count survival for ET:Legacy specifically, because ET has variable respawn delays (20s Allies, 30s Axis by default). A player who dies 10 times on Axis waits 300 seconds total vs. 200 seconds on Allies for the same death count.

**Recommendation**: Valid as-is for ET:Legacy. Consider also tracking DPR (deaths per round) for cross-game comparability.

---

### 2.3 Damage Efficiency — `damage_given / damage_received`

**Industry equivalents**:
- No exact equivalent found in competitive FPS analytics
- K/D ratio is the closest analog but uses kills/deaths instead of damage
- Some games track "damage differential" (given - received) rather than ratio

**Assessment**: Damage Efficiency as a ratio is **useful but uncommon**. The ratio form can be misleading — a player with 500/100 (5.0) looks much better than 5000/2000 (2.5), even though the second player was far more active and impactful.

**Recommendation**: Keep the ratio but also display damage differential (`damage_given - damage_received`) and total damage dealt. Consider weighting by activity level.

---

### 2.4 Headshot Accuracy — `headshot_kills / total_kills × 100`

**Note**: The CLAUDE.md warns that `headshots ≠ headshot_kills` — they're different stats.

**Industry equivalents**:
- **HS%** (CS2/HLTV): `headshot_kills / total_kills × 100` — identical formula
- Standard metric across all competitive FPS

**Assessment**: Perfectly standard implementation. In ET:Legacy, headshot mechanics differ from CS2 (different damage models, weapon types), but the formula is correct.

**Recommendation**: No changes needed. This is already industry-standard.

---

### 2.5 Useful Kills — kills timed when victim must wait ≥ half limbo time for respawn

**Industry equivalents**:
- **Round Swing** (HLTV 3.0): Measures win probability change per kill
- **First Kill / Entry Kill** (CS2): Valued higher because of round structure
- No direct time-based kill valuation found in published metrics

**Assessment**: This is one of Slomix's most **innovative and ET:Legacy-specific metrics**. In games with spawn waves (ET, TF2, etc.), kill timing relative to the respawn cycle is crucial. Killing an enemy right after they spawn wastes the kill's impact (they respawn in 5 seconds anyway), while killing them right before spawn forces a full wait.

The "≥ half limbo time" threshold is a reasonable heuristic. For a 30-second Axis spawn, this means kills where the victim waits ≥15 seconds.

**Strengths**:
- Captures a fundamentally important ET:Legacy concept
- Not found in any other analytics platform
- Directly rewards tactical awareness of spawn timers

**Weaknesses**:
- Binary threshold (useful/not useful) — a kill at 14.9s wait is "useless" but at 15.1s is "useful"
- Could use a continuous scoring function instead

**Recommendation**: Consider replacing the binary threshold with a **continuous spawn-timing multiplier**:

```python
# Proposed: Kill value scales linearly with wait time
kill_value = wait_time / max_spawn_time  # 0.0 to 1.0
# Or exponential: recently-spawned kills are nearly worthless
kill_value = (wait_time / max_spawn_time) ** 1.5
```

Sources: [ET:Legacy Spawn Mechanics](https://etlegacy.readthedocs.io/en/latest/manual.html), [ET Spawn Time Forums](https://forums.splashdamage.com/t/et-spawn-time-how-to-change/115154)

---

### 2.6 Denied Playtime — total time enemies spent dead because of your kills

**Industry equivalents**:
- No direct equivalent found in any competitive FPS analytics platform
- Conceptually related to **"time advantage"** in military simulation games
- Similar to hockey's **"penalty minutes caused"** concept

**Assessment**: Another **highly original Slomix metric**. This quantifies the concrete impact of kills: how much active game time did you deny the enemy team? A player who kills 10 enemies right before spawn (each waiting 2 seconds) denied 20 seconds, while a player who kills 5 enemies right after spawn (each waiting 28 seconds) denied 140 seconds — the latter is 7x more impactful despite fewer kills.

**Strengths**:
- Captures tactical impact in a way no other metric does
- Directly measures the real-world consequence of kills
- Synergizes beautifully with Useful Kills

**Recommendation**: This is Slomix's strongest original metric. Consider making it a **headline stat** alongside kills and damage. Also consider computing "denied playtime per kill" as an efficiency metric.

---

### 2.7 Playstyle Detection — multi-threshold scoring across 8 categories

**Industry equivalents**:
- **K-means clustering** for player classification (academic: [Springer](https://link.springer.com/chapter/10.1007/978-3-319-10422-5_22))
- **Bayesian playstyle learning** (academic: [arXiv](https://arxiv.org/pdf/2112.07437))
- **Real-time hybrid probabilistic classification** ([Springer](https://link.springer.com/chapter/10.1007/978-3-031-22321-1_5))
- **NVIDIA patent**: Using playstyle patterns to generate virtual player representations

**Current Slomix implementation** (from `frag_potential.py`):
- 8 categories: Fragger, Slayer, Tank, Medic, Sniper, Rusher, Objective, Balanced
- Manual thresholds (e.g., `fp_high: 900`, `kd_high: 1.5`, `hs_sniper: 35`)
- Additive scoring per category, winner-take-all with confidence threshold
- Balanced is the fallback (base score 0.3)

**Assessment**: The current implementation is a **well-designed heuristic system**. It's transparent, tunable, and doesn't require training data. However, academic approaches offer advantages:

| Approach | Pros | Cons |
|----------|------|------|
| **Slomix thresholds** (current) | Transparent, tunable, no training data needed | Thresholds are arbitrary, doesn't learn |
| **K-means clustering** | Data-driven categories, adapts to player base | Categories may not be interpretable |
| **Bayesian classification** | Handles uncertainty, prior knowledge | Complex implementation |
| **Decision tree/Random forest** | Interpretable, handles non-linear boundaries | Needs labeled training data |

**Recommendation**: The current approach is solid for production. For future improvement, consider:
1. **Data-driven threshold calibration**: Use actual player distribution data to set thresholds at meaningful percentiles (e.g., `fp_high` = 90th percentile FP)
2. **Fuzzy classification**: Report top-2 playstyles instead of winner-take-all (e.g., "Fragger/Sniper hybrid")
3. **Session vs. career playstyle**: Track how playstyle evolves over time

Sources: [Online Gamers Classification](https://link.springer.com/chapter/10.1007/978-3-319-10422-5_22), [Bayesian Play Styles](https://arxiv.org/pdf/2112.07437), [NVIDIA Playstyle Patent](https://www.freepatentsonline.com/y2020/0306638.html)

---

### 2.8 Session Detection — 60-minute inactivity gap

**Industry equivalents**:
- **Session Window Algorithm** (stream processing): Standard gap-based session detection used in web analytics, IoT, and gaming
- Typical web session timeout: 30 minutes
- Gaming sessions: 15-60 minutes depending on game type

**Academic reference**: "Dynamic timeout-based session identification algorithm" ([IEEE Xplore](https://ieeexplore.ieee.org/document/5777587)) — proposes adaptive gap thresholds based on user behavior patterns.

**Assessment**: The 60-minute gap is **appropriate for ET:Legacy**. Competitive ET sessions often have map rotations, breaks between matches, and team reorganization. A 30-minute gap (web standard) would incorrectly split sessions during normal between-match breaks.

**Recommendation**: Current 60-minute gap is well-chosen. Future enhancement: adaptive session gaps per player based on their historical break patterns.

Sources: [Session Window Algorithm](https://risingwave.com/glossary/session-window/), [Session-Based Analytics](https://www.randomforestservices.com/post/session-based-analytics-understanding-player-behavior-patterns-in-puzzle-games)

---

### 2.9 Round Correlation — pairing R1+R2 using map name + timestamp proximity

**Industry equivalents**:
- **Log-based event correlation** is a well-studied problem in distributed systems
- Closest FPS analog: CS demo file pairing (map + server + timestamp)
- No published algorithm for ET:Legacy-specific R1/R2 pairing

**Assessment**: The approach (match by map name within a 45-minute window) is pragmatic and correct for ET:Legacy's stopwatch format. The 45-minute `ROUND_MATCH_WINDOW_MINUTES` is generous enough to handle delays but tight enough to avoid false matches.

**Known edge cases** (from CLAUDE.md): midnight crossovers, name changes, multiple sessions per day — all handled.

**Recommendation**: Current implementation is solid. Consider adding a confidence score to round pairing (high confidence = same map + close timestamp; lower confidence = same map + large gap).

---

### 2.10 R2 Differential — R2_only = R2_cumulative - R1

**Industry equivalents**:
- Standard technique in any system with cumulative counters (network bytes, game stats)
- Similar to how SNMP counter differentials work
- No FPS-specific literature found — this is an ET:Legacy data pipeline concern

**Assessment**: The R2 differential calculation is a **data integrity** operation, not a metric. It's correctly handled in `community_stats_parser.py` and the system explicitly warns against recalculating it (correct — double-subtraction would corrupt data).

**Recommendation**: No changes needed. This is correctly implemented and well-documented.

---

## 3. Skill Rating Systems for Team Games

### 3.1 TrueSkill (Microsoft, 2005)

**Model**: Bayesian skill estimation using Gaussian distributions.

```
Player skill = N(μ, σ²)
  μ = estimated skill (mean)
  σ = uncertainty (standard deviation)
  Conservative estimate = μ - 3σ

Update after match:
  μ' = μ + (σ²/c) × v
  σ'² = σ² × (1 - (σ²/c²) × w)
  where v, w derived from match outcome probability
```

**Properties**:
- Works with teams of any size
- Handles free-for-all and multi-team matches
- Used in Halo, Gears of War, Xbox Live

**Comparison to Slomix**: Slomix has no skill rating system. TrueSkill could be implemented to rate ET:Legacy players across sessions.

Sources: [TrueSkill Wikipedia](https://en.wikipedia.org/wiki/TrueSkill), [Microsoft Research](https://www.microsoft.com/en-us/research/project/trueskill-ranking-system/)

---

### 3.2 TrueSkill 2 (Microsoft, 2018)

Extends TrueSkill with individual performance metrics:

**New components**:
- **Individual stats integration**: Incorporates kills/deaths alongside team outcome
- **Squad effect**: Models performance boost from queuing together
- **Experience modeling**: New players improve faster
- **Cross-mode correlation**: Borrows skill estimates across game modes
- **Quit penalty**: Mid-game quitting treated as surrender

**Performance**: 68% match outcome prediction accuracy (vs. 52% for original TrueSkill) on Halo 5 data.

**Comparison to Slomix**: TrueSkill 2's integration of individual stats with team outcomes is directly applicable. ET:Legacy has individual stats (kills, damage) and team outcomes (round wins), plus Slomix already tracks sessions and matches.

**Recommendation**: TrueSkill 2 or OpenSkill (see below) would be the best foundation for a Slomix skill rating system.

Sources: [TrueSkill 2 Paper](https://www.microsoft.com/en-us/research/uploads/prod/2018/03/trueskill2.pdf), [TrueSkill 2 Publication](https://www.microsoft.com/en-us/research/publication/trueskill-2-improved-bayesian-skill-rating-system/)

---

### 3.3 OpenSkill (Open Source, 2024)

**Model**: Bayesian approximation using Plackett-Luce model, designed as open-source TrueSkill alternative.

```python
# Python implementation
from openskill.models import PlackettLuce
model = PlackettLuce()

# Rate a match outcome
[[team1], [team2]] = model.rate([[player1, player2], [player3, player4]])
```

**Properties**:
- 3x faster than Python TrueSkill implementation
- Supports asymmetric teams (3v5, 2v4, etc.)
- Five models with different accuracy/speed tradeoffs
- Pure Python, no proprietary dependencies
- `pip install openskill`

**Comparison to Slomix**: OpenSkill is the **best candidate** for Slomix skill ratings because:
1. Open source (MIT license)
2. Python native
3. Handles asymmetric teams (ET:Legacy sessions often have uneven teams)
4. Well-maintained (PyPI package, active GitHub)
5. Plackett-Luce model balances accuracy and speed

**Recommendation**: **Strongly recommend** implementing OpenSkill for player skill ratings. It would give Slomix a proper ELO-like system with minimal code:

```python
from openskill.models import PlackettLuce
model = PlackettLuce()

# After each match
team_a_ratings = [player_ratings[guid] for guid in team_a_guids]
team_b_ratings = [player_ratings[guid] for guid in team_b_guids]
[new_a, new_b] = model.rate([team_a_ratings, team_b_ratings], ranks=[1, 2])  # 1=winner
```

Sources: [OpenSkill GitHub](https://github.com/vivekjoshy/openskill.py), [OpenSkill Paper](https://arxiv.org/abs/2401.05451), [OpenSkill Docs](https://openskill.me/en/stable/manual.html)

---

## 4. Academic & Novel Approaches

### 4.1 Machine Learning for Player Evaluation

Recent research (2024-2025) uses ML to evaluate CS2 players:

**Key features identified by SHAP analysis** ([SAGE Journals](https://journals.sagepub.com/doi/10.1177/17479541251388864)):
- Kills Per Round (KPR) — most predictive
- Opening Success (OS)
- Rounds With a Kill (RWK)
- Rounds With Multi-Kill (RWMK)
- Support Rounds (SR)
- Pistol Round Rating (PRR)
- Saves Per Round Loss (SPRL)

**Comparison to Slomix**: Most of these could be computed from existing Slomix data. RWK and RWMK are particularly interesting — they measure how often a player contributes kills, not just total kills.

### 4.2 PandaSkill (2025)

**Paper**: "PandaSkill - Player Performance and Skill Rating in Esports" ([arXiv](https://arxiv.org/html/2501.10049v2))

Proposes two novel metrics:
1. **ML-based**: Uses individual player variables and match context
2. **Heuristic-based**: Derived from the ML model's feature importance

Both metrics aim to capture individual contribution to team success, going beyond K/D or damage.

### 4.3 Comprehensive Game Analytics Taxonomy

From Springer's survey ([Link](https://link.springer.com/article/10.1007/s11761-020-00303-z)):

**Three categories of game metrics:**
1. **Player metrics**: Behavior, engagement, skill progression
2. **Process metrics**: Development pipeline, update impact
3. **Performance metrics**: Technical infrastructure, latency

Slomix primarily handles player metrics and is strong in that category.

---

## 5. Recommendations for Slomix

### Priority 1: Quick Wins (Low effort, high value)

| Metric | Formula | Effort | Value |
|--------|---------|--------|-------|
| **ADR** | `damage_given / rounds_played` | Trivial | Universal metric everyone understands |
| **DPR** (Deaths Per Round) | `deaths / rounds_played` | Trivial | Standard survival metric |
| **KPR** (Kills Per Round) | `kills / rounds_played` | Trivial | Standard output metric |
| **Damage Differential** | `damage_given - damage_received` | Trivial | Absolute impact measure |

### Priority 2: Medium-Term (Moderate effort, high value)

| Feature | Description | Effort |
|---------|-------------|--------|
| **OpenSkill ratings** | Bayesian skill rating per player | Medium — library exists, needs match outcome data |
| **Simplified KAST** | Kill/Assist/Survive per round (no Trade) | Medium — needs per-round player state |
| **Continuous Useful Kill scoring** | Replace binary threshold with continuous function | Low-Medium |
| **Denied Playtime per kill** | `total_denied / kills` as efficiency metric | Trivial once denied playtime exists |

### Priority 3: Long-Term (High effort, high value)

| Feature | Description | Effort |
|---------|-------------|--------|
| **Composite Rating** | Weighted combination like HLTV 2.0 adapted for ET | High — needs calibration and tuning |
| **Round Swing** | Win probability change per kill, adapted for spawn waves | High — needs round outcome modeling |
| **Data-driven playstyle thresholds** | Calibrate thresholds from actual player distribution | Medium — needs percentile analysis |
| **Career progression tracking** | Skill rating over time, playstyle evolution | Medium — needs historical data infrastructure |

---

# Part B: Code Quality & Architecture

## 6. Discord Bot Architecture

### 6.1 Cog Organization Best Practices

**Industry pattern**: Discord.py cogs are the standard for modular bot design. The recommended approach for 20+ cog projects:

```
bot/
├── cogs/
│   ├── __init__.py
│   ├── stats.py          # Player statistics
│   ├── admin.py           # Admin commands
│   ├── leaderboard.py     # Leaderboards
│   └── ...
├── core/                  # Business logic (NOT in cogs)
├── services/              # External integrations
└── main.py                # Entry point with dynamic cog loading
```

**Key principles** ([Medium: Architecting Discord Bots](https://itsnikhil.medium.com/architecting-discord-bot-the-right-way-46e426a0b995)):

1. **Treat the bot as a frontend client**: Business logic belongs in `core/` and `services/`, not in cogs
2. **Dynamic cog loading**: Auto-discover and load cogs from a directory
3. **Separation of concerns**: Cogs handle Discord interaction; core handles business logic
4. **Error handling at the cog level**: Each cog catches and reports its own errors

**Comparison to Slomix**:
- **21 cogs, 18 core modules, separate services layer** — this is excellent architecture
- Slomix already follows the "bot as frontend" pattern with `core/` for business logic
- The `bot/core/CLAUDE.md` shows clear module responsibilities

**Assessment**: Slomix's architecture is **above average** for Discord bot projects. Most large bots lack the clean separation between cogs, core, and services that Slomix has.

Sources: [Architecting Discord Bot](https://itsnikhil.medium.com/architecting-discord-bot-the-right-way-46e426a0b995), [Discord.py Masterclass Cogs](https://fallendeity.github.io/discord.py-masterclass/cogs/), [Advanced Discord Bot Strategies](https://arnauld-alex.com/building-a-production-ready-discord-bot-architecture-beyond-discordjs)

---

### 6.2 Microservices vs Monolith for Discord Bots

**Industry recommendation**: For bots with web dashboards, treat the Discord bot and web server as separate services communicating via shared database or API.

**Pattern**:
```
Discord Bot ←→ Shared Database ←→ Web Backend (FastAPI)
     ↑                                    ↑
   discord.py                          FastAPI
```

**Comparison to Slomix**: Slomix already has this architecture — the bot and website are separate components sharing the PostgreSQL database. This is the recommended pattern.

**Potential improvement**: Consider adding a message queue (Redis pub/sub) for real-time bot→website events (e.g., "new round imported" notifications for live dashboard updates).

---

## 7. Database & Caching Patterns

### 7.1 Async Database Adapter

**Best practice** ([GitHub Gist](https://gist.github.com/jegfish/cfc7b22e72426f5ced6f87caa6920fd6)):

- Use `asyncpg` for PostgreSQL (not sync `psycopg2`)
- Initialize connection pool in bot's `start()` method (NOT `on_ready`, which fires multiple times)
- Use `asyncpg.create_pool()` with `min_size` and `max_size` parameters
- Acquire connections via `async with pool.acquire()` context manager

**Comparison to Slomix**: Slomix's `database_adapter.py` provides async PostgreSQL/SQLite abstraction. Key considerations:
- Does it use connection pooling? If not, each query creates a new connection (expensive)
- The `?` placeholder syntax suggests it may use `aiosqlite`-style adapters rather than native `asyncpg`

**Recommendation**: Ensure the PostgreSQL path uses `asyncpg` with connection pooling:

```python
# Ideal setup
pool = await asyncpg.create_pool(
    dsn=DATABASE_URL,
    min_size=2,
    max_size=10,
    max_inactive_connection_lifetime=300
)
```

Sources: [FastAPI + asyncpg](https://www.sheshbabu.com/posts/fastapi-without-orm-getting-started-with-asyncpg/), [asyncpg Best Practices](https://daniel.feldroy.com/posts/2025-10-using-asyncpg-with-fastapi-and-air), [High-Performance Async APIs](https://leapcell.io/blog/building-high-performance-async-apis-with-fastapi-sqlalchemy-2-0-and-asyncpg)

---

### 7.2 Caching Strategy

**Best practices** ([StudyRaid](https://app.studyraid.com/en/read/7183/176831/caching-strategies-for-discord-bots)):

| Data Type | Cache Strategy | TTL |
|-----------|---------------|-----|
| Static data (maps, configs) | Long-lived cache | 1-24 hours |
| Player stats (per session) | Medium TTL | 5-15 minutes |
| Live game state | Short TTL | 30-60 seconds |
| Leaderboards | Event-driven invalidation | On new round import |

**Comparison to Slomix**: `StatsCache` uses a flat 5-minute TTL for all data. The implementation is clean and correct but could be enhanced:

**Current strengths**:
- Simple, correct TTL logic
- Lazy expiration (cleaned on access)
- Good logging

**Potential improvements**:
1. **Tiered TTL**: Different TTLs for different data types
2. **Max cache size**: No memory bound — could grow unbounded during long sessions
3. **Cache warming**: Pre-populate common queries on round import
4. **Event-driven invalidation**: Clear relevant cache entries when new data is imported (not just time-based)

**Recommendation**: Add a `max_size` parameter with LRU eviction, and consider event-based invalidation for round imports:

```python
class StatsCache:
    def __init__(self, ttl_seconds=300, max_size=1000):
        self.max_size = max_size
        # ... existing code

    def set(self, key, value):
        if len(self.cache) >= self.max_size:
            self._evict_oldest()
        # ... existing code

    def invalidate_pattern(self, pattern: str):
        """Invalidate all keys matching a pattern (e.g., 'session_*')"""
        to_delete = [k for k in self.cache if pattern in k]
        for k in to_delete:
            del self.cache[k]
            del self.timestamps[k]
```

Sources: [Caching Strategies](https://app.studyraid.com/en/read/7183/176831/caching-strategies-for-discord-bots), [Data Caching Optimization](https://app.studyraid.com/en/read/7183/176810/data-caching-and-optimization)

---

## 8. Data Pipeline & Monitoring

### 8.1 SSH File Monitoring

**Best practices**:

| Practice | Description | Slomix Status |
|----------|-------------|---------------|
| **Key-based auth** | SSH keys over passwords | Yes (SSH_KEY_PATH) |
| **Connection pooling** | Reuse SSH connections | Unknown |
| **Exponential backoff** | On connection failure | Unknown |
| **Health checks** | Verify SSH before polling | Unknown |
| **Dead Letter Queue** | Track failed file imports | Not implemented |

**Comparison to Slomix**: The SSH monitoring uses a 60-second polling loop (`endstats_monitor` task), which is appropriate for the use case. The SSHMonitor class was disabled due to race conditions, and monitoring was consolidated into the task loop — this is a **correct architectural decision** (single consumer is safer than competing consumers).

**Recommendation**: Add retry logic with exponential backoff for SSH connection failures:

```python
async def poll_with_retry(self, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await self._ssh_poll()
        except SSHException:
            wait = min(2 ** attempt * 5, 60)  # 5s, 10s, 20s, max 60s
            await asyncio.sleep(wait)
    logger.error("SSH polling failed after retries")
```

Sources: [Paramiko Best Practices](https://coderivers.org/blog/paramiko-python/), [Retry Patterns](https://leapcell.io/blog/seven-retry-patterns)

---

### 8.2 Data Pipeline Reliability

**Industry patterns** ([Airbyte](https://airbyte.com/data-engineering-resources/how-to-manage-dependencies-and-retries-in-data-pipelines)):

1. **Retry with exponential backoff**: 3-5 retries with increasing delays
2. **Circuit breaker**: Stop retrying after threshold failures, wait, then resume
3. **Dead Letter Queue (DLQ)**: Failed items go to a separate queue for manual review
4. **Idempotent processing**: Safe to re-process the same file multiple times
5. **Checkpointing**: Save progress so failures don't restart from scratch

**Comparison to Slomix**: Slomix uses SHA256 for file deduplication (idempotent processing) and tracks processed files. This is good. Missing elements:
- No DLQ for files that fail to parse
- No circuit breaker for persistent SSH failures
- No pipeline health dashboard

**Recommendation**: Add a `failed_imports` table to track files that couldn't be processed:

```sql
CREATE TABLE failed_imports (
    id SERIAL PRIMARY KEY,
    filename TEXT NOT NULL,
    sha256 TEXT,
    error_message TEXT,
    attempt_count INTEGER DEFAULT 1,
    first_failed_at TIMESTAMPTZ DEFAULT NOW(),
    last_failed_at TIMESTAMPTZ DEFAULT NOW(),
    resolved BOOLEAN DEFAULT FALSE
);
```

Sources: [Data Pipeline Reliability](https://datalakehousehub.com/blog/2026-02-de-best-practices-02-design-data-pipelines/), [Retry Patterns](https://leapcell.io/blog/seven-retry-patterns)

---

## 9. Web Dashboard Integration

### 9.1 FastAPI + Discord.py Pattern

**Recommended pattern** ([Medium](https://makubob.medium.com/combining-fastapi-and-discord-py-9aad07a5cfb6)):

```python
# Run both in the same event loop
import asyncio

async def main():
    bot = MyBot()
    config = uvicorn.Config(app, host="0.0.0.0", port=8000)
    server = uvicorn.Server(config)
    await asyncio.gather(bot.start(TOKEN), server.serve())
```

**Or (recommended for production)**: Run as separate processes sharing the database:

```
[Discord Bot Process] → PostgreSQL ← [FastAPI Process]
```

**Comparison to Slomix**: Slomix runs the bot and website as separate components, which is the **correct production pattern**. They share the PostgreSQL database.

**Potential enhancement**: Add Discord OAuth2 for the website dashboard using `fastapi-discord`:

```python
from fastapi_discord import DiscordOAuthClient

discord_oauth = DiscordOAuthClient(
    client_id="...", client_secret="...",
    redirect_url="https://..../callback",
    scopes=("identify", "guilds")
)
```

Sources: [FastAPI + Discord.py](https://makubob.medium.com/combining-fastapi-and-discord-py-9aad07a5cfb6), [fastapi-discord](https://github.com/Tert0/fastapi-discord), [Polly Bot Example](https://github.com/pacnpal/polly)

---

### 9.2 FastAPI + PostgreSQL Best Practices

**Key recommendations** (2025/2026):

| Practice | Description |
|----------|-------------|
| **Connection pooling** | `asyncpg.create_pool(min_size=2, max_size=10)` |
| **Lifespan functions** | Initialize pool in FastAPI lifespan, not on first request |
| **Dependency injection** | Use `Depends()` for database connections |
| **Connection release** | Always use `async with pool.acquire()` context manager |
| **Pool tuning** | `max_inactive_connection_lifetime=300` to recycle idle connections |

**Performance**: asyncpg pools deliver 4-6x higher QPS than sync psycopg2 in asyncio apps.

Sources: [Neon FastAPI Guide](https://neon.com/guides/fastapi-async), [FastAPI asyncpg](https://www.sheshbabu.com/posts/fastapi-without-orm-getting-started-with-asyncpg/), [Gino AsyncPG Best Practices](https://www.johal.in/gino-asyncpg-connection-pool-best-practices-2025/)

---

## 10. Code Quality Recommendations

### 10.1 Architecture Score Card

| Category | Current State | Industry Standard | Score |
|----------|--------------|-------------------|-------|
| **Cog organization** | 21 cogs, well-separated | Dynamic loading, grouped | 9/10 |
| **Business logic separation** | 18 core modules | Service/repository pattern | 8/10 |
| **Database abstraction** | Async adapter with fallback | Connection pool + DI | 7/10 |
| **Caching** | 5-min TTL, simple dict | Tiered TTL, LRU, invalidation | 6/10 |
| **Error handling** | Admin notifications, logging | Circuit breaker, DLQ | 6/10 |
| **Data pipeline** | SHA256 dedup, task loop | Retry, DLQ, health checks | 7/10 |
| **Documentation** | Extensive CLAUDE.md, guides | Auto-generated API docs | 9/10 |
| **Custom metrics** | Novel, well-implemented | Industry-validated | 8/10 |
| **Skill rating** | None | TrueSkill/OpenSkill | 3/10 |
| **Testing** | Smoke tests, scripts | CI/CD, unit tests, integration | 5/10 |

**Overall: 6.8/10** — Above average for a community project, with particular strengths in documentation and metric innovation.

---

### 10.2 Top 5 Actionable Improvements

1. **Add OpenSkill player ratings** — The single highest-impact feature missing. Players want to see their skill level change over time. `pip install openskill` gets you 80% there.

2. **Add standard metrics (ADR, KPR, DPR)** — Trivial to compute, universally understood, and allows players to benchmark against other FPS games.

3. **Enhance StatsCache with LRU + max size** — Prevent unbounded memory growth and add event-driven invalidation on round import.

4. **Add pipeline reliability** — Failed import tracking (DLQ table), SSH retry with backoff, and a health check endpoint.

5. **Promote Denied Playtime and Useful Kills** — These are Slomix's most original contributions. Make them headline stats and consider the continuous scoring function for Useful Kills.

---

### 10.3 What Slomix Does Better Than Industry

Not everything needs to change. Slomix excels in areas where industry tools fall short:

1. **Denied Playtime**: No other FPS analytics platform quantifies the actual time impact of kills relative to spawn waves. This is genuinely novel.

2. **FragPotential (DPM-alive)**: While DPM exists everywhere, specifically measuring damage output *excluding dead time* is uncommon and valuable for spawn-wave games.

3. **Useful Kills with spawn timing**: Weighting kills by spawn-timer proximity is unique to Slomix and captures an ET:Legacy-specific tactical dimension.

4. **Comprehensive documentation**: The multi-layer CLAUDE.md system (root, bot, core) with explicit pitfall warnings is better documentation than most open-source projects of any size.

5. **ET:Legacy-specific round correlation**: The R1+R2 differential parser with stopwatch-mode awareness handles a genuinely complex data problem well.

---

*Report generated from 20+ web searches across competitive FPS analytics, academic game research, Discord bot architecture, and data pipeline engineering.*
