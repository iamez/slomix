"""Explicit provenance for gameTime() offsets, not raw lastSpawnTime or epochs.

This records a producer declaration, not independent proof of clock accuracy.
Only the current pause-including clock is supported; no active-clock rollout.
"""

LEVEL_TIME_OFFSET_V1 = "level_time_offset_v1"


def missing_basis() -> dict:
    return {"status": "missing", "value": None}


def observe_basis(previous: dict | None, raw: str) -> dict:
    value = raw.strip()
    # Unknown strings need no storage: retain bounded evidence, not arbitrary input.
    incoming = (
        {"status": "declared", "value": value}
        if value == LEVEL_TIME_OFFSET_V1
        else {"status": "unsupported", "value": None}
    )
    if previous is None or previous["status"] == "missing":
        return incoming
    if previous == incoming and incoming["status"] == "declared":
        return previous
    return {"status": "conflicting", "value": None}


def receipt_basis_sql() -> str:
    """Fixed SQL identifiers only; independent of feature-manifest precedence.

    Missing never erases evidence; disagreement stays unknown on later replays.
    Called only within the existing processed-file upsert, no history backfill.
    """
    old = "proximity_processed_files.capabilities->'event_time_basis'"
    new = "EXCLUDED.capabilities->'event_time_basis'"
    return f"""CASE
        WHEN COALESCE(({old})->>'status', 'missing') = 'missing'
            THEN COALESCE(NULLIF({new}, 'null'::jsonb),
                 '{{"status":"missing","value":null}}'::jsonb)
        WHEN COALESCE(({new})->>'status', 'missing') = 'missing' THEN {old}
        WHEN {old} = {new} THEN {old}
        ELSE '{{"status":"conflicting","value":null}}'::jsonb
        END"""


def unanimous_basis(manifests: list[dict], *, unusable: int = 0) -> str | None:
    """Known only if EVERY resolved source explicitly declares the supported basis.

    This says nothing about source-to-round linkage accuracy or clock correctness.
    Unusable siblings count against agreement; feature declarations do not vote.
    """
    if unusable or not manifests:
        return None
    for manifest in manifests:
        basis = manifest.get("event_time_basis")
        if (not isinstance(basis, dict) or basis.get("status") != "declared"
                or basis.get("value") != LEVEL_TIME_OFFSET_V1):
            return None
    return LEVEL_TIME_OFFSET_V1
