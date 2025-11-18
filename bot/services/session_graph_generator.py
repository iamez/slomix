"""
Session Graph Generator - Creates performance graphs

This service manages:
- Performance graphs (kills, deaths, DPM trends)
- Combat efficiency graphs  
"""

import discord
import io
import logging
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from typing import Dict, List, Optional

logger = logging.getLogger("bot.services.session_graph_generator")


class SessionGraphGenerator:
    """Service for generating performance graphs"""

    def __init__(self, db_adapter):
        """
        Initialize the graph generator
        
        Args:
            db_adapter: Database adapter for queries
        """
        self.db_adapter = db_adapter

    async def generate_performance_graphs(
        self,
        latest_date: str,
        session_ids: List,
        session_ids_str: str
    ) -> Optional[io.BytesIO]:
        """Generate 6-panel performance graph (kills, deaths, DPM, time played, time dead, time denied)."""
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import io

            # Get all players data (limit to top 10 for readability)
            query = f"""
                SELECT p.player_name,
                    SUM(p.kills) as kills,
                    SUM(p.deaths) as deaths,
                    CASE
                        WHEN session_total.total_seconds > 0
                        THEN (SUM(p.damage_given) * 60.0) / session_total.total_seconds
                        ELSE 0
                    END as dpm,
                    session_total.total_seconds as time_played,
                    CAST(SUM(p.time_played_seconds * p.time_dead_ratio / 100.0) AS INTEGER) as time_dead,
                    SUM(p.denied_playtime) as denied
                FROM player_comprehensive_stats p
                CROSS JOIN (
                    SELECT SUM(
                        CASE
                            WHEN r.actual_time LIKE '%:%' THEN
                                CAST(SPLIT_PART(r.actual_time, ':', 1) AS INTEGER) * 60 +
                                CAST(SPLIT_PART(r.actual_time, ':', 2) AS INTEGER)
                            ELSE
                                CAST(r.actual_time AS INTEGER)
                        END
                    ) as total_seconds
                    FROM rounds r
                    WHERE r.id IN ({session_ids_str})
                      AND r.round_number IN (1, 2)
                      AND (r.round_status = 'completed' OR r.round_status IS NULL)
                ) session_total
                WHERE p.round_id IN ({session_ids_str})
                GROUP BY p.player_name, session_total.total_seconds
                ORDER BY kills DESC
                LIMIT 10
            """
            top_players = await self.db_adapter.fetch_all(query, tuple(session_ids))

            if not top_players:
                return None

            player_names = [p[0] for p in top_players]
            kills = [p[1] or 0 for p in top_players]
            deaths = [p[2] or 0 for p in top_players]
            dpm = [p[3] or 0 for p in top_players]
            time_played = [p[4] / 60 if p[4] else 0 for p in top_players]
            time_dead = [p[5] / 60 if p[5] else 0 for p in top_players]
            denied = [p[6] or 0 for p in top_players]

            # Create 2x3 grid
            fig, axes = plt.subplots(2, 3, figsize=(18, 10))
            fig.patch.set_facecolor('#2b2d31')
            fig.suptitle(f"Visual Performance Analytics - {latest_date}", fontsize=16, fontweight="bold", color='white')

            # Graph 1: Kills
            bars1 = axes[0, 0].bar(range(len(player_names)), kills, color="#57F287")
            axes[0, 0].set_title("Kills", fontweight="bold", color='white')
            axes[0, 0].set_xticks(range(len(player_names)))
            axes[0, 0].set_xticklabels(player_names, rotation=45, ha="right", color='white')
            axes[0, 0].set_facecolor('#1e1f22')
            axes[0, 0].tick_params(colors='white')
            axes[0, 0].spines['bottom'].set_color('white')
            axes[0, 0].spines['left'].set_color('white')
            axes[0, 0].spines['top'].set_visible(False)
            axes[0, 0].spines['right'].set_visible(False)
            axes[0, 0].grid(True, alpha=0.2, color='white', axis='y')
            # Add value labels on bars
            for i, (bar, value) in enumerate(zip(bars1, kills)):
                height = bar.get_height()
                axes[0, 0].text(bar.get_x() + bar.get_width()/2., height,
                               f'{int(value)}',
                               ha='center', va='bottom', color='white', fontsize=9, fontweight='bold')

            # Graph 2: Deaths
            bars2 = axes[0, 1].bar(range(len(player_names)), deaths, color="#ED4245")
            axes[0, 1].set_title("Deaths", fontweight="bold", color='white')
            axes[0, 1].set_xticks(range(len(player_names)))
            axes[0, 1].set_xticklabels(player_names, rotation=45, ha="right", color='white')
            axes[0, 1].set_facecolor('#1e1f22')
            axes[0, 1].tick_params(colors='white')
            axes[0, 1].spines['bottom'].set_color('white')
            axes[0, 1].spines['left'].set_color('white')
            axes[0, 1].spines['top'].set_visible(False)
            axes[0, 1].spines['right'].set_visible(False)
            axes[0, 1].grid(True, alpha=0.2, color='white', axis='y')
            # Add value labels
            for bar, value in zip(bars2, deaths):
                height = bar.get_height()
                axes[0, 1].text(bar.get_x() + bar.get_width()/2., height,
                               f'{int(value)}',
                               ha='center', va='bottom', color='white', fontsize=9, fontweight='bold')

            # Graph 3: DPM
            bars3 = axes[0, 2].bar(range(len(player_names)), dpm, color="#FEE75C")
            axes[0, 2].set_title("DPM (Damage Per Minute)", fontweight="bold", color='white')
            axes[0, 2].set_xticks(range(len(player_names)))
            axes[0, 2].set_xticklabels(player_names, rotation=45, ha="right", color='white')
            axes[0, 2].set_facecolor('#1e1f22')
            axes[0, 2].tick_params(colors='white')
            axes[0, 2].spines['bottom'].set_color('white')
            axes[0, 2].spines['left'].set_color('white')
            axes[0, 2].spines['top'].set_visible(False)
            axes[0, 2].spines['right'].set_visible(False)
            axes[0, 2].grid(True, alpha=0.2, color='white', axis='y')
            # Add value labels
            for bar, value in zip(bars3, dpm):
                height = bar.get_height()
                axes[0, 2].text(bar.get_x() + bar.get_width()/2., height,
                               f'{int(value)}',
                               ha='center', va='bottom', color='black', fontsize=9, fontweight='bold')

            # Graph 4: Time Played
            bars4 = axes[1, 0].bar(range(len(player_names)), time_played, color="#5865F2")
            axes[1, 0].set_title("Time Played (minutes)", fontweight="bold", color='white')
            axes[1, 0].set_xticks(range(len(player_names)))
            axes[1, 0].set_xticklabels(player_names, rotation=45, ha="right", color='white')
            axes[1, 0].set_facecolor('#1e1f22')
            axes[1, 0].tick_params(colors='white')
            axes[1, 0].spines['bottom'].set_color('white')
            axes[1, 0].spines['left'].set_color('white')
            axes[1, 0].spines['top'].set_visible(False)
            axes[1, 0].spines['right'].set_visible(False)
            axes[1, 0].grid(True, alpha=0.2, color='white', axis='y')
            # Add value labels
            for bar, value in zip(bars4, time_played):
                height = bar.get_height()
                axes[1, 0].text(bar.get_x() + bar.get_width()/2., height,
                               f'{value:.1f}',
                               ha='center', va='bottom', color='white', fontsize=9, fontweight='bold')

            # Graph 5: Time Dead
            bars5 = axes[1, 1].bar(range(len(player_names)), time_dead, color="#EB459E")
            axes[1, 1].set_title("Time Dead (minutes)", fontweight="bold", color='white')
            axes[1, 1].set_xticks(range(len(player_names)))
            axes[1, 1].set_xticklabels(player_names, rotation=45, ha="right", color='white')
            axes[1, 1].set_facecolor('#1e1f22')
            axes[1, 1].tick_params(colors='white')
            axes[1, 1].spines['bottom'].set_color('white')
            axes[1, 1].spines['left'].set_color('white')
            axes[1, 1].spines['top'].set_visible(False)
            axes[1, 1].spines['right'].set_visible(False)
            axes[1, 1].grid(True, alpha=0.2, color='white', axis='y')
            # Add value labels
            for bar, value in zip(bars5, time_dead):
                height = bar.get_height()
                axes[1, 1].text(bar.get_x() + bar.get_width()/2., height,
                               f'{value:.1f}',
                               ha='center', va='bottom', color='white', fontsize=9, fontweight='bold')

            # Graph 6: Time Denied
            bars6 = axes[1, 2].bar(range(len(player_names)), denied, color="#9B59B6")
            axes[1, 2].set_title("Time Denied (seconds)", fontweight="bold", color='white')
            axes[1, 2].set_xticks(range(len(player_names)))
            axes[1, 2].set_xticklabels(player_names, rotation=45, ha="right", color='white')
            axes[1, 2].set_facecolor('#1e1f22')
            axes[1, 2].tick_params(colors='white')
            axes[1, 2].spines['bottom'].set_color('white')
            axes[1, 2].spines['left'].set_color('white')
            axes[1, 2].spines['top'].set_visible(False)
            axes[1, 2].spines['right'].set_visible(False)
            axes[1, 2].grid(True, alpha=0.2, color='white', axis='y')
            # Add value labels
            for bar, value in zip(bars6, denied):
                height = bar.get_height()
                axes[1, 2].text(bar.get_x() + bar.get_width()/2., height,
                               f'{int(value)}',
                               ha='center', va='bottom', color='white', fontsize=9, fontweight='bold')

            plt.tight_layout()

            buf = io.BytesIO()
            plt.savefig(buf, format="png", facecolor='#2b2d31', dpi=150, bbox_inches="tight")
            buf.seek(0)
            plt.close()

            return buf

        except ImportError:
            logger.warning("matplotlib not installed - graphs unavailable")
            return None
        except Exception as e:
            logger.exception(f"Error generating performance graphs: {e}")
            return None

    async def generate_combat_efficiency_graphs(
        self,
        latest_date: str,
        session_ids: List,
        session_ids_str: str
    ) -> Optional[io.BytesIO]:
        """Generate 4-panel combat efficiency graph (damage given/received, ratio, bullets, bullets per kill)."""
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import io

            # Get efficiency data for all players (limit to top 10 for readability)
            query = f"""
                SELECT p.player_name,
                    SUM(p.damage_given) as dmg_given,
                    SUM(p.damage_received) as dmg_received,
                    SUM(w.shots) as bullets,
                    SUM(p.kills) as kills
                FROM player_comprehensive_stats p
                LEFT JOIN (
                    SELECT round_id, player_guid, SUM(shots) as shots
                    FROM weapon_comprehensive_stats
                    WHERE weapon_name NOT IN ('WS_GRENADE', 'WS_SYRINGE', 'WS_DYNAMITE', 'WS_AIRSTRIKE', 'WS_ARTILLERY', 'WS_SATCHEL', 'WS_LANDMINE')
                    GROUP BY round_id, player_guid
                ) w ON p.round_id = w.round_id AND p.player_guid = w.player_guid
                WHERE p.round_id IN ({session_ids_str})
                GROUP BY p.player_name
                ORDER BY dmg_given DESC
                LIMIT 10
            """
            efficiency_players = await self.db_adapter.fetch_all(query, tuple(session_ids))

            if not efficiency_players:
                return None

            eff_names = [row[0] for row in efficiency_players]
            eff_dmg_given = [row[1] or 0 for row in efficiency_players]
            eff_dmg_received = [row[2] or 0 for row in efficiency_players]
            eff_bullets = [row[3] or 0 for row in efficiency_players]
            eff_kills = [row[4] or 0 for row in efficiency_players]

            # Calculate ratios
            eff_damage_ratio = [(g / r) if r > 0 else g for g, r in zip(eff_dmg_given, eff_dmg_received)]
            eff_bullets_per_kill = [(b / k) if k > 0 else 0 for b, k in zip(eff_bullets, eff_kills)]

            # Create 2x2 grid
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 10))
            fig.patch.set_facecolor('#2b2d31')
            fig.suptitle(f"Combat Efficiency Analysis - {latest_date}", fontsize=16, fontweight="bold", color='white')

            x_eff = range(len(eff_names))
            width_eff = 0.35

            # Subplot 1: Damage Given vs Received
            bars_given = ax1.bar([i - width_eff / 2 for i in x_eff], eff_dmg_given, width_eff, label="Damage Given", color="#5865f2", alpha=0.8)
            bars_received = ax1.bar([i + width_eff / 2 for i in x_eff], eff_dmg_received, width_eff, label="Damage Received", color="#ed4245", alpha=0.8)
            ax1.set_xticks(x_eff)
            ax1.set_xticklabels(eff_names, rotation=20, ha="right", color="white", fontsize=9)
            ax1.set_ylabel("Damage", color="white", fontsize=11)
            ax1.set_title("Damage Given vs Received", color="white", fontsize=12, fontweight="bold")
            ax1.set_facecolor("#1e1f22")
            ax1.tick_params(colors="white")
            ax1.spines["bottom"].set_color("white")
            ax1.spines["left"].set_color("white")
            ax1.spines["top"].set_visible(False)
            ax1.spines["right"].set_visible(False)
            ax1.grid(True, alpha=0.2, color="white", axis="y")
            ax1.legend(facecolor="#1e1f22", edgecolor="white", labelcolor="white", fontsize=9)
            # Add value labels
            for bar, value in zip(bars_given, eff_dmg_given):
                height = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width()/2., height,
                        f'{int(value):,}',
                        ha='center', va='bottom', color='white', fontsize=7)
            for bar, value in zip(bars_received, eff_dmg_received):
                height = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width()/2., height,
                        f'{int(value):,}',
                        ha='center', va='bottom', color='white', fontsize=7)

            # Subplot 2: Damage Efficiency Ratio
            colors_ratio = ["#57f287" if r > 1.5 else "#fee75c" if r > 1.0 else "#ed4245" for r in eff_damage_ratio]
            ax2.bar(x_eff, eff_damage_ratio, color=colors_ratio, alpha=0.8)
            ax2.axhline(y=1.0, color="white", linestyle="--", alpha=0.5, linewidth=1)
            ax2.set_xticks(x_eff)
            ax2.set_xticklabels(eff_names, rotation=20, ha="right", color="white", fontsize=9)
            ax2.set_ylabel("Ratio (Given/Received)", color="white", fontsize=11)
            ax2.set_title("Damage Efficiency Ratio", color="white", fontsize=12, fontweight="bold")
            ax2.set_facecolor("#1e1f22")
            ax2.tick_params(colors="white")
            ax2.spines["bottom"].set_color("white")
            ax2.spines["left"].set_color("white")
            ax2.spines["top"].set_visible(False)
            ax2.spines["right"].set_visible(False)
            ax2.grid(True, alpha=0.2, color="white", axis="y")
            for i, v in enumerate(eff_damage_ratio):
                ax2.text(i, v, f"{v:.2f}x", ha="center", va="bottom", color="white", fontsize=8)

            # Subplot 3: Total Bullets Fired
            ax3.bar(x_eff, eff_bullets, color="#fee75c", alpha=0.8)
            ax3.set_xticks(x_eff)
            ax3.set_xticklabels(eff_names, rotation=20, ha="right", color="white", fontsize=9)
            ax3.set_ylabel("Bullets Fired", color="white", fontsize=11)
            ax3.set_title("Total Ammunition Fired", color="white", fontsize=12, fontweight="bold")
            ax3.set_facecolor("#1e1f22")
            ax3.tick_params(colors="white")
            ax3.spines["bottom"].set_color("white")
            ax3.spines["left"].set_color("white")
            ax3.spines["top"].set_visible(False)
            ax3.spines["right"].set_visible(False)
            ax3.grid(True, alpha=0.2, color="white", axis="y")
            for i, v in enumerate(eff_bullets):
                ax3.text(i, v, f"{int(v):,}", ha="center", va="bottom", color="white", fontsize=8)

            # Subplot 4: Bullets per Kill
            colors_bpk = ["#57f287" if b < 100 else "#fee75c" if b < 200 else "#ed4245" for b in eff_bullets_per_kill]
            ax4.bar(x_eff, eff_bullets_per_kill, color=colors_bpk, alpha=0.8)
            ax4.set_xticks(x_eff)
            ax4.set_xticklabels(eff_names, rotation=20, ha="right", color="white", fontsize=9)
            ax4.set_ylabel("Bullets per Kill", color="white", fontsize=11)
            ax4.set_title("Accuracy Metric (Lower = Better)", color="white", fontsize=12, fontweight="bold")
            ax4.set_facecolor("#1e1f22")
            ax4.tick_params(colors="white")
            ax4.spines["bottom"].set_color("white")
            ax4.spines["left"].set_color("white")
            ax4.spines["top"].set_visible(False)
            ax4.spines["right"].set_visible(False)
            ax4.grid(True, alpha=0.2, color="white", axis="y")
            for i, v in enumerate(eff_bullets_per_kill):
                ax4.text(i, v, f"{v:.0f}", ha="center", va="bottom", color="white", fontsize=8)

            plt.tight_layout()

            buf = io.BytesIO()
            plt.savefig(buf, format="png", facecolor='#2b2d31', dpi=100, bbox_inches="tight")
            buf.seek(0)
            plt.close()

            return buf

        except ImportError:
            logger.warning("matplotlib not installed - graphs unavailable")
            return None
        except Exception as e:
            logger.exception(f"Error generating combat efficiency graphs: {e}")
            return None

    # ═══════════════════════════════════════════════════════
