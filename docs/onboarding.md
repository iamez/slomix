# Onboarding

Use this as the shortest safe path into the repo.

## Read Order

1. [README.md](/home/samba/share/slomix_discord/README.md)
2. [ARCHITECTURE.md](/home/samba/share/slomix_discord/ARCHITECTURE.md)
3. [docs/ESSENTIAL_RUNTIME_MAP.md](/home/samba/share/slomix_discord/docs/ESSENTIAL_RUNTIME_MAP.md)
4. The subsystem docs relevant to your task:
   `bot/`, `website/`, `greatshot/`, `proximity/`, or deploy/runtime docs under `docs/`

## Runtime Entry Points

- Full repo-managed runtime: [scripts/prod_up.sh](/home/samba/share/slomix_discord/scripts/prod_up.sh)
- Local development stack: [scripts/dev_up.sh](/home/samba/share/slomix_discord/scripts/dev_up.sh)
- Compose stack: [docker-compose.yml](/home/samba/share/slomix_discord/docker-compose.yml)
- Bot only helper: [start_bot.sh](/home/samba/share/slomix_discord/start_bot.sh)

## Core Areas

- [bot](/home/samba/share/slomix_discord/bot)
  Discord bot, ingestion, session logic, and automation.
- [website](/home/samba/share/slomix_discord/website)
  FastAPI backend and SPA frontend.
- [greatshot](/home/samba/share/slomix_discord/greatshot)
  Demo analysis and highlight pipeline.
- [proximity](/home/samba/share/slomix_discord/proximity)
  Optional proximity telemetry and parser pipeline.
- [tools](/home/samba/share/slomix_discord/tools)
  Reusable operator and maintenance helpers.

## Safe First Commands

- `make bootstrap`
- `make test`
- `make lint`

If you are doing cleanup work, read [docs/archive/README.md](/home/samba/share/slomix_discord/docs/archive/README.md) and keep historical material archived rather than deleted unless runtime impact has been disproven.
