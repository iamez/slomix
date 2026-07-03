"""Unit tests for /api/skill/movers (S1.2) + multi-metric form expansion."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.routers.skill_router import get_movers, get_player_form


def _row(guid, name, sid, kills, dpm, deaths=10, obj=0.0, acc=0.0,
         kq=None, trades=None, clutch=None):
    # Matches _form_rows SELECT order:
    # player_guid, player_name, gaming_session_id, kills, deaths, dpm, obj, acc,
    # kill_quality, trades, clutch_rate  (proximity trio NULL when no coverage)
    return (guid, name, sid, kills, deaths, dpm, obj, acc, kq, trades, clutch)


@pytest.mark.asyncio
async def test_movers_vs_own_baseline_with_dedup_and_new():
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[
        # latest session 124
        _row("AAA", "hot", 124, 30, 400.0),
        _row("BBB", "cold", 124, 10, 200.0),
        _row("CCC", "fresh", 124, 15, 300.0),   # no history -> new
        # history
        _row("AAA", "hot", 123, 20, 300.0),     # +33%
        _row("BBB", "cold", 123, 25, 320.0),    # -37.5%
    ])
    db.fetch_val = AsyncMock(return_value="2026-06-11")

    res = await get_movers(metric="dpm", db=db)

    assert res["session_id"] == 124
    assert res["metric"] == "dpm"
    assert [m["name"] for m in res["movers_up"]] == ["hot"]
    assert res["movers_up"][0]["delta_pct"] == 33.3
    assert [m["name"] for m in res["movers_down"]] == ["cold"]
    assert [m["name"] for m in res["new_players"]] == ["fresh"]
    # series present (oldest→newest incl latest) for the sparkline
    assert res["movers_up"][0]["series"] == [300.0, 400.0]
    # nobody appears in both lists
    up = {m["guid"] for m in res["movers_up"]}
    down = {m["guid"] for m in res["movers_down"]}
    assert not (up & down)


@pytest.mark.asyncio
async def test_movers_empty_db():
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[])
    res = await get_movers(db=db)
    assert res["session_id"] is None and res["movers_up"] == []


@pytest.mark.asyncio
async def test_movers_metric_kd():
    # K/D metric: kills/deaths per session vs own baseline.
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[
        _row("AAA", "hot", 124, 20, 100.0, deaths=10),   # latest kd = 2.0
        _row("AAA", "hot", 123, 10, 100.0, deaths=10),   # hist kd = 1.0 -> +100%
    ])
    db.fetch_val = AsyncMock(return_value="2026-06-11")
    res = await get_movers(metric="kd", db=db)
    assert res["metric"] == "kd"
    assert res["movers_up"][0]["name"] == "hot"
    assert res["movers_up"][0]["delta_pct"] == 100.0
    assert res["movers_up"][0]["latest"] == 2.0


@pytest.mark.asyncio
async def test_movers_bad_metric_falls_back_to_overall():
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[])
    res = await get_movers(metric="not-a-metric", db=db)
    assert res["metric"] == "overall"


@pytest.mark.asyncio
async def test_movers_default_metric_is_overall_composite():
    # Composite blends every metric vs the player's own baseline into ONE index
    # (100 = usual). AAA is up across the board → overall > 100 → in movers_up with
    # a per-metric breakdown; BBB is down across the board → movers_down.
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[
        # latest session 124
        _row("AAA", "hot", 124, 30, 400.0, deaths=10, obj=3.0, acc=45.0),
        _row("BBB", "cold", 124, 10, 150.0, deaths=20, obj=0.5, acc=20.0),
        # history (session 123)
        _row("AAA", "hot", 123, 15, 250.0, deaths=15, obj=1.0, acc=30.0),
        _row("BBB", "cold", 123, 25, 300.0, deaths=10, obj=2.0, acc=40.0),
    ])
    db.fetch_val = AsyncMock(return_value="2026-06-11")

    res = await get_movers(db=db)  # default metric
    assert res["metric"] == "overall"
    assert res["metric_label"] == "Overall form"
    assert "form_weights" in res
    up_names = [m["name"] for m in res["movers_up"]]
    down_names = [m["name"] for m in res["movers_down"]]
    assert "hot" in up_names and "cold" in down_names
    hot = next(m for m in res["movers_up"] if m["name"] == "hot")
    # 100 = usual; hot is above their usual on every metric → index > 100, delta > 0
    assert hot["baseline"] == 100
    assert hot["delta_pct"] > 0
    assert hot["latest"] > 100
    # breakdown carries each per-metric delta that fed the composite
    bk = {b["metric"]: b["delta_pct"] for b in hot["breakdown"]}
    assert bk["dpm"] > 0 and bk["kd"] > 0 and bk["obj"] > 0 and bk["acc"] > 0
    # composite series has one point per session (oldest→newest)
    assert len(hot["series"]) == 2


@pytest.mark.asyncio
async def test_overall_renormalizes_when_metric_missing():
    # acc is NULL everywhere → it drops out of the blend; the index is still a real
    # number built from the remaining metrics (no NaN / None).
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[
        _row("AAA", "hot", 124, 30, 400.0, deaths=10, obj=3.0, acc=0.0),
        _row("AAA", "hot", 123, 15, 250.0, deaths=15, obj=1.0, acc=0.0),
    ])
    db.fetch_val = AsyncMock(return_value="2026-06-11")
    res = await get_movers(db=db)
    hot = next(m for m in res["movers_up"] if m["name"] == "hot")
    assert hot["delta_pct"] is not None and hot["latest"] is not None
    # acc had no usable value → not in the breakdown
    assert "acc" not in {b["metric"] for b in hot["breakdown"]}


@pytest.mark.asyncio
async def test_overall_new_player_flagged():
    # Played the latest session, no prior history → FIRST NIGHT (is_new), no delta.
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[
        _row("CCC", "fresh", 124, 15, 300.0, deaths=10, obj=1.0, acc=30.0),
    ])
    db.fetch_val = AsyncMock(return_value="2026-06-11")
    res = await get_movers(db=db)
    assert [m["name"] for m in res["new_players"]] == ["fresh"]
    assert res["new_players"][0]["is_new"] is True
    assert res["new_players"][0]["delta_pct"] is None


@pytest.mark.asyncio
async def test_overall_includes_impact_when_proximity_present():
    # Sessions with proximity coverage feed an "impact" factor (KIS-proxy kill
    # quality + trade rate + clutch rate) into the composite and the breakdown.
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[
        # latest: high impact night (gibs + trades + clutch)
        _row("AAA", "hot", 124, 20, 300.0, deaths=10, obj=1.0, acc=30.0,
             kq=1.25, trades=4, clutch=0.30),
        # history: modest impact
        _row("AAA", "hot", 123, 20, 300.0, deaths=10, obj=1.0, acc=30.0,
             kq=0.90, trades=0, clutch=0.05),
    ])
    db.fetch_val = AsyncMock(return_value="2026-06-11")
    res = await get_movers(db=db)
    hot = next(m for m in res["movers_up"] if m["name"] == "hot")
    bk = {b["metric"]: b["delta_pct"] for b in hot["breakdown"]}
    # everything else is flat → the whole move comes from impact
    assert bk["impact"] > 0
    assert hot["delta_pct"] > 0
    # impact also available as its own drill-down metric
    res_imp = await get_movers(metric="impact", db=db)
    assert res_imp["metric"] == "impact"
    assert res_imp["movers_up"][0]["name"] == "hot"


@pytest.mark.asyncio
async def test_overall_without_proximity_skips_impact():
    # No proximity rows (kq NULL) → impact drops out; composite still computes
    # from the PCS metrics alone (renormalized weights).
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[
        _row("AAA", "hot", 124, 30, 400.0, deaths=10, obj=3.0, acc=45.0),
        _row("AAA", "hot", 123, 15, 250.0, deaths=15, obj=1.0, acc=30.0),
    ])
    db.fetch_val = AsyncMock(return_value="2026-06-11")
    res = await get_movers(db=db)
    hot = next(m for m in res["movers_up"] if m["name"] == "hot")
    assert hot["delta_pct"] is not None
    assert "impact" not in {b["metric"] for b in hot["breakdown"]}


@pytest.mark.asyncio
async def test_overall_zero_baseline_history_is_not_first_night():
    # Player HAS a prior session, but it was all zeros (0 kills/damage/obj, no acc)
    # → no positive baseline to rank against. They must NOT be labeled FIRST NIGHT
    # (they have history) and must not appear in up/down (nothing to compare).
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[
        _row("AAA", "ghost", 124, 20, 300.0, deaths=10, obj=1.0, acc=30.0),
        _row("AAA", "ghost", 123, 0, 0.0, deaths=10, obj=0.0, acc=None),
    ])
    db.fetch_val = AsyncMock(return_value="2026-06-11")
    res = await get_movers(db=db)
    assert res["new_players"] == []
    assert res["movers_up"] == [] and res["movers_down"] == []


@pytest.mark.asyncio
async def test_metric_without_prior_values_is_not_first_night():
    # Per-metric drill-down: prior sessions exist but never carried this metric
    # (acc NULL throughout) → skip on the acc tab, don't mislabel as FIRST NIGHT.
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[
        _row("AAA", "vet", 124, 20, 300.0, deaths=10, obj=1.0, acc=40.0),
        _row("AAA", "vet", 123, 15, 280.0, deaths=10, obj=1.0, acc=None),
    ])
    db.fetch_val = AsyncMock(return_value="2026-06-11")
    res = await get_movers(metric="acc", db=db)
    assert res["new_players"] == []
    assert res["movers_up"] == [] and res["movers_down"] == []
    # sanity: a truly new player still gets flagged on the same tab
    db.fetch_all = AsyncMock(return_value=[
        _row("BBB", "fresh", 124, 20, 300.0, deaths=10, obj=1.0, acc=40.0),
    ])
    res2 = await get_movers(metric="acc", db=db)
    assert [m["name"] for m in res2["new_players"]] == ["fresh"]


@pytest.mark.asyncio
async def test_overall_ratio_clamped_on_tiny_baseline():
    # A near-zero historical baseline would make a raw ratio explode; the clamp keeps
    # the composite index bounded well under a runaway value.
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[
        _row("AAA", "spike", 124, 30, 400.0, deaths=1, obj=5.0, acc=60.0),
        _row("AAA", "spike", 123, 1, 1.0, deaths=99, obj=0.01, acc=0.5),
    ])
    db.fetch_val = AsyncMock(return_value="2026-06-11")
    res = await get_movers(db=db)
    spike = next(m for m in res["movers_up"] if m["name"] == "spike")
    # clamp hi = 2.5 → index can't exceed 250 even with an absurd ratio
    assert spike["latest"] <= 250


@pytest.mark.asyncio
async def test_movers_full_returns_all_up_and_down():
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[
        _row("A", "a", 124, 40, 400.0), _row("A", "a", 123, 20, 300.0),  # +33 up
        _row("B", "b", 124, 40, 410.0), _row("B", "b", 123, 20, 300.0),  # +37 up
        _row("C", "c", 124, 10, 100.0), _row("C", "c", 123, 20, 200.0),  # -50 down
        _row("D", "d", 124, 10, 120.0), _row("D", "d", 123, 20, 200.0),  # -40 down
    ])
    db.fetch_val = AsyncMock(return_value="2026-06-11")
    # top=1 but full=true → all movers returned, not capped
    res = await get_movers(top=1, full=True, db=db)
    assert len(res["movers_up"]) == 2
    assert len(res["movers_down"]) == 2


@pytest.mark.asyncio
async def test_player_form_per_metric():
    db = AsyncMock()
    db.fetch_one = AsyncMock(return_value=("AAA",))  # _resolve_guid finds it
    db.fetch_all = AsyncMock(return_value=[
        _row("AAA", "hot", 124, 20, 400.0, deaths=10),  # latest: dpm 400, kd 2.0
        _row("AAA", "hot", 123, 10, 300.0, deaths=10),  # hist:   dpm 300, kd 1.0
    ])
    db.fetch_val = AsyncMock(return_value="2026-06-11")
    res = await get_player_form(identifier="AAA", db=db)
    assert res["status"] == "ok"
    assert res["player_guid"] == "AAA"
    m = res["metrics"]
    assert m["dpm"]["latest"] == 400 and m["dpm"]["delta_pct"] == 33.3
    assert m["kd"]["latest"] == 2.0 and m["kd"]["delta_pct"] == 100.0
    assert m["dpm"]["series"] == [300.0, 400.0]
    # composite Form Index present: blends the per-metric deltas into one number
    comp = res["composite"]
    assert comp is not None
    assert comp["baseline"] == 100
    assert comp["delta_pct"] > 0  # up on both metrics → above own usual
    assert {b["metric"] for b in comp["breakdown"]} >= {"dpm", "kd"}
    assert len(comp["series"]) == 2


@pytest.mark.asyncio
async def test_player_form_zero_baseline_is_not_missing():
    # A 0.0 trailing average (e.g. zero objectives in every prior session) is a
    # real baseline — it must surface as 0.0, not null. delta stays None (div/0).
    db = AsyncMock()
    db.fetch_one = AsyncMock(return_value=("AAA",))
    db.fetch_all = AsyncMock(return_value=[
        _row("AAA", "hot", 124, 20, 400.0, deaths=10, obj=2.0),
        _row("AAA", "hot", 123, 10, 300.0, deaths=10, obj=0.0),
    ])
    db.fetch_val = AsyncMock(return_value="2026-06-11")
    res = await get_player_form(identifier="AAA", db=db)
    obj = res["metrics"]["obj"]
    assert obj["baseline"] == 0.0  # present, not null
    assert obj["delta_pct"] is None  # guarded: no division by zero


@pytest.mark.asyncio
async def test_player_form_not_found():
    db = AsyncMock()
    db.fetch_one = AsyncMock(return_value=None)  # resolve + PCS fallback both miss
    res = await get_player_form(identifier="nobody", db=db)
    assert res["status"] == "error"
