import sqlite3
import sys

from community_stats_parser import C0RNP0RN3StatsParser

sys.path.append('bot')

# Test a single file import
DB_PATH = 'etlegacy_production.db'
FILE_PATH = 'local_stats/2025-10-02-211808-etl_adlernest-round-1.txt'

parser = C0RNP0RN3StatsParser()
result = parser.parse_stats_file(FILE_PATH)

if not result.get('success'):
    print(f"❌ Parser failed: {result.get('error')}")
    sys.exit(1)

print(f"✅ Parser succeeded")
print(f"   Map: {result['map_name']}")
print(f"   Round: {result['round_num']}")
print(f"   Players: {len(result.get('players', []))}")

if len(result.get('players', [])) > 0:
    player = result['players'][0]
    print(f"\n📊 First player sample:")
    print(f"   Name: {player.get('name')}")
    print(f"   GUID: {player.get('guid')}")
    print(f"   Kills: {player.get('kills')}")
    print(f"   Deaths: {player.get('deaths')}")

    # Check what objective_stats looks like
    obj_stats = player.get('objective_stats', {})
    print(f"\n📈 Objective stats keys: {list(obj_stats.keys())}")
    print(f"   Total obj_stats fields: {len(obj_stats)}")

    # Check for any unusual types
    for key, value in obj_stats.items():
        if not isinstance(value, (int, float, str, type(None))):
            print(f"⚠️  WARNING: {key} has type {type(value)}: {value}")

    # Now try the INSERT
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    session_id = 999  # Test ID
    session_date = '2025-10-02'

    # Calculate derived values
    time_seconds = player.get('time_played_seconds', 0)
    time_minutes = time_seconds / 60.0 if time_seconds > 0 else 0.0
    time_display = player.get('time_display', '0:00')
    dpm = player.get('dpm', 0.0)
    kills = player.get('kills', 0)
    deaths = player.get('deaths', 0)
    kd_ratio = kills / deaths if deaths > 0 else float(kills)

    # Build the VALUES tuple
    values = (
        session_id,
        session_date,
        result['map_name'],
        result['round_num'],
        player.get('guid', 'UNKNOWN'),
        player.get('name', 'Unknown'),
        player.get('name', 'Unknown'),
        player.get('team', 0),
        kills,
        deaths,
        player.get('damage_given', 0),
        player.get('damage_received', 0),
        player.get('team_damage_given', 0),
        player.get('team_damage_received', 0),
        obj_stats.get('gibs', 0),
        obj_stats.get('self_kills', 0),
        obj_stats.get('team_kills', 0),
        obj_stats.get('team_gibs', 0),
        time_seconds,
        time_minutes,
        time_display,
        obj_stats.get('xp', 0),
        dpm,
        kd_ratio,
        obj_stats.get('killing_spree', 0),
        obj_stats.get('death_spree', 0),
        obj_stats.get('kill_assists', 0),
        obj_stats.get('kill_steals', 0),
        player.get('headshots', 0),
        obj_stats.get('objectives_stolen', 0),
        obj_stats.get('objectives_returned', 0),
        obj_stats.get('dynamites_planted', 0),
        obj_stats.get('dynamites_defused', 0),
        obj_stats.get('times_revived', 0),
        obj_stats.get('revives_given', 0),
        obj_stats.get('bullets_fired', 0),
        obj_stats.get('tank_meatshield', 0),
        obj_stats.get('time_dead_ratio', 0),
        obj_stats.get('most_useful_kills', 0),
        obj_stats.get('denied_playtime', 0),
        obj_stats.get('useless_kills', 0),
        obj_stats.get('full_selfkills', 0),
        obj_stats.get('repairs_constructions', 0),
        obj_stats.get('double_kills', 0),
        obj_stats.get('triple_kills', 0),
        obj_stats.get('quad_kills', 0),
        obj_stats.get('multi_kills', 0),
        obj_stats.get('mega_kills', 0),
    )

    print(f"\n🔢 VALUES tuple length: {len(values)}")
    print(f"   Expected: 48")

    try:
        cursor.execute(
            '''
            INSERT INTO player_comprehensive_stats (
                session_id, session_date, map_name, round_number,
                player_guid, player_name, clean_name, team,
                kills, deaths, damage_given, damage_received,
                team_damage_given, team_damage_received,
                gibs, self_kills, team_kills, team_gibs,
                time_played_seconds, time_played_minutes, time_display,
                xp, dpm, kd_ratio,
                killing_spree_best, death_spree_worst,
                kill_assists, kill_steals, headshot_kills,
                objectives_stolen, objectives_returned,
                dynamites_planted, dynamites_defused, times_revived, revives_given,
                bullets_fired, tank_meatshield, time_dead_ratio,
                most_useful_kills, denied_playtime,
                useless_kills, full_selfkills, repairs_constructions,
                double_kills, triple_kills, quad_kills, multi_kills, mega_kills
            ) VALUES (
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?,
                ?, ?, ?,
                ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?, ?
            )
        ''',
            values,
        )
        conn.commit()
        print("✅ INSERT successful!")
    except Exception as e:
        print(f"❌ INSERT failed: {e}")
        print(f"   Error type: {type(e).__name__}")
    finally:
        conn.close()
