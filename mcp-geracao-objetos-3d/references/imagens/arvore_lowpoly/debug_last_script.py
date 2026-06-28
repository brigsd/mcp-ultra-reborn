
import sys
import os
import bpy
import json
import traceback
import importlib.util

ROOT = r"C:/Users/tiago/Desktop/mcp-ultra-reborn/mcp-geracao-objetos-3d"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# 1. Limpar a cena
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()
for col in list(bpy.data.collections):
    bpy.data.collections.remove(col)

try:
    params = json.loads('{}')

    if "arvore_lowpoly" == "assembler":
        from assembler import montar_sistema_freio
        montar_sistema_freio()
    else:
        # Carrega o arquivo do gerador diretamente por caminho (robusto em headless)
        spec = importlib.util.spec_from_file_location("_gerador", r"C:/Users/tiago/Desktop/mcp-ultra-reborn/mcp-geracao-objetos-3d/parts/arvore_lowpoly.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        obj, rel_texto = mod.gerar_e_validar(**params)

    # Exportar para STL
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.wm.stl_export(filepath='C:\\Users\\tiago\\Desktop\\mcp-ultra-reborn\\mcp-geracao-objetos-3d\\references\\imagens\\arvore_lowpoly\\temp_output.stl', export_selected_objects=True, apply_modifiers=True)
    print("LARP_HEADLESS_OK")
except Exception as e:
    print("LARP_HEADLESS_ERR:", str(e))
    traceback.print_exc()
