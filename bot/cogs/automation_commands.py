"""
🤖 Automation Commands Cog
===========================

Discord commands for managing and monitoring automation services.

Commands:
- !health - Show bot health status
- !ssh_stats - SSH monitor statistics
- !metrics_report - Generate metrics report
- !backup_db - Manual database backup
- !start_monitoring - Start SSH monitoring
- !stop_monitoring - Stop SSH monitoring
"""

import discord
from discord.ext import commands
import logging
from datetime import datetime

from bot.core.checks import is_admin_channel

logger = logging.getLogger("AutomationCommands")


class AutomationCommands(commands.Cog):
    """Commands for automation management"""
    
    def __init__(self, bot):
        self.bot = bot
        logger.info("✅ Automation Commands Cog loaded")
    
    @is_admin_channel()
    @commands.command(name="health")
    async def health_command(self, ctx):
        """📊 Show comprehensive bot health status"""
        try:
            if not hasattr(self.bot, 'health_monitor'):
                await ctx.send("⚠️ Health monitoring not initialized")
                return
            
            embed = await self.bot.health_monitor.get_health_report()
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"❌ Health command error: {e}")
            await ctx.send(f"❌ Error getting health status: {e}")
    
    @is_admin_channel()
    @commands.command(name="ssh_stats")
    async def ssh_stats_command(self, ctx):
        """🔄 Show SSH monitor statistics and status"""
        try:
            if not hasattr(self.bot, 'ssh_monitor'):
                await ctx.send("⚠️ SSH monitor not initialized")
                return

            stats = self.bot.ssh_monitor.get_stats()

            # Choose color based on status
            if stats['is_monitoring']:
                color = 0x57F287  # Green
                status_text = "🟢 **Active Monitoring**"
            else:
                color = 0xED4245  # Red
                status_text = "🔴 **Stopped**"

            embed = discord.Embed(
                title="🔄 SSH Monitor Statistics",
                description=status_text,
                color=color,
                timestamp=datetime.now()
            )

            # Files processed
            embed.add_field(
                name="📁 Files Processed",
                value=f"```\n{stats['files_processed']:,}\n```",
                inline=True
            )

            # Files tracked
            embed.add_field(
                name="📊 Files Tracked",
                value=f"```\n{stats['files_tracked']}\n```",
                inline=True
            )

            # Errors
            error_icon = "⚠️" if stats['errors_count'] > 5 else "✅"
            error_color = "⚠️" if stats['errors_count'] > 5 else "🟢"
            embed.add_field(
                name=f"{error_color} Error Count",
                value=f"```\n{stats['errors_count']}\n```",
                inline=True
            )

            # Performance metrics
            embed.add_field(
                name="⚡ Avg Check Time",
                value=f"```\n{stats['avg_check_time_ms']:.1f} ms\n```",
                inline=True
            )

            embed.add_field(
                name="📥 Avg Download Time",
                value=f"```\n{stats['avg_download_time_ms']:.1f} ms\n```",
                inline=True
            )

            embed.add_field(
                name="⏱️ Check Interval",
                value=f"```\n{stats['check_interval']}s\n```",
                inline=True
            )

            # Last check time
            if stats['last_check']:
                time_str = stats['last_check'].strftime("%Y-%m-%d %H:%M:%S")
                embed.add_field(
                    name="🕐 Last Check",
                    value=f"`{time_str}`",
                    inline=False
                )

            # Last error (if any)
            if stats['last_error']:
                error_preview = stats['last_error'][:100]
                embed.add_field(
                    name="❌ Last Error",
                    value=f"```\n{error_preview}\n```",
                    inline=False
                )

            embed.set_footer(text=f"Requested by {ctx.author.name}")
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"❌ SSH stats command error: {e}")
            await ctx.send(f"❌ Error getting SSH stats: {e}")
    
    @commands.command(name="start_monitoring")
    @commands.has_permissions(administrator=True)
    async def start_monitoring_command(self, ctx):
        """🟢 Start SSH monitoring"""
        try:
            if not hasattr(self.bot, 'ssh_monitor'):
                await ctx.send("⚠️ SSH monitor not initialized")
                return
            
            if self.bot.ssh_monitor.is_monitoring:
                await ctx.send("ℹ️ Monitoring is already active")
                return
            
            await ctx.send("🔄 Starting SSH monitoring...")
            await self.bot.ssh_monitor.start_monitoring()
            await ctx.send("✅ SSH monitoring started!")
            
        except Exception as e:
            logger.error(f"❌ Start monitoring error: {e}")
            await ctx.send(f"❌ Error starting monitoring: {e}")
    
    @is_admin_channel()
    @commands.command(name="stop_monitoring")
    @commands.has_permissions(administrator=True)
    async def stop_monitoring_command(self, ctx):
        """🔴 Stop SSH monitoring"""
        try:
            if not hasattr(self.bot, 'ssh_monitor'):
                await ctx.send("⚠️ SSH monitor not initialized")
                return
            
            if not self.bot.ssh_monitor.is_monitoring:
                await ctx.send("ℹ️ Monitoring is not active")
                return
            
            await ctx.send("🛑 Stopping SSH monitoring...")
            await self.bot.ssh_monitor.stop_monitoring()
            await ctx.send("✅ SSH monitoring stopped!")
            
        except Exception as e:
            logger.error(f"❌ Stop monitoring error: {e}")
            await ctx.send(f"❌ Error stopping monitoring: {e}")
    
    @commands.command(name="metrics_report")
    @commands.has_permissions(administrator=True)
    async def metrics_report_command(self, ctx, hours: int = 24):
        """📊 Generate comprehensive metrics report"""
        try:
            if not hasattr(self.bot, 'metrics'):
                await ctx.send("⚠️ Metrics logger not initialized")
                return
            
            if hours < 1 or hours > 720:  # Max 30 days
                await ctx.send("⚠️ Hours must be between 1 and 720 (30 days)")
                return
            
            await ctx.send(f"📊 Generating metrics report for last {hours} hours...")
            
            report = await self.bot.metrics.generate_report(hours=hours)
            
            if not report:
                await ctx.send("❌ Failed to generate report")
                return
            
            # Create summary embed with color based on error rate
            summary = report.get('summary', {})
            error_rate = summary.get('error_rate', 0)

            if error_rate < 1:
                color = 0x57F287  # Green
            elif error_rate < 5:
                color = 0xFEE75C  # Yellow
            else:
                color = 0xED4245  # Red

            embed = discord.Embed(
                title=f"📊 Metrics Report",
                description=f"Performance analysis for last `{hours}` hours",
                color=color,
                timestamp=datetime.now()
            )

            # Overall summary
            if summary:
                embed.add_field(
                    name="📈 Overall Summary",
                    value=(
                        f"Total Events: `{summary.get('total_events', 0):,}`\n"
                        f"Total Errors: `{summary.get('total_errors', 0):,}`\n"
                        f"Error Rate: `{error_rate:.2f}%`\n"
                        f"Events/Hour: `{summary.get('events_per_hour', 0):.1f}`"
                    ),
                    inline=False
                )

            # Top events
            events = report.get('events', {})
            if events:
                top_events = sorted(events.items(), key=lambda x: x[1]['count'], reverse=True)[:5]
                event_text = []
                for event_type, data in top_events:
                    event_text.append(
                        f"• **{event_type}**: `{data['count']:,}` "
                        f"(✅ {data['success_rate']:.1f}%)"
                    )

                if event_text:
                    embed.add_field(
                        name="🎯 Top Events",
                        value="\n".join(event_text),
                        inline=False
                    )

            # Errors (if any)
            errors = report.get('errors', {})
            if errors:
                error_text = []
                for error_type, data in sorted(errors.items(), key=lambda x: x[1]['count'], reverse=True)[:5]:
                    error_text.append(f"• **{error_type}**: `{data['count']:,}`")

                if error_text:
                    embed.add_field(
                        name="❌ Top Errors",
                        value="\n".join(error_text),
                        inline=False
                    )

            # Health
            health = report.get('health', {})
            if health:
                embed.add_field(
                    name="🏥 Health Metrics",
                    value=(
                        f"Checks: `{health.get('total_checks', 0):,}`\n"
                        f"Healthy: `{health.get('health_rate', 0):.1f}%`\n"
                        f"Avg Memory: `{health.get('avg_memory_mb', 0):.1f} MB`\n"
                        f"Avg CPU: `{health.get('avg_cpu_percent', 0):.1f}%`"
                    ),
                    inline=True
                )

            embed.set_footer(text=f"Report period: {hours}h • Requested by {ctx.author.name}")
            await ctx.send(embed=embed)
            
            # Offer to export full report
            await ctx.send("💾 Exporting full report to JSON...")
            filepath = await self.bot.metrics.export_to_json()
            
            if filepath:
                await ctx.send(f"✅ Full report exported to: `{filepath}`")
            
        except Exception as e:
            logger.error(f"❌ Metrics report error: {e}", exc_info=True)
            await ctx.send(f"❌ Error generating report: {e}")
    
    @commands.command(name="metrics_summary")
    async def metrics_summary_command(self, ctx):
        """📊 Quick metrics summary"""
        try:
            if not hasattr(self.bot, 'metrics'):
                await ctx.send("⚠️ Metrics logger not initialized")
                return

            summary = self.bot.metrics.get_summary()

            # Calculate error rate for color
            total_events = summary.get('total_events', 0)
            total_errors = summary.get('total_errors', 0)
            error_rate = (total_errors / total_events * 100) if total_events > 0 else 0

            if error_rate < 1:
                color = 0x57F287  # Green
            elif error_rate < 5:
                color = 0xFEE75C  # Yellow
            else:
                color = 0xED4245  # Red

            embed = discord.Embed(
                title="📊 Metrics Summary",
                description=f"Bot performance overview • Error rate: `{error_rate:.2f}%`",
                color=color,
                timestamp=datetime.now()
            )

            embed.add_field(
                name="⏱️ Uptime",
                value=f"```\n{summary['uptime_formatted']}\n```",
                inline=True
            )

            embed.add_field(
                name="📝 Events Logged",
                value=f"```\n{summary['total_events']:,}\n```",
                inline=True
            )

            embed.add_field(
                name="❌ Errors Logged",
                value=f"```\n{summary['total_errors']:,}\n```",
                inline=True
            )

            if summary.get('most_common_event'):
                embed.add_field(
                    name="🎯 Most Common Event",
                    value=f"`{summary['most_common_event']}`",
                    inline=False
                )

            if summary.get('most_common_error'):
                embed.add_field(
                    name="⚠️ Most Common Error",
                    value=f"`{summary['most_common_error']}`",
                    inline=False
                )

            embed.set_footer(text=f"Requested by {ctx.author.name}")
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"❌ Metrics summary error: {e}")
            await ctx.send(f"❌ Error getting summary: {e}")
    
    @commands.command(name="backup_db")
    @commands.has_permissions(administrator=True)
    async def backup_command(self, ctx):
        """💾 Manually trigger database backup"""
        try:
            if not hasattr(self.bot, 'db_maintenance'):
                await ctx.send("⚠️ Database maintenance not initialized")
                return
            
            await ctx.send("💾 Creating database backup...")
            
            success = await self.bot.db_maintenance.backup_database()
            
            if success:
                stats = self.bot.db_maintenance.get_stats()
                await ctx.send(
                    f"✅ Backup complete!\n"
                    f"Total backups: {stats['backup_count']}\n"
                    f"Last backup: {stats.get('last_backup', 'N/A')}"
                )
            else:
                await ctx.send("❌ Backup failed - check logs for details")
                
        except Exception as e:
            logger.error(f"❌ Backup command error: {e}")
            await ctx.send(f"❌ Error creating backup: {e}")
    
    @commands.command(name="vacuum_db")
    @commands.has_permissions(administrator=True)
    async def vacuum_command(self, ctx):
        """🧹 Optimize database (VACUUM)"""
        try:
            if not hasattr(self.bot, 'db_maintenance'):
                await ctx.send("⚠️ Database maintenance not initialized")
                return
            
            await ctx.send("🧹 Optimizing database...")
            
            success = await self.bot.db_maintenance.vacuum_database()
            
            if success:
                await ctx.send("✅ Database optimized successfully!")
            else:
                await ctx.send("❌ Optimization failed - check logs")
                
        except Exception as e:
            logger.error(f"❌ Vacuum command error: {e}")
            await ctx.send(f"❌ Error optimizing database: {e}")
    
    @commands.command(name="automation_status")
    async def automation_status_command(self, ctx):
        """📋 Show all automation services status"""
        try:
            # Determine overall health color
            all_healthy = True

            # Check SSH monitor
            ssh_healthy = False
            if hasattr(self.bot, 'ssh_monitor'):
                stats = self.bot.ssh_monitor.get_stats()
                ssh_healthy = stats.get('is_monitoring', False) and stats.get('errors_count', 0) < 10
                all_healthy = all_healthy and ssh_healthy

            # Determine color
            if all_healthy:
                color = 0x57F287  # Green
                status_emoji = "🟢"
                status_text = "All systems operational"
            else:
                color = 0xFEE75C  # Yellow
                status_emoji = "🟡"
                status_text = "Some services need attention"

            embed = discord.Embed(
                title="🤖 Automation Services Status",
                description=f"{status_emoji} **{status_text}**",
                color=color,
                timestamp=datetime.now()
            )

            # SSH Monitor
            if hasattr(self.bot, 'ssh_monitor'):
                stats = self.bot.ssh_monitor.get_stats()
                ssh_status = "🟢 **Active**" if stats['is_monitoring'] else "🔴 **Stopped**"
                ssh_value = (
                    f"{ssh_status}\n"
                    f"Files: `{stats['files_processed']:,}`\n"
                    f"Errors: `{stats['errors_count']}`"
                )
                embed.add_field(name="🔄 SSH Monitor", value=ssh_value, inline=True)
            else:
                embed.add_field(name="🔄 SSH Monitor", value="❌ **Not initialized**", inline=True)

            # Health Monitor
            if hasattr(self.bot, 'health_monitor'):
                health_status = "🟢 **Active**" if self.bot.health_monitor.is_monitoring else "🔴 **Stopped**"
                embed.add_field(name="🏥 Health Monitor", value=health_status, inline=True)
            else:
                embed.add_field(name="🏥 Health Monitor", value="❌ **Not initialized**", inline=True)

            # Metrics Logger
            if hasattr(self.bot, 'metrics'):
                summary = self.bot.metrics.get_summary()
                metrics_value = (
                    f"Events: `{summary['total_events']:,}`\n"
                    f"Errors: `{summary['total_errors']:,}`"
                )
                embed.add_field(name="📊 Metrics Logger", value=metrics_value, inline=True)
            else:
                embed.add_field(name="📊 Metrics Logger", value="❌ **Not initialized**", inline=True)

            # Database Maintenance
            if hasattr(self.bot, 'db_maintenance'):
                maint_stats = self.bot.db_maintenance.get_stats()
                last_backup = maint_stats.get('last_backup', 'Never')
                if last_backup != 'Never' and len(last_backup) > 10:
                    last_backup = last_backup[:10]
                maint_value = (
                    f"Backups: `{maint_stats['backup_count']}`\n"
                    f"Last: `{last_backup}`"
                )
                embed.add_field(name="🔧 DB Maintenance", value=maint_value, inline=True)
            else:
                embed.add_field(name="🔧 DB Maintenance", value="❌ **Not initialized**", inline=True)

            # Bot info
            monitoring_status = "✅ **Enabled**" if getattr(self.bot, 'monitoring', False) else "❌ **Disabled**"
            automation_status = "✅ **Enabled**" if getattr(self.bot, 'automation_enabled', False) else "❌ **Disabled**"
            embed.add_field(
                name="🤖 Bot Status",
                value=f"Monitoring: {monitoring_status}\nAutomation: {automation_status}",
                inline=True
            )

            # Uptime
            if hasattr(self.bot, 'metrics') and hasattr(self.bot.metrics, 'get_summary'):
                summary = self.bot.metrics.get_summary()
                if 'uptime_formatted' in summary:
                    embed.add_field(
                        name="⏱️ Uptime",
                        value=f"```\n{summary['uptime_formatted']}\n```",
                        inline=True
                    )

            embed.set_footer(text=f"Requested by {ctx.author.name} • Use !health for detailed bot health")
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"❌ Status command error: {e}")
            await ctx.send(f"❌ Error getting status: {e}")


async def setup(bot):
    """Setup function for loading the cog"""
    await bot.add_cog(AutomationCommands(bot))
    logger.info("✅ Automation Commands Cog registered")
