"""What `scripts/export_map_geometry.py` decides to call a floor.

⚠️ The script had no tests. It is not a report — it decides which bytes go into
the repository and what the renderer believes the ground is, and one of its
rules was wrong in a way that would have drawn every floor in the game as
shattered glass.

The BSP stand-ins here are deliberately minimal. The export only ever reads
attributes, so a handful of small objects exercise the real code paths without
a 40 MB pk3, and they can express the exact shapes a real file would take
hours to find — a quad whose stored vertex order is a bow-tie, a sky surface,
a sliver.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.export_map_geometry import (  # noqa: E402
    FLOOR_NORMAL_Z,
    MIN_TRIANGLE_AREA,
    SURF_NODRAW,
    SURF_SKY,
    bounds_of,
    floor_triangles,
    to_indexed_mesh,
    triangle_area_xy,
)
from website.backend.map_geometry import SurfaceType  # noqa: E402

UP = (0.0, 0.0, 1.0)
WALL = (1.0, 0.0, 0.0)


@dataclass
class FakeVertex:
    position: tuple
    normal: tuple = UP


@dataclass
class FakeShader:
    surface_flags: int = 0
    content_flags: int = 1
    name: str = "textures/test/floor"


@dataclass
class FakeSurface:
    first_vertex: int
    num_vertices: int
    first_index: int
    num_indexes: int
    shader_index: int = 0
    surface_type: SurfaceType = SurfaceType.PLANAR
    patch_width: int = 0
    patch_height: int = 0


@dataclass
class FakeModel:
    first_surface: int
    num_surfaces: int


@dataclass
class FakeBsp:
    surfaces: list
    draw_vertices: list
    draw_indexes: list
    shaders: list = field(default_factory=lambda: [FakeShader()])
    models: list = field(default_factory=list)
    source: str = "test.bsp"

    def __post_init__(self):
        if not self.models:
            self.models = [FakeModel(0, len(self.surfaces))]


def quad_bsp(size: float = 56.0, normal=UP, flags: int = 0) -> FakeBsp:
    """One quad, stored the way a real BSP stores it.

    ⛔ THE VERTEX ORDER IS A BOW-TIE ON PURPOSE, because that is what the file
    actually contains. Corners 0,1,2,3 walked as a ring cross over themselves
    and enclose no area; the two triangles in `draw_indexes` are the real
    surface. Reading the stored order as a polygon is the bug this pins.
    """
    corners = [(0.0, 0.0, 0.0), (size, 0.0, 0.0), (0.0, size, 0.0), (size, size, 0.0)]
    return FakeBsp(
        surfaces=[FakeSurface(0, 4, 0, 6)],
        draw_vertices=[FakeVertex(c, normal) for c in corners],
        draw_indexes=[0, 1, 2, 1, 3, 2],
        shaders=[FakeShader(surface_flags=flags)],
    )


class TestTheQuadIsReadThroughItsIndexes:
    def test_the_stored_vertex_order_encloses_nothing(self):
        """The premise. If this ever stops being true the rest is moot."""
        corners = [v.position for v in quad_bsp().draw_vertices]
        ring = 0.0
        for i in range(len(corners)):
            x1, y1, _ = corners[i]
            x2, y2, _ = corners[(i + 1) % len(corners)]
            ring += x1 * y2 - x2 * y1
        assert abs(ring) / 2 == 0.0, "the fixture is no longer a bow-tie"

    def test_the_export_recovers_the_real_area(self):
        triangles, _ = floor_triangles(quad_bsp(size=56.0))
        assert len(triangles) == 2
        assert sum(triangle_area_xy(t) for t in triangles) == pytest.approx(56.0 * 56.0)

    def test_a_surface_with_no_indexes_is_rejected_not_guessed(self):
        bsp = quad_bsp()
        bsp.surfaces[0].num_indexes = 0
        triangles, rejected = floor_triangles(bsp)
        assert triangles == []
        assert rejected["degenerate"] == 1


class TestWhatCountsAsFloor:
    def test_a_wall_is_not_floor(self):
        triangles, rejected = floor_triangles(quad_bsp(normal=WALL))
        assert triangles == []
        assert rejected["not_floor"] == 1

    @pytest.mark.parametrize("flag,name", [(SURF_SKY, "sky"), (SURF_NODRAW, "nodraw")])
    def test_undrawn_surfaces_are_not_floor(self, flag, name):
        triangles, rejected = floor_triangles(quad_bsp(flags=flag))
        assert triangles == [], name
        assert rejected["shader"] == 1

    def test_a_ramp_at_the_threshold_is_kept(self):
        """The constant decides what "floor" means, so both sides of it are
        pinned — otherwise raising it later would silently delete ramps."""
        z = FLOOR_NORMAL_Z + 0.01
        rest = (1.0 - z * z) ** 0.5
        triangles, _ = floor_triangles(quad_bsp(normal=(rest, 0.0, z)))
        assert len(triangles) == 2

    def test_a_slope_past_the_threshold_is_dropped(self):
        z = FLOOR_NORMAL_Z - 0.01
        rest = (1.0 - z * z) ** 0.5
        triangles, _ = floor_triangles(quad_bsp(normal=(rest, 0.0, z)))
        assert triangles == []

    def test_a_sliver_is_dropped_and_counted(self):
        tiny = MIN_TRIANGLE_AREA ** 0.5 / 4
        triangles, rejected = floor_triangles(quad_bsp(size=tiny))
        assert triangles == []
        assert rejected["sliver"] == 2

    def test_only_the_world_model_is_exported(self):
        """⛔ Models 1..n are doors and lifts at their editor position. Including
        them put ground where there is none: etl_sp_delivery's standing height
        scattered to a spread of 154 units, against 11 with the world alone.
        """
        bsp = quad_bsp()
        mover = FakeSurface(0, 4, 0, 6)
        bsp.surfaces.append(mover)
        bsp.models = [FakeModel(0, 1)]           # the world is the first surface only
        triangles, _ = floor_triangles(bsp)
        assert len(triangles) == 2, "the brush entity's surface leaked in"


class TestIndexedMesh:
    def test_shared_corners_are_stored_once(self):
        triangles, _ = floor_triangles(quad_bsp())
        mesh = to_indexed_mesh(triangles)
        assert len(mesh["vertices"]) // 3 == 4, "the quad has four distinct corners"
        assert len(mesh["indexes"]) == 6

    def test_the_mesh_still_describes_the_same_triangles(self):
        triangles, _ = floor_triangles(quad_bsp(size=56.0))
        mesh = to_indexed_mesh(triangles)
        rebuilt = [
            [
                mesh["vertices"][mesh["indexes"][i + k] * 3:
                                 mesh["indexes"][i + k] * 3 + 3]
                for k in range(3)
            ]
            for i in range(0, len(mesh["indexes"]), 3)
        ]
        assert sum(triangle_area_xy(t) for t in rebuilt) == pytest.approx(56.0 * 56.0)

    def test_an_empty_mesh_is_empty_rather_than_malformed(self):
        assert to_indexed_mesh([]) == {"vertices": [], "indexes": []}


class TestBounds:
    def test_bounds_span_every_axis(self):
        triangles, _ = floor_triangles(quad_bsp(size=56.0))
        assert bounds_of(triangles) == {"min": [0, 0, 0], "max": [56, 56, 0]}

    def test_no_triangles_means_no_bounds_rather_than_a_point_at_the_origin(self):
        """⛔ Returning zeroes would put an empty map at the world origin and
        the renderer would scale the whole canvas to a single point."""
        assert bounds_of([]) is None
