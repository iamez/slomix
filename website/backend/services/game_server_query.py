"""
Game Server Query Service
Queries ET:Legacy/Quake3 servers using UDP protocol (no password required)
"""

import socket
import re
import logging
import time
from typing import Optional, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Player:
    """Player info from server query"""
    name: str
    score: int
    ping: int


@dataclass
class ServerStatus:
    """Game server status"""
    online: bool
    map_name: Optional[str] = None
    hostname: Optional[str] = None
    player_count: int = 0
    max_players: int = 0
    players: List[Player] = field(default_factory=list)
    game_type: Optional[str] = None
    version: Optional[str] = None
    ping_ms: Optional[int] = None  # Response time in milliseconds
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON response"""
        return {
            'online': self.online,
            'map': self.map_name,
            'hostname': self.clean_hostname,
            'player_count': self.player_count,
            'max_players': self.max_players,
            'players': [{'name': p.name, 'score': p.score, 'ping': p.ping} for p in self.players],
            'game_type': self.game_type,
            'version': self.version,
            'ping_ms': self.ping_ms,
            'error': self.error,
        }

    @property
    def clean_hostname(self) -> Optional[str]:
        """Remove Quake3 color codes from hostname"""
        if not self.hostname:
            return None
        return re.sub(r'\^[0-9a-zA-Z]', '', self.hostname)


def query_game_server(host: str, port: int = 27960, timeout: float = 3.0) -> ServerStatus:
    """
    Query an ET:Legacy/Quake3 game server using UDP protocol.

    This uses the standard Quake3 query protocol (getstatus) which doesn't
    require any password - it's the same protocol game clients use to
    browse servers.

    Args:
        host: Server hostname or IP
        port: Server port (default 27960)
        timeout: Query timeout in seconds

    Returns:
        ServerStatus object with server info including ping_ms
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)

    try:
        # Quake3 query packet: \xff\xff\xff\xff + "getstatus\n"
        query = b'\xff\xff\xff\xffgetstatus\n'

        # Measure response time
        start_time = time.perf_counter()
        sock.sendto(query, (host, port))

        # Receive response (may be large with many players)
        data, addr = sock.recvfrom(8192)
        ping_ms = int((time.perf_counter() - start_time) * 1000)

        # Response format: \xff\xff\xff\xffstatusResponse\n\key\value\key\value...\nplayer_info
        if not data.startswith(b'\xff\xff\xff\xff'):
            return ServerStatus(online=False, error='Invalid response format')

        response = data[4:].decode('latin-1', errors='replace')
        lines = response.split('\n')

        if len(lines) < 2:
            return ServerStatus(online=False, error='Incomplete response')

        # Parse server variables (second line, backslash-separated)
        server_vars = {}
        parts = lines[1].split('\\')
        for i in range(1, len(parts) - 1, 2):
            server_vars[parts[i].lower()] = parts[i + 1]

        # Parse players (remaining lines: "score ping name")
        players = []
        for line in lines[2:]:
            line = line.strip()
            if not line:
                continue

            # Format: score ping "name" or score ping name
            match = re.match(r'(-?\d+)\s+(\d+)\s+"?(.+?)"?\s*$', line)
            if match:
                name = match.group(3)
                # Remove Quake3 color codes (^0 through ^9, ^a through ^z)
                clean_name = re.sub(r'\^[0-9a-zA-Z]', '', name)
                players.append(Player(
                    name=clean_name.strip(),
                    score=int(match.group(1)),
                    ping=int(match.group(2))
                ))

        return ServerStatus(
            online=True,
            map_name=server_vars.get('mapname'),
            hostname=server_vars.get('sv_hostname'),
            player_count=len(players),
            max_players=int(server_vars.get('sv_maxclients', 0)),
            players=players,
            game_type=server_vars.get('g_gametype'),
            version=server_vars.get('version'),
            ping_ms=ping_ms,
        )

    except socket.timeout:
        logger.debug(f"Game server query timeout: {host}:{port}")
        return ServerStatus(online=False, error='Server not responding')
    except socket.gaierror as e:
        logger.warning(f"DNS resolution failed for {host}: {e}")
        return ServerStatus(online=False, error='DNS resolution failed')
    except Exception as e:
        logger.error(f"Game server query error: {e}")
        return ServerStatus(online=False, error=str(e))
    finally:
        sock.close()


# Convenience function for the configured server
_default_host = None
_default_port = 27960


def configure_default_server(host: str, port: int = 27960):
    """Set default server for queries"""
    global _default_host, _default_port
    _default_host = host
    _default_port = port


def query_default_server() -> ServerStatus:
    """Query the configured default server"""
    if not _default_host:
        return ServerStatus(online=False, error='No server configured')
    return query_game_server(_default_host, _default_port)
