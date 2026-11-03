"""Authenticate timing-close claims against independently accepted host context.

The expected basename must come from trusted host provisioning, never the received
notice or timing JSON. A receipt attests writer close only, not captured bytes.
"""
from shared.runtime_host_bootstrap import _write_once
from shared.runtime_host_completion import _bootstrap_verifier
from shared.runtime_manifest_reader import _read_private_manifest_bytes
from shared.runtime_process_channel import process_channel
from shared.runtime_timing_completion import TimingCompletion, TimingFilenamePolicy, decode_timing_completion

RECEIPT = 'timing-writer-closed.txt'


def _require_expected(completed, accepted, expected_filename):
    if not isinstance(completed, TimingCompletion):
        raise ValueError('Explicit timing completion required')
    completed.encode()
    generation = accepted.delivery.dispatch.generation
    if isinstance(expected_filename, TimingFilenamePolicy):
        expected_filename.require(completed.filename, accepted.delivery.dispatch)
        if completed.generation != generation:
            raise ValueError('Timing completion disagrees with host generation')
        return
    # Validate the host expectation independently, including basename safety.
    TimingCompletion(generation, expected_filename, 1).encode()
    if completed.generation != generation or completed.filename != expected_filename:
        raise ValueError('Timing completion disagrees with host expectation')


def receive_timing_completion(connection, authority, pin, expected, *, accepted,
                              expected_filename, timeout=5):
    """Own one credentialed channel, validate epoch/bootstrap, persist once."""
    with process_channel(connection, pin, timeout=timeout) as channel:
        key, directory, verify = _bootstrap_verifier(authority, pin, expected, accepted)
        verify()
        completed = decode_timing_completion(channel.receive_line())
        _require_expected(completed, accepted, expected_filename)
        verify()
        payload = (completed.encode() + '\n').encode('ascii')
        _write_once(directory, key, RECEIPT, payload)
        verify()
        if _read_private_manifest_bytes(directory, RECEIPT) != payload:
            raise ValueError('Timing completion record missing or changed')
        return completed


def verify_timing_completion(authority, pin, expected, *, accepted, completed,
                             expected_filename):
    """Revalidate persisted authentication before a separate capture operation."""
    _, directory, verify = _bootstrap_verifier(authority, pin, expected, accepted)
    _require_expected(completed, accepted, expected_filename)
    verify()
    if _read_private_manifest_bytes(directory, RECEIPT) != (completed.encode() + '\n').encode('ascii'):
        raise ValueError('Timing completion record missing or changed')
    verify()
