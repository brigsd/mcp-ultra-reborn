# Investigação: Internals do Qwen Chat Desktop
> Fonte: `C:\Users\tiago\AppData\Local\Programs\Qwen\resources\app.asar`
> Método 1: extração do bundle ASAR (formato Electron), leitura direta dos arquivos JS
> Método 2: interceptação ao vivo via CDP (Chrome DevTools Protocol) — patch de fetch/XHR/beacon no webview
> 4788 arquivos extraídos; 41 requisições capturadas ao vivo em ~2 minutos de uso normal

---

## Estrutura do app

Qwen Chat Desktop é um **Electron app** — não binário nativo, não Bun SEA.
O código JS é legível diretamente do ASAR sem nenhuma ofuscação.

Arquivos de app principal (fora de node_modules):

```
out/main/index.js          22 KB   — processo principal Electron
out/preload/index.js        2 KB   — bridge entre main e webview
out/renderer/assets/index-J-5aykDP.js   232 KB  — UI React (shell)
```

Runtimes bundlados em `resources/`:
- `bun/win-x64/bun.exe` — para rodar MCP servers em JS/TS
- `python/win-x64/uvx.exe` e `uv.exe` — para MCP servers Python

---

## O que o app realmente faz

A UI é uma **webview única** carregando `https://chat.qwen.ai`. Todo o chat, autenticação e lógica de conversa rodam dentro dessa webview — o Electron é apenas um container com recursos extras.

```js
const WEBVIEW_URL = `https://chat.qwen.ai`;
// ...
<webview src={url} useragent={navigator.userAgent + ` AliDesktop(QWENCHAT/1.0.3)`} />
```

O app injeta o mesmo preload script na webview, expondo `window.electronAPI` ao código do `chat.qwen.ai`. Ou seja, o site da Alibaba tem acesso direto ao sistema MCP e ao IPC Electron do desktop.

---

## Rede: destinos confirmados

| Destino | Protocolo | Para que serve |
|---|---|---|
| `chat.qwen.ai` (`8.212.2.173:443`) | HTTPS (webview) | Chat, API de modelos, login |
| `gm.mmstat.com/aes.1.1` | HTTPS POST | Telemetria (AES tracker) |
| `s-gm.mmstat.com` | HTTPS POST | Telemetria secundária (fallback) |
| `download.qwen.ai/windows/x64/` | HTTPS | Atualizações automáticas |
| `cdnwl.qwenlm.ai/qwenchat-backend/test` | HTTPS | Canal de update alternativo |
| `d.alicdn.com`, `g.alicdn.com` | HTTPS | CDN assets |

Todos os IPs pertencem à Alibaba Cloud. Sem reverse DNS — IPs numéricos diretos.

---

## Telemetria: o que é coletado e para onde vai

### Destino

```
https://gm.mmstat.com/aes.1.1
```

Alibaba's "goldlog" / AES analytics server. Payload via POST:
```json
{ "gokey": "<url-encoded data>", "gmkey": "EXP" }
```

### Project ID

`RfGbWG` — identificador do projeto Qwen no sistema de analytics da Alibaba.

### Fingerprint de hardware

O `device_id` enviado em **todo evento** é o MD5 do endereço MAC:

```js
const mac = os.networkInterfaces()  // busca MAC não-zero
const device_id = crypto.createHash('md5').update(mac).digest('hex')
```

Isso vincula cada evento a uma máquina específica, persistente através de reinstalações.

### Dados enviados em todo evento

- `pid` = `RfGbWG` (projeto)
- `device_id` = MD5 do MAC
- `os` = tipo de OS (Win32, Darwin, Linux)
- `os_version` = versão do kernel
- `app_version` = versão do Node/Electron
- `platform` = `node`
- `sdk_version` = `3.3.13` (versão do AES tracker)
- `pv_id` = UUID de sessão (gerado ao iniciar)
- `timezone_offset` = fuso horário

### Eventos específicos registrados pelo main process

| Evento | Quando | Payload extra |
|---|---|---|
| `initProcess` | Startup, window ready, dom-ready, finish-load | PID do processo |
| `getAppVersion` | Consulta de versão | Versão |
| `webviewLoaded` | Webview carregada | webContentsId |
| `switchTheme` | Troca de tema | Nome do tema |
| `switchLn` | Troca de idioma | Código do idioma |
| `openUrl` | URL externa aberta | URL |
| `autoUpdater` | Events de update | status (available/downloaded/error) |
| `renderCrush` | Crash do renderer | código de erro |
| `nodeUncaughtException` | Erro JS não capturado | mensagem |
| `update-status` | Checando atualizações | string "checking" |

Todos os eventos incluem `{time, timeStamp}` no campo `c6`.

### Stacks de tracking presentes

- `@ali/aes-tracker` + `@ali/aes-tracker-plugin-event` — eventos comportamentais
- `@ali/aplus` (aplus_pc.js) — pageview tracking, SPM anchor, click tracking
- `@ali/trace-core` + plugins (`trace-plugin-api`, `trace-plugin-error`, `trace-plugin-perf`, `trace-plugin-resource-error`, `trace-blank-screen`) — APM/performance monitoring
- `@ali/trace-sdk` — wrapper consolidado

Esses rodam dentro do webview (`chat.qwen.ai`), não no processo Electron.

---

## MCP client: como funciona

O processo principal usa `@ali/spark-mcp` para gerenciar servidores MCP:

```js
const mcpServer = new sparkMcp.Proxy();
// lista tools, chama tools, atualiza config
```

Quando o usuário configura um MCP server com `npx` ou `bun`, o app substitui silenciosamente pelo bun bundlado:

```js
if (cmd === "npx" || cmd === "bun") {
  cmd = getBunPath();  // resources/bun/win-x64/bun.exe
}
if (cmd === "uvx") {
  cmd = getUvxPath();  // resources/python/win-x64/uvx.exe
}
```

A configuração MCP fica salva em `electron-settings` (arquivo local) e é restaurada a cada inicialização.

O webview (`chat.qwen.ai`) acessa o MCP via `window.electronAPI`:
- `mcp_client_tool_list(serverName)` — lista tools de um server
- `mcp_client_tool_call(params)` — chama uma tool
- `mcp_client_get_config()` — lê config atual
- `mcp_client_update_config(config)` — atualiza config

---

## Autenticação

Sem tokens em arquivos locais. Auth acontece dentro do webview em `chat.qwen.ai`.

Mecanismo de deep link para login externo:

```
qwen://open?token=<jwt_ou_cookie>
```

O main process intercepta esse protocolo, valida, e envia o token para o webview via IPC (`set_cookie` event). O código da web app seta o cookie de autenticação com esse token.

Isso permite que outros apps (ou scripts) abram o Qwen já autenticado passando um token via URL de protocolo.

---

## Segurança do webview

O webview roda com várias proteções desabilitadas:

```js
webPreferences: {
  sandbox: false,
  webSecurity: false,                    // CORS desabilitado
  allowRunningInsecureContent: true,     // HTTP dentro de HTTPS
  nodeIntegrationInSubFrames: true,      // Node em sub-frames
  contextIsolation: true,               // (mantido)
  nodeIntegration: false,               // (mantido)
}
```

E o webview em si:
```js
webpreferences: "nodeIntegrationInSubFrames=true, sandbox=false"
```

Com `webSecurity: false`, o webview de `chat.qwen.ai` pode fazer requisições para qualquer origem sem restrição de CORS — incluindo `localhost`.

---

## Easter egg / backdoor de debug

Digitando a sequência `woshi149205` dentro do webview (com intervalo menor que 3s entre teclas) ativa o DevTools oculto:

```js
if (keySequence.join('') === 'woshi149205') {
  window.electron.ipcRenderer.sendToHost('EASTER_EGG_ACTIVATED');
}
// handler: abre DevTools do webview + DevTools do shell
```

---

## User-Agent customizado

Toda requisição do webview carrega:
```
Mozilla/5.0 ... Chrome/... Electron/... AliDesktop(QWENCHAT/1.0.3)
```

Isso identifica o cliente como desktop Qwen nos servidores da Alibaba — permite que o backend aplique comportamentos distintos para o app desktop vs. o web.

---

## Logs locais

O processo principal escreve logs em:
```
%APPDATA%\Qwen\qwen-electron-debug.log
```
Arquivo truncado a cada novo dia. Contém timestamps e saída do `console.log` do main process.

---

---

## Monitoramento ao vivo: o que foi capturado

Método: injeção de interceptores fetch/XHR/sendBeacon no webview via CDP (Runtime.evaluate),
capturados durante 2 minutos de uso normal incluindo abertura do app e envio de uma mensagem.

### Fluxo de dados em ordem cronológica

Ao abrir uma nova conversa, dentro de ~2 segundos, o app dispara 41 requisições:

**1. Telemetria Alibaba (aplus.qwen.ai) — imediata, antes de qualquer interação:**
```
beacon POST https://aplus.qwen.ai/aes.1.1
beacon POST https://aplus.qwen.ai/v.gif     ← pixel de pageview
```

Payload do `v.gif` (pageview pixel) decodificado:
```
logtype     = 1
title       = Qwen Studio
scr         = 2752x1152                     ← resolução de tela
_p_url      = https://chat.qwen.ai/c/new-chat
cna         = qJu9IuM17CUCAS3tUjlr8Js6     ← ID persistente de dispositivo (Alibaba CNA)
uidaplus    = 72f75b5a-68c4-43ac-8432-acbb29fbb407  ← UUID do usuário
timezone_offset = 180                        ← UTC-3 (Brasil)
dpi         = 1.25
```

O `cna` (Client Network Anchor) é um identificador persistente da Alibaba que atravessa sessões
e reinstalações — equivalente a um UDID de dispositivo nos sistemas Alibaba.

**2. Chat API (chat.qwen.ai) — com JWT de autenticação:**

Cada chamada de API inclui `Authorization: Bearer <JWT>`. O JWT decodificado:
```json
{
  "id": "72f75b5a-68c4-43ac-8432-acbb29fbb407",
  "last_password_change": 1781968329,
  "exp": 1785244607
}
```

Sequência de chamadas por nova conversa:
```
GET  /api/v2/mcp/list?language=pt-BR          ← lista de MCP servers (sincronizada com Alibaba)
GET  /api/v2/configs/setting-config           ← configurações do usuário (armazenadas no servidor)
POST /api/v2/users/status                     ← heartbeat com info de device/produto
POST /api/v2/chats/new                        ← criação do chat (model, tipo, timestamp)
POST /api/v2/chat/completions?chat_id=...     ← a mensagem em si (streaming)
GET  /api/v2/chats/?page=1&exclude_project=true  ← histórico de conversas
GET  /api/v2/chats/{chat_id}                  ← conteúdo da conversa atual
GET  /api/v2/library/list?type=all            ← biblioteca do usuário
GET  /api/v2/notifications/latest?type=memory ← polling a cada 10 SEGUNDOS
```

O body de `POST /api/v2/users/status` envia a cada interação:
```json
{
  "typarms": {
    "typarm1": "desktop",
    "typarm2": "72f75b5a-68c4-43ac-8432-acbb29fbb407",
    "typarm3": "prod",
    "typarm4": "qwen_chat",
    "typarm5": "product",
    "orgid": "tongyi",
    "cdn_version": "0.2.67",
    "spmId": "a2ty_o01.29997170..."
  }
}
```

`orgid: "tongyi"` revela o nome interno: **Tongyi (通义)** — divisão de IA da Alibaba.

O body de `POST /api/v2/chat/completions` (o que vai junto com sua mensagem):
```json
{
  "stream": true,
  "version": "2.1",
  "incremental_output": true,
  "chat_id": "32075a4b-c7aa-4dba-8d48-2b1ecae02d9f",
  "chat_mode": "normal",
  "model": "qwen3.7-plus",
  "parent_id": null,
  "messages": [...]     ← histórico completo da conversa, incluindo a mensagem enviada
}
```

**3. Google Ads (pagead2.googlesyndication.com) — a parte mais inesperada:**

A cada mudança de página (nova conversa, navegar para outra):
```
POST https://pagead2.googlesyndication.com/pagead/conversion/11551851435/
POST https://pagead2.googlesyndication.com/ccm/collect
```

Parâmetros enviados ao Google:
```
en       = page_view
url      = https://chat.qwen.ai/c/32075a4b-c7aa-4dba-8d48-2b1ecae02d9f  ← URL com ID do chat
ref      = https://chat.qwen.ai/c/new-chat
u_w      = 2752   ← largura de tela
u_h      = 1152   ← altura de tela
uap      = Windows
uapv     = 19.0.0
gtm      = 45be66o1v9203647779za200zd9203647779xec   ← Google Tag Manager ID
tid      = AW-11551851435   ← Google Ads Conversion ID da Alibaba
npa      = 1   ← "non-personalized ads" (irônico)
```

Isso significa: a Alibaba usa Google Tag Manager + Google Ads no Qwen Chat.
Cada sessão de chat é reportada ao Google como um "page view" — o Google sabe
quantas vezes você usou o Qwen e quais URLs de conversa visitou.

### Resumo de destinos confirmados ao vivo

| Destino | Tipo | Frequência | O que recebe |
|---|---|---|---|
| `chat.qwen.ai` | API de chat | Por mensagem | Mensagens completas, histórico |
| `aplus.qwen.ai/aes.1.1` | Analytics Alibaba | A cada ação | Ações do usuário + UUID + CNA |
| `aplus.qwen.ai/v.gif` | Pixel de pageview | A cada página | URL, resolução, UUID, CNA |
| `pagead2.googlesyndication.com` | Google Ads | A cada página | URL do chat, resolução, OS |
| `chat.qwen.ai/api/v2/notifications/latest?type=memory` | Polling | A cada 10 segundos | (recebe memória do servidor) |

### O que o endpoint `?type=memory` implica

O app faz polling a cada 10 segundos em `/api/v2/notifications/latest?type=memory`.
Isso indica que o Qwen tem memória de conversas armazenada no lado do servidor —
o backend da Alibaba mantém um estado persistente de "memória" por usuário,
e o app fica verificando constantemente se há atualizações.

---

## Diferença fundamental em relação ao Claude Code

| | Claude Code | Qwen Chat Desktop |
|---|---|---|
| Runtime | Bun SEA (PE nativo) | Electron (JS legível) |
| Chat/API | Via API Anthropic local | Webview em chat.qwen.ai |
| Autenticação | OAuth local / claude.ai | Cookie no webview |
| Telemetria | Azure + Google Cloud (mínimo observado) | gm.mmstat.com (Alibaba) + stacks de tracking |
| Código legível? | Bytecode JSC (parcialmente) | JS puro sem ofuscação |
| MCP | Integração nativa ao CLI | Via @ali/spark-mcp + IPC |

---

## Referências

- ASAR extraído: `scratchpad/qwen_asar/` (4268 arquivos)
- Script de extração: `scratchpad/extract_asar.py`
- Fonte AES tracker: `node_modules/@ali/aes-tracker/index-node.js`
- Fonte spark-mcp: `node_modules/@ali/spark-mcp/dist/cjs/`
- App principal: `out/main/index.js`, `out/preload/index.js`, `out/renderer/assets/index-J-5aykDP.js`
