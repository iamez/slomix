"""
SSH Handler - Remote file operations for ET:Legacy stats automation

Handles:
- Listing .txt files on remote SSH server
- Downloading files via SFTP
- Parsing gamestats filenames

All methods use paramiko for SSH/SFTP operations.
"""

# SECURITY NOTE: SSH host key verification
# By default, this module uses paramiko.AutoAddPolicy() which accepts any SSH host key.
# This is acceptable for connecting to our own trusted VPS but can be changed to
# strict mode (RejectPolicy with known_hosts) via SSH_STRICT_HOST_KEY=true env var.
# See: https://docs.paramiko.org/en/stable/api/client.html#paramiko.client.AutoAddPolicy

import asyncio
import logging
import os
import re
from typing import Dict, List, Optional

logger = logging.getLogger("bot.automation.ssh")

# Security: SSH host key verification mode
# Set SSH_STRICT_HOST_KEY=true to require known_hosts verification
SSH_STRICT_HOST_KEY = os.getenv('SSH_STRICT_HOST_KEY', 'true').lower() == 'true'


def configure_ssh_host_key_policy(ssh_client):
    """
    Configure SSH host key verification policy.

    If SSH_STRICT_HOST_KEY=true:
        Uses RejectPolicy - only connects to hosts in ~/.ssh/known_hosts
        More secure but requires manual host key setup

    If SSH_STRICT_HOST_KEY=false (default):
        Uses AutoAddPolicy - accepts any host key on first connect
        Less secure but works out of the box for trusted VPS

    Args:
        ssh_client: paramiko.SSHClient instance to configure
    """
    import paramiko

    if SSH_STRICT_HOST_KEY:
        # Strict mode: only connect to known hosts
        ssh_client.set_missing_host_key_policy(paramiko.RejectPolicy())
        known_hosts_path = os.path.expanduser('~/.ssh/known_hosts')
        if os.path.exists(known_hosts_path):
            ssh_client.load_host_keys(known_hosts_path)
            logger.debug("🔒 SSH strict mode: loaded known_hosts")
        else:
            logger.warning(
                "⚠️ SSH_STRICT_HOST_KEY=true but ~/.ssh/known_hosts not found. "
                "SSH connections may fail. Run 'ssh-keyscan <host> >> ~/.ssh/known_hosts' "
                "to add your server's host key."
            )
    else:
        # Permissive mode: auto-accept host keys (explicit opt-in only)
        logger.warning(
            "SSH host key validation DISABLED (SSH_STRICT_HOST_KEY=false). "
            "Set SSH_STRICT_HOST_KEY=true and populate ~/.ssh/known_hosts for production."
        )
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())


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
    async def list_remote_files(
        ssh_config: Dict,
        extensions: Optional[List[str]] = None,
        exclude_suffixes: Optional[List[str]] = None,
    ) -> List[str]:
        """
        List remote files on SSH server with extension filtering.

        Args:
            ssh_config: Dict with keys: host, port, user, key_path, remote_path
            extensions: Optional list of allowed extensions (defaults to [".txt"])
            exclude_suffixes: Optional list of suffixes to exclude (defaults to ["_ws.txt"])

        Returns:
            List of matching filenames
        """
        try:
            # Run in executor to avoid blocking event loop
            loop = asyncio.get_event_loop()
            files = await loop.run_in_executor(
                None,
                SSHHandler._list_files_sync,
                ssh_config,
                extensions,
                exclude_suffixes,
            )
            return files

        except Exception as e:
            logger.error(f"❌ SSH list files failed: {e}")
            return []

    @staticmethod
    def _list_files_sync(
        ssh_config: Dict,
        extensions: Optional[List[str]],
        exclude_suffixes: Optional[List[str]],
    ) -> List[str]:
        """Synchronous SSH file listing"""
        import paramiko

        ssh = paramiko.SSHClient()
        configure_ssh_host_key_policy(ssh)

        key_path = os.path.expanduser(ssh_config["key_path"])
        sftp = None

        try:
            ssh.connect(
                hostname=ssh_config["host"],
                port=ssh_config["port"],
                username=ssh_config["user"],
                key_filename=key_path,
                timeout=10,
            )

            sftp = ssh.open_sftp()

            # Set timeout for SFTP operations
            sftp.get_channel().settimeout(15.0)

            files = sftp.listdir(ssh_config["remote_path"])

            # Defaults preserve existing behavior
            if extensions is None:
                extensions = [".txt"]
            if exclude_suffixes is None:
                exclude_suffixes = ["_ws.txt"]

            filtered_files = []
            for filename in files:
                if extensions and not any(filename.endswith(ext) for ext in extensions):
                    continue
                if exclude_suffixes and any(filename.endswith(suffix) for suffix in exclude_suffixes):
                    continue
                filtered_files.append(filename)

            return filtered_files

        finally:
            # Ensure connections are closed even on error
            if sftp:
                try:
                    sftp.close()
                except Exception as e:  # nosec B110 - intentional cleanup suppression
                    logger.debug(f"SFTP close ignored: {e}")
            try:
                ssh.close()
            except Exception as e:  # nosec B110 - intentional cleanup suppression
                logger.debug(f"SSH close ignored: {e}")

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
        """Synchronous SSH file download with timeout protection"""
        import paramiko

        ssh = paramiko.SSHClient()
        configure_ssh_host_key_policy(ssh)

        key_path = os.path.expanduser(ssh_config["key_path"])

        try:
            ssh.connect(
                hostname=ssh_config["host"],
                port=ssh_config["port"],
                username=ssh_config["user"],
                key_filename=key_path,
                timeout=10,
            )

            sftp = ssh.open_sftp()

            # Set timeout for SFTP operations (30 seconds for file transfers)
            sftp.get_channel().settimeout(30.0)

            remote_file = f"{ssh_config['remote_path']}/{filename}"
            local_file = os.path.join(local_dir, filename)

            logger.info(f"📥 Downloading {filename}...")
            sftp.get(remote_file, local_file)

            return local_file

        finally:
            # Ensure connections are closed even on error
            try:
                sftp.close()
            except Exception as e:  # nosec B110 - intentional cleanup suppression
                logger.debug(f"SFTP close ignored: {e}")
            try:
                ssh.close()
            except Exception as e:  # nosec B110 - intentional cleanup suppression
                logger.debug(f"SSH close ignored: {e}")
