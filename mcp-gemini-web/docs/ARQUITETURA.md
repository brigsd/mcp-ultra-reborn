# Arquitetura — mcp-gemini-web

## O problema

Trazer o raciocinio do **Gemini web** (a conta gratuita/corporativa que voce ja
usa no navegador) pra dentro de um agente que fala MCP, com duas restricoes:

1. **Nao atrapalhar o usuario.** Nada de tomar o mouse/teclado fisico nem roubar
   foco. Ele continua trabalhando enquanto a tarefa roda.
2. **Sem rastro de automacao do lado do Google.** Usar a sessao real logada, nao
   um navegador headless cheirando a robo.

## A cadeia

```
host MCP  --tool-->  servidor (Python)  --WebSocket-->  extensao  --DOM-->  Gemini
```

- **Servidor MCP** (`gemini_bridge/`): expoe as tools e roda um servidor WebSocket
  local em `127.0.0.1:8765`. E o lado "servidor" da ponte.
- **Extensao Chrome** (`extension/`): conecta como **cliente** WebSocket, recebe a
  tarefa e dirige o Gemini pelo DOM.
- **Casamento por id**: cada pedido leva um id unico (`uuid`). O servidor guarda um
  `Future` por id e o resolve quando volta o `answer` com o mesmo id. Por isso da
  pra ter varios pedidos sem misturar respostas.

## Decisoes de design (o porque)

### Por que DOM, e nao input fisico
A inspiracao foi o MCP de visao **Lente**, que opera apps **nativos** injetando
teclado/mouse fisico e travando o input (ele nao tem escolha: app nativo so expoe
pixel e arvore de acessibilidade). O Gemini e uma **pagina**: tem DOM. Da pra
escrever no campo, clicar em enviar e ler a resposta com evento de JavaScript, sem
tocar no mouse, numa aba de fundo. **Alvo web nao precisa de input fisico; alvo
nativo precisa.** Essa e a diferenca de fundo entre os dois projetos.

### Por que extensao, e nao Google Drive + humano
O desenho inicial usava o Drive como "quadro de recados" (sobe a tarefa num
arquivo, humano cola no Gemini, exporta pro Docs, um watcher detecta o novo
arquivo). Tudo aquilo era **andaime pra resolver "como a resposta volta pra
maquina"**. Quando a extensao le a resposta direto do DOM, o Drive, o humano e o
watcher de pasta perdem a funcao. O Drive so sobraria pra payload gigante.

### Por que detectabilidade nao depende do metodo
Input fisico e extensao sao **igualmente invisiveis pro servidor do Google**,
porque a invisibilidade vem de usar a **sessao real logada**, nao de ser fisico.
O que de fato chama atencao e comportamental (volume, ritmo robotico). Ressalva
corporativa: em **Chrome gerenciado**, o console de admin lista extensoes
instaladas e eventos sinteticos carregam `isTrusted=false`, entao ali a extensao
deixa rastro que o input fisico nao deixa. Por isso este projeto e pensado pra
**conta pessoal**.

### Long-poll, nao fire-and-forget
A tool `pergunta_gemini` **bloqueia** ate a resposta voltar (com timeout). Pro host
e uma tool normal que demora alguns segundos. Um modo assincrono
(`pega_resultado(id)` separado) so seria preciso se o agente tivesse que continuar
trabalhando enquanto espera — ficou de fora de proposito, por simplicidade.

### Hibernacao do service worker (MV3) — o ponto delicado
O service worker do Manifest V3 hiberna em ~30s sem atividade, e ao morrer derruba
o WebSocket. Como o servidor empurra tarefas pela conexao, conexao morta = tarefa
nao chega. Duas defesas, em camadas:

- **Heartbeat do servidor** (`bridge.py`): um ping de aplicacao a cada 20s. A
  atividade no socket reseta o timer de ocio do worker (Chrome 116+), mantendo ele
  vivo e a conexao aberta. Essa e a defesa principal.
- **Alarme da extensao** (`background.js`): `chrome.alarms` a cada 30s chama
  `ensureConnected()`, que reconecta se o worker morreu mesmo assim. E a rede de
  recuperacao.

### Auto-injecao do content script
Recarregar a extensao deixa **orfao** o content script das abas ja abertas
(`chrome.tabs.sendMessage` falha com "Receiving end does not exist"). O background
trata: se o envio falhar, injeta `content.js` via `chrome.scripting.executeScript`
e tenta de novo. Acaba com o "de F5 na aba toda vez".

### Tratamento do A/B do Gemini
As vezes o Gemini mostra "Qual resposta e mais util?" com Opcao A/B e **trava a UI**
esperando escolha. O content script detecta o botao "mais util", clica na Opcao A
pra colapsar numa resposta unica e destravar, e entao le o texto consolidado.

### Protocolo de acoes e o fluxo "API"
O protocolo cresceu de uma acao (`ask`) para varias (`configurar`, `consultar`,
`selecionar_modelo`, `inspecionar`, `gerar_imagem`), todas casadas por id via `Bridge.send_cmd`.
Sobre isso se monta o fluxo que transforma o chat num endpoint com prompt de sistema
fixo:

- **`configurar_gemini`** abre um chat novo (forcando a navegacao no lugar, sem abrir
  aba nova), opcionalmente seleciona modelo/raciocinio, e fixa a 1a mensagem como
  configuracao.
- **`consultar_gemini`** faz cada chamada **editando a 2a mensagem**: cria na 1a vez
  e reescreve nas seguintes. Como editar regenera a resposta e descarta os turnos
  seguintes, o contexto fica em *config + pergunta atual* e nao cresce.
- **`gerar_imagem_gemini`** realiza o download e conversao hibrida (blobs locais em memory e URLs externas por background fetch anonimo) das imagens geradas na resposta, salvando-as localmente.

A leitura da resposta editada e **ancorada ao turno editado** (o `model-response`
apos o ultimo `user-query`), nao a "ultima resposta da pagina", pra nao pegar a
resposta de outro turno durante a regeneracao. A aba alvo e **fixada** no background
pra `configurar` e `consultar` caírem sempre na mesma.

### Selecao de modelo e raciocinio
O seletor de modelo (`button[data-test-id="bard-mode-menu-button"]`) abre um menu de
`gem-menu-item`; o modelo e escolhido por texto e o nivel de raciocinio por um
submenu que abre por **hover** (mat-menu). Isso casa com o `configurar`, ja que o
modelo e mais util definido no inicio do chat.

### inspecionar_gemini — diagnostico de excecao
Descreve o DOM real (elementos, atributos, custom elements) e existe **so pra
calibrar seletores** quando a UI muda; suporta sequencia de clique (`A >>> B`) pra
abrir menus. Nao e usado na operacao normal — uso raro, por excecao.

## Efemero por design
O servidor nao guarda nada em disco: pedidos pendentes vivem so na memoria, e o
ciclo de vida e do host (sobe/derruba junto). A extensao reconecta sozinha quando
o servidor volta.

## Mapa de arquivos

```
gemini_mcp.py              # launcher imune ao CWD (auto-localiza, poe raiz no sys.path)
gemini_bridge/
  server.py                # wiring FastMCP: tools + lifespan que sobe/derruba a Bridge
  bridge.py                # servidor WebSocket, registro de Futures por id, heartbeat
extension/
  manifest.json            # MV3: permissoes, host gemini.google.com e googleusercontent.com
  background.js            # cliente WebSocket, roteamento, keepalive, bypass de CORS
  content.js               # dirige o DOM: fluxo API, blobs
imagens/                   # pasta local onde as imagens sao salvas (uso-geral/ e referencia_3d/)
testar.py                  # teste isolado da ponte+extensao, sem host
.mcp.json                  # registro do MCP no host
```

## Limites honestos

- **Seletores derivam.** O `SEL` em `content.js` e o unico ponto que quebra quando
  o Google muda a UI. Conserto = reapontar seletor.
- **ToS.** Automatizar a web do Gemini fere o Termos; o caminho sancionado e a API
  (Vertex). Detalhe de risco no README.
- **Aba de fundo.** O throttle de aba em background atrasa timer de JS, mas DOM,
  rede e streaming seguem funcionando — ler a resposta na aba escondida e ok.
- **Uma extensao por vez.** A Bridge guarda so a conexao mais recente como cliente
  ativo.
