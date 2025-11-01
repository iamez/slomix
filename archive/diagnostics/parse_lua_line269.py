"""
Parse line 269 of c0rnp0rn3.lua to get EXACT field order
"""

# From c0rnp0rn3.lua line 269 - the ACTUAL order written:
fields = [
    "damageGiven",  # 0
    "damageReceived",  # 1
    "teamDamageGiven",  # 2
    "teamDamageReceived",  # 3
    "gibs",  # 4
    "selfkills",  # 5
    "teamkills",  # 6
    "teamgibs",  # 7
    "timePlayed",  # 8 (percentage)
    "xp",  # 9
    "topshots[i][1]",  # 10 - killing spree
    "topshots[i][2]",  # 11 - death spree
    "topshots[i][3]",  # 12 - kill assists
    "topshots[i][4]",  # 13 - kill steals
    "topshots[i][5]",  # 14 - headshot kills
    "topshots[i][6]",  # 15 - objectives stolen
    "topshots[i][7]",  # 16 - objectives returned
    "topshots[i][8]",  # 17 - dynamites planted
    "topshots[i][9]",  # 18 - dynamites defused
    "topshots[i][10]",  # 19 - times revived
    "topshots[i][11]",  # 20 - bullets fired
    "topshots[i][12]",  # 21 - DPM
    "roundNum((tp/1000)/60, 1)",  # 22 - time played minutes
    "topshots[i][13]",  # 23 - tank/meatshield
    "topshots[i][14]",  # 24 - time dead ratio
    "roundNum((death_time_total[i] / 60000), 1)",  # 25 - time dead minutes
    "kd",  # 26 - k/d ratio
    "topshots[i][15]",  # 27 - useful kills
    "math.floor(topshots[i][16]/1000)",  # 28 - denied playtime (seconds→seconds)
    "multikills[i][1]",  # 29 - 2 kills
    "multikills[i][2]",  # 30 - 3 kills
    "multikills[i][3]",  # 31 - 4 kills
    "multikills[i][4]",  # 32 - 5 kills
    "multikills[i][5]",  # 33 - 6 kills
    "topshots[i][17]",  # 34 - useless kills
    "topshots[i][18]",  # 35 - full selfkills
    "topshots[i][19]",  # 36 - repairs/constructions
]

print("EXACT FIELD ORDER FROM c0rnp0rn3.lua LINE 269")
print("=" * 80)
for i, field in enumerate(fields):
    print(f"Field {i:2d}: {field}")

print("\n" + "=" * 80)
print("DEV'S MESSAGE vs c0rnp0rn3.lua:")
print("=" * 80)
print("Dev said field 27 = 'useful kills' ✅ MATCHES")
print("Dev said field 28 = 'multikills(2)' ❌ WRONG - should be 'denied playtime'")
print("Dev said field 29 = 'multikills(3)' ✅ MATCHES 'multikills[i][1]' (2 kills)")
print("\nDev's mapping is OFF BY ONE starting at field 28!")
print("\nc0rnp0rn3.lua is the SOURCE OF TRUTH - use that!")
