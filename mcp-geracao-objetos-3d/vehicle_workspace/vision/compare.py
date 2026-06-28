"""Comparacao de silhueta lateral: nosso render vs blueprint.

Foca o perfil superior (teto/capo/deck) em mm acima do solo, calibrado pelo
comprimento conhecido. Faz auto-flip (tenta as duas orientacoes e escolhe a de
menor erro) para nao depender de o carro estar virado pro mesmo lado nas duas
imagens. Reporta IoU de area e erro medio com sinal por regiao.
"""

import numpy as np

from vehicle_workspace.vision.silhouette import (
    foreground_mask,
    height_profile_mm,
    load_gray,
)

# Regioes semanticas em X normalizado, nariz primeiro (0 = nariz, 1 = traseira).
DEFAULT_REGIONS = [
    ("front_overhang", 0.00, 0.12),
    ("front_wheel", 0.12, 0.28),
    ("hood_cowl", 0.28, 0.42),
    ("cabin", 0.42, 0.64),
    ("rear_deck", 0.64, 0.82),
    ("rear_overhang", 0.82, 1.00),
]


def _orient_nose_first(height_mm):
    """Orienta o perfil para nariz primeiro: o nariz e a ponta de menor altura
    media. Se a ponta direita for mais baixa, inverte."""
    n = len(height_mm)
    q = max(1, n // 4)
    left = np.nanmean(height_mm[:q])
    right = np.nanmean(height_mm[-q:])
    if right < left:
        return height_mm[::-1].copy(), True
    return height_mm.copy(), False


def _area_iou(a, b):
    """IoU 1D de area sob os perfis (min/max por amostra)."""
    inter = np.minimum(a, b).sum()
    union = np.maximum(a, b).sum()
    return float(inter / union) if union > 0 else 0.0


def _region_errors(ours, blue, x_norm, regions):
    out = []
    for name, lo, hi in regions:
        sel = (x_norm >= lo) & (x_norm < hi)
        if sel.sum() == 0:
            continue
        diff = ours[sel] - blue[sel]  # + = nosso mais alto
        mean = float(np.mean(diff))
        direction = "ok"
        if mean > 8:
            direction = "too_tall"
        elif mean < -8:
            direction = "too_short"
        out.append({
            "region": name,
            "mean_error_mm": round(mean, 1),
            "abs_error_mm": round(float(np.mean(np.abs(diff))), 1),
            "direction": direction,
        })
    return out


def compare_profiles(ours_height, blue_height, x_norm, regions=DEFAULT_REGIONS):
    """Compara dois perfis de altura ja reamostrados no mesmo x_norm.
    Orienta ambos nariz-primeiro e testa flip do blueprint para alinhar."""
    ours, _ = _orient_nose_first(ours_height)

    best = None
    for flip in (False, True):
        cand = blue_height[::-1].copy() if flip else blue_height.copy()
        cand, _ = _orient_nose_first(cand)
        mae = float(np.mean(np.abs(ours - cand)))
        if best is None or mae < best["mae"]:
            best = {"mae": mae, "blue": cand, "flip": flip}

    blue = best["blue"]
    report = {
        "upper_area_iou": round(_area_iou(ours, blue), 4),
        "mean_abs_error_mm": round(best["mae"], 1),
        "max_error_mm": round(float(np.max(np.abs(ours - blue))), 1),
        "blueprint_flipped": best["flip"],
        "regions": _region_errors(ours, blue, x_norm, regions),
        "_ours_mm": ours,
        "_blue_mm": blue,
        "_x_norm": x_norm,
    }
    return report


def compare_side(render_png, blueprint_png, length_mm,
                 render_kind="render", blueprint_kind="auto", samples=240):
    """Pipeline completo: carrega os dois PNGs, extrai perfis de altura em mm e
    compara. blueprint_png deve ser um recorte da VISTA LATERAL."""
    g_r = load_gray(render_png)
    g_b = load_gray(blueprint_png)
    m_r = foreground_mask(g_r, kind=render_kind)
    m_b = foreground_mask(g_b, kind=blueprint_kind)
    hp_r = height_profile_mm(m_r, length_mm, samples=samples)
    hp_b = height_profile_mm(m_b, length_mm, samples=samples)
    rep = compare_profiles(hp_r["height_mm"], hp_b["height_mm"], hp_r["x_norm"])
    rep["render_calibration"] = {k: hp_r[k] for k in ("mm_per_px", "bbox_px")}
    rep["blueprint_calibration"] = {k: hp_b[k] for k in ("mm_per_px", "bbox_px")}
    return rep


def public_report(rep):
    """Versao serializavel (sem os arrays internos)."""
    return {k: v for k, v in rep.items() if not k.startswith("_")}
