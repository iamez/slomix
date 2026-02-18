from __future__ import annotations

import json
from pathlib import Path

import greatshot.scanner.api as scanner_api


def test_analyze_demo_matches_golden_fixture(monkeypatch, tmp_path: Path):
    sample = json.loads(Path("greatshot/tests/fixtures/sample_udt_output.json").read_text(encoding="utf-8"))
    golden = json.loads(Path("greatshot/tests/fixtures/golden_analysis_v1.json").read_text(encoding="utf-8"))

    def fake_parser(**_kwargs):
        return sample

    monkeypatch.setattr(scanner_api, "run_udt_json_parser", fake_parser)

    demo_path = tmp_path / "gold.dm_84"
    header = (1).to_bytes(4, "little", signed=True) + (64).to_bytes(4, "little", signed=True)
    demo_path.write_bytes(header + (b"\x00" * 128))

    result = scanner_api.analyze_demo(demo_path).to_dict()
    # The scanner can add extra metadata/highlight details over time.
    # Keep this test focused on contract-critical fields.
    assert result["schema_version"] == golden["schema_version"]
    assert result["metadata"] == golden["metadata"]
    assert result["players"] == golden["players"]
    assert result["stats"] == golden["stats"]
    assert result["timeline"] == golden["timeline"]
    assert result["warnings"] == golden["warnings"]
    assert result["parser"] == golden["parser"]

    # Ensure current output still includes at least all golden highlight types.
    result_highlight_types = {h["type"] for h in result.get("highlights", [])}
    golden_highlight_types = {h["type"] for h in golden.get("highlights", [])}
    assert golden_highlight_types.issubset(result_highlight_types)
