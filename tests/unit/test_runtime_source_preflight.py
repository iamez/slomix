"""Real sealed source inspection with no database, writer lock or mutation."""
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from bot import runtime_source_preflight as preflight
from bot.runtime_completed_import import CompletedRoundInput
from shared.runtime_completion_manifest import record_completion_once
from shared.runtime_round_identity import RoundIdentity
from shared.runtime_source_reservation import reserve_source_generation
from shared.runtime_spool import publish_stats_file


@pytest.fixture
def sources(tmp_path):
    tmp_path.chmod(0o700)
    inputs, identities = [], []
    for half in (1, 2):
        identity = RoundIdentity('fixture', 'a' * 32, str(half) * 32, half, '1' * 32)
        name = f'2026-10-16-120000-supply-round-{half}.txt'
        raw = (f'x\\supply\\x\\{half}\\2\\1\\20:00\\10:00\\0\\{identity.encode()}\n'
               'PRIVATE PLAYER DATA\n').encode()
        digest = hashlib.sha256(raw).hexdigest()
        directory = reserve_source_generation(tmp_path, str(half) * 32)
        publish_stats_file(directory, name, [raw], expected_size=len(raw), expected_sha256=digest)
        record_completion_once(directory, dict(version=1, filename=name, bytes=len(raw),
                                               state='writer_closed'), expected_sha256=digest)
        inputs.append(CompletedRoundInput(tmp_path, str(half) * 32, name, len(raw), digest))
        identities.append(identity)
    return tuple(inputs), tuple(identities)


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('bound', [False, True])
def test_real_inspection_keeps_sources_and_closes_fds(sources, bound):
    inputs, identities = sources
    root = inputs[0].root
    before, descriptors = snapshot(root), set(os.listdir('/proc/self/fd'))
    result = preflight.inspect_sources(*inputs, expected_identities=identities if bound else None)
    assert result['verified_inputs'] == 2
    assert result['declared_identity'] == ('matched' if bound else 'unmeasured')
    assert not any(result[k] for k in ('parser_checked', 'database_checked', 'activation_ready',
                                      'source_acknowledged', 'writer_exclusion_verified'))
    assert snapshot(root) == before
    assert set(os.listdir('/proc/self/fd')) == descriptors
    assert not list(root.rglob('.import-writer.lock'))


@pytest.mark.parametrize('bad', ['digest', 'missing_receipt', 'payload', 'identity', 'map', 'order'])
def test_bad_pair_refused_without_side_effects(sources, bad):
    inputs, identities = sources
    first, second = inputs
    target = second.root / second.generation / second.filename
    if bad == 'digest':
        second = replace(second, sha256='0' * 64)
    elif bad == 'missing_receipt':
        target.with_name(target.name + '.complete.json').unlink()
    elif bad == 'payload':
        target.write_bytes(b'PRIVATE CORRUPTED DATA')
    elif bad == 'identity':
        identities = (identities[0], replace(identities[1], round_id='b' * 32))
    elif bad == 'map':
        second = replace(second, filename=second.filename.replace('supply', 'oasis'))
    else:
        first, second = second, first
    before, descriptors = snapshot(first.root), set(os.listdir('/proc/self/fd'))
    with pytest.raises((ValueError, OSError)):
        preflight.inspect_sources(first, second, expected_identities=identities)
    assert snapshot(first.root) == before
    assert set(os.listdir('/proc/self/fd')) == descriptors


def test_cli_real_process_never_connects_or_prints_source(sources, tmp_path):
    inputs, identities = sources
    args = ['--spool', str(inputs[0].root)]
    for half, item in enumerate(inputs, 1):
        args += [f'--r{half}', item.generation, item.filename, str(item.size), item.sha256]
    args += ['--expected-round-identities', *(identity.encode() for identity in identities)]
    # The fresh process can use files/memfds, but any network connection is a test failure.
    command = '''import runpy,sys
def deny(event, args):
    if event in ('socket.connect', 'socket.getaddrinfo'):
        raise AssertionError('Network forbidden in source inspection')
sys.addaudithook(deny)
sys.argv = ['runtime_source_preflight', *sys.argv[1:]]
runpy.run_module('bot.runtime_source_preflight', run_name='__main__')
'''
    before = snapshot(inputs[0].root)
    result = subprocess.run([sys.executable, '-B', '-c', command, *args],
                            cwd=Path(__file__).resolve().parents[2], capture_output=True,
                            text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['verified_inputs'] == 2
    assert 'PRIVATE' not in result.stdout + result.stderr
    assert snapshot(inputs[0].root) == before
    args[args.index('--r2') + 4] = '0' * 64
    result = subprocess.run([sys.executable, '-B', '-c', command, *args],
                            cwd=Path(__file__).resolve().parents[2], capture_output=True,
                            text=True, timeout=20)
    assert result.returncode == 1
    assert json.loads(result.stdout)['status'] == 'failed'
    assert 'PRIVATE' not in result.stdout + result.stderr
    assert snapshot(inputs[0].root) == before
