"""Orquestracao do Qwen sobre o CDP.

Espelha a logica que, no gemini-web/deepseek-web, vivia no content.js da extensao,
mas aqui ela roda em Python: preenche campos e le o DOM via Runtime.evaluate, e
clica com evento confiavel via Input.dispatchMouseEvent. A espera pela resposta e
por estabilizacao do texto (sem um sinal de "fim" confiavel na UI do Qwen).
"""

import asyncio
import json
from pathlib import Path

from qwen_bridge.cdp import CDP

_DRIVER = (Path(__file__).parent / "driver.js").read_text(encoding="utf-8")

IDLE = 2.5          # segundos de texto estavel para considerar a resposta pronta
POLL = 1.0          # intervalo entre leituras durante a espera


class Qwen:
    def __init__(self, host="127.0.0.1", port=9222):
        self.cdp = CDP(host, port)

    async def _drv(self, expr):
        """Avalia uma chamada do driver (window.__qwen.<fn>) no webview."""
        return await self.cdp.evaluate(_DRIVER + ";\n" + expr)

    def _call(self, fn, *args):
        args = ", ".join(json.dumps(a) for a in args)
        return f"window.__qwen.{fn}({args})"

    # ---- status ----

    async def status(self):
        if not self.cdp.reachable():
            return "desconectado"
        try:
            await self._drv(self._call("info"))
            return "conectado"
        except Exception:
            return "desconectado"

    # ---- espera por estabilizacao ----

    async def _aguardar(self, comecou, timeout):
        """Espera o texto da ultima resposta estabilizar. `comecou(snap, elapsed)` decide
        quando a geracao deste turno comecou, para nao aceitar texto de um turno anterior.
        O texto so e nao-vazio na fase de resposta (o pensamento devolve ""), e o sinal
        `pronto` (rodape com botao de copiar) permite confirmar o fim mais rapido."""
        loop = asyncio.get_running_loop()
        inicio = loop.time()
        last = None
        estavel_desde = None
        started = False
        while loop.time() - inicio < timeout:
            snap = await self._drv(self._call("snapshot")) or {}
            txt = snap.get("texto") or ""
            if not started and comecou(snap, loop.time() - inicio):
                started = True
            # So retorna com o sinal de fim (rodape/botao de copiar): durante o
            # pensamento nao ha rodape, evitando devolver resposta a meio caminho.
            if txt and started and snap.get("pronto"):
                if txt == last:
                    if estavel_desde is None:
                        estavel_desde = loop.time()
                    if loop.time() - estavel_desde >= 1.0:
                        return await self._resolver_ab(txt)
                else:
                    estavel_desde = None
                    last = txt
            else:
                estavel_desde = None
                if txt:
                    last = txt
            await asyncio.sleep(POLL)
        if last:
            return await self._resolver_ab(last)
        raise RuntimeError(f"Qwen nao respondeu em {timeout}s.")

    async def _resolver_ab(self, txt):
        """O Qwen as vezes mostra duas respostas (A/B). Escolhe a primeira para
        colapsar e rele o texto consolidado."""
        try:
            if not await self._drv(self._call("temAB")):
                return txt
            c = await self._drv(self._call("centroPreferir"))
            if c:
                await self.cdp.click_at(c["x"], c["y"])
                await asyncio.sleep(1.0)
                novo = await self._drv(self._call("ultimaResposta"))
                return novo or txt
        except Exception:
            pass
        return txt

    # ---- envio simples ----

    async def ask(self, prompt, timeout=180):
        if not prompt:
            raise ValueError("tarefa vazia.")
        antes = await self._drv(self._call("qtdAssistentes"))
        r = await self._drv(self._call("preencherComposer", prompt))
        if isinstance(r, dict) and r.get("erro"):
            raise RuntimeError("Campo de entrada do Qwen nao encontrado.")
        await asyncio.sleep(0.25)
        c = await self._drv(self._call("centroEnvio"))
        if not c:
            raise RuntimeError("Botao de envio do Qwen nao encontrado.")
        await self.cdp.click_at(c["x"], c["y"])
        comecou = lambda snap, _: (snap or {}).get("assistentes", 0) > antes and bool((snap or {}).get("texto"))
        return await self._aguardar(comecou, timeout)

    # ---- selecao de modelo ----

    async def selecionar_modelo(self, modelo):
        if not modelo:
            return "nada a selecionar"
        c = await self._drv(self._call("centroSeletorModelo"))
        if not c:
            raise RuntimeError("Seletor de modelo nao encontrado.")
        await self.cdp.click_at(c["x"], c["y"])
        await asyncio.sleep(0.7)
        alvo = await self._drv(self._call("centroModelo", modelo))
        if not alvo:
            disp = await self._drv(self._call("modelosDisponiveis"))
            await self.cdp.evaluate("document.body.click()")  # fecha o dropdown
            raise ValueError(f"Modelo '{modelo}' nao encontrado. Disponiveis: {disp}")
        await self.cdp.click_at(alvo["x"], alvo["y"])
        await asyncio.sleep(0.4)
        return f"modelo selecionado: {modelo}"

    # ---- fluxo API: configurar + consultar ----

    async def _nova_conversa(self):
        c = await self._drv(self._call("centroNova"))
        if not c:
            raise RuntimeError("Botao de nova conversa nao encontrado.")
        await self.cdp.click_at(c["x"], c["y"])
        loop = asyncio.get_running_loop()
        inicio = loop.time()
        while loop.time() - inicio < 15:
            await asyncio.sleep(0.4)
            info = await self._drv(self._call("info"))
            if info.get("temEditor") and info.get("usuarios", 0) == 0:
                return
        raise RuntimeError("Nao consegui iniciar uma conversa nova (a conversa nao limpou).")

    async def configurar(self, config, modelo=None, timeout=180):
        if not config:
            raise ValueError("config vazia.")
        await self._nova_conversa()
        if modelo:
            await self.selecionar_modelo(modelo)
        return await self.ask(config, timeout=timeout)

    async def consultar(self, tarefa, timeout=180):
        if not tarefa:
            raise ValueError("tarefa vazia.")
        info = await self._drv(self._call("info"))
        if info.get("usuarios", 0) == 0:
            raise RuntimeError("Configure primeiro com configurar_qwen.")
        # So a config existe: a mensagem de trabalho ainda nao existe, cria como nova.
        if info.get("usuarios", 0) < 2:
            return await self.ask(tarefa, timeout=timeout)

        texto_antigo = await self._drv(self._call("ultimaResposta"))
        ce = await self._drv(self._call("centroEditar", None))
        if not ce:
            raise RuntimeError("Botao de editar nao encontrado na mensagem de trabalho.")
        await self.cdp.click_at(ce["x"], ce["y"])
        await asyncio.sleep(0.5)
        r = await self._drv(self._call("preencherEdicao", tarefa))
        if isinstance(r, dict) and r.get("erro"):
            raise RuntimeError("Campo de edicao (textarea) nao encontrado.")
        await asyncio.sleep(0.2)
        cs = await self._drv(self._call("centroEnviarEdicao"))
        if not cs:
            raise RuntimeError("Botao 'Enviar' da edicao nao encontrado.")
        await self.cdp.click_at(cs["x"], cs["y"])
        # A edicao regenera a resposta no mesmo lugar: comecou quando o texto muda do
        # antigo (ou, em ultimo caso, apos 10s, caso a resposta nova seja identica).
        comecou = lambda snap, elapsed: (
            bool(snap.get("texto")) and snap.get("texto") != texto_antigo
        ) or elapsed > 10
        return await self._aguardar(comecou, timeout)

    # ---- diagnostico ----

    async def inspecionar(self, seletor="", max=40):
        return await self._drv(self._call("inspecionar", seletor, max))
