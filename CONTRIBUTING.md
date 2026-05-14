# Contributing

The previous long-form `docs/CONTRIBUTING.md` was retired (see Feb 2026 commit `0ed9747`). The rules that actually matter live below + in `docs/CLAUDE.md` (the root `CLAUDE.md` is a symlink to it). For deeper conventions (database, branch policy, R2 differential, etc.) read `docs/CLAUDE.md`.

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
