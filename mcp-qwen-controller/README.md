# mcp-qwen-controller

Ponte entre um host MCP (Claude Code, Antigravity) e o **Qwen Chat desktop**. O host
chama uma ferramenta, a tarefa é escrita e enviada no Qwen, e a resposta final volta.
O servidor dirige o aplicativo **pelo DOM, via Chrome DevTools Protocol (CDP)**, sem
tocar no mouse ou no teclado do usuário e sem precisar de extensão.

É o complemento do `mcp-qwen-coder`, e na direção oposta: enquanto o `coder` dá ao
Qwen acesso ao terminal e aos arquivos da máquina, o `controller` dá ao host o
controle do Qwen, usando o raciocínio do modelo da conta já autenticada no aplicativo.

## Como funciona

O Qwen Chat desktop é um aplicativo Electron. Iniciado com a porta de depuração
aberta, ele expõe o Chrome DevTools Protocol. A conversa em si vive em um alvo do
tipo *webview* (`chat.qwen.ai`), não na página raiz do aplicativo.

```
host MCP  --pergunta_qwen-->  servidor qwen-controller (local, Python)
                                  |  CDP  127.0.0.1:9222
                                  v
                           webview do Qwen (chat.qwen.ai)  --DOM-->  resposta
```

O servidor lê o DOM e preenche os campos com `Runtime.evaluate`, e clica com um
evento confiável (`Input.dispatchMouseEvent`), por coordenada, como faria um humano.
O clique confiável é a vantagem do CDP sobre uma extensão: ele abre menus, como o
seletor de modelo, que o clique sintético não consegue abrir.

A espera pela resposta é por estabilização: o servidor lê a fase de resposta a cada
segundo e a considera pronta quando o texto para de mudar e o rodapé de ações
(botão de copiar) aparece. O bloco de "pensamento" do modelo é ignorado, de modo que
a leitura corresponde apenas à resposta final.

## Requisito de operação

O Qwen Chat desktop precisa estar **aberto, autenticado e iniciado com a porta de
depuração 9222**. Sem isso, o `qwen_status` retorna `desconectado`.

No Windows, feche o Qwen e reabra-o pela linha de comando (o caminho do executável
pode variar conforme a instalação):

```powershell
& "$env:LOCALAPPDATA\Programs\Qwen\Qwen.exe" --remote-debugging-port=9222
```

Para tornar permanente, edite o atalho do Qwen (Propriedades → Destino) e acrescente
`--remote-debugging-port=9222` ao final do caminho do executável.

## Ferramentas MCP

| Ferramenta | O que faz |
|---|---|
| `qwen_status()` | Diz se o Qwen está acessível (`conectado` / `desconectado`). |
| `pergunta_qwen(tarefa, timeout=180)` | Envia uma tarefa nova e devolve a resposta final. |
| `selecionar_modelo_qwen(modelo)` | Troca o modelo ativo (ex.: `Qwen3.7-Plus`, `Qwen3.7-Max`). |
| `configurar_qwen(config, modelo=None, timeout=180)` | Abre conversa nova e fixa a 1ª mensagem como configuração. |
| `consultar_qwen(tarefa, timeout=180)` | Edita a 2ª mensagem e lê a resposta regenerada. |
| `inspecionar_qwen(seletor="", max=40)` | Diagnóstico de uso excepcional para recalibrar seletores. |

## Fluxo "API": configuração fixa mais consultas

O par `configurar_qwen` mais `consultar_qwen` transforma o chat em um endpoint com
prompt de sistema fixo. O `configurar_qwen` abre uma conversa nova e fixa a primeira
mensagem como configuração; cada `consultar_qwen` edita a segunda mensagem em vez de
enviar uma nova. Como editar uma mensagem regenera a resposta e descarta o que vinha
depois, o contexto permanece em *configuração mais pergunta atual* e não cresce a
cada chamada.

A seleção de modelo pode ser feita de forma avulsa com `selecionar_modelo_qwen` ou
passada diretamente ao `configurar_qwen`. Se o modelo informado não existir, o erro
lista os modelos disponíveis.

## Rodar o servidor

```bash
pip install -r requirements.txt
python qwen_mcp.py
```

Normalmente quem sobe e derruba o servidor é o **host** (via `.mcp.json`). O
`qwen_mcp.py` se auto-localiza, então funciona com qualquer diretório de trabalho
desde que o host aponte para o caminho absoluto dele. Os endereços padrão (host
`127.0.0.1`, porta `9222`) podem ser ajustados por `QWEN_CDP_HOST` e `QWEN_CDP_PORT`.

## Registrar no host

No Claude Code, o `.mcp.json` do repositório raiz já declara este servidor. Em outro
host, aponte `command: python` e `args: ["<caminho absoluto>/qwen_mcp.py"]`.

## Ponto frágil

Os campos e mensagens do Qwen têm classes geradas por build (com sufixos que mudam
entre versões), então a calibração se apoia em atributos estáveis. Se a interface do
Qwen mudar e uma ferramenta parar de achar o campo ou a resposta, o conserto fica em
um lugar só: o objeto `SEL`, no topo de
[`qwen_bridge/driver.js`](qwen_bridge/driver.js).

## Risco

Automatizar a interface do Qwen pela porta de depuração fere os Termos de Serviço; o
caminho sancionado é a API. Como o controle usa a sessão real já autenticada no
aplicativo, o provedor dificilmente distingue esse uso de um uso humano, mas volume
elevado e ritmo regular podem ser detectados. O uso é de responsabilidade do usuário.
