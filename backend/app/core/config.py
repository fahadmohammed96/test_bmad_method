"""Configurazione 12-factor: env vars per l'infrastruttura (spine Consistency).

I parametri normativi NON vivono qui: stanno nelle tabelle `config_normativa`
(AD-9). I segreti vivono nel secret manager dell'ambiente; `.env.example`
è il contratto.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HOSTPILOT_", env_file=".env", extra="ignore"
    )

    env: str = "dev"
    database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/hostpilot"
    )
    worker_poll_seconds: float = 1.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
