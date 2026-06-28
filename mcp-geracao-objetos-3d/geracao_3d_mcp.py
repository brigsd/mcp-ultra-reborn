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

    Esta ferramenta tenta se comunicar com a ponte GUI do Blender na porta 19000.
    Caso o Blender esteja fechado, ela automaticamente executa o processo em
    modo HEADLESS (em segundo plano), gerando o modelo STL e renderizando as 4 vistas.

    Args:
        peca: Nome do arquivo em parts/ (ex: 'brake_disc', 'arvore_lowpoly') ou 'assembler' para rodar a montagem.
        parametros_json: String JSON contendo os parâmetros a passar para o gerador (ex: '{"variante": "esportivo"}')
    """
    # Valida parâmetros JSON
    try:
        params = json.loads(parametros_json) if parametros_json else {}
    except Exception as e:
        return json.dumps({"sucesso": False, "erro": f"JSON de parametros invalido: {e}"})

    part_name = peca.lower().strip()

    # Script dinâmico que limpa, importa, executa e valida na ponte GUI
    codigo_gui = f"""
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
    if "{part_name}" == "assembler":
        from assembler import montar_sistema_freio
        montar_sistema_freio()
        rel_texto = "Montagem concluida."
        obj = bpy.context.active_object
    else:
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

    # 1. Tenta rodar via Bridge (GUI) se ela estiver ativa
    bridge_ativa = False
    try:
        bridge_ativa = testar_conexao()
    except Exception:
        pass

    if bridge_ativa:
        try:
            res = enviar_script(codigo_gui)
            if res.sucesso:
                pasta_imagens = ROOT / "references" / "imagens" / part_name
                pasta_imagens.mkdir(parents=True, exist_ok=True)
                caminhos_salvos = res.salvar_screenshots(str(pasta_imagens) + "/")
                retorno = {
                    "sucesso": True,
                    "modo": "bridge (Blender GUI ativo)",
                    "resumo": res.resumo(),
                    "screenshots_salvos": caminhos_salvos,
                    "caminho_pasta_screenshots": str(pasta_imagens)
                }
                return json.dumps(retorno, indent=2, ensure_ascii=False)
        except Exception:
            pass

    # 2. Se a bridge falhar ou não estiver ativa, executa em modo HEADLESS
    blender_path = r"C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe"
    if not os.path.exists(blender_path):
        import shutil
        blender_path = shutil.which("blender") or "blender"

    import tempfile
    import shutil
    
    pasta_imagens = ROOT / "references" / "imagens" / part_name
    pasta_imagens.mkdir(parents=True, exist_ok=True)
    
    fd_script, path_script = tempfile.mkstemp(suffix="_run.py", text=True)
    path_stl = str(pasta_imagens / "temp_output.stl")
    os.close(fd_script)
    
    script_headless = f"""
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

try:
    if "{part_name}" == "assembler":
        from assembler import montar_sistema_freio
        montar_sistema_freio()
    else:
        from parts.{part_name} import gerar_e_validar
        params = json.loads({repr(json.dumps(params))})
        obj, rel_texto = gerar_e_validar(**params)
        
    # Exportar para STL
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.wm.stl_export(filepath={repr(path_stl)}, export_selected_objects=True, apply_modifiers=True)
    print("LARP_HEADLESS_OK")
except Exception as e:
    print("LARP_HEADLESS_ERR:", str(e))
    traceback.print_exc()
"""
    
    try:
        Path(path_script).write_text(script_headless, encoding="utf-8")
        
        # Executa geração no Blender headless redirecionando stdout/stderr para log temporário
        fd_gen_log, path_gen_log = tempfile.mkstemp(suffix="_gen.log", text=True)
        os.close(fd_gen_log)
        
        with open(path_gen_log, "w", encoding="utf-8") as f_log:
            proc_gen = subprocess.run([blender_path, "--background", "--python", path_script], stdout=f_log, stderr=f_log, timeout=90)
            
        gen_output = Path(path_gen_log).read_text(encoding="utf-8", errors="ignore")
        if os.path.exists(path_gen_log):
            os.unlink(path_gen_log)
        
        # Remove script temporário
        if os.path.exists(path_script):
            os.unlink(path_script)
            
        if "LARP_HEADLESS_OK" not in gen_output:
            return json.dumps({
                "sucesso": False,
                "erro": f"Falha na geracao headless do Blender:\nLogs:\n{gen_output}"
            }, indent=2)
            
        # Executa renderização headless redirecionando stdout/stderr para log temporário
        render_script = ROOT / "prototype" / "render_views.py"
        fd_render_log, path_render_log = tempfile.mkstemp(suffix="_render.log", text=True)
        os.close(fd_render_log)
        
        with open(path_render_log, "w", encoding="utf-8") as f_log:
            proc_render = subprocess.run([blender_path, "--background", "--python", str(render_script), "--", path_stl], stdout=f_log, stderr=f_log, timeout=90)
            
        render_output = Path(path_render_log).read_text(encoding="utf-8", errors="ignore")
        if os.path.exists(path_render_log):
            os.unlink(path_render_log)
        
        # Remove o STL temporário
        if os.path.exists(path_stl):
            os.unlink(path_stl)
            
        if "LARP: FIM" not in render_output:
            return json.dumps({
                "sucesso": False,
                "erro": f"Falha na renderizacao headless do Blender:\nLogs:\n{render_output}"
            }, indent=2)
            
        # Move os 4 screenshots da pasta temporária para a definitiva
        src_dir = ROOT / "prototype" / "views" / "temp_output"
        caminhos_salvos = []
        for vista in ["perspectiva", "frente", "lado", "topo"]:
            src_file = src_dir / f"{vista}.png"
            dest_file = pasta_imagens / f"{vista}.png"
            if src_file.exists():
                if dest_file.exists():
                    os.unlink(str(dest_file))
                shutil.move(str(src_file), str(dest_file))
                caminhos_salvos.append(str(dest_file))
                
        if src_dir.exists():
            shutil.rmtree(src_dir)
            
        return json.dumps({
            "sucesso": True,
            "modo": "headless (Blender executado em background)",
            "resumo": f"Peca '{peca}' gerada e renderizada com sucesso (headless).",
            "screenshots_salvos": [str(p) for p in caminhos_salvos],
            "caminho_pasta_screenshots": str(pasta_imagens)
        }, indent=2, ensure_ascii=False)
        
    except Exception as e:
        return json.dumps({
            "sucesso": False,
            "erro": f"Falha na execucao headless: {e}"
        }, indent=2)


if __name__ == "__main__":
    mcp.run()
