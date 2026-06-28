"""Faróis e lanternas (Fase 5).

Faróis: unidades finas e angulares nos cantos dianteiros, material emissivo.
Lanternas: barra de LED larga e fina atravessando a traseira.
Ancorados nos perfis da carroceria (s: 0 traseira, 1 frente).
"""

import math

from vehicle_workspace.generators.blender_utils import (
    create_box_rot,
    make_emission,
)


def _x(prof, s):
    return -prof["length"] / 2.0 + s * prof["length"]


def generate_lights(spec, prof):
    created = []
    height = prof["height"]
    style = spec.get("style", {})

    mat_head = make_emission("vehicle_light_headlight", (0.85, 0.92, 1.0, 1.0), strength=6.0)
    mat_tail = make_emission("vehicle_light_taillight", (1.0, 0.06, 0.03, 1.0), strength=5.0)

    # Faróis dianteiros (par), finos e angulares
    s_h = 0.88
    xh = _x(prof, s_h)
    yh = prof["half_width"](s_h) * 0.70
    zh = prof["deck_z"](s_h) * 0.88
    thin = "thin" in str(style.get("headlights", "thin_angular_led"))
    dims = (0.34, 0.15, 0.06 if thin else 0.10)
    for side in (1, -1):
        hl = create_box_rot(
            f"vehicle_light_headlight_{'left' if side > 0 else 'right'}",
            (xh, side * yh, zh),
            dims,
            rotation=(0, math.radians(-10), side * math.radians(10)),
            material=mat_head,
            bevel=0.01,
        )
        created.append(hl.name)

    # Lanterna: barra fina atravessando a traseira
    s_t = 0.07
    xt = _x(prof, s_t)
    zt = prof["deck_z"](s_t) * 0.96
    bar_w = prof["width"] * 0.74
    bar = create_box_rot(
        "vehicle_light_taillight_bar",
        (xt, 0.0, zt),
        (0.05, bar_w, 0.06),
        rotation=(0, 0, 0),
        material=mat_tail,
        bevel=0.008,
    )
    created.append(bar.name)
    return {"objects": created}
