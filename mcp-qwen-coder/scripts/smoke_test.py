"""Smoke test do MCP-Worker: sobe o servidor em stdio, lista as tools e chama
algumas delas — sem precisar de cliente externo (Qwen/Claude).

Uso:
    .venv/Scripts/python.exe scripts/smoke_test.py
"""

from __future__ import annotations

import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> int:
    # Sobe o próprio server.py como subprocesso, em stdio.
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_qwen_coder.server"],
        env={**os.environ, "MCP_TRANSPORT": "stdio"},
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            print(f"[OK] {len(names)} tools expostas: {', '.join(names)}\n")

            async def call(name: str, **args):
                res = await session.call_tool(name, args)
                text = "".join(
                    block.text for block in res.content if block.type == "text"
                )
                print(f"--- {name}({args}) ---\n{text}\n")
                return text

            await call("get_system_info")
            await call("get_working_directory")
            await call("run_command", command="echo ola-do-worker")
            await call("write_file", path="_smoke_tmp.txt", content="conteudo de teste\n")
            await call("read_file", path="_smoke_tmp.txt")
            await call(
                "edit_file",
                path="_smoke_tmp.txt",
                old_string="teste",
                new_string="TESTE",
            )
            await call("read_file", path="_smoke_tmp.txt")
            await call("list_directory")

    # limpeza
    try:
        os.remove("_smoke_tmp.txt")
    except OSError:
        pass

    print("[OK] smoke test concluido sem excecoes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
