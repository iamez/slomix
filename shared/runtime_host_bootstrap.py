"""One credentialed bootstrap exchange, not a listener/daemon or game scheduler.

Caller supplies a reserved native process epoch and a previously durably prepared
StatsDispatch for the independently selected source/half. Source must run trusted
opaque-lease bootstrap, once per actual InitGame; no reconnect or replay. Epoch
names this exchange, NOT a clock-derived physical round or continuity proof.
All fsync/record IO runs OUTSIDE game callbacks in the host controller.
"""

import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from shared.runtime_init_observation import InitGameObservation, decode_init_observation
from shared.runtime_manifest_reader import _read_private_manifest_bytes
from shared.runtime_process_authority import (
    ProcessEpoch,
    prepare_observed_process_delivery,
    verify_process_epoch,
)
from shared.runtime_process_channel import process_channel
from shared.runtime_process_pin import ProcessPin
from shared.runtime_source_reservation import _open_root, reserve_source_generation
from shared.runtime_stats_delivery import StatsDelivery
from shared.runtime_stats_dispatch import StatsDispatch


@dataclass(frozen=True)
class BootstrapAcceptance:
    delivery: StatsDelivery
    observation: InitGameObservation


def _claim_key(dispatch):
    # Deliberately excludes process/generation/map: reapproval or a second
    # controller must not issue another bootstrap for the same planned round.
    return hashlib.sha256(('slomix-bootstrap-v1|' + dispatch.identity.encode()).encode('ascii')).hexdigest()[:32]


def _write_once(directory, key, name, payload):
    parent = _open_root(directory, key)
    try:
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
        try:
            if os.write(fd, payload) != len(payload):
                raise OSError('Incomplete bootstrap record')
            os.fsync(fd)
        finally:
            os.close(fd)
        os.fsync(parent)
    finally:
        os.close(parent)


def bootstrap_round(connection, authority: Path, pin: ProcessPin, expected: ProcessEpoch, *,
                    dispatch: StatsDispatch, timeout=5.0) -> BootstrapAcceptance:
    """Own/close accepted channel; reserve before sending, require exact ACK.

    Uses ONE stable private LOCAL authority root, same as process authority.
    Partial claim/record/ACK failure stays stranded; even an empty claim refuses
    another attempt. No cleanup, recovery, adoption or automatic redispatch.
    Network deadline includes elapsed host work but cannot bound filesystem
    syscall latency. Acceptance proves source bind, not stats close/import or
    continued source liveness. No application DB use.
    """
    with process_channel(connection, pin, timeout=timeout) as channel:
        verify_process_epoch(authority, pin, expected)
        observation = decode_init_observation(channel.receive_line())
        lifecycle = uuid.uuid4().hex
        delivery = prepare_observed_process_delivery(authority, pin, expected,
            lifecycle_epoch=lifecycle, observation=observation, dispatch=dispatch)
        wire = delivery.encode()
        key = _claim_key(dispatch)
        directory = reserve_source_generation(authority, key)
        reserve_source_generation(authority, lifecycle)
        context = '|'.join(('slomix_bootstrap_context_v1', expected.process_epoch, lifecycle, expected.source_id))
        record = json.dumps({'version': 1, 'observation': observation.encode(), 'context': context,
                             'delivery': wire}, separators=(',', ':'), sort_keys=True).encode('ascii') + b'\n'
        _write_once(directory, key, 'bootstrap-issued.json', record)

        def verify():
            verify_process_epoch(authority, pin, expected)
            token_fd = _open_root(authority / lifecycle, lifecycle)
            os.close(token_fd)
            if _read_private_manifest_bytes(directory, 'bootstrap-issued.json') != record:
                raise ValueError('Bootstrap issue record missing or changed')

        verify()
        channel.send_line(context)
        channel.send_line(wire)
        if channel.receive_line() != delivery.acknowledgement():
            raise ValueError('Bootstrap acknowledgement disagrees with issued delivery')
        verify()
        accepted = (delivery.acknowledgement() + '\n').encode('ascii')
        _write_once(directory, key, 'bootstrap-accepted.txt', accepted)
        verify()
        if _read_private_manifest_bytes(directory, 'bootstrap-accepted.txt') != accepted:
            raise ValueError('Bootstrap acceptance record missing or changed')
        return BootstrapAcceptance(delivery, observation)
