"""Local and CI Node versions share one exact pin above the frontend floor."""
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


def test_node_pin_satisfies_frontend_engine_floor():
    pin = (ROOT / ".nvmrc").read_text().strip()
    assert re.fullmatch(r"22\.\d+\.\d+", pin), "Pin an exact supported Node 22 patch"
    engine = json.loads((ROOT / "website/frontend/package.json").read_text())["engines"]["node"]
    floor = re.fullmatch(r">=(\d+)\.(\d+)\.(\d+)", engine)
    assert floor, "Update this contract explicitly if the engine range changes shape"
    assert tuple(map(int, pin.split("."))) >= tuple(map(int, floor.groups())), (
        f"Node pin {pin} is below frontend engine {engine}"
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
