# RUNBOOK_LOCAL_LINUX

Local Linux bootstrap for Availability + Linking + Promote + Planning flows.

## 1) Install prerequisites
```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip build-essential postgresql-client
```

## 2) Python environment
```bash
cd /home/samba/share/slomix_discord
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -r website/requirements.txt
```

## 3) Required environment variables
Use `website/.env` (or exported shell vars):
- `SESSION_SECRET`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DATABASE`
- `DISCORD_CLIENT_ID`
- `DISCORD_CLIENT_SECRET`
- `DISCORD_REDIRECT_URI`

Optional but recommended:
- `AVAILABILITY_PROMOTION_ENABLED=true`
- `AVAILABILITY_LINK_TOKEN_MIN_INTERVAL_SECONDS=30`
- `AVAILABILITY_PROMOTION_GLOBAL_COOLDOWN=true`

## 4) Start stack (local)
```bash
cd /home/samba/share/slomix_discord
SKIP_INSTALL=1 make dev-local
```

This starts:
- website on port `7000`
- bot runtime (or validate-only mode if configured)

## 5) Health checks
```bash
curl -fsS http://127.0.0.1:7000/health
curl -fsS http://127.0.0.1:7000/api/status
```

## 6) Test gate (prompt-critical slice)
```bash
pytest -q \
  tests/unit/test_availability_router.py \
  tests/unit/test_auth_linking_flow.py \
  tests/unit/test_availability_promotions_router.py \
  tests/unit/test_availability_poll_promotion_runtime.py \
  tests/unit/test_planning_router.py
```

## 7) Common failures and fixes
- `/health` fails with DB error:
  - verify `POSTGRES_*` env and DB role grants (migration `website/migrations/008_website_app_availability_grants.sql`).
- `/auth/link` returns `permission denied for table player_links`:
  - re-apply migration `008` and verify `website_app` table/sequence privileges.
- Availability buttons appear no-op:
  - hard refresh browser (`Ctrl+Shift+R`) after deploy and ensure `website/js/availability.js` is current.
- Link token generation returns 429:
  - wait for `AVAILABILITY_LINK_TOKEN_MIN_INTERVAL_SECONDS` cooldown.

## 8) Logs
```bash
tail -f logs/web.log
tail -f logs/errors.log
tail -f logs/bot.log
```

Canonical long-form runbook: `docs/RUNBOOK.md`.
