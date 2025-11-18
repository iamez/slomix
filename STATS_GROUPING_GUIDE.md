# 📊 Stats Organization & Grouping Strategy

**Date:** November 1, 2025  
**Purpose:** Organize 37+ stat fields into logical groups for better visualization

---

## 🎯 Current Stats (37+ Fields)

From your database schema (`player_comprehensive_stats` table):

### Core Combat (7 fields)
- `kills`
- `deaths`
- `damage_given`
- `damage_received`
- `team_damage_given`
- `team_damage_received`
- `gibs`

### Special Kills (4 fields)
- `self_kills`
- `team_kills`
- `team_gibs`
- `headshot_kills`

### Time Tracking (4 fields)
- `time_played_seconds` (PRIMARY)
- `time_played_minutes` (deprecated, calculated)
- `time_dead_minutes`
- `time_dead_ratio`
- time denied is also something  i would like to include and is something very importiant to me
### Performance Metrics (4 fields)
- `xp`
- `kd_ratio` (calculated: kills/deaths)
- `dpm` (calculated: damage_given / time_seconds * 60)
- `efficiency` (calculated: accuracy-like metric)

### Weapon Stats (2 fields)
- `bullets_fired` + bullets hit aswell 
- `accuracy` (calculated: hits/bullets_fired)

### Objective Stats (8 fields)
- `objectives_completed`
- `objectives_destroyed`
- `objectives_stolen`
- `objectives_returned`
- `dynamites_planted`
- `dynamites_defused`
- `constructions`
- `tank_meatshield`

### Support Stats (3 fields)
- `kill_assists`
- `times_revived`
- `revives_given`

### Advanced Stats (6 fields)
- `most_useful_kills`
- `useless_kills`
- `kill_steals`
- `double_kills`
- `triple_kills`
- `quad_kills`
- `multi_kills`
- `mega_kills`
- `killing_spree_best`
- `death_spree_worst`

---

## 🎨 Proposed Grouping for Visualizations

### Group 1: **COMBAT STATS** (Primary Kill Power)
**Best for:** Bar charts, line graphs  
**Fields:**
- Kills
- Deaths  
- Gibs
- Damage Given
- DPM (Damage Per Minute)

**Graph Type:** Grouped bar chart
```
[Player 1] | [Player 2] | [Player 3]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Kills      ████████ 45  ██████ 38   █████ 32
Deaths     ████ 22      ███ 19      ████ 22
Gibs       ██ 12        ██ 11       █ 8
Damage     ████████ 3420 ██████ 2980 █████ 2650
DPM        ████████ 156  ██████ 142  █████ 128
```

---

### Group 2: **TIME & SURVIVAL** (How Long You Played & Stayed Alive)
**Best for:** Stacked bar charts, area charts  
**Fields:**
- Time Played (minutes)
- Time Dead (minutes)
- Time Dead Ratio (%)
- Denied Playtime (how long you kept enemies dead)

**Graph Type:** Stacked bar chart
```
[Player 1]    [Player 2]    [Player 3]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Playing:        |  Playing:        |  Playing:
 ████████████  25m ██████████  20m  ████████  18m
 
 Dead:          |  Dead:           |  Dead:
 ███  5m        |  ████  8m        |  ████████  12m
 
Time Dead: 17%  |  Time Dead: 29%  |  Time Dead: 40%
```

---

### Group 3: **SUPPORT & TEAMWORK** (Helping Your Team)
**Best for:** Grouped bar chart, radar chart  
**Fields:**
- Revives Given
- Times Revived
- Kill Assists
- Constructions
- Tank/Meatshield

**Graph Type:** Grouped bar or Radar
```
         Revives  Times    Kill    Construct  Tank
         Given    Revived  Assists
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Player1   ████ 18  ███ 12  ████ 22  ██ 5      █ 3
Player2   ███ 15   ████ 15 ███ 18   ███ 8     ██ 4
Player3   ██ 10    █████ 20 ██ 12   █ 2       █ 1
```

---

### Group 4: **OBJECTIVES** (Mission Completion)
**Best for:** Pie chart, bar chart  
**Fields:**
- Objectives Completed
- Objectives Destroyed
- Objectives Stolen
- Objectives Returned
- Dynamites Planted
- Dynamites Defused

**Graph Type:** Stacked bar or pie
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Objectives Completed:      ████████ 8
Objectives Destroyed:      █████ 5
Objectives Stolen:         ███ 3
Objectives Returned:       ██ 2
Dynamites Planted:         ████ 4
Dynamites Defused:         ██ 2
```

---

### Group 5: **ACCURACY & EFFICIENCY** (How Precise You Are)
**Best for:** Circular target chart, bar chart  
**Fields:**
- Headshot Kills
- Bullets Fired
- Accuracy (%)
- Efficiency
- K/D Ratio

**Graph Type:** Target/bullseye chart or bar
```
       Headshot  Accuracy  Efficiency  K/D
       Kills     %         %          Ratio
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Player1  ███ 12  ████ 45%  ████ 82%   3.2
Player2  ██ 8    ███ 38%   ███ 75%    2.0
Player3  ██ 9    ██ 32%    ██ 68%     1.4
```

---

### Group 6: **SPECIAL EVENTS** (Multikills & Sprees)
**Best for:** Bar chart, badge display  
**Fields:**
- Double Kills
- Triple Kills
- Quad Kills
- Multi Kills (5 kills)
- Mega Kills (6+ kills)
- Killing Spree Best
- Death Spree Worst

**Graph Type:** Horizontal bar with icons
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 Killing Spree:    ████████ 12
💀 Death Spree:      ███ 5
⚡ Double Kills:     ████ 8
💥 Triple Kills:     ██ 4
🎯 Quad Kills:       █ 2
🚀 Multi Kills:      █ 1
💫 Mega Kills:       ░ 0
```

---

### Group 7: **NEGATIVE STATS** (Mistakes & Team Damage)
**Best for:** Small warning badges  
**Fields:**
- Self Kills
- Team Kills
- Team Gibs
- Team Damage Given
- Useless Kills
- Kill Steals

**Display:** Only show if non-zero (warning indicator)
```
⚠️ Negative Stats:
  • Team Kills: 2
  • Self Kills: 3
  • Team Damage: 450
```

---

## 🎨 Visual Layout for `!last_round maps`

### Map Performance Card Example:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 te_escape2 (4 games, 8 rounds)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Top Performers:
1. 🥇 vid     - 45K/14D (K/D: 3.21) | 156 DPM
2. 🥈 slomix  - 38K/19D (K/D: 2.00) | 142 DPM
3. 🥉 player3 - 32K/22D (K/D: 1.45) | 128 DPM

[GRAPH 1: Combat Stats]
           Kills  Deaths  Gibs  Damage  DPM
vid        ████   ██      ██    ████    ████
slomix     ███    ██      ██    ███     ███
player3    ███    ██      █     ███     ███

[GRAPH 2: Time & Survival]
           Time    Time    Dead
           Played  Dead    Ratio
vid        ████    █       12%
slomix     ████    ██      23%
player3    ███     ███     35%

[GRAPH 3: Support & Teamwork]
           Revives  Assists  Constructions
vid        ██       ███      █
slomix     ███      ████     ██
player3    ████     ██       █

[GRAPH 4: Objectives]
           Completed  Planted  Defused
vid        ██         ██       █
slomix     ███        ███      ██
player3    ██         █        █
```

---

## 💻 Implementation Code Structure

### Helper Function: Get Grouped Stats

```python
def get_grouped_stats(player_data):
    """Organize player stats into logical groups"""
    return {
        'combat': {
            'kills': player_data['kills'],
            'deaths': player_data['deaths'],
            'gibs': player_data['gibs'],
            'damage_given': player_data['damage_given'],
            'dpm': player_data['dpm']
        },
        'time_survival': {
            'time_played_min': player_data['time_played_minutes'],
            'time_dead_min': player_data['time_dead_minutes'],
            'time_dead_ratio': player_data['time_dead_ratio'],
            'denied_playtime_sec': player_data.get('denied_playtime', 0) / 1000
        },
        'support': {
            'revives_given': player_data['revives_given'],
            'times_revived': player_data['times_revived'],
            'kill_assists': player_data['kill_assists'],
            'constructions': player_data['constructions'],
            'tank_meatshield': player_data.get('tank_meatshield', 0)
        },
        'objectives': {
            'completed': player_data['objectives_completed'],
            'destroyed': player_data['objectives_destroyed'],
            'stolen': player_data.get('objectives_stolen', 0),
            'returned': player_data.get('objectives_returned', 0),
            'dynamites_planted': player_data['dynamites_planted'],
            'dynamites_defused': player_data['dynamites_defused']
        },
        'accuracy': {
            'headshot_kills': player_data['headshot_kills'],
            'bullets_fired': player_data['bullets_fired'],
            'accuracy_pct': player_data['accuracy'],
            'efficiency': player_data['efficiency'],
            'kd_ratio': player_data['kd_ratio']
        },
        'special_events': {
            'double_kills': player_data.get('double_kills', 0),
            'triple_kills': player_data.get('triple_kills', 0),
            'quad_kills': player_data.get('quad_kills', 0),
            'multi_kills': player_data.get('multi_kills', 0),
            'mega_kills': player_data.get('mega_kills', 0),
            'killing_spree': player_data.get('killing_spree_best', 0),
            'death_spree': player_data.get('death_spree_worst', 0)
        },
        'negative': {
            'self_kills': player_data['self_kills'],
            'team_kills': player_data['team_kills'],
            'team_gibs': player_data.get('team_gibs', 0),
            'team_damage': player_data['team_damage_given'],
            'useless_kills': player_data.get('useless_kills', 0),
            'kill_steals': player_data.get('kill_steals', 0)
        }
    }
```

### Create Grouped Bar Chart

```python
def create_grouped_combat_chart(players_data):
    """
    Create combat stats chart with: Kills, Deaths, Gibs, Damage, DPM
    """
    fig, ax = plt.subplots(figsize=(14, 6), facecolor=BG_DARK)
    ax.set_facecolor(BG_DARK)
    
    players = [p['name'] for p in players_data]
    x = np.arange(len(players))
    width = 0.15  # Width of each bar
    
    # Extract data
    kills = [p['kills'] for p in players_data]
    deaths = [p['deaths'] for p in players_data]
    gibs = [p['gibs'] for p in players_data]
    damage = [p['damage_given']/100 for p in players_data]  # Scale down
    dpm = [p['dpm']/10 for p in players_data]  # Scale down
    
    # Plot bars
    ax.bar(x - width*2, kills, width, label='Kills', color='#00FF88')
    ax.bar(x - width, deaths, width, label='Deaths', color='#FF4444')
    ax.bar(x, gibs, width, label='Gibs', color='#FF8800')
    ax.bar(x + width, damage, width, label='Damage (×100)', color='#FFAA00')
    ax.bar(x + width*2, dpm, width, label='DPM (×10)', color='#FFFF00')
    
    # Styling
    ax.set_xlabel('Player', color=TEXT_COLOR, fontsize=12)
    ax.set_ylabel('Value', color=TEXT_COLOR, fontsize=12)
    ax.set_title('Combat Stats: Kills • Deaths • Gibs • Damage • DPM', 
                 color=TEXT_COLOR, fontsize=14, pad=20)
    ax.set_xticks(x)
    ax.set_xticklabels(players, color=TEXT_COLOR)
    ax.legend(facecolor=BG_LIGHT, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR)
    ax.grid(True, axis='y', color=GRID_COLOR, alpha=0.3)
    ax.tick_params(colors=TEXT_COLOR)
    
    # Add value labels on bars
    for container in ax.containers:
        ax.bar_label(container, fmt='%.0f', padding=3, color=TEXT_COLOR, fontsize=8)
    
    for spine in ax.spines.values():
        spine.set_color(GRID_COLOR)
    
    plt.tight_layout()
    return save_graph_to_discord_file(fig, 'combat_stats.png')
```

---

## 🎯 Summary: Stat Groups

1. **Combat** (5) - Kills, Deaths, Gibs, Damage, DPM
2. **Time/Survival** (4) - Time Played, Time Dead, Ratio, Denied Time
3. **Support** (5) - Revives (given/received), Assists, Construction, Tank
4. **Objectives** (6) - Completed, Destroyed, Stolen, Returned, Dynamite (plant/defuse)
5. **Accuracy** (5) - Headshots, Bullets, Accuracy%, Efficiency, K/D
6. **Special Events** (7) - Multikills, Sprees
7. **Negative** (6) - Team damage, self kills, etc.

**Total: 38 fields organized into 7 logical groups!**

This makes graphs much cleaner and easier to understand. ✅
