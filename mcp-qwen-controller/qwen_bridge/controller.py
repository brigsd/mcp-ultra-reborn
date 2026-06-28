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
    def __init__(self, host="127.0.0.1", port=9222, http_port=None):
        if http_port is None:
            import os
            http_port = int(os.environ.get("QWEN_HTTP_PORT", 8780))
        if port == 9222:
            port = 9222 + (http_port - 8780)
        self.cdp = CDP(host, port)
        self.http_url = f"http://{host}:{http_port}"
        self.use_http = False

    async def _drv(self, expr):
        """Avalia uma chamada do driver (window.__qwen.<fn>) no webview."""
        if self.use_http:
            try:
                import urllib.request
                import json
                loop = asyncio.get_running_loop()
                def req():
                    data = (_DRIVER + ";\n" + expr).encode('utf-8')
                    req_obj = urllib.request.Request(f"{self.http_url}/evaluate", data=data, method="POST")
                    with urllib.request.urlopen(req_obj, timeout=5) as response:
                        return json.loads(response.read().decode('utf-8'))
                res = await loop.run_in_executor(None, req)
                return res.get("result")
            except Exception:
                self.use_http = False
        
        return await self.cdp.evaluate(_DRIVER + ";\n" + expr)

    async def _click(self, c, selector_js=None):
        if not c:
            return
        if not self.use_http:
            await self.cdp.click_at(c["x"], c["y"])
        else:
            if selector_js:
                await self._drv(f"document.querySelector('{selector_js}')?.click()")
            else:
                await self._drv(f"document.elementFromPoint({c['x']}, {c['y']})?.click()")

    async def _forcar_react_input(self, selector_js="textarea.message-input-textarea"):
        """Forca o React a atualizar seu estado enviando um evento fisico de teclado (Espaco + Backspace) via CDP."""
        try:
            await self._drv(f"document.querySelector('{selector_js}')?.focus()")
            await self.cdp._send("Input.dispatchKeyEvent", {
                "type": "keyDown",
                "text": " ",
                "key": "Space"
            })
            await self.cdp._send("Input.dispatchKeyEvent", {
                "type": "keyUp",
                "key": "Space"
            })
            await self.cdp._send("Input.dispatchKeyEvent", {
                "type": "keyDown",
                "key": "Backspace"
            })
            await self.cdp._send("Input.dispatchKeyEvent", {
                "type": "keyUp",
                "key": "Backspace"
            })
        except Exception:
            pass

    def _call(self, fn, *args):
        args = ", ".join(json.dumps(a) for a in args)
        return f"window.__qwen.{fn}({args})"

    # ---- status ----

    async def status(self):
        try:
            import urllib.request
            import json
            loop = asyncio.get_running_loop()
            def check():
                with urllib.request.urlopen(f"{self.http_url}/status", timeout=1.0) as response:
                    return json.loads(response.read().decode('utf-8'))
            data = await loop.run_in_executor(None, check)
            if data.get("status") == "ok":
                self.use_http = True
                return "conectado"
        except Exception:
            pass

        self.use_http = False
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
                await self._click(c)
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
        
        # Acorda o React para habilitar o botao de envio
        await self._forcar_react_input("textarea.message-input-textarea")
        
        # Aguarda o botao de envio ficar ativo/habilitado por ate 5 segundos (React render latency)
        c = None
        for _ in range(10):
            c = await self._drv(self._call("centroEnvio"))
            if c:
                break
            await asyncio.sleep(0.5)
        if not c:
            raise RuntimeError("Botao de envio do Qwen nao encontrado ou desabilitado.")
        await self._click(c, "button.send-button")
        comecou = lambda snap, _: (snap or {}).get("assistentes", 0) > antes and bool((snap or {}).get("texto"))
        return await self._aguardar(comecou, timeout)

    # ---- selecao de modelo ----

    async def selecionar_modelo(self, modelo):
        if not modelo:
            return "nada a selecionar"
        c = await self._drv(self._call("centroSeletorModelo"))
        if not c:
            raise RuntimeError("Seletor de modelo nao encontrado.")
        await self._click(c, '[class*="model-selector"]')
        await asyncio.sleep(0.7)
        alvo = await self._drv(self._call("centroModelo", modelo))
        if not alvo:
            # Tenta expandir mais modelos se o botao estiver visivel
            c_more = await self._drv(self._call("centroExpandirModelos"))
            if c_more:
                await self._click(c_more, '[class*="view-more"]')
                await asyncio.sleep(0.8)
                alvo = await self._drv(self._call("centroModelo", modelo))
        
        if not alvo:
            disp = await self._drv(self._call("modelosDisponiveis"))
            await self.cdp.evaluate("document.body.click()")  # fecha o dropdown
            raise ValueError(f"Modelo '{modelo}' nao encontrado. Disponiveis: {disp}")
        await self._click(alvo)
        await asyncio.sleep(0.4)
        return f"modelo selecionado: {modelo}"

    # ---- fluxo API: configurar + consultar ----

    async def _nova_conversa(self):
        c = await self._drv(self._call("centroNova"))
        if not c:
            raise RuntimeError("Botao de nova conversa nao encontrado.")
        await self._click(c, ".sidebar-entry-fixed-list-content, .sidebar-entry-fixed-list")
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
        await self._click(ce)
        await asyncio.sleep(0.5)
        r = await self._drv(self._call("preencherEdicao", tarefa))
        if isinstance(r, dict) and r.get("erro"):
            raise RuntimeError("Campo de edicao (textarea) nao encontrado.")
        
        # Acorda o React no textarea de edicao
        await self._forcar_react_input("textarea.qwen-edit-content-textarea")
        
        # Aguarda o botao 'Enviar' da edicao ficar ativo por ate 5 segundos
        cs = None
        for _ in range(10):
            cs = await self._drv(self._call("centroEnviarEdicao"))
            if cs:
                break
            await asyncio.sleep(0.5)
        if not cs:
            raise RuntimeError("Botao 'Enviar' da edicao nao encontrado ou desabilitado.")
        await self._click(cs)
        # A edicao regenera a resposta no mesmo lugar: comecou quando o texto muda do
        # antigo (ou, em ultimo caso, apos 10s, caso a resposta nova seja identica).
        comecou = lambda snap, elapsed: (
            bool(snap.get("texto")) and snap.get("texto") != texto_antigo
        ) or elapsed > 10
        return await self._aguardar(comecou, timeout)

    # ---- diagnostico ----

    async def inspecionar(self, seletor="", max=40):
        return await self._drv(self._call("inspecionar", seletor, max))
