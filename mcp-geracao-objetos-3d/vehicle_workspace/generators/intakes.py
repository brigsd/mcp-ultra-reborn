"""Entradas de ar laterais (Fase 5).

Lamina escura angular no flanco, ahead das rodas traseiras — marca registrada de
mid-engine. MVP: forma escura sobre a superficie (sem boolean), ancorada no perfil.
"""

import math

from vehicle_workspace.generators.blender_utils import (
    create_box_rot,
    make_material,
)


def _x(prof, s):
    return -prof["length"] / 2.0 + s * prof["length"]


def generate_intakes(spec, prof):
    created = []
    feats = spec.get("features", {})
    if not feats.get("side_intakes", True):
        return {"objects": created}

    mat_dark = make_material("vehicle_dark_detail", (0.015, 0.017, 0.018, 1.0), roughness=0.7)

    s = 0.36  # ahead da roda traseira (eixo traseiro ~ s 0.22)
    xi = _x(prof, s)
    yi = prof["half_width"](s) * 0.97
    zi = prof["deck_z"](s) * 0.62
    for side in (1, -1):
        intake = create_box_rot(
            f"vehicle_intake_side_{'left' if side > 0 else 'right'}",
            (xi, side * yi, zi),
            (0.52, 0.05, 0.24),
            rotation=(side * math.radians(8), 0, math.radians(-6)),
            material=mat_dark,
            bevel=0.012,
        )
        created.append(intake.name)
    return {"objects": created}
