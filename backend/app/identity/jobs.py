"""Manutenzione periodica di `identity` come job durevole (AD-10, G-5).

Elimina le sessioni oltre scadenza e le tracce ormai inutili dei
tentativi di login. La periodicità vive nella tabella `job`: nessun
timer di processo, quindi un restart non perde il ciclo. L'handler è
idempotente — la consegna è at-least-once.
"""

import logging
from datetime import timedelta
from typing import cast

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.date_range import utcnow
from app.core.events import catalog
from app.core.jobs import Job, JobStatus, handlers, schedule
from app.identity.models import Sessione, TentativoLogin

logger = logging.getLogger(__name__)

TIPO_JOB_PURGE_SESSIONI = "sessione.purge_scadute"

catalog.register_job(TIPO_JOB_PURGE_SESSIONI, payload_keys=())

# Le tracce dei tentativi servono solo dentro la finestra del freno:
# si tengono per qualche finestra in più, poi si buttano.
FINESTRE_DA_CONSERVARE = 4


def _riprogramma(db: Session) -> None:
    schedule(
        db,
        TIPO_JOB_PURGE_SESSIONI,
        {},
        due_at=utcnow()
        + timedelta(minutes=get_settings().purge_sessioni_intervallo_minuti),
    )


@handlers.register(TIPO_JOB_PURGE_SESSIONI)
def purge_sessioni_scadute(db: Session, payload: dict) -> None:
    """Elimina sessioni scadute e tracce vecchie, poi si riprogramma."""
    adesso = utcnow()
    # `cast`: `Session.execute` è tipizzato genericamente, ma una DELETE
    # restituisce sempre un CursorResult, che espone `rowcount`.
    sessioni = cast(
        CursorResult, db.execute(delete(Sessione).where(Sessione.expires_at <= adesso))
    )
    limite_tracce = adesso - timedelta(
        minutes=get_settings().login_finestra_minuti * FINESTRE_DA_CONSERVARE
    )
    tracce = cast(
        CursorResult,
        db.execute(
            delete(TentativoLogin).where(TentativoLogin.avvenuto_il < limite_tracce)
        ),
    )

    _riprogramma(db)
    logger.info(
        "purge periodico eseguito",
        extra={
            "sessioni_eliminate": sessioni.rowcount,
            "tracce_eliminate": tracce.rowcount,
        },
    )


def assicura_purge_periodico(db: Session) -> None:
    """Bootstrap idempotente: un solo job in coda, anche dopo un restart."""
    gia_in_coda = db.scalars(
        select(Job).where(
            Job.job_type == TIPO_JOB_PURGE_SESSIONI,
            Job.status.in_((JobStatus.PENDING, JobStatus.RUNNING)),
        )
    ).first()
    if gia_in_coda is None:
        _riprogramma(db)
