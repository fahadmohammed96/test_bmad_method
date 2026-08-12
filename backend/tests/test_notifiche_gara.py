"""Gara A3-5: «è già stata notificata?» seguito da «invia» è un check-then-write.

Due percorsi, e sono due domande diverse che si somigliano:

1. **Apertura della notifica.** Due Feed della stessa Struttura che concludono
   l'import insieme producono due consegne dello stesso `conflitto.rilevato`;
   entrambe chiedono «esiste già una notifica per questo Conflitto?» e con un
   controllo applicativo passano tutte e due. Il rimedio è il UNIQUE su
   `(host_id, tipo, riferimento_id)` con `ON CONFLICT DO NOTHING`.
2. **Consegna del canale.** Otto esecuzioni concorrenti dello stesso job
   chiedono «è ancora da inviare?» e poi inviano. Il rimedio è la condizione
   sullo stato DENTRO la `UPDATE`, con la decisione presa sul `RETURNING`: chi
   non ha vinto non tocca il canale. Marcare dopo l'invio manderebbe otto
   email e ne registrerebbe una.

Forma imposta dal test design §2.4: 8 contendenti, `threading.Barrier`
allineata **fra i client** e mai dentro il codice sotto test, una `Session`
fresca per thread, esiti contati **più** una ri-query di post-condizione, e il
riscaldamento con `rollback` prima della barriera — senza il quale la prima
esecuzione paga la compilazione SQLAlchemy per tutte le altre e i thread si
scaglionano oltre la finestra critica (lezione del Lotto B).

Il riscaldamento della seconda gara passa dalla consegna **in-app** e non da
quella email: è la stessa istruzione sulla stessa tabella, ma il canale in-app
non ha effetti esterni — riscaldare sull'email conterebbe otto invii di
riscaldamento e renderebbe illeggibile il numero che conta.
"""

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.calendario import service as calendario_service
from app.notifiche import service as notifiche_service
from app.notifiche.models import (
    CanaleConsegna,
    Notifica,
    NotificaConsegna,
    StatoConsegna,
)
from tests.calendario import Contesto, conflitti, consegna_eventi, crea_prenotazione
from tests.notifiche import consegna_su, installa_email_finta, job_di_consegna

CONCORRENTI = 8


def _conflitto_rilevato(db: Session, contesto: Contesto) -> uuid.UUID:
    crea_prenotazione(
        db, contesto, check_in=date(2026, 8, 12), check_out=date(2026, 8, 18)
    )
    crea_prenotazione(
        db, contesto, check_in=date(2026, 8, 15), check_out=date(2026, 8, 20)
    )
    calendario_service.rivaluta_conflitti(db, contesto.host_id, contesto.struttura_id)
    db.commit()
    return conflitti(db, contesto)[0].id


def _quante_notifiche(db: Session) -> int:
    return int(db.scalar(select(func.count()).select_from(Notifica)) or 0)


@pytest.mark.timeout(60)
def test_otto_richieste_in_gara_aprono_una_sola_notifica(
    pg_engine: Engine, db_session: Session, contesto: Contesto
) -> None:
    from app.cablaggio import TIPO_NOTIFICA_CONFLITTO_RILEVATO

    conflitto_id = _conflitto_rilevato(db_session, contesto)
    host_id = contesto.host_id
    assert _quante_notifiche(db_session) == 0

    barriera = threading.Barrier(CONCORRENTI, timeout=10)

    def richiedi(_: int) -> str:
        with Session(pg_engine) as db:
            # RISCALDAMENTO: percorso intero — lettura del destinatario,
            # `INSERT … ON CONFLICT`, accodamento dei job — e `rollback`, che
            # non lascia niente scritto.
            notifiche_service.richiedi(
                db,
                host_id,
                tipo=TIPO_NOTIFICA_CONFLITTO_RILEVATO,
                riferimento_id=conflitto_id,
            )
            db.rollback()
            barriera.wait()
            try:
                aperta = notifiche_service.richiedi(
                    db,
                    host_id,
                    tipo=TIPO_NOTIFICA_CONFLITTO_RILEVATO,
                    riferimento_id=conflitto_id,
                )
                db.commit()
            except Exception as exc:  # noqa: BLE001 — l'esito è il dato
                return f"errore:{type(exc).__name__}"
            return "aperta" if aperta is not None else "gia_aperta"

    with ThreadPoolExecutor(max_workers=CONCORRENTI) as esecutore:
        esiti = list(esecutore.map(richiedi, range(CONCORRENTI)))

    # Un `IntegrityError` che risale sarebbe un 500 dentro la consegna di un
    # evento, cioè un batch `outbox` che si blocca su un fatto già trattato.
    assert [esito for esito in esiti if esito.startswith("errore")] == []
    assert esiti.count("aperta") == 1, (
        f"più di un contendente dichiara di aver aperto la notifica: {esiti}"
    )

    with Session(pg_engine) as db:
        assert _quante_notifiche(db) == 1, (
            "due notifiche per lo stesso Conflitto: il UNIQUE su "
            "(host_id, tipo, riferimento_id) non sta imponendo l'identità"
        )
        consegne = list(db.scalars(select(NotificaConsegna)))
        assert len(consegne) == 2, f"consegne duplicate: {len(consegne)}"
        assert len(job_di_consegna(db)) == 2


@pytest.mark.timeout(60)
def test_otto_consegne_in_gara_mandano_una_sola_email(
    pg_engine: Engine, db_session: Session, contesto: Contesto
) -> None:
    _conflitto_rilevato(db_session, contesto)
    consegna_eventi(db_session)
    email = installa_email_finta()

    riga_email = consegna_su(db_session, contesto.host_id, CanaleConsegna.EMAIL)
    riga_in_app = consegna_su(db_session, contesto.host_id, CanaleConsegna.IN_APP)
    assert riga_email is not None and riga_in_app is not None
    host_id = contesto.host_id
    consegna_id = riga_email.id
    riscaldamento_id = riga_in_app.id
    db_session.commit()

    barriera = threading.Barrier(CONCORRENTI, timeout=10)

    def consegna(_: int) -> str:
        with Session(pg_engine) as db:
            # Riscaldamento sulla consegna IN-APP: stessa `UPDATE`, stessa
            # tabella, nessun effetto esterno da contare.
            notifiche_service.consegna(db, host_id, riscaldamento_id)
            db.rollback()
            barriera.wait()
            try:
                inviata = notifiche_service.consegna(db, host_id, consegna_id)
                db.commit()
            except Exception as exc:  # noqa: BLE001 — l'esito è il dato
                return f"errore:{type(exc).__name__}"
            return "inviata" if inviata else "gia_inviata"

    with ThreadPoolExecutor(max_workers=CONCORRENTI) as esecutore:
        esiti = list(esecutore.map(consegna, range(CONCORRENTI)))

    assert [esito for esito in esiti if esito.startswith("errore")] == []
    assert esiti.count("inviata") == 1, (
        f"più di un contendente dichiara di aver consegnato: {esiti}"
    )
    assert len(email.inviati) == 1, (
        f"{len(email.inviati)} email allo stesso Host per lo stesso Conflitto: "
        "la marcatura non sta serializzando l'invio"
    )

    with Session(pg_engine) as db:
        inviate = list(
            db.scalars(
                select(NotificaConsegna).where(
                    NotificaConsegna.canale == CanaleConsegna.EMAIL,
                    NotificaConsegna.stato == StatoConsegna.INVIATA,
                )
            )
        )
        assert len(inviate) == 1
        assert inviate[0].inviata_il is not None
