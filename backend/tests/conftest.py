"""Fixture condivise.

I test che toccano il database richiedono un PostgreSQL 18 raggiungibile via
`HOSTPILOT_TEST_DATABASE_URL` (default: localhost:54329, vedi README backend).
Senza database i test DB sono saltati; in CI `HOSTPILOT_TEST_DB_REQUIRED=1`
trasforma il salto in errore, così una pipeline verde implica sempre che i
test DB sono girati. Nessun dato reale di Ospiti nei fixture (NFR-16).
"""

import ipaddress
import os
import socket
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from tests.server_feed import ServerFeed

TABELLE_DA_SVUOTARE = (
    "outbox, job, prenotazione, sync_run, feed_ical, regime_lettura, struttura, "
    "sessione, tentativo_login, host, comune_config, regione_config, "
    "parametro_fiscale, config_audit, comune"
)

# Dati di RIFERIMENTO condivisi seedati dalle migrazioni: svuotarli fra i
# test toglierebbe le 20 Regioni ISTAT a chiunque venga dopo. L'esenzione è
# esplicita e sorvegliata da `tests/test_isolamento_dati.py` (GS-2).
TABELLE_DI_RIFERIMENTO_NON_SVUOTATE = frozenset({"alembic_version", "regione"})

DEFAULT_TEST_DB_URL = (
    "postgresql+psycopg://postgres:postgres@localhost:54329/hostpilot_test"
)

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _test_db_url() -> str:
    return os.environ.get("HOSTPILOT_TEST_DATABASE_URL", DEFAULT_TEST_DB_URL)


# Prima di QUALSIASI import di app.*: `get_settings()` è lru_cache-ata e
# alcuni moduli (app.main) la chiamano a import-time — l'URL del DB deve
# già puntare al database di test, mai a quello reale.
os.environ["HOSTPILOT_DATABASE_URL"] = _test_db_url()
# Token degli endpoint interni di configurazione (AD-9): valore di test,
# nessun segreto reale nel repository.
os.environ.setdefault("HOSTPILOT_ADMIN_TOKEN", "token-di-test-per-endpoint-interni")


class TentativoDiUscitaDiRete(BaseException):
    """Guardia GS-1: un test ha provato a uscire su Internet.

    Deriva da `BaseException` di proposito: un `except Exception` di
    produzione — per esempio la conversione di `OSError` in «destinazione
    non ammessa» del validatore — la assorbirebbe, e la guardia si
    trasformerebbe in un test che passa per il motivo sbagliato.
    """


def _destinazione_consentita(destinazione: object) -> bool:
    """Solo il loopback: il DB dei test e il server HTTP locale stanno lì."""
    if isinstance(destinazione, tuple) and destinazione:
        destinazione = destinazione[0]
    if destinazione in (None, "", "localhost", "localhost.localdomain"):
        return True
    try:
        return ipaddress.ip_address(str(destinazione)).is_loopback
    except ValueError:
        return False


@pytest.fixture(autouse=True)
def isolamento_di_rete(monkeypatch: pytest.MonkeyPatch) -> None:
    """GS-1 (E2-G1): nessuna chiamata di rete reale in unit e integration.

    Dall'Epic 2 il backend ha codice HTTP in uscita: un client HTTP
    dimenticato non fake produrrebbe una suite non deterministica che
    colpisce un servizio di terzi, e il fallimento apparirebbe come
    flakiness. Qui non appare come flakiness: appare subito.

    Restano ammessi il loopback (PostgreSQL dei test e il server HTTP di
    `tests/server_feed.py`) e la risoluzione dei nomi locali.
    """
    connect_originale = socket.socket.connect
    connect_ex_originale = socket.socket.connect_ex
    create_connection_originale = socket.create_connection
    getaddrinfo_originale = socket.getaddrinfo

    def _controlla(destinazione: object, operazione: str) -> None:
        if not _destinazione_consentita(destinazione):
            raise TentativoDiUscitaDiRete(
                f"{operazione} verso {destinazione!r}: la suite non esce in rete "
                "(GS-1). Inietta un client HTTP fake o usa tests/server_feed.py."
            )

    def connect(self: socket.socket, indirizzo: object) -> object:
        _controlla(indirizzo, "connect")
        return connect_originale(self, indirizzo)  # type: ignore[arg-type]

    def connect_ex(self: socket.socket, indirizzo: object) -> object:
        _controlla(indirizzo, "connect_ex")
        return connect_ex_originale(self, indirizzo)  # type: ignore[arg-type]

    def create_connection(indirizzo: object, *args: object, **kwargs: object) -> object:
        _controlla(indirizzo, "create_connection")
        return create_connection_originale(indirizzo, *args, **kwargs)  # type: ignore[arg-type]

    def getaddrinfo(host: object, *args: object, **kwargs: object) -> object:
        _controlla(host, "getaddrinfo")
        return getaddrinfo_originale(host, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "create_connection", create_connection)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)


@pytest.fixture(autouse=True)
def configurazione_pulita() -> Iterator[None]:
    """`get_settings()` è lru_cache-ata: nessun test eredita l'env di un altro.

    Un test che cambia una variabile d'ambiente e legge la configurazione
    lascia il valore in cache anche dopo che `monkeypatch` ha ripulito l'env:
    il test successivo vede un'impostazione che non ha chiesto, e il
    fallimento appare altrove.
    """
    from app.core.config import get_settings

    yield
    get_settings.cache_clear()


@pytest.fixture
def server_feed() -> Iterator[ServerFeed]:
    """Confine di rete reale su 127.0.0.1: si stub-a il trasporto, non il service."""
    with ServerFeed() as server:
        yield server


@pytest.fixture
def contesto(db_session: Session):
    """Un Host con una Struttura: il minimo per collegare un Feed.

    Vive qui e non in un file di test perché tre file la usano. Una fixture
    importata da un modulo di test diventa una ridefinizione a ogni funzione
    che la chiede come parametro (F811): le fixture si condividono dal
    conftest, gli helper puri da `tests/calendario.py`.

    Import LOCALE, non in testa al file: `tests.calendario` importa `app.*`, e
    più sopra questo modulo punta `HOSTPILOT_DATABASE_URL` al database di test
    PRIMA che qualunque cosa di `app` venga importata. Un import in testa
    invertirebbe quell'ordine e la suite parlerebbe col database di sviluppo.
    """
    from tests.calendario import crea_contesto

    return crea_contesto(
        db_session,
        email="host.di.prova@example.com",
        nome="Appartamento di prova",
    )


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
    from app.core.config import get_settings

    get_settings.cache_clear()
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
