"""Worker-safe wrappers for demo scanning jobs."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, Optional


from greatshot.scanner.api import analyze_demo
from greatshot.scanner.report import build_text_report


class AnalysisCancelledError(RuntimeError):
    """Raised when an analysis job is cancelled via a threading.Event."""


def run_analysis_job(
    demo_path: str | Path,
    output_dir: str | Path,
    scanner_options: Dict[str, Any] | None = None,
    cancel_event: Optional[threading.Event] = None,
) -> Dict[str, Any]:
    """Run demo analysis, optionally checking *cancel_event* for early exit.

    When *cancel_event* is set, the function raises ``AnalysisCancelledError``
    at the next checkpoint so the caller (and its wrapping thread) can exit
    promptly instead of continuing to consume resources after an asyncio
    timeout.
    """

    def _check_cancelled() -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise AnalysisCancelledError("Analysis cancelled by timeout")

    start = perf_counter()
    demo_path = Path(demo_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    _check_cancelled()

    analysis_result = analyze_demo(demo_path, scanner_options=scanner_options)

    _check_cancelled()

    analysis_payload = analysis_result.to_dict()
    report_text = build_text_report(analysis_payload)

    _check_cancelled()

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
