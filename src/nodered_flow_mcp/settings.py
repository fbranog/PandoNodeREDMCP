from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NODERED_", env_file=".env", extra="ignore")

    url: str = "http://localhost:1880"
    token: SecretStr | None = None
    user: str | None = None
    password: SecretStr | None = None
    read_only: bool = True
    examples_dir: Path | None = None
    node_sources_dir: str | None = None
    drafts_dir: Path = Path.home() / ".cache" / "nodered-flow-mcp" / "drafts"
    timeout: float = 20.0


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
