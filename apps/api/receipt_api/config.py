from functools import lru_cache
from pathlib import Path
from typing import List, Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
CONTRACTS_DIR = ROOT_DIR / "contracts"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM Settings (OpenAI-compatible)
    llm_base_url: str = Field(default="https://api.openai.com/v1", alias="LLM_BASE_URL")
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_model_fast: str = Field(default="gpt-4o-mini", alias="LLM_MODEL_FAST")
    llm_model_strong: str = Field(default="gpt-4o", alias="LLM_MODEL_STRONG")
    embed_model: str = Field(default="text-embedding-3-small", alias="EMBED_MODEL")
    llm_mode: Literal["live", "record", "replay"] = Field(default="live", alias="LLM_MODE")

    # GitHub Settings
    github_token: str = Field(default="", alias="GITHUB_TOKEN")
    github_webhook_secret: str = Field(default="", alias="GITHUB_WEBHOOK_SECRET")
    agent_authors: List[str] = Field(
        default=["agent/claude-code", "agent/cursor", "agent/codex", "agent/alan"]
    )

    # Sandbox Isolation
    sandbox_mode: Literal["docker", "subprocess"] = Field(default="subprocess", alias="SANDBOX_MODE")
    sandbox_timeout_secs: int = Field(default=300, alias="SANDBOX_TIMEOUT_SECS")
    sandbox_concurrency: int = Field(default=2, alias="SANDBOX_CONCURRENCY")

    # Storage and Networking
    data_dir: str = Field(default="data", alias="DATA_DIR")
    database_url: str = Field(default="sqlite:///data/receipt.db", alias="DATABASE_URL")
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
