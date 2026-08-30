"""A tiny GLB writer: boxes and cylinders, named nodes, named PBR materials.

Enough glTF 2.0 to satisfy `app/modules/catalog/infrastructure/glb.py`'s reader and three.js'
GLTFLoader, with no dependency beyond the stdlib -- same constraint the reader itself keeps.
"""

from __future__ import annotations

import json
import math
import struct
from dataclasses import dataclass, field

Vec3 = tuple[float, float, float]


@dataclass
class Geometry:
    """Flat-shaded triangle soup: 3 floats of position and normal per vertex."""

    positions: list[float] = field(default_factory=list)
    normals: list[float] = field(default_factory=list)
    indices: list[int] = field(default_factory=list)

    def extend(self, other: Geometry) -> None:
        offset = len(self.positions) // 3
        self.positions += other.positions
        self.normals += other.normals
        self.indices += [i + offset for i in other.indices]


def box(center: Vec3, size: Vec3) -> Geometry:
    cx, cy, cz = center
    hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
    corners = [
        (cx - hx, cy - hy, cz - hz),
        (cx + hx, cy - hy, cz - hz),
        (cx + hx, cy + hy, cz - hz),
        (cx - hx, cy + hy, cz - hz),
        (cx - hx, cy - hy, cz + hz),
        (cx + hx, cy - hy, cz + hz),
        (cx + hx, cy + hy, cz + hz),
        (cx - hx, cy + hy, cz + hz),
    ]
    faces = [
        ((4, 5, 6, 7), (0.0, 0.0, 1.0)),
        ((1, 0, 3, 2), (0.0, 0.0, -1.0)),
        ((5, 1, 2, 6), (1.0, 0.0, 0.0)),
        ((0, 4, 7, 3), (-1.0, 0.0, 0.0)),
        ((3, 7, 6, 2), (0.0, 1.0, 0.0)),
        ((0, 1, 5, 4), (0.0, -1.0, 0.0)),
    ]
    geometry = Geometry()
    for quad, normal in faces:
        base = len(geometry.positions) // 3
        for corner in quad:
            geometry.positions += list(corners[corner])
            geometry.normals += list(normal)
        geometry.indices += [base, base + 1, base + 2, base, base + 2, base + 3]
    return geometry


def cylinder(
    center: Vec3, radius: float, length: float, axis: str = "z", segments: int = 20
) -> Geometry:
    """A capped n-gon prism along `axis` -- wheels, drums, masts, antennas."""
    cx, cy, cz = center
    half = length / 2
    geometry = Geometry()

    def place(around_x: float, around_y: float, along: float) -> Vec3:
        if axis == "z":
            return (cx + around_x, cy + around_y, cz + along)
        if axis == "y":
            return (cx + around_x, cy + along, cz + around_y)
        return (cx + along, cy + around_x, cz + around_y)

    def normal_of(around_x: float, around_y: float) -> Vec3:
        if axis == "z":
            return (around_x, around_y, 0.0)
        if axis == "y":
            return (around_x, 0.0, around_y)
        return (0.0, around_x, around_y)

    for step in range(segments):
        a0 = 2 * math.pi * step / segments
        a1 = 2 * math.pi * (step + 1) / segments
        p0, p1 = (math.cos(a0), math.sin(a0)), (math.cos(a1), math.sin(a1))
        quad = [
            (place(p0[0] * radius, p0[1] * radius, -half), normal_of(*p0)),
            (place(p1[0] * radius, p1[1] * radius, -half), normal_of(*p1)),
            (place(p1[0] * radius, p1[1] * radius, half), normal_of(*p1)),
            (place(p0[0] * radius, p0[1] * radius, half), normal_of(*p0)),
        ]
        base = len(geometry.positions) // 3
        for position, normal in quad:
            geometry.positions += list(position)
            geometry.normals += list(normal)
        geometry.indices += [base, base + 1, base + 2, base, base + 2, base + 3]

    for along, winding in ((-half, False), (half, True)):
        cap_normal = (
            (0.0, 0.0, 1.0 if winding else -1.0)
            if axis == "z"
            else (0.0, 1.0 if winding else -1.0, 0.0)
            if axis == "y"
            else (1.0 if winding else -1.0, 0.0, 0.0)
        )
        center_index = len(geometry.positions) // 3
        geometry.positions += list(place(0.0, 0.0, along))
        geometry.normals += list(cap_normal)
        for step in range(segments + 1):
            angle = 2 * math.pi * step / segments
            geometry.positions += list(
                place(math.cos(angle) * radius, math.sin(angle) * radius, along)
            )
            geometry.normals += list(cap_normal)
        for step in range(segments):
            a, b = center_index + 1 + step, center_index + 2 + step
            geometry.indices += [center_index, b, a] if winding else [center_index, a, b]

    return geometry


class Glb:
    """Accumulates named nodes, each a set of (geometry, material) parts, then serialises."""

    def __init__(self) -> None:
        self._materials: dict[str, int] = {}
        self._material_json: list[dict] = []
        self._nodes: list[tuple[str, list[tuple[Geometry, int]]]] = []

    def material(self, name: str, color: str, metallic: float = 0.1, roughness: float = 0.7) -> int:
        if name in self._materials:
            return self._materials[name]
        red, green, blue = (int(color[i : i + 2], 16) / 255 for i in (1, 3, 5))
        # glTF base colours are linear; the hex is authored as sRGB.
        linear = [
            ((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92 for c in (red, green, blue)
        ]
        self._materials[name] = len(self._material_json)
        self._material_json.append(
            {
                "name": name,
                "pbrMetallicRoughness": {
                    "baseColorFactor": [*linear, 1.0],
                    "metallicFactor": metallic,
                    "roughnessFactor": roughness,
                },
                "doubleSided": True,
            }
        )
        return self._materials[name]

    def node(self, name: str, parts: list[tuple[Geometry, int]]) -> None:
        merged: dict[int, Geometry] = {}
        for geometry, material in parts:
            merged.setdefault(material, Geometry()).extend(geometry)
        self._nodes.append((name, [(geometry, m) for m, geometry in merged.items()]))

    def to_bytes(self) -> bytes:
        buffer = bytearray()
        views: list[dict] = []
        accessors: list[dict] = []
        meshes: list[dict] = []
        nodes: list[dict] = []

        def add_view(data: bytes, target: int) -> int:
            while len(buffer) % 4:
                buffer.append(0)
            views.append(
                {"buffer": 0, "byteOffset": len(buffer), "byteLength": len(data), "target": target}
            )
            buffer.extend(data)
            return len(views) - 1

        for name, parts in self._nodes:
            primitives = []
            for geometry, material in parts:
                count = len(geometry.positions) // 3
                position_view = add_view(
                    struct.pack(f"<{len(geometry.positions)}f", *geometry.positions), 34962
                )
                normal_view = add_view(
                    struct.pack(f"<{len(geometry.normals)}f", *geometry.normals), 34962
                )
                index_view = add_view(
                    struct.pack(f"<{len(geometry.indices)}H", *geometry.indices), 34963
                )
                axes = [geometry.positions[i::3] for i in range(3)]
                accessors.append(
                    {
                        "bufferView": position_view,
                        "componentType": 5126,
                        "count": count,
                        "type": "VEC3",
                        "min": [min(a) for a in axes],
                        "max": [max(a) for a in axes],
                    }
                )
                accessors.append(
                    {
                        "bufferView": normal_view,
                        "componentType": 5126,
                        "count": count,
                        "type": "VEC3",
                    }
                )
                accessors.append(
                    {
                        "bufferView": index_view,
                        "componentType": 5123,
                        "count": len(geometry.indices),
                        "type": "SCALAR",
                    }
                )
                primitives.append(
                    {
                        "attributes": {
                            "POSITION": len(accessors) - 3,
                            "NORMAL": len(accessors) - 2,
                        },
                        "indices": len(accessors) - 1,
                        "material": material,
                    }
                )
            meshes.append({"name": f"{name}_mesh", "primitives": primitives})
            nodes.append({"name": name, "mesh": len(meshes) - 1})

        document = {
            "asset": {"version": "2.0", "generator": "truckbuild placeholder model generator"},
            "scene": 0,
            "scenes": [{"nodes": list(range(len(nodes)))}],
            "nodes": nodes,
            "meshes": meshes,
            "materials": self._material_json,
            "accessors": accessors,
            "bufferViews": views,
            "buffers": [{"byteLength": len(buffer)}],
        }

        json_chunk = json.dumps(document, separators=(",", ":")).encode()
        json_chunk += b" " * (-len(json_chunk) % 4)
        bin_chunk = bytes(buffer)
        bin_chunk += b"\x00" * (-len(bin_chunk) % 4)

        total = 12 + 8 + len(json_chunk) + 8 + len(bin_chunk)
        out = bytearray(struct.pack("<4sII", b"glTF", 2, total))
        out += struct.pack("<I4s", len(json_chunk), b"JSON") + json_chunk
        out += struct.pack("<I4s", len(bin_chunk), b"BIN\x00") + bin_chunk
        return bytes(out)
