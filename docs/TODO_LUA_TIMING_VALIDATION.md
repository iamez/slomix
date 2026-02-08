# TODO — Lua Timing Validation & Gametimes Pipeline

## Goal
Verify **time dead** and **time denied** by capturing raw Lua timing and comparing against stats-file derived values.

---

## ✅ Recent Update (already deployed)
Updated `stats_discord_webhook.lua` to:
- Log resolved gametimes paths (`fs_basepath`, `fs_homepath`, `fs_game`)
- Write gametimes JSON with extra meta (round start/end, actual duration, warmup, pauses)
- Log file writes (`Gametime file written`)

---

## 1) Reload Lua Script (Game Server)
Restart map or server so Lua reloads.

Optional check:
```bash
ssh -i ~/.ssh/etlegacy_bot -p 48101 et@91.185.207.163 \
"grep -n 'stats_discord_webhook\|v1.6.0' /home/et/.etlegacy/legacy/etconsole.log | tail -n 30"
```

---

## 2) Confirm Gametimes Directory
```bash
ssh -i ~/.ssh/etlegacy_bot -p 48101 et@91.185.207.163 \
"ls -ld /home/et/.etlegacy/legacy/gametimes"
```

---

## 3) Finish a Real Round
We need a completed round to trigger:
- Discord webhook
- Gametimes JSON file write

---

## 4) Verify Lua Logs + File Output
```bash
ssh -i ~/.ssh/etlegacy_bot -p 48101 et@91.185.207.163 \
"grep -n 'gametimes_enabled\|Gametime file written\|Round ended' /home/et/.etlegacy/legacy/etconsole.log | tail -n 60"
```

```bash
ssh -i ~/.ssh/etlegacy_bot -p 48101 et@91.185.207.163 \
"ls -lt /home/et/.etlegacy/legacy/gametimes | head"
```

---

## 5) Apply DB Migration (Lua Spawn Stats)
```bash
sudo -u postgres psql -d etlegacy -f /home/samba/share/slomix_discord/migrations/008_add_lua_spawn_stats.sql
```

Grant read access:
```bash
sudo -u postgres psql -d etlegacy -c "GRANT SELECT ON TABLE lua_spawn_stats TO website_readonly;"
```

---

## 6) Confirm Bot Stored Lua Spawn Stats
```bash
rg -n "Stored Lua spawn stats|lua_spawn_stats" logs/bot.log | tail -n 50
```

---

## 7) Run API Diagnostics
```bash
curl -s http://localhost:8000/api/diagnostics/lua-webhook | python3 -m json.tool
```

```bash
curl -s "http://localhost:8000/api/diagnostics/spawn-audit?limit=200&diff_seconds=30" | python3 -m json.tool
```

---

## 8) Compare Lua vs Stats File (Manual Spot Check)
If a gametimes file was created, pick one and compare against the stats file:

```bash
# Find latest gametimes file
ssh -i ~/.ssh/etlegacy_bot -p 48101 et@91.185.207.163 \
"ls -lt /home/et/.etlegacy/legacy/gametimes | head -n 5"
```

```bash
# Copy that gametime file to local for review
scp -P 48101 -i ~/.ssh/etlegacy_bot \
"et@91.185.207.163:/home/et/.etlegacy/legacy/gametimes/<FILENAME>.json" \
/home/samba/share/slomix_discord/local_gametimes/
```

Then compare:
- Lua meta: `round_start_unix`, `round_end_unix`, `actual_duration_seconds`
- Stats file values: `time_played`, `time_dead`, `denied_playtime`

---

## 9) What We Expect to Learn
- Are Lua **dead_seconds** consistent with stats-file `time_dead`?
- Is **time denied** inflated by session aggregations or round truncation?
- Do warmup/pause segments skew totals?

---

## Notes
- Lua spawn stats are best for **dead time validation**.
- Stats file may include edge cases (surrender, early disconnect, late spawn).
- Once validation is stable, we can trust Lua for timing and keep stats-file for other metrics.

