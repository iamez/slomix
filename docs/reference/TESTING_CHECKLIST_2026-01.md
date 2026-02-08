# Testing Checklist for Recent Updates

Based on commits since `ffad15d`, here's what to watch for in your next game session.

---

## CRITICAL - Test First

### 1. Lua Webhook Real-Time Stats (NEW FEATURE)
**What it does:** Sends stats notification to Discord instantly when round ends (vs 60-second polling)

| Test Scenario | What to Watch For |
|--------------|-------------------|
| **Normal round completion** | Webhook appears in control channel ~1-3 sec after round ends |
| **Team surrenders** | `Lua_Playtime` shows ACTUAL time (e.g., "245 sec"), NOT full map time |
| **Multiple pauses** | `Lua_Pauses` shows count and total (e.g., "2 (60 sec)") |
| **Team composition** | `Axis`/`Allies` fields show player names |
| **Warmup tracking (v1.2.0)** | `Lua_Warmup` shows pre-round warmup (e.g., "45 sec") |
| **Warmup Unix (v1.2.0)** | `Lua_WarmupStart` shows timestamp when warmup started |
| **Warmup End (v1.3.0)** | `Lua_WarmupEnd` shows timestamp when warmup ended |
| **Pause events (v1.3.0)** | `Lua_Pauses_JSON` shows individual pause timestamps |
| **Timing legend (v1.3.0)** | Embed description explains Playtime vs Warmup vs Wall-clock |

**If webhook doesn't appear:** Check server console for Lua errors, verify webhook URL in config

---

### 2. Bug Fixes to Verify

| Command | Previous Bug | Expected Now |
|---------|-------------|--------------|
| `!last_session graphs` | Crashed on `None` player names | Graphs generate, shows GUID or "Player_0" fallback if needed |
| `!automation_status` | Crashed if no backups ran yet | Shows "Last: Never" gracefully |
| `!admin_audit` | Database parameter error | Returns audit log correctly |

---

## HIGH - Test Next

| Test | How |
|------|-----|
| Admin permission enforcement | Try `!backup_db` as non-admin (should be blocked) |
| `!session [date] maps full` | Verify "full" flag triggers expanded view |
| Season leader in `!stats` | Check bottom of stats output shows correct leader |

---

## Quick Reference: What Changed

```
e0010fc - Lua webhook documentation
4ee9609 - Lua webhook feature (real-time stats notification)
de29ba6 - Fix None player names in graphs
6a1b454 - Fix !automation_status and !admin_audit crashes
ffad15d - Add missing @is_admin decorators, fix session maps command
```

---

## Key Files Modified

- `vps_scripts/stats_discord_webhook.lua` - New Lua script on game server
- `bot/ultimate_bot.py` - Webhook handler (`_process_stats_ready_webhook()`)
- `bot/cogs/automation_commands.py` - Admin decorator fixes
- `bot/services/session_graph_generator.py` - Graph None-name fix (line 172)

---

## Most Important Test

**Surrender Duration** - This was the whole reason for the Lua webhook:
1. Start a round
2. Play 3-5 minutes
3. One team surrenders
4. Check webhook shows actual duration (~3-5 min), NOT full map time (20 min)

If this works correctly, the feature is working as intended.

---

## Lua Webhook Technical Details (v1.3.0)

**IMPORTANT: Naming Convention**
All fields from our webhook use `Lua_` prefix to distinguish from stats file (oksii lua) data:

| Field | Format | Description |
|-------|--------|-------------|
| `Map`, `Round` | text, int | Map name and round number |
| `Winner`, `Defender` | int | Team IDs (1=Axis, 2=Allies) |
| `Lua_Playtime` | "847 sec" | Actual playtime excluding pauses |
| `Lua_Timelimit` | "20 min" | Configured map time |
| `Lua_Pauses` | "2 (120 sec)" | Pause count and total pause time |
| `Lua_Pauses_JSON` | JSON array | Individual pause timestamps (v1.3.0) |
| `Lua_EndReason` | text | "objective" / "surrender" / "time_expired" |
| `Lua_Warmup` | "45 sec" | Pre-round warmup duration |
| `Lua_RoundStart` | Unix timestamp | When GS_PLAYING began |
| `Lua_RoundEnd` | Unix timestamp | When GS_INTERMISSION began |
| `Lua_WarmupStart` | Unix timestamp | When warmup phase began |
| `Lua_WarmupEnd` | Unix timestamp | When warmup ended (v1.3.0) |
| `Axis`, `Allies` | text | Player name lists |
| `Axis_JSON`, `Allies_JSON` | JSON | Full player data with GUIDs |

**v1.3.0 Pause Events Format:**
```json
[{"n":1,"start":1737752100,"end":1737752130,"sec":30},...]
```

**Embed Description (v1.3.0):**
The webhook includes a timing legend:
- Playtime = actual gameplay (pauses excluded)
- Warmup = waiting before round
- Wall-clock = WarmupStart→RoundEnd

**Bot-Side Aggregation:**
The bot can compute from timestamps:
- **Intermission** = R2.Lua_WarmupStart - R1.Lua_RoundEnd
- **Map total playtime** = R1.Lua_Playtime + R2.Lua_Playtime
- **Map total warmup** = R1.Lua_Warmup + R2.Lua_Warmup
- **Session totals** = Sum across all rounds

**Database Storage:**
All webhook data stored in `lua_round_teams` table (separate from stats file data in `rounds` table).

| Column | Added |
|--------|-------|
| `lua_warmup_seconds`, `lua_warmup_start_unix` | v1.2.0 |
| `lua_pause_events` (JSONB) | v1.3.0 |

See: `docs/reference/TIMING_DATA_SOURCES.md` for complete timing documentation.

The bot's `_process_stats_ready_webhook()` method parses this and triggers stats processing.

---

## Troubleshooting

### Webhook Not Appearing
1. SSH to game server
2. Check `/home/gameserver/ET/etmain/luamods.log` for errors
3. Verify `stats_discord_webhook.lua` is loaded (look for startup message)
4. Test webhook URL with curl:
   ```bash
   curl -X POST -H "Content-Type: application/json" \
     -d '{"content":"test"}' \
     "YOUR_WEBHOOK_URL"
   ```

### Graphs Still Crashing
1. Check bot logs for matplotlib errors
2. Verify `session_graph_generator.py` has the fallback fix on line 172
3. Look for player records with NULL player_name in database

### Admin Commands Blocked for Admins
1. Verify DISCORD_ADMIN_IDS in `.env` includes your Discord ID
2. Check `is_admin()` decorator is present on command
3. Restart bot after config changes
