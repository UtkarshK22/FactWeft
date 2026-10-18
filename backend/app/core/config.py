"""Application settings.

All configuration is read once from the environment (and an optional .env file).
Secrets use ``SecretStr`` so they are never rendered by ``repr``/logs.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_TOKENS_FILE = Path("demo_data/tokens.json")


def resolve_tokens_file(path: Path) -> Path:
    """Resolve a relative tokens path against cwd, the repo root, or backend/."""
    if path.is_absolute():
        return path
    candidates = (Path.cwd() / path, _REPO_ROOT / path, _REPO_ROOT / "backend" / path)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return Path.cwd() / path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "FactWeft"
    environment: Literal["local", "ci", "prod"] = "local"
    api_prefix: str = "/api"

    # FalkorDB is the only memory store; there is no local fallback.
    falkordb_host: str = "localhost"
    falkordb_port: int = Field(default=6379, ge=1, le=65535)
    falkordb_password: SecretStr | None = None

    llm_mode: Literal["fixture", "live"] = "fixture"
    llm_model: str = "gpt-4o-mini"
    llm_api_key: SecretStr | None = None

    demo_mode: bool = True
    tokens_file: Path = _DEFAULT_TOKENS_FILE

    # Comma-separated, e.g. "http://localhost:5173,http://127.0.0.1:5173"
    cors_origins: str = "http://localhost:5173"

    query_timeout_ms: int = Field(default=5000, ge=100, le=120_000)
    max_graph_nodes: int = Field(default=500, ge=10, le=20_000)
    trace_buffer_size: int = Field(default=500, ge=10, le=20_000)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def falkordb_password_value(self) -> str | None:
        return self.falkordb_password.get_secret_value() if self.falkordb_password else None

    @property
    def falkordb_endpoint(self) -> str:
        return f"{self.falkordb_host}:{self.falkordb_port}"

    @property
    def tokens_path(self) -> Path:
        return resolve_tokens_file(self.tokens_file)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings singleton (FastAPI dependency friendly)."""
    return Settings()
