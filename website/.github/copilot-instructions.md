# ET:Legacy Stats Website - AI Agent Instructions

## Project Identity
**ET:Legacy Stats Website** - FastAPI backend + vanilla JS frontend for displaying player stats from the Discord bot's PostgreSQL database.

## Architecture

### Backend (FastAPI)
- **Entry point:** `backend/main.py`
- **Database:** Read-only connection to bot's PostgreSQL (`et_stats` database)
- **Routers:** `backend/routers/api.py` (stats endpoints), `backend/routers/auth.py` (future)

### Frontend (Vanilla JS)
- **Main:** `index.html` + `js/app.js`
- **Records page:** `js/records.js`
- **No framework** - plain HTML/CSS/JS

## Database Access

**CRITICAL: Read-only access to bot's database**
- Uses same PostgreSQL as Discord bot
- Schema defined in bot's `postgresql_database_manager.py`
- Main table: `player_comprehensive_stats` (53 columns)

```python
# Connection pattern
from backend.local_database_adapter import LocalDatabaseAdapter
db = LocalDatabaseAdapter()
await db.connect()
```

## Key Files

| File | Purpose |
|------|---------|
| `backend/main.py` | FastAPI app, CORS, routers |
| `backend/routers/api.py` | Stats API endpoints |
| `backend/local_database_adapter.py` | Async PostgreSQL adapter |
| `js/app.js` | Frontend stats display |
| `index.html` | Main page |

## API Endpoints

- `GET /api/players` - List all players
- `GET /api/player/{guid}` - Player stats
- `GET /api/leaderboard` - Top players
- `GET /api/records` - Server records
- `GET /api/sessions` - Recent sessions

## Running Locally

```bash
cd website
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

Then open `index.html` in browser or use Live Server extension.

## Conventions

1. **Never modify bot's database** - read-only queries only
2. **Use parameterized queries** - prevent SQL injection
3. **Keep frontend simple** - no build tools, no frameworks
4. **Match bot's data** - website displays same stats as Discord commands

## Environment Variables

```bash
POSTGRES_HOST=localhost
POSTGRES_DATABASE=et_stats
POSTGRES_USER=website_readonly  # Use read-only user!
POSTGRES_PASSWORD=xxx
```
