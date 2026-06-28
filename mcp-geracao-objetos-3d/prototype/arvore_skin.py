"""
Árvore low poly por ESQUELETO + PELE CONTÍNUA (modificador Skin do Blender).

Conserta os dois defeitos da arvore_lowpoly.py (cilindros colados):
  1) emenda/degrau no nó tronco->galho  -> some, porque tronco e galhos
     COMPARTILHAM o mesmo vértice no nó e o Skin costura a malha ali.
  2) galho com cara de graveto reto      -> some, porque o raio cai por nível
     (raio_base -> raio_base*TAPER) e o Skin afina o tubo ao longo da aresta.

Roda DENTRO do Blender headless (tem bpy + numpy):
  "C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" \
      --background --python prototype/arvore_skin.py -- <saida.stl> <folhagem 0|1>

Depois renderiza com o de sempre:
  blender.exe --background --python prototype/render_views.py -- <saida.stl>
"""

import os
import sys
import math
import bpy
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))

# args depois de "--": [saida_stl, folhagem]
_extra = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = _extra[0] if len(_extra) >= 1 else os.path.join(AQUI, "out_arvore_skin.stl")
FOLHAGEM = (_extra[1] != "0") if len(_extra) >= 2 else True

# --- mesma matemática de arvore.py / arvore_lowpoly.py (sem mudar nada) ---
OURO = math.radians(137.5)        # ângulo de ouro distribui os galhos ao redor
TAPER, ENCURTA, ABRE = 0.72, 0.74, math.radians(34)
RAIO_TRONCO = 0.10


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


# --- 1) ESQUELETO: vértices (pos+raio), arestas, e pontas (folha) ---
# Cada nó = 1 vértice. O nó de bifurcação é UM vértice só: o galho-filho
# REUSA o índice da ponta do pai -> continuidade (sem isso volta a emenda).
def construir_esqueleto(profundidade=4, galhos=2, raio_tronco=RAIO_TRONCO):
    pos, raio_vert, arestas, folhas = [], [], [], []

    base = np.array([0, 0, 0.0])
    i_raiz = 0
    pos.append(base)
    raio_vert.append(raio_tronco)

    def crescer(i_base, d, comp, raio, prof):
        tip = pos[i_base] + d * comp
        i_tip = len(pos)
        pos.append(tip)
        raio_vert.append(raio * TAPER)        # raio na PONTA deste segmento
        arestas.append((i_base, i_tip))
        if prof <= 0:
            folhas.append((tip, comp))        # ponta -> aqui vai folhagem
            return
        for k in range(galhos):
            nd = _dir_galho(d, OURO * k + prof)
            crescer(i_tip, nd, comp * ENCURTA, raio * TAPER, prof - 1)

    crescer(i_raiz, np.array([0, 0, 1.0]), 1.0, raio_tronco, profundidade)
    return pos, raio_vert, arestas, i_raiz, folhas


# --- 2) malha só de vértices+arestas (faces=[]) ---
def malha_esqueleto(pos, arestas, nome="arvore_skin"):
    me = bpy.data.meshes.new(nome)
    verts = [tuple(float(c) for c in p) for p in pos]
    me.from_pydata(verts, [tuple(int(i) for i in a) for a in arestas], [])
    me.update()
    obj = bpy.data.objects.new(nome, me)
    bpy.context.collection.objects.link(obj)
    return obj


# --- 3) Skin: raio por vértice + raiz, e flags de low-poly ---
def aplicar_skin(obj, raio_vert, i_raiz):
    me = obj.data
    skin = obj.modifiers.new(name="Skin", type="SKIN")  # cria a layer skin_vertices
    sv = me.skin_vertices[0].data
    for i, r in enumerate(raio_vert):
        sv[i].radius = (r, r)                 # array de 2 (largura X,Y da seção)
    for i in range(len(sv)):
        sv[i].use_root = (i == i_raiz)        # exatamente 1 raiz na ilha
    skin.branch_smoothing = 0.0               # nó duro/anguloso = low-poly
    skin.use_smooth_shade = False             # facetado, não liso
    me.update()
    return skin


# --- 4) congela o Skin (rota depsgraph, robusta em headless) ---
def congelar(obj):
    deps = bpy.context.evaluated_depsgraph_get()
    me_eval = bpy.data.meshes.new_from_object(obj.evaluated_get(deps))
    obj.data = me_eval
    obj.modifiers.clear()


# --- folhagem facetada nas pontas (icosfera baixa), peça separada (ok) ---
def add_folha(tip, comp):
    bpy.ops.mesh.primitive_ico_sphere_add(
        subdivisions=1, radius=comp * 1.6,
        location=(float(tip[0]), float(tip[1]), float(tip[2])))


def exportar(caminho):
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.wm.stl_export(filepath=caminho, ascii_format=False,
                          export_selected_objects=True, apply_modifiers=True)


def main():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()

    pos, raio_vert, arestas, i_raiz, folhas = construir_esqueleto()
    arvore = malha_esqueleto(pos, arestas)
    aplicar_skin(arvore, raio_vert, i_raiz)
    congelar(arvore)
    n_galho = len(arvore.data.polygons)

    if FOLHAGEM:
        for tip, comp in folhas:
            add_folha(tip, comp)

    exportar(OUT)
    total = sum(len(o.data.polygons) for o in bpy.data.objects if o.type == "MESH")
    print(f"LARP: tronco+galhos={n_galho} faces (pele única)  "
          f"folhas={len(folhas) if FOLHAGEM else 0}  total={total} faces")
    print(f"LARP: exportado -> {os.path.basename(OUT)}  (folhagem={'on' if FOLHAGEM else 'off'})")
    print("LARP: FIM")


if __name__ == "__main__":
    main()
