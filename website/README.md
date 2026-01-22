# ET:Legacy Stats Website - Prototype Documentation

## Overview

Modern, responsive web frontend for the ET:Legacy stats tracking system. Built with FastAPI backend and Tailwind CSS + Chart.js frontend.

## Architecture

### Backend (FastAPI)

- **Port:** 8000 (configurable via `WEBSITE_PORT`)
- **Database:** Read-only PostgreSQL connection (or SQLite fallback)
- **Auth:** Discord OAuth2 for user authentication
- **Security:** CORS enabled, session middleware, parameterized queries

### Frontend (Vanilla JS + Tailwind)

- **Design:** Glass morphism UI with dark theme
- **Charts:** Chart.js for data visualization
- **Icons:** Lucide icons
- **State:** Client-side view routing with hash navigation

---

## Features Implemented

### ✅ Core Views

#### Home

- Hero search bar with player autocomplete
- Season information widget
- Last session summary with match cards
- Quick leaderboard (top 5 DPM)
- Recent matches widget

#### Leaderboards

- Sortable by DPM, Kills, K/D
- Period filters: 7d, 30d, season, all-time
- Clickable player names → profile

#### Player Profile

- Comprehensive stats (K/D, DPM, Win Rate, XP, etc.)
- ELO chart placeholder
- **Recent 10 matches** with K/D and DPM highlighting
- Clickable match cards open match details modal

#### Matches

- Grid view of recent 50 matches
- Winner/loser highlighting
- **"View Details" buttons** → Match Details Modal

#### Maps

- Map frequency statistics
- Win rate visualization per map
- Allied vs Axis breakdown

#### Weapons

- **Live weapon stats from API** (`/api/stats/weapons`)
- Weapon category grouping (SMG, Rifle, Heavy, etc.)
- Kill counts and usage rates

#### Community

- **Coming Soon placeholders** for Clips & Configs
- No broken API calls

---

### ✅ Modals & Interactions

#### Match Details Modal

- Full match breakdown by team (Allies/Axis)
- Player performance table with:
  - Kills, Deaths, K/D, Damage, DPM, Headshots, Accuracy
  - MVP highlighted with crown emoji
  - Clickable player names → profile
- Match summary cards (Duration, Total Kills, Total Damage, Avg DPM)

#### Player Comparison Modal

- Side-by-side stat comparison
- Winner highlights (🏆) for each category
- Compares: K/D, DPM, Kills, Win Rate, Games, Playtime

---

### ✅ Enhanced Widgets

#### Session MVP

- Displays top DPM performer from last session
- Animated gold badge with player initials
- Shows DPM and K/D stats
- Clickable → loads player profile

#### Search Functionality

- Hero search bar with live suggestions
- Player search in modals
- Escaped HTML to prevent XSS

---

## API Endpoints Used

| Endpoint | Purpose |
|----------|---------|
| `GET /api/status` | Health check |
| `GET /api/seasons/current` | Current season info |
| `GET /api/stats/last-session` | Latest session data |
| `GET /api/stats/session-leaderboard` | Top DPM players from session |
| `GET /api/stats/matches` | Recent matches list |
| `GET /api/stats/matches/{id}` | **NEW** - Match details with player breakdown |
| `GET /api/stats/leaderboard` | Global leaderboards (DPM/Kills/K/D) |
| `GET /api/stats/player/{name}` | Player aggregated stats |
| `GET /api/player/{name}/matches` | **NEW** - Player recent matches |
| `GET /api/stats/weapons` | **NEW** - Weapon kill statistics |
| `GET /api/stats/maps` | Distinct map list |
| `GET /api/stats/records` | Hall of Fame records |
| `GET /api/player/search` | Player name autocomplete |
| `POST /api/player/link` | Link Discord to player alias |
| `GET /api/predictions/recent` | Match predictions |
| `GET /auth/login` | Discord OAuth redirect |
| `GET /auth/callback` | OAuth callback |
| `GET /auth/me` | Current user info |

---

## Deployment

### Linux/VPS Setup

1. **Create PostgreSQL read-only user:**

   ```bash
   sudo -u postgres psql -d et_stats -f website/setup_readonly_user.sql
   ```text

2. **Configure environment:**

   ```bash
   cp website/.env.example website/.env
   nano website/.env
   # Set: POSTGRES_PASSWORD, SESSION_SECRET, DISCORD_CLIENT_ID/SECRET
   ```text

3. **Start website:**

   ```bash
   chmod +x website/start_website.sh
   ./website/start_website.sh
   ```text

4. **Or use systemd service:**

   ```bash
   sudo cp website/etlegacy-website.service /etc/systemd/system/
   sudo systemctl enable etlegacy-website
   sudo systemctl start etlegacy-website
   ```yaml

### Access

- **Website:** `http://your-server:8000`
- **API Docs:** `http://your-server:8000/docs` (FastAPI auto-generated)

---

## Security Features

✅ **SQL Injection Prevention** - All queries use parameterized statements  
✅ **XSS Protection** - `escapeHtml()` on all user input  
✅ **CORS** - Configured for specified origins  
✅ **Read-Only Database** - Website uses PostgreSQL role with SELECT-only grants  
✅ **Session Security** - Configurable secret key, signed cookies  
✅ **Environment Variables** - Secrets never hardcoded  

---

## Known Limitations / TODO

### High Priority

- [ ] **Weapon Usage Chart** on player profile (API endpoint needed: `/api/player/{name}/weapons`)
- [ ] **Dashboard View** for logged-in users
- [ ] **Mobile Menu** - Hamburger navigation for small screens

### Medium Priority

- [ ] Map-specific player stats (e.g., "How well does Player X perform on Supply?")
- [ ] Weapon mastery leaderboards (per-weapon K/D, accuracy)
- [ ] Historical performance trends (ELO chart currently placeholder)
- [ ] Pagination for leaderboards (currently hardcoded limit=50)

### Low Priority

- [ ] Community Clips/Configs implementation
- [ ] Dark/Light theme toggle
- [ ] Export stats to PDF/CSV
- [ ] Advanced filters (date range picker, map filters)

---

## File Structure

```python
website/
├── .env.example                 # Environment config template
├── setup_readonly_user.sql      # PostgreSQL read-only user setup
├── start_website.sh             # Linux startup script
├── etlegacy-website.service     # Systemd service unit
├── requirements.txt             # Python dependencies
├── index.html                   # Main HTML (749 lines)
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── dependencies.py          # DB connection pool management
│   ├── local_database_adapter.py # SQLite/Postgres adapter
│   ├── routers/
│   │   ├── api.py               # Main stats API (741 lines, 19 endpoints)
│   │   ├── auth.py              # Discord OAuth
│   │   └── predictions.py       # Match predictions
│   └── services/
│       └── website_session_data_service.py # Session aggregation
└── js/
    ├── app.js                   # Main frontend logic (1750+ lines)
    └── records.js               # Records view helper
```yaml

---

## Performance Notes

- **Database Queries:** Most endpoints complete in <100ms on VPS
- **Frontend Loading:** Initial page load ~2-3s (includes Tailwind CDN, Chart.js CDN)
- **API Response Times:**
  - Simple queries (status, season): <10ms
  - Leaderboards: 50-200ms (depends on period filter)
  - Match details: 30-100ms
  - Player stats: 50-150ms

**Optimization Opportunities:**

- Cache frequently accessed data (leaderboards, season info)
- Lazy load Chart.js only when needed
- Self-host Tailwind CSS for offline capability
- Add CDN for static assets

---

## Development Workflow

### Local Testing (Windows)

```powershell
cd website
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
# Edit .env with local settings
python -m uvicorn backend.main:app --reload --port 8000
```

### Code Quality

- **Linting:** ESLint for JavaScript (not yet configured)
- **Type Hints:** Python backend uses type hints
- **Security Scans:** Codacy MCP integrated (run after edits)

---

## Browser Compatibility

✅ **Tested:**

- Chrome/Edge 100+
- Firefox 100+
- Safari 15+

⚠️ **Known Issues:**

- Safari <15 - CSS backdrop-filter may not work (glass morphism degrades gracefully)
- IE11 - Not supported (uses modern ES6+)

---

## Credits

- **Bot/Backend:** Python, FastAPI, asyncpg
- **Frontend:** Tailwind CSS, Chart.js, Lucide Icons
- **Database:** PostgreSQL (ET:Legacy stats schema)
- **Design:** Custom glass morphism theme

---

## Support

For issues or feature requests:

1. Check existing TODOs in this document
2. Review API endpoint documentation at `/docs`
3. Check browser console for JavaScript errors
4. Verify `.env` configuration
5. Check `logs/website.log` for backend errors
