"""Objective-zone catalog invariants (Codex #552).

The catalog is generated but hand-corrected, so the cheap invariants that
would have caught earlier mistakes are pinned here:

* declared metadata must match the actual aggregate;
* every map the runtime loader can resolve must exist in the exported JSON;
* the generation template must know about every exported map, or the next
  documented extractor run silently drops it;
* previously-present maps must never disappear (regenerating the file once
  dropped `etl_frostbite`, which has 227 played rounds, because that key
  exists only in the committed file and not in the coords source).
"""
from __future__ import annotations

import json
from pathlib import Path

ZONES = Path("website/assets/maps/proximity/objective_zones.json")
SOURCE = Path("proximity/objective_coords_from_etmain.json")
TEMPLATE = Path("proximity/objective_coords_template.json")

# Maps that must never vanish from the catalog again. Not a full list — a
# regression guard for the ones with real play history.
PROTECTED = ("etl_frostbite", "supply", "te_escape2", "etl_adlernest",
             "sw_goldrush_te", "etl_sp_delivery", "et_brewdog")


def _zones() -> dict:
    return json.loads(ZONES.read_text(encoding="utf-8"))


def _canonical(maps: dict) -> dict:
    """Only the lowercase keys: the exporter writes each entry twice (raw
    name and normalized) pointing at one object."""
    return {k: v for k, v in maps.items() if k == k.lower()}


def test_declared_metadata_matches_the_actual_catalog():
    doc = _zones()
    maps = _canonical(doc["maps"])
    assert doc["meta"]["map_count"] == len(maps)
    assert doc["meta"]["objective_count"] == sum(
        len(v["objectives"]) for v in maps.values()
    )


def test_metadata_source_is_repo_relative():
    """An absolute path here is environment-specific and breaks
    reproducibility for other developers and CI."""
    src = _zones()["meta"]["source"]
    assert not src.startswith("/"), src
    assert src == "proximity/objective_coords_from_etmain.json"


def test_protected_maps_are_present_with_objectives():
    maps = _canonical(_zones()["maps"])
    for name in PROTECTED:
        assert name in maps, f"{name} vanished from the objective catalog"
        assert maps[name]["objectives"], f"{name} has no objectives"


def test_every_exported_map_is_in_the_extractor_template():
    """The extractor filters on the template by default, so a map missing
    from it is dropped by the next documented run."""
    tmpl = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    tmpl_maps = set(tmpl.get("maps", tmpl))
    src_maps = set(json.loads(SOURCE.read_text(encoding="utf-8"))["maps"])
    missing = sorted(src_maps - tmpl_maps)
    assert not missing, f"maps absent from the extractor template: {missing}"


def test_every_objective_has_coordinates_and_a_radius():
    for name, entry in _canonical(_zones()["maps"]).items():
        for obj in entry["objectives"]:
            for key in ("x", "y", "z", "radius"):
                assert obj.get(key) is not None, f"{name}/{obj.get('id')}: {key}"
            assert obj["radius"] > 0


def test_runtime_loader_resolves_every_exported_map():
    """The KIS objective-area lookup is `_load_zones().get(map_name.lower())`
    with no alias resolution, so an exported key that the loader cannot
    return is dead weight."""
    from website.backend.services.objective_pressure_service import _load_zones

    loaded = _load_zones()
    for name in _canonical(_zones()["maps"]):
        assert name in loaded, f"{name} exported but not resolvable at runtime"


def test_tracked_json_files_end_with_a_newline():
    for path in (ZONES, SOURCE, TEMPLATE):
        assert path.read_bytes().endswith(b"\n"), f"{path} missing EOF newline"
