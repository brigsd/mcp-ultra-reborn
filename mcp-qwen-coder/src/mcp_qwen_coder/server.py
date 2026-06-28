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

import fnmatch
import json
import os
import platform
import re
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .config import settings
from .planner import PlanManager
from .shell import CommandBlocked, ShellSession

mcp = FastMCP("mcp-qwen-coder")
session = ShellSession(settings)
planner = PlanManager(session.cwd)


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


# ── Novas ferramentas avançadas ──────────────────────────────────────────

# Pastas ignoradas durante varredura recursiva
_IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", ".nuxt", "coverage", ".tox",
    ".mypy_cache", ".pytest_cache", "egg-info",
}


@mcp.tool()
def grep_search(
    pattern: str,
    path: str | None = None,
    is_regex: bool = False,
    case_insensitive: bool = False,
    include_globs: list[str] | None = None,
    max_results: int = 50,
) -> str:
    """Busca um padrão (texto literal ou regex) em todos os arquivos de uma árvore.

    Retorna arquivo, número da linha e conteúdo para cada match (limitado a
    max_results). Útil para encontrar onde uma função é usada, onde um bug
    pode estar, etc.

    Args:
        pattern: texto ou regex a buscar.
        path: diretório raiz da busca (default: cwd).
        is_regex: se True, trata pattern como regex.
        case_insensitive: busca case-insensitive.
        include_globs: filtros de arquivo (ex: ["*.py", "*.js"]).
        max_results: máximo de resultados (default 50).
    """
    try:
        root = session.resolve_path(path) if path else session.cwd
    except PermissionError as exc:
        return f"[ERRO] {exc}"
    if not os.path.isdir(root):
        return f"[ERRO] Não é um diretório: {root}"

    flags = re.IGNORECASE if case_insensitive else 0
    try:
        compiled = re.compile(pattern, flags) if is_regex else None
    except re.error as exc:
        return f"[ERRO] Regex inválida: {exc}"

    matches: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _IGNORE_DIRS]
        for fname in filenames:
            if include_globs:
                if not any(fnmatch.fnmatch(fname, g) for g in include_globs):
                    continue
            fpath = os.path.join(dirpath, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                    for lineno, line in enumerate(fh, 1):
                        hit = False
                        if compiled:
                            hit = bool(compiled.search(line))
                        else:
                            hay = line.lower() if case_insensitive else line
                            needle = pattern.lower() if case_insensitive else pattern
                            hit = needle in hay
                        if hit:
                            rel = os.path.relpath(fpath, root)
                            matches.append(f"{rel}:{lineno}: {line.rstrip()}")
                            if len(matches) >= max_results:
                                break
            except (OSError, UnicodeDecodeError):
                continue
            if len(matches) >= max_results:
                break
        if len(matches) >= max_results:
            break

    if not matches:
        return f"Nenhum resultado para '{pattern}' em {root}"
    header = f"Resultados para '{pattern}' em {root} ({len(matches)} match(es)):\n"
    return header + "\n".join(matches)


@mcp.tool()
def find_files(
    pattern: str,
    path: str | None = None,
    max_results: int = 100,
) -> str:
    """Localiza arquivos por nome/extensão usando glob recursivo.

    Exemplos de pattern: "*.py", "test_*.js", "README*", "**/*.tsx".

    Args:
        pattern: padrão glob (ex: "*.py").
        path: diretório raiz da busca (default: cwd).
        max_results: máximo de resultados (default 100).
    """
    try:
        root = Path(session.resolve_path(path) if path else session.cwd)
    except PermissionError as exc:
        return f"[ERRO] {exc}"
    if not root.is_dir():
        return f"[ERRO] Não é um diretório: {root}"

    results: list[str] = []
    for match in root.rglob(pattern):
        # Ignora pastas bloqueadas
        parts = match.relative_to(root).parts
        if any(p in _IGNORE_DIRS for p in parts):
            continue
        kind = "DIR " if match.is_dir() else "FILE"
        try:
            size = match.stat().st_size if match.is_file() else 0
        except OSError:
            size = 0
        rel = match.relative_to(root)
        results.append(f"{kind}  {size:>10}  {rel}")
        if len(results) >= max_results:
            break

    if not results:
        return f"Nenhum arquivo encontrado para '{pattern}' em {root}"
    header = f"Arquivos para '{pattern}' em {root} ({len(results)} resultado(s)):\n"
    return header + "\n".join(results)


@mcp.tool()
def read_file_lines(
    path: str,
    start_line: int = 1,
    end_line: int | None = None,
) -> str:
    """Lê um trecho de um arquivo por intervalo de linhas (1-indexed, inclusivo).

    Ideal para arquivos grandes: evita estourar o contexto lendo só o necessário.
    Se end_line não for informado, retorna 200 linhas a partir de start_line.

    Args:
        path: caminho do arquivo (relativo ao cwd ou absoluto).
        start_line: primeira linha a retornar (1-indexed, default 1).
        end_line: última linha a retornar (inclusivo). Default: start_line + 199.
    """
    try:
        full = session.resolve_path(path)
    except PermissionError as exc:
        return f"[ERRO] {exc}"
    if not os.path.isfile(full):
        return f"[ERRO] Arquivo não encontrado: {full}"

    try:
        with open(full, "r", encoding="utf-8", errors="replace") as fh:
            all_lines = fh.readlines()
    except OSError as exc:
        return f"[ERRO] {exc}"

    total = len(all_lines)
    if end_line is None:
        end_line = min(start_line + 199, total)
    start_line = max(1, start_line)
    end_line = min(end_line, total)

    if start_line > total:
        return f"[ERRO] start_line ({start_line}) maior que o total de linhas ({total})"

    selected = all_lines[start_line - 1 : end_line]
    numbered = []
    for i, line in enumerate(selected, start_line):
        numbered.append(f"{i:>6}: {line.rstrip()}")

    header = f"# {full} — linhas {start_line}-{end_line} de {total}\n"
    return header + "\n".join(numbered)


# Regex simples para extrair definições de código por linguagem
_SYMBOL_PATTERNS = {
    ".py": re.compile(r"^\s*(class |def |async def )(\w+)"),
    ".js": re.compile(r"(?:^|\s)(function |class |const |let |var |export (?:default )?(?:function |class )?)(\w+)"),
    ".ts": re.compile(r"(?:^|\s)(function |class |const |let |var |export (?:default )?(?:function |class )?|interface |type |enum )(\w+)"),
    ".java": re.compile(r"(?:public |private |protected )?(?:static )?(?:class |interface |enum |void |int |String |boolean )(\w+)"),
    ".go": re.compile(r"^(?:func |type )(\w+)"),
    ".rs": re.compile(r"^(?:pub )?(?:fn |struct |enum |trait |impl |type |const |static )(\w+)"),
    ".c": re.compile(r"^(?:static |extern )?(?:void |int |char |float |double |struct |enum )\**\s*(\w+)\s*\("),
    ".cpp": re.compile(r"^(?:static |extern |virtual )?(?:void |int |char |float |double |struct |class |enum |auto )\**\s*(\w+)"),
    ".h": re.compile(r"^(?:static |extern )?(?:void |int |char |float |double |struct |enum )\**\s*(\w+)"),
}

_CODE_EXTS = set(_SYMBOL_PATTERNS.keys())


@mcp.tool()
def index_codebase(
    path: str | None = None,
    max_depth: int = 5,
) -> str:
    """Mapeia a estrutura completa do projeto: árvore de diretórios e símbolos de código.

    Percorre a árvore até max_depth níveis, ignora pastas comuns (.git,
    node_modules, etc.) e extrai definições de funções/classes/tipos dos
    arquivos de código encontrados. Use antes de começar a trabalhar num
    projeto para entender a arquitetura.

    Args:
        path: diretório raiz (default: cwd).
        max_depth: profundidade máxima de varredura (default 5).
    """
    try:
        root = session.resolve_path(path) if path else session.cwd
    except PermissionError as exc:
        return f"[ERRO] {exc}"
    if not os.path.isdir(root):
        return f"[ERRO] Não é um diretório: {root}"

    tree_lines: list[str] = []
    symbols_section: list[str] = []
    file_count = 0
    dir_count = 0

    for dirpath, dirnames, filenames in os.walk(root):
        # Calcula profundidade relativa
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth >= max_depth:
            dirnames.clear()
            continue

        dirnames[:] = sorted(d for d in dirnames if d not in _IGNORE_DIRS)
        indent = "  " * depth

        dir_name = os.path.basename(dirpath) if depth > 0 else os.path.basename(root)
        tree_lines.append(f"{indent}📁 {dir_name}/")
        dir_count += 1

        for fname in sorted(filenames):
            tree_lines.append(f"{indent}  📄 {fname}")
            file_count += 1

            # Extração de símbolos para arquivos de código
            ext = os.path.splitext(fname)[1].lower()
            if ext in _CODE_EXTS:
                fpath = os.path.join(dirpath, fname)
                pat = _SYMBOL_PATTERNS[ext]
                syms: list[str] = []
                try:
                    with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                        for line in fh:
                            m = pat.search(line)
                            if m:
                                # Pega o último grupo capturado (nome do símbolo)
                                name = m.group(m.lastindex) if m.lastindex else m.group(0)
                                prefix = m.group(1).strip() if m.lastindex and m.lastindex > 1 else ""
                                syms.append(f"{prefix} {name}".strip())
                except (OSError, UnicodeDecodeError):
                    continue
                if syms:
                    rel_file = os.path.relpath(fpath, root)
                    symbols_section.append(f"\n### {rel_file}")
                    for s in syms[:30]:  # Limita a 30 símbolos por arquivo
                        symbols_section.append(f"  - {s}")

    output = [f"# Índice do Codebase: {root}\n"]
    output.append(f"**{dir_count} diretórios, {file_count} arquivos**\n")
    output.append("## Árvore de Diretórios\n")
    output.extend(tree_lines)

    if symbols_section:
        output.append("\n\n## Símbolos de Código")
        output.extend(symbols_section)

    return "\n".join(output)


# ── Planning Mode ────────────────────────────────────────────────────────

@mcp.tool()
def create_plan(title: str, steps: list[str]) -> str:
    """Cria um plano de execução com uma lista de passos a seguir.

    Use antes de começar uma tarefa complexa para organizar o trabalho,
    pedir aprovação do usuário e rastrear o progresso.

    Args:
        title: título descritivo do plano.
        steps: lista de descrições dos passos (ex: ["Criar modelo", "Adicionar testes"]).
    """
    planner._dir = os.path.join(session.cwd, ".qwen-plans")
    plan = planner.create(title, steps)
    return f"Plano criado com sucesso!\n\n{plan.render()}"


@mcp.tool()
def update_plan(plan_id: str, step_index: int, status: str) -> str:
    """Atualiza o status de um passo de um plano existente.

    Args:
        plan_id: ID do plano (retornado por create_plan).
        step_index: número do passo (1-indexed).
        status: novo status — "pending", "in_progress" ou "done".
    """
    if status not in ("pending", "in_progress", "done"):
        return f"[ERRO] Status inválido: '{status}'. Use: pending, in_progress, done"
    planner._dir = os.path.join(session.cwd, ".qwen-plans")
    plan = planner.update_step(plan_id, step_index, status)
    if plan is None:
        return f"[ERRO] Plano '{plan_id}' não encontrado ou step_index inválido."
    return plan.render()


@mcp.tool()
def get_plan(plan_id: str | None = None) -> str:
    """Mostra um plano específico ou lista todos os planos existentes.

    Args:
        plan_id: ID do plano. Se não informado, lista todos os planos.
    """
    planner._dir = os.path.join(session.cwd, ".qwen-plans")
    if plan_id:
        plan = planner.get(plan_id)
        if plan is None:
            return f"[ERRO] Plano '{plan_id}' não encontrado."
        return plan.render()
    else:
        plans = planner.list_plans()
        if not plans:
            return "Nenhum plano encontrado. Use create_plan para criar um."
        lines = ["# Planos existentes\n"]
        for p in plans:
            done = sum(1 for s in p.steps if s.status == "done")
            total = len(p.steps)
            lines.append(f"  - [{p.id}] {p.title} ({done}/{total} concluído(s))")
        return "\n".join(lines)


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
