# Omni-bot Enable/Disable Plan + Implementation (2026-02-04)

## Goal
Use Omni-bot to generate data during quiet hours, with a **fast disable path** when humans want to play.

## What Was Done
- Verified `omnibot_enable` in server config:
  - `/home/et/etlegacy-v2.83.1-x86_64/etmain/vektor.cfg` → `set omnibot_enable "0"`
- Confirmed Omni-bot binaries + nav/goals exist:
  - `/home/et/etlegacy-v2.83.1-x86_64/legacy/omni-bot/`
- Added **server-side Omni-bot config** and deployed:
  - Repo template: `docs/OMNIBOT_CONFIG.cfg`
  - Server path: `/home/et/etlegacy-v2.83.1-x86_64/legacy/omni-bot/et/user/omni-bot.cfg`
- Added **RCON helper scripts**:
  - `scripts/rcon_command.py`
  - `scripts/omnibot_toggle.py`

## Enable / Disable Flow
### Enable (example)
```
python3 scripts/omnibot_toggle.py on --min 6 --max 8
```
This sends:
- `set omnibot_enable 1`
- `bot MinBots 6`
- `bot MaxBots 8`
- `bot BalanceTeams 1`
- `bot BotTeam -1`
- `bot HumanTeam 1`
- `bot BotsPerHuman 3`

### Disable
```
python3 scripts/omnibot_toggle.py off
```
This sends:
- `bot MinBots -1`
- `bot MaxBots -1`
- `bot BotTeam -1`
- `set omnibot_enable 0`

## Notes / Behavior
- Omni-bot uses `omni-bot.cfg` for defaults; RCON `/bot` commands can override and persist if `SaveConfigChanges=1`.
- `omnibot_enable` may require a map restart on some builds.
- If RCON from this machine times out, run the script from a host that can reach UDP 27960.

## Config Defaults (Deployed)
```
[ServerManager]
MaxBots = -1
MinBots = -1
BalanceTeams = 1
SaveConfigChanges = 1
CountSpectators = 0
SleepBots = 1

[Difficulty]
CurrentDifficulty = 4
AdjustAim = 1

[CombatMovement]
moveskill = 3

[Versus]
BotTeam = -1
HumanTeam = 1
BotsPerHuman = 3
```

## Files Added / Updated
- `docs/OMNIBOT_CONFIG.cfg`
- `scripts/omnibot_toggle.py`
- `docs/codexreport-2026-02-04-omnibot.md`
- `docs/SESSION_2026-02-03_CHANGELOG_LOCAL.md`

## Manual Steps (If Needed)
- RCON map restart (if bots don’t show):
  - `python3 scripts/rcon_command.py "map_restart 0"`

