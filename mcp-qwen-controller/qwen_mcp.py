#!/usr/bin/env python
"""Ponto de entrada do servidor MCP, imune ao diretorio de trabalho.

Hosts de MCP nem sempre lancam da raiz do repo. Este script se auto-localiza pelo
__file__ e poe a pasta no sys.path, entao funciona com qualquer CWD desde que o host
aponte para o caminho absoluto dele.

Uso no host:  command: python   args: ["/caminho/absoluto/qwen_mcp.py"]

Requer o Qwen Chat desktop aberto, logado, e iniciado com --remote-debugging-port=9222.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Defaults herdados se o host nao definir.
os.environ.setdefault("QWEN_CDP_HOST", "127.0.0.1")
os.environ.setdefault("QWEN_CDP_PORT", "9222")

from qwen_bridge.server import build_server  # noqa: E402

if __name__ == "__main__":
    build_server().run()
