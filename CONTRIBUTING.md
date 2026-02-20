# Contributing

Detailed contribution guidance lives in `docs/CONTRIBUTING.md`.

## Quick Rules

1. Use Conventional Commits (`feat:`, `fix:`, `chore:`, etc.).
2. Run local checks before opening a PR:
   - `ruff check bot/ website/backend/`
   - `pytest tests/ -v --tb=short`
   - `npm run lint:js`
3. Keep changes scoped and include tests for behavior changes.
4. Never commit secrets (`.env`, tokens, private keys).

## Local Stack

- Bootstrap once: `make dev`
- Stop stack: `make down`
