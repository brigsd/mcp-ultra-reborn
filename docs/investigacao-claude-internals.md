# Investigação: Internals do Claude Code
> Extraído do binário `~/.local/share/claude/versions/2.1.185` (Bun SEA, PE32+, 225 MB)
> Método: extração de strings ASCII da seção `.bun` (144 MB de bytecode JavaScriptCore)

---

## Estrutura do binário

Claude Code é um executável nativo Windows compilado com **Bun** (não Electron, não Node puro).
A seção `.bun` do PE contém bytecode JavaScriptCore — não é JS legível, mas strings ficam intactas.
80 762 strings ASCII extraídas; seção `.text` é código de máquina x86-64.

Seções PE relevantes:
- `.text`  — 56 MB — código de máquina compilado
- `.rdata` — 22 MB — dados somente leitura (strings constantes, tabelas)
- `.bun`   — 144 MB — bundle JS compilado em bytecode Bun/JSC

---

## Rede

Processo `claude` (PID 16248) mantém **múltiplas conexões simultâneas** para um único IP:

```
160.79.104.10:443  (confirmado: api.anthropic.com)
```

Todas as conexões são HTTPS/TLS. O IP `160.79.104.10` resolve para `api.anthropic.com`.
Cada subagente usa uma stream HTTP/2 separada dentro da mesma conexão multiplexada —
não abre TCP nova por chamada.

Segundo processo `claude` (PID 17584) conectado a:
- `4.228.31.149:443`  — possivelmente serviço Azure (telemetria ou OAuth)
- `34.149.66.137:443` e `34.149.66.154:443` — Google Cloud (possivelmente CDN de docs)

---

## Endpoints internos encontrados

```
https://api.anthropic.com/v1/design/mcp        ← NÃO documentado publicamente
https://claude.ai/oauth/claude-code-client-metadata
https://code.claude.com/docs/en
https://platform.claude.com/llms.txt

/v1/messages?beta=true
/v1/messages/batches?beta=true
/v1/messages/batches/
/v1/messages/count_tokens?beta=true
```

O endpoint `/v1/design/mcp` é suspeito: não aparece na documentação pública da API Anthropic.
Pode ser um endpoint interno de configuração de MCP usado pelo Claude Code para se registrar
como host MCP, ou um endpoint de design/scaffolding de servidores MCP.

---

## System prompts dos subagentes (strings literais do bundle)

```
You are a Claude agent, built on Anthropic's Claude Agent SDK.
```
Este é o system prompt que subagentes recebem — diferente do Claude Code principal.

```
You are a subagent spawned by a workflow orchestration script.
Use the tools available to complete the task.
```
System prompt dos subagentes do Workflow tool.

```
You are orchestrating a large, parallelizable change across this codebase.
```
Prompt de modo de orquestração (possivelmente ultracode ou worktree mode).

```
Internal subagent for workflow script orchestration.
```
Label interno do tipo de subagente de workflow.

---

## Tipos de subagente (`subagent_type`)

Encontrados nas strings:

- `worker`         — subagente padrão, contexto zerado
- `fork`           — herda o contexto da sessão pai (único tipo que faz isso)
- `fork-context-ref` — referência de contexto para fork, com UUID do pai
- `subagent_fork_coordinator_mode`
- `subagent_fork_remote_isolation`
- `subagent_recursive_fork`

Strings que descrevem o comportamento:

```
Any agent other than a fork starts with zero context.
(except subagent_type: "fork", which inherits your context)
Failed to record fork-context-ref:
[fork-context-ref] parent uuid
```

Ou seja: `fork` é o único tipo que não começa do zero — copia o contexto inteiro do pai.

---

## API Beta: BetaManagedAgents

Encontrado no bundle: referências a uma API beta chamada `BetaManagedAgents`, ainda não
documentada publicamente. Tipos identificados:

```
anthropic.BetaManagedAgentsAgentToolset20260401Params
anthropic.BetaManagedAgentsGitHubRepositoryResourceParams
anthropic.BetaManagedAgentsMCPToolsetParams
anthropic.BetaManagedAgentsTokenEndpointAuthPostParam
anthropic.BetaManagedAgentsUserMessageEventParams
anthropic.BetaManagedAgentsTextBlockParam
anthropic.BetaCloudConfigParamsNetworkingUnion
anthropic.BetaUnrestrictedNetworkParam
```

O sufixo `20260401` em `AgentToolset20260401` sugere uma data de versão: **1 de abril de 2026**.
Isso indica que a Anthropic está construindo uma camada de orquestração de agentes gerenciados
na própria API, com suporte a MCP toolsets, GitHub repos, e configuração de rede.

---

## Ultracode

```
ultracode: xhigh effort + dynamic workflow orchestration (this session only)
Whether ultracode (xhigh effort plus standing dynamic-workflow orchestration) is active
for the session. Set per session via the `ultracode` settings key.
```

É uma flag de sessão, não um modelo diferente. Ativa esforço `xhigh` e orquestração via
Workflow tool automaticamente.

---

## Observações sobre o que parece errado

1. **`/v1/design/mcp`** não existe na documentação pública. Pode ser um endpoint de
   configuração ou scaffolding que o Claude Code usa internamente sem expor ao usuário.

2. **`You are a Claude agent, built on Anthropic's Claude Agent SDK`** — o system prompt
   dos subagentes cita o "Claude Agent SDK" como se fosse um produto separado. Isso sugere
   que subagentes não são simplesmente "outra chamada de API" mas rodam num ambiente
   ligeiramente diferente, talvez com ferramentas ou limites distintos.

3. **`subagent_fork_remote_isolation`** — sugere que forks podem rodar remotamente (não só
   localmente). Combinado com o PID 17584 conectado a IPs de nuvem, pode indicar que alguns
   subagentes rodam em infraestrutura Anthropic, não na máquina local.

4. **`MountPath: "/workspace/repo"`** — path Unix num ambiente Windows. Indica que parte
   da execução acontece num container ou VM Linux remoto.

5. O bundle contém strings de **ArmA 3 SQF scripting** (addAction, addBackpack, etc.) —
   provavelmente documentação ou exemplos de código que entraram no bundle por alguma razão.
   Não é relevante mas é estranho.

---

## Referências

- Bundle extraído: `~/.local/share/claude/versions/2.1.185` (seção `.bun`)
- Strings completas: `bun_extracted/strings.txt` (80 762 entradas)
- Script de extração: `scratchpad/decode_bun.py`
