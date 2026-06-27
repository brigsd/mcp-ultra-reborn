"""Execução de comandos com sessão persistente.

A sessão guarda o diretório de trabalho e o ambiente entre chamadas, de modo
que a IA possa navegar e executar comandos como um agente local (ex.: Claude
Code / Antigravity).
"""

from __future__ import annotations

import os
import platform
import re
import subprocess
import time
from dataclasses import dataclass

from .config import Settings, settings as default_settings

IS_WINDOWS = platform.system() == "Windows"


class CommandBlocked(Exception):
    """Levantada quando um comando casa com um padrão da blocklist."""


@dataclass
class CommandResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_s: float
    cwd: str
    shell: str
    timed_out: bool = False
    truncated: bool = False

    def to_text(self) -> str:
        status = "TIMEOUT" if self.timed_out else f"exit={self.exit_code}"
        header = (
            f"$ {self.command}\n"
            f"[cwd={self.cwd} | shell={self.shell} | {status} | {self.duration_s:.2f}s]"
        )
        parts = [header]
        if self.stdout:
            parts.append("--- stdout ---\n" + self.stdout.rstrip("\n"))
        if self.stderr:
            parts.append("--- stderr ---\n" + self.stderr.rstrip("\n"))
        if not self.stdout and not self.stderr:
            parts.append("(sem saída)")
        if self.truncated:
            parts.append("[saída truncada — aumente MCP_MAX_OUTPUT_CHARS se precisar de mais]")
        return "\n".join(parts)


class ShellSession:
    """Mantém cwd e ambiente persistentes entre execuções de comandos."""

    def __init__(self, config: Settings | None = None):
        self.config = config or default_settings
        start = self.config.start_dir or os.getcwd()
        self.cwd = os.path.abspath(start)
        self.env: dict[str, str] = dict(os.environ)
        self._blocked = [re.compile(p) for p in self.config.blocked_patterns]

    # ------------------------------------------------------------------ jail
    def _check_jail(self, target: str) -> None:
        jail = self.config.allowed_dir
        if not jail:
            return
        jail_abs = os.path.abspath(jail)
        common = os.path.commonpath([jail_abs, os.path.abspath(target)])
        if common != jail_abs:
            raise PermissionError(f"Acesso negado fora de MCP_ALLOWED_DIR: {target}")

    def _check_command(self, command: str) -> None:
        for pat in self._blocked:
            if pat.search(command):
                raise CommandBlocked(f"Comando bloqueado por padrão: {pat.pattern!r}")

    # --------------------------------------------------------------- shell pick
    def _resolve_shell_kind(self) -> str:
        kind = self.config.shell_kind
        if kind != "auto":
            return kind
        return "cmd" if IS_WINDOWS else "bash"

    def _build_invocation(self, command: str) -> tuple[list[str] | str, bool, str]:
        """Retorna (argv_ou_str, use_shell, nome_do_shell)."""
        kind = self._resolve_shell_kind()
        if kind == "cmd":
            # cmd.exe via COMSPEC
            return command, True, "cmd"
        if kind == "powershell":
            exe = "powershell" if IS_WINDOWS else "pwsh"
            return [exe, "-NoProfile", "-Command", command], False, kind
        if kind == "bash":
            return ["/bin/bash", "-lc", command], False, "bash"
        # sh / fallback
        return command, True, "sh"

    def _resolve_timeout(self, timeout: int | None) -> int:
        if timeout is None:
            return self.config.default_timeout
        return max(1, min(timeout, self.config.max_timeout))

    def _truncate(self, text: str) -> tuple[str, bool]:
        limit = self.config.max_output_chars
        if len(text) <= limit:
            return text, False
        keep = limit // 2
        return text[:keep] + "\n...[truncado]...\n" + text[-keep:], True

    # ------------------------------------------------------------------- public
    def resolve_path(self, path: str) -> str:
        """Resolve um caminho relativo ao cwd da sessão e aplica o jail."""
        target = path if os.path.isabs(path) else os.path.join(self.cwd, path)
        target = os.path.abspath(target)
        self._check_jail(target)
        return target

    def change_directory(self, path: str) -> str:
        target = self.resolve_path(path)
        if not os.path.isdir(target):
            raise NotADirectoryError(f"Não é um diretório: {target}")
        self.cwd = target
        return self.cwd

    def set_env(self, key: str, value: str) -> None:
        self.env[key] = value

    def run(self, command: str, timeout: int | None = None) -> CommandResult:
        self._check_command(command)
        self._check_jail(self.cwd)
        eff_timeout = self._resolve_timeout(timeout)
        argv, use_shell, shell_name = self._build_invocation(command)

        start = time.monotonic()
        timed_out = False
        try:
            proc = subprocess.run(
                argv,
                cwd=self.cwd,
                env=self.env,
                shell=use_shell,
                capture_output=True,
                timeout=eff_timeout,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            stdout, stderr, code = proc.stdout or "", proc.stderr or "", proc.returncode
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout = exc.stdout or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", "replace")
            stderr = exc.stderr or ""
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", "replace")
            stderr += f"\n[timeout após {eff_timeout}s]"
            code = -1
        except FileNotFoundError as exc:
            stdout, stderr, code = "", f"shell não encontrado: {exc}", 127

        duration = time.monotonic() - start
        stdout, t1 = self._truncate(stdout)
        stderr, t2 = self._truncate(stderr)

        return CommandResult(
            command=command,
            exit_code=code,
            stdout=stdout,
            stderr=stderr,
            duration_s=duration,
            cwd=self.cwd,
            shell=shell_name,
            timed_out=timed_out,
            truncated=t1 or t2,
        )
