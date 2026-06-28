"""Wiring MCP (FastMCP) sobre o controller CDP do Qwen.

Ferramentas (mesma superficie do gemini-web/deepseek-web):
- qwen_status            : diz se o webview do Qwen esta acessivel via CDP.
- pergunta_qwen          : envia uma tarefa nova e devolve a resposta (one-shot).
- selecionar_modelo_qwen : troca o modelo do Qwen.
- configurar_qwen        : abre conversa nova e fixa a 1a mensagem (system prompt).
- consultar_qwen         : chamada "API" - edita a 2a mensagem e le a resposta.
- inspecionar_qwen       : diagnostico de uso excepcional para calibrar seletores.
"""

import os
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from qwen_bridge.controller import Qwen

# Controller unico do processo (mantem a conexao CDP com o webview do Qwen).
qwen: Qwen | None = None


@asynccontextmanager
async def _lifespan(_server):
    global qwen
    host = os.environ.get("QWEN_CDP_HOST", "127.0.0.1")
    port = int(os.environ.get("QWEN_CDP_PORT", "9222"))
    qwen = Qwen(host, port)
    try:
        yield {}
    finally:
        await qwen.cdp.close()
        qwen = None


def build_server():
    mcp = FastMCP("qwen-controller", lifespan=_lifespan)

    @mcp.tool()
    async def qwen_status() -> str:
        """Diz se o Qwen Chat desktop esta acessivel (aberto, logado e com a porta
        de depuracao 9222 ativa)."""
        if qwen is None:
            return "desconectado"
        return await qwen.status()

    @mcp.tool()
    async def pergunta_qwen(tarefa: str, timeout: int = 180) -> str:
        """Manda uma tarefa nova pro Qwen (one-shot) e devolve a resposta.

        Args:
            tarefa: o texto/prompt a enviar ao Qwen.
            timeout: segundos a esperar pela resposta.
        """
        if qwen is None:
            raise RuntimeError("Controller nao iniciado.")
        return await qwen.ask(tarefa, timeout=timeout)

    @mcp.tool()
    async def selecionar_modelo_qwen(modelo: str) -> str:
        """Troca o modelo ativo do Qwen.

        Args:
            modelo: nome (ou prefixo) do modelo, ex.: 'Qwen3.7-Plus', 'Qwen3.7-Max',
                'Qwen3.6-Plus'. Se nao existir, o erro lista os disponiveis.
        """
        if qwen is None:
            raise RuntimeError("Controller nao iniciado.")
        return await qwen.selecionar_modelo(modelo)

    @mcp.tool()
    async def configurar_qwen(
        config: str, modelo: str | None = None, timeout: int = 180
    ) -> str:
        """Abre uma conversa nova e fixa a 1a mensagem como configuracao (system prompt).

        Depois disso, use `consultar_qwen` pra fazer as chamadas: ele edita a 2a
        mensagem a cada vez, mantendo o contexto em config + pergunta atual.

        Args:
            config: a mensagem de configuracao (papel/instrucoes do agente).
            modelo: opcional, escolhe o modelo antes de configurar.
            timeout: segundos a esperar pela resposta de confirmacao.
        """
        if qwen is None:
            raise RuntimeError("Controller nao iniciado.")
        return await qwen.configurar(config, modelo=modelo, timeout=timeout)

    @mcp.tool()
    async def consultar_qwen(tarefa: str, timeout: int = 180) -> str:
        """Chamada "API": edita a 2a mensagem da conversa e le a resposta regenerada.

        Na primeira vez apos `configurar_qwen`, cria a mensagem de trabalho; nas
        seguintes, reescreve essa mesma mensagem (o contexto nao cresce). Requer ter
        chamado `configurar_qwen` antes pra haver a 1a mensagem fixa.

        Args:
            tarefa: o texto/prompt da chamada atual.
            timeout: segundos a esperar pela resposta.
        """
        if qwen is None:
            raise RuntimeError("Controller nao iniciado.")
        return await qwen.consultar(tarefa, timeout=timeout)

    @mcp.tool()
    async def inspecionar_qwen(seletor: str = "", max: int = 40) -> str:
        """Diagnostico: descreve o DOM real do Qwen pra calibrar seletores.

        Sem `seletor`, devolve um panorama (elementos interativos e inventario de
        custom elements). Com `seletor`, descreve os elementos que casam. Ferramenta
        de uso excepcional, so para recalibrar quando a interface do Qwen mudar.

        Args:
            seletor: um seletor CSS pra inspecionar (vazio = panorama geral).
            max: maximo de elementos descritos.
        """
        if qwen is None:
            raise RuntimeError("Controller nao iniciado.")
        return await qwen.inspecionar(seletor, max)

    @mcp.tool()
    async def delegar_para_subagente(
        tarefa: str, subagente_port: int = 8781, timeout: int = 180
    ) -> str:
        """Envia uma tarefa para uma instância secundária do Qwen Chat Desktop (subagente)
        rodando em uma porta HTTP específica e devolve a resposta final.

        Args:
            tarefa: o prompt/instrução a ser executado pelo subagente.
            subagente_port: a porta HTTP da instância do subagente (ex: 8781).
            timeout: segundos a esperar pela resposta.
        """
        host = os.environ.get("QWEN_CDP_HOST", "127.0.0.1")
        # O construtor calcula a porta CDP automaticamente a partir da porta HTTP
        sub_qwen = Qwen(host, http_port=subagente_port)
        
        status = await sub_qwen.status()
        if status != "conectado":
            await sub_qwen.cdp.close()
            raise RuntimeError(f"Subagente na porta HTTP {subagente_port} nao esta acessivel (status: {status}).")
            
        try:
            res = await sub_qwen.ask(tarefa, timeout=timeout)
            return res
        finally:
            await sub_qwen.cdp.close()

    return mcp


def main():
    """Entry point para execução via `uvx --from ... mcp-qwen-controller`."""
    build_server().run()
