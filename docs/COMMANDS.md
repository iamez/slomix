# Bot Commands Reference

Complete command reference for the Enemy Territory Stats Discord Bot.

---

## 📊 Player Statistics Commands

### `!stats [player]`
Get detailed player statistics.

**Usage:**
```
!stats                    # Your own stats (if linked)
!stats seareal            # Specific player by name
!stats @Username          # Mentioned Discord user's stats
```

**Shows:**
- Total kills, deaths, K/D ratio
- Accuracy percentage
- Damage given/received
- XP breakdown (combat, objective, support)
- Rounds played
- Favorite weapons

---

### `!ping`
Check bot responsiveness and latency.

**Usage:**
```
!ping
```

**Shows:**
- Bot latency in milliseconds
- Database connection status

---

### `!compare <player1> <player2>`
Compare stats between two players.

**Usage:**
```
!compare seareal BrewDog
!compare @User1 @User2
```

**Shows:**
- Side-by-side K/D comparison
- Accuracy differential
- Damage statistics
- XP comparison
- Head-to-head metrics

---

### `!check_achievements [player]`
View achievement progress and unlocked achievements.

**Aliases:** `!check_achivements`, `!check_achievement`

**Usage:**
```
!check_achievements
!check_achievements seareal
```

**Shows:**
- Unlocked achievements with timestamps
- Progress toward locked achievements
- Total achievement points

---

### `!season_info`
Display current season information.

**Aliases:** `!season`, `!seasons`

**Usage:**
```
!season_info
```

**Shows:**
- Current season name and dates
- Season statistics
- Top players this season

---

### `!help_command`
Display all available commands with categories.

**Aliases:** `!commands`

**Usage:**
```
!help_command
```

**Shows:**
- Commands organized by category
- Brief description of each command
- Usage examples

---

## 🏆 Leaderboard Commands

### `!leaderboard [stat]`
View rankings and leaderboards.

**Aliases:** `!lb`, `!top`

**Usage:**
```
!leaderboard              # Overall K/D leaderboard
!leaderboard kd           # K/D ratio rankings
!leaderboard kills        # Most kills
!leaderboard accuracy     # Highest accuracy
!leaderboard damage       # Most damage dealt
!leaderboard xp           # Most XP earned
!leaderboard headshots    # Most headshots
!leaderboard revives      # Most revives (medic)
```

**Shows:**
- Top 10 players for selected stat
- Your rank if you're linked
- Statistics for each ranked player

---

## 🎮 Session Commands

### `!last_session`
Generate comprehensive analytics for the most recent gaming session.

**Aliases:** `!last`, `!latest`, `!recent`, `!last_round`

**Usage:**
```
!last_session
```

**Generates 6 Graphs:**
1. **Player Performance** - K/D, accuracy, damage per player
2. **Weapon Analysis** - Usage distribution, accuracy by weapon
3. **Map Breakdown** - Rounds played per map
4. **Kill Metrics** - Total kills, deaths, revives
5. **Team Analysis** - Axis vs Allies performance
6. **Time-based Metrics** - XP gain, damage over time

**Shows:**
- Session summary (date, duration, total rounds)
- Top performers
- Map rotation
- Team balance
- MVP of the session

---

### `!session <number>`
View detailed statistics for a specific session.

**Aliases:** `!match`, `!game`

**Usage:**
```
!session 42               # Session #42
!session latest           # Latest session
```

**Shows:**
- Session metadata (date, duration, rounds)
- Player roster
- Map rotation
- Team assignments
- Round-by-round results

---

### `!sessions`
List recent gaming sessions.

**Aliases:** `!rounds`, `!list_sessions`, `!ls`

**Usage:**
```
!sessions                 # Last 10 sessions
!sessions 20              # Last 20 sessions
```

**Shows:**
- Session ID
- Date and time
- Duration
- Number of rounds
- Maps played
- Player count

---

### `!team_history`
View team assignment history for a player.

**Usage:**
```
!team_history seareal
!team_history @Username
```

**Shows:**
- Round-by-round team assignments (Axis/Allies)
- Team switches within sessions
- Time spent on each team
- Team balance statistics

---

## 🎯 Team Commands

### `!teams`
View team assignments for the last round.

**Usage:**
```
!teams
```

**Shows:**
- Axis roster with stats
- Allies roster with stats
- Team scores
- Team balance metrics

---

### `!set_team_names <axis_name> <allies_name>`
Set custom team names for a session.

**Usage:**
```
!set_team_names "Red Devils" "Blue Angels"
!set_team_names Attackers Defenders
```

**Shows:**
- Confirmation of team names
- Updated session display

---

### `!lineup_changes`
Track player movements between teams.

**Usage:**
```
!lineup_changes
```

**Shows:**
- Players who switched teams
- Number of switches
- Balance impact

---

### `!session_score`
View aggregate team scores across a session.

**Usage:**
```
!session_score
```

**Shows:**
- Total Axis wins
- Total Allies wins
- Win percentage per team
- Round breakdown

---

## 🔗 Player Linking Commands

### `!link`
Link your Discord account to your ET player name/GUID.

**Usage:**
```
!link
```

**Interactive Process:**
1. Bot shows recent players
2. You select your player number
3. Link is created
4. Your stats are now accessible via @mention

**Benefits:**
- `!stats` works without typing name
- Others can use `!stats @you`
- Leaderboards show your rank
- Achievement tracking

---

### `!unlink`
Remove link between Discord and ET player.

**Usage:**
```
!unlink
```

**Shows:**
- Confirmation of unlink
- You'll need to re-link to use @mention features

---

### `!list_players`
Search and browse all players in database.

**Aliases:** `!players`, `!lp`

**Usage:**
```
!list_players             # All players (paginated)
!list_players seareal     # Search for "seareal"
!list_players brew        # Partial match: "brewdog", "brewery", etc.
```

**Shows:**
- Player names
- Total rounds played
- Last seen date
- Link status (if Discord-linked)

---

### `!find_player <name>`
Find a specific player and their details.

**Aliases:** `!findplayer`, `!fp`, `!search_player`

**Usage:**
```
!find_player seareal
!find_player brew
```

**Shows:**
- Exact matches
- Similar names
- Player GUIDs
- Stats summary
- Link status

---

### `!select <number>`
Select a player from a list (used after !list_players).

**Usage:**
```
!list_players seareal
!select 1                 # Select first result
```

**Shows:**
- Confirmation of selection
- Next step (usually for linking)

---

## 🔄 Sync & Import Commands

### `!sync_stats`
Manually trigger stats file import from local directory.

**Aliases:** `!syncstats`, `!sync_logs`

**Usage:**
```
!sync_stats
```

**Process:**
1. Scans `LOCAL_STATS_PATH` directory
2. Identifies new files (not yet imported)
3. Parses stats files
4. Imports to database
5. Calculates R2 differentials
6. Groups into gaming sessions

**Shows:**
- Files found
- Files imported
- Errors (if any)
- Import summary

---

### `!sync_today`
Import only today's stats files.

**Aliases:** `!sync1day`

**Usage:**
```
!sync_today
```

**Shows:**
- Files from today
- Import results

---

### `!sync_week`
Import last 7 days of stats files.

**Aliases:** `!sync1week`

**Usage:**
```
!sync_week
```

---

### `!sync_month`
Import last 30 days of stats files.

**Aliases:** `!sync1month`

**Usage:**
```
!sync_month
```

---

### `!sync_all`
Import ALL stats files in directory (full rebuild).

**Usage:**
```
!sync_all
```

**⚠️ Warning:** This can take several minutes for large datasets.

---

## ⚙️ Admin Commands

### `!cache_clear`
Clear bot's internal caches.

**Usage:**
```
!cache_clear
```

**Clears:**
- Stats cache
- Processed files cache
- Session cache

**Shows:**
- Confirmation
- Cache rebuild status

---

### `!reload`
Reload bot cogs without restarting.

**Usage:**
```
!reload
```

**Shows:**
- Cogs reloaded
- Errors (if any)

---

### `!weapon_diag`
Run weapon stats diagnostics.

**Usage:**
```
!weapon_diag
```

**Shows:**
- Weapon data integrity
- Missing weapon stats
- Duplicate entries

---

## 📈 Advanced Analytics

### Synergy Analytics (Experimental)

**`!synergy_analytics.py`** and **`!synergy_analytics_fixed.py`** cogs provide:
- Player synergy detection (who plays well together)
- Role normalization (medic, engineer, soldier patterns)
- Proximity tracking (who fights near who)

**Note:** These are experimental features and may not be loaded by default.

---

## 🗺️ Map & Weapon Stats

### Map Commands
```
!maps                     # List all maps with play count
!map supply               # Detailed stats for "supply" map
!map radar                # Stats for "radar" map
```

### Weapon Commands
```
!weapons                  # All weapons usage stats
!weapon thompson          # Thompson SMG statistics
!weapon mp40              # MP40 statistics
!weapon panzerfaust       # Panzerfaust stats
```

---

## 🤖 Automation Status

### `!status`
Check bot and automation system status.

**Shows:**
- Bot uptime
- Database connection
- Auto-import status (enabled/disabled)
- Last import timestamp
- Files in queue

---

### `!resync`
Force database resynchronization.

**Usage:**
```
!resync
```

**Process:**
- Clears caches
- Rebuilds processed files list
- Recalculates gaming sessions
- Refreshes all statistics

---

## 📝 Command Permissions

### Public Commands
All players can use:
- `!stats`, `!leaderboard`, `!last_session`
- `!sessions`, `!session`
- `!link`, `!unlink`, `!find_player`
- `!ping`, `!help_command`
- `!teams`, `!team_history`

### Admin Commands
Require bot admin role:
- `!sync_*` commands
- `!cache_clear`, `!reload`
- `!weapon_diag`, `!resync`
- `!set_team_names`

---

## 💡 Command Tips

### Performance Tips
- Use `!sync_today` instead of `!sync_all` for daily imports
- `!last_session` may take 10-30 seconds for large sessions (graph generation)
- Use player search (`!find_player`) before linking to verify spelling

### Data Accuracy
- Stats are calculated from game server logs
- R2 (Round 2) stats show differential from R1
- Team assignments use 5-layer detection algorithm
- Gaming sessions auto-consolidate with 12-hour gap threshold

### Troubleshooting
- If `!stats @you` doesn't work, check `!link` status
- If graphs fail, check bot has `Attach Files` permission
- For import errors, check `logs/database_manager.log`
- Use `!cache_clear` if stats seem stale

---

## 🔗 Related Documentation

- [README.md](../README.md) - Setup and installation
- [DATA_PIPELINE.md](DATA_PIPELINE.md) - How data flows through system
- [FIELD_MAPPING.md](FIELD_MAPPING.md) - What stats are tracked
- [TECHNICAL_OVERVIEW.md](TECHNICAL_OVERVIEW.md) - Technical architecture
- [DEPLOYMENT_CHECKLIST.md](../DEPLOYMENT_CHECKLIST.md) - VPS deployment guide

---

**Total Commands:** 35+  
**Command Categories:** 8  
**Bot Prefix:** `!`  
**Case Sensitive:** No
