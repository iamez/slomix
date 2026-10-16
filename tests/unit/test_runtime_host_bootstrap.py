"""Connected native Lua/kernel/disk proof plus deterministic host failure injection."""

import json
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from shared import runtime_host_bootstrap as bootstrap
from shared.runtime_host_bootstrap import _write_once as write_once
from shared.runtime_process_authority import reserve_process_epoch
from shared.runtime_process_pin import pin_process
from shared.runtime_round_identity import stats_header_identity
from shared.runtime_stats_delivery import decode_stats_delivery
from tests.unit import test_runtime_process_pin as process_fixtures
from tests.unit.test_runtime_process_authority import pin as pin_fixture
from tests.unit.test_runtime_process_channel import approval
from tests.unit.test_runtime_process_channel import listener as listener_fixture
from tests.unit.test_runtime_stats_dispatch import prepare, setup_pair

ROOT = Path(__file__).resolve().parents[2]
pin, listener = pin_fixture, listener_fixture
approved, child = process_fixtures.approved, process_fixtures.child


@pytest.fixture
def prepared(tmp_path, pin):
    authority, spool, pair = setup_pair(tmp_path / 'rounds')
    dispatch = prepare(authority, spool, pair)
    host = tmp_path / 'host'
    host.mkdir(mode=0o700)
    epoch = reserve_process_epoch(host, pin, source_id=pair.first.source_id)
    return host, epoch, dispatch


class Channel:
    """Fault injection only; native credentialed composition is below."""
    def __init__(self, fault=None):
        self.sent, self.reads, self.closed, self.fault = [], 0, False, fault

    def send_line(self, value):
        self.sent.append(value)
        if self.fault == 'send':
            raise OSError('fixture send failure')

    def receive_line(self):
        self.reads += 1
        if self.reads == 1:
            return 'slomix_init_v1|1234|supply|1'
        if self.fault == 'ack':
            return 'not-the-ack'
        if self.fault == 'eof':
            raise EOFError('fixture EOF')
        return decode_stats_delivery(self.sent[-1]).acknowledgement()


@pytest.fixture
def channels(monkeypatch):
    values = SimpleNamespace(fault=None, opened=[])

    @contextmanager
    def channel(*args, **kwargs):
        value = Channel(values.fault)
        values.opened.append(value)
        try:
            yield value
        finally:
            value.closed = True

    monkeypatch.setattr(bootstrap, 'process_channel', channel)
    return values


def issued(host):
    paths = list(host.glob('*/bootstrap-issued.json'))
    assert len(paths) == 1
    return paths[0]


def test_durable_issue_before_send_and_exact_acceptance(prepared, pin, channels, monkeypatch):
    host, epoch, dispatch = prepared
    original_send = Channel.send_line

    def send(value, message):
        record = json.loads(issued(host).read_bytes())
        assert message == (record['context'] if not value.sent else record['delivery'])
        return original_send(value, message)

    monkeypatch.setattr(Channel, 'send_line', send)
    result = bootstrap.bootstrap_round(None, host, pin, epoch, dispatch=dispatch)
    path = issued(host)
    record = json.loads(path.read_bytes())
    assert record['delivery'] == result.delivery.encode()
    assert record['observation'] == result.observation.encode()
    assert result.delivery.lifecycle_epoch != epoch.process_epoch
    assert result.delivery.lifecycle_epoch not in ('2'*32, dispatch.generation)
    assert (host / result.delivery.lifecycle_epoch).is_dir()
    assert path.with_name('bootstrap-accepted.txt').read_text() == result.delivery.acknowledgement() + '\n'
    assert channels.opened[0].closed and len(channels.opened[0].sent) == 2
    before = {p: p.read_bytes() for p in host.rglob('*') if p.is_file()}
    with pytest.raises(FileExistsError):
        bootstrap.bootstrap_round(None, host, pin, epoch, dispatch=dispatch)
    assert channels.opened[-1].sent == []
    assert before == {p: p.read_bytes() for p in host.rglob('*') if p.is_file()}


@pytest.mark.parametrize('fault', ['send', 'ack', 'eof'])
def test_ambiguous_exchange_keeps_issue_and_forbids_reissue(prepared, pin, channels, fault):
    host, epoch, dispatch = prepared
    channels.fault = fault
    with pytest.raises((OSError, ValueError, EOFError)):
        bootstrap.bootstrap_round(None, host, pin, epoch, dispatch=dispatch)
    assert not issued(host).with_name('bootstrap-accepted.txt').exists()
    channels.fault = None
    with pytest.raises(FileExistsError):
        bootstrap.bootstrap_round(None, host, pin, epoch, dispatch=dispatch)
    assert channels.opened[-1].sent == [] and all(c.closed for c in channels.opened)


@pytest.mark.parametrize('fail_at', range(1, 9))
def test_every_fsync_failure_is_terminal_and_retains_claim(prepared, pin, channels, monkeypatch, fail_at):
    host, epoch, dispatch = prepared
    original, count = os.fsync, 0

    def sync(fd):
        nonlocal count
        count += 1
        if count == fail_at:
            raise OSError('fixture sync failure')
        original(fd)

    monkeypatch.setattr(os, 'fsync', sync)
    with pytest.raises(OSError, match='fixture sync'):
        bootstrap.bootstrap_round(None, host, pin, epoch, dispatch=dispatch)
    assert count == fail_at
    if fail_at <= 6:
        assert channels.opened[-1].sent == []
    monkeypatch.setattr(os, 'fsync', original)
    with pytest.raises(FileExistsError):
        bootstrap.bootstrap_round(None, host, pin, epoch, dispatch=dispatch)


@pytest.mark.parametrize('change', ['generation', 'map'])
def test_claim_does_not_key_on_mutable_dispatch_attributes(prepared, pin, channels, change):
    host, epoch, dispatch = prepared
    bootstrap.bootstrap_round(None, host, pin, epoch, dispatch=dispatch)
    changed = replace(dispatch, generation='f'*32) if change == 'generation' else replace(dispatch, map_name='radar')
    if change == 'map':
        # Matching source observation still cannot mint a second claim.
        original = Channel.receive_line

        def receive(channel):
            return original(channel).replace('|supply|', '|radar|')

        # Fixture scoped monkeypatch supplied explicitly below instead of class mutation.
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(Channel, 'receive_line', receive)
            with pytest.raises(FileExistsError):
                bootstrap.bootstrap_round(None, host, pin, epoch, dispatch=changed)
    else:
        with pytest.raises(FileExistsError):
            bootstrap.bootstrap_round(None, host, pin, epoch, dispatch=changed)
    assert channels.opened[-1].sent == []


@pytest.mark.parametrize('when', ['before-send', 'after-ack'])
def test_issued_record_drift_is_not_accepted(prepared, pin, channels, monkeypatch, when):
    host, epoch, dispatch = prepared
    original = write_once

    def write(directory, key, name, payload):
        original(directory, key, name, payload)
        if (when == 'before-send' and name == 'bootstrap-issued.json'
                or when == 'after-ack' and name == 'bootstrap-accepted.txt'):
            (directory / 'bootstrap-issued.json').write_bytes(b'{}\n')

    monkeypatch.setattr(bootstrap, '_write_once', write)
    with pytest.raises(ValueError, match='issue record'):
        bootstrap.bootstrap_round(None, host, pin, epoch, dispatch=dispatch)
    if when == 'before-send':
        assert channels.opened[-1].sent == []


def test_short_issue_write_sends_nothing_and_strands_claim(prepared, pin, channels, monkeypatch):
    host, epoch, dispatch = prepared
    original = os.write

    def short(fd, payload):
        return original(fd, payload[:1])

    monkeypatch.setattr(os, 'write', short)
    with pytest.raises(OSError, match='Incomplete bootstrap record'):
        bootstrap.bootstrap_round(None, host, pin, epoch, dispatch=dispatch)
    assert issued(host).read_bytes() == b'{'
    assert channels.opened[-1].sent == []
    with pytest.raises(FileExistsError):
        bootstrap.bootstrap_round(None, host, pin, epoch, dispatch=dispatch)


def test_parallel_controllers_issue_exactly_once(prepared, pin, channels):
    host, epoch, dispatch = prepared

    def run(_):
        try:
            return bootstrap.bootstrap_round(None, host, pin, epoch, dispatch=dispatch)
        except FileExistsError:
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        values = list(executor.map(run, range(6)))
    assert sum(value is not None for value in values) == 1
    assert len(list(host.glob('*/bootstrap-issued.json'))) == 1
    assert len(list(host.glob('*/bootstrap-accepted.txt'))) == 1
    assert sum(len(channel.sent) for channel in channels.opened) == 2


@pytest.mark.parametrize('lua', ['lua5.1', 'lua5.4'])
@pytest.mark.parametrize('fault', ['host', 'host-stale', 'host-shutdown', 'host-source', 'host-ack-error',
                                 'hooks-frame', 'hooks-shutdown', 'hooks-warmup'])
def test_native_bootstrap_to_whole_writer(tmp_path, listener, lua, fault):
    server, path = listener
    executable = Path(shutil.which(lua)).resolve()
    authority, spool, pair = setup_pair(tmp_path / 'rounds')
    dispatch = prepare(authority, spool, pair)
    directory = spool / dispatch.generation
    host = tmp_path / 'host'
    host.mkdir(mode=0o700)
    args = [str(executable), str(ROOT / 'tests/lua/runtime_identity_writer_harness.lua'), str(ROOT),
            str(directory), pair.first.source_id, pair.first.match_id, pair.first.round_id,
            pair.second.round_id, '1', dispatch.generation, 'bound-' + fault,
            ('@hooks:' if fault.startswith('hooks-') else '@bootstrap:') + str(path),
            'required-entrypoint', '1234']
    accepted = fault in ('host', 'hooks-frame', 'hooks-shutdown', 'hooks-warmup')
    with subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, umask=0o077) as child:
        try:
            connection, _ = server.accept()
            with connection, pin_process(child.pid, **approval(executable)) as pin:
                epoch = reserve_process_epoch(host, pin, source_id=pair.first.source_id)
                if accepted:
                    result = bootstrap.bootstrap_round(connection, host, pin, epoch, dispatch=dispatch)
                    assert result.delivery.lifecycle_epoch != epoch.process_epoch
                else:
                    with pytest.raises((EOFError, OSError, ValueError)):
                        bootstrap.bootstrap_round(connection, host, pin, epoch, dispatch=dispatch)
            stdout, stderr = child.communicate('finish\n', timeout=10)
        finally:
            if not child.stdin.closed:
                child.stdin.close()
            child.wait(timeout=10)
    assert child.returncode == 0, stdout + stderr
    record_path = issued(host)
    assert record_path.with_name('bootstrap-accepted.txt').exists() == accepted
    records = [json.loads(line[8:]) for line in stdout.splitlines() if line.startswith('receipt ')]
    if not accepted and fault != 'host-ack-error':
        assert records == [] and not list(directory.glob('*.txt'))
        assert ('invalid bootstrap context' if fault == 'host-source' else 'InitGame lease invalidated') in stdout
        return
    assert len(records) == 1
    receipt = records[0]['completion']
    output = directory / receipt['filename']
    raw = output.read_bytes()
    assert len(raw) == output.stat().st_size == receipt['bytes']
    assert stats_header_identity(raw.splitlines(keepends=True)[0].decode()) == pair.first
    if fault == 'host-ack-error':
        assert 'HOST BOOTSTRAP unconfirmed' in stdout
    elif fault.startswith('hooks-'):
        assert 'ENGINE HOOK BOOTSTRAP accepted' in stdout
        assert 'ENGINE HOOK FULL WRITER completed opens=1' in stdout
        if fault == 'hooks-warmup':
            assert 'WARMUP HELD UNTIL FRESH INIT' in stdout
    else:
        assert 'HOST BOOTSTRAP accepted' in stdout
    print(f'BOOTSTRAP {lua} {fault}: real socket/pin -> durable random epoch -> source lease -> actual stats; '
          'host accepted record only after exact ACK; ET API synthetic, no live engine')


@pytest.mark.parametrize('lua', ['lua5.1', 'lua5.4'])
@pytest.mark.parametrize('fault', ['ok', 'pending', 'cancel', 'open-error', 'hello-error', 'bad-context',
    'wrong-process', 'wrong-life', 'wrong-source', 'malformed', 'time', 'map', 'half',
    'callback-error', 'bad-return', 'ack-error'])
def test_source_state_machine_is_one_shot_and_exact(tmp_path, lua, fault):
    from shared.runtime_stats_delivery import StatsDelivery
    authority, spool, pair = setup_pair(tmp_path)
    dispatch = prepare(authority, spool, pair)
    delivery = StatsDelivery('1'*32, '2'*32, 1234, dispatch)
    context = 'slomix_bootstrap_context_v1|' + '1'*32 + '|' + '2'*32 + '|' + pair.first.source_id
    result = subprocess.run([lua, str(ROOT / 'tests/lua/runtime_host_bootstrap_harness.lua'),
                             str(ROOT), fault, delivery.encode(), context],
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stdout + result.stderr
