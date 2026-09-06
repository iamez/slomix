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
import socket
import time

logger = logging.getLogger("bot.automation.ssh")

SAFE_STATS_FILENAME_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}-\d{6}-[A-Za-z0-9_.+-]+-round-\d+(?:-endstats)?(?:_ws)?(?:_engagements)?\.txt$"
)

SAFE_GAMETIME_FILENAME_PATTERN = re.compile(
    r"^gametime-[A-Za-z0-9_.+-]+-R\d+-\d+\.json$"
)


#: A handshake slower than this is worth a line in the log. Set below the
#: banner ceiling on purpose: raising a timeout without measuring what it hides
#: turns a noisy alarm into a silent degradation, and the slowness itself is a
#: useful signal about the game host.
SLOW_HANDSHAKE_SECONDS = 3.0


def _log_slow_handshake(what: str, started: float) -> None:
    """Record a handshake that took long enough to be worth knowing about."""
    elapsed = time.monotonic() - started
    if elapsed >= SLOW_HANDSHAKE_SECONDS:
        logger.warning(f"⏱️ SSH {what} handshake took {elapsed:.1f}s")


def _describe_ssh_failure(exc: Exception) -> str:
    """Name which failure this is, because paramiko gives two of them one name.

    ⛔⛔ ONE MESSAGE, TWO CAUSES. Both of these surface as
    ``SSHException("Error reading SSH protocol banner")``:

    * the banner did not arrive in time — the server is slow or overloaded;
    * ``OSError: [Errno 9] Bad file descriptor`` — the socket was closed while
      paramiko was reading it, which is a local problem, not a slow server.

    On 2026-09-06 the bot logged **11 of each** inside one 30-minute window and
    reported them identically, so nobody could tell that two different things
    were happening — and the April timeout fix therefore aimed at only one of
    them. A cause that shares a name with another cause cannot be counted,
    graphed, or fixed separately.
    """
    root = exc
    while root.__cause__ is not None or root.__context__ is not None:
        nxt = root.__cause__ or root.__context__
        if nxt is root:
            break
        root = nxt

    if isinstance(root, socket.timeout | TimeoutError):
        return f"{exc} [banner/read timed out — remote slow]"
    if isinstance(root, OSError) and root.errno == 9:
        return f"{exc} [socket closed under the read — local]"
    if isinstance(root, OSError):
        return f"{exc} [{type(root).__name__}: {root}]"
    return str(exc)


class SSHConnectionError(Exception):
    """Raised when SSH operations fail due to connection or transport errors."""

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
    def parse_gamestats_filename(filename: str) -> dict | None:
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
        ssh_config: dict,
        extensions: list[str] | None = None,
        exclude_suffixes: list[str] | None = None,
    ) -> list[str]:
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
            loop = asyncio.get_running_loop()
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

        except TimeoutError:
            logger.error("❌ SSH list files timed out after 30 seconds")
            raise SSHConnectionError("SSH list files timed out after 30 seconds")

        except Exception as e:
            detail = _describe_ssh_failure(e)
            logger.error(f"❌ SSH list files failed: {detail}")
            raise SSHConnectionError(f"SSH list files failed: {detail}") from e

    @staticmethod
    def _list_files_sync(
        ssh_config: dict,
        extensions: list[str] | None,
        exclude_suffixes: list[str] | None,
    ) -> list[str]:
        """Synchronous SSH file listing"""
        import paramiko

        ssh = paramiko.SSHClient()
        configure_ssh_host_key_policy(ssh)

        key_path = os.path.expanduser(ssh_config["key_path"])
        sftp = None

        try:
            # ⛔⛔ THREE SEPARATE TIMEOUTS, AND `timeout` IS NOT THE ONE THAT
            # WAS FAILING. paramiko's `timeout` is the TCP connect budget;
            # reading the server's SSH banner has its own `banner_timeout`
            # (default 15) and authentication a third, `auth_timeout`.
            #
            # 6545797c (2026-04-20) raised `timeout` 10 -> 20 in response to
            # exactly the failure seen on 2026-09-06 — "the SSH auth handshake
            # alone can exceed 10s … observed in prod during EU evening peak".
            # It could not help: the banner read gives up at 15s, which is
            # BELOW the 20 it set. Five months of looking fixed.
            #
            # Measured that day: the banner latency distribution shifted right
            # (2026-09-05: 1492 polls answered within a second, thin tail;
            # 2026-09-06: 875 within a second and a tail out past 13s), and the
            # 15s ceiling clipped it. 45s is above the observed tail with room,
            # and _connect_timing below records what the handshake actually
            # cost so a longer ceiling does not simply hide the slowness.
            handshake_started = time.monotonic()
            ssh.connect(
                hostname=ssh_config["host"],
                port=ssh_config["port"],
                username=ssh_config["user"],
                key_filename=key_path,
                timeout=20,
                banner_timeout=45,
                auth_timeout=45,
            )
            _log_slow_handshake("list", handshake_started)

            sftp = ssh.open_sftp()

            # Set timeout for SFTP operations
            sftp.get_channel().settimeout(20.0)

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
        ssh_config: dict, filename: str, local_dir: str = "local_stats"
    ) -> str | None:
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
            loop = asyncio.get_running_loop()
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
    def _download_file_sync(ssh_config: dict, filename: str, local_dir: str) -> str:
        """Synchronous SSH file download with timeout protection"""
        import paramiko

        ssh = paramiko.SSHClient()
        configure_ssh_host_key_policy(ssh)

        key_path = os.path.expanduser(ssh_config["key_path"])
        sftp = None

        try:
            # Same three-timeout story as the listing path above.
            handshake_started = time.monotonic()
            ssh.connect(
                hostname=ssh_config["host"],
                port=ssh_config["port"],
                username=ssh_config["user"],
                key_filename=key_path,
                timeout=20,
                banner_timeout=45,
                auth_timeout=45,
            )
            _log_slow_handshake("download", handshake_started)

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
