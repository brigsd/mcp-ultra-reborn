"""
Seleção semântica de arestas e faces via bmesh.
A IA descreve o que quer selecionar em termos geométricos, não por índice.
"""

import bmesh
from bmesh.types import BMesh, BMEdge, BMFace
from mathutils import Vector
import math


# ---------------------------------------------------------------------------
# Seleção por string (interface simples para a IA)
# ---------------------------------------------------------------------------

def selecionar_arestas_por_string(bm: BMesh, descricao: str) -> list[BMEdge]:
    """
    descricao pode ser:
      "topo"            — arestas no Z máximo
      "base"            — arestas no Z mínimo
      "todas"           — todas as arestas
      "circulares_topo" — arestas circulares na face do topo
      "circulares_base" — arestas circulares na face da base
      "perfil"          — arestas verticais (paralelas ao eixo Z)
    """
    desc = descricao.lower()
    if desc == "todas":
        return list(bm.edges)
    elif desc == "topo":
        return selecionar_arestas_em_z_extremo(bm, extremo="max")
    elif desc == "base":
        return selecionar_arestas_em_z_extremo(bm, extremo="min")
    elif desc == "circulares_topo":
        return selecionar_arestas_circulares_em_z(bm, extremo="max")
    elif desc == "circulares_base":
        return selecionar_arestas_circulares_em_z(bm, extremo="min")
    elif desc == "perfil":
        return selecionar_arestas_verticais(bm)
    else:
        return []


# ---------------------------------------------------------------------------
# Seletores específicos
# ---------------------------------------------------------------------------

def selecionar_arestas_em_z_extremo(bm: BMesh, extremo: str = "max", tolerancia: float = 0.001) -> list[BMEdge]:
    zs = [v.co.z for v in bm.verts]
    z_alvo = max(zs) if extremo == "max" else min(zs)
    return [
        e for e in bm.edges
        if all(abs(v.co.z - z_alvo) < tolerancia for v in e.verts)
    ]


def selecionar_arestas_circulares_em_z(bm: BMesh, extremo: str = "max", tolerancia: float = 0.001) -> list[BMEdge]:
    """Arestas que formam círculos nas tampas superior ou inferior."""
    arestas_z = selecionar_arestas_em_z_extremo(bm, extremo, tolerancia)
    # Filtra arestas horizontais (dz ~0 entre seus vértices)
    return [
        e for e in arestas_z
        if abs(e.verts[0].co.z - e.verts[1].co.z) < tolerancia
    ]


def selecionar_arestas_verticais(bm: BMesh, tolerancia: float = 0.001) -> list[BMEdge]:
    """Arestas paralelas ao eixo Z (ex: perfil de um cilindro)."""
    return [
        e for e in bm.edges
        if (abs(e.verts[0].co.x - e.verts[1].co.x) < tolerancia and
            abs(e.verts[0].co.y - e.verts[1].co.y) < tolerancia)
    ]


def selecionar_faces_por_normal(bm: BMesh, direcao: Vector, tolerancia_graus: float = 10.0) -> list[BMFace]:
    """Seleciona faces cuja normal aponta para a direção dada (dentro da tolerância)."""
    direcao = direcao.normalized()
    limite = math.cos(math.radians(tolerancia_graus))
    return [f for f in bm.faces if f.normal.dot(direcao) >= limite]


def selecionar_faces_topo(bm: BMesh, tolerancia_graus: float = 10.0) -> list[BMFace]:
    return selecionar_faces_por_normal(bm, Vector((0, 0, 1)), tolerancia_graus)


def selecionar_faces_base(bm: BMesh, tolerancia_graus: float = 10.0) -> list[BMFace]:
    return selecionar_faces_por_normal(bm, Vector((0, 0, -1)), tolerancia_graus)


def selecionar_faces_laterais(bm: BMesh, tolerancia_z: float = 0.3) -> list[BMFace]:
    """Faces cujas normais são majoritariamente horizontais."""
    return [f for f in bm.faces if abs(f.normal.z) < tolerancia_z]


def selecionar_arestas_por_comprimento(
    bm: BMesh, comprimento_min: float, comprimento_max: float
) -> list[BMEdge]:
    return [
        e for e in bm.edges
        if comprimento_min <= e.calc_length() <= comprimento_max
    ]


def selecionar_arestas_em_raio(
    bm: BMesh, raio_alvo: float, tolerancia: float = 0.005
) -> list[BMEdge]:
    """Arestas cujos vértices estão a uma distância específica do eixo Z."""
    def dist_eixo(v):
        return math.sqrt(v.co.x**2 + v.co.y**2)

    return [
        e for e in bm.edges
        if all(abs(dist_eixo(v) - raio_alvo) < tolerancia for v in e.verts)
    ]
