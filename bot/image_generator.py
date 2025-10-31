"""
🎨 ET:Legacy Stats Image Generator
Creates beautiful stat cards and visualizations for Discord bot
"""

import io

import matplotlib
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont

matplotlib.use('Agg')


class StatsImageGenerator:
    """Generate professional-looking stat images"""

    # Discord dark theme colors
    COLORS = {
        'bg_dark': '#2b2d31',
        'bg_medium': '#1e1f22',
        'bg_light': '#313338',
        'text_white': '#ffffff',
        'text_gray': '#b5bac1',
        'text_dim': '#80848e',
        'accent_blue': '#5865f2',
        'accent_green': '#57f287',
        'accent_red': '#ed4245',
        'accent_yellow': '#fee75c',
        'accent_pink': '#eb459e',
    }

    def __init__(self):
        self.width = 1400
        self.height = 900

    def create_session_overview(
        self,
        session_data,
        top_players,
        team_data,
        team_names,
    ):
        """
        Create comprehensive session overview image

        Args:
            session_data: dict with maps, rounds, players, date
            top_players: list of top 5 player stats
            team_data: dict with team1/team2 stats and MVPs
            team_names: tuple of (team1_name, team2_name)
        """
        # Allow dynamic height based on number of players (keep a minimum)
        num_players = len(top_players) if top_players else 0
        extra_height = max(0, (num_players - 5)) * 36
        img_h = max(self.height, 900 + extra_height)

        # Create base image
        img = Image.new('RGB', (self.width, img_h), self.COLORS['bg_dark'])
        draw = ImageDraw.Draw(img)

        # Try to load fonts, fallback to default
        try:
            title_font = ImageFont.truetype("arial.ttf", 48)
            header_font = ImageFont.truetype("arialbd.ttf", 32)
            stat_font = ImageFont.truetype("arial.ttf", 24)
            small_font = ImageFont.truetype("arial.ttf", 18)
        except BaseException:
            title_font = ImageFont.load_default()
            header_font = ImageFont.load_default()
            stat_font = ImageFont.load_default()
            small_font = ImageFont.load_default()

        y_pos = 30

        # Title
        title = f"📊 Session Summary: {session_data.get('date', '')}"
        draw.text(
            (50, y_pos),
            title,
            fill=self.COLORS['text_white'],
            font=title_font,
        )
        y_pos += 70

        # Session info bar
        info_text = (
            f"{session_data.get('maps', 0)} maps  •  "
            f"{session_data.get('rounds', 0)} rounds  •  "
            f"{session_data.get('players', 0)} players"
        )
        draw.text(
            (50, y_pos),
            info_text,
            fill=self.COLORS['text_gray'],
            font=stat_font,
        )
        y_pos += 50

        # Maps played (if provided, list them)
        maps_list = (
            session_data.get('maps_list')
            or session_data.get('maps_names')
            or []
        )
        if maps_list:
            maps_display = " • ".join(maps_list)
            # truncate if too long
            if len(maps_display) > 240:
                maps_display = (
                    ", ".join(maps_list[:8]) + f" (+{len(maps_list) - 8} more)"
                )
            draw.text(
                (50, y_pos),
                f"🗺️ Maps: {maps_display}",
                fill=self.COLORS['text_dim'],
                font=small_font,
            )
            y_pos += 36

        # Divider line
        rect = [50, y_pos, self.width - 50, y_pos + 2]
        draw.rectangle(rect, fill=self.COLORS['bg_light'])
        y_pos += 30

        # Players (show all players, formatted like the text embed)
        draw.text(
            (50, y_pos),
            "🏆 Players",
            fill=self.COLORS['accent_yellow'],
            font=header_font,
        )
        y_pos += 44

        medals = ["🥇", "🥈", "🥉"]
        for i, player in enumerate(top_players or []):
            if isinstance(player, dict):
                name = player.get('name')
            else:
                name = player[0] if len(player) > 0 else 'Unknown'
            # Medal or ranking
            prefix = medals[i] if i < 3 else f"{i+1}."
            name_text = f"{prefix} {name}"
            draw.text(
                (70, y_pos),
                name_text,
                fill=self.COLORS['text_white'],
                font=stat_font,
            )
            y_pos += 28

            # Extract stats fields flexibly
            if isinstance(player, dict):
                kills = player.get('kills', 0)
                deaths = player.get('deaths', 0)
                kd = player.get('kd', (kills / deaths) if deaths else kills)
                dpm = player.get('dpm', 0)
                acc = player.get('acc', 0)
                hits = player.get('hits', 0)
                shots = player.get('shots', 0)
                hs = player.get('hs', 0)
                playtime = player.get('playtime', 0)
                time_dead = player.get('time_dead_minutes', None)
                gibs = player.get('gibs', 0)
                revives = player.get('revives', 0)
            else:
                # Tuple fallback (older callers)
                kills = player[1] if len(player) > 1 else 0
                deaths = player[2] if len(player) > 2 else 0
                kd = (kills / deaths) if deaths else kills
                dpm = player[3] if len(player) > 3 else 0
                playtime = (
                    player[4] / 60
                ) if len(player) > 4 and player[4] else 0
                time_dead = (
                    player[5] / 60
                ) if len(player) > 5 and player[5] else None
                hits = player[6] if len(player) > 6 else 0
                shots = player[7] if len(player) > 7 else 0
                hs = player[8] if len(player) > 8 else 0
                # compute accuracy percentage when using tuple fallback
                acc = (hits / shots * 100) if shots else 0
                gibs = player[9] if len(player) > 9 else 0
                revives = player[10] if len(player) > 10 else 0

            # Line 1: core combat stats
            acc_part = f"{acc:.1f}% ACC ({int(hits)}/{int(shots)})"
            stats1 = (
                f"{int(kills)}K/{int(deaths)}D ({kd:.2f})  •  "
                f"{int(dpm)} DPM  •  {acc_part}"
            )
            draw.text(
                (100, y_pos),
                stats1,
                fill=self.COLORS['text_gray'],
                font=small_font,
            )
            y_pos += 22

            # Line 2: HS, playtime, time dead, gibs, revives
            # Format playtime as H:MM
            try:
                mins = int(playtime)
                hours = mins // 60
                mins_rem = mins % 60
                playtime_str = (
                    f"{hours}:{mins_rem:02d}"
                    if hours
                    else f"{mins}m"
                )
            except Exception:
                playtime_str = f"{playtime:.0f}m"

            time_dead_str = ""
            if time_dead is not None:
                try:
                    td_mins = int(time_dead)
                    td_h = td_mins // 60
                    td_m = td_mins % 60
                    time_dead_str = (
                        f"💀 {td_h}:{td_m:02d}"
                        if td_h
                        else f"💀 {td_m}m"
                    )
                except Exception:
                    time_dead_str = f"💀 {time_dead:.0f}m"

            hs_line = f"{int(hs)} HS ({(hs / hits * 100) if hits else 0:.1f}%)"
            extras = []
            if gibs:
                extras.append(f"🦴 {int(gibs)} GIBS")
            if revives:
                extras.append(f"💉 {int(revives)} REV")

            stats2 = f"{hs_line} • ⏱️ {playtime_str} {time_dead_str}"
            if extras:
                stats2 += " • " + " • ".join(extras)

            draw.text(
                (100, y_pos),
                stats2,
                fill=self.COLORS['text_dim'],
                font=small_font,
            )
            y_pos += 32

        # Team Analytics Section
        y_pos += 20
        rect = [50, y_pos, self.width - 50, y_pos + 2]
        draw.rectangle(rect, fill=self.COLORS['bg_light'])
        y_pos += 30

        team1_name, team2_name = team_names
        title_text = f"⚔️ {team1_name} vs {team2_name}"
        draw.text(
            (50, y_pos),
            title_text,
            fill=self.COLORS['accent_red'],
            font=header_font,
        )
        y_pos += 50

        # Team stats side by side
        col1_x = 70
        col2_x = self.width // 2 + 50

        # Team 1
        team1 = team_data['team1']
        draw.text(
            (col1_x, y_pos),
            f"🔴 {team1_name}",
            fill=self.COLORS['accent_red'],
            font=stat_font,
        )
        y_temp = y_pos + 35
        team1_kd = f"K/D: {team1.get('kd', 0):.2f}  •  "
        team1_damage = f"{team1.get('damage', 0):,} Damage"
        team1_kills = f"{team1.get('kills', 0):,} Kills"
        team1_deaths = f"{team1.get('deaths', 0):,} Deaths"
        team1_kills_deaths = f"{team1_kills}  •  {team1_deaths}"
        team1_stats = f"{team1_kills_deaths}\n{team1_kd}{team1_damage}"
        for line in team1_stats.split('\n'):
            draw.text(
                (col1_x, y_temp),
                line,
                fill=self.COLORS['text_gray'],
                font=small_font,
            )
            y_temp += 25

        # MVP
        if 'mvp' in team1:
            mvp = team1['mvp']
            mvp_text = (
                f"MVP: {mvp.get('name', '')}\n"
                f"{mvp.get('kd', 0):.2f} K/D  •  {mvp.get('dpm', 0):.0f} DPM"
            )
            y_temp += 10
            for line in mvp_text.split('\n'):
                draw.text(
                    (col1_x, y_temp),
                    line,
                    fill=self.COLORS['accent_green'],
                    font=small_font,
                )
                y_temp += 23

        # Team 2
        team2 = team_data['team2']
        draw.text(
            (col2_x, y_pos),
            f"🔵 {team2_name}",
            fill=self.COLORS['accent_blue'],
            font=stat_font,
        )
        y_temp = y_pos + 35
        team2_kd = f"K/D: {team2.get('kd', 0):.2f}  •  "
        team2_damage = f"{team2.get('damage', 0):,} Damage"
        team2_kills = f"{team2.get('kills', 0):,} Kills"
        team2_deaths = f"{team2.get('deaths', 0):,} Deaths"
        team2_kills_deaths = f"{team2_kills}  •  {team2_deaths}"
        team2_stats = f"{team2_kills_deaths}\n{team2_kd}{team2_damage}"
        for line in team2_stats.split('\n'):
            draw.text(
                (col2_x, y_temp),
                line,
                fill=self.COLORS['text_gray'],
                font=small_font,
            )
            y_temp += 25

        # MVP
        if 'mvp' in team2:
            mvp = team2['mvp']
            mvp_text = (
                f"MVP: {mvp.get('name', '')}\n"
                f"{mvp.get('kd', 0):.2f} K/D  •  {mvp.get('dpm', 0):.0f} DPM"
            )
            y_temp += 10
            for line in mvp_text.split('\n'):
                draw.text(
                    (col2_x, y_temp),
                    line,
                    fill=self.COLORS['accent_green'],
                    font=small_font,
                )
                y_temp += 23

        # Save to bytes
        buf = io.BytesIO()
        img.save(buf, format='PNG', optimize=True)
        buf.seek(0)
        return buf

    def create_performance_graphs(self, player_data):
        """Create matplotlib performance graphs"""
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
        fig.patch.set_facecolor(self.COLORS['bg_dark'])

        names = [p['name'] for p in player_data]
        kills_data = [p['kills'] for p in player_data]
        deaths_data = [p['deaths'] for p in player_data]
        dpm_data = [p['dpm'] for p in player_data]

        # Graph 1: Kills, Deaths, DPM
        x = range(len(names))
        width = 0.25

        bars1 = ax1.bar(
            [i - width for i in x],
            kills_data,
            width,
            label='Kills',
            color=self.COLORS['accent_blue'],
            alpha=0.9,
        )
        bars2 = ax1.bar(
            x,
            deaths_data,
            width,
            label='Deaths',
            color=self.COLORS['accent_red'],
            alpha=0.9,
        )
        bars3 = ax1.bar(
            [i + width for i in x],
            dpm_data,
            width,
            label='DPM',
            color=self.COLORS['accent_yellow'],
            alpha=0.9,
        )

        ax1.set_ylabel('Value', color='white', fontsize=14, fontweight='bold')
        ax1.set_title(
            'Player Performance - Kills, Deaths, DPM',
            color='white',
            fontsize=16,
            fontweight='bold',
            pad=20,
        )
        ax1.set_xticks(x)
        ax1.set_xticklabels(
            names,
            rotation=35,
            ha='right',
            color='white',
            fontsize=11,
        )
        ax1.legend(
            facecolor=self.COLORS['bg_medium'],
            edgecolor='white',
            labelcolor='white',
            fontsize=11,
            loc='upper left',
            bbox_to_anchor=(1.02, 1),
            frameon=False,
        )
        ax1.set_facecolor(self.COLORS['bg_medium'])
        ax1.tick_params(colors='white', labelsize=11)
        ax1.spines['bottom'].set_color('white')
        ax1.spines['left'].set_color('white')
        ax1.spines['top'].set_visible(False)
        ax1.spines['right'].set_visible(False)
        ax1.grid(True, alpha=0.15, color='white', linestyle='--')

        # Add value labels
        for bars in [bars1, bars2, bars3]:
            for bar in bars:
                height = bar.get_height()
                ax1.text(
                    bar.get_x() + bar.get_width() / 2.0,
                    height,
                    f'{int(height)}',
                    ha='center',
                    va='bottom',
                    color='white',
                    fontsize=10,
                    fontweight='bold',
                )

        # Graph 2: K/D and Accuracy
        kd_ratios = [p['kd'] for p in player_data]
        accuracy_data = [p['acc'] for p in player_data]

        ax2_twin = ax2.twinx()

        bars4 = ax2.bar(
            [i - width / 2 for i in x],
            kd_ratios,
            width,
            label='K/D Ratio',
            color=self.COLORS['accent_green'],
            alpha=0.9,
        )
        bars5 = ax2_twin.bar(
            [i + width / 2 for i in x],
            accuracy_data,
            width,
            label='Accuracy %',
            color=self.COLORS['accent_pink'],
            alpha=0.9,
        )

        ax2.set_ylabel(
            'K/D Ratio',
            color='white',
            fontsize=14,
            fontweight='bold',
        )
        ax2_twin.set_ylabel(
            'Accuracy %',
            color='white',
            fontsize=14,
            fontweight='bold',
        )
        ax2.set_title(
            'Player Efficiency - K/D Ratio and Accuracy',
            color='white',
            fontsize=16,
            fontweight='bold',
            pad=20,
        )
        ax2.set_xticks(x)
        ax2.set_xticklabels(
            names,
            rotation=35,
            ha='right',
            color='white',
            fontsize=11,
        )

        # Combine legends
        lines1, labels1 = ax2.get_legend_handles_labels()
        lines2, labels2 = ax2_twin.get_legend_handles_labels()
        ax2.legend(
            lines1 + lines2,
            labels1 + labels2,
            facecolor=self.COLORS['bg_medium'],
            edgecolor='white',
            labelcolor='white',
            fontsize=11,
            loc='upper left',
            bbox_to_anchor=(1.02, 1),
            frameon=False,
        )

        ax2.set_facecolor(self.COLORS['bg_medium'])
        ax2.tick_params(colors='white', labelsize=11)
        ax2_twin.tick_params(colors='white', labelsize=11)
        ax2.spines['bottom'].set_color('white')
        ax2.spines['left'].set_color('white')
        ax2_twin.spines['right'].set_color('white')
        ax2.spines['top'].set_visible(False)
        ax2.grid(True, alpha=0.15, color='white', linestyle='--', axis='y')

        # Add value labels
        for bar in bars4:
            height = bar.get_height()
            ax2.text(
                bar.get_x() + bar.get_width() / 2.0,
                height,
                f'{height:.2f}',
                ha='center',
                va='bottom',
                color='white',
                fontsize=10,
                fontweight='bold',
            )

        for bar in bars5:
            height = bar.get_height()
            ax2_twin.text(
                bar.get_x() + bar.get_width() / 2.0,
                height,
                f'{height:.1f}%',
                ha='center',
                va='bottom',
                color='white',
                fontsize=10,
                fontweight='bold',
            )

        plt.tight_layout()

        # Save to bytes
        buf = io.BytesIO()
        plt.savefig(
            buf,
            format='png',
            facecolor=self.COLORS['bg_dark'],
            dpi=120,
            bbox_inches='tight',
        )
        buf.seek(0)
        plt.close()

        return buf

    def create_weapon_mastery_image(self, player_weapons_data):
        """
        Create weapon mastery breakdown image

        Args:
            player_weapons_data: dict mapping player_name to a list of tuples.
                Each tuple: (weapon, kills, acc, hs_pct, hs, hits, shots)
        """
        # Create large image for detailed weapon breakdown
        img = Image.new('RGB', (1600, 1200), self.COLORS['bg_dark'])
        draw = ImageDraw.Draw(img)

        # Try to load fonts
        try:
            title_font = ImageFont.truetype("arial.ttf", 42)
            player_font = ImageFont.truetype("arialbd.ttf", 28)
            weapon_font = ImageFont.truetype("arial.ttf", 22)
            stat_font = ImageFont.truetype("arial.ttf", 18)
        except BaseException:
            title_font = ImageFont.load_default()
            player_font = ImageFont.load_default()
            weapon_font = ImageFont.load_default()
            stat_font = ImageFont.load_default()

        y_pos = 30

        # Title
        draw.text(
            (50, y_pos),
            "🔫 Weapon Mastery Breakdown",
            fill=self.COLORS['accent_pink'],
            font=title_font,
        )
        y_pos += 60

        # Subtitle
        draw.text(
            (50, y_pos),
            "Top weapons for each player with detailed statistics",
            fill=self.COLORS['text_gray'],
            font=weapon_font,
        )
        y_pos += 50

        # Divider
        rect = [50, y_pos, self.width + 150, y_pos + 2]
        draw.rectangle(rect, fill=self.COLORS['bg_light'])
        y_pos += 30

        # Display players in 2 columns
        col1_x = 60
        col2_x = 820
        row_height = 180

        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣"]
        weapon_colors = [
            self.COLORS['accent_blue'],
            self.COLORS['accent_green'],
            self.COLORS['accent_yellow'],
        ]

        player_idx = 0
        for player_name, weapons in list(player_weapons_data.items())[:6]:
            # Determine column position
            if player_idx % 2 == 0:
                x_pos = col1_x
            else:
                x_pos = col2_x

            # Player header with medal
            medal = medals[player_idx] if player_idx < len(medals) else "•"
            total_kills = sum(w[1] for w in weapons)

            player_header = f"{medal} {player_name} ({total_kills}K)"
            draw.text(
                (x_pos, y_pos),
                player_header,
                fill=self.COLORS['text_white'],
                font=player_font,
            )
            y_temp = y_pos + 35

            # Show top 3 weapons for this player
            for weapon_idx, weapon_data in enumerate(weapons[:3]):
                weapon, kills, acc, hs_pct, hs, hits, shots = weapon_data

                # Weapon name with color
                color = (
                    weapon_colors[weapon_idx]
                    if weapon_idx < len(weapon_colors)
                    else self.COLORS['text_gray']
                )
                weapon_text = f"  {weapon_idx + 1}. {weapon}"
                draw.text(
                    (x_pos + 10, y_temp),
                    weapon_text,
                    fill=color,
                    font=weapon_font,
                )
                y_temp += 28

                # Stats line
                stats_text = (
                    f"     {kills} Kills  •  "
                    f"{acc:.1f}% ACC  •  "
                    f"{hs_pct:.1f}% HS ({hs}/{hits})"
                )
                draw.text(
                    (x_pos + 10, y_temp),
                    stats_text,
                    fill=self.COLORS['text_dim'],
                    font=stat_font,
                )
                y_temp += 26

            # Move to next row after every 2 players
            if player_idx % 2 == 1:
                y_pos += row_height

            player_idx += 1

        # If odd number of players, adjust y_pos
        if player_idx % 2 == 1:
            y_pos += row_height

        # Footer
        y_pos = max(y_pos, 1150)
        footer_text = (
            "ACC = Accuracy (Hits/Shots)  •  "
            "HS = Headshot Rate (Headshots/Hits)"
        )
        draw.text(
            (50, y_pos),
            footer_text,
            fill=self.COLORS['text_dim'],
            font=stat_font,
        )

        # Save to bytes
        buf = io.BytesIO()
        img.save(buf, format='PNG', optimize=True)
        buf.seek(0)
        return buf
