"""Opt-in S5 contracts against the exact installed ET asset corpus."""

import json
import os
from collections import Counter
from pathlib import Path

import pytest

from website.backend.map_geometry.pk3_index import Pk3GeometryIndex
from website.backend.map_geometry.stage_measurement import (
    asset_manifest_sha256,
    iter_cross_frontiers,
)

ETMAIN = Path(os.environ.get("SLOMIX_ETMAIN_DIR", "/home/samba/share/etmain"))
RUN_REAL_ASSET_TESTS = os.environ.get("SLOMIX_RUN_REAL_ASSET_TESTS") == "1"
EXPECTED = json.loads(
    (
        Path(__file__).resolve().parents[1]
        / "fixtures/map_geometry/w5b_s5_expected.json"
    ).read_text(encoding="utf-8")
)

pytestmark = [
    pytest.mark.timeout(120),
    pytest.mark.skipif(
        not RUN_REAL_ASSET_TESTS,
        reason="real ET map asset tests require SLOMIX_RUN_REAL_ASSET_TESTS=1",
    ),
    pytest.mark.skipif(not ETMAIN.is_dir(), reason="configured ET map asset directory is not installed"),
]


def test_s5_every_cross_frontier_has_an_exact_seed_or_named_adaptation_blocker():
    geometry_index = Pk3GeometryIndex.scan(ETMAIN)
    map_names = tuple(sorted(geometry_index.map_names))
    manifest = asset_manifest_sha256(geometry_index, map_names)
    assert list(map_names) == EXPECTED["map_names"]
    assert manifest == EXPECTED["asset_manifest_sha256"]

    occurrences = list(
        iter_cross_frontiers(
            geometry_index,
            map_names,
            asset_manifest=manifest,
            max_paths=16,
        )
    )

    expected_count = EXPECTED["summary"]["measured_cross_frontiers"]
    assert len(occurrences) == expected_count
    assert len({occurrence.occurrence_id for occurrence in occurrences}) == expected_count
    assert all(occurrence.path.temporal_frontier_snapshot is not None for occurrence in occurrences)
    outcomes = Counter(
        "ready" if occurrence.adaptation.ready else occurrence.adaptation.blocker_reason
        for occurrence in occurrences
    )
    assert outcomes == EXPECTED["raw_adaptation_inventory"]


def test_s5_occurrence_identity_is_deterministic_for_one_installed_map():
    geometry_index = Pk3GeometryIndex.scan(ETMAIN)
    map_names = ("etl_ice",)
    manifest = asset_manifest_sha256(geometry_index, map_names)

    def occurrence_ids():
        return tuple(
            occurrence.occurrence_id
            for occurrence in iter_cross_frontiers(
                geometry_index,
                map_names,
                asset_manifest=manifest,
                max_paths=16,
            )
        )

    assert occurrence_ids() == occurrence_ids()
