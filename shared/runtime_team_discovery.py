"""Read-only team-event discovery; no assignment, receipt, task or service startup."""

from dataclasses import dataclass
from typing import Literal

from shared.runtime_team_consumer import CONSUMER, team_consumer_enabled

_BIGINT_MAX = 9223372036854775807


@dataclass(frozen=True)
class TeamScanHint:
    """Scheduling position inside a finite sweep, NEVER an acknowledgement."""

    after_id: int
    through_id: int

    def __post_init__(self):
        if (type(self.after_id) is not int or type(self.through_id) is not int
                or not 0 <= self.after_id < self.through_id <= _BIGINT_MAX):
            raise ValueError('Team scan hint requires ordered PostgreSQL bigint bounds')


@dataclass(frozen=True)
class TeamCandidate:
    event_id: int
    reason: Literal['unsupported_event', 'not_round_one', 'validation_unavailable'] | None

    @property
    def eligible(self) -> bool:
        """Metadata only; consume_team_event must still recheck all effect guards."""
        return self.reason is None


@dataclass(frozen=True)
class TeamDiscovery:
    status: Literal['disabled', 'idle', 'page']
    candidates: tuple[TeamCandidate, ...]
    next_hint: TeamScanHint | None


# One statement snapshot for both the sweep fence and candidates. The left join
# returns the fence even when no unreceipted row exists. Page size limits returned
# rows, not underlying index/anti-join scan work or execution time.
_DISCOVER = """
    WITH sweep AS (
        SELECT COALESCE($3::bigint, (SELECT COALESCE(max(id), 0) FROM runtime_events)) AS through_id
    )
    SELECT sweep.through_id, candidate.*
    FROM sweep
    LEFT JOIN LATERAL (
        SELECT e.id, e.event_type, e.schema_version, e.round_number, e.validation_passed
        FROM runtime_events e
        WHERE e.id > $2 AND e.id <= sweep.through_id
          AND NOT EXISTS (
              SELECT 1 FROM runtime_consumer_receipts r
              WHERE r.consumer_name=$1 AND r.event_id=e.id
          )
        ORDER BY e.id LIMIT $4
    ) candidate ON true
    ORDER BY candidate.id
"""


async def discover_team_events(conn, *, batch_size: int = 100,
                               hint: TeamScanHint | None = None) -> TeamDiscovery:
    """Read one finite-sweep page with explicit per-candidate exclusions.

    Both event/team gates default off; disabled touches no connection. Caller
    owns connection, timeout and transaction isolation. To see later commits,
    later calls must use fresh statement snapshots (not a long repeatable read).
    Pass next_hint into the next call even if an effect remains pending. None
    starts a NEW sweep from zero: lower IDs may have committed after a previous
    page. Never replace the durable receipt with this scheduling hint. Forgetting
    a hint is safe but may repeat work; a caller that never advances can starve.

    The finite fence keeps continuous new high IDs from preventing another sweep.
    Unsupported event/schema, non-R1 and unvalidated rows remain unacknowledged
    and are reported only within this page, not counted as a total backlog. An
    eligible candidate still needs the existing consumer's schema, canonical
    identity and roster checks. This function never invokes that writer.
    Errors/cancellation propagate without manufacturing an empty or advanced page.
    """
    if not team_consumer_enabled():
        return TeamDiscovery('disabled', (), None)
    if type(batch_size) is not int or not 1 <= batch_size <= 1000:
        raise ValueError('Team discovery batch size must be an integer from 1 to 1000')
    if hint is not None and not isinstance(hint, TeamScanHint):
        raise ValueError('Team discovery requires an explicit scan hint or None')
    rows = await conn.fetch(_DISCOVER, CONSUMER, hint.after_id if hint else 0,
                            hint.through_id if hint else None, batch_size)
    # The statement always returns at least its fence row, even for an empty DB.
    if not rows:
        raise RuntimeError('Team discovery did not return its sweep fence')
    through_id = rows[0]['through_id']
    candidates = []
    for row in rows:
        if row['id'] is None:
            continue
        if row['event_type'] != 'round_stats_imported' or row['schema_version'] != 1:
            reason = 'unsupported_event'
        elif row['round_number'] != 1:
            reason = 'not_round_one'
        elif row['validation_passed'] is not True:
            reason = 'validation_unavailable'
        else:
            reason = None
        candidates.append(TeamCandidate(row['id'], reason))
    next_hint = None
    if len(candidates) == batch_size and candidates[-1].event_id < through_id:
        next_hint = TeamScanHint(candidates[-1].event_id, through_id)
    return TeamDiscovery('page' if candidates else 'idle', tuple(candidates), next_hint)
