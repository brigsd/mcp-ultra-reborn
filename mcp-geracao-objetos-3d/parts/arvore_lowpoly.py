"""
Árvore Low Poly — gerador usando esqueleto + modificador Skin do Blender.

Técnica: constrói um esqueleto de vértices+arestas, aplica o modificador Skin
(que costura uma pele contínua ao redor das arestas), congela via depsgraph
e adiciona folhagem icosférica nas pontas. Roda 100% headless e via bridge GUI.

Baseado em prototype/arvore_skin.py (validado).
"""

import os
import math
import bpy
import numpy as np

OURO = math.radians(137.5)
TAPER, ENCURTA, ABRE = 0.72, 0.74, math.radians(34)


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


def _construir_esqueleto(profundidade, galhos, raio_tronco):
    pos, raio_vert, arestas, folhas = [], [], [], []

    base = np.array([0, 0, 0.0])
    i_raiz = 0
    pos.append(base)
    raio_vert.append(raio_tronco)

    def crescer(i_base, d, comp, raio, prof):
        tip = pos[i_base] + d * comp
        i_tip = len(pos)
        pos.append(tip)
        raio_vert.append(raio * TAPER)
        arestas.append((i_base, i_tip))
        if prof <= 0:
            folhas.append((tip, comp))
            return
        for k in range(galhos):
            nd = _dir_galho(d, OURO * k + prof)
            crescer(i_tip, nd, comp * ENCURTA, raio * TAPER, prof - 1)

    crescer(i_raiz, np.array([0, 0, 1.0]), 1.0, raio_tronco, profundidade)
    return pos, raio_vert, arestas, i_raiz, folhas


def _malha_esqueleto(pos, arestas, nome):
    me = bpy.data.meshes.new(nome)
    verts = [tuple(float(c) for c in p) for p in pos]
    me.from_pydata(verts, [tuple(int(i) for i in a) for a in arestas], [])
    me.update()
    obj = bpy.data.objects.new(nome, me)
    colecao = bpy.context.collection if bpy.context.collection is not None else bpy.data.scenes[0].collection
    colecao.objects.link(obj)
    return obj


def _aplicar_skin(obj, raio_vert, i_raiz):
    me = obj.data
    skin = obj.modifiers.new(name="Skin", type="SKIN")
    sv = me.skin_vertices[0].data
    for i, r in enumerate(raio_vert):
        sv[i].radius = (r, r)
    for i in range(len(sv)):
        sv[i].use_root = (i == i_raiz)
    skin.branch_smoothing = 0.0
    skin.use_smooth_shade = False
    me.update()


def _congelar(obj):
    deps = bpy.context.evaluated_depsgraph_get()
    me_eval = bpy.data.meshes.new_from_object(obj.evaluated_get(deps))
    obj.data = me_eval
    obj.modifiers.clear()


def gerar(profundidade=4, galhos=2, raio_tronco=0.10, com_folhagem=True, nome="ArvoreLowPoly"):
    """
    Gera uma árvore low-poly usando o modificador Skin do Blender.

    Args:
        profundidade: Níveis de recursão (4 = denso, 3 = médio, 2 = simples)
        galhos: Número de galhos por nó (2 = binária, 3 = tripla)
        raio_tronco: Espessura do tronco principal em metros
        com_folhagem: Se True, adiciona icoesferas baixas nas pontas dos galhos
        nome: Nome do objeto principal na cena

    Returns:
        Objeto Blender da árvore (tronco + galhos como malha única)
    """
    pos, raio_vert, arestas, i_raiz, folhas = _construir_esqueleto(
        profundidade, galhos, raio_tronco
    )

    arvore = _malha_esqueleto(pos, arestas, nome)
    _aplicar_skin(arvore, raio_vert, i_raiz)
    _congelar(arvore)

    if com_folhagem:
        for tip, comp in folhas:
            bpy.ops.mesh.primitive_ico_sphere_add(
                subdivisions=1, radius=comp * 1.6,
                location=(float(tip[0]), float(tip[1]), float(tip[2]))
            )

    return arvore


def gerar_e_validar(profundidade=4, galhos=2, raio_tronco=0.10, com_folhagem=True):
    """
    Gera a árvore e retorna o objeto e um relatório textual.
    Interface padrão requerida pelo gerar_modelo_3d do servidor MCP.
    """
    obj = gerar(profundidade=profundidade, galhos=galhos,
                 raio_tronco=raio_tronco, com_folhagem=com_folhagem)

    total_faces = sum(len(o.data.polygons) for o in bpy.data.objects if o.type == "MESH")
    total_verts = sum(len(o.data.vertices) for o in bpy.data.objects if o.type == "MESH")
    n_folhas = sum(1 for o in bpy.data.objects if o.type == "MESH" and o != obj)

    relatorio = (
        f"ArvoreLowPoly OK\n"
        f"  profundidade={profundidade}  galhos={galhos}  raio_tronco={raio_tronco}\n"
        f"  tronco+galhos: {len(obj.data.polygons)} faces\n"
        f"  folhagens: {n_folhas} esferas\n"
        f"  total na cena: {total_verts} vértices / {total_faces} faces"
    )

    return obj, relatorio
