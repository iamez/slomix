from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/recent")
async def get_recent_predictions(limit: int = 5, db: DatabaseAdapter = Depends(get_db)):
    """
    Get recent match predictions.
    """
    try:
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
            ORDER BY prediction_time DESC
            LIMIT $1
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
