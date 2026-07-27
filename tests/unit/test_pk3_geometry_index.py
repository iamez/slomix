"""W1 contracts for deterministic, fail-closed BSP discovery in PK3 archives."""

from __future__ import annotations

import hashlib
import zipfile

import pytest

from website.backend.map_geometry.pk3_index import (
    Pk3BspConflictError,
    Pk3GeometryIndex,
    Pk3IndexError,
)


def _write_pk3(path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)


def test_scan_indexes_direct_map_bsps_and_records_sha256(tmp_path):
    bsp = b"synthetic-bsp"
    _write_pk3(
        tmp_path / "maps.pk3",
        {
            "maps/Test_Map.BSP": bsp,
            "maps/subdir/ignored.bsp": b"not a direct map member",
            "scripts/test_map.script": b"ignored",
        },
    )

    index = Pk3GeometryIndex.scan(tmp_path)
    resolution = index.resolve("TEST_MAP")

    assert index.map_names == ("test_map",)
    assert resolution.status == "geometry"
    assert resolution.selected is not None
    assert resolution.selected.sha256 == hashlib.sha256(bsp).hexdigest()
    assert resolution.selected.bsp_member == "maps/Test_Map.BSP"


def test_identical_duplicate_providers_are_kept_and_selected_deterministically(tmp_path):
    bsp = b"same geometry"
    _write_pk3(tmp_path / "z_provider.pk3", {"maps/duel.bsp": bsp})
    _write_pk3(tmp_path / "A_provider.pk3", {"maps/duel.bsp": bsp})

    index = Pk3GeometryIndex.scan(tmp_path)
    resolution = index.resolve("duel")

    assert [provider.pk3_path.name for provider in resolution.providers] == [
        "A_provider.pk3",
        "z_provider.pk3",
    ]
    assert resolution.selected == resolution.providers[0]


def test_non_identical_duplicate_providers_fail_the_whole_index(tmp_path):
    _write_pk3(tmp_path / "one.pk3", {"maps/duel.bsp": b"first"})
    _write_pk3(tmp_path / "two.pk3", {"maps/duel.bsp": b"second"})

    with pytest.raises(Pk3BspConflictError, match="non-identical BSP providers"):
        Pk3GeometryIndex.scan(tmp_path)


def test_missing_played_maps_are_explicit_and_named_in_manifest(tmp_path):
    _write_pk3(tmp_path / "one.pk3", {"maps/adlernest.bsp": b"geometry"})
    index = Pk3GeometryIndex.scan(tmp_path)

    manifest = index.manifest(["adlernest", "etl_frostbite", "radar"])

    assert manifest["maps"]["adlernest"]["status"] == "geometry"
    assert manifest["maps"]["etl_frostbite"]["status"] == "no_geometry"
    assert manifest["maps"]["radar"]["status"] == "no_geometry"
    assert manifest["summary"]["missing_maps"] == ["etl_frostbite", "radar"]
    assert manifest["summary"]["without_geometry"] == 2


def test_bad_pk3_is_not_silently_skipped(tmp_path):
    (tmp_path / "broken.pk3").write_bytes(b"not a zip")
    with pytest.raises(Pk3IndexError, match="cannot index PK3 archive"):
        Pk3GeometryIndex.scan(tmp_path)


def test_read_provider_returns_the_exact_hashed_member(tmp_path):
    content = b"chosen bsp bytes"
    _write_pk3(tmp_path / "one.pk3", {"maps/adlernest.bsp": content})
    index = Pk3GeometryIndex.scan(tmp_path)
    selected = index.resolve("adlernest").selected
    assert selected is not None

    assert index.read_provider(selected) == content
