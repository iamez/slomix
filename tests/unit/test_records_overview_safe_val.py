"""Regression test for audit finding: `_safe_val` / `_safe_one` must
include a metric label in the warning log line.

Copilot review on PR #123 flagged that `[overview] query failed: …`
without a metric name made debugging back-to-back aggregations
ambiguous. This test pins the labeled warning so future refactors
don't quietly drop the `metric=` kwarg.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.routers.records_overview import _safe_one, _safe_val


@pytest.mark.asyncio
async def test_safe_val_logs_metric_name_on_failure(caplog):
    db = AsyncMock()
    db.fetch_val.side_effect = RuntimeError("boom")

    with caplog.at_level(logging.WARNING, logger="api.records.overview"):
        result = await _safe_val(db, "SELECT 1", metric="rounds_count")

    assert result == 0  # default
    assert any("rounds_count" in rec.getMessage() for rec in caplog.records)
    assert any("boom" in rec.getMessage() for rec in caplog.records)


@pytest.mark.asyncio
async def test_safe_one_logs_metric_name_on_failure(caplog):
    db = AsyncMock()
    db.fetch_one.side_effect = RuntimeError("kablooey")

    with caplog.at_level(logging.WARNING, logger="api.records.overview"):
        result = await _safe_one(db, "SELECT 1", metric="active_overall")

    assert result is None
    assert any("active_overall" in rec.getMessage() for rec in caplog.records)


@pytest.mark.asyncio
async def test_safe_val_unknown_label_when_metric_omitted(caplog):
    """Backward-compat: callers that skip the kwarg still get a sensible
    label in the log, just 'unknown' instead of blowing up."""
    db = AsyncMock()
    db.fetch_val.side_effect = RuntimeError("legacy")

    with caplog.at_level(logging.WARNING, logger="api.records.overview"):
        await _safe_val(db, "SELECT 1")

    assert any("unknown" in rec.getMessage() for rec in caplog.records)
