"""Durable correction input foundation; no ingress or repair worker yet."""

import hashlib
import json
import math
import re

from bot.core.round_contract import END_REASON_ENUM


def _integer(value, field, minimum=0, maximum=2147483647):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or (isinstance(value, float) and (not math.isfinite(value) or not value.is_integer()))
            or not minimum <= value <= maximum):
        raise ValueError(f"Invalid correction inbox field: {field}")
    return int(value)


def normalize_correction_input(metadata):
    """Accept normalized producer metadata, not raw Lua round numbering.

    Unknown keys (including player data) are discarded. Missing values remain
    missing: a partial payload must not acquire invented zero-valued updates.
    """
    if not isinstance(metadata, dict):
        raise ValueError("Correction metadata must be an object")
    map_name = metadata.get("map_name")
    if not isinstance(map_name, str):
        raise ValueError("Invalid correction inbox map")
    map_name = map_name.strip().lower()
    if map_name == "unknown" or not re.fullmatch(r"[a-z0-9_-]{1,128}", map_name):
        raise ValueError("Invalid correction inbox map")
    present = metadata.get("_correction_present_fields")
    if present is not None:
        if not isinstance(present, list) or not all(isinstance(field, str) for field in present):
            raise ValueError("Invalid correction presence metadata")
        identity = {"map_name", "round_number", "round_start_unix"}
        metadata = {key: value for key, value in metadata.items() if key in identity or key in present}
    payload = {
        "map_name": map_name,
        "round_number": _integer(metadata.get("round_number"), "round_number", 1, 2),
        "round_start_unix": _integer(metadata.get("round_start_unix"), "round_start_unix", 1, 9223372036854775807),
    }
    for field in ("actual_duration_seconds", "total_pause_seconds", "pause_count"):
        if field in metadata:
            payload[field] = _integer(metadata[field], field)
    if "winner_team" in metadata:
        payload["winner_team"] = _integer(metadata["winner_team"], "winner_team", 0, 2)
    if "round_end_unix" in metadata and (
        isinstance(metadata["round_end_unix"], bool) or metadata["round_end_unix"] != 0
    ):
        payload["round_end_unix"] = _integer(metadata["round_end_unix"], "round_end_unix", 1, 9223372036854775807)
        if payload["round_end_unix"] < payload["round_start_unix"]:
            raise ValueError("Correction end precedes start")
    if "end_reason" in metadata:
        reason = metadata["end_reason"]
        if not isinstance(reason, str) or reason not in END_REASON_ENUM:
            raise ValueError("Invalid correction inbox end_reason")
        payload["end_reason"] = reason
    return payload


async def retain_lua_correction(adapter, source_key, metadata):
    """Return a stable input ID after commit; propagate all storage failures.

    source_key is a configured server identity, not a webhook URL or token.
    Caller must not ACK a surrounding transaction until that transaction commits.
    Distinct revisions are retained, not ordered or automatically applied.
    """
    if not isinstance(source_key, str) or not re.fullmatch(r"[a-z0-9_.:-]{1,64}", source_key):
        raise ValueError("Invalid correction inbox source identity")
    payload = normalize_correction_input(metadata)
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    digest = hashlib.sha256(("1:" + serialized).encode("utf-8")).hexdigest()
    async with adapter.transaction():
        row_id = await adapter.fetch_val("""
            INSERT INTO lua_correction_inputs
                (source_key, payload_version, payload_digest, map_name,
                 round_number, round_start_unix, payload)
            VALUES (?, 1, ?, ?, ?, ?, ?::jsonb)
            ON CONFLICT (source_key, payload_version, payload_digest) DO NOTHING
            RETURNING id
        """, (source_key, digest, payload["map_name"], payload["round_number"],
            payload["round_start_unix"], serialized))
        if row_id is None:
            existing = await adapter.fetch_one("""
                SELECT id, payload FROM lua_correction_inputs
                WHERE source_key=? AND payload_version=1 AND payload_digest=?
            """, (source_key, digest))
            if existing is None or json.loads(existing["payload"]) != payload:
                raise ValueError("Correction inbox digest conflict; no receipt issued")
            row_id = existing["id"]
    return row_id
