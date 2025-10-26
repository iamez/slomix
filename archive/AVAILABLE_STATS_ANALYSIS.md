# Available Stats Analysis - What Can We Add?

## Current Usage vs Available Data

### ✅ CURRENTLY DISPLAYED (in embeds/graphs)

**MESSAGE 1: Session Overview**
- Map name, date, rounds played
- Total players
- Session duration

**MESSAGE 2: Combat Stats**
- Kills, Deaths, K/D ratio
- DPM (Damage Per Minute)
- Headshots, Headshot Kill Rate
- Time played

**MESSAGE 3: Team Analytics**
- Team comparison (Axis vs Allies)
- Team win/loss

**MESSAGE 4: Weapons**
- All weapons used
- Kills per weapon

**MESSAGE 6: Objective & Support Stats** (Recently enhanced!)
- XP
- Kill Assists
- Objectives Stolen/Returned
- Dynamites Planted/Defused
- Times Revived
- Multikills (2x through 6x) 💥
- Best Killing Spree 🔥
- Death Spree 💀
- Gibs 🦴
- Useful Kills ✅
- Useless Kills 🤡
- Enemy Playtime Denied ⏱️

**GRAPHS:**
- Graph 1: Kills/Deaths/DPM comparison + K/D Ratio
- Graph 2: Revives/Gibs/Useful Kills/Total Damage (4 subplots)
- Graph 3: Per-Map Breakdown (Kills/Deaths/DPM per map)

---

## 🔥 UNDERUTILIZED STATS (Not displayed yet!)

### 1. **Team Damage Stats** (Friendly Fire!)
- `team_damage_given` - Damage dealt to teammates
- `team_damage_received` - Damage received from teammates
- `team_kills` - How many teammates you killed
- `team_gibs` - How many teammates you gibbed

**Potential Display:**
```
🔥 FRIENDLY FIRE HALL OF SHAME 🔥
😈 Most Team Damage: PlayerX (2,450 dmg)
💀 Most Teamkills: PlayerY (3 kills)
🦴 Fragged Own Team: PlayerZ (2 teamgibs)
```

### 2. **Kill Steals**
- `kill_steals` - Kills stolen from teammates

**Potential Display:**
```
🥷 KILL STEALER ALERT
PlayerX stole 5 kills from teammates!
```

### 3. **Tank Meatshield**
- `tank_meatshield` - Unknown stat (possibly tank damage absorbed?)

**Potential Display:**
```
🛡️ TANK SHIELD: PlayerX absorbed tank hits
```

### 4. **Full Self-Kills**
- `full_selfkills` - Complete suicides (vs partial self damage)

**Potential Display:**
```
🤦 EPIC SELF-DESTRUCTIONS
PlayerX: 3 full self-kills
```

### 5. **Repairs & Constructions**
- `repairs_constructions` - Engineer objective work

**Potential Display:**
```
🔧 TOP ENGINEERS
PlayerX: 15 repairs/constructions
```

### 6. **Bullets Fired**
- `bullets_fired` - Total ammunition used

**Potential Display:**
```
🎯 AMMO CONSUMPTION
PlayerX: 10,462 bullets fired
Trigger Happy Award: Most bullets/kill ratio
```

### 7. **Damage Statistics** (Currently not shown prominently)
- `damage_given` - Total damage dealt
- `damage_received` - Total damage taken

**Potential Display:**
```
💥 DAMAGE EFFICIENCY
Damage Dealt/Received Ratio
Best Damage Efficiency: PlayerX (3.2x more given than taken)
```

### 8. **Time Dead Ratio** (Partially shown)
- `time_dead_ratio` - Percentage of time spent dead

**Potential Display:**
```
⚰️ RESPAWN TIMER CHAMPIONS
PlayerX spent 35% of match dead (most respawn time)
```

### 9. **Kill Assists** (Currently shown but not prominent)
- `kill_assists` - Assists on teammate kills

**Potential Display:**
```
🤝 ULTIMATE SUPPORT PLAYER
PlayerX: 25 kill assists (teamwork master!)
```

---

## 💡 NEW EMBED/GRAPH IDEAS

### New Embed: "🔥 FRIENDLY FIRE & CHAOS"
- Team damage leaders
- Teamkill counts
- Self-kill champions
- Kill steals

### New Embed: "🔧 ENGINEER EXCELLENCE"
- Repairs & constructions
- Dynamite planted/defused (already shown)
- Objectives stolen/returned (already shown)

### New Graph 4: "📊 Damage Efficiency"
- Bar chart: Damage Given vs Damage Received per player
- Show who's most efficient at dealing damage while taking less

### New Graph 5: "🎯 Accuracy & Ammo"
- Bullets fired per player
- Bullets per kill ratio
- "Spray & Pray Award" (most bullets/kill)

### New Graph 6: "⚰️ Survival Analysis"
- Time dead ratio per player
- Time alive vs time dead comparison
- "Spawn Camped Award" (highest time_dead_ratio)

### New Ranking Section: "🏆 SPECIAL AWARDS"
```
🥇 Biggest Teamkiller: PlayerX (3 teamkills)
🥈 Most Self-Destructive: PlayerY (4 self-kills)
🥉 Kill Thief: PlayerZ (7 kill steals)
🎖️ Damage Efficiency King: PlayerA (4.5x ratio)
🛡️ Tank Meatshield: PlayerB (absorbed most tank hits)
🔧 Chief Engineer: PlayerC (20 repairs)
💀 Longest Death Streak: PlayerD (stayed dead 40% of match)
🎯 Spray Master: PlayerE (200 bullets per kill)
```

---

## 📊 IMPLEMENTATION PRIORITY

### HIGH PRIORITY (Impressive & Available)
1. ✅ **Friendly Fire Stats** - Team damage, teamkills (funny & informative)
2. ✅ **Special Awards Section** - Auto-generated awards based on stats
3. ✅ **Damage Efficiency Graph** - Visual damage given/received comparison
4. ✅ **Engineer Stats** - Repairs & constructions (currently hidden)

### MEDIUM PRIORITY
5. ⚠️ **Kill Steals** - Call out the steal masters
6. ⚠️ **Bullets Fired** - Ammo consumption analysis
7. ⚠️ **Survival Analysis** - Time dead visualization

### LOW PRIORITY
8. 🔍 **Tank Meatshield** - Need to understand what this stat means
9. 🔍 **Self-Kill Tracking** - Less interesting than teamkills

---

## 🎯 RECOMMENDED ADDITIONS

### Option A: Add "Special Awards" Section (Easy Win)
Create a new MESSAGE with auto-generated funny awards:
```python
# MESSAGE 7: SPECIAL AWARDS 🏆
awards_text = []
if max_teamkills > 0:
    awards_text.append(f"🔥 **Friendly Fire King:** {player_with_most_teamkills} ({max_teamkills} teamkills)")
if max_kill_steals > 0:
    awards_text.append(f"🥷 **Kill Stealer:** {player_with_steals} ({max_kill_steals} steals)")
# ... more awards
```

### Option B: Enhanced Graph 4 - Damage Efficiency
Show damage_given vs damage_received as dual bars per player

### Option C: New Embed - Friendly Fire Hall of Shame
Dedicated section for team damage stats (hilarious for community)

Would you like me to implement any of these? The **Special Awards** section would be the quickest win and most entertaining!
