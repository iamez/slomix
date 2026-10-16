"""Host reservations and bounded reads on a real private filesystem."""

import json
import os
import stat
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

from shared.runtime_identity_allocation import allocate_round_pair, inspect_round_pair

ROOT = Path(__file__).resolve().parents[2]


def test_allocation_reserves_distinct_ids_and_roundtrips(tmp_path):
    pair = allocate_round_pair(tmp_path, 'fixture')
    assert inspect_round_pair(tmp_path, pair.first.match_id, expected_source='fixture') == pair
    ids = {pair.first.match_id, pair.first.round_id, pair.second.round_id}
    assert {path.name for path in tmp_path.iterdir()} == ids
    assert len(ids) == 3
    assert pair.second.first_round_id == pair.first.round_id
    assert pair.first.match_id == pair.second.match_id
    print('ALLOCATION: 3 exclusive directories, one matching persistent R1/R2 record')


def test_simultaneous_allocations_have_disjoint_ids(tmp_path):
    with ThreadPoolExecutor(max_workers=2) as workers:
        pairs = list(workers.map(lambda _: allocate_round_pair(tmp_path, 'fixture'), range(8)))
    ids = [value for pair in pairs for value in
           (pair.first.match_id, pair.first.round_id, pair.second.round_id)]
    assert len(set(ids)) == len(ids) == len(list(tmp_path.iterdir())) == 24


def test_record_sync_order_and_fresh_process_inspection(tmp_path, monkeypatch):
    observed = []
    original = os.fsync
    def sync(fd):
        info = os.fstat(fd)
        observed.append((stat.S_ISDIR(info.st_mode), info.st_ino))
        original(fd)
    monkeypatch.setattr(os, 'fsync', sync)
    pair = allocate_round_pair(tmp_path, 'fixture')
    record = tmp_path / pair.first.match_id / 'round-pair.json'
    assert len(observed) == 8  # three child+parent reservations, record+directory
    assert observed[-2:] == [(False, record.stat().st_ino), (True, record.parent.stat().st_ino)]
    result = subprocess.run([sys.executable, '-c',
        'from pathlib import Path; import sys; '
        'from shared.runtime_identity_allocation import inspect_round_pair; '
        'print(inspect_round_pair(Path(sys.argv[1]),sys.argv[2],expected_source="fixture").first.encode())',
        str(tmp_path), pair.first.match_id], cwd=ROOT, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == pair.first.encode()


def test_collision_never_reuses_existing_reservation(tmp_path, monkeypatch):
    tokens = ['a' * 32, 'b' * 32, 'c' * 32]
    sequence = iter(tokens * 2)
    monkeypatch.setattr('shared.runtime_identity_allocation.uuid.uuid4', lambda: SimpleNamespace(hex=next(sequence)))
    first = allocate_round_pair(tmp_path, 'fixture')
    original = (tmp_path / tokens[0] / 'round-pair.json').read_bytes()
    with pytest.raises(FileExistsError):
        allocate_round_pair(tmp_path, 'fixture')
    assert (tmp_path / tokens[0] / 'round-pair.json').read_bytes() == original
    assert inspect_round_pair(tmp_path, tokens[0], expected_source='fixture') == first


def test_duplicate_tokens_fail_before_reservation(tmp_path, monkeypatch):
    monkeypatch.setattr('shared.runtime_identity_allocation.uuid.uuid4', lambda: SimpleNamespace(hex='a' * 32))
    with pytest.raises(ValueError, match='first-half dependency'):
        allocate_round_pair(tmp_path, 'fixture')
    assert not list(tmp_path.iterdir())


def test_match_token_cannot_equal_half_token(tmp_path, monkeypatch):
    sequence = iter(['a' * 32, 'a' * 32, 'b' * 32])
    monkeypatch.setattr('shared.runtime_identity_allocation.uuid.uuid4', lambda: SimpleNamespace(hex=next(sequence)))
    with pytest.raises(ValueError, match='distinct'):
        allocate_round_pair(tmp_path, 'fixture')
    assert not list(tmp_path.iterdir())


def test_authority_root_cannot_be_shared_or_symlinked(tmp_path):
    tmp_path.chmod(0o755)
    with pytest.raises(ValueError, match='0700'):
        allocate_round_pair(tmp_path, 'fixture')
    assert not list(tmp_path.iterdir())
    tmp_path.chmod(0o700)
    link = tmp_path / 'link'
    link.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(OSError):
        allocate_round_pair(link, 'fixture')
    assert list(tmp_path.iterdir()) == [link]


@pytest.mark.parametrize('source', ['', 'UPPER', 'a/b', None])
def test_invalid_source_has_no_filesystem_effect(tmp_path, source):
    with pytest.raises(ValueError):
        allocate_round_pair(tmp_path, source)
    assert not list(tmp_path.iterdir())


def test_identity_inspection_requires_expected_namespace(tmp_path):
    pair = allocate_round_pair(tmp_path, 'fixture')
    with pytest.raises(ValueError, match='namespace'):
        inspect_round_pair(tmp_path, pair.first.match_id, expected_source='another')


@pytest.mark.parametrize('failure', ['short-write', 'fsync'])
def test_failed_persistence_retains_reserved_ids(tmp_path, monkeypatch, failure):
    real_write, real_sync = os.write, os.fsync
    sequence = iter(['a' * 32, 'b' * 32, 'c' * 32])
    monkeypatch.setattr('shared.runtime_identity_allocation.uuid.uuid4', lambda: SimpleNamespace(hex=next(sequence)))
    def write(fd, content):
        return real_write(fd, content[:5] if failure == 'short-write' else content)
    def sync(fd):
        if failure == 'fsync' and not os.path.isdir(f'/proc/self/fd/{fd}'):
            raise OSError('fixture record fsync failure')
        real_sync(fd)
    monkeypatch.setattr(os, 'write', write)
    monkeypatch.setattr(os, 'fsync', sync)
    with pytest.raises(OSError, match='Incomplete|fixture'):
        allocate_round_pair(tmp_path, 'fixture')
    assert {path.name for path in tmp_path.iterdir()} == {'a' * 32, 'b' * 32, 'c' * 32}
    assert (tmp_path / ('a' * 32) / 'round-pair.json').exists()
    if failure == 'short-write':
        with pytest.raises(ValueError):
            inspect_round_pair(tmp_path, 'a' * 32, expected_source='fixture')


@pytest.mark.parametrize('damage', ['duplicate-key', 'bool-version', 'mismatched-pair', 'namespace'])
def test_invalid_record_is_not_repaired_or_accepted(tmp_path, damage):
    pair = allocate_round_pair(tmp_path, 'fixture')
    path = tmp_path / pair.first.match_id / 'round-pair.json'
    data = json.loads(path.read_bytes())
    if damage == 'duplicate-key':
        raw = path.read_text().replace('"version":1', '"version":1,"version":1')
    else:
        if damage == 'bool-version':
            data['version'] = True
        elif damage == 'mismatched-pair':
            data['second'] = data['second'].replace(pair.first.match_id, 'd' * 32)
        else:
            data['first'] = data['first'].replace('fixture', 'other')
            data['second'] = data['second'].replace('fixture', 'other')
        raw = json.dumps(data)
    path.write_text(raw)
    with pytest.raises(ValueError):
        inspect_round_pair(tmp_path, pair.first.match_id, expected_source='fixture')
    assert path.read_text() == raw
