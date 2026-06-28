"""Gera um PNG de overlay dos perfis superiores (nosso vs blueprint) para
inspecao visual humana. So PIL, sem matplotlib.

Verde = nosso modelo; laranja = blueprint. Eixo X = nariz->traseira.
"""

import numpy as np
from PIL import Image, ImageDraw


def draw_overlay(rep, out_path, width=900, height=320, pad=30):
    ours = rep["_ours_mm"]
    blue = rep["_blue_mm"]
    xn = rep["_x_norm"]
    hmax = max(float(np.max(ours)), float(np.max(blue)), 1.0)

    img = Image.new("RGB", (width, height), (24, 27, 32))
    d = ImageDraw.Draw(img)

    def to_px(t, h):
        x = pad + t * (width - 2 * pad)
        y = (height - pad) - (h / hmax) * (height - 2 * pad)
        return x, y

    # solo
    d.line([(pad, height - pad), (width - pad, height - pad)], fill=(80, 84, 92), width=1)

    def polyline(arr, color):
        pts = [to_px(xn[i], arr[i]) for i in range(len(arr))]
        d.line(pts, fill=color, width=3, joint="curve")

    polyline(blue, (240, 150, 40))   # blueprint
    polyline(ours, (90, 210, 120))   # nosso

    d.text((pad, 8), "verde=modelo  laranja=blueprint  (nariz->traseira)", fill=(200, 205, 212))
    d.text((pad, height - 20), f"IoU={rep.get('upper_area_iou')} MAE={rep.get('mean_abs_error_mm')}mm", fill=(200, 205, 212))

    img.save(out_path)
    return out_path
