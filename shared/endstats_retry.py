"""Opt-in publication retry ownership and always-on pending polling backoff."""

import os
import time
from dataclasses import dataclass, field


@dataclass(eq=False)
class EndstatsMarkerClaim:
    names: set[str] = field(default_factory=set)


def claim_endstats_marker(bot, filename: str):
    """Claim after DB preflight without an intervening await; OFF stays legacy."""
    if not endstats_retry_enabled():
        bot.processed_endstats_files.add(filename)
        return True
    if filename in bot.processed_endstats_files:
        return None
    owners = getattr(bot, "_endstats_marker_owners", None)
    if owners is None:
        owners = {}
        bot._endstats_marker_owners = owners  # noqa: SLF001 -- process-local ownership
    claim = EndstatsMarkerClaim({filename})
    owners[filename] = claim
    bot.processed_endstats_files.add(filename)
    return claim


def alias_endstats_marker(bot, original: str, selected: str) -> None:
    """Preserve another attempt's alias ownership; never steal its marker."""
    if endstats_retry_enabled() and selected not in bot.processed_endstats_files:
        owners = getattr(bot, "_endstats_marker_owners", {})
        claim = owners.get(original)
        if claim is not None:
            owners[selected] = claim
            claim.names.add(selected)
    bot.processed_endstats_files.add(selected)


def release_endstats_marker(bot, claim, *, legacy_filename: str | None = None) -> None:
    """Release only markers still owned by this attempt, never replacements."""
    if not isinstance(claim, EndstatsMarkerClaim):
        if legacy_filename is not None:
            bot.processed_endstats_files.discard(legacy_filename)
        return
    owners = getattr(bot, "_endstats_marker_owners", {})
    for name in claim.names:
        if owners.get(name) is claim:
            bot.processed_endstats_files.discard(name)
            owners.pop(name)


def endstats_retry_enabled() -> bool:
    return os.getenv("ENDSTATS_RETRY_ENABLED", "false").strip().lower() == "true"


async def bound_endstats_publish_failures(bot, filename: str) -> None:
    """Bound explicit False results across entry paths in this bot process.

    Persist exhaustion so a restart cannot reopen an exhausted filename.
    Pre-exhaustion counts are process-local, not a durable retry ledger.
    """
    if not endstats_retry_enabled():
        return
    counts = getattr(bot, "_endstats_publish_failures", None)
    if counts is None:
        counts = {}
        bot._endstats_publish_failures = counts  # noqa: SLF001 -- process-local producer state
    counts[filename] = counts.get(filename, 0) + 1
    limit = max(1, int(bot.endstats_retry_max_attempts))
    if counts[filename] >= limit:
        await bot.db_adapter.execute(
            "UPDATE processed_endstats_files SET error_message = 'publish_retry_exhausted' "
            "WHERE filename = $1 AND success = FALSE AND error_message = 'publish_failed'",
            (filename,),
        )


def endstats_filename_gate_query() -> str:
    """Unknown/in-flight and terminal markers stay blocking, including NULLs.

    This is eligibility only: existing scheduling and in-memory guards still
    apply. A successful handled marker is not necessarily a Discord ACK.
    """
    query = "SELECT 1 FROM processed_endstats_files WHERE filename = $1"
    if endstats_retry_enabled():
        query += " AND (success IS DISTINCT FROM FALSE OR error_message IS DISTINCT FROM 'publish_failed')"
    return query


def endstats_poll_pending(bot, filename: str) -> bool:
    """Pending identity is not new activity, even when its cooldown expires."""
    return filename in getattr(bot, "_endstats_poll_backoff", {})


def endstats_poll_due(bot, filename: str) -> bool:
    states = getattr(bot, "_endstats_poll_backoff", {})
    now = time.monotonic()
    # Remote files can disappear without another per-file callback. Drop stale
    # entries after seven days without an attempt, rather than retaining them
    # for the process lifetime. A reappearing file then gets a fresh attempt.
    for stale in [name for name, (_, due) in states.items() if now - due > 7 * 86400]:
        states.pop(stale, None)
    state = states.get(filename)
    return state is None or now >= state[1]


def defer_endstats_poll(bot, *filenames: str) -> None:
    """Keep initial normal polls, then 10m, 20m, 40m, 1h; no DB marker.

    Restart permits another attempt. Existing startup lookback still controls
    eligibility; these timers neither extend it nor schedule background work.
    """
    states = getattr(bot, "_endstats_poll_backoff", None)
    if states is None:
        states = {}
        bot._endstats_poll_backoff = states  # noqa: SLF001 -- process-local polling state
    budget = max(0, int(getattr(bot, "endstats_retry_max_attempts", 5)))
    attempt = min(budget + 4, max((states.get(f, (0, 0))[0] for f in filenames), default=0) + 1)
    delay = 0 if attempt <= budget else min(3600, 600 * 2 ** (attempt - budget - 1))
    deadline = time.monotonic() + delay
    for filename in filenames:
        states[filename] = (attempt, deadline)


def clear_endstats_poll(bot, *filenames: str) -> None:
    states = getattr(bot, "_endstats_poll_backoff", {})
    for filename in filenames:
        states.pop(filename, None)
