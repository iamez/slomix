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
    BspDrawVertex,
    BspFile,
    BspFormatError,
    BspLeaf,
    BspLump,
    BspModel,
    BspNode,
    BspPlane,
    BspShader,
    BspSurface,
    LumpType,
    SurfaceType,
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
    "BspDrawVertex",
    "BspFile",
    "BspFormatError",
    "BspLeaf",
    "BspLump",
    "BspModel",
    "BspNode",
    "BspPlane",
    "BspProvider",
    "BspShader",
    "BspSurface",
    "GeometryResolution",
    "LumpType",
    "Pk3BspConflictError",
    "Pk3GeometryIndex",
    "Pk3IndexError",
    "SurfaceType",
    "UnsupportedBspError",
    "parse_bsp",
    "parse_bsp_file",
    "parse_entities",
]
