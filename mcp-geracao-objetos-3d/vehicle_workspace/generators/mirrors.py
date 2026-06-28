"""Retrovisores externos (Fase 5): haste curta + cabeca, no inicio da cabine."""

from vehicle_workspace.generators.blender_utils import create_box, make_material


def _x(prof, s):
    return -prof["length"] / 2.0 + s * prof["length"]


def generate_mirrors(spec, prof):
    created = []
    mat_dark = make_material("vehicle_dark_detail", (0.015, 0.017, 0.018, 1.0), roughness=0.7)
    mat_glass = make_material("vehicle_mirror_glass", (0.3, 0.34, 0.4, 1.0), roughness=0.1, metallic=0.6)

    s = 0.62  # frente da cabine
    xm = _x(prof, s)
    y_body = prof["half_width"](s) * 0.92
    y_out = prof["wmax"] * 1.04
    zm = prof["deck_z"](s) + 0.06
    for side in (1, -1):
        stalk = create_box(
            f"vehicle_mirror_stalk_{'left' if side > 0 else 'right'}",
            (xm, side * (y_body + y_out) / 2.0, zm),
            (0.05, abs(y_out - y_body), 0.03),
            material=mat_dark,
            bevel=0.006,
        )
        created.append(stalk.name)
        head = create_box(
            f"vehicle_mirror_head_{'left' if side > 0 else 'right'}",
            (xm - 0.02, side * y_out, zm + 0.02),
            (0.06, 0.11, 0.10),
            material=mat_glass,
            bevel=0.02,
        )
        created.append(head.name)
    return {"objects": created}
