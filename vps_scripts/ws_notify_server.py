#!/usr/bin/env python3
"""
VPS WebSocket Notification Server for ET:Legacy Stats Bot

This script runs on the VPS (game server) and:
1. Uses inotifywait to watch for new stats files
2. Maintains WebSocket connections from Discord bot clients
3. Pushes filename notifications instantly when new files appear

Installation on VPS:
    pip install websockets
    
    # Make executable
    chmod +x ws_notify_server.py
    
    # Run directly
    ./ws_notify_server.py
    
    # Or as systemd service (see bottom of file for unit file)

Configuration:
    Set environment variables or edit the defaults below:
    - WS_PORT: Port to listen on (default: 8765)
    - WS_AUTH_TOKEN: Shared secret for client authentication
    - STATS_DIR: Directory to watch for new files

Usage:
    # Start server
    ./ws_notify_server.py
    
    # Test with wscat
    wscat -c ws://localhost:8765
    > your_auth_token
    < AUTH_OK
    < 2025-12-02-201530-supply-round-1.txt  (when file appears)
"""

import asyncio
import logging
import os
import signal
import sys
from datetime import datetime
from typing import Set

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('WSNotifyServer')

try:
    import websockets
    from websockets.server import WebSocketServerProtocol
except ImportError:
    logger.error("❌ websockets library not installed!")
    logger.error("   Run: pip install websockets")
    sys.exit(1)


# ==================== CONFIGURATION ====================
# Override via environment variables, or edit defaults here

WS_PORT = int(os.getenv('WS_PORT', '8765'))
WS_AUTH_TOKEN = os.getenv('WS_AUTH_TOKEN', 'YOUR_SECRET_TOKEN_HERE')  # Change this!
STATS_DIR = os.getenv('STATS_DIR', '/home/et/.etlegacy/legacy/gamestats')

# ========================================================


class StatsNotifyServer:
    """
    WebSocket server that notifies connected clients of new stats files.
    """
    
    def __init__(self, port: int, auth_token: str, stats_dir: str):
        self.port = port
        self.auth_token = auth_token
        self.stats_dir = stats_dir
        
        # Connected clients (authenticated)
        self.clients: Set[WebSocketServerProtocol] = set()
        
        # Stats
        self.files_notified = 0
        self.start_time = None
        
        logger.info(f"📡 Server config: port={port}, auth={'enabled' if auth_token else 'disabled'}")
        logger.info(f"📁 Watching directory: {stats_dir}")
    
    async def handler(self, websocket: WebSocketServerProtocol):
        """
        Handle incoming WebSocket connection.
        
        Flow:
        1. Client connects
        2. If auth enabled, wait for token
        3. Add to clients set
        4. Keep connection alive until closed
        """
        client_addr = websocket.remote_address
        logger.info(f"🔗 New connection from {client_addr}")
        
        try:
            # Authentication (if enabled)
            if self.auth_token:
                try:
                    token = await asyncio.wait_for(websocket.recv(), timeout=10)
                    # Security: only log length, not token content
                    logger.debug(f"🔑 Auth token received (len={len(token)})")
                    if token.strip() != self.auth_token:
                        logger.warning(f"🚫 Auth failed from {client_addr}")
                        await websocket.send("AUTH_FAILED")
                        await websocket.close(1008, "Invalid token")
                        return
                    await websocket.send("AUTH_OK")
                    logger.info(f"✅ Client authenticated: {client_addr}")
                except asyncio.TimeoutError:
                    logger.warning(f"⏰ Auth timeout from {client_addr}")
                    await websocket.close(1008, "Auth timeout")
                    return
            
            # Add to connected clients
            self.clients.add(websocket)
            logger.info(f"👥 Active clients: {len(self.clients)}")
            
            # Keep connection alive
            try:
                async for message in websocket:
                    # Handle any client messages (usually just keepalive)
                    if message == "PING":
                        await websocket.send("PONG")
                    else:
                        logger.debug(f"📨 Message from {client_addr}: {message[:50]}")
            except websockets.ConnectionClosed:  # nosec B110
                pass  # Client disconnected, handled in finally
                
        finally:
            # Remove from clients
            self.clients.discard(websocket)
            logger.info(f"👋 Client disconnected: {client_addr} (remaining: {len(self.clients)})")
    
    async def notify_all(self, filename: str):
        """
        Send filename notification to all connected clients.
        
        Args:
            filename: Name of new stats file
        """
        if not self.clients:
            logger.debug(f"📭 No clients to notify for: {filename}")
            return
        
        logger.info(f"📤 Notifying {len(self.clients)} clients: {filename}")
        self.files_notified += 1
        
        # Send to all clients concurrently
        tasks = [client.send(filename) for client in self.clients.copy()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check for errors
        for client, result in zip(self.clients.copy(), results):
            if isinstance(result, Exception):
                logger.warning(f"⚠️ Failed to notify {client.remote_address}: {result}")
    
    async def watch_directory(self):
        """
        Watch stats directory for new files using inotifywait.
        
        Uses subprocess to run inotifywait -m (monitor mode).
        When new file detected, calls notify_all().
        """
        logger.info(f"👁️ Starting directory watcher: {self.stats_dir}")
        
        # Check if inotifywait is available
        proc_check = await asyncio.create_subprocess_exec(
            'which', 'inotifywait',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await proc_check.wait()
        
        if proc_check.returncode != 0:
            logger.error("❌ inotifywait not found!")
            logger.error("   Run: sudo apt install inotify-tools")
            return
        
        # Start inotifywait in monitor mode
        # -m = monitor mode (don't exit after first event)
        # -e close_write = trigger when file is finished writing
        # --format '%f' = output just the filename
        proc = await asyncio.create_subprocess_exec(
            'inotifywait',
            '-m',
            '-e', 'close_write',
            '--format', '%f',
            self.stats_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        logger.info("✅ inotifywait started")
        
        try:
            async for line in proc.stdout:
                filename = line.decode().strip()
                
                # Filter for stats files only
                if filename.endswith('.txt') and '-round-' in filename:
                    logger.info(f"📁 New file detected: {filename}")
                    await self.notify_all(filename)
                else:
                    logger.debug(f"⏭️ Ignoring non-stats file: {filename}")
                    
        except asyncio.CancelledError:
            logger.info("🛑 Directory watcher cancelled")
            proc.terminate()
            raise
    
    async def run(self):
        """
        Start the WebSocket server and directory watcher.
        """
        self.start_time = datetime.now()
        
        logger.info(f"🚀 Starting WebSocket server on port {self.port}")
        
        # Start WebSocket server
        async with websockets.serve(
            self.handler,
            "0.0.0.0",  # nosec B104 - must accept external
            self.port,
            ping_interval=30,
            ping_timeout=10
        ):
            logger.info(f"✅ Server listening on ws://0.0.0.0:{self.port}")
            
            # Start directory watcher
            await self.watch_directory()


async def main():
    """Main entry point."""
    # Validate config
    if not os.path.isdir(STATS_DIR):
        logger.error(f"❌ Stats directory not found: {STATS_DIR}")
        logger.error("   Set STATS_DIR environment variable")
        sys.exit(1)
    
    if not WS_AUTH_TOKEN:
        logger.warning("⚠️ No WS_AUTH_TOKEN set - server accepts unauthenticated connections!")
    
    # Create and run server
    server = StatsNotifyServer(WS_PORT, WS_AUTH_TOKEN, STATS_DIR)
    
    # Handle shutdown signals
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda: asyncio.create_task(shutdown(server))
        )
    
    try:
        await server.run()
    except asyncio.CancelledError:
        logger.info("👋 Server shutdown complete")


async def shutdown(server):
    """Graceful shutdown handler."""
    logger.info("🛑 Shutdown signal received")
    
    # Close all client connections
    for client in server.clients.copy():
        await client.close(1001, "Server shutting down")
    
    # Cancel all tasks
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    
    await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Interrupted by user")


# ==================== SYSTEMD SERVICE FILE ====================
# Save this as: /etc/systemd/system/stats-notify.service
#
# [Unit]
# Description=ET:Legacy Stats WebSocket Notification Server
# After=network.target
#
# [Service]
# Type=simple
# User=et
# WorkingDirectory=/home/et/scripts
# Environment="WS_PORT=8765"
# Environment="WS_AUTH_TOKEN=your_secret_token_here"
# Environment="STATS_DIR=/home/et/.etlegacy/legacy/gamestats"
# ExecStart=/usr/bin/python3 /home/et/scripts/ws_notify_server.py
# Restart=always
# RestartSec=5
#
# [Install]
# WantedBy=multi-user.target
#
# Then run:
#   sudo systemctl daemon-reload
#   sudo systemctl enable stats-notify
#   sudo systemctl start stats-notify
#   sudo systemctl status stats-notify
# ==============================================================
