# 🔍 !list_guids Command - Admin Guide

## What It Does

The `!list_guids` command helps admins easily link players to their Discord accounts by showing **unlinked players** with their in-game names (aliases).

## Why You Need This

**Before** (the hard way):
```
Admin: "Hey what's your GUID?"
Player: "Uh... I don't know?"
Admin: *checks logs manually* "Is your name PlayerX?"
Player: "Yeah that's me!"
Admin: *searches database for GUID* "Found it! ABC12345"
Admin: !link @player ABC12345
```

**After** (the easy way):
```
Admin: !list_guids
Bot: *shows unlinked players with names and GUIDs*
Admin: "Oh I see PlayerX is ABC12345"
Admin: !link @player ABC12345
✅ Done!
```

## Usage Modes

### 1. Default - Most Active Unlinked Players
```
!list_guids
```
Shows top 10 unlinked players sorted by total kills/activity.

**Example Output:**
```
🎮 Most Active Unlinked Players (Top 10)
Found 7 unlinked player(s). Showing up to 2 aliases per GUID.
💡 To link: !link @user <GUID>

🆔 ABC12345
**PlayerName** / OldName (+1 more)
📊 5,234K / 3,112D / 1.68 KD
🎮 156 games • Last: 2025-10-28

🆔 DEF67890
**AnotherPlayer** / Rookie
📊 3,421K / 2,890D / 1.18 KD
🎮 98 games • Last: 2025-10-27
```

### 2. Search by Name
```
!list_guids PlayerName
```
Search for specific player by name (partial match works!).

**Use Cases:**
- Player asks "can you link me?" → `!list_guids theirname`
- Looking for someone specific → `!list_guids john`

### 3. Recently Active (Last 7 Days)
```
!list_guids recent
```
Shows players who played in the last 7 days only.

**Use Cases:**
- After a game night → see who played and needs linking
- Focus on active players first

### 4. Show All Unlinked
```
!list_guids all
```
Shows up to 20 unlinked players (most recent first).

**Use Cases:**
- Want to see everyone unlinked
- Bulk linking session

## How to Link Players

Once you see a player in the list:

### Method 1: Admin Link (Recommended)
```
!link @PlayerDiscord ABC12345
```
**Example:**
```
!list_guids
> Shows: ABC12345 - **JohnDoe** / Johnny
!link @JohnDoe ABC12345
✅ Linked JohnDoe to ABC12345!
```

### Method 2: Player Self-Link
```
Player: !link ABC12345
Bot: *asks for confirmation*
Player: *reacts with ✅*
✅ Linked!
```

## What You See in Each Entry

```
🆔 ABC12345                    ← The GUID (copy this for linking!)
**MainName** / OtherName      ← Primary name (bold) + 2nd most used name
(+3 more)                      ← Number of additional aliases
📊 5,234K / 3,112D / 1.68 KD  ← Kills / Deaths / K/D Ratio
🎮 156 games • Last: 2025-10-28 ← Total games played & last seen date
```

## Aliases Explained

### Why Up To 2 Aliases?
Players change names frequently in ET:Legacy. Showing 2 names helps you identify:
- **Primary name**: Most frequently used or most recent
- **Secondary name**: Second most common name
- **+X more**: If they have more than 2 names tracked

### Examples:
```
🆔 ABC12345
**JohnDoe** / Johnny (+2 more)
```
This player goes by "JohnDoe" most often, sometimes "Johnny", and has 2 other names in the system.

```
🆔 DEF67890
**RookiePlayer**
```
This player only has one name tracked.

## Practical Workflows

### Workflow 1: Post-Game Linking Session
```
1. Game ends at 22:00
2. Admin: !list_guids recent
3. Bot shows 8 players who just played
4. Admin goes through Discord:
   - !link @Player1 ABC12345
   - !link @Player2 DEF67890
   - !link @Player3 GHI11111
5. Done! All active players now linked
```

### Workflow 2: Player Requests Link
```
Player: "Hey can you link my account?"
Admin: "What's your in-game name?"
Player: "I go by Destroyer"
Admin: !list_guids destroyer
Bot: Shows GUID ABC12345 for "Destroyer"
Admin: !link @Player ABC12345
Player: ✅ "Thanks!"
```

### Workflow 3: Bulk Linking New Players
```
Admin: !list_guids all
Bot: Shows 15 unlinked players
Admin: Posts in Discord:
  "Hey guys, if you're on this list, please link your account!
   Just type !link and follow the prompts"
```

## Tips & Tricks

### Tip 1: Copy GUIDs Easily
On Discord desktop/mobile:
1. Long press/right-click on GUID
2. Copy text
3. Paste in !link command

### Tip 2: Identify Players by Stats
Can't tell which GUID is which player?
- Check K/D ratio (good players have higher)
- Check games played (regulars have more)
- Check last seen date (active players are recent)

### Tip 3: Search Works with Partial Names
```
!list_guids john      ← finds "Johnny", "JohnDoe", "Johnson"
!list_guids destroy   ← finds "Destroyer", "DestroyerX"
!list_guids ^3        ← finds names with color codes like "^3Red"
```

### Tip 4: Combine with Other Commands
```
# See who needs linking
!list_guids recent

# Link multiple players in sequence
!link @Player1 ABC12345
!link @Player2 DEF67890
!link @Player3 GHI11111

# Verify they're linked
!stats @Player1
```

## Command Aliases

You can also use:
```
!listguids    ← same as !list_guids
!unlinked     ← same as !list_guids
```

## Troubleshooting

### "No unlinked players found"
✅ **Good news!** Everyone is already linked.

### Player not showing up in list
**Possible reasons:**
1. They're already linked → Check with `!stats @player`
2. They haven't played recently → Use `!list_guids all`
3. No aliases tracked yet → Have them play a game first

### Wrong player name showing
**This is normal!** Players change names. The bot shows:
- Most frequently used name
- Most recently used name
- Other aliases available

### GUID not working when linking
**Make sure to:**
1. Copy GUID exactly (8 characters)
2. Use uppercase: `ABC12345` not `abc12345`
3. No spaces or extra characters

## For Developers

### Database Query
The command queries:
```sql
SELECT 
    pa.guid,
    COUNT(DISTINCT pa.alias) as alias_count,
    MAX(pa.last_seen) as last_seen,
    SUM(pcs.kills) as total_kills,
    SUM(pcs.deaths) as total_deaths,
    COUNT(DISTINCT pcs.session_id) as games
FROM player_aliases pa
LEFT JOIN player_comprehensive_stats pcs ON pa.guid = pcs.player_guid
WHERE pa.guid NOT IN (SELECT et_guid FROM player_links WHERE et_guid IS NOT NULL)
GROUP BY pa.guid
ORDER BY total_kills DESC, games DESC
LIMIT 10
```

### How Aliases Are Tracked
Every time a game is played:
1. Stats file processed
2. For each player: GUID + name → `player_aliases` table
3. `times_seen` counter incremented
4. `last_seen` date updated

### Adding Permissions
To make this admin-only, add before the command:
```python
@commands.has_permissions(administrator=True)
async def list_guids(self, ctx, *, search_term: str = None):
```

## Summary

**What**: Shows unlinked players with their GUIDs and names  
**Why**: Makes it easy for admins to help link players  
**How**: `!list_guids` → see players → `!link @user <GUID>`  
**Benefit**: 10x faster than manual GUID hunting!  

---

**The !list_guids command turns player linking from a 5-minute hunt into a 5-second task! 🚀**
