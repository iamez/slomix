"""Fresh declared timing correlation, not timing application or a durable link."""

import re
from dataclasses import dataclass
from typing import Literal

from bot.runtime_gametime_source import parse_verified_gametime
from bot.services.lua_correction_inbox import normalize_correction_input, validate_retained_correction
from shared.runtime_proximity_commit import _MappingSnapshotReader
from shared.runtime_proximity_mapping import DeclaredMappingPending, resolve_declared_parent
from shared.runtime_round_identity import RoundIdentity


@dataclass(frozen=True)
class GametimeCorrelationObservation:
    """Current committed evidence only; round_id is the canonical integer ID."""

    status: Literal['missing_retention', 'mapping_pending', 'conflict', 'canonical_target_verified']
    reason: str
    round_id: int | None = None
    gaming_session_id: int | None = None
    input_id: int | None = None


async def inspect_declared_gametime(
    observer, source_fd: int, *, source_id: str, generation: str, filename: str,
    expected_size: int, expected_sha256: str, expected_identity: RoundIdentity,
) -> GametimeCorrelationObservation:
    """Compare sealed caller-authenticated timing bytes to one committed snapshot.

    Requires migrations097/098/099 and the SAME authoritative primary/schema as
    retention/import. Caller owns an exclusive native connection, source FD,
    lifecycle and timeouts. An existing transaction is refused, including a
    read-only one, because it could expose uncommitted caller state.

    Expected identity is mandatory and supplied independently; it is never
    derived from a payload, normalized inbox input or a clock match. Raw map
    spelling is retained for099; only the inbox projection normalizes its map
    to lowercase. Multiple artifacts/declarations may share one input_id, so
    every source+generation must independently pass098 and099.

    Reads no whole-file completion marker and performs no writes, application,
    repair, acknowledgement, deletion or connection creation. The result is a
    current correlation observation, not persisted linkage, engine authenticity,
    timing correctness or permission to apply the timing projection.
    Invalid caller binding/bytes fail before DB; contradictory DB evidence is
    conflict; missing099 is pending. Infrastructure errors propagate.
    """
    timing, projection = verified_timing_binding(source_fd, source_id=source_id, generation=generation,
        filename=filename, expected_size=expected_size, expected_sha256=expected_sha256,
        expected_identity=expected_identity)
    if observer.is_in_transaction() is not False:
        raise RuntimeError('Gametime correlation requires a connection outside any transaction')
    async with observer.transaction(isolation='repeatable_read', readonly=True):
        return await inspect_timing_snapshot(observer, timing, expected_identity, projection)


def verified_timing_binding(source_fd, *, source_id, generation, filename,
                            expected_size, expected_sha256, expected_identity):
    """Shared admission for observer and transactional linker; no DB access."""
    if not isinstance(expected_identity, RoundIdentity):
        raise ValueError('Independently supplied expected gametime identity required')
    if (not isinstance(source_id, str)
            or re.fullmatch(r'[a-z0-9][a-z0-9_.-]{0,63}', source_id, re.ASCII) is None
            or expected_identity.source_id != source_id):
        raise ValueError('Expected gametime identity conflicts with configured source')
    timing = parse_verified_gametime(
        source_fd, source_id=source_id, generation=generation, filename=filename,
        expected_size=expected_size, expected_sha256=expected_sha256,
        expected_identity=expected_identity,
    )
    projection = normalize_correction_input({key: getattr(timing, key) for key in (
        'map_name', 'round_number', 'round_start_unix', 'round_end_unix',
        'actual_duration_seconds', 'total_pause_seconds', 'pause_count',
    )})
    return timing, projection


async def inspect_timing_snapshot(observer, timing, expected_identity, projection, *, lock=False):
    """Internal shared validator; caller owns stable snapshot or writer locks.

    Writer must first acquire the correction-identity lock shared with retention.
    This result is not an acknowledgement of the caller's outer commit.
    """
    if type(lock) is not bool:
        raise ValueError('Explicit timing lock policy required')
    source_id, generation = timing.source_id, timing.generation
    suffix = ' FOR SHARE' if lock else ''
    source = await observer.fetchrow(
        'SELECT source_key,generation,filename,source_size,source_sha256,input_id '
        'FROM runtime_gametime_sources WHERE source_key=$1 AND generation=$2' + suffix,
        source_id, generation,
    )
    if source is None:
        return GametimeCorrelationObservation('missing_retention', 'retained_source_missing')
    if (tuple(source[key] for key in (
        'source_key', 'generation', 'filename', 'source_size', 'source_sha256',
    )) != (source_id, generation, timing.filename, timing.size, timing.sha256)
            or type(source['input_id']) is not int or source['input_id'] <= 0):
        return GametimeCorrelationObservation('conflict', 'retained_source_conflict')
    input_id = source['input_id']
    declared = await observer.fetchrow(
        'SELECT source_key,generation,match_id,round_id,round_number,first_round_id '
        'FROM runtime_gametime_identities WHERE source_key=$1 AND generation=$2' + suffix,
        source_id, generation,
    )
    if declared is None or tuple(declared[key] for key in (
        'source_key', 'generation', 'match_id', 'round_id', 'round_number', 'first_round_id',
    )) != (source_id, generation, expected_identity.match_id, expected_identity.round_id,
           expected_identity.round_number, expected_identity.first_round_id):
        return GametimeCorrelationObservation('conflict', 'retained_identity_conflict', input_id=input_id)
    retained = await observer.fetchrow(
        'SELECT id,source_key,payload_version,payload_digest,payload,map_name,round_number,round_start_unix '
        'FROM lua_correction_inputs WHERE id=$1 AND source_key=$2' + (' FOR UPDATE' if lock else ''),
        input_id, source_id,
    )
    if retained is None or (retained['id'], retained['source_key']) != (input_id, source_id):
        return GametimeCorrelationObservation('conflict', 'retained_input_conflict', input_id=input_id)
    try:
        if validate_retained_correction(retained) != projection:
            return GametimeCorrelationObservation('conflict', 'retained_projection_conflict', input_id=input_id)
    except (ValueError, TypeError, KeyError):
        return GametimeCorrelationObservation('conflict', 'retained_input_conflict', input_id=input_id)
    try:
        parent = await resolve_declared_parent(
            _MappingSnapshotReader(observer), expected_identity, timing.map_name, lock=lock,
        )
    except DeclaredMappingPending:
        return GametimeCorrelationObservation('mapping_pending', 'canonical_mapping_pending', input_id=input_id)
    except ValueError:
        return GametimeCorrelationObservation('conflict', 'canonical_parent_conflict', input_id=input_id)
    return GametimeCorrelationObservation(
        'canonical_target_verified', 'declared_canonical_target_verified',
        round_id=parent.round_id, gaming_session_id=parent.gaming_session_id, input_id=input_id,
    )
