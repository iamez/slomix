# Omni-bot — Operations & Runbook

**Status**: ✅ **LIVE — in active use** (last live audit: 2026-05-19)
**Purpose**: AI-controlled players on the `puran.hehe.si` ET:Legacy server for
testing the stats / proximity pipeline without recruiting humans.
**Primary tool**: `tools/slomix_rcon.py` (run with **`python3`** on the dev box)

> ⚠️ This document was rewritten 2026-05-19 to match the live server. The old
> `scripts/omnibot_toggle.py` / `bot_scrim_mode.py` / `generate_omnibot_botnames.py`
> are **archived** (`scripts/archive/`) — do not use them; everything is now
> subcommands of `tools/slomix_rcon.py`.

---

## 1. TL;DR — start bots now

```bash
cd /home/samba/share/slomix_discord

# 0. Pre-flight (read-only, ~10s) — see §4 for what to expect
ssh -i ~/.ssh/etlegacy_bot -p 48101 et@puran.hehe.si \
  'grep -E "g_filterBan|g_banIPs" etlegacy-v2.83.1-x86_64/etmain/vektor.cfg; \
   grep -Ei "MinBots|MaxBots|SaveConfigChanges" \
   etlegacy-v2.83.1-x86_64/legacy/omni-bot/et/user/omni-bot.cfg'

# 1. Launch (overlay over the running production server)
python3 tools/slomix_rcon.py testmode on            # optional: --map supply

# 2. Verify after ~30-60s
python3 tools/slomix_rcon.py testmode status         # omnibot_enable=1, hostname [TEST]
python3 tools/slomix_rcon.py cmd "status"            # see ^o[BOT]^7 players

# 3. Stop / restore production
python3 tools/slomix_rcon.py testmode off            # exec vektor.cfg
#    OR do nothing — the 20:00 cron kill restores production automatically
```

Kill-switch if anything misbehaves: `python3 tools/slomix_rcon.py omnibot off`.
**Never** `lua_restart` — always a full map load (c0rnp0rn8 crashes otherwise).

---

## 2. How it actually works

The server **never boots with bots**. `etdaemon.sh` always starts it in
production: `etlded.x86_64 +exec vektor.cfg` inside `screen` session `vektor`
(`omnibot_enable 0`, `g_customConfig legacy3`).

Bots are turned on **after** boot by an **overlay config** that is `exec`-ed over
the running server via RCON:

```
testmode on  →  RCON: exec seareal.cfg   (bots ON, test config)
testmode off →  RCON: exec vektor.cfg    (production restored)
```

`seareal.cfg` (lives on the server at `etmain/seareal.cfg`) sets:
`g_customConfig "legacy3bot"` (competitive, no warmup/ready), `omnibot_enable 1`,
`g_gametype 3` (stopwatch), `timelimit 8`, hostname `^1[TEST]^7 purans.only`,
`bot minbots/maxbots 6`, and a hand-rolled stopwatch mapcycle (no match system —
odd `t#` = R1 `map`, even `t#` = R2 `map_restart 0` side-swap).

### Live mapcycle (6 maps × 2 rounds = 12 entries)

`etl_adlernest → supply → sw_goldrush_te → etl_sp_delivery → te_escape2 →
etl_frostbite` (loops). Starts on `sw_goldrush_te` (`vstr t6`).

> **`et_brewdog`, `etl_ice`, `erdenberg_t2`, `braundorf_b4` were removed** — bots
> don't engage in combat there, producing empty stats files. Do not re-add
> without verified waypoints.

---

## 3. `tools/slomix_rcon.py` subcommands

| Command | Effect |
|---|---|
| `testmode on [--map X]` | **Primary**: `exec seareal.cfg` — full bot test overlay |
| `testmode off` | `exec vektor.cfg` — restore production |
| `testmode status` | read `omnibot_enable`, `sv_hostname`, `g_gametype`, `timelimit` |
| `omnibot on --min 6 --max 8` / `off` | only bot cvars over current config (no mapcycle change) |
| `scrim on [--auto-ready] [--map X]` / `off` | 6 bots + `exec bot_scrim_mapcycle.cfg` + match cvars |
| `cmd "<rcon>"` | one-off RCON (e.g. `cmd "status"`, `cmd "map_restart 0"`) |
| `botnames [--limit 24]` | regenerate `server/omnibot/et_botnames_ext.gm` from `player_aliases` DB |

RCON config comes from `.env` (`RCON_HOST`, `RCON_PORT=27960`, `RCON_PASSWORD`).
`botnames` also needs `DB_*` in `.env`.

---

## 4. Server reference (verified live 2026-05-19)

| Item | Value |
|---|---|
| Host | `puran.hehe.si` (DNS fallback IP `91.185.207.163`) |
| SSH | `ssh -i ~/.ssh/etlegacy_bot -p 48101 et@puran.hehe.si` |
| Game install | `/home/et/etlegacy-v2.83.1-x86_64/` |
| Binary / session | `etlded.x86_64` in `screen` `vektor`, pinned `taskset -c 0,1` |
| Watchdog | `etdaemon.sh` (re-checks every 1 min, auto-restart) |
| Boot | crontab `@reboot /home/et/start.sh` → `etdaemon.sh` |
| Daily restart | crontab `0 20 * * * kill $(pidof …/etlded.x86_64)` → daemon restarts in **production** |
| Prod config | `etmain/vektor.cfg` (`g_customConfig legacy3`, `omnibot_enable 0`) |
| RCON | UDP port 27960, password `glavni123` (in `vektor.cfg` + `.env`) |
| `g_filterBan` / `g_banIPs` | `"1"` / `""` — **safe** (see §5) |
| Bot config | `legacy/omni-bot/et/user/omni-bot.cfg` (`MinBots`/`MaxBots`, `SaveConfigChanges=1`) |
| Bot names | `legacy/omni-bot/et/scripts/et_botnames_ext.gm` (prefix `^o[BOT]^7`, 11 names) |
| `legacy3bot.config` | `etmain/configs/legacy3bot.config` (required by `seareal.cfg`) |
| Box | 32 cores; game pinned to 0,1; idle load is normal |

Pre-flight expectation: `g_filterBan "1"`, `g_banIPs ""`, `omni-bot.cfg`
`MinBots = 6` & `MaxBots = 6` (or any value ≥ 1).

> **Repo note**: `server/omnibot/` (`seareal.cfg`, `et_botnames_ext.gm`,
> `bot_scrim_mapcycle.cfg`) is **gitignored** (`.gitignore:296 /server/`) — these
> are local working copies of server-side operational files, intentionally not
> committed. Keep the local copy in sync with the server by hand
> (`scp` from `etmain/`), then `sha256sum` to confirm.

---

## 5. Critical safety — two incidents to never repeat

### 5.1 The `g_filterBan` lockout (Feb 3–4, 2026)

Setting `g_filterBan 0` (blacklist mode) with an **empty** `g_banIPs` makes
ET:Legacy interpret it as **"ban everyone"** — 24h+ total lockout, admin included.

- `g_filterBan 0` = blacklist; `g_filterBan 1` = whitelist.
- **Always verify `g_filterBan "1"` before enabling bots.** (Live = `1` ✅.)
- Fix if ever wrong: SSH in, set `g_filterBan "1"`, restart (kill + daemon).

### 5.2 The `omni-bot.cfg` MinBots=0 override (Apr 3, 2026)

`legacy/omni-bot/et/user/omni-bot.cfg` had `MinBots=0` / `MaxBots=0`, which
**overrides** `seareal.cfg`'s `bot minbots 6` — bots never spawn. Because
`SaveConfigChanges = 1`, omni-bot can rewrite that file back to `0` on shutdown,
so this can silently regress. **Always pre-flight it** (§1 step 0).

If `MinBots`/`MaxBots` are `0`, fix before launching:

```bash
ssh -i ~/.ssh/etlegacy_bot -p 48101 et@puran.hehe.si \
  "sed -i 's/^MinBots .*/MinBots                        = 6/;
           s/^MaxBots .*/MaxBots                        = 6/' \
   etlegacy-v2.83.1-x86_64/legacy/omni-bot/et/user/omni-bot.cfg"
```

(Live on 2026-05-19 = `6/6` ✅ — not currently regressed.)

---

## 6. Rollback / recovery

| Situation | Action |
|---|---|
| Normal stop | `python3 tools/slomix_rcon.py testmode off` (or wait for 20:00 cron) |
| Bots misbehaving | `python3 tools/slomix_rcon.py omnibot off` (MinBots/MaxBots -1, enable 0) |
| RCON unresponsive | SSH in: `kill $(pidof /home/et/etlegacy-v2.83.1-x86_64/etlded.x86_64)` — daemon restarts production in ~1 min |
| Server broken | SSH: restore `etmain/vektor.cfg` from backup, then kill etlded |

Immediate-disable triggers: server crash/restart loop, "excluded from server"
error, Lua webhook entity crash, RCON timeout, CPU > 90%, humans can't join,
bot names missing in-game.

---

## 7. Stats pipeline integration

1. Bots play R1, then R2 (`map_restart 0` side-swap).
2. ET:Legacy dumps stats files to `/home/et/etlegacy*/.../stats/` (`R1`/`R2`).
3. `endstats_monitor` task loop (SSH poll) picks them up.
4. `bot/community_stats_parser.py` processes R1+R2 (R2 differential — never
   recalculate it).
5. Rows land in PostgreSQL; Discord/website query them.

Bot rows carry the `^o[BOT]^7` prefix:

```sql
-- count recent bot rows
SELECT COUNT(*) FROM player_comprehensive_stats
WHERE player_name LIKE '%[BOT]%' AND created_at > NOW() - INTERVAL '2 hours';

-- parser health (should be 0)
SELECT COUNT(*) FROM player_comprehensive_stats
WHERE player_name = 'unknown' OR player_guid IS NULL;
```

Proximity data lands under `~/.etlegacy/legacy/proximity/` on the server —
useful to `ls` there after a bot session to confirm the pipeline produced output.

Notes: bots keep consistent GUIDs across games; regenerating bot names mid-test
creates separate historical records; bots in one match share `gaming_session_id`.

---

## 8. Lua webhook & bots

`vps_scripts/stats_discord_webhook.lua` (v1.7.0) wraps entity field access in a
safe getter with `pcall` (since v1.6.0) — fixes the historical
`tried to get invalid gentity field pers.connected` crash with bot entities.
If a crash like that recurs, confirm the safe getter is present before anything
else.

---

## 9. Waypoint reality

Bots only play well on well-waypointed maps. The live 6-map rotation is the
curated set that actually produces combat/stats. Maps removed for poor bot
behaviour (empty stats): `et_brewdog`, `etl_ice`, `erdenberg_t2`,
`braundorf_b4`. Don't re-add without verifying waypoints on the server
(`find /home/et/etlegacy-v2.83.1-x86_64/legacy/omni-bot -name '*.way' -o -name '*.nav'`)
or by spawning 2 bots and observing.

---

## 10. File reference

| File | Purpose | Location | Git |
|---|---|---|---|
| `slomix_rcon.py` | unified RCON / bot control CLI | `tools/slomix_rcon.py` | tracked |
| `seareal.cfg` | bot test overlay (test mode) | server `etmain/`; local `server/omnibot/` | **gitignored** |
| `bot_scrim_mapcycle.cfg` | scrim-mode mapcycle | server `etmain/`; local `server/omnibot/` | **gitignored** |
| `et_botnames_ext.gm` | bot names (11, `^o[BOT]^7`) | server `legacy/omni-bot/et/scripts/`; local `server/omnibot/` | **gitignored** |
| `omni-bot.cfg` | MinBots/MaxBots, SaveConfigChanges | server `legacy/omni-bot/et/user/` | server-only |
| `vektor.cfg` | production server config | server `etmain/` | server-only |
| `community_stats_parser.py` | R1/R2 differential parser | `bot/community_stats_parser.py` | tracked |
| `stats_discord_webhook.lua` | real-time stats webhook | `vps_scripts/` | tracked |
| (archived) `omnibot_toggle.py` etc. | superseded by `slomix_rcon.py` | `scripts/archive/` | tracked |

---

## Document history

| Date | Change |
|---|---|
| 2026-02-15 | Initial dry-run plan |
| 2026-05-19 | Rewritten: LIVE status, `tools/slomix_rcon.py`/`python3`, live 6-map rotation, `/server/` gitignore note, MinBots/SaveConfigChanges drift + sed fix, trimmed aspirational scaffolding |
