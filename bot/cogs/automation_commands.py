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

logger = logging.getLogger("AutomationCommands")


class AutomationCommands(commands.Cog):
    """Commands for automation management"""
    
    def __init__(self, bot):
        self.bot = bot
        logger.info("✅ Automation Commands Cog loaded")
    
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
    
    @commands.command(name="ssh_stats")
    async def ssh_stats_command(self, ctx):
        """🔄 Show SSH monitor statistics and status"""
        try:
            if not hasattr(self.bot, 'ssh_monitor'):
                await ctx.send("⚠️ SSH monitor not initialized")
                return
            
            stats = self.bot.ssh_monitor.get_stats()
            
            embed = discord.Embed(
                title="🔄 SSH Monitor Status",
                color=discord.Color.green() if stats['is_monitoring'] else discord.Color.red(),
                timestamp=datetime.now()
            )
            
            # Status
            status_emoji = "🟢" if stats['is_monitoring'] else "🔴"
            embed.add_field(
                name="Status",
                value=f"{status_emoji} {'Monitoring' if stats['is_monitoring'] else 'Stopped'}",
                inline=True
            )
            
            # Files processed
            embed.add_field(
                name="Files Processed",
                value=str(stats['files_processed']),
                inline=True
            )
            
            # Errors
            error_icon = "⚠️" if stats['errors_count'] > 5 else "✅"
            embed.add_field(
                name="Errors",
                value=f"{error_icon} {stats['errors_count']}",
                inline=True
            )
            
            # Last check time
            if stats['last_check']:
                time_str = stats['last_check'].strftime("%H:%M:%S")
                embed.add_field(
                    name="Last Check",
                    value=time_str,
                    inline=True
                )
            
            # Performance
            embed.add_field(
                name="Avg Check Time",
                value=f"{stats['avg_check_time_ms']:.1f} ms",
                inline=True
            )
            
            embed.add_field(
                name="Avg Download Time",
                value=f"{stats['avg_download_time_ms']:.1f} ms",
                inline=True
            )
            
            # Files tracked
            embed.add_field(
                name="Files Tracked",
                value=f"{stats['files_tracked']} files",
                inline=True
            )
            
            # Check interval
            embed.add_field(
                name="Check Interval",
                value=f"{stats['check_interval']}s",
                inline=True
            )
            
            # Last error (if any)
            if stats['last_error']:
                embed.add_field(
                    name="Last Error",
                    value=f"```{stats['last_error'][:100]}```",
                    inline=False
                )
            
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
            
            # Create summary embed
            embed = discord.Embed(
                title=f"📊 Metrics Report ({hours}h)",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            # Overall summary
            summary = report.get('summary', {})
            if summary:
                embed.add_field(
                    name="📈 Overall Summary",
                    value=f"Total Events: {summary.get('total_events', 0)}\n"
                          f"Total Errors: {summary.get('total_errors', 0)}\n"
                          f"Error Rate: {summary.get('error_rate', 0):.2f}%\n"
                          f"Events/Hour: {summary.get('events_per_hour', 0):.1f}",
                    inline=False
                )
            
            # Top events
            events = report.get('events', {})
            if events:
                top_events = sorted(events.items(), key=lambda x: x[1]['count'], reverse=True)[:5]
                event_text = []
                for event_type, data in top_events:
                    event_text.append(
                        f"**{event_type}**: {data['count']} "
                        f"(success: {data['success_rate']:.1f}%)"
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
                    error_text.append(f"**{error_type}**: {data['count']}")
                
                if error_text:
                    embed.add_field(
                        name="❌ Errors",
                        value="\n".join(error_text),
                        inline=False
                    )
            
            # Health
            health = report.get('health', {})
            if health:
                embed.add_field(
                    name="🏥 Health",
                    value=f"Checks: {health.get('total_checks', 0)}\n"
                          f"Healthy: {health.get('health_rate', 0):.1f}%\n"
                          f"Avg Memory: {health.get('avg_memory_mb', 0):.1f} MB\n"
                          f"Avg CPU: {health.get('avg_cpu_percent', 0):.1f}%",
                    inline=True
                )
            
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
            
            embed = discord.Embed(
                title="📊 Metrics Summary",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="Uptime",
                value=summary['uptime_formatted'],
                inline=True
            )
            
            embed.add_field(
                name="Events Logged",
                value=str(summary['total_events']),
                inline=True
            )
            
            embed.add_field(
                name="Errors Logged",
                value=str(summary['total_errors']),
                inline=True
            )
            
            if summary['most_common_event']:
                embed.add_field(
                    name="Most Common Event",
                    value=summary['most_common_event'],
                    inline=False
                )
            
            if summary['most_common_error']:
                embed.add_field(
                    name="Most Common Error",
                    value=summary['most_common_error'],
                    inline=False
                )
            
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
            embed = discord.Embed(
                title="🤖 Automation Services Status",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            # SSH Monitor
            if hasattr(self.bot, 'ssh_monitor'):
                stats = self.bot.ssh_monitor.get_stats()
                ssh_status = "🟢 Active" if stats['is_monitoring'] else "🔴 Stopped"
                ssh_value = f"{ssh_status}\nFiles: {stats['files_processed']}\nErrors: {stats['errors_count']}"
                embed.add_field(name="🔄 SSH Monitor", value=ssh_value, inline=True)
            else:
                embed.add_field(name="🔄 SSH Monitor", value="❌ Not initialized", inline=True)
            
            # Health Monitor
            if hasattr(self.bot, 'health_monitor'):
                health_status = "🟢 Active" if self.bot.health_monitor.is_monitoring else "🔴 Stopped"
                embed.add_field(name="🏥 Health Monitor", value=health_status, inline=True)
            else:
                embed.add_field(name="🏥 Health Monitor", value="❌ Not initialized", inline=True)
            
            # Metrics Logger
            if hasattr(self.bot, 'metrics'):
                summary = self.bot.metrics.get_summary()
                metrics_value = f"Events: {summary['total_events']}\nErrors: {summary['total_errors']}"
                embed.add_field(name="📊 Metrics", value=metrics_value, inline=True)
            else:
                embed.add_field(name="📊 Metrics", value="❌ Not initialized", inline=True)
            
            # Database Maintenance
            if hasattr(self.bot, 'db_maintenance'):
                maint_stats = self.bot.db_maintenance.get_stats()
                maint_value = f"Backups: {maint_stats['backup_count']}\nLast: {maint_stats.get('last_backup', 'Never')[:10] if maint_stats.get('last_backup') else 'Never'}"
                embed.add_field(name="🔧 Maintenance", value=maint_value, inline=True)
            else:
                embed.add_field(name="🔧 Maintenance", value="❌ Not initialized", inline=True)
            
            # Bot info
            embed.add_field(
                name="🤖 Bot",
                value=f"Monitoring: {'✅' if getattr(self.bot, 'monitoring', False) else '❌'}\n"
                      f"Automation: {'✅' if getattr(self.bot, 'automation_enabled', False) else '❌'}",
                inline=True
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"❌ Status command error: {e}")
            await ctx.send(f"❌ Error getting status: {e}")


async def setup(bot):
    """Setup function for loading the cog"""
    await bot.add_cog(AutomationCommands(bot))
    logger.info("✅ Automation Commands Cog registered")
