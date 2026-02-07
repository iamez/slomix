# Reference Lua Script Comparison (Oksii vs Slomix)
Date: 2026-02-03

This document compares the reference script in `docs/reference/oksii-game-stats-web.lua` with our `vps_scripts/stats_discord_webhook.lua` and extracts improvements to apply.

## Summary
The Oksii script is production‑hardened for a large community (300+ players). It includes robust HTTP delivery, config validation, and local persistence fallback. Our webhook script is lightweight and fast but lacks delivery resilience and local failover, which can explain **"NO LUA DATA"** in the bot.

## Key Differences (Oksii wins)
1. **Config & Validation**
   - Oksii loads `config.toml`, validates configs, and supports dynamic override.
   - Our script uses a hardcoded webhook URL and no validation.

2. **HTTP Delivery Reliability**
   - Oksii: async curl with retries, timeouts, compression, and payload written to a temp file (`--data-binary @file`).
   - Us: raw `os.execute(curl ...)` on a JSON string (fragile when names contain quotes).

3. **Failure Recovery**
   - Oksii: optional local JSON dump if submission fails.
   - Us: if webhook fails, data is lost.

4. **Stable Match Identification**
   - Oksii: fetches `match_id` from remote API; caches it; falls back to unix time.
   - Us: no match_id/server_ip/server_port in payload; matching relies on file time heuristics.

5. **Duplicate Guard**
   - Oksii: `saveStatsState.inProgress` prevents multiple SaveStats() calls.
   - Us: no explicit de‑dupe guard beyond state variables.

## Implications for Slomix
- Missing Lua timing data can be caused by **webhook payload failures** or **Discord embed truncation**.
- Our webhook delivery is fragile against special characters and payload size limits.
- Lack of a stable match_id increases pairing mistakes and “NO LUA DATA” incidents.

## Planned Improvements (Borrowed from Oksii)
1. ✅ **Safe curl sender with retries**
   - Temp file + `--data-binary @file`.
   - Retry/timeout options.
   - Logs failures.

2. ✅ **Local failover file**
   - Writes JSON payload to `gametimes/` (toggleable).

3. ✅ **Stable identifiers**
   - `gametimes` payload includes `server_ip`, `server_port`, `match_id` (fallback to unix).

4. ✅ **Deduplicate sends**
   - Uses `map+round+round_end_unix` signature.

5. ☐ **Minimize embed size**
   - Keep embed short; push data fields into JSON payload (optional).

## Files to Modify
- `vps_scripts/stats_discord_webhook.lua`
- `docs/SESSION_2026-02-03_CHANGELOG_LOCAL.md`
- (optional) `docs/SECRETS_CENTRALIZATION_PLAN_2026-02-03.md`
