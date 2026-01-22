# SLOMIX Project Brief

## ET:Legacy Team Chemistry Analytics Platform

---

## THE VISION

We're not building a stats tracker. We're building a **team chemistry analyzer** for competitive ET:Legacy.

Raw stats lie. The player with the highest K/D might be a killstealer who's never in position when it matters. The "low performer" might be the one consistently setting up crossfires that let teammates get kills. Traditional stats can't show this — we need **spatial and temporal correlation data**.

**The Goal:** Help a group of old-school competitive ET players build balanced teams by understanding which player combinations work well together, not just who has the best individual numbers.

---

## GAME CONTEXT: ET:Legacy Competitive Stopwatch

### Format

- **Stopwatch mode**: Two teams play the same map twice, switching sides (attackers/defenders)
- **Team sizes**: Typically 3v3, 5v5, or 6v6
- **Teams**: Allies (usually attackers) vs Axis (usually defenders)
- **Objective-based**: Attackers must complete objectives (blow doors, steal gold, build bridges, etc.) within time limit
- **Winning**: Faster objective completion time wins

### Why This Matters for Analytics

- Every team plays both attack and defense → can normalize for map balance
- Can compare same players on attack vs defense (fraggers vs anchors)
- Objective completion matters more than kills
- Team coordination > individual skill

---

## CURRENT ARCHITECTURE

### The Stack

```text
┌─────────────────────────────────────────────────────────────┐
│                     SLOMIX ECOSYSTEM                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │  DISCORD    │    │   WEB       │    │  ET:LEGACY  │     │
│  │  BOT        │    │   DASHBOARD │    │  LUA MODULE │     │
│  │  (Python)   │    │  (FastAPI + │    │  (proximity │     │
│  │             │    │   Tailwind) │    │   tracker)  │     │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘     │
│         │                  │                  │             │
│         └──────────────────┼──────────────────┘             │
│                            │                                │
│                    ┌───────▼───────┐                        │
│                    │  PostgreSQL   │                        │
│                    │  DATABASE     │                        │
│                    │  (unified)    │                        │
│                    └───────────────┘                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```sql

### Component Status

| Component | Status | Description |
|-----------|--------|-------------|
| Discord Bot | ✅ Stable | Session tracking, stats commands, 1400+ messages processed |
| Web Dashboard | 🔨 Prototype | Player profiles, charts, live status, voice tracking |
| Proximity Lua | 🔨 Prototype | Player tracking, engagement detection, heatmaps |
| Database | ✅ Working | PostgreSQL with game stats, sessions, voice activity |

---

## THE PROXIMITY TRACKER (Current State)

### What It Currently Tracks

**Player Tracking (spawn to death):**

- Position (x, y, z) sampled every 500ms
- Velocity and speed
- Health
- Current weapon
- Stance (standing/crouching/prone)
- Sprint state
- First movement time after spawn
- GUID for persistent player identity

**Engagement Tracking:**

- Damage events (attacker → target)
- Crossfire detection (2+ attackers within 1 second window)
- Escape detection (survived 5 seconds + moved 300 units after taking damage)
- Kill attribution

**Heatmaps:**

- Kill locations (grid-based, per team)
- Movement density (traversal vs combat movement)

### Output Format

Single file per round containing:

- `PLAYER_TRACKS`: Full movement history for each player
- `ENGAGEMENTS`: Combat interactions with crossfire flags
- `KILL_HEATMAP`: Where kills happen
- `MOVEMENT_HEATMAP`: Where players move

---

## WHAT WE'RE ACTUALLY TRYING TO MEASURE

### 1. Crossfire Effectiveness (Team Shooting Synergy)

**Current:** Detects when 2+ players damage the same target within 1 second.

**What We Really Want:**

- Which player **pairs** consistently create crossfires together?
- How synchronized are they? (simultaneous vs sequential)
- Are they setting up crossfires intentionally (pre-positioned) or reactively?
- Success rate: Do crossfires lead to kills more often?

**Key Question:** "When Player A and Player B are on the same team, what's their crossfire success rate compared to other combinations?"

### 2. Movement Cohesion (Positional Synergy)

**Current:** We have position data every 500ms for all players.

**What We Want to Derive:**

- Do certain player pairs move in complementary patterns?
- Distance between teammates over time (tight vs spread formations)
- Role detection: Who pushes first? Who holds angles? Who flanks?
- Movement correlation: Do they rotate together or independently?

**Key Question:** "Which players naturally coordinate movement without explicit communication?"

### 3. Positional Intelligence (Game Sense)

**Current:** We have player positions but no game state context.

**What We Need to Add:**

- Current objective status (which objectives are active/completed)
- Game phase (early round, mid push, objective attempt, post-plant)
- For defenders: Are they set up in crossfire positions BEFORE attackers arrive?
- For attackers: Are they pushing toward objectives or farming kills?

**Key Question:** "Given the current game state, is this player positioned optimally for their role?"

### 4. Objective Focus (Playing to Win)

**Current:** We track kills and damage.

**What We Want:**

- Distance from active objective over time
- Who dies ON the objective vs far away?
- Engineers: Time spent near constructible/destructible objectives
- Medics: Proximity to teammates, revive patterns
- Who actually plays to win vs who pads stats?

**Key Question:** "Who's the most objective-focused player, and how does team objective-focus correlate with win rate?"

### 5. Attack vs Defense Performance

**Current:** We track team (Axis/Allies).

**What We Want:**

- Per-player performance split by role (attacker vs defender)
- Identify natural fraggers (excel on attack) vs anchors (excel on defense)
- Balance teams by ensuring mix of both types

**Key Question:** "Is this player better suited for aggressive or defensive playstyle?"

---

## DATA WE PROBABLY NEED TO ADD

### Map-Specific Objective Data

```lua
-- Example: Goldrush objectives
local objectives = {
    goldcrates = {x = 1234, y = 5678, z = 100, type = "steal"},
    bankdoor = {x = 2345, y = 6789, z = 100, type = "destroy"},
    -- etc.
}
```sql

### Game Phase Detection

- Objective status changes (listen for game events)
- Time remaining
- Which stage of multi-stage map

### Team Assignment at Engagement Time

- Who was on which team during each crossfire
- Needed to correlate player pairs with crossfire success

### Distances

- Player-to-objective distance
- Player-to-teammate distances (for cohesion analysis)

---

## ANALYSIS GOALS (What We Want to Answer)

### Team Building Questions

1. "Which 3-player combination has the highest crossfire rate?"
2. "Who should I pair with Player X for best movement synergy?"
3. "We need a strong defender — who performs best on Axis?"
4. "This player has good stats but low objective focus — where should they play?"

### Individual Insights

1. "What's my playstyle? Am I a fragger, anchor, or objective player?"
2. "Who do I synergize best with?"
3. "What's my weakness? (e.g., poor positioning on defense)"

### Team Balance

1. "Given these 10 players, what's the fairest 5v5 split?"
2. "Team A has better fraggers, Team B has better coordination — is this balanced?"

---

## TECHNICAL NOTES

### ET:Legacy Lua API

- `et.gentity_get()` — Get entity properties (position, health, team, etc.)
- `et.trap_Milliseconds()` — Current game time
- `et.trap_FS_Write()` — Write to files
- Callbacks: `et_Damage`, `et_Obituary`, `et_ClientSpawn`, `et_RunFrame`

### Coordinate System

- ET uses Quake 3 coordinate system
- Maps are mostly flat (2D distance usually sufficient)
- Grid size 512 units works well for heatmaps

### Performance Considerations

- 500ms sampling is aggressive but manageable
- File I/O happens at round end only
- Avoid expensive operations in `et_RunFrame`

---

## FILE STRUCTURE

```text

slomix/
├── bot/                    # Discord bot (Python)
│   ├── cogs/              # Command modules
│   └── services/          # Background tasks
├── website/               # Web dashboard
│   ├── backend/           # FastAPI
│   │   ├── routers/      # API endpoints
│   │   └── services/     # Business logic
│   ├── js/               # Frontend modules
│   └── migrations/       # Database schemas
├── proximity/            # Lua module for ET:Legacy
│   └── proximity_tracker.lua
└── docs/
    └── SESSION_NOTES_*.md  # Development session logs

```

---

## WORKING WITH THIS PROJECT

### My Context

- I'm a night shift worker (18:00-06:00) in Slovenia
- I communicate ideas better through discussion than formal specs
- I learn by building — explain concepts through working code
- Privacy-conscious (GrapheneOS user, Mullvad VPN, etc.)

### Session Notes

We maintain `SESSION_NOTES_YYYY-MM-DD.md` files documenting:

- What was requested
- What was implemented
- Files modified
- Testing checklist
- Next steps

### How to Help

1. Ask clarifying questions when my explanations are vague
2. Show me working code with explanations
3. Keep session notes updated
4. Think about the bigger picture (team chemistry) not just individual features

---

## CURRENT PRIORITY

Evolve the proximity tracker from "player position logger" to "team chemistry data collector" by:

1. **Enriching crossfire data** — Track which teammate pairs create crossfires, not just that a crossfire occurred
2. **Adding objective awareness** — Know where objectives are and track player distance to them
3. **Game state context** — Track what phase the round is in (defending spawn vs final push)
4. **Team pairing analysis** — Structure data so we can later ask "how do Players A+B perform together?"

The web dashboard and Discord bot can evolve later once we have richer data to display.

---

## REMEMBER

This isn't about finding the "best" player. It's about finding the best **team compositions**.

A group of individually skilled players who don't mesh will lose to a coordinated team of "average" players who move together, crossfire effectively, and play the objective.

We're trying to quantify that magic.
