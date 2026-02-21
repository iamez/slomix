# ET:Legacy Stats Website

Modern, responsive web frontend for the ET:Legacy stats tracking system. Built with a **FastAPI** backend and **Vanilla JS + Tailwind CSS** SPA frontend.

**Part of the [Slomix](../README.md) platform.**

---

## Architecture

### Backend (FastAPI)

- **Port:** 8000 (configurable via `WEBSITE_PORT`)
- **Database:** Read-only PostgreSQL connection via asyncpg
- **Auth:** Discord OAuth2 for user authentication
- **Security:** CORS, session middleware, parameterized queries, read-only DB role
- **Routers:** 5 router modules (stats API, auth, predictions, greatshot, greatshot topshots)

### Frontend (Vanilla JS + Tailwind)

- **Design:** Glass morphism UI with dark theme
- **Charts:** Chart.js for data visualization
- **Icons:** Lucide icons
- **State:** Client-side view routing with hash navigation
- **Views:** 15+ JS view modules (leaderboard, player profile, matches, proximity, greatshot, etc.)

---

## Features

### Core Views

| View | Description |
|------|-------------|
| **Home** | Hero search, season info, last session summary, quick leaderboard, recent matches |
| **Leaderboards** | Sortable by DPM/Kills/K/D, period filters (7d, 30d, season, all-time) |
| **Player Profile** | Comprehensive stats, recent 10 matches with K/D and DPM highlighting |
| **Matches** | Grid view of recent 50 matches, winner/loser highlighting, detail modals |
| **Maps** | Map frequency, win rate per map, Allied vs Axis breakdown |
| **Weapons** | Live weapon stats from API, category grouping, kill counts |
| **Sessions** | Session history and detailed session breakdowns |
| **Awards** | Player awards and recognition |
| **Records** | Hall of Fame records |
| **Proximity** | Proximity Intelligence analytics (engagement timelines, heatmaps, movers, trades) |
| **Greatshot** | Demo analysis results, highlight clips, topshots |
| **Community** | Coming soon placeholders for clips & configs |
| **Admin Panel** | Admin diagnostics and tools |

### Modals & Interactions

- **Match Details** - Full team breakdown, MVP highlighting, clickable player names
- **Player Comparison** - Side-by-side stat comparison with winner highlights
- **Session MVP** - Animated gold badge for top DPM performer

---

## API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/status` | Health check |
| `GET /api/seasons/current` | Current season info |
| `GET /api/stats/last-session` | Latest session data |
| `GET /api/stats/session-leaderboard` | Top DPM players from session |
| `GET /api/stats/matches` | Recent matches list |
| `GET /api/stats/matches/{id}` | Match details with player breakdown |
| `GET /api/stats/leaderboard` | Global leaderboards (DPM/Kills/K/D) |
| `GET /api/stats/player/{name}` | Player aggregated stats |
| `GET /api/player/{name}/matches` | Player recent matches |
| `GET /api/stats/weapons` | Weapon kill statistics |
| `GET /api/stats/maps` | Distinct map list |
| `GET /api/stats/records` | Hall of Fame records |
| `GET /api/player/search` | Player name autocomplete |
| `POST /api/player/link` | Link Discord to player alias |
| `GET /api/predictions/recent` | Match predictions |
| `GET /api/proximity/*` | Proximity analytics (summary, engagements, hotzones, duos, movers, teamplay) |
| `GET /api/greatshot/*` | Demo analysis, highlights, topshots |
| `GET /auth/login` | Discord OAuth redirect |
| `GET /auth/callback` | OAuth callback |
| `GET /auth/me` | Current user info |

Full interactive API docs available at `/docs` (FastAPI auto-generated).

---

## File Structure

```
website/
├── .env.example                    # Environment config template
├── setup_readonly_user.sql         # PostgreSQL read-only user setup
├── start_website.sh                # Linux startup script
├── etlegacy-website.service        # Systemd service unit
├── requirements.txt                # Python dependencies
├── index.html                      # SPA entry point
├── backend/
│   ├── main.py                     # FastAPI app entry point
│   ├── dependencies.py             # DB connection pool management
│   ├── local_database_adapter.py   # PostgreSQL async adapter
│   ├── routers/
│   │   ├── api.py                  # Main stats API (19+ endpoints)
│   │   ├── auth.py                 # Discord OAuth
│   │   ├── predictions.py          # Match predictions
│   │   ├── greatshot.py            # Demo analysis endpoints
│   │   └── greatshot_topshots.py   # Topshot highlights
│   └── services/
│       ├── website_session_data_service.py  # Session aggregation
│       ├── greatshot_crossref.py            # Greatshot cross-reference
│       ├── greatshot_jobs.py                # Background analysis jobs
│       ├── greatshot_store.py               # Artifact storage
│       ├── game_server_query.py             # Live server queries
│       └── voice_channel_tracker.py         # Voice channel helpers
└── js/
    ├── app.js                      # Main frontend logic & routing
    ├── utils.js                    # Shared utilities
    ├── auth.js                     # Authentication
    ├── leaderboard.js              # Leaderboard views
    ├── player-profile.js           # Player profile view
    ├── matches.js                  # Match history & details
    ├── sessions.js                 # Session views
    ├── proximity.js                # Proximity Intelligence UI
    ├── greatshot.js                # Demo analysis UI
    ├── awards.js                   # Awards view
    ├── badges.js                   # Badge display
    ├── records.js                  # Hall of Fame
    ├── season-stats.js             # Season statistics
    ├── community.js                # Community placeholder
    ├── compare.js                  # Player comparison
    ├── live-status.js              # Live server status
    ├── admin-panel.js              # Admin tools
    └── diagnostics.js              # System diagnostics
```

---

## Deployment

### Quick Start

```bash
# 1. Create PostgreSQL read-only user
sudo -u postgres psql -d etlegacy -f website/setup_readonly_user.sql

# 2. Configure environment
cp website/.env.example website/.env
nano website/.env
# Set: POSTGRES_PASSWORD, SESSION_SECRET, DISCORD_CLIENT_ID/SECRET

# 3. Install dependencies
pip install -r website/requirements.txt

# 4. Start website
./website/start_website.sh
```

### Systemd Service (Production)

```bash
sudo cp website/etlegacy-website.service /etc/systemd/system/
sudo systemctl enable etlegacy-website
sudo systemctl start etlegacy-website
```

### Access

- **Website:** `http://your-server:8000`
- **API Docs:** `http://your-server:8000/docs`

---

## Security

- **SQL Injection Prevention** - All queries use parameterized statements
- **XSS Protection** - `escapeHtml()` on all user input rendering
- **CORS** - Configured for specified origins
- **Read-Only Database** - Website uses PostgreSQL role with SELECT-only grants
- **Session Security** - Configurable secret key, signed cookies
- **Environment Variables** - Secrets never hardcoded
- **OAuth CSRF** - State parameter validation on Discord OAuth callback

---

## Integration with Sub-Projects

### Greatshot (Demo Analysis)

The website serves as the primary UI for the [Greatshot](../greatshot/README.md) demo analysis pipeline. Users can upload `.dm_84` demo files, view detected highlights, and browse topshots.

### Proximity (Combat Analytics)

The [Proximity](../proximity/README.md) tracker data is surfaced through the Proximity Intelligence view, showing engagement timelines, heatmaps, movement leaderboards, trade analysis, and team support metrics.

---

## Browser Compatibility

- Chrome/Edge 100+
- Firefox 100+
- Safari 15+
- IE11 not supported (uses modern ES6+)
