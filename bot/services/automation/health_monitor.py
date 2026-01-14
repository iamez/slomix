"""
🏥 Health Monitor
=================

Monitors bot health and sends alerts when issues are detected.

Features:
- Tracks uptime, errors, resource usage
- Monitors all automation tasks
- Sends alerts to Discord
- Rate-limited to avoid spam
- Generates health reports
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import discord

logger = logging.getLogger("HealthMonitor")


class HealthMonitor:
    """
    Comprehensive health monitoring system.
    
    Monitors:
    - Bot uptime and availability
    - Error rates and types
    - Resource usage (memory, CPU)
    - Task health (running, errors)
    - Database health
    """
    
    def __init__(self, bot, admin_channel_id: int, metrics_logger, config=None):
        """
        Initialize health monitor.

        Args:
            bot: Discord bot instance
            admin_channel_id: Channel for health alerts
            metrics_logger: MetricsLogger instance
            config: BotConfig instance (optional, uses defaults if not provided)
        """
        self.bot = bot
        self.admin_channel_id = admin_channel_id
        self.metrics = metrics_logger

        # Health state
        self.start_time = datetime.now()
        self.last_check_time: Optional[datetime] = None
        self.is_monitoring = False

        # Alert management
        self.last_alert_time: Optional[datetime] = None
        self.alert_cooldown = config.health_alert_cooldown if config else 300

        # Health thresholds
        self.error_threshold = config.health_error_threshold if config else 10
        self.ssh_error_threshold = config.health_ssh_error_threshold if config else 5
        self.db_error_threshold = config.health_db_error_threshold if config else 5

        logger.info("🏥 Health Monitor initialized")
    
    async def start_monitoring(self, check_interval: int = 300):
        """
        Start health monitoring.
        
        Args:
            check_interval: Seconds between health checks (default: 5 minutes)
        """
        self.is_monitoring = True
        logger.info(f"✅ Health monitoring started (interval: {check_interval}s)")
        
        # Start monitoring loop
        asyncio.create_task(self._monitoring_loop(check_interval))
    
    async def stop_monitoring(self):
        """Stop health monitoring"""
        self.is_monitoring = False
        logger.info("🛑 Health monitoring stopped")
    
    async def _monitoring_loop(self, interval: int):
        """Main health monitoring loop"""
        while self.is_monitoring:
            try:
                await asyncio.sleep(interval)
                await self.perform_health_check()
            except Exception as e:
                logger.error(f"❌ Health monitoring loop error: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait 1 minute on error
    
    async def perform_health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check.
        
        Returns:
            Dictionary with health status
        """
        try:
            health_data = await self._gather_health_data()
            
            # Log to metrics
            await self.metrics.log_health_check(
                status=health_data['status'],
                uptime_seconds=health_data['uptime_seconds'],
                error_count=health_data['error_count'],
                ssh_status=health_data.get('ssh_status', 'unknown'),
                db_size_mb=health_data.get('db_size_mb', 0),
                memory_mb=health_data.get('memory_mb', 0),
                cpu_percent=health_data.get('cpu_percent', 0)
            )
            
            # Check for issues
            issues = self._analyze_health_data(health_data)
            
            # Send alerts if needed
            if issues:
                await self._send_health_alert(issues, health_data)
            
            self.last_check_time = datetime.now()
            logger.debug(f"✅ Health check complete: {health_data['status']}")
            
            return health_data
            
        except Exception as e:
            logger.error(f"❌ Health check failed: {e}", exc_info=True)
            return {'status': 'error', 'error': str(e)}
    
    async def _gather_health_data(self) -> Dict[str, Any]:
        """Gather all health metrics"""
        uptime = datetime.now() - self.start_time
        
        health = {
            'status': 'healthy',
            'uptime': str(uptime).split('.')[0],
            'uptime_seconds': int(uptime.total_seconds()),
            'timestamp': datetime.now().isoformat(),
        }
        
        # Get bot error count
        health['error_count'] = getattr(self.bot, 'error_count', 0)
        health['ssh_errors'] = getattr(self.bot, 'ssh_error_count', 0)
        health['db_errors'] = getattr(self.bot, 'db_error_count', 0)
        
        # Get monitoring status
        health['monitoring_active'] = getattr(self.bot, 'monitoring', False)
        health['session_active'] = getattr(self.bot, 'session_active', False)
        
        # Get database size
        if hasattr(self.bot, 'db_path') and self.bot.db_path and os.path.exists(self.bot.db_path):
            db_size = os.path.getsize(self.bot.db_path) / (1024 * 1024)
            health['db_size_mb'] = round(db_size, 2)
        
        # Get resource usage (if psutil available)
        try:
            import psutil
            process = psutil.Process()
            health['memory_mb'] = round(process.memory_info().rss / (1024 * 1024), 2)
            health['cpu_percent'] = process.cpu_percent(interval=1)
        except:
            health['memory_mb'] = 0
            health['cpu_percent'] = 0
        
        # SSH status
        ssh_monitor = getattr(self.bot, 'ssh_monitor', None)
        if ssh_monitor:
            stats = ssh_monitor.get_stats()
            health['ssh_status'] = 'monitoring' if stats['is_monitoring'] else 'stopped'
            health['ssh_files_processed'] = stats['files_processed']
            health['ssh_errors'] = stats['errors_count']
        else:
            health['ssh_status'] = 'disabled'
        
        # Determine overall status
        if health['error_count'] > 20:
            health['status'] = 'critical'
        elif health['error_count'] > self.error_threshold:
            health['status'] = 'degraded'
        
        return health
    
    def _analyze_health_data(self, health: Dict[str, Any]) -> list:
        """Analyze health data and return list of issues"""
        issues = []
        
        # Check error counts
        if health['error_count'] > self.error_threshold:
            issues.append(f"High error count: {health['error_count']}")
        
        if health.get('ssh_errors', 0) > self.ssh_error_threshold:
            issues.append(f"SSH errors: {health['ssh_errors']}")
        
        if health.get('db_errors', 0) > self.db_error_threshold:
            issues.append(f"Database errors: {health['db_errors']}")
        
        # Check SSH status
        if health.get('ssh_status') == 'monitoring' and health.get('ssh_errors', 0) > 10:
            issues.append("SSH monitoring experiencing persistent errors")
        
        # Check memory usage
        if health.get('memory_mb', 0) > 500:
            issues.append(f"High memory usage: {health['memory_mb']} MB")
        
        return issues
    
    async def _send_health_alert(self, issues: list, health_data: Dict[str, Any]):
        """Send health alert to Discord"""
        try:
            # Rate limiting
            if self.last_alert_time:
                elapsed = (datetime.now() - self.last_alert_time).total_seconds()
                if elapsed < self.alert_cooldown:
                    logger.debug(f"Alert suppressed (cooldown: {self.alert_cooldown - elapsed:.0f}s)")
                    return
            
            self.last_alert_time = datetime.now()
            
            # Get channel
            channel = self.bot.get_channel(self.admin_channel_id)
            if not channel:
                logger.error(f"❌ Admin channel {self.admin_channel_id} not found")
                return
            
            # Create embed
            color = discord.Color.red() if health_data['status'] == 'critical' else discord.Color.orange()
            
            embed = discord.Embed(
                title="🚨 Bot Health Alert",
                description="Health issues detected that require attention",
                color=color,
                timestamp=datetime.now()
            )
            
            # Add issues
            embed.add_field(
                name="Issues Detected",
                value="\n".join(f"• {issue}" for issue in issues),
                inline=False
            )
            
            # Add stats
            embed.add_field(
                name="System Status",
                value=f"Uptime: {health_data['uptime']}\nErrors: {health_data['error_count']}\nStatus: {health_data['status'].upper()}",
                inline=False
            )
            
            await channel.send(embed=embed)
            logger.info(f"🚨 Health alert sent: {len(issues)} issues")
            
        except Exception as e:
            logger.error(f"❌ Failed to send health alert: {e}")
    
    async def get_health_report(self) -> discord.Embed:
        """
        Generate health report embed for Discord.
        
        Returns:
            Discord embed with health status
        """
        health = await self._gather_health_data()
        
        # Create embed
        color = {
            'healthy': discord.Color.green(),
            'degraded': discord.Color.orange(),
            'critical': discord.Color.red()
        }.get(health['status'], discord.Color.blue())
        
        embed = discord.Embed(
            title="🏥 Bot Health Status",
            color=color,
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
            value=f"Total: {health['error_count']}\nSSH: {health.get('ssh_errors', 0)}\nDB: {health.get('db_errors', 0)}",
            inline=True
        )
        
        # Monitoring status
        embed.add_field(
            name="🔍 Monitoring",
            value=f"Active: {'✅' if health.get('monitoring_active') else '❌'}\nSession: {'✅' if health.get('session_active') else '❌'}",
            inline=True
        )
        
        # Database
        if 'db_size_mb' in health:
            embed.add_field(
                name="💾 Database",
                value=f"Size: {health['db_size_mb']} MB",
                inline=True
            )
        
        # Resources
        if health.get('memory_mb', 0) > 0:
            embed.add_field(
                name="💻 Resources",
                value=f"Memory: {health['memory_mb']} MB\nCPU: {health['cpu_percent']}%",
                inline=True
            )
        
        # SSH Status
        if 'ssh_status' in health:
            ssh_icon = "✅" if health['ssh_status'] == 'monitoring' else "❌"
            ssh_text = f"{ssh_icon} {health['ssh_status'].title()}"
            if health.get('ssh_files_processed'):
                ssh_text += f"\nFiles: {health['ssh_files_processed']}"
            
            embed.add_field(
                name="🔄 SSH Monitor",
                value=ssh_text,
                inline=True
            )
        
        return embed
