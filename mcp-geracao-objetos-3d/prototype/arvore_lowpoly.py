"""
Árvore LOW POLY — mostra que o ESTILO mudou o método de geração.
A árvore anterior (SDF + marching cubes) sai LISA e com MUITOS polígonos. Low poly é o oposto:
poucas faces, facetado. Então não dá pra usar SDF — constrói-se direto com primitivos de
poucos lados: cilindros de 5 lados (tronco/galhos) + folhagens facetadas (icosfera baixa).

Mesma regra de ramificação recursiva da arvore.py; só o "tijolo" muda (malha low-poly, não SDF).
Rodar:  .venv/Scripts/python.exe prototype/arvore_lowpoly.py
"""

import os
import math
import numpy as np
import trimesh

AQUI = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(AQUI, "out_arvore_lowpoly.stl")
OURO = math.radians(137.5)
TAPER, ENCURTA, ABRE = 0.72, 0.74, math.radians(34)
LADOS_GALHO = 5          # cilindro de 5 lados = claramente facetado
SUBDIV_FOLHA = 1         # icosfera bem baixa = folhagem chunky


def _perp(d):
    a = np.array([0, 0, 1.0]) if abs(d[2]) < 0.9 else np.array([1.0, 0, 0])
    p = np.cross(d, a)
    return p / np.linalg.norm(p)


def _rot(v, eixo, ang):
    eixo = eixo / np.linalg.norm(eixo)
    return (v * math.cos(ang) + np.cross(eixo, v) * math.sin(ang)
            + eixo * np.dot(eixo, v) * (1 - math.cos(ang)))


def _dir_galho(d, radial):
    p = _rot(_perp(d), d, radial)
    nd = d * math.cos(ABRE) + p * math.sin(ABRE)
    return nd / np.linalg.norm(nd)


def _crescer(base, d, comp, raio, prof, n, pecas):
    tip = base + d * comp
    pecas.append(trimesh.creation.cylinder(radius=raio, segment=[base.tolist(), tip.tolist()],
                                           sections=LADOS_GALHO))
    if prof <= 0:
        # folhagem facetada na ponta
        folha = trimesh.creation.icosphere(subdivisions=SUBDIV_FOLHA, radius=comp * 1.6)
        folha.apply_translation(tip)
        pecas.append(folha)
        return
    for i in range(n):
        nd = _dir_galho(d, OURO * i + prof)
        _crescer(tip, nd, comp * ENCURTA, raio * TAPER, prof - 1, n, pecas)


def gerar(profundidade=4, galhos=2, raio_tronco=0.10):
    pecas = []
    _crescer(np.array([0, 0, 0.0]), np.array([0, 0, 1.0]), 1.0, raio_tronco,
             profundidade, galhos, pecas)
    return trimesh.util.concatenate(pecas), len(pecas)


def main():
    arvore, n = gerar()
    arvore.export(OUT)
    print(f"[gerou] {os.path.basename(OUT)}  de {n} peças")
    print(f"vertices={len(arvore.vertices)}  faces={len(arvore.faces)}  (low poly = poucas faces)")


if __name__ == "__main__":
    main()
