# mcp-ultra-reborn — contexto para IAs

Repositório de servidores MCP locais que permitem delegar tarefas para modelos
externos (Gemini, DeepSeek) sem usar tokens do host, e controlar o Qwen Chat
Desktop via CDP.

## MCPs disponíveis

| Servidor | Tipo | Porta | Para que serve |
|---|---|---|---|
| `gemini-web` | HTTP | 8775 | Delegar tarefas ao Gemini via Chrome |
| `deepseek-web` | HTTP | 8776 | Delegar tarefas ao DeepSeek via Chrome |
| `qwen-controller` | stdio | — | Controlar o Qwen Chat Desktop via CDP |
| `ia-local` | stdio | — | Modelo local via Qwen Coder |

## Iniciar os servidores HTTP (gemini-web e deepseek-web)

**Se `ToolSearch("gemini")` retornar vazio**, o servidor HTTP não está rodando.
Inicie com o Bash tool:

```bash
powershell -ExecutionPolicy Bypass -File scripts/start-http.ps1 &
```

Aguarde ~3 segundos e tente de novo. Os servidores ficam nas portas 8775 (Gemini)
e 8776 (DeepSeek) e sobrevivem a reloads do Claude Code.

A extensão do Chrome também precisa estar conectada. Verifique com
`gemini_status()` — deve retornar `conectada`. Se retornar `desconectada`, a aba
do Gemini não está aberta ou a extensão não está carregada.

## Fluxo para processar documentos sem gastar tokens

Use `processar_arquivo_gemini` quando quiser que o Gemini leia, reescreva ou
expanda um arquivo sem o conteúdo passar pelo contexto do host:

1. Chame `processar_arquivo_gemini(arquivo_origem, instrucao, arquivo_destino)`
2. O servidor lê o arquivo, manda pro Gemini, grava o resultado — zero tokens do host
3. O retorno é só o diff (linhas que mudaram), não o arquivo inteiro
4. Para revisar: `git diff -- <arquivo_destino>`

## Fluxo "API" do Gemini (sessão com prompt fixo)

Para uso repetido com contexto estável:
1. `configurar_gemini(config, modelo)` — abre chat novo, fixa o system prompt
2. `consultar_gemini(tarefa)` — cada chamada edita a 2ª mensagem e regenera (contexto não cresce)

Para tarefa avulsa sem configuração prévia: `pergunta_gemini(tarefa)`.
