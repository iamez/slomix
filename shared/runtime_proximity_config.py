"""Explicit local DEV configuration, import-safe for spawned child processes."""

import os
import re
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path

from bot.core.database_adapter import PostgreSQLAdapter
from shared.runtime_proximity_admission import _scope
from shared.runtime_proximity_resources import proximity_database_resources


@dataclass(frozen=True)
class ProximityProcessConfig:
    root: Path
    source_id: str
    gametimes_dir: Path
    host: str
    port: int
    database: str
    user: str
    schema: str
    password: str = field(repr=False)
    # Policy opt-in only; trusted source provisioning and handover stay separate.
    allow_declared_mapping: bool = False

    def __post_init__(self):
        if type(self.allow_declared_mapping) is not bool:
            raise ValueError('Explicit declared mapping policy required')

    @classmethod
    def from_environment(cls):
        if (os.getenv('BOT_ENVIRONMENT') != 'dev'
                or os.getenv('RUNTIME_PROXIMITY_DEV_HANDOVER_CONFIRMED') != 'true'):
            raise ValueError('Explicit DEV environment and exclusive handover confirmation required')
        names = ('RUNTIME_PROXIMITY_ROOT', 'RUNTIME_PROXIMITY_SOURCE_ID', 'RUNTIME_PROXIMITY_GAMETIMES_DIR',
                 'POSTGRES_HOST', 'POSTGRES_PORT', 'POSTGRES_DATABASE', 'POSTGRES_USER',
                 'RUNTIME_PROXIMITY_DB_SCHEMA')
        if any(not os.getenv(name, '').strip() for name in names):
            raise ValueError('Explicit proximity paths/source and PostgreSQL configuration required')
        root, source, gametimes, host, port, database, user, schema = (os.environ[name] for name in names)
        root, gametimes = Path(root), Path(gametimes)
        _scope(root / ('0' * 32), source, '0' * 32)
        if not gametimes.is_absolute():
            raise ValueError('Explicit absolute gametimes directory required')
        # No DNS/remote/multi-host fallback. Existing adapter does not parse IPv6
        # literals correctly, so this entrypoint deliberately refuses ::1 too.
        if host != '127.0.0.1' and (not host.startswith('/') or ':' in host or ',' in host):
            raise ValueError('Local Unix socket or IPv4 loopback required')
        port = int(port)
        if not 1 <= port <= 65535:
            raise ValueError('Invalid PostgreSQL port')
        if not re.fullmatch(r'[a-z_][a-z0-9_]{0,62}', schema):
            raise ValueError('Invalid explicit PostgreSQL schema')
        password = os.environ.get('POSTGRES_PASSWORD', '')
        if host == '127.0.0.1' and not password:
            raise ValueError('Explicit TCP password required')
        policy = os.getenv('RUNTIME_PROXIMITY_DECLARED_MAPPING_ENABLED', 'false')
        if policy not in {'true', 'false'}:
            raise ValueError('Explicit declared mapping policy must be true or false')
        return cls(root, source, gametimes, host, port, database, user, schema, password,
                   allow_declared_mapping=policy == 'true')

    def pool_options(self):
        return dict(host=self.host, port=self.port, database=self.database, user=self.user,
                    password=self.password, min_size=0, max_size=2, timeout=5, command_timeout=10,
                    server_settings={'search_path': f'"{self.schema}"', 'statement_timeout': '10000',
                                     'application_name': 'slomix-runtime-proximity-dev'})

    def resource_factory(self, pool):
        adapter = PostgreSQLAdapter(self.host, self.port, self.database, self.user, self.password)
        adapter.pool = pool
        return partial(proximity_database_resources, adapter)
