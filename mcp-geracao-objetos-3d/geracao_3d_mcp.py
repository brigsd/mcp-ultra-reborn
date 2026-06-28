import sys
import os
import json
import subprocess
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# Configura CWD e PYTHONPATH para incluir a pasta do MCP
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

mcp = FastMCP("mcp-geracao-objetos-3d")

# Importa o cliente de comunicação com o Blender
try:
    from client.send import testar_conexao, enviar_script, descrever_cena
except ImportError:
    # Fallback se import falhar por conta do path
    sys.path.append(str(ROOT / "client"))
    from client.send import testar_conexao, enviar_script, descrever_cena


@mcp.tool()
async def status_blender_bridge() -> str:
    """Verifica se o Blender está rodando e com o addon bridge conectado na porta 19000.

    Chame esta ferramenta para garantir que a ponte de modelagem 3D está ativa
    antes de tentar gerar ou visualizar objetos 3D no Blender.
    """
    try:
        conectado = testar_conexao()
        return "conectada" if conectado else "desconectada (inicie o Blender e ative a MCP 3D Bridge no painel lateral)"
    except Exception as e:
        return f"desconectada: {e}"


@mcp.tool()
async def obter_dimensoes_peca(peca: str = "") -> str:
    """Retorna as dimensões oficiais e proporções de engenharia cadastradas no catálogo.

    Use para consultar limites, espessuras e diâmetros realistas de peças antes de modelá-las.
    Se peca for vazia, lista todas as categorias disponíveis.

    Args:
        peca: Nome do componente (ex: 'DISCO_FREIO', 'PINCA_FREIO', 'ROLAMENTO', 'PARAFUSO_METRICO', 'ARO_RODA', 'MOLA_HELICOIDAL')
    """
    sys.path.insert(0, str(ROOT))
    import catalog.dimensions as dimensions

    todas = {
        "DISCO_FREIO": dimensions.DISCO_FREIO,
        "PINCA_FREIO": dimensions.PINCA_FREIO,
        "ROLAMENTO": dimensions.ROLAMENTO,
        "PARAFUSO_METRICO": dimensions.PARAFUSO_METRICO,
        "ARO_RODA": dimensions.ARO_RODA,
        "MOLA_HELICOIDAL": dimensions.MOLA_HELICOIDAL,
    }

    if not peca:
        return json.dumps({
            "mensagem": "Especifique uma peca para ver as dimensoes. Categorias disponiveis:",
            "categorias": list(todas.keys())
        }, indent=2)

    chave = peca.upper().strip()
    if chave in todas:
        return json.dumps(todas[chave], indent=2)
    else:
        # Busca aproximada/case-insensitive
        for k, v in todas.items():
            if k.lower() == peca.lower().strip():
                return json.dumps(v, indent=2)
        return json.dumps({
            "erro": f"Peca '{peca}' nao encontrada no catalogo.",
            "categorias_disponiveis": list(todas.keys())
        }, indent=2)


@mcp.tool()
async def listar_referencias_locais(peca: str) -> str:
    """Retorna as referências locais (meta.json, PNGs de patentes, PDFs) disponíveis para a peça.

    Use para obter a ficha técnica de design, chanfros obrigatórios e proporções
    antes de começar a gerar o script de modelagem.

    Args:
        peca: Nome da pasta da peça (ex: 'bearing', 'brake_disc', 'caliper')
    """
    pasta = ROOT / "references" / peca.lower().strip()
    if not pasta.exists():
        return json.dumps({
            "erro": f"Diretorio de referencias para '{peca}' nao existe em references/.",
            "pecas_existentes": [p.name for p in (ROOT / "references").iterdir() if p.is_dir()]
        }, indent=2)

    resultado = {
        "caminho_diretorio": str(pasta),
        "meta": None,
        "arquivos": []
    }

    meta_file = pasta / "meta.json"
    if meta_file.exists():
        try:
            resultado["meta"] = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception as e:
            resultado["meta"] = f"Erro ao ler meta.json: {e}"

    for f in pasta.iterdir():
        if f.is_file() and f.name != "meta.json":
            resultado["arquivos"].append({
                "nome": f.name,
                "tamanho_kb": round(f.stat().st_size / 1024, 1),
                "caminho_absoluto": str(f)
            })

    return json.dumps(resultado, indent=2, ensure_ascii=False)


@mcp.tool()
async def baixar_referencia_3d(peca: str, forcar: bool = False) -> str:
    """Executa o script CLI de download de referências e extração de patentes.

    Use quando o diretório local de uma peça não tiver as imagens de patente/catálogo.
    Requer PyMuPDF instalado para converter PDFs em PNGs.

    Args:
        peca: Nome da peça no catálogo de fontes (ex: 'brake_disc', 'bearing')
        forcar: Se True, força o re-download e extração mesmo se já existirem no cache
    """
    script_path = ROOT / "tools" / "fetch_references.py"
    cmd = [sys.executable, str(script_path), peca]
    if forcar:
        cmd.append("--force")

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
        if proc.returncode == 0:
            return f"Sucesso!\n\nSAÍDA:\n{proc.stdout}"
        else:
            return f"Erro na execucao (codigo {proc.returncode}):\n\nERRO:\n{proc.stderr}\n\nSAÍDA:\n{proc.stdout}"
    except Exception as e:
        return f"Falha ao executar fetch_references.py: {e}"


@mcp.tool()
async def gerar_modelo_3d(peca: str, parametros_json: str = "{}") -> str:
    """Envia código ou parâmetros ao Blender para gerar, medir e capturar 4 vistas do modelo 3D.

    Esta ferramenta limpa a cena do Blender, importa o gerador correspondente a peça
    da pasta parts/ (ou roda o assembler se peca == 'assembler') e retorna o relatório
    geométrico final junto com os metadados das vistas renderizadas.

    Args:
        peca: Nome do arquivo em parts/ (ex: 'brake_disc') ou 'assembler' para rodar a montagem completa.
        parametros_json: String JSON contendo os parâmetros a passar para o gerador (ex: '{"variante": "esportivo"}')
    """
    # Valida parâmetros JSON
    try:
        params = json.loads(parametros_json) if parametros_json else {}
    except Exception as e:
        return json.dumps({"sucesso": False, "erro": f"JSON de parametros invalido: {e}"})

    # Caso seja montagem completa
    if peca.lower().strip() == "assembler":
        script_file = ROOT / "assembler.py"
        if not script_file.exists():
            return json.dumps({"sucesso": False, "erro": "Arquivo assembler.py nao encontrado."})
        codigo = script_file.read_text(encoding="utf-8")
    else:
        # Caso seja uma peça específica
        part_name = peca.lower().strip()
        part_file = ROOT / "parts" / f"{part_name}.py"
        if not part_file.exists():
            return json.dumps({
                "sucesso": False,
                "erro": f"Gerador para a peca '{peca}' nao encontrado em parts/.",
                "pecas_disponiveis": [p.stem for p in (ROOT / "parts").glob("*.py") if p.stem != "__init__"]
            })

        # Script dinâmico que limpa, importa, executa e valida
        codigo = f"""
import sys
import os
import bpy
import json
import traceback

ROOT = r"{str(ROOT).replace('\\', '/')}"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# 1. Limpar a cena
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()
for col in list(bpy.data.collections):
    bpy.data.collections.remove(col)

# 2. Configurar shading do viewport para visualizacao
for area in bpy.context.screen.areas:
    if area.type == "VIEW_3D":
        for space in area.spaces:
            if space.type == "VIEW_3D":
                space.shading.type = "SOLID"
                space.shading.show_backface_culling = True

# 3. Executar o gerador
try:
    from parts.{part_name} import gerar_e_validar
    params = json.loads({repr(json.dumps(params))})
    obj, rel_texto = gerar_e_validar(**params)
    
    # Foca o objeto para o screenshot
    if obj:
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.view3d.view_selected(use_all_regions=False)
        
    print("LARPERIAN_JSON_START")
    print(json.dumps({{"sucesso": True, "relatorio": rel_texto, "objeto": obj.name if obj else None}}))
    print("LARPERIAN_JSON_END")
except Exception as e:
    print("LARPERIAN_JSON_START")
    print(json.dumps({{"sucesso": False, "erro": str(e), "traceback": traceback.format_exc()}}))
    print("LARPERIAN_JSON_END")
"""

    # Envia o script ao Blender via bridge HTTP cliente
    try:
        res = enviar_script(codigo)
        if not res.sucesso:
            return json.dumps({
                "sucesso": False,
                "erro": f"Erro retornado pelo Blender: {res.erro}"
            }, indent=2)

        # Salva localmente os 4 screenshots tirados pelo Blender na pasta de imagens da peça
        # para que o agente ou usuário possa visualizá-los
        pasta_imagens = ROOT / "references" / "imagens" / peca.lower().strip()
        pasta_imagens.mkdir(parents=True, exist_ok=True)
        caminhos_salvos = res.salvar_screenshots(str(pasta_imagens) + "/")

        # Retorna o resumo da modelagem com o caminho dos screenshots salvos no disco
        retorno = {
            "sucesso": True,
            "resumo": res.resumo(),
            "screenshots_salvos": caminhos_salvos,
            "caminho_pasta_screenshots": str(pasta_imagens)
        }
        return json.dumps(retorno, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "sucesso": False,
            "erro": f"Erro de comunicacao com a Larperian Bridge do Blender: {e}. Verifique se o Blender esta aberto e a ponte ativa."
        }, indent=2)


if __name__ == "__main__":
    mcp.run()
