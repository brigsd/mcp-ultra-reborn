"""Teste manual da bridge + extensao, sem precisar do host MCP.

Sobe o WebSocket, espera a extensao conectar e manda uma pergunta de teste.
Se imprimir a resposta do Gemini, a parte dificil esta funcionando.
"""

import asyncio

from gemini_bridge.bridge import Bridge


async def main():
    b = Bridge()
    await b.start()
    print("Bridge no ar em ws://127.0.0.1:8765")
    print("Agora carregue a extensao e abra o Gemini logado (recarregue a aba 1x).")
    print("Esperando a extensao conectar...")
    while not b.connected:
        await asyncio.sleep(0.5)
    print("Extensao conectada. Mandando pergunta de teste...\n")
    try:
        resp = await b.ask("Responda apenas com a palavra: ok", timeout=120)
        print("=== RESPOSTA DO GEMINI ===")
        print(resp)
    except Exception as e:
        print("FALHOU:", e)
    finally:
        await b.stop()


if __name__ == "__main__":
    asyncio.run(main())
