# Lua Webhook Hardening Plan (v1.5.0)
Date: 2026-02-03

## Goal
Make `stats_discord_webhook.lua` as reliable as Oksii’s production script while keeping our lightweight real‑time webhook format.

## Implemented (This Session)
1. **Safe curl sender**
   - Temp file + `--data-binary @file` to avoid JSON quoting issues.
   - Retries + timeouts + compression.
2. **Local gametimes fallback**
   - Writes payload JSON to `gametimes/` for later ingestion.
   - Optional write‑on‑failure‑only flag.
3. **Duplicate guard**
   - Prevents re‑sending same map/round/end_time.
4. **Version bump**
   - Script version updated to `1.5.0`.
5. **Stable identifiers in fallback file**
   - `server_ip`, `server_port`, and `match_id` recorded in `gametimes` meta.

## Pending / Optional Next Steps
1. **Bot ingestion of `gametimes/` files**
   - Add SSH fetch to pull `gametimes/*.json` if webhook missing.
2. **Match ID strategy**
   - Add server_ip/server_port and optional match_id from a small API endpoint.
3. **Payload trimming**
   - Reduce embed size (avoid near 25‑field limit).
4. **Config externalization**
   - Optional `config.toml` for webhook URL + flags.

## Files Updated
- `vps_scripts/stats_discord_webhook.lua`
- `docs/LUA_REF_SCRIPT_COMPARISON_2026-02-03.md`
- `docs/SESSION_2026-02-03_CHANGELOG_LOCAL.md`
