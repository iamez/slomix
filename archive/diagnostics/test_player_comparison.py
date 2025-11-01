#!/usr/bin/env python3
"""
Test the player comparison radar chart generation
Generates sample comparison without needing Discord
"""

import sqlite3
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

print("=" * 70)
print("  📊 Player Comparison Radar Chart - Test")
print("=" * 70)
print()

# Connect to database
db_path = 'bot/etlegacy_production.db'
conn = sqlite3.connect(db_path)

# Get two players with significant stats
cursor = conn.execute('''
    SELECT 
        player_guid,
        player_name,
        SUM(kills) as total_kills,
        SUM(deaths) as total_deaths,
        COUNT(DISTINCT session_id) as total_games
    FROM player_comprehensive_stats
    GROUP BY player_guid
    HAVING total_kills > 100
    ORDER BY total_kills DESC
    LIMIT 2
''')

players = cursor.fetchall()

if len(players) < 2:
    print("❌ Need at least 2 players with 100+ kills")
    exit(1)

print(f"📊 Comparing top 2 players:")
print(f"   1. {players[0][1]} ({players[0][2]:,} kills)")
print(f"   2. {players[1][1]} ({players[1][2]:,} kills)")
print()

# Function to get player stats
def get_player_stats(player_guid):
    # Get comprehensive stats
    cursor = conn.execute('''
        SELECT 
            SUM(kills) as total_kills,
            SUM(deaths) as total_deaths,
            COUNT(DISTINCT session_id) as total_games,
            SUM(damage_given) as total_damage,
            SUM(time_played_seconds) as total_time,
            SUM(headshot_kills) as total_headshots
        FROM player_comprehensive_stats
        WHERE player_guid = ?
    ''', (player_guid,))
    
    stats = cursor.fetchone()
    kills, deaths, games, damage, time_sec, headshots = stats
    
    # Get weapon stats
    cursor = conn.execute('''
        SELECT 
            SUM(hits) as total_hits,
            SUM(shots) as total_shots
        FROM weapon_comprehensive_stats
        WHERE player_guid = ?
    ''', (player_guid,))
    
    weapon_stats = cursor.fetchone()
    hits, shots = weapon_stats if weapon_stats else (0, 0)
    
    # Calculate metrics
    kd = kills / deaths if deaths > 0 else kills
    accuracy = (hits / shots * 100) if shots > 0 else 0
    dpm = (damage * 60 / time_sec) if time_sec > 0 else 0
    hs_pct = (headshots / kills * 100) if kills > 0 else 0
    
    return {
        'kd': kd,
        'accuracy': accuracy,
        'dpm': dpm,
        'hs_pct': hs_pct,
        'games': games
    }

# Get stats for both players
p1_guid, p1_name = players[0][0], players[0][1]
p2_guid, p2_name = players[1][0], players[1][1]

p1_stats = get_player_stats(p1_guid)
p2_stats = get_player_stats(p2_guid)

print(f"📈 {p1_name} Stats:")
print(f"   K/D: {p1_stats['kd']:.2f}")
print(f"   Accuracy: {p1_stats['accuracy']:.1f}%")
print(f"   DPM: {p1_stats['dpm']:.0f}")
print(f"   Headshot%: {p1_stats['hs_pct']:.1f}%")
print(f"   Games: {p1_stats['games']}")
print()

print(f"📈 {p2_name} Stats:")
print(f"   K/D: {p2_stats['kd']:.2f}")
print(f"   Accuracy: {p2_stats['accuracy']:.1f}%")
print(f"   DPM: {p2_stats['dpm']:.0f}")
print(f"   Headshot%: {p2_stats['hs_pct']:.1f}%")
print(f"   Games: {p2_stats['games']}")
print()

# Create radar chart
print("🎨 Generating radar chart...")

categories = ['K/D Ratio', 'Accuracy %', 'DPM/100', 'Headshot %', 'Games/10']

# Normalize values (scale to 0-10)
p1_values = [
    min(p1_stats['kd'], 5) * 2,  # K/D (max 5 = score 10)
    min(p1_stats['accuracy'], 50) / 5,  # Accuracy (50% = score 10)
    min(p1_stats['dpm'], 1000) / 100,  # DPM (1000 = score 10)
    min(p1_stats['hs_pct'], 50) / 5,  # Headshot% (50% = score 10)
    min(p1_stats['games'], 500) / 50,  # Games (500 = score 10)
]

p2_values = [
    min(p2_stats['kd'], 5) * 2,
    min(p2_stats['accuracy'], 50) / 5,
    min(p2_stats['dpm'], 1000) / 100,
    min(p2_stats['hs_pct'], 50) / 5,
    min(p2_stats['games'], 500) / 50,
]

# Number of variables
num_vars = len(categories)

# Compute angle for each axis
angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()

# Complete the circle
p1_values += p1_values[:1]
p2_values += p2_values[:1]
angles += angles[:1]

# Create figure
fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(projection='polar'))

# Plot data
ax.plot(angles, p1_values, 'o-', linewidth=2, label=p1_name, color='#3498db')
ax.fill(angles, p1_values, alpha=0.25, color='#3498db')

ax.plot(angles, p2_values, 'o-', linewidth=2, label=p2_name, color='#e74c3c')
ax.fill(angles, p2_values, alpha=0.25, color='#e74c3c')

# Fix axis to go in the right order
ax.set_theta_offset(np.pi / 2)
ax.set_theta_direction(-1)

# Draw axis lines for each angle and label
ax.set_xticks(angles[:-1])
ax.set_xticklabels(categories, size=12)

# Set y-axis limits and labels
ax.set_ylim(0, 10)
ax.set_yticks([2, 4, 6, 8, 10])
ax.set_yticklabels(['20%', '40%', '60%', '80%', '100%'], size=10)
ax.set_rlabel_position(180 / num_vars)

# Add title and legend
plt.title(f'Player Comparison\n{p1_name} vs {p2_name}', 
         size=16, weight='bold', pad=20)
plt.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=12)

# Add grid
ax.grid(True, linestyle='--', alpha=0.7)

# Save figure
output_dir = Path('temp')
output_dir.mkdir(exist_ok=True)
output_path = output_dir / 'test_comparison.png'

plt.tight_layout()
plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
plt.close()

print(f"✅ Radar chart saved: {output_path}")
print()

# Determine winners
print("🏆 Category Winners:")
if p1_stats['kd'] > p2_stats['kd']:
    print(f"   K/D: {p1_name} ({p1_stats['kd']:.2f} vs {p2_stats['kd']:.2f})")
elif p2_stats['kd'] > p1_stats['kd']:
    print(f"   K/D: {p2_name} ({p2_stats['kd']:.2f} vs {p1_stats['kd']:.2f})")
else:
    print(f"   K/D: Tie ({p1_stats['kd']:.2f})")

if p1_stats['accuracy'] > p2_stats['accuracy']:
    print(f"   Accuracy: {p1_name} ({p1_stats['accuracy']:.1f}% vs {p2_stats['accuracy']:.1f}%)")
elif p2_stats['accuracy'] > p1_stats['accuracy']:
    print(f"   Accuracy: {p2_name} ({p2_stats['accuracy']:.1f}% vs {p1_stats['accuracy']:.1f}%)")

if p1_stats['dpm'] > p2_stats['dpm']:
    print(f"   DPM: {p1_name} ({p1_stats['dpm']:.0f} vs {p2_stats['dpm']:.0f})")
elif p2_stats['dpm'] > p1_stats['dpm']:
    print(f"   DPM: {p2_name} ({p2_stats['dpm']:.0f} vs {p1_stats['dpm']:.0f})")

print()
print("=" * 70)
print("✅ Player comparison test complete!")
print()
print("💡 In Discord, use: !compare player1 player2")
print(f"   Example: !compare {p1_name} {p2_name}")

conn.close()
