# Live Monitoring Notes - 2026-02-03

## Status
Monitoring started. Bot log tail succeeded; game server log tail pending due to SSH auth.

## Bot Log Timeline (journalctl -u etlegacy-bot -f)
- 20:37:24 — SSH check triggered (ACTIVE players mode, 6 players in voice)
  - SSH connected, publickey auth OK, SFTP opened/closed
- 20:38:24 — SSH check triggered (ACTIVE players mode, 6 players in voice)
  - SSH connected, publickey auth OK, SFTP opened/closed
- 20:39:24 — SSH check triggered (ACTIVE players mode, 6 players in voice)
  - SSH connected, publickey auth OK, SFTP opened/closed
- 20:40:24 — SSH check triggered (ACTIVE players mode, 6 players in voice)
  - SSH connected, publickey auth OK, SFTP opened/closed

## Game Server Log Snapshot (User Provided)
- 6454250 Userinfo: multiple clients connected (c^aa^7rniee, vid, .olz, dProner2026, KomandantVarga, SuperBoyy)
- 6454350 broadcast: teams LOCKED
- 6463025 Kill: dProner killed vid (MOD_MP40)
- 6464275 Medic_Revive: SuperBoyy → vid
- 6465650 Kill: vid selfkill (MOD_SUICIDE)

## Game Server Log Tail
- Attempted: `ssh -p 48101 et@puran.hehe.si "tail -F /home/et/.etlegacy/legacy/etconsole.log"`
- Result: Permission denied (publickey,password)
- Action needed: confirm correct SSH key path or allow agent access.

## Current Action
- Switching to SSH tail with explicit key: `-i ~/.ssh/etlegacy_bot`

## Game Server Log Tail (SSH, 120s window)
Captured live activity (no errors seen in this window):
- Multiple kills, revives, item pickups logged.
- Team chat + voice lines logged.
- Legacy announces:
  - Allies captured forward bunker.
  - Axis command post constructed.
  - Depot fence constructed.
- Several selfkills (MOD_SUICIDE) observed.

Notes:
- No FastDL download failures in this segment.
- No round end / intermission lines yet in this window.

## Game Server Log Tail (SSH, 120s window #2)
Captured ongoing live activity:
- Objective destroyed: Forward spawn rear exit opened.
- Multiple selfkills observed (MOD_SUICIDE).
- Allied command post destroyed; Allied command post constructed later.
- No FastDL errors or download failures in this window.
- No round end / intermission lines yet in this window.

## Game Server Log Tail (SSH, 120s window #3)
Captured ongoing live activity:
- Allies planted Depot Gate (timer 6851275) and destroyed it (6881275).
- Allies planted East Depot Wall (6903225) and destroyed it (6933225).
- Team chat line logged: "medic - smg".
- Multiple suicides observed (pvid, c^aa rniee, dProner).
- No FastDL errors or download failures in this window.
- No round end / intermission lines yet in this window.

## Game Server Log Tail (SSH, 130s window #4)
Captured ongoing live activity:
- Allies truck in position; crane controls constructed; crane activated.
- Gold crate loaded onto the truck.
- Multiple suicides logged (c^aa rniee, .olz, dProner, pvid).
- No round end / intermission lines yet in this window.

## Game Server Log Tail (SSH, 130s window #5)
Captured ongoing live activity:
- Players reconnecting/ready states: "Proner is ready", "c^aa rniee is ready".
- WeaponStats line logged for player 5, then disconnect.
- Chat: "TO JE TO", "lol", "voice common".
- No explicit round end / intermission line in this window.

## Round End Correlation (supply R1)
- `Timelimit hit` logged at 7173650 (etconsole.log).
- `LUA event: Round ended!` logged at 7173675 (c0rnp0rn7.lua).
- `ExitLevel: executed` at 7188675 (map restart / intermission complete).
- `stats_discord_webhook.lua` shows only "Shutdown/loaded" lines; no "Sending webhook" lines present.

## Bot Restart + Log Triage (2026-02-03 21:30)
- Bot restart logged at 21:30:46; startup clean (all cogs loaded).
- No new ERROR entries after restart; prior `et_name` errors are from pre-restart.
- Current WARNINGS after restart:
  - `file_tracker`: 131 unimported files in `local_stats/`.
  - `!last_session` slow operation (~11.5s).
  - Voice session end called with `session_start_time=None` (expected after restart).

## Next Checks
- Confirm `etconsole.log` path
- Re-attempt SSH tail with correct key (likely `~/.ssh/etlegacy_bot`)
