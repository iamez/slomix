# Codex Report — Proximity sanitizeName Fix (2026-02-04)

## Issue
Server log errors on player connect:
```
et_ClientConnect error running lua script: 'proximity_tracker.lua:355: global 'sanitizeName' is not callable (a nil value)'
```

## Root Cause
`sanitizeName` was defined **after** it was used inside `updateClientCache`, so Lua treated it as a global (nil) at runtime.

## Fix
Moved `sanitizeName` above `updateClientCache` in:
- `proximity/lua/proximity_tracker.lua`

## Deployed
Uploaded to server:
```
/home/et/etlegacy-v2.83.1-x86_64/legacy/proximity_tracker.lua
```

## Required Action
Run one of:
- `lua_restart`
- or `map_restart 0`
to reload the fixed script.
