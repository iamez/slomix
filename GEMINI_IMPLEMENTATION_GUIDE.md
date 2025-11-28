# 🤝 For Gemini: Website Implementation Guide

**From:** Claude Code (Discord Bot Expert)
**To:** Gemini AI Agent (Website Developer)
**Date:** 2025-11-28
**Purpose:** Help you implement Discord bot features on the website

---

## 👋 Introduction

Hey Gemini! Claude here. I've been working on the Discord bot side of Slomix, and I understand you're building the website. The user asked me to help you since I know the bot's data systems intimately.

I'm going to share **exactly** how the Discord bot commands work, what data they use, and how you can replicate them on the website. Think of this as a complete handoff document.

---

## 📊 Database Overview

**Database:** PostgreSQL
**Connection Info:** Available in `/bot/config.py`
**Key Tables:**
- `gaming_sessions` - Session metadata
- `player_comprehensive_stats` - All player stats per round
- `match_predictions` - Prediction system (Phase 3-5)
- `session_results` - Match outcomes (Phase 4)
- `map_performance` - Map-specific stats (Phase 4)

---

## 🎯 Feature Implementation Guide

I'll show you how to implement each Discord bot command as a website feature.

---

## 1️⃣ **!last_session Command**

### **What It Does:**
Shows stats from the most recent gaming session:
- Date of session
- Number of players
- Number of rounds played
- Maps played
- Player leaderboard (DPM, K/D, etc.)

### **How the Bot Does It:**

**File:** `/bot/cogs/last_session_cog.py`
**Service:** `/bot/services/session_data_service.py`

**Step-by-step:**

1. **Get latest session date:**
```python
# From session_data_service.py:302
query = """
    SELECT DATE(round_date) as session_date
    FROM player_comprehensive_stats
    WHERE stopwatch_time IS NOT NULL
    GROUP BY DATE(round_date)
    ORDER BY session_date DESC
    LIMIT 1
"""
result = await db.fetch_one(query)
latest_date = result[0]  # e.g., "2025-11-28"
```

2. **Get session gaming_session IDs:**
```python
# From session_data_service.py:119
query = """
    SELECT DISTINCT
        gaming_session_id,
        map_name,
        round_date,
        stopwatch_time
    FROM player_comprehensive_stats
    WHERE DATE(round_date) = $1
        AND stopwatch_time IS NOT NULL
    ORDER BY round_date
"""
sessions = await db.fetch_all(query, (latest_date,))
session_ids = [row[0] for row in sessions]  # List of gaming_session_id
```

3. **Count unique players:**
```python
# From session_data_service.py:147
query = """
    SELECT COUNT(DISTINCT player_guid)
    FROM player_comprehensive_stats
    WHERE gaming_session_id = ANY($1)
"""
result = await db.fetch_one(query, (session_ids,))
player_count = result[0]
```

4. **Get player stats (DPM leaderboard):**
```python
# From session_stats_aggregator.py:45
query = """
    WITH player_totals AS (
        SELECT
            player_name,
            SUM(kills) as total_kills,
            SUM(deaths) as total_deaths,
            SUM(damage) as total_damage,
            SUM(stopwatch_time) as total_time
        FROM player_comprehensive_stats
        WHERE gaming_session_id = ANY($1)
        GROUP BY player_name
    )
    SELECT
        player_name,
        ROUND((total_damage::numeric / NULLIF(total_time, 0) * 60), 2) as dpm,
        total_kills,
        total_deaths,
        ROUND((total_kills::numeric / NULLIF(total_deaths, 1)), 2) as kd_ratio
    FROM player_totals
    ORDER BY dpm DESC
    LIMIT $2
"""
leaderboard = await db.fetch_all(query, (session_ids, limit))
```

### **Website Implementation:**

**API Endpoint (already exists!):**
```python
# /website/backend/routers/api.py:30
@router.get("/stats/last-session")
async def get_last_session(db: DatabaseAdapter = Depends(get_db)):
    # Already implemented! Returns:
    # {
    #     "date": "2025-11-28",
    #     "player_count": 12,
    #     "rounds": 8,
    #     "maps": ["goldrush", "supply", "radar"],
    #     "map_counts": {"goldrush": 2, "supply": 4, "radar": 2}
    # }
```

**Frontend (already using it!):**
```javascript
// /website/js/app.js:79
async function loadLastSession() {
    const data = await fetchJSON(`${API_BASE}/stats/last-session`);
    document.getElementById('ls-date').textContent = data.date;
    document.getElementById('ls-players').textContent = data.player_count;
    document.getElementById('ls-rounds').textContent = data.rounds;
    document.getElementById('ls-maps').textContent = data.maps.length;
}
```

✅ **Status:** Already implemented!

---

## 2️⃣ **!session Command**

### **What It Does:**
Shows full session breakdown for a specific date:
- Session summary (date, duration, players)
- Map rotation with rounds per map
- Top 3 players by DPM
- Kill leaders
- Team compositions (if detected)

### **How the Bot Does It:**

**File:** `/bot/cogs/session_cog.py:44-164`

**Key Queries:**

1. **Get all rounds for date:**
```python
query = """
    SELECT
        gaming_session_id,
        map_name,
        round_date,
        stopwatch_time,
        COUNT(DISTINCT player_guid) as players
    FROM player_comprehensive_stats
    WHERE DATE(round_date) = $1
        AND stopwatch_time IS NOT NULL
    GROUP BY gaming_session_id, map_name, round_date, stopwatch_time
    ORDER BY round_date
"""
rounds = await db.fetch_all(query, (date,))
```

2. **Calculate session duration:**
```python
# Total stopwatch time across all rounds
total_time = sum(row[3] for row in rounds)  # stopwatch_time column
duration_minutes = int(total_time / 60)
```

3. **Get map statistics:**
```python
# Group by map_name
map_stats = {}
for row in rounds:
    map_name = row[1]
    if map_name not in map_stats:
        map_stats[map_name] = {"rounds": 0, "time": 0}
    map_stats[map_name]["rounds"] += 1
    map_stats[map_name]["time"] += row[3]
```

4. **Get kill leaders:**
```python
query = """
    SELECT
        player_name,
        SUM(kills) as total_kills
    FROM player_comprehensive_stats
    WHERE gaming_session_id = ANY($1)
    GROUP BY player_name
    ORDER BY total_kills DESC
    LIMIT 5
"""
kill_leaders = await db.fetch_all(query, (session_ids,))
```

### **Website Implementation:**

**NEW API Endpoint Needed:**
```python
# Add to /website/backend/routers/api.py

@router.get("/stats/session/{date}")
async def get_session_details(date: str, db: DatabaseAdapter = Depends(get_db)):
    """
    Get full session breakdown for a specific date.

    Args:
        date: Session date in YYYY-MM-DD format

    Returns:
        {
            "date": "2025-11-28",
            "rounds": 8,
            "duration_minutes": 145,
            "unique_players": 12,
            "maps": [
                {"name": "goldrush", "rounds": 2, "duration": 35},
                {"name": "supply", "rounds": 4, "duration": 78},
                {"name": "radar", "rounds": 2, "duration": 32}
            ],
            "top_players": [
                {"name": "BAMBAM", "dpm": 456, "kills": 89, "deaths": 23},
                {"name": "Snake", "dpm": 423, "kills": 78, "deaths": 29},
                {"name": "Frost", "dpm": 398, "kills": 71, "deaths": 31}
            ],
            "kill_leaders": [
                {"name": "BAMBAM", "kills": 89},
                {"name": "Snake", "kills": 78},
                ...
            ]
        }
    """

    # 1. Get all rounds for this date
    rounds_query = """
        SELECT
            gaming_session_id,
            map_name,
            round_date,
            stopwatch_time,
            COUNT(DISTINCT player_guid) as players
        FROM player_comprehensive_stats
        WHERE DATE(round_date) = $1
            AND stopwatch_time IS NOT NULL
        GROUP BY gaming_session_id, map_name, round_date, stopwatch_time
        ORDER BY round_date
    """
    rounds = await db.fetch_all(rounds_query, (date,))

    if not rounds:
        raise HTTPException(status_code=404, detail="No session found for this date")

    # 2. Extract session IDs
    session_ids = [row[0] for row in rounds]

    # 3. Calculate map statistics
    map_stats = {}
    total_time = 0
    for gaming_session_id, map_name, round_date, stopwatch_time, players in rounds:
        total_time += stopwatch_time
        if map_name not in map_stats:
            map_stats[map_name] = {"name": map_name, "rounds": 0, "duration": 0}
        map_stats[map_name]["rounds"] += 1
        map_stats[map_name]["duration"] += int(stopwatch_time / 60)

    # 4. Get unique player count
    players_query = """
        SELECT COUNT(DISTINCT player_guid)
        FROM player_comprehensive_stats
        WHERE gaming_session_id = ANY($1)
    """
    player_count = (await db.fetch_one(players_query, (session_ids,)))[0]

    # 5. Get top players by DPM
    dpm_query = """
        WITH player_totals AS (
            SELECT
                player_name,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                SUM(damage) as total_damage,
                SUM(stopwatch_time) as total_time
            FROM player_comprehensive_stats
            WHERE gaming_session_id = ANY($1)
            GROUP BY player_name
        )
        SELECT
            player_name,
            ROUND((total_damage::numeric / NULLIF(total_time, 0) * 60), 2) as dpm,
            total_kills,
            total_deaths
        FROM player_totals
        ORDER BY dpm DESC
        LIMIT 3
    """
    top_players = await db.fetch_all(dpm_query, (session_ids,))

    # 6. Get kill leaders
    kills_query = """
        SELECT
            player_name,
            SUM(kills) as total_kills
        FROM player_comprehensive_stats
        WHERE gaming_session_id = ANY($1)
        GROUP BY player_name
        ORDER BY total_kills DESC
        LIMIT 5
    """
    kill_leaders = await db.fetch_all(kills_query, (session_ids,))

    return {
        "date": date,
        "rounds": len(rounds),
        "duration_minutes": int(total_time / 60),
        "unique_players": player_count,
        "maps": list(map_stats.values()),
        "top_players": [
            {"name": row[0], "dpm": float(row[1]), "kills": row[2], "deaths": row[3]}
            for row in top_players
        ],
        "kill_leaders": [
            {"name": row[0], "kills": row[1]}
            for row in kill_leaders
        ]
    }
```

**Frontend Component:**
```javascript
// Add to /website/js/app.js

async function loadSessionDetails(date) {
    try {
        const data = await fetchJSON(`${API_BASE}/stats/session/${date}`);

        // Display session header
        document.getElementById('session-date').textContent = data.date;
        document.getElementById('session-duration').textContent = `${data.duration_minutes} min`;
        document.getElementById('session-players').textContent = data.unique_players;
        document.getElementById('session-rounds').textContent = data.rounds;

        // Display map rotation
        const mapList = document.getElementById('session-maps-list');
        mapList.innerHTML = '';
        data.maps.forEach(map => {
            const html = `
                <div class="flex justify-between p-3 bg-slate-800/30 rounded">
                    <span class="font-bold text-white">${map.name}</span>
                    <div class="text-sm text-slate-400">
                        ${map.rounds} rounds • ${map.duration}m
                    </div>
                </div>
            `;
            mapList.insertAdjacentHTML('beforeend', html);
        });

        // Display top players
        const topList = document.getElementById('session-top-players');
        topList.innerHTML = '';
        data.top_players.forEach((player, index) => {
            const medal = index === 0 ? '🥇' : index === 1 ? '🥈' : '🥉';
            const html = `
                <div class="flex justify-between items-center p-3 bg-slate-800/30 rounded">
                    <div class="flex items-center gap-3">
                        <span class="text-2xl">${medal}</span>
                        <span class="font-bold text-white">${player.name}</span>
                    </div>
                    <div class="flex gap-6 text-sm">
                        <div>
                            <span class="text-slate-500">DPM:</span>
                            <span class="font-mono font-bold text-brand-emerald">${player.dpm}</span>
                        </div>
                        <div>
                            <span class="text-slate-500">K/D:</span>
                            <span class="font-mono font-bold text-white">${player.kills}/${player.deaths}</span>
                        </div>
                    </div>
                </div>
            `;
            topList.insertAdjacentHTML('beforeend', html);
        });

    } catch (e) {
        console.error('Failed to load session:', e);
    }
}

// Usage: loadSessionDetails('2025-11-28');
```

⏳ **Status:** Needs implementation

---

## 3️⃣ **!leaderboard Command**

### **What It Does:**
Shows global leaderboards across different metrics:
- DPM (Damage Per Minute) - default
- Kills
- K/D Ratio
- Accuracy
- Headshots
- Revives (for medics)

Supports filtering by:
- Time period (7 days, 30 days, season, all-time)
- Minimum games played

### **How the Bot Does It:**

**File:** `/bot/cogs/leaderboard_cog.py:31-198`

**Key Query (DPM Leaderboard):**
```python
# From session_stats_aggregator.py:76
query = """
    WITH player_stats AS (
        SELECT
            player_name,
            player_guid,
            COUNT(DISTINCT gaming_session_id) as sessions_played,
            SUM(kills) as total_kills,
            SUM(deaths) as total_deaths,
            SUM(damage) as total_damage,
            SUM(stopwatch_time) as total_time,
            ROUND((SUM(damage)::numeric / NULLIF(SUM(stopwatch_time), 0) * 60), 2) as dpm,
            ROUND((SUM(kills)::numeric / NULLIF(SUM(deaths), 1)), 2) as kd_ratio
        FROM player_comprehensive_stats
        WHERE stopwatch_time IS NOT NULL
            AND DATE(round_date) >= $1  -- Time filter
        GROUP BY player_name, player_guid
        HAVING COUNT(DISTINCT gaming_session_id) >= $2  -- Min games filter
    )
    SELECT
        player_name,
        dpm,
        total_kills,
        total_deaths,
        kd_ratio,
        sessions_played
    FROM player_stats
    ORDER BY dpm DESC
    LIMIT $3
"""
leaderboard = await db.fetch_all(query, (start_date, min_games, limit))
```

**Other Stat Types:**

```python
# Kills leaderboard
ORDER BY total_kills DESC

# K/D leaderboard
ORDER BY kd_ratio DESC

# Accuracy leaderboard
query = """
    SELECT
        player_name,
        ROUND((SUM(hits)::numeric / NULLIF(SUM(shots), 1) * 100), 2) as accuracy,
        SUM(shots) as total_shots,
        SUM(hits) as total_hits
    FROM player_comprehensive_stats
    WHERE shots > 0
    GROUP BY player_name
    HAVING SUM(shots) >= 100  -- Minimum shots filter
    ORDER BY accuracy DESC
    LIMIT $1
"""

# Headshot leaderboard
query = """
    SELECT
        player_name,
        SUM(headshots) as total_headshots,
        ROUND((SUM(headshots)::numeric / NULLIF(SUM(kills), 1) * 100), 2) as hs_percentage
    FROM player_comprehensive_stats
    WHERE kills > 0
    GROUP BY player_name
    ORDER BY total_headshots DESC
    LIMIT $1
"""
```

### **Website Implementation:**

**API Endpoint (partially exists!):**

Current endpoint only shows last session. Need to expand:

```python
# Update /website/backend/routers/api.py

@router.get("/stats/leaderboard")
async def get_leaderboard(
    stat: str = "dpm",  # dpm, kills, kd, accuracy, headshots
    period: str = "30d",  # 7d, 30d, season, all
    min_games: int = 3,
    limit: int = 50,
    db: DatabaseAdapter = Depends(get_db)
):
    """
    Get global leaderboards with various filters.

    Args:
        stat: Metric to rank by (dpm, kills, kd, accuracy, headshots)
        period: Time period (7d, 30d, season, all)
        min_games: Minimum games played to qualify
        limit: Number of players to return

    Returns:
        [
            {
                "rank": 1,
                "name": "BAMBAM",
                "value": 456.2,  # Main stat value
                "games": 45,
                "kills": 1234,
                "deaths": 567,
                "kd": 2.18
            },
            ...
        ]
    """

    # Calculate start date based on period
    from datetime import datetime, timedelta
    if period == "7d":
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    elif period == "30d":
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    elif period == "season":
        # Get current season start date
        from bot.core.season_manager import SeasonManager
        sm = SeasonManager()
        start_date = sm.get_season_start_date()
    else:  # all
        start_date = "2020-01-01"  # Far enough back to include everything

    # Build query based on stat type
    if stat == "dpm":
        query = """
            WITH player_stats AS (
                SELECT
                    player_name,
                    COUNT(DISTINCT gaming_session_id) as sessions_played,
                    SUM(kills) as total_kills,
                    SUM(deaths) as total_deaths,
                    SUM(damage) as total_damage,
                    SUM(stopwatch_time) as total_time,
                    ROUND((SUM(damage)::numeric / NULLIF(SUM(stopwatch_time), 0) * 60), 2) as dpm,
                    ROUND((SUM(kills)::numeric / NULLIF(SUM(deaths), 1)), 2) as kd_ratio
                FROM player_comprehensive_stats
                WHERE stopwatch_time IS NOT NULL
                    AND DATE(round_date) >= $1
                GROUP BY player_name
                HAVING COUNT(DISTINCT gaming_session_id) >= $2
            )
            SELECT
                player_name,
                dpm as value,
                sessions_played,
                total_kills,
                total_deaths,
                kd_ratio
            FROM player_stats
            ORDER BY dpm DESC
            LIMIT $3
        """
    elif stat == "kills":
        query = """
            WITH player_stats AS (
                SELECT
                    player_name,
                    COUNT(DISTINCT gaming_session_id) as sessions_played,
                    SUM(kills) as total_kills,
                    SUM(deaths) as total_deaths,
                    ROUND((SUM(kills)::numeric / NULLIF(SUM(deaths), 1)), 2) as kd_ratio
                FROM player_comprehensive_stats
                WHERE DATE(round_date) >= $1
                GROUP BY player_name
                HAVING COUNT(DISTINCT gaming_session_id) >= $2
            )
            SELECT
                player_name,
                total_kills as value,
                sessions_played,
                total_kills,
                total_deaths,
                kd_ratio
            FROM player_stats
            ORDER BY total_kills DESC
            LIMIT $3
        """
    elif stat == "kd":
        query = """
            WITH player_stats AS (
                SELECT
                    player_name,
                    COUNT(DISTINCT gaming_session_id) as sessions_played,
                    SUM(kills) as total_kills,
                    SUM(deaths) as total_deaths,
                    ROUND((SUM(kills)::numeric / NULLIF(SUM(deaths), 1)), 2) as kd_ratio
                FROM player_comprehensive_stats
                WHERE DATE(round_date) >= $1
                GROUP BY player_name
                HAVING COUNT(DISTINCT gaming_session_id) >= $2
                    AND SUM(deaths) > 0
            )
            SELECT
                player_name,
                kd_ratio as value,
                sessions_played,
                total_kills,
                total_deaths,
                kd_ratio
            FROM player_stats
            ORDER BY kd_ratio DESC
            LIMIT $3
        """
    elif stat == "accuracy":
        query = """
            WITH player_stats AS (
                SELECT
                    player_name,
                    COUNT(DISTINCT gaming_session_id) as sessions_played,
                    SUM(kills) as total_kills,
                    SUM(deaths) as total_deaths,
                    SUM(shots) as total_shots,
                    SUM(hits) as total_hits,
                    ROUND((SUM(hits)::numeric / NULLIF(SUM(shots), 1) * 100), 2) as accuracy,
                    ROUND((SUM(kills)::numeric / NULLIF(SUM(deaths), 1)), 2) as kd_ratio
                FROM player_comprehensive_stats
                WHERE DATE(round_date) >= $1
                    AND shots > 0
                GROUP BY player_name
                HAVING COUNT(DISTINCT gaming_session_id) >= $2
                    AND SUM(shots) >= 100
            )
            SELECT
                player_name,
                accuracy as value,
                sessions_played,
                total_kills,
                total_deaths,
                kd_ratio
            FROM player_stats
            ORDER BY accuracy DESC
            LIMIT $3
        """
    else:
        raise HTTPException(status_code=400, detail=f"Invalid stat type: {stat}")

    # Execute query
    rows = await db.fetch_all(query, (start_date, min_games, limit))

    # Format results
    result = []
    for rank, row in enumerate(rows, 1):
        result.append({
            "rank": rank,
            "name": row[0],
            "value": float(row[1]) if row[1] else 0,
            "games": row[2],
            "kills": row[3],
            "deaths": row[4],
            "kd": float(row[5]) if row[5] else 0
        })

    return result
```

**Frontend Component:**
```javascript
// Add to /website/js/app.js

async function loadFullLeaderboard(stat = 'dpm', period = '30d') {
    try {
        const data = await fetchJSON(
            `${API_BASE}/stats/leaderboard?stat=${stat}&period=${period}&limit=50`
        );

        const tbody = document.getElementById('leaderboard-table-body');
        tbody.innerHTML = '';

        data.forEach(player => {
            // Medal for top 3
            let rankDisplay = player.rank;
            if (player.rank === 1) rankDisplay = '🥇';
            else if (player.rank === 2) rankDisplay = '🥈';
            else if (player.rank === 3) rankDisplay = '🥉';

            const html = `
                <tr class="border-b border-white/5 hover:bg-white/5 transition">
                    <td class="p-4 font-mono font-bold text-brand-gold">${rankDisplay}</td>
                    <td class="p-4">
                        <div class="flex items-center gap-3">
                            <div class="w-8 h-8 rounded bg-slate-800 flex items-center justify-center text-xs font-bold">
                                ${player.name.substring(0, 2).toUpperCase()}
                            </div>
                            <span class="font-bold text-white">${player.name}</span>
                        </div>
                    </td>
                    <td class="p-4 font-mono font-bold text-brand-emerald text-lg">${player.value}</td>
                    <td class="p-4 text-sm text-slate-400">${player.games}</td>
                    <td class="p-4 font-mono text-sm">${player.kills}</td>
                    <td class="p-4 font-mono text-sm">${player.deaths}</td>
                    <td class="p-4 font-mono text-sm">${player.kd}</td>
                </tr>
            `;
            tbody.insertAdjacentHTML('beforeend', html);
        });

    } catch (e) {
        console.error('Failed to load leaderboard:', e);
    }
}

// Filter controls
document.getElementById('leaderboard-stat-select').addEventListener('change', (e) => {
    const stat = e.target.value;
    const period = document.getElementById('leaderboard-period-select').value;
    loadFullLeaderboard(stat, period);
});

document.getElementById('leaderboard-period-select').addEventListener('change', (e) => {
    const period = e.target.value;
    const stat = document.getElementById('leaderboard-stat-select').value;
    loadFullLeaderboard(stat, period);
});
```

**HTML for Leaderboard Page:**
```html
<!-- Add to index.html in #view-leaderboards -->
<div id="view-leaderboards" class="view-section">
    <div class="max-w-7xl mx-auto px-6 py-12">
        <!-- Header -->
        <div class="flex justify-between items-end mb-8">
            <div>
                <h1 class="text-4xl font-black text-white">Leaderboards</h1>
                <p class="text-slate-400">Top performers across all metrics</p>
            </div>

            <!-- Filters -->
            <div class="flex gap-3">
                <select id="leaderboard-stat-select" class="bg-slate-800 text-white px-4 py-2 rounded-lg border border-white/10">
                    <option value="dpm">DPM</option>
                    <option value="kills">Kills</option>
                    <option value="kd">K/D Ratio</option>
                    <option value="accuracy">Accuracy</option>
                </select>
                <select id="leaderboard-period-select" class="bg-slate-800 text-white px-4 py-2 rounded-lg border border-white/10">
                    <option value="7d">Last 7 Days</option>
                    <option value="30d" selected>Last 30 Days</option>
                    <option value="season">This Season</option>
                    <option value="all">All Time</option>
                </select>
            </div>
        </div>

        <!-- Leaderboard Table -->
        <div class="glass-panel rounded-xl overflow-hidden">
            <table class="w-full">
                <thead class="bg-slate-900/50">
                    <tr class="text-left text-xs font-bold text-slate-500 uppercase">
                        <th class="p-4">Rank</th>
                        <th class="p-4">Player</th>
                        <th class="p-4">DPM</th>
                        <th class="p-4">Games</th>
                        <th class="p-4">Kills</th>
                        <th class="p-4">Deaths</th>
                        <th class="p-4">K/D</th>
                    </tr>
                </thead>
                <tbody id="leaderboard-table-body">
                    <!-- Populated by JS -->
                    <tr>
                        <td colspan="7" class="p-12 text-center">
                            <i data-lucide="loader" class="w-8 h-8 text-brand-blue animate-spin mx-auto mb-4"></i>
                            <p class="text-slate-500">Loading leaderboard...</p>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
</div>
```

⏳ **Status:** Needs backend expansion + frontend implementation

---

## 4️⃣ **Live Scoring / Match Updates**

### **What It Does:**
Shows live match progress when a game is being played:
- Current round number
- Current map
- Team scores (if available)
- Live player stats
- Round timer

### **How the Bot Does It:**

**File:** `/bot/services/voice_session_service.py`

The bot detects when:
1. 6+ players join voice channels (session starts)
2. Players split into 2 channels (match starts)
3. Stats files are imported (round ends)
4. Players leave (session ends)

**Key Data Points:**

```python
# From voice_session_service.py:88
class VoiceSessionService:
    def __init__(self):
        self.session_active = False
        self.session_start_time = None
        self.current_player_count = 0
        self.peak_player_count = 0
        self.last_import_time = None
```

**Session Detection:**
```python
# When 6+ players join
if player_count >= self.session_start_threshold and not self.session_active:
    self.session_active = True
    self.session_start_time = datetime.now()
    # Post to Discord: "Gaming session started! 🎮"
```

**Round Completion:**
```python
# When stats file imported (from SSH monitor)
async def on_stats_imported(self, filename):
    # Parse R1 file for round data
    # Extract: map_name, round_time, player_stats
    # Post to Discord: "Round complete! goldrush - 12:34"
```

### **Website Implementation:**

This is more complex because it requires **real-time updates**. Here's how:

**Option 1: Polling (Simple)**
```javascript
// Check every 10 seconds for new data
setInterval(async () => {
    const latest = await fetchJSON(`${API_BASE}/stats/live-session`);
    if (latest.active) {
        updateLiveSessionUI(latest);
    }
}, 10000);  // 10 seconds
```

**Option 2: WebSocket (Better)**
```python
# Backend: WebSocket endpoint
from fastapi import WebSocket

@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    await websocket.accept()

    # Send updates when new rounds complete
    while True:
        # Wait for new data
        data = await wait_for_round_complete()
        await websocket.send_json(data)
```

```javascript
// Frontend: WebSocket client
const ws = new WebSocket('ws://localhost:8000/ws/live');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    updateLiveSessionUI(data);
};
```

**API Endpoint for Live Data:**
```python
@router.get("/stats/live-session")
async def get_live_session(db: DatabaseAdapter = Depends(get_db)):
    """
    Get current live session status.

    Returns:
        {
            "active": true,
            "start_time": "2025-11-28T19:30:00",
            "duration_minutes": 45,
            "current_players": 12,
            "peak_players": 14,
            "rounds_completed": 6,
            "current_map": "goldrush",
            "last_round_time": "12:34"
        }
    """

    # Check if session is active (last activity within 30 minutes)
    query = """
        SELECT
            MAX(round_date) as last_round,
            COUNT(DISTINCT gaming_session_id) as rounds,
            COUNT(DISTINCT player_guid) as players
        FROM player_comprehensive_stats
        WHERE DATE(round_date) = CURRENT_DATE
            AND round_date >= NOW() - INTERVAL '30 minutes'
    """
    result = await db.fetch_one(query)

    if not result or not result[0]:
        return {"active": False}

    # Get latest round details
    latest_query = """
        SELECT
            map_name,
            round_date,
            stopwatch_time
        FROM player_comprehensive_stats
        WHERE DATE(round_date) = CURRENT_DATE
        ORDER BY round_date DESC
        LIMIT 1
    """
    latest = await db.fetch_one(latest_query)

    return {
        "active": True,
        "rounds_completed": result[1],
        "current_players": result[2],
        "current_map": latest[0] if latest else "Unknown",
        "last_round_time": format_stopwatch_time(latest[2]) if latest else None,
        "last_update": result[0].isoformat()
    }
```

**Frontend Component:**
```javascript
// Live session widget
async function updateLiveSession() {
    try {
        const data = await fetchJSON(`${API_BASE}/stats/live-session`);

        const widget = document.getElementById('live-session-widget');

        if (data.active) {
            widget.classList.remove('hidden');
            document.getElementById('live-players').textContent = data.current_players;
            document.getElementById('live-rounds').textContent = data.rounds_completed;
            document.getElementById('live-map').textContent = data.current_map;
        } else {
            widget.classList.add('hidden');
        }
    } catch (e) {
        console.error('Failed to update live session:', e);
    }
}

// Poll every 10 seconds
setInterval(updateLiveSession, 10000);
updateLiveSession();  // Initial load
```

```html
<!-- Live Session Widget (add to homepage) -->
<div id="live-session-widget" class="hidden glass-card p-6 rounded-xl border-l-4 border-brand-rose animate-pulse-slow">
    <div class="flex items-center gap-3 mb-4">
        <div class="w-3 h-3 rounded-full bg-brand-rose animate-pulse"></div>
        <span class="text-xs font-bold text-brand-rose uppercase">LIVE NOW</span>
    </div>

    <div class="text-2xl font-black text-white mb-2">
        <span id="live-map">goldrush</span>
    </div>

    <div class="flex gap-6 text-sm">
        <div>
            <span class="text-slate-500">Players:</span>
            <span id="live-players" class="font-mono font-bold text-white ml-2">12</span>
        </div>
        <div>
            <span class="text-slate-500">Rounds:</span>
            <span id="live-rounds" class="font-mono font-bold text-white ml-2">6</span>
        </div>
    </div>

    <button onclick="navigateTo('matches')" class="mt-4 w-full px-4 py-2 bg-brand-rose text-white text-sm font-bold rounded-lg hover:bg-rose-600 transition">
        Watch Live
    </button>
</div>
```

⏳ **Status:** Needs implementation (consider WebSocket for real-time)

---

## 🎯 Priority Implementation Order

Based on user value and complexity:

### **Phase 1: Core Stats (1-2 days)**
1. ✅ Fix player search SQL bugs (you found them)
2. ✅ Expand `/stats/leaderboard` endpoint (backend)
3. ✅ Build leaderboard table UI (frontend)
4. ✅ Remove "Coming Soon" placeholder

### **Phase 2: Session Details (1 day)**
1. ⏳ Add `/stats/session/{date}` endpoint
2. ⏳ Create session detail page
3. ⏳ Add navigation from match cards to session

### **Phase 3: Live Updates (2-3 days)**
1. ⏳ Add `/stats/live-session` endpoint
2. ⏳ Build live session widget
3. ⏳ Add polling (10s intervals)
4. ⏳ Consider WebSocket upgrade

### **Phase 4: Player Profiles (3-4 days)**
1. ⏳ Add `/stats/player/{name}` endpoint
2. ⏳ Create player profile page
3. ⏳ Add charts (performance over time)
4. ⏳ Link from search results

---

## 📦 Database Schema Quick Reference

### **player_comprehensive_stats** (Main Stats Table)
```sql
Columns:
- id (primary key)
- gaming_session_id (groups rounds)
- round_date (timestamp)
- map_name (text)
- player_guid (unique ID)
- player_name (display name)
- team (1=Axis, 2=Allies)
- kills, deaths, damage, headshots, hits, shots
- stopwatch_time (round duration in seconds)
- xp_total, xp_battle, xp_engineer, xp_medic, etc.
```

**Key Indexes:**
- round_date (for date filtering)
- gaming_session_id (for session queries)
- player_guid (for player lookups)
- player_name (for name search)

### **gaming_sessions** (Session Metadata)
```sql
Columns:
- id (primary key)
- session_date (YYYY-MM-DD)
- map_name (text)
- total_rounds (int)
- unique_players (int)
- duration_minutes (int)
```

### **match_predictions** (Prediction System)
```sql
Columns:
- id (primary key)
- prediction_time (timestamp)
- session_date (text)
- team_a_guids, team_b_guids (JSON arrays)
- team_a_win_probability, team_b_win_probability (float)
- confidence (text: high/medium/low)
- actual_winner (int: 1=A, 2=B, 0=draw)
- prediction_correct (boolean)
- discord_message_id, discord_channel_id
```

---

## 🔧 Useful Helper Functions

### **Format Stopwatch Time**
```python
def format_stopwatch_time(seconds: int) -> str:
    """Convert seconds to MM:SS format."""
    minutes = int(seconds / 60)
    secs = int(seconds % 60)
    return f"{minutes}:{secs:02d}"
```

### **Calculate DPM**
```python
def calculate_dpm(damage: int, time: int) -> float:
    """Calculate damage per minute."""
    if time == 0:
        return 0.0
    return round((damage / time) * 60, 2)
```

### **Get Season Start Date**
```python
from bot.core.season_manager import SeasonManager

sm = SeasonManager()
season_start = sm.get_season_start_date()  # Returns YYYY-MM-DD
```

---

## 🐛 Common Pitfalls

### **1. SQL Parameter Placeholders**
**WRONG (SQLite style):**
```python
query = "SELECT * FROM table WHERE id = ?"
```

**RIGHT (PostgreSQL style):**
```python
query = "SELECT * FROM table WHERE id = $1"
```

**You already hit this bug!** Make sure all queries use `$1, $2, $3` format.

### **2. NULL Handling in Division**
```python
# WRONG - will crash if denominator is 0
SELECT kills / deaths as kd

# RIGHT - use NULLIF
SELECT kills::numeric / NULLIF(deaths, 1) as kd
```

### **3. Date Filtering**
```python
# WRONG - might miss time component
WHERE round_date = '2025-11-28'

# RIGHT - use DATE()
WHERE DATE(round_date) = '2025-11-28'
```

### **4. JSON Fields in PostgreSQL**
```python
# Storing JSON
import json
data = json.dumps(['guid1', 'guid2', 'guid3'])
query = "INSERT INTO table (guids) VALUES ($1)"
await db.execute(query, (data,))

# Reading JSON
result = await db.fetch_one("SELECT guids FROM table WHERE id = $1", (id,))
guids = json.loads(result[0])
```

---

## 💬 Communication Protocol

**When you need help:**
- Check this guide first
- Check `/bot/cogs/` for Discord command examples
- Check `/bot/services/` for data service examples
- Ask the user to get Claude (me) to help

**When you make changes:**
- Test queries in PostgreSQL first
- Use `console.log()` liberally on frontend
- Check browser Network tab for API errors
- Test with real data (not mock data)

---

## 🎯 Success Criteria

You'll know you've succeeded when:

✅ Users can:
1. View full leaderboards (DPM, kills, K/D, accuracy)
2. Filter by time period (7d, 30d, season, all)
3. Click on session date to see full breakdown
4. See live session status on homepage
5. Search for players and view profiles

✅ All data matches Discord bot exactly
✅ No SQL errors in console
✅ Mobile responsive
✅ Loading states look good

---

## 🤝 Final Notes

Gemini, you're doing great work! The website looks absolutely stunning.

I've given you everything I know about how the Discord bot handles stats. The data is all there in PostgreSQL - you just need to query it and display it beautifully (which you're already amazing at).

**Key takeaway:** The Discord bot and website are **two views of the same data**. The bot shows it in Discord embeds, you show it in beautiful web UI. Same queries, different presentation.

If you get stuck, just ask the user to bring me back in. I'm happy to help debug queries or explain how specific features work.

**You've got this! Let's make Slomix.gg the best ET:Legacy platform ever built.** 🚀

---

**From:** Claude Code
**To:** Gemini
**Good luck!** 💪

P.S. Don't forget to fix those SQL placeholder bugs in the search endpoints! 😉
