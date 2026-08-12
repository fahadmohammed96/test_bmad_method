"""Repository di `notifiche`: nessuna query di dominio fuori da qui (AD-2).

I due metodi che contano sono **due check-then-write chiusi nel database**, e
non è una preferenza di stile: la consegna degli eventi e dei job è
at-least-once (AD-10), quindi lo stesso percorso viene rieseguito, e il caso
concorrente non è raro — un Conflitto rilevato da due import che concludono
insieme produce due consegne dello stesso evento (gara A3-5).

- `apri` — «è già stata notificata?» seguito da «notifica»: la risposta è il
  UNIQUE su `(host_id, tipo, riferimento_id)` con `ON CONFLICT DO NOTHING`, e
  la domanda «l'ho aperta io?» ha per risposta il `RETURNING`.
- `marca_inviata` — «è ancora da inviare?» seguito da «invia»: la condizione
  sullo stato sta DENTRO la `UPDATE`, e il chiamante invia solo se ha vinto.

In entrambi i casi si guarda il `RETURNING` e mai il `rowcount`: su questa
famiglia di istruzioni SQLAlchemy restituisce `-1` quando il conteggio non è
disponibile, e `-1` è VERO in un `if` — il difetto della Story 2.5, che era
invisibile allo stato persistito e visibile solo a valle.
"""

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.db import new_uuid7
from app.notifiche.models import (
    CanaleConsegna,
    Notifica,
    NotificaConsegna,
    StatoConsegna,
)
from app.notifiche.registro import Messaggio


class NotificaRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def apri(
        self,
        host_id: uuid.UUID,
        *,
        tipo: str,
        riferimento_id: uuid.UUID,
        adesso: datetime,
    ) -> uuid.UUID | None:
        """Apre la notifica se non esiste già; `None` se esisteva.

        `None` non è un errore: è la risposta corretta al secondo sync che
        rileva lo stesso Conflitto. Chi riceve `None` non accoda nulla, ed è
        così che «alla prima rilevazione, non a ogni sync» smette di essere
        una promessa del codice.
        """
        nuovo_id = new_uuid7()
        istruzione = (
            pg_insert(Notifica)
            .values(
                id=nuovo_id,
                host_id=host_id,
                tipo=tipo,
                riferimento_id=riferimento_id,
                creata_il=adesso,
            )
            .on_conflict_do_nothing(
                index_elements=["host_id", "tipo", "riferimento_id"]
            )
            .returning(Notifica.id)
        )
        return None if self._db.execute(istruzione).first() is None else nuovo_id

    def by_id(self, host_id: uuid.UUID, notifica_id: uuid.UUID) -> Notifica | None:
        return self._db.scalars(
            select(Notifica).where(
                Notifica.host_id == host_id, Notifica.id == notifica_id
            )
        ).one_or_none()


class ConsegnaRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def aggiungi(
        self, host_id: uuid.UUID, *, notifica_id: uuid.UUID, canale: CanaleConsegna
    ) -> NotificaConsegna:
        consegna = NotificaConsegna(
            host_id=host_id,
            notifica_id=notifica_id,
            canale=canale,
            stato=StatoConsegna.IN_ATTESA,
        )
        self._db.add(consegna)
        self._db.flush()
        return consegna

    def by_id(
        self, host_id: uuid.UUID, consegna_id: uuid.UUID
    ) -> NotificaConsegna | None:
        return self._db.scalars(
            select(NotificaConsegna).where(
                NotificaConsegna.host_id == host_id,
                NotificaConsegna.id == consegna_id,
            )
        ).one_or_none()

    def marca_inviata(
        self,
        host_id: uuid.UUID,
        *,
        consegna_id: uuid.UUID,
        messaggio: Messaggio,
        adesso: datetime,
    ) -> bool:
        """Prende in carico la consegna: `True` solo a chi ha vinto la corsa.

        La marcatura precede l'invio e non lo segue, ed è la sola forma che
        regge sotto concorrenza: otto esecuzioni dello stesso job che
        inviassero prima di marcare manderebbero otto email e ne
        registrerebbero una. Qui il `WHERE` sullo stato serializza sulla riga,
        e i sette che perdono non toccano il canale.

        Se poi il canale fallisce, l'eccezione risale e il SAVEPOINT del
        kernel (G-1) annulla questa marcatura insieme al resto: nessuno stato
        di successo sopravvive a un esito che non c'è stato, e la consegna
        torna `in_attesa` per il ritentativo (AC 7).

        Il testo si scrive QUI, nello stesso istante: è ciò che l'Host ha
        ricevuto davvero, e per il canale in-app è la notifica stessa.
        """
        istruzione = (
            update(NotificaConsegna)
            .where(
                NotificaConsegna.host_id == host_id,
                NotificaConsegna.id == consegna_id,
                NotificaConsegna.stato == StatoConsegna.IN_ATTESA,
            )
            .values(
                stato=StatoConsegna.INVIATA,
                oggetto=messaggio.oggetto,
                corpo=messaggio.corpo,
                inviata_il=adesso,
            )
            .returning(NotificaConsegna.id)
        )
        return self._db.execute(istruzione).first() is not None
