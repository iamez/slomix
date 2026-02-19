"""Date-based availability API endpoints."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from website.backend.dependencies import get_db
from website.backend.logging_config import get_app_logger

logger = get_app_logger("availability.api")
router = APIRouter()

STATUS_VALUES = ("LOOKING", "AVAILABLE", "MAYBE", "NOT_PLAYING")
CHANNEL_TYPES = ("discord", "telegram", "signal")
MAX_FUTURE_HORIZON_DAYS = 90
MAX_RANGE_DAYS = 180
DEFAULT_RANGE_DAYS = 60
DEFAULT_ME_RANGE_DAYS = 30
DEFAULT_SOUND_COOLDOWN_SECONDS = 480
DEFAULT_LINK_TOKEN_TTL_MINUTES = 30


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


def _configured_admin_ids() -> set[int]:
    ids: set[int] = set()
    for env_name in ("WEBSITE_ADMIN_DISCORD_IDS", "ADMIN_DISCORD_IDS", "OWNER_USER_ID"):
        raw = os.getenv(env_name, "")
        if not raw:
            continue
        for token in raw.split(","):
            token = token.strip()
            if token.isdigit():
                ids.add(int(token))
    return ids


def _is_admin_user(request: Request) -> bool:
    user_id = _optional_user_id(request)
    if user_id is None:
        return False
    return user_id in _configured_admin_ids()


def _parse_iso_date(value: Any, field_name: str) -> date:
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise HTTPException(status_code=400, detail=f"{field_name} must be YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{field_name} must be YYYY-MM-DD")


def _normalize_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _serialize_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except (TypeError, ValueError):
            pass
    return str(value)


def _coerce_bool(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    return default


def _coerce_json_object(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    return {}


def _validate_range(from_date: date, to_date: date, *, max_days: int = MAX_RANGE_DAYS) -> None:
    if from_date > to_date:
        raise HTTPException(status_code=400, detail="'from' must be <= 'to'")
    if (to_date - from_date).days + 1 > max_days:
        raise HTTPException(status_code=400, detail=f"Date range cannot exceed {max_days} days")


def _status_counts_template() -> Dict[str, int]:
    return {status: 0 for status in STATUS_VALUES}


def _status_label(status: str) -> str:
    normalized = str(status or "").upper()
    if normalized in STATUS_VALUES:
        return normalized
    raise HTTPException(status_code=400, detail=f"status must be one of: {', '.join(STATUS_VALUES)}")


def _link_token_hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


async def _current_db_date(db) -> date:
    value = await db.fetch_val("SELECT CURRENT_DATE")
    return _normalize_date(value)


async def _is_discord_linked(user: Dict[str, Any], db) -> bool:
    if user.get("linked_player"):
        return True

    try:
        discord_id = int(user["id"])
    except (TypeError, ValueError, KeyError):
        return False

    row = await db.fetch_one(
        "SELECT id FROM player_links WHERE discord_id = $1 LIMIT 1",
        (discord_id,),
    )
    return row is not None


async def _require_linked_user(request: Request, db) -> tuple[Dict[str, Any], int]:
    user = _require_user(request)
    try:
        user_id = int(user["id"])
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid user session")

    if not await _is_discord_linked(user, db):
        raise HTTPException(status_code=403, detail="Linked Discord account required")

    return user, user_id


async def _fetch_subscriptions_map(db, user_id: int) -> Dict[str, Dict[str, Any]]:
    rows = await db.fetch_all(
        """
        SELECT channel_type, enabled, channel_address, verified_at, preferences
        FROM availability_subscriptions
        WHERE user_id = $1
        ORDER BY channel_type ASC
        """,
        (user_id,),
    )

    result: Dict[str, Dict[str, Any]] = {
        channel: {
            "channel_type": channel,
            "enabled": channel == "discord",
            "channel_address": str(user_id) if channel == "discord" else None,
            "verified": channel == "discord",
            "preferences": {},
        }
        for channel in CHANNEL_TYPES
    }

    for row in rows or []:
        channel_type = str(row[0] or "").lower()
        if channel_type not in result:
            continue
        preferences: Dict[str, Any] = {}
        raw_preferences = row[4]
        if isinstance(raw_preferences, dict):
            preferences = raw_preferences
        elif isinstance(raw_preferences, str):
            try:
                loaded = json.loads(raw_preferences)
                if isinstance(loaded, dict):
                    preferences = loaded
            except json.JSONDecodeError:
                preferences = {}

        result[channel_type] = {
            "channel_type": channel_type,
            "enabled": bool(row[1]),
            "channel_address": row[2],
            "verified": bool(row[3]) or channel_type == "discord",
            "preferences": preferences,
        }

    return result


async def _settings_payload(db, user_id: int) -> Dict[str, Any]:
    settings_row = await db.fetch_one(
        """
        SELECT sound_enabled, sound_cooldown_seconds, availability_reminders_enabled, timezone
        FROM availability_user_settings
        WHERE user_id = $1
        """,
        (user_id,),
    )

    if settings_row:
        sound_enabled = bool(settings_row[0])
        cooldown_seconds = int(settings_row[1] or DEFAULT_SOUND_COOLDOWN_SECONDS)
        reminders_enabled = bool(settings_row[2])
        timezone = settings_row[3] or "UTC"
    else:
        sound_enabled = True
        cooldown_seconds = DEFAULT_SOUND_COOLDOWN_SECONDS
        reminders_enabled = True
        timezone = "UTC"

    subscriptions = await _fetch_subscriptions_map(db, user_id)

    return {
        "user_id": user_id,
        "sound_enabled": sound_enabled,
        "get_ready_sound": sound_enabled,
        "sound_cooldown_seconds": cooldown_seconds,
        "availability_reminders_enabled": reminders_enabled,
        "timezone": timezone,
        "discord_notify": bool(subscriptions["discord"]["enabled"]),
        "telegram_notify": bool(subscriptions["telegram"]["enabled"]),
        "signal_notify": bool(subscriptions["signal"]["enabled"]),
        "subscriptions": [subscriptions[channel] for channel in CHANNEL_TYPES],
    }


def _session_ready_threshold() -> int:
    raw = os.getenv("AVAILABILITY_SESSION_READY_THRESHOLD", "6")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 6
    return max(1, value)


@router.get("/access")
async def get_availability_access(request: Request, db=Depends(get_db)):
    """Return current viewer auth/link/admin flags for availability controls."""
    user = _optional_user(request)
    authenticated = bool(user)
    linked = await _is_discord_linked(user, db) if authenticated else False
    return {
        "authenticated": authenticated,
        "linked_discord": linked,
        "can_submit": authenticated and linked,
        "is_admin": _is_admin_user(request) if authenticated else False,
    }


@router.get("")
async def get_availability_range(
    request: Request,
    from_date: Optional[date] = Query(default=None, alias="from"),
    to_date: Optional[date] = Query(default=None, alias="to"),
    include_users: bool = Query(default=False),
    db=Depends(get_db),
):
    """Get date-range availability aggregates and optional viewer detail."""
    today = await _current_db_date(db)
    range_start = from_date or today
    range_end = to_date or (range_start + timedelta(days=DEFAULT_RANGE_DAYS))
    _validate_range(range_start, range_end)

    counts_rows = await db.fetch_all(
        """
        SELECT entry_date, status, COUNT(*) AS cnt
        FROM availability_entries
        WHERE entry_date BETWEEN $1 AND $2
        GROUP BY entry_date, status
        ORDER BY entry_date ASC, status ASC
        """,
        (range_start, range_end),
    )

    counts_by_day: Dict[date, Dict[str, int]] = {}
    for row in counts_rows or []:
        entry_date = _normalize_date(row[0])
        status = str(row[1] or "").upper()
        if status not in STATUS_VALUES:
            continue
        day_counts = counts_by_day.setdefault(entry_date, _status_counts_template())
        day_counts[status] = int(row[2] or 0)

    user = _optional_user(request)
    user_id = _optional_user_id(request)
    linked_discord = False
    my_statuses: Dict[date, str] = {}

    if user is not None and user_id is not None:
        linked_discord = await _is_discord_linked(user, db)
        my_rows = await db.fetch_all(
            """
            SELECT entry_date, status
            FROM availability_entries
            WHERE user_id = $1 AND entry_date BETWEEN $2 AND $3
            ORDER BY entry_date ASC
            """,
            (user_id, range_start, range_end),
        )
        for row in my_rows or []:
            entry_date = _normalize_date(row[0])
            status = str(row[1] or "").upper()
            if status in STATUS_VALUES:
                my_statuses[entry_date] = status

    users_by_day: Dict[date, Dict[str, list[Dict[str, Any]]]] = {}
    if include_users and user_id is not None:
        user_rows = await db.fetch_all(
            """
            SELECT ae.entry_date,
                   ae.status,
                   ae.user_id,
                   COALESCE(pl.player_name, ae.user_name, pl.discord_username) AS display_name
            FROM availability_entries ae
            LEFT JOIN player_links pl ON pl.discord_id = ae.user_id
            WHERE ae.entry_date BETWEEN $1 AND $2
            ORDER BY ae.entry_date ASC, ae.updated_at DESC
            """,
            (range_start, range_end),
        )
        for row in user_rows or []:
            entry_date = _normalize_date(row[0])
            status = str(row[1] or "").upper()
            if status not in STATUS_VALUES:
                continue
            day_map = users_by_day.setdefault(
                entry_date,
                {status_name: [] for status_name in STATUS_VALUES},
            )
            day_map[status].append(
                {
                    "user_id": int(row[2]),
                    "display_name": row[3] or f"User {row[2]}",
                }
            )

    days = []
    cursor = range_start
    while cursor <= range_end:
        counts = dict(_status_counts_template())
        if cursor in counts_by_day:
            counts.update(counts_by_day[cursor])
        total = sum(counts.values())

        day_payload: Dict[str, Any] = {
            "date": cursor.isoformat(),
            "counts": counts,
            "total": total,
        }
        if user_id is not None:
            day_payload["my_status"] = my_statuses.get(cursor)
        if include_users and user_id is not None:
            day_payload["users_by_status"] = users_by_day.get(
                cursor,
                {status_name: [] for status_name in STATUS_VALUES},
            )

        days.append(day_payload)
        cursor += timedelta(days=1)

    today_counts = counts_by_day.get(today, _status_counts_template())
    threshold = _session_ready_threshold()
    looking_count = int(today_counts.get("LOOKING", 0))
    session_ready = looking_count >= threshold

    return {
        "from": range_start.isoformat(),
        "to": range_end.isoformat(),
        "statuses": list(STATUS_VALUES),
        "days": days,
        "viewer": {
            "authenticated": user_id is not None,
            "linked_discord": linked_discord,
        },
        "session_ready": {
            "date": today.isoformat(),
            "ready": session_ready,
            "looking_count": looking_count,
            "threshold": threshold,
            "event_key": f"SESSION_READY:{today.isoformat()}:threshold={threshold}",
        },
    }


@router.post("")
async def upsert_availability_entry(request: Request, db=Depends(get_db)):
    """Set availability for a specific date (linked Discord required)."""
    user, user_id = await _require_linked_user(request, db)
    body = await request.json()

    target_date = _parse_iso_date(body.get("date"), "date")
    status = _status_label(body.get("status"))

    today = await _current_db_date(db)
    if target_date < today:
        raise HTTPException(status_code=400, detail="Past dates are read-only")
    if target_date > today + timedelta(days=MAX_FUTURE_HORIZON_DAYS):
        raise HTTPException(
            status_code=400,
            detail=f"date must be within {MAX_FUTURE_HORIZON_DAYS} days",
        )

    username = str(user.get("username") or "")
    await db.execute(
        """
        INSERT INTO availability_entries
            (user_id, user_name, entry_date, status, created_at, updated_at)
        VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (user_id, entry_date) DO UPDATE SET
            user_name = EXCLUDED.user_name,
            status = EXCLUDED.status,
            updated_at = CURRENT_TIMESTAMP
        """,
        (user_id, username, target_date, status),
    )

    return {
        "success": True,
        "user_id": user_id,
        "date": target_date.isoformat(),
        "status": status,
    }


@router.get("/me")
async def get_my_availability(
    request: Request,
    from_date: Optional[date] = Query(default=None, alias="from"),
    to_date: Optional[date] = Query(default=None, alias="to"),
    db=Depends(get_db),
):
    """Get the logged-in user's availability entries in a date range."""
    user = _require_user(request)
    try:
        user_id = int(user["id"])
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid user session")

    today = await _current_db_date(db)
    range_start = from_date or today
    range_end = to_date or (range_start + timedelta(days=DEFAULT_ME_RANGE_DAYS))
    _validate_range(range_start, range_end)

    rows = await db.fetch_all(
        """
        SELECT entry_date, status, created_at, updated_at
        FROM availability_entries
        WHERE user_id = $1 AND entry_date BETWEEN $2 AND $3
        ORDER BY entry_date ASC
        """,
        (user_id, range_start, range_end),
    )

    entries = [
        {
            "date": _normalize_date(row[0]).isoformat(),
            "status": str(row[1]),
            "created_at": _serialize_value(row[2]),
            "updated_at": _serialize_value(row[3]),
        }
        for row in (rows or [])
    ]

    return {
        "user_id": user_id,
        "from": range_start.isoformat(),
        "to": range_end.isoformat(),
        "entries": entries,
    }


@router.get("/settings")
async def get_settings(request: Request, db=Depends(get_db)):
    """Get user availability settings and channel toggles."""
    _user, user_id = await _require_linked_user(request, db)
    return await _settings_payload(db, user_id)


@router.post("/settings")
async def upsert_settings(request: Request, db=Depends(get_db)):
    """Update user availability settings and optional channel toggles."""
    _user, user_id = await _require_linked_user(request, db)

    body = await request.json()
    sound_enabled = _coerce_bool(
        body.get("sound_enabled", body.get("get_ready_sound")),
        default=True,
    )
    reminders_enabled = _coerce_bool(
        body.get("availability_reminders_enabled", body.get("threshold_notify")),
        default=True,
    )
    timezone = body.get("timezone", "UTC")
    if not isinstance(timezone, str) or not timezone.strip():
        timezone = "UTC"
    timezone = timezone.strip()
    if len(timezone) > 64:
        raise HTTPException(status_code=400, detail="timezone is too long")

    sound_cooldown = body.get("sound_cooldown_seconds", DEFAULT_SOUND_COOLDOWN_SECONDS)
    try:
        sound_cooldown = int(sound_cooldown)
    except (TypeError, ValueError):
        sound_cooldown = DEFAULT_SOUND_COOLDOWN_SECONDS
    sound_cooldown = max(30, min(sound_cooldown, 3600))

    # Optional channel toggles from UI payload.
    channel_flags = {
        "discord": body.get("discord_notify"),
        "telegram": body.get("telegram_notify"),
        "signal": body.get("signal_notify"),
    }
    linked_channel_verified_at: Dict[str, Any] = {}
    for channel_type, raw_enabled in channel_flags.items():
        if not isinstance(raw_enabled, bool):
            continue
        if channel_type in ("telegram", "signal") and raw_enabled:
            verified_link = await db.fetch_one(
                """
                SELECT verified_at
                FROM availability_channel_links
                WHERE user_id = $1 AND channel_type = $2
                """,
                (user_id, channel_type),
            )
            if not verified_link or not verified_link[0]:
                raise HTTPException(
                    status_code=403,
                    detail=f"{channel_type} channel must be linked and verified first",
                )
            linked_channel_verified_at[channel_type] = verified_link[0]

    await db.execute(
        """
        INSERT INTO availability_user_settings
            (user_id, sound_enabled, sound_cooldown_seconds, availability_reminders_enabled, timezone, updated_at)
        VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP)
        ON CONFLICT (user_id) DO UPDATE SET
            sound_enabled = EXCLUDED.sound_enabled,
            sound_cooldown_seconds = EXCLUDED.sound_cooldown_seconds,
            availability_reminders_enabled = EXCLUDED.availability_reminders_enabled,
            timezone = EXCLUDED.timezone,
            updated_at = CURRENT_TIMESTAMP
        """,
        (user_id, sound_enabled, sound_cooldown, reminders_enabled, timezone),
    )
    for channel_type, raw_enabled in channel_flags.items():
        if not isinstance(raw_enabled, bool):
            continue

        channel_address = str(user_id) if channel_type == "discord" else None
        verified_at = datetime.utcnow() if channel_type == "discord" else linked_channel_verified_at.get(channel_type)
        await db.execute(
            """
            INSERT INTO availability_subscriptions
                (user_id, channel_type, channel_address, enabled, verified_at, preferences, created_at, updated_at)
            VALUES (
                $1,
                $2,
                $3,
                $4,
                $5,
                '{}'::jsonb,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            )
            ON CONFLICT (user_id, channel_type) DO UPDATE SET
                enabled = EXCLUDED.enabled,
                channel_address = COALESCE(EXCLUDED.channel_address, availability_subscriptions.channel_address),
                verified_at = CASE
                    WHEN EXCLUDED.channel_type = 'discord' THEN COALESCE(EXCLUDED.verified_at, CURRENT_TIMESTAMP)
                    WHEN EXCLUDED.enabled THEN COALESCE(EXCLUDED.verified_at, availability_subscriptions.verified_at)
                    ELSE availability_subscriptions.verified_at
                END,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, channel_type, channel_address, raw_enabled, verified_at),
        )

    return await _settings_payload(db, user_id)


@router.get("/preferences")
async def get_preferences(request: Request, db=Depends(get_db)):
    """Compatibility alias for settings endpoint."""
    return await get_settings(request=request, db=db)


@router.post("/preferences")
async def update_preferences(request: Request, db=Depends(get_db)):
    """Compatibility alias for settings endpoint."""
    return await upsert_settings(request=request, db=db)


@router.get("/subscriptions")
async def get_subscriptions(request: Request, db=Depends(get_db)):
    """Get per-channel notification subscriptions for availability events."""
    _user, user_id = await _require_linked_user(request, db)
    mapping = await _fetch_subscriptions_map(db, user_id)
    return {
        "user_id": user_id,
        "subscriptions": [mapping[channel] for channel in CHANNEL_TYPES],
    }


@router.post("/subscriptions")
async def upsert_subscription(request: Request, db=Depends(get_db)):
    """Create or update a notification subscription channel."""
    _user, user_id = await _require_linked_user(request, db)
    body = await request.json()

    channel_type = str(body.get("channel_type", "")).lower()
    if channel_type not in CHANNEL_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"channel_type must be one of: {', '.join(CHANNEL_TYPES)}",
        )

    enabled = _coerce_bool(body.get("enabled"), default=True)
    channel_address = body.get("channel_address", body.get("destination"))
    if channel_address is not None and not isinstance(channel_address, str):
        raise HTTPException(status_code=400, detail="channel_address must be a string")
    if isinstance(channel_address, str):
        channel_address = channel_address.strip() or None

    if channel_type == "discord":
        channel_address = channel_address or str(user_id)

    preferences = _coerce_json_object(body.get("preferences"))
    preferences_json = json.dumps(preferences, ensure_ascii=True)

    verified_at = None
    if channel_type == "discord":
        verified_at = datetime.utcnow()
    elif enabled:
        verified_link = await db.fetch_one(
            """
            SELECT verified_at, destination
            FROM availability_channel_links
            WHERE user_id = $1 AND channel_type = $2
            """,
            (user_id, channel_type),
        )
        if not verified_link or not verified_link[0]:
            raise HTTPException(
                status_code=403,
                detail=f"{channel_type} channel must be linked and verified first",
            )
        verified_at = verified_link[0]
        if not channel_address:
            channel_address = verified_link[1]

    await db.execute(
        """
        INSERT INTO availability_subscriptions
            (user_id, channel_type, channel_address, enabled, verified_at, preferences, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, CAST($6 AS JSONB), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (user_id, channel_type) DO UPDATE SET
            channel_address = COALESCE(EXCLUDED.channel_address, availability_subscriptions.channel_address),
            enabled = EXCLUDED.enabled,
            verified_at = COALESCE(EXCLUDED.verified_at, availability_subscriptions.verified_at),
            preferences = EXCLUDED.preferences,
            updated_at = CURRENT_TIMESTAMP
        """,
        (user_id, channel_type, channel_address, enabled, verified_at, preferences_json),
    )

    return {
        "success": True,
        "user_id": user_id,
        "channel_type": channel_type,
        "enabled": enabled,
        "channel_address": channel_address,
        "preferences": preferences,
    }


@router.post("/link-token")
async def create_link_token(request: Request, db=Depends(get_db)):
    """Create one-time token for Telegram/Signal subscription linking."""
    _user, user_id = await _require_linked_user(request, db)
    body = await request.json()

    channel_type = str(body.get("channel_type", "")).lower()
    if channel_type not in ("telegram", "signal"):
        raise HTTPException(status_code=400, detail="channel_type must be telegram or signal")

    ttl_minutes = body.get("ttl_minutes", DEFAULT_LINK_TOKEN_TTL_MINUTES)
    try:
        ttl_minutes = int(ttl_minutes)
    except (TypeError, ValueError):
        ttl_minutes = DEFAULT_LINK_TOKEN_TTL_MINUTES
    ttl_minutes = max(5, min(ttl_minutes, 120))

    token = secrets.token_urlsafe(24)
    token_hash = _link_token_hash(token)
    expires_at = datetime.utcnow() + timedelta(minutes=ttl_minutes)

    await db.execute(
        """
        INSERT INTO availability_channel_links
            (user_id, channel_type, destination, verification_token_hash, token_expires_at, verification_requested_at, updated_at)
        VALUES ($1, $2, NULL, $3, $4, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (user_id, channel_type) DO UPDATE SET
            destination = NULL,
            verification_token_hash = EXCLUDED.verification_token_hash,
            token_expires_at = EXCLUDED.token_expires_at,
            verified_at = NULL,
            verification_requested_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        """,
        (user_id, channel_type, token_hash, expires_at),
    )

    return {
        "success": True,
        "channel_type": channel_type,
        "token": token,
        "expires_at": expires_at.isoformat(),
    }


@router.post("/link-confirm")
async def confirm_link_token(request: Request, db=Depends(get_db)):
    """Confirm token from Telegram/Signal side and activate subscription."""
    body = await request.json()

    channel_type = str(body.get("channel_type", "")).lower()
    if channel_type not in ("telegram", "signal"):
        raise HTTPException(status_code=400, detail="channel_type must be telegram or signal")

    token = str(body.get("token", "")).strip()
    channel_address = str(body.get("channel_address", "")).strip()
    if not token:
        raise HTTPException(status_code=400, detail="token is required")
    if not channel_address:
        raise HTTPException(status_code=400, detail="channel_address is required")

    token_hash = _link_token_hash(token)

    row = await db.fetch_one(
        """
        SELECT user_id
        FROM availability_channel_links
        WHERE channel_type = $1
          AND verification_token_hash = $2
          AND (token_expires_at IS NULL OR token_expires_at >= CURRENT_TIMESTAMP)
          AND verified_at IS NULL
        LIMIT 1
        """,
        (channel_type, token_hash),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Invalid or expired token")

    user_id = int(row[0])

    await db.execute(
        """
        UPDATE availability_channel_links
        SET destination = $1,
            verified_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE user_id = $2 AND channel_type = $3
        """,
        (channel_address, user_id, channel_type),
    )

    await db.execute(
        """
        INSERT INTO availability_subscriptions
            (user_id, channel_type, channel_address, enabled, verified_at, preferences, created_at, updated_at)
        VALUES ($1, $2, $3, TRUE, CURRENT_TIMESTAMP, '{}'::jsonb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (user_id, channel_type) DO UPDATE SET
            channel_address = EXCLUDED.channel_address,
            enabled = TRUE,
            verified_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        """,
        (user_id, channel_type, channel_address),
    )

    return {
        "success": True,
        "user_id": user_id,
        "channel_type": channel_type,
        "channel_address": channel_address,
    }
