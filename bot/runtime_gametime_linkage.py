"""Read-only, explicitly scoped timing-link evidence; never a link authorization."""

import re
from dataclasses import dataclass
from typing import Literal

from bot.services.lua_correction_inbox import validate_retained_correction


@dataclass(frozen=True)
class RoundTimingEvidence:
    round_id: int
    status: Literal['identity_mismatch', 'missing_start', 'start_mismatch', 'end_mismatch', 'exact_start']


@dataclass(frozen=True)
class GametimeLinkInspection:
    source_id: str
    generation: str
    status: Literal['empty_scope', 'source_missing', 'missing_parent', 'incomplete_scope',
                    'identity_mismatch', 'needs_timing_evidence', 'timing_conflict',
                    'ambiguous', 'candidate_in_scope']
    requested_round_ids: tuple[int, ...]
    rounds: tuple[RoundTimingEvidence, ...] = ()
    # None means parent existence was not measured (e.g. source is missing).
    missing_round_ids: tuple[int, ...] | None = None
    candidate_round_id: int | None = None
    input_id: int | None = None
    filename: str | None = None
    source_sha256: str | None = None


async def inspect_gametime_link(adapter, *, source_id: str, generation: str, round_ids):
    """Inspect one retained source against up to100 explicit candidate IDs.

    One SELECT gives a statement-consistent snapshot; no explicit locks, writes, heuristic
    date/nearest-time lookup or automatic repair. Empty scope does no DB access.
    Missing measurements are not zero. Canonical timestamps can themselves come
    from legacy heuristic links: exact agreement is only a candidate WITHIN this
    caller-supplied scope, never independent physical identity/authentication or
    global uniqueness. Returned candidates MUST NOT authorize bootstrap writes.
    A later writer needs separately verified linkage and fresh transactional checks.
    Inside a caller transaction this can see uncommitted rows, not committed proof.
    Different-start siblings are excluded but reported; NULL end does not confirm
    end agreement. Session membership is not measured by this diagnostic.

    Requires097. Storage errors and corrupt inbox evidence propagate, not no_data.
    Caller must authenticate source/scope; rounds currently lack source namespace.
    Raw bytes are not re-read, so receipt consistency is not renewed hash proof.
    """
    if not isinstance(source_id, str) or re.fullmatch(r'[a-z0-9][a-z0-9_.-]{0,63}', source_id, re.ASCII) is None:
        raise ValueError('Invalid configured gametime source ID')
    if not isinstance(generation, str) or re.fullmatch(r'[a-f0-9]{32}', generation, re.ASCII) is None:
        raise ValueError('Invalid gametime source generation')
    if not isinstance(round_ids, (list, tuple)) or len(round_ids) > 100:
        raise ValueError('Explicit round ID list/tuple of at most100 required')
    if any(type(value) is not int or not 1 <= value <= 2147483647 for value in round_ids):
        raise ValueError('Round IDs must be positive int32 values')
    scope = tuple(dict.fromkeys(round_ids))
    base = dict(source_id=source_id, generation=generation, requested_round_ids=scope)
    if not scope:
        return GametimeLinkInspection(**base, status='empty_scope', missing_round_ids=())
    rows = await adapter.fetch_all('''
        SELECT s.input_id, s.filename, s.source_sha256,
               i.payload_version, i.payload_digest, i.payload,
               i.map_name, i.round_number, i.round_start_unix,
               r.id AS candidate_id, r.map_name AS candidate_map,
               r.round_number AS candidate_half, r.round_start_unix AS candidate_start,
               r.round_end_unix AS candidate_end
        FROM runtime_gametime_sources s
        JOIN lua_correction_inputs i ON i.id=s.input_id AND i.source_key=s.source_key
        LEFT JOIN rounds r ON r.id=ANY(?::integer[])
        WHERE s.source_key=? AND s.generation=?
        ORDER BY r.id
    ''', (list(scope), source_id, generation))
    if not rows:
        return GametimeLinkInspection(**base, status='source_missing')
    payload = validate_retained_correction(rows[0])
    required = {'round_end_unix', 'actual_duration_seconds', 'total_pause_seconds', 'pause_count'}
    if not required.issubset(payload):
        raise ValueError('Retained gametime timing projection is incomplete')
    evidence = []
    for row in rows:
        rid = row['candidate_id']
        if rid is None:
            continue
        if rid not in scope:
            raise ValueError('Gametime inspection escaped requested scope')
        if (str(row['candidate_map'] or '').strip().lower(), row['candidate_half']) != (
            payload['map_name'], payload['round_number'],
        ):
            status = 'identity_mismatch'
        elif row['candidate_start'] is None or row['candidate_start'] <= 0:
            status = 'missing_start'
        elif row['candidate_start'] != payload['round_start_unix']:
            status = 'start_mismatch'
        elif row['candidate_end'] is not None and row['candidate_end'] != payload['round_end_unix']:
            status = 'end_mismatch'
        else:
            status = 'exact_start'
        evidence.append(RoundTimingEvidence(rid, status))
    missing = tuple(rid for rid in scope if rid not in {item.round_id for item in evidence})
    viable = [item for item in evidence if item.status in {'exact_start', 'missing_start', 'end_mismatch'}]
    candidate = None
    if not evidence:
        status = 'missing_parent'
    elif missing:
        status = 'incomplete_scope'
    elif len(viable) > 1:
        status = 'ambiguous'
    elif viable and viable[0].status == 'missing_start':
        status = 'needs_timing_evidence'
    elif viable and viable[0].status == 'exact_start':
        status, candidate = 'candidate_in_scope', viable[0].round_id
    elif any(item.status != 'identity_mismatch' for item in evidence):
        status = 'timing_conflict'
    else:
        status = 'identity_mismatch'
    return GametimeLinkInspection(**base, status=status, rounds=tuple(evidence),
        missing_round_ids=missing, candidate_round_id=candidate,
        input_id=rows[0]['input_id'], filename=rows[0]['filename'], source_sha256=rows[0]['source_sha256'])
