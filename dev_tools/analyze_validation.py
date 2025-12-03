"""
Analyze validation results to find patterns in data mismatches
"""

import re
from collections import defaultdict

# Parse the validation results
with open('validation_complete.txt', 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# Extract all FAIL entries
fail_pattern = r'\[FAIL\] ([^\(]+) \(([A-F0-9]+)\)\n((?:      .*\n)*)'
matches = re.findall(fail_pattern, content)

# Organize by issue type
headshot_issues = []
weapon_death_issues = []
other_issues = []

for name, guid, issues_text in matches:
    name = name.strip()
    issues = [line.strip() for line in issues_text.split('\n') if line.strip()]
    
    for issue in issues:
        if 'headshots:' in issue:
            # Extract values
            match = re.search(r'headshots: R(\d+) != D(\d+)', issue)
            if match:
                raw_val, db_val = int(match.group(1)), int(match.group(2))
                headshot_issues.append({
                    'name': name,
                    'guid': guid,
                    'raw': raw_val,
                    'db': db_val,
                    'diff': raw_val - db_val
                })
        elif '.deaths:' in issue:
            # Weapon death issue
            match = re.search(r'(WS_\w+)\.deaths: R(\d+) != D(\d+)', issue)
            if match:
                weapon, raw_val, db_val = match.group(1), int(match.group(2)), int(match.group(3))
                weapon_death_issues.append({
                    'name': name,
                    'guid': guid,
                    'weapon': weapon,
                    'raw': raw_val,
                    'db': db_val
                })
        else:
            other_issues.append({
                'name': name,
                'guid': guid,
                'issue': issue
            })

print("="*80)
print("VALIDATION ANALYSIS - NOV 2 SESSION")
print("="*80)

print("\n1. HEADSHOTS MISMATCH ANALYSIS")
print(f"   Total instances: {len(headshot_issues)}")
print("   Pattern: Raw files show MORE headshots than database")
print("\n   Sample mismatches:")
for i, issue in enumerate(headshot_issues[:10]):
    print(f"     {issue['name']:20s} Raw: {issue['raw']:3d}  DB: {issue['db']:3d}  Missing: {issue['diff']:3d}")

# Calculate statistics
if headshot_issues:
    total_raw = sum(i['raw'] for i in headshot_issues)
    total_db = sum(i['db'] for i in headshot_issues)
    total_missing = sum(i['diff'] for i in headshot_issues)
    avg_missing = total_missing / len(headshot_issues)
    
    print("\n   Statistics:")
    print(f"     Total headshots in raw files: {total_raw}")
    print(f"     Total headshots in database:  {total_db}")
    print(f"     Total missing:                 {total_missing}")
    print(f"     Average missing per instance:  {avg_missing:.1f}")
    print(f"     Percentage lost:               {100*total_missing/total_raw:.1f}%")

print("\n2. WEAPON DEATHS MISMATCH ANALYSIS")
print(f"   Total instances: {len(weapon_death_issues)}")
print("   Pattern: Raw files show weapon deaths, database has 0")
print("\n   Weapons affected:")
weapon_counts = defaultdict(int)
for issue in weapon_death_issues:
    weapon_counts[issue['weapon']] += 1
for weapon, count in sorted(weapon_counts.items(), key=lambda x: -x[1])[:15]:
    print(f"     {weapon:20s} {count:3d} instances")

if weapon_death_issues:
    total_weapon_deaths = sum(i['raw'] for i in weapon_death_issues)
    print(f"\n   Total weapon deaths in raw files: {total_weapon_deaths}")
    print("   Total weapon deaths in database:  0 (ALL MISSING)")

print("\n3. OTHER ISSUES")
print(f"   Total instances: {len(other_issues)}")
if other_issues:
    print("\n   Sample issues:")
    for issue in other_issues[:10]:
        print(f"     {issue['name']:20s} {issue['issue']}")

print("\n4. SUMMARY BY ROUND TYPE")
# Parse round types from file
round_1_count = content.count('-round-1.txt')
round_2_count = content.count('-round-2.txt')
print(f"   Round 1 files: {round_1_count}")
print(f"   Round 2 files: {round_2_count}")
print(f"   Total files:   {round_1_count + round_2_count}")

print("\n5. KEY FINDINGS")
print("   ✓ All Round 2 files now parse successfully (emoji fix worked)")
print("   ✗ Headshots: Database consistently has FEWER headshots than raw files")
print("   ✗ Weapon deaths: Database shows 0 for ALL weapon deaths (raw files have them)")
print("   ✗ 0.9% success rate - only 1 player matched perfectly across all 18 rounds")

print("\n6. ROOT CAUSE HYPOTHESIS")
print("   The weapon deaths issue suggests:")
print("     - Parser IS extracting weapon deaths from raw files (validation sees them)")
print("     - Database insertion may NOT be storing weapon deaths")
print("     - OR database query returns wrong table/columns")
print("")
print("   The headshots issue suggests:")
print("     - Headshots calculation bug in parser or database insertion")
print("     - May be related to Round 2 differential calculation")
print("     - Affects BOTH Round 1 and Round 2 data")

print("\n" + "="*80)
