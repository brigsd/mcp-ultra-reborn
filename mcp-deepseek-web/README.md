# mcp-deepseek-web

> Parte do repositório [mcp-ultra-reborn](../README.md). Gêmeo do
> [`mcp-gemini-web`](../mcp-gemini-web/), dirigindo o **DeepSeek**.

Ponte entre um host MCP (ex.: Antigravity, Claude Code) e o **DeepSeek web**. O
host chama uma ferramenta, a tarefa é enviada no DeepSeek, e a resposta volta. Uma
extensão do Chrome dirige o DeepSeek pelo DOM, sem tocar no mouse ou no teclado e
em uma aba em segundo plano.

## Como funciona

```
host MCP  --ferramenta-->  servidor deepseek-web (Python)  --WebSocket 8766-->  extensao  --DOM-->  DeepSeek
```

Mesma arquitetura do gemini-web (ponte WebSocket, leitura no DOM, heartbeat e
auto-injeção do content script). Roda na **porta 8766** para não colidir com o
gemini-web (8765).

## Ferramentas

| Ferramenta | O que faz |
|---|---|
| `deepseek_status()` | Diz se a extensão está `conectada`. |
| `pergunta_deepseek(tarefa)` | Envia uma tarefa nova (one-shot) e devolve a resposta. |
| `selecionar_modo_deepseek(pensamento, pesquisa)` | Liga/desliga os toggles 'Pensamento Profundo' e 'Pesquisa inteligente'. |
| `configurar_deepseek(config, modo, pensamento, pesquisa)` | Abre um chat novo, escolhe o modo e fixa a 1ª mensagem como configuração. |
| `consultar_deepseek(tarefa)` | Chamada estilo API: edita a 2ª mensagem e devolve a resposta. |
| `inspecionar_deepseek(seletor)` | Diagnóstico de DOM. Uso excepcional (ver abaixo). |

## O fluxo "API" (configurar + consultar)

Igual ao gemini-web: `configurar_deepseek` abre um chat novo e fixa a primeira
mensagem como configuração (prompt de sistema); cada `consultar_deepseek` edita a
segunda mensagem, mantendo o contexto em *configuração + pergunta atual*. No
DeepSeek a edição cria uma nova versão da mesma mensagem (indicador "2 / 2" na UI),
e o contexto ativo é sempre a configuração mais a versão atual.

## Modos e toggles

O DeepSeek separa dois tipos de controle, e o servidor respeita essa diferença:

- **Modo** (`rapido`, `especialista`, `visao`): só pode ser escolhido no **início**
  de um chat; a UI trava depois da primeira mensagem. Por isso o modo é parâmetro
  do `configurar_deepseek` (padrão `especialista`). O `visao` existe para uso com
  imagens.
- **Toggles** (`pensamento` = Pensamento Profundo, `pesquisa` = Pesquisa
  inteligente): podem ser ligados/desligados a qualquer momento, via
  `selecionar_modo_deepseek` ou já no `configurar_deepseek`.

## Rodar e instalar

```bash
pip install -r requirements.txt
python deepseek_mcp.py
```

Registre no host pelo `.mcp.json`. A extensão: `chrome://extensions` → Modo do
desenvolvedor → "Carregar sem compactação" → pasta `extension/`. Abra
`https://chat.deepseek.com` logado; a aba pode ficar fixada em segundo plano.

## inspecionar_deepseek — ferramenta de exceção

`inspecionar_deepseek` descreve o DOM real da página. Serve **apenas à calibração**
de seletores e deve ser usada **poucas vezes**: o DeepSeek não usa
`aria-label`/`data-test-id` e seus botões são `div` de classe ofuscada, então
quando a interface muda esta ferramenta ajuda a reapontar o objeto `SEL` em
[`extension/content.js`](extension/content.js). Suporta busca por texto
(`texto:Especialista`) e sequência de clique (`A >>> B`). Não faz parte da operação
normal.

## Diferenças de código para o gemini-web

O composer e o campo de edição são `<textarea>` (setter nativo + evento `input`),
e o envio é por Enter. Como o DeepSeek não tem rótulos, vários elementos são
achados por texto, o **botão de editar** é identificado pelo `path` do ícone de
lápis no SVG, e o estado dos toggles é lido por `aria-pressed`.

## Ponto frágil

Os seletores em `SEL` no topo de [`extension/content.js`](extension/content.js).
Como o DeepSeek ofusca as classes, a calibração depende mais do
`inspecionar_deepseek` quando a interface muda.

## Risco

Automatizar a interface web do DeepSeek contraria o Termo de Serviço; o caminho
oficial é a API. Uso pessoal, por conta e risco.
