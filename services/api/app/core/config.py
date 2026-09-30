"""Settings, read from the environment (see .env.example at the repo root)."""

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

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
    nebius_model_vision: str = "deepseek-ai/DeepSeek-V4.1-Flash"
    llm_request_timeout_s: float = 120.0
    llm_max_attempts: int = 3

    # Frames (docs/design/storyboard.md §6). The prompt's word budget, a conservative proxy for the
    # text encoder's token limit: 55 words for CLIP's 77 tokens until T003 picks the model.
    comfyui_max_words: int = 55
    # A directory of private style TOMLs outside the repo; empty means none. Never set on the
    # hosted demo.
    panelwise_private_styles: str = ""

    @field_validator("database_url")
    @classmethod
    def _asyncpg_driver(cls, url: str) -> str:
        # Parsed with SQLAlchemy's own URL parser, the one the engine uses: a "?" or "&" inside
        # the password is part of the password, not the start of the query (PR #13 review).
        parsed = make_url(url)
        # Supabase hands out postgresql:// (or postgres://); the async engine needs +asyncpg.
        if parsed.drivername in ("postgresql", "postgres"):
            parsed = parsed.set(drivername="postgresql+asyncpg")
        # libpq's sslmode= (which Supabase suggests) is ssl= to asyncpg, same values; asyncpg
        # rejects an unknown sslmode keyword at connect time, so the API would never be healthy.
        if "sslmode" in parsed.query:
            query = dict(parsed.query)
            query["ssl"] = query.pop("sslmode")
            parsed = parsed.set(query=query)
        return parsed.render_as_string(hide_password=False)
