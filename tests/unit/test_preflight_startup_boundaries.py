"""Release startup refusals do not open non-regular/unbounded configuration."""
import hashlib
import json
import os
import subprocess
import sys

import pytest

from tests.unit.test_release_operator_tool_boundaries import payload


def arguments(root, path):
    return [str(root / 'scripts/dev_schema_preflight.py'), '--env-file', str(path),
            '--expected-host', 'fixture', '--expected-port', '5432', '--expected-database', 'fixture',
            '--expected-user', 'fixture', '--expected-env-sha256', 'a' * 64]


@pytest.mark.parametrize('dependency', ['asyncpg', 'dotenv'])
def test_native_missing_preflight_dependency_is_redacted(tmp_path, dependency):
    root = payload(tmp_path, 'dev_schema_preflight')
    # Native import hook models a trusted interpreter missing one distribution.
    # It neither imports a deployed payload nor uses PYTHONPATH shadow modules.
    code = '''
import builtins,runpy,sys
original = builtins.__import__
blocked = sys.argv[1]
def importing(name,*args,**kwargs):
    if name == blocked:
        raise ModuleNotFoundError('PRIVATE_INTERPRETER_PATH')
    return original(name,*args,**kwargs)
builtins.__import__ = importing
sys.argv = sys.argv[2:]
runpy.run_path(sys.argv[0], run_name='__main__')
'''
    result = subprocess.run([sys.executable, '-I', '-B', '-c', code, dependency,
                             *arguments(root, tmp_path / 'unused')],
                            env={'PATH': '/usr/bin:/bin'}, capture_output=True, text=True, timeout=5)
    assert result.returncode == 1 and result.stderr == ''
    assert json.loads(result.stdout) == {'clean': False, 'error': 'Preflight dependencies are unavailable'}


@pytest.mark.parametrize('kind', ['fifo', 'device', 'oversized', 'wrong-digest'])
def test_native_preflight_bounds_and_validates_before_hashing(tmp_path, kind):
    root = payload(tmp_path, 'dev_schema_preflight')
    path = tmp_path / 'approved.env'
    if kind == 'fifo':
        os.mkfifo(path, 0o600)
    elif kind == 'device':
        path = type(path)('/dev/zero')
    elif kind == 'oversized':
        # Sparse file: the guard must read at most its documented 1 MiB + 1.
        with path.open('wb') as stream:
            stream.truncate(2**35)
        path.chmod(0o600)
    else:
        path.write_text('DATABASE_TYPE=postgresql\n')
        path.chmod(0o600)
    argv = arguments(root, path)
    if kind == 'oversized':
        # Digest intentionally wrong; both checks must terminate with bounded IO.
        argv[-1] = hashlib.sha256(b'unapproved').hexdigest()
    result = subprocess.run([sys.executable, '-I', '-B', *argv],
                            env={'PATH': '/usr/bin:/bin', 'SLOMIX_ENV_FILE': str(path)},
                            capture_output=True, text=True, timeout=4)
    assert result.returncode == 1 and result.stderr == ''
    assert json.loads(result.stdout) == {'clean': False, 'error': 'Preflight could not complete safely'}
