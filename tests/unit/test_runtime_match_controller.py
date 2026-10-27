"""One-shot controller including native same-process two-half socket/capture proof."""

import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

from bot import runtime_import_attempt
from bot.community_stats_parser import C0RNP0RN3StatsParser
from bot.runtime_captured_import import import_captured_match
from shared import runtime_match_controller as controller_module
from shared.runtime_completion_manifest import publish_completion_manifest
from shared.runtime_match_controller import RuntimeMatchController
from shared.runtime_process_authority import reserve_process_epoch
from shared.runtime_process_pin import pin_process
from shared.runtime_stats_dispatch import prepare_stats_dispatch
from tests.unit import test_runtime_process_channel as channels
from tests.unit import test_runtime_process_pin as processes
from tests.unit.test_runtime_identity_writer_path import run_writer
from tests.unit.test_runtime_stats_dispatch import prepare, reference, setup_pair

listener = channels.listener
approved, child = processes.approved, processes.child


def roots(tmp_path):
    authority, spool, pair = setup_pair(tmp_path / 'rounds')
    host, capture = tmp_path / 'host', tmp_path / 'capture'
    host.mkdir(mode=0o700)
    capture.mkdir(mode=0o700)
    return authority, spool, pair, host, capture


def controller(all_roots, pin):
    authority, spool, pair, host, capture = all_roots
    epoch = reserve_process_epoch(host, pin, source_id=pair.first.source_id)
    return RuntimeMatchController(
        authority=authority, host_authority=host, producer_spool=spool, capture_root=capture,
        match_id=pair.first.match_id, source_id=pair.first.source_id,
        map_name='supply', pin=pin, epoch=epoch,
    )


@pytest.mark.parametrize('change', ['none', 'capture', 'spool', 'downgrade', 'missing', 'bytes'])
def test_separate_capture_root_handover_preserves_original_dispatch_binding(tmp_path, change):
    authority, spool, pair, _, capture = roots(tmp_path)
    first_dispatch = prepare(authority, spool, pair, capture_root=capture)
    first = run_writer('lua5.4', spool, pair, 1, dispatch=first_dispatch)
    # Existing actual Lua writer fixture makes bytes/manifest in producer spool.
    # Copy to the previously bound capture root for this dispatch-focused test.
    shutil.copytree(spool / first.generation, capture / first.generation)
    original = json.loads((authority / pair.first.round_id / 'dispatch.json').read_bytes())
    assert original['version'] == 2
    assert original['spool'] == [spool.stat().st_dev, spool.stat().st_ino]
    assert original['capture_root'] == [capture.stat().st_dev, capture.stat().st_ino]
    if change in ('capture', 'spool'):
        replacement = tmp_path / 'replacement'
        replacement.mkdir(mode=0o700)
        shutil.copytree(capture / first.generation, replacement / first.generation)
        if change == 'capture':
            capture = replacement
        else:
            spool = replacement
    elif change == 'downgrade':
        capture = None
    elif change == 'missing':
        path = capture / first.generation / (first.filename + '.complete.json')
        path.rename(path.with_suffix('.held'))
    elif change == 'bytes':
        (capture / first.generation / first.filename).write_bytes(b'corrupted')
    if change != 'none':
        with pytest.raises(ValueError):
            prepare(authority, spool, pair, 2, reference(first), capture_root=capture)
        assert not (authority / pair.second.round_id / '.writer-claimed').exists()
    else:
        second = prepare(authority, spool, pair, 2, reference(first), capture_root=capture)
        assert second.identity == pair.second
        record = json.loads((authority / pair.second.round_id / 'dispatch.json').read_bytes())
        assert record['capture_root'] == original['capture_root']
        assert record['spool'] == original['spool']
        assert record['previous']['sha256'] == first.sha256


def test_v1_dispatch_cannot_be_upgraded_by_copying_bytes(tmp_path):
    authority, spool, pair, _, capture = roots(tmp_path)
    ticket = prepare(authority, spool, pair)
    first = run_writer('lua5.4', spool, pair, 1, dispatch=ticket)
    shutil.copytree(spool / first.generation, capture / first.generation)
    with pytest.raises(ValueError, match='original dispatch'):
        prepare(authority, spool, pair, 2, reference(first), capture_root=capture)


@pytest.mark.parametrize('separate_capture', [False, True])
def test_dispatch_rejects_suffix_only_map_match(tmp_path, separate_capture):
    authority, spool, pair, _, capture = roots(tmp_path)
    capture_root = capture if separate_capture else None
    ticket = prepare(authority, spool, pair, capture_root=capture_root)
    first = run_writer('lua5.4', spool, pair, 1, dispatch=ticket)
    if separate_capture:
        shutil.copytree(spool / first.generation, capture / first.generation)
    directory = (capture_root or spool) / first.generation
    name = first.filename.replace('-supply-', '-evil-supply-')
    shutil.copy2(directory / first.filename, directory / name)
    publish_completion_manifest(directory, {'version': 1, 'filename': name,
                                'bytes': first.size, 'state': 'writer_closed'}, expected_sha256=first.sha256)
    with pytest.raises(ValueError, match='filename disagrees'):
        prepare(authority, spool, pair, 2, replace(reference(first), filename=name), capture_root=capture_root)
    assert not (authority / pair.second.round_id / '.writer-claimed').exists()


class Connection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


@pytest.mark.parametrize('phase', ['waiting', 'bootstrap'])
def test_interrupted_context_check_is_terminal(tmp_path, child, approved, monkeypatch, phase):
    class Interrupted(BaseException):
        pass

    with pin_process(child.pid, **approved) as pin:
        driver = controller(roots(tmp_path), pin)
        driver.prepare_half()
        incoming = Connection()

        def interrupted():
            raise Interrupted

        monkeypatch.setattr(driver, '_verify_context', interrupted)
        with pytest.raises(Interrupted):
            if phase == 'waiting':
                driver.check_waiting()
            else:
                driver.bootstrap(incoming)
        assert driver.state == 'failed'
        assert incoming.closed is (phase == 'bootstrap')
        with pytest.raises(ValueError, match='not awaiting'):
            driver.check_waiting()


def test_controller_orders_calls_and_failure_is_terminal(tmp_path, child, approved):
    all_roots = roots(tmp_path)
    with pin_process(child.pid, **approved) as pin:
        driver = controller(all_roots, pin)
        with pytest.raises(ValueError, match='Both successful captures'):
            driver.captured_match()
        wrong = Connection()
        with pytest.raises(ValueError, match='out of order'):
            driver.complete(wrong)
        assert wrong.closed and driver.state == 'ready'
        first = driver.prepare_half()
        assert first.identity.round_number == 1 and driver.state == 'awaiting_bootstrap'
        with pytest.raises(ValueError, match='out of order'):
            driver.prepare_half()
        bad = Connection()
        with pytest.raises(ValueError, match='Unix stream'):
            driver.bootstrap(bad)
        assert bad.closed and driver.state == 'failed'
        with pytest.raises(ValueError, match='out of order'):
            driver.prepare_half()
        # New controller cannot auto-recover a consumed dispatch either.
        authority, spool, pair, _, capture = all_roots
        with pytest.raises(FileExistsError):
            prepare_stats_dispatch(authority, spool, pair.first.match_id,
                                   expected_source=pair.first.source_id, map_name='supply',
                                   half=1, capture_root=capture)


def test_controller_detects_replaced_root_before_dispatch(tmp_path, child, approved):
    all_roots = roots(tmp_path)
    with pin_process(child.pid, **approved) as pin:
        driver = controller(all_roots, pin)
        capture = all_roots[-1]
        capture.rename(capture.with_name('capture-held'))
        capture.mkdir(mode=0o700)
        with pytest.raises(ValueError, match='root identity changed'):
            driver.prepare_half()
        assert driver.state == 'failed'
        assert not list(all_roots[0].glob('*/dispatch.json'))


def test_waiting_checks_do_not_advance_and_external_abort_is_terminal(tmp_path, child, approved):
    with pin_process(child.pid, **approved) as pin:
        driver = controller(roots(tmp_path), pin)
        with pytest.raises(ValueError, match='not awaiting'):
            driver.check_waiting()
        assert driver.state == 'ready'
        driver.prepare_half()
        driver.check_waiting()
        driver.check_waiting()
        assert driver.state == 'awaiting_bootstrap'
        driver.abort()
        driver.abort()
        assert driver.state == 'failed'
        with pytest.raises(ValueError, match='not awaiting'):
            driver.check_waiting()
        with pytest.raises(ValueError, match='out of order'):
            driver.prepare_half()


def test_waiting_rechecks_root_before_any_peer_arrives(tmp_path, child, approved):
    all_roots = roots(tmp_path)
    with pin_process(child.pid, **approved) as pin:
        driver = controller(all_roots, pin)
        driver.prepare_half()
        capture = all_roots[-1]
        capture.rename(capture.with_name('capture-held'))
        capture.mkdir(mode=0o700)
        with pytest.raises(ValueError, match='root identity changed'):
            driver.check_waiting()
        assert driver.state == 'failed'


def test_cross_user_controller_refuses_before_source_reservation(tmp_path, child, approved, monkeypatch):
    all_roots = roots(tmp_path)
    with pin_process(child.pid, **approved) as pin:
        authority, spool, pair, host, capture = all_roots
        epoch = reserve_process_epoch(host, pin, source_id=pair.first.source_id)
        monkeypatch.setattr(controller_module.os, 'getuid', lambda: pin.identity.uid + 1)
        with pytest.raises(ValueError, match='approved producer UID'):
            RuntimeMatchController(
                authority=authority, host_authority=host, producer_spool=spool, capture_root=capture,
                match_id=pair.first.match_id, source_id=pair.first.source_id,
                map_name='supply', pin=pin, epoch=epoch,
            )
        assert list(spool.iterdir()) == []
        assert not list(authority.glob('*/dispatch.json'))


def test_concurrent_call_closes_only_its_socket_without_consuming_dispatch(tmp_path, child, approved, monkeypatch):
    all_roots = roots(tmp_path)
    entered, release = Event(), Event()
    original = controller_module.prepare_stats_dispatch

    def slow_dispatch(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(controller_module, 'prepare_stats_dispatch', slow_dispatch)
    with pin_process(child.pid, **approved) as pin:
        driver = controller(all_roots, pin)
        socket = Connection()
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(driver.prepare_half)
            try:
                assert entered.wait(5)
                with pytest.raises(ValueError, match='concurrent'):
                    driver.bootstrap(socket)
                with pytest.raises(ValueError, match='concurrent'):
                    driver.check_waiting()
                with pytest.raises(ValueError, match='concurrent'):
                    driver.abort()
                assert socket.closed and driver.state == 'busy'
                assert not list(all_roots[0].glob('*/dispatch.json'))
            finally:
                release.set()
            assert pending.result(timeout=5).identity.round_number == 1
        assert driver.state == 'awaiting_bootstrap'


def test_socket_close_failure_is_terminal_too(tmp_path, child, approved, monkeypatch):
    class BrokenClose(Connection):
        def close(self):
            self.closed = True
            raise OSError('fixture close failure')

    with pin_process(child.pid, **approved) as pin:
        driver = controller(roots(tmp_path), pin)
        driver.prepare_half()
        monkeypatch.setattr(controller_module, 'bootstrap_round', lambda *a, **kw: object())
        with pytest.raises(OSError, match='fixture close failure'):
            driver.bootstrap(BrokenClose())
        assert driver.state == 'failed'


PEER = r'''
import json, os, socket, sys
from pathlib import Path
print('READY', flush=True)
for half in (1, 2):
    command = sys.stdin.readline()
    if not command: break
    config = json.loads(command)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(5)
        sock.connect(sys.argv[1])
        sock.sendall(f'slomix_init_v1|{half * 1000}|supply|{half}\n'.encode())
        with sock.makefile('rb') as stream:
            context = stream.readline().decode().strip()
            wire = stream.readline().decode().strip()
        fields = wire.split('|')
        assert len(fields) == 7 and fields[5] == config['generation']
        assert context.startswith('slomix_bootstrap_context_v1|')
        sock.sendall((wire.replace('slomix_stats_bind_v1', 'slomix_stats_ack_v1', 1) + '\n').encode())
    if sys.stdin.readline().strip() != 'finish': break
    name = f'2026-10-10-12000{half}-supply-round-{half}.txt'
    header = '\\'.join(['host', 'supply', '1', str(half), '2', '1', '20:00', '10:00', '600000', fields[4]])
    raw = (header + f'\n12345678\\Player\\1\\1\\1 {half} {half} {half} {half} {half}\n').encode()
    with (Path(config['directory']) / name).open('xb') as output:
        output.write(raw)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(5)
        sock.connect(sys.argv[1])
        sock.sendall(f'slomix_stats_closed_v1|{fields[5]}|{name}|{len(raw)}\n'.encode())
    print('CLOSED ' + name, flush=True)
    if sys.stdin.readline().strip() != 'next': break
'''


@pytest.mark.parametrize('fail_after_capture', [False, True])
def test_native_same_process_two_half_controller(tmp_path, listener, monkeypatch, fail_after_capture):
    server, path = listener
    all_roots = roots(tmp_path)
    executable = Path(sys.executable).resolve()
    with subprocess.Popen([str(executable), '-c', PEER, str(path)], stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, umask=0o077) as child:
        try:
            assert child.stdout.readline().strip() == 'READY'
            with pin_process(child.pid, **channels.approval(executable)) as pin:
                driver = controller(all_roots, pin)
                results = []
                if fail_after_capture:
                    real_capture = controller_module.capture_closed_stats

                    def interrupted(*args, **kwargs):
                        real_capture(*args, **kwargs)
                        raise OSError('fixture failure after durable capture')

                    monkeypatch.setattr(controller_module, 'capture_closed_stats', interrupted)
                for half in (1, 2):
                    dispatch = driver.prepare_half()
                    assert dispatch.identity.round_number == half
                    directory = all_roots[1] / dispatch.generation
                    child.stdin.write(json.dumps({'generation': dispatch.generation, 'directory': str(directory)}) + '\n')
                    child.stdin.flush()
                    connection, _ = server.accept()
                    driver.bootstrap(connection)
                    child.stdin.write('finish\n')
                    child.stdin.flush()
                    connection, _ = server.accept()
                    if fail_after_capture:
                        with pytest.raises(OSError, match='after durable capture'):
                            driver.complete(connection)
                        assert driver.state == 'failed'
                        assert len(list(all_roots[-1].glob('*/*.complete.json'))) == 1
                        assert not (all_roots[0] / all_roots[2].second.round_id / 'dispatch.json').exists()
                        with pytest.raises(ValueError, match='out of order'):
                            driver.prepare_half()
                        with pytest.raises(ValueError, match='Both successful captures'):
                            driver.captured_match()
                        break
                    captured = driver.complete(connection)
                    results.append(captured)
                    source = directory / captured.reference.filename
                    copy = captured.directory / source.name
                    assert source.read_bytes() == copy.read_bytes()
                    digest = hashlib.sha256(copy.read_bytes()).hexdigest()
                    assert digest == captured.reference.sha256
                    assert subprocess.check_output(['sha256sum', str(source)], text=True).split()[0] == digest
                    assert not list(directory.glob('*.complete.json'))
                    assert driver.state == ('ready' if half == 1 else 'complete')
                    if half == 1:
                        with pytest.raises(ValueError, match='Both successful captures'):
                            driver.captured_match()
                    child.stdin.write('next\n')
                    child.stdin.flush()
                if not fail_after_capture:
                    with pytest.raises(ValueError, match='out of order'):
                        driver.prepare_half()
                    assert results[0].reference.generation != results[1].reference.generation
                    record = json.loads((all_roots[0] / all_roots[2].second.round_id / 'dispatch.json').read_bytes())
                    assert record['previous']['sha256'] == results[0].reference.sha256
        finally:
            child.stdin.close()
            child.wait(timeout=10)
        assert child.returncode == 0, child.stderr.read()
        assert len(child.stdout.read().splitlines()) == (1 if fail_after_capture else 2)
    if not fail_after_capture:
        # Export survives source exit/pin close, but only for this successful
        # in-memory controller. Actual parser/receipts/lock/batch below; SQL stubbed.
        handoff = driver.captured_match()
        assert handoff.first_identity == all_roots[2].first
        assert handoff.second_identity == all_roots[2].second
        seen = []

        async def process(path, *, input_source, runtime_binding):
            parsed = input_source.parse(None)
            assert parsed['success']
            assert runtime_binding.identity == (handoff.first_identity, handoff.second_identity)[len(seen)]
            seen.append(parsed)
            return True, 'fixture canonical boundary'

        @asynccontextmanager
        async def session(*args, **kwargs):
            assert kwargs['journal_enabled'] is True
            yield SimpleNamespace(parser=C0RNP0RN3StatsParser(), process_file=process)

        monkeypatch.setattr(runtime_import_attempt, 'open_import_session', session)
        from tests.unit.test_runtime_import_attempt import database
        lock = tmp_path / 'import-lock'
        lock.mkdir(mode=0o700)
        outcomes = asyncio.run(import_captured_match(database(), handoff, lock_directory=lock))
        assert len(outcomes) == 2 and all(item[0] is True for item in outcomes)
        assert [parsed['round_num'] for parsed in seen] == [1, 2]
        assert seen[1]['r1_filename'] == handoff.first.reference.filename
        assert driver.state == 'complete' and driver.captured_match() == handoff
        # Exercise the independent CLI process using these actual controller
        # references, not another completed_pair fixture. Expectations come
        # from the independently allocated pair, never parsed payload headers.
        from tests.integration.test_runtime_team_cli_pg import import_command
        pair = all_roots[2]
        command = import_command(
            {'host': '/tmp/slomix-runtime-pg-offline', 'port': 5432},
            'fixture_database', 'fixture_role', handoff.first.root, lock,
            (handoff.first.reference, handoff.second.reference),
        )
        command.extend(['--require-declared-identity', '--expected-round-identities',
                        pair.first.encode(), pair.second.encode()])
        before = {p: p.read_bytes() for p in handoff.first.root.rglob('*') if p.is_file()}
        for defect in ('none', 'hash', 'identity'):
            args = command[3:].copy()
            if defect == 'hash':
                args[args.index('--r1') + 4] = '0' * 64
            elif defect == 'identity':
                args[-2:] = [replace(identity, source_id='other-source').encode()
                             for identity in (pair.first, pair.second)]
            result = subprocess.run(
                [sys.executable, '-c', CAPTURED_CLI, *args],
                cwd=tmp_path, capture_output=True, text=True, timeout=20,
                env={'PATH': os.environ.get('PATH', ''),
                     'PYTHONPATH': str(Path(__file__).resolve().parents[2]),
                     'EXPECTED_PAIR': json.dumps([pair.first.encode(), pair.second.encode()]),
                     'EXPECTED_PARSES': '2' if defect == 'none' else '0'},
            )
            assert result.returncode == (0 if defect == 'none' else 1), result.stderr
            assert result.stderr == ''
            report = json.loads(result.stdout)
            assert report['source_acknowledged'] is False
            assert report['status'] == ('completed' if defect == 'none' else 'failed')
            assert all(p.read_bytes() == raw for p, raw in before.items())
        print('CAPTURED CLI: actual child parser/bindings; independent pair; deferred teams; '
              'bad hash/identity refused; source retained; no database transport')
    print('NATIVE CONTROLLER: ' + ('post-capture failure retained files and refused R2' if fail_after_capture else
          'same pinned process -> authenticated R1/R2 captures -> exclusive sealed parser + canonical bindings') +
          '; source bytes retained; no game engine; SQL boundary stubbed')


# The production CLI, batch, lock, sealed snapshots, parser and bindings run in
# this child. Only the database session/canonical write boundary is replaced.
CAPTURED_CLI = r'''
import asyncio, importlib.abc, json, os, sys
from contextlib import asynccontextmanager
from types import SimpleNamespace
class NoDatabase(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {'psycopg', 'psycopg2', 'dotenv'}:
            raise AssertionError('Forbidden database/setup import')
sys.meta_path.insert(0, NoDatabase())
def deny_transport(event, args):
    if event == 'socket.connect':
        raise AssertionError('Forbidden database/network connection')
sys.addaudithook(deny_transport)
from bot import runtime_import_attempt as attempt
from bot.community_stats_parser import C0RNP0RN3StatsParser
from bot.runtime_import_cli import main, parser
args = parser().parse_args(sys.argv[1:])
assert args.require_declared_identity and args.defer_team_assignment
assert args.journal == 'enabled'
expected = json.loads(os.environ['EXPECTED_PAIR'])
seen = []
async def process(path, *, input_source, runtime_binding):
    assert runtime_binding.identity.encode() == expected[len(seen)]
    parsed = input_source.parse(None)
    assert parsed['success']
    assert parsed['round_num'] == len(seen) + 1
    if seen:
        assert parsed['r1_filename'] == args.r1[1]
    seen.append(parsed)
    return True, 'offline canonical boundary'
@asynccontextmanager
async def session(*unused, **options):
    assert options['journal_enabled'] is True
    assert options['defer_team_assignment'] is True
    yield SimpleNamespace(parser=C0RNP0RN3StatsParser(), process_file=process)
attempt.open_import_session = session
code = main(sys.argv[1:])
assert len(seen) == int(os.environ['EXPECTED_PARSES'])
raise SystemExit(code)
'''
