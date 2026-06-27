# mcp-gemini-web

> Parte do repositório [mcp-ultra-reborn](../README.md).

Ponte entre um host MCP (ex.: Antigravity, Claude Code) e o **Gemini web**. O host
chama uma ferramenta, a tarefa é enviada no Gemini, e a resposta volta. Uma
extensão do Chrome dirige o Gemini pelo DOM, sem tocar no mouse ou no teclado e em
uma aba em segundo plano.

## Como funciona

```
host MCP  --ferramenta-->  servidor gemini-web (Python)  --WebSocket 8765-->  extensao  --DOM-->  Gemini
```

O servidor mantém uma ponte WebSocket local. A extensão conecta como cliente,
executa a ação no DOM e devolve o resultado, casado ao pedido por um identificador
único. Para o host, cada ferramenta é síncrona e leva alguns segundos.

## Ferramentas

| Ferramenta | O que faz |
|---|---|
| `gemini_status()` | Diz se a extensão está `conectada`. |
| `pergunta_gemini(tarefa)` | Envia uma tarefa nova (one-shot) e devolve a resposta. |
| `selecionar_modelo_gemini(modelo, raciocinio)` | Escolhe o modelo (`flash-lite`, `flash`, `pro`) e, opcionalmente, o raciocínio (`padrao`, `estendido`). |
| `configurar_gemini(config, modelo, raciocinio)` | Abre um chat novo, escolhe modelo/raciocínio e fixa a 1ª mensagem como configuração. |
| `consultar_gemini(tarefa)` | Chamada estilo API: edita a 2ª mensagem e devolve a resposta regenerada. |
| `listar_conversas_gemini()` | Lista as conversas recentes da barra lateral (título + id), em JSON. |
| `abrir_conversa_gemini(conversa_id)` | Abre uma conversa pelo id e devolve a URL aberta. |
| `inspecionar_gemini(seletor)` | Diagnóstico de DOM. Uso excepcional (ver abaixo). |

## O fluxo "API" (configurar + consultar)

Além do envio simples, o servidor oferece um fluxo que transforma o chat em um
endpoint com prompt de sistema fixo. `configurar_gemini` abre um chat novo,
seleciona o modelo e fixa a primeira mensagem como configuração (o papel e as
instruções do agente). A partir daí, cada `consultar_gemini` realiza uma chamada
**editando a segunda mensagem** do chat: na primeira vez ele a cria, e nas
seguintes reescreve a mesma mensagem.

Como editar uma mensagem no Gemini regenera a resposta e descarta os turnos
seguintes, o contexto permanece em *configuração + pergunta atual* e não cresce a
cada chamada. Isso dá comportamento estável (a configuração é fixa) e chamadas
independentes (sem histórico acumulado). A escolha de modelo e raciocínio cabe no
`configurar_gemini` porque combina com o início do chat; `selecionar_modelo_gemini`
também funciona avulso.

## Gestão de conversas

`listar_conversas_gemini` e `abrir_conversa_gemini` operam na barra lateral. A
chave de tudo é o **id da conversa**, o trecho que aparece na URL
(`gemini.google.com/app/<id>`): ele é estável e é o que você guarda para reabrir
uma conversa depois, sem depender de nada que tenha ficado no contexto da IA.

`listar` devolve um JSON enxuto de `{id, titulo}`; `abrir` recebe um id, clica no
link e confirma pela URL que voltou. Os dois abrem a barra lateral sozinhos se
ela estiver fechada (fechada, os links somem do DOM). Para mexer com conversas
use estas ferramentas, não o `inspecionar_gemini`: o inspecionar despeja o DOM
inteiro e custa caro, estas retornam só o essencial.

Duas limitações conhecidas. A lista de Recentes é virtualizada (scroll infinito),
então `listar` enxerga só as conversas já carregadas, as mais recentes, não o
histórico inteiro. E `abrir` encontra a conversa por id no DOM; se ela não
estiver no trecho carregado, falha avisando, e aí é rolar a barra ou listar de
novo. A identificação é sempre por id ou seletor CSS, nunca por texto, porque
buscar a conversa pelo título derrubou o content script nos testes.

## Rodar e instalar

```bash
pip install -r requirements.txt
python gemini_mcp.py
```

Registre no host pelo `.mcp.json` (o `gemini_mcp.py` se auto-localiza). A extensão:
em `chrome://extensions`, ative o Modo do desenvolvedor, escolha "Carregar sem
compactação" e aponte para `extension/`. Abra `https://gemini.google.com` logado; a
aba pode ficar fixada em segundo plano. `gemini_status()` deve indicar `conectada`.

Para testar a ponte sem o host, `python testar.py` sobe o WebSocket e manda uma
pergunta de teste (não rode junto com o servidor do host: disputam a porta 8765).

## inspecionar_gemini — ferramenta de exceção

`inspecionar_gemini` descreve o DOM real da página (elementos, atributos, texto).
Serve **apenas à calibração** de seletores e deve ser usada **poucas vezes**:
quando o Google atualiza a interface e alguma ação para de funcionar, ela mostra a
estrutura atual para reapontar o objeto `SEL` em
[`extension/content.js`](extension/content.js). Não faz parte da operação normal.

## Ponto frágil

Os seletores de UI mudam quando o Google atualiza o Gemini. O conserto fica
concentrado no objeto `SEL` em [`extension/content.js`](extension/content.js); o
`inspecionar_gemini` ajuda a redescobrir os valores atuais.

## Risco

Automatizar a interface web do Gemini contraria o Termo de Serviço; o caminho
oficial é a API (Vertex). Como usa a sessão já autenticada, o provedor dificilmente
distingue de uso humano, mas volume alto e ritmo robótico chamam atenção. Em conta
corporativa o risco sobe. Uso pessoal, por conta e risco.

## Documentação

- [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md) — como é montado e por quê.
- [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) — modos de falha e diagnóstico.
