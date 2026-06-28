"""WebSocket bridge: liga a tool MCP a extensao do Chrome.

O MCP roda um servidor WebSocket local. A extensao conecta como cliente. Quando
a tool e chamada, o MCP manda a tarefa pela conexao e espera (long-poll) o
"answer" correspondente voltar, casado por um id unico.
"""

import asyncio
import json
import subprocess
import sys
import uuid

import websockets


def _liberar_porta(port: int) -> None:
    """Mata qualquer processo segurando a porta TCP localmente."""
    try:
        if sys.platform == "win32":
            r = subprocess.run(
                ["netstat", "-ano"], capture_output=True, text=True
            )
            for line in r.stdout.splitlines():
                if f":{port} " in line and "LISTENING" in line:
                    pid = line.split()[-1]
                    subprocess.run(
                        ["taskkill", "/F", "/PID", pid],
                        capture_output=True,
                    )
        else:
            subprocess.run(
                ["fuser", "-k", f"{port}/tcp"],
                capture_output=True,
            )
    except Exception:
        pass


class Bridge:
    def __init__(self, host="127.0.0.1", port=8765):
        self.host = host
        self.port = port
        self._server = None
        self._client = None          # conexao da extensao (a mais recente vence)
        self._pending = {}           # id -> Future

    async def start(self):
        try:
            self._server = await websockets.serve(self._handler, self.host, self.port)
        except OSError:
            # Porta ocupada por processo anterior (ex.: servidor HTTP de sessao antiga).
            # Libera e tenta de novo uma vez.
            _liberar_porta(self.port)
            await asyncio.sleep(0.5)
            self._server = await websockets.serve(self._handler, self.host, self.port)

    async def stop(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    @property
    def connected(self):
        return self._client is not None

    async def _heartbeat(self, ws):
        # Ping de aplicacao a cada 20s: a atividade no socket impede o service
        # worker do MV3 de hibernar e derrubar a conexao.
        try:
            while True:
                await asyncio.sleep(20)
                await ws.send(json.dumps({"type": "ping"}))
        except Exception:
            pass

    async def _handler(self, ws, *args):
        # Uma extensao por vez; a conexao mais nova assume.
        self._client = ws
        hb = asyncio.create_task(self._heartbeat(ws))
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
                rid = msg.get("id")
                fut = self._pending.pop(rid, None) if rid else None
                if not fut or fut.done():
                    continue
                if msg.get("type") == "answer":
                    fut.set_result(msg.get("text", ""))
                elif msg.get("type") == "error":
                    fut.set_exception(RuntimeError(msg.get("message", "erro na extensao")))
        finally:
            hb.cancel()
            if self._client is ws:
                self._client = None

    async def send_cmd(self, kind, payload=None, timeout=180):
        """Envia um comando generico pra extensao e espera a resposta (por id).

        kind: tipo da acao (ask, configurar, consultar, selecionar_modelo).
        payload: dict com os campos da acao (prompt, tarefa, config, modelo...).
        """
        if not self.connected:
            raise RuntimeError(
                "Extensao nao conectada. Abra o Chrome com a aba do Gemini e a "
                "extensao carregada."
            )
        rid = uuid.uuid4().hex
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        self._pending[rid] = fut
        msg = {"type": kind, "id": rid}
        if payload:
            msg.update(payload)
        await self._client.send(json.dumps(msg))
        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(rid, None)
            raise RuntimeError(f"Gemini nao respondeu em {timeout}s.")

    async def ask(self, prompt, timeout=180):
        return await self.send_cmd("ask", {"prompt": prompt}, timeout=timeout)
