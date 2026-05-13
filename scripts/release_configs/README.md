# Release configs

Per-tag config sourced by `scripts/deploy_release.sh` at deploy time.

## File layout

```
scripts/
  deploy_release.sh                 # Generic runner (release-agnostic)
  release_configs/
    README.md                       # This file
    v1.14.2.sh                      # One config per release tag
    v1.14.3.sh
    ...
```

## Creating a config for a new release

1. From the repo root, copy an existing config: `cp scripts/release_configs/v1.14.2.sh scripts/release_configs/v1.14.3.sh`
2. Edit the three arrays:
   - `MIGRATIONS=()` — filenames under `migrations/` to `psql`-apply in order. Must be idempotent (`IF NOT EXISTS`, `ON CONFLICT DO NOTHING`, etc.).
   - `FLAGS=()` — `KEY=VALUE` pairs to set/replace in `/opt/slomix/.env`. The deploy script uses `sudo` to write — the deploy user has read-only access to `.env`.
   - `RELEASE_NOTES=""` — one-line description shown in the deploy header.
3. Keep the `# shellcheck shell=bash` + `# shellcheck disable=SC2034` directives in the header — without them, shellcheck/Codacy flag the three arrays as "unused" (they're consumed via `source`, which static linters can't see).
4. Commit alongside the release PR (so the tag and its config land together).

## Deploying

```bash
# Full deploy
SUDO_PASS=<pass> ./scripts/deploy_release.sh v1.14.3

# Dry run (no changes, prints what would happen)
./scripts/deploy_release.sh v1.14.3 --dry-run

# Code-only deploy (skip migrations + flags, e.g. for a hotfix)
SUDO_PASS=<pass> ./scripts/deploy_release.sh v1.14.3 --skip-migrations --skip-flags
```

If the config file is missing and you didn't pass both `--skip-migrations`
and `--skip-flags`, the runner aborts with a template message.

## Migration tracking

After a successful `psql` apply, the runner calls `apply_migrations.py --mark`
to record the rows in `schema_migrations` so the migration runner doesn't
treat them as pending on the next deploy. This was a real gap pre-PR #257:
v1.14.2 migrations 052/053/054 went in via raw psql and the runner kept
showing them as pending until we manually reconciled.

## Cache-buster

Every deploy auto-bumps the `?v=...` query on `index.html` + `app.js` +
`session-detail.js` to the current git short SHA. Cloudflare caches static
JS for 24h keyed on the full URL including query string, so without the
bump CF would keep serving the previous release's bytes for a day. The
bump persists on disk after the deploy — `git checkout -f` on the next
deploy force-overwrites the bumped files with the new tag's content.
