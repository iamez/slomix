"""Read-only ET map geometry primitives.

The package deliberately stops at asset discovery and BSP decoding. Trace-mask
policy, dynamic entity state, and all derived metrics belong to later Spider
Web workstreams and must not be inferred here.
"""

from website.backend.map_geometry.bsp import (
    BSP_MAGIC,
    BSP_VERSION,
    BspBrush,
    BspBrushSide,
    BspFile,
    BspFormatError,
    BspLeaf,
    BspLump,
    BspModel,
    BspNode,
    BspPlane,
    BspShader,
    LumpType,
    UnsupportedBspError,
    parse_bsp,
    parse_bsp_file,
    parse_entities,
)
from website.backend.map_geometry.pk3_index import (
    BspContentChangedError,
    BspProvider,
    GeometryResolution,
    Pk3BspConflictError,
    Pk3GeometryIndex,
    Pk3IndexError,
)

__all__ = [
    "BSP_MAGIC",
    "BSP_VERSION",
    "BspBrush",
    "BspBrushSide",
    "BspContentChangedError",
    "BspFile",
    "BspFormatError",
    "BspLeaf",
    "BspLump",
    "BspModel",
    "BspNode",
    "BspPlane",
    "BspProvider",
    "BspShader",
    "GeometryResolution",
    "LumpType",
    "Pk3BspConflictError",
    "Pk3GeometryIndex",
    "Pk3IndexError",
    "UnsupportedBspError",
    "parse_bsp",
    "parse_bsp_file",
    "parse_entities",
]
