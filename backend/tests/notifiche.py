"""Helper condivisi dei test di `notifiche`: costruttori, non asserzioni.

Nessun dato reale (NFR-16): gli indirizzi sono `example.com`.
"""

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.jobs import Job
from app.identity.models import CanaleNotifica, Host
from app.notifiche.canali import canali
from app.notifiche.models import (
    CanaleConsegna,
    Notifica,
    NotificaConsegna,
    StatoConsegna,
)
from app.notifiche.registro import Messaggio


@dataclass
class CanaleEmailFinto:
    """Registra ciò che avrebbe spedito. Può essere istruito a fallire."""

    inviati: list[tuple[str, Messaggio]] = field(default_factory=list)
    fallisce: bool = False
    errore: Exception | None = None

    def invia(self, destinatario: str, messaggio: Messaggio) -> None:
        if self.fallisce:
            from app.notifiche.canali import ConsegnaFallitaError

            raise self.errore or ConsegnaFallitaError("canale finto in errore")
        self.inviati.append((destinatario, messaggio))


def installa_email_finta(fallisce: bool = False) -> CanaleEmailFinto:
    """Sostituisce la guardia del conftest con un canale osservabile.

    La rimozione la fa la fixture `isolamento_canale_email`, che al termine
    del test toglie comunque ciò che è installato: un canale finto non può
    sopravvivere al test che lo ha messo.
    """
    finto = CanaleEmailFinto(fallisce=fallisce)
    canali.installa(CanaleConsegna.EMAIL, finto)
    return finto


def preferisci(db: Session, host_id: uuid.UUID, canale: CanaleNotifica) -> None:
    """Imposta la preferenza di notifica dell'Host (FR-20, pannello 1.3)."""
    host = db.get(Host, host_id)
    assert host is not None
    host.canale_notifica_preferito = canale
    db.flush()


def notifiche_di(db: Session, host_id: uuid.UUID) -> list[Notifica]:
    return list(
        db.scalars(
            select(Notifica)
            .where(Notifica.host_id == host_id)
            .order_by(Notifica.creata_il, Notifica.id)
        )
    )


def consegne_di(db: Session, host_id: uuid.UUID) -> list[NotificaConsegna]:
    return list(
        db.scalars(
            select(NotificaConsegna)
            .where(NotificaConsegna.host_id == host_id)
            .order_by(NotificaConsegna.canale, NotificaConsegna.id)
        )
    )


def consegna_su(
    db: Session, host_id: uuid.UUID, canale: CanaleConsegna
) -> NotificaConsegna | None:
    for consegna in consegne_di(db, host_id):
        if consegna.canale is canale:
            return consegna
    return None


def inviate(db: Session, host_id: uuid.UUID) -> list[NotificaConsegna]:
    return [
        consegna
        for consegna in consegne_di(db, host_id)
        if consegna.stato is StatoConsegna.INVIATA
    ]


def job_di_consegna(db: Session) -> list[Job]:
    from app.notifiche.jobs import TIPO_JOB_CONSEGNA_NOTIFICA

    return list(
        db.scalars(
            select(Job)
            .where(Job.job_type == TIPO_JOB_CONSEGNA_NOTIFICA)
            .order_by(Job.created_at, Job.id)
        )
    )
