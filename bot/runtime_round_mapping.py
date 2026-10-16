"""Explicit sealed stats identity -> canonical row, inside the import transaction.

Caller provisions/authenticates the expected identity independently. Agreement
does not prove physical engine starts. Never attach declarations to legacy rows.
"""

import re
from dataclasses import dataclass

from shared.runtime_round_identity import RoundIdentity, require_round_pair


@dataclass(frozen=True)
class StatsRoundBinding:
    identity: RoundIdentity
    generation: str
    filename: str
    size: int
    sha256: str
    map_name: str
    first: 'StatsRoundBinding | None' = None

    def __post_init__(self):
        if not isinstance(self.identity, RoundIdentity):
            raise ValueError('Expected independently supplied round identity')
        if not isinstance(self.generation, str) or re.fullmatch(r'[0-9a-f]{32}', self.generation) is None:
            raise ValueError('Invalid mapped generation')
        if not isinstance(self.sha256, str) or re.fullmatch(r'[0-9a-f]{64}', self.sha256) is None:
            raise ValueError('Invalid mapped full digest')
        if type(self.size) is not int or not 0 < self.size <= 8 * 1024 * 1024:
            raise ValueError('Invalid mapped source size')
        if not isinstance(self.map_name, str) or re.fullmatch(r'[A-Za-z0-9_-]{1,64}', self.map_name) is None:
            raise ValueError('Invalid mapped map')
        expected = rf'\d{{4}}-\d{{2}}-\d{{2}}-\d{{6}}-{re.escape(self.map_name)}-round-{self.identity.round_number}\.txt'
        if not isinstance(self.filename, str) or re.fullmatch(expected, self.filename) is None:
            raise ValueError('Mapped filename/map/half conflict')
        if self.identity.round_number == 1:
            if self.first is not None:
                raise ValueError('R1 cannot have a dependency')
        else:
            if not isinstance(self.first, StatsRoundBinding) or self.first.map_name != self.map_name:
                raise ValueError('R2 requires exact mapped R1 artifact')
            require_round_pair(self.first.identity, self.identity)

    def values(self):
        identity = self.identity
        return (identity.source_id, identity.round_id, identity.match_id,
                identity.round_number, identity.first_round_id, self.generation,
                self.filename, self.size, self.sha256, self.map_name)


_FIELDS = ('source_key', 'round_key', 'match_key', 'round_number', 'first_round_key',
           'generation', 'filename', 'source_size', 'source_sha256', 'map_name')


async def _parent(conn, binding, round_id, payload_hash, *, expected_validation=None):
    row = await conn.fetchrow('SELECT map_name,round_number,gaming_session_id,match_id,round_date,round_time '
                              'FROM rounds WHERE id=$1 FOR SHARE',
                              round_id)
    match_filename = binding.first.filename if binding.first is not None else binding.filename
    if (row is None or row['map_name'] != binding.map_name
            or row['round_number'] != binding.identity.round_number or row['gaming_session_id'] is None
            or row['match_id'] != match_filename[:17]
            or row['round_date'] != binding.filename[:10] or row['round_time'] != binding.filename[11:17]):
        raise ValueError('Mapped canonical parent missing or changed')
    event = await conn.fetchrow("SELECT source_filename,source_payload_sha256,validation_passed,"
                               "round_number,gaming_session_id FROM runtime_events "
                               "WHERE round_id=$1 AND event_type='round_stats_imported' FOR SHARE", round_id)
    if (event is None or type(event['validation_passed']) is not bool
            or (expected_validation is not None and event['validation_passed'] is not expected_validation)
            or tuple(event) != (binding.filename, payload_hash, event['validation_passed'],
                                        binding.identity.round_number, row['gaming_session_id'])):
        raise ValueError('Mapped canonical journal missing or changed')


async def inspect_round_mapping(conn, binding, payload_hash):
    """Exact replay or absent, never legacy adoption. Caller holds transaction."""
    if not conn.is_in_transaction():
        raise RuntimeError('Round mapping requires import transaction')
    rows = await conn.fetch('SELECT * FROM runtime_round_mappings WHERE '
        '(source_key=$1 AND (round_key=$2 OR generation=$3 OR (match_key=$4 AND round_number=$5))) '
        'OR filename=$6 FOR SHARE', binding.identity.source_id, binding.identity.round_id,
        binding.generation, binding.identity.match_id, binding.identity.round_number, binding.filename)
    if not rows:
        return None
    if (len(rows) != 1 or tuple(rows[0][key] for key in _FIELDS) != binding.values()
            or rows[0]['payload_sha256'] != payload_hash):
        raise ValueError('Runtime round mapping conflicts with sealed artifact')
    await _parent(conn, binding, rows[0]['canonical_round_id'], payload_hash)
    await require_first_mapping(conn, binding)
    return rows[0]['canonical_round_id']


async def require_first_mapping(conn, binding):
    if binding.first is None:
        return
    first = binding.first
    row = await conn.fetchrow('SELECT * FROM runtime_round_mappings WHERE source_key=$1 AND round_key=$2 FOR SHARE',
                             first.identity.source_id, first.identity.round_id)
    if row is None or tuple(row[key] for key in _FIELDS) != first.values():
        raise ValueError('Exact canonical R1 mapping missing or conflicting')
    await _parent(conn, first, row['canonical_round_id'], row['payload_sha256'])


async def record_round_mapping(conn, binding, round_id, payload_hash, *, validation_passed):
    if type(validation_passed) is not bool:
        raise ValueError('Mapping requires the actual validation boolean')
    if not conn.is_in_transaction():
        raise RuntimeError('Round mapping requires import transaction')
    await require_first_mapping(conn, binding)
    await _parent(conn, binding, round_id, payload_hash, expected_validation=validation_passed)
    await conn.execute('INSERT INTO runtime_round_mappings (' + ','.join(_FIELDS) +
                       ',canonical_round_id,payload_sha256) VALUES '
                       '($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)',
                       *binding.values(), round_id, payload_hash)
