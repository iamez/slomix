"""Authenticate one writer-close notice; retain it durably, never infer payload durability.

Independent process/dispatch expectations and prior durable bootstrap acceptance
are mandatory. A fresh short-lived channel is a separate completion exchange,
not a bootstrap retry. No listener, game service, polling scheduler or recovery.
"""

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from shared.runtime_host_bootstrap import BootstrapAcceptance, _claim_key, _write_once
from shared.runtime_manifest_reader import _read_private_manifest_bytes
from shared.runtime_process_authority import ProcessEpoch, verify_process_epoch
from shared.runtime_process_channel import process_channel
from shared.runtime_process_pin import ProcessPin
from shared.runtime_source_reservation import _open_root
from shared.runtime_spool import _NAME

PREFIX = 'slomix_stats_closed_v1'


@dataclass(frozen=True)
class StatsCompletion:
    generation: str
    filename: str
    size: int

    def encode(self):
        if not isinstance(self.generation, str) or re.fullmatch('[0-9a-f]{32}', self.generation) is None:
            raise ValueError('Invalid completion generation')
        if (not isinstance(self.filename, str) or len(self.filename) > 240
                or _NAME.fullmatch(self.filename) is None or '..' in self.filename):
            raise ValueError('Invalid stats completion filename')
        if type(self.size) is not int or not 1 <= self.size <= 8 * 1024 * 1024:
            raise ValueError('Invalid stats completion size')
        return '|'.join((PREFIX, self.generation, self.filename, str(self.size)))

    def receipt(self):
        self.encode()
        return {'version': 1, 'filename': self.filename, 'bytes': self.size, 'state': 'writer_closed'}


def decode_stats_completion(wire: str) -> StatsCompletion:
    if not isinstance(wire, str) or len(wire) > 512:
        raise ValueError('Invalid completion wire')
    fields = wire.split('|')
    if (len(fields) != 4 or fields[0] != PREFIX
            or re.fullmatch('[1-9][0-9]{0,6}', fields[3]) is None):
        raise ValueError('Invalid completion wire')
    result = StatsCompletion(fields[1], fields[2], int(fields[3]))
    if result.encode() != wire:
        raise ValueError('Noncanonical completion wire')
    return result


def _bootstrap_verifier(authority, pin, expected, accepted):
    """Share the exact durable acceptance contract with receipt consumers."""
    if not isinstance(accepted, BootstrapAcceptance):
        raise ValueError('Explicit bootstrap acceptance required')
    delivery, observation = accepted.delivery, accepted.observation
    wire = delivery.encode()
    if (delivery.process_epoch != expected.process_epoch
            or delivery.dispatch.identity.source_id != expected.source_id
            or observation.init_time != delivery.init_time
            or observation.map_name != delivery.dispatch.map_name
            or observation.round_number != delivery.dispatch.identity.round_number):
        raise ValueError('Completion bootstrap expectation disagrees')
    key = _claim_key(delivery.dispatch)
    directory = authority / key
    context = '|'.join(('slomix_bootstrap_context_v1', delivery.process_epoch,
                        delivery.lifecycle_epoch, expected.source_id))
    issued = json.dumps({'version': 1, 'observation': observation.encode(), 'context': context,
                         'delivery': wire}, separators=(',', ':'), sort_keys=True).encode('ascii') + b'\n'
    acknowledged = (delivery.acknowledgement() + '\n').encode('ascii')

    def verify():
        verify_process_epoch(authority, pin, expected)
        fd = _open_root(authority / delivery.lifecycle_epoch, delivery.lifecycle_epoch)
        os.close(fd)
        if (_read_private_manifest_bytes(directory, 'bootstrap-issued.json') != issued
                or _read_private_manifest_bytes(directory, 'bootstrap-accepted.txt') != acknowledged):
            raise ValueError('Completion requires unchanged durable bootstrap acceptance')

    return key, directory, verify


def _require_dispatch(received, accepted):
    if not isinstance(received, StatsCompletion):
        raise ValueError('Explicit writer completion required')
    received.encode()
    dispatch = accepted.delivery.dispatch
    if (received.generation != dispatch.generation
            or received.filename[18:] != f'{dispatch.map_name}-round-{dispatch.identity.round_number}.txt'):
        raise ValueError('Writer completion disagrees with accepted dispatch')


def verify_stats_completion(authority: Path, pin: ProcessPin, expected: ProcessEpoch, *,
                            accepted: BootstrapAcceptance, completed: StatsCompletion) -> None:
    """Revalidate persisted authentication; this alone does not verify file bytes.

    Caller retains independently approved roots/process expectations. Source must
    still be live. No adoption of missing, changed or partially written records.
    """
    _, directory, verify = _bootstrap_verifier(authority, pin, expected, accepted)
    _require_dispatch(completed, accepted)
    verify()
    if (_read_private_manifest_bytes(directory, 'stats-writer-closed.txt')
            != (completed.encode() + '\n').encode('ascii')):
        raise ValueError('Writer completion record missing or changed')
    verify()


def receive_stats_completion(connection, authority: Path, pin: ProcessPin, expected: ProcessEpoch, *,
                             accepted: BootstrapAcceptance, timeout=5.0) -> StatsCompletion:
    """Own/close accepted socket; validate and fsync receipt before returning.

All records/roots and the independent process pin must remain unchanged. Missing
bootstrap ACK/acceptance refuses publication even if the source really wrote;
retain evidence for explicit reconciliation. Duplicate notices, partial disk
writes and fsync failures never overwrite or auto-adopt an earlier receipt.
No source ACK is sent: success on the Lua side means sent_unconfirmed only.
Payload capture/hash/fsync/manifest/import are SEPARATE steps. In particular the
generation/name/size here are authenticated assertions, not verified file bytes.
Source exit before host validation is refused; no liveness guarantee after return.
"""
    with process_channel(connection, pin, timeout=timeout) as channel:
        key, directory, verify = _bootstrap_verifier(authority, pin, expected, accepted)
        verify()
        received = decode_stats_completion(channel.receive_line())
        _require_dispatch(received, accepted)
        verify()
        payload = (received.encode() + '\n').encode('ascii')
        _write_once(directory, key, 'stats-writer-closed.txt', payload)
        verify()
        if _read_private_manifest_bytes(directory, 'stats-writer-closed.txt') != payload:
            raise ValueError('Writer completion record missing or changed')
        return received
