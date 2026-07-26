"""Sync dei Feed iCal come job durevole (AD-10, AD-17).

Il collegamento di un Feed accoda un job **scaduto subito** (`due_at` =
adesso): il worker lo prende al primo giro, prima di qualunque ciclo
periodico, che per costruzione ha `due_at` nel futuro. È così che l'import
on-demand è «prioritario» senza introdurre una nozione di priorità nel
kernel — che sarebbe un cambio di `core` per un bisogno di un solo dominio.

Il poller periodico e la sua riprogrammazione sono della Story 2.2: qui c'è
solo l'import su richiesta.
"""

import logging
import uuid

from sqlalchemy.orm import Session

from app.calendario.models import FeedIcal
from app.core.date_range import utcnow
from app.core.events import catalog
from app.core.jobs import Job, handlers, schedule

logger = logging.getLogger(__name__)

TIPO_JOB_SYNC_FEED = "feed_ical.sync_richiesto"

# AD-17: i tipi si dichiarano nel catalogo unico, con payload di SOLI
# identificatori scalari — mai nomi di Ospiti, mai snapshot di stato.
catalog.register_job(TIPO_JOB_SYNC_FEED, payload_keys=("feed_id", "host_id"))


def accoda_sync_immediato(db: Session, feed: FeedIcal) -> Job:
    """Job di sync scaduto subito, nella transazione del chiamante."""
    return schedule(
        db,
        TIPO_JOB_SYNC_FEED,
        {"feed_id": str(feed.id), "host_id": str(feed.host_id)},
        due_at=utcnow(),
    )


@handlers.register(TIPO_JOB_SYNC_FEED)
def esegui_sync_del_feed(db: Session, payload: dict) -> None:
    """Handler idempotente: rieseguirlo non duplica né perde Prenotazioni.

    L'import è idempotente per costruzione (upsert su `(feed_id, ical_uid)`),
    che è la proprietà richiesta dalla consegna at-least-once di AD-10.
    """
    # Import locale: `service` importa questo modulo per accodare, quindi al
    # livello di modulo il ciclo si chiuderebbe.
    from app.calendario import service

    feed_id = uuid.UUID(str(payload["feed_id"]))
    host_id = uuid.UUID(str(payload["host_id"]))
    run = service.esegui_sync(db, host_id, feed_id)
    logger.info(
        "job di sync eseguito",
        extra={"feed_id": str(feed_id), "esito": run.esito.value},
    )
