"""
Tests for RoundCorrelationService assembly behavior.

SKIPPED: The RoundCorrelationService was simplified from an assembly-based
architecture (with map_play_seq FIFO, orphan R2 tracking, pending events)
to a simpler correlation-row upsert model. These tests tested the old
assembly logic (round_assemblies table, round_assembly_events table,
map_play_seq assignment) which no longer exists.

The current service:
- Uses simple INSERT/UPDATE on round_correlations table
- Uses ? placeholder SQL (not $n)
- Does not track assemblies, map_play_seq, or pending events
- Does not assign FIFO ordering to repeated map rounds
"""
from __future__ import annotations

import pytest


@pytest.mark.skip(reason="RoundCorrelationService no longer manages round_assemblies or map_play_seq; simplified to correlation-row upserts")
def test_repeated_same_map_rounds_assign_fifo_map_play_seq():
    pass


@pytest.mark.skip(reason="RoundCorrelationService no longer tracks pending non-stats events or round_assembly_events")
def test_pending_non_stats_events_attach_fifo_on_anchor_arrival():
    pass


@pytest.mark.skip(reason="RoundCorrelationService no longer manages orphan R2 detection or late R1 claiming")
def test_r2_without_open_r1_creates_orphan_then_late_r1_claims_same_seq():
    pass


@pytest.mark.skip(reason="RoundCorrelationService.get_status_summary() no longer returns pending_events or orphan_r2 fields")
def test_status_summary_includes_pending_and_orphan_details():
    pass
