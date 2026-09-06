"""The dataset register (docs/design/19 §5, slice 1) is only useful while
its references are real: page keys that exist in routes.data.json, parity
keys the SPA actually renders, dependencies that name registered datasets,
and collection toggles that gate collection where telemetry originates.
Each rule below is checked against the source it refers to, not against a
copy — and the profile endpoint's section allowlist is asserted to be the
register's, so the two cannot drift.
"""
from __future__ import annotations

import json
import pathlib
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from website.backend.routers import datasets_router
from website.backend.routers.players_profile_router import _HEAVY_SECTIONS, _PROFILE_SECTIONS
from website.backend.services.dataset_registry import (
    DATASETS,
    PROFILE_SECTIONS,
    DatasetDescriptor,
    heavy_profile_section_keys,
    profile_section_keys,
)

REPO = pathlib.Path(__file__).resolve().parents[2]
SPA = REPO / "website" / "frontend" / "src" / "app"
LUA = REPO / "proximity" / "lua" / "proximity_tracker.lua"


def _route_keys() -> set[str]:
    return {r["key"] for r in json.loads((SPA / "routes.data.json").read_text(encoding="utf-8"))}


def _parity_keys() -> set[str]:
    keys: set[str] = set()
    for path in SPA.rglob("*.tsx"):
        keys |= set(re.findall(r'parity="([a-z0-9.\-]+)"', path.read_text(encoding="utf-8")))
    return keys


def _lua_feature_names() -> set[str]:
    return set(re.findall(r'isFeatureEnabled\("([a-z_]+)"\)', LUA.read_text(encoding="utf-8")))


def _bot_env_switches() -> set[str]:
    text = (REPO / "bot" / "config.py").read_text(encoding="utf-8")
    return set(re.findall(r"_get_config\('([A-Z_]+_ENABLED)'", text))


def test_keys_are_unique():
    keys = [d.key for d in DATASETS]
    assert len(keys) == len(set(keys)), sorted(k for k in keys if keys.count(k) > 1)


@pytest.mark.parametrize("d", DATASETS, ids=lambda d: d.key)
def test_default_pages_are_real_route_keys(d: DatasetDescriptor):
    unknown = set(d.default_visible_on) - _route_keys()
    assert not unknown, f"{d.key}: pages not in routes.data.json: {sorted(unknown)}"


@pytest.mark.parametrize("d", DATASETS, ids=lambda d: d.key)
def test_dependencies_name_registered_datasets(d: DatasetDescriptor):
    known = {x.key for x in DATASETS}
    unknown = set(d.depends_on) - known
    assert not unknown, f"{d.key}: depends on unregistered {sorted(unknown)}"
    assert d.key not in d.depends_on


@pytest.mark.parametrize("d", [d for d in DATASETS if d.parity_key], ids=lambda d: d.key)
def test_parity_keys_are_rendered_by_the_spa(d: DatasetDescriptor):
    assert d.parity_key in _parity_keys(), f"{d.key}: no data-parity=\"{d.parity_key}\" in src/app"


@pytest.mark.parametrize("d", [d for d in DATASETS if d.collection_toggle], ids=lambda d: d.key)
def test_collection_toggles_gate_collection_at_the_origin(d: DatasetDescriptor):
    """A toggle is a Lua `isFeatureEnabled` section or a bot env switch —
    never a flag the web layer invented (doc 19 §5)."""
    toggle = d.collection_toggle
    assert toggle in _lua_feature_names() or toggle in _bot_env_switches(), (
        f"{d.key}: toggle {toggle!r} gates nothing at the origin"
    )
    assert d.collected_by in ("lua", "bot_parser"), f"{d.key}: a derived dataset has no collection toggle of its own"


def test_a_shown_dataset_names_at_least_one_page_and_a_hidden_one_names_none():
    for d in DATASETS:
        if d.display_toggle_default:
            assert d.default_visible_on, f"{d.key}: shown by default but on no page"
        else:
            assert not d.default_visible_on, f"{d.key}: hidden by default yet listed on a page"


def test_the_profile_endpoint_allowlist_is_the_register():
    assert profile_section_keys() == _PROFILE_SECTIONS
    assert len(PROFILE_SECTIONS) == 14


def test_heavy_sections_come_from_the_measured_cost():
    assert heavy_profile_section_keys() == _HEAVY_SECTIONS == {"aim", "advanced"}
    costs = {d.key: d.cost_ms_cold for d in PROFILE_SECTIONS if d.cost_ms_cold}
    assert costs == {"aim": 16_887, "advanced": 11_077}


def test_the_endpoint_publishes_the_register_typed():
    app = FastAPI()
    app.include_router(datasets_router.router, prefix="/api")
    client = TestClient(app)
    r = client.get("/api/datasets")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == len(DATASETS) >= 30
    assert {d["key"] for d in body["datasets"]} == {d.key for d in DATASETS}
    schema = app.openapi()
    assert "DatasetDescriptor" in schema["components"]["schemas"]


def test_control_an_unknown_page_key_is_caught():
    """The rule has to be able to fail: a dataset on a page that does not
    exist must not pass the route-key check."""
    bogus = DatasetDescriptor(key="x", label="x", collected_by="derived", collection_toggle=None,
                              display_toggle_default=True, user_overridable=True,
                              default_visible_on=["no-such-page"], depends_on=[], endpoint=None,
                              cost_ms_cold=None, parity_key=None)
    assert set(bogus.default_visible_on) - _route_keys() == {"no-such-page"}
