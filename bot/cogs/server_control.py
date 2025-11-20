#!/usr/bin/env python3
"""
🎮 ET:Legacy Server Control Cog
Remote server management via Discord commands
Uses SSH for file operations and process control
Uses RCON for in-game commands

Customized for Vektor Server:
- Installation: /home/et/etlegacy-v2.83.1-x86_64
- Binary: etlded.x86_64
- Screen: vektor
- Maps: etmain/
"""

import asyncio
import hashlib
import logging
import os
import re
import shlex
import socket
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import discord
import paramiko
from discord.ext import commands

logger = logging.getLogger('ServerControl')


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent directory traversal attacks.

    Removes path separators and keeps only safe characters:
    - Letters (a-z, A-Z)
    - Numbers (0-9)
    - Dots, dashes, underscores (. - _)

    Examples:
        "../../../etc/passwd" -> "etcpasswd"
        "map.pk3" -> "map.pk3"
        "test/../hack.txt" -> "testhack.txt"

    Args:
        filename: User-provided filename

    Returns:
        Sanitized filename safe for file operations

    Raises:
        ValueError: If filename becomes empty after sanitization
    """
    # Get just the filename (no path)
    safe_name = os.path.basename(filename)

    # Remove any characters that aren't alphanumeric, dot, dash, or underscore
    safe_name = re.sub(r'[^a-zA-Z0-9._-]', '', safe_name)

    # Prevent empty filenames
    if not safe_name:
        raise ValueError("Invalid filename provided")

    return safe_name


def sanitize_rcon_input(input_str: str) -> str:
    """
    Sanitize input for RCON commands to prevent command injection.

    Removes dangerous characters that could be used for injection:
    - Semicolons (;) - command separator
    - Newlines (\n, \r) - command separator
    - Null bytes (\x00) - string terminator
    - Backticks (`) - command substitution
    - Dollar signs ($) - variable expansion
    - Pipes (|) - command chaining
    - Ampersands (&) - background execution

    Examples:
        "status; quit" -> "status quit"
        "say `rm -rf /`" -> "say rm -rf /"

    Args:
        input_str: User-provided RCON command or parameter

    Returns:
        Sanitized string safe for RCON execution
    """
    dangerous_chars = [';', '\n', '\r', '\x00', '`', '$', '|', '&']
    sanitized = input_str

    for char in dangerous_chars:
        sanitized = sanitized.replace(char, '')

    return sanitized.strip()


class ETLegacyRCON:
    """RCON client for ET:Legacy server"""
    
    def __init__(self, host: str, port: int, password: str):
        self.host = host
        self.port = port
        self.password = password
        self.socket = None
    
    def connect(self):
        """Connect to RCON server"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(5.0)
    
    def send_command(self, command: str) -> str:
        """Send RCON command and return response"""
        if not self.socket:
            self.connect()
        
        # ET:Legacy RCON protocol: "\xFF\xFF\xFF\xFFrcon PASSWORD COMMAND"
        packet = f"\xFF\xFF\xFF\xFFrcon {self.password} {command}".encode('utf-8')
        
        try:
            self.socket.sendto(packet, (self.host, self.port))
            response, _ = self.socket.recvfrom(4096)
            # Strip RCON header
            decoded = response.decode('utf-8', errors='ignore')
            return decoded.split('\n', 1)[1] if '\n' in decoded else decoded
        except Exception as e:
            return f"Error: {e}"
    
    def close(self):
        """Close RCON connection"""
        if self.socket:
            self.socket.close()
            self.socket = None


class ServerControl(commands.Cog):
    """🎮 ET:Legacy Server Control Commands"""
    
    def __init__(self, bot):
        self.bot = bot
        
        # SSH Configuration
        self.ssh_host = os.getenv('SSH_HOST')
        self.ssh_port = int(os.getenv('SSH_PORT', 22))
        self.ssh_user = os.getenv('SSH_USER')
        self.ssh_key_path = os.path.expanduser(os.getenv('SSH_KEY_PATH', '~/.ssh/id_rsa'))

        # Validate SSH key exists
        if self.ssh_key_path and not os.path.exists(self.ssh_key_path):
            logger.warning(f"⚠️ SSH key not found at: {self.ssh_key_path}")
            logger.warning("SSH features will be disabled until key is configured")
            self.ssh_enabled = False
        else:
            self.ssh_enabled = True
            logger.info(f"✅ SSH key found: {self.ssh_key_path}")

        # Server Configuration - Customized for Vektor
        self.server_install_path = '/home/et/etlegacy-v2.83.1-x86_64'
        self.maps_path = f"{self.server_install_path}/etmain"
        self.screen_name = 'vektor'
        self.server_binary = './etlded.x86_64'
        self.server_config = 'vektor.cfg'
        
        # RCON Configuration
        self.rcon_enabled = os.getenv('RCON_ENABLED', 'false').lower() == 'true'
        self.rcon_host = os.getenv('RCON_HOST', self.ssh_host)
        self.rcon_port = int(os.getenv('RCON_PORT', 27960))
        self.rcon_password = os.getenv('RCON_PASSWORD', '')
        
        # Admin Role - Check for channel instead of role
        self.admin_channel_id = int(os.getenv('ADMIN_CHANNEL_ID', 0)) if os.getenv('ADMIN_CHANNEL_ID') else None
        
        # Local audit logging
        self.audit_log_path = 'logs/server_control_access.log'
        os.makedirs('logs', exist_ok=True)
        
        logger.info(f"✅ ServerControl initialized")
        logger.info(f"   SSH: {self.ssh_user}@{self.ssh_host}:{self.ssh_port}")
        logger.info(f"   Server Path: {self.server_install_path}")
        logger.info(f"   Screen: {self.screen_name}")
        logger.info(f"   RCON: {'Enabled' if self.rcon_enabled else 'Disabled'}")
        logger.info(f"   Admin Channel: {self.admin_channel_id or 'Not configured'}")
    
    def is_admin_channel(ctx):
        """Check if command is in admin channel"""
        cog = ctx.bot.get_cog('ServerControl')
        if not cog or not cog.admin_channel_id:
            return True  # If not configured, allow from anywhere
        return ctx.channel.id == cog.admin_channel_id
    
    async def log_action(self, ctx, action: str, details: str = ""):
        """Log admin action to local file"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {action} by {ctx.author} ({ctx.author.id})"
        if details:
            log_entry += f" - {details}"
        
        logger.info(f"AUDIT: {log_entry}")
        
        # Write to local audit log
        try:
            with open(self.audit_log_path, 'a', encoding='utf-8') as f:
                f.write(log_entry + '\n')
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
    
    def get_ssh_client(self) -> paramiko.SSHClient:
        """Create and connect SSH client"""
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            hostname=self.ssh_host,
            port=self.ssh_port,
            username=self.ssh_user,
            key_filename=self.ssh_key_path,
            timeout=10
        )
        return ssh
    
    def execute_ssh_command(self, command: str, timeout: int = 30) -> Tuple[str, str, int]:
        """Execute SSH command and return (stdout, stderr, exit_code)"""
        ssh = self.get_ssh_client()
        try:
            stdin, stdout, stderr = ssh.exec_command(command, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()
            output = stdout.read().decode('utf-8')
            error = stderr.read().decode('utf-8')
            return output, error, exit_code
        finally:
            ssh.close()
    
    async def confirm_action(self, ctx, action: str, timeout: int = 30) -> bool:
        """Ask for confirmation before destructive action"""
        msg = await ctx.send(f"⚠️ **Confirm {action}?**\nReact with ✅ to confirm (timeout: {timeout}s)")
        await msg.add_reaction('✅')
        await msg.add_reaction('❌')
        
        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ['✅', '❌'] and reaction.message.id == msg.id
        
        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=timeout, check=check)
            return str(reaction.emoji) == '✅'
        except asyncio.TimeoutError:
            await ctx.send("❌ Confirmation timeout - action cancelled")
            return False
    
    # ========================================
    # SERVER PROCESS CONTROL
    # ========================================
    
    @commands.command(name='server_status', aliases=['status', 'srv_status'])
    async def server_status(self, ctx):
        """💚 Check if ET:Legacy server is running"""
        await ctx.send("🔍 Checking server status...")
        
        try:
            # Check if screen session exists
            output, error, exit_code = self.execute_ssh_command(f"screen -ls | grep {self.screen_name}")
            
            if exit_code == 0 and self.screen_name in output:
                # Server is running - get more details
                cpu_cmd = f"ps aux | grep '[e]tlded' | awk '{{print $3}}'"
                mem_cmd = f"ps aux | grep '[e]tlded' | awk '{{print $4}}'"
                
                cpu_output, _, _ = self.execute_ssh_command(cpu_cmd)
                mem_output, _, _ = self.execute_ssh_command(mem_cmd)
                
                cpu_usage = cpu_output.strip() or "N/A"
                mem_usage = mem_output.strip() or "N/A"
                
                # Try to get player count via RCON if enabled
                player_info = ""
                if self.rcon_enabled and self.rcon_password:
                    try:
                        rcon = ETLegacyRCON(self.rcon_host, self.rcon_port, self.rcon_password)
                        status = rcon.send_command('status')
                        rcon.close()
                        
                        # Count player lines (each player line has "num score ping name")
                        player_lines = [line for line in status.split('\n') if line.strip() and not line.startswith('map:') and not line.startswith('num score')]
                        player_count = len(player_lines)
                        player_info = f"\n**Players:** {player_count} online"
                    except:
                        pass
                
                embed = discord.Embed(
                    title="✅ Server Online",
                    description=f"ET:Legacy server is running in screen session `{self.screen_name}`",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                embed.add_field(name="CPU Usage", value=f"{cpu_usage}%", inline=True)
                embed.add_field(name="Memory", value=f"{mem_usage}%", inline=True)
                if player_info:
                    embed.add_field(name="Players", value=player_info.strip(), inline=True)
                
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(
                    title="❌ Server Offline",
                    description=f"ET:Legacy server is not running (screen session `{self.screen_name}` not found)",
                    color=discord.Color.red(),
                    timestamp=datetime.now()
                )
                await ctx.send(embed=embed)
        
        except Exception as e:
            logger.error(f"Error checking server status: {e}", exc_info=True)
            await ctx.send(f"❌ Error checking status: {e}")
    
    @commands.command(name='server_start', aliases=['start', 'srv_start'])
    @commands.check(is_admin_channel)
    async def server_start(self, ctx):
        """🚀 Start the ET:Legacy server (Admin channel only)"""
        await self.log_action(ctx, "Server Start", "Attempting to start server...")
        
        # Check if already running
        check_output, _, check_exit = self.execute_ssh_command(f"screen -ls | grep {self.screen_name}")
        if check_exit == 0 and self.screen_name in check_output:
            await ctx.send("⚠️ Server is already running!")
            return
        
        await ctx.send("🚀 Starting ET:Legacy server...")
        
        try:
            # Start server in screen session using vektor.cfg
            start_command = (
                f"cd {self.server_install_path} && "
                f"screen -dmS {self.screen_name} {self.server_binary} +exec {self.server_config}"
            )
            
            output, error, exit_code = self.execute_ssh_command(start_command)
            
            # Wait a moment for server to start
            await asyncio.sleep(3)
            
            # Verify it started
            verify_output, _, verify_exit = self.execute_ssh_command(f"screen -ls | grep {self.screen_name}")
            
            if verify_exit == 0 and self.screen_name in verify_output:
                embed = discord.Embed(
                    title="✅ Server Started",
                    description=f"ET:Legacy server is now running in screen session `{self.screen_name}`",
                    color=discord.Color.green(),
                    timestamp=datetime.now()
                )
                embed.add_field(
                    name="ℹ️ Note",
                    value="Your watchdog daemon will keep it running automatically",
                    inline=False
                )
                await ctx.send(embed=embed)
                await self.log_action(ctx, "Server Start Success", f"Screen: {self.screen_name}")
            else:
                await ctx.send(f"⚠️ Server may not have started properly. Check logs.\nOutput: {output}\nError: {error}")
                await self.log_action(ctx, "Server Start Failed", f"Exit code: {exit_code}")
        
        except Exception as e:
            logger.error(f"Error starting server: {e}", exc_info=True)
            await ctx.send(f"❌ Error starting server: {e}")
            await self.log_action(ctx, "Server Start Failed", f"❌ Exception: {e}")
    
    @commands.command(name='server_stop', aliases=['stop', 'srv_stop'])
    @commands.check(is_admin_channel)
    async def server_stop(self, ctx):
        """🛑 Stop the ET:Legacy server (Admin channel only)"""
        if not await self.confirm_action(ctx, "STOP server"):
            return
        
        await self.log_action(ctx, "Server Stop", "Attempting to stop server...")
        await ctx.send("🛑 Stopping ET:Legacy server...")
        
        try:
            # Send quit command via RCON if available
            if self.rcon_enabled and self.rcon_password:
                try:
                    rcon = ETLegacyRCON(self.rcon_host, self.rcon_port, self.rcon_password)
                    rcon.send_command('quit')
                    rcon.close()
                    await asyncio.sleep(2)
                except:
                    pass
            
            # Kill screen session
            stop_command = f"screen -S {self.screen_name} -X quit"
            output, error, exit_code = self.execute_ssh_command(stop_command)
            
            # Wait for shutdown
            await asyncio.sleep(2)
            
            # Verify stopped
            verify_output, _, verify_exit = self.execute_ssh_command(f"screen -ls | grep {self.screen_name}")
            
            if verify_exit != 0 or self.screen_name not in verify_output:
                embed = discord.Embed(
                    title="✅ Server Stopped",
                    description=f"ET:Legacy server has been stopped",
                    color=discord.Color.orange(),
                    timestamp=datetime.now()
                )
                embed.add_field(
                    name="⚠️ Note",
                    value="Your watchdog daemon will restart it automatically in ~1 minute",
                    inline=False
                )
                await ctx.send(embed=embed)
                await self.log_action(ctx, "Server Stop Success", "Screen session terminated")
            else:
                await ctx.send("⚠️ Server may still be running. Try again or check manually.")
                await self.log_action(ctx, "Server Stop Failed", "Screen session still exists")
        
        except Exception as e:
            logger.error(f"Error stopping server: {e}", exc_info=True)
            await ctx.send(f"❌ Error stopping server: {e}")
            await self.log_action(ctx, "Server Stop Failed", f"❌ Exception: {e}")
    
    @commands.command(name='server_restart', aliases=['restart', 'srv_restart'])
    @commands.check(is_admin_channel)
    async def server_restart(self, ctx):
        """🔄 Restart the ET:Legacy server (Admin channel only)"""
        if not await self.confirm_action(ctx, "RESTART server"):
            return
        
        await self.log_action(ctx, "Server Restart", "Restarting server...")
        
        await ctx.send("🔄 Restarting ET:Legacy server...")
        
        # Stop first
        await ctx.invoke(self.bot.get_command('server_stop'))
        
        # Wait for clean shutdown
        await asyncio.sleep(5)
        
        # Start again
        await ctx.invoke(self.bot.get_command('server_start'))
    
    # ========================================
    # SERVER UPDATE & DEPLOYMENT
    # ========================================

    @commands.command(name='et_update', aliases=['update_server', 'etlegacy_update'])
    @commands.check(is_admin_channel)
    async def et_update(self, ctx, update_url: str = None):
        """🚀 Update ET:Legacy server with new snapshot (Admin channel only)

        Downloads and installs ET:Legacy snapshot, then uploads new pk3 to Discord.

        Usage: !et_update <snapshot_url>
        Example: !et_update https://github.com/etlegacy/etlegacy/releases/download/continuous/etlegacy-v2.83.1-x86_64.tar.gz
        """
        if not update_url:
            await ctx.send(
                "❌ Please provide the ET:Legacy snapshot download URL!\n\n"
                "**Usage:** `!et_update <snapshot_url>`\n"
                "**Example:** `!et_update https://github.com/etlegacy/etlegacy/releases/download/continuous/etlegacy-v2.83.1-x86_64.tar.gz`"
            )
            return

        # Validate URL
        if not update_url.startswith(('http://', 'https://')):
            await ctx.send("❌ Invalid URL! Must start with http:// or https://")
            return

        if not await self.confirm_action(ctx, "UPDATE ET:Legacy server"):
            return

        await self.log_action(ctx, "ET:Legacy Update", f"URL: {update_url}")

        # Create progress embed
        embed = discord.Embed(
            title="🚀 ET:Legacy Server Update",
            description="Starting update process...",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.add_field(name="📥 Download URL", value=f"`{update_url[:100]}...`" if len(update_url) > 100 else f"`{update_url}`", inline=False)
        status_msg = await ctx.send(embed=embed)

        try:
            # Step 1: Download update file
            await self._update_progress(status_msg, "📥 Downloading ET:Legacy snapshot...", discord.Color.blue())
            download_cmd = f"""
                mkdir -p ~/legacyupdate/backup/logs
                cd ~/legacyupdate/backup
                wget -q '{update_url}' -O etlegacy-update.tar.gz 2>&1
                if [ $? -eq 0 ]; then echo 'SUCCESS'; else echo 'FAILED'; fi
            """
            output, error, exit_code = self.execute_ssh_command(download_cmd, timeout=120)

            if 'FAILED' in output or exit_code != 0:
                await self._update_progress(status_msg, f"❌ Download failed!\n```{error}```", discord.Color.red())
                await self.log_action(ctx, "ET:Legacy Update Failed", "Download failed")
                return

            # Step 2: Extract tarball
            await self._update_progress(status_msg, "📦 Extracting archive...", discord.Color.blue())
            extract_cmd = """
                cd ~/legacyupdate/backup
                tar -zxf etlegacy-update.tar.gz 2>&1
                if [ $? -eq 0 ]; then echo 'SUCCESS'; else echo 'FAILED'; fi
            """
            output, error, exit_code = self.execute_ssh_command(extract_cmd, timeout=60)

            if 'FAILED' in output or exit_code != 0:
                await self._update_progress(status_msg, f"❌ Extraction failed!\n```{error}```", discord.Color.red())
                await self.log_action(ctx, "ET:Legacy Update Failed", "Extraction failed")
                return

            # Step 3: Find extracted directory
            find_dir_cmd = "cd ~/legacyupdate/backup && find . -maxdepth 1 -type d -name 'etlegacy-v*' | head -n 1"
            output, error, exit_code = self.execute_ssh_command(find_dir_cmd)
            extracted_dir = output.strip()

            if not extracted_dir:
                await self._update_progress(status_msg, "❌ Could not find extracted directory!", discord.Color.red())
                await self.log_action(ctx, "ET:Legacy Update Failed", "Extracted directory not found")
                return

            # Step 4: Backup old pk3 files and get old version
            await self._update_progress(status_msg, "💾 Backing up old pk3 files...", discord.Color.blue())
            backup_cmd = f"""
                OLD_PK3=$(find /home/et/etlegacy-v2.83.1-x86_64/legacy/ -name "legacy_v2.83.1-*.pk3" -exec basename {{}} \\; 2>/dev/null | head -n 1)
                echo "OLD_VERSION:$OLD_PK3"
                find /home/et/etlegacy-v2.83.1-x86_64/legacy/ -name "legacy_v2.83.1-*.pk3" -exec mv {{}} ~/legacyupdate/backup/ \\; 2>/dev/null
            """
            output, error, exit_code = self.execute_ssh_command(backup_cmd)
            old_version = "unknown"
            for line in output.split('\n'):
                if line.startswith('OLD_VERSION:'):
                    old_version = line.split(':', 1)[1].strip()
                    break

            # Step 5: Stop server
            await self._update_progress(status_msg, "🛑 Stopping server...", discord.Color.orange())
            stop_cmd = "pkill etlded; sleep 2"
            self.execute_ssh_command(stop_cmd)
            await asyncio.sleep(3)

            # Step 6: Copy new files
            await self._update_progress(status_msg, "📂 Installing new files...", discord.Color.blue())
            install_cmd = f"""
                cd ~/legacyupdate/backup/{extracted_dir}
                cp -r * /home/et/etlegacy-v2.83.1-x86_64/
                if [ $? -eq 0 ]; then echo 'SUCCESS'; else echo 'FAILED'; fi
            """
            output, error, exit_code = self.execute_ssh_command(install_cmd, timeout=60)

            if 'FAILED' in output or exit_code != 0:
                await self._update_progress(status_msg, f"❌ Installation failed!\n```{error}```", discord.Color.red())
                await self.log_action(ctx, "ET:Legacy Update Failed", "Installation failed")
                return

            # Step 7: Find new pk3 file
            await self._update_progress(status_msg, "🔍 Finding new pk3 file...", discord.Color.blue())
            find_pk3_cmd = "find /home/et/etlegacy-v2.83.1-x86_64/legacy/ -name 'legacy_v2.83.1-*.pk3' -exec basename {} \\; 2>/dev/null | head -n 1"
            output, error, exit_code = self.execute_ssh_command(find_pk3_cmd)
            new_pk3_file = output.strip()

            if not new_pk3_file:
                await self._update_progress(status_msg, "⚠️ Update completed but new pk3 file not found!", discord.Color.orange())
                await self.log_action(ctx, "ET:Legacy Update Partial", "pk3 file not found")
                # Start server anyway
                await self._start_server_after_update(ctx, status_msg)
                return

            # Step 8: Download pk3 file to local temp
            await self._update_progress(status_msg, f"📥 Downloading {new_pk3_file}...", discord.Color.blue())

            ssh = self.get_ssh_client()
            sftp = ssh.open_sftp()

            temp_fd, temp_path = tempfile.mkstemp(suffix=f"_{new_pk3_file}", prefix="etlegacy_pk3_")
            os.close(temp_fd)

            remote_pk3_path = f"/home/et/etlegacy-v2.83.1-x86_64/legacy/{new_pk3_file}"
            sftp.get(remote_pk3_path, temp_path)

            # Get file size
            file_size = os.path.getsize(temp_path)
            file_size_mb = file_size / 1024 / 1024

            # Calculate MD5
            with open(temp_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()

            sftp.close()
            ssh.close()

            # Step 9: Upload to Discord
            await self._update_progress(status_msg, f"📤 Uploading {new_pk3_file} to Discord...", discord.Color.blue())

            # Check file size (Discord limit is 25MB for non-Nitro, 500MB for Nitro)
            discord_limit_mb = 25
            if file_size_mb > discord_limit_mb:
                await self._update_progress(
                    status_msg,
                    f"⚠️ File too large for Discord upload ({file_size_mb:.1f}MB > {discord_limit_mb}MB)\n"
                    f"File is available on server at: `{remote_pk3_path}`",
                    discord.Color.orange()
                )
                # Post summary without file
                await self._post_update_summary(ctx, old_version, new_pk3_file, file_hash, file_size_mb, None)
            else:
                # Upload to Discord
                discord_file = discord.File(temp_path, filename=new_pk3_file)

                # Post summary with file
                await self._post_update_summary(ctx, old_version, new_pk3_file, file_hash, file_size_mb, discord_file)

            # Clean up temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)

            # Step 10: Clean up remote files
            cleanup_cmd = """
                cd ~/legacyupdate/backup
                rm -f etlegacy-update.tar.gz
                rm -rf etlegacy-v*
            """
            self.execute_ssh_command(cleanup_cmd)

            # Step 11: Restart server
            await self._start_server_after_update(ctx, status_msg)

            await self._update_progress(status_msg, "✅ Update completed successfully!", discord.Color.green())
            await self.log_action(ctx, "ET:Legacy Update Success", f"{old_version} -> {new_pk3_file}")

        except Exception as e:
            logger.error(f"Error during ET:Legacy update: {e}", exc_info=True)
            await self._update_progress(status_msg, f"❌ Update failed!\n```{str(e)}```", discord.Color.red())
            await ctx.send(f"❌ Update failed with error: {e}")
            await self.log_action(ctx, "ET:Legacy Update Failed", f"Exception: {e}")

    async def _update_progress(self, message: discord.Message, status: str, color: discord.Color):
        """Update the progress embed message"""
        try:
            embed = discord.Embed(
                title="🚀 ET:Legacy Server Update",
                description=status,
                color=color,
                timestamp=datetime.now()
            )
            await message.edit(embed=embed)
        except:
            pass  # Ignore edit failures

    async def _start_server_after_update(self, ctx, status_msg):
        """Start server after update"""
        await self._update_progress(status_msg, "🚀 Starting server...", discord.Color.blue())
        start_cmd = f"cd {self.server_install_path} && screen -dmS {self.screen_name} {self.server_binary} +exec {self.server_config}"
        self.execute_ssh_command(start_cmd)
        await asyncio.sleep(3)

        # Verify it started
        verify_output, _, verify_exit = self.execute_ssh_command(f"screen -ls | grep {self.screen_name}")
        if verify_exit == 0 and self.screen_name in verify_output:
            await self._update_progress(status_msg, "✅ Server restarted successfully!", discord.Color.green())
        else:
            await self._update_progress(status_msg, "⚠️ Server may not have started properly. Check manually.", discord.Color.orange())

    async def _post_update_summary(self, ctx, old_version: str, new_version: str, file_hash: str, file_size_mb: float, discord_file: Optional[discord.File]):
        """Post update summary with optional file attachment"""
        embed = discord.Embed(
            title="✅ ET:Legacy Update Complete",
            description="Server has been updated to the latest snapshot!",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.add_field(name="📦 Old Version", value=f"`{old_version}`", inline=True)
        embed.add_field(name="🆕 New Version", value=f"`{new_version}`", inline=True)
        embed.add_field(name="📊 File Size", value=f"{file_size_mb:.2f} MB", inline=True)
        embed.add_field(name="🔐 MD5 Hash", value=f"`{file_hash}`", inline=False)
        embed.add_field(
            name="📥 Download",
            value="Attached below!" if discord_file else "File too large for Discord - available on server",
            inline=False
        )

        if discord_file:
            await ctx.send(embed=embed, file=discord_file)
        else:
            await ctx.send(embed=embed)

    # ========================================
    # MAP MANAGEMENT
    # ========================================
    
    @commands.command(name='map_list', aliases=['maps', 'listmaps'])
    async def map_list(self, ctx):
        """📋 List available maps on server"""
        await ctx.send("📂 Fetching map list...")
        
        try:
            # List .pk3 files in etmain folder
            list_command = f"ls -lh {self.maps_path}/*.pk3 2>/dev/null | awk '{{print $9, $5}}' || echo 'No maps found'"
            output, error, exit_code = self.execute_ssh_command(list_command)
            
            if "No maps found" in output or not output.strip():
                await ctx.send("❌ No map files found in etmain folder")
                return
            
            # Parse output
            maps = []
            for line in output.strip().split('\n'):
                if line.strip():
                    parts = line.rsplit(' ', 1)
                    if len(parts) == 2:
                        path, size = parts
                        filename = os.path.basename(path)
                        maps.append(f"• `{filename}` ({size})")
            
            if not maps:
                await ctx.send("❌ No maps found")
                return
            
            # Split into chunks if too many maps
            chunk_size = 20
            for i in range(0, len(maps), chunk_size):
                chunk = maps[i:i+chunk_size]
                embed = discord.Embed(
                    title=f"🗺️ Server Maps ({i+1}-{min(i+chunk_size, len(maps))} of {len(maps)})",
                    description='\n'.join(chunk),
                    color=discord.Color.blue(),
                    timestamp=datetime.now()
                )
                embed.set_footer(text=f"Path: {self.maps_path}")
                await ctx.send(embed=embed)
        
        except Exception as e:
            logger.error(f"Error listing maps: {e}", exc_info=True)
            await ctx.send(f"❌ Error listing maps: {e}")
    
    @commands.command(name='map_add', aliases=['addmap', 'upload_map'])
    @commands.check(is_admin_channel)
    async def map_add(self, ctx):
        """➕ Upload new map to server (Admin channel only)
        
        Attach a .pk3 file to your message!
        """
        # Check for attachment
        if not ctx.message.attachments:
            await ctx.send("❌ Please attach a .pk3 map file to your message!")
            return
        
        attachment = ctx.message.attachments[0]
        
        # Validate file extension
        if not attachment.filename.endswith('.pk3'):
            await ctx.send("❌ File must be a .pk3 file!")
            return
        
        # Check file size (limit to 100MB)
        max_size = 100 * 1024 * 1024  # 100MB
        if attachment.size > max_size:
            await ctx.send(f"❌ File too large! Max size: {max_size / 1024 / 1024:.0f}MB")
            return
        
        # Sanitize filename to prevent directory traversal
        sanitized_name = sanitize_filename(attachment.filename)

        await self.log_action(ctx, "Map Upload", f"Uploading {sanitized_name} ({attachment.size / 1024 / 1024:.1f}MB)")

        await ctx.send(f"📥 Downloading `{sanitized_name}`...")

        try:
            # Download to secure temp file
            temp_fd, temp_path = tempfile.mkstemp(suffix=f"_{sanitized_name}", prefix="etlegacy_upload_")
            os.close(temp_fd)  # Close the file descriptor, we'll use the path
            await attachment.save(temp_path)
            
            # Calculate MD5 hash
            with open(temp_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()
            
            await ctx.send(f"📤 Uploading to server... (MD5: `{file_hash}`)")
            
            # Upload via SSH
            ssh = self.get_ssh_client()
            sftp = ssh.open_sftp()

            remote_path = f"{self.maps_path}/{sanitized_name}"
            sftp.put(temp_path, remote_path)

            # Set proper permissions (use shlex.quote for safety)
            safe_path = shlex.quote(remote_path)
            ssh.exec_command(f"chmod 644 {safe_path}")
            
            sftp.close()
            ssh.close()
            
            # Clean up temp file
            os.remove(temp_path)
            
            embed = discord.Embed(
                title="✅ Map Uploaded",
                description=f"`{sanitized_name}` has been uploaded to the server",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Size", value=f"{attachment.size / 1024 / 1024:.1f} MB", inline=True)
            embed.add_field(name="MD5", value=f"`{file_hash[:8]}...`", inline=True)
            embed.add_field(
                name="ℹ️ Next Steps",
                value=f"Use `!map_change {sanitized_name.replace('.pk3', '')}` to load it",
                inline=False
            )

            await ctx.send(embed=embed)
            await self.log_action(ctx, "Map Upload Success", f"{sanitized_name} - MD5: {file_hash}")
        
        except Exception as e:
            logger.error(f"Error uploading map: {e}", exc_info=True)
            await ctx.send(f"❌ Error uploading map: {e}")
            await self.log_action(ctx, "Map Upload Failed", f"❌ {sanitized_name} - {e}")
    
    @commands.command(name='map_change', aliases=['changemap', 'map'])
    @commands.check(is_admin_channel)
    async def map_change(self, ctx, map_name: str):
        """🗺️ Change current map (Admin channel only)
        
        Usage: !map_change <mapname>
        Example: !map_change goldrush
        """
        if not self.rcon_enabled or not self.rcon_password:
            await ctx.send("❌ RCON is not configured! Cannot change map remotely.")
            return
        
        await self.log_action(ctx, "Map Change", f"Changing to map: {map_name}")
        await ctx.send(f"🗺️ Changing map to `{map_name}`...")
        
        try:
            rcon = ETLegacyRCON(self.rcon_host, self.rcon_port, self.rcon_password)
            rcon.send_command(f'map {map_name}')
            rcon.close()
            
            embed = discord.Embed(
                title="✅ Map Changed",
                description=f"Server is now loading `{map_name}`",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            await ctx.send(embed=embed)
            await self.log_action(ctx, "Map Change Success", map_name)
        
        except Exception as e:
            logger.error(f"Error changing map: {e}", exc_info=True)
            await ctx.send(f"❌ Error changing map: {e}")
            await self.log_action(ctx, "Map Change Failed", f"❌ {map_name} - {e}")
    
    @commands.command(name='map_delete', aliases=['deletemap', 'remove_map'])
    @commands.check(is_admin_channel)
    async def map_delete(self, ctx, map_name: str):
        """🗑️ Delete a map from server (Admin channel only)
        
        Usage: !map_delete <mapname.pk3>
        """
        if not await self.confirm_action(ctx, f"DELETE map {map_name}"):
            return
        
        await self.log_action(ctx, "Map Delete", f"Deleting map: {map_name}")
        
        try:
            # Ensure .pk3 extension
            if not map_name.endswith('.pk3'):
                map_name += '.pk3'

            # Sanitize filename to prevent directory traversal
            map_name = sanitize_filename(map_name)

            remote_path = f"{self.maps_path}/{map_name}"

            # Use shlex.quote to prevent command injection
            safe_path = shlex.quote(remote_path)
            delete_command = f"rm -f {safe_path} && echo 'deleted' || echo 'failed'"
            output, error, exit_code = self.execute_ssh_command(delete_command)
            
            if 'deleted' in output:
                embed = discord.Embed(
                    title="✅ Map Deleted",
                    description=f"`{map_name}` has been removed from the server",
                    color=discord.Color.orange(),
                    timestamp=datetime.now()
                )
                await ctx.send(embed=embed)
                await self.log_action(ctx, "Map Delete Success", map_name)
            else:
                await ctx.send(f"❌ Failed to delete map. It may not exist.\nError: {error}")
                await self.log_action(ctx, "Map Delete Failed", f"{map_name} - {error}")
        
        except Exception as e:
            logger.error(f"Error deleting map: {e}", exc_info=True)
            await ctx.send(f"❌ Error deleting map: {e}")
            await self.log_action(ctx, "Map Delete Failed", f"❌ {map_name} - {e}")
    
    # ========================================
    # RCON COMMANDS
    # ========================================
    
    @commands.command(name='rcon')
    @commands.check(is_admin_channel)
    async def rcon_command(self, ctx, *, command: str):
        """🎮 Send RCON command to server (Admin channel only)
        
        Usage: !rcon <command>
        Example: !rcon status
        Example: !rcon say "Server will restart in 5 minutes"
        """
        if not self.rcon_enabled or not self.rcon_password:
            await ctx.send("❌ RCON is not configured!")
            return
        
        # Sanitize command to prevent injection
        safe_command = sanitize_rcon_input(command)
        if safe_command != command:
            await ctx.send("⚠️ Command contained dangerous characters and was sanitized.")
            logger.warning(f"RCON command sanitized: '{command}' -> '{safe_command}'")

        await self.log_action(ctx, "RCON Command", f"Command: {safe_command}")

        try:
            rcon = ETLegacyRCON(self.rcon_host, self.rcon_port, self.rcon_password)
            response = rcon.send_command(safe_command)
            rcon.close()
            
            # Truncate long responses
            if len(response) > 1900:
                response = response[:1900] + "\n... (truncated)"
            
            embed = discord.Embed(
                title="🎮 RCON Response",
                description=f"```\n{response}\n```",
                color=discord.Color.purple(),
                timestamp=datetime.now()
            )
            embed.set_footer(text=f"Command: {command}")
            await ctx.send(embed=embed)
        
        except Exception as e:
            logger.error(f"Error executing RCON: {e}", exc_info=True)
            await ctx.send(f"❌ Error executing RCON command: {e}")
    
    @commands.command(name='kick')
    @commands.check(is_admin_channel)
    async def kick_player(self, ctx, player_id: int, *, reason: str = "Kicked by admin"):
        """👢 Kick a player from server (Admin channel only)
        
        Usage: !kick <player_id> [reason]
        Example: !kick 3 Teamkilling
        """
        if not self.rcon_enabled or not self.rcon_password:
            await ctx.send("❌ RCON is not configured!")
            return
        
        # Sanitize reason to prevent command injection
        safe_reason = sanitize_rcon_input(reason)

        await self.log_action(ctx, "Player Kick", f"Player ID: {player_id}, Reason: {safe_reason}")

        try:
            rcon = ETLegacyRCON(self.rcon_host, self.rcon_port, self.rcon_password)
            rcon.send_command(f'clientkick {player_id} "{safe_reason}"')
            rcon.close()

            await ctx.send(f"✅ Kicked player #{player_id} - Reason: {safe_reason}")
        
        except Exception as e:
            logger.error(f"Error kicking player: {e}", exc_info=True)
            await ctx.send(f"❌ Error kicking player: {e}")
    
    @commands.command(name='say')
    @commands.check(is_admin_channel)
    async def server_say(self, ctx, *, message: str):
        """💬 Send message to server chat (Admin channel only)
        
        Usage: !say <message>
        Example: !say Server will restart in 5 minutes
        """
        if not self.rcon_enabled or not self.rcon_password:
            await ctx.send("❌ RCON is not configured!")
            return

        # Sanitize message to prevent command injection
        safe_message = sanitize_rcon_input(message)

        try:
            rcon = ETLegacyRCON(self.rcon_host, self.rcon_port, self.rcon_password)
            rcon.send_command(f'say "{safe_message}"')
            rcon.close()

            await ctx.send(f"✅ Message sent to server: *{safe_message}*")
        
        except Exception as e:
            logger.error(f"Error sending message: {e}", exc_info=True)
            await ctx.send(f"❌ Error sending message: {e}")
    
    # ========================================
    # ERROR HANDLERS
    # ========================================
    
    @server_start.error
    @server_stop.error
    @server_restart.error
    @map_add.error
    @map_change.error
    @map_delete.error
    @rcon_command.error
    @kick_player.error
    @server_say.error
    async def admin_command_error(self, ctx, error):
        """Handle admin command errors"""
        if isinstance(error, commands.CheckFailure):
            admin_channel = self.bot.get_channel(self.admin_channel_id) if self.admin_channel_id else None
            channel_mention = admin_channel.mention if admin_channel else "the admin channel"
            await ctx.send(
                f"❌ **Permission Denied**\n"
                f"This command can only be used in {channel_mention}!"
            )
        else:
            logger.error(f"Command error: {error}", exc_info=True)
            await ctx.send(f"❌ An error occurred: {error}")


async def setup(bot):
    """Setup function for loading the cog"""
    await bot.add_cog(ServerControl(bot))
