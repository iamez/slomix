# 📊 Graph Design Guide - ET:Legacy Stats Bot

**Date:** November 1, 2025  
**Inspired by:** DALL-E samples + existing DPM line graph

---

## 🎨 Graph Style Philosophy

### Core Principles:
1. **Clean and Readable** - Not cluttered
2. **Color-Coded** - Teams/players easily distinguishable
3. **Interactive Data** - Show exact values on hover
4. **Consistent Branding** - ET:Legacy theme (military colors)
5. **Dark Mode Friendly** - Works on Discord's dark theme

### Color Palette:
```python
# Team Colors
AXIS_RED = '#FF4444'
ALLIES_BLUE = '#4444FF'
NEUTRAL = '#888888'

# Performance Colors
EXCELLENT = '#00FF00'  # Green
GOOD = '#FFFF00'      # Yellow
AVERAGE = '#FFA500'   # Orange
POOR = '#FF0000'      # Red

# Background (Discord-friendly)
BG_DARK = '#2C2F33'
BG_LIGHT = '#36393F'
GRID_COLOR = '#40444B'
TEXT_COLOR = '#DCDDDE'
```

---

## 📈 Graph Types for `!last_round`

### 1. **DPM Line Graph** (Keep Current Style!) ✅
**When:** `!last_round` (main overview)  
**Shows:** DPM trends across all players in the round  
**Style:** Multi-line chart with player names

```python
def create_dpm_line_graph(session_data):
    """
    The existing graph you like - KEEP THIS!
    Shows DPM progression with yellow line for each player.
    """
    fig, ax = plt.subplots(figsize=(12, 6), facecolor=BG_DARK)
    ax.set_facecolor(BG_DARK)
    
    # Plot each player's DPM line
    for player in session_data['players']:
        ax.plot(
            player['rounds'],
            player['dpm_values'],
            marker='o',
            linewidth=2,
            label=player['name'],
            alpha=0.8
        )
    
    # Styling
    ax.set_xlabel('Round Number', color=TEXT_COLOR, fontsize=12)
    ax.set_ylabel('DPM', color=TEXT_COLOR, fontsize=12)
    ax.set_title('Damage Per Minute Trends', color=TEXT_COLOR, fontsize=14, pad=20)
    ax.grid(True, color=GRID_COLOR, alpha=0.3, linestyle='--')
    ax.legend(facecolor=BG_LIGHT, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR)
    ax.tick_params(colors=TEXT_COLOR)
    
    # Make spines match theme
    for spine in ax.spines.values():
        spine.set_color(GRID_COLOR)
    
    return save_graph_to_discord_file(fig, 'dpm_trends.png')
```

---

### 2. **Radar Chart** (Skill Breakdown) 🎯
**When:** `!last_round maps` - Per-player performance on a map  
**Shows:** Multiple skill dimensions (like your DALL-E examples)  
**Inspired by:** Image #3 (RANARI radar chart)

```python
def create_player_radar_chart(player_data):
    """
    Multi-dimensional player performance radar chart.
    Shows: Kills, Accuracy, Objectives, Support, Survival
    """
    categories = ['Kills', 'Accuracy', 'Objectives', 'Support', 'Survival']
    
    # Normalize values to 0-100 scale
    values = [
        normalize(player_data['kills'], 0, 50),      # Max 50 kills
        player_data['accuracy'],                      # Already 0-100
        normalize(player_data['objectives'], 0, 10), # Max 10 objectives
        normalize(player_data['revives'], 0, 20),    # Max 20 revives
        normalize(player_data['survival_rate'], 0, 100)  # Already percentage
    ]
    
    # Close the polygon
    values += values[:1]
    angles = [n / len(categories) * 2 * np.pi for n in range(len(categories))]
    angles += angles[:1]
    
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(projection='polar'), facecolor=BG_DARK)
    ax.set_facecolor(BG_DARK)
    
    # Plot data
    ax.plot(angles, values, 'o-', linewidth=2, color=ALLIES_BLUE, label=player_data['name'])
    ax.fill(angles, values, alpha=0.25, color=ALLIES_BLUE)
    
    # Styling
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, color=TEXT_COLOR, size=11)
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(['20', '40', '60', '80', '100'], color=TEXT_COLOR, size=9)
    ax.grid(True, color=GRID_COLOR, alpha=0.3)
    ax.set_title(f'{player_data["name"]} - Performance Profile', 
                 color=TEXT_COLOR, size=14, pad=20)
    
    return save_graph_to_discord_file(fig, 'player_radar.png')
```

---

### 3. **Grouped Bar Chart** (Map Comparison) 📊
**When:** `!last_round maps`  
**Shows:** Performance comparison across different maps  
**Inspired by:** Image #4 (Visual Performance Analytics)

```python
def create_map_comparison_bars(session_data):
    """
    Side-by-side bars comparing stats across maps.
    Left panel: Kills/Deaths/Gibs/DPM
    Right panel: Playtime/Time Dead/Revives
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6), facecolor=BG_DARK)
    
    maps = [m['name'] for m in session_data['maps']]
    x = np.arange(len(maps))
    width = 0.2
    
    # LEFT PANEL: Combat Stats
    ax1.set_facecolor(BG_DARK)
    ax1.bar(x - width*1.5, [m['kills'] for m in session_data['maps']], 
            width, label='Kills', color='#00FF88')
    ax1.bar(x - width*0.5, [m['deaths'] for m in session_data['maps']], 
            width, label='Deaths', color='#FF4444')
    ax1.bar(x + width*0.5, [m['gibs']/10 for m in session_data['maps']], 
            width, label='Gibs (scaled)', color='#FFAA00')
    ax1.bar(x + width*1.5, [m['dpm']/10 for m in session_data['maps']], 
            width, label='DPM (scaled)', color='#FFFF00')
    
    ax1.set_xlabel('Map', color=TEXT_COLOR, fontsize=12)
    ax1.set_ylabel('Count', color=TEXT_COLOR, fontsize=12)
    ax1.set_title('Kills • Deaths • Gibs • DPM', color=TEXT_COLOR, fontsize=13)
    ax1.set_xticks(x)
    ax1.set_xticklabels(maps, color=TEXT_COLOR, rotation=15)
    ax1.legend(facecolor=BG_LIGHT, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR)
    ax1.grid(True, axis='y', color=GRID_COLOR, alpha=0.3)
    ax1.tick_params(colors=TEXT_COLOR)
    
    # RIGHT PANEL: Support/Time Stats
    ax2.set_facecolor(BG_DARK)
    ax2.bar(x - width, [m['time_played'] for m in session_data['maps']], 
            width, label='Time Played (m)', color='#6666FF')
    ax2.bar(x, [m['time_dead'] for m in session_data['maps']], 
            width, label='Time Dead (m)', color='#FF6666')
    ax2.bar(x + width, [m['revives'] for m in session_data['maps']], 
            width, label='Revives', color='#AA66FF')
    
    ax2.set_xlabel('Map', color=TEXT_COLOR, fontsize=12)
    ax2.set_ylabel('Value', color=TEXT_COLOR, fontsize=12)
    ax2.set_title('Playtime • Time Dead • Revives', color=TEXT_COLOR, fontsize=13)
    ax2.set_xticks(x)
    ax2.set_xticklabels(maps, color=TEXT_COLOR, rotation=15)
    ax2.legend(facecolor=BG_LIGHT, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR)
    ax2.grid(True, axis='y', color=GRID_COLOR, alpha=0.3)
    ax2.tick_params(colors=TEXT_COLOR)
    
    # Style spines
    for ax in [ax1, ax2]:
        for spine in ax.spines.values():
            spine.set_color(GRID_COLOR)
    
    plt.tight_layout()
    return save_graph_to_discord_file(fig, 'map_comparison.png')
```

---

### 4. **Stacked Area Chart** (Team Performance Over Time) 🌊
**When:** `!last_round graphs`  
**Shows:** How team performance evolved throughout the round

```python
def create_team_performance_timeline(session_data):
    """
    Stacked area chart showing team kills over session timeline.
    """
    fig, ax = plt.subplots(figsize=(14, 6), facecolor=BG_DARK)
    ax.set_facecolor(BG_DARK)
    
    rounds = range(1, len(session_data['rounds']) + 1)
    axis_kills = [r['axis_kills'] for r in session_data['rounds']]
    allies_kills = [r['allies_kills'] for r in session_data['rounds']]
    
    # Stacked area
    ax.fill_between(rounds, 0, axis_kills, 
                     alpha=0.7, color=AXIS_RED, label='Axis')
    ax.fill_between(rounds, axis_kills, 
                     [a+b for a,b in zip(axis_kills, allies_kills)],
                     alpha=0.7, color=ALLIES_BLUE, label='Allies')
    
    # Styling
    ax.set_xlabel('Round', color=TEXT_COLOR, fontsize=12)
    ax.set_ylabel('Total Kills', color=TEXT_COLOR, fontsize=12)
    ax.set_title('Team Performance Timeline', color=TEXT_COLOR, fontsize=14, pad=20)
    ax.legend(facecolor=BG_LIGHT, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR)
    ax.grid(True, color=GRID_COLOR, alpha=0.3, linestyle='--')
    ax.tick_params(colors=TEXT_COLOR)
    
    for spine in ax.spines.values():
        spine.set_color(GRID_COLOR)
    
    return save_graph_to_discord_file(fig, 'team_timeline.png')
```

---

### 5. **Heatmap** (Player Activity Map) 🔥
**When:** `!last_round graphs`  
**Shows:** Which players performed best on which maps

```python
def create_player_map_heatmap(session_data):
    """
    Heatmap showing player KD ratios across different maps.
    Rows = Players, Columns = Maps, Color = KD ratio
    """
    import seaborn as sns
    
    # Build matrix
    players = list(set(p['name'] for r in session_data['rounds'] for p in r['players']))
    maps = list(set(r['map'] for r in session_data['rounds']))
    
    matrix = np.zeros((len(players), len(maps)))
    
    for i, player in enumerate(players):
        for j, map_name in enumerate(maps):
            # Calculate average KD for this player on this map
            kd_values = []
            for round_data in session_data['rounds']:
                if round_data['map'] == map_name:
                    player_data = next((p for p in round_data['players'] if p['name'] == player), None)
                    if player_data:
                        kd_values.append(player_data['kd_ratio'])
            matrix[i][j] = np.mean(kd_values) if kd_values else 0
    
    # Create heatmap
    fig, ax = plt.subplots(figsize=(12, 8), facecolor=BG_DARK)
    
    sns.heatmap(matrix, 
                xticklabels=maps, 
                yticklabels=players,
                cmap='RdYlGn',  # Red (bad) -> Yellow -> Green (good)
                center=1.0,      # Center on 1.0 KD
                annot=True,      # Show values
                fmt='.2f',
                cbar_kws={'label': 'K/D Ratio'},
                ax=ax)
    
    ax.set_title('Player Performance by Map', color=TEXT_COLOR, fontsize=14, pad=20)
    ax.set_xlabel('Map', color=TEXT_COLOR, fontsize=12)
    ax.set_ylabel('Player', color=TEXT_COLOR, fontsize=12)
    
    plt.tight_layout()
    return save_graph_to_discord_file(fig, 'player_map_heatmap.png')
```

---

### 6. **Circular Progress/Target Chart** 🎯
**When:** Individual player stats  
**Shows:** Progress towards milestones (inspired by image #1 & #2)

```python
def create_target_accuracy_chart(player_data):
    """
    Circular 'bullseye' chart showing accuracy zones.
    Center = Headshots, Rings = Body shots, Outer = Misses
    """
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(projection='polar'), facecolor=BG_DARK)
    ax.set_facecolor(BG_DARK)
    
    # Data
    headshots = player_data['headshots']
    bodyshots = player_data['kills'] - player_data['headshots']
    shots_fired = player_data['bullets_fired']
    hits = player_data['kills']
    misses = shots_fired - hits
    
    # Calculate percentages for sizing
    total = shots_fired
    head_pct = (headshots / total) * 100
    body_pct = (bodyshots / total) * 100
    miss_pct = (misses / total) * 100
    
    # Create concentric circles
    theta = np.linspace(0, 2 * np.pi, 100)
    
    # Outer ring (misses)
    r_outer = np.full_like(theta, 100)
    ax.fill_between(theta, 0, r_outer, alpha=0.3, color='#444444', label=f'Misses ({miss_pct:.1f}%)')
    
    # Middle ring (body shots)
    r_middle = np.full_like(theta, 70)
    ax.fill_between(theta, 0, r_middle, alpha=0.5, color=AVERAGE, label=f'Body Shots ({body_pct:.1f}%)')
    
    # Center (headshots)
    r_center = np.full_like(theta, 40)
    ax.fill_between(theta, 0, r_center, alpha=0.7, color=EXCELLENT, label=f'Headshots ({head_pct:.1f}%)')
    
    # Remove radial ticks
    ax.set_yticks([])
    ax.set_xticks([])
    ax.spines['polar'].set_visible(False)
    
    ax.set_title(f'{player_data["name"]} - Accuracy Profile', 
                 color=TEXT_COLOR, size=14, pad=30)
    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1),
              facecolor=BG_LIGHT, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR)
    
    return save_graph_to_discord_file(fig, 'accuracy_target.png')
```

---

## 🎨 Complete Graph Suite for `!last_round`

### `!last_round` (overview)
- ✅ **DPM Line Graph** (keep current - you like it!)

### `!last_round maps`
- **Per-Map Bar Chart** - Kills/Deaths/Objectives for each map
- **Radar Chart** - Top 3 players' skill breakdown per map
- **Win Rate Pie Chart** - Defender vs Attacker wins per map

### `!last_round rounds`
- **Timeline Graph** - Visual timeline of all rounds with outcomes
- **Round Duration Chart** - Bar chart of round lengths

### `!last_round graphs`
- **DPM Trend Lines** - All players' DPM over session
- **K/D Comparison Bars** - Side-by-side player comparison
- **Kill Distribution Pie** - Who got what % of kills
- **Team Performance Area** - Stacked area chart of team scores
- **Player-Map Heatmap** - Performance matrix
- **Accuracy Target Chart** - Circular accuracy visualization

---

## 💻 Helper Functions

```python
def save_graph_to_discord_file(fig, filename):
    """
    Save matplotlib figure to BytesIO and return Discord File object.
    """
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=100, bbox_inches='tight', facecolor=BG_DARK)
    buf.seek(0)
    plt.close(fig)
    return discord.File(buf, filename=filename)

def normalize(value, min_val, max_val):
    """Normalize value to 0-100 scale"""
    if max_val == min_val:
        return 0
    return max(0, min(100, ((value - min_val) / (max_val - min_val)) * 100))

def get_performance_color(kd_ratio):
    """Get color based on K/D performance"""
    if kd_ratio >= 2.0:
        return EXCELLENT
    elif kd_ratio >= 1.5:
        return GOOD
    elif kd_ratio >= 1.0:
        return AVERAGE
    else:
        return POOR
```

---

## 📦 Required Dependencies

Add to `requirements.txt`:
```txt
matplotlib>=3.7.0
numpy>=1.24.0
seaborn>=0.12.0  # For heatmaps
scipy>=1.10.0    # For advanced statistics
```

---

## 🎯 Implementation Priority

### Phase 1 (Keep working):
1. ✅ DPM Line Graph (already exists - keep it!)

### Phase 2 (Add to maps view):
2. Map comparison bar chart
3. Per-map radar charts for top players

### Phase 3 (Add to graphs view):
4. K/D comparison bars
5. Kill distribution pie chart
6. Team performance timeline

### Phase 4 (Advanced):
7. Player-map heatmap
8. Accuracy target charts
9. Custom animations (if you want to get fancy!)

---

## 🎨 Example Output Order

When user types `!last_round graphs`:

```
📈 Statistical Analysis - October 31, 2025
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Generating graphs... This may take a moment.

[Graph 1: DPM Trend Lines]
Shows how each player's DPM changed throughout the round

[Graph 2: K/D Comparison]  
Side-by-side bar comparison of all players

[Graph 3: Kill Distribution]
Pie chart showing % of total kills per player

[Graph 4: Team Performance Timeline]
Stacked area chart of Axis vs Allies over time

[Graph 5: Player-Map Heatmap]
Which players dominated which maps

[Embed: Statistical Summary]
Most Played Map:     te_escape2 (50% of rounds)
Longest Round:       etl_adlernest R1 (14:32)
...
```

---

## 🚀 Ready to Implement?

The foundation is all here! When you're ready to code:

1. **Start with Phase 1** - Verify existing DPM graph still works
2. **Add Phase 2** - Map comparison bars (easiest)
3. **Add Phase 3** - More complex visualizations
4. **Polish Phase 4** - Advanced features

Want me to help implement any specific graph first? I can write the complete code! 🎨
