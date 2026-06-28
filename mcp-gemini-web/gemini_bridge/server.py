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
    # Garante a bridge de pe (idempotente). Nao a derruba no teardown: e singleton
    # do processo e pode ser compartilhada por varias sessoes (HTTP).
    await ensure_bridge()
    yield {}


def build_server():
    # host/port usados so no transporte HTTP (streamable-http); no stdio sao ignorados.
    http_host = os.environ.get("GEMINI_HTTP_HOST", "127.0.0.1")
    http_port = int(os.environ.get("GEMINI_HTTP_PORT", "8775"))
    mcp = FastMCP("gemini-web", lifespan=_lifespan, host=http_host, port=http_port)

    @mcp.tool()
    async def gemini_status() -> str:
        """Diz se a extensao do Chrome esta conectada ao MCP."""
        return "conectada" if (bridge and bridge.connected) else "desconectada"

    @mcp.tool()
    async def pergunta_gemini(tarefa: str, timeout: int = 180) -> str:
        """Manda uma tarefa nova pro Gemini web (one-shot) e devolve a resposta.

        Args:
            tarefa: o texto/prompt a colar no Gemini.
            timeout: segundos a esperar pela resposta.
        """
        if bridge is None:
            raise RuntimeError("Bridge nao iniciada.")
        return await bridge.ask(tarefa, timeout=timeout)

    @mcp.tool()
    async def selecionar_modelo_gemini(
        modelo: str, raciocinio: str | None = None
    ) -> str:
        """Seleciona o modelo do Gemini e, opcionalmente, o nivel de raciocinio.

        Args:
            modelo: 'flash-lite' (3.1 Flash-Lite), 'flash' (3.5 Flash) ou
                'pro' (3.1 Pro).
            raciocinio: 'padrao' ou 'estendido' (opcional; nem todo modelo tem).
        """
        if bridge is None:
            raise RuntimeError("Bridge nao iniciada.")
        payload = {
            "modelo": _label_modelo(modelo),
            "raciocinio": _label_raciocinio(raciocinio),
        }
        return await bridge.send_cmd("selecionar_modelo", payload, timeout=60)

    @mcp.tool()
    async def configurar_gemini(
        config: str,
        modelo: str | None = None,
        raciocinio: str | None = None,
        timeout: int = 180,
    ) -> str:
        """Abre um chat novo e fixa a 1a mensagem como configuracao (system prompt).

        Depois disso, use `consultar_gemini` pra fazer as chamadas: ele edita a 2a
        mensagem a cada vez, mantendo o contexto em config + pergunta atual.

        Args:
            config: a mensagem de configuracao (papel/instrucoes do agente).
            modelo: opcional, escolhe o modelo antes de configurar.
            raciocinio: opcional, 'padrao' ou 'estendido'.
            timeout: segundos a esperar pela resposta de confirmacao.
        """
        if bridge is None:
            raise RuntimeError("Bridge nao iniciada.")
        payload = {
            "config": config,
            "modelo": _label_modelo(modelo),
            "raciocinio": _label_raciocinio(raciocinio),
        }
        return await bridge.send_cmd("configurar", payload, timeout=timeout)

    @mcp.tool()
    async def inspecionar_gemini(seletor: str = "", max: int = 40) -> str:
        """Diagnostico: descreve o DOM real do Gemini pra calibrar seletores.

        Sem `seletor`, devolve um panorama (elementos interativos com aria-label e
        inventario de custom elements). Com `seletor`, descreve os elementos que
        casam. Ferramenta de diagnostico, de uso excepcional: so pra recalibrar os
        seletores quando a interface do Gemini mudar, nao pra operacao normal.

        Args:
            seletor: um seletor CSS pra inspecionar (vazio = panorama geral).
            max: maximo de elementos descritos.
        """
        if bridge is None:
            raise RuntimeError("Bridge nao iniciada.")
        payload = {"seletor": seletor, "max": max}
        return await bridge.send_cmd("inspecionar", payload, timeout=30)

    @mcp.tool()
    async def consultar_gemini(tarefa: str, timeout: int = 180) -> str:
        """Chamada "API": edita a 2a mensagem do chat e le a resposta regenerada.

        Na primeira vez apos `configurar_gemini`, cria a mensagem de trabalho; nas
        seguintes, reescreve essa mesma mensagem (o contexto nao cresce). Requer
        ter chamado `configurar_gemini` antes pra haver a 1a mensagem fixa.

        Args:
            tarefa: o texto/prompt da chamada atual.
            timeout: segundos a esperar pela resposta.
        """
        if bridge is None:
            raise RuntimeError("Bridge nao iniciada.")
        return await bridge.send_cmd("consultar", {"tarefa": tarefa}, timeout=timeout)

    @mcp.tool()
    async def listar_conversas_gemini() -> str:
        """Lista as conversas recentes da barra lateral do Gemini.

        Devolve um JSON: [{"id": "<id>", "titulo": "<titulo>"}, ...]. O `id` e o
        identificador estavel da conversa, o MESMO que aparece na URL
        (gemini.google.com/app/<id>); guarde-o e use em `abrir_conversa_gemini`.

        Abre a barra lateral sozinho se estiver fechada. A lista do Gemini e
        virtualizada (scroll infinito), entao isto devolve as conversas
        atualmente carregadas (as mais recentes), nao o historico inteiro.
        Pressupoe a secao "Recentes" expandida. Retorno enxuto de proposito:
        use isto, nao o `inspecionar_gemini` (que despeja o DOM e custa caro).
        """
        if bridge is None:
            raise RuntimeError("Bridge nao iniciada.")
        return await bridge.send_cmd("listar_conversas", {}, timeout=30)

    @mcp.tool()
    async def abrir_conversa_gemini(conversa_id: str) -> str:
        """Abre uma conversa existente do Gemini pelo id e devolve a URL aberta.

        `conversa_id` e o identificador da URL (gemini.google.com/app/<id>),
        tambem retornado por `listar_conversas_gemini`. Pegue o id de la; nao
        ha como abrir por titulo (buscar por texto no DOM derruba a extensao).

        Garante a barra lateral aberta, clica no link da conversa e confirma
        pela URL, que volta como recibo. Operacao barata: nao despeja DOM. Se o
        id nao estiver na lista carregada (virtualizada), falha avisando; nesse
        caso liste de novo ou role a barra.
        """
        if bridge is None:
            raise RuntimeError("Bridge nao iniciada.")
        return await bridge.send_cmd(
            "abrir_conversa", {"conversa_id": conversa_id}, timeout=30
        )

    @mcp.tool()
    async def editar_arquivo_gemini(
        caminho: str, instrucao: str, timeout: int = 300
    ) -> str:
        """Delega ao Gemini a edicao de um arquivo, sem o conteudo passar pelo
        contexto do host (economia de tokens).

        O servidor le o arquivo do disco, pede ao Gemini que aplique `instrucao`
        e devolva o arquivo INTEIRO, e grava o resultado por cima. Nem o conteudo
        original nem o editado voltam pro host: o retorno e so um status curto.
        Para revisar: COMMITE o arquivo antes de editar e rode `git diff
        <caminho>` depois (mais os testes). O git e a rede de seguranca; se o
        resultado ficar ruim, reverta com `git restore <caminho>`.

        Limites: o Gemini ve so este arquivo, nao o resto do projeto, entao
        mudancas que dependem de outros arquivos podem sair erradas (os testes
        pegam). Arquivo muito grande pode truncar na saida do Gemini; o status
        avisa se o arquivo encolheu demais. Use para mudancas locais a um arquivo.

        Args:
            caminho: caminho absoluto do arquivo existente a editar.
            instrucao: o que mudar, em linguagem natural.
            timeout: segundos a esperar a resposta do Gemini (padrao 300).
        """
        if bridge is None:
            raise RuntimeError("Bridge nao iniciada.")
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
        resp = await bridge.ask(prompt, timeout=timeout)
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

    return mcp
