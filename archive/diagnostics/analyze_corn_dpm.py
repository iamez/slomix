#!/usr/bin/env python3
"""
Understand c0rnp0rn3.lua's actual DPM calculation by looking at raw file
"""

# Read first player line from Round 1 file
with open(
    'local_stats/2025-10-02-211808-etl_adlernest-round-1.txt',
    'r',
    encoding='utf-8',
    errors='ignore',
) as f:
    lines = f.readlines()

header = lines[0].strip()
print('=' * 80)
print('HEADER ANALYSIS')
print('=' * 80)
header_parts = header.split('\\')
print(f'Server: {header_parts[0]}')
print(f'Map: {header_parts[1]}')
print(f'Round: {header_parts[3]}')
print(f'Time Limit: {header_parts[6]}')
print(f'Actual Time: {header_parts[7]}')

print('\n' + '=' * 80)
print('PLAYER LINE ANALYSIS (vid)')
print('=' * 80)

# Find vid's line
for line in lines[1:]:
    if 'vid' in line:
        parts = line.split('\\')
        if len(parts) >= 5:
            guid = parts[0]
            name = parts[1]
            stats_section = parts[4]

            print(f'GUID: {guid}')
            print(f'Name: {name}')

            # Split weapon stats from extended stats (TAB-separated)
            if '\t' in stats_section:
                weapon_section, extended_section = stats_section.split('\t', 1)
                tab_fields = extended_section.split('\t')

                print(f'\nExtended fields (TAB-separated): {len(tab_fields)} fields')
                print('-' * 80)

                # Print key fields
                print(f'Field  0 (damage_given):        {tab_fields[0]}')
                print(f'Field  1 (damage_received):     {tab_fields[1]}')
                print(f'Field 21 (DPM from c0rn):       {tab_fields[21]}')
                print(f'Field 22 (time_played_minutes): {tab_fields[22]}')

                print('\n' + '=' * 80)
                print('CALCULATION COMPARISON')
                print('=' * 80)

                damage = float(tab_fields[0])
                dpm_corn = float(tab_fields[21])
                time_played = float(tab_fields[22])

                print(f'c0rnp0rn3.lua DPM (Field 21): {dpm_corn:.2f}')
                print(f'Our DPM (damage/time):        {damage / time_played:.2f}')
                print(f'Session time:                 3.85 minutes (3:51)')
                print(f'Player time:                  {time_played:.2f} minutes')

                # What if c0rn uses session time?
                session_time = 3.85  # 3:51 = 3.85 minutes
                dpm_session = damage / session_time
                print(f'\nIf using session time:        {dpm_session:.2f}')

                print('\n📊 VERDICT:')
                if abs(dpm_corn - (damage / time_played)) < 1:
                    print('  ✅ c0rnp0rn3.lua uses time_played_minutes (Field 22)')
                elif abs(dpm_corn - dpm_session) < 1:
                    print('  ⚠️  c0rnp0rn3.lua uses session time (3:51)')
                else:
                    print('  ❓ c0rnp0rn3.lua uses unknown calculation')

        break

print('\n' + '=' * 80)
print('ROUND 2 FILE ANALYSIS')
print('=' * 80)

with open(
    'local_stats/2025-10-02-212249-etl_adlernest-round-2.txt',
    'r',
    encoding='utf-8',
    errors='ignore',
) as f:
    lines = f.readlines()

header = lines[0].strip()
header_parts = header.split('\\')
print(f'Actual Time: {header_parts[7]}')

# Find SuperBoyy's line (should have high damage in Round 2)
for line in lines[1:]:
    if 'Super' in line:
        parts = line.split('\\')
        if len(parts) >= 5:
            name = parts[1]
            stats_section = parts[4]

            if '\t' in stats_section:
                weapon_section, extended_section = stats_section.split('\t', 1)
                tab_fields = extended_section.split('\t')

                damage = float(tab_fields[0])
                dpm_corn = float(tab_fields[21])
                time_played = float(tab_fields[22])

                print(f'\nPlayer: {name}')
                print(f'  Damage:              {damage:.0f}')
                print(f'  DPM (from c0rn):     {dpm_corn:.2f}')
                print(f'  time_played_minutes: {time_played:.2f}')
                print(
                    f'  Our DPM:             {
                        damage /
                        time_played if time_played > 0 else 0:.2f}'
                )

        break
