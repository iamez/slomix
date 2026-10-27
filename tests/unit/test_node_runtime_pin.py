"""Local and CI Node versions share a bounded, patched Node 22 interval."""
import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_yaml_parser_is_a_declared_development_dependency():
    requirements = (ROOT / "requirements-dev.txt").read_text().splitlines()
    assert any(re.fullmatch(r"PyYAML==\d+\.\d+\.\d+", line) for line in requirements), (
        "The workflow parser needs an explicit pinned development dependency"
    )


@pytest.mark.parametrize("directory", [Path("."), Path("website/frontend")])
def test_node_pin_satisfies_frontend_engine_floor(directory):
    pin = (ROOT / ".nvmrc").read_text().strip()
    assert re.fullmatch(r"22\.\d+\.\d+", pin), "Pin an exact supported Node 22 patch"
    manifest = json.loads((ROOT / directory / "package.json").read_text())
    lock = json.loads((ROOT / directory / "package-lock.json").read_text())
    engine = manifest["engines"]["node"]
    bounds = re.fullmatch(r">=(\d+)\.(\d+)\.(\d+) <(\d+)", engine)
    assert bounds, "Declare an inclusive patch floor and exclusive major ceiling"
    floor = tuple(map(int, bounds.groups()[:3]))
    ceiling = int(bounds.group(4))
    selected = tuple(map(int, pin.split(".")))
    assert floor == selected, "Engine floor must match the reviewed patched Node pin"
    assert floor[0] == 22 and ceiling == 23, "Keep the supported Node 22 major interval"
    assert floor <= selected < (ceiling, 0, 0), f"Node pin {pin} is outside engine {engine}"
    assert lock["packages"][""]["engines"]["node"] == engine, (
        "Manifest and lockfile must declare the same Node engine interval"
    )


@pytest.mark.parametrize("job", ["javascript", "react-frontend"])
def test_ci_node_setup_uses_the_shared_pin(job):
    workflow = yaml.safe_load((ROOT / ".github/workflows/tests.yml").read_text())
    steps = workflow["jobs"][job]["steps"]
    setup = [step for step in steps if step.get("uses", "").startswith("actions/setup-node@")]
    assert len(setup) == 1, f"Expected exactly one Node setup in {job}"
    options = setup[0]["with"]
    assert options.get("node-version-file") == ".nvmrc"
    assert "node-version" not in options, "Inline versions override the shared pin"
