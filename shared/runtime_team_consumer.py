"""Explicit single-event team effect; no polling, source ACK or startup wiring."""

import os
from dataclasses import dataclass
from datetime import date

from shared.import_team_assignment import TeamAssignment, assign_round_teams
from shared.runtime_events import event_stream_enabled
from shared.team_identity import has_modern_team_identity
from shared.team_write_guard import team_write_transaction

CONSUMER = 'round-team-assignment-v1'


@dataclass(frozen=True)
class TeamConsumption:
    status: str
    reason: str | None = None


def team_consumer_enabled() -> bool:
    """Discovery and execution share the same two explicit, default-off gates."""
    return (event_stream_enabled()
            and os.getenv('RUNTIME_TEAM_EVENTS_ENABLED', 'false').strip().lower() == 'true')


async def consume_team_event(conn, *, event_id: int) -> TeamConsumption:
    """Own effect+receipt transaction under the cooperative team writer guard.

    Existing rosters remain pending even if legacy assignment calls them complete.
    Only this invocation's new assignment is acknowledged. No admission of manual
    rosters, retry loop, event discovery or promise of cross-writer exclusion.
    Errors/cancellation propagate; caller owns connection lifetime and deadlines.
    """
    if not team_consumer_enabled():
        return TeamConsumption('disabled')
    if type(event_id) is not int or not 0 < event_id <= 9223372036854775807:
        raise ValueError('event_id must be a positive PostgreSQL bigint')
    if conn.is_in_transaction():
        raise RuntimeError('Team consumer requires its own transaction')
    async with team_write_transaction(conn):
        if await conn.fetchval(
            'SELECT EXISTS(SELECT 1 FROM runtime_consumer_receipts WHERE consumer_name=$1 AND event_id=$2)',
            CONSUMER, event_id,
        ):
            return TeamConsumption('already_processed')
        modern_identity = await has_modern_team_identity(conn)
        if modern_identity is not True:
            return TeamConsumption('pending', 'schema_unavailable')
        event = await conn.fetchrow('SELECT * FROM runtime_events WHERE id=$1', event_id)
        if event is None:
            return TeamConsumption('pending', 'event_missing')
        if event['event_type'] != 'round_stats_imported' or event['schema_version'] != 1:
            return TeamConsumption('pending', 'unsupported_event')
        if event['round_number'] != 1:
            return TeamConsumption('pending', 'not_round_one')
        if event['validation_passed'] is not True:
            return TeamConsumption('pending', 'validation_unavailable')
        round_row = await conn.fetchrow(
            'SELECT round_number, gaming_session_id, round_date FROM rounds WHERE id=$1 FOR SHARE',
            event['round_id'],
        )
        if round_row is None:
            return TeamConsumption('pending', 'round_missing')
        if (round_row['round_number'] != 1 or event['gaming_session_id'] is None
                or round_row['gaming_session_id'] != event['gaming_session_id']):
            return TeamConsumption('pending', 'identity_mismatch')
        session_date = round_row['round_date']
        try:
            valid_date = isinstance(session_date, str) and date.fromisoformat(session_date).isoformat() == session_date
        except ValueError:
            valid_date = False
        if not valid_date:
            return TeamConsumption('pending', 'date_unavailable')
        outcome = await assign_round_teams(conn, round_id=event['round_id'], session_date=session_date)
        if outcome is not TeamAssignment.ASSIGNED:
            return TeamConsumption('pending', str(outcome))
        await conn.execute(
            'INSERT INTO runtime_consumer_receipts(consumer_name,event_id) VALUES ($1,$2)',
            CONSUMER, event_id,
        )
    return TeamConsumption('processed')
