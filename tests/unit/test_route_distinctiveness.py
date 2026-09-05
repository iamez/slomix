"""scripts/backtest_route_distinctiveness.py — the pure functions behind the
"is his route a personality or the map" measurement (docs/design/22 slice 1),
with the control that must fail."""
from __future__ import annotations

import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
import backtest_route_distinctiveness as rd  # noqa: E402


def cloud(cx: float, cy: float, n: int = 60, spread: float = 100.0, speed: float = 200.0, seed: int = 1):
    import random
    rng = random.Random(seed)  # noqa: S311 — synthetic clouds
    return [(cx + rng.uniform(-spread, spread), cy + rng.uniform(-spread, spread), speed) for _ in range(n)]


def test_cell_is_the_backends_floor_division():
    # proximity_positions.py: FLOOR(x / 512.0)
    assert rd.cell(0, 0) == (0, 0) and rd.cell(511.9, 512) == (0, 1) and rd.cell(-1, -512) == (-1, -1)
    assert rd.GRID == 512


def test_js_divergence_is_zero_for_identical_and_one_for_disjoint_and_symmetric():
    a = rd.normalize(rd.histogram(cloud(0, 0)))
    b = rd.normalize(rd.histogram(cloud(5000, 5000)))
    assert rd.js_divergence(a, a) == 0
    assert rd.js_divergence(a, b) == 1
    c = rd.normalize(rd.histogram(cloud(0, 0, seed=2) + cloud(5000, 5000, seed=3)))
    assert abs(rd.js_divergence(a, c) - rd.js_divergence(c, a)) < 1e-12
    assert 0 < rd.js_divergence(a, c) < 1


def test_nearest_point_distance_is_zero_for_the_same_cloud_and_floored_at_a_cell_when_far():
    a = cloud(0, 0)
    assert rd.nearest_point_distance(a, a) == 0
    assert rd.nearest_point_distance(a, cloud(9000, 9000)) == rd.GRID


def test_dwell_share_and_cells():
    pts = [(0, 0, 0.0)] * 3 + [(0, 0, 300.0)] * 7
    assert rd.dwell_share(pts) == 0.3
    assert rd.dwell_by_cell(pts) == [((0, 0), 3)]
    assert rd.dwell_share([(0, 0, 9.9)]) == 1.0 and rd.dwell_share([(0, 0, 10.0)]) == 0.0


def test_split_sessions_interleaves_by_date_not_first_half_last_half():
    a, b = rd.split_sessions(["2026-01-03", "2026-01-01", "2026-01-02", "2026-01-04"])
    assert a == {"2026-01-01", "2026-01-03"} and b == {"2026-01-02", "2026-01-04"}


def _rows_two_personalities(n_sessions: int = 8):
    """Player A lives around (0,0), player B around (3000,3000): a map where
    routes ARE personality. Each session a fresh sample, so the self-split
    halves differ only by sampling noise."""
    rows = []
    for i in range(n_sessions):
        rows.append(("A", f"2026-01-{i + 1:02d}", cloud(0, 0, seed=100 + i)))
        rows.append(("B", f"2026-01-{i + 1:02d}", cloud(3000, 3000, seed=200 + i)))
    return rows


def test_two_personalities_read_as_distinct_on_both_paths():
    r = rd.measure_map(_rows_two_personalities())
    assert r["self_js_median"] < 0.2 and r["cross_js_median"] == 1
    assert r["distinct_js"] > 0.5
    assert r["self_np_median"] < 50 and r["cross_np_median"] == rd.GRID
    assert r["distinct_np"] > 400
    assert r["nearest_other"]["A"][1] == "B"


def test_the_control_must_fail_shuffled_labels_collapse_the_distinctness():
    rows = _rows_two_personalities()
    real = rd.measure_map(rows)
    ctrl = rd.measure_map(rd.shuffle_labels(rows, seed=3))
    # With labels reassigned at random, a "player" is a mix of both clouds on
    # both halves: self-split and cross land together.
    assert real["distinct_js"] > 0.5
    assert abs(ctrl["distinct_js"]) < 0.25
    # The control keeps every session and point, only the labels move.
    assert sorted(s for _, s, _ in rows) == sorted(s for _, s, _ in rd.shuffle_labels(rows, seed=3))


def test_one_geometry_for_everyone_reads_as_not_distinct():
    # Everyone walks the same corridor: cross ≈ self, distinct ≈ 0.
    rows = []
    for i in range(8):
        rows.append(("A", f"2026-02-{i + 1:02d}", cloud(0, 0, seed=300 + i)))
        rows.append(("B", f"2026-02-{i + 1:02d}", cloud(0, 0, seed=400 + i)))
    r = rd.measure_map(rows)
    assert abs(r["distinct_js"]) < 0.2 and abs(r["distinct_np"]) < 50


def test_nan_when_a_side_is_empty():
    assert math.isnan(rd.js_divergence({}, {(0, 0): 1.0}))
    assert math.isnan(rd.nearest_point_distance([], [(0, 0, 0.0)]))
    assert math.isnan(rd.dwell_share([]))


def test_cross_compares_halves_so_sample_size_does_not_masquerade_as_distinctness():
    # Same geometry for both players, but few points per session spread over
    # many cells: the self halves are noisy. If cross compared FULL corpora
    # (smoother) against those noisy self halves, "distinct" would come out
    # clearly negative (measured -0.127 on the first version); halves against
    # halves keeps it at zero within noise.
    rows = []
    for i in range(8):
        rows.append(("A", f"2026-03-{i + 1:02d}", cloud(0, 0, n=20, spread=1500, seed=500 + i)))
        rows.append(("B", f"2026-03-{i + 1:02d}", cloud(0, 0, n=20, spread=1500, seed=600 + i)))
    r = rd.measure_map(rows)
    assert r["self_js_median"] > 0.15  # the halves really are noisy
    assert abs(r["distinct_js"]) < 0.05


def test_identification_is_perfect_for_six_personalities_and_near_chance_after_shuffling():
    rows = [(chr(65 + k), f"2026-01-{i + 1:02d}", cloud(3000 * k, 0, seed=100 * (k + 1) + i))
            for i in range(8) for k in range(6)]
    real = rd.measure_map(rows, with_np=False)
    assert real["identification_rate"] == 1.0 and all(real["identified"].values())
    assert math.isnan(real["self_np_median"])  # with_np=False really skips that path
    # Shuffled labels: each "player" is a mix of all six clouds on both halves,
    # so half A finds its own half B about 1 in 6 times (seeds 1–7 measured
    # 0.00–0.33). With two players the control would be a coin flip and could
    # land on 1.0 — hence six.
    ctrl = rd.measure_map(rd.shuffle_labels(rows, seed=3), with_np=False)
    assert ctrl["identification_rate"] <= 0.5
