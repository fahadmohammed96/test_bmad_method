"""Fixture condivise.

I test che toccano il database richiedono un PostgreSQL 18 raggiungibile via
`HOSTPILOT_TEST_DATABASE_URL` (default: localhost:54329, vedi README backend).
Senza database i test DB sono saltati; in CI `HOSTPILOT_TEST_DB_REQUIRED=1`
trasforma il salto in errore, così una pipeline verde implica sempre che i
test DB sono girati. Nessun dato reale di Ospiti nei fixture (NFR-16).
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from alembic import command

DEFAULT_TEST_DB_URL = (
    "postgresql+psycopg://postgres:postgres@localhost:54329/hostpilot_test"
)

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _test_db_url() -> str:
    return os.environ.get("HOSTPILOT_TEST_DATABASE_URL", DEFAULT_TEST_DB_URL)


@pytest.fixture(scope="session")
def pg_engine() -> Iterator[Engine]:
    url = _test_db_url()
    engine = create_engine(url, pool_pre_ping=True)
    try:
        with engine.connect():
            pass
    except Exception as exc:
        if os.environ.get("HOSTPILOT_TEST_DB_REQUIRED") == "1":
            raise RuntimeError(
                f"Database di test richiesto ma non raggiungibile: {exc}"
            ) from exc
        pytest.skip(f"PostgreSQL di test non raggiungibile ({exc})")

    # Schema pulito + migrazioni Alembic reali (forward-only, AR-11).
    with engine.connect() as conn:
        conn.execution_options(isolation_level="AUTOCOMMIT")
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))

    os.environ["HOSTPILOT_DATABASE_URL"] = url
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(cfg, "head")

    yield engine
    engine.dispose()


@pytest.fixture
def db_session(pg_engine: Engine) -> Iterator[Session]:
    with Session(pg_engine) as session:
        yield session
        session.rollback()
    with pg_engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE outbox, job"))
        conn.commit()


@pytest.fixture
def second_session(pg_engine: Engine) -> Iterator[Session]:
    """Seconda sessione indipendente per i test di concorrenza SKIP LOCKED."""
    with Session(pg_engine) as session:
        yield session
        session.rollback()
