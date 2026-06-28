"""
Operações geométricas de alto nível — chamadas pela IA e pelas partes.
"""

import bpy
import bmesh
from mathutils import Vector, Matrix
import math


# ---------------------------------------------------------------------------
# Booleanos seguros
# ---------------------------------------------------------------------------

def aplicar_booleano(
    base: bpy.types.Object,
    cortador: bpy.types.Object,
    tipo: str = "DIFFERENCE",
    nome_final: str | None = None,
) -> bpy.types.Object:
    """Aplica booleano, remove o cortador, limpa a malha."""
    mod = base.modifiers.new("bool_op", "BOOLEAN")
    mod.operation = tipo
    mod.object = cortador
    mod.solver = "EXACT"

    bpy.context.view_layer.objects.active = base
    bpy.ops.object.modifier_apply(modifier=mod.name)

    bpy.data.objects.remove(cortador, do_unlink=True)

    # Limpar geometria
    bm = bmesh.new()
    bm.from_mesh(base.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(base.data)
    bm.free()
    base.data.update()

    if nome_final:
        base.name = nome_final
        base.data.name = nome_final

    return base


# ---------------------------------------------------------------------------
# Furos e padrões
# ---------------------------------------------------------------------------

def furar_radial(
    obj: bpy.types.Object,
    quantidade: int,
    raio_orbital: float,
    raio_furo: float,
    profundidade: float,
    angulo_inicial: float = 0.0,
    eixo: str = "Z",
    nome_furo: str = "Furo",
) -> bpy.types.Object:
    """
    Cria `quantidade` furos cilíndricos dispostos em padrão circular.
    Ideal para furos de ventilação de disco, furos de parafuso, etc.
    """
    from api.primitives import criar_cilindro

    for i in range(quantidade):
        angulo = angulo_inicial + (math.tau / quantidade) * i
        x = math.cos(angulo) * raio_orbital
        y = math.sin(angulo) * raio_orbital
        furo = criar_cilindro(raio_furo, profundidade * 1.02, segmentos=32, nome=f"__furo_{i}__")

        if eixo == "Z":
            furo.location = (x, y, 0)
        elif eixo == "X":
            furo.location = (0, x, y)
        else:
            furo.location = (x, 0, y)

        bpy.ops.object.select_all(action="DESELECT")
        obj = aplicar_booleano(obj, furo, tipo="DIFFERENCE")

    return obj


def padrao_radial(
    obj: bpy.types.Object,
    quantidade: int,
    eixo: str = "Z",
    manter_original: bool = False,
) -> list[bpy.types.Object]:
    """
    Duplica o objeto `quantidade` vezes em volta do eixo.
    Retorna lista com todas as cópias (incluindo o original se manter_original=True).
    """
    objetos = []
    for i in range(quantidade):
        angulo = (math.tau / quantidade) * i
        copia = obj.copy()
        copia.data = obj.data.copy()
        bpy.context.collection.objects.link(copia)

        if eixo == "Z":
            copia.rotation_euler.z = angulo
        elif eixo == "Y":
            copia.rotation_euler.y = angulo
        else:
            copia.rotation_euler.x = angulo

        objetos.append(copia)

    if not manter_original:
        bpy.data.objects.remove(obj, do_unlink=True)

    return objetos


def juntar_objetos(objetos: list[bpy.types.Object], nome_final: str = "Conjunto") -> bpy.types.Object:
    """Une vários objetos em um único mesh."""
    bpy.ops.object.select_all(action="DESELECT")
    for o in objetos:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objetos[0]
    bpy.ops.object.join()
    resultado = bpy.context.active_object
    resultado.name = nome_final
    resultado.data.name = nome_final
    return resultado


# ---------------------------------------------------------------------------
# Chanfros e suavização
# ---------------------------------------------------------------------------

def chanfrar_arestas(
    obj: bpy.types.Object,
    seletor,  # função (bm) -> lista de BMEdge, ou string "todas_arestas_circulares"
    largura: float,
    segmentos: int = 2,
) -> bpy.types.Object:
    """
    seletor pode ser:
    - uma função que recebe bm e retorna lista de BMEdge
    - a string "topo", "base", "todas"
    """
    from api.selectors import selecionar_arestas_por_string

    bm = bmesh.new()
    bm.from_mesh(obj.data)

    if callable(seletor):
        arestas = seletor(bm)
    else:
        arestas = selecionar_arestas_por_string(bm, seletor)

    if arestas:
        bmesh.ops.bevel(
            bm,
            geom=arestas,
            offset=largura,
            offset_type="OFFSET",
            segments=segmentos,
            affect="EDGES",
        )

    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return obj


def suavizar_objeto(obj: bpy.types.Object, angulo_graus: float = 30.0) -> bpy.types.Object:
    """Aplica smooth shading com auto-smooth pelo ângulo dado."""
    for face in obj.data.polygons:
        face.use_smooth = True
    obj.data.auto_smooth_angle = math.radians(angulo_graus)
    obj.data.use_auto_smooth = True
    obj.data.update()
    return obj


# ---------------------------------------------------------------------------
# Transformações
# ---------------------------------------------------------------------------

def aplicar_transformacoes(obj: bpy.types.Object) -> bpy.types.Object:
    """Aplica location/rotation/scale para que a malha use coordenadas absolutas."""
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return obj


def posicionar(obj: bpy.types.Object, x=0.0, y=0.0, z=0.0) -> bpy.types.Object:
    obj.location = (x, y, z)
    return obj
