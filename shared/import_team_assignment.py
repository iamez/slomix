"""Connection-owned legacy team assignment with explicit outcomes and SQL errors.

Legacy assignment SQL is preserved, but unresolved date-only manual ownership
blocks ID-scoped assignment. Uses the cooperative team writer guard.
"""

import logging
from datetime import UTC, datetime
from enum import StrEnum

from shared.team_identity import (
    UNRESOLVED_TEAM_IDENTITY_SQL,
    require_resolved_team_identity,
)
from shared.team_write_guard import team_write_transaction

logger = logging.getLogger('bot.database.manager')


class TeamAssignment(StrEnum):
    ASSIGNED = 'assigned'
    ROUND_MISSING = 'round_missing'
    NOT_ROUND_ONE = 'not_round_one'
    DEFENDER_UNAVAILABLE = 'defender_unavailable'
    ALREADY_ASSIGNED = 'already_assigned'
    NO_PLAYERS = 'no_players'
    UNBALANCED = 'unbalanced'


async def assign_round_teams(conn, *, round_id: int, session_date: str) -> TeamAssignment:
    """Guard the full operation before any roster read, using a borrowed connection.

    Busy/error/cancellation propagates; no receipt, retry or acknowledgement.
    Only participating writers share exclusion. Unresolved manual identity raises
    TeamIdentityConflict; this must remain pending, never a successful receipt.
    """
    async with team_write_transaction(conn):
        return await _assign_round_teams(conn, round_id=round_id, session_date=session_date)


async def _assign_round_teams(conn, *, round_id: int, session_date: str) -> TeamAssignment:
    """Borrow a native connection; never acquire/close a pool or acknowledge events.

    SQL failures and cancellation propagate. Caller owns the connection and any
    outer transaction; the two team writes share a transaction/savepoint. A no-op
    is not permission to acknowledge an event. Historical schema branches/date
    fallback are preserved for legacy callers. Durable consumption still requires
    current schema, session identity and serialization with other team writers.
    Naive local created_at timestamps retain the legacy storage convention.
    """
    # Get defender_team and verify this is Round 1
    round_info = await conn.fetchrow(
        """
        SELECT defender_team, winner_team, round_number, gaming_session_id
        FROM rounds
        WHERE id = $1
        """,
        round_id
    )

    if not round_info:
        logger.debug(f"Round {round_id} not found for auto-team assignment")
        return TeamAssignment.ROUND_MISSING

    # Only process Round 1
    if round_info['round_number'] != 1:
        logger.debug(f"Round {round_id} is R{round_info['round_number']}, skipping auto-team")
        return TeamAssignment.NOT_ROUND_ONE

    defender_team = round_info['defender_team']
    gaming_session_id = round_info['gaming_session_id']

    has_session_teams_gaming_session_id = await conn.fetchval(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'session_teams'
              AND column_name = 'gaming_session_id'
        )
        """
    )
    has_session_teams_identity = await conn.fetchval(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'session_teams'
              AND column_name = 'session_identity'
        )
        """
    )

    # If defender_team is 0 (not set), skip
    if defender_team == 0:
        logger.debug(f"Round {round_id} has no defender_team, skipping auto-team")
        return TeamAssignment.DEFENDER_UNAVAILABLE

    # Check if teams already assigned for this session
    if has_session_teams_gaming_session_id and gaming_session_id is not None:
        # Never infer ownership from a date, even when only one session is known.
        # Include every recorded day of the target session for midnight crossings.
        unresolved_manual_scope = await conn.fetchval(
            UNRESOLVED_TEAM_IDENTITY_SQL,
            gaming_session_id, session_date,
        )
        require_resolved_team_identity(unresolved_manual_scope)
        existing = await conn.fetchval(
            """
            SELECT COUNT(*) FROM session_teams
            WHERE gaming_session_id = $1
              AND map_name = 'ALL'
            """,
            gaming_session_id
        )
    else:
        existing = await conn.fetchval(
            """
            SELECT COUNT(*) FROM session_teams
            WHERE session_start_date LIKE ($1 || '%')
              AND map_name = 'ALL'
            """,
            session_date
        )

    if existing > 0:
        logger.debug(
            f"Session already has teams assigned "
            f"(date={session_date}, gaming_session_id={gaming_session_id})"
        )
        return TeamAssignment.ALREADY_ASSIGNED

    # Query all players from R1 and their team (axis=1, allies=2)
    players = await conn.fetch(
        """
        SELECT player_guid, player_name, team
        FROM player_comprehensive_stats
        WHERE round_id = $1
        ORDER BY team, player_name
        """,
        round_id
    )

    if not players:
        logger.debug(f"No players found for round {round_id}")
        return TeamAssignment.NO_PLAYERS

    # Split into two teams based on defender_team
    team_a_players = []  # Defenders in R1
    team_b_players = []  # Attackers in R1

    for player in players:
        if player['team'] == defender_team:
            team_a_players.append(player)
        elif player['team'] in (1, 2) and player['team'] != defender_team:
            team_b_players.append(player)
        else:
            # Skip spectators (team=0) or other invalid teams (team=3, etc.)
            logger.debug(f"Skipping non-team player {player['player_name']} (team={player['team']})")

    # Need at least one player per team
    if not team_a_players or not team_b_players:
        logger.warning(
            f"Unbalanced teams in R1 (round_id={round_id}): "
            f"{len(team_a_players)} defenders vs {len(team_b_players)} attackers"
        )
        return TeamAssignment.UNBALANCED

    # Extract GUIDs and names
    team_a_guids = [p['player_guid'] for p in team_a_players]
    team_a_names = [p['player_name'] for p in team_a_players]
    team_b_guids = [p['player_guid'] for p in team_b_players]
    team_b_names = [p['player_name'] for p in team_b_players]

    # Insert into session_teams
    async with conn.transaction():
        # Insert Team A (defenders)
        # JSONB columns require JSON strings, not Python lists
        import json
        if has_session_teams_gaming_session_id:
            if has_session_teams_identity:
                await conn.execute(
                    """
                    INSERT INTO session_teams
                    (session_start_date, map_name, team_name, player_guids, player_names, created_at, gaming_session_id)
                    VALUES ($1, 'ALL', 'Team A', $2::jsonb, $3::jsonb, $4, $5)
                    ON CONFLICT (session_identity, map_name, team_name) DO UPDATE SET
                        player_guids = EXCLUDED.player_guids,
                        player_names = EXCLUDED.player_names,
                        created_at = EXCLUDED.created_at,
                        gaming_session_id = EXCLUDED.gaming_session_id
                    """,
                    session_date,
                    json.dumps(team_a_guids),
                    json.dumps(team_a_names),
                    datetime.now(UTC).astimezone().replace(tzinfo=None),
                    gaming_session_id,
                )

                # Insert Team B (attackers)
                await conn.execute(
                    """
                    INSERT INTO session_teams
                    (session_start_date, map_name, team_name, player_guids, player_names, created_at, gaming_session_id)
                    VALUES ($1, 'ALL', 'Team B', $2::jsonb, $3::jsonb, $4, $5)
                    ON CONFLICT (session_identity, map_name, team_name) DO UPDATE SET
                        player_guids = EXCLUDED.player_guids,
                        player_names = EXCLUDED.player_names,
                        created_at = EXCLUDED.created_at,
                        gaming_session_id = EXCLUDED.gaming_session_id
                    """,
                    session_date,
                    json.dumps(team_b_guids),
                    json.dumps(team_b_names),
                    datetime.now(UTC).astimezone().replace(tzinfo=None),
                    gaming_session_id,
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO session_teams
                    (session_start_date, map_name, team_name, player_guids, player_names, created_at, gaming_session_id)
                    VALUES ($1, 'ALL', 'Team A', $2::jsonb, $3::jsonb, $4, $5)
                    ON CONFLICT (session_start_date, map_name, team_name) DO UPDATE SET
                        player_guids = EXCLUDED.player_guids,
                        player_names = EXCLUDED.player_names,
                        created_at = EXCLUDED.created_at,
                        gaming_session_id = EXCLUDED.gaming_session_id
                    """,
                    session_date,
                    json.dumps(team_a_guids),
                    json.dumps(team_a_names),
                    datetime.now(UTC).astimezone().replace(tzinfo=None),
                    gaming_session_id,
                )

                # Insert Team B (attackers)
                await conn.execute(
                    """
                    INSERT INTO session_teams
                    (session_start_date, map_name, team_name, player_guids, player_names, created_at, gaming_session_id)
                    VALUES ($1, 'ALL', 'Team B', $2::jsonb, $3::jsonb, $4, $5)
                    ON CONFLICT (session_start_date, map_name, team_name) DO UPDATE SET
                        player_guids = EXCLUDED.player_guids,
                        player_names = EXCLUDED.player_names,
                        created_at = EXCLUDED.created_at,
                        gaming_session_id = EXCLUDED.gaming_session_id
                    """,
                    session_date,
                    json.dumps(team_b_guids),
                    json.dumps(team_b_names),
                    datetime.now(UTC).astimezone().replace(tzinfo=None),
                    gaming_session_id,
                )
        else:
            if has_session_teams_identity:
                await conn.execute(
                    """
                    INSERT INTO session_teams
                    (session_start_date, map_name, team_name, player_guids, player_names, created_at)
                    VALUES ($1, 'ALL', 'Team A', $2::jsonb, $3::jsonb, $4)
                    ON CONFLICT (session_identity, map_name, team_name) DO UPDATE SET
                        player_guids = EXCLUDED.player_guids,
                        player_names = EXCLUDED.player_names,
                        created_at = EXCLUDED.created_at
                    """,
                    session_date,
                    json.dumps(team_a_guids),
                    json.dumps(team_a_names),
                    datetime.now(UTC).astimezone().replace(tzinfo=None),
                )

                # Insert Team B (attackers)
                await conn.execute(
                    """
                    INSERT INTO session_teams
                    (session_start_date, map_name, team_name, player_guids, player_names, created_at)
                    VALUES ($1, 'ALL', 'Team B', $2::jsonb, $3::jsonb, $4)
                    ON CONFLICT (session_identity, map_name, team_name) DO UPDATE SET
                        player_guids = EXCLUDED.player_guids,
                        player_names = EXCLUDED.player_names,
                        created_at = EXCLUDED.created_at
                    """,
                    session_date,
                    json.dumps(team_b_guids),
                    json.dumps(team_b_names),
                    datetime.now(UTC).astimezone().replace(tzinfo=None),
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO session_teams
                    (session_start_date, map_name, team_name, player_guids, player_names, created_at)
                    VALUES ($1, 'ALL', 'Team A', $2::jsonb, $3::jsonb, $4)
                    ON CONFLICT (session_start_date, map_name, team_name) DO UPDATE SET
                        player_guids = EXCLUDED.player_guids,
                        player_names = EXCLUDED.player_names,
                        created_at = EXCLUDED.created_at
                    """,
                    session_date,
                    json.dumps(team_a_guids),
                    json.dumps(team_a_names),
                    datetime.now(UTC).astimezone().replace(tzinfo=None),
                )

                # Insert Team B (attackers)
                await conn.execute(
                    """
                    INSERT INTO session_teams
                    (session_start_date, map_name, team_name, player_guids, player_names, created_at)
                    VALUES ($1, 'ALL', 'Team B', $2::jsonb, $3::jsonb, $4)
                    ON CONFLICT (session_start_date, map_name, team_name) DO UPDATE SET
                        player_guids = EXCLUDED.player_guids,
                        player_names = EXCLUDED.player_names,
                        created_at = EXCLUDED.created_at
                    """,
                    session_date,
                    json.dumps(team_b_guids),
                    json.dumps(team_b_names),
                    datetime.now(UTC).astimezone().replace(tzinfo=None),
                )

    logger.info(
        f"✅ Auto-assigned teams for session {session_date}: "
        f"Team A ({len(team_a_guids)} defenders) vs Team B ({len(team_b_guids)} attackers)"
    )
    return TeamAssignment.ASSIGNED
