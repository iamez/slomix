"""Observed pause gating is capture quality, NOT an exact active-game clock.

Missing legacy headers cannot prove a pause-free round. Repeated contradictory
or unsupported declarations stay unknown, including after a later valid line.
"""

import re


def observe_capture_pauses(previous: dict | None, raw: str) -> dict:
    match = re.fullmatch(r"observed_pause_gate_v1:([01]):([01])", raw)
    current = {"status": "unknown"}
    if match:
        current = {
            "status": "declared",
            "policy": "observed_pause_gate_v1",
            "pause_observed": match[1] == "1",
            "signal_unknown": match[2] == "1",
        }
    if previous is not None and previous != current:
        return {"status": "unknown"}
    return current
