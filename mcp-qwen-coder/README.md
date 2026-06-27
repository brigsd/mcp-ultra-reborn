# mcp-qwen-coder

> Parte do repositório [mcp-ultra-reborn](../README.md).

Servidor **MCP (Model Context Protocol)** que dá a uma IA acesso ao seu
**terminal local (CMD / PowerShell / bash)** e a torna capaz de agir como um
**agente local** — parecido com o que o Claude Code e o Antigravity fazem.

A sessão é **persistente**: o diretório de trabalho é mantido entre comandos,
então a IA pode navegar pelo sistema, rodar builds, scripts, git, etc.

> ⚠️ **Aviso de segurança.** Este servidor executa comandos arbitrários na sua
> máquina. Trate-o como acesso total ao seu terminal. Só exponha o modo HTTP à
> rede/internet com `MCP_AUTH_TOKEN` definido e, de preferência, atrás de um
> túnel seguro (Cloudflare Tunnel, ngrok, VPN). Para limitar o alcance use
> `MCP_ALLOWED_DIR` (jail) e `MCP_BLOCKED_PATTERNS`.
> Se preferivel você pode dar acesso a desktop apenas (recomendavel) ou ao computador inteiro (tenha cuidado e monitore o cmd e o qwen em si)

## Ferramentas expostas

| Ferramenta | O que faz |
|---|---|
| `run_command` | Executa um comando no shell e retorna stdout/stderr/exit code |
| `change_directory` | Muda o diretório de trabalho da sessão (persistente) |
| `get_working_directory` | Diretório de trabalho atual |
| `list_directory` | Lista arquivos/pastas |
| `read_file` | Lê o conteúdo de um arquivo de texto |
| `write_file` | Cria ou sobrescreve um arquivo |
| `edit_file` | Substituição exata de trecho num arquivo (find-and-replace) |
| `get_system_info` | SO, shell, usuário, cwd, config de segurança |

## Instalação

```bash
# (recomendado) crie um ambiente virtual
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Linux/mac: source .venv/bin/activate

pip install -r requirements.txt
# ou instale como pacote (cria o comando `mcp-qwen-coder`):
pip install -e .
```

## Como rodar

### 1) Modo local (stdio) — para Claude Desktop / Claude Code

Este é o modo mais seguro: a IA roda no seu próprio computador e fala com o
servidor por stdin/stdout.

Configuração no Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "ia-local": {
      "command": "python",
      "args": ["-m", "mcp_qwen_coder.server"],
      "cwd": "C:/caminho/para/mcp-ultra-reborn/mcp-qwen-coder/src",
      "env": { "MCP_TRANSPORT": "stdio", "MCP_SHELL": "auto" }
    }
  }
}
```

No Claude Code:

```bash
claude mcp add ia-local -- python -m mcp_qwen_coder.server
```

No **Qwen Chat (app desktop)** — adicione um servidor MCP do tipo **STDIO**.
Usando `uvx` (recomendado: não depende de um venv específico), o comando é `uvx`
e os parâmetros são `--from <caminho-do-projeto> mcp-qwen-coder`:

```json
{
  "mcpServers": {
    "ia-local": {
      "command": "uvx",
      "args": ["--from", "C:/Users/voce/mcp-ultra-reborn/mcp-qwen-coder", "mcp-qwen-coder"],
      "env": {
        "MCP_SHELL": "auto",
        "MCP_START_DIR": "C:/Users/voce/Desktop/qwen-sandbox",
        "MCP_ALLOWED_DIR": "C:/Users/voce/Desktop/qwen-sandbox"
      }
    }
  }
}
```

> ⚠️ A jaula `MCP_ALLOWED_DIR` restringe as ferramentas de arquivo
> (`read_file`/`write_file`/`edit_file`/`change_directory`), mas **não** o
> `run_command`: o shell pode acessar caminhos absolutos fora da pasta. Não
> confie nela como isolamento forte de um modelo não supervisionado.

Para rodar **várias instâncias logadas** do Qwen Chat ao mesmo tempo (base de um
esquema multi-agente), veja [docs/multi-instancia-qwen.md](docs/multi-instancia-qwen.md).

### 2) Modo HTTP — para uma IA *web* acessar pela rede

```bash
# defina um token forte!
export MCP_TRANSPORT=http
export MCP_AUTH_TOKEN="troque-por-um-token-forte"
export MCP_HOST=0.0.0.0
export MCP_PORT=8000
python -m mcp_qwen_coder.server
```

O endpoint MCP fica em `http://<host>:8000/mcp`. Clientes (ex.: conectores de
IA web) devem enviar o header `Authorization: Bearer <seu-token>`.

Para acessar de fora da sua máquina com segurança, use um túnel:

```bash
cloudflared tunnel --url http://localhost:8000
# ou
ngrok http 8000
```

E aponte a IA web para a URL pública gerada + `/mcp`.

## Configuração (variáveis de ambiente)

Veja `.env.example`. Principais:

| Variável | Padrão | Descrição |
|---|---|---|
| `MCP_TRANSPORT` | `stdio` | `stdio` ou `http` |
| `MCP_HOST` / `MCP_PORT` | `127.0.0.1` / `8000` | endereço HTTP |
| `MCP_AUTH_TOKEN` | — | token Bearer exigido no HTTP |
| `MCP_SHELL` | `auto` | `auto`/`cmd`/`powershell`/`bash`/`sh` |
| `MCP_DEFAULT_TIMEOUT` | `60` | timeout padrão (s) |
| `MCP_MAX_TIMEOUT` | `600` | teto de timeout (s) |
| `MCP_MAX_OUTPUT_CHARS` | `100000` | corta saídas gigantes |
| `MCP_START_DIR` | cwd | diretório inicial da sessão |
| `MCP_ALLOWED_DIR` | — | jail: restringe a árvore acessível |
| `MCP_BLOCKED_PATTERNS` | — | regex CSV de comandos proibidos |

## Roadmap

O Worker já entrega execução de comandos, navegação e edição de arquivos
(read/write/edit). Próximos passos sugeridos: busca de conteúdo (grep) e de
arquivos (glob) dedicadas, leitura de arquivo paginada (offset/limite de
linhas), operações git dedicadas e busca na web — para se aproximar ainda mais
de um agente completo como o Claude Code.
