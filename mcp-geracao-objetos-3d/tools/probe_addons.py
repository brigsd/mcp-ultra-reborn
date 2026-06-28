"""
Sonda de scriptabilidade headless de addons do Blender.
Rodar com:  blender --background --python tools/probe_addons.py
Descobre quais addons-alvo existem, ativa, e tenta acionar o operador principal
de cada um SEM interface — pra confirmar se dá pra reaproveitar no modo automático.
"""
import bpy, addon_utils

def log(*a):
    print("LARP:", *a)

log("BLENDER", bpy.app.version_string)

ALVOS = {
    "3dprint":   ["print3d", "print 3d", "3d print"],
    "bolt":      ["bolt"],
    "sapling":   ["sapling"],
    "extra_obj": ["extra objects", "extra_objects", "extra mesh"],
    "measureit": ["measureit", "measure"],
    "looptools": ["looptools", "loop tools"],
}

mods = list(addon_utils.modules())
log("total de modulos de addon disponiveis:", len(mods))

found = {}
for key, kws in ALVOS.items():
    for m in mods:
        nm = m.__name__
        bl = getattr(m, "bl_info", {}) or {}
        lbl = bl.get("name", "")
        if any(k in nm.lower() or k in lbl.lower() for k in kws):
            found[key] = nm
            log("ACHOU", key, "->", nm, "|", lbl)
            break
    else:
        log("FALTANDO", key)

def enable(mod):
    try:
        addon_utils.enable(mod, default_set=True, persistent=True)
        return True
    except Exception as e:
        log("ativar FALHOU", mod, repr(e))
        return False

# limpar cena
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# BoltFactory
if "bolt" in found and enable(found["bolt"]):
    try:
        bpy.ops.mesh.bolt_add()
        o = bpy.context.active_object
        log("BOLT ok ->", o.name, len(o.data.vertices), "verts")
    except Exception as e:
        log("BOLT operador FALHOU", repr(e))

# Extra Objects -> engrenagem
if "extra_obj" in found and enable(found["extra_obj"]):
    ok = False
    for opid in ("mesh.primitive_gear", "mesh.primitive_worm_gear"):
        try:
            op = eval("bpy.ops." + opid)
            op()
            log("GEAR ok via", opid, "->", bpy.context.active_object.name)
            ok = True
            break
        except Exception as e:
            log("GEAR tentativa", opid, "falhou", repr(e))
    if not ok:
        log("GEAR nenhum operador funcionou")

# Sapling -> arvore
if "sapling" in found and enable(found["sapling"]):
    try:
        bpy.ops.curve.tree_add()
        log("SAPLING ok ->", bpy.context.active_object.name)
    except Exception as e:
        log("SAPLING operador FALHOU", repr(e))

# 3D Print Toolbox -> checagem de malha
if "3dprint" in found and enable(found["3dprint"]):
    try:
        bpy.ops.object.select_all(action='DESELECT')
        bpy.ops.mesh.primitive_cube_add()
        bpy.ops.object.mode_set(mode='OBJECT')
        ran = []
        for opid in ("mesh.print3d_check_all", "mesh.print3d_check_solid",
                     "mesh.print3d_check_intersect"):
            try:
                eval("bpy.ops." + opid)()
                ran.append(opid)
            except Exception as e:
                log("3DPRINT", opid, "falhou", repr(e))
        log("3DPRINT operadores que rodaram headless:", ran)
    except Exception as e:
        log("3DPRINT bloco FALHOU", repr(e))

# MeasureIt / LoopTools -> só confirmar ativacao
if "measureit" in found:
    log("MEASUREIT ativa headless:", enable(found["measureit"]))
if "looptools" in found:
    log("LOOPTOOLS ativa headless:", enable(found["looptools"]))

log("FIM")
