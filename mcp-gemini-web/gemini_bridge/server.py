"""Wiring MCP (FastMCP) sobre a Bridge.

Ferramentas:
- gemini_status            : diz se a extensao esta conectada.
- pergunta_gemini          : envia uma tarefa nova e devolve a resposta (one-shot).
- selecionar_modelo_gemini : escolhe modelo + nivel de raciocinio.
- configurar_gemini        : abre chat novo e fixa a 1a mensagem (system prompt).
- consultar_gemini         : chamada "API" - edita a 2a mensagem e le a resposta.
- listar_conversas_gemini  : lista as conversas recentes da barra (titulo + id).
- abrir_conversa_gemini    : abre uma conversa pelo id e devolve a URL aberta.
- editar_arquivo_gemini    : Gemini edita um arquivo no disco e o servidor grava
                             (conteudo nao passa pelo host); revise com git diff.
"""

import asyncio
import difflib
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from gemini_bridge.bridge import Bridge

# Chaves curtas -> rotulo visivel no menu do Gemini (a extensao casa por texto).
MODELOS = {
    "flash-lite": "3.1 Flash-Lite",
    "flash": "3.5 Flash",
    "pro": "3.1 Pro",
}
RACIOCINIO = {
    "padrao": "Padrão",
    "estendido": "Estendido",
}


def _label_modelo(modelo: str | None) -> str | None:
    if modelo is None:
        return None
    chave = modelo.strip().lower()
    if chave in MODELOS:
        return MODELOS[chave]
    if modelo in MODELOS.values():  # ja veio o rotulo cheio
        return modelo
    raise ValueError(f"Modelo invalido: {modelo!r}. Use um de {list(MODELOS)}.")


def _label_raciocinio(raciocinio: str | None) -> str | None:
    if raciocinio is None:
        return None
    chave = raciocinio.strip().lower()
    if chave in RACIOCINIO:
        return RACIOCINIO[chave]
    if raciocinio in RACIOCINIO.values():
        return raciocinio
    raise ValueError(
        f"Raciocinio invalido: {raciocinio!r}. Use 'padrao' ou 'estendido'."
    )


def _extrai_codigo(resp: str) -> str:
    """Extrai o conteudo do 1o bloco cercado por crases triplas na resposta.

    Se nao houver bloco cercado, usa a resposta inteira. Garante \\n no fim.
    """
    m = re.search(r"```[^\n]*\n(.*?)```", resp, re.DOTALL)
    corpo = m.group(1) if m else resp.strip()
    return corpo.rstrip("\n") + "\n"

# Bridge unica do processo (singleton). Em stdio ha uma sessao so; em HTTP o
# lifespan roda por sessao, entao subir a bridge precisa ser idempotente: a 1a
# sessao abre o WebSocket na porta, as demais reusam a mesma instancia. Ninguem
# a derruba enquanto o processo vive (o processo morrendo fecha tudo).
bridge: Bridge | None = None
_bridge_lock = asyncio.Lock()


async def ensure_bridge() -> Bridge:
    """Sobe a bridge WebSocket uma unica vez e devolve a instancia (singleton)."""
    global bridge
    if bridge is not None and bridge._server is not None:
        return bridge
    async with _bridge_lock:
        if bridge is None or bridge._server is None:
            host = os.environ.get("GEMINI_WS_HOST", "127.0.0.1")
            port = int(os.environ.get("GEMINI_WS_PORT", "8765"))
            b = Bridge(host, port)
            await b.start()
            bridge = b
    return bridge


@asynccontextmanager
async def _lifespan(_server):
    # Tenta subir a bridge no startup. Se falhar (ex.: porta ainda ocupada por
    # processo anterior), o servidor sobe mesmo assim e as ferramentas ficam
    # disponiveis — a bridge vai tentar de novo na primeira chamada a ensure_bridge().
    try:
        await ensure_bridge()
    except Exception as exc:
        import sys
        print(f"[gemini-web] bridge nao iniciou no startup: {exc}", file=sys.stderr)
    yield {}


def build_server():
    # host/port usados so no transporte HTTP (streamable-http); no stdio sao ignorados.
    http_host = os.environ.get("GEMINI_HTTP_HOST", "127.0.0.1")
    http_port = int(os.environ.get("GEMINI_HTTP_PORT", "8775"))
    mcp = FastMCP("gemini-web", lifespan=_lifespan, host=http_host, port=http_port)

    @mcp.tool()
    async def gemini_status() -> str:
        """Verifica se a extensao do Chrome esta conectada ao servidor MCP.

        Chame PRIMEIRO antes de qualquer outra ferramenta. Se retornar
        'desconectada', a aba do Gemini nao esta aberta ou a extensao nao esta
        carregada — nenhuma outra ferramenta vai funcionar ate isso ser resolvido.
        Nao tente enviar tarefas com a extensao desconectada.
        """
        return "conectada" if (bridge and bridge.connected) else "desconectada"

    @mcp.tool()
    async def reconectar_gemini(ambos: bool = False) -> str:
        """Inicia o Chrome com a extensao do gemini-web carregada.

        Se `ambos` for True, carrega tambem a extensao do deepseek-web.
        Abre as respectivas abas automaticamente.

        Args:
            ambos: True para carregar e abrir tambem o deepseek-web.
        """
        import subprocess

        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        gemini_ext = os.path.join(repo_root, "mcp-gemini-web", "extension")
        
        if ambos:
            deepseek_ext = os.path.join(repo_root, "mcp-deepseek-web", "extension")
            exts = f"{gemini_ext},{deepseek_ext}"
            urls = '"https://gemini.google.com" "https://chat.deepseek.com"'
        else:
            exts = gemini_ext
            urls = '"https://gemini.google.com"'

        cmd = f'cmd.exe /c start chrome --load-extension="{exts}" {urls}'
        subprocess.Popen(cmd, shell=True)
        return f"Comando enviado: {cmd}. Feche todas as janelas do Chrome se nao conectar."


    @mcp.tool()
    async def pergunta_gemini(tarefa: str, timeout: int = 180) -> str:
        """Envia uma tarefa avulsa ao Gemini e devolve a resposta (one-shot).

        Use para perguntas isoladas que nao precisam de contexto fixo.
        Para uso repetido com o mesmo papel/instrucoes, prefira o par
        configurar_gemini + consultar_gemini (contexto estavel, sem historico
        acumulado). Para processar arquivos sem gastar tokens do host, use
        processar_arquivo_gemini ou editar_arquivo_gemini.

        Args:
            tarefa: o texto completo do prompt a enviar ao Gemini.
            timeout: segundos a aguardar a resposta (padrao 180).
        """
        b = await ensure_bridge()
        return await b.ask(tarefa, timeout=timeout)

    @mcp.tool()
    async def selecionar_modelo_gemini(
        modelo: str, raciocinio: str | None = None
    ) -> str:
        """Troca o modelo ativo do Gemini e, opcionalmente, o nivel de raciocinio.

        Use quando quiser mudar o modelo sem abrir um chat novo (ex.: trocou de
        flash para pro no meio de uma sessao). Se estiver abrindo um chat novo,
        prefira passar modelo/raciocinio diretamente no configurar_gemini.

        Modelos disponiveis:
            'flash-lite' → Gemini 3.1 Flash-Lite  (rapido, economico)
            'flash'      → Gemini 3.5 Flash        (equilibrado, recomendado)
            'pro'        → Gemini 3.1 Pro           (mais capaz, mais lento)

        Niveis de raciocinio (nem todo modelo suporta):
            'padrao'    → raciocinio normal
            'estendido' → raciocinio mais profundo (mais lento)

        Args:
            modelo: 'flash-lite', 'flash' ou 'pro'.
            raciocinio: 'padrao' ou 'estendido' (opcional).
        """
        b = await ensure_bridge()
        payload = {
            "modelo": _label_modelo(modelo),
            "raciocinio": _label_raciocinio(raciocinio),
        }
        return await b.send_cmd("selecionar_modelo", payload, timeout=60)

    @mcp.tool()
    async def configurar_gemini(
        config: str,
        modelo: str | None = None,
        raciocinio: str | None = None,
        timeout: int = 180,
    ) -> str:
        """Abre um chat novo no Gemini e fixa a 1a mensagem como system prompt.

        DEVE ser chamado antes de consultar_gemini. Abre um chat limpo, escolhe
        o modelo/raciocinio e cola `config` como a primeira mensagem (o papel e
        as instrucoes do agente). A partir dai, use consultar_gemini para cada
        chamada: ele edita a 2a mensagem e regenera, mantendo o contexto em
        'config + tarefa atual' sem acumular historico.

        Nao use para tarefas avulsas — use pergunta_gemini. Nao use para
        processar arquivos — use processar_arquivo_gemini ou editar_arquivo_gemini.

        Args:
            config: instrucoes do agente (system prompt fixo para toda a sessao).
            modelo: 'flash-lite', 'flash' ou 'pro' (opcional; mantem o atual se omitido).
            raciocinio: 'padrao' ou 'estendido' (opcional).
            timeout: segundos a aguardar confirmacao (padrao 180).
        """
        b = await ensure_bridge()
        payload = {
            "config": config,
            "modelo": _label_modelo(modelo),
            "raciocinio": _label_raciocinio(raciocinio),
        }
        return await b.send_cmd("configurar", payload, timeout=timeout)

    @mcp.tool()
    async def inspecionar_gemini(seletor: str = "", max: int = 40) -> str:
        """DIAGNOSTICO APENAS — descreve o DOM do Gemini para recalibrar seletores.

        Use SOMENTE quando outra ferramenta parou de funcionar apos uma atualizacao
        do Google e precisar redescobrir os seletores CSS no extension/content.js.
        Nao use na operacao normal: despeja o DOM inteiro e e caro. Para listar
        conversas, use listar_conversas_gemini. Para qualquer outra operacao,
        use as ferramentas especificas.

        Args:
            seletor: seletor CSS a inspecionar (vazio = panorama geral do DOM).
            max: maximo de elementos retornados (padrao 40).
        """
        b = await ensure_bridge()
        payload = {"seletor": seletor, "max": max}
        return await b.send_cmd("inspecionar", payload, timeout=30)

    @mcp.tool()
    async def consultar_gemini(tarefa: str, timeout: int = 180) -> str:
        """Envia uma tarefa ao Gemini dentro de uma sessao configurada (estilo API).

        REQUER que configurar_gemini tenha sido chamado antes nesta sessao.
        Edita a 2a mensagem do chat (na primeira vez cria, nas seguintes reescreve)
        e le a resposta regenerada. O contexto permanece em 'config + tarefa atual':
        nao acumula historico, cada chamada e independente.

        Para tarefas avulsas sem sessao: use pergunta_gemini.
        Para processar arquivos: use processar_arquivo_gemini ou editar_arquivo_gemini.

        Args:
            tarefa: o prompt da chamada atual (substitui a mensagem anterior).
            timeout: segundos a aguardar a resposta (padrao 180).
        """
        b = await ensure_bridge()
        return await b.send_cmd("consultar", {"tarefa": tarefa}, timeout=timeout)

    @mcp.tool()
    async def listar_conversas_gemini() -> str:
        """Lista as conversas recentes do Gemini (barra lateral).

        Retorna JSON: [{"id": "<id>", "titulo": "<titulo>"}, ...].
        O 'id' e o identificador da URL (gemini.google.com/app/<id>) — use-o
        em abrir_conversa_gemini para reabrir a conversa depois.

        Limitacao: a lista e virtualizada (scroll infinito), entao retorna apenas
        as conversas ja carregadas na barra (as mais recentes). Se a conversa que
        voce quer nao aparecer, role a barra e chame de novo.

        Nao use inspecionar_gemini para listar conversas — e muito mais caro.
        """
        b = await ensure_bridge()
        return await b.send_cmd("listar_conversas", {}, timeout=30)

    @mcp.tool()
    async def abrir_conversa_gemini(conversa_id: str) -> str:
        """Abre uma conversa existente do Gemini pelo id e confirma a URL.

        Use o 'id' retornado por listar_conversas_gemini. Nao ha como abrir por
        titulo — a identificacao e sempre pelo id da URL. Se o id nao estiver
        carregado na barra lateral (lista virtualizada), liste de novo ou role a
        barra antes de tentar.

        Args:
            conversa_id: o id da conversa (parte final da URL: gemini.google.com/app/<id>).
        """
        b = await ensure_bridge()
        return await b.send_cmd(
            "abrir_conversa", {"conversa_id": conversa_id}, timeout=30
        )

    @mcp.tool()
    async def editar_arquivo_gemini(
        caminho: str, instrucao: str, timeout: int = 300
    ) -> str:
        """Pede ao Gemini que edite um arquivo e grava o resultado NO MESMO arquivo.

        O conteudo do arquivo nunca passa pelo contexto do host (zero tokens).
        O servidor le o arquivo, manda pro Gemini com a instrucao, e sobrescreve
        o arquivo com o resultado. O retorno e apenas um status curto (linhas antes
        e depois). Use quando quer modificar o arquivo existente no lugar.

        Para gerar uma versao alternativa SEM alterar o original, use
        processar_arquivo_gemini (grava em arquivo de destino separado e retorna
        o diff automaticamente).

        IMPORTANTE: commite o arquivo antes de editar. Se o resultado for ruim,
        reverta com: git restore <caminho>

        Limites: o Gemini ve so este arquivo, sem contexto do resto do projeto.
        Arquivos muito grandes podem truncar; o status avisa se encolheu demais.

        Args:
            caminho: caminho absoluto do arquivo a editar (sera sobrescrito).
            instrucao: o que mudar, em linguagem natural.
            timeout: segundos a aguardar o Gemini (padrao 300).
        """
        b = await ensure_bridge()
        p = Path(caminho)
        if not p.is_file():
            raise RuntimeError(f"Arquivo nao encontrado: {caminho}")
        original = p.read_text(encoding="utf-8")
        prompt = (
            "Voce e um editor de codigo preciso. Abaixo esta o conteudo COMPLETO "
            f"do arquivo `{p.name}`. Aplique exatamente esta mudanca:\n\n"
            f"{instrucao}\n\n"
            "Devolva o arquivo INTEIRO ja editado, dentro de UM unico bloco de "
            "codigo cercado por crases triplas. Nao escreva nada antes nem depois "
            "do bloco, nao explique, nao omita partes com reticencias nem com "
            "comentarios do tipo 'resto igual'. Preserve tudo o que nao muda.\n\n"
            f"```\n{original}\n```"
        )
        resp = await b.ask(prompt, timeout=timeout)
        novo = _extrai_codigo(resp)
        if not novo.strip():
            raise RuntimeError("Gemini devolveu vazio; nada foi gravado.")
        if novo == original:
            return f"sem mudancas: {caminho}"
        p.write_text(novo, encoding="utf-8")
        n_old = original.count("\n") + 1
        n_new = novo.count("\n") + 1
        aviso = ""
        if n_new < n_old * 0.6:
            aviso = " ATENCAO: encolheu bastante, confira o diff (possivel truncamento)."
        return (
            f"gravado: {caminho} ({n_old} -> {n_new} linhas)."
            f"{aviso} Revise com: git diff -- {caminho}"
        )

    @mcp.tool()
    async def processar_arquivo_gemini(
        arquivo_origem: str,
        instrucao: str,
        arquivo_destino: str,
        timeout: int = 300,
    ) -> str:
        """Le um arquivo, processa com o Gemini e grava o resultado num arquivo NOVO.

        Fluxo completamente server-side: o conteudo do arquivo nunca passa pelo
        contexto do host (zero tokens). O servidor le o arquivo de origem, manda
        pro Gemini com a instrucao, grava o resultado no arquivo de destino, calcula
        o diff entre os dois e retorna APENAS o diff — nao os arquivos completos.

        Use para: reescrever, expandir, traduzir, resumir ou transformar documentos.
        O arquivo de origem nunca e alterado.

        Diferenca de editar_arquivo_gemini: aqui o original e preservado e o
        resultado vai para um arquivo separado. O diff e calculado e retornado
        automaticamente — o host nao precisa ler nenhum dos dois arquivos.

        Args:
            arquivo_origem:  caminho absoluto do arquivo a processar (nao alterado).
            instrucao:       o que o Gemini deve fazer com o conteudo.
            arquivo_destino: caminho absoluto do novo arquivo a criar com o resultado.
            timeout:         segundos a aguardar o Gemini (padrao 300).
        """
        b = await ensure_bridge()
        p_origem = Path(arquivo_origem)
        if not p_origem.is_file():
            raise RuntimeError(f"Arquivo nao encontrado: {arquivo_origem}")
        conteudo = p_origem.read_text(encoding="utf-8")
        prompt = (
            f"Voce recebeu o arquivo `{p_origem.name}`. Aplique esta instrucao:\n\n"
            f"{instrucao}\n\n"
            "Devolva o resultado COMPLETO dentro de UM unico bloco de codigo "
            "cercado por crases triplas. Nao escreva nada antes nem depois do bloco.\n\n"
            f"```\n{conteudo}\n```"
        )
        resp = await b.ask(prompt, timeout=timeout)
        resultado = _extrai_codigo(resp)
        if not resultado.strip():
            raise RuntimeError("Gemini devolveu vazio; nada foi gravado.")
        p_destino = Path(arquivo_destino)
        p_destino.parent.mkdir(parents=True, exist_ok=True)
        p_destino.write_text(resultado, encoding="utf-8")
        n_orig = conteudo.count("\n") + 1
        n_dest = resultado.count("\n") + 1
        diff_linhas = list(difflib.unified_diff(
            conteudo.splitlines(keepends=True),
            resultado.splitlines(keepends=True),
            fromfile=p_origem.name,
            tofile=p_destino.name,
            n=2,
        ))
        diff_texto = "".join(diff_linhas[:200])  # cap: primeiras 200 linhas do diff
        truncado = " [diff truncado em 200 linhas]" if len(diff_linhas) > 200 else ""
        return (
            f"gravado: {arquivo_destino} ({n_orig} -> {n_dest} linhas){truncado}\n\n"
            f"--- diff ---\n{diff_texto if diff_texto else '(sem diferencas)'}"
        )

    return mcp
