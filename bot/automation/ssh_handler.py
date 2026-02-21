"""
SSH Handler - Remote file operations for ET:Legacy stats automation

Handles:
- Listing .txt files on remote SSH server
- Downloading files via SFTP
- Parsing gamestats filenames

All methods use paramiko for SSH/SFTP operations.
"""

# SECURITY NOTE: SSH host key verification
# This module enforces paramiko.RejectPolicy() and known_hosts validation.

import asyncio
import logging
import os
import posixpath
import re
from typing import Dict, List, Optional

logger = logging.getLogger("bot.automation.ssh")

SAFE_STATS_FILENAME_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}-\d{6}-[A-Za-z0-9_.+-]+-round-\d+(?:-endstats)?(?:_ws)?(?:_engagements)?\.txt$"
)

SAFE_GAMETIME_FILENAME_PATTERN = re.compile(
    r"^gametime-[A-Za-z0-9_.+-]+-R\d+-\d+\.json$"
)


class SSHConnectionError(Exception):
    """Raised when SSH operations fail due to connection or transport errors."""
    pass

# Security: SSH host key verification mode
# Strict verification is always enforced.
SSH_STRICT_HOST_KEY = os.getenv('SSH_STRICT_HOST_KEY', 'true').lower() == 'true'
SSH_ALLOW_INSECURE_HOST_KEY = os.getenv('SSH_ALLOW_INSECURE_HOST_KEY', 'false').lower() == 'true'


def configure_ssh_host_key_policy(ssh_client):
    """
    Configure SSH host key verification policy.

    Uses RejectPolicy only - connects exclusively to hosts in known_hosts.
    Insecure host-key auto-accept mode is intentionally disabled.

    Args:
        ssh_client: paramiko.SSHClient instance to configure
    """
    import paramiko

    if not SSH_STRICT_HOST_KEY:
        logger.warning(
            "SSH_STRICT_HOST_KEY=false requested, but strict host-key verification remains enforced."
        )
    if SSH_ALLOW_INSECURE_HOST_KEY:
        logger.warning(
            "SSH_ALLOW_INSECURE_HOST_KEY=true requested, but insecure mode is disabled."
        )

    ssh_client.set_missing_host_key_policy(paramiko.RejectPolicy())
    known_hosts_path = os.path.expanduser('~/.ssh/known_hosts')
    if os.path.exists(known_hosts_path):
        ssh_client.load_host_keys(known_hosts_path)
        logger.debug("🔒 SSH strict mode: loaded known_hosts")
    else:
        logger.warning(
            "⚠️ ~/.ssh/known_hosts not found. "
            "SSH connections may fail. Run 'ssh-keyscan <host> >> ~/.ssh/known_hosts' "
            "to add your server's host key."
        )


class SSHHandler:
    """SSH operations for remote stats file management"""

    @staticmethod
    def _sanitize_stats_filename(filename: str) -> str:
        """
        Validate incoming filename from webhook/websocket before filesystem use.

        Rejects path separators/traversal and allows only expected stats patterns.
        """
        candidate = str(filename or "").strip()
        if not candidate:
            raise ValueError("Filename is required")

        basename = os.path.basename(candidate)
        if basename != candidate or "/" in candidate or "\\" in candidate:
            raise ValueError("Unsafe filename path")
        if ".." in basename:
            raise ValueError("Path traversal detected in filename")
        if not (SAFE_STATS_FILENAME_PATTERN.match(basename) or SAFE_GAMETIME_FILENAME_PATTERN.match(basename)):
            raise ValueError(f"Unexpected stats filename format: {basename}")

        return basename

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
            # Run in executor to avoid blocking event loop, with 30s timeout
            loop = asyncio.get_event_loop()
            files = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    SSHHandler._list_files_sync,
                    ssh_config,
                    extensions,
                    exclude_suffixes,
                ),
                timeout=30,
            )
            return files

        except asyncio.TimeoutError:
            logger.error("❌ SSH list files timed out after 30 seconds")
            raise SSHConnectionError("SSH list files timed out after 30 seconds")

        except Exception as e:
            logger.error(f"❌ SSH list files failed: {e}")
            raise SSHConnectionError(f"SSH list files failed: {e}") from e

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
            safe_filename = SSHHandler._sanitize_stats_filename(filename)
            # Ensure local directory exists
            os.makedirs(local_dir, exist_ok=True)

            # Run in executor
            loop = asyncio.get_event_loop()
            local_path = await loop.run_in_executor(
                None,
                SSHHandler._download_file_sync,
                ssh_config,
                safe_filename,
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

            # Set timeout for SFTP operations (30 seconds for file transfers)
            sftp.get_channel().settimeout(30.0)

            safe_filename = SSHHandler._sanitize_stats_filename(filename)
            remote_base = str(ssh_config["remote_path"]).rstrip("/")
            remote_file = posixpath.join(remote_base, safe_filename)

            local_base = os.path.abspath(local_dir)
            local_file = os.path.abspath(os.path.join(local_base, safe_filename))
            if not local_file.startswith(local_base + os.sep):
                raise ValueError(f"Unsafe local destination for filename: {safe_filename}")

            logger.info(f"📥 Downloading {safe_filename}...")
            sftp.get(remote_file, local_file)

            return local_file

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
