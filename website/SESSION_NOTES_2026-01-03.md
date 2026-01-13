# Session Notes - January 3-4, 2026

## Game Server Status & Activity Monitoring

### Overview
Fixed the game server status widget (broken after ES6 refactoring) and added a new server activity monitoring feature with historical graphs showing player activity over time.

---

## Issues Fixed

### 1. Website Not Loading (Browser Cache Issue)

**Symptom:** After the ES6 refactoring (Jan 2), the website appeared completely broken - nothing clickable, no data loading.

**Root Cause:** Browser aggressively cached old versions of ES6 modules. The cached `records.js` didn't have the `loadRecordsView` export.

**Error:**
```
Uncaught SyntaxError: The requested module './records.js' doesn't provide an export named: 'loadRecordsView'
```

**Fix:** Hard refresh (Ctrl+Shift+R) to clear browser cache.

**Lesson Learned:** When changing ES6 module exports, users may need to hard-refresh their browsers.

---

### 2. Game Server Status Not Working

**Symptom:** Server status widget always showed "Loading..." or stale data from December 25.

**Previous Architecture (broken):**
```
Discord Bot → RCON → Database (live_status table) → Website reads
```

**Problems with old approach:**
- Required RCON password configuration
- Bot had to be running and connected
- Data could be stale if bot crashed
- Indirect dependency between website and bot

**New Architecture (implemented):**
```
Website Backend → UDP Query (port 27960) → Game Server → Real-time response
```

**Benefits:**
- No password required (uses public getstatus query)
- Direct real-time data
- No dependencies on Discord bot
- Works even if bot is offline

---

## New Feature: Server Activity Monitoring

### Feature Overview
Track and display historical server activity with an expandable status card showing:
- Player count over time (Chart.js line graph)
- Time range filtering (24h, 3d, 7d, 30d)
- Summary stats (peak players, average players, uptime percentage)

### User Preferences
- **Poll interval:** Every 10 minutes (144 records/day)
- **UI approach:** Expandable status card (click to reveal chart)
- **Default view:** 30 days
- **Data retention:** Store indefinitely (30 days = ~8,640 records = ~500KB)

---

## Implementation Details

### New Files Created

#### `/website/backend/services/game_server_query.py`
UDP query service for ET:Legacy/Quake3 servers using the standard getstatus protocol.

```python
@dataclass
class Player:
    name: str
    score: int
    ping: int

@dataclass
class ServerStatus:
    online: bool
    map_name: Optional[str] = None
    hostname: Optional[str] = None  # Raw with color codes
    clean_hostname: Optional[str] = None  # Without color codes
    player_count: int = 0
    max_players: int = 0
    players: List[Player] = field(default_factory=list)
    ping_ms: Optional[int] = None
    error: Optional[str] = None

def query_game_server(host: str, port: int = 27960, timeout: float = 3.0) -> ServerStatus:
    """Query using UDP Quake3 protocol: \xff\xff\xff\xffgetstatus\n"""
```

**Protocol Details:**
- Send: `\xff\xff\xff\xffgetstatus\n`
- Receive: `\xff\xff\xff\xffstatusResponse\n\\key\\value\\...\n<score> <ping> "<name>"\n...`
- Color codes: `^0-^9` stripped from hostname for clean display

---

### Database Schema

New table for historical data:
```sql
CREATE TABLE server_status_history (
    id SERIAL PRIMARY KEY,
    recorded_at TIMESTAMPTZ DEFAULT NOW(),
    player_count INT NOT NULL DEFAULT 0,
    max_players INT NOT NULL DEFAULT 16,
    map_name VARCHAR(64),
    hostname VARCHAR(128),
    players JSONB DEFAULT '[]',
    ping_ms INT,
    online BOOLEAN DEFAULT true
);

CREATE INDEX idx_server_status_history_recorded_at
    ON server_status_history(recorded_at DESC);
```

---

### Backend Changes

#### `/website/backend/main.py`
Added background task for periodic recording:

```python
STATUS_RECORD_INTERVAL = 600  # 10 minutes

async def record_server_status():
    """Background task: Record server status every 10 minutes"""
    while True:
        try:
            await asyncio.sleep(STATUS_RECORD_INTERVAL)
            status = query_game_server(GAME_SERVER_HOST, GAME_SERVER_PORT)
            db = get_db_pool()
            await db.execute("""
                INSERT INTO server_status_history
                (player_count, max_players, map_name, hostname, players, ping_ms, online)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """, (...))
        except asyncio.CancelledError:
            break  # Graceful shutdown
        except Exception as e:
            logger.error(f"Server status recording error: {e}")
            # Continue loop even on error

@app.on_event("startup")
async def startup_event():
    await init_db_pool()
    _status_recorder_task = asyncio.create_task(record_server_status())
```

#### `/website/backend/routers/api.py`
Updated `/api/live-status` and added new `/api/server-activity/history`:

```python
@router.get("/live-status")
async def get_live_status(db: DatabaseAdapter = Depends(get_db)):
    # Voice channel: still from database (bot updates this)
    # Game server: now using direct UDP query
    server_status = query_game_server(GAME_SERVER_HOST, GAME_SERVER_PORT)
    return {
        "game_server": {
            "online": server_status.online,
            "hostname": server_status.clean_hostname,
            "map": server_status.map_name,
            "player_count": server_status.player_count,
            "max_players": server_status.max_players,
            "players": [{"name": p.name, ...} for p in server_status.players],
            "ping_ms": server_status.ping_ms,
            "error": server_status.error
        },
        "voice_channel": {...}
    }

@router.get("/server-activity/history")
async def get_server_activity_history(hours: int = 72, db: DatabaseAdapter = Depends(get_db)):
    # Returns data_points + summary (peak, avg, uptime)
```

---

### Frontend Changes

#### `/website/js/live-status.js`
Added expandable card functionality and Chart.js activity chart:

```javascript
let serverActivityChart = null;
let serverExpanded = false;
let currentTimeRange = 720; // Default 30 days

export function toggleServerDetails() {
    serverExpanded = !serverExpanded;
    if (serverExpanded) {
        expandedContent.classList.remove('hidden');
        loadServerActivity(currentTimeRange);
    } else {
        expandedContent.classList.add('hidden');
    }
}

export async function loadServerActivity(hours = 720) {
    const data = await fetchJSON(`${API_BASE}/server-activity/history?hours=${hours}`);

    // Update summary stats
    document.getElementById('stat-peak-players').textContent = data.summary.peak_players;
    document.getElementById('stat-avg-players').textContent = data.summary.avg_players;
    document.getElementById('stat-uptime').textContent = `${data.summary.uptime_percent}%`;

    // Render Chart.js line chart with gradient fill
    serverActivityChart = new Chart(ctx, {
        type: 'line',
        data: { labels, datasets: [...] },
        options: { responsive: true, ... }
    });
}

// Expose to window for onclick handlers
window.toggleServerDetails = toggleServerDetails;
window.loadServerActivity = loadServerActivity;
```

#### `/website/index.html`
Restructured game server status card to be expandable:

```html
<div id="live-server-status" class="glass-card rounded-xl border overflow-hidden">
    <!-- Collapsed view (always visible) -->
    <div class="p-4 flex items-center gap-4 cursor-pointer" onclick="toggleServerDetails()">
        <div class="server-icon">...</div>
        <div class="flex-1">
            <span id="server-status-badge">ONLINE</span>
            <div id="server-status-details">hostname · map · players</div>
        </div>
        <i id="server-expand-icon" class="chevron-down transition-transform"></i>
    </div>

    <!-- Expanded view (hidden by default) -->
    <div id="server-expanded-content" class="hidden border-t p-4">
        <div class="flex justify-between">
            <span>Server Activity</span>
            <div class="time-range-buttons">
                <button onclick="loadServerActivity(24)">24h</button>
                <button onclick="loadServerActivity(72)">3d</button>
                <button onclick="loadServerActivity(168)">7d</button>
                <button onclick="loadServerActivity(720)" class="active">30d</button>
            </div>
        </div>
        <canvas id="server-activity-chart" height="128"></canvas>
        <div id="server-stats-summary">
            <span id="stat-peak-players">Peak</span>
            <span id="stat-avg-players">Avg</span>
            <span id="stat-uptime">Uptime</span>
        </div>
    </div>
</div>
```

---

### Configuration Changes

#### `/website/.env`
Fixed database connection (was using wrong user and host):

```env
# Before (caused permission errors):
POSTGRES_HOST=localhost
POSTGRES_USER=website_readonly

# After:
POSTGRES_HOST=192.168.64.116
POSTGRES_USER=etlegacy_user
POSTGRES_PASSWORD=etlegacy_secure_2025
```

---

## Error Resolutions

### Error: Permission Denied for Table
```
InsufficientPrivilegeError: permission denied for table server_status_history
```
**Cause:** Website `.env` was using `website_readonly` user
**Fix:** Changed to `etlegacy_user` with write permissions

### Error: Database Connection Failed
```
Connection to localhost:5432 refused
```
**Cause:** Website `.env` had `POSTGRES_HOST=localhost` but PostgreSQL is on `192.168.64.116`
**Fix:** Updated host in `.env`

### Error: Stale Connection Pool Permissions
After granting permissions, still got permission errors.
**Cause:** asyncpg connection pool cached old permissions
**Fix:** Touch `main.py` to trigger uvicorn reload with fresh connection

---

## UDP Query Protocol Reference

The Quake3/ET:Legacy server query protocol:

```
Request:  \xff\xff\xff\xffgetstatus\n
Response: \xff\xff\xff\xffstatusResponse\n
          \key1\value1\key2\value2\...\n
          <score> <ping> "<playername>"\n
          ...
```

Common server info keys:
- `sv_hostname` - Server name (may contain ^color codes)
- `mapname` - Current map
- `sv_maxclients` - Max player slots
- `g_gametype` - Game mode (2=objective, 5=stopwatch, etc.)

Color code stripping regex:
```python
re.sub(r'\^[0-9]', '', hostname)  # Remove ^0 through ^9
```

---

## Files Modified Summary

| File | Changes |
|------|---------|
| `backend/services/game_server_query.py` | **NEW** - UDP query service |
| `backend/main.py` | Added background status recorder task |
| `backend/routers/api.py` | Updated `/live-status`, added `/server-activity/history` |
| `backend/dependencies.py` | Added `get_db_pool()` for background task access |
| `js/live-status.js` | Added expandable card, Chart.js chart, time range buttons |
| `index.html` | Restructured server status card to be expandable |
| `.env` | Fixed database host and user |

---

## Testing Verification

- [x] Server status shows real-time data (hostname, map, players, ping)
- [x] Status updates correctly for online/offline states
- [x] Background task logs startup message
- [x] Backend reload triggers task restart
- [x] Click on server card expands to show chart
- [x] Time range buttons filter chart data
- [x] Summary stats (peak, avg, uptime) display correctly
- [x] Chart renders with gradient fill

---

## Next Steps (Future Sessions)

1. **Voice Channel Status** - Consider similar expandable chart for Discord voice activity
2. **Data Retention Policy** - Add cleanup job to archive data older than 90 days
3. **Alerts** - Notify when server goes offline for extended period
