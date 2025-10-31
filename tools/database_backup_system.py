#!/usr/bin/env python3
"""
ET:Legacy Database Backup System
Automated backups with multiple storage options
"""
import asyncio
import gzip
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiosqlite
import boto3  # For AWS S3 (optional)
import paramiko  # For remote SFTP backup


class DatabaseBackupManager:
    """Handles automated database backups"""

    def __init__(self, db_path: str = "./etlegacy.db"):
        self.db_path = Path(db_path)
        self.backup_dir = Path("./backups")
        self.backup_dir.mkdir(exist_ok=True)

        # Configuration
        self.backup_interval_hours = 6  # Backup every 6 hours
        self.keep_local_backups = 30  # Keep 30 local backups
        self.compress_backups = True  # Compress with gzip

        # Remote backup settings (optional)
        self.enable_remote_backup = False
        self.remote_host = os.getenv('BACKUP_HOST')
        self.remote_path = os.getenv('BACKUP_PATH', '/backup/etlegacy/')
        self.backup_key_path = os.getenv('BACKUP_KEY_PATH')

        # Cloud backup settings (optional)
        self.enable_s3_backup = False
        self.s3_bucket = os.getenv('BACKUP_S3_BUCKET')
        self.s3_prefix = os.getenv('BACKUP_S3_PREFIX', 'etlegacy-backups/')

        self.logger = logging.getLogger('BackupManager')

    def create_backup_filename(self) -> str:
        """Generate timestamped backup filename"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"etlegacy_backup_{timestamp}.db"
        if self.compress_backups:
            filename += ".gz"
        return filename

    async def create_local_backup(self) -> Optional[Path]:
        """Create a local backup of the database"""
        try:
            if not self.db_path.exists():
                self.logger.error(f"Database file not found: {self.db_path}")
                return None

            backup_filename = self.create_backup_filename()
            backup_path = self.backup_dir / backup_filename

            # Create a consistent backup using SQLite backup API
            async with aiosqlite.connect(self.db_path) as source:
                # Perform a checkpoint to ensure all data is written
                await source.execute("PRAGMA wal_checkpoint(TRUNCATE)")

                # Create backup
                if self.compress_backups:
                    # Backup to temporary file, then compress
                    temp_path = backup_path.with_suffix('')
                    await source.backup(temp_path)

                    # Compress the backup
                    with open(temp_path, 'rb') as f_in:
                        with gzip.open(backup_path, 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)

                    # Remove temporary file
                    temp_path.unlink()
                else:
                    # Direct backup
                    await source.backup(backup_path)

            # Get backup size
            size_mb = backup_path.stat().st_size / (1024 * 1024)
            self.logger.info(f"Created backup: {backup_filename} ({size_mb:.1f} MB)")

            return backup_path

        except Exception as e:
            self.logger.error(f"Failed to create backup: {e}")
            return None

    async def upload_to_remote(self, backup_path: Path) -> bool:
        """Upload backup to remote server via SFTP"""
        if not self.enable_remote_backup or not self.remote_host:
            return False

        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Connect using key
            if self.backup_key_path:
                key = paramiko.RSAKey.from_private_key_file(self.backup_key_path)
                ssh.connect(self.remote_host, username='backup', pkey=key)
            else:
                # Use agent or default keys
                ssh.connect(self.remote_host, username='backup')

            # Upload via SFTP
            sftp = ssh.open_sftp()
            remote_file = f"{self.remote_path}{backup_path.name}"
            sftp.put(str(backup_path), remote_file)
            sftp.close()
            ssh.close()

            self.logger.info(f"Uploaded backup to {self.remote_host}:{remote_file}")
            return True

        except Exception as e:
            self.logger.error(f"Remote backup failed: {e}")
            return False

    async def upload_to_s3(self, backup_path: Path) -> bool:
        """Upload backup to AWS S3"""
        if not self.enable_s3_backup or not self.s3_bucket:
            return False

        try:
            s3 = boto3.client('s3')
            s3_key = f"{self.s3_prefix}{backup_path.name}"

            # Upload with metadata
            extra_args = {
                'Metadata': {
                    'backup-date': datetime.now().isoformat(),
                    'database-size': str(self.db_path.stat().st_size),
                    'backup-type': 'automated',
                }
            }

            s3.upload_file(str(backup_path), self.s3_bucket, s3_key, ExtraArgs=extra_args)
            self.logger.info(f"Uploaded backup to S3: s3://{self.s3_bucket}/{s3_key}")
            return True

        except Exception as e:
            self.logger.error(f"S3 backup failed: {e}")
            return False

    def cleanup_old_backups(self):
        """Remove old local backups"""
        try:
            backup_files = sorted(self.backup_dir.glob("etlegacy_backup_*.db*"))

            if len(backup_files) > self.keep_local_backups:
                files_to_remove = backup_files[: -self.keep_local_backups]
                for file_path in files_to_remove:
                    file_path.unlink()
                    self.logger.info(f"Removed old backup: {file_path.name}")

        except Exception as e:
            self.logger.error(f"Cleanup failed: {e}")

    async def perform_backup(self) -> bool:
        """Perform complete backup process"""
        self.logger.info("Starting database backup...")

        # Create local backup
        backup_path = await self.create_local_backup()
        if not backup_path:
            return False

        # Upload to remote locations
        remote_success = await self.upload_to_remote(backup_path)
        s3_success = await self.upload_to_s3(backup_path)

        # Cleanup old backups
        self.cleanup_old_backups()

        # Report results
        locations = ["Local"]
        if remote_success:
            locations.append("Remote")
        if s3_success:
            locations.append("S3")

        self.logger.info(f"Backup completed successfully: {', '.join(locations)}")
        return True

    async def restore_from_backup(self, backup_filename: str) -> bool:
        """Restore database from backup"""
        try:
            backup_path = self.backup_dir / backup_filename

            if not backup_path.exists():
                self.logger.error(f"Backup file not found: {backup_filename}")
                return False

            # Create backup of current database
            if self.db_path.exists():
                current_backup = self.db_path.with_suffix('.db.restore_backup')
                shutil.copy2(self.db_path, current_backup)
                self.logger.info(f"Current database backed up to: {current_backup}")

            # Restore from backup
            if backup_path.suffix == '.gz':
                # Decompress and restore
                with gzip.open(backup_path, 'rb') as f_in:
                    with open(self.db_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
            else:
                # Direct copy
                shutil.copy2(backup_path, self.db_path)

            self.logger.info(f"Database restored from: {backup_filename}")
            return True

        except Exception as e:
            self.logger.error(f"Restore failed: {e}")
            return False

    def get_backup_info(self) -> dict:
        """Get information about available backups"""
        backup_files = sorted(self.backup_dir.glob("etlegacy_backup_*.db*"))

        backups = []
        for backup_path in backup_files:
            stat = backup_path.stat()
            backups.append(
                {
                    'filename': backup_path.name,
                    'size_mb': stat.st_size / (1024 * 1024),
                    'created': datetime.fromtimestamp(stat.st_mtime),
                    'compressed': backup_path.suffix == '.gz',
                }
            )

        return {
            'total_backups': len(backups),
            'backups': backups,
            'backup_dir': str(self.backup_dir),
            'database_size_mb': (
                self.db_path.stat().st_size / (1024 * 1024) if self.db_path.exists() else 0
            ),
        }


# Integration with your bot


class ETLegacyBotWithBackups:
    """Extended bot with backup functionality"""

    def __init__(self):
        self.backup_manager = DatabaseBackupManager()
        self.backup_task = None

    async def start_backup_scheduler(self):
        """Start automatic backup task"""
        self.backup_task = asyncio.create_task(self._backup_loop())

    async def _backup_loop(self):
        """Background task for periodic backups"""
        while True:
            try:
                await asyncio.sleep(self.backup_manager.backup_interval_hours * 3600)
                await self.backup_manager.perform_backup()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Backup loop error: {e}")

    async def manual_backup(self):
        """Trigger manual backup"""
        return await self.backup_manager.perform_backup()

    def stop_backup_scheduler(self):
        """Stop backup task"""
        if self.backup_task:
            self.backup_task.cancel()


# Configuration example


def setup_backup_config():
    """Example backup configuration"""
    config = """
# Add to your .env file for backup configuration

# Local backup settings
BACKUP_INTERVAL_HOURS=6
KEEP_LOCAL_BACKUPS=30
COMPRESS_BACKUPS=true

# Remote backup (optional)
BACKUP_HOST=your-backup-server.com
BACKUP_PATH=/backup/etlegacy/
BACKUP_KEY_PATH=/path/to/backup/key

# AWS S3 backup (optional)
BACKUP_S3_BUCKET=your-backup-bucket
BACKUP_S3_PREFIX=etlegacy-backups/
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
"""
    print(config)


if __name__ == "__main__":
    # Example usage
    async def test_backup():
        backup_manager = DatabaseBackupManager()

        # Perform backup
        success = await backup_manager.perform_backup()
        print(f"Backup successful: {success}")

        # Show backup info
        info = backup_manager.get_backup_info()
        print(f"Total backups: {info['total_backups']}")
        print(f"Database size: {info['database_size_mb']:.1f} MB")

        for backup in info['backups'][-3:]:  # Show last 3 backups
            print(f"  {backup['filename']} - {backup['size_mb']:.1f} MB - {backup['created']}")

    asyncio.run(test_backup())
