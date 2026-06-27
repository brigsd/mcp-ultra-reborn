"""Configuração do servidor MCP, lida das variáveis de ambiente.

Todas as opções têm padrões sensatos. Para máxima permissividade (mais
controle para a IA) deixe blocklist/jail vazios; para um ambiente mais
restrito, preencha-os.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass
class Settings:
    # Transporte: "stdio" (cliente local) ou "http"/"streamable-http" (IA web).
    transport: str = field(default_factory=lambda: os.getenv("MCP_TRANSPORT", "stdio").lower())

    # Endereço/porta usados apenas no transporte HTTP.
    host: str = field(default_factory=lambda: os.getenv("MCP_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: _int("MCP_PORT", 8000))

    # Token Bearer obrigatório no HTTP quando definido (recomendado se exposto à rede).
    auth_token: str | None = field(default_factory=lambda: os.getenv("MCP_AUTH_TOKEN") or None)

    # Timeouts de execução (segundos).
    default_timeout: int = field(default_factory=lambda: _int("MCP_DEFAULT_TIMEOUT", 60))
    max_timeout: int = field(default_factory=lambda: _int("MCP_MAX_TIMEOUT", 600))

    # Limite de caracteres devolvidos por stream (evita estourar o contexto da IA).
    max_output_chars: int = field(default_factory=lambda: _int("MCP_MAX_OUTPUT_CHARS", 100_000))

    # Shell preferido: auto | cmd | powershell | bash | sh.
    shell_kind: str = field(default_factory=lambda: os.getenv("MCP_SHELL", "auto").lower())

    # Diretório inicial da sessão (default: cwd do processo).
    start_dir: str | None = field(default_factory=lambda: os.getenv("MCP_START_DIR") or None)

    # "Jail" opcional: se definido, a IA não pode sair desta árvore de diretórios.
    allowed_dir: str | None = field(default_factory=lambda: os.getenv("MCP_ALLOWED_DIR") or None)

    # Padrões regex bloqueados (CSV). Vazio = sem bloqueio (mais controle).
    blocked_patterns: list[str] = field(default_factory=lambda: _csv(os.getenv("MCP_BLOCKED_PATTERNS")))

    def normalized_transport(self) -> str:
        if self.transport in ("http", "streamable-http", "streamable_http"):
            return "http"
        return "stdio"


def load_settings() -> Settings:
    return Settings()


settings = load_settings()
