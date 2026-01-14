"""
Session Graph Generator - Creates beautiful performance graphs

This service generates 5 themed graph images:
1. Combat Stats (Offense) - Kills/Deaths grouped, Damage grouped, K/D, DPM
2. Combat Stats (Defense/Support) - Revives grouped, Time grouped, Gibs, Headshots
3. Advanced Metrics - FragPotential, Damage Efficiency, Denied Playtime, Survival Rate
4. Playstyle Analysis - Player Playstyles + Legend
5. DPM Timeline - Performance evolution over rounds
"""

import io
import logging
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from typing import List, Optional, Tuple

from bot.core.frag_potential import FragPotentialCalculator

logger = logging.getLogger("bot.services.session_graph_generator")


class SessionGraphGenerator:
    """Service for generating beautiful performance graphs"""

    # Color palette - Discord-inspired dark theme
    COLORS = {
        'bg_dark': '#2b2d31',
        'bg_panel': '#1e1f22',
        'green': '#57F287',
        'red': '#ED4245',
        'blue': '#5865F2',
        'yellow': '#FEE75C',
        'orange': '#F39C12',
        'pink': '#EB459E',
        'purple': '#9B59B6',
        'cyan': '#3498DB',
        'teal': '#1ABC9C',
        'gray': '#95A5A6',
    }

    def __init__(self, db_adapter):
        self.db_adapter = db_adapter

    def _style_axis(self, ax, title: str, title_size: int = 13):
        """Apply beautiful dark theme styling"""
        ax.set_title(title, fontweight="bold", color='white',
                     fontsize=title_size, pad=10)
        ax.set_facecolor(self.COLORS['bg_panel'])
        ax.tick_params(colors='white', labelsize=9)
        for spine in ['bottom', 'left']:
            ax.spines[spine].set_color('#404249')
        for spine in ['top', 'right']:
            ax.spines[spine].set_visible(False)
        ax.grid(True, alpha=0.15, color='white', axis='y', linestyle='--')

    def _add_bar_labels(self, ax, bars, values, fmt="{:.0f}", offset=0):
        """Add white value labels on top of bars"""
        for bar, value in zip(bars, values):
            height = bar.get_height()
            if height > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2., height,
                    fmt.format(value),
                    ha='center', va='bottom', color='white',
                    fontsize=8, fontweight='bold'
                )

    def _add_grouped_bar_labels(self, ax, bars1, bars2, values1, values2, 
                                 fmt="{:.0f}"):
        """Add labels for grouped bars"""
        for bar, value in zip(bars1, values1):
            height = bar.get_height()
            if height > 0:
                ax.text(bar.get_x() + bar.get_width() / 2., height,
                        fmt.format(value), ha='center', va='bottom',
                        color='white', fontsize=7, fontweight='bold')
        for bar, value in zip(bars2, values2):
            height = bar.get_height()
            if height > 0:
                ax.text(bar.get_x() + bar.get_width() / 2., height,
                        fmt.format(value), ha='center', va='bottom',
                        color='white', fontsize=7, fontweight='bold')

    async def generate_performance_graphs(
        self,
        latest_date: str,
        session_ids: List,
        session_ids_str: str
    ) -> Tuple[Optional[io.BytesIO], Optional[io.BytesIO],
               Optional[io.BytesIO], Optional[io.BytesIO],
               Optional[io.BytesIO]]:
        """
        Generate FIVE beautiful graph images:
        
        Image 1: COMBAT STATS (OFFENSE) - 2x2
            - Kills vs Deaths (grouped bars)
            - Damage Given vs Received (grouped bars)
            - K/D Ratio
            - DPM
            
        Image 2: COMBAT STATS (DEFENSE/SUPPORT) - 2x2
            - Revives Given vs Times Revived (grouped bars)
            - Time Played vs Time Dead (grouped bars)
            - Gibs
            - Headshots
            
        Image 3: ADVANCED METRICS - 2x2
            - FragPotential
            - Damage Efficiency
            - Denied Playtime
            - Survival Rate
            
        Image 4: PLAYSTYLE ANALYSIS
            - Player Playstyles (horizontal bars - full width)
            - Playstyle Legend
            
        Image 5: DPM TIMELINE
            - DPM evolution line graph
            - Session Form Analysis
        
        Returns: Tuple of 5 buffers
        """
        try:
            # Comprehensive query with all needed stats
            placeholders = ','.join(['?' for _ in session_ids])
            query = f"""
                SELECT MAX(p.player_name) as player_name,
                       SUM(p.kills) as kills,
                       SUM(p.deaths) as deaths,
                       SUM(p.damage_given) as damage_given,
                       SUM(p.damage_received) as damage_received,
                       CASE
                           WHEN SUM(p.time_played_seconds) > 0
                           THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
                           ELSE 0
                       END as dpm,
                       SUM(p.time_played_seconds) as time_played,
                       SUM(
                           LEAST(
                               p.time_played_minutes * p.time_dead_ratio / 100.0,
                               p.time_played_seconds / 60.0
                           )
                       ) as time_dead_minutes,
                       SUM(p.revives_given) as revives_given,
                       SUM(p.times_revived) as times_revived,
                       SUM(p.gibs) as gibs,
                       SUM(COALESCE(p.headshots, p.headshot_kills, 0)) as headshots,
                       SUM(COALESCE(p.denied_playtime, 0)) as denied_playtime,
                       p.player_guid,
                       COUNT(DISTINCT p.round_id) as rounds_played
                FROM player_comprehensive_stats p
                WHERE p.round_id IN ({placeholders})
                GROUP BY p.player_guid
                ORDER BY kills DESC
                LIMIT 16
            """
            top_players = await self.db_adapter.fetch_all(
                query, tuple(session_ids)
            )

            if not top_players:
                return None, None, None, None, None

            # Extract all data arrays (keep full names for matching)
            names = [p[0] for p in top_players]
            display_names = [n[:12] for n in names]
            kills = [p[1] or 0 for p in top_players]
            deaths = [p[2] or 0 for p in top_players]
            damage_given = [p[3] or 0 for p in top_players]
            damage_received = [p[4] or 0 for p in top_players]
            dpm = [p[5] or 0 for p in top_players]
            time_played_sec = [p[6] or 0 for p in top_players]
            time_played = [t / 60 for t in time_played_sec]
            time_dead_minutes = [p[7] or 0 for p in top_players]
            revives_given = [p[8] or 0 for p in top_players]
            times_revived = [p[9] or 0 for p in top_players]
            gibs = [p[10] or 0 for p in top_players]
            headshots = [p[11] or 0 for p in top_players]
            denied_playtime_sec = [p[12] or 0 for p in top_players]
            rounds_played = [p[14] or 1 for p in top_players]
            
            # Calculate denied playtime as percentage of total time played
            denied_playtime_pct = [
                (dp / max(1, tp)) * 100 
                for dp, tp in zip(denied_playtime_sec, time_played_sec)
            ]

            # Calculate derived metrics
            kd_ratios = [k / max(1, d) for k, d in zip(kills, deaths)]
            time_dead = time_dead_minutes  # Already calculated correctly from time_dead_ratio
            dmg_eff = [
                dg / max(1, dr)
                for dg, dr in zip(damage_given, damage_received)
            ]
            # Calculate survival rate from time_dead
            survival_rate = [
                100 - (td / max(0.01, tp) * 100) if tp > 0 else 0
                for td, tp in zip(time_dead_minutes, time_played)
            ]

            # Calculate FragPotential and Playstyles
            frag_potentials = []
            playstyles = []
            avg_deaths = sum(deaths) / len(deaths) if deaths else 0
            avg_revives = sum(revives_given) / len(revives_given) if revives_given else 0

            from bot.core.frag_potential import PlayerMetrics
            for i, p in enumerate(top_players):
                # Calculate time_dead_ratio from time_dead_minutes and time_played
                time_dead_ratio_calc = (time_dead_minutes[i] / max(0.01, time_played[i]) * 100) if time_played[i] > 0 else 0

                fp = FragPotentialCalculator.calculate_frag_potential(
                    damage_given=damage_given[i],
                    time_played_seconds=time_played_sec[i],
                    time_dead_ratio=time_dead_ratio_calc
                )
                frag_potentials.append(fp)

                metrics = PlayerMetrics(
                    player_name=p[0],
                    player_guid=p[13] or "",
                    kills=kills[i],
                    deaths=deaths[i],
                    damage_given=damage_given[i],
                    damage_received=damage_received[i],
                    time_played_seconds=time_played_sec[i],
                    time_dead_ratio=time_dead_ratio_calc,
                    revives_given=revives_given[i],
                    headshot_kills=headshots[i],
                    objectives_completed=0,
                )

                style, _ = FragPotentialCalculator.determine_playstyle(
                    metrics,
                    session_avg_deaths=avg_deaths,
                    session_avg_revives=avg_revives,
                    rounds_played=rounds_played[i]
                )
                playstyles.append(style)

            n_players = len(names)
            x = np.arange(n_players)
            bar_width = 0.35

            # ═══════════════════════════════════════════════════════════════
            # IMAGE 1: COMBAT STATS (OFFENSE) - 2x2 with grouped bars
            # ═══════════════════════════════════════════════════════════════
            fig1, axes1 = plt.subplots(2, 2, figsize=(14, 10))
            fig1.patch.set_facecolor(self.COLORS['bg_dark'])
            fig1.suptitle(
                f"COMBAT STATS (OFFENSE)  -  {latest_date}",
                fontsize=18, fontweight="bold", color='white', y=0.98
            )

            # Kills vs Deaths (grouped)
            bars1 = axes1[0, 0].bar(x - bar_width/2, kills, bar_width,
                                     color=self.COLORS['green'], label='Kills',
                                     edgecolor='white', linewidth=0.5)
            bars2 = axes1[0, 0].bar(x + bar_width/2, deaths, bar_width,
                                     color=self.COLORS['red'], label='Deaths',
                                     edgecolor='white', linewidth=0.5)
            self._style_axis(axes1[0, 0], "KILLS vs DEATHS")
            axes1[0, 0].set_xticks(x)
            axes1[0, 0].set_xticklabels(display_names, rotation=45, ha="right")
            axes1[0, 0].legend(loc='upper right', facecolor=self.COLORS['bg_panel'],
                               edgecolor='white', labelcolor='white')
            self._add_grouped_bar_labels(axes1[0, 0], bars1, bars2, kills, deaths)

            # Damage Given vs Received (grouped)
            bars1 = axes1[0, 1].bar(x - bar_width/2, damage_given, bar_width,
                                     color=self.COLORS['blue'], label='Given',
                                     edgecolor='white', linewidth=0.5)
            bars2 = axes1[0, 1].bar(x + bar_width/2, damage_received, bar_width,
                                     color=self.COLORS['orange'], label='Received',
                                     edgecolor='white', linewidth=0.5)
            self._style_axis(axes1[0, 1], "DAMAGE GIVEN vs RECEIVED")
            axes1[0, 1].set_xticks(x)
            axes1[0, 1].set_xticklabels(display_names, rotation=45, ha="right")
            axes1[0, 1].legend(loc='upper right', facecolor=self.COLORS['bg_panel'],
                               edgecolor='white', labelcolor='white')
            self._add_grouped_bar_labels(axes1[0, 1], bars1, bars2,
                                          damage_given, damage_received, "{:,.0f}")

            # K/D Ratio
            kd_colors = [
                self.COLORS['green'] if kd >= 1.5
                else self.COLORS['yellow'] if kd >= 1.0
                else self.COLORS['red']
                for kd in kd_ratios
            ]
            bars = axes1[1, 0].bar(x, kd_ratios, color=kd_colors,
                                    edgecolor='white', linewidth=0.5)
            self._style_axis(axes1[1, 0], "K/D RATIO")
            axes1[1, 0].axhline(y=1.0, color="white", linestyle="--",
                                 alpha=0.5, linewidth=1)
            axes1[1, 0].set_xticks(x)
            axes1[1, 0].set_xticklabels(display_names, rotation=45, ha="right")
            self._add_bar_labels(axes1[1, 0], bars, kd_ratios, fmt="{:.2f}")

            # DPM
            bars = axes1[1, 1].bar(x, dpm, color=self.COLORS['cyan'],
                                    edgecolor='white', linewidth=0.5)
            self._style_axis(axes1[1, 1], "DPM (Damage Per Minute)")
            axes1[1, 1].set_xticks(x)
            axes1[1, 1].set_xticklabels(display_names, rotation=45, ha="right")
            self._add_bar_labels(axes1[1, 1], bars, dpm)

            plt.tight_layout(rect=(0, 0, 1, 0.96))
            buf1 = io.BytesIO()
            plt.savefig(buf1, format="png", facecolor=self.COLORS['bg_dark'],
                        dpi=120, bbox_inches="tight")
            buf1.seek(0)
            plt.close(fig1)

            # ═══════════════════════════════════════════════════════════════
            # IMAGE 2: COMBAT STATS (DEFENSE/SUPPORT) - 2x2 with grouped bars
            # ═══════════════════════════════════════════════════════════════
            fig2, axes2 = plt.subplots(2, 2, figsize=(14, 10))
            fig2.patch.set_facecolor(self.COLORS['bg_dark'])
            fig2.suptitle(
                f"COMBAT STATS (DEFENSE/SUPPORT)  -  {latest_date}",
                fontsize=18, fontweight="bold", color='white', y=0.98
            )

            # Revives Given vs Times Revived (grouped)
            bars1 = axes2[0, 0].bar(x - bar_width/2, revives_given, bar_width,
                                     color=self.COLORS['green'], label='Given',
                                     edgecolor='white', linewidth=0.5)
            bars2 = axes2[0, 0].bar(x + bar_width/2, times_revived, bar_width,
                                     color=self.COLORS['teal'], label='Received',
                                     edgecolor='white', linewidth=0.5)
            self._style_axis(axes2[0, 0], "REVIVES GIVEN vs RECEIVED")
            axes2[0, 0].set_xticks(x)
            axes2[0, 0].set_xticklabels(display_names, rotation=45, ha="right")
            axes2[0, 0].legend(loc='upper right', facecolor=self.COLORS['bg_panel'],
                               edgecolor='white', labelcolor='white')
            self._add_grouped_bar_labels(axes2[0, 0], bars1, bars2,
                                          revives_given, times_revived)

            # Time Played vs Time Dead (grouped)
            bars1 = axes2[0, 1].bar(x - bar_width/2, time_played, bar_width,
                                     color=self.COLORS['cyan'], label='Alive',
                                     edgecolor='white', linewidth=0.5)
            bars2 = axes2[0, 1].bar(x + bar_width/2, time_dead, bar_width,
                                     color=self.COLORS['pink'], label='Dead',
                                     edgecolor='white', linewidth=0.5)
            self._style_axis(axes2[0, 1], "TIME ALIVE vs DEAD (minutes)")
            axes2[0, 1].set_xticks(x)
            axes2[0, 1].set_xticklabels(display_names, rotation=45, ha="right")
            axes2[0, 1].legend(loc='upper right', facecolor=self.COLORS['bg_panel'],
                               edgecolor='white', labelcolor='white')
            self._add_grouped_bar_labels(axes2[0, 1], bars1, bars2,
                                          time_played, time_dead, "{:.1f}")

            # Gibs
            bars = axes2[1, 0].bar(x, gibs, color=self.COLORS['red'],
                                    edgecolor='white', linewidth=0.5)
            self._style_axis(axes2[1, 0], "GIBS")
            axes2[1, 0].set_xticks(x)
            axes2[1, 0].set_xticklabels(display_names, rotation=45, ha="right")
            self._add_bar_labels(axes2[1, 0], bars, gibs)

            # Headshots
            bars = axes2[1, 1].bar(x, headshots, color=self.COLORS['purple'],
                                    edgecolor='white', linewidth=0.5)
            self._style_axis(axes2[1, 1], "HEADSHOTS")
            axes2[1, 1].set_xticks(x)
            axes2[1, 1].set_xticklabels(display_names, rotation=45, ha="right")
            self._add_bar_labels(axes2[1, 1], bars, headshots)

            plt.tight_layout(rect=(0, 0, 1, 0.96))
            buf2 = io.BytesIO()
            plt.savefig(buf2, format="png", facecolor=self.COLORS['bg_dark'],
                        dpi=120, bbox_inches="tight")
            buf2.seek(0)
            plt.close(fig2)

            # ═══════════════════════════════════════════════════════════════
            # IMAGE 3: ADVANCED METRICS - 2x2
            # ═══════════════════════════════════════════════════════════════
            fig3, axes3 = plt.subplots(2, 2, figsize=(14, 10))
            fig3.patch.set_facecolor(self.COLORS['bg_dark'])
            fig3.suptitle(
                f"ADVANCED METRICS  -  {latest_date}",
                fontsize=18, fontweight="bold", color='white', y=0.98
            )

            # FragPotential
            fp_colors = [style.color for style in playstyles]
            bars = axes3[0, 0].bar(x, frag_potentials, color=fp_colors,
                                    edgecolor='white', linewidth=0.5)
            self._style_axis(axes3[0, 0], "FRAGPOTENTIAL (DPM While Alive)")
            axes3[0, 0].set_xticks(x)
            axes3[0, 0].set_xticklabels(display_names, rotation=45, ha="right")
            self._add_bar_labels(axes3[0, 0], bars, frag_potentials)

            # Damage Efficiency
            eff_colors = [
                self.COLORS['green'] if e >= 1.5
                else self.COLORS['yellow'] if e >= 1.0
                else self.COLORS['red']
                for e in dmg_eff
            ]
            bars = axes3[0, 1].bar(x, dmg_eff, color=eff_colors,
                                    edgecolor='white', linewidth=0.5)
            self._style_axis(axes3[0, 1], "DAMAGE EFFICIENCY")
            axes3[0, 1].axhline(y=1.0, color="white", linestyle="--",
                                 alpha=0.5, linewidth=1)
            axes3[0, 1].set_xticks(x)
            axes3[0, 1].set_xticklabels(display_names, rotation=45, ha="right")
            self._add_bar_labels(axes3[0, 1], bars, dmg_eff, fmt="{:.2f}x")

            # Denied Playtime (as percentage)
            denied_colors = [
                self.COLORS['red'] if d >= 30
                else self.COLORS['orange'] if d >= 15
                else self.COLORS['green']
                for d in denied_playtime_pct
            ]
            bars = axes3[1, 0].bar(x, denied_playtime_pct, color=denied_colors,
                                    edgecolor='white', linewidth=0.5)
            self._style_axis(axes3[1, 0], "TIME DENIED (%)")
            axes3[1, 0].set_ylim(0, max(50, max(denied_playtime_pct) * 1.2))
            axes3[1, 0].set_xticks(x)
            axes3[1, 0].set_xticklabels(display_names, rotation=45, ha="right")
            self._add_bar_labels(axes3[1, 0], bars, denied_playtime_pct, 
                                 fmt="{:.1f}%")

            # Survival Rate
            surv_colors = [
                self.COLORS['green'] if s >= 70
                else self.COLORS['yellow'] if s >= 50
                else self.COLORS['red']
                for s in survival_rate
            ]
            bars = axes3[1, 1].bar(x, survival_rate, color=surv_colors,
                                    edgecolor='white', linewidth=0.5)
            self._style_axis(axes3[1, 1], "SURVIVAL RATE (%)")
            axes3[1, 1].set_ylim(0, 100)
            axes3[1, 1].axhline(y=50, color="white", linestyle="--",
                                 alpha=0.5, linewidth=1)
            axes3[1, 1].set_xticks(x)
            axes3[1, 1].set_xticklabels(display_names, rotation=45, ha="right")
            self._add_bar_labels(axes3[1, 1], bars, survival_rate, fmt="{:.0f}%")

            plt.tight_layout(rect=(0, 0, 1, 0.96))
            buf3 = io.BytesIO()
            plt.savefig(buf3, format="png", facecolor=self.COLORS['bg_dark'],
                        dpi=120, bbox_inches="tight")
            buf3.seek(0)
            plt.close(fig3)

            # ═══════════════════════════════════════════════════════════════
            # IMAGE 4: PLAYSTYLE ANALYSIS - Full width bars + Legend
            # ═══════════════════════════════════════════════════════════════
            fig4, (ax4a, ax4b) = plt.subplots(1, 2, figsize=(16, 8),
                                               gridspec_kw={'width_ratios': [2, 1]})
            fig4.patch.set_facecolor(self.COLORS['bg_dark'])
            fig4.suptitle(
                f"PLAYSTYLE ANALYSIS  -  {latest_date}",
                fontsize=18, fontweight="bold", color='white', y=0.98
            )

            # Player Playstyles (horizontal bars)
            style_colors = [s.color for s in playstyles]
            y_pos = np.arange(n_players)
            bars = ax4a.barh(y_pos, frag_potentials, color=style_colors,
                              edgecolor='white', linewidth=0.5)
            ax4a.set_yticks(y_pos)
            ax4a.set_yticklabels(display_names, color='white', fontsize=10)
            ax4a.invert_yaxis()
            ax4a.set_facecolor(self.COLORS['bg_panel'])
            ax4a.set_title("PLAYER PLAYSTYLES", fontweight="bold",
                           color='white', fontsize=14, pad=10)
            ax4a.set_xlabel("FragPotential", color='white', fontsize=11)
            ax4a.tick_params(colors='white')
            for spine in ['bottom', 'left']:
                ax4a.spines[spine].set_color('#404249')
            for spine in ['top', 'right']:
                ax4a.spines[spine].set_visible(False)
            ax4a.grid(True, alpha=0.15, color='white', axis='x', linestyle='--')

            # Add playstyle labels
            for bar, style, fp in zip(bars, playstyles, frag_potentials):
                width = bar.get_width()
                ax4a.text(width + (max(frag_potentials) * 0.02),
                          bar.get_y() + bar.get_height() / 2,
                          f"{style.name_display} ({int(fp)})",
                          va='center', color='white', fontsize=9, fontweight='bold')

            # Playstyle Legend
            ax4b.set_facecolor(self.COLORS['bg_panel'])
            ax4b.axis('off')
            ax4b.set_title("PLAYSTYLE LEGEND", fontweight="bold",
                           color='white', fontsize=14, pad=10)

            legend_items = [
                ("FRAGGER", "#E74C3C", "High K/D + High FragPotential"),
                ("SLAYER", "#E91E63", "High kills, trades often"),
                ("TANK", "#3498DB", "Survives, low death ratio"),
                ("MEDIC", "#2ECC71", "High revives per round"),
                ("SNIPER", "#9B59B6", "High headshot percentage"),
                ("RUSHER", "#F39C12", "High FP, aggressive play"),
                ("OBJECTIVE", "#1ABC9C", "Objective focused"),
                ("BALANCED", "#95A5A6", "All-around player"),
            ]

            y_pos_legend = 0.92
            for name, color, desc in legend_items:
                ax4b.add_patch(mpatches.FancyBboxPatch(
                    (0.05, y_pos_legend - 0.04), 0.08, 0.06,
                    boxstyle="round,pad=0.01",
                    facecolor=color, edgecolor='white', linewidth=0.5,
                    transform=ax4b.transAxes
                ))
                ax4b.text(0.16, y_pos_legend, f"{name}",
                          transform=ax4b.transAxes,
                          color=color, fontsize=12, fontweight='bold', va='center')
                ax4b.text(0.16, y_pos_legend - 0.04, desc,
                          transform=ax4b.transAxes,
                          color='#B0B0B0', fontsize=9, va='center')
                y_pos_legend -= 0.11

            plt.tight_layout(rect=(0, 0, 1, 0.96))
            buf4 = io.BytesIO()
            plt.savefig(buf4, format="png", facecolor=self.COLORS['bg_dark'],
                        dpi=120, bbox_inches="tight")
            buf4.seek(0)
            plt.close(fig4)

            # ═══════════════════════════════════════════════════════════════
            # IMAGE 5: DPM TIMELINE
            # ═══════════════════════════════════════════════════════════════
            buf5 = await self._generate_timeline_graph(
                latest_date, session_ids, session_ids_str, names[:16]
            )

            return buf1, buf2, buf3, buf4, buf5

        except ImportError as e:
            logger.warning(f"matplotlib not available: {e}")
            return None, None, None, None, None
        except Exception as e:
            logger.exception(f"Error generating performance graphs: {e}")
            return None, None, None, None, None

    async def _generate_timeline_graph(
        self,
        latest_date: str,
        session_ids: List,
        session_ids_str: str,
        top_player_names: List[str]
    ) -> Optional[io.BytesIO]:
        """
        Generate Performance Timeline showing DPM evolution
        across all rounds (Map1-R1, Map1-R2, Map2-R1, Map2-R2, etc.)
        """
        try:
            placeholders = ','.join(['?' for _ in session_ids])
            query = f"""
                SELECT
                    p.player_name,
                    r.map_name,
                    r.round_number,
                    r.round_date,
                    p.damage_given,
                    p.time_played_seconds,
                    p.time_dead_ratio,
                    p.kills,
                    p.deaths,
                    r.id as round_id,
                    r.round_time
                FROM player_comprehensive_stats p
                JOIN rounds r ON p.round_id = r.id
                WHERE p.round_id IN ({placeholders})
                ORDER BY r.round_date, r.round_time, r.round_number
            """
            all_rounds = await self.db_adapter.fetch_all(
                query, tuple(session_ids)
            )

            if not all_rounds:
                return None

            # Build round order
            round_order = []
            round_labels = []
            seen_rounds = set()

            for row in all_rounds:
                round_id = row[9]
                if round_id not in seen_rounds:
                    seen_rounds.add(round_id)
                    map_name = row[1][:8] if row[1] else "?"
                    round_num = row[2]
                    round_order.append(round_id)
                    round_labels.append(f"{map_name}\nR{round_num}")

            # Calculate DPM per player per round
            player_timelines = {}
            for name in top_player_names:
                player_timelines[name] = {rid: None for rid in round_order}

            for row in all_rounds:
                name = row[0]
                if name not in top_player_names:
                    continue

                round_id = row[9]
                dmg = row[4] or 0
                time_sec = row[5] or 0

                if time_sec > 0:
                    dpm = (dmg / time_sec) * 60
                else:
                    dpm = 0
                player_timelines[name][round_id] = dpm

            # Create figure
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(18, 12),
                                            gridspec_kw={'height_ratios': [3, 1]})
            fig.patch.set_facecolor(self.COLORS['bg_dark'])
            fig.suptitle(
                f"DPM TIMELINE  -  {latest_date}",
                fontsize=18, fontweight="bold", color='white', y=0.98
            )

            # Color palette
            player_colors = [
                '#E74C3C', '#3498DB', '#2ECC71', '#F39C12',
                '#9B59B6', '#1ABC9C', '#E91E63', '#FEE75C',
                '#00BCD4', '#FF5722', '#8BC34A', '#607D8B',
                '#FF6B6B', '#4ECDC4', '#C9B037', '#BA68C8'
            ]

            x_positions = range(len(round_order))
            peak_data = {}
            trend_data = {}

            for idx, name in enumerate(top_player_names):
                timeline = player_timelines.get(name, {})
                y_values = [timeline.get(rid) for rid in round_order]

                valid_points = [(i, v) for i, v in enumerate(y_values) if v is not None]
                if not valid_points:
                    continue

                x_valid = [p[0] for p in valid_points]
                y_valid = [p[1] for p in valid_points]

                color = player_colors[idx % len(player_colors)]

                ax1.plot(x_valid, y_valid, color=color, linewidth=2.5,
                         marker='o', markersize=6, label=name[:12], alpha=0.9)

                if y_valid:
                    peak_idx = y_valid.index(max(y_valid))
                    peak_x = x_valid[peak_idx]
                    peak_y = y_valid[peak_idx]
                    ax1.scatter([peak_x], [peak_y], color=color, s=150,
                                marker='*', zorder=5, edgecolors='white',
                                linewidths=1)
                    peak_data[name] = (peak_x, peak_y, round_labels[peak_x])

                    if len(y_valid) >= 4:
                        mid = len(y_valid) // 2
                        first_half_avg = sum(y_valid[:mid]) / mid
                        second_half_avg = sum(y_valid[mid:]) / (len(y_valid) - mid)

                        avg_all = sum(y_valid) / len(y_valid)
                        variance = sum((v - avg_all)**2 for v in y_valid) / len(y_valid)
                        volatility = (variance ** 0.5) / max(1, avg_all) * 100

                        if volatility > 40:
                            trend_data[name] = ("VOLATILE", "🎢", self.COLORS['orange'])
                        elif second_half_avg > first_half_avg * 1.15:
                            trend_data[name] = ("RISING", "📈", self.COLORS['green'])
                        elif first_half_avg > second_half_avg * 1.15:
                            trend_data[name] = ("FADING", "📉", self.COLORS['red'])
                        else:
                            trend_data[name] = ("STEADY", "➡️", self.COLORS['cyan'])
                    else:
                        trend_data[name] = ("N/A", "❓", self.COLORS['gray'])

            # Style main graph
            ax1.set_facecolor(self.COLORS['bg_panel'])
            ax1.set_ylabel("DPM (Damage Per Minute)", color='white',
                           fontsize=12, fontweight='bold')
            ax1.tick_params(colors='white', labelsize=9)
            ax1.set_xticks(x_positions)
            ax1.set_xticklabels(round_labels, rotation=45, ha='right',
                                fontsize=8, color='white')
            ax1.grid(True, alpha=0.2, color='white', linestyle='--')
            for spine in ['bottom', 'left']:
                ax1.spines[spine].set_color('#404249')
            for spine in ['top', 'right']:
                ax1.spines[spine].set_visible(False)

            ax1.legend(loc='upper left', bbox_to_anchor=(1.01, 1),
                       facecolor=self.COLORS['bg_panel'],
                       edgecolor='white', labelcolor='white',
                       fontsize=9, ncol=1, framealpha=0.9)

            # Bottom panel: Form Summary
            ax2.set_facecolor(self.COLORS['bg_panel'])
            ax2.axis('off')
            ax2.set_title("SESSION FORM ANALYSIS", fontweight="bold",
                          color='white', fontsize=13, pad=10)

            for idx, name in enumerate(top_player_names[:16]):
                col = idx % 4
                row = idx // 4

                x_pos = 0.02 + col * 0.25
                y_pos = 0.7 - row * 0.45

                ax2.text(x_pos, y_pos, name[:12], transform=ax2.transAxes,
                         color='white', fontsize=11, fontweight='bold', va='top')

                if name in trend_data:
                    trend_name, emoji, color = trend_data[name]
                    ax2.text(x_pos, y_pos - 0.12, f"{trend_name}",
                             transform=ax2.transAxes, color=color,
                             fontsize=10, fontweight='bold', va='top')

                if name in peak_data:
                    px, py, plabel = peak_data[name]
                    clean_label = plabel.replace('\n', ' ')
                    ax2.text(x_pos, y_pos - 0.24, f"Peak: {int(py)} DPM",
                             transform=ax2.transAxes, color='#B0B0B0',
                             fontsize=9, va='top')
                    ax2.text(x_pos, y_pos - 0.34, f"@ {clean_label}",
                             transform=ax2.transAxes, color='#808080',
                             fontsize=8, va='top')

            plt.tight_layout(rect=(0, 0, 0.85, 0.96))
            buf = io.BytesIO()
            plt.savefig(buf, format="png", facecolor=self.COLORS['bg_dark'],
                        dpi=120, bbox_inches="tight")
            buf.seek(0)
            plt.close(fig)

            return buf

        except Exception as e:
            logger.exception(f"Error generating timeline graph: {e}")
            return None
