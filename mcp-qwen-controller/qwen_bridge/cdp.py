"""Cliente CDP (Chrome DevTools Protocol) para o webview do Qwen Chat desktop.

O Qwen desktop e um app Electron. Iniciado com --remote-debugging-port=9222, ele
expoe o protocolo de depuracao. O chat de verdade vive num alvo do tipo webview
(chat.qwen.ai), nao na pagina raiz do app.

Este cliente acha esse webview, mantem uma conexao WebSocket de depuracao e oferece
duas operacoes: avaliar JavaScript (Runtime.evaluate) e clicar por coordenada com um
evento confiavel (Input.dispatchMouseEvent). O clique confiavel e a vantagem do CDP
sobre uma extensao: abre menus (como o seletor de modelo) que o clique sintetico nao
abre.
"""

import asyncio
import json
import urllib.request

import websockets

# Toda chamada CDP e limitada no tempo: sem isto, um recv() sem resposta (target
# trocado, navegacao, mensagem perdida) trava para sempre, e o timeout das camadas
# de cima nao ajuda porque o proprio await fica preso antes de checar o relogio.
CDP_TIMEOUT = 30


class CDP:
    def __init__(self, host="127.0.0.1", port=9222):
        self.host = host
        self.port = port
        self._ws = None
        self._id = 0

    # ---- descoberta do alvo ----

    def _targets(self):
        with urllib.request.urlopen(f"http://{self.host}:{self.port}/json", timeout=5) as r:
            return json.load(r)

    def _find_ws(self):
        try:
            alvos = self._targets()
        except Exception:
            return None
        # O chat vive no webview do chat.qwen.ai.
        for t in alvos:
            if "chat.qwen.ai" in (t.get("url") or "") and t.get("type") in ("page", "webview"):
                return t.get("webSocketDebuggerUrl")
        return None

    def reachable(self):
        """True se a porta de depuracao responde e o webview do Qwen existe."""
        return self._find_ws() is not None

    # ---- conexao ----

    async def _ensure(self):
        if self._ws is not None and self._ws.close_code is None:
            return
        url = self._find_ws()
        if not url:
            raise RuntimeError(
                "Webview do Qwen nao encontrado. Confirme que o Qwen Chat desktop esta "
                "aberto, logado, e foi iniciado com --remote-debugging-port=9222."
            )
        self._ws = await websockets.connect(url, max_size=None)

    async def close(self):
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

    async def _send(self, method, params=None, timeout=CDP_TIMEOUT):
        # Uma tentativa de reconexao se o socket caiu (app reiniciado, webview trocado).
        for tentativa in (1, 2):
            try:
                await self._ensure()
                self._id += 1
                mid = self._id
                await self._ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
                return await asyncio.wait_for(self._recv_id(mid), timeout=timeout)
            except (websockets.ConnectionClosed, OSError):
                self._ws = None
                if tentativa == 2:
                    raise
            except asyncio.TimeoutError:
                # Resposta nunca veio: descarta o socket e falha (nao trava).
                self._ws = None
                raise RuntimeError(f"CDP sem resposta em {timeout}s ({method}).")

    async def _recv_id(self, mid):
        while True:
            msg = json.loads(await self._ws.recv())
            if msg.get("id") == mid:
                return msg.get("result", {}), msg.get("error")

    # ---- operacoes ----

    async def evaluate(self, expr, await_promise=False):
        res, err = await self._send("Runtime.evaluate", {
            "expression": expr,
            "awaitPromise": await_promise,
            "returnByValue": True,
        })
        if err:
            raise RuntimeError(f"CDP: {err.get('message')}")
        if "exceptionDetails" in res:
            exc = res["exceptionDetails"]
            desc = (exc.get("exception") or {}).get("description") or exc.get("text")
            raise RuntimeError(f"JS: {desc}")
        return res.get("result", {}).get("value")

    async def click_at(self, x, y):
        """Clique confiavel (isTrusted) por coordenada, igual ao de um humano."""
        await self._send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y, "buttons": 0})
        await self._send("Input.dispatchMouseEvent", {
            "type": "mousePressed", "x": x, "y": y, "button": "left", "buttons": 1, "clickCount": 1,
        })
        await self._send("Input.dispatchMouseEvent", {
            "type": "mouseReleased", "x": x, "y": y, "button": "left", "buttons": 0, "clickCount": 1,
        })
