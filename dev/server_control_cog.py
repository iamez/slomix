#!/usr/bin/env python3
"""
🎮 ET:Legacy Server Control Cog
Remote server management via Discord commands
Uses SSH for file operations and process control
Uses RCON for in-game commands
"""

import asyncio
import hashlib
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import discord
import paramiko
from discord.ext import commands

logger = logging.getLogger('ServerControl')


class ETLegacyRCON:
    """RCON client for ET:Legacy server"""
    
    def __init__(self, host: str, port: int, password: str):
        self.host = host
        self.port = port
        self.password = password
        self.socket = None
    
    def connect(self):
        """Connect to RCON server"""
        import socket
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
            return response.decode('utf-8', errors='ignore').split('\n', 1)[1] if '\n' in response.decode('utf-8', errors='ignore') else response.decode('utf-8', errors='ignore')
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
        
        # Server Configuration
        self.server_install_path = os.getenv('ETLEGACY_PATH', '/home/et/.etlegacy')
        self.maps_path = f"{self.server_install_path}/legacy/maps"
        self.screen_name = os.getenv('SCREEN_NAME', 'etlegacy')
        self.server_binary = os.getenv('SERVER_BINARY', './etlded')
        self.server_config = os.getenv('SERVER_CONFIG', 'server.cfg')
        
        # RCON Configuration
        self.rcon_enabled = os.getenv('RCON_ENABLED', 'false').lower() == 'true'
        self.rcon_host = os.getenv('RCON_HOST', self.ssh_host)
        self.rcon_port = int(os.getenv('RCON_PORT', 27960))
        self.rcon_password = os.getenv('RCON_PASSWORD', '')
        
        # Admin Role
        self.admin_role_name = os.getenv('ADMIN_ROLE', 'Server Admin')
        
        # Audit log channel
        self.audit_channel_id = int(os.getenv('AUDIT_CHANNEL_ID', 0)) if os.getenv('AUDIT_CHANNEL_ID') else None
        
        logger.info(f"✅ ServerControl initialized")
        logger.info(f"   SSH: {self.ssh_user}@{self.ssh_host}:{self.ssh_port}")
        logger.info(f"   Server Path: {self.server_install_path}")
        logger.info(f"   Screen: {self.screen_name}")
        logger.info(f"   RCON: {'Enabled' if self.rcon_enabled else 'Disabled'}")
    
    def has_admin_role(ctx):
        """Check if user has admin role"""
        if not ctx.guild:
            return False
        admin_role_name = os.getenv('ADMIN_ROLE', 'Server Admin')
        return any(role.name == admin_role_name for role in ctx.author.roles)
    
    async def log_action(self, ctx, action: str, details: str = ""):
        """Log admin action to audit channel"""
        log_msg = f"🔧 **{action}** by {ctx.author.mention} ({ctx.author.id})\n{details}"
        logger.info(f"AUDIT: {action} by {ctx.author} - {details}")
        
        if self.audit_channel_id:
            channel = self.bot.get_channel(self.audit_channel_id)
            if channel:
                embed = discord.Embed(
                    title=f"🔒 Server Action: {action}",
                    description=details,
                    color=discord.Color.blue(),
                    timestamp=datetime.now()
                )
                embed.set_footer(text=f"By {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
                await channel.send(embed=embed)
    
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
                # Get process info
                process_check = f"ps aux | grep '[e]tlded' | grep -v grep"
                ps_output, _, _ = self.execute_ssh_command(process_check)
                
                embed = discord.Embed(
                    title="✅ Server Online",
                    description=f"ET:Legacy server is **running** in screen session `{self.screen_name}`",
                    color=discord.Color.green()
                )
                
                if ps_output:
                    # Parse CPU and memory usage
                    parts = ps_output.split()
                    if len(parts) >= 11:
                        cpu = parts[2]
                        mem = parts[3]
                        embed.add_field(name="CPU Usage", value=f"{cpu}%", inline=True)
                        embed.add_field(name="Memory", value=f"{mem}%", inline=True)
                
                # Try RCON status if enabled
                if self.rcon_enabled and self.rcon_password:
                    try:
                        rcon = ETLegacyRCON(self.rcon_host, self.rcon_port, self.rcon_password)
                        status = rcon.send_command("status")
                        rcon.close()
                        
                        # Parse player count
                        if "players" in status.lower():
                            lines = status.split('\n')
                            player_lines = [l for l in lines if l.strip() and not l.startswith('map:')]
                            player_count = len(player_lines) - 1  # Subtract header
                            embed.add_field(name="Players", value=f"{player_count} online", inline=True)
                    except Exception as e:
                        logger.debug(f"RCON status failed: {e}")
                
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(
                    title="❌ Server Offline",
                    description=f"ET:Legacy server is **not running**\nScreen session `{self.screen_name}` not found",
                    color=discord.Color.red()
                )
                embed.add_field(
                    name="Start Server",
                    value=f"Use `!server_start` to start the server",
                    inline=False
                )
                await ctx.send(embed=embed)
        
        except Exception as e:
            logger.error(f"Error checking server status: {e}", exc_info=True)
            await ctx.send(f"❌ Error checking status: {e}")
    
    @commands.command(name='server_start', aliases=['start', 'srv_start'])
    @commands.check(has_admin_role)
    async def server_start(self, ctx):
        """🚀 Start the ET:Legacy server (Admin only)"""
        await self.log_action(ctx, "Server Start", "Attempting to start server...")
        
        # Check if already running
        check_output, _, check_exit = self.execute_ssh_command(f"screen -ls | grep {self.screen_name}")
        if check_exit == 0 and self.screen_name in check_output:
            await ctx.send("⚠️ Server is already running!")
            return
        
        await ctx.send("🚀 Starting ET:Legacy server...")
        
        try:
            # Start server in screen session
            start_command = (
                f"cd {self.server_install_path} && "
                f"screen -dmS {self.screen_name} "
                f"{self.server_binary} +set fs_basepath {self.server_install_path} "
                f"+set fs_homepath {self.server_install_path} "
                f"+exec {self.server_config}"
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
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="Check Status",
                    value="Use `!server_status` to verify",
                    inline=False
                )
                await ctx.send(embed=embed)
                await self.log_action(ctx, "Server Started", "✅ Success")
            else:
                await ctx.send(f"⚠️ Server may not have started properly. Check logs.\n```{error}```")
                await self.log_action(ctx, "Server Start Failed", f"❌ Error: {error}")
        
        except Exception as e:
            logger.error(f"Error starting server: {e}", exc_info=True)
            await ctx.send(f"❌ Error starting server: {e}")
            await self.log_action(ctx, "Server Start Failed", f"❌ Exception: {e}")
    
    @commands.command(name='server_stop', aliases=['stop', 'srv_stop'])
    @commands.check(has_admin_role)
    async def server_stop(self, ctx):
        """🛑 Stop the ET:Legacy server (Admin only)"""
        if not await self.confirm_action(ctx, "STOP server"):
            return
        
        await self.log_action(ctx, "Server Stop", "Attempting to stop server...")
        await ctx.send("🛑 Stopping ET:Legacy server...")
        
        try:
            # Send quit command via RCON if available
            if self.rcon_enabled and self.rcon_password:
                try:
                    rcon = ETLegacyRCON(self.rcon_host, self.rcon_port, self.rcon_password)
                    rcon.send_command("quit")
                    rcon.close()
                    await asyncio.sleep(2)
                except Exception as e:
                    logger.debug(f"RCON quit failed, using screen kill: {e}")
            
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
                    description="ET:Legacy server has been shut down",
                    color=discord.Color.orange()
                )
                await ctx.send(embed=embed)
                await self.log_action(ctx, "Server Stopped", "✅ Success")
            else:
                await ctx.send("⚠️ Server may still be running. Check status.")
                await self.log_action(ctx, "Server Stop", "⚠️ Uncertain state")
        
        except Exception as e:
            logger.error(f"Error stopping server: {e}", exc_info=True)
            await ctx.send(f"❌ Error stopping server: {e}")
            await self.log_action(ctx, "Server Stop Failed", f"❌ Exception: {e}")
    
    @commands.command(name='server_restart', aliases=['restart', 'srv_restart'])
    @commands.check(has_admin_role)
    async def server_restart(self, ctx):
        """🔄 Restart the ET:Legacy server (Admin only)"""
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
    # MAP MANAGEMENT
    # ========================================
    
    @commands.command(name='map_list', aliases=['maps', 'listmaps'])
    async def map_list(self, ctx):
        """📋 List available maps on server"""
        await ctx.send("📂 Fetching map list...")
        
        try:
            # List .pk3 files in maps directory
            command = f"ls -lh {self.maps_path}/*.pk3 | awk '{{print $9, $5}}'"
            output, error, exit_code = self.execute_ssh_command(command)
            
            if exit_code == 0 and output:
                lines = output.strip().split('\n')
                maps_info = []
                
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 2:
                        filepath = parts[0]
                        size = parts[1]
                        mapname = Path(filepath).stem
                        maps_info.append(f"`{mapname}` ({size})")
                
                # Create paginated embed
                maps_per_page = 20
                pages = [maps_info[i:i+maps_per_page] for i in range(0, len(maps_info), maps_per_page)]
                
                embed = discord.Embed(
                    title=f"🗺️ Available Maps ({len(maps_info)} total)",
                    description="\n".join(pages[0]),
                    color=discord.Color.blue()
                )
                embed.set_footer(text=f"Page 1/{len(pages)} • Use !map_change <mapname> to change")
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"❌ Could not list maps\n```{error}```")
        
        except Exception as e:
            logger.error(f"Error listing maps: {e}", exc_info=True)
            await ctx.send(f"❌ Error listing maps: {e}")
    
    @commands.command(name='map_add', aliases=['addmap', 'upload_map'])
    @commands.check(has_admin_role)
    async def map_add(self, ctx):
        """➕ Upload new map to server (Admin only)
        
        Attach a .pk3 file to your message!
        """
        # Check for attachment
        if not ctx.message.attachments:
            await ctx.send("❌ Please attach a `.pk3` map file to your message!")
            return
        
        attachment = ctx.message.attachments[0]
        
        # Validate file extension
        if not attachment.filename.endswith('.pk3'):
            await ctx.send("❌ File must be a `.pk3` map file!")
            return
        
        # Check file size (limit to 50MB)
        max_size = 50 * 1024 * 1024  # 50MB
        if attachment.size > max_size:
            await ctx.send(f"❌ File too large! Max size: 50MB (your file: {attachment.size / 1024 / 1024:.1f}MB)")
            return
        
        await self.log_action(ctx, "Map Upload", f"Uploading {attachment.filename} ({attachment.size / 1024 / 1024:.1f}MB)")
        
        await ctx.send(f"📥 Downloading `{attachment.filename}`...")
        
        try:
            # Download to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pk3') as tmp_file:
                await attachment.save(tmp_file.name)
                local_path = tmp_file.name
            
            # Calculate checksum
            with open(local_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()
            
            await ctx.send(f"📤 Uploading to server... (MD5: `{file_hash[:8]}`)")
            
            # Upload via SFTP
            ssh = self.get_ssh_client()
            sftp = ssh.open_sftp()
            
            remote_path = f"{self.maps_path}/{attachment.filename}"
            sftp.put(local_path, remote_path)
            
            # Verify upload
            stat = sftp.stat(remote_path)
            sftp.close()
            ssh.close()
            
            # Clean up local temp file
            os.unlink(local_path)
            
            embed = discord.Embed(
                title="✅ Map Uploaded",
                description=f"**{attachment.filename}** has been uploaded to the server",
                color=discord.Color.green()
            )
            embed.add_field(name="Size", value=f"{stat.st_size / 1024 / 1024:.2f} MB", inline=True)
            embed.add_field(name="MD5", value=f"`{file_hash[:16]}`", inline=True)
            embed.add_field(
                name="Load Map",
                value=f"Use `!map_change {Path(attachment.filename).stem}` to load it",
                inline=False
            )
            
            await ctx.send(embed=embed)
            await self.log_action(ctx, "Map Uploaded", f"✅ {attachment.filename} uploaded successfully")
        
        except Exception as e:
            logger.error(f"Error uploading map: {e}", exc_info=True)
            await ctx.send(f"❌ Error uploading map: {e}")
            await self.log_action(ctx, "Map Upload Failed", f"❌ Exception: {e}")
    
    @commands.command(name='map_change', aliases=['changemap', 'map'])
    @commands.check(has_admin_role)
    async def map_change(self, ctx, map_name: str):
        """🗺️ Change current map (Admin only)
        
        Usage: !map_change <mapname>
        Example: !map_change goldrush
        """
        if not self.rcon_enabled or not self.rcon_password:
            await ctx.send("❌ RCON is not configured! Cannot change map.")
            return
        
        await self.log_action(ctx, "Map Change", f"Changing to map: {map_name}")
        await ctx.send(f"🗺️ Changing map to `{map_name}`...")
        
        try:
            rcon = ETLegacyRCON(self.rcon_host, self.rcon_port, self.rcon_password)
            response = rcon.send_command(f"map {map_name}")
            rcon.close()
            
            # Wait for map change
            await asyncio.sleep(3)
            
            embed = discord.Embed(
                title="✅ Map Changed",
                description=f"Server is now loading **{map_name}**",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
            await self.log_action(ctx, "Map Changed", f"✅ Changed to {map_name}")
        
        except Exception as e:
            logger.error(f"Error changing map: {e}", exc_info=True)
            await ctx.send(f"❌ Error changing map: {e}")
            await self.log_action(ctx, "Map Change Failed", f"❌ Exception: {e}")
    
    @commands.command(name='map_delete', aliases=['deletemap', 'remove_map'])
    @commands.check(has_admin_role)
    async def map_delete(self, ctx, map_name: str):
        """🗑️ Delete a map from server (Admin only)
        
        Usage: !map_delete <mapname>
        """
        if not await self.confirm_action(ctx, f"DELETE map {map_name}"):
            return
        
        await self.log_action(ctx, "Map Delete", f"Deleting map: {map_name}")
        
        try:
            # Add .pk3 if not present
            if not map_name.endswith('.pk3'):
                map_name = f"{map_name}.pk3"
            
            remote_path = f"{self.maps_path}/{map_name}"
            command = f"rm {remote_path}"
            output, error, exit_code = self.execute_ssh_command(command)
            
            if exit_code == 0:
                await ctx.send(f"✅ Map `{map_name}` has been deleted")
                await self.log_action(ctx, "Map Deleted", f"✅ Deleted {map_name}")
            else:
                await ctx.send(f"❌ Could not delete map: {error}")
                await self.log_action(ctx, "Map Delete Failed", f"❌ Error: {error}")
        
        except Exception as e:
            logger.error(f"Error deleting map: {e}", exc_info=True)
            await ctx.send(f"❌ Error deleting map: {e}")
            await self.log_action(ctx, "Map Delete Failed", f"❌ Exception: {e}")
    
    # ========================================
    # RCON COMMANDS
    # ========================================
    
    @commands.command(name='rcon')
    @commands.check(has_admin_role)
    async def rcon_command(self, ctx, *, command: str):
        """🎮 Send RCON command to server (Admin only)
        
        Usage: !rcon <command>
        Example: !rcon status
        Example: !rcon say "Server will restart in 5 minutes"
        """
        if not self.rcon_enabled or not self.rcon_password:
            await ctx.send("❌ RCON is not configured!")
            return
        
        await self.log_action(ctx, "RCON Command", f"Command: {command}")
        
        try:
            rcon = ETLegacyRCON(self.rcon_host, self.rcon_port, self.rcon_password)
            response = rcon.send_command(command)
            rcon.close()
            
            # Format response
            if len(response) > 1900:
                response = response[:1900] + "... (truncated)"
            
            embed = discord.Embed(
                title="🎮 RCON Response",
                description=f"```\n{response}\n```",
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"Command: {command}")
            await ctx.send(embed=embed)
        
        except Exception as e:
            logger.error(f"Error executing RCON command: {e}", exc_info=True)
            await ctx.send(f"❌ RCON error: {e}")
    
    @commands.command(name='kick')
    @commands.check(has_admin_role)
    async def kick_player(self, ctx, player_id: int, *, reason: str = "Kicked by admin"):
        """👢 Kick a player from server (Admin only)
        
        Usage: !kick <player_id> [reason]
        Example: !kick 3 Teamkilling
        """
        if not self.rcon_enabled or not self.rcon_password:
            await ctx.send("❌ RCON is not configured!")
            return
        
        await self.log_action(ctx, "Player Kick", f"Player ID: {player_id}, Reason: {reason}")
        
        try:
            rcon = ETLegacyRCON(self.rcon_host, self.rcon_port, self.rcon_password)
            response = rcon.send_command(f"kick {player_id}")
            rcon.close()
            
            await ctx.send(f"✅ Player #{player_id} kicked: {reason}")
        
        except Exception as e:
            logger.error(f"Error kicking player: {e}", exc_info=True)
            await ctx.send(f"❌ Error: {e}")
    
    @commands.command(name='say')
    @commands.check(has_admin_role)
    async def server_say(self, ctx, *, message: str):
        """💬 Send message to server chat (Admin only)
        
        Usage: !say <message>
        Example: !say Server will restart in 5 minutes
        """
        if not self.rcon_enabled or not self.rcon_password:
            await ctx.send("❌ RCON is not configured!")
            return
        
        try:
            rcon = ETLegacyRCON(self.rcon_host, self.rcon_port, self.rcon_password)
            rcon.send_command(f'say "{message}"')
            rcon.close()
            
            await ctx.send(f"✅ Message sent to server: *{message}*")
            await self.log_action(ctx, "Server Message", f"Message: {message}")
        
        except Exception as e:
            logger.error(f"Error sending message: {e}", exc_info=True)
            await ctx.send(f"❌ Error: {e}")
    
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
            embed = discord.Embed(
                title="❌ Permission Denied",
                description=f"You need the `{self.admin_role_name}` role to use this command!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        else:
            logger.error(f"Command error: {error}", exc_info=True)
            await ctx.send(f"❌ Command error: {error}")


async def setup(bot):
    """Setup function for loading the cog"""
    await bot.add_cog(ServerControl(bot))
