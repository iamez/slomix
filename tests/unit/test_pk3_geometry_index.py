"""W1 contracts for content-verified ET map asset discovery."""

from __future__ import annotations

import hashlib
import zipfile

import pytest

from website.backend.map_geometry.pk3_index import (
    AssetContentChangedError,
    MapAssetKind,
    Pk3GeometryIndex,
    Pk3IndexError,
)


def _write_pk3(path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)


def test_scan_indexes_every_direct_consumed_asset_and_records_sha256(tmp_path):
    contents = {
        MapAssetKind.BSP: b"synthetic-bsp",
        MapAssetKind.SCRIPT: b"synthetic-script",
        MapAssetKind.OBJDATA: b"synthetic-objdata",
    }
    _write_pk3(
        tmp_path / "maps.pk3",
        {
            "maps/Test_Map.BSP": contents[MapAssetKind.BSP],
            "maps/Test_Map.script": contents[MapAssetKind.SCRIPT],
            "maps/Test_Map.objdata": contents[MapAssetKind.OBJDATA],
            "maps/subdir/ignored.bsp": b"not a direct map member",
            "scripts/test_map.script": b"wrong directory",
        },
    )

    index = Pk3GeometryIndex.scan(tmp_path)

    assert index.map_names == ("test_map",)
    assert index.asset_map_names == ("test_map",)
    for kind, content in contents.items():
        resolution = index.resolve_asset("TEST_MAP", kind)
        assert resolution.status == "resolved"
        assert resolution.selected is not None
        assert resolution.selected.asset_kind is kind
        assert resolution.selected.sha256 == hashlib.sha256(content).hexdigest()
        assert resolution.selected.member.casefold() == f"maps/test_map.{kind.value}"


def test_identical_duplicate_providers_are_kept_and_selected_deterministically(tmp_path):
    content = b"same script"
    _write_pk3(tmp_path / "z_provider.pk3", {"maps/duel.script": content})
    _write_pk3(tmp_path / "A_provider.pk3", {"maps/duel.script": content})

    index = Pk3GeometryIndex.scan(tmp_path)
    resolution = index.resolve_asset("duel", "script")

    assert [provider.pk3_path.name for provider in resolution.providers] == [
        "A_provider.pk3",
        "z_provider.pk3",
    ]
    assert resolution.status == "resolved"
    assert resolution.selected == resolution.providers[0]


def test_provider_order_has_exact_case_tie_breakers(tmp_path):
    content = b"same script"
    _write_pk3(tmp_path / "a.pk3", {"maps/duel.script": content})
    _write_pk3(tmp_path / "A.pk3", {"maps/duel.script": content})
    _write_pk3(
        tmp_path / "members.pk3",
        {
            "maps/CASE.script": content,
            "maps/case.script": content,
        },
    )

    index = Pk3GeometryIndex.scan(tmp_path)

    duel = index.resolve_asset("duel", "script")
    assert [provider.pk3_path.name for provider in duel.providers] == ["A.pk3", "a.pk3"]
    case = index.resolve_asset("case", "script")
    assert [provider.member for provider in case.providers] == ["maps/CASE.script", "maps/case.script"]


def test_differing_bsp_providers_are_reported_as_ambiguous(tmp_path):
    _write_pk3(tmp_path / "one.pk3", {"maps/duel.bsp": b"first"})
    _write_pk3(tmp_path / "two.pk3", {"maps/duel.bsp": b"second"})

    index = Pk3GeometryIndex.scan(tmp_path)
    resolution = index.resolve("duel")

    assert resolution.status == "ambiguous_geometry"
    assert resolution.selected is None
    assert len(resolution.providers) == 2
    assert "verified live pak precedence is unavailable" in (resolution.reason or "")
    with pytest.raises(Pk3IndexError, match="no unambiguous BSP geometry"):
        index.load_bsp("duel")


def test_each_asset_kind_resolves_independently(tmp_path):
    bsp = b"same geometry"
    _write_pk3(
        tmp_path / "one.pk3",
        {
            "maps/duel.bsp": bsp,
            "maps/duel.script": b"first script",
            "maps/duel.objdata": b"only objdata",
        },
    )
    _write_pk3(
        tmp_path / "two.pk3",
        {
            "maps/duel.bsp": bsp,
            "maps/duel.script": b"second script",
        },
    )

    index = Pk3GeometryIndex.scan(tmp_path)

    assert index.resolve("duel").status == "geometry"
    assert index.resolve_asset("duel", "script").status == "ambiguous"
    assert index.resolve_asset("duel", ".objdata").status == "resolved"

    manifest = index.manifest(["duel"])
    assert manifest["maps"]["duel"]["assets"]["bsp"]["status"] == "resolved"
    assert manifest["maps"]["duel"]["assets"]["script"]["selected"] is None
    assert manifest["maps"]["duel"]["assets"]["objdata"]["status"] == "resolved"
    assert manifest["summary"]["asset_status_counts"]["script"]["ambiguous"] == 1


def test_entity_override_indexes_pk3_and_loose_vfs_candidates_without_inventing_precedence(tmp_path):
    pk3_content = b'{ "classname" "worldspawn" "source" "pk3" }'
    loose_content = b'{ "classname" "worldspawn" "source" "loose" }'
    _write_pk3(tmp_path / "entities.pk3", {"maps/duel.ent": pk3_content})
    maps_dir = tmp_path / "maps"
    maps_dir.mkdir()
    loose_path = maps_dir / "duel.ent"
    loose_path.write_bytes(loose_content)

    index = Pk3GeometryIndex.scan(tmp_path)
    resolution = index.resolve_asset("duel", MapAssetKind.ENTITY_OVERRIDE)

    assert resolution.status == "ambiguous"
    assert resolution.selected is None
    assert len(resolution.providers) == 2
    assert {provider.is_loose_file for provider in resolution.providers} == {False, True}
    loose = next(provider for provider in resolution.providers if provider.is_loose_file)
    assert loose.source == str(loose_path)
    assert index.read_provider(loose) == loose_content


def test_identical_loose_and_pk3_entity_overrides_are_content_resolved(tmp_path):
    content = b'{ "classname" "worldspawn" }'
    _write_pk3(tmp_path / "entities.pk3", {"maps/duel.ent": content})
    maps_dir = tmp_path / "maps"
    maps_dir.mkdir()
    (maps_dir / "duel.ent").write_bytes(content)

    index = Pk3GeometryIndex.scan(tmp_path)
    resolution = index.resolve_asset("duel.ent", "ent")

    assert resolution.status == "resolved"
    assert resolution.selected is not None
    assert len(resolution.providers) == 2
    assert index.read_provider(resolution.selected) == content


def test_read_provider_rejects_loose_entity_override_changed_after_scan(tmp_path):
    maps_dir = tmp_path / "maps"
    maps_dir.mkdir()
    path = maps_dir / "duel.ent"
    path.write_bytes(b"original")
    index = Pk3GeometryIndex.scan(tmp_path)
    selected = index.resolve_asset("duel", "ent").selected
    assert selected is not None

    path.write_bytes(b"changed!")
    with pytest.raises(AssetContentChangedError, match="metadata changed|content changed"):
        index.read_provider(selected)


def test_missing_played_maps_and_assets_are_explicit_in_manifest(tmp_path):
    _write_pk3(tmp_path / "one.pk3", {"maps/adlernest.bsp": b"geometry"})
    index = Pk3GeometryIndex.scan(tmp_path)

    manifest = index.manifest(["adlernest", "etl_frostbite", "radar"])

    assert manifest["maps"]["adlernest"]["status"] == "geometry"
    assert manifest["maps"]["adlernest"]["assets"]["script"]["status"] == "missing"
    assert manifest["maps"]["etl_frostbite"]["status"] == "no_geometry"
    assert manifest["maps"]["radar"]["status"] == "no_geometry"
    assert manifest["summary"]["missing_maps"] == ["etl_frostbite", "radar"]
    assert manifest["summary"]["without_geometry"] == 2


def test_assets_without_bsp_are_in_asset_inventory_but_not_w2_default(tmp_path):
    _write_pk3(tmp_path / "one.pk3", {"maps/duel_lms.script": b"lms"})
    index = Pk3GeometryIndex.scan(tmp_path)

    assert index.map_names == ()
    assert index.asset_map_names == ("duel_lms",)
    assert index.resolve("duel_lms").status == "no_geometry"
    assert index.resolve_asset("duel_lms", "script").status == "resolved"


def test_bad_pk3_is_not_silently_skipped(tmp_path):
    (tmp_path / "broken.pk3").write_bytes(b"not a zip")
    with pytest.raises(Pk3IndexError, match="cannot index PK3 archive"):
        Pk3GeometryIndex.scan(tmp_path)


def test_read_provider_returns_the_exact_hashed_non_bsp_member(tmp_path):
    content = b"chosen script bytes"
    _write_pk3(tmp_path / "one.pk3", {"maps/adlernest.script": content})
    index = Pk3GeometryIndex.scan(tmp_path)
    selected = index.resolve_asset("adlernest", "script").selected
    assert selected is not None

    assert index.read_provider(selected) == content


def test_read_provider_rejects_archive_changed_after_scan(tmp_path):
    path = tmp_path / "one.pk3"
    _write_pk3(path, {"maps/adlernest.script": b"original"})
    index = Pk3GeometryIndex.scan(tmp_path)
    selected = index.resolve_asset("adlernest", "script").selected
    assert selected is not None

    _write_pk3(path, {"maps/adlernest.script": b"changed"})
    with pytest.raises(AssetContentChangedError, match="metadata changed|content changed"):
        index.read_provider(selected)


def test_unknown_asset_kind_is_rejected(tmp_path):
    index = Pk3GeometryIndex.scan(tmp_path)
    with pytest.raises(ValueError, match="invalid map asset kind"):
        index.resolve_asset("adlernest", "arena")
