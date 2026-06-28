"""Aero real (Fase 5): splitter dianteiro, difusor traseiro com aletas e asa
traseira em lamina sobre dois suportes. Substitui as caixas cruas do blockout.
"""

import math

from vehicle_workspace.generators.blender_utils import (
    create_box,
    create_box_rot,
    make_material,
)


def _x(prof, s):
    return -prof["length"] / 2.0 + s * prof["length"]


def generate_aero(spec, prof):
    created = []
    width = prof["width"]
    height = prof["height"]
    gc = prof["gc"]
    feats = spec.get("features", {})
    mat_dark = make_material("vehicle_dark_detail", (0.015, 0.017, 0.018, 1.0), roughness=0.7)
    mat_carbon = make_material("vehicle_carbon", (0.03, 0.03, 0.035, 1.0), roughness=0.45, metallic=0.2)

    # Splitter dianteiro: lamina fina e larga, rente ao chao
    if feats.get("front_splitter", True):
        s = 0.965
        sp = create_box(
            "vehicle_aero_front_splitter",
            (_x(prof, s), 0.0, gc * 0.55),
            (0.22, width * 0.86, 0.028),
            material=mat_carbon,
            bevel=0.01,
        )
        created.append(sp.name)

    # Difusor traseiro: bloco escuro angulado + aletas verticais
    if feats.get("large_rear_diffuser", True):
        s = 0.045
        xd = _x(prof, s)
        block = create_box_rot(
            "vehicle_aero_rear_diffuser",
            (xd, 0.0, gc + 0.07),
            (0.26, width * 0.66, 0.16),
            rotation=(0, math.radians(-14), 0),
            material=mat_dark,
            bevel=0.006,
        )
        created.append(block.name)
        n = 5
        for i in range(n):
            y = (i - (n - 1) / 2.0) * (width * 0.66 / n)
            fin = create_box_rot(
                f"vehicle_aero_diffuser_fin_{i}",
                (xd, y, gc + 0.07),
                (0.28, 0.015, 0.18),
                rotation=(0, math.radians(-14), 0),
                material=mat_carbon,
                bevel=0.0,
            )
            created.append(fin.name)

    # Asa traseira: lamina sobre dois suportes
    if feats.get("active_rear_wing", True):
        s = 0.14
        xw = _x(prof, s)
        deck = prof["deck_z"](s)
        wing_z = height * 0.96
        blade = create_box_rot(
            "vehicle_aero_rear_wing",
            (xw, 0.0, wing_z),
            (0.30, width * 0.72, 0.035),
            rotation=(0, math.radians(7), 0),
            material=mat_carbon,
            bevel=0.012,
        )
        created.append(blade.name)
        strut_h = max(wing_z - deck, 0.12)
        for side in (1, -1):
            strut = create_box(
                f"vehicle_aero_wing_strut_{'left' if side > 0 else 'right'}",
                (xw, side * width * 0.28, deck + strut_h / 2.0),
                (0.05, 0.05, strut_h),
                material=mat_dark,
                bevel=0.004,
            )
            created.append(strut.name)

    return {"objects": created}
