"""Persistence for the admin-alert failure streaks.

⛔⛔ WHY A FILE AND NOT A TABLE. The streak counters decide when the bot pages
an admin, and the thing they most often page about is infrastructure. Putting
them in PostgreSQL would give the alerting path a dependency on a service it
may need to alert about — a database outage would silence the alarm that
reports the database outage. A file on local disk has no such coupling, needs
no migration (so no production deploy), and is implicitly per-host, which the
counters already are: the dev bot and the production bot are different
processes watching different servers and must never share a streak.

The precedent for this shape is `vps_scripts/stats_webhook_notify.py:70`
(`processed_files.json`, "survives restarts"), including its atomic write via
a temp file plus `os.replace`.

⛔ THIS STORE MUST NEVER RAISE INTO THE ALERTING PATH. Every read and write
swallows its errors and continues from memory. Persistence here is a memory
aid, not a source of truth: if the disk is full or the file is corrupt, the
bot must still count failures and still page admins, exactly as it did before
this module existed.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bot.logging_config import LOGS_DIR, get_logger

logger = get_logger("bot.core")

#: Where the streaks live. LOGS_DIR honours BOT_LOG_DIR, so the test suite
#: redirects this the same way it redirects errors.log — without that, tests
#: would write fixture streaks into the real state the running bot reads.
STATE_FILE = LOGS_DIR / "bot_error_streaks.json"

#: Bumped only for a change the reader cannot absorb. An unknown version is
#: ignored (start empty) rather than guessed at.
SCHEMA_VERSION = 1


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _parse_dt(raw: object) -> datetime | None:
    """Parse an ISO timestamp, returning None for anything unusable.

    Always returns an aware datetime: the whole alert path compares against
    `datetime.now(timezone.utc)`, and a naive value would raise TypeError deep
    inside `track_error` — the one place that must not raise.
    """
    if not isinstance(raw, str):
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


class ErrorStreakStore:
    """Reads and writes the failure streaks as one small JSON document."""

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path is not None else STATE_FILE
        # Log a failing disk once per process, not once per failure — a full
        # disk fails on every cycle, and the log is where the operator looks
        # to understand the alert they just got.
        self._write_error_logged = False
        self.previous_boot: datetime | None = None

    def load(self, window: timedelta, now: datetime | None = None) -> dict:
        """Return the persisted streaks, dropping any the window already ended.

        ⛔⛔ THE WINDOW APPLIES ON READ, NOT ONLY IN MEMORY. Without this, a bot
        that was down for three days would boot holding a three-day-old streak
        with `alerted` set, and the first healthy cycle would announce a
        "Recovered" for an outage that ended before the weekend. The rule that
        governs a streak in memory — idle longer than STREAK_WINDOW means the
        streak is over — has to govern it on disk too, or restarting the bot
        would resurrect exactly the stale state this window exists to retire.
        """
        now = now or datetime.now(timezone.utc)
        empty = {
            "consecutive": {},
            "started": {},
            "last_seen": {},
            "alerted": set(),
            "expired": 0,
        }

        try:
            with open(self.path, encoding="utf-8") as fh:
                document = json.load(fh)
        except FileNotFoundError:
            return empty
        except (OSError, json.JSONDecodeError) as exc:
            # A truncated write (power loss mid-replace is not possible with
            # os.replace, but a hand-edited file is) must not stop the bot.
            logger.warning(f"Error-streak state unreadable, starting empty: {exc}")
            return empty

        if not isinstance(document, dict) or document.get("version") != SCHEMA_VERSION:
            logger.warning(
                f"Error-streak state has version {document.get('version') if isinstance(document, dict) else '?'}, "
                f"expected {SCHEMA_VERSION} — starting empty"
            )
            return empty

        self.previous_boot = _parse_dt(document.get("boot_time"))

        streaks = document.get("streaks")
        if not isinstance(streaks, dict):
            return empty

        loaded = dict(empty)
        loaded["alerted"] = set()
        for key, entry in streaks.items():
            if not isinstance(key, str) or not isinstance(entry, dict):
                continue
            count = entry.get("count")
            if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
                continue
            last_seen = _parse_dt(entry.get("last_seen_at"))
            if last_seen is None:
                # A streak with no last-seen cannot be aged, and an un-ageable
                # streak is the failure this window exists to prevent.
                continue
            if now - last_seen > window:
                loaded["expired"] += 1
                continue

            loaded["consecutive"][key] = count
            loaded["last_seen"][key] = last_seen
            started = _parse_dt(entry.get("streak_started_at"))
            if started is not None:
                loaded["started"][key] = started
            if entry.get("alerted") is True:
                loaded["alerted"].add(key)

        return loaded

    def save(
        self,
        *,
        boot_time: datetime,
        consecutive: dict[str, int],
        started: dict[str, datetime],
        last_seen: dict[str, datetime],
        alerted: set[str],
        now: datetime | None = None,
    ) -> bool:
        """Write the streaks atomically. Returns False on any failure.

        ⛔ Never raises. The caller is the alerting path.
        """
        now = now or datetime.now(timezone.utc)
        document = {
            "version": SCHEMA_VERSION,
            # `written_at` and `boot_time` are for the external watchdog:
            # together they separate "the bot is dead" (written_at is stale)
            # from "the bot is alive and a streak is old".
            "written_at": _iso(now),
            "boot_time": _iso(boot_time),
            "streaks": {
                key: {
                    "count": count,
                    "streak_started_at": _iso(started.get(key)),
                    "last_seen_at": _iso(last_seen.get(key)),
                    "alerted": key in alerted,
                }
                # A zeroed counter carries no information and would grow the
                # file for the life of the deployment.
                for key, count in consecutive.items()
                if count > 0
            },
        }

        temp_path = f"{self.path}.tmp"
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(temp_path, "w", encoding="utf-8") as fh:
                json.dump(document, fh, indent=2)
            os.replace(temp_path, self.path)
            self._write_error_logged = False
            return True
        except OSError as exc:
            if not self._write_error_logged:
                logger.warning(
                    f"Could not persist error streaks to {self.path} ({exc}); "
                    f"alerting continues from memory, streaks will not survive a restart"
                )
                self._write_error_logged = True
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            return False
