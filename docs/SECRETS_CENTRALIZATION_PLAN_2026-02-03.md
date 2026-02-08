# Secrets Centralization Plan (Draft)
Date: 2026-02-03

This is a **non-breaking** plan to centralize secrets (webhooks, DB passwords, SSH paths) without changing current behavior. It is documentation-only for now.

## Goals
- Keep secrets **out of repo** while preserving developer convenience.
- Maintain compatibility with existing `.env` and `bot_config.json` flows.
- Allow separate local/dev/prod overrides without code changes.

## Proposed Approach
1. **Single source of truth:**
   - Prefer `.env` for local dev
   - Support `bot_config.json` for structured config overrides
2. **No secrets in code:**
   - Replace hardcoded webhook URLs with config/env values
   - Provide safe fallback to `REPLACE_WITH_YOUR_WEBHOOK_URL`
3. **Per-environment overlays:**
   - `.env.local` (ignored by git) for personal values
   - `.env.production` on server (not in repo)
4. **Runtime validation:**
   - Startup check to warn if secrets missing or defaults used
5. **Rotation checklist:**
   - Add a simple script/document to rotate keys safely

## Minimal Implementation Plan (Future)
- Add `SECRETS.md` with required env keys and source priority.
- Add `tools/validate_env.py` to warn on missing secrets.
- Replace hardcoded webhook URLs in Lua with injected config value.

## Status
- Draft only. No behavior changes yet.
