# 📖 COMMAND REFERENCE - ET:Legacy Stats Bot
**Last Updated**: October 5, 2025  
**Bot Version**: 3.0  
**Total Commands**: 14

---

## 📋 Table of Contents

1. [Session & Statistics Commands](#session--statistics-commands)
2. [Player Statistics Commands](#player-statistics-commands)
3. [Account Linking Commands](#account-linking-commands)
4. [Leaderboard Commands](#leaderboard-commands)
5. [Utility Commands](#utility-commands)
6. [Command Aliases](#command-aliases)

---

## Session & Statistics Commands

### `!last_session`

**Description**: Shows the most recent gaming session with comprehensive details including team composition, player stats, and match results.

**Usage**:
```
!last_session
```

**Aliases**: None

**Parameters**: None

**Permissions**: Everyone

**Output**:
- Session header with date, map, round info
- Team A roster with players and stats
- Team B roster with players and stats
- Team scores
- Session MVP
- Top performers by category
- Match summary

**Example**:
```
!last_session
```

**Response**:
```
📊 Session Summary: 2025-10-02
Map: erdenberg_t2 • Round 1

👥 Team A (Allies)
   1. SuperBoyy - 543 DPM | 45K 23D
   2. qmr - 498 DPM | 38K 19D
   3. SmetarskiProner - 456 DPM | 32K 21D

👥 Team B (Axis)
   1. vid - 512 DPM | 42K 20D
   2. endekk - 489 DPM | 36K 18D
   3. .olz - 445 DPM | 30K 22D

🏆 Session MVP: SuperBoyy (543 DPM)
```

---

### `!session [date]`

**Description**: Shows full day summary for a specific date, aggregating all rounds and maps played that day.

**Usage**:
```
!session                    # Most recent session
!session 2025-10-02         # Specific date (hyphenated format)
!session 2025 10 2          # Specific date (spaced format)
```

**Aliases**: None

**Parameters**:
- `date` (optional): Date in format YYYY-MM-DD or YYYY MM DD

**Permissions**: Everyone

**Output**:
- Date header
- Total maps and rounds played
- List of all unique maps
- Top 5 players with aggregated stats (kills, deaths, K/D, DPM)
- Footer hint for !last_session

**Example**:
```
!session 2025-08-31
```

**Response**:
```
📊 Session Summary: 2025-08-31

🗓️ Date: August 31, 2025
🗺️ Maps Played: 5 maps • 10 rounds
📍 Maps: erdenberg_t2, te_escape2, Supply, radar, frost

🏆 Top Players:
🥇 vid - 156K 98D (1.59 K/D) | 512.3 DPM
🥈 carniee - 142K 87D (1.63 K/D) | 498.7 DPM
🥉 .wajs - 138K 79D (1.75 K/D) | 476.2 DPM
4️⃣ endekk - 129K 91D (1.42 K/D) | 445.8 DPM
5️⃣ .olz - 121K 85D (1.42 K/D) | 432.1 DPM

💡 Use !last_session for the most recent session with full details
```

**Recent Changes** (Session 7):
- ✅ Fixed to show full day aggregation (was showing single round)
- ✅ Now accepts spaced date format: `2025 8 31`
- ✅ Calculates weighted DPM across all rounds
- ✅ Shows all unique maps played

---

### `!sessions [month]`

**Description**: Lists all gaming sessions with filtering options by month.

**Usage**:
```
!sessions                   # All sessions
!sessions october           # Filter by month name
!sessions oct               # Filter by month abbreviation
!sessions 10                # Filter by month number
!sessions 2025-10           # Filter by year-month
```

**Aliases**: `!list_sessions`, `!ls`

**Parameters**:
- `month` (optional): Month name, abbreviation, number, or YYYY-MM format

**Permissions**: Everyone

**Output**:
- Title with month filter (if applied)
- List of sessions (most recent first)
- Each session shows:
  - Date
  - Number of maps
  - Number of rounds
  - Number of players
  - Duration (first to last round)
- Total session count
- Footer with page navigation (if multiple pages)

**Example**:
```
!sessions october
```

**Response**:
```
📅 Gaming Sessions - October 2025

📆 October 5, 2025
   🗺️ 6 maps • 12 rounds
   👥 8 players
   ⏱️ Duration: 3h 15m

📆 October 2, 2025
   🗺️ 10 maps • 20 rounds
   👥 6 players
   ⏱️ Duration: 4h 45m

📆 October 1, 2025
   🗺️ 4 maps • 8 rounds
   👥 7 players
   ⏱️ Duration: 2h 30m

📊 Total: 3 sessions in October 2025
```

**Month Formats Supported**:
- Full name: `january`, `february`, ..., `december`
- Abbreviation: `jan`, `feb`, ..., `dec`
- Number: `1`, `2`, ..., `12` (auto-pads to `01`, `02`, etc.)
- Year-Month: `2025-10`

**Added**: Session 7 (October 5, 2025)

---

## Player Statistics Commands

### `!stats [player/@mention]`

**Description**: Displays comprehensive player statistics including combat stats, team play, and performance metrics.

**Usage**:
```
!stats                      # Your own stats (if linked)
!stats vid                  # Search by player name
!stats @vid                 # Search by Discord mention
```

**Aliases**: None

**Parameters**:
- `player` (optional): Player name or @mention

**Permissions**: Everyone

**Output**:
- Player profile header (name, GUID, aliases)
- Combat statistics (K/D, DPM, accuracy, headshots)
- Team play statistics (revives, assists, dynamites, objectives)
- Performance metrics (games played, playtime, XP, efficiency)
- Best achievements (killing sprees, multikills)
- Last seen date and map

**Example**:
```
!stats @vid
```

**Response**:
```
📊 ET:Legacy Stats for @vid

Player: vid (GUID: D8423F90)
Also known as: v1d, vid-slo

🎯 Combat Stats
   Kills: 18,234 | Deaths: 12,456 | K/D: 1.46
   Damage: 2,345,678 | DPM: 342.5
   Accuracy: 23.4% | Headshots: 2,341

🎖️ Team Play
   Revives Given: 3,456
   Assists: 1,890
   Dynamites Planted: 234
   Objectives Completed: 145

📈 Performance
   Games Played: 1,462
   Time Played: 234h 12m
   XP: 1,234,567
   Efficiency: 67.8%

🏆 Best Achievements
   Best Spree: 23 kills
   Double Kills: 456
   Triple Kills: 123
   Quad Kills: 34

📅 Last Seen
   2025-10-02 playing te_escape2
```

**Notes**:
- If not linked, shows "You haven't linked your account" with linking instructions
- @mention support searches player_links table for instant lookup
- Name search includes alias detection

---

### `!list_players [filter]`

**Description**: Lists all players with their Discord link status, statistics, and activity.

**Usage**:
```
!list_players               # All players
!list_players linked        # Only linked players
!list_players unlinked      # Only unlinked players
!list_players active        # Active last 30 days
```

**Aliases**: `!players`, `!lp`

**Parameters**:
- `filter` (optional): `linked`, `unlinked`, or `active`

**Permissions**: Everyone

**Output**:
- Title with filter (if applied)
- Player list with:
  - Link status icon (🔗 linked, ❌ unlinked)
  - Player name and GUID
  - Discord mention (if linked)
  - K/D ratio
  - Sessions played
  - Last seen (Xd ago format)
- Total player count

**Example**:
```
!list_players linked
```

**Response**:
```
👥 Linked Players (12)

🔗 vid (D8423F90)
   Discord: @vid
   K/D: 1.46 | Sessions: 145
   Last seen: 3d ago

🔗 carniee (0A26D447)
   Discord: @carniee
   K/D: 1.38 | Sessions: 132
   Last seen: 1d ago

🔗 .olz (D8423F91)
   Discord: @olz
   K/D: 1.29 | Sessions: 128
   Last seen: 3d ago

...

📊 Total: 12 linked players
```

**Filter Types**:
- `linked` / `link`: Players with Discord accounts linked
- `unlinked` / `nolink`: Players without Discord accounts linked
- `active`: Players who played in last 30 days (any link status)

**Added**: Session 7 (October 5, 2025)

**Bug Fixes**:
- Fixed db_path reference (self.bot.db_path)
- Fixed discord_id column with player_links JOIN

---

## Account Linking Commands

### `!link [name/GUID/@user]`

**Description**: Links your Discord account to an ET:Legacy player GUID for personalized stats.

**Usage**:
```
!link                       # Interactive linking (shows top 3 matches)
!link carniee               # Link by player name
!link D8423F90              # Link by GUID
!link @user D8423F90        # Admin linking (requires Manage Server permission)
```

**Aliases**: None

**Parameters**:
- No parameters: Interactive mode with suggestions
- `name`: Player name to search
- `GUID`: 8-character hex GUID
- `@user GUID`: Admin linking for another user

**Permissions**:
- Everyone: Self-linking
- Manage Server: Admin linking

**Output**:

**Interactive Mode**:
- Shows top 3 unlinked GUIDs with stats preview
- Reaction buttons (1️⃣2️⃣3️⃣) to select
- 60-second timeout

**Name Search**:
- Shows matching players
- Reaction buttons to confirm
- Shows aliases and stats preview

**Direct GUID**:
- Shows player profile
- Confirmation with ✅/❌ reactions
- Links on confirmation

**Admin Mode**:
- Shows player profile
- Admin confirmation required
- Links target user to GUID
- Logs admin action

**Example (Interactive)**:
```
!link
```

**Response**:
```
🔍 Link Your Account

Found 3 potential matches!

1️⃣ vid (D8423F90)
   Also known as: v1d, vid-slo
   18,234 kills | 12,456 deaths | K/D: 1.46
   Played 145 games | Last: 2025-10-02

2️⃣ carniee (0A26D447)
   Also known as: carn, carn1
   15,678 kills | 11,234 deaths | K/D: 1.40
   Played 132 games | Last: 2025-10-03

3️⃣ .olz (D8423F91)
   12,345 kills | 9,876 deaths | K/D: 1.25
   Played 128 games | Last: 2025-10-02

React with 1️⃣/2️⃣/3️⃣ to select (60s)
```

**Example (Admin)**:
```
!link @newbie D8423F90
```

**Response**:
```
🔗 Admin Link Confirmation

Link @newbie to vid?

Player: vid (GUID: D8423F90)
Also known as: v1d, vid-slo
18,234 kills | 1.46 K/D

React ✅ (admin) to confirm or ❌ to cancel (60s)
```

**Notes**:
- Cannot link if already linked (must !unlink first)
- GUID must exist in database
- Admin actions are logged
- Timeout after 60 seconds

---

### `!unlink`

**Description**: Unlinks your Discord account from your ET:Legacy GUID.

**Usage**:
```
!unlink
```

**Aliases**: None

**Parameters**: None

**Permissions**: Everyone (own account only)

**Output**:
- Confirmation message with previous link info
- Success message after unlinking

**Example**:
```
!unlink
```

**Response**:
```
✅ Successfully unlinked from vid (GUID: D8423F90)
You can link again anytime with !link
```

**Notes**:
- Only affects your own Discord account
- Can re-link at any time
- Stats are never deleted, only the Discord link

---

### `!select <number>`

**Description**: Alternative to reaction buttons for selecting an option during interactive linking.

**Usage**:
```
!select 1                   # Select first option
!select 2                   # Select second option
!select 3                   # Select third option
```

**Aliases**: None

**Parameters**:
- `number`: Option number (1-3)

**Permissions**: Everyone

**Output**: Same as clicking reaction button

**Example**:
```
# After using !link:
!select 2
```

**Response**:
```
✅ Successfully linked to carniee (GUID: 0A26D447)
```

**Notes**:
- Only works during active !link session
- Must be used within 60 seconds of !link
- Useful if reactions don't work

---

## Leaderboard Commands

### `!leaderboard <type> [page]`

**Description**: Shows top players in various categories with pagination support.

**Usage**:
```
!leaderboard kills          # Kills leaderboard, page 1
!leaderboard dpm 2          # DPM leaderboard, page 2
!lb kd                      # K/D leaderboard (short alias)
```

**Aliases**: `!lb`

**Parameters**:
- `type` (required): Leaderboard category
- `page` (optional): Page number (default: 1)

**Permissions**: Everyone

**Output**:
- Leaderboard title with category
- Top 10 players on current page (medals for top 3: 🥇🥈🥉)
- Player stats relevant to category
- Special badges (👑 dev, 🔥 exceptional performance)
- Page footer with navigation hints

**Categories**:

| Category | Description | Sort By |
|----------|-------------|---------|
| `kills` | Most kills | Total kills |
| `kd` | Best K/D ratio | K/D ratio |
| `dpm` | Damage per minute | DPM |
| `acc` | Accuracy | Hit percentage |
| `hs` | Headshots | Headshot kills |
| `revives` | Most revives given | Revives given |
| `assists` | Most kill assists | Kill assists |
| `dynamites` | Most dynamites planted | Dynamites planted |
| `objectives` | Most objectives completed | Objectives completed |
| `gibs` | Most gibs | Gibs |
| `syringes` | Best medic (revives + times_revived) | Medic score |
| `grenades` | Best grenade usage (kills + accuracy + AOE) | Grenade score |

**Example**:
```
!leaderboard dpm
```

**Response**:
```
🏆 DPM Leaderboard - Page 1/3

╔════╦══════════════════╦═══════════════╗
║ #  ║ Player           ║ DPM           ║
╠════╬══════════════════╬═══════════════╣
║ 🥇 ║ vid 👑           ║ 342.5         ║
╠════╬══════════════════╬═══════════════╣
║ 🥈 ║ carniee          ║ 318.4         ║
╠════╬══════════════════╬═══════════════╣
║ 🥉 ║ .wajs            ║ 298.2         ║
╠════╬══════════════════╬═══════════════╣
║ 4  ║ endekk           ║ 287.6         ║
║ 5  ║ .olz             ║ 276.3         ║
║ 6  ║ SuperBoyy        ║ 265.8         ║
║ 7  ║ qmr              ║ 254.2         ║
║ 8  ║ SmetarskiProner  ║ 243.7         ║
║ 9  ║ c0rnp0rn3        ║ 232.1         ║
║ 10 ║ Lagger           ║ 221.5         ║
╚════╩══════════════════╩═══════════════╝

Page 1 of 3 • Use !lb dpm 2 for next page
```

**Special Badges**:
- 👑 Dev badge (GUID: E587CA5F)
- 🔥 High performance (varies by category)

**Pagination**:
- 10 players per page
- `!lb <type> 0` and `!lb <type> 1` both show page 1
- Footer shows current page and navigation hint

---

## Utility Commands

### `!ping`

**Description**: Tests bot responsiveness and shows latency.

**Usage**:
```
!ping
```

**Aliases**: None

**Parameters**: None

**Permissions**: Everyone

**Output**: Bot latency in milliseconds

**Example**:
```
!ping
```

**Response**:
```
🏓 Pong! Latency: 45ms
```

---

### `!help`

**Description**: Shows all available bot commands with brief descriptions.

**Usage**:
```
!help
```

**Aliases**: None

**Parameters**: None

**Permissions**: Everyone

**Output**:
- Bot description
- Categorized command list
- Usage examples
- Link to full documentation

**Example**:
```
!help
```

**Response**:
```
🤖 ET:Legacy Stats Bot - Command List

📊 Session & Statistics:
   !last_session - View most recent gaming session
   !session [date] - View specific date summary
   !sessions [month] - Browse sessions by month

👥 Player Statistics:
   !stats [player/@mention] - View player statistics
   !list_players [filter] - List players with link status

🔗 Account Linking:
   !link [name/GUID/@user] - Link Discord account
   !unlink - Unlink your account
   !select <number> - Alternative to reactions

🏆 Leaderboards:
   !leaderboard <type> [page] - View leaderboards
   Types: kills, kd, dpm, acc, hs, revives, assists,
          dynamites, objectives, gibs, syringes, grenades

⚙️ Utility:
   !ping - Test bot responsiveness
   !help - Show this help message

📚 Full documentation: docs/COMMAND_REFERENCE.md
```

---

## Command Aliases

Quick reference for command aliases:

| Command | Aliases |
|---------|---------|
| `!leaderboard` | `!lb` |
| `!sessions` | `!list_sessions`, `!ls` |
| `!list_players` | `!players`, `!lp` |

**Usage**:
```
!lb kills         # Same as !leaderboard kills
!ls october       # Same as !sessions october
!lp linked        # Same as !list_players linked
```

---

## Recent Updates

### Session 7 (October 5, 2025)

**New Commands**:
- ✅ `!sessions` - Browse gaming sessions by month
- ✅ `!list_players` - Show players with Discord link status

**Updated Commands**:
- ✅ `!session` - Fixed to show full day aggregation (was showing single round)

**Bug Fixes**:
- Fixed db_path references in Cog methods (self.bot.db_path)
- Fixed discord_id column error with player_links JOIN
- Added flexible date parsing (accepts "2025-10-02" and "2025 10 2")

**Total Commands**: 14 (up from 12)

---

## Tips & Tricks

### Quick Stats Lookup
- Use @mentions for instant lookup: `!stats @friend`
- No need to type exact names
- Works for linked players only

### Session Discovery
- Browse by month: `!sessions october`
- View specific date: `!session 2025-10-02`
- See recent activity: `!last_session`

### Player Management
- Find unlinked players: `!list_players unlinked`
- See active players: `!list_players active`
- Check link status: `!list_players linked`

### Leaderboards
- Short alias: `!lb` instead of `!leaderboard`
- Paginate: `!lb dpm 2` for page 2
- 12 different categories to explore

---

## Troubleshooting

### "You haven't linked your account"
→ Use `!link` to link your Discord to your ET:Legacy GUID

### "Player not found"
→ Check spelling or use @mention if they're linked

### "No data available"
→ Stats are imported from game server files, player may not have played yet

### Reactions not working?
→ Use `!select <number>` as alternative to reaction buttons

### Admin commands not working?
→ Requires "Manage Server" permission in Discord

---

**For more information**:
- User Guide: `docs/README.md`
- Technical Guide: `docs/BOT_COMPLETE_GUIDE.md`
- AI Agent Guide: `docs/AI_AGENT_GUIDE.md`
- Session History: `docs/SESSION_7_SUMMARY.md`

---

*Last updated: October 5, 2025 | Bot Version 3.0 | 14 Commands*
