# Website Backend - CLAUDE.md

## Overview

FastAPI backend for the ET:Legacy Statistics Website.
Provides REST API endpoints for player stats, sessions, predictions, and Greatshot analytics.

## Architecture

```python
Frontend (website/)
    |
    | HTTP/REST
    v
FastAPI (main.py)
    |
    +-- Routers (api.py, auth.py, predictions.py, greatshot.py, greatshot_topshots.py)
    |
    +-- Services (session + greatshot + voice/game helpers)
    |
    +-- Database adapter (local_database_adapter.py)
            |
            +-- PostgreSQL (shared with bot)
```python

## File Reference

| File | Purpose |
|------|---------|
| `main.py` | FastAPI app, middleware, router wiring |
| `dependencies.py` | Dependency injection (DB, auth) |
| `local_database_adapter.py` | PostgreSQL async adapter |
| `init_db.py` | Database initialization |

### Routers

| Router | Prefix | Purpose |
|--------|--------|---------|
| `api.py` | `/api` | Stats/session/search endpoints |
| `auth.py` | `/auth` | Discord OAuth |
| `predictions.py` | `/api/predictions` | Prediction endpoints |
| `greatshot.py` | `/api` | Greatshot import/crossref endpoints |
| `greatshot_topshots.py` | `/api` | Greatshot topshots endpoints |
| `uploads.py` | `/api/uploads` | Community file upload library |
| `availability.py` | `/api/availability` | Daily availability poll API |

### Services

| Service | Purpose |
|---------|---------|
| `website_session_data_service.py` | Session data aggregation |
| `greatshot_crossref.py` | Greatshot cross-reference matching |
| `greatshot_jobs.py` | Greatshot background job orchestration |
| `upload_store.py` | Upload file storage (UUID paths, streaming, SHA256) |
| `upload_validators.py` | Upload security (extension allowlists, magic bytes, size limits) |
| `greatshot_store.py` | Greatshot storage and schema helpers |
| `voice_channel_tracker.py` | Voice activity tracking helpers |
| `game_server_query.py` | Game-server query helpers |

## Security Requirements

### SESSION_SECRET (CRITICAL)

```python
# main.py - No defaults allowed
SESSION_SECRET = os.getenv("SESSION_SECRET")
if not SESSION_SECRET or SESSION_SECRET == "super-secret-key-change-me":
    raise ValueError("SESSION_SECRET must be set to secure value")
```text

Generate a secret:

```bash
python -c 'import secrets; print(secrets.token_urlsafe(32))'
```text

### CORS Configuration

```python
# Restricted to specific origins
allow_origins=[
    "http://localhost:8000",
    "https://your-domain.com"
]
allow_headers=["Content-Type", "Authorization", "X-Requested-With"]
```text

### SQL Injection Prevention

```python
# All queries use parameterized SQL
from website.backend.routers.api import escape_like_pattern

# For LIKE queries
pattern = escape_like_pattern(user_input)
query = "SELECT * FROM players WHERE name LIKE ?"
```yaml

## API Endpoints

### Stats API (`/api`)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/stats/{guid}` | GET | Player statistics |
| `/api/leaderboard` | GET | Top players by metric |
| `/api/sessions` | GET | Recent gaming sessions |
| `/api/session/{id}` | GET | Specific session details |
| `/api/records` | GET | All-time records |
| `/api/search` | GET | Player search |

### Auth (`/auth`)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/auth/discord` | GET | Start Discord OAuth |
| `/auth/callback` | GET | OAuth callback |
| `/auth/logout` | GET | Clear session |
| `/auth/me` | GET | Current user info |

## Database Access

Uses shared PostgreSQL database with the bot:

```python
# local_database_adapter.py
DATABASE_URL = f"postgresql://{user}:{password}@{host}:{port}/{db}"

async def fetch_all(query: str, params: tuple = ()):
    async with pool.acquire() as conn:
        return await conn.fetch(query, *params)
```text

## Running the Backend

```bash
# Development
cd website
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Production (systemd)
sudo systemctl start etlegacy-website
```text

## Environment Variables

```bash
# Database (same as bot)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=etlegacy
DB_USER=etlegacy_user
DB_PASSWORD=REDACTED_DB_PASSWORD

# Security
SESSION_SECRET=<generate-with-secrets-module>

# OAuth (optional)
DISCORD_CLIENT_ID=...
DISCORD_CLIENT_SECRET=...
DISCORD_REDIRECT_URI=...
```text

## Common Patterns

### Endpoint with Pagination

```python
@router.get("/leaderboard")
async def get_leaderboard(
    metric: str = "dpm",
    limit: int = Query(default=10, le=100),
    offset: int = Query(default=0, ge=0)
):
    query = f"""
        SELECT player_guid, MAX(player_name) as name, AVG({metric}) as value
        FROM player_comprehensive_stats
        GROUP BY player_guid
        ORDER BY value DESC
        LIMIT ? OFFSET ?
    """
    return await db.fetch_all(query, (limit, offset))
```text

### Error Handling

```python
from fastapi import HTTPException

@router.get("/stats/{guid}")
async def get_stats(guid: str):
    if not is_valid_guid(guid):
        raise HTTPException(status_code=400, detail="Invalid GUID format")

    stats = await fetch_player_stats(guid)
    if not stats:
        raise HTTPException(status_code=404, detail="Player not found")

    return stats
```
