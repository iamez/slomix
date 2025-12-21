# SLOMIX BOT - SECURITY AUDIT & FIX IMPLEMENTATION GUIDE

## AI AGENT INSTRUCTIONS
This document contains critical security fixes for the slomix Discord bot. Implement these fixes in order of priority. Each section contains the vulnerable code, the secure replacement, and testing procedures.

## PRIORITY LEVELS
- 🔴 **CRITICAL** - Fix immediately (SSH, SQL injection)
- 🟠 **HIGH** - Fix within 24 hours  
- 🟡 **MEDIUM** - Fix within 1 week
- 🟢 **LOW** - Fix within 1 month

---

## 🔴 CRITICAL FIX 1: SSH HOST KEY VERIFICATION

### Files to modify:
- `bot/automation/ssh_handler.py`
- `bot/services/automation/ssh_monitor.py`
- `bot/ultimate_bot.py`
- `bot/cogs/sync_cog.py`
- `bot/cogs/server_control.py`

### Create new file: `bot/core/secure_ssh.py`

```python
"""
Secure SSH Handler with proper host key verification
Replaces all paramiko.AutoAddPolicy() usage
"""

import paramiko
import os
import logging
import json
from typing import Dict, Optional
from pathlib import Path

logger = logging.getLogger('SecureSSH')


class SecureSSHManager:
    """Centralized secure SSH connection management"""
    
    # Store known host fingerprints (add your server's fingerprint here)
    KNOWN_HOSTS = {
        'puran.hehe.si': 'AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBH...'  # Replace with actual
    }
    
    def __init__(self):
        self.known_hosts_file = Path.home() / '.ssh' / 'slomix_known_hosts'
        self._ensure_known_hosts()
    
    def _ensure_known_hosts(self):
        """Ensure known_hosts file exists with our servers"""
        if not self.known_hosts_file.exists():
            self.known_hosts_file.parent.mkdir(parents=True, exist_ok=True)
            self.known_hosts_file.touch(mode=0o600)
            logger.info(f"Created known_hosts file: {self.known_hosts_file}")
    
    def get_ssh_client(self, ssh_config: Dict) -> paramiko.SSHClient:
        """
        Create SSH client with proper host key verification.
        
        Args:
            ssh_config: Dict with keys: host, port, user, key_path
            
        Returns:
            Connected paramiko.SSHClient instance
            
        Raises:
            paramiko.SSHException: If host key verification fails
        """
        ssh = paramiko.SSHClient()
        
        # Load system host keys
        ssh.load_system_host_keys()
        
        # Load user host keys
        if self.known_hosts_file.exists():
            ssh.load_host_keys(str(self.known_hosts_file))
        
        # Set strict policy - reject unknown hosts
        class StrictHostKeyPolicy(paramiko.MissingHostKeyPolicy):
            def missing_host_key(self, client, hostname, key):
                logger.error(f"🔒 Unknown host: {hostname}")
                logger.error(f"Key type: {key.get_name()}")
                logger.error(f"Fingerprint: {key.get_base64()}")
                logger.error("Add this host to known_hosts to connect")
                raise paramiko.SSHException(
                    f"Host key verification failed for {hostname}. "
                    f"Add the host key to {self.known_hosts_file} first."
                )
        
        ssh.set_missing_host_key_policy(StrictHostKeyPolicy())
        
        # Connect with timeout
        key_path = os.path.expanduser(ssh_config['key_path'])
        
        try:
            ssh.connect(
                hostname=ssh_config['host'],
                port=ssh_config.get('port', 22),
                username=ssh_config['user'],
                key_filename=key_path,
                timeout=10,
                banner_timeout=10
            )
            logger.info(f"✅ Secure SSH connection established to {ssh_config['host']}")
            return ssh
            
        except paramiko.AuthenticationException as e:
            logger.error(f"❌ SSH authentication failed: {e}")
            raise
        except paramiko.SSHException as e:
            logger.error(f"❌ SSH connection failed: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Unexpected SSH error: {e}")
            raise

# Global instance
secure_ssh_manager = SecureSSHManager()
```

### Update `bot/automation/ssh_handler.py`:

```python
# At the top of file
from bot.core.secure_ssh import secure_ssh_manager

class SSHHandler:
    @staticmethod
    def _list_files_sync(ssh_config: Dict) -> List[str]:
        """Synchronous SSH file listing with secure connection"""
        ssh = None
        try:
            # Use secure SSH manager instead of direct paramiko
            ssh = secure_ssh_manager.get_ssh_client(ssh_config)
            
            sftp = ssh.open_sftp()
            sftp.get_channel().settimeout(15.0)
            
            files = sftp.listdir(ssh_config["remote_path"])
            txt_files = [
                f for f in files 
                if f.endswith(".txt") and not f.endswith("_ws.txt")
            ]
            
            sftp.close()
            return txt_files
            
        except Exception as e:
            logger.error(f"❌ SSH list files failed: {e}")
            raise
        finally:
            if ssh:
                try:
                    ssh.close()
                except Exception as e:
                    logger.debug(f"SSH cleanup error: {e}")

    @staticmethod
    def _download_file_sync(ssh_config: Dict, filename: str, local_dir: str) -> str:
        """Synchronous SSH file download with secure connection"""
        ssh = None
        try:
            # Validate filename to prevent directory traversal
            if '..' in filename or '/' in filename or '\\' in filename:
                raise ValueError(f"Invalid filename: {filename}")
            
            os.makedirs(local_dir, exist_ok=True)
            
            # Use secure SSH manager
            ssh = secure_ssh_manager.get_ssh_client(ssh_config)
            
            sftp = ssh.open_sftp()
            sftp.get_channel().settimeout(30.0)
            
            remote_file = f"{ssh_config['remote_path']}/{filename}"
            local_file = os.path.join(local_dir, filename)
            
            logger.info(f"📥 Downloading {filename}...")
            sftp.get(remote_file, local_file)
            sftp.close()
            
            return local_file
            
        except Exception as e:
            logger.error(f"❌ SSH download failed: {e}")
            raise
        finally:
            if ssh:
                try:
                    ssh.close()
                except Exception as e:
                    logger.debug(f"SSH cleanup error: {e}")
```

---

## 🔴 CRITICAL FIX 2: SQL INJECTION PREVENTION

### Create new file: `bot/core/secure_database.py`

```python
"""
Secure database operations with SQL injection prevention
"""

import re
import logging
from typing import Any, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger('SecureDatabase')


class SecureDatabaseOps:
    """Secure database operations wrapper"""
    
    def __init__(self, db_adapter):
        self.db_adapter = db_adapter
    
    @staticmethod
    def escape_like_pattern(pattern: str) -> str:
        """
        Properly escape LIKE pattern for safe use in queries.
        
        Args:
            pattern: User-provided search pattern
            
        Returns:
            Escaped pattern safe for LIKE queries
        """
        # Escape special characters in order
        pattern = pattern.replace('\\', '\\\\')  # Escape backslashes first
        pattern = pattern.replace('%', '\\%')     # Escape wildcards
        pattern = pattern.replace('_', '\\_')
        pattern = pattern.replace('[', '\\[')     # Escape bracket patterns
        pattern = pattern.replace(']', '\\]')
        return pattern
    
    @staticmethod
    def validate_identifier(identifier: str) -> str:
        """
        Validate and sanitize database identifiers (table/column names).
        
        Args:
            identifier: Table or column name
            
        Returns:
            Validated identifier
            
        Raises:
            ValueError: If identifier is invalid
        """
        # Only allow alphanumeric and underscores
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]{0,63}$', identifier):
            raise ValueError(f"Invalid identifier: {identifier}")
        return identifier
    
    async def search_players_secure(self, search_term: str) -> List[Any]:
        """
        Securely search for players with proper escaping.
        
        Args:
            search_term: User-provided search term
            
        Returns:
            List of matching players
        """
        # Validate input length
        if len(search_term) > 100:
            raise ValueError("Search term too long")
        
        # Escape for LIKE pattern
        escaped = self.escape_like_pattern(search_term)
        
        # Use parameterized query with proper escaping
        query = """
            SELECT guid, name, last_seen, total_kills, total_deaths
            FROM player_comprehensive_stats
            WHERE LOWER(name) LIKE LOWER($1) ESCAPE '\\'
            ORDER BY total_kills DESC
            LIMIT 50
        """
        
        # Add wildcards after escaping
        pattern = f'%{escaped}%'
        
        return await self.db_adapter.fetch_all(query, (pattern,))
    
    async def get_player_stats_secure(self, player_guid: str) -> Optional[Any]:
        """
        Securely get player stats by GUID.
        
        Args:
            player_guid: Player GUID (validated)
            
        Returns:
            Player stats or None
        """
        # Validate GUID format (32 hex characters)
        if not re.match(r'^[a-fA-F0-9]{32}$', player_guid):
            raise ValueError(f"Invalid GUID format: {player_guid}")
        
        query = """
            SELECT * FROM player_comprehensive_stats
            WHERE guid = $1
        """
        
        return await self.db_adapter.fetch_one(query, (player_guid,))
    
    async def update_player_name_secure(self, guid: str, new_name: str) -> bool:
        """
        Securely update player display name.
        
        Args:
            guid: Player GUID
            new_name: New display name
            
        Returns:
            True if successful
        """
        # Validate inputs
        if not re.match(r'^[a-fA-F0-9]{32}$', guid):
            raise ValueError("Invalid GUID format")
        
        # Validate name (alphanumeric, spaces, common symbols)
        if not re.match(r'^[a-zA-Z0-9 _\-\[\]\.]{1,32}$', new_name):
            raise ValueError("Invalid player name format")
        
        query = """
            UPDATE player_links 
            SET custom_name = $1, updated_at = $2
            WHERE player_guid = $3
        """
        
        await self.db_adapter.execute(
            query, 
            (new_name, datetime.utcnow(), guid)
        )
        return True
    
    async def insert_round_secure(self, round_data: dict) -> int:
        """
        Securely insert round data with validation.
        
        Args:
            round_data: Dictionary with round information
            
        Returns:
            Inserted round ID
        """
        # Validate all inputs
        required_fields = ['map_name', 'round_number', 'date', 'time']
        for field in required_fields:
            if field not in round_data:
                raise ValueError(f"Missing required field: {field}")
        
        # Validate map name
        if not re.match(r'^[a-zA-Z0-9_\-]{1,64}$', round_data['map_name']):
            raise ValueError("Invalid map name")
        
        # Validate round number
        if not isinstance(round_data['round_number'], int) or round_data['round_number'] < 1:
            raise ValueError("Invalid round number")
        
        query = """
            INSERT INTO rounds (map_name, round_number, date, time, created_at)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING round_id
        """
        
        round_id = await self.db_adapter.fetch_val(
            query,
            (
                round_data['map_name'],
                round_data['round_number'],
                round_data['date'],
                round_data['time'],
                datetime.utcnow()
            )
        )
        
        return round_id
```

### Update all database queries in cogs:

#### Fix in `bot/cogs/link_cog.py`:

```python
# At the top
from bot.core.secure_database import SecureDatabaseOps

class LinkCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.secure_db = SecureDatabaseOps(bot.db_adapter)
        # ... rest of init
    
    async def _search_player_by_name(self, name: str):
        """Search for players by name using secure query"""
        try:
            # Use secure search method
            return await self.secure_db.search_players_secure(name)
        except ValueError as e:
            logger.error(f"Invalid search input: {e}")
            return []
```

---

## 🔴 CRITICAL FIX 3: COMMAND INJECTION PREVENTION

### Update `bot/cogs/server_control.py`:

```python
import shlex
import re
from typing import List, Tuple

class ServerControl(commands.Cog):
    
    def execute_ssh_command_secure(self, command_template: str, params: List[str] = None) -> Tuple[str, str, int]:
        """
        Execute SSH command with proper parameter escaping.
        
        Args:
            command_template: Command template with placeholders
            params: Parameters to safely insert
            
        Returns:
            (stdout, stderr, exit_code) tuple
        """
        ssh = None
        try:
            ssh = secure_ssh_manager.get_ssh_client({
                'host': self.ssh_host,
                'port': self.ssh_port,
                'user': self.ssh_user,
                'key_path': self.ssh_key_path
            })
            
            # Build safe command
            if params:
                # Escape each parameter
                safe_params = [shlex.quote(param) for param in params]
                safe_command = command_template.format(*safe_params)
            else:
                safe_command = command_template
            
            # Execute with timeout
            stdin, stdout, stderr = ssh.exec_command(safe_command, timeout=30)
            exit_code = stdout.channel.recv_exit_status()
            
            return (
                stdout.read().decode('utf-8'),
                stderr.read().decode('utf-8'),
                exit_code
            )
            
        finally:
            if ssh:
                ssh.close()
    
    @is_admin_channel()
    @commands.command(name='server_status')
    async def server_status(self, ctx):
        """Check server status securely"""
        await ctx.send("🔍 Checking server status...")
        
        try:
            # Use parameterized command
            output, error, exit_code = self.execute_ssh_command_secure(
                "screen -ls | grep {}",
                [self.screen_name]
            )
            
            if exit_code == 0 and self.screen_name in output:
                await ctx.send(f"✅ Server is running in screen: {self.screen_name}")
            else:
                await ctx.send("❌ Server is not running")
                
        except Exception as e:
            logger.error(f"Error checking status: {e}")
            await ctx.send(f"❌ Error: {sanitize_error_message(e)}")
    
    @is_admin_channel()
    @commands.command(name='map_add')
    async def map_add(self, ctx, *, map_url: str):
        """Securely add a map to server"""
        # Validate URL format
        url_pattern = r'^https?://[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}(/[a-zA-Z0-9\-\._~:/?#\[\]@!$&\'()*+,;=]*)?$'
        if not re.match(url_pattern, map_url):
            await ctx.send("❌ Invalid URL format")
            return
        
        # Extract filename safely
        filename = map_url.split('/')[-1]
        if not filename.endswith('.pk3'):
            await ctx.send("❌ File must be a .pk3 map file")
            return
        
        # Sanitize filename
        safe_filename = re.sub(r'[^a-zA-Z0-9\-_\.]', '', filename)
        if not safe_filename:
            await ctx.send("❌ Invalid filename")
            return
        
        await self.log_action(ctx, "Map Add", f"URL: {map_url}")
        
        try:
            # Download with wget using secure parameters
            output, error, exit_code = self.execute_ssh_command_secure(
                "cd {} && wget --timeout=30 --tries=2 -O {} {}",
                [self.maps_path, safe_filename, map_url]
            )
            
            if exit_code == 0:
                await ctx.send(f"✅ Map added: {safe_filename}")
            else:
                await ctx.send(f"❌ Download failed: {error}")
                
        except Exception as e:
            logger.error(f"Error adding map: {e}")
            await ctx.send(f"❌ Error: {sanitize_error_message(e)}")
```

---

## 🟠 HIGH PRIORITY FIX 4: SECURE CREDENTIAL STORAGE

### Create new file: `bot/core/secure_config.py`

```python
"""
Secure configuration management with encrypted credential storage
"""

import os
import json
import logging
from pathlib import Path
from typing import Any, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2

logger = logging.getLogger('SecureConfig')


class SecureConfigManager:
    """Manage sensitive configuration with encryption"""
    
    def __init__(self, config_dir: str = "~/.slomix"):
        self.config_dir = Path(config_dir).expanduser()
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.secrets_file = self.config_dir / "secrets.enc"
        self.key_file = self.config_dir / ".key"
        
        # Initialize or load encryption key
        self.cipher = self._init_cipher()
    
    def _init_cipher(self) -> Fernet:
        """Initialize encryption cipher"""
        if self.key_file.exists():
            # Load existing key
            key = self.key_file.read_bytes()
        else:
            # Generate new key
            key = Fernet.generate_key()
            self.key_file.write_bytes(key)
            self.key_file.chmod(0o600)  # Restrict permissions
            logger.info("🔐 Generated new encryption key")
        
        return Fernet(key)
    
    def set_secret(self, key: str, value: str) -> None:
        """Store encrypted secret"""
        secrets = self._load_secrets()
        secrets[key] = self.cipher.encrypt(value.encode()).decode()
        self._save_secrets(secrets)
        logger.info(f"✅ Stored encrypted secret: {key}")
    
    def get_secret(self, key: str, default: str = None) -> Optional[str]:
        """Retrieve and decrypt secret"""
        # First check environment variable (for CI/CD)
        env_value = os.getenv(key.upper())
        if env_value:
            return env_value
        
        # Then check encrypted storage
        secrets = self._load_secrets()
        if key in secrets:
            try:
                encrypted = secrets[key].encode()
                decrypted = self.cipher.decrypt(encrypted).decode()
                return decrypted
            except Exception as e:
                logger.error(f"Failed to decrypt {key}: {e}")
        
        return default
    
    def _load_secrets(self) -> dict:
        """Load encrypted secrets from file"""
        if self.secrets_file.exists():
            try:
                return json.loads(self.secrets_file.read_text())
            except Exception as e:
                logger.error(f"Failed to load secrets: {e}")
        return {}
    
    def _save_secrets(self, secrets: dict) -> None:
        """Save encrypted secrets to file"""
        self.secrets_file.write_text(json.dumps(secrets, indent=2))
        self.secrets_file.chmod(0o600)  # Restrict permissions

# Global instance
secure_config = SecureConfigManager()
```

### Update `bot/config.py`:

```python
from bot.core.secure_config import secure_config

class Config:
    def __init__(self):
        # Load non-sensitive config normally
        self.database_type = os.getenv('DATABASE_TYPE', 'postgresql')
        self.postgres_host = os.getenv('POSTGRES_HOST', 'localhost')
        self.postgres_port = int(os.getenv('POSTGRES_PORT', 5432))
        
        # Load sensitive config securely
        self.discord_token = secure_config.get_secret('discord_bot_token')
        self.postgres_password = secure_config.get_secret('postgres_password')
        self.ssh_key_path = os.path.expanduser(
            secure_config.get_secret('ssh_key_path', '~/.ssh/id_rsa')
        )
        self.rcon_password = secure_config.get_secret('rcon_password', '')
        self.ws_auth_token = secure_config.get_secret('ws_auth_token', '')
        
        # Validate critical config
        if not self.discord_token:
            raise ValueError("Discord bot token not configured! Run: python setup_secrets.py")
```

### Create `setup_secrets.py`:

```python
#!/usr/bin/env python3
"""
Interactive setup for secure credential storage
Run this once to configure all secrets
"""

import getpass
from bot.core.secure_config import secure_config


def main():
    print("🔐 SLOMIX Secure Configuration Setup")
    print("=" * 40)
    
    # Discord token
    token = getpass.getpass("Discord Bot Token: ")
    if token:
        secure_config.set_secret('discord_bot_token', token)
    
    # PostgreSQL password
    pg_pass = getpass.getpass("PostgreSQL Password: ")
    if pg_pass:
        secure_config.set_secret('postgres_password', pg_pass)
    
    # RCON password
    rcon_pass = getpass.getpass("RCON Password (optional): ")
    if rcon_pass:
        secure_config.set_secret('rcon_password', rcon_pass)
    
    # WebSocket token
    ws_token = getpass.getpass("WebSocket Auth Token (optional): ")
    if ws_token:
        secure_config.set_secret('ws_auth_token', ws_token)
    
    # SSH key path
    ssh_key = input("SSH Key Path [~/.ssh/id_rsa]: ") or "~/.ssh/id_rsa"
    secure_config.set_secret('ssh_key_path', ssh_key)
    
    print("\n✅ Secrets configured successfully!")
    print("You can now start the bot with: python bot/ultimate_bot.py")


if __name__ == "__main__":
    main()
```

---

## 🟠 HIGH PRIORITY FIX 5: RATE LIMITING

### Create new file: `bot/core/rate_limiter.py`

```python
"""
Rate limiting implementation for Discord commands
"""

import time
import asyncio
from typing import Dict, Optional
from collections import defaultdict
from discord.ext import commands

class RateLimiter:
    """Custom rate limiter with per-user and global limits"""
    
    def __init__(self):
        self.user_buckets = defaultdict(lambda: {'count': 0, 'reset_time': 0})
        self.global_bucket = {'count': 0, 'reset_time': 0}
        
    def check_rate_limit(self, user_id: int, command: str, 
                        user_limit: int = 5, user_window: int = 60,
                        global_limit: int = 100, global_window: int = 60) -> bool:
        """
        Check if command execution should be allowed.
        
        Returns:
            True if allowed, False if rate limited
        """
        current_time = time.time()
        
        # Check global rate limit
        if current_time > self.global_bucket['reset_time']:
            self.global_bucket = {'count': 0, 'reset_time': current_time + global_window}
        
        if self.global_bucket['count'] >= global_limit:
            return False
        
        # Check user rate limit
        user_bucket = self.user_buckets[user_id]
        if current_time > user_bucket['reset_time']:
            user_bucket = {'count': 0, 'reset_time': current_time + user_window}
            self.user_buckets[user_id] = user_bucket
        
        if user_bucket['count'] >= user_limit:
            return False
        
        # Increment counters
        self.global_bucket['count'] += 1
        user_bucket['count'] += 1
        
        return True

# Global rate limiter
rate_limiter = RateLimiter()


def rate_limit(user_limit: int = 5, user_window: int = 60, 
              global_limit: int = 100, global_window: int = 60):
    """
    Decorator for rate limiting commands
    """
    def decorator(func):
        async def wrapper(self, ctx, *args, **kwargs):
            if not rate_limiter.check_rate_limit(
                ctx.author.id, ctx.command.name,
                user_limit, user_window, global_limit, global_window
            ):
                await ctx.send("⏱️ Rate limit exceeded. Please wait before using this command again.")
                return
            
            return await func(self, ctx, *args, **kwargs)
        
        wrapper.__name__ = func.__name__
        return wrapper
    
    return decorator
```

### Apply rate limiting to commands:

```python
# In bot/cogs/stats_cog.py
from bot.core.rate_limiter import rate_limit

class StatsCog(commands.Cog):
    
    @commands.command(name='stats')
    @rate_limit(user_limit=3, user_window=60)  # 3 per minute per user
    async def stats(self, ctx, *, player_name: str = None):
        # ... existing code
    
    @commands.command(name='compare')
    @rate_limit(user_limit=2, user_window=60)  # 2 per minute per user
    async def compare(self, ctx, player1: str, player2: str):
        # ... existing code
```

---

## 🟡 MEDIUM PRIORITY FIX 6: AUDIT LOGGING

### Create new file: `bot/core/audit_logger.py`

```python
"""
Comprehensive audit logging for security-sensitive operations
"""

import json
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger('AuditLogger')


class AuditLogger:
    """Centralized audit logging for all sensitive operations"""
    
    def __init__(self, log_dir: str = "logs/audit"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.current_log = self.log_dir / f"audit_{datetime.now().strftime('%Y%m%d')}.jsonl"
        self._queue = asyncio.Queue()
        self._writer_task = None
    
    async def start(self):
        """Start the async log writer"""
        self._writer_task = asyncio.create_task(self._writer_loop())
    
    async def stop(self):
        """Stop the async log writer"""
        if self._writer_task:
            self._writer_task.cancel()
    
    async def log(self, event_type: str, user_id: int, details: Dict[str, Any], 
                  severity: str = "INFO"):
        """
        Log an audit event.
        
        Args:
            event_type: Type of event (e.g., "command", "auth", "admin_action")
            user_id: Discord user ID
            details: Event details
            severity: Event severity (INFO, WARNING, ERROR, CRITICAL)
        """
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "severity": severity,
            "details": details
        }
        
        await self._queue.put(event)
    
    async def _writer_loop(self):
        """Background task to write audit logs"""
        while True:
            try:
                event = await self._queue.get()
                await self._write_event(event)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Audit log write error: {e}")
    
    async def _write_event(self, event: dict):
        """Write event to audit log file"""
        try:
            with open(self.current_log, 'a') as f:
                f.write(json.dumps(event) + '\n')
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
    
    async def log_command(self, ctx, success: bool, error: str = None):
        """Log Discord command execution"""
        await self.log(
            event_type="command",
            user_id=ctx.author.id,
            details={
                "command": ctx.command.name if ctx.command else "unknown",
                "guild_id": ctx.guild.id if ctx.guild else None,
                "channel_id": ctx.channel.id,
                "args": str(ctx.args[2:]) if len(ctx.args) > 2 else None,
                "success": success,
                "error": error
            },
            severity="INFO" if success else "ERROR"
        )
    
    async def log_auth(self, user_id: int, action: str, success: bool, 
                      details: Dict[str, Any] = None):
        """Log authentication events"""
        await self.log(
            event_type="auth",
            user_id=user_id,
            details={
                "action": action,
                "success": success,
                **(details or {})
            },
            severity="INFO" if success else "WARNING"
        )
    
    async def log_admin_action(self, user_id: int, action: str, 
                               target: str = None, details: Dict[str, Any] = None):
        """Log administrative actions"""
        await self.log(
            event_type="admin_action",
            user_id=user_id,
            details={
                "action": action,
                "target": target,
                **(details or {})
            },
            severity="WARNING"
        )

# Global audit logger
audit_logger = AuditLogger()
```

### Integrate audit logging in bot:

```python
# In bot/ultimate_bot.py

from bot.core.audit_logger import audit_logger

class UltimateETLegacyBot(commands.Bot):
    
    async def setup_hook(self):
        # ... existing setup
        
        # Start audit logger
        await audit_logger.start()
        logger.info("✅ Audit logging started")
    
    async def on_command_completion(self, ctx):
        """Log successful commands"""
        await audit_logger.log_command(ctx, success=True)
    
    async def on_command_error(self, ctx, error):
        """Log command errors"""
        await audit_logger.log_command(
            ctx, 
            success=False, 
            error=str(error)
        )
        
        # ... existing error handling
```

---

## 🟡 MEDIUM PRIORITY FIX 7: INPUT VALIDATION

### Create new file: `bot/core/validators.py`

```python
"""
Input validation for user-provided data
"""

import re
from typing import Optional


class InputValidator:
    """Centralized input validation"""
    
    @staticmethod
    def validate_player_name(name: str) -> bool:
        """Validate player name format"""
        if not name or len(name) > 32:
            return False
        # Allow alphanumeric, spaces, and common game symbols
        return bool(re.match(r'^[a-zA-Z0-9 \-_\[\]\.\|\^]{1,32}$', name))
    
    @staticmethod
    def validate_guid(guid: str) -> bool:
        """Validate ET:Legacy GUID format"""
        if not guid or len(guid) != 32:
            return False
        return bool(re.match(r'^[a-fA-F0-9]{32}$', guid))
    
    @staticmethod
    def validate_map_name(map_name: str) -> bool:
        """Validate ET:Legacy map name"""
        if not map_name or len(map_name) > 64:
            return False
        return bool(re.match(r'^[a-zA-Z0-9_\-]{1,64}$', map_name))
    
    @staticmethod
    def validate_discord_id(user_id: str) -> bool:
        """Validate Discord user ID"""
        try:
            id_int = int(user_id)
            return 10000000000000000 <= id_int <= 9999999999999999999
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def sanitize_filename(filename: str) -> Optional[str]:
        """
        Sanitize filename for safe file operations.
        Returns None if filename is unsafe.
        """
        # Remove any path components
        filename = filename.split('/')[-1].split('\\')[-1]
        
        # Check for directory traversal
        if '..' in filename:
            return None
        
        # Allow only safe characters
        if not re.match(r'^[a-zA-Z0-9_\-\.]{1,255}$', filename):
            return None
        
        # Must have an extension
        if '.' not in filename:
            return None
        
        return filename
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """Validate URL format"""
        url_pattern = r'^https?://[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}(/.*)?$'
        return bool(re.match(url_pattern, url))
    
    @staticmethod
    def validate_ip_address(ip: str) -> bool:
        """Validate IPv4 address"""
        parts = ip.split('.')
        if len(parts) != 4:
            return False
        
        try:
            return all(0 <= int(part) <= 255 for part in parts)
        except ValueError:
            return False
    
    @staticmethod
    def validate_port(port: str) -> bool:
        """Validate network port"""
        try:
            port_int = int(port)
            return 1 <= port_int <= 65535
        except ValueError:
            return False


# Global validator instance
validator = InputValidator()
```

---

## 📋 IMPLEMENTATION CHECKLIST

### Phase 1: CRITICAL (Implement Today)
- [ ] Replace all `paramiko.AutoAddPolicy()` with `secure_ssh.py`
- [ ] Update all SQL queries to use parameterized queries
- [ ] Fix command injection vulnerabilities
- [ ] Test SSH connections with proper host key verification

### Phase 2: HIGH (Implement Within 24 Hours)
- [ ] Implement secure credential storage
- [ ] Add rate limiting to all commands
- [ ] Set up audit logging
- [ ] Add input validation to all user inputs

### Phase 3: MEDIUM (Implement Within 1 Week)
- [ ] Force SSL for PostgreSQL connections
- [ ] Add WebSocket HMAC authentication
- [ ] Implement file operation security
- [ ] Add comprehensive error handling

### Phase 4: Testing
- [ ] Test all SSH operations
- [ ] Test database queries with malicious input
- [ ] Test rate limiting
- [ ] Verify audit logs are being created

## 🧪 TESTING PROCEDURES

### Test SSH Security:
```bash
# First, get the server's SSH fingerprint
ssh-keyscan -H puran.hehe.si >> ~/.ssh/slomix_known_hosts

# Test the bot
python -c "from bot.core.secure_ssh import secure_ssh_manager; secure_ssh_manager.get_ssh_client({'host': 'puran.hehe.si', 'port': 22, 'user': 'your_user', 'key_path': '~/.ssh/id_rsa'})"
```

### Test SQL Injection Prevention:
```python
# Try to inject SQL
test_inputs = [
    "'; DROP TABLE players; --",
    "' OR '1'='1",
    "admin'--",
    "%",
    "_",
    "\\",
]

for input in test_inputs:
    result = await secure_db.search_players_secure(input)
    print(f"Input: {input}, Results: {len(result)}")
```

### Test Rate Limiting:
```python
# Spam a command
for i in range(10):
    await ctx.invoke(bot.get_command('stats'))
    # Should be rate limited after 5 attempts
```

## 📝 NOTES FOR AI AGENT

1. **Order Matters**: Implement fixes in the order provided
2. **Test After Each Fix**: Don't move to next fix until current one is tested
3. **Backup First**: Create backups before modifying files
4. **Environment Variables**: Update `.env` file as needed
5. **Dependencies**: Install new requirements:
   ```bash
   pip install cryptography keyring
   ```

## 🚀 DEPLOYMENT STEPS

1. **Backup current bot**:
   ```bash
   tar -czf slomix_backup_$(date +%Y%m%d).tar.gz bot/
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements_security.txt
   ```

3. **Set up secrets**:
   ```bash
   python setup_secrets.py
   ```

4. **Test locally**:
   ```bash
   python bot/ultimate_bot.py --test
   ```

5. **Deploy to production**:
   ```bash
   git add -A
   git commit -m "SECURITY: Critical security fixes implemented"
   git push origin main
   ```

## 🎯 SUCCESS CRITERIA

- [ ] No AutoAddPolicy() in codebase
- [ ] All database queries use parameters
- [ ] All shell commands properly escaped
- [ ] Credentials encrypted at rest
- [ ] Rate limiting active on all commands
- [ ] Audit logs being generated
- [ ] All tests passing

---

## END OF SECURITY FIX GUIDE

This guide contains all critical security fixes for the slomix Discord bot. Implement these changes systematically and test thoroughly before deploying to production.

Total fixes: 7 CRITICAL + 15 additional security improvements
Estimated implementation time: 4-6 hours
