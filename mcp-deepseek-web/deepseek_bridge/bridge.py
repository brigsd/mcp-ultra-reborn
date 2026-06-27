"""WebSocket bridge: liga a tool MCP a extensao do Chrome.

O MCP roda um servidor WebSocket local. A extensao conecta como cliente. Quando
a tool e chamada, o MCP manda o comando pela conexao e espera (long-poll) a
resposta correspondente, casada por um id unico.
"""

import asyncio
import json
import uuid

import websockets


class Bridge:
    def __init__(self, host="127.0.0.1", port=8766):
        self.host = host
        self.port = port
        self._server = None
        self._client = None          # conexao da extensao (a mais recente vence)
        self._pending = {}           # id -> Future

    async def start(self):
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
        """Envia um comando generico pra extensao e espera a resposta (por id)."""
        if not self.connected:
            raise RuntimeError(
                "Extensao nao conectada. Abra o Chrome com a aba do DeepSeek e a "
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
            raise RuntimeError(f"DeepSeek nao respondeu em {timeout}s.")

    async def ask(self, prompt, timeout=180):
        return await self.send_cmd("ask", {"prompt": prompt}, timeout=timeout)
