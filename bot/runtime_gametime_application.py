"""Opt-in atomic three-field timing fill, with exact replay and independent proof."""

import hashlib
import json
from dataclasses import dataclass

from bot.runtime_gametime_correlation import verified_timing_binding
from bot.runtime_gametime_link import _COLUMNS, _values, inspect_link_snapshot
from bot.runtime_gametime_preview import TIMING_FILL_FIELDS, preview_timing_values
from bot.services.lua_correction_inbox import lock_correction_identity


@dataclass(frozen=True)
class TimingApplicationResult:
    status: str
    reason: str
    round_id: int | None = None
    event_id: int | None = None


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _decode(value):
    return json.loads(value) if isinstance(value, str) else value


def _details(link, before, after):
    return dict(source='declared_gametime_v1', link=link,
                before={field: before[field] for field in TIMING_FILL_FIELDS}, after=after,
                before_round_sha256=hashlib.sha256(_json(before).encode('utf-8')).hexdigest(),
                player_timing_changed=False)


async def _state(connection, timing, projection, identity, *, lock):
    linked = await inspect_link_snapshot(connection, timing, identity, projection, lock=lock)
    if linked.status != 'linked':
        return TimingApplicationResult(linked.status, linked.reason), None
    row = await connection.fetchrow(
        'SELECT to_jsonb(r) AS snapshot FROM rounds r WHERE id=$1' + (' FOR UPDATE' if lock else ''),
        linked.round_id)
    if row is None:
        return TimingApplicationResult('conflict', 'canonical_round_missing'), None
    current = _decode(row['snapshot'])
    link = dict(zip(_COLUMNS, _values(timing, identity, projection, linked), strict=True))
    after = {field: projection[field] for field in TIMING_FILL_FIELDS}
    receipt = await connection.fetchrow(
        'SELECT canonical_round_id,event_id,link_snapshot,before_round,after_values '
        'FROM runtime_gametime_applications WHERE source_key=$1 AND generation=$2'
        + (' FOR SHARE' if lock else ''), timing.source_id, timing.generation)
    state = (linked, current, link, after)
    if receipt is None:
        if await connection.fetchval(
                "SELECT 1 FROM runtime_events WHERE round_id=$1 "
                "AND event_type IN ('round_timing_reconciled','round_lua_corrected') LIMIT 1", linked.round_id):
            return TimingApplicationResult('conflict', 'unreceipted_timing_event_present'), None
        return None, state
    # Stored preimage must itself be an eligible fill, not an adopted old row.
    try:
        before = _decode(receipt['before_round'])
        preview = preview_timing_values(timing, projection, before)
        if (receipt['canonical_round_id'] != linked.round_id
                or before['id'] != linked.round_id
                or before['gaming_session_id'] != current['gaming_session_id']
                or preview.status != 'proposed'
                or _json(_decode(receipt['link_snapshot'])) != _json(link)
                or _json(_decode(receipt['after_values'])) != _json(after)
                or _json({field: current[field] for field in TIMING_FILL_FIELDS}) != _json(after)):
            return TimingApplicationResult('conflict', 'application_receipt_or_state_conflict'), None
        event = await connection.fetchrow(
            'SELECT event_type,schema_version,round_id,round_number,gaming_session_id,event_details '
            'FROM runtime_events WHERE id=$1' + (' FOR SHARE' if lock else ''), receipt['event_id'])
        if (event is None or tuple(event[key] for key in (
                'event_type', 'schema_version', 'round_id', 'round_number', 'gaming_session_id')) != (
                'round_timing_reconciled', 1, linked.round_id, identity.round_number, current['gaming_session_id'])
                or _json(_decode(event['event_details'])) != _json(_details(link, before, after))):
            return TimingApplicationResult('conflict', 'application_event_conflict'), None
    except (ValueError, TypeError, KeyError):
        return TimingApplicationResult('conflict', 'application_receipt_or_state_conflict'), None
    return TimingApplicationResult('applied', 'matching_application_visible', linked.round_id, receipt['event_id']), state


async def apply_declared_gametime(adapter, source_fd, **binding):
    """Fill only three missing/default timing scalars and atomically retain proof.

    Requires an existing exact101 link and exclusive legacy-writer handover.
    No clock selection, implicit link, historical adoption, player/canonical
    change, scheduler or source ACK. Adapter yields its native connection;
    success inside an outer transaction does not confirm that outer commit.
    Failures/cancellation propagate so the transaction rolls back everything.
    Caller must not pre-hold conflicting input/parent locks before the correction
    advisory lock. Composing unrelated workflows in one outer tx is not covered.
    """
    timing, projection = verified_timing_binding(source_fd, **binding)
    identity = binding['expected_identity']
    async with adapter.transaction() as connection:
        if await connection.fetchval('SHOW transaction_isolation') != 'read committed':
            raise ValueError('Timing application requires read committed writer transaction')
        await lock_correction_identity(adapter, timing.source_id, projection)
        observed, state = await _state(connection, timing, projection, identity, lock=True)
        if observed is not None:
            if observed.status == 'applied':
                return TimingApplicationResult('already_applied', observed.reason, observed.round_id, observed.event_id)
            return observed
        linked, current, link, after = state
        preview = preview_timing_values(timing, projection, current)
        if preview.status != 'proposed':
            return TimingApplicationResult(preview.status, preview.reason)
        await connection.execute(
            'UPDATE rounds SET actual_duration_seconds=$1,total_pause_seconds=$2,pause_count=$3 WHERE id=$4',
            *(after[field] for field in TIMING_FILL_FIELDS), linked.round_id)
        actual = await connection.fetchrow('SELECT actual_duration_seconds,total_pause_seconds,pause_count '
                                            'FROM rounds WHERE id=$1', linked.round_id)
        if actual is None or _json(dict(actual)) != _json(after):
            raise ValueError('Timing application read-back mismatch')
        details = _details(link, current, after)
        event_id = await connection.fetchval(
            "INSERT INTO runtime_events(event_type,schema_version,round_id,round_number,gaming_session_id,event_details) "
            "VALUES ('round_timing_reconciled',1,$1,$2,$3,$4::jsonb) RETURNING id",
            linked.round_id, identity.round_number, current['gaming_session_id'], _json(details))
        await connection.execute(
            'INSERT INTO runtime_gametime_applications '
            '(source_key,generation,canonical_round_id,event_id,link_snapshot,before_round,after_values) '
            'VALUES ($1,$2,$3,$4,$5::jsonb,$6::jsonb,$7::jsonb)',
            timing.source_id, timing.generation, linked.round_id, event_id, _json(link), _json(current), _json(after))
        await connection.execute("SELECT pg_notify('round_events',$1)", str(event_id))
        return TimingApplicationResult('applied', 'atomic_timing_fill', linked.round_id, event_id)


async def inspect_declared_gametime_application(observer, source_fd, **binding):
    """Committed application proof in a fresh readonly snapshot; never repairs."""
    timing, projection = verified_timing_binding(source_fd, **binding)
    if observer.is_in_transaction() is not False:
        raise RuntimeError('Timing application observation requires a connection outside any transaction')
    async with observer.transaction(isolation='repeatable_read', readonly=True):
        observed, _ = await _state(observer, timing, projection, binding['expected_identity'], lock=False)
        return observed or TimingApplicationResult('not_applied', 'application_receipt_missing')
