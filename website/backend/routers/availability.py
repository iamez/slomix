"""Date-based availability API endpoints."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import re
from datetime import date, datetime, time as dt_time, timedelta, timezone
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from website.backend.dependencies import get_db
from website.backend.logging_config import get_app_logger
from website.backend.services.contact_handle_crypto import ContactHandleCrypto, mask_contact

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
LINK_TOKEN_MIN_INTERVAL_SECONDS = max(
    5,
    int(os.getenv("AVAILABILITY_LINK_TOKEN_MIN_INTERVAL_SECONDS", "30")),
)
PROMOTION_TIMEZONE = os.getenv("AVAILABILITY_PROMOTION_TIMEZONE", "Europe/Ljubljana")
PROMOTION_TARGET_TIME = "21:00"
PROMOTION_REMINDER_TIME = "20:45"
PROMOTION_VOICE_CHECK_DELAY_SECONDS = 30
PROMOTION_DEFAULT_DRY_RUN = os.getenv("AVAILABILITY_PROMOTION_DRY_RUN_DEFAULT", "false").lower() == "true"
PROMOTION_GLOBAL_COOLDOWN = os.getenv("AVAILABILITY_PROMOTION_GLOBAL_COOLDOWN", "true").lower() == "true"
PROMOTION_CHANNEL_TYPES = ("discord", "telegram", "signal")
PROMOTION_JOB_TYPES = ("send_reminder_2045", "send_start_2100", "voice_check_2100")
PROMOTION_PREFERRED_CHANNELS = ("discord", "telegram", "signal", "any")


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


def _require_ajax_csrf_header(request: Request) -> None:
    """Require a non-simple AJAX header on state-changing session routes."""
    if request.headers.get("x-requested-with", "").lower() != "xmlhttprequest":
        raise HTTPException(status_code=403, detail="Missing required CSRF header")


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


def _website_user_id_from_user(user: Dict[str, Any]) -> Optional[int]:
    for key in ("website_user_id", "id"):
        raw = user.get(key)
        try:
            return int(raw)
        except (TypeError, ValueError):
            continue
    return None


def _promotion_timezone() -> ZoneInfo:
    try:
        return ZoneInfo(PROMOTION_TIMEZONE)
    except Exception:
        return ZoneInfo("UTC")


def _parse_hhmm(value: str) -> tuple[int, int]:
    match = re.match(r"^([01]\d|2[0-3]):([0-5]\d)$", str(value or "").strip())
    if not match:
        raise ValueError("Expected HH:MM")
    return int(match.group(1)), int(match.group(2))


def _build_localized_datetime(target_date: date, hhmm: str) -> datetime:
    hour, minute = _parse_hhmm(hhmm)
    local = datetime.combine(target_date, dt_time(hour=hour, minute=minute))
    return local.replace(tzinfo=_promotion_timezone())


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).isoformat()
    return value.astimezone(timezone.utc).isoformat()


def _coerce_preferred_channel(value: Any) -> str:
    normalized = str(value or "any").strip().lower()
    if normalized not in PROMOTION_PREFERRED_CHANNELS:
        raise HTTPException(
            status_code=400,
            detail=f"preferred_channel must be one of: {', '.join(PROMOTION_PREFERRED_CHANNELS)}",
        )
    return normalized


def _coerce_timezone(value: Any, *, default: str) -> str:
    candidate = str(value or default).strip()
    if not candidate:
        candidate = default
    try:
        ZoneInfo(candidate)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid timezone")
    return candidate


def _normalize_quiet_hours(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise HTTPException(status_code=400, detail="quiet_hours must be an object")

    start = value.get("start")
    end = value.get("end")
    if not start and not end:
        return {}
    if not isinstance(start, str) or not isinstance(end, str):
        raise HTTPException(status_code=400, detail="quiet_hours.start/end must be HH:MM strings")
    try:
        _parse_hhmm(start)
        _parse_hhmm(end)
    except ValueError:
        raise HTTPException(status_code=400, detail="quiet_hours.start/end must be HH:MM strings")
    return {"start": start, "end": end}


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


def _as_utc_datetime(value: Any) -> Optional[datetime]:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


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
        # user_permissions might not exist in local/dev snapshots.
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
            # Rollout fallback: if new link table does not exist, legacy path below.
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


async def _require_linked_user(request: Request, db) -> tuple[Dict[str, Any], int]:
    user = _require_user(request)
    try:
        user_id = int(user["id"])
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid user session")

    if not await _is_discord_linked(user, db):
        raise HTTPException(status_code=403, detail="Linked Discord account required")

    return user, user_id


def _require_identity_user(request: Request) -> tuple[Dict[str, Any], int, int]:
    user = _require_user(request)
    try:
        discord_user_id = int(user["id"])
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid user session")
    website_user_id = _website_user_id_from_user(user)
    if website_user_id is None:
        website_user_id = discord_user_id
    return user, discord_user_id, int(website_user_id)


def _contact_crypto() -> ContactHandleCrypto:
    return ContactHandleCrypto.from_env()


def _channel_for_recipient(
    *,
    preferred_channel: str,
    telegram_handle: str | None,
    signal_handle: str | None,
    discord_user_id: int,
) -> tuple[str | None, str | None]:
    preferred = preferred_channel.lower()
    if preferred not in PROMOTION_PREFERRED_CHANNELS:
        preferred = "any"

    options = []
    if preferred == "telegram":
        options = [("telegram", telegram_handle), ("signal", signal_handle), ("discord", str(discord_user_id))]
    elif preferred == "signal":
        options = [("signal", signal_handle), ("telegram", telegram_handle), ("discord", str(discord_user_id))]
    elif preferred == "discord":
        options = [("discord", str(discord_user_id)), ("telegram", telegram_handle), ("signal", signal_handle)]
    else:
        options = [("telegram", telegram_handle), ("signal", signal_handle), ("discord", str(discord_user_id))]

    for channel_type, target in options:
        if channel_type == "discord":
            return channel_type, target
        if target and str(target).strip():
            return channel_type, str(target).strip()

    return None, None


def _public_campaign_recipients(raw_recipients: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    sanitized: list[Dict[str, Any]] = []
    for recipient in raw_recipients:
        if not isinstance(recipient, dict):
            continue
        display_name = str(recipient.get("display_name") or "").strip()
        status = str(recipient.get("status") or "").strip().upper()
        selected_channel = str(recipient.get("selected_channel") or "discord").strip().lower()
        if not display_name:
            continue
        sanitized.append(
            {
                "display_name": display_name,
                "status": status,
                "selected_channel": selected_channel,
            }
        )
    return sanitized


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
    website_user_id = _website_user_id_from_user(user) if authenticated else None
    can_promote = await _is_promoter_user(request, db) if authenticated and linked else False
    return {
        "authenticated": authenticated,
        "linked_discord": linked,
        "can_submit": authenticated and linked,
        "is_admin": _is_admin_user(request) if authenticated else False,
        "can_promote": bool(can_promote),
        "website_user_id": website_user_id,
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
    _require_ajax_csrf_header(request)
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
    _require_ajax_csrf_header(request)

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
    _require_ajax_csrf_header(request)
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


@router.delete("/subscriptions/{channel_type}")
async def delete_subscription_channel(channel_type: str, request: Request, db=Depends(get_db)):
    """Unlink and disable a Telegram/Signal subscription channel."""
    _user, user_id = await _require_linked_user(request, db)
    _require_ajax_csrf_header(request)

    channel = str(channel_type or "").strip().lower()
    if channel not in ("telegram", "signal"):
        raise HTTPException(status_code=400, detail="channel_type must be telegram or signal")

    await db.execute(
        "DELETE FROM availability_subscriptions WHERE user_id = $1 AND channel_type = $2",
        (user_id, channel),
    )
    await db.execute(
        "DELETE FROM availability_channel_links WHERE user_id = $1 AND channel_type = $2",
        (user_id, channel),
    )

    if channel == "telegram":
        await db.execute(
            """
            UPDATE subscription_preferences
            SET telegram_handle_encrypted = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = $1
            """,
            (user_id,),
        )
    else:
        await db.execute(
            """
            UPDATE subscription_preferences
            SET signal_handle_encrypted = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = $1
            """,
            (user_id,),
        )

    return {
        "success": True,
        "user_id": user_id,
        "channel_type": channel,
        "unlinked": True,
    }


@router.post("/link-token")
async def create_link_token(request: Request, db=Depends(get_db)):
    """Create one-time token for Telegram/Signal subscription linking."""
    _user, user_id = await _require_linked_user(request, db)
    _require_ajax_csrf_header(request)
    body = await request.json()

    channel_type = str(body.get("channel_type", "")).lower()
    if channel_type not in ("telegram", "signal"):
        raise HTTPException(status_code=400, detail="channel_type must be telegram or signal")

    existing_request = await db.fetch_one(
        """
        SELECT verification_requested_at
        FROM availability_channel_links
        WHERE user_id = $1 AND channel_type = $2
        LIMIT 1
        """,
        (user_id, channel_type),
    )
    if existing_request and existing_request[0] is not None:
        last_requested_at = _as_utc_datetime(existing_request[0])
        if last_requested_at is not None:
            elapsed = (datetime.now(timezone.utc) - last_requested_at).total_seconds()
            if elapsed < LINK_TOKEN_MIN_INTERVAL_SECONDS:
                retry_after = max(1, int(LINK_TOKEN_MIN_INTERVAL_SECONDS - elapsed))
                raise HTTPException(
                    status_code=429,
                    detail=f"Link token was generated recently. Try again in {retry_after}s",
                )

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


async def _load_subscription_preference_row(db, website_user_id: int):
    return await db.fetch_one(
        """
        SELECT allow_promotions,
               preferred_channel,
               telegram_handle_encrypted,
               signal_handle_encrypted,
               quiet_hours,
               timezone,
               notify_threshold
        FROM subscription_preferences
        WHERE user_id = $1
        LIMIT 1
        """,
        (website_user_id,),
    )


def _decode_json_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            loaded = json.loads(value)
            if isinstance(loaded, dict):
                return loaded
        except json.JSONDecodeError:
            return {}
    return {}


def _decode_json_list(value: Any) -> list[Dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, str):
        try:
            loaded = json.loads(value)
            if isinstance(loaded, list):
                return [item for item in loaded if isinstance(item, dict)]
        except json.JSONDecodeError:
            return []
    return []


async def _collect_campaign_recipients(
    db,
    *,
    target_date: date,
    include_maybe: bool,
    include_available: bool,
) -> tuple[list[Dict[str, Any]], Dict[str, int]]:
    rows = await db.fetch_all(
        """
        SELECT user_id, user_name, status
        FROM availability_entries
        WHERE entry_date = $1
          AND status IN ('LOOKING', 'AVAILABLE', 'MAYBE')
        ORDER BY updated_at DESC
        """,
        (target_date,),
    )

    allowed_statuses = {"LOOKING"}
    if include_available:
        allowed_statuses.add("AVAILABLE")
    if include_maybe:
        allowed_statuses.add("MAYBE")

    crypto = _contact_crypto()
    recipients: list[Dict[str, Any]] = []
    channels_summary: Dict[str, int] = {channel: 0 for channel in PROMOTION_CHANNEL_TYPES}
    seen: set[int] = set()

    for row in rows or []:
        discord_user_id = int(row[0])
        if discord_user_id in seen:
            continue
        seen.add(discord_user_id)

        status = str(row[2] or "").upper()
        if status not in allowed_statuses:
            continue

        pref_row = await _load_subscription_preference_row(db, discord_user_id)
        allow_promotions = bool(pref_row[0]) if pref_row else False
        if not allow_promotions:
            continue

        preferred_channel = str(pref_row[1] or "any").lower() if pref_row else "any"
        telegram_handle_encrypted = pref_row[2] if pref_row else None
        signal_handle_encrypted = pref_row[3] if pref_row else None
        quiet_hours = _decode_json_dict(pref_row[4]) if pref_row else {}
        pref_timezone = str(pref_row[5] or "Europe/Ljubljana") if pref_row else "Europe/Ljubljana"

        telegram_handle = crypto.decrypt(telegram_handle_encrypted)
        signal_handle = crypto.decrypt(signal_handle_encrypted)

        channel_type, _target = _channel_for_recipient(
            preferred_channel=preferred_channel,
            telegram_handle=telegram_handle,
            signal_handle=signal_handle,
            discord_user_id=discord_user_id,
        )
        if not channel_type:
            continue

        player_row = await db.fetch_one(
            "SELECT player_name, discord_username FROM player_links WHERE discord_id = $1 LIMIT 1",
            (discord_user_id,),
        )
        display_name = (
            (player_row[0] if player_row else None)
            or (player_row[1] if player_row else None)
            or row[1]
            or f"User {discord_user_id}"
        )

        recipients.append(
            {
                "user_id": discord_user_id,
                "display_name": str(display_name),
                "status": status,
                "selected_channel": channel_type,
                "preferred_channel": preferred_channel,
                "timezone": pref_timezone,
                "quiet_hours": quiet_hours,
                "telegram_handle_encrypted": telegram_handle_encrypted,
                "signal_handle_encrypted": signal_handle_encrypted,
            }
        )
        channels_summary[channel_type] += 1

    return recipients, channels_summary


def _promotion_idempotency_key(
    *,
    target_date: date,
    promoter_user_id: int,
    include_maybe: bool,
    include_available: bool,
    dry_run: bool,
) -> str:
    raw = (
        f"{target_date.isoformat()}:{promoter_user_id}:"
        f"{int(include_maybe)}:{int(include_available)}:{int(dry_run)}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


async def _campaign_payload(db, campaign_id: int) -> Dict[str, Any]:
    row = await db.fetch_one(
        """
        SELECT id,
               campaign_date,
               target_timezone,
               target_start_time,
               initiated_by_user_id,
               initiated_by_discord_id,
               include_maybe,
               include_available,
               dry_run,
               status,
               recipient_count,
               channels_summary,
               recipients_snapshot,
               created_at,
               updated_at
        FROM availability_promotion_campaigns
        WHERE id = $1
        LIMIT 1
        """,
        (campaign_id,),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Campaign not found")

    jobs = await db.fetch_all(
        """
        SELECT id, job_type, run_at, status, attempts, max_attempts, last_error, sent_at
        FROM availability_promotion_jobs
        WHERE campaign_id = $1
        ORDER BY run_at ASC, id ASC
        """,
        (campaign_id,),
    )

    return {
        "id": int(row[0]),
        "campaign_date": _normalize_date(row[1]).isoformat(),
        "target_timezone": str(row[2] or PROMOTION_TIMEZONE),
        "target_start_time": str(row[3] or PROMOTION_TARGET_TIME),
        "initiated_by_user_id": int(row[4]),
        "initiated_by_discord_id": int(row[5]),
        "include_maybe": bool(row[6]),
        "include_available": bool(row[7]),
        "dry_run": bool(row[8]),
        "status": str(row[9]),
        "recipient_count": int(row[10] or 0),
        "channels_summary": _decode_json_dict(row[11]),
        "created_at": _serialize_value(row[13]),
        "updated_at": _serialize_value(row[14]),
        "jobs": [
            {
                "id": int(job[0]),
                "job_type": str(job[1]),
                "run_at": _serialize_value(job[2]),
                "status": str(job[3]),
                "attempts": int(job[4] or 0),
                "max_attempts": int(job[5] or 0),
                "last_error": job[6],
                "sent_at": _serialize_value(job[7]),
            }
            for job in (jobs or [])
        ],
    }


@router.get("/promotion-preferences")
async def get_promotion_preferences(request: Request, db=Depends(get_db)):
    _user, _discord_user_id, website_user_id = _require_identity_user(request)
    row = await _load_subscription_preference_row(db, website_user_id)

    crypto = _contact_crypto()
    if not row:
        return {
            "user_id": website_user_id,
            "allow_promotions": False,
            "preferred_channel": "any",
            "telegram_handle": None,
            "telegram_handle_masked": None,
            "signal_handle": None,
            "signal_handle_masked": None,
            "quiet_hours": {},
            "timezone": "Europe/Ljubljana",
            "notify_threshold": 0,
            "encryption_enabled": bool(crypto.enabled),
        }

    telegram_handle = crypto.decrypt(row[2])
    signal_handle = crypto.decrypt(row[3])
    quiet_hours = _decode_json_dict(row[4])

    return {
        "user_id": website_user_id,
        "allow_promotions": bool(row[0]),
        "preferred_channel": str(row[1] or "any"),
        "telegram_handle": telegram_handle,
        "telegram_handle_masked": mask_contact(telegram_handle),
        "signal_handle": signal_handle,
        "signal_handle_masked": mask_contact(signal_handle),
        "quiet_hours": quiet_hours,
        "timezone": str(row[5] or "Europe/Ljubljana"),
        "notify_threshold": int(row[6] or 0),
        "encryption_enabled": bool(crypto.enabled),
        "encryption_reason": crypto.reason,
    }


@router.post("/promotion-preferences")
async def upsert_promotion_preferences(request: Request, db=Depends(get_db)):
    _user, _discord_user_id, website_user_id = _require_identity_user(request)
    _require_ajax_csrf_header(request)
    body = await request.json()

    allow_promotions = _coerce_bool(body.get("allow_promotions"), default=False)
    preferred_channel = _coerce_preferred_channel(body.get("preferred_channel"))
    quiet_hours = _normalize_quiet_hours(body.get("quiet_hours"))
    pref_timezone = _coerce_timezone(body.get("timezone"), default="Europe/Ljubljana")

    notify_threshold = body.get("notify_threshold", 0)
    try:
        notify_threshold = int(notify_threshold)
    except (TypeError, ValueError):
        notify_threshold = 0
    notify_threshold = max(0, min(notify_threshold, 99))

    telegram_handle = body.get("telegram_handle")
    signal_handle = body.get("signal_handle")
    if telegram_handle is not None:
        telegram_handle = str(telegram_handle).strip() or None
    if signal_handle is not None:
        signal_handle = str(signal_handle).strip() or None

    if (telegram_handle or signal_handle) and not allow_promotions:
        raise HTTPException(
            status_code=400,
            detail="allow_promotions must be true to save telegram/signal handles",
        )

    crypto = _contact_crypto()
    try:
        telegram_encrypted = crypto.encrypt(telegram_handle)
        signal_encrypted = crypto.encrypt(signal_handle)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    quiet_hours_json = json.dumps(quiet_hours, ensure_ascii=True)

    await db.execute(
        """
        INSERT INTO subscription_preferences
            (user_id, allow_promotions, preferred_channel, telegram_handle_encrypted, signal_handle_encrypted,
             quiet_hours, timezone, notify_threshold, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, CAST($6 AS JSONB), $7, $8, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (user_id) DO UPDATE SET
            allow_promotions = EXCLUDED.allow_promotions,
            preferred_channel = EXCLUDED.preferred_channel,
            telegram_handle_encrypted = EXCLUDED.telegram_handle_encrypted,
            signal_handle_encrypted = EXCLUDED.signal_handle_encrypted,
            quiet_hours = EXCLUDED.quiet_hours,
            timezone = EXCLUDED.timezone,
            notify_threshold = EXCLUDED.notify_threshold,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            website_user_id,
            allow_promotions,
            preferred_channel,
            telegram_encrypted,
            signal_encrypted,
            quiet_hours_json,
            pref_timezone,
            notify_threshold,
        ),
    )

    return await get_promotion_preferences(request=request, db=db)


@router.get("/promotions/preview")
async def preview_promotion_campaign(
    request: Request,
    include_maybe: bool = Query(default=False),
    include_available: bool = Query(default=False),
    db=Depends(get_db),
):
    user, _discord_user_id, _website_user_id = _require_identity_user(request)
    if not await _is_discord_linked(user, db):
        raise HTTPException(status_code=403, detail="Linked Discord account required")
    if not await _is_promoter_user(request, db):
        raise HTTPException(status_code=403, detail="Promoter permission required")

    target_date = await _current_db_date(db)
    recipients, channels_summary = await _collect_campaign_recipients(
        db,
        target_date=target_date,
        include_maybe=include_maybe,
        include_available=include_available,
    )
    return {
        "campaign_date": target_date.isoformat(),
        "target_time_cet": PROMOTION_TARGET_TIME,
        "reminder_time_cet": PROMOTION_REMINDER_TIME,
        "recipient_count": len(recipients),
        "channels_summary": channels_summary,
        "recipients_preview": _public_campaign_recipients(recipients),
    }


@router.post("/promotions/campaigns")
async def create_promotion_campaign(request: Request, db=Depends(get_db)):
    user, discord_user_id, website_user_id = _require_identity_user(request)
    if not await _is_discord_linked(user, db):
        raise HTTPException(status_code=403, detail="Linked Discord account required")
    if not await _is_promoter_user(request, db):
        raise HTTPException(status_code=403, detail="Promoter permission required")
    _require_ajax_csrf_header(request)

    body = await request.json()
    include_maybe = _coerce_bool(body.get("include_maybe"), default=False)
    include_available = _coerce_bool(body.get("include_available"), default=False)
    dry_run = _coerce_bool(body.get("dry_run"), default=PROMOTION_DEFAULT_DRY_RUN)

    target_date = await _current_db_date(db)

    if PROMOTION_GLOBAL_COOLDOWN:
        existing_global = await db.fetch_one(
            """
            SELECT id
            FROM availability_promotion_campaigns
            WHERE campaign_date = $1
            LIMIT 1
            """,
            (target_date,),
        )
        if existing_global:
            raise HTTPException(status_code=409, detail="A promotion campaign already exists for today")

    existing_user_campaign = await db.fetch_one(
        """
        SELECT id
        FROM availability_promotion_campaigns
        WHERE campaign_date = $1
          AND initiated_by_user_id = $2
        LIMIT 1
        """,
        (target_date, website_user_id),
    )
    if existing_user_campaign:
        raise HTTPException(status_code=409, detail="You already created a campaign for today")

    recipients, channels_summary = await _collect_campaign_recipients(
        db,
        target_date=target_date,
        include_maybe=include_maybe,
        include_available=include_available,
    )

    if dry_run:
        promoter_name = (
            str(user.get("linked_player") or user.get("display_name") or user.get("username") or f"User {discord_user_id}")
        )
        recipients = [
            {
                "user_id": int(discord_user_id),
                "display_name": promoter_name,
                "status": "LOOKING",
                "selected_channel": "discord",
                "preferred_channel": "discord",
                "timezone": "Europe/Ljubljana",
                "quiet_hours": {},
                "telegram_handle_encrypted": None,
                "signal_handle_encrypted": None,
            }
        ]
        channels_summary = {"discord": 1, "telegram": 0, "signal": 0}

    idempotency_key = _promotion_idempotency_key(
        target_date=target_date,
        promoter_user_id=website_user_id,
        include_maybe=include_maybe,
        include_available=include_available,
        dry_run=dry_run,
    )

    reminder_local = _build_localized_datetime(target_date, PROMOTION_REMINDER_TIME)
    start_local = _build_localized_datetime(target_date, PROMOTION_TARGET_TIME)
    voice_check_local = start_local + timedelta(seconds=PROMOTION_VOICE_CHECK_DELAY_SECONDS)
    now_utc = datetime.now(timezone.utc)

    reminder_at = reminder_local.astimezone(timezone.utc)
    start_at = start_local.astimezone(timezone.utc)
    voice_check_at = voice_check_local.astimezone(timezone.utc)
    if reminder_at < now_utc:
        reminder_at = now_utc + timedelta(seconds=10)
    if start_at < now_utc:
        start_at = now_utc + timedelta(seconds=20)
    if voice_check_at <= start_at:
        voice_check_at = start_at + timedelta(seconds=PROMOTION_VOICE_CHECK_DELAY_SECONDS)

    recipients_json = json.dumps(recipients, ensure_ascii=True)
    channels_summary_json = json.dumps(channels_summary, ensure_ascii=True)

    row = await db.fetch_one(
        """
        INSERT INTO availability_promotion_campaigns
            (campaign_date, target_timezone, target_start_time, initiated_by_user_id, initiated_by_discord_id,
             include_maybe, include_available, dry_run, status, idempotency_key,
             recipient_count, channels_summary, recipients_snapshot, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'scheduled', $9, $10, CAST($11 AS JSONB), CAST($12 AS JSONB),
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        RETURNING id
        """,
        (
            target_date,
            PROMOTION_TIMEZONE,
            PROMOTION_TARGET_TIME,
            website_user_id,
            discord_user_id,
            include_maybe,
            include_available,
            dry_run,
            idempotency_key,
            len(recipients),
            channels_summary_json,
            recipients_json,
        ),
    )
    if not row:
        raise HTTPException(status_code=500, detail="Failed to create promotion campaign")

    campaign_id = int(row[0])
    job_payload = json.dumps(
        {
            "campaign_date": target_date.isoformat(),
            "timezone": PROMOTION_TIMEZONE,
            "target_time_cet": PROMOTION_TARGET_TIME,
            "reminder_time_cet": PROMOTION_REMINDER_TIME,
        },
        ensure_ascii=True,
    )

    job_specs = [
        ("send_reminder_2045", reminder_at),
        ("send_start_2100", start_at),
        ("voice_check_2100", voice_check_at),
    ]
    for job_type, run_at in job_specs:
        await db.execute(
            """
            INSERT INTO availability_promotion_jobs
                (campaign_id, job_type, run_at, status, attempts, max_attempts, payload, created_at, updated_at)
            VALUES ($1, $2, $3, 'pending', 0, 5, CAST($4 AS JSONB), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (campaign_id, job_type) DO NOTHING
            """,
            (campaign_id, job_type, run_at, job_payload),
        )

    return {
        "success": True,
        "campaign_id": campaign_id,
        "campaign_date": target_date.isoformat(),
        "status": "scheduled",
        "recipient_count": len(recipients),
        "channels_summary": channels_summary,
        "scheduled_times": {
            "reminder_2045_cet": _utc_iso(reminder_at),
            "start_2100_cet": _utc_iso(start_at),
            "voice_check_after_start": _utc_iso(voice_check_at),
        },
        "dry_run": dry_run,
    }


@router.get("/promotions/campaign")
async def get_today_promotion_campaign(
    request: Request,
    target_date: Optional[date] = Query(default=None, alias="date"),
    db=Depends(get_db),
):
    _user = _require_user(request)
    campaign_date = target_date or await _current_db_date(db)
    row = await db.fetch_one(
        """
        SELECT id
        FROM availability_promotion_campaigns
        WHERE campaign_date = $1
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (campaign_date,),
    )
    if not row:
        return {"campaign": None}
    payload = await _campaign_payload(db, int(row[0]))
    return {"campaign": payload}
