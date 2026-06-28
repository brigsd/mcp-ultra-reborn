#!/usr/bin/env python
"""Ponto de entrada do servidor MCP, imune ao diretorio de trabalho.

Auto-localiza pelo __file__ e poe a raiz no sys.path, entao funciona com qualquer
CWD desde que o host aponte para o caminho absoluto dele.

Uso no host:  command: python   args: ["/caminho/absoluto/deepseek_mcp.py"]
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Porta propria (8766) pra nao colidir com o mcp-gemini-web (8765).
os.environ.setdefault("DEEPSEEK_WS_HOST", "127.0.0.1")
os.environ.setdefault("DEEPSEEK_WS_PORT", "8766")

from deepseek_bridge.server import build_server  # noqa: E402

if __name__ == "__main__":
    # DEEPSEEK_TRANSPORT=http roda como servidor HTTP persistente (de pe sozinho,
    # o host conecta pela URL); qualquer outro valor mantem o stdio padrao.
    _transporte = os.environ.get("DEEPSEEK_TRANSPORT", "stdio").strip().lower()
    if _transporte in ("http", "streamable-http", "streamable_http"):
        build_server().run(transport="streamable-http")
    else:
        build_server().run()
