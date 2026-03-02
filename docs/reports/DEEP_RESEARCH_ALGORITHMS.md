# Deep Research: Algorithms, Metrics & Architecture Patterns

> **Generated**: 2026-02-23 | **Scope**: FPS stat tracking, skill rating, data pipelines, architecture patterns
> **Purpose**: Validate and improve Slomix's custom algorithms against industry standards

---

## Table of Contents

1. [FPS Performance Metrics (Industry Standard)](#1-fps-performance-metrics-industry-standard)
2. [Skill Rating Algorithms](#2-skill-rating-algorithms)
3. [Slomix Algorithm Validation & Recommendations](#3-slomix-algorithm-validation--recommendations)
4. [Code Quality & Architecture Patterns](#4-code-quality--architecture-patterns)
5. [Data Pipeline Reliability](#5-data-pipeline-reliability)
6. [Round/Match Reconstruction](#6-roundmatch-reconstruction)
7. [Session Detection Algorithms](#7-session-detection-algorithms)
8. [Database Schema Patterns](#8-database-schema-patterns)
9. [Automation & Monitoring Patterns](#9-automation--monitoring-patterns)
10. [Summary of Recommendations](#10-summary-of-recommendations)

---

## 1. FPS Performance Metrics (Industry Standard)

### 1.1 HLTV Rating Evolution (CS2)

The gold standard for FPS player performance metrics, evolving across three major versions.

#### Rating 2.0 (Reverse-Engineered Formula)

The exact formula was kept confidential by HLTV, but [flashed.gg reverse-engineered](https://flashed.gg/posts/reverse-engineering-hltv-rating/) an approximation accurate to within ±0.01:

```
Rating 2.0 ≈ 0.0073×KAST + 0.3591×KPR − 0.5329×DPR + 0.2372×Impact + 0.0032×ADR + 0.1587
```

**Components:**
| Sub-Rating | What It Measures |
|------------|-----------------|
| **KAST** | % of rounds with Kill, Assist, Survive, or Traded death |
| **KPR** | Kills Per Round |
| **DPR** | Deaths Per Round (negative weight — dying is punished) |
| **Impact** | Multi-kills, opening kills, 1vX clutch wins |
| **ADR** | Average Damage Per Round |

**Key insight**: Deaths (DPR) has the largest absolute weight (−0.5329), meaning staying alive matters more than getting kills.

#### Rating 2.1 (CS2 Adaptation, Oct 2024)

Updated using 1 year of CS2 data:
- Average rating returned to 1.00 over events
- All five sub-ratings given **equal weight** (survival/KAST were too dominant in 2.0)
- Survivals in lost rounds give lower reward
- Assisted kills (25-damage assists in CS2 vs 40 in CSGO) give more reward

#### Rating 3.0 (Aug 2025, Current)

```
Rating 3.0 = Rating 2.1 +/− Eco Adjustment +/− Round Swing
```

**Six sub-ratings**: Kills, Damage, KAST, Survival, Multi-Kills, **Round Swing** (new).

**Round Swing** is the major innovation:
- Measures how each kill changes team's **win probability** for the round
- Considers: economy situation, bomb planted status, players alive, map, CT/T side
- Credit distributed: 35% kill credit, 30% damage share, 15% flash assists, 20% trade kills
- Eco frags (kills against under-equipped opponents) weighted less
- Kills against better-equipped players weighted more

**October 2025 adjustment**: Reduced Round Swing weight, increased kill weight to restore 60-40 balance (output vs survival stats).

**Relevance to Slomix**: ET:Legacy doesn't have economy, but the concept of **context-weighted kills** (kills that happen at critical moments) maps directly to the "useful kills" concept. Slomix could weight kills based on spawn wave timing impact.

---

### 1.2 ADR (Average Damage Per Round)

```
ADR = Total Damage Dealt / Rounds Played
```

**Benchmarks:**
| Game | Good | Excellent | Outstanding |
|------|------|-----------|-------------|
| CS2 | 70-80 | 80-95 | 95+ |
| Valorant | 110-130 | 140-160 | 160+ |

**Comparison to Slomix's FragPotential**: ADR is per-round, FragPotential is per-minute-alive. Both measure damage output efficiency but with different denominators. ADR is simpler and more widely understood; FragPotential accounts for time alive which is more nuanced for ET:Legacy's longer rounds.

---

### 1.3 KAST (Kill/Assist/Survive/Trade)

```
KAST = (Rounds with K, A, S, or T) / Total Rounds × 100
```

- **Kill**: Got at least one kill in the round
- **Assist**: Got at least one assist
- **Survive**: Survived the round
- **Traded**: Died but a teammate avenged within ~5 seconds

**Typical range**: 65-80% for average players, 75%+ for good players.

**Relevance to Slomix**: ET:Legacy rounds are longer and don't have the same "one death ends your round" dynamic, but KAST could be adapted: measure % of spawn waves where a player contributed meaningfully (kill, revive, objective action).

---

### 1.4 ESEA RWS (Round Win Shares)

```
Total RWS per round = 100 (distributed only to winning team)
```

**Distribution rules:**
- **Frag-ended rounds**: 100 RWS split by damage share
- **Bomb objective rounds**: 30 RWS to objective completer + 70 split by damage share
- **Profile RWS**: Career total RWS / (total rounds + rounds left)

**Average**: ~10 RWS. Range: 0-100 per round, but career average typically 6-14.

**Relevance to Slomix**: The "only winning team gets credit" concept is interesting but may not suit ET:Legacy's objective-based mode where both sides contribute. The damage-share-based distribution is similar to what Slomix could implement for "round contribution" metrics.

---

### 1.5 Valorant ACS (Average Combat Score)

```
ACS = Total Combat Score / Rounds Played
```

**Combat Score per round:**
| Action | Points |
|--------|--------|
| Damage dealt | 1 point per HP |
| Kill (5 alive) | 150 |
| Kill (4 alive) | 130 |
| Kill (3 alive) | 110 |
| Kill (2 alive) | 90 |
| Kill (last enemy) | 70 |
| Multi-kill bonus | +50 per extra kill |
| Ace bonus | +200 |
| Non-damage assist | 25 |

**Key insight**: Kills when more enemies are alive are worth more — entry frags > cleanup kills. This "context-weighted kills" concept is very relevant to Slomix's "useful kills" metric.

---

### 1.6 Leetify Rating (CS2)

A zero-sum, win-probability-based rating:

```
Leetify Rating = Average round-by-round contribution to win probability change
```

**Kill credit distribution:**
- 35% to the player who secures the kill
- 30% to all players who dealt damage
- 15% for flash assists
- 20% for traded deaths

**Key properties:**
- Zero-sum: all ratings in a match sum to zero
- Economy-aware: considers buy levels (4 tiers per side)
- Uses historical CS2 data from HLTV for win probability baselines
- Does NOT consider player history — everyone treated equally

**Relevance to Slomix**: The "damage share" distribution concept (not just final blow gets credit) could improve ET:Legacy kill attribution. The win-probability shift approach is sophisticated but requires baseline data Slomix doesn't yet have.

---

### 1.7 Overwatch SR/MMR

- Hidden MMR drives matchmaking
- **30+ stats** feed into ML models per match
- Considers: damage dealt, healing, objective time, eliminations, "team impact metrics"
- Players with strong assist ratios and objective participation climb faster
- Performance-based adjustments below Diamond rank; pure win/loss above

**Relevance to Slomix**: The multi-stat ML approach validates Slomix's multi-threshold playstyle detection. The "team impact" concept maps to ET:Legacy's revives, objective completions, and ammo/health packs.

---

## 2. Skill Rating Algorithms

### 2.1 Elo (Classic)

```
New Rating = Old Rating + K × (Actual − Expected)
Expected = 1 / (1 + 10^((Opponent − Self) / 400))
```

- K-factor typically 20-40
- Only for 1v1 or simplified team scenarios
- No uncertainty tracking

### 2.2 Glicko-2

Extends Elo with:
- **Rating Deviation (RD)**: Uncertainty grows with inactivity
- **Volatility (σ)**: How consistent a player's performance is
- Better for players who play infrequently
- Still primarily designed for 1v1

### 2.3 TrueSkill / TrueSkill 2 (Microsoft)

```
Skill = μ − 3σ  (conservative estimate)
```

- Bayesian inference model
- Supports teams and multiplayer
- **TrueSkill 2** (2018) adds: player experience, squad membership, individual stats (K/D), quitting behavior
- Used in Xbox Live matchmaking

### 2.4 OpenSkill (Weng-Lin)

Modern, open-source alternative to TrueSkill:

```python
# pip install openskill
from openskill.models import PlackettLuce

model = PlackettLuce()
# Each player: (mu, sigma) — mu=skill estimate, sigma=uncertainty
team1 = [model.rating(), model.rating()]
team2 = [model.rating(), model.rating()]
[team1, team2] = model.rate([team1, team2])  # team1 won
```

**Advantages:**
- 3× faster than TrueSkill Python implementations
- Supports asymmetric teams (3v4, 5v6, etc.)
- MIT licensed (no patent restrictions like TrueSkill)
- Multiple models: Plackett-Luce, Bradley-Terry, Thurstone-Mosteller
- Time decay support for inactive players

**Recommendation for Slomix**: OpenSkill is the best fit for ET:Legacy's team-based gameplay. It handles:
- Variable team sizes (common in ET pickup games)
- Bayesian uncertainty (good for new players)
- No license restrictions
- Python native implementation

---

## 3. Slomix Algorithm Validation & Recommendations

### 3.1 FragPotential — VALIDATED ✅ (with suggested enhancement)

**Current formula:**
```
FragPotential = (damage_given / time_alive_seconds) × 60
```

**Industry comparison:**
- Closest to **DPM (Damage Per Minute)** used in MOBAs and some FPS analytics
- ADR (damage/rounds) is more common in round-based FPS, but ET:Legacy rounds are 10-30 minutes, not 2-minute CS2 rounds
- FragPotential's use of time_alive (not total time) is **more sophisticated** than standard ADR/DPM — it correctly ignores dead time

**Verdict**: Good metric, well-suited to ET:Legacy. More informative than ADR for long-round games.

**Suggested enhancement — add "Damage Per Life" variant:**
```
DamagePerLife = damage_given / (deaths + 1)  // +1 to avoid division by zero
```
This complements FragPotential by measuring damage efficiency per spawn, similar to "damage per death" used in some analytics platforms.

---

### 3.2 Survival Rate — VALIDATED ✅

**Current formula:**
```
Survival Rate = 100 − (time_dead / time_played × 100)
```

**Industry comparison:**
- HLTV's Survival sub-rating uses deaths per round (DPR) — lower is better
- Overwatch tracks "time alive %" similarly
- Slomix's approach is directly measuring alive-time %, which is more granular than DPR

**Verdict**: Solid metric. More nuanced than binary survive/die-per-round metrics used in CS2.

---

### 3.3 Damage Efficiency — VALIDATED ✅ (suggest normalization)

**Current formula:**
```
Damage Efficiency = damage_given / damage_received
```

**Industry comparison:**
- Similar to "Damage Ratio" used in some analytics
- CS2/Valorant don't commonly use this because rounds are short and health doesn't regenerate
- In ET:Legacy, medics heal, so damage received can be "recovered" — this metric makes more sense here

**Suggested enhancement — bounded version:**
```
Bounded Efficiency = damage_given / (damage_given + damage_received)
// Range: 0.0 to 1.0 (0.5 = even trade, >0.5 = positive)
```
This avoids the unbounded nature of ratios (a 50:1 ratio isn't meaningfully different from 100:1 in practice).

---

### 3.4 Headshot Accuracy — VALIDATED ✅

**Current formula:**
```
Headshot Accuracy = headshot_hits / total_hits × 100
```

**Industry comparison:**
- CS2 tracks headshot percentage identically
- Valorant tracks "HS%" the same way
- This is the universal standard

**Verdict**: Perfect implementation. No changes needed.

---

### 3.5 Useful Kills — INNOVATIVE ✅ (unique to Slomix)

**Current concept**: Kills timed when victim must wait long for respawn.

**Industry comparison:**
- **No direct equivalent exists** in CS2/Valorant (they have elimination-based rounds)
- HLTV's "Round Swing" is the closest conceptual analog — it measures how much a kill changes win probability
- Valorant's ACS gives more points for kills when more enemies are alive (similar value-weighting concept)
- TF2 community has "spawn advantage" analysis based on respawn wave alignment

**ET:Legacy spawn wave context:**
ET:Legacy uses fixed-interval spawn waves (typically 20-30 seconds, configurable per server). A kill right after the enemy spawns means maximum denied playtime; a kill right before the next spawn wave means minimal denial.

**Suggested enhancement — formalize with spawn wave math:**
```
Kill Value = base_value × (seconds_until_next_enemy_spawn / spawn_wave_interval)
```
Where `seconds_until_next_enemy_spawn` comes from the server's spawn timer configuration. This makes "useful kills" a continuous metric rather than a threshold-based one.

---

### 3.6 Denied Playtime — INNOVATIVE ✅ (unique to Slomix)

**Current concept**: Total time enemies spent dead because of your kills.

**Industry comparison:**
- **No direct equivalent** in any major FPS analytics platform
- Closest concept: "tempo advantage" in MOBA analytics (how long an enemy is off the map)
- TF2 Medic Übercharge economy analysis considers denied time similarly
- This is genuinely novel and valuable for ET:Legacy's respawn-wave gameplay

**Verdict**: Keep as-is. This is a strong differentiator. Consider also tracking "cumulative spawn wave advantage" — if your kill causes an enemy to miss a spawn wave, that's a 20-30 second swing vs just a 3-second swing for a kill near the next wave.

---

### 3.7 Playstyle Detection — GOOD ✅ (suggest ML enhancement path)

**Current approach**: Rule-based multi-threshold scoring across 8 categories (Fragger, Slayer, Tank, Medic, Sniper, Rusher, Objective, Balanced).

**Industry comparison:**

**Academic approaches:**
- **K-Means clustering** on behavioral features (Battlefield 2/Tera studies)
- **Archetype Analysis** finding extreme behavioral profiles (GameAnalytics)
- **Random Forest classification** for skill prediction from gameplay input
- **Nonnegative Tensor Factorization (NTF)** on match×feature×time tensors
- **Bayesian learning of play styles** (Battlefield 3 study found 90 clusters)
- **Decision Tree classifiers** (CART/C5.0) achieving ~70% accuracy

**Rule-based vs ML:**

| Approach | Pros | Cons |
|----------|------|------|
| Rule-based (Slomix current) | Interpretable, no training data needed, deterministic | Rigid boundaries, may miss emergent patterns |
| K-Means clustering | Discovers natural groupings | Requires choosing K, hard to label clusters |
| Decision Trees | Interpretable like rules but data-driven | Needs labeled training data |
| Neural/Deep | Most flexible | Black box, needs lots of data |

**Verdict**: The rule-based approach is **appropriate for Slomix's data volume**. ML approaches require thousands of player-sessions; a community ET:Legacy server likely has hundreds. Keep rule-based for now.

**Suggested enhancement path:**
1. Log playstyle classification results to a table
2. After accumulating 500+ classifications, run k-means on the raw features to see if natural clusters match the 8 predefined categories
3. If they diverge, consider adding or merging categories
4. Add a "confidence" field to playstyle detection (how strongly does the player fit one archetype vs being split)

---

### 3.8 Session Detection (60-minute gap) — VALIDATED ✅

**Current approach**: 60-minute inactivity gap defines session boundaries.

**Industry comparison:**
- **Google Analytics**: 30-minute default session timeout
- **GameAnalytics**: Uses platform signals (app backgrounding) + timeouts
- **Academic research**: "Inter-session interval" varies by game genre
  - Casual/mobile: 30 minutes
  - Competitive/PC: 30-60 minutes
  - MMO/persistent: 2-4 hours
- More sophisticated approaches use **context signals**: level completion, explicit logout, platform state changes

**For competitive FPS gaming**: 60 minutes is well-calibrated. Players who take a break longer than an hour are genuinely starting a new session. Players who take a 30-minute dinner break in the middle of a gaming evening should be in the same session.

**Verdict**: 60 minutes is correct for this use case. No change needed.

**Optional enhancement**: Track "sub-sessions" within a session — detect natural breaks (10-15 minute gaps) for finer-grained analysis without breaking the session boundary.

---

## 4. Code Quality & Architecture Patterns

### 4.1 Large Discord Bot Organization

**Slomix current**: 21 cogs in `bot/cogs/`, 18 core modules in `bot/core/`, services in `bot/services/`.

**Industry patterns for large Discord.py bots:**

#### Layered Architecture (Recommended)
```
bot/
├── cogs/          # Presentation layer (Discord UI)
├── core/          # Business logic layer
├── services/      # External service integration
├── repositories/  # Data access layer
└── models/        # Data transfer objects
```

Slomix already follows this pattern well. The key principle is: **cogs should be thin** — they handle Discord interaction but delegate to core/services for logic.

#### Error Handling Patterns
```python
# Pattern: Centralized error handler in bot
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return  # Silent ignore
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("Insufficient permissions.")
    else:
        logger.error(f"Command error: {error}", exc_info=True)
        await alert_admins(f"Error in {ctx.command}: {error}")
```

#### Caching Strategies
- **TTL cache** (Slomix uses 5-min TTL — good)
- **LRU cache** for frequently accessed, rarely changing data (player names, GUIDs)
- **Invalidation on write**: When a new round is imported, invalidate relevant cache keys
- **Tiered caching**: Hot data (current session) in memory, warm data (recent sessions) in Redis/cache, cold data (historical) only from DB

### 4.2 Database Adapter Patterns

**Slomix current**: `database_adapter.py` with async PostgreSQL/SQLite abstraction.

**Best practices from large projects:**
- **Connection pooling**: Use asyncpg with pool (min_size=2, max_size=10)
- **Query builder vs raw SQL**: Raw SQL is fine for analytics-heavy projects (better optimization control)
- **Retry with exponential backoff** for transient DB errors:
```python
async def fetch_with_retry(query, params, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await db.fetch_all(query, params)
        except (ConnectionError, TimeoutError) as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)
```

---

## 5. Data Pipeline Reliability

### 5.1 Current Slomix Pipeline
```
ET:Legacy Server → SSH (60s poll) → Stats Parser → PostgreSQL → Discord Bot
```

### 5.2 Event-Driven vs Polling

| Approach | Latency | Complexity | Reliability |
|----------|---------|------------|-------------|
| **Polling (Slomix current)** | 0-60s | Low | High (simple to reason about) |
| **Webhook/Push** | <1s | Medium | Medium (needs retry logic) |
| **Pub/Sub (Redis/NATS)** | <1s | High | High (with proper ack) |
| **Hybrid** | <1s normal, 60s fallback | Medium | Highest |

**Slomix already has hybrid**: Lua webhook (v1.6.2) for real-time round notification + SSH polling as fallback. This is the **recommended industry pattern**.

### 5.3 Retry & Deduplication

**Industry best practices:**
1. **Idempotent processing**: SHA256 hash of stats files (Slomix already does this ✅)
2. **Retry with backoff**: 3 attempts with exponential delay before alerting
3. **Dead letter queue**: Failed files stored separately for manual review
4. **Event IDs**: Globally unique IDs per ingestion event to prevent duplicate processing
5. **Watermarking**: Track "latest processed timestamp" to detect gaps

**Slomix recommendation**: The SHA256-based deduplication is solid. Consider adding:
- A `failed_imports` table for files that parse but fail to insert
- Alerting when SSH polling fails N consecutive times
- A health check endpoint that reports last successful import time

### 5.4 Data Completeness Monitoring

From [AWS Game Analytics Pipeline](https://github.com/awslabs/game-analytics-pipeline):
- Instrument every pipeline stage
- Track: events received, events processed, events failed
- Alert on: processing gaps, sudden throughput changes, error rate spikes

---

## 6. Round/Match Reconstruction

### 6.1 Current Slomix Approach

ET:Legacy uses a stopwatch mode where:
- Round 1 (R1): Stats file with raw stats
- Round 2 (R2): Stats file with **cumulative** stats
- Parser calculates R2-only stats: `R2_actual = R2_cumulative − R1`
- R1-R2 matching uses 45-minute window and map name

### 6.2 Industry Patterns for Round Pairing

**CS2 Demo Parsing** (cs-demo-manager, demoinfocs-golang):
- Rounds are explicitly tagged with match IDs in demo files
- No reconstruction needed — game engine provides the structure

**Riot Games (Valorant)**:
- API returns complete match objects with all rounds pre-structured

**For games without explicit match IDs** (like ET:Legacy):
- **Temporal proximity**: Rounds within a time window on the same map = same match (Slomix does this ✅)
- **Player overlap**: >60% same players = likely same match
- **Map continuity**: Same map + same server = same match

### 6.3 Cumulative vs Differential Stats

Slomix's R2 differential approach is **correct and necessary** given ET:Legacy's cumulative R2 format. Key considerations:
- Validate that R2 values ≥ R1 values (catch corruption)
- Handle player disconnects (R1 has player that R2 doesn't, and vice versa)
- Handle midnight rollover edge cases

---

## 7. Session Detection Algorithms

### 7.1 Gap-Based Detection (Current Slomix)

```
If time_since_last_activity > 60 minutes → New session
```

**Industry usage:**
- Google Analytics: 30-min default
- Most game analytics: 30-60 min depending on genre
- 60 minutes for competitive PC gaming: **well-calibrated**

### 7.2 Alternative Approaches

#### Activity-Based
```
Session boundary = explicit events (map change, server disconnect, voice leave)
```
Slomix could supplement gap-based with voice channel leave events.

#### Hybrid (Recommended Enhancement)
```
New session if ANY of:
  - 60-minute gap in round data
  - Player left voice channel AND 15+ minute gap
  - Server restarted (detected via SSH)
  - Map pool reset to starting map
```

#### ML-Based (Academic)
- Hidden Markov Models for player engagement states
- Requires significant data volume — not practical for Slomix's scale

### 7.3 Sub-Session Detection

Beyond session boundaries, detecting "phases" within a session:
- Warmup phase: First 1-2 rounds, lower performance
- Peak phase: Rounds 3-8, highest performance
- Fatigue phase: Later rounds, declining metrics

This could be an interesting analytics feature for Slomix.

---

## 8. Database Schema Patterns

### 8.1 Current Slomix Schema

68 tables, 56 columns in `player_comprehensive_stats`. This is a **normalized operational schema** optimized for write-heavy stat ingestion.

### 8.2 Star Schema for Analytics

For read-heavy analytics queries, consider a **star schema** layer:

```
Fact Table: fact_player_round_stats
  - round_id (FK)
  - player_guid (FK)
  - kills, deaths, damage_given, damage_received, ...

Dimension Tables:
  - dim_player (guid, name, first_seen, total_rounds)
  - dim_round (id, map, date, session_id, round_number)
  - dim_map (name, type, typical_duration)
  - dim_session (id, date, player_count, duration)
```

**Benefits:**
- Queries like "top fraggers on map X across all sessions" become simple joins
- Pre-aggregated summary tables for common queries
- `stats_cache.py` TTL cache handles most of this benefit already

**Recommendation**: Slomix's current schema works well for its scale. Star schema adds complexity without proportional benefit for <100 concurrent users. The 5-minute TTL cache is the right optimization at this scale.

### 8.3 Materialized Views

An intermediate optimization: PostgreSQL materialized views for common aggregations:

```sql
CREATE MATERIALIZED VIEW mv_player_career_stats AS
SELECT player_guid, MAX(player_name) as name,
       COUNT(*) as total_rounds, SUM(kills) as total_kills, ...
FROM player_comprehensive_stats
GROUP BY player_guid;

-- Refresh after each import
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_player_career_stats;
```

This is lighter than a full star schema but gives similar query benefits.

---

## 9. Automation & Monitoring Patterns

### 9.1 Voice Channel → Game Monitoring

**Slomix current**: Voice channel presence triggers SSH monitoring.

**Industry patterns:**
- Discord bots commonly use `on_voice_state_update` events
- [Discord-Game-Detect](https://github.com/bencroskery/Discord-Game-Detect) auto-detects games from voice channel activity
- Grace period after voice empties (Slomix: 45 minutes) is standard

**Best practice:**
```
Voice join detected → Start monitoring (if not already active)
Voice empty + grace period → Stop monitoring
Game activity detected (SSH) → Keep monitoring regardless of voice
```

Slomix's approach is solid. The 45-minute grace period handles cases where players briefly disconnect.

### 9.2 Health Monitoring

**Recommended health checks:**
- SSH connection alive: Ping every 5 minutes
- Database connection alive: Simple query every minute
- Bot latency: Track Discord gateway latency
- Pipeline freshness: Alert if no new rounds in X hours during active gaming time
- Disk space: Monitor stats file storage

---

## 10. Summary of Recommendations

### High Priority (Should Implement)

| # | Recommendation | Effort | Impact |
|---|---------------|--------|--------|
| 1 | **Add OpenSkill rating** for player skill tracking | Medium | High |
| 2 | **Formalize useful kills** with spawn wave math formula | Low | Medium |
| 3 | **Add "Damage Per Life"** as complement to FragPotential | Low | Medium |
| 4 | **Add bounded Damage Efficiency** (0-1 scale variant) | Low | Low |
| 5 | **Database retry logic** with exponential backoff | Low | Medium |

### Medium Priority (Nice to Have)

| # | Recommendation | Effort | Impact |
|---|---------------|--------|--------|
| 6 | **KAST-equivalent metric** adapted for ET spawn waves | Medium | Medium |
| 7 | **Materialized views** for career stat aggregations | Low | Medium |
| 8 | **Sub-session phase detection** (warmup/peak/fatigue) | Medium | Low |
| 9 | **Playstyle confidence scores** for classification strength | Low | Low |
| 10 | **Failed imports table** for dead letter queue pattern | Low | Medium |

### Low Priority (Future Exploration)

| # | Recommendation | Effort | Impact |
|---|---------------|--------|--------|
| 11 | **Round Swing-style metric** using win probability estimation | High | High |
| 12 | **ML-based playstyle clustering** (after 500+ sessions) | High | Medium |
| 13 | **Star schema analytics layer** (if query performance degrades) | High | Medium |
| 14 | **RWS-style round contribution** metric | Medium | Medium |

### Already Well-Implemented ✅

- FragPotential (DPM while alive) — better than standard ADR for ET:Legacy
- Survival Rate — more granular than DPR
- Headshot Accuracy — universal standard, correctly implemented
- Denied Playtime — genuinely novel, no equivalent found in industry
- Session Detection (60-min gap) — perfectly calibrated for competitive PC gaming
- Data pipeline (SSH + Lua webhook hybrid) — follows industry best practices
- SHA256 deduplication — solid idempotency pattern
- Cog architecture — well-organized layered structure
- TTL cache — appropriate optimization for current scale

---

## Sources

### HLTV Rating System
- [Introducing Rating 2.0 | HLTV.org](https://www.hltv.org/news/20695/introducing-rating-20)
- [Introducing Rating 2.1 | HLTV.org](https://www.hltv.org/news/40051/introducing-rating-21)
- [Introducing Rating 3.0 | HLTV.org](https://www.hltv.org/news/42485/introducing-rating-30)
- [Rating 3.0 adjustments | HLTV.org](https://www.hltv.org/news/43047/rating-30-adjustments-go-live)
- [Reverse Engineering HLTV 2.0 | flashed.gg](https://flashed.gg/posts/reverse-engineering-hltv-rating/)
- [Rating 3.0 explained | escorenews](https://escorenews.com/en/csgo/article/71475-how-hltv-rating-3-0-formula-actually-works-round-swing-and-eco-adjustment-explained)
- [HLTV Rating 2.0 Calculator (GitHub)](https://github.com/mang0cs/hltv-rating-2.0)

### Valorant & Other FPS Metrics
- [What is ACS in Valorant | tracker.gg](https://tracker.gg/valorant/articles/what-is-acs-in-valorant-and-how-does-it-work)
- [ACS Explained | esports.net](https://www.esports.net/wiki/guides/acs-explained-valorant/)
- [What is ADR in CS2 | eloboss.net](https://eloboss.net/blog/what-is-adr-in-cs2)
- [What is RWS | ESEA](https://support.esea.net/hc/en-us/articles/360008740634-What-is-RWS-)

### Leetify & FACEIT
- [Leetify Rating Explained](https://leetify.com/blog/leetify-rating-explained/)
- [Leetify Stats Glossary](https://leetify.com/blog/leetify-stats-glossary/)
- [FACEIT CS2 Elo and Skill Levels](https://support.faceit.com/hc/en-us/articles/10525200579740-FACEIT-CS2-Elo-and-skill-levels)
- [FACEIT Advanced Stats](https://support.faceit.com/hc/en-us/articles/19309126922140-FACEIT-CS2-Advanced-Stats)

### Skill Rating Algorithms
- [TrueSkill | Microsoft Research](https://www.microsoft.com/en-us/research/project/trueskill-ranking-system/)
- [OpenSkill Paper | arxiv](https://arxiv.org/abs/2401.05451)
- [OpenSkill Python | GitHub](https://github.com/vivekjoshy/openskill.py)
- [OpenSkill Python | PyPI](https://pypi.org/project/openskill/)
- [Abstracting Glicko-2 for Team Games](https://rhetoricstudios.com/downloads/AbstractingGlicko2ForTeamGames.pdf)
- [skillratings (Rust) | GitHub](https://github.com/atomflunder/skillratings)

### Player Behavior & Playstyle
- [Bayesian Learning of Play Styles | arxiv](https://arxiv.org/pdf/2112.07437)
- [Unsupervised Playstyle Metric | arxiv](https://arxiv.org/abs/2110.00950)
- [Real-time Rule-based Classification | Springer](https://link.springer.com/article/10.1007/s11257-012-9126-z)
- [Introducing Clustering for Behavioral Profiling | GameAnalytics](https://gameanalytics.com/blog/introducing-clustering-behavioral-profiling-gameanalytics)
- [Player Progression and Playstyle Analysis | Anders Drachen](https://andersdrachen.com/2013/09/17/player-progression-and-playstyle-analysis/)

### Session & Engagement Analytics
- [Session-Based Analytics in Puzzle Games](https://www.randomforestservices.com/post/session-based-analytics-understanding-player-behavior-patterns-in-puzzle-games)
- [Engagement Tracing | GameAnalytics](https://www.gameanalytics.com/blog/engagement-tracing-retention)
- [Player Engagement Review | ACM](https://dl.acm.org/doi/10.1145/3722116)

### Data Pipelines & Architecture
- [Event-Driven vs Scheduled Pipelines | Prefect](https://www.prefect.io/blog/event-driven-versus-scheduled-data-pipelines)
- [AWS Game Analytics Pipeline | GitHub](https://github.com/awslabs/game-analytics-pipeline)
- [Monitor Game Analytics Pipeline | OneUptime](https://oneuptime.com/blog/post/2026-02-06-monitor-game-analytics-pipeline-opentelemetry/view)
- [Architecting Discord Bot the Right Way | Medium](https://itsnikhil.medium.com/architecting-discord-bot-the-right-way-46e426a0b995)

### Database & Schema Design
- [Star Schema Data Warehouse Guide | MotherDuck](https://motherduck.com/learn-more/star-schema-data-warehouse-guide/)
- [How to Design a Database for Multiplayer Games | GeeksforGeeks](https://www.geeksforgeeks.org/dbms/how-to-design-a-database-for-multiplayer-online-games/)
- [PostgreSQL for Game Databases](https://jahej.com/alt/2011_08_08_from-the-mmo-trenches-using-postgresql-for-the-game-database.html)

### Overwatch & Matchmaking
- [Overwatch SR Calculation Explained | dotesports](https://dotesports.com/overwatch/news/overwatch-sr-calculation-explained-16535)
- [Overwatch Matchmaker Goals | Blizzard](https://overwatch.blizzard.com/en-us/news/23910161/)
- [Achieving Fairness in Team-Based FPS Matchmaking](https://www.researchgate.net/publication/378738777_Achieving_fairness_in_team-based_FPS_games_A_skill-based_matchmaking_solution)
- [Team Matchmaking Theoretical Foundations | AAMAS 2017](https://www.ifaamas.org/Proceedings/aamas2017/pdfs/p1073.pdf)

### ET:Legacy
- [ET:Legacy Game Manual](https://etlegacy.readthedocs.io/en/latest/manual.html)
- [ET:Legacy g_stats.c | GitHub](https://github.com/etlegacy/etlegacy/blob/master/src/game/g_stats.c)
- [ET:Legacy Spawn Timer Issue](https://github.com/etlegacy/etlegacy/issues/1414)
