"""
Montador central — limpa a cena, chama os geradores e posiciona as peças.
Execute este script via client/send.py ou cole no editor de textos do Blender.
"""

import bpy
import sys
import os

# Adiciona o diretório raiz do projeto ao path para que os imports funcionem
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def limpar_cena():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for col in list(bpy.data.collections):
        bpy.data.collections.remove(col)


def configurar_viewport():
    """Deixa o viewport em Material Preview para ver a geometria bem."""
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            for space in area.spaces:
                if space.type == "VIEW_3D":
                    space.shading.type = "SOLID"
                    space.shading.show_backface_culling = True
                    space.overlay.show_wireframes = False


def montar_sistema_freio(variante: str = "compacto"):
    """Monta o sistema de freio completo e exibe no viewport."""
    from parts.brake_disc import gerar as gerar_disco
    # from parts.caliper import gerar as gerar_pinca      # descomente quando implementado
    # from parts.brake_pads import gerar as gerar_pastilha

    disco = gerar_disco(variante, nome="DiscoDFreio")
    disco.location = (0, 0, 0)

    # pinca = gerar_pinca(variante)
    # pinca.location = (dim["raio_ext"] + 0.01, 0, 0)

    # Vista no viewport
    bpy.ops.object.select_all(action="DESELECT")
    disco.select_set(True)
    bpy.context.view_layer.objects.active = disco
    bpy.ops.view3d.view_selected(use_all_regions=False)

    return {"disco": disco.name}


if __name__ == "__main__":
    limpar_cena()
    configurar_viewport()
    objetos = montar_sistema_freio("compacto")
    print(f"Montagem concluída: {objetos}")
