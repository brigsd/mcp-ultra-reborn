# mcp-ultra-reborn

Coleção de servidores **MCP (Model Context Protocol)** locais. Cada subpasta é um
servidor independente, com o seu próprio `README.md`, e em conjunto eles formam um
conjunto de peças para construir uma IA capaz de agir como agente na máquina.

## Duas abordagens

Os servidores deste repositório resolvem a relação entre IA e agente por dois
caminhos complementares.

O primeiro é **expor a máquina local a uma IA**: o servidor MCP fornece ao modelo
acesso ao terminal e ao sistema de arquivos, de modo que ele próprio execute ações
no computador. É o caso do `mcp-qwen-coder`.

O segundo é **delegar raciocínio a uma IA web**: um agente host, como o Claude Code
ou o Antigravity, encaminha uma tarefa a um modelo disponível na web e recebe a
resposta, utilizando-o como capacidade de raciocínio adicional. É o caso do
`mcp-gemini-web`, do `mcp-deepseek-web` e do `mcp-qwen-controller`, este último
dirigindo o aplicativo Qwen Chat desktop.

As duas abordagens podem ser combinadas: o agente resolve localmente o que é
simples e delega ao Gemini, ao DeepSeek ou ao Qwen as tarefas que exigem maior
capacidade de raciocínio, reservando o recurso mais custoso para quando ele é de
fato necessário.

## Os servidores

| Servidor | Abordagem | Porta | README |
|---|---|---|---|
| `mcp-qwen-coder` | acesso local | — (stdio/HTTP) | [↗](mcp-qwen-coder/README.md) |
| `mcp-gemini-web` | delegação web | 8765 | [↗](mcp-gemini-web/README.md) |
| `mcp-deepseek-web` | delegação web | 8766 | [↗](mcp-deepseek-web/README.md) |
| `mcp-qwen-controller` | delegação web (app desktop) | CDP 9222 | [↗](mcp-qwen-controller/README.md) |

### mcp-qwen-coder — acesso ao terminal e aos arquivos

Concede a uma IA acesso ao terminal e ao sistema de arquivos da máquina,
permitindo que ela atue como um agente local. Foi pensado para o Qwen Chat desktop,
mas funciona com qualquer host MCP. A sessão é persistente: o diretório de trabalho
é mantido entre comandos, o que permite navegar pelo sistema, rodar builds e
executar scripts em sequência.

As ferramentas expostas são `run_command`, `change_directory`,
`get_working_directory`, `list_directory`, `read_file`, `write_file`, `edit_file` e
`get_system_info`. O servidor opera em dois transportes: **stdio**, para um host
local, e **HTTP**, para uma IA web acessá-lo pela rede, neste caso com token Bearer
e, idealmente, atrás de um túnel seguro. Há ainda uma restrição opcional de
diretório (`MCP_ALLOWED_DIR`) e uma lista de comandos bloqueados, mas a restrição
de diretório não se aplica ao `run_command` e, portanto, não constitui isolamento
forte. O README do servidor descreve também como executar várias instâncias
logadas do Qwen, por meio da clonagem de perfil, para um esquema multi-agente.

### mcp-gemini-web e mcp-deepseek-web — delegação a uma IA web

Permitem que um host encaminhe uma tarefa a um modelo web e receba a resposta. A
interação ocorre pelo DOM da página, sem uso do mouse ou do teclado físicos, em uma
aba em segundo plano, de modo que o uso do computador não é interrompido.

Cada um oferece três níveis de uso. O envio simples (`pergunta_gemini` /
`pergunta_deepseek`) faz uma pergunta avulsa. A seleção de capacidade escolhe o
modelo ou modo (`selecionar_modelo_gemini`; no DeepSeek, o modo no `configurar` mais
os toggles de `selecionar_modo_deepseek`). E o fluxo "API" (`configurar_*` mais
`consultar_*`) fixa um prompt de sistema e faz chamadas com contexto enxuto. O
estado da conexão sai de `gemini_status` / `deepseek_status`.

O fluxo "API" transforma o chat em um endpoint com prompt de sistema fixo:
`configurar_*` abre um chat novo e fixa a primeira mensagem como configuração, e
cada `consultar_*` edita a segunda mensagem em vez de enviar uma nova. Como editar
regenera a resposta e descarta o que vinha depois, o contexto permanece em
*configuração + pergunta atual* e não cresce a cada chamada. Os detalhes de modelo,
modo e limitações estão no README de cada servidor.

Cada servidor inclui ainda um `inspecionar_*`, ferramenta de **diagnóstico de uso
excepcional**: serve apenas para calibrar os seletores quando o site muda de
interface, e não para a operação normal.

### mcp-qwen-controller — delegação ao Qwen Chat desktop

Segue a mesma ideia de delegação, mas o alvo é o **aplicativo Qwen Chat desktop**, e
não uma aba do navegador. Por ser um aplicativo Electron iniciado com a porta de
depuração aberta, o servidor o controla diretamente pelo Chrome DevTools Protocol,
sem extensão. A conversa vive em um *webview* (`chat.qwen.ai`) dentro do aplicativo.

A superfície de ferramentas é a mesma dos demais: `pergunta_qwen` para o envio
simples, `selecionar_modelo_qwen` para trocar o modelo, o par `configurar_qwen` mais
`consultar_qwen` para o fluxo "API", `qwen_status` para o estado e `inspecionar_qwen`
para a calibração excepcional. O requisito de operação é que o Qwen desktop esteja
aberto, autenticado e iniciado com `--remote-debugging-port=9222`.

## Arquitetura dos servidores de delegação web

Os dois seguem a mesma arquitetura:

```
host MCP  ──tool──>  servidor (Python)  ──WebSocket──>  extensao Chrome  ──DOM──>  IA web
```

Quando o host chama `pergunta_*` com a tarefa, o servidor MCP, que mantém uma ponte
WebSocket local, gera um identificador único e aguarda (long-poll) a resposta
correspondente a esse identificador. A extensão, conectada como cliente WebSocket,
escreve a tarefa no campo da página, envia, acompanha a resposta enquanto ela é
gerada e, quando o texto se estabiliza, devolve o resultado. O identificador
associa cada resposta ao pedido que a originou.

Para o host, o resultado é uma ferramenta síncrona que leva alguns segundos. Cada
servidor utiliza uma porta própria (8765 para o Gemini, 8766 para o DeepSeek), de
modo que os dois podem operar simultaneamente. A ausência de rastros perante o
provedor decorre do uso da sessão real, já autenticada no navegador, e não de
qualquer manipulação de entrada.

Alguns aspectos exigiram tratamento específico na implementação. O service worker
do Chrome (Manifest V3) hiberna após cerca de 30 segundos, o que derrubaria a
conexão; por isso o servidor envia um ping a cada 20 segundos e a extensão mantém
um alarme de reconexão. Além disso, recarregar a extensão deixa o content script
órfão na aba aberta, de modo que o background o reinjeta automaticamente quando
necessário.

A limitação que permanece é a dependência dos seletores de interface, que mudam
quando o site é atualizado. A correção, nesse caso, concentra-se em um único ponto:
o objeto `SEL`, no início do `content.js` de cada extensão.

O `mcp-qwen-controller` adota um transporte diferente. Em vez de extensão e
WebSocket, o servidor fala Chrome DevTools Protocol direto com o webview do
aplicativo: lê o DOM e preenche os campos com `Runtime.evaluate` e clica por
coordenada com um evento confiável (`Input.dispatchMouseEvent`). Esse clique
confiável abre menus, como o seletor de modelo, que um clique sintético não abriria.
A espera pela resposta é por estabilização do texto, ignorando o bloco de pensamento
do modelo e confirmando o fim pelo rodapé de ações. Os seletores, aqui, ficam no
objeto `SEL` no início do `qwen_bridge/driver.js`.

## Instalação e registro

### 1. Instalar as dependências

A raiz mantém um ambiente virtual compartilhado e um `requirements.txt` que reúne
os quatro servidores, com o `mcp-qwen-coder` como pacote editável:

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate
pip install -r requirements.txt
```

Cada subpasta também possui o seu próprio `requirements.txt`, caso prefira manter
ambientes separados por servidor.

### 2. Registrar no host

No **Claude Code**, o [`.mcp.json`](.mcp.json) da raiz já declara os quatro
servidores (`gemini-web`, `deepseek-web`, `ia-local` e `qwen-controller`). Basta
abrir esta pasta como projeto: o Claude Code os detecta automaticamente e solicita
aprovação.

> O host precisa utilizar o mesmo interpretador Python em que as dependências foram
> instaladas. Ative o ambiente virtual antes de iniciar o host, ou aponte o campo
> `command` para o Python do ambiente. A falha mais comum de conexão decorre de o
> host usar outro Python, sem as dependências.

Em outros hosts (Claude Desktop, Antigravity, Qwen Chat), a configuração reside no
próprio host, e não no repositório. Utilize os trechos de configuração presentes no
README de cada subpasta.

### 3. Instalar a extensão (servidores de delegação web)

Em `chrome://extensions`, ative o Modo do desenvolvedor, escolha "Carregar sem
compactação" e selecione a pasta `extension/` do servidor desejado. Em seguida,
abra a página da IA já autenticada (`gemini.google.com` ou `chat.deepseek.com`),
que pode permanecer fixada em segundo plano. A ferramenta `*_status` deve então
indicar `conectada`.

### 4. Preparar o Qwen desktop (mcp-qwen-controller)

O `mcp-qwen-controller` não usa extensão. Em vez disso, o aplicativo Qwen Chat
desktop precisa estar aberto, autenticado e iniciado com a porta de depuração:
`--remote-debugging-port=9222`. Com isso, `qwen_status` deve indicar `conectado`. Os
detalhes de como iniciar o aplicativo com esse argumento estão no
[README do servidor](mcp-qwen-controller/README.md).

## Uso

Com os servidores registrados, o host invoca as ferramentas como quaisquer outras.
As ferramentas `gemini_status` e `deepseek_status` confirmam que a extensão está
conectada; `pergunta_gemini` e `pergunta_deepseek` encaminham a tarefa e devolvem a
resposta; e `run_command`, `read_file` e `edit_file`, entre outras, permitem ao
agente atuar localmente por meio do `mcp-qwen-coder`.

## Segurança e conformidade

O `mcp-qwen-coder` executa comandos arbitrários e deve ser tratado como
acesso integral ao terminal. O modo HTTP só deve ser exposto com `MCP_AUTH_TOKEN`
definido e atrás de um túnel seguro, lembrando que a restrição de diretório não
cobre o `run_command`.

Os servidores de delegação web automatizam a interface do Gemini, do DeepSeek e do
Qwen, o que contraria os respectivos Termos de Serviço; o caminho oficialmente
suportado é a API. Como utilizam a sessão já autenticada, o provedor dificilmente
distingue esse uso de um uso humano, mas volume elevado e padrões regulares de uso
podem ser detectados, e o risco é maior em contas corporativas. O uso é de
responsabilidade do usuário.

## Estado atual

O `mcp-qwen-coder` tem as ferramentas de comando, navegação e manipulação de
arquivos prontas; o esquema de múltiplas instâncias ainda requer validação, como
descrito em seu README. O `mcp-gemini-web` e o `mcp-deepseek-web` foram testados de
ponta a ponta no Claude Code, incluindo a seleção de modelo/modo e o fluxo "API"
(`configurar` mais `consultar` com edição da segunda mensagem). O
`mcp-qwen-controller` teve o controlador validado diretamente via CDP (envio simples,
seleção de modelo, e o fluxo `configurar` mais `consultar` com edição), e falta a
validação ponta a ponta com o servidor já registrado no host.
