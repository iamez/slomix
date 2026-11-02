"""Pinned external importer configuration; no ambient settings or env mutation.

The expected tuple is supplied independently by the operator. Agreement records
intent, not physical database identity or exclusive writer ownership. Read one
private canonical dotenv file, verify its exact bytes and refuse shadowing.
"""

import hashlib
import io
import os
import re
import stat
from pathlib import Path

from shared.runtime_environment import external_config_path, refuse_config_overrides
from shared.runtime_import_pool import TcpImportDatabaseConfig

ROOT = Path(__file__).resolve().parents[1]
MAX_CONFIG_BYTES = 1024 * 1024


def _read_private_config(path, expected_digest):
    if not isinstance(expected_digest, str) or re.fullmatch('[0-9a-f]{64}', expected_digest) is None:
        raise ValueError('Explicit lowercase configuration SHA256 required')
    selected = external_config_path(str(path), ROOT)
    # O_NONBLOCK prevents a concurrently replaced FIFO from blocking open. The
    # digest binds the actual FD bytes; fstat rechecks privacy after path checks.
    fd = os.open(selected, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as source:
        before = os.fstat(source.fileno())
        if (not stat.S_ISREG(before.st_mode) or before.st_mode & 0o077
                or before.st_uid not in {0, os.geteuid()}):
            raise ValueError('Private regular configuration owned by the operator or root required')
        raw = source.read(MAX_CONFIG_BYTES + 1)
        after = os.fstat(source.fileno())
        current = selected.stat(follow_symlinks=False)
    attributes = ('st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
    if (len(raw) > MAX_CONFIG_BYTES
            or any(getattr(before, key) != getattr(after, key)
                   or getattr(after, key) != getattr(current, key) for key in attributes)):
        raise ValueError('Configuration changed or exceeds size limit')
    if hashlib.sha256(raw).hexdigest() != expected_digest:
        raise ValueError('Configuration differs from approved SHA256')
    return raw


def load_import_database(path, *, expected_digest, expected_target, environment=None):
    """Validate before creating any pool; never print values or discover files.

    Full bot env files are permitted, but only explicit PostgreSQL keys select
    this connection. PostgreSQL mode ignores the legacy DB_PATH and always uses
    fixed importer pool budgets, independent of legacy MIN/MAX pool settings.
    TLS requests, interpolation, duplicate keys and unknown DB/PG aliases fail.
    """
    from dotenv import dotenv_values
    from dotenv.parser import parse_stream

    if (type(expected_target) is not tuple or len(expected_target) != 4
            or any(not isinstance(expected_target[index], str) for index in (0, 2, 3))
            or type(expected_target[1]) is not int):
        raise ValueError('Independent host, port, database and user tuple required')
    raw = _read_private_config(path, expected_digest)
    try:
        content = raw.decode('utf-8')
    except UnicodeError:
        raise ValueError('Invalid external dotenv encoding') from None
    seen = set()
    for binding in parse_stream(io.StringIO(content)):
        if binding.error or (binding.key is not None and binding.key in seen):
            raise ValueError('Invalid or duplicate external dotenv configuration')
        if binding.key is not None:
            seen.add(binding.key)
    values = dict(dotenv_values(stream=io.StringIO(content), interpolate=False))
    refuse_config_overrides(values, os.environ if environment is None else environment)
    names = ('POSTGRES_HOST', 'POSTGRES_PORT', 'POSTGRES_DATABASE', 'POSTGRES_USER', 'POSTGRES_PASSWORD')
    if any(not isinstance(values.get(key), str) or not values[key] for key in names):
        raise ValueError('Explicit PostgreSQL target and password required')
    if values.get('DATABASE_TYPE', 'postgresql') != 'postgresql':
        raise ValueError('Explicit PostgreSQL configuration required')
    if values.get('POSTGRES_SSL_MODE', 'disable') != 'disable':
        raise ValueError('This explicit private TCP importer does not implement TLS')
    non_target_keys = ('DATABASE_TYPE', 'DB_PATH', 'POSTGRES_MIN_POOL', 'POSTGRES_MAX_POOL', 'POSTGRES_SSL_MODE')
    if any(key not in (*names, *non_target_keys) and key.startswith(('POSTGRES_', 'DB_', 'PG', 'DATABASE_'))
           for key in values):
        raise ValueError('Ambiguous database configuration is not supported')
    if any('${' in values[key] for key in names):
        raise ValueError('Interpolated PostgreSQL configuration is not supported')
    try:
        port = int(values['POSTGRES_PORT'])
    except ValueError:
        raise ValueError('Invalid explicit PostgreSQL port') from None
    host, database, user = (values[key] for key in ('POSTGRES_HOST', 'POSTGRES_DATABASE', 'POSTGRES_USER'))
    if (host, port, database, user) != expected_target:
        raise ValueError('Configuration target differs from independent operator expectation')
    return TcpImportDatabaseConfig(host, database, user, values['POSTGRES_PASSWORD'], port=port)
