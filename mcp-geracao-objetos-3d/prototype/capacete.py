"""
Capacete viking via SDF — a IA (eu) escrevendo a RECEITA procedural.
Não está no vocabulário da entrada; é o gerador orgânico (SDF) sendo dirigido na unha.
Versão simples e reconhecível: casco (meia-esfera oca) + aba + dois chifres.
"""

import os
import math
from sdf import sphere, slab, torus, capped_cone, X, Y, Z

AQUI = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(AQUI, "out_capacete.stl")


def chifre(sinal):
    # chifre grosso, reto, pra cima e pra fora (45°) — silhueta clássica de capacete viking
    h = capped_cone((0, 0, 0), (0, 0, 0.9), 0.22, 0.04)   # base grossa -> ponta fina
    h = h.rotate(math.radians(45 * sinal), Y)             # 45° pro lado
    h = h.translate((sinal * 0.62, 0.0, 0.46))            # sai da lateral alta do casco
    return h


def gerar():
    R = 1.0
    casco = sphere(R) & slab(z0=0.0)                  # meia-esfera (metade de cima)
    interno = sphere(R * 0.86) & slab(z0=-0.1)        # miolo (deixa base aberta)
    casco = casco - interno                           # casca
    aba = torus(R * 0.92, 0.08).translate((0, 0, 0.03))
    cap = casco | aba
    cap = cap.union(chifre(+1), k=0.08).union(chifre(-1), k=0.08)
    return cap


def main():
    f = gerar()
    f.save(OUT, step=0.03)
    print(f"[gerou] {os.path.basename(OUT)}")
    import trimesh
    m = trimesh.load(OUT)
    print(f"vertices={len(m.vertices)} faces={len(m.faces)} "
          f"watertight={m.is_watertight} componentes={len(m.split(only_watertight=False))}")


if __name__ == "__main__":
    main()
