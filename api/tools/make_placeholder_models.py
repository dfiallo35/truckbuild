"""Generates placeholder build models for the three demo platforms.

Low-poly stand-ins for a modeller's GLB, whose only job is to be *correct where the pipeline
looks*: every node an option's ``model_effect`` names exists, and the paint material is called
``body_paint``, so ``python -m app.assets sync`` validates and the configurator's option toggles
move something on screen. Node names follow ``docs/domain-model.md``'s
``<platform>_<group>_<option>`` convention -- which is a contract with a modeller, unenforced by
any schema, so a generator that keeps it is also the worked example of what it looks like.

Without this the 3D half of the build cannot be exercised at all outside a modelling tool: no GLB
is in the repo (they are large binaries, and ``api/seed/models/`` is gitignored), so
``platform.model`` stays null, ``BuildViewer`` never leaves its poster, and
``e2e/configurator.spec.ts``'s "the 3D canvas mounts" spec skips itself. Placeholder geometry is
not a substitute for the real asset -- it is what makes the pipeline around the real asset
testable before one exists.

Metres, Y up, front of the truck towards +X, so the catalog's camera orbit lands on a front
three-quarter view. Every part is sized against the framing pinned in ``seed/catalog.yaml``:
geometry outside that frame is a toggle nobody can see move.

Usage, from ``api/``::

    uv run python tools/make_placeholder_models.py seed/models
    docker compose exec api python -m app.assets sync --dry-run

See ``.claude/skills/model-ingest`` for where this sits in the ingest chain.
"""

from __future__ import annotations

import sys
from pathlib import Path

from glb_writer import Geometry, Glb, box, cylinder


def wheel(glb: Glb, x: float, z: float, radius: float, width: float) -> list[tuple[Geometry, int]]:
    tyre = glb.material("tyre_rubber", "#1a1a1c", metallic=0.0, roughness=0.95)
    hub = glb.material("wheel_hub", "#9aa0a6", metallic=0.9, roughness=0.35)
    return [
        (cylinder((x, radius, z), radius, width, axis="z", segments=20), tyre),
        (
            cylinder(
                (x, radius, z + (0.02 if z > 0 else -0.02)), radius * 0.55, width * 1.05, "z", 16
            ),
            hub,
        ),
    ]


def axle(glb: Glb, x: float, radius: float) -> list[tuple[Geometry, int]]:
    steel = glb.material("chassis_steel", "#3a3d42", metallic=0.8, roughness=0.5)
    return [
        (cylinder((x, radius, 0.0), 0.09, 2.0, axis="z", segments=12), steel),
        (cylinder((x, radius, 0.0), 0.2, 0.34, axis="z", segments=14), steel),
    ]


# --------------------------------------------------------------------------------------------
# Bristlecone -- expedition habitat on a 4x4 cab-chassis.
# --------------------------------------------------------------------------------------------


def bristlecone() -> Glb:
    glb = Glb()
    paint = glb.material("body_paint", "#8d9299", metallic=0.35, roughness=0.45)
    steel = glb.material("chassis_steel", "#3a3d42", metallic=0.8, roughness=0.5)
    black = glb.material("trim_black", "#141517", metallic=0.2, roughness=0.65)
    glass = glb.material("glass", "#243040", metallic=0.1, roughness=0.08)
    alu = glb.material("aluminium", "#b9bec4", metallic=0.9, roughness=0.3)
    solar = glb.material("solar_cell", "#131c33", metallic=0.4, roughness=0.25)
    amber = glb.material("lamp_amber", "#ffb547", metallic=0.0, roughness=0.4)

    wheel_r = 0.54

    glb.node(
        "bristlecone_base_chassis",
        [
            (box((0.1, 0.72, 0.42), (7.0, 0.22, 0.16)), steel),
            (box((0.1, 0.72, -0.42), (7.0, 0.22, 0.16)), steel),
            (box((0.1, 0.72, 0.0), (0.6, 0.14, 0.84)), steel),
            (box((-1.0, 0.66, 0.72), (1.3, 0.5, 0.36)), alu),  # fuel tank
            (box((-1.0, 0.66, -0.72), (1.3, 0.5, 0.36)), alu),
            *axle(glb, 2.35, wheel_r),
            *axle(glb, -1.95, wheel_r),
        ],
    )

    glb.node(
        "bristlecone_base_wheels",
        [
            *wheel(glb, 2.35, 1.02, wheel_r, 0.36),
            *wheel(glb, 2.35, -1.02, wheel_r, 0.36),
            *wheel(glb, -1.95, 1.02, wheel_r, 0.36),
            *wheel(glb, -1.95, -1.02, wheel_r, 0.36),
        ],
    )

    glb.node(
        "bristlecone_base_cab",
        [
            (box((2.2, 1.62, 0.0), (1.7, 1.34, 2.16)), paint),  # cab shell
            (box((2.92, 1.85, 0.0), (0.42, 0.72, 2.0)), glass),  # windshield
            (box((2.2, 1.85, 1.09), (1.0, 0.6, 0.06)), glass),  # side windows
            (box((2.2, 1.85, -1.09), (1.0, 0.6, 0.06)), glass),
            (box((3.24, 1.18, 0.0), (0.3, 0.62, 2.1)), black),  # grille
            (box((3.3, 1.42, 0.86), (0.16, 0.18, 0.3)), amber),  # headlamps
            (box((3.3, 1.42, -0.86), (0.16, 0.18, 0.3)), amber),
            (box((3.05, 0.86, 0.0), (0.34, 0.26, 2.3)), black),  # standard bumper
            (box((2.35, 0.98, 1.16), (1.9, 0.18, 0.14)), black),  # running boards
            (box((2.35, 0.98, -1.16), (1.9, 0.18, 0.14)), black),
        ],
    )

    # An expedition build carries the habitat behind the cab with a flex gap between them; the
    # gap is where the crew-cab section lands when that option is on.
    glb.node(
        "bristlecone_base_habitat",
        [
            (box((-1.45, 1.86, 0.0), (4.3, 1.86, 2.3)), paint),
            (box((-3.58, 1.86, 0.0), (0.08, 1.7, 2.16)), alu),  # rear wall panel
            (box((-2.9, 1.7, 1.16), (1.0, 1.1, 0.06)), black),  # entry door
            (box((-2.9, 1.72, 1.2), (0.1, 0.1, 0.06)), alu),  # handle
            (box((-0.6, 2.14, 1.16), (0.9, 0.62, 0.06)), glass),  # habitat window
            (box((-0.6, 2.14, -1.16), (0.9, 0.62, 0.06)), glass),
            (box((-1.45, 0.92, 1.18), (3.9, 0.16, 0.1)), alu),  # skirt
            (box((-1.45, 0.92, -1.18), (3.9, 0.16, 0.1)), alu),
        ],
    )

    glb.node(
        "bristlecone_cab-chassis_cab-crew",
        [
            (box((0.95, 1.62, 0.0), (0.86, 1.34, 2.16)), paint),
            (box((0.95, 1.85, 1.09), (0.62, 0.56, 0.06)), glass),
            (box((0.95, 1.85, -1.09), (0.62, 0.56, 0.06)), glass),
            (box((0.95, 0.98, 1.16), (0.8, 0.18, 0.14)), black),
            (box((0.95, 0.98, -1.16), (0.8, 0.18, 0.14)), black),
        ],
    )

    # A pop-top over the living half only, so the rooftop tent still has the rear roof to itself.
    glb.node(
        "bristlecone_habitat-shell_shell-extended",
        [
            (box((-0.75, 3.02, 0.0), (2.7, 0.46, 2.22)), paint),
            (box((-0.75, 3.02, 1.12), (2.4, 0.26, 0.06)), glass),
            (box((-0.75, 3.02, -1.12), (2.4, 0.26, 0.06)), glass),
        ],
    )

    glb.node(
        "bristlecone_power-system_solar-standard",
        [(box((0.25, 2.83, 0.0), (0.9, 0.05, 1.5)), solar)],
    )
    glb.node(
        "bristlecone_power-system_solar-max",
        [
            (box((-2.05, 2.83, 0.0), (1.2, 0.05, 1.9)), solar),
            (box((-3.15, 2.83, 0.0), (0.9, 0.05, 1.9)), solar),
        ],
    )
    glb.node(
        "bristlecone_water-thermal_ac-rooftop",
        [
            (box((-0.9, 2.94, 0.0), (0.78, 0.24, 0.72)), alu),
            (box((-0.9, 3.08, 0.0), (0.62, 0.06, 0.58)), black),
        ],
    )

    long_travel: list[tuple[Geometry, int]] = []
    for x in (2.35, -1.95):
        for z in (1.02, -1.02):
            long_travel += [
                (cylinder((x - 0.42, 0.95, z * 0.72), 0.09, 0.86, axis="y", segments=12), amber),
                (cylinder((x + 0.42, 0.95, z * 0.72), 0.07, 0.8, axis="y", segments=12), alu),
                (box((x, 0.62, z * 0.85), (0.5, 0.12, 0.2)), steel),
            ]
    glb.node("bristlecone_suspension-tires_suspension-longtravel", long_travel)

    mud_terrain: list[tuple[Geometry, int]] = []
    lug = glb.material("tyre_lug", "#0f1011", metallic=0.0, roughness=1.0)
    for x in (2.35, -1.95):
        for z in (1.06, -1.06):
            mud_terrain.append((cylinder((x, wheel_r + 0.06, z), 0.66, 0.44, "z", 22), lug))
    glb.node("bristlecone_suspension-tires_suspension-longtravel-mt", mud_terrain)

    glb.node(
        "bristlecone_recovery-protection_bumper-heavy",
        [
            (box((3.22, 0.94, 0.0), (0.42, 0.5, 2.36)), steel),
            (box((3.3, 1.5, 1.06), (0.22, 1.2, 0.16)), steel),  # bull-bar uprights
            (box((3.3, 1.5, -1.06), (0.22, 1.2, 0.16)), steel),
            (box((3.3, 2.06, 0.0), (0.22, 0.16, 2.28)), steel),  # top hoop
        ],
    )
    glb.node(
        "bristlecone_recovery-protection_winch-12000",
        [
            (cylinder((3.24, 1.02, 0.0), 0.16, 0.86, axis="z", segments=16), alu),
            (box((3.24, 1.02, 0.5), (0.3, 0.34, 0.12)), black),
            (box((3.24, 1.02, -0.5), (0.3, 0.34, 0.12)), black),
            (box((3.44, 1.02, 0.0), (0.1, 0.24, 0.3)), steel),  # fairlead
        ],
    )
    glb.node(
        "bristlecone_recovery-protection_rock-sliders",
        [
            (box((0.6, 0.66, 1.24), (3.4, 0.14, 0.14)), steel),
            (box((0.6, 0.66, -1.24), (3.4, 0.14, 0.14)), steel),
            (box((1.9, 0.72, 1.24), (0.12, 0.3, 0.12)), steel),
            (box((1.9, 0.72, -1.24), (0.12, 0.3, 0.12)), steel),
            (box((-0.7, 0.72, 1.24), (0.12, 0.3, 0.12)), steel),
            (box((-0.7, 0.72, -1.24), (0.12, 0.3, 0.12)), steel),
        ],
    )

    glb.node(
        "bristlecone_roof-storage_rooftop-tent",
        [
            (box((-2.6, 3.02, 0.0), (1.9, 0.42, 2.0)), alu),
            (
                box((-2.6, 3.42, 0.0), (1.7, 0.4, 1.8)),
                glb.material("tent_canvas", "#3f4a3c", 0.0, 0.9),
            ),
            (box((-1.62, 2.6, 0.0), (0.14, 1.0, 0.4)), alu),  # ladder
        ],
    )
    glb.node(
        "bristlecone_roof-storage_roof-rack-basic",
        [
            (box((-1.45, 2.88, 1.06), (4.0, 0.1, 0.1)), black),
            (box((-1.45, 2.88, -1.06), (4.0, 0.1, 0.1)), black),
            (box((0.5, 2.88, 0.0), (0.1, 0.1, 2.2)), black),
            (box((-3.4, 2.88, 0.0), (0.1, 0.1, 2.2)), black),
        ],
    )
    return glb


# --------------------------------------------------------------------------------------------
# Ironwood -- service body, crane, lift gate.
# --------------------------------------------------------------------------------------------


def ironwood() -> Glb:
    glb = Glb()
    paint = glb.material("body_paint", "#d9dbdd", metallic=0.3, roughness=0.45)
    steel = glb.material("chassis_steel", "#3a3d42", metallic=0.8, roughness=0.5)
    black = glb.material("trim_black", "#141517", metallic=0.2, roughness=0.65)
    glass = glb.material("glass", "#243040", metallic=0.1, roughness=0.08)
    alu = glb.material("aluminium", "#b9bec4", metallic=0.9, roughness=0.3)
    amber = glb.material("lamp_amber", "#ffb547", metallic=0.0, roughness=0.4)
    plate = glb.material("diamond_plate", "#9298a0", metallic=0.85, roughness=0.4)

    wheel_r = 0.5

    glb.node(
        "ironwood_base_chassis",
        [
            (box((0.0, 0.68, 0.4), (6.6, 0.2, 0.16)), steel),
            (box((0.0, 0.68, -0.4), (6.6, 0.2, 0.16)), steel),
            (box((-0.4, 0.62, 0.72), (1.2, 0.44, 0.34)), alu),
            *axle(glb, 2.2, wheel_r),
            *axle(glb, -1.8, wheel_r),
        ],
    )
    glb.node(
        "ironwood_base_wheels",
        [
            *wheel(glb, 2.2, 0.98, wheel_r, 0.34),
            *wheel(glb, 2.2, -0.98, wheel_r, 0.34),
            *wheel(glb, -1.8, 1.06, wheel_r, 0.26),
            *wheel(glb, -1.8, 0.8, wheel_r, 0.26),
            *wheel(glb, -1.8, -1.06, wheel_r, 0.26),
            *wheel(glb, -1.8, -0.8, wheel_r, 0.26),
        ],
    )
    glb.node(
        "ironwood_base_cab",
        [
            (box((2.15, 1.5, 0.0), (2.1, 1.3, 2.1)), paint),
            (box((2.95, 1.72, 0.0), (0.5, 0.7, 1.94)), glass),
            (box((2.15, 1.72, 1.06), (1.5, 0.56, 0.06)), glass),
            (box((2.15, 1.72, -1.06), (1.5, 0.56, 0.06)), glass),
            (box((3.22, 1.06, 0.0), (0.28, 0.58, 2.04)), black),
            (box((3.28, 1.3, 0.82), (0.16, 0.18, 0.3)), amber),
            (box((3.28, 1.3, -0.82), (0.16, 0.18, 0.3)), amber),
            (box((3.04, 0.78, 0.0), (0.32, 0.26, 2.24)), black),
            (box((2.2, 0.9, 1.12), (2.0, 0.14, 0.2)), plate),
            (box((2.2, 0.9, -1.12), (2.0, 0.14, 0.2)), plate),
        ],
    )
    # A compartmentalised aluminium service body: floor, headboard, and side compartment doors.
    glb.node(
        "ironwood_base_body",
        [
            (box((-0.55, 0.86, 0.0), (3.4, 0.16, 2.3)), plate),
            (box((0.98, 1.6, 0.0), (0.14, 1.4, 2.24)), paint),  # headboard
            (box((-0.55, 1.42, 1.06), (3.3, 1.0, 0.2)), paint),  # side compartments
            (box((-0.55, 1.42, -1.06), (3.3, 1.0, 0.2)), paint),
            (box((0.25, 1.42, 1.18), (1.2, 0.86, 0.04)), black),
            (box((-1.35, 1.42, 1.18), (1.2, 0.86, 0.04)), black),
            (box((0.25, 1.42, -1.18), (1.2, 0.86, 0.04)), black),
            (box((-1.35, 1.42, -1.18), (1.2, 0.86, 0.04)), black),
            (box((-2.22, 1.3, 0.0), (0.12, 0.72, 2.3)), paint),  # tail panel
            (box((-2.34, 0.8, 0.0), (0.2, 0.26, 2.3)), black),
        ],
    )

    glb.node(
        "ironwood_cab-chassis_chassis-4x4",
        [
            (box((2.2, 0.5, 0.0), (0.9, 0.2, 1.1)), steel),  # front diff / skid plate
            (cylinder((2.2, 0.52, 0.0), 0.24, 0.5, axis="z", segments=14), steel),
            (box((0.6, 0.58, 0.0), (0.7, 0.3, 0.5)), steel),  # transfer case
            (cylinder((-1.8, 0.52, 0.0), 0.26, 0.56, axis="z", segments=14), steel),
            (box((2.2, 0.9, 0.62), (0.16, 0.5, 0.16)), amber),  # lift blocks
            (box((2.2, 0.9, -0.62), (0.16, 0.5, 0.16)), amber),
        ],
    )
    glb.node(
        "ironwood_service-body_body-extended",
        [
            (box((-2.9, 0.86, 0.0), (1.3, 0.16, 2.3)), plate),
            (box((-2.9, 1.42, 1.06), (1.3, 1.0, 0.2)), paint),
            (box((-2.9, 1.42, -1.06), (1.3, 1.0, 0.2)), paint),
            (box((-2.9, 1.42, 1.18), (1.0, 0.86, 0.04)), black),
            (box((-2.9, 1.42, -1.18), (1.0, 0.86, 0.04)), black),
        ],
    )
    glb.node(
        "ironwood_crane-lifting_crane-3200lb",
        [
            (box((0.72, 1.0, -0.72), (0.6, 0.28, 0.6)), steel),  # base
            (cylinder((0.72, 2.0, -0.72), 0.16, 1.9, axis="y", segments=14), alu),  # mast
            (box((0.05, 2.86, -0.72), (1.5, 0.22, 0.3)), alu),  # boom
            (box((-0.62, 2.7, -0.72), (0.3, 0.2, 0.24)), black),  # winch head
            (cylinder((-0.66, 2.3, -0.72), 0.03, 0.7, axis="y", segments=8), steel),  # cable
            (box((-0.66, 1.9, -0.72), (0.14, 0.24, 0.14)), steel),  # hook
        ],
    )
    glb.node(
        "ironwood_crane-lifting_liftgate-hydraulic",
        [
            (box((-2.75, 0.72, 0.0), (0.9, 0.1, 2.1)), plate),
            (box((-2.4, 0.9, 1.0), (0.24, 0.6, 0.14)), steel),
            (box((-2.4, 0.9, -1.0), (0.24, 0.6, 0.14)), steel),
            (cylinder((-2.5, 1.1, 0.0), 0.08, 0.5, axis="x", segments=10), alu),
        ],
    )
    glb.node(
        "ironwood_power-system_generator-onboard",
        [
            (box((-0.4, 2.16, 0.0), (1.1, 0.6, 0.86)), alu),
            (box((-0.4, 2.16, 0.44), (0.9, 0.42, 0.06)), black),
            (cylinder((0.2, 2.46, 0.0), 0.06, 0.34, axis="y", segments=8), steel),
        ],
    )
    glb.node(
        "ironwood_lighting-safety_scene-lighting",
        [
            (box((0.95, 2.5, 0.98), (0.1, 0.42, 0.1)), black),
            (box((0.95, 2.74, 0.98), (0.4, 0.16, 0.2)), amber),
            (box((0.95, 2.5, -0.98), (0.1, 0.42, 0.1)), black),
            (box((0.95, 2.74, -0.98), (0.4, 0.16, 0.2)), amber),
            (box((-2.1, 2.2, 0.98), (0.1, 0.42, 0.1)), black),
            (box((-2.1, 2.44, 0.98), (0.4, 0.16, 0.2)), amber),
            (box((-2.1, 2.2, -0.98), (0.1, 0.42, 0.1)), black),
            (box((-2.1, 2.44, -0.98), (0.4, 0.16, 0.2)), amber),
        ],
    )
    glb.node(
        "ironwood_lighting-safety_arrow-board",
        [
            (box((-2.42, 1.9, 0.0), (0.14, 0.8, 2.0)), black),
            (box((-2.5, 1.9, 0.0), (0.06, 0.6, 1.7)), amber),
        ],
    )
    return glb


# --------------------------------------------------------------------------------------------
# Sentinel -- command module, mast, warning lighting.
# --------------------------------------------------------------------------------------------


def sentinel() -> Glb:
    glb = Glb()
    paint = glb.material("body_paint", "#e6e8e6", metallic=0.3, roughness=0.42)
    steel = glb.material("chassis_steel", "#3a3d42", metallic=0.8, roughness=0.5)
    black = glb.material("trim_black", "#141517", metallic=0.2, roughness=0.65)
    glass = glb.material("glass", "#243040", metallic=0.1, roughness=0.08)
    alu = glb.material("aluminium", "#b9bec4", metallic=0.9, roughness=0.3)
    amber = glb.material("lamp_amber", "#ffb547", metallic=0.0, roughness=0.4)
    red = glb.material("lamp_red", "#e2453a", metallic=0.0, roughness=0.35)
    blue = glb.material("lamp_blue", "#3f7bd8", metallic=0.0, roughness=0.35)

    wheel_r = 0.54

    glb.node(
        "sentinel_base_chassis",
        [
            (box((0.0, 0.72, 0.42), (7.4, 0.22, 0.16)), steel),
            (box((0.0, 0.72, -0.42), (7.4, 0.22, 0.16)), steel),
            *axle(glb, 2.6, wheel_r),
            *axle(glb, -2.0, wheel_r),
        ],
    )
    glb.node(
        "sentinel_base_wheels",
        [
            *wheel(glb, 2.6, 1.02, wheel_r, 0.36),
            *wheel(glb, 2.6, -1.02, wheel_r, 0.36),
            *wheel(glb, -2.0, 1.1, wheel_r, 0.28),
            *wheel(glb, -2.0, 0.82, wheel_r, 0.28),
            *wheel(glb, -2.0, -1.1, wheel_r, 0.28),
            *wheel(glb, -2.0, -0.82, wheel_r, 0.28),
        ],
    )
    glb.node(
        "sentinel_base_cab",
        [
            (box((2.55, 1.62, 0.0), (1.8, 1.34, 2.2)), paint),
            (box((3.3, 1.86, 0.0), (0.42, 0.7, 2.04)), glass),
            (box((2.55, 1.86, 1.11), (1.2, 0.6, 0.06)), glass),
            (box((2.55, 1.86, -1.11), (1.2, 0.6, 0.06)), glass),
            (box((3.56, 1.2, 0.0), (0.28, 0.6, 2.1)), black),
            (box((3.62, 1.44, 0.86), (0.16, 0.18, 0.3)), amber),
            (box((3.62, 1.44, -0.86), (0.16, 0.18, 0.3)), amber),
            (box((3.4, 0.9, 0.0), (0.32, 0.28, 2.3)), black),
        ],
    )
    glb.node(
        "sentinel_base_module",
        [
            (box((-0.75, 1.94, 0.0), (4.4, 2.0, 2.34)), paint),
            (box((-2.98, 1.94, 0.0), (0.1, 1.84, 2.2)), alu),
            (box((0.3, 2.3, 1.18), (0.9, 0.6, 0.05)), glass),
            (box((0.3, 2.3, -1.18), (0.9, 0.6, 0.05)), glass),
            (box((-2.2, 1.72, 1.18), (1.0, 1.2, 0.05)), black),  # crew door
            (box((-2.2, 1.74, 1.22), (0.1, 0.1, 0.05)), alu),
            (box((-2.2, 0.7, 1.3), (0.9, 0.1, 0.34)), steel),  # step
            (box((-0.75, 0.9, 1.2), (4.0, 0.16, 0.12)), alu),
            (box((-0.75, 0.9, -1.2), (4.0, 0.16, 0.12)), alu),
        ],
    )

    glb.node(
        "sentinel_cab-chassis_cab-crew-extended",
        [
            (box((1.35, 1.62, 0.0), (0.6, 1.34, 2.2)), paint),
            (box((1.35, 1.86, 1.11), (0.44, 0.56, 0.06)), glass),
            (box((1.35, 1.86, -1.11), (0.44, 0.56, 0.06)), glass),
            (box((1.35, 0.98, 1.18), (0.56, 0.16, 0.16)), black),
            (box((1.35, 0.98, -1.18), (0.56, 0.16, 0.16)), black),
        ],
    )
    glb.node(
        "sentinel_command-module_module-extended",
        [
            (box((-3.55, 1.94, 0.0), (1.15, 2.0, 2.34)), paint),
            (box((-4.14, 1.94, 0.0), (0.1, 1.84, 2.2)), alu),
            (box((-3.6, 2.3, 1.18), (0.7, 0.5, 0.05)), glass),
            (box((-3.6, 2.3, -1.18), (0.7, 0.5, 0.05)), glass),
        ],
    )
    # Foreshortened deliberately: a mast at its full 33 ft stands well outside the frame the
    # catalog's `camera_distance_m` pins, and a toggle whose geometry is off-screen tests
    # nothing. A real model would either be modelled stowed or come with its own framing.
    glb.node(
        "sentinel_communications_mast-33ft",
        [
            (box((-2.6, 3.1, -0.86), (0.44, 0.3, 0.44)), steel),  # mast foot
            (cylinder((-2.6, 3.66, -0.86), 0.12, 0.95, axis="y", segments=12), alu),
            (cylinder((-2.6, 4.24, -0.86), 0.085, 0.7, axis="y", segments=12), alu),
            (box((-2.6, 4.42, -0.86), (1.0, 0.07, 0.07)), black),  # cross-elements
            (box((-2.6, 4.56, -0.86), (0.7, 0.07, 0.07)), black),
            (cylinder((-2.6, 4.66, -0.86), 0.02, 0.3, axis="y", segments=6), black),
        ],
    )
    glb.node(
        "sentinel_communications_radio-suite",
        [
            (box((-0.2, 3.06, 0.9), (0.5, 0.22, 0.5)), black),  # roof pod
            (cylinder((0.6, 3.4, 0.7), 0.02, 0.9, axis="y", segments=6), alu),  # whips
            (cylinder((0.6, 3.4, -0.7), 0.02, 0.9, axis="y", segments=6), alu),
            (cylinder((-1.4, 3.3, 0.9), 0.02, 0.7, axis="y", segments=6), alu),
            (box((-0.9, 3.12, -0.9), (0.7, 0.34, 0.7)), alu),  # satcom dome base
            (cylinder((-0.9, 3.34, -0.9), 0.3, 0.16, axis="y", segments=16), glass),
        ],
    )
    glb.node(
        "sentinel_power-system_generator-onboard-10kw",
        [
            (box((0.4, 0.66, 0.0), (1.5, 0.62, 1.0)), alu),
            (box((0.4, 0.66, 0.52), (1.2, 0.46, 0.06)), black),
            (cylinder((-0.4, 0.5, 0.4), 0.07, 1.2, axis="x", segments=10), steel),  # exhaust
        ],
    )
    glb.node(
        "sentinel_lighting-warning_lightbar-full",
        [
            (box((2.55, 2.36, 0.0), (0.4, 0.16, 2.16)), black),
            (box((2.55, 2.36, 0.72), (0.36, 0.14, 0.62)), red),
            (box((2.55, 2.36, -0.72), (0.36, 0.14, 0.62)), blue),
            (box((2.55, 2.36, 0.0), (0.36, 0.14, 0.5)), amber),
        ],
    )
    glb.node(
        "sentinel_lighting-warning_scene-lighting-perimeter",
        [
            (box((1.15, 2.9, 1.1), (0.3, 0.14, 0.18)), amber),
            (box((1.15, 2.9, -1.1), (0.3, 0.14, 0.18)), amber),
            (box((-1.5, 2.9, 1.18), (0.3, 0.14, 0.14)), amber),
            (box((-1.5, 2.9, -1.18), (0.3, 0.14, 0.14)), amber),
            (box((-2.94, 2.6, 0.6), (0.14, 0.14, 0.3)), amber),
            (box((-2.94, 2.6, -0.6), (0.14, 0.14, 0.3)), amber),
        ],
    )
    glb.node(
        "sentinel_storage-racking_exterior-compartments",
        [
            (box((-0.2, 1.36, 1.19), (1.3, 0.9, 0.06)), alu),
            (box((-1.55, 1.36, -1.19), (1.2, 0.9, 0.06)), alu),
            (box((0.5, 1.36, -1.19), (1.2, 0.9, 0.06)), alu),
            (box((-0.2, 1.36, 1.24), (0.2, 0.08, 0.05)), black),
            (box((-1.55, 1.36, -1.24), (0.2, 0.08, 0.05)), black),
            (box((0.5, 1.36, -1.24), (0.2, 0.08, 0.05)), black),
        ],
    )
    return glb


PLATFORMS = {"bristlecone": bristlecone, "ironwood": ironwood, "sentinel": sentinel}


def main() -> None:
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    for slug, builder in PLATFORMS.items():
        data = builder().to_bytes()
        target = out_dir / f"{slug}.glb"
        target.write_bytes(data)
        print(f"{target}  {len(data):,} bytes")


if __name__ == "__main__":
    main()
