"""Opt-in timing projection over verified bytes, not ingestion or authentication."""

import json
import re
from dataclasses import dataclass

from bot.services.webhook_round_metadata_service import WebhookRoundMetadataService
from shared.runtime_manifest_reader import _unique_object
from shared.runtime_round_identity import RoundIdentity, decode_round_identity
from shared.runtime_sealed_snapshot import sealed_stats_snapshot

MAX_GAMETIME_BYTES = 1024 * 1024
_NAME = re.compile(r'gametime-([A-Za-z0-9_-]{1,128})-R([12])-([0-9]{1,19})\.json', re.ASCII)


@dataclass(frozen=True)
class VerifiedGametimeTiming:
    """Content agreement, NOT authenticated provenance or a resolved DB parent.

    Only timing scalars are admitted. Retain raw source for team/spawn/other data;
    this record must never be used to mark a whole gametime file fully imported.
    """

    source_id: str
    generation: str
    filename: str
    size: int
    sha256: str
    map_name: str
    round_number: int
    round_start_unix: int
    round_end_unix: int
    actual_duration_seconds: int
    total_pause_seconds: int
    pause_count: int
    declared_identity: RoundIdentity | None = None


def _reject_constant(_):
    raise ValueError('Nonfinite gametime JSON value')


def _json(value):
    try:
        result = json.loads(value, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError('Malformed gametime JSON') from exc
    # Bound accepted structure, not peak decoder allocations. Raw bytes are
    # limited before json.loads; expanded memory and latency need worker limits.
    pending, nodes = [(result, 0)], 0
    while pending:
        item, depth = pending.pop()
        nodes += 1
        if nodes > 50_000 or depth > 32:
            raise ValueError('Gametime JSON structure exceeds admission limits')
        if isinstance(item, dict):
            pending.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            pending.extend((child, depth + 1) for child in item)
        elif isinstance(item, float):
            # Producer timing fields are integer/string; reject overflow floats
            # even outside selected fields (JSON 1e999 is not parse_constant).
            import math
            if not math.isfinite(item):
                raise ValueError('Nonfinite gametime JSON value')
    return result


def _integer(value, field, *, minimum=0, maximum=2_147_483_647):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f'Invalid gametime {field}')
    return value


def _decimal(fields, name, pattern=r'([0-9]+)'):
    value = fields.get(name)
    match = re.fullmatch(pattern, value, re.ASCII) if isinstance(value, str) else None
    if match is None:
        raise ValueError(f'Missing or invalid gametime {name}')
    return tuple(int(group) for group in match.groups())


def _decode_timing(payload, expected_identity, source_id, expected_round):
    document = _json(payload.decode('utf-8'))
    if not isinstance(document, dict) or not isinstance(document.get('meta'), dict):
        raise ValueError('Gametime requires explicit meta identity')
    embed_payload = document.get('payload')
    if isinstance(embed_payload, str):
        embed_payload = _json(embed_payload)
    if not isinstance(embed_payload, dict):
        raise ValueError('Gametime payload must be an object')
    embeds = embed_payload.get('embeds')
    if not isinstance(embeds, list) or len(embeds) != 1 or not isinstance(embeds[0], dict):
        raise ValueError('Gametime requires exactly one embed')
    entries = embeds[0].get('fields')
    if not isinstance(entries, list):
        raise ValueError('Gametime fields must be a list')
    fields = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get('name'), str):
            raise ValueError('Invalid gametime embed field')
        key = entry['name'].lower()
        if key in fields:
            raise ValueError('Duplicate gametime embed field')
        fields[key] = entry.get('value')
    meta = document['meta']
    map_name = meta.get('map')
    half = _integer(meta.get('round'), 'round', minimum=1, maximum=2)
    start = _integer(meta.get('round_start_unix'), 'start', minimum=1, maximum=9_223_372_036_854_775_807)
    end = _integer(meta.get('round_end_unix'), 'end', minimum=1, maximum=9_223_372_036_854_775_807)
    duration = _integer(meta.get('actual_duration_seconds'), 'duration')
    pauses = _integer(meta.get('pause_seconds'), 'pause seconds')
    count = _integer(meta.get('pause_count'), 'pause count')
    if ((map_name, half, end) != expected_identity or fields.get('map') != map_name
            or _decimal(fields, 'round') != (half,)
            or _decimal(fields, 'lua_roundstart') != (start,)
            or _decimal(fields, 'lua_roundend') != (end,)
            or _decimal(fields, 'lua_playtime', r'([0-9]+) sec') != (duration,)
            or _decimal(fields, 'lua_pauses', r'([0-9]+) \(([0-9]+) sec\)') != (count, pauses)):
        raise ValueError('Gametime filename/meta/embed identity or timing conflict')
    if end < start or duration + pauses > end - start:
        raise ValueError('Gametime timing exceeds its wall-clock interval')
    declared = None
    if 'runtime_identity' in meta:
        declared = decode_round_identity(meta['runtime_identity'])
        if declared.source_id != source_id or declared.round_number != half:
            raise ValueError('Gametime declared source or half conflicts')
    if expected_round is not None and declared != expected_round:
        raise ValueError('Gametime declared round identity missing or conflicts')
    # Feed only verified fields into the shared legacy decoder. Never expose its
    # permissive nested JSON/defaults as validated runtime measurements.
    selected = ('map', 'round', 'lua_roundstart', 'lua_roundend', 'lua_playtime', 'lua_pauses')
    _, decoded, _ = WebhookRoundMetadataService().decode_gametime_document({
        'payload': {'embeds': [{'fields': [{'name': key, 'value': fields[key]} for key in selected]}]},
    })
    projection = tuple(decoded[key] for key in (
        'map_name', 'round_number', 'round_start_unix', 'round_end_unix',
        'actual_duration_seconds', 'total_pause_seconds', 'pause_count',
    ))
    if projection != (map_name, half, start, end, duration, pauses, count):
        raise ValueError('Gametime decoder disagrees with validated timing')
    return (*projection, declared)


def parse_verified_gametime(
    source_fd: int, *, source_id: str, generation: str, filename: str,
    expected_size: int, expected_sha256: str,
    expected_identity: RoundIdentity | None = None,
) -> VerifiedGametimeTiming:
    """Read a kernel-sealed copy and admit only mutually consistent timing.

    Caller authenticates descriptor + configured source/generation/name/size/hash
    together and owns fd lifetime. Neither these strings nor matching hash prove
    producer trust/completion. Reuses the existing8MiB snapshot primitive with a
    stricter1MiB admission ceiling; source offset unchanged, no source path reopen.
    No disk publication, receipt, DB, remote IO, service, source deletion or ack.
    Strict R1/R2 only: legacy round0/defaults/conflicts require separate handling.
    Optional expected_identity requires exact producer declaration. A present
    malformed/conflicting declaration always rejects, even without strict policy.
    Declaration agreement is not authenticated physical round linkage.
    """
    if expected_identity is not None and not isinstance(expected_identity, RoundIdentity):
        raise ValueError('Explicit expected round identity required')
    if not isinstance(source_id, str) or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', source_id, re.ASCII) is None:
        raise ValueError('Gametime requires configured source identity')
    if not isinstance(generation, str) or re.fullmatch(r'[0-9a-f]{32}', generation, re.ASCII) is None:
        raise ValueError('Gametime requires explicit source generation')
    match = _NAME.fullmatch(filename) if isinstance(filename, str) else None
    if match is None:
        raise ValueError('Invalid gametime filename')
    if type(expected_size) is not int or not 0 < expected_size <= MAX_GAMETIME_BYTES:
        raise ValueError('Gametime size must be within the 1MiB admission limit')
    map_name, half, end = match.groups()
    with sealed_stats_snapshot(source_fd, expected_size=expected_size, expected_sha256=expected_sha256) as snapshot:
        timing = _decode_timing(snapshot.read(), (map_name, int(half), int(end)), source_id, expected_identity)
    return VerifiedGametimeTiming(source_id, generation, filename, expected_size, expected_sha256, *timing)
