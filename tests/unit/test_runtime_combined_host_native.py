"""Whole Lua producers -> real credentials/sockets -> durable two-half capture."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from shared.runtime_process_authority import reserve_process_epoch
from shared.runtime_process_pin import pin_process
from shared.runtime_timing_completion import TimingFilenamePolicy
from shared.runtime_timing_controller import RuntimeTimingController
from shared.runtime_timing_listener import serve_timing_match
from tests.unit.test_runtime_match_controller import roots
from tests.unit.test_runtime_process_channel import approval, listener  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]


def test_whole_lua_vm_bootstrap_and_both_writers_through_native_controller(tmp_path, listener):  # noqa: F811
    _, socket_path = listener
    socket_path = socket_path.with_name('combined')
    timing_paths = {half: socket_path.with_name('t' + str(half)) for half in (1, 2)}
    authority, spool, pair, host, capture = roots(tmp_path)
    timing_capture = tmp_path / 'timing-capture'
    timing_capture.mkdir(mode=0o700)
    executable = Path(shutil.which('lua5.4')).resolve()
    command = [str(executable), str(ROOT / 'tests/lua/runtime_combined_source_harness.lua'),
               str(ROOT), str(spool), 'native', str(socket_path), str(timing_paths[1]),
               str(timing_paths[2]), pair.first.source_id, pair.first.match_id,
               pair.first.round_id, pair.second.round_id]
    with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, umask=0o077) as peer:
        try:
            assert peer.stdout.readline().strip() == 'READY'
            with pin_process(peer.pid, **approval(executable)) as pin:
                epoch = reserve_process_epoch(host, pin, source_id=pair.first.source_id)
                driver = RuntimeTimingController(authority=authority, host_authority=host,
                    producer_spool=spool, capture_root=capture, timing_capture_root=timing_capture,
                    timing_filenames={half: TimingFilenamePolicy('supply', half) for half in (1, 2)},
                    match_id=pair.first.match_id, source_id=pair.first.source_id,
                    map_name='supply', pin=pin, epoch=epoch)

                def release(command):
                    peer.stdin.write(command + '\n')
                    peer.stdin.flush()

                prepare, bootstrap = driver.prepare_half, driver.bootstrap

                def prepared():
                    dispatch = prepare()
                    if dispatch.identity.round_number == 2:
                        release('next')
                    return dispatch

                def bound(connection, **options):
                    accepted = bootstrap(connection, **options)
                    release('finish')
                    return accepted

                driver.prepare_half, driver.bootstrap = prepared, bound
                result = serve_timing_match(driver, socket_path, timing_socket_paths=timing_paths,
                    initial_readiness_wait=5, bootstrap_wait=5, completion_wait=5,
                    timing_wait=5, exchange_timeout=3, on_ready=lambda: release('start'))
                assert result.timing_status == {1: 'captured', 2: 'captured'}
                handoff = result.timing_match
                assert handoff is not None
                handoff.verify()
                assert handoff.stats.first_identity == pair.first
                assert handoff.stats.second_identity == pair.second
                for item in handoff.timings:
                    raw = (item.root / item.generation / item.filename).read_bytes()
                    assert hashlib.sha256(raw).hexdigest() == item.sha256
                    data = json.loads(raw)
                    assert data['meta']['runtime_identity'] == item.identity.encode()
                    assert data['meta']['actual_duration_seconds'] == 610
                release('done')
        finally:
            stdout, stderr = peer.communicate(timeout=5)
            assert peer.returncode == 0, stdout + stderr
    assert 'half 1 closed' in stdout and 'half 2 closed' in stdout
    print('NATIVE WHOLE LUA: same pinned PID, two fresh leases, stats and timing captured for both halves')
