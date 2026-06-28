"""
Primitivos geométricos de alto nível usando bmesh.
Todas as funções retornam o objeto Blender criado e já em modo Object.
A IA usa estas funções em vez de bpy.ops direto.
"""

import bpy
import bmesh
from mathutils import Vector, Matrix
import math


def _novo_objeto(nome, bm):
    mesh = bpy.data.meshes.new(nome)
    bm.to_mesh(mesh)
    mesh.update()
    obj = bpy.data.objects.new(nome, mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    return obj


# ---------------------------------------------------------------------------
# Sólidos básicos
# ---------------------------------------------------------------------------

def criar_cilindro(raio: float, altura: float, segmentos: int = 64, nome: str = "Cilindro") -> bpy.types.Object:
    bm = bmesh.new()
    bmesh.ops.create_cylinder(
        bm,
        cap_ends=True,
        cap_tris=False,
        segments=segmentos,
        radius1=raio,
        radius2=raio,
        depth=altura,
    )
    return _novo_objeto(nome, bm)


def criar_cilindro_oco(
    raio_ext: float,
    raio_int: float,
    altura: float,
    segmentos: int = 64,
    nome: str = "CilindroOco",
) -> bpy.types.Object:
    """Tubo/anel — ex: cubo de freio, aro, bucha."""
    bm = bmesh.new()
    # Cilindro externo
    bmesh.ops.create_cylinder(bm, cap_ends=True, cap_tris=False, segments=segmentos,
                               radius1=raio_ext, radius2=raio_ext, depth=altura)
    # Cilindro interno (vai ser subtraído)
    obj_ext = _novo_objeto("__tmp_ext__", bm)

    bm2 = bmesh.new()
    bmesh.ops.create_cylinder(bm2, cap_ends=True, cap_tris=False, segments=segmentos,
                               radius1=raio_int, radius2=raio_int, depth=altura * 1.01)
    obj_int = _novo_objeto("__tmp_int__", bm2)

    from api.operations import aplicar_booleano
    resultado = aplicar_booleano(obj_ext, obj_int, tipo="DIFFERENCE", nome_final=nome)
    return resultado


def criar_disco(
    raio: float,
    espessura: float,
    segmentos: int = 128,
    nome: str = "Disco",
) -> bpy.types.Object:
    """Disco sólido (cilindro achatado) — base para discos de freio."""
    return criar_cilindro(raio, espessura, segmentos, nome)


def criar_esfera(raio: float, subdivisoes: int = 4, nome: str = "Esfera") -> bpy.types.Object:
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=subdivisoes * 8, v_segments=subdivisoes * 4, radius=raio)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _novo_objeto(nome, bm)


def criar_caixa(
    largura: float,
    profundidade: float,
    altura: float,
    nome: str = "Caixa",
) -> bpy.types.Object:
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector((largura, profundidade, altura)), verts=bm.verts)
    return _novo_objeto(nome, bm)


def criar_cone(
    raio_base: float,
    raio_topo: float,
    altura: float,
    segmentos: int = 64,
    nome: str = "Cone",
) -> bpy.types.Object:
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm,
        cap_ends=True,
        cap_tris=False,
        segments=segmentos,
        radius1=raio_base,
        radius2=raio_topo,
        depth=altura,
    )
    return _novo_objeto(nome, bm)


def criar_torus(
    raio_maior: float,
    raio_menor: float,
    segmentos_maior: int = 48,
    segmentos_menor: int = 16,
    nome: str = "Torus",
) -> bpy.types.Object:
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=False, segments=segmentos_menor, radius=raio_menor)
    # Rotaciona e aplica spin
    bmesh.ops.rotate(bm, verts=bm.verts,
                     cent=Vector((0, 0, 0)),
                     matrix=Matrix.Rotation(math.pi / 2, 3, "X"))
    bmesh.ops.translate(bm, verts=bm.verts, vec=Vector((raio_maior, 0, 0)))
    resultado = bmesh.ops.spin(
        bm,
        geom=bm.verts[:] + bm.edges[:],
        axis=Vector((0, 0, 1)),
        cent=Vector((0, 0, 0)),
        angle=math.tau,
        steps=segmentos_maior,
        use_duplicate=False,
    )
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _novo_objeto(nome, bm)
