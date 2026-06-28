"""
Árvore com galhos via SDF RECURSIVO — o gerador orgânico de RAMIFICAÇÃO que faltava
(o blob não ramifica). Realiza a ideia de L-System/fractal: tronco -> galhos cada vez
menores e mais finos, distribuídos pelo ângulo de ouro (~137.5°), com afinamento (taper).

Rodar:  .venv/Scripts/python.exe prototype/arvore.py
"""

import os
import math
import functools
import numpy as np
from sdf import capped_cone

AQUI = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(AQUI, "out_arvore.stl")
OURO = math.radians(137.5)   # ângulo de ouro (filotaxia) distribui os galhos ao redor

TAPER = 0.70   # cada galho fica com 70% do raio do pai (afinamento natural)
ENCURTA = 0.74  # e 74% do comprimento
ABRE = math.radians(36)  # abertura do galho em relação ao pai


def _perp(d):
    a = np.array([0, 0, 1.0]) if abs(d[2]) < 0.9 else np.array([1.0, 0, 0])
    p = np.cross(d, a)
    return p / np.linalg.norm(p)


def _rot(v, eixo, ang):
    eixo = eixo / np.linalg.norm(eixo)
    return (v * math.cos(ang) + np.cross(eixo, v) * math.sin(ang)
            + eixo * np.dot(eixo, v) * (1 - math.cos(ang)))


def _dir_galho(d, radial):
    p = _rot(_perp(d), d, radial)            # gira o "pra onde abrir" ao redor do galho-pai
    nd = d * math.cos(ABRE) + p * math.sin(ABRE)
    return nd / np.linalg.norm(nd)


def _crescer(base, d, comp, raio, prof, n, segs):
    tip = base + d * comp
    segs.append(capped_cone(tuple(base), tuple(tip), raio, raio * TAPER))
    if prof <= 0:
        return
    for i in range(n):
        nd = _dir_galho(d, OURO * i + prof)  # distribui pelo ângulo de ouro
        _crescer(tip, nd, comp * ENCURTA, raio * TAPER, prof - 1, n, segs)


def gerar(profundidade=4, galhos=2, raio_tronco=0.10):
    segs = []
    _crescer(np.array([0, 0, 0.0]), np.array([0, 0, 1.0]), 1.0, raio_tronco,
             profundidade, galhos, segs)
    arvore = functools.reduce(lambda a, b: a | b, segs)
    return arvore, len(segs)


def main():
    arvore, n = gerar()
    print(f"[receita] {n} segmentos (tronco + galhos)")
    arvore.save(OUT, step=0.025)
    print(f"[gerou] {os.path.basename(OUT)}")
    import trimesh
    m = trimesh.load(OUT)
    print(f"vertices={len(m.vertices)} faces={len(m.faces)} "
          f"watertight={m.is_watertight} componentes={len(m.split(only_watertight=False))}")


if __name__ == "__main__":
    main()
