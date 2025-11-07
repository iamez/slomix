"""
🔧 Database Maintenance
=======================

Automated database maintenance tasks.

Features:
- Automatic backups
- Database optimization (VACUUM)
- Old log cleanup
- Database health checks
"""

import asyncio
import logging
import os
import shutil
from datetime import datetime, timedelta
from typing import Optional
# import aiosqlite  # Removed - using database adapter

logger = logging.getLogger("DBMaintenance")


class DatabaseMaintenance:
    """Automated database maintenance system"""
    
    def __init__(self, bot, db_path: str, admin_channel_id: int):
        """
        Initialize database maintenance.
        
        Args:
            bot: Discord bot instance
            db_path: Path to database
            admin_channel_id: Channel for notifications
        """
        self.bot = bot
        self.db_path = db_path
        self.admin_channel_id = admin_channel_id
        
        # Backup settings
        self.backup_dir = "bot/backups"
        self.backup_retention = 7  # Keep last 7 backups
        
        # Log settings
        self.log_dir = "bot/logs"
        self.log_retention_days = 30
        
        # State
        self.last_backup: Optional[datetime] = None
        self.last_vacuum: Optional[datetime] = None
        self.last_cleanup: Optional[datetime] = None
        
        os.makedirs(self.backup_dir, exist_ok=True)
        
        logger.info("🔧 Database Maintenance initialized")
    
    async def backup_database(self) -> bool:
        """Create database backup"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(
                self.backup_dir,
                f"etlegacy_production.db.backup_{timestamp}"
            )
            
            # Create backup
            shutil.copy2(self.db_path, backup_path)
            self.last_backup = datetime.now()
            
            # Cleanup old backups
            await self._cleanup_old_backups()
            
            logger.info(f"✅ Database backed up: {backup_path}")
            
            # Notify Discord
            await self._send_notification(
                "💾 Database Backup Complete",
                f"Backup created: `{os.path.basename(backup_path)}`"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Backup failed: {e}")
            return False
    
    async def vacuum_database(self) -> bool:
        """Optimize database"""
        try:
            await self.bot.db_adapter.execute("VACUUM", ())
            await self.bot.db_adapter.execute("ANALYZE", ())
            
            self.last_vacuum = datetime.now()
            logger.info("✅ Database vacuumed and optimized")
            return True
            
        except Exception as e:
            logger.error(f"❌ Vacuum failed: {e}")
            return False
    
    async def cleanup_old_logs(self) -> int:
        """Remove old log files"""
        try:
            if not os.path.exists(self.log_dir):
                return 0
            
            cutoff = datetime.now() - timedelta(days=self.log_retention_days)
            cleaned = 0
            
            for filename in os.listdir(self.log_dir):
                filepath = os.path.join(self.log_dir, filename)
                if os.path.isfile(filepath):
                    mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                    if mtime < cutoff:
                        os.remove(filepath)
                        cleaned += 1
            
            if cleaned > 0:
                self.last_cleanup = datetime.now()
                logger.info(f"✅ Cleaned {cleaned} old log files")
            
            return cleaned
            
        except Exception as e:
            logger.error(f"❌ Log cleanup failed: {e}")
            return 0
    
    async def _cleanup_old_backups(self):
        """Keep only most recent backups"""
        try:
            backups = sorted(
                [f for f in os.listdir(self.backup_dir) if "backup" in f],
                key=lambda x: os.path.getmtime(os.path.join(self.backup_dir, x)),
                reverse=True
            )
            
            for old_backup in backups[self.backup_retention:]:
                os.remove(os.path.join(self.backup_dir, old_backup))
                logger.debug(f"🗑️ Removed old backup: {old_backup}")
                
        except Exception as e:
            logger.error(f"❌ Backup cleanup failed: {e}")
    
    async def _send_notification(self, title: str, message: str):
        """Send notification to Discord"""
        try:
            import discord
            
            channel = self.bot.get_channel(self.admin_channel_id)
            if channel:
                embed = discord.Embed(
                    title=title,
                    description=message,
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"❌ Failed to send notification: {e}")
    
    def get_stats(self) -> dict:
        """Get maintenance statistics"""
        return {
            'last_backup': self.last_backup.isoformat() if self.last_backup else None,
            'last_vacuum': self.last_vacuum.isoformat() if self.last_vacuum else None,
            'last_cleanup': self.last_cleanup.isoformat() if self.last_cleanup else None,
            'backup_count': len([f for f in os.listdir(self.backup_dir) if "backup" in f]) if os.path.exists(self.backup_dir) else 0,
        }
