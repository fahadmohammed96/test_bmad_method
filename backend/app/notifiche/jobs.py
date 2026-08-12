"""La consegna di una notifica è un job durevole (AD-10, AD-17).

Mai un invio dentro la transazione che ha rilevato il fatto: il Conflitto si
scrive e la notifica si accoda, e se il processo muore fra le due cose non
muore niente, perché sono la stessa transazione. Vietato un timer di processo.

Un job **per canale**: `payload = (consegna_id, host_id)`, soli
identificatori. Né il testo né l'indirizzo dell'Host passano di qui — la coda
`job` è leggibile da chi amministra il sistema e sopravvive alla retention che
AD-21 impone all'anagrafica (AD-16, AD-17, NFR-11).
"""

import logging
import uuid

from sqlalchemy.orm import Session

from app.core.date_range import utcnow
from app.core.events import catalog
from app.core.jobs import Job, handlers, schedule
from app.notifiche.models import NotificaConsegna

logger = logging.getLogger(__name__)

TIPO_JOB_CONSEGNA_NOTIFICA = "notifica.consegna_richiesta"

catalog.register_job(
    TIPO_JOB_CONSEGNA_NOTIFICA, payload_keys=("consegna_id", "host_id")
)


def accoda_consegna(db: Session, consegna: NotificaConsegna) -> Job:
    """Job scaduto subito: la notifica di un Conflitto non aspetta un ciclo."""
    return schedule(
        db,
        TIPO_JOB_CONSEGNA_NOTIFICA,
        {"consegna_id": str(consegna.id), "host_id": str(consegna.host_id)},
        due_at=utcnow(),
    )


@handlers.register(TIPO_JOB_CONSEGNA_NOTIFICA)
def esegui_consegna(db: Session, payload: dict) -> None:
    """Handler idempotente: rieseguirlo non manda una seconda volta."""
    # Import locale: `service` importa questo modulo per accodare, quindi al
    # livello di modulo il ciclo si chiuderebbe.
    from app.notifiche import service

    host_id = uuid.UUID(str(payload["host_id"]))
    consegna_id = uuid.UUID(str(payload["consegna_id"]))
    service.consegna(db, host_id, consegna_id)
