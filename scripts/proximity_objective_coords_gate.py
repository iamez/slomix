# Shim: proximity_objective_coords_gate was consolidated into tools/slomix_proximity.py.
# This module re-exports the public API from the archived original so that
# tests and other callers continue to work without modification.
from scripts.archive.proximity_objective_coords_gate import *  # noqa: F401, F403
from scripts.archive.proximity_objective_coords_gate import (
    evaluate_gate,
    parse_top_maps_arg,
)

__all__ = [
    "evaluate_gate",
    "parse_top_maps_arg",
]
