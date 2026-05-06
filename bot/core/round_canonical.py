"""Canonical round identifier — content-addressed stable trace_id-style key.

Per ADR `docs/ADR_round_canonical_id.md`:
  round_canonical_id = sha256(f"{round_start_unix}:{map_name}:{round_number}")[:16]

Properties:
  - Stable: same canonical fields → same id, always (idempotent)
  - Content-addressed: derives from canonical timestamps only
  - Collision-free: 16-char hex = 64 bits = 1.8×10^19 space (negligible risk)
  - Cross-source verifiable: each ingest source has enough info to compute

Used as UNIQUE key in `rounds.round_canonical_id` for idempotent UPSERT
ingest pattern (Phase 3 of migration).
"""
from __future__ import annotations

import hashlib
import logging
import re

logger = logging.getLogger("round_canonical")

# Length tuning: 16 chars = 8 bytes = 2^64 space. Birthday collision at ~4×10^9
# rounds. We expect <10^6 in any decade. Headroom huge.
CANONICAL_ID_LENGTH = 16

# Map names are lowercased in DB but ET server can emit mixed case in some
# edge cases. Normalize for stable hash.
def _normalize_map(map_name: str | None) -> str:
    if not map_name:
        return ""
    # Lowercase + strip whitespace; remove ET color codes if present
    s = re.sub(r"\^[0-9A-Za-z]", "", map_name)
    return s.strip().lower()


def compute_canonical_id(
    round_start_unix: int | None,
    map_name: str | None,
    round_number: int | None,
) -> str | None:
    """Compute canonical id for a round. Returns None if any required field missing.

    Uses SHA256 truncated to CANONICAL_ID_LENGTH chars.
    """
    if round_start_unix is None or round_start_unix <= 0:
        return None
    if not map_name:
        return None
    if round_number is None or round_number not in (0, 1, 2):
        return None

    normalized_map = _normalize_map(map_name)
    if not normalized_map:
        return None

    payload = f"{int(round_start_unix)}:{normalized_map}:{int(round_number)}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return digest[:CANONICAL_ID_LENGTH]


def derive_round_start_from_stats_filename(
    filename_ts_unix: int,
    actual_duration_seconds: int | None,
) -> int | None:
    """Derive round_start_unix from native stats file (which lacks canonical timestamp in content).

    Stats file filename is os.date() at flush moment ≈ round_end + 0-3s.
    actual_duration_seconds is in file content (first line, "M:SS" format parsed elsewhere).

    Returns: estimated round_start_unix. Caller should verify via fuzzy match
    against existing rounds to confirm.
    """
    if not filename_ts_unix or filename_ts_unix <= 0:
        return None
    if actual_duration_seconds is None or actual_duration_seconds < 0:
        return None
    return int(filename_ts_unix) - int(actual_duration_seconds)


async def update_canonical_id_if_possible(db_adapter, round_id: int) -> str | None:
    """Compute and write round_canonical_id for an existing rounds row.

    Idempotent: no-op if canonical_id already set, or if round lacks
    round_start_unix. Safe to call from any ingest path after INSERT or
    UPDATE that sets round_start_unix.

    Returns the canonical_id (newly written or already present), or None
    if round can't be canonicalized (missing fields).

    Phase 2 of ADR docs/ADR_round_canonical_id.md: dual-write pattern.
    """
    if round_id is None or round_id <= 0:
        return None
    row = await db_adapter.fetch_one(
        "SELECT round_start_unix, map_name, round_number, round_canonical_id "
        "FROM rounds WHERE id = ?",
        (round_id,),
    )
    if not row:
        return None

    start_unix = row[0]
    map_name = row[1]
    round_number = row[2]
    existing_cid = row[3]

    if existing_cid:
        return existing_cid

    cid = compute_canonical_id(start_unix, map_name, round_number)
    if cid is None:
        return None

    # Conditional UPDATE: only set if still NULL (race-safe).
    # The partial UNIQUE index from migration 050 will reject this if
    # another round already owns the same canonical_id (a true collision —
    # 1 of 409 historic rounds hit this during backfill). Catch and log
    # rather than crash the calling ingest path: the round just stays
    # without a canonical id and falls back to fuzzy round_linker logic.
    try:
        await db_adapter.execute(
            "UPDATE rounds SET round_canonical_id = ? "
            "WHERE id = ? AND round_canonical_id IS NULL",
            (cid, round_id),
        )
    except Exception as e:
        # asyncpg UniqueViolationError is the expected case; we don't import
        # asyncpg here (would tie this module to a specific driver), so we
        # match by class name + repr, which is robust across driver versions.
        if "UniqueViolation" in type(e).__name__ or "uniq_rounds_canonical_id" in str(e):
            logger.warning(
                "round_canonical_id collision for round_id=%s cid=%s — leaving NULL "
                "(round will fall back to fuzzy linker)",
                round_id, cid,
            )
            return None
        raise
    return cid
