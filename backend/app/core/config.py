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

    # Sessione server-side (AD-15). `Secure` resta attivo ovunque; l'override
    # a False è ammesso SOLO in dev locale su http (browser senza TLS).
    session_cookie_name: str = "hostpilot_session"
    session_cookie_secure: bool = True
    session_ttl_days: int = 30

    # Origin del frontend ammessa dal CORS (cookie con credentials, AD-14/15).
    frontend_origin: str = "http://localhost:3000"

    # Freno ai tentativi di login (G-5): finestra temporale, mai lockout
    # permanente. Due limiti complementari: per account (Host preso di
    # mira) e per origine (spraying su molti account).
    login_max_tentativi_account: int = 5
    login_max_tentativi_origine: int = 20
    login_finestra_minuti: int = 15

    # Ogni quanto gira il purge delle sessioni scadute (job durevole).
    purge_sessioni_intervallo_minuti: int = 60

    # Token degli endpoint interni di configurazione normativa (AD-9).
    # Vive nel secret manager dell'ambiente; se vuoto, gli endpoint sono
    # chiusi (nessun accesso di default).
    admin_token: str = ""

    # Cap di prodotto del pilota (FR-1): max Strutture ATTIVE per Host.
    # Parametro DISTINTO dalla soglia fiscale, che vive in config_normativa
    # (AD-12) e arriva con la Story 1.6.
    max_strutture_attive: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()
