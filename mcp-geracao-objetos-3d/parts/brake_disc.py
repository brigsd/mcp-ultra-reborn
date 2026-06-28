"""
Disco de freio ventilado — exemplo de peça usando a api/ e catalog/.
Demonstra o padrão que a IA deve seguir para criar peças realistas.
"""

import bpy
from catalog.dimensions import DISCO_FREIO
from api.primitives import criar_disco, criar_cilindro_oco
from api.operations import furar_radial, chanfrar_arestas, suavizar_objeto, aplicar_transformacoes
from api.selectors import selecionar_arestas_circulares_em_z
from api.validators import validar_objeto, relatorio_para_texto


def gerar(variante: str = "compacto", nome: str = "DiscoDFreio") -> bpy.types.Object:
    """
    Gera um disco de freio ventilado com furos de ventilação e chanfros.

    Args:
        variante: "compacto", "medio" ou "esportivo"
        nome: nome do objeto no Blender

    Returns:
        Objeto Blender pronto para uso no assembler.
    """
    dim = DISCO_FREIO[variante]

    # 1. Anel base (corpo do disco)
    disco = criar_cilindro_oco(
        raio_ext=dim["raio_ext"],
        raio_int=dim["raio_int"],
        altura=dim["espessura"],
        segmentos=128,
        nome=nome,
    )

    # 2. Furos de ventilação radiais
    disco = furar_radial(
        obj=disco,
        quantidade=dim["qtd_furos_ventilacao"],
        raio_orbital=dim["raio_orbital_furos"],
        raio_furo=dim["raio_furo_ventilacao"],
        profundidade=dim["espessura"],
    )

    # 3. Chanfros nas bordas do topo e base (reduz arestas vivas, mais realismo)
    chanfrar_arestas(disco, "circulares_topo", largura=0.0015, segmentos=2)
    chanfrar_arestas(disco, "circulares_base", largura=0.0015, segmentos=2)

    # 4. Suavização
    suavizar_objeto(disco, angulo_graus=60.0)

    # 5. Aplicar transformações
    aplicar_transformacoes(disco)

    return disco


def gerar_e_validar(variante: str = "compacto") -> tuple[bpy.types.Object | None, str]:
    """Gera o disco e valida. Retorna (objeto, relatorio_texto)."""
    obj = gerar(variante)
    relatorio = validar_objeto(obj)
    texto = relatorio_para_texto(relatorio)
    if not relatorio["valido"]:
        print(f"[brake_disc] AVISO: validação falhou para variante '{variante}'")
    return obj, texto
