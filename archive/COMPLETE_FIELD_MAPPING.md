# Complete Field Mapping (from dev c0rnn)

## Line Structure
```
guid\name\rounds\team\dwWeaponMask weaponStats \t field0 \t field1 \t ... \t field36
```

## Prefix Fields (separated by `\`)
1. guid
2. name
3. rounds
4. team
5. dwWeaponMask

## Weapon Stats (after space, before first TAB)
- weaponStats (variable length)

## TAB-Separated Fields (37 total: field 0-36)
```
TAB[0]  = damageGiven
TAB[1]  = damageReceived
TAB[2]  = teamDamageGiven
TAB[3]  = teamDamageReceived
TAB[4]  = gibs
TAB[5]  = selfkills
TAB[6]  = teamkills
TAB[7]  = teamgibs
TAB[8]  = timePlayed ratio
TAB[9]  = xp
TAB[10] = killing spree
TAB[11] = death spree
TAB[12] = kill assists
TAB[13] = kill steals
TAB[14] = headshot kills
TAB[15] = objectives stolen
TAB[16] = objectives returned
TAB[17] = dynamites planted
TAB[18] = dynamites defused
TAB[19] = most revived
TAB[20] = bullets fired
TAB[21] = DPM
TAB[22] = time played
TAB[23] = tank/meatshield (dmg received/death)
TAB[24] = time dead ratio
TAB[25] = time dead
TAB[26] = k/d ratio
TAB[27] = useful kills
TAB[28] = denied playtime
TAB[29] = multikills(2)
TAB[30] = multikills(3)
TAB[31] = multikills(4)
TAB[32] = multikills(5)
TAB[33] = multikills(6)
TAB[34] = useless kills (from c0rnp0rn3.lua: topshots[i][17])
TAB[35] = full selfkills (from c0rnp0rn3.lua: topshots[i][18])
TAB[36] = repairs/constructions (from c0rnp0rn3.lua: topshots[i][19])
```

## Total Fields
- **42 fields total** (as dev said "1-42 polj")
- 5 prefix fields (guid, name, rounds, team, dwWeaponMask)
- 1 weaponStats field
- 37 TAB-separated fields (0-36) starting from damageGiven

## Key Finding
**The dev's complete list shows TAB[28] = denied playtime, which matches c0rnp0rn3.lua exactly!**
The first shorter list the dev provided was missing "denied playtime" between "useful kills" and "multikills(2)".
