"""Protocol isolation and real capture/receipt recovery across process exit."""

import hashlib
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from shared.runtime_capture import capture_proximity_stream
from shared.runtime_completion_manifest import (
    publish_completion_manifest,
    publish_proximity_completion_manifest,
    record_completion_once,
    record_proximity_completion_once,
)
from shared.runtime_manifest_reader import (
    inspect_completion_manifest,
    inspect_proximity_completion_manifest,
)

STATS = '2026-10-05-120000-oasis-round-1.txt'
PROXIMITY = STATS.replace('.txt', '_engagements.txt')
PAYLOAD = b'synthetic engagement transport bytes\n'
HASH = hashlib.sha256(PAYLOAD).hexdigest()


def receipt(name):
    return {'version': 1, 'filename': name, 'bytes': len(PAYLOAD), 'state': 'writer_closed'}


@pytest.mark.parametrize('publish,record,inspect,name', [
    (publish_completion_manifest, record_completion_once, inspect_completion_manifest, PROXIMITY),
    (publish_proximity_completion_manifest, record_proximity_completion_once,
     inspect_proximity_completion_manifest, STATS),
])
def test_wrong_protocol_rejected_before_filesystem_io(tmp_path, monkeypatch, publish, record, inspect, name):
    """No receipt API may infer or silently widen the caller's input protocol."""
    def forbidden(*args, **kwargs):
        raise AssertionError('Wrong protocol reached filesystem I/O')

    with monkeypatch.context() as patch:
        patch.setattr(os, 'open', forbidden)
        for operation in (publish, record):
            with pytest.raises(ValueError, match='filename'):
                operation(tmp_path, receipt(name), expected_sha256=HASH)
        with pytest.raises(ValueError, match='filename'):
            inspect(tmp_path, name)
    assert list(tmp_path.iterdir()) == []


def test_capture_manifest_recovers_after_process_exit(tmp_path):
    """Real socket -> durable local receipt -> fresh interpreter read-only recovery.

    Synthetic payload, no SSH/DB or service. Independent sha256sum verifies the
    size/hash recorded by the reader; inode/mode/bytes comparisons prove no retry
    replacement. A completion manifest is not a canonical parser import receipt.
    """
    tmp_path.chmod(0o700)
    receiver, sender = socket.socketpair()
    with receiver, sender:
        sender.sendall(PAYLOAD)
        sender.shutdown(socket.SHUT_WR)
        path = capture_proximity_stream(
            SimpleNamespace(read=receiver.recv, settimeout=receiver.settimeout),
            tmp_path, PROXIMITY, expected_size=len(PAYLOAD), expected_sha256=HASH,
            chunk_size=5,
        )
    assert inspect_proximity_completion_manifest(tmp_path, PROXIMITY).status == 'missing_manifest'
    assert record_proximity_completion_once(tmp_path, receipt(PROXIMITY), expected_sha256=HASH) == 'published'
    manifest = tmp_path / (PROXIMITY + '.complete.json')
    assert json.loads(manifest.read_text()) == {**receipt(PROXIMITY), 'sha256': HASH}
    before = {p.name: (p.stat().st_ino, p.stat().st_mode, p.read_bytes()) for p in tmp_path.iterdir()}
    script = '''
import json, sys
from dataclasses import asdict
from pathlib import Path
from shared.runtime_manifest_reader import inspect_proximity_completion_manifest
from shared.runtime_completion_manifest import record_proximity_completion_once
directory, name, digest, size = sys.argv[1:]
completion = dict(version=1, filename=name, bytes=int(size), state='writer_closed')
observed = inspect_proximity_completion_manifest(Path(directory), name)
retry = record_proximity_completion_once(Path(directory), completion, expected_sha256=digest)
assert 'discord' not in sys.modules and 'website.backend.main' not in sys.modules
print(json.dumps(dict(observed=asdict(observed), retry=retry)))
'''
    results = []
    for _ in range(2):
        process = subprocess.run(
            [sys.executable, '-c', script, str(tmp_path), PROXIMITY, HASH, str(len(PAYLOAD))],
            cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True,
            timeout=10, check=True,
        )
        results.append(json.loads(process.stdout))
    independent_hash = subprocess.check_output(['sha256sum', str(path)], text=True).split()[0]
    assert results[0] == results[1] == {
        'observed': {'status': 'match', 'filename': PROXIMITY,
                     'size': path.stat().st_size, 'sha256': independent_hash},
        'retry': 'content_present',
    }
    assert independent_hash == HASH and path.stat().st_size == len(PAYLOAD)
    assert {p.name: (p.stat().st_ino, p.stat().st_mode, p.read_bytes()) for p in tmp_path.iterdir()} == before
    print('Proximity manifest runtime proof: socket capture, published receipt, two fresh '
          'process recoveries = match/content_present; independent sha256sum agrees; '
          'no Discord/website import, no database acknowledgement')
