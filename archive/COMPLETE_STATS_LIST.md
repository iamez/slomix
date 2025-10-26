# 📊 Complete List of All In-Game Stats We Collect

**Last Updated:** October 4, 2025  
**Database:** etlegacy_production.db  
**Total Stats Tracked:** 78+ individual data points per session

---

## 🎮 SESSION INFORMATION (7 fields)

Every gameplay session is tracked with:

1. **Session ID** - Unique identifier for each round
2. **Session Date** - Date the round was played (YYYY-MM-DD)
3. **Map Name** - Which map was played (e.g., etl_adlernest, supply, te_escape2)
4. **Round Number** - Round 1 or Round 2
5. **Time Limit** - Map's time limit setting (e.g., "10:00")
6. **Actual Time** - How long the round actually lasted
7. **Created At** - Timestamp when record was created

---

## 👤 PLAYER COMPREHENSIVE STATS (35 fields)

### **Basic Information (6 fields)**
1. **Player GUID** - Unique player identifier
2. **Player Name** - Full name with color codes
3. **Clean Name** - Name without color codes
4. **Team** - Which team (0=Spectator, 1=Axis, 2=Allies)
5. **Time Axis** - Seconds spent on Axis team
6. **Time Allies** - Seconds spent on Allies team

### **Combat Stats (8 fields)**
7. **Kills** - Total enemy kills
8. **Deaths** - Total deaths
9. **Headshot Kills** - Kills with headshots
10. **Gibs** - Enemies gibbed (exploded)
11. **Self Kills** - Deaths from own actions
12. **Team Kills** - Friendly fire kills
13. **Team Gibs** - Teammates gibbed
14. **Kill Assists** - Assists on kills

### **Damage Stats (4 fields)**
15. **Damage Given** - Total damage dealt to enemies
16. **Damage Received** - Total damage taken from enemies
17. **Team Damage Given** - Damage dealt to teammates (friendly fire)
18. **Team Damage Received** - Damage taken from teammates

### **Time & Experience (4 fields)**
19. **Time Played (Seconds)** - Total seconds played (INTEGER)
20. **Time Played (Minutes)** - Total minutes played (REAL)
21. **XP** - Total experience points earned
22. **DPM** - Damage Per Minute (calculated: damage_given / time_played_minutes)

### **Performance Metrics (3 fields)**
23. **K/D Ratio** - Kill/Death ratio
24. **Efficiency** - Combat efficiency percentage
25. **Killing Spree Best** - Longest kill streak
26. **Death Spree Worst** - Longest death streak

### **Support Stats (3 fields)**
27. **Revives** - Players revived
28. **Ammo Packs** - Ammo packs given
29. **Health Packs** - Health packs given

### **Awards (4 fields)**
30. **Award Accuracy** - Accuracy award points
31. **Award Damage** - Damage award points
32. **Award Kills** - Kill award points
33. **Award Experience** - Experience award points

---

## 🎯 PLAYER OBJECTIVE STATS (27 fields)

### **Objective Actions (8 fields)**
1. **Objectives Completed** - Total objectives finished
2. **Objectives Destroyed** - Objectives destroyed
3. **Objectives Captured** - Objectives captured
4. **Objectives Defended** - Objectives defended
5. **Objectives Stolen** - Objectives stolen from enemy
6. **Objectives Returned** - Objectives returned to base
7. **Dynamites Planted** - Dynamite charges planted
8. **Dynamites Defused** - Enemy dynamites defused

### **Engineering & Support (7 fields)**
9. **Landmines Planted** - Landmines placed
10. **Landmines Spotted** - Enemy mines spotted
11. **Constructions Built** - Buildings/objectives built
12. **Constructions Destroyed** - Enemy constructions destroyed
13. **Revives** - Players revived (medic)
14. **Ammo Packs** - Ammo given (field ops)
15. **Health Packs** - Health given (medic)
16. **Times Revived** - How many times player was revived

### **Advanced Combat Stats (7 fields)**
17. **Kill Assists** - Assists on enemy kills
18. **Killing Spree Best** - Longest kill streak in round
19. **Death Spree Worst** - Longest death streak in round
20. **Kill Steals** - Kills stolen from teammates
21. **Most Useful Kills** - High-value target kills
22. **Useless Kills** - Low-value kills
23. **Denied Playtime** - Time denied to enemies (in seconds)

### **Unique Stats (1 field)**
24. **Tank Meatshield** - Damage absorbed while near tank (REAL)

---

## 🔫 WEAPON STATS (10 fields per weapon)

**Tracked for EVERY weapon a player uses:**

### **Per-Weapon Breakdown**
1. **Weapon Name** - Weapon identifier (e.g., WS_MP40, WS_THOMPSON)
2. **Hits** - Successful hits with weapon
3. **Shots** - Total shots fired
4. **Kills** - Kills with this weapon
5. **Deaths** - Deaths while holding this weapon
6. **Headshots** - Headshot kills with weapon
7. **Accuracy** - Hit percentage (hits/shots × 100)

### **Weapons Tracked:**
- **Primary Weapons:**
  - WS_MP40 (SMG - Axis)
  - WS_THOMPSON (SMG - Allies)
  - WS_GARAND (Rifle - Allies)
  - WS_KAR98 (Rifle - Axis)
  - WS_K43 (Semi-auto rifle - Axis)
  - WS_CARBINE (Semi-auto rifle - Allies)
  - WS_FG42 (Automatic rifle)
  - WS_PANZERFAUST (Anti-tank)
  - WS_BAZOOKA (Anti-tank)
  - WS_FLAMETHROWER
  - WS_MORTAR
  - WS_GRENADELAUNCHER
  
- **Secondary Weapons:**
  - WS_LUGER (Pistol - Axis)
  - WS_COLT (Pistol - Allies)
  
- **Equipment:**
  - WS_GRENADE (Hand grenades)
  - WS_KNIFE (Melee)
  - WS_DYNAMITE
  - WS_LANDMINE
  - WS_SATCHEL
  - WS_AIRSTRIKE
  - WS_ARTILLERY
  
- **Special:**
  - WS_SYRINGE (Medic revive)
  - WS_SMOKE (Smoke grenades)
  - WS_PLIERS (Engineer tool)

**Total weapon records in database: 61,497** (as of October 4, 2025)

---

## 📈 CALCULATED STATS

These are derived from the raw data:

1. **DPM (Damage Per Minute)**
   - Formula: `damage_given / time_played_minutes`
   - Example: 3044 damage in 10 minutes = 304.4 DPM

2. **K/D Ratio**
   - Formula: `kills / deaths` (or kills if no deaths)
   - Example: 12 kills, 16 deaths = 0.75 K/D

3. **Efficiency**
   - Formula: `kills / (kills + deaths) × 100`
   - Example: 12 kills, 16 deaths = 42.86% efficiency

4. **Accuracy (per weapon)**
   - Formula: `hits / shots × 100`
   - Example: 139 hits, 334 shots = 41.6% accuracy

---

## 🎯 CURRENT DATA STATS

**As of October 4, 2025:**

- **Sessions Tracked:** 1,862 rounds
- **Player Records:** 12,396 complete player stat records
- **Weapon Records:** 61,497 individual weapon usage records
- **Date Range:** January 1, 2025 - October 2, 2025
- **Maps Played:** 20+ different maps
- **Average Players/Session:** 6.7 players

---

## 🔍 TOP WEAPON USAGE (All-Time)

Based on total kills across all sessions:

1. **WS_MP40:** 50,727 kills (most popular)
2. **WS_THOMPSON:** 42,951 kills
3. **WS_GRENADE:** 8,178 kills
4. **WS_LUGER:** 3,125 kills
5. **WS_COLT:** 2,088 kills
6. **WS_GRENADELAUNCHER:** 1,014 kills
7. **WS_GARAND:** 832 kills
8. **WS_KAR98:** 441 kills

---

## 📝 NOTES

### **What's Currently Tracked:**
✅ All combat stats (kills, deaths, damage, headshots, gibs)  
✅ All objective actions (dynamites, constructions, captures)  
✅ All support actions (revives, ammo, health)  
✅ Detailed weapon breakdown (every weapon used)  
✅ Time tracking (seconds played, team time)  
✅ Sprees (killing/death streaks)  
✅ Awards and experience  
✅ Team damage (friendly fire)  

### **Limitations:**
⚠️ Some fields default to 0 (not captured by c0rnp0rn3.lua yet):
- `time_axis` / `time_allies` - Team time split
- Some objective fields may be 0 for certain game modes

### **Data Source:**
All stats come from **c0rnp0rn3.lua** mod running on the ET:Legacy server. The mod writes 38 tab-separated fields per player to text files, which our parser reads and imports into the database.

---

## 🎮 HOW TO USE THIS DATA

### **Discord Bot Commands:**
- `!last_session` - View stats from most recent round
- `!player <name>` - View specific player's stats
- `!top kills` - Top players by kills
- `!top dpm` - Top players by damage per minute
- `!weapon <name>` - Weapon usage stats

### **Direct Database Queries:**
```sql
-- Get player's total stats across all sessions
SELECT 
    clean_name,
    SUM(kills) as total_kills,
    SUM(deaths) as total_deaths,
    SUM(damage_given) as total_damage,
    AVG(dpm) as avg_dpm
FROM player_comprehensive_stats
WHERE player_guid = 'PLAYER_GUID_HERE'
GROUP BY player_guid;

-- Get weapon accuracy for a player
SELECT 
    weapon_name,
    SUM(kills) as kills,
    SUM(hits) as hits,
    SUM(shots) as shots,
    ROUND(SUM(hits) * 100.0 / SUM(shots), 2) as accuracy
FROM weapon_comprehensive_stats
WHERE player_guid = 'PLAYER_GUID_HERE'
GROUP BY weapon_name
ORDER BY kills DESC;
```

---

**Total Unique Stats:** 78+ fields tracked per player per session!  
**Database Size:** ~20-50 MB for full 2025 season  
**Query Performance:** Indexed on session_id, player_guid, map_name, session_date
