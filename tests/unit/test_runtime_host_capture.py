"""Authenticated capture failure boundaries; native Lua composition is tested separately."""

import hashlib
import os
from contextlib import contextmanager
from dataclasses import replace

import pytest

from shared import runtime_host_capture as capture
from shared import runtime_host_completion as completion
from shared.runtime_manifest_reader import inspect_completion_manifest
from tests.unit import test_runtime_host_completion as fixtures
from tests.unit.test_runtime_host_bootstrap import issued

approved, child, pin = fixtures.approved, fixtures.child, fixtures.pin
channels, prepared, ready = fixtures.channels, fixtures.prepared, fixtures.ready


@pytest.fixture
def case(ready, pin, tmp_path):
    host, epoch, accepted, state = ready
    source, target = tmp_path / 'source', tmp_path / 'captures'
    source.mkdir(mode=0o700)
    target.mkdir(mode=0o700)
    identity = accepted.delivery.dispatch.identity
    raw = ('host\\supply\\1\\1\\0\\0\\0\\0\\0\\' + identity.encode() + '\nbody\n').encode()
    filename = fixtures.NAME
    path = source / filename
    path.write_bytes(raw)
    path.chmod(0o600)

    def receipt(payload=raw, name=filename):
        value = completion.StatsCompletion(accepted.delivery.dispatch.generation, name, len(payload))
        state['wire'] = value.encode()
        return fixtures.receive(ready, pin)

    def run(value):
        return capture.capture_closed_stats(
            host, pin, epoch, accepted=accepted, completed=value,
            source_directory=source, capture_root=target,
        )

    return host, source, target, path, raw, receipt, run


def test_capture_seals_publishes_and_refuses_duplicate_without_changing_source(case):
    _, _, target, source, raw, receipt, run = case
    completed = receipt()
    before = source.stat(), source.read_bytes()
    result = run(completed)
    assert result.root == target and result.reference.generation == completed.generation
    assert result.reference.size == len(raw) and result.reference.sha256 == hashlib.sha256(raw).hexdigest()
    assert (result.directory / source.name).read_bytes() == raw
    assert inspect_completion_manifest(result.directory, source.name).status == 'match'
    source_after = source.stat()
    assert (before[0].st_ino, before[0].st_mtime_ns, before[1]) == (
        source_after.st_ino, source_after.st_mtime_ns, source.read_bytes(),
    )
    captured_before = {p.name: (p.stat().st_ino, p.read_bytes()) for p in result.directory.iterdir()}
    with pytest.raises(FileExistsError):
        run(completed)
    assert captured_before == {p.name: (p.stat().st_ino, p.read_bytes()) for p in result.directory.iterdir()}


@pytest.mark.parametrize('fault', ['identity', 'map', 'half', 'legacy', 'utf8', 'long', 'unterminated'])
def test_header_must_prove_exact_dispatch(case, fault):
    _, _, target, source, raw, receipt, run = case
    if fault == 'identity':
        raw = raw.replace(b'slomix_round_v1:', b'slomix_round_v1:other-')
    elif fault == 'map':
        raw = raw.replace(b'supply', b'radar')
    elif fault == 'half':
        raw = raw.replace(b'\\1\\1\\', b'\\1\\2\\')
    elif fault == 'legacy':
        raw = b'host\\supply\\1\\1\\0\\0\\0\\0\\0\n'
    elif fault == 'utf8':
        raw = b'\xff' + raw
    elif fault == 'long':
        raw = b'x' * 4097 + raw
    else:
        raw = raw.splitlines()[0]
    source.write_bytes(raw)
    completed = receipt(raw)
    with pytest.raises(ValueError):
        run(completed)
    stranded = target / completed.generation
    assert stranded.is_dir() and list(stranded.iterdir()) == []
    with pytest.raises(FileExistsError):
        run(completed)


@pytest.mark.parametrize('fault', ['symlink', 'fifo', 'hardlink', 'size', 'writable', 'directory'])
def test_unsafe_source_cannot_publish_or_block_on_fifo(case, fault):
    _, source_root, target, source, raw, receipt, run = case
    completed = receipt()
    if fault in ('symlink', 'fifo', 'directory'):
        held = source.with_suffix('.held')
        source.rename(held)
        if fault == 'symlink':
            source.symlink_to(held)
        elif fault == 'fifo':
            os.mkfifo(source)
        else:
            source.mkdir()
    elif fault == 'hardlink':
        os.link(source, source_root / 'alias')
    elif fault == 'size':
        source.write_bytes(raw + b'extra')
    else:
        source.chmod(0o660)
    with pytest.raises((OSError, ValueError)):
        run(completed)
    assert not list(target.rglob('*.complete.json'))


@pytest.mark.parametrize('record', ['stats-writer-closed.txt', 'bootstrap-accepted.txt', 'bootstrap-issued.json'])
def test_changed_authority_refuses_before_reservation(case, record):
    host, _, target, _, _, receipt, run = case
    completed = receipt()
    issued(host).with_name(record).write_bytes(b'changed\n')
    with pytest.raises(ValueError):
        run(completed)
    assert list(target.iterdir()) == []


def test_receipt_object_alone_does_not_authorize_capture(case, ready):
    _, _, target, _, raw, _, run = case
    completed = completion.StatsCompletion(ready[2].delivery.dispatch.generation, fixtures.NAME, len(raw))
    with pytest.raises(ValueError, match='record missing or changed'):
        run(completed)
    assert list(target.iterdir()) == []


def test_receipt_size_cannot_be_substituted(case):
    _, _, target, _, _, receipt, run = case
    completed = receipt()
    with pytest.raises(ValueError, match='record missing or changed'):
        run(replace(completed, size=completed.size + 1))
    assert list(target.iterdir()) == []


@pytest.mark.parametrize('fault', ['rewrite', 'rename'])
def test_source_change_between_hash_and_sealing_refuses(case, monkeypatch, fault):
    _, _, target, source, raw, receipt, run = case
    completed = receipt()
    original = capture.sealed_stats_snapshot

    @contextmanager
    def snapshot(fd, **kwargs):
        if fault == 'rewrite':
            source.write_bytes(raw.replace(b'body', b'evil'))
        else:
            source.rename(source.with_suffix('.held'))
            source.write_bytes(raw)
        with original(fd, **kwargs) as sealed:
            yield sealed

    monkeypatch.setattr(capture, 'sealed_stats_snapshot', snapshot)
    with pytest.raises(ValueError):
        run(completed)
    assert not list(target.rglob('*.complete.json'))


@pytest.mark.parametrize('stage', [2, 3, 4])
def test_lost_authentication_never_returns_success_even_after_publication(case, monkeypatch, stage):
    host, _, target, _, _, receipt, run = case
    completed = receipt()
    original, calls = capture.verify_stats_completion, 0

    def verify(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == stage:
            issued(host).with_name('bootstrap-accepted.txt').write_bytes(b'changed\n')
        return original(*args, **kwargs)

    monkeypatch.setattr(capture, 'verify_stats_completion', verify)
    with pytest.raises(ValueError, match='durable bootstrap acceptance'):
        run(completed)
    directory = target / completed.generation
    assert (directory / completed.filename).exists() == (stage >= 3)
    assert (directory / (completed.filename + '.complete.json')).exists() == (stage == 4)


@pytest.mark.parametrize('fail_at', range(1, 7))
def test_each_fsync_failure_retains_generation_and_forbids_retry(case, monkeypatch, fail_at):
    _, _, target, _, _, receipt, run = case
    completed = receipt()
    original, calls = os.fsync, 0

    def sync(fd):
        nonlocal calls
        calls += 1
        if calls == fail_at:
            raise OSError('fixture capture fsync failure')
        return original(fd)

    monkeypatch.setattr(os, 'fsync', sync)
    with pytest.raises(OSError, match='fixture capture fsync failure'):
        run(completed)
    assert (target / completed.generation).is_dir()
    monkeypatch.setattr(os, 'fsync', original)
    with pytest.raises(FileExistsError):
        run(completed)


def test_overlap_cannot_publish_beside_mutable_source(case, ready, pin):
    host, source_root, _, _, _, receipt, _ = case
    completed = receipt()
    with pytest.raises(ValueError, match='must be separate'):
        capture.capture_closed_stats(
            host, pin, ready[1], accepted=ready[2], completed=completed,
            source_directory=source_root, capture_root=source_root,
        )
    assert not list(source_root.glob('*.complete.json'))


def test_invalid_calendar_is_not_a_trusted_filename(case):
    _, _, target, source, raw, receipt, run = case
    name = source.name.replace('2026-09-25', '2026-02-30')
    source.rename(source.with_name(name))
    completed = receipt(raw, name)
    with pytest.raises(ValueError):
        run(completed)
    assert list(target.iterdir()) == []
