"""Settings, read from the environment (see .env.example at the repo root)."""

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The repo-root .env, wherever the API is started from. In the Docker image this path
# doesn't exist and compose supplies the environment instead; a missing file is ignored.
REPO_ENV = Path(__file__).resolve().parents[4] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ENV, extra="ignore")

    database_url: str = "postgresql+asyncpg://panelwise:panelwise@localhost:5432/panelwise"
    health_check_timeout_s: float = 2.0

    # Nebius Token Factory -- values measured in docs/nebius-findings.md (T001).
    nebius_api_key: str = ""
    nebius_base_url: str = "https://api.tokenfactory.nebius.com/v1"
    nebius_model_fast: str = "nvidia/Nemotron-3_5-Lightning"
    nebius_model_reasoning: str = "nvidia/nemotron-3-super-120b-a12b"
    nebius_model_vision: str = "zai-org/GLM-5.3-Flash"
    llm_request_timeout_s: float = 120.0
    llm_max_attempts: int = 3

    @field_validator("database_url")
    @classmethod
    def _asyncpg_driver(cls, url: str) -> str:
        # Supabase hands out postgresql:// (or postgres://); the async engine needs +asyncpg.
        for scheme in ("postgresql://", "postgres://"):
            if url.startswith(scheme):
                return "postgresql+asyncpg://" + url.removeprefix(scheme)
        return url
