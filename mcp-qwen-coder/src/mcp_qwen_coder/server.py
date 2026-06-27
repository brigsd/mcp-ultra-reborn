"""Servidor MCP "IA Web" — dá a uma IA acesso ao terminal local.

Ferramentas expostas:
  - run_command        : executa um comando no shell/CMD
  - change_directory   : muda o diretório de trabalho da sessão
  - get_working_directory
  - list_directory     : lista o conteúdo de uma pasta
  - read_file          : lê o conteúdo de um arquivo
  - write_file         : cria/sobrescreve um arquivo
  - edit_file          : substituição exata de trecho num arquivo
  - get_system_info    : informações do SO/shell/sessão

Transportes:
  - stdio (default): para clientes locais (Claude Desktop/Code)
  - http           : servidor HTTP streamable para uma IA web acessar pela rede
"""

from __future__ import annotations

import json
import os
import platform
import sys

from mcp.server.fastmcp import FastMCP

from .config import settings
from .shell import CommandBlocked, ShellSession

mcp = FastMCP("mcp-qwen-coder")
session = ShellSession(settings)


@mcp.tool()
def run_command(command: str, timeout: int | None = None) -> str:
    """Executa um comando no terminal local (CMD/PowerShell/bash) e retorna a saída.

    A sessão é persistente: o diretório de trabalho definido por
    `change_directory` é mantido entre chamadas. Use `timeout` (segundos) para
    comandos demorados; o limite máximo é controlado por MCP_MAX_TIMEOUT.
    """
    try:
        result = session.run(command, timeout=timeout)
    except CommandBlocked as exc:
        return f"[BLOQUEADO] {exc}"
    return result.to_text()


@mcp.tool()
def change_directory(path: str) -> str:
    """Muda o diretório de trabalho da sessão (relativo ao cwd atual ou absoluto)."""
    try:
        new = session.change_directory(path)
    except (NotADirectoryError, PermissionError) as exc:
        return f"[ERRO] {exc}"
    return f"cwd agora é: {new}"


@mcp.tool()
def get_working_directory() -> str:
    """Retorna o diretório de trabalho atual da sessão."""
    return session.cwd


@mcp.tool()
def list_directory(path: str | None = None) -> str:
    """Lista arquivos e pastas (default: diretório atual da sessão)."""
    try:
        target = session.resolve_path(path) if path else session.cwd
    except PermissionError as exc:
        return f"[ERRO] {exc}"
    if not os.path.isdir(target):
        return f"[ERRO] Não é um diretório: {target}"
    entries = []
    for name in sorted(os.listdir(target)):
        full = os.path.join(target, name)
        kind = "DIR " if os.path.isdir(full) else "FILE"
        try:
            size = os.path.getsize(full) if os.path.isfile(full) else 0
        except OSError:
            size = 0
        entries.append(f"{kind}  {size:>12}  {name}")
    return f"Conteúdo de {target}:\n" + ("\n".join(entries) if entries else "(vazio)")


@mcp.tool()
def read_file(path: str, max_bytes: int = 1_000_000) -> str:
    """Lê e retorna o conteúdo de um arquivo de texto (relativo ao cwd ou absoluto)."""
    try:
        full = session.resolve_path(path)
    except PermissionError as exc:
        return f"[ERRO] {exc}"
    if not os.path.isfile(full):
        return f"[ERRO] Arquivo não encontrado: {full}"
    try:
        with open(full, "r", encoding="utf-8", errors="replace") as fh:
            data = fh.read(max_bytes + 1)
    except OSError as exc:
        return f"[ERRO] {exc}"
    truncated = len(data) > max_bytes
    if truncated:
        data = data[:max_bytes]
    header = f"# {full}" + (" [truncado]" if truncated else "")
    return header + "\n" + data


@mcp.tool()
def write_file(path: str, content: str, create_dirs: bool = True) -> str:
    """Cria ou sobrescreve um arquivo com `content`. Cria pastas-pai se preciso."""
    try:
        full = session.resolve_path(path)
    except PermissionError as exc:
        return f"[ERRO] {exc}"
    if create_dirs:
        parent = os.path.dirname(full)
        if parent:
            os.makedirs(parent, exist_ok=True)
    try:
        with open(full, "w", encoding="utf-8", newline="") as fh:
            fh.write(content)
    except OSError as exc:
        return f"[ERRO] {exc}"
    return f"OK: {len(content)} caracteres escritos em {full}"


@mcp.tool()
def edit_file(path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
    """Substituição exata de texto num arquivo (estilo find-and-replace).

    `old_string` deve ser único no arquivo, a menos que `replace_all=True`.
    """
    try:
        full = session.resolve_path(path)
    except PermissionError as exc:
        return f"[ERRO] {exc}"
    if not os.path.isfile(full):
        return f"[ERRO] Arquivo não encontrado: {full}"
    try:
        with open(full, "r", encoding="utf-8") as fh:
            content = fh.read()
    except OSError as exc:
        return f"[ERRO] {exc}"
    count = content.count(old_string)
    if count == 0:
        return "[ERRO] old_string não encontrado no arquivo."
    if count > 1 and not replace_all:
        return f"[ERRO] old_string aparece {count}x; use replace_all=true ou torne-o único."
    new_content = content.replace(old_string, new_string)
    try:
        with open(full, "w", encoding="utf-8", newline="") as fh:
            fh.write(new_content)
    except OSError as exc:
        return f"[ERRO] {exc}"
    n = count if replace_all else 1
    return f"OK: {n} substituição(ões) em {full}"


@mcp.tool()
def get_system_info() -> str:
    """Retorna informações do sistema, shell e sessão (em JSON)."""
    info = {
        "os": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "hostname": platform.node(),
        "shell_kind": session._resolve_shell_kind(),
        "cwd": session.cwd,
        "user": os.environ.get("USERNAME") or os.environ.get("USER"),
        "allowed_dir": settings.allowed_dir,
        "blocked_patterns": settings.blocked_patterns,
    }
    return json.dumps(info, indent=2, ensure_ascii=False)


def _run_http() -> None:
    """Sobe o servidor HTTP streamable, com autenticação Bearer opcional."""
    import uvicorn
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    token = settings.auth_token

    class BearerAuthMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            if token:
                auth = request.headers.get("authorization", "")
                expected = f"Bearer {token}"
                if auth != expected:
                    return JSONResponse({"error": "unauthorized"}, status_code=401)
            return await call_next(request)

    app = mcp.streamable_http_app()
    if token:
        app.add_middleware(BearerAuthMiddleware)
    else:
        print(
            "[AVISO] MCP_AUTH_TOKEN não definido: o endpoint HTTP está SEM "
            "autenticação. Não exponha à internet sem um token/túnel seguro.",
            file=sys.stderr,
        )

    print(
        f"MCP HTTP em http://{settings.host}:{settings.port}/mcp "
        f"(auth: {'on' if token else 'OFF'})",
        file=sys.stderr,
    )
    uvicorn.run(app, host=settings.host, port=settings.port)


def main() -> None:
    if settings.normalized_transport() == "http":
        _run_http()
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
