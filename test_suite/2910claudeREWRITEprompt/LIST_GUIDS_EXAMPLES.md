# 📸 !list_guids Command - Visual Examples

## Example 1: Default Mode (Most Active)

**Command:**
```
!list_guids
```

**Bot Response:**
```
┌─────────────────────────────────────────────────────────┐
│ 🎮 Most Active Unlinked Players (Top 10)               │
├─────────────────────────────────────────────────────────┤
│ Found 7 unlinked player(s).                             │
│ Showing up to 2 aliases per GUID.                       │
│                                                          │
│ 💡 To link: !link @user <GUID>                         │
└─────────────────────────────────────────────────────────┘

🆔 D8423F90
**^pvid** / vidPlayer
📊 5,234K / 3,112D / 1.68 KD
🎮 156 games • Last: 2025-10-28

🆔 652EB4A6
**^3qmr** / qmrPlayer (+1 more)
📊 4,521K / 2,890D / 1.56 KD
🎮 132 games • Last: 2025-10-27

🆔 7B84BE88
**endekk**
📊 3,892K / 3,001D / 1.30 KD
🎮 98 games • Last: 2025-10-26

🆔 EDBB5DA9
**^6S^2uper^6B^2oyy** / SuperBoy
📊 2,341K / 2,100D / 1.11 KD
🎮 87 games • Last: 2025-10-25

🆔 5D989160
**^1.^7olz** / olzPlayer (+2 more)
📊 1,892K / 1,950D / 0.97 KD
🎮 76 games • Last: 2025-10-24

💡 Use !list_guids <n> to search • !list_guids recent for last 7 days
```

---

## Example 2: Search by Name

**Command:**
```
!list_guids qmr
```

**Bot Response:**
```
┌─────────────────────────────────────────────────────────┐
│ 🔍 Unlinked Players matching 'qmr'                      │
├─────────────────────────────────────────────────────────┤
│ Found 1 unlinked player(s).                              │
│ Showing up to 2 aliases per GUID.                       │
│                                                          │
│ 💡 To link: !link @user <GUID>                         │
└─────────────────────────────────────────────────────────┘

🆔 652EB4A6
**^3qmr** / qmrPlayer (+1 more)
📊 4,521K / 2,890D / 1.56 KD
🎮 132 games • Last: 2025-10-27

💡 Use !list_guids <n> to search • !list_guids recent for last 7 days
```

**Then Admin Links:**
```
!link @qmr#1234 652EB4A6
```

**Bot Confirms:**
```
✅ Successfully linked to ^3qmr (GUID: 652EB4A6)
```

---

## Example 3: Recently Active (Last 7 Days)

**Command:**
```
!list_guids recent
```

**Bot Response:**
```
┌─────────────────────────────────────────────────────────┐
│ 🕐 Recently Active Unlinked Players (Last 7 Days)       │
├─────────────────────────────────────────────────────────┤
│ Found 4 unlinked player(s).                              │
│ Showing up to 2 aliases per GUID.                       │
│                                                          │
│ 💡 To link: !link @user <GUID>                         │
└─────────────────────────────────────────────────────────┘

🆔 D8423F90
**^pvid** / vidPlayer
📊 892K / 634D / 1.41 KD
🎮 23 games • Last: 2025-10-28

🆔 652EB4A6
**^3qmr** / qmrPlayer (+1 more)
📊 756K / 589D / 1.28 KD
🎮 19 games • Last: 2025-10-27

🆔 7B84BE88
**endekk**
📊 634K / 512D / 1.24 KD
🎮 18 games • Last: 2025-10-26

🆔 2B5938F5
**^ybronze^h.** / BronzePlayer
📊 423K / 389D / 1.09 KD
🎮 12 games • Last: 2025-10-23

💡 Use !list_guids <n> to search • !list_guids recent for last 7 days
```

**Perfect for post-game linking sessions!**

---

## Example 4: Show All Unlinked

**Command:**
```
!list_guids all
```

**Bot Response:**
```
┌─────────────────────────────────────────────────────────┐
│ 📋 All Unlinked Players (Top 20)                        │
├─────────────────────────────────────────────────────────┤
│ Found 12 unlinked player(s).                             │
│ Showing up to 2 aliases per GUID.                       │
│                                                          │
│ 💡 To link: !link @user <GUID>                         │
└─────────────────────────────────────────────────────────┘

[Shows all 12 players, max 20]

💡 Use !list_guids <n> to search • !list_guids recent for last 7 days
```

---

## Example 5: No Results

**Command:**
```
!list_guids nonexistent
```

**Bot Response:**
```
✅ No unlinked players found!
Everyone is linked or search returned no results.
```

---

## Example 6: Complete Admin Workflow

**Step 1: List unlinked players**
```
Admin: !list_guids recent
```

**Bot shows:**
```
🆔 D8423F90
**^pvid** / vidPlayer
📊 892K / 634D / 1.41 KD
🎮 23 games • Last: 2025-10-28

🆔 652EB4A6
**^3qmr** / qmrPlayer (+1 more)
📊 756K / 589D / 1.28 KD
🎮 19 games • Last: 2025-10-27
```

**Step 2: Admin links players**
```
Admin: !link @vid#5678 D8423F90
Bot: ✅ Successfully linked to ^pvid (GUID: D8423F90)

Admin: !link @qmr#1234 652EB4A6
Bot: ✅ Successfully linked to ^3qmr (GUID: 652EB4A6)
```

**Step 3: Verify it worked**
```
Admin: !stats @vid#5678
Bot: [Shows vid's full stats]

Admin: !stats @qmr#1234
Bot: [Shows qmr's full stats]

Admin: !list_guids recent
Bot: ✅ No unlinked players found!
```

**Done! All recent players now linked!** 🎉

---

## Example 7: Player with Multiple Names

**Command:**
```
!list_guids
```

**Bot Shows Player with 5 Aliases:**
```
🆔 5D989160
**^1.^7olz** / olzPlayer (+3 more)
📊 1,892K / 1,950D / 0.97 KD
🎮 76 games • Last: 2025-10-24
```

**What this means:**
- Primary name: `^1.^7olz` (most frequently used or most recent)
- Secondary name: `olzPlayer` (second most common)
- Has 3 additional names tracked in the database

**All 5 aliases point to the same GUID:** `5D989160`

---

## Example 8: Mobile/Desktop Display

**Discord Mobile:**
```
[Compact embed view]
🎮 Most Active Unlinked Players

🆔 D8423F90
^pvid / vidPlayer
📊 5,234K / 3,112D / 1.68 KD
🎮 156 games • Last: 2025-10-28
[... more players ...]
```

**Discord Desktop:**
```
[Full width embed with clear formatting]
┌────────────────────────────────────────────┐
│ 🎮 Most Active Unlinked Players (Top 10)  │
│                                             │
│ 🆔 D8423F90                                │
│ ^pvid / vidPlayer                          │
│ 📊 5,234K / 3,112D / 1.68 KD              │
│ 🎮 156 games • Last: 2025-10-28           │
└────────────────────────────────────────────┘
```

---

## Quick Copy/Paste Examples

### For Help Message to Players:
```
Hey everyone! To link your ET:Legacy stats to Discord:
1. Type: !link
2. React with the number that matches your in-game name
3. Done!

If you need help, ask an admin to use !list_guids to find your GUID.
```

### For Admin Announcement:
```
📢 Admins can now easily link players!
Use: !list_guids recent
Then: !link @user <GUID>

Makes linking 10x faster! 🚀
```

### For Troubleshooting:
```
Player: "I can't find my stats"
Admin: !list_guids PlayerName
Admin: !link @Player <GUID>
Admin: "Try !stats now!"
Player: ✅ "It works!"
```

---

## Key Features Highlighted

✅ **Shows up to 2 aliases** - Easy player identification  
✅ **Displays stats** - K/D, games, last seen  
✅ **Multiple modes** - default, recent, search, all  
✅ **Ready-to-copy GUIDs** - Just copy and !link  
✅ **Sorted intelligently** - Most active first  
✅ **Clean formatting** - Easy to read on mobile/desktop  

---

**Visual aid makes it easy to understand how powerful this command is!** 📸
