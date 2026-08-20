"""Opt-in S5 contracts against the exact installed ET asset corpus."""

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
PINNED_MANIFEST = "86ddd0ec23b3c6120136195af34aa633ad249eb358ea0fb6cd6e490dd81b220d"

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
    assert manifest == PINNED_MANIFEST

    occurrences = list(
        iter_cross_frontiers(
            geometry_index,
            map_names,
            asset_manifest=manifest,
            max_paths=16,
        )
    )

    assert len(occurrences) == 452
    assert len({occurrence.occurrence_id for occurrence in occurrences}) == 452
    assert all(occurrence.path.temporal_frontier_snapshot is not None for occurrence in occurrences)
    outcomes = Counter(
        "ready" if occurrence.adaptation.ready else occurrence.adaptation.blocker_reason
        for occurrence in occurrences
    )
    assert outcomes == {
        "ready": 278,
        "frontier_schedule_outer_dispatch_context_unresolved": 99,
        "frontier_schedule_prior_lifecycle_identity_unresolved": 75,
    }


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
