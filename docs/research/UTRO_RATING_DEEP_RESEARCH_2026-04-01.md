# UTRO Rating — Deep Research Report

**Date**: 2026-04-01
**Source**: etlstats.stiba.lol (Stiba's ET:Legacy stats platform)
**Extracted from**: JavaScript bundle `/_astro/stats.BqoK8XIW.js`
**Match example**: https://etlstats.stiba.lol/matches/3b326e69-06a2-5255-aba4-258a0b32b349?map=et_brewdog
**Public documentation**: None exists — formula reverse-engineered from minified JS

---

## 1. What Is UTRO?

UTRO is a custom player performance metric displayed on etlstats.stiba.lol alongside standard stats columns (EFF, KDR, Kills, Deaths, DMG G, DMG R, HS, GIBS, SK, REV, TMP).

No public documentation, blog posts, forum discussions, or Discord messages about "UTRO rating" were found anywhere online. The acronym does not appear in ET:Legacy official docs, Splash Damage community forums, or any GitHub repositories.

**Most likely meaning**: **"Useful Time Removed from Opponent"** — the formula weights each kill by how long the victim must wait before rejoining the game (reinforcement wave timer), measuring how much "useful playing time" each frag denies the enemy team.

**Created by**: Stiba (etlstats.stiba.lol developer), using data collected by Oksii's Lua stats system.

**Observed values** (from et_brewdog match):
- sb KREDY: 1.88
- sb subAk: 1.51
- sb hAkim: 1.28
- +/- 5 > czkk_: 3.02
- +/- 5 > Baczo: 1.50
- +/- 5 > SkyLine: 1.63

---

## 2. Complete UTRO Formula (Reverse-Engineered)

### 2.1 Respawn Weight Function — 8-Tier Graduated Scale

Each kill is weighted by the victim's time until next reinforcement wave:

```javascript
function respawnWeight(victimRespawnTime) {
  if (victimRespawnTime < 2)  return 0.3;   // Victim respawns almost instantly — nearly worthless kill
  if (victimRespawnTime < 5)  return 0.4;   // Very short wait
  if (victimRespawnTime < 10) return 0.7;   // Short wait
  if (victimRespawnTime < 13) return 1.0;   // Baseline — roughly half a wave cycle
  if (victimRespawnTime < 15) return 1.2;   // Above average timing
  if (victimRespawnTime < 20) return 1.5;   // Good timing
  if (victimRespawnTime < 25) return 1.8;   // Great timing
  return 2.0;                                // 25s+ — maximum impact, victim just missed a wave
}
```

**ET:Legacy context**: Teams respawn in synchronized reinforcement waves. Default timers are Allies every 20 seconds, Axis every 30 seconds (configurable per map). A kill right after a wave fires means the victim waits the maximum duration. A kill right before a wave means they're back almost instantly.

### 2.2 Constants

```javascript
const SELFKILL_PENALTY = 0.4;   // Penalty per selfkill (applied TWICE — see bugs)
```

### 2.3 Main Formula

```javascript
function calculateUTRO(playerGuid, stats, allKillsInRound) {

  // Step 1: Total weight of ALL non-selfkill kills in the round (denominator)
  const totalWeight = allKillsInRound
    .filter(k => k.attacker !== k.target)          // Exclude selfkills
    .reduce((sum, k) => sum + respawnWeight(k.victimRespawnTime), 0);

  // Step 2: Player's kill score (weighted kills minus selfkill penalties)
  const playerScore = allKillsInRound.reduce((sum, k) => {
    // Selfkill by this player
    if (k.attacker === playerGuid && k.attacker === k.target) {
      return k.victimRespawnTime > 3 ? sum - 0.4 : sum;  // Penalty if respawn > 3s
    }
    // Not this player's kill
    if (k.attacker !== playerGuid) return sum;
    // Normal kill by this player
    return sum + respawnWeight(k.victimRespawnTime);
  }, 0);

  // Step 3: Separate selfkill penalty (BUG: duplicates Step 2 penalty)
  const selfkillPenalty = allKillsInRound.reduce((sum, k) => {
    if (k.attacker === playerGuid && k.attacker === k.target && k.victimRespawnTime > 3)
      return sum - 0.4;
    return sum;
  }, 0);

  // Step 4: Gib bonus
  const gibBonus = stats.gibs / 10;

  // Step 5: Raw score = kill weight + selfkill penalty (doubled) + gib bonus
  const rawScore = playerScore + selfkillPenalty + gibBonus;

  // Step 6: Playtime scaling factor
  const playtimeFactor = stats.playtime / 100;  // playtime in seconds

  // Final UTRO
  return (rawScore / totalWeight) * 10 * playtimeFactor;
}
```

### 2.4 Formula Breakdown (Plain English)

```
UTRO = (yourWeightedKills - selfkillPenalties + gibBonus) / allRoundWeightedKills * 10 * playtimeScale

Where:
  yourWeightedKills  = sum of respawnWeight(victimRespawnTime) for each of your kills
  selfkillPenalties  = -0.8 per selfkill (double bug)
  gibBonus           = your total gibs / 10
  allRoundWeightedKills = sum of respawnWeight() for ALL kills in the round (by everyone)
  playtimeScale      = your playtime in seconds / 100
```

---

## 3. Known Bugs & Issues

### 3.1 Double Selfkill Penalty (BUG)

Selfkills with `victimRespawnTime > 3` are penalized -0.4 **twice**:
1. Once in `playerScore` (Step 2)
2. Once in `selfkillPenalty` (Step 3)

Total penalty per selfkill: **-0.8** (likely intended: -0.4)

The `selfkillPenalty` variable was probably meant to replace the inline handling in `playerScore`, but both were left in.

### 3.2 Division by Zero

When `totalWeight` is 0 (no non-selfkill kills in the entire round), the formula divides by zero → `NaN` or `Infinity`. Unhandled edge case. Would occur in rounds with zero frags or only selfkills.

### 3.3 Possible Variable Name Swap in Oksii's Lua

In `docs/reference/oksii-game-stats-web.lua` (line 2522-2523):

```lua
victimRespawnTime = calculateReinfTime(et.gentity_get(attacker, "sess.sessionTeam"))
```

`victimRespawnTime` is calculated using the **attacker's** team, not the victim's. If UTRO consumes this literally as "how long until the victim respawns," the actual measurement is the **attacker's team's** wave timing. This may be intentional (measuring context from attacker's perspective) or a naming error.

**Note**: Slomix's own `proximity_tracker.lua` stores `victim_reinf` correctly using the victim's team.

### 3.4 Accumulative Not Rate-Based

`playtimeFactor = playtime / 100` means UTRO scales linearly with playtime. A mediocre player who plays 20 minutes scores higher than a dominant player who plays 8 minutes. Most competitive rating systems normalize to create a rate (e.g., HLTV ~1.0 average, KPR, DPM).

---

## 4. Mathematical Analysis

### 4.1 Expected Value Ranges

For a typical competitive 6v6 round (15 min, ~100 total kills):

| Player Type | Kills | Avg Weight | gibBonus | playtimeFactor | UTRO |
|---|---|---|---|---|---|
| Top fragger | 25 | 1.2 | 1.0 | 9.0 | ~23 |
| Average | 15 | 1.2 | 0.5 | 9.0 | ~13 |
| Weak player | 5 | 1.2 | 0.2 | 9.0 | ~5 |
| Late joiner (5 min, 10 kills) | 10 | 1.2 | 0.3 | 3.0 | ~3 |

Expected range: **~2–30** per round, average around 10-15.

### 4.2 What the Normalization Means

`rawScore / totalWeight` represents your **share of the round's total kill impact**. If there were 100 kills with average weight 1.2, totalWeight = 120. A player with 15 kills at avg weight 1.2 has rawScore ~18, giving ratio 18/120 = 0.15 (15% share). This is zero-sum: all players' shares add up to ~1.0 (before selfkill penalties and gib bonuses).

The `* 10 * playtimeFactor` then scales this into a more readable range.

---

## 5. Comparison with Other Rating Systems

### 5.1 vs HLTV Rating 2.0 (CS:GO/CS2)

HLTV 2.0 (reverse-engineered): `0.0073*KAST + 0.3591*KPR + -0.5329*DPR + 0.2372*Impact + 0.0032*ADR + 0.1587`

| Aspect | UTRO | HLTV 2.0 |
|---|---|---|
| Scale | Accumulative (~2-30) | Rate-based (~1.0 avg) |
| Death penalty | Only selfkills (-0.8) | Major factor (DPR) |
| Damage | Not included | ADR component |
| Timing context | Core mechanic | Added in 3.0 (Round Swing) |
| Consistency | Not measured | KAST component |
| Complexity | Single dimension | Multi-dimensional (5+) |

### 5.2 vs TrueSkill / ET:Legacy Built-in SR

ET:Legacy has a built-in Bayesian Skill Rating: `SR = mu - 3*sigma`
- Team-outcome based, converges over many games
- Measures "ability to make your team win"
- UTRO is per-round individual performance, not latent skill

### 5.3 vs Slomix ET Rating v2

See Section 6 for detailed comparison.

---

## 6. Slomix vs UTRO — Detailed Comparison

### 6.1 How Slomix Handles Respawn-Weighted Kill Scoring

Slomix has **two independent systems** that capture what UTRO does:

#### A) `spawn_timing_score` (Lua, continuous 0.0–1.0)

**File**: `proximity/lua/proximity_tracker.lua:1451-1493`

```lua
local function calculateSpawnTimingScore(kill_game_time, victim_team_num)
    local interval = victim_team_num == 1 and tracker.spawn.axis_interval
                                           or tracker.spawn.allies_interval
    if interval <= 0 then return 0, 0 end
    local cycle_elapsed = (reinf_offset + kill_game_time) % interval
    local time_to_next = interval - cycle_elapsed
    local score = time_to_next / interval    -- 0.0 = instant respawn, 1.0 = full wait
    return time_to_next, score
end
```

Applied in KIS as: `spawn_mult = 1.0 + score` → range **1.0 – 2.0**

**vs UTRO**: Slomix uses a continuous scale (infinite granularity), UTRO uses 8 discrete tiers. Slomix is more precise.

#### B) `reinf_mult` (KIS binary threshold)

**File**: `website/backend/services/storytelling_service.py:314-328`

```python
REINF_PENALTY_THRESHOLD = 0.75  # 75% of spawn interval

if victim_reinf > (spawn_interval * REINF_PENALTY_THRESHOLD):
    reinf_mult = 1.2
else:
    reinf_mult = 1.0
```

**vs UTRO**: Slomix is binary (yes/no bonus), UTRO has 8 graduated tiers. UTRO is more granular here, but Slomix's `spawn_mult` already provides continuous weighting, making `reinf_mult` a secondary boost.

### 6.2 Full Feature Comparison

| Feature | Slomix KIS (10 multipliers) | Slomix ET Rating v2 (15 metrics) | UTRO |
|---|---|---|---|
| Spawn timing weight | `spawn_mult` 1.0–2.0 (continuous) | `spawn_timing_eff` 4% weight | 8-tier 0.3–2.0 |
| Reinf timing bonus | `reinf_mult` 1.0/1.2 (binary) | (via KIS avg) | (built into main weight) |
| Death penalty | — | DPR 8% weight | None (only selfkills) |
| Damage | — | DPM **12%** weight (highest) | None |
| Revives | — | revive_rate 7% weight | None |
| Objectives | — | objective_rate 6% weight | None |
| Headshots | — | headshot_pct 3% weight | None |
| Accuracy | — | accuracy 5% weight | None |
| Kill permanence | `outcome_mult` (gib=1.3, revived=0.5) | permanence_rate 5% weight | gibs/10 bonus |
| Carrier kill | `carrier_mult` 3.0–5.0 | — | None |
| Crossfire | `cf_mult` 1.5 | crossfire_rate 5% weight | None |
| Trade kills | — | trade_rate 5% weight | None |
| Class context | `class_mult` (medic=1.5, engi=1.3) | — | None |
| Distance | `dist_mult` (sniper=1.2, melee=0.9) | — | None |
| Health context | `health_mult` 1.3 (under 30 HP) | — | None |
| Alive count | `alive_mult` 1.5–2.0 (clutch) | — | None |
| Push quality | `push_mult` 1.3 | push_aggression 4% weight | None |
| Survival | — | survival_rate 5% weight | None |
| Kill rate | — | KPR **10%** weight | Implicit (via kill count) |
| Soft cap | 5.0 + 25% compression | Percentile normalization | None (unbounded) |
| Normalization | Per-kill multiplicative | Percentile (0–100) | Share of round total * playtime |

### 6.3 Verdict

**UTRO would NOT add significant value to Slomix as a standalone metric.** Slomix's KIS already captures spawn timing (continuously, not in 8 tiers) along with 9 other contextual dimensions. ET Rating v2 provides a 15-metric holistic view.

**What UTRO does that Slomix doesn't**:
1. "Share of round total" normalization — interesting zero-sum framing, but approximated by percentile normalization
2. (Nothing else)

**What Slomix does that UTRO doesn't**: Deaths, damage, revives, objectives, accuracy, headshots, crossfire, trades, class context, carrier kills, distance, health, alive count, push quality, survival

---

## 7. Potential Adoption Path (If Desired)

If we ever want to incorporate UTRO-inspired logic, the best approach is **NOT** adding UTRO as a separate metric, but enhancing the existing KIS `reinf_mult`:

### Option A: Graduated reinf_mult (UTRO-inspired)

Replace binary 1.0/1.2 with graduated scale:

```python
def graduated_reinf_mult(victim_reinf_seconds):
    """UTRO-inspired 8-tier reinforcement multiplier."""
    if victim_reinf < 2:  return 0.85   # Kill nearly worthless timing-wise
    if victim_reinf < 5:  return 0.90
    if victim_reinf < 10: return 0.95
    if victim_reinf < 13: return 1.00   # Baseline
    if victim_reinf < 15: return 1.05
    if victim_reinf < 20: return 1.10
    if victim_reinf < 25: return 1.15
    return 1.20                          # Maximum timing impact
```

**Pro**: Finer granularity without disrupting existing KIS architecture.
**Con**: `spawn_mult` (1.0–2.0) already provides continuous weighting — this may be redundant.

### Option B: Display UTRO Alongside (Informational Only)

Calculate UTRO as a read-only display metric on the website for comparison/curiosity, without feeding it into any scoring system.

```python
def calculate_utro(player_guid, gibs, playtime_seconds, kill_events):
    """Calculate UTRO rating (Stiba's formula) for display purposes."""
    total_weight = sum(
        respawn_weight(k['victim_reinf'])
        for k in kill_events
        if k['killer_guid'] != k['victim_guid']
    )
    if total_weight == 0:
        return 0.0

    player_score = sum(
        respawn_weight(k['victim_reinf'])
        for k in kill_events
        if k['killer_guid'] == player_guid and k['killer_guid'] != k['victim_guid']
    )
    selfkill_penalty = sum(
        -0.4
        for k in kill_events
        if k['killer_guid'] == player_guid
        and k['killer_guid'] == k['victim_guid']
        and k['victim_reinf'] > 3
    )
    gib_bonus = gibs / 10.0
    raw = player_score + selfkill_penalty + gib_bonus
    playtime_factor = playtime_seconds / 100.0
    return (raw / total_weight) * 10 * playtime_factor

def respawn_weight(victim_reinf_seconds):
    if victim_reinf_seconds < 2:  return 0.3
    if victim_reinf_seconds < 5:  return 0.4
    if victim_reinf_seconds < 10: return 0.7
    if victim_reinf_seconds < 13: return 1.0
    if victim_reinf_seconds < 15: return 1.2
    if victim_reinf_seconds < 20: return 1.5
    if victim_reinf_seconds < 25: return 1.8
    return 2.0
```

**Note**: This fixes the double-selfkill bug (applies penalty only once).

### Option C: Do Nothing (Recommended)

Slomix's existing `spawn_mult` + `reinf_mult` + 8 other KIS multipliers + 15-metric ET Rating already provide superior coverage. UTRO adds no unique information.

---

## 8. Data Availability in Slomix

All fields needed for UTRO calculation are already stored:

| UTRO Field | Slomix Table | Column | Status |
|---|---|---|---|
| `victimRespawnTime` | `proximity_spawn_timing` | `victim_reinf` (seconds) | Available since migration 033 |
| `attackerGuid` | `proximity_spawn_timing` | `killer_guid` | Always available |
| `victimGuid` | `proximity_spawn_timing` | `victim_guid` | Always available |
| `gibs` | `player_comprehensive_stats` | `gibs` | Always available |
| `playtime` | `player_comprehensive_stats` | `time_played_seconds` | Always available |

**SQL query to calculate UTRO from existing data**:

```sql
WITH kill_weights AS (
    SELECT
        pst.round_id,
        pst.killer_guid,
        pst.victim_guid,
        pst.victim_reinf,
        CASE
            WHEN pst.victim_reinf < 2  THEN 0.3
            WHEN pst.victim_reinf < 5  THEN 0.4
            WHEN pst.victim_reinf < 10 THEN 0.7
            WHEN pst.victim_reinf < 13 THEN 1.0
            WHEN pst.victim_reinf < 15 THEN 1.2
            WHEN pst.victim_reinf < 20 THEN 1.5
            WHEN pst.victim_reinf < 25 THEN 1.8
            ELSE 2.0
        END AS kill_weight
    FROM proximity_spawn_timing pst
    WHERE pst.killer_guid != pst.victim_guid
),
round_totals AS (
    SELECT round_id, SUM(kill_weight) AS total_weight
    FROM kill_weights
    GROUP BY round_id
),
player_scores AS (
    SELECT
        kw.round_id,
        kw.killer_guid,
        SUM(kw.kill_weight) AS player_weight
    FROM kill_weights kw
    GROUP BY kw.round_id, kw.killer_guid
)
SELECT
    ps.killer_guid,
    ps.round_id,
    (ps.player_weight + pcs.gibs / 10.0) / NULLIF(rt.total_weight, 0) * 10
        * (pcs.time_played_seconds / 100.0) AS utro
FROM player_scores ps
JOIN round_totals rt ON rt.round_id = ps.round_id
JOIN player_comprehensive_stats pcs
    ON pcs.player_guid = ps.killer_guid
    AND pcs.round_id = ps.round_id
ORDER BY utro DESC;
```

---

## 9. Source Code Location

The UTRO formula was extracted from:
- **URL**: `https://etlstats.stiba.lol/_astro/stats.BqoK8XIW.js`
- **Function**: `Ot(e, r, t)` (minified name)
- **Weight function**: `da(e)` (minified name)
- **Penalty constant**: `ha = 0.4`
- **Column mapping**: `R.CustomRating = "utro"` (in `MatchPageWrapper.DX6sFZXv.js`)
- **Rendering**: `<span class="uppercase text-xs font-semibold text-mud-300">utro</span>`
- **Framework**: Astro v5.6.1 with React hydration islands

**Oksii's Lua data source**: `https://github.com/Oksii/legacy-configs/tree/main/luascripts/stats`
- `events.lua` — Kill event recording with `victimRespawnTime` field
- `stats.lua` — Weapon stats collection and JSON submission to API
- 15 total Lua modules — pure data collection, NO scoring/rating calculated server-side

---

## 10. Key Takeaways

1. **UTRO is a niche, single-dimension metric** focused exclusively on respawn-wave-timed kill impact
2. **No public documentation** — name likely coined by Stiba, plausibly "Useful Time Removed from Opponent"
3. **Contains bugs**: double selfkill penalty, division by zero, possible variable name swap
4. **Accumulative scaling** (grows with playtime) rather than normalized rate
5. **Slomix already has superior coverage**: KIS (10 multipliers per kill) + ET Rating (15 metrics) + continuous spawn_mult
6. **All data needed for UTRO is already in our database** (proximity_spawn_timing + player_comprehensive_stats)
7. **Recommendation**: Do not adopt as standalone metric. If desired, enhance KIS `reinf_mult` with graduated tiers.
8. **UTRO's one unique idea**: "share of round total" zero-sum normalization — worth considering as optional display metric

---

*Research conducted 2026-04-01 by reverse-engineering etlstats.stiba.lol JavaScript bundles.*
