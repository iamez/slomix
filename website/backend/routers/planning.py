"""Planning room API endpoints for post-readiness coordination."""

from __future__ import annotations

import os
from datetime import date
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from website.backend.dependencies import get_db
from website.backend.logging_config import get_app_logger
from website.backend.services.planning_discord_bridge import PlanningDiscordBridge

logger = get_app_logger("planning.api")
router = APIRouter()

PLANNING_COMMITTED_STATUSES = {"LOOKING", "AVAILABLE"}
PLANNING_PARTICIPANT_STATUSES = {"LOOKING", "AVAILABLE", "MAYBE"}


def _require_user(request: Request) -> Dict[str, Any]:
    user = request.session.get("user")
    if not user or "id" not in user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def _optional_user(request: Request) -> Optional[Dict[str, Any]]:
    user = request.session.get("user")
    if not user or "id" not in user:
        return None
    return user


def _optional_user_id(request: Request) -> Optional[int]:
    user = _optional_user(request)
    if not user:
        return None
    try:
        return int(user["id"])
    except (TypeError, ValueError):
        return None


def _website_user_id_from_user(user: Dict[str, Any]) -> Optional[int]:
    for key in ("website_user_id", "id"):
        raw = user.get(key)
        try:
            return int(raw)
        except (TypeError, ValueError):
            continue
    return None


def _require_ajax_csrf_header(request: Request) -> None:
    if request.headers.get("x-requested-with", "").lower() != "xmlhttprequest":
        raise HTTPException(status_code=403, detail="Missing required CSRF header")


def _configured_admin_ids() -> set[int]:
    values: set[int] = set()
    for env_name in ("WEBSITE_ADMIN_DISCORD_IDS", "ADMIN_DISCORD_IDS", "OWNER_USER_ID"):
        raw = os.getenv(env_name, "")
        if not raw:
            continue
        for token in raw.split(","):
            token = token.strip()
            if token.isdigit():
                values.add(int(token))
    return values


def _configured_promoter_ids() -> set[int]:
    raw = os.getenv("PROMOTER_DISCORD_IDS", "")
    if not raw:
        return set()
    values: set[int] = set()
    for token in raw.split(","):
        token = token.strip()
        if token.isdigit():
            values.add(int(token))
    return values


def _session_ready_threshold() -> int:
    raw = os.getenv("AVAILABILITY_SESSION_READY_THRESHOLD", "6")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 6
    return max(1, value)


async def _current_db_date(db) -> date:
    value = await db.fetch_val("SELECT CURRENT_DATE")
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


async def _is_promoter_user(request: Request, db) -> bool:
    discord_user_id = _optional_user_id(request)
    if discord_user_id is None:
        return False
    if discord_user_id in _configured_admin_ids():
        return True
    if discord_user_id in _configured_promoter_ids():
        return True
    try:
        row = await db.fetch_one(
            "SELECT tier FROM user_permissions WHERE discord_id = $1 LIMIT 1",
            (discord_user_id,),
        )
        if row and str(row[0] or "").lower() in {"root", "admin"}:
            return True
    except Exception:
        return False
    return False


async def _is_discord_linked(user: Dict[str, Any], db) -> bool:
    if user.get("linked_player"):
        return True

    website_user_id = _website_user_id_from_user(user)
    if website_user_id is not None:
        try:
            row = await db.fetch_one(
                "SELECT user_id FROM user_player_links WHERE user_id = $1 LIMIT 1",
                (website_user_id,),
            )
            if row:
                return True
        except Exception:
            pass

    try:
        discord_id = int(user["id"])
    except (TypeError, ValueError, KeyError):
        return False

    row = await db.fetch_one(
        "SELECT id FROM player_links WHERE discord_id = $1 LIMIT 1",
        (discord_id,),
    )
    return row is not None


async def _require_linked_identity(request: Request, db) -> tuple[Dict[str, Any], int, int]:
    user = _require_user(request)
    try:
        discord_user_id = int(user["id"])
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid user session")

    if not await _is_discord_linked(user, db):
        raise HTTPException(status_code=403, detail="Linked Discord account required")

    website_user_id = _website_user_id_from_user(user)
    if website_user_id is None:
        website_user_id = discord_user_id

    return user, discord_user_id, int(website_user_id)


def _coerce_user_id_list(value: Any) -> list[int]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise HTTPException(status_code=400, detail="team member lists must be arrays")
    user_ids: list[int] = []
    seen: set[int] = set()
    for raw in value:
        try:
            user_id = int(raw)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="team member ids must be integers")
        if user_id in seen:
            continue
        seen.add(user_id)
        user_ids.append(user_id)
    return user_ids


async def _today_readiness(db, target_date: date) -> tuple[int, int, bool]:
    threshold = _session_ready_threshold()
    row = await db.fetch_one(
        "SELECT COUNT(*) FROM availability_entries WHERE entry_date = $1 AND status = 'LOOKING'",
        (target_date,),
    )
    looking_count = int((row[0] if row else 0) or 0)
    return threshold, looking_count, looking_count >= threshold


async def _participants_for_date(db, target_date: date) -> list[Dict[str, Any]]:
    rows = await db.fetch_all(
        """
        SELECT ae.user_id,
               COALESCE(pl.player_name, ae.user_name, pl.discord_username) AS display_name,
               ae.status
        FROM availability_entries ae
        LEFT JOIN player_links pl ON pl.discord_id = ae.user_id
        WHERE ae.entry_date = $1
          AND ae.status IN ('LOOKING', 'AVAILABLE', 'MAYBE')
        ORDER BY ae.updated_at DESC
        """,
        (target_date,),
    )

    participants: list[Dict[str, Any]] = []
    seen: set[int] = set()
    for row in rows or []:
        user_id = int(row[0])
        if user_id in seen:
            continue
        seen.add(user_id)
        status = str(row[2] or "").upper()
        if status not in PLANNING_PARTICIPANT_STATUSES:
            continue
        display_name = str(row[1] or f"User {user_id}")
        participants.append(
            {
                "user_id": user_id,
                "display_name": display_name,
                "status": status,
            }
        )
    return participants


async def _session_row_for_date(db, target_date: date):
    return await db.fetch_one(
        """
        SELECT id, session_date, created_by_user_id, discord_thread_id, created_at, updated_at
        FROM planning_sessions
        WHERE session_date = $1
        LIMIT 1
        """,
        (target_date,),
    )


async def _resolve_display_name(db, user_id: int, cache: Dict[int, str]) -> str:
    if user_id in cache:
        return cache[user_id]

    row = await db.fetch_one(
        "SELECT player_name, discord_username FROM player_links WHERE discord_id = $1 LIMIT 1",
        (int(user_id),),
    )
    if row:
        name = str(row[0] or row[1] or f"User {user_id}")
    else:
        name = f"User {user_id}"
    cache[user_id] = name
    return name


async def _session_payload(db, session_row, *, viewer_user_id: Optional[int], display_name_cache: Dict[int, str]) -> Dict[str, Any]:
    session_id = int(session_row[0])

    suggestion_rows = await db.fetch_all(
        """
        SELECT id, name, suggested_by_user_id, created_at
        FROM planning_team_names
        WHERE session_id = $1
        ORDER BY created_at ASC, id ASC
        """,
        (session_id,),
    )
    vote_rows = await db.fetch_all(
        "SELECT suggestion_id, user_id FROM planning_votes WHERE session_id = $1",
        (session_id,),
    )

    vote_counts: dict[int, int] = {}
    my_vote_suggestion_id: Optional[int] = None
    for vote_row in vote_rows or []:
        suggestion_id = int(vote_row[0])
        voter_id = int(vote_row[1])
        vote_counts[suggestion_id] = vote_counts.get(suggestion_id, 0) + 1
        if viewer_user_id is not None and voter_id == int(viewer_user_id):
            my_vote_suggestion_id = suggestion_id

    suggestions: list[Dict[str, Any]] = []
    for row in suggestion_rows or []:
        suggestion_id = int(row[0])
        suggester_id = int(row[2])
        suggestions.append(
            {
                "id": suggestion_id,
                "name": str(row[1]),
                "suggested_by_user_id": suggester_id,
                "suggested_by_name": await _resolve_display_name(db, suggester_id, display_name_cache),
                "votes": int(vote_counts.get(suggestion_id, 0)),
                "voted_by_me": my_vote_suggestion_id == suggestion_id,
                "created_at": str(row[3]),
            }
        )

    suggestions.sort(key=lambda item: (-int(item["votes"]), str(item["name"]).lower(), int(item["id"])))

    team_rows = await db.fetch_all(
        """
        SELECT id, side, captain_user_id
        FROM planning_teams
        WHERE session_id = $1
        ORDER BY side ASC
        """,
        (session_id,),
    )

    teams: Dict[str, Dict[str, Any]] = {
        "A": {"side": "A", "captain_user_id": None, "captain_name": None, "members": []},
        "B": {"side": "B", "captain_user_id": None, "captain_name": None, "members": []},
    }

    for team_row in team_rows or []:
        team_id = int(team_row[0])
        side = str(team_row[1]).upper()
        if side not in teams:
            continue

        captain_user_id = team_row[2]
        if captain_user_id is not None:
            captain_int = int(captain_user_id)
            teams[side]["captain_user_id"] = captain_int
            teams[side]["captain_name"] = await _resolve_display_name(db, captain_int, display_name_cache)

        member_rows = await db.fetch_all(
            """
            SELECT user_id
            FROM planning_team_members
            WHERE team_id = $1
            ORDER BY created_at ASC, id ASC
            """,
            (team_id,),
        )
        members: list[Dict[str, Any]] = []
        for member_row in member_rows or []:
            member_user_id = int(member_row[0])
            members.append(
                {
                    "user_id": member_user_id,
                    "display_name": await _resolve_display_name(db, member_user_id, display_name_cache),
                }
            )
        teams[side]["members"] = members

    return {
        "id": session_id,
        "session_date": str(session_row[1]),
        "created_by_user_id": int(session_row[2]),
        "discord_thread_id": session_row[3],
        "created_at": str(session_row[4]),
        "updated_at": str(session_row[5]),
        "suggestions": suggestions,
        "my_vote_suggestion_id": my_vote_suggestion_id,
        "teams": teams,
    }


async def _planning_state(
    db,
    *,
    request: Request,
    target_date: date,
    session_row,
) -> Dict[str, Any]:
    user = _optional_user(request)
    viewer_website_user_id = _website_user_id_from_user(user) if user else None
    viewer_linked = bool(user and await _is_discord_linked(user, db))

    threshold, looking_count, ready = await _today_readiness(db, target_date)
    participants = await _participants_for_date(db, target_date)
    committed = [row for row in participants if row["status"] in PLANNING_COMMITTED_STATUSES]

    display_name_cache = {int(p["user_id"]): str(p["display_name"]) for p in participants}

    session_payload = None
    if viewer_linked and session_row:
        session_payload = await _session_payload(
            db,
            session_row,
            viewer_user_id=viewer_website_user_id,
            display_name_cache=display_name_cache,
        )

    return {
        "date": target_date.isoformat(),
        "session_ready": {
            "ready": bool(ready),
            "looking_count": int(looking_count),
            "threshold": int(threshold),
        },
        "unlocked": bool(ready or session_payload),
        "participant_count": len(participants),
        "participants": participants if viewer_linked else [],
        "committed_count": len(committed),
        "viewer": {
            "authenticated": bool(user),
            "linked_discord": viewer_linked,
            "website_user_id": int(viewer_website_user_id) if viewer_website_user_id is not None else None,
        },
        "session": session_payload,
    }


@router.get("/today")
async def get_today_planning_room(
    request: Request,
    target_date: Optional[date] = Query(default=None, alias="date"),
    db=Depends(get_db),
):
    resolved_date = target_date or await _current_db_date(db)
    session_row = await _session_row_for_date(db, resolved_date)
    return await _planning_state(db, request=request, target_date=resolved_date, session_row=session_row)


@router.post("/today/create")
async def create_today_planning_room(request: Request, db=Depends(get_db)):
    _require_ajax_csrf_header(request)
    user, _discord_user_id, website_user_id = await _require_linked_identity(request, db)

    target_date = await _current_db_date(db)
    existing = await _session_row_for_date(db, target_date)

    if existing:
        return {
            "success": True,
            "created": False,
            "thread_created": bool(existing[3]),
            "state": await _planning_state(db, request=request, target_date=target_date, session_row=existing),
        }

    _threshold, _looking_count, ready = await _today_readiness(db, target_date)
    if not ready:
        raise HTTPException(status_code=409, detail="Planning room unlocks once session-ready threshold is met")

    row = await db.fetch_one(
        """
        INSERT INTO planning_sessions
            (session_date, created_by_user_id, created_at, updated_at)
        VALUES ($1, $2, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (session_date) DO NOTHING
        RETURNING id
        """,
        (target_date, int(website_user_id)),
    )
    if not row:
        row = await _session_row_for_date(db, target_date)
        if not row:
            raise HTTPException(status_code=500, detail="Failed to create planning session")
        session_row = row
    else:
        session_row = await _session_row_for_date(db, target_date)
        if not session_row:
            raise HTTPException(status_code=500, detail="Planning session was created but could not be loaded")

    participants = await _participants_for_date(db, target_date)
    thread_id = None
    bridge = PlanningDiscordBridge.from_env()
    try:
        thread_id = await bridge.create_private_thread(
            session_date=target_date,
            participant_count=len(participants),
        )
    except Exception as exc:
        logger.warning("Planning thread creation failed: %s", exc)

    if thread_id:
        await db.execute(
            "UPDATE planning_sessions SET discord_thread_id = $1, updated_at = CURRENT_TIMESTAMP WHERE id = $2",
            (thread_id, int(session_row[0])),
        )
        session_row = await _session_row_for_date(db, target_date)

    return {
        "success": True,
        "created": True,
        "thread_created": bool(thread_id),
        "state": await _planning_state(db, request=request, target_date=target_date, session_row=session_row),
    }


@router.post("/today/join")
async def join_today_planning_room(request: Request, db=Depends(get_db)):
    _require_ajax_csrf_header(request)
    user, discord_user_id, _website_user_id = await _require_linked_identity(request, db)

    target_date = await _current_db_date(db)
    session_row = await _session_row_for_date(db, target_date)
    if not session_row:
        raise HTTPException(status_code=404, detail="Planning room is not created yet")

    entry = await db.fetch_one(
        "SELECT status FROM availability_entries WHERE user_id = $1 AND entry_date = $2 LIMIT 1",
        (int(discord_user_id), target_date),
    )
    status = str(entry[0] or "").upper() if entry else ""

    if status not in PLANNING_PARTICIPANT_STATUSES:
        await db.execute(
            """
            INSERT INTO availability_entries
                (user_id, user_name, entry_date, status, created_at, updated_at)
            VALUES ($1, $2, $3, 'LOOKING', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id, entry_date) DO UPDATE SET
                user_name = EXCLUDED.user_name,
                status = 'LOOKING',
                updated_at = CURRENT_TIMESTAMP
            """,
            (int(discord_user_id), str(user.get("username") or ""), target_date),
        )

    return {
        "success": True,
        "state": await _planning_state(db, request=request, target_date=target_date, session_row=session_row),
    }


@router.post("/today/suggestions")
async def add_planning_name_suggestion(request: Request, db=Depends(get_db)):
    _require_ajax_csrf_header(request)
    _user, _discord_user_id, website_user_id = await _require_linked_identity(request, db)

    target_date = await _current_db_date(db)
    session_row = await _session_row_for_date(db, target_date)
    if not session_row:
        raise HTTPException(status_code=404, detail="Planning room is not created yet")

    body = await request.json()
    name = str(body.get("name") or "").strip()
    if len(name) < 2:
        raise HTTPException(status_code=400, detail="Suggestion name must be at least 2 characters")
    if len(name) > 48:
        raise HTTPException(status_code=400, detail="Suggestion name must be at most 48 characters")

    duplicate = await db.fetch_one(
        "SELECT id FROM planning_team_names WHERE session_id = $1 AND lower(name) = lower($2) LIMIT 1",
        (int(session_row[0]), name),
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="Suggestion already exists")

    created = await db.fetch_one(
        """
        INSERT INTO planning_team_names
            (session_id, suggested_by_user_id, name, created_at)
        VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
        RETURNING id
        """,
        (int(session_row[0]), int(website_user_id), name),
    )

    return {
        "success": True,
        "suggestion_id": int(created[0]) if created else None,
        "state": await _planning_state(db, request=request, target_date=target_date, session_row=session_row),
    }


@router.post("/today/vote")
async def vote_planning_name(request: Request, db=Depends(get_db)):
    _require_ajax_csrf_header(request)
    _user, _discord_user_id, website_user_id = await _require_linked_identity(request, db)

    target_date = await _current_db_date(db)
    session_row = await _session_row_for_date(db, target_date)
    if not session_row:
        raise HTTPException(status_code=404, detail="Planning room is not created yet")

    body = await request.json()
    try:
        suggestion_id = int(body.get("suggestion_id"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="suggestion_id must be an integer")

    exists = await db.fetch_one(
        "SELECT id FROM planning_team_names WHERE id = $1 AND session_id = $2 LIMIT 1",
        (suggestion_id, int(session_row[0])),
    )
    if not exists:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    await db.execute(
        """
        INSERT INTO planning_votes
            (session_id, user_id, suggestion_id, created_at, updated_at)
        VALUES ($1, $2, $3, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (session_id, user_id) DO UPDATE SET
            suggestion_id = EXCLUDED.suggestion_id,
            updated_at = CURRENT_TIMESTAMP
        """,
        (int(session_row[0]), int(website_user_id), int(suggestion_id)),
    )

    return {
        "success": True,
        "state": await _planning_state(db, request=request, target_date=target_date, session_row=session_row),
    }


@router.post("/today/teams")
async def save_planning_teams(request: Request, db=Depends(get_db)):
    _require_ajax_csrf_header(request)
    _user, _discord_user_id, website_user_id = await _require_linked_identity(request, db)

    target_date = await _current_db_date(db)
    session_row = await _session_row_for_date(db, target_date)
    if not session_row:
        raise HTTPException(status_code=404, detail="Planning room is not created yet")

    session_id = int(session_row[0])
    creator_user_id = int(session_row[2])
    if int(website_user_id) != creator_user_id and not await _is_promoter_user(request, db):
        raise HTTPException(status_code=403, detail="Only session creator or promoter/admin can update teams")

    body = await request.json()
    side_a = _coerce_user_id_list(body.get("side_a"))
    side_b = _coerce_user_id_list(body.get("side_b"))

    overlap = sorted(set(side_a) & set(side_b))
    if overlap:
        raise HTTPException(status_code=400, detail="A player cannot be on both teams")

    participants = await _participants_for_date(db, target_date)
    participant_ids = {int(row["user_id"]) for row in participants}
    unknown = [uid for uid in (*side_a, *side_b) if uid not in participant_ids]
    if unknown:
        raise HTTPException(status_code=400, detail="Team members must be in today's participant pool")

    captain_a = body.get("captain_a")
    captain_b = body.get("captain_b")
    try:
        captain_a_id = int(captain_a) if captain_a is not None else None
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="captain_a must be an integer or null")
    try:
        captain_b_id = int(captain_b) if captain_b is not None else None
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="captain_b must be an integer or null")

    if captain_a_id is not None and captain_a_id not in side_a:
        raise HTTPException(status_code=400, detail="captain_a must be a member of side A")
    if captain_b_id is not None and captain_b_id not in side_b:
        raise HTTPException(status_code=400, detail="captain_b must be a member of side B")

    team_a = await db.fetch_one(
        """
        INSERT INTO planning_teams
            (session_id, side, captain_user_id, created_at, updated_at)
        VALUES ($1, 'A', $2, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (session_id, side) DO UPDATE SET
            captain_user_id = EXCLUDED.captain_user_id,
            updated_at = CURRENT_TIMESTAMP
        RETURNING id
        """,
        (session_id, captain_a_id),
    )
    team_b = await db.fetch_one(
        """
        INSERT INTO planning_teams
            (session_id, side, captain_user_id, created_at, updated_at)
        VALUES ($1, 'B', $2, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (session_id, side) DO UPDATE SET
            captain_user_id = EXCLUDED.captain_user_id,
            updated_at = CURRENT_TIMESTAMP
        RETURNING id
        """,
        (session_id, captain_b_id),
    )

    if not team_a or not team_b:
        raise HTTPException(status_code=500, detail="Failed to persist planning teams")

    team_a_id = int(team_a[0])
    team_b_id = int(team_b[0])

    await db.execute("DELETE FROM planning_team_members WHERE session_id = $1", (session_id,))

    for user_id in side_a:
        await db.execute(
            """
            INSERT INTO planning_team_members
                (session_id, team_id, user_id, created_at)
            VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
            ON CONFLICT (session_id, user_id) DO UPDATE SET
                team_id = EXCLUDED.team_id
            """,
            (session_id, team_a_id, int(user_id)),
        )

    for user_id in side_b:
        await db.execute(
            """
            INSERT INTO planning_team_members
                (session_id, team_id, user_id, created_at)
            VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
            ON CONFLICT (session_id, user_id) DO UPDATE SET
                team_id = EXCLUDED.team_id
            """,
            (session_id, team_b_id, int(user_id)),
        )

    return {
        "success": True,
        "state": await _planning_state(db, request=request, target_date=target_date, session_row=session_row),
    }
