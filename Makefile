SHELL := /bin/bash

.PHONY: dev dev-bg dev-local prod down logs ps test lint bootstrap

bootstrap:
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env from .env.example"; fi
	@if [ ! -f website/.env ]; then cp website/.env.example website/.env; echo "Created website/.env from website/.env.example"; fi

dev: bootstrap
	docker compose up --build

dev-bg: bootstrap
	docker compose up --build -d

dev-local: bootstrap
	./scripts/dev_up.sh

prod: bootstrap
	./scripts/prod_up.sh

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

ps:
	docker compose ps

test:
	pytest tests/ -v --tb=short

lint:
	ruff check bot/ website/backend/
	./scripts/lint-js.sh
