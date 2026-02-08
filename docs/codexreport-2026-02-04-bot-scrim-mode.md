# Codex Report — Bot-Only Scrim Mode (2026-02-04)

## What I set up
- Added a generator that builds Omni-bot names from **most recently active** players (with a `[BOT]` prefix).
- Added a `bot_scrim_mode.py` helper to toggle **3v3 bot-only scrims** via RCON.
- Generated a starter `et_botnames_ext.gm` in `server/omnibot/` (fallback-only because DB access is blocked in this environment).

## Files Added/Updated
- `scripts/generate_omnibot_botnames.py`
- `scripts/bot_scrim_mode.py`
- `server/omnibot/et_botnames_ext.gm`
- `server/omnibot/bot_scrim_mapcycle.cfg`

## Map Rotation (Bot Scrim)
Added a dedicated mapcycle file (uploaded to server):
```
/home/et/etlegacy-v2.83.1-x86_64/etmain/bot_scrim_mapcycle.cfg
```
Rotation order (as provided):
1. etl_adlernest
2. supply
3. etl_sp_delivery
4. te_escape2
5. te_escape2
6. sw_goldrush_te
7. et_brewdog
8. etl_frostbite
9. erdenberg_t2
10. braundorf_b4
11. etl_adlernest

Note: I assumed **te_escape2 twice**. If you want it **3x**, tell me and I’ll update the mapcycle.

## How to regenerate with real DB names
Run on a machine that can reach Postgres:
```bash
python3 scripts/generate_omnibot_botnames.py --limit 24
```
This pulls the latest alias per GUID, sorts by `last_seen`, and builds a GM file with:
- `BotPrefix = ^o[BOT]^7`
- Axis + Allied names distributed across classes
- Fallback list if DB is short/unavailable

## How to deploy to the game server
Target file on server:
```
/home/et/etlegacy-v2.83.1-x86_64/legacy/omni-bot/et/scripts/et_botnames_ext.gm
```
Recommended approach (from this repo):
```bash
ssh -i ~/.ssh/etlegacy_bot -p 48101 et@puran.hehe.si \
  "cat > /home/et/etlegacy-v2.83.1-x86_64/legacy/omni-bot/et/scripts/et_botnames_ext.gm" \
  < server/omnibot/et_botnames_ext.gm
```

Then reload Omni-bot:
- `map_restart 0`
- or toggle: `omnibot_enable 0` then `omnibot_enable 1`
- or a full map change

## Bot-only 3v3 scrim mode
Enable:
```bash
python3 scripts/bot_scrim_mode.py on --auto-ready
```
Disable:
```bash
python3 scripts/bot_scrim_mode.py off
```

Notes:
- `--auto-ready` tries `ref allready` + `map_restart 0`.
- If stopwatch doesn’t start, use `ref allready` or `ref startmatch` manually.
- `bot MinBots 6` + `bot MaxBots 6` keeps it 3v3.
- `bot_scrim_mode.py on` now runs `exec bot_scrim_mapcycle.cfg` and starts at `scrim_d1`.
- Use `--keep-map` to avoid forcing a map change when enabling.
- `bot_scrim_mode.py on` also sets `match_readypercent 0` and `match_minplayers 0` so rounds auto-start.
- `bot_scrim_mode.py off` restores `match_readypercent 100` and `match_minplayers 2`.

## Stopwatch side swapping
Stopwatch swaps sides automatically **as long as the round actually starts**.
The only risk is when nobody “readies up.” Bots don’t ready, so we use `ref allready`
to force the match start.

## Test Enable (2026-02-04)
Attempted RCON from this environment failed due to UDP restrictions/timeouts.
I enabled bot scrim mode by sending RCON locally on the server (via SSH),
including mapcycle exec + `vstr scrim_d1` + `ref allready` + `map_restart 0`.

## BOT tag in names
Set via:
```
global BotPrefix = "^o[BOT]^7";
```
This makes every bot show with a `[BOT]` tag before the fake nick.

## Known limitation (this environment)
DB access from this sandbox is blocked, so the generated `server/omnibot/et_botnames_ext.gm` currently uses the fallback list:
`SuperBoyy, Olympus, lagger, carniee, wajs, bronze, vid, ...`

Run the generator on a machine with DB access to replace it.
