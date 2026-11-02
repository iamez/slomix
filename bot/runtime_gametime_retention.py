"""Caller-driven source provenance + existing timing inbox, one transaction."""

import re
from dataclasses import dataclass

from bot.runtime_gametime_source import parse_verified_gametime
from bot.services.lua_correction_inbox import retain_lua_correction
from shared.runtime_round_identity import RoundIdentity


@dataclass(frozen=True)
class GametimeRetention:
    """Timing input retained, not whole-file processing or a source deletion ACK."""

    source_id: str
    generation: str
    input_id: int


async def retain_gametime_source(
    adapter, source_fd: int, *, source_id: str, generation: str, filename: str,
    expected_size: int, expected_sha256: str,
    expected_identity: RoundIdentity | None = None,
) -> GametimeRetention:
    """Validate sealed bytes before DB access; atomically retain timing + source.

    Caller authenticates descriptor/source/generation/expectations together,
    owns descriptor lifetime and retains raw bytes for other sections. Configured
    source IDs use the intersection of admission and existing inbox contracts;
    no case-folding of source identities. One artifact per source generation.
    Different generations can reference one deduplicated normalized input while
    retaining distinct raw hashes. Replay verifies all fields, never reassigns.

    Requires migration097 (plus098 for declared IDs) and nested transactions.
    Declared IDs remain separate artifact provenance, not canonical round links.
    A return inside a caller transaction is not an outer commit acknowledgement.
    Failures/cancellation propagate. No round linkage, repair/application, new
    discovery loop, feature-flag activation, file publication, deletion or ACK.
    Legacy correction workers must remain off for a dedicated runtime source
    until its separate linking/repair contract is approved.
    """
    if not isinstance(source_id, str) or re.fullmatch(r'[a-z0-9][a-z0-9_.-]{0,63}', source_id, re.ASCII) is None:
        raise ValueError('Gametime retention requires a lowercase configured source ID')
    timing = parse_verified_gametime(
        source_fd, source_id=source_id, generation=generation, filename=filename,
        expected_size=expected_size, expected_sha256=expected_sha256,
        expected_identity=expected_identity,
    )
    payload = {key: getattr(timing, key) for key in (
        'map_name', 'round_number', 'round_start_unix', 'round_end_unix',
        'actual_duration_seconds', 'total_pause_seconds', 'pause_count',
    )}
    async with adapter.transaction():
        input_id = await retain_lua_correction(adapter, source_id, payload)
        expected = (filename, expected_size, expected_sha256, input_id)
        row = await adapter.fetch_one('''
            INSERT INTO runtime_gametime_sources
                (source_key,generation,filename,source_size,source_sha256,input_id)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT (source_key,generation) DO NOTHING
            RETURNING filename,source_size,source_sha256,input_id
        ''', (source_id, generation, *expected))
        if row is None:
            row = await adapter.fetch_one('''
                SELECT filename,source_size,source_sha256,input_id
                FROM runtime_gametime_sources
                WHERE source_key=? AND generation=? FOR UPDATE
            ''', (source_id, generation))
        if row is None or tuple(row) != expected:
            raise ValueError('Gametime source generation conflicts with retained provenance')
        identity = timing.declared_identity
        if identity is not None:
            declared = (identity.match_id, identity.round_id, identity.round_number, identity.first_round_id)
            row = await adapter.fetch_one('''
                INSERT INTO runtime_gametime_identities
                    (source_key,generation,match_id,round_id,round_number,first_round_id)
                VALUES (?,?,?,?,?,?)
                ON CONFLICT (source_key,generation) DO NOTHING
                RETURNING match_id,round_id,round_number,first_round_id
            ''', (source_id, generation, *declared))
            if row is None:
                row = await adapter.fetch_one('''
                    SELECT match_id,round_id,round_number,first_round_id
                    FROM runtime_gametime_identities
                    WHERE source_key=? AND generation=? FOR UPDATE
                ''', (source_id, generation))
            if row is None or tuple(row) != declared:
                raise ValueError('Gametime declaration conflicts with retained identity')
    return GametimeRetention(source_id, generation, input_id)
