"""Test di gara sulla cancellazione di una Prenotazione manuale (Story 2.4).

Il test design dell'Epic 2 non elenca un percorso A3 per la 2.4, e la lettura
è corretta: nessun vincolo persistito nasce qui. Questo test esiste comunque,
perché la forma del difetto c'è ed è quella della regola §2.4 — **due
scritture legittime e concorrenti sulla stessa riga**, cioè la famiglia di
A3-7. Il caso reale non è esotico: l'Host clicca due volte, o clicca su due
schede.

Il rimedio non è un lock: la transizione è **condizionata allo stato letto**
(`UPDATE … WHERE stato = 'attiva'`), quindi la lettura e la scrittura sono la
stessa istruzione e a decidere chi vince è il database. Ciò che si osserva è
la conseguenza che conta: **un solo** `prenotazione.cessata` in `outbox` e
**una sola** decorrenza `cessata_il`.

Perché quelle due, e non «lo stato finale è cancellata»: lo stato finale è
`cancellata` anche con un check-then-write ingenuo — è invariante sotto
serializzazione, quindi non distingue nulla. Un secondo evento invece farebbe
`decadere` due volte lo stesso Conflitto nella 2.5, e una `cessata_il`
riscritta rimanderebbe in avanti la scadenza di un dato personale (AD-21).

Forma imposta dal test design §2.4 (A3): 8 contendenti, `threading.Barrier`
allineato **fra i client** e mai dentro il codice sotto test, una `Session`
fresca per thread, esiti contati **più** una ri-query di post-condizione — e
il riscaldamento prima della barriera, senza il quale la prima esecuzione paga
la compilazione SQLAlchemy per tutte le altre e i thread si scaglionano oltre
la finestra critica (lezione del Lotto B).
"""

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.calendario import service
from app.calendario.models import Prenotazione, StatoPrenotazione
from app.calendario.repository import PrenotazioneRepository
from app.core.date_range import utcnow
from app.core.outbox import OutboxEvent
from tests.calendario import Contesto, crea_manuale

CONCORRENTI = 8

EVENTO_CESSATA = "prenotazione.cessata"


def _quanti_eventi(db: Session) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(OutboxEvent)
            .where(OutboxEvent.event_name == EVENTO_CESSATA)
        )
        or 0
    )


@pytest.mark.timeout(60)
def test_otto_cancellazioni_in_gara_emettono_un_solo_evento(
    pg_engine: Engine, db_session: Session, contesto: Contesto
) -> None:
    manuale = crea_manuale(
        db_session,
        contesto,
        check_in=date(2026, 11, 2),
        check_out=date(2026, 11, 6),
    )
    prenotazione_id = manuale.id
    host_id = contesto.host_id
    db_session.commit()
    assert _quanti_eventi(db_session) == 0

    barriera = threading.Barrier(CONCORRENTI, timeout=10)

    def cancella(_: int) -> str:
        with Session(pg_engine) as db:
            # RISCALDAMENTO: si eseguono le DUE istruzioni del percorso — la
            # lettura e la transizione — su un id inesistente, che le compila
            # e apre la connessione senza scrivere niente. Senza queste righe
            # la finestra critica non si presenta e il test resta verde anche
            # col rimedio rimosso, cioè è un test di gara che non ha mai visto
            # la gara (lezione del Lotto B). La lettura sola non basta: è la
            # `UPDATE` a pagare la compilazione più costosa.
            inesistente = uuid.uuid4()
            try:
                service.cancella_prenotazione(db, host_id, inesistente)
            except service.PrenotazioneNonTrovataError:
                pass
            PrenotazioneRepository(db).marca_cancellata(
                host_id, prenotazione_id=inesistente, adesso=utcnow()
            )
            db.rollback()
            barriera.wait()
            try:
                service.cancella_prenotazione(db, host_id, prenotazione_id)
            except Exception as exc:  # noqa: BLE001 — l'esito è il dato
                return f"errore:{type(exc).__name__}"
            return "fatto"

    with ThreadPoolExecutor(max_workers=CONCORRENTI) as esecutore:
        esiti = list(esecutore.map(cancella, range(CONCORRENTI)))

    # Nessuno deve esplodere: un 500 su un doppio click è un difetto visibile
    # all'Host, e la cancellazione è idempotente per contratto.
    assert [esito for esito in esiti if esito.startswith("errore")] == []
    assert esiti.count("fatto") == CONCORRENTI

    with Session(pg_engine) as db:
        assert _quanti_eventi(db) == 1, (
            "più di un `prenotazione.cessata` per la stessa Prenotazione: "
            "nella 2.5 farebbe `decadere` due volte lo stesso Conflitto"
        )
        righe = list(
            db.scalars(select(Prenotazione).where(Prenotazione.id == prenotazione_id))
        )
        assert len(righe) == 1
        assert righe[0].stato is StatoPrenotazione.CANCELLATA
        assert righe[0].cessata_il is not None
