"""
Parte "ver" da fatia: roda no Blender FECHADO, importa a malha gerada e
renderiza 4 vistas no Cycles pra arquivo. Fecha o ciclo gerar->conferir->ver.

Rodar:
  "C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe" \
      --background --python prototype/render_views.py
"""

import bpy
import os
import sys
import math
from mathutils import Vector

AQUI = os.path.dirname(os.path.abspath(__file__))
# malha opcional passada após "--"; default = blob orgânico
_extra = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
STL = _extra[0] if _extra else os.path.join(AQUI, "out_blob.stl")
SAIDA = os.path.join(AQUI, "views", os.path.splitext(os.path.basename(STL))[0])
os.makedirs(SAIDA, exist_ok=True)


def limpar_cena():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def importar_stl(caminho):
    antes = set(bpy.data.objects)
    try:
        bpy.ops.wm.stl_import(filepath=caminho)        # Blender 4.x/5.x
    except Exception:
        bpy.ops.import_mesh.stl(filepath=caminho)       # legado
    novos = [o for o in bpy.data.objects if o not in antes]
    return novos[0]


def material_argila(obj):
    mat = bpy.data.materials.new("argila")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.6, 0.62, 0.66, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.7
    obj.data.materials.append(mat)


def bbox_mundo(obj):
    cantos = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    mn = Vector((min(c.x for c in cantos), min(c.y for c in cantos), min(c.z for c in cantos)))
    mx = Vector((max(c.x for c in cantos), max(c.y for c in cantos), max(c.z for c in cantos)))
    return mn, mx, (mn + mx) / 2, (mx - mn)


def olhar_para(cam, alvo):
    d = alvo - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def render_vista(nome, cam, centro, dim, perspectiva=False):
    maxd = max(dim)
    if perspectiva:
        cam.data.type = "PERSP"
        cam.data.lens = 50
    else:
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = maxd * 1.4
    olhar_para(cam, centro)
    bpy.context.scene.render.filepath = os.path.join(SAIDA, f"{nome}.png")
    bpy.ops.render.render(write_still=True)
    print(f"LARP: render {nome} -> {nome}.png")


def main():
    limpar_cena()
    obj = importar_stl(STL)
    material_argila(obj)
    mn, mx, centro, dim = bbox_mundo(obj)
    maxd = max(dim)
    print(f"LARP: importado {obj.name}  dim={[round(d,3) for d in dim]}")

    # luz
    sol = bpy.data.lights.new("sol", "SUN")
    sol.energy = 4.0
    sol_obj = bpy.data.objects.new("sol", sol)
    bpy.context.collection.objects.link(sol_obj)
    sol_obj.rotation_euler = (math.radians(50), math.radians(15), math.radians(40))
    bpy.context.scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.05, 0.06, 1)
    bpy.context.scene.world.node_tree.nodes["Background"].inputs[1].default_value = 0.4

    # camera
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    bpy.context.collection.objects.link(cam)
    bpy.context.scene.camera = cam

    # render settings
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 24
    sc.render.resolution_x = 700
    sc.render.resolution_y = 700
    sc.render.image_settings.file_format = "PNG"
    try:
        sc.view_settings.view_transform = "Standard"
    except Exception:
        pass

    d = maxd * 3
    vistas = [
        ("perspectiva", centro + Vector(( d,  -d,  d * 0.8)), True),
        ("frente",      centro + Vector(( 0,  -d,  0)),       False),
        ("lado",        centro + Vector(( d,   0,  0)),       False),
        ("topo",        centro + Vector(( 0,   0,  d)),       False),
    ]
    for nome, pos, persp in vistas:
        cam.location = pos
        render_vista(nome, cam, centro, dim, perspectiva=persp)

    print("LARP: FIM")


if __name__ == "__main__":
    main()
