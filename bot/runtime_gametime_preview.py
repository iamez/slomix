"""Sealed-source dry run for a bounded timing fill, never a write authorization."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from bot.runtime_gametime_correlation import verified_timing_binding

TIMING_FILL_FIELDS = ('actual_duration_seconds', 'total_pause_seconds', 'pause_count')


@dataclass(frozen=True)
class TimingFieldChange:
    field: str
    before: int | None
    after: int


@dataclass(frozen=True)
class TimingFillPreview:
    status: Literal['proposed', 'conflict', 'unavailable', 'existing_values_unproven']
    reason: str
    round_id: int
    source_id: str
    generation: str
    source_sha256: str
    changes: tuple[TimingFieldChange, ...] = ()


def preview_declared_timing_fill(source_fd, current: Mapping, **binding) -> TimingFillPreview:
    """Calculate a conservative diff from admitted bytes and an untrusted row.

    No DB, network, writes, canonical linkage or receipt verification. Caller
    owns descriptor and trusted expected identity. A proposed diff is not a
    reusable write token: future writer must lock/revalidate097-101, refuse
    legacy/application receipts, and recompute from its fresh locked round.

    Existing equal values WITHOUT an application receipt are unproven, not an
    idempotent success. NULL duration and NULL/default-zero pause columns are
    the only fill candidate. Source wall clocks are evidence, never new round
    keys or player durations; no timestamp/canonical/player fields are proposed.
    """
    timing, projection = verified_timing_binding(source_fd, **binding)
    return preview_timing_values(timing, projection, current)


def preview_timing_values(timing, projection, current: Mapping) -> TimingFillPreview:
    """Internal pure policy for the already-admitted snapshot; not admission."""
    if not isinstance(current, Mapping):
        raise ValueError('Timing preview requires an explicit round row')
    required = ('id', 'map_name', 'round_number', *TIMING_FILL_FIELDS)
    if any(key not in current for key in required):
        raise ValueError('Timing preview round row is incomplete')
    if type(current['id']) is not int or not 0 < current['id'] <= 2_147_483_647:
        raise ValueError('Timing preview requires a positive PostgreSQL INTEGER round ID')
    if (not isinstance(current['map_name'], str)
            or type(current['round_number']) is not int or current['round_number'] not in (1, 2)):
        raise ValueError('Timing preview requires a valid R1/R2 round')
    for field in TIMING_FILL_FIELDS:
        value = current[field]
        if value is not None and (type(value) is not int or not 0 <= value <= 2_147_483_647):
            raise ValueError(f'Invalid current timing preview field: {field}')

    def result(status, reason, changes=()):
        return TimingFillPreview(status, reason, current['id'], timing.source_id,
                                 timing.generation, timing.sha256, changes)

    if (current['map_name'].strip().lower(), current['round_number']) != (
            projection['map_name'], timing.round_number):
        return result('conflict', 'round_map_or_half_mismatch')
    if timing.actual_duration_seconds == 0:
        return result('unavailable', 'zero_duration_not_a_fill')
    # Retention accepts underfilled intervals; application must not invent the
    # missing seconds or silently present an unexplained gap as measured play.
    if timing.actual_duration_seconds + timing.total_pause_seconds != timing.round_end_unix - timing.round_start_unix:
        return result('conflict', 'source_timing_ledger_unbalanced')
    if timing.pause_count == 0 and timing.total_pause_seconds != 0:
        return result('conflict', 'source_pause_ledger_inconsistent')
    if all(current[field] == projection[field] for field in TIMING_FILL_FIELDS):
        return result('existing_values_unproven', 'matching_values_without_application_receipt')
    if current['actual_duration_seconds'] is not None:
        return result('conflict', 'existing_duration_requires_reconciliation')
    if any(current[field] not in (None, 0) for field in TIMING_FILL_FIELDS[1:]):
        return result('conflict', 'existing_pause_measurement_requires_reconciliation')
    changes = tuple(TimingFieldChange(field, current[field], projection[field])
                    for field in TIMING_FILL_FIELDS if current[field] != projection[field])
    return result('proposed', 'null_duration_fill_preview_only', changes)
