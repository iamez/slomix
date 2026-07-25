"""Formula registry contract (Codex MODEL-01).

The registry is only trustworthy if a version it publishes cannot drift
from the module that owns the formula. Entries backed by an owner constant
are imported; the rest are hand-typed and are allowed here only while they
are explicitly listed, so adding a new live formula without a constant is a
visible decision rather than an accident.
"""
from __future__ import annotations

import pytest

from website.backend.services.formula_registry import REGISTRY_VERSION, get_registry

# Live formulas whose version is imported from the owning module.
# name -> (module path, attribute)
OWNED = {
    "kis": ("website.backend.services.storytelling.kis", "FORMULA_VERSION"),
    "pwc": ("website.backend.services.storytelling.win_contribution", "FORMULA_VERSION"),
    "s_effort": ("website.backend.services.s_effort_service", "FORMULA_VERSION"),
    "adjusted_lifetime": ("website.backend.services.s_effort_service", "FORMULA_VERSION"),
    "situational_skill_rating": ("website.backend.services.ssr_service", "FORMULA_VERSION"),
    "ois": ("website.backend.services.storytelling.ois", "FORMULA_VERSION"),
    "prox_score_web": ("website.backend.services.prox_scoring", "FORMULA_VERSION"),
    "power_rating": ("website.backend.routers.proximity_scoring", "POWER_FORMULA_VERSION"),
}

# Live entries that still carry a hand-typed version. Each one is a known
# drift path; shrinking this list is the point of MODEL-01.
STATIC_ALLOWED = {
    "et_rating", "et_performance_v3", "box_scoring", "krogt", "prox_score_bot",
    "good_night_index", "form_index", "prediction_engine", "player_radar",
}


def _by_name() -> dict:
    return {e["name"]: e for e in get_registry()}


def test_registry_version_is_declared():
    assert REGISTRY_VERSION


@pytest.mark.parametrize("name,ref", sorted(OWNED.items()))
def test_owned_versions_are_imported_not_copied(name, ref):
    """The registry value must EQUAL the owning module's constant, so a bump
    in the formula cannot leave the registry behind."""
    import importlib

    entry = _by_name().get(name)
    assert entry, f"{name} missing from the registry"
    module_path, attr = ref
    owned = getattr(importlib.import_module(module_path), attr)
    assert entry["version"] == owned, (
        f"{name}: registry says {entry['version']!r}, owner says {owned!r}"
    )


def test_every_entry_has_the_required_fields():
    for entry in get_registry():
        for field in ("name", "version", "status", "module", "surface", "summary"):
            assert entry.get(field), f"{entry.get('name')}: missing {field}"


def test_no_new_live_formula_without_an_owner_constant():
    """A live formula that is neither owned nor explicitly grandfathered is
    an unversioned surface — exactly what let power_rating ship two broken
    axes unnoticed."""
    live = {e["name"] for e in get_registry() if e["status"] == "live"}
    unaccounted = live - set(OWNED) - STATIC_ALLOWED
    assert not unaccounted, (
        f"live formulas with neither an imported version nor an explicit "
        f"static allowance: {sorted(unaccounted)}"
    )


def test_declared_modules_exist():
    from pathlib import Path

    for entry in get_registry():
        path = entry["module"].split(" ")[0]  # some carry a trailing note
        assert Path(path).exists(), f"{entry['name']}: {path} does not exist"
