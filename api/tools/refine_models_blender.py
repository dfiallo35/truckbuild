"""Rebuilds the placeholder build models in Blender as realistic trucks.

``make_placeholder_models.py`` writes flat-shaded triangle soup straight to a GLB: every box is a
razor-edged cuboid and every cylinder a 12-to-22-sided prism. That was the right trade while the
only question was whether the ingest chain worked, but the build view is the configurator's whole
centrepiece, and a wireframe study is not what a visitor is being asked to price.

The layout is not re-authored. The part list is read back out of ``make_placeholder_models`` by
standing a recording double in for ``glb_writer``, so every node name, position, dimension and
material still comes from the file that already agrees with ``seed/catalog.yaml``'s camera framing
and every option's ``model_effect``. Nothing here can move a part out of frame or invent a node
name the sync would reject. What changes is what occupies each of those volumes:

- **Nothing has a zero-radius edge.** Every crease is bevelled and every surface is smooth-shaded
  by angle, which is what lets a highlight run along a body line at all.
- **Round things are round.** Segment counts scale with radius instead of being pinned low.
- **Wheels are wheels.** A lathed tyre with rounded shoulders and a moulded, staggered tread block
  pattern, on a dished rim with spokes, lug nuts, a centre cap and a brake disc behind it. They sit
  nearest the camera at every framing the catalog pins, so they are where a capped 20-gon reads
  worst.
- **Bodywork is detailed where a truck is detailed** -- arched fenders over every wheel, mud flaps,
  mirrors on stalks, a roof fairing and sun visor over the cab, slatted grilles, bezelled lamps,
  and recessed panel seams that give the flat sides a sense of scale.
- **The chassis is a chassis** -- C-section frame rails, leaf-spring packs at each axle, a
  driveshaft between them.

The extra detail is merged into the *same* node it belongs to, never added as a node of its own, so
an option's ``model_effect`` keeps hiding and showing exactly what it always did.

Deliberately *not* Draco-compressed: ``web/src/lib/viewer/scene.ts`` constructs a bare
``GLTFLoader`` with no ``DRACOLoader`` attached, so a compressed GLB would fail to parse in the one
place it has to load.

Run headless::

    blender -b -P tools/refine_models_blender.py -- seed/models

or through the Blender MCP server, which cannot run in background mode, by ``exec``-ing this file
from ``execute_blender_code``.

**A re-run always produces a new content hash.** The geometry is deterministic, but Blender's glTF
exporter is not byte-reproducible -- two consecutive runs of this file give GLBs of identical size
and different bytes, with or without ``PYTHONHASHSEED`` pinned. So unlike
``make_placeholder_models``, rebuilding here and re-syncing always uploads rather than reporting
``unchanged``. Rebuild when the model changed, not to check whether it did.

See ``.claude/skills/model-ingest`` for where this sits in the ingest chain.
"""

from __future__ import annotations

import contextlib
import math
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path

import bmesh
import bpy
import mathutils

TOOLS_DIR = Path(__file__).resolve().parent
PLATFORMS = ("bristlecone", "ironwood", "sentinel")

# Faces meeting at more than this stay a crease; everything shallower is shaded smooth across.
SHARP_ANGLE = math.radians(33.0)
BEVEL_FRACTION = 0.10  # of a part's smallest dimension
BEVEL_MIN, BEVEL_MAX = 0.004, 0.045

# Materials the detailing needs that the placeholder generator never had a use for.
EXTRA_MATERIALS = {
    "panel_seam": {"name": "panel_seam", "color": "#2b2e33", "metallic": 0.4, "roughness": 0.6},
    "chrome": {"name": "chrome", "color": "#d7dbe0", "metallic": 1.0, "roughness": 0.12},
    "rubber_black": {
        "name": "rubber_black",
        "color": "#17181a",
        "metallic": 0.0,
        "roughness": 0.92,
    },
    "brake_disc": {"name": "brake_disc", "color": "#5c5f63", "metallic": 0.9, "roughness": 0.42},
}


# ------------------------------------------------------------------------------------------
# Reading the part list back out of the placeholder generator.
# ------------------------------------------------------------------------------------------


@dataclass
class _Geometry:
    parts: list = field(default_factory=list)

    def extend(self, other: _Geometry) -> None:
        self.parts.extend(other.parts)


def _spec_box(center, size):
    return _Geometry([{"kind": "box", "center": list(center), "size": list(size)}])


def _spec_cylinder(center, radius, length, axis="z", segments=20):
    return _Geometry(
        [
            {
                "kind": "cylinder",
                "center": list(center),
                "radius": radius,
                "length": length,
                "axis": axis,
            }
        ]
    )


class _SpecGlb:
    """Stands in for ``glb_writer.Glb``, recording instead of serialising."""

    def __init__(self) -> None:
        self.materials: dict[str, dict] = {}
        self.nodes: list[dict] = []

    def material(self, name, color, metallic=0.1, roughness=0.7):
        self.materials.setdefault(
            name, {"name": name, "color": color, "metallic": metallic, "roughness": roughness}
        )
        return name  # the "index" is the name; only _SpecGlb.node ever reads it

    def node(self, name, parts):
        self.nodes.append(
            {
                "name": name,
                "parts": [{**p, "material": m} for geometry, m in parts for p in geometry.parts],
            }
        )


def read_part_specs() -> dict[str, _SpecGlb]:
    double = types.ModuleType("glb_writer")
    double.Geometry, double.Glb = _Geometry, _SpecGlb
    double.box, double.cylinder = _spec_box, _spec_cylinder
    sys.modules["glb_writer"] = double
    sys.path.insert(0, str(TOOLS_DIR))

    import make_placeholder_models as generator

    return {slug: getattr(generator, slug)() for slug in PLATFORMS}


# ------------------------------------------------------------------------------------------
# Coordinates. The specs are authored in glTF's frame (Y up, +X forward); Blender is Z up, and
# its exporter converts back on the way out, so everything is built pre-converted.
# ------------------------------------------------------------------------------------------


def to_blender(point) -> tuple[float, float, float]:
    x, y, z = point
    return (x, -z, y)


AXIS_ROTATION = {
    "y": None,  # glTF +Y is Blender +Z, which is how bmesh builds a cylinder already
    "x": ("Y", math.radians(90)),
    "z": ("X", math.radians(90)),
}


def segments_for(radius: float) -> int:
    if radius >= 0.45:
        return 56
    if radius >= 0.20:
        return 36
    if radius >= 0.09:
        return 24
    return 16


# ------------------------------------------------------------------------------------------
# Primitives. Each returns (vertices, faces) already in Blender world coordinates, so a node is
# a plain concatenation and no bpy.ops -- which need a context this may not have -- is involved.
# ------------------------------------------------------------------------------------------


def _drain(bm) -> tuple[list, list]:
    bm.verts.index_update()
    vertices = [tuple(v.co) for v in bm.verts]
    faces = [tuple(v.index for v in f.verts) for f in bm.faces]
    bm.free()
    return vertices, faces


def _bevel(bm, offset: float, segments: int) -> None:
    """Round every crease. Edges already shallow are left alone -- bevelling the 56 length-wise
    edges of a cylinder would quadruple its triangle count and change nothing on screen."""
    creases = [
        e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > math.radians(20)
    ]
    if not creases or offset <= 0:
        return
    bmesh.ops.bevel(
        bm,
        geom=creases,
        offset=offset,
        offset_type="OFFSET",
        segments=segments,
        profile=0.5,
        affect="EDGES",
        clamp_overlap=True,
        miter_outer="SHARP",
    )


def _bevel_width(smallest: float) -> float:
    return max(BEVEL_MIN, min(BEVEL_MAX, smallest * BEVEL_FRACTION))


def _finish(bm, axis: str | None, center, rotate_first=None) -> tuple[list, list]:
    """Rotate a Z-built solid onto ``axis``, move it to ``center``, and hand back plain lists."""
    if rotate_first is not None:
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=rotate_first)
    rotation = AXIS_ROTATION[axis] if axis else None
    if rotation:
        which, angle = rotation
        bmesh.ops.rotate(
            bm,
            verts=bm.verts,
            cent=(0, 0, 0),
            matrix=mathutils.Matrix.Rotation(angle, 3, which),
        )
    bmesh.ops.translate(bm, vec=to_blender(center), verts=bm.verts)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return _drain(bm)


def build_box(center, size, bevel_segments: int = 3) -> tuple[list, list]:
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    # to_blender negates its Z argument, and a negative scale factor flips the winding; a size is
    # symmetric about its centre, so only the magnitudes matter.
    sx, sy, sz = (abs(c) for c in to_blender(size))
    bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=bm.verts)
    bmesh.ops.translate(bm, vec=to_blender(center), verts=bm.verts)
    _bevel(bm, _bevel_width(min(sx, sy, sz)), bevel_segments)
    return _drain(bm)


def build_cylinder(center, radius, length, axis, segments=None) -> tuple[list, list]:
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm,
        cap_ends=True,
        cap_tris=False,
        segments=segments or segments_for(radius),
        radius1=radius,
        radius2=radius,
        depth=length,
    )
    _bevel(bm, _bevel_width(min(radius, length) * 0.6), 2)
    return _finish(bm, axis, center)


def _spin(profile, segments: int, closed: bool, arc: float = math.tau, start: float = 0.0):
    """Lathe a (radius, axial) polyline around Z. ``closed`` makes the profile a solid section."""
    bm = bmesh.new()
    chain = [bm.verts.new((r, 0.0, a)) for r, a in profile]
    pairs = list(zip(chain, chain[1:], strict=False)) + ([(chain[-1], chain[0])] if closed else [])
    for first, second in pairs:
        bm.edges.new((first, second))
    if start:
        bmesh.ops.rotate(
            bm, verts=bm.verts, cent=(0, 0, 0), matrix=mathutils.Matrix.Rotation(start, 3, "Z")
        )
    bmesh.ops.spin(
        bm,
        geom=list(bm.verts) + list(bm.edges),
        cent=(0, 0, 0),
        axis=(0, 0, 1),
        dvec=(0, 0, 0),
        angle=arc,
        steps=segments,
        use_merge=False,
        use_duplicate=False,
    )
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    boundary = [e for e in bm.edges if len(e.link_faces) == 1]
    if boundary:
        bmesh.ops.holes_fill(bm, edges=boundary, sides=0)
    return bm


def _add(bm, vertices, faces) -> None:
    """Append loose geometry into ``bm``. Parts never weld, which is what keeps the sharp-edge
    pass from creasing across the seam between two touching parts."""
    added = [bm.verts.new(v) for v in vertices]
    bm.verts.ensure_lookup_table()
    for face in faces:
        # A duplicate face from a coincident primitive; the first one wins.
        with contextlib.suppress(ValueError):
            bm.faces.new(tuple(added[i] for i in face))


def build_tyre(center, radius, width, axis, chunky: bool) -> tuple[list, list]:
    """A lathed tyre with rounded shoulders and moulded tread, in place of a capped prism."""
    half = width / 2
    bead = radius * 0.66
    shoulder = radius * (0.94 if chunky else 0.965)
    profile = [
        (bead, -half),
        (shoulder, -half),
        (radius * 0.995, -half * 0.68),
        (radius, -half * 0.38),
        (radius, half * 0.38),
        (radius * 0.995, half * 0.68),
        (shoulder, half),
        (bead, half),
    ]
    bm = _spin(profile, 56 if radius >= 0.4 else 44, closed=False)

    lug_count = 16 if chunky else 24
    depth = radius * (0.055 if chunky else 0.016)
    lug_width = width * (0.34 if chunky else 0.26)
    span = math.tau / lug_count * (0.55 if chunky else 0.45)
    for index in range(lug_count):
        # Staggered inboard/outboard, the way a real block pattern is cut.
        offset = (half - lug_width) * (0.55 if index % 2 else -0.55)
        lug = bmesh.new()
        bmesh.ops.create_cube(lug, size=1.0)
        bmesh.ops.scale(lug, vec=(depth * 2, radius * span * 2, lug_width), verts=lug.verts)
        bmesh.ops.translate(lug, vec=(radius, 0.0, offset), verts=lug.verts)
        _bevel(lug, min(depth, lug_width) * 0.22, 1)
        bmesh.ops.rotate(
            lug,
            verts=lug.verts,
            cent=(0, 0, 0),
            matrix=mathutils.Matrix.Rotation(math.tau * index / lug_count, 3, "Z"),
        )
        _add(bm, *_drain(lug))
    return _finish(bm, axis, center)


def build_rim(center, radius, width, axis, outboard: float) -> tuple[list, list]:
    """Rim barrel, spokes, lug nuts and centre cap -- with the gaps between the spokes left open.

    An earlier version lathed a solid dish, which filled the wheel with one flat disc of one
    colour: the spokes were there and invisible, because what makes a wheel read is the dark
    holes *between* them. ``road_wheel`` puts a dark plate behind this, so those gaps have
    something to be a gap onto.

    ``outboard`` is +1 or -1 along the wheel's own axis, so the face points out of the truck on
    both sides rather than being mirrored inward on one of them.
    """
    half = width / 2 * outboard
    # A closed section, so the lathe makes a ring rather than a filled plate.
    bm = _spin(
        [(radius, half), (radius * 0.84, half * 0.86), (radius * 0.84, -half), (radius, -half)],
        36,
        closed=True,
    )

    spoke_count = 5
    for index in range(spoke_count):
        spoke = bmesh.new()
        bmesh.ops.create_cube(spoke, size=1.0)
        bmesh.ops.scale(
            spoke, vec=(radius * 0.80, radius * 0.32, abs(half) * 0.40), verts=spoke.verts
        )
        bmesh.ops.translate(spoke, vec=(radius * 0.53, 0.0, half * 0.80), verts=spoke.verts)
        _bevel(spoke, radius * 0.035, 2)
        bmesh.ops.rotate(
            spoke,
            verts=spoke.verts,
            cent=(0, 0, 0),
            matrix=mathutils.Matrix.Rotation(math.tau * index / spoke_count, 3, "Z"),
        )
        _add(bm, *_drain(spoke))

    hub = bmesh.new()
    bmesh.ops.create_cone(
        hub,
        cap_ends=True,
        cap_tris=False,
        segments=24,
        radius1=radius * 0.34,
        radius2=radius * 0.34,
        depth=abs(half) * 1.2,
    )
    bmesh.ops.translate(hub, vec=(0.0, 0.0, half * 0.78), verts=hub.verts)
    _bevel(hub, radius * 0.02, 2)
    _add(bm, *_drain(hub))

    for index in range(6):
        angle = math.tau * index / 6
        nut = bmesh.new()
        bmesh.ops.create_cone(
            nut,
            cap_ends=True,
            cap_tris=False,
            segments=6,
            radius1=radius * 0.062,
            radius2=radius * 0.062,
            depth=abs(half) * 0.28,
        )
        bmesh.ops.translate(
            nut,
            vec=(radius * 0.23 * math.cos(angle), radius * 0.23 * math.sin(angle), half * 1.02),
            verts=nut.verts,
        )
        _add(bm, *_drain(nut))

    cap = bmesh.new()
    bmesh.ops.create_cone(
        cap,
        cap_ends=True,
        cap_tris=False,
        segments=20,
        radius1=radius * 0.15,
        radius2=radius * 0.12,
        depth=abs(half) * 0.4,
    )
    bmesh.ops.translate(cap, vec=(0.0, 0.0, half * 1.12), verts=cap.verts)
    _bevel(cap, radius * 0.012, 2)
    _add(bm, *_drain(cap))
    return _finish(bm, axis, center)


def build_disc(center, radius, width, axis, outboard: float) -> tuple[list, list]:
    """The brake disc and caliper that sit behind a rim once you can see between the spokes."""
    inboard = -width / 2 * outboard
    bm = _spin(
        [
            (radius * 0.34, inboard * 0.30),
            (radius * 0.90, inboard * 0.30),
            (radius * 0.90, inboard * 0.62),
            (radius * 0.34, inboard * 0.62),
        ],
        32,
        closed=True,
    )
    caliper = bmesh.new()
    bmesh.ops.create_cube(caliper, size=1.0)
    bmesh.ops.scale(
        caliper, vec=(radius * 0.34, radius * 0.52, abs(inboard) * 1.05), verts=caliper.verts
    )
    bmesh.ops.translate(caliper, vec=(-radius * 0.72, 0.0, inboard * 0.46), verts=caliper.verts)
    _bevel(caliper, radius * 0.03, 2)
    _add(bm, *_drain(caliper))
    return _finish(bm, axis, center)


def build_arch(center, radius, width, axis, forward_lean: float = 0.0) -> tuple[list, list]:
    """A fender arched over a wheel: a rectangular section lathed through the top half-turn."""
    half = width / 2
    inner, outer = radius * 1.10, radius * 1.19
    bm = _spin(
        [(inner, -half), (outer, -half * 1.04), (outer, half * 1.04), (inner, half)],
        26,
        closed=True,
        arc=math.radians(196),
        start=math.radians(-8) + forward_lean,
    )
    return _finish(bm, axis, center)


def build_extrusion(profile_xy, z_center: float, width: float) -> tuple[list, list]:
    """A side-profile polygon (glTF X/Y) given thickness along glTF Z -- fairings, flaps, wedges."""
    bm = bmesh.new()
    half = width / 2
    verts = [bm.verts.new(to_blender((x, y, z_center - half))) for x, y in profile_xy]
    face = bm.faces.new(verts)
    result = bmesh.ops.extrude_face_region(bm, geom=[face])
    moved = [e for e in result["geom"] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=to_blender((0, 0, width)), verts=moved)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    _bevel(bm, _bevel_width(width * 0.5), 2)
    return _drain(bm)


# ------------------------------------------------------------------------------------------
# The accumulator every assembly writes through.
# ------------------------------------------------------------------------------------------


class Build:
    """Collects geometry per node name, and nothing else knows about Blender data-blocks."""

    def __init__(self, slug: str, materials: dict[str, dict]) -> None:
        self.slug = slug
        self.materials = dict(materials)
        self.nodes: dict[str, list] = {}

    def _node(self, suffix: str) -> list:
        return self.nodes.setdefault(f"{self.slug}_{suffix}", [])

    def _put(self, node: str, geometry, material: str) -> None:
        if material not in self.materials:
            self.materials[material] = EXTRA_MATERIALS[material]
        self._node(node).append((geometry[0], geometry[1], material))

    def box(self, node, center, size, material, bevel=3):
        self._put(node, build_box(center, size, bevel), material)

    def cyl(self, node, center, radius, length, axis, material, segments=None):
        self._put(node, build_cylinder(center, radius, length, axis, segments), material)

    def prof(self, node, profile_xy, z_center, width, material):
        """A side-profile polygon given thickness across the truck -- hoods, cabs, fenders."""
        self._put(node, build_extrusion(profile_xy, z_center, width), material)

    def tyre(self, node, center, radius, width, material, chunky=False):
        self._put(node, build_tyre(center, radius, width, "z", chunky), material)

    def rim(self, node, center, radius, width, material, outboard):
        self._put(node, build_rim(center, radius, width, "z", outboard), material)

    def disc(self, node, center, radius, width, material, outboard):
        self._put(node, build_disc(center, radius, width, "z", outboard), material)

    def arch(self, node, center, radius, width, material, lean=0.0):
        self._put(node, build_arch(center, radius, width, "z", lean), material)

    def mirrored(self, method, node, center, *args, **kwargs):
        """Run a builder at ``+z`` and again at ``-z``. Trucks are symmetric; the code should be."""
        for sign in (1, -1):
            flipped = (center[0], center[1], center[2] * sign)
            getattr(self, method)(node, flipped, *args, **kwargs)


# ------------------------------------------------------------------------------------------
# Assemblies shared by all three trucks. Every one of these is a conventional-cab American
# chassis cab -- a long hood ahead of a raked windscreen, then a separate body behind -- which
# is what `web/public/images/*/hero.jpg` shows and what the cab-over boxes never resembled.
# ------------------------------------------------------------------------------------------


def road_wheel(b: Build, node, x, z, radius, width, *, chunky=False, rim="wheel_hub"):
    outboard = 1.0 if z > 0 else -1.0
    b.tyre(node, (x, radius, z), radius, width, "tyre_lug" if chunky else "tyre_rubber", chunky)
    # The dark plate the spoke gaps are gaps onto, and the brake behind that.
    b.cyl(
        node,
        (x, radius, z + outboard * width * 0.14),
        radius * 0.655,
        width * 0.10,
        "z",
        "trim_black",
        segments=36,
    )
    b.rim(node, (x, radius, z), radius * 0.70, width * 0.94, rim, outboard)
    b.disc(node, (x, radius, z), radius * 0.62, width, "brake_disc", outboard)


def live_axle(b: Build, node, x, radius, half_track, *, spring_z=0.52):
    """Beam axle, differential, leaf-spring pack and shock absorbers."""
    b.cyl(node, (x, radius, 0.0), 0.075, half_track * 2 - 0.18, "z", "chassis_steel")
    b.cyl(node, (x, radius, 0.0), 0.21, 0.30, "z", "chassis_steel")  # differential bowl
    b.box(node, (x - 0.19, radius, 0.0), (0.16, 0.30, 0.30), "chassis_steel")  # pinion housing
    for sign in (1, -1):
        z = spring_z * sign
        for leaf in range(4):
            b.box(
                node,
                (x - leaf * 0.015, radius + 0.20 + leaf * 0.026, z),
                (1.44 - leaf * 0.22, 0.022, 0.10),
                "chassis_steel",
                bevel=1,
            )
        b.box(node, (x, radius + 0.34, z), (0.24, 0.10, 0.16), "chassis_steel")  # u-bolt plate
        b.cyl(node, (x - 0.30, radius + 0.34, z + 0.10), 0.045, 0.52, "y", "chassis_steel")


def frame_rails(b: Build, node, front_x, back_x, top_y, *, rail_z=0.44):
    """C-section rails, crossmembers, driveshaft, tank and exhaust: what is under every truck."""
    web_h = 0.20
    for sign in (1, -1):
        z = rail_z * sign
        b.box(
            node,
            ((front_x + back_x) / 2, top_y - web_h / 2, z),
            (front_x - back_x, web_h, 0.035),
            "chassis_steel",
            bevel=1,
        )
        for flange_y in (top_y - 0.012, top_y - web_h + 0.012):
            b.box(
                node,
                ((front_x + back_x) / 2, flange_y, z + sign * 0.035),
                (front_x - back_x, 0.024, 0.10),
                "chassis_steel",
                bevel=1,
            )
    for x in (front_x - 0.35, (front_x + back_x) / 2, back_x + 0.30):
        b.box(node, (x, top_y - web_h / 2, 0.0), (0.10, web_h * 0.8, rail_z * 2), "chassis_steel")
    b.box(node, (back_x + 1.05, top_y - 0.30, 0.78), (1.25, 0.46, 0.34), "aluminium")  # fuel tank
    b.cyl(node, (back_x + 1.15, top_y - 0.34, -0.72), 0.115, 1.30, "x", "chassis_steel")  # muffler
    b.cyl(node, (back_x + 0.20, top_y - 0.36, -0.72), 0.038, 1.60, "x", "chassis_steel")


def arch_cut(wheel_x: float, wheel_r: float, sill_y: float, clearance: float = 1.24):
    """The stretch of a body-side profile that arches over a wheel instead of running through it.

    Returned in increasing x, so it drops straight into the bottom edge of a side profile. The gap
    between tyre and arch is a truck's most recognisable line three-quarter on; a flat sill with a
    tyre passing through it is the one thing no amount of surface detail recovers.
    """
    radius = wheel_r * clearance
    rise = sill_y - wheel_r
    if radius <= abs(rise):
        return []
    limit = math.asin(max(-1.0, min(1.0, rise / radius)))
    steps, start, end = 14, math.pi - limit, limit
    return [
        (
            wheel_x + radius * math.cos(start + (end - start) * i / steps),
            wheel_r + radius * math.sin(start + (end - start) * i / steps),
        )
        for i in range(steps + 1)
    ]


def front_clip(
    b: Build,
    node,
    *,
    nose_x,
    cowl_x,
    roof_back_x,
    sill_y,
    belt_y,
    hood_y,
    roof_y,
    half_width,
    chrome=True,
    flare=False,
    wheel_x=0.0,
    wheel_r=0.0,
    wheel_w=0.0,
):
    """Hood, grille, bumper, lamps, fenders, greenhouse and glass -- the whole front of a truck.

    Two extrusions carry the silhouette: the lower body from the bumper back through the doors,
    and a narrower greenhouse sitting on the belt line with the windscreen raked into it. That
    profile, rather than any amount of surface detail, is what makes it read as a truck at all.
    """
    width = half_width * 2
    lower = [(roof_back_x, sill_y)]
    lower += arch_cut(wheel_x, wheel_r, sill_y) if wheel_r else []
    lower += [
        (nose_x - 0.16, sill_y),
        (nose_x, sill_y + 0.14),
        (nose_x, hood_y - 0.14),
        (nose_x - 0.18, hood_y),
        (cowl_x + 0.06, hood_y + 0.07),
        (cowl_x, belt_y),
        (roof_back_x, belt_y),
    ]
    b.prof(node, lower, 0.0, width, "body_paint")

    greenhouse = [
        (roof_back_x, belt_y),
        (cowl_x, belt_y),
        (cowl_x - 0.66, roof_y),
        (roof_back_x, roof_y),
    ]
    b.prof(node, greenhouse, 0.0, width * 0.965, "body_paint")

    # Windscreen, laid *in* the rake: inset along the rake and offset along its normal, so the
    # glass sits in an aperture instead of hovering over one.
    ax, ay = cowl_x, belt_y
    bx, by = cowl_x - 0.66, roof_y
    dx, dy = bx - ax, by - ay
    span = math.hypot(dx, dy)
    (dx, dy), (nx, ny) = (dx / span, dy / span), (dy / span, -dx / span)

    def on_rake(along, out):
        return (ax + dx * along + nx * out, ay + dy * along + ny * out)

    b.prof(
        node,
        [
            on_rake(0.07, 0.008),
            on_rake(span - 0.09, 0.008),
            on_rake(span - 0.09, -0.030),
            on_rake(0.07, -0.030),
        ],
        0.0,
        width * 0.90,
        "glass",
    )

    # Side glass and the door cuts under it.
    door_front, door_back = cowl_x - 0.14, roof_back_x + 0.10
    for sign in (1, -1):
        z = sign * half_width * 0.965
        b.box(
            node,
            ((door_front + door_back) / 2, (belt_y + roof_y) / 2 + 0.05, z),
            (door_front - door_back, roof_y - belt_y - 0.26, 0.03),
            "glass",
            bevel=1,
        )
        b.box(
            node,
            ((door_front + door_back) / 2, belt_y - 0.02, sign * half_width),
            (door_front - door_back, 0.035, 0.02),
            "panel_seam",
            bevel=1,
        )  # belt moulding
        b.box(
            node,
            (door_back + 0.02, (sill_y + belt_y) / 2, sign * half_width),
            (0.025, belt_y - sill_y, 0.02),
            "panel_seam",
            bevel=1,
        )  # door shut line
        b.box(
            node,
            (door_front - 0.30, belt_y - 0.20, sign * half_width),
            (0.20, 0.045, 0.035),
            "chrome",
            bevel=1,
        )  # door handle

    # Grille, bumper and lamps.
    trim = "chrome" if chrome else "trim_black"
    grille_y, grille_h, grille_w = hood_y - 0.34, 0.42, width * 0.52
    b.box(node, (nose_x - 0.03, grille_y, 0.0), (0.10, grille_h, grille_w), "trim_black")
    for row in range(4):
        b.box(
            node,
            (nose_x + 0.015, grille_y - grille_h / 2 + 0.07 + row * 0.095, 0.0),
            (0.05, 0.05, grille_w * 0.97),
            trim,
            bevel=1,
        )
    for edge_z in (grille_w / 2, -grille_w / 2):  # chrome surround around the opening
        b.box(node, (nose_x + 0.03, grille_y, edge_z), (0.07, grille_h + 0.08, 0.06), trim, 1)
    for edge_y in (grille_y - grille_h / 2, grille_y + grille_h / 2):
        b.box(node, (nose_x + 0.03, edge_y, 0.0), (0.07, 0.06, grille_w + 0.06), trim, 1)

    lamp_z = grille_w / 2 + 0.20
    b.mirrored(
        "box", node, (nose_x + 0.02, grille_y + 0.03, lamp_z), (0.08, 0.26, 0.32), "lamp_amber"
    )
    b.mirrored("box", node, (nose_x + 0.035, grille_y + 0.03, lamp_z), (0.05, 0.32, 0.38), trim, 1)

    b.box(node, (nose_x + 0.08, sill_y + 0.12, 0.0), (0.22, 0.30, width * 1.0), trim)
    b.box(node, (nose_x + 0.05, sill_y - 0.10, 0.0), (0.18, 0.22, width * 0.86), "trim_black")

    # West-coast mirrors: an arm off the A-pillar and a tall head, which is most of what breaks
    # a cab's silhouette side-on.
    for sign in (1, -1):
        for arm_y in (belt_y + 0.10, belt_y + 0.44):
            b.cyl(
                node,
                (cowl_x - 0.16, arm_y, sign * (half_width + 0.10)),
                0.022,
                0.22,
                "z",
                "trim_black",
            )
        b.box(
            node,
            (cowl_x - 0.17, belt_y + 0.30, sign * (half_width + 0.21)),
            (0.075, 0.46, 0.15),
            "trim_black",
        )
        b.box(
            node,
            (cowl_x - 0.19, belt_y + 0.30, sign * (half_width + 0.25)),
            (0.03, 0.40, 0.11),
            "glass",
            bevel=1,
        )

    # Front fenders arched over the steer axle, with flares where the truck wears them.
    if wheel_r:
        b.mirrored(
            "arch",
            node,
            (wheel_x, wheel_r, wheel_x * 0 + half_width * 0.86),
            wheel_r,
            wheel_w * 1.9,
            "body_paint",
        )
        if flare:
            b.mirrored(
                "arch",
                node,
                (wheel_x, wheel_r, half_width * 0.88),
                wheel_r * 1.09,
                wheel_w * 2.5,
                "trim_black",
            )

    # Cab steps, the way every one of these trucks is climbed into.
    b.mirrored(
        "box",
        node,
        ((door_front + door_back) / 2, sill_y - 0.16, half_width * 0.86),
        (door_front - door_back - 0.2, 0.05, 0.18),
        "diamond_plate" if "diamond_plate" in b.materials else "aluminium",
    )


def module_body(
    b: Build,
    node,
    *,
    front_x,
    back_x,
    floor_y,
    roof_y,
    half_width,
    material="body_paint",
    doors=0,
    windows=(),
    skirt=True,
    nose_radius=0.0,
    wheel=None,
):
    """A box body -- service body, command module, camper -- with the seams that give it scale.

    A flat 4-metre panel with nothing on it reads as a crate at any resolution. Compartment door
    cuts, a corner-post seam, a rubbed rail and a skirt are what a photograph of one of these
    actually shows.
    """
    length, height = front_x - back_x, roof_y - floor_y
    mid_x, mid_y = (front_x + back_x) / 2, (floor_y + roof_y) / 2
    # Always a profile, never a plain box: the bottom edge has to be able to arch over a wheel,
    # and the top-front corner of a service body is folded, not square.
    side = [(back_x, floor_y)]
    if wheel:
        side += arch_cut(wheel[0], wheel[1], floor_y, clearance=1.30)
    side += [(front_x, floor_y)]
    if nose_radius:
        side += [
            (front_x, roof_y - nose_radius),
            (front_x - nose_radius * 0.45, roof_y - nose_radius * 0.12),
            (front_x - nose_radius, roof_y),
        ]
    else:
        side += [(front_x, roof_y)]
    side += [(back_x, roof_y)]
    b.prof(node, side, 0.0, half_width * 2, material)

    for sign in (1, -1):
        z = sign * half_width
        b.box(node, (mid_x, roof_y - 0.03, z), (length, 0.05, 0.045), "aluminium", bevel=1)
        if not doors:
            b.box(node, (mid_x, floor_y + height * 0.42, z), (length, 0.03, 0.028), "panel_seam", 1)
        if skirt:
            b.box(node, (mid_x, floor_y - 0.02, z), (length, 0.10, 0.06), "aluminium", bevel=1)
        for index in range(doors):
            door_w = (length - 0.30) / doors
            door_h = height - 0.24
            x = front_x - 0.15 - door_w * (index + 0.5)
            for edge_x in (x - door_w / 2 + 0.03, x + door_w / 2 - 0.03):
                b.box(
                    node,
                    (edge_x, mid_y, z + sign * 0.008),
                    (0.022, door_h, 0.02),
                    "panel_seam",
                    bevel=1,
                )
            for edge_y in (mid_y - door_h / 2, mid_y + door_h / 2):
                b.box(
                    node,
                    (x, edge_y, z + sign * 0.008),
                    (door_w - 0.06, 0.022, 0.02),
                    "panel_seam",
                    bevel=1,
                )
            b.box(
                node,
                (x - door_w * 0.36, mid_y, z + sign * 0.028),
                (0.045, 0.17, 0.055),
                "chrome",
                bevel=1,
            )
            b.box(
                node,
                (x, mid_y - door_h / 2 + 0.10, z + sign * 0.012),
                (door_w * 0.55, 0.03, 0.018),
                "panel_seam",
                bevel=1,
            )
        for win_x, win_w, win_y, win_h in windows:
            b.box(node, (win_x, win_y, z + sign * 0.02), (win_w, win_h, 0.03), "trim_black", 1)
            b.box(
                node,
                (win_x, win_y, z + sign * 0.035),
                (win_w - 0.07, win_h - 0.07, 0.02),
                "glass",
                bevel=1,
            )
    b.box(node, (back_x - 0.02, mid_y, 0.0), (0.06, height * 0.96, half_width * 1.98), "aluminium")


# ------------------------------------------------------------------------------------------
# Bristlecone -- desert-tan overland pickup carrying a cab-over camper, on 37s with flares.
# ------------------------------------------------------------------------------------------


def bristlecone(materials) -> Build:
    b = Build("bristlecone", materials)
    r, w = 0.54, 0.40
    front_x, rear_x, track = 2.34, -1.50, 0.94
    half, sill, belt, hood, roof = 1.02, 0.90, 1.76, 1.62, 2.34
    cab_back = 1.00
    camper_front, camper_back, camper_roof = 0.34, -3.60, 2.86

    frame_rails(b, "base_chassis", 3.06, -3.34, 0.94)
    live_axle(b, "base_chassis", front_x, r, track)
    live_axle(b, "base_chassis", rear_x, r, track)
    b.cyl("base_chassis", (0.4, 0.62, 0.0), 0.05, 3.4, "x", "chassis_steel")  # driveshaft

    for x in (front_x, rear_x):
        for z in (track, -track):
            road_wheel(b, "base_wheels", x, z, r, w)

    front_clip(
        b,
        "base_cab",
        nose_x=3.32,
        cowl_x=2.12,
        roof_back_x=cab_back,
        sill_y=sill,
        belt_y=belt,
        hood_y=hood,
        roof_y=roof,
        half_width=half,
        chrome=False,
        flare=True,
        wheel_x=front_x,
        wheel_r=r,
        wheel_w=w,
    )
    b.box(
        "base_cab",
        (cab_back - 0.03, (sill + roof) / 2, 0.0),
        (0.08, roof - sill, half * 1.92),
        "body_paint",
    )
    b.cyl("base_cab", (2.02, 1.98, half * 1.05), 0.052, 1.34, "y", "trim_black")  # snorkel riser
    b.box("base_cab", (2.02, 2.68, half * 1.05), (0.22, 0.17, 0.14), "trim_black")  # snorkel head

    # Bed, then the camper sitting in it with its nose out over the cab roof.
    b.prof(
        "base_habitat",
        [(-3.60, 1.02)]
        + arch_cut(rear_x, r, 1.02, clearance=1.34)
        + [(0.34, 1.02), (0.34, 1.36), (-3.60, 1.36)],
        0.0,
        half * 2,
        "body_paint",
    )
    b.mirrored("arch", "base_habitat", (rear_x, r, half * 0.88), r * 1.09, w * 2.5, "trim_black")
    module_body(
        b,
        "base_habitat",
        front_x=camper_front,
        back_x=camper_back,
        floor_y=1.34,
        roof_y=camper_roof,
        half_width=1.04,
        doors=0,
        skirt=True,
        windows=((-0.55, 1.05, 2.30, 0.62), (-2.45, 0.80, 2.30, 0.58)),
    )
    b.box("base_habitat", (-3.05, 1.90, half * 0.92), (0.90, 1.05, 0.06), "trim_black")  # door
    nose = [
        (camper_front, 2.36),
        (1.62, 2.42),
        (1.16, camper_roof),
        (camper_front, camper_roof),
    ]
    b.prof("base_habitat", nose, 0.0, 2.02, "body_paint")
    b.prof(
        "base_habitat", [(1.52, 2.50), (1.22, 2.79), (1.26, 2.83), (1.56, 2.54)], 0.0, 1.58, "glass"
    )
    b.cyl("base_habitat", (-3.72, 1.06, 0.0), 0.09, 1.30, "z", "chassis_steel")  # spare carrier
    b.tyre("base_habitat", (-3.86, 1.30, 0.0), r, w, "tyre_rubber", False)
    b.rim("base_habitat", (-3.86, 1.30, 0.0), r * 0.56, w * 1.02, "wheel_hub", 1.0)
    b.box("base_habitat", (-3.72, 0.78, 0.0), (0.26, 0.28, half * 2.02), "trim_black")  # bumper

    # --- options ---------------------------------------------------------------------------
    crew_front, crew_back = cab_back, 0.34
    b.prof(
        "cab-chassis_cab-crew",
        [(crew_back, sill), (crew_front, sill), (crew_front, belt), (crew_back, belt)],
        0.0,
        half * 2,
        "body_paint",
    )
    b.prof(
        "cab-chassis_cab-crew",
        [(crew_back, belt), (crew_front, belt), (crew_front, roof), (crew_back, roof)],
        0.0,
        half * 1.93,
        "body_paint",
    )
    for sign in (1, -1):
        z = sign * half * 0.965
        b.box(
            "cab-chassis_cab-crew",
            (0.68, (belt + roof) / 2 + 0.05, z),
            (0.56, roof - belt - 0.26, 0.03),
            "glass",
            bevel=1,
        )
        b.box(
            "cab-chassis_cab-crew",
            (0.98, (sill + belt) / 2, sign * half),
            (0.025, belt - sill, 0.02),
            "panel_seam",
            bevel=1,
        )
        b.box(
            "cab-chassis_cab-crew",
            (0.86, belt - 0.20, sign * half),
            (0.18, 0.045, 0.035),
            "chrome",
            bevel=1,
        )

    b.prof(
        "habitat-shell_shell-extended",
        [
            (-0.45, camper_roof),
            (-0.45, camper_roof + 0.46),
            (-2.70, camper_roof + 0.46),
            (-2.70, camper_roof),
        ],
        0.0,
        2.06,
        "body_paint",
    )
    b.mirrored(
        "box",
        "habitat-shell_shell-extended",
        (-1.58, camper_roof + 0.24, 1.02),
        (2.10, 0.28, 0.04),
        "glass",
        1,
    )

    b.box(
        "power-system_solar-standard",
        (-0.10, camper_roof + 0.04, 0.0),
        (0.92, 0.045, 1.52),
        "solar_cell",
        bevel=1,
    )
    b.box(
        "power-system_solar-max",
        (-1.35, camper_roof + 0.04, 0.0),
        (1.20, 0.045, 1.86),
        "solar_cell",
        bevel=1,
    )
    b.box(
        "power-system_solar-max",
        (-2.65, camper_roof + 0.04, 0.0),
        (0.95, 0.045, 1.86),
        "solar_cell",
        bevel=1,
    )

    b.box(
        "water-thermal_ac-rooftop",
        (-0.95, camper_roof + 0.14, 0.0),
        (0.80, 0.24, 0.74),
        "aluminium",
    )
    b.box(
        "water-thermal_ac-rooftop",
        (-0.95, camper_roof + 0.28, 0.0),
        (0.62, 0.06, 0.58),
        "trim_black",
        bevel=1,
    )

    for x in (front_x, rear_x):
        for sign in (1, -1):
            z = sign * track * 0.78
            b.cyl(
                "suspension-tires_suspension-longtravel",
                (x - 0.30, r + 0.36, z),
                0.075,
                0.62,
                "y",
                "lamp_amber",
            )
            b.cyl(
                "suspension-tires_suspension-longtravel",
                (x - 0.30, r + 0.36, z),
                0.115,
                0.54,
                "y",
                "aluminium",
            )
            b.cyl(
                "suspension-tires_suspension-longtravel",
                (x + 0.34, r + 0.30, z),
                0.055,
                0.56,
                "y",
                "aluminium",
            )
    for x in (front_x, rear_x):
        for z in (track, -track):
            road_wheel(
                b,
                "suspension-tires_suspension-longtravel-mt",
                x,
                z,
                r + 0.07,
                w + 0.05,
                chunky=True,
            )

    b.box(
        "recovery-protection_bumper-heavy",
        (3.44, 1.00, 0.0),
        (0.30, 0.44, half * 2.2),
        "chassis_steel",
    )
    b.mirrored(
        "cyl",
        "recovery-protection_bumper-heavy",
        (3.44, 1.58, half * 0.86),
        0.055,
        1.10,
        "y",
        "chassis_steel",
    )
    b.cyl(
        "recovery-protection_bumper-heavy",
        (3.44, 2.12, 0.0),
        0.055,
        half * 1.72,
        "z",
        "chassis_steel",
    )
    b.cyl(
        "recovery-protection_bumper-heavy",
        (3.44, 1.86, 0.0),
        0.045,
        half * 1.20,
        "z",
        "chassis_steel",
    )

    b.cyl("recovery-protection_winch-12000", (3.22, 1.06, 0.0), 0.115, 0.80, "z", "aluminium")
    b.mirrored(
        "box",
        "recovery-protection_winch-12000",
        (3.22, 1.06, 0.46),
        (0.26, 0.30, 0.10),
        "trim_black",
    )
    b.box("recovery-protection_winch-12000", (3.40, 1.06, 0.0), (0.09, 0.22, 0.28), "chassis_steel")

    b.mirrored(
        "cyl",
        "recovery-protection_rock-sliders",
        (0.70, 0.68, half * 1.10),
        0.065,
        2.90,
        "x",
        "chassis_steel",
    )
    for x in (1.90, 0.70, -0.50):
        b.mirrored(
            "box",
            "recovery-protection_rock-sliders",
            (x, 0.80, half * 1.10),
            (0.10, 0.30, 0.10),
            "chassis_steel",
        )

    b.box(
        "roof-storage_rooftop-tent",
        (-2.30, camper_roof + 0.30, 0.0),
        (1.90, 0.34, 1.94),
        "aluminium",
    )
    b.box(
        "roof-storage_rooftop-tent",
        (-2.30, camper_roof + 0.68, 0.0),
        (1.74, 0.42, 1.78),
        "tent_canvas",
    )
    b.cyl(
        "roof-storage_rooftop-tent", (-1.30, camper_roof + 0.10, 0.0), 0.035, 1.10, "z", "aluminium"
    )

    b.mirrored(
        "cyl",
        "roof-storage_roof-rack-basic",
        (-1.60, camper_roof + 0.10, 0.90),
        0.035,
        3.60,
        "x",
        "trim_black",
    )
    for x in (0.10, -1.60, -3.30):
        b.cyl(
            "roof-storage_roof-rack-basic",
            (x, camper_roof + 0.10, 0.0),
            0.035,
            1.86,
            "z",
            "trim_black",
        )
    return b


# ------------------------------------------------------------------------------------------
# Ironwood -- white enclosed service body on a chrome-bumper chassis cab, crane over the roof.
# ------------------------------------------------------------------------------------------


def ironwood(materials) -> Build:
    b = Build("ironwood", materials)
    r, w = 0.50, 0.34
    front_x, rear_x, track = 2.28, -1.62, 0.92
    half, sill, belt, hood, roof = 1.02, 0.86, 1.70, 1.56, 2.26
    cab_back = 0.70
    body_front, body_back, body_roof = 0.60, -3.20, 2.30

    frame_rails(b, "base_chassis", 3.00, -3.34, 0.90)
    live_axle(b, "base_chassis", front_x, r, track)
    live_axle(b, "base_chassis", rear_x, r, track, spring_z=0.56)
    b.cyl("base_chassis", (0.35, 0.58, 0.0), 0.05, 3.3, "x", "chassis_steel")

    for z in (track, -track):
        road_wheel(b, "base_wheels", front_x, z, r, w)
    for sign in (1, -1):  # dual rears, as the photograph shows
        for inner in (0.78, 1.08):
            road_wheel(b, "base_wheels", rear_x, sign * inner, r, 0.26)

    front_clip(
        b,
        "base_cab",
        nose_x=3.26,
        cowl_x=2.06,
        roof_back_x=cab_back,
        sill_y=sill,
        belt_y=belt,
        hood_y=hood,
        roof_y=roof,
        half_width=half,
        chrome=True,
        wheel_x=front_x,
        wheel_r=r,
        wheel_w=w,
    )
    b.box(
        "base_cab",
        (cab_back - 0.03, (sill + roof) / 2, 0.0),
        (0.08, roof - sill, half * 1.92),
        "body_paint",
    )
    for index in range(5):  # cab-roof clearance lamps
        b.box(
            "base_cab",
            (1.05, roof + 0.04, (index - 2) * 0.17),
            (0.13, 0.06, 0.10),
            "lamp_amber",
            bevel=1,
        )

    module_body(
        b,
        "base_body",
        front_x=body_front,
        back_x=body_back,
        floor_y=0.94,
        roof_y=body_roof,
        half_width=1.06,
        doors=3,
        nose_radius=0.34,
        wheel=(rear_x, r),
    )
    b.box("base_body", (-1.30, 0.90, 0.0), (3.80, 0.10, 2.12), "diamond_plate")  # body floor
    b.mirrored(
        "box", "base_body", (-1.30, 0.84, half * 1.06), (3.20, 0.09, 0.22), "diamond_plate"
    )  # running board
    b.box("base_body", (body_back - 0.10, 1.24, 0.0), (0.14, 0.44, 2.10), "diamond_plate")
    b.mirrored("arch", "base_body", (rear_x, r, 1.06), r * 1.12, 0.96, "body_paint")

    # --- options ---------------------------------------------------------------------------
    b.box("cab-chassis_chassis-4x4", (front_x, 0.44, 0.0), (0.92, 0.14, 1.05), "chassis_steel")
    b.cyl("cab-chassis_chassis-4x4", (0.55, 0.58, 0.0), 0.20, 0.62, "x", "chassis_steel")
    b.mirrored(
        "box", "cab-chassis_chassis-4x4", (front_x, 0.92, 0.60), (0.20, 0.34, 0.18), "lamp_amber"
    )
    b.mirrored(
        "cyl",
        "cab-chassis_chassis-4x4",
        (rear_x + 0.30, 0.86, 0.60),
        0.05,
        0.50,
        "y",
        "chassis_steel",
    )

    module_body(
        b,
        "service-body_body-extended",
        front_x=body_back,
        back_x=body_back - 1.15,
        floor_y=0.94,
        roof_y=body_roof,
        half_width=1.06,
        doors=1,
    )
    b.box(
        "service-body_body-extended",
        (body_back - 0.58, 0.90, 0.0),
        (1.15, 0.10, 2.12),
        "diamond_plate",
    )

    # A knuckle-boom crane stowed forward along the body roof, the way the hero photo shows it.
    b.box("crane-lifting_crane-3200lb", (0.30, 2.44, -0.66), (0.62, 0.32, 0.66), "aluminium")
    b.cyl("crane-lifting_crane-3200lb", (0.30, 2.86, -0.66), 0.15, 0.60, "y", "chassis_steel")
    b.prof(
        "crane-lifting_crane-3200lb",
        [(0.10, 3.02), (2.40, 3.62), (2.40, 3.46), (0.10, 2.86)],
        -0.66,
        0.22,
        "aluminium",
    )
    b.prof(
        "crane-lifting_crane-3200lb",
        [(0.16, 2.98), (2.33, 3.55), (2.33, 3.49), (0.16, 2.92)],
        -0.66,
        0.30,
        "trim_black",
    )
    b.box("crane-lifting_crane-3200lb", (2.50, 3.56, -0.66), (0.30, 0.26, 0.30), "trim_black")
    b.cyl("crane-lifting_crane-3200lb", (2.56, 3.16, -0.66), 0.022, 0.70, "y", "chassis_steel")
    b.cyl("crane-lifting_crane-3200lb", (1.00, 3.04, -0.66), 0.07, 1.10, "x", "chassis_steel")

    b.box(
        "crane-lifting_liftgate-hydraulic",
        (body_back - 0.52, 0.74, 0.0),
        (0.95, 0.08, 2.05),
        "diamond_plate",
    )
    b.mirrored(
        "box",
        "crane-lifting_liftgate-hydraulic",
        (body_back - 0.12, 0.96, 0.98),
        (0.22, 0.58, 0.12),
        "chassis_steel",
    )
    b.cyl(
        "crane-lifting_liftgate-hydraulic",
        (body_back - 0.24, 1.12, 0.0),
        0.06,
        0.48,
        "x",
        "aluminium",
    )

    b.box(
        "power-system_generator-onboard",
        (-0.35, body_roof + 0.30, 0.0),
        (1.10, 0.58, 0.88),
        "aluminium",
    )
    b.box(
        "power-system_generator-onboard",
        (-0.35, body_roof + 0.30, 0.44),
        (0.90, 0.40, 0.05),
        "trim_black",
        bevel=1,
    )
    b.cyl(
        "power-system_generator-onboard",
        (0.20, body_roof + 0.72, 0.0),
        0.05,
        0.32,
        "y",
        "chassis_steel",
    )

    for x, z in ((0.45, 0.98), (0.45, -0.98), (-2.90, 0.98), (-2.90, -0.98)):
        b.cyl(
            "lighting-safety_scene-lighting",
            (x, body_roof + 0.24, z),
            0.045,
            0.44,
            "y",
            "trim_black",
        )
        b.box(
            "lighting-safety_scene-lighting",
            (x, body_roof + 0.50, z),
            (0.34, 0.16, 0.20),
            "lamp_amber",
        )

    b.box(
        "lighting-safety_arrow-board",
        (body_back - 0.20, 1.76, 0.0),
        (0.12, 0.76, 1.90),
        "trim_black",
    )
    b.box(
        "lighting-safety_arrow-board",
        (body_back - 0.28, 1.76, 0.0),
        (0.05, 0.58, 1.62),
        "lamp_amber",
        bevel=1,
    )
    return b


# ------------------------------------------------------------------------------------------
# Sentinel -- walk-in command module on the same chassis cab, warning lighting and a mast.
# ------------------------------------------------------------------------------------------


def sentinel(materials) -> Build:
    b = Build("sentinel", materials)
    r, w = 0.52, 0.34
    front_x, rear_x, track = 2.30, -1.66, 0.92
    half, sill, belt, hood, roof = 1.02, 0.88, 1.72, 1.58, 2.28
    cab_back = 0.80
    mod_front, mod_back, mod_roof = 0.12, -3.50, 2.88

    frame_rails(b, "base_chassis", 3.02, -3.60, 0.92)
    live_axle(b, "base_chassis", front_x, r, track)
    live_axle(b, "base_chassis", rear_x, r, track, spring_z=0.56)
    b.cyl("base_chassis", (0.32, 0.60, 0.0), 0.05, 3.3, "x", "chassis_steel")

    for z in (track, -track):
        road_wheel(b, "base_wheels", front_x, z, r, w, rim="aluminium")
    for sign in (1, -1):
        for inner in (0.78, 1.08):
            road_wheel(b, "base_wheels", rear_x, sign * inner, r, 0.26, rim="aluminium")

    front_clip(
        b,
        "base_cab",
        nose_x=3.28,
        cowl_x=2.08,
        roof_back_x=cab_back,
        sill_y=sill,
        belt_y=belt,
        hood_y=hood,
        roof_y=roof,
        half_width=half,
        chrome=True,
        wheel_x=front_x,
        wheel_r=r,
        wheel_w=w,
    )
    b.box(
        "base_cab",
        (cab_back - 0.03, (sill + roof) / 2, 0.0),
        (0.08, roof - sill, half * 1.92),
        "body_paint",
    )

    module_body(
        b,
        "base_module",
        front_x=mod_front,
        back_x=mod_back,
        floor_y=1.00,
        roof_y=mod_roof,
        half_width=1.10,
        doors=1,
        nose_radius=0.26,
        wheel=(rear_x, r),
        windows=((-0.35, 0.55, 2.32, 0.50), (-1.45, 0.60, 2.32, 0.50), (-2.55, 0.60, 2.32, 0.50)),
    )
    b.mirrored("box", "base_module", (-1.69, 2.02, 1.10), (3.52, 0.055, 0.03), "lamp_blue", 1)
    b.mirrored("box", "base_module", (-1.69, 1.92, 1.10), (3.52, 0.045, 0.03), "aluminium", 1)
    b.mirrored("box", "base_module", (-1.69, 0.92, 1.06), (3.10, 0.09, 0.24), "aluminium")
    b.mirrored("arch", "base_module", (rear_x, r, 1.10), r * 1.12, 0.96, "body_paint")
    b.box("base_module", (mod_back - 0.14, 1.90, 0.0), (0.16, 1.60, 2.00), "aluminium")

    # --- options ---------------------------------------------------------------------------
    b.prof(
        "cab-chassis_cab-crew-extended",
        [(0.18, sill), (cab_back, sill), (cab_back, belt), (0.18, belt)],
        0.0,
        half * 2,
        "body_paint",
    )
    b.prof(
        "cab-chassis_cab-crew-extended",
        [(0.18, belt), (cab_back, belt), (cab_back, roof), (0.18, roof)],
        0.0,
        half * 1.93,
        "body_paint",
    )
    for sign in (1, -1):
        z = sign * half * 0.965
        b.box(
            "cab-chassis_cab-crew-extended",
            (0.50, (belt + roof) / 2 + 0.05, z),
            (0.52, roof - belt - 0.26, 0.03),
            "glass",
            bevel=1,
        )
        b.box(
            "cab-chassis_cab-crew-extended",
            (0.78, (sill + belt) / 2, sign * half),
            (0.025, belt - sill, 0.02),
            "panel_seam",
            bevel=1,
        )

    module_body(
        b,
        "command-module_module-extended",
        front_x=mod_back,
        back_x=mod_back - 1.05,
        floor_y=1.00,
        roof_y=mod_roof,
        half_width=1.10,
        doors=1,
        windows=((mod_back - 0.55, 0.50, 2.32, 0.50),),
    )

    b.cyl("communications_mast-33ft", (-0.10, mod_roof + 0.30, 0.86), 0.10, 0.60, "y", "trim_black")
    b.cyl("communications_mast-33ft", (-0.10, mod_roof + 1.35, 0.86), 0.072, 1.60, "y", "aluminium")
    b.cyl("communications_mast-33ft", (-0.10, mod_roof + 2.55, 0.86), 0.050, 1.10, "y", "aluminium")
    b.box(
        "communications_mast-33ft", (-0.10, mod_roof + 3.14, 0.86), (0.46, 0.10, 0.46), "trim_black"
    )

    b.mirrored(
        "cyl",
        "communications_radio-suite",
        (-2.35, mod_roof + 0.62, 0.72),
        0.018,
        1.20,
        "y",
        "chassis_steel",
    )
    b.box(
        "communications_radio-suite", (-2.80, mod_roof + 0.16, 0.0), (0.50, 0.30, 0.60), "aluminium"
    )
    b.cyl("communications_radio-suite", (-3.10, mod_roof + 0.22, 0.0), 0.26, 0.14, "y", "aluminium")

    b.box(
        "power-system_generator-onboard-10kw", (-1.95, 1.34, 1.12), (1.20, 0.62, 0.42), "aluminium"
    )
    b.box(
        "power-system_generator-onboard-10kw",
        (-1.95, 1.34, 1.30),
        (0.98, 0.44, 0.05),
        "trim_black",
        bevel=1,
    )
    b.cyl(
        "power-system_generator-onboard-10kw", (-2.55, 1.10, 1.12), 0.05, 0.34, "x", "chassis_steel"
    )

    b.box(
        "lighting-warning_lightbar-full", (1.11, roof + 0.10, 0.0), (0.34, 0.14, 1.86), "trim_black"
    )
    for index in range(9):
        z = (index - 4) * 0.19
        lamp = "lamp_red" if index % 3 == 0 else ("lamp_blue" if index % 3 == 1 else "aluminium")
        b.box(
            "lighting-warning_lightbar-full",
            (1.11, roof + 0.13, z),
            (0.30, 0.10, 0.15),
            lamp,
            bevel=1,
        )

    for x, z in ((-0.05, 1.10), (-0.05, -1.10), (-3.30, 1.10), (-3.30, -1.10)):
        b.box(
            "lighting-warning_scene-lighting-perimeter",
            (x, mod_roof - 0.12, z),
            (0.30, 0.14, 0.10),
            "lamp_amber",
            bevel=1,
        )
    b.mirrored(
        "box",
        "lighting-warning_scene-lighting-perimeter",
        (-1.69, mod_roof - 0.10, 1.11),
        (3.10, 0.06, 0.05),
        "aluminium",
        1,
    )

    for index in range(3):
        x = -0.15 - index * 1.10
        b.box(
            "storage-racking_exterior-compartments",
            (x, 1.46, 1.13),
            (1.05, 0.80, 0.10),
            "aluminium",
        )
        b.box(
            "storage-racking_exterior-compartments",
            (x, 1.46, 1.19),
            (0.92, 0.68, 0.04),
            "panel_seam",
            bevel=1,
        )
        b.box(
            "storage-racking_exterior-compartments",
            (x - 0.36, 1.46, 1.22),
            (0.05, 0.16, 0.05),
            "chrome",
            bevel=1,
        )
    return b


# ------------------------------------------------------------------------------------------
# Materials, meshes, and the check that none of the above lost a node the catalog names.
# ------------------------------------------------------------------------------------------

# The placeholder's material values were picked to read at all under flat shading. With bevels
# and smooth normals doing that work instead, they can go back to being physically sensible.
REALISM = {
    "body_paint": (0.15, 0.30),
    "glass": (0.0, 0.05),
    "chassis_steel": (0.85, 0.46),
    "aluminium": (0.95, 0.26),
    "diamond_plate": (0.90, 0.34),
    "trim_black": (0.15, 0.62),
    "tyre_rubber": (0.0, 0.95),
    "tyre_lug": (0.0, 0.97),
    "wheel_hub": (0.85, 0.32),
    "solar_cell": (0.35, 0.16),
    "tent_canvas": (0.0, 0.88),
}


def srgb_to_linear(hex_colour: str) -> tuple[float, float, float]:
    channels = (int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5))
    return tuple(((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92 for c in channels)


def make_material(spec: dict) -> bpy.types.Material:
    """One Blender material per name, so the exporter emits exactly one glTF material per name.

    ``scene.ts`` keys its recolour map on material *name*, keeping one instance per key -- two
    glTF materials both called ``body_paint`` would leave whichever lost the race stuck at its
    authored colour when a finish option is picked.
    """
    material = bpy.data.materials.new(spec["name"])
    material.use_nodes = True
    principled = next(n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    red, green, blue = srgb_to_linear(spec["color"])
    metallic, roughness = REALISM.get(spec["name"], (spec["metallic"], spec["roughness"]))
    principled.inputs["Base Color"].default_value = (red, green, blue, 1.0)
    principled.inputs["Metallic"].default_value = metallic
    principled.inputs["Roughness"].default_value = roughness
    return material


def emit_node(name: str, parts: list, materials: dict) -> bpy.types.Object:
    """One Blender object per catalog node, its parts merged into a single multi-material mesh.

    A node is what an option's ``model_effect`` hides and shows, and ``scene.ts`` toggles
    ``object.visible`` on whatever it finds by that name -- so a node has to be one object, not a
    parent with children whose names would also land in the lookup.
    """
    vertices: list = []
    faces: list = []
    face_slots: list[int] = []
    slots: list[str] = []

    for part_vertices, part_faces, material in parts:
        if material not in slots:
            slots.append(material)
        base = len(vertices)
        vertices.extend(part_vertices)
        faces.extend(tuple(index + base for index in face) for face in part_faces)
        face_slots.extend([slots.index(material)] * len(part_faces))

    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    for material in slots:
        obj.data.materials.append(materials[material])
    for polygon, slot in zip(mesh.polygons, face_slots, strict=True):
        polygon.material_index = slot
        polygon.use_smooth = True

    # Creases stay crisp, curvature does not. Parts never share vertices, so an edge only ever
    # spans two faces of the same part and the angle test cannot fuse two neighbouring parts.
    bm = bmesh.new()
    bm.from_mesh(mesh)
    for edge in bm.edges:
        edge.smooth = not (len(edge.link_faces) == 2 and edge.calc_face_angle(0.0) > SHARP_ANGLE)
    bm.to_mesh(mesh)
    bm.free()

    bpy.context.scene.collection.objects.link(obj)
    return obj


def check_contract(build: Build, reference) -> None:
    """Fail loudly if this file has drifted from the node set the catalog's effects name.

    ``make_placeholder_models`` is not the source of geometry any more, but it is still the file
    that agrees with ``seed/catalog.yaml`` node for node -- and ``SyncModelsUseCase.validate``
    refuses a whole sync over one missing name. Catching it here means catching it before an
    upload rather than after one.
    """
    expected = {node["name"] for node in reference.nodes}
    produced = set(build.nodes)
    missing, extra = expected - produced, produced - expected
    if missing or extra:
        raise SystemExit(
            f"{build.slug}: node set drifted from the catalog contract\n"
            f"  missing: {sorted(missing)}\n  unexpected: {sorted(extra)}"
        )


def _export_override():
    """The glTF exporter reads ``context.active_object``, which a bare context does not carry.

    Running this file through the MCP server means running it from a ``bpy.app.timers`` callback,
    whose context has no window and no view layer, so the exporter fails on the attribute rather
    than on its value. Under ``blender -b`` the context is already complete, which keeps the two
    entry points on one code path.
    """
    if hasattr(bpy.context, "active_object"):
        return contextlib.nullcontext()
    window = bpy.context.window_manager.windows[0]
    return bpy.context.temp_override(
        window=window,
        screen=window.screen,
        area=window.screen.areas[0],
        scene=bpy.context.scene,
        view_layer=bpy.context.view_layer,
    )


def export(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _export_override():
        bpy.ops.export_scene.gltf(
            filepath=str(path),
            export_format="GLB",
            use_selection=False,
            export_apply=True,
            export_yup=True,
            export_materials="EXPORT",
            export_normals=True,
            export_cameras=False,
            export_lights=False,
            export_extras=False,
            export_draco_mesh_compression_enable=False,
        )


BUILDERS = {"bristlecone": bristlecone, "ironwood": ironwood, "sentinel": sentinel}


def main(out_dir: Path) -> None:
    references = read_part_specs()
    for slug, builder in BUILDERS.items():
        reference = references[slug]
        bpy.ops.wm.read_factory_settings(use_empty=True)
        build = builder(reference.materials)
        check_contract(build, reference)

        materials = {name: make_material(spec) for name, spec in build.materials.items()}
        triangles = 0
        for name, parts in build.nodes.items():
            obj = emit_node(name, parts, materials)
            triangles += sum(len(p.vertices) - 2 for p in obj.data.polygons)
        destination = out_dir / f"{slug}.glb"
        export(destination)
        print(
            f"{slug}: {len(build.nodes)} nodes, {triangles} triangles, "
            f"{destination.stat().st_size / 1024:.0f} KiB -> {destination}"
        )


def _out_dir_from_argv() -> Path:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return Path(argv[0]).resolve() if argv else TOOLS_DIR.parent / "seed" / "models"


if __name__ == "__main__":
    main(_out_dir_from_argv())
