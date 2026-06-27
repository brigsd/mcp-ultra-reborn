"""Wiring MCP (FastMCP) sobre a Bridge.

Ferramentas:
- gemini_status            : diz se a extensao esta conectada.
- pergunta_gemini          : envia uma tarefa nova e devolve a resposta (one-shot).
- selecionar_modelo_gemini : escolhe modelo + nivel de raciocinio.
- configurar_gemini        : abre chat novo e fixa a 1a mensagem (system prompt).
- consultar_gemini         : chamada "API" - edita a 2a mensagem e le a resposta.
"""

import os
from contextlib import asynccontextmanager

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

# Bridge unica do processo. Iniciada no lifespan (precisa do loop asyncio rodando).
bridge: Bridge | None = None


@asynccontextmanager
async def _lifespan(_server):
    global bridge
    host = os.environ.get("GEMINI_WS_HOST", "127.0.0.1")
    port = int(os.environ.get("GEMINI_WS_PORT", "8765"))
    bridge = Bridge(host, port)
    await bridge.start()
    try:
        yield {}
    finally:
        await bridge.stop()
        bridge = None


def build_server():
    mcp = FastMCP("gemini-web", lifespan=_lifespan)

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

    return mcp
