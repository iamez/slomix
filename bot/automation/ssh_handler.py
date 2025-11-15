"""
SSH Handler - Remote file operations for ET:Legacy stats automation

Handles:
- Listing .txt files on remote SSH server
- Downloading files via SFTP
- Parsing gamestats filenames

All methods use paramiko for SSH/SFTP operations.
"""

import asyncio
import logging
import os
import re
from typing import Dict, List, Optional

logger = logging.getLogger("bot.automation.ssh")


class SSHHandler:
    """SSH operations for remote stats file management"""

    @staticmethod
    def parse_gamestats_filename(filename: str) -> Optional[Dict]:
        """
        Parse gamestats filename to extract metadata

        Format: YYYY-MM-DD-HHMMSS-<map_name>-round-<N>.txt
        Example: 2025-10-02-232818-erdenberg_t2-round-2.txt

        Returns:
            dict with keys: date, time, map_name, round_number, etc.
            None if filename doesn't match expected pattern
        """
        pattern = r"^(\d{4}-\d{2}-\d{2})-(\d{6})-(.+?)-round-(\d+)\.txt$"
        match = re.match(pattern, filename)

        if not match:
            return None

        date, time, map_name, round_num = match.groups()
        round_number = int(round_num)

        return {
            "date": date,
            "time": time,
            "map_name": map_name,
            "round_number": round_number,
            "is_round_1": round_number == 1,
            "is_round_2": round_number == 2,
            "is_map_complete": round_number == 2,
            "full_timestamp": f"{date} {time[:2]}:{time[2:4]}:{time[4:6]}",
            "filename": filename,
        }

    @staticmethod
    async def list_remote_files(ssh_config: Dict) -> List[str]:
        """
        List .txt files on remote SSH server

        Args:
            ssh_config: Dict with keys: host, port, user, key_path, remote_path

        Returns:
            List of .txt filenames (excludes _ws.txt files)
        """
        try:
            # Run in executor to avoid blocking event loop
            loop = asyncio.get_event_loop()
            files = await loop.run_in_executor(
                None, SSHHandler._list_files_sync, ssh_config
            )
            return files

        except Exception as e:
            logger.error(f"❌ SSH list files failed: {e}")
            return []

    @staticmethod
    def _list_files_sync(ssh_config: Dict) -> List[str]:
        """Synchronous SSH file listing"""
        import paramiko

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        key_path = os.path.expanduser(ssh_config["key_path"])

        ssh.connect(
            hostname=ssh_config["host"],
            port=ssh_config["port"],
            username=ssh_config["user"],
            key_filename=key_path,
            timeout=10,
        )

        sftp = ssh.open_sftp()
        files = sftp.listdir(ssh_config["remote_path"])

        # Filter: only .txt files, exclude obsolete _ws.txt files
        txt_files = [
            f
            for f in files
            if f.endswith(".txt") and not f.endswith("_ws.txt")
        ]

        sftp.close()
        ssh.close()

        return txt_files

    @staticmethod
    async def download_file(
        ssh_config: Dict, filename: str, local_dir: str = "local_stats"
    ) -> Optional[str]:
        """
        Download a single file from remote server

        Args:
            ssh_config: Dict with keys: host, port, user, key_path, remote_path
            filename: Remote filename to download
            local_dir: Local directory to save to

        Returns:
            Local file path if successful, None if failed
        """
        try:
            # Ensure local directory exists
            os.makedirs(local_dir, exist_ok=True)

            # Run in executor
            loop = asyncio.get_event_loop()
            local_path = await loop.run_in_executor(
                None,
                SSHHandler._download_file_sync,
                ssh_config,
                filename,
                local_dir,
            )
            return local_path

        except Exception as e:
            logger.error(f"❌ SSH download failed for {filename}: {e}")
            return None

    @staticmethod
    def _download_file_sync(ssh_config: Dict, filename: str, local_dir: str) -> str:
        """Synchronous SSH file download"""
        import paramiko

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        key_path = os.path.expanduser(ssh_config["key_path"])

        ssh.connect(
            hostname=ssh_config["host"],
            port=ssh_config["port"],
            username=ssh_config["user"],
            key_filename=key_path,
            timeout=10,
        )

        sftp = ssh.open_sftp()

        remote_file = f"{ssh_config['remote_path']}/{filename}"
        local_file = os.path.join(local_dir, filename)

        logger.info(f"📥 Downloading {filename}...")
        sftp.get(remote_file, local_file)

        sftp.close()
        ssh.close()

        return local_file
