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

| Ferramenta | Quando usar |
|---|---|
| `gemini_status()` | **Sempre primeiro.** Confirma se a extensão está `conectada` antes de qualquer outra chamada. |
| `reconectar_gemini(ambos)` | Inicia o Chrome com a extensão do gemini-web carregada e abre a aba automaticamente. |
| `pergunta_gemini(tarefa)` | Tarefa avulsa sem contexto fixo. Uma chamada, uma resposta. |
| `gerar_imagem_gemini(prompt, pasta_destino, imagem_precisa)` | Pede ao Gemini para gerar uma imagem a partir de um prompt e a salva localmente (em `uso-geral` ou `referencia_3d`). |
| `configurar_gemini(config, modelo, raciocinio)` | Inicia sessão estilo API: abre chat novo e fixa o system prompt. Chame antes de `consultar_gemini`. |
| `consultar_gemini(tarefa)` | Chamada dentro de sessão configurada: edita a 2ª mensagem e regenera. Requer `configurar_gemini` antes. |
| `selecionar_modelo_gemini(modelo, raciocinio)` | Troca o modelo no meio de uma sessão. Se estiver abrindo chat novo, prefira passar o modelo no `configurar_gemini`. |
| `editar_arquivo_gemini(caminho, instrucao)` | Gemini edita um arquivo e grava **no mesmo arquivo**. Conteúdo não passa pelo host. Commite antes; reverta com `git restore` se precisar. |
| `processar_arquivo_gemini(arquivo_origem, instrucao, arquivo_destino)` | Gemini processa um arquivo e grava o resultado em **arquivo separado**. Retorna o diff — o host não lê nenhum dos dois arquivos. Ideal para reescrever/expandir documentos. |
| `listar_conversas_gemini()` | Lista conversas recentes da barra lateral (título + id em JSON). |
| `abrir_conversa_gemini(conversa_id)` | Abre uma conversa pelo id (da URL) e confirma a URL aberta. |
| `inspecionar_gemini(seletor)` | **Diagnóstico apenas.** Descreve o DOM para recalibrar seletores quando a UI do Gemini mudar. Não use na operação normal. |

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

## Se as ferramentas não aparecerem no host

O servidor HTTP precisa estar rodando antes de o host tentar conectar. Se
`gemini_status()` não aparecer como ferramenta disponível, inicie o servidor:

```bash
# Da raiz do repositório:
powershell -ExecutionPolicy Bypass -File scripts/start-http.ps1
```

Ou manualmente só o gemini-web:

```powershell
$env:GEMINI_TRANSPORT = "http"
python mcp-gemini-web\gemini_mcp.py
```

Aguarde ~3 segundos e recarregue o host. O servidor sobrevive a reloads do
Claude Code — só cai se o terminal for fechado.

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

## Modo HTTP (conexão persistente e portável)

Por padrão o servidor fala **stdio**: o host (Claude Code) o inicia e o segura
pelo pipe. Quando o host recarrega ou re-sincroniza, o servidor morre junto, e é
isso que derruba a conexão. Em **HTTP** o servidor fica de pé sozinho numa porta
e o host apenas se conecta pela URL, sobrevivendo a quedas do host. Como o
streamable-http é padrão MCP, o mesmo servidor passa a ser plugável em qualquer
host com conector MCP (Claude Code, Codex, Antigravity).

```bash
# sobe o servidor HTTP persistente (porta 8775 por padrão)
GEMINI_TRANSPORT=http python gemini_mcp.py
#   Windows PowerShell:  $env:GEMINI_TRANSPORT="http"; python gemini_mcp.py
```

O endpoint fica em `http://127.0.0.1:8775/mcp`. A bridge WebSocket (8765, para a
extensão) sobe sozinha na primeira sessão. Variáveis: `GEMINI_TRANSPORT=http`,
`GEMINI_HTTP_HOST` (padrão 127.0.0.1) e `GEMINI_HTTP_PORT` (padrão 8775). O
registro deixa de ser um comando que o host inicia e vira uma URL que ele conecta:

```json
{ "mcpServers": { "gemini-web": { "type": "http", "url": "http://127.0.0.1:8775/mcp" } } }
```

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
