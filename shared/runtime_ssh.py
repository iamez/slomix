"""Explicit, caller-driven SSH/SFTP ownership without bot configuration."""

import math
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimeSSHConfig:
    """Explicit key-only authentication and phase budgets; no ambient discovery."""

    host: str
    port: int
    user: str
    key_path: Path
    known_hosts: Path
    connect_timeout: float = 10.0
    banner_timeout: float = 10.0
    auth_timeout: float = 10.0
    channel_timeout: float = 10.0
    read_timeout: float = 5.0

    def __post_init__(self):
        """Reject malformed or unbounded settings before opening a connection."""
        for value in (self.host, self.user):
            if not isinstance(value, str) or not value.strip() or value != value.strip() or '\x00' in value:
                raise ValueError('SSH host and user must be explicit nonempty strings')
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ValueError('SSH port must be between 1 and 65535')
        for path in (self.key_path, self.known_hosts):
            if not isinstance(path, Path) or not path.is_absolute():
                raise ValueError('SSH key and known-host paths must be absolute Paths')
        for value in (self.connect_timeout, self.banner_timeout, self.auth_timeout,
                      self.channel_timeout, self.read_timeout):
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 60:
                raise ValueError('SSH phase timeouts must be finite and within (0, 60]')


@contextmanager
def open_runtime_sftp(config: RuntimeSSHConfig):
    """Own one strict-host-verified session, closing SFTP before SSH on exit.

    Blocking API for a dedicated worker, not an event loop. Caller owns every
    remote file handle opened on the yielded session and must close it first.
    No password, SSH agent, key discovery, dotenv or system known-host fallback.
    Phase budgets are NOT an overall deadline: DNS, SFTP subsystem negotiation
    and cleanup may still block. A hard-bound connection worker is a separate
    activation gate; cancelling an executor future would not supply that bound.
    Exceptions propagate; ExitStack still closes SSH if SFTP cleanup raises.
    """
    import paramiko

    with ExitStack() as stack:
        client = paramiko.SSHClient()
        stack.callback(client.close)
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
        client.load_host_keys(str(config.known_hosts))
        client.connect(
            hostname=config.host, port=config.port, username=config.user,
            key_filename=str(config.key_path), allow_agent=False, look_for_keys=False,
            timeout=config.connect_timeout, banner_timeout=config.banner_timeout,
            auth_timeout=config.auth_timeout, channel_timeout=config.channel_timeout,
        )
        sftp = client.open_sftp()
        stack.callback(sftp.close)
        sftp.get_channel().settimeout(config.read_timeout)
        yield sftp
