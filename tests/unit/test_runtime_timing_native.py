"""Real process credentials, bootstrap exchange and timing receipt on Linux."""
import socket
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from shared.runtime_host_bootstrap import bootstrap_round
from shared.runtime_host_timing_completion import receive_timing_completion, verify_timing_completion
from shared.runtime_process_authority import reserve_process_epoch
from shared.runtime_process_pin import pin_process
from shared.runtime_timing_capture import capture_closed_timing
from tests.unit.test_runtime_host_bootstrap import issued
from tests.unit.test_runtime_process_channel import approval, listener  # noqa: F401
from tests.unit.test_runtime_stats_dispatch import prepare, setup_pair

CHILD = r'''
import socket,sys
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);s.connect(sys.argv[1])
s.sendall(b'slomix_init_v1|1234|supply|1\n')
f=s.makefile('rb')
context=f.readline();delivery=f.readline().decode().strip()
s.sendall((delivery.replace('slomix_stats_bind_v1','slomix_stats_ack_v1',1)+'\n').encode())
f.close();s.close()
if sys.stdin.readline().strip() != 'timing': sys.exit(0)
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);s.connect(sys.argv[1])
with open(sys.argv[3], 'wb') as output: output.write(b'{}' + b' ' * 40)
s.sendall(('slomix_timing_closed_v1|'+sys.argv[2]+'|round.json|42\n').encode())
print('SENT',flush=True)
sys.stdin.readline()
s.close()
'''


@pytest.mark.parametrize('fault', ['none', 'bootstrap', 'epoch', 'other-process'])
def test_native_timing_peer_and_durable_context(tmp_path, listener, fault):  # noqa: F811
    server, path = listener
    authority, spool, pair = setup_pair(tmp_path / 'rounds')
    dispatch = prepare(authority, spool, pair)
    host = tmp_path / 'host'
    host.mkdir(mode=0o700)
    source, capture = tmp_path / 'source', tmp_path / 'timing-capture'
    source.mkdir(mode=0o700)
    capture.mkdir(mode=0o700)
    executable = Path(sys.executable).resolve()
    with subprocess.Popen([str(executable), '-c', CHILD, str(path), dispatch.generation, str(source / 'round.json')],
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True) as proc:
        try:
            connection, _ = server.accept()
            with connection, pin_process(proc.pid, **approval(executable)) as pin:
                epoch = reserve_process_epoch(host, pin, source_id=pair.first.source_id)
                accepted = bootstrap_round(connection, host, pin, epoch, dispatch=dispatch)
                if fault == 'bootstrap':
                    issued(host).with_name('bootstrap-accepted.txt').write_text('changed\n')
                if fault == 'epoch':
                    epoch = replace(epoch, process_epoch='f' * 32)
                peer = None
                if fault == 'other-process':
                    peer = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    peer.connect(str(path))
                    peer.sendall(('slomix_timing_closed_v1|' + dispatch.generation
                                  + '|round.json|42\n').encode())
                else:
                    proc.stdin.write('timing\n')
                    proc.stdin.flush()
                done, _ = server.accept()
                if peer is not None:
                    peer.close()
                with done:
                    if fault == 'none':
                        result = receive_timing_completion(done, host, pin, epoch,
                            accepted=accepted, expected_filename='round.json')
                        verify_timing_completion(host, pin, epoch, accepted=accepted,
                            completed=result, expected_filename='round.json')
                        assert list(host.rglob('timing-writer-closed.txt'))
                        captured = capture_closed_timing(host, pin, epoch, accepted=accepted,
                            completed=result, expected_filename='round.json',
                            source_directory=source, capture_root=capture)
                        assert (capture / captured.generation / captured.filename).read_bytes() == (
                            source / 'round.json').read_bytes()
                    else:
                        with pytest.raises(ValueError):
                            receive_timing_completion(done, host, pin, epoch,
                                accepted=accepted, expected_filename='round.json')
                        assert not list(host.rglob('timing-writer-closed.txt'))
                assert not list(host.rglob('stats-writer-closed.txt'))
        finally:
            out, err = proc.communicate('\n', timeout=5)
            assert proc.returncode == 0, out + err
