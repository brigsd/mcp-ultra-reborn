# Pendentes — mcp-ultra-reborn

## 1. Migrar `.mcp.json` para HTTP

O `.mcp.json` raiz ainda registra gemini-web e deepseek-web como processos stdio.
Com os servidores HTTP no ar (porta 8775 e 8776), a entrada vira URL:

```json
"gemini-web":  { "type": "http", "url": "http://127.0.0.1:8775/mcp" }
"deepseek-web": { "type": "http", "url": "http://127.0.0.1:8776/mcp" }
```

`ia-local` e `qwen-controller` continuam stdio (não têm modo HTTP).
Pré-requisito: rodar `scripts/start-http.ps1` antes de abrir o Claude Code.

---

## 2. Testar as novas ferramentas do gemini-web

Três ferramentas adicionadas na última sessão que ainda não foram exercitadas com
o Gemini aberto e a extensão ativa:

- `listar_conversas_gemini` — abre a barra lateral e devolve `[{id, titulo}]`
- `abrir_conversa_gemini(id)` — clica no link e confirma pela URL
- `editar_arquivo_gemini(caminho, instrucao)` — lê o arquivo, manda pro Gemini
  editar, grava de volta; retorna delta de linhas + dica de `git diff`

Teste mínimo: listar → pegar um id → abrir → confirmar URL retornada.
Para editar: usar um arquivo de baixo risco, conferir diff depois.

---

## 3. Plugin Superpowers para Qwen

Criar `C:\Users\tiago\Desktop\superpowers\.qwen-plugin\plugin.json` seguindo o
molde do `.kimi-plugin\plugin.json` (mais próximo: modelo de fora, sem
integração oficial).

O que muda no mapa de ferramentas (`skillInstructions`):
- `AskUserQuestion` → não existe no Qwen; substituir por "apresente as opções
  como lista numerada no chat e aguarde resposta do usuário"
- `Agent` com subagente → o Qwen Chat não tem subagentes; substituir por
  "execute inline, uma etapa por vez, reportando progresso"
- `TodoWrite/TodoList` → não existe; manter como lista markdown no chat
- `Read/Write/Edit/Grep/Glob/Bash` → ferramentas nativas do qwen-controller MCP
  que já temos (`configurar_qwen`, `consultar_qwen`, etc.) mais as do ia-local

Campo `sessionStart` injeta a skill `using-superpowers` igual ao Kimi.
Campo `skills` aponta para `./skills/` (mesma pasta).

Onde registrar no Qwen: ainda a descobrir — depende de como o Qwen Chat aceita
contexto inicial (system prompt, arquivo de contexto, ou extensão). Investigar
na primeira sessão com o Qwen aberto.
