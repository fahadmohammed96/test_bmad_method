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
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from alembic import command

TABELLE_DA_SVUOTARE = "outbox, job, sessione, host"

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


def _svuota_tabelle(engine: Engine) -> None:
    with engine.connect() as conn:
        conn.execute(text(f"TRUNCATE TABLE {TABELLE_DA_SVUOTARE} CASCADE"))
        conn.commit()


@pytest.fixture
def db_session(pg_engine: Engine) -> Iterator[Session]:
    with Session(pg_engine) as session:
        yield session
        session.rollback()
    _svuota_tabelle(pg_engine)


@pytest.fixture
def client(pg_engine: Engine) -> Iterator[TestClient]:
    """TestClient dell'app con il database dei test al posto di quello reale."""
    from app.core.db import get_db
    from app.main import app

    factory = sessionmaker(pg_engine)

    def _get_test_db() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_test_db
    # base_url https: il cookie di sessione è Secure (AD-15) e il jar del
    # client non lo invierebbe mai su http.
    with TestClient(
        app, base_url="https://testserver", raise_server_exceptions=False
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    _svuota_tabelle(pg_engine)


@pytest.fixture
def second_session(pg_engine: Engine) -> Iterator[Session]:
    """Seconda sessione indipendente per i test di concorrenza SKIP LOCKED."""
    with Session(pg_engine) as session:
        yield session
        session.rollback()
