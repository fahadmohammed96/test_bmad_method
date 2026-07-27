"""Test di gara A3-2 e A3-3 — i due check-then-write del poller.

Regola dell'Epic 2 (§2.4 del test design): **ogni percorso che legge-poi-scrive
con un vincolo nasce con un test di gara.** Nell'Epic 1 lo stesso identico
difetto è stato trovato due volte a tre Story di distanza, e la seconda volta
è la prova che una regola non scritta non vale.

Forma imposta, la stessa di `test_strutture.py::TestCapAtomico` e di
`test_calendario_gara.py`:

- **8 contendenti**, non 2: con due thread una finestra critica stretta spesso
  non si presenta e il test passa a vuoto;
- `threading.Barrier(8, timeout=10)` allineato **fra i client**, mai dentro il
  codice sotto test: con un rimedio basato su lock un barrier interno andrebbe
  in deadlock invece che in rosso, mascherando l'esito;
- una `Session(pg_engine)` fresca per thread, `barriera.wait()` **dentro** il
  blocco di sessione;
- esiti contati **più** una ri-query di post-condizione;
- e il test va **visto rosso** prima di essere verde. L'evidenza — quale
  vincolo è stato rimosso per farlo fallire — è nel commento della PR e nel
  Dev Agent Record della Story.

**A3-2 — claim del poller.** `claim_due` è `SELECT ... FOR UPDATE SKIP LOCKED`
seguito da una scrittura di stato. La proprietà da dimostrare non è solo «uno
solo lo esegue»: è che **gli altri sette non bloccano**. Senza `SKIP LOCKED`
uno solo prenderebbe comunque il job, ma gli altri resterebbero appesi sul
lock di riga fino al commit del primo — e in un worker in-process quello è il
modo in cui una coda si ferma tutta insieme. Per questo qui le transazioni si
tengono APERTE fino a che tutti gli otto hanno tentato: è l'unica disposizione
in cui la differenza fra le due implementazioni si vede.

**A3-3 — bootstrap del ciclo periodico.** `assicura_sync_periodico` è un
`SELECT`-poi-`schedule`: fra la lettura e la scrittura un altro chiamante può
inserire, e il risultato sarebbero due cicli per lo stesso Feed — cioè il
doppio delle richieste al portale, per sempre, senza alcun errore. Il test
design nota che il precedente `assicura_purge_periodico` dell'Epic 1 ha la
stessa forma e nessun test di gara: con N Feed la probabilità di collisione
cresce, e va coperta qui.
"""

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.calendario import service
from app.calendario.jobs import (
    TIPO_JOB_SYNC_PERIODICO,
    assicura_sync_periodico,
)
from app.calendario.models import CanaleFeed, FeedIcal
from app.core.jobs import Job, JobStatus, claim_due
from app.identity.models import Host
from app.strutture.models import Struttura

CONCORRENTI = 8


@pytest.fixture
def feed_collegato(db_session: Session) -> tuple[uuid.UUID, uuid.UUID]:
    """Un Feed vero, con il suo Host e la sua Struttura. Nessuna rete."""
    host = Host(
        email="host.poller.in.gara@example.com", password_hash="$argon2id$finto"
    )
    db_session.add(host)
    db_session.flush()
    struttura = Struttura(
        host_id=host.id,
        nome="Poller in gara",
        comune="Testopoli",
        regione="Emilia-Romagna",
    )
    db_session.add(struttura)
    db_session.commit()

    feed = service.collega_feed(
        db_session,
        host.id,
        service.DatiFeed(
            struttura_id=struttura.id,
            url="https://feed.example.com/calendario.ics",
            canale=CanaleFeed.AIRBNB,
        ),
    )
    return host.id, feed.id


class TestClaimDelPollerSottoConcorrenza:
    """A3-2 (P0) — uno solo esegue, e gli altri sette NON aspettano."""

    # Un deadlock del database appenderebbe `ThreadPoolExecutor.__exit__`
    # all'infinito. Sbaglia dal lato sicuro — non passa in verde — ma un hang
    # non deve essere l'unica difesa: il timeout lo trasforma in un rosso.
    @pytest.mark.timeout(60)
    def test_otto_worker_sullo_stesso_job_ne_fanno_claim_uno_solo(
        self, pg_engine: Engine, feed_collegato: tuple[uuid.UUID, uuid.UUID]
    ) -> None:
        _, feed_id = feed_collegato
        partenza = threading.Barrier(CONCORRENTI, timeout=10)
        # Seconda barriera: NESSUNO committa finché tutti e otto non hanno
        # tentato. È ciò che tiene aperta la transazione del vincitore mentre
        # gli altri provano, cioè la condizione in cui `SKIP LOCKED` è
        # distinguibile da un `FOR UPDATE` che aspetta. Vive fra i client,
        # non dentro il codice sotto test.
        tutti_hanno_tentato = threading.Barrier(CONCORRENTI, timeout=10)

        def fai_claim(_: int) -> int:
            with Session(pg_engine) as db:
                partenza.wait()
                try:
                    presi = claim_due(db, limit=10)
                    quanti = len(presi)
                finally:
                    tutti_hanno_tentato.wait()
                db.commit()
                return quanti

        with ThreadPoolExecutor(max_workers=CONCORRENTI) as esecutore:
            esiti = list(esecutore.map(fai_claim, range(CONCORRENTI)))

        # Il job scaduto è uno solo — l'import on-demand del collegamento: il
        # ciclo periodico nasce nel futuro e non è candidabile.
        assert sum(esiti) == 1
        assert esiti.count(1) == 1
        assert esiti.count(0) == CONCORRENTI - 1

        # Post-condizione sullo stato finale, non solo sugli esiti contati.
        with Session(pg_engine) as db:
            righe = db.scalars(
                select(Job).where(Job.payload["feed_id"].astext == str(feed_id))
            ).all()
            per_stato = [job.status for job in righe]
        assert per_stato.count(JobStatus.RUNNING) == 1
        # Nessun job è rimasto `pending` e scaduto: se `SKIP LOCKED` fosse
        # sparito, sette transazioni avrebbero atteso e poi trovato la riga
        # già presa — il conteggio reggerebbe, l'attesa no.
        assert per_stato.count(JobStatus.PENDING) == 1  # il ciclo periodico


class TestBootstrapDelCicloSottoConcorrenza:
    """A3-3 (P0) — 8 bootstrap in gara lasciano UN solo ciclo in coda."""

    @pytest.mark.timeout(60)
    def test_otto_bootstrap_in_gara_accodano_un_solo_ciclo(
        self, pg_engine: Engine, feed_collegato: tuple[uuid.UUID, uuid.UUID]
    ) -> None:
        host_id, feed_id = feed_collegato
        # Si parte dal Feed SENZA ciclo in coda: è lo stato in cui il
        # check-then-write ha davvero una finestra: con il ciclo già presente
        # tutti e otto leggerebbero «c'è» e nessuno scriverebbe.
        with Session(pg_engine) as db:
            for job in db.scalars(
                select(Job).where(Job.job_type == TIPO_JOB_SYNC_PERIODICO)
            ):
                db.delete(job)
            db.commit()

        barriera = threading.Barrier(CONCORRENTI, timeout=10)

        def fai_bootstrap(_: int) -> str:
            with Session(pg_engine) as db:
                feed = db.get(FeedIcal, feed_id)
                assert feed is not None
                barriera.wait()
                try:
                    assicura_sync_periodico(db, feed)
                    db.commit()
                except Exception as exc:  # noqa: BLE001 — l'esito è il dato
                    return f"errore:{type(exc).__name__}"
                return "fatto"

        with ThreadPoolExecutor(max_workers=CONCORRENTI) as esecutore:
            esiti = list(esecutore.map(fai_bootstrap, range(CONCORRENTI)))

        # Nessuno deve esplodere: una IntegrityError che arriva all'avvio del
        # worker impedirebbe il boot dell'intero processo.
        assert [esito for esito in esiti if esito.startswith("errore")] == []
        assert esiti.count("fatto") == CONCORRENTI

        # LA post-condizione: un solo ciclo in coda. Due cicli sarebbero il
        # doppio delle richieste a quel portale, per sempre, senza errori.
        with Session(pg_engine) as db:
            cicli = db.scalars(
                select(Job).where(
                    Job.job_type == TIPO_JOB_SYNC_PERIODICO,
                    Job.status.in_((JobStatus.PENDING, JobStatus.RUNNING)),
                    Job.payload["feed_id"].astext == str(feed_id),
                )
            ).all()
        assert len(cicli) == 1
        assert cicli[0].payload["host_id"] == str(host_id)

    @pytest.mark.timeout(60)
    def test_feed_DIVERSI_non_si_aspettano_a_vicenda(
        self, pg_engine: Engine, db_session: Session
    ) -> None:
        # Il lock è per Feed, non globale: due bootstrap di Feed diversi non
        # devono serializzarsi. Con centinaia di Feed una serializzazione
        # globale trasformerebbe il bootstrap dell'avvio in una fila indiana,
        # e la post-condizione sui conteggi non lo direbbe — è invariante
        # sotto serializzazione. Qui la granularità si OSSERVA, con la
        # barriera raggiunta mentre i lock sono ancora tenuti (vedi sotto).
        host = Host(email="host.molti.feed@example.com", password_hash="$argon2id$x")
        db_session.add(host)
        db_session.flush()
        struttura = Struttura(
            host_id=host.id,
            nome="Molti feed",
            comune="Testopoli",
            regione="Emilia-Romagna",
        )
        db_session.add(struttura)
        db_session.commit()
        feed_id = [
            service.collega_feed(
                db_session,
                host.id,
                service.DatiFeed(
                    struttura_id=struttura.id,
                    url=f"https://feed.example.com/c{indice}.ics",
                    canale=CanaleFeed.ALTRO,
                ),
            ).id
            for indice in range(CONCORRENTI)
        ]
        with Session(pg_engine) as db:
            for job in db.scalars(
                select(Job).where(Job.job_type == TIPO_JOB_SYNC_PERIODICO)
            ):
                db.delete(job)
            db.commit()

        partenza = threading.Barrier(CONCORRENTI, timeout=10)
        # LA barriera che rende questo test capace di fallire. Si raggiunge
        # DOPO `assicura_sync_periodico` e PRIMA del `commit`, cioè mentre
        # ogni thread TIENE ancora il proprio lock consultivo (è legato alla
        # transazione e si rilascia al commit).
        #
        # Con un lock per Feed gli otto lock sono distinti, quindi tutti e
        # otto arrivano qui e la barriera si apre. Con un lock su chiave
        # costante — la serializzazione globale — solo il primo entra: gli
        # altri sette restano appesi dentro il codice sotto test e non
        # raggiungono mai la barriera, che scade. È lo stesso meccanismo di
        # A3-2, e vive fra i client come impone §2.4.
        #
        # Senza questa barriera il test asseriva solo «8 esiti, 8 cicli»,
        # invarianti entrambi anche sotto serializzazione globale: era verde
        # per costruzione, e la sua stessa docstring diceva «nessun test lo
        # direbbe».
        tutti_hanno_il_lock = threading.Barrier(CONCORRENTI, timeout=10)

        def bootstrap_di(indice: int) -> str:
            with Session(pg_engine) as db:
                feed = db.get(FeedIcal, feed_id[indice])
                assert feed is not None
                partenza.wait()
                try:
                    assicura_sync_periodico(db, feed)
                except Exception as exc:  # noqa: BLE001 — l'esito è il dato
                    return f"errore:{type(exc).__name__}"
                finally:
                    tutti_hanno_il_lock.wait()
                db.commit()
                return "fatto"

        with ThreadPoolExecutor(max_workers=CONCORRENTI) as esecutore:
            assert (
                list(esecutore.map(bootstrap_di, range(CONCORRENTI)))
                == ["fatto"] * CONCORRENTI
            )

        with Session(pg_engine) as db:
            cicli = db.scalars(
                select(Job).where(
                    Job.job_type == TIPO_JOB_SYNC_PERIODICO,
                    Job.status == JobStatus.PENDING,
                )
            ).all()
        # Uno per Feed: né duplicati né mancanti.
        assert len(cicli) == CONCORRENTI
        assert {job.payload["feed_id"] for job in cicli} == {
            str(identificatore) for identificatore in feed_id
        }
