"""Il piano di esecuzione delle query sulla coda `job` (MYL-51).

La proposta segnalava un **sequential scan** sulla query di idempotenza dei
bootstrap periodici: filtra `job_type` e `status IN (pending, running)`, ma
`ix_job_due` è parziale su `status = 'pending'` e il pianificatore non può
usarlo. Il supervisore ha chiesto di verificare anche il percorso di
**scodamento** sotto crescita: qui si misurano entrambi, e la misura dice
quale dei due era davvero degradato.

**Come si misura senza duplicare la query.** Un test che riscrive a mano
l'`SQL` da spiegare misura la query del test, non quella del codice: la
prima resta indietro alla prima modifica e nessuno se ne accorge. Qui si
esegue il **percorso di produzione** e si cattura l'istruzione realmente
inviata al database (`before_cursor_execute`), poi si chiede a Postgres il
piano di QUELLA istruzione, con QUEI parametri.

**Il rosso è dentro il test.** L'indice si lascia cadere dentro un savepoint e
si rimisura: senza `ix_job_attivi` la query di idempotenza cade sul sequential
scan, con l'indice no. È la stessa asserzione vista fallire e passare nella
stessa esecuzione, non un'affermazione su come sarebbero andate le cose.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta

import pytest
from sqlalchemy import Engine, event, insert, text
from sqlalchemy.orm import Session

from app.calendario.jobs import (
    TIPO_JOB_SYNC_PERIODICO,
    assicura_retention_periodica,
    bootstrap_sync_periodico,
)
from app.core.date_range import utcnow
from app.core.db import new_uuid7
from app.core.jobs import Job, JobStatus, claim_due
from tests.calendario import Contesto, collega

# Abbastanza righe perché il sequential scan sia la scelta peggiore in modo
# non ambiguo: ~96 righe per Feed al giorno significa che un solo Feed ci
# arriva in sette mesi, e il pilota ne prevede più d'uno per Host.
RIGHE_COMPLETATE = 20_000

INDICE = "ix_job_attivi"


@contextmanager
def cattura_istruzioni(engine: Engine) -> Iterator[list[tuple[str, object]]]:
    """Le istruzioni realmente inviate al database, con i loro parametri."""
    catturate: list[tuple[str, object]] = []

    def prima_di_eseguire(
        conn: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        catturate.append((statement, parameters))

    event.listen(engine, "before_cursor_execute", prima_di_eseguire)
    try:
        yield catturate
    finally:
        event.remove(engine, "before_cursor_execute", prima_di_eseguire)


def _sulla_coda(catturate: list[tuple[str, object]]) -> list[tuple[str, object]]:
    return [(sql, par) for sql, par in catturate if "FROM job" in sql]


def _una_sola(candidate: list[tuple[str, object]], che_cosa: str) -> tuple[str, object]:
    # Un pavimento sul numero di bersagli: puntata su un percorso che non
    # interroga più `job`, questa guardia misurerebbe zero query e tacerebbe.
    assert candidate, f"nessuna istruzione catturata per {che_cosa}"
    return candidate[0]


def _nodi(piano: dict) -> list[dict]:
    trovati = [piano]
    for figlio in piano.get("Plans", []):
        trovati += _nodi(figlio)
    return trovati


def _accessi_alla_coda(db: Session, istruzione: str, parametri: object) -> list[str]:
    """Come Postgres raggiunge la tabella `job` per quell'istruzione.

    Ritorna una voce per accesso, nella forma `Seq Scan` oppure
    `Index Scan su ix_job_due`.
    """
    risultato = db.connection().exec_driver_sql(
        f"EXPLAIN (FORMAT JSON) {istruzione}", parametri
    )
    piano = risultato.scalar_one()[0]["Plan"]
    accessi = []
    for nodo in _nodi(piano):
        if nodo.get("Relation Name") != "job":
            continue
        indice = nodo.get("Index Name")
        accessi.append(
            f"{nodo['Node Type']} su {indice}" if indice else nodo["Node Type"]
        )
    return accessi


@pytest.fixture
def coda_a_regime(db_session: Session, contesto: Contesto) -> None:
    """La coda com'è dopo qualche mese: quasi tutta righe `completed`."""
    feed = collega(db_session, contesto, "https://feed.example.com/calendario.ics")
    db_session.commit()

    adesso = utcnow()
    db_session.execute(
        insert(Job),
        [
            {
                "id": new_uuid7(),
                "job_type": TIPO_JOB_SYNC_PERIODICO,
                "payload": {"feed_id": str(feed.id), "host_id": str(feed.host_id)},
                "due_at": adesso - timedelta(minutes=indice),
                "status": JobStatus.COMPLETED,
                "attempts": 1,
                "max_attempts": 5,
                "backoff_base_seconds": 60,
                "created_at": adesso - timedelta(minutes=indice),
            }
            for indice in range(RIGHE_COMPLETATE)
        ],
    )
    # Senza statistiche il pianificatore decide su stime di default e la
    # misura direbbe poco di ciò che farà in esercizio.
    db_session.execute(text("ANALYZE job"))


@pytest.mark.usefixtures("coda_a_regime")
class TestIlPianoSullaCodaCresciuta:
    @pytest.mark.timeout(120)
    def test_l_idempotenza_smette_di_scandire_l_intera_coda(
        self, pg_engine: Engine, db_session: Session
    ) -> None:
        with cattura_istruzioni(pg_engine) as catturate:
            bootstrap_sync_periodico(db_session)
        istruzione, parametri = _una_sola(
            [(sql, par) for sql, par in _sulla_coda(catturate) if "payload" in sql],
            "l'idempotenza del bootstrap del poller",
        )

        con_indice = _accessi_alla_coda(db_session, istruzione, parametri)

        # Il rosso, nella stessa esecuzione: senza l'indice la stessa query
        # sulla stessa tabella attraversa tutte le righe.
        savepoint = db_session.begin_nested()
        db_session.execute(text(f"DROP INDEX {INDICE}"))
        senza_indice = _accessi_alla_coda(db_session, istruzione, parametri)
        savepoint.rollback()

        assert any("Seq Scan" in accesso for accesso in senza_indice), (
            f"senza {INDICE} il piano non è degradato ({senza_indice}): la "
            "misura non sta osservando la query che si voleva correggere"
        )
        assert not any("Seq Scan" in accesso for accesso in con_indice), (
            f"la query di idempotenza scandisce ancora l'intera coda: {con_indice}"
        )
        assert any(INDICE in accesso for accesso in con_indice), con_indice

    @pytest.mark.timeout(120)
    def test_anche_il_bootstrap_della_retention_usa_l_indice(
        self, pg_engine: Engine, db_session: Session
    ) -> None:
        # Lo stesso predicato senza filtro sul payload: è la forma di
        # `assicura_retention_periodica` e dei due purge singoletto.
        with cattura_istruzioni(pg_engine) as catturate:
            assicura_retention_periodica(db_session)
        istruzione, parametri = _una_sola(
            [(sql, par) for sql, par in _sulla_coda(catturate) if "payload" not in sql],
            "l'idempotenza del bootstrap della retention",
        )

        assert not any(
            "Seq Scan" in accesso
            for accesso in _accessi_alla_coda(db_session, istruzione, parametri)
        )

    @pytest.mark.timeout(120)
    def test_lo_SCODAMENTO_non_era_degradato(
        self, pg_engine: Engine, db_session: Session
    ) -> None:
        # L'altra metà della verifica chiesta dal supervisore, e la risposta
        # è che il percorso di scodamento stava già bene: `ix_job_due` è
        # parziale su `status = 'pending'` ed è esattamente il predicato di
        # `claim_due`, quindi le righe `completed` non lo toccano nemmeno.
        # Dirlo con la misura in mano evita di «correggere» ciò che non era
        # rotto.
        with cattura_istruzioni(pg_engine) as catturate:
            claim_due(db_session, limit=10)
        istruzione, parametri = _una_sola(
            [(sql, par) for sql, par in _sulla_coda(catturate) if "FOR UPDATE" in sql],
            "lo scodamento",
        )

        accessi = _accessi_alla_coda(db_session, istruzione, parametri)
        assert not any("Seq Scan" in accesso for accesso in accessi), accessi

        # E resta sano anche senza il nuovo indice: la prova che il degrado
        # non era qui, e che l'indice aggiunto non è ciò che lo salva.
        savepoint = db_session.begin_nested()
        db_session.execute(text(f"DROP INDEX {INDICE}"))
        senza_indice = _accessi_alla_coda(db_session, istruzione, parametri)
        savepoint.rollback()

        assert not any("Seq Scan" in accesso for accesso in senza_indice), senza_indice
