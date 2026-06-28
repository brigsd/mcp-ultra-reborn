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

    path_stl = str(pasta_imagens / "temp_output.stl")

    # Arquivo temporário para o script (delete=False para evitar lock no Windows)
    fd_script, path_script = tempfile.mkstemp(suffix="_run.py", text=True)
    os.close(fd_script)  # fecha o handle antes de escrever via Path
    
    # Monta o script headless usando importlib para carregar o arquivo diretamente por caminho
    # (evita problemas de resolução de módulo em Blender headless)
    part_file_path = str(ROOT / "parts" / f"{part_name}.py").replace("\\", "/")
    params_json_str = json.dumps(params)

    script_headless = f"""
import sys
import os
import bpy
import json
import traceback
import importlib.util

ROOT = r"{str(ROOT).replace('\\', '/')}"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# 1. Limpar a cena
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()
for col in list(bpy.data.collections):
    bpy.data.collections.remove(col)

try:
    params = json.loads({repr(params_json_str)})

    if "{part_name}" == "assembler":
        from assembler import montar_sistema_freio
        montar_sistema_freio()
    else:
        # Carrega o arquivo do gerador diretamente por caminho (robusto em headless)
        spec = importlib.util.spec_from_file_location("_gerador", r"{part_file_path}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        obj, rel_texto = mod.gerar_e_validar(**params)

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
        
        # Debug: copia o script para um caminho fixo para inspeção
        debug_script_path = ROOT / "references" / "imagens" / part_name / "debug_last_script.py"
        debug_script_path.parent.mkdir(parents=True, exist_ok=True)
        import shutil as _shutil
        _shutil.copy2(path_script, str(debug_script_path))
        
        # Executa geração no Blender headless
        # stdin=DEVNULL evita que o Blender fique aguardando input sem TTY no Windows
        proc_gen = subprocess.Popen(
            [blender_path, "--background", "--python", path_script],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        try:
            gen_output_bytes, _ = proc_gen.communicate(timeout=180)
            gen_output = gen_output_bytes.decode("utf-8", errors="ignore")
        except subprocess.TimeoutExpired:
            proc_gen.kill()
            proc_gen.communicate()
            if os.path.exists(path_script):
                os.unlink(path_script)
            return json.dumps({"sucesso": False, "erro": "Timeout na geracao headless (>180s)"}, indent=2)
        
        # Remove script temporário
        if os.path.exists(path_script):
            os.unlink(path_script)
            
        if "LARP_HEADLESS_OK" not in gen_output:
            return json.dumps({
                "sucesso": False,
                "erro": f"Falha na geracao headless do Blender:\nLogs:\n{gen_output}"
            }, indent=2)
            
        # Executa renderização headless com Popen + communicate (seguro no Windows)
        render_script = ROOT / "prototype" / "render_views.py"
        proc_render = subprocess.Popen(
            [blender_path, "--background", "--python", str(render_script), "--", path_stl],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        try:
            render_output_bytes, _ = proc_render.communicate(timeout=180)
            render_output = render_output_bytes.decode("utf-8", errors="ignore")
        except subprocess.TimeoutExpired:
            proc_render.kill()
            proc_render.communicate()
            return json.dumps({"sucesso": False, "erro": "Timeout na renderizacao headless (>180s)"}, indent=2)
        
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


def _blender_executable() -> str:
    blender_path = r"C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe"
    if not os.path.exists(blender_path):
        import shutil
        blender_path = shutil.which("blender") or "blender"
    return blender_path


def _run_vehicle_headless(action: str, spec_json: str, qualidade: str = "draft") -> str:
    import tempfile
    import time
    import uuid

    run_id = f"{action}_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    output_root = Path(os.environ.get("VEHICLE_OUTPUT_ROOT", r"C:\tmp\mcp-ultra-vehicle-runs"))
    output_dir = output_root / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "renders").mkdir(parents=True, exist_ok=True)

    fd_script, path_script = tempfile.mkstemp(suffix="_vehicle_run.py", text=True)
    os.close(fd_script)

    script = f"""
import json
import sys
import traceback

ROOT = r"{str(ROOT).replace('\\', '/')}"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    from vehicle_workspace.orchestration.pipeline import run_vehicle_action
    report = run_vehicle_action(
        action={action!r},
        spec_json={spec_json!r},
        output_dir={str(output_dir).replace('\\', '/')!r},
        quality={qualidade!r},
    )
    print("VEHICLE_JSON_START")
    print(json.dumps(report, ensure_ascii=False))
    print("VEHICLE_JSON_END")
except Exception as exc:
    print("VEHICLE_JSON_START")
    print(json.dumps({{
        "success": False,
        "error": str(exc),
        "traceback": traceback.format_exc(),
        "paths": {{"output_dir": {str(output_dir).replace('\\', '/')!r}}}
    }}, ensure_ascii=False))
    print("VEHICLE_JSON_END")
"""

    try:
        Path(path_script).write_text(script, encoding="utf-8")
        proc = subprocess.Popen(
            [_blender_executable(), "--background", "--python", path_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        try:
            output_bytes, _ = proc.communicate(timeout=240)
            output = output_bytes.decode("utf-8", errors="ignore")
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            return json.dumps({
                "success": False,
                "error": "Timeout na geracao headless de veiculo (>240s)",
                "paths": {"output_dir": str(output_dir)}
            }, indent=2, ensure_ascii=False)
    finally:
        if os.path.exists(path_script):
            os.unlink(path_script)

    start = output.find("VEHICLE_JSON_START")
    end = output.find("VEHICLE_JSON_END")
    if start == -1 or end == -1:
        return json.dumps({
            "success": False,
            "error": "Blender nao retornou marcador VEHICLE_JSON.",
            "blender_log": output[-6000:],
            "paths": {"output_dir": str(output_dir)}
        }, indent=2, ensure_ascii=False)

    payload = output[start + len("VEHICLE_JSON_START"):end].strip()
    try:
        parsed = json.loads(payload)
        return json.dumps(parsed, indent=2, ensure_ascii=False)
    except Exception:
        return json.dumps({
            "success": False,
            "error": "Falha ao parsear JSON retornado pelo runner de veiculo.",
            "raw": payload,
            "blender_log": output[-6000:],
            "paths": {"output_dir": str(output_dir)}
        }, indent=2, ensure_ascii=False)


@mcp.tool()
async def vehicle_listar_arquetipos() -> str:
    """Lista os arquetipos de veiculo disponiveis no workspace procedural."""
    archetype_dir = ROOT / "vehicle_workspace" / "archetypes"
    result = []
    for path in sorted(archetype_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            result.append({
                "id": data.get("id", path.stem),
                "label": data.get("label", path.stem),
                "arquivo": str(path),
            })
        except Exception as exc:
            result.append({"id": path.stem, "erro": str(exc), "arquivo": str(path)})
    return json.dumps({"arquetipos": result}, indent=2, ensure_ascii=False)


@mcp.tool()
async def vehicle_criar_spec(prompt: str = "", referencia_path: str = "", medidas_json: str = "{}", overrides_json: str = "{}") -> str:
    """Cria e normaliza um VehicleSpec a partir de prompt, medidas e overrides.

    Args:
        prompt: Descricao curta do veiculo desejado.
        referencia_path: Caminho opcional para imagem/blueprint de referencia.
        medidas_json: JSON com medidas em mm, ex: {"length": 4750, "width": 2020}.
        overrides_json: JSON opcional para sobrescrever campos completos da spec.
    """
    try:
        from vehicle_workspace.vehicle.schema import create_spec
        medidas = json.loads(medidas_json) if medidas_json else {}
        overrides = json.loads(overrides_json) if overrides_json else {}
        spec = create_spec(prompt=prompt, referencia_path=referencia_path, medidas=medidas, overrides=overrides)
        return json.dumps(spec, indent=2, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)}, indent=2, ensure_ascii=False)


@mcp.tool()
async def vehicle_gerar_rig(spec_json: str, qualidade: str = "draft") -> str:
    """Gera um rig dimensional headless para um VehicleSpec e renderiza vistas diagnosticas."""
    return _run_vehicle_headless("rig", spec_json, qualidade)


@mcp.tool()
async def vehicle_gerar_blockout(spec_json: str, qualidade: str = "draft") -> str:
    """Gera um blockout veicular headless com carroceria simples, rodas e auditoria basica."""
    return _run_vehicle_headless("blockout", spec_json, qualidade)


@mcp.tool()
async def vehicle_gerar_modelo(spec_json: str, qualidade: str = "draft") -> str:
    """Gera o modelo veicular MVP. Nesta versao, equivale ao blockout refinavel."""
    return _run_vehicle_headless("model", spec_json, qualidade)


@mcp.tool()
async def vehicle_pipeline(prompt: str, referencia_path: str = "", medidas_json: str = "{}", budget_json: str = "{}") -> str:
    """Fluxo composto (fase 6). Cria a spec e gera o modelo. Se `referencia_path`
    for o PNG da VISTA LATERAL de um blueprint, roda o loop de iteracao
    automatica: gera -> compara silhueta -> ajusta parametros da spec -> repete,
    ate o budget. Sem referencia, faz uma geracao unica em qualidade standard.

    Args:
        prompt: Descricao do veiculo (define o arquetipo).
        referencia_path: PNG recortado da vista lateral do blueprint (opcional).
        medidas_json: JSON com medidas em mm.
        budget_json: JSON do budget, ex.: {"max_iterations": 3, "target_shape_iou": 0.92}.
    """
    try:
        from vehicle_workspace.vehicle.schema import create_spec
        from vehicle_workspace.orchestration.budgets import Budget
        from vehicle_workspace.orchestration.iteration import iterate
        from vehicle_workspace.vision.compare import compare_side, public_report

        medidas = json.loads(medidas_json) if medidas_json else {}
        spec = create_spec(prompt=prompt, referencia_path=referencia_path, medidas=medidas)
        length = float(spec["dimensions"]["length"])

        if not referencia_path or not os.path.exists(referencia_path):
            return _run_vehicle_headless("model", json.dumps(spec, ensure_ascii=False), "standard")

        budget = Budget.from_json(json.loads(budget_json) if budget_json else {})

        def gen_and_cmp(s):
            rep_json = _run_vehicle_headless("model", json.dumps(s, ensure_ascii=False), "standard")
            rep = json.loads(rep_json)
            if not rep.get("success"):
                raise RuntimeError(rep.get("error", "falha na geracao headless"))
            sil = _find_silhouette(rep.get("paths", {}).get("output_dir", ""))
            if not sil:
                raise RuntimeError("silhueta lateral nao foi gerada")
            comp = public_report(compare_side(sil, referencia_path, length))
            return rep, comp

        result = iterate(spec, gen_and_cmp, budget)
        return json.dumps({"success": True, "blueprint": referencia_path, **result}, indent=2, ensure_ascii=False)
    except Exception as exc:
        import traceback
        return json.dumps({"success": False, "error": str(exc), "traceback": traceback.format_exc()}, indent=2, ensure_ascii=False)


@mcp.tool()
async def vehicle_iterar(spec_json: str, compare_json: str) -> str:
    """Passo unico de correcao (fase 6): le uma comparacao de silhueta e devolve
    a spec com o bloco `tuning` ajustado. Corrige PARAMETROS, nunca a malha.

    Args:
        spec_json: VehicleSpec atual (JSON).
        compare_json: Saida de vehicle_comparar_blueprint (precisa de shape_regions).
    """
    try:
        from vehicle_workspace.orchestration.iteration import propose_tuning
        from vehicle_workspace.vehicle.schema import load_spec
        spec = load_spec(spec_json)
        comp = json.loads(compare_json) if compare_json else {}
        new_tuning = propose_tuning(spec, comp)
        out = dict(spec)
        out.pop("_meters", None)
        out["tuning"] = new_tuning
        return json.dumps({"success": True, "tuning": new_tuning, "spec": out}, indent=2, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)}, indent=2, ensure_ascii=False)


@mcp.tool()
async def vehicle_auditar(modelo_id: str) -> str:
    """Le o report.json de uma execucao de veiculo e retorna a auditoria salva.

    Args:
        modelo_id: Pasta da execucao ou caminho direto para report.json.
    """
    try:
        from vehicle_workspace.orchestration.pipeline import read_report
        report = read_report(modelo_id)
        return json.dumps({
            "success": True,
            "modelo_id": modelo_id,
            "audit": report.get("audit", {}),
            "paths": report.get("paths", {}),
        }, indent=2, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc), "modelo_id": modelo_id}, indent=2, ensure_ascii=False)


@mcp.tool()
async def vehicle_renderizar_vistas(modelo_id: str) -> str:
    """Lista os renders ja gerados para uma execucao de veiculo.

    Args:
        modelo_id: Pasta da execucao ou caminho direto para report.json.
    """
    try:
        from vehicle_workspace.orchestration.pipeline import read_report
        report = read_report(modelo_id)
        return json.dumps({
            "success": True,
            "modelo_id": modelo_id,
            "renders": report.get("renders", {}),
            "paths": report.get("paths", {}),
        }, indent=2, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc), "modelo_id": modelo_id}, indent=2, ensure_ascii=False)


def _find_silhouette(modelo_id: str) -> str:
    """Localiza a silhueta lateral de uma execucao de modelo."""
    p = Path(modelo_id)
    candidates = [
        p / "renders" / "silhouette_lado.png",
        p / "silhouette_lado.png",
    ]
    if p.suffix == ".json":  # apontaram report.json
        candidates.insert(0, p.parent / "renders" / "silhouette_lado.png")
    for c in candidates:
        if c.exists():
            return str(c)
    return ""


@mcp.tool()
async def vehicle_calibrar_blueprint(imagem_path: str, medidas_json: str) -> str:
    """Calibra UMA vista de blueprint: detecta a silhueta, mede a bbox em pixels
    e converte para mm/pixel usando uma medida conhecida.

    Args:
        imagem_path: PNG de UMA vista (ex.: recorte da vista lateral).
        medidas_json: JSON com a medida conhecida, ex.:
            {"axis": "length", "value_mm": 4750}  (axis: length|height)
    """
    try:
        from vehicle_workspace.vision.silhouette import (
            bbox, foreground_mask, load_gray,
        )
        med = json.loads(medidas_json) if medidas_json else {}
        axis = med.get("axis", "length")
        value_mm = float(med.get("value_mm", 0) or 0)
        if value_mm <= 0:
            return json.dumps({"success": False, "error": "medidas_json precisa de value_mm > 0."}, indent=2)
        gray = load_gray(imagem_path)
        mask = foreground_mask(gray, kind="auto")
        bb = bbox(mask)
        if bb is None:
            return json.dumps({"success": False, "error": "Nenhuma silhueta detectada na imagem."}, indent=2)
        x0, y0, x1, y1 = bb
        span_px = (x1 - x0) if axis == "length" else (y1 - y0)
        mm_per_px = value_mm / max(span_px, 1)
        return json.dumps({
            "success": True,
            "imagem_path": imagem_path,
            "bbox_px": [x0, y0, x1, y1],
            "axis": axis,
            "value_mm": value_mm,
            "mm_per_px": round(mm_per_px, 4),
            "implied_length_mm": round((x1 - x0) * mm_per_px, 1),
            "implied_height_mm": round((y1 - y0) * mm_per_px, 1),
        }, indent=2, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc), "imagem_path": imagem_path}, indent=2, ensure_ascii=False)


@mcp.tool()
async def vehicle_comparar_blueprint(modelo_id: str, blueprint_lateral_path: str, length_mm: float = 0.0) -> str:
    """Compara a silhueta lateral do modelo gerado com a vista lateral de um
    blueprint. Calibra ambos pelo comprimento, foca o perfil superior, faz
    auto-flip e devolve IoU + erro por regiao. Salva um PNG de overlay.

    Requer que o modelo tenha sido gerado com qualidade standard/high (gera a
    silhueta). length_mm: comprimento real do veiculo em mm (se 0, le do report).

    Args:
        modelo_id: Pasta da execucao do modelo (ou report.json).
        blueprint_lateral_path: PNG recortado da VISTA LATERAL do blueprint.
        length_mm: Comprimento total conhecido, em mm.
    """
    try:
        from vehicle_workspace.orchestration.pipeline import read_report
        from vehicle_workspace.vision.compare import compare_side, public_report
        from vehicle_workspace.vision.overlay import draw_overlay

        our_sil = _find_silhouette(modelo_id)
        if not our_sil:
            return json.dumps({
                "success": False,
                "error": "Silhueta do modelo nao encontrada. Gere com qualidade 'standard'.",
                "modelo_id": modelo_id,
            }, indent=2, ensure_ascii=False)
        if not os.path.exists(blueprint_lateral_path):
            return json.dumps({"success": False, "error": f"Blueprint nao encontrado: {blueprint_lateral_path}"}, indent=2)

        length = float(length_mm or 0)
        if length <= 0:
            try:
                rep = read_report(modelo_id)
                length = float(rep["spec"]["dimensions"]["length"])
            except Exception:
                return json.dumps({"success": False, "error": "length_mm nao informado e nao foi possivel ler do report."}, indent=2)

        rep = compare_side(our_sil, blueprint_lateral_path, length)
        out_dir = Path(our_sil).parent
        overlay_path = str(out_dir / "overlay_blueprint.png")
        try:
            draw_overlay(rep, overlay_path)
        except Exception as exc:
            overlay_path = f"(overlay falhou: {exc})"

        result = public_report(rep)
        result.update({
            "success": True,
            "modelo_id": modelo_id,
            "length_mm": length,
            "our_silhouette": our_sil,
            "blueprint": blueprint_lateral_path,
            "overlay": overlay_path,
        })
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as exc:
        import traceback
        return json.dumps({"success": False, "error": str(exc), "traceback": traceback.format_exc()}, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
