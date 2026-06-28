"""Wiring MCP (FastMCP) sobre a Bridge.

Ferramentas:
- deepseek_status      : diz se a extensao esta conectada.
- pergunta_deepseek    : envia uma tarefa nova e devolve a resposta (one-shot).
- selecionar_modo_deepseek : liga/desliga DeepThink (raciocinio) e Busca.
- configurar_deepseek  : abre chat novo e fixa a 1a mensagem (system prompt).
- consultar_deepseek   : chamada "API" - edita a 2a mensagem e le a resposta.
- inspecionar_deepseek : diagnostico do DOM real (calibracao de seletores).
"""

import asyncio
import os
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from deepseek_bridge.bridge import Bridge

# Bridge unica do processo (singleton). Em stdio ha uma sessao so; em HTTP o
# lifespan roda por sessao, entao subir a bridge precisa ser idempotente: a 1a
# sessao abre o WebSocket na porta, as demais reusam. Ninguem a derruba enquanto
# o processo vive (o processo morrendo fecha tudo).
bridge: Bridge | None = None
_bridge_lock = asyncio.Lock()

# Modos do DeepSeek (so selecionaveis no inicio do chat) -> rotulo visivel.
MODOS = {
    "rapido": "Rápido",
    "especialista": "Especialista",
    "visao": "Visão",
}


def _label_modo(modo: str | None) -> str | None:
    if modo is None:
        return None
    chave = modo.strip().lower()
    if chave in MODOS:
        return MODOS[chave]
    if modo in MODOS.values():
        return modo
    raise ValueError(f"Modo invalido: {modo!r}. Use um de {list(MODOS)}.")


async def ensure_bridge() -> Bridge:
    """Sobe a bridge WebSocket uma unica vez e devolve a instancia (singleton)."""
    global bridge
    if bridge is not None and bridge._server is not None:
        return bridge
    async with _bridge_lock:
        if bridge is None or bridge._server is None:
            host = os.environ.get("DEEPSEEK_WS_HOST", "127.0.0.1")
            port = int(os.environ.get("DEEPSEEK_WS_PORT", "8766"))
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
    http_host = os.environ.get("DEEPSEEK_HTTP_HOST", "127.0.0.1")
    http_port = int(os.environ.get("DEEPSEEK_HTTP_PORT", "8776"))
    mcp = FastMCP("deepseek-web", lifespan=_lifespan, host=http_host, port=http_port)

    @mcp.tool()
    async def deepseek_status() -> str:
        """Diz se a extensao do Chrome esta conectada ao MCP."""
        return "conectada" if (bridge and bridge.connected) else "desconectada"

    @mcp.tool()
    async def pergunta_deepseek(tarefa: str, timeout: int = 180) -> str:
        """Manda uma tarefa nova pro DeepSeek web (one-shot) e devolve a resposta."""
        if bridge is None:
            raise RuntimeError("Bridge nao iniciada.")
        return await bridge.ask(tarefa, timeout=timeout)

    @mcp.tool()
    async def selecionar_modo_deepseek(
        pensamento: bool | None = None, pesquisa: bool | None = None
    ) -> str:
        """Liga/desliga os toggles do DeepSeek (a qualquer momento).

        Args:
            pensamento: True liga 'Pensamento Profundo' (raciocinio), False desliga.
            pesquisa: True liga 'Pesquisa inteligente' (web), False desliga.
                (None = nao mexe no toggle.)
        """
        if bridge is None:
            raise RuntimeError("Bridge nao iniciada.")
        payload = {"pensamento": pensamento, "pesquisa": pesquisa}
        return await bridge.send_cmd("selecionar_modo", payload, timeout=60)

    @mcp.tool()
    async def configurar_deepseek(
        config: str,
        modo: str = "especialista",
        pensamento: bool | None = None,
        pesquisa: bool | None = None,
        timeout: int = 180,
    ) -> str:
        """Abre um chat novo e fixa a 1a mensagem como configuracao (system prompt).

        O modo (rapido/especialista/visao) so pode ser escolhido aqui, no inicio do
        chat (a UI do DeepSeek trava depois da 1a mensagem). Depois, use
        `consultar_deepseek`: ele edita a 2a mensagem a cada vez.

        Args:
            config: a mensagem de configuracao (papel/instrucoes do agente).
            modo: 'rapido', 'especialista' (padrao) ou 'visao'.
            pensamento: opcional, liga 'Pensamento Profundo'.
            pesquisa: opcional, liga 'Pesquisa inteligente'.
            timeout: segundos a esperar pela resposta de confirmacao.
        """
        if bridge is None:
            raise RuntimeError("Bridge nao iniciada.")
        payload = {
            "config": config,
            "modo": _label_modo(modo),
            "pensamento": pensamento,
            "pesquisa": pesquisa,
        }
        return await bridge.send_cmd("configurar", payload, timeout=timeout)

    @mcp.tool()
    async def consultar_deepseek(tarefa: str, timeout: int = 180) -> str:
        """Chamada "API": edita a 2a mensagem do chat e le a resposta regenerada.

        Na primeira vez apos `configurar_deepseek`, cria a mensagem de trabalho;
        nas seguintes, reescreve essa mesma mensagem (o contexto nao cresce).
        """
        if bridge is None:
            raise RuntimeError("Bridge nao iniciada.")
        return await bridge.send_cmd("consultar", {"tarefa": tarefa}, timeout=timeout)

    @mcp.tool()
    async def inspecionar_deepseek(seletor: str = "", max: int = 40) -> str:
        """Diagnostico: descreve o DOM real do DeepSeek pra calibrar seletores.

        Sem `seletor`, devolve um panorama. Com `seletor`, descreve os elementos
        que casam. Suporta sequencia 'A >>> B' (clica A, depois dumpa B) e busca por
        texto ('texto:Especialista'). Uso excepcional: so pra recalibrar os seletores
        quando a interface do DeepSeek mudar, nao pra operacao normal.
        """
        if bridge is None:
            raise RuntimeError("Bridge nao iniciada.")
        return await bridge.send_cmd("inspecionar", {"seletor": seletor, "max": max}, timeout=30)

    return mcp
