"""Trailing per-player baselines + delta formatting (VISION_2026, S1.3).

The writing rule from the vision (R2 §6.4, Whoop pattern): no generated
narrative states a raw number without its baseline delta — "23 frags, 6 above
your usual" instead of "23 frags". This module is THE one implementation of
that rule; every narrative/recap surface should go through it.
"""
from __future__ import annotations

TRAILING_SESSIONS = 10

# Per-session aggregates we can baseline. Keys are stable public metric names.
_METRIC_EXPRS = {
    "kills": "SUM(pcs.kills)",
    "deaths": "SUM(pcs.deaths)",
    "damage_given": "SUM(pcs.damage_given)",
    "revives_given": "SUM(pcs.revives_given)",
    "dpm": "SUM(pcs.damage_given)::float / NULLIF(SUM(pcs.time_played_seconds) / 60.0, 0)",
}


async def trailing_averages(
    db, player_guid: str, *, before_session_id: int | None = None,
    n: int = TRAILING_SESSIONS,
) -> dict[str, float]:
    """Average per-session metrics over the player's last `n` sessions.

    before_session_id: exclude that session and anything newer (so "tonight"
    is compared against history, not against itself).
    """
    params: list = [player_guid]
    before_sql = ""
    if before_session_id is not None:
        params.append(before_session_id)
        before_sql = f"AND r.gaming_session_id < ${len(params)}"
    params.append(n)
    metric_cols = ", ".join(f"{expr} AS {name}" for name, expr in _METRIC_EXPRS.items())
    rows = await db.fetch_all(
        f"""
        SELECT {metric_cols}
        FROM player_comprehensive_stats pcs
        JOIN rounds r ON r.id = pcs.round_id
        WHERE pcs.player_guid = $1 AND r.gaming_session_id IS NOT NULL
          AND r.is_valid IS DISTINCT FROM FALSE
          AND pcs.time_played_seconds > 0 {before_sql}
        GROUP BY r.gaming_session_id
        ORDER BY r.gaming_session_id DESC
        LIMIT ${len(params)}
        """,  # nosec B608 - metric exprs and before_sql are module literals; values are $N-bound
        tuple(params),
    )
    if not rows:
        return {}
    names = list(_METRIC_EXPRS.keys())
    sums = [0.0] * len(names)
    for r in rows:
        for i in range(len(names)):
            sums[i] += float(r[i] or 0)
    return {
        "_sessions": float(len(rows)),
        **{name: round(sums[i] / len(rows), 2) for i, name in enumerate(names)},
    }


def format_with_baseline(
    value: float, avg: float | None, unit: str = "", *, precision: int = 0,
) -> str:
    """'23 frags — 6 above your usual' (or just the value when no history)."""
    val_str = f"{value:.{precision}f}".rstrip("0").rstrip(".") if precision else f"{value:.0f}"
    head = f"{val_str} {unit}".strip()
    if avg is None or avg <= 0:
        return head
    delta = value - avg
    if abs(delta) < max(0.5, avg * 0.05):  # within noise of the baseline
        return f"{head} (around your usual)"
    direction = "above" if delta > 0 else "below"
    delta_str = f"{abs(delta):.{precision}f}".rstrip("0").rstrip(".") if precision else f"{abs(delta):.0f}"
    return f"{head} — {delta_str} {direction} your usual"
