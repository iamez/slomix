"""Durable one-shot process epochs for an explicitly approved native process.

Use ONE stable private authority root for all cooperating controllers. No root
rotation, record repair, crash redispatch or implicit recovery. Records are
evidence, not secrets/signatures; hostile same-user writes and unstable ancestors
are outside the filesystem contract. No engine role or Lua lifecycle is inferred.
"""

import hashlib
import json
import os
import re
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from shared.runtime_init_observation import InitGameObservation
from shared.runtime_manifest_reader import _read_private_manifest_bytes
from shared.runtime_process_pin import ProcessIdentity, ProcessPin
from shared.runtime_source_reservation import _open_root, reserve_source_generation
from shared.runtime_stats_delivery import StatsDelivery
from shared.runtime_stats_dispatch import StatsDispatch


def _process_key(identity):
    # Immutable kernel lifetime coordinates, not operator-selectable source or
    # executable approval. A hash collision refuses a process, never reuses it.
    coordinates = ['slomix-process-v1', identity.boot_id, identity.pid, identity.start_ticks]
    return hashlib.sha256(json.dumps(coordinates, separators=(',', ':')).encode('ascii')).hexdigest()[:32]


def _root_identity(root, token):
    fd = _open_root(root, token)
    try:
        info = os.fstat(fd)
        return info.st_dev, info.st_ino
    finally:
        os.close(fd)


@dataclass(frozen=True)
class ProcessEpoch:
    source_id: str
    process_epoch: str
    process: ProcessIdentity
    authority_identity: tuple[int, int]


def _record(value):
    return json.dumps({'version': 1, **asdict(value)}, separators=(',', ':'),
                      sort_keys=True).encode('ascii') + b'\n'


def reserve_process_epoch(authority: Path, pin: ProcessPin, *, source_id: str) -> ProcessEpoch:
    """Claim the approved process exactly once in this authority, fsync then return.

    Any existing claim (even partial/empty) refuses a second epoch. Failure after
    mkdir leaves all evidence intact and requires reconciliation, not retry or
    deletion. A returned epoch still needs live revalidation before use. Neither
    a successful fsync nor a live PID proves physical rounds or IPC acceptance.
    This blocking disk operation belongs outside ET callbacks.
    """
    if not isinstance(pin, ProcessPin):
        raise ValueError('Explicit native process pin required')
    if not isinstance(source_id, str) or re.fullmatch(r'[a-z0-9][a-z0-9_.-]{0,63}', source_id) is None:
        raise ValueError('Invalid process authority source')
    identity = pin.assert_current()
    key = _process_key(identity)
    root_identity = _root_identity(authority, key)
    reserve_source_generation(authority, key)
    epoch = uuid.uuid4().hex
    reserve_source_generation(authority, epoch)
    value = ProcessEpoch(source_id, epoch, identity, root_identity)
    directory = _open_root(authority / key, key)
    try:
        fd = os.open('process-epoch.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=directory)
        try:
            payload = _record(value)
            if os.write(fd, payload) != len(payload):
                raise OSError('Incomplete process epoch record')
            os.fsync(fd)
        finally:
            os.close(fd)
        os.fsync(directory)
    finally:
        os.close(directory)
    verify_process_epoch(authority, pin, value)
    return value


def verify_process_epoch(authority: Path, pin: ProcessPin, expected: ProcessEpoch) -> ProcessEpoch:
    """Recheck a known successful reservation; NOT permission to recover dispatch.

    Does not freeze the process; same-binary exec and Lua reload are not detected.
    Caller must independently prove lifecycle and exclusive legacy handover.
    No discovery/adoption of a record as its own expected identity.
    """
    if not isinstance(pin, ProcessPin) or not isinstance(expected, ProcessEpoch):
        raise ValueError('Explicit process pin and expected epoch required')
    if pin.assert_current() != expected.process:
        raise ValueError('Process epoch belongs to another process')
    key = _process_key(expected.process)
    if _root_identity(authority, key) != expected.authority_identity:
        raise ValueError('Process authority root changed')
    _root_identity(authority / expected.process_epoch, expected.process_epoch)
    _root_identity(authority / key, key)
    if _read_private_manifest_bytes(authority / key, 'process-epoch.json') != _record(expected):
        raise ValueError('Process epoch record missing or changed')
    if pin.assert_current() != expected.process:
        raise ValueError('Process changed during epoch verification')
    return expected


def prepare_process_delivery(authority: Path, pin: ProcessPin, expected: ProcessEpoch, *,
                             lifecycle_epoch: str, init_time: int, dispatch: StatsDispatch) -> StatsDelivery:
    """Serialize with the reserved process epoch and an independently proven life.

    Caller supplies trusted lifecycle_epoch/init_time; this function neither
    authenticates them nor allocates lifecycle IDs. It sends nothing and cannot
    authorize retries/redispatch. Existing one-shot dispatch and Lua ACK policies
    still apply. Revalidate again at the actual transport boundary.
    """
    verify_process_epoch(authority, pin, expected)
    delivery = StatsDelivery(expected.process_epoch, lifecycle_epoch, init_time, dispatch)
    delivery.encode()
    if dispatch.identity.source_id != expected.source_id:
        raise ValueError('Delivery source disagrees with approved process')
    verify_process_epoch(authority, pin, expected)
    return delivery


def prepare_observed_process_delivery(authority: Path, pin: ProcessPin, expected: ProcessEpoch, *,
                                      lifecycle_epoch: str, observation: InitGameObservation,
                                      dispatch: StatsDispatch) -> StatsDelivery:
    """Use source-observed fields; source VM must still consume its own lease.

    This snapshot does not authenticate the source or replace its opaque live
    context check. Caller supplies a separately issued lifecycle epoch and a
    durably prepared dispatch. No sending, lease recovery or timestamp identity.
    """
    if not isinstance(observation, InitGameObservation) or not isinstance(dispatch, StatsDispatch):
        raise ValueError('Explicit InitGame observation and dispatch required')
    observation.encode()
    if (observation.map_name != dispatch.map_name
            or observation.round_number != dispatch.identity.round_number):
        raise ValueError('Dispatch disagrees with observed InitGame map or half')
    return prepare_process_delivery(authority, pin, expected, lifecycle_epoch=lifecycle_epoch,
                                    init_time=observation.init_time, dispatch=dispatch)
