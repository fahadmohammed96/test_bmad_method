"""Test di gara sui bootstrap SINGOLETTO dei cicli periodici (MYL-50).

Tre percorsi con la stessa identica forma — `SELECT`-poi-`schedule` su un
ciclo che deve esistere in **una sola** copia per tutto il sistema:

- `identity/jobs.py::assicura_purge_periodico` (Epic 1);
- `calendario/jobs.py::assicura_retention_periodica` (Story 2.3);
- `core/manutenzione.py::assicura_purge_job_periodico` (questa PR).

Nessuno dei tre aveva una serializzazione né un test di gara: il quarto
percorso della stessa forma, `assicura_sync_periodico`, l'ha presa nella
Story 2.2 e questi sono rimasti indietro. La finestra si apre davvero — due
worker avviati insieme, o un restart che si sovrappone al precedente, entrano
qui contemporaneamente — e il danno non produce alcun errore: due cicli in
coda sono il doppio dei giri, per sempre, in silenzio.

Forma imposta dal test design dell'Epic 2 (§2.4, A3), la stessa di
`test_calendario_gara_poller.py`:

- **8 contendenti**, non 2: con due thread una finestra critica stretta spesso
  non si presenta e il test passa a vuoto;
- `threading.Barrier(8, timeout=10)` allineato **fra i client**, mai dentro il
  codice sotto test: con un rimedio basato su lock un barrier interno andrebbe
  in deadlock invece che in rosso, mascherando l'esito;
- una `Session(pg_engine)` fresca per thread, `barriera.wait()` **dentro** il
  blocco di sessione;
- esiti contati **più** una ri-query di post-condizione;
- e il test va **visto rosso** prima di essere verde: l'evidenza — quale
  vincolo è stato rimosso per farlo fallire, e come è caduto — è nella nota di
  consegna della PR.

L'ultima classe copre la metà che i conteggi non vedono: che i tre percorsi
**non si serializzino a vicenda**. Namespace di advisory lock condivisi non
producono alcun errore, solo latenza sotto carico, quindi si scoprono in
produzione e si attribuiscono al database.
"""

import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.calendario.jobs import TIPO_JOB_RETENTION_OSPITE, assicura_retention_periodica
from app.core.jobs import Job, JobStatus
from app.core.manutenzione import TIPO_JOB_PURGE_JOB, assicura_purge_job_periodico
from app.identity.jobs import TIPO_JOB_PURGE_SESSIONI, assicura_purge_periodico

CONCORRENTI = 8

Bootstrap = Callable[[Session], None]

# I tre singoletti, con il tipo di job che ciascuno accoda. La lista è ciò che
# tiene insieme la regola e il codice: un quarto ciclo periodico aggiunto senza
# passare da qui resta senza test di gara, ed è esattamente come sono nati
# questi tre.
SINGOLETTI: list[tuple[str, str, Bootstrap]] = [
    ("purge sessioni", TIPO_JOB_PURGE_SESSIONI, assicura_purge_periodico),
    ("retention Ospite", TIPO_JOB_RETENTION_OSPITE, assicura_retention_periodica),
    ("purge coda job", TIPO_JOB_PURGE_JOB, assicura_purge_job_periodico),
]


def _cicli_attivi(db: Session, tipo: str) -> list[Job]:
    return list(
        db.scalars(
            select(Job).where(
                Job.job_type == tipo,
                Job.status.in_((JobStatus.PENDING, JobStatus.RUNNING)),
            )
        )
    )


class TestBootstrapSingolettoSottoConcorrenza:
    """8 bootstrap in gara lasciano UN solo ciclo in coda."""

    @pytest.mark.timeout(60)
    @pytest.mark.parametrize(
        ("nome", "tipo", "bootstrap"),
        SINGOLETTI,
        ids=[nome for nome, _, _ in SINGOLETTI],
    )
    def test_otto_bootstrap_in_gara_accodano_un_solo_ciclo(
        self,
        pg_engine: Engine,
        db_session: Session,
        nome: str,
        tipo: str,
        bootstrap: Bootstrap,
    ) -> None:
        # Si parte dalla coda VUOTA per questo tipo: è lo stato in cui il
        # check-then-write ha davvero una finestra. Con il ciclo già presente
        # tutti e otto leggerebbero «c'è» e nessuno scriverebbe — il test
        # passerebbe senza aver mai messo in gara nulla.
        assert _cicli_attivi(db_session, tipo) == []
        db_session.commit()

        barriera = threading.Barrier(CONCORRENTI, timeout=10)

        def fai_bootstrap(_: int) -> str:
            with Session(pg_engine) as db:
                # RISCALDAMENTO, e non è un dettaglio di stile: la prima
                # esecuzione paga l'apertura della connessione e la
                # compilazione dell'istruzione da parte di SQLAlchemy, e sono
                # costi abbastanza diversi fra thread da scaglionarli oltre la
                # finestra critica. Misurato: senza queste due righe il caso
                # `purge sessioni` — il primo della lista, quello che paga la
                # compilazione per tutti — restava verde anche senza il lock,
                # cioè era un test di gara che non aveva mai visto la gara. Il
                # `rollback` non lascia nulla di scritto e rilascia il lock
                # consultivo, che è legato alla transazione.
                bootstrap(db)
                db.rollback()
                barriera.wait()
                try:
                    bootstrap(db)
                    db.commit()
                except Exception as exc:  # noqa: BLE001 — l'esito è il dato
                    return f"errore:{type(exc).__name__}"
                return "fatto"

        with ThreadPoolExecutor(max_workers=CONCORRENTI) as esecutore:
            esiti = list(esecutore.map(fai_bootstrap, range(CONCORRENTI)))

        # Nessuno deve esplodere: un'eccezione all'avvio del worker
        # impedirebbe il boot dell'intero processo.
        assert [esito for esito in esiti if esito.startswith("errore")] == []
        assert esiti.count("fatto") == CONCORRENTI

        with Session(pg_engine) as db:
            cicli = _cicli_attivi(db, tipo)
        assert len(cicli) == 1, (
            f"{nome}: {len(cicli)} cicli in coda invece di uno — "
            "il ciclo girerebbe in copie multiple, per sempre, senza errori"
        )


class TestIlBootstrapRestaIdempotente:
    """La serializzazione non deve cambiare il comportamento a un chiamante solo."""

    @pytest.mark.parametrize(
        ("nome", "tipo", "bootstrap"),
        SINGOLETTI,
        ids=[nome for nome, _, _ in SINGOLETTI],
    )
    def test_due_chiamate_in_sequenza_accodano_un_solo_ciclo(
        self, db_session: Session, nome: str, tipo: str, bootstrap: Bootstrap
    ) -> None:
        bootstrap(db_session)
        db_session.commit()
        bootstrap(db_session)
        db_session.commit()

        assert len(_cicli_attivi(db_session, tipo)) == 1

    @pytest.mark.parametrize(
        ("nome", "tipo", "bootstrap"),
        SINGOLETTI,
        ids=[nome for nome, _, _ in SINGOLETTI],
    )
    def test_un_ciclo_perso_torna_in_coda(
        self, db_session: Session, nome: str, tipo: str, bootstrap: Bootstrap
    ) -> None:
        # L'altra metà del bootstrap: è la rete di sicurezza per il ciclo
        # andato a `failed`, o cancellato a mano. Senza, un ciclo perso
        # resterebbe perso per sempre e la manutenzione si fermerebbe in
        # silenzio.
        bootstrap(db_session)
        db_session.commit()
        for job in _cicli_attivi(db_session, tipo):
            db_session.delete(job)
        db_session.commit()

        bootstrap(db_session)
        db_session.commit()
        assert len(_cicli_attivi(db_session, tipo)) == 1


class TestITreSingolettiNonSiAspettano:
    """I namespace sono distinti, e qui la distinzione si OSSERVA.

    Due percorsi con lo stesso namespace di advisory lock si serializzano a
    vicenda **senza alcun errore**: la post-condizione sui conteggi resta
    identica — è invariante sotto serializzazione — e il sintomo è solo
    latenza all'avvio del worker, cioè si scopre in produzione e si
    attribuisce al database.

    La barriera si raggiunge DOPO il bootstrap e PRIMA del commit, cioè mentre
    ogni thread TIENE ancora il proprio lock (è legato alla transazione e si
    rilascia al commit). Con namespace distinti tutti e tre arrivano e la
    barriera si apre; con un namespace condiviso solo il primo entra, gli altri
    restano appesi dentro il codice sotto test e la barriera scade.
    """

    @pytest.mark.timeout(60)
    def test_i_bootstrap_di_cicli_DIVERSI_procedono_in_parallelo(
        self, pg_engine: Engine, db_session: Session
    ) -> None:
        for _, tipo, _bootstrap in SINGOLETTI:
            assert _cicli_attivi(db_session, tipo) == []
        db_session.commit()

        quanti = len(SINGOLETTI)
        partenza = threading.Barrier(quanti, timeout=10)
        tutti_hanno_il_lock = threading.Barrier(quanti, timeout=10)

        def bootstrap_di(indice: int) -> str:
            _nome, _tipo, bootstrap = SINGOLETTI[indice]
            with Session(pg_engine) as db:
                bootstrap(db)  # riscaldamento, vedi sopra
                db.rollback()
                partenza.wait()
                try:
                    bootstrap(db)
                except Exception as exc:  # noqa: BLE001 — l'esito è il dato
                    return f"errore:{type(exc).__name__}"
                finally:
                    tutti_hanno_il_lock.wait()
                db.commit()
                return "fatto"

        with ThreadPoolExecutor(max_workers=quanti) as esecutore:
            esiti = list(esecutore.map(bootstrap_di, range(quanti)))

        assert esiti == ["fatto"] * quanti

        with Session(pg_engine) as db:
            for nome, tipo, _bootstrap in SINGOLETTI:
                assert len(_cicli_attivi(db, tipo)) == 1, nome
