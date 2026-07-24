"""Test dello scheduling durevole (AD-10).

Ogni azione futura è una riga in `job`; claim con SELECT ... FOR UPDATE
SKIP LOCKED; consegna at-least-once con retry/backoff; handler idempotenti.
"""

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.date_range import utcnow
from app.core.events import Catalog, UnknownTypeError
from app.core.jobs import (
    Job,
    JobHandlers,
    JobStatus,
    claim_due,
    run_due_jobs,
    schedule,
)


@pytest.fixture
def test_catalog() -> Catalog:
    c = Catalog()
    c.register_job("promemoria.invia", payload_keys=("adempimento_id",))
    return c


def _schedule_due_now(session: Session, catalog: Catalog, **kwargs) -> Job:
    return schedule(
        session,
        "promemoria.invia",
        {"adempimento_id": str(uuid.uuid4())},
        due_at=utcnow() - timedelta(seconds=1),
        catalog=catalog,
        **kwargs,
    )


class TestSchedule:
    def test_schedula_una_riga_job(
        self, db_session: Session, test_catalog: Catalog
    ) -> None:
        job = _schedule_due_now(db_session, test_catalog)
        db_session.commit()
        assert job.status is JobStatus.PENDING
        assert job.attempts == 0

    def test_job_type_non_a_catalogo_rifiutato(
        self, db_session: Session, test_catalog: Catalog
    ) -> None:
        with pytest.raises(UnknownTypeError):
            schedule(
                db_session,
                "job.inventato",
                {},
                due_at=utcnow(),
                catalog=test_catalog,
            )


class TestClaim:
    def test_claim_prende_solo_job_scaduti(
        self, db_session: Session, test_catalog: Catalog
    ) -> None:
        _schedule_due_now(db_session, test_catalog)
        schedule(
            db_session,
            "promemoria.invia",
            {"adempimento_id": str(uuid.uuid4())},
            due_at=utcnow() + timedelta(hours=1),
            catalog=test_catalog,
        )
        db_session.commit()

        claimed = claim_due(db_session)
        db_session.commit()
        assert len(claimed) == 1

    def test_claim_concorrente_skip_locked(
        self,
        db_session: Session,
        second_session: Session,
        test_catalog: Catalog,
    ) -> None:
        _schedule_due_now(db_session, test_catalog)
        db_session.commit()

        # Primo worker in transazione aperta: tiene il lock sulla riga.
        claimed_a = claim_due(db_session)
        claimed_b = claim_due(second_session)
        db_session.commit()

        assert len(claimed_a) == 1
        assert claimed_b == []


class TestExecution:
    def test_handler_eseguito_e_job_completato(
        self, db_session: Session, test_catalog: Catalog
    ) -> None:
        eseguiti: list[dict] = []
        handlers = JobHandlers()
        handlers.register("promemoria.invia")(
            lambda session, payload: eseguiti.append(payload)
        )
        job = _schedule_due_now(db_session, test_catalog)
        db_session.commit()

        assert run_due_jobs(db_session, handlers) == 1
        db_session.commit()

        db_session.refresh(job)
        assert job.status is JobStatus.COMPLETED
        assert eseguiti == [job.payload]

    def test_fallimento_riprogramma_con_backoff(
        self, db_session: Session, test_catalog: Catalog
    ) -> None:
        handlers = JobHandlers()

        @handlers.register("promemoria.invia")
        def handler_rotto(session: Session, payload: dict) -> None:
            raise RuntimeError("smtp non raggiungibile")

        job = _schedule_due_now(db_session, test_catalog, max_attempts=3)
        db_session.commit()
        prima_scadenza = job.due_at

        run_due_jobs(db_session, handlers)
        db_session.commit()

        db_session.refresh(job)
        assert job.status is JobStatus.PENDING  # riproverà: at-least-once
        assert job.attempts == 1
        assert job.last_error is not None
        assert "smtp" in job.last_error
        assert job.due_at > prima_scadenza  # backoff, non retry immediato

    def test_esauriti_i_tentativi_il_job_e_failed(
        self, db_session: Session, test_catalog: Catalog
    ) -> None:
        handlers = JobHandlers()
        handlers.register("promemoria.invia")(
            lambda session, payload: (_ for _ in ()).throw(RuntimeError("boom"))
        )
        job = _schedule_due_now(db_session, test_catalog, max_attempts=1)
        db_session.commit()

        run_due_jobs(db_session, handlers)
        db_session.commit()

        db_session.refresh(job)
        assert job.status is JobStatus.FAILED

    def test_job_senza_handler_registrato_fallisce_con_motivo(
        self, db_session: Session, test_catalog: Catalog
    ) -> None:
        job = _schedule_due_now(db_session, test_catalog, max_attempts=1)
        db_session.commit()

        run_due_jobs(db_session, JobHandlers())
        db_session.commit()

        db_session.refresh(job)
        assert job.status is JobStatus.FAILED
        assert job.last_error is not None

    def test_handler_idempotente_su_doppia_esecuzione(
        self, db_session: Session, test_catalog: Catalog
    ) -> None:
        # Consegna at-least-once: lo stesso payload eseguito due volte
        # deve produrre lo stesso stato finale (contratto degli handler).
        stato: set[str] = set()
        handlers = JobHandlers()
        handlers.register("promemoria.invia")(
            lambda session, payload: stato.add(payload["adempimento_id"])
        )

        job = _schedule_due_now(db_session, test_catalog)
        db_session.commit()
        run_due_jobs(db_session, handlers)
        db_session.commit()

        # Simula la riconsegna dello stesso job (crash dopo l'esecuzione,
        # prima del commit di stato).
        job.status = JobStatus.PENDING
        job.due_at = utcnow() - timedelta(seconds=1)
        db_session.commit()
        run_due_jobs(db_session, handlers)
        db_session.commit()

        assert len(stato) == 1

    def test_i_job_futuri_restano_pending(
        self, db_session: Session, test_catalog: Catalog
    ) -> None:
        handlers = JobHandlers()
        handlers.register("promemoria.invia")(lambda session, payload: None)
        schedule(
            db_session,
            "promemoria.invia",
            {"adempimento_id": str(uuid.uuid4())},
            due_at=utcnow() + timedelta(hours=1),
            catalog=test_catalog,
        )
        db_session.commit()

        assert run_due_jobs(db_session, handlers) == 0
        job = db_session.scalars(select(Job)).one()
        assert job.status is JobStatus.PENDING
