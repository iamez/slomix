# Ban/Exclude Trace — 2026-02-04

## Summary
You were getting **"excluded from server 0"** even after restarts. I traced the server configs over SSH and found that **`g_filterBan` was persisted as `0`** in the auto-written server config. In ET, `g_filterBan 0` turns the ban list into a whitelist, so if your IP is not explicitly listed, **every human gets excluded** while bots still join.

## What I checked (server-side)
- **WolfAdmin files**
  - Found: `/home/et/etlegacy-v2.83.1-x86_64/legacy/luascripts/wolfadmin`
  - Config: `/home/et/etlegacy-v2.83.1-x86_64/legacy/wolfadmin.toml`
  - **No wolfadmin database found** (no `wolfadmin.db` on disk)
  - **No ban files in `~/.etlegacy/legacy`** (searched for `*ban*`, none found)
- **Lua modules**
  - `legacy3.config` currently sets: `lua_modules "luascripts/team-lock"` (WolfAdmin not loaded)
- **Omni-bot**
  - `vektor.cfg` already has `omnibot_enable "0"`

## Root cause found
`/home/et/.etlegacy/legacy/etconfig_server.cfg` had:

- `seta g_filterBan "0"`  ✅ **(whitelist mode)**
- `seta g_banIPs ""`       ✅ **(empty list)**

That combination **excludes all human clients**.

## Changes applied
Updated the auto-written config to normal ban mode:

- `seta g_filterBan "1"`
- `seta g_banIPs ""`

File edited:
- `/home/et/.etlegacy/legacy/etconfig_server.cfg`

## Update: force sane defaults via vektor.cfg
To make sure `exec vektor.cfg` also fixes the issue, I added these lines in:
- `/home/et/etlegacy-v2.83.1-x86_64/etmain/vektor.cfg`

```
set g_filterBan "1"
set g_banIPs ""
```

## What you should do next
Restart server or run:
- `exec etconfig_server.cfg; map_restart 0`

This will apply `g_filterBan 1` immediately.

## Notes
- WolfAdmin is not currently loaded, so it is **not** the source of the ban.
- Omni-bot is already disabled in `vektor.cfg`.
