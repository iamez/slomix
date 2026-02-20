# Website - CLAUDE.md

> **Status**: Production-Ready | **Version**: 1.0.0
> **Last Updated**: 2026-02-19
> **Move to**: `website/CLAUDE.md` after permissions restart

## Overview

The **Slomix Website** is a modern, responsive web frontend for the ET:Legacy stats tracking system. It provides real-time player statistics, leaderboards, match histories, live server status, and a date-based availability planner.

**Stack**: FastAPI (Python) + Vanilla JavaScript + Tailwind CSS + Chart.js
**Database**: PostgreSQL (read-only user, shared with bot)
**Auth**: Discord OAuth2
**Port**: 8000 | **Screen Session**: `website`

---

## Architecture

```
Browser (User)
    ↓ HTTP requests
FastAPI Backend (port 8000)
    ↓ Async queries
PostgreSQL (shared with bot)
    ↑ Bot writes stats
Discord Bot
```

**Key Pattern**: Website is mostly read-only for stats surfaces, with authenticated write paths for account linking and availability.

## Availability Update (2026-02-19)

`/api/availability` now uses date-based entries as source of truth.

Primary endpoints:
- `GET /api/availability?from=YYYY-MM-DD&to=YYYY-MM-DD`
- `POST /api/availability`
- `GET /api/availability/me`

Settings/subscription endpoints:
- `GET/POST /api/availability/settings`
- `GET/POST /api/availability/subscriptions`
- `POST /api/availability/link-token`
- `POST /api/availability/link-confirm`

Promotion endpoints:
- `GET/POST /api/availability/promotion-preferences`
- `GET /api/availability/promotions/preview`
- `POST /api/availability/promotions/campaigns`
- `GET /api/availability/promotions/campaign`

Default promotion schedule:
- `20:45 CET` reminder
- `21:00 CET` start

Gating:
- Anonymous users can view aggregates.
- Only authenticated + linked Discord users can submit or subscribe.
- Promote action also requires promoter/admin permission.

---

## Directory Structure

```
website/
├── index.html                    # SPA entry point (749 lines)
├── js/
│   ├── app.js                    # Navigation, view management
│   ├── utils.js                  # XSS prevention, fetch helpers
│   ├── auth.js                   # Discord OAuth, player linking
│   ├── player-profile.js         # Player stats + charts
│   ├── leaderboard.js            # Rankings
│   ├── matches.js                # Match browser, maps, weapons
│   ├── sessions.js               # Gaming session browser
│   ├── records.js                # Hall of Fame
│   ├── live-status.js            # Server status polling
│   └── ...
├── backend/
│   ├── main.py                   # FastAPI app entry
│   ├── dependencies.py           # DB pool injection
│   ├── routers/
│   │   ├── api.py                # Stats API (19 endpoints, 2,444 lines)
│   │   ├── auth.py               # Discord OAuth
│   │   └── predictions.py        # Match predictions
│   └── services/
│       ├── game_server_query.py  # UDP Quake3 server query
│       └── ...
├── .env.example                  # Config template
├── requirements.txt              # Python deps
└── etlegacy-website.service      # Systemd service
```

---

## API Endpoints (Core + Availability)

### Status
- `GET /api/status` - Health check
- `GET /api/live-status` - Game server + voice channel status

### Sessions
- `GET /api/stats/last-session` - Latest gaming session
- `GET /api/sessions` - All sessions (paginated)
- `GET /api/sessions/{date}` - Session details

### Players
- `GET /api/stats/player/{name}` - Lifetime stats
- `GET /api/stats/player/{name}/form` - Session form chart (15 sessions)
- `GET /api/stats/player/{name}/rounds` - Round chart (30 rounds)
- `GET /api/player/{name}/matches` - Recent 10 matches
- `GET /api/player/search?q=` - Autocomplete

### Leaderboards
- `GET /api/stats/leaderboard?stat=dpm&period=30d` - Top players

### Matches
- `GET /api/stats/matches?limit=50` - Recent matches
- `GET /api/stats/matches/{match_id}` - Match details with teams

### Statistics
- `GET /api/stats/maps` - Map list
- `GET /api/stats/weapons` - Weapon stats
- `GET /api/stats/records` - Hall of Fame
- `GET /api/stats/overview` - Global stats

### Auth
- `GET /auth/login` - Discord OAuth start
- `GET /auth/callback` - OAuth callback
- `GET /auth/me` - Current user
- `GET /auth/link/start` - Redirect entry point for UI CTA
- `GET /auth/link/status` - Discord + player link status
- `GET /auth/players/suggestions` - Suggested player matches
- `POST /auth/link` - Link Discord user to player
- `DELETE /auth/link` - Unlink player mapping
- `POST /auth/discord/unlink` - Unlink Discord account

### Availability (date-based)
- `GET /api/availability?from=...&to=...`
- `POST /api/availability`
- `GET /api/availability/me`
- `GET/POST /api/availability/settings`
- `GET/POST /api/availability/subscriptions`
- `GET/POST /api/availability/promotion-preferences`
- `GET /api/availability/promotions/preview`
- `POST /api/availability/promotions/campaigns`
- `GET /api/availability/promotions/campaign`

### Availability (date-based)
- `GET /api/availability?from=...&to=...`
- `POST /api/availability`
- `GET /api/availability/me`
- `GET/POST /api/availability/settings`
- `GET/POST /api/availability/subscriptions`

---

## Frontend Views (SPA)

| View | Route | Purpose |
|------|-------|---------|
| Home | `/#/` | Dashboard, search, widgets |
| Profile | `/#/profile` | Player stats + charts |
| Leaderboard | `/#/leaderboard` | Rankings by DPM/Kills/K/D |
| Matches | `/#/matches` | Match browser with details modal |
| Sessions | `/#/sessions` | Gaming session history |
| Maps | `/#/maps` | Map statistics + balance |
| Weapons | `/#/weapons` | Weapon usage stats |
| Records | `/#/records` | Hall of Fame |
| Awards | `/#/awards` | Achievement badges |

---

## Security

### XSS Prevention (Frontend)
```javascript
// Always use these for user-generated content:
escapeHtml(userInput)      // For innerHTML
escapeJsString(playerName) // For onclick handlers
```

### SQL Injection Prevention (Backend)
```python
# All queries use parameterized statements
query = "SELECT * FROM players WHERE name = $1"
await db.fetch(query, (user_input,))

# LIKE patterns escaped
from bot.core.utils import escape_like_pattern
pattern = escape_like_pattern(search_term)
```

---

## Configuration (.env)

```bash
# Database (read-only user recommended)
DATABASE_TYPE=postgresql
POSTGRES_HOST=localhost
POSTGRES_DATABASE=etlegacy
POSTGRES_USER=website_readonly
POSTGRES_PASSWORD=...

# Session security (REQUIRED)
SESSION_SECRET=<generate-with-secrets.token_urlsafe(32)>

# Discord OAuth
DISCORD_CLIENT_ID=...
DISCORD_CLIENT_SECRET=...
DISCORD_REDIRECT_URI=http://localhost:8000/auth/callback
DISCORD_REDIRECT_URI_ALLOWLIST=http://localhost:8000/auth/callback
DISCORD_OAUTH_STATE_TTL_SECONDS=600
DISCORD_OAUTH_RATE_LIMIT_WINDOW_SECONDS=60
DISCORD_OAUTH_RATE_LIMIT_MAX_REQUESTS=40

# Promote + linking controls
PROMOTER_DISCORD_IDS=
AVAILABILITY_PROMOTION_TIMEZONE=Europe/Ljubljana
AVAILABILITY_PROMOTION_DRY_RUN_DEFAULT=false
AVAILABILITY_PROMOTION_GLOBAL_COOLDOWN=false
CONTACT_DATA_ENCRYPTION_KEY=

# Server
WEBSITE_PORT=8000
WEBSITE_HOST=0.0.0.0
GREATSHOT_STARTUP_TIMEOUT_SECONDS=20
```

---

## Database Access

### Read-Only User Setup
```sql
-- Run setup_readonly_user.sql
CREATE USER website_readonly WITH PASSWORD '...';
GRANT SELECT ON ALL TABLES IN SCHEMA public TO website_readonly;
```

### Shared Tables (with bot)
| Table | Written By | Read By |
|-------|-----------|---------|
| `rounds` | Bot | Website |
| `player_comprehensive_stats` | Bot | Website |
| `weapon_comprehensive_stats` | Bot | Website |
| `player_links` | Bot + Website | Both |
| `user_player_links` | Website | Website/Bot bridge |
| `discord_accounts` | Website | Website |
| `lua_round_teams` | Bot | Website |

---

## Deployment

### Screen Session (Current)
```bash
# Running in screen session "website"
screen -r website  # Attach
# Ctrl+A D to detach
```

### Start Commands
```bash
cd /home/samba/share/slomix_discord/website
source venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### Systemd Alternative
```bash
sudo cp etlegacy-website.service /etc/systemd/system/
sudo systemctl enable etlegacy-website
sudo systemctl start etlegacy-website
```

---

## Key Features

### Live Status Polling
- Game server status via UDP Quake3 protocol
- Voice channel status from bot integration
- 10-second refresh interval

### Player Linking
- Discord OAuth → fetch user info
- Search for ET player name
- Store mapping in `player_links` table
- Website and bot share this data

### Charts (Chart.js)
- Session form: DPM trend over 15 sessions
- Round performance: DPM for 30 individual rounds
- Session distribution: Maps, outcomes

---

## Common Tasks

### Add New API Endpoint
1. Edit `website/backend/routers/api.py`
2. Use parameterized queries (`$1`, `$2`)
3. Add proper error handling
4. Test with `curl http://localhost:8000/api/your-endpoint`

### Add New Frontend View
1. Add view container in `index.html`
2. Create `website/js/your-view.js`
3. Add navigation in `app.js`
4. Use `escapeHtml()` for user content

### Debug Database Issues
```bash
# Test query directly
PGPASSWORD='...' psql -h localhost -U website_readonly -d etlegacy \
  -c "SELECT COUNT(*) FROM rounds;"

# Check API response
curl -s http://localhost:8000/api/status | jq
```

---

## Integration with Bot

**No direct integration needed.** Data flow is automatic:

1. Game server writes stats file
2. Bot parses and imports to PostgreSQL
3. Website queries PostgreSQL on page load
4. Users see updated stats

**Shared data**: `player_links` table used by both for Discord ↔ player mapping.

---

## Quick Reference

| What | Where |
|------|-------|
| Start website | `screen -r website` or systemctl |
| API code | `website/backend/routers/api.py` |
| Frontend views | `website/js/*.js` |
| Config | `website/.env` |
| Logs | `logs/website.log` |
| Port | 8000 |

---

**Status**: Production-Ready
