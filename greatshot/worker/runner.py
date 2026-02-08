"""Worker-safe wrappers for demo scanning jobs."""

from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter
from typing import Any, Dict

from greatshot.scanner.api import analyze_demo
from greatshot.scanner.report import build_text_report


def run_analysis_job(
    demo_path: str | Path,
    output_dir: str | Path,
    scanner_options: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    start = perf_counter()
    demo_path = Path(demo_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    analysis_result = analyze_demo(demo_path, scanner_options=scanner_options)
    analysis_payload = analysis_result.to_dict()
    report_text = build_text_report(analysis_payload)

    json_path = output_dir / "analysis.json"
    txt_path = output_dir / "report.txt"

    json_path.write_text(
        json.dumps(analysis_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    txt_path.write_text(report_text, encoding="utf-8")

    elapsed_ms = int((perf_counter() - start) * 1000)
    return {
        "analysis": analysis_payload,
        "analysis_json_path": str(json_path),
        "report_txt_path": str(txt_path),
        "elapsed_ms": elapsed_ms,
    }
