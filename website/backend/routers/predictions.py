import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter

router = APIRouter()
logger = logging.getLogger(__name__)


# ⛔ `limit` HAD NO BOUNDS AND `LIMIT -5` WAS A LIVE 500. The value went
# straight into the query, Postgres rejected it, and the blanket
# `except Exception` below turned the rejection into "Failed to fetch
# predictions" — an INPUT error reported as a server fault, which sends the
# reader looking in the wrong place entirely.
#
# ⭐ The bound is declared on the parameter, not checked in the body, and that
# placement is the fix: FastAPI validates before the handler runs, so a bad
# value answers 422 and never reaches the `try` that would disguise it. Same
# shape as the fix `/proximity/revives` needed — parse and bound ABOVE the
# exception handler, never inside it.
#
# `le=200` follows the storytelling feeds; every caller in the tree asks for 3
# (`app.js:483`, `probes.ts:35`, `diagnostics.js:26`), so the ceiling is
# generous rather than tight.
#
# ⚠️ This lives in a comment and not in the docstring on purpose: FastAPI
# publishes the docstring as the endpoint's description in `openapi.json`,
# which is committed, size-guarded and read by generated clients. A note about
# a bug we fixed is for whoever edits this handler, not for whoever calls it.
@router.get("/recent")
async def get_recent_predictions(
    limit: int = Query(
        default=5,
        ge=1,
        le=200,
        description="How many published predictions to return.",
    ),
    db: DatabaseAdapter = Depends(get_db),
):
    """Recent match predictions that have been published."""
    try:
        # Shadow program (AUD-006): only rows explicitly published are
        # public. Shadow rows exist purely for calibration evidence.
        query = """
            SELECT
                id,
                prediction_time,
                format,
                team_a_win_probability,
                team_b_win_probability,
                confidence,
                key_insight,
                actual_winner,
                prediction_correct,
                prediction_accuracy,
                team_a_guids,
                team_b_guids
            FROM match_predictions
            WHERE publish_state = 'published'
            ORDER BY prediction_time DESC
            LIMIT ?
        """

        # Note: fetch_all arguments might need to be a tuple depending on the adapter implementation
        # Based on previous files, it seems to expect a tuple for params.
        rows = await db.fetch_all(query, (limit,))

        predictions = []
        for row in rows:
            # Unpack row - adjust index if needed based on select order
            (
                pred_id,
                pred_time,
                fmt,
                prob_a,
                prob_b,
                conf,
                insight,
                winner,
                correct,
                accuracy,
                team_a_guids,
                team_b_guids,
            ) = row

            predictions.append(
                {
                    "id": pred_id,
                    "timestamp": pred_time,
                    "format": fmt,
                    "team_a_probability": prob_a,
                    "team_b_probability": prob_b,
                    "confidence": conf,
                    "insight": insight,
                    "actual_winner": winner,
                    "is_correct": correct,
                    "accuracy": accuracy,
                    # We might want to parse team guids if we want to show player names,
                    # but for now let's just return the raw prediction data.
                }
            )

        return predictions

    except Exception as e:
        logger.error(f"Error fetching predictions: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch predictions")
