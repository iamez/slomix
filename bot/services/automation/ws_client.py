"""
WebSocket Client Service - Push-based file notifications from VPS

This service handles:
- Outbound WebSocket connection to VPS (no ports needed on bot machine)
- Receiving real-time "new file" notifications from game server
- Triggering file download + processing + Discord posting
- Auto-reconnection with exponential backoff

Architecture:
- Bot connects OUT to VPS WebSocket server on startup
- VPS uses inotifywait to detect new stats files
- VPS pushes filename to connected bot clients instantly
- Bot downloads file via SSH and processes normally

This replaces polling-based SSH monitoring for faster notifications (<1s vs 60s).
SSH polling is kept as fallback (every 10 min) if WebSocket disconnects.
"""

import asyncio
import logging
import re
from datetime import datetime
from typing import Optional, Callable, Awaitable

logger = logging.getLogger('WebSocketClient')

SAFE_WS_STATS_FILENAME_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}-\d{6}-[A-Za-z0-9_.+-]+-round-\d+(?:-endstats)?(?:_ws)?\.txt$"
)

# Try to import websockets library
try:
    import websockets
    from websockets.client import WebSocketClientProtocol
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    logger.debug("websockets library not installed; WebSocket push client unavailable")


class StatsWebSocketClient:
    """
    WebSocket client that connects to VPS for push-based file notifications.
    
    The bot initiates the connection (outbound), so no ports need to be
    opened on the bot's machine. The VPS pushes notifications when new
    stats files are detected.
    """
    
    def __init__(
        self,
        config,
        on_new_file: Callable[[str], Awaitable[None]]
    ):
        """
        Initialize WebSocket client.
        
        Args:
            config: BotConfig instance with WS_* settings
            on_new_file: Async callback when new file notification received.
                         Takes filename as argument.
        """
        self.config = config
        self.on_new_file = on_new_file
        
        # Connection state
        self._ws: Optional[WebSocketClientProtocol] = None
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._connected = False
        
        # Stats
        self.files_received = 0
        self.last_notification: Optional[datetime] = None
        self.reconnect_count = 0
        
        # Build URI
        ws_scheme = str(getattr(config, "ws_scheme", "wss") or "wss").strip().lower()
        if ws_scheme not in {"ws", "wss"}:
            ws_scheme = "wss"
        self.uri = f"{ws_scheme}://{config.ws_host}:{config.ws_port}"
        if ws_scheme == "ws":
            logger.warning("⚠️ Insecure WebSocket scheme configured (ws://). Prefer wss:// in production.")
        
        logger.info(f"✅ StatsWebSocketClient initialized (target: {self.uri})")
    
    @property
    def is_connected(self) -> bool:
        """Check if currently connected to VPS."""
        return self._connected and self._ws is not None
    
    def start(self) -> asyncio.Task:
        """
        Start the WebSocket client connection loop.
        
        Returns:
            The background task running the connection loop.
        """
        if not WEBSOCKETS_AVAILABLE:
            logger.error("❌ Cannot start WebSocket client: websockets library not installed")
            raise RuntimeError("websockets library not installed")
        
        if self._task and not self._task.done():
            logger.warning("⚠️ WebSocket client already running")
            return self._task
        
        self._running = True
        self._task = asyncio.create_task(
            self._connection_loop(),
            name="ws-stats-client"
        )
        logger.info("🚀 WebSocket client started")
        return self._task
    
    def stop(self):
        """Stop the WebSocket client gracefully."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("🛑 WebSocket client stopped")
    
    async def _connection_loop(self):
        """
        Main connection loop with auto-reconnect.
        
        Connects to VPS WebSocket server and listens for file notifications.
        On disconnect, waits and retries with exponential backoff.
        """
        backoff = self.config.ws_reconnect_delay
        max_backoff = 300  # Max 5 minutes between retries
        
        while self._running:
            try:
                logger.info(f"🔌 Connecting to VPS WebSocket: {self.uri}")
                
                async with websockets.connect(
                    self.uri,
                    ping_interval=30,
                    ping_timeout=10,
                    close_timeout=5
                ) as ws:
                    self._ws = ws
                    self._connected = True
                    backoff = self.config.ws_reconnect_delay  # Reset backoff on success
                    
                    # Authenticate with shared token
                    if self.config.ws_auth_token:
                        token = self.config.ws_auth_token
                        # Security: only log length, not token content
                        logger.debug(f"🔑 Sending auth token (len={len(token)})")
                        await ws.send(token)
                        auth_response = await asyncio.wait_for(ws.recv(), timeout=5)
                        if auth_response != "AUTH_OK":
                            logger.error(f"❌ WebSocket authentication failed: {auth_response}")
                            self._connected = False
                            await asyncio.sleep(backoff)  # Wait before retry
                            backoff = min(backoff * 2, max_backoff)
                            continue
                    
                    logger.info(f"✅ Connected to VPS WebSocket (reconnects: {self.reconnect_count})")
                    
                    # Listen for file notifications
                    async for message in ws:
                        await self._handle_message(message)
                        
            except websockets.ConnectionClosed as e:
                self._connected = False
                self._ws = None
                logger.warning(f"🔌 WebSocket connection closed: {e.code} {e.reason}")
                
            except asyncio.TimeoutError:
                self._connected = False
                self._ws = None
                logger.warning("⏰ WebSocket connection timeout")
                
            except ConnectionRefusedError:
                self._connected = False
                self._ws = None
                logger.warning("🚫 WebSocket refused (VPS down?)")
                
            except Exception as e:
                self._connected = False
                self._ws = None
                logger.error(f"❌ WebSocket error: {e}", exc_info=True)
            
            # Wait before reconnecting (if still running)
            if self._running:
                self.reconnect_count += 1
                logger.info(f"⏳ Reconnecting in {backoff}s (attempt #{self.reconnect_count})...")
                await asyncio.sleep(backoff)
                # Exponential backoff
                backoff = min(backoff * 2, max_backoff)
        
        logger.info("👋 WebSocket connection loop ended")
    
    async def _handle_message(self, message: str):
        """
        Handle incoming message from VPS.
        
        Expected messages:
        - Filename (e.g., "2025-12-02-201530-supply-round-1.txt")
        - PING (keepalive)
        - AUTH_OK (authentication response)
        
        Args:
            message: Raw message string from WebSocket
        """
        message = message.strip()
        
        # Ignore keepalive pings
        if message == "PING":
            logger.debug("📶 Received keepalive ping")
            return
        
        # Ignore auth response (handled in connection loop)
        if message == "AUTH_OK":
            return
        
        # Treat as filename notification
        if self._is_valid_stats_filename(message):
            logger.info(f"📥 NEW FILE notification: {message}")
            self.files_received += 1
            self.last_notification = datetime.now()
            
            try:
                await self.on_new_file(message)
            except Exception as e:
                logger.error(f"❌ Error processing file notification: {e}", exc_info=True)
        elif message.endswith('.txt'):
            logger.warning(f"⚠️ Rejected unsafe filename from VPS: {message[:100]}")
        else:
            logger.warning(f"⚠️ Unknown message from VPS: {message[:100]}")

    @staticmethod
    def _is_valid_stats_filename(filename: str) -> bool:
        candidate = str(filename or "").strip()
        if not candidate or len(candidate) > 255:
            return False
        if "/" in candidate or "\\" in candidate or ".." in candidate:
            return False
        return SAFE_WS_STATS_FILENAME_PATTERN.match(candidate) is not None
    
    def get_status(self) -> dict:
        """
        Get current client status.
        
        Returns:
            Dict with connection status and stats
        """
        return {
            'enabled': self.config.ws_enabled,
            'connected': self.is_connected,
            'uri': self.uri,
            'files_received': self.files_received,
            'last_notification': self.last_notification.isoformat() if self.last_notification else None,
            'reconnect_count': self.reconnect_count,
            'running': self._running
        }


# Convenience function to check if WebSocket is available
def is_websocket_available() -> bool:
    """Check if websockets library is installed."""
    return WEBSOCKETS_AVAILABLE
