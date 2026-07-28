"""Scheduling durevole (AD-10).

Ogni azione futura è una riga in `job` (due_at, tipo, payload, stato,
tentativi, backoff); il worker fa claim con SELECT ... FOR UPDATE SKIP LOCKED.
Consegna at-least-once: ogni handler DEVE essere idempotente. Vietato
schedulare con timer di processo non persistiti.
"""

import enum
import logging
import uuid
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta

from sqlalchemy import DateTime, Enum, Index, Integer, String, Text, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.date_range import utcnow
from app.core.db import Base, new_uuid7
from app.core.events import Catalog
from app.core.events import catalog as production_catalog

logger = logging.getLogger(__name__)

JobHandler = Callable[[Session, dict], None]

DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_BACKOFF_BASE_SECONDS = 60


class JobStatus(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Job(Base):
    __tablename__ = "job"
    __table_args__ = (
        # Indice PARZIALE sui soli job in attesa: è la query di `claim_due`,
        # e la coda a regime è quasi tutta fatta di righe `completed` che un
        # indice pieno indicizzerebbe per niente.
        #
        # Dichiarato qui e non solo nella migrazione 0001: un indice che vive
        # nel database e non nei modelli è deriva, e `alembic check` in CI
        # (MYL-44) la segnala come una `remove_index` da applicare — cioè
        # propone di cancellare l'indice che serve.
        Index(
            "ix_job_due",
            "status",
            "due_at",
            postgresql_where=text("status = 'pending'"),
        ),
        # Indice PARZIALE sui job ATTIVI, per tipo: è la query di idempotenza
        # di ogni bootstrap periodico («c'è già un ciclo di QUESTO tipo in
        # coda?»). `ix_job_due` non la serve — è parziale su
        # `status = 'pending'` e il predicato qui è `IN (pending, running)`,
        # quindi il pianificatore non può usarlo e resta il sequential scan
        # sull'intera tabella. Morde per primo al bootstrap del worker, che fa
        # una query per Feed a ogni riavvio, su una coda fatta quasi
        # interamente di righe `completed` (MYL-51).
        #
        # Solo `job_type`, senza espressione sul payload: un indice su
        # `payload->>'feed_id'` legherebbe lo schema del kernel alla forma del
        # payload di un dominio — è lo stesso argomento AD-1 con cui
        # `assicura_sync_periodico` rifiuta il `UNIQUE` parziale — e non
        # serve, perché la parte parziale riduce già i candidati ai soli job
        # ATTIVI di quel tipo, che sono al più uno per Feed.
        Index(
            "ix_job_attivi",
            "job_type",
            postgresql_where=text("status IN ('pending', 'running')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid7)
    job_type: Mapped[str] = mapped_column(String(200), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        Enum(
            JobStatus,
            name="job_status",
            values_callable=lambda e: [s.value for s in e],
        ),
        nullable=False,
        default=JobStatus.PENDING,
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=DEFAULT_MAX_ATTEMPTS
    )
    backoff_base_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=DEFAULT_BACKOFF_BASE_SECONDS
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


def schedule(
    session: Session,
    job_type: str,
    payload: Mapping[str, object],
    *,
    due_at: datetime,
    catalog: Catalog | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    backoff_base_seconds: int = DEFAULT_BACKOFF_BASE_SECONDS,
) -> Job:
    """Accoda un job durevole nella transazione corrente."""
    active_catalog = catalog if catalog is not None else production_catalog
    active_catalog.validate_job_payload(job_type, payload)
    job = Job(
        job_type=job_type,
        payload=dict(payload),
        due_at=due_at,
        max_attempts=max_attempts,
        backoff_base_seconds=backoff_base_seconds,
    )
    session.add(job)
    return job


class JobHandlers:
    """Registro degli handler per tipo di job."""

    def __init__(self) -> None:
        self._handlers: dict[str, JobHandler] = {}

    def register(self, job_type: str) -> Callable[[JobHandler], JobHandler]:
        def decorator(fn: JobHandler) -> JobHandler:
            self._handlers[job_type] = fn
            return fn

        return decorator

    def handler_for(self, job_type: str) -> JobHandler | None:
        return self._handlers.get(job_type)


# Registro di produzione: i moduli registrano qui i propri handler.
handlers = JobHandlers()


def claim_due(
    session: Session, *, now: datetime | None = None, limit: int = 10
) -> list[Job]:
    """Fa claim dei job scaduti con FOR UPDATE SKIP LOCKED e li marca RUNNING."""
    moment = now if now is not None else utcnow()
    claimed = list(
        session.scalars(
            select(Job)
            .where(Job.status == JobStatus.PENDING, Job.due_at <= moment)
            .order_by(Job.due_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    for job in claimed:
        job.status = JobStatus.RUNNING
    session.flush()
    return claimed


def _handle_failure(job: Job, error: Exception, moment: datetime) -> None:
    job.attempts += 1
    job.last_error = f"{type(error).__name__}: {error}"
    if job.attempts >= job.max_attempts:
        job.status = JobStatus.FAILED
        logger.error(
            "job fallito definitivamente",
            extra={"job_type": job.job_type, "job_id": str(job.id)},
        )
    else:
        # Backoff esponenziale: base * 2^(tentativi già consumati - 1).
        delay = job.backoff_base_seconds * 2 ** (job.attempts - 1)
        job.due_at = moment + timedelta(seconds=delay)
        job.status = JobStatus.PENDING


def run_due_jobs(
    session: Session,
    job_handlers: JobHandlers | None = None,
    *,
    now: datetime | None = None,
    limit: int = 10,
) -> int:
    """Esegue i job scaduti; ritorna quanti ne ha completati."""
    active_handlers = job_handlers if job_handlers is not None else handlers
    moment = now if now is not None else utcnow()
    completed = 0
    for job in claim_due(session, now=moment, limit=limit):
        handler = active_handlers.handler_for(job.job_type)
        if handler is None:
            _handle_failure(
                job, LookupError(f"nessun handler per '{job.job_type}'"), moment
            )
            continue
        try:
            # SAVEPOINT per item (G-1): un handler che scrive e poi fallisce
            # non lascia scritture parziali; il retry riparte da stato pulito.
            with session.begin_nested():
                handler(session, job.payload)
        except Exception as exc:
            logger.exception(
                "esecuzione job fallita",
                extra={"job_type": job.job_type, "job_id": str(job.id)},
            )
            _handle_failure(job, exc, moment)
            continue
        job.status = JobStatus.COMPLETED
        completed += 1
    session.flush()
    return completed
