"""
Complete data pipeline investigation for vid's October 2nd stats.
Compares: Human-readable → c0rnp0rn3 files → Parser → Database
"""

import sqlite3
import sys

from community_stats_parser import C0RNP0RN3StatsParser

sys.path.insert(0, 'bot')

# Expected stats from human-readable attachments
expected = {
    'etl_adlernest_r1': {
        'kills': 9,
        'deaths': 3,
        'gibs': 3,
        'xp': 48,
        'assists': 1,
        'damage_given': 1328,
        'damage_received': 1105,
    },
    'etl_adlernest_r2': {
        'kills': 16,
        'deaths': 5,
        'gibs': 9,
        'xp': 51,
        'assists': 2,
        'damage_given': 2775,
        'damage_received': 1800,
    },
    'supply_r1': {
        'kills': 20,
        'deaths': 12,
        'gibs': 8,
        'xp': 95,
        'assists': 3,
        'damage_given': 2646,
        'damage_received': 2349,
    },
    'supply_r2': {
        'kills': 30,
        'deaths': 19,
        'gibs': 12,
        'xp': 111,
        'assists': 3,
        'damage_given': 4838,
        'damage_received': 4309,
    },
}


def parse_c0rnp0rn3_line(line):
    """Manually parse a player line from c0rnp0rn3 format"""
    parts = line.split('\\')
    if len(parts) < 4:
        return None

    guid = parts[0]
    name = parts[1]

    # Find the tab-separated section
    if '\t' not in line:
        return None

    weapon_section, tab_section = line.split('\t', 1)
    tab_fields = tab_section.strip().split('\t')

    if len(tab_fields) < 10:
        return None

    return {
        'guid': guid,
        'name': name,
        'damage_given': int(tab_fields[0]),
        'damage_received': int(tab_fields[1]),
        'gibs': int(tab_fields[2]),
        'xp': int(tab_fields[9]),
    }


print("=" * 80)
print("VID'S OCTOBER 2ND DATA PIPELINE INVESTIGATION")
print("=" * 80)
print()

# Test 1: etl_adlernest Round 1
print("=" * 80)
print("TEST 1: etl_adlernest Round 1")
print("=" * 80)
print()

file_path = "local_stats/2025-10-02-211808-etl_adlernest-round-1.txt"
print(f"📁 Reading: {file_path}")
print()

# Read c0rnp0rn3 file
with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

print("🔍 STEP 1: C0RNP0RN3 FORMAT (Raw File)")
print("-" * 80)
# Find vid's line
for line in content.split('\n'):
    if 'D8423F90' in line and 'vid' in line:
        print("Found vid's line:")
        print(line[:200] + "...")
        print()

        parsed = parse_c0rnp0rn3_line(line)
        if parsed:
            print("Manually parsed from c0rnp0rn3:")
            print(f"  Damage Given:    {parsed['damage_given']}")
            print(f"  Damage Received: {parsed['damage_received']}")
            print(f"  Gibs:            {parsed['gibs']}")
            print(f"  XP:              {parsed['xp']}")
        break
print()

# Parse with our parser
print("🔍 STEP 2: PARSER OUTPUT")
print("-" * 80)
parser = C0RNP0RN3StatsParser()
result = parser.parse_stats_file(file_path)

if result and 'players' in result:
    for player in result['players']:
        if player.get('guid') == 'D8423F90':
            print(f"Parser found vid:")
            print(f"  Name:            {player.get('name')}")
            print(f"  Kills:           {player.get('kills')}")
            print(f"  Deaths:          {player.get('deaths')}")

            if 'objective_stats' in player:
                stats = player['objective_stats']
                print(f"  Damage Given:    {stats.get('damage_given')}")
                print(f"  Damage Received: {stats.get('damage_received')}")
                print(f"  Gibs:            {stats.get('gibs')}")
                print(f"  XP:              {stats.get('xp')}")
                print(f"  Kill Assists:    {stats.get('kill_assists')}")
            break
print()

# Check database
print("🔍 STEP 3: DATABASE VALUE")
print("-" * 80)
conn = sqlite3.connect("etlegacy_production.db")
cursor = conn.cursor()

cursor.execute(
    """
    SELECT
        p.kills, p.deaths, p.gibs, p.xp, p.kill_assists,
        p.damage_given, p.damage_received
    FROM player_comprehensive_stats p
    JOIN sessions s ON p.session_id = s.id
    WHERE p.player_name = 'vid'
    AND s.session_date = '2025-10-02'
    AND s.map_name = 'etl_adlernest'
    AND s.round_number = 1
"""
)

db_result = cursor.fetchone()
if db_result:
    kills, deaths, gibs, xp, assists, dmg_given, dmg_recv = db_result
    print(f"Database stored:")
    print(f"  Kills:           {kills}")
    print(f"  Deaths:          {deaths}")
    print(f"  Gibs:            {gibs}")
    print(f"  XP:              {xp}")
    print(f"  Kill Assists:    {assists}")
    print(f"  Damage Given:    {dmg_given}")
    print(f"  Damage Received: {dmg_recv}")
print()

# Compare with expected
print("🔍 STEP 4: COMPARISON WITH HUMAN-READABLE ATTACHMENT")
print("-" * 80)
expected_r1 = expected['etl_adlernest_r1']
print(f"Expected from attachment:")
print(f"  Kills:           {expected_r1['kills']}")
print(f"  Deaths:          {expected_r1['deaths']}")
print(f"  Gibs:            {expected_r1['gibs']}")
print(f"  XP:              {expected_r1['xp']}")
print(f"  Kill Assists:    {expected_r1['assists']}")
print(f"  Damage Given:    {expected_r1['damage_given']}")
print(f"  Damage Received: {expected_r1['damage_received']}")
print()

if db_result:
    print("✅ MATCHES:")
    print(f"  Kills:           {kills == expected_r1['kills']} ({kills} vs {expected_r1['kills']})")
    print(
        f"  Deaths:          {
            deaths == expected_r1['deaths']} ({deaths} vs {
            expected_r1['deaths']})"
    )
    print(f"  Gibs:            {gibs == expected_r1['gibs']} ({gibs} vs {expected_r1['gibs']})")
    print(f"  XP:              {xp == expected_r1['xp']} ({xp} vs {expected_r1['xp']})")
    print(
        f"  Kill Assists:    {
            assists == expected_r1['assists']} ({assists} vs {
            expected_r1['assists']})"
    )
    print(
        f"  Damage Given:    {
            dmg_given == expected_r1['damage_given']} ({dmg_given} vs {
            expected_r1['damage_given']})"
    )
    print(
        f"  Damage Received: {
            dmg_recv == expected_r1['damage_received']} ({dmg_recv} vs {
            expected_r1['damage_received']})"
    )

print()
print()

# Test 2: supply Round 1
print("=" * 80)
print("TEST 2: supply Round 1")
print("=" * 80)
print()

file_path = "local_stats/2025-10-02-213333-supply-round-1.txt"
print(f"📁 Reading: {file_path}")
print()

# Read c0rnp0rn3 file
with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

print("🔍 STEP 1: C0RNP0RN3 FORMAT (Raw File)")
print("-" * 80)
for line in content.split('\n'):
    if 'D8423F90' in line and 'vid' in line:
        print("Found vid's line:")
        print(line[:200] + "...")
        print()

        parsed = parse_c0rnp0rn3_line(line)
        if parsed:
            print("Manually parsed from c0rnp0rn3:")
            print(f"  Damage Given:    {parsed['damage_given']}")
            print(f"  Damage Received: {parsed['damage_received']}")
            print(f"  Gibs:            {parsed['gibs']}")
            print(f"  XP:              {parsed['xp']}")
        break
print()

# Parse with our parser
print("🔍 STEP 2: PARSER OUTPUT")
print("-" * 80)
result = parser.parse_stats_file(file_path)

if result and 'players' in result:
    for player in result['players']:
        if player.get('guid') == 'D8423F90':
            print(f"Parser found vid:")
            if 'objective_stats' in player:
                stats = player['objective_stats']
                print(f"  Damage Given:    {stats.get('damage_given')}")
                print(f"  Damage Received: {stats.get('damage_received')}")
                print(f"  Gibs:            {stats.get('gibs')}")
                print(f"  XP:              {stats.get('xp')}")
                print(f"  Kill Assists:    {stats.get('kill_assists')}")
            break
print()

# Check database
print("🔍 STEP 3: DATABASE VALUE")
print("-" * 80)
cursor.execute(
    """
    SELECT
        p.kills, p.deaths, p.gibs, p.xp, p.kill_assists,
        p.damage_given, p.damage_received
    FROM player_comprehensive_stats p
    JOIN sessions s ON p.session_id = s.id
    WHERE p.player_name = 'vid'
    AND s.session_date = '2025-10-02'
    AND s.map_name = 'supply'
    AND s.round_number = 1
"""
)

db_result = cursor.fetchone()
if db_result:
    kills, deaths, gibs, xp, assists, dmg_given, dmg_recv = db_result
    print(f"Database stored:")
    print(f"  Kills:           {kills}")
    print(f"  Deaths:          {deaths}")
    print(f"  Gibs:            {gibs}")
    print(f"  XP:              {xp}")
    print(f"  Kill Assists:    {assists}")
    print(f"  Damage Given:    {dmg_given}")
    print(f"  Damage Received: {dmg_recv}")
print()

# Compare with expected
print("🔍 STEP 4: COMPARISON WITH HUMAN-READABLE ATTACHMENT")
print("-" * 80)
expected_r1 = expected['supply_r1']
print(f"Expected from attachment:")
print(f"  Kills:           {expected_r1['kills']}")
print(f"  Deaths:          {expected_r1['deaths']}")
print(f"  Gibs:            {expected_r1['gibs']}")
print(f"  XP:              {expected_r1['xp']}")
print(f"  Kill Assists:    {expected_r1['assists']}")
print(f"  Damage Given:    {expected_r1['damage_given']}")
print(f"  Damage Received: {expected_r1['damage_received']}")
print()

if db_result:
    print("✅ MATCHES:")
    print(f"  Kills:           {kills == expected_r1['kills']} ({kills} vs {expected_r1['kills']})")
    print(
        f"  Deaths:          {
            deaths == expected_r1['deaths']} ({deaths} vs {
            expected_r1['deaths']})"
    )
    print(f"  Gibs:            {gibs == expected_r1['gibs']} ({gibs} vs {expected_r1['gibs']})")
    print(f"  XP:              {xp == expected_r1['xp']} ({xp} vs {expected_r1['xp']})")
    print(
        f"  Kill Assists:    {
            assists == expected_r1['assists']} ({assists} vs {
            expected_r1['assists']})"
    )
    print(
        f"  Damage Given:    {
            dmg_given == expected_r1['damage_given']} ({dmg_given} vs {
            expected_r1['damage_given']})"
    )
    print(
        f"  Damage Received: {
            dmg_recv == expected_r1['damage_received']} ({dmg_recv} vs {
            expected_r1['damage_received']})"
    )

conn.close()

print()
print("=" * 80)
print("INVESTIGATION COMPLETE")
print("=" * 80)
