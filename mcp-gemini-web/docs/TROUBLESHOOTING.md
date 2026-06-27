# Troubleshooting — mcp-gemini-web

A fonte de verdade do estado da conexao e a tool `gemini_status`, **nao** o console
da extensao (que acumula erros velhos). Comece sempre por ela.

## `gemini_status` diz `desconectada`

A ponte esta no ar, mas a extensao nao esta conectada. Cheque, em ordem:

1. A extensao "Gemini Bridge" esta carregada em `chrome://extensions` sem erro
   vermelho?
2. Tem uma aba `https://gemini.google.com/*` aberta e logada?
3. Abra o console do **service worker** (link no card da extensao) e veja se diz
   `[gemini-bridge] WS conectado` ou um erro de WebSocket.

Causa comum: o worker do MV3 hibernou na janela do restart e nao tentou reconectar.
O alarme reconecta em ate ~30s; se nao, **recarregue o card** da extensao.

## Console da extensao: `ERR_CONNECTION_REFUSED` em `ws://127.0.0.1:8765`

Quase sempre e **erro velho** da janela em que o servidor ainda nao tinha subido
(durante um restart). Nao confie nele; confirme o estado real:

```bash
# a porta esta escutando?
netstat -ano | grep 8765        # deve mostrar 127.0.0.1:8765  LISTENING <pid>

# algo consegue conectar? (teste TCP independente do Chrome)
python -c "import socket;s=socket.socket();s.settimeout(2);s.connect(('127.0.0.1',8765));print('OK');s.close()"
```

Se aparece `LISTENING` e o teste TCP imprime OK, o servidor esta bom e o erro do
console e passado. Rode `gemini_status` — se der `conectada`, ignore o console.

## Tool retorna `Could not establish connection. Receiving end does not exist`

O content script nao esta na aba do Gemini (ficou orfao apos recarregar a
extensao). O `background.js` ja trata reinjetando via `chrome.scripting`, mas se
ainda ocorrer, **de F5 na aba do Gemini** pra reinjetar o `content.js`.

## Tool falha com "Campo de entrada do Gemini nao encontrado" ou da timeout

Os seletores do Gemini mudaram (o Google atualizou a UI). Conserto fica todo no
objeto `SEL` no topo de `extension/content.js`:

- `editor`    — o campo de texto (contenteditable do Quill).
- `sendBtn`   — o botao de enviar.
- `responses` — os blocos de resposta (le-se o `innerText` do ultimo).
- `stopBtn`   — o botao "parar de gerar" (presenca = ainda streamando).

Inspecione o elemento real no DevTools da aba e reaponte o seletor.

## Porta 8765 ocupada / conflito

So **um** processo pode escutar a 8765. Nao deixe o `testar.py` rodando junto com
o MCP do host: os dois tentam abrir a mesma porta. Rode um de cada vez. Pra trocar
de porta, ajuste `GEMINI_WS_PORT` (servidor, via env/`.mcp.json`) **e** `WS_URL`
em `background.js`.

## Mudei o servidor (`bridge.py`/`server.py`) e nada mudou

O host so recarrega o servidor MCP ao reiniciar. Reinicie o host (ex.: Claude Code)
pra ele relançar o `gemini_mcp.py` com o codigo novo.

## Mudei a extensao e nada mudou

Recarregue o card em `chrome://extensions`. Mudancas de `background.js` exigem
reload do card; mudancas que afetam a aba podem exigir F5 nela (ou o primeiro
pedido reinjeta sozinho).

## A UI do Gemini fica travada num A/B ("Qual resposta e mais util?")

O `content.js` ja detecta e clica na Opcao A pra destravar. Se o Google mudar o
texto do botao, ajuste o regex em `resolveComparison` (hoje casa `mais util`).
