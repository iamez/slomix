import sqlite3
import os
from datetime import datetime, timedelta

db_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "etlegacy_production.db",
)
print(f"Initializing DB at: {db_path}")

# Remove existing DB to ensure clean schema
if os.path.exists(db_path):
    try:
        os.remove(db_path)
        print("Removed existing database file.")
    except Exception as e:
        print(f"Could not remove existing database: {e}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Create rounds table
cursor.execute(
    """
CREATE TABLE IF NOT EXISTS rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    map_name TEXT,
    round_number INTEGER,
    actual_time TEXT,
    winner_team TEXT,
    round_outcome TEXT,
    round_date TEXT,
    round_time TEXT,
    round_status TEXT
);
"""
)

# Create player_comprehensive_stats table with round_id
cursor.execute(
    """
CREATE TABLE IF NOT EXISTS player_comprehensive_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    round_id INTEGER,
    session_date TEXT NOT NULL,
    map_name TEXT NOT NULL,
    round_number INTEGER NOT NULL,
    player_guid TEXT NOT NULL,
    player_name TEXT NOT NULL,
    clean_name TEXT NOT NULL,
    team INTEGER,
    kills INTEGER DEFAULT 0,
    deaths INTEGER DEFAULT 0,
    damage_given INTEGER DEFAULT 0,
    damage_received INTEGER DEFAULT 0,
    team_damage_given INTEGER DEFAULT 0,
    team_damage_received INTEGER DEFAULT 0,
    gibs INTEGER DEFAULT 0,
    self_kills INTEGER DEFAULT 0,
    team_kills INTEGER DEFAULT 0,
    team_gibs INTEGER DEFAULT 0,
    headshot_kills INTEGER DEFAULT 0,
    time_played_seconds INTEGER DEFAULT 0,
    time_played_minutes REAL DEFAULT 0,
    time_dead_minutes REAL DEFAULT 0,
    time_dead_ratio REAL DEFAULT 0,
    xp INTEGER DEFAULT 0,
    kd_ratio REAL DEFAULT 0,
    dpm REAL DEFAULT 0,
    efficiency REAL DEFAULT 0,
    bullets_fired INTEGER DEFAULT 0,
    accuracy REAL DEFAULT 0,
    kill_assists INTEGER DEFAULT 0,
    objectives_completed INTEGER DEFAULT 0,
    objectives_destroyed INTEGER DEFAULT 0,
    objectives_stolen INTEGER DEFAULT 0,
    objectives_returned INTEGER DEFAULT 0,
    dynamites_planted INTEGER DEFAULT 0,
    dynamites_defused INTEGER DEFAULT 0,
    times_revived INTEGER DEFAULT 0,
    revives_given INTEGER DEFAULT 0,
    most_useful_kills INTEGER DEFAULT 0,
    useless_kills INTEGER DEFAULT 0,
    kill_steals INTEGER DEFAULT 0,
    denied_playtime INTEGER DEFAULT 0,
    constructions INTEGER DEFAULT 0,
    tank_meatshield REAL DEFAULT 0,
    double_kills INTEGER DEFAULT 0,
    triple_kills INTEGER DEFAULT 0,
    quad_kills INTEGER DEFAULT 0,
    multi_kills INTEGER DEFAULT 0,
    mega_kills INTEGER DEFAULT 0,
    killing_spree_best INTEGER DEFAULT 0,
    death_spree_worst INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""
)

print("Seeding rounds table...")
today = datetime.now().strftime("%Y-%m-%d")
yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

rounds_data = [
    ("radar", 1, "14:20", "Allies", "Objective", today, "20:00", "completed"),
    ("radar", 2, "12:15", "Axis", "Full Hold", today, "20:30", "completed"),
    ("goldrush", 1, "08:45", "Axis", "Full Hold", yesterday, "19:00", "completed"),
    (
        "goldrush",
        2,
        "18:10",
        "Allies",
        "Objective",
        yesterday,
        "19:30",
        "completed",
    ),
    ("battery", 1, "15:00", "Allies", "Objective", yesterday, "21:00", "completed"),
]

cursor.executemany(
    """
INSERT INTO rounds (map_name, round_number, actual_time, winner_team, round_outcome, round_date, round_time, round_status)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""",
    rounds_data,
)

conn.commit()
print("Seeded 5 rounds.")

# Get the ID of the first round (radar 1) to link stats
cursor.execute(
    "SELECT id FROM rounds WHERE map_name='radar' AND round_number=1 LIMIT 1"
)
round_row = cursor.fetchone()
round_id = round_row[0] if round_row else 1

print("Seeding player_comprehensive_stats table...")

# Dummy data for Quick Leaders
# Added round_id (using the fetched round_id)
players_data = [
    (
        1,
        round_id,
        today,
        "radar",
        1,
        "guid1",
        "BAMBAM",
        "BAMBAM",
        1,
        42,
        18,
        4850,
        2000,
        520,
        2.33,
        485.0,
    ),
    (
        1,
        round_id,
        today,
        "radar",
        1,
        "guid2",
        "Snake",
        "Snake",
        2,
        45,
        30,
        5100,
        2500,
        480,
        1.50,
        510.0,
    ),
    (
        1,
        round_id,
        today,
        "radar",
        1,
        "guid3",
        "cronos",
        "cronos",
        1,
        38,
        22,
        4100,
        2100,
        480,
        1.72,
        410.0,
    ),
    (
        1,
        round_id,
        today,
        "radar",
        1,
        "guid4",
        "Viper",
        "Viper",
        1,
        25,
        25,
        3200,
        2800,
        350,
        1.00,
        320.0,
    ),
    (
        1,
        round_id,
        today,
        "radar",
        1,
        "guid5",
        "Ghost",
        "Ghost",
        2,
        18,
        40,
        2200,
        3000,
        150,
        0.45,
        220.0,
    ),
]

cursor.executemany(
    """
INSERT INTO player_comprehensive_stats (
    session_id, round_id, session_date, map_name, round_number, player_guid, player_name, clean_name, team,
    kills, deaths, damage_given, damage_received, xp, kd_ratio, dpm
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""",
    players_data,
)

conn.commit()
print("Seeded 5 player stats.")

conn.close()
