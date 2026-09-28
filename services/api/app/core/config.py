"""Settings, read from the environment (see .env.example at the repo root)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://panelwise:panelwise@localhost:5432/panelwise"
    redis_url: str = "redis://localhost:6379/0"
    health_check_timeout_s: float = 2.0
