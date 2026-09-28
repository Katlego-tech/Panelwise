"""Settings, read from the environment (see .env.example at the repo root)."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# The repo-root .env, wherever the API is started from. In the Docker image this path
# doesn't exist and compose supplies the environment instead; a missing file is ignored.
REPO_ENV = Path(__file__).resolve().parents[4] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ENV, extra="ignore")

    database_url: str = "postgresql+asyncpg://panelwise:panelwise@localhost:5432/panelwise"
    redis_url: str = "redis://localhost:6379/0"
    health_check_timeout_s: float = 2.0
