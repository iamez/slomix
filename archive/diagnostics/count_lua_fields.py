"""Count the number of fields in the lua stats line"""

# Line 273 from c0rnp0rn3.lua - the format string with all the fields
import re

lua_format_line = """stats[guid] = string.format("%s \t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%0.1f\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%0.1f\t%0.1f\t%0.1f\t%0.1f\t%0.1f\t%0.1f\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\n", stats[guid], damageGiven, damageReceived, teamDamageGiven, teamDamageReceived, gibs, selfkills, teamkills, teamgibs, timePlayed, xp, topshots[i][1], topshots[i][2], topshots[i][3], topshots[i][4], topshots[i][5], topshots[i][6], topshots[i][7], topshots[i][8], topshots[i][9], topshots[i][10], topshots[i][11], topshots[i][12], roundNum((tp/1000)/60, 1), topshots[i][13], topshots[i][14], roundNum((death_time_total[i] / 60000), 1), kd, topshots[i][15], math.floor(topshots[i][16]/1000), multikills[i][1], multikills[i][2], multikills[i][3], multikills[i][4], multikills[i][5], topshots[i][17], topshots[i][18])"""

# Count format specifiers after the first %s (which is stats[guid])

# Find all format specifiers
format_specs = re.findall(r'%[ds]|%0\.\d+f', lua_format_line)

print("Format specifiers found:")
print(f"Total: {len(format_specs)}")
print(f"First 10: {format_specs[:10]}")
print(f"Last 10: {format_specs[-10:]}")
print()

# The first %s is for stats[guid] (which already contains the weapon stats)
# Then there's " \t" (space + tab)
# Then the rest are the extended stats fields

extended_fields = format_specs[1:]  # Skip the first %s
print(f"Extended stats fields (after first %s): {len(extended_fields)}")
print()

# Now let's map them to the parameter list
params = """stats[guid], damageGiven, damageReceived, teamDamageGiven, teamDamageReceived, gibs, selfkills, teamkills, teamgibs, timePlayed, xp, topshots[i][1], topshots[i][2], topshots[i][3], topshots[i][4], topshots[i][5], topshots[i][6], topshots[i][7], topshots[i][8], topshots[i][9], topshots[i][10], topshots[i][11], topshots[i][12], roundNum((tp/1000)/60, 1), topshots[i][13], topshots[i][14], roundNum((death_time_total[i] / 60000), 1), kd, topshots[i][15], math.floor(topshots[i][16]/1000), multikills[i][1], multikills[i][2], multikills[i][3], multikills[i][4], multikills[i][5], topshots[i][17], topshots[i][18]"""

param_list = [p.strip() for p in params.split(',')]
print(f"Parameters: {len(param_list)}")
print()

# List them out
print("Extended fields mapping (TAB-separated):")
for i, (fmt, param) in enumerate(zip(extended_fields, param_list[1:])):  # Skip stats[guid]
    print(f"  Field {i}: {fmt:6} = {param}")
