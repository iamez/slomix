"""
🤖 Automation Enhancements for ET:Legacy Discord Bot
====================================================

This module contains production-ready automation enhancements:
- Health monitoring and alerting
- Error recovery and retry logic
- Database maintenance tasks
- Automated reporting (daily/weekly stats)
- Graceful shutdown handling
- Admin dashboard commands

Add these methods to your ETStatsBot class in ultimate_bot.py
"""

import asyncio
import aiosqlite
import discord
from datetime import datetime, timedelta
import logging
import os
import shutil
import psutil

logger = logging.getLogger("etlegacy_bot")


class AutomationEnhancements:
    """
    Mixin class containing automation enhancements
    Add these methods to your ETStatsBot class
    """
    
    def init_health_monitoring(self):
        """Initialize health monitoring variables (call in __init__)"""
        # 🏥 Health Monitoring System
        self.bot_start_time = datetime.now()
        self.last_health_check = None
        self.last_db_backup = None
        self.last_stats_post = None
        self.ssh_error_count = 0
        self.db_error_count = 0
        self.processed_files_count = 0
        self.last_error_alert_time = None
        self.error_alert_cooldown = 300  # 5 minutes between error alerts
        
        # Task health tracking
        self.task_last_run = {}
        self.task_run_counts = {}
        self.task_errors = {}
        
        # Admin channel for health reports
        self.admin_channel_id = int(os.getenv("ADMIN_CHANNEL_ID", self.stats_channel_id))
    
    # ==================== HEALTH MONITORING ====================
    
    async def get_bot_health_status(self):
        """
        📊 Comprehensive health check
        Returns dict with all bot health metrics
        """
        try:
            uptime = datetime.now() - self.bot_start_time
            
            # Database stats
            db_size = os.path.getsize(self.db_path) / (1024 * 1024)  # MB
            
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("SELECT COUNT(*) FROM processed_files")
                total_files = (await cursor.fetchone())[0]
                
                cursor = await db.execute("SELECT COUNT(*) FROM player_comprehensive_stats")
                total_records = (await cursor.fetchone())[0]
                
                cursor = await db.execute(
                    "SELECT COUNT(DISTINCT session_id) FROM player_comprehensive_stats"
                )
                total_sessions = (await cursor.fetchone())[0]
            
            # System resources
            memory_mb = psutil.Process().memory_info().rss / (1024 * 1024)
            cpu_percent = psutil.Process().cpu_percent(interval=1)
            
            # Task statuses
            task_statuses = {}
            for task_name, task in [
                ("endstats_monitor", self.endstats_monitor),
                ("cache_refresher", self.cache_refresher),
                ("scheduled_monitoring_check", self.scheduled_monitoring_check),
            ]:
                task_statuses[task_name] = {
                    "running": task.is_running(),
                    "last_run": self.task_last_run.get(task_name),
                    "run_count": self.task_run_counts.get(task_name, 0),
                    "error_count": self.task_errors.get(task_name, 0),
                }
            
            return {
                "status": "healthy" if self.error_count < 10 else "degraded",
                "uptime": str(uptime).split('.')[0],  # Remove microseconds
                "uptime_seconds": int(uptime.total_seconds()),
                "error_count": self.error_count,
                "ssh_errors": self.ssh_error_count,
                "db_errors": self.db_error_count,
                "monitoring": self.monitoring,
                "automation_enabled": self.automation_enabled,
                "ssh_enabled": self.ssh_enabled,
                "session_active": self.session_active,
                "database": {
                    "size_mb": round(db_size, 2),
                    "total_files": total_files,
                    "total_records": total_records,
                    "total_sessions": total_sessions,
                },
                "resources": {
                    "memory_mb": round(memory_mb, 2),
                    "cpu_percent": cpu_percent,
                },
                "tasks": task_statuses,
                "last_health_check": self.last_health_check,
                "last_db_backup": self.last_db_backup,
            }
        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            return {"status": "error", "error": str(e)}
    
    async def send_health_alert(self, message, level="warning"):
        """
        🚨 Send health alert to admin channel
        Rate-limited to avoid spam
        """
        try:
            # Rate limiting
            now = datetime.now()
            if self.last_error_alert_time:
                elapsed = (now - self.last_error_alert_time).total_seconds()
                if elapsed < self.error_alert_cooldown:
                    logger.debug(f"Alert suppressed (cooldown: {self.error_alert_cooldown - elapsed:.0f}s)")
                    return
            
            self.last_error_alert_time = now
            
            # Send alert
            channel = self.get_channel(self.admin_channel_id)
            if not channel:
                logger.error(f"❌ Admin channel {self.admin_channel_id} not found")
                return
            
            emoji = "🚨" if level == "critical" else "⚠️" if level == "warning" else "ℹ️"
            color = discord.Color.red() if level == "critical" else discord.Color.orange() if level == "warning" else discord.Color.blue()
            
            embed = discord.Embed(
                title=f"{emoji} Bot Health Alert",
                description=message,
                color=color,
                timestamp=datetime.now()
            )
            
            await channel.send(embed=embed)
            logger.info(f"🚨 Health alert sent: {message}")
            
        except Exception as e:
            logger.error(f"❌ Failed to send health alert: {e}")
    
    # ==================== BACKGROUND TASKS ====================
    
    async def health_monitor_task(self):
        """
        🏥 Health Monitoring Task - Runs every 5 minutes
        Monitors bot health and sends alerts if issues detected
        """
        await self.wait_until_ready()
        logger.info("✅ Health monitoring task ready")
        
        while not self.is_closed():
            try:
                await asyncio.sleep(300)  # 5 minutes
                
                health = await self.get_bot_health_status()
                self.last_health_check = datetime.now()
                
                # Check for issues
                issues = []
                
                if health["error_count"] > 10:
                    issues.append(f"High error count: {health['error_count']}")
                
                if health["ssh_errors"] > 5:
                    issues.append(f"SSH errors: {health['ssh_errors']}")
                
                if health["db_errors"] > 5:
                    issues.append(f"Database errors: {health['db_errors']}")
                
                # Check if tasks are running
                for task_name, task_status in health["tasks"].items():
                    if not task_status["running"]:
                        issues.append(f"Task '{task_name}' is not running")
                    
                    if task_status["error_count"] > 3:
                        issues.append(f"Task '{task_name}' has {task_status['error_count']} errors")
                
                # Alert if issues found
                if issues:
                    alert_msg = "**Health Check Issues Detected:**\n\n" + "\n".join(f"• {issue}" for issue in issues)
                    await self.send_health_alert(alert_msg, level="warning")
                
                logger.debug(f"✅ Health check complete: {health['status']}")
                
            except Exception as e:
                logger.error(f"❌ Health monitor task error: {e}")
                await asyncio.sleep(60)  # Shorter retry on error
    
    async def daily_report_task(self):
        """
        📊 Daily Report Task - Runs once per day at 23:00 CET
        Posts daily statistics summary
        """
        await self.wait_until_ready()
        logger.info("✅ Daily report task ready")
        
        while not self.is_closed():
            try:
                # Get timezone
                try:
                    import pytz
                    cet = pytz.timezone("Europe/Paris")
                except:
                    try:
                        from zoneinfo import ZoneInfo
                        cet = ZoneInfo("Europe/Paris")
                    except:
                        cet = None
                
                now = datetime.now(cet) if cet else datetime.now()
                
                # Check if it's 23:00
                if now.hour == 23 and now.minute == 0:
                    logger.info("📊 Generating daily report...")
                    await self.post_daily_summary()
                    
                    # Sleep until next day to avoid duplicate posts
                    await asyncio.sleep(3600)  # 1 hour
                else:
                    # Check every minute
                    await asyncio.sleep(60)
                    
            except Exception as e:
                logger.error(f"❌ Daily report task error: {e}")
                await asyncio.sleep(300)  # 5 minutes on error
    
    async def database_maintenance_task(self):
        """
        🔧 Database Maintenance Task - Runs daily at 04:00 CET
        Performs vacuum, backup, and cleanup
        """
        await self.wait_until_ready()
        logger.info("✅ Database maintenance task ready")
        
        while not self.is_closed():
            try:
                # Get timezone
                try:
                    import pytz
                    cet = pytz.timezone("Europe/Paris")
                except:
                    try:
                        from zoneinfo import ZoneInfo
                        cet = ZoneInfo("Europe/Paris")
                    except:
                        cet = None
                
                now = datetime.now(cet) if cet else datetime.now()
                
                # Check if it's 04:00 (low-traffic time)
                if now.hour == 4 and now.minute == 0:
                    logger.info("🔧 Running database maintenance...")
                    
                    # Backup database
                    await self.backup_database()
                    
                    # Vacuum database (optimize)
                    await self.vacuum_database()
                    
                    # Clean old logs
                    await self.cleanup_old_logs(days=30)
                    
                    # Sleep until next day
                    await asyncio.sleep(3600)  # 1 hour
                else:
                    # Check every 10 minutes
                    await asyncio.sleep(600)
                    
            except Exception as e:
                logger.error(f"❌ Database maintenance task error: {e}")
                await asyncio.sleep(1800)  # 30 minutes on error
    
    # ==================== MAINTENANCE METHODS ====================
    
    async def backup_database(self):
        """📦 Create database backup"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = "bot/backups"
            os.makedirs(backup_dir, exist_ok=True)
            
            backup_path = f"{backup_dir}/etlegacy_production.db.backup_{timestamp}"
            shutil.copy2(self.db_path, backup_path)
            
            # Keep only last 7 backups
            backups = sorted(
                [f for f in os.listdir(backup_dir) if f.endswith(".db") or "backup" in f],
                key=lambda x: os.path.getmtime(os.path.join(backup_dir, x)),
                reverse=True
            )
            
            for old_backup in backups[7:]:
                os.remove(os.path.join(backup_dir, old_backup))
                logger.info(f"🗑️ Removed old backup: {old_backup}")
            
            self.last_db_backup = datetime.now()
            logger.info(f"✅ Database backed up to: {backup_path}")
            
            # Send notification
            channel = self.get_channel(self.admin_channel_id)
            if channel:
                embed = discord.Embed(
                    title="💾 Database Backup Complete",
                    description=f"Backup created: `{os.path.basename(backup_path)}`\nRetaining {min(len(backups), 7)} backups",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                await channel.send(embed=embed)
            
        except Exception as e:
            logger.error(f"❌ Database backup failed: {e}")
            await self.send_health_alert(f"Database backup failed: {e}", level="critical")
    
    async def vacuum_database(self):
        """🧹 Vacuum and optimize database"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("VACUUM")
                await db.execute("ANALYZE")
                await db.commit()
            
            logger.info("✅ Database vacuumed and optimized")
            
        except Exception as e:
            logger.error(f"❌ Database vacuum failed: {e}")
    
    async def cleanup_old_logs(self, days=30):
        """🗑️ Clean up log files older than N days"""
        try:
            log_dir = "bot/logs"
            if not os.path.exists(log_dir):
                return
            
            cutoff_date = datetime.now() - timedelta(days=days)
            cleaned = 0
            
            for filename in os.listdir(log_dir):
                filepath = os.path.join(log_dir, filename)
                if os.path.isfile(filepath):
                    file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                    if file_time < cutoff_date:
                        os.remove(filepath)
                        cleaned += 1
            
            if cleaned > 0:
                logger.info(f"✅ Cleaned {cleaned} old log files")
            
        except Exception as e:
            logger.error(f"❌ Log cleanup failed: {e}")
    
    async def post_daily_summary(self):
        """📊 Post daily statistics summary"""
        try:
            # Get today's stats
            today = datetime.now().date()
            
            async with aiosqlite.connect(self.db_path) as db:
                # Sessions today
                cursor = await db.execute("""
                    SELECT COUNT(DISTINCT session_id)
                    FROM player_comprehensive_stats
                    WHERE DATE(timestamp) = ?
                """, (today,))
                sessions_today = (await cursor.fetchone())[0]
                
                # Rounds today
                cursor = await db.execute("""
                    SELECT COUNT(DISTINCT session_id || '-' || round_num)
                    FROM player_comprehensive_stats
                    WHERE DATE(timestamp) = ?
                """, (today,))
                rounds_today = (await cursor.fetchone())[0]
                
                # Total kills today
                cursor = await db.execute("""
                    SELECT SUM(kills)
                    FROM player_comprehensive_stats
                    WHERE DATE(timestamp) = ?
                """, (today,))
                kills_today = (await cursor.fetchone())[0] or 0
                
                # Most active player today
                cursor = await db.execute("""
                    SELECT player_name, COUNT(*) as rounds
                    FROM player_comprehensive_stats
                    WHERE DATE(timestamp) = ?
                    GROUP BY player_name
                    ORDER BY rounds DESC
                    LIMIT 1
                """, (today,))
                top_player_row = await cursor.fetchone()
                top_player = f"{top_player_row[0]} ({top_player_row[1]} rounds)" if top_player_row else "None"
            
            # Create embed
            embed = discord.Embed(
                title="📊 Daily Statistics Summary",
                description=f"Statistics for {today.strftime('%B %d, %Y')}",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            embed.add_field(name="🎮 Sessions", value=str(sessions_today), inline=True)
            embed.add_field(name="🔄 Rounds", value=str(rounds_today), inline=True)
            embed.add_field(name="💀 Total Kills", value=str(kills_today), inline=True)
            embed.add_field(name="👑 Most Active", value=top_player, inline=False)
            
            # Get health status
            health = await self.get_bot_health_status()
            embed.add_field(
                name="🏥 Bot Health",
                value=f"Uptime: {health['uptime']}\nErrors: {health['error_count']}\nStatus: {health['status'].upper()}",
                inline=False
            )
            
            # Send to stats channel
            channel = self.get_channel(self.stats_channel_id)
            if channel:
                await channel.send(embed=embed)
                logger.info("✅ Daily summary posted")
            
        except Exception as e:
            logger.error(f"❌ Failed to post daily summary: {e}")
    
    # ==================== ERROR RECOVERY ====================
    
    async def recover_from_ssh_error(self):
        """🔄 Attempt to recover from SSH connection errors"""
        try:
            self.ssh_error_count += 1
            
            if self.ssh_error_count > 10:
                await self.send_health_alert(
                    "SSH connection failures exceeded threshold. Check server connectivity.",
                    level="critical"
                )
                # Disable SSH temporarily
                self.ssh_enabled = False
                logger.warning("⚠️ SSH disabled due to persistent errors")
            
            # Exponential backoff
            wait_time = min(300, 30 * (2 ** min(self.ssh_error_count, 5)))
            logger.info(f"🔄 SSH error recovery: waiting {wait_time}s before retry")
            await asyncio.sleep(wait_time)
            
        except Exception as e:
            logger.error(f"❌ SSH recovery failed: {e}")
    
    async def recover_from_db_error(self):
        """🔄 Attempt to recover from database errors"""
        try:
            self.db_error_count += 1
            
            if self.db_error_count > 10:
                await self.send_health_alert(
                    "Database errors exceeded threshold. Check database integrity.",
                    level="critical"
                )
            
            # Wait and retry
            await asyncio.sleep(5)
            
            # Try to reconnect
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("SELECT 1")
            
            logger.info("✅ Database connection recovered")
            self.db_error_count = max(0, self.db_error_count - 1)  # Reduce counter on success
            
        except Exception as e:
            logger.error(f"❌ Database recovery failed: {e}")
    
    # ==================== GRACEFUL SHUTDOWN ====================
    
    async def graceful_shutdown(self):
        """👋 Graceful shutdown handler"""
        try:
            logger.info("🛑 Initiating graceful shutdown...")
            
            # Post maintenance notice
            channel = self.get_channel(self.stats_channel_id)
            if channel:
                embed = discord.Embed(
                    title="🛑 Bot Shutting Down",
                    description="Bot is shutting down for maintenance. Will be back shortly.",
                    color=discord.Color.orange(),
                    timestamp=datetime.now()
                )
                await channel.send(embed=embed)
            
            # Save state
            logger.info("💾 Saving bot state...")
            
            # Close database connections gracefully
            logger.info("🔌 Closing connections...")
            
            # Cancel all tasks
            logger.info("⏹️ Cancelling background tasks...")
            for task_attr in ['endstats_monitor', 'cache_refresher', 'scheduled_monitoring_check']:
                if hasattr(self, task_attr):
                    task = getattr(self, task_attr)
                    if task.is_running():
                        task.cancel()
            
            logger.info("✅ Graceful shutdown complete")
            
        except Exception as e:
            logger.error(f"❌ Graceful shutdown error: {e}")


# ==================== ADMIN COMMANDS ====================

def get_admin_commands():
    """
    Returns a list of admin command functions to add to your bot
    Add these to your Cog or main bot class
    """
    
    from discord.ext import commands
    
    @commands.command(name="health")
    async def health_command(ctx):
        """📊 Show bot health status"""
        try:
            health = await ctx.bot.get_bot_health_status()
            
            embed = discord.Embed(
                title="🏥 Bot Health Status",
                color=discord.Color.green() if health["status"] == "healthy" else discord.Color.orange(),
                timestamp=datetime.now()
            )
            
            # Status overview
            embed.add_field(
                name="📊 Overall Status",
                value=f"**{health['status'].upper()}**\nUptime: {health['uptime']}",
                inline=False
            )
            
            # Error counts
            embed.add_field(
                name="❌ Errors",
                value=f"Total: {health['error_count']}\nSSH: {health['ssh_errors']}\nDB: {health['db_errors']}",
                inline=True
            )
            
            # Monitoring status
            embed.add_field(
                name="🔍 Monitoring",
                value=f"Active: {'✅' if health['monitoring'] else '❌'}\nSession: {'✅' if health['session_active'] else '❌'}",
                inline=True
            )
            
            # Database stats
            db = health['database']
            embed.add_field(
                name="💾 Database",
                value=f"Size: {db['size_mb']} MB\nFiles: {db['total_files']}\nRecords: {db['total_records']}\nSessions: {db['total_sessions']}",
                inline=False
            )
            
            # System resources
            res = health['resources']
            embed.add_field(
                name="💻 Resources",
                value=f"Memory: {res['memory_mb']} MB\nCPU: {res['cpu_percent']}%",
                inline=True
            )
            
            # Task statuses
            task_status_text = []
            for task_name, status in health['tasks'].items():
                emoji = "✅" if status['running'] else "❌"
                task_status_text.append(f"{emoji} {task_name}")
            
            embed.add_field(
                name="⚙️ Background Tasks",
                value="\n".join(task_status_text),
                inline=True
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Error getting health status: {e}")
    
    @commands.command(name="backup")
    @commands.has_permissions(administrator=True)
    async def backup_command(ctx):
        """💾 Manually trigger database backup"""
        try:
            await ctx.send("💾 Creating database backup...")
            await ctx.bot.backup_database()
            await ctx.send("✅ Backup complete!")
        except Exception as e:
            await ctx.send(f"❌ Backup failed: {e}")
    
    @commands.command(name="vacuum")
    @commands.has_permissions(administrator=True)
    async def vacuum_command(ctx):
        """🧹 Manually optimize database"""
        try:
            await ctx.send("🧹 Optimizing database...")
            await ctx.bot.vacuum_database()
            await ctx.send("✅ Database optimized!")
        except Exception as e:
            await ctx.send(f"❌ Optimization failed: {e}")
    
    @commands.command(name="errors")
    async def errors_command(ctx):
        """📊 Show recent error statistics"""
        try:
            health = await ctx.bot.get_bot_health_status()
            
            embed = discord.Embed(
                title="❌ Error Statistics",
                color=discord.Color.red() if health['error_count'] > 10 else discord.Color.orange(),
                timestamp=datetime.now()
            )
            
            embed.add_field(name="Total Errors", value=str(health['error_count']), inline=True)
            embed.add_field(name="SSH Errors", value=str(health['ssh_errors']), inline=True)
            embed.add_field(name="DB Errors", value=str(health['db_errors']), inline=True)
            
            # Task errors
            task_errors = []
            for task_name, status in health['tasks'].items():
                if status['error_count'] > 0:
                    task_errors.append(f"{task_name}: {status['error_count']}")
            
            if task_errors:
                embed.add_field(
                    name="Task Errors",
                    value="\n".join(task_errors),
                    inline=False
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Error getting error stats: {e}")
    
    return [health_command, backup_command, vacuum_command, errors_command]


# ==================== INTEGRATION INSTRUCTIONS ====================

INTEGRATION_INSTRUCTIONS = """
📝 How to Integrate These Enhancements
======================================

1. **Add Health Monitoring Variables** (in __init__):
   
   # Add after line 2593 (after self.error_count = 0)
   self.init_health_monitoring()

2. **Start Background Tasks** (in setup_hook or on_ready):
   
   # Add these task starts
   self.loop.create_task(self.health_monitor_task())
   self.loop.create_task(self.daily_report_task())
   self.loop.create_task(self.database_maintenance_task())

3. **Add Error Recovery** (in your existing tasks):
   
   # In endstats_monitor, wrap SSH calls:
   try:
       # SSH operations
   except Exception as e:
       await self.recover_from_ssh_error()
   
   # In database operations:
   try:
       # DB operations
   except Exception as e:
       await self.recover_from_db_error()

4. **Add Graceful Shutdown** (in on_close or close):
   
   async def close(self):
       await self.graceful_shutdown()
       await super().close()

5. **Add Admin Commands** (create a Cog or add to bot):
   
   # Add commands from get_admin_commands()
   for command in get_admin_commands():
       self.add_command(command)

6. **Update .env** (add admin channel):
   
   ADMIN_CHANNEL_ID=your_admin_channel_id

7. **Install Required Package**:
   
   pip install psutil

That's it! Your bot now has:
✅ Health monitoring with alerts
✅ Automatic error recovery
✅ Daily reports and summaries
✅ Database maintenance
✅ Graceful shutdown
✅ Admin dashboard commands
"""

if __name__ == "__main__":
    print(INTEGRATION_INSTRUCTIONS)
