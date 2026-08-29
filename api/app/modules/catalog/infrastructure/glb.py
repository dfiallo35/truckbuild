"""Reads node and material names out of a GLB, without loading it as a scene.

A GLB is a 12-byte header (magic, version, total length) followed by chunks, the first of which
is always the glTF JSON document. Getting at ``nodes[].name`` and ``materials[].name`` is
``struct`` plus ``json`` over that first chunk -- **stdlib only, no new dependency** -- and is all
Stage 15's validation needs: whether the mesh or material an option's ``model_effect`` names is
actually in the file, not what it looks like. See docs/stages/15-blob-storage-ingest.md.
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass

from app.modules.catalog.domain.exceptions import InvalidModelFileError

GLB_MAGIC = b"glTF"
SUPPORTED_VERSION = 2
JSON_CHUNK_TYPE = b"JSON"

# magic (4s) + version (I) + total length (I)
HEADER_FORMAT = "<4sII"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

# chunk length (I) + chunk type (4s)
CHUNK_HEADER_FORMAT = "<I4s"
CHUNK_HEADER_SIZE = struct.calcsize(CHUNK_HEADER_FORMAT)


@dataclass(frozen=True)
class GlbContents:
    """The names Stage 15's validation cares about, out of a GLB's JSON chunk."""

    nodes: frozenset[str]
    materials: frozenset[str]


def read_glb(data: bytes, filename: str) -> GlbContents:
    """Parse ``data`` as a GLB and return the node and material names it declares.

    Raises ``InvalidModelFileError`` -- naming ``filename`` -- on a bad magic, an unsupported
    version, or a JSON chunk that does not parse. Geometry and binary chunks past the first are
    never read: nothing here needs them.
    """
    if len(data) < HEADER_SIZE:
        raise InvalidModelFileError(filename, "shorter than a GLB header")

    magic, version, _total_length = struct.unpack_from(HEADER_FORMAT, data, 0)
    if magic != GLB_MAGIC:
        raise InvalidModelFileError(filename, f"bad magic {magic!r}, expected {GLB_MAGIC!r}")
    if version != SUPPORTED_VERSION:
        raise InvalidModelFileError(filename, f"unsupported glTF version {version}")

    offset = HEADER_SIZE
    if offset + CHUNK_HEADER_SIZE > len(data):
        raise InvalidModelFileError(filename, "no chunks after the header")

    chunk_length, chunk_type = struct.unpack_from(CHUNK_HEADER_FORMAT, data, offset)
    offset += CHUNK_HEADER_SIZE
    if chunk_type != JSON_CHUNK_TYPE:
        raise InvalidModelFileError(filename, f"first chunk is {chunk_type!r}, expected JSON")

    chunk_data = data[offset : offset + chunk_length]
    if len(chunk_data) != chunk_length:
        raise InvalidModelFileError(filename, "JSON chunk is truncated")

    try:
        document = json.loads(chunk_data)
    except json.JSONDecodeError as exc:
        raise InvalidModelFileError(filename, f"JSON chunk does not parse: {exc}") from exc

    nodes = frozenset(node["name"] for node in document.get("nodes", []) if node.get("name"))
    materials = frozenset(
        material["name"] for material in document.get("materials", []) if material.get("name")
    )
    return GlbContents(nodes=nodes, materials=materials)
