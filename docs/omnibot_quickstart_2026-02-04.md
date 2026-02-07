# Omni-bot Quickstart (ET:Legacy) — 2026-02-04

This is a **short, repeatable** procedure to enable Omni-bots for bot-only scrims and disable them afterward **without locking out humans**.

## 0) Safety prerequisite (prevents “excluded from server 0”)
Whitelist mode (g_filterBan 0) will exclude humans if g_banIPs is empty.
Make sure these are set in `vektor.cfg`:

```
set g_filterBan "1"
set g_banIPs ""
```

This is now enforced in `vektor.cfg` on your server.

## 1) Enable Omni-bots
In server console:

```
omnibot_enable 1; map_restart 0
```

Confirm load:
- You should see `Omni-bot Loaded Successfully` in console.
- `status` should list bot clients once added.

## 2) Add bots (3v3 example)
Use any combo of these:

```
bot addbot
bot addbot
bot addbot
bot addbot
bot addbot
bot addbot
```

Optional: assign names / teams later.

## 3) Bot-only scrim mode (recommended settings)
Set match to auto-start and allow low player count:

```
match_readypercent 0; match_minplayers 0; g_doWarmup 0; g_warmup 0; map_restart 0
```

## 4) Map rotation (bot scrim cycle)
If using the custom bot scrim mapcycle:

```
exec bot_scrim_mapcycle.cfg
```

Mapcycle path on server:
- `/home/et/etlegacy-v2.83.1-x86_64/etmain/bot_scrim_mapcycle.cfg`

## 5) Disable Omni-bots (restore human-only play)
In server console:

```
bot kickall; omnibot_enable 0; map_restart 0
```

## 6) Waypoint status (important)
Bots only play maps with **working navs**.
Currently confirmed navs on server:
- `supply`, `etl_sp_delivery`, `te_escape2`, `sw_goldrush_te`, `braundorf_b4`

Stopgap navs copied:
- `etl_adlernest` (from `adlernest`)
- `etl_frostbite` (from `etl_frostbite_v4`)
- `erdenberg_t2` (incomplete)

If bots stand still:
- Missing/invalid navs for that map.

## 7) Troubleshooting checklist
- **Excluded from server 0** → check `g_filterBan` must be `1`.
- **Bots won’t load** → confirm `omnibot_enable 1` and server has `legacy/omni-bot/omnibot_et.x86_64.so`.
- **Bots won’t move** → nav missing or incompatible.

