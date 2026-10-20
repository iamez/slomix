"""One caller-driven team page; no scheduler, pool, startup or source ACK."""

from dataclasses import dataclass
from typing import Literal

from shared.runtime_team_consumer import TeamConsumption, consume_team_event, team_consumer_enabled
from shared.runtime_team_discovery import TeamScanHint, discover_team_events


@dataclass(frozen=True)
class TeamBatchItem:
    event_id: int
    outcome: TeamConsumption


@dataclass(frozen=True)
class TeamBatch:
    status: Literal['disabled', 'idle', 'page']
    items: tuple[TeamBatchItem, ...]
    next_hint: TeamScanHint | None


async def consume_team_page(conn, *, batch_size: int = 100,
                            hint: TeamScanHint | None = None) -> TeamBatch:
    """Discover once, then consume eligible events serially in own transactions.

    Caller owns an exclusive connection and deadline. Reject a surrounding
    transaction before discovery: each existing consumer must commit its own
    effect and receipt, and later pages need fresh statement snapshots.
    Metadata exclusions stay pending without invoking the writer. Eligible
    candidates are revalidated by the existing consumer, including roster policy.

    Exceptions and cancellation propagate. Earlier events may already have
    committed; retry with the ORIGINAL input hint and durable receipts suppress
    duplicate effects. No new hint is returned on error. If a gate check before
    a remaining item or its consumer reports disabled, return completed items
    and the original retry hint. A fully completed page may still advance if
    the gate closes during its final successful consumer call.
    Never persist a scan hint as an ACK. A page is not an atomic batch, backlog
    total, wall-clock work bound or worker. No retries or background tasks here.
    """
    if not team_consumer_enabled():
        return TeamBatch('disabled', (), hint)
    if conn.is_in_transaction():
        raise RuntimeError('Team page requires its own consumer transactions')
    page = await discover_team_events(conn, batch_size=batch_size, hint=hint)
    if page.status == 'disabled':
        return TeamBatch('disabled', (), hint)
    items = []
    for candidate in page.candidates:
        if not team_consumer_enabled():
            return TeamBatch('disabled', tuple(items), hint)
        if candidate.eligible:
            outcome = await consume_team_event(conn, event_id=candidate.event_id)
            if outcome.status == 'disabled':
                return TeamBatch('disabled', tuple(items), hint)
        else:
            outcome = TeamConsumption('pending', candidate.reason)
        items.append(TeamBatchItem(candidate.event_id, outcome))
    return TeamBatch(page.status, tuple(items), page.next_hint)
