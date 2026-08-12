"""Gara A3-4: «mai due Conflitti aperti per la stessa coppia» (AD-5).

Il caso reale non è esotico ed è quello descritto dal test design: **due Feed
della stessa Struttura che concludono l'import insieme**. Ogni import termina
con una rilevazione, entrambe leggono lo stesso insieme di Prenotazioni
`attiva`, entrambe trovano la stessa coppia sovrapposta, ed entrambe si
trovano davanti alla domanda «esiste già un Conflitto?». Con un controllo
applicativo passano tutte e due.

Il rimedio non è un lock: è un **indice UNIQUE parziale** sullo stato
`rilevato`, con la coppia in ordine canonico. Senza canonicalizzazione `(A,B)`
e `(B,A)` sono due righe diverse per l'indice e il vincolo non morde — cioè
l'invariante sarebbe violabile **senza violare la lettera dell'AC** (§4.2-4).
Qui la canonicalizzazione è imposta a sua volta da un CHECK, quindi le due
metà non possono separarsi.

Ciò che si osserva NON è lo stato finale: «esiste un Conflitto rilevato» è
vero anche con due righe. Si contano le righe e gli EVENTI — un secondo
`conflitto.rilevato` diventerebbe una seconda notifica all'Host nella 2.6, che
è il modo in cui la funzione di fiducia del prodotto comincia a fare rumore.

Forma imposta dal test design §2.4: 8 contendenti, `threading.Barrier`
allineata **fra i client** e mai dentro il codice sotto test, una `Session`
fresca per thread, esiti contati **più** una ri-query di post-condizione — e
il riscaldamento con `rollback` prima della barriera, senza il quale la prima
esecuzione paga la compilazione SQLAlchemy per tutte le altre e i thread si
scaglionano oltre la finestra critica (lezione del Lotto B).
"""

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.calendario import service
from app.calendario.models import Conflitto, StatoConflitto
from app.core.outbox import OutboxEvent
from tests.calendario import Contesto, crea_prenotazione

CONCORRENTI = 8


def _quanti_eventi(db: Session) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(OutboxEvent)
            .where(OutboxEvent.event_name == service.EVENTO_CONFLITTO_RILEVATO)
        )
        or 0
    )


@pytest.mark.timeout(60)
def test_otto_rilevazioni_in_gara_aprono_un_solo_conflitto(
    pg_engine: Engine, db_session: Session, contesto: Contesto
) -> None:
    crea_prenotazione(
        db_session, contesto, check_in=date(2026, 10, 1), check_out=date(2026, 10, 5)
    )
    crea_prenotazione(
        db_session, contesto, check_in=date(2026, 10, 4), check_out=date(2026, 10, 8)
    )
    db_session.commit()
    host_id = contesto.host_id
    struttura_id = contesto.struttura_id
    assert _quanti_eventi(db_session) == 0

    barriera = threading.Barrier(CONCORRENTI, timeout=10)

    def rileva(_: int) -> str:
        with Session(pg_engine) as db:
            # RISCALDAMENTO: si esegue il percorso INTERO — la lettura delle
            # Prenotazioni attive e l'`INSERT … ON CONFLICT` — e si fa
            # `rollback`, che non lascia niente scritto. Senza queste righe la
            # finestra critica non si presenta: la prima esecuzione paga
            # l'apertura della connessione e la compilazione, e il test resta
            # verde anche con l'indice rimosso — cioè è un test di gara che
            # non ha mai visto la gara.
            service.rivaluta_conflitti(db, host_id, struttura_id)
            db.rollback()
            barriera.wait()
            try:
                aperti = service.rivaluta_conflitti(db, host_id, struttura_id)
                db.commit()
            except Exception as exc:  # noqa: BLE001 — l'esito è il dato
                return f"errore:{type(exc).__name__}"
            return f"aperti:{aperti}"

    with ThreadPoolExecutor(max_workers=CONCORRENTI) as esecutore:
        esiti = list(esecutore.map(rileva, range(CONCORRENTI)))

    # Nessuno deve esplodere: un `IntegrityError` che risale sarebbe un 500
    # dentro un job di sync, cioè un import fallito per un Conflitto che il
    # sistema ha rilevato correttamente.
    assert [esito for esito in esiti if esito.startswith("errore")] == []
    assert esiti.count("aperti:1") == 1, (
        f"più di un contendente dichiara di aver aperto il Conflitto: {esiti}"
    )

    with Session(pg_engine) as db:
        aperti = list(
            db.scalars(
                select(Conflitto).where(Conflitto.stato == StatoConflitto.RILEVATO)
            )
        )
        assert len(aperti) == 1, (
            "due Conflitti aperti per la stessa coppia: l'indice UNIQUE "
            "parziale non sta imponendo l'identità di AD-5"
        )
        assert _quanti_eventi(db) == 1, (
            "più di un `conflitto.rilevato` per la stessa coppia: nella 2.6 "
            "sarebbe una seconda notifica all'Host per lo stesso fatto"
        )
