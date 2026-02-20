# Runbook

## Stage 0 goal
Bring up website + bot with actionable logs and health checks.

## Prereqs
- Python 3.10+
- `pip`
- `curl`
- Optional: Docker + Docker Compose (for containerized dev)

## Env bootstrap
```bash
cp .env.example .env
cp website/.env.example website/.env
```

Set at minimum in `.env`:
- `SESSION_SECRET`
- `DATABASE_TYPE` (`sqlite` for local quick start, `postgresql` for prod-ish)
- `DISCORD_BOT_TOKEN` (or use validate-only mode in local dev)

## Local dev (no Docker)
Runs web on port `7000` and bot in the same process group with shared logs.

```bash
make dev-local
# same as: ./scripts/dev_up.sh
# optional in restricted CI/sandbox:
# SKIP_HEALTHCHECK=1 ./scripts/dev_up.sh
```

Dev defaults in `scripts/dev_up.sh`:
- `WEBSITE_PORT=7000`
- `DATABASE_TYPE=sqlite`
- `CACHE_BACKEND=memory`
- `GREATSHOT_STARTUP_ENABLED=false`
- If no `DISCORD_BOT_TOKEN`, bot runs with `BOT_STARTUP_VALIDATE_ONLY=true`
- Optional overrides use `DEV_*` vars (`DEV_WEBSITE_PORT`, `DEV_DATABASE_TYPE`, `DEV_CACHE_BACKEND`, `DEV_SQLITE_DB_PATH`).

Health check:
```bash
curl -fsS http://127.0.0.1:7000/health
```

## Containerized dev
```bash
make dev
```

## Prod-ish local startup
Requires full env + PostgreSQL credentials + real Discord token.

```bash
make prod
# same as: ./scripts/prod_up.sh
```

Defaults in `scripts/prod_up.sh`:
- `WEBSITE_PORT=7000`
- `DATABASE_TYPE=postgresql`
- `CACHE_BACKEND=redis`

## Logs
- `logs/web.log`
- `logs/bot.log`
- `logs/errors.log`

Fast boot error view:
```bash
tail -n 200 logs/errors.log
```

Follow all logs live:
```bash
tail -f logs/web.log logs/bot.log logs/errors.log
```

## Common failures
- `SESSION_SECRET environment variable must be set`:
  - Set `SESSION_SECRET` in `.env`.
- Web health check fails:
  - Inspect `logs/web.log` and `logs/errors.log`.
  - Verify DB settings (`DATABASE_TYPE`, PG vars, sqlite path).
- Bot exits with code 1:
  - Missing `DISCORD_BOT_TOKEN` (set token or use dev validate-only mode).
- Bot exits with code 2:
  - Invalid Discord token.
