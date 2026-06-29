"""Gerador de rodas (eixo Y). Capacidade real: pneu + aro + disco de freio +
cubo + N raios radiais, parametrizado. Substitui o cilindro liso anterior.
"""

import math

from vehicle_workspace.generators.blender_utils import (
    create_box_rot,
    create_cylinder_y,
    make_material,
)
from vehicle_workspace.vehicle.coordinate_system import wheel_positions


def _spokes(name, center, side, r, width, n, material):
    """N raios radiais no plano X-Z (eixo da roda = Y), na face externa."""
    created = []
    r_in = r * 0.20
    r_out = r * 0.60
    rmid = (r_in + r_out) / 2.0
    spoke_len = r_out - r_in
    y_face = center[1] + side * width * 0.42
    for j in range(n):
        a = j * 2.0 * math.pi / n
        dx, dz = math.cos(a), -math.sin(a)
        pos = (center[0] + rmid * dx, y_face, center[2] + rmid * dz)
        spoke = create_box_rot(
            f"{name}_spoke_{j}",
            pos,
            (spoke_len, width * 0.16, r * 0.12),
            rotation=(0, a, 0),
            material=material,
            bevel=0.004,
        )
        created.append(spoke.name)
    return created


def generate_wheels(spec):
    mat_tire = make_material("vehicle_tire_rubber", (0.015, 0.014, 0.013, 1.0), roughness=0.9)
    mat_rim = make_material("vehicle_wheel_rim", (0.62, 0.64, 0.67, 1.0), roughness=0.3, metallic=0.7)
    mat_disc = make_material("vehicle_brake_disc", (0.22, 0.22, 0.24, 1.0), roughness=0.4, metallic=0.5)
    mat_hub = make_material("vehicle_wheel_hub", (0.08, 0.08, 0.09, 1.0), roughness=0.45, metallic=0.3)
    mat_caliper = make_material("vehicle_brake_caliper", (0.75, 0.12, 0.05, 1.0), roughness=0.4)

    created = []
    for wheel in wheel_positions(spec["_meters"]):
        c = (wheel["x"], wheel["y"], wheel["z"])
        r = wheel["radius"]
        w = wheel["width"]
        side = 1.0 if wheel["y"] >= 0 else -1.0
        name = f"vehicle_wheel_{wheel['id']}"

        tire = create_cylinder_y(f"{name}_tire", c, r, w, mat_tire, vertices=80)
        created.append(tire.name)

        # disco de freio (atras dos raios)
        disc = create_cylinder_y(
            f"{name}_brake_disc",
            (c[0], c[1] - side * w * 0.10, c[2]),
            r * 0.58, w * 0.18, mat_disc, vertices=48,
        )
        created.append(disc.name)

        # pinca de freio (vermelha), no topo do disco
        caliper = create_box_rot(
            f"{name}_caliper",
            (c[0] - r * 0.18, c[1] - side * w * 0.10, c[2] + r * 0.5),
            (r * 0.22, w * 0.18, r * 0.30),
            rotation=(0, 0, 0), material=mat_caliper, bevel=0.006,
        )
        created.append(caliper.name)

        # barril do aro (raso) + cubo
        barrel = create_cylinder_y(f"{name}_rim", c, r * 0.30, w * 0.7, mat_rim, vertices=48)
        created.append(barrel.name)
        hub = create_cylinder_y(
            f"{name}_hub",
            (c[0], c[1] + side * w * 0.42, c[2]),
            r * 0.14, w * 0.16, mat_hub, vertices=24,
        )
        created.append(hub.name)

        created.extend(_spokes(name, c, side, r, w, 5, mat_rim))

    return {"objects": created, "wheel_centers": wheel_positions(spec["_meters"])}
