"""Ambiente Alembic: URL dal contratto env (HOSTPILOT_DATABASE_URL),
metadata dal shared kernel. Migrazioni forward-only (AR-11).

I modelli NON si elencano a mano: si scoprono (`app.registro_modelli`). Un
elenco scritto a mano non fallisce quando è incompleto — `--autogenerate`
semplicemente non vede le tabelle del modulo dimenticato e propone di
CANCELLARLE, che è il modo più silenzioso per perdere dati.
"""

from sqlalchemy import create_engine

from alembic import context
from app.core.config import get_settings
from app.registro_modelli import importa_tutti_i_modelli

target_metadata = importa_tutti_i_modelli().metadata


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(get_settings().database_url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
