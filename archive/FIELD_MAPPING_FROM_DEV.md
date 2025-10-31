# OFFICIAL FIELD MAPPING FROM c0rnp0rn3 DEVELOPER

## Example Line from File:
```
0566F682\^3O^2z ^7forty\1\2\142870584 5 14 0 0 1 7 16 1 15 0 123 377 9 0 4 4 12 1 2 0 0 0 0 1 0 0 0 0 1 0 2 3 0 0 0 2510 3826 324 142 1 3 2 0 67.4 72
```

## Field Order (TAB-separated after weaponStats):

**BEFORE TAB:** guid, name, rounds, team, dwWeaponMask, weaponStats (space-separated)

**AFTER TAB (TAB-separated):**

| Field# | Name | Description |
|--------|------|-------------|
| 0 | damageGiven | Total damage dealt |
| 1 | damageReceived | Total damage taken |
| 2 | teamDamageGiven | Friendly fire damage dealt |
| 3 | teamDamageReceived | Friendly fire damage taken |
| 4 | gibs | **Number of gibs** |
| 5 | selfkills | Self kills |
| 6 | teamkills | Team kills |
| 7 | teamgibs | Team gibs |
| 8 | timePlayed ratio | Time played percentage |
| 9 | xp | Experience points |
| 10 | killing spree | Longest killing spree |
| 11 | death spree | Longest death spree |
| 12 | kill assists | Kill assists |
| 13 | kill steals | Kill steals |
| 14 | headshot kills | Headshot kills |
| 15 | objectives stolen | Objectives stolen |
| 16 | objectives returned | Objectives returned |
| 17 | dynamites planted | Dynamites planted |
| 18 | dynamites defused | Dynamites defused |
| 19 | most revived | **Number of times THIS player was revived** |
| 20 | bullets fired | Total bullets fired |
| 21 | DPM | Damage per minute |
| 22 | time played | Time played in minutes |
| 23 | tank/meatshield | Damage received per death / 130 |
| 24 | time dead ratio | Percentage of time dead |
| 25 | time dead | Time dead in minutes |
| 26 | k/d ratio | Kill/death ratio |
| 27 | useful kills | Useful kills |
| 28 | multikills(2) | Double kills |
| 29 | multikills(3) | Triple kills |
| 30 | multikills(4) | Quad kills |
| 31 | multikills(5) | Penta kills |
| 32 | multikills(6) | Hexa kills |

**TOTAL: 33 TAB-separated fields (0-32)**

## Our Parser Status:
✅ **CORRECT** - We already fixed this! Parser reads gibs from field 4.
✅ **CORRECT** - Parser reads all other fields from correct positions.

## Verification Needed:
- Check that field 28-32 are named correctly (multikills vs multi_kill)
- Ensure database schema matches these field names
- Verify import script uses correct field names
