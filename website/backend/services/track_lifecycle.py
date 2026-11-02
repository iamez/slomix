"""Parent lifecycle is authoritative; legacy fallback is explicit terminal evidence.

Requires migration103. A missing column is a schema error, not unknown data.
Do not infer a death from a timestamp, a sample, or a capture boundary. Explicit
parent 'unknown' deliberately prevents falling back to a contradictory path.
"""


def track_end_sql(prefix: str = "") -> str:
    """SQL fragment for the two internal query aliases, never user input."""
    if prefix not in ("", "pt."):
        raise ValueError("unsupported track alias")
    event = f"{prefix}path -> -1 ->> 'event'"
    return (
        f"COALESCE({prefix}death_type, CASE WHEN {event} IN "
        "('killed','selfkill','fallen','world','teamkill','round_end','disconnect','shutdown') "
        f"THEN {event} END)"
    )
