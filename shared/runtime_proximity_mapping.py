"""Forward-only declared proximity linkage; callers own transactions and trust.

No clock-based parent selection, historical adoption or source acknowledgement.
All cooperating declared writers serialize first ingestion; legacy writers must
already have handed over exclusively. A receipt is not whole-row attestation.
"""

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from io import StringIO

from shared.proximity_receipt_link import record_receipt_parent
from shared.runtime_proximity_identity import proximity_header_identity
from shared.runtime_round_identity import RoundIdentity
from shared.runtime_spool import _PROXIMITY_NAME, _validate_metadata


class DeclaredMappingPending(ValueError):
    """No trusted mapping yet; preserve the source and reconciliation hold."""


@dataclass(frozen=True)
class DeclaredProximityBinding:
    source_id: str
    generation: str
    filename: str
    size: int
    sha256: str
    session_date: date

    def __post_init__(self):
        if not isinstance(self.source_id, str) or re.fullmatch(r'[a-z0-9][a-z0-9_.-]{0,63}', self.source_id) is None:
            raise ValueError('Invalid declared source authority')
        if not isinstance(self.generation, str) or re.fullmatch(r'[0-9a-f]{32}', self.generation) is None:
            raise ValueError('Invalid declared generation')
        if not isinstance(self.filename, str) or len(self.filename) > 240 or self.sha256 is None:
            raise ValueError('Declared binding requires bounded filename and digest')
        _validate_metadata(self.filename, self.size, 8 * 1024 * 1024, self.sha256, name_pattern=_PROXIMITY_NAME)
        if type(self.session_date) is not date:
            raise ValueError('Declared binding requires resolved session date')

    def verify(self, payload, filename, session_date):
        if (type(payload) is not bytes or len(payload) != self.size
                or hashlib.sha256(payload).hexdigest() != self.sha256
                or filename != self.filename or session_date != self.session_date):
            raise ValueError('Declared proximity bytes disagree with trusted binding')
        identity = proximity_header_identity(StringIO(payload.decode('utf-8')), filename)
        if identity is None or identity.source_id != self.source_id:
            raise ValueError('Declared proximity source disagrees with trusted binding')
        map_name = filename[18:].rsplit('-round-', 1)[0]
        return identity, map_name


@dataclass(frozen=True)
class ResolvedDeclaredParent:
    round_id: int
    gaming_session_id: int


_MAPPING_COLUMNS = ('source_key', 'round_key', 'match_key', 'round_number', 'first_round_key',
                    'map_name', 'filename', 'canonical_round_id', 'payload_sha256')


async def resolve_declared_parent(adapter, identity, map_name, *, lock=True):
    """Read a consistent transaction; writers lock, snapshot observers do not.

    Adapter supplies fetch_one(query, params). Caller must own the transaction;
    read-only observers need repeatable_read across these related reads.
    """
    if not isinstance(identity, RoundIdentity) or type(lock) is not bool:
        raise ValueError('Explicit identity and mapping lock policy required')
    suffix = ' FOR SHARE' if lock else ''

    async def mapped(expected):
        row = await adapter.fetch_one('SELECT ' + ','.join(_MAPPING_COLUMNS) +
            ' FROM runtime_round_mappings WHERE source_key=? AND round_key=?' + suffix,
            (expected.source_id, expected.round_id))
        if row is None:
            raise DeclaredMappingPending('declared_identity_mapping_pending')
        row = dict(zip(_MAPPING_COLUMNS, row, strict=True))
        if tuple(row[key] for key in _MAPPING_COLUMNS[:6]) != (
            expected.source_id, expected.round_id, expected.match_id, expected.round_number,
            expected.first_round_id, map_name,
        ):
            raise ValueError('Declared proximity mapping conflicts with source identity')
        pattern = rf'\d{{4}}-\d{{2}}-\d{{2}}-\d{{6}}-{re.escape(map_name)}-round-{expected.round_number}\.txt'
        if re.fullmatch(pattern, row['filename']) is None:
            raise ValueError('Mapped stats filename conflicts with declared identity')
        return row

    async def parent(row, first_filename):
        canonical = await adapter.fetch_one(
            'SELECT map_name,round_number,gaming_session_id,match_id,round_date,round_time '
            'FROM rounds WHERE id=?' + suffix, (row['canonical_round_id'],))
        if (canonical is None or canonical[2] is None
                or tuple(canonical) != (map_name, row['round_number'], canonical[2], first_filename[:17],
                                       row['filename'][:10], row['filename'][11:17])):
            raise ValueError('Mapped canonical parent missing or changed')
        event = await adapter.fetch_one(
            'SELECT source_filename,source_payload_sha256,validation_passed,round_number,gaming_session_id '
            "FROM runtime_events WHERE round_id=? AND event_type='round_stats_imported'" + suffix,
            (row['canonical_round_id'],))
        if event is None or tuple(event) != (row['filename'], row['payload_sha256'], True,
                                           row['round_number'], canonical[2]):
            raise ValueError('Mapped canonical journal missing or changed')
        return ResolvedDeclaredParent(row['canonical_round_id'], canonical[2])

    row = await mapped(identity)
    first_filename = row['filename']
    if identity.round_number == 2:
        first = await mapped(RoundIdentity(identity.source_id, identity.match_id, identity.first_round_id,
                                           1, identity.first_round_id))
        first_filename = first['filename']
        await parent(first, first_filename)
    return await parent(row, first_filename)


# All canonical per-round INSERT targets. Full-schema access is required; do not
# turn a missing column/table into permission to import unlinked child rows.
ROUND_TABLES = (
    'combat_engagement', 'player_track', 'proximity_focus_fire', 'proximity_kill_outcome',
    'proximity_hit_region', 'proximity_combat_position', 'proximity_shot_fired', 'proximity_aim_lock',
    'proximity_spawn_select', 'proximity_skill_snapshot', 'proximity_comm_event', 'proximity_carrier_event',
    'proximity_carrier_kill', 'proximity_carrier_return', 'proximity_vehicle_progress',
    'proximity_escort_credit', 'proximity_construction_event', 'proximity_objective_run',
    'proximity_objective_focus', 'proximity_spawn_timing', 'proximity_team_cohesion',
    'proximity_crossfire_opportunity', 'proximity_team_push', 'proximity_lua_trade_kill',
    'proximity_trade_event', 'proximity_reaction_metric', 'proximity_support_summary',
    'proximity_revive', 'proximity_weapon_accuracy',
)


async def reject_existing_children(adapter, parent, metadata, session_date):
    """Refuse first-import legacy/natural-key overlap, never silently skip rows.

    Twenty-seven natural keys include date/half/start; revive and accuracy omit
    date and map nonpositive start to NULL. This deliberately over-rejects rows,
    rather than adopting prior partial/legacy data. Excludes global aggregates.
    """
    for table in ROUND_TABLES:
        start = metadata.get('round_start_unix', 0)
        special = table in ('proximity_revive', 'proximity_weapon_accuracy')
        if special:
            start = start if start and start > 0 else None
        date_clause = '' if special else 'session_date=? AND '
        params = (parent.round_id,) + (() if special else (session_date,)) + (metadata['round_num'], start)
        row = await adapter.fetch_one(
            f'SELECT EXISTS (SELECT 1 FROM {table} WHERE round_id=? OR '
            f'({date_clause}round_number=? AND round_start_unix IS NOT DISTINCT FROM ?))', params)
        if row is None or row[0] is not False:
            raise ValueError('Existing proximity child scope requires reconciliation')


def provenance_values(binding, identity, parent):
    return (binding.source_id, binding.generation, identity.round_id, binding.size,
            binding.sha256, binding.session_date, parent.round_id)


async def validate_declared_receipt(adapter, binding, identity, parent):
    """Caller owns receipt lock or stable read snapshot; no legacy adoption."""
    receipt = await adapter.fetch_one(
        'SELECT file_hash,runtime_parent_gate,aggregates_applied,linked_round_id '
        'FROM proximity_processed_files WHERE filename=?', (binding.filename,))
    proof = await adapter.fetch_one(
        'SELECT source_key,generation,round_key,source_size,source_sha256,session_date,canonical_round_id '
        'FROM runtime_proximity_mappings WHERE filename=?', (binding.filename,))
    if (receipt is None or tuple(receipt) != (binding.sha256, True, True, parent.round_id)
            or proof is None or tuple(proof) != provenance_values(binding, identity, parent)):
        raise ValueError('Declared proximity receipt provenance missing or conflicting')


async def import_declared_proximity(parser, binding, payload, filename, session_date, run_steps):
    """Entire declared import, including direct parser calls, under ONE transaction.

    Exact replay verifies evidence and skips ALL child/aggregate writes. New
    provenance may never be attached to any preexisting receipt, even unfinished.
    Caller must use read_committed writer isolation and exclusive legacy handover.
    """
    from proximity.parser.import_receipt import claim_import_receipt

    identity, map_name = binding.verify(payload, filename, session_date)
    adapter = parser.db_adapter
    # Acquire before reading receipt/child state. This serializes declared first
    # imports across different filenames whose legacy child keys can collide.
    await adapter.fetch_one("SELECT pg_advisory_xact_lock(hashtextextended('slomix-declared-proximity-v1',0))")
    isolation = await adapter.fetch_one('SHOW transaction_isolation')
    if isolation is None or isolation[0] != 'read committed':
        raise ValueError('Declared import requires read committed writer transaction')
    parent = await resolve_declared_parent(adapter, identity, map_name)
    parser._round_link_context = {  # noqa: SLF001 -- canonical parser integration seam
        'round_id': parent.round_id, 'round_link_source': 'runtime_round_mapping',
        'round_link_reason': 'declared_identity_verified', 'round_linked_at': None,
    }
    existing = await adapter.fetch_one('SELECT filename FROM proximity_processed_files WHERE filename=? FOR UPDATE',
                                       (filename,))
    if existing is not None:
        await validate_declared_receipt(adapter, binding, identity, parent)
        return parent
    await reject_existing_children(adapter, parent, parser.metadata, session_date)
    await claim_import_receipt(adapter, filename, source_sha256=binding.sha256, require_linked_parent=True)
    await run_steps()
    if await resolve_declared_parent(adapter, identity, map_name) != parent:
        raise ValueError('Declared proximity parent changed during import')
    await record_receipt_parent(adapter, filename, parent.round_id)
    await adapter.execute(
        'INSERT INTO runtime_proximity_mappings '
        '(filename,source_key,generation,round_key,source_size,source_sha256,session_date,canonical_round_id) '
        'VALUES (?,?,?,?,?,?,?,?)', (filename, *provenance_values(binding, identity, parent)))
    await validate_declared_receipt(adapter, binding, identity, parent)
    return parent
