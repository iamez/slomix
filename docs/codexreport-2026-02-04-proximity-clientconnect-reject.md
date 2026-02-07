# Codex Report — Proximity ClientConnect Reject Fix (2026-02-04)

## Symptom
Clients were getting:
```
You are excluded from the server 0
```
and server logs only showed:
```
Client X connecting...
Writing session file...
```

## Root Cause
`proximity_tracker.lua` implemented:
```
function et_ClientConnect(...)
    updateClientCache(...)
    return 0
end
```
In ET:Legacy Lua, **any non-nil return value** from `et_ClientConnect` is treated as a rejection string.
Returning `0` was interpreted as a rejection reason and produced the client message
`excluded from the server 0`.

## Fix
Changed `return 0` → `return nil` in:
- `proximity/lua/proximity_tracker.lua`

## Deployed
Uploaded to server:
```
/home/et/etlegacy-v2.83.1-x86_64/legacy/proximity_tracker.lua
```

## Required Action
Run one of:
- `lua_restart`
- `map_restart 0`
to reload the script.
